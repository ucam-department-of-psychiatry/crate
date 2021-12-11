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
from cardinal_pythonlib.sqlalchemy.schema import hack_in_mssql_xml_type
from sqlalchemy import create_engine, MetaData
from sqlalchemy.engine.base import Engine

from crate_anon.anonymise.constants import CHARSET
from crate_anon.common.sql import (
    add_indexes,
    IndexCreationInfo,
    set_print_not_execute,
)
from crate_anon.preprocess.systmone_ddgen import (
    core_tablename,
    DEFAULT_SYSTMONE_CONTEXT,
    is_mpid,
    is_pid,
    is_pk_simple,
    SystmOneContext,
)

if TYPE_CHECKING:
    from sqlalchemy.schema import Column, Table

log = logging.getLogger(__name__)


# =============================================================================
# Preprocessing
# =============================================================================

def preprocess_systmone(engine: Engine,
                        context: SystmOneContext,
                        allow_unprefixed_tables: bool = False) -> None:
    """
    Add indexes to a SystmOne source database. Otherwise, anonymisation is very
    slow.
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
        # noinspection PyTypeChecker
        for column in table.columns:  # type: Column
            colname = column.name
            idxname = f"_idx_{colname}"
            if is_pk_simple(colname):
                add_indexes(engine, table, [IndexCreationInfo(
                    index_name=idxname,
                    column=colname,
                    unique=True
                )])
            elif is_pid(colname) or is_mpid(colname):
                add_indexes(engine, table, [IndexCreationInfo(
                    index_name=idxname,
                    column=colname,
                    unique=False
                )])


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
    )


if __name__ == '__main__':
    main()
