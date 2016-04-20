#!/usr/bin/env python3
# manage.py

# import logging
import os
import sys

# http://stackoverflow.com/questions/2636536/how-to-make-django-work-with-unsupported-mysql-drivers-such-as-gevent-mysql-or-c  # noqa
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass

import django
from django.core.management import execute_from_command_line


os.environ.setdefault("DJANGO_SETTINGS_MODULE",
                      "crate_anon.crateweb.config.settings")

# from crate_anon.crateweb.config.settings import MIDDLEWARE_CLASSES
# print("1. MIDDLEWARE_CLASSES: {}".format(id(MIDDLEWARE_CLASSES)))
# print("1. MIDDLEWARE_CLASSES: {}".format(MIDDLEWARE_CLASSES))
django.setup()
# from crate_anon.crateweb.config.settings import MIDDLEWARE_CLASSES
# print("2. MIDDLEWARE_CLASSES: {}".format(id(MIDDLEWARE_CLASSES)))
# print("2. MIDDLEWARE_CLASSES: {}".format(MIDDLEWARE_CLASSES))

# print("sys.path: {}".format(sys.path))
# print("os.environ['DJANGO_SETTINGS_MODULE']: {}".format(
#     os.environ['DJANGO_SETTINGS_MODULE']))
# print("os.environ['CRATE_LOCAL_SETTINGS']: {}".format(
#     os.environ['CRATE_LOCAL_SETTINGS']))


def main(argv=None):
    if argv is None:
        argv = sys.argv
    # print(argv)
    execute_from_command_line(argv)


def runserver():
    argv = sys.argv[:]  # copy
    argv.insert(1, 'runserver')
    main(argv)


def runcpserver():
    argv = sys.argv[:]  # copy
    argv.insert(1, 'runcpserver')
    main(argv)


if __name__ == "__main__":
    main()
