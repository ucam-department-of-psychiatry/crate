#!/usr/bin/env python

"""
crate_anon/nlp_manager/cloud_parser.py

===============================================================================

    Copyright (C) 2015-2020 Rudolf Cardinal (rudolf@pobox.com).

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

Send text to a cloud-based NLPRP server for processing.

.. todo:: cloud_parser: handle new ``tabular_schema`` info from server

"""

import logging
from typing import Any, Dict, List, Optional, Type

from cardinal_pythonlib.lists import chunks
from sqlalchemy.schema import Column, Index
from sqlalchemy import types as sqlatypes

from crate_anon.common.extendedconfigparser import configfail
from crate_anon.nlp_manager.nlp_definition import (
    NlpDefinition,
)
from crate_anon.nlp_manager.constants import (
    full_sectionname,
    NlpConfigPrefixes,
    ProcessorConfigKeys,
    NlpDefValues,
)
from crate_anon.nlp_manager.output_user_config import OutputUserConfig
from crate_anon.nlprp.constants import (
    NlprpKeys as NKeys,
    NlprpValues,
)
from crate_anon.nlp_manager.base_nlp_parser import TableMaker
from crate_anon.nlp_webserver.server_processor import ServerProcessor

log = logging.getLogger(__name__)


# =============================================================================
# Cloud class for cloud-based processsors
# =============================================================================

