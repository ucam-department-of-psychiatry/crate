#!/usr/bin/env python
# crate_anon/common/fileops.py

import fnmatch
import glob
import logging
import os
import shutil
from typing import List

log = logging.getLogger(__name__)


def mkdirp(path: str) -> None:
    print("mkdir_p: " + path)
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
