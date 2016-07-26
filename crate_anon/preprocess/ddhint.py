#!/usr/bin/env python
# crate_anon/preprocess/ddhint.py

import logging
from typing import Iterable, List, Tuple, Union

from sqlalchemy import MetaData
from sqlalchemy.engine import Engine

from crate_anon.common.lang import (
    get_case_insensitive_dict_key,
)
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
            table_columns_list: Iterable[Tuple[str, Iterable[str]]]) -> None:
        for table, columns in table_columns_list:
            assert table, ("Bad table; table={}, table_columns_list={}".format(
                repr(table), repr(table_columns_list)))
            assert columns, (
                "Bad table; columns={}, table_columns_list={}".format(
                    repr(columns), repr(table_columns_list)))
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
