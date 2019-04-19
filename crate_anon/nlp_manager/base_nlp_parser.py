#!/usr/bin/env python

"""
crate_anon/nlp_manager/base_nlp_parser.py

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

**Simple base class for all our NLP parsers (GATE, regex, ...)**

"""

from functools import lru_cache
import logging
import sys
from typing import (
    Any, Dict, Generator, Iterable, List, Optional, TextIO, Tuple
)

from cardinal_pythonlib.timing import MultiTimerContext, timer
from cardinal_pythonlib.sqlalchemy.schema import (
    column_lists_equal,
    index_lists_equal
)
from sqlalchemy.engine.base import Engine
from sqlalchemy.orm.session import Session
from sqlalchemy.schema import Column, Index, Table
from sqlalchemy.sql import and_, exists, or_
from sqlalchemy.sql.schema import MetaData

from crate_anon.nlp_manager.constants import (
    FN_NLPDEF,
    FN_SRCPKVAL,
    FN_SRCPKSTR,
)
from crate_anon.nlp_manager.input_field_config import InputFieldConfig
from crate_anon.anonymise.dbholder import DatabaseHolder

# if sys.version_info.major >= 3 and sys.version_info.minor >= 5:
#     from crate_anon.nlp_manager import nlp_definition  # see PEP0484
from crate_anon.nlp_manager.nlp_definition import (
    full_sectionname,
    NlpConfigPrefixes,
    NlpDefinition,
)

log = logging.getLogger(__name__)

TIMING_DELETE_DEST_RECORD = "BaseNlpParser_delete_dest_record"
TIMING_INSERT = "BaseNlpParser_sql_insert"
TIMING_PARSE = "parse"
TIMING_HANDLE_PARSED = "handled_parsed"


# =============================================================================
# Base class for all parser types
# =============================================================================

