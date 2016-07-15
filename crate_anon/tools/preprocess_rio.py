#!/usr/bin/env python
# crate_anon/tools/preprocess_rio.py

"""
NOTES

===============================================================================
Primary keys
===============================================================================
In RCEP, Document_ID is VARCHAR(MAX), and is often:
    'global_table_id_9_or_10_digits' + '_' + 'pk_int_as_string'

HOWEVER, the last part is not always unique; e.g. Care_Plan_Interventions.

-   Care_Plan_Interventions has massive tranches of ENTIRELY identical rows,
    including a column called, ironically, "Unique_Key".
-   Therefore, we could either ditch the key entirely, or just use a non-UNIQUE
    index (and call it "key" not "pk").

-   AND THEN... In Client_Family, we have Document_ID values like
    773577794_1000000_1000001
    ^^^^^^^^^ ^^^^^^^ ^^^^^^^
    table ID  RiO#    Family member's RiO#

    ... there is no unique ID. And we don't need the middle part as we already
    have Client_ID. So this is not very useful. We could mangle out the second
    and subsequent '_' characters to give a unique number here, which would
    meaning having PK as BIGINT not INTEGER.
-   SQL Server's ROW_NUMBER() relates to result sets.
-   However, ADD pkname INT IDENTITY(1, 1) works beautifully and
    autopopulates existing tables.

===============================================================================
How is RiO non-core structured?
===============================================================================

- INDEX TABLES
    AssessmentDates
        associates AssessmentID and ClientID with dates

    AssessmentFormGroupsIndex, e.g.:
        Name               Description          Version    Deleted
        CoreAssess         Core Assessment      16          0
        CoreAssess         Core Assessment      17          0
        CoreAssessNewV1    Core Assessment v1   0           0
        CoreAssessNewV1    Core Assessment v1   1           0
        CoreAssessNewV2    Core Assessment v2   0           0
        CoreAssessNewV2    Core Assessment v2   1           0
        CoreAssessNewV2    Core Assessment v2   2           0
        ^^^                ^^^
        RiO form groups    Nice names

    AssessmentFormGroupsStructure, e.g.:
        name            FormName           AddedDate FormgroupVersion FormOrder
        CoreAssessNewV2	coreasspresprob	    2013-10-30 15:46:00.000	0	0
        CoreAssessNewV2	coreassesspastpsy	2013-10-30 15:46:00.000	0	1
        CoreAssessNewV2	coreassessbackhist	2013-10-30 15:46:00.000	0	2
        CoreAssessNewV2	coreassesmentstate	2013-10-30 15:46:00.000	0	3
        CoreAssessNewV2	coreassescapsafrisk	2013-10-30 15:46:00.000	0	4
        CoreAssessNewV2	coreasssumminitplan	2013-10-30 15:46:00.000	0	5
        CoreAssessNewV2	coreasspresprob	    2014-12-14 19:19:06.410	1	0
        CoreAssessNewV2	coreassesspastpsy	2014-12-14 19:19:06.410	1	1
        CoreAssessNewV2	coreassessbackhist	2014-12-14 19:19:06.413	1	2
        CoreAssessNewV2	coreassesmentstate	2014-12-14 19:19:06.413	1	3
        CoreAssessNewV2	coreassescapsafrisk	2014-12-14 19:19:06.417	1	4
        CoreAssessNewV2	coreasssumminitplan	2014-12-14 19:19:06.417	1	5
        CoreAssessNewV2	coresocial1	        2014-12-14 19:19:06.420	1	6
        CoreAssessNewV2	coreasspresprob	    2014-12-14 19:31:25.377	2	0 } NB
        CoreAssessNewV2	coreassesspastpsy	2014-12-14 19:31:25.377	2	1 }
        CoreAssessNewV2	coreassessbackhist	2014-12-14 19:31:25.380	2	2 }
        CoreAssessNewV2	coreassesmentstate	2014-12-14 19:31:25.380	2	3 }
        CoreAssessNewV2	coreassescapsafrisk	2014-12-14 19:31:25.380	2	4 }
        CoreAssessNewV2	coreasssumminitplan	2014-12-14 19:31:25.383	2	5 }
        CoreAssessNewV2	coresocial1	        2014-12-14 19:31:25.383	2	6 }
        CoreAssessNewV2	kcsahyper	        2014-12-14 19:31:25.387	2	7 }
        ^^^             ^^^
        Form groups     RiO forms; these correspond to UserAssess___ tables.

    AssessmentFormsIndex, e.g.
        Name                InUse Style Deleted    Description  ...
        core_10             1     6     0    Clinical Outcomes in Routine Evaluation Screening Measure-10 (core-10)
        corealcsub          1     6     0    Alcohol and Substance Misuse
        coreassescapsafrisk 1     6     0    Capacity, Safeguarding and Risk
        coreassesmentstate  1     6     0    Mental State
        coreassessbackhist  1     6     0    Background and History
        coreassesspastpsy   1     6     0    Past Psychiatric History and Physical Health
        coreasspresprob     1     6     0    Presenting Problem
        coreasssumminitplan 1     6     0    Summary and Initial Plan
        corecarer           1     6     0    Carers and Cared For
        corediversity       1     6     0    Diversity Needs
        coremedsum          1     6     0    Medication, Allergies and Adverse Reactions
        coremenhis          1     6     0    Mental Health / Psychiatric History
        coremenstate        1     6     0    Mental State and Formulation
        coreperdev          1     6     0    Personal History and Developmental History
        ^^^                                  ^^^
        |||                                  Nice names.
        RiO forms; these correspond to UserAssess___ tables,
        e.g. UserAssesscoreassesmentstate

    AssessmentFormsLocks
        system only; not relevant

    AssessmentFormsTimeout
        system only; not relevant

    AssessmentImageForms
        SequenceID, FormName, ClientID, AssessmentDate, UserID, ImagePath
        ?
        no data

    AssessmentIndex, e.g.
        Name          InUse Version DateBound RequiresClientID  Deleted Description ...
        ConsentShare  1     3       1         0                 1       Consent to Share Information
        CoreAssess    1     1       0         1                 0       Core Assessment
        CoreAssess    1     2       0         1                 0       Core Assessment
        CoreAssess    1     3       0         1                 0       Core Assessment
        CoreAssess    1     4       0         1                 0       Core Assessment
        CoreAssess    1     5       0         1                 0       Core Assessment
        CoreAssess    1     6       0         1                 0       Core Assessment
        CoreAssess    1     7       0         1                 0       Core Assessment
        crhtaaucp     1     1       0         0                 0       CRHTT / AAU Care Plan
        ^^^
        These correspond to AssessmentStructure.Assessment

    AssessmentMasterTableIndex, e.g.
        TableName       TableDescription
        core10          core10
        Corealc1        TAUDIT - Q1
        Corealc2        TAUDIT Q2
        Corealc3        TAUDIT - Q3,4,5,6,7,8
        Corealc4        TAUDIT - Q9,10
        Corealc5        Dependence
        Corealc6        Cocaine Use
        CoreOtherAssess Other Assessments
        crhttcpstat     CRHTT Care Plan Status
        ^^^
        These correspond to UserMaster___ tables.
        ... Find with:
            SELECT * FROM rio_data_raw.information_schema.columns
            WHERE table_name LIKE '%core10%';

    AssessmentPseudoForms, e.g. (all rows):
        Name            Link
        CaseNoteBar     ../Letters/LetterEditableMain.aspx?ClientID
        CaseNoteoview   ../Reports/RioReports.asp?ReportID=15587&ClientID
        kcsahyper       tfkcsa
        physv1hypa      physassess16a&readonlymode=1
        physv1hypb1     physasses16b1&readonlymode=1
        physv1hypb2     physasses16b22&readonlymode=1
        physv1hypbody   testbmap&readonlymode=1
        physv1hypvte    vte&readonlymode=1

    AssessmentReadOnlyFields, e.g.
        Code        CodeDescription       SQLStatementLookup    SQLStatementSearch
        ADCAT       Adminstrative Cat...  SELECT TOP 1 u.Cod... ...
        ADD         Client  Address       SELECT '$LookupVal... ...
        AdmCons     Consultant            SELECT '$LookupVal... ...
        AdmglStat   Status at Admission   SELECT '$LookupVal... ...
        AdmitDate   Admission Date        SELECT '$LookupVal... ...
        AEDEXLI     AED Exceptions...     SELECT TOP 1 ISNUL... ...
        Age         Client Age            SELECT '$LookupVal... ...
        Allergies   Client Allergies      SELECT dbo.LocalCo... ...
        bg          Background (PSOC323)  SELECT TOP 1 ISNUL... ...

        That Allergies one in full:
        - SQLStatementLookup
            SELECT dbo.LocalConfig_GetClientAllergies('$key$') AS Allergies
        - SQLStatementSearch = SQLStatementLookup

        And the bg/Background... one:
        - SQLStatementLookup
            SELECT TOP 1
                ISNULL(Men03,'History of Mental Health Problems / Psychiatric History section of core assessment not filled'),
                ISNULL(Men03,'History of Mental Health Problems / Psychiatric History section of core assessment not filled')
            FROM dbo.view_userassesscoremenhis
              -- ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
              -- view in which data column names renamed 'Men01', 'Men02'...
            WHERE ClientID = '$ClientID$'
            AND dbo.udf_Config_SystemValidationStatus(system_validationData,'Men03','v') = 1
            ORDER BY
                AssessmentDate DESC,
                type12_UpdatedDate DESC
        - SQLStatementSearch = SQLStatementLookup

        - EXEC sp_helptext 'production.rio62camlive.dbo.udf_Config_SystemValidationStatus';
          ... can't view this at present (am on the wrong machine?).

    AssessmentStructure, e.g.:
        FormGroup       Assessment  AssessmentVersion FormGroupVersion FormGroupOrder
        CoreAssessNewV1 CoreAssess    7    1    1
        CoreAssessNewV2 CoreAssess    7    2    0
        CoreAssessNewV2 CoreAssess    6    1    0
        CoreAssessNewV2 CoreAssess    5    0    0
        CoreAssessNewV2 CoreAssess    2    0    1
        CoreAssessNewV2 CoreAssess    3    0    0

        ... FORM GROUP to ASSESSMENT mapping

- MAIN DATA TABLES

    e.g.:
    UserAssesscoreassesmentstate
        ClientID
        system_ValidationData  -- e.g. (with newlines added):
            '<v n="3">
                <MentState s="v" a="<userID>" v="" d="" e="10/11/2013 13:23" o="1" n="3" b="" c="">
                </MentState>
            </v>'
            ... where <userID> was a specific user ID
        NHSNum  -- as VARCHAR
        AssessmentDate
        ServRef
        MentState   -- this contains the text
        type12_NoteID -- PK
        type12_OriginalNoteID  -- can be NULL
        type12_DeletedDate  -- can be NULL
        type12_UpdatedBy
        type12_UpdatedDate
        formref

    UserAssesscoreassesspastpsy
        ClientID
        system_ValidationData
        NHSNum
        AssessmentDate
        ServRef
        PastPsyHist  -- contains text
        PhyHealth    -- contains text
        Allergies    -- contains text
        type12_NoteID
        type12_OriginalNoteID
        type12_DeletedDate
        type12_UpdatedBy
        type12_UpdatedDate
        formref
        frailty  -- numeric; in passing, here's the Rockwood frailty score

- LOOKUP TABLES

    UserMasterfrailty, in full:
        Code CodeDescription            Deleted
        1    1 - Very Fit               0
        2    2 - Well                   0
        3    3 - Managing Well          0
        4    4 - Vulnerable             0
        5    5 - Mildly Frail           0
        7    7 - Severely Frail         0
        6    6 - Moderately Frail       0
        9    9 - Terminally Ill         0
        8    8 - Very Serverely Frail   0

- SO, OVERALL STRUCTURE, APPROXIMATELY:

    RiO front-end example:
        Assessments [on menu]
            -> Core Assessment [menu dropdown]
            -> Core Assessment v2 [LHS, expands to...]
                ->  Presenting Problem [LHS]
                    Past Psychiatric History and Physical Health
                        ->  Service/Team
                            Past Psychiatric History
                            Physical Health / Medical History
                            Allergies
                            Frailty Score
                    Background and History
                    Mental State
                    Capacity, Safeguarding and Risk
                    Summary and Initial Plan
                    Social Circumstances and Employment
                    Keeping Children Safe Assessment

    So, hierarchy at the backend (> forward, < backward keys):

        AssessmentIndex.Name(>) / .Description ('Core Assessment')
            AssessmentStructure.Assessment(<) / .FormGroup(>)
                AssessmentFormGroupsIndex.Name(<) / .Description ('Core Assessment v2')
                AssessmentFormGroupsStructure.name(<) / .FormName(>) ('coreassesspastpsy')
                    AssessmentFormsIndex.FormName(<) / .Description ('Past Psychiatric History and Physical Health')
                    UserAssesscoreassesspastpsy = data
                              _________________(<)
                        UserAssesscoreassesspastpsy.frailty(>) [lookup]
                            UserMasterfrailty.Code(<) / .CodeDescription

- Simplifying views (for core and non-core RiO) could be implemented in the
  preprocessor, or after anonymisation.
  Better to do it in the preprocessor, because this knows about RiO.
  The two points of "RiO knowledge" should be:
    - the preprocessor;
        ... PK, RiO number as integer, views
    - the ddgen_* information in the anonymiser config file.
        ... tables to omit
        ... fields to omit
        ... default actions on fields
            ... e.g. exclude if type12_DeletedDate is None
            ... however, we could also do that more efficiently as a view,
                and that suits all use cases so far.

"""  # noqa

