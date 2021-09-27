#!/usr/bin/env python

r"""
crate_anon/nlp_webserver/settings.py

===============================================================================

    Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).

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

Settings for CRATE's implementation of an NLPRP server.

"""

import os
from typing import Any, Dict, Optional

from pyramid.paster import get_appsettings
from pyramid.config import Configurator

from crate_anon.common.constants import EnvVar
from crate_anon.nlp_webserver.constants import (
    NLP_WEBSERVER_CONFIG_ENVVAR,
    NlpServerConfigKeys,
)

SETTINGS_PATH = os.getenv(NLP_WEBSERVER_CONFIG_ENVVAR)

if EnvVar.GENERATING_CRATE_DOCS in os.environ:
    # Prevent errors whilst building docs, using dummy settings.
    SETTINGS = {
        v: ""
        for k, v in NlpServerConfigKeys.__dict__.items()
        if not k.startswith("_")
    }
    SETTINGS[NlpServerConfigKeys.SQLALCHEMY_URL] = "sqlite://"
    SETTINGS[NlpServerConfigKeys.SQLALCHEMY_ECHO] = "false"
    SETTINGS[NlpServerConfigKeys.ENCRYPTION_KEY] = \
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa="
    CONFIG = None  # type: Optional[Configurator]
else:
    # Real settings.
    assert SETTINGS_PATH, (
        f"Missing environment variable {NLP_WEBSERVER_CONFIG_ENVVAR}")
    SETTINGS = get_appsettings(SETTINGS_PATH)  # type: Dict[str, Any]
    CONFIG = Configurator(settings=SETTINGS)
