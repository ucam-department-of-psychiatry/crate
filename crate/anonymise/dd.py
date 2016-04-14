#!/usr/bin/env python3
# crate/anonymise/anon_dd.py

"""
Data dictionary classes for CRATE anonymiser.

Data dictionary as a TSV file, for ease of editing by multiple authors, rather
than a database table.

Author: Rudolf Cardinal
Created at: 18 Feb 2015
Last update: 22 Nov 2015

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

# =============================================================================
# Imports
# =============================================================================

import csv
import logging
import operator
from sortedcontainers import SortedSet  # sudo pip install sortedcontainers

import cardinal_pythonlib.rnc_db as rnc_db
from cardinal_pythonlib.rnc_db import (
    does_sqltype_merit_fulltext_index,
    does_sqltype_require_index_len,
    ensure_valid_field_name,
    ensure_valid_table_name,
    is_sqltype_binary,
    is_sqltype_date,
    is_sqltype_integer,
    is_sqltype_numeric,
    is_sqltype_text_over_one_char,
    is_sqltype_text_of_length_at_least,
    is_sqltype_valid,
)
from cardinal_pythonlib.rnc_lang import (
    convert_attrs_to_bool,
    convert_attrs_to_int,
    convert_attrs_to_uppercase,
    count_bool,
    raise_if_attr_blank,
)

from crate.anonymise.constants import (
    ALTERMETHOD,
    DEFAULT_INDEX_LEN,
    INDEX,
    LONGTEXT,
    ODD_CHARS_TRANSLATE,
    SCRUBMETHOD,
    SCRUBSRC,
    SRCFLAG,
)

log = logging.getLogger(__name__)


# =============================================================================
# DataDictionaryRow
# =============================================================================

class DataDictionaryRow(object):
    """
    Class representing a single row of a data dictionary.
    """
    ROWNAMES = [
        "src_db",
        "src_table",
        "src_field",
        "src_datatype",
        "src_flags",

        "scrub_src",
        "scrub_method",

        "omit",
        "alter_method",

        "dest_table",
        "dest_field",
        "dest_datatype",
        "index",
        "indexlen",
        "comment",
    ]

    def __init__(self, config=None):
        """
        Set up basic defaults.
        """
        self.config = config

        for x in DataDictionaryRow.ROWNAMES:
            setattr(self, x, None)
        self._signature = None
        self._from_file = False
        # For alter_method:
        self._scrub = False
        self._truncate_date = False
        self._extract_text = False
        self._extract_from_filename = False
        self._extract_ext_field = ""

    def __lt__(self, other):
        return self.get_signature() < other.get_signature()

    def alter_method_to_components(self):
        """
        Convert the alter_method field (from the data dictionary) to a bunch of
        boolean/simple fields.
        """
        self._scrub = False
        self._truncate_date = False
        self._extract_text = False
        self._extract_from_filename = False
        self._extract_ext_field = ""
        secondhalf = ""
        if "=" in self.alter_method:
            secondhalf = self.alter_method[self.alter_method.index("=") + 1:]
        if self.alter_method == ALTERMETHOD.TRUNCATEDATE:
            self._truncate_date = True
        elif self.alter_method.startswith(ALTERMETHOD.SCRUBIN):
            self._scrub = True
        elif self.alter_method.startswith(ALTERMETHOD.BIN2TEXT):
            self._extract_text = True
            self._extract_ext_field = secondhalf
        elif self.alter_method.startswith(ALTERMETHOD.BIN2TEXT_SCRUB):
            self._extract_text = True
            self._extract_ext_field = secondhalf
            self._scrub = True
        elif self.alter_method.startswith(ALTERMETHOD.FILENAME2TEXT):
            self._extract_text = True
            self._extract_from_filename = True
        elif self.alter_method.startswith(ALTERMETHOD.FILENAME2TEXT_SCRUB):
            self._extract_text = True
            self._extract_from_filename = True
            self._scrub = True

    def get_alter_method(self):
        """
        Return the alter_method field from the working fields.
        """
        if self._truncate_date:
            return ALTERMETHOD.TRUNCATEDATE
        if self._extract_text:
            if self._extract_ext_field:
                if self._scrub:
                    return (ALTERMETHOD.BIN2TEXT_SCRUB + "=" +
                            self._extract_ext_field)
                else:
                    return ALTERMETHOD.BIN2TEXT + "=" + self._extract_ext_field
            else:
                if self._scrub:
                    return ALTERMETHOD.FILENAME2TEXT_SCRUB
                else:
                    return ALTERMETHOD.FILENAME2TEXT
        if self._scrub:
            return ALTERMETHOD.SCRUBIN
        return ""

    def components_to_alter_method(self):
        """
        Write the alter_method field from the component (working) fields.
        """
        self.alter_method = self.get_alter_method()

    def __str__(self):
        """
        Return a string representation.
        """
        self.components_to_alter_method()
        return ", ".join(["{}: {}".format(a, getattr(self, a))
                          for a in DataDictionaryRow.ROWNAMES])

    def get_signature(self):
        """
        Return a signature based on the source database/table/field.
        """
        return "{}.{}.{}".format(self.src_db,
                                 self.src_table,
                                 self.src_field)

    def set_from_elements(self, elements):
        """
        Set internal fields from a list of elements representing a row from the
        TSV data dictionary file.
        """
        if len(elements) != len(DataDictionaryRow.ROWNAMES):
            raise ValueError("Bad data dictionary row. Values:\n" +
                             "\n".join(elements))
        for i in range(len(elements)):
            setattr(self, DataDictionaryRow.ROWNAMES[i], elements[i])
        convert_attrs_to_bool(self, [
            "omit",
        ])
        convert_attrs_to_uppercase(self, [
            "src_datatype",
            "dest_datatype",
        ])
        convert_attrs_to_int(self, [
            "indexlen"
        ])
        self._from_file = True
        self.alter_method_to_components()
        self.check_valid()

    # noinspection PyUnusedLocal
    def set_from_src_db_info(self, db, table, field, datatype_short,
                             datatype_full, cfg, comment=None,
                             default_omit=True):
        """
        Create a draft data dictionary row from a field in the source database.
        """
        # If Unicode, mangle to ASCII:
        table = table.encode("ascii", "ignore")
        field = field.encode("ascii", "ignore")
        datatype_full = datatype_full.encode("ascii", "ignore")

        self.src_db = db
        self.src_table = table
        self.src_field = field
        self.src_datatype = datatype_full

        # Is the field special, such as a PK?
        self.src_flags = ""
        if self.src_field in cfg.ddgen_pk_fields:
            self.src_flags += SRCFLAG.PK
            if cfg.ddgen_constant_content:
                self.src_flags += SRCFLAG.CONSTANT
            else:
                self.src_flags += SRCFLAG.ADDSRCHASH
            if cfg.ddgen_addition_only:
                self.src_flags += SRCFLAG.ADDITION_ONLY
        if self.src_field == cfg.ddgen_per_table_pid_field:
            self.src_flags += SRCFLAG.PRIMARYPID
        if self.src_field == cfg.ddgen_master_pid_fieldname:
            self.src_flags += SRCFLAG.MASTERPID
        if self.src_field in cfg.ddgen_pid_defining_fieldnames:  # unusual!
            self.src_flags += SRCFLAG.DEFINESPRIMARYPIDS

        # Does the field contain sensitive data?
        if (self.src_field in cfg.ddgen_scrubsrc_patient_fields or
                self.src_field == cfg.ddgen_per_table_pid_field or
                self.src_field == cfg.ddgen_master_pid_fieldname or
                self.src_field in cfg.ddgen_pid_defining_fieldnames):
            self.scrub_src = SCRUBSRC.PATIENT
        elif self.src_field in cfg.ddgen_scrubsrc_thirdparty_fields:
            self.scrub_src = SCRUBSRC.THIRDPARTY
        elif (self.src_field in cfg.ddgen_scrubmethod_code_fields or
                self.src_field in cfg.ddgen_scrubmethod_date_fields or
                self.src_field in cfg.ddgen_scrubmethod_number_fields or
                self.src_field in cfg.ddgen_scrubmethod_phrase_fields):
            # We're not sure what sort these are, but it seems conservative to
            # include these! Easy to miss them otherwise, and better to be
            # overly conservative.
            self.scrub_src = SCRUBSRC.PATIENT
        else:
            self.scrub_src = ""

        # What kind of sensitive data? Date, text, number, code?
        if not self.scrub_src:
            self.scrub_method = ""
        elif (is_sqltype_numeric(datatype_full) or
                self.src_field == cfg.ddgen_per_table_pid_field or
                self.src_field == cfg.ddgen_master_pid_fieldname or
                self.src_field in cfg.ddgen_scrubmethod_number_fields):
            self.scrub_method = SCRUBMETHOD.NUMERIC
        elif (is_sqltype_date(datatype_full) or
                self.src_field in cfg.ddgen_scrubmethod_date_fields):
            self.scrub_method = SCRUBMETHOD.DATE
        elif self.src_field in cfg.ddgen_scrubmethod_code_fields:
            self.scrub_method = SCRUBMETHOD.CODE
        elif self.src_field in cfg.ddgen_scrubmethod_phrase_fields:
            self.scrub_method = SCRUBMETHOD.PHRASE
        else:
            self.scrub_method = SCRUBMETHOD.WORDS

        # Should we omit it (at least until a human has looked at the DD)?
        self.omit = (
            (default_omit or bool(self.scrub_src)) and
            not (SRCFLAG.PK in self.src_flags) and
            not (SRCFLAG.PRIMARYPID in self.src_flags) and
            not (SRCFLAG.MASTERPID in self.src_flags)
        )

        # Do we want to change the destination fieldname?
        if SRCFLAG.PRIMARYPID in self.src_flags:
            self.dest_field = self.config.research_id_fieldname
        elif SRCFLAG.MASTERPID in self.src_flags:
            self.dest_field = self.config.master_research_id_fieldname
        else:
            self.dest_field = field
        if cfg.ddgen_convert_odd_chars_to_underscore:
            self.dest_field = str(self.dest_field)  # if this fails,
            # there's a Unicode problem
            self.dest_field = self.dest_field.translate(ODD_CHARS_TRANSLATE)
            # ... this will choke on a Unicode string

        # Do we want to change the destination field SQL type?
        self.dest_datatype = (
            self.config.SQLTYPE_ENCRYPTED_PID
            if (SRCFLAG.PRIMARYPID in self.src_flags or
                SRCFLAG.MASTERPID in self.src_flags)
            else rnc_db.full_datatype_to_mysql(datatype_full))

        # How should we manipulate the destination?
        if self.src_field in cfg.ddgen_truncate_date_fields:
            self._truncate_date = True
        elif self.src_field in cfg.ddgen_filename_to_text_fields:
            self._extract_text = True
            self._extract_from_filename = True
            self.dest_datatype = LONGTEXT
            if (self.src_field not in
                    cfg.ddgen_safe_fields_exempt_from_scrubbing):
                self._scrub = True
        elif self.src_field in cfg.bin2text_dict.keys():
            self._extract_text = True
            self._extract_from_filename = False
            self._extract_ext_field = cfg.bin2text_dict[self.src_field]
            self.dest_datatype = LONGTEXT
            if (self.src_field not in
                    cfg.ddgen_safe_fields_exempt_from_scrubbing):
                self._scrub = True
        elif (is_sqltype_text_of_length_at_least(
                datatype_full, cfg.ddgen_min_length_for_scrubbing) and
                not self.omit and
                SRCFLAG.PRIMARYPID not in self.src_flags and
                SRCFLAG.MASTERPID not in self.src_flags and
                self.src_field not in
                cfg.ddgen_safe_fields_exempt_from_scrubbing):
            self._scrub = True

        # Manipulate the destination table name?
        # http://stackoverflow.com/questions/10017147
        self.dest_table = table
        if cfg.ddgen_convert_odd_chars_to_underscore:
            self.dest_table = str(self.dest_table)  # if this fails,
            # there's a Unicode problem
            self.dest_table = self.dest_table.translate(ODD_CHARS_TRANSLATE)

        # Should we index the destination?
        if SRCFLAG.PK in self.src_flags:
            self.index = INDEX.UNIQUE
        elif (self.dest_field == self.config.research_id_fieldname or
                SRCFLAG.PRIMARYPID in self.src_flags or
                SRCFLAG.MASTERPID in self.src_flags or
                SRCFLAG.DEFINESPRIMARYPIDS in self.src_flags):
            self.index = INDEX.NORMAL
        elif (does_sqltype_merit_fulltext_index(self.dest_datatype) and
                cfg.ddgen_allow_fulltext_indexing):
            self.index = INDEX.FULLTEXT
        elif self.src_field in cfg.ddgen_index_fields:
            self.index = INDEX.NORMAL
        else:
            self.index = ""

        self.indexlen = (
            DEFAULT_INDEX_LEN
            if (does_sqltype_require_index_len(self.dest_datatype) and
                self.index != INDEX.FULLTEXT)
            else None
        )

        self.comment = comment
        self._from_file = False
        self.check_valid()

    def get_tsv(self):
        """
        Return a TSV row for writing.
        """
        values = []
        for x in DataDictionaryRow.ROWNAMES:
            v = getattr(self, x)
            if v is None:
                v = ""
            v = str(v)
            values.append(v)
        return "\t".join(values)

    def get_offender_description(self):
        offenderdest = "" if not self.omit else " -> {}.{}".format(
            self.dest_table, self.dest_field)
        return "{}.{}.{}{}".format(
            self.src_db, self.src_table, self.src_field, offenderdest)

    def check_valid(self):
        """
        Check internal validity and complain if invalid, showing the source
        of the problem.
        """
        self.components_to_alter_method()
        try:
            self._check_valid()
        except:
            log.exception(
                "Offending DD row [{}]: {}".format(
                    self.get_offender_description(), str(self)))
            raise

    def check_prohibited_fieldnames(self, fieldnames):
        if self.dest_field in fieldnames:
            log.exception(
                "Offending DD row [{}]: {}".format(
                    self.get_offender_description(), str(self)))
            raise ValueError("Prohibited dest_field name")

    def _check_valid(self):
        """
        Check internal validity and complain if invalid.
        """
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

        if self.src_db not in self.config.src_db_names:
            raise ValueError(
                "Data dictionary row references non-existent source "
                "database")
        srccfg = self.config.srccfg[self.src_db]
        ensure_valid_table_name(self.src_table)
        ensure_valid_field_name(self.src_field)
        if not is_sqltype_valid(self.src_datatype):
            raise ValueError(
                "Field has invalid source data type: {}".format(
                    self.src_datatype))

        if (self.src_field == srccfg.ddgen_per_table_pid_field and
                not is_sqltype_integer(self.src_datatype)):
            raise ValueError(
                "All fields with src_field = {} should be integer, for work "
                "distribution purposes".format(self.src_field))

        if (SRCFLAG.DEFINESPRIMARYPIDS in self.src_flags and
                SRCFLAG.PRIMARYPID not in self.src_flags):
            raise ValueError(
                "All fields with src_flags={} set must have src_flags={} "
                "set".format(
                    SRCFLAG.DEFINESPRIMARYPIDS,
                    SRCFLAG.PRIMARYPID
                ))

        if count_bool([SRCFLAG.PRIMARYPID in self.src_flags,
                       SRCFLAG.MASTERPID in self.src_flags,
                       bool(self.alter_method)]) > 1:
            raise ValueError(
                "Field can be any ONE of: src_flags={}, src_flags={}, "
                "alter_method".format(
                    SRCFLAG.PRIMARYPID,
                    SRCFLAG.MASTERPID
                ))

        valid_scrubsrc = [SCRUBSRC.PATIENT, SCRUBSRC.THIRDPARTY, ""]
        if self.scrub_src not in valid_scrubsrc:
            raise ValueError(
                "Invalid scrub_src - must be one of [{}]".format(
                    ",".join(valid_scrubsrc)))

        if (self.scrub_src and self.scrub_method and
                self.scrub_method not in SCRUBMETHOD.values()):
            raise ValueError(
                "Invalid scrub_method - must be blank or one of [{}]".format(
                    ",".join(SCRUBMETHOD.values())))

        if not self.omit:
            ensure_valid_table_name(self.dest_table)
            if self.dest_table == self.config.temporary_tablename:
                raise ValueError(
                    "Destination tables can't be named {}, as that's the "
                    "name set in the config's temporary_tablename "
                    "variable".format(self.config.temporary_tablename))
            ensure_valid_field_name(self.dest_field)
            if self.dest_field == self.config.source_hash_fieldname:
                raise ValueError(
                    "Destination fields can't be named {}, as that's the "
                    "name set in the config's source_hash_fieldname "
                    "variable".format(self.config.source_hash_fieldname))
            if not is_sqltype_valid(self.dest_datatype):
                raise ValueError(
                    "Field has invalid destination data type: "
                    "{}".format(self.dest_datatype))
            if self.src_field == srccfg.ddgen_per_table_pid_field:
                if SRCFLAG.PRIMARYPID not in self.src_flags:
                    raise ValueError(
                        "All fields with src_field={} used in output should "
                        "have src_flag={} set".format(self.src_field,
                                                      SRCFLAG.PRIMARYPID))
                if self.dest_field != self.config.research_id_fieldname:
                    raise ValueError(
                        "Primary PID field should have "
                        "dest_field = {}".format(
                            self.config.research_id_fieldname))
            if (self.src_field == srccfg.ddgen_master_pid_fieldname and
                    SRCFLAG.MASTERPID not in self.src_flags):
                raise ValueError(
                    "All fields with src_field = {} used in output should have"
                    " src_flags={} set".format(
                        srccfg.ddgen_master_pid_fieldname,
                        SRCFLAG.MASTERPID))

            if self._truncate_date:
                if not (is_sqltype_date(self.src_datatype) or
                        is_sqltype_text_over_one_char(self.src_datatype)):
                    raise ValueError("Can't set truncate_date for non-date/"
                                     "non-text field")
            if self._extract_text:
                if self._extract_from_filename:
                    if not is_sqltype_text_over_one_char(self.src_datatype):
                        raise ValueError(
                            "For alter_method = {ALTERMETHOD.FILENAME2TEXT} or"
                            " {ALTERMETHOD.FILENAME2TEXT_SCRUB}, source field "
                            "must contain filename and therefore must be text "
                            "type of >1 character".format(
                                ALTERMETHOD=ALTERMETHOD))
                else:
                    if not is_sqltype_binary(self.src_datatype):
                        raise ValueError(
                            "For alter_method = {ALTERMETHOD.BIN2TEXT} or "
                            "{ALTERMETHOD.BIN2TEXT_SCRUB}, source field "
                            "must be of binary type".format(
                                ALTERMETHOD=ALTERMETHOD))
                    if not self._extract_ext_field:
                        raise ValueError(
                            "For alter_method = {ALTERMETHOD.BIN2TEXT} or "
                            "{ALTERMETHOD.BIN2TEXT_SCRUB}, must also specify "
                            "field containing extension (or filename with "
                            "extension) in the alter_method parameter".format(
                                ALTERMETHOD=ALTERMETHOD))
            if self._scrub and not self._extract_text:
                if not is_sqltype_text_over_one_char(self.src_datatype):
                    raise ValueError("Can't scrub in non-text field or "
                                     "single-character text field")

            if ((SRCFLAG.PRIMARYPID in self.src_flags or
                 SRCFLAG.MASTERPID in self.src_flags) and
                    self.dest_datatype != self.config.SQLTYPE_ENCRYPTED_PID):
                raise ValueError(
                    "All src_flags={}/src_flags={} fields used in output must "
                    "have destination_datatype = {}".format(
                        SRCFLAG.PRIMARYPID,
                        SRCFLAG.MASTERPID,
                        self.config.SQLTYPE_ENCRYPTED_PID))

            valid_index = [INDEX.NORMAL, INDEX.UNIQUE, INDEX.FULLTEXT, ""]
            if self.index not in valid_index:
                raise ValueError("Index must be one of: [{}]".format(
                    ",".join(valid_index)))

            if (self.index in [INDEX.NORMAL, INDEX.UNIQUE] and
                    self.indexlen is None and
                    does_sqltype_require_index_len(self.dest_datatype)):
                raise ValueError(
                    "Must specify indexlen to index a TEXT or BLOB field")

        if SRCFLAG.ADDSRCHASH in self.src_flags:
            if SRCFLAG.PK not in self.src_flags:
                raise ValueError(
                    "src_flags={} can only be set on "
                    "src_flags={} fields".format(
                        SRCFLAG.ADDSRCHASH,
                        SRCFLAG.PK))
            if self.omit:
                raise ValueError(
                    "Do not set omit on src_flags={} fields".format(
                        SRCFLAG.ADDSRCHASH))
            if self.index != INDEX.UNIQUE:
                raise ValueError(
                    "src_flags={} fields require index=={}".format(
                        SRCFLAG.ADDSRCHASH,
                        INDEX.UNIQUE))
            if SRCFLAG.CONSTANT in self.src_flags:
                raise ValueError(
                    "cannot mix {} flag with {} flag".format(
                        SRCFLAG.ADDSRCHASH,
                        SRCFLAG.CONSTANT))

        if SRCFLAG.CONSTANT in self.src_flags:
            if SRCFLAG.PK not in self.src_flags:
                raise ValueError(
                    "src_flags={} can only be set on "
                    "src_flags={} fields".format(
                        SRCFLAG.CONSTANT,
                        SRCFLAG.PK))
            if self.omit:
                raise ValueError(
                    "Do not set omit on src_flags={} fields".format(
                        SRCFLAG.CONSTANT))
            if self.index != INDEX.UNIQUE:
                raise ValueError(
                    "src_flags={} fields require index=={}".format(
                        SRCFLAG.CONSTANT,
                        INDEX.UNIQUE))


# =============================================================================
# DataDictionary
# =============================================================================

class DataDictionary(object):
    """
    Class representing an entire data dictionary.
    """

    def __init__(self, config):
        """
        Set defaults.
        """
        self.config = config

        self.rows = []
        self.cached_srcdb_table_pairs = SortedSet()

    def read_from_file(self, filename):
        """
        Read DD from file.
        """
        self.rows = []
        log.debug("Opening data dictionary: {}".format(filename))
        with open(filename, 'r') as tsvfile:
            tsv = csv.reader(tsvfile, delimiter='\t')
            headerlist = next(tsv)
            if headerlist != DataDictionaryRow.ROWNAMES:
                raise ValueError(
                    "Bad data dictionary file. Must be a tab-separated value "
                    "(TSV) file with the following row headings:\n" +
                    "\n".join(DataDictionaryRow.ROWNAMES)
                )
            log.debug("Data dictionary has correct header. Loading content...")
            for rowelements in tsv:
                ddr = DataDictionaryRow(self.config)
                ddr.set_from_elements(rowelements)
                self.rows.append(ddr)
            log.debug("... content loaded.")
        self.cache_stuff()

    # noinspection PyProtectedMember
    def read_from_source_databases(self, report_every=100,
                                   default_omit=True):
        """
        Create a draft DD from a source database.
        """
        log.info("Reading information for draft data dictionary")
        for pretty_dbname, db in self.config.sources.items():
            cfg = self.config.srccfg[pretty_dbname]
            schema = db.get_schema()
            log.info("... database nice name = {}, schema = {}".format(
                pretty_dbname, schema))
            if db.is_sqlserver():
                sql = """
                    SELECT table_name, column_name, data_type, {}, NULL
                    FROM information_schema.columns
                    WHERE table_schema=?
                """.format(rnc_db.SQLServer.column_type_expr())
            else:
                sql = """
                    SELECT table_name, column_name, data_type, column_type,
                        column_comment
                    FROM information_schema.columns
                    WHERE table_schema=?
                """
            args = [schema]
            i = 0
            signatures = []
            for r in db.gen_fetchall(sql, *args):
                i += 1
                if report_every and i % report_every == 0:
                    log.debug("... reading source field {}".format(i))
                t = r[0]
                f = r[1]
                datatype_short = r[2].upper()
                datatype_full = r[3].upper()
                c = r[4]
                if cfg.ddgen_force_lower_case:
                    t = t.lower()
                    f = f.lower()
                if (t in cfg.ddgen_table_blacklist or
                        f in cfg.ddgen_field_blacklist):
                    continue
                ddr = DataDictionaryRow()
                ddr.set_from_src_db_info(
                    pretty_dbname, t, f, datatype_short,
                    datatype_full,
                    cfg=cfg,
                    comment=c,
                    default_omit=default_omit)
                sig = ddr.get_signature()
                if sig not in signatures:
                    self.rows.append(ddr)
                    signatures.append(sig)
        log.info("... done")
        self.cache_stuff()
        log.info("Revising draft data dictionary")
        for ddr in self.rows:
            if ddr._from_file:
                continue
            # Don't scrub_in non-patient tables
            if (ddr.src_table
                    not in self.cached_src_tables_w_pt_info[ddr.src_db]):
                ddr._scrub = False
                ddr.components_to_alter_method()
        log.info("... done")
        log.info("Sorting draft data dictionary")
        self.rows = sorted(self.rows,
                           key=operator.attrgetter("src_db",
                                                   "src_table",
                                                   "src_field"))
        log.info("... done")

    def cache_stuff(self):
        """
        Cache DD information from various perspectives for performance and
        simplicity during actual processing.
        """
        log.debug("Caching data dictionary information...")
        self.cached_dest_tables = SortedSet()
        self.cached_dest_tables_w_pt_info = SortedSet()
        self.cached_source_databases = SortedSet()
        self.cached_srcdb_table_pairs = SortedSet()
        self.cached_srcdb_table_pairs_w_pt_info = SortedSet()  # w = with
        self.cached_scrub_from_db_table_pairs = SortedSet()
        self.cached_scrub_from_rows = {}
        self.cached_src_tables = {}
        self.cached_src_tables_w_pt_info = {}  # w = with
        src_tables_with_dest = {}
        self.cached_pt_src_tables_w_dest = {}
        self.cached_rows_for_src_table = {}
        self.cached_rows_for_dest_table = {}
        self.cached_fieldnames_for_src_table = {}
        self.cached_src_dbtables_for_dest_table = {}
        self.cached_pk_ddr = {}
        self.cached_has_active_destination = {}
        self.cached_dest_tables_for_src_db_table = {}
        self.cached_srcdb_table_pairs_to_int_pk = {}  # (db, table): pkname
        for ddr in self.rows:

            # Database-oriented maps
            if ddr.src_db not in self.cached_src_tables:
                self.cached_src_tables[ddr.src_db] = SortedSet()
            if ddr.src_db not in self.cached_pt_src_tables_w_dest:
                self.cached_pt_src_tables_w_dest[ddr.src_db] = SortedSet()
            if ddr.src_db not in self.cached_src_tables_w_pt_info:
                self.cached_src_tables_w_pt_info[ddr.src_db] = SortedSet()
            if ddr.src_db not in src_tables_with_dest:
                src_tables_with_dest[ddr.src_db] = SortedSet()

            # (Database + table)-oriented maps
            db_t_key = (ddr.src_db, ddr.src_table)
            if db_t_key not in self.cached_rows_for_src_table:
                self.cached_rows_for_src_table[db_t_key] = SortedSet()
            if db_t_key not in self.cached_fieldnames_for_src_table:
                self.cached_fieldnames_for_src_table[db_t_key] = SortedSet()
            if db_t_key not in self.cached_dest_tables_for_src_db_table:
                self.cached_dest_tables_for_src_db_table[db_t_key] = \
                    SortedSet()
            if db_t_key not in self.cached_scrub_from_rows:
                self.cached_scrub_from_rows[db_t_key] = SortedSet()

            # Destination table-oriented maps
            if ddr.dest_table not in self.cached_src_dbtables_for_dest_table:
                self.cached_src_dbtables_for_dest_table[ddr.dest_table] = \
                    SortedSet()
            if ddr.dest_table not in self.cached_rows_for_dest_table:
                self.cached_rows_for_dest_table[ddr.dest_table] = SortedSet()

            # Regardless...
            self.cached_rows_for_src_table[db_t_key].add(ddr)
            self.cached_fieldnames_for_src_table[db_t_key].add(ddr.src_field)
            self.cached_srcdb_table_pairs.add(db_t_key)
            self.cached_src_dbtables_for_dest_table[ddr.dest_table].add(
                db_t_key)
            self.cached_rows_for_dest_table[ddr.dest_table].add(ddr)

            if db_t_key not in self.cached_has_active_destination:
                self.cached_has_active_destination[db_t_key] = False

            # Is it a scrub-from row?
            if ddr.scrub_src:
                self.cached_scrub_from_db_table_pairs.add(db_t_key)
                self.cached_scrub_from_rows[db_t_key].add(ddr)
                # ... even if omit flag set

            # Is it a src_pk row, contributing to src_hash info?
            if SRCFLAG.PK in ddr.src_flags:
                log.debug("SRCFLAG.PK found: {}".format(ddr))
                self.cached_pk_ddr[db_t_key] = ddr
                if rnc_db.is_sqltype_integer(ddr.src_datatype):
                    self.cached_srcdb_table_pairs_to_int_pk[db_t_key] = \
                        ddr.src_field

            # Is it a relevant contribution from a source table?
            pt_info = (
                bool(ddr.scrub_src) or
                SRCFLAG.PRIMARYPID in ddr.src_flags or
                SRCFLAG.MASTERPID in ddr.src_flags
            )
            omit = ddr.omit
            if pt_info or not omit:
                # Ensure our source lists contain that table.
                self.cached_source_databases.add(ddr.src_db)
                self.cached_src_tables[ddr.src_db].add(ddr.src_table)

            # Does it indicate that the table contains patient info?
            if pt_info:
                self.cached_src_tables_w_pt_info[ddr.src_db].add(
                    ddr.src_table)
                self.cached_srcdb_table_pairs_w_pt_info.add(db_t_key)

            # Does it contribute to our destination?
            if not omit:
                self.cached_dest_tables.add(ddr.dest_table)
                self.cached_has_active_destination[db_t_key] = True
                src_tables_with_dest[ddr.src_db].add(ddr.dest_table)
                self.cached_dest_tables_for_src_db_table[db_t_key].add(
                    ddr.dest_table
                )

            if pt_info and not omit:
                self.cached_dest_tables_w_pt_info.add(ddr.dest_table)

        db_table_pairs_w_int_pk = set(
            self.cached_srcdb_table_pairs_to_int_pk.keys()
        )

        # Set calculations...
        self.cached_srcdb_table_pairs_wo_pt_info_no_pk = sorted(
            self.cached_srcdb_table_pairs -
            self.cached_srcdb_table_pairs_w_pt_info -
            db_table_pairs_w_int_pk
        )
        self.cached_srcdb_table_pairs_wo_pt_info_int_pk = sorted(
            (self.cached_srcdb_table_pairs -
                self.cached_srcdb_table_pairs_w_pt_info) &
            db_table_pairs_w_int_pk
        )
        for s in self.cached_source_databases:
            self.cached_pt_src_tables_w_dest[s] = sorted(
                self.cached_src_tables_w_pt_info[s] &
                src_tables_with_dest[s]  # & is intersection
            )

        # Debugging
        log.debug("cached_srcdb_table_pairs_w_pt_info: {}".format(
            list(self.cached_srcdb_table_pairs_w_pt_info)))
        log.debug("cached_srcdb_table_pairs_wo_pt_info_no_pk: {}".format(
            self.cached_srcdb_table_pairs_wo_pt_info_no_pk))
        log.debug("cached_srcdb_table_pairs_wo_pt_info_int_pk: {}".format(
            self.cached_srcdb_table_pairs_wo_pt_info_int_pk))

        log.debug("... cached.")

    # noinspection PyProtectedMember
    def check_against_source_db(self):
        """
        Check DD validity against the source database.
        """
        log.debug("Checking DD: source tables...")
        for d in self.get_source_databases():
            db = self.config.sources[d]
            for t in self.get_src_tables(d):

                dt = self.get_dest_tables_for_src_db_table(d, t)
                if len(dt) > 1:
                    raise ValueError(
                        "Source table {d}.{t} maps to >1 destination "
                        "table: {dt}".format(
                            d=d,
                            t=t,
                            dt=", ".join(dt),
                        )
                    )

                rows = self.get_rows_for_src_table(d, t)
                fieldnames = self.get_fieldnames_for_src_table(d, t)

                if any([r._scrub or SRCFLAG.MASTERPID in r.src_flags
                        for r in rows if not r.omit]):
                    pidfield = self.config.srccfg[d].ddgen_per_table_pid_field
                    if pidfield not in fieldnames:
                        raise ValueError(
                            "Source table {d}.{t} has a scrub_in or "
                            "src_flags={f} field but no {p} field".format(
                                d=d,
                                t=t,
                                f=SRCFLAG.MASTERPID,
                                p=pidfield,
                            )
                        )

                for r in rows:
                    if r._extract_text and not r._extract_from_filename:
                        extrow = next(
                            (r2 for r2 in rows
                                if r2.src_field == r._extract_ext_field),
                            None)
                        if extrow is None:
                            raise ValueError(
                                "alter_method = {am}, but field {f} not "
                                "found in the same table".format(
                                    am=r.alter_method,
                                    f=r._extract_ext_field
                                )
                            )
                        if not is_sqltype_text_over_one_char(
                                extrow.src_datatype):
                            raise ValueError(
                                "alter_method = {am}, but field {f}, which"
                                " should contain an extension or filename,"
                                " is not text of >1 character".format(
                                    am=r.alter_method,
                                    f=r._extract_ext_field
                                )
                            )

                n_pks = sum([1 if SRCFLAG.PK in x.src_flags else 0
                             for x in rows])
                if n_pks > 1:
                    raise ValueError(
                        "Table {d}.{t} has >1 source PK set".format(
                            d=d, t=t))

                if not db.table_exists(t):
                    raise ValueError(
                        "Table {t} missing from source database "
                        "{d}".format(
                            t=t,
                            d=d
                        )
                    )

        log.debug("... source tables checked.")

    def check_valid(self, check_against_source_db, prohibited_fieldnames=None):
        """
        Check DD validity, internally +/- against the source database.
        """
        if prohibited_fieldnames is None:
            prohibited_fieldnames = []
        log.info("Checking data dictionary...")
        if not self.rows:
            raise ValueError("Empty data dictionary")
        if not self.cached_dest_tables:
            raise ValueError("Empty data dictionary after removing "
                             "redundant tables")

        # Individual rows will already have been checked with their own
        # check_valid() method. But now we check collective consistency

        log.debug("Checking DD: prohibited fieldnames...")
        if prohibited_fieldnames:
            for r in self.rows:
                r.check_prohibited_fieldnames(prohibited_fieldnames)

        log.debug("Checking DD: destination tables...")
        for t in self.get_dest_tables():
            sdt = self.get_src_dbs_tables_for_dest_table(t)
            if len(sdt) > 1:
                raise ValueError(
                    "Destination table {t} is mapped to by multiple "
                    "source databases: {s}".format(
                        t=t,
                        s=", ".join(["{}.{}".format(s[0], s[1]) for s in sdt]),
                    )
                )

        if check_against_source_db:
            self.check_against_source_db()

        log.debug("Checking DD: global checks...")
        self.n_definers = sum(
            [1 if SRCFLAG.DEFINESPRIMARYPIDS in x.src_flags else 0
             for x in self.rows])
        if self.n_definers == 0:
            if all([x.ddgen_allow_no_patient_info
                    for x in self.config.srccfg.itervalues()]):
                log.warning("NO PATIENT-DEFINING FIELD! DATABASE(S) WILL "
                            "BE COPIED, NOT ANONYMISED.")
            else:
                raise ValueError(
                    "Must have at least one field with "
                    "src_flags={} set.".format(SRCFLAG.DEFINESPRIMARYPIDS))
        if self.n_definers > 1:
            log.warning(
                "Unusual: >1 field with src_flags={} set.".format(
                    SRCFLAG.DEFINESPRIMARYPIDS))

        log.debug("... DD checked.")

    def get_dest_tables(self):
        """Return a SortedSet of all destination tables."""
        return self.cached_dest_tables

    def get_dest_tables_for_src_db_table(self, src_db, src_table):
        """For a given source database/table, return a SortedSet of destination
        tables."""
        return self.cached_dest_tables_for_src_db_table[(src_db, src_table)]

    def get_dest_table_for_src_db_table(self, src_db, src_table):
        """For a given source database/table, return the single or the first
        destination table."""
        return self.cached_dest_tables_for_src_db_table[(src_db, src_table)][0]

    def get_source_databases(self):
        """Return a SortedSet of source database names."""
        return self.cached_source_databases

    def get_src_dbs_tables_for_dest_table(self, dest_table):
        """For a given destination table, return a SortedSet of (dbname, table)
        tuples."""
        return self.cached_src_dbtables_for_dest_table[dest_table]

    def get_src_tables(self, src_db):
        """For a given source database name, return a SortedSet of source
        tables."""
        return self.cached_src_tables[src_db]

    def get_patient_src_tables_with_active_dest(self, src_db):
        """For a given source database name, return a SortedSet of source
        tables that have an active destination table."""
        return self.cached_pt_src_tables_w_dest[src_db]

    def get_src_tables_with_patient_info(self, src_db):
        """For a given source database name, return a SortedSet of source
        tables that have patient information."""
        return self.cached_src_tables_w_pt_info[src_db]

    def get_dest_tables_with_patient_info(self):
        """Return a SortedSet of destination table names that have patient
        information."""
        return self.cached_dest_tables_w_pt_info

    def get_rows_for_src_table(self, src_db, src_table):
        """For a given source database name/table, return a SortedSet of DD
        rows."""
        return self.cached_rows_for_src_table[(src_db, src_table)]

    def get_rows_for_dest_table(self, dest_table):
        """For a given destination table, return a SortedSet of DD rows."""
        return self.cached_rows_for_dest_table[dest_table]

    def get_fieldnames_for_src_table(self, src_db, src_table):
        """For a given source database name/table, return a SortedSet of source
        fields."""
        return self.cached_fieldnames_for_src_table[(src_db, src_table)]

    def get_scrub_from_db_table_pairs(self):
        """Return a SortedSet of (source database name, source table) tuples
        where those fields contain scrub_src (scrub-from) information."""
        return self.cached_scrub_from_db_table_pairs

    def get_scrub_from_rows(self, src_db, src_table):
        """Return a SortedSet of DD rows for all fields containing scrub_src
        (scrub-from) information."""
        return self.cached_scrub_from_rows[(src_db, src_table)]

    def get_tsv(self):
        """
        Return the DD in TSV format.
        """
        return "\n".join(
            ["\t".join(DataDictionaryRow.ROWNAMES)] +
            [r.get_tsv() for r in self.rows]
        )

    def get_src_db_tablepairs(self):
        """Return a SortedSet of (source database name, source table) tuples.
        """
        return self.cached_srcdb_table_pairs

    def get_src_dbs_tables_with_no_pt_info_no_pk(self):
        """Return a SortedSet of (source database name, source table) tuples
        where the table has no patient information and no integer PK."""
        return self.cached_srcdb_table_pairs_wo_pt_info_no_pk

    def get_src_dbs_tables_with_no_pt_info_int_pk(self):
        """Return a SortedSet of (source database name, source table) tuples
        where the table has no patient information and has an integer PK."""
        return self.cached_srcdb_table_pairs_wo_pt_info_int_pk

    def get_int_pk_name(self, src_db, src_table):
        """For a given source database name and table, return the field name
        of the integer PK for that table."""
        return self.cached_srcdb_table_pairs_to_int_pk[(src_db, src_table)]

    def get_pk_ddr(self, src_db, src_table):
        """For a given source database name and table, return the DD row
        for the integer PK for that table.

        Will return None if no such data dictionary row.
        """
        return self.cached_pk_ddr.get((src_db, src_table), None)

    def has_active_destination(self, src_db, src_table):
        """For a given source database name and table: does it have an active
        destination?"""
        return self.cached_has_active_destination[(src_db, src_table)]
