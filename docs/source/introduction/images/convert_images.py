#!/usr/bin/env python

import subprocess
import os

FILENAMES = ['crate.pdf']
THIS_DIR = os.path.dirname(os.path.realpath(__file__))


if __name__ == '__main__':
    for filename in FILENAMES:
        infile = os.path.join(THIS_DIR, filename)
        outfile = os.path.splitext(infile)[0] + '.png'
        args = ['convert', '-trim', '-density', '300', infile, outfile]
        subprocess.call(args)
