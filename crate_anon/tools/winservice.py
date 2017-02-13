#!/usr/bin/env python
# crate_anon/tools/winservice.py

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

import atexit
import ctypes
import os
import logging
import platform
import subprocess
import sys
import traceback
from typing import Any, List, TextIO

try:
    from subprocess import CREATE_NEW_PROCESS_GROUP
    from signal import CTRL_C_EVENT
    from signal import CTRL_BREAK_EVENT
except ImportError:
    CREATE_NEW_PROCESS_GROUP = None
    CTRL_C_EVENT = 0  # wincon.h
    CTRL_BREAK_EVENT = 1  # wincon.h

import arrow
import servicemanager  # part of pypiwin32
import winerror  # part of pypiwin32
import win32event  # part of pypiwin32
import win32service  # part of pypiwin32
import win32serviceutil  # part of pypiwin32

log = logging.getLogger(__name__)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ENVVAR = 'CRATE_WINSERVICE_LOGDIR'
TEST_FILENAME = r'C:\test_win_svc.txt'
TEST_PERIOD_MS = 5000
WINDOWS = platform.system() == 'Windows'


# =============================================================================
# Subprocess management
# =============================================================================

class ProcessDetails(object):
    def __init__(self,
                 name: str,
                 procargs: List[str],
                 logfile_out: str = '',
                 logfile_err: str = '') -> None:
        self.name = name
        self.procargs = procargs
        self.logfile_out = logfile_out
        self.logfile_err = logfile_err


