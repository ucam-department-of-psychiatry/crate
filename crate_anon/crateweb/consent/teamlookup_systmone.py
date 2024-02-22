"""
crate_anon/crateweb/consent/teamlookup_systmone.py

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

**Function to get clinical team names from a TPP SystmOne Strategic Reporting
Extract (SRE) database.**

Note that ``teamlookup*.py`` files are separate from patient lookup files to
avoid circular imports, because teams are cached very early on (including for
Django field choices).

"""

from typing import List

from cardinal_pythonlib.dbfunc import fetchallfirstvalues
from django.db import connections

from crate_anon.crateweb.config.constants import ClinicalDatabaseType
from crate_anon.preprocess.systmone_ddgen import cpft_s1_tablename, S1Table


# =============================================================================
# Look up teams
# =============================================================================


def get_cpft_systmone_teams() -> List[str]:
    """
    Returns a list of clinical teams from a SystmOne Strategic Reporting
    Extract (SRE) database in CPFT's Data Warehosue format.
    """
    cursor = connections[ClinicalDatabaseType.CPFT_SYSTMONE].cursor()
    teams = cpft_s1_tablename(S1Table.TEAM)
    cursor.execute(
        f"""
        SELECT DISTINCT TeamName
        FROM {teams}
        WHERE TeamDeleted IS NULL
        ORDER BY TeamName
    """
    )
    return fetchallfirstvalues(cursor)
