#!/usr/bin/env python

r"""
crate_anon/preprocess/preprocess_rio.py

===============================================================================

    Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).

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

**Generate a CRATE data dictionary for SystmOne data.**


Notes
-----

- SystmOne is a general-purpose electronic health record (EHR) system from TPP
  (The Phoenix Partnership): https://tpp-uk.com/products/.

- TPP provide a nightly "Strategic Reporting extract" (SRE) of SystmOne data.

- Its primary coding mechanisms are (1) CTV3 (Read) codes, and (2) SNOMED
  codes (see e.g. https://termbrowser.nhs.uk/) -- the latter are gradually
  taking over (as of 2021). Coded values can be numeric. For example, one entry
  might include:

  - SNOMED code 718087004
  - SNOMED text "QRISK2 cardiovascular disease 10 year risk score"
  - CTV3 code "XaQVY"
  - CTV3 text "QRISK2 cardiovascular disease 10 year risk score"
  - Numeric unit "%"
  - Numeric value 10.4

- SystmOne collects data mostly via "templates" and "questionnaires". Templates
  are perhaps closer to the heart of SystmOne (e.g. better presented in the
  long-form journal view) and values entered into templates are (always?)
  coded. Questionnaires are more free-form. Both can have free text attached to
  coded values.


Strategic Reporting extract
---------------------------

``SpecificationDirectory.zip`` (e.g. 2021-02-18) contains e.g. ``Specification
v123.csv``, which is a full description of the SRE. Principles:

- All these tables start ``SR``, e.g. ``SR18WeekWait``, ``SRAAndEAttendance``.

- Columns in that spreadsheet are:

  .. code-block:: none

    TableName
    TableDescription
    ColumnName
    ColumnDescription
    ColumnDataType -- possible values include:
        Boolean
        Date
        Date and Time
        Numeric - Integer
        Numeric - Real
        Text - Fixed
        Text - Variable
    ColumnLength -- possible values include:
        empty (e.g. boolean, date, date/time)
        8 for integer
        4 for real
        the VARCHAR length -- for both "variable" and "fixed" text types
    DateDefining
    ColumnOrdinal -- sequence number of column within table
    LinkedTable     }
    LinkedColumn1   }-+
    LinkedColumn2   } |
                      +-- e.g.
                            SROrganisation, ID
                            SRStaffMember, RowIdentifier
                            SRPatient, RowIdentifier, IDOrganisationVisibleTo

- To get a table list:

  .. code-block:: bash

    # Poor for CSVs with newlines within their strings:
    tail -n+2 "Specification v123.csv" | cut -d, -f1 | sort | uniq

    # Much better:
    python3 -c 'import csv; print("\n".join(row[0] for i, row in enumerate(csv.reader(open("Specification v123.csv"))) if i > 0))' | sort | uniq

- Tables and their descriptions:

  .. code-block:: python

    import csv
    s = set()
    for i, row in enumerate(csv.reader(open("Specification v123.csv"))):
        if i > 0:
            s.add(f"{row[0]} - {row[1]}")

    print("\n".join((x for x in sorted(s))))

  Translating that to a single line: https://www.python.org/dev/peps/pep-0289/
  ... meh, hard.

- ``SRPatient`` looks to be the master patient table here -- including names,
  dates of birth/death, NHS number.

- ``Tpp Strategic Reporting Table Specification v123.rtf`` contains a nicer
  version of (exactly?) the same information.

- Strategic Reporting downloads can be configured. Options include:

  - Whether to include the shared record. (I'm not sure if that means a
    national thing or data from SystmOne that each patient may have consented
    to sharing "'out' from another organization, then 'in' to mine".)

- When a download is set up, the recipient gets one CSV file per table
  selected, such as ``SRPatient.csv`` for the ``SRPatient`` table, plus some
  ever-present system tables:

  - ``SRManifest.csv``, describing what you've received;
  - ``SRMapping.csv`` and ``SRMappingGroup.csv``, providing text for built-in
     lists.

- The date format is e.g. "29 Sep 2011 14:53:28". Unknown times are marked as
  "00:00:00". Unknown dates give an empty string. Boolean values are ``TRUE``
  or ``FALSE``.


Free-text data
--------------

The SRE does not contain free text data or binary documents by default. For
some Trusts, an augmented SRE is provided also, with that information.

From ``FreeText Model.xlsx``, 2021-04-15, some of this data comes in the
following format:

.. code-block:: none

    Field Name	                Type	        Description
    RowIdentifier	            bigint	        The unique identifier of the
                                                record
    IDPatient	                bigint	        Links to patient ID in
                                                demographics
    IDReferralIn	            bigint	        ID of referral
    IDEvent	                    bigint	        Links to activity event ID
    Question	                varchar(MAX)	The questionnaire question
    [FreeText]	                varchar(MAX)	The answer given to the above
                                                question
    EventDate	                datetime	    The data/time of the
                                                questionnaire
    SRTable	                    varchar(100)	Which SR table the record
                                                relates to
    IDSRTable	                bigint	        The ID of the above table
    QuestionnaireName	        varchar(255)	The name of the questionnaire
    IDAnsweredQuestionnaire	    bigint	        The ID of the above
                                                questionnaire
    QuestionnaireVersionNumber	int	            The version number of the above
                                                questionnaire
    IDOrganisation	            bigint	        Organisation ID of the
                                                questionnaire record
    CPFTGroup	                int	            Group (directorate)
    Directorate	                varchar(50)	    Directorate name
    TeamName	                varchar(100)	Name of team linked to the
                                                referral
    IsMentalHealth	            int	            Mental or physical health
    Imported	                date	        Date imported to the database

    (SR = Strategic Reporting.)

Specimen values:

- SRTable: 'SRAnsweredQuestionnaire'
- IDSRTable: this varies for rows with SRTable = 'SRAnsweredQuestionnaire', so
  I think it's the PK within the table indicated by SRTable.
- QuestionnaireName = 'CPFT Risk Assessment'
- IDAnsweredQuestionnaire = this is unique for rows with QuestionnaireName =
  'CPFT Risk Assessment', so I think it's the ID of the Questionnaire, and is
  probably a typo.

(This ends up (in our environment) in the S1_FreeText table, as below, so it
likely arrives as SRFreeText.)


Key fields
----------

- ``IDPatient`` -- the SystmOne patient number, in all patient tables (PID,
  in CRATE terms).
- ``SRPatient.NHSNumber`` -- the NHS number (MPID, in CRATE terms).


Notable tables in the SRE
-------------------------

- [SR]Patient, as above

- Patient identifiers and relationship/third-party details:

  - [SR]PatientAddressHistory
  - [SR]PatientContactDetails
  - [SR]HospitalAAndENumber

- Relationship/third-party details:

  - [SR]PatientRelationship
  - some of the safeguarding tables

- [SR]NDOptOutPreference, re NHS national data opt out (for NHS Act s251 use)

- Full text and binary:

  - [SR]Media
  - [SR]FreeText -- if supplied


Notable additional tables/columns in the CPFT environment
---------------------------------------------------------

- S1_FreeText -- this includes all answers to Questionnaires (linked via
  ``IDAnsweredQuestionnaire`` etc.).

- Several tables have identifiers linked in. For example, try:

  .. code-block:: sql
  
    SELECT * FROM information_schema.columns WHERE column_name = 'FirstName'


Notable tables omitted from the CPFT environment
------------------------------------------------

- Questionnaire -- data is linked into to AnsweredQuestionnaire (which still
  contains the column ``IDQuestionnaire``).


CPFT copy
---------

This broadly follows the SRE, but is expanded. Some notable differences:

- Tables named ``SR*`` in the SRE are named ``S1_*`` in the CPFT version (e.g.
  ``SRPatient`` becomes ``S1_Patient``).

- There is a ``S1_Patient.NationalDataOptOut`` column.

- There seem to be quite a few extra tables, such as:

  .. code-block:: none

    S1_ClinicalMeasure_QRisk
    S1_ClinicalMeasure_SWEMWBS
    S1_ClinicalMeasure_Section58

  These look like CPFT-created tables pulling data from questionnaires or
  similar.

- There is ``S1_FreeText``, where someone (NP!) has helpfully imported that
  additional data.

- There is ``S1_ClinicalOutcome_ConsentResearch``, which is the traffic-light
  system for the CPFT Research Database.

In more detail:

- All data is loaded via stored procedures, available via Microsoft SQL Server
  Management Studio in :menuselection:`[server] --> [database] -->
  Programmability --> Stored Procedures`. Right-click any and choose "Modify"
  to view the source. For example, the stored procedure named
  ``dbo.load_S1_Patient`` creates the ``S1_Patient`` table.

- ``RwNo`` is frequently used, typically via:

  .. code-block:: none

    SELECT
        -- stuff,
        ROW_NUMBER() OVER (
            PARTITION BY IDPatient
            ORDER BY DateEventRecorded DESC
        ) RwNo
    FROM
        -- somewhere
    WHERE
        RwNo = 1

  ... in other words, picking the most recent for each patient.


Related tools
-------------

- The OpenSAFELY research tool runs on SystmOne data (with other data linked
  in); it therefore provides helpful code lists. See

  - https://github.com/opensafely
  - https://github.com/opensafely-core

  This tool is one that separates researchers from data (by allowing queries,
  not researchers, access); it made its debut during COVID-19 with Williamson
  et al. (2020), https://pubmed.ncbi.nlm.nih.gov/32640463/.

- Other such tools like DataSHIELD (https://www.datashield.org/, or e.g. Gaye
  et al. 2014, https://pubmed.ncbi.nlm.nih.gov/25261970/) perform similar
  researcher/data separation via other methods.

"""  # noqa

