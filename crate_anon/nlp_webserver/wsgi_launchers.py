#!/usr/bin/env python

r"""
crate_anon/nlp_webserver/wsgi_launchers.py

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

Launch different web servers with arbitrary WSGI applications.

"""

import logging
from typing import Any, Dict

from cardinal_pythonlib.wsgi.constants import TYPE_WSGI_APP

log = logging.getLogger(__name__)


# noinspection PyUnusedLocal
def cherrypy(wsgi_application: TYPE_WSGI_APP,
             global_conf: Dict[str, Any],
             **kwargs) -> int:
    """
    Start the CherryPy server.

    Arrives here from the relevant ``paste.server_runner`` entry point in
    ``setup.py``.
    """
    try:
        import cherrypy
    except ImportError:
        log.critical("You must install CherryPy first (pip install CherryPy).")
        raise

    args_to_int = [  # Parameters that must be integer, not string
        "server.socket_port",
    ]
    for a in args_to_int:
        if a in kwargs:
            kwargs[a] = int(kwargs[a])

    log.debug(f"Launching CherryPy with settings: {kwargs!r}")
    cherrypy.config.update(kwargs)
    cherrypy.tree.graft(wsgi_application, "/")

    # noinspection PyBroadException,PyPep8
    try:
        cherrypy.engine.start()
        cherrypy.engine.block()
    except:
        cherrypy.engine.stop()
    return 0


def waitress(wsgi_application: TYPE_WSGI_APP,
             global_conf: Dict[str, Any],
             **kwargs) -> int:
    """
    Start the Waitress server.

    Arrives here from the relevant ``paste.server_runner`` entry point in
    ``setup.py``.
    """
    try:
        import waitress
    except ImportError:
        log.critical("You must install Waitress first (pip install waitress).")
        raise
    log.debug(f"Launching Waitress with "
              f"global_conf = {global_conf!r}, kwargs = {kwargs!r}")
    return waitress.serve_paste(wsgi_application, global_conf, **kwargs)
