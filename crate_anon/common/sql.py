#!/usr/bin/env python

"""
crate_anon/common/sql.py

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

**Low-level SQL manipulation functions.**

"""

from collections import OrderedDict
import functools
import logging
import re
from typing import Any, Dict, Iterable, List, Tuple, Union

from cardinal_pythonlib.json.serialize import (
    METHOD_PROVIDES_INIT_KWARGS,
    METHOD_STRIP_UNDERSCORE,
    register_for_json,
)
from cardinal_pythonlib.lists import unique_list
from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from cardinal_pythonlib.reprfunc import mapped_repr_stripping_underscores
from cardinal_pythonlib.sizeformatter import sizeof_fmt
from cardinal_pythonlib.sql.literals import (
    sql_date_literal,
    sql_string_literal,
)
from cardinal_pythonlib.sql.sql_grammar import SqlGrammar, text_from_parsed
from cardinal_pythonlib.sql.sql_grammar_factory import (
    make_grammar,
    mysql_grammar,
)
from cardinal_pythonlib.sqlalchemy.core_query import count_star
from cardinal_pythonlib.sqlalchemy.dialect import SqlaDialectName
from cardinal_pythonlib.sqlalchemy.schema import column_creation_ddl
from cardinal_pythonlib.timing import MultiTimerContext, timer
from pyparsing import ParseResults
from sqlalchemy import inspect
from sqlalchemy.dialects.mssql.base import MS_2012_VERSION
from sqlalchemy.engine.base import Engine
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.orm.session import Session
from sqlalchemy.schema import Column, Table

from crate_anon.common.stringfunc import get_spec_match_regex

log = logging.getLogger(__name__)

# =============================================================================
# Types
# =============================================================================

SqlArgsTupleType = Tuple[str, List[Any]]


# =============================================================================
# Constants
# =============================================================================

TIMING_COMMIT = "commit"

SQL_OPS_VALUE_UNNECESSARY = ['IS NULL', 'IS NOT NULL']
SQL_OPS_MULTIPLE_VALUES = ['IN', 'NOT IN']

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

# Must match querybuilder.js:
QB_DATATYPE_INTEGER = "int"
QB_DATATYPE_FLOAT = "float"
QB_DATATYPE_DATE = "date"
QB_DATATYPE_STRING = "string"
QB_DATATYPE_STRING_FULLTEXT = "string_fulltext"
QB_DATATYPE_UNKNOWN = "unknown"
QB_STRING_TYPES = [QB_DATATYPE_STRING, QB_DATATYPE_STRING_FULLTEXT]

COLTYPE_WITH_ONE_INTEGER_REGEX = re.compile(r"^([A-z]+)\((-?\d+)\)$")
# ... start, group(alphabetical), literal (, group(optional_minus_sign digits),
# literal ), end


# def combine_db_schema_table(db: Optional[str],
#                             schema: Optional[str],
#                             table: str) -> str:
#     # ANSI SQL: http://www.contrib.andrew.cmu.edu/~shadow/sql/sql1992.txt
#     # <table name>, <qualified name>
#     if not table:
#         raise ValueError("Missing table supplied to combine_db_schema_table")
#     return ".".join(x for x in [db, schema, table] if x)


# =============================================================================
# SQL elements: identifiers
# =============================================================================

@register_for_json(method=METHOD_STRIP_UNDERSCORE)
@functools.total_ordering
class SchemaId(object):
    """
    Represents a database schema. This is a bit complex:

    - In SQL Server, schemas live within databases. Tables can be referred to
      as ``table``, ``schema.table``, or ``database.schema.table``.
    
      - https://docs.microsoft.com/en-us/dotnet/framework/data/adonet/sql/ownership-and-user-schema-separation-in-sql-server
      - The default schema is named ``dbo``.
      
    - In PostgreSQL, schemas live within databases. Tables can be referred to
      as ``table``, ``schema.table``, or ``database.schema.table``.
    
      - https://www.postgresql.org/docs/current/static/ddl-schemas.html
      - The default schema is named ``public``.

    - In MySQL, "database" and "schema" are synonymous. Tables can be referred
      to as ``table`` or ``database.table`` (= ``schema.table``). 
      
      - https://stackoverflow.com/questions/11618277/difference-between-schema-database-in-mysql

    """  # noqa
    def __init__(self, db: str = '', schema: str = '') -> None:
        """
        Args:
            db: database name
            schema: schema name
        """
        assert "." not in db, (
            f"Bad database name ({db!r}); can't include '.'"
        )
        assert "." not in schema, (
            f"Bad schema name ({schema!r}); can't include '.'"
        )
        self._db = db
        self._schema = schema

    @property
    def schema_tag(self) -> str:
        """
        String suitable for encoding the SchemaId e.g. in a single HTML form.
        Takes the format ``database.schema``.
        
        The :func:`__init__` function has already checked the assumption of no
        ``'.'`` characters in either part.
        """
        return f"{self._db}.{self._schema}"

    @classmethod
    def from_schema_tag(cls, tag: str) -> 'SchemaId':
        """
        Returns a :class:`SchemaId` from a tag of the form ``db.schema``.
        """
        parts = tag.split(".")
        assert len(parts) == 2, f"Bad schema tag {tag!r}"
        db, schema = parts
        return SchemaId(db, schema)

    def __bool__(self) -> bool:
        """
        Returns:
            is there a named schema?
        """
        return bool(self._schema)

    def __eq__(self, other: 'SchemaId') -> bool:
        return (  # ordering is for speed
            self._schema == other._schema and
            self._db == other._db
        )

    def __lt__(self, other: 'SchemaId') -> bool:
        return (
            (self._db, self._schema) <
            (other._db, other._schema)
        )

    def __hash__(self) -> int:
        return hash(str(self))

    def identifier(self, grammar: SqlGrammar) -> str:
        """
        Returns an SQL identifier for this schema using the specified SQL
        grammar, quoting it if need be.
        
        Args:
            grammar: :class:`cardinal_pythonlib.sql.sql_grammar.SqlGrammar`
        """
        return make_identifier(grammar,
                               database=self._db,
                               schema=self._schema)

    def table_id(self, table: str) -> 'TableId':
        """
        Returns a :class:`TableId` combining this schema and the specified
        table.
        
        Args:
            table: name of the table 
        """
        return TableId(db=self._db, schema=self._schema, table=table)

    def column_id(self, table: str, column: str) -> 'ColumnId':
        """
        Returns a :class:`ColumnId` combining this schema and the specified
        table/column.

        Args:
            table: name of the table
            column: name of the column 
        """
        return ColumnId(db=self._db, schema=self._schema,
                        table=table, column=column)

    @property
    def db(self) -> str:
        """
        Returns the database part.
        """
        return self._db

    @property
    def schema(self) -> str:
        """
        Returns the schema part.
        """
        return self._schema

    def __str__(self) -> str:
        return self.identifier(mysql_grammar)  # specific one unimportant

    def __repr__(self) -> str:
        return mapped_repr_stripping_underscores(
            self, ['_db', '_schema'])