# *** todo: implement S1_ClinicalOutcome_ConsentResearch when it arrives

# =============================================================================
# Imports
# =============================================================================

import csv
from dataclasses import dataclass, field
from enum import Enum
import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from cardinal_pythonlib.dicts import reversedict
from cardinal_pythonlib.enumlike import CaseInsensitiveEnumMeta

from crate_anon.anonymise.altermethod import AlterMethod
from crate_anon.anonymise.config import Config
from crate_anon.anonymise.constants import (
    Decision,
    IndexType,
    ScrubMethod,
    ScrubSrc,
    SrcFlag,
)
from crate_anon.anonymise.dd import DataDictionary, DataDictionaryRow

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# -----------------------------------------------------------------------------
# Typing
# -----------------------------------------------------------------------------

SRE_SPEC_TYPE = Dict[Tuple[str, str],
                     "SystmOneSRESpecRow"]
# ... maps (tablename, colname) tuples to SystmOneSRESpecRow objects.

TABLE_TRANSLATION_DICT_TYPE = Dict["SystmOneContext",
                                   Dict[str, str]]
# ... maps a SystmOneContext to a dictionary mapping one tablename to another

COLUMN_TRANSLATION_DICT_TYPE = Dict["SystmOneContext",
                                    Dict[Tuple[str, str], str]]
# ... maps a SystmOneContext to a dictionary mapping (table, col) to newcol


# -----------------------------------------------------------------------------
# Helper functions for constants
# -----------------------------------------------------------------------------

def _flip_coldict(d: Dict[Tuple[str, str], str]) -> Dict[Tuple[str, str], str]:
    """
    Flips a mapping from (tablename, col1): col2 to (tablename, col2): col1.
    """
    newmap = {}  # type: Dict[Tuple[str, str], str]
    for (table, srccol), newcol in d.items():
        newmap[(table, newcol)] = srccol
    return newmap


# -----------------------------------------------------------------------------
# Cosmetic
# -----------------------------------------------------------------------------

COMMENT_SEP = " // "


# -----------------------------------------------------------------------------
# Contexts and table naming
# -----------------------------------------------------------------------------

class SystmOneContext(Enum, metaclass=CaseInsensitiveEnumMeta):
    """
    Environments in which we might have SystmOne data.
    """
    TPP_SRE = "TPP Strategic Reporting Extract"
    CPFT_DW = "CPFT Data Warehouse"


DEFAULT_SYSTMONE_CONTEXT = SystmOneContext.CPFT_DW
TABLE_PREFIXES = {
    SystmOneContext.TPP_SRE: "SR",
    SystmOneContext.CPFT_DW: "S1_",
}


# -----------------------------------------------------------------------------
# Table names
# -----------------------------------------------------------------------------
# "Core" tablename, without the SR/S1_/... prefix.

S1_TAB_PATIENT = "Patient"  # e.g. SRPatient (SRE), S1_Patient (CPFT)
S1_TAB_ADDRESS = "PatientAddressHistory"
S1_TAB_CONTACT_DETAILS = "PatientContactDetails"
S1_TAB_RELATIONSHIPS = "PatientRelationship"

# Other tables starting "Patient":
# - SRPatientContactProperty: seems not relevant; describes visits/diary events
# - SRPatientGroups: e.g. to group patients in a residential home; also family,
#   but contains no direct identifiers.
# - SRPatientLeave: leave from hospital.
# - SRPatientLocation: location within A&E departments, I think.
# - SRPatientRegistration: registration status (and who did it); also their
#   preferred pharmacy; but no direct identifiers.

S1_TAB_HOSP_AE_NUMBERS = "HospitalAAndENumber"
S1_TAB_MEDIA = "Media"  # todo: binary documents -- how?
S1_TAB_SAFEGUARDING_PERSON_AT_RISK = "SafeguardingPersonAtRisk"

# See also OMIT_TABLENAME_COLNAME_PAIRS below.
#
# Other tables whose name might suggest patient identifiers:
# - SRAddressBookEntry: institutional addresses only? (FK to this from
#   SRSafeguardingIncidentDetails, for example.) todo: check -- institutional addresses only?  # noqa
# - SRHospitalAdmissionAndDischarge, etc. -- no external identifiers linked to
#   HospitalAAndENumber, just SystmOne IDs.
# - SROohEmergencyCall -- no contact numbers.
# - SROohTransport -- very structured.
# - SROohVisit -- very structured.

S1_TO_CPFT_TABLE_TRANSLATION = {
    # Where CPFT has renamed a S1 SRE table directly.
    S1_TAB_ADDRESS: "PatientAddress",
    # ... i.e. CPFT have renamed SRPatientAddressHistory to S1_PatientAddress.
    S1_TAB_CONTACT_DETAILS: "PatientContact",
}

CPFT_TAB_REL_MOTHER = "PatientRelationshipMother"

# -----------------------------------------------------------------------------
# Table collections
# -----------------------------------------------------------------------------

OMIT_TABLES = (
    "NomisNumber",  # Prison NOMIS numbers

    # CPFT extras:
    "gr_workings",  # no idea
    "Inpatients",  # S1_Inpatients: current inpatients -- but has NHSNumber as FLOAT  # noqa
)
OMIT_TABLES_REGEX = (
    # CPFT extras:
    # ... nothing; we were doing "vw" (views) and "zzz" (scratch tables) but
    # this should be handled by --systmone_allow_unprefixed_tables (and now
    # is), so the user can decide.
)
CORE_TO_CONTEXT_TABLE_TRANSLATIONS = {
    # Key: destination context.
    # Value: translation dictionary, mapping "core" tablename to target.
    # Absent values lead to no translation.
    SystmOneContext.TPP_SRE: {},
    SystmOneContext.CPFT_DW: S1_TO_CPFT_TABLE_TRANSLATION,
}  # type: TABLE_TRANSLATION_DICT_TYPE
CONTEXT_TO_CORE_TABLE_TRANSLATIONS = {
    SystmOneContext.TPP_SRE: {},
    SystmOneContext.CPFT_DW: reversedict(S1_TO_CPFT_TABLE_TRANSLATION),
}  # type: TABLE_TRANSLATION_DICT_TYPE


# -----------------------------------------------------------------------------
# Column names
# -----------------------------------------------------------------------------
# We work internally with TPP SRE column names. Any renaming (e.g. in CPFT) is
# explicitly noted.

