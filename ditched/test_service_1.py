#!/usr/bin/env python

"""
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
