#!/usr/bin/env python

"""
crate_anon/crateweb/consent/lookup_rio.py

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

**Functions to look up patient details from various versions of a Servelec
RiO clinical database.**

"""

from operator import attrgetter
from typing import Generator, List, Optional, Tuple

from cardinal_pythonlib.dbfunc import (
    dictfetchall,
    dictfetchone,
    genrows,
)
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from django.db import connections

from crate_anon.crateweb.consent.models import (
    ClinicianInfoHolder,
    ConsentMode,
    PatientLookup,
    TeamRep,
)
from crate_anon.crateweb.consent.utils import latest_date, to_date
from crate_anon.preprocess.rio_constants import (
    CRATE_COL_RIO_NUMBER,
    RCEP_COL_PATIENT_ID,
)


# =============================================================================
# Look up patient IDs
# =============================================================================

# -----------------------------------------------------------------------------
# CPFT RiO (raw -> preprocessed by CRATE)
# -----------------------------------------------------------------------------

def lookup_cpft_rio_crate_preprocessed(lookup: PatientLookup,
                                       decisions: List[str],
                                       secret_decisions: List[str]) -> None:
    """
    Look up patient details from a CRATE-preprocessed RiO database.

    Args:
        lookup: a :class:`crate_anon.crateweb.consent.models.PatientLookup`
        decisions: list of human-readable decisions; will be modified
        secret_decisions: list of human-readable decisions containing secret
            (identifiable) information; will be modified

    Here, we use the version of RiO preprocessed by the CRATE preprocessor.
    This is almost identical to the RCEP version, saving us some thought and
    lots of repetition of complex JOIN code to deal with the raw RiO database.

    However, the CRATE preprocessor does this with views. We would need to
    index the underlying tables; however, the CRATE processor has also done
    this for us for the lookup tables, so we don't need so many.

    .. code-block:: sql

        USE my_database_name;

        CREATE INDEX _idx_cdd_nhs ON ClientIndex (NNN);  -- already in RiO source

        CREATE INDEX _idx_cnh_id ON ClientName (ClientID);  -- already in RiO source  # noqa
        CREATE INDEX _idx_cnh_eff ON ClientName (EffectiveDate);  -- ignored
        CREATE INDEX _idx_cnh_end ON ClientName (EndDate);  -- ignored

        CREATE INDEX _idx_cah_id ON ClientAddress (ClientID);  -- already in RiO source as part of composite index  # noqa
        CREATE INDEX _idx_cah_from ON ClientAddress (FromDate);  -- ignored
        CREATE INDEX _idx_cah_to ON ClientAddress (ToDate);  -- ignored

        CREATE INDEX _idx_cch_id ON ClientTelecom (ClientID);  -- already in RiO source as part of composite index  # noqa

        CREATE INDEX _idx_cgh_id ON ClientHealthCareProvider (ClientID);  -- already in RiO source  # noqa
        CREATE INDEX _idx_cgh_from ON ClientHealthCareProvider (FromDate);  -- ignored  # noqa
        CREATE INDEX _idx_cgh_to ON ClientHealthCareProvider (ToDate);  -- ignored

        CREATE INDEX _idx_cc_id ON CPACareCoordinator (ClientID);  -- preprocessor adds this  # noqa
        CREATE INDEX _idx_cc_start ON CPACareCoordinator (StartDate);  -- ignored
        CREATE INDEX _idx_cc_end ON CPACareCoordinator (EndDate);  -- ignored

        CREATE INDEX _idx_ref_id ON AmsReferral (ClientID);  -- already in RiO source as part of composite index  # noqa
        CREATE INDEX _idx_ref_recv ON AmsReferral (ReferralReceivedDate);  -- ignored  # noqa
        CREATE INDEX _idx_ref_removal ON AmsReferral (RemovalDateTime);  -- ignored

        CREATE INDEX _idx_rsh_id ON AmsReferralAllocation (ClientID);  -- already in RiO source as part of composite index  # noqa
        CREATE INDEX _idx_rsh_start ON AmsReferralAllocation (StartDate);  -- ignored
        CREATE INDEX _idx_rsh_end ON AmsReferralAllocation (EndDate);  -- ignored

        CREATE INDEX _idx_rth_id ON AmsReferralTeam (ClientID);  -- already in RiO source as part of composite index  # noqa
        CREATE INDEX _idx_rth_start ON AmsReferralTeam (StartDate);  -- ignored
        CREATE INDEX _idx_rth_end ON AmsReferralTeam (EndDate);  -- ignored

    ... or alternative RiO number indexes on CRATE_COL_RIO_NUMBER field.

    Then, the only field name differences from RCEP are:

    .. code-block:: none

        Client_Name_History.End_Date  -- not End_Date_
    """
    lookup_cpft_rio_generic(lookup, decisions, secret_decisions,
                            as_crate_not_rcep=True)


# -----------------------------------------------------------------------------
# CPFT RiO as preprocessed by Servelec RCEP tool
# -----------------------------------------------------------------------------

