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

import ast
import collections
import csv
import fnmatch
from functools import lru_cache
import logging
import operator
from typing import (AbstractSet, Any, List, Dict, Iterable, Optional, Union,
                    Tuple)

import regex
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
    convert_to_int,
    count_bool,
)
from sortedcontainers import SortedSet
from sqlalchemy import (
    Column,
    Table,
)

# don't import config: circular dependency would have to be sorted out
from crate_anon.anonymise.constants import (
    ALTERMETHOD,
    DECISION,
    DEFAULT_INDEX_LEN,
    INDEX,
    LONGTEXT,
    MYSQL_MAX_IDENTIFIER_LENGTH,
    MYSQL_TABLE_ARGS,
    ODD_CHARS_TRANSLATE,
    SCRUBMETHOD,
    SCRUBSRC,
    SRCFLAG,
    TridType,
)
from crate_anon.common.sqla import (
    convert_sqla_type_for_dialect,
    get_sqla_coltype_from_dialect_str,
)
from crate_anon.common.sql import split_db_table

log = logging.getLogger(__name__)


# =============================================================================
# AlterMethod
# =============================================================================

class AlterMethod(object):
    def __init__(self,
                 text_value: str = None,
                 scrub: bool = False,
                 truncate_date: bool = False,
                 extract_from_filename: bool = False,
                 extract_from_blob: bool = False,
                 skip_if_text_extract_fails: bool = False,
                 extract_ext_field: str = "",
                 # html_escape: bool = False,
                 html_unescape: bool = False,
                 html_untag: bool = False) -> None:
        self.scrub = scrub
        self.truncate_date = truncate_date
        self.extract_text = (extract_from_filename or extract_from_blob)
        self.extract_from_blob = extract_from_blob
        self.extract_from_filename = extract_from_filename
        self.skip_if_text_extract_fails = skip_if_text_extract_fails
        self.extract_ext_field = extract_ext_field
        # self.html_escape = html_escape
        self.html_unescape = html_unescape
        self.html_untag = html_untag
        if text_value is not None:
            self.set_from_text(text_value)

    def set_from_text(self, value: str) -> None:
        """
        Convert the alter_method field (from the data dictionary) to a bunch of
        boolean/simple fields.
        """
        self.scrub = False
        self.truncate_date = False
        self.extract_text = False
        self.extract_from_blob = False
        self.extract_from_filename = False
        self.skip_if_text_extract_fails = False
        self.extract_ext_field = ""
        if value == ALTERMETHOD.TRUNCATEDATE.value:
            self.truncate_date = True
        elif value == ALTERMETHOD.SCRUBIN.value:
            self.scrub = True
        elif value.startswith(ALTERMETHOD.BIN2TEXT.value):
            if "=" not in value:
                raise ValueError(
                    "Bad format for alter method: {}".format(value))
            secondhalf = value[value.index("=") + 1:]
            if not secondhalf:
                raise ValueError(
                    "Missing filename/extension field in alter method: "
                    "{}".format(value))
            self.extract_text = True
            self.extract_from_blob = True
            self.extract_ext_field = secondhalf
        elif value == ALTERMETHOD.FILENAME2TEXT.value:
            self.extract_text = True
            self.extract_from_filename = True
        elif value == ALTERMETHOD.SKIP_IF_TEXT_EXTRACT_FAILS.value:
            self.skip_if_text_extract_fails = True
        # elif value == ALTERMETHOD.HTML_ESCAPE:
        #     self.html_escape = True
        elif value == ALTERMETHOD.HTML_UNESCAPE.value:
            self.html_unescape = True
        elif value == ALTERMETHOD.HTML_UNTAG.value:
            self.html_untag = True
        else:
            raise ValueError("Bad alter_method part: {}".format(value))

    def get_text(self) -> str:
        """
        Return the alter_method fragment from the working fields.
        """
        if self.truncate_date:
            return ALTERMETHOD.TRUNCATEDATE.value
        if self.scrub:
            return ALTERMETHOD.SCRUBIN.value
        if self.extract_text:
            if self.extract_from_blob:
                return ALTERMETHOD.BIN2TEXT.value + "=" + self.extract_ext_field
            else:
                return ALTERMETHOD.FILENAME2TEXT.value
        if self.skip_if_text_extract_fails:
            return ALTERMETHOD.SKIP_IF_TEXT_EXTRACT_FAILS.value
        # if self.html_escape:
        #     return ALTERMETHOD.HTML_ESCAPE.value
        if self.html_unescape:
            return ALTERMETHOD.HTML_UNESCAPE.value
        if self.html_untag:
            return ALTERMETHOD.HTML_UNTAG.value
        return ""


