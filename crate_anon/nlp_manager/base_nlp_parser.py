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

from abc import ABC, abstractmethod
from functools import lru_cache
import json
import logging
import sys
from typing import (
    Any, Dict, Generator, Iterable, List, Optional, TextIO, Tuple,
    TYPE_CHECKING,
)

from cardinal_pythonlib.reprfunc import auto_repr
from cardinal_pythonlib.timing import MultiTimerContext, timer
from cardinal_pythonlib.sqlalchemy.schema import (
    column_lists_equal,
    index_lists_equal
)
# OK to import "registry"; see
# https://github.com/zzzeek/sqlalchemy/blob/master/README.dialects.rst
# noinspection PyProtectedMember
from sqlalchemy.dialects import registry
# from sqlalchemy.dialects.mssql.base import MSDialect
from sqlalchemy.engine.base import Engine
from sqlalchemy.orm.session import Session
from sqlalchemy.schema import Column, Index, Table
from sqlalchemy.sql import and_, exists, or_
from sqlalchemy.sql.schema import MetaData
from sqlalchemy.types import Integer, Text

from crate_anon.anonymise.dbholder import DatabaseHolder
from crate_anon.common.stringfunc import does_text_contain_word_chars
from crate_anon.nlp_manager.constants import (
    FN_NLPDEF,
    FN_SRCPKVAL,
    FN_SRCPKSTR,
    full_sectionname,
    NlpConfigPrefixes,
    ProcessorConfigKeys,
    GateFieldNames as GateFN,
    SqlTypeDbIdentifier,
    MAX_SQL_FIELD_LEN,
)
from crate_anon.nlp_manager.input_field_config import InputFieldConfig
from crate_anon.nlp_manager.nlp_definition import (
    NlpDefinition,
)
from crate_anon.nlprp.api import NlprpServerProcessor
from crate_anon.nlprp.constants import (
    ALL_SQL_DIALECTS,
    NlprpKeys,
    NlprpValues,
    SqlDialects,
)
from crate_anon.version import CRATE_VERSION

if TYPE_CHECKING:
    from sqlalchemy.engine.interfaces import Dialect

log = logging.getLogger(__name__)

DEFAULT_NLPRP_SQL_DIALECT = SqlDialects.MYSQL
TIMING_DELETE_DEST_RECORD = "BaseNlpParser_delete_dest_record"
TIMING_INSERT = "BaseNlpParser_sql_insert"
TIMING_PARSE = "parse"
TIMING_HANDLE_PARSED = "handled_parsed"


# =============================================================================
# Exception meaning "could not parse this piece of text"
# =============================================================================

class TextProcessingFailed(Exception):
    pass


# =============================================================================
# Base class for all parser types
# =============================================================================

