..  crate_anon/docs/source/anonymisation/data_prerequisites.rst

..  Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).
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


Data and database prerequisites
-------------------------------

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
and tell CRATE about it via an SQLAlchemy URL.

You will be able to link records later from databases A–C in this example using
the MRID (= hashed NHS number in this example).


Secret administrative database(s)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You will need one secret administrative database for every destination
database. This will store information like the PID-to-RID mapping, the
MPID-to-MRID mapping, and state information to make incremental updates faster.

Web site administrative database
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

You’ll need a database (and it’s probably easiest to have it separate) to store
secret administrative information for the CRATE web front end.
