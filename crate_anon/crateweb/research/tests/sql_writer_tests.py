"""
crate_anon/crateweb/research/tests/sql_writer_tests.py

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

Test sql_writer.py.

"""

import logging

from cardinal_pythonlib.sql.sql_grammar_factory import make_grammar
from cardinal_pythonlib.sqlalchemy.dialect import SqlaDialectName
from django.test import TestCase

from crate_anon.common.sql import ColumnId, WhereCondition
from crate_anon.crateweb.research.errors import DatabaseStructureNotUnderstood
from crate_anon.crateweb.research.sql_writer import (
    add_to_select,
    SelectElement,
)

log = logging.getLogger(__name__)


class AddToSelectTests(TestCase):
    def setUp(self) -> None:
        super().setUp()
        self.grammar = make_grammar(SqlaDialectName.MYSQL)

    def assert_query_equal(self, actual: str, expected: str) -> None:
        # Test a query string matches the expected value, ignoring
        # whitespace differences
        actual = actual.replace(" ,", ",")
        actual = " ".join(actual.split())

        self.assertEqual(actual, expected)

    def test_second_table_joined(self) -> None:
        sql = add_to_select(
            "SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 5",
            grammar=self.grammar,
            select_elements=[
                SelectElement(column_id=ColumnId(table="t2", column="c"))
            ],
            # magic_join requires DB knowledge hence Django
            magic_join=False,
        )
        self.assert_query_equal(
            sql,
            (
                "SELECT t1.a, t1.b, t2.c FROM t1 NATURAL JOIN t2 "
                "WHERE t1.col1 > 5"
            ),
        )

    def test_another_column_added(self) -> None:
        sql = add_to_select(
            "SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 5",
            grammar=self.grammar,
            select_elements=[
                SelectElement(column_id=ColumnId(table="t1", column="a"))
            ],
        )
        self.assert_query_equal(
            sql, "SELECT t1.a, t1.b, t1.a FROM t1 WHERE t1.col1 > 5"
        )

    def test_select_element_added_to_nothing(self) -> None:
        sql = add_to_select(
            "",
            grammar=self.grammar,
            select_elements=[
                SelectElement(column_id=ColumnId(table="t2", column="c"))
            ],
        )
        self.assert_query_equal(sql, "SELECT t2.c FROM t2")

    def test_first_where_condition_added(self) -> None:
        sql = add_to_select(
            "SELECT t1.a, t1.b FROM t1",
            grammar=self.grammar,
            where_conditions=[WhereCondition(raw_sql="t1.col1 > 5")],
        )
        self.assert_query_equal(
            sql, "SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 5"
        )

    def test_second_where_condition_added(self) -> None:
        sql = add_to_select(
            "SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 5",
            grammar=self.grammar,
            where_conditions=[WhereCondition(raw_sql="t1.col2 < 3")],
        )

        self.assert_query_equal(
            sql, "SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 5 AND t1.col2 < 3"
        )

    def test_third_where_condition_added(self) -> None:
        sql = add_to_select(
            "SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 5 AND t3.col99 = 100",
            grammar=self.grammar,
            where_conditions=[WhereCondition(raw_sql="t1.col2 < 3")],
        )
        self.assert_query_equal(
            sql,
            (
                "SELECT t1.a, t1.b FROM t1 "
                "WHERE t1.col1 > 5 AND t3.col99 = 100 AND t1.col2 < 3"
            ),
        )

    def test_multiple_wheres_added_to_none(self) -> None:
        sql = add_to_select(
            "SELECT t1.a, t1.b FROM t1",
            grammar=self.grammar,
            where_conditions=[
                WhereCondition(raw_sql="t1.col1 > 99"),
                WhereCondition(raw_sql="t1.col2 < 999"),
            ],
        )
        self.assert_query_equal(
            sql,
            "SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 99 AND t1.col2 < 999",
        )

    def test_raises_when_table_does_not_exist(self) -> None:
        column_id = ColumnId(
            schema="research", table="blobdoc", column="_src_hash"
        )
        with self.assertRaises(DatabaseStructureNotUnderstood):
            add_to_select(
                "SELECT foo from bar",
                grammar=self.grammar,
                select_elements=[SelectElement(column_id=column_id)],
            )
