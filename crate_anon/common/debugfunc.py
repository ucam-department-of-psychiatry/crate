#!/usr/bin/env python
# crate_anon/common/debugfunc.py

import pdb
import sys
import traceback


def pdb_run(main):
    # noinspection PyBroadException
    try:
        main()
    except:
        type_, value, tb = sys.exc_info()
        traceback.print_exc()
        pdb.post_mortem(tb)
