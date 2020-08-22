..  crate_anon/docs/source/installation/database_drivers.rst

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

.. _ADO: https://en.wikipedia.org/wiki/ActiveX_Data_Objects
.. _Django: https://www.djangoproject.com/
.. _MARS: https://docs.microsoft.com/en-us/sql/relational-databases/native-client/features/using-multiple-active-result-sets-mars
.. _Microsoft ODBC Driver for SQL Server: https://docs.microsoft.com/en-us/sql/connect/odbc/microsoft-odbc-driver-for-sql-server
.. _Microsoft ODBC Driver for SQL Server (Linux): https://docs.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server
.. _MySQL: https://www.mysql.com/
.. _MySQL C API: https://dev.mysql.com/doc/refman/5.7/en/c-api.html
.. _MySQL Workbench: https://www.mysql.com/products/workbench/
.. _PostgreSQL: https://www.postgresql.org/
.. _Python: https://www.python.org/
.. _SQLAlchemy: https://www.sqlalchemy.org/
.. _SQL Server: https://en.wikipedia.org/wiki/Microsoft_SQL_Server
.. _SQLite: https://www.sqlite.org/
.. _unixODBC: http://www.unixodbc.org/


.. _database_drivers:

Databases and database drivers
==============================

.. contents::
   :local:


Database engines
----------------

Supported engines include:

- MySQL_: free, open source, simple administration including via `MySQL
  Workbench`_.

- PostgreSQL_: free, open source, emphasis on standards compliance, advanced
  column types.

- `SQL Server`_: Microsoft; not free; common in UK NHS contexts.


.. _recommended_database_drivers:

Recommended database drivers
----------------------------

CRATE needs to talk to several databases, potentially of several types (e.g. an
`SQL Server`_ source and a MySQL_ destination), and from several operating
systems (e.g. if it runs on Windows or Linux). It’s therefore important to be
clear of what works well and what doesn’t when connecting CRATE to databases.

Summarizing the discussion below:

- For MySQL_: if you want to install a fast option, use mysqlclient_. If you
  want to avoid dependencies, use :ref:`MySQL Connector/Python
  <mysqlconnector>` or :ref:`PyMySQL <pymysql>`.

- For `SQL Server`_: with Django use :ref:`django-mssql-backend
  <django_mssql_backend>`, and with SQLAlchemy use pyodbc_, both via ODBC. For
  the ODBC drivers:

  - under Windows, use native drivers (`Microsoft ODBC Driver for SQL Server`_);
  - under Linux, use the `Microsoft ODBC Driver for SQL Server (Linux)`_ (and
    if you don't want to use that, use FreeTDS_ in a version that supports
    MARS_).

- For PostgreSQL_: use psycopg2_, though you may have to install prerequisites
  (e.g. PostgreSQL itself).

CRATE doesn’t bundle in database drivers, since they are OS-specific in many
instances, and can be installed as required by the user. The exception is the
:ref:`Docker setup <crate_docker>`, which does bundle recommended drivers.


More detail
-----------

Internally, CRATE is written primarily in Python_ 3. It uses SQLAlchemy_ for
the anonymisation, and it uses Django_ for its web interface.

In general, software can talk to database via files (e.g. SQLite_), via TCP/IP
(e.g. MySQL_, PostgreSQL_, `SQL Server`_), via custom interfaces (e.g.
Windows-based authentication for SQL Server), and via standardized intermediate
interfaces (e.g. ODBC, JDBC) in which the client software communicates with the
intermediate interface which talks (somehow) to the final database.

Python libraries may be “pure Python”, in which case they install well via
standard tools like pip, or use a mixture of Python and other code (e.g. C,
Java), in which case appropriate tools (e.g. a C compiler or a Java virtual
machine) must also be available on the destination machine. Since the latter
are often specific to an operating system and/or CPU architecture, they are
sometimes more complex to install.

