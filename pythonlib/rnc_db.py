#!/usr/bin/python
# -*- encoding: utf8 -*-

"""Support functions to interface Python to SQL-based databases conveniently.

Author: Rudolf Cardinal (rudolf@pobox.com)
Created: October 2012
Last update: 19 Mar 2015

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

General note about PyODBC:
    # Fine:
    cursor.execute("SELECT * FROM mytable WHERE myfield=?", 1)
    # NOT fine; will return no rows:
    cursor.execute("SELECT * FROM mytable WHERE myfield=?", None)
    # Fine; will return no rows
    cursor.execute("SELECT * FROM mytable WHERE myfield IS NULL")
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

try:
    import pyodbc  # sudo apt-get install python-pyodbc
    PYODBC_AVAILABLE = True
except:
    PYODBC_AVAILABLE = False
try:
    import MySQLdb  # sudo apt-get install python-mysqldb
    import MySQLdb.converters
    import _mysql
    MYSQLDB_AVAILABLE = True
except:
    MYSQLDB_AVAILABLE = False

import datetime
import re
import logging
logging.basicConfig()
logger = logging.getLogger("rnc_db")
logger.setLevel(logging.INFO)


# =============================================================================
# Constants
# =============================================================================

_QUERY_VALUE_REGEX = re.compile("\?", re.MULTILINE)
_PERCENT_REGEX = re.compile("%", re.MULTILINE)
LINE_EQUALS = "=" * 79
MSG_PYODBC_UNAVAILABLE = "Python pyodbc module not available"
MSG_MYSQLDB_UNAVAILABLE = "Python MySQLdb module not available"


# =============================================================================
# Exceptions
# =============================================================================

class NoDatabaseError(IOError):
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
    return _mysql.string_literal(d.strftime("%Y-%m-%d %H:%M:%S"), c)


# =============================================================================
# Generic routines for objects with database fields
# =============================================================================

def debug_object(obj):
    """Prints key/value pairs for an object's dictionary."""
    pairs = []
    for k, v in vars(obj).items():
        pairs.append("{}={}".format(unicode(k), unicode(v)))
    return ", ".join(pairs)


def dump_database_object(obj, fieldlist):
    """Prints key/value pairs for an object's dictionary."""
    logger.info(LINE_EQUALS)
    logger.info("DUMP OF: " + unicode(obj))
    for f in fieldlist:
        logger.info(f + ": " + unicode(getattr(obj, f)))
    logger.info(LINE_EQUALS)


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

REGEX_INVALID_TABLE_FIELD_CHARS = re.compile("[^a-zA-Z0-9_]")


def is_valid_field_name(f):
    if not f:
        return False
    if bool(REGEX_INVALID_TABLE_FIELD_CHARS.search(f)):
        return False
    return True


