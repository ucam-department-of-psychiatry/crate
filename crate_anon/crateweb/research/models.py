#!/usr/bin/env python
# crate_anon/crateweb/research/models.py

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
from functools import lru_cache
import logging
# import os
from typing import Any, Dict, List, Generator, Iterable, Optional, Tuple, Type

from django.db import connections, models
from django.db.backends.base.base import BaseDatabaseWrapper
from django.db.models import QuerySet
from django.conf import settings
from django.http.request import HttpRequest
# from django.utils.functional import cached_property
from picklefield.fields import PickledObjectField

from crate_anon.common.sql_grammar import (
    DIALECT_MSSQL,
    DIALECT_POSTGRES,
    DIALECT_MYSQL,
)
from crate_anon.crateweb.core.dbfunc import (
    dictfetchall,
    escape_percent_for_python_dbapi,
    get_fieldnames_from_cursor,
    is_mysql_column_type_textual,
    translate_sql_qmark_to_percent,
    tsv_escape,
)
from crate_anon.crateweb.research.html_functions import (
    highlight_text,
    N_CSS_HIGHLIGHT_CLASSES,
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
# Debugging SQL
# =============================================================================

def debug_query() -> None:
    cursor = connections['research'].cursor()
    cursor.execute("SELECT 'debug'")


# =============================================================================
# Query highlighting class
# =============================================================================

HIGHLIGHT_FWD_REF = "Highlight"


class Highlight(models.Model):
    """
    Represents the highlighting of a query.
    """
    id = models.AutoField(primary_key=True)  # automatic
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    colour = models.PositiveSmallIntegerField(verbose_name="Colour number")
    text = models.CharField(max_length=255, verbose_name="Text to highlight")
    active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return "colour={}, text={}".format(self.colour, self.text)

    def get_safe_colour(self) -> int:
        if self.colour is None:
            return 0
        return min(self.colour, N_CSS_HIGHLIGHT_CLASSES - 1)

    @staticmethod
    def as_ordered_dict(highlight_list) -> Dict[int, List[HIGHLIGHT_FWD_REF]]:
        d = dict()
        for highlight in highlight_list:
            n = highlight.get_safe_colour()
            if n not in d:
                d[n] = []  # type: List[HIGHLIGHT_FWD_REF]
            d[n].append(highlight)
        return OrderedDict(sorted(d.items()))

    @staticmethod
    def get_active_highlights(request: HttpRequest) -> QuerySet:
        return Highlight.objects.filter(user=request.user, active=True)

    def activate(self) -> None:
        self.active = True
        self.save()

    def deactivate(self) -> None:
        self.active = False
        self.save()


# =============================================================================
# Query class
# =============================================================================

QUERY_FWD_REF = "Query"


class Query(models.Model):
    """
    Class to query the research database.
    """
    class Meta:
        app_label = "research"

    id = models.AutoField(primary_key=True)  # automatic
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    sql = models.TextField(verbose_name='SQL query')
    args = PickledObjectField(verbose_name='Pickled arguments',
                              null=True)
    # ... https://github.com/shrubberysoft/django-picklefield
    raw = models.BooleanField(
        default=False, verbose_name='SQL is raw, not parameter-substituted')
    qmark = models.BooleanField(
        default=True,
        verbose_name='Parameter-substituted SQL uses ?, not %s, '
        'as placeholders')
    active = models.BooleanField(default=True)  # see save() below
    created = models.DateTimeField(auto_now_add=True)
    deleted = models.BooleanField(
        default=False,
        verbose_name="Deleted from the user's perspective. "
                     "Audited queries are never properly deleted.")
    audited = models.BooleanField(default=False)

    def __str__(self) -> str:
        return "<Query id={}>".format(self.id)

    def save(self, *args, **kwargs) -> None:
        """
        Custom save method.
        Ensures that only one Query has active == True for a given user.
        """
        # http://stackoverflow.com/questions/1455126/unique-booleanfield-value-in-django  # noqa
        if self.active:
            Query.objects.filter(user=self.user, active=True)\
                         .update(active=False)
        super().save(*args, **kwargs)

    @staticmethod
    def get_active_query_or_none(request: HttpRequest) \
            -> Optional[QUERY_FWD_REF]:
        try:
            return Query.objects.get(user=request.user, active=True)
        except Query.DoesNotExist:
            return None

    @staticmethod
    def get_active_query_id_or_none(request: HttpRequest) -> Optional[int]:
        if not request.user.is_authenticated():
            return None
        try:
            query = Query.objects.get(user=request.user, active=True)
            return query.id
        except Query.DoesNotExist:
            return None

    def activate(self) -> None:
        self.active = True
        self.save()

    def mark_audited(self) -> None:
        if self.audited:
            return
        self.audited = True
        self.save()

    def mark_deleted(self) -> None:
        if self.deleted:
            log.debug("pointless)")
            return
        self.deleted = True
        self.active = False
        log.debug("about to save")
        self.save()
        log.debug("saved")

    def delete_if_permitted(self) -> None:
        """If a query has been audited, it isn't properly deleted."""
        if self.deleted:
            log.debug("already flagged as deleted")
            return
        if self.audited:
            log.debug("marking as deleted")
            self.mark_deleted()
        else:
            # actually delete
            log.debug("actually deleting")
            self.delete()

    def audit(self, count_only: bool = False, n_records: int = 0,
              failed: bool = False, fail_msg: str = "") -> None:
        a = QueryAudit(query=self,
                       count_only=count_only,
                       n_records=n_records,
                       failed=failed,
                       fail_msg=fail_msg)
        a.save()
        self.mark_audited()

    def get_original_sql(self) -> str:
        # noinspection PyTypeChecker
        return self.sql

    def get_sql_args_for_mysql(self) -> Tuple[str, Optional[List[Any]]]:
        """
        Get sql/args in a format suitable for MySQL, with %s placeholders,
        or as escaped raw SQL.
        """
        if self.raw:
            # noinspection PyTypeChecker
            sql = escape_percent_for_python_dbapi(self.sql)
            args = None
        else:
            if self.qmark:
                # noinspection PyTypeChecker
                sql = translate_sql_qmark_to_percent(self.sql)
            else:
                sql = self.sql
            args = self.args
        return sql, args

    def get_executed_cursor(self, sql_append_raw: str = None) -> Any:
        """
        Get cursor with a query executed
        """
        (sql, args) = self.get_sql_args_for_mysql()
        if sql_append_raw:
            sql += sql_append_raw
        cursor = connections['research'].cursor()
        if args:
            cursor.execute(sql, args)
        else:
            cursor.execute(sql)
        return cursor

    def gen_rows(self,
                 firstrow: int = 0,
                 lastrow: int = None) -> Generator[List[Any], None, None]:
        """
        Generate rows from the query.
        """
        if firstrow > 0 or lastrow is not None:
            sql_append_raw = " LIMIT {f},{n}".format(
                f=firstrow,
                n=(lastrow - firstrow + 1),
            )
            # zero-indexed; http://dev.mysql.com/doc/refman/5.0/en/select.html
        else:
            sql_append_raw = None
        cursor = self.get_executed_cursor(sql_append_raw)
        row = cursor.fetchone()
        while row is not None:
            yield row
            row = cursor.fetchone()

    def make_tsv(self) -> str:
        cursor = self.get_executed_cursor()
        fieldnames = get_fieldnames_from_cursor(cursor)
        tsv = "\t".join([tsv_escape(f) for f in fieldnames]) + "\n"
        row = cursor.fetchone()
        while row is not None:
            tsv += "\t".join([tsv_escape(x) for x in row]) + "\n"
            row = cursor.fetchone()
        return tsv

    def dictfetchall(self) -> List[Dict[str, Any]]:
        """Generates all results as a list of OrderedDicts."""
        cursor = self.get_executed_cursor()
        return dictfetchall(cursor)

    def add_highlight(self, text: str, colour: int = 0) -> None:
        h = Highlight(text=text, colour=colour)
        self.highlight_set.add(h)

    def get_highlights_as_dict(self) -> Dict[int, Iterable[Highlight]]:
        d = OrderedDict()
        for n in range(N_CSS_HIGHLIGHT_CLASSES):
            d[n] = Highlight.objects.filter(query_id=self.id, colour=n)
        return d

    def get_highlight_descriptions(self) -> List[str]:
        d = self.get_highlights_as_dict()
        desc = []
        for n in range(N_CSS_HIGHLIGHT_CLASSES):
            if d[n]:
                # noinspection PyTypeChecker
                desc.append(", ".join(highlight_text(h.text, n) for h in d[n]))
        return desc


# =============================================================================
# Query auditing class
# =============================================================================

class QueryAudit(models.Model):
    """
    Audit log for a query.
    """
    id = models.AutoField(primary_key=True)  # automatic
    query = models.ForeignKey('Query')
    when = models.DateTimeField(auto_now_add=True)
    count_only = models.BooleanField(default=False)
    n_records = models.IntegerField(default=0)
    # ... not PositiveIntegerField; SQL Server gives -1, for example
    failed = models.BooleanField(default=False)
    fail_msg = models.TextField()

    def __str__(self):
        return "<QueryAudit id={}>".format(self.id)


# =============================================================================
# Information about the research database
# =============================================================================

SQLTYPES_INTEGER = [
    "INT", "INTEGER",
    "TINYINT", "SMALLINT", "MEDIUMINT", "BIGINT",
    "BIT", "BOOL", "BOOLEAN",
]
SQLTYPES_FLOAT = [
    "DOUBLE", "FLOAT", "DEC", "DECIMAL",
]
SQLTYPES_TEXT = [
    "CHAR", "VARCHAR", "NVARCHAR",
    "TINYTEXT", "TEXT", "NTEXT", "MEDIUMTEXT", "LONGTEXT",
]
SQLTYPES_WITH_DATE = [
    "DATE", "DATETIME", "TIMESTAMP",
]
# SQLTYPES_BINARY = [
#     "BINARY", "BLOB", "IMAGE", "LONGBLOB", "VARBINARY",
# ]


class ColumnInfo(object):
    # See also querybuilder.js
    DATATYPE_INTEGER = "int"
    DATATYPE_FLOAT = "float"
    DATATYPE_DATE = "date"
    DATATYPE_STRING = "string"
    DATATYPE_STRING_FULLTEXT = "string_fulltext"
    DATATYPE_UNKNOWN = "unknown"
    STRING_TYPES = [DATATYPE_STRING, DATATYPE_STRING_FULLTEXT]

    def __init__(self, **kwargs) -> None:
        self.table_catalog = kwargs.pop('table_catalog')
        self.table_schema = kwargs.pop('table_schema')
        self.table_name = kwargs.pop('table_name')
        self.column_name = kwargs.pop('column_name')
        self.is_nullable = kwargs.pop('is_nullable')
        self.column_type = kwargs.pop('column_type')
        self.column_comment = kwargs.pop('column_comment')
        self.indexed = kwargs.pop('indexed')
        self.indexed_fulltext = kwargs.pop('indexed_fulltext')

    @property
    def basetype(self) -> str:
        return self.column_type.split("(")[0].upper()

    @property
    def querybuilder_type(self) -> str:
        """
        Returns a string that is defined in querybuilder.js
        """
        basetype = self.basetype
        if basetype in SQLTYPES_FLOAT:
            return self.DATATYPE_FLOAT
        if basetype in SQLTYPES_WITH_DATE:
            return self.DATATYPE_DATE
        if basetype in SQLTYPES_TEXT:
            if self.indexed_fulltext:
                return self.DATATYPE_STRING_FULLTEXT
            else:
                return self.DATATYPE_STRING
        if basetype in SQLTYPES_INTEGER:
            return self.DATATYPE_INTEGER
        return self.DATATYPE_UNKNOWN


def get_researchdb_databases_schemas() -> List[Tuple[str, str]]:
    return [(x['database'], x['schema']) for x in settings.RESEARCH_DB_INFO]


def get_default_database() -> str:
    if settings.RESEARCH_DB_DIALECT == DIALECT_MSSQL:
        return settings.DATABASES['research']['NAME']
    elif settings.RESEARCH_DB_DIALECT == DIALECT_POSTGRES:
        return ''
    elif settings.RESEARCH_DB_DIALECT == DIALECT_MYSQL:
        return ''
    else:
        raise ValueError("Bad settings.RESEARCH_DB_DIALECT")


def get_default_schema() -> str:
    if settings.RESEARCH_DB_DIALECT == DIALECT_MSSQL:
        return 'dbo'
    elif settings.RESEARCH_DB_DIALECT == DIALECT_POSTGRES:
        return 'public'
    elif settings.RESEARCH_DB_DIALECT == DIALECT_MYSQL:
        return settings.DATABASES['research']['NAME']
    else:
        raise ValueError("Bad settings.RESEARCH_DB_DIALECT")


def get_db_info(db: str, schema: str) -> Optional[Dict[str, Any]]:
    db = db or get_default_database()
    schema = schema or get_default_schema()
    infolist = [x for x in settings.RESEARCH_DB_INFO
                if x['database'] == db and x['schema'] == schema]
    if not infolist:
        log.warning("No such database/schema: {}.{}".format(db, schema))
        return None
    return infolist[0]


@lru_cache(maxsize=None)
def get_schema_trid_field(db: str, schema: str) -> str:
    db_info = get_db_info(db, schema)
    if not db_info:
        return ''
    return db_info.get('trid_field', '')


@lru_cache(maxsize=None)
def get_schema_rid_field(db: str, schema: str) -> str:
    schema_info = get_db_info(db, schema)
    if not schema_info:
        return ''
    return schema_info.get('rid_field', '')


@lru_cache(maxsize=None)
def get_db_rid_family(db: str, schema: str) -> str:
    db_info = get_db_info(db, schema)
    if not db_info:
        return ''
    return db_info.get('rid_family', '')


@lru_cache(maxsize=None)
def get_db_mrid_table(db: str, schema: str) -> str:
    db_info = get_db_info(db, schema)
    if not db_info:
        return ''
    return db_info.get('mrid_table', '')


@lru_cache(maxsize=None)
def get_db_mrid_field(db: str, schema: str) -> str:
    db_info = get_db_info(db, schema)
    if not db_info:
        return ''
    return db_info.get('mrid_field', '')


@lru_cache(maxsize=None)
def is_db_schema_eligible_for_query_builder(db: str, schema: str) -> bool:
    this_dbs_info = get_db_info(db, schema)
    if not this_dbs_info:
        return False
    first_dbs_info = settings.RESEARCH_DB_INFO[0]
    first_dbs_name = first_dbs_info['database']
    first_dbs_schema = first_dbs_info['schema']
    if db == first_dbs_name and schema == first_dbs_schema:
        # First one: always eligible
        return True
    first_db_talks_to_world = bool(
        first_dbs_info.get('mrid_table', None) and
        first_dbs_info.get('mrid_field', None)
    )
    this_db_talks_to_world = bool(
        this_dbs_info.get('mrid_table', None) and
        this_dbs_info.get('mrid_field', None)
    )
    can_communicate_directly = bool(
        first_dbs_info.get('rid_field', None) and
        this_dbs_info.get('rid_field', None) and
        this_dbs_info.get('rid_family', None) and
        this_dbs_info.get('rid_family', None) ==
        first_dbs_info.get('rid_family', None)
    )
    return (
        (first_db_talks_to_world and this_db_talks_to_world) or
        can_communicate_directly
    )


class ResearchDatabaseInfo(object):
    """
    Fetches schema information from the research database.
    Class only exists to be able to use @cached_property.
    ... replaced by lru_cache
    """

    @classmethod
    def connection(cls) -> BaseDatabaseWrapper:
        return connections['research']

    @classmethod
    def uses_database_level(cls) -> bool:
        return cls._offers_db_above_schema(cls.connection())

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

    @classmethod
    def get_info_microsoft(cls, db_name: str,
                           schema_names: List[str]) -> Tuple[str, List[Any]]:
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
    def get_info_mysql(cls, db_and_schema_name: str) -> Tuple[str, List[Any]]:
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
    def get_info_postgres(cls, schema_names: List[str]) -> Tuple[str, List[Any]]:  # noqa
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
    def get_infodictlist_for_db(
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
            sql, args = cls.get_info_microsoft(db_name, [schema_name])
        elif vendor == VENDOR_POSTGRESQL:
            if db_name:
                raise ValueError("db_name specified; must be '' for PostgreSQL")  # noqa
            if not schema_name:
                raise ValueError("No schema_name specified; required for PostgreSQL")  # noqa
            sql, args = cls.get_info_postgres([schema_name])
        elif vendor == VENDOR_MYSQL:
            if db_name:
                raise ValueError("db_name specified; must be '' for MySQL")
            if not schema_name:
                raise ValueError("No schema_name specified; required for MySQL")  # noqa
            sql, args = cls.get_info_mysql(db_and_schema_name=schema_name)
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

    @lru_cache(maxsize=None)
    def get_infodictlist(self) -> List[Dict[str, Any]]:
        connection = self.connection()
        vendor = connection.vendor
        results = []
        for dbinfo in settings.RESEARCH_DB_INFO:
            db_name = dbinfo['database']
            schema_name = dbinfo['schema']
            results.extend(self.get_infodictlist_for_db(connection, vendor,
                                                        db_name, schema_name))
        if not results:
            log.warning("ResearchDatabaseInfo.get_infodictlist(): no results "
                        "for 'research' database - misconfigured?")
        return results

    @lru_cache(maxsize=None)
    def get_colinfolist(self) -> List[ColumnInfo]:
        infodictlist = self.get_infodictlist()
        return [ColumnInfo(**d) for d in infodictlist]

    @lru_cache(maxsize=None)
    def get_infodictlist_by_tables(self) \
            -> List[Tuple[str, str, str, List[Dict[str, Any]]]]:
        idl = self.get_infodictlist()
        db_schema_table_idl = []
        for database, schema, table in sorted(set(
                (x['table_catalog'], x['table_schema'], x['table_name'])
                for x in idl)):
            log.debug("database={}, schema={}, table={}".format(
                database, schema, table))
            dictlist = [i for i in idl
                        if i['table_catalog'] == database and
                        i['table_schema'] == schema and
                        i['table_name'] == table]
            db_schema_table_idl.append((database, schema, table, dictlist))
        # log.debug(repr(schema_table_idl))
        return db_schema_table_idl

    @lru_cache(maxsize=1000)
    def tables_containing_field(self,
                                fieldname: str) -> List[Tuple[str, str, str]]:
        """
        Returns a list of (db, schema, table) tuples.
        We won't use a SELECT on INFORMATION_SCHEMA here, since we already
        have the information.
        """
        idl = self.get_infodictlist()
        results = []
        for infodict in idl:
            if infodict['column_name'] == fieldname:
                newtuple = (
                    infodict['table_catalog'],
                    infodict['table_schema'],
                    infodict['table_name']
                )
                if newtuple not in results:
                    results.append(newtuple)
        return results

    @lru_cache(maxsize=1000)
    def text_columns(self,
                     db: str,
                     schema: str,
                     table: str,
                     min_length: int = 1) -> List[Tuple[str, bool]]:
        """
        Returns list of (column_name, indexed_fulltext) pairs.
        """
        results = []
        use_db = self.uses_database_level()
        for rowdict in self.get_infodictlist():
            if use_db and rowdict['table_catalog'] != db:
                continue
            if rowdict['table_schema'] != schema:
                continue
            if rowdict['table_name'] != table:
                continue
            column_type = rowdict['column_type']
            if not is_mysql_column_type_textual(column_type, min_length):
                continue
            column_name = rowdict['column_name']
            indexed_fulltext = rowdict['indexed_fulltext']
            results.append((column_name, indexed_fulltext))
        return results


research_database_info = ResearchDatabaseInfo()


# =============================================================================
# Lookup class for secret RID-to-PID conversion
# =============================================================================

class PidLookupRouter(object):
    # https://docs.djangoproject.com/en/1.8/topics/db/multi-db/
    # https://newcircle.com/s/post/1242/django_multiple_database_support
    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def db_for_read(self, model: Type[models.Model], **hints) -> Optional[str]:
        """
        read model PidLookup -> look at database secret
        """
        # log.debug("PidLookupRouter: {}".format(model._meta.model_name))
        # if model._meta.model_name == PidLookup._meta.model_name:
        if model == PidLookup:
            return 'secret'
        return None


class PidLookup(models.Model):
    """
    Lookup class for secret RID-to-PID conversion.
    Uses the 'secret' database connection.

    Use as e.g. Lookup(pid=XXX)
    """
    pid = models.PositiveIntegerField(
        primary_key=True,
        db_column=settings.SECRET_MAP['PID_FIELD'])
    mpid = models.PositiveIntegerField(
        db_column=settings.SECRET_MAP['MASTER_PID_FIELD'])
    rid = models.CharField(
        db_column=settings.SECRET_MAP['RID_FIELD'],
        max_length=settings.SECRET_MAP['MAX_RID_LENGTH'])
    mrid = models.CharField(
        db_column=settings.SECRET_MAP['MASTER_RID_FIELD'],
        max_length=settings.SECRET_MAP['MAX_RID_LENGTH'])
    trid = models.PositiveIntegerField(
        db_column=settings.SECRET_MAP['TRID_FIELD'])

    class Meta:
        managed = False
        db_table = settings.SECRET_MAP['TABLENAME']


def get_pid_lookup(trid: int = None,
                   rid: str = None,
                   mrid: str = None) -> PidLookup:
    if trid is not None:
        lookup = PidLookup.objects.get(trid=trid)
    elif rid is not None:
        lookup = PidLookup.objects.get(rid=rid)
    elif mrid is not None:
        lookup = PidLookup.objects.get(mrid=mrid)
    else:
        raise ValueError("no input")
    return lookup


def get_mpid(trid: int = None,
             rid: str = None,
             mrid: str = None) -> int:
    lookup = get_pid_lookup(trid=trid, rid=rid, mrid=mrid)
    # noinspection PyTypeChecker
    return lookup.mpid


def get_pid(trid: int = None,
            rid: str = None,
            mrid: str = None) -> int:
    lookup = get_pid_lookup(trid=trid, rid=rid, mrid=mrid)
    # noinspection PyTypeChecker
    return lookup.pid
