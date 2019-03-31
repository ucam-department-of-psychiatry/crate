#!/usr/bin/env python

"""
crate_anon/nlp_manager/input_field_config.py

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

**Class to define input fields for NLP.**

"""

import logging
# import sys
from typing import Any, Dict, Generator, List, Optional, Tuple

from cardinal_pythonlib.datetimefunc import get_now_utc_notz_datetime
from cardinal_pythonlib.hash import hash64
from cardinal_pythonlib.rnc_db import (
    ensure_valid_field_name,
    ensure_valid_table_name,
)
from cardinal_pythonlib.sqlalchemy.core_query import count_star
from cardinal_pythonlib.sqlalchemy.schema import (
    is_sqlatype_integer,
    get_column_type,
    table_or_view_exists,
)
from cardinal_pythonlib.timing import MultiTimerContext, timer
from sqlalchemy import BigInteger, Column, DateTime, Index, String, Table
from sqlalchemy.sql import and_, column, exists, null, or_, select, table

from crate_anon.nlp_manager.constants import (
    FN_CRATE_VERSION_FIELD,
    FN_WHEN_FETCHED,
    FN_NLPDEF,
    FN_PK,
    FN_SRCDATETIMEFIELD,
    FN_SRCDATETIMEVAL,
    FN_SRCDB,
    FN_SRCTABLE,
    FN_SRCPKFIELD,
    FN_SRCPKVAL,
    FN_SRCPKSTR,
    FN_SRCFIELD,
    MAX_SEMANTIC_VERSION_STRING_LENGTH,
    MAX_STRING_PK_LENGTH,
)
from crate_anon.common.parallel import is_my_job_by_hash_prehashed
from crate_anon.nlp_manager.constants import SqlTypeDbIdentifier
from crate_anon.nlp_manager.models import NlpRecord
# if sys.version_info.major >= 3 and sys.version_info.minor >= 5:
#     from crate_anon.nlp_manager import nlp_definition  # see PEP0484
from crate_anon.nlp_manager.nlp_definition import (
    full_sectionname,
    NlpConfigPrefixes,
    NlpDefinition,
)
from crate_anon.version import CRATE_VERSION

log = logging.getLogger(__name__)

TIMING_GEN_TEXT_SQL_SELECT = "gen_text_sql_select"
TIMING_PROCESS_GEN_TEXT = "process_generated_text"
TIMING_PROGRESS_DB_SELECT = "progress_db_select"
TIMING_PROGRESS_DB_DELETE = "progress_db_delete"


# =============================================================================
# Input field definition
# =============================================================================