import argparse
import logging
import sys

from sqlalchemy import (
    create_engine,
    inspect,
    MetaData,
)

from crate_anon.anonymise.constants import MYSQL_CHARSET
from crate_anon.anonymise.logsupport import configure_logger_for_colour

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

AUTONUMBER_COLTYPE = "INTEGER IDENTITY(1, 1) NOT NULL"
# ... is specific to SQL Server, which is what RiO uses.
#     MySQL equivalent would be "INTEGER PRIMARY KEY AUTO_INCREMENT" or
#     "INTEGER UNIQUE KEY AUTO_INCREMENT".
#     (MySQL allows only one auto column and it must be a key.)
#     (This also does the indexing.)

# Tables in RiO v6.2 Core:
RIO_TABLE_MASTER_PATIENT = "ClientIndex"
RIO_TABLE_ADDRESS = "ClientAddress"
RIO_TABLE_PROGRESS_NOTES = "PrgProgressNote"
# Columns in RiO Core:
RIO_COL_PATIENT_ID = "ClientID"  # RiO 6.2: VARCHAR(15)
RIO_COL_NHS_NUMBER = "NNN"  # RiO 6.2: CHAR(10) ("National NHS Number")
RIO_COL_POSTCODE = "PostCode"  # ClientAddress.PostCode
RIO_COL_DEFAULT_PK = "SequenceID"  # INT
RIO_COL_USER_ASSESS_DEFAULT_PK = "type12_NoteID"

# Tables in RiO CRIS Extract Program (RCEP) output database:
RCEP_TABLE_MASTER_PATIENT = "Client_Demographic_Details"
RCEP_TABLE_ADDRESS = "Client_Address_History"
RCEP_TABLE_PROGRESS_NOTES = "Progress_Notes"
# Columns in RCEP extract:
RCEP_COL_PATIENT_ID = "Client_ID"  # RCEP: VARCHAR(15)
RCEP_COL_NHS_NUMBER = "NHS_Number"  # RCEP: CHAR(10)
RCEP_COL_POSTCODE = "Post_Code"  # RCEP: NVARCHAR(10)
# ... general format (empirically): "XX12 3YY" or "XX1 3YY"; "ZZ99" for unknown
# This matches the ONPD "pdcs" format.
RCEP_COL_MANGLED_KEY = "Document_ID"

# CPFT hacks (RiO tables added to RCEP output):
CPFT_RCEP_TABLE_FULL_PROGRESS_NOTES = "Progress_Notes_II"

# Columns in ONS Postcode Database (from CRATE import):
ONSPD_TABLE_POSTCODE = "postcode"
DEFAULT_GEOG_COLS = [
    "pcon", "pct", "nuts", "lea", "statsward", "casward",
    "lsoa01", "msoa01", "ur01ind", "oac01", "lsoa11",
    "msoa11", "parish", "bua11", "buasd11", "ru11ind",
    "oac11", "imd",
]

# Columns added:
CRATE_COL_PK = "crate_pk"
# Do NOT use 'id'; this appears in RiO ClientAlternativeId /
# RCEP Client_Alternative_ID. "pk" is OK for RCEP + RiO, but clarity is good
CRATE_COL_RIO_NUMBER = "crate_rio_number"
# "rio_number" is OK for RCEP + RiO, but clarity is good
CRATE_COL_NHS_NUMBER = "crate_nhs_number_int"
# "nhs_number_int" is OK for RCEP + RiO, but again...
# For RCEP, in SQL Server, check existing columns with:
#   USE database;
#   SELECT column_name, table_name
#       FROM information_schema.columns
#       WHERE column_name = 'something';
# For RiO, for now, check against documented table structure.

# For progress notes:
CRATE_COL_MAX_SUBNUM = "crate_max_subnum_for_notenum"
CRATE_COL_LAST_NOTE = "crate_last_note_in_edit_chain"

# Indexes added:
CRATE_IDX_PK = "crate_idx_pk"  # for any patient table
CRATE_IDX_RIONUM = "crate_idx_rionum"  # for any patient table
CRATE_IDX_RIONUM_NOTENUM = "crate_idx_rionum_notenum"  # for Progress Notes
CRATE_IDX_MAX_SUBNUM = "crate_idx_max_subnum"
CRATE_IDX_LAST_NOTE = "crate_idx_last_note"

# Views added:
VIEW_PROGRESS_NOTES_CURRENT = "progress_notes_current"
VIEW_ADDRESS_WITH_GEOGRAPHY = "client_address_with_geography"

RIO_6_2_ATYPICAL_PKS = {
    # These are table: pk_field mappings for PATIENT tables, i.e. those
    # containing the ClientID field, where that PK is not the default of
    # SequenceID.

    # -------------------------------------------------------------------------
    # RiO Core
    # -------------------------------------------------------------------------

    # Ams*: Appointment Management System
    'AmsAppointmentContactActivity': 'ActivitySequenceID',
    'AmsAppointmentOtherHCP': None,  # non-patient; non-unique SequenceID
    # ... SequenceID is non-unique and the docs also list it as an FK;
    #     ActivitySequenceID this is unique and a PK
    'AmsReferralDatesArchive': 'AMSSequenceID',
    # ... UNVERIFIED as no rows in our data; listed as a PK and an FK
    'AmsReferralListUrgency': None,
    'AmsReferralListWaitingStatus': None,
    'AmsStream': None,  # non-patient; non-unique SequenceID

    'CarePlanIndex': 'CarePlanID',
    'CarePlanProblemOrder': None,

    'ClientAddressMerged': None,  # disused table
    'ClientCareSpell': None,  # CareSpellNum is usually 1 for a given ClientID
    'ClientDocumentAdditionalClient': None,
    'ClientFamily': None,
    'ClientFamilyLink': None,
    'ClientGPMerged': None,
    'ClientHealthCareProvider': None,
    'ClientMerge': None,
    'ClientMerged': None,
    'ClientName': 'ClientNameID',
    'ClientOtherDetail': None,  # not in docs, but looks like Core
    'ClientPhoto': None,
    'ClientPhotoMerged': None,
    'ClientProperty': None,
    'ClientPropertyMerged': None,
    'ClientTelecom': 'ClientTelecomID',
    'ClientUpdatePDSCache': None,

    # Con*: Contracts
    'Contract': 'ContractNumber',
    'ConAdHocAwaitingApproval': 'SequenceNo',
    'ConClientInitialBedRate': None,
    'ConClinicHistory': 'SequenceNo',
    'ConLeaveDiscountHistory': 'SequenceNo',

    # Not documented, but looks like Core
    'Deceased': None,  # or possibly TrustWideID (or just ClientID!)

    'DemClientDeletedDetails': None,

    # EP: E-Prescribing
    # ... with DA: Drug Administration
    # ... with DS: Drug Service
    'EPClientConditions': 'RowID',
    'EPClientPrescription': 'PrescriptionID',
    'EPClientSensitivities': None,  # UNVERIFIED: None? Joint PK on ProdID?
    'EPDiscretionaryDrugClientLink': None,
    'EPVariableDosageDrugLink': 'HistoryID',  # UNVERIFIED
    'EPClientAllergies': 'ReactionID',
    'DAConcurrencyControl': None,
    'DAIPPrescription': 'PrescriptionID',
    'DSBatchPatientGroups': None,
    'DSMedicationBatchContinue': None,
    'DSMedicationBatchLink': None,

    # Ims*: Inpatient Management System
    'ImsEventLeave': 'UniqueSequenceID',  # SequenceID
    'ImsEventMovement': None,
    'ImsEventRefno': None,  # Not in docs but looks like Core.
    'ImsEventRefnoBAKUP': None,  # [Sic.] Not in docs but looks like Core.

    # LR*: Legitimate Relationships
    'LRIdentifiedCache': None,

    # Mes*: messaging
    'MesLettersGenerated': 'Reference',

    # Mnt*: Mental Health module (re MHA detention)
    'MntArtAttendee': None,  # SequenceID being "of person within a meeting"
    'MntArtOutcome': None,  # ditto
    'MntArtPanel': None,  # ditto
    'MntArtRpts': None,  # ditto
    'MntArtRptsReceived': None,  # ditto
    'MntClientEctSection62': None,
    'MntClientMedSection62': None,
    'MntClientSectionDetailCareCoOrdinator': None,
    'MntClientSectionDetailCourtAppearance': None,
    'MntClientSectionDetailFMR': None,
    'MntClientSectionReview': None,

    # NDTMS*: Nation(al?) Drug Treatment Monitoring System

    # SNOMED*: SNOMED
    'SNOMED_Client': 'SC_ID',

    # UserAssess*: user assessment (= non-core?) tables.
    # See other default PK below: type12:

    # -------------------------------------------------------------------------
    # Non-core? No docs available.
    # -------------------------------------------------------------------------
    # Chd*: presumably, child development
    'ChdClientDevCheckBreastFeeding': None,
    # ... guess; DevChkSeqID is probably FK to ChdClientDevCheck.SequenceID

    # ??? But it has q1-q30, qu2-14, home, sch, comm... assessment tool...
    'CYPcurrentviewImport': None,  # not TrustWideID (which is non-unique)

    'GoldmineIfcMapping': None,  # no idea, really, and no data to explore

    'KP90ErrorLog': None,

    'ReportsOutpatientWaitersHashNotSeenReferrals': None,
    'ReportsOutpatientWaitersNotSeenReferrals': None,
}

RIO_6_2_ATYPICAL_PATIENT_ID_COLS = {
    'SNOMED_Client': 'SC_ClientID',
}


# =============================================================================
# Ancillary functions
# =============================================================================

def die(msg):
    log.critical(msg)
    sys.exit(1)


def format_sql_for_print(sql):
    # Remove blank lines and trailing spaces
    lines = list(filter(None, [x.replace("\t", "    ").rstrip()
                               for x in sql.splitlines()]))
    # Shift all lines left if they're left-padded
    firstleftpos = float('inf')
    for line in lines:
        leftpos = len(line) - len(line.lstrip())
        firstleftpos = min(firstleftpos, leftpos)
    if firstleftpos > 0:
        lines = [x[firstleftpos:] for x in lines]
    return "\n".join(lines)


def sql_fragment_cast_to_int(expr):
    # Conversion to INT:
    # http://stackoverflow.com/questions/2000045
    # http://stackoverflow.com/questions/14719760  # this one
    # http://stackoverflow.com/questions/14692131
    return "CASE WHEN {expr} NOT LIKE '%[^0-9]%' " \
           "THEN CAST({expr} AS INTEGER) ELSE NULL END".format(expr=expr)


