#!/usr/bin/env python

"""
crate_anon/preprocess/preprocess_rio.py

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

**Preprocess RiO tables for CRATE.**

RiO is a mental health EMR system from Servelec.


**Things to do**

TODO:
    preprocess_rio: specific supposed PK failing (non-unique) on incremental

TODO:
    preprocess_rio: Imperfectly tested: Audit_Created_Date, Audit_Updated_Date
    ... some data for Audit_Created_Date, but incomplete audit table

TODO:
    preprocess_rio: Similarly, all cross-checks to RCEP output (currently
    limited by data availability)


**Primary keys**

In RCEP, Document_ID is VARCHAR(MAX), and is often:

.. code-block:: none

    'global_table_id_9_or_10_digits' + '_' + 'pk_int_as_string'

HOWEVER, the last part is not always unique; e.g. Care_Plan_Interventions.

-   Care_Plan_Interventions has massive tranches of ENTIRELY identical rows,
    including a column called, ironically, "Unique_Key".

-   Therefore, we could either ditch the key entirely, or just use a non-UNIQUE
    index (and call it "key" not "pk").

-   AND THEN... In Client_Family, we have Document_ID values like

    .. code-block:: none

        773577794_1000000_1000001
        ^^^^^^^^^ ^^^^^^^ ^^^^^^^
        table ID  RiO#    Family member's RiO#

    ... there is no unique ID. And we don't need the middle part as we already
    have Client_ID. So this is not very useful. We could mangle out the second
    and subsequent '_' characters to give a unique number here, which would
    meaning having PK as BIGINT not INTEGER.

-   SQL Server's ``ROW_NUMBER()`` relates to result sets.

-   However, ``ADD pkname INT IDENTITY(1, 1)`` works beautifully and
    autopopulates existing tables.

-   CHUCKED this way of back-mangling DocumentID, since it doesn't work well:

    .. code-block:: none

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


**How is RiO non-core structured?**

- Index tables

  .. code-block:: none

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
        name            FormName            AddedDate               FormgroupVersion FormOrder
        CoreAssessNewV2 coreasspresprob     2013-10-30 15:46:00.000 0                0
        CoreAssessNewV2 coreassesspastpsy   2013-10-30 15:46:00.000 0                1
        CoreAssessNewV2 coreassessbackhist  2013-10-30 15:46:00.000 0                2
        CoreAssessNewV2 coreassesmentstate  2013-10-30 15:46:00.000 0                3
        CoreAssessNewV2 coreassescapsafrisk 2013-10-30 15:46:00.000 0                4
        CoreAssessNewV2 coreasssumminitplan 2013-10-30 15:46:00.000 0                5
        CoreAssessNewV2 coreasspresprob     2014-12-14 19:19:06.410 1                0
        CoreAssessNewV2 coreassesspastpsy   2014-12-14 19:19:06.410 1                1
        CoreAssessNewV2 coreassessbackhist  2014-12-14 19:19:06.413 1                2
        CoreAssessNewV2 coreassesmentstate  2014-12-14 19:19:06.413 1                3
        CoreAssessNewV2 coreassescapsafrisk 2014-12-14 19:19:06.417 1                4
        CoreAssessNewV2 coreasssumminitplan 2014-12-14 19:19:06.417 1                5
        CoreAssessNewV2 coresocial1         2014-12-14 19:19:06.420 1                6
        CoreAssessNewV2 coreasspresprob     2014-12-14 19:31:25.377 2                0 } NB
        CoreAssessNewV2 coreassesspastpsy   2014-12-14 19:31:25.377 2                1 }
        CoreAssessNewV2 coreassessbackhist  2014-12-14 19:31:25.380 2                2 }
        CoreAssessNewV2 coreassesmentstate  2014-12-14 19:31:25.380 2                3 }
        CoreAssessNewV2 coreassescapsafrisk 2014-12-14 19:31:25.380 2                4 }
        CoreAssessNewV2 coreasssumminitplan 2014-12-14 19:31:25.383 2                5 }
        CoreAssessNewV2 coresocial1         2014-12-14 19:31:25.383 2                6 }
        CoreAssessNewV2 kcsahyper           2014-12-14 19:31:25.387 2                7 }
        ^^^             ^^^
        Form groups     RiO forms; these correspond to UserAssess___ tables.

    AssessmentFormsIndex, e.g.
        Name                InUse Style Deleted    Description ...
        core_10             1     6     0          Clinical Outcomes in Routine Evaluation Screening Measure-10 (core-10)
        corealcsub          1     6     0          Alcohol and Substance Misuse
        coreassescapsafrisk 1     6     0          Capacity, Safeguarding and Risk
        coreassesmentstate  1     6     0          Mental State
        coreassessbackhist  1     6     0          Background and History
        coreassesspastpsy   1     6     0          Past Psychiatric History and Physical Health
        coreasspresprob     1     6     0          Presenting Problem
        coreasssumminitplan 1     6     0          Summary and Initial Plan
        corecarer           1     6     0          Carers and Cared For
        corediversity       1     6     0          Diversity Needs
        coremedsum          1     6     0          Medication, Allergies and Adverse Reactions
        coremenhis          1     6     0          Mental Health / Psychiatric History
        coremenstate        1     6     0          Mental State and Formulation
        coreperdev          1     6     0          Personal History and Developmental History
        ^^^                                        ^^^
        |||                                        Nice names.
        |||
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

- Main data tables

  .. code-block:: none

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

- Lookup tables

  .. code-block:: none

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

- So, overall structure, approximately:

  .. code-block:: none

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

    - PK, RiO number as integer, views

  - the ddgen_* information in the anonymiser config file.

    - tables to omit
    - fields to omit
    - default actions on fields

      - e.g. exclude if type12_DeletedDate is None
      - however, we could also do that more efficiently as a view, and that
        suits all use cases so far.


**Scrubbing references to other patients**

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

**RiO audit trail and change history**

.. code-block:: none

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


"""

