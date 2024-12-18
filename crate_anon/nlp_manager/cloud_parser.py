"""
crate_anon/nlp_manager/cloud_parser.py

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

Send text to a cloud-based NLPRP server for processing.

"""

import logging
from typing import Any, Dict, List, Optional, Tuple, Type, Union

from cardinal_pythonlib.lists import chunks
from sqlalchemy.schema import Column, Index
from sqlalchemy import types as sqlatypes

from crate_anon.nlp_manager.nlp_definition import NlpDefinition
from crate_anon.nlp_manager.constants import ProcessorConfigKeys, NlpDefValues
from crate_anon.nlp_manager.output_user_config import OutputUserConfig
from crate_anon.nlprp.constants import NlprpKeys as NKeys, NlprpValues
from crate_anon.nlp_manager.base_nlp_parser import TableMaker
from crate_anon.nlp_webserver.server_processor import ServerProcessor

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

TABLE_STRUCTURE_UNSPECIFIED = (
    "You haven't specified a table structure and the processor hasn't "
    "provided one."
)


# =============================================================================
# Cloud class for cloud-based processsors
# =============================================================================


class Cloud(TableMaker):
    """
    EXTERNAL.

    Abstract NLP processor that passes information to a remote (cloud-based)
    NLP system via the NLPRP protocol. The processor at the other end might be
    of any kind.
    """

    _is_cloud_processor = True

    def __init__(
        self,
        nlpdef: Optional[NlpDefinition],
        cfg_processor_name: Optional[str],
        commit: bool = False,
    ) -> None:
        """
        Args:
            nlpdef:
                :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
            cfg_processor_name:
                the config section for the processor
            commit:
                force a COMMIT whenever we insert data? You should specify this
                in multiprocess mode, or you may get database deadlocks.
        """
        super().__init__(
            nlpdef, cfg_processor_name, commit, friendly_name="Cloud"
        )
        self.remote_processor_info = None  # type: Optional[ServerProcessor]
        self.schema_type = None
        self.sql_dialect = None
        self.schema = None  # type: Optional[Dict[str, Any]]
        self.available_remotely = False  # update later if available
        # Output section
        self._outputtypemap = {}  # type: Dict[str, OutputUserConfig]
        self._type_to_tablename = {}  # type: Dict[str, str]

        if not nlpdef and not cfg_processor_name:
            # Debugging only
            self.procname = ""
            self.procversion = ""
            self.format = ""
        else:
            self.procname = self._cfgsection.opt_str(
                ProcessorConfigKeys.PROCESSOR_NAME, required=True
            )
            self.procversion = self._cfgsection.opt_str(
                ProcessorConfigKeys.PROCESSOR_VERSION, default=None
            )
            # Made format required so people are less likely to make mistakes
            self.format = self._cfgsection.opt_str(
                ProcessorConfigKeys.PROCESSOR_FORMAT, required=True
            )
            # Output section - bit of repetition from the 'Gate' parser
            typepairs = self._cfgsection.opt_strlist(
                ProcessorConfigKeys.OUTPUTTYPEMAP, required=True, lower=False
            )
            for output_type, outputsection in chunks(typepairs, 2):
                output_type = output_type.lower()
                c = OutputUserConfig(
                    config_parser=nlpdef.parser,
                    cfg_output_name=outputsection,
                    schema_required=False,
                )
                self._outputtypemap[output_type] = c
                self._type_to_tablename[output_type] = c.dest_tablename
            # Also, ensure the user doesn't specify desttable (would be
            # confusing).
            if self._cfgsection.opt_str(ProcessorConfigKeys.DESTTABLE):
                raise ValueError(
                    f"For cloud processors, don't specify "
                    f"{ProcessorConfigKeys.DESTTABLE!r}; table information is "
                    f"in {ProcessorConfigKeys.OUTPUTTYPEMAP!r}"
                )

    @staticmethod
    def get_coltype_parts(coltype_str: str) -> Tuple[str, Union[str, int]]:
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
            except ValueError:  # e.g. "too many values to unpack"
                log.error(f"Invalid column type in response: {coltype_str}")
                raise
            try:
                # Turn the parameter into an integer if it's supposed to be one
                parameter = int(parameter)
            except ValueError:
                pass
        return col_str, parameter

    @staticmethod
    def data_type_str_to_coltype(
        data_type_str: str,
    ) -> Type[sqlatypes.TypeEngine]:
        """
        Get the SQLAlchemy column type class which fits with the data type
        specified. Currently we IGNORE self.sql_dialect.
        """
        coltype = getattr(sqlatypes, data_type_str)
        # Check if 'coltype' is really an sqlalchemy column type
        if issubclass(coltype, sqlatypes.TypeEngine):
            return coltype
        raise NotImplementedError(
            f"Don't know the SQLAlchemy column type corresponding to "
            f"data type: {data_type_str!r}"
        )

    def is_tabular(self) -> bool:
        """
        Is the format of the schema information given by the remote processor
        tabular?
        """
        return self.schema_type == NlprpValues.TABULAR

    def get_tabular_schema_tablenames(self) -> List[str]:
        """
        Returns the names of the tables in the tabular schema (or an empty list
        if we do not have a tabular schema).
        """
        if not self.is_tabular():
            return []
        return list(self.schema.keys())

    def get_local_from_remote_tablename(self, remote_tablename: str) -> str:
        """
        When the remote server specifies a table name, we need to map it to
        a local database table name.

        Raises KeyError on failure.
        """
        try:
            return self.get_tablename_from_type(remote_tablename)
        except KeyError:
            raise KeyError(
                "No local table name defined for remote table "
                f"{remote_tablename!r}"
            )

    def get_first_local_tablename(self) -> str:
        """
        Used in some circumstances when the remote processor doesn't specify
        a table.
        """
        assert len(self._type_to_tablename) > 0
        return self._type_to_tablename[0]

    def get_tablename_from_type(self, output_type: str) -> str:
        """
        For simple remote GATE processors, or cloud processors: for a given
        annotation type (GATE) or remote table name (cloud), return the
        destination table name.

        Enforces lower-case lookup.

        Will raise KeyError if this fails.
        """
        return self._type_to_tablename[output_type.lower()]

    def get_otconf_from_type(self, output_type: str) -> OutputUserConfig:
        """
        For a GATE annotation type, or cloud remote table name, return the
        corresponding OutputUserConfig.

        Enforces lower-case lookup.

        Will raise KeyError if this fails.
        """
        return self._outputtypemap[output_type.lower()]

    def _standard_columns_if_gate(self) -> List[Column]:
        """
        Returns standard columns for GATE output if ``self.format`` is GATE.
        Returns an empty list otherwise.
        """
        if self.format == NlpDefValues.FORMAT_GATE:
            return self._standard_gate_columns()
        else:
            return []

    def _standard_indexes_if_gate(self) -> List[Index]:
        """
        Returns standard indexes for GATE output if ``self.format`` is GATE.
        Returns an empty list otherwise.
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

    def set_procinfo_if_correct(
        self, remote_processor: ServerProcessor
    ) -> None:
        """
        Checks if a processor dictionary, with all the NLPLP-specified info
        a processor should have, belongs to this processor. If it does, then
        we add the information from the procesor dictionary.
        """
        if self.procname != remote_processor.name:
            return
        if (remote_processor.is_default_version and not self.procversion) or (
            self.procversion == remote_processor.version
        ):
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
        if remote_processor.is_tabular():
            self.schema = remote_processor.tabular_schema
            self.sql_dialect = remote_processor.sql_dialect
        # Check that, by this stage, we either have a tabular schema from
        # the processor, or we have user-specified destfields
        assert self.is_tabular() or all(
            x.destfields for x in self._outputtypemap.values()
        ), TABLE_STRUCTURE_UNSPECIFIED

    def dest_tables_columns(self) -> Dict[str, List[Column]]:
        """
        Describes the destination table(s) that this NLP processor wants to
        write to.

        Returns:
             dict: a dictionary of ``{tablename: destination_columns}``, where
             ``destination_columns`` is a list of SQLAlchemy :class:`Column`
             objects.

        If there is an NLPRP remote table specification (tabular_schema
        method), we start with that.

        Then we add any user-defined tables. If there is both a remote
        definition and a local definition, the local definition overrides the
        remote definition. If the destination table info has no columns,
        however, it is not used for table creation.

        There may in principle be other tables too in the local config that are
        absent in the remote info (unusual!).
        """
        table_columns = {}  # type: Dict[str, List[Column]]

        # 1. NLPRP remote specification.
        if self.is_tabular():
            for remote_tablename, columndefs in self.schema.items():
                # We may start with predefined GATE columns (but this might
                # return an empty list). We'll then add to it, if additional
                # information is provided.
                column_objects = []  # type: List[Column]
                dest_tname = self.get_local_from_remote_tablename(
                    remote_tablename
                )
                column_renames = self.get_otconf_from_type(
                    remote_tablename
                ).renames
                for column_info in columndefs:
                    colname = column_info[NKeys.COLUMN_NAME]
                    # Rename (or keep the same if no applicable rename):
                    colname = column_renames.get(colname, colname)
                    col_str, parameter = self.get_coltype_parts(
                        column_info[NKeys.COLUMN_TYPE]
                    )
                    data_type_str = column_info[NKeys.DATA_TYPE]
                    # We could use col_str or data_type_str here.
                    coltype = self.data_type_str_to_coltype(data_type_str)
                    column_objects.append(
                        Column(
                            name=colname,
                            type_=coltype(parameter) if parameter else coltype,
                            comment=column_info.get(NKeys.COLUMN_COMMENT),
                            nullable=column_info[NKeys.IS_NULLABLE],
                        )
                    )
                if not column_objects:
                    raise ValueError(
                        "Remote error: NLPRP server declares table "
                        f"{remote_tablename!r} but provides no column "
                        "information for it."
                    )
                table_columns[dest_tname] = column_objects

        # 2. User specification.
        for output_type, otconfig in self._outputtypemap.items():
            if otconfig.destfields:
                # The user has specified columns.
                table_columns[
                    otconfig.dest_tablename
                ] = self._standard_columns_if_gate() + otconfig.get_columns(
                    self.dest_engine
                )
            else:
                # The user has noted the existence of the table, but hasn't
                # specified columns.
                if otconfig.dest_tablename not in table_columns:
                    raise ValueError(
                        f"Local table {otconfig.dest_tablename!r} has no "
                        "remote definition, and no columns are defined for it "
                        "in the config file either."
                    )
                # Otherwise: defined remotely, with no local detail; that's OK.
                continue

        # Done.
        return table_columns

    def dest_tables_indexes(self) -> Dict[str, List[Index]]:
        """
        Describes indexes that this NLP processor suggests for its destination
        table(s).

        Returns:
             dict: a dictionary of ``{tablename: indexes}``, where ``indexes``
             is a list of SQLAlchemy :class:`Index` objects.

        The NLPRP remote table specification doesn't include indexing. So all
        indexing information is from our config file, whether for GATE or
        cloud processors.
        """
        table_indexes = {}  # type: Dict[str, List[Index]]
        for output_type, otconfig in self._outputtypemap.items():
            table_indexes[otconfig.dest_tablename] = (
                self._standard_indexes_if_gate() + otconfig.indexes
            )
        return table_indexes
