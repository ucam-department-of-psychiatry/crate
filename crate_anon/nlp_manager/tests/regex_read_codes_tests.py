#!/usr/bin/env python

"""
crate_anon/nlp_manager/tests/regex_read_codes_tests.py

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

Unit tests.

"""

# =============================================================================
# Imports
# =============================================================================

import logging
import unittest

from crate_anon.nlp_manager.regex_read_codes import ReadCode, ReadCodes

log = logging.getLogger(__name__)


# =============================================================================
# Unit tests
# =============================================================================

class TestReadCodeRegexes(unittest.TestCase):
    def test_read_code_regexes(self) -> None:
        spacer = "    "
        for name, rc in ReadCodes.__dict__.items():
            if name.startswith("_"):
                continue
            assert isinstance(rc, ReadCode)
            phrases = "\n".join(
                f"{spacer}{x}" for x in rc.phrases
            )
            regexes = "\n".join(
                f"{spacer}{x}" for x in rc.component_regex_strings()
            )
            regex_str = rc.regex_str()
            log.info(f"Name: {name!r}.\n"
                     f"- Read code:\n{spacer}{rc.read_code}\n"
                     f"- Phrases:\n{phrases}\n"
                     f"- Regular expressions:\n{regexes}\n"
                     f"- Single regex string:\n{spacer}{regex_str}")
        log.warning("No testing performed; just printed.")
