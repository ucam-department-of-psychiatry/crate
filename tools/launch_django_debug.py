#!/usr/bin/env python

import os
import subprocess
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CRATE_BASE_DIR = os.path.abspath(os.path.join(THIS_DIR, os.pardir, "crate"))
CRATE_WEB_DIR = os.path.join(CRATE_BASE_DIR, "crateweb")
DJANGO_SCRIPT = os.path.join(CRATE_WEB_DIR, "manage.py")

if "CRATE_LOCAL_SETTINGS" not in os.environ:
    print("""
You must set the CRATE_LOCAL_SETTINGS environment variable first.
Aim it at your settings file, like this:

    export CRATE_LOCAL_SETTINGS=/etc/crate/my_secret_crate_settings.py
    """)
    sys.exit(1)

print("""
If the next bit fails, check that you have activated your Python virtual
environment with
    source /PATH/TO/MY/VENV/bin/activate
""")

def main():
    subprocess.call([DJANGO_SCRIPT, 'runserver'])

if __name__ == '__main__':
    main()
