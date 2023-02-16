#!/usr/bin/env python

"""
crate_anon/preprocess/ddhint.py

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

**Hint class for data dictionary generation.**

"""

import logging
from typing import Dict, Iterable, List, Set, Union

from cardinal_pythonlib.dicts import get_case_insensitive_dict_key
from sqlalchemy import MetaData
from sqlalchemy.engine.base import Engine

from crate_anon.common.sql import (
    add_indexes,
    drop_indexes,
    IndexCreationInfo,
)

log = logging.getLogger(__name__)


# =============================================================================
# DDHint class
# =============================================================================


class DDHint:
    """
    Represents a hint for creating data dictionaries.
    """

    def __init__(self) -> None:
        self._suppressed_tables = set()  # type: Set[str]
        self._index_requests = {}  # type: Dict[str, List[IndexCreationInfo]]
        # ... key = table name
        # ... value = list of IndexCreationInfo objects for that table

    def suppress_table(self, table: str) -> None:
        """
        Adds a table to the "suppress table" list. This is intended to
        represent source tables that you don't want to appear in the
        destination database (usually because you have made a copy in a nicer
        format).

        Args:
            table: name of the table
        """
        self._suppressed_tables.add(table)

    def suppress_tables(self, tables: Iterable[str]) -> None:
        """
        Adds multiple tables to the "suppress table" list. See
        :func:`suppress_table`.

        Args:
            tables: iterable of table names
        """
        for t in tables:
            self.suppress_table(t)

    def get_suppressed_tables(self) -> List[str]:
        """
        Returns the names of all tables to be suppressed.
        """
        return sorted(self._suppressed_tables)

    def add_source_index_request(
        self, table: str, columns: Union[str, Iterable[str]]
    ) -> None:
        """
        Adds a request to index tables on the **source** database.

        Args:
            table: table name
            columns: single column name (string) or iterable of multiple
                column names
        """
        if isinstance(columns, str):
            columns = [columns]
        assert table, f"Bad table: {table!r}"
        assert columns, f"Bad columns: {columns!r}"
        assert len(columns) == len(
            set(columns)
        ), f"Duplicate columns in: {columns!r}"
        index_name = "crate_idx_" + "_".join(columns)
        index_requests_for_table = self._index_requests.setdefault(table, [])
        if index_name not in index_requests_for_table:
            index_requests_for_table.append(
                IndexCreationInfo(
                    index_name=index_name,
                    column=columns,
                    unique=False,
                )
            )

    def add_bulk_source_index_request(
        self, table_columns_dict: Dict[str, List[str]]
    ) -> None:
        """
        Adds multiple index requests for the **source** database. (See
        :func:`add_source_index_request`.)

        Args:
            table_columns_dict:
                dictionary mapping ``tablename: columns``, where ``tablename``
                is a string table name, and ``columns`` is a single column name
                as a string or an iterable of multiple column names
        """
        for table, columns in table_columns_dict.items():
            assert table, (
                f"Bad table; table={table!r}, "
                f"table_columns_dict={table_columns_dict!r}"
            )
            assert columns, (
                f"Bad table; columns={columns!r}, "
                f"table_columns_dict={table_columns_dict!r}"
            )
            self.add_source_index_request(table, columns)

    def create_indexes(self, engine: Engine, metadata: MetaData) -> None:
        """
        Creates indexes in the **source** database according to instructions we
        have previously received via :func:`add_source_index_request` and/or
        :func:`add_bulk_source_index_request`.

        Args:
            engine: SQLAlchemy database Engine
            metadata: SQLAlchemy ORM Metadata
        """
        for tablename, index_info_list in self._index_requests.items():
            tablename_casematch = get_case_insensitive_dict_key(
                metadata.tables, tablename
            )
            if not tablename_casematch:
                log.warning(
                    f"add_indexes: Skipping index as table {tablename} absent"
                )
                continue
            table = metadata.tables[tablename_casematch]
            add_indexes(engine, table, index_info_list)

    def drop_indexes(self, engine: Engine, metadata: MetaData) -> None:
        """
        Drop indexes from the source database. Reverses the effects of
        :func:`create_indexes`.

        Args:
            engine: SQLAlchemy database Engine
            metadata: SQLAlchemy ORM Metadata
        """
        for tablename, index_info_list in self._index_requests.items():
            index_names = [i.index_name for i in index_info_list]
            tablename_casematch = get_case_insensitive_dict_key(
                metadata.tables, tablename
            )
            if not tablename_casematch:
                log.warning(
                    f"add_indexes: Skipping index as table {tablename} absent"
                )
                continue
            table = metadata.tables[tablename_casematch]
            drop_indexes(engine, table, index_names)
