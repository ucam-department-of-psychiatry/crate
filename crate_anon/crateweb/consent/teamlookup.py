#!/usr/bin/env python

"""
crate_anon/crateweb/consent/teamlookup.py

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

**Function to get clinical teams from our clinical source database.**

Note that ``teamlookup*.py`` files are separate from patient lookup files to
avoid circular imports, because teams are cached very early on (including for
Django field choices).

"""

import logging
from typing import List

from cardinal_pythonlib.django.function_cache import django_cache_function
from django.conf import settings

from crate_anon.crateweb.config.constants import ClinicalDatabaseType
from crate_anon.crateweb.consent.teamlookup_dummy import get_dummy_teams
from crate_anon.crateweb.consent.teamlookup_rio import get_rio_teams_rcep_crate

log = logging.getLogger(__name__)


# =============================================================================
# Fetch clinical team names
# =============================================================================

@django_cache_function(timeout=None)
def get_teams() -> List[str]:
    """
    Return all clinical team names from our clinical source database (as
    determined by ``settings.CLINICAL_LOOKUP_DB``).
    """
    log.debug("Fetching/caching clinical teams")
    source_db = settings.CLINICAL_LOOKUP_DB
    if settings.CLINICAL_LOOKUP_DB in (
            ClinicalDatabaseType.CPFT_RIO_RCEP,
            ClinicalDatabaseType.CPFT_RIO_CRATE_PREPROCESSED):
        return get_rio_teams_rcep_crate(source_db=source_db)
    elif settings.CLINICAL_LOOKUP_DB == 'dummy_clinical':
        return get_dummy_teams()
    else:
        return []
