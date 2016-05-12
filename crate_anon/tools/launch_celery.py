#!/usr/bin/env python

import argparse
import os
import platform
import subprocess

from crate_anon.crateweb.config.constants import CELERY_APP_NAME


THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DJANGO_ROOT = os.path.abspath(os.path.join(THIS_DIR, os.pardir, "crateweb"))
WINDOWS = platform.system() == 'Windows'


# http://stackoverflow.com/questions/21666229/celery-auto-reload-on-any-changes
# HOWEVER: autoreload appears (a) not to work, and (b) to prevent processing!


# def get_python_modules(rootdir, prefix=''):
#     # Find Python files within the relevant root, and convert their filenames
#     # to relative module names.
#     # NOT NEEDED WITH A PROPERLY CONFIGURED, pip-INSTALLED, PACKAGE.
#     # AND MAKES THINGS GO WRONG UNDER WINDOWS.
#     modules = []
#     for root, _, files in os.walk(rootdir):
#         if root.endswith(os.sep + "specimen_secret_local_settings"):
#             # importing the demo secret settings will raise an exception
#             continue
#         for filename in files:
#             basename, ext = os.path.splitext(filename)
#             if ext != ".py":
#                 continue
#             reldir = os.path.relpath(root, DJANGO_ROOT)
#             if reldir == ".":  # special for Python modules
#                 relfile_no_ext = basename
#             else:
#                 relfile_no_ext = os.path.join(reldir, basename)
#             module = prefix + relfile_no_ext.replace(os.sep, '.')
#             modules.append(module)
#     return modules


def main():
    parser = argparse.ArgumentParser(
        description="Launch CRATE Celery processes. (Any leftover arguments "
                    "will be passed to Celery.)")
    parser.add_argument("--command", default="worker",
                        help="Celery command (default: worker)")
    parser.add_argument("--debug", action="store_true",
                        help="Ask Celery to be verbose")
    args, leftovers = parser.parse_known_args()
    
    # print("Changing to directory: {}".format(DJANGO_ROOT))
    # os.chdir(DJANGO_ROOT)
    cmdargs = [
        "celery",
        args.command,
        "-A", CELERY_APP_NAME,
    ]
    if args.command == "worker":
        cmdargs += ["-l", "debug" if args.debug else "info"]  # --loglevel
        if WINDOWS:
            # Default concurrency is 1. Under Celery 3.1.23, RabbitMQ 3.6.1,
            # and Windows 10, things like "celery -A myapp status" don't work
            # unless the concurrency flag is increased, e.g. to 4.
            # (Default is 1 under Windows.)
            cmdargs += ["--concurrency=4"]
            
            # Without "--pool=solo", sod all happens: tasks go into the
            # Reserved queue, but aren't executed.
            # See:
            # http://docs.celeryproject.org/en/latest/reference/celery.bin.worker.html#module-celery.bin.worker  # noqa
            # https://github.com/celery/celery/issues/2146
            cmdargs += ["--pool=solo"]

            # The "-Ofair" option is relevant to pre-fetching, but doesn't
            # seem critical.
            # cmdargs += ["-Ofair"]

        # We don't need to specify modules manually, now we have a package.
        # modules = get_python_modules(DJANGO_ROOT,
        #                              prefix="crate_anon.crateweb.")
        # cmdargs += ["--include", "{}".format(','.join(modules))]

        # "--autoreload",
    cmdargs += leftovers
    print("Launching Celery: {}".format(cmdargs))
    subprocess.call(cmdargs)


if __name__ == '__main__':
    main()