@register_for_json(method=METHOD_STRIP_UNDERSCORE)
@functools.total_ordering
class TableId(object):
    """
    Represents a database table.
    """
    def __init__(self, db: str = '', schema: str = '',
                 table: str = '') -> None:
        """
        Args:
            db: database name 
            schema: schema name
            table: table name
        """
        self._db = db
        self._schema = schema
        self._table = table

    def __bool__(self) -> bool:
        return bool(self._table)

    def __eq__(self, other: 'TableId') -> bool:
        return (  # ordering is for speed
            self._table == other._table and
            self._schema == other._schema and
            self._db == other._db
        )

    def __lt__(self, other: 'TableId') -> bool:
        return (
            (self._db, self._schema, self._table) <
            (other._db, other._schema, other._table)
        )

    def __hash__(self) -> int:
        return hash(str(self))

    def identifier(self, grammar: SqlGrammar) -> str:
        """
        Returns an SQL identifier for this table using the specified SQL
        grammar, quoting it if need be.

        Args:
            grammar: :class:`cardinal_pythonlib.sql.sql_grammar.SqlGrammar`
        """
        return make_identifier(grammar,
                               database=self._db,
                               schema=self._schema,
                               table=self._table)

    @property
    def schema_id(self) -> SchemaId:
        """
        Returns a :class:`SchemaId` for the schema of our table.
        """
        return SchemaId(db=self._db, schema=self._schema)

    def column_id(self, column: str) -> 'ColumnId':
        """
        Returns a :class:`ColumnId` combining this table and the specified
        column.

        Args:
            column: name of the column 
        """
        return ColumnId(db=self._db, schema=self._schema,
                        table=self._table, column=column)

    def database_schema_part(self, grammar: SqlGrammar) -> str:
        """
        Returns an SQL identifier for this table's database/schema (without the
        table part) using the specified SQL grammar, quoting it if need be.

        Args:
            grammar: :class:`cardinal_pythonlib.sql.sql_grammar.SqlGrammar`
        """
        return make_identifier(grammar,
                               database=self._db,
                               schema=self._schema)

    def table_part(self, grammar: SqlGrammar) -> str:
        """
        Returns an SQL identifier for this table's table name (only) using the
        specified SQL grammar, quoting it if need be.

        Args:
            grammar: :class:`cardinal_pythonlib.sql.sql_grammar.SqlGrammar`
        """
        return make_identifier(grammar, table=self._table)

    @property
    def db(self) -> str:
        """
        Returns the database part.
        """
        return self._db

    @property
    def schema(self) -> str:
        """
        Returns the schema part.
        """
        return self._schema

    @property
    def table(self) -> str:
        """
        Returns the table part.
        """
        return self._table

    def __str__(self) -> str:
        return self.identifier(mysql_grammar)  # specific one unimportant

    def __repr__(self) -> str:
        return mapped_repr_stripping_underscores(
            self, ['_db', '_schema', '_table'])


@register_for_json(method=METHOD_STRIP_UNDERSCORE)
@functools.total_ordering
class ColumnId(object):
    """
    Represents a database column.
    """
    def __init__(self, db: str = '', schema: str = '',
                 table: str = '', column: str = '') -> None:
        """
        Args:
            db: database name
            schema: schema name
            table: table name
            column: column name
        """
        self._db = db
        self._schema = schema
        self._table = table
        self._column = column

    def __bool__(self) -> bool:
        return bool(self._column)

    def __eq__(self, other: 'ColumnId') -> bool:
        return (
            self._column == other._column and
            self._table == other._table and
            self._schema == other._schema and
            self._db == other._db
        )

    def __lt__(self, other: 'ColumnId') -> bool:
        return (
            (self._db, self._schema, self._table, self._column) <
            (other._db, other._schema, other._table, other._column)
        )

    @property
    def is_valid(self) -> bool:
        """
        Do we know about a table and a column, at least?
        """
        return bool(self._table and self._column)  # the minimum

    def identifier(self, grammar: SqlGrammar) -> str:
        return make_identifier(grammar,
                               database=self._db,
                               schema=self._schema,
                               table=self._table,
                               column=self._column)

    @property
    def db(self) -> str:
        """
        Returns the database part.
        """
        return self._db

    @property
    def schema(self) -> str:
        """
        Returns the schema part.
        """
        return self._schema

    @property
    def table(self) -> str:
        """
        Returns the table part.
        """
        return self._table

    @property
    def column(self) -> str:
        """
        Returns the column part.
        """
        return self._column

    @property
    def schema_id(self) -> SchemaId:
        """
        Returns a :class:`SchemaId` for the schema of our column.
        """
        return SchemaId(db=self._db, schema=self._schema)

    @property
    def table_id(self) -> TableId:
        """
        Returns a :class:`TableId` for our table.
        """
        return TableId(db=self._db, schema=self._schema, table=self._table)

    @property
    def has_table_and_column(self) -> bool:
        """
        Do we know about a table and a column?
        """
        return bool(self._table and self._column)

    def __str__(self) -> str:
        return self.identifier(mysql_grammar)  # specific one unimportant

    def __repr__(self) -> str:
        return mapped_repr_stripping_underscores(
            self, ['_db', '_schema', '_table', '_column'])

    # def html(self, grammar: SqlGrammar, bold_column: bool = True) -> str:
    #     components = [
    #         html.escape(grammar.quote_identifier_if_required(x))
    #         for x in [self._db, self._schema, self._table, self._column]
    #         if x]
    #     if not components:
    #         return ''
    #     if bold_column:
    #         components[-1] = f"<b>{components[-1]}</b>"
    #     return ".".join(components)


def split_db_schema_table(db_schema_table: str) -> TableId:
    """
    Converts a simple SQL-style identifier string into a :class:`TableId`.

    Args:
        db_schema_table:
            one of: ``database.schema.table``, ``schema.table``, ``table``

    Returns:
        a :class:`TableId`

    Raises:
        :exc:`ValueError` if the input is bad

    """
    components = db_schema_table.split('.')
    if len(components) == 3:  # db.schema.table
        d, s, t = components[0], components[1], components[2]
    elif len(components) == 2:  # schema.table
        d, s, t = '', components[0], components[1]
    elif len(components) == 1:  # table
        d, s, t = '', '', components[0]
    else:
        raise ValueError(f"Bad db_schema_table: {db_schema_table}")
    return TableId(db=d, schema=s, table=t)


def split_db_schema_table_column(db_schema_table_col: str) -> ColumnId:
    """
    Converts a simple SQL-style identifier string into a :class:`ColumnId`.

    Args:
        db_schema_table_col:
            one of: ``database.schema.table.column``, ``schema.table.column``,
            ``table.column``, ``column``

    Returns:
        a :class:`ColumnId`

    Raises:
        :exc:`ValueError` if the input is bad

    """
    components = db_schema_table_col.split('.')
    if len(components) == 4:  # db.schema.table.column
        d, s, t, c = components[0], components[1], components[2], components[3]
    elif len(components) == 3:  # schema.table.column
        d, s, t, c = '', components[0], components[1], components[2]
    elif len(components) == 2:  # table.column
        d, s, t, c = '', '', components[0], components[1]
    elif len(components) == 1:  # column
        d, s, t, c = '', '', '', components[0]
    else:
        raise ValueError(f"Bad db_schema_table_col: {db_schema_table_col}")
    return ColumnId(db=d, schema=s, table=t, column=c)


def columns_to_table_column_hierarchy(
        columns: List[ColumnId],
        sort: bool = True) -> List[Tuple[TableId, List[ColumnId]]]:
    """
    Converts a list of column IDs
    Args:
        columns: list of :class:`ColumnId` objects
        sort: sort by table, and column within table?

    Returns:
        a list of tuples, each ``table, columns``, where ``table`` is a
        :class:`TableId` and ``columns`` is a list of :class:`ColumnId`

    """
    tables = unique_list(c.table_id for c in columns)
    if sort:
        tables.sort()
    table_column_map = []
    for t in tables:
        t_columns = [c for c in columns if c.table_id == t]
        if sort:
            t_columns.sort()
        table_column_map.append((t, t_columns))
    return table_column_map


# =============================================================================
# Using SQL grammars (but without reference to Django models, for testing)
# =============================================================================

def make_identifier(grammar: SqlGrammar,
                    database: str = None,
                    schema: str = None,
                    table: str = None,
                    column: str = None) -> str:
    """
    Makes an SQL identifier by quoting its elements according to the style of
    the specific SQL grammar, and then joining them with ``.``.

    Args:
        grammar: :class:`cardinal_pythonlib.sql.sql_grammar.SqlGrammar`
        database: database name
        schema: schema name
        table: table name
        column: column name

    Returns:
        a string as above in the order "database, schema, table, column", but
        omitting any missing parts

    """
    elements = [grammar.quote_identifier_if_required(x)
                for x in (database, schema, table, column) if x]
    assert elements, "make_identifier(): No elements passed!"
    return ".".join(elements)


