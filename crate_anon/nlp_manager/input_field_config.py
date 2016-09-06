##!/usr/bin/env python
# crate_anon/nlp_manager/input_field_config.py

import logging
from typing import Any, Dict, Iterator, List, Optional, Tuple

from cardinal_pythonlib.rnc_db import (
    ensure_valid_field_name,
    ensure_valid_table_name,
)
from sqlalchemy import BigInteger, Column, Index, Table
from sqlalchemy.sql import column, func, select, table

from crate_anon.common.sqla import table_exists
from crate_anon.nlp_manager.constants import SqlTypeDbIdentifier
from crate_anon.nlp_manager.models import NlpRecord
from crate_anon.nlp_manager.nlp_definition import NlpDefinition

log = logging.getLogger(__name__)

FN_SRCDB = '_srcdb'
FN_SRCTABLE = '_srctable'
FN_SRCPKFIELD = '_srcpkfield'
FN_SRCPKVAL = '_srcpkval'
FN_SRCFIELD = '_srcfield'


# =============================================================================
# Input field definition
# =============================================================================

class InputFieldConfig(object):
    """
    Class defining configuration for an input field (containing text).
    """

    def __init__(self, nlpdef: NlpDefinition, section: str) -> None:
        """
        Read config from a configparser section.
        """
        def opt_str(option: str) -> str:
            return nlpdef.opt_str(section, option, required=True)

        def opt_strlist(option: str,
                        required: bool = False,
                        lower: bool = True) -> List[str]:
            return nlpdef.opt_strlist(section, option, as_words=False,
                                      lower=lower, required=required)

        self._nlpdef = nlpdef

        self._srcdb = opt_str('srcdb')
        self._srctable = opt_str('srctable')
        self._srcpkfield = opt_str('srcpkfield')
        self._srcfield = opt_str('srcfield')
        self._copyfields = opt_strlist('copyfields')  # fieldnames
        self._indexed_copyfields = opt_strlist('indexed_copyfields')

        ensure_valid_table_name(self._srctable)
        ensure_valid_field_name(self._srcpkfield)
        ensure_valid_field_name(self._srcfield)
        allfields = [self._srcpkfield, self._srcfield] + self._copyfields
        if len(allfields) != len(set(allfields)):
            raise ValueError(
                "Field overlap in InputFieldConfig: {}".format(section))

        self._db = nlpdef.get_database(self._srcdb)

    def get_srcdb(self) -> str:
        return self._srcdb

    def get_srctable(self) -> str:
        return self._srctable

    def get_srcpkfield(self) -> str:
        return self._srcpkfield

    def get_srcfield(self) -> str:
        return self._srcfield

    def _get_source_session(self):
        return self._db.session

    def _get_source_metadata(self):
        return self._db.metadata

    def _get_source_engine(self):
        return self._db.engine

    def _get_progress_session(self):
        return self._nlpdef.get_progdb_session()

    @staticmethod
    def get_srcref_columns_for_dest() -> List[Column]:
        """Columns referring to the source."""
        return [
            Column(FN_SRCDB, SqlTypeDbIdentifier,
                   doc="Source database name (from CRATE NLP config)"),
            Column(FN_SRCTABLE, SqlTypeDbIdentifier,
                   doc="Source table name"),
            Column(FN_SRCPKFIELD, SqlTypeDbIdentifier,
                   doc="PK field (column) in source table"),
            Column(FN_SRCPKVAL, BigInteger,
                   doc="PK of source record"),
            Column(FN_SRCFIELD, SqlTypeDbIdentifier,
                   doc="Field (column) name of source text"),
        ]

    @staticmethod
    def get_srcref_indexes_for_dest() -> List[Index]:
        """Indexes for columns referring to the source."""
        # http://stackoverflow.com/questions/179085/multiple-indexes-vs-multi-column-indexes  # noqa
        return [
            Index('_idx_srcref',
                  FN_SRCDB, FN_SRCTABLE, FN_SRCPKFIELD, FN_SRCPKVAL),
        ]

    def _require_table_exists(self) -> None:
        if not table_exists(self._get_source_engine(), self._srctable):
            msg = "Missing source table: {}.{}".format(self._srcdb,
                                                       self._srctable)
            log.critical(msg)
            raise ValueError(msg)

    def get_copy_columns(self) -> List[Column]:
        # We read the column type from the source database.
        self._require_table_exists()
        meta = self._get_source_metadata()
        t = Table(self._srctable, meta, autoload=True)
        return [c.copy() for c in t.columns
                if c.name.lower() in self._copyfields]

    def get_copy_indexes(self) -> List[Index]:
        self._require_table_exists()
        meta = self._get_source_metadata()
        t = Table(self._srctable, meta, autoload=True)
        return [Index(c.copy()) for c in t.columns
                if c.name.lower() in self._indexed_copyfields]

    def gen_src_pks(self) -> Iterator(int):
        """
        Generate integer PKs from the source table specified for the
        InputFieldConfig.
        """
        session = self._get_source_session()
        query = (
            select([column(self._srcpkfield)]).
            select_from(table(self._srctable))
        )
        result = session.execute(query)
        for row in result:
            yield row[0]

    def gen_text(self,
                 tasknum: int = 0,
                 ntasks: int = 1) -> Iterator(Tuple[str, Dict[str, Any]]):
        """
        Generate text strings from the input database.
        Yields tuple of (text, dict), where the dict is a column-to-value
        mapping for all other fields (source reference fields, copy fields).
        """
        if 1 < ntasks <= tasknum:
            raise Exception("Invalid tasknum {}; must be <{}".format(
                tasknum, ntasks))
        base_dict = {
            FN_SRCDB: self._srcdb,
            FN_SRCTABLE: self._srctable,
            FN_SRCPKFIELD: self._srcpkfield,
            FN_SRCFIELD: self._srcfield,
        }
        session = self._get_source_session()
        pkcol = column(self._srcpkfield)
        selectcols = [pkcol, column(self._srcfield)]
        for extracol in self._copyfields:
            selectcols.append(column(extracol))
        query = (
            select(selectcols).
            select_from(table(self._srctable)).
            order_by(pkcol)
        )
        if ntasks > 1:
            query = query.where(pkcol % ntasks == tasknum)
        for row in session.execute(query):  # ... a generator itself
            pkval = row[0]
            text = row[1]
            other_values = dict(zip(self._copyfields, row[2:]))
            other_values[FN_SRCPKVAL] = pkval
            other_values.update(base_dict)
            yield text, other_values

    def get_count_max(self) -> int:
        """
        Counts records in the input table for the given InputFieldConfig.
        Used for progress monitoring.
        """
        session = self._get_source_session()
        pkcol = column(self._srcpkfield)
        query = (
            select([func.count(), func.max(pkcol)]).
            select_from(table(self._srctable)).
            order_by(pkcol)
        )
        result = session.execute(query)
        return result.fetchone()  # count, maximum

    def get_progress_record(self,
                            srcpkval: int,
                            srchash: str = None) -> Optional[NlpRecord]:
        """
        Fetch a progress record (NlpRecord) for the given source record, if one
        exists.
        """
        session = self._get_progress_session()
        query = (
            session.query(NlpRecord).
            filter(NlpRecord.srcdb == self._srcdb).
            filter(NlpRecord.srctable == self._srctable).
            filter(NlpRecord.srcpkfield == self._srcpkfield).
            filter(NlpRecord.srcpkval == srcpkval).
            filter(NlpRecord.srcfield == self._srcfield)
        )
        if srchash is not None:
            query = query.filter(NlpRecord.srchash == srchash)
        return query.one_or_none()

    def delete_progress_records_where_srcpk_not(self,
                                                src_pks: List[int]) -> None:
        progsession = self._get_progress_session()
        log.debug("delete_progress_records_where_srcpk_not... {}.{} -> "
                  "progressdb".format(self._srcdb, self._srctable))
        prog_deletion_query = (
            progsession.query(NlpRecord).
            filter(NlpRecord.srcdb == self._srcdb).
            filter(NlpRecord.srctable == self._srctable).
            filter(NlpRecord.srcpkfield == self._srcpkfield).
            filter(NlpRecord.nlpdef == self._nlpdef.get_name())
        )
        if src_pks:
            log.debug("... deleting selectively")
            prog_deletion_query = prog_deletion_query.filter(
                ~NlpRecord.srcpkval.in_(src_pks)
            )
        else:
            log.debug("... deleting all")
        progsession.execute(prog_deletion_query)
        progsession.commit()

