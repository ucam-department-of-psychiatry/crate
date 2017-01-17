#!/usr/bin/env python
# crate_anon/common/debugfunc.py

"""
===============================================================================
    Copyright © 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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

import pdb
import sys
import traceback
from typing import Callable


def pdb_run(main: Callable[[], None]) -> None:
    # noinspection PyBroadException
    try:
        main()
    except:
        type_, value, tb = sys.exc_info()
        traceback.print_exc()
        pdb.post_mortem(tb)
