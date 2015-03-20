#!/usr/bin/python2.7
# -*- encoding: utf8 -*-

"""
Shared functions for anonymiser.py, nlp_manager.py, webview_anon.py

Author: Rudolf Cardinal
Created at: 26 Feb 2015
Last update: 19 Mar 2015

Copyright/licensing:

    Copyright (C) 2015-2015 Rudolf Cardinal (rudolf@pobox.com).
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

import cgi
import csv
import codecs
import ConfigParser
import datetime
import dateutil
import dateutil.tz
import logging
logging.basicConfig()  # just in case nobody else has done this
logger = logging.getLogger("anonymise")
import os
import pytz
import urllib

from rnc_crypto import MD5Hasher
from rnc_datetime import format_datetime
import rnc_db
from rnc_db import (
    does_sqltype_merit_fulltext_index,
    does_sqltype_require_index_len,
    is_sqltype_date,
    is_sqltype_integer,
    is_sqltype_numeric,
    is_sqltype_text_over_one_char,
    is_sqltype_valid,
    is_valid_field_name,
    is_valid_table_name
)
from rnc_lang import (
    convert_attrs_to_bool,
    convert_attrs_to_int_or_none,
    convert_attrs_to_uppercase,
    count_bool,
    raise_if_attr_blank
)
import rnc_log


# =============================================================================
# Constants
# =============================================================================

MAX_PID_STR = "9" * 10  # e.g. NHS numbers are 10-digit
ENCRYPTED_OUTPUT_LENGTH = len(MD5Hasher("dummysalt").hash(MAX_PID_STR))
SQLTYPE_ENCRYPTED_PID = "VARCHAR({})".format(ENCRYPTED_OUTPUT_LENGTH)
# ... in practice: VARCHAR(32)
DATEFORMAT_ISO8601 = "%Y-%m-%dT%H:%M:%S%z"  # e.g. 2013-07-24T20:04:07+0100
DEFAULT_INDEX_LEN = 20  # for data types where it's mandatory
SEP = "=" * 20 + " "

# =============================================================================
# Demo config
# =============================================================================

DEMO_CONFIG = """
# Configuration file for anonymise.py

# =============================================================================
# Main settings
# =============================================================================

[main]

# -----------------------------------------------------------------------------
# Data dictionary
# -----------------------------------------------------------------------------
# Specify a data dictionary in TSV (tab-separated value) format, with a header
# row. Boolean values can be 0/1, Y/N, T/F, True/False.
# Columns in the data dictionary:
#
#   src_db
#       Specify the source database.
#       Database names are those used in source_databases list below; they
#       don't have to be SQL database names.
#   src_table
#       Table name in source database.
#   src_field
#       Field name in source database.
#   src_datatype
#       SQL data type in source database, e.g. INT, VARCHAR(50).
#   src_pk
#       Boolean. Is this field the primary key for the table it's in?
#
#   primary_pid
#       Boolean. If set:
#       (a) This field will be used to link records for the same patient across
#           all tables. It must therefore be present, and marked in the data
#           dictionary, for ALL tables that contain patient-identifiable
#           information,
#       (b) If the field is not omitted: the field will be hashed as the
#           primary ID (database patient primary key) in the destination.
#   defines_primary_pids
#       Boolean. This row should be used to search for all patient IDs, and
#       will define them for this database. Only those patients will be
#       processed (for all tables containing patient info). Typically, this
#       flag is applied to a SINGLE field in a SINGLE table, the master patient
#       ID.
#
#   scrubsrc_patient
#       Boolean. If true, contains patient-identifiable information that must
#       be removed from "scrub_in" fields.
#   scrubsrc_thirdparty
#       Boolean. If true, contains identifiable information about carer/family/
#       other third party, which must be removed from "scrub_in" fields.
#       (tp = third party)
#   scrubsrc_numeric
#       Boolean. If true, this field (even if textual) is treated as a number
#       for the purposes of scrubbing. Use this for ID numbers, phone numbers,
#       and the like.
#
#   omit
#       Boolean. Omit from output entirely?
#   scrub_in
#       Boolean. Applies to text fields only. If true, the field will have its
#       contents anonymised (using information from other fields).
#   truncate_date
#       Boolean. For date fields; truncate to first of month?
#   master_pid
#       Boolean. Hash this field as the master ID (e.g. NHS number)?
#
#   dest_table
#       Table name in destination database.
#   dest_field
#       Field name in destination database.
#   dest_datatype
#       SQL data type in destination database.
#   add_src_hash
#       - Boolean.
#       - May only be set for src_pk fields (which cannot then be omitted in
#         the destination, and which require the 'index' and 'indexunique'
#         flags, so that a unique index is created for this field).
#       - If set, a field is added to the destination table, with field name as
#         set by the config's source_hash_fieldname variable, containing a hash
#         of the contents of the source record (all fields that are not
#         omitted, OR contain scrubbing information [scrubsrc_patient or
#         scrubsrc_thirdparty]). The field is of type {SQLTYPE_ENCRYPTED_PID}.
#       - This table is then capable of incremental updates.
#   index
#       Boolean. Index this field?
#   indexunique
#       Boolean. Make this index a UNIQUE one? Mandatory for src_pk fields.
#   indexlen
#       Integer. Can be blank. If not, sets the prefix length of the index.
#       Mandatory in MySQL if you apply a normal index to a TEXT or BLOB field.
#   fulltextindex
#       Boolean. Create a FULLTEXT index, for rapid searching within long text
#       fields. (Does not require indexlen.)
#   comment
#       Field comment, stored in destination database.

