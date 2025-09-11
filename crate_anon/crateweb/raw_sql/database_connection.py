"""
crate_anon/crateweb/raw_sql/database_connection.py

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

Methods for direct database access with raw SQL queries i.e. not via the Django
ORM.

"""

import logging
from typing import Any, Iterable, Optional, Sequence, Tuple

from cardinal_pythonlib.dbfunc import dictfetchall
from cardinal_pythonlib.django.django_constants import ConnectionVendors
from cardinal_pythonlib.json_utils.serialize import (
    METHOD_NO_ARGS,
    register_for_json,
)
from cardinal_pythonlib.logs import BraceStyleAdapter
from django.db import connections
from django.db.backends.base.base import BaseDatabaseWrapper

from crate_anon.common.sql import (
    SqlArgsTupleType,
    translate_sql_qmark_to_percent,
)

log = BraceStyleAdapter(logging.getLogger(__name__))


class UnsupportedEngineException(Exception):
    pass


@register_for_json(method=METHOD_NO_ARGS)
class DatabaseConnection:
    def __init__(self, connection_name: str) -> None:
        self.connection_name = connection_name
        self._schema_infodictlist = None

    def fetchone_as_dict(
        self,
        column_names: Iterable[str],
        table_name: str,
        where: Optional[str] = None,
        params: Optional[Sequence[Any]] = None,
    ) -> dict[str, Any]:

        out = {}

        sql = self.get_sql(column_names, table_name, where, params)

        with self.connection.cursor() as cursor:
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

        with self.connection.cursor() as cursor:
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

    def get_table_names(self) -> set[str]:
        table_names = []

        for infodict in self.get_schema_infodictlist():
            table_names.append(
                self.get_case_insensitive_value(infodict, "table_name")
            )

        return sorted(set(table_names))

    def get_column_names_for_table(self, table_name: str) -> set[str]:
        column_names = []

        for infodict in self.get_schema_infodictlist():
            if table_name == self.get_case_insensitive_value(
                infodict, "table_name"
            ):
                column_names.append(
                    self.get_case_insensitive_value(infodict, "column_name")
                )

        return sorted(column_names)

    @staticmethod
    def get_case_insensitive_value(infodict: dict[str, Any], key: str) -> Any:
        return infodict.get(key) or infodict.get(key.upper())

    # -------------------------------------------------------------------------
    # Fetching schema info from the database: internals
    # -------------------------------------------------------------------------

    def _schema_query_microsoft(
        self, db_name: str, schema_names: list[str]
    ) -> SqlArgsTupleType:
        """
        Returns a query to fetch the database structure from an SQL Server
        database.

        The columns returned are as expected by
        :func:`get_schema_infodictlist`.

        Args:
            db_name: a database name
            schema_names: a list of schema names within the database

        Returns:
            tuple: ``sql, args``

        Notes:

        - SQL Server ``INFORMATION_SCHEMA.COLUMNS``: see
          https://msdn.microsoft.com/en-us/library/ms188348.aspx
        - Re fulltext indexes:

          - https://stackoverflow.com/questions/16280918/how-to-find-full-text-indexing-on-database-in-sql-server-2008
          - ``sys.fulltext_indexes``: https://msdn.microsoft.com/en-us/library/ms186903.aspx
          - ``sys.fulltext_catalogs``: https://msdn.microsoft.com/en-us/library/ms188779.aspx
          - ``sys.fulltext_index_columns``: https://msdn.microsoft.com/en-us/library/ms188335.aspx

        """  # noqa: E501
        if not schema_names:
            raise ValueError(
                "No schema_names specified (for SQL Server " "database)"
            )
        schema_placeholder = ",".join(["?"] * len(schema_names))
        sql = translate_sql_qmark_to_percent(
            f"""
SELECT
    ? AS table_catalog,
    d.table_schema,
    d.table_name,
    d.column_name,
    d.is_nullable,
    d.column_type,
    d.column_comment,
    CASE WHEN COUNT(d.index_id) > 0 THEN 1 ELSE 0 END AS indexed,
    CASE
        WHEN COUNT(d.fulltext_index_object_id) > 0 THEN 1
        ELSE 0
    END AS indexed_fulltext
FROM (
    SELECT
        s.name AS table_schema,
        ta.name AS table_name,
        c.name AS column_name,
        c.is_nullable,
        UPPER(ty.name) + '(' + CONVERT(VARCHAR(100), c.max_length) + ')'
            AS column_type,
        CONVERT(VARCHAR(1000), x.value) AS column_comment,
            -- x.value is of type SQL_VARIANT
        i.index_id,
        fi.object_id AS fulltext_index_object_id
    FROM [{db_name}].sys.tables ta
    INNER JOIN [{db_name}].sys.schemas s ON ta.schema_id = s.schema_id
    INNER JOIN [{db_name}].sys.columns c ON c.object_id = ta.object_id
    INNER JOIN [{db_name}].sys.types ty ON ty.system_type_id = c.system_type_id
    LEFT JOIN [{db_name}].sys.extended_properties x ON (
        x.major_id = c.object_id
        AND x.minor_id = c.column_id
    )
    LEFT JOIN [{db_name}].sys.index_columns i ON (
        i.object_id = c.object_id
        AND i.column_id = c.column_id
    )
    LEFT JOIN [{db_name}].sys.fulltext_index_columns fi ON (
        fi.object_id = c.object_id
        AND fi.column_id = c.column_id
    )
    WHERE s.name IN ({schema_placeholder})
    AND ty.user_type_id = ty.system_type_id
        -- restricts to system data types; eliminates 'sysname' type
) AS d
GROUP BY
    table_schema,
    table_name,
    column_name,
    is_nullable,
    column_type,
    column_comment
ORDER BY
    table_schema,
    table_name,
    column_name
            """
        )
        args = [db_name] + schema_names
        return sql, args

    def _schema_query_mysql(self, db_and_schema_name: str) -> SqlArgsTupleType:
        """
        Returns a query to fetch the database structure from a MySQL database.

        The columns returned are as expected by
        :func:`get_schema_infodictlist`.

        Args:
            db_and_schema_name: the database (and schema) name

        Returns:
            tuple: ``sql, args``

        Notes:

        - MySQL's ``INFORMATION_SCHEMA.COLUMNS``: see
          https://dev.mysql.com/doc/refman/5.7/en/tables-table.html

        """
        # ---------------------------------------------------------------------
        # Method A. Stupidly slow, e.g. 47s for the query.
        # ---------------------------------------------------------------------
        # It's the EXISTS stuff that's slow.
        #
        # sql = translate_sql_qmark_to_percent("""
        #     SELECT
        #         c.table_schema,
        #         c.table_name,
        #         c.column_name,
        #         c.is_nullable,
        #         c.column_type,  /* MySQL: e.g. varchar(32) */
        #         c.column_comment,  /* MySQL */
        #         EXISTS (
        #             SELECT *
        #             FROM information_schema.statistics s
        #             WHERE s.table_schema = c.table_schema
        #             AND s.table_name = c.table_name
        #             AND s.column_name = c.column_name
        #         ) AS indexed,
        #         EXISTS (
        #             SELECT *
        #             FROM information_schema.statistics s
        #             WHERE s.table_schema = c.table_schema
        #             AND s.table_name = c.table_name
        #             AND s.column_name = c.column_name
        #             AND s.index_type LIKE 'FULLTEXT%'
        #         ) AS indexed_fulltext
        #     FROM
        #         information_schema.columns c
        #     WHERE
        #         c.table_schema IN ({schema_placeholder})
        #     ORDER BY
        #         c.table_schema,
        #         c.table_name,
        #         c.column_name
        # """.format(
        #     schema_placeholder=",".join(["?"] * len(schemas)),
        # ))
        # args = schemas

        # ---------------------------------------------------------------------
        # Method B. Much faster, e.g. 0.35s for the same thing.
        # ---------------------------------------------------------------------
        # http://www.codeproject.com/Articles/33052/Visual-Representation-of-SQL-Joins  # noqa: E501
        # (Note that EXISTS() above returns 0 or 1.)
        # The LEFT JOIN below will produce NULL values for the index
        # columns for non-indexed fields.
        # However, you can have more than one index on a column, in which
        # case the column appears in two rows.
        sql = translate_sql_qmark_to_percent(
            """
SELECT
    '' AS table_catalog,
    d.table_schema,
    d.table_name,
    d.column_name,
    d.is_nullable,
    d.column_type,
    d.column_comment,
    d.indexed,
    MAX(d.indexed_fulltext) AS indexed_fulltext
FROM (
    SELECT
        -- c.table_catalog,  -- will always be 'def'
        c.table_schema,
        c.table_name,
        c.column_name,
        c.is_nullable,
        c.column_type,  /* MySQL: e.g. varchar(32) */
        c.column_comment,  /* MySQL */
        /* s.index_name, */
        /* s.index_type, */
        IF(s.index_type IS NOT NULL, 1, 0) AS indexed,
        IF(s.index_type LIKE 'FULLTEXT%', 1, 0) AS indexed_fulltext
    FROM
        information_schema.columns c
        LEFT JOIN information_schema.statistics s
        ON (
            c.table_schema = s.table_schema
            AND c.table_name = s.table_name
            AND c.column_name = s.column_name
        )
    WHERE
        c.table_schema = ?
) AS d  /* "Every derived table must have its own alias" */
GROUP BY
    table_catalog,
    table_schema,
    table_name,
    column_name,
    is_nullable,
    column_type,
    column_comment,
    indexed
ORDER BY
    table_catalog,
    table_schema,
    table_name,
    column_name
            """
        )
        args = [db_and_schema_name]
        return sql, args

    def _schema_query_postgres(
        self, schema_names: list[str]
    ) -> SqlArgsTupleType:
        """
        Returns a query to fetch the database structure from an SQL Server
        database.

        The columns returned are as expected by
        :func:`get_schema_infodictlist`.

        Args:
            schema_names: a list of schema names within the database

        Returns:
            tuple: ``sql, args``

        Notes:

        - A PostgreSQL connection is always to a single database; see
          https://stackoverflow.com/questions/10335561/use-database-name-command-in-postgresql
        - https://dba.stackexchange.com/questions/75015
        - https://stackoverflow.com/questions/14713774
        - Note that creating a GIN index looks like:

          .. code-block:: sql

            ALTER TABLE t ADD COLUMN tsv_mytext TSVECTOR;
            UPDATE t SET tsv_mytext = to_tsvector(mytext);
            CREATE INDEX idx_t_mytext_gin ON t USING GIN(tsv_mytext);

        - PostgreSQL ``INFORMATION_SCHEMA.COLUMNS``: see
          https://www.postgresql.org/docs/9.1/static/infoschema-columns.html

        """
        if not schema_names:
            raise ValueError(
                "No schema_names specified (for PostgreSQL " "database)"
            )
        schema_placeholder = ",".join(["?"] * len(schema_names))
        sql = translate_sql_qmark_to_percent(
            f"""
SELECT
    '' AS table_catalog,
    d.table_schema,
    d.table_name,
    d.column_name,
    d.is_nullable,
    d.column_type,
    d.column_comment,
    CASE WHEN COUNT(d.indrelid) > 0 THEN 1 ELSE 0 END AS indexed,
    MAX(d.indexed_fulltext) AS indexed_fulltext
FROM (
    SELECT
        -- c.table_catalog,  -- will always be the connection's database name
        c.table_schema,
        c.table_name,
        c.column_name,
        a.attnum as column_seq_num,
        c.is_nullable,
        pg_catalog.format_type(a.atttypid, a.atttypmod) as column_type,
        pgd.description AS column_comment,
        i.indrelid,
        CASE
            WHEN pg_get_indexdef(indexrelid) ~ 'USING (gin |gist )' THEN 1
            ELSE 0
        END AS indexed_fulltext
    FROM pg_catalog.pg_statio_all_tables AS t
    INNER JOIN information_schema.columns c ON (
        c.table_schema = t.schemaname
        AND c.table_name = t.relname
    )
    INNER JOIN pg_catalog.pg_attribute a ON (  -- one row per column
        a.attrelid = t.relid
        AND a.attname = c.column_name
    )
    LEFT JOIN pg_catalog.pg_index AS i ON (
        i.indrelid = t.relid  -- match on table
        AND i.indkey[0] = a.attnum  -- match on column sequence number
        AND i.indnatts = 1  -- one column in the index
    )
    LEFT JOIN pg_catalog.pg_description pgd ON (
        pgd.objoid = t.relid
        AND pgd.objsubid = c.ordinal_position
    )
    WHERE t.schemaname IN ({schema_placeholder})
) AS d
GROUP BY
    table_catalog,
    table_schema,
    table_name,
    column_name,
    is_nullable,
    column_type,
    column_comment
ORDER BY
    table_catalog,
    table_schema,
    table_name,
    column_name
            """
        )
        args = schema_names
        return sql, args

    def _schema_query_sqlite_as_infodictlist(
        self, debug: bool = False
    ) -> list[dict[str, Any]]:
        """
        Queries an SQLite databases and returns columns as expected by
        :func:`get_schema_infodictlist`.
        """
        # 1. Catalogue tables.
        # pragma table_info(sqlite_master);
        empty_args = []
        sql_get_tables = """
            SELECT tbl_name AS tablename
            FROM sqlite_master
            WHERE type='table'
        """
        table_info_rows = self._exec_sql_query(
            (sql_get_tables, empty_args), debug=debug
        )
        table_names = [row["tablename"] for row in table_info_rows]

        # 2. Catalogue each tables
        results = []  # type: list[dict[str, Any]]
        for table_name in table_names:
            # A "PRAGMA table_info()" call doesn't work with arguments.
            sql_inspect_table = f"PRAGMA table_info({table_name})"
            column_info_rows = self._exec_sql_query(
                (sql_inspect_table, empty_args), debug=debug
            )
            for ci in column_info_rows:
                results.append(
                    dict(
                        table_catalog="",
                        table_schema="",
                        table_name=table_name,
                        column_name=ci["name"],
                        is_nullable=1 - ci["notnull"],
                        column_type=ci["type"],
                        column_comment="",
                        indexed=0,
                        indexed_fulltext=0,
                    )
                )
                # Ignored:
                # - "cid" (column ID)
                # - "dflt_value"
                # - "pk"
        return results

    def _exec_sql_query(
        self,
        sql_args: SqlArgsTupleType,
        debug: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Used by get_schema_infodictlist() as a common function to translate an
        sql/args pair into the desired results. But it does that because the
        incoming SQL has the right column names; the function is more generic
        and just runs a query.

        Args:
            connection:
                a :class:`django.db.backends.base.base.BaseDatabaseWrapper`,
                i.e. a Django database connection
            sql_args:
                tuple of SQL and arguments
            debug:
                be verbose to the log?

        Returns:
            A list of dictionaries, each mapping column names to values.
            The dictionaries are suitable for use as ``**kwargs`` to
            :class:`ColumnInfo`.
        """
        # We execute this one directly, rather than using the Query class,
        # since this is a system rather than a per-user query.
        sql, args = sql_args
        cursor = self.connection.cursor()
        if debug:
            log.debug(f"- sql = {sql}\n- args = {args!r}")
        cursor.execute(sql, args)
        # Re passing multiple values to SQL via args:
        # - Don't circumvent the parameter protection against SQL injection.
        # - Too much hassle to use Django's ORM model here, though that would
        #   also be possible.
        # - https://stackoverflow.com/questions/907806
        # - Similarly via SQLAlchemy reflection/inspection.
        results = dictfetchall(cursor)  # list of OrderedDicts
        if debug:
            log.debug(f"results = {results!r}")
        log.debug("... done")
        return results

    # -------------------------------------------------------------------------
    # Fetching schema info from the database: main (still internal) interface
    # -------------------------------------------------------------------------
    def get_schema_infodictlist(
        self, db_name: str = None, schema_name: str = None, debug: bool = False
    ) -> list[dict[str, Any]]:
        """
        Fetch structure information for a specific database, by asking the
        database.

        Args:
            debug:
                be verbose to the log?

        Returns:
            A list of dictionaries, each mapping column names to values.
            The dictionaries are suitable for use as ``**kwargs`` to
            :class:`ColumnInfo`.

        """

        if self._schema_infodictlist is None:
            self._schema_infodictlist = self._get_schema_results_for_vendor(
                db_name, schema_name, debug
            )

        return self._schema_infodictlist

    def _get_schema_results_for_vendor(
        self, db_name: str = None, schema_name: str = None, debug: bool = False
    ) -> list[dict[str, Any]]:
        if db_name is None and schema_name is None:
            (db_name, schema_name) = self._get_db_and_schema_name()

        # The db/schema names are guaranteed to be strings by __init__().
        if self.connection.vendor == ConnectionVendors.MICROSOFT:
            if not db_name:
                raise ValueError(f"{db_name=!r}; required for MSSQL")
            if not schema_name:
                raise ValueError(f"{schema_name=!r}; required for MSSQL")
            results = self._exec_sql_query(
                sql_args=self._schema_query_microsoft(db_name, [schema_name]),
                debug=debug,
            )
        elif self.connection.vendor == ConnectionVendors.POSTGRESQL:
            if db_name:
                raise ValueError(f"{db_name=!r}; must be '' for PostgreSQL")
            if not schema_name:
                raise ValueError(f"{schema_name=!r}; required for PostgreSQL")
            results = self._exec_sql_query(
                sql_args=self._schema_query_postgres([schema_name]),
                debug=debug,
            )
        elif self.connection.vendor == ConnectionVendors.MYSQL:
            if db_name:
                raise ValueError(f"{db_name=!r}; must be '' for MySQL")
            if not schema_name:
                raise ValueError(f"{schema_name=!r}; required for MySQL")
            results = self._exec_sql_query(
                sql_args=self._schema_query_mysql(
                    db_and_schema_name=schema_name
                ),
                debug=debug,
            )
        elif self.connection.vendor == ConnectionVendors.SQLITE:
            # db_name: don't care?
            # schema_name: don't care?
            # This one can't be done as a single query; the following function
            # builds up the information by querying a list of tables, then each
            # table.
            results = self._schema_query_sqlite_as_infodictlist(debug=debug)
        else:
            raise ValueError(
                f"Don't know how to get metadata for "
                f"{self.connection.vendor=!r}"
            )

        return results

    # TODO: Duplicate code in research_db_info.py
    def _get_db_and_schema_name(self) -> Tuple[str, str]:
        db_name = ""
        schema_name = ""

        if self.connection.vendor == ConnectionVendors.MICROSOFT:
            db_name = self.connection.settings_dict["NAME"]
            schema_name = "dbo"
        elif self.connection.vendor == ConnectionVendors.MYSQL:
            schema_name = self.connection.settings_dict["NAME"]
        elif self.connection.vendor == ConnectionVendors.POSTGRESQL:
            schema_name = "public"
        elif self.connection.vendor == ConnectionVendors.SQLITE:
            pass
        else:
            raise UnsupportedEngineException(
                f"Connection vendor '{self.connection.vendor}' "
                "is not supported."
            )

        return (db_name, schema_name)
        log.info(
            f"Fetching/caching database structure (for database "
            f"{db_name!r}, schema {schema_name!r})..."
        )

    def offers_db_above_schema(self) -> bool:
        """
        Does the database simultaneously offer a "database" level above its
        "schema" level?

        - True for Microsoft SQL Server
        - False for MySQL (in which "database" and "schema" are synonymous)
        - False for PostgreSQL (in which a connection can only talk to one
          database at once, though there can be many schemas within each
          database).

        Args:
            connection:
                a :class:`django.db.backends.base.base.BaseDatabaseWrapper`,
                i.e. a Django database connection
        """
        return self.connection.vendor in [ConnectionVendors.MICROSOFT]

    @property
    def connection(self) -> BaseDatabaseWrapper:
        return connections[self.connection_name]
