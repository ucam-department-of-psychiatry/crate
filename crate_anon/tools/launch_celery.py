#!/usr/bin/env python

import argparse
import os
import subprocess

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DJANGO_ROOT = os.path.abspath(os.path.join(THIS_DIR, os.pardir, "crateweb"))


# http://stackoverflow.com/questions/21666229/celery-auto-reload-on-any-changes
# HOWEVER: autoreload appears (a) not to work, and (b) to prevent processing!


def get_python_modules(rootdir, prefix=''):
    # Find Python files within the relevant root, and convert their filenames
    # to relative module names.
    modules = []
    for root, _, files in os.walk(rootdir):
        if root.endswith(os.sep + "specimen_secret_local_settings"):
            # importing the demo secret local settings will raise an exception
            continue
        for filename in files:
            basename, ext = os.path.splitext(filename)
            if ext != ".py":
                continue
            reldir = os.path.relpath(root, DJANGO_ROOT)
            if reldir == ".":  # special for Python modules
                relfile_no_ext = basename
            else:
                relfile_no_ext = os.path.join(reldir, basename)
            module = prefix + relfile_no_ext.replace(os.sep, '.')
            modules.append(module)
    return modules


def main():
    parser = argparse.ArgumentParser(
        description="Launch CRATE Celery processes")
    parser.add_argument("--debug", action="store_true",
                        help="Ask Celery to be verbose")
    args = parser.parse_args()

    modules = get_python_modules(DJANGO_ROOT, prefix="crate_anon.crateweb.")
    # print("Changing to directory: {}".format(DJANGO_ROOT))
    # os.chdir(DJANGO_ROOT)
    cmdargs = [
        "celery", "worker",
        "--app", "crate_anon.crateweb.consent",
        "--loglevel", "debug" if args.debug else "info",
        # "--autoreload",
        "--include", "{}".format(','.join(modules)),
    ]
    print("Launching Celery: {}".format(cmdargs))
    subprocess.call(cmdargs)


if __name__ == '__main__':
    main()
