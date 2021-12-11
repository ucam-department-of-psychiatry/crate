#!/usr/bin/env python

"""
crate_anon/common/tests/sql_tests.py

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

Unit testing.

"""

# =============================================================================
# Imports
# =============================================================================

import logging
from unittest import TestCase

from cardinal_pythonlib.sql.sql_grammar_factory import make_grammar
from cardinal_pythonlib.sqlalchemy.dialect import SqlaDialectName

from crate_anon.common.sql import (
    get_first_from_table,
    matches_fielddef,
    matches_tabledef,
)

log = logging.getLogger(__name__)


# =============================================================================
# Unit tests
# =============================================================================

_ = """
    _SQLTEST1 = "SELECT a FROM b WHERE c=? AND d LIKE 'blah%' AND e='?'"
    _SQLTEST2 = "SELECT a FROM b WHERE c=%s AND d LIKE 'blah%%' AND e='?'"
    _SQLTEST3 = translate_sql_qmark_to_percent(_SQLTEST1)
"""


class SqlTests(TestCase):
    # noinspection PyMethodMayBeStatic
    def test_sql(self) -> None:
        assert matches_tabledef("sometable", "sometable")
        assert matches_tabledef("sometable", "some*")
        assert matches_tabledef("sometable", "*table")
        assert matches_tabledef("sometable", "*")
        assert matches_tabledef("sometable", "s*e")
        assert not matches_tabledef("sometable", "x*y")

        assert matches_fielddef("sometable", "somefield", "*.somefield")
        assert matches_fielddef("sometable", "somefield", "sometable.somefield")
        assert matches_fielddef("sometable", "somefield", "sometable.*")
        assert matches_fielddef("sometable", "somefield", "somefield")

        grammar = make_grammar(SqlaDialectName.MYSQL)
        sql = ("""
            -- noinspection SqlResolve
            SELECT t1.c1, t2.c2
            FROM t1 INNER JOIN t2 ON t1.k = t2.k
        """)
        parsed = grammar.get_select_statement().parseString(sql, parseAll=True)
        log.critical(repr(parsed))
        table_id = get_first_from_table(parsed)
        log.info(repr(table_id))
