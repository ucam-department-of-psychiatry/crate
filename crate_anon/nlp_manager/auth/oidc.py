"""
crate_anon/nlp_manager/all_processors.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

    This file is part of CRATE.

    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

**Helpers to manage OpenID Connect authentication.**

"""

import hashlib
import json
import logging
import os
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import requests
import requests_oauthlib
from oauthlib.oauth2 import DeviceClient, OAuth2Error

from crate_anon.common.extendedconfigparser import ConfigSection
from crate_anon.nlp_manager.constants import CloudNlpConfigKeys

log = logging.getLogger(__name__)


def default_token_cache() -> str:
    """
    Determine the default token cache directory for the current
    platform.  On Windows this is under ``%APPDATA%``, on Mac it
    is under ``~/Library/Application Support``, on other platforms
    it is under ``~/.cache``.

    Returns:
        an appropriate cache directory.
    """
    if sys.platform == "win32":
        return f"{os.getenv('APPDATA')}\\Crate\\tokens"
    if sys.platform == "darwin":
        return os.path.expanduser("~/Library/Application Support/Crate/tokens")
    return os.path.expanduser("~/.cache/crate_tokens")


class OIDCAuth:
    """
    Class to manage OpenID Connect authentication, both the initial
    login flow to obtain the first token, and the logic to inject
    the current token into API requests and renew it when it expires.
    """

    def __init__(self, cfg: ConfigSection):
        self.issuer = cfg.opt_str(
            CloudNlpConfigKeys.OIDC_ISSUER, required=True
        )
        self.client_id = cfg.opt_str(
            CloudNlpConfigKeys.OIDC_CLIENT_ID, required=True
        )
        self.client_secret = cfg.opt_str(
            CloudNlpConfigKeys.OIDC_CLIENT_SECRET, None
        )
        # Build the set of scopes - default is
        # "openid profile email offline_access" unless overridden by
        # oidc_scope setting.  We use a dict in order to both de-duplicate
        # and preserve the ordering.
        scopes = {
            s: True
            for s in cfg.opt_strlist(
                CloudNlpConfigKeys.OIDC_SCOPE, as_words=True
            )
        }
        if not scopes:
            scopes = {
                "openid": True,
                "profile": True,
                "email": True,
                "offline_access": True,
            }
        # Then add any oidc_extra_scopes to the set
        scopes.update(
            (s, True)
            for s in cfg.opt_strlist(
                CloudNlpConfigKeys.OIDC_EXTRA_SCOPES, as_words=True
            )
        )
        self.scope = " ".join(s for s in scopes)
        self.login_method = cfg.opt_str(
            CloudNlpConfigKeys.OIDC_LOGIN_METHOD, default="web"
        )
        self.callback_port = cfg.opt_int_positive(
            CloudNlpConfigKeys.OIDC_CALLBACK_PORT, 0
        )
        self.cache_dir = Path(
            cfg.opt_str(
                CloudNlpConfigKeys.OIDC_TOKEN_CACHE, default_token_cache()
            )
        )
        self.verify_ssl = cfg.opt_bool(CloudNlpConfigKeys.VERIFY_SSL, True)

        # Private attributes
        self._provider_config = None

    @property
    def provider_config(self):
        """
        The OIDC discovery document downloaded from
        ``{issuer}/.well-known/openid-configuration``.
        """

        if not self._provider_config:
            discovery_url = self.issuer
            if not discovery_url.endswith("/"):
                discovery_url += "/"
            discovery_url = f"{discovery_url}.well-known/openid-configuration"
            discovery_response = requests.get(
                discovery_url, verify=self.verify_ssl
            )
            discovery_response.raise_for_status()
            self._provider_config = discovery_response.json()

        return self._provider_config

    def create_session(
        self, allow_missing=False, pkce: bool | str | None = None, **kwargs
    ):
        """
        Create a ``requests.Session`` that is able to authenticate using
        an OAuth2 Bearer token.  The token is cached on disk and automatically
        renewed on expiry.

        Args:
            allow_missing: if ``False`` (the default), the session creation
                will fail if there is no existing token in the cache.  Pass
                ``True`` to create a session without an initial token, which
                may be fine if the purpose of the session is to begin the
                login flow from scratch.
            pkce: PKCE method to use.  If ``None`` then we will pick the
                best method that the provider declares that it supports,
                if set to ``False`` then PKCE will be disabled even if the
                provider supports it.
            **kwargs: additional keyword arguments to pass to the
                ``requests_oauthlib.OAuth2Session`` constructor.

        Returns:
            session that can be used to make NLPRP API requests.
        """

        os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            self.cache_dir.chmod(0o700)
        except:  # noqa: E722
            # oh well, we tried
            pass

        self.cache = TokenCache(self.cache_dir, self.issuer, self.client_id)
        initial_token = self.cache.load()
        if not initial_token and not allow_missing:
            raise ValueError(
                "OIDC authentication requested, but no token found in cache. "
                "You may need to sign in with crate_nlp --oidc-login"
            )

        # fetch discovery document
        oidc_config = self.provider_config
        token_url = oidc_config["token_endpoint"]
        if pkce is None:
            # Enable PKCE if the provider supports it
            code_challenge_methods = oidc_config.get(
                "code_challenge_methods_supported"
            )
            if code_challenge_methods:
                if "S256" in code_challenge_methods:
                    pkce = "S256"
                elif "plain" in code_challenge_methods:
                    pkce = "plain"
        # for now we assume we're either using a public client, or the
        # provider supports client_secret_post authentication when
        # fetching tokens.
        auto_refresh_kwargs = {"client_id": self.client_id}
        if self.client_secret:
            auto_refresh_kwargs["client_secret"] = self.client_secret

        return requests_oauthlib.OAuth2Session(
            client_id=self.client_id,
            scope=self.scope,
            auto_refresh_url=token_url,
            auto_refresh_kwargs=auto_refresh_kwargs,
            pkce=pkce or None,
            token=initial_token,
            token_updater=self.cache.save_token,
            **kwargs,
        )

    def do_login(self):
        """
        Perform the appropriate login flow, depending on the
        ``oidc_grant_type`` setting in the config file.
        """

        if self.login_method == "web":
            self.auth_code_login()
        elif self.login_method == "device":
            self.device_login()
        else:
            raise ValueError(
                f"Unsupported login method {self.login_method}, "
                "should be one of 'web' or 'device'"
            )

    def auth_code_login(self):
        """
        Authorization code login flow.  Opens the user's browser on
        the authentication page, with the post-login redirect set to
        deliver the auth code to a temporary HTTP server on localhost.
        """

        # Set insecure transport flag to allow us to use a localhost callback
        # os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
        callback_result = ""

        class CallbackHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                nonlocal callback_result
                port = self.server.server_address[1]
                callback_result = f"http://localhost:{port}{self.path}"
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(
                    b"<html><body><h1>Thank you</h1>"
                    b"<p>Authentication complete, you may close this "
                    b"browser.</p></body></html>"
                )

        with HTTPServer(("localhost", 0), CallbackHandler) as callback_server:
            callback_url = (
                f"http://localhost:{callback_server.server_address[1]}"
            )
            callback_server.timeout = 300  # 5 minutes
            with self.create_session(
                allow_missing=True, redirect_uri=callback_url
            ) as session:
                authorization_url, state = session.authorization_url(
                    self.provider_config["authorization_endpoint"]
                )
                print(
                    "If your browser does not open automatically, please "
                    "go to the following URL to sign in:"
                )
                print(authorization_url)
                webbrowser.open(authorization_url, new=2)
                # wait for the callback
                callback_server.handle_request()
                if not callback_result:
                    raise ValueError(
                        "OIDC authentication failed, please try again."
                    )

                token = session.fetch_token(
                    self.provider_config["token_endpoint"],
                    authorization_response=callback_result,
                    include_client_id=True,
                    client_secret=self.client_secret,
                    verify=self.verify_ssl,
                )

                self.cache.save_token(token)
                print("Authentication successful!")

    def device_login(self):
        """
        Device code login flow.  Gives the user a short code that they
        can enter into a login page (possibly using a browser on a
        different device).  We poll the provider's token endpoint, which
        delivers us the token once the user has completed their login
        process.
        """

        if "device_authorization_endpoint" not in self.provider_config:
            raise Exception(
                "Issuer does not support device authorization flow"
            )

        client = DeviceClient(
            client_id=self.client_id, client_secret=self.client_secret
        )
        with self.create_session(
            allow_missing=True, pkce=False, client=client
        ) as session:
            # Request a device code
            code_request_data = {
                "client_id": self.client_id,
                "scope": self.scope,
            }
            if self.client_secret:
                code_request_data["client_secret"] = self.client_secret
            code_request_headers = {
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            }
            code_response = session.post(
                self.provider_config["device_authorization_endpoint"],
                data=code_request_data,
                headers=code_request_headers,
                verify=self.verify_ssl,
            )
            code_response.raise_for_status()
            devicecode = code_response.json()
            log.debug("Device code response: %s", devicecode)
            print(
                "To authenticate, please visit "
                + devicecode["verification_uri"]
                + f" and enter the code {devicecode['user_code']}"
            )
            deadline = time.monotonic() + devicecode["expires_in"]
            interval = devicecode["interval"]
            while time.monotonic() < deadline:
                time.sleep(interval + 0.5)
                try:
                    token = session.fetch_token(
                        token_url=self.provider_config["token_endpoint"],
                        device_code=devicecode["device_code"],
                        include_client_id=True,
                        client_secret=self.client_secret,
                        verify=self.verify_ssl,
                    )
                except OAuth2Error as e:
                    if e.error == "authorization_pending":
                        # User has not completed their part, keep polling
                        continue
                    raise

                self.cache.save_token(token)
                print("Authentication successful!")
                return

            raise ValueError(
                "Authentication not completed in the required time, "
                "please try again."
            )


