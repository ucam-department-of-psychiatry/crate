#!/usr/bin/env python

"""
crate_anon/crateweb/consent/teamlookup_dummy.py

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

**Function to get made-up clinical teams from a dummay database.**

Note that ``teamlookup*.py`` files are separate from patient lookup files to
avoid circular imports, because teams are cached very early on (including for
Django field choices).

"""

from typing import List


# =============================================================================
# Dummy clinical database (part of CRATE)
# =============================================================================

def get_dummy_teams() -> List[str]:
    """
    Returns a fictional list of clinical teams.
    """
    return ["dummy_team_one", "dummy_team_two", "dummy_team_three"]
