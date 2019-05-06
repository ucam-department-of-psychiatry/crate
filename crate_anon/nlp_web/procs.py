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

from typing import Optional
import importlib.util

from crate_anon.nlp_manager.base_nlp_parser import BaseNlpParser
from crate_anon.nlp_manager.all_processors import make_processor
from crate_anon.nlprp.constants import NlprpKeys as NKeys
from crate_anon.nlp_web.constants import (
    KEY_PROCTYPE,
    # PROCESSORS,
    KEY_PROCPATH,
    SETTINGS,
    PROCTYPE_GATE,
)

proc_file = SETTINGS[KEY_PROCPATH]
# from processor_file import PROCESSORS  # doesn't work, need importlib

# Import the processors module using the full path as it is configurable
spec = importlib.util.spec_from_file_location("processors", proc_file)
processors = importlib.util.module_from_spec(spec)
spec.loader.exec_module(processors)


class Processor(object):
    """
    Class for containing information about processors.

    For ease of finding processor info based on name and version
    (alternative would be a dictionary in which the keys were name_version
    and the values were another dictionary with the rest of the info)
    """
    # Master list of all instances (processors)
    processors = {}

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

        self.parser = None  # type: BaseNlpParser
        if not proctype:
            self.proctype = name
        else:
            self.proctype = proctype
        self.dict = {
            NKeys.NAME: name,
            NKeys.TITLE: title,
            NKeys.VERSION: version,
            NKeys.IS_DEFAULT_VERSION: is_default_version,
            NKeys.DESCRIPTION: description,
        }

        # Add instance to list of processors
        Processor.processors[self.processor_id] = self

    def set_parser(self) -> None:
        """
        Sets 'self.parser' to an instance of a subclass of 'BaseNlpParser'
        not bound to any nlpdef or cfgsection, unless self.proctype is GATE.'
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
        name=proc[NKeys.NAME],
        title=proc[NKeys.TITLE],
        version=proc[NKeys.VERSION],
        is_default_version=proc[NKeys.IS_DEFAULT_VERSION],
        description=proc[NKeys.DESCRIPTION],
        proctype=proc.get(KEY_PROCTYPE)
    )
    # Doing this here saves time per request
    x.set_parser()