def lookup_cpft_rio_rcep(lookup: PatientLookup,
                         decisions: List[str],
                         secret_decisions: List[str]) -> None:
    """
    Look up patient details from a RiO database that's been preprocessed
    through Servelec's RCEP (RiO CRIS Extraction Program) tool.

    Args:
        lookup: a :class:`crate_anon.crateweb.consent.models.PatientLookup`
        decisions: list of human-readable decisions; will be modified
        secret_decisions: list of human-readable decisions containing secret
            (identifiable) information; will be modified

    **RiO notes, 2015-05-19**

    ... ADDENDUM 2017-02-27: this is the RiO database as modified by Servelec's
    RiO CRIS Extraction Program (RCEP). See also lookup_cpft_rio_raw().

    For speed, RiO-RCEP needs these indexes:

    .. code-block:: sql

        USE my_database_name;

        CREATE INDEX _idx_cdd_nhs ON Client_Demographic_Details (NHS_Number);

        CREATE INDEX _idx_cnh_id ON Client_Name_History (Client_ID);
        CREATE INDEX _idx_cnh_eff ON Client_Name_History (Effective_Date);
        CREATE INDEX _idx_cnh_end ON Client_Name_History (End_Date_);

        CREATE INDEX _idx_cah_id ON Client_Address_History (Client_ID);
        CREATE INDEX _idx_cah_from ON Client_Address_History (Address_From_Date);
        CREATE INDEX _idx_cah_to ON Client_Address_History (Address_To_Date);

        CREATE INDEX _idx_cch_id ON Client_Communications_History (Client_ID);

        CREATE INDEX _idx_cgh_id ON Client_GP_History (Client_ID);
        CREATE INDEX _idx_cgh_from ON Client_GP_History (GP_From_Date);
        CREATE INDEX _idx_cgh_to ON Client_GP_History (GP_To_Date);

        CREATE INDEX _idx_cc_id ON CPA_CareCoordinator (Client_ID);
        CREATE INDEX _idx_cc_start ON CPA_CareCoordinator (Start_Date);
        CREATE INDEX _idx_cc_end ON CPA_CareCoordinator (End_Date);

        CREATE INDEX _idx_ref_id ON Main_Referral_Data (Client_ID);
        CREATE INDEX _idx_ref_recv ON Main_Referral_Data (Referral_Received_Date);
        CREATE INDEX _idx_ref_removal ON Main_Referral_Data (Removal_DateTime);

        CREATE INDEX _idx_rsh_id ON Referral_Staff_History (Client_ID);
        CREATE INDEX _idx_rsh_start ON Referral_Staff_History (Start_Date);
        CREATE INDEX _idx_rsh_end ON Referral_Staff_History (End_Date);

        CREATE INDEX _idx_rth_id ON Referral_Team_History (Client_ID);
        CREATE INDEX _idx_rth_start ON Referral_Team_History (Start_Date);
        CREATE INDEX _idx_rth_end ON Referral_Team_History (End_Date);

        -- CREATE INDEX _idx_rth_teamdesc ON Referral_Team_History (Team_Description);  # noqa
    """
    lookup_cpft_rio_generic(lookup, decisions, secret_decisions,
                            as_crate_not_rcep=False)


# -----------------------------------------------------------------------------
# CPFT RiO: function that copes with either the RCEP or the CRATE version,
# which are extremely similar.
# -----------------------------------------------------------------------------

