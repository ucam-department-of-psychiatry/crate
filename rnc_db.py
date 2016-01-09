#!/usr/bin/python
# -*- encoding: utf8 -*-

"""Support functions to interface Python to SQL-based databases conveniently.

Author: Rudolf Cardinal (rudolf@pobox.com)
Created: October 2012
Last update: 6 Jan 2015

Copyright/licensing:

    Copyright (C) 2012-2015 Rudolf Cardinal (rudolf@pobox.com).

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

Regarding fieldspecs and fieldspec lists:

An individual fieldspec is a dictionary, e.g.
        { "name": "q1", "sqltype": "INTEGER" }
or
        dict(name="q1", sqltype="INTEGER")

Possible keys are:
    name: field name
    sqltype: SQL type
    notnull (optional): True for NOT NULL
    autoincrement (optional): true for AUTO_INCREMENT
    pk (optional): True for a PK
    unique (optional): True for a UNIQUE (but not PK) field
    comment (optional): string
    value (optional): value for an individual record (not currently used)
    indexed (optional): should the field be specifically indexed?
    index_nchar (optional): specify if the field needs an index key length

General note about Python None/NULL handling:
    # Fine:
    cursor.execute("SELECT * FROM mytable WHERE myfield=?", 1)
    # NOT fine; will return no rows:
    cursor.execute("SELECT * FROM mytable WHERE myfield=?", None)
    # Fine
    cursor.execute("SELECT * FROM mytable WHERE myfield IS NULL")

JDBC types:

    # http://webcache.googleusercontent.com/search?q=cache:WoMF0RGkqwgJ:www.tagwith.com/question_439319_jpype-and-jaydebeapi-returns-jpype-jclass-java-lang-long  # noqa

    The object returned by JPype is a Python version of Java's java.lang.Long
    class. To get the value out of it, use the value attribute:

        >>> n = java.lang.Long(44)
        >>> n
        <jpype._jclass.java.lang.Long object at 0x2377390>
        >>> n.value
        44L

    JayDeBeApi contains a dict (_DEFAULT_CONVERTERS) that maps types it
    recognises to functions that convert the Java values to Python values. This
    dict can be found at the bottom of the dbapi2.pysource code. BIGINT is not
    included in this dict, so objects of that database type don't get mapped
    out of Java objects into Python values.

    It's fairly easy to modify JayDeBeApi to add support for BIGINTs. Edit the
    dbapi2.py file that contains most of the JayDeBeApi code and add the line

        'BIGINT': _java_to_py('longValue'),
    to the _DEFAULT_CONVERTERS dict.
"""

# =============================================================================
# Notes on setting up ODBC
# =============================================================================

# Open database connection.
# There's no direct Python equivalent of DBI
# (which can talk to e.g. ODBC and MySQL).
# So we'll use ODBC. On Windows, that comes by default.
# For IODBC: sudo apt-get install iodbc libiodbc2-dev. Then see
# http://www.iodbc.org/dataspace/iodbc/wiki/iODBC/IODBCPythonHOWTO .
# This uses ~/.odbc.ini .
# Or, for MySQL, sudo apt-get install iodbc libmyodbc. Then see
# https://help.ubuntu.com/community/ODBC . This uses /etc/odbc.ini .
# Or UnixODBC: sudo apt-get install unixodbc unixodbc-dev. Then see
# http://ubuntu-virginia.ubuntuforums.org/showthread.php?p=5846508 .
# WE'RE GOING THIS WAY.
# The Python interface to ODBC is pyodbc:
# http://code.google.com/p/pyodbc/wiki/GettingStarted
# To install pyodbc (see in part
#       http://www.easysoft.com/developer/languages/python/pyodbc.html):
#   METHOD 1
#       * sudo apt-get install python-all-dev (to get development headers)
#       * download e.g. pyodbc-2.1.6.zip from
#           http://code.google.com/p/pyodbc/downloads/list
#       * unzip pyodbc-2.1.6.zip
#       * cd pyodbc-2.1.6
#       * amend setup.py: FOR IODBC: change "libraries.append('odbc')" to
#               "libraries.append('iodbc')"...
#       * amend setup.py: FOR LIBMYODBC: not yet worked out
#       * amend setup.py: FOR UNIXODBC: works as is
#       * sudo python setup.py install
#   METHOD 2
#       * sudo apt-get install python-pyodbc
# Now, for unixodbc, set it up:
#   * edit /etc/odbcinst.ini to be e.g.:
#       [myodbc]
#       Description = MySQL ODBC 3.51 Driver (this can be an arbitrary name)
#       Driver = /usr/lib/odbc/libmyodbc.so
#       Setup = /usr/lib/odbc/libodbcmyS.so
#       FileUsage       = 1
#   * edit /etc/odbc.ini to be e.g.
#       [mysql-testdb]
#       Driver       = myodbc
#       Description  = mysql_egret_testdb NEEDS SSH TUNNEL
#       SERVER       = 127.0.0.1 # do not use "localhost" or the driver will
#           # look in /var/run/mysqld/mysqld.sock, instead of looking at PORT
#       PORT         = 3306
#       Database     = testdb
#       OPTION       = 3
# Now test:
#   * isql mysql-testdb USER PASSWORD
#   * python tests/dbapitests.py python tests/dbapitests.py \
#       "DSN=mysql-testdb;UID=xxx;PWD=xxx"
#
# Ultraquick Python connection:
#   import MySQLdb
#   db = MySQLdb.connect(host = "127.0.0.1", port = 3306, user = "root",
#           passwd = "XXX", db = "YYY", charset = "utf8", use_unicode = True)
#   c = db.cursor()
#   c.execute("SELECT * FROM ZZZ")
#   c.fetchone()


# =============================================================================
# Imports
# =============================================================================

import binascii
import datetime
import re
import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
logger.setLevel(logging.INFO)
import six
from six.moves import range
import time

# 1. An ODBC driver
try:
    import pyodbc  # Python 2: "sudo pip install pyodbc"; Python 3: "sudo pip3 install pyodbc"  # noqa
    PYODBC_AVAILABLE = True
except ImportError:
    PYODBC_AVAILABLE = False

# 2. A JDBC driver
try:
    import jaydebeapi  # Python 2: "sudo pip install jaydebeapi"; Python 3: "sudo pip3 install jaydebeapi"  # noqa
    import jpype
    JDBC_AVAILABLE = True
except ImportError:
    JDBC_AVAILABLE = False

# 3. A direct MySQL driver
try:
    import pymysql  # Python 2: "sudo pip install PyMySQL"; Python 3: "sudo pip3 install PyMySQL"  # noqa
    # pymysql.converters is automatically available now
    mysql = pymysql
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False

MYSQLDB_AVAILABLE = False
if not PYMYSQL_AVAILABLE:
    try:
        import MySQLdb  # Python 2 (Debian): "sudo apt-get install python-mysqldb"  # noqa
        import MySQLdb.converters  # needs manual import
        import _mysql
        mysql = MySQLdb
        MYSQLDB_AVAILABLE = True
    except ImportError:
        pass

# =============================================================================
# Constants
# =============================================================================

_QUERY_VALUE_REGEX = re.compile("\?", re.MULTILINE)
_PERCENT_REGEX = re.compile("%", re.MULTILINE)
_CONNECTION_ERROR_MSG = "Failed to connect. {ex}: {msg}"
_LINE_EQUALS = "=" * 79
_MSG_JDBC_UNAVAILABLE = "Python jaydebeapi module not available"
_MSG_MYSQL_DRIVERS_UNAVAILABLE = (
    "Python PyMySQL (Python 2/3) and MySQLdb (Python 2) modules unavailable")
_MSG_NO_FLAVOUR = "No database flavour specified"
_MSG_PYODBC_UNAVAILABLE = "Python pyodbc module not available"

ENGINE_ACCESS = "access"
ENGINE_MYSQL = "mysql"
ENGINE_SQLSERVER = "sqlserver"

FLAVOUR_ACCESS = ENGINE_ACCESS
FLAVOUR_MYSQL = ENGINE_MYSQL
FLAVOUR_SQLSERVER = ENGINE_SQLSERVER

INTERFACE_JDBC = "jdbc"  # Java Database Connectivity
INTERFACE_MYSQL = "mysql"  # Direct e.g. TCP/IP connection to a MySQL instance
INTERFACE_ODBC = "odbc"  # Open Database Connectivity

PYTHONLIB_JAYDEBEAPI = "jaydebeapi"
PYTHONLIB_MYSQLDB = "mysqldb"
PYTHONLIB_PYMYSQL = "pymysql"
PYTHONLIB_PYODBC = "pyodbc"


# =============================================================================
# Database specializations
# =============================================================================

class Flavour(object):
    @classmethod
    def flavour(cls):
        return ""

    @classmethod
    def delims(cls):
        return ("[", "]")

    @classmethod
    def current_schema_expr(cls):
        return "NULL"  # Don't know how

    @classmethod
    def column_type_expr(cls):
        return "NULL"  # Don't know how

    @classmethod
    def jdbc_error_help(cls):
        return ""

    @classmethod
    def get_all_table_names(cls, db):
        """Returns all table names in the database."""
        raise RuntimeError(_MSG_NO_FLAVOUR)

    @classmethod
    def get_all_table_details(cls, db):
        """Returns all information the database has on a table."""
        raise RuntimeError(_MSG_NO_FLAVOUR)
        # works in MySQL and SQL Server
        # SQL Server: TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
        # ... those fields (and more) available in MySQL

    @classmethod
    def describe_table(cls, db, table):
        """Returns details on a specific table."""
        raise RuntimeError(_MSG_NO_FLAVOUR)

    @classmethod
    def fetch_column_names(cls, db, table):
        """Returns all column names for a table."""
        raise RuntimeError(_MSG_NO_FLAVOUR)

    @classmethod
    def get_datatype(cls, db, table, column):
        """Returns database SQL datatype for a column: e.g. VARCHAR."""
        raise RuntimeError(_MSG_NO_FLAVOUR)

    @classmethod
    def get_column_type(cls, db, table, column):
        """Returns database SQL datatype for a column, e.g. VARCHAR(50)."""
        raise RuntimeError(_MSG_NO_FLAVOUR)

    @classmethod
    def get_comment(cls, db, table, column):
        """Returns database SQL comment for a column."""
        return None

    @classmethod
    def get_system_variable(self, db, varname):
        """Returns a database system variable."""
        return None

    @classmethod
    def mysql_using_file_per_table(cls, db):
        return False

    @classmethod
    def mysql_using_innodb_barracuda(cls, db):
        return False

    @classmethod
    def mysql_table_using_barracuda(cls, db, tablename):
        return False

    @classmethod
    def mysql_convert_table_to_barracuda(cls, db, tablename, logger=None,
                                         compressed=False):
        pass

    @classmethod
    def mysql_using_innodb_strict_mode(cls, db):
        return False

    @classmethod
    def mysql_get_max_allowed_packet(cls, db):
        return None

    @classmethod
    def is_read_only(cls, db, logger=None):
        return False


