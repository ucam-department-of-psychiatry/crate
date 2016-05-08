#!/usr/bin/env python

"""
Run the CRATE web service as a Windows service.

Details:
    http://stackoverflow.com/questions/32404
    http://www.chrisumbel.com/article/windows_services_in_python

Synopsis:
    - INSTALL: run this script with "install" argument, as administrator
    - RUN: use Windows service manager, or NET START CRATE
    - STOP: use Windows service manager, or NET STOP CRATE

Windows functions:
    - CreateEvent: https://msdn.microsoft.com/en-us/library/windows/desktop/ms682396(v=vs.85).aspx  # noqa
    - WaitForSingleObject: https://msdn.microsoft.com/en-us/library/windows/desktop/ms687032(v=vs.85).aspx  # noqa
"""

import win32service  # part of pypiwin32
import win32serviceutil  # part of pypiwin32
import win32event  # part of pypiwin32


class CratewebService(win32serviceutil.ServiceFramework):
    # you can NET START/STOP the service by the following name
    _svc_name_ = "CRATE"
    # this text shows up as the service name in the Service
    # Control Manager (SCM)
    _svc_display_name_ = "CRATE web service"
    # this text shows up as the description in the SCM
    _svc_description_ = "Runs Django/Celery processes for CRATE web site"

    def __init__(self, args):
        super().__init__(args)
        # create an event to listen for stop requests on
        self.h_stop_event = win32event.CreateEvent(None, 0, 0, None)

    # core logic of the service
    # noinspection PyPep8Naming
    def SvcDoRun(self):
        import servicemanager  # part of pypiwin32  # pointless? ***

        f = open(r'D:\test_win_svc.txt', 'w+')
        retcode = None

        # if the stop event hasn't been fired keep looping
        while retcode != win32event.WAIT_OBJECT_0:
            f.write('TEST DATA\n')
            f.flush()
            # block for 5 seconds and listen for a stop event
            retcode = win32event.WaitForSingleObject(self.h_stop_event, 5000)

        f.write('SHUTTING DOWN\n')
        f.close()

    # called when we're being shut down
    # noinspection PyPep8Naming
    def SvcStop(self):
        # tell the SCM we're shutting down
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        # fire the stop event
        win32event.SetEvent(self.h_stop_event)


def main():
    win32serviceutil.HandleCommandLine(CratewebService)


if __name__ == '__main__':
    main()
