#!/usr/bin/env python
# crate_anon/anonymise/sqla.py

import ast
import logging
import re

from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.schema import DDL, Index
from sqlalchemy.sql import exists, func, select, table
from sqlalchemy.sql.expression import (
    ClauseElement,
    Insert,
    TableClause,
)

log = logging.getLogger(__name__)


# =============================================================================
# Get or create (SQLAlchemy ORM)
# =============================================================================
# http://stackoverflow.com/questions/2546207
# ... composite of several suggestions

def get_or_create(session, model, defaults=None, **kwargs):
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
# SELECT COUNT(*) (SQLAlchemy Core)
# =============================================================================
# http://stackoverflow.com/questions/12941416

def count_star(session, tablename):
    # works if you pass a connection or a session
    query = select([func.count()]).select_from(table(tablename))
    return session.execute(query).scalar()


# =============================================================================
# SELECT EXISTS (SQLAlchemy Core)
# =============================================================================
# http://stackoverflow.com/questions/15381604
# http://docs.sqlalchemy.org/en/latest/orm/query.html

def plain_exists(session, tablename, *criteria):
    # works if you pass a connection or a session
    exists_clause = exists().select_from(table(tablename))
    for criterion in criteria:
        exists_clause = exists_clause.where(criterion)
    query = select([exists_clause])
    return session.execute(query).scalar()


def orm_exists(session, ormclass, *criteria):
    # http://docs.sqlalchemy.org/en/latest/orm/query.html
    q = session.query(ormclass)
    for criterion in criteria:
        q = q.filter(criterion)
    return session.query(q.exists()).scalar()


# =============================================================================
# Inspect tables (SQLAlchemy Core)
# =============================================================================

def get_table_names(engine):
    insp = Inspector.from_engine(engine)
    return insp.get_table_names()


def get_columns(engine, tablename):
    insp = Inspector.from_engine(engine)
    return insp.get_columns(tablename)


def get_column_names(engine, tablename):
    return [x['name'] for x in get_columns(engine, tablename)]


# =============================================================================
# Indexes
# =============================================================================

def index_exists(engine, tablename, indexname):
    insp = Inspector.from_engine(engine)
    return any([i['name'] == indexname for i in insp.get_indexes(tablename)])


def add_index(engine, sqla_column, unique=False, fulltext=False, length=None):
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
            log.error(
                "Don't know how to make full text index on dialect {}".format(
                    engine.dialect.name))
    else:
        index = Index(idxname, sqla_column, unique=unique, mysql_length=length)
        index.create(engine)
    # Index creation doesn't require a commit.


# =============================================================================
# Reverse a textual SQL column type to an SQLAlchemy column type
# =============================================================================

RE_COLTYPE_WITH_PARAMS = re.compile(r'(?P<type>\w+)\((?P<size>\w+)\)')
# http://www.w3schools.com/sql/sql_create_table.asp


def _get_sqla_coltype_class_from_str(engine, coltype):
    """
    As-is/lower-case search.
    For example, the SQLite dialect uses upper case, and the
    MySQL dialect uses lower case.
    """
    ischema_names = engine.dialect.ischema_names
    try:
        return ischema_names[coltype]
    except KeyError:
        return ischema_names[coltype.lower()]


def get_sqla_coltype_from_dialect_str(engine, coltype):
    """
    Args:
        engine: a SQLAlchemy engine
        coltype: a str() representation, e.g. from str(c['type']) where
            c is an instance of sqlalchemy.sql.schema.Column.
    Returns:
        a Python object that is a subclass of sqlalchemy.types.TypeEngine
    Example:
        get_sqla_coltype_from_string(engine, 'INTEGER(11)')
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
    args = []
    kwargs = {}
    m = RE_COLTYPE_WITH_PARAMS.match(coltype)
    if m is not None:
        basetype = m.group('type').upper()
        size = ast.literal_eval(m.group('size'))
    else:
        basetype = coltype.upper()
    cls = _get_sqla_coltype_class_from_str(engine, basetype)
    # Special cases
    if basetype == 'DATETIME' and size:
        # First argument to DATETIME() is timezone, so...
        if engine.dialect.name == 'mysql':
            kwargs = {'fsp': size}
        else:
            pass
    else:
        args = [size] if size is not None else []
    try:
        return cls(*args, **kwargs)
    except TypeError:
        return cls()

# get_sqla_coltype_from_dialect_str(engine, "INTEGER")
# get_sqla_coltype_from_dialect_str(engine, "INTEGER(11)")
# get_sqla_coltype_from_dialect_str(engine, "VARCHAR(50)")
# get_sqla_coltype_from_dialect_str(engine, "DATETIME")
# get_sqla_coltype_from_dialect_str(engine, "DATETIME(6)")


# =============================================================================
# INSERT ... ON DUPLICATE KEY UPDATE
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
