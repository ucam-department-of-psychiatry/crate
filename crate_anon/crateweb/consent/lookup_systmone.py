#!/usr/bin/env python

"""
crate_anon/crateweb/consent/lookup_systmone.py

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

**Functions to look up patient details from a TPP SystmOne Strategic Reporting
Extract (SRE) database, or at least its CPFT equivalent.**

"""
import datetime
from typing import Generator, List, Optional, Tuple

from cardinal_pythonlib.dbfunc import (
    dictfetchall,
    dictfetchone,
)
from cardinal_pythonlib.typing_helpers import (
    Pep249DatabaseCursorType as Cursor,
)
from django.db import connections

from crate_anon.crateweb.config.constants import ClinicalDatabaseType
from crate_anon.crateweb.consent.lookup_common import (
    get_team_details,
    pick_best_clinician,
    SignatoryTitles,
)
from crate_anon.crateweb.consent.models import (
    ClinicianInfoHolder,
    ConsentMode,
    PatientLookup,
)
from crate_anon.crateweb.consent.utils import to_date
from crate_anon.preprocess.systmone_ddgen import (
    cpft_s1_tablename,
    S1Table,
)


# =============================================================================
# Constants
# =============================================================================

_GENDER_S1_TO_CRATE = {
    "F": PatientLookup.FEMALE,
    "I": PatientLookup.INTERSEX,
    "M": PatientLookup.MALE,
    "U": PatientLookup.UNKNOWNSEX,
}


# =============================================================================
# CPFT staff details
# =============================================================================


def _is_staff_title(x: str) -> bool:
    """
    Does this string look like a title?
    """
    x = x.strip().rstrip(".").upper()
    return x in ("DR", "MISS", "MR", "MRS", "MS", "PROF")


def _is_initial(x: str) -> bool:
    """
    Does this bit look like an initial?
    """
    x = x.strip().rstrip(".")
    return len(x) == 1


def _get_staff_title_forename_surname(_combined: str) -> Tuple[str, str, str]:
    """
    Parse forename/surname for staff, in simple fashion. Generally, these are
    either "Dr Alice Smith" or "Alice Smith".
    """
    parts = (_combined or "").split()
    title = ""
    if len(parts) > 1 and _is_staff_title(parts[0]):
        title = parts[0]
        parts = parts[1:]
    fname = "".join(parts[:1])
    parts = parts[1:]
    if len(parts) > 1 and _is_initial(parts[0]):
        # Skip initial
        parts = parts[1:]
    sname = " ".join(parts)
    return title, fname, sname


def _get_staff_details(
    cursor: Cursor,
    clinician_type: str,
    signatory_title: str,
    is_consultant: bool,
    name: str = None,
    profile_id: int = None,
    start_date: datetime.date = None,
    end_date: datetime.date = None,
) -> Optional[ClinicianInfoHolder]:
    """
    Look up details about a member of staff, as best we can.

    MAY RE-USE THE DATABASE CURSOR; the calling code needs to be happy about
    that. [Note that our `dictfetchall()` function fetches everything in one
    go, so that's OK -- the cursor is not going to be re-used later in a loop
    -- and dictfetchone() is used in this file's code on a one-off basis only.]

    Relevant database structure:

    - Some tables have IDProfile<something_e.g._StaffMember>, which is a
      foreign key to SRStaffMemberProfile.RowIdentifier). That seems the most
      prevalent. Find these in CPFT with e.g.:

      .. code-block:: sql

        SELECT * FROM information_schema.columns
        WHERE table_catalog = 'SystmOne' AND column_name LIKE '%IDProfile%';

    - Some have StaffName, which is inserted by CPFT, likely from
      SRStaffMember.StaffName.

    - A few (e.g. CPFT's S1_ReferralAllocationStaff) have IDStaffMember, not
      in the original. This is likely from SRStaffMemberProfile.IDStaffMember,
      itself a key to SRStaffMember.RowIdentifier. SRStaffMember contains
      names.

    - So, the original TPP SRE uses IDProfile*, and the others have been added
      by CPFT.

    - However, staff e-mail addresses aren't obviously present anywhere.

    - Also, as of 2023-10-25, the staff lookup tables are missing too.

    """
    # Look up from profile ID.
    if profile_id:
        assert cursor is not None  # temporary, removes unused var warning
        pass  # todo: When SystmOne staff data available, implement lookup
        # (a) fetch profile record from SRStaffMemberProfile
        # (b) fetch name from SRStaffMember

    # Poor version: name alone.
    if name:
        title, first_name, surname = _get_staff_title_forename_surname(name)
        return ClinicianInfoHolder(
            clinician_type=clinician_type,
            title=title,
            first_name=first_name,
            surname=surname,
            email="",  # PROBLEM!
            signatory_title=signatory_title,
            is_consultant=is_consultant,
            start_date=start_date,
            end_date=end_date,
        )

    # Failed
    return None


