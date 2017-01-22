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
import re
from typing import Any, Dict, Generator, List, Optional


COLTYPE_WITH_ONE_INTEGER_REGEX = re.compile(r"^([A-z]+)\((\d+)\)$")
# ... start, group(alphabetical), literal (, group(digit), literal ), end


def escape_quote_in_literal(s: str) -> str:
    """
    Escape '. We could use '' or \'.
    Let's use \. for consistency with percent escaping.
    """
    return s.replace("'", r"\'")


def escape_percent_in_literal(sql: str) -> str:
    """
    Escapes % by converting it to \%.
    Use this for LIKE clauses.
    http://dev.mysql.com/doc/refman/5.7/en/string-literals.html
    """
    return sql.replace('%', r'\%')


def escape_percent_for_python_dbapi(sql: str) -> str:
    """
    Escapes % by converting it to %%.
    Use this for SQL within Python where % characters are used for argument
    placeholders.
    """
    return sql.replace('%', '%%')


def escape_sql_string_literal(s: str) -> str:
    """
    Escapes SQL string literal fragments against quotes and parameter
    substitution.
    """
    return escape_percent_in_literal(escape_quote_in_literal(s))


def translate_sql_qmark_to_percent(sql: str) -> str:
    """
    Translate SQL using ? placeholders to SQL using %s placeholders,
    for engines like MySQL.
    """
    # Django always uses the '%s' placeholder, not ?
    # ... https://docs.djangoproject.com/en/1.8/topics/db/sql/
    # I prefer ?, because % is used in LIKE clauses.
    # 1. Escape % characters
    sql = escape_percent_for_python_dbapi(sql)
    # 2. Replace ? characters that are not within quotes with %s.
    newsql = ""
    in_quotes = False
    for c in sql:
        if c == "'":
            in_quotes = not in_quotes
        if c == '?' and not in_quotes:
            newsql += '%s'
        else:
            newsql += c
    return newsql


if False:
    _SQLTEST1 = "SELECT a FROM b WHERE c=? AND d LIKE 'blah%' AND e='?'"
    _SQLTEST2 = "SELECT a FROM b WHERE c=%s AND d LIKE 'blah%%' AND e='?'"
    _SQLTEST3 = translate_sql_qmark_to_percent(_SQLTEST1)


def get_fieldnames_from_cursor(cursor) -> List[str]:
    """
    Get fieldnames from an executed cursor.
    """
    return [i[0] for i in cursor.description]


def tsv_escape(x: str) -> str:
    """
    Escape data for tab-separated value format.
    """
    if x is None:
        return ""
    x = str(x)
    return x.replace("\t", "\\t").replace("\n", "\\n")


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


def is_mysql_column_type_textual(column_type: str,
                                 min_length: int = 1) -> bool:
    column_type = column_type.upper()
    if column_type == 'TEXT':
        return True
    try:
        m = COLTYPE_WITH_ONE_INTEGER_REGEX.match(column_type)
        basetype = m.group(1)
        length = int(m.group(2))
    except (AttributeError, ValueError):
        return False
    return length >= min_length and basetype in ['CHAR', 'VARCHAR']
