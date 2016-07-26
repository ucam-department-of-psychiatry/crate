#!/usr/bin/env python

import os
from os.path import abspath, dirname, join, splitext
import shutil
import subprocess

CURRENT_DIR = dirname(abspath(__file__))
PROJECT_BASE_DIR = abspath(join(CURRENT_DIR, os.pardir))

FLAKE8 = shutil.which('flake8')
if not FLAKE8:
    raise AssertionError("Need flake8")

# http://stackoverflow.com/questions/19859840/excluding-directories-in-os-walk
exclude = ["migrations"]
for root, dirs, files in os.walk(PROJECT_BASE_DIR, topdown=True):
    dirs[:] = [d for d in dirs if d not in exclude]
    for f in files:
        filename, ext = splitext(f)
        if ext == '.py':
            filepath = join(root, f)
            subprocess.call([FLAKE8, "--ignore=T003", filepath])