import argparse
import logging
from typing import List

from cardinal_pythonlib.debugging import pdb_run
from cardinal_pythonlib.logs import configure_logger_for_colour
from cardinal_pythonlib.sqlalchemy.schema import (
    get_effective_int_pk_col,
    hack_in_mssql_xml_type,
    make_bigint_autoincrement_column,
)
from sqlalchemy import (
    create_engine,
    MetaData,
)
from sqlalchemy.engine.base import Engine
from sqlalchemy.schema import Column, Table
from sqlalchemy.sql.sqltypes import BigInteger, Integer

from crate_anon.anonymise.constants import CHARSET
from crate_anon.common.sql import (
    add_columns,
    add_indexes,
    assert_view_has_same_num_rows,
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
    CPFT_RCEP_TABLE_FULL_PROGRESS_NOTES,
    CRATE_COL_LAST_DOC,
    CRATE_COL_LAST_NOTE,
    CRATE_COL_MAX_DOCVER,
    CRATE_COL_MAX_SUBNUM,
    CRATE_COL_NHS_NUMBER,
    CRATE_COL_PK,
    CRATE_COL_RIO_NUMBER,
    CRATE_IDX_LAST_DOC,
    CRATE_IDX_LAST_NOTE,
    CRATE_IDX_MAX_DOCVER,
    CRATE_IDX_MAX_SUBNUM,
    CRATE_IDX_PK,
    CRATE_IDX_RIONUM,
    CRATE_IDX_RIONUM_NOTENUM,
    CRATE_IDX_RIONUM_SERIALNUM,
    DEFAULT_GEOG_COLS,
    ONSPD_TABLE_POSTCODE,
    RCEP_COL_NHS_NUMBER,
    RCEP_COL_PATIENT_ID,
    RCEP_COL_POSTCODE,
    RCEP_TABLE_ADDRESS,
    RCEP_TABLE_MASTER_PATIENT,
    RIO_COL_NHS_NUMBER,
    RIO_COL_PATIENT_ID,
    RIO_COL_POSTCODE,
    RIO_TABLE_ADDRESS,
    RIO_TABLE_CLINICAL_DOCUMENTS,
    RIO_TABLE_MASTER_PATIENT,
    RIO_TABLE_PROGRESS_NOTES,
    VIEW_ADDRESS_WITH_GEOGRAPHY,
    VIEW_RCEP_CPFT_PROGRESS_NOTES_CURRENT,
)
from crate_anon.preprocess.rio_ddgen import (
    DDHint,
    get_rio_dd_settings,
)
from crate_anon.preprocess.rio_pk import (
    RIO_6_2_ATYPICAL_PATIENT_ID_COLS,
)
from crate_anon.preprocess.rio_view_func import (
    rio_add_audit_info,
    RioViewConfigOptions,
)
from crate_anon.preprocess.rio_views import RIO_VIEWS

log = logging.getLogger(__name__)


# =============================================================================
# Generic table processors
# =============================================================================

def table_is_rio_type(tablename: str,
                      configoptions: RioViewConfigOptions) -> bool:
    """
    Is the named table one that uses the original RiO format?

    Args:
        tablename: name of the table
        configoptions: instance of :class:`RioViewConfigOptions`
    """
    if configoptions.rio:
        return True
    if not configoptions.cpft:
        return False
    # RCEP + CPFT modifications: there's one RiO table in the mix
    return tablename == configoptions.full_prognotes_table


def get_rio_patient_id_col(table: Table) -> str:
    """
    Returns the RiO patient ID column for a table.

    Args:
        table: SQLAlchemy Table

    Returns:
        the column name for patient ID

    """
    patient_id_col = RIO_6_2_ATYPICAL_PATIENT_ID_COLS.get(table.name,
                                                          RIO_COL_PATIENT_ID)
    # log.debug(f"get_rio_patient_id_col: {table.name} -> {patient_id_col}")
    return patient_id_col


