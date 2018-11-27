.. crate_anon/docs/source/misc/faq_troubleshooting.rst

..  Copyright (C) 2015-2018 Rudolf Cardinal (rudolf@pobox.com).
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

.. _AMQP: https://en.wikipedia.org/wiki/Advanced_Message_Queuing_Protocol
.. _Celery: http://www.celeryproject.org/
.. _RabbitMQ: https://www.rabbitmq.com/

FAQs and troubleshooting
========================

.. contents::
   :local:

Known bugs elsewhere affecting CRATE
------------------------------------

- wkhtmltopdf font size bug

  - See notes next to PATIENT_FONTSIZE in config/settings.py
  - https://github.com/wkhtmltopdf/wkhtmltopdf/issues/2505

- If you try to use django-debug-toolbar when proxying via a Unix domain
  socket, you need to use a custom INTERNAL_IPS setting; see the specimen
  config file.

- SQL Server returns a rowcount of -1; this is normal.
  See https://code.google.com/p/pyodbc/wiki/Cursor.


General
-------

ImportError: No module named ‘{mysqldb, pyodbc, ...}’
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You haven’t installed the right drivers for the database URL(s) that you have
specified in your CRATE configuration file. Make sure the virtualenv is
activated (see :ref:`Activating your virtual environment <activate_venv>`), and
then install it (see :ref:`Database drivers <database_drivers>`).


Which Python modules should be installed?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``pip freeze`` to show what you have installed. For a Windows installation
using SQL Server, the list below works. The ones you have to install manually
are marked with ``# MANUAL``; CRATE installs the others.

.. code-block:: none

    amqp==2.1.3
    appdirs==1.4.0
    arrow==0.10.0
    Babel==2.3.4
    beautifulsoup4==4.5.3
    billiard==3.5.0.2
    cardinal-pythonlib==0.2.13
    celery==4.0.1
    chardet==3.0.2
    cheroot==5.1.0
    CherryPy==10.0.0
    colorama==0.3.7
    colorlog==2.10.0
    crate-anon==0.18.32
    distro==1.0.2
    Django==1.10.5
    django-debug-toolbar==1.6
    django-extensions==1.7.6
    django-picklefield==0.3.2
    django-pyodbc-azure==1.10.4.0  # MANUAL: for Django to talk to SQL Server
    django-sslserver==0.19
    et-xmlfile==1.0.1
    flower==0.9.1
    gunicorn==19.6.0
    jdcal==1.3
    kombu==4.0.1
    mmh3==2.3.1  # MANUAL: to speed up hashing
    openpyxl==2.4.2
    packaging==16.8
    pdfkit==0.6.1
    portend==1.8
    prettytable==0.7.2
    psutil==5.0.1
    Pygments==2.2.0
    pyhashxx==0.1.3
    pyodbc==4.0.3  # MANUAL: for ODBC database connections
    pyparsing==2.1.10
    PyPDF2==1.26.0
    pypiwin32==219
    python-dateutil==2.6.0
    pytz==2016.10
    regex==2017.1.17
    semver==2.7.5
    six==1.10.0
    sortedcontainers==1.5.7
    SQLAlchemy==1.1.5
    sqlparse==0.2.2
    tempora==1.6.1
    tornado==4.2
    typing==3.5.3.0
    vine==1.1.3
    Werkzeug==0.11.15
    xlrd==1.0.0



Pretty colours all gone (anonymiser, NLP, etc.)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

That’s what happens when you pipe the tool through ``tee``.


CRATE anonymiser
----------------

Anonymisation is slow
~~~~~~~~~~~~~~~~~~~~~

Make sure you have indexes created on all patient_id fields, because the tool
will use this to find (a) values for scrubbing, and (b) records for
anonymisation. Indexing here makes a huge difference!


CRATE uses lots of memory
~~~~~~~~~~~~~~~~~~~~~~~~~

