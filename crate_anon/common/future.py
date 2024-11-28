"""
crate_anon/preprocess/autoimport_db.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

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

**Python code that will be in the Python standard library in higher versions of
Python.**

"""

from itertools import islice
from typing import Any, Generator, Iterable, List
import warnings


def batched(
    iterable: Iterable[Any], n: int
) -> Generator[List[Any], None, None]:
    """
    Batch data into lists of length n. The last batch may be shorter.

    batched('ABCDEFG', 3) --> ABC DEF G

    From Python 3.12, this is itertools.batched(). See

    - https://stackoverflow.com/questions/8290397
    - https://docs.python.org/3/library/itertools.html#itertools.batched
    """
    warnings.warn(
        "When Python 3.12 is the minimum for CRATE, use itertools.batched "
        "instead of crate_anon.common.future.batched",
        FutureWarning,
    )
    it = iter(iterable)
    while True:
        batch = list(islice(it, n))
        if not batch:
            return
        yield batch