def lookup_cpft_rio_generic(lookup: PatientLookup,
                            decisions: List[str],
                            secret_decisions: List[str],
                            as_crate_not_rcep: bool) -> None:
    """
    Look up patient details from a RiO database, either as a CRATE-processed
    or an RCEP-processed version. (They are very similar.)

    Args:
        lookup: a :class:`crate_anon.crateweb.consent.models.PatientLookup`
        decisions: list of human-readable decisions; will be modified
        secret_decisions: list of human-readable decisions containing secret
            (identifiable) information; will be modified
        as_crate_not_rcep: is it a CRATE-preprocessed, rather than an
            RCEP-preprocessed, database?

    Main:

    .. code-block:: none

      Client_Demographic_Details
          Client_ID -- PK; RiO number; integer in VARCHAR(15) field
          Date_of_Birth -- DATETIME
          Date_of_Death -- DATETIME; NULL if not dead
          Death_Flag -- INT; 0 for alive, 1 for dead
          Deleted_Flag -- INT; 0 normally; 1 for deleted
          NHS_Number -- CHAR(10)
          Gender_Code -- 'F', 'M', 'U', 'X'
          Gender_Description -- 'Male', 'Female', ...

    Then, linked to it:

    .. code-block:: none

      Client_Name_History
          Client_ID -- integer in VARCHAR(15)
          Effective_Date -- DATETIME
          End_Date_  -- DATETIME, typically NULL
                -- in the CRATE version, this is End_Date instead
          Name_Type_Code  -- '1' for 'usual name', '2' for 'Alias', '3'
              for 'Preferred name', '4' for 'Birth name', '5' for
              'Maiden name', '7' for 'Other', 'CM' for 'Client Merge';
              NVARCHAR(10)
          Name_Type_Description  -- e.g. 'Usual name', 'Alias'
          Deleted_Flag -- INT

          title
          Given_Name_1  -- through to Given_Name_5
          Family_Name
          suffix
          ...

      Client_Address_History
          Client_ID -- integer in VARCHAR(15)
          Address_Type_Code -- e.g. 'PRIMARY' but also 'CA', 'FCH'...
          Address_Type_Description
          Address_From_Date -- DATETIME
          Address_To_Date -- DATETIME; NULL for active ones

          Address_Line_1
          Address_Line_2
          Address_Line_3
          Address_Line_4
          Address_Line_5
          Post_Code
          ... -- no e-mail address field

      Client_GP_History
          Client_ID -- integer in VARCHAR(15)
          GP_From_Date -- DATETIME
          GP_To_Date -- DATETIME; NULL for active ones

          GP_Name -- e.g. 'Smith JT'
          GP_Practice_Address_Line1
          GP_Practice_Address_Line2
          GP_Practice_Address_Line3
          GP_Practice_Address_Line4
          GP_Practice_Address_Line5
          GP_Practice_Post_code
          ...

    CPFT clinician details/?discharged info appear to be here:

    .. code-block:: none

      CPA_CareCoordinator
          Client_ID -- integer in VARCHAR(15)
          Start_Date -- DATETIME
          End_Date -- DATETIME
          End_Reason_Code
          End_Reason_Description
          End_Reason_National_Code

          Care_Coordinator_User_title
          Care_Coordinator_User_first_name
          Care_Coordinator_User_surname
          Care_Coordinator_User_email
          Care_Coordinator_User_Consultant_Flag -- INT; 0 or 1 (or NULL?)

      Main_Referral_Data
          Client_ID -- integer in VARCHAR(15)
          Referral_Received_Date -- DATETIME
          Removal_DateTime -- DATETIME
          # Care_Spell_Start_Date
          # Care_Spell_End_Date -- never non-NULL in our data set
          # Discharge_HCP -- ??user closing the referral

          Referred_Consultant_User_title
          Referred_Consultant_User_first_name
          Referred_Consultant_User_surname
          Referred_Consultant_User_email
          Referred_Consultant_User_Consultant_Flag  -- 0, 1, NULL

      Referral_Staff_History
          Client_ID -- integer in VARCHAR(15)
          Start_Date -- DATETIME
          End_Date -- DATETIME
          Current_At_Discharge -- INT -- ? -- 1 or NULL

          HCP_User_title
          HCP_User_first_name
          HCP_User_surname
          HCP_User_email
          HCP_User_Consultant_Flag  -- 0, 1, NULL

      Referral_Team_History
              -- similar, but for teams; no individual info
          Client_ID -- integer in VARCHAR(15)
          Start_Date -- DATETIME
          End_Date -- DATETIME
          Current_At_Discharge -- INT -- ? -- 1 or NULL

          Team_Code -- NVARCHAR -- e.g. 'TCGMH712'
          Team_Description -- NVARCHAR -- e.g. 'George Mackenzie'
          Team_Classification_Group_Code -- NVARCHAR -- e.g. 'FS'
          Team_Classification_Group_Description -- NVARCHAR -- e.g.
                                                          'Forensic Service'

    Not obviously relevant:

    .. code-block:: none

      Client_CPA -- records CPA start/end, etc.
      Client_Professional_Contacts -- empty table!

    Added 2017-02-27:

    .. code-block:: none

      Client_Communications_History -- email/phone
          Client_ID -- integer in VARCHAR(15)
          Method_Code -- NVARCHAR(10); '1' for 'Telephone number', '3'
              for 'Email address', '4' for 'Minicom/textphone number'
          Method_Description
          Context_Code -- e.g. '1' for 'Communication address at home',
              other codes for 'Vacation home...', etc.
          Context_Description
          Contact_Details -- NVARCHAR(80)

    """
    cursor = connections[lookup.source_db].cursor()
    rio_number_field = (CRATE_COL_RIO_NUMBER if as_crate_not_rcep
                        else RCEP_COL_PATIENT_ID)

    # -------------------------------------------------------------------------
    # RiO/RCEP: 1. Get RiO PK
    # -------------------------------------------------------------------------
    cursor.execute(
        f"""
            SELECT
                {rio_number_field}, -- RiO number (PK)
                -- NHS_Number,
                Date_of_Birth,
                Date_of_Death,
                Death_Flag,
                -- Deleted_Flag,
                Gender_Code
                -- Gender_Description,
            FROM Client_Demographic_Details
            WHERE
                NHS_Number = %s -- CHAR comparison
                AND (Deleted_Flag IS NULL OR Deleted_Flag = 0)
        """,
        [str(lookup.nhs_number)]
    )
    # Can't use "NOT Deleted_Flag" with SQL Server; you get
    # "An expression of non-boolean type specified in a context where a
    # condition is expected, near 'Deleted_Flag'."
    # The field is of type INTEGER NULL, but SQL Server won't auto-cast it
    # to something boolean.
    rows = dictfetchall(cursor)
    if not rows:
        decisions.append(
            "NHS number not found in Client_Demographic_Details table.")
        return
    if len(rows) > 1:
        decisions.append("Two patients found with that NHS number; aborting.")
        return
    row = rows[0]
    rio_client_id = row[rio_number_field]
    lookup.pt_local_id_description = "CPFT RiO number"
    lookup.pt_local_id_number = rio_client_id
    secret_decisions.append(f"RiO number: {rio_client_id}.")
    lookup.pt_dob = to_date(row['Date_of_Birth'])
    lookup.pt_dod = to_date(row['Date_of_Death'])
    lookup.pt_dead = bool(lookup.pt_dod or row['Death_Flag'])
    lookup.pt_sex = "?" if row['Gender_Code'] == "U" else row['Gender_Code']

    # -------------------------------------------------------------------------
    # RiO/RCEP: 2. Name
    # -------------------------------------------------------------------------
    cursor.execute(
        f"""
            SELECT
                title,
                Given_Name_1,
                Family_Name
            FROM Client_Name_History
            WHERE
                {rio_number_field} = %s
                AND Effective_Date <= GETDATE()
                AND ({'End_Date' if as_crate_not_rcep else 'End_Date_'} IS NULL
                     OR {'End_Date' if as_crate_not_rcep else 'End_Date_'} > GETDATE())
                AND (Deleted_Flag IS NULL OR Deleted_Flag = 0)
            ORDER BY Name_Type_Code
        """,  # noqa
        [rio_client_id]
    )
    row = dictfetchone(cursor)
    if not row:
        decisions.append(
            "No name/address information found in Client_Name_History.")
        return
    lookup.pt_found = True
    lookup.pt_title = row['title'] or ''
    lookup.pt_first_name = row['Given_Name_1'] or ''
    lookup.pt_last_name = row['Family_Name'] or ''
    # Deal with dodgy case
    lookup.pt_title = lookup.pt_title.title()
    lookup.pt_first_name = lookup.pt_first_name.title()
    lookup.pt_last_name = lookup.pt_last_name.title()

    # -------------------------------------------------------------------------
    # RiO/RCEP: 3. Address
    # -------------------------------------------------------------------------
    cursor.execute(
        f"""
            SELECT
                Address_Line_1,
                Address_Line_2,
                Address_Line_3,
                Address_Line_4,
                Address_Line_5,
                Post_Code
            FROM Client_Address_History
            WHERE
                {rio_number_field} = %s
                AND Address_From_Date <= GETDATE()
                AND (Address_To_Date IS NULL
                     OR Address_To_Date > GETDATE())
            ORDER BY CASE WHEN Address_Type_Code = 'PRIMARY' THEN '1'
                          ELSE Address_Type_Code END ASC
        """,
        [rio_client_id]
    )
    row = dictfetchone(cursor)
    if not row:
        decisions.append("No address found in Client_Address_History table.")
    else:
        lookup.pt_address_1 = row['Address_Line_1'] or ''
        lookup.pt_address_2 = row['Address_Line_2'] or ''
        lookup.pt_address_3 = row['Address_Line_3'] or ''
        lookup.pt_address_4 = row['Address_Line_4'] or ''
        lookup.pt_address_5 = row['Address_Line_5'] or ''
        lookup.pt_address_6 = row['Post_Code'] or ''

    # -------------------------------------------------------------------------
    # RiO/RCEP: 3b. Patient's e-mail address
    # -------------------------------------------------------------------------
    cursor.execute(
        f"""
            SELECT
                Contact_Details  -- an e-mail address if Method_Code = 3
            FROM Client_Communications_History
            WHERE
                {rio_number_field} = %s
                AND Method_Code = 3  -- e-mail address
                AND Valid_From <= GETDATE()
                AND (Valid_To IS NULL
                     OR Valid_To > GETDATE())
            ORDER BY Context_Code ASC
                -- 1 = Communication address at home
                -- 2 = Primary home (after business hours)
                -- 3 = Vacation home (when person on holiday)
                -- 4 = Office address
                -- 6 = Emergency contact
                -- 8 = Mobile device
        """,
        [rio_client_id]
    )
    rows = dictfetchall(cursor)
    if rows:
        row = rows[0]
        lookup.pt_email = row['Contact_Details']

    # -------------------------------------------------------------------------
    # RiO/RCEP: 4. GP
    # -------------------------------------------------------------------------
    if as_crate_not_rcep:
        cursor.execute(
            f"""
                SELECT
                    GP_Title,
                    GP_Forename,
                    GP_Surname,
                    GP_Practice_Address_Line_1,
                    GP_Practice_Address_Line_2,
                    GP_Practice_Address_Line_3,
                    GP_Practice_Address_Line_4,
                    GP_Practice_Address_Line_5,
                    GP_Practice_Post_Code
                FROM Client_GP_History
                WHERE
                    {rio_number_field} = %s
                    AND GP_From_Date <= GETDATE()
                    AND (GP_To_Date IS NULL OR GP_To_Date > GETDATE())
            """,
            [rio_client_id]
        )
        row = dictfetchone(cursor)
        if not row:
            decisions.append("No GP found in Client_GP_History table.")
        else:
            lookup.gp_found = True
            lookup.gp_title = row['GP_Title'] or 'Dr'
            lookup.gp_first_name = row['GP_Forename'] or ''
            lookup.gp_last_name = row['GP_Surname'] or ''
            lookup.gp_address_1 = row['GP_Practice_Address_Line_1'] or ''
            lookup.gp_address_2 = row['GP_Practice_Address_Line_2'] or ''
            lookup.gp_address_3 = row['GP_Practice_Address_Line_3'] or ''
            lookup.gp_address_4 = row['GP_Practice_Address_Line_4'] or ''
            lookup.gp_address_5 = row['GP_Practice_Address_Line_5'] or ''
            lookup.gp_address_6 = row['GP_Practice_Post_Code']
    else:
        cursor.execute(
            f"""
                SELECT
                    GP_Name,
                    GP_Practice_Address_Line1,
                    GP_Practice_Address_Line2,
                    GP_Practice_Address_Line3,
                    GP_Practice_Address_Line4,
                    GP_Practice_Address_Line5,
                    GP_Practice_Post_code
                FROM Client_GP_History
                WHERE
                    {rio_number_field} = %s
                    AND GP_From_Date <= GETDATE()
                    AND (GP_To_Date IS NULL OR GP_To_Date > GETDATE())
            """,
            [rio_client_id]
        )
        row = dictfetchone(cursor)
        if not row:
            decisions.append("No GP found in Client_GP_History table.")
        else:
            lookup.gp_found = True
            lookup.set_gp_name_components(row['GP_Name'] or '',
                                          decisions, secret_decisions)
            lookup.gp_address_1 = row['GP_Practice_Address_Line1'] or ''
            lookup.gp_address_2 = row['GP_Practice_Address_Line2'] or ''
            lookup.gp_address_3 = row['GP_Practice_Address_Line3'] or ''
            lookup.gp_address_4 = row['GP_Practice_Address_Line4'] or ''
            lookup.gp_address_5 = row['GP_Practice_Address_Line5'] or ''
            lookup.gp_address_6 = row['GP_Practice_Post_code']

    # -------------------------------------------------------------------------
    # RiO/RCEP: 5. Clinician, active v. discharged
    # -------------------------------------------------------------------------
    # This bit is complicated! We do it last, so we can return upon success.
    clinicians = []  # type: List[ClinicianInfoHolder]
    #
    # (a) Care coordinator?
    #
    if as_crate_not_rcep:
        care_co_title_field = 'Care_Coordinator_Title'
        care_co_forename_field = 'Care_Coordinator_First_Name'
        care_co_surname_field = 'Care_Coordinator_Surname'
        care_co_email_field = 'Care_Coordinator_Email'
        care_co_consultant_flag_field = 'Care_Coordinator_Consultant_Flag'
        care_co_table = 'CPA_Care_Coordinator'
    else:
        care_co_title_field = 'Care_Coordinator_User_title'
        care_co_forename_field = 'Care_Coordinator_User_first_name'
        care_co_surname_field = 'Care_Coordinator_User_surname'
        care_co_email_field = 'Care_Coordinator_User_email'
        care_co_consultant_flag_field = 'Care_Coordinator_User_Consultant_Flag'
        care_co_table = 'CPA_CareCoordinator'
    cursor.execute(
        f"""
            SELECT
                {care_co_title_field},
                {care_co_forename_field},
                {care_co_surname_field},
                {care_co_email_field},
                {care_co_consultant_flag_field},
                Start_Date,
                End_Date
            FROM {care_co_table}
            WHERE
                {rio_number_field} = %s
                AND Start_Date <= GETDATE()
        """,
        [rio_client_id]
    )
    for row in dictfetchall(cursor):
        clinicians.append(ClinicianInfoHolder(
            clinician_type=ClinicianInfoHolder.CARE_COORDINATOR,
            title=row[care_co_title_field] or '',
            first_name=row[care_co_forename_field] or '',
            surname=row[care_co_surname_field] or '',
            email=row[care_co_email_field] or '',
            signatory_title="Care coordinator",
            is_consultant=bool(row[care_co_consultant_flag_field]),
            start_date=row['Start_Date'],
            end_date=row['End_Date'],
        ))
    #
    # (b) Active named consultant referral?
    #
    if as_crate_not_rcep:
        cons_title_field = 'Referred_Consultant_Title'
        cons_forename_field = 'Referred_Consultant_First_Name'
        cons_surname_field = 'Referred_Consultant_Surname'
        cons_email_field = 'Referred_Consultant_Email'
        cons_consultant_flag_field = 'Referred_Consultant_Consultant_Flag'
        referral_table = 'Referral'
    else:
        cons_title_field = 'Referred_Consultant_User_title'
        cons_forename_field = 'Referred_Consultant_User_first_name'
        cons_surname_field = 'Referred_Consultant_User_surname'
        cons_email_field = 'Referred_Consultant_User_email'
        cons_consultant_flag_field = 'Referred_Consultant_User_Consultant_Flag'
        referral_table = 'Main_Referral_Data'
    cursor.execute(
        f"""
            SELECT
                {cons_title_field},
                {cons_forename_field},
                {cons_surname_field},
                {cons_email_field},
                {cons_consultant_flag_field},
                Referral_Received_Date,
                Removal_DateTime
            FROM {referral_table}
            WHERE
                {rio_number_field} = %s
                AND Referral_Received_Date <= GETDATE()
        """,
        [rio_client_id]
    )
    for row in dictfetchall(cursor):
        clinicians.append(ClinicianInfoHolder(
            clinician_type=ClinicianInfoHolder.CONSULTANT,
            title=row[cons_title_field] or '',
            first_name=row[cons_forename_field] or '',
            surname=row[cons_surname_field] or '',
            email=row[cons_email_field] or '',
            signatory_title="Consultant psychiatrist",
            is_consultant=bool(row[cons_consultant_flag_field]),
            # ... would be odd if this were not true!
            start_date=row['Referral_Received_Date'],
            end_date=row['Removal_DateTime'],
        ))
    #
    # (c) Active other named staff referral?
    #
    if as_crate_not_rcep:
        hcp_title_field = 'HCP_Title'
        hcp_forename_field = 'HCP_First_Name'
        hcp_surname_field = 'HCP_Surname'
        hcp_email_field = 'HCP_Email'
        hcp_consultant_flag_field = 'HCP_Consultant_Flag'
    else:
        hcp_title_field = 'HCP_User_title'
        hcp_forename_field = 'HCP_User_first_name'
        hcp_surname_field = 'HCP_User_surname'
        hcp_email_field = 'HCP_User_email'
        hcp_consultant_flag_field = 'HCP_User_Consultant_Flag'
    cursor.execute(
        f"""
            SELECT
                {hcp_title_field},
                {hcp_forename_field},
                {hcp_surname_field},
                {hcp_email_field},
                {hcp_consultant_flag_field},
                Start_Date,
                End_Date
            FROM Referral_Staff_History
            WHERE
                {rio_number_field} = %s
                AND Start_Date <= GETDATE()
        """,
        [rio_client_id]
    )
    for row in dictfetchall(cursor):
        clinicians.append(ClinicianInfoHolder(
            clinician_type=ClinicianInfoHolder.HCP,
            title=row[hcp_title_field] or '',
            first_name=row[hcp_forename_field] or '',
            surname=row[hcp_surname_field] or '',
            email=row[hcp_email_field] or '',
            signatory_title="Clinician",
            is_consultant=bool(row[hcp_consultant_flag_field]),
            start_date=row['Start_Date'],
            end_date=row['End_Date'],
        ))
    #
    # (d) Active team referral?
    #
    cursor.execute(
        f"""
            SELECT
                Team_Description,
                Start_Date,
                End_Date
            FROM Referral_Team_History
            WHERE
                {rio_number_field} = %s
                AND Start_Date <= GETDATE()
        """,
        [rio_client_id]
    )
    for row in dictfetchall(cursor):
        team_info = ClinicianInfoHolder(
            clinician_type=ClinicianInfoHolder.TEAM,
            title='',
            first_name='',
            surname='',
            email='',
            signatory_title="Clinical team member",
            is_consultant=False,
            start_date=row['Start_Date'],
            end_date=row['End_Date'],
        )
        # We know a team - do we have a team representative?
        team_description = row['Team_Description']
        team_summary = "{status} team {desc}".format(
            status="active" if team_info.end_date is None else "previous",
            desc=repr(team_description),
        )
        try:
            teamrep = TeamRep.objects.get(team=team_description)
            decisions.append("Clinical team representative found.")
            profile = teamrep.user.profile
            team_info.title = profile.title
            team_info.first_name = teamrep.user.first_name
            team_info.surname = teamrep.user.last_name
            team_info.email = teamrep.user.email
            team_info.signatory_title = profile.signatory_title
            team_info.is_consultant = profile.is_consultant
        except ObjectDoesNotExist:
            decisions.append(
                f"No team representative found for {team_summary}.")
        except MultipleObjectsReturned:
            decisions.append(
                f"Confused: >1 team representative found for {team_summary}.")
        clinicians.append(team_info)
        # We append it even if we can't find a representative, because it still
        # carries information about whether the patient is discharged or not.

    # Re CLINICIAN ADDRESSES:
    # Candidate tables in RiO:
    # - OrgContactAddress +/- OrgContactAddressHistory
    # - OrgOrganisation
    # - GenPerson <-- THIS. From GenHCP: "This table contains about all HCPs
    #   registered in RiO. HCP’s personal details (name, address etc.) are
    #   stored in GenPerson.
    # - ??GenLocation; ??GenNHSLocation
    #
    # So, GenPerson is correct. However, in CPFT, when we
    #       SELECT * FROM GenPerson WHERE AddressLine2 IS NOT NULL
    # we get lots of things saying "Agency Staff", "leaves Trust 17/02/15",
    # "changed name from Smith", "Medical student", and so on.
    #
    # Therefore, our source is simply duff; people are using the fields for
    # a different purpose.
    # Therefore, the set_from_clinician_info_holder() function will default
    # to the RDBM's address.

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # OK.
    # Now we know all relevant recent clinicians, including (potentially) ones
    # from which the patient has been discharged, and ones that are active.
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    decisions.append(f"{len(clinicians)} total past/present "
                     f"clinician(s)/team(s) found: {clinicians!r}.")
    current_clinicians = [c for c in clinicians if c.current()]
    if current_clinicians:
        lookup.pt_discharged = False
        lookup.pt_discharge_date = None
        decisions.append("Patient not discharged.")
        contactable_curr_clin = [c for c in current_clinicians
                                 if c.contactable()]
        # Sorting by two keys: http://stackoverflow.com/questions/11206884
        # LOW priority: most recent clinician. (Goes first in sort.)
        # HIGH priority: preferred type of clinician. (Goes last in sort.)
        # Sort order is: most preferred first.
        contactable_curr_clin.sort(key=attrgetter('start_date'), reverse=True)
        contactable_curr_clin.sort(key=attrgetter('clinician_preference_order'))  # noqa
        decisions.append(f"{len(contactable_curr_clin)} contactable active "
                         f"clinician(s) found.")
        if contactable_curr_clin:
            chosen_clinician = contactable_curr_clin[0]
            lookup.set_from_clinician_info_holder(chosen_clinician)
            decisions.append(f"Found active clinician of type: "
                             f"{chosen_clinician.clinician_type}")
            return  # All done!
        # If we get here, the patient is not discharged, but we haven't found
        # a contactable active clinician.
        # We'll fall through and check older clinicians for contactability.
    else:
        end_dates = [c.end_date for c in clinicians]
        lookup.pt_discharged = True
        lookup.pt_discharge_date = latest_date(*end_dates)
        decisions.append("Patient discharged.")

    # We get here either if the patient is discharged, or they're current but
    # we can't contact a current clinician.
    contactable_old_clin = [c for c in clinicians if c.contactable()]
    # LOW priority: preferred type of clinician. (Goes first in sort.)
    # HIGH priority: most recent end date. (Goes last in sort.)
    # Sort order is: most preferred first.
    contactable_old_clin.sort(key=attrgetter('clinician_preference_order'))
    contactable_old_clin.sort(key=attrgetter('end_date'), reverse=True)
    decisions.append(f"{len(contactable_old_clin)} contactable previous "
                     f"clinician(s) found.")
    if contactable_old_clin:
        chosen_clinician = contactable_old_clin[0]
        lookup.set_from_clinician_info_holder(chosen_clinician)
        decisions.append(f"Found previous clinician of type: "
                         f"{chosen_clinician.clinician_type}")

    if not lookup.clinician_found:
        decisions.append("Failed to establish contactable clinician.")


