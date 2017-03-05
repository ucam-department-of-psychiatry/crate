#!/usr/bin/env python
# crate_anon/common/sqla.py

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

import ast
import contextlib
import copy
from functools import lru_cache
import logging
import re
from typing import Any, Dict, List, Optional, Tuple, Type, Union

from sqlalchemy.dialects import mssql, mysql
# noinspection PyUnresolvedReferences
from sqlalchemy.engine import Connection, Engine, ResultProxy
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.declarative.api import DeclarativeMeta
from sqlalchemy.schema import (Column, CreateColumn, DDL, MetaData, Index,
                               Sequence, Table)
from sqlalchemy.orm.session import Session
from sqlalchemy.sql import (column, exists, func, literal, select, sqltypes,
                            text, table)
from sqlalchemy.sql.expression import (
    ClauseElement,
    Insert,
    TableClause,
)
from sqlalchemy.sql.sqltypes import BigInteger, TypeEngine

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

MSSQL_DEFAULT_SCHEMA = 'dbo'
POSTGRES_DEFAULT_SCHEMA = 'public'


# =============================================================================
# SQL - SQLAlchemy ORM
# =============================================================================

# -----------------------------------------------------------------------------
# Get or create (SQLAlchemy ORM)
# -----------------------------------------------------------------------------
# http://stackoverflow.com/questions/2546207
# ... composite of several suggestions

def get_or_create(session: Session,
                  model: DeclarativeMeta,
                  defaults: Dict[str, Any] = None,
                  **kwargs: Any) -> Tuple[Any, bool]:
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance, False
    else:
        params = dict((k, v) for k, v in kwargs.items()
                      if not isinstance(v, ClauseElement))
        params.update(defaults or {})
        instance = model(**params)
        session.add(instance)
        return instance, True


# =============================================================================
# SQL - SQLAlchemy Core
# =============================================================================

# -----------------------------------------------------------------------------
# SELECT COUNT(*) (SQLAlchemy Core)
# -----------------------------------------------------------------------------
# http://stackoverflow.com/questions/12941416

def count_star(session: Union[Session, Engine, Connection],
               tablename: str) -> int:
    # works if you pass a connection or a session or an engine; all have
    # the execute() method
    query = select([func.count()]).select_from(table(tablename))
    return session.execute(query).scalar()


# -----------------------------------------------------------------------------
# SELECT COUNT(*), MAX(field) (SQLAlchemy Core)
# -----------------------------------------------------------------------------

def count_star_and_max(session: Union[Session, Engine, Connection],
                       tablename: str,
                       maxfield: str) -> Tuple[int, Optional[int]]:
    query = select([
        func.count(),
        func.max(column(maxfield))
    ]).select_from(table(tablename))
    result = session.execute(query)
    return result.fetchone()  # count, maximum


# -----------------------------------------------------------------------------
# SELECT EXISTS (SQLAlchemy Core)
# -----------------------------------------------------------------------------
# http://stackoverflow.com/questions/15381604
# http://docs.sqlalchemy.org/en/latest/orm/query.html


def exists_plain(session: Session, tablename: str, *criteria: Any) -> bool:
    exists_clause = exists().select_from(table(tablename))
    # ... EXISTS (SELECT * FROM tablename)
    for criterion in criteria:
        exists_clause = exists_clause.where(criterion)
    # ... EXISTS (SELECT * FROM tablename WHERE ...)

    if session.get_bind().dialect.name == 'mssql':
        query = select([literal(True)]).where(exists_clause)
        # ... SELECT 1 WHERE EXISTS (SELECT * FROM tablename WHERE ...)
    else:
        query = select([exists_clause])
        # ... SELECT EXISTS (SELECT * FROM tablename WHERE ...)

    result = session.execute(query).scalar()
    return bool(result)


def exists_orm(session: Session,
               ormclass: DeclarativeMeta,
               *criteria: Any) -> bool:
    # http://docs.sqlalchemy.org/en/latest/orm/query.html
    q = session.query(ormclass)
    for criterion in criteria:
        q = q.filter(criterion)

    # See this:
    # - https://bitbucket.org/zzzeek/sqlalchemy/issues/3212/misleading-documentation-for-queryexists  # noqa
    # - http://docs.sqlalchemy.org/en/latest/orm/query.html#sqlalchemy.orm.query.Query.exists  # noqa

    exists_clause = q.exists()
    if session.get_bind().dialect.name == 'mssql':
        # SQL Server
        result = session.query(literal(True)).filter(exists_clause).scalar()
        # SELECT 1 WHERE EXISTS (SELECT 1 FROM table WHERE ...)
        # ... giving 1 or None (no rows)
        # ... fine for SQL Server, but invalid for MySQL (no FROM clause)
    else:
        # MySQL, etc.
        result = session.query(exists_clause).scalar()
        # SELECT EXISTS (SELECT 1 FROM table WHERE ...)
        # ... giving 1 or 0
        # ... fine for MySQL, but invalid syntax for SQL server
    return bool(result)


