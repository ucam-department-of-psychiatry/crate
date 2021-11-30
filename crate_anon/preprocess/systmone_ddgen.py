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

.. code-block:: none

    SRTable = 'SRAnsweredQuestionnaire'
    QuestionnaireName = 'CPFT Risk Assessment'


Key fields
----------

- ``IDPatient`` -- the SystmOne patient number, in all patient tables (PID,
  in CRATE terms).
- ``SRPatient.NHSNumber`` -- the NHS number (MPID, in CRATE terms).


CPFT copy
---------

This broadly follows the SRE, but is expanded. Differences:

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


# =============================================================================
# Imports
# =============================================================================

import csv
from dataclasses import dataclass, field
from enum import Enum
import logging
from typing import Any, Dict, List, Optional

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

# Tables ("core" tablename, without the SR/S1_/... prefix):
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
# Other tables whose name might suggest patient identifiers:
# - SRAddressBookEntry: institutional addresses only? (FK to this from
#   SRSafeguardingIncidentDetails, for example.) todo: check -- institutional addresses only?  # noqa
# - SRHospitalAdmissionAndDischarge, etc. -- no external identifiers linked to
#   HospitalAAndENumber, just SystmOne IDs.
# - SROohEmergencyCall -- no contact numbers.
# - SROohTransport -- very structured.
# - SROohVisit -- very structured.


# -----------------------------------------------------------------------------
# Column names
# -----------------------------------------------------------------------------

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

# Columns for free text:
S1_COL_FREETEXT = "FreeText"

# Columns in the Patient table:
S1_PATIENT_COL_MPID = "NHSNumber"
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

# Columns in the PatientContactDetails table:
S1_CONTACT_COL_NUMBER = "ContactNumber"

# Columns in the PatientRelationship table:
S1_REL_COL_RELATED_ID_DEPRECATED = "IDRelationshipWithPatient"  # replaced by IDPatientRelationshipWith  # noqa
S1_REL_COL_RELATED_ID = "IDPatientRelationshipWith"
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

# Columns in the HospitalAAndENumber table
S1_HOSPNUM_COL_HOSPNUM = "HospitalNumber"
S1_HOSPNUM_COL_COMMENTS = "Comments"

# Columns in the SafeguardingPersonAtRisk table
S1_SAFEGUARDING_P_AT_RISK_COL_NHSNUM = "NhsNumber"


# -----------------------------------------------------------------------------
# Table collections
# -----------------------------------------------------------------------------

OMIT_TABLES = (
    "NomisNumber",  # Prison NOMIS numbers
)


# -----------------------------------------------------------------------------
# Column collections
# -----------------------------------------------------------------------------

S1_COLS_GENERIC_OK = (
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
    S1_PATIENT_COL_FORENAME,
    S1_PATIENT_COL_SURNAME,
    S1_PATIENT_COL_DOB,
)
S1_COLS_PATIENT_TABLE_OK = S1_COLS_GENERIC_OK + (
    S1_PATIENT_COL_TITLE,
    S1_PATIENT_COL_GENDER,
    S1_PATIENT_COL_SPEAKS_ENGLISH,
    S1_PATIENT_COL_SPINE_MATCHED,
)

S1_COLS_ADDRESS_PHRASES = (
    # Scrub as phrases.
    S1_ADDRESS_COL_BUILDING_NAME,
    # not S1_ADDRESS_COL_BUILDING_NUMBER *** todo: check no text in this
    S1_ADDRESS_COL_ROAD,
    S1_ADDRESS_COL_LOCALITY,
    S1_ADDRESS_COL_TOWN,
    S1_ADDRESS_COL_COUNTY,
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
)
S1_COLS_RELATIONSHIP_DATES = (
    # Scrub (third-party) as dates.
    S1_REL_COL_DOB,
)
S1_COLS_RELATIONSHIP_PHRASES = (
    # Scrub (third-party) as phrases.
    S1_REL_COL_ADDRESS_HOUSE_NAME,
    # not S1_REL_COL_ADDRESS_HOUSE_NUMBER *** todo: check no text in this
    S1_REL_COL_ADDRESS_ROAD,
    S1_REL_COL_ADDRESS_LOCALITY,
    S1_REL_COL_ADDRESS_POST_TOWN,
    S1_REL_COL_ADDRESS_COUNTY,
)
S1_COLS_RELATIONSHIP_CODES = (
    # Scrub (third-party) as codes.
    S1_REL_COL_ADDRESS_POSTCODE,
)
S1_COLS_RELATIONSHIP_NUMBERS = (
    # Scrub (third-party) as numbers.
    S1_REL_COL_ADDRESS_TELEPHONE,
    S1_REL_COL_ADDRESS_WORK_TELEPHONE,
    S1_REL_COL_ADDRESS_MOBILE_TELEPHONE,
    S1_REL_COL_ADDRESS_FAX,
)