def execute(engine, progargs, sql):
    log.debug(sql)
    if progargs.print:
        print(format_sql_for_print(sql) + "\n;")
        # extra \n in case the SQL ends in a comment
    else:
        engine.execute(sql)


def add_columns(engine, progargs, table, name_coltype_dict):
    existing_column_names = get_column_names(engine, table=table,
                                             to_lower=True)
    column_defs = []
    for name, coltype in name_coltype_dict.items():
        if name.lower() not in existing_column_names:
            column_defs.append("{} {}".format(name, coltype))
        else:
            log.debug("Table '{}': column '{}' already exists; not "
                      "adding".format(table.name, name))
    # ANSI SQL: add one column at a time: ALTER TABLE ADD [COLUMN] coldef
    #   - i.e. "COLUMN" optional, one at a time, no parentheses
    #   - http://www.contrib.andrew.cmu.edu/~shadow/sql/sql1992.txt
    # MySQL: ALTER TABLE ADD [COLUMN] (a INT, b VARCHAR(32));
    #   - i.e. "COLUMN" optional, parentheses required for >1, multiple OK
    #   - http://dev.mysql.com/doc/refman/5.7/en/alter-table.html
    # MS SQL Server: ALTER TABLE ADD COLUMN a INT, B VARCHAR(32);
    #   - i.e. no "COLUMN", no parentheses, multiple OK
    #   - https://msdn.microsoft.com/en-us/library/ms190238.aspx
    #   - https://msdn.microsoft.com/en-us/library/ms190273.aspx
    #   - http://stackoverflow.com/questions/2523676/alter-table-add-multiple-columns-ms-sql  # noqa
    # SQLAlchemy doesn't provide a shortcut for this.
    for column_def in column_defs:
        log.info("Table '{}': adding column {}".format(
            table.name, column_def))
        execute(engine, progargs, """
            ALTER TABLE {tablename} ADD {column_def}
        """.format(tablename=table.name, column_def=column_def))


def drop_columns(engine, progargs, table, column_names):
    existing_column_names = get_column_names(engine, table=table,
                                             to_lower=True)
    for name in column_names:
        if name.lower() not in existing_column_names:
            log.debug("Table '{}': column '{}' does not exist; not "
                      "dropping".format(table.name, name))
        else:
            log.info("Table '{}': dropping column '{}'".format(table.name,
                                                               name))
            sql = "ALTER TABLE {t} DROP COLUMN {c}".format(t=table.name,
                                                           c=name)
            # SQL Server: http://www.techonthenet.com/sql_server/tables/alter_table.php  # noqa
            # MySQL: http://dev.mysql.com/doc/refman/5.7/en/alter-table.html
            execute(engine, progargs, sql)


def add_indexes(engine, progargs, table, indexdictlist):
    existing_index_names = get_index_names(engine, table=table, to_lower=True)
    for idxdefdict in indexdictlist:
        index_name = idxdefdict['index_name']
        column = idxdefdict['column']
        unique = idxdefdict.get('unique', False)
        if index_name.lower() not in existing_index_names:
            log.info("Table '{}': adding index '{}' on columns '{}'".format(
                table.name, index_name, column))
            execute(engine, progargs, """
              CREATE{unique} INDEX {idxname} ON {tablename} ({column})
            """.format(
                unique=" UNIQUE" if unique else "",
                idxname=index_name,
                tablename=table.name,
                column=column,
            ))
        else:
            log.debug("Table '{}': index '{}' already exists; not "
                      "adding".format(table.name, index_name))


def drop_indexes(engine, progargs, table, index_names):
    existing_index_names = get_index_names(engine, table=table, to_lower=True)
    for index_name in index_names:
        if index_name.lower() not in existing_index_names:
            log.debug("Table '{}': index '{}' does not exist; not "
                      "dropping".format(table.name, index_name))
        else:
            log.info("Table '{}': dropping index '{}'".format(table.name,
                                                              index_name))
            if engine.dialect.name == 'mysql':
                sql = "ALTER TABLE {t} DROP INDEX {i}".format(t=table.name,
                                                              i=index_name)
            elif engine.dialect.name == 'mssql':
                sql = "DROP INDEX {t}.{i}".format(t=table.name, i=index_name)
            else:
                assert False, "Unknown dialect: {}".format(engine.dialect.name)
            execute(engine, progargs, sql)


def get_view_names(engine, to_lower=False, sort=False):
    inspector = inspect(engine)
    view_names = inspector.get_view_names()
    if to_lower:
        view_names = [x.lower() for x in view_names]
    if sort:
        view_names = sorted(view_names, key=lambda x: x.lower())
    return view_names


def get_column_names(engine, tablename=None, table=None, to_lower=False,
                     sort=False):
    """
    Reads columns names afresh from the database (in case metadata is out of
    date.
    """
    assert (table is not None) != bool(tablename), "Need table XOR tablename"
    tablename = tablename or table.name
    inspector = inspect(engine)
    columns = inspector.get_columns(tablename)
    column_names = [x['name'] for x in columns]
    if to_lower:
        column_names = [x.lower() for x in column_names]
    if sort:
        column_names = sorted(column_names, key=lambda x: x.lower())
    return column_names


def get_index_names(engine, tablename=None, table=None, to_lower=False):
    """
    Reads index names from the database.
    """
    # http://docs.sqlalchemy.org/en/latest/core/reflection.html
    assert (table is not None) != bool(tablename), "Need table XOR tablename"
    tablename = tablename or table.name
    inspector = inspect(engine)
    indexes = inspector.get_indexes(tablename)
    index_names = [x['name'] for x in indexes if x['name']]
    # ... at least for SQL Server, there always seems to be a blank one
    # with {'name': None, ...}.
    if to_lower:
        index_names = [x.lower() for x in index_names]
    return index_names


def ensure_columns_present(engine, table=None, tablename=None,
                           column_names=None):
    assert column_names, "Need column_names"
    assert (table is not None) != bool(tablename), "Need table XOR tablename"
    tablename = tablename or table.name
    existing_column_names = get_column_names(engine, tablename=tablename,
                                             to_lower=True)
    for col in column_names:
        if col.lower() not in existing_column_names:
            die("Column '{}' missing from table '{}'".format(col, tablename))


def create_view(engine, progargs, viewname, select_sql):
    # MySQL has CREATE OR REPLACE VIEW.
    # SQL Server doesn't: http://stackoverflow.com/questions/18534919
    if engine.dialect.name == 'mysql':
        sql = "CREATE OR REPLACE VIEW {viewname} AS {select_sql}".format(
            viewname=viewname,
            select_sql=select_sql,
        )
    else:
        drop_view(engine, progargs, viewname, quiet=True)
        sql = "CREATE VIEW {viewname} AS {select_sql}".format(
            viewname=viewname,
            select_sql=select_sql,
        )
    log.info("Creating view: '{}'".format(viewname))
    execute(engine, progargs, sql)


def drop_view(engine, progargs, viewname, quiet=False):
    # MySQL has DROP VIEW IF EXISTS, but SQL Server only has that from
    # SQL Server 2016 onwards.
    # - https://msdn.microsoft.com/en-us/library/ms173492.aspx
    # - http://dev.mysql.com/doc/refman/5.7/en/drop-view.html
    view_names = get_view_names(engine, to_lower=True)
    if viewname.lower() not in view_names:
        log.debug("View {} does not exist; not dropping".format(viewname))
    else:
        if not quiet:
            log.info("Dropping view: '{}'".format(viewname))
        sql = "DROP VIEW {viewname}".format(viewname=viewname)
        execute(engine, progargs, sql)


# =============================================================================
# Generic table processors
# =============================================================================

def table_is_rio_type(tablename, progargs):
    if progargs.rio:
        return True
    if not progargs.cpft:
        return False
    # RCEP + CPFT modifications: there's one RiO table in the mix
    return tablename == progargs.full_prognotes_table


def get_rio_pk_col_patient_table(table):
    if table.name.startswith('UserAssess'):
        default = RIO_COL_USER_ASSESS_DEFAULT_PK
    else:
        default = RIO_COL_DEFAULT_PK
    pkcol = RIO_6_2_ATYPICAL_PKS.get(table.name, default)
    # log.debug("get_rio_pk_col: {} -> {}".format(table.name, pkcol))
    return pkcol


def get_rio_patient_id_col(table):
    patient_id_col = RIO_6_2_ATYPICAL_PATIENT_ID_COLS.get(table.name,
                                                          RIO_COL_PATIENT_ID)
    # log.debug("get_rio_patient_id_col: {} -> {}".format(table.name,
    #                                                     patient_id_col))
    return patient_id_col


def get_rio_pk_col_nonpatient_table(table):
    if RIO_COL_DEFAULT_PK in table.columns.keys():
        default = RIO_COL_DEFAULT_PK
    else:
        default = None
    return RIO_6_2_ATYPICAL_PKS.get(table.name, default)


def process_patient_table(table, engine, progargs):
    log.info("Patient table: '{}'".format(table.name))
    rio_type = table_is_rio_type(table.name, progargs)
    if rio_type:
        rio_pk = get_rio_pk_col_patient_table(table)
        string_pt_id = get_rio_patient_id_col(table)
        required_cols = [string_pt_id]
    else:  # RCEP type
        rio_pk = None
        required_cols = [RCEP_COL_PATIENT_ID]
        string_pt_id = RCEP_COL_PATIENT_ID
    if not progargs.print:
        required_cols.extend([CRATE_COL_PK, CRATE_COL_RIO_NUMBER])
    # -------------------------------------------------------------------------
    # Add pk and rio_number columns, if not present
    # -------------------------------------------------------------------------
    if rio_type and rio_pk is not None:
        crate_pk_type = 'INTEGER'  # can't do NOT NULL; need to populate it
        required_cols.append(rio_pk)
    else:  # RCEP type, or no PK in RiO
        crate_pk_type = AUTONUMBER_COLTYPE  # autopopulates
    add_columns(engine, progargs, table, {
        CRATE_COL_PK: crate_pk_type,
        CRATE_COL_RIO_NUMBER: 'INTEGER',
    })

    # -------------------------------------------------------------------------
    # Update pk and rio_number values, if not NULL
    # -------------------------------------------------------------------------
    ensure_columns_present(engine, table=table, column_names=required_cols)
    log.info("Table '{}': updating columns '{}' and '{}'".format(
        table.name, CRATE_COL_PK, CRATE_COL_RIO_NUMBER))
    cast_id_to_int = sql_fragment_cast_to_int(string_pt_id)
    if rio_type and rio_pk:
        execute(engine, progargs, """
            UPDATE {tablename} SET
                {crate_pk} = {rio_pk},
                {crate_rio_number} = {cast_id_to_int}
            WHERE
                {crate_pk} IS NULL
                OR {crate_rio_number} IS NULL
        """.format(
            tablename=table.name,
            crate_pk=CRATE_COL_PK,
            rio_pk=rio_pk,
            crate_rio_number=CRATE_COL_RIO_NUMBER,
            cast_id_to_int=cast_id_to_int,
        ))
    else:
        # RCEP format, or RiO with no PK
        # crate_pk is autogenerated as an INT IDENTITY field
        execute(engine, progargs, """
            UPDATE {tablename} SET
                {crate_rio_number} = {cast_id_to_int}
            WHERE
                {crate_rio_number} IS NULL
        """.format(  # noqa
            tablename=table.name,
            crate_rio_number=CRATE_COL_RIO_NUMBER,
            cast_id_to_int=cast_id_to_int,
        ))
    """
    Chucked:
        ensure_columns_present(... RCEP_COL_MANGLED_KEY...)

        {pk} = CAST(
            SUBSTRING(
                {rcep_mangled_pk},
                CHARINDEX('_', {rcep_mangled_pk}) + 1,
                LEN({rcep_mangled_pk}) - CHARINDEX('_', {rcep_mangled_pk})
            ) AS INTEGER
        ),

        # pk=CRATE_COL_PK,
        # rcep_mangled_pk=RCEP_COL_MANGLED_KEY,
    """
    # -------------------------------------------------------------------------
    # Add indexes, if absent
    # -------------------------------------------------------------------------
    # Note that the indexes are unlikely to speed up the WHERE NOT NULL search
    # above, so it doesn't matter that we add these last. Their use is for
    # the subsequent CRATE anonymisation table scans.
    add_indexes(engine, progargs, table, [
        {
            'index_name': CRATE_IDX_PK,
            'column': CRATE_COL_PK,
            'unique': True,
        },
        {
            'index_name': CRATE_IDX_RIONUM,
            'column': CRATE_COL_RIO_NUMBER,
        },
    ])