def dumb_make_identifier(database: str = None,
                         schema: str = None,
                         table: str = None,
                         column: str = None) -> str:
    """
    Makes an SQL-style identifier by joining all the parts with ``.``, without
    bothering to quote them.

    Args:
        database: database name
        schema: schema name
        table: table name
        column: column name

    Returns:
        a string as above in the order "database, schema, table, column", but
        omitting any missing parts

    """
    elements = filter(None, [database, schema, table, column])
    assert elements, "make_identifier(): No elements passed!"
    return ".".join(elements)


def parser_add_result_column(parsed: ParseResults,
                             column: str,
                             grammar: SqlGrammar) -> ParseResults:
    """
    Takes a parsed SQL statement of the form

    .. code-block:: sql

        SELECT a, b, c
        FROM sometable
        WHERE conditions;

    and adds a result column, e.g. ``d``, to give

    .. code-block:: sql

        SELECT a, b, c, d
        FROM sometable
        WHERE conditions;

    Presupposes that there is at least one column already in the SELECT
    statement.

    Args:
        parsed: a `pyparsing.ParseResults` result
        column: column name
        grammar: :class:`cardinal_pythonlib.sql.sql_grammar.SqlGrammar`

    Returns:
        a `pyparsing.ParseResults` result

    """
    # log.critical("Adding: " + repr(column))
    existing_columns = parsed.select_expression.select_columns.asList()
    # log.critical(parsed.dump())
    # log.critical(f"existing columns: {repr(existing_columns)}")
    # log.critical(f"adding column: {column}")
    if column not in existing_columns:
        # log.critical("... doesn't exist; adding")
        newcol = grammar.get_result_column().parseString(column,
                                                         parseAll=True)
        # log.critical("... " + repr(newcol))
        parsed.select_expression.extend([",", newcol])
    # else:
    #     log.critical("... skipping column; exists")
    # log.critical(parsed.dump())
    return parsed


class JoinInfo(object):
    """
    Object to represent a SQL join condition in a simple way.
    """
    def __init__(self,
                 table: str,
                 join_type: str = 'INNER JOIN',
                 join_condition: str = '') -> None:  # e.g. "ON x = y"
        """
        Args:
            table: table to be joined in
            join_type: join method, e.g. ``"INNER JOIN"``
            join_condition: join condition, e.g. ``"ON x = y"``
        """
        self.join_type = join_type
        self.table = table
        self.join_condition = join_condition


def parser_add_from_tables(parsed: ParseResults,
                           join_info_list: List[JoinInfo],
                           grammar: SqlGrammar) -> ParseResults:
    """
    Takes a parsed SQL statement of the form

    .. code-block:: sql

        SELECT a, b, c
        FROM sometable
        WHERE conditions;

    and adds one or more join columns, e.g. ``JoinInfo("othertable", "INNER
    JOIN", "ON table.key = othertable.key")``, to give

    .. code-block:: sql

        SELECT a, b, c
        FROM sometable
        INNER JOIN othertable ON table.key = othertable.key
        WHERE conditions;

    Presupposes that there at least one table already in the FROM clause.

    Args:
        parsed: a `pyparsing.ParseResults` result
        join_info_list: list of :class:`JoinInfo` objects
        grammar: :class:`cardinal_pythonlib.sql.sql_grammar.SqlGrammar`

    Returns:
        a `pyparsing.ParseResults` result

    """
    # log.critical(parsed.dump())
    existing_tables = parsed.join_source.from_tables.asList()
    # log.critical(f"existing tables: {existing_tables}")
    # log.critical(f"adding table: {table}")
    for ji in join_info_list:
        if ji.table in existing_tables:  # already there
            # log.critical("field already present")
            continue
        parsed_join = grammar.get_join_op().parseString(ji.join_type,
                                                        parseAll=True)[0]  # e.g. INNER JOIN  # noqa
        parsed_table = grammar.get_table_spec().parseString(ji.table,
                                                            parseAll=True)[0]
        extrabits = [parsed_join, parsed_table]
        if ji.join_condition:  # e.g. ON x = y
            extrabits.append(
                grammar.get_join_constraint().parseString(ji.join_condition,
                                                          parseAll=True)[0])
        parsed.join_source.extend(extrabits)
    # log.critical(parsed.dump())
    return parsed


def get_first_from_table(parsed: ParseResults,
                         match_db: str = '',
                         match_schema: str = '',
                         match_table: str = '') -> TableId:
    """
    Given a set of parsed results from a SELECT statement, returns the ``db,
    schema, table`` tuple representing the first table in the FROM clause.

    Optionally, the match may be constrained with the ``match*`` parameters.

    Args:
        parsed: a `pyparsing.ParseResults` result
        match_db: optional database name to constrain the result to
        match_schema: optional schema name to constrain the result to
        match_table: optional table name to constrain the result to

    Returns:
        a :class:`TableId`, which will be empty in case of failure
    """
    existing_tables = parsed.join_source.from_tables.asList()
    for t in existing_tables:
        table_id = split_db_schema_table(t)
        if match_db and table_id.db != match_db:
            continue
        if match_schema and table_id.schema != match_schema:
            continue
        if match_table and table_id.table != match_table:
            continue
        return table_id
    return TableId()


def set_distinct_within_parsed(p: ParseResults, action: str = 'set') -> None:
    """
    Modifies (in place) the DISTINCT status of a parsed SQL statement.

    Args:
        p: a `pyparsing.ParseResults` result
        action: ``"set"`` to turn DISTINCT on; ``"clear"`` to turn it off;
            or ``"toggle"`` to toggle it.
    """
    ss = p.select_specifier  # type: ParseResults
    if action == 'set':
        if 'DISTINCT' not in ss.asList():
            ss.append('DISTINCT')
    elif action == 'clear':
        if 'DISTINCT' in ss.asList():
            del ss[:]
    elif action == 'toggle':
        if 'DISTINCT' in ss.asList():
            del ss[:]
        else:
            ss.append('DISTINCT')
    else:
        raise ValueError("action must be one of set/clear/toggle")


def set_distinct(sql: str,
                 grammar: SqlGrammar,
                 action: str = 'set',
                 formatted: bool = True,
                 debug: bool = False,
                 debug_verbose: bool = False) -> str:
    """
    Takes an SQL statement (as a string) and modifies its DISTINCT status.

    Args:
        sql: SQL statment as text
        grammar: :class:`cardinal_pythonlib.sql.sql_grammar.SqlGrammar`
        action: one of ``"set"``, ``"clear"``, ``"toggle"``; see
            :func:`set_distinct_within_parsed`
        formatted: pretty-format the result?
        debug: show debugging information to the Python log
        debug_verbose: be verbose when debugging

    Returns:
        the modified SQL statment, as a string

    """
    p = grammar.get_select_statement().parseString(sql, parseAll=True)
    if debug:
        log.info(f"START: {sql}")
        if debug_verbose:
            log.debug("start dump:\n" + p.dump())
    set_distinct_within_parsed(p, action=action)
    result = text_from_parsed(p, formatted=formatted)
    if debug:
        log.info(f"END: {result}")
        if debug_verbose:
            log.debug("end dump:\n" + p.dump())
    return result


def toggle_distinct(sql: str,
                    grammar: SqlGrammar,
                    formatted: bool = True,
                    debug: bool = False,
                    debug_verbose: bool = False) -> str:
    """
    Takes an SQL statement and toggles its DISTINCT status.

    Args:
        sql: SQL statment as text
        grammar: :class:`cardinal_pythonlib.sql.sql_grammar.SqlGrammar`
        formatted: pretty-format the result?
        debug: show debugging information to the Python log
        debug_verbose: be verbose when debugging

    Returns:
        the modified SQL statment, as a string

    """
    return set_distinct(sql=sql,
                        grammar=grammar,
                        action='toggle',
                        formatted=formatted,
                        debug=debug,
                        debug_verbose=debug_verbose)


