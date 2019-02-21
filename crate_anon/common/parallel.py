#!/usr/bin/env python

"""
crate_anon/common/parallel.py

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

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

**Assistance functions for "embarrassingly parallel" job assignment.**

"""

import logging
from typing import Any

from cardinal_pythonlib.hash import hash64

log = logging.getLogger(__name__)


def is_my_job_by_int(value: int, tasknum: int, ntasks: int) -> bool:
    """
    "Is it my job to do this work?"

    Args:
        value: some integer value that is fairly evenly distributed, to spread
            the workload
        tasknum: which task number am I?
        ntasks: how many tasks are there in total?

    Returns:
        is it my job?

    Algorithm:

    - if there's only one task: yes
    - otherwise, return ``value % ntasks == tasknum``

    """
    if ntasks == 1:
        return True
    return value % ntasks == tasknum


def is_my_job_by_hash(value: Any, tasknum: int, ntasks: int) -> bool:
    """
    "Is it my job to do this work?"

    Args:
        value: anything that's hashable
        tasknum: which task number am I?
        ntasks: how many tasks are there in total?

    Returns:
        is it my job?

    Algorithm:

    - We convert some non-integer thing into a deterministic but roughly
      randomly distributed integer using :func:`hash64`. That produces a signed
      integer, which is OK because ``%`` works nonetheless.

    When we use it:

    - We use this function to parallelize for non-integer PKs.

    - This is less efficient than dividing the work up via SQL, because we have
      to fetch/hash something.

    - Perform this test ASAP in loops, for speed.
    """
    if ntasks == 1:
        return True
    return hash64(value) % ntasks == tasknum


def is_my_job_by_hash_prehashed(hashed_value: int,
                                tasknum: int,
                                ntasks: int) -> bool:
    """
    A version of :func:`is_my_job_by_hash` for use when you have pre-hashed
    the value, and ``ntasks`` is guaranteed to be >1.

    Args:
        hashed_value: integer hashed value
        tasknum: which task number am I?
        ntasks: how many tasks are there in total?

    Returns:
        is it my job?

    """
    return hashed_value % ntasks == tasknum
