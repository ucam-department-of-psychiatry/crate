#!/usr/bin/env python

"""
crate_anon/crateweb/consent/lookup.py

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

**Core functions to look up patient details from a clinical database.**

These functions then send the request to specialized functions according to
which type of clinical database is in use.

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
    """
    Looks up details of a patient.

    Args:
        nhs_number: NHS number
        source_db: the type of the source database; see
            :class:`crate_anon.crateweb.config.constants.ClinicalDatabaseType`
        save: save the lookup in our admin database?
        existing_ok: if we have a lookup saved in our admin database, use that?
            (If ``False``, fetch a new one from the primary source,
            regardless.)

    Returns:
        a :class:`crate_anon.crateweb.consent.models.PatientLookup`

    """
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
    decisions = []  # type: List[str]
    secret_decisions = []  # type: List[str]
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
        raise ValueError(f"Bad source_db for ID lookup: {source_db}")
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
    Returns the latest :class:`crate_anon.crateweb.consent.models.ConsentMode`
    for this patient from the primary clinical source, or ``None``. Writes to
    ``decisions`` as it goes.

    Args:
        nhs_number: NHS number
        decisions: list of human-readable decisions; will be modified
        source_db: the type of the source database; see
            :class:`crate_anon.crateweb.config.constants.ClinicalDatabaseType`

    Returns:
        a :class:`crate_anon.crateweb.consent.models.ConsentMode` or ``None``
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
        errmsg = f"Don't know how to look up consent modes from {source_db}"
        decisions.append(errmsg)
        log.warning(errmsg)
        return None


def gen_opt_out_pids_mpids(source_db: str) -> Generator[
        Tuple[Union[int, str], Union[int, str]],
        None, None]:
    """
    Generates PID/MPID information for all patients wishing to opt out of the
    anonymous database.

    Args:
        source_db: the type of the source database; see
            :class:`crate_anon.crateweb.config.constants.ClinicalDatabaseType`

    Yields:
        tuples: ``pid, mpid`` for each patient opting out

    """
    if source_db == ClinicalDatabaseType.CPFT_RIO_DATAMART:
        generator = gen_opt_out_pids_mpids_rio_cpft_datamart(source_db)
    elif source_db in [ClinicalDatabaseType.CPFT_RIO_RAW,
                       ClinicalDatabaseType.CPFT_RIO_CRATE_PREPROCESSED]:
        generator = gen_opt_out_pids_mpids_rio_raw(source_db)
    else:
        # Don't know how to look up consent modes from other sources
        log.error(f"Don't know how to look up opt-outs from {source_db}")
        return
    for pid, mpid in generator:
        yield pid, mpid