# =============================================================================
# INSERT ... ON DUPLICATE KEY UPDATE support, for MySQL
# =============================================================================
# https://www.reddit.com/r/Python/comments/p5grh/sqlalchemy_whats_the_idiomatic_way_of_writing/  # noqa
# https://github.com/bedwards/sqlalchemy_mysql_ext/blob/master/duplicate.py
# ... modified
# http://docs.sqlalchemy.org/en/rel_1_0/core/compiler.html
# http://stackoverflow.com/questions/6611563/sqlalchemy-on-duplicate-key-update
# http://dev.mysql.com/doc/refman/5.7/en/insert-on-duplicate.html

# noinspection PyAbstractClass
class InsertOnDuplicate(Insert):
    pass


def insert_on_duplicate(tablename, values=None, inline=False, **kwargs):
    return InsertOnDuplicate(tablename, values, inline=inline, **kwargs)


# noinspection PyPep8Naming
def monkeypatch_TableClause():
    log.debug("Adding 'INSERT ON DUPLICATE KEY UPDATE' support for MySQL "
              "to SQLAlchemy")
    TableClause.insert_on_duplicate = insert_on_duplicate


# noinspection PyPep8Naming
def unmonkeypatch_TableClause():
    del TableClause.insert_on_duplicate


STARTSEPS = '`'
ENDSEPS = '`'
INSERT_FIELDNAMES_REGEX = (
    r'^INSERT\sINTO\s[{startseps}]?(?P<table>\w+)[{endseps}]?\s+'
    r'\((?P<columns>[, {startseps}{endseps}\w]+)\)\s+VALUES'.format(
        startseps=STARTSEPS, endseps=ENDSEPS)
)
# http://pythex.org/ !
RE_INSERT_FIELDNAMES = re.compile(INSERT_FIELDNAMES_REGEX)


@compiles(InsertOnDuplicate, 'mysql')
def compile_insert_on_duplicate_key_update(insert, compiler, **kw):
    """
    We can't get the fieldnames directly from 'insert' or 'compiler'.
    We could rewrite the innards of the visit_insert statement, like
        https://github.com/bedwards/sqlalchemy_mysql_ext/blob/master/duplicate.py  # noqa
    ... but, like that, it will get outdated.
    We could use a hack-in-by-hand method, like
        http://stackoverflow.com/questions/6611563/sqlalchemy-on-duplicate-key-update
    ... but a little automation would be nice.
    So, regex to the rescue:
    """
    # log.critical(compiler.__dict__)
    # log.critical(compiler.dialect.__dict__)
    # log.critical(insert.__dict__)
    s = compiler.visit_insert(insert, **kw)
    # log.critical(s)
    m = RE_INSERT_FIELDNAMES.match(s)
    if m is None:
        raise ValueError("compile_insert_on_duplicate_key_update: no match")
    columns = [c.strip() for c in m.group('columns').split(",")]
    # log.critical(columns)
    updates = ", ".join(["{c} = VALUES({c})".format(c=c) for c in columns])
    s += ' ON DUPLICATE KEY UPDATE {}'.format(updates)
    # log.critical(s)
    return s


# =============================================================================
# Inspect tables (SQLAlchemy Core)
# =============================================================================

def get_table_names(engine: Engine) -> List[str]:
    insp = Inspector.from_engine(engine)
    return insp.get_table_names()


def table_exists(engine: Engine, tablename: str) -> bool:
    return tablename in get_table_names(engine)


def get_columns_info(engine: Engine, tablename: str) -> List[Dict]:
    insp = Inspector.from_engine(engine)
    return insp.get_columns(tablename)


def get_column_info(engine: Engine, tablename: str,
                    columnname: str) -> Optional[Dict]:
    # Dictionary structure: see
    # http://docs.sqlalchemy.org/en/latest/core/reflection.html#sqlalchemy.engine.reflection.Inspector.get_columns  # noqa
    columns = get_columns_info(engine, tablename)
    for x in columns:
        if x['name'] == columnname:
            return x
    return None


def get_column_type(engine: Engine, tablename: str,
                    columnname: str) -> Optional[TypeEngine]:
    # Dictionary structure: see
    # http://docs.sqlalchemy.org/en/latest/core/reflection.html#sqlalchemy.engine.reflection.Inspector.get_columns  # noqa
    columns = get_columns_info(engine, tablename)
    for x in columns:
        if x['name'] == columnname:
            return x['type']
    return None


def get_column_names(engine: Engine, tablename: str) -> List[str]:
    return [x['name'] for x in get_columns_info(engine, tablename)]


# =============================================================================
# More introspection
# =============================================================================