class BaseNlpParser(object):
    """
    Base class for all CRATE NLP processors, including those that talk to
    third-party software. Manages the interface to databases for results
    storage, etc.
    """

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        """
        Args:
            nlpdef:
                a :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
            cfgsection:
                the name of a CRATE NLP config file section (from which we may
                choose to get extra config information)
            commit:
                force a COMMIT whenever we insert data? You should specify this
                in multiprocess mode, or you may get database deadlocks.
        """
        self._nlpdef = nlpdef
        self._cfgsection = cfgsection
        self._commit = commit
        self._destdb_name = None
        self._destdb = None
        if nlpdef is not None:
            self._sectionname = full_sectionname(
                NlpConfigPrefixes.PROCESSOR, cfgsection)
            self._destdb_name = nlpdef.opt_str(self._sectionname, 'destdb',
                                               required=True)
            self._destdb = nlpdef.get_database(self._destdb_name)

    @classmethod
    def print_info(cls, file: TextIO = sys.stdout) -> None:
        """
        Print general information about this NLP processor.

        Args:
            file: file to print to (default: stdout)
        """
        print("Base class for all CRATE NLP parsers", file=file)

    def dest_tables_columns(self) -> Dict[str, List[Column]]:
        """
        Describes the destination table(s) that this NLP processor wants to
        write to.

        Returns:
             dict: a dictionary of ``{tablename: destination_columns}``, where
             ``destination_columns`` is a list of SQLAlchemy :class:`Column`
             objects.
        """
        raise NotImplementedError

    def dest_tables_indexes(self) -> Dict[str, List[Index]]:
        """
        Describes indexes that this NLP processor suggests for its destination
        table(s).

        Returns:
             dict: a dictionary of ``{tablename: indexes}``, where ``indexes``
             is a list of SQLAlchemy :class:`Index` objects.
        """
        return {}

    def get_metadata(self) -> MetaData:
        """
        Returns the SQLAlchemy metadata for the destination database (which this
        NLP processor was told about at construction).
        """
        return self._destdb.metadata

    def get_session(self) -> Session:
        """
        Returns the SQLAlchemy ORM Session for the destination database (which
        this NLP processor was told about at construction).
        """
        return self._destdb.session

    def get_engine(self) -> Engine:
        """
        Returns the SQLAlchemy database Engine for the destination database
        (which this NLP processor was told about at construction).
        """
        return self._destdb.engine

    def get_nlpdef_name(self) -> Optional[str]:
        """
        Returns the name of our
        :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`, if we
        have one, or ``None``.
        """
        if self._nlpdef is None:
            return None
        return self._nlpdef.get_name()

    def get_parser_name(self) -> str:
        """
        Returns the NLP parser's name, from our :attr:`NAME` attribute.
        """
        return getattr(self, 'NAME', None)

    def get_dbname(self) -> str:
        """
        Returns the friendly name for the destination database (which this NLP
        processor was told about at construction).
        """
        return self._destdb_name

    def get_cfgsection(self) -> str:
        """
        Returns the cfgsection the class was created with.
        """
        return self._cfgsection

    @staticmethod
    def _assert_no_overlap(description1: str, cols1: List[Column],
                           description2: str, cols2: List[Column]) -> None:
        """
        Asserts that the two column lists do not include overlapping column
        names.

        Used for ensuring non-overlapping column names when we add NLP-specific
        columns to generic columns (e.g. about the source data).

        Args:
            description1: description of group 1, used for error messages
            cols1: list 1 of SQLAlchemy :class:`Column` objects
            description2: description of group 2, used for error messages
            cols2: list 2 of SQLAlchemy :class:`Column` objects
        """
        set1 = set(c.name for c in cols1)
        set2 = set(c.name for c in cols2)
        assert not (set1 & set2), (
            f"Overlap between {description1} column names ({set1}) and "
            f"{description2} column names ({set2})"
        )

    @staticmethod
    def _assert_column_lists_identical(
            list_of_column_lists: List[List[Column]]) -> None:
        """
        Ensure that every column list (in a list of column lists) is identical.
        """
        n = len(list_of_column_lists)
        if n <= 1:
            return
        for i in range(n - 1):
            a_list = list_of_column_lists[i]
            b_list = list_of_column_lists[i + 1]
            if not column_lists_equal(a_list, b_list):
                msg = (
                    "Mismatch between column lists. (Are you trying to"
                    " blend source tables with different column names into a "
                    "single NLP results table?) Mismatch is between list {a} "
                    "and list {b}.\n"
                    "-- LIST A: {a_list}.\n"
                    "-- LIST B: {b_list}.\n"
                    "-- ALL LISTS: {all_lists}.\n"
                    "-- ALL COLUMN NAMES: {all_colnames}.".format(
                        a=i,
                        b=i + 1,
                        a_list=a_list,
                        b_list=b_list,
                        all_lists=list_of_column_lists,
                        all_colnames=[[c.name for c in columns]
                                      for columns in list_of_column_lists],
                    )
                )
                log.critical(msg)
                raise ValueError(msg)

    @staticmethod
    def _assert_index_lists_identical(
            list_of_index_lists: List[List[Index]]) -> None:
        """
        Ensure that every index list (in a list of index lists) is identical.
        """
        n = len(list_of_index_lists)
        if n <= 1:
            return
        for i in range(n - 1):
            a_list = list_of_index_lists[i]
            b_list = list_of_index_lists[i + 1]
            if not index_lists_equal(a_list, b_list):
                msg = (
                    "Mismatch between index lists. (Are you trying to"
                    " blend source tables with different column names into a "
                    "single NLP results table?) Mismatch is between list {a} "
                    "and list {b}.\n"
                    "-- LIST A: {a_list}.\n"
                    "-- LIST B: {b_list}.\n"
                    "-- ALL LISTS: {all_lists}.\n"
                    "-- ALL COLUMN NAMES: {all_colnames}.".format(
                        a=i,
                        b=i + 1,
                        a_list=a_list,
                        b_list=b_list,
                        all_lists=list_of_index_lists,
                        all_colnames=[[c.name for c in columns]
                                      for columns in list_of_index_lists],
                    )
                )
                log.critical(msg)
                raise ValueError(msg)

    @lru_cache(maxsize=None)
    def tables(self) -> Dict[str, Table]:
        """
        Returns a dictionary of ``{tablename: Table}``, mapping table names
        to SQLAlchemy Table objects, for all destination tables of this NLP
        processor.
        """
        # Obtain a single set of copy columns
        ifconfigs = self._nlpdef.get_ifconfigs()
        assert ifconfigs, "Must specify a list of InputFieldConfigs"
        assert self._destdb, "Cannot use tables() call without a database"

        copycolumns_list = [i.get_copy_columns() for i in ifconfigs]
        self._assert_column_lists_identical(copycolumns_list)
        copy_columns = copycolumns_list[0]

        core_columns = InputFieldConfig.get_core_columns_for_dest()
        self._assert_no_overlap("copy", copy_columns,
                                "source", core_columns)

        # Create one or more tables
        meta = self.get_metadata()
        tables = {}  # Dict[str, Table]
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
            extra_dest_indexes = []  # type: List[Index]
            if tablename in t_indexes:
                extra_dest_indexes = t_indexes[tablename]
            copyindexes_list = [i.get_copy_indexes() for i in ifconfigs]
            self._assert_index_lists_identical(copyindexes_list)
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
        """
        Returns all destination table names for this NLP processor.
        """
        return self.dest_tables_columns().keys()

    def get_table(self, tablename: str) -> Table:
        """
        Returns an SQLAlchemy :class:`Table` for a given destination table of
        this NLP processor whose name is ``tablename``.
        """
        tables = self.tables()
        return tables[tablename]

    def make_tables(self, drop_first: bool = False) -> List[str]:
        """
        Creates all destination tables for this NLP processor in the
        destination database.

        Args:
            drop_first: drop the tables first?
        """
        assert self._destdb, "No database specified!"
        engine = self.get_engine()
        tables = self.tables()
        pretty_names = []  # type: List[str]
        for t in tables.values():
            pretty_name = f"{self._destdb.name}.{t.name}"
            if drop_first:
                log.info(f"Dropping table {pretty_name}")
                t.drop(engine, checkfirst=True)
            log.info(f"Creating table {pretty_name} (with indexes)")
            t.create(engine, checkfirst=True)
            pretty_names.append(pretty_name)
        return pretty_names

    def parse(self, text: str) -> Generator[Tuple[str, Dict[str, Any]],
                                            None, None]:
        """
        Main parsing function.

        Args:
            text: the raw text to parse

        Yields:
            tuple: ``tablename, valuedict``, where ``valuedict`` is
            a dictionary of ``{columnname: value}``. The values returned are
            ONLY those generated by NLP, and do not include either (a) the
            source reference values (``_srcdb``, ``_srctable``, etc.) or the
            "copy" fields.
        """
        raise NotImplementedError

    def process(self, text: str,
                starting_fields_values: Dict[str, Any]) -> None:
        """
        The core function that takes a single piece of text and feeds it
        through a single NLP processor. This may produce zero, one, or many
        output records. Those records are then merged with information about
        their source (etc)., and inserted into the destination database.

        Args:
            text:
                the raw text to parse
            starting_fields_values:
                a dictionary of the format ``{columnname: value}`` that should
                be added to whatever the NLP processor comes up with. This
                will, in practice, include source metadata (which table,
                row [PK], and column did the text come from), processing
                metadata (when did the NLP processing take place?), and other
                values that the user has told us to copy across from the source
                database.
        """
        if not text:
            return
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
                        session,
                        n_rows=1,
                        n_bytes=sys.getsizeof(final_values),
                        force_commit=self._commit
                    )
                    n_values += 1
        log.debug(
            f"NLP processor {self.get_nlpdef_name()}/{self.get_parser_name()}:"
            f" found {n_values} values")

    def test(self, verbose: bool = False) -> None:
        """
        Performs a self-test on the NLP processor.

        Args:
            verbose: be verbose?
        """
        pass

    def test_parser(self, test_strings: List[str]) -> None:
        """
        Tests the NLP processor's parser with a set of test strings.
        """
        print(f"Testing parser: {type(self).__name__}")
        for text in test_strings:
            print(f"    {text} -> {list(self.parse(text))}")

    def delete_dest_record(self,
                           ifconfig: InputFieldConfig,
                           srcpkval: int,
                           srcpkstr: Optional[str],
                           commit: bool = False) -> None:
        """
        Deletes all destination records for a given source record.
        
        - Used during incremental updates.
        - For when a record (specified by ``srcpkval``) has been updated in the
          source; wipe older entries for it in the destination database(s).

        Args:
            ifconfig:
                :class:`crate_anon.nlp_manager.input_field_config.InputFieldConfig`
                that defines the source database, table, and field (column)
            srcpkval:
                integer primary key (PK) value 
            srcpkstr:
                for tables with string PKs: the string PK value
            commit:
                execute a COMMIT after we have deleted the records?
                If you don't do this, we will get deadlocks in incremental mode.
                See e.g.
                http://dev.mysql.com/doc/refman/5.5/en/innodb-deadlocks.html
        """  # noqa
        session = self.get_session()
        srcdb = ifconfig.get_srcdb()
        srctable = ifconfig.get_srctable()
        srcfield = ifconfig.get_srcfield()
        destdb_name = self._destdb.name
        nlpdef_name = self._nlpdef.get_name()
        for tablename, desttable in self.tables().items():
            log.debug(f"delete_from_dest_dbs... {srcdb}.{srctable} -> "
                      f"{destdb_name}.{tablename}")
            # noinspection PyProtectedMember,PyPropertyAccess
            delquery = (
                desttable.delete().
                where(desttable.c._srcdb == srcdb).
                where(desttable.c._srctable == srctable).
                where(desttable.c._srcfield == srcfield).
                where(desttable.c._srcpkval == srcpkval).
                where(desttable.c._nlpdef == nlpdef_name)
            )
            if srcpkstr is not None:
                # noinspection PyProtectedMember,PyPropertyAccess
                delquery = delquery.where(desttable.c._srcpkstr == srcpkstr)
            with MultiTimerContext(timer, TIMING_DELETE_DEST_RECORD):
                session.execute(delquery)
            if commit:
                self._nlpdef.commit(session)

    def delete_where_srcpk_not(self,
                               ifconfig: InputFieldConfig,
                               temptable: Optional[Table]) -> None:
        """
        Function to help with deleting NLP destination records whose source
        records have been deleted.

        See :func:`crate_anon.nlp_manager.nlp_manager.delete_where_no_source`.

        Args:
            ifconfig:
                :class:`crate_anon.nlp_manager.input_field_config.InputFieldConfig`
                that defines the source database, table, and field (column).
            temptable:
                If this is specified (as an SQLAlchemy) table, we delete NLP
                destination records whose source PK has not been inserted into
                this table. Otherwise, we delete *all* NLP destination records
                from the source column.
        """
        destsession = self.get_session()
        srcdb = ifconfig.get_srcdb()
        srctable = ifconfig.get_srctable()
        srcfield = ifconfig.get_srcfield()
        for desttable_name, desttable in self.tables().items():
            log.debug(f"delete_where_srcpk_not... {srcdb}.{srctable} -> "
                      f"{self._destdb_name}.{desttable_name}")
            # noinspection PyProtectedMember,PyPropertyAccess
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
                # noinspection PyProtectedMember,PyPropertyAccess
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

    def get_destdb(self) -> DatabaseHolder:
        """
        Returns the destination database.
        """
        return self._destdb
