#!/usr/bin/env python
# crate_anon/nlp_manager/base_nlp_parser.py

"""
===============================================================================
    Copyright © 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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

# Simple base class for all our NLP parsers (GATE, regex, ...)

from functools import lru_cache
import logging
import sys
from typing import Any, Dict, Iterable, Iterator, List, Optional, Tuple

from sqlalchemy.schema import Column, Index, Table
from sqlalchemy.sql import and_, exists, or_

from crate_anon.common.timing import MultiTimerContext, timer
from crate_anon.nlp_manager.constants import (
    FN_NLPDEF,
    FN_SRCPKVAL,
    FN_SRCPKSTR,
)
from crate_anon.nlp_manager.input_field_config import InputFieldConfig

# if sys.version_info.major >= 3 and sys.version_info.minor >= 5:
#     from crate_anon.nlp_manager import nlp_definition  # see PEP0484
from crate_anon.nlp_manager.nlp_definition import NlpDefinition

log = logging.getLogger(__name__)

TIMING_DELETE_DEST_RECORD = "BaseNlpParser_delete_dest_record"
TIMING_INSERT = "BaseNlpParser_sql_insert"
TIMING_PARSE = "parse"
TIMING_HANDLE_PARSED = "handled_parsed"


# =============================================================================
# Base class for all parser types
# =============================================================================

class BaseNlpParser(object):

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        self._nlpdef = nlpdef
        self._cfgsection = cfgsection
        self._commit = commit
        self._destdb_name = None
        self._destdb = None
        if nlpdef is not None:
            self._destdb_name = nlpdef.opt_str(cfgsection, 'destdb',
                                               required=True)
            self._destdb = nlpdef.get_database(self._destdb_name)

    def dest_tables_columns(self) -> Dict[str, List[Column]]:
        """
        Returns a dictionary of {tablename: destination_columns}.
        """
        raise NotImplementedError

    def dest_tables_indexes(self) -> Dict[str, List[Index]]:
        return {}

    def get_metadata(self):
        return self._destdb.metadata

    def get_session(self):
        return self._destdb.session

    def get_engine(self):
        return self._destdb.engine

    def get_nlpdef_name(self) -> Optional[str]:
        if self._nlpdef is None:
            return None
        return self._nlpdef.get_name()

    def get_parser_name(self) -> str:
        return getattr(self, 'NAME', None)

    def get_dbname(self) -> str:
        return self._destdb_name

    @staticmethod
    def _assert_no_overlap(description1: str, cols1: List[Column],
                           description2: str, cols2: List[Column]) -> None:
        """Used for ensuring non-overlapping column names."""
        set1 = set(c.name for c in cols1)
        set2 = set(c.name for c in cols2)
        assert not (set1 & set2), (
            "Overlap between {} column names ({}) and {} column names "
            "({})".format(description1, set1, description2, set2)
        )

    @staticmethod
    def _assert_column_lists_identical(
            list_of_column_lists: List[List[Any]],
            description: str) -> None:
        n = len(list_of_column_lists)
        if n <= 1:
            return
        for i in range(n - 1):
            if list_of_column_lists[i] != list_of_column_lists[i + 1]:
                msg = (
                    "Mismatch between {} lists: {}. (Are you trying to blend "
                    "source tables with different column names into a single "
                    "NLP results table?".format(
                        description, list_of_column_lists)
                )
                log.critical(msg)
                raise ValueError(msg)

    @lru_cache(maxsize=None)
    def tables(self) -> Dict[str, Table]:
        """
        Returns a dictionary of {tablename: Table}.
        """
        # Obtain a single set of copy columns
        ifconfigs = self._nlpdef.get_ifconfigs()
        assert ifconfigs, "Must specify a list of InputFieldConfigs"
        assert self._destdb, "Cannot use tables() call without a database"

        copycolumns_list = [i.get_copy_columns() for i in ifconfigs]
        self._assert_column_lists_identical(copycolumns_list, "column")
        copy_columns = copycolumns_list[0]

        core_columns = InputFieldConfig.get_core_columns_for_dest()
        self._assert_no_overlap("copy", copy_columns,
                                "source", core_columns)

        # Create one or more tables
        meta = self.get_metadata()
        tables = {}
        t_columns = self.dest_tables_columns()
        for tablename, extra_dest_cols in t_columns.items():
            self._assert_no_overlap("copy", copy_columns,
                                    "destination", extra_dest_cols)
            # And to check we haven't introduced any bugs internally:
            self._assert_no_overlap("source", core_columns,
                                    "destination", extra_dest_cols)

            columns = (core_columns +
                       extra_dest_cols +
                       copy_columns)
            copy_of_cols = [c.copy() for c in columns]

            t_indexes = self.dest_tables_indexes()
            extra_dest_indexes = []
            if tablename in t_indexes:
                extra_dest_indexes = t_indexes[tablename]
            copyindexes_list = [i.get_copy_indexes() for i in ifconfigs]
            self._assert_column_lists_identical(copyindexes_list, "index")
            copy_indexes = copyindexes_list[0]
            core_indexes = InputFieldConfig.get_core_indexes_for_dest()

            column_like_things = (
                copy_of_cols +
                core_indexes +
                extra_dest_indexes +
                copy_indexes
            )
            # log.critical(repr(column_like_things))
            tables[tablename] = Table(tablename, meta, *column_like_things)
            # You can put indexes in the column list:
            # http://docs.sqlalchemy.org/en/latest/core/constraints.html

            # NOTE that after creating the Table, all the column objects get
            # "contaminated" by the link to it, so you have to start afresh
            # with new column objects, or take a further copy, as above.

            # You can copy a Column, but not an Index.
        return tables

    def get_tablenames(self) -> Iterable[str]:
        return self.dest_tables_columns().keys()

    def get_table(self, tablename: str) -> Table:
        tables = self.tables()
        assert tablename in tables
        return tables[tablename]

    def make_tables(self, drop_first: bool = False) -> List[str]:
        assert self._destdb, "Cannot use tables() call without a database"
        engine = self.get_engine()
        tables = self.tables()
        pretty_names = []
        for t in tables.values():
            pretty_name = "{}.{}".format(self._destdb.name, t.name)
            if drop_first:
                log.info("Dropping table {}".format(pretty_name))
                t.drop(engine, checkfirst=True)
            log.info("Creating table {} (with indexes)".format(pretty_name))
            t.create(engine, checkfirst=True)
            pretty_names.append(pretty_name)
        return pretty_names

    def parse(self, text: str) -> Iterator[Tuple[str, Dict[str, Any]]]:
        """
        Takes the raw text as input.
        Yields (tablename, valuedict) tuples, where valuedict is
        a dictionary of {column: value}. The values returned are ONLY those
        generated by NLP, and do not include either (a) the source reference
        values (_srcdb, _srctable, etc.) or the "copy" fields.
        """
        raise NotImplementedError

    def process(self, text: str,
                starting_fields_values: Dict[str, Any]) -> None:
        starting_fields_values[FN_NLPDEF] = self._nlpdef.get_name()
        session = self.get_session()
        n_values = 0
        with MultiTimerContext(timer, TIMING_PARSE):
            for tablename, nlp_values in self.parse(text):
                with MultiTimerContext(timer, TIMING_HANDLE_PARSED):
                    # Merge dictionaries so EXISTING FIELDS/VALUES
                    # (starting_fields_values) HAVE PRIORITY.
                    nlp_values.update(starting_fields_values)
                    sqla_table = self.get_table(tablename)
                    # If we have superfluous keys in our dictionary, SQLAlchemy
                    # will choke ("Unconsumed column names", reporting the
                    # thing that's in our dictionary that it doesn't know
                    # about). HOWEVER, note that SQLA column names may be mixed
                    # case (e.g. 'Text') while our copy-column names are lower
                    # case (e.g. 'text'), so we must have pre-converted
                    # the SQLA column names to lower case. That happens in
                    # InputFieldConfig.get_copy_columns and
                    # InputFieldConfig.get_copy_indexes
                    column_names = [c.name for c in sqla_table.columns]
                    final_values = {k: v for k, v in nlp_values.items()
                                    if k in column_names}
                    # log.critical(repr(sqla_table))
                    insertquery = sqla_table.insert().values(final_values)
                    with MultiTimerContext(timer, TIMING_INSERT):
                        session.execute(insertquery)
                    self._nlpdef.notify_transaction(
                        session, n_rows=1, n_bytes=sys.getsizeof(final_values),
                        force_commit=self._commit)  # or we get deadlocks in multiprocess mode  # noqa
                    n_values += 1
        log.debug("NLP processor {}/{}: found {} values".format(
            self.get_nlpdef_name(), self.get_parser_name(), n_values))

    def test(self):
        pass

    def test_parser(self, test_strings: List[str]) -> None:
        print("Testing parser: {}".format(type(self).__name__))
        for text in test_strings:
            print("    {} -> {}".format(text, list(self.parse(text))))

    def delete_dest_record(self,
                           ifconfig: InputFieldConfig,
                           srcpkval: int,
                           srcpkstr: Optional[str],
                           commit: bool = False) -> None:
        """
        Used during incremental updates.
        For when a record (specified by srcpkval) has been updated in the
        source; wipe older entries for it in the destination database(s).
        """
        session = self.get_session()
        srcdb = ifconfig.get_srcdb()
        srctable = ifconfig.get_srctable()
        srcfield = ifconfig.get_srcfield()
        destdb_name = self._destdb.name
        nlpdef_name = self._nlpdef.get_name()
        for tablename, desttable in self.tables().items():
            log.debug(
                "delete_from_dest_dbs... {}.{} -> {}.{}".format(
                    srcdb, srctable, destdb_name, tablename))
            # noinspection PyProtectedMember
            delquery = (
                desttable.delete().
                where(desttable.c._srcdb == srcdb).
                where(desttable.c._srctable == srctable).
                where(desttable.c._srcfield == srcfield).
                where(desttable.c._srcpkval == srcpkval).
                where(desttable.c._nlpdef == nlpdef_name)
            )
            if srcpkstr is not None:
                # noinspection PyProtectedMember
                delquery = delquery.where(desttable.c._srcpkstr == srcpkstr)
            with MultiTimerContext(timer, TIMING_DELETE_DEST_RECORD):
                session.execute(delquery)
            if commit:
                self._nlpdef.commit(session)
                # ... or we get deadlocks in incremental updates
                # http://dev.mysql.com/doc/refman/5.5/en/innodb-deadlocks.html

    def delete_where_srcpk_not(self,
                               ifconfig: InputFieldConfig,
                               temptable: Optional[Table]) -> None:
        destsession = self.get_session()
        srcdb = ifconfig.get_srcdb()
        srctable = ifconfig.get_srctable()
        srcfield = ifconfig.get_srcfield()
        for desttable_name, desttable in self.tables().items():
            log.debug(
                "delete_where_srcpk_not... {}.{} -> {}.{}".format(
                    srcdb, srctable, self._destdb_name, desttable_name))
            # noinspection PyProtectedMember
            dest_deletion_query = (
                # see get_core_indexes_for_dest
                desttable.delete().
                where(desttable.c._srcdb == srcdb).
                where(desttable.c._srctable == srctable).
                where(desttable.c._srcfield == srcfield).
                where(desttable.c._nlpdef == self._nlpdef.get_name())
            )
            if temptable is not None:
                log.debug("... deleting selectively")
                #   DELETE FROM a WHERE NOT EXISTS (
                #       SELECT 1 FROM b
                #       WHERE a.a1 = b.b1
                #       AND (
                #           a.a2 = b.b2
                #           OR (a.a2 IS NULL AND b.b2 IS NULL)
                #       )
                #   )
                temptable_pkvalcol = temptable.columns[FN_SRCPKVAL]
                temptable_pkstrcol = temptable.columns[FN_SRCPKSTR]
                # noinspection PyProtectedMember
                dest_deletion_query = dest_deletion_query.where(
                    ~exists().where(
                        and_(
                            desttable.c._srcpkval == temptable_pkvalcol,
                            or_(
                                desttable.c._srcpkstr == temptable_pkstrcol,
                                and_(
                                    desttable.c._srcpkstr.is_(None),
                                    temptable_pkstrcol.is_(None)
                                )
                            )
                        )
                    )
                )
            else:
                log.debug("... deleting all")
            destsession.execute(dest_deletion_query)
            self._nlpdef.commit(destsession)
