#!/usr/bin/env python
# crate_anon/anonymise/dd.py

"""
Data dictionary classes for CRATE anonymiser.

Data dictionary as a TSV file, for ease of editing by multiple authors, rather
than a database table.

Author: Rudolf Cardinal
Created at: 18 Feb 2015
Last update: 22 Nov 2015

Copyright/licensing:

    Copyright (C) 2015-2016 Rudolf Cardinal (rudolf@pobox.com).
    Department of Psychiatry, University of Cambridge.

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

"""

# =============================================================================
# Imports
# =============================================================================

import collections
import csv
from functools import lru_cache
import logging
import operator
from typing import AbstractSet, Any, List, Optional, Tuple

from cardinal_pythonlib.rnc_db import is_sqltype_integer
from sortedcontainers import SortedSet
from sqlalchemy import Column, Table

# don't import config: circular dependency would have to be sorted out
from crate_anon.anonymise.constants import (
    MYSQL_TABLE_ARGS,
    SRCFLAG,
    TridType,
)
from crate_anon.anonymise.ddr import DataDictionaryRow
from crate_anon.common.sqla import is_sqlatype_text_over_one_char

log = logging.getLogger(__name__)


# =============================================================================
# DataDictionary
# =============================================================================

CONFIG_FWD_REF = "Config"


