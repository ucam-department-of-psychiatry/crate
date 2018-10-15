#!/usr/bin/env python

"""
ditched/test_sqla_reflection.py

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

**Test SQLAlchemy reflection.**

"""

import os
# import sys

from sqlalchemy import (
    column,
    Column,
    create_engine,
    exists,
    func,
    # ForeignKey,
    Integer,
    select,
    String,
    Table,
    table,
)
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import MetaData


MEMORY_URL = 'sqlite:///:memory:'
ormmeta = MetaData()
Base = declarative_base(metadata=ormmeta)


# =============================================================================
# Reflection
# =============================================================================
# http://docs.sqlalchemy.org/en/latest/core/reflection.html

def test_reflection(url, echo=True):
    engine = create_engine(url, echo=echo)
    conn = engine.connect()
    meta = MetaData()
    meta.reflect(bind=engine)
    # http://docs.sqlalchemy.org/en/rel_1_0/core/metadata.html

    # for t in meta.sorted_tables:
    #     # http://docs.sqlalchemy.org/en/rel_1_0/core/metadata.html#sqlalchemy.schema.Table  # noqa
    #     print("=" * 79)
    #     print(t.name)
    #     # print(t.__dict__)
    #     print(t.columns)

    # http://docs.sqlalchemy.org/en/latest/core/reflection.html#sqlalchemy.engine.reflection.Inspector  # noqa
    insp = Inspector.from_engine(engine)
    for t in insp.get_table_names():
        descriptions = []
        for col in insp.get_columns(t):
            name = col['name']
            coltype = col['type']  # e.g. salalchemy.dialects.mysql.base.INTEGER  # noqa
            sqltype = str(coltype)  # e.g. "INTEGER(11)"
            sqlatype = repr(coltype)
            descriptions.append("{name}: {sqltype} / {sqlatype}".format(
                name=name, sqltype=sqltype, sqlatype=sqlatype))
            # print(
            #     "Column: name={name}, raw SQL type={sqltype}, object={obj}, "
            #     "column object type={objtype}, "
            #     "column type type={typetype}".format(
            #         name=name, sqltype=sqltype, obj=col, objtype=type(col),
            #         typetype=type(coltype)))
        print("=" * 79)
        print(t)
        print("=" * 79)
        print("COUNT(*): {}".format(count_star(conn, t)))
        # print("EXISTS test: {}".format(
        #     plain_exists(conn, t, column('brcid')==3)))
        print("\n".join(descriptions))
        print()

    for v in insp.get_view_names():
        print("View: " + v)


# =============================================================================
# Create table
# =============================================================================
# http://stackoverflow.com/questions/2580497/database-on-the-fly-with-scripting-languages/2580543#2580543  # noqa

def test_create(echo=True):
    engine = create_engine(MEMORY_URL, echo=echo)

    metadata = MetaData()

    user = Table(
        'user',
        metadata,
        Column('user_id', Integer, primary_key=True),
        Column('user_name', String(16), nullable=False),
        Column('email_address', String(60), key='email'),
        Column('password', String(20), nullable=False)
    )
    user.create(engine, checkfirst=True)
    user.create(engine, checkfirst=True)


# =============================================================================
# ORM
# =============================================================================

class OrmThing(Base):
    __tablename__ = 'ormthing'
    intthing = Column('intthing', Integer, primary_key=True)


def test_orm(echo=True):
    engine = create_engine(MEMORY_URL, echo=echo)
    OrmThing.__table__.create(engine, checkfirst=True)


# =============================================================================
# SQL Server
# =============================================================================

def test_sqlserver(echo=True):
    user = 'researcher'
    password = 'blibble'
    freetdsname = 'crate_sqlserver_test'  # /etc/freetds/freetds.conf
    url = (
        'mssql+pymssql://{user}:{password}@{freetdsname}/?charset=utf8'.format(
            user=user, password=password, freetdsname=freetdsname))
    print(url)
    test_reflection(url, echo=echo)


# =============================================================================
# Counting
# =============================================================================

def plain_exists(conn, tablename, *criteria):
    query = select([
        exists().where(*criteria).select_from(table(tablename))
    ])
    return conn.execute(query).scalar()


def count_star(conn, tablename):
    query = select([func.count()]).select_from(tablename)
    return conn.execute(query).scalar()


# =============================================================================
# Main
# =============================================================================

if __name__ == '__main__':
    crate_url = os.environ['TMP_CRATE_SQLA_URL_RESEARCH']
    print("Using URL: {}".format(crate_url))
    # test_create()
    # test_sqlserver()
    test_reflection(crate_url)
    # test_orm()

