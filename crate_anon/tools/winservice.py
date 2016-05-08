#!/usr/bin/env python

r"""
Run the CRATE web service as a Windows service.

Details:
    http://stackoverflow.com/questions/32404
    http://www.chrisumbel.com/article/windows_services_in_python
    http://code.activestate.com/recipes/551780-win-services-helper/
    http://docs.activestate.com/activepython/2.4/pywin32/PyWin32.HTML
        http://docs.activestate.com/activepython/2.4/pywin32/modules.html
    source:
        ...venv.../Lib/site-packages/win32/lib/win32serviceutil.py
    http://docs.activestate.com/activepython/3.3/pywin32/servicemanager.html
    http://timgolden.me.uk/pywin32-docs/contents.html

Synopsis:
    - INSTALL: run this script with "install" argument, as administrator
    - RUN: use Windows service manager, or NET START CRATE
    - STOP: use Windows service manager, or NET STOP CRATE
    - STATUS: SC QUERY CRATE
    - DEBUG: run this script with "debug" argument
        Log messages are sent to the console.
        Press CTRL-C to abort.

If the debug script succeeds but the start command doesn't...
    - Find the service in the Windows service manage.
    - Right-click it and inspect its properties. You'll see the name of the
      actual program being run, e.g.
        D:\venvs\crate\Lib\site-packages\win32\pythonservice.exe
    - Try running this from the command line (outside any virtual 
      environment).
     
    - In my case this failed with:
        pythonservice.exe - Unable to Locate Component
        This application has failed to start because pywintypes34.dll was not
        found. Re-installing the application may fix this problem.
    - That DLL was in:
        D:\venvs\crate\Lib\site-packages\pypiwin32_system32
      ... so add that to the system PATH
      ... and reboot
      ... and then it's happy.
    - However, that's not ideal for a virtual environment!
    - Looking at win32serviceutil.py, it seems we could do better by
      specifying _exe_name_ (to replace the default PythonService.exe) and
      _exe_args_. The sequence 
            myscript.py install
            -> win32serviceutil.HandleCommandLine()
                ... fishes things out of cls._exe_name_, etc.
            -> win32serviceutil.InstallService()
                ... builds a command line
                ... by default:
                "d:\venvs\crate\lib\site-packages\win32\PythonService.exe"
            -> win32service.CreateService()
    - So how, in the normal situation, does PythonService.exe find our
      script?
    - At this point, see also http://stackoverflow.com/questions/34696815
    - Source code is:
      https://github.com/tjguk/pywin32/blob/master/win32/src/PythonService.cpp
    
    - Starting a service directly with PrepareToHostSingle:
      https://mail.python.org/pipermail/python-win32/2008-April/007299.html
      https://mail.python.org/pipermail/python-win32/2010-May/010487.html
      
    - SUCCESS! Method is:
    
      In service class:
      
        _exe_name_ = sys.executable  # python.exe in the virtualenv
        _exe_args_ = '"{}"'.format(os.path.realpath(__file__))  # this script

      In main:

        if len(sys.argv) == 1:
            try:
                print("Trying to start service directly...")
                evtsrc_dll = os.path.abspath(servicemanager.__file__)
                servicemanager.PrepareToHostSingle(CratewebService)  # CLASS
                servicemanager.Initialize('aservice', evtsrc_dll)
                servicemanager.StartServiceCtrlDispatcher()
            except win32service.error as details:
                print("Failed: {}".format(details))
                # print(repr(details.__dict__))
                errnum = details.winerror
                if errnum == winerror.ERROR_FAILED_SERVICE_CONTROLLER_CONNECT:
                    win32serviceutil.usage()
        else:
            win32serviceutil.HandleCommandLine(CratewebService)  # CLASS
            
    - Now, if you run it directly with no arguments, from a command prompt, 
      it will fail and print the usage message, but if you run it from the
      service manager (with no arguments), it'll start the service. Everything
      else seems to work. Continues to work when the PATH doesn't include the
      virtual environment.

    - However, it breaks the "debug" option. The "debug" option reads the
      registry about the INSTALLED service to establish the name of the program
      that it runs. It assumes PythonService.exe.


Script parameters:
    If you run this script with no parameters, you'll see this:

    Usage: 'crate_windows_service-script.py [options] install|update|remove|start [...]|stop|restart [...]|debug [...]'
    Options for 'install' and 'update' commands only:
     --username domain\username : The Username the service is to run under
     --password password : The password for the username
     --startup [manual|auto|disabled|delayed] : How the service starts, default = manual
     --interactive : Allow the service to interact with the desktop.
     --perfmonini file: .ini file to use for registering performance monitor data
     --perfmondll file: .dll file to use when querying the service for
       performance data, default = perfmondata.dll
    Options for 'start' and 'stop' commands only:
     --wait seconds: Wait for the service to actually start or stop.
                     If you specify --wait with the 'stop' option, the service
                     and all dependent services will be stopped, each waiting
                     the specified period.

    Windows functions:
        - CreateEvent: https://msdn.microsoft.com/en-us/library/windows/desktop/ms682396(v=vs.85).aspx
        - WaitForSingleObject: https://msdn.microsoft.com/en-us/library/windows/desktop/ms687032(v=vs.85).aspx
"""  # noqa

