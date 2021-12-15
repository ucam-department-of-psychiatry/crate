#!/usr/bin/env python

"""
crate_anon/ancillary/timely_project/dd_criteria.py

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

Helper code for MRC TIMELY project (Moore, grant MR/T046430/1). Not of general
interest.

Helpers for data dictionary filtering.

"""

# =============================================================================
# Imports
# =============================================================================

import re
from typing import List, Optional, Tuple


# =============================================================================
# Constants
# =============================================================================

# Arbitrary symbol that we'll use for "regex matches":
MATCHES = "≛"


# =============================================================================
# Deciding about rows
# =============================================================================

class TableCriterion:
    """
    Stores a regular expression so we can reuse it compiled for speed and view
    it and its associated stage.

    Note that "matching" uses ``compiled_regex.match()`` via a case-insensitive
    comparison. That matches at the start of strings. (Compare ``search()``,
    which matches anywhere.) So:

    - a leading ``^`` is implicit;
    - prefix with ``.*`` to allow matching in the middle of strings;
    - suffix with ``$`` to match the entire string only (not just the start).
    """
    def __init__(self, stage: Optional[int], table_regex_str: str) -> None:
        self.stage = stage
        self.table_regex_str = table_regex_str
        self.table_regex_compiled = re.compile(table_regex_str,
                                               flags=re.IGNORECASE)

    def table_match(self, tablename: str) -> bool:
        """
        Does ``tablename`` match our stored pattern?
        """
        return bool(self.table_regex_compiled.match(tablename))

    def description(self) -> str:
        return f"table {MATCHES} {self.table_regex_str}"


class FieldCriterion(TableCriterion):
    """
    As for :class:`TableCriterion`, but for both a table and a field (column)
    name.
    """
    def __init__(self, field_regex_str: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.field_regex_str = field_regex_str
        self.field_regex_compiled = re.compile(field_regex_str,
                                               flags=re.IGNORECASE)

    def table_field_match(self, tablename: str, fieldname: str) -> bool:
        """
        Do both the table and field names match?
        """
        return bool(
            self.table_regex_compiled.match(tablename)
            and self.field_regex_compiled.match(fieldname)
        )

    def description(self) -> str:
        return (
            f"table {MATCHES} {self.table_regex_str}, "
            f"field {MATCHES} {self.field_regex_str}"
        )


def add_table_criteria(criteria: List[TableCriterion],
                       stage: Optional[int],
                       regex_strings: List[str]) -> None:
    """
    Appends to ``criteria``.
    """
    for rs in regex_strings:
        criteria.append(TableCriterion(stage=stage, table_regex_str=rs))


def add_field_criteria(criteria: List[TableCriterion],
                       stage: Optional[int],
                       regex_tuples: List[Tuple[str, str]]) -> None:
    """
    Appends to ``criteria``.
    """
    for tablename, fieldname in regex_tuples:
        criteria.append(FieldCriterion(stage=stage,
                                       table_regex_str=tablename,
                                       field_regex_str=fieldname))