def process_patient_table(table: Table, engine: Engine,
                          configoptions: RioViewConfigOptions) -> None:
    """
    Processes a RiO or RiO-like table:

    - Add ``pk`` and ``rio_number`` columns, if not present
    - Update ``pk`` and ``rio_number`` values, if not NULL
    - Add indexes, if absent

    Args:
        table: SQLAlchemy Table to process
        engine: an SQLAlchemy database Engine
        configoptions: instance of :class:`RioViewConfigOptions`
    """
    log.info(f"Preprocessing patient table: {repr(table.name)}")
    rio_type = table_is_rio_type(table.name, configoptions)
    if rio_type:
        pk_col = get_effective_int_pk_col(table)
        rio_pk = pk_col if pk_col != CRATE_COL_PK else None
        string_pt_id = get_rio_patient_id_col(table)
        required_cols = [string_pt_id]
    else:  # RCEP type
        rio_pk = None
        required_cols = [RCEP_COL_PATIENT_ID]
        string_pt_id = RCEP_COL_PATIENT_ID
    if not configoptions.print_sql_only:
        required_cols.extend([CRATE_COL_PK, CRATE_COL_RIO_NUMBER])

    # -------------------------------------------------------------------------
    # Add pk and rio_number columns, if not present
    # -------------------------------------------------------------------------
    if rio_type and rio_pk is not None:
        crate_pk_col = Column(CRATE_COL_PK, BigInteger, nullable=True)
        # ... can't do NOT NULL; need to populate it
        required_cols.append(rio_pk)
    else:  # RCEP type, or no PK in RiO
        crate_pk_col = make_bigint_autoincrement_column(CRATE_COL_PK,
                                                        engine.dialect)
        # ... autopopulates
    crate_rio_number_col = Column(CRATE_COL_RIO_NUMBER, BigInteger,
                                  nullable=True)
    # ... even if RiO numbers are INT, they come from VARCHAR(15) here, and
    # that can (aod does) look numeric and overflow an INT.
    # SQL Server requires Table-bound columns in order to generate DDL:
    table.append_column(crate_pk_col)
    table.append_column(crate_rio_number_col)
    add_columns(engine, table, [crate_pk_col, crate_rio_number_col])

    # -------------------------------------------------------------------------
    # Update pk and rio_number values, if not NULL
    # -------------------------------------------------------------------------
    ensure_columns_present(engine, tablename=table.name,
                           column_names=required_cols)
    cast_id_to_int = sql_fragment_cast_to_int(string_pt_id,
                                              dialect=engine.dialect)
    if rio_type and rio_pk:
        log.info(f"Table {table.name!r}: updating columns {CRATE_COL_PK!r} "
                 f"and {CRATE_COL_RIO_NUMBER!r}")
        execute(engine, f"""
            UPDATE {table.name} SET
                {CRATE_COL_PK} = {rio_pk},
                {CRATE_COL_RIO_NUMBER} = {cast_id_to_int}
            WHERE
                {CRATE_COL_PK} IS NULL
                OR {CRATE_COL_RIO_NUMBER} IS NULL
        """)
    else:
        # RCEP format, or RiO with no PK
        # crate_pk is autogenerated as an INT IDENTITY field
        log.info(f"Table {table.name!r}: "
                 f"updating column {CRATE_COL_RIO_NUMBER!r}")
        execute(engine, f"""
            UPDATE {table.name} SET
                {CRATE_COL_RIO_NUMBER} = {cast_id_to_int}
            WHERE
                {CRATE_COL_RIO_NUMBER} IS NULL
        """)
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


def drop_for_patient_table(table: Table, engine: Engine) -> None:
    """
    Drop CRATE indexes and CRATE columns for a patient table.

    Args:
        table: SQLAlchemy Table to process
        engine: an SQLAlchemy database Engine
    """
    drop_indexes(engine, table, [CRATE_IDX_PK, CRATE_IDX_RIONUM])
    drop_columns(engine, table, [CRATE_COL_PK, CRATE_COL_RIO_NUMBER])


def process_nonpatient_table(table: Table,
                             engine: Engine,
                             configoptions: RioViewConfigOptions) -> None:
    """
    Process a RiO or RiO-like non-patient table:
    - ensure it has an integer PK
    - add indexes

    Args:
        table: SQLAlchemy Table to process
        engine: an SQLAlchemy database Engine
        configoptions: instance of :class:`RioViewConfigOptions`
    """
    if configoptions.rcep:
        return
    log.info(f"Preprocessing non-patient table {table.name!r}")
    pk_col = get_effective_int_pk_col(table)
    other_pk_col = pk_col if pk_col != CRATE_COL_PK else None
    if other_pk_col:  # table has a primary key already
        crate_pk_col = Column(CRATE_COL_PK, BigInteger, nullable=True)
    else:
        crate_pk_col = make_bigint_autoincrement_column(CRATE_COL_PK,
                                                        engine.dialect)
    table.append_column(crate_pk_col)  # must be Table-bound, as above
    add_columns(engine, table, [crate_pk_col])
    if not configoptions.print_sql_only:
        ensure_columns_present(engine, tablename=table.name,
                               column_names=[CRATE_COL_PK])
    if other_pk_col:
        execute(engine, f"""
            UPDATE {table.name} SET {CRATE_COL_PK} = {other_pk_col}
            WHERE {CRATE_COL_PK} IS NULL
        """)
    add_indexes(engine, table, [{'index_name': CRATE_IDX_PK,
                                 'column': CRATE_COL_PK,
                                 'unique': True}])


