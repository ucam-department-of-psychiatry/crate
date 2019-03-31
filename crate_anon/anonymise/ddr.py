#!/usr/bin/env python

"""
crate_anon/anonymise/ddr.py

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

**Data dictionary rows.**

"""

# =============================================================================
# Imports
# =============================================================================

import ast
import logging
from typing import Any, List, Dict, Iterable, TYPE_CHECKING, Union

from cardinal_pythonlib.convert import convert_to_int
from cardinal_pythonlib.lists import count_bool
from cardinal_pythonlib.rnc_db import (
    ensure_valid_field_name,
    ensure_valid_table_name,
    is_sqltype_valid,
)
from cardinal_pythonlib.sqlalchemy.schema import (
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
from sqlalchemy import Column
from sqlalchemy.sql.sqltypes import TypeEngine

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
import crate_anon.common.sql

if TYPE_CHECKING:
    from crate_anon.anonymise.config import Config

log = logging.getLogger(__name__)


# =============================================================================
# DataDictionaryRow
# =============================================================================

DDR_FWD_REF = "DataDictionaryRow"
DATABASE_SAFE_CONFIG_FWD_REF = "DatabaseSafeConfig"


class DataDictionaryRow(object):
    """
    Class representing a single row of a data dictionary (a DDR).
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

    def __init__(self, config: "Config") -> None:
        """
        Set up basic defaults.

        Args:
            config: :class:`crate_anon.anonymise.config.Config`
        """
        self.config = config
        self.src_db = None
        self.src_table = None
        self.src_field = None
        self.src_datatype = None  # in SQL string format
        # src_flags: a property; see below

        self._src_sqla_coltype = None

        self.scrub_src = None
        self.scrub_method = None

        # decision: a property; see below
        self.omit = False  # in the DD file, this is 'decision'
        # inclusion_values: a property; see below
        # exclusion_values: a property; see below
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
        """
        Returns the source database name, in lower case.
        """
        return self.src_db.lower()

    @property
    def src_table_lowercase(self) -> str:
        """
        Returns the source table name, in lower case.
        """
        return self.src_table.lower()

    @property
    def src_field_lowercase(self) -> str:
        """
        Returns the source field (column) name, in lower case.
        """
        return self.src_field.lower()

    @property
    def pk(self) -> bool:
        """
        Is the source field (and the destination field, for that matter) a
        primary key (PK)?
        """
        return self._pk

    @property
    def add_src_hash(self) -> bool:
        """
        Should we add a column to the destination that contains a hash of the
        contents of the whole source row (all fields)?
        """
        return self._add_src_hash

    @property
    def primary_pid(self) -> bool:
        """
        Does the source field contain the primary patient ID (PID)?

        (A typical example of a PID: "hospital number".)
        """
        return self._primary_pid

    @property
    def defines_primary_pids(self) -> bool:
        """
        Is this the field -- usually one in the entire source database -- that
        *defines* primary PIDs? Usually this is true for the "ID" column of
        the master patient table.
        """
        return self._defines_primary_pids

    @property
    def master_pid(self) -> bool:
        """
        Does this field contain the master patient ID (MPID)?

        (A typical example of an MPID: "NHS number".)
        """
        return self._master_pid

    @property
    def constant(self) -> bool:
        """
        Is the source field guaranteed not to change (for a given PK)?
        """
        return self._constant

    @property
    def addition_only(self) -> bool:
        """
        May we assume that records can only be added to this table, not
        deleted?

        This is a flag that may be applied to a PK row only.
        """
        return self._addition_only

    @property
    def opt_out_info(self) -> bool:
        """
        Does the field contain information about whether the patient wishes
        to opt out entirely from the anonymised database?

        (Whether the contents of the field means "opt out" or "don't opt out"
        depends on ``optout_col_values`` in the
        :class:`crate_anon.anonymise.config.Config`.)
        """
        return self._opt_out_info

    @property
    def src_flags(self) -> str:
        """
        Returns a string representation of the source flags.
        """
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
        """
        Takes a string representation of the source flags, and sets our
        internal flags accordingly.
        """
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
        """
        Returns a list of inclusion values (or an empty string if there are
        no such values).

        This slightly curious output format is used to create a TSV row (see
        :func:`get_tsv`) or to check in a "truthy" way whether we have
        inclusion values (see
        :func:`crate_anon.anonymise.anonymise.process_table`).
        """
        return self._inclusion_values or ''  # for TSV output

    @inclusion_values.setter
    def inclusion_values(self, value: str) -> None:
        """
        Set the inclusion values.

        Args:
            value:
                either something that is "falsy" (to set the inclusion values
                to an empty list) or something that evaluates to a Python
                iterable (e.g. list or tuple) via :func:`ast.literal_eval`.

                For example: ``[None, 0]``, or ``[True, 1, 'yes', 'true',
                'Yes', 'True']``.

        """
        if value:
            self._inclusion_values = ast.literal_eval(value) or []
        else:
            self._inclusion_values = []

    @property
    def exclusion_values(self) -> List[Any]:
        """
        Returns a list of exclusion values (or an empty string if there are
        no such values).

        This slightly curious output format is used to create a TSV row (see
        :func:`get_tsv`) or to check in a "truthy" way whether we have
        exclusion values (see
        :func:`crate_anon.anonymise.anonymise.process_table`).
        """
        return self._exclusion_values or ''  # for TSV output

    @exclusion_values.setter
    def exclusion_values(self, value: str) -> None:
        """
        Set the exclusion values.

        Args:
            value:
                either something that is "falsy" (to set the inclusion values
                to an empty list) or something that evaluates to a Python
                iterable (e.g. list or tuple) via :func:`ast.literal_eval`.

                For example: ``[None, 0]``, or ``[True, 1, 'yes', 'true',
                'Yes', 'True']``.

        """
        if value:
            self._exclusion_values = ast.literal_eval(value) or []
        else:
            self._exclusion_values = []

    @property
    def required_scrubber(self) -> bool:
        """
        Is this a "required scrubber" field?

        A "required scrubber" is a field that must provide at least one
        non-NULL value for each patient, or the patient won't get processed.
        (For example, you might want to omit a patient if you can't be certain
        about their surname for anonymisation.)
        """
        return self._required_scrubber

    @property
    def alter_method(self) -> str:
        """
        Return the ``alter_method`` string from the working fields.
        """
        return ",".join(filter(
            None, (x.get_text() for x in self._alter_methods)))

    @alter_method.setter
    def alter_method(self, value: str) -> None:
        """
        Convert the ``alter_method`` string (from the data dictionary) to a
        bunch of Boolean/simple fields internally.
        """
        # Get the list of elements in the user's order.
        self._alter_methods = []
        elements = [x.strip() for x in value.split(",") if x]
        methods = []
        for e in elements:
            methods.append(AlterMethod(config=self.config,
                                       text_value=e))
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
                raise ValueError(f"Date truncation must stand alone in "
                                 f"alter_method: {value}")
            if am.extract_text and have_text_extraction:
                raise ValueError(f"Can only have one text extraction method "
                                 f"in {value}")
            if am.truncate_date:
                have_truncate_date = True
            if am.extract_text:
                have_text_extraction = True

    @property
    def from_file(self) -> bool:
        """
        Was this DDR loaded from a file (rather than, say, autogenerated from
        a database)?
        """
        return self._from_file

    @property
    def decision(self) -> str:
        """
        Should we include the field in the destination?

        Returns:
            ``"OMIT"`` or ``"include``.
        """
        return DECISION.OMIT.value if self.omit else DECISION.INCLUDE.value

    @decision.setter
    def decision(self, value: str) -> None:
        """
        Sets the internal ``omit`` flag from the input (usually taken from the
        data dictionary file).

        Args:
            value: ``"OMIT"`` or ``"include``.
        """
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
        """
        Defines an order of DDRs based on their source field's signature.
        """
        return self.get_signature() < other.get_signature()

    def matches_tabledef(self, tabledef: Union[str, List[str]]) -> bool:
        """
        Does our source table match the wildcard-based table definition?

        Args:
            tabledef: ``fnmatch``-style pattern (e.g.
                ``"patient_address_table_*"``), or list of them
        """
        return crate_anon.common.sql.matches_tabledef(self.src_table, tabledef)

    def matches_fielddef(self, fielddef: Union[str, List[str]]) -> bool:
        """
        Does our source table/field match the wildcard-based field definition?

        Args:
            fielddef: ``fnmatch``-style pattern (e.g. ``"system_table.*"`` or
                ``"*.nhs_number"``), or list of them
        """
        return crate_anon.common.sql.matches_fielddef(
            self.src_table, self.src_field, fielddef)

    # -------------------------------------------------------------------------
    # Representations
    # -------------------------------------------------------------------------

    def __str__(self) -> str:
        """
        Returns a string representation of the DDR.
        """
        return ", ".join([f"{a}: {getattr(self, a)}"
                          for a in DataDictionaryRow.ROWNAMES])

    def get_signature(self) -> str:
        """
        Returns a signature based on the source database/table/field, in the
        format ``db.table.column``.
        """
        return f"{self.src_db}.{self.src_table}.{self.src_field}"

    def get_dest_signature(self) -> str:
        """
        Returns a signature based on the destination table/field, in the format
        ``table.column``.
        """
        return f"{self.dest_table}.{self.dest_field}"

    def get_offender_description(self) -> str:
        """
        Get a string used to describe this DDR (in terms of its
        source/destination fields) if it does something wrong.
        """
        offenderdest = (
            "" if not self.omit else f" -> {self.get_dest_signature()}"
        )
        return f"{self.get_signature()}{offenderdest}"

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
        # noinspection PyAttributeOutsideInit
        self.src_flags = valuedict['src_flags']  # a property
        self.scrub_src = SCRUBSRC.lookup(valuedict['scrub_src'],
                                         allow_none=True)
        self.scrub_method = SCRUBMETHOD.lookup(valuedict['scrub_method'],
                                               allow_none=True)
        # noinspection PyAttributeOutsideInit
        self.decision = valuedict['decision']  # a property; sets self.omit
        # noinspection PyAttributeOutsideInit
        self.inclusion_values = valuedict['inclusion_values']  # a property
        # noinspection PyAttributeOutsideInit
        self.exclusion_values = valuedict['exclusion_values']  # a property
        # noinspection PyAttributeOutsideInit
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
        """
        Is the field being scrubbed as it passes from source to destination?
        """
        return any(am.scrub for am in self._alter_methods)

    def contains_patient_info(self) -> bool:
        """
        Does the field contain patient information? That means any of:

        - primary PID
        - MPID
        - scrub-source (sensitive) information
        """
        return self._primary_pid or self._master_pid or bool(self.scrub_src)

    def contains_vital_patient_info(self) -> bool:
        """
        Does the field contain vital patient information? That means:

        - scrub-source (sensitive) information
        """
        return bool(self.scrub_src)

    def required(self) -> bool:
        """
        Is the field required? That means any of:

        - chosen by the user to be translated into the destination
        - contains vital patient information (scrub-source information)
        """
        # return not self.omit or self.contains_patient_info()
        return not self.omit or self.contains_vital_patient_info()

    def skip_row_by_value(self, value: Any) -> bool:
        """
        Should we skip this row, because the value is one of the row's
        exclusion values, or the row has inclusion values and the value isn't
        one of them?

        Args:
            value: value to test
        """
        if self._inclusion_values and value not in self._inclusion_values:
            # log.debug("skipping row based on inclusion_values")
            return True
        if value in self._exclusion_values:
            # log.debug("skipping row based on exclusion_values")
            return True
        return False

    def get_alter_methods(self) -> List[AlterMethod]:
        """
        Return all alteration methods to be applied.

        Returns:
            list of :class:`crate_anon.anonymise.altermethod.AlterMethod`
            objects

        """
        return self._alter_methods

    def skip_row_if_extract_text_fails(self) -> bool:
        """
        Should we skip the row if processing the row involves extracting text
        and that process fails?
        """
        return any(x.skip_if_text_extract_fails for x in self._alter_methods)

    def get_extracting_text_altermethods(self) -> List[AlterMethod]:
        """
        Return all alteration methods that involve text extraction.

        Returns:
            list of :class:`crate_anon.anonymise.altermethod.AlterMethod`
            objects
        """
        return [am for am in self._alter_methods if am.extract_text]

    def remove_scrub_from_alter_methods(self) -> None:
        """
        Prevent this row from being scrubbed, by removing any "scrub" method
        from among its alteration methods.
        """
        log.debug(
            f"remove_scrub_from_alter_methods [used for non-patient tables]: "
            f"{self.get_signature()}")
        for sm in self._alter_methods:
            sm.scrub = False

    # -------------------------------------------------------------------------
    # Other decisions
    # -------------------------------------------------------------------------

    def using_fulltext_index(self) -> bool:
        """
        Should the destination field have a full-text index?
        """
        return self.index is INDEX.FULLTEXT

    # -------------------------------------------------------------------------
    # SQLAlchemy types
    # -------------------------------------------------------------------------

    def get_src_sqla_coltype(self) -> TypeEngine:
        """
        Returns the SQLAlchemy column type of the source column.
        """
        return self._src_sqla_coltype or get_sqla_coltype_from_dialect_str(
            self.src_datatype, self.config.get_src_dialect(self.src_db))

    def set_src_sqla_coltype(self, sqla_coltype: TypeEngine) -> None:
        """
        Sets the SQLAlchemy column type of the source column.
        """
        self._src_sqla_coltype = sqla_coltype

    def get_dest_sqla_coltype(self) -> TypeEngine:
        """
        Returns the SQLAlchemy column type of the destination column.
        """
        dialect = self.config.get_dest_dialect()
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
                coltype=self.get_src_sqla_coltype(),
                dialect=dialect,
                expand_for_scrubbing=self.being_scrubbed())

    def get_dest_sqla_column(self) -> Column:
        """
        Returns an SQLAlchemy :class:`sqlalchemy.sql.schema.Column` for the
        destination column.
        """
        name = self.dest_field
        coltype = self.get_dest_sqla_coltype()
        comment = self.comment or ''
        kwargs = {
            'doc': comment,
            # When SQLAlchemy 1.2 released, add this:
            # 'comment': comment,
            # https://bitbucket.org/zzzeek/sqlalchemy/issues/1546/feature-request-commenting-db-objects  # noqa
        }
        if self._pk:
            kwargs['primary_key'] = True
            kwargs['autoincrement'] = False
        if self.primary_pid:
            kwargs['nullable'] = False
        return Column(name, coltype, **kwargs)

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    def check_valid(self) -> None:
        """
        Check internal validity and complain if invalid, showing the source
        of the problem.

        Raises:
            :exc:`AssertionError`, :exc:`ValueError`
        """
        try:
            self._check_valid()
        except (AssertionError, ValueError):
            log.exception(
                f"Offending DD row [{self.get_offender_description()}]: "
                f"{str(self)}")
            raise

    def check_prohibited_fieldnames(
            self, prohibited_fieldnames: Iterable[str]) -> None:
        """
        Check that the destination field isn't a prohibited one.

        Args:
            prohibited_fieldnames: list of prohibited fieldnames

        Raises:
            :exc:`ValueError` if there's a problem.

        """
        if self.dest_field in prohibited_fieldnames:
            log.exception(
                f"Offending DD row [{self.get_offender_description()}]: "
                f"{str(self)}")
            raise ValueError("Prohibited dest_field name")

    def _check_valid(self) -> None:
        """
        Check internal validity and complain if invalid.

        Raises:
            :exc:`AssertionError`, :exc:`ValueError`
        """
        assert self.src_db, "Need src_db"
        assert self.src_table, "Need src_table"
        assert self.src_field, "Need src_field"
        assert self.src_datatype, "Need src_datatype"
        if not self.omit:
            assert self.dest_table, "Need dest_table"
            assert self.dest_field, "Need dest_field"
        src_sqla_coltype = self.get_src_sqla_coltype()
        dest_sqla_coltype = self.get_dest_sqla_coltype()

        if self.src_db not in self.config.get_source_db_names():
            raise ValueError(
                "Data dictionary row references non-existent source "
                "database")
        srccfg = self.config.sources[self.src_db].srccfg
        ensure_valid_table_name(self.src_table)
        ensure_valid_field_name(self.src_field)
        if len(self.src_table) > MAX_IDENTIFIER_LENGTH:
            log.warning(
                f"Table name in {self.src_table}.{self.src_field} is too long "
                f"for MySQL ({len(self.src_table)} characters > "
                f"{MAX_IDENTIFIER_LENGTH} maximum")
        if len(self.src_field) > MAX_IDENTIFIER_LENGTH:
            log.warning(
                f"Field name in {self.src_table}.{self.src_field} is too long "
                f"for MySQL ({len(self.src_field)} characters > "
                f"{MAX_IDENTIFIER_LENGTH} maximum")

        # REMOVED 2016-06-04; fails with complex SQL Server types, which can
        # look like 'NVARCHAR(10) COLLATE "Latin1_General_CI_AS"'.
        #
        # if not is_sqltype_valid(self.src_datatype):
        #     raise ValueError(
        #         "Field has invalid source data type: {}".format(
        #             self.src_datatype))

        # 2016-11-11: error message clarified
        # 2017-05-06: check removed; we can now handle non-integer PIDs
        #
        # if ((self._primary_pid or self._master_pid) and
        #         not is_sqltype_integer(self.src_datatype)):
        #     raise ValueError(
        #         "For {}: All fields with src_flags={} or src_flags={} set "
        #         "should be integer, (a) for work distribution purposes, and "
        #         "(b) so we know the structure of our secret mapping table "
        #         "in advance.".format(self.src_field,
        #                              SRCFLAG.PRIMARY_PID,
        #                              SRCFLAG.MASTER_PID))

        if self._defines_primary_pids and not self._primary_pid:
            raise ValueError(
                f"All fields with src_flags={SRCFLAG.DEFINES_PRIMARY_PIDS} "
                f"set must have src_flags={SRCFLAG.PRIMARY_PID} set")

        if self._opt_out_info and not self.config.optout_col_values:
            raise ValueError(
                f"Fields with src_flags={SRCFLAG.OPT_OUT} exist, but config's "
                f"optout_col_values setting is empty")

        if count_bool([self._primary_pid,
                       self._master_pid,
                       bool(self.alter_method)]) > 1:
            raise ValueError(
                f"Field can be any ONE of: src_flags={SRCFLAG.PRIMARY_PID}, "
                f"src_flags={SRCFLAG.MASTER_PID}, alter_method")

        if self._required_scrubber and not self.scrub_src:
            raise ValueError(
                f"If you specify src_flags={SRCFLAG.REQUIRED_SCRUBBER}, "
                f"you must specify scrub_src")

        if self._add_src_hash:
            if not self._pk:
                raise ValueError(
                    f"src_flags={SRCFLAG.ADD_SRC_HASH} can only be set on "
                    f"src_flags={SRCFLAG.PK} fields")
            if self.index is not INDEX.UNIQUE:
                raise ValueError(
                    f"src_flags={SRCFLAG.ADD_SRC_HASH} fields require "
                    f"index=={INDEX.UNIQUE}")
            if self._constant:
                raise ValueError(
                    f"cannot mix {SRCFLAG.ADD_SRC_HASH} flag with "
                    f"{SRCFLAG.CONSTANT} flag")

        if self._constant:
            if not self._pk:
                raise ValueError(
                    f"src_flags={SRCFLAG.CONSTANT} can only be set on "
                    f"src_flags={SRCFLAG.PK} fields")
            if self.index is not INDEX.UNIQUE:
                raise ValueError(
                    f"src_flags={SRCFLAG.CONSTANT} fields require "
                    f"index=={INDEX.UNIQUE}")

        if self._addition_only:
            if not self._pk:
                raise ValueError(
                    f"src_flags={SRCFLAG.ADDITION_ONLY} can only be set on "
                    f"src_flags={SRCFLAG.PK} fields")

        if self.omit:
            return

        # ---------------------------------------------------------------------
        # Below here: checks only applying to non-omitted columns
        # ---------------------------------------------------------------------
        ensure_valid_table_name(self.dest_table)
        if self.dest_table == self.config.temporary_tablename:
            raise ValueError(
                f"Destination tables can't be named "
                f"{self.config.temporary_tablename}, as that's the name set "
                f"in the config's temporary_tablename variable")
        ensure_valid_field_name(self.dest_field)
        if self.dest_field == self.config.source_hash_fieldname:
            raise ValueError(
                f"Destination fields can't be named "
                f"{self.config.source_hash_fieldname}, as that's the name set "
                f"in the config's source_hash_fieldname variable")
        if self.dest_datatype and not is_sqltype_valid(self.dest_datatype):
            raise ValueError(
                f"Field has invalid destination data type: "
                f"{self.dest_datatype}")
        if self.matches_fielddef(srccfg.ddgen_per_table_pid_field):
            if not self._primary_pid:
                raise ValueError(
                    f"All fields with src_field={self.src_field} used in "
                    f"output should have src_flag={SRCFLAG.PRIMARY_PID} set")
            if self.dest_field != self.config.research_id_fieldname:
                raise ValueError(
                    f"Primary PID field should have dest_field = "
                    f"{self.config.research_id_fieldname}")
        if (self.matches_fielddef(srccfg.ddgen_master_pid_fieldname) and
                not self._master_pid):
            raise ValueError(
                f"All fields with src_field = "
                f"{srccfg.ddgen_master_pid_fieldname} used in output should "
                f"have src_flags={SRCFLAG.MASTER_PID} set")

        for am in self._alter_methods:
            if am.truncate_date:
                if not (is_sqlatype_date(src_sqla_coltype) or
                        is_sqlatype_text_over_one_char(src_sqla_coltype)):
                    raise ValueError("Can't set truncate_date for "
                                     "non-date/non-text field")
            if am.extract_from_filename:
                if not is_sqlatype_text_over_one_char(src_sqla_coltype):
                    raise ValueError(
                        f"For alter_method = {ALTERMETHOD.FILENAME_TO_TEXT}, "
                        f"source field must contain a filename and therefore "
                        f"must be text type of >1 character")
            if am.extract_from_blob:
                if not is_sqlatype_binary(src_sqla_coltype):
                    raise ValueError(
                        f"For alter_method = {ALTERMETHOD.BINARY_TO_TEXT}, "
                        f"source field must be of binary type")

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
                f"All src_flags={SRCFLAG.PRIMARY_PID}/"
                f"src_flags={SRCFLAG.MASTER_PID} fields used in output must "
                f"have destination_datatype = "
                f"{self.config.sqltype_encrypted_pid_as_sql}")

        if (self.index in (INDEX.NORMAL, INDEX.UNIQUE) and
                self.indexlen is None and
                does_sqlatype_require_index_len(dest_sqla_coltype)):
            raise ValueError(
                "Must specify indexlen to index a TEXT or BLOB field")

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
                             comment: str = None) -> None:
        """
        Set up this DDR from a field in the source database.

        Args:
            db: source database name
            table: source table name
            field: source field (column) name
            datatype_sqltext: string SQL type, e.g. ``"VARCHAR(100)"``
            sqla_coltype: SQLAlchemy column type, e.g. ``Integer()``
            dbconf: :class:`crate_anon.anonymise.config.DatabaseSafeConfig`
            comment: textual comment
        """
        self.src_db = db
        self.src_table = table
        self.src_field = field
        self.src_datatype = datatype_sqltext
        self._src_sqla_coltype = sqla_coltype
        self._pk = False
        self._add_src_hash = False
        self._primary_pid = False
        self._defines_primary_pids = False
        self._master_pid = False
        self._constant = False
        self._addition_only = False
        self.comment = comment
        self._from_file = False

        # ---------------------------------------------------------------------
        # Is the field special, such as a PK?
        # ---------------------------------------------------------------------
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

        # ---------------------------------------------------------------------
        # Does it indicate the patient wishes to opt out entirely?
        # ---------------------------------------------------------------------
        if self.matches_fielddef(dbconf.ddgen_patient_opt_out_fields):
            self._opt_out_info = True

        # ---------------------------------------------------------------------
        # Does the field contain sensitive data?
        # ---------------------------------------------------------------------
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

        # ---------------------------------------------------------------------
        # Is it a mandatory scrubbing field?
        # ---------------------------------------------------------------------
        if self.matches_fielddef(dbconf.ddgen_required_scrubsrc_fields):
            self._required_scrubber = True

        # ---------------------------------------------------------------------
        # What kind of sensitive data? Date, text, number, code?
        # ---------------------------------------------------------------------
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

        # ---------------------------------------------------------------------
        # Do we want to change the destination fieldname?
        # ---------------------------------------------------------------------
        if self._primary_pid:
            self.dest_field = self.config.research_id_fieldname
        elif self._master_pid:
            self.dest_field = self.config.master_research_id_fieldname
        else:
            self.dest_field = field
        if dbconf.ddgen_force_lower_case:
            self.dest_field = self.dest_field.lower()
        if dbconf.ddgen_convert_odd_chars_to_underscore:
            self.dest_field = str(self.dest_field)  # if this fails,
            # there's a Unicode problem
            self.dest_field = self.dest_field.translate(ODD_CHARS_TRANSLATE)
            # ... this will choke on a Unicode string

        # ---------------------------------------------------------------------
        # Do we want to change the destination field SQL type?
        # ---------------------------------------------------------------------
        if self._primary_pid or self._master_pid:
            self.dest_datatype = self.config.sqltype_encrypted_pid_as_sql
        else:
            self.dest_datatype = ''
        # ... and see also potential changes made below

        # ---------------------------------------------------------------------
        # How should we manipulate the destination?
        # ---------------------------------------------------------------------
        extracting_text = False
        if self.matches_fielddef(dbconf.ddgen_truncate_date_fields):
            self._alter_methods.append(AlterMethod(config=self.config,
                                                   truncate_date=True))
        elif self.matches_fielddef(dbconf.ddgen_filename_to_text_fields):
            self._alter_methods.append(AlterMethod(config=self.config,
                                                   extract_from_filename=True))
            self.dest_datatype = giant_text_sqltype(
                self.config.get_dest_dialect())
            extracting_text = True
        elif self.matches_fielddef(dbconf.bin2text_dict.keys()):
            for binfielddef, extfield in dbconf.bin2text_dict.items():
                if self.matches_fielddef(binfielddef):
                    self._alter_methods.append(AlterMethod(
                        config=self.config,
                        extract_from_blob=True,
                        extract_ext_field=extfield))
            self.dest_datatype = giant_text_sqltype(
                self.config.get_dest_dialect())
            extracting_text = True
        elif (not self._primary_pid and
              not self._master_pid and
              is_sqlatype_text_of_length_at_least(
                  sqla_coltype, dbconf.ddgen_min_length_for_scrubbing) and
              not self.matches_fielddef(
                  dbconf.ddgen_safe_fields_exempt_from_scrubbing)):
            # Text field meeting the criteria to scrub
            self._alter_methods.append(AlterMethod(config=self.config,
                                                   scrub=True))
        if extracting_text:
            # Scrub all extract-text fields, unless asked not to
            if (not self.matches_fielddef(
                    dbconf.ddgen_safe_fields_exempt_from_scrubbing)):
                self._alter_methods.append(AlterMethod(config=self.config,
                                                       scrub=True))
            # Set skip_if_text_extract_fails flag?
            if self.matches_fielddef(
                    dbconf.ddgen_skip_row_if_extract_text_fails_fields):
                self._alter_methods.append(AlterMethod(
                    config=self.config,
                    skip_if_text_extract_fails=True))

        for fieldspec, cfg_section in dbconf.ddgen_extra_hash_fields.items():
            if self.matches_fielddef(fieldspec):
                self._alter_methods.append(AlterMethod(
                    config=self.config,
                    hash_=True,
                    hash_config_section=cfg_section
                ))

        # ---------------------------------------------------------------------
        # Manipulate the destination table name?
        # ---------------------------------------------------------------------
        # http://stackoverflow.com/questions/10017147
        self.dest_table = table
        if dbconf.ddgen_force_lower_case:
            self.dest_table = self.dest_table.lower()
        if dbconf.ddgen_convert_odd_chars_to_underscore:
            self.dest_table = str(self.dest_table)
            # ... if this fails, there's a Unicode problem
            self.dest_table = self.dest_table.translate(ODD_CHARS_TRANSLATE)
        for suffix in dbconf.ddgen_rename_tables_remove_suffixes:
            if self.dest_table.endswith(suffix):
                self.dest_table = self.dest_table[:-len(suffix)]  # remove it
                break  # only remove one suffix!

        # ---------------------------------------------------------------------
        # Should we index the destination?
        # ---------------------------------------------------------------------
        dest_sqla_type = self.get_dest_sqla_coltype()
        if self._pk:
            self.index = INDEX.UNIQUE
        elif (self._primary_pid or
              self._master_pid or
              self._defines_primary_pids or
              self.dest_field == self.config.research_id_fieldname):
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

        # ---------------------------------------------------------------------
        # Should we omit it (at least until a human has looked at the DD)?
        # ---------------------------------------------------------------------
        # In descending order of priority:
        if self.matches_fielddef(dbconf.ddgen_omit_fields):  # explicit
            # Explicit omission trumps everything else
            # (There are rare occasions with "additional" databases where we
            # may want to omit a PK/PID/MPID field.)
            self.omit = True
        elif self._pk or self._primary_pid or self._master_pid:
            # We always want PKs, and the translated PID/MPID (RID+TRID or
            # MRID respectively).
            self.omit = False
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
