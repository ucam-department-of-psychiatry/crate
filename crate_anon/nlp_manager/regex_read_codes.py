#!/usr/bin/env python

"""
crate_anon/nlp_manager/regex_read_codes.py

===============================================================================

    Copyright (C) 2015-2020 Rudolf Cardinal (rudolf@pobox.com).

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

**Regular expressions to detect some Read codes (CTV3).**

See https://en.wikipedia.org/wiki/Read_code.

"""

import logging
from typing import List
import unittest

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger

from crate_anon.anonymise.anonregex import escape_literal_string_for_regex

log = logging.getLogger(__name__)


# =============================================================================
# Represent a Read code
# =============================================================================

class ReadCode(object):
    """
    Represents information about the way a quantity is represented as a Read
    code.
    """
    def __init__(self,
                 read_code: str,
                 phrases: List[str] = None) -> None:
        """
        Args:
            read_code:
                The Read (CTV3) code, a string of length 5.
            phrases:
                The associated possible phrases.
        """
        assert isinstance(read_code, str)
        assert len(read_code) == 5
        self.read_code = read_code
        self.phrases = phrases or []  # type: List[str]

    def possible_strings(self) -> List[str]:
        """
        Ways in which this Read code may be represented in text.
        """
        rc = self.read_code
        strings = []  # type: List[str]
        for phrase in self.phrases:
            strings.append(f"{phrase} ({rc})")
        return strings

    def regex_strings(self) -> List[str]:
        """
        Regular expression strings representing this quantity.
        """
        return [
            escape_literal_string_for_regex(s)
            for s in self.possible_strings()
        ]


# =============================================================================
# Some known values used by our NLP parsers
# =============================================================================

class ReadCodes(object):
    BILIRUBIN = ReadCode(
        read_code="44E..",
        phrases=["Serum bilirubin level"]
    )


# =============================================================================
# Unit tests
# =============================================================================

class TestReadCodeRegexes(unittest.TestCase):
    def test_read_code_regexes(self) -> None:
        for name, rc in ReadCodes.__dict__.items():
            if name.startswith("_"):
                continue
            assert isinstance(rc, ReadCode)
            possible_strings = "\n".join(rc.possible_strings())
            regexes = "\n".join(rc.regex_strings())
            log.info(f"Name: {name!r}.\n"
                     f"- Possible strings:\n{possible_strings}\n"
                     f"- Regular expressions:\n{regexes}")


if __name__ == '__main__':
    main_only_quicksetup_rootlogger(level=logging.DEBUG)
    unittest.main()