# =============================================================================
# DataDictionaryRow
# =============================================================================

DDR_FWD_REF = "DataDictionaryRow"
CONFIG_FWD_REF = "Config"


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

        "decision",
        "inclusion_values",
        "exclusion_values",
        "alter_method",

        "dest_table",
        "dest_field",
        "dest_datatype",
        "index",
        "indexlen",
        "comment",
    ]

    def __init__(self, config: CONFIG_FWD_REF) -> None:
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
        self.omit = False  # in the DD file, this is 'decision'
        # alter_method: a property; see below
        self.dest_table = None
        self.dest_field = None
        self.dest_datatype = None
        self.index = None
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
        self._opt_out_info = False
        self._required_scrubber = False

        self._inclusion_values = []
        self._exclusion_values = []

        self._alter_methods = []

    # -------------------------------------------------------------------------
    # Comparisons and properties
    # -------------------------------------------------------------------------

    def __lt__(self, other: DDR_FWD_REF) -> bool:
        return self.get_signature() < other.get_signature()

    @property
    def src_db_lowercase(self) -> str:
        return self.src_db.lower()

    @property
    def src_table_lowercase(self) -> str:
        return self.src_table.lower()

    @property
    def src_field_lowercase(self) -> str:
        return self.src_field.lower()

    @property
    def pk(self) -> bool:
        return self._pk

    @property
    def add_src_hash(self) -> bool:
        return self._add_src_hash

    @property
    def primary_pid(self) -> bool:
        return self._primary_pid

    @property
    def defines_primary_pids(self) -> bool:
        return self._defines_primary_pids

    @property
    def master_pid(self) -> bool:
        return self._master_pid

    @property
    def constant(self) -> bool:
        return self._constant

    @property
    def addition_only(self) -> bool:
        return self._addition_only

    @property
    def opt_out_info(self) -> bool:
        return self._opt_out_info

    @property
    def src_flags(self) -> str:
        return ''.join(str(x) for x in [
            SRCFLAG.PK if self._pk else '',
            SRCFLAG.ADD_SRC_HASH if self._add_src_hash else '',
            SRCFLAG.PRIMARY_PID if self._primary_pid else '',
            SRCFLAG.DEFINES_PRIMARY_PIDS if self._defines_primary_pids else '',
            SRCFLAG.MASTER_PID if self._master_pid else '',
            SRCFLAG.CONSTANT if self._constant else '',
            SRCFLAG.ADDITION_ONLY if self._addition_only else '',
            SRCFLAG.OPT_OUT if self._opt_out_info else '',
            SRCFLAG.REQUIRED_SCRUBBER if self._required_scrubber else '',
        ])

    @src_flags.setter
    def src_flags(self, value: str) -> None:
        self._pk = SRCFLAG.PK.value in value
        self._add_src_hash = SRCFLAG.ADD_SRC_HASH.value in value
        self._primary_pid = SRCFLAG.PRIMARY_PID.value in value
        self._defines_primary_pids = SRCFLAG.DEFINES_PRIMARY_PIDS.value in value
        self._master_pid = SRCFLAG.MASTER_PID.value in value
        self._constant = SRCFLAG.CONSTANT.value in value
        self._addition_only = SRCFLAG.ADDITION_ONLY.value in value
        self._opt_out_info = SRCFLAG.OPT_OUT.value in value
        self._required_scrubber = SRCFLAG.REQUIRED_SCRUBBER.value in value

    @property
    def inclusion_values(self) -> List[Any]:
        return self._inclusion_values or ''  # for TSV output

    @inclusion_values.setter
    def inclusion_values(self, value: str) -> None:
        if value:
            self._inclusion_values = ast.literal_eval(value) or []
        else:
            self._inclusion_values = []

    @property
    def exclusion_values(self) -> List[Any]:
        return self._exclusion_values or ''  # for TSV output

    @exclusion_values.setter
    def exclusion_values(self, value: str) -> None:
        if value:
            self._exclusion_values = ast.literal_eval(value) or []
        else:
            self._exclusion_values = []

    @property
    def alter_method(self) -> str:
        """
        Return the alter_method field from the working fields.
        """
        return ",".join(filter(
            None, (x.get_text() for x in self._alter_methods)))

    def get_extracting_text_altermethods(self):
        return [am.extract_text for am in self._alter_methods
                if am.extract_text]
    
    def remove_scrub_from_alter_methods(self) -> None:
        for sm in self._alter_methods:
            sm.scrub = False

    @alter_method.setter
    def alter_method(self, value: str) -> None:
        """
        Convert the alter_method field (from the data dictionary) to a bunch of
        boolean/simple fields.
        """
        # Get the list of elements in the user's order.
        self._alter_methods = []
        elements = [x.strip() for x in value.split(",") if x]
        methods = []
        for e in elements:
            methods.append(AlterMethod(e))
        # Now establish order. Text extraction first; everything else in order.
        text_extraction_indices = []
        for i, am in enumerate(methods):
            if am.extract_text:
                text_extraction_indices.append(i)
        for index in sorted(text_extraction_indices, reverse=True):
            # Go in reverse order of index.
            self._alter_methods.append(methods[index])
            del methods[index]
        self._alter_methods.extend(methods)
        # Now, checks:
        have_text_extraction = False
        have_truncate_date = False
        for am in self._alter_methods:
            if not am.truncate_date and have_truncate_date:
                raise ValueError("Date truncation must stand alone in "
                                 "alter_method: {}".format(value))
            if am.extract_text and have_text_extraction:
                raise ValueError("Can only have one text extraction method in "
                                 "{}".format(value))
            if am.truncate_date:
                have_truncate_date = True
            if am.extract_text:
                have_text_extraction = True

    def get_alter_methods(self) -> List[AlterMethod]:
        return self._alter_methods

    def skip_row_if_extract_text_fails(self) -> bool:
        return any(x.skip_if_text_extract_fails for x in self._alter_methods)

    @property
    def from_file(self) -> bool:
        return self._from_file
    
    @property
    def decision(self) -> str:
        return DECISION.OMIT.value if self.omit else DECISION.INCLUDE.value

    @decision.setter
    def decision(self, value: str) -> None:
        try:
            e = DECISION.lookup(value)
            self.omit = e is DECISION.OMIT
        except ValueError:
            raise ValueError("decision was {}; must be one of {}".format(
                value, [DECISION.OMIT.value, DECISION.INCLUDE.value]))

    # -------------------------------------------------------------------------
    # Representations
    # -------------------------------------------------------------------------

    def __str__(self) -> str:
        """
        Return a string representation.
        """
        return ", ".join(["{}: {}".format(a, getattr(self, a))
                          for a in DataDictionaryRow.ROWNAMES])

    def get_signature(self) -> str:
        """
        Return a signature based on the source database/table/field.
        """
        return "{}.{}.{}".format(self.src_db, self.src_table, self.src_field)

    def get_dest_signature(self) -> str:
        return "{}.{}".format(self.dest_table, self.dest_field)

    def get_tsv(self) -> str:
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

    # -------------------------------------------------------------------------
    # Setting
    # -------------------------------------------------------------------------

    def set_from_dict(self, valuedict: Dict[str, Any]) -> None:
        """
        Set internal fields from a dict of elements representing a row from the
        TSV data dictionary file.
        """
        self.src_db = valuedict['src_db']
        self.src_table = valuedict['src_table']
        self.src_field = valuedict['src_field']
        self.src_datatype = valuedict['src_datatype'].upper()
        self.src_flags = valuedict['src_flags']  # a property
        self.scrub_src = SCRUBSRC.lookup(valuedict['scrub_src'])
        self.scrub_method = SCRUBMETHOD.lookup(valuedict['scrub_method'])
        self.decision = valuedict['decision']  # a property; sets self.omit
        self.inclusion_values = valuedict['inclusion_values']  # a property
        self.exclusion_values = valuedict['exclusion_values']  # a property
        self.alter_method = valuedict['alter_method']  # a property
        self.dest_table = valuedict['dest_table']
        self.dest_field = valuedict['dest_field']
        self.dest_datatype = valuedict['dest_datatype'].upper()
        self.index = INDEX.lookup(valuedict['index'])
        self.indexlen = convert_to_int(valuedict['indexlen'])
        self.comment = valuedict['comment']
        self._from_file = True
        self.check_valid()
    
    def _matches_tabledef(self, tabledef: str) -> bool:
        tr = regex.compile(fnmatch.translate(tabledef), regex.IGNORECASE)
        return tr.match(self.src_table)
    
    def matches_tabledef(self, tabledef: Union[str, List[str]]) -> bool:
        if isinstance(tabledef, str):
            return self._matches_tabledef(tabledef)
        elif not tabledef:
            return False
        else:  # list
            return any(self._matches_tabledef(td) for td in tabledef)

    def _matches_fielddef(self, fielddef: str) -> bool:
        t, c = split_db_table(fielddef)
        cr = regex.compile(fnmatch.translate(c), regex.IGNORECASE)
        if not t:
            return cr.match(self.src_field)
        tr = regex.compile(fnmatch.translate(t), regex.IGNORECASE)
        return tr.match(self.src_table) and cr.match(self.src_field)
        
    def matches_fielddef(self, fielddef: Union[str, List[str]]) -> bool:
        if isinstance(fielddef, str):
            return self._matches_fielddef(fielddef)
        elif not fielddef:
            return False
        else:  # list
            return any(self._matches_fielddef(fd) for fd in fielddef)

    def set_from_src_db_info(self,
                             db: str,
                             table: str,
                             field: str,
                             datatype_sqltext: str,
                             sqla_coltype: Column,
                             cfg: CONFIG_FWD_REF,
                             comment=None) -> None:
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
        if self.matches_fielddef(cfg.ddgen_pk_fields):
            self._pk = True
            self._constant = (
                (cfg.ddgen_constant_content or
                 self.matches_tabledef(cfg.ddgen_constant_content_tables)) and
                not self.matches_tabledef(cfg.ddgen_nonconstant_content_tables)
            )
            self._add_src_hash = not self._constant
            self._addition_only = (
                (cfg.ddgen_addition_only or
                 self.matches_tabledef(cfg.ddgen_addition_only_tables)) and
                not self.matches_tabledef(cfg.ddgen_deletion_possible_tables)
            )
        if self.matches_fielddef(cfg.ddgen_per_table_pid_field):
            self._primary_pid = True
        if self.matches_fielddef(cfg.ddgen_master_pid_fieldname):
            self._master_pid = True
        if self.matches_fielddef(cfg.ddgen_pid_defining_fieldnames):
            self._defines_primary_pids = True

        # Does the field contain sensitive data?
        if (self.matches_fielddef(cfg.ddgen_scrubsrc_patient_fields) or
                (self._primary_pid and
                 cfg.ddgen_add_per_table_pids_to_scrubber) or
                self._master_pid or
                self._defines_primary_pids):
            self.scrub_src = SCRUBSRC.PATIENT
        elif self.matches_fielddef(cfg.ddgen_scrubsrc_thirdparty_fields):
            self.scrub_src = SCRUBSRC.THIRDPARTY
        elif self.matches_fielddef(
                cfg.ddgen_scrubsrc_thirdparty_xref_pid_fields):
            self.scrub_src = SCRUBSRC.THIRDPARTY_XREF_PID
        else:
            self.scrub_src = None

        # Is it a mandatory scrubbing field?
        if self.matches_fielddef(cfg.ddgen_required_scrubsrc_fields):
            self._required_scrubber = True

        # What kind of sensitive data? Date, text, number, code?
        if not self.scrub_src:
            self.scrub_method = ""
        elif (self.scrub_src is SCRUBSRC.THIRDPARTY_XREF_PID or
                is_sqltype_numeric(datatype_sqltext) or
                self.matches_fielddef(cfg.ddgen_per_table_pid_field) or
                self.matches_fielddef(cfg.ddgen_master_pid_fieldname) or
                self.matches_fielddef(cfg.ddgen_scrubmethod_number_fields)):
            self.scrub_method = SCRUBMETHOD.NUMERIC
        elif (is_sqltype_date(datatype_sqltext) or
                self.matches_fielddef(cfg.ddgen_scrubmethod_date_fields)):
            self.scrub_method = SCRUBMETHOD.DATE
        elif self.matches_fielddef(cfg.ddgen_scrubmethod_code_fields):
            self.scrub_method = SCRUBMETHOD.CODE
        elif self.matches_fielddef(cfg.ddgen_scrubmethod_phrase_fields):
            self.scrub_method = SCRUBMETHOD.PHRASE
        else:
            self.scrub_method = SCRUBMETHOD.WORDS

        # Should we omit it (at least until a human has looked at the DD)?
        # In order:
        self.omit = cfg.ddgen_omit_by_default
        if self.matches_fielddef(cfg.ddgen_include_fields):
            self.omit = False
        if self.matches_fielddef(cfg.ddgen_omit_fields):
            self.omit = True
        if bool(self.scrub_src):
            self.omit = True
        if self._pk or self._primary_pid or self._master_pid:
            self.omit = False

        # Do we want to change the destination fieldname?
        if self._primary_pid:
            self.dest_field = self.config.research_id_fieldname
        elif self._master_pid:
            self.dest_field = self.config.master_research_id_fieldname
        else:
            self.dest_field = field
        if cfg.ddgen_force_lower_case:
            self.dest_field = self.dest_field.lower()
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
        extracting_text = False
        if self.matches_fielddef(cfg.ddgen_truncate_date_fields):
            self._alter_methods.append(AlterMethod(truncate_date=True))
        elif self.matches_fielddef(cfg.ddgen_filename_to_text_fields):
            self._alter_methods.append(AlterMethod(extract_from_filename=True))
            self.dest_datatype = LONGTEXT
            extracting_text = True
        elif self.matches_fielddef(cfg.bin2text_dict.keys()):
            for binfielddef, extfield in cfg.bin2text_dict.items():
                if self.matches_fielddef(binfielddef):
                    self._alter_methods.append(AlterMethod(
                        extract_from_blob=True,
                        extract_ext_field=extfield))
            self.dest_datatype = LONGTEXT
            extracting_text = True
        elif (is_sqltype_text_of_length_at_least(
                datatype_sqltext, cfg.ddgen_min_length_for_scrubbing) and
                not self._primary_pid and
                not self._master_pid and
                not self.matches_fielddef(
                    cfg.ddgen_safe_fields_exempt_from_scrubbing)):
            # Text field meeting the criteria to scrub
            self._alter_methods.append(AlterMethod(scrub=True))
        if extracting_text:
            # Scrub all extract-text fields, unless asked not to
            if (not self.matches_fielddef(
                    cfg.ddgen_safe_fields_exempt_from_scrubbing)):
                self._alter_methods.append(AlterMethod(scrub=True))
            # Set skip_if_text_extract_fails flag?
            if self.matches_fielddef(
                    cfg.ddgen_skip_row_if_extract_text_fails_fields):
                self._alter_methods.append(AlterMethod(
                    skip_if_text_extract_fails=True))

        # Manipulate the destination table name?
        # http://stackoverflow.com/questions/10017147
        self.dest_table = table
        if cfg.ddgen_force_lower_case:
            self.dest_table = self.dest_table.lower()
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
        elif self.matches_fielddef(cfg.ddgen_index_fields):
            self.index = INDEX.NORMAL
        else:
            self.index = ""

        self.indexlen = (
            DEFAULT_INDEX_LEN
            if (does_sqltype_require_index_len(self.dest_datatype) and
                self.index is not INDEX.FULLTEXT)
            else None
        )

        self.comment = comment
        self._from_file = False
        self.check_valid()

    def get_offender_description(self) -> str:
        offenderdest = "" if not self.omit else " -> {}".format(
            self.get_dest_signature())
        return "{}{}".format(self.get_signature(), offenderdest)

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def check_valid(self) -> None:
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

    def check_prohibited_fieldnames(self, fieldnames: Iterable[str]) -> None:
        if self.dest_field in fieldnames:
            log.exception(
                "Offending DD row [{}]: {}".format(
                    self.get_offender_description(), str(self)))
            raise ValueError("Prohibited dest_field name")

    def _check_valid(self) -> None:
        """
        Check internal validity and complain if invalid.
        """
        assert self.src_db, "Need src_db"
        assert self.src_table, "Need src_table"
        assert self.src_field, "Need src_field"
        assert self.src_datatype, "Need src_datatype"
        if not self.omit:
            assert self.dest_table, "Need dest_table"
            assert self.dest_field, "Need dest_field"

        if self.src_db not in self.config.get_source_db_names():
            raise ValueError(
                "Data dictionary row references non-existent source "
                "database")
        srccfg = self.config.sources[self.src_db].srccfg
        ensure_valid_table_name(self.src_table)
        ensure_valid_field_name(self.src_field)
        if len(self.src_table) > MYSQL_MAX_IDENTIFIER_LENGTH:
            log.warning(
                "Table name in {}.{} is too long for MySQL ({} characters > "
                "{} maximum".format(
                    self.src_table, self.src_field,
                    len(self.src_table), MYSQL_MAX_IDENTIFIER_LENGTH))
        if len(self.src_field) > MYSQL_MAX_IDENTIFIER_LENGTH:
            log.warning(
                "Field name in {}.{} is too long for MySQL ({} characters > "
                "{} maximum".format(
                    self.src_table, self.src_field,
                    len(self.src_field), MYSQL_MAX_IDENTIFIER_LENGTH))

        # REMOVED 2016-06-04; fails with complex SQL Server types, which can
        # look like 'NVARCHAR(10) COLLATE "Latin1_General_CI_AS"'.
        #
        # if not is_sqltype_valid(self.src_datatype):
        #     raise ValueError(
        #         "Field has invalid source data type: {}".format(
        #             self.src_datatype))

        if (self._primary_pid and
                not is_sqltype_integer(self.src_datatype)):
            raise ValueError(
                "All fields with src_field = {} should be integer, for work "
                "distribution purposes".format(self.src_field))

        if self._defines_primary_pids and not self._primary_pid:
            raise ValueError(
                "All fields with src_flags={} set must have src_flags={} "
                "set".format(SRCFLAG.DEFINES_PRIMARY_PIDS, SRCFLAG.PRIMARY_PID))

        if self._opt_out_info and not self.config.optout_col_values:
            raise ValueError(
                "Fields with src_flags={} exist, but config's "
                "optout_col_values setting is empty".format(SRCFLAG.OPT_OUT))

        if count_bool([self._primary_pid,
                       self._master_pid,
                       bool(self.alter_method)]) > 1:
            raise ValueError(
                "Field can be any ONE of: src_flags={}, src_flags={}, "
                "alter_method".format(SRCFLAG.PRIMARY_PID, SRCFLAG.MASTER_PID))

        if self._required_scrubber and not self.scrub_src:
            raise ValueError("If you specify src_flags={}, you must specify "
                             "scrub_src".format(SRCFLAG.REQUIRED_SCRUBBER))

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
            if self.matches_fielddef(srccfg.ddgen_per_table_pid_field):
                if not self._primary_pid:
                    raise ValueError(
                        "All fields with src_field={} used in output should "
                        "have src_flag={} set".format(self.src_field,
                                                      SRCFLAG.PRIMARY_PID))
                if self.dest_field != self.config.research_id_fieldname:
                    raise ValueError(
                        "Primary PID field should have "
                        "dest_field = {}".format(
                            self.config.research_id_fieldname))
            if (self.matches_fielddef(srccfg.ddgen_master_pid_fieldname) and
                    not self._master_pid):
                raise ValueError(
                    "All fields with src_field = {} used in output should have"
                    " src_flags={} set".format(
                        srccfg.ddgen_master_pid_fieldname,
                        SRCFLAG.MASTER_PID))

            for am in self._alter_methods:
                if am.truncate_date:
                    if not (is_sqltype_date(self.src_datatype) or
                            is_sqltype_text_over_one_char(self.src_datatype)):
                        raise ValueError("Can't set truncate_date for "
                                         "non-date/non-text field")
                if am.extract_from_filename:
                    if not is_sqltype_text_over_one_char(self.src_datatype):
                        raise ValueError(
                            "For alter_method = {ALTERMETHOD.FILENAME2TEXT}, "
                            "source field must contain filename and therefore "
                            "must be text type of >1 character".format(
                                ALTERMETHOD=ALTERMETHOD))
                if am.extract_from_blob:
                    if not is_sqltype_binary(self.src_datatype):
                        raise ValueError(
                            "For alter_method = {ALTERMETHOD.BIN2TEXT} or "
                            "{ALTERMETHOD.BIN2TEXT_SCRUB}, source field "
                            "must be of binary type".format(
                                ALTERMETHOD=ALTERMETHOD))

            # This error/warning too hard to be sure of with SQL Server odd
            # string types:
            # if self._scrub and not self._extract_text:
            #     if not is_sqltype_text_over_one_char(self.src_datatype):
            #         raise ValueError("Can't scrub in non-text field or "
            #                          "single-character text field")

            if ((self._primary_pid or self._master_pid) and
                    self.dest_datatype !=
                    self.config.sqltype_encrypted_pid_as_sql):
                raise ValueError(
                    "All src_flags={}/src_flags={} fields used in output must "
                    "have destination_datatype = {}".format(
                        SRCFLAG.PRIMARY_PID,
                        SRCFLAG.MASTER_PID,
                        self.config.sqltype_encrypted_pid_as_sql))

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
                        SRCFLAG.ADD_SRC_HASH,
                        SRCFLAG.PK))
            if self.index is not INDEX.UNIQUE:
                raise ValueError(
                    "src_flags={} fields require index=={}".format(
                        SRCFLAG.ADD_SRC_HASH,
                        INDEX.UNIQUE))
            if self._constant:
                raise ValueError(
                    "cannot mix {} flag with {} flag".format(
                        SRCFLAG.ADD_SRC_HASH,
                        SRCFLAG.CONSTANT))

        if self._constant:
            if not self._pk:
                raise ValueError(
                    "src_flags={} can only be set on "
                    "src_flags={} fields".format(
                        SRCFLAG.CONSTANT,
                        SRCFLAG.PK))
            if self.index is not INDEX.UNIQUE:
                raise ValueError(
                    "src_flags={} fields require index=={}".format(
                        SRCFLAG.CONSTANT,
                        INDEX.UNIQUE))

    # -------------------------------------------------------------------------
    # Anonymisation decisions
    # -------------------------------------------------------------------------

    def being_scrubbed(self) -> bool:
        return any(am.scrub for am in self._alter_methods)

    def contains_patient_info(self) -> bool:
        return bool(self.scrub_src) or self._primary_pid or self._master_pid

    def contains_vital_patient_info(self) -> bool:
        return bool(self.scrub_src)

    def required(self) -> bool:
        # return not self.omit or self.contains_patient_info()
        return not self.omit or self.contains_vital_patient_info()

    def skip_row_by_value(self, value: Any) -> bool:
        if self._inclusion_values and value not in self._inclusion_values:
            # log.debug("skipping row based on inclusion_values")
            return True
        if value in self._exclusion_values:
            # log.debug("skipping row based on exclusion_values")
            return True
        return False

    @property
    def required_scrubber(self) -> bool:
        return self._required_scrubber

    # -------------------------------------------------------------------------
    # SQLAlchemy types
    # -------------------------------------------------------------------------

    def set_src_sqla_coltype(self, sqla_coltype: Column) -> None:
        self._src_sqla_coltype = sqla_coltype

    def get_sqla_dest_coltype(self, default_dialect: Any = None) -> Column:
        dialect = (
            self.config.destdb.engine.dialect or
            default_dialect or
            self.config.get_default_dest_dialect()
        )
        if self.dest_datatype:
            # User (or our autogeneration process) wants to override
            # the type.
            return get_sqla_coltype_from_dialect_str(self.dest_datatype,
                                                     dialect)
        else:
            # Return the SQLAlchemy column type class determined from the
            # source database by reflection.
            # Will be autoconverted to the destination dialect.
            # With some exceptions, addressed as below:
            return convert_sqla_type_for_dialect(self._src_sqla_coltype,
                                                 dialect)
            
    def get_sqla_dest_column(self) -> Column:
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

    # -------------------------------------------------------------------------
    # Other
    # -------------------------------------------------------------------------

    def using_fulltext_index(self) -> bool:
        return self.index is INDEX.FULLTEXT


