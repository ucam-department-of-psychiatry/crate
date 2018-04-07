#!/usr/bin/env python
# crate_anon/crateweb/consent/teamlookup.py

"""
===============================================================================
    Copyright (C) 2015-2018 Rudolf Cardinal (rudolf@pobox.com).

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

Note that teamlookup* files are separate from patient lookup files to avoid
circular imports, because teams are cached very early on (including for Django
field choices).

"""

from typing import List

from django.conf import settings

from crate_anon.crateweb.config.constants import ClinicalDatabaseType
from crate_anon.crateweb.consent.teamlookup_dummy import get_dummy_teams
from crate_anon.crateweb.consent.teamlookup_rio import get_rio_teams_rcep_crate


# =============================================================================
# Fetch clinical team names
# =============================================================================

def get_teams() -> List[str]:
    source_db = settings.CLINICAL_LOOKUP_DB
    if settings.CLINICAL_LOOKUP_DB in (
            ClinicalDatabaseType.CPFT_RIO_RCEP,
            ClinicalDatabaseType.CPFT_RIO_CRATE_PREPROCESSED):
        return get_rio_teams_rcep_crate(source_db=source_db)
    elif settings.CLINICAL_LOOKUP_DB == 'dummy_clinical':
        return get_dummy_teams()
    else:
        return []
