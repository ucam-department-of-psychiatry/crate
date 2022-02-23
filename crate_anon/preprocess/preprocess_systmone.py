#!/usr/bin/env python

r"""
crate_anon/preprocess/preprocess_systmone.py

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

**Preprocess a copy of a SystmOne database -- primarily to index it.**

"""

import argparse
import logging
from typing import TYPE_CHECKING

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
    drop_columns,
    drop_indexes,
    IndexCreationInfo,
    set_print_not_execute,
)
from crate_anon.preprocess.constants import CRATE_COL_PK, CRATE_IDX_PREFIX
from crate_anon.preprocess.systmone_ddgen import (
    core_tablename,
    DEFAULT_SYSTMONE_CONTEXT,
    is_mpid,
    is_pid,
    is_pk,
    SystmOneContext,
)

if TYPE_CHECKING:
    from sqlalchemy.schema import Column, Table

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================
# Tables are referred to here by their "core" name, i.e. after removal of
# prefixes like "SR" or "S1_", if they have one.

TABLES_REQUIRING_CRATE_PK = (
    "FreeText",
)


# =============================================================================
# Preprocessing
# =============================================================================

def preprocess_systmone(engine: Engine,
                        context: SystmOneContext,
                        allow_unprefixed_tables: bool = False,
                        drop_danger_drop: bool = False) -> None:
    """
    Add indexes to a SystmOne source database. Without this, anonymisation is
    very slow. Also adds pseudo-PK columns to selected tables.
    """
    log.info("Reflecting (inspecting) database...")
    metadata = MetaData()
    metadata.bind = engine
    metadata.reflect(engine)
    log.info("... inspection complete")

    for table in sorted(metadata.tables.values(),
                        key=lambda t: t.name.lower()):  # type: Table
        ct = core_tablename(
            table.name,
            from_context=context,
            allow_unprefixed=allow_unprefixed_tables,
        )
        if not ct:
            log.debug(f"Skipping table: {table.name}")
            continue

        table_needs_pk = ct in TABLES_REQUIRING_CRATE_PK

        # If creating, (1) create pseudo-PK if necessary, (2) create indexes.
        # If dropping, (1) drop indexes, (2) drop pseudo-PK if necessary.

        # Create step #1
        if not drop_danger_drop and table_needs_pk:
            crate_pk_col = make_bigint_autoincrement_column(
                CRATE_COL_PK, engine.dialect)
            # SQL Server requires Table-bound columns in order to generate DDL:
            table.append_column(crate_pk_col)
            add_columns(engine, table, [crate_pk_col])

        # Create step #2 or drop step #1
        # noinspection PyTypeChecker
        for column in table.columns:  # type: Column
            colname = column.name
            idxname = f"{CRATE_IDX_PREFIX}_{colname}"
            if (column.primary_key
                    or is_pk(ct, colname, context)
                    or is_pid(colname, context)
                    or is_mpid(colname, context)):
                # It's too much faff to work out reliably if the source table
                # should have a UNIQUE index, particularly when local (CPFT)
                # tables use the "RowIdentifier" column name in a non-unique
                # way. It's not critical, as we're only reading, so a
                # non-unique index is fine (even if we move to a unique index
                # on the destination).
                if drop_danger_drop:
                    drop_indexes(engine, table, [idxname])
                else:
                    add_indexes(engine, table, [IndexCreationInfo(
                        index_name=idxname,
                        column=colname,
                        unique=False
                    )])

        # Drop step #2
        if drop_danger_drop and table_needs_pk:
            drop_columns(engine, table, [CRATE_COL_PK])


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    """
    Command-line parser. See command-line help.
    """
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=r"Indexes a SystmOne database to be suitable for CRATE."
    )
    parser.add_argument("--url", required=True, help="SQLAlchemy database URL")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose")
    parser.add_argument(
        "--print", action="store_true",
        help="Print SQL but do not execute it. (You can redirect the printed "
             "output to create an SQL script.)")
    parser.add_argument("--echo", action="store_true", help="Echo SQL")
    context_k, context_d = keys_descriptions_from_enum(
        SystmOneContext, keys_to_lower=True)
    parser.add_argument(
        "--systmone_context", type=str, choices=context_k,
        default=DEFAULT_SYSTMONE_CONTEXT.name.lower(),
        help="Context of the SystmOne database that you are reading. "
             f"[{context_d}]"
    )
    parser.add_argument(
        "--systmone_allow_unprefixed_tables", action="store_true",
        help="Permit tables that don't start with the expected prefix "
             "(which is e.g. 'SR' for the TPP SRE context, 'S1_' for the CPFT "
             "Data Warehouse context). May add helpful content, but you may "
             "get odd tables and views."
    )
    parser.add_argument(
        "--drop_danger_drop", action="store_true",
        help="REMOVES new columns and indexes, rather than creating them. "
             "(There's not very much danger; no real information is lost, but "
             "it might take a while to recalculate it.)")

    args = parser.parse_args()

    main_only_quicksetup_rootlogger(level=logging.DEBUG if args.verbose
                                    else logging.INFO)

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
    )


if __name__ == "__main__":
    main()