def drop_for_patient_table(table, engine, progargs):
    drop_indexes(engine, progargs, table, [CRATE_IDX_PK, CRATE_IDX_RIONUM])
    drop_columns(engine, progargs, table, [CRATE_COL_PK, CRATE_COL_RIO_NUMBER])


def process_nonpatient_table(table, engine, progargs):
    if progargs.rcep:
        return
    pk_col = get_rio_pk_col_nonpatient_table(table)
    if pk_col:
        add_columns(engine, progargs, table, {CRATE_COL_PK: 'INTEGER'})
    else:
        add_columns(engine, progargs, table,
                    {CRATE_COL_PK: AUTONUMBER_COLTYPE})
    if not progargs.print:
        ensure_columns_present(engine, table=table,
                               column_names=[CRATE_COL_PK])
    if pk_col:
        execute(engine, progargs, """
            UPDATE {tablename} SET {crate_pk} = {rio_pk}
            WHERE {crate_pk} IS NULL
        """.format(tablename=table.name,
                   crate_pk=CRATE_COL_PK,
                   rio_pk=pk_col))
    add_indexes(engine, progargs, table, [{'index_name': CRATE_IDX_PK,
                                           'column': CRATE_COL_PK,
                                           'unique': True}])


def drop_for_nonpatient_table(table, engine, progargs):
    drop_indexes(engine, progargs, table, [CRATE_IDX_PK])
    drop_columns(engine, progargs, table, [CRATE_COL_PK])


# =============================================================================
# Specific table processors
# =============================================================================

def process_master_patient_table(table, engine, progargs):
    add_columns(engine, progargs, table, {
        CRATE_COL_NHS_NUMBER: 'BIGINT',
    })
    if progargs.rcep:
        nhscol = RCEP_COL_NHS_NUMBER
    else:
        nhscol = RIO_COL_NHS_NUMBER
    log.info("Table '{}': updating column '{}'".format(table.name, nhscol))
    ensure_columns_present(engine, table=table, column_names=[nhscol])
    if not progargs.print:
        ensure_columns_present(engine, table=table, column_names=[
            CRATE_COL_NHS_NUMBER])
    execute(engine, progargs, """
        UPDATE {tablename} SET
            {nhs_number_int} = CAST({nhscol} AS BIGINT)
            WHERE {nhs_number_int} IS NULL
    """.format(
        tablename=table.name,
        nhs_number_int=CRATE_COL_NHS_NUMBER,
        nhscol=nhscol,
    ))


def drop_for_master_patient_table(table, engine, progargs):
    drop_columns(engine, progargs, table, [CRATE_COL_NHS_NUMBER])


def process_progress_notes(table, engine, progargs):
    add_columns(engine, progargs, table, {
        CRATE_COL_MAX_SUBNUM: 'INTEGER',
        CRATE_COL_LAST_NOTE: 'INTEGER',
    })
    # We're always in "RiO land", not "RCEP land", for this one.
    add_indexes(engine, progargs, table, [
        {  # Joint index, for JOIN in UPDATE statement below
            'index_name': CRATE_IDX_RIONUM_NOTENUM,
            'column': '{rio_number}, NoteNum'.format(
                rio_number=CRATE_COL_RIO_NUMBER),
        },
        {  # Speeds up WHERE below. (Much, much faster for second run.)
            'index_name': CRATE_IDX_MAX_SUBNUM,
            'column': CRATE_COL_MAX_SUBNUM,
        },
        {  # Speeds up WHERE below. (Much, much faster for second run.)
            'index_name': CRATE_IDX_LAST_NOTE,
            'column': CRATE_COL_LAST_NOTE,
        },
    ])

    ensure_columns_present(engine, table=table, column_names=[
        "NoteNum", "SubNum", "EnteredInError", "EnteredInError"])
    if not progargs.print:
        ensure_columns_present(engine, table=table, column_names=[
            CRATE_COL_MAX_SUBNUM, CRATE_COL_LAST_NOTE, CRATE_COL_RIO_NUMBER])

    # Find the maximum SubNum for each note, and store it.
    # Slow query, even with index.
    log.info("Progress notes table '{}': "
             "updating 'max_subnum_for_notenum'".format(table.name))
    execute(engine, progargs, """
        UPDATE p1
        SET p1.{max_subnum_col} = subq.max_subnum
        FROM {tablename} p1 JOIN (
            SELECT {rio_number}, NoteNum, MAX(SubNum) AS max_subnum
            FROM {tablename} p2
            GROUP BY {rio_number}, NoteNum
        ) subq
        ON subq.{rio_number} = p1.{rio_number}
        AND subq.NoteNum = p1.NoteNum
        WHERE p1.{max_subnum_col} IS NULL
    """.format(
        max_subnum_col=CRATE_COL_MAX_SUBNUM,
        tablename=table.name,
        rio_number=CRATE_COL_RIO_NUMBER,
    ))

    # Set a single column accordingly
    log.info("Progress notes table '{}': "
             "updating 'last_note_in_edit_chain'".format(table.name))
    execute(engine, progargs, """
        UPDATE {tablename} SET
            {last_note_col} =
                CASE
                    WHEN SubNum = {max_subnum_col} THEN 1
                    ELSE 0
                END
        WHERE {last_note_col} IS NULL
    """.format(
        tablename=table.name,
        last_note_col=CRATE_COL_LAST_NOTE,
        max_subnum_col=CRATE_COL_MAX_SUBNUM,
    ))

    # Create a view
    select_sql = """
        SELECT *
        FROM {tablename}
        WHERE
            (EnteredInError <> 1 OR EnteredInError IS NULL)
            AND {last_note_col} = 1
    """.format(
        tablename=table.name,
        last_note_col=CRATE_COL_LAST_NOTE,
    )
    create_view(engine, progargs, VIEW_PROGRESS_NOTES_CURRENT, select_sql)


def drop_for_progress_notes(table, engine, progargs):
    drop_view(engine, progargs, VIEW_PROGRESS_NOTES_CURRENT)
    drop_indexes(engine, progargs, table, [CRATE_IDX_RIONUM_NOTENUM,
                                           CRATE_IDX_MAX_SUBNUM,
                                           CRATE_IDX_LAST_NOTE])
    drop_columns(engine, progargs, table, [CRATE_COL_MAX_SUBNUM,
                                           CRATE_COL_LAST_NOTE])


# =============================================================================
# RiO view creators: generic
# =============================================================================

class ViewMaker(object):
    def __init__(self, progargs, engine, basetable, existing_to_lower=False,
                 rename=None):
        rename = rename or {}
        self.progargs = progargs
        self.engine = engine
        self.basetable = basetable
        self.select_elements = []
        for colname in get_column_names(engine, tablename=basetable,
                                        to_lower=existing_to_lower):
            if colname in rename:
                rename_to = rename[colname]
                if not rename_to:
                    continue
                as_clause = " AS {}".format(rename_to)
            else:
                as_clause = ""
            self.select_elements.append("{t}.{c}{as_clause}".format(
                t=basetable, c=colname, as_clause=as_clause))
        assert self.select_elements, "Must have some active SELECT elements " \
                                     "from base table"
        self.from_elements = [basetable]
        self.where_elements = []
        self.lookup_tables = set()
        
    def add_select(self, clause):
        self.select_elements.append(clause)
        
    def add_from(self, clause):
        self.from_elements.append(clause)
        
    def add_where(self, clause):
        self.where_elements.append(clause)
        
    def get_sql(self):
        if self.where_elements:
            where = "\n    WHERE {}".format(
                "\n        AND ".join(self.where_elements))
        else:
            where = ""
        return (
            "\n    SELECT {select_elements}"
            "\n    FROM {from_elements}{where}".format(
                select_elements=",\n        ".join(self.select_elements),
                from_elements="\n        ".join(self.from_elements),
                where=where))

    def record_lookup_table(self, table):
        self.lookup_tables.add(table)

    def record_lookup_tables(self, tables):
        for t in tables:
            self.record_lookup_table(t)

    def get_lookup_table(self):
        return list(self.lookup_tables)


def simple_lookup_join(viewmaker, basecolumn,
                       lookup_table, lookup_pk, lookup_fields_aliases,
                       internal_alias_prefix):
    aliased_table = internal_alias_prefix + "_" + lookup_table
    for column, alias in lookup_fields_aliases.items():
        viewmaker.add_select("{aliased_table}.{column} AS {alias}".format(
            aliased_table=aliased_table, column=column, alias=alias))
    viewmaker.add_from(
        "LEFT JOIN {lookup_table} {aliased_table}\n"
        "            ON {aliased_table}.{lookup_pk} = "
        "{basetable}.{basecolumn}".format(
            lookup_table=lookup_table,
            aliased_table=aliased_table,
            lookup_pk=lookup_pk,
            basetable=viewmaker.basetable,
            basecolumn=basecolumn))
    viewmaker.record_lookup_table(lookup_table)


def standard_rio_code_lookup(viewmaker, basecolumn, lookup_table,
                             result_alias, internal_alias_prefix):
    return simple_lookup_join(
        viewmaker=viewmaker,
        basecolumn=basecolumn,
        lookup_table=lookup_table,
        lookup_pk="Code",
        lookup_fields_aliases={'CodeDescription': result_alias},
        internal_alias_prefix=internal_alias_prefix)


def view_formatting_dict(viewmaker):
    return {
        'basetable': viewmaker.basetable,
    }


def simple_view_expr(viewmaker, expr, alias):
    vd = view_formatting_dict(viewmaker)
    formatted_expr = expr.format(**vd)
    viewmaker.add_select(formatted_expr + " AS {}".format(alias))


def simple_view_where(viewmaker, where_clause):
    viewmaker.add_where(where_clause)


def get_rio_views(engine, metadata, progargs, ddhint,
                  suppress_basetables=True, suppress_lookup=True):
    # ddhint modified
    # Returns dictionary of {viewname: select_sql} pairs.
    views = {}
    all_tables_lower = [t.name.lower() for t in metadata.tables.values()]
    for viewname, viewdetails in RIO_VIEWS.items():
        basetable = viewdetails['basetable']
        if basetable.lower() not in all_tables_lower:
            log.warning("Skipping view {} as base table {} not present".format(
                viewname, basetable))
            continue
        suppress_basetable = viewdetails.get('suppress_basetable',
                                             suppress_basetables)
        suppress_other_tables = viewdetails.get('suppress_other_tables', [])
        if suppress_basetable:
            ddhint.suppress_table(basetable)
        ddhint.suppress_tables(suppress_other_tables)
        rename = viewdetails.get('rename', None)
        # noinspection PyTypeChecker
        viewmaker = ViewMaker(progargs, engine, basetable, rename=rename)
        if 'add' in viewdetails:
            for addition in viewdetails['add']:
                function = addition['function']
                kwargs = addition['kwargs']
                kwargs['viewmaker'] = viewmaker
                function(**kwargs)  # will alter viewmaker
        views[viewname] = viewmaker.get_sql()
        if suppress_lookup:
            ddhint.suppress_tables(viewmaker.get_lookup_table())
    return views


def create_rio_views(engine, metadata, progargs, ddhint):  # ddhint modified
    rio_views = get_rio_views(engine, metadata, progargs, ddhint)
    for viewname, select_sql in rio_views.items():
        create_view(engine, progargs, viewname, select_sql)


