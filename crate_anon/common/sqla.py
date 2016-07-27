#!/usr/bin/env python
# crate_anon/anonymise/sqla.py

import ast
import copy
import logging
import re
from typing import Any, Dict, List, Tuple, Type

from sqlalchemy.dialects import mssql, mysql
from sqlalchemy.engine import Engine
# from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.declarative.api import DeclarativeMeta
from sqlalchemy.schema import Column, DDL, Index
from sqlalchemy.orm.session import Session
from sqlalchemy.sql import exists, func, select, sqltypes, table
from sqlalchemy.sql.expression import (
    ClauseElement,
    Insert,
    TableClause,
)

log = logging.getLogger(__name__)


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

def count_star(session: Session, tablename: str) -> int:
    # works if you pass a connection or a session
    query = select([func.count()]).select_from(table(tablename))
    return session.execute(query).scalar()


# -----------------------------------------------------------------------------
# SELECT EXISTS (SQLAlchemy Core)
# -----------------------------------------------------------------------------
# http://stackoverflow.com/questions/15381604
# http://docs.sqlalchemy.org/en/latest/orm/query.html

def exists_plain(session: Session, tablename: str, *criteria: Any) -> bool:
    # works if you pass a connection or a session
    exists_clause = exists().select_from(table(tablename))
    for criterion in criteria:
        exists_clause = exists_clause.where(criterion)
    query = select([exists_clause])
    return session.execute(query).scalar()


def exists_orm(session: Session,
               ormclass: DeclarativeMeta,
               *criteria: Any) -> bool:
    # http://docs.sqlalchemy.org/en/latest/orm/query.html
    q = session.query(ormclass)
    for criterion in criteria:
        q = q.filter(criterion)
    return session.query(q.exists()).scalar()


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


def get_columns(engine: Engine, tablename: str) -> List[Column]:
    insp = Inspector.from_engine(engine)
    return insp.get_columns(tablename)


def get_column_names(engine: Engine, tablename: str) -> List[str]:
    return [x['name'] for x in get_columns(engine, tablename)]


# =============================================================================
# Indexes
# =============================================================================

def index_exists(engine: Engine, tablename: str, indexname: str) -> bool:
    insp = Inspector.from_engine(engine)
    return any(i['name'] == indexname for i in insp.get_indexes(tablename))


def add_index(engine: Engine,
              sqla_column: Column,
              unique: bool = False,
              fulltext: bool = False,
              length: int = None) -> None:
    # We used to process a table as a unit; this makes index creation faster
    # (using ALTER TABLE).
    # http://dev.mysql.com/doc/innodb/1.1/en/innodb-create-index-examples.html  # noqa
    # ... ignored in transition to SQLAlchemy
    colname = sqla_column.name
    tablename = sqla_column.table.name
    if fulltext:
        idxname = "_idxft_{}".format(colname)
    else:
        idxname = "_idx_{}".format(colname)
    if index_exists(engine, tablename, idxname):
        log.debug("skipping creation of index {} on table {}".format(
            idxname, tablename))
        return
        # because it will crash if you add it again!
    log.info("Creating index {i} on {t}.{c}".format(i=idxname, t=tablename,
                                                    c=colname))
    if fulltext:
        if engine.dialect.name == 'mysql':
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
        else:
            log.error("Don't know how to make full text index on dialect "
                      "{}".format(engine.dialect.name))
    else:
        index = Index(idxname, sqla_column, unique=unique, mysql_length=length)
        index.create(engine)
    # Index creation doesn't require a commit.


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
                                     dialect: Any) -> Type[Column]:
    """
    As-is/lower-case search.
    For example, the SQLite dialect uses upper case, and the
    MySQL dialect uses lower case.
    """
    ischema_names = dialect.ischema_names
    try:
        return ischema_names[coltype]
    except KeyError:
        return ischema_names[coltype.lower()]