None of Django, SQLAlchemy, or CRATE “bake in” support for specific databases
[#notbakedin]_. This is because it’s easy to bake in old versions, making it
hard to upgrade. Keep things modular.



A catalogue of Python database drivers
--------------------------------------

.. _mysqldb:

MySQL + MySQLdb
~~~~~~~~~~~~~~~

**Deprecated.** ``MySQLdb`` is an open-source Python interface to the `MySQL C
API`_. It has largely been replaced by mysqlclient_. It doesn't support Python
3 [#mysqldbnotpython3]_: Python 2 only.

==================  ===========================================================
Driver              MySQLdb
Home page           | https://pypi.org/project/MySQL-python/
                    | https://github.com/farcepest/MySQLdb1
Database            MySQL_
Installation        ``pip install mysql-python``
Import              ``import MySQLdb``
Django ``ENGINE``   ``django.db.backends.mysql``
SQLAlchemy URL      ``mysql+mysqldb://user:password@host:port/database?charset=utf8``
Licence             GPL
==================  ===========================================================

"MySQLdb" and "mysql-python" are synonyms.

.. include:: include_needs_compiler.rst

It also requires appropriate libraries to build itself, so can fail to
autoinstall. It doesn’t autoinstall on a clean Linux box. You will need the
MySQL libraries installed; under Ubuntu Linux, you can do this:

.. code-block:: bash

    sudo apt-get install mysql


.. _mysqlclient:

MySQL + mysqlclient
~~~~~~~~~~~~~~~~~~~

``mysqlclient`` is an open-source fork of :ref:`MySQLdb (MySQL-python)
<mysqldb>` that adds Python 3 support and fixes bugs. (Similarly, it is a
Python interface to the `MySQL C API`_.) It is a drop-in replacement for
MySQLdb, all Python references remain to ``MySQLdb``.

==================  ===========================================================
Driver              mysqlclient
Home page           | https://mysqlclient.readthedocs.io/
                    | https://pypi.org/project/mysqlclient/
Database            MySQL_
Installation        ``pip install mysqlclient``
Import              ``import MySQLdb  # same as MySQLdb``
Django ``ENGINE``   ``django.db.backends.mysql``
SQLAlchemy URL      ``mysql+mysqldb://user:password@host:port/database?charset=utf8``
Licence             GPL
==================  ===========================================================

.. note::
    This is Django's recommended method for using MySQL
    [#djangorecommendedmysql]_.

.. note::
    It's quick, because it's C-based [#mysqlcfast]_.

.. include:: include_needs_compiler.rst

.. note::
    Under Linux, you might see the error ``NameError: name '_mysql' is not
    defined``, despite installing the relevant MySQL libraries in the operating
    system (e.g. via ``sudo apt install mysql-client``). Higher up in the error
    trace, you may see this error: ``ImportError: libmysqlclient.so.21: cannot
    open shared object file: No such file or directory``. (It may be buried in
    lots of other error messages; to see it by itself, just run Python and try
    ``import MySQLdb``.) The MySQL libraries live somewhere within
    ``/usr/lib``. This error can occur if mysqlclient was installed under a
    different operating system version to the one you're using. You can fix it
    by reinstalling the Python library with ``pip uninstall mysqlclient && pip
    install --no-binary mysqlclient mysqlclient``.

Under Windows, there can be additional compilation problems; see
https://github.com/PyMySQL/mysqlclient-python/issues/54.

.. _mysqlconnector:

MySQL + MySQL Connector/Python
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

MySQL Connector/Python is a pure Python driver for MySQL from MySQL themselves
(well, Oracle; Oracle own MySQL).

==================  ===========================================================
Driver              MySQL Connector/Python
Home page           | https://dev.mysql.com/downloads/connector/python/
                    | https://github.com/mysql/mysql-connector-python
Database            MySQL_
Installation        Use ``pip`` with a custom URL. See below.
Import              ``import mysql.connector``
Django ``ENGINE``   ``mysql.connector.django``
SQLAlchemy URL      ``mysql+mysqlconnector://...``
Licence             GPL [#gpldebate]_
==================  ===========================================================

Installation: use ``pip`` with a custom URL. See
http://stackoverflow.com/questions/34489271. They have a presence at
https://pypi.python.org/pypi/mysql-connector-python, but you can’t do ``pip
install mysql-connector-python``; the subpage for a given version (e.g. 2.0.4)
advertises a URL that you can use with ``pip install <URL>``, and you can
substitute ``https`` for ``http`` if required.

Re the Django `ENGINE` setting: see
https://dev.mysql.com/doc/connector-python/en/connector-python-django-backend.html.

It's slower than C-based interfaces, obviously [#mysqlconnectorslow]_.

**Problems.** MySQL Connector/Python 2.0.4 doesn’t work with Django 1.9.7
(“cannot import name ‘BaseDatabaseFeatures’”), as of 2016-06-14
[https://code.djangoproject.com/ticket/24355]. At this time, 2.0.4 was the most
recent MySQL Connector/Python version cited in PyPI, but the direct-download
version from Oracle was 2.1.3. Don’t use the .MSI download; use “pip install
https://cdn.mysql.com/Downloads/Connector-Python/mysql-connector-python-2.1.3.tar.gz”
from within the virtual environment. This version does better with Django
1.9.7. However, it fails with errors like “django.db.utils.DatabaseError:
Incorrect datetime value: ‘2016-06-14 12:41:52.320665+00:00’ for column
‘applied’ at row 1” [https://code.djangoproject.com/ticket/26113].


.. _pymysql:

MySQL + PyMySQL
~~~~~~~~~~~~~~~

PyMySQL is a pure-Python MySQL client library. It's slower than mysqlclient_ as
a result.

==================  ===========================================================
Driver              PyMySQL
Home page           | http://pymysql.readthedocs.io
                    | https://github.com/PyMySQL/PyMySQL
                    | https://pypi.python.org/pypi/PyMySQL
Database            MySQL_
Installation        ``pip install pymysql``
Import              ``import pymysql``
Django ``ENGINE``   ``django.db.backends.mysql`` plus extras; see below
SQLAlchemy URL      ``mysql+pymysql://user:password@host:port/database?charset=utf8``
Licence             MIT License
==================  ===========================================================

PyMySQL can masquerade as MySQLdb upon explicit request. The Django ``ENGINE`` setting
remains ``django.db.backends.mysql``, but a short extra import statement is
required in ``manage.py``. See:

- http://stackoverflow.com/questions/2636536
- http://stackoverflow.com/questions/13320343/

CRATE implements this fix, though actually if you want to run Celery as well,
you need the fix via the Celery entry point, so it’s easier to put one fix in
``settings.py``.


.. _django_mssql:

SQL Server + django-mssql
~~~~~~~~~~~~~~~~~~~~~~~~~

**Not recommended.**

An ADO_-based Django database backend for Microsoft SQL Server.

==================  ===========================================================
Driver              django-mssql
Home page           http://django-mssql.readthedocs.io/
Database            `SQL Server`_
Installation        ``pip install django-mssql``
Import              –
Django ``ENGINE``   ``sqlserver_ado``
SQLAlchemy URL      –
==================  ===========================================================

Django doesn’t support SQL Server officially
[https://docs.djangoproject.com/en/1.9/ref/databases/]; django-mssql is a
third-party back-end, but it’s the semi-official one
[http://django-mssql.readthedocs.org/en/latest/]. It is **Windows-only**
[http://stackoverflow.com/questions/22604732].

With django-mssql==1.7 and Django==1.9.7, it doesn’t work (the error being “No
module named ‘django.db.backends.util’). It’s possible to hack around this, but
it doesn’t work out of the box
[http://stackoverflow.com/questions/9944204/setting-up-django-mssql-issues].
Also, the SQL Server version supported appears
to be somewhat specific to the django-mssql version [https://bitbucket.org/Manfre/django-mssql/].

With django-mssql==1.8 and Django==1.10.5, it works (tested with SQL Server
2014), but you have to edit the ‘provider’ option, or you get errors like
‘ADODB.Connection’ / ‘Provider cannot be found. It may not be properly
installed.’ [See also
http://stackoverflow.com/questions/26406943/establishing-connection-to-ms-sql-server-2014-with-django-mssql-1-6.]
For compatibility with the way django-pyodbc-azure works, you also need to set
``use_legacy_date_fields``. Here’s an example:

.. code-block:: none

    ‘my_rio': {
        'ENGINE': 'sqlserver_ado',
        'NAME': 'RIO_TEST',  # database name
        'OPTIONS': {
             'use_mars': True,  # the default is True
             'provider’: ‘SQLOLEDB’,
             'use_legacy_date_fields’: True,
        },
        'USER': 'XXX',
        'PASSWORD': 'XXX',
    }

It works to a degree, but even with ``use_legacy_date_fields``, lots of date
comparisons failed. It was easier to hack django-pyodbc-azure slightly.


.. _django_pymssql:

SQL Server + django-pymssql
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Not recommended.**

This is no longer maintained (2018-12-06). It is a wrapper around
:ref:`django-mssql <django_mssql>` that uses pymssql_ instead of ADO_ to
connect to SQL Server.

==================  ===========================================================
Driver              django-pymssql
Home page           https://github.com/aaugustin/django-pymssql
Database            `SQL Server`_
Installation        ``pip install django-pymssql`` and also needs pymssql_
Import              –
Django ``ENGINE``   ``sqlserver_pymssql``
SQLAlchemy URL      –
Licence             MIT License
==================  ===========================================================

- The project self-reports as not quite passing the Django test suite. It’s
  probably this or the :ref:`django-pyodbc-azure <django_pyodbc_azure>` route.
  This has the simpler stack.

- Doesn't work with Django 1.8. Using ‘sqlserver_pymssql’ engine leads to
  sqlserver_ado failing to import ‘django.db.backends.util’, etc. See
  http://stackoverflow.com/questions/30051839;
  http://stackoverflow.com/questions/9944204.


.. _pymssql:

SQL Server + pymssql
~~~~~~~~~~~~~~~~~~~~

A Python interface to `SQL Server`_ via FreeTDS_.

==================  ===========================================================
Driver              pymssql
Home page           http://www.pymssql.org/
Database            `SQL Server`_
Installation        ``pip install pymssql``
Import              ``import pymssql``
Django ``ENGINE``   –
SQLAlchemy URL      mssql+pymssql://username:password@freetdsname/database?charset=utf8
Licence             LGPL
==================  ===========================================================

Intended for Linux use. The pymssql_ library uses FreeTDS_ code to communicate
with SQL Server. Under Ubuntu, there are prerequisites: ``sudo apt-get install
freetds-dev`` first.


.. _django_pyodbc_azure:

SQL Server (or other) + django-pyodbc-azure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

``django-pyodbc-azure`` is a Django interface to any database via :ref:`PyODBC
<pyodbc>`. It was subsequently replaced (e.g. for Django 3) by
:ref:`django-mssql-backend <django_mssql_backend>` (q.v.).

==================  ===========================================================
Driver              django-pyodbc-azure
Home page           | https://pypi.org/project/django-pyodbc-azure/
                    | https://github.com/michiya/django-pyodbc-azure
Database            Any with an :ref:`ODBC <odbc>` connection
Installation        ``pip install django-pyodbc-azure`` and also needs :ref:`PyODBC <pyodbc>`
Import              –
Django ``ENGINE``   ``sql_server.pyodbc``
SQLAlchemy URL      –
Licence             BSD License
==================  ===========================================================

Under Linux, you can use the FreeTDS_ ODBC driver, in which case read the
``'OPTIONS': {'host_is_server': ...}`` option carefully in the docs.

The Django database dictionary can be configured to use a Windows ODBC DSN with
e.g.: [#djangopyodbcazuremethod]_

.. code-block:: none

    ‘my_rio': {
        'ENGINE': 'sql_server.pyodbc',
        'NAME': 'RIO_TEST',  # database name
        'OPTIONS': {
             'driver': 'SQL Server Native Client 11.0',
             # ... 'driver' is optional

             'dsn': 'RIO_TEST_SANDPIT',  # ODBC DSN
             # ... note lower case key as of django-pyodbc-azure 2.0.6

             # 'MARS_Connection': True,
             # ... no longer in django-pyodbc-azure 2.0.6; automatic
        },
        'USER': '',  # blank for Microsoft Integrated Security
        'PASSWORD': '',
    }


It is not possible to avoid specifying NAME (without hacking the
sql_server.pyodbc source) – even if it’s unnecessary because database name is
also in the ODBC configuration for the specified DSN. Just supply it again.
(Note that if you specify a NAME that is a mismatch to the ODBC configuration,
you get odd effects – e.g. no data when you try to describe the database or
view its structure.)

If you are running as a service, you may have to specify the username/password,
since the program will be running as a system account.

.. note::

    ``django-pyodbc-azure`` generally works well. However, with
    ``django-pyodbc-azure==1.10.4.0``, ``pyodbc==4.0.3``, and
    ``Django==1.10.5``, there appears to be a bug in using
    ``cursor.fetchone()``, in that PyODBC automatically calls
    ``self.cursor.nextset()``, and this can lead to crashes with errors like
    “No results. Previous SQL was not a query.” This can be fixed by hacking
    that call out of ``sql_server/pyodbc/base.py``, in ``Cursor.fetchone()``,
    and CRATE does this in a dynamic fashion if
    ``DISABLE_DJANGO_PYODBC_AZURE_CURSOR_FETCHONE_NEXTSET`` is set (see
    :ref:`web_config_file`). This proved easier than switching to
    ``django-mssql``.


.. todo::
    Check if ``DISABLE_DJANGO_PYODBC_AZURE_CURSOR_FETCHONE_NEXTSET`` with
    more recent of ``django-pyodbc-azure`` (and if not necessary, document
    successful version).


.. _django_mssql_backend:

SQL Server + django-mssql-backend
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A replacement for :ref:`django-pyodbc-azure <django_pyodbc_azure>` (q.v.)

==================  ===========================================================
Driver              django-mssql-backend
Home page           | https://pypi.org/project/django-mssql-backend/
                    | https://github.com/ESSolutions/django-mssql-backend
Database            Any with an :ref:`ODBC <odbc>` connection
Installation        ``pip install django-mssql-backend`` and also needs
                    :ref:`PyODBC <pyodbc>`
Import              –
Django ``ENGINE``   ``sql_server.pyodbc``
SQLAlchemy URL      –
Licence             BSD License
==================  ===========================================================


.. _psycopg2:

PostgreSQL + psycopg2
~~~~~~~~~~~~~~~~~~~~~

Python interface to PostgreSQL_.

==================  ===========================================================
Driver              psycopg2
Home page           http://initd.org/psycopg/docs/
Database            PostgreSQL_
Installation        ``pip install psycopg2``
Import              ``import psycopg2``
Django ``ENGINE``   ``django.db.backends.postgresql_psycopg2``
SQLAlchemy URL      ``postgresql://user:password@host/database``
Licence             LGPL
==================  ===========================================================

.. include:: include_needs_compiler.rst


.. _pyodbc:

Any database + PyODBC
~~~~~~~~~~~~~~~~~~~~~

A Python interface to any database via :ref:`ODBC <odbc>`.

==================  ===========================================================
Driver              PyODBC
Home page           | http://mkleehammer.github.io/pyodbc/
                    | https://github.com/mkleehammer/pyodbc/wiki
Database            Any with an :ref:`ODBC <odbc>` connection
Installation        ``pip install pyodbc``
Import              ``import pyodbc``
Django ``ENGINE``   –
SQLAlchemy URL      | mssql+pyodbc://username:password@MY_DATABASE
                    | mssql+pyodbc://@MY_DATABASE [for e.g. Windows authentication]
==================  ===========================================================

In the SQLAlchemy URL examples, ``MY_DATABASE`` is an example ODBC data source
name (DSN).

When talking to SQL Server databases via SQLAlchemy, you can also specify the
host/port directly in the connection string (rather than having to set up a
DSN); see `Hostname connections
<https://docs.sqlalchemy.org/en/13/dialects/mssql.html#module-sqlalchemy.dialects.mssql.pyodbc>`_.

SQLAlchemy **deprecates** MySQL via this route:
http://docs.sqlalchemy.org/en/rel_1_0/dialects/mysql.html.

- Install an ODBC driver.

- On Windows systems with SQL Server installed, you get driver choices like
  “SQL Server”, “SQL Server Native Client 10.0”, “SQL Server Native Client
  10.0”. I tested with “SQL Server Native Client 11.0” talking to SQL Server
  10.50.6000 [= SQL Server 2008 R2 SP3]. See
  https://support.microsoft.com/en-us/kb/321185

- In creating the ODBC data source, you choose whether you want
  username/password authentication or Integrated Windows authentication, and
  you give the data source a name (DSN), e.g. MY_DATABASE. The SQLAlchemy URL
  is then ``mssql+pyodbc://@MY_DATABASE`` (for Windows authentication), or
  ``mssql+pyodbc://username:password@MY_DATABASE`` for
  username/password authentication.

- Addendum 2017-01-16: Microsoft have deprecated the SQL Server Native Client;
  use the Microsoft ODBC Driver for SQL Server instead. (See
  https://msdn.microsoft.com/en-us/library/ms130828.aspx;
  https://blogs.msdn.microsoft.com/sqlnativeclient/2013/01/23/introducing-the-new-microsoft-odbc-drivers-for-sql-server/)
  This typically appears as “ODBC Driver 11 for SQL Server”.


Others to ignore
~~~~~~~~~~~~~~~~

- **django-pyodbc** doesn't support Python 3
  [https://pypi.python.org/pypi/django-pyodbc].

- **django-sqlserver** failed in 2015 with Django 1.9rc1, and is documented as
  buggy [https://github.com/denisenkom/django-sqlserver; older version was
  https://bitbucket.org/denisenkom/django-pytds]. It was formerly known as
  ``django-pytds`` and uses the python-tds interface
  [https://pypi.python.org/pypi/python-tds].

- **django-jython** (via **zxJDBC** then JDBC, then jTDS or a native driver):
  this requires running Django under Jython, adding complexity.

- **mxODBC**: ignored; commercial
  [http://www.egenix.com/products/python/mxODBC/].

- **adodbapi**: Not implemented in SQLAlchemy 0.6+
  [http://docs.sqlalchemy.org/en/latest/dialects/mssql.html].


Other database connection components
------------------------------------


.. _odbc:

ODBC
~~~~

ODBC is a generic API for talking to databases; see
https://en.wikipedia.org/wiki/Open_Database_Connectivity.

It’s normally easy for Python to talk to ODBC (via PyODBC). However, the ODBC
system also requires a database-specific driver, and sometimes this is fiddly.

For Windows, there shouldn't be many problems. ODBC is built into Windows, and
database-specific drivers for e.g. SQL Server are installed with SQL Server
itself, or built in, or readily available.

ODBC is provided for Linux via third-party products, notably unixODBC_.
However, the ODBC system also requires a database-specific driver, and
sometimes this is fiddly under Linux (e.g. for SQL Server).

There is some support in Python for JDBC. Here we have better drivers for SQL
Server. A full (“Type 4”) JDBC driver talks directly to the database, and does
so on any platform, as it runs in a Java virtual machine (JVM). There are two
of note: (1) Microsoft provide a Type 4 JDBC driver for SQL Server
[https://www.microsoft.com/en-gb/download/details.aspx?id=11774]; (2) jTDS is
an open-source Type 4 JDBC driver for SQL Server (based on FreeTDS)
[http://jtds.sourceforge.net/]. That sounds great, but the use of JDBC requires
Python to talk to Java. This brings some complexities. JDBC drivers for Python
can run Jython (Python in a JVM), but that’s getting complex (e.g. Django under
Jython → django-jython → zxJDBC → jTDS → SQL Server).


.. _FreeTDS:

FreeTDS
~~~~~~~

FreeTDS is a set of Unix/Linux C libraries to communicate natively with `SQL
Server`_, via an open-source implementation of the TDS protocol. See
http://www.freetds.org/. (There is also a Java equivalent, `jTDS
<http://jtds.sourceforge.net/>`_, not discussed further.)

**Configuring?** Under Linux, the system-wide file is
``/etc/freetds/freetds.conf``; this contains server/database settings
[http://www.freetds.org/userguide/freetdsconf.htm].

**Testing.**

- Use the ``tsql`` command to test it. See ``man tsql``.

- For example, to connect to a server called ``wombatvmxp``, try: ``tsql -L -H
  wombatvmxp`` to list instances, and ``tsql -H wombatvmxp -p 1433 -U user -P
  password`` to connect.

- Once you have configured ``/etc/freetds/freetds.conf``,
  you can use the config section as the server name: ``tsql -S
  my_sqlserver_connection -U user -P password``, and you’ll need to get this
  version working before you can use SQLAlchemy with FreeTDS.

- A command likely to work at the TSQL command prompt is
  ``SELECT * FROM information_schema.tables``.

- Remember to type ``GO`` (the default batch separator) to execute a command
  (http://stackoverflow.com/questions/2299249). To specify a particular
  database on the server: add ``-D database`` to the ``tsql`` command (it
  should say “Default database being set to ...”).

- Note that though http://www.freetds.org/userguide/freetdsconf.htm specifies a
  ``database`` parameter, ``man freetds.conf`` doesn’t (for ``tsql -C`` showing
  a version of 0.91). Mind you, v0.91 is from 2011
  (http://www.freetds.org/news.html). So for v0.91, ``freetds.conf`` is not the
  place to specify the database, it seems. But specifying the database in the
  SQLAlchemy URL works.

**WARNING.** FreeTDS prior to version 0.95 does not support MARS. Without this,
CRATE will fail (stopping during/after the first patient). Furthermore,
FreeTDS only supports MARS via ODBC [http://www.freetds.org/mars.html], i.e.
presumably not this way. Use pyodbc → FreeTDS instead.

To get this working under Linux:

**TL;DR: install FreeTDS 1.0 or higher, compiled for MARS; use TDS protocol 7.2
or higher; ensure MARS_Connection = Yes.**

Ubuntu 16.04 uses FreeTDS 0.91. However, this has one minor problem and one
major one. The minor one is that ``freetds.conf`` doesn’t support the
“database” parameter (but ``tsql -D`` does, and so does the SQL Alchemy URL).
The major one is that it doesn’t support MARS, so you can’t use it with CRATE
and SQL Server (CRATE will silently stop during processing of the first
patient).

To install FreeTDS 1.0, you have to get fairly low-level:

.. code-block:: bash

    # http://www.freetds.org/userguide/config.htm
    # http://www.linuxforums.org/forum/applications/199305-wmvolman-2-0-1-install-problems.html
    cd /tmp  # or somewhere
    git clone https://github.com/FreeTDS/freetds.git
    cd freetds
    libtoolize --force
    aclocal
    autoheader
    automake --force-missing --add-missing
    autoconf
    ./configure --enable-mars=yes
    make
    sudo make install

Note in particular ``--enable-mars=yes``.

Use ``tsql -C`` to check the compile-time options (you should see “MARS: yes”).

Be aware that FreeTDS only supports MARS via ODBC. So don’t expect an
SQLAlchemy URL of

.. code-block:: none

    mssql+pymssql://username:password@freetds_name/database_name?charset=utf8

to work. Instead, use

.. code-block:: none

    mssql+pyodbc://username:password@odbc_name/?charset=utf8

If this fails, edit ``/etc/odbc.ini`` to add a logfile, e.g.

.. code-block:: ini

    [crate_sqlserver_odbc]
    description = "CRATE test SQL Server database on Wombat VMXP"
    driver = FreeTDS
    ; this is looked up in /etc/odbcinst.ini
    TDS_Version = 7.4
    ; see http://www.freetds.org/userguide/choosingtdsprotocol.htm
    server = 192.168.1.13
    port = 1433
    Database = crate_test_src
    MARS_Connection = Yes
    DumpFile = /tmp/freedump.log

to check the actual FreeTDS software version and TDS protocol version being
used; the lines are near the top and look like

.. code-block:: none

    log.c:196:Starting log file for FreeTDS 0.91
                                            ^^^ bad; need higher FreeTDS version
    net.c:207:Connecting to 192.168.1.13 port 1433 (TDS version 7.1)
                                                                ^^^ bad; need TDS 7.2

Note that a TDS_Version of “8.0” in ``/etc/odbc.ini`` will be converted to
“7.1”; if you specify a version that exceeds your SQL Server (e.g. specify
“7.4” when you’re running SQL Server 2005) it will fall back to 4.2; and **you
need 7.2 or higher** for MARS.

In this case, the problem was the ``TDS_Version = 7.4`` (should have been 7.2,
for a SQL Server 2005 backend), and the ``driver = FreeTDS`` referring to an
installation of FreeTDS 0.91. Here’s a working version:

.. code-block:: ini

    # /etc/odbcinst.ini

	[FreeTDS_v1_1]
    Description = FreeTDS 1.1 (SQL Server protocol driver for Unix)
    Driver = /usr/local/lib/libtdsodbc.so

.. code-block:: ini

    # /etc/odbc.ini

    [crate_sqlserver_odbc]
    description = "CRATE test SQL Server database on Wombat VMXP"
    driver = FreeTDS_v1_1
    TDS_Version = 7.2
    server = 192.168.1.13
    port = 1433
    Database = crate_test_src
    MARS_Connection = Yes
    DumpFile = /tmp/freedump.log
    ; remove this line after testing!

This worked.


===============================================================================

.. rubric:: Footnotes

.. [#notbakedin]
    Django supports several databases but doesn’t ship with the required
    interfaces, except for SQLite support, which is part of the Python standard
    library (https://docs.djangoproject.com/en/1.9/ref/databases). The same is
    true of SQLAlchemy
    (http://docs.sqlalchemy.org/en/rel_1_0/core/engines.html), and of the
    old custom ``rnc_db`` library.

.. [#djangorecommendedmysql]
    https://docs.djangoproject.com/en/1.9/ref/databases/

.. [#mysqldbnotpython3]
    April 2016: https://pypi.python.org/pypi/MySQL-python/1.2.4.
    June 2018: Python 3 still unsupported:
    https://pypi.org/project/MySQL-python/.

.. [#gpldebate]
    For debate on the law about bundling GPL code with software with less
    copyleft licences, see http://opensource.stackexchange.com/questions/2139;
    http://opensource.stackexchange.com/questions/1640

.. [#mysqlcfast]
    http://techspot.zzzeek.org/2015/02/15/asynchronous-python-and-databases/

.. [#mysqlconnectorslow]
    http://charlesnagy.info/it/python/python-mysqldb-vs-mysql-connector-query-performance

.. [#djangopyodbcazuremethod]
    https://pypi.python.org/pypi/django-pyodbc. When things go wrong... insert
    print() statements into
    sqlalchemy/engine/default.py:DefaultDialect.connect(), if SQLAlchemy is
    working, and into
    sql_server/pyodbc/base.py:DatabaseWrapper.get_new_connection(), if Django
    isn’t. Then use: import pyodbc; connstr = “something”; conn =
    pyodbc.connect(connstr). Then fiddle until it works. Then back-translate to
    the Django interface. For ODBC connection string details for SQL Server
    Native Client, see https://msdn.microsoft.com/en-us/library/ms130822.aspx.