import os
import sys

import arrow
import servicemanager  # part of pypiwin32
import winerror  # part of pypiwin32
import win32event  # part of pypiwin32
import win32service  # part of pypiwin32
import win32serviceutil  # part of pypiwin32

from crate_anon.anonymise.subproc import (
    run_multiple_processes
)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_FILENAME = r'C:\test_win_svc.txt'
TEST_PERIOD_MS = 5000


class CratewebService(win32serviceutil.ServiceFramework):
    # you can NET START/STOP the service by the following name
    _svc_name_ = "CRATE"
    # this text shows up as the service name in the Service
    # Control Manager (SCM)
    _svc_display_name_ = "CRATE web service"
    # this text shows up as the description in the SCM
    _svc_description_ = "Runs Django/Celery processes for CRATE web site"
    # how to launch?
    _exe_name_ = sys.executable  # python.exe in the virtualenv
    _exe_args_ = '"{}"'.format(os.path.realpath(__file__))  # this script

    def __init__(self, args=None):
        if args is not None:
            super().__init__(args)
        # create an event to listen for stop requests on
        self.h_stop_event = win32event.CreateEvent(None, 0, 0, None)

    @staticmethod
    def log(msg):
        servicemanager.LogInfoMsg(str(msg))

    # called when we're being shut down
    # noinspection PyPep8Naming
    def SvcStop(self):
        # tell the SCM we're shutting down
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        # fire the stop event
        win32event.SetEvent(self.h_stop_event)
        
    # called when service is started
    # noinspection PyPep8Naming
    def SvcDoRun(self):
        print("hello")
        # No need to self.ReportServiceStatus(win32service.SERVICE_RUNNING);
        # that is done by the framework (see win32serviceutil.py).
        # Similarly, no need to report a SERVICE_STOP_PENDING on exit.
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ''))
        # self.test_service()  # test service
        self.main()  # real service

    def test_service(self, filename=TEST_FILENAME, period_ms=TEST_PERIOD_MS):
        # A test service. This works! (As long as you can write to the file.)
        def write(msg):
            f.write('{}: {}\n'.format(arrow.now(), msg))
            f.flush()

        self.log("Starting test service; writing data periodically to "
                 "{}".format(TEST_FILENAME))
        f = open(filename, 'a')  # open for append
        write('STARTING')
        retcode = None
        # if the stop event hasn't been fired keep looping
        while retcode != win32event.WAIT_OBJECT_0:
            write('Test data; will now wait {} ms'.format(period_ms))
            # block for a while seconds and listen for a stop event
            retcode = win32event.WaitForSingleObject(self.h_stop_event, 
                                                     period_ms)
        write('SHUTTING DOWN')
        f.close()
        self.log("Test service FINISHED.")

    def main(self):
        # Actual main service code.
        django_script = os.path.join(CURRENT_DIR, os.pardir, 'crateweb',
                                     'manage.py')
        celery_script = os.path.join(CURRENT_DIR, 'launch_django_debug.py')
        django_args = [
            sys.executable,
            django_script,
            'runcpserver'
        ]
        celery_args = [
            sys.executable,
            celery_script,
        ]
        args_list = [django_args, celery_args]
        run_multiple_processes(args_list)
        win32event.WaitForSingleObject(self.h_stop_event, win32event.INFINITE)

    def debug(self):
        self.main()


def generic_service_main(cls, name):
    # https://mail.python.org/pipermail/python-win32/2008-April/007299.html
    argc = len(sys.argv)
    if argc == 1:
        try:
            print("Trying to start service directly...")
            evtsrc_dll = os.path.abspath(servicemanager.__file__)
            servicemanager.PrepareToHostSingle(cls)
            servicemanager.Initialize(name, evtsrc_dll)
            servicemanager.StartServiceCtrlDispatcher()
        except win32service.error as details:
            print("Failed: {}".format(details))
            # print(repr(details.__dict__))
            errnum = details.winerror
            if errnum == winerror.ERROR_FAILED_SERVICE_CONTROLLER_CONNECT:
                win32serviceutil.usage()
    elif argc == 2 and sys.argv[1] == 'debug':
        s = cls()
        s.debug()
    else:
        win32serviceutil.HandleCommandLine(cls)


def main():
    # Called as an entry point (see setup.py).
    generic_service_main(CratewebService, 'CratewebService')


if __name__ == '__main__':
    main()