# Columns in all tables:
S1_GENERIC_COL_DONE_AT = "IDOrganisationDoneAt"  # FK to SROrganisation.ID
S1_GENERIC_COL_DONE_BY = "IDDoneBy"  # FK to SRStaffMember.RowIdentifier
S1_GENERIC_COL_EVENT_ID = "IDEvent"  # FK to SREvent.RowIdentifier
S1_GENERIC_COL_EVENT_OCCURRED = "DateEvent"  # when event happened
S1_GENERIC_COL_EVENT_RECORDED = "DateEventRecorded"  # when event recorded
S1_GENERIC_COL_ORG = "IDOrganisation"  # org at which the data was entered
S1_GENERIC_COL_ORG_ID = "IDOrganisationVisibleTo"  # FK to SROrganisation.ID
S1_GENERIC_COL_ORG_REGISTERED_AT = "IDOrganisationRegisteredAt"  # org where the patient was registered when the data was entered  # noqa
S1_GENERIC_COL_PID = "IDPatient"  # FK to Patient table
S1_GENERIC_COL_PK = "RowIdentifier"  # PK for all tables
S1_GENERIC_COL_RECORDED_BY = "IDProfileEnteredBy"  # FK to SRStaffMemberProfile.RowIdentifier  # noqa

# Columns in the Patient table:
S1_PATIENT_COL_NHSNUM = "NHSNumber"
S1_PATIENT_COL_TITLE = "Title"
S1_PATIENT_COL_FORENAME = "FirstName"
S1_PATIENT_COL_MIDDLE_NAMES = "MiddleNames"
S1_PATIENT_COL_SURNAME = "Surname"
S1_PATIENT_COL_PREV_SURNAME = "PreviousSurname"
S1_PATIENT_COL_EMAIL = "EmailAddress"
S1_PATIENT_COL_DOB = "DateBirth"
S1_PATIENT_COL_DOD = "DateDeath"
S1_PATIENT_COL_BIRTHPLACE = "BirthPlace"
S1_PATIENT_COL_GENDER = "Gender"
S1_PATIENT_COL_SPEAKS_ENGLISH = "SpeaksEnglish"  # curious that this is a specific flag  # noqa
S1_PATIENT_COL_TESTPATIENT = "TestPatient"
S1_PATIENT_COL_SOCIAL_SERVICES_REF = "SSRef"
S1_PATIENT_COL_SPINE_MATCHED = "SpineMatched"

# Columns in the PatientAddressHistory table:
S1_ADDRESS_COL_BUILDING_NAME = "NameOfBuilding"
S1_ADDRESS_COL_BUILDING_NUMBER = "NumberOfBuilding"
S1_ADDRESS_COL_ROAD = "NameOfRoad"
S1_ADDRESS_COL_LOCALITY = "NameOfLocality"
S1_ADDRESS_COL_TOWN = "NameOfTown"
S1_ADDRESS_COL_COUNTY = "NameOfCounty"
S1_ADDRESS_COL_POSTCODE = "FullPostCode"
CPFT_ADDRESS_COL_POSTCODE_NOSPACE = "PostCode_NoSpaces"

# Columns in the PatientContactDetails table:
S1_CONTACT_COL_NUMBER = "ContactNumber"

# Columns in the PatientRelationship table:
# (this is also one that we specify everything in detail, since CPFT add in
# extra identifiers)
S1_REL_COL_RELATED_ID_DEPRECATED = "IDRelationshipWithPatient"
# ... replaced by IDPatientRelationshipWith
S1_REL_COL_RELATED_ID = "IDPatientRelationshipWith"
S1_REL_COL_RELATED_STAFFCODE_OR_RELNHSNUM = "CodeRelationshipWithUser"
# ... SRE help says "The ODS code for the staff member the relationship is
# with". However, it seems that it sometimes contains the NHS number of the
# relative (certainly an NHS number that differs from the patient's!).
S1_REL_COL_NAME = "RelationshipWithName"
S1_REL_COL_DOB = "RelationshipWithDateOfBirth"
S1_REL_COL_ADDRESS_HOUSE_NAME = "RelationshipWithHouseName"
S1_REL_COL_ADDRESS_HOUSE_NUMBER = "RelationshipWithHouseNumber"
S1_REL_COL_ADDRESS_ROAD = "RelationshipWithRoad"
S1_REL_COL_ADDRESS_LOCALITY = "RelationshipWithLocality"
S1_REL_COL_ADDRESS_POST_TOWN = "RelationshipWithPostTown"
S1_REL_COL_ADDRESS_COUNTY = "RelationshipWithCounty"
S1_REL_COL_ADDRESS_POSTCODE = "RelationshipWithPostCode"
S1_REL_COL_ADDRESS_TELEPHONE = "RelationshipWithTelephone"
S1_REL_COL_ADDRESS_WORK_TELEPHONE = "RelationshipWithWorkTelephone"
S1_REL_COL_ADDRESS_MOBILE_TELEPHONE = "RelationshipWithMobileTelephone"
S1_REL_COL_ADDRESS_FAX = "RelationshipWithFax"
S1_REL_COL_ADDRESS_EMAIL = "RelationshipWithEmailAddress"
# Fields about the timing/nature of the relationship:
S1_REL_COL_DATE_ENDED = "DateEnded"
S1_REL_COL_REL_TYPE = "RelationshipType"
S1_REL_COL_GUARDIAN_PROXY = "PersonalGuardianOrProxy"
S1_REL_COL_NEXT_OF_KIN = "NextOfKin"
S1_REL_COL_CARER = "CaresForPatient"
S1_REL_COL_PRINCIPAL_CARER = "PrincipalCarerForPatient"
S1_REL_COL_KEYHOLDER = "KeyHolder"
S1_REL_COL_PARENTAL_RESPONSIBILITY = "HasParentalResponsibility"
S1_REL_COL_FINANCIAL_REP = "FinancialRepresentative"
S1_REL_COL_ADVOCATE = "Advocate"
S1_REL_COL_MAIN_VISITOR = "MainVisitor"
S1_REL_COL_CALLBACK_CONSENT = "CallCentreCallBackConsent"
S1_REL_COL_COPY_CORRESPONDENCE = "CopyCorrespondence"
S1_REL_COL_CONTACT_ORDER = "ContactOrder"
S1_REL_COL_CONTACT_METHOD = "ContactMethod"
S1_REL_COL_COMMS_FORMAT = "CommunicationFormat"
S1_REL_COL_INTERPRETER_REQUIRED = "InterpreterRequired"
# and things that are about the relative but not directly identifying:
S1_REL_COL_SEX = "RelationshipWithSex"
S1_REL_COL_LANGUAGE = "RelationshipWithSpokenLanguage"
S1_REL_COL_ORG = "RelationshipWithOrganisation"

# Columns in the HospitalAAndENumber table
S1_HOSPNUM_COL_HOSPNUM = "HospitalNumber"
S1_HOSPNUM_COL_COMMENTS = "Comments"

# Columns in the SafeguardingPersonAtRisk table
S1_SAFEGUARDING_P_AT_RISK_COL_NHSNUM = "NhsNumber"  # case different

# Other column names used by CPFT
CPFT_CLIENT_ID = "ClientID"
CPFT_REL_MOTHER_COL_NHSNUM = S1_PATIENT_COL_NHSNUM
CPFT_PATIENT_COL_MIDDLE_NAMES = "GivenName2"
CPFT_PATIENT_COL_DOB = "DOB"
CPFT_GENERIC_COL_NHSNUM2 = "NHSNumber2"
CPFT_GENERIC_COL_AGE_YEARS = "AgeInYears"
# ... usually "at the time of calculation, or death", i.e. unhelpful if you are
# unsure when the data was extracted; see stored procedure load_S1_Patient.
CPFT_GENERIC_COL_PATIENT_NAME = "PatientName"
CPFT_GENERIC_COL_NHSNUM_MOTHER = "CYPHS_NHSNumber_Mother"

