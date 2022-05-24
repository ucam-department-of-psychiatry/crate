#!/usr/bin/env python

r"""
crate_anon/nlp_webserver/procs.py

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

Representation of NLP processors used by CRATE's NLPRP server.

"""

import logging
import importlib.util
import os

from crate_anon.common.constants import EnvVar
from crate_anon.nlprp.constants import NlprpKeys
from crate_anon.nlp_webserver.constants import (
    KEY_PROCTYPE,
    NlpServerConfigKeys,
)
from crate_anon.nlp_webserver.server_processor import ServerProcessor
from crate_anon.nlp_webserver.settings import SETTINGS

log = logging.getLogger(__name__)

if EnvVar.GENERATING_CRATE_DOCS not in os.environ:
    _proc_file = SETTINGS[NlpServerConfigKeys.PROCESSORS_PATH]
    # from processor_file import PROCESSORS  # doesn't work, need importlib

    # Import the processors module using the full path as it is configurable
    _spec = importlib.util.spec_from_file_location("processors", _proc_file)
    _processors = importlib.util.module_from_spec(_spec)
    # noinspection PyUnresolvedReferences
    _spec.loader.exec_module(_processors)

    # noinspection PyUnresolvedReferences
    for _proc in _processors.PROCESSORS:
        _name = _proc[NlprpKeys.NAME]
        _version = _proc[NlprpKeys.VERSION]
        log.info(f"Registering NLPRP processor {_name!r} (v{_version})")
        _x = ServerProcessor(
            name=_name,
            title=_proc[NlprpKeys.TITLE],
            version=_version,
            is_default_version=_proc[NlprpKeys.IS_DEFAULT_VERSION],
            description=_proc[NlprpKeys.DESCRIPTION],
            proctype=_proc.get(KEY_PROCTYPE),  # may be None
            schema_type=_proc[NlprpKeys.SCHEMA_TYPE],  # 'unknown' or 'tabular'
            sql_dialect=_proc.get(NlprpKeys.SQL_DIALECT),
            tabular_schema=_proc.get(NlprpKeys.TABULAR_SCHEMA),
        )  # registers with the ServerProcessor class
        # Doing this here saves time per request
        _x.set_parser()