def get_single_int_pk_colname(table_: Table) -> Optional[str]:
    """
    If a table has a single-field (non-composite) integer PK, this will
    return its name; otherwise, None.

    Note that it is fine to have both a composite primary key and a separate
    IDENTITY (AUTOINCREMENT) integer field.
    """
    n_pks = 0
    int_pk_names = []
    for col in table_.columns:
        if col.primary_key:
            n_pks += 1
            if is_sqlatype_integer(col.type):
                int_pk_names.append(col.name)
    if n_pks == 1 and len(int_pk_names) == 1:
        return int_pk_names[0]
    return None


def get_single_int_autoincrement_colname(table_: Table) -> Optional[str]:
    """
    If a table has a single integer AUTOINCREMENT column, this will
    return its name; otherwise, None.

    - It's unlikely that a database has >1 AUTOINCREMENT field anyway, but we
      should check.
    - SQL Server's IDENTITY keyword is equivalent to MySQL's AUTOINCREMENT.
    - Verify against SQL Server:

        SELECT table_name, column_name
        FROM information_schema.columns
        WHERE COLUMNPROPERTY(OBJECT_ID(table_schema + '.' + table_name),
                             column_name,
                             'IsIdentity') = 1
        ORDER BY table_name;

      ... http://stackoverflow.com/questions/87747

    - Also:

        sp_columns 'tablename';

        ... which is what SQLAlchemy does (dialects/mssql/base.py, in
        get_columns).
    """
    n_autoinc = 0
    int_autoinc_names = []
    for col in table_.columns:
        if col.autoincrement:
            n_autoinc += 1
            if is_sqlatype_integer(col.type):
                int_autoinc_names.append(col.name)
    if n_autoinc > 1:
        log.warning("Table {} has {} autoincrement columns".format(
            repr(table_.name), n_autoinc))
    if n_autoinc == 1 and len(int_autoinc_names) == 1:
        return int_autoinc_names[0]
    return None


# =============================================================================
# Indexes
# =============================================================================

def index_exists(engine: Engine, tablename: str, indexname: str) -> bool:
    insp = Inspector.from_engine(engine)
    return any(i['name'] == indexname for i in insp.get_indexes(tablename))


def mssql_get_pk_index_name(engine: Engine,
                            tablename: str,
                            schemaname: str = MSSQL_DEFAULT_SCHEMA) -> str:
    # http://docs.sqlalchemy.org/en/latest/core/connections.html#sqlalchemy.engine.Connection.execute  # noqa
    # http://docs.sqlalchemy.org/en/latest/core/sqlelement.html#sqlalchemy.sql.expression.text  # noqa
    # http://docs.sqlalchemy.org/en/latest/core/sqlelement.html#sqlalchemy.sql.expression.TextClause.bindparams  # noqa
    # http://docs.sqlalchemy.org/en/latest/core/connections.html#sqlalchemy.engine.ResultProxy  # noqa
    query = text("""
SELECT
    kc.name AS index_name
FROM
    sys.key_constraints AS kc
    INNER JOIN sys.tables AS ta ON ta.object_id = kc.parent_object_id
    INNER JOIN sys.schemas AS s ON ta.schema_id = s.schema_id
WHERE
    kc.[type] = 'PK'
    AND ta.name = :tablename
    AND s.name = :schemaname
    """).bindparams(
        tablename=tablename,
        schemaname=schemaname,
    )
    with contextlib.closing(engine.execute(query)) as result:  # type: ResultProxy  # noqa
        row = result.fetchone()
        return row[0] if row else ''


def mssql_table_has_ft_index(engine: Engine,
                             tablename: str,
                             schemaname: str = MSSQL_DEFAULT_SCHEMA) -> bool:
    query = text("""
SELECT
    COUNT(*)
FROM
    sys.key_constraints AS kc
    INNER JOIN sys.tables AS ta ON ta.object_id = kc.parent_object_id
    INNER JOIN sys.schemas AS s ON ta.schema_id = s.schema_id
    INNER JOIN sys.fulltext_indexes AS fi ON fi.object_id = ta.object_id
WHERE
    ta.name = :tablename
    AND s.name = :schemaname
    """).bindparams(
        tablename=tablename,
        schemaname=schemaname,
    )
    with contextlib.closing(engine.execute(query)) as result:  # type: ResultProxy  # noqa
        row = result.fetchone()
        return row[0] > 0


def mssql_transaction_count(engine_or_conn: Union[Connection, Engine]) -> int:
    sql = "SELECT @@TRANCOUNT"
    with contextlib.closing(engine_or_conn.execute(sql)) as result:  # type: ResultProxy  # noqa
        row = result.fetchone()
        return row[0] if row else None


