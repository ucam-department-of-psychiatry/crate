..  crate_anon/docs/source/installation/installation.rst

..  Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).
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
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.


Installing CRATE without Docker
-------------------------------


.. contents::
   :local:


URLs for CRATE source code
~~~~~~~~~~~~~~~~~~~~~~~~~~


- https://github.com/ucam-department-of-psychiatry/crate (for source)
- https://pypi.io/project/crate-anon/ (for ``pip install crate-anon``)


Manual installation
~~~~~~~~~~~~~~~~~~~


Installing CRATE itself is very easy, but you probably want a lot of supporting
tools. Here's a logical sequence.


Python
^^^^^^


Install Python 3.10 or higher. If it's not already installed:

**Linux**

.. code-block:: bash

    sudo apt-get install python3.10-dev

**Windows**

- https://www.python.org/ → Downloads


Python virtual environment and CRATE itself
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


Create a Python virtual environment (an isolated set of Python programs
that won’t interfere with any other Python things) and install CRATE.
Choose your own directory names.

**Linux**

.. code-block:: bash

    python3.10 -m venv ~/venvs/crate
    source ~/venvs/crate/bin/activate
    python -m pip install --upgrade pip
    pip install crate-anon

**Windows**

.. code-block:: bat

    C:\Python39\python.exe -m ensurepip
    C:\Python39\python.exe -m venv C:\venvs\crate
    C:\venvs\crate\Scripts\activate
    C:\Python39\python.exe -m pip install --upgrade pip
    pip install crate-anon


.. _activate_venv:

Activating your virtual environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^


**Every time you want to work within your virtual environment, you should
activate it, by running (Windows) or sourcing (Linux) the ``activate`` script
within it, as above.**

Once activated,

- the PATHs are set up for the programs in the virtual environment;

- when you run Python, you will run the copy in the virtual environment;

- the Python package installation tool, ``pip``, will be the one in the virtual
  environment and will modify the virtual environment (not the whole system).

See:

- https://docs.python.org/3/tutorial/venv.html

- https://realpython.com/python-virtual-environments-a-primer/


RabbitMQ
^^^^^^^^


Install RabbitMQ, required by the CRATE web site.

**Linux**

.. code-block:: bash

    sudo apt-get install rabbitmq
    # Check it's working:
    sudo rabbitmqctl status

**Windows**

- Download/install Erlang from http://www.erlang.org/downloads. The 32-bit
  Windows download (Erlang/OTP 18.3) does not work on Windows XP, so everything
  that follows has been tested on Windows 10, 64-bit.

- Download/install RabbitMQ from https://www.rabbitmq.com/ → Download. (If you
  use the default installer, it will find Erlang automatically.)

- Check it’s working: :menuselection:`Start --> RabbitMQ Server --> RabbitMQ
  Command Prompt (sbin dir)`. Then type ``rabbitmqctl status``. It’s helpful to
  do this, because you need to tell Windows to allow the various bits of
  RabbitMQ/Erlang to communicate over internal networks, and (under Windows 10)
  this triggers the appropriate prompts.

- For additional RabbitMQ help see
  https://cmatskas.com/getting-started-with-rabbitmq-on-windows/.


Java
^^^^


Install a Java development kit, to compile support for GATE natural language
processing (NLP).

**Linux**

- Usually built in.

**Windows**

- Download/run the Java Development Kit installer from Oracle.


GATE
^^^^


Install GATE, for NLP.

- Download and install GATE from https://gate.ac.uk/download/


.. _third_party_text_extractors:

Third-party text extractors
^^^^^^^^^^^^^^^^^^^^^^^^^^^


Ensure any necessary third-party text extractor tools are installed and on the
PATH.

Good extractors are built into CRATE for:

- Office Open XML (DOCX, DOCM), for Microsoft Word 2007 onwards;

- HTM(L), XML;

- Open Document text format (ODT), for OpenOffice/LibreOffice;

- plain text (LOG, TXT).

For some, there is a fallback converter built in, but third-party tools are
faster:

