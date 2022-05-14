#!/usr/bin/env python

r"""
crate_anon/preprocess/preprocess_systmone.py

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

**Preprocess a copy of a SystmOne database -- primarily to index it.**

"""

import argparse
import logging
from typing import List, TYPE_CHECKING

from cardinal_pythonlib.enumlike import keys_descriptions_from_enum
from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from cardinal_pythonlib.sqlalchemy.schema import (
    hack_in_mssql_xml_type,
    make_bigint_autoincrement_column,
)
from sqlalchemy import create_engine, MetaData
from sqlalchemy.engine.base import Engine

from crate_anon.anonymise.constants import CHARSET
from crate_anon.common.sql import (
    add_columns,
    add_indexes,
    create_view,
    drop_columns,
    drop_indexes,
    drop_view,
    ensure_columns_present,
    IndexCreationInfo,
    set_print_not_execute,
)
from crate_anon.preprocess.constants import (
    CRATE_COL_PK,
    CRATE_IDX_PREFIX,
    DEFAULT_GEOG_COLS,
    ONSPD_TABLE_POSTCODE,
)
from crate_anon.preprocess.postcodes import COL_POSTCODE_VARIABLE_LENGTH_SPACE
from crate_anon.preprocess.systmone_ddgen import (
    contextual_tablename,
    core_tablename,
    CrateS1ViewCol,
    CrateView,
    DEFAULT_SYSTMONE_CONTEXT,
    is_in_re,
    is_mpid,
    is_pid,
    is_pk,
    S1AddressCol,
    S1GenericCol,
    S1PatientCol,
    S1Table,
    SystmOneContext,
    TABLES_REQUIRING_CRATE_PK_REGEX,
)

if TYPE_CHECKING:
    from sqlalchemy.schema import Column, Table

log = logging.getLogger(__name__)


# =============================================================================
# Preprocessing
# =============================================================================


def add_postcode_geography_view(
    engine: Engine,
    address_table: str,
    postcode_db: str,
    geog_cols: List[str],
    view_name: str,
) -> None:
    """
    Creates a source view to add geography columns to an address table
    including postcodes, linking in e.g. LSOA/IMD information from an ONS
    postcode table (e.g. imported by CRATE; see postcodes.py).

    Args:
        engine:
            An SQLAlchemy Engine.
        address_table:
            The name of the address table in the source SystmOne database.
        postcode_db:
            The name of the database (and, for SQL Server, the schema) in which
            ONS postcode information is stored.
        geog_cols:
            Columns to merge in from the postcode database.
        view_name:
            The name of the view to create in the source SystmOne database.

    Re SystmOne postcode encoding:
    - CPFT creates PostCode_NoSpaces.
    - However

      .. code-block:: sql

        SELECT COUNT(*) FROM S1_PatientAddress
        WHERE CHARINDEX(' ', FullPostcode) > 0;
        -- ... gives lots of hits (e.g. 593k); so they mostly have spaces in.

        SELECT COUNT(*) FROM S1_PatientAddress
        WHERE CHARINDEX(' ', FullPostcode) = 0;
        -- ... a few (e.g. 20); all are just the first halves, and none are a
        -- full postcode with space missing.

        SELECT DISTINCT LEN(FullPostcode) FROM S1_PatientAddress
        ORDER BY LEN(FullPostcode);
        -- NULL, 4, 5, 6, 7, 8

      So, with a bit more testing, we conclude that SystmOne uses STANDARD
      VARIABLE-LENGTH FORMAT WITH SPACES.

    """
    a = "A"  # alias for address table
    p = "P"  # alias for postcode table
    geog_col_specs = [
        f"{p}.{col}" for col in sorted(geog_cols, key=lambda x: x.lower())
    ]
    s1_postcode_col = S1AddressCol.POSTCODE
    ons_postcode_col = COL_POSTCODE_VARIABLE_LENGTH_SPACE
    ensure_columns_present(
        engine, tablename=address_table, column_names=[s1_postcode_col]
    )
    colsep = ",\n            "
    select_sql = f"""
        SELECT
            -- Original columns that are not identifying:

            -- ... PK and patient ID:
            {a}.{S1GenericCol.PK},
            {a}.{S1GenericCol.PATIENT_ID},

            -- ... Admin fields:
            {a}.{S1GenericCol.EVENT_OCCURRED_WHEN},
            {a}.{S1GenericCol.EVENT_RECORDED_WHEN},
            -- [not in CPFT version] {a}.IDDoneBy,
            -- [not in CPFT version] {a}.IDEvent,
            -- [not in CPFT version] {a}.IDOrganisation,
            -- [not in CPFT version] {a}.IDOrganisationDoneAt,
            -- [not in CPFT version] {a}.IDOrganisationRegisteredAt,
            -- [not in CPFT version] {a}.IDOrganisationVisibleTo,
            -- [not in CPFT version] {a}.IDProfileEnteredBy,
            -- [not in CPFT version] {a}.TextualEventDoneBy,

            -- ... Non-identifying information about the address:
            {a}.{S1AddressCol.ADDRESS_TYPE},
            {a}.{S1AddressCol.CCG_OF_RESIDENCE},
            {a}.{S1AddressCol.DATE_TO},

            -- Geography columns (with nothing too specific):
            {colsep.join(geog_col_specs)}

        FROM
            {address_table} AS {a}
        INNER JOIN
            {postcode_db}.{ONSPD_TABLE_POSTCODE} AS {p}
            ON {p}.{ons_postcode_col} = {a}.{s1_postcode_col}
    """
    create_view(engine, view_name, select_sql)


