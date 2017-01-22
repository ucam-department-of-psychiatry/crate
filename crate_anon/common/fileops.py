#!/usr/bin/env python
# crate_anon/common/fileops.py

"""
===============================================================================
    Copyright (C) 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

    This file is part of CRATE.

    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.
===============================================================================
"""

import fnmatch
import glob
import logging
import os
import shutil
from typing import List

log = logging.getLogger(__name__)


def mkdir_p(path: str) -> None:
    log.debug("mkdir_p: " + path)
    os.makedirs(path, exist_ok=True)


def copyglob(src: str, dest: str, allow_nothing: bool = False) -> None:
    something = False
    for filename in glob.glob(src):
        shutil.copy(filename, dest)
        something = True
    if something or allow_nothing:
        return
    raise ValueError("No files found matching: {}".format(src))


def copytree(src_dir: str, dest_parent: str) -> None:
    dirname = os.path.basename(os.path.normpath(src_dir))
    dest_dir = os.path.join(dest_parent, dirname)
    shutil.copytree(src_dir, dest_dir)


def chown_r(path: str, user: str, group: str) -> None:
    # http://stackoverflow.com/questions/2853723
    for root, dirs, files in os.walk(path):
        for x in dirs:
            shutil.chown(os.path.join(root, x), user, group)
        for x in files:
            shutil.chown(os.path.join(root, x), user, group)


def get_lines_without_comments(filename: str) -> List[str]:
    lines = []
    with open(filename) as f:
        for line in f:
            line = line.partition('#')[0]
            line = line.rstrip()
            line = line.lstrip()
            if line:
                lines.append(line)
    return lines


def moveglob(src: str, dest: str, allow_nothing: bool = False) -> None:
    something = False
    for filename in glob.glob(src):
        shutil.move(filename, dest)
        something = True
    if something or allow_nothing:
        return
    raise ValueError("No files found matching: {}".format(src))


def rmglob(pattern: str) -> None:
    for f in glob.glob(pattern):
        os.remove(f)


def purge(path: str, pattern: str) -> None:
    for f in find(pattern, path):
        log.info("Deleting {}".format(f))
        os.remove(f)


def find(pattern: str, path: str) -> List[str]:
    result = []
    for root, dirs, files in os.walk(path):
        for name in files:
            if fnmatch.fnmatch(name, pattern):
                result.append(os.path.join(root, name))
    return result


def find_first(pattern, path):
    try:
        return find(pattern, path)[0]
    except IndexError:
        log.critical('''Couldn't find "{}" in "{}"'''.format(pattern, path))
        raise
