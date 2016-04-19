#!/usr/bin/env python

"""
Script to run an instance of mysql-proxy

Author: Rudolf Cardinal
Copyright (C) 2015-2016 Rudolf Cardinal.
License: http://www.apache.org/licenses/LICENSE-2.0

The mysql-proxy version must be at least 0.8.5; see
      http://dev.mysql.com/doc/mysql-proxy/en/
and downloads are at
      https://dev.mysql.com/downloads/mysql-proxy/

The tee problem:
    http://stackoverflow.com/questions/616645

General daemon problem:

- UNIX and Windows work differently. In Windows, you run a Windows service;
  under UNIX, you start a daemon. Daemons are processes that dissociate from
  terminals, etc. Services are standalone processes. (It's common to wrap a
  daemon in a service wrapper, e.g. "service mything start" starts a daemon.)

- Daemons/services don't have terminals, so don't have stdout.

- The mysql-proxy tool supports daemonizing itself (e.g. --daemon, --keepalive,
  --pid-file), but if you do this, its output becomes limited; it runs its
  own log (--log-file), but doesn't do anything with its stdout, so the log
  ends up as just, or containing, its own status messages, not our audit log.

- So, let's create a framework that does whatever we want. At its core will be
  a Python function that runs mysql-proxy (ignoring its --daemon option), takes
  its stdout/stderr, and does something useful (like writing to a Python log).

- This function will then be wrapped in a UNIX daemon, with a DaemonRunner
  (undocumented but useful code from the python-daemon library), or wrapped in
  a Windows service.

- The DaemonRunner() code doesn't work on Python 3 because it does things like
    # app.stdout_path = "/dev/tty"
    ... = open(app.stdout_path, 'w+t')  # daemon/runner.py, line 111
  which gives: "io.UnsupportedOperation: File or stream is not seekable."
  ... e.g. https://github.com/stefanholek/term/issues/1
  ... https://bugs.python.org/issue20074
  Anyway, DaemonRunner() is undocumented/unsupported and we have to hack it a
  bit anyway, so let's just rewrite it.



        echo "... appending stdout (audit information) to $OUTLOG"
        if $STDOUT_PLUS_LOG ; then
            echo "... keeping stdout as well"
        fi
        echo "... appending stderr (mysql-proxy log) to $ERRLOG"
        if $STDERR_PLUS_LOG; then
            echo "... keeping stderr as well"
        fi
        # We're not using mysql-proxy's --log-file option; we'll do it by hand.
        # http://stackoverflow.com/questions/692000/how-do-i-write-stderr-to-a-file-while-using-tee-with-a-pipe
        # http://mywiki.wooledge.org/BashGuide/InputAndOutput
        if $STDOUT_PLUS_LOG ; then
            if $STDERR_PLUS_LOG; then
                # tee stdout; tee stderr
                $CMD > >(tee --append $OUTLOG) 2> >(tee --append $ERRLOG >&2)
            else
                # tee stdout; file stderr
                $CMD > >(tee --append $OUTLOG) 2>> $ERRLOG
            fi
        else
            if $STDERR_PLUS_LOG; then
                # file stdout; tee stderr
                $CMD >> $OUTLOG 2> >(tee --append $ERRLOG >&2)
            else
                # file stdout; file stderr
                $CMD >> $OUTLOG 2>> $ERRLOG
            fi
        fi
        chmod -v 600 $OUTLOG
        chmod -v 600 $ERRLOG



"""

import argparse
import errno
import os
import platform
import psutil
import re
import select
import semver
import shlex
import signal
import subprocess
import sys
import time

import lockfile

try:  # UNIX
    import daemon  # pip install python-daemon
    from daemon import pidfile
    from daemon import DaemonContext
except ImportError:
    daemon = None
    pidfile = None
    DaemonContext = None

try:  # Windows
    import win32service
    import win32serviceutil
    import win32api
    import win32con
    import win32event
    import win32evtlogutil
except ImportError:
    win32service = None
    win32serviceutil = None
    win32api = None
    win32con = None
    win32event = None
    win32evtlogutil = None


# =============================================================================
# Constants
# =============================================================================

DATE = time.strftime("%Y_%m_%d")

DEFAULT_AUDIT_LOG = 'mysql_audit_{}.log'.format(DATE)
DEFAULT_ERROR_LOG = 'mysqlproxy_{}.log'.format(DATE)
DEFAULT_LOGDIR = '/var/log/mysql_auditor'
# DEFAULT_MYSQLPROXY = 'mysql-proxy'
DEFAULT_MYSQLPROXY = os.path.expanduser(
    '~/software/mysql-proxy-0.8.5-linux-glibc2.3-x86-64bit/bin/mysql-proxy')
