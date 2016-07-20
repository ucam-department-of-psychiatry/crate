#!/usr/bin/env python
# crate_anon/preprocess/preprocess_rio.py

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
                    AssessmentFormsIndex.Name(<) / .Description ('Past Psychiatric History and Physical Health')
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

===============================================================================
Scrubbing references to other patients
===============================================================================

There are two ways to do this, in principle.

The first is to reshape the data so that data from "referred-to" patients
appear in fields that can be marked as "third-party". The difficulty is that
the mapping is not 1:1 with any database row. For example, if row A has
fields "MainCarer" and "OtherCarer" that can refer to other patients, then
if the "OtherCarer" field changes, the number of rows to be examined changes.
This prohibits using a real-world PK. (A view that joined according to these
fields would not have an immutable pseudo-PK either.) And that causes
difficulties for a change-detection system. One would have to mark such a view
as something not otherwise read/copied by the anonymiser.

The other method, which is more powerful, is to do this work in the anonymiser
itself, by defining fields that are marked as "third_party_xref_pid", and
building the scrubber recursively with "depth" and "max_depth" parameters;
if depth > 0, the information is taken as third-party.

Well, that sounds achievable.

Done.

===============================================================================
RiO audit trail and change history
===============================================================================

- AuditTrail
    SequenceID -- PK for AuditTrail
    UserNumber -- FK to GenUser.UserNumber
    ActionDateTime
    AuditAction -- 2 = insert, 3 = update
    RowID -- row number -- how does that work?
        ... cheerfully, SQL Server doesn't have an automatic row ID;
        http://stackoverflow.com/questions/909155/equivalent-of-oracles-rowid-in-sql-server  # noqa
        ... so is it the PK we've already identified and called crate_pk?
    TableNumber -- FK to GenTable.Code
    ClientID -- FK to ClientIndex.ClientID
    ...

