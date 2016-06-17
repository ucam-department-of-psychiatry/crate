#!/usr/bin/env python

import os


def main():
    this_dir = os.path.abspath(os.path.dirname(__file__))
    filename = os.path.abspath(os.path.join(
        this_dir, "..", "crateweb", "specimen_secret_local_settings",
        "crateweb_local_settings.py"
    ))
    for line in open(filename):
        print(line.rstrip('\n'))


if __name__ == '__main__':
    main()
