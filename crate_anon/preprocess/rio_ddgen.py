"""
crate_anon/preprocess/rio_ddgen.py

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

**Generate hints for Servelec RiO/RCEP databases, so CRATE can draft an
appropriate data dictionary.**

The results should still be reviewed by a human!

"""

from crate_anon.anonymise.constants import AnonymiseDatabaseSafeConfigKeys
from crate_anon.preprocess.ddhint import DDHint
from crate_anon.preprocess.constants import CRATE_COL_PK
from crate_anon.preprocess.rio_constants import (
    CRATE_COL_RIO_NUMBER,
    RIO_COL_PATIENT_ID,
    VIEW_ADDRESS_WITH_GEOGRAPHY,
)


# =============================================================================
# Default settings for CRATE anonymiser "ddgen_*" fields, for RiO
# =============================================================================


def get_rio_dd_settings(ddhint: DDHint) -> str:
    """
    Draft CRATE config file settings that will allow CRATE to create a RiO
    data dictionary near-automatically.

    Args:
        ddhint: :class:`crate_anon.preprocess.ddhint.DDHint`

    Returns:
        the config file settings, as a string
    """
    suppress_tables = "\n    ".join(ddhint.get_suppressed_tables())
    sk = AnonymiseDatabaseSafeConfigKeys
    return f"""
{sk.DDGEN_OMIT_BY_DEFAULT} = True

{sk.DDGEN_OMIT_FIELDS} =

{sk.DDGEN_INCLUDE_FIELDS} = #
    # -------------------------------------------------------------------------
    # RCEP core views:
    # -------------------------------------------------------------------------
    Care_Plan_Index.*
    Care_Plan_Interventions.*
    Care_Plan_Problems.*
    Client_Address_History.*
    Client_Alternative_ID.*
    Client_Allergies.*
    Client_Communications_History.*
    Client_CPA.*
    Client_Demographic_Details.*
    Client_Family.*
    Client_GP_History.*
    Client_Medication.*
    Client_Name_History.*
    Client_Personal_Contacts.*
    Client_Physical_Details.*
    Client_Prescription.*
    Client_Professional_Contacts.*
    Client_School.*
    CPA_CareCoordinator.*
    CPA_Review.*
    Diagnosis.*
    Inpatient_Stay.*
    Inpatient_Leave.*
    Inpatient_Movement.*
    Inpatient_Named_Nurse.*
    Inpatient_Sleepover.*
    Referral.*
    Progress_Notes.*
    Referral_Staff_History.*
    Referral_Team_History.*
    Referral_Waiting_Status_History.*
    # -------------------------------------------------------------------------
    # Non-core:
    # -------------------------------------------------------------------------
    CPFT_*.*  # all fields in "CPFT_*" views

{sk.DDGEN_PER_TABLE_PID_FIELD} = crate_rio_number

{sk.DDGEN_ADD_PER_TABLE_PIDS_TO_SCRUBBER} = False

{sk.DDGEN_MASTER_PID_FIELDNAME} = crate_nhs_number_int
    # ... is in Client_Demographic_Details view

{sk.DDGEN_TABLE_DENYLIST} = #
    # -------------------------------------------------------------------------
    # Denylist: Prefixes: groups of tables; individual tables
    # -------------------------------------------------------------------------
    Agresso*  # Agresso [sic] module (comms to social worker systems)
    ADT*  # ?admit/discharge/transfer messages (see codes in ADTMessage)
    Ams*  # Appointment Management System (Ams) module
    Audit*  # RiO Audit Trail
    CDSContract*  # something to do with commissioner contracts
    Chd*  # Child development (interesting, but lots of tables and all empty)
    Client  # RiO 5; superseded by ClientIndex (and then view Client_Demographic_Details); ?runs alongside as partial duplicate?
    ClientAddressHistory  # defunct according to RIO 6.2 docs
    ClientAddressMerged  # defunct according to RIO 6.2 docs
    ClientChild*  # child info e.g. birth/immunisation (interesting, but several tables and all empty)
    ClientCommunityDomain # defunct according to RIO 6.2 docs
    ClientFamily  # contains only a comment; see ClientFamilyLink instead
    ClientMerge*  # record of admin events (merging of client records)
    ClientPhoto*  # no use to us or identifiable!
    ClientRestrictedRecord*  # ? but admin
    Con*  # Contracts module
    DA*  # Drug Administration within EP
    DemAuditTrail  # not in v6.2 docs; ?audit trail for demographics
    DgnDiagnosis  # "Obsolete"; see DiagnosisClient
    DS*  # Drug Service within EP
    dtoElectoralWardPCLookup  # we do our own geography; 2.5m records
    EP*  # E-Prescribing (EP) module, which we don't have
    #   ... mostly we don't have it, but we may have EPClientAllergies etc.
    #   ... so see allowlist too
    ESRImport  # user-to-?role map? Small and system.
    ExternalSystem*  # system
    GenChd*  # lookup codes for Chd*
    GenCon*  # lookup codes for Con*
    GenDiagnosis  # "Obsolete"
    GenError*  # system
    GenExtendedPostcode  # we provide our own geography lookups; 5m records
    GenExtract*  # details of reporting extracts
    GenHCPTemplateDetails  # HCP diary template
    GenIDSeed  # system (counters for different ID types)
    GenLicenseKeys  # system; NB shows what components are licensed!
    GenNumbers  # just a list of integers
    GenPostcodeGeographicDataMappings  # as above, we do our own geography; 2.5m records
    GenPrinter*  # printers
    GenToDoList  # user to-do list items/notifications
    gridall  # same number of records as dtoElectoralWardPCLookup; also geography;
    KP90ErrorLog  # error log for KP90 report; https://www.hscic.gov.uk/datacollections/kp90
    LR*  # Legitimate Relationships module
    Meeting*  # Meetings module
    Mes*  # messaging
    MonthlyPlanner*  # system
    PSS*  # Prevention, Screening & Surveillance (PSS)
    RioPerformanceTimings  # system
    RR*  # Results Reporting (e.g. laboratories, radiology)
    #   ... would be great, but we don't have it
    RTT*  # RTT* -- Referral-to-Treatment (RTT) data collection (see NHS England docs)
    SAF*  # SAF* -- system; looks like details of tablet devices
    Scheduler*  # Scheduler* -- Scheduler module (for RiO computing)
    Sec*  # Security? Definitely RiO internal stuff.
    SPINE*  # system
    SPRExternalNotification  # system?
    tbl*  # records of changes to tables?
    TeamPlanner*  # system
    Temp*  # system
    umt*  # system
    Wfl*  # workflow
    WL*  # Waiting lists (WL) module
    view_AuditTrailPurge  # system; e.g. 96m records
    # -------------------------------------------------------------------------
    # Denylist: Middle bits, suffixes
    # -------------------------------------------------------------------------
    *Access*  # system access controls
    *Backup  # I'm guessing backups...
    *Cache*  # system
    *Lock*  # system
    *Timeout*  # system
    # -------------------------------------------------------------------------
    # Denylist: CPFT custom
    # -------------------------------------------------------------------------
    CDL_OUTDATEDPATIENTS_TWI  # RiO to CPFT 'M' number mapping, but we will use NHS number
    # -------------------------------------------------------------------------
    # Denylist: Views supersede
    # Below here, we have other tables suppressed because CRATE's views offer
    # more comprehensive alternatives
    # -------------------------------------------------------------------------
    {suppress_tables}

# USEFUL TABLES (IN CPFT INSTANCE) INCLUDE:
# =========================================
# Assessment* -- includes maps of non-core assessments (see e.g. AssessmentIndex)
# CDL_OUTDATEDPATIENTS_TWI -- map from TWI (trust-wide identifier) to old CPFT M number
# UserAssess* -- non-core assessments themselves
# UserMaster* -- lookup tables for non-core assessments

{sk.DDGEN_TABLE_ALLOWLIST} = #
    # -------------------------------------------------------------------------
    # Allowlist: Prefixes: groups of tables
    # -------------------------------------------------------------------------
    EPClientAllergy*  # Allergy details within EP module
    # -------------------------------------------------------------------------
    # Allowlist: Suffixes
    # -------------------------------------------------------------------------
    *_crate  # Views added by CRATE
    # -------------------------------------------------------------------------
    # Allowlist: Individual tables
    # -------------------------------------------------------------------------
    EPReactionType  # Allergy reaction type details within EP module

{sk.DDGEN_TABLE_REQUIRE_FIELD_ABSOLUTE} = #
    # All tables/fields must have crate_pk
    {CRATE_COL_PK}

{sk.DDGEN_TABLE_REQUIRE_FIELD_CONDITIONAL} = #
    # If a table/view has ClientID, it must have crate_rio_number
    {RIO_COL_PATIENT_ID}, {CRATE_COL_RIO_NUMBER}

{sk.DDGEN_FIELD_DENYLIST} = #
    {RIO_COL_PATIENT_ID}  # replaced by crate_rio_number (which is then pseudonymised)
    *Soundex  # identifying 4-character code; https://msdn.microsoft.com/en-us/library/ms187384.aspx
    Spine*  # NHS Spine identifying codes

{sk.DDGEN_FIELD_ALLOWLIST} =

{sk.DDGEN_PK_FIELDS} = crate_pk

{sk.DDGEN_PREFER_ORIGINAL_PK} = False

{sk.DDGEN_CONSTANT_CONTENT} = False

{sk.DDGEN_CONSTANT_CONTENT_TABLES} =

{sk.DDGEN_NONCONSTANT_CONTENT_TABLES} =

{sk.DDGEN_ADDITION_ONLY} = False

{sk.DDGEN_ADDITION_ONLY_TABLES} = #
    UserMaster*  # Lookup tables for non-core - addition only?

{sk.DDGEN_DELETION_POSSIBLE_TABLES} =

{sk.DDGEN_PID_DEFINING_FIELDNAMES} = Client_Demographic_Details.crate_rio_number

{sk.DDGEN_SCRUBSRC_PATIENT_FIELDS} = # several of these:
    # ----------------------------------------------------------------------
    # Original RiO tables (some may be superseded by views; list both here;
    # if the table is denylisted anyway, it doesn't matter).
    # ----------------------------------------------------------------------
    AmsReferral.DischargeAddressLine*  # superseded by view Referral
    AmsReferral.DischargePostCode  # superseded by view Referral
    ClientAddress.AddressLine*  # superseded by view Client_Address_History
    ClientAddress.PostCode  # superseded by view Client_Address_History
    ClientAlternativeID.ID  # superseded by view Client_Alternative_ID
    ClientIndex.crate_pk  # superseded by view Client_Demographic_Details
    ClientIndex.DateOfBirth  # superseded by view Client_Demographic_Details
    ClientIndex.DaytimePhone  # superseded by view Client_Demographic_Details
    ClientIndex.EMailAddress  # superseded by view Client_Demographic_Details
    ClientIndex.EveningPhone  # superseded by view Client_Demographic_Details
    ClientIndex.Firstname  # superseded by view Client_Demographic_Details
    ClientIndex.MobilePhone  # superseded by view Client_Demographic_Details
    ClientIndex.NINumber  # superseded by view Client_Demographic_Details
    ClientIndex.OtherAddress  # superseded by view Client_Demographic_Details
    ClientIndex.SpineID  # superseded by view Client_Demographic_Details
    ClientIndex.Surname  # superseded by view Client_Demographic_Details
    ClientName.GivenName*  # superseded by view Client_Name_History
    ClientName.Surname  # superseded by view Client_Name_History
    ClientOtherDetail.NINumber
    ClientTelecom.Detail  # superseded by view Client_Communications_History
    ImsEvent.DischargeAddressLine*  # superseded by view Inpatient_Stay
    ImsEvent.DischargePostCode*  # superseded by view Inpatient_Stay
    ImsEventLeave.AddressLine*  # superseded by view Inpatient_Leave
    ImsEventLeave.PostCode  # superseded by view Inpatient_Leave
    # ----------------------------------------------------------------------
    # Views
    # ----------------------------------------------------------------------
    Client_Address_History.Address_Line_*
    Client_Address_History.Post_Code
    Client_Alternative_ID.ID
    Client_Communications_History.crate_telephone
    Client_Communications_History.crate_email_address
    Client_Demographic_Details.crate_rio_number
    Client_Demographic_Details.NHS_Number
    Client_Demographic_Details.Firstname
    Client_Demographic_Details.Surname
    Client_Demographic_Details.Date_of_Birth
    Client_Demographic_Details.National_Insurance_Number
    Client_Demographic_Details.*Phone
    Client_Demographic_Details.Superseding_NHS_Number
    Client_Name_History.Given_Name_*
    Client_Name_History.Family_Name
    Inpatient_Leave.Address_Line*
    Inpatient_Leave.PostCode
    Inpatient_Stay.Discharge_Address_Line_*
    Inpatient_Stay.Discharge_Post_Code*
    Referral.Discharge_Address_Line_*
    Referral.Discharge_Post_Code*
    {VIEW_ADDRESS_WITH_GEOGRAPHY}.AddressLine*  # superseded by other view Client_Address_History
    {VIEW_ADDRESS_WITH_GEOGRAPHY}.PostCode  # superseded by other view Client_Address_History

{sk.DDGEN_SCRUBSRC_THIRDPARTY_FIELDS} = # several:
    # ----------------------------------------------------------------------
    # Original RiO tables (some may be superseded by views; list both here)
    # ----------------------------------------------------------------------
    # ClientFamilyLink.RelatedClientID  # superseded by view Client_Family
    ClientContact.Surname  # superseded by view Client_Personal_Contacts
    ClientContact.Firstname  # superseded by view Client_Personal_Contacts
    ClientContact.AddressLine*  # superseded by view Client_Personal_Contacts
    ClientContact.PostCode  # superseded by view Client_Personal_Contacts
    ClientContact.*Phone  # superseded by view Client_Personal_Contacts
    ClientContact.EmailAddress  # superseded by view Client_Personal_Contacts
    ClientContact.NHSNumber  # superseded by view Client_Personal_Contacts
    # ClientIndex.MainCarer  # superseded by view Client_Demographic_Details
    # ClientIndex.OtherCarer  # superseded by view Client_Demographic_Details
    # ----------------------------------------------------------------------
    # RCEP/CRATE views
    # ----------------------------------------------------------------------
    Client_Personal_Contacts.Family_Name
    Client_Personal_Contacts.Given_Name
    Client_Personal_Contacts.Address_Line_*
    Client_Personal_Contacts.Post_Code
    Client_Personal_Contacts.*Phone
    Client_Personal_Contacts.Email_Address
    Client_Personal_Contacts.NHS_Number

{sk.DDGEN_SCRUBSRC_THIRDPARTY_XREF_PID_FIELDS} = # several:
    # ----------------------------------------------------------------------
    # Original RiO tables (some may be superseded by views; list both here)
    # ----------------------------------------------------------------------
    # none; these are not integer:
    # ClientFamilyLink.RelatedClientID  # superseded by view Client_Family
    # ClientIndex.MainCarer  # superseded by view Client_Demographic_Details
    # ClientIndex.OtherCarer  # superseded by view Client_Demographic_Details
    # ----------------------------------------------------------------------
    # RCEP/CRATE views
    # ----------------------------------------------------------------------
    Client_Demographic_Details.Main_Carer
    Client_Demographic_Details.Other_Carer
    Client_Family.Related_Client_ID

{sk.DDGEN_REQUIRED_SCRUBSRC_FIELDS} = # several:
    Client_Demographic_Details.Date_Of_Birth
    Client_Name_History.Given_Name_1
    Client_Name_History.Family_Name

{sk.DDGEN_SCRUBMETHOD_CODE_FIELDS} = # variants:
    *PostCode*
    *Post_Code*
    NINumber
    National_Insurance_Number
    ClientAlternativeID.ID
    Client_Alternative_ID.ID

{sk.DDGEN_SCRUBMETHOD_DATE_FIELDS} = *Date*

{sk.DDGEN_SCRUBMETHOD_NUMBER_FIELDS} = #
    *Phone*
    *NNN*
    *NHS_Number*

{sk.DDGEN_SCRUBMETHOD_PHRASE_FIELDS} = *Address*

{sk.DDGEN_SAFE_FIELDS_EXEMPT_FROM_SCRUBBING} =

    # RiO mostly uses string column lengths of 4, 10, 20, 40, 80, 500,
    # unlimited. So what length is the minimum for "free text"?
    # Comments are 500. Lots of 80-length fields are lookup descriptions.
    # (Note that many scrub-SOURCE fields are of length 80, e.g. address
    # fields, but they need different special handling.)
{sk.DDGEN_MIN_LENGTH_FOR_SCRUBBING} = 81

{sk.DDGEN_TRUNCATE_DATE_FIELDS} = Client_Demographic_Details.Date_Of_Birth

{sk.DDGEN_FILENAME_TO_TEXT_FIELDS} = Clinical_Documents.Path

{sk.DDGEN_BINARY_TO_TEXT_FIELD_PAIRS} =

{sk.DDGEN_SKIP_ROW_IF_EXTRACT_TEXT_FAILS_FIELDS} = Clinical_Documents.Path

{sk.DDGEN_INDEX_FIELDS} =

{sk.DDGEN_ALLOW_FULLTEXT_INDEXING} = True

{sk.DDGEN_FORCE_LOWER_CASE} = False

{sk.DDGEN_CONVERT_ODD_CHARS_TO_UNDERSCORE} = True
"""  # noqa
