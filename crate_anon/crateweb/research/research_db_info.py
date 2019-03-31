#!/usr/bin/env python

"""
crate_anon/crateweb/research/research_db_info.py

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

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

**Represents information about the structure of our research database(s).**

"""

from collections import OrderedDict
# from functools import lru_cache
import logging
import re
from typing import Any, Dict, List, Optional

from cardinal_pythonlib.dbfunc import dictfetchall
from cardinal_pythonlib.django.django_constants import ConnectionVendors
from cardinal_pythonlib.django.function_cache import django_cache_function
from cardinal_pythonlib.excel import excel_to_bytes
from cardinal_pythonlib.json.serialize import METHOD_NO_ARGS, register_for_json
from cardinal_pythonlib.logs import BraceStyleAdapter
from cardinal_pythonlib.reprfunc import auto_repr
from cardinal_pythonlib.sql.sql_grammar import SqlGrammar
from cardinal_pythonlib.sqlalchemy.dialect import SqlaDialectName
from cardinal_pythonlib.sqlalchemy.schema import (
    MSSQL_DEFAULT_SCHEMA,
    POSTGRES_DEFAULT_SCHEMA,
)
from cardinal_pythonlib.tsv import dictlist_to_tsv
from django.db import connections
from django.db.backends.base.base import BaseDatabaseWrapper
from django.conf import settings
from openpyxl import Workbook

from crate_anon.common.constants import RUNNING_WITHOUT_CONFIG
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
from crate_anon.crateweb.config.constants import ResearchDbInfoKeys

log = BraceStyleAdapter(logging.getLogger(__name__))


# =============================================================================
# Constants
# =============================================================================

RESEARCH_DB_CONNECTION_NAME = 'research'

SUPPORTED_DIALECTS = [
    SqlaDialectName.MSSQL,
    SqlaDialectName.MYSQL,
    # SqlaDialectName.POSTGRES,  # no grammar yet
]


class PatientFieldPythonTypes(object):
    """
    Represents Python types for each type of patient ID field.
    """
    PID = int
    MPID = int
    RID = str
    MRID = str
    TRID = int


# =============================================================================
# Information about the research database
# =============================================================================

class ColumnInfo(object):
    """
    Represents information about a database column, reflected from the
    database.

    See also ``querybuilder.js``.
    """

    def __init__(self, **kwargs) -> None:
        self.table_catalog = kwargs.pop('table_catalog')  # type: str
        self.table_schema = kwargs.pop('table_schema')  # type: str
        self.table_name = kwargs.pop('table_name')  # type: str
        self.column_name = kwargs.pop('column_name')  # type: str
        self.is_nullable = bool(kwargs.pop('is_nullable'))
        self.column_type = kwargs.pop('column_type')  # type: str
        self.column_comment = kwargs.pop('column_comment')  # type: str
        self.indexed = bool(kwargs.pop('indexed'))
        self.indexed_fulltext = bool(kwargs.pop('indexed_fulltext'))

    @property
    def basetype(self) -> str:
        """
        Returns the SQL base type, such as ``VARCHAR``.
        """
        return self.column_type.split("(")[0].upper()

    @property
    def querybuilder_type(self) -> str:
        """
        Returns a string that is defined in ``querybuilder.js`` and that
        defines our field type, like ``"int"`` or ``"date"``. See source.
        """
        basetype = self.basetype
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

    @property
    def column_id(self) -> ColumnId:
        """
        Returns a :class:`crate_anon.common.sql.ColumnId` describing this
        column.
        """
        return ColumnId(db=self.table_catalog,
                        schema=self.table_schema,
                        table=self.table_name,
                        column=self.column_name)

    @property
    def table_id(self) -> TableId:
        """
        Returns a :class:`crate_anon.common.sql.TableId` describing this
        column's table.
        """
        return TableId(db=self.table_catalog,
                       schema=self.table_schema,
                       table=self.table_name)

    def __repr__(self) -> str:
        return auto_repr(self, sort_attrs=False)

    def __str__(self) -> str:
        return str(self.column_id)


