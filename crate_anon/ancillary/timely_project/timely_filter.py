#!/usr/bin/env python

"""
crate_anon/ancillary/timely_project/timely_filter.py

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

Helper code for MRC TIMELY project (Moore, grant MR/T046430/1). Not of general
interest.

Class from which we inherit to implement specific data dictionary filters.

"""

# =============================================================================
# Imports
# =============================================================================

from typing import List

from crate_anon.ancillary.timely_project.dd_criteria import (
    FieldCriterion,
    TableCriterion,
)


# =============================================================================
# Constants
# =============================================================================

# Approvals are in stages.
N_STAGES = 6


# =============================================================================
# TimelyDDFilter
# =============================================================================


class TimelyDDFilter:
    """
    Base class for specific data dictionary filters to inherit from.
    """

    def __init__(self) -> None:
        # Tables to exclude at all times:
        self.exclude_tables = []  # type: List[TableCriterion]

        # Tables to include, by stage:
        self.staged_include_tables = []  # type: List[TableCriterion]

        # Fields to exclude, by stage:
        self.staged_exclude_fields = []  # type: List[FieldCriterion]
