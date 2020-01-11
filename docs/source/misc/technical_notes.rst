.. crate_anon/docs/source/misc/technical_notes.rst

..  Copyright (C) 2015-2020 Rudolf Cardinal (rudolf@pobox.com).
    .
    This file is part of CRATE.
    .
    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    .
    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.
    .
    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.


Technical notes
===============

.. contents::
   :local:


Resolved bugs elsewhere, previously affecting CRATE
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- When mounted other than at /, using FORCE_SCRIPT_NAME, the "View site" link
  of Django admin sites points to / rather than the approriate site root.
  This is fixed in Django 1.10 (not yet released 2015-11-23, but out by
  2017-02-09).

    https://github.com/stephenmcd/mezzanine/issues/389
    https://docs.djangoproject.com/en/dev/releases/1.10/


Cross-platform hosting
~~~~~~~~~~~~~~~~~~~~~~

For Ubuntu, CRATE is packaged as a Debian .DEB file and will install itself,
though will not configure the web front end (intrinsically a separate
configuration task).

If you have to run under Windows, then one option is a VirtualBox
(https://www.virtualbox.org/).

In the conversion from Ubuntu to Windows:

**Python code, i.e. CRATE itself**

Cross-platform

**Database connections**

All configurable, and Windows connections available for all. MySQL supported
under Windows.

**Text extraction tools**

The Linux tools used are unrtf (.RTF), pdftotext (.PDF), antiword (.DOC),
strings (anything). They are generally very fast. CRATE calls them by name.

- unrtf is available for Windows (license: GPL)
  (https://www.gnu.org/software/unrtf/;
  http://gnuwin32.sourceforge.net/packages/unrtf.htm).

- pdftotext is available for Windows as part of Xpdf (license: GPL)
  (http://www.foolabs.com/xpdf/).

- antiword (http://www.winfield.demon.nl/) can be compiled for Windows and is
  available as a binary
  (http://www-stud.rbi.informatik.uni-frankfurt.de/~markus/antiword/).

- strings has an equivalent for Windows
  (https://technet.microsoft.com/en-us/sysinternals/bb897439.aspx).

*Users on Windows should install these tools so that they’re visible to CRATE
via the PATH.*

**Web framework (Gunicorn, with e.g. Apache as a front end)**

Gunicorn is UNIX-only, although happily it installs without complaint on
Windows, so we don’t need to exclude it from the dependencies.

Alternatives include: (1) CherryPy. This is pure Python. It supports SSL and
serves static files. Let’s use it. (2) uWSGI: written in C and requires Cygwin;
probably overly complex. (3) Waitress
(https://pylons.readthedocs.org/projects/waitress/en/latest/). This doesn’t
support SSL but does support reverse proxying.

CherryPy works nicely; I’ve set up a launch script and default configuration.
(But see also: https://baxeico.wordpress.com/2013/10/13/django-on-windows/;
http://tools.cherrypy.org/wiki/WindowsService.) **This is also suitable for
Linux use.** It uses a thread pool by default for its HTTP server. It runs as a
django manage.py command, so use it as **crate_django_manage runcpserver**. You
can append ``--help`` to get other options that you can use with the
CRATE_CHERRYPY_ARGS environment variable. There are also a few settings in
crateweb/config/settings.py that configure CherryPy, and quite a lot more in
crateweb/core/management/commands/runcpserver.py.

**Celery**

Celery is in Python, so is cross-platform. It can be run as a daemon/service
under Windows, using the Windows built-in Task Scheduler
(http://docs.celeryproject.org/en/latest/tutorials/daemonizing.html;
https://www.calazan.com/windows-tip-run-applications-in-the-background-using-task-scheduler/;
you use the virtualenv’s ‘crate/bin/celeryd’ as the process). Services can also
be installed from Python. [Use ‘pip install pypiwin32’. (It’s a pip-only
version of pywin32, I think.) That makes available the libraries pythoncom
(unnecessary?), win32serviceutil, win32service, win32event, servicemanager.
Then see http://stackoverflow.com/questions/32404 for how to install/run Python
code as a service.]

It did need some fixing, which was hard: key parameters to the “celery worker”
command were “--concurrency=4” and “--pool=solo”. See comments in
crateweb/consent/celery.py.

**RabbitMQ**

RabbitMQ supports Windows directly and runs as a service
(https://www.rabbitmq.com/install-windows.html).

**supervisord**

supervisord is used under Linux to control (a) celery and (b) gunicorn. It does
not run under Windows
(http://supervisord.org/introduction.html#platform-requirements ; though see
http://stackoverflow.com/questions/7629813 as you can run supervisord under
Cygwin). Under Windows, we need to run (a) celery and (b) CherryPy. For Celery,
this function is replaced by the Windows Task Scheduler. For CherryPy, there is
also a daemon script. It can be run from the command line with ``python -c
“from cherrypy.daemon import run; run()”``. (An aside: note also Monit; not
free, but potentially good, in the UNIX environment; https://mmonit.com/.) See
also django-windows-tools
(http://django-windows-tools.readthedocs.org/en/latest/index.html; this seems
to be Python 2 only (as of 2016-05-11).).

The practical answer was to write a small Windows service that runs other
processes.

**MySQL standalone auditor**

Ditched; MySQL now supports adequate auditing itself. In mysql.cnf:

- Set ‘log_output = TABLE’ (to use the table mysql.general_log), ‘log_output =
  FILE’ (to use the file specified by the ‘general_log_file’ variable), or
  ‘log_output = FILE,TABLE’ for both.

- Set ‘general_log = 1’.

Restart MySQL (https://dev.mysql.com/doc/refman/5.7/en/log-destinations.html).
The TABLE form of the log neatly includes username and queries. The
mysql.general_log.thread_id field is used as the ‘id’ column of the disk log;
you can in principle work out user information from the Connect entries that
occur prior to queries, but the TABLE form provides a much more convenient way
of working out user/query mappings. It will hit performance, though.

**Library dependencies**

DOCX extraction preferred to use python-docx, which uses lxml, which has C
dependencies and is therefore fiddly to install on arbitrary Windows systems
(i.e. is not guaranteed to be installed by pip). One option would be for the
user to install lxml from e.g. a binary repository
(http://www.lfd.uci.edu/~gohlke/pythonlibs/#lxml), but instead I rewrote
rnc_extract_text.py (in cardinal_pythonlib) to use a pure Python approach that
also handles tables.


Converting to SQLAlchemy
~~~~~~~~~~~~~~~~~~~~~~~~

See ``test_sqla_reflection.py``

- Cataloguing databases: easy.

- Storing a datatype: a SQLAlchemy column type (coltype = col[‘type’])
  String(length=10); str(coltype) looks like ‘VARCHAR(10)’, using a
  dialect-free version, and repr(coltype) looks like ‘String(length=10)’.
  Parsing the latter involves something akin to eval (maybe using ast). Parsing
  the former... see sqlalchemy/dialects/mysql/base.py, particularly
  _parse_column() and ischema_names. For dialect-specific things, you find
  ‘LONGBLOB’ (str) and ‘LONGBLOB()’ (repr). Dealt with by using the
  str(coltype) method and adding a reverse lookup via SQLAlchemy dialect.

- SQL field comments: there is no standard cross-database way
  (https://bitbucket.org/zzzeek/sqlalchemy/issues/1546/feature-request-commenting-db-objects,
  including my compilation of methods for different backends). The web
  interface could read comments from the DD, but that introduces an otherwise
  unnecessary dependence on a user-maintained file. Better to read just from
  the database. **When SQLAlchemy supports comments, set up CRATE’s Django code
  to read them from all relevant backends (currently it is MySQL-specific).**

- Iteration by rows: if memory constraints become a real problem, consider
  yield_per(); note that some DBAPIs fetch all rows anyway even if you use
  cursor.fetchone(). [See e.g. MySQL/cursors.py; compare
  CursorStoreResultMixIn.fetchone() and CursorUseResultMixIn.fetchone(). The
  default, cursors.Cursor (used by Connection()), uses CursorStoreResultMixIn,
  which keeps the resultset on the client side. See also e.g.
  http://stackoverflow.com/questions/18193825/python-how-to-use-a-generator-to-avoid-sql-memory-issue;
  http://stackoverflow.com/questions/2067529/mysqldb-pulls-whole-query-result-in-one-chunk-always-even-if-i-just-do-a-fetchon;
  https://mail.python.org/pipermail/python-list/2006-June/370129.html;
  http://stackoverflow.com/questions/1145905/sqlalchemy-scan-huge-tables-using-orm]

- INSERT... ON DUPLICATE KEY UPDATE: tricky
  [http://stackoverflow.com/questions/6611563/sqlalchemy-on-duplicate-key-update;
  https://gist.github.com/timtadh/7811458;
  https://www.reddit.com/r/Python/comments/p5grh/sqlalchemy_whats_the_idiomatic_way_of_writing/;
  https://groups.google.com/forum/#!topic/sqlalchemy/RJQHYOpmMCo;
  https://bitbucket.org/zzzeek/sqlalchemy/issues/3113/warning-for-custom-insert-mysql;
  http://stackoverflow.com/questions/1382469/sqlalchemy-easy-way-to-insert-or-update
  https://bitbucket.org/zzzeek/sqlalchemy/issues/960]. Used a custom directive
  (with compile-specific-to-MySQL option) to append SQL.

- Character set: tricky. Getting this wrong leads to MySQL ‘1336, Incorrect
  string value’ errors or Python ‘UnicodeEncodeError’ errors on insert. MySQL
  has character set/collation settings for: client, server, database, table,
  column... [To view:
  http://makandracards.com/makandra/2529-show-and-change-mysql-default-character-set.]
  In SQLAlchemy, specify the character set for the connection and,
  particularly, for creating the destination table. [See
  http://docs.sqlalchemy.org/en/latest/dialects/mysql.html . Specify options
  like mysql_charset either in the Table() definition (SQLAlchemy Core) or the
  __table_args__ dictionary (SQLAlchemy ORM):
  http://stackoverflow.com/questions/8971960.] Database URLs should include
  ‘?charset=utf8’ or similar, and the rest is handled internally.

- CREATE FULLTEXT INDEX: MySQL-specific
  [http://stackoverflow.com/questions/14971619/proper-use-of-mysql-full-text-search-with-sqlalchemy].
  PostgreSQL supports full-text indexing but uses different methods
  [http://www.postgresql.org/docs/9.1/static/textsearch-tables.html]. Handled
  with dialect-specific code.

- **MySQL settings: configure using ``/etc/mysql/my.cnf`` or equivalent.** To
  walk through: the InnoDB storage engine is probably best, with transactions
  and savepoints (see “SHOW ENGINES”); it’s the default. As of MySQL 5.6, it
  also supports FULLTEXT indexes. It can be asked to store tables using a file
  per table; this is true by default for versions ≤5.5.6 and false by default
  for ≥5.5.7
  [https://dev.mysql.com/doc/refman/5.7/en/server-system-variables.html].
  InnoDB can use the Antelope or Barracuda file format
  [https://dev.mysql.com/doc/refman/5.7/en/innodb-file-format.html]; the
  default became Barracuda for MySQL ≥5.7.7; Barracuda is fancier. It supports
  options like DYNAMIC row formats. As of MySQL 5.7.9, one can specify the
  default row format
  [https://dev.mysql.com/doc/refman/5.7/en/innodb-row-format-specification.html].
  You can dynamically change a table’s file and row format
  [http://stackoverflow.com/questions/8112517/alter-row-format-to-dynamic].

  .. code-block:: none

    # Example lines from /etc/mysql/my.cnf:
    character_set_server = utf8
    collation_server = utf8_unicode_ci
    default_storage_engine = InnoDB
    innodb_file_per_table = 1
    innodb_file_format = Barracuda
    innodb_default_row_format = DYNAMIC

    # To alter row format dynamically later
    # (e.g. from Antelope/COMPACT to Barracuda/DYNAMIC):
    mysql> ALTER TABLE databasename.tablename ROW_FORMAT=DYNAMIC;
    # To confirm:
    mysql> SELECT * FROM information_schema.innodb_sys_tables WHERE name = ‘databasename/tablename’;

    # To create a database with a specified charset/collation:
    mysql> CREATE DATABASE somedb DEFAULT CHARACTER SET utf8 DEFAULT COLLATE utf8_unicode_ci;

    # To alter a table’s character set/collation:
    # (http://stackoverflow.com/questions/742205)
    # (http://stackoverflow.com/questions/766809)
    mysql> ALTER TABLE sometable CONVERT TO CHARACTER SET utf8 COLLATE utf8_unicode_ci;


Installing Python 3.4 on Ubuntu 16.04
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

See
http://devmartin.com/blog/2016/04/creating-a-virtual-environment-with-python3.4-on-ubuntu-16.04-xenial-xerus/:

.. code-block:: bash

    sudo apt install build-essential checkinstall libreadline-gplv2-dev \
        libncursesw5-dev libssl-dev libsqlite3-dev tk-dev libgdbm-dev libc6-dev \
        libbz2-dev openssl

    mkdir -p $HOME/opt
    cd $HOME/opt
    curl -O https://www.python.org/ftp/python/3.4.4/Python-3.4.4.tgz
    tar xzvf Python-3.4.4.tgz
    cd Python-3.4.4
    ./configure --enable-shared --prefix=/usr/local LDFLAGS="-Wl,--rpath=/usr/local/lib"
    sudo make altinstall

    sudo python3.4 -m pip install --upgrade pip
    sudo python3.4 -m pip install virtualenv


Transaction count always >0 for SQL Server, prohibiting CREATE FULLTEXT INDEX
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- SET IMPLICIT_TRANSACTIONS ON|OFF
  https://msdn.microsoft.com/en-gb/library/ms187807.aspx
  didn't help

- SQLSetConnectAttr()
  https://docs.microsoft.com/en-us/sql/odbc/reference/syntax/sqlsetconnectattr-function

- ODBC commit mode
  https://docs.microsoft.com/en-us/sql/odbc/reference/develop-app/commit-mode

- Other
  http://dba.stackexchange.com/questions/43254/is-it-a-bad-practice-to-always-create-a-transaction

- SQLAlchemy and the Python DBAPI transaction rule even without "BEGIN"
  https://news.ycombinator.com/item?id=4269241


Celery: test_email_rdbm_task() missing 1 required positional argument: 'self'
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Change decorators from:

    @shared_task
    @task(ignore_result=True)

to

    @shared_task(ignore_result=True)


SQL comments
~~~~~~~~~~~~

See https://bitbucket.org/zzzeek/sqlalchemy/issues/1546/feature-request-commenting-db-objects

.. code-block:: none

    For column comments, I think the various DDLs are as follows:

    Oracle
    ======

    1. Adding during table creation:

        not possible?

    2. Adding comments later:

        COMMENT ON TABLE sometable IS 'This is a table comment';
        COMMENT ON COLUMN sometable.somecol IS 'This is a column comment';

    3. Retrieving:

        SELECT table_name, comments FROM all_tab_comments WHERE table_name = 'sometable';
        SELECT column_name, comments FROM all_col_comments WHERE table_name = 'sometable';

    4. References

        https://docs.oracle.com/cd/B19306_01/server.102/b14200/statements_4009.htm
        https://docs.oracle.com/cd/B28359_01/server.111/b28320/statviews_1036.htm
        https://docs.oracle.com/cd/B19306_01/server.102/b14237/statviews_2095.htm
        Note also alternative views (DBA_*, USER_* rather than ALL_*).

    MySQL
    =====

    1. Adding during table creation:

        CREATE TABLE sometable (somecol INTEGER COMMENT 'this is a column comment') COMMENT 'this is a table comment';

    2. Adding comments later:

        ALTER TABLE sometable COMMENT 'this is a table comment too';
        ALTER TABLE sometable CHANGE somecol somecol INTEGER COMMENT 'this is a column comment too';

    3. Retrieving:

        SELECT table_schema, table_name, table_comment FROM information_schema.tables WHERE table_schema = DATABASE() AND table_name = 'sometable';
        SELECT table_schema, column_name, column_comment FROM information_schema.columns WHERE table_schema = DATABASE() AND table_name = 'sometable';

    4. References

        http://dev.mysql.com/doc/refman/5.7/en/create-table.html
        http://dev.mysql.com/doc/refman/5.7/en/tables-table.html
        http://dev.mysql.com/doc/refman/5.7/en/columns-table.html

    PostgreSQL
    ==========

    1. Adding during table creation:

        not possible?

    2. Adding comments later:

        COMMENT ON TABLE sometable IS 'This is a table comment';
        COMMENT ON COLUMN sometable.somecol IS 'This is a column comment';

    3. Retrieving:

        (Uses internal OIDs to reference table number.)

        SELECT t.table_schema, t.table_name, pgd.description
        FROM pg_catalog.pg_statio_all_tables AS st
        INNER JOIN pg_catalog.pg_description pgd ON (pgd.objoid = st.relid)
        INNER JOIN information_schema.tables t ON (
            pgd.objsubid = 0 AND
            t.table_schema = st.schemaname AND
            t.table_name = st.relname)
        WHERE t.table_name = 'sometable';

        SELECT c.table_schema, c.table_name, c.column_name, pgd.description
        FROM pg_catalog.pg_statio_all_tables AS st
        INNER JOIN pg_catalog.pg_description pgd ON (pgd.objoid = st.relid)
        INNER JOIN information_schema.columns c ON (
            pgd.objsubid = c.ordinal_position AND
            c.table_schema = st.schemaname AND
            c.table_name = st.relname)
        WHERE c.table_name = 'sometable';

    4. References

        http://www.postgresql.org/docs/9.1/static/sql-createtable.html
        http://www.postgresql.org/docs/9.2/static/sql-comment.html
        http://stackoverflow.com/questions/343138/retrieving-comments-from-a-postgresql-db
        http://www.postgresql.org/docs/8.3/static/catalog-pg-description.html
        http://www.postgresql.org/docs/9.2/static/monitoring-stats.html#PG-STATIO-ALL-TABLES-VIEW

    MSSQL (SQL Server)
    ==================

    - Unsupported in SQL. Possible using "extended properties". A bit nasty, but...

    1. Adding during table creation:

        not possible?

    2. Adding comments later:

        EXEC sys.sp_addextendedproperty
            @name=N'Description',
            @value=N'This is a table comment',
            @level0type=N'SCHEMA',
            @level0name=N'dbo',
            @level1type=N'TABLE',
            @level1name=N'sometable'
        GO
        EXEC sys.sp_addextendedproperty
            @name=N'Description',
            @value=N'This is a column comment',
            @level0type=N'SCHEMA',
            @level0name=N'dbo',
            @level1type=N'TABLE',
            @level1name=N'sometable',
            @level2type=N'COLUMN',
            @level2name=N'somecol'
        GO

    3. Retrieving:

        SELECT
            s.name AS schema_name,
            t.name AS table_name,
            CONVERT(VARCHAR(1000), x.value) AS table_comment -- is of type SQL_VARIANT
        FROM sys.tables t
        LEFT JOIN sys.extended_properties x ON t.object_id = x.major_id
        LEFT JOIN sys.schemas s on t.schema_id = s.schema_id
        WHERE x.minor_id = 0 AND t.name = 'sometable';

        SELECT
            s.name AS schema_name,
            t.name AS table_name,
            c.name AS column_name,
            CONVERT(VARCHAR(1000), x.value) AS column_comment
        FROM sys.columns c
        LEFT JOIN sys.extended_properties x ON (
            c.object_id = x.major_id AND
            c.column_id = x.minor_id
        )
        LEFT JOIN sys.tables t ON c.object_id = t.object_id
        LEFT JOIN sys.schemas s on t.schema_id = s.schema_id
        WHERE t.name = 'sometable';

    4. References

        http://stackoverflow.com/questions/4586842/sql-comments-on-create-table-on-sql-server-2008
        https://msdn.microsoft.com/en-us/library/ms180047.aspx
        https://mrsql.wordpress.com/tag/sp_addextendedproperty/

    SQLite
    ======

    - Unsupported.

        http://www.sqlite.org/lang.html


webnotes.txt
~~~~~~~~~~~~

.. code-block:: none

    ===============================================================================
    Early thoughts preceding Django, starting 19 Mar 2015
    ===============================================================================

        - output roughly sketched out
        - WSGI framework drafted

        - needs safe SQL creation framework
            - easy to make something too fiddly: http://www.ajaxquerybuilder.com/
        - needs session, security/users, main menu, audit
        - user accessing the destination database must be READ ONLY here

    This kind of queries that might benefit from some autogeneration:

        SELECT
            master.rid, master.dob, ...
            secondtable.field1, secondtable.field2, ...
            thirdtable.field1, thirdtable.field2, ...
        FROM
            master
            INNER JOIN secondtable ON (secondtable.rid = master.rid)
            INNER JOIN thirdtable ON (thirdtable.rid = master.rid)
        WHERE
            MATCH(secondtable.field1) AGAINST ('schizophrenia')
            OR MATCH(thirdtable.field1) AGAINST ('schizophrenia')

    However, it's not clear anything really improves on writing raw SQL; most
    assisted query generation frameworks are quite crippled functionally. Simple
    SQL also has the advantage of producing a clear tabular structure, without
    nesting.

    ===============================================================================
    SITE-SPECIFIC CONFIGURATION FILES FOR DJANGO
    ===============================================================================

    Several methods; e.g.
        https://code.djangoproject.com/wiki/SplitSettings#ini-stylefilefordeployment
        https://code.djangoproject.com/wiki/SplitSettings#Multiplesettingfilesimportingfromeachother
    The question is which works best with WSGI, where we have public (repository)
    code and secret (site-specific) settings, and in principle might want to run
    more than one instance of the application on a single server.

    Using Apache's SetEnv and then reading the WSGI environment (as I currently do
    for CamCOPS, Sep 2015) can be flaky with Django, so should be avoided:
        http://stackoverflow.com/questions/19754834/access-apache-setenv-variable-from-django-wsgi-py-file
    Note that it appears possible, and lots of people advocate it, but Graham D.'s
    point is cautionary, and he wrote mod_wsgi.

    Therefore, follow Graham Dumpleton's suggestion, e.g. as follows:

    - hard-code the filename 'crate_local_settings.py', so that the Django
      settings.py does 'from crate_local_settings import *'
    - define settings for multiple apps by creating e.g.
        /etc/crate_instance_1/crate_local_settings.py
        /etc/crate_instance_2/crate_local_settings.py
    - set the WSGI "python-path" (more or less equivalent to the normal environment
      variable PYTHONPATH) to include the relevant /etc/[something] directory

    ===============================================================================
    DJANGO PROJECT
    ===============================================================================

    # -----------------------------------------------------------------------------
    # SYSTEM-WIDE OPTIONAL EXTRAS
    # -----------------------------------------------------------------------------

    sudo apt-get install sqliteman

    # -----------------------------------------------------------------------------
    # VIRTUALENV; PYTHON PREREQUISITES
    # -----------------------------------------------------------------------------

    # (a) System-wide installation of pip and virtualenv

    sudo apt-get install python3-pip  # pip for Python 3
    sudo pip3 install virtualenv  # Python 3 version of virtualenv

    # (b) Creation of clean Python 3 virtual environment, with its own pip

    export VENV=~/tmp/crate_virtualenv
    mkdir -p $VENV
    virtualenv --python=/usr/bin/python3.4 $VENV
    export PIP=$VENV/bin/pip
    export PYTHON=$VENV/bin/python

    # (c) Installation of packages into virtual environment

    $PIP install django  # Django
    export DJANGO_ADMIN=$VENV/bin/django-admin.py
    $PIP install mysqlclient  # Python 3 replacement for MySQLdb
    $PIP install django-sslserver  # SSL development server
    $PIP install django-picklefield  # PickleField

    # -----------------------------------------------------------------------------
    # DJANGO PROJECT CREATION
    # -----------------------------------------------------------------------------

    # Check versions
    $PYTHON -c "import django; print(django.get_version())"
    $DJANGO_ADMIN version
    # ... is currently 1.8.4

    $DJANGO_ADMIN startproject crateweb

    # Edit manage.py, changing
    #       #!/usr/bin/env python
    # to
    #       #!/usr/bin/env python
    # ... or Python 2 and an old version of Django may be used.

    # -----------------------------------------------------------------------------
    # DJANGO PROJECT MANAGEMENT
    # -----------------------------------------------------------------------------

    export CRATE_BASE=~/Documents/code/crate
    export CRATE_DJANGO_ROOT=$CRATE_BASE/webfrontend/crateweb
    export CRATE_MANAGE="$PYTHON $CRATE_DJANGO_ROOT/manage.py"
    . $CRATE_BASE/webfrontend/SET_PATHS.sh
    $CRATE_MANAGE  # shouldn't produce an error

    -------------------------------------------------------------------------------
    RUN TEST SERVER
    -------------------------------------------------------------------------------

    # For HTTP:
    $CRATE_MANAGE runserver
    # ... now browse to http://127.0.0.1:8000/

    # For HTTPS (having installed/configured django-sslserver)
    $CRATE_MANAGE runsslserver
    # ... now browse to https://127.0.0.1:8000/

    -------------------------------------------------------------------------------
    GRANT READ-ONLY ACCESS TO MYSQL RESEARCH DATABASE
    -------------------------------------------------------------------------------

    mysql -u root -p
    mysql> GRANT SELECT ON anonymous_output.* TO 'researcher'@'localhost' IDENTIFIED BY 'password';

    -------------------------------------------------------------------------------
    CREATE/RECREATE TABLES
    -------------------------------------------------------------------------------

    # If models have changed:
    $CRATE_MANAGE makemigrations [appname] --name MIGRATION_NAME

    # To see what it'll do, e.g.
    $CRATE_MANAGE sqlmigrate research 0001  # ... appname, migration_number

    # Then:
    $CRATE_MANAGE migrate

    -------------------------------------------------------------------------------
    CREATE APP
    -------------------------------------------------------------------------------

    cd $CRATE_DJANGO_ROOT
    $CRATE_MANAGE startapp research
    # now add it to INSTALLED_APPS in settings.py

    -------------------------------------------------------------------------------
    EXPLORE APP FROM COMMAND LINE
    -------------------------------------------------------------------------------

    $CRATE_MANAGE shell
    # See https://docs.djangoproject.com/en/1.8/intro/tutorial01/

    -------------------------------------------------------------------------------
    CREATE SUPERUSER
    -------------------------------------------------------------------------------

    $CRATE_MANAGE createsuperuser

    # Now run the demo server and go to http://127.0.0.1:8000/admin/

    -------------------------------------------------------------------------------
    TUTORIALS
    -------------------------------------------------------------------------------

    - https://docs.djangoproject.com/en/1.8/intro/tutorial01/
    - https://www.youtube.com/watch?v=oT1A1KKf0SI&list=PLxxA5z-8B2xk4szCgFmgonNcCboyNneMD&index=1

    -------------------------------------------------------------------------------
    USER PROFILES
    -------------------------------------------------------------------------------

    # http://stackoverflow.com/questions/19433630/how-to-use-user-as-foreign-key-in-django-1-5
    # https://docs.djangoproject.com/en/dev/topics/auth/customizing/#referencing-the-user-model
    # https://www.youtube.com/watch?v=qLRxkStiaUg&list=PLxxA5z-8B2xk4szCgFmgonNcCboyNneMD&index=22

    cd $CRATE_DJANGO_ROOT
    $CRATE_MANAGE startapp userprofile
    # edit settings.py (a) INSTALLED_APPS; (b) AUTH_PROFILE_MODULE = 'userprofile.UserProfile'

    -------------------------------------------------------------------------------
    GENERAL DJANGO ADVICE
    -------------------------------------------------------------------------------
    Cheat sheet: http://www.mercurytide.co.uk/news/article/django-15-cheat-sheet/

    Collected tips: http://stackoverflow.com/questions/550632/favorite-django-tips-features
    ... including:

        $CRATE_MANAGE graph_models -a -g -o crate_model_diagram.png

        $CRATE_MANAGE runserver_plus
        assert False somewhere; then use the Werkzeug console to explore

    ===============================================================================
    CONSENT-MODE DATABASE
    ===============================================================================
    - General principle to avoid storing BLOBs in databases, to keep the database
      small, and to allow static file serving. With Django, for private static
      files, that may need something like X-Sendfile:
        http://zacharyvoase.com/2009/09/08/sendfile/
        http://django-private-files.readthedocs.org/en/0.1.2/serverconf.html
        ... Apache with mod_xsendfile
        http://stackoverflow.com/questions/1156246/having-django-serve-downloadable-files
    - However, we do want to concatenate PDFs to make packages for clinicians.
      Though not necessarily very often.
    - Outbound e-mails can be stored as text (e.g. HTML).
    - Letters could be stored as PDFs (e.g. files) or as the HTML used to generate
      the PDF (smaller; reproducible exactly unless e.g. the header changes).



    If you drop a table, or want to drop a table:
        http://stackoverflow.com/questions/5328053/how-to-restore-dropped-table-with-django-south

    ===============================================================================
    CSS MODEL
    ===============================================================================
    - Static or template-based?
      Since we want consistency across web/email/PDF (inc. the web aspects of
      clinicians responding to e-mails), and since we have to embed CSS for email,
      we'll embed the lot and use templates.

    - CSS selector tutorial:
      http://css.maxdesign.com.au/selectutorial/selectors_class.htm

    ===============================================================================
    GENERAL DJANGO NOTES FOR URL/'GET' INFORMATION-PASSING:
    ===============================================================================
    1. URL path
        - create in code with reverse()
        - encapsulate the output of reverse() in request.build_absolute_uri()
          to get an absolute URI with site domain name, etc.
        - details are read back by the urlconf regexes (in urls.py) and passed
          to views as parameters
        - validation is "manual" e.g. using
            study = get_object_or_404(Study, pk=study_id)
            if not custom_is_valid_function(extraparam):
                raise Http404('error message')
        - ... or could validate manually with a form, e.g.
            form = MyForm(request.GET, extraparam)
          using the style at
            http://stackoverflow.com/questions/18769607/django-form-with-customer-parameter-and-validation-not-getting-clean-function  # noqa

    2. Query parameters
        - can encode using urllib, e.g.
            def url_with_querystring(path, **kwargs):
                return path + '?' + urllib.urlencode(kwargs)
        - ?BETTER is to encode using Django's QueryDict and its urlencode()
          method:
            q = QueryDict(mutable=True)
            q['key'] = value
            querybits = q.urlencode()
        - read them like this:
            request.GET.get('key', 'defaultvalue')
        - or could read/validate them with a form and its validators:
            form = MyForm(request.GET):
            # ... might use a ChoiceField or other validators
            if form.is_valid():
                ...
            else:
                ...

    3. Combining them
        "{path}?{querystring}".format(
            path=request.build_absolute_uri(reverse(...)),
            querystring=querydict.urlencode()
        )
        ... etc ...

    4. Which is best?
        - path parameters:
            best for fixed resource lookup
            elegant handling in Django; DRY
        - query parameters:
            best for display modification
            order can vary
            they can be optional
            form-based validation is simpler
        - sometimes either works

    5. But if we're building a Django object...
        - consider a ModelForm
        - slide
            35 - basic pattern
            86 - unit testing
            99 - dynamically adding fields
          of http://www.slideshare.net/pydanny/advanced-django-forms-usage
          BUT SEE
            http://www.pydanny.com/the-easy-form-views-pattern-controversy.html
          ... use this:
            request.POST if request.method == 'POST' else None
          not this:
            request.POST or None

    http://stackoverflow.com/questions/2345708/how-can-i-get-the-full-absolute-url-with-domain-in-django  # noqa
    http://stackoverflow.com/questions/150505/capturing-url-parameters-in-request-get  # noqa
    http://stackoverflow.com/questions/2778247/how-do-i-construct-a-django-reverse-url-using-query-args  # noqa
    http://whippleit.blogspot.co.uk/2010/10/pretty-urls-vs-query-strings.html
    http://stackoverflow.com/questions/3821663/querystring-in-rest-resource-url
    http://stackoverflow.com/questions/9399147/django-form-validation-with-get

    ===============================================================================
    Back-end processing: Celery
    ===============================================================================
    - High-end optimum broker for Celery is perhaps RabbitMQ.
      Can persist messages to disk (or say you don't care).
      But moderately complex.
    - Simpler is Celery with the Django database backend as the broker.
      And we have a very low volume of traffic.

    http://docs.celeryproject.org/en/latest/getting-started/brokers/django.html#broker-django

    - pip install celery
    - in Django settings.py
        BROKER_URL = 'django://'
        CELERY_ACCEPT_CONTENT =  ['json']
        CELERY_RESULT_SERIALIZER = 'json'
        CELERY_TASK_SERIALIZER = 'json'
        INSTALLED_APPS should include 'kombu.transport.django'
    - manage.py migrate
        ... will make tables djkombu_message, djkombu_queue
    - follow http://docs.celeryproject.org/en/latest/django/first-steps-with-django.html

    - to run a debugging worker:
        cd .../crateweb
        celery -A consent worker --loglevel=debug

    - NOTE difficulty with PYTHONPATH
        ... if PYTHONPATH includes .../crate and .../crate/crateweb,
        Django moans when you start about duplicate filesystem locations.
        ... if it only includes .../crate and you start Celery from a random
        location with "crateweb.consent" as the module name, it can't find
        other Django bits like "userprofile".
        ... so the above seems simplest.
        ... and celery also says you have to:
            http://docs.celeryproject.org/en/latest/getting-started/next-steps.html#next-steps

    - Anyway, success now.

    - However, database is going to grow (old messages not pruned).
      Generally true? I'm unclear; https://github.com/celery/kombu/issues/276

      Let's try RabbitMQ.

        sudo apt-get install rabbitmq-server
        # ... will autostart service

      Easy. Also, much snappier.

      Will start with localhost-only access via the "guest" account:
        https://www.rabbitmq.com/access-control.html

      Status:
        sudo rabbitmqctl status
        sudo rabbitmqctl report


    ===============================================================================
    mod_wsgi-express, etc.
    ===============================================================================

    # http://blog.dscpl.com.au/2015/04/introducing-modwsgi-express.html
    # http://blog.dscpl.com.au/2015/04/using-modwsgi-express-with-django.html
    # http://blog.dscpl.com.au/2015/04/integrating-modwsgi-express-as-django.html
    # http://blog.dscpl.com.au/2015/05/using-modwsgi-express-as-development.html
    # https://pypi.python.org/pypi/mod_wsgi
    # https://gist.github.com/GrahamDumpleton/b79d336569054882679e

    # https://opensourcemissions.wordpress.com/2010/03/12/finally-a-working-django-non-root-url-with-mod_wsgi/
    # https://groups.google.com/forum/#!topic/django-users/xFdZnKq26H0
    # https://code.djangoproject.com/ticket/8906

    # http://stackoverflow.com/questions/30566836/how-to-autostart-apachectl-script-that-mod-wsgi-express-made-for-django

    ===============================================================================
    Celery (etc.) as daemon, and overall stack
    ===============================================================================

    Most convenient to use supervisor/django-supervisor?
        http://stackoverflow.com/questions/14275821/how-to-run-celery-as-a-daemon-in-production
    Supervisor won't install via pip for Python 3. It's Python 2 only at present:
        http://supervisord.org
    However, it is an Ubuntu package (supervisor).
    Then we can use django-supervisor.
        ... or maybe not; the installation is difficult.

    The "raw" Celery methods are:
        http://docs.celeryproject.org/en/latest/tutorials/daemonizing.html#daemonizing
        http://docs.celeryproject.org/en/latest/getting-started/next-steps.html#next-steps

    Possibly just follow this, which is clear:
        http://www.apreche.net/complete-single-server-django-stack-tutorial/

    supervisord / PYTHONPATH
        http://stackoverflow.com/questions/7930259/supervisor-running-a-python-script-pythonpath-issue

    ===============================================================================
    Overall stack
    ===============================================================================

    - We want very simple installation.
    - Happy to mandate Ubuntu/Debian for now. (CentOS is a pain, for a start.)
    - Several components of the stack auto-run (Apache; RabbitMQ).
    - No pressing reason not to run "proper" Apache.
      Alternative include "standalone" Apache via mod_wsgi-express, which would
      need daemonizing; other similar Python-based servers like nginx/gunicorn
    - If Apache is used, then that keeps the Django bit up and running.
    - Only other bit that needs daemonizing is Celery; we can daemonize that with
      supervisord (which can be installed via Ubuntu).
      Once configured, this works beautifully.

      For monitoring, can use:
        sudo supervisorctl

    - So installation process would be:

        sudo gdebi --non-interactive PACKAGE
        ... ensure Ubuntu requirements
            ... makes RabbitMQ happen automatically
            ... Apache configuration is the user's business (but we offer instructions)
        ... install code to /usr/share/crate
        ... create virtualenv in /usr/share/crate/virtualenv
            using sub-script install_virtualenv.sh
            parameters:
                (1) virtualenv: /usr/share/crate/virtualenv
                (2) secrets: /etc/crate
            ... ensure Python package requirements
            ... create specimen /etc/crate/crate_local_settings.py
            ... create customized instructions.txt for Apache, supervisord
        ... create some scripts in /usr/share/crate
            - launch demo Django server
            - launch debugging Celery backend
        ... restart supervisor
        ... restart Apache, if running

    - The other possibility might be to run a separate web server and proxy it from Apache, e.g.
        http://stackoverflow.com/questions/6418016/gunicorn-via-mod-proxy-is-redirecting-outside-of-the-projects-scope-despite-pr
        http://serverfault.com/questions/429404/help-me-understand-how-to-use-proxypass
        http://blog.endpoint.com/2013/04/making-ssl-work-with-django-behind.html
      It adds another thing to fall over, but it would allow Apache to run without
      restarting even when Python apps need to be restarted (a positive...).
      Plus it would allow non-root running more simply, since port 80 is restricted.
      And it minimizes the amount of Apache configuration required from the end user.
      And it makes "development versus production" simpler.
      It also has the consequence that we don't have mod_wsgi tied to a specific
      Python version, which is a massive pain.
    - OK. Let's give it a go with gunicorn.

        http://michal.karzynski.pl/blog/2013/06/09/django-nginx-gunicorn-virtualenv-supervisor/

    Unix domain sockets

    - Working
    - However, Django debug toolbar stops working

        https://github.com/django-debug-toolbar/django-debug-toolbar/issues/690
        https://github.com/benoitc/gunicorn/issues/797

        ... see fix to INTERNAL_IPS, which is a bit bizarre, in the specimen
        config file.

    SSL proxy

        https://bharatikunal.wordpress.com/2010/12/01/howto-reverseproxy-to-https-in-apache/





    -------------------------------------------------------------------------------
    NOT THE SIMPLEST: To use Apache with mod_wsgi
    -------------------------------------------------------------------------------
    # ... we'll skip this.

    (a) Add Ubuntu prerequisites

        sudo apt-get install apache2 libapache2-mod-wsgi-py3 libapache2-mod-xsendfile

    (b) Configure Apache for CRATE.
        Use a section like this in the Apache config file:

    <VirtualHost *:80>
        # ...

        # =========================================================================
        # CRATE
        # =========================================================================

        # Define a process group (using the specimen name crate_pg)
        # Must use threads=1 (code may not be thread-safe).
        # Example here with 5 processes.
        WSGIDaemonProcess crate_pg processes=5 threads=1 python-path=$SITE_PACKAGES:$DEST_DJANGO_ROOT:$SECRETS_DIR

        # Point a particular URL to a particular WSGI script (using the specimen path /crate)
        WSGIScriptAlias /crate $DEST_DJANGO_ROOT/config/wsgi.py process-group=crate_pg

        # Redirect requests for static files, and admin static files.
        # MIND THE ORDER - more specific before less specific.
        Alias /static/admin/ $SITE_PACKAGES/django/contrib/admin/static/admin/
        # Alias /static/debug_toolbar/ $SITE_PACKAGES/debug_toolbar/static/debug_toolbar/
        Alias /static/ $DEST_DJANGO_ROOT/static/

        # Make our set of processes use a specific process group
        <Location /crate>
            WSGIProcessGroup crate_pg
        </Location>

        # Allow access to the WSGI script
        <Directory $DEST_DJANGO_ROOT/config>
            <Files "wsgi.py">
                Require all granted
            </Files>
        </Directory>

        # Allow access to the static files
        <Directory $DEST_DJANGO_ROOT/static>
            Require all granted
        </Directory>

        # Allow access to the admin static files
        <Directory $SITE_PACKAGES/django/contrib/admin/static/admin>
            Require all granted
        </Directory>

        # Allow access to the debug toolbar static files
        # <Directory $SITE_PACKAGES/debug_toolbar/static/debug_toolbar>
        #     Require all granted
        # </Directory>

    </VirtualHost>

    (c) Additionally, install mod_xsendfile, e.g. (on Ubuntu):

            sudo apt-get install libapache2-mod-xsendfile

        ... which will implicitly run "a2enmod xsendfile" to enable it. Then add to
        the Apache config file in an appropriate place:

            # Turn on XSendFile
            <IfModule mod_xsendfile.c>
                XSendFile on
                XSendFilePath /MY/SECRET/CRATE/FILE/ZONE
                # ... as configured in your secret crate_local_settings.py
            </IfModule>

    - If you get problems, check the log, typically /var/log/apache2/error.log
    - If it's a permissions problem, check the www-data user can see the file:
        sudo -u www-data cat FILE
        # ... using an absolute path
        groups USER
    - If Chrome fails to load GIFs and says "pending" in the Network developer
      view, restart Chrome. (Probably only a "caching of failure" during
      development!)

    -------------------------------------------------------------------------------
    Standalone Apache with mod_wsgi-express
    -------------------------------------------------------------------------------

        pip install mod_wsgi-httpd  # a bit slow; don't worry
        pip install mod_wsgi

        mod_wsgi-express start-server config.wsgi \\
            --application-type module \\
            --log-to-terminal \\
            --port 80 \\
            --processes 5 \\
            --python-path $SECRETS_DIR \\
            --threads 1 \\
            --url-alias /static $DEST_DJANGO_ROOT/static \\
            --working-directory $DEST_DJANGO_ROOT

    - This changes to the working directory and uses config/wsgi.py
    - Add --reload-on-changes for debugging.
    - Port 80 will require root privilege.


    ===============================================================================
    Versioning
    ===============================================================================

    versioning (think for CamCOPS and for consent mode)

    https://www.djangopackages.com/grids/g/versioning/
        Python 3 support and production/stable -- narrows to
            Django Reversion
            django-simple-history
        ... of which Django Reversion looks best, as it can "version"
            relationships.

    ===============================================================================
    Making the debug toolbar appear in different settings
    ===============================================================================

    # If you want to use the Django debug toolbar while proxying (e.g. between
    # gunicorn and Apache) through a Unix domain socket, this will wipe out
    # REMOTE_ADDR, which is checked in debug_toolbar.middleware.show_toolbar .
    # Bizarrely, while at first glance it looks like b'', it's actually "b''"!
    # So you would need this:
    #
    # INTERNAL_IPS = (
    #     '127.0.0.1',  # for port proxy
    #     "b''",  # for Unix domain socket proxy
    # )
    #
    # An alternative is to set DEBUG_TOOLBAR_CONFIG as per
    # http://stackoverflow.com/questions/28226940/django-debug-toolbar-wont-display-from-production-server  # noqa
    # Like this:

    def always_show_toolbar(request):
        return True # Always show toolbar, for example purposes only.

    DEBUG_TOOLBAR_CONFIG = {
        'SHOW_TOOLBAR_CALLBACK': always_show_toolbar,
    }

    ===============================================================================
    SQL Server
    ===============================================================================

    http://stackoverflow.com/questions/13726670/using-jython-with-django

    - Microsoft SQL Server drivers:
      OLD: ODBC: https://msdn.microsoft.com/en-us/library/hh568451(v=sql.110).aspx
      NEW: JDBC: https://www.microsoft.com/en-gb/download/details.aspx?id=11774
      OPEN SOURCE: jTDS: http://jtds.sourceforge.net/

    - Django-Jython supports zxJDBC, which supports SQL Server via jTDS:
      https://pythonhosted.org/django-jython/database-backends.html
      # 'ENGINE': 'doj.db.backends.mssql',

    - Jython is Python in a JVM. It's not clear this is very easy to set up with Apache.
      https://www.mail-archive.com/pythonireland@googlegroups.com/msg00945.html

    - Django (Python) support Microsoft SQL Server via django-mssql, but that is Windows only, and doesn't support Linux.
      http://django-mssql.readthedocs.org/en/latest/
      http://stackoverflow.com/questions/22604732/linux-django-sqlserver

    - Another Python route, looking dated:
      Django / django-sqlserver / python-tds
      https://github.com/denisenkom/django-sqlserver  # BECOMING OUT OF DATE? SAYS IT CAN'T HANDLE DATETIME COLUMNS PROPERLY.
      # django-sqlserver was formerly called django-pytds
      # OLD # https://bitbucket.org/denisenkom/django-pytds
      https://pypi.python.org/pypi/python-tds

      http://python-tds.readthedocs.org/en/latest/

    - Another Python route, looking more recent:
      Django / django-pymssql / pymssql / [?FreeTDS]
      https://github.com/aaugustin/django-pymssql
      http://www.pymssql.org/en/latest/

    - Another Python route, but not Python 3:
      Django / django-pyodbc
      https://github.com/lionheart/django-pyodbc/
      http://stackoverflow.com/questions/24026608/sql-server-2008-2012-backend-module-for-django-on-linux
      http://stackoverflow.com/questions/2791766/django-pyodbc-sql-server-freetds-server-connection-problems-on-linux

    TO READ:
    http://blog.nguyenvq.com/blog/tag/jtds/


    LIKELY BEST? AVOID JAVA. And jaydebeapi is a bit flaky, and doesn't integrate with Django as yet.

    Django / django-pyodbc-azure / pyodbc / UnixODBC / FreeTDS
      http://stefanoapostolico.com/2015/04/20/django_mssql_osx.html
      https://github.com/michiya/django-pyodbc-azure
      https://github.com/mkleehammer/pyodbc
      http://www.unixodbc.org/
      http://www.freetds.org/

      +/- https://code.google.com/p/django-pyodbc/wiki/FreeTDS
      +/- http://stackoverflow.com/questions/24906016/exception-value-08001-08001-unixodbcfreetdssql-serverunable-to-con
      and http://stackoverflow.com/questions/20283199/django-pyodbc-azure-databaseerror-42000-42000-error-converting-data-type
      ... = how to set TDS protocol version with Django

    ... NB not old UnixODBC versions: https://github.com/michiya/django-pyodbc-azure/issues/4


    SUMMARY: From Django onwards through the stack:

        django-jython
            zxJDBC
                jTDS
        django-mssql
            quasi-endorsed by Django but FAIL: needs Windows
        django-sqlserver
            POSSIBLE? django-sqlserver==1.7 -- BUGGY; tries to import "django.db.backends.util" (should be "utils") with Django 1.9rc1
        django-pyodbc-azure


    -------------------------------------------------------------------------------
    django-pyodbc-azure -> unixODBC -> FreeTDS -> SQL Server
    -------------------------------------------------------------------------------
    - https://github.com/michiya/django-pyodbc-azure/blob/azure/README.rst

    1. On the Windows end (in this case, 192.168.1.13):

        (*) SQL Server Configuration Manager (from Windows Start menu)
            > SQL Server 2005 Network Configuration
            > Protocols for MSSQLSERVER
            > TCP/IP
            > Enabled (and double-click "TCP/IP" for more settings)

        (*) Create a database in Microsoft SQL Server Management Studio Express.
            e.g. crate_sqlserver_db

        (*) Create a user:
            Microsoft SQL Server Management Studio Express
            > [root server, e.g. WOMBATVMXP]
            > Security
            > Logins
            > (right-click: Add Login)
            >   Login name = crate_user
                SQL Server authentication
                    password = something
                set sensible defaults like not requiring password change

        (*) Allow the user access
            Microsoft SQL Server Management Studio Express
            > New Query [button]
                USE crate_sqlserver_db;
                -- NOT SURE -- EXEC sp_grantdbaccess crate_user;
                -- DOESN'T DO MUCH -- GRANT ALL TO crate_user;
                EXEC sp_addrolemember 'db_owner', 'crate_user';

        (*) Allow proper logins via TCP/IP:
            Microsoft SQL Server Management Studio Express
            > [root server, e.g. WOMBATVMXP]
            > Security
            > Logins
            > (right-click: Properties)
            > Security
                Server authentication = SQL Server and Windows Authentication mode

        (*) Services > stop/restart "SQL Server (MSSQLSERVER)"

        (*) netstat -a
            ... to verify port 1433 is open (or "ms-sql-s")

        (*) from another machine, check the port is open:
            telnet 192.168.1.13 1433

        OK. Back to the Linux end.

    2. Get latest FreeTDS (see also http://www.freetds.org/)

        $ sudo apt-get install freetds-bin tdsodbc

        ... note that tdsodbc is critical for /usr/lib/x86_64-linux-gnu/odbc/libtdsodbc.so

    3. Test the FreeTDS connection

        $ TDSVER=8.0 tsql -H 192.168.1.13 -p 1433 -U crate_user -P something

        Failure levels:
            "No route to host"
            "Connection refused"
                -- duff port or port not open
            "Login failed for user ''. The user is not associated with a trusted
            SQL Server connection." / "Adaptive Server connection failed"
                -- better... need to allow TCP/IP access
            "Cannot open user default database. Using master database instead."
                -- much better; need the grant command as above
        At the point of success:
            locale is "en_GB.UTF-8"
            locale charset is "UTF-8"
            using default charset "UTF-8"
            1>

        Then:
            1> SELECT * FROM notes
            2> GO
        Also:
            > VERSION
            ... to show TDS protocol version
        Which version? Choose from
            http://www.freetds.org/userguide/choosingtdsprotocol.htm
        ... but if you get "unrecognized msgno", go up.

    4. Get unixODBC and nice tools

        $ sudo apt-get install unixodbc-bin

    5. Configure ODBC

        - ignore /etc/freetds/freetds.conf
            ... though there are some optional [global] settings there

        - in /etc/odbcinst.ini

            [FreeTDS]
            Description = FreeTDS (SQL Server protocol driver for Unix)
            Driver = /usr/lib/x86_64-linux-gnu/odbc/libtdsodbc.so
            Setup = /usr/lib/x86_64-linux-gnu/odbc/libtdsS.so

        - in /etc/odbc.ini, or ~/.odbc.ini

            [crate_sqlserver_odbc]
            description = "CRATE test SQL Server 2005 database on Wombat VMXP"
            driver = FreeTDS
            TDS_Version = 8.0
            ; which TDS version setting is read, of the several possibilities? See http://stackoverflow.com/questions/13066716
            server = 192.168.1.13
            port = 1433

        $ odbcinst -j  # print config information
        $ odbcinst -q -d  # query drivers
        $ odbcinst -q -s  # query data sources
        $ ODBCManageDataSourcesQ4  # visual confirmation of everything

    6. Configure Django

        - in settings.py:

            'research': {
                'ENGINE': 'sql_server.pyodbc',
                'NAME': 'crate_sqlserver_db',
                'USER': 'crate_user',
                'PASSWORD': 'something',
                'OPTIONS': {
                    'dsn': 'crate_sqlserver_odbc',
                }
            },

        - should then work.


notes_on_database_schemas.txt
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: none

    ===============================================================================
    Microsoft SQL Server
    ===============================================================================

    In Microsoft SQL Server (MSSQL), at least from 2005+, there are 4 "layers":

        SELECT database_name.schema_name.table_name.column_name
        FROM database_name.schema_name.table_name;

    The default schema is 'dbo'.
    (In old versions of MSSQL, up to SQL Server 2000, "owners" stood in the stead
    of schemas; the default owner was 'dbo', the database owner.)

    - https://technet.microsoft.com/en-us/library/dd283095(v=sql.100).aspx
    - https://blog.sqlauthority.com/2009/09/07/sql-server-importance-of-database-schemas-in-sql-server/

    Default schemas include:
        dbo
        guest
        sys
        INFORMATION_SCHEMA

    ... so there's one of those for EACH database.

    - https://msdn.microsoft.com/en-us/library/bb669061(v=vs.110).aspx

    Can a connection talk to >1 database? Yes.
    A connection has a database context.
    This is set automatically to the default database for the login, and can be
    set or changed explicitly using
        USE mydatabase;

    - https://msdn.microsoft.com/en-us/library/ms188366.aspx

    SELECTed things can actually be 5-layered; the "table"-level one can be any
    of:

        server_name.[database_name].[schema_name].object_name
        | database_name.[schema_name].object_name
        | schema_name.object_name
        | object_name

    - https://msdn.microsoft.com/en-us/library/ms177563.aspx

    To describe a database, use its INFORMATION_SCHEMA.

    ===============================================================================
    PostgreSQL
    ===============================================================================

    Similar to SQL Server in that the levels are database/schema/table/column.

    However, Postgres doesn't allow you to query across databases, so "schema"
    becomes more important.

    - http://stackoverflow.com/questions/1152405/postgresql-is-it-better-using-multiple-databases-with-1-schema-each-or-1-datab
    - http://stackoverflow.com/questions/46324/possible-to-perform-cross-database-queries-with-postgres
    - http://stackoverflow.com/questions/4678862/joining-results-from-two-separate-databases
    - http://wiki.postgresql.org/wiki/FAQ#How_do_I_perform_queries_using_multiple_databases.3F

    The default PostgreSQL schema is 'public'.

    - https://www.postgresql.org/docs/9.3/static/ddl-schemas.html


    ===============================================================================
    ANSI SQL
    ===============================================================================

    - http://www.contrib.andrew.cmu.edu/~shadow/sql/sql1992.txt
      21.2   INFORMATION_SCHEMA
      21.3.4 INFORMATION_SCHEMA.SCHEMATA

    ===============================================================================
    MySQL
    ===============================================================================

    SCHEMA and DATABASE are synonymous.

    - http://stackoverflow.com/questions/11618277/difference-between-schema-database-in-mysql
    - https://dev.mysql.com/doc/refman/5.7/en/glossary.html#glos_schema

    The SELECT statement can go up to:

        SELECT database_name.table_name.column_name
        FROM database_name.table_name;

    As before, the USE statement allows you to specify a particular default
    database, but doesn't stop you querying from others.

    - https://dev.mysql.com/doc/refman/5.7/en/use.html

    INFORMATION_SCHEMA is at the same level as databases.
    ... and the TABLE_CATALOG column is meaningless.

    See als:
    - http://dba.stackexchange.com/questions/3774/what-is-the-point-of-the-table-catalog-column-in-information-schema-tables

    ===============================================================================
    CRATE web interface
    ===============================================================================

    - We will have a single connection to the research database(s).
    - That is django.conf.settings.DATABASES['research'].
    - We will want to scan, potentially, several schemas.
    - We don't want a distinction between the "browse structure" views and the
      query builder.
    - We'll need to know the dialect, to know whether we need to use d.s.t.c
      or a three-level structure.
    - For MySQL, should we call the top level "database" or "schema"?
    - Well, the concept of schemas allows enforced foreign keys between two
      different schemas in the same database (in SQL Server).
      - http://stackoverflow.com/questions/2095268/foreign-key-reference-to-table-in-another-schema
    - SQL Server doesn't allow referential constraints across databases, except
      via manual triggers
      - http://stackoverflow.com/questions/4452132/add-foreign-key-relationship-between-two-databases
    - What about MySQL?
      MySQL allows FKs between two different databases, I think:
      - http://stackoverflow.com/questions/3905013/mysql-innodb-foreign-key-between-different-databases
      ... but are they properly enforced? I think so.
    - That would make a MySQL {database/schema} more like an SQL Server schema,
      rather than an SQL Server database.
    - On the other hand, from the outside in, "database" probably makes more sense
      to users.

    - Therefore, we'll say that RESEARCH_DB_INFO has keys:
        database  -- None for MySQL/PostgreSQL
        schemas
        ...

    - The query builder may or may not offer the additional "database" level.


old notes.txt
~~~~~~~~~~~~~

.. code-block:: none

    ===============================================================================
    Considered but not implemented
    ===============================================================================

    - NOT YET SUITABLE FOR PYTHON 3: the following dependencies do not work:
        docx (in rnc_extract_text.py)

    - Ability to run an incremental update from a partial data set.
      Since this data set might not include all identifiers, the software would
      have to store the anonymisation information (e.g. a repr()-style
      representation of the regexes) and work on the assumption that identifiers
      can be added but not subtracted. However, this is still problematic: if
      a scrubber has changed, the rows it's scrubbed should be re-scrubbed, but
      that requires the original data source (unless one were just to re-scrub
      the destination from its previous version, which would give potentially
      inconsistent results). So not implemented.

    ===============================================================================
    Performance
    ===============================================================================

        For a test source database mostly consisting of text (see makedata.py),
        on a 8-core x 3.5-Ghz machine, including (non-full-text) indexing:

    from __future__ import division
    test_size_mb = 1887
    time_s = 84
    speed_mb_per_s = test_size_mb / time_s
    cpft_size_gb = 84
    estimated_cpft_time_min = cpft_size_gb * 1024 * time_s / (test_size_mb * 60)

        Initial speed tests (Mb/s):
            7.9 Mb/s with 1 process, 8 threads
            8.6 Mb/s with 1 process, 16 threads
            18.0 Mb/s with 8 patient processes + 1 for non-patient tables.
            18.0 Mb/s with 16 patient processes + 1 for non-patient tables.
        Most recent:
            22.5 Mb/s with 8 patient processes + 1 for non-patient tables.
        See launch_multiprocess.sh.
        Guesstimate for Feb 2015 CPFT RiO database (about 84 Gb): 1 h 04 min.
        Note that the full-text indexing is very slow, and would be extra.

    Incremental updates:

        Where a full run takes 126s, an incremental run with nothing to do takes
        11s.

    MySQL full-text indexing:

        http://dev.mysql.com/doc/refman/5.0/en/fulltext-search.html

        Once indexed, change this conventional SQL:
            SELECT something
            WHERE field1 LIKE '%word%' OR field2 LIKE '%word%';

        to one of these:
            SELECT something
            WHERE MATCH(field1, field2) AGAINST ('word');

            SELECT something
            WHERE MATCH(field1, field2) AGAINST ('word');

        ... and there are some more subtle options.

        Improves speed from e.g.:
            SELECT brcid FROM notes WHERE note LIKE '%Citibank%';
            ... 10.66 s
        to:
            SELECT brcid FROM idxnotes WHERE MATCH(note) AGAINST('citibank');
            ...  0.49 s

        NOTE: requires MySQL 5.6 to use FULLTEXT indexes with InnoDB tables (as
        opposed to MyISAM tables, which don't support transactions).

        On Ubuntu 14.04, default MySQL is 5.5, so use:
            sudo apt-get install mysql-server-5.6 mysql-server-core-5.6 \
                mysql-client-5.6 mysql-client-core-5.6
        ... but it does break dependences on (e.g.) mysql-server, so not yet done.


    ===============================================================================
    Profiling
    ===============================================================================

    python -m cProfile -s cumtime tools/launch_cherrypy_server.py > ~/tmp/profile.txt

    ===============================================================================
    Encryption/hashing
    ===============================================================================

    - A normal PID might be an 'M' number, RiO number, or some other such system-
      specific ID number. A master PID might be an NHS number.
    - There must not be collisions in the PID -> RID mapping; we need to keep our
      patients separate.
    - The transformation must involve something unknown outside this (open-
      source) code. If we used encrypted = hashlib.sha256(plaintext).hexdigest(),
      then anybody could run that function over a bunch of integers from 0 to
      9,999,999,999 and they'd have a simple way of reversing the algorithm for
      all PIDs up to that value.
    - So the options are
      (a) hash with a secret salt;
      (b) hash with a random salt;
      (c) encrypt with a secret key.
    - We can't use (b), because we want consistency in our PID -> RID mappings
      when we we re-run the anonymisation.
    - We do need to reverse one or both transformations, for consent-to-contact
      methods (and potentially clinicaly use), but only a superuser/research
      database manager should be able to do this.
    - Thus, if we hash with a secret salt, we'd have to store the PID/RID mapping
      somewhere safe.
    - If we encrypt, we can skip that storage and just keep the secret key.
    - We also want a consistent output length.
    - With encryption, if the key is leaked, everything encrypted with it is
      available to those with access to the encrypted data. With a secret
      constant salt, the same is true (given a dictionary attack, since the stuff
      being encrypted is just a bunch of integers).
    - This is *not* the same problem as password storage, where we don't care if
      two users have the same passwords. Here, we need to distinguish patients
      by the RID. It may be acceptable to use a per-patient salt, and then store
      the PID/RID mapping, but for an incremental update one would have to rely
      on being able to retrieve the old PID/RID mapping, or the mapping would
      change. So: per-patient salt wouldn't be safe for incremental updates.
    - We're left with (a) and (c). Both are in principle vulnerable to loss of
      the secret information; but that will always be true of a reversible
      system.
    - One benefit of encryption, is that we could use public-key encryption and
      this program would then never need to know the decryption key (whereas with
      a hash, it needs to know the salt, so loss of this program's config file
      will be of concern). The decryption key can be stored somewhere especially
      secret. However, RSA (for example) produces long output, e.g. 1024 bytes.
    - Remaining options then include:
      (a) SHA256 hash with secret salt;
      (c) AES256 encryption with secret key.
      I don't think either has a strong advantage over the other, so since we do
      have to be able to reverse the system, we might as well use AES256. But
      then... AES should really have a random initialization vector (IV) used
      (typically stored with the encrypted output, which is fine), but that means
      that a second encryption of the same thing (e.g. for a second anonymisation
      run) gives a different output.
    - If we want to use hex encoding and end up with an encrypted thing of length
      32 bytes, then the actual pre-hex value needs to be 16 bytes, etc.
    - Anyway, pragmatic weakening of security for practical purposes: let's use
      an MD5 hash with a secret salt.

    ===============================================================================
    NOT YET IMPLEMENTED
    ===============================================================================

    - Incremental updates following small data dictionary changes, e.g. field
      addition. Currently, these require a full re-run.

    ===============================================================================
    Z. NOTES
    ===============================================================================

    -------------------------------------------------------------------------------
    Q.  Segmentation fault (core dumped)... ?
    -------------------------------------------------------------------------------
    A.  Short answer: use the Microsoft JDBC driver instead of the Microsoft ODBC
        driver for Linux, which is buggy.

        Long answer, i.e. working this out:

        Examine the core with gdb anonymise.py ~/core
        ... then it tells you which program generated the core
        ... then gdb PROGRAM ~/core
        ... but actually the likely reason is being out of RAM
        ... monitor memory use with
                htop
                top (press M)
                watch free -m
                    http://www.linuxatemyram.com/
        ... tried: reduce the innodb_thread_concurrency variable as above, and
            restart MySQL (under Ubuntu/Debian, with: sudo service mysql restart).
            - didn't fix it
        ... for 32M max_allowed_packet, use 320M (not 512M) for the logfile
            - did significantly reduce memory usage, but still crashed, and not
              while processing a large record
            - longest BLOB in this data set is
        So, systematic method:
        (1) What's the biggest packet needed? Estimate with:
                SELECT MAX(LEN(giantbinaryfield)) FROM relevanttable;
            ... in our case (CRS/CDL test): 39,294,299 = 37.47 MiB.
            So with a bit of margin, let's use
                max_allowed_packet = 40M
                innodb_log_file_size = 400M
        (2) Then set max number of rows and bytes, e.g. to 1000 rows and 80 MiB.
        OK, actually relates to a single specific record -- found using MySQL
        log with
                SET GLOBAL general_log = 'ON';
                SHOW VARIABLES LIKE 'general_log_file';
        ... but actually not relating to insertion at all, but to retrieval
        ... nrows=90060 then crash in gen_rows at the point of cursor.fetchone()
        ... This?
            http://stackoverflow.com/questions/11657958
            https://code.google.com/p/pyodbc/issues/detail?id=346
            https://msdn.microsoft.com/en-us/library/hh568448.aspx
            https://code.google.com/p/pyodbc/issues/detail?id=188
        ... changing rnc_db to use pypyodbc rather than pyodbc:
                sudo pip install pypyodbc
                import pypyodbc as pyodbc
            ... crashed at the same point (segfault).
            ... so back to pyodbc
        ... git clone https://github.com/mkleehammer/pyodbc
            ... getdata.cpp, as one bughunt above suggested, already has that fix
        ... sudo pip install pyodbc --upgrade  # from 3.0.6 to 3.0.7
            ... no change
        ... try the query using Perl and DBI::ODBC -- also crashes.
            So probably a bug in the SQL Server Native Client 11.0 for Linux.
        ... can't use FreeTDS because the SQL Server won't let us login (another
            Microsoft bug).
        ... removing the VARCHAR(MAX) fields from the data dictionary makes it happy again.
        ... random: http://www.saltycrane.com/blog/2011/09/notes-sqlalchemy-w-pyodbc-freetds-ubuntu/

        [Full details in private log.]

        Switched to the JDBC driver.
        Problem went away.


    -------------------------------------------------------------------------------
    Q.  "Killed."
    -------------------------------------------------------------------------------
    A.  Out of memory.
        Suggest
        - Reduce MySQL memory footprint; see notes below.
        Testing on a rather small machine (0.5 Gb RAM, 1 Gb swap).
        Inspect what was running:

            # cat /var/log/syslog

        Remove memory-hogging things:

            # apt-get purge modemmanager
            - change the report_crashes parameter to false in the /etc/default/whoopsie file.
            # service whoopsie stop
            # apt-get remove unity unity-asset-pool unity-control-center unity-control-center-signon unity-gtk-module-common unity-lens* unity-services unity-settings-daemon unity-webapps* unity-voice-service
            ... NOT YET REMOVED: network-manager

        Inspect it:

            # pmap -x <process_id>

        Leaks?
        - http://www.lshift.net/blog/2008/11/14/tracing-python-memory-leaks/

            $ python -m pdb ./anonymise.py
            (Pdb) run crs_cdl_anon.ini -v
            (Pdb) c

        Use openDBcopy to copy the database: http://opendbcopy.sourceforge.net/

            Prerequisites
                export JAVA_HOME=/usr/lib/jvm/default-java
                cd ~/openDBcopy/bin
                ./start.sh &

            Plugin chain:

                - Migrate database schema (DDL)

                    0.  Configuration

                    1.  Database connections
                        SOURCE
                            Driver name = Microsoft MSSQL Server JDBC Driver
                            Driver class = com.microsoft.sqlserver.jdbc.SQLServerDriver
                            URL = jdbc:sqlserver://XXX:1433;databaseName=XXX
                            User name = XXX
                            Password = XXX
                        DESTINATION
                            Driver name = MySQL Driver
                            Driver class = com.mysql.jdbc.Driver
                            URL = jdbc:mysql://localhost:3306/DATABASENAME
                            User name = XXX
                            Password = XXX
                        TEST BOTH.

                    2.  Source model
                            Catalog = [DATABASE NAME]
                            Schema = dbo
                            Table pattern = %
                        CAPTURE SOURCE MODEL.

                    3.  Tables to migrate
                            = all by default

                    4.  Columns to migrate
                            = all by default

                - Copy data from a source into a destination database

            ... NOT WORKING.

        - http://stackoverflow.com/questions/27068092/jpype-java-initialize-with-or-get-remaining-heap-space

        - http://stackoverflow.com/questions/1178736/mysql-maximum-memory-usage
        - SHOW ENGINE INNODB STATUS

        USEFUL THINGS:
        - see estimate_mysql_memory_usage.sh
        - changed innodb_buffer_pool_size from 128M to 16M
            ... big improvement; mysqld %MEM (in top) went from ~30% to ~10%
        - RTF processing takes lots of memory, using Python/pyth
            ... significant improvement after switching to Linux/unrtf
            ... similarly, using Linux/pdftotext rather than Python/pdfminer

        AFTERWARDS:
        - Show table size and number of rows in MySQL (note: APPROXIMATE):

            SELECT table_name AS 'Table',
                ROUND(((data_length + index_length) / 1024 / 1024), 2) AS "Size in MiB",
                table_rows AS 'Approx. # rows'
            FROM information_schema.TABLES
            WHERE table_schema = DATABASE()
            ORDER BY table_name;

        TEMPORARY HOLDUP: not enough disk space (~9.2 Gb on CPFT test machine):

            +---------------------+-------------+------------+
            | Table               | Size in MiB | table_rows |
            +---------------------+-------------+------------+
            | address             |       63.61 |     431262 |
            | alias               |        5.52 |      58468 |
            | assessment          |      256.63 |       9725 |
            | careplan            |      191.64 |      16801 |
            | careplangoal        |       98.64 |     187922 |
            | cdlinternalreferral |        2.52 |       4679 |
            | cdlpatient          |        2.52 |      14014 |
            | cgas                |        1.52 |       2571 |
            | dependant           |        0.13 |       1001 |
            | diagnosis           |        8.52 |      76361 |
            | documentlibrary     |     3795.00 |     474874 |
            | employment_status   |        0.02 |          0 |
            | exclude             |        0.02 |          0 |
            | honos               |        0.02 |          0 |
            | honos_65            |        0.02 |          0 |
            | honos_ca            |        0.02 |          0 |
            | honos_ld            |        0.02 |          0 |
            | honos_secure        |        0.02 |          0 |
            | living_arrangements |        0.02 |          0 |
            | mpi                 |        0.02 |          0 |
            | personal_carers     |        0.02 |          0 |
            | practicegp          |        0.02 |          0 |
            | procedures          |        0.02 |          0 |
            | referral            |        0.02 |          0 |
            | schedules           |        0.02 |          0 |
            | team_episodes       |        0.02 |          0 |
            | telephone           |        0.02 |          0 |
            | ward_stays          |        0.02 |          0 |
            +---------------------+-------------+------------+
            28 rows in set (0.42 sec)

            ... THEN OUT OF DISK SPACE:

            _mysql_exceptions.OperationalError: (1114, "The table 'documentlibrary' is full")

            Since we want to test with all patients being processed but only a
            subset of documents (to make sure all documents are anonymised), let's
            add the debug_row_limit and debug_limited_tables options in the config.

        Source (NB exact number of rows):

        2015-04-25 20:44:05.676:INFO:anonymise:crs_cdl_network.address: 394511 records
        2015-04-25 20:44:05.701:INFO:anonymise:crs_cdl_network.alias: 58606 records
        2015-04-25 20:44:05.722:INFO:anonymise:crs_cdl_network.assessment: 10874 records
        2015-04-25 20:44:05.762:INFO:anonymise:crs_cdl_network.careplan: 17601 records
        2015-04-25 20:44:05.820:INFO:anonymise:crs_cdl_network.careplangoal: 203553 records
        2015-04-25 20:44:05.851:INFO:anonymise:crs_cdl_network.cdlinternalreferral: 5098 records
        2015-04-25 20:44:05.869:INFO:anonymise:crs_cdl_network.cdlpatient: 13021 records
        2015-04-25 20:44:05.878:INFO:anonymise:crs_cdl_network.cgas: 2523 records
        2015-04-25 20:44:05.892:INFO:anonymise:crs_cdl_network.dependant: 953 records
        2015-04-25 20:44:05.922:INFO:anonymise:crs_cdl_network.diagnosis: 74119 records
        2015-04-25 20:44:06.075:INFO:anonymise:crs_cdl_network.documentlibrary: 691360 records
        2015-04-25 20:44:06.081:INFO:anonymise:crs_cdl_network.employment_status: 11874 records
        2015-04-25 20:44:06.093:INFO:anonymise:crs_cdl_network.honos: 16530 records
        2015-04-25 20:44:06.098:INFO:anonymise:crs_cdl_network.honos_65: 11948 records
        2015-04-25 20:44:06.112:INFO:anonymise:crs_cdl_network.honos_ca: 48 records
        2015-04-25 20:44:06.140:INFO:anonymise:crs_cdl_network.honos_ld: 866 records
        2015-04-25 20:44:06.151:INFO:anonymise:crs_cdl_network.honos_secure: 308 records
        2015-04-25 20:44:06.164:INFO:anonymise:crs_cdl_network.living_arrangements: 676 records
        2015-04-25 20:44:06.200:INFO:anonymise:crs_cdl_network.mpi: 159506 records
        2015-04-25 20:44:06.216:INFO:anonymise:crs_cdl_network.personal_carers: 37788 records
        2015-04-25 20:44:06.284:INFO:anonymise:crs_cdl_network.practicegp: 350050 records
        2015-04-25 20:44:06.292:INFO:anonymise:crs_cdl_network.procedures: 2688 records
        2015-04-25 20:44:06.376:INFO:anonymise:crs_cdl_network.referral: 353714 records
        2015-04-25 20:44:06.983:INFO:anonymise:crs_cdl_network.schedules: 2948420 records
        2015-04-25 20:44:07.028:INFO:anonymise:crs_cdl_network.team_episodes: 151836 records
        2015-04-25 20:44:07.064:INFO:anonymise:crs_cdl_network.telephone: 148720 records
        2015-04-25 20:44:07.097:INFO:anonymise:crs_cdl_network.ward_stays: 131985 records

        After phase 1 of copying/text extraction, with a 1000-row limit on the
        documentlibrary table (NB approximate number of rows):

        +---------------------+-------------+----------------+
        | Table               | Size in MiB | Approx. # rows |
        +---------------------+-------------+----------------+
        | address             |       70.13 |         425752 |
        | alias               |        7.03 |          59073 |
        | assessment          |      256.83 |          10318 |
        | careplan            |      191.95 |          20559 |
        | careplangoal        |      102.16 |         192640 |
        | cdlinternalreferral |        2.63 |           4741 |
        | cdlpatient          |        2.75 |          13209 |
        | cgas                |        1.59 |           2505 |
        | dependant           |        0.14 |            886 |
        | diagnosis           |       10.03 |          75277 |
        | documentlibrary     |        8.56 |           1274 |
        | employment_status   |        1.73 |          11945 |
        | exclude             |        0.02 |              0 |
        | honos               |        9.81 |          16171 |
        | honos_65            |        5.73 |          11701 |
        | honos_ca            |        0.06 |             63 |
        | honos_ld            |        0.50 |            912 |
        | honos_secure        |        0.23 |            309 |
        | living_arrangements |        0.11 |            588 |
        | mpi                 |       28.08 |         160866 |
        | personal_carers     |        7.03 |          38366 |
        | practicegp          |       80.13 |         354670 |
        | procedures          |        0.44 |           2225 |
        | referral            |      109.17 |         357245 |
        | schedules           |      990.59 |        2952553 |
        | team_episodes       |       35.08 |         151676 |
        | telephone           |       17.03 |         149018 |
        | ward_stays          |       29.08 |         131564 |
        +---------------------+-------------+----------------+


    -------------------------------------------------------------------------------
    Q.  Crash when closing cursor after reading VARBINARY(MAX) field (via SQL
        Server JDBC interface, via jpype, via jaydebeapi).
    -------------------------------------------------------------------------------
    A.  Short answer: fixed internally (in rnc_db.py) by reconfiguring the SQL
        Server JDBC connection.

        Long answer/thoughts:

        ps aux
        gdb -p 28896
        backtrace

            #0  0x00007fbfd1b3f14b in __libc_recv (fd=21, buf=0x7fff06f5a300, n=8,
                flags=-1) at ../sysdeps/unix/sysv/linux/x86_64/recv.c:33
            #1  0x00007fbfc09ece1d in ?? ()
               from /usr/lib/jvm/java-7-openjdk-amd64/jre/lib/amd64/libnet.so
            #2  0x00007fbfc09e8bd0 in Java_java_net_SocketInputStream_socketRead0 ()
               from /usr/lib/jvm/java-7-openjdk-amd64/jre/lib/amd64/libnet.so
            #3  0x00007fbfc10989a1 in ?? ()
            #4  0x0000000000000000 in ?? ()

        Related to this bug?
            https://bugs.openjdk.java.net/browse/JDK-8049846

        Occurs when you call cursor.close() of jaydebeapi:
            https://github.com/baztian/jaydebeapi/blob/master/jaydebeapi/__init__.py

        Unrelated to any conversion that I was doing.

        sudo apt-get remove openjdk-7-jre  # though didn't get rid of java

        sudo add-apt-repository ppa:webupd8team/java
        sudo apt-get update
        sudo apt-get install oracle-java8-installer

        ... no help

        Thoughts:
            https://code.google.com/p/jyjdbc/source/browse/jyjdbc/__init__.py
            https://social.technet.microsoft.com/Forums/en-US/430b4352-92c9-4a5c-98b5-f96643009453/jdbc-driver-thread-stuck-infinite-while-closing-result-set-locked?forum=sqldataaccess
            https://bugs.mysql.com/bug.php?id=74739

        Nasty workaround:
            don't close the cursors; use a set for each database?
            ... didn't help: crashed on the table *after* the one with the
            VARBINARY(MAX) field.

        SQL Server / JDBC driver / connection properties:
            https://msdn.microsoft.com/en-us/library/ms378672(v=sql.110).aspx
        ... and data types:
            https://msdn.microsoft.com/en-us/library/ms378813(v=sql.110).aspx

        FIXED!
            Use responseBuffering = adaptive in the settings for the SQL Server
            JDBC driver.
            https://msdn.microsoft.com/en-us/library/ms378988(SQL.90).aspx

        ---------------------------------------------------------------------------
        Enabling JDBC logging
        ---------------------------------------------------------------------------
            https://msdn.microsoft.com/en-us/library/ms378517(v=sql.110).aspx
        $ find /usr -name "logging.properties"
            /usr/lib/jvm/java-7-openjdk-amd64/jre/lib/logging.properties
            /usr/lib/jvm/java-8-oracle/jre/lib/logging.properties
                ... this one (check with: java -version)
        Default handler is the console. Unchanged line:
            # handlers = java.util.logging.ConsoleHandler
            handlers = java.util.logging.ConsoleHandler, java.util.logging.FileHandler
        Add line:
            com.microsoft.sqlserver.jdbc.level=FINEST
        Change logger level:
            java.util.logging.ConsoleHandler.level = FINEST
        OR configure file handler:
            java.util.logging.FileHandler.pattern = %h/java%u.log
            java.util.logging.FileHandler.limit = 5000000
            java.util.logging.FileHandler.count = 20
            java.util.logging.FileHandler.formatter = java.util.logging.SimpleFormatter
            java.util.logging.FileHandler.level = FINEST


        Python 3 changes -- not done, but some notes:

        $ sudo apt-get install python3-pip

        import bcrypt  # sudo apt-get install python3-bcrypt
        import configparser  # was: import ConfigParser
        import dateutil  # sudo apt-get install python3-dateutil
        import M2Crypto  # sudo apt-get install swig; sudo pip3 install M2Crypto  # INSTALLS BUT FAILS TO IMPORT
        import pytz  # sudo pip3 install pytz
        import regex  # sudo apt-get install python3-regex
        import sortedcontainers  # sudo pip3 install sortedcontainers


    -------------------------------------------------------------------------------
    ??naming
    -------------------------------------------------------------------------------

    CRATE: Clinical Records Anonymisation and Text Extraction


    ===============================================================================
    JDBC SQL tools
    ===============================================================================

    - Squirrel SQL
        - Install

            wget http://downloads.sourceforge.net/project/squirrel-sql/1-stable/3.6.0/squirrel-sql-3.6-standard.jar?r=http%3A%2F%2Fsquirrel-sql.sourceforge.net%2F&ts=1432028753&use_mirror=netcologne

            # now rename the result to squirrel-sql-3.6-standard.jar

            java -jar squirrel-sql-3.6-standard.jar

            # install, picking Microsoft SQL Server and MySQL as plugins,
            # plus "Multi Source" and "Data import"
            # Will then run from its new directory, via

            squirrel-sql-3.6/squirrel-sql.sh &

        - Configure SQL Server

            Windows > View Drivers > Microsoft MSSQL Server JDBC Driver
                > Extra Class Path
                > find sqljdbc_4.1/enu/sqljdbc41.jar

            Windows > View Aliases > Add Alias
                ... set up the database
                ... test connection
            URL defaults to:
                jdbc:sqlserver://<server_name>:1433;databaseName=<db_name>
            Since it didn't work, using this:
               jdbc:sqlserver://INSERT_IP_ADDRESS:1433;databaseName=INSERT_DB_NAME;responseBuffering=adaptive;selectMethod=cursor
            It copes with specifying the username/password in the dialogue box.

        - Configure MySQL

            Extra classpath is /usr/share/java/mysql.jar
            Beforehand: sudo apt-get install libmysql-java
            URL: jdbc:mysql://{host}:{port}/{database}

    ===============================================================================
    Django app and project structure
    ===============================================================================

    - want a single virtualenv
    - Django app may want to access anonymisation classes e.g. data dictionary
    - top-level Python programs should be distinct from imported files

    - http://python-notes.curiousefficiency.org/en/latest/python_concepts/import_traps.html

    ===============================================================================
    Profiling the Django app
    ===============================================================================

    python -m cProfile -o c:\CRATE_PROFILE.profile crate_anon/tools/launch_cherrypy_server.py

    ===============================================================================
    Static files, speed, etc.
    ===============================================================================

    - Minimize the number of templates (e.g. remove action_only_form.html).
    - At present we're using {% include %} to put CSS in.
    - This would be faster with static URLs.
    - However, the tricky bit is PDF generation, for which wkhtmltopdf needs to
      have embedded CSS (since we can't guarantee its network access to our own web
      server).
    - Can this be managed better? If so, several things could go to static:
        - base.css
        - collapse.js
        - potentially a new fancier Javascript file for query building
    - We could achieve this with our pdf_template_dict() function, which is called
      for all PDF generation. It could bake in appropriate CSS, by loading the
      static file directly in code (and caching the result).
    - Similarly for e-mail generation, where CSS also needs to be embedded.
    - Just define convenience functions:
            render_pdf_html_to_string(template, context)
            render_email_html_to_string(template, context)
    - But the tricky bits:
        - collapse.js refers to static image files, and relative paths are from
          the HTML, not the JS, so "./plus.gif" doesn't work. It needs to know the
          URL prefix for static files, so that's a problem.
          - But we can split it: variable definition in HTML/template, and the rest
            in static JS.
    - For email.css (included from base_email.html), speed isn't critical. Let's
      leave that as it is.
    - Removed base_root.html, taking out one layer of regular indirection.
    - Now, base_email.html and base_pdf.html have CSS passed to them by the
      convenience functions (extracted in Python). The web one, base.html, uses
      links to static files.

    ===============================================================================
    7. AUDITING ACCESS TO THE RESEARCH DATABASE
    ===============================================================================

    a)  MYSQL RAW ACCESS.

      - You need an auditing tool, so we've provided one; see the contents of the
        "mysql_auditor" directory.
      - Download and install mysql-proxy, at least version 0.8.5, from
            https://dev.mysql.com/downloads/mysql-proxy/
        Install its files somewhere sensible.
      - Configure (by editing) mysql_auditor.sh
      - Run it. By default it's configured for daemon mode. So you can do this:
            sudo ./mysql_auditor.sh CONFIGFILE start
      - By default the logs go in /var/log/mysql_auditor; the audit*.log files
        contain the queries, and the mysqlproxy*.log files contain information from
        the mysql-proxy program.
      - The audit log is a comma-separated value (CSV) file with these columns:
            - date/time, in ISO-8601 format with local timezone information,
              e.g. "2015-06-24T12:58:29+0100";
            - client IP address/port, e.g. "127.0.0.1:52965";
            - MySQL username, e.g. "root";
            - current schema (database), e.g. "test";
            - query, e.g. "SELECT * FROM mytable"
        Query results (or result success/failure status) are not shown.

      - To open fresh log files daily, run
            sudo FULLPATH/mysql_auditor.sh CONFIGFILE restart
        daily (e.g. from your /etc/crontab, just after midnight). Logs are named
        e.g. audit_2015_06_24.log, for their creation date.

    b)  FRONT END.

        The nascent front end will also audit queries.
        (Since this runs a web service that in principle can have access to proper
        data, it's probably better to run a username system rather than rely on
        MySQL usernames alone. Therefore, it can use a single username, and a
        database-based auditing system. The administrator could also pipe its MySQL
        connection via the audit proxy, but doesn't have to.)



    ===============================================================================
    - functools.lru_cache is not thread-safe
    ===============================================================================

      .. code-block:: none

        - Symptom:
            KeyError at /pe_df_results/4/
            (<crate_anon.crateweb.research.research_db_info.ResearchDatabaseInfo object at ...>,
            <TableId<db='RiO', schema='dbo', table='GenSENFunctionTest') at ...>)

            at get_mrid_linkable_patient_tables():

                if self.table_contains_rid(table):

            which is defined as:

                @lru_cache(maxsize=1000)
                def table_contains_rid(self, table: TableId):

        - https://bugs.python.org/issue28969

        - Thus:
          https://noamkremen.github.io/a-simple-threadsafe-caching-decorator.html
          http://codereview.stackexchange.com/questions/91656/thread-safe-memoizer
          https://pythonhosted.org/cachetools/#
          http://stackoverflow.com/questions/213455/python-threadsafe-object-cache
          http://codereview.stackexchange.com/questions/91656/thread-safe-memoizer

        - Then, also, the Django cache system:
          https://docs.djangoproject.com/en/1.10/topics/cache/
          https://github.com/rchrd2/django-cache-decorator
          https://gist.github.com/tuttle/9190308


Old pipeline notes
~~~~~~~~~~~~~~~~~~

.. code-block:: none

    PIPELINE

    ===============================================================================
    0. BEFORE FIRST USE
    ===============================================================================

    a)  Software prerequisites

        1)  MySQL 5.6 or later. For Ubuntu 14.10:

                $ sudo apt-get install mysql-server-5.6 mysql-server-core-5.6 \
                    mysql-client-5.6 mysql-client-core-5.6
                - Download the corresponding MySQL Workbench from
                    http://dev.mysql.com/downloads/workbench/
                  ... though it may moan about library incompatibilities

            ... but also sensible to use Ubuntu 15.04?

        2)  Stuff that should come with Ubuntu:
                git
                Python 2.7

        3)  This toolkit:

                $ git clone https://github.com/RudolfCardinal/anonymise

        4)  GATE
            - Download GATE Developer
            - java -jar gate-8.0-build4825-installer.jar
            - Read the documentation; it's quite good.

    b)  Ensure that the PYTHONPATH is pointing to necessary Python support files:

            $ . SET_PATHS.sh

        To ensure it's working:

            $ ./anonymise.py --help

    c)  Ensure that all source database(s) are accessible to the Processing
        Computer.

    d)  Write a draft config file, giving connection details for all source
        databases. To generate a demo config for editing:

            $ ./anonymise.py --democonfig > MYCONFIG.ini

        Edit it so that it can access your databases.

    e)  Ensure that the data dictionary (DD) has been created, and then updated and
        verified by a human. To generate a draft DD from your databases for
        editing:

            $ ./anonymise.py MYCONFIG.ini --draftdd

        Edit it with any TSV editor (e.g. Excel, LibreOffice Calc).

    ===============================================================================
    1. PRE-PROCESSING
    ===============================================================================

    a)  Ensure that the databases are copied and ready.

    b)  Add in any additional data. For example, if you want to process a postcode
        field to geographical output areas, such as
            http://en.wikipedia.org/wiki/ONS_coding_system
        then do it now; add in the new fields. Don't remove the old (raw) postcodes;
        they'll be necessary for anonymisation.

    c)  UNCOMMON OPTION: anonymise using NLP to find names. See below.
        If you want to anonymise using NLP to find names, rather than just use the
        name information in your source database, run nlp_manager.py now, using
        (for example) the Person annotation from GATE's
            plugins/ANNIE/ANNIE_with_defaults.gapp
        application, and send the output back into your database. You'll need to
        ensure the resulting data has patient IDs attached, probably with a view
        (see (d) below).

    d)  Ensure every table that relates to a patient has a common field with the
        patient ID that's used across the database(s) to be anonymised.
        Create views if necessary. The data dictionary should reflect this work.

    e)  Strongly consider using a row_id (e.g. integer primary key) field for each
        table. This will make natural language batch processing simpler (see
        below).

    ===============================================================================
    2. ANONYMISATION (AND FULL-TEXT INDEXING) USING A DATA DICTIONARY
    ===============================================================================

    OBJECTIVES:
        - Make a record-by-record copy of tables in the source database(s).
          Handle tables that do and tables that don't contain patient-identifiable
          information.
        - Collect patient-identifiable information and use it to "scrub" free-text
          fields; for example, with forename=John, surname=Smith, and spouse=Jane,
          one can convert freetext="I saw John in clinic with Sheila present" to
          "I saw XXX in clinic with YYY present" in the output. Deal with date,
          numerical, textual, and number-as-text information sensibly.
        - Allow other aspects of information restriction, e.g. truncating dates of
          birth to the first of the month.
        - Apply one-way encryption to patient ID numbers (storing a secure copy for
          superuser re-identification).
        - Enable linking of data from multiple source databases with a common
          identifier (such as the NHS number), similarly encrypted.
        - For performance reasons, enable parallel processing and incremental
          updates.
        - Deal with binary attachments containing text.

        For help: anonymise.py --help

    a)  METHOD 1: THREAD-BASED. THIS IS SLOWER.
            anonymise.py <configfile> [--threads=<n>]

    b)  METHOD 2: PROCESS-BASED. THIS IS FASTER.
        See example in launch_multiprocess.sh

        ---------------------------------------------------------------------------
        Work distribution
        ---------------------------------------------------------------------------
        - Best performance from multiprocess (not multithreaded) operation.
        - Drop/rebuild tables: single-process operation only.
        - Non-patient tables:
            - if there's an integer PK, split by row
            - if there's no integer PK, split by table (in sequence of all tables).
        - Patient tables: split by patient ID.
          (You have to process all scrubbing information from a patient
          simultaneously, so that's the unit of work. Patient IDs need to be
          integer for this method, though for no other reason.)
        - Indexes: split by table (in sequence of all tables requiring indexing).
          (Indexing a whole table at a time is fastest, not index by index.)

        ---------------------------------------------------------------------------
        Incremental updates
        ---------------------------------------------------------------------------
        - Supported via the --incremental option.
        - The problems include:
            - aspects of patient data (e.g. address/phone number) might, in a
              very less than ideal world, change rather than being added to. How
              to detect such a change?
            - If a new phone number is added (even in a sensible way) -- or, more
              importantly, a new alias (following an anonymisation failure),
              should re-scrub all records for that patient, even records previously
              scrubbed.
        - Solution:
            - Only tables with a suitable PK can be processed incrementally.
              The PK must appear in the destination database (and therefore can't
              be sensitive, but should be an uninformative integer).
              This is so that if a row is deleted from the source, one can check
              by looking at the destination.
            - For a table with a src_pk, one can set the add_src_hash flag.
              If set, then a hash of all source fields (more specifically: all that
              are not omitted from the destination, plus any that are used for
              scrubbing, i.e. scrubsrc_patient or scrubsrc_thirdparty) is created
              and stored in the destination database.
            - Let's call tables that use the src_pk/add_src_hash system "hashed"
              tables.
            - During incremental processing:
                1. Non-hashed tables are dropped and rebuilt entirely.
                   Any records in a hashed destination table that don't have a
                   matching PK in their source table are deleted.
                2. For each patient, the scrubber is calculated. If the
                   *scrubber's* hash has changed (stored in the secret_map table),
                   then all destination records for that patient are reworked
                   in full (i.e. the incremental option is disabled for that
                   patient).
                3. During processing of a table (either per-table for non-patient
                   tables, or per-patient then per-table for patient tables), each
                   row has its source hash recalculated. For a non-hashed table,
                   this is then reprocessed normally. For a hashed table, if there
                   is a record with a matching PK and a matching source hash, that
                   record is skipped.

        ---------------------------------------------------------------------------
        Anonymising multiple databases together
        ---------------------------------------------------------------------------
        - RATIONALE: A scrubber will be built across ALL source databases, which
          may improve anonymisation.
        - If you don't need this, you can anonymise them separately (even into
          the same destination database, if you want to, as long as table names
          don't overlap).
        - The intention is that if you anonymise multiple databases together,
          then they must share a patient numbering (ID) system. For example, you
          might have two databases using RiO numbers; you can anonymise them
          together. If they also have an NHS number, that can be hashed as a master
          PID, for linking to other databases (anonymised separately). (If you used
          the NHS number as the primary PID, the practical difference would be that
          you would ditch any patients who have a RiO number but no NHS number
          recorded.)
        - Each database must each use a consistent name for this field, across all
          tables, WITHIN that database.
        - This field, which must be an integer, must fit into a BIGINT UNSIGNED
          field (see wipe_and_recreate_mapping_table() in anonymise.py).
        - However, the databases don't have to use the same *name* for the field.
          For example, RiO might use "id" to mean "RiO number", while CamCOPS might
          use "_patient_idnum1".

    ===============================================================================
    3. NATURAL LANGUAGE PROCESSING
    ===============================================================================

    OBJECTIVES: Send free-text content to natural language processing (NLP) tools,
    storing the results in structured form in a relational database -- for example,
    to find references to people, drugs/doses, cognitive examination scores, or
    symptoms.

        - For help: nlp_manager.py --help
        - The Java element needs building; use buildjava.sh

        - STRUCTURE: see nlp_manager.py; CamAnonGatePipeline.java

        - Run the Python script in parallel; see launch_multiprocess_nlp.sh

        ---------------------------------------------------------------------------
        Work distribution
        ---------------------------------------------------------------------------
        - Parallelize by source_pk.

        ---------------------------------------------------------------------------
        Incremental updates
        ---------------------------------------------------------------------------
        - Here, incremental updates are simpler, as the NLP just requires a record
          taken on its own.
        - Nonetheless, still need to deal with the conceptual problem of source
          record modification; how would we detect that?
            - One method would be to hash the source record, and store that with
              the destination...
        - Solution:
            1. Delete any destination records without a corresponding source.
            2. For each record, hash the source.
               If a destination exists with the matching hash, skip.

    ===============================================================================
    EXTRA: ANONYMISATION USING NLP.
    ===============================================================================

    OBJECTIVE: remove other names not properly tagged in the source database.

    Here, we have a preliminary stage. Instead of the usual:

                            free text
        source database -------------------------------------> anonymiser
                    |                                           ^
                    |                                           | scrubbing
                    +-------------------------------------------+ information


    we have:

                            free text
        source database -------------------------------------> anonymiser
              |     |                                           ^  ^
              |     |                                           |  | scrubbing
              |     +-------------------------------------------+  | information
              |                                                    |
              +---> NLP software ---> list of names ---------------+
                                      (stored in source DB
                                       or separate DB)

    For example, you could:

        a) run the NLP processor to find names, feeding its output back into a new
           table in the source database, e.g. with these options:

                inputfielddefs =
                    SOME_FIELD_DEF
                outputtypemap =
                    person SOME_OUTPUT_DEF
                progenvsection = SOME_ENV_SECTION
                progargs = java
                    -classpath {NLPPROGDIR}:{GATEDIR}/bin/gate.jar:{GATEDIR}/lib/*
                    CamAnonGatePipeline
                    -g {GATEDIR}/plugins/ANNIE/ANNIE_with_defaults.gapp
                    -a Person
                    -it END_OF_TEXT_FOR_NLP
                    -ot END_OF_NLP_OUTPUT_RECORD
                    -lt {NLPLOGTAG}
                input_terminator = END_OF_TEXT_FOR_NLP
                output_terminator = END_OF_NLP_OUTPUT_RECORD

                # ...

        b) add a view to include patient numbers, e.g.

                CREATE VIEW patient_nlp_names
                AS SELECT
                    notes.patient_id,
                    nlp_person_from_notes._content AS nlp_name
                FROM notes
                INNER JOIN nlp_person_from_notes
                    ON notes.note_id = nlp_person_from_notes._srcpkval
                ;

        c) feed that lot to the anonymiser, including the NLP-generated names as
           scrubsrc_* field(s).


    ===============================================================================
    4. SQL ACCESS
    ===============================================================================

    OBJECTIVE: research access to the anonymised database(s).

    a)  Grant READ-ONLY access to the output database for any relevant user.

    b)  Don't grant any access to the secret mapping database! This is for
        trusted superusers only.

    c)  You're all set.