S1_TO_CPFT_COLUMN_TRANSLATION = {
    # Where CPFT has renamed a column.
    # - Key: (core_tablename, colname) tuple.
    # - Value: new CPFT column name.
    (S1_TAB_PATIENT,
     S1_PATIENT_COL_MIDDLE_NAMES): CPFT_PATIENT_COL_MIDDLE_NAMES,
    (S1_TAB_PATIENT, S1_PATIENT_COL_DOB): CPFT_PATIENT_COL_DOB,
    (S1_TAB_RELATIONSHIPS,
     S1_REL_COL_RELATED_STAFFCODE_OR_RELNHSNUM): S1_PATIENT_COL_NHSNUM,
}


# -----------------------------------------------------------------------------
# Column collections
# -----------------------------------------------------------------------------

CORE_TO_CONTEXT_COLUMN_TRANSLATIONS = {
    # Key: destination context.
    # Value: translation dictionary -- see e.g. S1_TO_CPFT_COLUMN_TRANSLATION.
    SystmOneContext.TPP_SRE: {},
    SystmOneContext.CPFT_DW: S1_TO_CPFT_COLUMN_TRANSLATION,
}  # type: COLUMN_TRANSLATION_DICT_TYPE
CONTEXT_TO_CORE_CONTEXT_COLUMN_TRANSLATIONS = {
    SystmOneContext.TPP_SRE: {},
    SystmOneContext.CPFT_DW: _flip_coldict(S1_TO_CPFT_COLUMN_TRANSLATION)
}  # type: COLUMN_TRANSLATION_DICT_TYPE

S1_COLS_GENERIC_OK_UNMODIFIED = (
    S1_GENERIC_COL_DONE_AT,
    S1_GENERIC_COL_DONE_BY,
    S1_GENERIC_COL_EVENT_ID,
    S1_GENERIC_COL_EVENT_OCCURRED,
    S1_GENERIC_COL_EVENT_RECORDED,
    S1_GENERIC_COL_ORG,
    S1_GENERIC_COL_ORG_ID,
    S1_GENERIC_COL_ORG_REGISTERED_AT,
    S1_GENERIC_COL_RECORDED_BY,
)
S1_COLS_GENERIC_EXCLUDE = (
    # For when CPFT put identifiers all over the place. We can simply exclude
    # (rather than using them for scrubbing) since they are duplicates (for
    # convenience) of information in other tables like Patient,
    # PatientContactDetails, PatientAddressHistory.

    S1_PATIENT_COL_FORENAME,
    S1_PATIENT_COL_MIDDLE_NAMES,
    S1_PATIENT_COL_SURNAME,
    S1_PATIENT_COL_PREV_SURNAME,
    S1_PATIENT_COL_EMAIL,
    S1_PATIENT_COL_DOB,

    CPFT_GENERIC_COL_NHSNUM2,
    CPFT_PATIENT_COL_MIDDLE_NAMES,
    CPFT_PATIENT_COL_DOB,
    CPFT_GENERIC_COL_AGE_YEARS,
    # ... age when? Unhelpful. (And also, potentially leads to DOB discovery;
    # a blurred age near a birthday might be un-blurred by this.)
    CPFT_GENERIC_COL_PATIENT_NAME,

    S1_ADDRESS_COL_BUILDING_NAME,
    S1_ADDRESS_COL_BUILDING_NUMBER,
    S1_ADDRESS_COL_ROAD,
    S1_ADDRESS_COL_LOCALITY,
    S1_ADDRESS_COL_TOWN,
    S1_ADDRESS_COL_COUNTY,
    S1_ADDRESS_COL_POSTCODE,

    CPFT_ADDRESS_COL_POSTCODE_NOSPACE,

    S1_REL_COL_NAME,
    S1_REL_COL_DOB,
    S1_REL_COL_ADDRESS_HOUSE_NAME,
    S1_REL_COL_ADDRESS_HOUSE_NUMBER,
    S1_REL_COL_ADDRESS_ROAD,
    S1_REL_COL_ADDRESS_LOCALITY,
    S1_REL_COL_ADDRESS_POST_TOWN,
    S1_REL_COL_ADDRESS_COUNTY,
    S1_REL_COL_ADDRESS_POSTCODE,
    S1_REL_COL_ADDRESS_TELEPHONE,
    S1_REL_COL_ADDRESS_WORK_TELEPHONE,
    S1_REL_COL_ADDRESS_MOBILE_TELEPHONE,
    S1_REL_COL_ADDRESS_FAX,
    S1_REL_COL_ADDRESS_EMAIL,

    CPFT_GENERIC_COL_NHSNUM_MOTHER,

    S1_HOSPNUM_COL_HOSPNUM,  # just in case
)

S1_COLS_PATIENT_WORDS = (
    # Scrub as words.
    S1_PATIENT_COL_FORENAME,
    S1_PATIENT_COL_MIDDLE_NAMES,
    S1_PATIENT_COL_SURNAME,
    S1_PATIENT_COL_PREV_SURNAME,
    S1_PATIENT_COL_EMAIL,
    S1_PATIENT_COL_BIRTHPLACE,  # Unusual. But: scrub birthplace.
)
S1_COLS_REQUIRED_SCRUBBERS = (
    # Information that must be present in the master patient table.
    S1_GENERIC_COL_PK,  # likely redundant! It's the PID "definer".
    S1_PATIENT_COL_FORENAME,
    S1_PATIENT_COL_SURNAME,
    S1_PATIENT_COL_DOB,
)
S1_COLS_PATIENT_TABLE_OK_UNMODIFIED = S1_COLS_GENERIC_OK_UNMODIFIED + (
    # This list exists because we don't assume that things in the Patient table
    # are safe -- we assume they are unsafe, and let them through only if we
    # know about them. So we add "safe" things (that are not direct
    # identifiers) here.

    # S1_PATIENT_COL_TITLE,  # unnecessary -- and might be rare, e.g. Lord High Admiral  # noqa
    S1_PATIENT_COL_GENDER,
    S1_PATIENT_COL_SPEAKS_ENGLISH,
    S1_PATIENT_COL_SPINE_MATCHED,
    # Added by CPFT:
    "DeathIndicator",  # binary version (0 alive, 1 dead)
    "NationalDataOptOut",  # Added by CPFT (from NDOptOutPreference)?)
    # - CPFT also add "RwNo" (bigint), but it's always 1 here. See above.
    # - We ignore "AgeInYears" (added by CPFT) since that is dangerous and
    #   depends on when you ask.
)

S1_COLS_ADDRESS_PHRASES = (
    # Scrub as phrases.
    # - For S1_ADDRESS_COL_BUILDING_NAME, see below.
    # - For S1_ADDRESS_COL_BUILDING_NUMBER, see below.
    S1_ADDRESS_COL_ROAD,
    S1_ADDRESS_COL_LOCALITY,
    S1_ADDRESS_COL_TOWN,
    S1_ADDRESS_COL_COUNTY,
)
S1_COLS_ADDRESS_PHRASE_UNLESS_NUMBER = (
    S1_ADDRESS_COL_BUILDING_NAME,
    S1_ADDRESS_COL_BUILDING_NUMBER,
    # S1_ADDRESS_COL_BUILDING_NUMBER poses a new problem for us: this is meant
    # to be e.g. "5", which is by itself non-identifying and would be a big
    # problem if we scrub (consider e.g. "5 mg"). However, sometimes it is "5
    # Tree Road", because it's not forced to be numeric. So we extend CRATE
    # (2021-12-01) to add ScrubMethod.PHRASE_UNLESS_NUMERIC.
    # (S1_ADDRESS_COL_BUILDING_NAME occasionally contains numbers only, so we
    # do the same thing.)
)