def _process_consultant(
    clinicians: List[ClinicianInfoHolder],
    cursor: Cursor,
    name: str = "",
    profile_id: int = None,
    start_date: datetime.date = None,
    end_date: datetime.date = None,
) -> None:
    """
    Look up details for a consultant and add them to "clinicians".
    """
    if profile_id is None:
        return
    consultant = _get_staff_details(
        cursor=cursor,
        clinician_type=ClinicianInfoHolder.CONSULTANT,
        signatory_title=SignatoryTitles.CONSULTANT,
        # ... not necessarily (though often) a psychiatrist; might be e.g. a
        # consultant geriatrician.
        is_consultant=True,
        name=name,
        profile_id=profile_id,
        start_date=start_date,
        end_date=end_date,
    )
    if not consultant:
        return
    clinicians.append(consultant)


# =============================================================================
# Look up patient IDs
# =============================================================================


def lookup_cpft_systmone(
    lookup: PatientLookup, decisions: List[str], secret_decisions: List[str]
) -> None:
    """
    Look up patient details from a TPP SystmOne Strategic Reporting Extract
    (SRE) database.

    Args:
        lookup: a :class:`crate_anon.crateweb.consent.models.PatientLookup`
        decisions: list of human-readable decisions; will be modified
        secret_decisions: list of human-readable decisions containing secret
            (identifiable) information; will be modified
    """
    cursor = connections[ClinicalDatabaseType.CPFT_SYSTMONE].cursor()

    # -------------------------------------------------------------------------
    # 1. Name, DOB, DOD, gender, e-mail address
    # -------------------------------------------------------------------------
    patient_tab = cpft_s1_tablename(S1Table.PATIENT)
    cursor.execute(
        f"""
            SELECT
                IDPatient,  -- BIGINT; internal S1 reference number
                Title,
                FirstName,
                GivenName2,
                Surname,
                DOB,  -- DATETIME
                DateDeath,  -- DATETIME
                DeathIndicator,  -- INT
                Gender,  -- CHAR(1)
                EmailAddress  -- VARCHAR
                -- Note also: TestPatient, BOOLEAN
            FROM {patient_tab}
            WHERE NHSNumber = %s  -- CHAR comparison; VARCHAR(10)
        """,
        [str(lookup.nhs_number)],
    )
    rows = dictfetchall(cursor)
    if not rows:
        decisions.append(f"NHS number not found in {patient_tab} table.")
        return
    if len(rows) > 1:
        decisions.append("Two patients found with that NHS number; aborting.")
        return
    row = rows[0]
    s1_patient_id = row["IDPatient"]
    secret_decisions.append(f"SystmOne patient ID: {s1_patient_id}")
    lookup.pt_found = True
    lookup.pt_local_id_description = "SystmOne patient ID"
    lookup.pt_local_id_number = s1_patient_id
    lookup.pt_title = row["Title"] or ""
    lookup.pt_first_name = row["FirstName"] or ""
    lookup.pt_last_name = row["Surname"] or ""
    lookup.pt_dob = to_date(row["DOB"])
    lookup.pt_dod = to_date(row["DateDeath"])
    lookup.pt_dead = bool(lookup.pt_dod or row["DeathIndicator"])
    lookup.pt_sex = _GENDER_S1_TO_CRATE.get(
        row["Gender"], PatientLookup.UNKNOWNSEX
    )
    lookup.pt_email = row["EmailAddress"] or ""

    # Deal with dodgy case
    lookup.pt_title = lookup.pt_title.title()
    lookup.pt_first_name = lookup.pt_first_name.title()
    lookup.pt_last_name = lookup.pt_last_name.title()

    # - There is also SRPatientContactDetails, but no e-mail address there;
    #   it's about phone numbers, I think.

    # -------------------------------------------------------------------------
    # 2. Address
    # -------------------------------------------------------------------------
    address_tab = cpft_s1_tablename(S1Table.ADDRESS_HISTORY)
    cursor.execute(
        f"""
            SELECT
                NameOfBuilding,
                NumberOfBuilding,  -- text
                NameOfRoad,
                NameOfLocality,
                NameOfTown,
                NameOfCounty,
                FullPostCode
            FROM {address_tab}
            WHERE
                IDPatient = %s
                AND DateTo IS NULL  -- still current
            ORDER BY
                DateEvent DESC  -- most recent first
        """,
        [s1_patient_id],
    )
    row = dictfetchone(cursor)
    if not row:
        decisions.append(f"No address found in {address_tab} table.")
    else:
        lookup.pt_address_1 = row["NameOfBuilding"] or ""
        lookup.pt_address_2 = " ".join(
            filter(
                None, [row["NumberOfBuilding"] or "", row["NameOfRoad"] or ""]
            )
        )
        lookup.pt_address_3 = row["NameOfLocality"] or ""
        lookup.pt_address_4 = row["NameOfTown"] or ""
        lookup.pt_address_5 = row["NameOfCounty"] or ""
        lookup.pt_address_6 = row["FullPostCode"] or ""

    # -------------------------------------------------------------------------
    # 3. GP
    # -------------------------------------------------------------------------
    # In the original SRE, this is SRGPPracticeHistory.
    #
    # _tmp = """
    #     SELECT *
    #     FROM information_schema.tables
    #     WHERE table_catalog = 'SystmOne'
    #     AND (
    #         table_name LIKE '%practi%'
    #         OR table_name LIKE '%gp%'
    #     )
    # """
    #
    # ... it's S1_PatientGPPractice.
    #
    # In the original, SRGPPracticeHistory.IDPractice is a textual foreign key
    # to SROrganisation.ID. However, in the CPFT copy, that's gone. Instead,
    # there is S1_PatientGPPractice.Practice_Name, but there are no "%org%"
    # tables. So we will get some, but limited, GP information.

    gp_tab = cpft_s1_tablename(S1Table.GP_PRACTICE_HISTORY)
    cursor.execute(
        f"""
            SELECT
                IDPractice,  -- FK to SROrganisation; text
                Practice_Name
            FROM {gp_tab}
            WHERE
                IDPatient = %s
                AND DateTo IS NULL  -- still current
            ORDER BY
                DateFrom DESC  -- most recent first (unlikely >1 current!)
        """,
        [s1_patient_id],
    )
    row = dictfetchone(cursor)
    if not row:
        decisions.append(f"No GP found in {gp_tab} table.")
    else:
        lookup.gp_found = True
        lookup.gp_address_1 = row["Practice_Name"] or ""

    # -------------------------------------------------------------------------
    # 4. CPFT clinician, active v. discharged
    # -------------------------------------------------------------------------
    # - PROBLEM: there appear to be no rows with staff e-mail addresses in the
    #   SRE -- nor in CPFT's copy.
    # - So this will be lame.
    # - We could in theory guess them (forename.surname@cpft.nhs.uk) but that
    #   is risky. However, team representatives will have proper e-mails
    #   recorded, in CRATE.

    clinicians = []  # type: List[ClinicianInfoHolder]

    # (a) Care coordinator?
    care_co_tab = cpft_s1_tablename(S1Table.RESPONSIBLE_PARTY)
    cursor.execute(
        f"""
            SELECT
                IDProfileResponsibleParty,  -- BIGINT NULL
                Staff,  -- firstname surname
                DateStart,
                DateEnd
            FROM {care_co_tab}
            WHERE
                IDPatient = %s
                AND Start_Date <= GETDATE()
        """,
        [s1_patient_id],
    )
    for row in dictfetchall(cursor):
        care_co = _get_staff_details(
            cursor=cursor,
            clinician_type=ClinicianInfoHolder.CARE_COORDINATOR,
            signatory_title=SignatoryTitles.CARE_COORDINATOR,
            is_consultant=False,  # We don't know. Assume not (for CTIMPs).
            name=row["StaffName"],
            profile_id=row["IDProfileResponsibleParty"],
            start_date=to_date(row["DateStart"]),
            end_date=to_date(row["DateEnd"]),
        )
        if care_co:
            clinicians.append(care_co)

    # (b) Active named consultant referral?
    # - S1_Diagnosis, from SRClinicalCode
    codes_tab = cpft_s1_tablename(S1Table.CLINICAL_CODE)
    cursor.execute(
        f"""
            SELECT
                IDProfileConsultant,  -- BIGINT NULL
                DateEpisodeStart,
                DateEpisodeEnd
            FROM {codes_tab}
            WHERE
                IDPatient = %s
        """,
        [s1_patient_id],
    )
    # ... NB also IDConsultantEvent, likely FK to
    # SRHospitalConsultantEvent.RowIdentifier (in CPFT,
    # S1_InpatientSpells_ConsultantEpisode), but we deal with that separately
    # below. There is no staff name field here.
    for row in dictfetchall(cursor):
        _process_consultant(
            clinicians=clinicians,
            cursor=cursor,
            profile_id=row["IDProfileConsultant"],
            start_date=to_date(row["DateEpisodeStart"]),
            end_date=to_date(row["DateEpisodeEnd"]),
        )
    # - S1_InpatientSpells_ConsultantEpisode
    inpatient_tab = cpft_s1_tablename(S1Table.HOSPITAL_CONSULTANT_EVENT)
    cursor.execute(
        f"""
            SELECT
                IDProfileConsultant,
                StaffName,  -- is of the consultant
                DateEpisodeStart,
                DateEpisodeEnd
            FROM {inpatient_tab}
            WHERE
                IDPatient = %s
        """,
        [s1_patient_id],
    )
    for row in dictfetchall(cursor):
        _process_consultant(
            clinicians=clinicians,
            cursor=cursor,
            name=row["StaffName"],
            profile_id=row["IDProfileConsultant"],
            start_date=to_date(row["DateEpisodeStart"]),
            end_date=to_date(row["DateEpisodeEnd"]),
        )

    # (c) Active other named staff referral?
    referral_staff_tab = cpft_s1_tablename(S1Table.REFERRAL_ALLOCATION)
    # - In SRReferralAllocation, there is StaffName (VARCHAR) but we want more
    #   detail.
    # - There is IDProfileStaffMember, in the original (FK to
    #   SRStaffMemberProfile.RowIdentifier). SRStaffMemberProfile doesn't
    #   contain names (but does contain e.g. roles, employment start/end
    #   dates).
    # - There is also IDStaffMember, not in the original
    # - Of 79566 rows in CPFT's S1_ReferralAllocation during testing,
    #   IDProfileStaffMember and IDStaffMember are always different!
    cursor.execute(
        f"""
            SELECT
                IDProfileStaffMember,
                StaffName,
                DateStart,
                DateEnd
            FROM {referral_staff_tab}
            WHERE
                IDPatient = %s
                AND DateStart <= GETDATE()
                AND DateDeleted IS NULL
        """,
        [s1_patient_id],
    )
    for row in dictfetchall(cursor):
        hcp = _get_staff_details(
            cursor=cursor,
            clinician_type=ClinicianInfoHolder.HCP,
            signatory_title=SignatoryTitles.CLINICIAN,
            is_consultant=False,  # We don't know. Assume not (for CTIMPs).
            name=row["StaffName"],
            profile_id=row["IDProfileStaffMember"],
            start_date=to_date(row["DateStart"]),
            end_date=to_date(row["DateEnd"]),
        )
        if hcp:
            clinicians.append(hcp)

    # (d) Active team referral?
    referral_team_tab = cpft_s1_tablename(S1Table.REFERRAL_ALLOCATION)
    cursor.execute(
        f"""
            SELECT
                TeamName,
                DateStart,
                DateEnd
            FROM {referral_team_tab}
            WHERE
                IDPatient = %s
                AND DateStart <= GETDATE()
                AND DateDeleted IS NULL
        """,
        [s1_patient_id],
    )
    for row in dictfetchall(cursor):
        team_info = get_team_details(
            team_name=row["TeamName"] or "",
            start_date=to_date(row["DateStart"]),
            end_date=to_date(row["DateEnd"]),
            decisions=decisions,
        )
        clinicians.append(team_info)
        # We append it even if we can't find a representative, because it still
        # carries information about whether the patient is discharged or not.

    # Now pick one:
    pick_best_clinician(lookup, clinicians, decisions)


