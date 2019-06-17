#!/usr/bin/env python

"""
debugging/mssql_without_transaction.py

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

THE PROBLEM: SQL Server requires that a "CREATE FULLTEXT INDEX" command
happens outside all transactions. However, the Python DBAPI wishes that
everything happens inside a transaction. We have to reconcile these somehow.
The test environment uses pyodbc.

"""

import contextlib
from typing import Union

# noinspection PyPackageRequirements
import pyodbc
from sqlalchemy.engine.base import Connection, Engine
from sqlalchemy.engine import create_engine


def show_query(engine_or_conn: Union[Connection, Engine],
               sql: str) -> None:
    with contextlib.closing(engine_or_conn.execute(sql)) as result:
        print(f"{sql} -> {result.fetchall()}\n")


def execute(engine_or_conn: Union[Connection, Engine], sql: str) -> None:
    print("Executing: " + sql)
    engine_or_conn.execute(sql)


dsn = "XXX"
username = "XXX"
password = "XXX"
url = f"mssql+pyodbc://{username}:{password}@{dsn}"
pyodbc_connect_str = f"DSN={dsn};UID={username};PWD={password}"

query_trancount = "SELECT @@TRANCOUNT"
# From SQL Server Management Studio: @@TRANCOUNT starts at 0.

engine = create_engine(url)
raw_conn = engine.raw_connection()
print("SQLAlchemy engine.raw_connection():")
show_query(raw_conn, query_trancount)  # 1
print("SQLAlchemy engine:")
show_query(engine, query_trancount)  # 1

print("pyodbc default:")
pyodbc_conn = pyodbc.connect(pyodbc_connect_str)
show_query(pyodbc_conn, query_trancount)  # 1

print("pyodbc connect(..., autocommit=True):")
pyodbc_conn_2 = pyodbc.connect(pyodbc_connect_str, autocommit=True)
show_query(pyodbc_conn_2, query_trancount)  # 0  -- HERE! That's what we want.

print("pyodbc connect(..., autocommit=False):")
pyodbc_conn_3 = pyodbc.connect(pyodbc_connect_str, autocommit=False)
show_query(pyodbc_conn_3, query_trancount)  # 1

"""
In the pyodbc source, a connect() call goes like this:

- pyodbcmodule.cpp / mod_connect()
  sets fAutoCommit as Python boolean value from "autocommit" parameter
  calls Connection_New()

- connection.cpp / Connection_New()
  sets cnxn->nAutoCommit = fAutoCommit ? SQL_AUTOCOMMIT_ON : SQL_AUTOCOMMIT_OFF;

  (cnxn is of type Connection, defined in connection.h)

  then, the start-of-transaction stuff is controlled by this function calling
  SQLSetConnectAttr(cnxn->hdbc, SQL_ATTR_AUTOCOMMIT, ...) if (fAutoCommit == false)

- in cursor.cpp, Cursor_exit() reads it as well

- SQLSetConnectAttr is an ODBC function:
  https://docs.microsoft.com/en-us/sql/odbc/reference/syntax/sqlsetconnectattr-function

"""  # noqa

print("SQLAlchemy engine again:")
show_query(engine, query_trancount)  # 1
execute(engine, "COMMIT")
show_query(engine, query_trancount)  # 1
execute(engine, "SET IMPLICIT_TRANSACTIONS OFF")
execute(engine, "COMMIT")
execute(engine, "COMMIT")
execute(engine, "COMMIT")
show_query(engine, query_trancount)  # 1
execute(engine, "ROLLBACK")
show_query(engine, query_trancount)  # 1

show_query(engine, query_trancount)  # 1
execute(engine, "SET IMPLICIT_TRANSACTIONS ON")
execute(engine, "COMMIT")
execute(engine, "COMMIT")
execute(engine, "COMMIT")
show_query(engine, query_trancount)  # 1
execute(engine, "ROLLBACK")
show_query(engine, query_trancount)  # 1