S1_COLS_RELATIONSHIP_XREF_ID = (
    # Scrub (third-party) as full cross-references to another record.
    S1_REL_COL_RELATED_ID_DEPRECATED,
    S1_REL_COL_RELATED_ID,
)
S1_COLS_RELATIONSHIP_WORDS = (
    # Scrub (third-party) as words.
    S1_REL_COL_NAME,
    S1_REL_COL_ADDRESS_EMAIL,
    # Added by CPFT:
    "Surname",  # surname of relative
    "FirstName",  # surname of relative
)
S1_COLS_RELATIONSHIP_DATES = (
    # Scrub (third-party) as dates.
    S1_REL_COL_DOB,
    # Added by CPFT:
    "DOB",  # likely duplicate of S1_REL_COL_DOB
)
S1_COLS_RELATIONSHIP_PHRASES = (
    # Scrub (third-party) as phrases.
    # Same principles as for the patient address, above.
    # - For S1_REL_COL_ADDRESS_HOUSE_NAME, see below.
    # - For S1_REL_COL_ADDRESS_HOUSE_NUMBER, see below.
    S1_REL_COL_ADDRESS_ROAD,
    S1_REL_COL_ADDRESS_LOCALITY,
    S1_REL_COL_ADDRESS_POST_TOWN,
    S1_REL_COL_ADDRESS_COUNTY,
)
S1_COLS_RELATIONSHIP_PHRASE_UNLESS_NUMERIC = (
    S1_REL_COL_ADDRESS_HOUSE_NAME,
    S1_REL_COL_ADDRESS_HOUSE_NUMBER,
)
S1_COLS_RELATIONSHIP_CODES = (
    # Scrub (third-party) as codes.
    S1_REL_COL_ADDRESS_POSTCODE,
)
S1_COLS_RELATIONSHIP_NUMBERS = (
    # Scrub (third-party) as numbers.
    S1_REL_COL_RELATED_STAFFCODE_OR_RELNHSNUM,
    S1_REL_COL_ADDRESS_TELEPHONE,
    S1_REL_COL_ADDRESS_WORK_TELEPHONE,
    S1_REL_COL_ADDRESS_MOBILE_TELEPHONE,
    S1_REL_COL_ADDRESS_FAX,
)
S1_COLS_RELATIONSHIP_OK_UNMODIFIED = (
    S1_REL_COL_DATE_ENDED,
    S1_REL_COL_REL_TYPE,
    S1_REL_COL_GUARDIAN_PROXY,
    S1_REL_COL_NEXT_OF_KIN,
    S1_REL_COL_CARER,
    S1_REL_COL_PRINCIPAL_CARER,
    S1_REL_COL_KEYHOLDER,
    S1_REL_COL_PARENTAL_RESPONSIBILITY,
    S1_REL_COL_FINANCIAL_REP,
    S1_REL_COL_ADVOCATE,
    S1_REL_COL_MAIN_VISITOR,
    S1_REL_COL_CALLBACK_CONSENT,
    S1_REL_COL_COPY_CORRESPONDENCE,
    S1_REL_COL_CONTACT_ORDER,
    S1_REL_COL_CONTACT_METHOD,
    S1_REL_COL_COMMS_FORMAT,
    S1_REL_COL_INTERPRETER_REQUIRED,
    S1_REL_COL_SEX,
    S1_REL_COL_LANGUAGE,
    S1_REL_COL_ORG,
    # Added by CPFT:
    "DateDeath",  # date of death of relative
)

CPFT_REL_MOTHER_OK_UNMODIFIED = ()

OMIT_TABLENAME_COLNAME_PAIRS = (
    # Other specific fields to omit.
    ("Contacts", "ContactWith"),
    (S1_TAB_HOSP_AE_NUMBERS, S1_HOSPNUM_COL_COMMENTS),
    ("OohAction", "Details"),  # Out-of-hours calls; details can sometimes contain phone numbers  # noqa
    ("OohThirdPartyCall", "Contact"),  # free text
    ("SafeguardingIncidentDetails", "PoliceReference"),
)

FREETEXT_TABLENAME_COLNAME_PAIRS = (
    ("FreeText", "FreeText"),  # the bulk of free text; VARCHAR(MAX)
    ("PersonAtRisk", "ReasonForPlan"),  # free text re safeguarding
    ("ReferralIn", "PrimaryReason"),  # only 200 chars; may be OK
    ("SafeguardingAllegationDetails", "Outcome"),  # only 100 chars; ?OK
    ("SpecialNotes", "Note"),  # 8000 char free text
)
EXTRA_STANDARD_INDEX_TABLENAME_COLNAME_PAIRS = (
    # S1_Patient.IDPatient: Added by CPFT. Duplicate of RowIdentifier.
    # But likely to be used by researchers, so should be indexed.
    (S1_TAB_PATIENT, S1_GENERIC_COL_PID),
)


# =============================================================================
# Output
# =============================================================================

_warned = set()  # type: Set[str]


def warn_once(msg: str) -> None:
    """
    Warns the user once only.
    """
    global _warned
    if msg not in _warned:
        log.warning(msg)
        _warned.add(msg)


# =============================================================================
# String comparison helper functions
# =============================================================================

# -----------------------------------------------------------------------------
# Plain strings
# -----------------------------------------------------------------------------

def eq(x: str, y: str) -> bool:
    """
    Case-insensitive string comparison.
    """
    return x.lower() == y.lower()


def tcmatch(table1: str, column1: str,
            table2: str, column2: str) -> bool:
    """
    Equal (in case-insensitive fashion) for table and column?
    """
    return eq(table1, table2) and eq(column1, column2)


def is_in(x: str, y: Iterable[str]) -> bool:
    """
    Case-insensitive version of "in", to replace "if x in y".
    """
    return any(eq(x, test) for test in y)


def is_pair_in(a: str, b: str, y: Iterable[Tuple[str, str]]) -> bool:
    """
    Case-insensitive version of "in", to replace "if a, b in y".
    """
    return any(
        eq(a, test_a) and eq(b, test_b)
        for test_a, test_b in y
    )


# -----------------------------------------------------------------------------
# Regular expressions
# -----------------------------------------------------------------------------

def eq_re(x: str, y_regex: str) -> bool:
    """
    Returns True if the regex matches at the start of the string.
    """
    return bool(re.match(y_regex, x, flags=re.IGNORECASE))


def is_in_re(x: str, y_regexes: Iterable[str]) -> bool:
    """
    Case-insensitive regex-based version of "in", to replace "if x in y".
    """
    return any(eq_re(x, test) for test in y_regexes)


# =============================================================================
# Table/column name interpretation
# =============================================================================

def tablename_prefix(context: SystmOneContext) -> str:
    """
    The tablename prefix in the given context.
    """
    try:
        return TABLE_PREFIXES[context]
    except KeyError:
        raise KeyError(f"Unknown SystmOne context: {context}")


def core_tablename(tablename: str,
                   from_context: SystmOneContext,
                   allow_unprefixed: bool = False) -> str:
    """
    Is this a table of an expected format that we will consider?
    - If so, returns the "core" part of the tablename, in the given context.
    - Otherwise, if ``allow_unprefixed`` return the input.
    - Otherwise, return an empty string.
    """
    prefix = tablename_prefix(from_context)
    if not tablename.startswith(prefix):
        warn_once(f"Unrecognized table name style: {tablename}")
        if allow_unprefixed:
            return tablename
        else:
            return ""
    rest = tablename[len(prefix):]
    if not rest:
        raise ValueError(f"Table name {tablename!r} only contains its prefix")
    xlate = CONTEXT_TO_CORE_TABLE_TRANSLATIONS[from_context]
    return xlate.get(rest) or rest


def contextual_tablename(tablename_core: str,
                         to_context: SystmOneContext) -> str:
    """
    Prefixes the "core" table name for a given context, and sometimes
    translates it too.
    """
    prefix = tablename_prefix(to_context)
    xlate = CORE_TO_CONTEXT_TABLE_TRANSLATIONS[to_context]
    translated = xlate.get(tablename_core)
    tablename = translated if translated else tablename_core
    return f"{prefix}{tablename}"


def core_columnname(tablename_core: str,
                    columnname_context: str,
                    from_context: SystmOneContext) -> str:
    """
    Some contexts rename their column names. This function puts them back into
    the "core" (TPP SRE) name space.
    """
    xlate = CONTEXT_TO_CORE_CONTEXT_COLUMN_TRANSLATIONS[from_context]
    return (
        xlate.get((tablename_core, columnname_context))
        or columnname_context
    )