A normal run should see CRATE using roughly 60–80 Mb per process. Values much
in excess of this likely relate to the text extraction process, which uses
third-party software over which CRATE has no control (I’ve seen >1 Gb)
[#debugginghighmemusage]_.

“File is not a zip file”
~~~~~~~~~~~~~~~~~~~~~~~~

In full: “Caught exception from document_to_text: File is not a zip file” when
extracting text from DOCX documents

This error usually appears with encrypted, password-protected DOCX files. The
anonymiser will not be able to read these, and this error can be ignored.

“UnRtf: … has stopped working”
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If a third-party program is used by CRATE for text extraction and fails, you
may get lots of messages from Windows like “UnRtf: convert document in RTF
format to other formats has stopped working. Windows can check online for a
solution to the problem...”

To disable this in Windows Server 2008, run the Server Manager, and in the main
page scroll down to a section titled Resources and Support. There should be a
“Windows Error Reporting” section. It’s probably set to “Ask me about sending
reports every time an error occurs”; change this to “I don’t want to
participate, and don’t ask me again”.

That gets rid of the options to tell Microsoft, but it still pops up some
“close or debug?” dialog boxes. To fix that, add the following registry
entries [#disabledebugcloseapplication]_:

.. code-block:: registry

    HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\Windows Error Reporting : “ForceQueue”=dword:00000000
    HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\Windows Error Reporting : “DontShowUI”=dword:00000001
    HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\Windows Error Reporting : “DontSendAdditionalData”=dword:00000001
    HKEY_LOCAL_MACHINE\SOFTWARE\Microsoft\Windows\Windows Error Reporting\Consent : “DefaultConsent”=dword:00000002

CRATE NLP
---------

How can I update a source file in KConnect/Bio-YODIE
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Example: replacing `plugins/Tagger_ConText/src/gate/context/ContextFeaturesTagger.java`.

- Make sure Apache Ant is installed [#installapacheant]_.

- Replace the source file.

- Delete the existing `.jar` file.

- Run ``ant build``.

- If it fails, check the `build.properties` file, which contains local
  variables such as directories (e.g. `gate.home`); edit this and try again.


CRATE web site
--------------

crate_launch_cherrypy_server can’t find its config files
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use forward slashes (``/``) rather than backslashes (``\``) for filename paths
in the environment variable `CRATE_CHERRYPY_ARGS` (e.g.
``C:/somepath/somefile.ext``) or escape the backslashes by doubling them (e.g.
``C:\\somepath\\somefile.ext``).

Port 443 not free on ‘127.0.0.1’
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Problem: Under Windows Server: `OSError(“Port 443 not free on ‘127.0.0.1’”)`

If you launch the CRATE web server on port 443 (for HTTPS) and get this error,
something else is probably using port 443. If that’s unexpected to you, it’s
because Microsoft uses it by default [#win443unavailable]_. Try:

.. code-block:: bat

    netstat -ban

to see what’s using it. In our case we had this:

.. code-block:: none

     Proto  Local Address      Foreign Address    State
    ...
    [svchost.exe]
     TCP    0.0.0.0:443        0.0.0.0            LISTENING
    ...
    [svchost.exe]
     TCP    [::]:443           [::]:0             LISTENING

That is, svchost.exe is using port 443. One question now is: which actual
program is using this port via svchost.exe (which is a service host program
that does all sorts of things) [#svchost]_? A possibility relates to VMWare
[#vmware443]_.

If you have sufficient control over your machine to wrest port 443 away from
whatever’s using it, fine. Otherwise, you may need to use an alternative port.
A common choice might be 8443 [#port8443]_.

“Your connection is not private...” browser error
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You will always get this error until you get a proper HTTPS certificate. This
error occurs when you self-sign a certificate. Browers will offer you a way
round, usually in small print [e.g. in Chrome: :menuselection:`Advanced -->
Proceed... (unsafe)`].

403 Forbidden: CSRF verification failed
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There are at least two possible reasons:

- Your browser must enable cookies, at least for ‘same-origin’ requests; this
  is a critical part of CRATE’s security to prevent cross-site request
  forgeries. If you’re using Firefox, try Chrome [#csrffirefox]_.

- By default, the CRATE web site uses only HTTPS (secure HTTP). This is
  governed by the `CRATE_HTTPS` parameter in CRATE’s own
  `crateweb/config/settings.py`. When `CRATE_HTTPS` is `True`, then CSRF
  cookies are only permitted over HTTPS, so if you use plain HTTP, you will see
  this error. A quick hack is to set ``CRATE_HTTPS = False`` in your local
  settings, but this is a bad idea; set up HTTPS properly instead, as above.

"Unknown, invalid, or unsupported option... in a getsockopt or setsockopt call"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Problem: the front end might produce the error: “An unknown, invalid, or
unsupported option or level was specified in a getsockopt or setsockopt call”
while initiating a back-end task.

This is due to a bug in the Python AMQP_ package version 2.1.4 [#amqp214bug]_.
(AMQP is a protocol used by Celery_ to talk to a message broker such as
RabbitMQ_; CRATE uses Celery to manage its back-end asynchronous tasks, like
sending e-mails.)

Solution: downgrade AMQP. From the activated CRATE virtual environment:

.. code-block:: bash

    pip uninstall amqp
    pip install -Iv amqp==2.1.3

This change has been hardcoded into CRATE’s setup scripts to prevent Celery
from picking the buggy version of the Python `amqp` package. As a consequence,
other requirements are also downgraded (`celery` to 4.0.1; `kombu` to 4.0.1).

Static files not served via CherryPy
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Problem: Static files are not served (e.g. broken icons rather than plus/minus
symbols; broken-looking admin site) when using the CherryPy server for CRATE.

Solution: You should specify either (1) ``FORCE_SCRIPT_NAME = "/crate"`` in
your config file, or (2) ``--root_path /crate`` in your `CRATE_CHERRYPY_ARGS`
environment variable. (The default value for the latter is taken from the
former.)

The cause of the problem is as follows: if you don’t do this, then
`https://mysite/` is meant to be your site, while
`https://mysite/crate_static/` is meant to be your static root. However, the
latter comes under the former, so Django says “it’s for me” then “it doesn’t
exist”. If you use `https://mysite/crate/` as your site root, with
`https://mysite/crate_static/` as your static root, then the software is happy.


I can’t restart the CRATE Windows Service cleanly
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There may be a problem whereby the CRATE web service doesn’t entirely shut down
when its service is stopped. You can manually kill leftover processes (which
will appear as `python.exe` or `python.exe *32`) using taskmgr.

This should be fixed now.


CRATE service doesn't start... errors in Windows Event Log
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If your CRATE service doesn't start and you see this error in the Event
Log:

.. code-block:: none

    Unable to read Server Queue performance data from the Server service.
    The first four bytes (DWORD) of the Data section contains the status
    code, the second four bytes contains the IOSB.Status and the next four
    bytes contains the IOSB.Information.

    Log Name: Application
    Source: PerfNet
    Event ID: 2006

then consider first if this might be a bug relating to HP ProLiant servers. See
https://support.hpe.com/hpsc/doc/public/display?docId=emr_na-a00041653en_us&docLocale=en_US
and a fix at
https://support.microsoft.com/en-in/help/4057142/windows-10-update-kb4057142.
However, that is for Windows Server 2016.

    The CPFT server from Dec 2016 is an HP ProLiant DL360 Gen9 server with 2 ×
    12-core/24-thread Intel Xeon E5-2687WV4 3 GHz CPUs (48 effective CPUs),
    with 96 Gb RAM later upgraded to 672 Gb RAM (in 2018), and 11.5 Tb SSD
    storage in a RAID configuration (8.9 Tb available); it was about £15k inc.
    VAT initially plus £8k for the extra RAM. It runs Windows Server 2008 R2.

Other possible problems:

- https://support.microsoft.com/en-my/help/2607486/windows-server-2008-r2-reports-perfnet-error-in-application-log-on-mac
  ... but that relates to machines with >64 processors;

- https://support.microsoft.com/en-us/help/2279566/32-bit-application-cannot-query-performance-server-work-queues-counter
  ... that's more likely since it relates to machines with >32 processors,
  and in turn this suggests that a 32-bit application is having trouble.
  However, we have 64-bit Python installed.

- As it turned out, s per the :ref:`CRATE Windows service <windows_service>`
  help, we try ``crate_windows_service``, and it reported that the
  ``servicemanager`` module was missing; that'd explain it! The virtual
  environment had got messed up.

So the general rescue method:

- remove the old virtual environment
- recreate the virtual environment and reinstall, e.g.

    .. code-block:: none

        cd \srv\crate
        "\Program Files\Python35\python.exe" -m venv crate_virtualenv
        crate_virtualenv\Scripts\activate.bat
        pip install crate_anon==0.18.51 pyodbc django-pyodbc-azure

- remove and reinstall the CRATE service, using an Administrator command
  prompt:

    .. code-block:: none

        crate_windows_service remove

    ... reboot...

    .. code-block:: none

        crate_windows_service install


“No connection could be made because the target machine actively refused it”
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Problem: From the front end, you see: “No connection could be made because the
target machine actively refused it”.

Check that RabbitMQ is running. Check also CRATE’s Celery log. If RabbitMQ is
not running, you’ll see something like this in CRATE’s Celery log, giving a
little more detail:

.. code-block:: none

    [2017-02-25 23:50:11,433: Error/MainProcess] consumer: Cannot connect to
    amqp://guest:**@127.0.0.1:5672//: [WinError 10061] No connection could be
    made because the target machine actively refused it.

This indicates that Celery (called by CRATE) is looking for RabbitMQ on port
5672, finding it, but being refused access. Make sure RabbitMQ is installed and
its service started. Run ``rabbitmqctl``, which on Windows machines is typically
typically at

.. code-block:: none

    C:\Program Files\RabbitMQ Server\rabbitmq_server-3.6.6\sbin\rabbitmqctl.bat

Specifically, run:

.. code-block:: bash

    rabbitmqctl status

If you see this unhappy output:

.. code-block:: none

    Status of node 'rabbit@cpft-crate-p01' ...
    Error: unable to connect to node 'rabbit@cpft-crate-p01': nodedown

    DIAGNOSTICS
    ===========

    attempted to contact: ['rabbit@cpft-crate-p01']

    rabbit@cpft-crate-p01:
      * connected to epmd (port 4369) on cpft-crate-p01
      * epmd reports: node 'rabbit' not running at all
                      other nodes on cpft-crate-p01: ['RabbitMQ']
      * suggestion: start the node

    current node details:
    - node name: 'rabbitmq-cli-11@cpft-crate-p01'
    - home dir: P:\
    - cookie hash: <...some hash...>

... then one possibility is that RabbitMQ was improperly installed. This can
happen if installed by a non-administrative user [#rabbitmqwinquirks]_, or if
your Windows variables `HOMEDRIVE` and `HOMESHARE` are pointing to a network
drive [#homedrivehomeshare]_. From an **administrative** command prompt, this
was one solution:

.. code-block:: bat

    REM Remove the old installation:
    net stop rabbitmq
    “C:\Program Files\RabbitMQ Server\uninstall.exe”

    REM Set environment variables for the new installation:
    SET HOMEDRIVE=C:\
    SET HOMESHARE=C:\Users
    SET ERLANG_HOME=C:\Program Files\erl8.2

    REM Now reinstall:
    C:\some_download_dir\rabbitmq-server-3.6.6.exe
    REM ... and watch the detailed output closely to make sure there are no errors

    C:\Program Files\RabbitMQ Server\rabbitmq_server_3.6.6\sbin\rabbitmqctl.bat status

Here’s some happy output:

.. code-block:: none

    Status of node 'rabbit@cpft-crate-p01' ...
    [{pid,55372},
     {running_applications,[{rabbit,"RabbitMQ","3.6.6"},
                            {rabbit_common,[],"3.6.6"},
                            {mnesia,"MNESIA  CXC 138 12","4.14.2"},
                            {ranch,"Socket acceptor pool for TCP protocols.",
                                   "1.2.1"},
                            {xmerl,"XML parser","1.3.12"},
                            {os_mon,"CPO  CXC 138 46","2.4.1"},
                            {sasl,"SASL  CXC 138 11","3.0.2"},
                            {stdlib,"ERTS  CXC 138 10","3.2"},
                            {kernel,"ERTS  CXC 138 10","5.1.1"}]},
     {os,{win32,nt}},
     {erlang_version,"Erlang/OTP 19 [erts-8.2] [64-bit] [smp:24:24] [async-threads:64]\n"},
     {memory,[{total,63923600},
              {connection_readers,0},
              {connection_writers,0},
              {connection_channels,0},
              {connection_other,0},
              {queue_procs,2736},
              {queue_slave_procs,0},
              {plugins,0},
              {other_proc,23674272},
              {mnesia,61784},
              {mgmt_db,0},
              {msg_index,42592},
              {other_ets,1003792},
              {binary,22848},
              {code,17795673},
              {atom,752561},
              {other_system,20567342}]},
     {alarms,[]},

    {listeners,[{clustering,25672,"::"},{amqp,5672,"::"},{amqp,5672,"0.0.0.0"}]},
     {vm_memory_high_watermark,0.4},
     {vm_memory_limit,41174066790},
     {disk_free_limit,50000000},
     {disk_free,8951801614336},
     {file_descriptors,[{total_limit,8092},
                        {total_used,2},
                        {sockets_limit,7280},
                        {sockets_used,0}]},
     {processes,[{limit,1048576},{used,179}]},
     {run_queue,0},
     {uptime,28},
     {kernel,{net_ticktime,60}}]

If you see something like that, all should be well.


MySQL
-----

Can’t connect to MySQL, even manually
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

See https://dev.mysql.com/doc/refman/5.5/en/problems-connecting.html.

How do I reconfigure MySQL?
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Edit the MySQL configuration file.

- Under Ubuntu Linux this is usually `/etc/mysql/my.cnf`.

- Under Windows it can be in several locations [#mysqlcfglocation]_. If you’re
  not sure where yours is, find `mysqld` (typically ``C:\Program
  Files\MySQL\MySQL Server 5.7\bin\mysqld.exe``) and run ``mysqld --verbose
  --help > helpoutput.txt`` and inspect the resulting file `helpoutput.txt`
  (which is quite long). There’ll be a pair of lines like:

  .. code-block:: none

    Default options are read from the following files in the given order:
    C:\Windows\my.ini C:\Windows\my.cnf C:\my.ini C:\my.cnf C:\Program
    Files\MySQL\MySQL Server 5.7\my.ini C:\Program Files\MySQL\MySQL Server
    5.7\my.cnf

- Note that on our main test system (Windows Server 2008 R2, MySQL 5.7) the
  only file existing was ``C:\ProgramData\MySQL\MySQL Server 5.7\my.ini``, but
  this was busy being ignored when mysqld was run manually (see below for why –
  it can be specified directly as an argument to the Windows service, so a
  manual call to ``mysqld`` doesn’t see the same file, which is confusing).

- For running MySQL systems, you can also view the configuration filename via
  MySQL Workbench (under Server Status), but what you see here can be wrong.
  For example, we’ve had it showing ``C:\Program Files\MySQL\MySQL Server
  5.0\my.ini``, when there was no such directory (we were using MySQL 5.7), and
  the actual file was ``C:\my.ini``.

Restart MySQL.

- Under Ubuntu Linux, use ``sudo service mysql restart``.

- Under Windows, restart the MySQL service in the Services tool (it’s typically
  called e.g. `MySQL57`).

If MySQL fails to restart, run the ``mysqld`` program manually so you can see
why.

- If it sits there appearing to do nothing, it’s probably happy; check the log
  files, on Windows usually called `HOSTNAME.err` in the database data
  directory (where *HOSTNAME* is the name of your computer).

- You can run ``mysqld --console --standalone --log-error-verbosity 3`` to get
  it to write to the console. These options also allow you to abort it with
  CTRL-C.

- Under Ubuntu, precede that with ``sudo -u mysql bash`` to get a shell running
  as the `mysql` user.

- You might also try ``mysqld --print-defaults`` to see its options.

- Under Ubuntu, try also ``journalctl -xe | grep -i mysql | less`` (sometimes
  `apparmor` will block access to MySQL files, if you’ve moved them from their
  default location, which can be very confusing; in this case, you’ll need to
  edit `/etc/apparmor.d/usr.sbin.mysqld` or
  `/etc/apparmor.d/local/usr.sbin.mysqld`).

If the Windows service is stuck in the ‘starting’ state, for example after
you’ve reconfigured MySQL:

- To kill a dead/stuck service: (1) Check the service short name by
  double-clicking it in Services. Let’s support it’s `MySQL57`. (2) ``sc
  queryex MySQL57`` to see its process ID or PID. (3) ``taskkill /f /pid
  PIDNUM`` (where *PIDNUM* is the process ID from the previous step).

- Inspect the Properties of the malfunctioning service carefully. These include
  a “path to executable” option, which can look like this: ``"C:\Program
  Files\MySQL\MySQL Server 5.7\bin\mysqld.exe"
  --defaults-file="C:\ProgramData\MySQL\MySQL Server 5.7\my.ini" MySQL57``. This
  gives you the service name and also the hidden configuration path!

- To reinstall the service: ``mysqld --install`` [#mysqlinstallwinservice]_.
  The default service name is ‘MySQL’, but you can override this. You’re
  probably best being explicit, like this: ``mysqld --install MySQL57
  --defaults-file="C:\my.ini"``

- After creating a service, start it manually; if it fails, check
  :menuselection:`Event Viewer --> Windows Logs --> Application`.

- If MySQL fails to start and you see errors like `The innodb_system data file
  ‘ibdata1’ must be writable`, the first thing to check is that another copy of
  `mysqld` is not already running.

- To delete a defunct service: ``sc delete servicename``. Exercise extreme
  caution with this!

Your target is a happy MySQL installation that restarts automatically when you
reboot.

Table names are always lower case using MySQL under Windows
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Under Windows, MySQL converts table names to lower case by default (but is
happy with mixed-case column names, and is happy with table and column names
being mixed case under Linux). This is because of the default setting for
``lower_case_table_names`` in `my.ini` or `my.cnf`. In turn, this is because
Windows can use a case-insensitive file system (and since tables can be stored
by the name, this would result in an almighty mess) [#mysqlidcasesens]_.
However, when using NTFS, Windows filenames are case-sensitive
[#ntfscasesens]_. Therefore, under Windows with NTFS, you have more options for
``lower_case_table_names``. Note, however, that it also affects the
case-sensitivity of table names using SQL (but not of column names). So you’re
probably better off always using ``lower_case_table_names = 1``, as per the
MySQL advice. This is the default behaviour under Windows.

“Got a packet bigger than ‘max_allowed_packet’ bytes” or “MySQL has gone away”
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Problem: `sqlalchem.exc.OperationalError:
(mysql.connector.errors.OperationalError)... Got a packet bigger than
‘max_allowed_packet’ bytes` *or* `MySQL has gone away` when sending large
packets.

Using large “chunks” is efficient but you have to configure MySQL to allow it.
The ``max_allowed_packet`` setting in the MySQL configuration file (see above)
governs this. Try changing the default, e.g. from

.. code-block:: none

    max_allowed_packet=4M  # too small!

to

.. code-block:: none

    max_allowed_packet=40M

and restart MySQL (as above). You can also view current settings using MySQL
Workbench (:menuselection:`Management --> Status and System Variables -->
System Variables`; search for ``max_allowed_packet``).

If you can’t get this working, reduce the ``--chunksize`` parameter to the
CRATE anonymiser.

How do I hot-swap two MySQL databases?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Since anonymisation is slow, you may want a live research database and another
that you can update offline. When you're ready to swap, you'll want to

- create DEFUNCT
- rename LIVE -> DEFUNCT
- rename OFFLINE -> LIVE

then either revert:

- rename LIVE -> OFFLINE
- rename DEFUNCT -> LIVE

or commit:

- drop DEFUNCT

How?

- http://stackoverflow.com/questions/67093/how-do-i-quickly-rename-a-mysql-database-change-schema-name
- https://gist.github.com/michaelmior/1173781

"MySQL server has gone away"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

One possibility is that you are processing a big binary field, and MySQL's
``max_allowed_packet`` parameter is too small. Try increasing it (e.g. from 16M
to 32M). See also
https://egret.psychol.cam.ac.uk/camcops/documentation/server/server_troubleshooting.html?highlight=max_allowed_packet#mysql-server-has-gone-away


How to convert a database from SQL Server to MySQL?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This facility is provided by MySQL Workbench, which will connect to an SQL
Server instance. Use the "ODBC via connection string" option if other methods
aren't working: ``DSN=XXX;UID=YYY;PWD=ZZZ``.

If the schema definitions are not seen, it's a permissions issue
(http://stackoverflow.com/questions/17038716), in which case you can also copy
copy the database using CRATE's anonymiser, treating all tables as non-patient
tables (i.e. doing no actual anonymisation).


What settings do I need in /etc/mysql/my.cnf?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Probably these:

    .. code-block:: ini

        [mysqld]
        max_allowed_packet = 32M

        innodb_strict_mode = 1
        innodb_file_per_table = 1
        innodb_file_format = Barracuda

        # Only for MySQL prior to 5.7.5 (http://dev.mysql.com/doc/relnotes/mysql/5.6/en/news-5-6-20.html):
        innodb_log_file_size = 320M

        # For more performance, less safety:
        innodb_flush_log_at_trx_commit = 2

        # To save memory?
        # Default is 8; suggestion is ncores * 2
        # innodb_thread_concurrency = ...

        [mysqldump]
        max_allowed_packet = 32M

"_mysql_exceptions.OperationalError: (1118, 'Row size too large (> 8126)"
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In full, the error is:

    .. code-block:: none

        _mysql_exceptions.OperationalError: (1118, 'Row size too large (> 8126).
        Changing some columns to TEXT or BLOB or using ROW_FORMAT=DYNAMIC or
        ROW_FORMAT=COMPRESSED may help. In current row format, BLOB prefix of 768
        bytes is stored inline.')

See above. If you need to change the log file size, FOLLOW THIS PROCEDURE:
https://dev.mysql.com/doc/refman/5.0/en/innodb-data-log-reconfiguration.html


"Segmentation fault (core dumped)..."
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This error can be seen when using the Microsoft ODBC driver for Linux, which is
buggy. In this situation, use the Microsoft JDBC driver instead.


"Killed."
~~~~~~~~~

You may be out of memory, on a small computer. Try reducing MySQL's memory
footprint. (Steps have already been taken to reduce memory usage by the
anonymiser itself.)

Can't create FULLTEXT index(es)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

MySQL v5.6 is required to use FULLTEXT indexes with InnoDB tables (as opposed
to MyISAM tables, which don't support transactions).

On Ubuntu 14.04, the default MySQL version is 5.5, so use:

    .. code-block:: bash

        sudo apt-get install mysql-server-5.6 mysql-server-core-5.6 \
            mysql-client-5.6 mysql-client-core-5.6


How to search with FULLTEXT indexes?
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In conventional SQL, you would use:

.. code-block:: none

    ... WHERE field LIKE '%word%'

In a field having a MySQL FULLTEXT index, you can use:

.. code-block:: none

    ... WHERE MATCH(field) AGAINST ('word')

There are several variants. See
https://dev.mysql.com/doc/refman/5.0/en/fulltext-search.html


SQL Server
----------

[…] “Connection is busy with results for another command” […]
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you see this with Microsoft SQL Server via ODBC/pyodbc, you need to enable
Multiple Active Result Sets (MARS), because for some reason Microsoft think
it’s unusual to want more than one cursor open (more than one simultaneous
query) to a single database at once. There are several ways:

**Windows**

- (DOESN’T WORK.) Append ``;MultipleActiveResultSets=True`` to the connection
  URL, e.g. ``mssql+pyodbc://@MYDSN;MultipleActiveResultSets=True``. However,
  although this is documented [#enablingmars]_, it didn’t work via pyodbc
  [#enablingmarsmethodfailed]_!

- (WORKS.) Run the command: ``odbcconf /a {CONFIGSYSDSN "SQL Server Native Client
  11.0" "DSN=MY_DSN|MARS_Connection=Yes"}`` (replacing the driver and DSN names
  with your own). You can re-run the ODBC configuration wizard, and it should
  now say `Multiple Active Result Sets(MARS): YES` where it said `... NO`
  before. This does work. Use ``CONFIGDSN`` instead of ``CONFIGSYSDSN`` if you
  are using a user DSN. Your changes should be visible if you restart the ODBC
  control panel (e.g. with ``odbccp32.cpl``) and go through the configuration
  wizard again; the MARS option (which you can’t edit) should have changed from
  “No” to “Yes”.

- There’s also a registry hack [#marsregistry]_.

**Linux**

- Under Linux, in ``/etc/odbc.ini``, for that DSN, set
  ``MARS_Connection = yes``. See

    - https://msdn.microsoft.com/en-us/library/cfa084cz(v=vs.110).aspx
    - https://msdn.microsoft.com/en-us/library/h32h3abf(v=vs.110).aspx
    - Rationale: We use gen_patient_ids() to iterate through patients, but then
      we fetch data for that patient via the same connection to the source
      database(s). Therefore, we're operating multiple result sets through one
      connection.


"The data types nvarchar(max) and ntext are incompatible..."
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Problem: Using SQL Server, you get an error from the CRATE web front end saying
“The data types nvarchar(max) and ntext are incompatible in the equal to
operator.”

Solution: Upgrade pyodbc.

(This error occurs with pyodbc 3.1.1 but not with pyodbc 4.0.3, for example.)
The error relates to pyodbc passing text parameters to SQL Server as NTEXT
rather than NVARCHAR(MAX).


"A default full-text catalog does not exist in database..."
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Problem: Using SQL Server: “A default full-text catalog does not exist in database ‘XXX’ or user does not have permission to perform this action.”

Assuming the user does have permission, this means **you need to run this SQL
beforehand:**

.. code-block:: sql

    USE mydatabase;
    CREATE FULLTEXT CATALOG default_fulltext_catalog AS DEFAULT;

See https://technet.microsoft.com/en-us/library/dd283095(v=sql.100).aspx.


New tables are named like mydb.[SERVERNAME\USERNAME].mytable
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Problem: Under SQL Server, new tables (e.g. from NLP) look like
`mydatabase.[SERVERNAME\USERNAME].tablename` rather than
`mydatabase.dbo.tablename`.

Under Microsoft SQL Server, the standard full notation for a table is
`database.schema.table`. The default schema is often `dbo`, so tables look like
`mydatabase.dbo.mytable`. However [#sqlserverschemas]_:

    The default schema for a user can be defined by using the
    ``DEFAULT_SCHEMA`` option of ``CREATE USER`` or ``ALTER USER``. If no
    default schema is defined for a user account, SQL Server will assume
    ``dbo`` is the default schema. **It is important [to] note that if the user
    is authenticated by SQL Server as a member of a group in the Windows
    operating system, no default schema will be associated with the user. If
    the user creates an object, a new schema will be created and named the same
    as the user, and the object will be associated with that user schema.**

So, for example, if your username is `RCardinal` and you authenticate to SQL
Server via Windows authentication, and then create a table, it is likely to be
called something like ``[mydatabase].[myserver\RCardinal].[mytable]``. You can
try this:

.. code-block:: none

    USE mydatabase;
    SELECT name, type_desc, default_schema_name FROM sys.database_principals;

    USE mydatabase;
    ALTER USER [myserver\RCardinal] WITH DEFAULT_SCHEMA = dbo;


Windows
-------

Control Panel looks blank in Windows 2008 Server
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This isn’t a CRATE problem. However, it’s something we encountered as a problem
when using CRATE. If your Control Panel looks blank, (1) run ``gpedit.msc``
(Local Group Policy Editor), then :menuselection:`User Configuration -->
Administrative Templates --> Control Panel`. Check the settings there.

When that doesn’t work, I’m a bit stuck; try running ``.cpl`` items from the
command line instead.

MedEx-UIMA
----------

MedEx-UIMA gives Java errors
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Yes. Frankly, it’s just fairly badly written, from a programmer’s perspective.
I’ve fixed a few of its bugs in a nasty patch-based way; see
``build_medex_itself.py``. MedEx takes the approach of allowing bugs to throw
exceptions, catching its own exceptions, printing the stack trace, and carrying
on regardless; this can be off-putting, but I’ve not bothered to fix all its
bugs. CRATE will abort if any exceptions make it out of MedEx, but you can just
ignore ones that you see. Here are a couple I fixed:

.. code-block:: none

    Exception in thread "main" java.lang.StringIndexOutOfBoundsException: String index out of range: 2
        at java.lang.String.charAt(Unknown Source)
        at org.apache.NLPTools.Document.<init>(Document.java:134)
        at org.apache.medex.MedTagger.run_batch_medtag(MedTagger.java:256)
        at CrateMedexPipeline.processInput(CrateMedexPipeline.java:302)
        at CrateMedexPipeline.<init>(CrateMedexPipeline.java:128)
        at CrateMedexPipeline.main(CrateMedexPipeline.java:320)

.. code-block:: none

    java.lang.StringIndexOutOfBoundsException: String index out of range: 1
        at java.lang.String.charAt(Unknown Source)
        at org.apache.algorithms.SuffixArray.construct_tree_word(SuffixArray.java:375)
        at org.apache.algorithms.SuffixArray.re_build(SuffixArray.java:97)
        at org.apache.algorithms.SuffixArray.<init>(SuffixArray.java:60)
        at org.apache.medex.MedTagger.medtagging(MedTagger.java:359)
        at org.apache.medex.MedTagger.run_batch_medtag(MedTagger.java:264)
        at CrateMedexPipeline.processInput(CrateMedexPipeline.java:302)
        at CrateMedexPipeline.<init>(CrateMedexPipeline.java:128)
        at CrateMedexPipeline.main(CrateMedexPipeline.java:320)

(the first being an example of using & when they meant && in a logic test).
Here are a couple of MedEx bugs I haven’t fixed, so you might see them:

.. code-block:: none

    java.lang.ArrayIndexOutOfBoundsException: -1
        at java.util.Vector.elementData(Unknown Source)
        at java.util.Vector.get(Unknown Source)
        at org.apache.NLPTools.SentenceBoundary.detect_boundaries(SentenceBoundary.java:329)
        at org.apache.medex.MedTagger.medtagging(MedTagger.java:354)
        at org.apache.medex.MedTagger.run_batch_medtag(MedTagger.java:264)
        at CrateMedexPipeline.processInput(CrateMedexPipeline.java:312)
        at CrateMedexPipeline.runPipeline(CrateMedexPipeline.java:138)
        at CrateMedexPipeline.<init>(CrateMedexPipeline.java:112)
        at CrateMedexPipeline.main(CrateMedexPipeline.java:330)

.. code-block:: none

    java.lang.NullPointerException
        at org.apache.algorithms.SuffixArray.search(SuffixArray.java:636)
        at org.apache.medex.MedTagger.medtagging(MedTagger.java:362)
        at org.apache.medex.MedTagger.run_batch_medtag(MedTagger.java:264)
        at CrateMedexPipeline.processInput(CrateMedexPipeline.java:312)
        at CrateMedexPipeline.runPipeline(CrateMedexPipeline.java:138)
        at CrateMedexPipeline.<init>(CrateMedexPipeline.java:112)
        at CrateMedexPipeline.main(CrateMedexPipeline.java:330)

.. code-block:: none

    java.lang.NullPointerException


CRATE reports an encoding error when talking to MedEx
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You have probably missed out the ``-Dfile.encoding=UTF-8`` setting for Java in
your config file; see the example.



.. rubric:: Footnotes

.. [#debugginghighmemusage]
    For tracking it down:
    https://www.huyng.com/posts/python-performance-analysis;
    http://chase-seibert.github.io/blog/2013/08/03/diagnosing-memory-leaks-python.html

.. [#disabledebugcloseapplication]
    http://stackoverflow.com/questions/396369/how-do-i-disable-the-debug-close-application-dialog-on-windows-vista;
    https://msdn.microsoft.com/en-us/library/windows/desktop/bb513638(v=vs.85).aspx;
    http://stackoverflow.com/questions/3561545/how-to-terminate-a-program-when-it-crashes-which-should-just-fail-a-unit-test/3637710#3637710

.. [#installapacheant]
    Apache Ant uses `build.xml` files to build Java `.jar` files from Java
    `.java` source files. From https://ant.apache.org, menuselection:`Download
    --> Binary distributions`, fetch `apache-ant-1.10.1.zip` or similar, and
    unzip it (e.g. to ``C:\Program Files``). Set the `JAVA_HOME` environment
    variable to the Java JDK root directory. Set the `ANT_HOME` environment
    variable to the Apache Ant root directory.

.. [#amqp214bug]
    https://github.com/celery/py-amqp/issues/135;
    http://stackoverflow.com/questions/41775353;
    https://github.com/celery/py-amqp/issues/130

.. [#mysqlidcasesens]
    http://dev.mysql.com/doc/refman/5.7/en/identifier-case-sensitivity.html

.. [#ntfscasesens]
    https://support.microsoft.com/en-us/kb/100625

.. [#csrffirefox]
    Or maybe see http://superuser.com/questions/461608

.. [#enablingmars]
    https://msdn.microsoft.com/en-us/library/h32h3abf(v=vs.110).aspx

.. [#enablingmarsmethodfailed]
    Connection string emitted by SQLAlchemy (found by placing a trace within
    `sqlalchemy.engine.default.DefaultDialect.connect`):
    ``dsn=MY_DSN;MultipleActiveResultSets=True;Trusted_Connection=Yes``.

.. [#marsregistry]
    http://serverfault.com/questions/302169

.. [#mysqlcfglocation]
    http://dev.mysql.com/doc/refman/5.7/en/option-files.html

.. [#mysqlinstallwinservice]
    http://dev.mysql.com/doc/refman/5.7/en/windows-start-service.html

.. [#win443unavailable]
    https://helpdesk.stone-ware.com/portal/helpcenter/articles/port-443-80-not-available-on-windows-server

.. [#svchost]
    https://en.wikipedia.org/wiki/Svchost.exe

.. [#vmware443]
    http://superuser.com/questions/125455/why-is-the-system-process-listening-on-port-443

.. [#port8443]
    http://www.speedguide.net/port.php?port=8443

.. [#sqlserverschemas]
    https://technet.microsoft.com/en-us/library/dd283095(v=sql.100).aspx

.. [#rabbitmqwinquirks]
    https://www.rabbitmq.com/windows-quirks.html

.. [#homedrivehomeshare]
    https://github.com/rabbitmq/rabbitmq-server/issues/625