# =============================================================================
# Look up choices about research consent
# =============================================================================

# Constant strings used in database:
ADULT_WITH_CAPACITY_TEXT = "16 or over, has capacity"
ADULT_WITH_CAPACITY_CODE = "a"
ADULT_LACKS_CAPACITY_TEXT = "16 or over, lacks capacity"
ADULT_LACKS_CAPACITY_CODE = "b"
CHILD_PARENT_TEXT = "Under 16, parent/guardian consent"
CHILD_PARENT_CODE = "c"
CHILD_GILLICK_TEXT = "Under 16, “Gillick competent”"
CHILD_GILLICK_CODE = "d"  # by inference; none live yet in raw20171128 DB
DECISION_METHOD_CODE_TO_TEXT = {
    ADULT_WITH_CAPACITY_CODE: ADULT_WITH_CAPACITY_TEXT,
    ADULT_LACKS_CAPACITY_CODE: ADULT_LACKS_CAPACITY_TEXT,
    CHILD_PARENT_CODE: CHILD_PARENT_TEXT,
    CHILD_GILLICK_CODE: CHILD_GILLICK_TEXT,
}
NOT_APPLICABLE_UPPER = "N/A"


def get_latest_consent_mode_from_rio_generic(
        nhs_number: int,
        source_db: str,
        decisions: List[str],
        raw_rio: bool = False,
        cpft_datamart: bool = False) -> Optional[ConsentMode]:
    """
    Returns the latest consent mode for a patient, from some style of RiO
    database.

    Args:
        nhs_number: NHS number
        source_db: the type of the source database; see
            :class:`crate_anon.crateweb.config.constants.ClinicalDatabaseType`
        decisions: list of human-readable decisions; will be modified
        raw_rio: is the source database a raw copy of RiO?
        cpft_datamart: is the source database the version from the CPFT
            data warehouse?

    Returns:
        a :class:`crate_anon.crateweb.consent.models.ConsentMode`, or ``None``

    Shared function as very similar for the various copies of RiO data.

    In raw RiO at CPFT, the traffic-light table is UserAssessConsentrd.
    This is processed regularly into the CPFT Data Warehouse, so that
    contains very fresh data and is a good choice.

    For CPFT's custom consent mode, built into RiO v6, the table copy in
    the Data Warehouse is:

    .. code-block:: sql

        SELECT
            [ClientID]  -- VARCHAR(15) NOT NULL; RiO number as text
            ,[AssessmentDate]  -- DATETIME
            ,[ReferralNumber]  -- NVARCHAR(20); a small integer as text
            ,[ResearchContact]  -- NVARCHAR(20); 'RED', 'YELLOW', 'GREEN'
            ,[OptOut]
                -- BIT; 1 for opt out; NULL (or potentially 0?) for not
                -- opted out
            ,[OptOutFromMedicalResearch_AfterDetailsRemoved]
                -- VARCHAR(1); 'Y' for opt out; 9 for not opted out
                -- identical information to OptOut; OptOut is the simpler
            ,[PersonActingonBehalf_of_Patient]
                -- NTEXT, e.g. 'Mr Smith' or NULL
            ,[PersonActingonBehalf_of_Patient_Relation]
                -- NTEXT, e.g. 'Husband' or NULL or 'N/A' or 'n/a'
            ,[Personactingonbehalf_address]
                -- NTEXT, e.g. an address or NULL or 'N/A' or 'n/a'
            ,[WhoMakesDecisionFor_Patient]
                -- NVARCHAR(40), e.g. one of:
                --  '16 or over, has capacity'
                --  '16 or over, lacks capacity'
                --  'Under 16, “Gillick competent”'
                    -- note left/right double quotes
                --  'Under 16, parent/guardian consent'
        FROM [CPFT_DATAMART].[dbo].[ConsentToResearch]
            -- NB this is on a different CPFT server; see databases.txt

    Note also: the CPFT_DATAMART database does not provide patient-
    identifiable information, except PatientOverview_RiO:

    .. code-block:: sql

        SELECT
            [NHSNumber]     -- VARCHAR(15); NHS number as text
            ,[ClientID]     -- VARCHAR(15) NOT NULL; RiO number as text
            ,[PatientName]  -- VARCHAR(202); e.g. 'Smith, John'
            ,[Surname]      -- VARCHAR(100); e.g. 'Smith'
            ,[DOB]          -- DATETIME; time part is zero
            ,[TeamStartDate]    -- DATETIME
            ,[TeamName]         -- NVARCHAR(50)
            ,[ReferralNumber]   -- INT NOT NULL; a small integer
            ,[LastAttendedApptDate_WithTeam]    -- DATE
            ,[FutureAppts_WithTeam]     -- DATE; just one despite the name
            ,[HCPs]
                -- NVARCHAR(MAX); semicolon-delimited list; e.g.
                -- '; Alice Smith'
                -- '; Alice Smith; Bob Jones'
                -- '; Unknown Consultant'
        FROM [CPFT_DATAMART].[dbo].[PatientOverviewRiO]

    In raw RiO at CPFT, the traffic-light table is UserAssessConsentrd.

    .. code-block:: sql

        SELECT
            [ClientID]  -- VARCHAR(15); RiO number as text
            ,[AssessmentDate]  -- DATETIME
            ,[system_ValidationData]  -- NTEXT; XML style
            ,[ResearchContact]  -- NVARCHAR(20); 'RED', 'YELLOW', 'GREEN', NULL
            ,[useemail]  -- BIT (1, 0, NULL)
            ,[optout]  -- BIT
            ,[capname]  -- NTEXT
            ,[capaddress]  -- NTEXT
            ,[caprelation]  -- NTEXT
            ,[capacity]  -- VARCHAR(20); e.g. 'a', 'b'
            ,[type12_NoteID]  -- INT NOT NULL; small integer
            ,[type12_OriginalNoteID]  -- INT; usually NULL
            ,[type12_DeletedDate]  -- DATETIME; NULL if not deleted
            ,[type12_UpdatedBy]  -- NVARCHAR(20); username
            ,[type12_UpdatedDate]  -- DATETIME
            ,[formref]  -- NVARCHAR(20); typically a small integer as text

            -- If it's been preprocessed, also these:
            ,[crate_pk]         -- in CRATE preprocessed version only; BIGINT
            ,[crate_rio_number] -- in CRATE preprocessed version only; BIGINT
        FROM [dbo].[UserAssessconsentrd]

    The NHS number table is:

    .. code-block:: sql

        SELECT
            [ClientID]  -- VARCHAR(15); RiO number as text
            ,[NNN]  -- CHAR(10); NHS number as text
            -- and lots more
        FROM [dbo].ClientIndex]

    """
    assert sum([raw_rio, cpft_datamart]) == 1, (
        "Specify exactly one database type to look up from"
    )
    if raw_rio:
        sql = """
            SELECT TOP 1  -- guaranteed to be running SQL Server
                ci.NNN AS nhs_number_text,
                ci.ClientID AS rio_number_text,
                cr.AssessmentDate AS decision_date,
                cr.ResearchContact AS traffic_light,
                    -- 'RED', 'YELLOW', 'GREEN', NULL
                cr.useemail AS use_email,
                cr.optout AS opt_out,  -- 1, 0 (possibly), NULL
                cr.capacity AS decision_method_code,
                cr.capname AS representative_name,
                cr.caprelation AS representative_relation
            FROM
                UserAssessconsentrd AS cr
            INNER JOIN
                ClientIndex AS ci
                ON cr.ClientID = ci.ClientID
            WHERE
                ci.NNN = %s  -- string comparison
            ORDER BY
                cr.AssessmentDate DESC
        """
    elif cpft_datamart:
        # Old, discarded 2018-06-28:
        _ = """
            SELECT TOP 1  -- guaranteed to be running SQL Server
                po.NHSNumber AS nhs_number_text,
                po.ClientID AS rio_number_text,
                cr.AssessmentDate AS decision_date,
                cr.ResearchContact AS traffic_light,
                    -- 'RED', 'YELLOW', 'GREEN', NULL
                0 AS use_email,  -- not in CPFT data warehouse copy
                cr.OptOut AS opt_out,  -- 1, 0 (possibly), NULL
                cr.WhoMakesDecisionFor_Patient AS decision_method,
                cr.PersonActingonBehalf_of_Patient AS representative_name,
                cr.PersonActingonBehalf_of_Patient_Relation AS representative_relation
            FROM
                ConsentToResearch AS cr
            INNER JOIN
                PatientOverviewRiO AS po
                ON cr.ClientID = po.ClientID
            WHERE
                po.NHSNumber = %s  -- string comparison
            ORDER BY
                cr.AssessmentDate DESC
        """  # noqa
        # BEWARE "%s" IN SQL COMMENTS! The database backend will crash because
        # the number of substituted parameters will be wrong.
        # New as of 2018-06-28:
        sql = """
            SELECT TOP 1  -- guaranteed to be running SQL Server
                cr.NHSNumber AS nhs_number_text,
                cr.ClientID AS rio_number_text,
                cr.AssessmentDate AS decision_date,
                cr.ResearchContact AS traffic_light,
                    -- 'RED', 'YELLOW', 'GREEN', NULL
                0 AS use_email,  -- not in CPFT data warehouse copy
                cr.OptOut AS opt_out,  -- 1, 0 (possibly), NULL
                cr.WhoMakesDecisionFor_Patient AS decision_method,
                cr.PersonActingonBehalf_of_Patient AS representative_name,
                cr.PersonActingonBehalf_of_Patient_Relation AS representative_relation
            FROM
                ConsentToResearch AS cr
            WHERE
                cr.NHSNumber = %s  -- string comparison
            ORDER BY
                cr.AssessmentDate DESC
        """  # noqa
    else:
        assert False, "Internal bug"  # makes type checker happy

    cursor = connections[source_db].cursor()
    cursor.execute(sql, [str(nhs_number)])
    row = dictfetchone(cursor)
    if not row:
        return None

    decision_date = row["decision_date"]
    exclude_entirely = row["opt_out"] == 1
    use_email = row["use_email"] == 1
    representative_name = row["representative_name"]

    traffic_light = row["traffic_light"]
    if traffic_light:
        traffic_light = traffic_light.lower()
        if traffic_light not in ConsentMode.VALID_CONSENT_MODES:
            decisions.append(
                f"Invalid traffic light {traffic_light!r}; ignoring")
            return None

    if raw_rio:
        # Raw RiO contains codes.
        dmc = row["decision_method_code"]
        if dmc not in DECISION_METHOD_CODE_TO_TEXT.keys():
            decisions.append(
                f"Decision method code {dmc!r} unknown; ignoring")
            return None
        dm = DECISION_METHOD_CODE_TO_TEXT[dmc]
    else:
        # The CPFT Data Warehouse version contains text.
        dm = row["decision_method"]
        if dm not in DECISION_METHOD_CODE_TO_TEXT.values():
            decisions.append(
                f"Decision method {dm!r} unknown; ignoring")
            return None

    decision_by_other = (
        representative_name and
        representative_name.upper() != NOT_APPLICABLE_UPPER
    )
    # Compare what follows with decision_valid()
    decision_signed_by_patient = False
    decision_otherwise_directly_authorized_by_patient = (
        dm in [ADULT_WITH_CAPACITY_TEXT, CHILD_GILLICK_TEXT, CHILD_PARENT_TEXT]
    )
    decision_under16_signed_by_parent = (dm == CHILD_PARENT_TEXT)
    decision_under16_signed_by_clinician = (dm == CHILD_GILLICK_TEXT)
    # ... the clinician has had to verify Gillick competence
    decision_lack_capacity_signed_by_representative = (
        # not strictly "signed", but authorized directly by
        dm == ADULT_LACKS_CAPACITY_TEXT and decision_by_other
    )
    decision_lack_capacity_signed_by_clinician = (
        dm == ADULT_LACKS_CAPACITY_TEXT
    )  # ... similarly verified by clinician

    cm = ConsentMode(
        nhs_number=nhs_number,
        created_at=decision_date,
        # ... important that this date matches the source, not "now". For
        #   example, if the clinical record copy comes from time T1, and
        #   we check it at T3, but then data from T2 comes in later, we
        #   want to recognize that T2 data is newer than what we have (so
        #   the CRATE copy should be timestamped T2, not T3).
        exclude_entirely=exclude_entirely,
        consent_mode=traffic_light,
        prefers_email=use_email,
        decision_signed_by_patient=decision_signed_by_patient,
        decision_otherwise_directly_authorized_by_patient=decision_otherwise_directly_authorized_by_patient,  # noqa
        decision_under16_signed_by_parent=decision_under16_signed_by_parent,  # noqa
        decision_under16_signed_by_clinician=decision_under16_signed_by_clinician,  # noqa
        decision_lack_capacity_signed_by_representative=decision_lack_capacity_signed_by_representative,  # noqa
        decision_lack_capacity_signed_by_clinician=decision_lack_capacity_signed_by_clinician,  # noqa
    )
    return cm