- PDF: speed improves by installing ``pdftotext`` [#pdftotext]_

- Rich Text Format (RTF): speed improves by installing ``unrtf`` [#unrtf]_

For some, you will need an external tool:

- For Microsoft Word 97–2003 binary (DOC) files, you will need ``antiword``
  [#antiword]_

- As a fallback tool (“extract text from anything”), CRATE will use ``strings``
  or ``strings2`` [#strings]_, whichever it finds first.

If you install any manually, check they run, as follows.

To check that your text extractors are available and visible to CRATE via the
``PATH``, you can use the :ref:`crate_anon_check_text_extractor
<crate_anon_check_text_extractor>` tool.


C/C++ compiler
^^^^^^^^^^^^^^


.. note::
    This is optional. If you want to install C-based Python libraries, you’ll
    need a C/C++ compiler.

**Linux**

Built in.

**Windows**

Install Visual C++ 14.x [#vs2015]_ (or later?), the official compiler for
Python 3.10-3.11 under Windows [#pythonvstudio]_. Visual Studio Community is
free [#vscommunity]_.


Database and database drivers
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


You'll want drivers for at least one database. See :ref:`Recommended database
drivers <recommended_database_drivers>`.

In the CPFT NHS environment, we use SQL Server and these:

    .. code-block:: none

        pip install pyodbc django-pyodbc-azure


Build the CRATE Java NLP interfaces
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


.. code-block:: bash

    crate_nlp_build_gate_java_interface --help
    crate_nlp_build_gate_java_interface --javac JAVA_COMPILER_FILENAME --gatedir GATE_DIRECTORY

For example, on Windows:

.. code-block:: bat

    crate_nlp_build_gate_java_interface ^
        --javac "C:\Program Files\Java\jdk1.8.0_91\bin\javac.exe" ^
        --gatedir "C:\Program Files\GATE_Developer_8.1"

Once built, you can run the script again with an additional ``--launch``
parameter to launch the GATE framework in an interactive demonstration mode
(using GATE’s supplied “people and places” app).


Configure CRATE for your system
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


The anonymiser and NLP manager are run on an ad-hoc or regularly scheduled
basis, and do not need to be kept running continuously.

For the anonymiser, you will need a .INI-style configuration file (see
:ref:`the anonymiser config file <anon_config_file>` that the
`CRATE_ANON_CONFIG` environment variable points to when the anonymiser is run
(and a .TSV format data dictionary that the configuration file points to -- see
:ref:`data dictionary <data_dictionary>`).

For the NLP manager, you will need another .INI-style configuration file (see
:ref:`NLP config file <nlp_config>`) that the `CRATE_NLP_CONFIG` environment
variable points to when the NLP manager is run.

For the web service, which you will want to run continuously, you will need a
Python (Django) configuration file (see :ref:`web config file
<web_config_file>`) that the `CRATE_WEB_LOCAL_SETTINGS` environment variable
points to when the web server processes are run. Use
``crate_print_demo_crateweb_config`` to make a new one, and edit it for your
own settings.


Set up the web site infrastructure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


Create the database yourself using your normal database management tool. Make
sure that the config file pointed to by the `CRATE_WEB_LOCAL_SETTINGS`
environment variable is set up to point to the database. From the activated
Python virtual environment, you want to build the admin database, collect
static files, populate relevant parts of the database, and create a superuser:

.. code-block:: bash

    crate_django_manage migrate
    crate_django_manage collectstatic
    crate_django_manage populate
    crate_django_manage createsuperuser


Test the web server and message queue
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


In two separate command windows, with the virtual environment activated in
each, run the following two programs:

.. code-block:: bash

    crate_launch_cherrypy_server

.. code-block:: bash

    crate_launch_celery --debug

Browse to the web site. Choose ‘Test message queue by sending an e-mail to the
RDBM’. If an e-mail arrives, that’s good. If you can’t see the web site,
there’s a configuration problem. If you can see the web site but no e-mail
arrives, check:

- that e-mail server and the RDBM e-mail destination are correctly configured
  in the Django config file (as per the `CRATE_WEB_LOCAL_SETTINGS` environment
  variable);

- check the Django log;

- check the Celery log;

- from the RabbitMQ administrative command prompt, run ``rabbitmqctl
  list_queues name messages consumers``; this shows each queue’s name along
  with the number of messages in the queue and the number of consumers. If the
  number of messages is stuck at >0, they’re not being consumed properly.

- run ``crate_launch_flower`` and browse to http://localhost:5555/ to explore
  the messaging system.


Configure the CRATE web service to run automatically
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


CRATE's web service has two parts: the web site itself runs Django, and the
offline message handling part (e.g. to send emails) runs Celery.

**Linux**

Try to avoid managing this by hand! That’s what the `.deb` file is there for.

**Windows: service method**

Using a privileged command prompt [e.g. on Windows 10: :menuselection:`Winkey+X
--> Command Prompt (Admin)`], activate the virtual environment and install
the service:

.. code-block:: bat

    C:\venvs\crate\Scripts\activate
    crate_windows_service install

Set the following system (not user!) environment variables (if you can’t find
the Environment Variables part of Control Panel, use the command
``sysdm.cpl``):

- `CRATE_ANON_CONFIG` – to your main database’s CRATE anonymisation config file

- `CRATE_CHERRYPY_ARGS` – e.g. to ``--port 8999 --root_path /`` (for relevant
  options, see ``crate_django_manage runcpserver --help``)

- `CRATE_WEB_LOCAL_SETTINGS` – to your Django site-specific Python
  configuration file.

- `CRATE_WINSERVICE_LOGDIR` – to a writable directory.

In older versions of Windows you had to reboot or the service manager wouldn’t
see it, but Windows 10 seems to cope happily. You can start the CRATE service
manually, or configure it to start automatically on boot, with the Automatic or
Automatic (Delayed Start) option [#servicedelayedstart]_, or (with the virtual
environment activated) with ``crate_windows_service start``. Any messages will
appear in the Windows ‘Application’ event log.

**Windows: task scheduler method**

In principle you could also run the scripts via the Windows Task Scheduler,
rather than as a service [#taskscheduler]_, e.g. with tasks like

.. code-block:: bat

    cmd /c C:\venvs\crate\Scripts\crate_launch_cherrypy_server >>C:\crate_logs\djangolog.txt 2>&1

.. code-block:: bat

    cmd /c C:\venvs\crate\Scripts\crate_launch_celery >>C:\crate_logs\celerylog.txt 2>&1

… but I’ve not bothered to test this, as the Service method works fine.


Retest the web server and message queue
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


Going to a “behind-the-scenes” (service) mode of operation has the potential to
go wrong, so retest that the web server and the e-mail transmission task work.


===============================================================================

.. rubric:: Footnotes

.. [#servicedelayedstart]
    https://stackoverflow.com/questions/11015189/automatic-vs-automatic-delayed-start

.. [#taskscheduler]
    See
    https://www.calazan.com/windows-tip-run-applications-in-the-background-using-task-scheduler/

.. [#pdftotext]
    ``pdftotext``: Ubuntu: ``sudo apt-get install poppler-utils``.
    Windows: see http://blog.alivate.com.au/poppler-windows/, then install it
    and add it to the PATH.

.. [#unrtf]
    ``unrtf``: Ubuntu: ``sudo apt-get install unrtf``.
    Windows: see http://gnuwin32.sourceforge.net/packages/unrtf.htm, then
    install it and add it to the PATH.

.. [#antiword]
    ``antiword``: Ubuntu: ``sudo apt-get install antiword``.
    Windows: see http://www.winfield.demon.nl/, then install it and add it to
    the PATH.

.. [#strings]
     ``strings`` and ``strings2``: ``strings`` is part of Linux by default;
     for Windows, see
     https://technet.microsoft.com/en-us/sysinternals/strings.aspx or
     http://split-code.com/strings2.html (then install it and add it to the
     PATH.

.. [#vs2010]
    Visual Studio 2010; VC++ 10.0; MSC_VER=1600

.. [#vs2015]
    Visual Studio 2015; VC++ 14.0; MSC_VER=1900

.. [#pythonvstudio]
    See https://wiki.python.org/moin/WindowsCompilers

.. [#vstudiogeneral]
    To map Visual C++/Studio versions to compiler numbers, see
    https://stackoverflow.com/questions/2676763. For more detail see
    https://stackoverflow.com/questions/2817869.


.. [#vscommunity]
    https://visualstudio.microsoft.com/vs/community/