class InputFieldConfig(object):
    """
    Class defining an input field for NLP (containing text).

    See the documentation for the :ref:`NLP config file <nlp_config>`.
    """

    def __init__(self, nlpdef: NlpDefinition, section: str) -> None:
        """
        Read config from a configparser section, and also associate with a
        specific NLP definition.

        Args:
            nlpdef:
                :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`,
                the master NLP definition, referring to the master config file
                etc.
            section:
                config section name for the input field definition
        """
        sectionname = full_sectionname(NlpConfigPrefixes.INPUT, section)

        def opt_str(option: str, required: bool = True) -> str:
            return nlpdef.opt_str(sectionname, option, required=required)

        def opt_strlist(option: str,
                        required: bool = False,
                        lower: bool = True) -> List[str]:
            return nlpdef.opt_strlist(sectionname, option, as_words=False,
                                      lower=lower, required=required)

        def opt_int(option: str, default: Optional[int]) -> Optional[int]:
            return nlpdef.opt_int(sectionname, option, default=default)

        # def opt_bool(option: str, default: bool) -> bool:
        #     return nlpdef.opt_bool(section, option, default=default)

        self._nlpdef = nlpdef

        self._srcdb = opt_str('srcdb')
        self._srctable = opt_str('srctable')
        self._srcpkfield = opt_str('srcpkfield')
        self._srcfield = opt_str('srcfield')
        self._srcdatetimefield = opt_str('srcdatetimefield',
                                         required=False)  # new in v0.18.52
        # Make these case-sensitive to avoid our failure in renaming SQLA
        # Column objects to be lower-case:
        self._copyfields = opt_strlist('copyfields', lower=False)  # fieldnames
        self._indexed_copyfields = opt_strlist('indexed_copyfields',
                                               lower=False)
        self._debug_row_limit = opt_int('debug_row_limit', default=0)
        # self._fetch_sorted = opt_bool('fetch_sorted', default=True)

        # In case we want to store this value after running
        # 'nlpdef.get_ifconfigs()' so that we can later re-create the ifconfig
        self.section = section

        ensure_valid_table_name(self._srctable)
        ensure_valid_field_name(self._srcpkfield)
        ensure_valid_field_name(self._srcfield)
        if self._srcdatetimefield:
            ensure_valid_field_name(self._srcdatetimefield)

        if len(set(self._indexed_copyfields)) != len(self._indexed_copyfields):
            raise ValueError(
                f"Redundant indexed_copyfields: {self._indexed_copyfields}")

        if len(set(self._copyfields)) != len(self._copyfields):
            raise ValueError(f"Redundant copyfields: {self._copyfields}")

        indexed_not_copied = set(self._indexed_copyfields) - set(
            self._copyfields)
        if indexed_not_copied:
            raise ValueError(f"Fields in index_copyfields but not in "
                             f"copyfields: {indexed_not_copied}")

        # allfields = [self._srcpkfield, self._srcfield] + self._copyfields
        # if len(allfields) != len(set(allfields)):
        #     raise ValueError(
        #         f"Field overlap in InputFieldConfig: {section}")
        # RE-THOUGHT: OK to copy source text fields etc. if desired.
        # It's fine in SQL to say SELECT a, a FROM mytable;

        self._db = nlpdef.get_database(self._srcdb)

    def get_srcdb(self) -> str:
        """
        Returns the name of the source database.
        """
        return self._srcdb

    def get_srctable(self) -> str:
        """
        Returns the name of the source table.
        """
        return self._srctable

    def get_srcpkfield(self) -> str:
        """
        Returns the name of the primary key (PK) field (column) in the source
        table.
        """
        return self._srcpkfield

    def get_srcfield(self) -> str:
        """
        Returns the name of the text field (column) in the source table.
        """
        return self._srcfield

    def get_srcdatetimefield(self) -> str:  # new in v0.18.52
        """
        Returns the name of the field (column) in the source table that defines
        the date/time of the source text.
        """
        return self._srcdatetimefield

    def get_source_session(self):
        """
        Returns the SQLAlchemy ORM :class:`Session` for the source database.
        """
        return self._db.session

    def _get_source_metadata(self):
        """
        Returns the SQLAlchemy :class:`Metadata` for the source database,
        used for reflection (inspection) of the source database structure.
        """
        return self._db.metadata

    def _get_source_engine(self):
        """
        Returns the SQLAlchemy Core :class:`Engine` for the source database.
        """
        return self._db.engine

    def _get_progress_session(self):
        """
        Returns the SQLAlchemy ORM :class:`Session` for the progress database.
        """
        return self._nlpdef.get_progdb_session()

    @staticmethod
    def get_core_columns_for_dest() -> List[Column]:
        """
        Returns the columns used NLP destination tables, primarily describing
        the source. See :ref:`Standard NLP output columns
        <standard_nlp_output_columns>`.

        Returns:
            a list of SQLAlchemy :class:`Column` objects
        """
        return [
            Column(FN_PK, BigInteger, primary_key=True,
                   autoincrement=True,
                   doc="Arbitrary primary key (PK) of output record"),
            Column(FN_NLPDEF, SqlTypeDbIdentifier,
                   doc="Name of the NLP definition producing this row"),
            Column(FN_SRCDB, SqlTypeDbIdentifier,
                   doc="Source database name (from CRATE NLP config)"),
            Column(FN_SRCTABLE, SqlTypeDbIdentifier,
                   doc="Source table name"),
            Column(FN_SRCPKFIELD, SqlTypeDbIdentifier,
                   doc="PK field (column) name in source table"),
            Column(FN_SRCPKVAL, BigInteger,
                   doc="PK of source record (or integer hash of PK if the PK "
                       "is a string)"),
            Column(FN_SRCPKSTR, String(MAX_STRING_PK_LENGTH),
                   doc="NULL if the table has an integer PK, but the PK if "
                       "the PK was a string, to deal with hash collisions. "
                       "Max length: {}".format(MAX_STRING_PK_LENGTH)),
            Column(FN_SRCFIELD, SqlTypeDbIdentifier,
                   doc="Field (column) name of source text"),
            Column(FN_SRCDATETIMEFIELD, SqlTypeDbIdentifier,
                   doc="Date/time field (column) name in source table"),
            Column(FN_SRCDATETIMEVAL, DateTime, nullable=True,
                   doc="Date/time of source field"),
            Column(FN_CRATE_VERSION_FIELD,
                   String(MAX_SEMANTIC_VERSION_STRING_LENGTH), nullable=True,
                   doc="Version of CRATE that generated this NLP record."),
            Column(FN_WHEN_FETCHED, DateTime, nullable=True,
                   doc="Date/time that the NLP processor fetched the record "
                       "from the source database."),
        ]

    @staticmethod
    def get_core_indexes_for_dest() -> List[Index]:
        """
        Returns the core indexes to be applied to the destination tables.
        Primarily, these are for columns that refer to the source.
        
        Returns:
            a list of SQLAlchemy :class:`Index` objects
        
        See
        
        - http://stackoverflow.com/questions/179085/multiple-indexes-vs-multi-column-indexes
        """  # noqa
        return [
            Index('_idx_srcref',
                  # Remember, order matters; more to less specific
                  # See also BaseNlpParser.delete_dest_record
                  FN_SRCPKVAL,
                  FN_NLPDEF,
                  FN_SRCFIELD,
                  FN_SRCTABLE,
                  FN_SRCDB,
                  FN_SRCPKSTR),
            Index('_idx_srcdate',
                  FN_SRCDATETIMEVAL),
            Index('_idx_deletion',
                  # We sometimes delete just using the following; see
                  # BaseNlpParser.delete_where_srcpk_not
                  FN_NLPDEF,
                  FN_SRCFIELD,
                  FN_SRCTABLE,
                  FN_SRCDB),
        ]

    def _require_table_or_view_exists(self) -> None:
        """
        Ensure that the source table exists, or raise :exc:`RuntimeError`.
        """
        if not table_or_view_exists(self._get_source_engine(), self._srctable):
            msg = f"Missing source table: {self._srcdb}.{self._srctable}"
            log.critical(msg)
            raise RuntimeError(msg)

    def get_copy_columns(self) -> List[Column]:
        """
        Returns the columns that the user has requested to be copied from the
        source table to the NLP destination table.

        Returns:
            a list of SQLAlchemy :class:`Column` objects

        """
        # We read the column type from the source database.
        self._require_table_or_view_exists()
        meta = self._get_source_metadata()
        t = Table(self._srctable, meta, autoload=True)
        copy_columns = []  # type: List[Column]
        processed_copy_column_names = []  # type: List[str]
        for c in t.columns:
            # if c.name.lower() in self._copyfields:
            if c.name in self._copyfields:
                copied = c.copy()
                # Force lower case:
                # copied.name = copied.name.lower()
                # copied.name = quoted_name(copied.name.lower(), None)
                # ... this is not working properly. Keep getting an
                # "Unconsumed column names" error with e.g. a source field of
                # "Text".
                # Try making copyfields case-sensitive instead.
                copy_columns.append(copied)
                processed_copy_column_names.append(c.name)
        # Check all requested fields are present:
        missing = set(self._copyfields) - set(processed_copy_column_names)
        if missing:
            raise RuntimeError(
                f"The following fields were requested to be copied but are "
                f"absent from the source (NB case-sensitive): {missing}")
        # log.critical(copy_columns)
        return copy_columns

    def get_copy_indexes(self) -> List[Index]:
        """
        Returns indexes that should be made in the destination table for
        columns that the user has requested to be copied from the source.

        Returns:
            a list of SQLAlchemy :class:`Index` objects

        """
        self._require_table_or_view_exists()
        meta = self._get_source_metadata()
        t = Table(self._srctable, meta, autoload=True)
        copy_indexes = []  # type: List[Index]
        processed_copy_index_col_names = []  # type: List[str]
        for c in t.columns:
            # if c.name.lower() in self._indexed_copyfields:
            if c.name in self._indexed_copyfields:
                copied = c.copy()
                # See above re case.
                idx_name = f"idx_{c.name}"
                copy_indexes.append(Index(idx_name, copied))
                processed_copy_index_col_names.append(c.name)
        missing = set(self._indexed_copyfields) - set(
            processed_copy_index_col_names)
        if missing:
            raise ValueError(
                f"The following fields were requested to be copied/indexed but"
                f" are absent from the source (NB case-sensitive): {missing}")
        return copy_indexes

    def is_pk_integer(self):
        """
        Is the primary key (PK) of the source table an integer?
        """
        pkcoltype = get_column_type(self._get_source_engine(), self._srctable,
                                    self._srcpkfield)
        if not pkcoltype:
            raise ValueError(f"Unable to get column type for column "
                             f"{self._srctable}.{self._srcpkfield}")
        pk_is_integer = is_sqlatype_integer(pkcoltype)
        # log.debug(f"pk_is_integer: {repr(pkcoltype)} -> {pk_is_integer}")
        return pk_is_integer

    def gen_text(self, tasknum: int = 0,
                 ntasks: int = 1) -> Generator[Tuple[str, Dict[str, Any]],
                                               None, None]:
        """
        Generate text strings from the source database.

        Yields:
            tuple: ``text, dict``, where ``text`` is the source text and
            ``dict`` is a column-to-value mapping for all other fields (source
            reference fields, copy fields).
        """
        if 1 < ntasks <= tasknum:
            raise Exception(f"Invalid tasknum {tasknum}; must be <{ntasks}")

        # ---------------------------------------------------------------------
        # Values that are constant to all items we will generate
        # (i.e. database/field *names*, plus CRATE version info)
        # ---------------------------------------------------------------------
        base_dict = {
            FN_SRCDB: self._srcdb,
            FN_SRCTABLE: self._srctable,
            FN_SRCPKFIELD: self._srcpkfield,
            FN_SRCFIELD: self._srcfield,
            FN_SRCDATETIMEFIELD: self._srcdatetimefield,
            FN_CRATE_VERSION_FIELD: CRATE_VERSION,
        }

        # ---------------------------------------------------------------------
        # Build a query
        # ---------------------------------------------------------------------
        session = self.get_source_session()
        pkcol = column(self._srcpkfield)
        # ... don't use is_sqlatype_integer with this; it's a column clause,
        # not a full column definition.
        pk_is_integer = self.is_pk_integer()

        # Core columns
        colindex_pk = 0
        colindex_text = 1
        colindex_datetime = 2
        colindex_remainder_start = 3
        selectcols = [
            pkcol,
            column(self._srcfield),
            column(self._srcdatetimefield) if self._srcdatetimefield else null()  # noqa
        ]
        # User-specified extra columns
        for extracol in self._copyfields:
            selectcols.append(column(extracol))

        query = select(selectcols).select_from(table(self._srctable))
        # not ordered...
        # if self._fetch_sorted:
        #     query = query.order_by(pkcol)

        # ---------------------------------------------------------------------
        # Plan our parallel-processing approach
        # ---------------------------------------------------------------------
        distribute_by_hash = False
        if ntasks > 1:
            if pk_is_integer:
                # Integer PK, so we can be efficient and bake the parallel
                # processing work division into the SQL:
                query = query.where(pkcol % ntasks == tasknum)
            else:
                distribute_by_hash = True

        # ---------------------------------------------------------------------
        # Execute the query
        # ---------------------------------------------------------------------
        nrows_returned = 0
        with MultiTimerContext(timer, TIMING_GEN_TEXT_SQL_SELECT):
            when_fetched = get_now_utc_notz_datetime()
            result = session.execute(query)
            for row in result:  # ... a generator itself
                with MultiTimerContext(timer, TIMING_PROCESS_GEN_TEXT):
                    # Get PK value
                    pkval = row[colindex_pk]

                    # Deal with non-integer PKs
                    if pk_is_integer:
                        hashed_pk = None  # remove warning about reference before assignment  # noqa
                    else:
                        hashed_pk = hash64(pkval)
                        if (distribute_by_hash and
                                not is_my_job_by_hash_prehashed(
                                    hashed_pk, tasknum, ntasks)):
                            continue

                    # Optional debug limit on the number of rows
                    if 0 < self._debug_row_limit <= nrows_returned:
                        log.warning(
                            f"Table {self._srcdb}.{self._srctable}: not "
                            f"fetching more than {self._debug_row_limit} rows "
                            f"(in total for this process) due to debugging "
                            f"limits")
                        result.close()  # http://docs.sqlalchemy.org/en/latest/core/connections.html  # noqa
                        return

                    # Get text
                    text = row[colindex_text]
                    if not text:
                        continue

                    # Get everything else
                    other_values = dict(zip(self._copyfields,
                                            row[colindex_remainder_start:]))
                    if pk_is_integer:
                        other_values[FN_SRCPKVAL] = pkval  # an integer
                        other_values[FN_SRCPKSTR] = None
                    else:  # hashed_pk will have been set above
                        other_values[FN_SRCPKVAL] = hashed_pk  # an integer
                        other_values[FN_SRCPKSTR] = pkval  # a string etc.
                    other_values[FN_SRCDATETIMEVAL] = row[colindex_datetime]
                    other_values[FN_WHEN_FETCHED] = when_fetched
                    other_values.update(base_dict)

                    # Yield the result
                    yield text, other_values
                    nrows_returned += 1

    def get_count(self) -> int:
        """
        Counts records in the source table.

        Used for progress monitoring.
        """
        return count_star(session=self.get_source_session(),
                          tablename=self._srctable)

    def get_progress_record(self,
                            srcpkval: int,
                            srcpkstr: str = None) -> Optional[NlpRecord]:
        """
        Fetch a progress record for the given source record, if one exists.

        Returns:
            :class:`crate_anon.nlp_manager.models.NlpRecord`, or ``None``
        """
        session = self._get_progress_session()
        query = (
            session.query(NlpRecord).
            filter(NlpRecord.srcdb == self._srcdb).
            filter(NlpRecord.srctable == self._srctable).
            filter(NlpRecord.srcpkval == srcpkval).
            filter(NlpRecord.srcfield == self._srcfield).
            filter(NlpRecord.nlpdef == self._nlpdef.get_name())
            # Order not important (though the order of the index certainly
            # is; see NlpRecord.__table_args__).
            # http://stackoverflow.com/questions/11436469/does-order-of-where-clauses-matter-in-sql  # noqa
        )
        if srcpkstr is not None:
            query = query.filter(NlpRecord.srcpkstr == srcpkstr)
        # log.critical(query)
        with MultiTimerContext(timer, TIMING_PROGRESS_DB_SELECT):
            # This was surprisingly slow under SQL Server testing.
            return query.one_or_none()

    def gen_src_pks(self) -> Generator[Tuple[int, Optional[str]], None, None]:
        """
        Generate integer PKs from the source table.

        For tables with an integer PK, yields tuples: ``pk_value, None``.

        For tables with a string PK, yields tuples: ``pk_hash, pk_value``.

        - Timing is subsumed under the timer named
          ``TIMING_DELETE_WHERE_NO_SOURCE``.
        """
        session = self.get_source_session()
        query = (
            select([column(self._srcpkfield)]).
            select_from(table(self._srctable))
        )
        result = session.execute(query)
        if self.is_pk_integer():
            for row in result:
                yield row[0], None
        else:
            for row in result:
                pkval = row[0]
                yield hash64(pkval), pkval

    def delete_progress_records_where_srcpk_not(
            self,
            temptable: Optional[Table]) -> None:
        """
        If ``temptable`` is None, deletes all progress records for this input
        field/NLP definition.

        If ``temptable`` is a table, deletes records from the progress database
        (from this input field/NLP definition) whose source PK is not in the
        temporary table. (Used for deleting NLP records when the source has
        subsequently been deleted.)

        """
        progsession = self._get_progress_session()
        log.debug(f"delete_progress_records_where_srcpk_not... "
                  f"{self._srcdb}.{self._srctable} -> progressdb")
        prog_deletion_query = (
            progsession.query(NlpRecord).
            filter(NlpRecord.srcdb == self._srcdb).
            filter(NlpRecord.srctable == self._srctable).
            # unnecessary # filter(NlpRecord.srcpkfield == self._srcpkfield).
            filter(NlpRecord.nlpdef == self._nlpdef.get_name())
        )
        if temptable is not None:
            log.debug("... deleting selectively")
            temptable_pkvalcol = temptable.columns[FN_SRCPKVAL]
            temptable_pkstrcol = temptable.columns[FN_SRCPKSTR]
            prog_deletion_query = prog_deletion_query.filter(
                ~exists().where(
                    and_(
                        NlpRecord.srcpkval == temptable_pkvalcol,
                        or_(
                            NlpRecord.srcpkstr == temptable_pkstrcol,
                            and_(
                                NlpRecord.srcpkstr.is_(None),
                                temptable_pkstrcol.is_(None)
                            )
                        )
                    )
                )
            )
        else:
            log.debug("... deleting all")
        with MultiTimerContext(timer, TIMING_PROGRESS_DB_DELETE):
            prog_deletion_query.delete(synchronize_session=False)
            # http://docs.sqlalchemy.org/en/latest/orm/query.html#sqlalchemy.orm.query.Query.delete  # noqa
        self._nlpdef.commit(progsession)

    def delete_all_progress_records(self) -> None:
        """
        Deletes **all** records from the progress database for this NLP
        definition (across all source tables/columns).
        """
        progsession = self._get_progress_session()
        prog_deletion_query = (
            progsession.query(NlpRecord).
            filter(NlpRecord.nlpdef == self._nlpdef.get_name())
        )
        log.debug(f"delete_all_progress_records for NLP definition: "
                  f"{self._nlpdef.get_name()}")
        with MultiTimerContext(timer, TIMING_PROGRESS_DB_DELETE):
            prog_deletion_query.delete(synchronize_session=False)
        self._nlpdef.commit(progsession)
