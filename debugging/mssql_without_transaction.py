import contextlib
import pyodbc
from sqlalchemy.engine import create_engine


def show_query(engine_or_conn, sql):
    with contextlib.closing(engine_or_conn.execute(sql)) as result:
        print("{} -> {}\n".format(sql, result.fetchall()))


def exec(engine_or_conn, sql):
    print("Executing: " + sql)
    engine_or_conn.execute(sql)


dsn = "XXX"
username = "XXX"
password = "XXX"
url = "mssql+pyodbc://{u}:{p}@{d}".format(u=username, p=password, d=dsn)
pyodbc_connect_str = "DSN={d};UID={u};PWD={p}".format(u=username, p=password, d=dsn)

query_trancount = "SELECT @@TRANCOUNT"  # from SQL Server Management Studio: 0 to start with

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
show_query(pyodbc_conn_2, query_trancount)  # 0  -- HERE!

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


"""

print("SQLAlchemy engine again:")
show_query(engine, query_trancount)  # 1
exec(engine, "COMMIT")
show_query(engine, query_trancount)  # 1
exec(engine, "SET IMPLICIT_TRANSACTIONS OFF")
exec(engine, "COMMIT")
exec(engine, "COMMIT")
exec(engine, "COMMIT")
show_query(engine, query_trancount)  # 1
exec(engine, "ROLLBACK")
show_query(engine, query_trancount)  # 1

show_query(engine, query_trancount)  # 1
exec(engine, "SET IMPLICIT_TRANSACTIONS ON")
exec(engine, "COMMIT")
exec(engine, "COMMIT")
exec(engine, "COMMIT")
show_query(engine, query_trancount)  # 1
exec(engine, "ROLLBACK")
show_query(engine, query_trancount)  # 1
