#!/usr/bin/env python

r"""
crate_anon/nlp_web/security.py

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

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
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.

===============================================================================
"""

import bcrypt
import binascii
import base64
from typing import Dict, Optional

from cryptography.fernet import Fernet
# noinspection PyUnresolvedReferences
from paste.httpheaders import AUTHORIZATION
from pyramid.request import Request

from crate_anon.nlp_web.constants import SETTINGS


def generate_encryption_key() -> None:
    """
    Generates a key to be used for reversible encryption of passwords and
    prints it to screen. The key should then be put in the config file.

    To be called via the command line.
    """
    key = Fernet.generate_key()
    print(key)


def encrypt_password(password: str) -> bytes:
    key = SETTINGS['encryption_key']
    # Turn key into bytes object
    key = key.encode()
    cipher_suite = Fernet(key)
    # Turn password into bytes object
    password_bytes = password.encode()
    return cipher_suite.encrypt(password_bytes)


def decrypt_password(encrypted_pw: bytes, cipher_suite: Fernet) -> str:
    # Get the password as bytes
    password_bytes = cipher_suite.decrypt(encrypted_pw)
    # Return the password as a string
    return password_bytes.decode()


def hash_password(pw: str) -> str:
    pwhash = bcrypt.hashpw(pw.encode('utf8'), bcrypt.gensalt())
    return pwhash.decode('utf8')


def check_password(pw: str, hashed_pw: str) -> bool:
    expected_hash = hashed_pw.encode('utf8')
    return bcrypt.checkpw(pw.encode('utf8'), expected_hash)


def get_auth_credentials(request: Request) -> Optional[Dict[str, str]]:
    """
    Gets username and password as a dictionary. Returns None if there is a
    problem.
    """
    authorization = AUTHORIZATION(request.environ)
    try:
        authmeth, auth = authorization.split(' ', 1)
    except ValueError:  # not enough values to unpack
        return None
    if authmeth.lower() == 'basic':  # ensure rquest is using basicauth
        try:
            # auth = auth.strip().decode('base64')
            auth = base64.b64decode(auth.strip())
        except binascii.Error:  # can't decode
            return None
        # Turn it back into a string
        auth = "".join(chr(x) for x in auth)
        try:
            username, password = auth.split(':', 1)
        except ValueError:  # not enough values to unpack
            return None
        return {'username': username, 'password': password}

    return None