def drop_rio_views(engine, metadata, progargs, ddhint):  # ddhint modified
    rio_views, _ = get_rio_views(engine, metadata, progargs, ddhint)
    for viewname, _ in rio_views.items():
        drop_view(engine, progargs, viewname)


# =============================================================================
# RiO view creators: specific
# =============================================================================

def rio_add_user_lookup(viewmaker, basecolumn,
                        column_prefix=None, internal_alias_prefix=None):
    # NOT VERIFIED IN FULL - insufficient data with just top 1000 rows for
    # each table (2016-07-12).
    column_prefix = column_prefix or basecolumn
    internal_alias_prefix = internal_alias_prefix or "t_" + column_prefix
    # ... table alias
    viewmaker.add_select("""
        {basetable}.{basecolumn_usercode} AS {cp}_code,

        {ap}_genhcp.ConsultantFlag AS {cp}_consultant_flag,

        {ap}_genperson.Email AS {cp}_email,
        {ap}_genperson.Title AS {cp}_title,
        {ap}_genperson.FirstName AS {cp}_first_name,
        {ap}_genperson.Surname AS {cp}_surname,

        {ap}_prof.Code AS {cp}_responsible_clinician_profession_code,
        {ap}_prof.CodeDescription AS {cp}_responsible_clinician_profession_description,

        {ap}_serviceteam.Code AS {cp}_primary_team_code,
        {ap}_serviceteam.CodeDescription AS {cp}_primary_team_description,

        {ap}_genspec.Code AS {cp}_main_specialty_code,
        {ap}_genspec.CodeDescription AS {cp}_main_specialty_description,
        {ap}_genspec.NationalCode AS {cp}_main_specialty_national_code,

        {ap}_profgroup.Code AS {cp}_professional_group_code,
        {ap}_profgroup.CodeDescription AS {cp}_professional_group_description,

        {ap}_genorg.Code AS {cp}_organisation_type_code,
        {ap}_genorg.CodeDescription AS {cp}_organisation_type_description
    """.format(  # noqa
        basetable=viewmaker.basetable,
        basecolumn_usercode=basecolumn,
        cp=column_prefix,
        ap=internal_alias_prefix,
    ))
    # - RECP had "speciality" / "specialty" inconsistency.
    # - {cp}_location... ?? Presumably from GenLocation, but via what? Seems
    #   meaningless. In our snapshut, all are NULL anyway.
    # - User codes are keyed to GenUser.GenUserID, but also to several other
    #   tables, e.g. GenHCP.GenHCPCode; GenPerson.GenPersonID
    # - We use unique table aliases here, so that overall we can make >1 sets
    #   of different "user" joins simultaneously.
    viewmaker.add_from("""
        LEFT JOIN (
            GenHCP {ap}_genhcp
            INNER JOIN GenUser {ap}_genuser
                ON {ap}_genhcp.GenHCPCode = {ap}_genuser.GenUserID
            INNER JOIN GenPerson {ap}_genperson
                ON {ap}_genhcp.GenHCPCode = {ap}_genperson.GenPersonID
            LEFT JOIN GenHCPRCProfession {ap}_prof
                ON {ap}_genhcp.RCProfession = {ap}_prof.Code
            LEFT JOIN GenServiceTeam {ap}_serviceteam
                ON {ap}_genhcp.PrimaryTeam = {ap}_serviceteam.Code
            LEFT JOIN GenSpecialty {ap}_genspec
                ON {ap}_genhcp.MainGenSpecialtyCode = {ap}_genspec.Code
            LEFT JOIN GenStaffProfessionalGroup {ap}_profgroup
                ON {ap}_genhcp.StaffProfessionalGroup = {ap}_profgroup.Code
            LEFT JOIN GenOrganisationType {ap}_genorg
                ON {ap}_genuser.OrganisationType = {ap}_genorg.Code
        ) ON {basetable}.{basecolumn_usercode} = {ap}_genhcp.GenHCPCode
    """.format(  # noqa
        basetable=viewmaker.basetable,
        basecolumn_usercode=basecolumn,
        ap=internal_alias_prefix,
    ))
    # OTHER THINGS:
    # - GenHCP.Occupation is listed in the RiO docs but doesn't actually seem
    #   to exist. (Perhaps explaining why it's not linked in the RCEP output.)
    #   I had tried to link it to CareCoordinatorOccupation.Code.
    #   If you use:
    #       SELECT *
    #       FROM information_schema.columns
    #       WHERE column_name LIKE '%Occup%'
    #   you only get Client_Demographic_Details.Occupation and
    #   Client_Demographic_Details.Partner_Occupation
    viewmaker.record_lookup_tables([
        'GenHCP',
        'GenUser',
        'GenPerson',
        'GenHCPRCProfession',
        'GenServiceTeam',
        'GenSpecialty',
        'GenStaffProfessionalGroup',
        'GenOrganisationType',
    ])


def rio_add_consultant_lookup(viewmaker, basecolumn,
                              column_prefix=None, internal_alias_prefix=None):
    column_prefix = column_prefix or basecolumn
    internal_alias_prefix = internal_alias_prefix or "t_" + column_prefix
    viewmaker.add_select("""
        {basetable}.{basecolumn} AS {cp}_id,
        {ap}_cons.Firstname AS {cp}_first_name,
        {ap}_cons.Surname AS {cp}_surname,
        {ap}_cons.SpecialtyID AS {cp}_specialty_code,
        {ap}_spec.CodeDescription AS {cp}_specialty_description
    """.format(  # noqa
        basetable=viewmaker.basetable,
        basecolumn=basecolumn,
        cp=column_prefix,
        ap=internal_alias_prefix,
    ))
    viewmaker.add_from("""
        LEFT JOIN (
            GenHospitalConsultant {ap}_cons
            LEFT JOIN GenSpecialty {ap}_spec
                ON {ap}_spec.Code = {ap}_cons.SpecialtyID
        ) ON {basetable}.{basecolumn} = {ap}_cons.ConsultantID
    """.format(  # noqa
        basetable=viewmaker.basetable,
        basecolumn=basecolumn,
        ap=internal_alias_prefix,
    ))
    viewmaker.record_lookup_tables([
        'GenHospitalConsultant',
        'GenSpecialty',
    ])


def rio_add_team_lookup(viewmaker, basecolumn,
                        column_prefix=None, internal_alias_prefix=None):
    column_prefix = column_prefix or basecolumn
    internal_alias_prefix = internal_alias_prefix or "t_" + column_prefix
    viewmaker.add_select("""
        {basetable}.{basecolumn} AS {cp}_code,
        {ap}_team.CodeDescription AS {cp}_description,
        {ap}_classif.Code AS {cp}_classification_group_code,
        {ap}_classif.CodeDescription AS {cp}_classification_group_description
    """.format(  # noqa
        basetable=viewmaker.basetable,
        basecolumn=basecolumn,
        cp=column_prefix,
        ap=internal_alias_prefix,
    ))
    viewmaker.add_from("""
        LEFT JOIN (
            GenServiceTeam {ap}_team
            INNER JOIN GenServiceTeamClassification {ap}_classif
                ON {ap}_classif.Code = {ap}_team.ClassificationGroup
        ) ON {basetable}.{basecolumn} = {ap}_team.Code
    """.format(  # noqa
        basetable=viewmaker.basetable,
        basecolumn=basecolumn,
        ap=internal_alias_prefix,
    ))
    viewmaker.record_lookup_tables([
        'GenServiceTeam',
        'GenServiceTeamClassification',
    ])


def rio_add_carespell_lookup(viewmaker, basecolumn,
                             column_prefix=None, internal_alias_prefix=None):
    column_prefix = column_prefix or basecolumn
    internal_alias_prefix = internal_alias_prefix or "t_" + column_prefix
    viewmaker.add_select("""
        {ap}_spell.CareSpellNum AS {cp}_Number,
        {ap}_spell.StartDate AS {cp}_Start_Date,
        {ap}_spell.EndDate AS {cp}_End_Date,
        {ap}_spell.MentalHealth AS {cp}_Mental_Health,
        {ap}_spell.GenSpecialtyCode AS {cp}_Specialty_Code,
        {ap}_spec.CodeDescription AS {cp}_Specialty_Description,
        {ap}_spec.NationalCode AS {cp}_Specialty_National_Code
    """.format(  # noqa
        cp=column_prefix,
        ap=internal_alias_prefix,
    ))
    viewmaker.add_from("""
        LEFT JOIN (
            ClientCareSpell {ap}_spell
            INNER JOIN GenSpecialty {ap}_spec
                ON {ap}_spec.Code = {ap}_spell.GenSpecialtyCode
        ) ON {basetable}.{basecolumn} = {ap}_spell.CareSpellNum
    """.format(
        basetable=viewmaker.basetable,
        basecolumn=basecolumn,
        ap=internal_alias_prefix,
    ))
    viewmaker.record_lookup_tables([
        'ClientCareSpell',
        'GenSpecialty',
    ])


def rio_add_diagnosis_lookup(viewmaker,
                             basecolumn_scheme, basecolumn_code,
                             alias_scheme, alias_code, alias_description,
                             internal_alias_prefix=None):
    # Can't use simple_lookup_join as we have to join on two fields,
    # diagnostic scheme and diagnostic code.
    internal_alias_prefix = internal_alias_prefix or "t"
    viewmaker.add_select("""
        {ap}_diag.CodingScheme AS {alias_scheme},
        {ap}_diag.Code AS {alias_code},
        {ap}_diag.CodeDescription AS {alias_description}
    """.format(  # noqa
        ap=internal_alias_prefix,
        alias_scheme=alias_scheme,
        alias_code=alias_code,
        alias_description=alias_description,
    ))
    # - RECP had "speciality" / "specialty" inconsistency.
    # - {cp}_location... ?? Presumably from GenLocation, but via what? Seems
    #   meaningless. In our snapshut, all are NULL anyway.
    # - User codes are keyed to GenUser.GenUserID, but also to several other
    #   tables, e.g. GenHCP.GenHCPCode; GenPerson.GenPersonID
    # - We use unique table aliases here, so that overall we can make >1 sets
    #   of different "user" joins simultaneously.
    viewmaker.add_from("""
        LEFT JOIN DiagnosisCode
            ON {basetable}.{basecolumn_scheme} = {ap}_diag.CodingScheme
            AND {basetable}.{basecolumn_code} = {ap}_diag.Code
    """.format(  # noqa
        basetable=viewmaker.basetable,
        basecolumn_scheme=basecolumn_scheme,
        basecolumn_code=basecolumn_code,
        ap=internal_alias_prefix,
    ))
    viewmaker.record_lookup_table('DiagnosisCode')


# =============================================================================
# RiO view creators: collection
# =============================================================================