def add_testpatient_view(
    engine: Engine, patient_table: str, view_name: str
) -> None:
    """
    Creates a source view to find extra test patients, where they have not been
    correctly identified by the "official" method or caught by additional local
    filters.

    Args:
        engine:
            An SQLAlchemy Engine.
        patient_table:
            The name of the patient table in the source SystmOne database.
        view_name:
            The name of the view to create in the source SystmOne database.

    Test with:

    .. code-block:: sql

        SELECT t.IDPatient, p.FirstName, p.Surname
        FROM vw_crate_FindExtraTestPatients t
        INNER JOIN S1_Patient p
            ON p.RowIdentifier = t.RowIdentifier

    """
    select_sql = f"""
        SELECT
            {S1GenericCol.PK},
            {S1GenericCol.PATIENT_ID},
            1 AS {CrateS1ViewCol.IS_TEST_PATIENT}
        FROM
            {patient_table}
        WHERE
            {S1PatientCol.FORENAME} LIKE '%test%'
            AND {S1PatientCol.SURNAME} LIKE '%test%'
    """
    create_view(engine, view_name, select_sql)


def preprocess_systmone(
    engine: Engine,
    context: SystmOneContext,
    allow_unprefixed_tables: bool = False,
    drop_danger_drop: bool = False,
    postcode_db_name: str = None,
    geog_cols: List[str] = None,
) -> None:
    """
    Add indexes to a SystmOne source database. Without this, anonymisation is
    very slow. Also adds pseudo-PK columns to selected tables.
    """
    geog_cols = geog_cols or []  # type: List[str]

    log.info("Reflecting (inspecting) database...")
    metadata = MetaData()
    metadata.bind = engine
    metadata.reflect(engine)
    log.info("... inspection complete")

    # Tables
    for table in sorted(
        metadata.tables.values(), key=lambda t: t.name.lower()
    ):  # type: Table
        ct = core_tablename(
            table.name,
            from_context=context,
            allow_unprefixed=allow_unprefixed_tables,
        )
        if not ct:
            log.debug(f"Skipping table: {table.name}")
            continue

        table_needs_pk = is_in_re(ct, TABLES_REQUIRING_CRATE_PK_REGEX)

        # If creating, (1) create pseudo-PK if necessary, (2) create indexes.
        # If dropping, (1) drop indexes, (2) drop pseudo-PK if necessary.

        # Create step #1
        if not drop_danger_drop and table_needs_pk:
            crate_pk_col = make_bigint_autoincrement_column(
                CRATE_COL_PK, engine.dialect
            )
            # SQL Server requires Table-bound columns in order to generate DDL:
            table.append_column(crate_pk_col)
            add_columns(engine, table, [crate_pk_col])

        # Create step #2 or drop step #1
        # noinspection PyTypeChecker
        for column in table.columns:  # type: Column
            colname = column.name
            idxname = f"{CRATE_IDX_PREFIX}_{colname}"
            if (
                column.primary_key
                or is_pk(ct, colname, context)
                or is_pid(colname, context)
                or is_mpid(colname, context)
            ):
                # It's too much faff to work out reliably if the source table
                # should have a UNIQUE index, particularly when local (CPFT)
                # tables use the "RowIdentifier" column name in a non-unique
                # way. It's not critical, as we're only reading, so a
                # non-unique index is fine (even if we move to a unique index
                # on the destination).
                if drop_danger_drop:
                    drop_indexes(engine, table, [idxname])
                else:
                    add_indexes(
                        engine,
                        table,
                        [
                            IndexCreationInfo(
                                index_name=idxname,
                                column=colname,
                                unique=False,
                            )
                        ],
                    )

        # Drop step #2
        if drop_danger_drop and table_needs_pk:
            drop_columns(engine, table, [CRATE_COL_PK])

    # Views
    if drop_danger_drop:
        drop_view(engine, CrateView.TESTPATIENT_VIEW)
        if postcode_db_name:
            drop_view(engine, CrateView.GEOGRAPHY_VIEW)
    else:
        add_testpatient_view(
            engine=engine,
            patient_table=contextual_tablename(S1Table.PATIENT, context),
            view_name=CrateView.TESTPATIENT_VIEW,
        )
        if postcode_db_name:
            add_postcode_geography_view(
                engine=engine,
                postcode_db=postcode_db_name,
                address_table=contextual_tablename(
                    S1Table.ADDRESS_HISTORY, context
                ),
                view_name=CrateView.GEOGRAPHY_VIEW,
                geog_cols=geog_cols,
            )


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    """
    Command-line parser. See command-line help.
    """
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=r"Indexes a SystmOne database to be suitable for CRATE.",
    )
    parser.add_argument("--url", required=True, help="SQLAlchemy database URL")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose")
    parser.add_argument(
        "--print",
        action="store_true",
        help="Print SQL but do not execute it. (You can redirect the printed "
        "output to create an SQL script.)",
    )
    parser.add_argument("--echo", action="store_true", help="Echo SQL")
    context_k, context_d = keys_descriptions_from_enum(
        SystmOneContext, keys_to_lower=True
    )
    parser.add_argument(
        "--systmone_context",
        type=str,
        choices=context_k,
        default=DEFAULT_SYSTMONE_CONTEXT.name.lower(),
        help="Context of the SystmOne database that you are reading. "
        f"[{context_d}]",
    )
    parser.add_argument(
        "--systmone_allow_unprefixed_tables",
        action="store_true",
        help="Permit tables that don't start with the expected prefix "
        "(which is e.g. 'SR' for the TPP SRE context, 'S1_' for the CPFT "
        "Data Warehouse context). May add helpful content, but you may "
        "get odd tables and views.",
    )
    parser.add_argument(
        "--postcodedb",
        help="Specify database (schema) name for ONS Postcode Database (as "
        "imported by CRATE) to link to addresses as a view. With SQL "
        "Server, you will have to specify the schema as well as the "
        'database; e.g. "--postcodedb ONS_PD.dbo"',
    )
    parser.add_argument(
        "--geogcols",
        nargs="*",
        default=DEFAULT_GEOG_COLS,
        help=f"List of geographical information columns to link in from ONS "
        f"Postcode Database. BEWARE that you do not specify anything too "
        f"identifying. Default: {' '.join(DEFAULT_GEOG_COLS)}",
    )
    parser.add_argument(
        "--drop_danger_drop",
        action="store_true",
        help="REMOVES new columns and indexes, rather than creating them. "
        "(There's not very much danger; no real information is lost, but "
        "it might take a while to recalculate it.)",
    )

    args = parser.parse_args()

    main_only_quicksetup_rootlogger(
        level=logging.DEBUG if args.verbose else logging.INFO
    )

    set_print_not_execute(args.print)

    hack_in_mssql_xml_type()

    engine = create_engine(args.url, echo=args.echo, encoding=CHARSET)
    log.info(f"Database: {repr(engine.url)}")  # ... repr hides p/w
    log.debug(f"Dialect: {engine.dialect.name}")

    preprocess_systmone(
        engine,
        context=SystmOneContext[args.systmone_context],
        allow_unprefixed_tables=args.systmone_allow_unprefixed_tables,
        drop_danger_drop=args.drop_danger_drop,
        postcode_db_name=args.postcodedb,
        geog_cols=args.geogcols,
    )


if __name__ == "__main__":
    main()