# =============================================================================
# SQLAlchemy reflection and DDL
# =============================================================================

_print_not_execute = False


def set_print_not_execute(print_not_execute: bool) -> None:
    """
    Sets a nasty global flag: should we print DDL, rather than executing it,
    when we issue DDL commands from this module?

    Args:
        print_not_execute: print (not execute)?
    """
    global _print_not_execute
    _print_not_execute = print_not_execute


def execute(engine: Engine, sql: str) -> None:
    """
    Executes SQL.

    Whether we act or just print is conditional on previous calls to
    :func:`set_print_not_execute`.

    Args:
        engine: SQLAlchemy database Engine
        sql: raw SQL to execute (or print)
    """
    log.debug(sql)
    if _print_not_execute:
        print(format_sql_for_print(sql) + "\n;")
        # extra \n in case the SQL ends in a comment
    else:
        engine.execute(sql)


def add_columns(engine: Engine, table: Table, columns: List[Column]) -> None:
    """
    Adds columns to a table.

    Whether we act or just print is conditional on previous calls to
    :func:`set_print_not_execute`.

    Args:
        engine: SQLAlchemy database Engine
        table: SQLAlchemy Table object
        columns: SQLAlchemy Column objects to add to the table

    Behaviour of different database systems:

    - ANSI SQL: add one column at a time: ``ALTER TABLE ADD [COLUMN] coldef``

      - i.e. "COLUMN" optional, one at a time, no parentheses
      - http://www.contrib.andrew.cmu.edu/~shadow/sql/sql1992.txt

    - MySQL: ``ALTER TABLE ADD [COLUMN] (a INT, b VARCHAR(32));``

      - i.e. "COLUMN" optional, parentheses required for >1, multiple OK
      - http://dev.mysql.com/doc/refman/5.7/en/alter-table.html

    - MS SQL Server: ``ALTER TABLE ADD COLUMN a INT, B VARCHAR(32);``

      - i.e. no "COLUMN", no parentheses, multiple OK
      - https://msdn.microsoft.com/en-us/library/ms190238.aspx
      - https://msdn.microsoft.com/en-us/library/ms190273.aspx
      - http://stackoverflow.com/questions/2523676

    This function therefore operates one at a time.

    SQLAlchemy doesn't provide a shortcut for this.

    """
    existing_column_names = get_column_names(engine, tablename=table.name,
                                             to_lower=True)
    column_defs = []
    for column in columns:
        if column.name.lower() not in existing_column_names:
            column_defs.append(column_creation_ddl(column, engine.dialect))
        else:
            log.debug(f"Table {table.name!r}: column {column.name!r} "
                      f"already exists; not adding")
    for column_def in column_defs:
        log.info(f"Table {repr(table.name)}: adding column {repr(column_def)}")
        execute(engine, f"""
            ALTER TABLE {table.name} ADD {column_def}
        """)


def drop_columns(engine: Engine, table: Table,
                 column_names: Iterable[str]) -> None:
    """
    Drops columns from a table.

    Whether we act or just print is conditional on previous calls to
    :func:`set_print_not_execute`.

    Args:
        engine: SQLAlchemy database Engine
        table: SQLAlchemy Table object
        column_names: names of columns to drop

    Columns are dropped one by one.

    """
    existing_column_names = get_column_names(engine, tablename=table.name,
                                             to_lower=True)
    for name in column_names:
        if name.lower() not in existing_column_names:
            log.debug(f"Table {table.name!r}: column {name!r} "
                      f"does not exist; not dropping")
        else:
            log.info(f"Table {table.name!r}: dropping column {name!r}")
            sql = f"ALTER TABLE {table.name} DROP COLUMN {name}"
            # SQL Server:
            #   http://www.techonthenet.com/sql_server/tables/alter_table.php
            # MySQL:
            #   http://dev.mysql.com/doc/refman/5.7/en/alter-table.html
            execute(engine, sql)


def add_indexes(engine: Engine, table: Table,
                indexdictlist: Iterable[Dict[str, Any]]) -> None:
    """
    Adds indexes to a table.

    Whether we act or just print is conditional on previous calls to
    :func:`set_print_not_execute`.

    Args:
        engine: SQLAlchemy database Engine
        table: SQLAlchemy Table object
        indexdictlist:
            indexes to add, specified as a list of dictionaries. Each
            dictionary has the following keys:

            =============== =================== ===============================
            Key             Status              Contents
            =============== =================== ===============================
            ``index_name``  mandatory, str      Name of the index
            ``column``      mandatory, str or   Column name(s) to index
                            List[str]
            ``unique``      optional, bool,     Make a unique index?
                            default ``False``
            =============== =================== ===============================
    """
    existing_index_names = get_index_names(engine, tablename=table.name,
                                           to_lower=True)
    for idxdefdict in indexdictlist:
        index_name = idxdefdict['index_name']
        column = idxdefdict['column']
        if not isinstance(column, str):
            column = ", ".join(column)  # must be a list
        unique = idxdefdict.get('unique', False)
        if index_name.lower() not in existing_index_names:
            log.info(f"Table {table.name!r}: adding index {index_name!r} on "
                     f"column {column!r}")
            execute(engine, f"""
                CREATE{" UNIQUE" if unique else ""} INDEX {index_name} 
                    ON {table.name} ({column})
            """)
        else:
            log.debug(f"Table {table.name!r}: index {index_name!r} "
                      f"already exists; not adding")


def drop_indexes(engine: Engine, table: Table,
                 index_names: Iterable[str]) -> None:
    """
    Drops indexes from a table.

    Whether we act or just print is conditional on previous calls to
    :func:`set_print_not_execute`.

    Args:
        engine: SQLAlchemy database Engine
        table: SQLAlchemy Table object
        index_names: names of indexes to drop
    """
    existing_index_names = get_index_names(engine, tablename=table.name,
                                           to_lower=True)
    for index_name in index_names:
        if index_name.lower() not in existing_index_names:
            log.debug(f"Table {table.name!r}: index {index_name!r} "
                      f"does not exist; not dropping")
        else:
            log.info(f"Table {table.name!r}: dropping index {index_name!r}")
            if engine.dialect.name == 'mysql':
                sql = f"ALTER TABLE {table.name} DROP INDEX {index_name}"
            elif engine.dialect.name == 'mssql':
                sql = f"DROP INDEX {table.name}.{index_name}"
            else:
                assert False, f"Unknown dialect: {engine.dialect.name}"
            execute(engine, sql)


def get_table_names(engine: Engine,
                    to_lower: bool = False,
                    sort: bool = False) -> List[str]:
    """
    Returns all table names for the database.

    Args:
        engine: SQLAlchemy database Engine
        to_lower: convert table names to lower case?
        sort: sort table names?

    Returns:
        list of table names

    """
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if to_lower:
        table_names = [x.lower() for x in table_names]
    if sort:
        table_names = sorted(table_names, key=lambda x: x.lower())
    return table_names


def get_view_names(engine: Engine,
                   to_lower: bool = False,
                   sort: bool = False) -> List[str]:
    """
    Returns all view names for the database.

    Args:
        engine: SQLAlchemy database Engine
        to_lower: convert view names to lower case?
        sort: sort view names?

    Returns:
        list of view names

    """
    inspector = inspect(engine)
    view_names = inspector.get_view_names()
    if to_lower:
        view_names = [x.lower() for x in view_names]
    if sort:
        view_names = sorted(view_names, key=lambda x: x.lower())
    return view_names