# -----------------------------------------------------------------------------
# Microsoft Access
# -----------------------------------------------------------------------------
class Access(Flavour):
    @classmethod
    def flavour(cls):
        return FLAVOUR_ACCESS

    @classmethod
    def delims(cls):
        return ("[", "]")

    @classmethod
    def get_all_table_names(cls, db):
        return db.fetchallfirstvalues("""
            SELECT MSysObjects.Name AS table_name
            FROM MSysObjects
            WHERE (((Left([Name],1))<>"~")
                    AND ((Left([Name],4))<>"MSys")
                    AND ((MSysObjects.Type) In (1,4,6)))
            ORDER BY MSysObjects.Name
        """)
        # http://stackoverflow.com/questions/201282

    @classmethod
    def get_all_table_details(cls, db):
        # returns some not-very-helpful stuff too!
        return db.fetchall("""
            SELECT *
            FROM MSysObjects
            WHERE (((Left([Name],1))<>"~")
                    AND ((Left([Name],4))<>"MSys")
                    AND ((MSysObjects.Type) In (1,4,6)))
            ORDER BY MSysObjects.Name
        """)

    @classmethod
    def describe_table(cls, db, table):
        raise RuntimeError("Don't know how to describe table in Access")

    @classmethod
    def fetch_column_names(cls, db, table):
        # not possible in SQL:
        #   http://stackoverflow.com/questions/2221250
        # can do this:
        #   http://stackoverflow.com/questions/3343922/get-column-names
        # or can use pyodbc:
        db.ensure_db_open()
        cursor = db.db.cursor()
        sql = "SELECT TOP 1 * FROM " + db.delimit(table)
        debug_sql(sql)
        cursor.execute(sql)
        return [x[0] for x in cursor.variables]
        # https://code.google.com/p/pyodbc/wiki/Cursor

    @classmethod
    def get_datatype(cls, db, table, column):
        raise AssertionError("Don't know how to get datatype in Access")

    @classmethod
    def get_column_type(cls, db, table, column):
        raise AssertionError("Don't know how to get datatype in Access")


