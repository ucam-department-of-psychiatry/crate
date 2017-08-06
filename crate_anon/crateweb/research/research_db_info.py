#!/usr/bin/env python
# crate_anon/crateweb/research/research_db_info.py

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
# from functools import lru_cache
import logging
from typing import Any, Dict, List, Optional

from cardinal_pythonlib.dbfunc import dictfetchall
from cardinal_pythonlib.django.function_cache import django_cache_function
from cardinal_pythonlib.excel import excel_to_bytes
from cardinal_pythonlib.json.serialize import METHOD_NO_ARGS, register_for_json
from cardinal_pythonlib.sql.sql_grammar import SqlGrammar
from cardinal_pythonlib.sql.sql_grammar_factory import (
    DIALECT_MSSQL,
    DIALECT_POSTGRES,
    DIALECT_MYSQL,
)
from cardinal_pythonlib.sqlalchemy.schema import (
    MSSQL_DEFAULT_SCHEMA,
    POSTGRES_DEFAULT_SCHEMA,
)
from cardinal_pythonlib.tsv import dictlist_to_tsv
from django.db import connections
from django.db.backends.base.base import BaseDatabaseWrapper
from django.conf import settings
from openpyxl import Workbook

from crate_anon.common.sql import (
    ColumnId,
    is_sql_column_type_textual,
    make_grammar,
    QB_DATATYPE_DATE,
    QB_DATATYPE_FLOAT,
    QB_DATATYPE_INTEGER,
    QB_DATATYPE_STRING,
    QB_DATATYPE_STRING_FULLTEXT,
    QB_DATATYPE_UNKNOWN,
    SchemaId,
    SqlArgsTupleType,
    SQLTYPES_FLOAT,
    SQLTYPES_WITH_DATE,
    SQLTYPES_TEXT,
    SQLTYPES_INTEGER,
    TableId,
    translate_sql_qmark_to_percent,
)

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# https://docs.djangoproject.com/en/1.10/howto/custom-lookups/#writing-alternative-implementations-for-existing-lookups  # noqa
VENDOR_MICROSOFT = 'microsoft'
VENDOR_POSTGRESQL = 'postgresql'
VENDOR_MYSQL = 'mysql'


# =============================================================================
# Information about the research database
# =============================================================================

class ColumnInfo(object):
    # See also querybuilder.js

    def __init__(self, **kwargs) -> None:
        self.table_catalog = kwargs.pop('table_catalog')
        self.table_schema = kwargs.pop('table_schema')
        self.table_name = kwargs.pop('table_name')
        self.column_name = kwargs.pop('column_name')
        self.is_nullable = bool(kwargs.pop('is_nullable'))
        self.column_type = kwargs.pop('column_type')
        self.column_comment = kwargs.pop('column_comment')
        self.indexed = bool(kwargs.pop('indexed'))
        self.indexed_fulltext = bool(kwargs.pop('indexed_fulltext'))

    def basetype(self) -> str:
        return self.column_type.split("(")[0].upper()

    def querybuilder_type(self) -> str:
        """
        Returns a string that is defined in querybuilder.js
        """
        basetype = self.basetype()
        if basetype in SQLTYPES_FLOAT:
            return QB_DATATYPE_FLOAT
        if basetype in SQLTYPES_WITH_DATE:
            return QB_DATATYPE_DATE
        if basetype in SQLTYPES_TEXT:
            if self.indexed_fulltext:
                return QB_DATATYPE_STRING_FULLTEXT
            else:
                return QB_DATATYPE_STRING
        if basetype in SQLTYPES_INTEGER:
            return QB_DATATYPE_INTEGER
        return QB_DATATYPE_UNKNOWN

    def column_id(self) -> ColumnId:
        return ColumnId(db=self.table_catalog,
                        schema=self.table_schema,
                        table=self.table_name,
                        column=self.column_name)

    def table_id(self) -> TableId:
        return TableId(db=self.table_catalog,
                       schema=self.table_schema,
                       table=self.table_name)


