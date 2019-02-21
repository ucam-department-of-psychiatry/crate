#!/usr/bin/env python

"""
crate_anon/anonymise/anonymise.py

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

**Simple functions for file I/O.**

"""

from typing import Generator


def gen_words_from_file(filename: str) -> Generator[str, None, None]:
    """
    Generate words from a file.

    Args:
        filename:

    Yields:
        each word
    """
    for line in open(filename):
        for word in line.split():
            yield word


def gen_integers_from_file(filename: str) -> Generator[int, None, None]:
    """
    Generates integers from a file.

    Args:
        filename: filename to parse

    Yields:
        all valid integers from words in the file
    """
    for word in gen_words_from_file(filename):
        if word.isdigit():
            pid = int(word)
            yield pid