data_dictionary_filename = testdd.tsv

# -----------------------------------------------------------------------------
# Input fields
# -----------------------------------------------------------------------------

# Specify the (typically integer) patient identifier present in EVERY table.
# It will be replaced by the research ID in the destination database.

per_table_patient_id_field = patient_id

# Master patient ID fieldname. Used for e.g. NHS numbers.

master_pid_fieldname = nhsnum

# -----------------------------------------------------------------------------
# Encryption phrases/passwords
# -----------------------------------------------------------------------------

per_table_patient_id_encryption_phrase = SOME_PASSPHRASE_REPLACE_ME

master_patient_id_encryption_phrase = SOME_OTHER_PASSPHRASE_REPLACE_ME

change_detection_encryption_phrase = YETANOTHER

# -----------------------------------------------------------------------------
# Anonymisation
# -----------------------------------------------------------------------------

# Patient information will be replaced with this

replace_patient_info_with = XXX

# Third-party information will be replaced by this

replace_third_party_info_with = YYY

# Strings to append to every "scrub from" string.
# For example, include "s" if you want to scrub "Roberts" whenever you scrub
# "Robert".
# Multiline field: https://docs.python.org/2/library/configparser.html

scrub_string_suffixes =
    s

# Specify maximum number of errors (insertions, deletions, substitutions) in
# string regex matching. Beware using a high number! Suggest 1-2.

string_max_regex_errors = 1

# Anonymise at word boundaries? True is more conservative; False is more
# liberal and will deal with accidental word concatenation.

anonymise_dates_at_word_boundaries_only = False
anonymise_numbers_at_word_boundaries_only = True
anonymise_strings_at_word_boundaries_only = False

# -----------------------------------------------------------------------------
# Output fields and formatting
# -----------------------------------------------------------------------------

# Research ID field name. This will be a {SQLTYPE_ENCRYPTED_PID}.

research_id_fieldname = brcid

# Change-detection hash fieldname. This will be a {SQLTYPE_ENCRYPTED_PID}.

source_hash_fieldname = _src_hash

# Date-to-text conversion formats

date_to_text_format = %Y-%m-%d
# ... ISO-8601, e.g. 2013-07-24
datetime_to_text_format = %Y-%m-%dT%H:%M:%S
# ... ISO-8601, e.g. 2013-07-24T20:04:07

# Append source table/field to the comment? Boolean.

append_source_info_to_comment = True

# -----------------------------------------------------------------------------
# List of source databases (each of which is defined in its own section).
# -----------------------------------------------------------------------------

# Source database list.
# Multiline field: https://docs.python.org/2/library/configparser.html

source_databases =
    mysourcedb1
    mysourcedb2

# ...

# =============================================================================
# Destination database details. User should have WRITE access.
# =============================================================================

[destination_database]

engine = mysql
host = localhost
port = 3306
user = XXX
password = XXX
db = XXX

# =============================================================================
# Administrative database, containing these tables:
# - secret_map: secret patient ID to research ID mapping.
# - audit: audit trail of various types of access
# User should have WRITE access.
# =============================================================================

[admin_database]

engine = mysql
host = localhost
port = 3306
user = XXX
password = XXX
db = XXX

# =============================================================================
# SOURCE DATABASE DETAILS BELOW HERE.
# User should have READ access only for safety.
# =============================================================================

[mysourcedb1]

engine = mysql
host = localhost
port = 3306
user = XXX
password = XXX
db = XXX

[mysourcedb2]

engine = mysql
host = localhost
port = 3306
user = XXX
password = XXX
db = XXX