def is_valid_table_name(t):
    return is_valid_field_name(t)


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
    "CHAR", "VARCHAR",
    "TINYTEXT", "TEXT", "MEDIUMTEXT", "LONGTEXT",
]
SQLTYPES_BINARY = [
    "BINARY", "BLOB", "LONGBLOB", "VARBINARY",
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
        length = int(datatype_long[find_open + 1:find_close])
    else:
        length = None
    return (datatype_short, length)


def is_sqltype_valid(datatype_long):
    (datatype_short, length) = split_long_sqltype(datatype_long)
    return datatype_short in SQLTYPES_ALL


def is_sqltype_date(datatype_long):
    (datatype_short, length) = split_long_sqltype(datatype_long)
    return datatype_short in SQLTYPES_WITH_DATE


def is_sqltype_text_over_one_char(datatype_long):
    (datatype_short, length) = split_long_sqltype(datatype_long)
    possibles_short_text = ["CHAR(1)", "VARCHAR(1)"]
    return not (
        datatype_short in SQLTYPES_NOT_TEXT
        or datatype_long in possibles_short_text
    )


def is_sqltype_numeric(datatype_long):
    (datatype_short, length) = split_long_sqltype(datatype_long)
    return datatype_short in SQLTYPES_NUMERIC


def is_sqltype_integer(datatype_long):
    (datatype_short, length) = split_long_sqltype(datatype_long)
    return datatype_short in SQLTYPES_INTEGER


def does_sqltype_require_index_len(datatype_long):
    (datatype_short, length) = split_long_sqltype(datatype_long)
    return datatype_short in ["TEXT", "BLOB"]


def does_sqltype_merit_fulltext_index(datatype_long):
    return datatype_long in ["TEXT"]


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
    """Connects via MySQLdb and creates a database."""
    con = MySQLdb.connect(
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
    """Connects via MySQLdb and creates a database superuser."""
    con = MySQLdb.connect(
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
# Database support class. ODBC via pyodbc or MySQLdb.
# =============================================================================

class DatabaseSupporter:
    """Support class for databases using pyodbc or MySQLdb."""
    FLAVOUR_SQLSERVER = "sqlserver"
    FLAVOUR_MYSQL = "mysql"
    FLAVOUR_ACCESS = "access"
    PYTHONLIB_MYSQLDB = "mysqldb"
    PYTHONLIB_PYODBC = "pyodbc"
    MYSQL_COLUMN_TYPE_EXPR = "column_type"
    SQLSERVER_COLUMN_TYPE_EXPR = """
        (CASE WHEN character_maximum_length > 0
         THEN data_type + '(' +
            CAST(character_maximum_length AS VARCHAR(20)) + ')'
         ELSE data_type
         END)
    """
    ACCESS_COLUMN_TYPE_EXPR = "NULL"  # don't know how

    def __init__(self):
        self.db = None
        self.db_flavour = None
        self.db_pythonlib = None
        self.schema = None
        self.delims = ("", "")
        self.autocommit = None
        self.coltype_expr = ""
        # http://stackoverflow.com/questions/2901453
        # http://stackoverflow.com/questions/7311990

    # -------------------------------------------------------------------------
    # MySQLdb
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
        """Connects to a MySQL database via MySQLdb."""
        # MySQL:
        # http://dev.mysql.com/doc/refman/5.1/en/
        #        connector-odbc-configuration-connection-parameters.html
        # http://code.google.com/p/pyodbc/wiki/ConnectionStrings
        FUNCNAME = "connect_to_database_mysql: "
        if not MYSQLDB_AVAILABLE:
            logger.error(FUNCNAME + MSG_MYSQLDB_UNAVAILABLE)
            return False
        try:
            # Between MySQLdb 1.2.3 and 1.2.5, the DateTime2literal function
            # stops producing e.g.
            #   '2014-01-03 18:15:51'
            # and starts producing e.g.
            #   '2014-01-03 18:15:51.842097+00:00'.
            # Let's fix that...
            DateTimeType = datetime.datetime  # as per MySQLdb times.py
            converters = MySQLdb.converters.conversions.copy()
            converters[DateTimeType] = DateTime2literal_RNC
            # See also:
            #   http://stackoverflow.com/questions/11053941

            self.db_flavour = DatabaseSupporter.FLAVOUR_MYSQL
            self.db_pythonlib = DatabaseSupporter.PYTHONLIB_MYSQLDB
            self.db = MySQLdb.connect(
                host=server,
                port=port,
                user=user,
                passwd=password,
                db=database,
                charset=charset,
                use_unicode=use_unicode,
                conv=converters
            )
            self._database = database
            self._user = user
            self._password = password
            self._server = server
            self._port = port
            self._charset = charset
            self._use_unicode = use_unicode
            self.autocommit = autocommit
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

            self.schema = database
            self.delims = ("`", "`")
            self.coltype_expr = DatabaseSupporter.MYSQL_COLUMN_TYPE_EXPR
        except Exception as e:
            err = "{f} Failed to connect to database {d}. {ex}: {msg}".format(
                f=FUNCNAME,
                d=database,
                ex=type(e).__name__,
                msg=str(e),
            )
            logger.error(err)
            raise NoDatabaseError(err)

    def ping(self):
        """Pings a database connection, reconnecting if necessary."""
        if (self.db is None
                or self.db_pythonlib != DatabaseSupporter.PYTHONLIB_MYSQLDB):
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
        except MySQLdb.OperationalError:  # loss of connection
            self.db = None
            self.connect_to_database_mysql(
                self._database, self._user, self._password, self._server,
                self._port, self._charset, self._use_unicode)  # reconnect

    # -------------------------------------------------------------------------
    # pyodbc
    # -------------------------------------------------------------------------

    def connect_to_database_odbc_mysql(self,
                                       database,
                                       user,
                                       password,
                                       server="localhost",
                                       port=3306,
                                       driver="{MySQL ODBC 5.1 Driver}",
                                       autocommit=True):
        """Connects to a MySQL database via ODBC."""
        # MySQL:
        # http://dev.mysql.com/doc/refman/5.1/en/
        #        connector-odbc-configuration-connection-parameters.html
        # http://code.google.com/p/pyodbc/wiki/ConnectionStrings
        # Catch all exceptions, so the error-catcher never shows a password.
        FUNCNAME = "connect_to_database_odbc_mysql: "
        if not PYODBC_AVAILABLE:
            logger.error(FUNCNAME + MSG_PYODBC_UNAVAILABLE)
            return False
        try:
            self.db_flavour = DatabaseSupporter.FLAVOUR_MYSQL
            self.db_pythonlib = DatabaseSupporter.PYTHONLIB_PYODBC
            dsn = ("DRIVER={0};SERVER={1};PORT={2};DATABASE={3};"
                   "USER={4};PASSWORD={5}").format(driver, server, port,
                                                   database, user, password)
            self.db = pyodbc.connect(dsn)
            self.autocommit = autocommit
            self.db.autocommit = autocommit
            # http://stackoverflow.com/questions/1063770
            self.schema = database
            self.delims = ("`", "`")
            self.coltype_expr = DatabaseSupporter.MYSQL_COLUMN_TYPE_EXPR
            return True
        except Exception as e:
            err = "{f} Failed to connect to database {d}. {ex}: {msg}".format(
                f=FUNCNAME,
                d=database,
                ex=type(e).__name__,
                msg=str(e),
            )
            logger.error(err)
            raise NoDatabaseError(err)

    def connect_to_database_odbc_sqlserver(self,
                                           database,
                                           user,
                                           password,
                                           server="localhost",
                                           driver="{SQL Server}",
                                           autocommit=True):
        """Connects to an SQL Server database via ODBC."""
        # SQL Server: http://code.google.com/p/pyodbc/wiki/ConnectionStrings
        FUNCNAME = "connect_to_database_odbc_sqlserver: "
        if not PYODBC_AVAILABLE:
            logger.error(FUNCNAME + MSG_PYODBC_UNAVAILABLE)
            return False
        try:
            self.db_flavour = DatabaseSupporter.FLAVOUR_SQLSERVER
            self.db_pythonlib = DatabaseSupporter.PYTHONLIB_PYODBC
            dsn = "DRIVER={};SERVER={};DATABASE={};UID={};PWD={}".format(
                driver, server, database, user, password)
            self.db = pyodbc.connect(dsn)
            self.autocommit = autocommit
            self.db.autocommit = autocommit
            # http://stackoverflow.com/questions/1063770
            self.schema = database
            self.delims = ("[", "]")
            self.coltype_expr = DatabaseSupporter.SQLSERVER_COLUMN_TYPE_EXPR
            return True
        except Exception as e:
            err = "{f} Failed to connect to database {d}. {ex}: {msg}".format(
                f=FUNCNAME,
                d=database,
                ex=type(e).__name__,
                msg=str(e),
            )
            logger.error(err)
            raise NoDatabaseError(err)

    def connect_to_database_odbc_sqlserver_dsn(self, dsn, user, password,
                                               autocommit=True):
        """Connects to an SQL Server database via ODBC, with the DSN
        prespecified."""
        # SQL Server: http://code.google.com/p/pyodbc/wiki/ConnectionStrings
        FUNCNAME = "connect_to_database_odbc_sqlserver_dsn: "
        if not PYODBC_AVAILABLE:
            logger.error(FUNCNAME + MSG_PYODBC_UNAVAILABLE)
            return False
        try:
            self.db_flavour = DatabaseSupporter.FLAVOUR_SQLSERVER
            self.db_pythonlib = DatabaseSupporter.PYTHONLIB_PYODBC
            full_dsn = "DSN={};UID={};PWD={}".format(dsn, user, password)
            self.db = pyodbc.connect(full_dsn, unicode_results=True)
            self.autocommit = autocommit
            self.db.autocommit = autocommit
            # http://stackoverflow.com/questions/1063770
            self.schema = "dbo"  # default for SQL server
            self.delims = ("[", "]")
            self.coltype_expr = DatabaseSupporter.SQLSERVER_COLUMN_TYPE_EXPR
            return True
        except Exception as e:
            err = (
                "{f} Failed to connect to database; DSN={dsn}, user={u}. "
                "{ex}: {msg}".format(
                    f=FUNCNAME,
                    dsn=dsn,
                    u=user,
                    ex=type(e).__name__,
                    msg=str(e),
                )
            )
            logger.error(err)
            raise NoDatabaseError(err)

    def connect_to_database_odbc_access(self, dsn, autocommit=True):
        """Connects to an Access database via ODBC, with the DSN
        prespecified."""
        FUNCNAME = "connect_to_database_odbc_access: "
        if not PYODBC_AVAILABLE:
            logger.error(FUNCNAME + MSG_PYODBC_UNAVAILABLE)
            return False
        try:
            self.db_flavour = DatabaseSupporter.FLAVOUR_ACCESS
            self.db_pythonlib = DatabaseSupporter.PYTHONLIB_PYODBC
            dsn = "DSN={}".format(dsn)
            self.db = pyodbc.connect(dsn)
            self.autocommit = autocommit
            self.db.autocommit = autocommit
            # http://stackoverflow.com/questions/1063770
            self.schema = "dbo"  # default for SQL server
            self.delims = ("[", "]")
            self.coltype_expr = DatabaseSupporter.ACCESS_COLUMN_TYPE_EXPR
            return True
        except Exception as e:
            err = (
                "{f} Failed to connect to database; DSN={dsn}. "
                "{ex}: {msg}".format(
                    f=FUNCNAME,
                    dsn=dsn,
                    ex=type(e).__name__,
                    msg=str(e),
                )
            )
            logger.error(err)
            raise NoDatabaseError(err)

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
        return delimit(x, self.delims)

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
            sql = get_sql_insert_or_update(table, fields, self.delims)
        else:
            sql = get_sql_insert(table, fields, self.delims)
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
        for f, v in valuedict.iteritems():
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
        sql = self.localize_sql(get_sql_insert(table, fields, self.delims))
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
        charset = self.db.character_set_name()
        if isinstance(query, unicode):
            query = query.encode(charset)
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
        if self.db_pythonlib == DatabaseSupporter.PYTHONLIB_MYSQLDB:
            # pyodbc seems happy with ? now (pyodbc.paramstyle is 'qmark');
            # this is much simpler, because we may want to use % with LIKE
            # fields or (in my case) with date formatting strings for
            # STR_TO_DATE().
            # Oh, no, still breaks ("not all arguments converted during
            # string formatting");
            # http://stackoverflow.com/questions/9337134
            sql = _PERCENT_REGEX.sub("%%", sql)
            # ... replace all % with %% first
            sql = _QUERY_VALUE_REGEX.sub("%s", sql)
            # ... replace all ? with %s in the SQL
        return sql

    def fetch_object_from_db_by_pk(self, obj, table, fieldlist, pkvalue):
        """Fetches object from database table by PK value. Writes back to
        object. Returns True/False for success/failure."""
        if pkvalue is None:
            blank_object(obj, fieldlist)
            return False
        row = self.fetchone(
            get_sql_select_all_non_pk_fields_by_pk(table, fieldlist,
                                                   self.delims),
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
                                             self.delims),
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
            get_sql_insert(table, fieldlist, self.delims),
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
            get_sql_insert_without_first_field(table, fieldlist, self.delims),
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
            get_sql_update_by_first_field(table, fieldlist, self.delims),
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
            AND table_schema=DATABASE()
        """
        row = self.fetchone(sql, tablename)
        return True if row[0] >= 1 else False

    def column_exists(self, tablename, column):
        """Does the column exist?"""
        sql = """
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_name=?
            AND column_name=?
            AND table_schema=DATABASE()
        """
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
        if self.db_flavour != DatabaseSupporter.FLAVOUR_MYSQL:
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
        if self.db_flavour == DatabaseSupporter.FLAVOUR_SQLSERVER:
            return self.fetchall("SELECT * FROM information_schema.tables")
            # restricted to current database (in full:
            #   databasename.information_schema.tables)
            # http://stackoverflow.com/questions/6568098
        elif self.db_flavour == DatabaseSupporter.FLAVOUR_MYSQL:
            return self.fetchall("SELECT * FROM information_schema.tables "
                                 "WHERE table_schema=?", self.schema)
            # not restricted to current database, unless we do that manually
        elif self.db_flavour == DatabaseSupporter.FLAVOUR_ACCESS:
            # returns some not-very-helpful stuff too!
            return self.fetchall("""
                SELECT *
                FROM MSysObjects
                WHERE (((Left([Name],1))<>"~")
                        AND ((Left([Name],4))<>"MSys")
                        AND ((MSysObjects.Type) In (1,4,6)))
                ORDER BY MSysObjects.Name
            """)
        else:
            raise AssertionError("Unknown database flavour")
        # works in MySQL and SQL Server
        # SQL Server: TABLE_CATALOG, TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
        # ... those fields (and more) available in MySQL

    def get_all_table_names(self):
        """Returns all table names in the database."""
        if self.db_flavour == DatabaseSupporter.FLAVOUR_SQLSERVER:
            return self.fetchallfirstvalues("SELECT table_name "
                                            "FROM information_schema.tables")
        elif self.db_flavour == DatabaseSupporter.FLAVOUR_MYSQL:
            return self.fetchallfirstvalues(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema=?", self.schema)
            # or: "SHOW TABLES"
        elif self.db_flavour == DatabaseSupporter.FLAVOUR_ACCESS:
            return self.fetchallfirstvalues("""
                SELECT MSysObjects.Name AS table_name
                FROM MSysObjects
                WHERE (((Left([Name],1))<>"~")
                        AND ((Left([Name],4))<>"MSys")
                        AND ((MSysObjects.Type) In (1,4,6)))
                ORDER BY MSysObjects.Name
            """)
            # http://stackoverflow.com/questions/201282
        else:
            raise AssertionError("Unknown database flavour")

    def describe_table(self, table):
        """Returns details on a specific table."""
        if self.db_flavour == DatabaseSupporter.FLAVOUR_SQLSERVER:
            return self.fetchall(
                "SELECT * FROM information_schema.columns "
                "WHERE table_name=?", table)
        elif self.db_flavour == DatabaseSupporter.FLAVOUR_MYSQL:
            return self.fetchall(
                "SELECT * FROM information_schema.columns "
                "WHERE table_schema=? AND table_name=?", self.schema, table)
            # or: "SHOW TABLES"
        elif self.db_flavour == DatabaseSupporter.FLAVOUR_ACCESS:
            raise RuntimeError("Don't know how to describe table in Access")
        else:
            raise AssertionError("Unknown database flavour")

    def fetch_column_names(self, table):
        """Returns all column names for a table."""
        # May come back in Unicode
        if self.db_flavour == DatabaseSupporter.FLAVOUR_SQLSERVER:
            c = self.fetchallfirstvalues(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name=?", table)
        elif self.db_flavour == DatabaseSupporter.FLAVOUR_MYSQL:
            c = self.fetchallfirstvalues(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema=? AND table_name=?", self.schema, table)
            # or: "SHOW TABLES"
        elif self.db_flavour == DatabaseSupporter.FLAVOUR_ACCESS:
            # not possible in SQL:
            #   http://stackoverflow.com/questions/2221250
            # can do this:
            #   http://stackoverflow.com/questions/3343922/get-column-names
            # or can use pyodbc:
            self.ensure_db_open()
            cursor = self.db.cursor()
            sql = "SELECT TOP 1 * FROM " + self.delimit(table)
            debug_sql(sql)
            cursor.execute(sql)
            c = [x[0] for x in cursor.variables]
            # https://code.google.com/p/pyodbc/wiki/Cursor
        else:
            raise AssertionError("Unknown database flavour")
        return c

    def get_datatype(self, table, column):
        """Returns database SQL datatype for a column: e.g. varchar."""
        if (self.db_flavour == DatabaseSupporter.FLAVOUR_SQLSERVER
                or self.db_flavour == DatabaseSupporter.FLAVOUR_MYSQL):
            # ISO standard for INFORMATION_SCHEMA, I think.
            # SQL Server carries a warning but the warning may be incorrect:
            # https://msdn.microsoft.com/en-us/library/ms188348.aspx
            # http://stackoverflow.com/questions/917431
            # http://sqlblog.com/blogs/aaron_bertrand/archive/2011/11/03/the-case-against-information-schema-views.aspx  # noqa
            c = self.fetchvalue(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_schema=? AND table_name=? AND column_name=?",
                self.schema, table, column)
        elif self.db_flavour == DatabaseSupporter.FLAVOUR_ACCESS:
            raise AssertionError("Don't know how to get datatype in Access")
        else:
            raise AssertionError("Unknown database flavour")
        return c.upper()

    def get_column_type(self, table, column):
        """Returns database SQL datatype for a column, e.g. varchar(50)."""
        if (self.db_flavour == DatabaseSupporter.FLAVOUR_SQLSERVER
                or self.db_flavour == DatabaseSupporter.FLAVOUR_MYSQL):
            # ISO standard for INFORMATION_SCHEMA, I think.
            # SQL Server carries a warning but the warning may be incorrect:
            # https://msdn.microsoft.com/en-us/library/ms188348.aspx
            # http://stackoverflow.com/questions/917431
            # http://sqlblog.com/blogs/aaron_bertrand/archive/2011/11/03/the-case-against-information-schema-views.aspx  # noqa
            sql = """
                SELECT {}
                FROM information_schema.columns
                WHERE table_schema=? AND table_name=? AND column_name=?
            """.format(self.coltype_expr)
            c = self.fetchvalue(sql, self.schema, table, column)
        elif self.db_flavour == DatabaseSupporter.FLAVOUR_ACCESS:
            raise AssertionError("Don't know how to get datatype in Access")
        else:
            raise AssertionError("Unknown database flavour")
        return c.upper()

    def get_comment(self, table, column):
        """Returns database SQL datatype for a column."""
        if self.db_flavour == DatabaseSupporter.FLAVOUR_SQLSERVER:
            return None  # unable to fetch
        elif self.db_flavour == DatabaseSupporter.FLAVOUR_MYSQL:
            c = self.fetchvalue(
                "SELECT column_comment FROM information_schema.columns "
                "WHERE table_schema=? AND table_name=? AND column_name=?",
                self.schema, table, column)
        elif self.db_flavour == DatabaseSupporter.FLAVOUR_ACCESS:
            return None  # unable to fetch
        else:
            raise AssertionError("Unknown database flavour")
        return c

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
            AND table_schema=database()
            AND constraint_name='PRIMARY'
        """
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

    def get_mysql_variable(self, varname):
        """Returns a MySQL system variable."""
        if self.db_flavour != DatabaseSupporter.FLAVOUR_MYSQL:
            return None
        sql = "SELECT @@{varname}".format(varname=varname)
        # http://dev.mysql.com/doc/refman/5.5/en/using-system-variables.html
        return self.fetchvalue(sql)

    def mysql_using_file_per_table(self):
        value = self.get_mysql_variable("innodb_file_per_table")
        return True if value == 1 else False

    def mysql_using_innodb_barracuda(self):
        value = self.get_mysql_variable("innodb_file_format")
        return True if value == "Barracuda" else False

    def mysql_table_using_barracuda(self, tablename):
        if (not self.mysql_using_file_per_table()
                or not self.mysql_using_innodb_barracuda()):
            return False
        sql = """
            SELECT engine, row_format
            FROM information_schema.tables
            WHERE table_name = ?
            AND table_schema=database()
        """
        args = [tablename]
        row = self.fetchone(sql, *args)
        if not row:
            return False
        engine = row[0]
        row_format = row[1]
        return engine == "InnoDB" and row_format in ["Compressed", "Dynamic"]
        # http://dev.mysql.com/doc/refman/5.6/en/innodb-file-format-identifying.html  # noqa

    def mysql_convert_table_to_barracuda(self, tablename, compressed=False):
        row_format = "COMPRESSED" if compressed else "DYNAMIC"
        sql = """
            ALTER TABLE {tablename}
            ENGINE=InnoDB
            ROW_FORMAT={row_format}
        """.format(
            tablename=tablename,
            row_format=row_format,
        )
        logger.info("Converting table {} to Barracuda (row_format={})".format(
            tablename,
            row_format
        ))
        self.db_exec(sql)
        # http://dev.mysql.com/doc/refman/5.5/en/innodb-compression-usage.html
        # http://www.percona.com/blog/2011/04/07/innodb-row-size-limitation/

    def mysql_using_innodb_strict_mode(self):
        value = self.get_mysql_variable("innodb_strict_mode")
        return True if value == 1 else False

    def mysql_get_max_allowed_packet(self):
        return self.get_mysql_variable("max_allowed_packet")

    def get_schema(self):
        if self.db_flavour == DatabaseSupporter.FLAVOUR_MYSQL:
            return self.fetchvalue("SELECT DATABASE()")
        else:  # certainly for SQL server...
            return self.fetchvalue("SELECT SCHEMA_NAME()")