def drop_for_nonpatient_table(table: Table, engine: Engine) -> None:
    """
    Drop CRATE indexes and CRATE columns for a non-patient table.

    Args:
        table: SQLAlchemy Table to process
        engine: an SQLAlchemy database Engine
    """
    drop_indexes(engine, table, [CRATE_IDX_PK])
    drop_columns(engine, table, [CRATE_COL_PK])


# =============================================================================
# Specific table processors
# =============================================================================

def process_master_patient_table(table: Table,
                                 engine: Engine,
                                 configoptions: RioViewConfigOptions) -> None:
    """
    Process a RiO master patient table:

    - Add an integer version of the NHS number.

    Args:
        table: SQLAlchemy Table to process
        engine: an SQLAlchemy database Engine
        configoptions: instance of :class:`RioViewConfigOptions`
    """
    crate_col_nhs_number = Column(CRATE_COL_NHS_NUMBER, BigInteger,
                                  nullable=True)
    table.append_column(crate_col_nhs_number)
    add_columns(engine, table, [crate_col_nhs_number])
    if configoptions.rcep:
        nhscol = RCEP_COL_NHS_NUMBER
    else:
        nhscol = RIO_COL_NHS_NUMBER
    log.info(f"Table {table.name!r}: updating column {nhscol!r}")
    ensure_columns_present(engine, tablename=table.name,
                           column_names=[nhscol])
    if not configoptions.print_sql_only:
        ensure_columns_present(engine, tablename=table.name,
                               column_names=[CRATE_COL_NHS_NUMBER])
    execute(engine, f"""
        UPDATE {table.name} SET
            {CRATE_COL_NHS_NUMBER} = CAST({nhscol} AS BIGINT)
            WHERE {CRATE_COL_NHS_NUMBER} IS NULL
    """)


def drop_for_master_patient_table(table: Table, engine: Engine) -> None:
    """
    Drop CRATE columns for the RiO master patient table.

    Args:
        table: SQLAlchemy Table to process
        engine: an SQLAlchemy database Engine
    """
    drop_columns(engine, table, [CRATE_COL_NHS_NUMBER])


