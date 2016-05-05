#!/usr/bin/env python3
# crate_anon/anonymise/anon_dd.py

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

from sortedcontainers import SortedSet
from sqlalchemy import (
    Column,
    Table,
)

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
    convert_to_bool,
    convert_to_int,
    count_bool,
    raise_if_attr_blank,
)

# don't import config: circular dependency would have to be sorted out
from crate_anon.anonymise.constants import (
    ALTERMETHOD,
    DEFAULT_INDEX_LEN,
    INDEX,
    LONGTEXT,
    MYSQL_TABLE_ARGS,
    ODD_CHARS_TRANSLATE,
    SCRUBMETHOD,
    SCRUBSRC,
    SRCFLAG,
    TridType,
)
from crate_anon.anonymise.sqla import get_sqla_coltype_from_dialect_str

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

    def __init__(self, config):
        """
        Set up basic defaults.
        """
        self.config = config

        self.src_db = None
        self.src_table = None
        self.src_field = None
        self.src_datatype = None  # in SQL string format
        self._src_sqla_coltype = None
        # src_flags: a property; see below
        self.scrub_src = None
        self.scrub_method = None
        self.omit = False
        # alter_method: a property; see below
        self.dest_table = None
        self.dest_field = None
        self.dest_datatype = None
        self.index = False
        self.indexlen = None
        self.comment = ''

        self._from_file = False

        # For src_flags:
        self._pk = False
        self._add_src_hash = False
        self._primary_pid = False
        self._defines_primary_pids = False
        self._master_pid = False
        self._constant = False
        self._addition_only = False

        # For alter_method:
        self._scrub = False
        self._truncate_date = False
        self._extract_text = False
        self._extract_from_filename = False
        self._extract_ext_field = ""

    def __lt__(self, other):
        return self.get_signature() < other.get_signature()

    @property
    def pk(self):
        return self._pk

    @property
    def add_src_hash(self):
        return self._add_src_hash

    @property
    def primary_pid(self):
        return self._primary_pid

    @property
    def defines_primary_pids(self):
        return self._defines_primary_pids

    @property
    def master_pid(self):
        return self._master_pid

    @property
    def constant(self):
        return self._constant

    @property
    def addition_only(self):
        return self._addition_only

    @property
    def src_flags(self):
        return ''.join([
            SRCFLAG.PK if self._pk else '',
            SRCFLAG.ADDSRCHASH if self._add_src_hash else '',
            SRCFLAG.PRIMARYPID if self._primary_pid else '',
            SRCFLAG.DEFINESPRIMARYPIDS if self._defines_primary_pids else '',
            SRCFLAG.MASTERPID if self._master_pid else '',
            SRCFLAG.CONSTANT if self._constant else '',
            SRCFLAG.ADDITION_ONLY if self._addition_only else '',
        ])

    @src_flags.setter
    def src_flags(self, value):
        self._pk = SRCFLAG.PK in value
        self._add_src_hash = SRCFLAG.ADDSRCHASH in value
        self._primary_pid = SRCFLAG.PRIMARYPID in value
        self._defines_primary_pids = SRCFLAG.DEFINESPRIMARYPIDS in value
        self._master_pid = SRCFLAG.MASTERPID in value
        self._constant = SRCFLAG.CONSTANT in value
        self._addition_only = SRCFLAG.ADDITION_ONLY in value

    @property
    def scrub(self):
        return self._scrub

    @property
    def truncate_date(self):
        return self._truncate_date

    @property
    def extract_text(self):
        return self._extract_text

    @property
    def extract_from_filename(self):
        return self._extract_from_filename

    @property
    def extract_ext_field(self):
        return self._extract_ext_field

    @property
    def alter_method(self):
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

    @alter_method.setter
    def alter_method(self, value):
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
        if "=" in value:
            secondhalf = value[value.index("=") + 1:]
        if value == ALTERMETHOD.TRUNCATEDATE:
            self._truncate_date = True
        elif value.startswith(ALTERMETHOD.SCRUBIN):
            self._scrub = True
        elif value.startswith(ALTERMETHOD.BIN2TEXT):
            self._extract_text = True
            self._extract_ext_field = secondhalf
        elif value.startswith(ALTERMETHOD.BIN2TEXT_SCRUB):
            self._extract_text = True
            self._extract_ext_field = secondhalf
            self._scrub = True
        elif value.startswith(ALTERMETHOD.FILENAME2TEXT):
            self._extract_text = True
            self._extract_from_filename = True
        elif value.startswith(ALTERMETHOD.FILENAME2TEXT_SCRUB):
            self._extract_text = True
            self._extract_from_filename = True
            self._scrub = True

    @property
    def from_file(self):
        return self._from_file

    def __str__(self):
        """
        Return a string representation.
        """
        return ", ".join(["{}: {}".format(a, getattr(self, a))
                          for a in DataDictionaryRow.ROWNAMES])

    def get_signature(self):
        """
        Return a signature based on the source database/table/field.
        """
        return "{}.{}.{}".format(self.src_db, self.src_table, self.src_field)

    def get_dest_signature(self):
        return "{}.{}".format(self.dest_table, self.dest_field)

    def set_from_dict(self, valuedict):
        """
        Set internal fields from a dict of elements representing a row from the
        TSV data dictionary file.
        """
        self.src_db = valuedict['src_db']
        self.src_table = valuedict['src_table']
        self.src_field = valuedict['src_field']
        self.src_datatype = valuedict['src_datatype'].upper()
        self.src_flags = valuedict['src_flags']  # a property
        self.scrub_src = valuedict['scrub_src']
        self.scrub_method = valuedict['scrub_method']
        self.omit = convert_to_bool(valuedict['omit'])
        self.alter_method = valuedict['alter_method']  # a property
        self.dest_table = valuedict['dest_table']
        self.dest_field = valuedict['dest_field']
        self.dest_datatype = valuedict['dest_datatype'].upper()
        self.index = valuedict['index']
        self.indexlen = convert_to_int(valuedict['indexlen'])
        self.comment = valuedict['comment']
        self._from_file = True
        self.check_valid()

    def set_from_src_db_info(self, db, table, field,
                             datatype_sqltext, sqla_coltype, cfg, comment=None,
                             default_omit=True):
        """
        Create a draft data dictionary row from a field in the source database.
        """
        self.src_db = db
        self.src_table = table
        self.src_field = field
        self.src_datatype = datatype_sqltext
        self._src_sqla_coltype = sqla_coltype

        # Is the field special, such as a PK?
        self._pk = False
        self._add_src_hash = False
        self._primary_pid = False
        self._defines_primary_pids = False
        self._master_pid = False
        self._constant = False
        self._addition_only = False
        if self.src_field in cfg.ddgen_pk_fields:
            self._pk = True
            if cfg.ddgen_constant_content:
                self._constant = True
            else:
                self._add_src_hash = True
            if cfg.ddgen_addition_only:
                self._addition_only = True
        if self.src_field == cfg.ddgen_per_table_pid_field:
            self._primary_pid = True
        if self.src_field == cfg.ddgen_master_pid_fieldname:
            self._master_pid = True
        if self.src_field in cfg.ddgen_pid_defining_fieldnames:  # unusual!
            self._defines_primary_pids = True

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
        elif (is_sqltype_numeric(datatype_sqltext) or
                self.src_field == cfg.ddgen_per_table_pid_field or
                self.src_field == cfg.ddgen_master_pid_fieldname or
                self.src_field in cfg.ddgen_scrubmethod_number_fields):
            self.scrub_method = SCRUBMETHOD.NUMERIC
        elif (is_sqltype_date(datatype_sqltext) or
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
            not self._pk and
            not self._primary_pid and
            not self._master_pid
        )

        # Do we want to change the destination fieldname?
        if self._primary_pid:
            self.dest_field = self.config.research_id_fieldname
        elif self._master_pid:
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
            self.config.sqltype_encrypted_pid_as_sql
            if (self._primary_pid or self._master_pid)
            # else rnc_db.full_datatype_to_mysql(datatype_full)
            # else datatype_full
            else ''
        )

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
                datatype_sqltext, cfg.ddgen_min_length_for_scrubbing) and
                not self.omit and
                not self._primary_pid and
                not self._master_pid and
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
        if self._pk:
            self.index = INDEX.UNIQUE
        elif (self.dest_field == self.config.research_id_fieldname or
                self._primary_pid or
                self._master_pid or
                self._defines_primary_pids):
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
        offenderdest = "" if not self.omit else " -> {}".format(
            self.get_dest_signature())
        return "{}{}".format(self.get_signature(), offenderdest)

    def check_valid(self):
        """
        Check internal validity and complain if invalid, showing the source
        of the problem.
        """
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
                # "dest_datatype",
            ])

        if self.src_db not in self.config.get_source_db_names():
            raise ValueError(
                "Data dictionary row references non-existent source "
                "database")
        srccfg = self.config.sources[self.src_db].srccfg
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

        if self._defines_primary_pids and not self._primary_pid:
            raise ValueError(
                "All fields with src_flags={} set must have src_flags={} "
                "set".format(
                    SRCFLAG.DEFINESPRIMARYPIDS,
                    SRCFLAG.PRIMARYPID
                ))

        if count_bool([self._primary_pid,
                       self._master_pid,
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
            if self.dest_datatype and not is_sqltype_valid(self.dest_datatype):
                raise ValueError(
                    "Field has invalid destination data type: "
                    "{}".format(self.dest_datatype))
            if self.src_field == srccfg.ddgen_per_table_pid_field:
                if not self._primary_pid:
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
                    not self._master_pid):
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

            if ((self._primary_pid or self._master_pid) and
                    self.dest_datatype !=
                    self.config.sqltype_encrypted_pid_as_sql):
                raise ValueError(
                    "All src_flags={}/src_flags={} fields used in output must "
                    "have destination_datatype = {}".format(
                        SRCFLAG.PRIMARYPID,
                        SRCFLAG.MASTERPID,
                        self.config.sqltype_encrypted_pid_as_sql))

            valid_index = [INDEX.NORMAL, INDEX.UNIQUE, INDEX.FULLTEXT, ""]
            if self.index not in valid_index:
                raise ValueError("Index must be one of: [{}]".format(
                    ",".join(valid_index)))

            if (self.index in [INDEX.NORMAL, INDEX.UNIQUE] and
                    self.indexlen is None and
                    does_sqltype_require_index_len(
                        self.dest_datatype if self.dest_datatype
                        else self.src_datatype)):
                raise ValueError(
                    "Must specify indexlen to index a TEXT or BLOB field")

        if self._add_src_hash:
            if not self._pk:
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
            if self._constant:
                raise ValueError(
                    "cannot mix {} flag with {} flag".format(
                        SRCFLAG.ADDSRCHASH,
                        SRCFLAG.CONSTANT))

        if self._constant:
            if not self._pk:
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

    def contains_patient_info(self):
        return bool(self.scrub_src) or self._primary_pid or self._master_pid

    def required(self):
        return not self.omit or self.contains_patient_info()

    def set_src_sqla_coltype(self, sqla_coltype):
        self._src_sqla_coltype = sqla_coltype

    def get_sqla_dest_coltype(self):
        if self.dest_datatype:
            # User (or our autogeneration process) wants to override
            # the type.
            return get_sqla_coltype_from_dialect_str(
                self.config.destdb.engine,
                self.dest_datatype)
        else:
            return self._src_sqla_coltype
            # Will be autoconverted to the destination dialect.

    def get_sqla_dest_column(self):
        name = self.dest_field
        coltype = self.get_sqla_dest_coltype()
        comment = self.comment or ''
        kwargs = {'doc': comment}
        if self._pk:
            kwargs['primary_key'] = True
            kwargs['autoincrement'] = False
        if self.primary_pid:
            kwargs['nullable'] = False
        return Column(name, coltype, **kwargs)


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
        self.n_definers = 0

    def read_from_file(self, filename):
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
                    "(TSV) file with the following row headings:\n" +
                    "\n".join(DataDictionaryRow.ROWNAMES)
                )
            log.debug("Data dictionary has correct header. Loading content...")
            for values in tsv:
                valuedict = dict(zip(headers, values))
                ddr = DataDictionaryRow(self.config)
                ddr.set_from_dict(valuedict)
                self.rows.append(ddr)
            log.debug("... content loaded.")
        self.clear_caches()

    def read_from_source_databases(self, report_every=100,
                                   default_omit=True):
        """
        Create a draft DD from a source database.
        """
        log.info("Reading information for draft data dictionary")
        signatures = [ddr.get_signature() for ddr in self.rows]
        for pretty_dbname, db in self.config.sources.items():
            log.info("... database nice name = {}".format(pretty_dbname))
            cfg = db.srccfg
            meta = db.metadata
            i = 0
            for t in meta.sorted_tables:
                tablename = t.name
                for c in t.columns:
                    i += 1
                    if report_every and i % report_every == 0:
                        log.debug("... reading source field {}".format(i))
                    columnname = c.name
                    # log.critical("str(coltype) == {}".format(str(c.type)))
                    # log.critical("repr(coltype) == {}".format(repr(c.type)))
                    datatype_sqltext = str(c.type)
                    sqla_coltype = c.type
                    if cfg.ddgen_force_lower_case:
                        tablename = tablename.lower()
                        columnname = columnname.lower()
                    if (tablename in cfg.ddgen_table_blacklist or
                            columnname in cfg.ddgen_field_blacklist):
                        continue
                    comment = ''  # currently unsupported by SQLAlchemy
                    if self.config.append_source_info_to_comment:
                        comment = "[from {t}.{f}]".format(
                            t=tablename,
                            f=columnname,
                        )
                    ddr = DataDictionaryRow(self.config)
                    ddr.set_from_src_db_info(
                        pretty_dbname, tablename, columnname,
                        datatype_sqltext,
                        sqla_coltype,
                        cfg=cfg,
                        comment=comment,
                        default_omit=default_omit)
                    sig = ddr.get_signature()
                    if sig not in signatures:
                        self.rows.append(ddr)
                        signatures.append(sig)
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
        log.info("Sorting draft data dictionary")
        self.rows = sorted(self.rows,
                           key=operator.attrgetter("src_db",
                                                   "src_table",
                                                   "src_field"))
        log.info("... done")

    def check_against_source_db(self):
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
                        "table: {dt}".format(
                            d=d,
                            t=t,
                            dt=", ".join(dt),
                        )
                    )

                rows = self.get_rows_for_src_table(d, t)
                fieldnames = self.get_fieldnames_for_src_table(d, t)

                if any([r.scrub or r.master_pid
                        for r in rows if not r.omit]):
                    pidfield = db.srccfg.ddgen_per_table_pid_field
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
                    r.set_src_sqla_coltype(
                        db.metadata.tables[t].columns[r.src_field].type)
                    if r.extract_text and not r.extract_from_filename:
                        extrow = next(
                            (r2 for r2 in rows
                                if r2.src_field == r.extract_ext_field),
                            None)
                        if extrow is None:
                            raise ValueError(
                                "alter_method = {am}, but field {f} not "
                                "found in the same table".format(
                                    am=r.alter_method,
                                    f=r.extract_ext_field
                                )
                            )
                        if not is_sqltype_text_over_one_char(
                                extrow.src_datatype):
                            raise ValueError(
                                "alter_method = {am}, but field {f}, which"
                                " should contain an extension or filename,"
                                " is not text of >1 character".format(
                                    am=r.alter_method,
                                    f=r.extract_ext_field
                                )
                            )

                n_pks = sum([1 if x.pk else 0 for x in rows])
                if n_pks > 1:
                    raise ValueError(
                        "Table {d}.{t} has >1 source PK set".format(
                            d=d, t=t))

                if t not in db.table_names:
                    log.debug(
                        "Source database {d} has tables: {tables}".format(
                            d=d, tables=db.table_names))
                    raise ValueError(
                        "Table {t} missing from source database "
                        "{d}".format(
                            t=t,
                            d=d
                        )
                    )

        log.debug("... source tables checked.")

    def check_valid(self, prohibited_fieldnames=None):
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

        log.debug("Checking DD: duplicate source/destination rows?")
        src_sigs = []
        dst_sigs = []
        for r in self.rows:
            src_sigs.append(r.get_signature())
            dst_sigs.append(r.get_dest_signature())
        src_duplicates = [
            item for item, count in collections.Counter(src_sigs).items()
            if count > 1]
        dst_duplicates = [
            item for item, count in collections.Counter(dst_sigs).items()
            if count > 1]
        if src_duplicates:
            raise ValueError("Duplicate source rows: {}".format(
                src_duplicates))
        if dst_duplicates:
            raise ValueError("Duplicate source rows: {}".format(
                dst_duplicates))

        self.check_against_source_db()

        log.debug("Checking DD: global checks...")
        self.n_definers = sum([1 if x.defines_primary_pids else 0
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
        elif self.n_definers > 1:
            log.warning(
                "Unusual: >1 field with src_flags={} set.".format(
                    SRCFLAG.DEFINESPRIMARYPIDS))

        log.debug("... DD checked.")

    # =========================================================================
    # Whole-DD operations
    # =========================================================================

    def get_tsv(self):
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
    def get_source_databases(self):
        """Return a SortedSet of source database names."""
        return SortedSet([
             ddr.src_db
             for ddr in self.rows
             if ddr.required()
         ])

    @lru_cache(maxsize=None)
    def get_scrub_from_db_table_pairs(self):
        """Return a SortedSet of (source database name, source table) tuples
        where those fields contain scrub_src (scrub-from) information."""
        return SortedSet([
            (ddr.src_db, ddr.src_table)
            for ddr in self.rows
            if ddr.scrub_src
        ])
        # even if omit flag set

    @lru_cache(maxsize=None)
    def get_src_db_tablepairs(self):
        """Return a SortedSet of (source database name, source table) tuples.
        """
        return SortedSet([
            (ddr.src_db, ddr.src_table)
            for ddr in self.rows
        ])

    @lru_cache(maxsize=None)
    def get_src_db_tablepairs_w_pt_info(self):
        """Return a SortedSet of (source database name, source table) tuples.
        """
        return SortedSet([
            (ddr.src_db, ddr.src_table)
            for ddr in self.rows
            if ddr.contains_patient_info()
        ])

    @lru_cache(maxsize=None)
    def get_src_db_tablepairs_w_int_pk(self):
        """Return a SortedSet of (source database name, source table) tuples.
        """
        return SortedSet([
            (ddr.src_db, ddr.src_table)
            for ddr in self.rows
            if self.get_pk_ddr(ddr.src_db, ddr.src_table) is not None
        ])

    @lru_cache(maxsize=None)
    def get_src_dbs_tables_with_no_pt_info_no_pk(self):
        """Return a SortedSet of (source database name, source table) tuples
        where the table has no patient information and no integer PK."""
        return (
            self.get_src_db_tablepairs() -
            self.get_src_db_tablepairs_w_pt_info() -
            self.get_src_db_tablepairs_w_int_pk()
        )

    @lru_cache(maxsize=None)
    def get_src_dbs_tables_with_no_pt_info_int_pk(self):
        """Return a SortedSet of (source database name, source table) tuples
        where the table has no patient information and has an integer PK."""
        return (
            (self.get_src_db_tablepairs() -
                self.get_src_db_tablepairs_w_pt_info()) &  # & is intersection
            self.get_src_db_tablepairs_w_int_pk()
        )

    @lru_cache(maxsize=None)
    def get_dest_tables(self):
        """Return a SortedSet of all destination tables."""
        return SortedSet([
            ddr.dest_table
            for ddr in self.rows
            if not ddr.omit
        ])

    @lru_cache(maxsize=None)
    def get_dest_tables_with_patient_info(self):
        """Return a SortedSet of destination table names that have patient
        information."""
        return SortedSet([
            ddr.dest_table
            for ddr in self.rows
            if ddr.contains_patient_info() and not ddr.omit
        ])

    # =========================================================================
    # Queries by source DB
    # =========================================================================

    @lru_cache(maxsize=None)
    def get_src_tables(self, src_db):
        """For a given source database name, return a SortedSet of source
        tables."""
        return SortedSet([
            ddr.src_table
            for ddr in self.rows
            if ddr.src_db == src_db and ddr.required()
        ])

    @lru_cache(maxsize=None)
    def get_src_tables_with_active_dest(self, src_db):
        """For a given source database name, return a SortedSet of source
        tables."""
        return SortedSet([
            ddr.src_table
            for ddr in self.rows
            if ddr.src_db == src_db and not ddr.omit
        ])

    @lru_cache(maxsize=None)
    def get_src_tables_with_patient_info(self, src_db):
        """For a given source database name, return a SortedSet of source
        tables that have patient information."""
        return SortedSet([
            ddr.src_table
            for ddr in self.rows
            if ddr.src_db == src_db and ddr.contains_patient_info()
        ])

    @lru_cache(maxsize=None)
    def get_patient_src_tables_with_active_dest(self, src_db):
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
    def get_dest_tables_for_src_db_table(self, src_db, src_table):
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
    def get_dest_table_for_src_db_table(self, src_db, src_table):
        """For a given source database/table, return the single or the first
        destination table."""
        return self.get_dest_tables_for_src_db_table(src_db, src_table)[0]

    @lru_cache(maxsize=None)
    def get_rows_for_src_table(self, src_db, src_table):
        """For a given source database name/table, return a SortedSet of DD
        rows."""
        return SortedSet([
            ddr
            for ddr in self.rows
            if ddr.src_db == src_db and ddr.src_table == src_table
        ])

    @lru_cache(maxsize=None)
    def get_fieldnames_for_src_table(self, src_db, src_table):
        """For a given source database name/table, return a SortedSet of source
        fields."""
        return SortedSet([
            ddr.src_field
            for ddr in self.rows
            if ddr.src_db == src_db and ddr.src_table == src_table
        ])

    @lru_cache(maxsize=None)
    def get_scrub_from_rows(self, src_db, src_table):
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
    def get_pk_ddr(self, src_db, src_table):
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
    def get_int_pk_name(self, src_db, src_table):
        """For a given source database name and table, return the field name
        of the integer PK for that table."""
        ddr = self.get_pk_ddr(src_db, src_table)
        if ddr is None:
            return None
        return ddr.src_field

    @lru_cache(maxsize=None)
    def has_active_destination(self, src_db, src_table):
        """For a given source database name and table: does it have an active
        destination?"""
        for ddr in self.rows:
            if (ddr.src_db == src_db and
                    ddr.src_table == src_table and
                    not ddr.omit):
                return True
        return False

    @lru_cache(maxsize=None)
    def get_pid_name(self, src_db, src_table):
        for ddr in self.rows:
            if (ddr.src_db == src_db and
                    ddr.src_table == src_table and
                    ddr.primary_pid):
                return ddr.src_field
        return None

    # =========================================================================
    # Queries by destination table
    # =========================================================================

    @lru_cache(maxsize=None)
    def get_src_dbs_tables_for_dest_table(self, dest_table):
        """For a given destination table, return a SortedSet of (dbname, table)
        tuples."""
        return SortedSet([
            (ddr.src_db, ddr.src_table)
            for ddr in self.rows
            if ddr.dest_table == dest_table
        ])

    @lru_cache(maxsize=None)
    def get_rows_for_dest_table(self, dest_table):
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
    def get_dest_sqla_table(self, tablename):
        metadata = self.config.destdb.metadata
        columns = []
        for ddr in self.get_rows_for_dest_table(tablename):
            columns.append(ddr.get_sqla_dest_column())
            if ddr.add_src_hash:
                columns.append(self.get_srchash_sqla_column())
            if ddr.primary_pid:
                columns.append(self.get_trid_sqla_column())
        return Table(tablename, metadata, *columns, **MYSQL_TABLE_ARGS)

    def get_srchash_sqla_column(self):
        return Column(
            self.config.source_hash_fieldname,
            self.config.SqlTypeEncryptedPid,
            doc='Hashed amalgamation of all source fields'
        )

    def get_trid_sqla_column(self):
        return Column(
            self.config.trid_fieldname,
            TridType,
            nullable=False,
            doc='Transient integer research ID (TRID)'
        )

    # =========================================================================
    # Clear caches
    # =========================================================================

    def cached_funcs(self):
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

            self.get_src_dbs_tables_for_dest_table,
            self.get_rows_for_dest_table,

            self.get_dest_sqla_table,
        ]

    def clear_caches(self):
        for func in self.cached_funcs():
            func.cache_clear()

    def debug_cache_hits(self):
        for func in self.cached_funcs():
            log.debug("{}: {}".format(func.__name__, func.cache_info()))
