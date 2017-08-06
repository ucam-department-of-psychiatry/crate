#!/usr/bin/env python
# crate_anon/preprocess/ddhint.py

"""
===============================================================================
    Copyright (C) 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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
"""

import logging
from typing import Dict, Iterable, List, Union

from cardinal_pythonlib.dicts import get_case_insensitive_dict_key
from sqlalchemy import MetaData
from sqlalchemy.engine import Engine

from crate_anon.common.sql import (
    add_indexes,
    drop_indexes,
)

log = logging.getLogger(__name__)


# =============================================================================
# DDHint class
# =============================================================================

class DDHint(object):
    def __init__(self) -> None:
        self._suppressed_tables = set()
        self._index_requests = {}  # dict of dicts

    def suppress_table(self, table: str) -> None:
        self._suppressed_tables.add(table)

    def suppress_tables(self, tables: Iterable[str]) -> None:
        for t in tables:
            self.suppress_table(t)

    def get_suppressed_tables(self) -> List[str]:
        return sorted(self._suppressed_tables)

    def add_source_index_request(self,
                                 table: str,
                                 columns: Union[str, Iterable[str]]) -> None:
        if isinstance(columns, str):
            columns = [columns]
        assert table, "Bad table: {}".format(repr(table))
        assert columns, "Bad columns: {}".format(repr(columns))
        index_name = 'crate_idx_' + '_'.join(columns)
        if table not in self._index_requests:
            self._index_requests[table] = {}
            if index_name not in self._index_requests[table]:
                self._index_requests[table][index_name] = {
                    'index_name': index_name,
                    'column': ', '.join(columns),
                    'unique': False,
                }

    def add_bulk_source_index_request(
            self,
            table_columns_dict: Dict[str, List[str]]) -> None:
        for table, columns in table_columns_dict.items():
            assert table, ("Bad table; table={}, table_columns_dict={}".format(
                repr(table), repr(table_columns_dict)))
            assert columns, (
                "Bad table; columns={}, table_columns_dict={}".format(
                    repr(columns), repr(table_columns_dict)))
            self.add_source_index_request(table, columns)

    def add_indexes(self, engine: Engine, metadata: MetaData) -> None:
        for tablename, tabledict in self._index_requests.items():
            indexdictlist = []
            for indexname, indexdict in tabledict.items():
                indexdictlist.append(indexdict)
            tablename_casematch = get_case_insensitive_dict_key(
                metadata.tables, tablename)
            if not tablename_casematch:
                log.warning("add_indexes: Skipping index as table {} "
                            "absent".format(tablename))
                continue
            table = metadata.tables[tablename_casematch]
            add_indexes(engine, table, indexdictlist)

    def drop_indexes(self, engine: Engine, metadata: MetaData) -> None:
        for tablename, tabledict in self._index_requests.items():
            index_names = list(tabledict.keys())
            tablename_casematch = get_case_insensitive_dict_key(
                metadata.tables, tablename)
            if not tablename_casematch:
                log.warning("add_indexes: Skipping index as table {} "
                            "absent".format(tablename))
                continue
            table = metadata.tables[tablename_casematch]
            drop_indexes(engine, table, index_names)