def add_index(engine: Engine,
              sqla_column: Column = None,
              multiple_sqla_columns: List[Column] = None,
              unique: bool = False,
              fulltext: bool = False,
              length: int = None) -> None:
    # We used to process a table as a unit; this makes index creation faster
    # (using ALTER TABLE).
    # http://dev.mysql.com/doc/innodb/1.1/en/innodb-create-index-examples.html  # noqa
    # ... ignored in transition to SQLAlchemy
    is_mssql = engine.dialect.name == 'mssql'
    is_mysql = engine.dialect.name == 'mysql'

    multiple_sqla_columns = multiple_sqla_columns or []
    if multiple_sqla_columns and not (fulltext and is_mssql):
        raise ValueError("add_index: Use multiple_sqla_columns only for mssql "
                         "(Microsoft SQL Server) full-text indexing")
    if bool(multiple_sqla_columns) == (sqla_column is not None):
        raise ValueError(
            "add_index: Use either sqla_column or multiple_sqla_columns, not "
            "both (sqla_column = {}, multiple_sqla_columns = {}".format(
                repr(sqla_column), repr(multiple_sqla_columns)))
    if sqla_column is not None:
        colname = sqla_column.name
        sqla_table = sqla_column.table
    else:
        colname = ", ".join(c.name for c in multiple_sqla_columns)
        sqla_table = multiple_sqla_columns[0].table
        if any(c.table.name != tablename for c in multiple_sqla_columns[1:]):
            raise ValueError(
                "add_index: tablenames are inconsistent in "
                "multiple_sqla_columns = {}".format(
                    repr(multiple_sqla_columns)))
    tablename = sqla_table.name

    if fulltext:
        if is_mssql:
            idxname = ''  # they are unnamed
        else:
            idxname = "_idxft_{}".format(colname)
    else:
        idxname = "_idx_{}".format(colname)
    if idxname and index_exists(engine, tablename, idxname):
        log.info("Skipping creation of index {} on table {}; already "
                 "exists".format(idxname, tablename))
        return
        # because it will crash if you add it again!
    log.info("Creating{ft} index {i} on table {t}, column {c}".format(
        ft=" full-text" if fulltext else "",
        i=idxname or "<unnamed>",
        t=tablename,
        c=colname))

    if fulltext:
        if is_mysql:
            log.warning('OK to ignore this warning: '
                        '"InnoDB rebuilding table to add column FTS_DOC_ID"')
            # https://dev.mysql.com/doc/refman/5.6/en/innodb-fulltext-index.html
            sql = (
                "ALTER TABLE {tablename} "
                "ADD FULLTEXT INDEX {idxname} ({colname})".format(
                    tablename=tablename,
                    idxname=idxname,
                    colname=colname,
                )
            )
            # DDL(sql, bind=engine).execute_if(dialect='mysql')
            DDL(sql, bind=engine).execute()

        elif is_mssql:  # Microsoft SQL Server
            # https://msdn.microsoft.com/library/ms187317(SQL.130).aspx
            # Argh! Complex.
            # Note that the database must also have had a
            #   CREATE FULLTEXT CATALOG somename AS DEFAULT;
            # statement executed on it beforehand.
            schemaname = engine.schema_for_object(sqla_table) or MSSQL_DEFAULT_SCHEMA  # noqa
            if mssql_table_has_ft_index(engine=engine,
                                        tablename=tablename,
                                        schemaname=schemaname):
                log.info(
                    "... skipping creation of full-text index on table {}; a "
                    "full-text index already exists for that table; you can "
                    "have only one full-text index per table, though it can "
                    "be on multiple columns".format(tablename))
                return
            pk_index_name = mssql_get_pk_index_name(
                engine=engine, tablename=tablename, schemaname=schemaname)
            if not pk_index_name:
                raise ValueError(
                    "To make a FULLTEXT index under SQL Server, we need to "
                    "know the name of the PK index, but couldn't find one "
                    "from get_pk_index_name() for table {}".format(
                        repr(tablename)))
            # We don't name the FULLTEXT index itself, but it has to relate
            # to an existing unique index.
            sql = (
                "CREATE FULLTEXT INDEX ON {tablename} ({colname}) "
                "KEY INDEX {keyidxname} ".format(
                    tablename=tablename,
                    keyidxname=pk_index_name,
                    colname=colname,
                )
            )
            # SQL Server won't let you do this inside a transaction:
            # "CREATE FULLTEXT INDEX statement cannot be used inside a user
            # transaction."
            # https://msdn.microsoft.com/nl-nl/library/ms191544(v=sql.105).aspx
            # So let's ensure any preceding transactions are completed, and
            # run the SQL in a raw way:
            # engine.execute(sql).execution_options(autocommit=False)
            # http://docs.sqlalchemy.org/en/latest/core/connections.html#understanding-autocommit
            #
            # ... lots of faff with this (see test code in no_transactions.py)
            # ... ended up using explicit "autocommit=True" parameter (for
            #     pyodbc); see create_indexes()
            transaction_count = mssql_transaction_count(engine)
            if transaction_count != 0:
                log.critical("SQL Server transaction count (should be 0): "
                             "{}".format(transaction_count))
                # Executing serial COMMITs or a ROLLBACK won't help here if
                # this transaction is due to Python DBAPI default behaviour.
            DDL(sql, bind=engine).execute()

            # The reversal procedure is DROP FULLTEXT INDEX ON tablename;

        else:
            log.error("Don't know how to make full text index on dialect "
                      "{}".format(engine.dialect.name))

    else:
        index = Index(idxname, sqla_column, unique=unique, mysql_length=length)
        index.create(engine)
    # Index creation doesn't require a commit.


