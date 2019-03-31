#!/usr/bin/env python

"""
crate_anon/common/formatting.py

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

**Ancillary formatting functions.**

"""

from typing import List, Tuple
from operator import itemgetter


# =============================================================================
# Ancillary functions
# =============================================================================

def print_record_counts(counts: List[Tuple[str, int]]) -> None:
    """
    Prints (to stdout) record counts for tables, firstly in alphabetical
    order of table name, then in numerical order of record count.

    Args:
        counts: list of ``table_name, n_record`` tuples
    """
    alphabetical = sorted(counts, key=itemgetter(0))
    numerical = sorted(counts, key=itemgetter(1))
    print("\n-- ALPHABETICALLY\n")
    for t, n in alphabetical:
        print(f"{t}: {n} records")
    print("\n-- NUMERICALLY\n")
    for t, n in numerical:
        print(f"{n} records in {t}")
    print()
