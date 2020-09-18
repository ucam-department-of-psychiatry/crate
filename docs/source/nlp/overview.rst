..  crate_anon/docs/source/nlp/overview.rst

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

Overview of NLP
---------------

The purpose of NLP is to start with **free text** that a human wrote and end up
with **structured data** that a machine can deal with.

CRATE provides a high-level NLP management system. It churns through databases
(typically, databases that have already been de-identified by CRATE's
:ref:`anonymisation <anonymisation>` system) and sends text to one or more
**NLP processors**. It takes the results and stashes them in an NLP **output
database**.

NLP processors can be disparate. For example, CRATE has support for:

- built-in :ref:`Python NLP via regular expressions <regex_nlp>`;

- all sorts of tools that use :ref:`GATE <gate_nlp>`;

- other third-party tools like :ref:`MedEx-UIMA <medex_nlp>`.


.. _standard_nlp_output_columns:

Standard NLP output columns
~~~~~~~~~~~~~~~~~~~~~~~~~~~

All CRATE NLP processors use the following output columns:

=================== =============== ===========================================
Column              SQL type        Description
=================== =============== ===========================================
_pk                 BIGINT          Arbitrary PK of output record

_nlpdef             VARCHAR(64)     Name of the NLP definition producing this
                                    row

_srcdb              VARCHAR(64)     Source database name (from CRATE NLP
                                    config)

_srctable           VARCHAR(64)     Source table name

_srcpkfield         VARCHAR(64)     PK field (column) name in source table

_srcpkval           BIGINT          PK of source record (or integer hash of PK
                                    if the PK is a string)

_srcpkstr           VARCHAR(64)     NULL if the table has an integer PK, but
                                    the PK itself if the PK was a string, to
                                    deal with hash collisions.

_srcfield           VARCHAR(64)     Field (column) name of source text

_srcdatetimefield   DATETIME        Field (column) name containing the source
                                    date/time. (Added in v0.18.52.)

_srcdatetimeval     DATETIME        Date/time of the source field.
                                    (Added in v0.18.52.)

_crate_version      VARCHAR(147)    Version of CRATE that generated this NLP
                                    record, in semantic version form.
                                    (Added in v0.18.53.)

_when_fetched_utc   DATETIME        Date/time (in UTC) that the NLP processor
                                    fetched the record from the source
                                    database. (Added in v0.18.53.)
=================== =============== ===========================================

The length of the VARCHAR fields that refer to relational database entity names
is set by the `MAX_SQL_FIELD_LEN` constant.

These default output columns are prefixed with an underscore to reduce the
risk of name clashes (for example, with :ref:`GATE NLP applications <gate_nlp>`
that can themselves generate arbitrary column names). Columns beginning with an
underscore are a nuisance for R, though; one has to refer to them in data
tables as e.g. ``dt$`_myfield``` rather than ``dt$myfield``.