# =============================================================================
# More DDL
# =============================================================================

def make_bigint_autoincrement_column(column_name: str,
                                     dialect: Dialect) -> Column:
    # noinspection PyUnresolvedReferences
    if dialect.name == 'mssql':
        return Column(column_name, BigInteger,
                      Sequence('dummy_name', start=1, increment=1))
    else:
        # return Column(column_name, BigInteger, autoincrement=True)
        # noinspection PyUnresolvedReferences
        raise AssertionError(
            "SQLAlchemy doesn't support non-PK autoincrement fields yet for "
            "dialect {}".format(repr(dialect.name)))
        # see http://stackoverflow.com/questions/2937229


def column_creation_ddl(sqla_column: Column, dialect: Dialect) -> str:
    """
    The column should already be bound to a table (because e.g. the SQL Server
    dialect requires this for DDL generation).

    Manual testing:

        from sqlalchemy.schema import Column, CreateColumn, MetaData, Sequence, Table
        from sqlalchemy.sql.sqltypes import BigInteger
        from sqlalchemy.dialects.mssql.base import MSDialect
        dialect = MSDialect()
        col1 = Column('hello', BigInteger, nullable=True)
        col2 = Column('world', BigInteger, autoincrement=True)  # does NOT generate IDENTITY
        col3 = Column('you', BigInteger, Sequence('dummy_name', start=1, increment=1))
        metadata = MetaData()
        t = Table('mytable', metadata)
        t.append_column(col1)
        t.append_column(col2)
        t.append_column(col3)
        print(str(CreateColumn(col1).compile(dialect=dialect)))  # hello BIGINT NULL
        print(str(CreateColumn(col2).compile(dialect=dialect)))  # world BIGINT NULL
        print(str(CreateColumn(col3).compile(dialect=dialect)))  # you BIGINT NOT NULL IDENTITY(1,1)

    If you don't append the column to a Table object, the DDL generation step
    gives:

        sqlalchemy.exc.CompileError: mssql requires Table-bound columns in
        order to generate DDL
    """  # noqa
    return str(CreateColumn(sqla_column).compile(dialect=dialect))


# noinspection PyUnresolvedReferences
def giant_text_sqltype(dialect: Dialect) -> str:
    """
    Args:
        dialect: a SQLAlchemy dialect class
    Returns:
        the SQL data type of "giant text", typically 'LONGTEXT' for MySQL
        and 'NVARCHAR(MAX)' for SQL Server.
    """
    if dialect.name == 'mssql':
        return 'NVARCHAR(MAX)'
    elif dialect.name == 'mysql':
        return 'LONGTEXT'
    else:
        raise ValueError("Unknown dialect: {}".format(dialect.name))


# =============================================================================
# SQLAlchemy column types
# =============================================================================

# -----------------------------------------------------------------------------
# Reverse a textual SQL column type to an SQLAlchemy column type
# -----------------------------------------------------------------------------

RE_COLTYPE_WITH_COLLATE = re.compile(r'(?P<maintype>.+) COLLATE .+')
RE_COLTYPE_WITH_ONE_PARAM = re.compile(r'(?P<type>\w+)\((?P<size>\w+)\)')
RE_COLTYPE_WITH_TWO_PARAMS = re.compile(
    r'(?P<type>\w+)\((?P<size>\w+),\s*(?P<dp>\w+)\)')
# http://www.w3schools.com/sql/sql_create_table.asp


def _get_sqla_coltype_class_from_str(coltype: str,
                                     dialect: Dialect) -> Type[Column]:
    """
    Upper- and lower-case search.
    For example, the SQLite dialect uses upper case, and the
    MySQL dialect uses lower case.
    """
    # noinspection PyUnresolvedReferences
    ischema_names = dialect.ischema_names
    try:
        return ischema_names[coltype.upper()]
    except KeyError:
        return ischema_names[coltype.lower()]