OMIT_TABLENAME_COLNAME_PAIRS = (
    # Other specific fields to omit.
    ("Contacts", "ContactWith"),
    (S1_TAB_HOSP_AE_NUMBERS, S1_HOSPNUM_COL_COMMENTS),
    ("OohAction", "Details"),  # Out-of-hours calls; details can sometimes contain phone numbers  # noqa
    ("OohThirdPartyCall", "Contact"),  # free text
    ("SafeguardingIncidentDetails", "PoliceReference"),
)

ALWAYS_FREETEXT_COLS = (
    S1_COL_FREETEXT,
)
FREETEXT_TABLENAME_COLNAME_PAIRS = (
    ("PersonAtRisk", "ReasonForPlan"),  # free-text re safeguarding
    ("ReferralIn", "PrimaryReason"),  # only 200 chars; may be OK
    ("SafeguardingAllegationDetails", "Outcome"),  # only 100 chars; ?OK
    ("SpecialNotes", "Note"),  # 8000 char free text
)


# =============================================================================
# Table name interpretation
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
                   context: SystmOneContext,
                   required: bool = True) -> str:
    """
    Is this a table of an expected format that we will consider? If so, returns
    the "core" part of the tablename, in the given context. If not, then if
    ``required`` is True, raise ``ValueError``; otherwise, return an empty
    string.
    """
    prefix = tablename_prefix(context)
    if not tablename.startswith(prefix):
        if not required:
            return ""
        raise ValueError(
            f"Table name {tablename!r} must start with {prefix!r}")
    rest = tablename[len(prefix):]
    if not rest:
        if not required:
            return ""
        raise ValueError(f"Table name {tablename!r} only contains its prefix")
    return rest


def contextual_tablename(tablename_core: str, context: SystmOneContext) -> str:
    """
    Prefixes the "core" table name for a given context.
    """
    prefix = tablename_prefix(context)
    return f"{prefix}{tablename_core}"


# =============================================================================
# Helper classes
# =============================================================================

class SystmOneSRESpecRow:
    """
    Represents a row in the SystmOne SRE specification CSV file.
    """
    def __init__(self, d: Dict[str, Any]) -> None:
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
        return core_tablename(self.table_name, SystmOneContext.TPP_SRE)

    @property
    def linked_table_core(self) -> str:
        """
        Core part of the tablename.
        """
        return core_tablename(self.linked_table, SystmOneContext.TPP_SRE)

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

    def line(self, context: SystmOneContext) -> str:
        """
        Full description line.
        """
        elements = [
            f"{contextual_tablename(self.tablename_core, context)}."
            f"{self.column_name}",
            self.comment(context)
        ]
        return COMMENT_SEP.join(elements)

    def matches(self, tablename_core: str, colname: str) -> bool:
        """
        Does this match a table/column name pair?
        """
        return (
            self.tablename_core == tablename_core and
            self.column_name == colname
        )


@dataclass
class ScrubSrcAlterMethodInfo:
    """
    For describing scrub-source and alter-method information.
    """
    src_flags: str = ""
    scrub_src: Optional[ScrubSrc] = None
    scrub_method: Optional[ScrubMethod] = None
    decision: Decision = Decision.OMIT
    alter_methods: List[AlterMethod] = field(default_factory=list)

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
    return tablename == S1_TAB_PATIENT


def is_pid(colname: str) -> bool:
    """
    Is this column the SystmOne primary patient identifier (PID)?

    This works for all tables EXCEPT the main "Patient" table, where the PK
    takes its place.
    """
    return colname == S1_GENERIC_COL_PID


def is_mpid(colname: str) -> bool:
    """
    Is this column the SystmOne primary patient identifier (PID)?
    """
    return colname == S1_PATIENT_COL_MPID


def is_pk(colname: str) -> bool:
    """
    Is this a primary key (PK) column within its table?
    """
    return colname == S1_GENERIC_COL_PK


def is_free_text(tablename: str, colname: str) -> bool:
    """
    Is this a free-text field requiring scrubbing?

    Unusually, there is not very much free text, and it is all collated.
    (We haven't added binary support yet. Do we have the binary documents?)
    """
    return (
        colname in ALWAYS_FREETEXT_COLS or
        (tablename, colname) in FREETEXT_TABLENAME_COLNAME_PAIRS
    )