def get_column_names(engine: Engine,
                     tablename: str,
                     to_lower: bool = False,
                     sort: bool = False) -> List[str]:
    """
    Reads columns names afresh from the database, for a specific table (in case
    metadata is out of date).

    Args:
        engine: SQLAlchemy database Engine
        tablename: name of the table
        to_lower: convert view names to lower case?
        sort: sort view names?

    Returns:
        list of column names

    """
    inspector = inspect(engine)
    columns = inspector.get_columns(tablename)
    column_names = [x['name'] for x in columns]
    if to_lower:
        column_names = [x.lower() for x in column_names]
    if sort:
        column_names = sorted(column_names, key=lambda x: x.lower())
    return column_names


def get_index_names(engine: Engine,
                    tablename: str,
                    to_lower: bool = False,
                    sort: bool = False) -> List[str]:
    """
    Reads index names from the database, for a specific table.

    Args:
        engine: SQLAlchemy database Engine
        tablename: name of the table
        to_lower: convert index names to lower case?
        sort: sort index names?

    Returns:
        list of index names

    """
    # http://docs.sqlalchemy.org/en/latest/core/reflection.html
    inspector = inspect(engine)
    indexes = inspector.get_indexes(tablename)
    index_names = [x['name'] for x in indexes if x['name']]
    # ... at least for SQL Server, there always seems to be a blank one
    # with {'name': None, ...}.
    if to_lower:
        index_names = [x.lower() for x in index_names]
    if sort:
        index_names = sorted(index_names, key=lambda x: x.lower())
    return index_names


def ensure_columns_present(engine: Engine,
                           tablename: str,
                           column_names: Iterable[str]) -> None:
    """
    Ensure all these columns are present in a table, or raise an exception.

    Operates in case-insensitive fashion.

    Args:
        engine: SQLAlchemy database Engine
        tablename: name of the table
        column_names: names of required columns

    Raises:
        :exc:`ValueError` if any are missing

    """
    existing_column_names = get_column_names(engine, tablename=tablename,
                                             to_lower=True)
    if not column_names:
        return
    for col in column_names:
        if col.lower() not in existing_column_names:
            raise ValueError(
                f"Column {col!r} missing from table {tablename!r}, "
                f"whose columns are {existing_column_names!r}")


def create_view(engine: Engine,
                viewname: str,
                select_sql: str) -> None:
    """
    Creates a view.

    Whether we act or just print is conditional on previous calls to
    :func:`set_print_not_execute`.

    Args:
        engine: SQLAlchemy database Engine
        viewname: view name
        select_sql: SQL SELECT statement for this view
    """
    if engine.dialect.name == 'mysql':
        # MySQL has CREATE OR REPLACE VIEW.
        sql = f"CREATE OR REPLACE VIEW {viewname} AS {select_sql}"
    else:
        # SQL Server doesn't: http://stackoverflow.com/questions/18534919
        drop_view(engine, viewname, quiet=True)
        sql = f"CREATE VIEW {viewname} AS {select_sql}"
    log.info(f"Creating view: {repr(viewname)}")
    execute(engine, sql)


def assert_view_has_same_num_rows(engine: Engine,
                                  basetable: str,
                                  viewname: str) -> None:
    """
    Ensures that a view gives the same number of rows as a table. (For use in
    situations where this should hold; views don't have to do this in general!)

    Args:
        engine: SQLAlchemy database Engine
        basetable: name of the table that this view should have a 1:1
            relationship to
        viewname: view name

    Raises:
        :exc:`AssertionError` if they don't have the same number of rows

    """
    # Note that this relies on the data, i.e. design failures MAY cause this
    # assertion to fail, but won't necessarily (e.g. if the table is empty).
    n_base = count_star(engine, basetable)
    n_view = count_star(engine, viewname)
    assert n_view == n_base, (
        f"View bug: view {viewname} has {n_view} records but its base table "
        f"{basetable} has {n_base}; they should be equal")


def drop_view(engine: Engine,
              viewname: str,
              quiet: bool = False) -> None:
    """
    Drops a view.

    Whether we act or just print is conditional on previous calls to
    :func:`set_print_not_execute`.

    Args:
        engine: SQLAlchemy database Engine
        viewname: view name
        quiet: don't announce this to the Python log

    """
    # MySQL has DROP VIEW IF EXISTS, but SQL Server only has that from
    # SQL Server 2016 onwards.
    # - https://msdn.microsoft.com/en-us/library/ms173492.aspx
    # - http://dev.mysql.com/doc/refman/5.7/en/drop-view.html
    view_names = get_view_names(engine, to_lower=True)
    if viewname.lower() not in view_names:
        log.debug(f"View {viewname} does not exist; not dropping")
    else:
        if not quiet:
            log.info(f"Dropping view: {repr(viewname)}")
        sql = f"DROP VIEW {viewname}"
        execute(engine, sql)


# =============================================================================
# ViewMaker
# =============================================================================

class ViewMaker(object):
    """
    View-building assistance class.
    """
    def __init__(self,
                 viewname: str,
                 engine: Engine,
                 basetable: str,
                 existing_to_lower: bool = False,
                 rename: Dict[str, str] = None,
                 userobj: Any = None,
                 enforce_same_n_rows_as_base: bool = True,
                 insert_basetable_columns: bool = True) -> None:
        """
        Args:
            viewname: name of the view
            engine: SQLAlchemy database Engine
            basetable: name of the single base table that this view draws from
            existing_to_lower: translate column names to lower case in the
                view?
            rename: optional dictionary mapping ``from_name: to_name`` to
                translate column names in the view
            userobj: optional object (e.g. `argparse.Namespace`,
                dictionary...), not used by this class, and purely to store
                information for others' benefit
            enforce_same_n_rows_as_base: ensure that the view produces the
                same number of rows as its base table?
            insert_basetable_columns: start drafting the view by including all
                columns from the base table?
        """
        rename = rename or {}
        assert basetable, "ViewMaker: basetable missing!"
        self.viewname = viewname
        self.engine = engine
        self.basetable = basetable
        self.userobj = userobj  # only for others' benefit
        self.enforce_same_n_rows_as_base = enforce_same_n_rows_as_base
        self.select_elements = []
        self.from_elements = [basetable]
        self.where_elements = []
        self.lookup_tables = []  # type: List[str]
        self.index_requests = OrderedDict()

        if insert_basetable_columns:
            grammar = make_grammar(engine.dialect.name)

            def q(identifier: str) -> str:
                return grammar.quote_identifier_if_required(identifier)

            for colname in get_column_names(engine, tablename=basetable,
                                            to_lower=existing_to_lower):
                if colname in rename:
                    rename_to = rename[colname]
                    if not rename_to:
                        continue
                    as_clause = f" AS {q(rename_to)}"
                else:
                    as_clause = ""
                self.select_elements.append(
                    f"{q(basetable)}.{q(colname)}{as_clause}")
            assert self.select_elements, "Must have some active SELECT " \
                                         "elements from base table"

    def add_select(self, element: str) -> None:
        """
        Add an element to the SELECT clause of the the draft view's SQL
        (meaning: add e.g. a result column).
        """
        self.select_elements.append(element)

    def add_from(self, element: str) -> None:
        """
        Add an element to the FROM clause of the draft view's SQL statement.
        """
        self.from_elements.append(element)

    def add_where(self, element: str) -> None:
        """
        Add an element to the WHERE clause of the draft view's SQL statement.
        """
        self.where_elements.append(element)

    def get_sql(self) -> str:
        """
        Returns the view-creation SQL.
        """
        assert self.select_elements, "ViewMaker: no SELECT elements!"
        if self.where_elements:
            where = "\n    WHERE {}".format(
                "\n        AND ".join(self.where_elements))
        else:
            where = ""
        return (
            "\n    SELECT {select_elements}"
            "\n    FROM {from_elements}{where}".format(
                select_elements=",\n        ".join(self.select_elements),
                from_elements="\n        ".join(self.from_elements),
                where=where))

    def create_view(self, engine: Engine) -> None:
        """
        Creates the view.

        Whether we act or just print is conditional on previous calls to
        :func:`set_print_not_execute`.

        If ``enforce_same_n_rows_as_base`` is set, check the number of rows
        returned matches the base table.

        Args:
            engine: SQLAlchemy database Engine
        """
        create_view(engine, self.viewname, self.get_sql())
        if self.enforce_same_n_rows_as_base:
            assert_view_has_same_num_rows(engine, self.basetable,
                                          self.viewname)

    def drop_view(self, engine: Engine) -> None:
        """
        Drops the view.

        Whether we act or just print is conditional on previous calls to
        :func:`set_print_not_execute`.

        Args:
            engine: SQLAlchemy database Engine

        """
        drop_view(engine, self.viewname)

    def record_lookup_table(self, table: str) -> None:
        """
        Keep a record of a lookup table. The framework may wish to suppress
        these from a data dictionary later (e.g. create a view, suppress the
        messier raw data). See :func:`get_lookup_tables`.

        Args:
            table: table name
        """
        if table not in self.lookup_tables:
            self.lookup_tables.append(table)

    def get_lookup_tables(self) -> List[str]:
        """
        Returns all lookup tables that we have recorded. See
        :func:`record_lookup_table`.
        """
        return self.lookup_tables

    def request_index(self, table: str, column: str) -> None:
        """
        Note a request that a specific column be indexed. The framework can use
        the ViewMaker to keep a note of these requests, and then add index
        hints to a data dictionary if it wishes. See
        :func:`get_index_request_dict`.

        Args:
            table: table name
            column: column name
        """
        if table not in self.index_requests:
            self.index_requests[table] = []  # type: List[str]
        if column not in self.index_requests[table]:
            self.index_requests[table].append(column)

    def get_index_request_dict(self) -> Dict[str, List[str]]:
        """
        Returns all our recorded index requests, as a dictionary mapping each
        table name to a list of column names to be indexed. See
        :func:`request_index`.
        """
        return self.index_requests

    def record_lookup_table_keyfield(
            self,
            table: str,
            keyfield: Union[str, Iterable[str]]) -> None:
        """
        Makes a note that a table is a lookup table, and its key field(s)
        should be indexed. See :func:`get_lookup_tables`,
        :func:`get_index_request_dict`.

        Args:
            table: table name
            keyfield: field name, or iterable (e.g. list) of them
        """
        if isinstance(keyfield, str):
            keyfield = [keyfield]
        self.record_lookup_table(table)
        for kf in keyfield:
            self.request_index(table, kf)

    def record_lookup_table_keyfields(
            self,
            table_keyfield_tuples: Iterable[
                Tuple[str, Union[str, Iterable[str]]]
            ]) -> None:
        """
        Make a note of a whole set of lookup table / key field groups. See
        :func:`record_lookup_table_keyfield`.

        Args:
            table_keyfield_tuples:
                iterable (e.g. list) of tuples of the format ``tablename,
                keyfield``. Each will be passed to
                :func:`record_lookup_table_keyfield`.
        """
        for t, k in table_keyfield_tuples:
            self.record_lookup_table_keyfield(t, k)