@lru_cache(maxsize=None)
def get_sqla_coltype_from_dialect_str(coltype: str,
                                      dialect: Dialect) -> TypeEngine:
    """
    Args:
        dialect: a SQLAlchemy dialect class
        coltype: a str() representation, e.g. from str(c['type']) where
            c is an instance of sqlalchemy.sql.schema.Column.
    Returns:
        a Python object that is a subclass of sqlalchemy.types.TypeEngine
    Example:
        get_sqla_coltype_from_string('INTEGER(11)', engine.dialect)
            -> Integer(length=11)

    Notes:
        -   sqlalchemy.engine.default.DefaultDialect is the dialect base class
        -   a dialect contains these things of interest:
                ischema_names: string-to-class dictionary
                type_compiler: instance of e.g.
                    sqlalchemy.sql.compiler.GenericTypeCompiler
                    ... has a process() method
                    ... but that operates on TypeEngine objects
                get_columns: takes a table name, inspects the database
        -   example of the dangers of eval:
            http://nedbatchelder.com/blog/201206/eval_really_is_dangerous.html
        -   An example of a function doing the reflection/inspection within
            SQLAlchemy is sqlalchemy.dialects.mssql.base.MSDialect.get_columns,
            which has this lookup:
                coltype = self.ischema_names.get(type, None)

    Caveats:
        -   the parameters, e.g. DATETIME(6), do NOT necessarily either work at
            all or work correctly. For example, SQLAlchemy will happily spit
            out 'INTEGER(11)' but its sqlalchemy.sql.sqltypes.INTEGER class
            takes no parameters, so you get:
                TypeError: object() takes no parameters
            Similarly, MySQL's DATETIME(6) uses the 6 to refer to precision,
            but the DATETIME class in SQLAlchemy takes only a boolean parameter
            (timezone).
        -   However, sometimes we have to have parameters, e.g. VARCHAR length.
        -   Thus, this is a bit useless.
        -   Fixed, with a few special cases.
    """
    size = None
    dp = None
    args = []
    kwargs = {}

    try:
        # Split e.g. "VARCHAR(32) COLLATE blah" into "VARCHAR(32)", "who cares"
        m = RE_COLTYPE_WITH_COLLATE.match(coltype)
        if m is not None:
            coltype = m.group('maintype')

        # Split e.g. "DECIMAL(10, 2)" into DECIMAL, 10, 2
        m = RE_COLTYPE_WITH_TWO_PARAMS.match(coltype)
        if m is not None:
            basetype = m.group('type').upper()
            size = ast.literal_eval(m.group('size'))
            dp = ast.literal_eval(m.group('dp'))
        else:
            # Split e.g. "VARCHAR(32)" into VARCHAR, 32
            m = RE_COLTYPE_WITH_ONE_PARAM.match(coltype)
            if m is not None:
                basetype = m.group('type').upper()
                size_text = m.group('size').strip().upper()
                if size_text != 'MAX':
                    size = ast.literal_eval(size_text)
            else:
                basetype = coltype.upper()

        # Special cases: pre-processing
        # noinspection PyUnresolvedReferences
        if dialect.name == 'mssql' and basetype.lower() == 'integer':
            basetype = 'int'

        cls = _get_sqla_coltype_class_from_str(basetype, dialect)

        # Special cases: post-processing
        if basetype == 'DATETIME' and size:
            # First argument to DATETIME() is timezone, so...
            # noinspection PyUnresolvedReferences
            if dialect.name == 'mysql':
                kwargs = {'fsp': size}
            else:
                pass
        else:
            args = [x for x in (size, dp) if x is not None]

        try:
            return cls(*args, **kwargs)
        except TypeError:
            return cls()

    except:
        # noinspection PyUnresolvedReferences
        raise ValueError("Failed to convert SQL type {} in dialect {} to an "
                         "SQLAlchemy type".format(repr(coltype),
                                                  repr(dialect.name)))

# get_sqla_coltype_from_dialect_str("INTEGER", engine.dialect)
# get_sqla_coltype_from_dialect_str("INTEGER(11)", engine.dialect)
# get_sqla_coltype_from_dialect_str("VARCHAR(50)", engine.dialect)
# get_sqla_coltype_from_dialect_str("DATETIME", engine.dialect)
# get_sqla_coltype_from_dialect_str("DATETIME(6)", engine.dialect)


# =============================================================================
# Do special dialect conversions on SQLAlchemy SQL types (of class type)
# =============================================================================

def remove_collation(coltype: TypeEngine) -> TypeEngine:
    if not getattr(coltype, 'collation', None):
        return coltype
    newcoltype = copy.copy(coltype)
    newcoltype.collation = None
    return newcoltype


