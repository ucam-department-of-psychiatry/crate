#!/usr/bin/env python
# crate_anon/common/fileops.py

import glob
import os
import shutil


def mkdirp(path):
    print("mkdir_p: " + path)
    os.makedirs(path, exist_ok=True)


def copyglob(src, dest, allow_nothing=False):
    something = False
    for filename in glob.glob(src):
        shutil.copy(filename, dest)
        something = True
    if something or allow_nothing:
        return
    raise ValueError("No files found matching: {}".format(src))


def copytree(src_dir, dest_parent):
    dirname = os.path.basename(os.path.normpath(src_dir))
    dest_dir = os.path.join(dest_parent, dirname)
    shutil.copytree(src_dir, dest_dir)


def chown_r(path, user, group):
    # http://stackoverflow.com/questions/2853723
    for root, dirs, files in os.walk(path):
        for x in dirs:
            shutil.chown(os.path.join(root, x), user, group)
        for x in files:
            shutil.chown(os.path.join(root, x), user, group)


def get_lines_without_comments(filename):
    lines = []
    with open(filename) as f:
        for line in f:
            line = line.partition('#')[0]
            line = line.rstrip()
            line = line.lstrip()
            if line:
                lines.append(line)
    return lines
