#!/usr/bin/env python3
# manage.py

# import logging
import os
import sys
from django.core.management import call_command, execute_from_command_line


def common():
    if "CRATE_LOCAL_SETTINGS" not in os.environ:
        print("""
You must set the CRATE_LOCAL_SETTINGS environment variable first.
Aim it at your settings file, like this:

    export CRATE_LOCAL_SETTINGS=/etc/crate/my_secret_crate_settings.py
        """)
        sys.exit(1)

    os.environ.setdefault("DJANGO_SETTINGS_MODULE",
                          "crate.crateweb.config.settings")

    # print("sys.path: {}".format(sys.path))
    # print("os.environ['DJANGO_SETTINGS_MODULE']: {}".format(
    #     os.environ['DJANGO_SETTINGS_MODULE']))
    # print("os.environ['CRATE_LOCAL_SETTINGS']: {}".format(
    #     os.environ['CRATE_LOCAL_SETTINGS']))


def main():
    common()
    execute_from_command_line(sys.argv)


def runserver():
    # logging.basicConfig()
    common()
    call_command('runserver')


if __name__ == "__main__":
    main()