class SingleResearchDatabase(object):
    """
    Represents, and adds information to, a single entry from the
    ``RESEARCH_DB_INFO`` list: that is, a research database. (It's a list
    because it's ordered.)
    """
    def __init__(self,
                 index: int,
                 grammar: SqlGrammar,
                 rdb_info: "ResearchDatabaseInfo",
                 connection: BaseDatabaseWrapper,
                 vendor: str) -> None:
        """
        Instantiates, reading database information as follows:

        - the relevant dictionary is ``settings.RESEARCH_DB_INFO[index]``
        - the keys to that dictionary are in
          :class:`crate_anon.crateweb.config.constants.ResearchDbInfoKeys`

        Args:
            index:
                Python zero-based index to ``settings.RESEARCH_DB_INFO``
            grammar:
                a :class:`cardinal_pythonlib.sql.sql_grammar.SqlGrammar`,
                for the SQL dialect we're using
            rdb_info:
                a :class:`ResearchDatabaseInfo`, describing the structure of
                the research database
            connection:
                a :class:`django.db.backends.base.base.BaseDatabaseWrapper`,
                i.e. a Django database connection
            vendor:
                the Django database vendor name; see e.g.
                https://docs.djangoproject.com/en/2.1/ref/models/options/
        """
        assert 0 <= index <= len(settings.RESEARCH_DB_INFO)
        infodict = settings.RESEARCH_DB_INFO[index]

        self.connection = connection
        self.vendor = vendor

        self.index = index
        self.is_first_db = index == 0
        self.grammar = grammar
        self.rdb_info = rdb_info

        try:
            self.name = infodict[ResearchDbInfoKeys.NAME]  # type: str
            self.description = infodict[ResearchDbInfoKeys.DESCRIPTION]  # type: str  # noqa
            self.database = infodict[ResearchDbInfoKeys.DATABASE]  # type: str
            self.schema_name = infodict[ResearchDbInfoKeys.SCHEMA]  # type: str
            self.trid_field = infodict[ResearchDbInfoKeys.TRID_FIELD]  # type: str  # noqa
            self.rid_field = infodict[ResearchDbInfoKeys.RID_FIELD]  # type: str  # noqa
            self.rid_family = infodict[ResearchDbInfoKeys.RID_FAMILY]  # type: int  # noqa
            self.mrid_table = infodict[ResearchDbInfoKeys.MRID_TABLE]  # type: str  # noqa
            self.mrid_field = infodict[ResearchDbInfoKeys.MRID_FIELD]  # type: str  # noqa
        except KeyError as e:
            raise KeyError(
                f"Key {e} is missing from settings.RESEARCH_DB_INFO "
                f"for this dict: {infodict!r}")

        assert isinstance(self.name, str) and self.name  # no blanks
        assert re.match(r'^\w+$', self.name), (
            f"Database name {self.name!r} should contain only "
            f"alphanumeric/underscore characters"
        )
        assert isinstance(self.description, str) and self.description  # no blanks  # noqa

        assert isinstance(self.database, str)  # may be blank
        assert isinstance(self.schema_name, str) and self.schema_name  # no blanks  # noqa

        assert isinstance(self.trid_field, str)  # may be blank
        assert isinstance(self.rid_field, str) and self.rid_field  # no blanks
        assert isinstance(self.rid_family, int)  # may be blank
        assert self.rid_family > 0  # positive integers only
        assert isinstance(self.mrid_table, str)  # may be blank
        assert isinstance(self.mrid_field, str)  # may be blank

        self.pid_pseudo_field = infodict.get(
            ResearchDbInfoKeys.PID_PSEUDO_FIELD, '')  # type: str
        self.mpid_pseudo_field = infodict.get(
            ResearchDbInfoKeys.MPID_PSEUDO_FIELD, '')  # type: str
        assert isinstance(self.pid_pseudo_field, str)  # may be blank unless it's a lookup DB  # noqa
        assert isinstance(self.mpid_pseudo_field, str)  # may be blank unless it's a lookup DB  # noqa

        self.pid_description = infodict.get(
            ResearchDbInfoKeys.PID_DESCRIPTION,
            'Patient ID (PID) for database ' + self.description
        )  # type: str
        self.mpid_description = infodict.get(
            ResearchDbInfoKeys.MPID_DESCRIPTION,
            'Master patient ID (MPID)'
        )  # type: str
        self.rid_description = infodict.get(
            ResearchDbInfoKeys.RID_DESCRIPTION,
            'Research ID (RID) for database ' + self.description
        )  # type: str
        self.mrid_description = infodict.get(
            ResearchDbInfoKeys.MRID_DESCRIPTION,
            'Master research ID (MRID)'
        )  # type: str
        self.trid_description = infodict.get(
            ResearchDbInfoKeys.TRID_DESCRIPTION,
            'Transient research ID (TRID) for database ' + self.description
        )  # type: str
        assert isinstance(self.pid_description, str)
        assert isinstance(self.mpid_description, str)
        assert isinstance(self.rid_description, str)
        assert isinstance(self.mrid_description, str)
        assert isinstance(self.trid_description, str)

        self.secret_lookup_db = infodict.get(
            ResearchDbInfoKeys.SECRET_LOOKUP_DB, '')
        assert isinstance(self.secret_lookup_db, str)
        if self.secret_lookup_db:
            assert self.secret_lookup_db in settings.DATABASES, (
                f"Research database named {self.name!r} in "
                f"settings.RESEARCH_DB_INFO has an invalid "
                f"secret_lookup_db: {self.secret_lookup_db!r}"
            )
            assert re.match(r'^\w+$', self.pid_pseudo_field), (
                f"The research database named {self.name!r} should have a "
                f"pid_pseudo_field containing only alphanumeric/underscore "
                f"characters (it's {self.pid_pseudo_field!r})"
            )
            assert re.match(r'^\w+$', self.mpid_pseudo_field), (
                f"The research database named {self.name!r} should have a "
                f"mpid_pseudo_field containing only alphanumeric/underscore "
                f"characters (it's {self.mpid_pseudo_field!r})"
            )

        self.date_fields_by_table = infodict.get(
            ResearchDbInfoKeys.DATE_FIELDS_BY_TABLE, {}
        )  # type: Dict[str, str]
        assert isinstance(self.date_fields_by_table, dict)
        for k, v in self.date_fields_by_table.items():
            assert isinstance(k, str) and k, (
                f"Bad key {k!r} for {ResearchDbInfoKeys.DATE_FIELDS_BY_TABLE} "
                f"for database named {self.name!r}")
            assert isinstance(v, str) and v, (
                f"Bad value {v!r} for "
                f"{ResearchDbInfoKeys.DATE_FIELDS_BY_TABLE} "
                f"for database named {self.name!r}")

        self.default_date_fields = infodict.get(
            ResearchDbInfoKeys.DEFAULT_DATE_FIELDS, []
        )  # type: List[str]
        assert isinstance(self.default_date_fields, list)
        for v in self.default_date_fields:
            assert isinstance(v, str) and v, (
                f"Bad item {v!r} for {ResearchDbInfoKeys.DEFAULT_DATE_FIELDS} "
                f"for database named {self.name!r}")

        # Field for when the record was last updated in db
        self.update_date_field = infodict.get(
            ResearchDbInfoKeys.UPDATE_DATE_FIELD, ""
        )
        assert isinstance(self.update_date_field, str)

        self.schema_id = SchemaId(self.database, self.schema_name)
        assert self.schema_id

        # Now discover the schema
        self._schema_infodictlist = None  # type: List[Dict[str, Any]]
        self._colinfolist = None  # type: List[ColumnInfo]

    @property
    def schema_infodictlist(self) -> List[Dict[str, Any]]:
        """
        Discovers the schema. Returns the results of
        :meth:`get_schema_infodictlist` for our connection and vendor.
        Implements caching.
        """
        if self._schema_infodictlist is None:
            self._schema_infodictlist = self.get_schema_infodictlist(
                self.connection, self.vendor)
        return self._schema_infodictlist

    @property
    def colinfolist(self) -> List[ColumnInfo]:
        """
        Returns a list of :class:`ColumnInfo` objects for our research
        database.
        """
        if self._colinfolist is None:
            self._colinfolist = [ColumnInfo(**d)
                                 for d in self.schema_infodictlist]
        return self._colinfolist

    @property
    def schema_identifier(self) -> str:
        """
        Returns the SQL schema identifier.
        """
        return self.schema_id.identifier(self.grammar)

    @property
    def eligible_for_query_builder(self) -> bool:
        """
        Is this database eligible to participate in the CRATE assisted query
        builder?

        This is ``True`` if it's the first database, or if it can link directly
        to the first database (shares a common RID), or if it and the first
        database share a common MRID.
        """
        if self.is_first_db:
            # First one: always eligible
            return True
        first_db = self.rdb_info.first_dbinfo
        return (
            (first_db.talks_to_world and self.talks_to_world) or
            self.can_communicate_directly(first_db)
        )

    @property
    def talks_to_world(self) -> bool:
        """
        Does this database "talk to the world", i.e. have an MRID?
        """
        return self.has_mrid

    @property
    def has_mrid(self) -> bool:
        """
        Does this database have a defined master research ID (MRID), i.e. a
        table with one row per patient and one column that is the MRID?
        """
        return bool(self.mrid_table and self.mrid_field)

    def can_communicate_directly(self,
                                 other: "SingleResearchDatabase") -> bool:
        """
        Can this database "talk" (link, join) to another?

        Args:
            other: the other :class:`SingleResearchDatabase`

        Returns:
            ``True`` if they are the same database or share a common RID type

        """
        if self.schema_id == other.schema_id:
            return True
        return self.rid_family == other.rid_family

    def get_default_date_field(self, table_id: TableId) -> Optional[ColumnId]:
        """
        Gets the default date column for the specified table, or ``None`` if
        none exists.

        Args:
            table_id: a :class:`crate_anon.common.sql.TableId`

        Returns:
            a :class:`crate_anon.common.sql.ColumnId`, or ``None``
        """
        if table_id.table in self.date_fields_by_table:
            # We've been told about a specific date column for this table.
            column_id = ColumnId(
                db=table_id.db,
                schema=table_id.schema,
                table=table_id.table,
                column=self.date_fields_by_table[table_id.table]
            )
            # Now, does it actually exist?
            if self.column_present(column_id):
                # Yes.
                return column_id
            # No.
        for datecolname in self.default_date_fields:
            column_id = ColumnId(
                db=table_id.db,
                schema=table_id.schema,
                table=table_id.table,
                column=datecolname
            )
            if self.column_present(column_id):
                return column_id
        return None

    def column_present(self, column_id: ColumnId) -> bool:
        """
        Is the named column present in this database?

        Args:
            column_id: a :class:`crate_anon.common.sql.ColumnId`
        """
        for ci in self.colinfolist:
            if ci.column_id == column_id:
                return True
        return False

    # -------------------------------------------------------------------------
    # Fetching schema info from the database
    # -------------------------------------------------------------------------

    @classmethod
    def _schema_query_microsoft(
            cls,
            db_name: str,
            schema_names: List[str]) -> SqlArgsTupleType:
        """
        Returns a query to fetche the database structure from an SQL Server
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
        
          - http://stackoverflow.com/questions/16280918/how-to-find-full-text-indexing-on-database-in-sql-server-2008
          - ``sys.fulltext_indexes``: https://msdn.microsoft.com/en-us/library/ms186903.aspx
          - ``sys.fulltext_catalogs``: https://msdn.microsoft.com/en-us/library/ms188779.aspx
          - ``sys.fulltext_index_columns``: https://msdn.microsoft.com/en-us/library/ms188335.aspx

        """  # noqa
        if not schema_names:
            raise ValueError("No schema_names specified (for SQL Server "
                             "database)")
        schema_placeholder = ",".join(["?"] * len(schema_names))
        sql = translate_sql_qmark_to_percent(f"""
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
        """)  # noqa
        args = [db_name] + schema_names
        return sql, args

    @classmethod
    def _schema_query_mysql(cls, db_and_schema_name: str) -> SqlArgsTupleType:
        """
        Returns a query to fetche the database structure from a MySQL database.

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
        # http://www.codeproject.com/Articles/33052/Visual-Representation-of-SQL-Joins  # noqa
        # (Note that EXISTS() above returns 0 or 1.)
        # The LEFT JOIN below will produce NULL values for the index
        # columns for non-indexed fields.
        # However, you can have more than one index on a column, in which
        # case the column appears in two rows.
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
    def _schema_query_postgres(cls,
                               schema_names: List[str]) -> SqlArgsTupleType:
        """
        Returns a query to fetche the database structure from an SQL Server
        database.

        The columns returned are as expected by
        :func:`get_schema_infodictlist`.

        Args:
            schema_names: a list of schema names within the database

        Returns:
            tuple: ``sql, args``
            
        Notes:
            
        - A PostgreSQL connection is always to a single database; see
          http://stackoverflow.com/questions/10335561/use-database-name-command-in-postgresql
        - http://dba.stackexchange.com/questions/75015
        - http://stackoverflow.com/questions/14713774
        - Note that creating a GIN index looks like:
        
          .. code-block:: sql
          
            ALTER TABLE t ADD COLUMN tsv_mytext TSVECTOR;
            UPDATE t SET tsv_mytext = to_tsvector(mytext);
            CREATE INDEX idx_t_mytext_gin ON t USING GIN(tsv_mytext);
            
        - PostgreSQL ``INFORMATION_SCHEMA.COLUMNS``: see
          https://www.postgresql.org/docs/9.1/static/infoschema-columns.html

        """  # noqa
        if not schema_names:
            raise ValueError("No schema_names specified (for PostgreSQL "
                             "database)")
        schema_placeholder = ",".join(["?"] * len(schema_names))
        sql = translate_sql_qmark_to_percent(f"""
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
        """)
        args = schema_names
        return sql, args

    def get_schema_infodictlist(self,
                                connection: BaseDatabaseWrapper,
                                vendor: str,
                                debug: bool = False) -> List[Dict[str, Any]]:
        """
        Fetch structure information for a specific database, by asking the
        database.

        Args:
            connection:
                a :class:`django.db.backends.base.base.BaseDatabaseWrapper`,
                i.e. a Django database connection
            vendor:
                the Django database vendor name; see e.g.
                https://docs.djangoproject.com/en/2.1/ref/models/options/
            debug:
                be verbose to the log?

        Returns:
            A list of dictionaries, each mapping column names to values.
            The dictionaries are suitable for use as ``**kwargs`` to
            :class:`ColumnInfo`.

        """
        db_name = self.database
        schema_name = self.schema_name
        log.debug(f"Fetching/caching database structure (for database "
                  f"{db_name!r}, schema {schema_name!r})...")
        # The db/schema names are guaranteed to be strings by __init__().
        if vendor == ConnectionVendors.MICROSOFT:
            if not db_name:
                raise ValueError("No db_name specified; required for MSSQL")
            if not schema_name:
                raise ValueError("No schema_name specified; required for MSSQL")  # noqa
            sql, args = self._schema_query_microsoft(db_name, [schema_name])
        elif vendor == ConnectionVendors.POSTGRESQL:
            if db_name:
                raise ValueError("db_name specified; must be '' for PostgreSQL")  # noqa
            if not schema_name:
                raise ValueError("No schema_name specified; required for PostgreSQL")  # noqa
            sql, args = self._schema_query_postgres([schema_name])
        elif vendor == ConnectionVendors.MYSQL:
            if db_name:
                raise ValueError("db_name specified; must be '' for MySQL")
            if not schema_name:
                raise ValueError("No schema_name specified; required for MySQL")  # noqa
            sql, args = self._schema_query_mysql(db_and_schema_name=schema_name)  # noqa
        else:
            raise ValueError(
                f"Don't know how to get metadata for "
                f"connection.vendor=='{vendor}'")
        # We execute this one directly, rather than using the Query class,
        # since this is a system rather than a per-user query.
        cursor = connection.cursor()
        if debug:
            log.debug(f"sql = {sql}, args = {repr(args)}")
        cursor.execute(sql, args)
        results = dictfetchall(cursor)  # list of OrderedDicts
        if debug:
            log.debug(f"results = {results!r}")
        log.debug("... done")
        if not results:
            log.warning(
                f"SingleResearchDatabase.get_schema_infodictlist(): no "
                f"results for database/schema {self.schema_identifier!r} "
                f"database - misconfigured?")
        return results
        # Re passing multiple values to SQL via args:
        # - Don't circumvent the parameter protection against SQL injection.
        # - Too much hassle to use Django's ORM model here, though that would
        #   also be possible.
        # - http://stackoverflow.com/questions/907806
        # - Similarly via SQLAlchemy reflection/inspection.


@register_for_json(method=METHOD_NO_ARGS)
class ResearchDatabaseInfo(object):
    """
    Fetches schema information from the research databases. There can be
    several, and this class represents the whole collection.

    Notes:

    - Class primarily exists to be able to use ``@cached_property``.

      - ... replaced by ``@lru_cache``
      - ... replaced by ``@django_cache_function``
    """
    # We fetch the dialect at first request; this enables us to import the
    # class without Django configured.

    def __init__(self) -> None:
        self.dbinfolist = []  # type: List[SingleResearchDatabase]

        if RUNNING_WITHOUT_CONFIG:
            self.dialect = ""
            self.grammar = None
            self.dbinfo_for_contact_lookup = None

        else:
            self.dialect = settings.RESEARCH_DB_DIALECT
            assert self.dialect in SUPPORTED_DIALECTS, (
                f"Unsupported dialect: {self.dialect!r}"
            )

            self.grammar = make_grammar(self.dialect)  # not expensive

            connection = self._connection()
            vendor = connection.vendor

            for index in range(len(settings.RESEARCH_DB_INFO)):
                self.dbinfolist.append(SingleResearchDatabase(
                    index=index,
                    grammar=self.grammar,
                    rdb_info=self,
                    connection=connection,
                    vendor=vendor
                ))
            assert len(self.dbinfolist) > 0, (
                "No research databases configured in RESEARCH_DB_INFO"
            )
            names = [x.name for x in self.dbinfolist]
            assert len(names) == len(set(names)), (
                f"Duplicate database names in {names!r}"
            )

            try:
                self.dbinfo_for_contact_lookup = self.get_dbinfo_by_name(
                    settings.RESEARCH_DB_FOR_CONTACT_LOOKUP)
            except ValueError:
                raise ValueError(
                    f"In your settings, RESEARCH_DB_FOR_CONTACT_LOOKUP "
                    f"specifies {settings.RESEARCH_DB_FOR_CONTACT_LOOKUP!r} "
                    f"but there is no database with that name in "
                    f"RESEARCH_DB_INFO")
            assert self.dbinfo_for_contact_lookup.secret_lookup_db, (
                f"Research database {self.dbinfo_for_contact_lookup.name!r} "
                f"is set as your RESEARCH_DB_FOR_CONTACT_LOOKUP but has no "
                f"{ResearchDbInfoKeys.SECRET_LOOKUP_DB!r} attribute"
            )

    # -------------------------------------------------------------------------
    # Classmethods, staticmethods
    # -------------------------------------------------------------------------

    @classmethod
    def _connection(cls) -> BaseDatabaseWrapper:
        """
        Returns the Django connection to the research database(s), from
        ``connections[RESEARCH_DB_CONNECTION_NAME]``, meaning
        ``connections['research']``.

        **This must be a read-only connection, enforced by the database.
        Researchers will be allowed to execute unrestricted SQL via this
        connection.**

        """
        return connections[RESEARCH_DB_CONNECTION_NAME]

    @classmethod
    def uses_database_level(cls) -> bool:
        """
        Does the database simultaneously offer a "database" level above its
        "schema" level?
        """
        return cls._offers_db_above_schema(cls._connection())

    @classmethod
    def format_db_schema(cls, db: str, schema: str) -> str:
        if cls.uses_database_level():
            return f"{db}.{schema}"
        else:
            return schema

    @staticmethod
    def _offers_db_above_schema(connection: BaseDatabaseWrapper) -> bool:
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
        return connection.vendor in [ConnectionVendors.MICROSOFT]

    # -------------------------------------------------------------------------
    # Whole-database/schema information
    # -------------------------------------------------------------------------

    @property
    def single_research_db(self) -> bool:
        """
        Do we have only a single research database?
        """
        return len(self.dbinfolist) == 1

    @property
    def single_research_db_with_secret_map(self) -> bool:
        """
        Do we have only one database that has an associated secret lookup
        database to patient IDs?
        """
        return len(self.dbs_with_secret_map) == 1

    @property
    def dbs_with_secret_map(self) -> List[SingleResearchDatabase]:
        """
        Which of our databases has an associated secret lookup database to
        patient IDs?

        Returns:
            a list of :class:`SingleResearchDatabase` objects
        """
        return [db for db in self.dbinfolist if db.secret_lookup_db]

    def _get_dbinfo_by_index(self, index: int) -> SingleResearchDatabase:
        """
        Returns a :class:`SingleResearchDatabase` by its zero-based index, and
        assert if the index is bad.

        Args:
            index: a zero-based index

        Returns:
            a :class:`SingleResearchDatabase`

        Raises:
            :exc:`IndexError` if the index was bad
        """
        return self.dbinfolist[index]

    def get_dbinfo_by_name(self, name: str) -> SingleResearchDatabase:
        """
        Returns the research database whose name (from
        ``settings.RESEARCH_DB_INFO``) is ``name``.

        Args:
            name: the name of a database, as per ``settings.RESEARCH_DB_INFO``

        Returns:
            a :class:`SingleResearchDatabase`

        Raises:
            :exc:`ValueError` if none is found

        """
        try:
            return next(x for x in self.dbinfolist if x.name == name)
        except StopIteration:
            raise ValueError(f"No research database named {name!r}")

    def get_dbinfo_by_schema_id(self,
                                schema_id: SchemaId) -> SingleResearchDatabase:
        """
        Returns the first database representing the specified schema.

        Args:
            schema_id: a :class:`crate_anon.common.sql.SchemaId`

        Returns:
            a :class:`SingleResearchDatabase`

        Raises:
            :exc:`StopIteration` if none is found

        - This is probably a functional duplicate of
          :func:`_get_db_info`!
        """
        return next(x for x in self.dbinfolist if x.schema_id == schema_id)

    @property
    def first_dbinfo(self) -> SingleResearchDatabase:
        """
        Returns the first :class:`SingleResearchDatabase` that we know about.
        """
        return self._get_dbinfo_by_index(0)

    @property
    def first_dbinfo_with_secret_map(self) -> Optional[SingleResearchDatabase]:
        """
        Returns the first :class:`SingleResearchDatabase` that has a secret map
        (an associated secret lookup database to patient IDs), or ``None`` if
        there isn't one.
        """
        dbs = self.dbs_with_secret_map
        if len(dbs) == 0:
            return None
        return dbs[0]

    @property
    def researchdb_schemas(self) -> List[SchemaId]:
        """
        Returns all :class:`crate_anon.common.sql.SchemaId` values for our
        databases (one per database).
        """
        return [x.schema_id for x in self.dbinfolist]

    def get_default_database_name(self) -> str:
        """
        Returns the default "database name" for our dialect.

        - For Microsoft SQL Server, this is
          ``settings.DATABASES['research']['NAME']``
        - For MySQL, this is blank
        - For PostgreSQL, this is blank
        """
        dialect = self.dialect
        if dialect == SqlaDialectName.MSSQL:
            return settings.DATABASES[RESEARCH_DB_CONNECTION_NAME]['NAME']
        elif dialect == SqlaDialectName.POSTGRES:
            return ''
        elif dialect == SqlaDialectName.MYSQL:
            return ''
        else:
            raise ValueError("Bad settings.RESEARCH_DB_DIALECT")

    def get_default_schema_name(self) -> str:
        """
        Returns the default "schema name" for our dialect.

        - For Microsoft SQL Server, this is ``'dbo'``
        - For PostgreSQL, this is ``'public'``
        - For MySQL, this is ``settings.DATABASES['research']['NAME']``

        """
        dialect = self.dialect
        if dialect == SqlaDialectName.MSSQL:
            return MSSQL_DEFAULT_SCHEMA
        elif dialect == SqlaDialectName.POSTGRES:
            return POSTGRES_DEFAULT_SCHEMA
        elif dialect == SqlaDialectName.MYSQL:
            return settings.DATABASES[RESEARCH_DB_CONNECTION_NAME]['NAME']
        else:
            raise ValueError("Bad settings.RESEARCH_DB_DIALECT")

    def _get_db_info(self, schema_id: SchemaId) -> SingleResearchDatabase:
        """
        Returns the first database representing the specified schema.

        Args:
            schema_id: a :class:`crate_anon.common.sql.SchemaId`

        Returns:
            a :class:`SingleResearchDatabase`

        Raises:
            :exc:`ValueError` if none is found

        - This is probably a functional duplicate of
          :func:`get_dbinfo_by_schema_id`!

        """
        try:
            return next(d for d in self.dbinfolist if d.schema_id == schema_id)
        except StopIteration:
            raise ValueError(f"No such database/schema: "
                             f"{schema_id.identifier(self.grammar)!r}")

    # -------------------------------------------------------------------------
    # Database-wide fields and descriptions
    # -------------------------------------------------------------------------

    def get_rid_column(self, table: TableId) -> ColumnId:
        """
        Returns the RID column in the specified table (which may or may not
        exist).

        Args:
            table: a :class:`crate_anon.common.sql.TableId`

        Returns:
            a :class:`crate_anon.common.sql.ColumnId`, which may be blank

        """
        dbinfo = self._get_db_info(table.schema_id)
        return table.column_id(dbinfo.rid_field)

    def get_trid_column(self, table: TableId) -> ColumnId:
        """
        Returns the TRID column in the specified table (which may or may not
        exist).

        Args:
            table: a :class:`crate_anon.common.sql.TableId`

        Returns:
            a :class:`crate_anon.common.sql.ColumnId`, which may be blank

        """
        dbinfo = self._get_db_info(table.schema_id)
        return table.column_id(dbinfo.trid_field)

    def get_mrid_column_from_schema(self, schema: SchemaId) -> ColumnId:
        """
        Returns the MRID column in the MRID master table for a given
        schema/database.

        Args:
            schema: a :class:`crate_anon.common.sql.SchemaId`

        Returns:
            a :class:`crate_anon.common.sql.ColumnId`, which may be blank

        """
        dbinfo = self._get_db_info(schema)
        return schema.column_id(table=dbinfo.mrid_table,
                                column=dbinfo.mrid_field)

    def get_mrid_column_from_table(self, table: TableId) -> ColumnId:
        """
        Returns the MRID column in the specified table (which may or may not
        exist).

        Args:
            table: a :class:`crate_anon.common.sql.TableId`; this should be the
                MRID master table

        Returns:
            a :class:`crate_anon.common.sql.ColumnId`, which may be blank

        """
        return self.get_mrid_column_from_schema(table.schema_id)

    def get_linked_mrid_column(self, table: TableId) -> Optional[ColumnId]:
        """
        Returns either (a) the MRID column in the schema containing the table
        specified, or (b) one that can be linked to it automatically.

        Args:
            table: a :class:`crate_anon.common.sql.TableId`

        Returns:
            a :class:`crate_anon.common.sql.ColumnId`, or ``None``

        """
        mrid_in_same_db = self.get_mrid_column_from_table(table)
        if mrid_in_same_db:
            return mrid_in_same_db
        # OK. So our table isn't from a database with an MRID table, but it
        # might be linked to one.
        table_db = self._get_db_info(table.schema_id)
        first_db = self.first_dbinfo
        if not first_db.talks_to_world:
            return None
        if (table_db.talks_to_world or
                table_db.can_communicate_directly(first_db)):
            return self.get_mrid_column_from_schema(first_db.schema_id)

    def get_default_date_column(self, table: TableId) -> Optional[ColumnId]:
        """
        Returns the default date column in the specified table (which may or
        may not exist).

        Args:
            table: a :class:`crate_anon.common.sql.TableId`

        Returns:
            a :class:`crate_anon.common.sql.ColumnId`, which may be blank

        """
        dbinfo = self._get_db_info(table.schema_id)
        return dbinfo.get_default_date_field(table)

    # -------------------------------------------------------------------------
    # Table/column information
    # -------------------------------------------------------------------------

    @django_cache_function(timeout=None)
    def get_schema_infodictlist(self) -> List[Dict[str, Any]]:
        """
        Get details of all columns in all research databases.

        Returns:
            list: across all databases, of all dictionaries provided by their
            :meth:`SingleResearchDatabase.get_schema_infodictlist` function
        """
        results = []  # type: List[Dict[str, Any]]
        for dbinfo in self.dbinfolist:
            results.extend(dbinfo.schema_infodictlist)
        return results

    @django_cache_function(timeout=None)
    def get_colinfolist(self) -> List[ColumnInfo]:
        """
        Get details of all columns in all research databases.

        Returns:
            list: across all databases, of :class:`ColumnInfo` objects
        """
        colinfolist = []  # type: List[ColumnInfo]
        for dbi in self.dbinfolist:
            colinfolist.extend(dbi.colinfolist)
        return colinfolist

    @django_cache_function(timeout=None)
    def get_colinfolist_by_tables(self) -> Dict[TableId, List[ColumnInfo]]:
        """
        Get details of all columns in all research databases, by table.

        Returns:
            OrderedDict: across all databases, ``{table_id: columns}`` where
            ``table_id`` is a :class:`crate_anon.common.sql.TableId` and
            ``columns`` is a list of :class:`ColumnInfo` objects
        """
        colinfolist = self.get_colinfolist()
        table_to_colinfolist = {}  # type: Dict[TableId, List[ColumnInfo]]
        for c in colinfolist:
            table_id = c.table_id
            if table_id not in table_to_colinfolist:
                table_to_colinfolist[table_id] = []
            table_to_colinfolist[table_id].append(c)
        # noinspection PyTypeChecker
        return OrderedDict(sorted(table_to_colinfolist.items()))

    @django_cache_function(timeout=None)
    def get_colinfolist_by_schema(self) -> Dict[SchemaId, List[ColumnInfo]]:
        """
        Get details of all columns in all research databases, by schema.

        Returns:
            OrderedDict: across all databases, ``{schema_id: columns}`` where
            ``schema_id`` is a :class:`crate_anon.common.sql.SchemaId` and
            ``columns`` is a list of :class:`ColumnInfo` objects
        """
        colinfolist = self.get_colinfolist()
        schema_to_colinfolist = {}  # type: Dict[SchemaId, List[ColumnInfo]]
        for c in colinfolist:
            table_id = c.table_id
            schema = table_id.schema_id
            if schema not in schema_to_colinfolist:
                schema_to_colinfolist[schema] = []
            schema_to_colinfolist[schema].append(c)
        # noinspection PyTypeChecker
        return OrderedDict(sorted(schema_to_colinfolist.items()))

    def tables_containing_field(self, fieldname: str) -> List[TableId]:
        """
        Returns all tables containing the column (field) with the specified
        name.

        Args:
            fieldname: field (column) name

        Returns:
            a list of :class:`crate_anon.common.sql.TableId` objects

        - We won't use a ``SELECT`` on ``INFORMATION_SCHEMA`` here, since we
          already have the information.

        """
        columns = self.get_colinfolist()
        results = []
        for column in columns:
            if column.column_name == fieldname:
                table_id = column.table_id
                if table_id not in results:
                    results.append(table_id)
        return results

    def text_columns(self, table_id: TableId,
                     min_length: int = 1) -> List[ColumnInfo]:
        """
        Returns all text columns from the specified table.

        Args:
            table_id: a :class:`crate_anon.common.sql.TableId`
            min_length: the minimum SQL text length to include the column

        Returns:
            a list of :class:`crate_anon.common.sql.ColumnInfo` objects

        """
        results = []
        for column in self.get_colinfolist():
            if column.table_id != table_id:
                continue
            if not is_sql_column_type_textual(column.column_type,
                                              min_length):
                # log.debug("Skipping {!r}", column)
                continue
            results.append(column)
        # log.debug("text_columns for {} with min_length={}: [{}]", table_id,
        #           min_length, ", ".join(str(x) for x in results))
        return results

    @django_cache_function(timeout=None)
    def all_columns(self, table_id: TableId) -> List[ColumnInfo]:
        """
        Returns all columns from the specified table.

        Args:
            table_id: a :class:`crate_anon.common.sql.TableId`

        Returns:
            a list of :class:`crate_anon.common.sql.ColumnInfo` objects

        """
        results = []
        for column in self.get_colinfolist():
            if column.table_id != table_id:
                continue
            results.append(column)
        return results

    def get_tsv(self) -> str:
        """
        Returns a tab-separated value (TSV) file detailing of all columns in
        all research databases.

        Returns:
            str: TSV

        """
        return dictlist_to_tsv(self.get_schema_infodictlist())

    def get_excel(self) -> bytes:
        """
        Returns an XLSX (Excel) file detailing of all columns in all research
        databases.

        Returns:
            bytes: binary XLSX file

        """
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
                    c.basetype, c.column_id.identifier(self.grammar),
                ])
        return excel_to_bytes(wb)

    @django_cache_function(timeout=None)
    def get_tables(self) -> List[TableId]:
        """
        Returns all tables in the research database(s).

        Returns:
            a list of :class:`crate_anon.common.sql.TableId` objects
        """
        tables = set()
        for column in self.get_colinfolist():
            tables.add(column.table_id)
        return sorted(list(tables))

    @django_cache_function(timeout=None)
    def table_contains_rid(self, table_id: TableId) -> bool:
        """
        Does the specified table contain a research ID (RID)?

        Args:
            table_id: a :class:`crate_anon.common.sql.TableId`
        """
        target_rid_column = self.get_rid_column(table_id)
        for column in self.get_colinfolist():
            if column.column_id == target_rid_column:
                return True
        return False

    def table_contains(self, table_id: TableId, column_id: ColumnId) -> bool:
        """
        Does the specified table contain the specified column?

        Args:
            table_id: a :class:`crate_anon.common.sql.TableId`
            column_id: a :class:`crate_anon.common.sql.ColumnId`
        """
        for c in self.all_columns(table_id):
            if c.column_id == column_id:
                return True
        return False

    @django_cache_function(timeout=None)
    def get_mrid_linkable_patient_tables(self) -> List[TableId]:
        """
        Returns all tables in the research database(s) that are linkable on
        MRID (i.e. that contain a RID and live in a database with a RID-to-MRID
        lookup table).

        Returns:
            a list of :class:`crate_anon.common.sql.TableId` objects
        """
        eligible_tables = set()
        for table in self.get_tables():
            dbinfo = self._get_db_info(table.schema_id)
            if not dbinfo.has_mrid:
                continue
            if self.table_contains_rid(table):
                eligible_tables.add(table)
        return sorted(list(eligible_tables))


research_database_info = ResearchDatabaseInfo()
