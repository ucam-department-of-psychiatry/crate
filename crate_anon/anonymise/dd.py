#!/usr/bin/env python

"""
crate_anon/anonymise/dd.py

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

**Data dictionary classes for CRATE anonymiser.**

The data dictionary is a TSV file, for ease of editing by multiple authors,
rather than a database table.

"""

# =============================================================================
# Imports
# =============================================================================

from collections import Counter, OrderedDict
from dataclasses import dataclass
from functools import lru_cache
from itertools import zip_longest
import logging
import operator
from typing import (
    AbstractSet, Any, Callable, Dict, List, Optional,
    Tuple, TYPE_CHECKING, Union
)

from cardinal_pythonlib.sql.validation import is_sqltype_integer
from cardinal_pythonlib.sqlalchemy.dialect import SqlaDialectName
from cardinal_pythonlib.sqlalchemy.schema import (
    is_sqlatype_integer,
    is_sqlatype_string,
    is_sqlatype_text_over_one_char,
)
from sortedcontainers import SortedSet
import sqlalchemy.exc
from sqlalchemy import Column, Table, DateTime
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.sql.sqltypes import String, TypeEngine

# don't import config: circular dependency would have to be sorted out
from crate_anon.anonymise.constants import (
    AlterMethodType,
    AnonymiseConfigKeys,
    Decision,
    IndexType,
    ScrubMethod,
    ScrubSrc,
    SrcFlag,
    TABLE_KWARGS,
    TridType,
)
from crate_anon.anonymise.ddr import DataDictionaryRow
from crate_anon.anonymise.scrub import PersonalizedScrubber
from crate_anon.common.spreadsheet import (
    gen_rows_from_spreadsheet,
    SINGLE_SPREADSHEET_TYPE,
    write_spreadsheet,
)

if TYPE_CHECKING:
    from crate_anon.anonymise.config import Config

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

STRING_LENGTH_FOR_BIGINT = len(str(-2 ** 63))
# = -2^63: https://dev.mysql.com/doc/refman/8.0/en/integer-types.html


# =============================================================================
# Helper classes
# =============================================================================

@dataclass
class ScrubSourceFieldInfo:
    is_mpid: bool
    is_patient: bool
    recurse: bool
    required_scrubber: bool
    scrub_method: ScrubMethod
    signature: str
    value_fieldname: str


@dataclass
class DDTableSummary:
    # Which table?
    src_db: str
    src_table: str

    # Source information
    src_has_pk: bool
    src_pk_fieldname: str
    src_constant: bool
    src_addition_only: bool
    src_defines_pid: bool
    src_has_pid: bool
    src_has_mpid: bool
    src_has_opt_out: bool
    src_has_patient_scrub_info: bool
    src_has_third_party_scrub_info: bool
    src_has_required_scrub_info: bool

    # Destination information
    dest_table: str
    dest_has_rows: bool
    dest_add_src_hash: bool
    dest_being_scrubbed: bool


# =============================================================================
# Helper functions
# =============================================================================

def ensure_no_source_type_mismatch(ddr: DataDictionaryRow,
                                   config_sqlatype: Union[TypeEngine, String],
                                   primary_pid: bool = True) -> None:
    """
    Ensure that the source column type of a data dictionary row is compatible
    with what's expected from the config. We check this only for specific type
    of column (PID, MPID), because we need to know their data types concretely
    for the secret mapping table. The question is not whether the types are the
    same, but whether the value will fit into the config-determined type (for
    example, it's OK to convert an integer to a long-enough string but
    necessarily not the other way round).

    Args:
        ddr:
            Data dictionary row.
        config_sqlatype:
            SQLAlchemy column type that would be expected based on the current
            config.
        primary_pid:
            Is this the main PID field? If false, it's the MPID.
    """
    if primary_pid:
        human_type = "primary PID"
        configparam = AnonymiseConfigKeys.SQLATYPE_PID
    else:
        human_type = "master PID"
        configparam = AnonymiseConfigKeys.SQLATYPE_MPID
    rowtype = ddr.src_sqla_coltype
    suffix = ""
    if is_sqlatype_integer(rowtype):
        # ---------------------------------------------------------------------
        # Integer source
        # ---------------------------------------------------------------------
        if is_sqlatype_integer(config_sqlatype):
            # Good enough. The only integer type we use for PID/MPID is
            # BigInteger, so any integer type should fit.
            return
        elif is_sqlatype_string(config_sqlatype):
            # Storing an integer in a string. This may be OK, if the string is
            # long enough. We could do detailed checks here based on the type
            # of integer, but we'll be simple.
            if STRING_LENGTH_FOR_BIGINT <= config_sqlatype.length:
                # It'll fit!
                return
            else:
                suffix = (
                    f"Using a bigger string field in the config (minimum "
                    f"length {STRING_LENGTH_FOR_BIGINT}) would fix this."
                )
    elif is_sqlatype_string(rowtype):
        # ---------------------------------------------------------------------
        # String source
        # ---------------------------------------------------------------------
        # Strings are fine if we will store them in a long-enough string.
        if is_sqlatype_string(config_sqlatype):
            # noinspection PyUnresolvedReferences
            if rowtype.length <= config_sqlatype.length:
                return
            else:
                suffix = (
                    f"Using a bigger string field in the config (minimum "
                    f"length {rowtype.length}) would fix this."
                )
    # Generic error:
    raise ValueError(
        f"Source column {ddr.src_signature} is marked as a "
        f"{human_type} field but its type is {rowtype}, "
        f"while the config thinks it should be {config_sqlatype} "
        f"(determined by the {configparam!r} parameter). {suffix}")


# =============================================================================
# DataDictionary
# =============================================================================

