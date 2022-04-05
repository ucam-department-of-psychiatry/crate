#!/usr/bin/env python

"""
crate_anon/anonymise/ddr.py

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

**Data dictionary rows.**

"""

# =============================================================================
# Imports
# =============================================================================

import ast
import logging
from typing import Any, List, Dict, Iterable, Optional, TYPE_CHECKING, Union

from cardinal_pythonlib.convert import convert_to_int
from cardinal_pythonlib.lists import count_bool
from cardinal_pythonlib.sql.validation import (
    ensure_valid_field_name,
    ensure_valid_table_name,
    is_sqltype_valid,
)
from cardinal_pythonlib.sqlalchemy.dialect import SqlaDialectName
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
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.sql.sqltypes import TypeEngine

from crate_anon.anonymise.altermethod import AlterMethod
from crate_anon.anonymise.constants import (
    AlterMethodType,
    AnonymiseConfigKeys,
    Decision,
    DEFAULT_INDEX_LEN,
    IndexType,
    MYSQL_MAX_IDENTIFIER_LENGTH,
    ODD_CHARS_TRANSLATE,
    ScrubMethod,
    ScrubSrc,
    SQLSERVER_MAX_IDENTIFIER_LENGTH,
    SrcFlag,
)
from crate_anon.common.sql import (
    coltype_length_if_text,
    is_sql_column_type_textual,
    matches_fielddef,
    matches_tabledef,
    SQLTYPE_DATE,
)

if TYPE_CHECKING:
    from crate_anon.anonymise.config import Config, DatabaseSafeConfig

log = logging.getLogger(__name__)


# =============================================================================
# Helper functions
# =============================================================================


def warn_if_identifier_long(
    table: str, column: str, dest_dialect: Optional[str]
) -> None:
    """
    Warns about identifiers that are too long for specific database engines.
    """
    prettyname_dialectname_maxlen = (
        ("MySQL", SqlaDialectName.MYSQL, MYSQL_MAX_IDENTIFIER_LENGTH),
        ("SQL Server", SqlaDialectName.MSSQL, SQLSERVER_MAX_IDENTIFIER_LENGTH),
    )
    description_value = (
        ("Table", table),
        ("Column", column),
    )
    for prettyname, dialect_name, maxlen in prettyname_dialectname_maxlen:
        if dest_dialect is not None and dest_dialect != dialect_name:
            # We know our destination dialect and it's not the one we're
            # considering.
            continue
        for description, value in description_value:
            if len(value) > maxlen:
                log.warning(
                    f"{description} name in {table!r}.{column!r} "
                    f"is too long for {prettyname} "
                    f"({len(value)} characters > {maxlen} maximum)"
                )


# =============================================================================
# DataDictionaryRow
# =============================================================================