# =============================================================================
# TransactionSizeLimiter
# =============================================================================

class TransactionSizeLimiter(object):
    """
    Class to allow us to limit the size of database transactions.
    """
    def __init__(self, session: Session,
                 max_rows_before_commit: int = None,
                 max_bytes_before_commit: int = None) -> None:
        """
        Args:
            session: SQLAlchemy database Session
            max_rows_before_commit: how many rows should we insert before
                triggering a COMMIT? ``None`` for no limit.
            max_bytes_before_commit: how many bytes should we insert before
                triggering a COMMIT? ``None`` for no limit.
        """
        self._session = session
        self._max_rows_before_commit = max_rows_before_commit
        self._max_bytes_before_commit = max_bytes_before_commit
        self._bytes_in_transaction = 0
        self._rows_in_transaction = 0

    def commit(self) -> None:
        """
        Performs a database COMMIT and resets our counters.

        (Measures some timing information, too.)
        """
        with MultiTimerContext(timer, TIMING_COMMIT):
            self._session.commit()
        self._bytes_in_transaction = 0
        self._rows_in_transaction = 0

    def notify(self, n_rows: int, n_bytes: int,
               force_commit: bool = False) -> None:
        """
        Use this function to notify the limiter of data that you've inserted
        into the database. If the total number of rows or bytes exceeds a limit
        that we've set, this will trigger a COMMIT.

        Args:
            n_rows: number of rows inserted
            n_bytes: number of bytes inserted
            force_commit: force a COMMIT?
        """
        if force_commit:
            self.commit()
            return
        self._bytes_in_transaction += n_bytes
        self._rows_in_transaction += n_rows
        # log.critical(
        #     f"adding {n_rows} rows, {n_bytes} bytes, to make "
        #     f"{self._rows_in_transaction} rows, "
        #     f"{self._bytes_in_transaction} bytes so far")
        if (self._max_bytes_before_commit is not None and
                self._bytes_in_transaction >= self._max_bytes_before_commit):
            log.info(
                f"Triggering early commit based on byte count "
                f"(reached {sizeof_fmt(self._bytes_in_transaction)}, "
                f"limit is {sizeof_fmt(self._max_bytes_before_commit)})")
            self.commit()
        elif (self._max_rows_before_commit is not None and
                self._rows_in_transaction >= self._max_rows_before_commit):
            log.info(
                f"Triggering early commit based on row count "
                f"(reached {self._rows_in_transaction} rows, "
                f"limit is {self._max_rows_before_commit})")
            self.commit()


# =============================================================================
# Specification matching
# =============================================================================

def _matches_tabledef(table: str, tabledef: str) -> bool:
    """
    Does the table name match the wildcard-based table definition?

    Args:
        table: tablename
        tabledef: ``fnmatch``-style pattern (e.g.
            ``"patient_address_table_*"``)
    """
    tr = get_spec_match_regex(tabledef)
    return bool(tr.match(table))


def matches_tabledef(table: str, tabledef: Union[str, List[str]]) -> bool:
    """
    Does the table name match the wildcard-based table definition?

    Args:
        table: table name
        tabledef: ``fnmatch``-style pattern (e.g.
            ``"patient_address_table_*"``), or list of them
    """
    if isinstance(tabledef, str):
        return _matches_tabledef(table, tabledef)
    elif not tabledef:
        return False
    else:  # list
        return any(_matches_tabledef(table, td) for td in tabledef)


def _matches_fielddef(table: str, field: str, fielddef: str) -> bool:
    """
    Does the table/field name match the wildcard-based field definition?

    Args:
        table: tablename
        field: fieldname
        fielddef: ``fnmatch``-style pattern (e.g. ``"system_table.*"``,
            ``"*.nhs_number"``)
    """
    column_id = split_db_schema_table_column(fielddef)
    cr = get_spec_match_regex(column_id.column)
    if not column_id.table:
        # Table not specified in the wildcard.
        # It's a match if the field matches.
        return bool(cr.match(field))
    # Table specified in the wildcard.
    # Both the table and the field parts have to match.
    tr = get_spec_match_regex(column_id.table)
    return bool(tr.match(table)) and bool(cr.match(field))


def matches_fielddef(table: str, field: str,
                     fielddef: Union[str, List[str]]) -> bool:
    """
    Does the table/field name match the wildcard-based field definition?

    Args:
        table: table name
        field: fieldname
        fielddef: ``fnmatch``-style pattern (e.g. ``"system_table.*"`` or
            ``"*.nhs_number"``), or list of them
    """
    if isinstance(fielddef, str):
        return _matches_fielddef(table, field, fielddef)
    elif not fielddef:
        return False
    else:  # list
        return any(_matches_fielddef(table, field, fd) for fd in fielddef)


# =============================================================================
# More SQL
# =============================================================================