def contextual_columnname(tablename_core: str,
                          columname_core: str,
                          to_context: SystmOneContext) -> str:
    """
    Translates a "core" column name to its contextual variant, if applicable.
    """
    xlate = CORE_TO_CONTEXT_COLUMN_TRANSLATIONS[to_context]
    return (
        xlate.get((tablename_core, columname_core))
        or columname_core
    )


# =============================================================================
# Helper classes
# =============================================================================

class SystmOneSRESpecRow:
    """
    Represents a row in the SystmOne SRE specification CSV file.
    """
    def __init__(self, d: Dict[str, Any]) -> None:
        """
        Initialize with a row dictionary from a :class:`csv.DictReader`.
        """
        self.table_name = d["TableName"]  # type: str
        self.table_description = d["TableDescription"]  # type: str
        self.column_name = d["ColumnName"]  # type: str
        self.column_description = d["ColumnDescription"]  # type: str
        self.column_data_type = d["ColumnDataType"]  # type: str
        _col_length = d["ColumnLength"]
        self.column_length = int(_col_length) if _col_length else None
        _date_def = d["DateDefining"]  # type: str
        if _date_def == "Yes":
            self.date_defining = True
        elif _date_def == "No":
            self.date_defining = False
        else:
            raise ValueError(f"Bad DateDefining field: {_date_def!r}")
        self.column_ordinal = int(d["ColumnOrdinal"])
        self.linked_table = d["LinkedTable"]  # type: str
        self.linked_column_1 = d["LinkedColumn1"]  # type: str
        self.linked_column_2 = d["LinkedColumn2"]  # type: str

    @property
    def tablename_core(self) -> str:
        """
        Core part of the tablename.
        """
        return core_tablename(self.table_name,
                              from_context=SystmOneContext.TPP_SRE)

    @property
    def linked_table_core(self) -> str:
        """
        Core part of the linked table name.
        """
        return core_tablename(self.linked_table,
                              from_context=SystmOneContext.TPP_SRE)

    def comment(self, context: SystmOneContext) -> str:
        """
        Used to generate a comment for the CRATE data dictionary.
        """
        elements = [
            f"TABLE: {self.table_description}",
            f"COLUMN: {self.column_description}"
        ]
        if self.linked_table:
            context_prefix = tablename_prefix(context)
            linked_table_ctx = f"{context_prefix}{self.linked_table_core}"
            links = []  # type: List[str]
            if self.linked_column_1:
                links.append(f"FOREIGN KEY TO "
                             f"{linked_table_ctx}.{self.linked_column_1}")
            if self.linked_column_2:
                links.append(f"WITH {linked_table_ctx}.{self.linked_column_2}")
            elements.append(" ".join(links))
        return COMMENT_SEP.join(elements)

    def description(self, context: SystmOneContext) -> str:
        """
        Full description line.
        """
        tname = contextual_tablename(self.tablename_core, context)
        cname = contextual_columnname(self.tablename_core, self.column_name,
                                      context)
        elements = [f"{tname}.{cname}", self.comment(context)]
        return COMMENT_SEP.join(elements)

    # def matches(self, tablename_core: str, colname: str) -> bool:
    #     """
    #     Does this match a table/column name pair?
    #     """
    #     return (
    #         eq(self.tablename_core, tablename_core)
    #         and eq(self.column_name, colname)
    #     )


@dataclass
class ScrubSrcAlterMethodInfo:
    """
    For describing scrub-source and alter-method information.
    """
    change_comment_only: bool = False
    src_flags: str = ""
    scrub_src: Optional[ScrubSrc] = None
    scrub_method: Optional[ScrubMethod] = None
    decision: Decision = Decision.OMIT
    alter_methods: List[AlterMethod] = field(default_factory=list)
    dest_datatype: str = None

    def __post_init__(self) -> None:
        """
        Validation.
        """
        for char in self.src_flags:
            assert any(char == enum.value for enum in SrcFlag)

    def add_src_flag(self, flag: SrcFlag) -> None:
        """
        Add a flag, if it doesn't exist already.
        """
        flagchar = flag.value
        if flagchar not in self.src_flags:
            self.src_flags += flagchar

    def add_alter_method(self, alter_method: AlterMethod) -> None:
        """
        Adds an alteration method.
        """
        self.alter_methods.append(alter_method)

    def include(self) -> None:
        """
        Sets the decision to "include".
        """
        self.decision = Decision.INCLUDE

    def omit(self) -> None:
        """
        Sets the decision to "omit".
        """
        self.decision = Decision.OMIT


# =============================================================================
# Feature detection
# =============================================================================

def is_master_patient_table(tablename: str) -> bool:
    """
    Is this the master patient table?
    """
    return eq(tablename, S1_TAB_PATIENT)


def is_pid(colname: str) -> bool:
    """
    Is this column the SystmOne primary patient identifier (PID)?

    This works for all tables EXCEPT the main "Patient" table, where the PK
    takes its place.
    """
    return eq(colname, S1_GENERIC_COL_PID)


def is_mpid(colname: str) -> bool:
    """
    Is this column the SystmOne primary patient identifier (PID)?
    """
    return eq(colname, S1_PATIENT_COL_NHSNUM)


def is_pk(colname: str) -> bool:
    """
    Is this a primary key (PK) column within its table?
    """
    return eq(colname, S1_GENERIC_COL_PK)


def is_free_text(tablename: str, colname: str) -> bool:
    """
    Is this a free-text field requiring scrubbing?

    Unusually, there is not very much free text, and it is mostly collated.
    (We haven't added binary support yet. Do we have the binary documents?)
    """
    return is_pair_in(tablename, colname, FREETEXT_TABLENAME_COLNAME_PAIRS)


# =============================================================================
# Deciding about columns
# =============================================================================

def process_generic_table_column(tablename: str,
                                 colname: str,
                                 ssi: ScrubSrcAlterMethodInfo,
                                 cfg: Config) -> bool:
    """
    Performs operations applicable to columns any SystmOne table, except a few
    very special ones like Patient. Modifies ssi in place.

    Returns: recognized and dealt with?
    """
    # ---------------------------------------------------------------------
    # Generic table
    # ---------------------------------------------------------------------
    if is_pk(colname):
        # PK for all tables.
        ssi.add_src_flag(SrcFlag.PK)
        ssi.add_src_flag(SrcFlag.ADD_SRC_HASH)
        ssi.include()

    elif is_pid(colname):
        # FK to Patient.RowIdentifier for all other patient-related tables.
        ssi.add_src_flag(SrcFlag.PRIMARY_PID)
        ssi.include()

    elif is_mpid(colname):
        # An NHS number in a random table. OK, as long as we hash it.
        ssi.add_src_flag(SrcFlag.MASTER_PID)
        ssi.include()

    elif is_free_text(tablename, colname):
        # Free text to be scrubbed.
        ssi.add_alter_method(AlterMethod(config=cfg, scrub=True))
        ssi.include()

    elif is_in(colname, S1_COLS_GENERIC_OK_UNMODIFIED):
        # Generic columns that are always OK (e.g. organization ID).
        ssi.include()

    elif is_in(colname, S1_COLS_GENERIC_EXCLUDE):
        # Columns that are never OK in a generic table, and are duplicated
        # direct identifiers (handled specially in the master patient ID table
        # etc.).
        ssi.omit()
        # ... likely redundant but that's not obvious within this function

    elif eq(colname, CPFT_CLIENT_ID):
        # Some tables blend in old (e.g. RiO) or other (e.g. PCMIS) patient
        # IDs. These need to be scrubbed out, but might not be PIDs.
        ssi.scrub_src = ScrubSrc.PATIENT
        ssi.scrub_method = ScrubMethod.CODE
        ssi.omit()
        # ... if there's not also an NHS number, this will be unhelpful, but
        # we can't hash this consistently (I don't think), or at least we
        # could, but it would likely be confusing since those patients are not
        # in the master index.

    else:
        # Unrecognized.
        return False

    return True