class DataDictionary(object):
    """
    Class representing an entire data dictionary.
    """

    def __init__(self, config: CONFIG_FWD_REF) -> None:
        """
        Set defaults.
        """
        self.config = config
        self.rows = []
        self.cached_srcdb_table_pairs = SortedSet()
        self.n_definers = 0

    def read_from_file(self, filename: str) -> None:
        """
        Read DD from file.
        """
        self.rows = []
        log.debug("Opening data dictionary: {}".format(filename))
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
                ddr = DataDictionaryRow()
                try:
                    ddr.set_from_dict(valuedict)
                    ddr.check_valid(self.config)
                except ValueError:
                    log.critical("Offending input: {}".format(valuedict))
                    raise
                self.rows.append(ddr)
            log.debug("... content loaded.")
        self.clear_caches()

    def read_from_source_databases(self, report_every: int = 100) -> None:
        """
        Create a draft DD from a source database.
        """
        log.info("Reading information for draft data dictionary")
        existing_signatures = [ddr.get_signature() for ddr in self.rows]
        for pretty_dbname, db in self.config.sources.items():
            log.info("... database nice name = {}".format(pretty_dbname))
            cfg = db.srccfg
            meta = db.metadata
            i = 0
            for t in meta.sorted_tables:
                tablename = t.name
                log.info("... ... table: {}".format(tablename))
                new_rows = []
                for c in t.columns:
                    i += 1
                    if report_every and i % report_every == 0:
                        log.debug("... reading source field {}".format(i))
                    columnname = c.name
                    # import pdb; pdb.set_trace()
                    # log.critical("str(coltype) == {}".format(str(c.type)))
                    # log.critical("repr(coltype) == {}".format(repr(c.type)))
                    datatype_sqltext = str(c.type)
                    sqla_coltype = c.type
                    # Do not manipulate the case of SOURCE tables/columns.
                    # If you do, they can fail to match the SQLAlchemy
                    # introspection and cause a crash.
                    # Changed to be a destination manipulation (2016-06-04).
                    if cfg.is_table_blacklisted(tablename):
                        continue
                    if cfg.is_field_blacklisted(columnname):
                        continue
                    comment = ''  # currently unsupported by SQLAlchemy
                    if self.config.append_source_info_to_comment:
                        comment = "[from {t}.{f}]".format(
                            t=tablename,
                            f=columnname,
                        )
                    ddr = DataDictionaryRow()
                    ddr.set_from_src_db_info(
                        pretty_dbname, tablename, columnname,
                        datatype_sqltext,
                        sqla_coltype,
                        dbconf=cfg,
                        config=self.config,
                        comment=comment)

                    # If we have this one already, skip ASAP
                    sig = ddr.get_signature()
                    if sig in existing_signatures:
                        continue
                    existing_signatures.append(sig)

                    ddr.check_valid(self.config)
                    new_rows.append(ddr)

                # Now, table-wide checks across all columns:
                is_patient_table = any(ddr.contains_patient_info()
                                       for ddr in new_rows)
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
        log.info("Sorting data dictionary")
        self.rows = sorted(
            self.rows,
            key=operator.attrgetter("src_db_lowercase",
                                    "src_table_lowercase",
                                    "src_field_lowercase"))
        log.info("... done")

    def check_against_source_db(self) -> None:
        """
        Check DD validity against the source database.
        Also caches SQLAlchemy source column type
        """
        log.debug("Checking DD: source tables...")
        for d in self.get_source_databases():
            db = self.config.sources[d]

            for t in self.get_src_tables(d):

                dt = self.get_dest_tables_for_src_db_table(d, t)
                if len(dt) > 1:
                    raise ValueError(
                        "Source table {d}.{t} maps to >1 destination "
                        "table: {dt}".format(d=d, t=t, dt=", ".join(dt)))

                rows = self.get_rows_for_src_table(d, t)
                fieldnames = self.get_fieldnames_for_src_table(d, t)

                if any([r.being_scrubbed() or r.master_pid
                        for r in rows if not r.omit]):
                    pidfield = db.srccfg.ddgen_per_table_pid_field
                    if pidfield not in fieldnames:
                        raise ValueError(
                            "Source table {d}.{t} has a scrub_in or "
                            "src_flags={f} field but no {p} field".format(
                                d=d, t=t, f=SRCFLAG.MASTER_PID, p=pidfield))

                if t not in db.table_names:
                    log.debug(
                        "Source database {d} has tables: {tables}".format(
                            d=d, tables=db.table_names))
                    raise ValueError(
                        "Table {t} missing from source database "
                        "{d}".format(t=t, d=d))

                # We may need to cross-reference rows, so all rows need to know
                # their type.
                for r in rows:
                    sqla_coltype = (
                        db.metadata.tables[t].columns[r.src_field].type)
                    r.set_src_sqla_coltype(sqla_coltype)

                for r in rows:
                    if r.src_field not in db.metadata.tables[t].columns:
                        raise ValueError(
                            "Column {c} missing from table {t} in source "
                            "database {d}".format(c=r.src_field, t=t, d=d))

                    for am in r.get_alter_methods():
                        if am.extract_from_blob:
                            extrow = next(
                                (r2 for r2 in rows
                                    if r2.src_field == am.extract_ext_field),
                                None)
                            if extrow is None:
                                raise ValueError(
                                    "alter_method = {am}, but field {f} not "
                                    "found in the same table".format(
                                        am=r.alter_method,
                                        f=am.extract_ext_field))
                            if not is_sqlatype_text_over_one_char(
                                    extrow.get_src_sqla_coltype(self.config)):
                                raise ValueError(
                                    "alter_method = {am}, but field {f}, which"
                                    " should contain an extension or filename,"
                                    " is not text of >1 character".format(
                                        am=r.alter_method,
                                        f=am.extract_ext_field))

                n_pks = sum([1 if x.pk else 0 for x in rows])
                if n_pks > 1:
                    raise ValueError(
                        "Table {d}.{t} has >1 source PK set".format(
                            d=d, t=t))

        log.debug("... source tables checked.")
        
    def check_valid(self,
                    prohibited_fieldnames: List[str] = None,
                    check_against_source_db: bool = True) -> None:
        """
        Check DD validity, internally +/- against the source database.
        """
        if prohibited_fieldnames is None:
            prohibited_fieldnames = []
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
                        raise ValueError("Do not set omit on src_flags={} "
                                         "fields".format(SRCFLAG.ADD_SRC_HASH))
                    if r.constant and r.omit:
                        raise ValueError("Do not set omit on src_flags={} "
                                         "fields".format(SRCFLAG.CONSTANT))
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
                    "Field {}.{}.{} has src_flags={} set, but that table does "
                    "not have a primary patient ID field or a master patient "
                    "ID field".format(src_db, src_table, optout_colname,
                                      SRCFLAG.OPT_OUT))

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
        src_sigs = []
        dst_sigs = []
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
            raise ValueError("Duplicate source rows: {}".format(
                src_duplicates))
        if dst_duplicates:
            raise ValueError("Duplicate source rows: {}".format(
                dst_duplicates))

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
                    "Must have at least one field with "
                    "src_flags={} set.".format(SRCFLAG.DEFINES_PRIMARY_PIDS))
        elif self.n_definers > 1:
            log.warning(
                "Unusual: >1 field with src_flags={} set.".format(
                    SRCFLAG.DEFINES_PRIMARY_PIDS))

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
        """Return a SortedSet of source database names."""
        return SortedSet([
             ddr.src_db
             for ddr in self.rows
             if ddr.required()
         ])

    @lru_cache(maxsize=None)
    def get_scrub_from_db_table_pairs(self) -> AbstractSet[Tuple[str, str]]:
        """Return a SortedSet of (source database name, source table) tuples
        where those fields contain scrub_src (scrub-from) information."""
        return SortedSet([
            (ddr.src_db, ddr.src_table)
            for ddr in self.rows
            if ddr.scrub_src
        ])
        # even if omit flag set

    @lru_cache(maxsize=None)
    def get_src_db_tablepairs(self) -> AbstractSet[Tuple[str, str]]:
        """Return a SortedSet of (source database name, source table) tuples.
        """
        return SortedSet([
            (ddr.src_db, ddr.src_table)
            for ddr in self.rows
        ])

    @lru_cache(maxsize=None)
    def get_src_db_tablepairs_w_pt_info(self) -> AbstractSet[Tuple[str, str]]:
        """Return a SortedSet of (source database name, source table) tuples.
        """
        return SortedSet([
            (ddr.src_db, ddr.src_table)
            for ddr in self.rows
            if ddr.contains_patient_info()
        ])

    @lru_cache(maxsize=None)
    def get_src_db_tablepairs_w_int_pk(self) -> AbstractSet[Tuple[str, str]]:
        """Return a SortedSet of (source database name, source table) tuples.
        """
        return SortedSet([
            (ddr.src_db, ddr.src_table)
            for ddr in self.rows
            if self.get_pk_ddr(ddr.src_db, ddr.src_table) is not None
        ])

    @lru_cache(maxsize=None)
    def get_src_dbs_tables_with_no_pt_info_no_pk(self) \
            -> AbstractSet[Tuple[str, str]]:
        """Return a SortedSet of (source database name, source table) tuples
        where the table has no patient information and no integer PK."""
        return (
            self.get_src_db_tablepairs() -
            self.get_src_db_tablepairs_w_pt_info() -
            self.get_src_db_tablepairs_w_int_pk()
        )

    @lru_cache(maxsize=None)
    def get_src_dbs_tables_with_no_pt_info_int_pk(self) \
            -> AbstractSet[Tuple[str, str]]:
        """Return a SortedSet of (source database name, source table) tuples
        where the table has no patient information and has an integer PK."""
        return (
            (self.get_src_db_tablepairs() -
                self.get_src_db_tablepairs_w_pt_info()) &  # & is intersection
            self.get_src_db_tablepairs_w_int_pk()
        )

    @lru_cache(maxsize=None)
    def get_dest_tables(self) -> AbstractSet[str]:
        """Return a SortedSet of all destination tables."""
        return SortedSet([
            ddr.dest_table
            for ddr in self.rows
            if not ddr.omit
        ])

    @lru_cache(maxsize=None)
    def get_dest_tables_with_patient_info(self) -> AbstractSet[str]:
        """Return a SortedSet of destination table names that have patient
        information."""
        return SortedSet([
            ddr.dest_table
            for ddr in self.rows
            if ddr.contains_patient_info() and not ddr.omit
        ])

    @lru_cache(maxsize=None)
    def get_optout_defining_fields(self) \
            -> AbstractSet[Tuple[str, str, str, str, str]]:
        """Return a SortedSet of (src_db, src_table, src_field, pidfield,
        mpidfield) tuples."""
        return SortedSet([
            (ddr.src_db, ddr.src_table, ddr.src_field,
                self.get_pid_name(ddr.src_db, ddr.src_table),
                self.get_mpid_name(ddr.src_db, ddr.src_table))
            for ddr in self.rows
            if ddr.opt_out_info
        ])

    @lru_cache(maxsize=None)
    def get_mandatory_scrubber_sigs(self) -> AbstractSet[str]:
        return set([ddr.get_signature() for ddr in self.rows
                    if ddr.required_scrubber])

    # =========================================================================
    # Queries by source DB
    # =========================================================================

    @lru_cache(maxsize=None)
    def get_src_tables(self, src_db: str) -> AbstractSet[str]:
        """For a given source database name, return a SortedSet of source
        tables."""
        return SortedSet([
            ddr.src_table
            for ddr in self.rows
            if ddr.src_db == src_db and ddr.required()
        ])

    @lru_cache(maxsize=None)
    def get_src_tables_with_active_dest(self, src_db: str) -> AbstractSet[str]:
        """For a given source database name, return a SortedSet of source
        tables."""
        return SortedSet([
            ddr.src_table
            for ddr in self.rows
            if ddr.src_db == src_db and not ddr.omit
        ])

    @lru_cache(maxsize=None)
    def get_src_tables_with_patient_info(self, src_db: str) -> AbstractSet[str]:
        """For a given source database name, return a SortedSet of source
        tables that have patient information."""
        return SortedSet([
            ddr.src_table
            for ddr in self.rows
            if ddr.src_db == src_db and ddr.contains_patient_info()
        ])

    @lru_cache(maxsize=None)
    def get_patient_src_tables_with_active_dest(self, src_db: str) \
            -> AbstractSet[str]:
        """For a given source database name, return a SortedSet of source
        tables that have an active destination table."""
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
        """For a given source database/table, return a SortedSet of destination
        tables."""
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
        """For a given source database/table, return the single or the first
        destination table."""
        return list(
            self.get_dest_tables_for_src_db_table(src_db, src_table))[0]

    @lru_cache(maxsize=None)
    def get_rows_for_src_table(self, src_db: str, src_table: str) \
            -> AbstractSet[DataDictionaryRow]:
        """For a given source database name/table, return a SortedSet of DD
        rows."""
        return SortedSet([
            ddr
            for ddr in self.rows
            if ddr.src_db == src_db and ddr.src_table == src_table
        ])

    @lru_cache(maxsize=None)
    def get_fieldnames_for_src_table(self, src_db: str, src_table: str) \
            -> AbstractSet[DataDictionaryRow]:
        """For a given source database name/table, return a SortedSet of source
        fields."""
        return SortedSet([
            ddr.src_field
            for ddr in self.rows
            if ddr.src_db == src_db and ddr.src_table == src_table
        ])

    @lru_cache(maxsize=None)
    def get_scrub_from_rows(self, src_db: str, src_table: str) \
            -> AbstractSet[DataDictionaryRow]:
        """Return a SortedSet of DD rows for all fields containing scrub_src
        (scrub-from) information."""
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
        """For a given source database name and table, return the DD row
        for the integer PK for that table.

        Will return None if no such data dictionary row.
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
        """For a given source database name and table, return the field name
        of the integer PK for that table."""
        ddr = self.get_pk_ddr(src_db, src_table)
        if ddr is None:
            return None
        return ddr.src_field

    @lru_cache(maxsize=None)
    def has_active_destination(self, src_db: str, src_table: str) -> bool:
        """For a given source database name and table: does it have an active
        destination?"""
        for ddr in self.rows:
            if (ddr.src_db == src_db and
                    ddr.src_table == src_table and
                    not ddr.omit):
                return True
        return False

    @lru_cache(maxsize=None)
    def get_pid_name(self, src_db: str, src_table: str) -> Optional[str]:
        for ddr in self.rows:
            if (ddr.src_db == src_db and
                    ddr.src_table == src_table and
                    ddr.primary_pid):
                return ddr.src_field
        return None

    @lru_cache(maxsize=None)
    def get_mpid_name(self, src_db: str, src_table: str) -> Optional[str]:
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
        """For a given destination table, return a SortedSet of (dbname, table)
        tuples."""
        return SortedSet([
            (ddr.src_db, ddr.src_table)
            for ddr in self.rows
            if ddr.dest_table == dest_table
        ])

    @lru_cache(maxsize=None)
    def get_rows_for_dest_table(
            self, dest_table: str) -> AbstractSet[DataDictionaryRow]:
        """For a given destination table, return a SortedSet of DD rows."""
        return SortedSet([
            ddr
            for ddr in self.rows
            if ddr.dest_table == dest_table and not ddr.omit
        ])

    # =========================================================================
    # SQLAlchemy Table objects
    # =========================================================================

    @lru_cache(maxsize=None)
    def get_dest_sqla_table(self, tablename: str) -> Table:
        metadata = self.config.destdb.metadata
        columns = []
        for ddr in self.get_rows_for_dest_table(tablename):
            columns.append(ddr.get_dest_sqla_column(self.config))
            if ddr.add_src_hash:
                columns.append(self._get_srchash_sqla_column())
            if ddr.primary_pid:
                columns.append(self._get_trid_sqla_column())
        return Table(tablename, metadata, *columns, **MYSQL_TABLE_ARGS)

    def _get_srchash_sqla_column(self) -> Column:
        return Column(
            self.config.source_hash_fieldname,
            self.config.SqlTypeEncryptedPid,
            doc='Hashed amalgamation of all source fields'
        )

    def _get_trid_sqla_column(self) -> Column:
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
            self.get_int_pk_name,
            self.has_active_destination,
            self.get_pid_name,
            self.get_mpid_name,

            self.get_src_dbs_tables_for_dest_table,
            self.get_rows_for_dest_table,

            self.get_dest_sqla_table,
        ]

    def clear_caches(self) -> None:
        for func in self.cached_funcs():
            func.cache_clear()

    def debug_cache_hits(self) -> None:
        for func in self.cached_funcs():
            log.debug("{}: {}".format(func.__name__, func.cache_info()))
