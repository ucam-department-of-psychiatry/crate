.. crate_anon/docs/source/anonymisation/preprocessing.rst

..  Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).
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

Preprocessing tools
-------------------

These tools reshape specific databases for CRATE.

crate_preprocess_rio
~~~~~~~~~~~~~~~~~~~~

The RiO preprocessor creates a unique integer field named `crate_pk` in all
tables (copying the existing integer PK, creating one from an existing
non-integer primary key, or adding a new one using SQL Server’s `INT
IDENTITY(1, 1)` type. For all patient tables, it makes the patient ID (RiO
number) into an integer, called `crate_rio_number`. It then adds *indexes* and
*views*. All of these can be removed again, or updated incrementally if you add
new data.

The views ‘denormalize’ the data for convenience, since it can be pretty hard
to follow the key chain of fully normalized tables. The views conform mostly to
the names used by the Servelec RiO CRIS Extraction Program (RCEP), with added
consistency. Because user lookups are common, to save typing (and in some cases
keep the field length below the 64-character column name limit of MySQL), the
following abbreviations are used:

=================== =======================
_Resp_Clinician_	… Responsible Clinician
=================== =======================

Options as of 2017-02-28:

.. code-block:: none

    usage: crate_preprocess_rio [-h] --url URL [-v] [--print] [--echo] [--rcep]
                                [--drop-danger-drop] [--cpft] [--debug-skiptables]
                                [--prognotes-current-only | --prognotes-all]
                                [--clindocs-current-only | --clindocs-all]
                                [--allergies-current-only | --allergies-all]
                                [--audit-info | --no-audit-info]
                                [--postcodedb POSTCODEDB]
                                [--geogcols [GEOGCOLS [GEOGCOLS ...]]]
                                [--settings-filename SETTINGS_FILENAME]

    *   Alters a RiO database to be suitable for CRATE.

    *   By default, this treats the source database as being a copy of a RiO
        database (slightly later than version 6.2; exact version unclear).
        Use the "--rcep" (+/- "--cpft") switch(es) to treat it as a
        Servelec RiO CRIS Extract Program (RCEP) v2 output database.


    optional arguments:
      -h, --help            show this help message and exit
      --url URL             SQLAlchemy database URL
      -v, --verbose         Verbose
      --print               Print SQL but do not execute it. (You can redirect the
                            printed output to create an SQL script.
      --echo                Echo SQL
      --rcep                Treat the source database as the product of Servelec's
                            RiO CRIS Extract Program v2 (instead of raw RiO)
      --drop-danger-drop    REMOVES new columns and indexes, rather than creating
                            them. (There's not very much danger; no real
                            information is lost, but it might take a while to
                            recalculate it.)
      --cpft                Apply hacks for Cambridgeshire & Peterborough NHS
                            Foundation Trust (CPFT) RCEP database. Only appicable
                            with --rcep
      --debug-skiptables    DEBUG-ONLY OPTION. Skip tables (view creation only)
      --prognotes-current-only
                            Progress_Notes view restricted to current versions
                            only (* default)
      --prognotes-all       Progress_Notes view shows old versions too
      --clindocs-current-only
                            Clinical_Documents view restricted to current versions
                            only (*)
      --clindocs-all        Clinical_Documents view shows old versions too
      --allergies-current-only
                            Client_Allergies view restricted to current info only
      --allergies-all       Client_Allergies view shows deleted allergies too (*)
      --audit-info          Audit information (creation/update times) added to
                            views
      --no-audit-info       No audit information added (*)
      --postcodedb POSTCODEDB
                            Specify database (schema) name for ONS Postcode
                            Database (as imported by CRATE) to link to addresses
                            as a view. With SQL Server, you will have to specify
                            the schema as well as the database; e.g. "--postcodedb
                            ONS_PD.dbo"
      --geogcols [GEOGCOLS [GEOGCOLS ...]]
                            List of geographical information columns to link in
                            from ONS Postcode Database. BEWARE that you do not
                            specify anything too identifying. Default: pcon pct
                            nuts lea statsward casward lsoa01 msoa01 ur01ind oac01
                            lsoa11 msoa11 parish bua11 buasd11 ru11ind oac11 imd
      --settings-filename SETTINGS_FILENAME
                            Specify filename to write draft ddgen_* settings to,
                            for use in a CRATE anonymiser configuration file.



crate_preprocess_pcmis
~~~~~~~~~~~~~~~~~~~~~~

Options as of 2018-06-10:

.. code-block:: none

    usage: crate_preprocess_pcmis [-h] --url URL [-v] [--print] [--echo]
                                  [--drop-danger-drop] [--debug-skiptables]
                                  [--postcodedb POSTCODEDB]
                                  [--geogcols [GEOGCOLS [GEOGCOLS ...]]]
                                  [--settings-filename SETTINGS_FILENAME]

    Alters a PCMIS database to be suitable for CRATE.

    optional arguments:
      -h, --help            show this help message and exit
      --url URL             SQLAlchemy database URL
      -v, --verbose         Verbose
      --print               Print SQL but do not execute it. (You can redirect the
                            printed output to create an SQL script.
      --echo                Echo SQL
      --drop-danger-drop    REMOVES new columns and indexes, rather than creating
                            them. (There's not very much danger; no real
                            information is lost, but it might take a while to
                            recalculate it.)
      --debug-skiptables    DEBUG-ONLY OPTION. Skip tables (view creation only)
      --postcodedb POSTCODEDB
                            Specify database (schema) name for ONS Postcode
                            Database (as imported by CRATE) to link to addresses
                            as a view. With SQL Server, you will have to specify
                            the schema as well as the database; e.g. "--postcodedb
                            ONS_PD.dbo"
      --geogcols [GEOGCOLS [GEOGCOLS ...]]
                            List of geographical information columns to link in
                            from ONS Postcode Database. BEWARE that you do not
                            specify anything too identifying. Default: pcon pct
                            nuts lea statsward casward lsoa01 msoa01 ur01ind oac01
                            lsoa11 msoa11 parish bua11 buasd11 ru11ind oac11 imd
      --settings-filename SETTINGS_FILENAME
                            Specify filename to write draft ddgen_* settings to,
                            for use in a CRATE anonymiser configuration file.
