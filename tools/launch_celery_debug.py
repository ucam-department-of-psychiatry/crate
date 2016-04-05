#!/usr/bin/env python

import os
import subprocess

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
DJANGO_ROOT = os.path.abspath(os.path.join(THIS_DIR, os.pardir,
                                           "crate", "crateweb"))


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
            module = prefix + relfile_no_ext.replace('/', '.')
            modules.append(module)
    return modules


def main():
    modules = get_python_modules(DJANGO_ROOT, prefix="crate.crateweb.")
    # print("Changing to directory: {}".format(DJANGO_ROOT))
    # os.chdir(DJANGO_ROOT)
    cmdargs = [
        "celery", "worker",
        "--app=crate.crateweb.consent",
        "--loglevel=debug",
        # "--autoreload",
        "--include={}".format(','.join(modules)),
    ]
    print(cmdargs)
    subprocess.call(cmdargs)


if __name__ == '__main__':
    main()
