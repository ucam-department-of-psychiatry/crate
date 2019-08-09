#!/usr/bin/env python

r"""
crate_anon/nlp_web/procs.py

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
"""

import importlib.util
from typing import Any, Dict, Optional

from crate_anon.nlp_manager.base_nlp_parser import BaseNlpParser
from crate_anon.nlp_manager.all_processors import make_processor
from crate_anon.nlprp.constants import NlprpKeys
from crate_anon.nlp_web.constants import (
    KEY_PROCTYPE,
    KEY_PROCPATH,
    SETTINGS,
    PROCTYPE_GATE,
)
from crate_anon.nlp_web.errors import (
    BAD_REQUEST,
    mkerror,
    no_such_proc_error,
)


proc_file = SETTINGS[KEY_PROCPATH]
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
                 proctype: Optional[str] = None) -> None:
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
        }

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
            :exc:`crate_anon.nlp_web.errors.NlprpError` if no processor
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
    def get_processor_nlprp(cls, requested_processor_dict: Dict[str, Any]) \
            -> "Processor":
        """
        Fetch a processor, from an NLPRP dictionary specifying it.

        Args:
            requested_processor_dict: part of an NLPRP request

        Returns:
            a :class:`Processor`

        Raises:
            :exc:`crate_anon.nlp_web.errors.NlprpError` if the
            ``NlprpKeys.NAME`` key is missing or no processor matches.
        """
        version = requested_processor_dict.get(NlprpKeys.VERSION)
        try:
            name = requested_processor_dict[NlprpKeys.NAME]  # may raise
        except KeyError:
            raise mkerror(BAD_REQUEST,
                          f"Processor request has no {NlprpKeys.NAME!r} key")
        return cls.get_processor(name=name, version=version)

    def set_parser(self) -> None:
        """
        Sets 'self.parser' to an instance of a subclass of 'BaseNlpParser'
        not bound to any nlpdef or cfgsection, unless self.proctype is GATE.
        """
        if self.proctype != PROCTYPE_GATE:
            # Suppressed warning because, although make_processor asks for
            # NlpDefinition, str, the processor it makes doesn't require this
            # noinspection PyTypeChecker
            self.parser = make_processor(processor_type=self.proctype,
                                         nlpdef=None, section=None)
        # else: do nothing


for proc in processors.PROCESSORS:
    x = Processor(
        name=proc[NlprpKeys.NAME],
        title=proc[NlprpKeys.TITLE],
        version=proc[NlprpKeys.VERSION],
        is_default_version=proc[NlprpKeys.IS_DEFAULT_VERSION],
        description=proc[NlprpKeys.DESCRIPTION],
        proctype=proc.get(KEY_PROCTYPE)
    )
    # Doing this here saves time per request
    x.set_parser()
