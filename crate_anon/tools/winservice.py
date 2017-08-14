#!/usr/bin/env python
# crate_anon/tools/winservice.py

r"""
===============================================================================
    Copyright (C) 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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

Problems killing things
===============================================================================

We had this:

    def terminate(self):
        if not self.running:
            return
        if WINDOWS:
            # Under Windows, terminate() is an alias for kill(), which is
            # the hard kill. This is the soft kill:
            # https://docs.python.org/3.4/library/subprocess.html

            # SOMETHING GOES SERIOUSLY AWRY HERE.
            # - Tracebacks are from a slightly irrelevant place.
            # - Not all instances of OSError are caught.
            # - Running two processes, you get messages like:
            #       * process 1/2: sending CTRL-C
            #       * process 2/2: failed to send CTRL-C...
            #   without the other expected pair of messages.
            # DOES THIS MEAN A BUG IN SUBPROCESS?
            # Not sure. Removed "send_signal" code.

            # try:
            #     # Ctrl-C is generally "softer" than Ctrl-Break.
            #     # Specifically: CherryPy prints exiting message upon Ctrl-C
            #     # and just stops on Ctrl-Break.
            #     self.warning("Asking process to stop (sending CTRL-C)")
            #     self.process.send_signal(CTRL_C_EVENT)
            #     # self.warning("Asking process to stop (sending CTRL-BREAK)")
            #     # self.process.send_signal(CTRL_BREAK_EVENT)
            # except OSError:
            #     # In practice: "OSError: [WinError 6] The handle is invalid"
            #     self.warning("Failed to send CTRL-C; using hard kill")
            #     self.process.terminate()  # hard kill under Windows

            self.warning("Can't terminate nicely; using hard kill")
            self.process.terminate()  # hard kill under Windows

            # The PROBLEM is that Celery processes live on.
        else:
            self.warning("Asking process to stop (SIGTERM)")
            self.process.terminate()  # soft kill under POSIX

However, the CTRL-C/CTRL-BREAK method failed, and a hard kill left Celery
stuff running (because it killed the root, not child, processes, I presume).
Looked at django-windows-tools,
    https://pypi.python.org/pypi/django-windows-tools
    https://github.com/antoinemartin/django-windows-tools
but it crashed in a print statement -- Python 2 only at present (2016-05-11,
version 0.1.1). However, its process management is instructive; it uses
"multiprocessing", not "subprocess". The multiprocessing module calls Python
functions. And its docs explicitly note that terminate() leaves descendant
processes orphaned.

See in particular
    http://stackoverflow.com/questions/7085604/sending-c-to-python-subprocess-objects-on-windows
    http://stackoverflow.com/questions/140111/sending-an-arbitrary-signal-in-windows

Python bug?
    http://bugs.python.org/issue3905
    http://bugs.python.org/issue13368

Maybe a subprocess bug. Better luck with
    ctypes.windll.kernel32.GenerateConsoleCtrlEvent

Current method tries a variety of things under Windows:
    CTRL-C -> CTRL-BREAK -> TASKKILL /T -> TASKKILL /T /F -> kill()
... which are progressively less graceful in terms of child processes getting
to clean up. Still, it works (usually at one of the two TASKKILL stages).

"The specified service is marked for deletion"
===============================================================================
http://stackoverflow.com/questions/20561990

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

    # -------------------------------------------------------------------------
    # The service
    # -------------------------------------------------------------------------

    def service(self) -> None:
        # Read from environment
        # self.info(repr(os.environ))
        try:
            logdir = os.environ[ENVVAR]
        except KeyError:
            raise ValueError(
                "Must specify {} system environment variable".format(ENVVAR))

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
    # Called as an entry point (see setup.py).
    logging.basicConfig(level=logging.DEBUG)
    generic_service_main(CratewebService, 'CratewebService')


if __name__ == '__main__':
    main()