@lru_cache(maxsize=None)
def convert_sqla_type_for_dialect(
        coltype: TypeEngine,
        dialect: Dialect,
        strip_collation: bool = True,
        convert_mssql_timestamp: bool = True,
        expand_for_scrubbing: bool = False) -> TypeEngine:
    """
    - The purpose of expand_for_scrubbing is that, for example, a VARCHAR(200)
      field containing one or more instances of "Jones", where "Jones" is to be
      replaced with "[XXXXXX]", will get longer (by an unpredictable amount).
      So, better to expand to unlimited length.
    """
    # log.critical("Incoming coltype: {}, vars={}".format(repr(coltype),
    #                                                     vars(coltype)))
    # noinspection PyUnresolvedReferences
    to_mysql = dialect.name == 'mysql'
    # noinspection PyUnresolvedReferences
    to_mssql = dialect.name == 'mssql'
    typeclass = type(coltype)
    
    # -------------------------------------------------------------------------
    # Text
    # -------------------------------------------------------------------------
    if isinstance(coltype, sqltypes.UnicodeText):
        # Unbounded Unicode text.
        # Includes derived classes such as mssql.base.NTEXT.
        return sqltypes.UnicodeText()
    if isinstance(coltype, sqltypes.Text):
        # Unbounded text, more generally. (UnicodeText inherits from Text.)
        # Includes sqltypes.TEXT.
        return sqltypes.Text()
    # Everything inheriting from String has a length property, but can be None.
    # There are types that can be unlimited in SQL Server, e.g. VARCHAR(MAX)
    # and NVARCHAR(MAX), that MySQL needs a length for. (Failure to convert
    # gives e.g.: 'NVARCHAR requires a length on dialect mysql'.)
    if isinstance(coltype, sqltypes.Unicode):
        # Includes NVARCHAR(MAX) in SQL -> NVARCHAR() in SQLAlchemy.
        if (coltype.length is None and to_mysql) or expand_for_scrubbing:
            return sqltypes.UnicodeText()
    # The most general case; will pick up any other string types.
    if isinstance(coltype, sqltypes.String):
        # Includes VARCHAR(MAX) in SQL -> VARCHAR() in SQLAlchemy
        if (coltype.length is None and to_mysql) or expand_for_scrubbing:
            return sqltypes.Text()
        if strip_collation:
            return remove_collation(coltype)
        return coltype

    # -------------------------------------------------------------------------
    # Binary
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # BIT
    # -------------------------------------------------------------------------
    if typeclass == mssql.base.BIT and to_mysql:
        # MySQL BIT objects have a length attribute.
        return mysql.base.BIT()

    # -------------------------------------------------------------------------
    # TIMESTAMP
    # -------------------------------------------------------------------------
    if (isinstance(coltype, sqltypes.TIMESTAMP) and to_mssql and
            convert_mssql_timestamp):
        # You cannot write explicitly to a TIMESTAMP field in SQL Server; it's
        # used for autogenerated values only.
        # - http://stackoverflow.com/questions/10262426/sql-server-cannot-insert-an-explicit-value-into-a-timestamp-column  # noqa
        # - https://social.msdn.microsoft.com/Forums/sqlserver/en-US/5167204b-ef32-4662-8e01-00c9f0f362c2/how-to-tranfer-a-column-with-timestamp-datatype?forum=transactsql  # noqa
        #   ... suggesting BINARY(8) to store the value.
        # MySQL is more helpful:
        # - http://stackoverflow.com/questions/409286/should-i-use-field-datetime-or-timestamp  # noqa
        return mssql.base.BINARY(8)

    # -------------------------------------------------------------------------
    # Some other type
    # -------------------------------------------------------------------------
    return coltype


# =============================================================================
# Questions about SQLAlchemy column types
# =============================================================================

def is_sqlatype_binary(coltype: TypeEngine) -> bool:
    # Several binary types inherit internally from _Binary, making that the
    # easiest to check.

    # noinspection PyProtectedMember
    return isinstance(coltype, sqltypes._Binary)


def is_sqlatype_date(coltype: TypeEngine) -> bool:
    # isinstance also cheerfully handles multiple inheritance, i.e. if you have
    # class A(object), class B(object), and class C(A, B), followed by x = C(),
    # then all of isinstance(x, A), isinstance(x, B), isinstance(x, C) are True

    # noinspection PyProtectedMember
    return isinstance(coltype, sqltypes._DateAffinity)


def is_sqlatype_integer(coltype: TypeEngine) -> bool:
    return isinstance(coltype, sqltypes.Integer)


def is_sqlatype_numeric(coltype: TypeEngine) -> bool:
    return isinstance(coltype, sqltypes.Numeric)  # includes Float, Decimal


def is_sqlatype_text_of_length_at_least(coltype: TypeEngine,
                                        min_length: int = 1000) -> bool:
    if not isinstance(coltype, sqltypes.String):
        return False  # not a string/text type at all
    if coltype.length is None:
        return True  # string of unlimited length
    return coltype.length >= min_length


def is_sqlatype_text_over_one_char(coltype: TypeEngine) -> bool:
    return is_sqlatype_text_of_length_at_least(coltype, 2)


