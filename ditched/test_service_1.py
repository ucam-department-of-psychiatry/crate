#!/usr/bin/env python

"""
ditched/test_service_1.py

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

http://stackoverflow.com/questions/32404/is-it-possible-to-run-a-python-script-as-a-service-in-windows-if-possible-how  # noqa
http://stackoverflow.com/questions/25770873/python-windows-service-pyinstaller-executables-error-1053  # noqa
"""

import socket
import time

import win32serviceutil
import win32service
import win32event
import servicemanager


# noinspection PyPep8Naming
class AppServerSvc(win32serviceutil.ServiceFramework):
    _svc_name_ = "TestService"
    _svc_display_name_ = "Test Service"
    _svc_description_ = "Test service (Windows service via Python)"

    def __init__(self, args) -> None:
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)

    def SvcStop(self) -> None:
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self) -> None:
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ''))
        self.main()

    @staticmethod
    def main() -> None:
        while True:
            with open(r"C:\current_time.txt", "w") as f:
                f.write("The time is now " + time.ctime() + "\n")
            time.sleep(5)


if __name__ == '__main__':
    win32serviceutil.HandleCommandLine(AppServerSvc)