class TokenCache:
    """
    An on-disk cache for authentication tokens.  Tokens are stored in
    JSON format in the given cache directory, in files whose names are
    a hash of the issuer URL and client ID.
    """

    def __init__(self, cache_dir: Path, issuer: str, client_id: str):
        self.cache_dir = cache_dir
        self.issuer = issuer
        self.client_id = client_id
        self.iss_client_hash = hashlib.sha256(
            f"{issuer}:{client_id}".encode("utf-8")
        ).hexdigest()

    def load(self):
        try:
            with open(
                self.cache_dir / f"{self.iss_client_hash}.json",
                "r",
                encoding="utf-8",
            ) as f:
                return json.load(f)
        except IOError:
            pass
        return None

    def save_token(self, token) -> None:
        """
        Save the given token into the cache directory.  This method
        may be passed to the ``OAuth2Session`` constructor as its
        ``token_updater`` argument.

        Args:
            token: the token to be persisted
        """
        try:
            token_file = self.cache_dir / f"{self.iss_client_hash}.json"
            tmp_file = self.cache_dir / f"{self.iss_client_hash}.tmp"
            with tmp_file.open("w", encoding="utf-8") as f:
                json.dump(token, f)
            tmp_file.replace(token_file)
        except IOError:
            log.warning(
                "Failed to save refreshed token for issuer %s, client %s",
                self.issuer,
                self.client_id,
            )
