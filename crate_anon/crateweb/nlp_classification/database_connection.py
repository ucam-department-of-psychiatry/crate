from typing import Any, Iterable, Optional

from crate_anon.crateweb.core.constants import (
    NLP_DB_CONNECTION_NAME,
    RESEARCH_DB_CONNECTION_NAME,
)

from django.db import connections


class DatabaseConnection:
    connection_name = None

    @classmethod
    def fetchone_as_dict(
        cls,
        column_names: Iterable[str],
        table_name: str,
        where: Optional[str],
        params: Optional[Iterable[Any]],
    ) -> dict[str, Any]:
        column_names_str = ", ".join(column_names)
        sql = f"SELECT {column_names_str} FROM {table_name} "
        if where:
            sql += f"WHERE {where}"

        out = {}

        with connections[cls.connection_name].cursor() as cursor:
            cursor.execute(sql, params)
            row = cursor.fetchone()
            for index, column_name in enumerate(column_names):
                out[column_name] = row[index]

        return out


class NlpDatabaseConnection(DatabaseConnection):
    connection_name = NLP_DB_CONNECTION_NAME


class ResearchDatabaseConnection(DatabaseConnection):
    connection_name = RESEARCH_DB_CONNECTION_NAME
