#!/usr/bin/env python

"""
crate_anon/nlp_manager/tests/nlp_manager_tests.py

===============================================================================

    Copyright (C) 2015-2020 Rudolf Cardinal (rudolf@pobox.com).

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
import sys

from sqlalchemy.exc import OperationalError
from sqlalchemy.schema import Column
from typing import Any, Dict, Generator, List, Tuple
from unittest import mock, TestCase

from crate_anon.nlp_manager.base_nlp_parser import BaseNlpParser


class FruitParser(BaseNlpParser):
    def test(self) -> None:
        pass

    def dest_tables_columns(self) -> Dict[str, List[Column]]:
        return {}

    def parse(self, text: str) -> Generator[Tuple[str, Dict[str, Any]],
                                            None, None]:
        fruits = ("apple", "banana", "cherry", "fig")

        for word in text.split(" "):
            if word.lower() in fruits:
                yield ("output", {"fruit": word.lower()})


class NlpParserProcessTests(TestCase):
    def setUp(self) -> None:
        self.parser = FruitParser(None, None)

        self.mock_execute_method = mock.Mock()
        self.mock_session = mock.Mock(execute=self.mock_execute_method)
        self.mock_db = mock.Mock(session=self.mock_session)

        # can't set name attribute in constructor here as it has special meaning
        mock_column = mock.Mock()
        mock_column.name = "fruit"  # so set it here

        self.mock_values_method = mock.Mock()
        mock_insert_object = mock.Mock(values=self.mock_values_method)
        mock_insert_method = mock.Mock(return_value=mock_insert_object)
        mock_sqla_table = mock.Mock(columns=[mock_column],
                                    insert=mock_insert_method)
        self.mock_get_table = mock.Mock(return_value=mock_sqla_table)

        self.mock_notify_transaction_method = mock.Mock()
        self.mock_nlpdef = mock.Mock(
            notify_transaction=self.mock_notify_transaction_method
        )
        self.mock_nlpdef.name = "fruitdef"

    def test_inserts_values(self) -> None:
        with self.assertLogs(level=logging.DEBUG) as logging_cm:
            with mock.patch.multiple(self.parser,
                                     _nlpdef=self.mock_nlpdef,
                                     _destdb=self.mock_db,
                                     get_table=self.mock_get_table,
                                     _friendly_name="Fruit"):

                starting_fields_values = {}

                self.parser.process(
                    "Apple Banana Cabbage Dandelion Edelweiss Fig",
                    starting_fields_values
                )

        self.mock_values_method.assert_any_call({"fruit": "apple"})
        self.mock_values_method.assert_any_call({"fruit": "banana"})
        self.mock_values_method.assert_any_call({"fruit": "fig"})
        self.assertEqual(self.mock_values_method.call_count, 3)
        self.assertEqual(self.mock_execute_method.call_count, 3)

        self.mock_notify_transaction_method.assert_any_call(
            self.mock_session, n_rows=1, n_bytes=sys.getsizeof(
                {"fruit": "apple"}
            ),
            force_commit=mock.ANY
        )
        self.mock_notify_transaction_method.assert_any_call(
            self.mock_session, n_rows=1, n_bytes=sys.getsizeof(
                {"fruit": "banana"}
            ),
            force_commit=mock.ANY
        )
        self.mock_notify_transaction_method.assert_any_call(
            self.mock_session, n_rows=1, n_bytes=sys.getsizeof(
                {"fruit": "fig"}
            ),
            force_commit=mock.ANY
        )
        self.assertEqual(self.mock_notify_transaction_method.call_count, 3)

        logger_name = "crate_anon.nlp_manager.base_nlp_parser"
        self.assertIn(
            f"DEBUG:{logger_name}:NLP processor fruitdef/Fruit: found 3 values",
            logging_cm.output
        )

    def test_skips_failed_insert(self) -> None:
        self.mock_execute_method.side_effect = OperationalError(
            "Insert failed", None, None, None
        )
        with self.assertLogs(level=logging.ERROR) as logging_cm:
            with mock.patch.multiple(self.parser,
                                     _nlpdef=self.mock_nlpdef,
                                     _destdb=self.mock_db,
                                     get_table=self.mock_get_table,
                                     _friendly_name="Fruit"):

                starting_fields_values = {}

                self.parser.process(
                    "Apple",
                    starting_fields_values
                )

        self.mock_notify_transaction_method.assert_any_call(
            self.mock_session, n_rows=1, n_bytes=sys.getsizeof(
                {"fruit": "apple"}
            ),
            force_commit=mock.ANY
        )
        logger_name = "crate_anon.nlp_manager.base_nlp_parser"

        self.assertIn(
            f"ERROR:{logger_name}",
            logging_cm.output[0]
        )
        self.assertIn(
            "Insert failed",
            logging_cm.output[0]
        )
