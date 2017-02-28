#!/usr/bin/env python
# crate_anon/anonymise/ddr.py

"""
===============================================================================
    Copyright (C) 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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
"""

# =============================================================================
# Imports
# =============================================================================

import ast
import logging
from typing import Any, List, Dict, Iterable, Union

from cardinal_pythonlib.rnc_db import (
    ensure_valid_field_name,
    ensure_valid_table_name,
    is_sqltype_integer,
    is_sqltype_valid,
)
from cardinal_pythonlib.rnc_lang import (
    convert_to_int,
    count_bool,
)
from sqlalchemy import Column
from sqlalchemy.sql.sqltypes import TypeEngine

# don't import config: circular dependency would have to be sorted out
from crate_anon.anonymise.altermethod import AlterMethod
from crate_anon.anonymise.constants import (
    ALTERMETHOD,
    DECISION,
    DEFAULT_INDEX_LEN,
    INDEX,
    MAX_IDENTIFIER_LENGTH,
    ODD_CHARS_TRANSLATE,
    SCRUBMETHOD,
    SCRUBSRC,
    SRCFLAG,
)
from crate_anon.common.sqla import (
    convert_sqla_type_for_dialect,
    does_sqlatype_merit_fulltext_index,
    does_sqlatype_require_index_len,
    giant_text_sqltype,
    get_sqla_coltype_from_dialect_str,
    is_sqlatype_binary,
    is_sqlatype_date,
    is_sqlatype_numeric,
    is_sqlatype_text_of_length_at_least,
    is_sqlatype_text_over_one_char,
)
import crate_anon.common.sql

log = logging.getLogger(__name__)


# =============================================================================
# DataDictionaryRow
# =============================================================================

