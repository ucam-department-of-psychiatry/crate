#!/usr/bin/env python

r"""
crate_anon/preprocess/systmone_ddgen.py

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

  - This has an IDPatient column; presumably presence indicates an active
    opt-out.

- Full text and binary:

  - [SR]Media -- contains filenames and some metadata
  - [SR]FreeText -- if supplied


Notable additional tables/columns in the CPFT environment
---------------------------------------------------------

- S1_FreeText -- this includes all answers to Questionnaires (linked via
  ``IDAnsweredQuestionnaire`` etc.). Comes from the "upgraded" SRE.

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

- There is a ``S1_Patient.NationalDataOptOut`` column (0 or 1).

- The local opt-out information appears in S1_ClinicalOutcome_ConsentResearch
  (as the OptOut field, a text field) but is clearer in
  S1_ClinicalOutcome_ConsentResearch_OptOutCheck, which only contains patients
  opting out and has:
  
  .. code-block:: none

    IDPatient = <ID_of_patient_opting_out>  
    SNOMEDCode = 1091881000000109
    CTV3Code = 'XaaDb'
    CTV3Text = 'Declined invitation to participate in research study'

  So for CPFT, we will autodetect this table/column
  (S1_ClinicalOutcome_ConsentResearch_OptOutCheck.SNOMEDCode) and the config
  file should contain:
  
  .. code-block:: ini
  
    optout_col_values = [1091881000000109]

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

- ``RwNo`` or ``RwNo_Patient`` is frequently used, typically via:

  .. code-block:: none

    SELECT
        -- stuff,
        ROW_NUMBER() OVER (
            PARTITION BY IDPatient
            ORDER BY DateEventRecorded DESC
        ) AS RwNo
    FROM
        -- somewhere
    WHERE
        RwNo = 1
    ;

    SELECT
        -- stuff,
        ROW_NUMBER() OVER (
            PARTITION BY IDPatient
            ORDER BY DateEvent DESC
        ) AS RwNo_Patient
    FROM
        -- somewhere
    ;

  ... in other words, picking the most recent for each patient (or, without
  the WHERE clause, showing its sequencing within each patient).


Manual review after first draft
-------------------------------

Reviewing CPFT de-identified output for patient-related content only (not
staff-related), per local ethics approvals.

.. code-block:: sql

    -- Tables in the de-identified database:
    SELECT table_name FROM information_schema.tables WHERE table_catalog = 'S1' ORDER BY table_name;

Reviewed and OK:

- S1_18WeekWait

Reviewed and tweaked and OK:

Tweaked and needs re-review:

- S1_3DayFollowUp (eliminate PatientAddress)
- S1_7DayFollowUp (eliminate PatientAddress, auto-rename NHSNumber to mrid)

To review:

- S1_Accommodation
- S1_ActivityEvent
- S1_ActivityEvent_DNA
- S1_ActivityEvent_EventDuration
- S1_AnsweredQuestionnaire
- S1_Appointments
- S1_AQ_CarePlan
- S1_AQ_CrisisPlan
- S1_AQ_CurrentView
- S1_AQ_HoNOSChildren
- S1_AQ_PhysicalHealthCheck_B1
- S1_AQ_PhysicalHealthCheck_B2
- S1_AQ_RiskAssessment
- S1_AQ_SafePlan
- S1_AQ_VTE
- S1_AssistiveTechnologyToSupportDisability
- S1_AuditLog
- S1_CarePlan
- S1_CarePlanDetail
- S1_CarePlanReview
- S1_CarerStatus
- S1_Caseload
- S1_Child_At_Risk
- S1_Child_Protection_Plan_Reason
- S1_ClinicalDashboard
- S1_ClinicalDashboard_Pulmonary
- S1_ClinicalDashboard_Pulmonary_Referrals
- S1_ClinicalMeasure_ACE_II
- S1_ClinicalMeasure_AlcoholUnitsWeek
- S1_ClinicalMeasure_BloodPressure
- S1_ClinicalMeasure_BloodPressure_Grouped
- S1_ClinicalMeasure_BloodTestDeclined
- S1_ClinicalMeasure_BMI
- S1_ClinicalMeasure_BodyWeight
- S1_ClinicalMeasure_CGAS
- S1_ClinicalMeasure_Cholesterol_HDL_Ratio
- S1_ClinicalMeasure_Cigarettes_Day
- S1_ClinicalMeasure_Exercise_MinsWeek
- S1_ClinicalMeasure_FruitVeg_Day
- S1_ClinicalMeasure_GlycatedHaemoglobin
- S1_ClinicalMeasure_NEWS_II
- S1_ClinicalMeasure_QRisk
- S1_ClinicalMeasure_QTcB_IntervalDuration
- S1_ClinicalMeasure_Rockwood
- S1_ClinicalMeasure_SWEMWBS
- S1_ClinicalMeasure_TotalCholesterol
- S1_ClinicalOutcome_7DFU_UnsuccessfulContact
- S1_ClinicalOutcome_AlcoholAdvice
- S1_ClinicalOutcome_CPA
- S1_ClinicalOutcome_MaritalStatus
- S1_ClinicalOutcome_MHCapacity
- S1_ClinicalOutcome_MilitaryServicesMember
- S1_ClinicalOutcome_NHS_Staff_LongCovid
- S1_ClinicalOutcome_Occupation
- S1_ClinicalOutcome_PhysicalHealthCheck_A1
- S1_ClinicalOutcome_Section58
- S1_ClinicalOutcome_SmokingAdvice
- S1_Clustering
- S1_Coded_Finding
- S1_Coded_Observations
- S1_Coded_Procedure
- S1_Coded_Scored_Assessment
- S1_Contacts
- S1_Contacts_CYP_PlanMetric_7
- S1_ContactsArchive
- S1_ContactsArchive_ClientSequence
- S1_ContactsArchive_ClientSequenceAttended
- S1_ContactsArchive_ClientSequenceAttendedFaceToFace
- S1_ContactsArchive_LatestStaffContact
- S1_ContactsArchive_NonLegalContacts
- S1_ContactsArchive_TotalsByReferral
- S1_CoronaVirus
- S1_CPA
- S1_CPACareCoordinator
- S1_CPAMentalHealthAssessment
- S1_CurrentInpatientDashboard_Doctors
- S1_CYPFRS_TelephoneTriage
- S1_CYPHS_502_Immunisation
- S1_Deaths
- S1_Demographics
- S1_Diagnosis
- S1_Disability
- S1_DisabilityImpactPerception
- S1_DischargeDelay
- S1_DischargeDelay_Fact
- S1_ECTCourse
- S1_ECTTreatment
- S1_eDSM
- S1_Employment
- S1_EuroQol
- S1_EuroQol_Comparison
- S1_Event
- S1_Falls_AtRiskState
- S1_Falls_AtRiskState_Comparison
- S1_FreeText
- S1_Goal
- S1_HealthyChildProgramme_DashboardExtractASQ3
- S1_HealthyChildProgramme_DashboardExtractASQ3_Trend
- S1_HealthyChildProgramme_DashboardExtractTwoPointFiveYearReview
- S1_HealthyChildProgramme_DashboardExtractTwoPointFiveYearReview_Trend
- S1_HealthyChildProgramme_DashboardExtractVisitType
- S1_HealthyChildProgramme_DashboardExtractVisitType_Trend
- S1_HealthyChildProgramme_Monitoring
- S1_HealthyChildProgramme_Monitoring_Trend
- S1_ICW_PTL
- S1_Immunisation
- S1_Inpatient_NorthwickParkIndex
- S1_InpatientAvailableBeds
- S1_InpatientBedClosure
- S1_InpatientBedStay
- S1_InpatientBedStay_Old
- S1_InpatientLeave
- S1_InpatientWardStay
- S1_LADSCYPHS_Output
- S1_LADSCYPQuestionnaires
- S1_Letter
- S1_MDT_Caseload
- S1_Medical_History_Previous_Diagnosis
- S1_MentalHealthAct_Awol
- S1_MentalHealthAct_ClientConsent
- S1_MentalHealthAct_ClientSection
- S1_MentalHealthAct_ClientSectionedBy
- S1_MentalHealthAct_ClientSectionRecall
- S1_MentalHealthAct_ClientSectionRightsExplained
- S1_MentalHealthAct_SectionAppeal
- S1_MentalHealthCarePlan
- S1_NDOptOutPreference
- S1_Newborn_Bloodspot_Congenital_Hyperthyroidism
- S1_Newborn_Bloodspot_Cystic_Fibrosis
- S1_Newborn_Bloodspot_Dehydrogenase_Deficiency
- S1_Newborn_Bloodspot_Glutaric_Aciduria_Type1
- S1_Newborn_Bloodspot_Homocystinuria
- S1_Newborn_Bloodspot_Isovaleric_Aciduria
- S1_Newborn_Bloodspot_Maple_Syrup_Urine
- S1_Newborn_Bloodspot_Phenylketonuria
- S1_Newborn_Bloodspot_SickleCell
- S1_NewbornHearingAudiologyOutcome
- S1_NewbornHearingScreeningOutcome
- S1_OutOfHours
- S1_OutOfHoursAction
- S1_OutOfHoursAssessment
- S1_OutOfHoursCaseOutcome
- S1_OutOfHoursSRCodeInformation
- S1_OverseasVisitorChargingCategory
- S1_Patient
- S1_PatientAddress
- S1_PatientAnsweredQuestionnaireInformation
- S1_PatientContact
- S1_PatientEthnicity
- S1_PatientGPPractice
- S1_PatientLanguageDeathOptions
- S1_PatientLetterInformation
- S1_PatientOverview
- S1_PatientRelationship
- S1_PatientRelationshipMother
- S1_PatientSRCodeInformation
- S1_PersonAtRisk
- S1_PhysicalHealthChecks
- S1_PRISM_ReReferral
- S1_Provisional_Diagnosis
- S1_QRisk
- S1_ReferralAllocation
- S1_ReferralAllocationStaff
- S1_ReferralInIntervention
- S1_ReferralInReferralReason
- S1_ReferralsIn
- S1_ReferralsOut
- S1_RestrictiveIntervention
- S1_RiskReview
- S1_SafeguardingCases
- S1_SafeguardingCaseStageQuestions
- S1_SafeguardingCaseStages
- S1_SafeguardingIncidentDetails
- S1_SafeguardingPersonAlleged
- S1_SafeguardingPersonAtRisk
- S1_SafeguardingVulnerabilityFactor
- S1_Secondary_Diagnosis
- S1_SessionNotes_CTV3Code
- S1_SessionNotes_Templates
- S1_SettledAccomodationIndicator
- S1_SpecialEducationalNeeds
- S1_StaffActivity
- S1_Team
- S1_TeamMember
- S1_Templates
- S1_Vanguard
- S1_Visit
- S1_WaitingList
- S1_WaitList_EatingDisorders
- S1_WardAttender
- S1_WorkingHours
- vwS1_OutOfHours
- vwS1_PatientAddressWithResearchGeography


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

# todo: SystmOne (CRATE traffic-light system): implement S1_ClinicalOutcome_ConsentResearch  # noqa

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
# from cardinal_pythonlib.sqlalchemy.schema import is_sqlatype_string

from crate_anon.anonymise.altermethod import AlterMethod
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

class S1Table:
    """
    SystmOne "core" table names, with no prefix.
    """
    PATIENT = "Patient"  # e.g. SRPatient (SRE), S1_Patient (CPFT)
    ADDRESS = "PatientAddressHistory"
    CONTACT_DETAILS = "PatientContactDetails"
    RELATIONSHIPS = "PatientRelationship"

    # Other tables starting "Patient":
    # - SRPatientContactProperty: seems not relevant; describes visits/diary
    #   events
    # - SRPatientGroups: e.g. to group patients in a residential home; also

    #   family, but contains no direct identifiers.
    # - SRPatientLeave: leave from hospital.
    # - SRPatientLocation: location within A&E departments, I think.
    # - SRPatientRegistration: registration status (and who did it); also their
    #   preferred pharmacy; but no direct identifiers.

    HOSP_AE_NUMBERS = "HospitalAAndENumber"
    MEDIA = "Media"  # todo: binary documents -- how?
    SAFEGUARDING_PERSON_AT_RISK = "SafeguardingPersonAtRisk"

    # See also OMIT_TABLENAME_COLNAME_PAIRS below.
    #
    # Other tables whose name might suggest patient identifiers:
    # - SRAddressBookEntry: institutional addresses only? (FK to this from
    #   SRSafeguardingIncidentDetails, for example.) todo: check -- institutional addresses only?  # noqa
    # - SRHospitalAdmissionAndDischarge, etc. -- no external identifiers linked
    #   to HospitalAAndENumber, just SystmOne IDs.
    # - SROohEmergencyCall -- no contact numbers.
    # - SROohTransport -- very structured.
    # - SROohVisit -- very structured.


class CPFTTable:
    """
    Selected tables that CPFT have renamed or created.
    """
    ADDRESS = "PatientAddress"
    CONTACT_DETAILS = "PatientContact"
    REL_MOTHER = "PatientRelationshipMother"
    CYP_FRS_TELEPHONE_TRIAGE = "CYPFRS_TelephoneTriage"


_S1_TO_CPFT_TABLE_TRANSLATION = {
    # Where CPFT has renamed a S1 SRE table directly.
    S1Table.ADDRESS: CPFTTable.ADDRESS,
    # ... i.e. CPFT have renamed SRPatientAddressHistory to S1_PatientAddress.
    S1Table.CONTACT_DETAILS: CPFTTable.CONTACT_DETAILS,
}


# -----------------------------------------------------------------------------
# Table collections
# -----------------------------------------------------------------------------
# Tables are referred to here by their "core" name, i.e. after removal of
# prefixes like "SR" or "S1_", if they have one.

_INCLUDE_TABLES_REGEX_S1 = ()
_INCLUDE_TABLES_REGEX_CPFT = (
    # Include even if --systmone_allow_unprefixed_tables is not used.
    "vw",  # views
)
INCLUDE_TABLES_REGEX = {
    SystmOneContext.TPP_SRE: _INCLUDE_TABLES_REGEX_S1,
    SystmOneContext.CPFT_DW: _INCLUDE_TABLES_REGEX_S1 + _INCLUDE_TABLES_REGEX_CPFT  # noqa
}

_OMIT_TABLES_S1 = (
    "NomisNumber",  # Prison NOMIS numbers
    "SafeguardingAllegationDetails",  # sensitive and no patient ID column

    # CPFT extras:
    "gr_workings",  # no idea
    "InpatientAvailableBeds",  # RowIdentifier very far from unique; ?no PK; no patient info  # noqa
)
_OMIT_TABLES_CPFT_EXTRAS = (
    # CPFT extras:
    "gr_workings",  # no idea
    "InpatientAvailableBeds",  # RowIdentifier very far from unique; ?no PK; no patient info  # noqa
)
OMIT_TABLES = {
    SystmOneContext.TPP_SRE: _OMIT_TABLES_S1,
    SystmOneContext.CPFT_DW: _OMIT_TABLES_S1 + _OMIT_TABLES_CPFT_EXTRAS
}

_OMIT_TABLES_REGEX_S1 = ()
_OMIT_TABLES_REGEX_CPFT = (
    # CPFT extras:

    "AuditLog",  # may have gone now! Was there for a while. Not relevant.
    # todo: *** check gone

    # KEPT: ClinicalOutcome_NHS_Staff_LongCovid.
    # This one filters for CTV3 codes Y2c49 and Y2ca. As d/w NP 2021-12-14:
    # - These are "local" codes.
    #   ("Official" Read codes have been frozen since 2016, according to
    #   https://datadictionary.nhs.uk/supporting_information/read_coded_clinical_terms.html.)  # noqa
    # - They indicate whether or not someone is a healthcare worker (HCW).
    # - Introduced for COVID-19, since HCW status was a clear risk factor for
    #   infection.
    # - No detail suggesting identification (and they don't indicate e.g.
    #   membership of a specific Trust, or a specific job role).

    "Inpatients",
    # S1_Inpatients, S1_Inpatients_20201020: current inpatients -- but these
    # tables have NHSNumber as FLOAT. Exclude them.
    # todo: *** check gone

    "Mortality",  # includes S1_Mortality, S1_MortalityAdditionalInfo
    # These contain (a) age (rather than DOB) information, and (b) information
    # from multiple systems -- some risk of including RiO patients with
    # coincidentally the same ClientID as a SystmOne IDPatient, unless
    # filtered, and is derived information anyway -- for now, we'll omit.
    # todo: *** check gone

    "ReferralsOpen$",
    # This CPFT table is a non-patient table (but with potentially identifiable
    # information about referral reason? -- maybe not) -- skip it.
    # todo: *** check gone

    "WaitList_",  # S1_Waitlist_*
    # Waiting list tables use a confusing blend of SystmOne "IDPatient" and
    # RiO "ClientID" columns, and it's not clear they add much.
    # todo: *** check gone

    "UserSmartCard",
    # Not relevant clinically.
    # todo: *** check gone

    # I considered excluding "vw.*" (views) and "zzz.*" (scratch tables) here,
    # but the user has the option to exclude all such tables via
    # --systmone_allow_unprefixed_tables if they desire. Views may be useful;
    # see also INCLUDE_TABLES_REGEX above. However, "zz" or "zzz" tables in
    # CPFT are scratch tables that should not be used:
    "zz",

    # Some have suffixes e.g. "S1_ReferralsIn_20200917", i.e. end with an
    # underscore then 8 digits. These are temporary copies that we should not
    # use. Some have more after that date.
    r".*_\d{8}",
)
OMIT_TABLES_REGEX = {
    SystmOneContext.TPP_SRE: _OMIT_TABLES_REGEX_S1,
    SystmOneContext.CPFT_DW: _OMIT_TABLES_REGEX_S1 + _OMIT_TABLES_REGEX_CPFT
}

CORE_TO_CONTEXT_TABLE_TRANSLATIONS = {
    # Key: destination context.
    # Value: translation dictionary, mapping "core" tablename to target.
    # Absent values lead to no translation.
    SystmOneContext.TPP_SRE: {},
    SystmOneContext.CPFT_DW: _S1_TO_CPFT_TABLE_TRANSLATION,
}  # type: TABLE_TRANSLATION_DICT_TYPE
CONTEXT_TO_CORE_TABLE_TRANSLATIONS = {
    SystmOneContext.TPP_SRE: {},
    SystmOneContext.CPFT_DW: reversedict(_S1_TO_CPFT_TABLE_TRANSLATION),
}  # type: TABLE_TRANSLATION_DICT_TYPE


# -----------------------------------------------------------------------------
# Column names
# -----------------------------------------------------------------------------
# We work internally with TPP SRE column names. Any renaming (e.g. in CPFT) is
# explicitly noted.

class S1GenericCol:
    """
    Columns used in many SystmOne tables.
    """
    EVENT_ID = "IDEvent"  # FK to SREvent.RowIdentifier
    EVENT_OCCURRED_WHEN = "DateEvent"  # when event happened
    EVENT_RECORDED_WHEN = "DateEventRecorded"  # when event recorded
    ORG_ID_DONE_AT = "IDOrganisationDoneAt"  # FK to SROrganisation.ID
    ORG_ID_ENTERED_AT = "IDOrganisation"  # org at which the data was entered
    ORG_ID_VISIBLE_TO = "IDOrganisationVisibleTo"  # FK to SROrganisation.ID
    ORG_REGISTERED_AT = "IDOrganisationRegisteredAt"  # org where the patient was registered when the data was entered  # noqa
    PATIENT_ID = "IDPatient"  # FK to SRPatient.RowIdentifier
    PK = "RowIdentifier"  # PK for nearly all SystmOne original tables
    QUESTIONNAIRE_ID = "IDAnsweredQuestionnaire"  # FK to SRAnsweredQuestionnaire.RowIdentifier  # noqa
    REFERRAL_ID = "IDReferralIn"  # FK to SRReferralIn.RowIdentifier  # noqa
    STAFF_ID_DONE_BY = "IDDoneBy"  # FK to SRStaffMember.RowIdentifier
    STAFF_PROFILE_ID_RECORDED_BY = "IDProfileEnteredBy"  # FK to SRStaffMemberProfile.RowIdentifier  # noqa


class CPFTGenericCol:
    """"
    CPFT variants for generic column names.
    """
    AGE_YEARS = "AgeInYears"
    # ... usually "at the time of calculation, or death", i.e. unhelpful if you
    # are unsure when the data was extracted; see stored procedure
    # load_S1_Patient.
    ASSIGNMENT_NUMBER = "AssignmentNumber"
    # ... payroll number of member of staff, I think -- too sensitive and I am
    # surprised it is there in the first place.
    HOME_CONTACT_NUMBER = "HomeContactNumber"  # *** todo: check gone from Demographics  # noqa
    MOBILE_CONTACT_NUMBER = "MobileContactNumber"  # *** todo: check gone from Demographics  # noqa
    NHSNUM2 = "NHSNumber2"
    NHSNUM_MOTHER = "CYPHS_NHSNumber_Mother"
    PATIENT_ADDRESS = "PatientAddress"
    PATIENT_NAME = "PatientName"
    POSTCODE = "PostCode"
    PATIENT_ID_SYNONYM_1 = "Patient_ID"


class S1PatientCol:
    """
    Columns in the Patient table.
    """
    PK = S1GenericCol.PK  # RowIdentifier
    NHSNUM = "NHSNumber"
    TITLE = "Title"
    FORENAME = "FirstName"
    MIDDLE_NAMES = "MiddleNames"
    SURNAME = "Surname"
    PREV_SURNAME = "PreviousSurname"
    EMAIL = "EmailAddress"
    DOB = "DateBirth"
    DOD = "DateDeath"
    BIRTHPLACE = "BirthPlace"
    GENDER = "Gender"
    SPEAKS_ENGLISH = "SpeaksEnglish"  # curious that this is a specific flag
    TESTPATIENT = "TestPatient"
    SOCIAL_SERVICES_REF = "SSRef"
    SPINE_MATCHED = "SpineMatched"


class CPFTPatientCol:
    """
    CPFT variants for the patient table.
    """
    MIDDLE_NAMES = "GivenName2"
    DOB = "DOB"


class S1AddressCol:
    """
    Columns in the PatientAddressHistory table.
    """
    BUILDING_NAME = "NameOfBuilding"
    BUILDING_NUMBER = "NumberOfBuilding"
    ROAD = "NameOfRoad"
    LOCALITY = "NameOfLocality"
    TOWN = "NameOfTown"
    COUNTY = "NameOfCounty"
    POSTCODE = "FullPostCode"


class CPFTAddressCol:
    """
    CPFT variants for the address table.
    """
    POSTCODE_NOSPACE = "PostCode_NoSpaces"


class S1ContactCol:
    """
    Columns in the PatientContactDetails table.
    """
    NUMBER = "ContactNumber"


class S1RelCol:
    """
    Columns in the PatientRelationship table.
    (This is also one for which we specify everything in detail, since CPFT add
    in extra identifiers.)
    """
    RELATED_ID_DEPRECATED = "IDRelationshipWithPatient"
    # ... replaced by IDPatientRelationshipWith
    RELATED_ID = "IDPatientRelationshipWith"
    RELATED_STAFFCODE_OR_RELNHSNUM = "CodeRelationshipWithUser"
    # ... SRE help says "The ODS code for the staff member the relationship is
    # with". However, it seems that it sometimes contains the NHS number of the
    # relative (certainly an NHS number that differs from the patient's!).
    NAME = "RelationshipWithName"
    DOB = "RelationshipWithDateOfBirth"
    ADDRESS_HOUSE_NAME = "RelationshipWithHouseName"
    ADDRESS_HOUSE_NUMBER = "RelationshipWithHouseNumber"
    ADDRESS_ROAD = "RelationshipWithRoad"
    ADDRESS_LOCALITY = "RelationshipWithLocality"
    ADDRESS_POST_TOWN = "RelationshipWithPostTown"
    ADDRESS_COUNTY = "RelationshipWithCounty"
    ADDRESS_POSTCODE = "RelationshipWithPostCode"
    ADDRESS_TELEPHONE = "RelationshipWithTelephone"
    ADDRESS_WORK_TELEPHONE = "RelationshipWithWorkTelephone"
    ADDRESS_MOBILE_TELEPHONE = "RelationshipWithMobileTelephone"
    ADDRESS_FAX = "RelationshipWithFax"
    ADDRESS_EMAIL = "RelationshipWithEmailAddress"
    # Fields about the timing/nature of the relationship:
    DATE_ENDED = "DateEnded"
    REL_TYPE = "RelationshipType"
    GUARDIAN_PROXY = "PersonalGuardianOrProxy"
    NEXT_OF_KIN = "NextOfKin"
    CARER = "CaresForPatient"
    PRINCIPAL_CARER = "PrincipalCarerForPatient"
    KEYHOLDER = "KeyHolder"
    PARENTAL_RESPONSIBILITY = "HasParentalResponsibility"
    FINANCIAL_REP = "FinancialRepresentative"
    ADVOCATE = "Advocate"
    MAIN_VISITOR = "MainVisitor"
    CALLBACK_CONSENT = "CallCentreCallBackConsent"
    COPY_CORRESPONDENCE = "CopyCorrespondence"
    CONTACT_ORDER = "ContactOrder"
    CONTACT_METHOD = "ContactMethod"
    COMMS_FORMAT = "CommunicationFormat"
    INTERPRETER_REQUIRED = "InterpreterRequired"
    # and things that are about the relative but not directly identifying:
    SEX = "RelationshipWithSex"
    LANGUAGE = "RelationshipWithSpokenLanguage"
    ORG = "RelationshipWithOrganisation"


class CPFTOtherCol:
    """
    Other CPFT variants.
    """
    REL_MOTHER_COL_NHSNUM = S1PatientCol.NHSNUM


class S1HospNumCol:
    """
    Columns in the HospitalAAndENumber table.
    """
    HOSPNUM = "HospitalNumber"
    COMMENTS = "Comments"


_S1_TO_CPFT_COLUMN_TRANSLATION = {
    # Where CPFT has renamed a column.
    # - Key: (core_tablename, colname) tuple.
    # - Value: new CPFT column name.
    (S1Table.PATIENT,
     S1PatientCol.MIDDLE_NAMES): CPFTPatientCol.MIDDLE_NAMES,
    (S1Table.PATIENT, S1PatientCol.DOB): CPFTPatientCol.DOB,
    (S1Table.RELATIONSHIPS,
     S1RelCol.RELATED_STAFFCODE_OR_RELNHSNUM): S1PatientCol.NHSNUM,
}

_PID_SYNONYMS_S1 = (
    S1GenericCol.PATIENT_ID,
)
_PID_SYNONYMS_CPFT = (
    "ClientID",
    # ... seen in CPFT -- although often these tables should be excluded and
    # this field contains RiO (not SystmOne) IDs. However, some look at least
    # partially valid (e.g. S1_Deaths.ClientID, S1_Mortality.ClientID,
    # S1_MortalityAdditionalInfo.ClientID). For the last of those, there is an
    # explicit "SourceSystem" column; sometimes this is SystmOne, sometimes
    # RiO, etc. Using ClientID as a primary patient ID will mean that only IDs
    # present in the SystmOne master table will be taken. However, there is
    # also potential for confusion, so we exclude these tables above.

    "PatientID",  # e.g. in CPFT: S1_eDSM (a CPFT table)
    "PatID",  # e.g. in CPFT: ASCRIBE_Statin
)
PID_SYNONYMS = {
    SystmOneContext.TPP_SRE: _PID_SYNONYMS_S1,
    SystmOneContext.CPFT_DW: _PID_SYNONYMS_S1 + _PID_SYNONYMS_CPFT,
}

_MPID_SYNONYMS_S1 = (
    S1PatientCol.NHSNUM,
)
_MPID_SYNONYMS_CPFT = (
    CPFTGenericCol.NHSNUM2,
)
MPID_SYNONYMS = {
    SystmOneContext.TPP_SRE: _MPID_SYNONYMS_S1,
    SystmOneContext.CPFT_DW: _MPID_SYNONYMS_S1 + _MPID_SYNONYMS_CPFT,
}


# -----------------------------------------------------------------------------
# Column collections
# -----------------------------------------------------------------------------

CORE_TO_CONTEXT_COLUMN_TRANSLATIONS = {
    # Key: destination context.
    # Value: translation dictionary -- see e.g. S1_TO_CPFT_COLUMN_TRANSLATION.
    SystmOneContext.TPP_SRE: {},
    SystmOneContext.CPFT_DW: _S1_TO_CPFT_COLUMN_TRANSLATION,
}  # type: COLUMN_TRANSLATION_DICT_TYPE
CONTEXT_TO_CORE_CONTEXT_COLUMN_TRANSLATIONS = {
    SystmOneContext.TPP_SRE: {},
    SystmOneContext.CPFT_DW: _flip_coldict(_S1_TO_CPFT_COLUMN_TRANSLATION)
}  # type: COLUMN_TRANSLATION_DICT_TYPE

COLS_GENERIC_OK_UNMODIFIED_S1 = (
    S1GenericCol.ORG_ID_DONE_AT,
    S1GenericCol.STAFF_ID_DONE_BY,
    S1GenericCol.EVENT_ID,
    S1GenericCol.EVENT_OCCURRED_WHEN,
    S1GenericCol.EVENT_RECORDED_WHEN,
    S1GenericCol.ORG_ID_ENTERED_AT,
    S1GenericCol.ORG_ID_VISIBLE_TO,
    S1GenericCol.ORG_REGISTERED_AT,
    S1GenericCol.STAFF_PROFILE_ID_RECORDED_BY,
)
_COLS_GENERIC_EXCLUDE_S1 = (
    # Columns to exclude, regardless of table.
    #
    # This is primarily for when CPFT put identifiers all over the place (e.g.
    # joining them from the patient table). We can simply exclude (rather than
    # using them for scrubbing) since they are duplicates (for convenience) of
    # information in other tables like Patient, PatientContactDetails,
    # PatientAddressHistory.

    S1PatientCol.DOB,
    S1PatientCol.EMAIL,
    S1PatientCol.FORENAME,
    S1PatientCol.MIDDLE_NAMES,
    S1PatientCol.PREV_SURNAME,
    S1PatientCol.SURNAME,
    S1PatientCol.TITLE,  # unnecessary -- and might be rare, e.g. Lord High Admiral  # noqa

    S1AddressCol.BUILDING_NAME,
    S1AddressCol.BUILDING_NUMBER,
    S1AddressCol.COUNTY,
    S1AddressCol.LOCALITY,
    S1AddressCol.POSTCODE,
    S1AddressCol.ROAD,
    S1AddressCol.TOWN,

    S1RelCol.ADDRESS_COUNTY,
    S1RelCol.ADDRESS_EMAIL,
    S1RelCol.ADDRESS_FAX,
    S1RelCol.ADDRESS_HOUSE_NAME,
    S1RelCol.ADDRESS_HOUSE_NUMBER,
    S1RelCol.ADDRESS_LOCALITY,
    S1RelCol.ADDRESS_MOBILE_TELEPHONE,
    S1RelCol.ADDRESS_POST_TOWN,
    S1RelCol.ADDRESS_POSTCODE,
    S1RelCol.ADDRESS_ROAD,
    S1RelCol.ADDRESS_TELEPHONE,
    S1RelCol.ADDRESS_WORK_TELEPHONE,
    S1RelCol.DOB,
    S1RelCol.NAME,

    S1HospNumCol.HOSPNUM,  # just in case
)
_COLS_GENERIC_EXCLUDE_CPFT = (
    CPFTGenericCol.AGE_YEARS,
    # ... age when? Unhelpful. (And also, potentially leads to DOB discovery;
    # a blurred age near a birthday might be un-blurred by this.)
    CPFTGenericCol.ASSIGNMENT_NUMBER,  # could hash it, but still, sensitive.
    CPFTGenericCol.HOME_CONTACT_NUMBER,
    CPFTGenericCol.MOBILE_CONTACT_NUMBER,
    CPFTGenericCol.NHSNUM2,
    CPFTGenericCol.NHSNUM_MOTHER,
    CPFTGenericCol.PATIENT_ADDRESS,
    CPFTGenericCol.PATIENT_NAME,
    CPFTGenericCol.POSTCODE,

    CPFTPatientCol.DOB,
    CPFTPatientCol.MIDDLE_NAMES,

    CPFTAddressCol.POSTCODE_NOSPACE,
)
COLS_GENERIC_EXCLUDE = {
    SystmOneContext.TPP_SRE: _COLS_GENERIC_EXCLUDE_S1,
    SystmOneContext.CPFT_DW:
        _COLS_GENERIC_EXCLUDE_S1
        + _COLS_GENERIC_EXCLUDE_CPFT,
}

COLS_PATIENT_WORDS = (
    # Scrub as words.
    S1PatientCol.FORENAME,
    S1PatientCol.MIDDLE_NAMES,
    S1PatientCol.SURNAME,
    S1PatientCol.PREV_SURNAME,
    S1PatientCol.EMAIL,
    S1PatientCol.BIRTHPLACE,  # Unusual. But: scrub birthplace.
)
COLS_REQUIRED_SCRUBBERS = (
    # Information that must be present in the master patient table.
    S1PatientCol.PK,  # likely redundant! It's the PID "definer".
    S1PatientCol.FORENAME,
    S1PatientCol.SURNAME,
    S1PatientCol.DOB,
)
_COLS_PATIENT_TABLE_OK_UNMODIFIED_S1 = COLS_GENERIC_OK_UNMODIFIED_S1 + (
    # This list exists because we don't assume that things in the Patient table
    # are safe -- we assume they are unsafe, and let them through only if we
    # know about them. So we add "safe" things (that are not direct
    # identifiers) here.

    S1PatientCol.GENDER,
    S1PatientCol.SPEAKS_ENGLISH,
    S1PatientCol.SPINE_MATCHED,
)
_COLS_PATIENT_TABLE_OK_UNMODIFIED_CPFT = (
    # Added by CPFT:
    "DeathIndicator",  # binary version (0 alive, 1 dead)
    "NationalDataOptOut",  # Added by CPFT (from NDOptOutPreference)?)
    # - CPFT also add "RwNo" (bigint), but it's always 1 here. See above.
    # - We ignore "AgeInYears" (added by CPFT) since that is dangerous and
    #   depends on when you ask.
)
COLS_PATIENT_TABLE_OK_UNMODIFIED = {
    SystmOneContext.TPP_SRE: _COLS_PATIENT_TABLE_OK_UNMODIFIED_S1,
    SystmOneContext.CPFT_DW:
        _COLS_PATIENT_TABLE_OK_UNMODIFIED_S1
        + _COLS_PATIENT_TABLE_OK_UNMODIFIED_CPFT,
}

COLS_ADDRESS_PHRASES = (
    # Scrub as phrases.
    # - For S1AddressCol.BUILDING_NAME, see below.
    # - For S1AddressCol.BUILDING_NUMBER, see below.
    S1AddressCol.ROAD,
    S1AddressCol.LOCALITY,
    S1AddressCol.TOWN,
    S1AddressCol.COUNTY,
)
COLS_ADDRESS_PHRASE_UNLESS_NUMBER = (
    S1AddressCol.BUILDING_NAME,
    S1AddressCol.BUILDING_NUMBER,
    # S1AddressCol.BUILDING_NUMBER poses a new problem for us: this is meant
    # to be e.g. "5", which is by itself non-identifying and would be a big
    # problem if we scrub (consider e.g. "5 mg"). However, sometimes it is "5
    # Tree Road", because it's not forced to be numeric. So we extend CRATE
    # (2021-12-01) to add ScrubMethod.PHRASE_UNLESS_NUMERIC.
    # (S1AddressCol.BUILDING_NAME occasionally contains numbers only, so we
    # do the same thing.)
)

COLS_RELATIONSHIP_XREF_ID = (
    # Scrub (third-party) as full cross-references to another record.
    S1RelCol.RELATED_ID_DEPRECATED,
    S1RelCol.RELATED_ID,
)
_COLS_RELATIONSHIP_WORDS_S1 = (
    # Scrub (third-party) as words.
    S1RelCol.NAME,
    S1RelCol.ADDRESS_EMAIL,
)
_COLS_RELATIONSHIP_WORDS_CPFT = (
    # Added by CPFT:
    "Surname",  # surname of relative
    "FirstName",  # surname of relative
)
COLS_RELATIONSHIP_WORDS = {
    SystmOneContext.TPP_SRE: _COLS_RELATIONSHIP_WORDS_S1,
    SystmOneContext.CPFT_DW:
        _COLS_RELATIONSHIP_WORDS_S1
        + _COLS_RELATIONSHIP_WORDS_CPFT,
}
_COLS_RELATIONSHIP_DATES_S1 = (
    # Scrub (third-party) as dates.
    S1RelCol.DOB,
)
_COLS_RELATIONSHIP_DATES_CPFT = (
    # Added by CPFT:
    "DOB",  # likely duplicate of S1RelCol.DOB
)
COLS_RELATIONSHIP_DATES = {
    SystmOneContext.TPP_SRE: _COLS_RELATIONSHIP_DATES_S1,
    SystmOneContext.CPFT_DW:
        _COLS_RELATIONSHIP_DATES_S1
        + _COLS_RELATIONSHIP_WORDS_CPFT,
}
COLS_RELATIONSHIP_PHRASES = (
    # Scrub (third-party) as phrases.
    # Same principles as for the patient address, above.
    # - For S1RelCol.ADDRESS_HOUSE_NAME, see below.
    # - For S1RelCol.ADDRESS_HOUSE_NUMBER, see below.
    S1RelCol.ADDRESS_ROAD,
    S1RelCol.ADDRESS_LOCALITY,
    S1RelCol.ADDRESS_POST_TOWN,
    S1RelCol.ADDRESS_COUNTY,
)
COLS_RELATIONSHIP_PHRASE_UNLESS_NUMERIC = (
    S1RelCol.ADDRESS_HOUSE_NAME,
    S1RelCol.ADDRESS_HOUSE_NUMBER,
)
COLS_RELATIONSHIP_CODES = (
    # Scrub (third-party) as codes.
    S1RelCol.ADDRESS_POSTCODE,
)
COLS_RELATIONSHIP_NUMBERS = (
    # Scrub (third-party) as numbers.
    S1RelCol.RELATED_STAFFCODE_OR_RELNHSNUM,
    S1RelCol.ADDRESS_TELEPHONE,
    S1RelCol.ADDRESS_WORK_TELEPHONE,
    S1RelCol.ADDRESS_MOBILE_TELEPHONE,
    S1RelCol.ADDRESS_FAX,
)
_COLS_RELATIONSHIP_OK_UNMODIFIED_S1 = (
    S1RelCol.DATE_ENDED,
    S1RelCol.REL_TYPE,
    S1RelCol.GUARDIAN_PROXY,
    S1RelCol.NEXT_OF_KIN,
    S1RelCol.CARER,
    S1RelCol.PRINCIPAL_CARER,
    S1RelCol.KEYHOLDER,
    S1RelCol.PARENTAL_RESPONSIBILITY,
    S1RelCol.FINANCIAL_REP,
    S1RelCol.ADVOCATE,
    S1RelCol.MAIN_VISITOR,
    S1RelCol.CALLBACK_CONSENT,
    S1RelCol.COPY_CORRESPONDENCE,
    S1RelCol.CONTACT_ORDER,
    S1RelCol.CONTACT_METHOD,
    S1RelCol.COMMS_FORMAT,
    S1RelCol.INTERPRETER_REQUIRED,
    S1RelCol.SEX,
    S1RelCol.LANGUAGE,
    S1RelCol.ORG,
)
_COLS_RELATIONSHIP_OK_UNMODIFIED_CPFT = (
    # Added by CPFT:
    "DateDeath",  # date of death of relative
)
COLS_RELATIONSHIP_OK_UNMODIFIED = {
    SystmOneContext.TPP_SRE: _COLS_RELATIONSHIP_OK_UNMODIFIED_S1,
    SystmOneContext.CPFT_DW:
        _COLS_RELATIONSHIP_OK_UNMODIFIED_S1
        + _COLS_RELATIONSHIP_OK_UNMODIFIED_CPFT,
}

CPFT_REL_MOTHER_OK_UNMODIFIED = ()

OMIT_TABLENAME_COLNAME_PAIRS_S1 = (
    # Other specific fields to omit.
    ("Contacts", "ContactWith"),
    (S1Table.HOSP_AE_NUMBERS, S1HospNumCol.COMMENTS),
    ("OohAction", "Details"),  # Out-of-hours calls; details can sometimes contain phone numbers  # noqa
    ("OohThirdPartyCall", "Contact"),  # free text
    ("SafeguardingIncidentDetails", "PoliceReference"),
)

_FREETEXT_TABLENAME_COLNAME_REGEX_PAIRS_S1 = (
    ("FreeText$", "FreeText$"),  # the bulk of free text; VARCHAR(MAX)
    ("PersonAtRisk$", "ReasonForPlan$"),  # free text re safeguarding
    ("ReferralIn$", "PrimaryReason$"),  # only 200 chars; may be OK
    ("SafeguardingAllegationDetails$", "Outcome$"),  # only 100 chars -- but OMIT whole table, as above  # noqa
    ("SpecialNotes$", "Note$"),  # 8000 char free text
)
_FREETEXT_TABLENAME_COLNAME_REGEX_PAIRS_CPFT = (
    # CPFT:

    # - SRReferralIn renamed to S1_ReferralsIn with extra columns,
    #   PrimaryReason, but there are several others, like
    #   ReferralReasonDescription1.
    (".*Referral", ".*Reason"),

    # - S1_CYPFRS_TelephoneTriage links in a bunch of things from S1_FreeText.
    (CPFTTable.CYP_FRS_TELEPHONE_TRIAGE, ".*Assessment"),
    (CPFTTable.CYP_FRS_TELEPHONE_TRIAGE, ".*Presentation"),
    (CPFTTable.CYP_FRS_TELEPHONE_TRIAGE, ".*Risk"),
    (CPFTTable.CYP_FRS_TELEPHONE_TRIAGE, ".*Strength"),
    (CPFTTable.CYP_FRS_TELEPHONE_TRIAGE, ".*Intervention"),
    (CPFTTable.CYP_FRS_TELEPHONE_TRIAGE, ".*Problem"),
    (CPFTTable.CYP_FRS_TELEPHONE_TRIAGE, ".*Social"),
    (CPFTTable.CYP_FRS_TELEPHONE_TRIAGE, ".*Advice"),
    (CPFTTable.CYP_FRS_TELEPHONE_TRIAGE, ".*Clinical"),
    (CPFTTable.CYP_FRS_TELEPHONE_TRIAGE, ".*Outcome"),
    (CPFTTable.CYP_FRS_TELEPHONE_TRIAGE, ".*NextOfKin"),
    # todo: *** check filtered
)
FREETEXT_TABLENAME_COLNAME_REGEX_PAIRS = {
    SystmOneContext.TPP_SRE: _FREETEXT_TABLENAME_COLNAME_REGEX_PAIRS_S1,
    SystmOneContext.CPFT_DW:
        _FREETEXT_TABLENAME_COLNAME_REGEX_PAIRS_S1
        + _FREETEXT_TABLENAME_COLNAME_REGEX_PAIRS_CPFT,
}
FULLTEXT_INDEX_TABLENAME_COLNAME_REGEX_PAIRS = (
    # Subset of FREETEXT_TABLENAME_COLNAME_REGEX_PAIRS where we would want to
    # implement a FULLTEXT index.
    ("FreeText$", "FreeText$"),  # the bulk of free text; VARCHAR(MAX)
)

_EXTRA_STANDARD_INDEX_TABLENAME_COLNAME_PAIRS_CPFT = (
    # S1_Patient.IDPatient: Added by CPFT. Duplicate of RowIdentifier.
    # But likely to be used by researchers, so should be indexed.
    (S1Table.PATIENT, S1GenericCol.PATIENT_ID),
)
EXTRA_STANDARD_INDEX_TABLENAME_COLNAME_PAIRS = {
    SystmOneContext.TPP_SRE: (),
    SystmOneContext.CPFT_DW: _EXTRA_STANDARD_INDEX_TABLENAME_COLNAME_PAIRS_CPFT,  # noqa
}

_GENERIC_COLS_TO_INDEX_S1 = (
    # Generically sensible things to index.
    S1GenericCol.EVENT_ID,
    S1GenericCol.PATIENT_ID,
    S1GenericCol.QUESTIONNAIRE_ID,
    S1GenericCol.REFERRAL_ID,
)
_GENERIC_COLS_TO_INDEX_CPFT = (
    CPFTGenericCol.PATIENT_ID_SYNONYM_1,
)
GENERIC_COLS_TO_INDEX = {
    SystmOneContext.TPP_SRE: _GENERIC_COLS_TO_INDEX_S1,
    SystmOneContext.CPFT_DW:
        _GENERIC_COLS_TO_INDEX_S1
        + _GENERIC_COLS_TO_INDEX_CPFT,
}

EXEMPT_FROM_SCRUBBING_TABLENAME_COLNAME_PAIRS_S1 = (
    # Things that look like free text, but aren't.
    ("AnsweredQuestionnaire", "QuestionnaireName"),
)

_PK_TABLENAME_COLNAME_REGEX_PAIRS_CPFT = (
    # Primary key fields with non-standard names.
    # Note that some are CPFT-created tables, which is why they don't follow
    # standard conventions.
    ("3DayFollowUp", "IDHospitalAdmissionAndDischarge"),
    ("ActivityEvent_EventDuration", S1GenericCol.EVENT_ID),
    # AQ_* -- no obvious PK.
    ("_CGAS_PairedScore_By_Referral", S1GenericCol.REFERRAL_ID),
    ("CarePlan", "CarePlanID"),  # includes CarePlanDetail, modified from the source  # noqa
    # ... CarePlanReview has IDCarePlan but that is not unique.
    ("Caseload", "IDReferralIn"),
    # ClinicalDashboard*: a bunch of CPFT things; no obvious PK.
    # ClinicalMeasure*: a bunch of CPFT derived things; no obvious PK.
    # ClinicalOutcome*: a bunch of CPFT derived things; no obvious PK.
    # ContactsArchive_LatestStaffContact: no obvious PK.
    ("ContactsArchive_NonLegalContacts", S1GenericCol.EVENT_ID),
    ("ContactsArchive_TotalsByReferral", S1GenericCol.REFERRAL_ID),
    # Contacts_CYP_PlanMetric_7: no obvious PK.
    ("Contacts_CarerStatus_MH", S1GenericCol.PATIENT_ID),
    ("Contacts_CarerStatus_PH", S1GenericCol.PATIENT_ID),
    # CoronaVirus: no obvious PK (maybe combination of IDPatient, IDReferralIn)
    # CurrentInpatientDashboard_Doctors: *almost* IDPatient, IDReferralIn but one extra row  # noqa
    # Deaths: no obvious PK, despite "ClientID" (not unique)
    ("Demographics", S1GenericCol.PATIENT_ID),
    # DischargeDelay_Fact: no obvious PK.
    # EuroQol*: no PKs
    # FACT_Inp_Data: no obvious PK.
    # Falls_AtRiskState*: no PKs
    # FreeText_* [CPFT derived free text tables]: none in the first, not all explored  # noqa
    # GateKeeping: no obvious PK.
    # Honos_Scores: no PK
    # ICW_PTL: no PK
    # Immunisation: no obvious PK
    # InpatientLeave: no obvious PK
    # Inpatient_NorthwickParkIndex: no obvious PK
    # LADSAdults_Output: no obvious PK
    ("LADSAdultsQuestionnaires", S1GenericCol.QUESTIONNAIRE_ID),
    # LADSCYPHS_Output: no obvious PK
    ("LADSCYPQuestionnaires", S1GenericCol.QUESTIONNAIRE_ID),
    ("MDT_Caseload", S1GenericCol.REFERRAL_ID),
    # OutOfHoursSRCodeInformation: no PK
    # PRISM_ReReferral: no PK
    # PatientAnsweredQuestionnaireInformation: IDPatient currently unique but I strongly suspect only temporarily  # noqa
    # PatientContact: no PK
    # PatientEthnicity: no PK
    ("PatientGPPractice", S1GenericCol.PATIENT_ID),
    # PatientLanguageDeathOptions: no PK
    # PatientLetterInformation: IDPatient currently unique but I strongly suspect only temporarily  # noqa
    ("PatientOverview", S1GenericCol.REFERRAL_ID),
    # PatientRelationship: no PK (modified from the source)
    ("PatientRelationshipMother", S1GenericCol.PATIENT_ID),
    # PatientSRCodeInformation: no PK
    # PhysicalHealthChecks*: no PK (IDPatient currently unique in S1_PhysicalHealthChecks_CQUIN but unlikely to remain so)  # noqa
    # QRisk: no PK
    ("ReferralInIntervention", S1GenericCol.REFERRAL_ID), # modified from the source  # noqa
    ("Vanguard", "ReferralNumber"),
    # eDSM: no PK
)
PK_TABLENAME_COLNAME_REGEX_PAIRS = {
    SystmOneContext.TPP_SRE: (),
    SystmOneContext.CPFT_DW: _PK_TABLENAME_COLNAME_REGEX_PAIRS_CPFT,
}

_OPT_OUT_TABLENAME_COLNAME_PAIRS_CPFT = (
    ("ClinicalOutcome_ConsentResearch_OptOutCheck", "SNOMEDCode"),
)
OPT_OUT_TABLENAME_COLNAME_PAIRS = {
    SystmOneContext.TPP_SRE: (),
    SystmOneContext.CPFT_DW: _OPT_OUT_TABLENAME_COLNAME_PAIRS_CPFT,
}


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


def is_pair_in_re(a: str, b: str, y_regexes: Iterable[Tuple[str, str]]) -> bool:
    """
    Case-insensitive regex-based version of "in", to replace "if a, b in y".
    """
    return any(
        eq_re(a, test_a) and eq_re(b, test_b)
        for test_a, test_b in y_regexes
    )


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
        if is_in_re(tablename, INCLUDE_TABLES_REGEX[from_context]):
            return tablename
        else:
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
    change_comment_and_indexing_only: bool = False
    src_flags: str = ""
    scrub_src: Optional[ScrubSrc] = None
    scrub_method: Optional[ScrubMethod] = None
    decision: Decision = Decision.OMIT
    alter_methods: List[AlterMethod] = field(default_factory=list)
    dest_datatype: str = None
    dest_field: str = None

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
    return eq(tablename, S1Table.PATIENT)


def is_pid(colname: str, context: SystmOneContext) -> bool:
    """
    Is this column the SystmOne primary patient identifier (PID)?

    It's nearly always S1GenericCol.PID. But occasionally something else
    (e.g. in CPFT-created tables).

    This works for all tables EXCEPT the main "Patient" table, where the PK
    takes its place.

    Occasionally, CPFT tables blend SystmOne patients with other patients using
    IDs from other EHR systems. However, those patients won't be in our master
    patient index, so their data won't be brought through.
    """
    return is_in(colname, PID_SYNONYMS[context])


def is_mpid(colname: str, context: SystmOneContext) -> bool:
    """
    Is this column the master patient identifier (MPID), i.e. the NHS number?
    """
    return is_in(colname, MPID_SYNONYMS[context])


def is_pk(tablename: str,
          colname: str,
          context: SystmOneContext,
          ddr: DataDictionaryRow = None) -> bool:
    """
    Is this a primary key (PK) column within its table?
    """
    # This check is debatable. It's possible that the source database has
    # columns that are NULLable but are in fact never null and are PKs. Indeed,
    # that is the case; e.g. S1_FreeText.RowIdentifier is shown as "bigint,
    # null" in SQL Server Manager, but "SELECT COUNT(*) FROM S1_FreeText WHERE
    # RowIdentifier IS NULL" gives 0 rows, out of ~1M rows in total.
    #
    # if ddr.src_reflected_nullable:
    #     return False  # can't be a PK if it can be NULL

    # 1. If the source database says so (ours never does).
    if ddr and ddr.pk:
        return True
    # 2. If it has the standard column name, i.e. RowIdentifier, then it's
    #    a PK.
    if eq(colname, S1GenericCol.PK):
        return True
    # 3. If it's a specifically noted PK.
    return is_pair_in_re(tablename, colname,
                         PK_TABLENAME_COLNAME_REGEX_PAIRS[context])


def is_free_text(tablename: str,
                 colname: str,
                 context: SystmOneContext) -> bool:
    """
    Is this a free-text field requiring scrubbing?

    Unusually, there is not very much free text, and it is mostly collated.
    (We haven't added binary support yet. Do we have the binary documents?)
    """
    # if not is_sqlatype_string(ddr.src_sqla_coltype):  # UNRELIABLE?
    #     # Not a textual type
    #     return False
    return is_pair_in_re(tablename, colname,
                         FREETEXT_TABLENAME_COLNAME_REGEX_PAIRS[context])


def should_be_fulltext_indexed(tablename: str, colname: str) -> bool:
    """
    Is this a field that should get a FULLTEXT index? That's not just "a column
    that contains free text and should scrubbed", that is "a column with a lot
    of interesting free text that should get a special index".
    """
    return is_pair_in_re(tablename, colname,
                         FULLTEXT_INDEX_TABLENAME_COLNAME_REGEX_PAIRS)


# =============================================================================
# Deciding about columns
# =============================================================================

def process_generic_table_column(tablename: str,
                                 colname: str,
                                 ddr: DataDictionaryRow,
                                 ssi: ScrubSrcAlterMethodInfo,
                                 context: SystmOneContext) -> bool:
    """
    Performs operations applicable to columns any SystmOne table, except a few
    very special ones like Patient. Modifies ssi in place.

    Returns: recognized and dealt with?
    """
    # -------------------------------------------------------------------------
    # Generic table
    # -------------------------------------------------------------------------

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # PKs, PIDs, MPIDs (which can overlap, e.g. a PK that is a PID)
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    handled = False
    if is_pk(tablename, colname, context, ddr):
        # PK for all tables.
        ssi.add_src_flag(SrcFlag.PK)
        ssi.add_src_flag(SrcFlag.NOT_NULL)
        ssi.add_src_flag(SrcFlag.ADD_SRC_HASH)
        ssi.include()
        handled = True

    # PKs can also be other things:

    if is_pair_in(tablename, colname, OPT_OUT_TABLENAME_COLNAME_PAIRS[context]):
        ssi.add_src_flag(SrcFlag.OPT_OUT)
        handled = True

    if is_pid(colname, context):
        # FK to Patient.RowIdentifier for all other patient-related tables.
        ssi.add_src_flag(SrcFlag.PRIMARY_PID)
        ssi.dest_field = ddr.config.research_id_fieldname
        ssi.include()
        handled = True

    elif is_mpid(colname, context):
        # An NHS number in a random table. OK, as long as we hash it.
        ssi.add_src_flag(SrcFlag.MASTER_PID)
        ssi.dest_field = ddr.config.master_research_id_fieldname
        ssi.include()
        handled = True

    if handled:
        return True

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Other things
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    if is_in(colname, COLS_GENERIC_EXCLUDE[context]):
        # Columns that are never OK in a generic table, and are duplicated
        # direct identifiers (handled specially in the master patient ID table
        # etc.).
        ssi.omit()
        # ... likely redundant but that's not obvious within this function

    elif is_in(colname, COLS_GENERIC_OK_UNMODIFIED_S1):
        # Generic columns that are always OK (e.g. organization ID).
        ssi.include()

    elif (is_free_text(tablename, colname, context)
            and not is_pair_in(
                tablename, colname,
                EXEMPT_FROM_SCRUBBING_TABLENAME_COLNAME_PAIRS_S1)):
        # Free text to be scrubbed.
        ssi.add_alter_method(AlterMethod(config=ddr.config, scrub=True))
        ssi.include()

    else:
        # Unrecognized.
        return False

    return True


def get_scrub_alter_details(
        tablename: str,
        colname: str,
        ddr: DataDictionaryRow,
        context: SystmOneContext,
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
        ddr:
            Data dictionary row.
        context:
            The context from which SystmOne data is being extracted (e.g. the
            raw TPP Strategic Reporting Extract (SRE), or a local version
            processed into CPFT's Data Warehouse).
        include_generic:
            Include all fields that are not known about by this code and
            treated specially? If False, the config file settings are used
            (which may omit or include). If True, all such fields are included.
    """
    ssi = ScrubSrcAlterMethodInfo(decision=Decision.OMIT)  # omit by default

    # -------------------------------------------------------------------------
    # Omit table entirely?
    # -------------------------------------------------------------------------
    if (is_in(tablename, OMIT_TABLES[context])
            or is_in_re(tablename, OMIT_TABLES_REGEX[context])):
        return ssi

    # -------------------------------------------------------------------------
    # Deal with the core patient table. Many details here.
    # -------------------------------------------------------------------------
    if eq(tablename, S1Table.PATIENT):
        if eq(colname, S1GenericCol.PK):
            # RowIdentifier: SystmOne patient ID in the master patient table.
            # Hash and scrub SystmOne IDs.
            ssi.add_src_flag(SrcFlag.PK)
            ssi.add_src_flag(SrcFlag.NOT_NULL)
            ssi.add_src_flag(SrcFlag.PRIMARY_PID)  # automatically hashed
            ssi.add_src_flag(SrcFlag.DEFINES_PRIMARY_PIDS)
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.NUMERIC
            ssi.include()

        elif eq(colname, S1GenericCol.PATIENT_ID):
            # IDPatient: Added by CPFT to the master patient table.
            # Needs to be hashed. Is a duplicate of RowIdentifier.
            ssi.add_src_flag(SrcFlag.PRIMARY_PID)  # automatically hashed
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.NUMERIC
            ssi.include()

        elif is_mpid(colname, context):  # NHS number
            # Hash and scrub NHS numbers. (Present as a text field, but is
            # numeric.)
            ssi.add_src_flag(SrcFlag.MASTER_PID)  # automatically hashed
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.NUMERIC
            ssi.include()

        elif is_in(colname, COLS_PATIENT_WORDS):
            # Scrub and omit all names.
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.WORDS

        elif eq(colname, S1PatientCol.DOB):
            # Truncate and scrub dates of birth.
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.DATE
            ssi.add_alter_method(AlterMethod(config=ddr.config,
                                             truncate_date=True))
            ssi.include()

        elif eq(colname, S1PatientCol.DOD):
            # Include dates of death.
            ssi.include()

        elif eq(colname, S1PatientCol.BIRTHPLACE):
            # Unusual. But: scrub birthplace.
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.WORDS

        elif eq(colname, S1PatientCol.TESTPATIENT):
            # Exclude test patients.
            ssi.add_src_flag(SrcFlag.OPT_OUT)
            ssi.include()

        elif eq(colname, S1PatientCol.SOCIAL_SERVICES_REF):
            # Scrub and omit Social Services ID (text).
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.CODE
            ssi.omit()  # just to be explicit

        elif is_in(colname, COLS_PATIENT_TABLE_OK_UNMODIFIED[context]):
            # These are OK.
            ssi.include()

        else:
            # If anything else is put into this table, it may be sensitive.
            pass  # omit anything else in the master patient table

        # Via a separate "if" statement:
        if is_in(colname, COLS_REQUIRED_SCRUBBERS):
            ssi.add_src_flag(SrcFlag.REQUIRED_SCRUBBER)

        return ssi

    # -------------------------------------------------------------------------
    # Proceed for all other tables.
    # -------------------------------------------------------------------------
    handled = process_generic_table_column(
        tablename=tablename,
        colname=colname,
        ddr=ddr,
        ssi=ssi,
        context=context
    )
    if handled:
        # Recognized and handled as a generic column.
        return ssi

    if eq(tablename, S1Table.ADDRESS):
        # ---------------------------------------------------------------------
        # Address table.
        # ---------------------------------------------------------------------
        if is_in(colname, COLS_ADDRESS_PHRASES):
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.PHRASE

        elif is_in(colname, COLS_ADDRESS_PHRASE_UNLESS_NUMBER):
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.PHRASE_UNLESS_NUMERIC

        elif eq(colname, S1AddressCol.POSTCODE):
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.CODE

        else:
            # omit anything else in the address table, e.g.
            # CPFTAddressCol.POSTCODE_NOSPACE
            pass

    elif eq(tablename, S1Table.CONTACT_DETAILS):
        # ---------------------------------------------------------------------
        # Contact details table.
        # ---------------------------------------------------------------------
        if eq(colname, S1ContactCol.NUMBER):
            # Could be patient; ?could be third party; mostly patient?
            ssi.scrub_src = ScrubSrc.PATIENT
            ssi.scrub_method = ScrubMethod.NUMERIC

        else:
            pass  # omit anything else in the contact details table

    elif eq(tablename, S1Table.RELATIONSHIPS):
        # ---------------------------------------------------------------------
        # Third-party (relationships) table.
        # ---------------------------------------------------------------------
        if is_in(colname, COLS_RELATIONSHIP_XREF_ID):
            # "Go fetch that linked patient, and use their identity information
            # as a third-party scrubber for our index patient."
            ssi.scrub_src = ScrubSrc.THIRDPARTY_XREF_PID
            ssi.scrub_method = ScrubMethod.NUMERIC
            ssi.include()

        elif is_in(colname, COLS_RELATIONSHIP_WORDS[context]):
            ssi.scrub_src = ScrubSrc.THIRDPARTY
            ssi.scrub_method = ScrubMethod.WORDS

        elif is_in(colname, COLS_RELATIONSHIP_DATES[context]):
            ssi.scrub_src = ScrubSrc.THIRDPARTY
            ssi.scrub_method = ScrubMethod.DATE

        elif is_in(colname, COLS_RELATIONSHIP_PHRASES):
            ssi.scrub_src = ScrubSrc.THIRDPARTY
            ssi.scrub_method = ScrubMethod.PHRASE

        elif is_in(colname, COLS_RELATIONSHIP_PHRASE_UNLESS_NUMERIC):
            ssi.scrub_src = ScrubSrc.THIRDPARTY
            ssi.scrub_method = ScrubMethod.PHRASE_UNLESS_NUMERIC

        elif is_in(colname, COLS_RELATIONSHIP_CODES):
            ssi.scrub_src = ScrubSrc.THIRDPARTY
            ssi.scrub_method = ScrubMethod.CODE

        elif is_in(colname, COLS_RELATIONSHIP_NUMBERS):
            ssi.scrub_src = ScrubSrc.THIRDPARTY
            ssi.scrub_method = ScrubMethod.NUMERIC

        elif is_in(colname, COLS_RELATIONSHIP_OK_UNMODIFIED[context]):
            ssi.include()

        else:
            pass  # omit anything unknown in the relationship table

    elif (context == SystmOneContext.CPFT_DW
            and eq(tablename, CPFTTable.REL_MOTHER)):
        # ---------------------------------------------------------------------
        # A CPFT partial duplicate table: from the relationship table where
        # that relationship is "Mother".
        # ---------------------------------------------------------------------
        if is_in(colname, COLS_RELATIONSHIP_XREF_ID):
            ssi.scrub_src = ScrubSrc.THIRDPARTY_XREF_PID
            ssi.scrub_method = ScrubMethod.NUMERIC
            ssi.include()

        elif eq(colname, CPFTOtherCol.REL_MOTHER_COL_NHSNUM):
            # Likely a duplicate as a scrubber. But that's not a problem for
            # CRATE and this also marks it as something to remove.
            ssi.scrub_src = ScrubSrc.THIRDPARTY
            ssi.scrub_method = ScrubMethod.NUMERIC

        elif is_in(colname, CPFT_REL_MOTHER_OK_UNMODIFIED):
            ssi.include()

        else:
            pass  # omit anything unown

    elif tcmatch(tablename, colname,
                 S1Table.HOSP_AE_NUMBERS, S1HospNumCol.HOSPNUM):
        # ---------------------------------------------------------------------
        # A hospital number.
        # ---------------------------------------------------------------------
        ssi.scrub_src = ScrubSrc.PATIENT
        ssi.scrub_method = ScrubMethod.CODE  # can contain text

    elif tcmatch(tablename, colname,
                 S1Table.SAFEGUARDING_PERSON_AT_RISK, S1PatientCol.NHSNUM):
        # ---------------------------------------------------------------------
        # Another person's NHS number.
        # ---------------------------------------------------------------------
        ssi.scrub_src = ScrubSrc.THIRDPARTY
        ssi.scrub_method = ScrubMethod.NUMERIC

    elif is_pair_in(tablename, colname, OMIT_TABLENAME_COLNAME_PAIRS_S1):
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
            ssi.change_comment_and_indexing_only = True

    return ssi


def get_index_flag(tablename: str,
                   colname: str,
                   ddr: DataDictionaryRow,
                   context: SystmOneContext) -> Optional[IndexType]:
    """
    Should this be indexed? Returns an indexing flag, or ``None`` if it should
    not be indexed.
    """
    if is_pk(tablename, colname, context, ddr):
        # PKs should have a unique index.
        return IndexType.UNIQUE
    pid = is_pid(colname, context)
    if is_master_patient_table(tablename) and pid:
        # In the master patient table, PIDs are unique.
        # (MPIDs aren't -- they can be NULL.)
        return IndexType.UNIQUE
    if pid or is_mpid(colname, context):
        # We index all patient IDs.
        return IndexType.NORMAL
    if is_pair_in(tablename, colname,
                  EXTRA_STANDARD_INDEX_TABLENAME_COLNAME_PAIRS[context]):
        # Additional columns to index
        return IndexType.NORMAL
    if colname in GENERIC_COLS_TO_INDEX[context]:
        return IndexType.NORMAL
    if should_be_fulltext_indexed(tablename, colname):
        # Full-text indexes
        return IndexType.FULLTEXT
    return IndexType.NONE


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
            A few (see INCLUDE_TABLES_REGEX) are explicitly included anyway.
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
    ssi = get_scrub_alter_details(
        tablename=tablename,
        colname=colname,
        ddr=ddr,
        include_generic=include_generic,
        context=context
    )

    if not ssi.change_comment_and_indexing_only:
        # Source information
        ddr.src_flags = ssi.src_flags
        ddr.scrub_src = ssi.scrub_src
        ddr.scrub_method = ssi.scrub_method

        # Output decision
        ddr.decision = ssi.decision

        # Alterations
        ddr.set_alter_methods_directly(ssi.alter_methods)

        # Destination -- mostly automatic
        ddr.dest_field = ssi.dest_field or ddr.dest_field

    # Indexing
    ddr.index = get_index_flag(tablename, colname, ddr, context)
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
