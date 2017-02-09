#!/usr/bin/env python
# crate_anon/crateweb/core/dbfunc.py

"""
===============================================================================
    Copyright (C) 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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

from collections import OrderedDict
# import logging
# log = logging.getLogger(__name__)
from typing import Any, Dict, Generator, List, Optional


def get_fieldnames_from_cursor(cursor) -> List[str]:
    """
    Get fieldnames from an executed cursor.
    """
    return [i[0] for i in cursor.description]


def tsv_escape(x: Any) -> str:
    """
    Escape data for tab-separated value format.
    """
    if x is None:
        return ""
    x = str(x)
    return x.replace("\t", "\\t").replace("\n", "\\n")


def make_tsv_row(values: List[Any]) -> str:
    return "\t".join([tsv_escape(x) for x in values]) + "\n"


def genrows(cursor, arraysize: int = 1000) -> Generator[List[Any], None, None]:
    """Generate all rows from a cursor."""
    # http://code.activestate.com/recipes/137270-use-generators-for-fetching-large-db-record-sets/  # noqa
    while True:
        results = cursor.fetchmany(arraysize)
        if not results:
            break
        for result in results:
            yield result


def genfirstvalues(cursor, arraysize: int = 1000) -> Generator[Any, None, None]:
    """Generate the first value in each row."""
    return (row[0] for row in genrows(cursor, arraysize))


def fetchallfirstvalues(cursor) -> List[Any]:
    """Return a list of the first value in each row."""
    return [row[0] for row in cursor.fetchall()]


def gendicts(cursor, arraysize: int = 1000) -> Generator[Dict[str, Any],
                                                         None, None]:
    """Generate all rows from a cursor as a list of OrderedDicts."""
    columns = get_fieldnames_from_cursor(cursor)
    return (
        OrderedDict(zip(columns, row))
        for row in genrows(cursor, arraysize)
    )


def dictfetchall(cursor) -> List[Dict[str, Any]]:
    """Return all rows from a cursor as a list of OrderedDicts."""
    columns = get_fieldnames_from_cursor(cursor)
    return [
        OrderedDict(zip(columns, row))
        for row in cursor.fetchall()
    ]


def dictfetchone(cursor) -> Optional[Dict[str, Any]]:
    """
    Return the next row from a cursor as an OrderedDict, or None
    """
    columns = get_fieldnames_from_cursor(cursor)
    row = cursor.fetchone()
    if not row:
        return None
    return OrderedDict(zip(columns, row))


def dictlist_to_tsv(dictlist: List[Dict[str, Any]]) -> str:
    if not dictlist:
        return ""
    fieldnames = dictlist[0].keys()
    tsv = "\t".join([tsv_escape(f) for f in fieldnames]) + "\n"
    for d in dictlist:
        tsv += "\t".join([tsv_escape(v) for v in d.values()]) + "\n"
    return tsv