def sql_fragment_cast_to_int(expr: str,
                             big: bool = True,
                             dialect: Dialect = None,
                             viewmaker: ViewMaker = None) -> str:
    """
    Takes an SQL expression and coerces it to an integer. For Microsoft SQL
    Server.

    Args:
        expr: starting SQL expression
        big: use BIGINT, not INTEGER?
        dialect: optional :class:`sqlalchemy.engine.interfaces.Dialect`. If
            ``None`` and we have a ``viewmaker``, use the viewmaker's dialect.
            Otherwise, assume SQL Server.
        viewmaker: optional :class:`ViewMaker`

    Returns:
        modified SQL expression
    
    *Notes*
    
    Conversion to INT:

    - http://stackoverflow.com/questions/2000045
    - http://stackoverflow.com/questions/14719760 (this one in particular!)
    - http://stackoverflow.com/questions/14692131

      - see LIKE example.
      - see ISNUMERIC();
        https://msdn.microsoft.com/en-us/library/ms186272.aspx;
        but that includes non-integer numerics

    - https://msdn.microsoft.com/en-us/library/ms174214(v=sql.120).aspx;
      relates to the SQL Server Management Studio "Find and Replace"
      dialogue box, not to SQL itself!

    - http://stackoverflow.com/questions/29206404/mssql-regular-expression

    Note that the regex-like expression supported by LIKE is extremely limited.

    - https://msdn.microsoft.com/en-us/library/ms179859.aspx

    - The only things supported are:

      .. code-block:: none

        %   any characters
        _   any single character
        []  single character in range or set, e.g. [a-f], [abcdef]
        [^] single character NOT in range or set, e.g. [^a-f], [abcdef]

    SQL Server does not support a REGEXP command directly.

    So the best bet is to have the LIKE clause check for a non-integer:

    .. code-block:: sql

        CASE
            WHEN something LIKE '%[^0-9]%' THEN NULL
            ELSE CAST(something AS BIGINT)
        END

    ... which doesn't deal with spaces properly, but there you go.
    Could also strip whitespace left/right:

    .. code-block:: sql

        CASE
            WHEN LTRIM(RTRIM(something)) LIKE '%[^0-9]%' THEN NULL
            ELSE CAST(something AS BIGINT)
        END

    That only works for positive integers.
    
    LTRIM/RTRIM are not ANSI SQL.
    Nor are unusual LIKE clauses; see
    http://stackoverflow.com/questions/712580/list-of-special-characters-for-sql-like-clause

    The other, for SQL Server 2012 or higher, is TRY_CAST:

    .. code-block:: sql

        TRY_CAST(something AS BIGINT)

    ... which returns NULL upon failure; see
    https://msdn.microsoft.com/en-us/library/hh974669.aspx
    
    Therefore, our **method** is as follows:
    
    - If the database supports TRY_CAST, use that.
    - Otherwise if we're using SQL Server, use a CASE/CAST construct.
    - Otherwise, raise :exc:`ValueError` as we don't know what to do. 

    """  # noqa
    inttype = "BIGINT" if big else "INTEGER"
    if dialect is None and viewmaker is not None:
        dialect = viewmaker.engine.dialect
    if dialect is None:
        sql_server = True
        supports_try_cast = False
    else:
        # noinspection PyUnresolvedReferences
        sql_server = dialect.name == 'mssql'
        # noinspection PyUnresolvedReferences
        supports_try_cast = (sql_server and
                             dialect.server_version_info >= MS_2012_VERSION)
    if supports_try_cast:
        return f"TRY_CAST({expr} AS {inttype})"
    elif sql_server:
        return (
            f"CASE WHEN LTRIM(RTRIM({expr})) LIKE '%[^0-9]%' "
            f"THEN NULL ELSE CAST({expr} AS {inttype}) END"
        )
        # Doesn't support negative integers.
    else:
        # noinspection PyUnresolvedReferences
        raise ValueError(f"Code not yet written for convert-to-int for "
                         f"dialect {dialect.name}")


# =============================================================================
# Abstracted SQL WHERE condition
# =============================================================================

@register_for_json(method=METHOD_PROVIDES_INIT_KWARGS)
@functools.total_ordering
class WhereCondition(object):
    """
    Ancillary class for building SQL WHERE expressions from our web forms.

    The essence of it is ``WHERE column op value_or_values``.
    """
    def __init__(self,
                 column_id: ColumnId = None,
                 op: str = '',
                 datatype: str = '',
                 value_or_values: Any = None,
                 raw_sql: str = '',
                 from_table_for_raw_sql: TableId = None) -> None:
        """
        Args:
            column_id:
                :class:`ColumnId` for the column
            op:
                operation (e.g. ``=``, ``<``, ``<=``, etc.)
            datatype:
                data type string that must match values in our
                ``querybuilder.js``; see source code. We use this to know how
                to build SQL literal values. (Not terribly elegant, but it
                works; SQL injection isn't a particular concern because we
                let our users run any SQL they want and ensure the connection
                is made read-only.)
            value_or_values:
                ``None``, single value, or list of values. Which is appropriate
                depends on the operation. For example, ``IS NULL`` takes no
                value; ``=`` takes one; ``IN`` takes many.
            raw_sql:
                override any thinking we might wish to do, and just return this
                raw SQL
            from_table_for_raw_sql:
                if we are using raw SQL, provide a :class:`TableId` for the
                relevant table here
        """
        self._column_id = column_id
        self._op = op.upper()
        self._datatype = datatype
        self._value = value_or_values
        self._no_value = False
        self._multivalue = False
        self._raw_sql = raw_sql
        self._from_table_for_raw_sql = from_table_for_raw_sql

        if not self._raw_sql:
            if self._op in SQL_OPS_VALUE_UNNECESSARY:
                self._no_value = True
                assert value_or_values is None, "Superfluous value passed"
            elif self._op in SQL_OPS_MULTIPLE_VALUES:
                self._multivalue = True
                assert isinstance(value_or_values, list), "Need list"
            else:
                assert not isinstance(value_or_values, list), "Need single value"  # noqa

    def init_kwargs(self) -> Dict:
        return {
            'column_id': self._column_id,
            'op': self._op,
            'datatype': self._datatype,
            'value_or_values': self._value,
            'raw_sql': self._raw_sql,
            'from_table_for_raw_sql': self._from_table_for_raw_sql,
        }

    def __repr__(self) -> str:
        return (
            "<{qualname}("
            "column_id={column_id}, "
            "op={op}, "
            "datatype={datatype}, "
            "value_or_values={value_or_values}, "
            "raw_sql={raw_sql}, "
            "from_table_for_raw_sql={from_table_for_raw_sql}"
            ") at {addr}>".format(
                qualname=self.__class__.__qualname__,
                column_id=repr(self._column_id),
                op=repr(self._op),
                datatype=repr(self._datatype),
                value_or_values=repr(self._value),
                raw_sql=repr(self._raw_sql),
                from_table_for_raw_sql=repr(self._from_table_for_raw_sql),
                addr=hex(id(self)),
            )
        )

    def __eq__(self, other: 'WhereCondition') -> bool:
        return (
            self._raw_sql == other._raw_sql and
            self._column_id == other._column_id and
            self._op == other._op and
            self._value == other._value
        )

    def __lt__(self, other: 'WhereCondition') -> bool:
        return (
            (self._raw_sql, self._column_id, self._op, self._value) <
            (other._raw_sql, other._column_id, other._op, other._value)
        )

    @property
    def column_id(self) -> ColumnId:
        """
        Returns the :class:`ColumnId` provided at creation.
        """
        return self._column_id

    @property
    def table_id(self) -> TableId:
        """
        Returns a :class:`TableId`:

        - for raw SQL, our ``from_table_for_raw_sql`` attribute
        - otherwise, the table ID extracted from our ``column_id`` attribute
        """
        if self._raw_sql:
            return self._from_table_for_raw_sql
        return self.column_id.table_id

    def table_str(self, grammar: SqlGrammar) -> str:
        """
        Returns the table identifier in the specified SQL grammar.

        Args:
            grammar: :class:`cardinal_pythonlib.sql.sql_grammar.SqlGrammar`
        """
        return self.table_id.identifier(grammar)

    def sql(self, grammar: SqlGrammar) -> str:
        """
        Returns the WHERE clause (without ``WHERE`` itself!) for our condition,
        in the specified SQL grammar. Some examples might be:

        - ``somecol = 3``
        - ``othercol IN (6, 7, 8)``
        - ``thirdcol IS NOT NULL``
        - ``textcol LIKE '%paracetamol%'``
        - ``MATCH (fulltextcol AGAINST 'paracetamol')`` (MySQL)
        - ``CONTAINS(fulltextcol, 'paracetamol')`` (SQL Server)

        Args:
            grammar: :class:`cardinal_pythonlib.sql.sql_grammar.SqlGrammar`
        """
        if self._raw_sql:
            return self._raw_sql

        col = self._column_id.identifier(grammar)
        op = self._op

        if self._no_value:
            return f"{col} {op}"

        if self._datatype in QB_STRING_TYPES:
            element_converter = sql_string_literal
        elif self._datatype == QB_DATATYPE_DATE:
            element_converter = sql_date_literal
        elif self._datatype == QB_DATATYPE_INTEGER:
            element_converter = str
        elif self._datatype == QB_DATATYPE_FLOAT:
            element_converter = str
        else:
            # Safe default
            element_converter = sql_string_literal

        if self._multivalue:
            literal = "({})".format(", ".join(element_converter(v)
                                              for v in self._value))
        else:
            literal = element_converter(self._value)

        if self._op == 'MATCH':  # MySQL
            return f"MATCH ({col}) AGAINST ({literal})"
        elif self._op == 'CONTAINS':  # SQL Server
            return f"CONTAINS({col}, {literal})"
        else:
            return f"{col} {op} {literal}"