def process_progress_notes(table: Table,
                           engine: Engine,
                           configoptions: RioViewConfigOptions) -> None:
    """
    Process the RiO Progress Notes table.

    - Index by patient ID/note number.
    - Add/calculate/index the ``crate_max_subnum_for_notenum`` column.
    - Add/calculate/index the ``crate_last_note_in_edit_chain`` column.
    - If on an RCEP database, create a view.

    Args:
        table: SQLAlchemy Table to process
        engine: an SQLAlchemy database Engine
        configoptions: instance of :class:`RioViewConfigOptions`
    """
    crate_col_max_subnum = Column(CRATE_COL_MAX_SUBNUM, Integer, nullable=True)
    crate_col_last_note = Column(CRATE_COL_LAST_NOTE, Integer, nullable=True)
    table.append_column(crate_col_max_subnum)
    table.append_column(crate_col_last_note)
    add_columns(engine, table, [crate_col_max_subnum, crate_col_last_note])
    # We're always in "RiO land", not "RCEP land", for this one.
    add_indexes(engine, table, [
        {  # Joint index, for JOIN in UPDATE statement below
            'index_name': CRATE_IDX_RIONUM_NOTENUM,
            'column': f'{CRATE_COL_RIO_NUMBER}, NoteNum',
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

    ensure_columns_present(engine, tablename=table.name, column_names=[
        "NoteNum", "SubNum", "EnteredInError", "EnteredInError"])
    if not configoptions.print_sql_only:
        ensure_columns_present(engine, tablename=table.name, column_names=[
            CRATE_COL_MAX_SUBNUM, CRATE_COL_LAST_NOTE, CRATE_COL_RIO_NUMBER])

    # Find the maximum SubNum for each note, and store it.
    # Slow query, even with index.
    log.info(f"Progress notes table {table.name!r}: "
             f"updating {CRATE_COL_MAX_SUBNUM!r}")
    execute(engine, f"""
        UPDATE p1
        SET p1.{CRATE_COL_MAX_SUBNUM} = subq.max_subnum
        FROM {table.name} p1 JOIN (
            SELECT {CRATE_COL_RIO_NUMBER}, NoteNum, MAX(SubNum) AS max_subnum
            FROM {table.name} p2
            GROUP BY {CRATE_COL_RIO_NUMBER}, NoteNum
        ) subq
        ON subq.{CRATE_COL_RIO_NUMBER} = p1.{CRATE_COL_RIO_NUMBER}
        AND subq.NoteNum = p1.NoteNum
        WHERE p1.{CRATE_COL_MAX_SUBNUM} IS NULL
    """)

    # Set a single column accordingly
    log.info(f"Progress notes table {table.name!r}: "
             f"updating {CRATE_COL_LAST_NOTE!r}")
    execute(engine, f"""
        UPDATE {table.name} SET
            {CRATE_COL_LAST_NOTE} =
                CASE
                    WHEN SubNum = {CRATE_COL_MAX_SUBNUM} THEN 1
                    ELSE 0
                END
        WHERE {CRATE_COL_LAST_NOTE} IS NULL
    """)

    # Create a view, if we're on an RCEP database
    if configoptions.rcep and configoptions.cpft:
        select_sql = f"""
            SELECT *
            FROM {table.name}
            WHERE
                (EnteredInError <> 1 OR EnteredInError IS NULL)
                AND {CRATE_COL_LAST_NOTE} = 1
        """
        create_view(engine, VIEW_RCEP_CPFT_PROGRESS_NOTES_CURRENT, select_sql)


def drop_for_progress_notes(table: Table, engine: Engine) -> None:
    """
    Reverses the changes made by :func:`process_progress_notes` to the RiO
    Progress Note table.

    Args:
        table: SQLAlchemy Table to process
        engine: an SQLAlchemy database Engine
    """
    drop_view(engine, VIEW_RCEP_CPFT_PROGRESS_NOTES_CURRENT)
    drop_indexes(engine, table, [CRATE_IDX_RIONUM_NOTENUM,
                                 CRATE_IDX_MAX_SUBNUM,
                                 CRATE_IDX_LAST_NOTE])
    drop_columns(engine, table, [CRATE_COL_MAX_SUBNUM,
                                 CRATE_COL_LAST_NOTE])


def process_clindocs_table(table: Table, engine: Engine,
                           configoptions: RioViewConfigOptions) -> None:
    """
    Process the RiO (not RCEP) Clinical Documents Table.

    - For RiO only, not RCEP.
    - Index on document serial number.
    - Add/calculate/index the ``crate_max_docver_for_doc`` column.
    - Add/calculate/index the ``crate_last_doc_in_chain`` column.

    Args:
        table: SQLAlchemy Table to process
        engine: an SQLAlchemy database Engine
        configoptions: instance of :class:`RioViewConfigOptions`
    """
    crate_col_max_docver = Column(CRATE_COL_MAX_DOCVER, Integer, nullable=True)
    crate_col_last_doc = Column(CRATE_COL_LAST_DOC, Integer, nullable=True)
    table.append_column(crate_col_max_docver)
    table.append_column(crate_col_last_doc)
    add_columns(engine, table, [crate_col_max_docver, crate_col_last_doc])
    add_indexes(engine, table, [
        {
            'index_name': CRATE_IDX_RIONUM_SERIALNUM,
            'column': f'{CRATE_COL_RIO_NUMBER}, SerialNumber',
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
    if not configoptions.print_sql_only:
        required_cols.extend([CRATE_COL_MAX_DOCVER,
                              CRATE_COL_LAST_DOC,
                              CRATE_COL_RIO_NUMBER])
    ensure_columns_present(engine, tablename=table.name,
                           column_names=required_cols)

    # Find the maximum SerialNumber for each note, and store it.
    # Slow query, even with index.
    log.info(f"Clinical documents table {table.name!r}: "
             f"updating {CRATE_COL_MAX_DOCVER!r}")
    execute(
        engine, f"""
        UPDATE p1
        SET p1.{CRATE_COL_MAX_DOCVER} = subq.max_docver
        FROM {table.name} p1 JOIN (
            SELECT {CRATE_COL_RIO_NUMBER}, SerialNumber, 
                   MAX(RevisionID) AS max_docver
            FROM {table.name} p2
            GROUP BY {CRATE_COL_RIO_NUMBER}, SerialNumber
        ) subq
        ON subq.{CRATE_COL_RIO_NUMBER} = p1.{CRATE_COL_RIO_NUMBER}
        AND subq.SerialNumber = p1.SerialNumber
        WHERE p1.{CRATE_COL_MAX_DOCVER} IS NULL
    """)

    # Set a single column accordingly
    log.info(f"Clinical documents table {table.name!r}: "
             f"updating {CRATE_COL_LAST_DOC!r}")
    execute(engine, f"""
        UPDATE {table.name} SET
            {CRATE_COL_LAST_DOC} =
                CASE
                    WHEN RevisionID = {CRATE_COL_MAX_DOCVER} THEN 1
                    ELSE 0
                END
        WHERE {CRATE_COL_LAST_DOC} IS NULL
    """)


def drop_for_clindocs_table(table: Table, engine: Engine) -> None:
    """
    Reverses the changes made by :func:`process_clindocs_table` to the RiO
    Clinical Documents table.

    Args:
        table: SQLAlchemy Table to process
        engine: an SQLAlchemy database Engine
    """
    drop_indexes(engine, table, [CRATE_IDX_RIONUM_SERIALNUM,
                                 CRATE_IDX_MAX_DOCVER,
                                 CRATE_IDX_LAST_DOC])
    drop_columns(engine, table, [CRATE_COL_MAX_DOCVER,
                                 CRATE_COL_LAST_DOC])


# =============================================================================
# RiO views
# =============================================================================

def get_rio_views(engine: Engine,
                  configoptions: RioViewConfigOptions,
                  ddhint: DDHint,
                  suppress_basetables: bool = True,
                  suppress_lookup: bool = True) -> List[ViewMaker]:
    """
    Gets all view definitions for RiO.

    Args:
        engine: an SQLAlchemy database Engine
        configoptions: instance of :class:`RioViewConfigOptions`
        ddhint: a :class:`crate_anon/preprocess/ddhint.DDHint`, which will be
            modified
        suppress_basetables: suppress (for data-dictionary generating hints)
            the RiO base tables for views that are made on them?
        suppress_lookup: suppress (for data-dictionary generating hints) lookup
            tables whose information has been linked into views?

    Returns:
        a list of :class:`crate_anon.common.sql.ViewMaker` objects

    """
    views = []  # type: List[ViewMaker]
    all_tables_lower = get_table_names(engine, to_lower=True)
    all_views_lower = get_view_names(engine, to_lower=True)
    all_selectables_lower = list(set(all_tables_lower + all_views_lower))
    for viewname, viewdetails in RIO_VIEWS.items():
        basetable = viewdetails['basetable']
        if basetable.lower() not in all_selectables_lower:
            log.warning(f"Skipping view {viewname} as base table/view "
                        f"{basetable} not present")
            continue
        suppress_basetable = viewdetails.get('suppress_basetable',
                                             suppress_basetables)
        suppress_other_tables = viewdetails.get('suppress_other_tables', [])
        if suppress_basetable:
            ddhint.suppress_table(basetable)
        ddhint.suppress_tables(suppress_other_tables)
        rename = viewdetails.get('rename', None)
        enforce_same_n_rows_as_base = viewdetails.get(
            'enforce_same_n_rows_as_base', True)
        # noinspection PyTypeChecker
        viewmaker = ViewMaker(
            viewname=viewname,
            engine=engine,
            basetable=basetable,
            rename=rename,
            userobj=configoptions,
            enforce_same_n_rows_as_base=enforce_same_n_rows_as_base
        )
        if 'add' in viewdetails:
            for addition in viewdetails['add']:
                func = addition['function']
                kwargs = addition.get('kwargs', {})
                kwargs['viewmaker'] = viewmaker
                func(**kwargs)  # will alter viewmaker
        if configoptions.audit_info:
            rio_add_audit_info(viewmaker)  # will alter viewmaker
        if suppress_lookup:
            ddhint.suppress_tables(viewmaker.get_lookup_tables())
        ddhint.add_bulk_source_index_request(
            viewmaker.get_index_request_dict())
        views.append(viewmaker)
    return views


def create_rio_views(engine: Engine,
                     metadata: MetaData,
                     configoptions: RioViewConfigOptions,
                     ddhint: DDHint) -> None:
    """
    Creates all views on a RiO/RCEP database.

    Args:
        engine: an SQLAlchemy Engine
        metadata: SQLAlchemy MetaData containing reflected details of database
        configoptions: an instance of :class:`RioViewConfigOptions`
        ddhint: a :class:`crate_anon/preprocess/ddhint.DDHint`, which will be
            modified
    """
    rio_views = get_rio_views(engine, configoptions, ddhint)
    for viewmaker in rio_views:
        viewmaker.create_view(engine)
    ddhint.create_indexes(engine, metadata)


def drop_rio_views(engine: Engine,
                   metadata: MetaData,
                   configoptions: RioViewConfigOptions,
                   ddhint: DDHint) -> None:  # ddhint modified
    """
    Drops all views on a RiO/RCEP database.

    Args:
        engine: an SQLAlchemy Engine
        metadata: SQLAlchemy MetaData containing reflected details of database
        configoptions: an instance of :class:`RioViewConfigOptions`
        ddhint: a :class:`crate_anon/preprocess/ddhint.DDHint`, which will be
            modified
    """
    rio_views = get_rio_views(engine, configoptions, ddhint)
    ddhint.drop_indexes(engine, metadata)
    for viewmaker in rio_views:
        viewmaker.drop_view(engine)


# =============================================================================
# Geography views
# =============================================================================

def add_postcode_geography_view(engine: Engine,
                                configoptions: RioViewConfigOptions,
                                ddhint: DDHint) -> None:
    """
    Modifies a viewmaker to add geography columns to views on RiO tables. For
    example, if you start with an address table including postcodes, and you're
    building a view involving it, then you can link in LSOA or IMD information
    with this function.

    Args:
        engine: an SQLAlchemy Engine
        configoptions: an instance of :class:`RioViewConfigOptions`
        ddhint: a :class:`crate_anon/preprocess/ddhint.DDHint`, which will be
            modified
    """
    # Re-read column names, as we may have inserted some recently by hand that
    # may not be in the initial metadata.
    if configoptions.rio:
        addresstable = RIO_TABLE_ADDRESS
        rio_postcodecol = RIO_COL_POSTCODE
    else:
        addresstable = RCEP_TABLE_ADDRESS
        rio_postcodecol = RCEP_COL_POSTCODE
    orig_column_names = get_column_names(engine, tablename=addresstable,
                                         sort=True)

    # Remove any original column names being overridden by new ones.
    # (Could also do this the other way around!)
    geogcols_lowercase = [x.lower() for x in configoptions.geogcols]
    orig_column_names = [x for x in orig_column_names
                         if x.lower() not in geogcols_lowercase]

    orig_column_specs = [
        f"{addresstable}.{col}"
        for col in orig_column_names
    ]
    geog_col_specs = [
        f"{configoptions.postcodedb}.{ONSPD_TABLE_POSTCODE}.{col}"
        for col in sorted(configoptions.geogcols, key=lambda x: x.lower())
    ]
    overlap = set(orig_column_names) & set(configoptions.geogcols)
    if overlap:
        raise ValueError(
            f"Columns overlap: address table contains columns "
            f"{orig_column_names}; geogcols = {configoptions.geogcols}; "
            f"overlap = {overlap}")
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
        pdb=configoptions.postcodedb,
        pcdtab=ONSPD_TABLE_POSTCODE,
        rio_postcodecol=rio_postcodecol,
    )
    create_view(engine, VIEW_ADDRESS_WITH_GEOGRAPHY, select_sql)
    assert_view_has_same_num_rows(engine, addresstable,
                                  VIEW_ADDRESS_WITH_GEOGRAPHY)
    ddhint.suppress_table(addresstable)


# =============================================================================
# Table action selector
# =============================================================================

def process_table(table: Table, engine: Engine,
                  configoptions: RioViewConfigOptions) -> None:
    """
    Process a RiO-like table; the specific action is selected by the database
    type and there are custom processors for some tables (e.g. master patient
    table, progress notes, clinical documents).

    Args:
        table: SQLAlchemy Table to process
        engine: an SQLAlchemy database Engine
        configoptions: instance of :class:`RioViewConfigOptions`
    """
    tablename = table.name
    column_names = table.columns.keys()
    log.debug(f"TABLE: {tablename}; COLUMNS: {column_names}")
    if configoptions.rio:
        patient_table_indicator_column = get_rio_patient_id_col(table)
    else:  # RCEP:
        patient_table_indicator_column = RCEP_COL_PATIENT_ID

    is_patient_table = (patient_table_indicator_column in column_names or
                        tablename == configoptions.full_prognotes_table)
    # ... special for RCEP/CPFT, where a RiO table (with different patient ID
    # column) lives within an RCEP database.
    if configoptions.drop_not_create:
        # ---------------------------------------------------------------------
        # DROP STUFF! Opposite order to creation (below)
        # ---------------------------------------------------------------------
        # Specific
        if tablename == configoptions.master_patient_table:
            drop_for_master_patient_table(table, engine)
        elif tablename == configoptions.full_prognotes_table:
            drop_for_progress_notes(table, engine)
        elif configoptions.rio and tablename == RIO_TABLE_CLINICAL_DOCUMENTS:
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
            process_patient_table(table, engine, configoptions)
        else:
            process_nonpatient_table(table, engine, configoptions)
        # Specific
        if tablename == configoptions.master_patient_table:
            process_master_patient_table(table, engine, configoptions)
        elif configoptions.rio and tablename == RIO_TABLE_CLINICAL_DOCUMENTS:
            process_clindocs_table(table, engine, configoptions)
        elif tablename == configoptions.full_prognotes_table:
            process_progress_notes(table, engine, configoptions)


def process_all_tables(engine: Engine,
                       metadata: MetaData,
                       configoptions: RioViewConfigOptions) -> None:
    """
    Process all RiO-like tables via :func:`process_table`.

    Args:
        metadata: SQLAlchemy MetaData containing reflected details of database
        engine: an SQLAlchemy database Engine
        configoptions: instance of :class:`RioViewConfigOptions`
    """
    for table in sorted(metadata.tables.values(),
                        key=lambda t: t.name.lower()):
        process_table(table, engine, configoptions)


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    """
    Command-line parser. See command-line help.
    """
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        # formatter_class=argparse.ArgumentDefaultsHelpFormatter,
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
        "--drop-danger-drop", action="store_true",
        help="REMOVES new columns and indexes, rather than creating them. "
             "(There's not very much danger; no real information is lost, but "
             "it might take a while to recalculate it.)")
    parser.add_argument(
        "--cpft", action="store_true",
        help="Apply hacks for Cambridgeshire & Peterborough NHS Foundation "
             "Trust (CPFT) RCEP database. Only applicable with --rcep")

    parser.add_argument(
        "--debug-skiptables", action="store_true",
        help="DEBUG-ONLY OPTION. Skip tables (view creation only)")

    prog_curr_group = parser.add_mutually_exclusive_group()
    prog_curr_group.add_argument(
        "--prognotes-current-only",
        dest="prognotes_current_only",
        action="store_true",
        help="Progress_Notes view restricted to current versions only "
             "(* default)")
    prog_curr_group.add_argument(
        "--prognotes-all",
        dest="prognotes_current_only",
        action="store_false",
        help="Progress_Notes view shows old versions too")
    parser.set_defaults(prognotes_current_only=True)

    clindocs_curr_group = parser.add_mutually_exclusive_group()
    clindocs_curr_group.add_argument(
        "--clindocs-current-only",
        dest="clindocs_current_only",
        action="store_true",
        help="Clinical_Documents view restricted to current versions only (*)")
    clindocs_curr_group.add_argument(
        "--clindocs-all",
        dest="clindocs_current_only",
        action="store_false",
        help="Clinical_Documents view shows old versions too")
    parser.set_defaults(clindocs_current_only=True)

    allerg_curr_group = parser.add_mutually_exclusive_group()
    allerg_curr_group.add_argument(
        "--allergies-current-only",
        dest="allergies_current_only",
        action="store_true",
        help="Client_Allergies view restricted to current info only")
    allerg_curr_group.add_argument(
        "--allergies-all",
        dest="allergies_current_only",
        action="store_false",
        help="Client_Allergies view shows deleted allergies too (*)")
    parser.set_defaults(allergies_current_only=False)

    audit_group = parser.add_mutually_exclusive_group()
    audit_group.add_argument(
        "--audit-info",
        dest="audit_info",
        action="store_true",
        help="Audit information (creation/update times) added to views")
    audit_group.add_argument(
        "--no-audit-info",
        dest="audit_info",
        action="store_false",
        help="No audit information added (*)")
    parser.set_defaults(audit_info=False)

    parser.add_argument(
        "--postcodedb",
        help='Specify database (schema) name for ONS Postcode Database (as '
             'imported by CRATE) to link to addresses as a view. With SQL '
             'Server, you will have to specify the schema as well as the '
             'database; e.g. "--postcodedb ONS_PD.dbo"')
    parser.add_argument(
        "--geogcols", nargs="*", default=DEFAULT_GEOG_COLS,
        help=f"List of geographical information columns to link in from ONS "
             f"Postcode Database. BEWARE that you do not specify anything too "
             f"identifying. Default: {' '.join(DEFAULT_GEOG_COLS)}")

    parser.add_argument(
        "--settings-filename",
        help="Specify filename to write draft ddgen_* settings to, for use in "
             "a CRATE anonymiser configuration file.")

    progargs = parser.parse_args()

    rootlogger = logging.getLogger()
    configure_logger_for_colour(
        rootlogger, level=logging.DEBUG if progargs.verbose else logging.INFO)

    rio = not progargs.rcep
    if progargs.rcep:
        # RCEP
        master_patient_table = RCEP_TABLE_MASTER_PATIENT
        if progargs.cpft:
            full_prognotes_table = CPFT_RCEP_TABLE_FULL_PROGRESS_NOTES
            # We (CPFT) may have a hacked-in copy of the RiO main progress
            # notes table added to the RCEP output database.
        else:
            full_prognotes_table = None
            # The RCEP does not export sufficient information to distinguish
            # current and non-current versions of progress notes.
    else:
        # RiO
        master_patient_table = RIO_TABLE_MASTER_PATIENT
        full_prognotes_table = RIO_TABLE_PROGRESS_NOTES

    log.info("CRATE in-place preprocessor for RiO or RiO CRIS Extract Program "
             "(RCEP) databases")
    safeargs = {k: v for k, v in vars(progargs).items() if k != 'url'}
    log.debug(f"args (except url): {repr(safeargs)}")
    log.info("RiO mode" if rio else "RCEP mode")

    if progargs.postcodedb and not progargs.geogcols:
        raise ValueError(
            "If you specify postcodedb, you must specify some geogcols")

    set_print_not_execute(progargs.print)

    hack_in_mssql_xml_type()

    engine = create_engine(progargs.url, echo=progargs.echo,
                           encoding=CHARSET)
    metadata = MetaData()
    metadata.bind = engine
    log.info(f"Database: {repr(engine.url)}")  # ... repr hides p/w
    log.debug(f"Dialect: {engine.dialect.name}")

    log.info("Reflecting (inspecting) database...")
    metadata.reflect(engine)
    log.info("... inspection complete")

    configoptions = RioViewConfigOptions(
        rio=rio,
        rcep=progargs.rcep,
        cpft=progargs.cpft,
        print_sql_only=progargs.print,
        drop_not_create=progargs.drop_danger_drop,
        master_patient_table=master_patient_table,
        full_prognotes_table=full_prognotes_table,
        prognotes_current_only=progargs.prognotes_current_only,
        clindocs_current_only=progargs.clindocs_current_only,
        allergies_current_only=progargs.allergies_current_only,
        audit_info=progargs.audit_info,
        postcodedb=progargs.postcodedb,
        geogcols=progargs.geogcols,
    )
    ddhint = DDHint()

    if progargs.drop_danger_drop:
        # Drop views (and view-induced table indexes) first
        if rio:
            drop_rio_views(engine, metadata, configoptions, ddhint)
        drop_view(engine, VIEW_ADDRESS_WITH_GEOGRAPHY)
        if not progargs.debug_skiptables:
            process_all_tables(engine, metadata, configoptions)
    else:
        # Tables first, then views
        if not progargs.debug_skiptables:
            process_all_tables(engine, metadata, configoptions)
        if progargs.postcodedb:
            add_postcode_geography_view(engine, configoptions, ddhint)
        if rio:
            create_rio_views(engine, metadata, configoptions, ddhint)

    if progargs.settings_filename:
        with open(progargs.settings_filename, 'w') as f:
            print(get_rio_dd_settings(ddhint), file=f)


if __name__ == '__main__':
    pdb_run(main)