DEFAULT_MYSQLPROXY_LOGLEVEL = 'debug'
DEFAULT_MYSQL_HOST = '127.0.0.1'
DEFAULT_MYSQL_PORT = 3306  # default MySQL port
DEFAULT_PROXY_PORT = 4040  # will be created as the auditing proxy port
# DEFAULT_PID_FILE = '/var/run/mysql_auditor.pid'
DEFAULT_PID_FILE = '/tmp/mysql_auditor.pid'
DEFAULT_START_WAIT_TIME_SEC = 3
DEFAULT_CYCLE_WAIT_TIME_SEC = 3

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
LUA_SCRIPT = os.path.join(THIS_DIR, 'query_auditor_mysqlproxy.lua')

MYSQLPROXY_VERSION_REQ = ">=0.8.5"

# =============================================================================
# OS checks
# =============================================================================

UNIX = os.name == 'posix'
WINDOWS = platform.system() == 'Windows'
if UNIX and not daemon:
    raise AssertionError("Need python-daemon (use: pip install python-daemon")
if not UNIX and not WINDOWS:
    raise AssertionError("Only Unix (POSIX) and Windows supported")


# =============================================================================
# Helper functions
# =============================================================================

def fail(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


def wait(time_sec):
    print("Waiting {} seconds...".format(time_sec))
    time.sleep(time_sec)






# =============================================================================
# DaemonRunner class
# =============================================================================

def _chain_exception_from_existing_exception_context(exc, as_cause=False):
    """ Decorate the specified exception with the existing exception context.

        :param exc: The exception instance to decorate.
        :param as_cause: If true, the existing context is declared to be
            the cause of the exception.
        :return: ``None``.

        :PEP:`344` describes syntax and attributes (`__traceback__`,
        `__context__`, `__cause__`) for use in exception chaining.

        Python 2 does not have that syntax, so this function decorates
        the exception with values from the current exception context.

        """
    (existing_exc_type, existing_exc, existing_traceback) = sys.exc_info()
    if as_cause:
        exc.__cause__ = existing_exc
    else:
        exc.__context__ = existing_exc
    exc.__traceback__ = existing_traceback


class DaemonRunnerError(Exception):
    """ Abstract base class for errors from DaemonRunner. """

    def __init__(self, *args, **kwargs):
        self._chain_from_context()
        super().__init__(*args, **kwargs)

    def _chain_from_context(self):
        _chain_exception_from_existing_exception_context(self, as_cause=True)


class DaemonRunnerInvalidActionError(DaemonRunnerError, ValueError):
    """ Raised when specified action for DaemonRunner is invalid. """

    def _chain_from_context(self):
        # This exception is normally not caused by another.
        _chain_exception_from_existing_exception_context(self, as_cause=False)


class DaemonRunnerStartFailureError(DaemonRunnerError, RuntimeError):
    """ Raised when failure starting DaemonRunner. """


class DaemonRunnerStopFailureError(DaemonRunnerError, RuntimeError):
    """ Raised when failure stopping DaemonRunner. """


class DaemonRunner:
    """ Controller for a callable running in a separate background process.

        The first command-line argument is the action to take:

        * 'start': Become a daemon and call `app.run()`.
        * 'stop': Exit the daemon process specified in the PID file.
        * 'restart': Stop, then start.

        """

    __metaclass__ = type

    start_message = "started with pid {pid:d}"

    def __init__(self, app, action):  # RNC
        """ Set up the parameters of a new runner.

            :param app: The application instance; see below.
            :return: ``None``.

            The `app` argument must have the following attributes:

            * `stdin_path`, `stdout_path`, `stderr_path`: Filesystem paths
              to open and replace the existing `sys.stdin`, `sys.stdout`,
              `sys.stderr`.

            * `pidfile_path`: Absolute filesystem path to a file that will
              be used as the PID file for the daemon. If ``None``, no PID
              file will be used.

            * `pidfile_timeout`: Used as the default acquisition timeout
              value supplied to the runner's PID lock file.

            * `run`: Callable that will be invoked when the daemon is
              started.

            """
        # RNC modification
        self.action = action  # RNC
        if action not in self.action_funcs:  # RNC
            raise ValueError("Bad action: {} (permitted: {})".format(
                action, '|'.join(self.action_funcs.keys())))

        self.app = app
        self.daemon_context = DaemonContext()
        # *** deal with sudo here
        self.daemon_context.stdin = open(app.stdin_path, 'rt')
        console = '/dev/tty'
        # RNC hacks for /dev/tty
        if app.stdout_path == console:
            self.daemon_context.stdout = open(
                app.stdout_path, 'w+b', buffering=0)
        else:
            self.daemon_context.stdout = open(app.stdout_path, 'w+t')
        if app.stderr_path == console:
            self.daemon_context.stderr = open(
                app.stderr_path, 'w+b', buffering=0)
        else:
            self.daemon_context.stderr = open(
                    app.stderr_path, 'w+t', buffering=0)
        self.pidfile = None
        if app.pidfile_path is not None:
            self.pidfile = make_pidlockfile(
                    app.pidfile_path, app.pidfile_timeout)
        self.daemon_context.pidfile = self.pidfile

    def _start(self):
        """ Open the daemon context and run the application.

            :return: ``None``.
            :raises DaemonRunnerStartFailureError: If the PID file cannot
                be locked by this process.

            """
        if is_pidfile_stale(self.pidfile):
            self.pidfile.break_lock()
        try:
            self.daemon_context.open()
        except lockfile.AlreadyLocked:
            error = DaemonRunnerStartFailureError(
                    "PID file {pidfile.path!r} already locked".format(
                        pidfile=self.pidfile))
            raise error

        pid = os.getpid()
        message = self.start_message.format(pid=pid)
        emit_message(message)
        self.app.run()

    def _terminate_daemon_process(self):
        """ Terminate the daemon process specified in the current PID file.

            :return: ``None``.
            :raises DaemonRunnerStopFailureError: If terminating the daemon
                fails with an OS error.

            """
        pid = self.pidfile.read_pid()
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError as exc:
            error = DaemonRunnerStopFailureError(
                    "Failed to terminate {pid:d}: {exc}".format(
                        pid=pid, exc=exc))
            raise error

    def _stop(self):
        """ Exit the daemon process specified in the current PID file.

            :return: ``None``.
            :raises DaemonRunnerStopFailureError: If the PID file is not
                already locked.

            """
        if not self.pidfile.is_locked():
            error = DaemonRunnerStopFailureError(
                    "PID file {pidfile.path!r} not locked".format(
                        pidfile=self.pidfile))
            raise error
        if is_pidfile_stale(self.pidfile):
            self.pidfile.break_lock()
        else:
            self._terminate_daemon_process()

    def _restart(self):
        """ Stop, then start.
            """
        self._stop()
        self._start()

    def _status(self):
        success = False
        if self.pidfile:
            pid = self.pidfile.read_pid()
            if pid is not None:
                success = True
        if success:
            print(
                "Daemon running as process {} "
                "(according to PID file: {})".format(
                    pid, self.app.pidfile_path))
        else:
            print("Daemon not running (based on PID file: {})".format(
                self.app.pidfile_path))

    action_funcs = {
        'start': _start,
        'stop': _stop,
        'restart': _restart,
        'status': _status,
    }

    def _get_action_func(self):
        """ Get the function for the specified action.

            :return: The function object corresponding to the specified
                action.
            :raises DaemonRunnerInvalidActionError: if the action is
               unknown.

            The action is specified by the `action` attribute, which is set
            during `parse_args`.

            """
        try:
            func = self.action_funcs[self.action]
        except KeyError:
            error = DaemonRunnerInvalidActionError(
                    "Unknown action: {action!r}".format(
                        action=self.action))
            raise error
        return func

    def do_action(self):
        """ Perform the requested action.

            :return: ``None``.

            The action is specified by the `action` attribute, which is set
            during `parse_args`.

            """
        func = self._get_action_func()
        func(self)


def emit_message(message, stream=None):
    """ Emit a message to the specified stream (default `sys.stderr`). """
    if stream is None:
        stream = sys.stderr
    stream.write("{message}\n".format(message=message))
    stream.flush()


def make_pidlockfile(path, acquire_timeout):
    """ Make a PIDLockFile instance with the given filesystem path. """
    if not isinstance(path, str):
        error = ValueError("Not a filesystem path: {path!r}".format(
                path=path))
        raise error
    if not os.path.isabs(path):
        error = ValueError("Not an absolute path: {path!r}".format(
                path=path))
        raise error
    lockfile_ = pidfile.TimeoutPIDLockFile(path, acquire_timeout)
    return lockfile_


# noinspection PyShadowingNames
def is_pidfile_stale(pidfile):
    """ Determine whether a PID file is stale.

        :return: ``True`` iff the PID file is stale; otherwise ``False``.

        The PID file is “stale” if its contents are valid but do not
        match the PID of a currently-running process.

        """
    result = False
    pidfile_pid = pidfile.read_pid()
    if pidfile_pid is not None:
        try:
            os.kill(pidfile_pid, signal.SIG_DFL)
        except ProcessLookupError:
            # The specified PID does not exist.
            result = True
        except OSError as exc:
            if exc.errno == errno.ESRCH:
                # Under Python 2, process lookup error is an OSError.
                # The specified PID does not exist.
                result = True
    return result


# =============================================================================
# Daemon application
# =============================================================================

class App:
    def __init__(self, args):
        self.args = args
        self.encoding = 'utf8'
        # ***
        self.stdin_path = '/dev/null'
        self.stdout_path = '/dev/tty'
        self.stderr_path = '/dev/tty'
        self.pidfile_path =  args.pidfile
        self.pidfile_timeout = 5

    def ensure_minimum_mysqlproxy_version(self):
        cmdargs = [self.args.mysqlproxy, '--version']
        ret = subprocess.check_output(cmdargs).decode('utf8')
        # print("ret: {}".format(ret))
        m = re.search(r"^mysql-proxy ([\d\.]+)", ret)
        ok = False
        version = None
        if m:
            version = m.group(1)  # e.g.
            # print("version: {}".format(version))
            ok = semver.match(version, MYSQLPROXY_VERSION_REQ)
        if ok:
            print("Found mysql-proxy {}".format(version))
        else:
            fail(
                "mysql-proxy version must be {}; is {}\n"
                "See https://dev.mysql.com/doc/mysql-proxy/en/\n"
                "    http://downloads.mysql.com/archives/proxy/".format(
                    MYSQLPROXY_VERSION_REQ, version))

    def make_log_dir(self):
        os.makedirs(self.args.logdir, exist_ok=True)

    def get_mysqlproxy_args(self):
        # (['sudo'] if args.sudo else [])
        return [
            self.args.mysqlproxy,
            '--log-level={}'.format(self.args.loglevel),
            '--plugins=proxy',
            '--proxy-address={}:{}'.format(self.args.proxyhost,
                                           self.args.proxyport),
            '--proxy-backend-addresses={}:{}'.format(self.args.mysqlhost,
                                                     self.args.mysqlport),
            '--proxy-lua-script={}'.format(LUA_SCRIPT),
            '--verbose-shutdown',
            # '--log-file={}'.format(os.path.join(args.logdir, args.logfile)),
        ]

    def run(self):
        self.ensure_minimum_mysqlproxy_version()
        self.make_log_dir()
        cmdargs = self.get_mysqlproxy_args()
        print("Executing: {}".format(cmdargs))
        print("Executing: {}".format(
            ' '.join([shlex.quote(s) for s in cmdargs])))
        p = subprocess.Popen(cmdargs, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        # http://stackoverflow.com/questions/12270645/can-you-make-a-python-subprocess-output-stdout-and-stderr-as-usual-but-also-cap  # noqa
        while True:
            reads = [p.stdout.fileno(), p.stderr.fileno()]
            ret = select.select(reads, [], [])
            for fd in ret[0]:
                if fd == p.stdout.fileno():
                    line = p.stdout.readline().decode(self.encoding).rstrip()
                    print("STDOUT: " + line)
                elif fd == p.stderr.fileno():
                    line = p.stderr.readline().decode(self.encoding).rstrip()
                    print("STDERR: " + line)
            if p.poll() != None:
                break
        # program ended


# =============================================================================
# Core
# =============================================================================


def start(args):
    """Start as a daemon."""
    if not args.pidfile:
        fail("Must specify pidfile for daemon mode")
    # In daemon mode, stdout/stderr become impossible/silly.
    # args.stdout = False
    # args.stderr = False

    ensure_minimum_mysqlproxy_version(args)
    make_log_dir(args)
    cmdargs = get_common_mysqlproxy_args(args) + [
        '--daemon',
        '--keepalive',
        '--pid-file={}'.format(args.pidfile),
    ]
    print("Starting auditor as daemon: {}".format(cmdargs))
    subprocess.check_call(cmdargs)
    # mysql-proxy writes the PID file itself
    wait(args.startwait)
    pid = get_pid(args)
    print("Running in daemon mode as process {}".format(pid))


def stop(args):
    """Stop a running daemon."""
    pid = get_pid(args)
    if not pid:
        fail("Can't get process ID to kill daemon")
    print(
        "Stopping auditor on process {pid}... If this fails, kill it "
        "manually (using ps and kill) and remove {pidfile}".format(
            pid=pid, pidfile=args.pidfile))
    # http://stackoverflow.com/questions/17856928/how-to-terminate-process-from-python-using-pid  # noqa
    p = psutil.Process(pid)
    p.terminate()  # or p.kill()
    # or (psutil.NoSuchProcess, psutil.ZombieProcess, psutil.AccessDenied)
    os.remove(args.pidfile)
    print("Stopped.")


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Create a TCP/IP interface to MySQL with an audit "
                    "intermediary, via mysql-proxy. Requires mysql-proxy "
                    "{}.".format(MYSQLPROXY_VERSION_REQ))
    parser.add_argument(
        'command', choices=('run', 'start', 'stop', 'restart', 'status'),
        help="Action to take (run directly, start as daemon, "
             "stop, restart, show daemon status)")
    # -------------------------------------------------------------------------
    # Arguments for our daemon
    # -------------------------------------------------------------------------
    parser.add_argument(
        '--mysqlhost', default=DEFAULT_MYSQL_HOST,
        help="MySQL host to connect to (default: {})".format(
            DEFAULT_MYSQL_HOST))
    parser.add_argument(
        '--mysqlport', type=int, default=DEFAULT_MYSQL_PORT,
        help="MySQL port to connect to (default: {})".format(
            DEFAULT_MYSQL_PORT))
    parser.add_argument(
        '--proxyhost', default='',
        help='IP address of the proxy to create (default is blank, meaning '
             '"this computer regardless of its IP address(es)"')
    parser.add_argument(
        '--proxyport', type=int, default=DEFAULT_PROXY_PORT,
        help="Port number of proxy to create (default: {})".format(
            DEFAULT_PROXY_PORT))
    parser.add_argument(
        '--mysqlproxy', default=DEFAULT_MYSQLPROXY,
        help="Path to mysql-proxy executable (default: {})".format(
            DEFAULT_MYSQLPROXY))
    parser.add_argument(
        '--logdir', default=DEFAULT_LOGDIR,
        help="Log directory (default: {})".format(DEFAULT_LOGDIR))
    parser.add_argument(
        '--logfile', default=DEFAULT_AUDIT_LOG,
        help="Audit log file (default: {})".format(DEFAULT_AUDIT_LOG))
    parser.add_argument(
        '--errorlog', default=DEFAULT_ERROR_LOG,
        help="mysql-proxy error log file, from stderr "
             "(default: {})".format(DEFAULT_ERROR_LOG))
    parser.add_argument(
        '--loglevel', default=DEFAULT_MYSQLPROXY_LOGLEVEL,
        choices=('error', 'warning', 'info', 'message', 'debug'),
        help="Log level for mysql-proxy itself (default: {})".format(
            DEFAULT_MYSQLPROXY_LOGLEVEL))
    # -------------------------------------------------------------------------
    # Extra arguments for a UNIX daemon; see DaemonRunner
    # -------------------------------------------------------------------------
    parser.add_argument(
        '--pidfile', default=DEFAULT_PID_FILE,
        help="(UNIX) Process ID (PID) file to be used for daemon mode "
             "(default: {})".format(DEFAULT_PID_FILE))
    parser.add_argument(
        '--sudo', action='store_true',
        help="(UNIX) Use sudo to run as root")
    # -------------------------------------------------------------------------
    # Extra arguments for a Windows service
    # -------------------------------------------------------------------------

    args = parser.parse_args()
    if args.command == 'run':
        app = App(args)
        app.run()
    elif UNIX and args.command in ['start', 'stop', 'restart', 'status']:
        app = App(args)
        daemon_runner = DaemonRunner(app, action=args.command)
        daemon_runner.do_action()
    elif WINDOWS and args.command in ['start', 'stop', 'restart']:
        pass
    elif WINDOWS and args.command == 'status':
        pass
    else:
        raise AssertionError("Bug; condition not covered")


# =============================================================================
# Command-line entry point
# =============================================================================

if __name__ == '__main__':
    main()