class DataDictionaryRow(object):
    """
    Class representing a single row of a data dictionary (a DDR).
    """

    # For attribute/config references:
    SRC_DB = "src_db"
    SRC_TABLE = "src_table"
    SRC_FIELD = "src_field"
    SRC_DATAFILE = "src_datatype"
    SRC_FLAGS = "src_flags"

    SCRUB_SRC = "scrub_src"
    SCRUB_METHOD = "scrub_method"

    DECISION = "decision"
    INCLUSION_VALUES = "inclusion_values"
    EXCLUSION_VALUES = "exclusion_values"
    ALTER_METHOD = "alter_method"

    DEST_TABLE = "dest_table"
    DEST_FIELD = "dest_field"
    DEST_DATATYPE = "dest_datatype"
    INDEX = "index"
    INDEXLEN = "indexlen"
    COMMENT = "comment"

    ROWNAMES = [
        SRC_DB,
        SRC_TABLE,
        SRC_FIELD,
        SRC_DATAFILE,
        SRC_FLAGS,
        SCRUB_SRC,
        SCRUB_METHOD,
        DECISION,
        INCLUSION_VALUES,
        EXCLUSION_VALUES,
        ALTER_METHOD,
        DEST_TABLE,
        DEST_FIELD,
        DEST_DATATYPE,
        INDEX,
        INDEXLEN,
        COMMENT,
    ]
    ENUM_ROWNAMES = (INDEX, SCRUB_SRC, SCRUB_METHOD)

    def __init__(self, config: "Config") -> None:
        """
        Set up basic defaults.

        Args:
            config: :class:`crate_anon.anonymise.config.Config`
        """
        self.config = config

        # In the order of ROWNAMES:
        self.src_db = None  # type: Optional[str]
        self.src_table = None  # type: Optional[str]
        self.src_field = None  # type: Optional[str]
        self.src_datatype = (
            None
        )  # type: Optional[str]  # in SQL string format  # noqa
        # src_flags: a property; see below

        self.scrub_src = None  # type: Optional[str]
        self.scrub_method = None  # type: Optional[str]

        # decision: a property; see below
        # inclusion_values: a property; see below
        # exclusion_values: a property; see below
        # alter_method: a property; see below

        self.dest_table = None  # type: Optional[str]
        self.dest_field = None  # type: Optional[str]
        self.dest_datatype = None  # type: Optional[str]
        self.index = IndexType.NONE  # type: IndexType
        self.indexlen = None  # type: Optional[int]
        self.comment = ""

        # For src_flags:
        self._pk = False
        self._not_null = False
        self._add_src_hash = False
        self._primary_pid = False
        self._defines_primary_pids = False
        self._master_pid = False
        self._constant = False
        self._addition_only = False
        self._opt_out_info = False
        self._required_scrubber = False

        # Other:
        self.omit = False  # in the DD file, this corresponds to 'decision'

        self._from_file = False
        self._src_override_dialect = None  # type: Optional[Dialect]
        self._src_sqla_coltype = None  # type: Optional[str]
        self._inclusion_values = []  # type: List[Any]
        self._exclusion_values = []  # type: List[Any]
        self._alter_methods = []  # type: List[AlterMethod]

    # -------------------------------------------------------------------------
    # Properties: Relating to whole databases
    # -------------------------------------------------------------------------

    @property
    def src_db_lowercase(self) -> str:
        """
        Returns the source database name, in lower case.
        """
        return self.src_db.lower()

    @property
    def src_dialect(self) -> Dialect:
        """
        Returns the SQLAlchemy :class:`Dialect` (e.g. MySQL, SQL Server...) for
        the source database.
        """
        return self._src_override_dialect or self.config.get_src_dialect(
            self.src_db
        )

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
    # Properties: Relating to database columns
    # -------------------------------------------------------------------------

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
    def not_null(self) -> bool:
        """
        Defaults to False. But if the DD row was created by database reflection,
        and the source field was set NOT NULL, will return True.
        """
        return self._not_null

    @property
    def src_is_textual(self) -> bool:
        """
        Is the source column textual?
        """
        return is_sql_column_type_textual(self.src_datatype)

    @property
    def src_textlength(self) -> Optional[int]:
        """
        If the source column is textual, returns its length (or ``None``) for
        unlimited. Also returns ``None`` if the source is not textual.
        """
        if not self.src_is_textual:
            return None
        dialect = self.src_dialect
        # Get length of field if text field (otherwise this remains 'None')
        # noinspection PyUnresolvedReferences
        return coltype_length_if_text(self.src_datatype, dialect.name)

    # -------------------------------------------------------------------------
    # Properties: CRATE
    # -------------------------------------------------------------------------

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
    def contains_patient_scrub_src_info(self) -> bool:
        """
        Does this field contain scrub-source information about the patient?
        """
        return self.scrub_src == ScrubSrc.PATIENT

    @property
    def contains_third_party_info_directly(self) -> bool:
        """
        Does this field contain (identifiable) information about a third party,
        directly?
        """
        return self.scrub_src == ScrubSrc.THIRDPARTY

    @property
    def third_party_pid(self) -> bool:
        """
        Does this field contain the PID of a different (e.g. related) patient?
        """
        return self.scrub_src == ScrubSrc.THIRDPARTY_XREF_PID

    @property
    def contains_third_party_info(self) -> bool:
        """
        Does this field contain (identifiable) information about a third party,
        either directly or via a third-party PID?
        """
        return self.third_party_pid or self.contains_third_party_info_directly

    @property
    def has_special_alter_method(self) -> bool:
        """
        Fields for which the alter method is fixed.
        """
        return self.primary_pid or self.master_pid or self.third_party_pid

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
        return "".join(
            str(x)
            for x in (
                SrcFlag.PK if self._pk else "",
                SrcFlag.NOT_NULL if self._not_null else "",
                SrcFlag.ADD_SRC_HASH if self._add_src_hash else "",
                SrcFlag.PRIMARY_PID if self._primary_pid else "",
                SrcFlag.DEFINES_PRIMARY_PIDS
                if self._defines_primary_pids
                else "",
                SrcFlag.MASTER_PID if self._master_pid else "",
                SrcFlag.CONSTANT if self._constant else "",
                SrcFlag.ADDITION_ONLY if self._addition_only else "",
                SrcFlag.OPT_OUT if self._opt_out_info else "",
                SrcFlag.REQUIRED_SCRUBBER if self._required_scrubber else "",
            )
        )

    @src_flags.setter
    def src_flags(self, flags: str) -> None:
        """
        Takes a string representation of the source flags, and sets our
        internal flags accordingly.
        """
        self._pk = SrcFlag.PK.value in flags
        self._not_null = SrcFlag.NOT_NULL.value in flags
        self._add_src_hash = SrcFlag.ADD_SRC_HASH.value in flags
        self._primary_pid = SrcFlag.PRIMARY_PID.value in flags
        self._defines_primary_pids = (
            SrcFlag.DEFINES_PRIMARY_PIDS.value in flags
        )
        self._master_pid = SrcFlag.MASTER_PID.value in flags
        self._constant = SrcFlag.CONSTANT.value in flags
        self._addition_only = SrcFlag.ADDITION_ONLY.value in flags
        self._opt_out_info = SrcFlag.OPT_OUT.value in flags
        self._required_scrubber = SrcFlag.REQUIRED_SCRUBBER.value in flags

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
        return self._inclusion_values or ""  # for TSV output

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
            self._inclusion_values = (
                ast.literal_eval(value) or []
            )  # type: List[Any]  # noqa
        else:
            self._inclusion_values = []  # type: List[Any]

    @property
    def exclusion_values(self) -> Union[List[Any], str]:
        """
        Returns a list of exclusion values (or an empty string if there are
        no such values).

        This slightly curious output format is used to create a TSV row (see
        :func:`get_tsv`) or to check in a "truthy" way whether we have
        exclusion values (see
        :func:`crate_anon.anonymise.anonymise.process_table`).
        """
        return self._exclusion_values or ""  # for TSV output

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
            self._exclusion_values = (
                ast.literal_eval(value) or []
            )  # type: List[Any]  # noqa
        else:
            self._exclusion_values = []  # type: List[Any]

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
        return ",".join(filter(None, (x.as_text for x in self._alter_methods)))
        # This removes any AlterMethod objects that are doing nothing, because
        # they return blank strings.

    @alter_method.setter
    def alter_method(self, value: str) -> None:
        """
        Convert the ``alter_method`` string (from the data dictionary) to a
        bunch of Boolean/simple fields internally.
        """
        # Get the list of elements in the user's order.
        self._alter_methods = []  # type: List[AlterMethod]
        elements = [x.strip() for x in value.split(",") if x]
        methods = []  # type: List[AlterMethod]
        for e in elements:
            methods.append(AlterMethod(config=self.config, text_value=e))
        # Now establish order. Text extraction first; everything else in order.
        text_extraction_indices = []  # type: List[int]
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
                raise ValueError(
                    f"Date truncation must stand alone in "
                    f"alter_method: {value}"
                )
            if am.extract_text and have_text_extraction:
                raise ValueError(
                    f"Can only have one text extraction method " f"in {value}"
                )
            if am.truncate_date:
                have_truncate_date = True
            if am.extract_text:
                have_text_extraction = True

    def set_alter_methods_directly(self, methods: List[AlterMethod]) -> None:
        """
        For internal use: setting from a list directly.
        """
        # Calls the alter_method setter.
        self.alter_method = ",".join(m.as_text for m in methods)

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
        return Decision.OMIT.value if self.omit else Decision.INCLUDE.value

    @decision.setter
    def decision(self, value: Union[str, Decision]) -> None:
        """
        Sets the internal ``omit`` flag from the input (usually taken from the
        data dictionary file).

        Args:
            value: ``"OMIT"`` or ``"include``.
        """
        try:
            if isinstance(value, Decision):
                e = value
            else:
                e = Decision.lookup(value)
            self.omit = e is Decision.OMIT
        except ValueError:
            raise ValueError(
                "decision was {}; must be one of {}".format(
                    value, [Decision.OMIT.value, Decision.INCLUDE.value]
                )
            )

    @property
    def include(self) -> bool:
        """
        Is this row being included (not omitted)?
        """
        return not self.omit

    # -------------------------------------------------------------------------
    # Comparisons
    # -------------------------------------------------------------------------

    def __lt__(self, other: "DataDictionaryRow") -> bool:
        """
        Defines an order of DDRs based on their source field's signature.
        """
        return self.src_signature < other.src_signature

    def matches_tabledef(self, tabledef: Union[str, List[str]]) -> bool:
        """
        Does our source table match the wildcard-based table definition?

        Args:
            tabledef: ``fnmatch``-style pattern (e.g.
                ``"patient_address_table_*"``), or list of them
        """
        return matches_tabledef(self.src_table, tabledef)

    def matches_fielddef(self, fielddef: Union[str, List[str]]) -> bool:
        """
        Does our source table/field match the wildcard-based field definition?

        Args:
            fielddef: ``fnmatch``-style pattern (e.g. ``"system_table.*"`` or
                ``"*.nhs_number"``), or list of them
        """
        return matches_fielddef(self.src_table, self.src_field, fielddef)

    # -------------------------------------------------------------------------
    # Representations
    # -------------------------------------------------------------------------

    def __str__(self) -> str:
        """
        Returns a string representation of the DDR.
        """
        return ", ".join(
            [f"{a}: {getattr(self, a)!r}" for a in DataDictionaryRow.ROWNAMES]
        )

    @property
    def src_signature(self) -> str:
        """
        Returns a signature based on the source database/table/field, in the
        format ``db.table.column``.
        """
        return f"{self.src_db}.{self.src_table}.{self.src_field}"

    @property
    def dest_signature(self) -> str:
        """
        Returns a signature based on the destination table/field, in the format
        ``table.column``.
        """
        return f"{self.dest_table}.{self.dest_field}"

    @property
    def offender_description(self) -> str:
        """
        Get a string used to describe this DDR (in terms of its
        source/destination fields) if it does something wrong.
        """
        offenderdest = "" if not self.omit else f" -> {self.dest_signature}"
        return f"{self.src_signature}{offenderdest}"

    @classmethod
    def header_row(cls) -> List[str]:
        """
        Returns a header row (a list of headings) for use in spreadsheet
        formats.
        """
        return list(cls.ROWNAMES)

    def as_row(self) -> List[Any]:
        """
        Returns a data row (a list of values whose order matches
        :meth:`header_row`) for use in spreadsheet formats.
        """
        row = []  # type: List[Any]
        for k in self.ROWNAMES:
            v = getattr(self, k)
            if v is None:
                # some spreadsheet handlers (e.g. pyexcel_ods) choke on None
                v = ""
            elif k in self.ENUM_ROWNAMES:
                # convert enum to str
                v = str(v)
            row.append(v)
        return row

    # -------------------------------------------------------------------------
    # Setting
    # -------------------------------------------------------------------------

    def set_from_dict(
        self, valuedict: Dict[str, Any], override_dialect: Dialect = None
    ) -> None:
        """
        Set internal fields from a dict of elements representing a row from the
        TSV data dictionary file.

        Also sets the "loaded from file" indicator, since that is the context
        in which we use this function.

        Args:
            valuedict:
                Dictionary mapping row headings (or attribute names) to values.
            override_dialect:
                SQLAlchemy SQL dialect to enforce (e.g. for interpreting
                textual column types in the source database). By default, the
                source database's own dialect is used.
        """
        self.src_db = valuedict["src_db"]
        self.src_table = valuedict["src_table"]
        self.src_field = valuedict["src_field"]
        self.src_datatype = valuedict["src_datatype"].upper()
        self._src_override_dialect = override_dialect
        # noinspection PyAttributeOutsideInit
        self.src_flags = valuedict["src_flags"]  # a property
        self.scrub_src = ScrubSrc.lookup(
            valuedict["scrub_src"], allow_none=True
        )
        self.scrub_method = ScrubMethod.lookup(
            valuedict["scrub_method"], allow_none=True
        )
        # noinspection PyAttributeOutsideInit
        self.decision = valuedict["decision"]  # a property; sets self.omit
        # noinspection PyAttributeOutsideInit
        self.inclusion_values = valuedict["inclusion_values"]  # a property
        # noinspection PyAttributeOutsideInit
        self.exclusion_values = valuedict["exclusion_values"]  # a property
        # noinspection PyAttributeOutsideInit
        self.alter_method = valuedict["alter_method"]  # a property
        self.dest_table = valuedict["dest_table"]
        self.dest_field = valuedict["dest_field"]
        self.dest_datatype = valuedict["dest_datatype"].upper()
        self.index = IndexType.lookup(valuedict["index"], allow_none=True)
        self.indexlen = convert_to_int(valuedict["indexlen"])
        self.comment = valuedict["comment"]
        self._from_file = True

    # -------------------------------------------------------------------------
    # Anonymisation decisions
    # -------------------------------------------------------------------------

    @property
    def being_scrubbed(self) -> bool:
        """
        Is the field being scrubbed as it passes from source to destination?
        (Only true if the field is being included, not omitted.)
        """
        return not self.omit and any(am.scrub for am in self._alter_methods)

    @property
    def contains_patient_info(self) -> bool:
        """
        Does the field contain patient information? That means any of:

        - primary PID
        - MPID
        - scrub-source (sensitive) information
        """
        return self.primary_pid or self.master_pid or bool(self.scrub_src)

    @property
    def contains_scrub_src(self) -> bool:
        """
        Does the field contain scrub-source information (sensitive information
        used for de-identification)?
        """
        return bool(self.scrub_src)

    @property
    def contains_vital_patient_info(self) -> bool:
        """
        Does the field contain vital patient information? That means:

        - scrub-source (sensitive) information
        """
        return self.contains_scrub_src

    @property
    def required(self) -> bool:
        """
        Is the field required? That means any of:

        - chosen by the user to be translated into the destination
        - contains vital patient information (scrub-source information)
        """
        # return not self.omit or self.contains_patient_info
        return not self.omit or self.contains_vital_patient_info

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

    @property
    def alter_methods(self) -> List[AlterMethod]:
        """
        Return all alteration methods to be applied.

        Returns:
            list of :class:`crate_anon.anonymise.altermethod.AlterMethod`
            objects

        """
        return self._alter_methods

    @property
    def skip_row_if_extract_text_fails(self) -> bool:
        """
        Should we skip the row if processing the row involves extracting text
        and that process fails?
        """
        return any(x.skip_if_text_extract_fails for x in self._alter_methods)

    @property
    def extracting_text_altermethods(self) -> List[AlterMethod]:
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
        # log.debug(
        #     f"remove_scrub_from_alter_methods "
        #     f"[used for non-patient tables]: {self.src_signature}")
        for sm in self._alter_methods:
            sm.scrub = False

    # -------------------------------------------------------------------------
    # Other decisions
    # -------------------------------------------------------------------------

    @property
    def using_fulltext_index(self) -> bool:
        """
        Should the destination field have a full-text index?
        """
        return self.index == IndexType.FULLTEXT

    # -------------------------------------------------------------------------
    # SQLAlchemy types
    # -------------------------------------------------------------------------

    @property
    def src_sqla_coltype(self) -> TypeEngine:
        """
        Returns the SQLAlchemy column type of the source column.
        """
        return self._src_sqla_coltype or get_sqla_coltype_from_dialect_str(
            self.src_datatype, self.config.get_src_dialect(self.src_db)
        )

    def set_src_sqla_coltype(self, sqla_coltype: TypeEngine) -> None:
        """
        Sets the SQLAlchemy column type of the source column.
        """
        self._src_sqla_coltype = sqla_coltype

    @property
    def dest_should_be_encrypted_pid_type(self) -> bool:
        """
        Should the destination column (if included) be of the encrypted
        PID/MPID type?
        """
        return self.primary_pid or self.third_party_pid or self.master_pid

    @property
    def dest_sqla_coltype(self) -> TypeEngine:
        """
        Returns the SQLAlchemy column type of the destination column.

        Note that this doesn't include nullable status. An SQLAlchemy column
        looks like Column(String(50), nullable=False) -- the type that we're
        fetching here is, for example, the String(50) part. For the full
        column, see ``dest_sqla_column`` below.
        """
        if self.dest_datatype:
            # User (or our autogeneration process) wants to override
            # the type.
            return get_sqla_coltype_from_dialect_str(
                self.dest_datatype, self.dest_dialect
            )
        else:
            # Destination data type is not explicitly specified.
            # Is it a special type of field?
            if self.dest_should_be_encrypted_pid_type:
                return self.config.sqltype_encrypted_pid
            else:
                # Otherwise: return the SQLAlchemy column type class determined
                # from the source database by reflection. Will be autoconverted
                # to the destination dialect, with some exceptions, addressed
                # as below:
                return convert_sqla_type_for_dialect(
                    coltype=self.src_sqla_coltype,
                    dialect=self.dest_dialect,
                    expand_for_scrubbing=self.being_scrubbed,
                )

    @property
    def dest_sqla_column(self) -> Column:
        """
        Returns an SQLAlchemy :class:`sqlalchemy.sql.schema.Column` for the
        destination column.
        """
        name = self.dest_field
        coltype = self.dest_sqla_coltype
        comment = self.comment or ""
        kwargs = {
            "doc": comment,  # Python side
            "comment": comment,  # SQL side; supported from SQLAlchemy 1.2:
            # https://docs.sqlalchemy.org/en/14/core/metadata.html#sqlalchemy.schema.Column.params.comment  # noqa
        }
        if self.pk:
            kwargs["primary_key"] = True
            kwargs["autoincrement"] = False
        if self.not_null or self.primary_pid:
            kwargs["nullable"] = False
        return Column(name, coltype, **kwargs)

    def make_dest_datatype_explicit(self) -> None:
        """
        By default, when autocreating a data dictionary, the ``dest_datatype``
        field is not populated explicit, just implicitly. This option makes
        them explicit by instantiating those values. Primarily for debugging.
        """
        if not self.dest_datatype:
            self.dest_datatype = str(self.dest_sqla_coltype)

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
                f"Offending DD row [{self.offender_description}]: "
                f"{str(self)}"
            )
            raise

    def check_prohibited_fieldnames(
        self, prohibited_fieldnames: Iterable[str]
    ) -> None:
        """
        Check that the destination field isn't a prohibited one.

        Args:
            prohibited_fieldnames: list of prohibited fieldnames

        Raises:
            :exc:`ValueError` if there's a problem.

        """
        if self.dest_field in prohibited_fieldnames:
            log.exception(
                f"Offending DD row [{self.offender_description}]: "
                f"{str(self)}"
            )
            raise ValueError("Prohibited dest_field name")

    def _check_valid(self) -> None:
        """
        Check internal validity and complain if invalid.

        Raises:
            :exc:`AssertionError`, :exc:`ValueError`
        """
        src_sqla_coltype = self.src_sqla_coltype
        dest_sqla_coltype = self.dest_sqla_coltype

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Anything missing?
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        assert self.src_db, "Need src_db"
        assert self.src_table, "Need src_table"
        assert self.src_field, "Need src_field"
        assert self.src_datatype, "Need src_datatype"
        if not self.omit:
            assert self.dest_table, "Need dest_table"
            assert self.dest_field, "Need dest_field"

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Check source database/table/field are OK
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        if self.src_db not in self.config.source_db_names:
            raise ValueError(
                "Data dictionary row references non-existent source "
                "database"
            )

        srccfg = self.config.sources[self.src_db].srccfg

        ensure_valid_table_name(self.src_table)
        ensure_valid_field_name(self.src_field)

        if self.include:
            # Ensure the destination table/column names are OK for the dialect.
            warn_if_identifier_long(
                self.dest_table, self.dest_field, self.dest_dialect_name
            )

        # REMOVED 2016-06-04; fails with complex SQL Server types, which can
        # look like 'NVARCHAR(10) COLLATE "Latin1_General_CI_AS"'.
        #
        # if not is_sqltype_valid(self.src_datatype):
        #     raise ValueError(
        #         "Field has invalid source data type: {}".format(
        #             self.src_datatype))

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Check for conflicting or missing flags
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        if self.defines_primary_pids and not self.primary_pid:
            raise ValueError(
                f"All fields with "
                f"{self.SRC_FLAGS}={SrcFlag.DEFINES_PRIMARY_PIDS} "
                f"set must have {self.SRC_FLAGS}={SrcFlag.PRIMARY_PID} set"
            )

        if self.opt_out_info and not self.config.optout_col_values:
            raise ValueError(
                f"Fields with {self.SRC_FLAGS}={SrcFlag.OPT_OUT} "
                f"exist, but config's {AnonymiseConfigKeys.OPTOUT_COL_VALUES} "
                f"setting is empty"
            )

        if (
            count_bool(
                [
                    self.primary_pid,
                    self.master_pid,
                    self.third_party_pid,
                    bool(self.alter_method),
                ]
            )
            > 1
        ):
            raise ValueError(
                f"Field can be any ONE of: "
                f"{self.SRC_FLAGS}={SrcFlag.PRIMARY_PID}, "
                f"{self.SRC_FLAGS}={SrcFlag.MASTER_PID}, "
                f"{self.SCRUB_SRC}={ScrubSrc.THIRDPARTY_XREF_PID}, or "
                f"{self.ALTER_METHOD} "
                f"(because those flags all imply a certain "
                f"{self.ALTER_METHOD})"
            )

        if self.required_scrubber and not self.scrub_src:
            raise ValueError(
                f"If you specify "
                f"{self.SRC_FLAGS}={SrcFlag.REQUIRED_SCRUBBER}, "
                f"you must specify {self.SCRUB_SRC}"
            )

        if self.add_src_hash:
            if not self.pk:
                raise ValueError(
                    f"{self.SRC_FLAGS}={SrcFlag.ADD_SRC_HASH} "
                    f"can only be set on "
                    f"{self.SRC_FLAGS}={SrcFlag.PK} fields"
                )
            if self.omit:
                raise ValueError(
                    f"Cannot omit fields with "
                    f"{self.SRC_FLAGS}={SrcFlag.ADD_SRC_HASH} set"
                )
            if self.index != IndexType.UNIQUE:
                raise ValueError(
                    f"{self.SRC_FLAGS}={SrcFlag.ADD_SRC_HASH} fields require "
                    f"{self.INDEX}=={IndexType.UNIQUE}"
                )
            if self.constant:
                raise ValueError(
                    f"cannot mix {SrcFlag.ADD_SRC_HASH} flag with "
                    f"{SrcFlag.CONSTANT} flag"
                )

        if self.constant:
            if not self.pk:
                raise ValueError(
                    f"{self.SRC_FLAGS}={SrcFlag.CONSTANT} can only be set on "
                    f"{self.SRC_FLAGS}={SrcFlag.PK} fields"
                )
            if self.index != IndexType.UNIQUE:
                raise ValueError(
                    f"{self.SRC_FLAGS}={SrcFlag.CONSTANT} fields require "
                    f"{self.INDEX}=={IndexType.UNIQUE}"
                )

        if self.addition_only:
            if not self.pk:
                raise ValueError(
                    f"{self.SRC_FLAGS}={SrcFlag.ADDITION_ONLY} "
                    f"can only be set on "
                    f"{self.SRC_FLAGS}={SrcFlag.PK} fields"
                )

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # No more checks required if field will be omitted.
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        if self.omit:
            return

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Check destination table/field/datatype
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Table
        ensure_valid_table_name(self.dest_table)
        if self.dest_table == self.config.temporary_tablename:
            raise ValueError(
                f"Destination tables can't be named "
                f"{self.config.temporary_tablename}, as that's the name set "
                f"in the config's {AnonymiseConfigKeys.TEMPORARY_TABLENAME} "
                f"variable"
            )
        # Field
        ensure_valid_field_name(self.dest_field)
        if self.dest_field == self.config.source_hash_fieldname:
            raise ValueError(
                f"Destination fields can't be named "
                f"{self.config.source_hash_fieldname}, as that's the name set "
                f"in the config's {AnonymiseConfigKeys.SOURCE_HASH_FIELDNAME} "
                f"variable"
            )
        elif self.dest_field == self.config.trid_fieldname:
            raise ValueError(
                f"Destination fields can't be named "
                f"{self.config.trid_fieldname}, as that's the name set "
                f"in the config's {AnonymiseConfigKeys.TRID_FIELDNAME} "
                f"variable"
            )
        # Datatype
        if self.dest_datatype and not is_sqltype_valid(self.dest_datatype):
            raise ValueError(
                f"Field has invalid {self.DEST_DATATYPE}: "
                f"{self.dest_datatype}"
            )

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Check destination flags/special fields
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # PID/RID
        if self.matches_fielddef(srccfg.ddgen_per_table_pid_field):
            if not self.primary_pid:
                raise ValueError(
                    f"All fields with {self.SRC_FIELD}={self.src_field!r} "
                    f"used in output should have "
                    f"{self.SRC_FLAGS}={SrcFlag.PRIMARY_PID} set"
                )
            if self.dest_field != self.config.research_id_fieldname:
                raise ValueError(
                    f"Primary PID field should have {self.DEST_FIELD} = "
                    f"{self.config.research_id_fieldname}"
                )
        # MPID/MRID
        if (
            self.matches_fielddef(srccfg.ddgen_master_pid_fieldname)
            and not self.master_pid
        ):
            raise ValueError(
                f"All fields with {self.SRC_FIELD} = "
                f"{srccfg.ddgen_master_pid_fieldname} used in output should "
                f"have {self.SRC_FLAGS}={SrcFlag.MASTER_PID} set"
            )
        # Anything that is hashed (but not self._add_src_hash -- added
        # separately):
        if (
            self.dest_should_be_encrypted_pid_type
            and self.dest_datatype
            and self.dest_datatype != self.config.sqltype_encrypted_pid_as_sql
        ):
            raise ValueError(
                f"All {self.SRC_FLAGS}={SrcFlag.PRIMARY_PID}/"
                f"{self.SRC_FLAGS}={SrcFlag.MASTER_PID}/"
                f"{self.SRC_FLAGS}={SrcFlag.ADD_SRC_HASH} "
                f"fields used in output must have {self.DEST_DATATYPE} = "
                f"{self.config.sqltype_encrypted_pid_as_sql} "
                f"(determined by the config parameter "
                f"{AnonymiseConfigKeys.HASH_METHOD!r})"
            )

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Check alteration methods
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        if self.has_special_alter_method and self._alter_methods:
            raise ValueError(
                f"Don't specify {self.ALTER_METHOD} "
                f"for PID/MPID/third-party PID fields; "
                f"these are handled specially"
            )
        for am in self._alter_methods:
            if am.truncate_date:
                if not (
                    is_sqlatype_date(src_sqla_coltype)
                    or is_sqlatype_text_over_one_char(src_sqla_coltype)
                ):
                    raise ValueError(
                        f"Can't set {AlterMethodType.TRUNCATEDATE.value} "
                        f"for non-date/non-text field"
                    )
            if am.extract_from_filename:
                if not is_sqlatype_text_over_one_char(src_sqla_coltype):
                    raise ValueError(
                        f"For {self.ALTER_METHOD} = "
                        f"{AlterMethodType.FILENAME_TO_TEXT}, "
                        f"source field must contain a filename and therefore "
                        f"must be text type of >1 character"
                    )
            if am.extract_from_blob:
                if not is_sqlatype_binary(src_sqla_coltype):
                    raise ValueError(
                        f"For {self.ALTER_METHOD} = "
                        f"{AlterMethodType.BINARY_TO_TEXT}, "
                        f"source field must be of binary type"
                    )

        # This error/warning too hard to be sure of with SQL Server odd
        # string types:
        # if [RENAMED: self._scrub] and not self._extract_text:
        #     if not is_sqltype_text_over_one_char(self.src_datatype):
        #         raise ValueError("Can't scrub in non-text field or "
        #                          "single-character text field")

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Check indexing
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        if (
            self.index in (IndexType.NORMAL, IndexType.UNIQUE)
            and self.indexlen is None
            and does_sqlatype_require_index_len(dest_sqla_coltype)
        ):
            raise ValueError(
                f"Must specify {self.INDEXLEN} "
                f"to index a TEXT or BLOB field"
            )

    # -------------------------------------------------------------------------
    # Other stuff requiring config or database info
    # -------------------------------------------------------------------------

    def set_from_src_db_info(
        self,
        src_db: str,
        src_table: str,
        src_field: str,
        src_datatype_sqltext: str,
        src_sqla_coltype: TypeEngine,
        dbconf: "DatabaseSafeConfig",
        comment: str = None,
        nullable: bool = True,
        primary_key: bool = False,
    ) -> None:
        """
        Set up this DDR from a field in the source database, using options set
        in the config file. Used to draft a data dictionary. This is the
        first-draft classification of a given column, which the administrator
        should review and may then wish to edit.

        Args:
            src_db:
                Source database name.
            src_table:
                Source table name.
            src_field:
                Source field (column) name.
            src_datatype_sqltext:
                Source string SQL type, e.g. ``"VARCHAR(100)"``.
            src_sqla_coltype:
                Source SQLAlchemy column type, e.g. ``Integer()``.
            dbconf:
                A :class:`crate_anon.anonymise.config.DatabaseSafeConfig`.
            comment:
                Textual comment.
            nullable:
                Whether the source is can be NULL (True) or is NOT NULL
                (False).
            primary_key:
                Whether the source is marked as a primary key.
        """
        self.src_db = src_db
        self.src_table = src_table
        self.src_field = src_field
        self.src_datatype = src_datatype_sqltext
        self._src_sqla_coltype = src_sqla_coltype
        self._not_null = not nullable
        self._pk = False
        self._add_src_hash = False
        self._primary_pid = False
        self._defines_primary_pids = False
        self._master_pid = False
        self._constant = False
        self._addition_only = False
        self.comment = comment
        self._from_file = False

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # ddgen: Is the field special, such as a PK?
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        if self.matches_fielddef(dbconf.ddgen_pk_fields) or primary_key:
            # Table primary key (e.g. arbitrary integer).
            self._pk = True
            self._constant = (
                dbconf.ddgen_constant_content
                or self.matches_tabledef(dbconf.ddgen_constant_content_tables)
            ) and not self.matches_tabledef(
                dbconf.ddgen_nonconstant_content_tables
            )
            self._add_src_hash = not self._constant
            self._addition_only = (
                dbconf.ddgen_addition_only
                or self.matches_tabledef(dbconf.ddgen_addition_only_tables)
            ) and not self.matches_tabledef(
                dbconf.ddgen_deletion_possible_tables
            )

        if self.matches_fielddef(dbconf.ddgen_per_table_pid_field):
            # PID, e.g. local hospital number.
            self._primary_pid = True
            if self.matches_tabledef(dbconf.ddgen_table_defines_pids):
                self._defines_primary_pids = True

        if self.matches_fielddef(dbconf.ddgen_master_pid_fieldname):
            # MPID, e.g. NHS number.
            self._master_pid = True

        if self.matches_fielddef(dbconf.ddgen_pid_defining_fieldnames):
            # The PID in the "chief" patient table.
            self._defines_primary_pids = True

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # ddgen: Does it indicate the patient wishes to opt out entirely?
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        if self.matches_fielddef(dbconf.ddgen_patient_opt_out_fields):
            self._opt_out_info = True

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # ddgen: Does the field contain sensitive data?
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        if (
            self.master_pid
            or self.defines_primary_pids
            or (
                self.primary_pid
                and dbconf.ddgen_add_per_table_pids_to_scrubber
            )
            or self.matches_fielddef(dbconf.ddgen_scrubsrc_patient_fields)
        ):  # noqa
            self.scrub_src = ScrubSrc.PATIENT

        elif self.matches_fielddef(dbconf.ddgen_scrubsrc_thirdparty_fields):
            self.scrub_src = ScrubSrc.THIRDPARTY

        elif self.matches_fielddef(
            dbconf.ddgen_scrubsrc_thirdparty_xref_pid_fields
        ):
            self.scrub_src = ScrubSrc.THIRDPARTY_XREF_PID

        else:
            self.scrub_src = None  # type: Optional[str]

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # ddgen: Is it a mandatory scrubbing field?
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        if self.matches_fielddef(dbconf.ddgen_required_scrubsrc_fields):
            self._required_scrubber = True

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # ddgen: What kind of sensitive data? Date, text, number, code?
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        if not self.scrub_src:
            self.scrub_method = ""

        elif (
            self.scrub_src is ScrubSrc.THIRDPARTY_XREF_PID
            or is_sqlatype_numeric(src_sqla_coltype)
            or self.matches_fielddef(dbconf.ddgen_per_table_pid_field)
            or self.matches_fielddef(dbconf.ddgen_master_pid_fieldname)
            or self.matches_fielddef(dbconf.ddgen_scrubmethod_number_fields)
        ):  # noqa
            self.scrub_method = ScrubMethod.NUMERIC

        elif is_sqlatype_date(src_sqla_coltype) or self.matches_fielddef(
            dbconf.ddgen_scrubmethod_date_fields
        ):
            self.scrub_method = ScrubMethod.DATE

        elif self.matches_fielddef(dbconf.ddgen_scrubmethod_code_fields):
            self.scrub_method = ScrubMethod.CODE

        elif self.matches_fielddef(dbconf.ddgen_scrubmethod_phrase_fields):
            self.scrub_method = ScrubMethod.PHRASE

        else:
            self.scrub_method = ScrubMethod.WORDS

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # ddgen: Do we want to change the destination fieldname?
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        if self.primary_pid:
            self.dest_field = self.config.research_id_fieldname
        elif self.master_pid:
            self.dest_field = self.config.master_research_id_fieldname
        else:
            self.dest_field = src_field
        if dbconf.ddgen_force_lower_case:
            self.dest_field = self.dest_field.lower()
        if dbconf.ddgen_convert_odd_chars_to_underscore:
            self.dest_field = str(self.dest_field)  # if this fails,
            # there's a Unicode problem
            self.dest_field = self.dest_field.translate(ODD_CHARS_TRANSLATE)
            # ... this will choke on a Unicode string

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # ddgen: Do we want to change the destination field SQL type?
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        if self.dest_should_be_encrypted_pid_type:
            self.dest_datatype = self.config.sqltype_encrypted_pid_as_sql
        else:
            self.dest_datatype = ""
        # ... and see also potential changes made below

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # ddgen: How should we manipulate the destination?
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        extracting_text = False

        if self.matches_fielddef(dbconf.ddgen_truncate_date_fields):
            # Date truncation
            self._alter_methods.append(
                AlterMethod(config=self.config, truncate_date=True)
            )
            # If we're truncating a date, we should also encourage a DATE
            # destination (as opposed to e.g. a DATETIME).
            self.dest_datatype = SQLTYPE_DATE

        elif self.matches_fielddef(dbconf.ddgen_filename_to_text_fields):
            # Read filename from database, read file, convert to text
            self._alter_methods.append(
                AlterMethod(config=self.config, extract_from_filename=True)
            )
            self.dest_datatype = giant_text_sqltype(self.dest_dialect)
            extracting_text = True

        elif self.matches_fielddef(dbconf.bin2text_dict.keys()):
            # Read binary data from database, convert to text
            for binfielddef, extfield in dbconf.bin2text_dict.items():
                if self.matches_fielddef(binfielddef):
                    self._alter_methods.append(
                        AlterMethod(
                            config=self.config,
                            extract_from_blob=True,
                            extract_ext_field=extfield,
                        )
                    )
            self.dest_datatype = giant_text_sqltype(self.dest_dialect)
            extracting_text = True

        elif (
            not self.primary_pid
            and not self.master_pid
            and not self.matches_fielddef(
                dbconf.ddgen_safe_fields_exempt_from_scrubbing
            )
            and dbconf.ddgen_min_length_for_scrubbing >= 1
            and is_sqlatype_text_of_length_at_least(
                src_sqla_coltype, dbconf.ddgen_min_length_for_scrubbing
            )
        ):
            # Text field meeting the criteria to scrub
            self._alter_methods.append(
                AlterMethod(config=self.config, scrub=True)
            )

        if extracting_text:
            # Scrub all extract-text fields, unless asked not to
            if not self.matches_fielddef(
                dbconf.ddgen_safe_fields_exempt_from_scrubbing
            ):
                self._alter_methods.append(
                    AlterMethod(config=self.config, scrub=True)
                )
            # Set skip_if_text_extract_fails flag?
            if self.matches_fielddef(
                dbconf.ddgen_skip_row_if_extract_text_fails_fields
            ):
                self._alter_methods.append(
                    AlterMethod(
                        config=self.config, skip_if_text_extract_fails=True
                    )
                )

        for fieldspec, cfg_section in dbconf.ddgen_extra_hash_fields.items():
            # Hash something using an "extra" hasher.
            if self.matches_fielddef(fieldspec):
                self._alter_methods.append(
                    AlterMethod(
                        config=self.config,
                        hash_=True,
                        hash_config_section=cfg_section,
                    )
                )

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # ddgen: Manipulate the destination table name?
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # https://stackoverflow.com/questions/10017147
        self.dest_table = src_table

        if dbconf.ddgen_force_lower_case:
            self.dest_table = self.dest_table.lower()

        if dbconf.ddgen_convert_odd_chars_to_underscore:
            self.dest_table = str(self.dest_table)
            # ... if this fails, there's a Unicode problem
            self.dest_table = self.dest_table.translate(ODD_CHARS_TRANSLATE)

        for suffix in dbconf.ddgen_rename_tables_remove_suffixes:
            if self.dest_table.endswith(suffix):
                self.dest_table = self.dest_table[: -len(suffix)]  # remove it
                break  # only remove one suffix!

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # ddgen: Should we index the destination?
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        dest_sqla_type = self.dest_sqla_coltype

        if self._pk:
            self.index = IndexType.UNIQUE

        elif (
            self.primary_pid
            or self.master_pid
            or self.defines_primary_pids
            or self.dest_field == self.config.research_id_fieldname
        ):
            self.index = IndexType.NORMAL

        elif (
            dbconf.ddgen_allow_fulltext_indexing
            and does_sqlatype_merit_fulltext_index(
                src_sqla_coltype,
                min_length=dbconf.ddgen_freetext_index_min_length,
            )
        ):
            self.index = IndexType.FULLTEXT

        elif self.matches_fielddef(dbconf.ddgen_index_fields):
            self.index = IndexType.NORMAL

        else:
            self.index = IndexType.NONE

        self.indexlen = (
            DEFAULT_INDEX_LEN
            if (
                self.index != IndexType.NONE
                and self.index != IndexType.FULLTEXT
                and does_sqlatype_require_index_len(dest_sqla_type)
            )
            else None
        )

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # ddgen: Should we omit it (at least until a human has checked the DD)?
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        # In descending order of priority:
        if self.matches_fielddef(dbconf.ddgen_omit_fields):  # explicit
            # Explicit omission trumps everything else
            # (There are rare occasions with "additional" databases where we
            # may want to omit a PK/PID/MPID field.)
            self.omit = True

        elif self._pk or self.primary_pid or self.master_pid:
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