def get_sqla_coltype_from_dialect_str(coltype: str,
                                      dialect: Any) -> Column:
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
    
    # Split e.g. "VARCHAR(32) COLLATE blah" into "VARCHAR(32)" and "who cares"
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
            size = ast.literal_eval(m.group('size'))
        else:
            basetype = coltype.upper()

    # Special cases: pre-processing
    if dialect.name == 'mssql' and basetype.lower() == 'integer':
        basetype = 'int'

    cls = _get_sqla_coltype_class_from_str(basetype, dialect)

    # Special cases: post-processing
    if basetype == 'DATETIME' and size:
        # First argument to DATETIME() is timezone, so...
        if dialect.name == 'mysql':
            kwargs = {'fsp': size}
        else:
            pass
    else:
        args = [x for x in [size, dp] if x is not None]

    try:
        return cls(*args, **kwargs)
    except TypeError:
        return cls()

# get_sqla_coltype_from_dialect_str("INTEGER", engine.dialect)
# get_sqla_coltype_from_dialect_str("INTEGER(11)", engine.dialect)
# get_sqla_coltype_from_dialect_str("VARCHAR(50)", engine.dialect)
# get_sqla_coltype_from_dialect_str("DATETIME", engine.dialect)
# get_sqla_coltype_from_dialect_str("DATETIME(6)", engine.dialect)


# =============================================================================
# Do special dialect conversions on SQLAlchemy SQL types (of class type)
# =============================================================================

def remove_collation(coltype: Column) -> Column:
    if not hasattr(coltype, 'collation') or not coltype.collation:
        return coltype
    newcoltype = copy.copy(coltype)
    newcoltype.collation = None
    return newcoltype


def convert_sqla_type_for_dialect(coltype: Column,
                                  dialect: Any,
                                  strip_collation: bool = True) -> Column:
    # log.critical("Incoming coltype: {}, vars={}".format(repr(coltype),
    #                                                     vars(coltype)))
    to_mysql = dialect.name == 'mysql'
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
        if coltype.length is None and to_mysql:
            return sqltypes.UnicodeText()
    # The most general case; will pick up any other string types.
    if isinstance(coltype, sqltypes.String):
        # Includes VARCHAR(MAX) in SQL -> VARCHAR() in SQLAlchemy
        if coltype.length is None and to_mysql:
            return sqltypes.Text()
        if strip_collation:
            # noinspection PyTypeChecker
            return remove_collation(coltype)
        return coltype

    # -------------------------------------------------------------------------
    # BIT
    # -------------------------------------------------------------------------
    if typeclass == mssql.base.BIT and to_mysql:
        # MySQL BIT objects have a length attribute.
        return mysql.base.BIT()

    # Some other type
    return coltype


# =============================================================================
# Questions about SQLAlchemy column types
# =============================================================================

def is_sqlatype_binary(coltype: Column) -> bool:
    # Several binary types inherit internally from _Binary, making that the
    # easiest to check.

    # noinspection PyProtectedMember
    return isinstance(coltype, sqltypes._Binary)


def is_sqlatype_date(coltype: Column) -> bool:
    # isinstance also cheerfully handles multiple inheritance, i.e. if you have
    # class A(object), class B(object), and class C(A, B), followed by x = C(),
    # then all of isinstance(x, A), isinstance(x, B), isinstance(x, C) are True

    # noinspection PyProtectedMember
    return isinstance(coltype, sqltypes._DateAffinity)


def is_sqlatype_integer(coltype: Column) -> bool:
    return isinstance(coltype, sqltypes.Integer)


def is_sqlatype_numeric(coltype: Column) -> bool:
    return isinstance(coltype, sqltypes.Numeric)  # includes Float, Decimal


def is_sqlatype_text_of_length_at_least(coltype: Column,
                                        min_length: int = 1000) -> bool:
    if not isinstance(coltype, sqltypes.String):
        return False  # not a string/text type at all
    if coltype.length is None:
        return True  # string of unlimited length
    return coltype.length >= min_length


def is_sqlatype_text_over_one_char(coltype: Column) -> bool:
    return is_sqlatype_text_of_length_at_least(coltype, 2)


def does_sqlatype_merit_fulltext_index(coltype: Column,
                                       min_length: int = 1000) -> bool:
    return is_sqlatype_text_of_length_at_least(coltype, min_length)


def does_sqlatype_require_index_len(coltype: Column) -> bool:
    # MySQL, at least, requires index length to be specified for BLOB and TEXT
    # columns: http://dev.mysql.com/doc/refman/5.7/en/create-index.html
    if isinstance(coltype, sqltypes.Text):
        return True
    if isinstance(coltype, sqltypes.LargeBinary):
        return True
    return False
