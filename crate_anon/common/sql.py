#!/usr/bin/env python

"""
crate_anon/common/sql.py

===============================================================================

    Copyright (C) 2015-2018 Rudolf Cardinal (rudolf@pobox.com).

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

import argparse
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

COLTYPE_WITH_ONE_INTEGER_REGEX = re.compile(r"^([A-z]+)\((\d+)\)$")
# ... start, group(alphabetical), literal (, group(digit), literal ), end


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
    def __init__(self, db: str = '', schema: str = '') -> None:
        assert "." not in db, (
            "Bad database name ({!r}); can't include '.'".format(db)
        )
        assert "." not in schema, (
            "Bad schema name ({!r}); can't include '.'".format(schema)
        )
        self._db = db
        self._schema = schema

    @property
    def schema_tag(self) -> str:
        """
        String suitable for encoding the SchemaId e.g. in a single HTML form.
        The __init__ function checks the assumption of no '.' characters in
        either part.
        """
        return "{}.{}".format(self._db, self._schema)

    @classmethod
    def from_schema_tag(cls, tag: str) -> 'SchemaId':
        parts = tag.split(".")
        assert len(parts) == 2, "Bad schema tag {!r}".format(tag)
        db, schema = parts
        return SchemaId(db, schema)

    def __bool__(self) -> bool:
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
        return make_identifier(grammar,
                               database=self._db,
                               schema=self._schema)

    def table_id(self, table: str) -> 'TableId':
        return TableId(db=self._db, schema=self._schema, table=table)

    def column_id(self, table: str, column: str) -> 'ColumnId':
        return ColumnId(db=self._db, schema=self._schema,
                        table=table, column=column)

    @property
    def db(self) -> str:
        return self._db

    @property
    def schema(self) -> str:
        return self._schema

    def __str__(self) -> str:
        return self.identifier(mysql_grammar)  # specific one unimportant

    def __repr__(self) -> str:
        return mapped_repr_stripping_underscores(
            self, ['_db', '_schema'])


@register_for_json(method=METHOD_STRIP_UNDERSCORE)
@functools.total_ordering
class TableId(object):
    def __init__(self, db: str = '', schema: str = '',
                 table: str = '') -> None:
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
        return make_identifier(grammar,
                               database=self._db,
                               schema=self._schema,
                               table=self._table)

    @property
    def schema_id(self) -> SchemaId:
        return SchemaId(db=self._db, schema=self._schema)

    def column_id(self, column: str) -> 'ColumnId':
        return ColumnId(db=self._db, schema=self._schema,
                        table=self._table, column=column)

    def database_schema_part(self, grammar: SqlGrammar) -> str:
        return make_identifier(grammar,
                               database=self._db,
                               schema=self._schema)

    def table_part(self, grammar: SqlGrammar) -> str:
        return make_identifier(grammar, table=self._table)

    @property
    def db(self) -> str:
        return self._db

    @property
    def schema(self) -> str:
        return self._schema

    @property
    def table(self) -> str:
        return self._table

    def __str__(self) -> str:
        return self.identifier(mysql_grammar)  # specific one unimportant

    def __repr__(self) -> str:
        return mapped_repr_stripping_underscores(
            self, ['_db', '_schema', '_table'])


@register_for_json(method=METHOD_STRIP_UNDERSCORE)
@functools.total_ordering
class ColumnId(object):
    def __init__(self, db: str = '', schema: str = '',
                 table: str = '', column: str = '') -> None:
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
        return bool(self._table and self._column)  # the minimum

    def identifier(self, grammar: SqlGrammar) -> str:
        return make_identifier(grammar,
                               database=self._db,
                               schema=self._schema,
                               table=self._table,
                               column=self._column)

    @property
    def db(self) -> str:
        return self._db

    @property
    def schema(self) -> str:
        return self._schema

    @property
    def table(self) -> str:
        return self._table

    @property
    def column(self) -> str:
        return self._column

    @property
    def schema_id(self) -> SchemaId:
        return SchemaId(db=self._db, schema=self._schema)

    @property
    def table_id(self) -> TableId:
        return TableId(db=self._db, schema=self._schema, table=self._table)

    @property
    def has_table_and_column(self) -> bool:
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
    #         components[-1] = "<b>{}</b>".format(components[-1])
    #     return ".".join(components)


def split_db_schema_table(db_schema_table: str) -> TableId:
    components = db_schema_table.split('.')
    if len(components) == 3:  # db.schema.table
        d, s, t = components[0], components[1], components[2]
    elif len(components) == 2:  # schema.table
        d, s, t = '', components[0], components[1]
    elif len(components) == 1:  # table
        d, s, t = '', '', components[0]
    else:
        raise ValueError("Bad db_schema_table: {}".format(db_schema_table))
    return TableId(db=d, schema=s, table=t)


def split_db_schema_table_column(db_schema_table_col: str) -> ColumnId:
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
        raise ValueError("Bad db_schema_table_col: {}".format(
            db_schema_table_col))
    return ColumnId(db=d, schema=s, table=t, column=c)


def columns_to_table_column_hierarchy(
        columns: List[ColumnId],
        sort: bool = True) -> List[Tuple[TableId, List[ColumnId]]]:
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
    elements = [grammar.quote_identifier_if_required(x)
                for x in (database, schema, table, column) if x]
    assert elements, "make_identifier(): No elements passed!"
    return ".".join(elements)


def dumb_make_identifier(database: str = None,
                         schema: str = None,
                         table: str = None,
                         column: str = None) -> str:
    elements = filter(None, [database, schema, table, column])
    assert elements, "make_identifier(): No elements passed!"
    return ".".join(elements)


def parser_add_result_column(parsed: ParseResults,
                             column: str,
                             grammar: SqlGrammar) -> ParseResults:
    # Presupposes at least one column already in the SELECT statement.
    # log.critical("Adding: " + repr(column))
    existing_columns = parsed.select_expression.select_columns.asList()
    # log.critical(parsed.dump())
    # log.critical("existing columns: {}".format(repr(existing_columns)))
    # log.critical("adding column: {}".format(column))
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
    def __init__(self,
                 table: str,
                 join_type: str = 'INNER JOIN',
                 join_condition: str = '') -> None:  # e.g. "ON x = y"
        self.join_type = join_type
        self.table = table
        self.join_condition = join_condition


def parser_add_from_tables(parsed: ParseResults,
                           join_info_list: List[JoinInfo],
                           grammar: SqlGrammar) -> ParseResults:
    """
    Presupposes at least one table already in the FROM clause.
    """
    # log.critical(parsed.dump())
    existing_tables = parsed.join_source.from_tables.asList()
    # log.critical("existing tables: {}".format(existing_tables))
    # log.critical("adding table: {}".format(table))
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
    Given a set of parsed results from a SELECT statement,
    returns the (db, schema, table) tuple
    representing the first table in the FROM clause.

    Optionally, the match may be constrained with the match* parameters.
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
    p = grammar.get_select_statement().parseString(sql, parseAll=True)
    if debug:
        log.info("START: {}".format(sql))
        if debug_verbose:
            log.debug("start dump:\n" + p.dump())
    set_distinct_within_parsed(p, action=action)
    result = text_from_parsed(p, formatted=formatted)
    if debug:
        log.info("END: {}".format(result))
        if debug_verbose:
            log.debug("end dump:\n" + p.dump())
    return result


def toggle_distinct(sql: str,
                    grammar: SqlGrammar,
                    formatted: bool = True,
                    debug: bool = False,
                    debug_verbose: bool = False) -> str:
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
    global _print_not_execute
    _print_not_execute = print_not_execute


def execute(engine: Engine, sql: str) -> None:
    log.debug(sql)
    if _print_not_execute:
        print(format_sql_for_print(sql) + "\n;")
        # extra \n in case the SQL ends in a comment
    else:
        engine.execute(sql)


def add_columns(engine: Engine, table: Table, columns: List[Column]) -> None:
    existing_column_names = get_column_names(engine, tablename=table.name,
                                             to_lower=True)
    column_defs = []
    for column in columns:
        if column.name.lower() not in existing_column_names:
            column_defs.append(column_creation_ddl(column, engine.dialect))
        else:
            log.debug("Table {}: column {} already exists; not adding".format(
                repr(table.name), repr(column.name)))
    # ANSI SQL: add one column at a time: ALTER TABLE ADD [COLUMN] coldef
    #   - i.e. "COLUMN" optional, one at a time, no parentheses
    #   - http://www.contrib.andrew.cmu.edu/~shadow/sql/sql1992.txt
    # MySQL: ALTER TABLE ADD [COLUMN] (a INT, b VARCHAR(32));
    #   - i.e. "COLUMN" optional, parentheses required for >1, multiple OK
    #   - http://dev.mysql.com/doc/refman/5.7/en/alter-table.html
    # MS SQL Server: ALTER TABLE ADD COLUMN a INT, B VARCHAR(32);
    #   - i.e. no "COLUMN", no parentheses, multiple OK
    #   - https://msdn.microsoft.com/en-us/library/ms190238.aspx
    #   - https://msdn.microsoft.com/en-us/library/ms190273.aspx
    #   - http://stackoverflow.com/questions/2523676
    # SQLAlchemy doesn't provide a shortcut for this.
    for column_def in column_defs:
        log.info("Table {}: adding column {}".format(
            repr(table.name), repr(column_def)))
        execute(engine, """
            ALTER TABLE {tablename} ADD {column_def}
        """.format(tablename=table.name, column_def=column_def))


def drop_columns(engine: Engine, table: Table,
                 column_names: Iterable[str]) -> None:
    existing_column_names = get_column_names(engine, tablename=table.name,
                                             to_lower=True)
    for name in column_names:
        if name.lower() not in existing_column_names:
            log.debug("Table {}: column {} does not exist; not "
                      "dropping".format(repr(table.name), repr(name)))
        else:
            log.info("Table {}: dropping column {}".format(
                repr(table.name), repr(name)))
            sql = "ALTER TABLE {t} DROP COLUMN {c}".format(t=table.name,
                                                           c=name)
            # SQL Server:
            #   http://www.techonthenet.com/sql_server/tables/alter_table.php
            # MySQL:
            #   http://dev.mysql.com/doc/refman/5.7/en/alter-table.html
            execute(engine, sql)


def add_indexes(engine: Engine, table: Table,
                indexdictlist: Iterable[Dict[str, Any]]) -> None:
    existing_index_names = get_index_names(engine, tablename=table.name,
                                           to_lower=True)
    for idxdefdict in indexdictlist:
        index_name = idxdefdict['index_name']
        column = idxdefdict['column']
        if not isinstance(column, str):
            column = ", ".join(column)  # must be a list
        unique = idxdefdict.get('unique', False)
        if index_name.lower() not in existing_index_names:
            log.info("Table {}: adding index {} on column {}".format(
                repr(table.name), repr(index_name), repr(column)))
            execute(engine, """
                CREATE{unique} INDEX {idxname} ON {tablename} ({column})
            """.format(
                unique=" UNIQUE" if unique else "",
                idxname=index_name,
                tablename=table.name,
                column=column,
            ))
        else:
            log.debug("Table {}: index {} already exists; not adding".format(
                repr(table.name), repr(index_name)))


def drop_indexes(engine: Engine, table: Table,
                 index_names: Iterable[str]) -> None:
    existing_index_names = get_index_names(engine, tablename=table.name,
                                           to_lower=True)
    for index_name in index_names:
        if index_name.lower() not in existing_index_names:
            log.debug("Table {}: index {} does not exist; not dropping".format(
                repr(table.name), repr(index_name)))
        else:
            log.info("Table {}: dropping index {}".format(
                repr(table.name), repr(index_name)))
            if engine.dialect.name == 'mysql':
                sql = "ALTER TABLE {t} DROP INDEX {i}".format(t=table.name,
                                                              i=index_name)
            elif engine.dialect.name == 'mssql':
                sql = "DROP INDEX {t}.{i}".format(t=table.name, i=index_name)
            else:
                assert False, "Unknown dialect: {}".format(engine.dialect.name)
            execute(engine, sql)


def get_table_names(engine: Engine,
                    to_lower: bool = False,
                    sort: bool = False) -> List[str]:
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
    Reads columns names afresh from the database (in case metadata is out of
    date).
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
                    to_lower: bool = False) -> List[str]:
    """
    Reads index names from the database.
    """
    # http://docs.sqlalchemy.org/en/latest/core/reflection.html
    inspector = inspect(engine)
    indexes = inspector.get_indexes(tablename)
    index_names = [x['name'] for x in indexes if x['name']]
    # ... at least for SQL Server, there always seems to be a blank one
    # with {'name': None, ...}.
    if to_lower:
        index_names = [x.lower() for x in index_names]
    return index_names


def ensure_columns_present(engine: Engine,
                           tablename: str,
                           column_names: Iterable[str]) -> None:
    existing_column_names = get_column_names(engine, tablename=tablename,
                                             to_lower=True)
    if not column_names:
        return
    for col in column_names:
        if col.lower() not in existing_column_names:
            raise ValueError(
                "Column {} missing from table {}, whose columns are {}".format(
                    repr(col), repr(tablename), repr(existing_column_names)))


def create_view(engine: Engine,
                viewname: str,
                select_sql: str) -> None:
    if engine.dialect.name == 'mysql':
        # MySQL has CREATE OR REPLACE VIEW.
        sql = "CREATE OR REPLACE VIEW {viewname} AS {select_sql}".format(
            viewname=viewname,
            select_sql=select_sql,
        )
    else:
        # SQL Server doesn't: http://stackoverflow.com/questions/18534919
        drop_view(engine, viewname, quiet=True)
        sql = "CREATE VIEW {viewname} AS {select_sql}".format(
            viewname=viewname,
            select_sql=select_sql,
        )
    log.info("Creating view: {}".format(repr(viewname)))
    execute(engine, sql)


def assert_view_has_same_num_rows(engine: Engine,
                                  basetable: str,
                                  viewname: str) -> None:
    # Note that this relies on the data, i.e. design failures MAY cause this
    # assertion to fail, but won't necessarily (e.g. if the table is empty).
    n_base = count_star(engine, basetable)
    n_view = count_star(engine, viewname)
    assert n_view == n_base, (
        "View bug: view {} has {} records but its base table {} "
        "has {}; they should be equal".format(
            viewname, n_view,
            basetable, n_base))


def drop_view(engine: Engine,
              viewname: str,
              quiet: bool = False) -> None:
    # MySQL has DROP VIEW IF EXISTS, but SQL Server only has that from
    # SQL Server 2016 onwards.
    # - https://msdn.microsoft.com/en-us/library/ms173492.aspx
    # - http://dev.mysql.com/doc/refman/5.7/en/drop-view.html
    view_names = get_view_names(engine, to_lower=True)
    if viewname.lower() not in view_names:
        log.debug("View {} does not exist; not dropping".format(viewname))
    else:
        if not quiet:
            log.info("Dropping view: {}".format(repr(viewname)))
        sql = "DROP VIEW {viewname}".format(viewname=viewname)
        execute(engine, sql)


# =============================================================================
# View-building assistance class
# =============================================================================

class ViewMaker(object):
    def __init__(self,
                 viewname: str,
                 engine: Engine,
                 basetable: str,
                 existing_to_lower: bool = False,
                 rename: Dict[str, str] = None,
                 progargs: argparse.Namespace = None,
                 enforce_same_n_rows_as_base: bool = True,
                 insert_basetable_columns: bool = True) -> None:
        rename = rename or {}
        assert basetable, "ViewMaker: basetable missing!"
        self.viewname = viewname
        self.engine = engine
        self.basetable = basetable
        self.progargs = progargs  # only for others' benefit
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
                    as_clause = " AS {}".format(q(rename_to))
                else:
                    as_clause = ""
                self.select_elements.append("{t}.{c}{as_clause}".format(
                    t=q(basetable),
                    c=q(colname),
                    as_clause=as_clause))
            assert self.select_elements, "Must have some active SELECT " \
                                         "elements from base table"

    def add_select(self, clause: str) -> None:
        self.select_elements.append(clause)

    def add_from(self, clause: str) -> None:
        self.from_elements.append(clause)

    def add_where(self, clause: str) -> None:
        self.where_elements.append(clause)

    def get_sql(self) -> str:
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
        create_view(engine, self.viewname, self.get_sql())
        if self.enforce_same_n_rows_as_base:
            assert_view_has_same_num_rows(engine, self.basetable,
                                          self.viewname)

    def drop_view(self, engine: Engine) -> None:
        drop_view(engine, self.viewname)

    def record_lookup_table(self, table: str) -> None:
        if table not in self.lookup_tables:
            self.lookup_tables.append(table)

    def request_index(self, table: str, column: str) -> None:
        if table not in self.index_requests:
            self.index_requests[table] = []  # type: List[str]
        self.index_requests[table].append(column)

    def record_lookup_table_keyfield(
            self,
            table: str,
            keyfield: Union[str, Iterable[str]]) -> None:
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
        for t, k in table_keyfield_tuples:
            self.record_lookup_table_keyfield(t, k)

    def get_lookup_tables(self) -> List[str]:
        return self.lookup_tables

    def get_index_request_dict(self) -> Dict[str, List[str]]:
        return self.index_requests


# =============================================================================
# Transaction size-limiting class
# =============================================================================

class TransactionSizeLimiter(object):
    def __init__(self, session: Session,
                 max_rows_before_commit: int = None,
                 max_bytes_before_commit: int = None) -> None:
        self._session = session
        self._max_rows_before_commit = max_rows_before_commit
        self._max_bytes_before_commit = max_bytes_before_commit
        self._bytes_in_transaction = 0
        self._rows_in_transaction = 0

    def commit(self) -> None:
        with MultiTimerContext(timer, TIMING_COMMIT):
            self._session.commit()
        self._bytes_in_transaction = 0
        self._rows_in_transaction = 0

    def notify(self, n_rows: int, n_bytes: int,
               force_commit: bool=False) -> None:
        if force_commit:
            self.commit()
            return
        self._bytes_in_transaction += n_bytes
        self._rows_in_transaction += n_rows
        # log.critical(
        #     "adding {} rows, {} bytes, "
        #     "to make {} rows, {} bytes so far".format(
        #         n_rows, n_bytes,
        #         self._rows_in_transaction, self._bytes_in_transaction))
        if (self._max_bytes_before_commit is not None and
                self._bytes_in_transaction >= self._max_bytes_before_commit):
            log.info(
                "Triggering early commit based on byte count (reached {}, "
                "limit is {})".format(
                    sizeof_fmt(self._bytes_in_transaction),
                    sizeof_fmt(self._max_bytes_before_commit)))
            self.commit()
        elif (self._max_rows_before_commit is not None and
                self._rows_in_transaction >= self._max_rows_before_commit):
            log.info(
                "Triggering early commit based on row count (reached {} rows, "
                "limit is {})".format(self._rows_in_transaction,
                                      self._max_rows_before_commit))
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
    For Microsoft SQL Server.
    Conversion to INT:

    - http://stackoverflow.com/questions/2000045
    - http://stackoverflow.com/questions/14719760  # this one
    - http://stackoverflow.com/questions/14692131

      - see LIKE example.
      - see ISNUMERIC();
        https://msdn.microsoft.com/en-us/library/ms186272.aspx
        ... but that includes non-integer numerics

    - https://msdn.microsoft.com/en-us/library/ms174214(v=sql.120).aspx
      ... relates to the SQL Server Management Studio "Find and Replace"
      dialogue box, not to SQL itself!

    - http://stackoverflow.com/questions/29206404/mssql-regular-expression

    Note that the regex-like expression supported by LIKE is extremely limited.

    - https://msdn.microsoft.com/en-us/library/ms179859.aspx

    The only things supported are:

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

    Only works for positive integers.
    LTRIM/RTRIM are not ANSI SQL.
    Nor are unusual LIKE clauses; see
    http://stackoverflow.com/questions/712580/list-of-special-characters-for-sql-like-clause

    The other, for SQL Server 2012 or higher, is TRY_CAST:

    .. code-block:: sql

        TRY_CAST(something AS BIGINT)


    ... which returns NULL upon failure; see
    https://msdn.microsoft.com/en-us/library/hh974669.aspx

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
        return "TRY_CAST({expr} AS {inttype})".format(expr=expr,
                                                      inttype=inttype)
    elif sql_server:
        return (
            "CASE WHEN LTRIM(RTRIM({expr})) LIKE '%[^0-9]%' "
            "THEN NULL ELSE CAST({expr} AS {inttype}) END".format(
                expr=expr, inttype=inttype)
        )
        # Doesn't support negative integers.
    else:
        # noinspection PyUnresolvedReferences
        raise ValueError("Code not yet written for convert-to-int for "
                         "dialect {}".format(dialect.name))


# =============================================================================
# Abstracted SQL WHERE condition
# =============================================================================

@register_for_json(method=METHOD_PROVIDES_INIT_KWARGS)
@functools.total_ordering
class WhereCondition(object):
    # Ancillary class for building SQL WHERE expressions from our web forms.
    def __init__(self,
                 column_id: ColumnId = None,
                 op: str = '',
                 datatype: str = '',
                 value_or_values: Any = None,
                 raw_sql: str = '',
                 from_table_for_raw_sql: TableId = None) -> None:
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
        return self._column_id

    @property
    def table_id(self) -> TableId:
        if self._raw_sql:
            return self._from_table_for_raw_sql
        return self.column_id.table_id

    def table_str(self, grammar: SqlGrammar) -> str:
        return self.table_id.identifier(grammar)

    def sql(self, grammar: SqlGrammar) -> str:
        if self._raw_sql:
            return self._raw_sql

        col = self._column_id.identifier(grammar)
        op = self._op

        if self._no_value:
            return "{col} {op}".format(col=col, op=op)

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
            return "MATCH ({col}) AGAINST ({val})".format(col=col, val=literal)
        elif self._op == 'CONTAINS':  # SQL Server
            return "CONTAINS({col}, {val})".format(col=col, val=literal)
        else:
            return "{col} {op} {val}".format(col=col, op=op, val=literal)


# =============================================================================
# SQL formatting
# =============================================================================

def format_sql_for_print(sql: str) -> str:
    # Remove blank lines and trailing spaces
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
    return length >= min_length and basetype in SQLTYPES_TEXT


def escape_quote_in_literal(s: str) -> str:
    """
    Escape '. We could use '' or \'.
    Let's use \. for consistency with percent escaping.
    """
    return s.replace("'", r"\'")


def escape_percent_in_literal(sql: str) -> str:
    """
    Escapes % by converting it to \%.
    Use this for LIKE clauses.
    http://dev.mysql.com/doc/refman/5.7/en/string-literals.html
    """
    return sql.replace('%', r'\%')


def escape_percent_for_python_dbapi(sql: str) -> str:
    """
    Escapes % by converting it to %%.
    Use this for SQL within Python where % characters are used for argument
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
    return "'{}'".format(escape_sql_string_literal(s))