def get_latest_consent_mode_from_rio_cpft_datamart(
        nhs_number: int,
        source_db: str,
        decisions: List[str]) -> Optional[ConsentMode]:
    """
    Returns the latest consent mode for a patient from the copy of RiO in
    the CPFT data warehouse.

    Args:
        nhs_number: NHS number
        source_db: the type of the source database; see
            :class:`crate_anon.crateweb.config.constants.ClinicalDatabaseType`
        decisions: list of human-readable decisions; will be modified

    Returns:
        a :class:`crate_anon.crateweb.consent.models.ConsentMode`, or ``None``

    """
    return get_latest_consent_mode_from_rio_generic(
        nhs_number=nhs_number,
        source_db=source_db,
        decisions=decisions,
        cpft_datamart=True,
    )


def get_latest_consent_mode_from_rio_raw(
        nhs_number: int,
        source_db: str,
        decisions: List[str]) -> Optional[ConsentMode]:
    """
    Returns the latest consent mode for a patient from a raw copy of RiO.

    Args:
        nhs_number: NHS number
        source_db: the type of the source database; see
            :class:`crate_anon.crateweb.config.constants.ClinicalDatabaseType`
        decisions: list of human-readable decisions; will be modified

    Returns:
        a :class:`crate_anon.crateweb.consent.models.ConsentMode`, or ``None``

    """
    return get_latest_consent_mode_from_rio_generic(
        nhs_number=nhs_number,
        source_db=source_db,
        decisions=decisions,
        raw_rio=True,
    )


