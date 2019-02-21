#!/usr/bin/env python

"""
crate_anon/crateweb/consent/teamlookup_rio.py

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

**Function to get clinical team names from RiO.**

Note that ``teamlookup*.py`` files are separate from patient lookup files to
avoid circular imports, because teams are cached very early on (including for
Django field choices).

"""

from typing import List

from cardinal_pythonlib.dbfunc import fetchallfirstvalues
from django.db import connections


# =============================================================================
# Look up teams
# =============================================================================

def get_rio_teams_rcep_crate(source_db: str) -> List[str]:
    """
    Returns a list of clinical teams from a RiO database that has been
    preprocessed through RCEP or CRATE.

    Args:
        source_db: the type of the source database; see
            :class:`crate_anon.crateweb.config.constants.ClinicalDatabaseType`
    """
    cursor = connections[source_db].cursor()
    cursor.execute("""
        SELECT DISTINCT Team_Description
        FROM Referral_Team_History
        ORDER BY Team_Description
    """)
    return fetchallfirstvalues(cursor)