"""  # noqa

import argparse
import logging
import pdb
import sys
import traceback

from sqlalchemy import (
    create_engine,
    MetaData,
)

from crate_anon.anonymise.constants import MYSQL_CHARSET
from crate_anon.common.logsupport import configure_logger_for_colour
from crate_anon.common.sql import (
    add_columns,
    add_indexes,
    create_view,
    drop_columns,
    drop_indexes,
    drop_view,
    ensure_columns_present,
    execute,
    get_column_names,
    get_table_names,
    get_view_names,
    set_print_not_execute,
    sql_fragment_cast_to_int,
    ViewMaker,
)
from crate_anon.preprocess.rio_constants import (
    RIO_COL_PATIENT_ID,
RIO_COL_DEFAULT_PK,
RIO_COL_USER_ASSESS_DEFAULT_PK,
    VIEW_ADDRESS_WITH_GEOGRAPHY,
)
from crate_anon.preprocess.rio_pk import (
    RIO_6_2_ATYPICAL_PKS,
    RIO_6_2_ATYPICAL_PATIENT_ID_COLS,
)

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
    add_columns(engine, table, {
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
        execute(engine, """
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
        execute(engine, """
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
    add_indexes(engine, table, [
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


def drop_for_patient_table(table, engine):
    drop_indexes(engine, table, [CRATE_IDX_PK, CRATE_IDX_RIONUM])
    drop_columns(engine, table, [CRATE_COL_PK, CRATE_COL_RIO_NUMBER])


def process_nonpatient_table(table, engine, progargs):
    if progargs.rcep:
        return
    pk_col = get_rio_pk_col_nonpatient_table(table)
    if pk_col:
        add_columns(engine, table, {CRATE_COL_PK: 'INTEGER'})
    else:
        add_columns(engine, table, {CRATE_COL_PK: AUTONUMBER_COLTYPE})
    if not progargs.print:
        ensure_columns_present(engine, table=table,
                               column_names=[CRATE_COL_PK])
    if pk_col:
        execute(engine, """
            UPDATE {tablename} SET {crate_pk} = {rio_pk}
            WHERE {crate_pk} IS NULL
        """.format(tablename=table.name,
                   crate_pk=CRATE_COL_PK,
                   rio_pk=pk_col))
    add_indexes(engine, table, [{'index_name': CRATE_IDX_PK,
                                 'column': CRATE_COL_PK,
                                 'unique': True}])


def drop_for_nonpatient_table(table, engine):
    drop_indexes(engine, table, [CRATE_IDX_PK])
    drop_columns(engine, table, [CRATE_COL_PK])


# =============================================================================
# Specific table processors
# =============================================================================

def process_master_patient_table(table, engine, progargs):
    add_columns(engine, table, {CRATE_COL_NHS_NUMBER: 'BIGINT'})
    if progargs.rcep:
        nhscol = RCEP_COL_NHS_NUMBER
    else:
        nhscol = RIO_COL_NHS_NUMBER
    log.info("Table '{}': updating column '{}'".format(table.name, nhscol))
    ensure_columns_present(engine, table=table, column_names=[nhscol])
    if not progargs.print:
        ensure_columns_present(engine, table=table, column_names=[
            CRATE_COL_NHS_NUMBER])
    execute(engine, """
        UPDATE {tablename} SET
            {nhs_number_int} = CAST({nhscol} AS BIGINT)
            WHERE {nhs_number_int} IS NULL
    """.format(
        tablename=table.name,
        nhs_number_int=CRATE_COL_NHS_NUMBER,
        nhscol=nhscol,
    ))


def drop_for_master_patient_table(table, engine):
    drop_columns(engine, table, [CRATE_COL_NHS_NUMBER])


def process_progress_notes(table, engine, progargs):
    add_columns(engine, table, {
        CRATE_COL_MAX_SUBNUM: 'INTEGER',
        CRATE_COL_LAST_NOTE: 'INTEGER',
    })
    # We're always in "RiO land", not "RCEP land", for this one.
    add_indexes(engine, table, [
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
    log.info("Progress notes table '{}': updating '{}'".format(
        table.name, CRATE_COL_MAX_SUBNUM))
    execute(engine, """
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
    log.info("Progress notes table '{}': updating '{}'".format(
        table.name, CRATE_COL_LAST_NOTE))
    execute(engine, """
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

    # Create a view, if we're on an RCEP database
    if progargs.rcep and progargs.cpft:
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
        create_view(engine, VIEW_RCEP_CPFT_PROGRESS_NOTES_CURRENT, select_sql)


def drop_for_progress_notes(table, engine):
    drop_view(engine, VIEW_RCEP_CPFT_PROGRESS_NOTES_CURRENT)
    drop_indexes(engine, table, [CRATE_IDX_RIONUM_NOTENUM,
                                 CRATE_IDX_MAX_SUBNUM,
                                 CRATE_IDX_LAST_NOTE])
    drop_columns(engine, table, [CRATE_COL_MAX_SUBNUM,
                                 CRATE_COL_LAST_NOTE])


def process_clindocs_table(table, engine, progargs):
    # For RiO only, not RCEP
    add_columns(engine, table, {
        CRATE_COL_MAX_DOCVER: 'INTEGER',
        CRATE_COL_LAST_DOC: 'INTEGER',
    })
    add_indexes(engine, table, [
        {
            'index_name': CRATE_IDX_RIONUM_SERIALNUM,
            'column': '{rio_number}, SerialNumber'.format(
                rio_number=CRATE_COL_RIO_NUMBER),
        },
        {
            'index_name': CRATE_IDX_MAX_DOCVER,
            'column': CRATE_COL_MAX_DOCVER,
        },
        {
            'index_name': CRATE_IDX_LAST_DOC,
            'column': CRATE_COL_LAST_DOC,
        },
    ])

    required_cols = ["SerialNumber", "RevisionID"]
    if not progargs.print:
        required_cols.extend([CRATE_COL_MAX_DOCVER,
                              CRATE_COL_LAST_DOC,
                              CRATE_COL_RIO_NUMBER])
    ensure_columns_present(engine, table=table, column_names=required_cols)

    # Find the maximum SerialNumber for each note, and store it.
    # Slow query, even with index.
    log.info("Clinical documents table '{}': updating '{}'".format(
        table.name, CRATE_COL_MAX_DOCVER))
    execute(engine, """
        UPDATE p1
        SET p1.{max_docver_col} = subq.max_docver
        FROM {tablename} p1 JOIN (
            SELECT {rio_number}, SerialNumber, MAX(RevisionID) AS max_docver
            FROM {tablename} p2
            GROUP BY {rio_number}, SerialNumber
        ) subq
        ON subq.{rio_number} = p1.{rio_number}
        AND subq.SerialNumber = p1.SerialNumber
        WHERE p1.{max_docver_col} IS NULL
    """.format(
        max_docver_col=CRATE_COL_MAX_DOCVER,
        tablename=table.name,
        rio_number=CRATE_COL_RIO_NUMBER,
    ))

    # Set a single column accordingly
    log.info("Clinical documents table '{}': updating '{}'".format(
        table.name, CRATE_COL_LAST_DOC))
    execute(engine, """
        UPDATE {tablename} SET
            {last_doc_col} =
                CASE
                    WHEN RevisionID = {max_docver_col} THEN 1
                    ELSE 0
                END
        WHERE {last_doc_col} IS NULL
    """.format(
        tablename=table.name,
        last_doc_col=CRATE_COL_LAST_DOC,
        max_docver_col=CRATE_COL_MAX_DOCVER,
    ))


def drop_for_clindocs_table(table, engine):
    drop_indexes(engine, table, [CRATE_IDX_RIONUM_SERIALNUM,
                                 CRATE_IDX_MAX_DOCVER,
                                 CRATE_IDX_LAST_DOC])
    drop_columns(engine, table, [CRATE_COL_MAX_DOCVER,
                                 CRATE_COL_LAST_DOC])


# =============================================================================
# RiO views
# =============================================================================

def get_rio_views(engine, progargs, ddhint,
                  suppress_basetables=True, suppress_lookup=True):
    # ddhint modified
    # Returns dictionary of {viewname: select_sql} pairs.
    views = {}
    all_tables_lower = get_table_names(engine, to_lower=True)
    all_views_lower = get_view_names(engine, to_lower=True)
    all_selectables_lower = list(set(all_tables_lower + all_views_lower))
    for viewname, viewdetails in RIO_VIEWS.items():
        basetable = viewdetails['basetable']
        if basetable.lower() not in all_selectables_lower:
            log.warning("Skipping view {} as base table/view {} not "
                        "present".format(viewname, basetable))
            continue
        suppress_basetable = viewdetails.get('suppress_basetable',
                                             suppress_basetables)
        suppress_other_tables = viewdetails.get('suppress_other_tables', [])
        if suppress_basetable:
            ddhint.suppress_table(basetable)
        ddhint.suppress_tables(suppress_other_tables)
        rename = viewdetails.get('rename', None)
        # noinspection PyTypeChecker
        viewmaker = ViewMaker(engine, basetable,
                              rename=rename, progargs=progargs)
        if 'add' in viewdetails:
            for addition in viewdetails['add']:
                function = addition['function']
                kwargs = addition.get('kwargs', {})
                kwargs['viewmaker'] = viewmaker
                function(**kwargs)  # will alter viewmaker
        views[viewname] = viewmaker.get_sql()
        if suppress_lookup:
            ddhint.suppress_tables(viewmaker.get_lookup_tables())
        ddhint.add_bulk_source_index_request(
            viewmaker.get_lookup_table_keyfields())
    return views


def create_rio_views(engine, metadata, progargs, ddhint):  # ddhint modified
    rio_views = get_rio_views(engine, progargs, ddhint)
    for viewname, select_sql in rio_views.items():
        create_view(engine, viewname, select_sql)
    ddhint.add_indexes(engine, metadata)


def drop_rio_views(engine, metadata, progargs, ddhint):  # ddhint modified
    rio_views = get_rio_views(engine, progargs, ddhint)
    ddhint.drop_indexes(engine, metadata)
    for viewname, _ in rio_views.items():
        drop_view(engine, viewname)


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
        raise ValueError(
            "Columns overlap: address table contains columns {}; "
            "geogcols = {}; overlap = {}".format(
                orig_column_names, progargs.geogcols, overlap))
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
        origcols=",\n            ".join(orig_column_specs),
        geogcols=",\n            ".join(geog_col_specs),
        pdb=progargs.postcodedb,
        pcdtab=ONSPD_TABLE_POSTCODE,
        rio_postcodecol=rio_postcodecol,
    )
    create_view(engine, VIEW_ADDRESS_WITH_GEOGRAPHY, select_sql)
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
            drop_for_master_patient_table(table, engine)
        elif tablename == progargs.full_prognotes_table:
            drop_for_progress_notes(table, engine)
        elif progargs.rio and tablename == RIO_TABLE_CLINICAL_DOCUMENTS:
            drop_for_clindocs_table(table, engine)
        # Generic
        if is_patient_table:
            drop_for_patient_table(table, engine)
        else:
            drop_for_nonpatient_table(table, engine)
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
        elif progargs.rio and tablename == RIO_TABLE_CLINICAL_DOCUMENTS:
            process_clindocs_table(table, engine, progargs)
        elif tablename == progargs.full_prognotes_table:
            process_progress_notes(table, engine, progargs)


def process_all_tables(engine, metadata, progargs):
    if progargs.debug_skiptables:
        return
    for table in sorted(metadata.tables.values(),
                        key=lambda t: t.name.lower()):
        process_table(table, engine, progargs)


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=
        r"""
*   Alters a RiO database to be suitable for CRATE.

*   By default, this treats the source database as being a copy of a RiO
    database (slightly later than version 6.2; exact version unclear).
    Use the "--rcep" (+/- "--cpft") switch(es) to treat it as a
    Servelec RiO CRIS Extract Program (RCEP) v2 output database.
    """)  # noqa
    parser.add_argument("--url", required=True, help="SQLAlchemy database URL")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose")
    parser.add_argument(
        "--print", action="store_true",
        help="Print SQL but do not execute it. (You can redirect the printed "
             "output to create an SQL script.")
    parser.add_argument("--echo", action="store_true", help="Echo SQL")

    parser.add_argument(
        "--rcep", action="store_true",
        help="Treat the source database as the product of Servelec's RiO CRIS "
             "Extract Program v2 (instead of raw RiO)")
    parser.add_argument(
        "--drop_danger_drop", action="store_true",
        help="REMOVES new columns and indexes, rather than creating them. "
             "(There's not very much danger; no real information is lost, but "
             "it might take a while to recalculate it.)")
    parser.add_argument(
        "--cpft", action="store_true",
        help="Apply hacks for Cambridgeshire & Peterborough NHS Foundation "
             "Trust (CPFT) RCEP database. Only appicable with --rcep")

    parser.add_argument(
        "--debug_skiptables", action="store_true",
        help="DEBUG-ONLY OPTION. Skip tables (view creation only)")

    parser.add_argument(
        "--prognotes_current_only",
        dest="prognotes_current_only",
        action="store_true",
        help="Progress_Notes view restricted to current versions only "
             "(* default)")
    parser.add_argument(
        "--prognotes_all",
        dest="prognotes_current_only",
        action="store_false",
        help="Progress_Notes view shows old versions too")
    parser.set_defaults(prognotes_current_only=True)

    parser.add_argument(
        "--clindocs_current_only",
        dest="clindocs_current_only",
        action="store_true",
        help="Clinical_Documents view restricted to current versions only (*)")
    parser.add_argument(
        "--clindocs_all",
        dest="clindocs_current_only",
        action="store_false",
        help="Clinical_Documents view shows old versions too")
    parser.set_defaults(clindocs_current_only=True)

    parser.add_argument(
        "--allergies_current_only",
        dest="allergies_current_only",
        action="store_true",
        help="Client_Allergies view restricted to current info only")
    parser.add_argument(
        "--allergies_all",
        dest="allergies_current_only",
        action="store_false",
        help="Client_Allergies view shows deleted allergies too (*)")
    parser.set_defaults(allergies_current_only=False)

    parser.add_argument(
        "--postcodedb",
        help='Specify database (schema) name for ONS Postcode Database (as '
             'imported by CRATE) to link to addresses as a view. With SQL '
             'Server, you will have to specify the schema as well as the '
             'database; e.g. "--postcodedb ONS_PD.dbo"')
    parser.add_argument(
        "--geogcols", nargs="*", default=DEFAULT_GEOG_COLS,
        help="List of geographical information columns to link in from ONS "
             "Postcode Database. BEWARE that you do not specify anything too "
             "identifying. Default: {}".format(' '.join(DEFAULT_GEOG_COLS)))

    parser.add_argument(
        "--settings_filename",
        help="Specify filename to write draft ddgen_* settings to, for use in "
             "a CRATE anonymiser configuration file.")

    progargs = parser.parse_args()

    rootlogger = logging.getLogger()
    configure_logger_for_colour(
        rootlogger, level=logging.DEBUG if progargs.verbose else logging.INFO)

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
        raise ValueError(
            "If you specify postcodedb, you must specify some geogcols")

    log.info("CRATE in-place preprocessor for RiO or RiO CRIS Extract Program "
             "(RCEP) databases")
    safeargs = {k: v for k, v in vars(progargs).items() if k != 'url'}
    log.debug("args (except url): {}".format(repr(safeargs)))
    log.info("RiO mode" if progargs.rio else "RCEP mode")

    set_print_not_execute(progargs.print)

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

    if progargs.drop_danger_drop:
        # Drop views (and view-induced table indexes) first
        if progargs.rio:
            drop_rio_views(engine, metadata, progargs, ddhint)
        if progargs.postcodedb:
            drop_view(engine, VIEW_ADDRESS_WITH_GEOGRAPHY)
        process_all_tables(engine, metadata, progargs)
    else:
        # Tables first, then views
        process_all_tables(engine, metadata, progargs)
        if progargs.postcodedb:
            add_postcode_geography_view(engine, progargs, ddhint)
        if progargs.rio:
            create_rio_views(engine, metadata, progargs, ddhint)

    if progargs.settings_filename:
        report_rio_dd_settings(progargs, ddhint)


if __name__ == '__main__':
    # noinspection PyBroadException
    try:
        main()
    except:
        type_, value, tb = sys.exc_info()
        traceback.print_exc()
        pdb.post_mortem(tb)
