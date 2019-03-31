#!/usr/bin/env python

"""
crate_anon/anonymise/dd.py

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

**Data dictionary classes for CRATE anonymiser.**

The data dictionary is a TSV file, for ease of editing by multiple authors,
rather than a database table.

"""

# =============================================================================
# Imports
# =============================================================================

import collections
import csv
from functools import lru_cache
import logging
import operator
from typing import (AbstractSet, Any, List, Optional, Tuple, TYPE_CHECKING,
                    Union)

from cardinal_pythonlib.rnc_db import is_sqltype_integer
from cardinal_pythonlib.sqlalchemy.schema import (
    is_sqlatype_integer,
    is_sqlatype_string,
    is_sqlatype_text_over_one_char,
)
from sortedcontainers import SortedSet
import sqlalchemy.exc
from sqlalchemy import Column, Table, DateTime
from sqlalchemy.sql.sqltypes import String, TypeEngine

# don't import config: circular dependency would have to be sorted out
from crate_anon.anonymise.constants import (
    TABLE_KWARGS,
    SRCFLAG,
    TridType,
)
from crate_anon.anonymise.ddr import DataDictionaryRow

if TYPE_CHECKING:
    from crate_anon.anonymise.config import Config

log = logging.getLogger(__name__)


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
        self.n_definers = 0

    def read_from_file(self, filename: str) -> None:
        """
        Read DD from file.

        Args:
            filename: filename to read
        """
        self.rows = []  # type: List[DataDictionaryRow]
        log.debug(f"Opening data dictionary: {filename}")
        with open(filename, 'r') as tsvfile:
            tsv = csv.reader(tsvfile, delimiter='\t')
            headers = next(tsv)
            if not all(x in headers for x in DataDictionaryRow.ROWNAMES):
                raise ValueError(
                    "Bad data dictionary file. Must be a tab-separated value "
                    "(TSV) file with the following row headings:\n"
                    "{}\n\n"
                    "but yours are:\n\n"
                    "{}".format(
                        "\n".join(DataDictionaryRow.ROWNAMES),
                        "\n".join(headers)
                    )
                )
            log.debug("Data dictionary has correct header. Loading content...")
            for values in tsv:
                valuedict = dict(zip(headers, values))
                ddr = DataDictionaryRow(self.config)
                try:
                    ddr.set_from_dict(valuedict)
                    ddr.check_valid()
                except ValueError:
                    log.critical(f"Offending input: {valuedict}")
                    raise
                self.rows.append(ddr)
            log.debug("... content loaded.")
        self.clear_caches()

    def read_from_source_databases(self, report_every: int = 100) -> None:
        """
        Create a draft DD from a source database.

        Args:
            report_every: report to the Python log every *n* columns
        """
        log.info("Reading information for draft data dictionary")
        existing_signatures = set(ddr.get_signature() for ddr in self.rows)
        for pretty_dbname, db in self.config.sources.items():
            log.info(f"... database nice name = {pretty_dbname}")
            cfg = db.srccfg
            meta = db.metadata
            i = 0
            for t in meta.sorted_tables:
                tablename = t.name
                log.info(f"... ... table: {tablename}")
                new_rows = []  # type: List[DataDictionaryRow]
                is_patient_table = False

                # Skip table?
                if cfg.is_table_blacklisted(tablename):
                    log.debug(f"Skipping blacklisted table: {tablename}")
                    continue
                all_col_names = [c.name for c in t.columns]
                if cfg.does_table_fail_minimum_fields(all_col_names):
                    log.debug(f"Skipping table {t} because it fails "
                              f"minimum field requirements")
                    continue

                for c in t.columns:
                    i += 1
                    if report_every and i % report_every == 0:
                        log.debug(f"... reading source field number {i}")
                    columnname = c.name
                    # import pdb; pdb.set_trace()
                    # log.critical(f"str(coltype) == {str(c.type)}")
                    # log.critical(f"repr(coltype) == {repr(c.type)}")
                    try:
                        datatype_sqltext = str(c.type)
                    except sqlalchemy.exc.CompileError:
                        log.critical(f"Column that failed was: {c!r}")
                        raise
                    sqla_coltype = c.type
                    # Do not manipulate the case of SOURCE tables/columns.
                    # If you do, they can fail to match the SQLAlchemy
                    # introspection and cause a crash.
                    # Changed to be a destination manipulation (2016-06-04).
                    if cfg.is_field_blacklisted(columnname):
                        log.debug(f"Skipping blacklisted column: "
                                  f"{tablename}.{columnname}")
                        continue
                    comment = ''  # currently unsupported by SQLAlchemy
                    if self.config.ddgen_append_source_info_to_comment:
                        comment = f"[from {tablename}.{columnname}]"
                    ddr = DataDictionaryRow(self.config)
                    ddr.set_from_src_db_info(
                        pretty_dbname, tablename, columnname,
                        datatype_sqltext,
                        sqla_coltype,
                        dbconf=cfg,
                        comment=comment)

                    # If we have this one already, skip ASAP
                    sig = ddr.get_signature()
                    if sig in existing_signatures:
                        log.debug(f"Skipping duplicated column: "
                                  f"{tablename}.{columnname}")
                        continue
                    existing_signatures.add(sig)

                    if ddr.contains_patient_info():
                        is_patient_table = True

                    # Checking validity slows us down, and we are after all
                    # creating these programmatically!
                    # ddr.check_valid(self.config)

                    new_rows.append(ddr)

                # Now, table-wide checks across all columns:
                if not is_patient_table:
                    for ddr in new_rows:
                        ddr.remove_scrub_from_alter_methods()
                        # Pointless to scrub in a non-patient table

                self.rows.extend(new_rows)

        log.info("... done")
        self.clear_caches()
        log.info("Revising draft data dictionary")
        for ddr in self.rows:
            if ddr.from_file:
                continue
            # Don't scrub_in non-patient tables
            if (ddr.src_table
                    not in self.get_src_tables_with_patient_info(ddr.src_db)):
                ddr._scrub = False
        log.info("... done")
        self.sort()

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

    def check_against_source_db(self) -> None:
        """
        Check DD validity against the source database(s).

        Also caches SQLAlchemy source column types.
        """
        def ensure_no_type_mismatch(ddr: DataDictionaryRow,
                                    config_sqlatype: Union[TypeEngine, String],
                                    human_type: str) -> None:
            rowtype = ddr.get_src_sqla_coltype()
            if (is_sqlatype_integer(rowtype) and
                    is_sqlatype_integer(config_sqlatype)):
                # Good enough. The only integer type we use for PID/MPID is
                # BigInteger, so any integer type should fit.
                return
            if (is_sqlatype_string(rowtype) and
                    is_sqlatype_string(config_sqlatype)):
                # noinspection PyUnresolvedReferences
                if rowtype.length <= config_sqlatype.length:
                    return
            raise ValueError(
                f"Source column {r.get_signature()} is marked as a "
                f"{human_type} field but its type is "
                f"{r.get_src_sqla_coltype()}, while the config thinks it "
                f"should be {config_sqlatype}")

        log.debug("Checking DD: source tables...")
        for d in self.get_source_databases():
            db = self.config.sources[d]

            for t in self.get_src_tables(d):

                dt = self.get_dest_tables_for_src_db_table(d, t)
                if len(dt) > 1:
                    raise ValueError(
                        f"Source table {d}.{t} maps to >1 destination "
                        f"table: {', '.join(dt)}")

                rows = self.get_rows_for_src_table(d, t)
                fieldnames = self.get_fieldnames_for_src_table(d, t)

                if t not in db.table_names:
                    log.debug(
                        f"Source database {d!r} has tables: {db.table_names}")
                    raise ValueError(
                        f"Table {t!r} missing from source database {d!r}")

                # We may need to cross-reference rows, so all rows need to know
                # their type.
                for r in rows:
                    if r.src_field not in db.metadata.tables[t].columns:
                        raise ValueError(
                            f"Column {r.src_field!r} missing from table {t!r} "
                            f"in source database {d!r}")
                    sqla_coltype = (
                        db.metadata.tables[t].columns[r.src_field].type)
                    r.set_src_sqla_coltype(sqla_coltype)  # CACHES TYPE HERE

                # We have to iterate twice, but shouldn't iterate more than
                # that, for speed.
                n_pks = 0
                needs_pidfield = False
                for r in rows:
                    # Needs PID field in table?
                    if not r.omit and (r.being_scrubbed() or r.master_pid):
                        needs_pidfield = True

                    if r.primary_pid:
                        ensure_no_type_mismatch(r, self.config.pidtype,
                                                "primary PID")
                    if r.master_pid:
                        ensure_no_type_mismatch(r, self.config.mpidtype,
                                                "master PID")

                    # Too many PKs?
                    if r.pk:
                        n_pks += 1
                        if n_pks > 1:
                            raise ValueError(
                                f"Table {d}.{t} has >1 source PK set")

                    # Duff alter method?
                    for am in r.get_alter_methods():
                        if am.extract_from_blob:
                            extrow = next(
                                (r2 for r2 in rows
                                    if r2.src_field == am.extract_ext_field),
                                None)
                            if extrow is None:
                                raise ValueError(
                                    f"alter_method = {r.alter_method}, but "
                                    f"field {am.extract_ext_field} not found "
                                    f"in the same table")
                            if not is_sqlatype_text_over_one_char(
                                    extrow.get_src_sqla_coltype()):
                                raise ValueError(
                                    f"alter_method = {r.alter_method}, but "
                                    f"field {am.extract_ext_field}, which "
                                    f"should contain an extension or "
                                    f"filename, is not text of >1 character")

                if needs_pidfield:
                    # Test changed from an error to a warning 2016-11-11.
                    # We don't really care about validating against the ddgen
                    # options; if a user has done their data dictionary
                    # manually, it may not be relevant.
                    expected_pidfield = db.srccfg.ddgen_per_table_pid_field
                    if expected_pidfield not in fieldnames:
                        log.warning(
                            f"Source table {d}.{t} has a scrub_in or "
                            f"src_flags={SRCFLAG.MASTER_PID} field but no "
                            f"master patient ID field (expected to be: "
                            f"{expected_pidfield})")

        log.debug("... source tables checked.")

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

        # Individual rows will already have been checked with their own
        # check_valid() method. But now we check collective consistency.

        log.debug("Checking DD: prohibited flags...")
        for d in self.get_source_databases():
            for t in self.get_src_tables(d):
                # This will have excluded all tables where all rows are
                # omitted. So now we have only active tables, for which we
                # cannot combine certain flags.
                for r in self.get_rows_for_src_table(d, t):
                    if r.add_src_hash and r.omit:
                        raise ValueError(
                            f"Do not set omit on "
                            f"src_flags={SRCFLAG.ADD_SRC_HASH} fields")
                    if r.constant and r.omit:
                        raise ValueError(
                            f"Do not set omit on "
                            f"src_flags={SRCFLAG.CONSTANT} fields")
                # We used to prohibit these combinations at all times, in the
                # DataDictionaryRow class, but it's inconvenient to have to
                # alter these flags if you want to omit the whole table.

        log.debug("Checking DD: prohibited fieldnames...")
        if prohibited_fieldnames:
            for r in self.rows:
                r.check_prohibited_fieldnames(prohibited_fieldnames)

        log.debug("Checking DD: source tables...")
        for t in self.get_optout_defining_fields():
            (src_db, src_table, optout_colname, pid_colname, mpid_colname) = t
            if not pid_colname and not mpid_colname:
                raise ValueError(
                    f"Field {src_db}.{src_table}.{optout_colname} has "
                    f"src_flags={SRCFLAG.OPT_OUT} set, but that table does "
                    f"not have a primary patient ID field or a master patient "
                    f"ID field")

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

        log.debug("Checking DD: duplicate source/destination rows?")
        src_sigs = []  # type: List[str]
        dst_sigs = []  # type: List[str]
        for r in self.rows:
            src_sigs.append(r.get_signature())
            if not r.omit:
                dst_sigs.append(r.get_dest_signature())
        # noinspection PyArgumentList
        src_duplicates = [
            item for item, count in collections.Counter(src_sigs).items()
            if count > 1]
        # noinspection PyArgumentList
        dst_duplicates = [
            item for item, count in collections.Counter(dst_sigs).items()
            if count > 1]
        if src_duplicates:
            raise ValueError(f"Duplicate source rows: {src_duplicates}")
        if dst_duplicates:
            raise ValueError(f"Duplicate source rows: {dst_duplicates}")

        if check_against_source_db:
            self.check_against_source_db()

        log.debug("Checking DD: global checks...")
        self.n_definers = sum([1 if x.defines_primary_pids else 0
                               for x in self.rows])
        if self.n_definers == 0:
            if all([db.srccfg.ddgen_allow_no_patient_info
                    for pretty_dbname, db in self.config.sources.items()]):
                log.warning("NO PATIENT-DEFINING FIELD! DATABASE(S) WILL "
                            "BE COPIED, NOT ANONYMISED.")
            else:
                raise ValueError(
                    f"Must have at least one field with "
                    f"src_flags={SRCFLAG.DEFINES_PRIMARY_PIDS} set.")
        elif self.n_definers > 1:
            log.warning(
                f"Unusual: >1 field with "
                f"src_flags={SRCFLAG.DEFINES_PRIMARY_PIDS} set.")

        log.debug("... DD checked.")

    # =========================================================================
    # Whole-DD operations
    # =========================================================================

    def get_tsv(self) -> str:
        """
        Return the DD in TSV format.
        """
        return "\n".join(
            ["\t".join(DataDictionaryRow.ROWNAMES)] +
            [r.get_tsv() for r in self.rows]
        )

    # =========================================================================
    # Global DD queries
    # =========================================================================

    @lru_cache(maxsize=None)
    def get_source_databases(self) -> AbstractSet[str]:
        """
        Return a SortedSet of source database names.
        """
        return SortedSet([
             ddr.src_db
             for ddr in self.rows
             if ddr.required()
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
            if ddr.contains_patient_info()
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
            if ddr.contains_patient_info() and not ddr.omit
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
        return set([ddr.get_signature() for ddr in self.rows
                    if ddr.required_scrubber])

    # =========================================================================
    # Queries by source DB
    # =========================================================================

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
            if ddr.src_db == src_db and ddr.required()
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
            if ddr.src_db == src_db and ddr.contains_patient_info()
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

    # =========================================================================
    # Queries by source DB/table
    # =========================================================================

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

    # =========================================================================
    # Queries by destination table
    # =========================================================================

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

    # =========================================================================
    # SQLAlchemy Table objects
    # =========================================================================

    @lru_cache(maxsize=None)
    def get_dest_sqla_table(self, tablename: str,
                            timefield: str = None) -> Table:
        """
        For a given destination table name, return an
        :class:`sqlalchemy.sql.schema.Table` object for the destination table
        (which we will create).
        """
        metadata = self.config.destdb.metadata
        columns = []  # type: List[Column]
        for ddr in self.get_rows_for_dest_table(tablename):
            columns.append(ddr.get_dest_sqla_column())
            if ddr.add_src_hash:
                columns.append(self._get_srchash_sqla_column())
            if ddr.primary_pid:
                columns.append(self._get_trid_sqla_column())
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
            self.config.SqlTypeEncryptedPid,
            doc='Hashed amalgamation of all source fields'
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
            doc='Transient integer research ID (TRID)'
        )

    # =========================================================================
    # Clear caches
    # =========================================================================

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
