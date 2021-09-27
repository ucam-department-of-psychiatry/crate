#!/usr/bin/env python

"""
crate_anon/common/profiling.py

===============================================================================

    Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).

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
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

crate_anon/common/sql.py
**A single function to profile particular functions or methods**

"""

import cProfile
from typing import Any, Callable

FuncType = Callable[[Any], Any]


def do_cprofile(func: FuncType) -> FuncType:
    """
    Print profile stats to screen. To be used as a decorator for the function
    or method you want to profile.
    """
    def profiled_func(*args, **kwargs) -> Any:
        profile = cProfile.Profile()
        try:
            profile.enable()
            result = func(*args, **kwargs)
            profile.disable()
            return result
        finally:
            profile.print_stats()
    return profiled_func


def do_cprofile_raw(func):
    """
    Decorator to generate profiler output for slow code

    from crate_anon.common.profiling import do_cprofile_raw

    Add @do_cprofile_raw to the function you want to profile.
    Will generate a file called <function name>.profile.

    Can be visualised with e.g. SnakeViz (pip install snakeviz)
    """

    def profiled_func(*args, **kwargs):
        profile = cProfile.Profile()
        retval = profile.runcall(func, *args, **kwargs)

        filename = func.__name__ + ".profile"
        profile.dump_stats(filename)

        return retval

    return profiled_func
