#!/usr/bin/env python

r"""
crate_anon/nlp_webserver/tests/settings_tests.py

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

Unit testing.

"""

import os
import unittest

from sqlalchemy import engine_from_config

from crate_anon.common.constants import EnvVar
from crate_anon.nlp_webserver.constants import (
    NlpServerConfigKeys,
    SQLALCHEMY_COMMON_OPTIONS,
)


class NlprpDocgenSettingsTests(unittest.TestCase):
    @staticmethod
    def test_docgen_sqlite_settings():
        # Simulate doc building environment
        os.environ[EnvVar.GENERATING_CRATE_DOCS] = "True"
        from crate_anon.nlp_webserver.settings import (
            SETTINGS,
        )  # delayed import  # noqa

        _ = engine_from_config(
            SETTINGS,
            NlpServerConfigKeys.SQLALCHEMY_PREFIX,
            **SQLALCHEMY_COMMON_OPTIONS
        )