RIO_VIEWS = {
    # -------------------------------------------------------------------------
    # Template
    # -------------------------------------------------------------------------
    # 'XXX': {
    #     'basetable': 'XXX',
    #     'rename': {
    #         'XXX': 'XXX',  #
    #         'XXX': None,  #
    #     },
    #     'add': [
    #         {
    #             'function': simple_view_expr,
    #             'kwargs': {
    #                 'expr': 'XXX',
    #                 'alias': 'XXX',
    #             },
    #         },
    #         {
    #             'function': simple_lookup_join,
    #             'kwargs': {
    #                 'basecolumn': 'XXX',
    #                 'lookup_table': 'XXX',
    #                 'lookup_pk': 'XXX',
    #                 'lookup_fields_aliases': {
    #                     'XXX': 'XXX',
    #                 },
    #                 'internal_alias_prefix': 'XXX',
    #             }
    #         },
    #         {
    #             'function': standard_rio_code_lookup,
    #             'kwargs': {
    #                 'basecolumn': 'XXX',
    #                 'lookup_table': 'XXX',
    #                 'result_alias': 'XXX',
    #                 'internal_alias_prefix': 'XXX',
    #             },
    #         },
    #         {
    #             'function': rio_add_user_lookup,
    #             'kwargs': {
    #                 'basecolumn': 'XXX',
    #                 'column_prefix': 'XXX',
    #                 'internal_alias_prefix': 'XXX',
    #             },
    #         },
    #         {
    #             'function': rio_add_consultant_lookup,
    #             'kwargs': {
    #                 'basecolumn': 'XXX',
    #                 'column_prefix': 'XXX',
    #                 'internal_alias_prefix': 'XXX',
    #             },
    #         },
    #         {
    #             'function': rio_add_team_lookup,
    #             'kwargs': {
    #                 'basecolumn': 'XXX',
    #                 'column_prefix': 'XXX',
    #                 'internal_alias_prefix': 'XXX',
    #             },
    #         },
    #         {
    #             'function': rio_add_carespell_lookup,
    #             'kwargs': {
    #                 'basecolumn': 'XXX',
    #                 'column_prefix': 'XXX',
    #                 'internal_alias_prefix': 'XXX',
    #             },
    #         },
    #         {
    #             'function': rio_add_diagnosis_lookup,
    #             'kwargs': {
    #                 'basecolumn_scheme': 'XXX',
    #                 'basecolumn_code': 'XXX',
    #                 'alias_scheme': 'XXX',
    #                 'alias_code': 'XXX',
    #                 'alias_description': 'XXX',
    #                 'internal_alias_prefix': 'XXX',
    #             }
    #         },
    #         {
    #             'function': simple_view_where,
    #             'kwargs': {
    #                 'where_clause': 'XXX',
    #             },
    #         },
    #     ],
    #     'suppress_basetable': True,
    #     'suppress_other_tables': [],
    # },
    # -------------------------------------------------------------------------
    # Core: views provided by RCEP (with some extensions)
    # -------------------------------------------------------------------------
    # 'assessmentsCRISSpec' is RCEP internal for CRIS tree/form/field/... info
    # *** 'Care_Plan_index'
    # *** 'Care_Plan_Interventions'
    # *** 'Care_Plan_Problems'
    # *** 'Client_Address_History'
    # *** 'Client_Alternative_ID'
    # *** 'Client_Allergies'
    # *** 'Client_Communications_History'
    # *** 'Client_CPA'
    # *** 'Client_Demographic_Details'
    # *** 'Client_Family'
    # *** 'Client_GP_History'
    # *** 'Client_Medication'
    # *** 'Client_Name_History'
    # *** 'Client_Personal_Contacts'
    # *** 'Client_Physical_Details'
    # *** 'Client_Prescription'
    # *** 'Client_Professional_Contacts'
    # *** 'Client_School'
    # *** 'CPA_CareCoordinator'
    # *** 'CPA_Review'
    'Diagnosis': {
        'basetable': 'DiagnosisClient',
        'rename': {
            'CodingScheme': None,  # put back in below
            # Comment: unchanged
            'Diagnosis': 'Diagnosis_Code',  # RCEP
            'DiagnosisStartDate': 'Diagnosis_Start_Date',  # RCEP
            'DiagnosisEndDate': 'Diagnosis_End_Date',  # RCEP
            'EntryBy': None,  # RCEP; is user code
            'EntryDate': 'Entry_Date',
            'RemovalBy': None,  # RCEP; is user code
            # RemovalComment: unchanged
            'RemovalDate': 'Removal_Date',
            'RemovalReason': 'Removal_Reason_Code',  # RCEP
        },
        'add': [
            {
                'function': rio_add_diagnosis_lookup,
                'kwargs': {
                    'basecolumn_scheme': 'CodingScheme',
                    'basecolumn_code': 'Diagnosis',
                    'alias_scheme': 'Coding_Scheme',  # RCEP: CodingScheme
                    'alias_code': 'Diagnosis_Code',  # RCEP
                    'alias_description': 'Diagnosis',  # RCEP
                    'internal_alias_prefix': 'd',
                }
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'RemovalReason',
                    'lookup_table': 'DiagnosisRemovalReason',
                    'result_alias': 'Removal_Reason_Description',  # RCEP
                    'internal_alias_prefix': 'rr',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'EntryBy',
                    'column_prefix': 'Entered_By',
                    'internal_alias_prefix': 'eb',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'RemovalBy',
                    'column_prefix': 'Removal_By',
                    'internal_alias_prefix': 'rb',
                },
            },
        ],
    },
    # *** 'Inpatient_Leave'
    # *** 'Inpatient_Movement'
    # *** 'Inpatient_Named_Nurse'
    # *** 'Inpatient_Sleepover'
    # *** 'Inpatient_Stay'
    # 'LSOA_buffer' is RCEP internal, cf. my ONS PD geography database
    'Main_Referral_Data': {
        'basetable': 'AmsReferral',
        'rename': {
            'ReferralNumber': 'Referral_Number',  # RCEP
            'ReferralSource': 'Referral_Source',  # RCEP
            'ReferringGP': 'Referring_GP_Code',  # RCEP
            'ReferringConsultant': None,  # tricky lookup; see below
            # 'Referrer': unchanged; not in RCEP; missing?
            'TeamReferredTo': None,  # not in RCEP; lookup added below
            'ServiceReferredTo': 'Service_Referred_To_Code',  # not in RCEP; lookup added below  # noqa
            'HCPReferredTo': None,  # not in RCEP; lookup added below
            'SpecialtyReferredTo': 'Specialty_Referred_To_Code',  # not in RCEP; lookup added below  # noqa
            'ReferralActionDate': 'Referral_ActionDate',  # not in RCEP; missing?  # noqa
            'ReferralDateTime': 'Referral_DateTime',  # not in RCEP; missing?
            'Urgency': 'Urgency_Code',  # not in RCEP; missing?
            'ReferralComment': 'Referral_Comment',  # not in RCEP; missing?
            'DischargeDateTime': 'Discharge_DateTime',  # not in RCEP; missing?
            'DischargeReason': 'Discharge_Reason',  # not in RCEP; missing?
            'DischargeHCP': None,  # RCEP; user lookup
            'DischargeComment': 'Discharge_Comment',  # RCEP
            'ClientCareSpell': None,  # see lookup below
            'ReferralReason': 'Referral_Reason_Code',  # RCEP
            # RCEP 'Referral_Reason_National_Code': ?? can't find. Only AmsReferralSource.NationalCode  # noqa
            'AdministrativeCategory': 'Administrative_Category_Code',  # RCEP
            'PatientArea': 'Patient_Area',  # RCEP
            'RemovalCode': 'Removal_Code',  # RCEP
            'RemovalUser': None,  # RCEP; user lookup
            'RemovalDateTime': 'Removal_DateTime',  # RCEP
            'ReferralReceivedDate': 'Referral_Received_Date',  # RCEP
            'ReferralAllocation': 'Referral_Allocation',  # RCEP
            'DischargeAllocation': 'Discharge_Allocation',  # RCEP
            'HCPAllocationDate': 'HCP_Allocation_Date',  # RCEP
            'ReferralAcceptedDate': 'Referral_Accepted_Date',  # RCEP
            'IWSComment': 'IWS_Comment',  # RCEP
            'IWSHeld': 'IWS_Held',  # RCEP
            'ReferrerOther': 'Referrer_Other',  # RCEP
            'ReferringGPPracticeCode': 'Referring_GP_Practice_Code',  # RCEP
            'ExternalReferralId': 'External_Referral_Id',  # RCEP (field is not VARCHAR(8000) as docs suggest; 25 in RiO, 50 in RCEP)  # noqa
            'LikelyFunder': 'Likely_Funder',  # RCEP
            # EnquiryNumber: unchanged
            'ReferredWard': 'Referred_Ward_Code',  # RCEP
            'ReferredConsultant': None,  # RCEP; user lookup
            'DischargeAddressLine1': 'Discharge_Address_Line_1',  # RCEP
            'DischargeAddressLine2': 'Discharge_Address_Line_2',  # RCEP
            'DischargeAddressLine3': 'Discharge_Address_Line_3',  # RCEP
            'DischargeAddressLine4': 'Discharge_Address_Line_4',  # RCEP
            'DischargeAddressLine5': 'Discharge_Address_Line_5',  # RCEP
            'DischargePostCode': 'Discharge_Post_Code',  # RCEP
            'LikelyLegalStatus': 'Likely_Legal_Status',  # RCEP
            'CABReferral': 'CAB_Referral',  # RCEP
            'DischargedOnAdmission': 'Discharged_On_Admission',  # RCEP
            'WaitingListID': 'Waiting_List_ID',  # RCEP; FK to WLConfig.WLCode (ignored)  # noqa
            'RTTCode': 'RTT_Code',  # RCEP; FK to RTTPathwayConfig.RTTCode (ignored)  # noqa
        },
        'add': [
            {  # not in RCEP
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'Urgency',
                    'lookup_table': 'GenUrgency',
                    'result_alias': 'Urgency_Description',
                    'internal_alias_prefix': 'ur',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'PatientArea',
                    'lookup_table': 'AmsPatientArea',
                    'result_alias': 'Patient_Area_Description',  # RCEP
                    'internal_alias_prefix': 'pa',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'AdministrativeCategory',
                    'lookup_table': 'GenAdministrativeCategory',
                    'result_alias': 'Administrative_Category_Description',  # RCEP  # noqa
                    'internal_alias_prefix': 'ac',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'ReferralReason',
                    'lookup_table': 'GenReferralReason',
                    'result_alias': 'Referral_Reason_Description',  # RCEP
                    'internal_alias_prefix': 'rr',
                },
            },
            {
                'function': simple_lookup_join,
                'kwargs': {
                    'basecolumn': 'ReferredWard',
                    'lookup_table': 'ImsWard',
                    'lookup_pk': 'WardCode',
                    'lookup_fields_aliases': {
                        'WardDescription': 'Referred_Ward_Description',  # RCEP
                    },
                    'internal_alias_prefix': 'rw',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'DischargeHCP',
                    'column_prefix': 'Discharge_HCP',  # RCEP
                    'internal_alias_prefix': 'dhcp',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'ReferredConsultant',
                    'column_prefix': 'Referred_Consultant',  # RCEP
                    'internal_alias_prefix': 'rc',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'RemovalUser',
                    'column_prefix': 'Removal_User',  # RCEP
                    'internal_alias_prefix': 'ru',
                },
            },
            {
                'function': rio_add_carespell_lookup,
                'kwargs': {
                    'basecolumn': 'ClientCareSpell',
                    'column_prefix': 'Care_Spell',  # RCEP
                    'internal_alias_prefix': 'cs',
                },
            },
            {  # not in RCEP
                'function': rio_add_team_lookup,
                'kwargs': {
                    'basecolumn': 'TeamReferredTo',
                    'column_prefix': 'Team_Referred_To',
                    'internal_alias_prefix': 'trt',
                },
            },
            {  # not in RCEP
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'HCPReferredTo',
                    'column_prefix': 'HCP_Referred_To',
                    'internal_alias_prefix': 'hrt',
                },
            },
            {  # not in RCEP
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'SpecialtyReferredTo',
                    'lookup_table': 'GenSpecialty',
                    'result_alias': 'Specialty_Referred_To_Description',
                    'internal_alias_prefix': 'sprt',
                }
            },
            {  # not in RCEP
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'ServiceReferredTo',
                    'lookup_table': 'GenService',
                    'result_alias': 'Service_Referred_To_Description',
                    'internal_alias_prefix': 'sert',
                }
            },
            # Look up the same field two ways.
            {  # If AmsReferralSource.Behaviour = 'CS'...
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'ReferringConsultant',
                    'column_prefix': 'Referring_Consultant_Cons',
                    'internal_alias_prefix': 'rcc',
                },
            },
            {  # If AmsReferralSource.Behaviour = 'CH'...
                'function': rio_add_consultant_lookup,
                'kwargs': {
                    'basecolumn': 'ReferringConsultant',
                    'column_prefix': 'Referring_Consultant_HCP',  # RCEP: Referring_Consultant_User  # noqa
                    'internal_alias_prefix': 'rch',
                },
            },
        ],
    },
    'Progress_Notes': {
        'basetable': RIO_TABLE_PROGRESS_NOTES,
        'rename': {
            'DateAndTime': 'Created_Date',  # RCEP; RCEP synonym: 'Date'
            'EnterDatetime': 'Updated_Date',  # RCEP
            'VerifyDate': 'Verified_Date',  # RCEP was: Validate_This_Note
            'NoteType': None,  # RCEP; this is a code
            'SubNoteType': None,  # RCEP; this is a code
            'NoteText': 'Text',  # RCEP
            # 'Significant': 'This_Is_A_Significant_Event',  # RCEP
            'ThirdPartyInfo': 'Third_Party_Info',  # RCEP was: This_Note_Contains_Third_Party_Information  # noqa
            'RiskRelated': 'Risk_Related',  # RCEP was: Add_To_Risk_History
            'RiskType': None,  # RCEP; this is a code
            'EnteredInError': 'Entered_In_Error',  # RCEP
            # 'NoteNum': None,  # RCEP
            # 'SubNum': None,  # RCEP
            # 'HTMLIncludedFlag': None,  # RCEP
            'Problem': None,  # RCEP; "obsolete"
            'UserID': None,  # RCEP: ignored? Same as EnteredBy? ***
            'EnteredBy': None,  # RCEP; user lookup
            'VerifyUserID': None,  # RCEP; user lookup
        },
        'add': [
            {  # not in RCEP
                'function': simple_view_expr,
                'kwargs': {
                    'expr': 'CASE WHEN {basetable}.VerifyDate IS NULL THEN 0 '
                            'ELSE 1 END',
                    'alias': 'validated',
                },
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'NoteType',
                    'lookup_table': 'GenUserPrgNoteType',
                    'result_alias': 'Note_Type',  # RCEP
                    'internal_alias_prefix': 'nt',
                }
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'SubNoteType',
                    'lookup_table': 'GenUserPrgNoteSubType',
                    'result_alias': 'Sub_Note_Type',  # RCEP
                    'internal_alias_prefix': 'snt',
                }
            },
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'RiskType',
                    'lookup_table': 'RskRiskType',
                    'result_alias': 'Risk_Type',  # RCEP
                    'internal_alias_prefix': 'rt',
                }
            },
            {  # not in RCEP
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'ClinicalEventType',
                    'lookup_table': 'GenClinicalEventType',
                    'result_alias': 'Clinical_Event_Type_Description',
                    'internal_alias_prefix': 'cet',
                }
            },
            {  # not in RCEP
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'SpecialtyID',
                    'lookup_table': 'GenSpecialty',
                    'result_alias': 'Specialty_Description',
                    'internal_alias_prefix': 'spec',
                }
            },
            {  # not in RCEP
                'function': simple_lookup_join,
                'kwargs': {
                    'basecolumn': 'RoleID',
                    'lookup_table': 'GenUserType',
                    'lookup_pk': 'UserTypeID',
                    'lookup_fields_aliases': {
                        'RoleDescription': 'Role_Description',
                    },
                    'internal_alias_prefix': 'rl',
                }
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'EnteredBy',  # or UserID? ***
                    'column_prefix': 'Originating_User',  # RCEP: was originator_user  # noqa
                    'internal_alias_prefix': 'ou',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'VerifyUserID',
                    'column_prefix': 'Verifying_User',  # RCEP: was verified_by_user  # noqa
                    'internal_alias_prefix': 'vu',
                },
            },
        ],
    },
    'Referral_Staff_History': {
        'basetable': 'AmsReferralAllocation',
        'rename': {
            'ReferralID': 'Referral_Key',  # RCEP
            'TransferDate': 'Transfer_Date',  # RCEP
            'StartDate': 'Start_Date',  # RCEP
            'EndDate': 'End_Date',  # RCEP
            'HCPCode': None,  # RCEP was HCPCode but this is in user lookup
            # Comment: unchanged
            'CurrentAtDischarge': 'Current_At_Discharge',
        },
        'add': [
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'HCPCode',
                    'column_prefix': 'HCP_User',  # RCEP
                    'internal_alias_prefix': 'hu',
                },
            },
        ],
        'suppress_basetable': True,
        'suppress_other_tables': [],
    },
    'Referral_Team_History': {
        'basetable': 'AmsReferralTeam',
        'rename': {
            'ReferralID': 'Referral_Key',  # RCEP
            'StartDate': 'Start_Date',  # RCEP
            'EndDate': 'End_Date',  # RCEP
            'TeamCode': None,  # see lookup below, which will produce Team_Code as per RCEP  # noqa
            # Comment - unchanged
            'CurrentAtDischarge': 'Current_At_Discharge',  # RCEP
        },
        'add': [
            {
                'function': rio_add_team_lookup,
                'kwargs': {
                    'basecolumn': 'TeamCode',
                    'column_prefix': 'Team',  # RCEP
                    'internal_alias_prefix': 't',
                },
            },
        ],
    },
    'Referral_Waiting_Status_History': {
        'basetable': 'AmsReferralListWaitingStatus',
        'rename': {
            'ReferralID': 'Referral_Key',  # RCEP
            'WaitingStatus': None,  # RCEP; is a code
            'StartDate': 'Start_Date',  # RCEP
            'EndDate': 'End_Date',  # RCEP
            'ChangeDateTime': 'Change_Date_Time',  # RCEP
            'ChangeBy': None,  # RCEP; user lookup
        },
        'add': [
            {
                'function': standard_rio_code_lookup,
                'kwargs': {
                    'basecolumn': 'WaitingStatus',
                    'lookup_table': 'GenReferralWaitingStatus',
                    'result_alias': 'Waiting_Status',
                    'internal_alias_prefix': 'ws',
                },
            },
            {
                'function': rio_add_user_lookup,
                'kwargs': {
                    'basecolumn': 'ChangeBy',
                    'column_prefix': 'Changed_By',  # RCEP
                    'internal_alias_prefix': 'cb',
                },
            },
        ],
    },
    # -------------------------------------------------------------------------
    # Non-core: CPFT
    # -------------------------------------------------------------------------
    'core_assess_past_psy': {
        'basetable': 'UserAssesscoreassesspastpsy',
        'add': [
            {
                # Rockwood frailty score
                'function': simple_lookup_join,
                'kwargs': {
                    'basecolumn': 'frailty',
                    'lookup_table': 'UserMasterfrailty',
                    'lookup_pk': 'Code',
                    'lookup_fields_aliases': {
                        'CodeDescription': 'Frailty_Description',
                    },
                    'internal_alias_prefix': 'fr',
                }
            },
            {
                'function': simple_view_where,
                'kwargs': {
                    # remove deleted entries
                    'where_clause': 'type12_DeletedDate IS NULL',
                },
            },
        ],
    },
}