""".format(SQLTYPE_ENCRYPTED_PID=SQLTYPE_ENCRYPTED_PID)

# For the style:
#       [source_databases]
#       source1 = blah
#       source2 = thing
# ... you can't have multiple keys with the same name.
# http://stackoverflow.com/questions/287757


# =============================================================================
# Regexes
# =============================================================================

REGEX_METACHARS = ["\\", "^", "$", ".",
                   "|", "?", "*", "+",
                   "(", ")", "[", "{"]
# http://www.regular-expressions.info/characters.html
# Start with \, for replacement.


def escape_literal_string_for_regex(s):
    # Escape any regex characters. Start with \ -> \\.
    for c in REGEX_METACHARS:
        s.replace(c, "\\" + c)
    return s


# =============================================================================
# Data dictionary
# =============================================================================
# - Data dictionary as a TSV file, for ease of editing by multiple authors,
#   rather than a database table.

class DataDictionaryRow(object):
    ROWNAMES = [
        "src_db",
        "src_table",
        "src_field",
        "src_datatype",
        "src_pk",

        "primary_pid",
        "defines_primary_pids",

        "scrubsrc_patient",
        "scrubsrc_thirdparty",
        "scrubsrc_numeric",

        "omit",
        "scrub_in",
        "truncate_date",
        "master_pid",

        "dest_table",
        "dest_field",
        "dest_datatype",
        "add_src_hash",
        "index",
        "indexunique",
        "indexlen",
        "fulltextindex",
        "comment",
    ]

    def __init__(self):
        self.blank()

    def blank(self):
        for x in DataDictionaryRow.ROWNAMES:
            setattr(self, x, None)

    def __str__(self):
        return ", ".join(["{}: {}".format(a, getattr(self, a))
                          for a in DataDictionaryRow.ROWNAMES])

    def set_from_elements(self, elements):
        self.blank()
        if len(elements) != len(DataDictionaryRow.ROWNAMES):
            raise Exception("Bad data dictionary row. Values:\n" +
                            "\n".join(elements))
        for i in xrange(len(elements)):
            setattr(self, DataDictionaryRow.ROWNAMES[i], elements[i])
        convert_attrs_to_bool(self, [
            "src_pk",

            "primary_pid",
            "defines_primary_pids",

            "scrubsrc_patient",
            "scrubsrc_thirdparty",
            "scrubsrc_numeric",

            "omit",
            "scrub_in",
            "truncate_date",
            "master_pid",

            "add_src_hash",
            "index",
            "indexunique",
            "fulltextindex",
        ])
        convert_attrs_to_uppercase(self, [
            "src_datatype",
            "dest_datatype",
        ])
        convert_attrs_to_int_or_none(self, [
            "indexlen"
        ])
        self.check_valid()

    def set_from_src_db_info(self, db, table, field, datatype_short,
                             datatype_full, comment=None):
        self.blank()

        self.src_db = db
        self.src_table = table
        self.src_field = field
        self.src_datatype = datatype_full
        self.src_pk = False

        self.primary_pid = (
            self.src_field == config.per_table_patient_id_field)
        self.defines_primary_pids = False

        self.scrubsrc_patient = False
        self.scrubsrc_thirdparty = False
        self.scrubsrc_numeric = (
            is_sqltype_numeric(datatype_full)
            or self.src_field == config.per_table_patient_id_field
            or self.src_field == config.master_pid_fieldname)

        self.omit = True  # for extra safety
        self.scrub_in = is_sqltype_text_over_one_char(datatype_full)
        # ... for safety
        self.truncate_date = False
        self.master_pid = (
            self.src_field == config.master_pid_fieldname)

        self.dest_table = table
        self.dest_field = (config.research_id_fieldname
                           if self.primary_pid else field)
        self.dest_datatype = (SQLTYPE_ENCRYPTED_PID
                              if self.primary_pid or self.master_pid
                              else datatype_full)
        self.add_src_hash = False
        self.index = (self.dest_field ==
                      config.research_id_fieldname)
        self.indexlen = (
            DEFAULT_INDEX_LEN
            if does_sqltype_require_index_len(self.dest_datatype)
            else None)
        self.fulltextindex = does_sqltype_merit_fulltext_index(
            self.dest_datatype)
        self.comment = comment

    def get_tsv(self):
        values = []
        for x in DataDictionaryRow.ROWNAMES:
            v = getattr(self, x)
            if v is None:
                v = ""
            v = str(v)
            values.append(v)
        return "\t".join(values)

    def check_valid(self):
        try:
            self._check_valid()
        except:
            logger.exception("Offending DD row: {}".format(str(self)))
            raise

    def _check_valid(self):
        raise_if_attr_blank(self, [
            "src_db",
            "src_table",
            "src_field",
            "src_datatype",
        ])
        if not self.omit:
            raise_if_attr_blank(self, [
                "dest_table",
                "dest_field",
                "dest_datatype",
            ])

        if self.src_db not in config.src_db_names:
            raise Exception(
                "Data dictionary row references non-existent source "
                "database: {}".format(self.src_db))
        ensure_valid_table_name(self.src_table)
        ensure_valid_field_name(self.src_field)
        if not is_sqltype_valid(self.src_datatype):
            raise Exception(
                "Source field {db}.{t} has invalid data type: {dt}".format(
                    db=self.src_db,
                    t=self.src_table,
                    dt=self.src_datatype,
                )
            )

        if (self.src_field == config.per_table_patient_id_field
                and not is_sqltype_integer(self.src_datatype)):
            raise Exception(
                "All fields with src_field = {} should be "
                "integer, for work distribution purposes".format(
                    self.src_field
                )
            )

        if self.defines_primary_pids and not self.primary_pid:
            raise Exception("All fields with defines_primary_pids set must "
                            "have primary_pid set")

        if self.scrubsrc_patient and self.scrubsrc_thirdparty:
            raise Exception("Can't treat as both patient and third-party info")

        if count_bool([self.primary_pid, self.master_pid,
                       self.truncate_date, self.scrub_in]) > 1:
            raise Exception(
                "Field can be any ONE of: primary_pid, master_pid, "
                "truncate_date, scrub_in.")

        if not self.omit:
            ensure_valid_table_name(self.dest_table)
            ensure_valid_field_name(self.dest_field)
            if self.dest_field == config.source_hash_fieldname:
                raise Exception(
                    "Destination fields can't be named {f}, as that's the "
                    "name set in the config's source_hash_fieldname "
                    "variable".format(config.source_hash_fieldname))
            if not is_sqltype_valid(self.dest_datatype):
                raise Exception(
                    "Source field {db}.{t} has invalid data type: {dt}".format(
                        db=self.destination_database,
                        t=self.dest_table,
                        dt=self.dest_datatype,
                    )
                )
            if self.src_field == config.per_table_patient_id_field:
                if not self.primary_pid:
                    raise Exception(
                        "All fields with src_field = {} used in output should "
                        "have primary_pid set.".format(self.src_field))
                if self.dest_field != config.research_id_fieldname:
                    raise Exception(
                        "All fields with src_field = {} used in output should "
                        "have dest_field = {}".format(
                            config.per_table_patient_id_field,
                            config.research_id_fieldname))
            if (self.src_field == config.master_pid_fieldname
                    and not self.master_pid):
                raise Exception(
                    "All fields with src_field = {} used in output should have"
                    " master_pid set.".format(config.master_pid_fieldname))

            if self.truncate_date and not is_sqltype_date(self.src_datatype):
                raise Exception("Can't set truncate_date for non-date field")
            if (self.scrub_in
                    and not is_sqltype_text_over_one_char(self.src_datatype)):
                raise Exception("Can't scrub in non-text field or "
                                "single-character text field")

            if ((self.primary_pid or self.master_pid) and
                    self.dest_datatype != SQLTYPE_ENCRYPTED_PID):
                raise Exception(
                    "All primary_pid/master_pid fields used in output must "
                    "have destination_datatype = {}".format(
                        SQLTYPE_ENCRYPTED_PID))

            if self.index and self.fulltextindex:
                raise Exception("Choose either normal or full-text index, "
                                "not both.")
            if (self.index and self.indexlen is None
                    and does_sqltype_require_index_len(self.dest_datatype)):
                raise Exception(
                    "Must specify indexlen to index a TEXT or BLOB field.")

        if self.add_src_hash:
            if not self.src_pk:
                raise Exception(
                    "add_src_hash can only be set on src_pk fields")
            if self.omit:
                raise Exception("Do not set omit on add_src_hash fields")
            if not (self.index and self.indexunique):
                raise Exception("add_src_hash fields require index, "
                                "indexunique")


class DataDictionary(object):
    def __init__(self):
        self.rows = []

    def read_from_file(self, filename, check_against_source_db=True):
        self.rows = []
        with open(filename, 'rb') as tsvfile:
            tsv = csv.reader(tsvfile, delimiter='\t')
            headerlist = tsv.next()
            if headerlist != DataDictionaryRow.ROWNAMES:
                raise Exception(
                    "Bad data dictionary file. Must be a tab-separated value "
                    "(TSV) file with the following row headings:\n" +
                    "\n".join(DataDictionaryRow.ROWNAMES)
                )
            logger.debug("Data dictionary has correct header.")
            for rowelements in tsv:
                ddr = DataDictionaryRow()
                ddr.set_from_elements(rowelements)
                self.rows.append(ddr)
        self.check_valid(check_against_source_db)

    def read_from_source_databases(self):
        logger.info("Reading information for draft data dictionary")
        for pretty_dbname, db in config.sources.iteritems():
            schema = db.get_schema()
            logger.info("... database nice name = {}, schema = {}".format(
                pretty_dbname, schema))
            if db.db_flavour == rnc_db.DatabaseSupporter.FLAVOUR_MYSQL:
                sql = """
                    SELECT table_name, column_name, data_type, column_type,
                        column_comment
                    FROM information_schema.columns
                    WHERE table_schema=?
                """
            else:
                sql = """
                    SELECT table_name, column_name, data_type, column_type,
                        NULL
                    FROM information_schema.columns
                    WHERE table_schema=?
                """
            args = [schema]
            rows = db.fetchall(sql, *args)
            for r in rows:
                t = r[0]
                f = r[1]
                datatype_short = r[2].upper()
                datatype_full = r[3].upper()
                c = r[4]
                dd = DataDictionaryRow()
                dd.set_from_src_db_info(pretty_dbname, t, f, datatype_short,
                                        datatype_full, c)
                already_exists = False
                for other in self.rows:
                    if (dd.src_db == other.src_db
                            and dd.src_table == other.src_table
                            and dd.src_field == other.src_field):
                        already_exists = True
                        break
                if not already_exists:
                    self.rows.append(dd)

    def cache_stuff(self):
        logger.debug("Caching data dictionary information...")
        self.cached_dest_tables = self._get_dest_tables()
        self.cached_source_databases = self._get_source_databases()
        self.cached_src_tables = {}
        self.cached_src_tables_with_patient_info = {}
        self.cached_patient_src_tables_with_active_destination = {}
        for d in self.cached_source_databases:
            self.cached_src_tables[d] = self._get_src_tables(d)
            self.cached_src_tables_with_patient_info[d] = (
                self._get_src_tables_with_patient_info(d)
            )
            self.cached_patient_src_tables_with_active_destination[d] = (
                self._get_patient_src_tables_with_active_dest(d)
            )
        self.cached_scrub_from_rows = self._get_scrub_from_rows()

    def check_valid(self, check_against_source_db):
        logger.debug("Checking data dictionary...")
        if not self.rows:
            raise Exception("Empty data dictionary")

        # Remove tables that are entirely redundant
        skiptables = []
        for t in self._get_dest_tables():
            ddr = self.get_rows_for_dest_table(t)
            if all([(r.omit and not r.scrubsrc_patient
                     and not r.scrubsrc_thirdparty) for r in ddr]):
                skiptables.append(t)
        self.rows = [r for r in self.rows
                     if not r.dest_table in skiptables]
        if not self.rows:
            raise Exception("Empty data dictionary after removing "
                            "redundant tables")
        self.cache_stuff()

        # Check individual rows
        for r in self.rows:
            r.check_valid()
        # Now check collective consistency

        logger.debug("Checking DD: destination tables...")
        for t in self.get_dest_tables():
            sdt = self.get_src_dbs_tables_for_dest_table(t)
            if len(sdt) > 1:
                raise Exception(
                    "Destination table {t} is mapped to by multiple "
                    "source databases: {s}".format(
                        t=t,
                        s=", ".join(["{}.{}".format(s[0], s[1]) for s in sdt]),
                    )
                )

        if check_against_source_db:
            logger.debug("Checking DD: source tables...")
            for d in self.get_source_databases():
                db = config.sources[d]
                for t in self.get_src_tables(d):

                    dt = self.get_dest_tables_for_src_db_table(d, t)
                    if len(dt) > 1:
                        raise Exception(
                            "Source table {d}.{t} maps to >1 destination "
                            "table: {dt}".format(
                                d=d,
                                t=t,
                                dt=", ".join(dt),
                            )
                        )

                    rows = self.get_rows_for_src_table(d, t)
                    if any([r.scrub_in or r.master_pid
                            for r in rows if not r.omit]):
                        fieldnames = self.get_fieldnames_for_src_table(d, t)
                        if not config.per_table_patient_id_field in fieldnames:
                            raise Exception(
                                "Source table {d}.{t} has a scrub_in or "
                                "master_pid field but no {p} field".format(
                                    d=d,
                                    t=t,
                                    p=config.per_table_patient_id_field,
                                )
                            )

                    n_pks = sum([1 if x.src_pk else 0 for x in rows])
                    if n_pks > 1:
                        raise Exception(
                            "Table {d}.{t} has >1 src_pk set".format(d=d, t=t))

                    if not db.table_exists(t):
                        raise Exception(
                            "Table {t} missing from source database "
                            "{d}".format(
                                t=t,
                                d=d
                            )
                        )

        logger.debug("Checking DD: global checks...")
        n_definers = sum([1 if x.defines_primary_pids else 0
                          for x in self.rows])
        if n_definers == 0:
            raise Exception("Must have at least one field with "
                            "'defines_primary_pids' set.")
        if n_definers > 1:
            logger.warning("Unusual: >1 field with "
                           "defines_primary_pids set.")

    def _get_dest_tables(self):
        return list(set([ddr.dest_table for ddr in self.rows
                         if ddr.dest_table
                         and not ddr.omit]))

    def get_dest_tables(self):
        return self.cached_dest_tables

    def get_dest_tables_for_src_db_table(self, src_db, src_table):
        return list(set([ddr.dest_table for ddr in self.rows
                         if ddr.src_db == src_db
                         and ddr.src_table == src_table
                         and not ddr.omit]))

    def _get_source_databases(self):
        return list(set([ddr.src_db for ddr in self.rows]))

    def get_source_databases(self):
        return self.cached_source_databases

    def get_src_dbs_tables_for_dest_table(self, dest_table):
        return list(set([
            (ddr.src_db, ddr.src_table)
            for ddr in self.rows
            if ddr.dest_table == dest_table
        ]))

    def _get_src_tables(self, src_db):
        return list(set([ddr.src_table for ddr in self.rows
                         if ddr.src_db == src_db]))

    def get_src_tables(self, src_db):
        return self.cached_src_tables[src_db]

    def _get_patient_src_tables_with_active_dest(self, src_db):
        potential_tables = self._get_src_tables_with_patient_info(
            src_db)
        tables = []
        for t in potential_tables:
            ddrows = self.get_rows_for_src_table(src_db, t)
            if any(not ddr.omit for ddr in ddrows):
                tables.append(t)
        return tables

    def get_patient_src_tables_with_active_dest(self, src_db):
        return self.cached_patient_src_tables_with_active_destination[
            src_db]

    def get_src_tables_with_no_patient_info(self, src_db):
        potential_tables = self.get_src_tables(src_db)
        tables = []
        for t in potential_tables:
            if any([ddr.primary_pid or ddr.master_pid
                    for ddr in self.get_rows_for_src_table(src_db, t)]):
                continue
            tables.append(t)
        return tables

    def _get_src_tables_with_patient_info(self, src_db):
        potential_tables = self.get_src_tables(src_db)
        tables = []
        for t in potential_tables:
            if not any([ddr.primary_pid or ddr.master_pid
                        for ddr in self.get_rows_for_src_table(
                            src_db, t)]):
                continue
            tables.append(t)
        return tables

    def get_src_tables_with_patient_info(self, src_db):
        return self.cached_src_tables_with_patient_info[src_db]

    def get_rows_for_src_table(self, src_db, src_table):
        return [ddr for ddr in self.rows
                if ddr.src_db == src_db
                and ddr.src_table == src_table]

    def get_rows_for_dest_table(self, dest_table):
        return [ddr for ddr in self.rows
                if ddr.dest_table == dest_table]

    def get_fieldnames_for_src_table(self, src_db, src_table):
        return [ddr.src_field for ddr in self.rows
                if ddr.src_db == src_db
                and ddr.src_table == src_table]

    def _get_scrub_from_rows(self):
        return [ddr for ddr in self.rows
                if (ddr.scrubsrc_patient
                    or ddr.scrubsrc_thirdparty)]
        # ... even if omit flag set

    def get_scrub_from_rows(self):
        return self.cached_scrub_from_rows

    def get_tsv(self):
        return "\n".join(
            ["\t".join(DataDictionaryRow.ROWNAMES)]
            + [r.get_tsv() for r in self.rows]
        )

    def get_src_dbs_tables_with_no_patient_info(self):
        db_table_tuple_list = []
        for db in self.get_source_databases():
            for t in self.get_src_tables(db):
                if any([ddr.primary_pid or ddr.master_pid
                        for ddr in self.get_rows_for_src_table(db, t)]):
                    continue
            db_table_tuple_list.append((db, t))
        return db_table_tuple_list

    def get_srchash_info(self, src_db, src_table):
        dest_table = None
        src_pk = None
        dest_pk = None
        src_hash = False
        ddrows = self.get_rows_for_src_table(src_db, src_table)
        for ddr in ddrows:
            if not dest_table:
                dest_table = ddr.dest_table
            if ddr.src_pk:
                src_pk = ddr.src_field
                dest_pk = ddr.dest_field
                src_hash = ddr.add_src_hash
        return (src_pk, src_hash, dest_table, dest_pk)

    def has_active_destination(self, src_db, src_table):
        ddrows = self.get_rows_for_src_table(src_db, src_table)
        return any([not x.omit for x in ddrows])


# =============================================================================
# Config/databases
# =============================================================================

def read_config_string_options(obj, parser, section, options,
                               enforce_str=False):
    if not parser.has_section(section):
        raise Exception("config missing section: " + section)
    for o in options:
        if parser.has_option(section, o):
            value = parser.get(section, o)
            enforce_str
            setattr(obj, o, str(value) if enforce_str else value)
        else:
            setattr(obj, o, None)


class DatabaseConfig(object):
    def __init__(self, parser, section):
        read_config_string_options(self, parser, section, [
            "engine",
            "host",
            "port",
            "user",
            "password",
            "db",
        ])
        self.port = int(self.port)
        self.check_valid(section)

    def check_valid(self, section):
        if not self.engine:
            raise Exception(
                "Database {} doesn't specify engine".format(section))
        self.engine = self.engine.lower()
        if self.engine not in ["mysql", "sqlserver"]:
            raise Exception("Unknown database engine: {}".format(self.engine))
        if self.engine == "mysql":
            if (not self.host or not self.port or not self.user or not
                    self.password or not self.db):
                raise Exception("Missing MySQL details")
        elif self.engine == "sqlserver":
            if (not self.host or not self.user or not
                    self.password or not self.db):
                raise Exception("Missing SQL Server details")


def get_database(dbc):
    db = rnc_db.DatabaseSupporter()
    logger.info(
        "Opening database: host={h}, port={p}, db={d}, user={u}".format(
            h=dbc.host,
            p=dbc.port,
            d=dbc.db,
            u=dbc.user,
        )
    )
    if dbc.engine == "mysql":
        db.connect_to_database_mysql(
            server=dbc.host,
            port=dbc.port,
            database=dbc.db,
            user=dbc.user,
            password=dbc.password,
            autocommit=False  # NB therefore need to commit
        )
    elif dbc.engine == "sqlserver":
        db.connect_to_database_odbc_sqlserver(
            database=dbc.db,
            user=dbc.user,
            password=dbc.password,
            server=dbc.host,
            autocommit=False
        )
    return db


def ensure_valid_field_name(f):
    if not is_valid_field_name(f):
        raise Exception("Field name invalid: {}".format(f))


def ensure_valid_table_name(f):
    if not is_valid_table_name(f):
        raise Exception("Table name invalid: {}".format(f))


# =============================================================================
# DestinationFieldInfo
# =============================================================================

class DestinationFieldInfo(object):
    def __init__(self, table, field, fieldtype, comment):
        self.table = table
        self.field = field
        self.fieldtype = fieldtype
        self.comment = comment

    def __str__(self):
        return "table={}, field={}, fieldtype={}, comment={}".format(
            self.table, self.field, self.fieldtype, self.comment
        )


# =============================================================================
# Config
# =============================================================================

class Config(object):
    MAIN_HEADINGS = [
        "data_dictionary_filename",
        "per_table_patient_id_field",
        "master_pid_fieldname",
        "per_table_patient_id_encryption_phrase",
        "master_patient_id_encryption_phrase",
        "change_detection_encryption_phrase",
        "replace_patient_info_with",
        "replace_third_party_info_with",
        "scrub_string_suffixes",
        "string_max_regex_errors",
        "anonymise_dates_at_word_boundaries_only",
        "anonymise_numbers_at_word_boundaries_only",
        "anonymise_strings_at_word_boundaries_only",
        "research_id_fieldname",
        "source_hash_fieldname",
        "date_to_text_format",
        "datetime_to_text_format",
        "append_source_info_to_comment",
        "source_databases",
    ]

    def __init__(self):
        self.config_filename = None
        for x in Config.MAIN_HEADINGS:
            setattr(self, x, None)
        self.report_every_n_rows = 100
        self.PERSISTENT_CONSTANTS_INITIALIZED = False
        self.DESTINATION_FIELDS_LOADED = False
        self.destfieldinfo = []

    def set(self, filename=None, environ=None, include_sources=True,
            load_dd=True, load_destfields=True):
        """Set up process-local storage from the incoming environment (which
        may be very fast if already cached) and ensure we have an active
        database connection."""
        # 1. Set up process-local storage
        self.set_internal(filename, environ, include_sources=include_sources,
                          load_dd=load_dd)
        if load_destfields:
            self.load_destination_fields()
        # 2. Ping MySQL connection, to reconnect if it's timed out.
        self.admindb.ping()
        self.destdb.ping()
        for db in self.sources.values():
            db.ping()

    def set_internal(self, filename=None, environ=None, include_sources=True,
                     load_dd=True):
        self.set_always()
        if self.PERSISTENT_CONSTANTS_INITIALIZED:
            return
        logger.info(SEP + "Loading config")
        if filename and environ:
            raise Exception("Config.set(): mis-called")
        if environ:
            self.read_environ(environ)
        else:
            self.read_environ(os.environ)
            self.config_filename = filename
        self.read_config(include_sources=include_sources)
        self.check_valid(include_sources=include_sources)
        self.dd = DataDictionary()
        if load_dd:
            logger.info(SEP + "Loading data dictionary")
            self.dd.read_from_file(config.data_dictionary_filename,
                                   check_against_source_db=include_sources)
        self.PERSISTENT_CONSTANTS_INITIALIZED = True

    def set_always(self):
        """Set the things we set every time the script is invoked (time!)."""
        localtz = dateutil.tz.tzlocal()
        self.NOW_LOCAL_TZ = datetime.datetime.now(localtz)
        self.NOW_UTC_WITH_TZ = self.NOW_LOCAL_TZ.astimezone(pytz.utc)
        self.NOW_UTC_NO_TZ = self.NOW_UTC_WITH_TZ.replace(tzinfo=None)
        self.NOW_LOCAL_TZ_ISO8601 = self.NOW_LOCAL_TZ.strftime(
            DATEFORMAT_ISO8601)
        self.TODAY = datetime.date.today()  # fetches the local date

    def read_environ(self, environ):
        self.remote_addr = environ.get("REMOTE_ADDR", "")
        self.remote_port = environ.get("REMOTE_PORT", "")
        self.SCRIPT_NAME = environ.get("SCRIPT_NAME", "")
        self.SERVER_NAME = environ.get("SERVER_NAME", "")

        # Reconstruct URL:
        # http://www.python.org/dev/peps/pep-0333/#url-reconstruction
        url = environ.get("wsgi.url_scheme", "") + "://"
        if environ.get("HTTP_HOST"):
            url += environ.get("HTTP_HOST")
        else:
            url += environ.get("SERVER_NAME", "")
        if environ.get("wsgi.url_scheme") == "https":
            if environ.get("SERVER_PORT") != "443":
                url += ':' + environ.get("SERVER_PORT", "")
        else:
            if environ.get("SERVER_PORT") != "80":
                url += ':' + environ.get("SERVER_PORT", "")
        url += urllib.quote(environ.get("SCRIPT_NAME", ""))
        url += urllib.quote(environ.get("PATH_INFO", ""))
        # But not the query string:
        # if environ.get("QUERY_STRING"):
        #    url += "?" + environ.get("QUERY_STRING")
        self.SCRIPT_PUBLIC_URL_ESCAPED = cgi.escape(url)

    def read_config(self, include_sources=False):
        """Read config from file."""
        parser = ConfigParser.RawConfigParser()
        parser.readfp(codecs.open(self.config_filename, "r", "utf8"))
        read_config_string_options(self, parser, "main", Config.MAIN_HEADINGS)
        # Processing of parameters
        if self.scrub_string_suffixes is None:
            self.scrub_string_suffixes = ""
        self.scrub_string_suffixes = [
            x.strip() for x in self.scrub_string_suffixes.splitlines()]
        self.scrub_string_suffixes = [x for x in self.scrub_string_suffixes
                                      if x]
        self.string_max_regex_errors = int(self.string_max_regex_errors)
        convert_attrs_to_bool(self, [
            "anonymise_dates_at_word_boundaries_only",
            "anonymise_numbers_at_word_boundaries_only",
            "anonymise_strings_at_word_boundaries_only",
            "append_source_info_to_comment",
        ])
        # Databases
        self.destdb_config = DatabaseConfig(parser, "destination_database")
        self.destdb = get_database(self.destdb_config)
        self.admindb_config = DatabaseConfig(parser, "admin_database")
        self.admindb = get_database(self.admindb_config)
        self.src_db_configs = []
        self.sources = {}
        self.src_db_names = []
        for sourcedb_name in [x.strip()
                              for x in self.source_databases.splitlines()]:
            if not sourcedb_name:
                continue
            self.src_db_names.append(sourcedb_name)
            if not include_sources:
                continue
            try:  # guard this bit to prevent any password leakage
                dbc = DatabaseConfig(parser, sourcedb_name)
                self.src_db_configs.append(dbc)
                db = get_database(dbc)
                self.sources[sourcedb_name] = db
            except:
                raise rnc_db.NoDatabaseError(
                    "Problem opening or reading from database {}; details "
                    "concealed for security reasons".format(sourcedb_name))
            finally:
                dbc = None
        # Hashers
        self.primary_pid_hasher = None
        self.master_pid_hasher = None
        self.change_detection_hasher = None

    def check_valid(self, include_sources=False):
        """Raise exception if config is invalid."""

        # Test databases
        if include_sources:
            if not self.sources:
                raise Exception("No source databases specified.")
        if not self.destdb:
            raise Exception("No destination database specified.")
        if not self.admindb:
            raise Exception("No admin database specified.")

        # Test field names
        if not self.per_table_patient_id_field:
            raise Exception("Blank fieldname: per_table_patient_id_field")
        ensure_valid_field_name(self.per_table_patient_id_field)

        if not self.research_id_fieldname:
            raise Exception("Blank fieldname: research_id_fieldname")
        ensure_valid_field_name(self.research_id_fieldname)

        if self.master_pid_fieldname:
            ensure_valid_field_name(self.master_pid_fieldname)

        if self.source_hash_fieldname:
            ensure_valid_field_name(self.source_hash_fieldname)

        if self.per_table_patient_id_field == self.source_hash_fieldname:
            raise Exception("Config: per_table_patient_id_field can't be the "
                            "same as source_hash_fieldname")
        if self.research_id_fieldname == self.source_hash_fieldname:
            raise Exception("Config: research_id_fieldname can't be the "
                            "same as source_hash_fieldname")

        # Test strings
        if not self.replace_patient_info_with:
            raise Exception("Blank replace_patient_info_with")
        if not self.replace_third_party_info_with:
            raise Exception("Blank replace_third_party_info_with")
        if (self.replace_patient_info_with ==
                self.replace_third_party_info_with):
            raise Exception("Inadvisable: replace_patient_info_with == "
                            "replace_third_party_info_with")

        # Regex
        if self.string_max_regex_errors < 0:
            raise Exception("string_max_regex_errors < 0, nonsensical")

        # Test date conversions
        format_datetime(self.NOW_UTC_NO_TZ, self.date_to_text_format)
        format_datetime(self.NOW_UTC_NO_TZ, self.datetime_to_text_format)

        # Load encryption keys
        if not self.per_table_patient_id_encryption_phrase:
            raise Exception("Missing per_table_patient_id_encryption_phrase")
        self.primary_pid_hasher = MD5Hasher(
            self.per_table_patient_id_encryption_phrase)

        if not self.master_patient_id_encryption_phrase:
            raise Exception("Missing master_patient_id_encryption_phrase")
        self.master_pid_hasher = MD5Hasher(
            self.master_patient_id_encryption_phrase)

        if not self.change_detection_encryption_phrase:
            raise Exception("Missing change_detection_encryption_phrase")
        self.change_detection_hasher = MD5Hasher(
            self.change_detection_encryption_phrase)

        # OK!
        logger.debug("Config validated.")

    def encrypt_primary_pid(self, pid):
        return self.primary_pid_hasher.hash(pid)

    def encrypt_master_pid(self, pid):
        return self.master_pid_hasher.hash(pid)

    def hash_list(self, l):
        """ Hashes a list with Python's built-in hash function.
        We could use Python's build-in hash() function, which produces a 64-bit
        unsigned integer (calculated from: sys.maxint).
        However, there is an outside chance that someone uses a single-field
        table and therefore that this is vulnerable to content discovery via a
        dictionary attack. Thus, we should use a better version.
        """
        return self.change_detection_hasher.hash(repr(l))

    def hash_scrubber(self, scrubber):
        return self.change_detection_hasher.hash(scrubber.get_hash_string())

    def load_destination_fields(self, force=False):
        if self.DESTINATION_FIELDS_LOADED and not force:
            return
        # Everything that was in the data dictionary should now be in the
        # destination, commented... so just process actual destination fields,
        # which will encompass all oddities including NLP fields.
        for t in self.destdb.get_all_table_names():
            for c in self.destdb.fetch_column_names(t):
                fieldtype = self.destdb.get_column_type(t, c)
                comment = self.destdb.get_comment(t, c)
                dfi = DestinationFieldInfo(t, c, fieldtype, comment)
                self.destfieldinfo.append(dfi)
        self.DESTINATION_FIELDS_LOADED = True


# =============================================================================
# Config instance, as process-local storage
# =============================================================================

config = Config()


# =============================================================================
# Logger manipulation
# =============================================================================

def reset_logformat(logger, name="", debug=False):
    # logging.basicConfig() won't reset the formatter if another module
    # has called it, so always set the formatter like this.
    if name:
        namebit = name + ":"
    else:
        namebit = ""
    fmt = "%(levelname)s:%(name)s:" + namebit + "%(message)s"
    rnc_log.reset_logformat(logger, fmt=fmt)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)


# =============================================================================
# Audit
# =============================================================================

AUDIT_TABLE = "audit"
AUDIT_FIELDSPECS = [
    dict(name="id", sqltype="INT UNSIGNED", pk=True, autoincrement=True,
         comment="Arbitrary primary key"),
    dict(name="when_access_utc", sqltype="DATETIME", notnull=True,
         comment="Date/time of access (UTC)", indexed=True),
    dict(name="source", sqltype="VARCHAR(20)", notnull=True,
         comment="Source (e.g. tablet, webviewer)"),
    dict(name="remote_addr",
         sqltype="VARCHAR(45)",  # http://stackoverflow.com/questions/166132
         comment="IP address of the remote computer"),
    dict(name="user", sqltype="VARCHAR(255)",
         comment="User name, where applicable"),
    dict(name="query", sqltype="TEXT",
         comment="SQL query (with arguments)"),
    dict(name="details", sqltype="TEXT",
         comment="Details of the access"),
]


def audit(details,
          from_console=False, remote_addr=None, user=None, query=None):
    """Write an entry to the audit log."""
    if not remote_addr:
        remote_addr = config.session.ip_address if config.session else None
    if not user:
        user = config.session.user if config.session else None
    if from_console:
        source = "console"
    else:
        source = "webviewer"
    config.admindb.db_exec(
        """
            INSERT INTO {table}
                (when_access_utc, source, remote_addr, user, query, details)
            VALUES
                (?,?,?,?,?,?)
        """.format(table=AUDIT_TABLE),
        config.NOW_UTC_NO_TZ,  # when_access_utc
        source,
        remote_addr,
        user,
        query,
        details
    )