class ProcessManager(object):
    KILL_LEVEL_CTRL_C_OR_SOFT_KILL = 0
    KILL_LEVEL_CTRL_BREAK = 1
    KILL_LEVEL_TASKKILL = 2
    KILL_LEVEL_TASKKILL_FORCE = 3
    KILL_LEVEL_HARD_KILL = 4
    ALL_KILL_LEVELS = [
        KILL_LEVEL_CTRL_C_OR_SOFT_KILL,
        KILL_LEVEL_CTRL_BREAK,
        KILL_LEVEL_TASKKILL,
        KILL_LEVEL_TASKKILL_FORCE,
        KILL_LEVEL_HARD_KILL,
    ]

    def __init__(self,
                 details: ProcessDetails,
                 procnum: int,
                 nprocs: int,
                 kill_timeout_sec: float = 5,
                 debugging: bool = False):
        self.details = details
        self.procnum = procnum
        self.nprocs = nprocs
        self.kill_timeout_sec = kill_timeout_sec
        self.process = None  # type: subprocess.Popen
        self.running = False
        self.stdout = None  # type: TextIO
        self.stderr = None  # type: TextIO
        self.debugging = debugging

    @property
    def fullname(self) -> str:
        fullname = "Process {}/{} ({})".format(self.procnum, self.nprocs,
                                               self.details.name)
        if self.running:
            fullname += " (PID={})".format(self.process.pid)
        return fullname

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------

    def debug(self, msg: str) -> None:
        if self.debugging:
            s = "{}: {}".format(self.fullname, msg)
            log.debug(s)

    def info(self, msg: str) -> None:
        # Log messages go to the Windows APPLICATION log.
        # noinspection PyUnresolvedReferences
        s = "{}: {}".format(self.fullname, msg)
        servicemanager.LogInfoMsg(s)
        if self.debugging:
            log.info(s)

    def warning(self, msg: str) -> None:
        # Log messages go to the Windows APPLICATION log.
        # noinspection PyUnresolvedReferences
        s = "{}: {}".format(self.fullname, msg)
        servicemanager.LogWarningMsg(s)
        if self.debugging:
            log.warning(s)

    def error(self, msg: str) -> None:
        # Log messages go to the Windows APPLICATION log.
        # noinspection PyUnresolvedReferences
        s = "{}: {}".format(self.fullname, msg)
        servicemanager.LogErrorMsg(s)
        if self.debugging:
            log.warning(s)

    def open_logs(self) -> None:
        if self.details.logfile_out:
            self.stdout = open(self.details.logfile_out, 'a')
        else:
            self.stdout = None
        if self.details.logfile_err:
            if self.details.logfile_err == self.details.logfile_out:
                self.stderr = subprocess.STDOUT
            else:
                self.stderr = open(self.details.logfile_err, 'a')
        else:
            self.stderr = None

    def close_logs(self) -> None:
        if self.stdout is not None:
            self.stdout.close()
            self.stdout = None
        if self.stderr is not None and self.stderr != subprocess.STDOUT:
            self.stderr.close()
            self.stderr = None

    # -------------------------------------------------------------------------
    # Starting, stopping
    # -------------------------------------------------------------------------

    def start(self) -> None:
        """
        Starts a subprocess.
        """
        if self.running:
            return
        self.info("Starting: {} (with logs stdout={}, stderr={})".format(
            self.details.procargs,
            self.details.logfile_out,
            self.details.logfile_err))
        self.open_logs()
        creationflags = CREATE_NEW_PROCESS_GROUP if WINDOWS else 0
        # self.warning("creationflags: {}".format(creationflags))
        self.process = subprocess.Popen(self.details.procargs, stdin=None,
                                        stdout=self.stdout, stderr=self.stderr,
                                        creationflags=creationflags)
        self.running = True

    def stop(self) -> None:
        """
        Stops a subprocess.
        Asks nicely. Waits. Asks less nicely. Repeat until subprocess is dead.
        """
        if not self.running:
            return
        try:
            self.wait(timeout_s=0)
            # If we get here: stopped already
        except subprocess.TimeoutExpired:  # still running
            for kill_level in self.ALL_KILL_LEVELS:
                tried_to_kill = self._terminate(level=kill_level)  # please stop
                if tried_to_kill:
                    try:
                        self.wait(timeout_s=self.kill_timeout_sec)
                        break
                    except subprocess.TimeoutExpired:  # failed to close
                        self.warning("Subprocess didn't stop when asked")
                        pass  # carry on escalating
        self.close_logs()
        self.running = False

    def _terminate(self, level: int) -> bool:
        """Returns: succeeded in *attempting* a kill?"""
        if not self.running:
            return True

        # Already closed by itself?
        try:
            self.wait(0)
            return True
        except subprocess.TimeoutExpired:  # failed to close
            pass

        # SEE NOTES ABOVE. This is tricky under Windows.

        suffix = " [to child process {}]".format(self.process.pid)
        if level == self.KILL_LEVEL_CTRL_C_OR_SOFT_KILL:
            if WINDOWS:
                success = 0 != ctypes.windll.kernel32.GenerateConsoleCtrlEvent(
                    CTRL_C_EVENT, self.process.pid)
                if success:
                    self.info("Sent CTRL-C to request stop" + suffix)
                    # ... but that doesn't mean it'll stop...
                else:
                    self.info("Failed to send CTRL-C" + suffix)
                return success
            else:
                self.warning("Asking process to stop (SIGTERM)" + suffix)
                self.process.terminate()  # soft kill under POSIX
                return True

        elif level == self.KILL_LEVEL_CTRL_BREAK:
            if not WINDOWS:
                return False
            success = 0 != ctypes.windll.kernel32.GenerateConsoleCtrlEvent(
                CTRL_BREAK_EVENT, self.process.pid)
            if success:
                self.info("Sent CTRL-BREAK to request stop" + suffix)
            else:
                self.info("Failed to send CTRL-BREAK" + suffix)
            return success

        elif level == self.KILL_LEVEL_TASKKILL:
            if not WINDOWS:
                return False
            retcode = self._taskkill(force=False)  # does its own info messages
            return retcode == winerror.ERROR_SUCCESS

        elif level == self.KILL_LEVEL_TASKKILL_FORCE:
            if not WINDOWS:
                return False
            retcode = self._taskkill(force=True)  # does its own info messages
            return retcode == winerror.ERROR_SUCCESS

        elif level == self.KILL_LEVEL_HARD_KILL:
            # Last resort
            self._kill()  # may do TASKKILL /F or some other method
            return True

        else:
            raise ValueError("Bad kill level requested")

    def _taskkill(self, force: bool = False) -> int:
        args = [
            "taskkill",  # built in to Windows XP and higher
            "/pid", str(self.process.pid),
            "/t",  # tree kill: kill all children
        ]
        if force:
            args.append("/f")  # forcefully
        callname = " ".join(args)
        retcode = subprocess.call(args)
        # http://stackoverflow.com/questions/18682681/what-are-exit-codes-from-the-taskkill-utility  # noqa
        if retcode == winerror.ERROR_SUCCESS:  # 0
            # You also get errorlevel 0 (try: echo %ERRORLEVEL%) if a forceful
            # kill is required but you didn't specify it. So we always specify
            # a forceful kill, as above.
            self.info("Killed with " + repr(callname))
        elif retcode == winerror.ERROR_WAIT_NO_CHILDREN:  # 128
            self.warning(
                repr(callname) +
                " failed (error code 128 = ERROR_WAIT_NO_CHILDREN "
                "= 'There are no child processes to wait for', but also "
                "occurs when the process doesn't exist, and when processes "
                "require a forceful [/F] termination)")
        else:
            self.warning(callname + " failed: error code {}".format(retcode))
        return retcode

    def _kill(self) -> None:
        """Hard kill."""
        msg = "Using a hard kill; will assume it worked"
        if WINDOWS:
            msg += "; may leave orphans"
        self.warning(msg)
        self.process.kill()  # hard kill, Windows or POSIX
        # ... but will leave orphans under Windows

    def wait(self, timeout_s: float = None) -> None:
        """Will raise subprocess.TimeoutExpired if the process continues to
        run."""
        if not self.running:
            return
        retcode = self.process.wait(timeout=timeout_s)
        # We won't get further unless the process has stopped.
        if retcode > 0:
            self.error(
                "Subprocess finished, but FAILED (return code {}). "
                "Logs were: {} (stdout), {} (stderr)".format(
                    retcode,
                    self.details.logfile_out,
                    self.details.logfile_err))
        else:
            self.info("Subprocess finished cleanly (return code 0).")
        self.running = False