# =============================================================================
# SQL formatting
# =============================================================================

def format_sql_for_print(sql: str) -> str:
    """
    Very simple SQL formatting.

    Remove blank lines and trailing spaces from an SQL statement.
    Converts tabs to spaces.
    """
    lines = list(filter(None, [x.replace("\t", "    ").rstrip()
                               for x in sql.splitlines()]))
    # Shift all lines left if they're left-padded
    firstleftpos = float('inf')
    for line in lines:
        leftpos = len(line) - len(line.lstrip())
        firstleftpos = min(firstleftpos, leftpos)
    if firstleftpos > 0:
        lines = [x[firstleftpos:] for x in lines]
    return "\n".join(lines)


# =============================================================================
# Plain SQL types
# =============================================================================

def is_sql_column_type_textual(column_type: str,
                               min_length: int = 1) -> bool:
    """
    Does an SQL column type look textual?

    Args:
        column_type: SQL column type as a string, e.g. ``"VARCHAR(50)"``
        min_length: what's the minimum string length we'll say "yes" to?

    Returns:
        is it a textual column (of the minimum length or more)?

    Note:

    - For SQL Server's NVARCHAR(MAX), 
      :meth:`crate_anon.crateweb.research.research_db_info._schema_query_microsoft`
      returns "NVARCHAR(-1)"
    """
    column_type = column_type.upper()
    if column_type in SQLTYPES_TEXT:
        # A text type without a specific length
        return True
    try:
        m = COLTYPE_WITH_ONE_INTEGER_REGEX.match(column_type)
        basetype = m.group(1)
        length = int(m.group(2))
    except (AttributeError, ValueError):
        return False
    return (length >= min_length or length < 0) and basetype in SQLTYPES_TEXT


def escape_quote_in_literal(s: str) -> str:
    """
    Escape ``'``. We could use ``''`` or ``\'``.
    Let's use ``\.`` for consistency with percent escaping.
    """
    return s.replace("'", r"\'")


def escape_percent_in_literal(sql: str) -> str:
    """
    Escapes ``%`` by converting it to ``\%``.
    Use this for LIKE clauses.

    - http://dev.mysql.com/doc/refman/5.7/en/string-literals.html
    """
    return sql.replace('%', r'\%')


def escape_percent_for_python_dbapi(sql: str) -> str:
    """
    Escapes ``%`` by converting it to ``%%``.
    Use this for SQL within Python where ``%`` characters are used for argument
    placeholders.
    """
    return sql.replace('%', '%%')


def escape_sql_string_literal(s: str) -> str:
    """
    Escapes SQL string literal fragments against quotes and parameter
    substitution.
    """
    return escape_percent_in_literal(escape_quote_in_literal(s))


def make_string_literal(s: str) -> str:
    """
    Converts a Python string into an SQL single-quoted (and escaped) string
    literal.
    """
    return f"'{escape_sql_string_literal(s)}'"


def escape_sql_string_or_int_literal(s: Union[str, int]) -> str:
    """
    Converts an integer or a string into an SQL literal (with single quotes and
    escaping in the case of a string).
    """
    if isinstance(s, int):
        return str(s)
    else:
        return make_string_literal(s)


def translate_sql_qmark_to_percent(sql: str) -> str:
    """
    This function translates SQL using ``?`` placeholders to SQL using ``%s``
    placeholders, without breaking literal ``'?'`` or ``'%'``, e.g. inside
    string literals.
    
    *Notes*

    - MySQL likes ``?`` as a placeholder.
    
      - https://dev.mysql.com/doc/refman/5.7/en/sql-syntax-prepared-statements.html

    - Python DBAPI allows several: ``%s``, ``?``, ``:1``, ``:name``,
      ``%(name)s``.
    
      - https://www.python.org/dev/peps/pep-0249/#paramstyle

    - Django uses ``%s``.
    
      - https://docs.djangoproject.com/en/1.8/topics/db/sql/

    - Microsoft like ``?``, ``@paramname``, and ``:paramname``.
    
      - https://msdn.microsoft.com/en-us/library/yy6y35y8(v=vs.110).aspx

    - We need to parse SQL with argument placeholders.
    
      - See :class:`cardinal_pythonlib.sql.sql_grammar.SqlGrammar` classes,
        particularly: ``bind_parameter``

    I prefer ``?``, because ``%`` is used in LIKE clauses, and the databases
    we're using like it.

    So:

    - We use ``%s`` when using ``cursor.execute()`` directly, via Django.
    - We use ``?`` when talking to users, and
      :class:`cardinal_pythonlib.sql.sql_grammar.SqlGrammar` objects, so that
      the visual appearance matches what they expect from their database.

    """  # noqa
    # 1. Escape % characters
    sql = escape_percent_for_python_dbapi(sql)
    # 2. Replace ? characters that are not within quotes with %s.
    newsql = ""
    in_quotes = False
    for c in sql:
        if c == "'":
            in_quotes = not in_quotes
        if c == '?' and not in_quotes:
            newsql += '%s'
        else:
            newsql += c
    return newsql


_ = """
    _SQLTEST1 = "SELECT a FROM b WHERE c=? AND d LIKE 'blah%' AND e='?'"
    _SQLTEST2 = "SELECT a FROM b WHERE c=%s AND d LIKE 'blah%%' AND e='?'"
    _SQLTEST3 = translate_sql_qmark_to_percent(_SQLTEST1)
"""


# =============================================================================
# Tests
# =============================================================================

def unit_tests():
    """
    Unit tests.
    """
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
    sql = "SELECT t1.c1, t2.c2 " \
          "FROM t1 INNER JOIN t2 ON t1.k = t2.k"
    parsed = grammar.get_select_statement().parseString(sql, parseAll=True)
    table_id = get_first_from_table(parsed)  # noqa
    log.info(repr(table_id))


if __name__ == '__main__':
    main_only_quicksetup_rootlogger()
    unit_tests()
