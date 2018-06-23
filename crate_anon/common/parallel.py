##!/usr/bin/env python
# crate_anon/common/parallel.py

"""
===============================================================================

    Copyright (C) 2015-2018 Rudolf Cardinal (rudolf@pobox.com).

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

import logging
from typing import Any

from cardinal_pythonlib.hash import hash64

log = logging.getLogger(__name__)


def is_my_job_by_int(value: int, tasknum: int, ntasks: int) -> bool:
    if ntasks == 1:
        return True
    return value % ntasks == tasknum


def is_my_job_by_hash(value: Any, tasknum: int, ntasks: int) -> bool:
    """
    We convert some non-integer thing into a deterministic but roughly
    randomly distributed integer using hash64. That produces a signed integer,
    which is OK because % works nonetheless.

    We use this function to parallelize for non-integer PKs.

    This is less efficient than dividing the work up via SQL, because we have
    to fetch/hash something.

    Perform this test ASAP in loops, for speed.
    """
    if ntasks == 1:
        return True
    return hash64(value) % ntasks == tasknum