def gen_opt_out_pids_mpids_rio_generic(
        source_db: str,
        raw_rio: bool = False,
        cpft_datamart: bool = False) -> Generator[Tuple[str, str],
                                                  None, None]:
    """
    Generates PIDs/MPIDs from all patients opting out, from a RiO database of
    some sort.

    Args:
        source_db: the type of the source database; see
            :class:`crate_anon.crateweb.config.constants.ClinicalDatabaseType`
        raw_rio: is the source database a raw copy of RiO?
        cpft_datamart: is the source database the version from the CPFT
            data warehouse?

    Yields:
        tuple: ``rio_number, nhs_number`` for each patient opting out; both are
        in string format
    """
    assert sum([raw_rio, cpft_datamart]) == 1, (
        "Specify exactly one database type to look up from"
    )
    if raw_rio:
        sql = """
            SELECT
                ci.ClientID AS rio_number_text,
                ci.NNN AS nhs_number_text
            FROM
                UserAssessconsentrd AS cr
            INNER JOIN
                ClientIndex AS ci
                ON cr.ClientID = ci.ClientID
            WHERE
                cr.optout = 1
            ORDER BY
                cr.ClientID
        """
    elif cpft_datamart:
        sql = """
            SELECT
                po.ClientID AS rio_number_text,
                po.NHSNumber AS nhs_number_text
            FROM
                ConsentToResearch AS cr
            INNER JOIN
                PatientOverviewRiO AS po
                ON cr.ClientID = po.ClientID
            WHERE
                cr.OptOut = 1
            ORDER BY
                cr.ClientID
        """  # noqa
    else:
        assert False, "Internal bug"  # makes type checker happy

    cursor = connections[source_db].cursor()
    cursor.execute(sql)
    for row in genrows(cursor):
        pid = row[0]  # RiO number, as text
        mpid = row[1]  # NHS number, as text
        yield pid, mpid


def gen_opt_out_pids_mpids_rio_cpft_datamart(source_db: str) -> Generator[
        Tuple[str, str], None, None]:
    """
    Generates PIDs/MPIDs from all patients opting out, from a RiO database that
    is the version in the CPFT data warehouse.

    Args:
        source_db: the type of the source database; see
            :class:`crate_anon.crateweb.config.constants.ClinicalDatabaseType`

    Yields:
        tuple: ``rio_number, nhs_number`` for each patient opting out; both are
        in string format
    """
    return gen_opt_out_pids_mpids_rio_generic(
        source_db=source_db,
        cpft_datamart=True
    )


def gen_opt_out_pids_mpids_rio_raw(source_db: str) -> Generator[
        Tuple[str, str], None, None]:
    """
    Generates PIDs/MPIDs from all patients opting out, from a raw RiO database.

    Args:
        source_db: the type of the source database; see
            :class:`crate_anon.crateweb.config.constants.ClinicalDatabaseType`

    Yields:
        tuple: ``rio_number, nhs_number`` for each patient opting out; both are
        in string format
    """
    return gen_opt_out_pids_mpids_rio_generic(
        source_db=source_db,
        raw_rio=True
    )