# =============================================================================
# Look up choices about research consent
# =============================================================================


def get_latest_consent_mode_from_cpft_systmone(
    nhs_number: int,
    decisions: List[str],
) -> Optional[ConsentMode]:
    """
    Returns the latest CPFT consent mode for a patient, from a CPFT SystmOne
    database.

    Args:
        nhs_number: NHS number
        decisions: list of human-readable decisions; will be modified

    Returns:
        a :class:`crate_anon.crateweb.consent.models.ConsentMode`, or ``None``
    """
    # *** S1_ClinicalOutcome_ConsentResearch
    # *** S1_ClinicalOutcome_ConsentResearch_OptOutCheck
    # *** S1_ClinicalOutcome_ConsentResearch_EmailCheck
    raise NotImplementedError("todo: ***")


def gen_opt_out_pids_mpids_cpft_systmone() -> Generator[
    Tuple[str, str], None, None
]:
    """
    Generates PID/MPID pairs from all patients opting out, from a CPFT SystmOne
    database.

    Note: this is the CPFT Research Database opt-out, not the NHS National Data
    Opt-Out. The latter applies to NHS Act s251 work, and is in
    SRNDOptOutPreference [marked as "future" in the SRE details?] or, in CPFT's
    copy, S1_Patient.NationalDataOptOut.

    Yields:
        ``s1_patient_id, nhs_number`` for each patient opting out, in string
        format
    """
    # *** S1_ClinicalOutcome_ConsentResearch_OptOutCheck
    raise NotImplementedError("todo: ***")