def escape_sql_string_or_int_literal(s: Union[str, int]) -> str:
    if isinstance(s, int):
        return str(s)
    else:
        return make_string_literal(s)


def translate_sql_qmark_to_percent(sql: str) -> str:
    """
    MySQL likes '?' as a placeholder.
    - https://dev.mysql.com/doc/refman/5.7/en/sql-syntax-prepared-statements.html

    Python DBAPI allows several: '%s', '?', ':1', ':name', '%(name)s'.
    - https://www.python.org/dev/peps/pep-0249/#paramstyle

    Django uses '%s'.
    - https://docs.djangoproject.com/en/1.8/topics/db/sql/

    Microsoft like '?', '@paramname', and ':paramname'.
    - https://msdn.microsoft.com/en-us/library/yy6y35y8(v=vs.110).aspx

    We need to parse SQL with argument placeholders.
    - See SqlGrammar classes, particularly: bind_parameter

    I prefer ?, because % is used in LIKE clauses, and the databases we're
    using like it.

    So:

    - We use %s when using cursor.execute() directly, via Django.
    - We use ? when talking to users, and SqlGrammar objects, so that the
      visual appearance matches what they expect from their database.

    This function translates SQL using ? placeholders to SQL using %s
    placeholders, without breaking literal '?' or '%', e.g. inside string
    literals.
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