class TableMaker(ABC):
    """
    Base class for all CRATE NLP processors, including those that talk to
    third-party software. Manages the interface to databases for results
    storage, etc.
    """

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False,
                 name: str = "?") -> None:
        """
        Args:
            nlpdef:
                a :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
            cfgsection:
                the name of a CRATE NLP config file section, TO WHICH we will
                add a "processor:" prefix (from which section we may choose to
                get extra config information)
            commit:
                force a COMMIT whenever we insert data? You should specify this
                in multiprocess mode, or you may get database deadlocks.
            name:
                friendly name for the parser
        """
        self._nlpdef = nlpdef
        self._cfgsection = cfgsection
        self._commit = commit
        self._name = name
        self._destdb_name = None  # type: Optional[str]
        self._destdb = None  # type: Optional[DatabaseHolder]
        if nlpdef is not None:
            self._sectionname = full_sectionname(
                NlpConfigPrefixes.PROCESSOR, cfgsection)
            self._destdb_name = nlpdef.opt_str(
                self._sectionname, ProcessorConfigKeys.DESTDB, required=True)
            self._destdb = nlpdef.get_database(self._destdb_name)
        else:
            self._sectionname = ""
            self._destdb_name = ""
            self._destdb = None  # type: Optional[DatabaseHolder]

    def __str__(self) -> str:
        return self.classname()

    def __repr__(self) -> str:
        return auto_repr(self)

    @classmethod
    def classname(cls) -> str:
        """
        Returns the short Python name of this class.
        """
        return cls.__name__

    @classmethod
    def fully_qualified_name(cls) -> str:
        """
        Returns the class's fully qualified name.
        """
        # This may be imperfect; see
        # https://stackoverflow.com/questions/2020014/get-fully-qualified-class-name-of-an-object-in-python  # noqa
        # https://www.python.org/dev/peps/pep-3155/
        return ".".join([cls.__module__,
                         cls.__qualname__])

    @classmethod
    def print_info(cls, file: TextIO = sys.stdout) -> None:
        """
        Print general information about this NLP processor.

        Args:
            file: file to print to (default: stdout)
        """
        print("Base class for all CRATE NLP parsers", file=file)

    @abstractmethod
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
        Returns the NLP parser's friendly name
        """
        return self._name

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

    # Put these GATE methods here because it's also useful for Cloud processors

    @staticmethod
    def _standard_gate_columns() -> List[Column]:
        """
        Returns standard columns for GATE output.
        """
        return [
            Column(GateFN.SET, SqlTypeDbIdentifier,
                   comment="GATE output set name"),
            Column(GateFN.TYPE, SqlTypeDbIdentifier,
                   comment="GATE annotation type name"),
            Column(GateFN.ID, Integer,
                   comment="GATE annotation ID (not clear this is very useful)"),  # noqa
            Column(GateFN.STARTPOS, Integer,
                   comment="Start position in the content"),
            Column(GateFN.ENDPOS, Integer,
                   comment="End position in the content"),
            Column(GateFN.CONTENT, Text,
                   comment="Full content marked as relevant."),
        ]

    @staticmethod
    def _standard_gate_indexes() -> List[Index]:
        """
        Returns standard indexes for GATE output.
        """
        return [
            Index('_idx__set', GateFN.SET, mysql_length=MAX_SQL_FIELD_LEN),
        ]

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
        try:
            return tables[tablename]
        except KeyError:
            raise KeyError(f"No destination table for this NLP processor "
                           f"named {tablename!r}")

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


# =============================================================================
# Base class for all local parser types
# =============================================================================

class BaseNlpParser(TableMaker):
    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False,
                 name: str = "?") -> None:
        super().__init__(nlpdef, cfgsection, commit, name=name)

    # -------------------------------------------------------------------------
    # NLP processing
    # -------------------------------------------------------------------------

    @abstractmethod
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

        Raises:
            :exc:`crate_anon.nlp_manager.base_nlp_parser.TextProcessingFailed`
            if we could not process this text.
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

        Raises:
            :exc:`crate_anon.nlp_manager.base_nlp_parser.TextProcessingFailed`
            if this parser could not process the text
        """
        if not does_text_contain_word_chars(text):
            # log.warning(f"No word characters found in {text}")
            # ... the warning occurs frequently so slows down processing
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

    @abstractmethod
    def test(self, verbose: bool = False) -> None:
        """
        Performs a self-test on the NLP processor.

        Args:
            verbose: be verbose?
        """
        raise NotImplementedError(f"No test function for regex class: "
                                  f"{self.classname()}")

    def test_parser(self, test_strings: List[str]) -> None:
        """
        Tests the NLP processor's parser with a set of test strings.
        """
        log.info(f"Testing parser: {self.classname()}")
        for text in test_strings:
            log.info(f"    {text} -> {list(self.parse(text))}")
        log.info("... OK")

    # -------------------------------------------------------------------------
    # NLPRP info
    # -------------------------------------------------------------------------

    @staticmethod
    def describe_sqla_col(column: Column, sql_dialect: str = None) \
            -> Dict[str, Any]:
        """
        Describes a single SQLAlchemy :class:`Column` in the :ref:`NLPRP
        <nlprp>` format, which follows ``INFORMATION_SCHEMA.COLUMNS`` closely.

        Args:
            column: the :class:`Column`
            sql_dialect: preferred SQL dialect for response, or ``None`` for
                a default
        """
        sql_dialect = sql_dialect or DEFAULT_NLPRP_SQL_DIALECT
        assert sql_dialect in ALL_SQL_DIALECTS, (
            f"Unknown SQL dialect {sql_dialect!r}; must be one of "
            f"{ALL_SQL_DIALECTS}"
        )
        dialect = registry.load(sql_dialect)()  # type: Dialect
        # log.critical(f"dialect: {dialect}")
        # dialect = MSDialect()
        column_type = column.type.compile(dialect)
        data_type = column_type.partition("(")[0]
        # ... https://stackoverflow.com/questions/27387415/how-would-i-get-everything-before-a-in-a-string-python  # noqa
        return {
            NlprpKeys.COLUMN_NAME: column.name,
            NlprpKeys.COLUMN_TYPE: column_type,
            NlprpKeys.DATA_TYPE: data_type,
            NlprpKeys.IS_NULLABLE: column.nullable,
            NlprpKeys.COLUMN_COMMENT: column.comment,
        }

    def nlprp_schema_info(self, sql_dialect: str = None) -> Dict[str, Any]:
        """
        Returns a dictionary for the ``schema_type`` parameter, and associated
        parameters describing the schema (e.g. ``tabular_schema``), of the
        NLPRP :ref:`list_processors <nlprp_list_processors>` command.

        This is not a classmethod, because it may be specialized as we load
        external schema information (e.g. GATE processors).

        Args:
            sql_dialect: preferred SQL dialect for ``tabular_schema``
        """
        sql_dialect = sql_dialect or DEFAULT_NLPRP_SQL_DIALECT
        tabular_schema = {}  # type: Dict[str, List[Dict[str, Any]]]
        for tablename, columns in self.dest_tables_columns().items():
            colinfo = []  # type: List[Dict[str, Any]]
            for column in columns:
                colinfo.append(self.describe_sqla_col(column, sql_dialect))
            tabular_schema[tablename] = colinfo
        schema_info = {
            NlprpKeys.SCHEMA_TYPE: NlprpValues.TABULAR,
            NlprpKeys.SQL_DIALECT: sql_dialect,
            NlprpKeys.TABULAR_SCHEMA: tabular_schema,
        }
        return schema_info

    @classmethod
    def nlprp_name(cls) -> str:
        """
        Returns the processor's name for use in response to the NLPRP
        :ref:`list_processors <nlprp_list_processors>` command.

        The default is the fully qualified module/class name -- because this is
        highly unlikely to clash with any other NLP processors on a given
        server.
        """
        return cls.fully_qualified_name()

    @classmethod
    def nlprp_title(cls) -> str:
        """
        Returns the processor's title for use in response to the NLPRP
        :ref:`list_processors <nlprp_list_processors>` command.

        The default is the short Python class name.
        """
        return cls.__name__

    @classmethod
    def nlprp_version(cls) -> str:
        """
        Returns the processor's version for use in response to the NLPRP
        :ref:`list_processors <nlprp_list_processors>` command.

        The default is the current CRATE version.
        """
        return CRATE_VERSION

    @classmethod
    def nlprp_is_default_version(cls) -> bool:
        """
        Returns whether this processor is the default version of its name, for
        use in response to the NLPRP :ref:`list_processors
        <nlprp_list_processors>` command.

        The default is ``True``.
        """
        return True

    @classmethod
    def nlprp_description(cls) -> str:
        """
        Returns the processor's description for use in response to the NLPRP
        :ref:`list_processors <nlprp_list_processors>` command.

        Uses each processor's docstring, and reformats it slightly.
        """
        # PyCharm thinks that __doc__ is bytes, but it's str!
        docstring = str(cls.__doc__)
        docstring = docstring.replace("\n", " ")
        # https://stackoverflow.com/questions/2077897/substitute-multiple-whitespace-with-single-whitespace-in-python
        return " ".join(docstring.split())

    def nlprp_server_processor(self, sql_dialect: str = None) \
            -> NlprpServerProcessor:
        schema_info = self.nlprp_schema_info(sql_dialect)
        return NlprpServerProcessor(
            name=self.nlprp_name(),
            title=self.nlprp_title(),
            version=self.nlprp_version(),
            is_default_version=self.nlprp_is_default_version(),
            description=self.nlprp_description(),
            schema_type=schema_info[NlprpKeys.SCHEMA_TYPE],
            sql_dialect=schema_info.get(NlprpKeys.SQL_DIALECT),
            tabular_schema=schema_info.get(NlprpKeys.TABULAR_SCHEMA)
        )

    def nlprp_processor_info(self, sql_dialect: str = None) -> Dict[str, Any]:
        """
        Returns a dictionary suitable for use as this processor's response to
        the NLPRP :ref:`list_processors <nlprp_list_processors>` command.

        This is not a classmethod, because it may be specialized as we load
        external schema information (e.g. GATE processors).

        Args:
            sql_dialect: preferred SQL dialect for ``tabular_schema``
        """
        return self.nlprp_server_processor(sql_dialect).infodict

    def nlprp_processor_info_json(self,
                                  indent: int = 4,
                                  sort_keys: bool = True,
                                  sql_dialect: str = None) -> str:
        """
        Returns a formatted JSON string from :func:`nlprp_schema_info`.
        This is primarily for debugging.

        Args:
            indent: number of spaces for indentation
            sort_keys: sort keys?
            sql_dialect: preferred SQL dialect for ``tabular_schema``, or
                ``None`` for default
        """
        json_structure = self.nlprp_processor_info(sql_dialect=sql_dialect)
        return json.dumps(json_structure, indent=indent, sort_keys=sort_keys)