# -----------------------------------------------------------------------------
# MySQL
# -----------------------------------------------------------------------------
class MySQL(Flavour):
    @classmethod
    def flavour(cls):
        return FLAVOUR_MYSQL

    @classmethod
    def delims(cls):
        return ("`", "`")

    @classmethod
    def current_schema_expr(cls):
        return "DATABASE()"

    @classmethod
    def column_type_expr(cls):
        return "column_type"

    @classmethod
    def jdbc_error_help(cls):
        return """

    If you get:
        java.lang.RuntimeException: Class com.mysql.jdbc.Driver not found
    ... then, under Ubuntu/Debian, try:
    (1) sudo apt-get install libmysql-java
    (2) export CLASSPATH=$CLASSPATH:/usr/share/java/mysql.jar

    If you get:
        Failed to connect. OSError: [Errno 2] No such file or directory:
        '/usr/lib/jvm'
    ... under 64-bit Ubuntu, then:
        sudo apt-get install default-jre libc6-i386

        """

    @classmethod
    def get_all_table_names(cls, db):
        return db.fetchallfirstvalues(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema=?", db.schema)
        # or: "SHOW TABLES"

    @classmethod
    def get_all_table_details(cls, db):
        return db.fetchall("SELECT * FROM information_schema.tables "
                           "WHERE table_schema=?", db.schema)
        # not restricted to current database, unless we do that manually

    @classmethod
    def describe_table(cls, db, table):
        return db.fetchall(
            "SELECT * FROM information_schema.columns "
            "WHERE table_schema=? AND table_name=?", db.schema, table)
        # or: "SHOW TABLES"

    @classmethod
    def fetch_column_names(cls, db, table):
        return db.fetchallfirstvalues(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema=? AND table_name=?", db.schema, table)
        # or: "SHOW TABLES"

    @classmethod
    def get_datatype(cls, db, table, column):
        # ISO standard for INFORMATION_SCHEMA, I think.
        return db.fetchvalue(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_schema=? AND table_name=? AND column_name=?",
            db.schema, table, column)

    @classmethod
    def get_column_type(cls, db, table, column):
        # ISO standard for INFORMATION_SCHEMA, I think.
        sql = """
            SELECT {}
            FROM information_schema.columns
            WHERE table_schema=? AND table_name=? AND column_name=?
        """.format(cls.column_type_expr())
        return db.fetchvalue(sql, db.schema, table, column)

    @classmethod
    def get_comment(cls, db, table, column):
        return db.fetchvalue(
            "SELECT column_comment FROM information_schema.columns "
            "WHERE table_schema=? AND table_name=? AND column_name=?",
            db.schema, table, column)

    @classmethod
    def get_system_variable(self, db, varname):
        sql = "SELECT @@{varname}".format(varname=varname)
        # http://dev.mysql.com/doc/refman/5.5/en/using-system-variables.html
        return db.fetchvalue(sql)

    @classmethod
    def mysql_using_file_per_table(cls, db):
        return cls.get_system_variable(db, "innodb_file_per_table") == 1

    @classmethod
    def mysql_using_innodb_barracuda(cls, db):
        return cls.get_system_variable(db, "innodb_file_format") == "Barracuda"

    @classmethod
    def mysql_table_using_barracuda(cls, db, tablename):
        if (not cls.mysql_using_file_per_table(db)
                or not cls.mysql_using_innodb_barracuda(db)):
            return False
        sql = """
            SELECT engine, row_format
            FROM information_schema.tables
            WHERE table_name = ?
            AND table_schema={}
        """.format(cls.current_schema_expr())
        args = [tablename]
        row = db.fetchone(sql, *args)
        if not row:
            return False
        engine = row[0]
        row_format = row[1]
        return engine == "InnoDB" and row_format in ["Compressed", "Dynamic"]
        # http://dev.mysql.com/doc/refman/5.6/en/innodb-file-format-identifying.html  # noqa

    @classmethod
    def mysql_convert_table_to_barracuda(cls, db, tablename, logger=None,
                                         compressed=False):
        row_format = "COMPRESSED" if compressed else "DYNAMIC"
        sql = """
            ALTER TABLE {tablename}
            ENGINE=InnoDB
            ROW_FORMAT={row_format}
        """.format(
            tablename=tablename,
            row_format=row_format,
        )
        if logger:
            logger.info(
                "Converting table {} to Barracuda (row_format={})".format(
                    tablename,
                    row_format
                )
            )
        db.db_exec(sql)
        # http://dev.mysql.com/doc/refman/5.5/en/innodb-compression-usage.html
        # http://www.percona.com/blog/2011/04/07/innodb-row-size-limitation/

    @classmethod
    def mysql_using_innodb_strict_mode(cls, db):
        return cls.get_system_variable(db, "innodb_strict_mode") == 1

    @classmethod
    def mysql_get_max_allowed_packet(cls, db):
        return cls.get_system_variable(db, "max_allowed_packet")

    @classmethod
    def is_read_only(cls, db, logger=None):
        """Do we have read-only access?"""

        def convert_enums(row):
            # All these columns are of type enum('N', 'Y');
            # https://dev.mysql.com/doc/refman/5.0/en/enum.html
            return [True if x == 'Y' else (False if x == 'N' else None)
                    for x in row]

        # 1. Check per-database privileges.
        # We don't check SELECT privileges. We're just trying to ensure
        # nothing dangerous is present - for ANY database.
        # If we get an exception
        try:
            sql = """
                SELECT db,
                       /* must not have: */
                       Insert_priv, Update_priv, Delete_priv,
                       Create_priv, Drop_priv, Index_priv, Alter_priv,
                       Lock_tables_priv, Create_view_priv,
                       Create_routine_priv, Alter_routine_priv,
                       Execute_priv, Event_priv, Trigger_priv
                FROM mysql.db
                WHERE
                    CONCAT(user, '@', host) = CURRENT_USER()
            """
            rows = db.fetchall(sql)
            for row in rows:
                dbname = row[0]
                prohibited = convert_enums(row[1:])
                if any(prohibited):
                    if logger:
                        logger.debug(
                            "MySQL.is_read_only(): FAIL: database privileges "
                            "wrong: dbname={}, prohibited={}".format(
                                dbname, prohibited
                            )
                        )
                    return False
        except mysql.OperationalError:
            # Probably: error 1142, "SELECT command denied to user 'xxx'@'yyy'
            # for table 'db'". This would be OK.
            pass

        # 2. Global privileges, e.g. as held by root
        try:
            sql = """
                SELECT /* must not have: */
                       Insert_priv, Update_priv, Delete_priv,
                       Create_priv, Drop_priv,
                       Reload_priv, Shutdown_priv,
                       Process_priv, File_priv, Grant_priv,
                       Index_priv, Alter_priv,
                       Show_db_priv, Super_priv,
                       Lock_tables_priv, Execute_priv,
                       Repl_slave_priv, Repl_client_priv,
                       Create_view_priv,
                       Create_routine_priv, Alter_routine_priv,
                       Create_user_priv,
                       Event_priv, Trigger_priv,
                       Create_tablespace_priv
                FROM mysql.user
                WHERE
                    CONCAT(user, '@', host) = CURRENT_USER()
            """
            rows = db.fetchall(sql)
            if not rows or len(rows) > 1:
                return False
            prohibited = convert_enums(rows[0])
            if any(prohibited):
                if logger:
                    logger.debug(
                        "MySQL.is_read_only(): FAIL: GLOBAL privileges "
                        "wrong: prohibited={}".format(prohibited))
                return False
        except mysql.OperationalError:
            # Probably: error 1142, "SELECT command denied to user 'xxx'@'yyy'
            # for table 'user'". This would be OK.
            pass

        return True


# -----------------------------------------------------------------------------
# SQL Server
# -----------------------------------------------------------------------------
class SQLServer(Flavour):
    @classmethod
    def flavour(cls):
        return FLAVOUR_SQLSERVER

    @classmethod
    def delims(cls):
        return ("[", "]")

    @classmethod
    def current_schema_expr(cls):
        return "SCHEMA_NAME()"

    @classmethod
    def column_type_expr(cls):
        return """
            (CASE
                WHEN character_maximum_length > 0
                    THEN data_type + '(' +
                        CAST(character_maximum_length AS VARCHAR(20)) + ')'
                WHEN character_maximum_length = -1
                    THEN data_type + '(MAX)'
                ELSE data_type
             END)
        """

    @classmethod
    def jdbc_error_help(cls):
        return """

    If you get:
        java.lang.RuntimeException: Class
            com.microsoft.sqlserver.jdbc.SQLServerDriver not found
    ... then, under Ubuntu/Debian, try:
    (1) Download the driver from
        http://www.microsoft.com/en-us/download/details.aspx?id=11774
        ... it's sqljdbc_4.1.5605.100_enu.tar.gz
    (2) [sudo] tar xvzf sqljdbc_4.1.5605.100_enu.tar.gz [-C destdir]
    (3) export CLASSPATH=$CLASSPATH:/wherever/sqljdbc_4.1/enu/sqljdbc41.jar

        """

    @classmethod
    def get_all_table_names(cls, db):
        return db.fetchallfirstvalues(
            "SELECT table_name FROM information_schema.tables")

    @classmethod
    def get_all_table_details(cls, db):
        return db.fetchall("SELECT * FROM information_schema.tables")
        # restricted to current database (in full:
        #   databasename.information_schema.tables)
        # http://stackoverflow.com/questions/6568098

    @classmethod
    def describe_table(cls, db, table):
        return db.fetchall(
            "SELECT * FROM information_schema.columns "
            "WHERE table_name=?", table)

    @classmethod
    def fetch_column_names(cls, db, table):
        return db.fetchallfirstvalues(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name=?", table)

    @classmethod
    def get_datatype(cls, db, table, column):
        # ISO standard for INFORMATION_SCHEMA, I think.
        # SQL Server carries a warning but the warning may be incorrect:
        # https://msdn.microsoft.com/en-us/library/ms188348.aspx
        # http://stackoverflow.com/questions/917431
        # http://sqlblog.com/blogs/aaron_bertrand/archive/2011/11/03/the-case-against-information-schema-views.aspx  # noqa
        return db.fetchvalue(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_schema=? AND table_name=? AND column_name=?",
            db.schema, table, column)

    @classmethod
    def get_column_type(cls, db, table, column):
        # ISO standard for INFORMATION_SCHEMA, I think.
        # SQL Server carries a warning but the warning may be incorrect:
        # https://msdn.microsoft.com/en-us/library/ms188348.aspx
        # http://stackoverflow.com/questions/917431
        # http://sqlblog.com/blogs/aaron_bertrand/archive/2011/11/03/the-case-against-information-schema-views.aspx  # noqa
        sql = """
            SELECT {}
            FROM information_schema.columns
            WHERE table_schema=? AND table_name=? AND column_name=?
        """.format(cls.column_type_expr())
        return db.fetchvalue(sql, db.schema, table, column)


# =============================================================================
# Exceptions
# =============================================================================

class NoDatabaseError(ConnectionError):
    """Exception class for when a database is unavailable."""
    def __init__(self, value=""):
        self.value = value

    def __str__(self):
        return repr(self.value)


# =============================================================================
# Generic database routines.
# =============================================================================

def set_verbose_logging(verbose):
    """Chooses basic or verbose logging."""
    if verbose:
        set_loglevel(logging.DEBUG)
    else:
        set_loglevel(logging.INFO)


def set_loglevel(level):
    logger.setLevel(level)


def debug_sql(sql, *args):
    """Writes SQL and arguments to the logger."""
    logger.debug("SQL: %s" % sql)
    if args:
        logger.debug("Args: %r" % args)  # %r is repr()


def delimit(x, delims):
    """Delimits x, using delims[0] (left) and delims[1] (right)."""
    return delims[0] + x + delims[1]


def get_pk_of_last_insert(cursor):
    """Returns the primary key of the last insert performed with the cursor."""
    return cursor.lastrowid


def get_sql_select_all_non_pk_fields_by_pk(table, fieldlist, delims=("", "")):
    """Returns SQL:
        SELECT [all but the first field] WHERE [the first field] = ?
    """
    return "SELECT " + \
        ",".join([delimit(x, delims) for x in fieldlist[1:]]) + \
        " FROM " + table + \
        " WHERE " + delimit(fieldlist[0], delims) + "=?"


def get_sql_select_all_fields_by_key(table, fieldlist, keyname,
                                     delims=("", "")):
    """Returns SQL:
        SELECT [all fields in the fieldlist] WHERE [keyname] = ?
    """
    return "SELECT " + \
        ",".join([delimit(x, delims) for x in fieldlist]) + \
        " FROM " + delimit(table, delims) + \
        " WHERE " + delimit(keyname, delims) + "=?"


def get_sql_insert(table, fieldlist, delims=("", "")):
    """Returns ?-marked SQL for an INSERT statement."""
    return "INSERT INTO " + delimit(table, delims) + \
        " (" + \
        ",".join([delimit(x, delims) for x in fieldlist]) + \
        ") VALUES (" + \
        ",".join(["?"] * len(fieldlist)) + \
        ")"


def get_sql_insert_or_update(table, fieldlist, delims=("", "")):
    """Returns ?-marked SQL for an INSERT-or-if-duplicate-key-UPDATE statement.
    """
    # http://stackoverflow.com/questions/4205181
    return """
        INSERT INTO {table} ({fields})
        VALUES ({placeholders})
        ON DUPLICATE KEY UPDATE {updatelist}
    """.format(
        table=delimit(table, delims),
        fields=",".join([delimit(x, delims) for x in fieldlist]),
        placeholders=",".join(["?"] * len(fieldlist)),
        updatelist=",".join(
            ["{field}=VALUES({field})".format(field=delimit(x, delims))
             for x in fieldlist]
        ),
    )


def get_sql_insert_without_first_field(table, fieldlist, delims=("", "")):
    """Returns ?-marked SQL for an INSERT statement, ignoring the first field
    (typically, the PK)."""
    return get_sql_insert(table, fieldlist[1:], delims)


def get_sql_update_by_first_field(table, fieldlist, delims=("", "")):
    """Returns SQL for an UPDATE statement, to update all fields except the
    first field (PK) using the PK as the key."""
    return "UPDATE " + delimit(table, delims) + \
        " SET " + \
        ",".join([delimit(x, delims) + "=?" for x in fieldlist[1:]]) + \
        " WHERE " + delimit(fieldlist[0], delims) + "=?"


def sql_quote_string(s):
    """Quotes string, escaping apostrophes by doubling them."""
    return "'" + s.replace("'", "''") + "'"  # double up single quotes


def sql_dequote_string(s):
    """Reverses sql_quote_string."""
    if len(s) < 2:
        # Something wrong.
        return s
    s = s[1:-1]  # strip off the surrounding quotes
    return s.replace("''", "'")


def DateTime2literal_RNC(d, c):
    """Format a DateTime object as something MySQL will actually accept."""
    # dt = d.strftime("%Y-%m-%d %H:%M:%S")
    # ... can fail with e.g.
    #   ValueError: year=1850 is before 1900; the datetime strftime() methods
    #   require year >= 1900
    # http://stackoverflow.com/questions/10263956
    dt = d.isoformat(" ")
    return _mysql.string_literal(dt, c)


def full_datatype_to_mysql(d):
    """Converts a full datatype, e.g. INT, VARCHAR(10), VARCHAR(MAX), to a
    MySQL equivalent."""
    d = d.upper()
    (s, length) = split_long_sqltype(d)
    if d in ["VARCHAR(MAX)", "NVARCHAR(MAX)"]:
        # http://wiki.ispirer.com/sqlways/mysql/data-types/longtext
        return "LONGTEXT"
    elif d in ["VARBINARY(MAX)"] or s in ["IMAGE"]:
        # http://wiki.ispirer.com/sqlways/mysql/data-types/varbinary
        return "LONGBLOB"
    else:
        return d


# =============================================================================
# Generic routines for objects with database fields
# =============================================================================

def debug_object(obj):
    """Prints key/value pairs for an object's dictionary."""
    pairs = []
    for k, v in vars(obj).items():
        pairs.append(u"{}={}".format(k, v))
    return u", ".join(pairs)


def dump_database_object(obj, fieldlist):
    """Prints key/value pairs for an object's dictionary."""
    logger.info(_LINE_EQUALS)
    logger.info(u"DUMP OF: {}".format(obj))
    for f in fieldlist:
        logger.info(u"{f}: {v}".format(f=f, v=getattr(obj, f)))
    logger.info(_LINE_EQUALS)


def assign_from_list(obj, fieldlist, valuelist):
    """Within "obj", assigns the values from the value list to the fields in
    the fieldlist."""
    if len(fieldlist) != len(valuelist):
        raise AssertionError("assign_from_list: fieldlist and valuelist of "
                             "different length")
    for i in range(len(valuelist)):
        setattr(obj, fieldlist[i], valuelist[i])


def blank_object(obj, fieldlist):
    """Within "obj", sets all fields in the fieldlist to None."""
    for f in fieldlist:
        setattr(obj, f, None)


def debug_query_result(rows):
    """Writes a query result to the logger."""
    logger.info("Retrieved {} rows".format(len(rows)))
    for i in range(len(rows)):
        logger.info("Row {}: {}".format(i, rows[i]))


# =============================================================================
# SQL types and validation
# =============================================================================

# REGEX_INVALID_TABLE_FIELD_CHARS = re.compile("[^a-zA-Z0-9_ ]")
REGEX_INVALID_TABLE_FIELD_CHARS = re.compile("[^\x20-\x7E]")
# ... SQL Server is very liberal!


def is_valid_field_name(f):
    if not f:
        return False
    if bool(REGEX_INVALID_TABLE_FIELD_CHARS.search(f)):
        return False
    return True


def is_valid_table_name(t):
    return is_valid_field_name(t)


def ensure_valid_field_name(f):
    if not is_valid_field_name(f):
        raise ValueError("Field name invalid: {}".format(f))


def ensure_valid_table_name(f):
    if not is_valid_table_name(f):
        raise ValueError("Table name invalid: {}".format(f))


SQLTYPES_INTEGER = [
    "INT", "INTEGER",
    "TINYINT", "SMALLINT", "MEDIUMINT", "BIGINT",
]
SQLTYPES_FLOAT = [
    "DOUBLE", "FLOAT",
]
SQLTYPES_OTHER_NUMERIC = [
    "BIT", "BOOL", "BOOLEAN", "DEC", "DECIMAL",
]
SQLTYPES_TEXT = [
    "CHAR", "VARCHAR", "NVARCHAR",
    "TINYTEXT", "TEXT", "NTEXT", "MEDIUMTEXT", "LONGTEXT",
]
SQLTYPES_BINARY = [
    "BINARY", "BLOB", "IMAGE", "LONGBLOB", "VARBINARY",
]

SQLTYPES_WITH_DATE = [
    "DATE", "DATETIME", "TIME", "TIMESTAMP",
]
SQLTYPES_DATETIME_OTHER = [
    "TIME", "YEAR",
]
SQLTYPES_DATETIME_ALL = SQLTYPES_WITH_DATE + SQLTYPES_DATETIME_OTHER

SQLTYPES_ALL = (
    SQLTYPES_INTEGER
    + SQLTYPES_FLOAT
    + SQLTYPES_OTHER_NUMERIC
    + SQLTYPES_TEXT
    + SQLTYPES_BINARY
    + SQLTYPES_DATETIME_ALL
)
# Could be more comprehensive!

SQLTYPES_NOT_TEXT = (
    SQLTYPES_INTEGER
    + SQLTYPES_FLOAT
    + SQLTYPES_OTHER_NUMERIC
    + SQLTYPES_DATETIME_ALL
)
SQLTYPES_NUMERIC = (
    SQLTYPES_INTEGER
    + SQLTYPES_FLOAT
    + SQLTYPES_OTHER_NUMERIC
)


def split_long_sqltype(datatype_long):
    datatype_short = datatype_long.split("(")[0].strip()
    find_open = datatype_long.find("(")
    find_close = datatype_long.find(")")
    if find_open >= 0 and find_close > find_open:
        try:
            length = int(datatype_long[find_open + 1:find_close])
        except:  # e.g. for "VARCHAR(MAX)"
            length = None
    else:
        length = None
    return (datatype_short, length)


def is_sqltype_valid(datatype_long):
    (datatype_short, length) = split_long_sqltype(datatype_long)
    return datatype_short in SQLTYPES_ALL


def is_sqltype_date(datatype_long):
    (datatype_short, length) = split_long_sqltype(datatype_long)
    return datatype_short in SQLTYPES_WITH_DATE


def is_sqltype_text(datatype_long):
    (datatype_short, length) = split_long_sqltype(datatype_long)
    return datatype_short in SQLTYPES_TEXT


def is_sqltype_text_of_length_at_least(datatype_long, min_length):
    (datatype_short, length) = split_long_sqltype(datatype_long)
    if datatype_short not in SQLTYPES_TEXT:
        return False
    if length is None:  # text, with no length, e.g. VARCHAR(MAX)
        return True
    return length >= min_length


def is_sqltype_text_over_one_char(datatype_long):
    return is_sqltype_text_of_length_at_least(datatype_long, 2)


def is_sqltype_binary(datatype_long):
    (datatype_short, length) = split_long_sqltype(datatype_long)
    return datatype_short in SQLTYPES_BINARY


def is_sqltype_numeric(datatype_long):
    (datatype_short, length) = split_long_sqltype(datatype_long)
    return datatype_short in SQLTYPES_NUMERIC


def is_sqltype_integer(datatype_long):
    (datatype_short, length) = split_long_sqltype(datatype_long)
    return datatype_short in SQLTYPES_INTEGER


def does_sqltype_require_index_len(datatype_long):
    (datatype_short, length) = split_long_sqltype(datatype_long)
    return datatype_short in ["TEXT", "BLOB"]


def does_sqltype_merit_fulltext_index(datatype_long, min_length=1000):
    return is_sqltype_text_of_length_at_least(datatype_long, min_length)


# =============================================================================
# Reconfiguring jaydebeapi to do sensible type conversions
# =============================================================================

def _convert_java_binary(rs, col):
    # https://github.com/originell/jpype/issues/71
    # http://stackoverflow.com/questions/5088671
    # https://github.com/baztian/jaydebeapi/blob/master/jaydebeapi/__init__.py
    # https://msdn.microsoft.com/en-us/library/ms378813(v=sql.110).aspx
    # http://stackoverflow.com/questions/2920364/checking-for-a-null-int-value-from-a-java-resultset  # noqa
    v = None
    logger.debug("_convert_java_binary: converting...")
    time1 = time.time()
    try:
        # ---------------------------------------------------------------------
        # Method 1: 3578880 bytes in 21.7430660725 seconds =   165 kB/s
        # ---------------------------------------------------------------------
        # java_val = rs.getObject(col)
        # if java_val is None:
        #     return
        # t = str(type(java_val))
        # if t == "<class 'jpype._jarray.byte[]'>": ...
        # v = ''.join(map(lambda x: chr(x % 256), java_val))
        # ---------------------------------------------------------------------
        # Method 2: 3578880 bytes in 8.07930088043 seconds =   442 kB/s
        # ---------------------------------------------------------------------
        # java_val = rs.getObject(col)
        # if java_val is None:
        #     return
        # l = len(java_val)
        # v = bytearray(l)
        # for i in range(l):
        #     v[i] = java_val[i] % 256
        # ---------------------------------------------------------------------
        # Method 3: 3578880 bytes in 20.1435189247 seconds =   177 kB/s
        # ---------------------------------------------------------------------
        # java_val = rs.getObject(col)
        # if java_val is None:
        #     return
        # v = bytearray(map(lambda x: x % 256, java_val))
        # ---------------------------------------------------------------------
        # Method 4: 3578880 bytes in 0.48352599144 seconds = 7,402 kB/s
        # ---------------------------------------------------------------------
        j_hexstr = rs.getString(col)
        if rs.wasNull():
            return
        v = binascii.unhexlify(j_hexstr)
    finally:
        time2 = time.time()
        logger.debug("... done (in {} seconds)".format(time2 - time1))
        # if v:
        #     logger.debug("_convert_java_binary: type={}, length={}".format(
        #         type(v), len(v)))
        return v


def _convert_java_bigstring(rs, col):
    v = str(rs.getCharacterStream(col))
    if rs.wasNull():
        return None
    return v


def _convert_java_bigint(rs, col):
    # http://stackoverflow.com/questions/26899595
    # https://github.com/baztian/jaydebeapi/issues/6
    # https://github.com/baztian/jaydebeapi/blob/master/jaydebeapi/__init__.py
    # https://docs.oracle.com/javase/7/docs/api/java/math/BigInteger.html
    # http://docs.oracle.com/javase/7/docs/api/java/sql/ResultSet.html
    java_val = rs.getObject(col)
    if java_val is None:
        return
    v = getattr(java_val, 'toString')()  # Java call: java_val.toString()
    return int(v)


def _convert_java_datetime(rs, col):
    java_val = rs.getTimestamp(col)
    if not java_val:
        return
    d = datetime.datetime.strptime(str(java_val)[:19], "%Y-%m-%d %H:%M:%S")
    d = d.replace(microsecond=int(str(java_val.getNanos())[:6]))
    # jaydebeapi 0.2.0 does this:
    #   return str(d)
    # but we want a datetime!
    return d


def reconfigure_jaydebeapi():
    if not JDBC_AVAILABLE:
        return
    # The types used as keys below MUST be in java.sql.Types -- search for
    # _init_types() calls in jaydebeapi's __init__.py. If not, this bit
    # crashes:
    #       for i in _DEFAULT_CONVERTERS:
    #           const_val = types_map[i]
    # Those types are:
    #       http://docs.oracle.com/javase/6/docs/api/java/sql/Types.html
    # In particular, note that DATETIME is not one of them!
    # The equivalent is TIMESTAMP.
    #       http://stackoverflow.com/questions/6777810
    try:
        if hasattr(jaydebeapi, "_DEFAULT_CONVERTERS"):
            # Recent version of jaydebeapi, e.g. 0.2.0
            converters = jaydebeapi._DEFAULT_CONVERTERS
        else:
            # Older version, e.g. prior to 0.2.0
            logger.warning("Old jaydebeapi version")
            converters = jaydebeapi.dbapi2._DEFAULT_CONVERTERS
    except:
        raise AssertionError(
            "Don't know how to hook into this version of JayDeBeApi")

    converters.update({
        'BIGINT': _convert_java_bigint,
        'BINARY': _convert_java_binary,  # overrides an existing one
        'BLOB': _convert_java_binary,
        'LONGNVARCHAR': _convert_java_bigstring,
        'LONGVARBINARY': _convert_java_binary,
        'LONGVARCHAR': _convert_java_bigstring,
        'TIMESTAMP': _convert_java_datetime,
        'VARBINARY': _convert_java_binary,
        # Handled sensibly by jaydebeapi:
        # 'TIME': _to_time,
        # 'DATE': _to_date,
        # 'BINARY': _to_binary,
        # 'DECIMAL': _to_double,
        # 'NUMERIC': _to_double,
        # 'DOUBLE': _to_double,
        # 'FLOAT': _to_double,
        # 'INTEGER': _to_int,
        # 'SMALLINT': _to_int,
        # 'BOOLEAN': _java_to_py('booleanValue'),
        #
        # Not handled sensibly:
        # 'TIMESTAMP': _to_datetime,
    })


reconfigure_jaydebeapi()


# =============================================================================
# Database creation
# =============================================================================

def create_database_mysql(database,
                          user,
                          password,
                          server="localhost",
                          port=3306,
                          charset="utf8",
                          collate="utf8_general_ci",
                          use_unicode=True):
    """Connects via PyMySQL/MySQLdb and creates a database."""
    con = mysql.connect(
        host=server,
        port=port,
        user=user,
        passwd=password,
        charset=charset,
        use_unicode=use_unicode
    )
    sql = ("CREATE DATABASE IF NOT EXISTS {} DEFAULT CHARACTER SET {} "
           "DEFAULT COLLATE {}").format(
        database,
        charset,
        collate
    )
    cursor = con.cursor()
    debug_sql(sql)
    cursor.execute(sql)
    logger.info("Created database {}".format(database))
    return True


def add_master_user_mysql(database,
                          root_user,
                          root_password,
                          new_user,
                          new_password,
                          server="localhost",
                          port=3306,
                          charset="utf8",
                          use_unicode=True,
                          localhost_only=True):
    """Connects via PyMySQL/MySQLdb and creates a database superuser."""
    con = mysql.connect(
        host=server,
        port=port,
        user=root_user,
        passwd=root_password,
        charset=charset,
        use_unicode=use_unicode
    )
    wherefrom = "localhost" if localhost_only else "%"
    sql = ("GRANT ALL PRIVILEGES ON {}.* TO '{}'@'{}' "
           "IDENTIFIED BY '{}'").format(
        database,
        new_user,
        wherefrom,
        new_password
    )
    cursor = con.cursor()
    debug_sql(sql)
    cursor.execute(sql)
    logger.info("Added master user {} to database {}".format(
        new_user, database))


# =============================================================================
# Database config class
# =============================================================================

class DatabaseConfig(object):
    def __init__(self, parser, section):
        self.section = section
        if not parser.has_section(section):
            raise ValueError("config missing section: " + section)
        options = [
            # Connection
            "engine",
            "interface",

            # Various ways:
            "host",
            "port",
            "db",

            "dsn",

            "odbc_connection_string",

            # Then regardless:
            "user",
            "password",
        ]
        for o in options:
            if parser.has_option(section, o):
                value = parser.get(section, o)
                setattr(self, o, value)
            else:
                setattr(self, o, None)
        self.port = int(self.port) if self.port else None
        self.check_valid()

    def check_valid(self):
        if not self.engine:
            raise ValueError(
                "Database {} doesn't specify engine".format(self.section))
        self.engine = self.engine.lower()
        if self.engine not in [ENGINE_MYSQL, ENGINE_SQLSERVER]:
            raise ValueError("Unknown database engine: {}".format(self.engine))
        if not self.interface:
            if self.engine == ENGINE_MYSQL:
                self.interface = INTERFACE_MYSQL
            else:
                self.interface = INTERFACE_ODBC
        if self.interface not in [INTERFACE_JDBC,
                                  INTERFACE_MYSQL,
                                  INTERFACE_ODBC]:
            raise ValueError("Unknown interface: {}".format(self.interface))
        if self.engine == ENGINE_MYSQL:
            if (not self.host or not self.port or not self.user or not
                    self.password or not self.db):
                raise ValueError("Missing MySQL details")
        elif self.engine == ENGINE_SQLSERVER:
            if self.odbc_connection_string:
                pass  # this is OK
            elif self.dsn:
                if (not self.user or not self.password):
                    raise ValueError(
                        "Missing SQL Server details: user or password")
            else:
                if (not self.host or not self.user or not
                        self.password):
                    raise ValueError(
                        "Missing SQL Server details: host, user, or password")

    def get_database(self, autocommit=False, securely=True):
        try:
            db = DatabaseSupporter()
            db.connect(
                engine=self.engine,
                interface=self.interface,
                host=self.host,
                port=self.port,
                database=self.db,
                dsn=self.dsn,
                odbc_connection_string=self.odbc_connection_string,
                user=self.user,
                password=self.password,
                autocommit=autocommit  # if False, need to commit
            )
            return db
        except:
            if securely:
                raise NoDatabaseError(
                    "Problem opening or reading from database {}; details "
                    "concealed for security reasons".format(self.section))
            else:
                raise


def get_database_from_configparser(parser, section, securely=True):
    try:  # guard this bit to prevent any password leakage
        dbc = DatabaseConfig(parser, section)
        db = dbc.get_database(securely=securely)
        return db
    except:
        if securely:
            raise NoDatabaseError(
                "Problem opening or reading from database {}; details "
                "concealed for security reasons".format(section))
        else:
            raise
    finally:
        dbc = None


# =============================================================================
# Database support class. ODBC via pyodbc or MySQLdb.
# =============================================================================

class DatabaseSupporter:
    """Support class for databases using pyodbc or MySQLdb."""

    def __init__(self):
        self.db = None
        self.flavour = None
        self.db_pythonlib = None
        self.schema = None
        self.autocommit = None
        # http://stackoverflow.com/questions/2901453
        # http://stackoverflow.com/questions/7311990

    # -------------------------------------------------------------------------
    # Generic connection method
    # -------------------------------------------------------------------------

    @staticmethod
    def reraise_connection_exception(e):
        err = "Failed to connect. {ex}: {msg}".format(
            ex=type(e).__name__,
            msg=str(e),
        )
        logger.exception(err)
        raise NoDatabaseError(err)

    def connect(self,
                engine=None, interface=None,
                host=None, port=None, database=None,
                driver=None, dsn=None, odbc_connection_string=None,
                user=None, password=None,
                autocommit=True, charset="utf8", use_unicode=True):
        """
            engine: access, mysql, sqlserver
            interface: mysql, odbc, jdbc
        """

        # Catch all exceptions, so the error-catcher never shows a password.
        # Note also that higher-level things may catch exceptions, so use the
        # logger as well.
        try:
            return self._connect(
                engine=engine, interface=interface,
                host=host, port=port, database=database,
                driver=driver, dsn=dsn,
                odbc_connection_string=odbc_connection_string,
                user=user, password=password,
                autocommit=autocommit, charset=charset,
                use_unicode=use_unicode)
        except Exception as e:
            self.reraise_connection_exception(e)

    def _connect(self,
                 engine=None, interface=None,
                 host=None, port=None, database=None,
                 driver=None, dsn=None, odbc_connection_string=None,
                 user=None, password=None,
                 autocommit=True, charset="utf8", use_unicode=True):
        # Check engine
        if engine == ENGINE_MYSQL:
            self.flavour = MySQL()
            self.schema = database
        elif engine == ENGINE_SQLSERVER:
            self.flavour = SQLServer()
            if database:
                self.schema = database
            else:
                self.schema = "dbo"  # default for SQL server
        elif engine == ENGINE_ACCESS:
            self.flavour = Access()
            self.schema = "dbo"  # default for SQL server
        else:
            raise ValueError("Unknown engine")

        # Default interface
        if interface is None:
            if engine == ENGINE_MYSQL:
                interface = INTERFACE_MYSQL
            else:
                interface = INTERFACE_ODBC

        # Default port
        if port is None:
            if engine == ENGINE_MYSQL:
                port = 3306
            elif engine == ENGINE_SQLSERVER:
                port = 1433

        # Default driver
        if driver is None:
            if engine == ENGINE_MYSQL and interface == INTERFACE_ODBC:
                driver = "{MySQL ODBC 5.1 Driver}"

        self._engine = engine
        self._interface = interface
        self._server = host
        self._port = port
        self._database = database
        self._user = user
        self._password = password
        self._charset = charset
        self._use_unicode = use_unicode
        self.autocommit = autocommit

        # Report intent
        logger.info("Opening database: engine={e}, interface={i}, "
                    "use_unicode={u}, autocommit={a}".format(
                        e=engine, i=interface, u=use_unicode, a=autocommit))

        # Interface
        if interface == INTERFACE_MYSQL:
            if PYMYSQL_AVAILABLE:
                self.db_pythonlib = PYTHONLIB_PYMYSQL
            elif MYSQLDB_AVAILABLE:
                self.db_pythonlib = PYTHONLIB_MYSQLDB
            else:
                raise ImportError(_MSG_MYSQL_DRIVERS_UNAVAILABLE)
        elif interface == INTERFACE_ODBC:
            if not PYODBC_AVAILABLE:
                raise ImportError(_MSG_PYODBC_UNAVAILABLE)
            self.db_pythonlib = PYTHONLIB_PYODBC
        elif interface == INTERFACE_JDBC:
            if not JDBC_AVAILABLE:
                raise ImportError(_MSG_JDBC_UNAVAILABLE)
            if host is None:
                raise ValueError("Missing host parameter")
            if port is None:
                raise ValueError("Missing port parameter")
            # if database is None:
            #     raise ValueError("Missing database parameter")
            if user is None:
                raise ValueError("Missing user parameter")
            self.db_pythonlib = PYTHONLIB_JAYDEBEAPI
        else:
            raise ValueError("Unknown interface")

        # ---------------------------------------------------------------------
        # Connect
        # ---------------------------------------------------------------------
        if engine == ENGINE_MYSQL and interface == INTERFACE_MYSQL:
            # Connects to a MySQL database via MySQLdb/PyMySQL.
            # http://dev.mysql.com/doc/refman/5.1/en/connector-odbc-configuration-connection-parameters.html  # noqa
            # http://code.google.com/p/pyodbc/wiki/ConnectionStrings

            # Between MySQLdb 1.2.3 and 1.2.5, the DateTime2literal function
            # stops producing e.g.
            #   '2014-01-03 18:15:51'
            # and starts producing e.g.
            #   '2014-01-03 18:15:51.842097+00:00'.
            # Let's fix that...
            DateTimeType = datetime.datetime  # as per MySQLdb times.py
            converters = mysql.converters.conversions.copy()
            converters[DateTimeType] = DateTime2literal_RNC
            # See also:
            #   http://stackoverflow.com/questions/11053941
            logger.info(
                "{i} connect: host={h}, port={p}, user={u}, "
                "database={d}".format(
                    i=interface, h=host, p=port, u=user, d=database))
            self.db = mysql.connect(
                host=host,
                port=port,
                user=user,
                passwd=password,
                db=database,
                charset=charset,
                use_unicode=use_unicode,
                conv=converters
            )
            self.db.autocommit(autocommit)
            # http://mysql-python.sourceforge.net/MySQLdb.html
            # http://dev.mysql.com/doc/refman/5.0/en/mysql-autocommit.html

            # MySQL character sets and collations:
            #   http://dev.mysql.com/doc/refman/5.1/en/charset.html
            # Create a database using UTF8:
            # ... CREATE DATABASE mydb DEFAULT CHARACTER SET utf8
            #     DEFAULT COLLATE utf8_general_ci;
            # What is my database using?
            # ... SHOW VARIABLES LIKE 'character_set_%';
            # Change a database character set:
            # ... ALTER DATABASE mydatabasename charset=utf8;
            # http://docs.moodle.org/23/en/
            #        Converting_your_MySQL_database_to_UTF8
            #
            # Python talking to MySQL in Unicode:
            # http://www.harelmalka.com/?p=81
            # http://stackoverflow.com/questions/6001104

        elif engine == ENGINE_MYSQL and interface == INTERFACE_ODBC:
            logger.info(
                "ODBC connect: DRIVER={dr};SERVER={s};PORT={p};"
                "DATABASE={db};USER={u};PASSWORD=[censored]".format(
                    dr=driver, s=host, p=port, u=user, d=database))
            dsn = (
                "DRIVER={0};SERVER={1};PORT={2};DATABASE={3};"
                "USER={4};PASSWORD={5}".format(driver, host, port,
                                               database, user, password)
            )
            self.db = pyodbc.connect(dsn)
            self.db.autocommit = autocommit
            # http://stackoverflow.com/questions/1063770

        elif engine == ENGINE_MYSQL and interface == INTERFACE_JDBC:
            # https://help.ubuntu.com/community/JDBCAndMySQL
            # https://github.com/baztian/jaydebeapi/issues/1
            jclassname = "com.mysql.jdbc.Driver"
            url = "jdbc:mysql://{host}:{port}/{database}".format(
                host=host, port=port, database=database)
            driver_args = [url, user, password]
            jars = None
            libs = None
            logger.info(
                "JDBC connect: jclassname={jclassname}, "
                "url={url}, user={user}, password=[censored]".format(
                    jclassname=jclassname,
                    url=url,
                    user=user,
                )
            )
            self._jdbc_connect(jclassname, driver_args, jars, libs, autocommit)

        elif engine == ENGINE_SQLSERVER and interface == INTERFACE_ODBC:
            # SQL Server:
            # http://code.google.com/p/pyodbc/wiki/ConnectionStrings
            if odbc_connection_string:
                logger.info("Using raw ODBC connection string [censored]")
                connectstring = odbc_connection_string
            elif dsn:
                logger.info(
                    "ODBC connect: DSN={dsn};UID={u};PWD=[censored]".format(
                        dsn=dsn, u=user))
                connectstring = "DSN={};UID={};PWD={}".format(dsn, user,
                                                              password)
            else:
                logger.info(
                    "ODBC connect: DRIVER={dr};SERVER={s};DATABASE={db};"
                    "UID={u};PWD=[censored]".format(
                        dr=driver, s=host, db=database, u=user))
                connectstring = (
                    "DRIVER={};SERVER={};DATABASE={};UID={};PWD={}".format(
                        driver, host, database, user, password)
                )
            self.db = pyodbc.connect(connectstring, unicode_results=True)
            self.db.autocommit = autocommit
            # http://stackoverflow.com/questions/1063770

        elif engine == ENGINE_SQLSERVER and interface == INTERFACE_JDBC:
            # jar tvf sqljdbc41.jar
            # https://msdn.microsoft.com/en-us/sqlserver/aa937724.aspx
            # https://msdn.microsoft.com/en-us/library/ms378428(v=sql.110).aspx
            # https://msdn.microsoft.com/en-us/library/ms378988(v=sql.110).aspx
            jclassname = 'com.microsoft.sqlserver.jdbc.SQLServerDriver'
            urlstem = 'jdbc:sqlserver://{host}:{port};'.format(
                host=host,
                port=port
            )
            nvp = {}
            if database:
                nvp['databaseName'] = database
            nvp['user'] = user
            nvp['password'] = password
            nvp['responseBuffering'] = 'adaptive'  # default is 'full'
            # ... THIS CHANGE (responseBuffering = adaptive) stops the JDBC
            # driver crashing on cursor close [in a socket recv() call] when
            # it's fetched a VARBINARY(MAX) field.
            nvp['selectMethod'] = 'cursor'  # trying this; default is 'direct'
            url = urlstem + ';'.join(
                '{}={}'.format(x, y) for x, y in six.iteritems(nvp))

            nvp['password'] = '[censored]'
            url_censored = urlstem + ';'.join(
                '{}={}'.format(x, y) for x, y in six.iteritems(nvp))
            logger.info(
                'jdbc connect: jclassname={jclassname}, url = {url}'.format(
                    jclassname=jclassname,
                    url=url_censored
                )
            )

            driver_args = [url]
            jars = None
            libs = None
            self._jdbc_connect(jclassname, driver_args, jars, libs, autocommit)

        elif engine == ENGINE_ACCESS and interface == INTERFACE_ODBC:
            dsn = "DSN={}".format(dsn)
            logger.info("ODBC connect: DSN={}".format(dsn))
            self.db = pyodbc.connect(dsn)
            self.db.autocommit = autocommit
            # http://stackoverflow.com/questions/1063770

        else:
            raise ValueError(
                "Unknown 'engine'/'interface' combination: {}/{}".format(
                    engine, interface
                )
            )

        return True

    def _jdbc_connect(self, jclassname, driver_args, jars, libs,
                      autocommit):
        try:
            self.db = jaydebeapi.connect(jclassname, driver_args, jars=jars,
                                         libs=libs)
            # ... which should have had its connectors altered by
            #     reconfigure_jaydebeapi()
        except Exception as e:
            logger.error(self.flavour.jdbc_error_help())
            self.reraise_connection_exception(e)
        # http://almostflan.com/2012/03/01/turning-off-autocommit-in-jaydebeapi/  # noqa
        self.db.jconn.setAutoCommit(autocommit)

    # -------------------------------------------------------------------------
    # ping
    # -------------------------------------------------------------------------

    def ping(self):
        """Pings a database connection, reconnecting if necessary."""
        if self.db is None or self.db_pythonlib not in [PYTHONLIB_MYSQLDB,
                                                        PYTHONLIB_PYMYSQL]:
            return
        try:
            self.db.ping(True)  # test connection; reconnect upon failure
            # ... should auto-reconnect; however, it seems to fail the first
            # time, then work the next time.
            # Exception (the first time) is:
            # <class '_mysql_exceptions.OperationalError'>:
            #   (2006, 'MySQL server has gone away')
            # http://mail.python.org/pipermail/python-list/2008-February/
            #        474598.html
        except mysql.OperationalError:  # loss of connection
            self.db = None
            self.connect_to_database_mysql(
                self._database, self._user, self._password, self._server,
                self._port, self._charset, self._use_unicode)  # reconnect

    # -------------------------------------------------------------------------
    # Specific connection methods
    # -------------------------------------------------------------------------

    def connect_to_database_mysql(self,
                                  database,
                                  user,
                                  password,
                                  server="localhost",
                                  port=3306,
                                  charset="utf8",
                                  use_unicode=True,
                                  autocommit=True):
        self.connect(engine=ENGINE_MYSQL, interface=INTERFACE_MYSQL,
                     database=database, user=user, password=password,
                     host=server, port=port, charset=charset,
                     use_unicode=use_unicode, autocommit=autocommit)

    def connect_to_database_odbc_mysql(self,
                                       database,
                                       user,
                                       password,
                                       server="localhost",
                                       port=3306,
                                       driver="{MySQL ODBC 5.1 Driver}",
                                       autocommit=True):
        """Connects to a MySQL database via ODBC."""
        self.connect(engine=ENGINE_MYSQL, interface=INTERFACE_ODBC,
                     database=database, user=user, password=password,
                     host=server, port=port, driver=driver,
                     autocommit=autocommit)

    def connect_to_database_odbc_sqlserver(self,
                                           odbc_connection_string=None,
                                           dsn=None,
                                           database=None,
                                           user=None,
                                           password=None,
                                           server="localhost",
                                           driver="{SQL Server}",
                                           autocommit=True):
        """Connects to an SQL Server database via ODBC."""
        self.connect(engine=ENGINE_SQLSERVER, interface=INTERFACE_ODBC,
                     odbc_connection_string=odbc_connection_string,
                     dsn=dsn,
                     database=database, user=user, password=password,
                     host=server, driver=driver,
                     autocommit=autocommit)

    def connect_to_database_odbc_access(self, dsn, autocommit=True):
        """Connects to an Access database via ODBC, with the DSN
        prespecified."""
        self.connect(engine=ENGINE_ACCESS, interface=INTERFACE_ODBC,
                     dsn=dsn, autocommit=autocommit)

    # -------------------------------------------------------------------------
    # Engine configurations
    # -------------------------------------------------------------------------

    def get_coltype_expr(self):
        return self.flavour.column_type_expr()

    def get_current_schema_expr(self):
        return self.flavour.current_schema_expr()

    def get_delims(self):
        return self.flavour.delims()

    # -------------------------------------------------------------------------
    # Generic SQL and database operations
    # CONVENTION: PK is the first field in the fieldlist
    # Thus fieldlist[0] means the PK name,
    # and fieldlist[1:] means all non-PK fields
    # -------------------------------------------------------------------------

    def is_open(self):
        """Is the database open?"""
        return self.db is not None

    def ensure_db_open(self):
        """Raise NoDatabaseError if the database isn't open."""
        if self.db is None:
            raise NoDatabaseError("Database not open")

    def delimit(self, x):
        """Delimits e.g. a fieldname."""
        return delimit(x, self.get_delims())

    def commit(self):
        """Commits the transaction."""
        self.ensure_db_open()
        self.db.commit()
        logger.debug("commit")

    def rollback(self):
        """Rolls back the transaction."""
        self.ensure_db_open()
        self.db.rollback()
        logger.debug("rollback")

    def insert_record(self, table, fields, values,
                      update_on_duplicate_key=False):
        """Inserts a record into database, table "table", using the list of
        fieldnames and the list of values. Returns the new PK (or None)."""
        self.ensure_db_open()
        if len(fields) != len(values):
            raise AssertionError("Field/value mismatch")
        if update_on_duplicate_key:
            sql = get_sql_insert_or_update(table, fields, self.get_delims())
        else:
            sql = get_sql_insert(table, fields, self.get_delims())
        sql = self.localize_sql(sql)
        new_pk = None
        logger.debug("About to insert_record with SQL template: " + sql)
        try:
            cursor = self.db.cursor()
            debug_sql(sql, values)
            cursor.execute(sql, values)
            # ... binds the placeholders (?, %s) to values in the process
            new_pk = get_pk_of_last_insert(cursor)
            logger.debug("Record inserted.")
            return new_pk
        except:
            logger.exception("insert_record: Failed to insert record.")
            raise

    def insert_record_by_fieldspecs_with_values(self, table, fieldspeclist):
        """Inserts a record into the database using a list of fieldspecs having
        their value stored under the 'value' key.
        """
        fields = []
        values = []
        for fs in fieldspeclist:
            fields.append(fs["name"])
            values.append(fs["value"])
        return self.insert_record(table, fields, values)

    def insert_record_by_dict(self, table, valuedict):
        """Inserts a record into database, table "table", using a dictionary
        containing field/value mappings. Returns the new PK (or None)."""
        if not valuedict:
            return None
        n = len(valuedict)
        fields = []
        args = []
        for f, v in six.iteritems(valuedict):
            fields.append(self.delimit(f))
            args.append(v)
        query = """
            INSERT INTO {table}
                ({fields})
                VALUES ({placeholders})
        """.format(
            table=table,
            fields=",".join(fields),
            placeholders=",".join(["?"]*n)
        )
        query = self.localize_sql(query)
        logger.debug("About to insert_record_by_dict with SQL template: "
                     + query)
        try:
            cursor = self.db.cursor()
            debug_sql(query, args)
            cursor.execute(query, args)
            new_pk = get_pk_of_last_insert(cursor)
            logger.debug("Record inserted.")
            return new_pk
        except:
            logger.exception("insert_record_by_dict: Failed to insert record.")
            raise

    def insert_multiple_records(self, table, fields, records):
        """Inserts a record into database, table "table", using the list of
        fieldnames and the list of records (each a list of values).
        Returns number of rows affected."""
        self.ensure_db_open()
        sql = self.localize_sql(get_sql_insert(table, fields,
                                               self.get_delims()))
        logger.debug("About to insert multiple records with SQL template: "
                     + sql)
        try:
            cursor = self.db.cursor()
            debug_sql(sql, records)
            cursor.executemany(sql, records)
            # ... binds the placeholders (?, %s) to values in the process
            # http://www.python.org/dev/peps/pep-0249/
            logger.debug("Records inserted.")
            return cursor.rowcount
        except:
            logger.exception("insert_multiple_records: Failed to insert "
                             "records.")
            raise

    def db_exec_with_cursor(self, cursor, sql, *args):
        """Executes SQL on a supplied cursor, with "?" placeholders,
        substituting in the arguments. Returns number of rows affected."""
        sql = self.localize_sql(sql)
        try:
            debug_sql(sql, args)
            cursor.execute(sql, args)
            return cursor.rowcount
        except:
            logger.exception("db_exec_with_cursor: SQL was: " + sql)
            raise
        # MySQLdb:
        #   cursor.execute("SELECT * FROM blah WHERE field=%s", (value,))
        # pyodbc 1:
        #   cursor.execute("SELECT * FROM blah WHERE field=?", (value,))
        # pyodbc 2:
        #   cursor.execute("SELECT * FROM blah WHERE field=?", value)

    def db_exec(self, sql, *args):
        """Executes SQL (with "?" placeholders for arguments)."""
        self.ensure_db_open()
        cursor = self.db.cursor()
        return self.db_exec_with_cursor(cursor, sql, *args)

    def db_exec_and_commit(self, sql, *args):
        """Execute SQL and commit."""
        rowcount = self.db_exec(sql, *args)
        self.commit()
        return rowcount

    def db_exec_literal(self, sql):
        """Executes SQL without modification. Returns rowcount."""
        self.ensure_db_open()
        cursor = self.db.cursor()
        debug_sql(sql)
        try:
            cursor.execute(sql)
            return cursor.rowcount
        except:
            logger.exception("db_exec_literal: SQL was: " + sql)
            raise

    def get_literal_sql_with_arguments(self, query, *args):
        query = self.localize_sql(query)
        # Now into the back end:
        # See cursors.py, connections.py in MySQLdb source.

        # charset = self.db.character_set_name()
        # if isinstance(query, unicode):
        #     query = query.encode(charset)
        # Don't get them double-encoded:
        #   http://stackoverflow.com/questions/6202726/writing-utf-8-string-to-mysql-with-python  # noqa
        if args is not None:
            query = query % self.db.literal(args)
        return query

    def fetchvalue(self, sql, *args):
        """Executes SQL; returns the first value of the first row, or None."""
        row = self.fetchone(sql, *args)
        if row is None:
            return None
        return row[0]

    def fetchone(self, sql, *args):
        """Executes SQL; returns the first row, or None."""
        self.ensure_db_open()
        cursor = self.db.cursor()
        self.db_exec_with_cursor(cursor, sql, *args)
        try:
            return cursor.fetchone()
        except:
            logger.exception("fetchone: SQL was: " + sql)
            raise

    def fetchall(self, sql, *args):
        """Executes SQL; returns all rows, or []."""
        self.ensure_db_open()
        cursor = self.db.cursor()
        self.db_exec_with_cursor(cursor, sql, *args)
        try:
            rows = cursor.fetchall()
            return rows
        except:
            logger.exception("fetchall: SQL was: " + sql)
            raise

    def gen_fetchall(self, sql, *args):
        """fetchall() as a generator."""
        self.ensure_db_open()
        cursor = self.db.cursor()
        self.db_exec_with_cursor(cursor, sql, *args)
        try:
            row = cursor.fetchone()
            while row is not None:
                yield row
                row = cursor.fetchone()
        except:
            logger.exception("gen_fetchall: SQL was: " + sql)
            raise

    def gen_fetchfirst(self, sql, *args):
        """fetch first values, as a generator."""
        self.ensure_db_open()
        cursor = self.db.cursor()
        self.db_exec_with_cursor(cursor, sql, *args)
        try:
            row = cursor.fetchone()
            while row is not None:
                yield row[0]
                row = cursor.fetchone()
        except:
            logger.exception("gen_fetchfirst: SQL was: " + sql)
            raise

    def fetchall_with_fieldnames(self, sql, *args):
        """Executes SQL; returns (rows, fieldnames)."""
        self.ensure_db_open()
        cursor = self.db.cursor()
        self.db_exec_with_cursor(cursor, sql, *args)
        try:
            rows = cursor.fetchall()
            fieldnames = [i[0] for i in cursor.description]
            return (rows, fieldnames)
        except:
            logger.exception("fetchall_with_fieldnames: SQL was: " + sql)
            raise

    def fetchall_as_dictlist(self, sql, *args):
        """Executes SQL; returns list of dictionaries, where each dict contains
        fieldname/value pairs."""
        self.ensure_db_open()
        cursor = self.db.cursor()
        self.db_exec_with_cursor(cursor, sql, *args)
        try:
            rows = cursor.fetchall()
            fieldnames = [i[0] for i in cursor.description]
            dictlist = []
            for r in rows:
                dictlist.append(dict(zip(fieldnames, r)))
            return dictlist
        except:
            logger.exception("fetchall_as_dictlist: SQL was: " + sql)
            raise

    def fetchallfirstvalues(self, sql, *args):
        """Executes SQL; returns list of first values of each row."""
        rows = self.fetchall(sql, *args)
        return [row[0] for row in rows]

    def fetch_fieldnames(self, sql, *args):
        """Executes SQL; returns just the output fieldnames."""
        self.ensure_db_open()
        cursor = self.db.cursor()
        self.db_exec_with_cursor(cursor, sql, *args)
        try:
            return [i[0] for i in cursor.description]
        except:
            logger.exception("fetch_fieldnames: SQL was: " + sql)
            raise

    def localize_sql(self, sql):
        """Translates ?-placeholder SQL to appropriate dialect.

        For example, MySQLdb uses %s rather than ?.
        """
        # pyodbc seems happy with ? now (pyodbc.paramstyle is 'qmark');
        # using ? is much simpler, because we may want to use % with LIKE
        # fields or (in my case) with date formatting strings for
        # STR_TO_DATE().
        # If you get this wrong, you may see "not all arguments converted
        # during string formatting";
        # http://stackoverflow.com/questions/9337134
        if self.db_pythonlib in [PYTHONLIB_PYMYSQL, PYTHONLIB_MYSQLDB]:
            # These engines use %, so we need to convert ? to %, without
            # breaking literal % values.
            sql = _PERCENT_REGEX.sub("%%", sql)
            # ... replace all % with %% first
            sql = _QUERY_VALUE_REGEX.sub("%s", sql)
            # ... replace all ? with %s in the SQL
        # Otherwise: engine uses ?, so we don't have to fiddle.
        return sql

    def fetch_object_from_db_by_pk(self, obj, table, fieldlist, pkvalue):
        """Fetches object from database table by PK value. Writes back to
        object. Returns True/False for success/failure."""
        if pkvalue is None:
            blank_object(obj, fieldlist)
            return False
        row = self.fetchone(
            get_sql_select_all_non_pk_fields_by_pk(table, fieldlist,
                                                   self.get_delims()),
            pkvalue
        )
        if row is None:
            blank_object(obj, fieldlist)
            return False
        setattr(obj, fieldlist[0], pkvalue)  # set PK value of obj
        assign_from_list(obj, fieldlist[1:], row)  # set non-PK values of obj
        return True

    def fetch_object_from_db_by_other_field(self, obj, table, fieldlist,
                                            keyname, keyvalue):
        """Fetches object from database table by a field specified by
        keyname/keyvalue. Writes back to object. Returns True/False for
        success/failure."""
        row = self.fetchone(
            get_sql_select_all_fields_by_key(table, fieldlist, keyname,
                                             self.get_delims()),
            keyvalue
        )
        if row is None:
            blank_object(obj, fieldlist)
            return False
        assign_from_list(obj, fieldlist, row)
        return True

    def fetch_all_objects_from_db(self, cls, table, fieldlist,
                                  construct_with_pk, *args):
        """Fetches all objects from a table, returning an array of objects of
        class cls."""
        return self.fetch_all_objects_from_db_where(
            cls, table, fieldlist, construct_with_pk, None, *args)

    def fetch_all_objects_from_db_by_pklist(self, cls, table, fieldlist,
                                            pklist, construct_with_pk, *args):
        """Fetches all objects from a table, given a list of PKs."""
        objarray = []
        for pk in pklist:
            if construct_with_pk:
                obj = cls(pk, *args)  # should do its own fetching
            else:
                obj = cls(*args)
                self.fetch_object_from_db_by_pk(obj, table, fieldlist, pk)
            objarray.append(obj)
        return objarray

    def fetch_all_objects_from_db_where(self, cls, table, fieldlist,
                                        construct_with_pk, wheredict, *args):
        """Fetches all objects from a table, given a set of WHERE criteria
        (ANDed), returning an array of objects of class cls."""
        sql = ("SELECT " + self.delimit(fieldlist[0])
               + " FROM " + self.delimit(table))
        if wheredict is not None:
            sql += " WHERE " + " AND ".join([
                self.delimit(k) + "=?"
                for k in wheredict.keys()
            ])
            whereargs = wheredict.values()
            # logger.debug("fetch_all_objects_from_db_where: sql = " + sql)
            pklist = self.fetchallfirstvalues(sql, *whereargs)
        else:
            pklist = self.fetchallfirstvalues(sql)
        return self.fetch_all_objects_from_db_by_pklist(
            cls, table, fieldlist, pklist, construct_with_pk, *args)

    def count_where(self, table, wheredict=None):
        """Counts rows in a table, given a set of WHERE criteria (ANDed),
        returning a count."""
        sql = "SELECT COUNT(*) FROM " + self.delimit(table)
        if wheredict is not None:
            sql += " WHERE " + " AND ".join([
                self.delimit(k) + "=?"
                for k in wheredict.keys()
            ])
            whereargs = wheredict.values()
            count = self.fetchone(sql, *whereargs)[0]
        else:
            count = self.fetchone(sql)[0]
        return count

    def insert_object_into_db_pk_known(self, obj, table, fieldlist):
        """Inserts object into database table, with PK (first field) already
        known."""
        pkvalue = getattr(obj, fieldlist[0])
        if pkvalue is None:
            raise AssertionError("insert_object_intoto_db_pk_known called "
                                 "without PK")
        valuelist = []
        for f in fieldlist:
            valuelist.append(getattr(obj, f))
        self.db_exec(
            get_sql_insert(table, fieldlist, self.get_delims()),
            *valuelist
        )

    def insert_object_into_db_pk_unknown(self, obj, table, fieldlist):
        """Inserts object into database table, with PK (first field) initially
        unknown (and subsequently set in the object from the database)."""
        self.ensure_db_open()
        valuelist = []
        for f in fieldlist[1:]:
            valuelist.append(getattr(obj, f))
        cursor = self.db.cursor()
        self.db_exec_with_cursor(
            cursor,
            get_sql_insert_without_first_field(table, fieldlist,
                                               self.get_delims()),
            *valuelist
        )
        pkvalue = get_pk_of_last_insert(cursor)
        setattr(obj, fieldlist[0], pkvalue)

    def update_object_in_db(self, obj, table, fieldlist):
        """Updates an object in the database (saves it to the database, where
        it exists there already)."""
        self.ensure_db_open()
        pkvalue = getattr(obj, fieldlist[0])
        valuelist = []
        # Non-PK fields first
        for f in fieldlist[1:]:
            valuelist.append(getattr(obj, f))
        # Then PK
        valuelist.append(pkvalue)
        cursor = self.db.cursor()
        self.db_exec_with_cursor(
            cursor,
            get_sql_update_by_first_field(table, fieldlist, self.get_delims()),
            *valuelist
        )

    def cursor(self):
        """Returns database cursor, or raises NoDatabaseError."""
        self.ensure_db_open()
        return self.db.cursor()

    def save_object_to_db(self, obj, table, fieldlist, is_new_record):
        """Saves a object to the database, inserting or updating as
        necessary."""
        if is_new_record:
            pkvalue = getattr(obj, fieldlist[0])
            if pkvalue is None:
                self.insert_object_into_db_pk_unknown(obj, table, fieldlist)
            else:
                self.insert_object_into_db_pk_known(obj, table, fieldlist)
        else:
            self.update_object_in_db(obj, table, fieldlist)

    def does_row_exist(self, table, field, value):
        """Checks for the existence of a record by a single field (typically a
        PK)."""
        sql = ("SELECT COUNT(*) FROM " + self.delimit(table)
               + " WHERE " + self.delimit(field) + "=?")
        row = self.fetchone(sql, value)
        return True if row[0] >= 1 else False

    def delete_by_field(self, table, field, value):
        """Deletes all records where "field" is "value"."""
        sql = ("DELETE FROM " + self.delimit(table)
               + " WHERE " + self.delimit(field) + "=?")
        return self.db_exec(sql, value)

    # -------------------------------------------------------------------------
    # Index
    # -------------------------------------------------------------------------
    def index_exists(self, table, indexname):
        """Does an index exist? (Specific to MySQL.)"""
        # MySQL:
        sql = ("SELECT COUNT(*) FROM information_schema.statistics"
               " WHERE table_name=? AND index_name=?")
        row = self.fetchone(sql, table, indexname)
        return True if row[0] >= 1 else False

    def create_index(self, table, field, nchars=None, indexname=None,
                     unique=False):
        """Creates an index (default name _idx_FIELDNAME), unless it exists
        already."""
        limit = ""
        if nchars is not None:
            limit = "({})".format(nchars)
        if indexname is None:
            indexname = "_idx_{}".format(field)
        if self.index_exists(table, indexname):
            return
        uniquestr = "UNIQUE" if unique else ""
        sql = (
            "CREATE {unique} INDEX {indexname} "
            "ON {table} ({field}{limit})".format(
                unique=uniquestr,
                indexname=indexname,
                table=table,
                field=field,
                limit=limit,
            )
        )
        return self.db_exec(sql)

    def create_index_from_fieldspec(self, table, fieldspec, indexname=None):
        """Calls create_index based on a fieldspec, if the fieldspec has
        indexed = True."""
        if "indexed" in fieldspec and fieldspec["indexed"]:
            if "index_nchar" in fieldspec:
                nchar = fieldspec["index_nchar"]
            else:
                nchar = None
            self.create_index(table, fieldspec["name"], nchar,
                              indexname=indexname)

    def create_fulltext_index(self, table, field, indexname=None):
        """Creates a FULLTEXT index (default name _idxft_FIELDNAME), unless it
        exists already. See:

        http://dev.mysql.com/doc/refman/5.6/en/innodb-fulltext-index.html
        http://dev.mysql.com/doc/refman/5.0/en/fulltext-search.html
        """
        if indexname is None:
            indexname = "_idxft_{}".format(field)
        if self.index_exists(table, indexname):
            return
        sql = "CREATE FULLTEXT INDEX {} ON {} ({})".format(indexname, table,
                                                           field)
        return self.db_exec(sql)

    # -------------------------------------------------------------------------
    # Fieldspec lists
    # -------------------------------------------------------------------------

    def fieldnames_from_fieldspeclist(self, fieldspeclist):
        """Returns fieldnames from a field specification list."""
        return [x["name"] for x in fieldspeclist]

    def fieldname_from_fieldspec(self, fieldspec):
        """Returns a fieldname from a field specification."""
        return fieldspec["name"]

    def fielddefsql_from_fieldspec(self, fieldspec):
        """Returns SQL fragment to define a field."""
        sql = fieldspec["name"] + " " + fieldspec["sqltype"]
        if "notnull" in fieldspec and fieldspec["notnull"]:
            sql += " NOT NULL"
        if "autoincrement" in fieldspec and fieldspec["autoincrement"]:
            sql += " AUTO_INCREMENT"
        if "pk" in fieldspec and fieldspec["pk"]:
            sql += " PRIMARY KEY"
        else:
            if "unique" in fieldspec and fieldspec["unique"]:
                sql += " UNIQUE"
        if "comment" in fieldspec:
            sql += " COMMENT " + sql_quote_string(fieldspec["comment"])
        return sql

    def fielddefsql_from_fieldspeclist(self, fieldspeclist):
        """Returns list of field-defining SQL fragments."""
        return ",".join([
            self.fielddefsql_from_fieldspec(x)
            for x in fieldspeclist
        ])

    def fieldspec_subset_by_name(self, fieldspeclist, fieldnames):
        """Returns a subset of the fieldspecs matching the fieldnames list."""
        result = []
        for x in fieldspeclist:
            if x["name"] in fieldnames:
                result.append(x)
        return result

    # -------------------------------------------------------------------------
    # Tables
    # -------------------------------------------------------------------------

    def table_exists(self, tablename):
        """Does the table exist?"""
        # information_schema is ANSI standard
        sql = """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name=?
            AND table_schema={}
        """.format(self.get_current_schema_expr())
        row = self.fetchone(sql, tablename)
        return True if row[0] >= 1 else False

    def column_exists(self, tablename, column):
        """Does the column exist?"""
        sql = """
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_name=?
            AND column_name=?
            AND table_schema={}
        """.format(self.get_current_schema_expr())
        row = self.fetchone(sql, tablename, column)
        return True if row[0] >= 1 else False

    def drop_table(self, tablename):
        """Drops a table. Use caution!"""
        sql = "DROP TABLE IF EXISTS {}".format(tablename)
        logger.info("Dropping table " + tablename +
                    " (ignore any warning here)")
        return self.db_exec_literal(sql)

    def drop_view(self, viewname):
        """Drops a view."""
        sql = "DROP VIEW IF EXISTS {}".format(viewname)
        logger.info("Dropping view " + viewname +
                    " (ignore any warning here)")
        return self.db_exec_literal(sql)

    def make_table(self, tablename, fieldspeclist, dynamic=False,
                   compressed=False):
        """Makes a table, if it doesn't already exist."""
        if self.table_exists(tablename):
            logger.info("Skipping creation of table " + tablename
                        + " (already exists)")
            return
        if not self.is_mysql():
            dynamic = False
            compressed = False
        # http://dev.mysql.com/doc/refman/5.5/en/innodb-compression-usage.html
        sql = """
            CREATE TABLE IF NOT EXISTS {tablename}
            ({fieldspecs})
            {dynamic}
            {compressed}
        """.format(
            tablename=tablename,
            fieldspecs=self.fielddefsql_from_fieldspeclist(fieldspeclist),
            dynamic="ROW_FORMAT=DYNAMIC" if dynamic else "",
            compressed="ROW_FORMAT=COMPRESSED" if compressed else "",
        )
        logger.info("Creating table " + tablename)
        return self.db_exec_literal(sql)

    def rename_table(self, from_table, to_table):
        """Renames a table. MySQL-specific."""
        if not self.table_exists(from_table):
            logger.info("Skipping renaming of table " + from_table +
                        " (doesn't exist)")
            return
        if self.table_exists(to_table):
            raise RuntimeError("Can't rename table {} to {}: destination "
                               "already exists!".format(from_table, to_table))
        logger.info("Renaming table {} to {}".format(from_table, to_table))
        sql = "RENAME TABLE {} TO {}".format(from_table, to_table)
        return self.db_exec_literal(sql)

    def add_column(self, tablename, fieldspec):
        """Adds a column to an existing table."""
        sql = "ALTER TABLE {} ADD COLUMN {}".format(
            tablename, self.fielddefsql_from_fieldspec(fieldspec))
        logger.info(sql)
        return self.db_exec_literal(sql)

    def drop_column(self, tablename, fieldname):
        """Drops (deletes) a column from an existing table."""
        sql = "ALTER TABLE {} DROP COLUMN {}".format(tablename, fieldname)
        logger.info(sql)
        return self.db_exec_literal(sql)

    def modify_column_if_table_exists(self, tablename, fieldname, newdef):
        """Alters a column's definition without renaming it."""
        if not self.table_exists(tablename):
            return
        sql = "ALTER TABLE {t} MODIFY COLUMN {field} {newdef}".format(
            t=tablename,
            field=fieldname,
            newdef=newdef
        )
        logger.info(sql)
        return self.db_exec_literal(sql)

    def change_column_if_table_exists(self, tablename, oldfieldname,
                                      newfieldname, newdef):
        """Renames a column and alters its definition."""
        if not self.table_exists(tablename):
            return
        if not self.column_exists(tablename, oldfieldname):
            return
        sql = "ALTER TABLE {t} CHANGE COLUMN {old} {new} {newdef}".format(
            t=tablename,
            old=oldfieldname,
            new=newfieldname,
            newdef=newdef,
        )
        logger.info(sql)
        return self.db_exec_literal(sql)

    def create_or_update_table(self, tablename, fieldspeclist,
                               drop_superfluous_columns=False,
                               dynamic=False,
                               compressed=False):
        """Make table, if it doesn't exist.
        Add fields that aren't there.
        Warn about superfluous fields, but don't delete them, unless
            drop_superfluous_columns == True.
        Make indexes, if requested.
        """

        # 1. Make table, if it doesn't exist
        self.make_table(tablename, fieldspeclist, dynamic=dynamic,
                        compressed=compressed)

        # 2. Are all the fields there?
        # ... copes fine with fieldnames coming back in Unicode and being
        #     compared to str
        fields_in_db = set(self.fetch_column_names(tablename))
        desired_fieldnames = set(
            self.fieldnames_from_fieldspeclist(fieldspeclist))
        missing_fieldnames = desired_fieldnames - fields_in_db
        missing_fieldspecs = self.fieldspec_subset_by_name(fieldspeclist,
                                                           missing_fieldnames)
        for f in missing_fieldspecs:
            self.add_column(tablename, f)

        # 3. Anything superfluous?
        superfluous_fieldnames = fields_in_db - desired_fieldnames
        for f in superfluous_fieldnames:
            if drop_superfluous_columns:
                logger.warn("... dropping superfluous field: " + f)
                self.drop_column(tablename, f)
            else:
                logger.warn("... superfluous field (ignored): " + f)

        # 4. Make indexes, if some have been requested:
        for fs in fieldspeclist:
            self.create_index_from_fieldspec(tablename, fs)

        # NOT easy to do field type checks; for example, you might create
        # a field in MySQL as BOOLEAN but then its type within
        # information_schema.columns.data_type might be "tinyint".

    def get_all_table_details(self):
        """Returns all information the database has on a table."""
        return self.flavour.get_all_table_details(self)

    def get_all_table_names(self):
        """Returns all table names in the database."""
        return self.flavour.get_all_table_names(self)

    def describe_table(self, table):
        """Returns details on a specific table."""
        return self.flavour.describe_table(self, table)

    def fetch_column_names(self, table):
        """Returns all column names for a table."""
        return self.flavour.fetch_column_names(self, table)

    def get_datatype(self, table, column):
        """Returns database SQL datatype for a column: e.g. VARCHAR."""
        return self.flavour.get_datatype(self, table, column).upper()

    def get_column_type(self, table, column):
        """Returns database SQL datatype for a column, e.g. VARCHAR(50)."""
        return self.flavour.get_column_type(self, table, column).upper()

    def get_comment(self, table, column):
        """Returns database SQL comment for a column."""
        return self.flavour.get_comment(self, table, column)

    def debug_query(self, sql, *args):
        """Executes SQL and writes the result to the logger."""
        rows = self.fetchall(sql, *args)
        debug_query_result(rows)

    def wipe_table(self, table):
        """Delete all records from a table. Use caution!"""
        sql = "DELETE FROM " + self.delimit(table)
        return self.db_exec(sql)

    def create_or_replace_primary_key(self, table, fieldnames):
        """Make a primary key, or replace it if it exists."""
        # *** create_or_replace_primary_key: Uses code specific to MySQL
        sql = """
            SELECT COUNT(*)
            FROM information_schema.table_constraints
            WHERE table_name=?
            AND table_schema={}
            AND constraint_name='PRIMARY'
        """.format(self.get_current_schema_expr())
        # http://forums.mysql.com/read.php?10,114742,114748#msg-114748
        row = self.fetchone(sql, table)
        has_pk_already = True if row[0] >= 1 else False
        drop_pk_if_exists = " DROP PRIMARY KEY," if has_pk_already else ""
        fieldlist = ",".join([self.delimit(f) for f in fieldnames])
        sql = ("ALTER TABLE " + self.delimit(table)
               + drop_pk_if_exists
               + " ADD PRIMARY KEY(" + fieldlist + ")")
        # http://stackoverflow.com/questions/8859353
        return self.db_exec(sql)

    # =========================================================================
    # Flavours
    # =========================================================================

    def get_flavour(self):
        if not self.flavour:
            return None
        return self.flavour.flavour()

    def is_sqlserver(self):
        return self.get_flavour() == FLAVOUR_SQLSERVER

    def is_mysql(self):
        return self.get_flavour() == FLAVOUR_MYSQL

    def mysql_using_file_per_table(self):
        return self.flavour.mysql_using_file_per_table(self)

    def mysql_using_innodb_barracuda(self):
        return self.flavour.mysql_using_innodb_barracuda(self)

    def mysql_table_using_barracuda(self, tablename):
        return self.flavour.mysql_table_using_barracuda(self, tablename)

    def mysql_convert_table_to_barracuda(self, tablename, compressed=False):
        self.flavour.mysql_convert_table_to_barracuda(
            self, tablename, logger=logger, compressed=compressed)

    def mysql_using_innodb_strict_mode(self):
        return self.flavour.mysql_using_innodb_strict_mode(self)

    def mysql_get_max_allowed_packet(self):
        return self.flavour.mysql_get_max_allowed_packet(self)

    def get_schema(self):
        return self.fetchvalue("SELECT {}".format(
            self.get_current_schema_expr()))

    def is_read_only(self):
        """Does the user have read-only access to the database?
        This is a safety check, but should NOT be the only safety check!"""
        return self.flavour.is_read_only(self, logger=logger)

    # =========================================================================
    # Debugging
    # =========================================================================

    def java_garbage_collect(self):
        # http://stackoverflow.com/questions/1903041
        # http://docs.oracle.com/javase/7/docs/api/java/lang/Runtime.html
        if not JDBC_AVAILABLE:
            return
        if self.db_pythonlib != PYTHONLIB_JAYDEBEAPI:
            return
        logger.info("Calling Java garbage collector...")
        rt = jpype.java.lang.Runtime.getRuntime()
        rt.gc()
        logger.info("... done")