# =============================================================================
# DataDictionary
# =============================================================================

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
                ddr = DataDictionaryRow(self.config)
                try:
                    ddr.set_from_dict(valuedict)
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
        signatures = [ddr.get_signature() for ddr in self.rows]
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
                    ddr = DataDictionaryRow(self.config)
                    ddr.set_from_src_db_info(
                        pretty_dbname, tablename, columnname,
                        datatype_sqltext,
                        sqla_coltype,
                        cfg=cfg,
                        comment=comment)
                    new_rows.append(ddr)

                # Now, table-wide checks across all columns:
                is_patient_table = any(ddr.contains_patient_info()
                                       for ddr in new_rows)
                if not is_patient_table:
                    for ddr in new_rows:
                        ddr.remove_scrub_from_alter_methods()
                        # Pointless to scrub in a non-patient table

                # Now, filter out any rows that exist already:
                for ddr in new_rows:
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

                for r in rows:
                    if r.src_field not in db.metadata.tables[t].columns:
                        raise ValueError(
                            "Column {c} missing from table {t} in source "
                            "database {d}".format(c=r.src_field, t=t, d=d))

                    r.set_src_sqla_coltype(
                        db.metadata.tables[t].columns[r.src_field].type)
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
                            if not is_sqltype_text_over_one_char(
                                    extrow.src_datatype):
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
        
    def set_src_sql_coltypes(self, dialect: Any = None) -> None:
        dialect = (
            dialect or
            self.config.get_default_src_dialect()
        )
        for r in self.rows:
            str_coltype = r.src_datatype
            sqla_coltype = get_sqla_coltype_from_dialect_str(str_coltype,
                                                             dialect)
            # ("{} -> {}".format(str_coltype, sqla_coltype))
            r.set_src_sqla_coltype(sqla_coltype)

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
            columns.append(ddr.get_sqla_dest_column())
            if ddr.add_src_hash:
                columns.append(self.get_srchash_sqla_column())
            if ddr.primary_pid:
                columns.append(self.get_trid_sqla_column())
        return Table(tablename, metadata, *columns, **MYSQL_TABLE_ARGS)

    def get_srchash_sqla_column(self) -> Column:
        return Column(
            self.config.source_hash_fieldname,
            self.config.SqlTypeEncryptedPid,
            doc='Hashed amalgamation of all source fields'
        )

    def get_trid_sqla_column(self) -> Column:
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
