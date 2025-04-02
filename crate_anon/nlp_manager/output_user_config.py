"""
crate_anon/nlp_manager/output_user_config.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

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

**Define output configuration for GATE NLP applications.**

"""

import ast
import logging
import shlex
from typing import Dict, List

from cardinal_pythonlib.sql.validation import (
    ensure_valid_field_name,
    ensure_valid_table_name,
    is_sqltype_valid,
)
from cardinal_pythonlib.lists import chunks
from cardinal_pythonlib.sqlalchemy.schema import (
    get_sqla_coltype_from_dialect_str,
)
from sqlalchemy.engine.base import Engine
from sqlalchemy.schema import Column, Index

from crate_anon.common.extendedconfigparser import (
    ConfigSection,
    ExtendedConfigParser,
)
from crate_anon.nlp_manager.constants import (
    full_sectionname,
    NlpOutputConfigKeys,
    NlpConfigPrefixes,
)
from crate_anon.nlp_manager.input_field_config import InputFieldConfig

log = logging.getLogger(__name__)


# =============================================================================
# OutputUserConfig
# =============================================================================


class OutputUserConfig:
    """
    Class defining configuration for the output of a given GATE app, or remote
    cloud app.

    See the documentation for the :ref:`NLP config file <nlp_config>`.
    """

    def __init__(
        self,
        config_parser: ExtendedConfigParser,
        cfg_output_name: str,
        schema_required: bool = True,
    ) -> None:
        """
        Read config from a configparser section.

        Args:
            config_parser:
                :class:`crate_anon.common.extendedconfigparser.ExtendedConfigParser`
            cfg_output_name:
                config file section name suffix -- this is the second of the
                pair of strings in the ``outputtypemap`` part of the GATE NLP
                app config section. See

                - :ref:`NLP config file <nlp_config>`
                - :class:`crate_anon.nlp_manager.parse_gate.Gate`
            schema_required:
                is it required that the user has specified a schema, i.e.
                destfields and a desttable? - Should be true for Gate, False
                for Cloud as the remote processors may have their own schema
                definition.
        """

        sectionname = full_sectionname(
            NlpConfigPrefixes.OUTPUT, cfg_output_name
        )
        cfg = ConfigSection(section=sectionname, parser=config_parser)

        # ---------------------------------------------------------------------
        # desttable
        # ---------------------------------------------------------------------

        self._desttable = cfg.opt_str(
            NlpOutputConfigKeys.DESTTABLE, required=True
        )
        ensure_valid_table_name(self._desttable)

        # ---------------------------------------------------------------------
        # renames
        # ---------------------------------------------------------------------

        self._renames = {}  # type: Dict[str, str]
        rename_lines = cfg.opt_strlist(
            NlpOutputConfigKeys.RENAMES, required=False, as_words=False
        )
        for line in rename_lines:
            if not line.strip():
                continue
            words = shlex.split(line)
            if len(words) != 2:
                raise ValueError(
                    f"Bad {NlpOutputConfigKeys.RENAMES!r} option in config "
                    f"section {sectionname!r}; line was {line!r} but should "
                    f"have contained two things"
                )
            annotation_or_remote_column_name = words[0]
            to_column_name = words[1]
            ensure_valid_field_name(to_column_name)
            self._renames[annotation_or_remote_column_name] = to_column_name

        # ---------------------------------------------------------------------
        # null_literals
        # ---------------------------------------------------------------------

        null_literal_lines = cfg.opt_strlist(
            NlpOutputConfigKeys.NULL_LITERALS, required=False, as_words=False
        )
        self._null_literals = []  # type: List[str]
        for line in null_literal_lines:
            self._null_literals += shlex.split(line)

        # ---------------------------------------------------------------------
        # destfields
        # ---------------------------------------------------------------------

        self._destfields = []  # type: List[str]
        self._dest_datatypes = []  # type: List[str]
        self._dest_comments = []  # type: List[str]
        dest_field_lines = cfg.opt_strlist(
            NlpOutputConfigKeys.DESTFIELDS,
            required=schema_required,
            as_words=False,
        )
        # ... comments will be removed during that process.
        # If dest_field_lines is empty (as it may be for a Cloud processor)
        # the following block doesn't execute, so the 'dest' attributed remain
        # empty
        for dfl in dest_field_lines:
            parts = dfl.split(maxsplit=2)
            assert len(parts) >= 2, f"Bad field definition line: {dfl!r}"
            field = parts[0]
            datatype = parts[1].upper()
            comment = parts[2] if len(parts) > 2 else None
            ensure_valid_field_name(field)
            if not is_sqltype_valid(datatype):
                raise ValueError(f"Invalid datatype for {field}: {datatype}")
            self._destfields.append(field)
            self._dest_datatypes.append(datatype)
            self._dest_comments.append(comment)

        src_fields = [
            c.name for c in InputFieldConfig.get_core_columns_for_dest()
        ]
        for sf in src_fields:
            if sf in self._destfields:
                raise ValueError(
                    f"For section {sectionname}, destination field {sf} is "
                    f"auto-supplied; do not add it manually"
                )

        if len(set(self._destfields)) != len(self._destfields):
            raise ValueError(
                f"Duplicate fields exist in destination fields: "
                f"{self._destfields}"
            )

        # ---------------------------------------------------------------------
        # indexdefs
        # ---------------------------------------------------------------------

        self._indexfields = []  # type: List[str]
        self._indexlengths = []  # type: List[int]
        indexdefs = cfg.opt_strlist(NlpOutputConfigKeys.INDEXDEFS)
        if indexdefs:
            for c in chunks(indexdefs, 2):  # pairs: field, length
                indexfieldname = c[0]
                lengthstr = c[1]
                if indexfieldname not in self._destfields:
                    raise ValueError(
                        f"Index field {indexfieldname} not in "
                        f"destination fields {self._destfields}"
                    )
                try:
                    length = ast.literal_eval(lengthstr)
                    if length is not None:
                        length = int(length)
                except ValueError:
                    raise ValueError(f"Bad index length: {lengthstr}")
                self._indexfields.append(indexfieldname)
                self._indexlengths.append(length)

    @property
    def dest_tablename(self) -> str:
        """
        Returns the name of the destination table.
        """
        return self._desttable

    @property
    def destfields(self) -> List[str]:
        """
        Returns the list of destination fields.
        """
        return self._destfields

    def get_columns(self, engine: Engine) -> List[Column]:
        """
        Return all SQLAlchemy :class:`Column` definitions for the destination
        table.

        Args:
            engine: SQLAlchemy database :class:`Engine`

        Returns:
            list of SQLAlchemy :class:`Column` objects

        """
        columns = []  # type: List[Column]
        for i, field in enumerate(self._destfields):
            datatype = self._dest_datatypes[i]
            comment = self._dest_comments[i]
            columns.append(
                Column(
                    field,
                    get_sqla_coltype_from_dialect_str(
                        datatype, engine.dialect
                    ),
                    comment=comment,
                )
            )
        return columns

    @property
    def indexes(self) -> List[Index]:
        """
        Return all SQLAlchemy :class:`Index` definitions for the destination
        table.

        Returns:
            list of SQLAlchemy :class:`Index` objects

        """
        indexes = []  # type: List[Index]
        for i, field in enumerate(self._indexfields):
            index_name = f"_idx_{field}"
            length = self._indexlengths[i]
            kwargs = {"mysql_length": length} if length is not None else {}
            indexes.append(Index(index_name, field, **kwargs))
        return indexes

    @property
    def renames(self) -> Dict[str, str]:
        """
        Return the "rename dictionary": a dictionary mapping GATE annotation
        names (or cloud remote column names) to local field (column) names in
        the NLP destination table.

        See

        - ``renames`` in the :ref:`NLP config file <nlp_config>`.
        - :meth:`crate_anon.nlp_manager.parse_gate.Gate.parse`
        """
        return self._renames

    @property
    def null_literals(self) -> List[str]:
        """
        Returns string values from the GATE output that will be interpreted as
        NULL values.

        See

        - ``null_literals`` in the :ref:`NLP config file <nlp_config>`.
        - :meth:`crate_anon.nlp_manager.parse_gate.Gate.parse`.
        """
        return self._null_literals