@register_for_json(method=METHOD_NO_ARGS)
class ResearchDatabaseInfo(object):
    """
    Fetches schema information from the research database.
    Class primarily exists to be able to use @cached_property.
    ... replaced by @lru_cache
    ... replaced by @django_cache_function
    """
    # We fetch the dialect at first request; this enables us to import the
    # class without Django configured.

    def __init__(self) -> None:
        self._dialect = None
        self._grammar = None

    @property
    def dialect(self) -> str:
        if not self._dialect:
            self._dialect = settings.RESEARCH_DB_DIALECT
        return self._dialect

    @property
    def grammar(self) -> SqlGrammar:
        if not self._grammar:
            self._grammar = make_grammar(self.dialect)
        return self._grammar

    @classmethod
    def _connection(cls) -> BaseDatabaseWrapper:
        return connections['research']

    @classmethod
    def uses_database_level(cls) -> bool:
        return cls._offers_db_above_schema(cls._connection())

    @classmethod
    def format_db_schema(cls, db: str, schema: str) -> str:
        if cls.uses_database_level():
            return "{}.{}".format(db, schema)
        else:
            return schema

    @staticmethod
    def _offers_db_above_schema(connection: BaseDatabaseWrapper) -> bool:
        return connection.vendor in [VENDOR_MICROSOFT]
        # not MySQL ("database" concept = "schema" concept)
        # not PostgreSQL (only one database per connection)

    @staticmethod
    def get_researchdb_schemas() -> List[SchemaId]:
        return [SchemaId(db=x['database'], schema=x['schema'])
                for x in settings.RESEARCH_DB_INFO]

    def get_default_database_name(self) -> str:
        dialect = self.dialect
        if dialect == DIALECT_MSSQL:
            return settings.DATABASES['research']['NAME']
        elif dialect == DIALECT_POSTGRES:
            return ''
        elif dialect == DIALECT_MYSQL:
            return ''
        else:
            raise ValueError("Bad settings.RESEARCH_DB_DIALECT")

    def get_default_schema_name(self) -> str:
        dialect = self.dialect
        if dialect == DIALECT_MSSQL:
            return MSSQL_DEFAULT_SCHEMA
        elif dialect == DIALECT_POSTGRES:
            return POSTGRES_DEFAULT_SCHEMA
        elif dialect == DIALECT_MYSQL:
            return settings.DATABASES['research']['NAME']
        else:
            raise ValueError("Bad settings.RESEARCH_DB_DIALECT")

    def get_db_info(self, schema: SchemaId) -> Optional[Dict[str, Any]]:
        db_name = schema.db() or self.get_default_database_name()
        schema_name = schema.schema() or self.get_default_schema_name()
        for x in settings.RESEARCH_DB_INFO:
            if x['database'] == db_name and x['schema'] == schema_name:
                return x
        log.warning("No such database/schema: {}".format(
            schema.identifier(self.grammar)))
        return None

    def get_schema_trid_field(self, schema: SchemaId) -> str:
        db_info = self.get_db_info(schema)
        if not db_info:
            return ''
        return db_info.get('trid_field', '')

    def get_schema_rid_field(self, schema: SchemaId) -> str:
        schema_info = self.get_db_info(schema)
        if not schema_info:
            return ''
        return schema_info.get('rid_field', '')

    def get_db_rid_family(self, schema: SchemaId) -> str:
        db_info = self.get_db_info(schema)
        if not db_info:
            return ''
        return db_info.get('rid_family', '')

    def get_db_mrid_table(self, schema: SchemaId) -> str:
        db_info = self.get_db_info(schema)
        if not db_info:
            return ''
        return db_info.get('mrid_table', '')

    def get_db_mrid_field(self, schema: SchemaId) -> str:
        db_info = self.get_db_info(schema)
        if not db_info:
            return ''
        return db_info.get('mrid_field', '')

    def get_schema_date_field(self, schema: SchemaId) -> str:
        db_info = self.get_db_info(schema)
        if not db_info:
            return ''
        return db_info.get('default_date_field', '')

    def get_rid_column(self, table: TableId) -> ColumnId:
        # RID column in the specified table (which may or may not exist)
        return table.column_id(self.get_schema_rid_field(table.schema_id()))

    def get_trid_column(self, table: TableId) -> ColumnId:
        # TRID column in the specified table (which may or may not exist)
        return table.column_id(
            self.get_schema_trid_field(table.schema_id()))

    def get_mrid_column_from_schema(self, schema: SchemaId) -> ColumnId:
        # MRID column in the MRID master table
        return schema.column_id(
            table=self.get_db_mrid_table(schema),
            column=self.get_db_mrid_field(schema))

    def get_mrid_column_from_table(self, table: TableId) -> ColumnId:
        # MRID column in the MRID master table
        return self.get_mrid_column_from_schema(table.schema_id())

    def get_linked_mrid_column(self, table: TableId) -> Optional[ColumnId]:
        """
        Returns either the MRID column in the schema containing the table
        specified, or one that can be linked to it automatically.
        """
        own_mrid = self.get_mrid_column_from_table(table)
        if own_mrid:
            return own_mrid
        # OK. So our table isn't from a database with an MRID table, but it
        # might be linked to one.
        this_schema = table.schema_id()
        first_schema = self.get_first_schema()
        if not first_schema or not self.talks_to_world(first_schema):
            return None
        if self.talks_to_world(this_schema) or self.can_communicate_directly(
                this_schema, first_schema):
            return self.get_mrid_column_from_schema(first_schema)

    def get_default_date_column(self, table: TableId) -> ColumnId:
        # Default date column (which may or may not exist)
        return table.column_id(
            self.get_schema_date_field(table.schema_id()))

    def does_db_schema_have_mrid(self, schema: SchemaId) -> bool:
        this_dbs_info = self.get_db_info(schema)
        if not this_dbs_info:
            return False
        return bool(
            this_dbs_info.get('mrid_table', None) and
            this_dbs_info.get('mrid_field', None)
        )

    @staticmethod
    def get_first_schema() -> SchemaId:
        if not settings.RESEARCH_DB_INFO:
            return SchemaId()
        first_dbs_info = settings.RESEARCH_DB_INFO[0]
        return SchemaId(db=first_dbs_info['database'],
                        schema=first_dbs_info['schema'])

    def talks_to_world(self, schema: SchemaId) -> bool:
        return self.does_db_schema_have_mrid(schema)

    def can_communicate_directly(self,
                                 schema1: SchemaId,
                                 schema2: SchemaId) -> bool:
        if schema1 == schema2:
            return True
        info1 = self.get_db_info(schema1)
        info2 = self.get_db_info(schema2)
        if not info1 or not info2:
            return False
        return bool(
            info1.get('rid_field', None) and info1.get('rid_family', None) and
            info2.get('rid_field', None) and info2.get('rid_family', None) and
            info2.get('rid_family', None) == info1.get('rid_family', None)
        )

    def is_db_schema_eligible_for_query_builder(self,
                                                schema: SchemaId) -> bool:
        first_schema = self.get_first_schema()
        if not schema or not first_schema:
            return False
        if schema == first_schema:
            # First one: always eligible
            return True
        return (
            (self.talks_to_world(first_schema) and
             self.talks_to_world(schema)) or
            self.can_communicate_directly(schema, first_schema)
        )

    @classmethod
    def _get_info_microsoft(cls, db_name: str,
                            schema_names: List[str]) -> SqlArgsTupleType:
        if not schema_names:
            raise ValueError("No schema_names specified (for SQL Server "
                             "database)")
        # SQL Server INFORMATION_SCHEMA.COLUMNS:
        # - https://msdn.microsoft.com/en-us/library/ms188348.aspx
        # Re fulltext indexes:
        # - http://stackoverflow.com/questions/16280918/how-to-find-full-text-indexing-on-database-in-sql-server-2008  # noqa
        # - sys.fulltext_indexes: https://msdn.microsoft.com/en-us/library/ms186903.aspx  # noqa
        # - sys.fulltext_catalogs: https://msdn.microsoft.com/en-us/library/ms188779.aspx  # noqa
        # - sys.fulltext_index_columns: https://msdn.microsoft.com/en-us/library/ms188335.aspx  # noqa
        schema_placeholder = ",".join(["?"] * len(schema_names))
        sql = translate_sql_qmark_to_percent("""
SELECT
    ? AS table_catalog,
    d.table_schema,
    d.table_name,
    d.column_name,
    d.is_nullable,
    d.column_type,
    d.column_comment,
    CASE WHEN COUNT(d.index_id) > 0 THEN 1 ELSE 0 END AS indexed,
    CASE WHEN COUNT(d.fulltext_index_object_id) > 0 THEN 1 ELSE 0 END AS indexed_fulltext
FROM (
    SELECT
        s.name AS table_schema,
        ta.name AS table_name,
        c.name AS column_name,
        c.is_nullable,
        UPPER(ty.name) + '(' + CONVERT(VARCHAR(100), c.max_length) + ')' AS column_type,
        CONVERT(VARCHAR(1000), x.value) AS column_comment, -- x.value is of type SQL_VARIANT
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
    AND ty.user_type_id = ty.system_type_id  -- restricts to system data types; eliminates 'sysname' type
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
        """.format(db_name=db_name,  # noqa
                   schema_placeholder=schema_placeholder))
        args = [db_name] + schema_names
        return sql, args

    @classmethod
    def _get_info_mysql(cls, db_and_schema_name: str) -> SqlArgsTupleType:
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
        #
        # ---------------------------------------------------------------------
        # Method B. Much faster, e.g. 0.35s for the same thing.
        # ---------------------------------------------------------------------
        # http://www.codeproject.com/Articles/33052/Visual-Representation-of-SQL-Joins  # noqa
        # (Note that EXISTS() above returns 0 or 1.)
        # The LEFT JOIN below will produce NULL values for the index
        # columns for non-indexed fields.
        # However, you can have more than one index on a column, in which
        # case the column appears in two rows.
        #
        # MySQL's INFORMATION_SCHEMA.COLUMNS:
        # - https://dev.mysql.com/doc/refman/5.7/en/tables-table.html
        sql = translate_sql_qmark_to_percent("""
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
        """)
        args = [db_and_schema_name]
        return sql, args

    @classmethod
    def _get_info_postgres(cls, schema_names: List[str]) -> SqlArgsTupleType:
        # A PostgreSQL connection is always to a single database.
        # http://stackoverflow.com/questions/10335561/use-database-name-command-in-postgresql  # noqa
        if not schema_names:
            raise ValueError("No schema_names specified (for PostgreSQL "
                             "database)")
        # http://dba.stackexchange.com/questions/75015
        # http://stackoverflow.com/questions/14713774
        # Note that creating a GIN index looks like:
        #       ALTER TABLE t ADD COLUMN tsv_mytext TSVECTOR;
        #       UPDATE t SET tsv_mytext = to_tsvector(mytext);
        #       CREATE INDEX idx_t_mytext_gin ON t USING GIN(tsv_mytext);
        schema_placeholder = ",".join(["?"] * len(schema_names))
        # PostgreSQL INFORMATION_SCHEMA.COLUMNS:
        # - https://www.postgresql.org/docs/9.1/static/infoschema-columns.html
        sql = translate_sql_qmark_to_percent("""
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
        """.format(schema_placeholder=schema_placeholder))
        args = schema_names
        return sql, args

    @classmethod
    def _get_infodictlist_for_db(
            cls, connection: BaseDatabaseWrapper, vendor: str, db_name: str,
            schema_name: str) -> List[Dict[str, Any]]:
        log.debug("Fetching/caching database structure (for database {}, "
                  "schema {})...".format(db_name, schema_name))
        if db_name is None:
            raise ValueError("Use '', not None, for a blank db_name")
        if schema_name is None:
            raise ValueError("Use '', not None, for a blank schema_name")
        if vendor == VENDOR_MICROSOFT:
            if not db_name:
                raise ValueError("No db_name specified; required for MSSQL")
            if not schema_name:
                raise ValueError("No schema_name specified; required for MSSQL")  # noqa
            sql, args = cls._get_info_microsoft(db_name, [schema_name])
        elif vendor == VENDOR_POSTGRESQL:
            if db_name:
                raise ValueError("db_name specified; must be '' for PostgreSQL")  # noqa
            if not schema_name:
                raise ValueError("No schema_name specified; required for PostgreSQL")  # noqa
            sql, args = cls._get_info_postgres([schema_name])
        elif vendor == VENDOR_MYSQL:
            if db_name:
                raise ValueError("db_name specified; must be '' for MySQL")
            if not schema_name:
                raise ValueError("No schema_name specified; required for MySQL")  # noqa
            sql, args = cls._get_info_mysql(db_and_schema_name=schema_name)
        else:
            raise ValueError(
                "Don't know how to get metadata for "
                "connection.vendor=='{}'".format(vendor))
        # We execute this one directly, rather than using the Query class,
        # since this is a system rather than a per-user query.
        cursor = connection.cursor()
        # log.debug("sql = {}, args = {}".format(sql, repr(args)))
        cursor.execute(sql, args)
        results = dictfetchall(cursor)  # list of OrderedDicts
        # log.debug("results = {}".format(repr(results)))
        log.debug("... done")
        return results
        # Re passing multiple values to SQL via args:
        # - Don't circumvent the parameter protection against SQL injection.
        # - Too much hassle to use Django's ORM model here, though that would
        #   also be possible.
        # - http://stackoverflow.com/questions/907806
        # - Similarly via SQLAlchemy reflection/inspection.

    @django_cache_function(timeout=None)
    # @lru_cache(maxsize=None)
    def get_infodictlist(self) -> List[Dict[str, Any]]:
        connection = self._connection()
        vendor = connection.vendor
        results = []
        for dbinfo in settings.RESEARCH_DB_INFO:
            db_name = dbinfo['database']
            schema_name = dbinfo['schema']
            results.extend(self._get_infodictlist_for_db(connection, vendor,
                                                         db_name, schema_name))
        if not results:
            log.warning("ResearchDatabaseInfo._get_infodictlist(): no results "
                        "for 'research' database - misconfigured?")
        return results

    @django_cache_function(timeout=None)
    # @lru_cache(maxsize=None)
    def get_colinfolist(self) -> List[ColumnInfo]:
        infodictlist = self.get_infodictlist()
        return [ColumnInfo(**d) for d in infodictlist]

    @django_cache_function(timeout=None)
    # @lru_cache(maxsize=None)
    def get_colinfolist_by_tables(self) -> OrderedDict:
        colinfolist = self.get_colinfolist()
        table_to_colinfolist = {}
        for c in colinfolist:
            table_id = c.table_id()
            if table_id not in table_to_colinfolist:
                table_to_colinfolist[table_id] = []
            table_to_colinfolist[table_id].append(c)
        return OrderedDict(sorted(table_to_colinfolist.items()))

    @django_cache_function(timeout=None)
    # @lru_cache(maxsize=None)
    def get_colinfolist_by_schema(self) -> Dict[SchemaId, List[ColumnInfo]]:
        colinfolist = self.get_colinfolist()
        schema_to_colinfolist = {}  # type: Dict[SchemaId, List[ColumnInfo]]
        for c in colinfolist:
            table_id = c.table_id()
            schema = table_id.schema_id()
            if schema not in schema_to_colinfolist:
                schema_to_colinfolist[schema] = []
            schema_to_colinfolist[schema].append(c)
        return OrderedDict(sorted(schema_to_colinfolist.items()))

    def tables_containing_field(self,
                                fieldname: str) -> List[TableId]:
        """
        Returns a list of (db, schema, table) tuples.
        We won't use a SELECT on INFORMATION_SCHEMA here, since we already
        have the information.
        """
        columns = self.get_colinfolist()
        results = []
        for column in columns:
            if column.column_name == fieldname:
                table_id = column.table_id()
                if table_id not in results:
                    results.append(table_id)
        return results

    def text_columns(self, table_id: TableId,
                     min_length: int = 1) -> List[ColumnInfo]:
        results = []
        for column in self.get_colinfolist():
            if column.table_id() != table_id:
                continue
            if not is_sql_column_type_textual(column.column_type,
                                              min_length):
                continue
            results.append(column)
        return results

    @django_cache_function(timeout=None)
    # @lru_cache(maxsize=1000)
    def all_columns(self, table_id: TableId) -> List[ColumnInfo]:
        results = []
        for column in self.get_colinfolist():
            if column.table_id() != table_id:
                continue
            results.append(column)
        return results

    def get_tsv(self) -> str:
        return dictlist_to_tsv(self.get_infodictlist())

    def get_excel(self) -> bytes:
        wb = Workbook()
        wb.remove_sheet(wb.active)  # remove the autocreated blank sheet
        schema_colinfolist_dict = self.get_colinfolist_by_schema()
        for schema, colinfolist in schema_colinfolist_dict.items():
            ws = wb.create_sheet(title=schema.identifier(self.grammar))
            ws.append([
                "table_catalog", "table_schema", "table_name", "column_name",
                "is_nullable", "column_type", "column_comment",
                "indexed", "indexed_fulltext",
                "basetype", "full_identifier"
            ])
            for c in colinfolist:  # type: ColumnInfo
                ws.append([
                    c.table_catalog, c.table_schema, c.table_name,
                    c.column_name, c.is_nullable, c.column_type,
                    c.column_comment, c.indexed, c.indexed_fulltext,
                    c.basetype(), c.column_id().identifier(self.grammar),
                ])
        return excel_to_bytes(wb)

    @django_cache_function(timeout=None)
    # @lru_cache(maxsize=None)
    def get_tables(self) -> List[TableId]:
        tables = set()
        for column in self.get_colinfolist():
            tables.add(column.table_id())
        return sorted(list(tables))

    @django_cache_function(timeout=None)
    # @lru_cache(maxsize=1000)
    def table_contains_rid(self, table: TableId):
        target_rid_column = self.get_rid_column(table)
        for column in self.get_colinfolist():
            if column.column_id() == target_rid_column:
                return True
        return False

    def table_contains(self, table: TableId, column: ColumnId):
        for c in self.all_columns(table):
            if c.column_id() == column:
                return True
        return False

    @django_cache_function(timeout=None)
    # @lru_cache(maxsize=None)
    def get_mrid_linkable_patient_tables(self) -> List[TableId]:
        eligible_tables = set()
        for table in self.get_tables():
            schema = table.schema_id()
            if not self.does_db_schema_have_mrid(schema):
                continue
            if self.table_contains_rid(table):
                eligible_tables.add(table)
        return sorted(list(eligible_tables))


research_database_info = ResearchDatabaseInfo()
