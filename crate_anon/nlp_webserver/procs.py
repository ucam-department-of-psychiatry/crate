#!/usr/bin/env python

r"""
crate_anon/nlp_webserver/procs.py

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

Representation of NLP processors used by CRATE's NLPRP server.

"""

import importlib.util
from typing import Dict, Optional, Any
import logging

from crate_anon.nlp_manager.base_nlp_parser import BaseNlpParser
from crate_anon.nlp_manager.all_processors import make_nlp_parser_unconfigured
from crate_anon.nlprp.api import JsonObjectType, NlprpServerProcessor
from crate_anon.nlprp.constants import NlprpKeys, NlprpValues
from crate_anon.nlprp.errors import (
    BAD_REQUEST,
    mkerror,
    no_such_proc_error,
)
from crate_anon.nlp_webserver.constants import (
    KEY_PROCTYPE,
    NlpServerConfigKeys,
    PROCTYPE_GATE,
    GATE_BASE_URL,
)
from crate_anon.nlp_webserver.settings import SETTINGS

log = logging.getLogger(__name__)

proc_file = SETTINGS[NlpServerConfigKeys.PROCESSORS_PATH]
# from processor_file import PROCESSORS  # doesn't work, need importlib

# Import the processors module using the full path as it is configurable
spec = importlib.util.spec_from_file_location("processors", proc_file)
processors = importlib.util.module_from_spec(spec)
spec.loader.exec_module(processors)


class ServerProcessor(NlprpServerProcessor):
    """
    Adds extra information to
    :class:`crate_anon.nlprp.api.NlprpServerProcessor`.

    - For ease of finding processor info based on name and version
      (alternative would be a dictionary in which the keys were name_version
      and the values were another dictionary with the rest of the info).

    - Also used as the client-side representation.
    """

    # Master list of all instances (processors)
    processors = {}  # type: Dict[str, "ServerProcessor"]

    def __init__(self,
                 name: str,
                 title: str,
                 version: str,
                 is_default_version: bool,
                 description: str,
                 schema_type: str = NlprpValues.UNKNOWN,
                 sql_dialect: Optional[str] = None,
                 tabular_schema: Optional[Dict[str, Any]] = None,
                 proctype: Optional[str] = None) -> None:
        super().__init__(
            name=name,
            title=title,
            version=version,
            is_default_version=is_default_version,
            description=description,
            schema_type=schema_type,
            sql_dialect=sql_dialect,
            tabular_schema=tabular_schema
        )
        if len(self.processor_id) > 100:
            raise ValueError(f"Processor id {self.processor_id} is too "
                             "long for database field")

        self.base_url = None
        if proctype == PROCTYPE_GATE:
            self.base_url = GATE_BASE_URL

        self.parser = None  # type: Optional[BaseNlpParser]
        if not proctype:
            self.proctype = name
        else:
            self.proctype = proctype

        # Add instance to list of processors
        ServerProcessor.processors[self.processor_id] = self

    @property
    def processor_id(self) -> str:
        return f"{self.name}_{self.version}"

    @classmethod
    def get_processor(cls, name: str,
                      version: str = "") -> "ServerProcessor":
        """
        Fetch a processor by name and (optionally) version.

        Args:
            name: requested processor name
            version: (optional) requested processor version

        Returns:
            a :class:`Processor`

        Raises:
            :exc:`crate_anon.nlprp.errors.NlprpError` if no processor
            matches.
        """
        for candidate in cls.processors.values():
            if name == candidate.name:
                # Initially coded as case-insensitive (as someone might put
                # e.g. 'CRP' instead of 'Crp'), but has to be case-sensitive
                # because some of the GATE processors have the same name as the
                # Python ones only different case.
                if version:
                    # Specific version requested.
                    if version == candidate.version:
                        return candidate
                else:
                    # No specific version requested.
                    if candidate.is_default_version:
                        return candidate
        raise no_such_proc_error(name, version)

    @classmethod
    def get_processor_nlprp(cls, requested_processor_dict: JsonObjectType) \
            -> "ServerProcessor":
        """
        Fetch a processor, from an NLPRP dictionary specifying it.

        Args:
            requested_processor_dict: part of an NLPRP request

        Returns:
            a :class:`Processor`

        Raises:
            :exc:`crate_anon.nlprp.errors.NlprpError` if the
            ``NlprpKeys.NAME`` key is missing or no processor matches.
        """
        version = requested_processor_dict.get(NlprpKeys.VERSION)  # optional
        try:
            name = requested_processor_dict[NlprpKeys.NAME]  # may raise
        except KeyError:
            raise mkerror(BAD_REQUEST,
                          f"Processor request has no {NlprpKeys.NAME!r} key")
        return cls.get_processor(name=name, version=version)

    @classmethod
    def get_processor_from_id(cls, processor_id: str) -> "ServerProcessor":
        """
        Fetch a processor, from a processor ID (a string representing name and
        versio).

        Args:
            processor_id: string in the format ``name_version``. The version
                part can't contain an underscore, but the name can.

        Returns:
            a :class:`Processor`

        Raises:
            :exc:`crate_anon.nlprp.errors.NlprpError` if no processor
            matches.
        """
        # Split on the last occurrence of '_'
        name, _, version = processor_id.rpartition("_")
        return cls.get_processor(name, version)

    def set_parser(self) -> None:
        """
        Sets 'self.parser' to an instance of a subclass of 'BaseNlpParser'
        not bound to any nlpdef or cfgsection, unless self.proctype is GATE
        (in which case, do nothing).
        """
        if self.proctype != PROCTYPE_GATE:
            # We do not have to supply a NLP definition here.
            self.parser = make_nlp_parser_unconfigured(self.proctype)
        # else: do nothing


for proc in processors.PROCESSORS:
    x = ServerProcessor(
        name=proc[NlprpKeys.NAME],
        title=proc[NlprpKeys.TITLE],
        version=proc[NlprpKeys.VERSION],
        is_default_version=proc[NlprpKeys.IS_DEFAULT_VERSION],
        description=proc[NlprpKeys.DESCRIPTION],
        proctype=proc.get(KEY_PROCTYPE),  # may be None
        schema_type=proc[NlprpKeys.SCHEMA_TYPE],  # 'unknown' or 'tabular'
        sql_dialect=proc.get(NlprpKeys.SQL_DIALECT),
        tabular_schema=proc.get(NlprpKeys.TABULAR_SCHEMA)
    )
    # Doing this here saves time per request
    x.set_parser()