def get_scrub_alter_details(
        tablename: str,
        colname: str,
        cfg: Config,
        include_generic: bool = False) -> ScrubSrcAlterMethodInfo:
    """
    The main "thinking" function.

    Is this a sensitive field that should be used for scrubbing?
    Should it be modified in transit?

    Args:
        tablename:
            The "core" tablename being considered, without any prefix (e.g.
            "Patient", not "SRPatient" or "S1_Patient").
        colname:
            The database column name.
        cfg:
            A :class:`crate_anon.anonymise.config.Config` object.
        include_generic:
            Include all fields that are not known about by this code and
            treated specially? If False, the config file settings are used
            (which may omit or include). If True, all such fields are included.
    """
    ssi = ScrubSrcAlterMethodInfo(decision=Decision.OMIT)  # omit by default

    # -------------------------------------------------------------------------
    # Omit table entirely?
    # -------------------------------------------------------------------------
    if is_in(tablename, OMIT_TABLES) or is_in_re(tablename, OMIT_TABLES_REGEX):
        return ssi

    # -------------------------------------------------------------------------
    # Deal with the core patient table. Many details here.
    # -------------------------------------------------------------------------
    if eq(tablename, S1_TAB_PATIENT):
        if eq(colname, S1_GENERIC_COL_PK):
            # RowIdentifier: SystmOne patient ID in the master patient table.
            # Hash and scrub SystmOne IDs.
            ssi.add_src_flag(SrcFlag.PRIMARY_PID)  # automatically hashed
            ssi.add_src_flag(SrcFlag.DEFINES_PRIMARY_PIDS)
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.NUMERIC
            ssi.include()

        elif eq(colname, S1_GENERIC_COL_PID):
            # IDPatient: Added by CPFT to the master patient table?
            # Needs to be hashed. Is a duplicate of RowIdentifier.
            ssi.add_src_flag(SrcFlag.PRIMARY_PID)  # automatically hashed
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.NUMERIC
            ssi.include()

        elif is_mpid(colname):  # NHS number
            # Hash and scrub NHS numbers. (Present as a text field, but is
            # numeric.)
            ssi.add_src_flag(SrcFlag.MASTER_PID)  # automatically hashed
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.NUMERIC
            ssi.include()

        elif is_in(colname, S1_COLS_PATIENT_WORDS):
            # Scrub and omit all names.
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.WORDS

        elif eq(colname, S1_PATIENT_COL_DOB):
            # Truncate and scrub dates of birth.
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.DATE
            ssi.add_alter_method(AlterMethod(config=cfg, truncate_date=True))
            ssi.include()

        elif eq(colname, S1_PATIENT_COL_DOD):
            # Include dates of death.
            ssi.include()

        elif eq(colname, S1_PATIENT_COL_BIRTHPLACE):
            # Unusual. But: scrub birthplace.
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.WORDS

        elif eq(colname, S1_PATIENT_COL_TESTPATIENT):
            # Exclude test patients.
            ssi.add_src_flag(SrcFlag.OPT_OUT)
            ssi.include()

        elif eq(colname, S1_PATIENT_COL_SOCIAL_SERVICES_REF):
            # Scrub and omit Social Services ID (text).
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.CODE
            ssi.omit()  # just to be explicit

        elif is_in(colname, S1_COLS_PATIENT_TABLE_OK_UNMODIFIED):
            # These are OK.
            ssi.include()

        else:
            # If anything else is put into this table, it may be sensitive.
            pass  # omit anything else in the master patient table

        # Via a separate "if" statement:
        if is_in(colname, S1_COLS_REQUIRED_SCRUBBERS):
            ssi.add_src_flag(SrcFlag.REQUIRED_SCRUBBER)

        return ssi

    # -------------------------------------------------------------------------
    # Proceed for all other tables.
    # -------------------------------------------------------------------------
    handled = process_generic_table_column(tablename, colname, ssi, cfg)
    if handled:
        # Recognized and handled as a generic column.
        return ssi

    if eq(tablename, S1_TAB_ADDRESS):
        # ---------------------------------------------------------------------
        # Address table.
        # ---------------------------------------------------------------------
        if is_in(colname, S1_COLS_ADDRESS_PHRASES):
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.PHRASE

        elif is_in(colname, S1_COLS_ADDRESS_PHRASE_UNLESS_NUMBER):
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.PHRASE_UNLESS_NUMERIC

        elif eq(colname, S1_ADDRESS_COL_POSTCODE):
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.CODE

        else:
            # omit anything else in the address table, e.g.
            # CPFT_ADDRESS_COL_POSTCODE_NOSPACE
            pass

    elif eq(tablename, S1_TAB_CONTACT_DETAILS):
        # ---------------------------------------------------------------------
        # Contact details table.
        # ---------------------------------------------------------------------
        if eq(colname, S1_CONTACT_COL_NUMBER):
            # Could be patient; ?could be third party; mostly patient?
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.NUMERIC

        else:
            pass  # omit anything else in the contact details table

    elif eq(tablename, S1_TAB_RELATIONSHIPS):
        # ---------------------------------------------------------------------
        # Third-party (relationships) table.
        # ---------------------------------------------------------------------
        if is_in(colname, S1_COLS_RELATIONSHIP_XREF_ID):
            # "Go fetch that linked patient, and use their identity information
            # as a third-party scrubber for our index patient."
            ssi.scrub_src = ScrubSrc.THIRDPARTY_XREF_PID
            ssi.scrub_method = ScrubMethod.NUMERIC
            ssi.include()

        elif is_in(colname, S1_COLS_RELATIONSHIP_WORDS):
            ssi.scrub_src = ScrubSrc.THIRDPARTY
            ssi.scrub_method = ScrubMethod.WORDS

        elif is_in(colname, S1_COLS_RELATIONSHIP_DATES):
            ssi.scrub_src = ScrubSrc.THIRDPARTY
            ssi.scrub_method = ScrubMethod.DATE

        elif is_in(colname, S1_COLS_RELATIONSHIP_PHRASES):
            ssi.scrub_src = ScrubSrc.THIRDPARTY
            ssi.scrub_method = ScrubMethod.PHRASE

        elif is_in(colname, S1_COLS_RELATIONSHIP_PHRASE_UNLESS_NUMERIC):
            ssi.scrub_src = ScrubSrc.THIRDPARTY
            ssi.scrub_method = ScrubMethod.PHRASE_UNLESS_NUMERIC

        elif is_in(colname, S1_COLS_RELATIONSHIP_CODES):
            ssi.scrub_src = ScrubSrc.THIRDPARTY
            ssi.scrub_method = ScrubMethod.CODE

        elif is_in(colname, S1_COLS_RELATIONSHIP_NUMBERS):
            ssi.scrub_src = ScrubSrc.THIRDPARTY
            ssi.scrub_method = ScrubMethod.NUMERIC

        elif is_in(colname, S1_COLS_RELATIONSHIP_OK_UNMODIFIED):
            ssi.include()

        else:
            pass  # omit anything unknown in the relationship table

    elif eq(tablename, CPFT_TAB_REL_MOTHER):
        # ---------------------------------------------------------------------
        # A CPFT partial duplicate table: from the relationship table where
        # that relationship is "Mother".
        # ---------------------------------------------------------------------
        if is_in(colname, S1_COLS_RELATIONSHIP_XREF_ID):
            ssi.scrub_src = ScrubSrc.THIRDPARTY_XREF_PID
            ssi.scrub_method = ScrubMethod.NUMERIC
            ssi.include()

        elif eq(colname, CPFT_REL_MOTHER_COL_NHSNUM):
            # Likely a duplicate as a scrubber. But that's not a problem for
            # CRATE and this also marks it as something to remove.
            ssi.scrub_src = ScrubSrc.THIRDPARTY
            ssi.scrub_method = ScrubMethod.NUMERIC

        elif is_in(colname, CPFT_REL_MOTHER_OK_UNMODIFIED):
            ssi.include()

        else:
            pass  # omit anything unown

    elif tcmatch(tablename, colname,
                 S1_TAB_HOSP_AE_NUMBERS, S1_HOSPNUM_COL_HOSPNUM):
        # ---------------------------------------------------------------------
        # A hospital number.
        # ---------------------------------------------------------------------
        ssi.scrub_src = ScrubSrc.PATIENT
        ssi.scrub_method = ScrubMethod.CODE  # can contain text

    elif tcmatch(tablename, colname,
                 S1_TAB_SAFEGUARDING_PERSON_AT_RISK,
                 S1_SAFEGUARDING_P_AT_RISK_COL_NHSNUM):
        # ---------------------------------------------------------------------
        # Another person's NHS number.
        # ---------------------------------------------------------------------
        ssi.scrub_src = ScrubSrc.THIRDPARTY
        ssi.scrub_method = ScrubMethod.NUMERIC

    elif is_pair_in(tablename, colname, OMIT_TABLENAME_COLNAME_PAIRS):
        # ---------------------------------------------------------------------
        # A column to omit specifically.
        # ---------------------------------------------------------------------
        pass  # omit

    else:
        # ---------------------------------------------------------------------
        # A generic field in a generic table.
        # ---------------------------------------------------------------------
        if include_generic:
            ssi.include()
        else:
            # Don't change anything except the comment:
            ssi.change_comment_only = True

    return ssi


