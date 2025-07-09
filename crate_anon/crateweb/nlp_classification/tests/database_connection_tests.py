from unittest import mock
from django.test import TestCase

from crate_anon.crateweb.nlp_classification.database_connection import (
    DatabaseConnection,
)


class DatabaseConnectionTest(TestCase):
    def test_fetchone_as_dict_no_condition(self) -> None:
        column_names = ["column_one", "column_two", "column_three"]
        table_name = "test_table"

        mock_execute = mock.Mock()
        mock_fetchone = mock.Mock(return_value=[1, 2, 3])
        mock_cursor = mock.Mock(execute=mock_execute, fetchone=mock_fetchone)
        mock_cm = mock.Mock(
            return_value=mock.Mock(
                __enter__=mock.Mock(return_value=mock_cursor),
                __exit__=mock.Mock(),
            )
        )
        connection = DatabaseConnection("test")
        mock_connections = {"test": mock.Mock(cursor=mock_cm)}

        with mock.patch.multiple(
            "crate_anon.crateweb.nlp_classification.database_connection",
            connections=mock_connections,
        ):
            row_dict = connection.fetchone_as_dict(column_names, table_name)
            self.assertEqual(
                row_dict, {"column_one": 1, "column_two": 2, "column_three": 3}
            )

            mock_execute.assert_called_once_with(
                "SELECT column_one, column_two, column_three FROM test_table",
                None,
            )
            mock_fetchone.assert_called_once_with()

    def test_fetchone_as_dict_with_condition(self) -> None:
        column_names = ["column_one", "column_two", "column_three"]
        table_name = "test_table"

        mock_execute = mock.Mock()
        mock_fetchone = mock.Mock(return_value=[1, 2, 3])
        mock_cursor = mock.Mock(execute=mock_execute, fetchone=mock_fetchone)
        mock_cm = mock.Mock(
            return_value=mock.Mock(
                __enter__=mock.Mock(return_value=mock_cursor),
                __exit__=mock.Mock(),
            )
        )
        connection = DatabaseConnection("test")
        mock_connections = {"test": mock.Mock(cursor=mock_cm)}

        with mock.patch.multiple(
            "crate_anon.crateweb.nlp_classification.database_connection",
            connections=mock_connections,
        ):
            connection.fetchone_as_dict(
                column_names, table_name, "column_one = %s", ["1"]
            )
            mock_execute.assert_called_once_with(
                (
                    "SELECT column_one, column_two, column_three "
                    "FROM test_table "
                    "WHERE column_one = %s"
                ),
                ["1"],
            )
