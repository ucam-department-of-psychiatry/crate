#!/usr/bin/env python

"""
crate_anon/nlp_manager/test_all_regex.py

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

**Test all simple regexes and regex-based NLP parsers.**

"""

import argparse

from crate_anon.nlp_manager import (
    all_processors,
    regex_parser,
    regex_units,
)


def test_all_regex_nlp(verbose: bool = False) -> None:
    """
    Test all NLP-related regular expressions.
    """
    regex_parser.test_all(verbose=verbose)  # basic regexes
    regex_units.test_all(verbose=verbose)
    all_processors.test_all_processors(verbose=verbose)
    # ... tests all parser classes


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', '-v', action="store_true", help="Verbose")
    args = parser.parse_args()
    test_all_regex_nlp(verbose=args.verbose)