# =============================================================================
# Geography views
# =============================================================================

def add_postcode_geography_view(engine, progargs, ddhint):  # ddhint modified
    # Re-read column names, as we may have inserted some recently by hand that
    # may not be in the initial metadata.
    if progargs.rio:
        addresstable = RIO_TABLE_ADDRESS
        rio_postcodecol = RIO_COL_POSTCODE
    else:
        addresstable = RCEP_TABLE_ADDRESS
        rio_postcodecol = RCEP_COL_POSTCODE
    orig_column_names = get_column_names(engine, tablename=addresstable,
                                         sort=True)

    # Remove any original column names being overridden by new ones.
    # (Could also do this the other way around!)
    geogcols_lowercase = [x.lower() for x in progargs.geogcols]
    orig_column_names = [x for x in orig_column_names
                         if x.lower() not in geogcols_lowercase]

    orig_column_specs = [
        "{t}.{c}".format(t=addresstable, c=col)
        for col in orig_column_names
    ]
    geog_col_specs = [
        "{db}.{t}.{c}".format(db=progargs.postcodedb,
                              t=ONSPD_TABLE_POSTCODE,
                              c=col)
        for col in sorted(progargs.geogcols, key=lambda x: x.lower())
    ]
    overlap = set(orig_column_names) & set(progargs.geogcols)
    if overlap:
        die("Columns overlap: address table contains columns {}; "
            "geogcols = {}; overlap = {}".format(
                orig_column_names, progargs.geogcols, overlap))
    log.info("Creating view '{}'".format(VIEW_ADDRESS_WITH_GEOGRAPHY))
    ensure_columns_present(engine, tablename=addresstable, column_names=[
        rio_postcodecol])
    select_sql = """
        SELECT {origcols},
               {geogcols}
        FROM {addresstable}
        LEFT JOIN {pdb}.{pcdtab}
        ON {addresstable}.{rio_postcodecol} = {pdb}.{pcdtab}.pcds
        -- RCEP, and presumably RiO, appear to use the ONS pcds format, of
        -- 2-4 char outward code; space; 3-char inward code.
        -- If this fails, use this slower version:
        -- ON REPLACE({addresstable}.{rio_postcodecol},
        --            ' ',
        --            '') = {pdb}.{pcdtab}.pcd_nospace
    """.format(
        addresstable=addresstable,
        origcols=", ".join(orig_column_specs),
        geogcols=", ".join(geog_col_specs),
        pdb=progargs.postcodedb,
        pcdtab=ONSPD_TABLE_POSTCODE,
        rio_postcodecol=rio_postcodecol,
    )
    create_view(engine, progargs, VIEW_ADDRESS_WITH_GEOGRAPHY, select_sql)
    ddhint.suppress_table(addresstable)


# =============================================================================
# Table action selector
# =============================================================================

def process_table(table, engine, progargs):
    tablename = table.name
    column_names = table.columns.keys()
    log.debug("TABLE: '{}'; COLUMNS: {}".format(tablename, column_names))
    if progargs.rio:
        patient_table_indicator_column = get_rio_patient_id_col(table)
    else:  # RCEP:
        patient_table_indicator_column = RCEP_COL_PATIENT_ID

    is_patient_table = (patient_table_indicator_column in column_names or
                        tablename == progargs.full_prognotes_table)
    # ... special for RCEP/CPFT, where a RiO table (with different patient ID
    # column) lives within an RCEP database.
    if progargs.drop_danger_drop:
        # ---------------------------------------------------------------------
        # DROP STUFF! Opposite order to creation (below)
        # ---------------------------------------------------------------------
        # Specific
        if tablename == progargs.master_patient_table:
            drop_for_master_patient_table(table, engine, progargs)
        elif tablename == progargs.full_prognotes_table:
            drop_for_progress_notes(table, engine, progargs)
        # Generic
        if is_patient_table:
            drop_for_patient_table(table, engine, progargs)
        else:
            drop_for_nonpatient_table(table, engine, progargs)
    else:
        # ---------------------------------------------------------------------
        # CREATE STUFF!
        # ---------------------------------------------------------------------
        # Generic
        if is_patient_table:
            process_patient_table(table, engine, progargs)
        else:
            process_nonpatient_table(table, engine, progargs)
        # Specific
        if tablename == progargs.master_patient_table:
            process_master_patient_table(table, engine, progargs)
        elif tablename == progargs.full_prognotes_table:
            process_progress_notes(table, engine, progargs)


# =============================================================================
# Default settings for CRATE anonymiser "ddgen_*" fields, for RiO
# =============================================================================

class DDHint(object):
    def __init__(self):
        self._suppressed_tables = set()
        
    def suppress_table(self, table):
        self._suppressed_tables.add(table)
    
    def suppress_tables(self, tables):
        for t in tables:
            self.suppress_table(t)

    def get_suppressed_tables(self):
        return sorted(self._suppressed_tables)


