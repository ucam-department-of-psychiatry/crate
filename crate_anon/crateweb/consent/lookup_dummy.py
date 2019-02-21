#!/usr/bin/env python

"""
crate_anon/crateweb/consent/lookup_dummy.py

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

**Function to "look up" patient details from a fictional dummy database.**

"""

from typing import List

from django.core.exceptions import ObjectDoesNotExist

from crate_anon.crateweb.consent.models import (
    DummyPatientSourceInfo,
    PatientLookup,
    PatientLookupBase,
)


# =============================================================================
# Dummy clinical database (part of CRATE)
# =============================================================================

# noinspection PyUnusedLocal
def lookup_dummy_clinical(lookup: PatientLookup,
                          decisions: List[str],
                          secret_decisions: List[str]) -> None:
    """
    Looks up a patient from the fictional dummy database.

    Args:
        lookup: a :class:`crate_anon.crateweb.consent.models.PatientLookup`
        decisions: list of human-readable decisions; will be modified
        secret_decisions: list of human-readable decisions containing secret
            (identifiable) information; will be modified
    """
    try:
        dummylookup = DummyPatientSourceInfo.objects.get(
            nhs_number=lookup.nhs_number)
    except ObjectDoesNotExist:
        decisions.append("Patient not found in dummy lookup")
        return
    # noinspection PyProtectedMember
    fieldnames = [f.name for f in PatientLookupBase._meta.get_fields()]
    for fieldname in fieldnames:
        setattr(lookup, fieldname, getattr(dummylookup, fieldname))
    lookup.pt_found = True
    lookup.gp_found = True
    lookup.clinician_found = True
    decisions.append("Copying all information from dummy lookup")