class DataDictionary(object):
    """
    Class representing an entire data dictionary.
    """

    def __init__(self, config: "Config") -> None:
        """
        Set defaults.

        Args:
            config: :class:`crate_anon.anonymise.config.Config`
        """
        self.config = config
        self.rows = []  # type: List[DataDictionaryRow]
        # noinspection PyArgumentList
        self.cached_srcdb_table_pairs = SortedSet()

    # -------------------------------------------------------------------------
    # Information
    # -------------------------------------------------------------------------

    @property
    def n_rows(self) -> int:
        """
        Number of rows.
        """
        return len(self.rows)

    @property
    def dest_dialect(self) -> Dialect:
        """
        Returns the SQLAlchemy :class:`Dialect` (e.g. MySQL, SQL Server...) for
        the destination database.
        """
        return self.config.dest_dialect

    @property
    def dest_dialect_name(self) -> str:
        """
        Returns the SQLAlchemy dialect name for the destination database.
        """
        return self.config.dest_dialect_name

    # -------------------------------------------------------------------------
    # Loading
    # -------------------------------------------------------------------------

    def read_from_file(self,
                       filename: str,
                       check_valid: bool = True,
                       override_dialect: Dialect = None) -> None:
        """
        Read DD from file.

        Args:
            filename:
                Filename to read.
            check_valid:
                Run a validity check after setting each row from its values?
            override_dialect:
                SQLAlchemy SQL dialect to enforce (e.g. for interpreting
                textual column types in the source database). By default, the
                source database's own dialect is used.
        """
        log.debug(f"Loading data dictionary: {filename}")
        row_gen = gen_rows_from_spreadsheet(filename)
        self._read_from_rows(row_gen,
                             check_valid=check_valid,
                             override_dialect=override_dialect)

    def _read_from_rows(self,
                        rows: SINGLE_SPREADSHEET_TYPE,
                        check_valid: bool = True,
                        override_dialect: Dialect = None) -> None:
        """
        Internal function to read from a set of rows, whatever the underlying
        format.

        Args:
            rows:
                Iterable of rows (one per data dictionary row), each row being
                a list of values.
            check_valid:
                Run a validity check after setting the values?
            override_dialect:
                SQLAlchemy SQL dialect to enforce (e.g. for interpreting
                textual column types in the source database). By default, the
                source database's own dialect is used.
        """
        # Clear existing data
        self.rows = []  # type: List[DataDictionaryRow]

        # Headers
        # noinspection PyTypeChecker
        headers = next(rows)
        if not all(x in headers for x in DataDictionaryRow.ROWNAMES):
            actual = "\n".join(
                f"{i}. {h}"
                for i, h in enumerate(headers, start=1)
            )
            desired = "\n".join(
                f"{i}. {h}"
                for i, h in enumerate(DataDictionaryRow.ROWNAMES, start=1)
            )
            raise ValueError(
                f"Bad data dictionary file. Data dictionaries must be in "
                f"tabular format and contain the following headings:\n\n"
                f"{desired}\n\n"
                f"but yours are:\n\n"
                f"{actual}"
            )
        log.debug("Data dictionary has correct header. Loading content...")

        # Data
        for values in rows:
            if len(values) < len(headers):
                valuedict = dict(zip_longest(headers, values, fillvalue=""))
            else:
                valuedict = dict(zip(headers, values))
            ddr = DataDictionaryRow(self.config)
            try:
                ddr.set_from_dict(valuedict, override_dialect=override_dialect)
                if check_valid:
                    ddr.check_valid()
            except ValueError:
                log.critical(f"Offending input: {valuedict}")
                raise
            self.rows.append(ddr)
        log.debug("... content loaded.")

        # Clear caches
        self.clear_caches()

    @classmethod
    def create_from_file(cls,
                         filename: str,
                         config: "Config",
                         check_valid: bool = True,
                         override_dialect: Dialect = None) -> "DataDictionary":
        """
        Creates a new data dictionary by reading a file.
        """
        dd = DataDictionary(config)
        dd.read_from_file(filename,
                          check_valid=check_valid,
                          override_dialect=override_dialect)
        return dd

    def draft_from_source_databases(self, report_every: int = 100) -> None:
        """
        Create a draft DD from a source database.

        Will skip any rows it knows about already (thus allowing the generation
        of incremental changes).

        Args:
            report_every: report to the Python log every *n* columns
        """
        log.info("Reading information for draft data dictionary")

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Scan databases
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        existing_signatures = set(ddr.src_signature for ddr in self.rows)
        for pretty_dbname, db in self.config.sources.items():
            log.info(f"... database nice name = {pretty_dbname}")
            cfg = db.srccfg
            meta = db.metadata
            i = 0
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            # Scan each table
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            for t in meta.sorted_tables:
                tablename = t.name
                log.info(f"... ... table: {tablename}")

                # Skip table?
                if cfg.is_table_denied(tablename):
                    log.debug(f"Skipping denied table: {tablename}")
                    continue
                all_col_names = [c.name for c in t.columns]
                if cfg.does_table_fail_minimum_fields(all_col_names):
                    log.debug(f"Skipping table {t} because it fails "
                              f"minimum field requirements")
                    continue

                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # Scan each column
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                for c in t.columns:
                    i += 1
                    if report_every and i % report_every == 0:
                        log.debug(f"... reading source field number {i}")
                    # Name
                    columnname = c.name
                    # Do not manipulate the case of SOURCE tables/columns.
                    # If you do, they can fail to match the SQLAlchemy
                    # introspection and cause a crash.

                    # Skip column?
                    if cfg.is_field_denied(columnname):
                        log.debug(f"Skipping denied column: "
                                  f"{tablename}.{columnname}")
                        continue
                    # Other attributes
                    try:
                        datatype_sqltext = str(c.type)
                    except sqlalchemy.exc.CompileError:
                        log.critical(f"Column that failed was: {c!r}")
                        raise
                    sqla_coltype = c.type
                    nullable = c.nullable
                    primary_key = c.primary_key
                    comment = getattr(c, "comment", "")
                    # ... not all dialects support reflecting comments;
                    # https://docs.sqlalchemy.org/en/14/core/reflection.html
                    if cfg.ddgen_append_source_info_to_comment:
                        comment = f"[from {tablename}.{columnname}]"
                    # Create row
                    ddr = DataDictionaryRow(self.config)
                    ddr.set_from_src_db_info(
                        pretty_dbname, tablename, columnname,
                        datatype_sqltext,
                        sqla_coltype,
                        dbconf=cfg,
                        comment=comment,
                        nullable=nullable,
                        primary_key=primary_key,
                    )

                    # ---------------------------------------------------------
                    # If we have this one already, skip ASAP
                    # This is how incremental data dictionaries get generated.
                    # ---------------------------------------------------------
                    sig = ddr.src_signature
                    if sig in existing_signatures:
                        log.debug(f"Skipping duplicated column: "
                                  f"{tablename}.{columnname}")
                        continue
                    existing_signatures.add(sig)

                    self.rows.append(ddr)

        log.info("... done")
        self.clear_caches()
        self.sort()

    def tidy_draft(self) -> None:
        """
        Corrects a draft data dictionary for overall logical consistency.

        The checks are:

        - Don't scrub in non-patient tables.
        - SQL Server only supports one FULLTEXT index per table, and only if
          the table has a non-null column with a unique index.

        Test code for full-text index creation:

        .. code-block:: sql

            -- SQL Server
            USE mydb;
            CREATE FULLTEXT CATALOG default_fulltext_catalog AS DEFAULT;
            CREATE TABLE junk (intthing INT PRIMARY KEY, textthing VARCHAR(MAX));
            -- now find the name of the PK index (! -- by hand or see cardinal_pythonlib)
            CREATE FULLTEXT INDEX ON junk (textthing) KEY INDEX <pk_index_name>;

            -- MySQL:
            USE mydb;
            CREATE TABLE junk (intthing INT PRIMARY KEY, text1 LONGTEXT, text2 LONGTEXT);
            ALTER TABLE junk ADD FULLTEXT INDEX ftidx1 (text1);
            ALTER TABLE junk ADD FULLTEXT INDEX ftidx2 (text2);  -- OK
        """   # noqa
        log.info("Tidying/correcting draft data dictionary")

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        log.debug("... Don't scrub in non-patient tables")
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        for d, t in self.get_src_db_tablepairs_w_no_pt_info():
            for ddr in self.get_rows_for_src_table(d, t):
                ddr.remove_scrub_from_alter_methods()

        log.debug("... Make full-text indexes follow dialect rules")

        # https://docs.microsoft.com/en-us/sql/t-sql/statements/create-fulltext-index-transact-sql?view=sql-server-ver15  # noqa
        if self.dest_dialect_name == SqlaDialectName.SQLSERVER:
            for d, t in self.get_src_db_tablepairs():
                rows = self.get_rows_for_src_table(d, t)

                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # SQL Server: every table with a FULLTEXT index must have a
                # column that is non-nullable with a unique index.
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                sqlserver_ok_for_fulltext = False
                for ddr in rows:
                    if (ddr.include
                            and not ddr.src_reflected_nullable
                            and ddr.index == IndexType.UNIQUE):
                        sqlserver_ok_for_fulltext = True
                if not sqlserver_ok_for_fulltext:
                    for ddr in rows:
                        if ddr.include and ddr.index == IndexType.FULLTEXT:
                            log.warning(
                                f"To create a FULLTEXT index, SQL Server "
                                f"requires a non-nullable column with a "
                                f"unique index. Can't find one for "
                                f"destination table {ddr.dest_table!r}. "
                                f"Removing index from column "
                                f"{ddr.dest_field!r}."
                            )
                            ddr.index = IndexType.NONE

                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # SQL server: only one FULLTEXT index per table. (Although in
                # principle you can have one FULLTEXT index that covers
                # multiple columns; we don't support that.)
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                n_fulltext = 0
                for ddr in rows:
                    if ddr.include and ddr.index == IndexType.FULLTEXT:
                        if n_fulltext >= 1:
                            log.warning(
                                f"SQL Server permits only one FULLTEXT index "
                                f"per table (and CRATE does not support "
                                f"multi-column full-text indexes). Since "
                                f"there is already one, removing the "
                                f"full-text index from "
                                f"{ddr.dest_table}.{ddr.dest_field}."
                            )
                            ddr.index = IndexType.NONE
                        else:
                            n_fulltext += 1

        # MySQL: fine to have multiple FULLTEXT indexes in one table.
        # See text code above.

        log.info("... done")
        self.clear_caches()

    def make_dest_datatypes_explicit(self) -> None:
        """
        By default, when autocreating a data dictionary, the ``dest_datatype``
        field is not populated explicit, just implicitly. This option makes
        them explicit by instantiating those values. Primarily for debugging.
        """
        for ddr in self.rows:
            ddr.make_dest_datatype_explicit()

    # -------------------------------------------------------------------------
    # Sorting
    # -------------------------------------------------------------------------

    def sort(self) -> None:
        """
        Sorts the data dictionary.
        """
        log.info("Sorting data dictionary")
        self.rows = sorted(
            self.rows,
            key=operator.attrgetter("src_db_lowercase",
                                    "src_table_lowercase",
                                    "src_field_lowercase"))
        log.info("... done")

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def check_against_source_db(self) -> None:
        """
        Check DD validity against the source database(s).

        Also caches SQLAlchemy source column types.
        """
        for d in self.get_source_databases():
            db = self.config.sources[d]

            for t in self.get_src_tables(d):

                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # Ensure each source table maps to only one destination table
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                dt = self.get_dest_tables_for_src_db_table(d, t)
                if len(dt) > 1:
                    raise ValueError(
                        f"Source table {d}.{t} maps to >1 destination "
                        f"table: {', '.join(dt)}")

                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # Ensure source table is in database
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                if t not in db.table_names:
                    log.debug(
                        f"Source database {d!r} has tables: {db.table_names}")
                    raise ValueError(
                        f"Table {t!r} missing from source database {d!r}")

                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # Row checks: preamble
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                rows = self.get_rows_for_src_table(d, t)
                # We may need to cross-reference rows, so all rows need to know
                # their type.
                for r in rows:
                    if r.src_field not in db.metadata.tables[t].columns:
                        raise ValueError(
                            f"Column {r.src_field!r} missing from table {t!r} "
                            f"in source database {d!r}")
                    sqla_coltype = (
                        db.metadata.tables[t].columns[r.src_field].type
                    )
                    r.set_src_sqla_coltype(sqla_coltype)  # CACHES TYPE HERE

                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # If PID field is required, is it present?
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                needs_pidfield = any(r.being_scrubbed for r in rows)
                # Before 2021-12-07, we used to check r.master_pid, too.
                # However, if nothing is being scrubbed, then the lack of a
                # link via primary PID is a researcher inconvenience, not an
                # de-identification risk.
                if needs_pidfield and not self.get_pid_name(d, t):
                    raise ValueError(
                        f"Source table {d}.{t} has a "
                        f"{AlterMethodType.SCRUBIN.value!r} "
                        f"field but no primary patient ID field"
                    )

                n_pks = 0
                for r in rows:
                    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                    # Data types for special rows
                    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                    if r.primary_pid:
                        ensure_no_source_type_mismatch(r, self.config.pidtype,
                                                       primary_pid=True)
                    if r.master_pid:
                        ensure_no_source_type_mismatch(r, self.config.mpidtype,
                                                       primary_pid=False)

                    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                    # Too many PKs?
                    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                    if r.pk:
                        n_pks += 1
                        if n_pks > 1:
                            raise ValueError(
                                f"Table {d}.{t} has >1 source PK set")

                    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                    # Duff alter method?
                    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                    for am in r.alter_methods:
                        if am.extract_from_blob:
                            extrow = next(
                                (r2 for r2 in rows
                                    if r2.src_field == am.extract_ext_field),
                                None
                            )
                            if extrow is None:
                                raise ValueError(
                                    f"alter_method = {r.alter_method}, "
                                    f"but field {am.extract_ext_field} "
                                    f"not found in the same table")
                            if not is_sqlatype_text_over_one_char(
                                    extrow.src_sqla_coltype):
                                raise ValueError(
                                    f"alter_method = {r.alter_method}, but "
                                    f"field {am.extract_ext_field}, which "
                                    f"should contain an extension or "
                                    f"filename, is not text of >1 character")

    def check_valid(self,
                    prohibited_fieldnames: List[str] = None,
                    check_against_source_db: bool = True) -> None:
        """
        Check DD validity, internally ± against the source database(s).

        Args:
            prohibited_fieldnames:
                list of prohibited destination fieldnames
            check_against_source_db:
                check validity against the source database(s)?

        Raises:
            :exc:`ValueError` if the DD is invalid
        """
        if prohibited_fieldnames is None:
            prohibited_fieldnames = []  # type: List[str]
        log.info("Checking data dictionary...")
        if not self.rows:
            raise ValueError("Empty data dictionary")
        if not self.get_dest_tables():
            raise ValueError("Empty data dictionary after removing "
                             "redundant tables")

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Check (or re-check) individual rows
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        log.debug("Checking DD: individual row validity...")
        for r in self.rows:
            r.check_valid()

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Check collective consistency
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        log.debug("Checking DD: prohibited flags...")
        for d in self.get_source_databases():
            for t in self.get_src_tables(d):
                # This will have excluded all tables where all rows are
                # omitted. So now we have only active tables, for which we
                # cannot combine certain flags.
                # (We used to prohibit these combinations at all times, in the
                # DataDictionaryRow class, but it's inconvenient to have to
                # alter these flags if you want to omit the whole table.)
                for r in self.get_rows_for_src_table(d, t):
                    if r.add_src_hash and r.omit:
                        raise ValueError(
                            f"Do not set {Decision.OMIT.value} on "
                            f"{DataDictionaryRow.SRC_FLAGS}="
                            f"{SrcFlag.ADD_SRC_HASH} fields -- "
                            f"currently set for {r.src_signature}")
                    if r.constant and r.omit:
                        raise ValueError(
                            f"Do not set {Decision.OMIT.value} on "
                            f"{DataDictionaryRow.SRC_FLAGS}="
                            f"{SrcFlag.CONSTANT} fields -- "
                            f"currently set for {r.src_signature}")

        log.debug("Checking DD: table consistency...")
        for d, t in self.get_scrub_from_db_table_pairs():
            pid_field = self.get_pid_name(d, t)
            if not pid_field:
                raise ValueError(
                    f"Scrub-source table {d}.{t} must have a patient ID field "
                    f"(one with flag {SrcFlag.PRIMARY_PID})"
                )

        log.debug("Checking DD: prohibited fieldnames...")
        if prohibited_fieldnames:
            for r in self.rows:
                r.check_prohibited_fieldnames(prohibited_fieldnames)

        log.debug("Checking DD: opt-out fields...")
        for t in self.get_optout_defining_fields():
            (src_db, src_table, optout_colname, pid_colname, mpid_colname) = t
            if not pid_colname and not mpid_colname:
                raise ValueError(
                    f"Field {src_db}.{src_table}.{optout_colname} has "
                    f"{DataDictionaryRow.SRC_FLAGS}={SrcFlag.OPT_OUT} set, "
                    f"but that table does not have a primary patient ID field "
                    f"or a master patient ID field")

        log.debug("Checking DD: destination tables...")
        for t in self.get_dest_tables():
            sdt = self.get_src_dbs_tables_for_dest_table(t)
            if len(sdt) > 1:
                raise ValueError(
                    "Destination table {t} is mapped to by multiple source "
                    "databases: {s}".format(
                        t=t,
                        s=", ".join(["{}.{}".format(s[0], s[1]) for s in sdt]),
                    ))

        log.debug("Checking DD: duplicate source rows?")
        src_sigs = [r.src_signature for r in self.rows]
        src_duplicates = [
            item for item, count in Counter(src_sigs).items()
            if count > 1
        ]
        if src_duplicates:
            raise ValueError(f"Duplicate source rows: {src_duplicates}")

        log.debug("Checking DD: duplicate destination rows?")
        dst_sigs = [r.dest_signature for r in self.rows if not r.omit]
        dst_duplicates = [
            item for item, count in Counter(dst_sigs).items()
            if count > 1
        ]
        if dst_duplicates:
            raise ValueError(f"Duplicate destination rows: {dst_duplicates}")

        if check_against_source_db:
            log.debug("Checking DD against source database tables...")
            self.check_against_source_db()

        log.debug("Checking DD: global patient-defining fields...")
        n_definers = self.n_definers
        if n_definers == 0:
            if self.config.allow_no_patient_info:
                log.warning("NO PATIENT-DEFINING FIELD! DATABASE(S) WILL "
                            "BE COPIED, NOT ANONYMISED.")
            else:
                raise ValueError(
                    f"No patient-defining field! (And "
                    f"{AnonymiseConfigKeys.ALLOW_NO_PATIENT_INFO} not set.)"
                )
        elif n_definers > 1:
            log.warning(
                f"Unusual: >1 field with "
                f"{DataDictionaryRow.SRC_FLAGS}="
                f"{SrcFlag.DEFINES_PRIMARY_PIDS} set.")

        log.debug("... DD checked.")

    # -------------------------------------------------------------------------
    # Saving
    # -------------------------------------------------------------------------

    def write(self, filename: str, filetype: str = None) -> None:
        """
        Writes the dictionary, either specifying the filetype or autodetecting
        it from the specified filename.

        Args:
            filename:
                Name of file to write, or "-" for stdout (in which case the
                filetype is forced to TSV).
            filetype:
                File type as one of ``.ods``, ``.tsv``, or ``.xlsx``;
                alternatively, use ``None`` to autodetect from the filename.
        """
        log.info("Saving data dictionary...")
        data = self._as_dict()
        write_spreadsheet(filename, data, filetype=filetype)

    def _as_dict(self) -> Dict[str, Any]:
        """
        Returns an ordered dictionary representation used for writing
        spreadsheets.
        """
        sheetname = "data_dictionary"
        rows = [
            DataDictionaryRow.header_row()
        ] + [
            ddr.as_row() for ddr in self.rows
        ]
        data = OrderedDict()
        data[sheetname] = rows
        return data

    # -------------------------------------------------------------------------
    # Global DD queries
    # -------------------------------------------------------------------------

    @property
    def n_definers(self) -> int:
        """
        The number of patient-defining columns.
        """
        return sum([1 if x.defines_primary_pids else 0
                    for x in self.rows])

    @lru_cache(maxsize=None)
    def get_source_databases(self) -> AbstractSet[str]:
        """
        Return a SortedSet of source database names.
        """
        return SortedSet([
             ddr.src_db
             for ddr in self.rows
             if ddr.required
         ])

    @lru_cache(maxsize=None)
    def get_scrub_from_db_table_pairs(self) -> AbstractSet[Tuple[str, str]]:
        """
        Return a SortedSet of ``source_database_name, source_table`` tuples
        where those fields contain ``scrub_src`` (scrub-from) information.
        """
        return SortedSet([
            (ddr.src_db, ddr.src_table)
            for ddr in self.rows
            if ddr.scrub_src
        ])
        # even if omit flag set

    @lru_cache(maxsize=None)
    def get_src_db_tablepairs(self) -> AbstractSet[Tuple[str, str]]:
        """
        Return a SortedSet of all ``source_database_name, source_table``
        tuples.
        """
        return SortedSet([
            (ddr.src_db, ddr.src_table)
            for ddr in self.rows
        ])

    @lru_cache(maxsize=None)
    def get_src_db_tablepairs_w_pt_info(self) -> AbstractSet[Tuple[str, str]]:
        """
        Return a SortedSet of ``source_database_name, source_table`` tuples
        for tables that contain patient information.
        """
        return SortedSet([
            (ddr.src_db, ddr.src_table)
            for ddr in self.rows
            if ddr.contains_patient_info
        ])

    def get_src_db_tablepairs_w_no_pt_info(self) \
            -> AbstractSet[Tuple[str, str]]:
        """
        Return a SortedSet of ``source_database_name, source_table`` tuples
        for tables that contain no patient information.
        """
        return SortedSet([
            (ddr.src_db, ddr.src_table)
            for ddr in self.rows
            if not ddr.contains_patient_info
        ])

    def get_tables_w_no_pt_info(self) -> AbstractSet[str]:
        """
        Return a SortedSet of ``source_table`` names for tables that contain no
        patient information.
        """
        tables_with_pt_info = SortedSet([
            ddr.src_table
            for ddr in self.rows
            if ddr.contains_patient_info
        ])
        all_tables = SortedSet([ddr.src_table for ddr in self.rows])
        return all_tables - tables_with_pt_info

    def get_tables_w_scrub_src(self) -> AbstractSet[str]:
        """
        Return a SortedSet of ``source_table`` names for tables that contain
        ``scrub_src`` information, i.e. that contribute to anonymisation.
        """
        return SortedSet([
            ddr.src_table
            for ddr in self.rows
            if ddr.contains_scrub_src
        ])

    @lru_cache(maxsize=None)
    def get_src_db_tablepairs_w_int_pk(self) -> AbstractSet[Tuple[str, str]]:
        """
        Return a SortedSet of ``source_database_name, source_table`` tuples
        for tables that have an integer PK.
        """
        return SortedSet([
            (ddr.src_db, ddr.src_table)
            for ddr in self.rows
            if self.get_int_pk_ddr(ddr.src_db, ddr.src_table) is not None
        ])

    @lru_cache(maxsize=None)
    def get_src_dbs_tables_with_no_pt_info_no_pk(self) \
            -> AbstractSet[Tuple[str, str]]:
        """
        Return a SortedSet of ``source_database_name, source_table`` tuples
        where the table has no patient information and no integer PK.
        """
        return (
            self.get_src_db_tablepairs() -
            self.get_src_db_tablepairs_w_pt_info() -
            self.get_src_db_tablepairs_w_int_pk()
        )

    @lru_cache(maxsize=None)
    def get_src_dbs_tables_with_no_pt_info_int_pk(self) \
            -> AbstractSet[Tuple[str, str]]:
        """
        Return a SortedSet of ``source_database_name, source_table`` tuples
        where the table has no patient information and has an integer PK.
        """
        return (
            (self.get_src_db_tablepairs() -
                self.get_src_db_tablepairs_w_pt_info()) &  # & is intersection
            self.get_src_db_tablepairs_w_int_pk()
        )

    @lru_cache(maxsize=None)
    def get_dest_tables(self) -> AbstractSet[str]:
        """
        Return a SortedSet of all destination table names.
        """
        return SortedSet([
            ddr.dest_table
            for ddr in self.rows
            if not ddr.omit
        ])

    @lru_cache(maxsize=None)
    def get_dest_tables_with_patient_info(self) -> AbstractSet[str]:
        """
        Return a SortedSet of destination table names that have patient
        information.
        """
        return SortedSet([
            ddr.dest_table
            for ddr in self.rows
            if ddr.contains_patient_info and not ddr.omit
        ])

    @lru_cache(maxsize=None)
    def get_optout_defining_fields(self) \
            -> AbstractSet[Tuple[str, str, str, str, str]]:
        """
        Return a SortedSet of ``src_db, src_table, src_field, pidfield,
        mpidfield`` tuples for rows that define opt-out information.
        """
        return SortedSet([
            (ddr.src_db, ddr.src_table, ddr.src_field,
                self.get_pid_name(ddr.src_db, ddr.src_table),
                self.get_mpid_name(ddr.src_db, ddr.src_table))
            for ddr in self.rows
            if ddr.opt_out_info
        ])

    @lru_cache(maxsize=None)
    def get_mandatory_scrubber_sigs(self) -> AbstractSet[str]:
        """
        Return a set of field signatures (strings of the format
        ``db.table.column``) for all rows representing "required scrubber"
        fields -- that is, rows that must have at least one non-NULL value for
        each patient, or the patient won't get processed.
        """
        return set([ddr.src_signature for ddr in self.rows
                    if ddr.required_scrubber])

    def get_summary_info_for_table(self,
                                   src_db: str,
                                   src_table: str) -> DDTableSummary:
        """
        Returns summary information for a specific table.
        """
        rows = self.get_rows_for_src_table(src_db, src_table)

        # Source
        src_has_pk = False
        src_pk_fieldname = None  # type: Optional[str]
        src_constant = False
        src_addition_only = False
        src_defines_pid = False
        src_has_pid = False
        src_has_mpid = False
        src_has_opt_out = False
        src_has_patient_scrub_info = False
        src_has_third_party_scrub_info = False
        src_has_required_scrub_info = False
        # Destination
        dest_table = None  # type: Optional[str]
        dest_has_rows = False
        dest_add_src_hash = False
        dest_being_scrubbed = False

        for ddr in rows:
            # Source
            src_has_pk = src_has_pk or ddr.pk
            if ddr.pk:
                src_pk_fieldname = ddr.src_field
            src_constant = src_constant or ddr.constant
            src_addition_only = src_addition_only or ddr.addition_only
            src_defines_pid = src_defines_pid or ddr.defines_primary_pids
            src_has_pid = src_has_pid or ddr.primary_pid
            src_has_mpid = src_has_mpid or ddr.master_pid
            src_has_opt_out = src_has_opt_out or ddr.opt_out_info
            src_has_patient_scrub_info = (
                src_has_patient_scrub_info
                or ddr.contains_patient_scrub_src_info
            )
            src_has_third_party_scrub_info = (
                src_has_third_party_scrub_info
                or ddr.contains_third_party_info
            )
            src_has_required_scrub_info = (
                src_has_required_scrub_info
                or ddr.required_scrubber
            )
            # Destination
            dest_table = dest_table or ddr.dest_table
            dest_has_rows = dest_has_rows or not ddr.omit
            dest_add_src_hash = dest_add_src_hash or ddr.add_src_hash
            dest_being_scrubbed = dest_being_scrubbed or ddr.being_scrubbed

        return DDTableSummary(
            # Which table?
            src_db=src_db,
            src_table=src_table,
            # Source info
            src_has_pk=src_has_pk,
            src_pk_fieldname=src_pk_fieldname,
            src_constant=src_constant,
            src_addition_only=src_addition_only,
            src_defines_pid=src_defines_pid,
            src_has_pid=src_has_pid,
            src_has_mpid=src_has_mpid,
            src_has_opt_out=src_has_opt_out,
            src_has_patient_scrub_info=src_has_patient_scrub_info,
            src_has_third_party_scrub_info=src_has_third_party_scrub_info,
            src_has_required_scrub_info=src_has_required_scrub_info,
            # Destination info
            dest_table=dest_table,
            dest_has_rows=dest_has_rows,
            dest_add_src_hash=dest_add_src_hash,
            dest_being_scrubbed=dest_being_scrubbed,
        )

    def get_summary_info_all_tables(self) -> List[DDTableSummary]:
        """
        Returns summary information by table.
        """
        infolist = []  # type: List[DDTableSummary]
        for src_db, src_table in self.get_src_db_tablepairs():
            infolist.append(self.get_summary_info_for_table(src_db, src_table))
        return infolist

    # -------------------------------------------------------------------------
    # Queries by source DB
    # -------------------------------------------------------------------------

    @lru_cache(maxsize=None)
    def get_src_tables(self, src_db: str) -> AbstractSet[str]:
        """
        For a given source database name, return a SortedSet of all source
        tables that are required (that is, ones being copied and ones providing
        vital patient information).
        """
        return SortedSet([
            ddr.src_table
            for ddr in self.rows
            if ddr.src_db == src_db and ddr.required
        ])

    @lru_cache(maxsize=None)
    def get_src_tables_with_active_dest(self, src_db: str) -> AbstractSet[str]:
        """
        For a given source database name, return a SortedSet of its source
        tables that have an active destination.
        """
        return SortedSet([
            ddr.src_table
            for ddr in self.rows
            if ddr.src_db == src_db and not ddr.omit
        ])

    @lru_cache(maxsize=None)
    def get_src_tables_with_patient_info(self, src_db: str) -> AbstractSet[str]:
        """
        For a given source database name, return a SortedSet of source tables
        that have patient information.
        """
        return SortedSet([
            ddr.src_table
            for ddr in self.rows
            if ddr.src_db == src_db and ddr.contains_patient_info
        ])

    @lru_cache(maxsize=None)
    def get_patient_src_tables_with_active_dest(self, src_db: str) \
            -> AbstractSet[str]:
        """
        For a given source database name, return a SortedSet of source tables
        that contain patient information and have an active destination table.
        """
        return (
            self.get_src_tables_with_active_dest(src_db) &
            self.get_src_tables_with_patient_info(src_db)
        )

    # -------------------------------------------------------------------------
    # Queries by source DB/table
    # -------------------------------------------------------------------------

    @lru_cache(maxsize=None)
    def get_dest_tables_for_src_db_table(
            self, src_db: str, src_table: str) -> AbstractSet[str]:
        """
        For a given source database/table, return a SortedSet of destination
        tables.
        """
        return SortedSet([
            ddr.dest_table
            for ddr in self.rows
            if (ddr.src_db == src_db and
                ddr.src_table == src_table and
                not ddr.omit)
        ])

    @lru_cache(maxsize=None)
    def get_dest_table_for_src_db_table(
            self, src_db: str, src_table: str) -> str:
        """
        For a given source database/table, return the single or the first
        destination table.
        """
        return list(
            self.get_dest_tables_for_src_db_table(src_db, src_table))[0]

    @lru_cache(maxsize=None)
    def get_rows_for_src_table(self, src_db: str, src_table: str) \
            -> AbstractSet[DataDictionaryRow]:
        """
        For a given source database name/table, return a SortedSet of DD rows.
        """
        return SortedSet([
            ddr
            for ddr in self.rows
            if ddr.src_db == src_db and ddr.src_table == src_table
        ])

    @lru_cache(maxsize=None)
    def get_fieldnames_for_src_table(self, src_db: str, src_table: str) \
            -> AbstractSet[DataDictionaryRow]:
        """
        For a given source database name/table, return a SortedSet of source
        fields.
        """
        return SortedSet([
            ddr.src_field
            for ddr in self.rows
            if ddr.src_db == src_db and ddr.src_table == src_table
        ])

    @lru_cache(maxsize=None)
    def get_scrub_from_rows(self, src_db: str, src_table: str) \
            -> AbstractSet[DataDictionaryRow]:
        """
        Return a SortedSet of DD rows for all fields containing ``scrub_src``
        (scrub-from) information.
        """
        return SortedSet([
            ddr
            for ddr in self.rows
            if (ddr.scrub_src and
                ddr.src_db == src_db and
                ddr.src_table == src_table)
        ])
        # even if omit flag set

    def get_scrub_from_rows_as_fieldinfo(
            self,
            src_db: str,
            src_table: str,
            depth: int,
            max_depth: int) -> List[ScrubSourceFieldInfo]:
        """
        Using :meth:`get_scrub_from_rows`, as a list of
        :class:`ScrubSourceFieldInfo` objects, which is more convenient for
        scrubbing.

        Args:
            src_db:
                Source database name.
            src_table:
                Source table name.
            depth:
                Current recursion depth for looking up third-party information.
            max_depth:
                Maximum permitted recursion depth for looking up third-party
                information.
        """
        ddrows = self.get_scrub_from_rows(src_db, src_table)
        infolist = []  # type: List[ScrubSourceFieldInfo]
        for ddr in ddrows:
            info = ScrubSourceFieldInfo(
                is_mpid=(
                    depth == 0 and ddr.master_pid
                    # The check for "depth == 0" means that third-party
                    # information is never marked as patient-related.
                ),
                is_patient=(
                    depth == 0 and ddr.scrub_src is ScrubSrc.PATIENT
                ),
                recurse=(
                    depth < max_depth
                    and ddr.scrub_src is ScrubSrc.THIRDPARTY_XREF_PID
                ),
                required_scrubber=ddr.required_scrubber,
                scrub_method=PersonalizedScrubber.get_scrub_method(
                    ddr.src_datatype,
                    ddr.scrub_method
                ),
                signature=ddr.src_signature,
                value_fieldname=ddr.src_field,
            )
            infolist.append(info)
        return infolist

    @lru_cache(maxsize=None)
    def get_pk_ddr(self, src_db: str, src_table: str) \
            -> Optional[DataDictionaryRow]:
        """
        For a given source database name and table, return the DD row for the
        PK for that table, whether integer or not.

        Will return ``None`` if no such data dictionary row exists.
        """
        for ddr in self.rows:
            if (ddr.src_db == src_db and
                    ddr.src_table == src_table and
                    ddr.pk):
                return ddr
        return None

    @lru_cache(maxsize=None)
    def get_int_pk_ddr(self, src_db: str, src_table: str) \
            -> Optional[DataDictionaryRow]:
        """
        For a given source database name and table, return the DD row for the
        integer PK for that table.

        Will return ``None`` if no such data dictionary row exists.
        """
        for ddr in self.rows:
            if (ddr.src_db == src_db and
                    ddr.src_table == src_table and
                    ddr.pk and
                    is_sqltype_integer(ddr.src_datatype)):
                return ddr
        return None

    @lru_cache(maxsize=None)
    def get_int_pk_name(self, src_db: str, src_table: str) -> Optional[str]:
        """
        For a given source database name and table, return the field name of
        the integer PK for that table (or ``None`` if there isn't one).
        """
        ddr = self.get_int_pk_ddr(src_db, src_table)
        if ddr is None:
            return None
        return ddr.src_field

    @lru_cache(maxsize=None)
    def has_active_destination(self, src_db: str, src_table: str) -> bool:
        """
        For a given source database name and table, does it have an active
        destination?
        """
        for ddr in self.rows:
            if (ddr.src_db == src_db and
                    ddr.src_table == src_table and
                    not ddr.omit):
                return True
        return False

    @lru_cache(maxsize=None)
    def get_pid_name(self, src_db: str, src_table: str) -> Optional[str]:
        """
        For a given source database name and table: return the field name of
        the field providing primary PID information (or ``None`` if there isn't
        one).
        """
        for ddr in self.rows:
            if (ddr.src_db == src_db and
                    ddr.src_table == src_table and
                    ddr.primary_pid):
                return ddr.src_field
        return None

    @lru_cache(maxsize=None)
    def get_mpid_name(self, src_db: str, src_table: str) -> Optional[str]:
        """
        For a given source database name and table: return the field name of
        the field providing master PID (MPID) information (or ``None`` if there
        isn't one).
        """
        for ddr in self.rows:
            if (ddr.src_db == src_db and
                    ddr.src_table == src_table and
                    ddr.master_pid):
                return ddr.src_field
        return None

    # -------------------------------------------------------------------------
    # Queries by destination table
    # -------------------------------------------------------------------------

    @lru_cache(maxsize=None)
    def get_src_dbs_tables_for_dest_table(
            self, dest_table: str) -> AbstractSet[Tuple[str, str]]:
        """
        For a given destination table, return a SortedSet of ``dbname, table``
        tuples.
        """
        return SortedSet([
            (ddr.src_db, ddr.src_table)
            for ddr in self.rows
            if ddr.dest_table == dest_table
        ])

    @lru_cache(maxsize=None)
    def get_rows_for_dest_table(
            self, dest_table: str) -> AbstractSet[DataDictionaryRow]:
        """
        For a given destination table, return a SortedSet of DD rows.
        """
        return SortedSet([
            ddr
            for ddr in self.rows
            if ddr.dest_table == dest_table and not ddr.omit
        ])

    # -------------------------------------------------------------------------
    # SQLAlchemy Table objects
    # -------------------------------------------------------------------------

    @lru_cache(maxsize=None)
    def get_dest_sqla_table(self, tablename: str) -> Table:
        """
        For a given destination table name, return an
        :class:`sqlalchemy.sql.schema.Table` object for the destination table
        (which we will create).
        """
        config = self.config
        metadata = config.destdb.metadata
        timefield = config.timefield
        add_mrid_wherever_rid_added = config.add_mrid_wherever_rid_added
        pid_found = False
        rows_include_mrid_with_expected_name = False
        columns = []  # type: List[Column]
        for ddr in self.get_rows_for_dest_table(tablename):
            columns.append(ddr.dest_sqla_column)
            if ddr.add_src_hash:
                columns.append(self._get_srchash_sqla_column())
            if ddr.primary_pid:
                columns.append(self._get_trid_sqla_column())
                pid_found = True
            if (ddr.master_pid and
                    ddr.dest_field == config.master_research_id_fieldname):
                # This table has an explicit MRID field with the expected name;
                # we make a note, because if we're being asked to add MRIDs
                # automatically along with RIDs, we need not to do it twice.
                rows_include_mrid_with_expected_name = True
        if (pid_found
                and add_mrid_wherever_rid_added
                and not rows_include_mrid_with_expected_name):
            columns.append(self._get_mrid_sqla_column())
        if timefield:
            timecol = Column(timefield, DateTime)
            columns.append(timecol)
        return Table(tablename, metadata, *columns, **TABLE_KWARGS)

    def _get_srchash_sqla_column(self) -> Column:
        """
        Returns a :class:`sqlalchemy.sql.schema.Column` object for the
        "source hash" column (which is inserted into many destination tables
        so they can record the hash of their source, for change detection).
        """
        return Column(
            self.config.source_hash_fieldname,
            self.config.sqltype_encrypted_pid,
            comment='Hashed amalgamation of all source fields'
        )

    def _get_trid_sqla_column(self) -> Column:
        """
        Returns a :class:`sqlalchemy.sql.schema.Column` object for the "TRID"
        column. This is inserted into all patient-related destination tables as
        a high-speed (integer) but impermanent research ID -- a transient
        research ID (TRID).
        """
        return Column(
            self.config.trid_fieldname,
            TridType,
            nullable=False,
            comment='Transient integer research ID (TRID)'
        )

    def _get_mrid_sqla_column(self) -> Column:
        """
        Returns a :class:`sqlalchemy.sql.schema.Column` object for the "MRID"
        column. This is inserted into all patient-related destination tables
        where the flag 'add_mrid_wherever_rid_added' is set.
        """
        return Column(
            self.config.master_research_id_fieldname,
            self.config.sqltype_encrypted_pid,
            nullable=True,
            comment='Master research ID (MRID)'
        )

    # -------------------------------------------------------------------------
    # Clear caches
    # -------------------------------------------------------------------------

    def cached_funcs(self) -> List[Any]:
        """
        Returns a list of our methods that are cached. See
        :func:`clear_caches`.
        """
        return [
            self.get_source_databases,
            self.get_scrub_from_db_table_pairs,
            self.get_src_db_tablepairs,
            self.get_src_db_tablepairs_w_pt_info,
            self.get_src_db_tablepairs_w_int_pk,
            self.get_src_dbs_tables_with_no_pt_info_no_pk,
            self.get_src_dbs_tables_with_no_pt_info_int_pk,
            self.get_dest_tables,
            self.get_dest_tables_with_patient_info,
            self.get_optout_defining_fields,
            self.get_mandatory_scrubber_sigs,

            self.get_src_tables,
            self.get_src_tables_with_active_dest,
            self.get_src_tables_with_patient_info,
            self.get_patient_src_tables_with_active_dest,

            self.get_dest_tables_for_src_db_table,
            self.get_dest_table_for_src_db_table,
            self.get_rows_for_src_table,
            self.get_fieldnames_for_src_table,
            self.get_scrub_from_rows,
            self.get_pk_ddr,
            self.get_int_pk_ddr,
            self.get_int_pk_name,
            self.has_active_destination,
            self.get_pid_name,
            self.get_mpid_name,

            self.get_src_dbs_tables_for_dest_table,
            self.get_rows_for_dest_table,

            self.get_dest_sqla_table,
        ]

    def clear_caches(self) -> None:
        """
        Clear all our cached information.
        """
        for func in self.cached_funcs():
            func.cache_clear()

    def debug_cache_hits(self) -> None:
        """
        Report cache hit information for our caches, to the Python log.
        """
        for func in self.cached_funcs():
            log.debug(f"{func.__name__}: {func.cache_info()}")

    # -------------------------------------------------------------------------
    # Filtering
    # -------------------------------------------------------------------------

    KEEP_FUNCTION_TYPE = Callable[[DataDictionaryRow], bool]
    # ... returns keep (True/False)

    def remove_rows_by_filter(self, keep: KEEP_FUNCTION_TYPE) -> None:
        """
        Removes any rows that do not pass a filter function.

        Args:
            keep:
                Function taking a data dictionary row as an argument, and
                returning a boolean of whether to keep the row.
        """
        self.rows = [
            row for row in self.rows if keep(row)
        ]

    def omit_rows_by_filter(self, keep: KEEP_FUNCTION_TYPE) -> None:
        """
        Set to "omit" any rows that do not pass a filter function.
        Does not alter any rows already set to omit.

        Args:
            keep:
                Function taking a data dictionary row as an argument, and
                returning a boolean of whether to keep the row.
        """
        for row in self.rows:
            if not row.omit:
                row.omit = not keep(row)

    MODIFYING_KEEP_FUNCTION_TYPE = Callable[[DataDictionaryRow],
                                            Optional[DataDictionaryRow]]
    # returns the row (perhaps modified) to keep, or None to reject

    def remove_rows_by_modifying_filter(
            self, keep_modify: MODIFYING_KEEP_FUNCTION_TYPE) -> None:
        """
        Removes any rows that do not pass a filter function; allows the filter
        function to modify rows that are kept.

        Args:
            keep_modify:
                Function taking a data dictionary row as an argument, and
                returning either the row (potentially modified) to retain it,
                or ``None`` to reject it.
        """
        new_rows = []  # type: List[DataDictionaryRow]
        for row in self.rows:
            result = keep_modify(row)
            if result is not None:
                new_rows.append(result)
        self.rows = new_rows
