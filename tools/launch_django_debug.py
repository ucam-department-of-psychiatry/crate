#!/usr/bin/env python3

import os
import subprocess
import sys

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
CRATE_BASE_DIR = os.path.abspath(os.path.join(THIS_DIR, os.pardir))
CRATE_WEB_DIR = os.path.join(CRATE_BASE_DIR, "crateweb")
DJANGO_SCRIPT = os.path.join(CRATE_WEB_DIR, "manage.py")

if "CRATE_LOCAL_SETTINGS" not in os.environ:
    print("""
You must set the CRATE_LOCAL_SETTINGS environment variable first.
Aim it at your settings file, like this:

    export CRATE_LOCAL_SETTINGS=/etc/crate/my_secret_crate_settings.py
    """)
    sys.exit(1)

try:
    subprocess.check_call([DJANGO_SCRIPT, 'runserver'])
except:
    print("""

Something went wrong. Check that you have activated your Python virtual
environment with
    source /PATH/TO/MY/VENV/bin/activate

    """)
    raise
