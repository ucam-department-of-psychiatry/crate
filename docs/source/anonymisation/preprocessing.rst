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

..  literalinclude:: crate_preprocess_rio_help.txt
    :language: none


crate_preprocess_pcmis
~~~~~~~~~~~~~~~~~~~~~~

Options as of 2018-06-10:

..  literalinclude:: crate_preprocess_pcmis_help.txt
    :language: none