# =============================================================================
# Windows service framework
# =============================================================================

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

    def __init__(self, args: List[Any] = None) -> None:
        if args is not None:
            super().__init__(args)
        # create an event to listen for stop requests on
        self.h_stop_event = win32event.CreateEvent(None, 0, 0, None)
        self.process_managers = []
        self.debugging = False
        
    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------

    def debug(self, msg: str) -> None:
        if self.debugging:
            log.debug(msg)    

    def info(self, msg: str) -> None:
        # Log messages go to the Windows APPLICATION log.
        # noinspection PyUnresolvedReferences
        servicemanager.LogInfoMsg(str(msg))
        if self.debugging:
            log.info(msg)

    def error(self, msg: str) -> None:
        # Log messages go to the Windows APPLICATION log.
        # noinspection PyUnresolvedReferences
        servicemanager.LogErrorMsg(str(msg))
        if self.debugging:
            log.error(msg)

    # -------------------------------------------------------------------------
    # Windows service calls
    # -------------------------------------------------------------------------

    # called when we're being shut down
    # noinspection PyPep8Naming
    def SvcStop(self) -> None:
        # tell the SCM we're shutting down
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        # fire the stop event
        win32event.SetEvent(self.h_stop_event)
        
    # called when service is started
    # noinspection PyPep8Naming
    def SvcDoRun(self) -> None:
        # No need to self.ReportServiceStatus(win32service.SERVICE_RUNNING);
        # that is done by the framework (see win32serviceutil.py).
        # Similarly, no need to report a SERVICE_STOP_PENDING on exit.
        # noinspection PyUnresolvedReferences
        self.debug("Sending PYS_SERVICE_STARTED message")
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ''))
        # self.test_service()  # test service
        self.main()  # real service

    # -------------------------------------------------------------------------
    # Testing
    # -------------------------------------------------------------------------

    def test_service(self,
                     filename: str = TEST_FILENAME,
                     period_ms: int = TEST_PERIOD_MS):
        # A test service. This works! (As long as you can write to the file.)
        def write(msg):
            f.write('{}: {}\n'.format(arrow.now(), msg))
            f.flush()

        self.info("Starting test service; writing data periodically to "
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
        self.info("Test service FINISHED.")

    def run_debug(self) -> None:
        self.debugging = True
        self.main()

    # -------------------------------------------------------------------------
    # Main service
    # -------------------------------------------------------------------------

    def main(self) -> None:
        # Actual main service code.
        try:
            self.service()
        except Exception as e:
            self.error("Unexpected exception: {e}\n{t}".format(
                e=e, t=traceback.format_exc()))

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

    def run_processes(self,
                      procdetails: List[ProcessDetails],
                      subproc_run_timeout_sec: float = 1,
                      stop_event_timeout_ms: int = 1000,
                      kill_timeout_sec: float = 5) -> None:
        """
        Run multiple child processes.
        Args:
            procdetails: list of dictionaries: {
                'name': name (str),
                'procargs': list of command arguments, passed to Popen,
                'logfile_out': log file name for stdout,
                'logfile_err': log file name for stderr,
            }
            subproc_run_timeout_sec:
            stop_event_timeout_ms:
            kill_timeout_sec:

        Returns:
            None
        """
        # NOT YET IMPLEMENTED: Windows service autorestart

        # https://stackoverflow.com/questions/16333054
        def cleanup():
            self.debug("atexit function called: cleaning up")
            for pmgr_ in self.process_managers:
                pmgr_.stop()

        atexit.register(cleanup)
            
        # Set up process info
        self.process_managers = []
        n = len(procdetails)
        for i, details in enumerate(procdetails):
            pmgr = ProcessManager(details, i + 1, n,
                                  kill_timeout_sec=kill_timeout_sec,
                                  debugging=self.debugging)
            self.process_managers.append(pmgr)
            
        # Start processes
        for pmgr in self.process_managers:
            pmgr.start()
        self.info("All started")

        # Run processes
        something_running = True
        stop_requested = False
        subproc_failed = False
        while something_running and not stop_requested and not subproc_failed:
            if (win32event.WaitForSingleObject(
                    self.h_stop_event,
                    stop_event_timeout_ms) == win32event.WAIT_OBJECT_0):
                stop_requested = True
                self.info("Stop requested; stopping")
            else:
                something_running = False
                for pmgr in self.process_managers:
                    if subproc_failed:
                        break
                    try:
                        retcode = pmgr.wait(timeout_s=subproc_run_timeout_sec)
                        if retcode > 0:
                            subproc_failed = True
                    except subprocess.TimeoutExpired:
                        something_running = True

        # Kill any outstanding processes
        #
        # (a) Slow way
        # for pmgr in self.process_managers:
        #     pmgr.stop()
        #
        # (b) Faster (slightly more parallel) way
        # for pmgr in self.process_managers:
        #     pmgr.terminate()
        # for pmgr in self.process_managers:
        #     pmgr.stop_having_terminated()
        #
        # ... No, it's bad if we leave things orphaned.
        # Let's go for slow, clean code.

        for pmgr in self.process_managers:
            pmgr.stop()
        self.info("All stopped")


# =============================================================================
# Main
# =============================================================================

def generic_service_main(cls, name: str) -> None:
    # https://mail.python.org/pipermail/python-win32/2008-April/007299.html
    argc = len(sys.argv)
    if argc == 1:
        try:
            print("Trying to start service directly...")
            evtsrc_dll = os.path.abspath(servicemanager.__file__)
            # noinspection PyUnresolvedReferences
            servicemanager.PrepareToHostSingle(cls)
            # noinspection PyUnresolvedReferences
            servicemanager.Initialize(name, evtsrc_dll)
            # noinspection PyUnresolvedReferences
            servicemanager.StartServiceCtrlDispatcher()
        except win32service.error as details:
            print("Failed: {}".format(details))
            # print(repr(details.__dict__))
            errnum = details.winerror
            if errnum == winerror.ERROR_FAILED_SERVICE_CONTROLLER_CONNECT:
                win32serviceutil.usage()
    elif argc == 2 and sys.argv[1] == 'debug':
        s = cls()
        s.run_debug()
    else:
        win32serviceutil.HandleCommandLine(cls)


def main():
    # Called as an entry point (see setup.py).
    logging.basicConfig(level=logging.DEBUG)
    generic_service_main(CratewebService, 'CratewebService')


if __name__ == '__main__':
    main()
