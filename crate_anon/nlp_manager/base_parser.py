#!/usr/bin/env python
# crate_anon/nlp_manager/base_parser.py

# Simple base class for all our NLP parsers (GATE, regex, ...)

from functools import lru_cache
import logging
from typing import Any, Dict, Iterator, List, Optional, Tuple

from sqlalchemy import BigInteger, Column, Index, Table

from crate_anon.nlp_manager.constants import SqlTypeDbIdentifier
from crate_anon.nlp_manager.input_field_config import InputFieldConfig
from crate_anon.nlp_manager.nlp_definition import NlpDefinition

log = logging.getLogger(__name__)


# =============================================================================
# Base class for all parser types
# =============================================================================

class NlpParser(object):
    FN_PK = '_pk'
    FN_NLPDEF = '_nlpdef'

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        self._nlpdef = nlpdef
        self._cfgsection = cfgsection
        self._commit = commit
        if nlpdef is not None:
            self._destdb_name = nlpdef.opt_str(cfgsection, 'destdb',
                                               required=True)
            self._destdb = nlpdef.get_database(self._destdb_name)

    @classmethod
    def _core_dest_columns(cls) -> List[Column]:
        return [
            Column(cls.FN_PK, BigInteger, primary_key=True,
                   autoincrement=True,
                   doc="Arbitrary PK of output record"),
            Column(cls.FN_NLPDEF, SqlTypeDbIdentifier,
                   doc="Name of the NLP definition producing this row"),
        ]

    def dest_tables_columns(self) -> Dict[str, List[Column]]:
        """
        Returns a dictionary of {tablename: destination_columns}.
        """
        raise NotImplementedError

    def dest_tables_indexes(self) -> Dict[str, List[Index]]:
        return {}

    def _get_metadata(self):
        return self._destdb.metadata

    def _get_session(self):
        return self._destdb.session

    def _get_engine(self):
        return self._destdb.engine

    def get_nlpdef_name(self) -> str:
        if self._nlpdef is None:
            return None
        return self._nlpdef.get_name()

    def get_parser_name(self) -> str:
        return getattr(self, 'NAME', None)

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
    def _assert_column_lists_identical(list_of_column_lists: List[Column],
                                       description: str) -> None:
        n = len(list_of_column_lists)
        if n <= 1:
            return
        for i in range(n - 1):
            if list_of_column_lists[i] != list_of_column_lists[i + 1]:
                msg = "Mismatch between {} lists: {}".format(
                    description, list_of_column_lists)
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

        source_columns = InputFieldConfig.get_srcref_columns_for_dest()
        self._assert_no_overlap("copy", copy_columns,
                                "source", source_columns)

        # Create one or more tables
        meta = self._get_metadata()
        tables = {}
        t_columns = self.dest_tables_columns()
        for tablename, destcols in t_columns.items():
            self._assert_no_overlap("copy", copy_columns,
                                    "destination", destcols)
            # And to check we haven't introduced any bugs internally:
            self._assert_no_overlap("source", source_columns,
                                    "destination", destcols)

            columns = (self._core_dest_columns() +
                       source_columns +
                       destcols +
                       copy_columns)
            copy_of_cols = [c.copy() for c in columns]

            t_indexes = self.dest_tables_indexes()
            dest_indexes = []
            if tablename in t_indexes:
                dest_indexes = t_indexes[tablename]
            copyindexes_list = [i.get_copy_indexes() for i in ifconfigs]
            self._assert_column_lists_identical(copyindexes_list, "index")
            copy_indexes = copyindexes_list[0]
            source_indexes = InputFieldConfig.get_srcref_indexes_for_dest()

            column_like_things = (
                copy_of_cols + source_indexes + dest_indexes + copy_indexes)
            log.critical(repr(column_like_things))
            tables[tablename] = Table(tablename, meta, *column_like_things)
            # You can put indexes in the column list:
            # http://docs.sqlalchemy.org/en/latest/core/constraints.html

            # NOTE that after creating the Table, all the column objects get
            # "contaminated" by the link to it, so you have to start afresh
            # with new column objects, or take a further copy, as above.

            # You can copy a Column, but not an Index.
        return tables

    def get_table(self, tablename: str) -> Table:
        tables = self.tables()
        assert tablename in tables
        return tables[tablename]

    def make_tables(self, drop_first: bool = False) -> None:
        assert self._destdb, "Cannot use tables() call without a database"
        engine = self._get_engine()
        tables = self.tables()
        for t in tables.values():
            pretty_name = "{}.{}".format(self._destdb.name, t.name)
            if drop_first:
                log.info("Dropping table {}".format(pretty_name))
                t.drop(engine, checkfirst=True)
            log.info("Creating table {} (with indexes)".format(pretty_name))
            t.create(engine, checkfirst=True)

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
        starting_fields_values[self.FN_NLPDEF] = self._nlpdef.get_name()
        session = self._get_session()
        n_values = 0
        for tablename, nlp_values in self.parse(text):
            # Merge dictionaries so EXISTING FIELDS/VALUES
            # (starting_fields_values) HAVE PRIORITY.
            nlp_values.update(starting_fields_values)
            sqla_table = self.get_table(tablename)
            # If we have superfluous keys in our dictionary, SQLAlchemy will
            # choke ("Unconsumed column names")
            column_names = [c.name for c in sqla_table.columns]
            final_values = {k: v for k, v in nlp_values.items()
                            if k in column_names}
            insertquery = sqla_table.insert().values(final_values)
            session.execute(insertquery)
            if self._commit:
                session.commit()  # or we get deadlocks in multiprocess mode
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
                           commit: bool = False) -> None:
        """
        Used during incremental updates.
        For when a record (specified by srcpkval) has been updated in the
        source; wipe older entries for it in the destination database(s).
        """
        session = self._get_session()
        srcdb = ifconfig.get_srcdb()
        srctable = ifconfig.get_srctable()
        srcpkfield = ifconfig.get_srcpkfield()
        destdb_name = self._destdb.name
        nlpdef_name = self._nlpdef.get_name()
        for tablename, desttable in self.tables():
            log.debug(
                "delete_from_dest_dbs... {}.{} -> {}.{}".format(
                    srcdb, srctable, destdb_name, tablename))
            # noinspection PyProtectedMember
            delquery = (
                desttable.delete().
                where(desttable.c._srcdb == srcdb).
                where(desttable.c._srctable == srctable).
                where(desttable.c._srcpkfield == srcpkfield).
                where(desttable.c._srcpkval == srcpkval).
                where(desttable.c._nlpdef == nlpdef_name)
            )
            session.execute(delquery)
            if commit:
                session.commit()
                # ... or we get deadlocks in incremental updates
                # http://dev.mysql.com/doc/refman/5.5/en/innodb-deadlocks.html

    def delete_where_srcpk_not(self,
                               ifconfig: InputFieldConfig,
                               src_pks: List[int]) -> None:
        destsession = self._get_session()
        srcdb = ifconfig.get_srcdb()
        srctable = ifconfig.get_srctable()
        for desttable_name, desttable in self.tables().items():
            log.debug(
                "delete_where_srcpk_not... {}.{} -> {}.{}".format(
                    srcdb, srctable, self._destdb_name, desttable_name))
            # noinspection PyProtectedMember
            dest_deletion_query = (
                desttable.delete().
                where(desttable.c._srcdb == srcdb).
                where(desttable.c._srctable == srctable).
                where(desttable.c._srcpkfield == ifconfig.get_srcpkfield()).
                where(desttable.c._nlpdef == self._nlpdef.get_name())
            )
            if src_pks:
                log.debug("... deleting selectively")
                # noinspection PyProtectedMember
                dest_deletion_query = dest_deletion_query.where(
                    ~desttable.c._srcpkval.in_(src_pks)
                )
            else:
                log.debug("... deleting all")
            destsession.execute(dest_deletion_query)
            destsession.commit()
