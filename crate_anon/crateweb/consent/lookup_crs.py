#!/usr/bin/env python

"""
crate_anon/crateweb/consent/lookup_crs.py

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

**Function to look up patient details from CPFT's now-defunct
CRS (Care Records System) database.**

"""

from typing import List

from cardinal_pythonlib.dbfunc import dictfetchall, dictfetchone
from django.db import connections

from crate_anon.crateweb.consent.models import PatientLookup
from crate_anon.crateweb.consent.utils import make_cpft_email_address


# =============================================================================
# CPFT Care Records System (CRS)
# =============================================================================

def lookup_cpft_crs(lookup: PatientLookup,
                    decisions: List[str],
                    secret_decisions: List[str]) -> None:
    """
    Looks up patient details from the (defunct) CPFT CRS database.

    Args:
        lookup: a :class:`crate_anon.crateweb.consent.models.PatientLookup`
        decisions: list of human-readable decisions; will be modified
        secret_decisions: list of human-readable decisions containing secret
            (identifiable) information; will be modified
    """
    cursor = connections[lookup.source_db].cursor()
    # -------------------------------------------------------------------------
    # CRS 1. Fetch basic details
    # -------------------------------------------------------------------------
    # Incoming nhs_number will be a number. However, the database has a VARCHAR
    # field (nhs_identifier) that may include spaces. So we compare a
    # whitespace-stripped field to our value converted to a VARCHAR:
    #       WHERE REPLACE(nhs_identifier, ' ', '') = CAST(%s AS VARCHAR)
    # ... or the other way round:
    #       WHERE CAST(nhs_identifier AS BIGINT) = %s
    cursor.execute(
        """
            SELECT
                patient_id, -- M number (PK)
                -- nhs_identifier,
                title,
                forename,
                surname,
                gender,
                -- ethnicity,
                -- marital_status,
                -- religion,
                dttm_of_birth,
                dttm_of_death
            FROM mpi
            WHERE CAST(nhs_identifier AS BIGINT) = %s
        """,
        [lookup.nhs_number]
    )
    rows = dictfetchall(cursor)
    if not rows:
        decisions.append("NHS number not found in mpi table.")
        return
    if len(rows) > 1:
        decisions.append("Two patients found with that NHS number; aborting.")
        return
    row = rows[0]
    crs_patient_id = row['patient_id']
    lookup.pt_local_id_description = "CPFT M number"
    lookup.pt_local_id_number = crs_patient_id
    secret_decisions.append(f"CPFT M number: {crs_patient_id}.")
    lookup.pt_found = True
    lookup.pt_title = row['title'] or ''
    lookup.pt_first_name = row['forename'] or ''
    lookup.pt_last_name = row['surname'] or ''
    lookup.pt_sex = row['gender'] or ''
    lookup.pt_dob = row['dttm_of_birth']
    lookup.pt_dod = row['dttm_of_death']
    lookup.pt_dead = bool(lookup.pt_dod)
    # Deal with dodgy case
    lookup.pt_title = lookup.pt_title.title()
    lookup.pt_first_name = lookup.pt_first_name.title()
    lookup.pt_last_name = lookup.pt_last_name.title()
    # -------------------------------------------------------------------------
    # CRS 2. Address
    # -------------------------------------------------------------------------
    cursor.execute(
        """
            SELECT
                -- document_id, -- PK
                address1,
                address2,
                address3,
                address4,
                postcode,
                email
                -- startdate
                -- enddate
                -- patient_id

            FROM Address
            WHERE
                patient_id = %s
                AND enddate IS NULL
        """,
        [crs_patient_id]
    )
    row = dictfetchone(cursor)
    if not row:
        decisions.append("No address found in Address table.")
    else:
        lookup.pt_address_1 = row['address1'] or ''
        lookup.pt_address_2 = row['address2'] or ''
        lookup.pt_address_3 = row['address3'] or ''
        lookup.pt_address_4 = row['address4'] or ''
        lookup.pt_address_6 = row['postcode'] or ''
        lookup.pt_email = row['email'] or ''
    # -------------------------------------------------------------------------
    # CRS 3. GP
    # -------------------------------------------------------------------------
    cursor.execute(
        """
            SELECT
                -- sourcesystempk,  # PK
                -- patient_id,  # FK
                -- national_gp_id,
                gpname,
                -- national_practice_id,
                practicename,
                address1,
                address2,
                address3,
                address4,
                address5,
                postcode,
                telno
                -- startdate,
                -- enddate,
            FROM PracticeGP
            WHERE
                patient_id = %s
                AND enddate IS NULL
        """,
        [crs_patient_id]
    )
    row = dictfetchone(cursor)
    if not row:
        decisions.append("No GP found in PracticeGP table.")
    else:
        lookup.gp_found = True
        lookup.set_gp_name_components(row['gpname'] or '',
                                      decisions, secret_decisions)
        lookup.gp_address_1 = row['practicename'] or ''
        lookup.gp_address_2 = row['address1'] or ''
        lookup.gp_address_3 = row['address2'] or ''
        lookup.gp_address_4 = row['address3'] or ''
        lookup.gp_address_5 = ", ".join([row['address4'] or '',
                                         row['address5'] or ''])
        lookup.gp_address_6 = row['postcode']
        lookup.gp_telephone = row['telno']
    # -------------------------------------------------------------------------
    # CRS 4. Clinician
    # -------------------------------------------------------------------------
    cursor.execute(
        """
            SELECT
                -- patient_id,  # PK
                -- trustarea,
                consultanttitle,
                consultantfirstname,
                consultantlastname,
                carecoordinatortitle,
                carecoordinatorfirstname,
                carecoordinatorlastname,
                carecoordinatoraddress1,
                carecoordinatoraddress2,
                carecoordinatoraddress3,
                carecoordinatortown,
                carecoordinatorcounty,
                carecoordinatorpostcode,
                carecoordinatoremailaddress,
                carecoordinatormobilenumber,
                carecoordinatorlandlinenumber
            FROM CDLPatient
            WHERE
                patient_id = %s
        """,
        [crs_patient_id]
    )
    row = dictfetchone(cursor)
    if not row:
        decisions.append("No clinician info found in CDLPatient table.")
    else:
        lookup.clinician_address_1 = row['carecoordinatoraddress1'] or ''
        lookup.clinician_address_2 = row['carecoordinatoraddress2'] or ''
        lookup.clinician_address_3 = row['carecoordinatoraddress3'] or ''
        lookup.clinician_address_4 = row['carecoordinatortown'] or ''
        lookup.clinician_address_5 = row['carecoordinatorcounty'] or ''
        lookup.clinician_address_6 = row['carecoordinatorpostcode'] or ''
        lookup.clinician_telephone = " / ".join([
            row['carecoordinatorlandlinenumber'] or '',
            row['carecoordinatormobilenumber'] or ''
        ])
        careco_email = (
            row['carecoordinatoremailaddress'] or
            make_cpft_email_address(row['carecoordinatorfirstname'],
                                    row['carecoordinatorlastname'])
        )
        cons_email = make_cpft_email_address(row['consultantfirstname'],
                                             row['consultantlastname'])
        if careco_email:
            # Use care coordinator information
            lookup.clinician_found = True
            lookup.clinician_title = row['carecoordinatortitle'] or ''
            lookup.clinician_first_name = row['carecoordinatorfirstname'] or ''
            lookup.clinician_last_name = row['carecoordinatorlastname'] or ''
            lookup.clinician_email = careco_email
            lookup.clinician_signatory_title = "Care coordinator"
            decisions.append("Clinician found: care coordinator (CDL).")
        elif cons_email:
            # Use consultant information
            lookup.clinician_found = True
            lookup.clinician_title = row['consultanttitle'] or ''
            lookup.clinician_first_name = row['consultantfirstname'] or ''
            lookup.clinician_last_name = row['consultantlastname'] or ''
            lookup.clinician_email = cons_email
            lookup.clinician_signatory_title = "Consultant psychiatrist"
            lookup.clinician_is_consultant = True
            decisions.append("Clinician found: consultant psychiatrist (CDL).")
        else:
            # Don't know
            decisions.append(
                "No/insufficient clinician information found (CDL).")
