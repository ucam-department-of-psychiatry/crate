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

from crate_anon.nlp_manager.base_nlp_parser import BaseNlpParser
from crate_anon.nlp_manager.all_processors import make_nlp_parser_unconfigured
from crate_anon.nlprp.api import JsonObjectType
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
)
from crate_anon.nlp_webserver.settings import SETTINGS


proc_file = SETTINGS[NlpServerConfigKeys.PROCESSORS_PATH]
# from processor_file import PROCESSORS  # doesn't work, need importlib

# Import the processors module using the full path as it is configurable
spec = importlib.util.spec_from_file_location("processors", proc_file)
processors = importlib.util.module_from_spec(spec)
spec.loader.exec_module(processors)


class Processor(object):
    """
    Class for containing information about NLP processors known to an NLPRP
    server.

    For ease of finding processor info based on name and version
    (alternative would be a dictionary in which the keys were name_version
    and the values were another dictionary with the rest of the info)
    """

    # Master list of all instances (processors)
    processors = {}  # type: Dict[str, "Processor"]

    def __init__(self,
                 name: str,
                 title: str,
                 version: str,
                 is_default_version: bool,
                 description: str,
                 proctype: Optional[str] = None,
                 schema_type: str = NlprpValues.UNKNOWN,
                 sql_dialect: Optional[str] = None,
                 tabular_schema: Optional[Dict[str, Any]] = None) -> None:
        assert schema_type in (NlprpValues.UNKNOWN, NlprpValues.TABULAR), (
            "'schema_type' must be one of '{NlprpValues.UNKNOWN}', "
            "'{NlprpValues.TABULAR}' for each processor.")
        self.name = name
        self.title = title
        self.version = version
        self.is_default_version = is_default_version
        self.description = description
        self.processor_id = "{}_{}".format(self.name, self.version)

        self.parser = None  # type: Optional[BaseNlpParser]
        if not proctype:
            self.proctype = name
        else:
            self.proctype = proctype
        self.dict = {
            NlprpKeys.NAME: name,
            NlprpKeys.TITLE: title,
            NlprpKeys.VERSION: version,
            NlprpKeys.IS_DEFAULT_VERSION: is_default_version,
            NlprpKeys.DESCRIPTION: description,
            NlprpKeys.SCHEMA_TYPE: schema_type,
        }

        if schema_type == NlprpValues.TABULAR:
            self.dict[NlprpKeys.SQL_DIALECT] = sql_dialect
            self.dict[NlprpKeys.TABULAR_SCHEMA] = tabular_schema

        # Add instance to list of processors
        Processor.processors[self.processor_id] = self

    @classmethod
    def get_processor(cls, name: str,
                      version: str = "") -> "Processor":
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
            -> "Processor":
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
    def get_processor_from_id(cls, processor_id: str) -> "Processor":
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
    x = Processor(
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