def process_generic_table_column(colname: str,
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
        return True

    elif is_pid(colname):
        # FK to Patient.RowIdentifier for all other patient-related tables.
        ssi.add_src_flag(SrcFlag.PRIMARY_PID)
        ssi.include()
        return True

    elif colname == S1_COL_FREETEXT:
        # Free text to be scrubbed.
        ssi.add_alter_method(AlterMethod(config=cfg, scrub=True))
        ssi.include()
        return True

    elif colname in S1_COLS_GENERIC_OK:
        # Generic columns that are always OK (e.g. organization ID).
        ssi.include()
        return True

    return False


def get_scrub_alter_details(tablename: str,
                            colname: str,
                            cfg: Config) -> ScrubSrcAlterMethodInfo:
    """
    The main "thinking" function.

    Is this a sensitive field that should be used for scrubbing?
    Should it be modified in transit?
    """
    ssi = ScrubSrcAlterMethodInfo(decision=Decision.OMIT)  # omit by default

    # -------------------------------------------------------------------------
    # Omit table entirely?
    # -------------------------------------------------------------------------
    if tablename in OMIT_TABLES:
        return ssi

    # -------------------------------------------------------------------------
    # Deal with the core patient table. Many details here.
    # -------------------------------------------------------------------------
    if tablename == S1_TAB_PATIENT:
        if colname == S1_GENERIC_COL_PK:  # SystmOne patient ID.
            # Hash and scrub SystmOne IDs.
            ssi.add_src_flag(SrcFlag.PRIMARY_PID)  # automatically hashed
            ssi.add_src_flag(SrcFlag.DEFINES_PRIMARY_PIDS)
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

        elif colname in S1_COLS_PATIENT_WORDS:
            # Scrub and omit all names.
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.WORDS

        elif colname == S1_PATIENT_COL_DOB:
            # Truncate and scrub dates of birth.
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.DATE
            ssi.add_alter_method(AlterMethod(config=cfg, truncate_date=True))
            ssi.include()

        elif colname == S1_PATIENT_COL_DOD:
            # Include dates of death.
            ssi.include()

        elif colname == S1_PATIENT_COL_BIRTHPLACE:
            # Unusual. But: scrub birthplace.
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.WORDS

        elif colname == S1_PATIENT_COL_TESTPATIENT:
            # Exclude test patients.
            ssi.add_src_flag(SrcFlag.OPT_OUT)
            ssi.include()

        elif colname == S1_PATIENT_COL_SOCIAL_SERVICES_REF:
            # Scrub and omit Social Services ID (text).
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.CODE
            ssi.omit()  # just to be explicit

        elif colname in S1_COLS_PATIENT_TABLE_OK:
            # These are OK.
            ssi.include()

        # *** add national opt out flag

        else:
            # If anything else is put into this table, it may be sensitive.
            pass  # omit

        # In a separate "if" statement:
        if colname in S1_COLS_REQUIRED_SCRUBBERS:
            ssi.add_src_flag(SrcFlag.REQUIRED_SCRUBBER)

        return ssi

    # -------------------------------------------------------------------------
    # Proceed for all other tables.
    # -------------------------------------------------------------------------
    if process_generic_table_column(colname, ssi, cfg):
        # Recognized and handled as a generic column.
        return ssi

    if tablename == S1_TAB_ADDRESS:
        # ---------------------------------------------------------------------
        # Address table.
        # ---------------------------------------------------------------------
        if colname in S1_COLS_ADDRESS_PHRASES:
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.PHRASE

        elif colname == S1_ADDRESS_COL_POSTCODE:
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.CODE

        # todo: check re "NumberOfBuilding" -- if numeric, include so as to
        # avoid removing e.g. "7" everywhere; if text, we have a problem.

    elif tablename == S1_TAB_CONTACT_DETAILS:
        # ---------------------------------------------------------------------
        # Contact details table.
        # ---------------------------------------------------------------------
        if colname == S1_CONTACT_COL_NUMBER:
            # Could be patient; ?could be third party; mostly patient?
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.NUMERIC

    elif tablename == S1_TAB_RELATIONSHIPS:
        # ---------------------------------------------------------------------
        # Third-party (relationships) table.
        # ---------------------------------------------------------------------
        if colname in S1_COLS_RELATIONSHIP_XREF_ID:
            # "Go fetch that linked patient, and use their identity information
            # as a third-party scrubber for our index patient."
            ssi.scrub_src = ScrubSrc.THIRDPARTY_XREF_PID

        elif colname in S1_COLS_RELATIONSHIP_WORDS:
            ssi.scrub_src = ScrubSrc.THIRDPARTY
            ssi.scrub_method = ScrubMethod.WORDS

        elif colname in S1_COLS_RELATIONSHIP_DATES:
            ssi.scrub_src = ScrubSrc.THIRDPARTY
            ssi.scrub_method = ScrubMethod.DATE

        elif colname in S1_COLS_RELATIONSHIP_PHRASES:
            ssi.scrub_src = ScrubSrc.THIRDPARTY
            ssi.scrub_method = ScrubMethod.PHRASE

        elif colname in S1_COLS_RELATIONSHIP_CODES:
            ssi.scrub_src = ScrubSrc.THIRDPARTY
            ssi.scrub_method = ScrubMethod.CODE

        elif colname in S1_COLS_RELATIONSHIP_NUMBERS:
            ssi.scrub_src = ScrubSrc.THIRDPARTY
            ssi.scrub_method = ScrubMethod.NUMERIC

        else:
            # The rest are boolean flags (e.g. advocate? parental
            # responsibility?); those are useful.
            ssi.include()

    elif (tablename == S1_TAB_HOSP_AE_NUMBERS and
          colname == S1_HOSPNUM_COL_HOSPNUM):
        # ---------------------------------------------------------------------
        # A hospital number.
        # ---------------------------------------------------------------------
        ssi.scrub_src = ScrubSrc.PATIENT
        ssi.scrub_method = ScrubMethod.CODE  # can contain text

    elif (tablename == S1_TAB_SAFEGUARDING_PERSON_AT_RISK and
          colname == S1_SAFEGUARDING_P_AT_RISK_COL_NHSNUM):
        # ---------------------------------------------------------------------
        # Another person's NHS number.
        # ---------------------------------------------------------------------
        ssi.scrub_src = ScrubSrc.THIRDPARTY
        ssi.scrub_method = ScrubMethod.NUMERIC

    elif (tablename, colname) in OMIT_TABLENAME_COLNAME_PAIRS:
        # ---------------------------------------------------------------------
        # A column to omit specifically.
        # ---------------------------------------------------------------------
        pass  # omit

    else:
        # ---------------------------------------------------------------------
        # A generic field in a generic table.
        # ---------------------------------------------------------------------
        ssi.include()

    return ssi


def get_index_flag(tablename: str, colname: str) -> Optional[IndexType]:
    """
    Should this be indexed? Returns an indexing flag, or ``None`` if it should
    not be indexed.
    """
    if is_free_text(tablename, colname):
        return IndexType.FULLTEXT
    elif (is_master_patient_table(tablename) and
            (is_pid(colname) or is_mpid(colname))):
        return IndexType.UNIQUE
    elif is_pid(colname) or is_pk(colname):
        return IndexType.NORMAL
    else:
        return None


# =============================================================================
# Modify a data dictionary row according to detected features
# =============================================================================

def annotate_systmone_dd_row(ddr: DataDictionaryRow,
                             context: SystmOneContext,
                             specifications: List[SystmOneSRESpecRow]) -> None:
    """
    Modifies (in place) a data dictionary row for SystmOne.
    """
    tablename = core_tablename(ddr.src_table, context, required=False)
    # We proceed even if the table doesn't fit out scheme (in which case
    # tablename will contain an empty string). For example, our local team
    # might create a table with an inconsistent name, yet meeting the basic
    # structure of other SystmOne tables.
    colname = ddr.src_field
    log.debug(f"Considering: {ddr.src_table}.{colname}")

    # Do our thinking
    ssi = get_scrub_alter_details(tablename, colname, ddr.config)

    # Source information
    ddr.src_flags = ssi.src_flags
    ddr.scrub_src = ssi.scrub_src
    ddr.scrub_method = ssi.scrub_method

    # Output decision
    ddr.decision = ssi.decision

    # Alterations
    ddr.set_alter_methods_directly(ssi.alter_methods)

    # Indexing
    ddr.index = get_index_flag(tablename, colname)

    # Improve comment
    for spec in specifications:
        if spec.matches(tablename, colname):
            ddr.comment = COMMENT_SEP.join((
                ddr.comment or "",
                spec.comment(context)
            ))


# =============================================================================
# Read a SystmOne SRE specification CSV file
# =============================================================================

def read_systmone_sre_spec(filename: str) -> List[SystmOneSRESpecRow]:
    """
    Read a SystmOne SRE specification CSV file. This provides useful comments!
    """
    with open(filename, "r") as f:
        reader = csv.DictReader(f)
        specs = []  # type: List[SystmOneSRESpecRow]
        for rowdict in reader:
            specs.append(SystmOneSRESpecRow(rowdict))
        return specs


# =============================================================================
# Modify a data dictionary
# =============================================================================

def modify_dd_for_systmone(dd: DataDictionary,
                           context: SystmOneContext,
                           sre_spec_csv_filename: str = "",
                           debug_specs: bool = False) -> None:
    """
    Modifies a data dictionary in place.
    """
    specs = (
        read_systmone_sre_spec(sre_spec_csv_filename)
        if sre_spec_csv_filename else []
    )
    if debug_specs:
        specs_str = '\n'.join(spec.line(context) for spec in specs)
        log.debug(f"SystmOne specs:\n{specs_str}")
    for ddr in dd.rows:
        annotate_systmone_dd_row(ddr, context, specs)
