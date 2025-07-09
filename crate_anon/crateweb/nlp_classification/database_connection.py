from typing import Any, Iterable, Optional, Sequence

from django.db import connections


class DatabaseConnection:
    def __init__(self, connection_name: str) -> None:
        self.connection_name = connection_name

    def fetchone_as_dict(
        self,
        column_names: Iterable[str],
        table_name: str,
        where: Optional[str] = None,
        params: Optional[Sequence[Any]] = None,
    ) -> dict[str, Any]:

        out = {}

        sql = self.get_sql(column_names, table_name, where, params)

        with connections[self.connection_name].cursor() as cursor:
            cursor.execute(sql, params)
            row = cursor.fetchone()

            if row:
                for index, column_name in enumerate(column_names):
                    out[column_name] = row[index]

        return out

    def fetchall(
        self,
        column_names: Iterable[str],
        table_name: str,
        where: Optional[str] = None,
        params: Optional[Sequence[Any]] = None,
    ):  # TODO: Return type
        sql = self.get_sql(column_names, table_name, where, params)

        with connections[self.connection_name].cursor() as cursor:
            cursor.execute(sql, params)
            for row in cursor.fetchall():
                yield row

    def get_sql(
        self,
        column_names: Iterable[str],
        table_name: str,
        where: Optional[str] = None,
        params: Optional[Sequence[Any]] = None,
    ) -> str:

        column_names_str = ", ".join(column_names)
        sql = f"SELECT {column_names_str} FROM {table_name}"
        if where:
            sql += f" WHERE {where}"

        return sql