def report_rio_dd_settings(progargs, ddhint):
    settings_text = """
ddgen_allow_no_patient_info = False

ddgen_per_table_pid_field = crate_rio_number

ddgen_add_per_table_pids_to_scrubber = False

ddgen_master_pid_fieldname = crate_nhs_number_int

ddgen_table_whitelist = #
    # -------------------------------------------------------------------------
    # Whitelist: Prefixes: groups of tables
    # -------------------------------------------------------------------------
    EPClientAllergy*  # Allergy details within EP module
    # -------------------------------------------------------------------------
    # Whitelist: Suffixes
    # -------------------------------------------------------------------------
    *_crate  # Views added by CRATE
    # -------------------------------------------------------------------------
    # Whitelist: Individual tables
    # -------------------------------------------------------------------------
    EPReactionType  # Allergy reaction type details within EP module

ddgen_table_blacklist = #
    # -------------------------------------------------------------------------
    # Blacklist: Prefixes: groups of tables; individual tables
    # -------------------------------------------------------------------------
    Agresso*  # Agresso [sic] module (comms to social worker systems)
    ADT*  # ?admit/discharge/transfer messages (see codes in ADTMessage)
    Ams*  # Appointment Management System (Ams) module
    Audit*  # RiO Audit Trail
    CDSContract*  # something to do with commissioner contracts
    Chd*  # Child development (interesting, but lots of tables and all empty)
    ClientAddressHistory  # defunct according to RIO 6.2 docs
    ClientAddressMerged  # defunct according to RIO 6.2 docs
    ClientChild*  # child info e.g. birth/immunisation (interesting, but several tables and all empty)
    ClientCommunityDomain # defunct according to RIO 6.2 docs
    ClientMerge*  # record of admin events (merging of client records)
    ClientPhoto*  # no use to us or identifiable!
    ClientRestrictedRecord*  # ? but admin
    Con*  # Contracts module
    DA*  # Drug Administration within EP
    DgnDiagnosis  # "Obsolete"; see DiagnosisClient
    DS*  # Drug Service within EP
    EP*  # E-Prescribing (EP) module, which we don't have
    #   ... mostly we don't have it, but we may have EPClientAllergies etc.
    #   ... so see whitelist too
    ESRImport  # user-to-?role map? Small and system.
    ExternalSystem*  # system
    GenChd*  # lookup codes for Chd*
    GenCon*  # lookup codes for Con*
    GenDiagnosis  # "Obsolete"
    GenError*  # system
    GenExtract*  # details of reporting extracts
    GenHCPTemplateDetails  # HCP diary template
    GenIDSeed  # system (counters for different ID types)
    GenLicenseKeys  # system; NB shows what components are licensed!
    GenPrinter*  # printers
    GenToDoList  # user to-do list items/notifications
    KP90ErrorLog  # error log for KP90 report; http://www.hscic.gov.uk/datacollections/kp90
    LR*  # Legitimate Relationships module
    Meeting*  # Meetings module
    Mes*  # messaging
    MonthlyPlanner*  # system
    PSS*  # Prevention, Screening & Surveillance (PSS)
    RioPerformanceTimings  # system
    RR*  # Results Reporting (e.g. laboratories, radiology)
    #   ... would be great, but we don't have it
    RTT*  # RTT* = Referral-to-Treatment (RTT) data collection (see NHS England docs)
    SAF*  # SAF* = system; looks like details of tablet devices
    Scheduler*  # Scheduler* = Scheduler module (for RiO computing)
    Sec*  # Security? Definitely RiO internal stuff.
    SPINE*  # system
    SPRExternalNotification  # system?
    tbl*  # records of changes to tables?
    TeamPlanner*  # system
    Temp*  # system
    umt*  # system
    Wfl*  # workflow
    WL*  # Waiting lists (WL) module
    # -------------------------------------------------------------------------
    # Blacklist: Middle bits, suffixes
    # -------------------------------------------------------------------------
    *Access*  # system access controls
    *Backup  # I'm guessing backups...
    *Cache*  # system
    *Lock*  # system
    *Timeout*  # system
    # -------------------------------------------------------------------------
    # Blacklist: Views supersede
    # Below here, we have other tables suppressed because CRATE's views offer
    # more comprehensive alternatives
    # -------------------------------------------------------------------------
    {suppress_tables}

# USEFUL TABLES (IN CPFT INSTANCE) INCLUDE:
# =========================================
# Assessment* = includes maps of non-core assessments (see e.g. AssessmentIndex)
# CDL_OUTDATEDPATIENTS_TWI = map from TWI (trust-wide identifier) to old CPFT M number
# UserAssess* = non-core assessments themselves
# UserMaster* = lookup tables for non-core assessments

ddgen_field_whitelist =

ddgen_field_blacklist = #
    {RIO_COL_PATIENT_ID}  # replaced by crate_rio_number
    *Soundex  # identifying 4-character code; https://msdn.microsoft.com/en-us/library/ms187384.aspx

ddgen_pk_fields = crate_pk

ddgen_constant_content = False

ddgen_constant_content_tables =

ddgen_nonconstant_content_tables =

ddgen_addition_only = False

ddgen_addition_only_tables = #
    UserMaster*  # Lookup tables for non-core - addition only?

ddgen_deletion_possible_tables =

ddgen_pid_defining_fieldnames = ClientIndex.crate_rio_number

ddgen_scrubsrc_patient_fields = # several of these:
    # ----------------------------------------------------------------------
    # Original RiO tables (some may be superseded by views; list both here)
    # ----------------------------------------------------------------------
    AmsReferral.DischargeAddressLine*
    AmsReferral.DischargePostCode
    ClientIndex.crate_pk
    ClientIndex.DateOfBirth
    ClientIndex.DaytimePhone
    ClientIndex.EMailAddress
    ClientIndex.EveningPhone
    ClientIndex.Firstname
    ClientIndex.MobilePhone
    ClientIndex.NINumber
    ClientIndex.OtherAddress
    ClientIndex.SpineID
    ClientIndex.Surname
    ClientName.GivenName1
    ClientName.GivenName2
    ClientName.GivenName3
    ClientName.GivenName4
    ClientName.GivenName5
    ClientName.SpineID
    ClientName.Surname
    # ----------------------------------------------------------------------
    # Views
    # ----------------------------------------------------------------------
    Main_Referral_Data.Discharge_Address_Line_*
    Main_Referral_Data.Discharge_Post_Code*
    {VIEW_ADDRESS_WITH_GEOGRAPHY}.AddressLine*
    {VIEW_ADDRESS_WITH_GEOGRAPHY}.PostCode

ddgen_scrubsrc_thirdparty_fields = # several:
    ClientContact.AddressLine*
    ClientContact.EmailAddress
    ClientContact.Firstname
    ClientContact.MainPhone
    ClientContact.NHSNumber
    ClientContact.SpineID
    ClientContact.Surname

ddgen_scrubmethod_code_fields = # variants:
    *PostCode*
    *Post_Code*

ddgen_scrubmethod_date_fields = *Date*

ddgen_scrubmethod_number_fields = # several:
    *DaytimePhone*
    *EveningPhone*
    *MobilePhone*
    *Daytime_Phone*
    *Evening_Phone*
    *Mobile_Phone*

ddgen_scrubmethod_phrase_fields = AddressLine*

ddgen_safe_fields_exempt_from_scrubbing =

    # RiO mostly uses string column lengths of 4, 10, 20, 40, 80, 500,
    # unlimited. So what length is the minimum for "free text"?
    # Comments are 500. Lots of 80-length fields are lookup descriptions.
    # (Note that many scrub-SOURCE fields are of length 80, e.g. address
    # fields, but they need different special handling.)
ddgen_min_length_for_scrubbing = 81

ddgen_truncate_date_fields = ClientIndex.DateOfBirth

ddgen_filename_to_text_fields =

ddgen_binary_to_text_field_pairs =

ddgen_index_fields =

ddgen_allow_fulltext_indexing = True

ddgen_force_lower_case = False

ddgen_convert_odd_chars_to_underscore = True
    """.format(  # noqa
        suppress_tables="\n    ".join(ddhint.get_suppressed_tables()),
        RIO_COL_PATIENT_ID=RIO_COL_PATIENT_ID,
        VIEW_ADDRESS_WITH_GEOGRAPHY=VIEW_ADDRESS_WITH_GEOGRAPHY,
    )
    with open(progargs.settings_filename, 'w') as f:
        print(settings_text, file=f)


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=
        r"""
*   Alters a RiO database to be suitable for CRATE.

*   By default, this treats the source database as being a copy of a RiO 6.2
    database. Use the "--rcep" (+/- "--cpft") switch(es) to treat it as a
    Servelec RiO CRIS Extract Program (RCEP) v2 output database.
    """)  # noqa
    parser.add_argument("--url", required=True, help="SQLAlchemy database URL")
    parser.add_argument(
        "--print", action="store_true",
        help="Print SQL but do not execute it. (You can redirect the printed "
             "output to create an SQL script.")
    parser.add_argument("--echo", action="store_true", help="Echo SQL")
    parser.add_argument(
        "--debug_skiptables", action="store_true",
        help="DEBUG-ONLY OPTION. Skip tables (view creation only)")
    parser.add_argument(
        "--rcep", action="store_true",
        help="Treat the source database as the product of Servelec's RiO CRIS "
             "Extract Program v2 (instead of raw RiO)")
    parser.add_argument(
        "--drop_danger_drop", action="store_true",
        help="REMOVES new columns and indexes, rather than creating them.")
    parser.add_argument(
        "--cpft", action="store_true",
        help="Apply hacks for Cambridgeshire & Peterborough NHS Foundation "
             "Trust (CPFT)")
    parser.add_argument(
        "--postcodedb",
        help="Specify database (schema) name for ONS Postcode Database (as "
             "imported by CRATE) to link to addresses as a view")
    parser.add_argument(
        "--geogcols", nargs="*", default=DEFAULT_GEOG_COLS,
        help="List of geographical information columns to link in from ONS "
             "Postcode Database. BEWARE that you do not specify anything too "
             "identifying. Default: {}".format(' '.join(DEFAULT_GEOG_COLS)))
    parser.add_argument(
        "--settings_filename",
        help="Specify filename to write draft ddgen_* settings to, for use in "
             "a CRATE anonymiser configuration file.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose")
    progargs = parser.parse_args()

    configure_logger_for_colour(
        log, level=logging.DEBUG if progargs.verbose else logging.INFO)

    progargs.rio = not progargs.rcep
    if progargs.rcep:
        # RCEP
        progargs.master_patient_table = RCEP_TABLE_MASTER_PATIENT
        if progargs.cpft:
            progargs.full_prognotes_table = CPFT_RCEP_TABLE_FULL_PROGRESS_NOTES
            # We (CPFT) may have a hacked-in copy of the RiO main progress 
            # notes table added to the RCEP output database. 
        else:
            progargs.full_prognotes_table = None
            # The RCEP does not export sufficient information to distinguish 
            # current and non-current versions of progress notes.
    else:
        # RiO
        progargs.master_patient_table = RIO_TABLE_MASTER_PATIENT
        progargs.full_prognotes_table = RIO_TABLE_PROGRESS_NOTES

    if progargs.postcodedb and not progargs.geogcols:
        die("If you specify postcodedb, you must specify some geogcols")

    log.info("CRATE in-place preprocessor for RiO or RiO CRIS Extract Program "
             "(RCEP) databases")
    safeargs = {k: v for k, v in vars(progargs).items() if k != 'url'}
    log.debug("args = {}".format(repr(safeargs)))
    log.info("RiO mode" if progargs.rio else "RCEP mode")

    engine = create_engine(progargs.url, echo=progargs.echo,
                           encoding=MYSQL_CHARSET)
    metadata = MetaData()
    metadata.bind = engine
    log.info("Database: {}".format(repr(engine.url)))  # ... repr hides p/w
    log.debug("Dialect: {}".format(engine.dialect.name))

    log.info("Reflecting (inspecting) database...")
    metadata.reflect(engine)
    log.info("... inspection complete")
    
    ddhint = DDHint()

    if not progargs.debug_skiptables:
        for table in sorted(metadata.tables.values(),
                            key=lambda t: t.name.lower()):
            process_table(table, engine, progargs)
    if progargs.rio:
        if progargs.drop_danger_drop:
            drop_rio_views(engine, metadata, progargs, ddhint)
        else:
            create_rio_views(engine, metadata, progargs, ddhint)
            
    if progargs.postcodedb:
        if progargs.drop_danger_drop:
            drop_view(engine, progargs, VIEW_ADDRESS_WITH_GEOGRAPHY)
        else:
            add_postcode_geography_view(engine, progargs, ddhint)

    if progargs.settings_filename:
        report_rio_dd_settings(progargs, ddhint)


if __name__ == '__main__':
    main()
