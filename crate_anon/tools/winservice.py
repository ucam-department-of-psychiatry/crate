#!/usr/bin/env python

r"""
crate_anon/tools/winservice.py

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

**Run the CRATE web service as a Windows service.**

See notes in ``cardinal_pythonlib/winservice.py``.

"""  # noqa

import os
import logging
import sys

from cardinal_pythonlib.winservice import (
    ProcessDetails,
    generic_service_main,
    WindowsService,
)

log = logging.getLogger(__name__)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ENVVAR = 'CRATE_WINSERVICE_LOGDIR'


# =============================================================================
# Windows service framework
# =============================================================================

class CratewebService(WindowsService):
    """
    Windows service class for CRATE.
    """
    # you can NET START/STOP the service by the following name
    _svc_name_ = "CRATE"
    # this text shows up as the service name in the Service
    # Control Manager (SCM)
    _svc_display_name_ = "CRATE web service"
    # this text shows up as the description in the SCM
    _svc_description_ = "Runs Django/Celery processes for CRATE web site"
    # how to launch?
    _exe_name_ = sys.executable  # python.exe in the virtualenv
    _exe_args_ = f'"{os.path.realpath(__file__)}"'  # this script

    # -------------------------------------------------------------------------
    # The service
    # -------------------------------------------------------------------------

    def service(self) -> None:
        """
        Run the service.

        - Reads the log directory from the environment variable
          ``CRATE_WINSERVICE_LOGDIR``.
        - Launches the Django process (front-end web service).
        - Launches the Celery process (back-end job management).
        """
        # Read from environment
        # self.info(repr(os.environ))
        try:
            logdir = os.environ[ENVVAR]
        except KeyError:
            raise ValueError(
                f"Must specify {ENVVAR} system environment variable")

        # Define processes
        djangolog = os.path.join(logdir, 'crate_log_django.txt')
        celerylog = os.path.join(logdir, 'crate_log_celery.txt')
        procdetails = [
            ProcessDetails(
                name='Django/CherryPy',
                procargs=[
                    sys.executable,
                    os.path.join(CURRENT_DIR, 'launch_cherrypy_server.py'),
                ],
                logfile_out=djangolog,
                logfile_err=djangolog,
            ),
            ProcessDetails(
                name='Celery',
                procargs=[
                    sys.executable,
                    os.path.join(CURRENT_DIR, 'launch_celery.py'),
                ],
                logfile_out=celerylog,
                logfile_err=celerylog,
            ),
        ]

        # Run processes
        self.run_processes(procdetails)


# =============================================================================
# Main
# =============================================================================

def main():
    """
    Command-line entry point.
    """
    # Called as an entry point (see setup.py).
    logging.basicConfig(level=logging.DEBUG)
    generic_service_main(CratewebService, 'CratewebService')


if __name__ == '__main__':
    main()
