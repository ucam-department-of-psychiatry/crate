#!/usr/bin/env python

"""
bug_reports/check_pycharm_generator_hint.py

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

**Test PyCharm type hint checking for generators.**

"""

# See https://youtrack.jetbrains.com/issue/PY-20709
# - reported as fixed in version 2016.3.1, build 163.10230
# - partially fixed in version 2016.3.2, build #PY-163.10154.54 (28 Dec 2016)
#   ... so presumably still to be released, and "Fix versions" doesn't mean
#   "version in which it was fixed".
# - Certainly fixed by PyCharm 2018.2

from typing import Generator


def generate_int() -> Generator[int, None, None]:
    for x in (1, 2, 3, 4, 5):
        yield x


def use_int(x: int) -> None:
    print(f"x is {x}")


for value in generate_int():
    use_int(value)