def get_index_flag(tablename: str, colname: str) -> Optional[IndexType]:
    """
    Should this be indexed? Returns an indexing flag, or ``None`` if it should
    not be indexed.
    """
    if is_free_text(tablename, colname):
        return IndexType.FULLTEXT
    elif (is_master_patient_table(tablename)
            and (is_pid(colname) or is_mpid(colname))):
        return IndexType.UNIQUE
    elif is_pid(colname) or is_pk(colname):
        return IndexType.NORMAL
    elif is_pair_in(tablename, colname,
                    EXTRA_STANDARD_INDEX_TABLENAME_COLNAME_PAIRS):
        return IndexType.NORMAL
    else:
        return None


# =============================================================================
# Modify a data dictionary row according to detected features
# =============================================================================

def annotate_systmone_dd_row(ddr: DataDictionaryRow,
                             context: SystmOneContext,
                             specifications: SRE_SPEC_TYPE,
                             append_comments: bool = False,
                             include_generic: bool = False,
                             allow_unprefixed_tables: bool = False) -> None:
    """
    Modifies (in place) a data dictionary row for SystmOne.

    Args:
        ddr:
            The data dictionary row to amend.
        context:
            The context from which SystmOne data is being extracted (e.g. the
            raw TPP Strategic Reporting Extract (SRE), or a local version
            processed into CPFT's Data Warehouse).
        specifications:
            Details of the TPP SRE specifications.
        append_comments:
            Append comments to any that were autogenerated, rather than
            replacing them. (If you use the SRE specifications, you may as well
            set this to False as the SRE specification comments are much
            better.)
        include_generic:
            Include all fields that are not known about by this code and
            treated specially? If False, the config file settings are used
            (which may omit or include). If True, all such fields are included.
        allow_unprefixed_tables:
            Permit tables that don't start with the expected contextual prefix?
            Discouraged; you may get odd tables and views.
    """
    tablename = core_tablename(ddr.src_table,
                               from_context=context,
                               allow_unprefixed=allow_unprefixed_tables)
    if not tablename:
        # It didn't have the right prefix and allow_unprefixed_tables is False.
        ddr.decision = Decision.OMIT
        return
    colname = core_columnname(tablename, ddr.src_field, from_context=context)

    debugmsg = f"Considering: {ddr.src_table}.{ddr.src_field}"
    if tablename != ddr.src_table or colname != ddr.src_field:
        debugmsg += f" [translated to 'core' version: {tablename}.{colname}]"
    log.debug(debugmsg)

    # Do our thinking
    ssi = get_scrub_alter_details(tablename, colname, ddr.config,
                                  include_generic=include_generic)

    if not ssi.change_comment_only:
        # Source information
        ddr.src_flags = ssi.src_flags
        ddr.scrub_src = ssi.scrub_src
        ddr.scrub_method = ssi.scrub_method

        # Output decision
        ddr.decision = ssi.decision

        # Alterations
        ddr.set_alter_methods_directly(ssi.alter_methods)

        # Destination
        if (SrcFlag.PRIMARY_PID.value in ssi.src_flags
                or SrcFlag.MASTER_PID.value in ssi.src_flags
                or SrcFlag.ADD_SRC_HASH.value in ssi.src_flags):
            ddr.dest_datatype = ddr.config.sqltype_encrypted_pid_as_sql

        # Indexing
        ddr.index = get_index_flag(tablename, colname)
        if SrcFlag.ADD_SRC_HASH.value in ssi.src_flags:
            ddr.index = IndexType.UNIQUE

    # Improve comment
    spec = specifications.get((tablename, colname))
    if spec:
        spec_comment = spec.comment(context)
        # If we have no new comment, leave the old one alone.
        if spec_comment:
            if append_comments:
                ddr.comment = COMMENT_SEP.join((ddr.comment or "",
                                                spec_comment))
            else:
                ddr.comment = spec_comment


# =============================================================================
# Read a SystmOne SRE specification CSV file
# =============================================================================

def read_systmone_sre_spec(filename: str) -> SRE_SPEC_TYPE:
    """
    Read a SystmOne SRE specification CSV file. This provides useful comments!
    The format is of a dictionary mapping (tablename, colname) tuples to
    SystmOneSRESpecRow objects.
    """
    specs = {}  # type: SRE_SPEC_TYPE
    with open(filename, "r") as f:
        reader = csv.DictReader(f)
        for rowdict in reader:
            s = SystmOneSRESpecRow(rowdict)
            tablename_colname_tuple = s.tablename_core, s.column_name
            specs[tablename_colname_tuple] = s
    return specs


# =============================================================================
# Modify a data dictionary
# =============================================================================

def modify_dd_for_systmone(dd: DataDictionary,
                           context: SystmOneContext,
                           sre_spec_csv_filename: str = "",
                           debug_specs: bool = False,
                           append_comments: bool = False,
                           include_generic: bool = False,
                           allow_unprefixed_tables: bool = False,
                           alter_loaded_rows: bool = False) -> None:
    """
    Modifies a data dictionary in place.

    Args:
        dd
            The data dictionary to amend.
        context:
            The context from which SystmOne data is being extracted (e.g. the
            raw TPP Strategic Reporting Extract (SRE), or a local version
            processed into CPFT's Data Warehouse).
        sre_spec_csv_filename:
            Optional filename for the TPP SRE specification file, in
            comma-separated value (CSV) format. If present, this will be used
            to add proper descriptive comments to all known fields. Highly
            recommended.
        debug_specs:
            Report the SRE specifications to the log.
        append_comments:
            Append comments to any that were autogenerated, rather than
            replacing them. (If you use the SRE specifications, you may as well
            set this to False as the SRE specification comments are much
            better.)
        include_generic:
            Include all fields that are not known about by this code and
            treated specially? If False, the config file settings are used
            (which may omit or include). If True, all such fields are included.
        allow_unprefixed_tables:
            Permit tables that don't start with the expected contextual prefix?
            Discouraged; you may get odd tables and views.
        alter_loaded_rows:
            Alter rows that were loaded from disk (not read from a database)?
            The default is to leave such rows untouched.
    """
    log.info(f"Modifying data dictionary for SystmOne. Context = {context}")
    specs = (
        read_systmone_sre_spec(sre_spec_csv_filename)
        if sre_spec_csv_filename else []
    )
    if debug_specs:
        specs_str = '\n'.join(spec.description(context) for spec in specs)
        log.debug(f"SystmOne specs:\n{specs_str}")
    for ddr in dd.rows:
        if ddr.from_file and not alter_loaded_rows:
            # Skip rows that were loaded from disk.
            continue
        annotate_systmone_dd_row(
            ddr=ddr,
            context=context,
            specifications=specs,
            append_comments=append_comments,
            include_generic=include_generic,
            allow_unprefixed_tables=allow_unprefixed_tables,
        )
    log.info("... done")