def does_sqlatype_merit_fulltext_index(coltype: TypeEngine,
                                       min_length: int = 1000) -> bool:
    return is_sqlatype_text_of_length_at_least(coltype, min_length)


def does_sqlatype_require_index_len(coltype: TypeEngine) -> bool:
    # MySQL, at least, requires index length to be specified for BLOB and TEXT
    # columns: http://dev.mysql.com/doc/refman/5.7/en/create-index.html
    if isinstance(coltype, sqltypes.Text):
        return True
    if isinstance(coltype, sqltypes.LargeBinary):
        return True
    return False


# =============================================================================
# Hack in new type
# =============================================================================

def hack_in_mssql_xml_type():
    """
    SQLAlchemy does not support the XML type in SQL Server (mssql).
    Upon reflection, we get:
       sqlalchemy\dialects\mssql\base.py:1921: SAWarning: Did not recognize
       type 'xml' of column '...'

    We will convert anything of type XML into type TEXT.

    """
    log.debug("Adding type 'xml' to SQLAlchemy reflection for dialect 'mssql'")
    mssql.base.ischema_names['xml'] = mssql.base.TEXT
    # http://stackoverflow.com/questions/32917867/sqlalchemy-making-schema-reflection-find-use-a-custom-type-for-all-instances  # noqa

    # print(repr(mssql.base.ischema_names.keys()))
    # print(repr(mssql.base.ischema_names))


# =============================================================================
# Check column definition equality
# =============================================================================

def column_types_equal(a_coltype: TypeEngine, b_coltype: TypeEngine) -> bool:
    # http://stackoverflow.com/questions/34787794/sqlalchemy-column-type-comparison  # noqa
    # IMPERFECT:
    return str(a_coltype) == str(b_coltype)


def columns_equal(a: Column, b: Column) -> bool:
    return (
        a.name == b.name and
        column_types_equal(a.type, b.type) and
        a.nullable == b.nullable
    )


def column_lists_equal(a: List[Column], b: List[Column]) -> bool:
    n = len(a)
    if len(b) != n:
        return False
    for i in range(n):
        if not columns_equal(a[i], b[i]):
            log.debug("Mismatch: {} != {}".format(repr(a[i]), repr(b[i])))
            return False
    return True


def indexes_equal(a: Index, b: Index) -> bool:
    # Unsure.
    return str(a) == str(b)


def index_lists_equal(a: List[Index], b: List[Index]) -> bool:
    n = len(a)
    if len(b) != n:
        return False
    for i in range(n):
        if not indexes_equal(a[i], b[i]):
            log.debug("Mismatch: {} != {}".format(repr(a[i]), repr(b[i])))
            return False
    return True


# =============================================================================
# Tests
# =============================================================================

def test_assert(x, y) -> None:
    try:
        assert x == y
    except AssertionError:
        print("{} should have been {}".format(repr(x), repr(y)))
        raise


def unit_tests() -> None:
    from sqlalchemy.dialects.mssql.base import MSDialect
    from sqlalchemy.dialects.mysql.base import MySQLDialect
    d_mssql = MSDialect()
    d_mysql = MySQLDialect()
    col1 = Column('hello', BigInteger, nullable=True)
    col2 = Column('world', BigInteger,
                  autoincrement=True)  # does NOT generate IDENTITY
    col3 = make_bigint_autoincrement_column('you', d_mssql)
    metadata = MetaData()
    t = Table('mytable', metadata)
    t.append_column(col1)
    t.append_column(col2)
    t.append_column(col3)

    print("Checking Column -> DDL: SQL Server (mssql)")
    test_assert(column_creation_ddl(col1, d_mssql), "hello BIGINT NULL")
    test_assert(column_creation_ddl(col2, d_mssql), "world BIGINT NULL")
    test_assert(column_creation_ddl(col3, d_mssql),
                "you BIGINT NOT NULL IDENTITY(1,1)")

    print("Checking Column -> DDL: MySQL (mysql)")
    test_assert(column_creation_ddl(col1, d_mysql), "hello BIGINT")
    test_assert(column_creation_ddl(col2, d_mysql), "world BIGINT")
    # not col3; unsupported

    print("Checking SQL type -> SQL Alchemy type")
    to_check = [
        # mssql
        ("BIGINT", d_mssql),
        ("NVARCHAR(32)", d_mssql),
        ("NVARCHAR(MAX)", d_mssql),
        ('NVARCHAR(160) COLLATE "Latin1_General_CI_AS"', d_mssql),
        # mysql
        ("BIGINT", d_mssql),
        ("LONGTEXT", d_mysql),
    ]
    for coltype, dialect in to_check:
        print("... {} -> dialect {} -> {}".format(
            repr(coltype),
            repr(dialect.name),
            repr(get_sqla_coltype_from_dialect_str(coltype, dialect))))


if __name__ == '__main__':
    unit_tests()
