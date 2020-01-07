#!/usr/bin/env python

r"""
crate_anon/nlp_webserver/procs.py

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

Representation of NLP processors used by CRATE's NLPRP server.

"""

import importlib.util
import logging

from crate_anon.nlprp.constants import NlprpKeys
from crate_anon.nlp_webserver.constants import (
    KEY_PROCTYPE,
    NlpServerConfigKeys,
)
from crate_anon.nlp_webserver.server_processor import ServerProcessor
from crate_anon.nlp_webserver.settings import SETTINGS

log = logging.getLogger(__name__)

proc_file = SETTINGS[NlpServerConfigKeys.PROCESSORS_PATH]
# from processor_file import PROCESSORS  # doesn't work, need importlib

# Import the processors module using the full path as it is configurable
spec = importlib.util.spec_from_file_location("processors", proc_file)
processors = importlib.util.module_from_spec(spec)
spec.loader.exec_module(processors)


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
