#!/usr/bin/env python
# crate_anon/crateweb/consent/lookup.py

"""
..

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

..
"""

import logging
from typing import Generator, List, Optional, Tuple, Union

from cardinal_pythonlib.logs import BraceStyleAdapter
from django.conf import settings

from crate_anon.crateweb.config.constants import ClinicalDatabaseType
from crate_anon.crateweb.consent.lookup_crs import (
    lookup_cpft_crs,
)
from crate_anon.crateweb.consent.lookup_dummy import (
    lookup_dummy_clinical,
)
from crate_anon.crateweb.consent.lookup_rio import (
    gen_opt_out_pids_mpids_rio_cpft_datamart,
    gen_opt_out_pids_mpids_rio_raw,
    get_latest_consent_mode_from_rio_cpft_datamart,
    get_latest_consent_mode_from_rio_raw,
    lookup_cpft_rio_crate_preprocessed,
    lookup_cpft_rio_rcep,
)
from crate_anon.crateweb.consent.models import ConsentMode, PatientLookup

log = BraceStyleAdapter(logging.getLogger(__name__))


# =============================================================================
# Look up patient ID
# =============================================================================

def lookup_patient(nhs_number: int,
                   source_db: str = None,
                   save: bool = True,
                   existing_ok: bool = False) -> PatientLookup:
    source_db = source_db or settings.CLINICAL_LOOKUP_DB
    if existing_ok:
        try:
            lookup = PatientLookup.objects.filter(nhs_number=nhs_number)\
                                          .latest('lookup_at')
            if lookup:
                return lookup
        except PatientLookup.DoesNotExist:
            # No existing lookup, so proceed to do it properly (below).
            pass
    lookup = PatientLookup(nhs_number=nhs_number,
                           source_db=source_db)
    # ... this object will be modified by the subsequent calls
    decisions = []
    secret_decisions = []
    if source_db == ClinicalDatabaseType.DUMMY_CLINICAL:
        lookup_dummy_clinical(lookup, decisions, secret_decisions)
    elif source_db == ClinicalDatabaseType.CPFT_PCMIS:
        raise AssertionError("Don't know how to look up ID from PCMIS yet")
        # lookup_cpft_iapt(lookup, decisions, secret_decisions)
    elif source_db == ClinicalDatabaseType.CPFT_CRS:
        lookup_cpft_crs(lookup, decisions, secret_decisions)
    elif source_db == ClinicalDatabaseType.CPFT_RIO_RCEP:
        lookup_cpft_rio_rcep(lookup, decisions, secret_decisions)
    elif source_db == ClinicalDatabaseType.CPFT_RIO_CRATE_PREPROCESSED:
        lookup_cpft_rio_crate_preprocessed(lookup, decisions, secret_decisions)
    elif source_db == ClinicalDatabaseType.CPFT_RIO_DATAMART:
        raise AssertionError("Not enough information in RiO Data Warehouse "
                             "copy yet to look up patient ID")
    else:
        raise ValueError("Bad source_db for ID lookup: {}".format(source_db))
    lookup.decisions = " ".join(decisions)
    lookup.secret_decisions = " ".join(secret_decisions)
    if save:
        lookup.save()
    return lookup


# =============================================================================
# Look up research consent choices
# =============================================================================

def lookup_consent(nhs_number: int,
                   decisions: List[str],
                   source_db: str = None) -> Optional[ConsentMode]:
    """
    Returns the latest ConsentMode for this patient from the primary clinical
    source, or None. Writes to decisions.
    """
    source_db = source_db or settings.CLINICAL_LOOKUP_CONSENT_DB
    if source_db == ClinicalDatabaseType.CPFT_RIO_DATAMART:
        return get_latest_consent_mode_from_rio_cpft_datamart(
            nhs_number=nhs_number,
            source_db=source_db,
            decisions=decisions
        )
    elif source_db in [ClinicalDatabaseType.CPFT_RIO_RAW,
                       ClinicalDatabaseType.CPFT_RIO_CRATE_PREPROCESSED]:
        return get_latest_consent_mode_from_rio_raw(
            nhs_number=nhs_number,
            source_db=source_db,
            decisions=decisions
        )
    else:
        # Don't know how to look up consent modes from other sources
        errmsg = ("Don't know how to look up consent modes "
                  "from {}".format(source_db))
        decisions.append(errmsg)
        log.warning(errmsg)
        return None


def gen_opt_out_pids_mpids(source_db: str) -> Generator[
        Tuple[Union[int, str], Union[int, str]],
        None, None]:
    """
    Generates (pid, mpid) tuples.
    """
    if source_db == ClinicalDatabaseType.CPFT_RIO_DATAMART:
        generator = gen_opt_out_pids_mpids_rio_cpft_datamart(source_db)
    elif source_db in [ClinicalDatabaseType.CPFT_RIO_RAW,
                       ClinicalDatabaseType.CPFT_RIO_CRATE_PREPROCESSED]:
        generator = gen_opt_out_pids_mpids_rio_raw(source_db)
    else:
        # Don't know how to look up consent modes from other sources
        log.error("Don't know how to look up opt-outs "
                  "from {}".format(source_db))
        return
    for pid, mpid in generator:
        yield pid, mpid