class Cloud(TableMaker):
    """
    Class to hold information on remote processors and create the relavant
    tables.
    """
    # Index for anonymous tables
    i = 0

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        """
        Args:
            nlpdef:
                :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
            cfgsection:
                the config section for the processor
            commit:
                force a COMMIT whenever we insert data? You should specify this
                in multiprocess mode, or you may get database deadlocks.
        """
        super().__init__(nlpdef, cfgsection, commit, name="Cloud")
        self.remote_processor_info = None  # type: Optional[ServerProcessor]
        sectionname = full_sectionname(NlpConfigPrefixes.PROCESSOR,
                                       cfgsection)
        self.procname = nlpdef.opt_str(
            sectionname, ProcessorConfigKeys.PROCESSOR_NAME,
            required=True)
        self.procversion = nlpdef.opt_str(
            sectionname, ProcessorConfigKeys.PROCESSOR_VERSION,
            default=None)
        # Made format required so people are less likely to make mistakes
        self.format = nlpdef.opt_str(
            sectionname,
            ProcessorConfigKeys.PROCESSOR_FORMAT,
            required=True)
        self.schema_type = None
        self.sql_dialect = None
        self.schema = None  # type: Optional[Dict[str, Any]]
        self.available_remotely = False  # update later if available

        # Output section - bit of repetition from the 'Gate' parser
        typepairs = nlpdef.opt_strlist(
            sectionname, ProcessorConfigKeys.OUTPUTTYPEMAP,
            required=True, lower=False)
        self._outputtypemap = {}  # type: Dict[str, OutputUserConfig]
        self._type_to_tablename = {}  # type: Dict[str, str]
        self.tablename = None
        # If typepairs is empty the following block won't execute
        for c in chunks(typepairs, 2):
            output_type = c[0]
            outputsection = c[1]
            output_type = output_type.lower()
            c = OutputUserConfig(nlpdef.get_parser(), outputsection,
                                 schema_required=False)
            self._outputtypemap[output_type] = c
            self._type_to_tablename[output_type] = c.get_tablename()
            if output_type == '""':
                self.tablename = c.get_tablename()
        # Checks are now taken care of elsewhere
        # if not self._outputtypemap and not self.tablename:
        #     configfail(
        #         f"In section [{sectionname}], neither "
        #         f"{ProcessorConfigKeys.OUTPUTTYPEMAP!r} nor "
        #         f"{ProcessorConfigKeys.DESTTABLE!r} is specified. The cloud "
        #         f"processor won't know where to store its results.")

    @staticmethod
    def get_coltype_parts(coltype_str: str) -> List[str]:
        """
        Get root column type and parameter, i.e. for VARCHAR(50)
        root column type is VARCHAR and parameter is 50.
        """
        parts = [x.strip() for x in coltype_str.replace(")", "").split("(")]
        if len(parts) == 1:
            col_str = parts[0]
            parameter = ""
        else:
            try:
                col_str, parameter = parts
            except ValueError:
                log.error(f"Invalid column type in response: {coltype_str}")
                raise
            try:
                # Turn the parameter into an integer if it's supposed to be one
                parameter = int(parameter)
            except ValueError:
                pass
        return [col_str, parameter]

    @staticmethod
    def str_to_coltype_general(
            coltype_str: str) -> Type[sqlatypes.TypeEngine]:
        """
        Get the sqlalchemy column type class which fits with the column type.
        """
        coltype = getattr(sqlatypes, coltype_str)
        # Check if 'coltype' is really an sqlalchemy column type
        if issubclass(coltype, sqlatypes.TypeEngine):
            return coltype

    @classmethod
    def unique_identifier(cls) -> str:
        """
        Create a unique (for this run) identifier for the output table. Only
        used if the remote processor has an empty string for the tablename,
        and no name is specified by the user.
        """
        cls.i += 1
        return f"anon_table{cls.i}"

    def is_tabular(self) -> bool:
        """
        Is the format of the schema information given by the remote processor
        tabular?
        """
        return self.schema_type == NlprpValues.TABULAR

    def get_tablename_from_type(self, output_type: str) -> str:
        return self._type_to_tablename[output_type]

    def get_otconf_from_type(self, output_type: str) -> OutputUserConfig:
        return self._outputtypemap[output_type]

    def _standard_columns_if_gate(self) -> List[Column]:
        """
        Returns standard columns for GATE output if ``self.format`` is GATE.
        """
        if self.format == NlpDefValues.FORMAT_GATE:
            return self._standard_gate_columns()
        else:
            return []

    def _standard_indexes_if_gate(self) -> List[Index]:
        """
        Returns standard indexes for GATE output if ``self.format`` is GATE.
        """
        if self.format == NlpDefValues.FORMAT_GATE:
            return self._standard_gate_indexes()
        else:
            return []

    def _confirm_available(self, available: bool = True) -> None:
        """
        Set the attribute 'available_remotely', which indicates whether
        a requested processor is actually available from the specified server.
        """
        self.available_remotely = available

    def set_procinfo_if_correct(self,
                                remote_processor: ServerProcessor) -> None:
        """
        Checks if a processor dictionary, with all the nlprp specified info
        a processor should have, belongs to this processor. If it does, then
        we add the information from the procesor dictionary.
        """
        if self.procname != remote_processor.name:
            return
        # if ((self.procversion is None and
        #         processor_dict[NKeys.IS_DEFAULT_VERSION]) or
        if ((self.procversion is None and
                remote_processor.is_default_version) or
                (self.procversion == remote_processor.version)):
            self._set_processor_info(remote_processor)

    def _set_processor_info(self, remote_processor: ServerProcessor) -> None:
        """
        Add the information from a processor dictionary. If it contains
        table information, this allows us to create the correct tables when
        the time comes.
        """
        # This won't be called unless the remote processor is available
        self._confirm_available()
        self.remote_processor_info = remote_processor
        # self.name = processor_dict[NKeys.NAME]
        self.schema_type = remote_processor.schema_type
        if self.is_tabular():
            self.schema = remote_processor.tabular_schema
            self.sql_dialect = remote_processor.sql_dialect
        # Check that, by this stage, we either have a tabular shcema from
        # the processor, or we have user-specified destfields
        assert self.is_tabular or all([x.get_destfields() for
                                      x in self._outputtypemap.values()]), (
            "You haven't specified a table structure and the processor hasn't "
            "provided one.")

    def _str_to_coltype(self, data_type_str: str) -> sqlatypes.TypeEngine:
        """
        This is supposed to get column types depending on the sql dialect
        used by the server, but it's not implemented yet.
        """
        raise NotImplementedError
        # if self.sql_dialect == SqlDialects.MSSQL:
        #     return self._str_to_coltype_mssql(data_type_str)
        # elif self.sql_dialect == SqlDialects.MYSQL:
        #     return self._str_to_coltype_mysql(data_type_str)
        # elif self.sql_dialect == SqlDialects.ORACLE:
        #     return self._str_to_coltype_oracle(data_type_str)
        # elif self.sql_dialect == SqlDialects.POSTGRES:
        #     return self._str_to_coltype_postgres(data_type_str)
        # elif self.sql_dialect == SqlDialects.SQLITE:
        #     return self._str_to_coltype_sqlite(data_type_str)
        # else:
        #     pass

    def _dest_tables_columns_user(self) -> Dict[str, List[Column]]:

        tables = {}  # type: Dict[str, List[Column]]

        for output_type, otconfig in self._outputtypemap.items():
            tables[otconfig.get_tablename()] = (
                self._standard_columns_if_gate() +
                otconfig.get_columns(self.get_engine())
            )
        return tables

    def _dest_tables_indexes_user(self) -> Dict[str, List[Index]]:
        tables = {}  # type: Dict[str, List[Index]]
        for output_type, otconfig in self._outputtypemap.items():
            tables[otconfig.get_tablename()] = (
                self._standard_indexes_if_gate() +
                otconfig.get_indexes()
            )
        return tables

    def _dest_tables_columns_auto(self) -> Dict[str, List[Column]]:
        """
        Gets the destination tables and their columns using the remote
        processor information.
        """
        tables = {}
        for table, columns in self.schema.items():
            # identifier = table if table else self.unique_identifier()
            # self.tablename = self.tablename if self.tablename else identifier
            column_objects = self._standard_columns_if_gate()  # type: List[Column]  # noqa
            if self.tablename:
                tablename = self.tablename
            else:
                tablename = self.get_tablename_from_type(table)
            # ... might be empty list
            for column in columns:
                col_str, parameter = self.get_coltype_parts(
                    column[NKeys.COLUMN_TYPE])
                data_type_str = column[NKeys.DATA_TYPE]
                coltype = self.str_to_coltype_general(data_type_str)
                column_objects.append(Column(
                    column[NKeys.COLUMN_NAME],
                    coltype if not parameter else coltype(parameter),
                    comment=column[NKeys.COLUMN_COMMENT],
                    nullable=column[NKeys.IS_NULLABLE]
                ))
            tables[tablename] = column_objects
        return tables

    def _dest_tables_indexes_auto(self) -> Dict[str, List[Index]]:
        if self.format != NlpDefValues.FORMAT_GATE:
            return {}  # indexes can't be returned by the server
        tables = {}  # type: Dict[str, List[Index]]
        for table in self.schema:
            tables[table] = self._standard_gate_indexes()
        return tables

    def dest_tables_indexes(self) -> Dict[str, List[Index]]:
        # Docstring in superclass
        if self._outputtypemap and all([x.get_destfields() for
                                        x in self._outputtypemap.values()]):
            return self._dest_tables_indexes_user()
        elif self.is_tabular():
            return self._dest_tables_indexes_auto()
        else:
            raise ValueError("You haven't specified a table structure and "
                             "the processor hasn't provided one.")

    def dest_tables_columns(self) -> Dict[str, List[Column]]:
        # Docstring in superclass
        if self._outputtypemap and all([x.get_destfields() for
                                        x in self._outputtypemap.values()]):
            return self._dest_tables_columns_user()
        elif self.is_tabular():
            # Must have processor-defined schema because we already checked
            # for it
            return self._dest_tables_columns_auto()
        else:
            raise ValueError("You haven't specified a table structure and "
                             "the processor hasn't provided one.")


