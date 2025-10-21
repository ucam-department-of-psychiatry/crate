..  docs/source/administrator/introduction.rst

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

Prerequisites
=============

..  contents::
    :local:
    :depth: 3

System specification
--------------------

Any contemporary desktop or laptop computer is capable of running CRATE. The
specification of the hardware really depends on:

- the number of records in your database.
- which functions of CRATE you are using.
- how quickly and how often you wish to run the various CRATE functions.

CRATE does not need to run on the computer where your databases are hosted,
provided it has access to the databases over the network.

We recommend using the Docker-based CRATE installer, which should run on any
modern Linux distribution. CRATE is mostly developed and tested with Ubuntu
Linux so if you are agnostic about the choice of operating system then a recent
Ubuntu LTS version would be a good choice. The CRATE installer will also run on
Windows Sub-system for Linux 2 (WSL2) with Docker Desktop, though we would not
recommend its use in a multi-user production environment as Docker Desktop and
ssh services are tied to a single user's account.

If your database administrator and/or researchers are more used to a Windows
desktop environmment, one approach is to have CRATE running on a Linux
distribution under Docker and a separate Windows machine (Desktop with remote
access) hosting the databases and researchers' workspaces. The researchers would
not normally access the CRATE server itself but they would need access to the
databases with the anonymised / NLPed data. The CRATE administrators can then
log in from the Windows side with PuTTY or OpenSSH.

It is helpful to have some kind of spreadsheet application to edit CRATE's data
dictionaries used for anonymisation and a desktop text editor to edit the
various scripts and configuration files. You can achieve this with a single
Linux desktop server or take a hybrid Windows/Linux approach as described above.

It is also possible to run CRATE on any platform without the Docker-based
installer, though you will need to install a lot of the build tools and
components required by CRATE separately. See :ref:`Versions of software etc. used by CRATE <versions_of_software_etc_used_by_crate>`.

.. _data_and_database_prerequisites:

Data and database prerequisites
-------------------------------

Unless you are just evaluating CRATE and wish the installer to create
demonstration databases for you, you will need either to create or point CRATE
to the following databases:

Source database(s)
~~~~~~~~~~~~~~~~~~

- There should be a database-wide integer patient ID field, present in every
  table (or view, if you need to add it) containing patient-identifiable data.
  Tables should have an index on this field, for speed.

- For non-patient tables, it is usually faster to have an integer primary key
  (PK) (particularly in a multiprocessing environment, where CRATE divides up
  the work in part by PK). However, this is not obligatory.

**Summary:** all tables should be indexed on an integer PK. All patient tables
should also be indexed on an integer patient number.

If you are working with a RiO database, the preprocessor will do this for you.
See below.

Destination database(s)
~~~~~~~~~~~~~~~~~~~~~~~

You are likely to want one destination database for every set of source
databases that share the same PID. So, for example (EMR = electronic medical
record):

=========================== ======================= =========== ======================
Source database             PID                     MPID        Destination database
=========================== ======================= =========== ======================
Brand X EMR                 Brand X number          NHS number  Destination database A
Legacy hospital system 1    Trust ‘M’ number        NHS number  Destination database B
Legacy hospital system 2    Trust ‘M’ number        NHS number  Destination database B
Brand Y IAPT EMR            IAPT reference number   NHS number  Destination database C
=========================== ======================= =========== ======================

CRATE will create the contents for you; you just need to create the database,
and tell the CRATE installer about it.

You will be able to link records later from databases A–C in this example using
the MRID (= hashed NHS number in this example).


Secret administrative database(s)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You will need one secret administrative database for every destination
database. This will store information like the PID-to-RID mapping, the
MPID-to-MRID mapping, and state information to make incremental updates faster.

Web site administrative database
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You will need a database (and it’s probably easiest to have it separate) to store
secret administrative information for the CRATE web application. You can
optionally have the CRATE installer create a MySQL database running in a Docker
container for this purpose

File system prerequisites
-------------------------

The CRATE installer needs access to a file system, which is writeable by the
user running the installer. The installer will download the CRATE source code
into this file system. It will also create the CRATE configuration and copy the
various helper scripts for running CRATE commands into this file system. By
default the file hierarchy looks like this:

::

    crate
    ├── bioyodie_resources
    ├── config
    ├── files
    ├── scripts
    ├── src
    ├── static
    └── venv

- ``bioyodie_resources`` contains preprocessed UMLS data for the Bio-YODIE NLP tool
- ``config`` contains the configuration files for the various CRATE tools
- ``files`` contains miscellaneous files generated by the CRATE tools such as log files
- ``scripts`` contains various Bash scripts for running CRATE commands
- ``src`` contains a git checkout of the CRATE source code
- ``static`` contains statically served files for the CRATE web application
- ``venv`` contains the Python virtual environment used by the installer


List of domains that the CRATE installer will need to access
------------------------------------------------------------

If you are installing CRATE behind a firewall that restricts access to the
internet, you will need to ensure the following domains are allowed. This list is
correct as of May 2023 and is likely to change over time:

- \*.debian.org
- \*.docker.com
- \*.docker.io
- \*.github.com
- \*.githubusercontent.com
- \*.maven.org
- \*.pypi.org
- \*.pythonhosted.org
- \*.ubuntu.com