DDR_FWD_REF = "DataDictionaryRow"
DATABASE_SAFE_CONFIG_FWD_REF = "DatabaseSafeConfig"
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

    def __init__(self) -> None:
        """
        Set up basic defaults.
        """
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

        self._inclusion_values = []  # type: List[Any]
        self._exclusion_values = []  # type: List[Any]

        self._alter_methods = []  # type: List[AlterMethod]

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

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
        return ''.join(str(x) for x in (
            SRCFLAG.PK if self._pk else '',
            SRCFLAG.ADD_SRC_HASH if self._add_src_hash else '',
            SRCFLAG.PRIMARY_PID if self._primary_pid else '',
            SRCFLAG.DEFINES_PRIMARY_PIDS if self._defines_primary_pids else '',
            SRCFLAG.MASTER_PID if self._master_pid else '',
            SRCFLAG.CONSTANT if self._constant else '',
            SRCFLAG.ADDITION_ONLY if self._addition_only else '',
            SRCFLAG.OPT_OUT if self._opt_out_info else '',
            SRCFLAG.REQUIRED_SCRUBBER if self._required_scrubber else '',
        ))

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

    @property
    def required_scrubber(self) -> bool:
        return self._required_scrubber

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
    # Comparisons
    # -------------------------------------------------------------------------

    def __lt__(self, other: DDR_FWD_REF) -> bool:
        return self.get_signature() < other.get_signature()

    def matches_tabledef(self, tabledef: Union[str, List[str]]) -> bool:
        return crate_anon.common.sql.matches_tabledef(self.src_table, tabledef)

    def matches_fielddef(self, fielddef: Union[str, List[str]]) -> bool:
        return crate_anon.common.sql.matches_fielddef(
            self.src_table, self.src_field, fielddef)

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

    def get_offender_description(self) -> str:
        offenderdest = "" if not self.omit else " -> {}".format(
            self.get_dest_signature())
        return "{}{}".format(self.get_signature(), offenderdest)

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
        self.scrub_src = SCRUBSRC.lookup(valuedict['scrub_src'],
                                         allow_none=True)
        self.scrub_method = SCRUBMETHOD.lookup(valuedict['scrub_method'],
                                               allow_none=True)
        self.decision = valuedict['decision']  # a property; sets self.omit
        self.inclusion_values = valuedict['inclusion_values']  # a property
        self.exclusion_values = valuedict['exclusion_values']  # a property
        self.alter_method = valuedict['alter_method']  # a property
        self.dest_table = valuedict['dest_table']
        self.dest_field = valuedict['dest_field']
        self.dest_datatype = valuedict['dest_datatype'].upper()
        self.index = INDEX.lookup(valuedict['index'], allow_none=True)
        self.indexlen = convert_to_int(valuedict['indexlen'])
        self.comment = valuedict['comment']
        self._from_file = True

    # -------------------------------------------------------------------------
    # Anonymisation decisions
    # -------------------------------------------------------------------------

    def being_scrubbed(self) -> bool:
        return any(am.scrub for am in self._alter_methods)

    def contains_patient_info(self) -> bool:
        return self._primary_pid or self._master_pid or bool(self.scrub_src)

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

    def get_alter_methods(self) -> List[AlterMethod]:
        return self._alter_methods

    def skip_row_if_extract_text_fails(self) -> bool:
        return any(x.skip_if_text_extract_fails for x in self._alter_methods)

    def get_extracting_text_altermethods(self):
        return [am.extract_text for am in self._alter_methods
                if am.extract_text]

    def remove_scrub_from_alter_methods(self) -> None:
        for sm in self._alter_methods:
            sm.scrub = False

    # -------------------------------------------------------------------------
    # Other decisions
    # -------------------------------------------------------------------------

    def using_fulltext_index(self) -> bool:
        return self.index is INDEX.FULLTEXT

    # -------------------------------------------------------------------------
    # SQLAlchemy types
    # -------------------------------------------------------------------------

    def get_src_sqla_coltype(self, config: CONFIG_FWD_REF):
        return self._src_sqla_coltype or get_sqla_coltype_from_dialect_str(
            self.src_datatype, config.get_src_dialect(self.src_db))

    def set_src_sqla_coltype(self, sqla_coltype: Column) -> None:
        self._src_sqla_coltype = sqla_coltype

    def get_dest_sqla_coltype(self, config: CONFIG_FWD_REF) -> TypeEngine:
        dialect = config.get_dest_dialect()
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
            return convert_sqla_type_for_dialect(
                coltype=self._src_sqla_coltype,
                dialect=dialect,
                expand_for_scrubbing=self.being_scrubbed())

    def get_dest_sqla_column(self, config: CONFIG_FWD_REF) -> Column:
        name = self.dest_field
        coltype = self.get_dest_sqla_coltype(config)
        comment = self.comment or ''
        kwargs = {'doc': comment}
        if self._pk:
            kwargs['primary_key'] = True
            kwargs['autoincrement'] = False
        if self.primary_pid:
            kwargs['nullable'] = False
        return Column(name, coltype, **kwargs)

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def check_valid(self, config: CONFIG_FWD_REF) -> None:
        """
        Check internal validity and complain if invalid, showing the source
        of the problem.
        """
        try:
            self._check_valid(config)
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

    def _check_valid(self, config: CONFIG_FWD_REF) -> None:
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
        src_sqla_coltype = self.get_src_sqla_coltype(config)
        dest_sqla_coltype = self.get_dest_sqla_coltype(config)

        if self.src_db not in config.get_source_db_names():
            raise ValueError(
                "Data dictionary row references non-existent source "
                "database")
        srccfg = config.sources[self.src_db].srccfg
        ensure_valid_table_name(self.src_table)
        ensure_valid_field_name(self.src_field)
        if len(self.src_table) > MAX_IDENTIFIER_LENGTH:
            log.warning(
                "Table name in {}.{} is too long for MySQL ({} characters > "
                "{} maximum".format(
                    self.src_table, self.src_field,
                    len(self.src_table), MAX_IDENTIFIER_LENGTH))
        if len(self.src_field) > MAX_IDENTIFIER_LENGTH:
            log.warning(
                "Field name in {}.{} is too long for MySQL ({} characters > "
                "{} maximum".format(
                    self.src_table, self.src_field,
                    len(self.src_field), MAX_IDENTIFIER_LENGTH))

        # REMOVED 2016-06-04; fails with complex SQL Server types, which can
        # look like 'NVARCHAR(10) COLLATE "Latin1_General_CI_AS"'.
        #
        # if not is_sqltype_valid(self.src_datatype):
        #     raise ValueError(
        #         "Field has invalid source data type: {}".format(
        #             self.src_datatype))

        # 2016-11-11: error message clarified
        if (self._primary_pid and
                not is_sqltype_integer(self.src_datatype)):
            raise ValueError(
                "All fields with src_field = {} should be integer, (a) for "
                "work distribution purposes, and (b) so we know the structure "
                "of our secret mapping table in advance.".format(
                    self.src_field))

        if self._defines_primary_pids and not self._primary_pid:
            raise ValueError(
                "All fields with src_flags={} set must have src_flags={} "
                "set".format(SRCFLAG.DEFINES_PRIMARY_PIDS, SRCFLAG.PRIMARY_PID))

        if self._opt_out_info and not config.optout_col_values:
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
            if self.dest_table == config.temporary_tablename:
                raise ValueError(
                    "Destination tables can't be named {}, as that's the "
                    "name set in the config's temporary_tablename "
                    "variable".format(config.temporary_tablename))
            ensure_valid_field_name(self.dest_field)
            if self.dest_field == config.source_hash_fieldname:
                raise ValueError(
                    "Destination fields can't be named {}, as that's the "
                    "name set in the config's source_hash_fieldname "
                    "variable".format(config.source_hash_fieldname))
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
                if self.dest_field != config.research_id_fieldname:
                    raise ValueError(
                        "Primary PID field should have "
                        "dest_field = {}".format(config.research_id_fieldname))
            if (self.matches_fielddef(srccfg.ddgen_master_pid_fieldname) and
                    not self._master_pid):
                raise ValueError(
                    "All fields with src_field = {} used in output should have"
                    " src_flags={} set".format(
                        srccfg.ddgen_master_pid_fieldname,
                        SRCFLAG.MASTER_PID))

            for am in self._alter_methods:
                if am.truncate_date:
                    if not (is_sqlatype_date(src_sqla_coltype) or
                            is_sqlatype_text_over_one_char(src_sqla_coltype)):
                        raise ValueError("Can't set truncate_date for "
                                         "non-date/non-text field")
                if am.extract_from_filename:
                    if not is_sqlatype_text_over_one_char(src_sqla_coltype):
                        raise ValueError(
                            "For alter_method = {ALTERMETHOD.FILENAME2TEXT}, "
                            "source field must contain filename and therefore "
                            "must be text type of >1 character".format(
                                ALTERMETHOD=ALTERMETHOD))
                if am.extract_from_blob:
                    if not is_sqlatype_binary(src_sqla_coltype):
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
                    config.sqltype_encrypted_pid_as_sql):
                raise ValueError(
                    "All src_flags={}/src_flags={} fields used in output must "
                    "have destination_datatype = {}".format(
                        SRCFLAG.PRIMARY_PID,
                        SRCFLAG.MASTER_PID,
                        config.sqltype_encrypted_pid_as_sql))

            if (self.index in (INDEX.NORMAL, INDEX.UNIQUE) and
                    self.indexlen is None and
                    does_sqlatype_require_index_len(dest_sqla_coltype)):
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
    # Other stuff requiring config or database info
    # -------------------------------------------------------------------------

    def set_from_src_db_info(self,
                             db: str,
                             table: str,
                             field: str,
                             datatype_sqltext: str,
                             sqla_coltype: TypeEngine,
                             dbconf: DATABASE_SAFE_CONFIG_FWD_REF,
                             config: CONFIG_FWD_REF,
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
        if self.matches_fielddef(dbconf.ddgen_pk_fields):
            self._pk = True
            self._constant = (
                (dbconf.ddgen_constant_content or
                 self.matches_tabledef(
                     dbconf.ddgen_constant_content_tables)) and
                not self.matches_tabledef(
                    dbconf.ddgen_nonconstant_content_tables)
            )
            self._add_src_hash = not self._constant
            self._addition_only = (
                (dbconf.ddgen_addition_only or
                 self.matches_tabledef(dbconf.ddgen_addition_only_tables)) and
                not self.matches_tabledef(dbconf.ddgen_deletion_possible_tables)
            )
        if self.matches_fielddef(dbconf.ddgen_per_table_pid_field):
            self._primary_pid = True
        if self.matches_fielddef(dbconf.ddgen_master_pid_fieldname):
            self._master_pid = True
        if self.matches_fielddef(dbconf.ddgen_pid_defining_fieldnames):
            self._defines_primary_pids = True

        # Does the field contain sensitive data?
        if (self._master_pid or
                self._defines_primary_pids or
                (self._primary_pid and
                 dbconf.ddgen_add_per_table_pids_to_scrubber) or
                self.matches_fielddef(dbconf.ddgen_scrubsrc_patient_fields)):
            self.scrub_src = SCRUBSRC.PATIENT
        elif self.matches_fielddef(dbconf.ddgen_scrubsrc_thirdparty_fields):
            self.scrub_src = SCRUBSRC.THIRDPARTY
        elif self.matches_fielddef(
                dbconf.ddgen_scrubsrc_thirdparty_xref_pid_fields):
            self.scrub_src = SCRUBSRC.THIRDPARTY_XREF_PID
        else:
            self.scrub_src = None

        # Is it a mandatory scrubbing field?
        if self.matches_fielddef(dbconf.ddgen_required_scrubsrc_fields):
            self._required_scrubber = True

        # What kind of sensitive data? Date, text, number, code?
        if not self.scrub_src:
            self.scrub_method = ""
        elif (self.scrub_src is SCRUBSRC.THIRDPARTY_XREF_PID or
                is_sqlatype_numeric(sqla_coltype) or
                self.matches_fielddef(dbconf.ddgen_per_table_pid_field) or
                self.matches_fielddef(dbconf.ddgen_master_pid_fieldname) or
                self.matches_fielddef(dbconf.ddgen_scrubmethod_number_fields)):
            self.scrub_method = SCRUBMETHOD.NUMERIC
        elif (is_sqlatype_date(sqla_coltype) or
                self.matches_fielddef(dbconf.ddgen_scrubmethod_date_fields)):
            self.scrub_method = SCRUBMETHOD.DATE
        elif self.matches_fielddef(dbconf.ddgen_scrubmethod_code_fields):
            self.scrub_method = SCRUBMETHOD.CODE
        elif self.matches_fielddef(dbconf.ddgen_scrubmethod_phrase_fields):
            self.scrub_method = SCRUBMETHOD.PHRASE
        else:
            self.scrub_method = SCRUBMETHOD.WORDS

        # Do we want to change the destination fieldname?
        if self._primary_pid:
            self.dest_field = config.research_id_fieldname
        elif self._master_pid:
            self.dest_field = config.master_research_id_fieldname
        else:
            self.dest_field = field
        if dbconf.ddgen_force_lower_case:
            self.dest_field = self.dest_field.lower()
        if dbconf.ddgen_convert_odd_chars_to_underscore:
            self.dest_field = str(self.dest_field)  # if this fails,
            # there's a Unicode problem
            self.dest_field = self.dest_field.translate(ODD_CHARS_TRANSLATE)
            # ... this will choke on a Unicode string

        # Do we want to change the destination field SQL type?
        if self._primary_pid or self._master_pid:
            self.dest_datatype = config.sqltype_encrypted_pid_as_sql
        else:
            self.dest_datatype = ''
        # ... and see also potential changes made below

        # How should we manipulate the destination?
        extracting_text = False
        if self.matches_fielddef(dbconf.ddgen_truncate_date_fields):
            self._alter_methods.append(AlterMethod(truncate_date=True))
        elif self.matches_fielddef(dbconf.ddgen_filename_to_text_fields):
            self._alter_methods.append(AlterMethod(extract_from_filename=True))
            self.dest_datatype = giant_text_sqltype(config.get_dest_dialect())
            extracting_text = True
        elif self.matches_fielddef(dbconf.bin2text_dict.keys()):
            for binfielddef, extfield in dbconf.bin2text_dict.items():
                if self.matches_fielddef(binfielddef):
                    self._alter_methods.append(AlterMethod(
                        extract_from_blob=True,
                        extract_ext_field=extfield))
            self.dest_datatype = giant_text_sqltype(config.get_dest_dialect())
            extracting_text = True
        elif (not self._primary_pid and
              not self._master_pid and
              is_sqlatype_text_of_length_at_least(
                  sqla_coltype, dbconf.ddgen_min_length_for_scrubbing) and
              not self.matches_fielddef(
                  dbconf.ddgen_safe_fields_exempt_from_scrubbing)):
            # Text field meeting the criteria to scrub
            self._alter_methods.append(AlterMethod(scrub=True))
        if extracting_text:
            # Scrub all extract-text fields, unless asked not to
            if (not self.matches_fielddef(
                    dbconf.ddgen_safe_fields_exempt_from_scrubbing)):
                self._alter_methods.append(AlterMethod(scrub=True))
            # Set skip_if_text_extract_fails flag?
            if self.matches_fielddef(
                    dbconf.ddgen_skip_row_if_extract_text_fails_fields):
                self._alter_methods.append(AlterMethod(
                    skip_if_text_extract_fails=True))

        # Manipulate the destination table name?
        # http://stackoverflow.com/questions/10017147
        self.dest_table = table
        if dbconf.ddgen_force_lower_case:
            self.dest_table = self.dest_table.lower()
        if dbconf.ddgen_convert_odd_chars_to_underscore:
            self.dest_table = str(self.dest_table)  # if this fails,
            # there's a Unicode problem
            self.dest_table = self.dest_table.translate(ODD_CHARS_TRANSLATE)

        # Should we index the destination?
        dest_sqla_type = self.get_dest_sqla_coltype(config)
        if self._pk:
            self.index = INDEX.UNIQUE
        elif (self._primary_pid or
              self._master_pid or
              self._defines_primary_pids or
              self.dest_field == config.research_id_fieldname):
            self.index = INDEX.NORMAL
        elif (dbconf.ddgen_allow_fulltext_indexing and
              does_sqlatype_merit_fulltext_index(dest_sqla_type)):
            self.index = INDEX.FULLTEXT
        elif self.matches_fielddef(dbconf.ddgen_index_fields):
            self.index = INDEX.NORMAL
        else:
            self.index = ""

        self.indexlen = (
            DEFAULT_INDEX_LEN
            if (self.index is not INDEX.FULLTEXT and
                does_sqlatype_require_index_len(dest_sqla_type))
            else None
        )

        # Should we omit it (at least until a human has looked at the DD)?
        # In descending order of priority:
        if self._pk or self._primary_pid or self._master_pid:
            # We always want PKs, and the translated PID/MPID (RID+TRID or
            # MRID respectively).
            self.omit = False
        elif self.matches_fielddef(dbconf.ddgen_omit_fields):  # explicit
            # Otherwise, explicit omission trumps everything else
            self.omit = True
        elif bool(self.scrub_src):
            # Scrub-source fields are generally sensitive and therefore worthy
            # of omission, EXCEPT that if a date is marked for truncation, the
            # user probably wants it (truncated) to come through!
            if any(am.truncate_date for am in self._alter_methods):
                self.omit = False
            else:
                self.omit = True
        elif self.matches_fielddef(dbconf.ddgen_include_fields):  # explicit
            # Explicit inclusion next.
            self.omit = False
        else:
            self.omit = dbconf.ddgen_omit_by_default

        self.comment = comment
        self._from_file = False
