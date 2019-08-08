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

.. _ONS: https://www.ons.gov.uk/
.. _PCMIS: https://www.york.ac.uk/healthsciences/pc-mis/
.. _RiO: https://www.servelec.co.uk/product-range/rio-epr-system/


Preprocessing tools
-------------------

These tools:

- reshape specific databases for CRATE:

  - crate_preprocess_rio_ -- preprocess a RiO_ database
  - crate_preprocess_pcmis_ -- preprocess a PCMIS_ database

- fetch external data used for anonymisation:

  - crate_postcodes_ -- fetch ONS_ postcode information
  - crate_fetch_wordlists_ -- fetch forenames, surnames, and medical eponyms

- perform fuzzy identity matching for linking different databases securely:

  - crate_fuzzy_id_match_

Although they are usually run before anonymisation, it's probably more helpful
to read the :ref:`Anonymisation <anonymisation>` section first.


.. _crate_preprocess_rio:

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

==================== =======================
``_Resp_Clinician_`` … Responsible Clinician
==================== =======================

Options:

..  literalinclude:: crate_preprocess_rio_help.txt
    :language: none


.. _crate_preprocess_pcmis:

crate_preprocess_pcmis
~~~~~~~~~~~~~~~~~~~~~~

Options:

..  literalinclude:: crate_preprocess_pcmis_help.txt
    :language: none


.. _crate_postcodes:

crate_postcodes
~~~~~~~~~~~~~~~

Options:

..  literalinclude:: crate_postcodes_help.txt
    :language: none


.. _crate_fetch_wordlists:

crate_fetch_wordlists
~~~~~~~~~~~~~~~~~~~~~

This tool assists in fetching common word lists, such as name lists for global
blacklisting, and words to exclude from such lists (such as English words or
medical eponyms). It also provides an exclusion filter system, to find lines in
some files that are absent from others.

Options:

..  literalinclude:: crate_fetch_wordlists_help.txt
    :language: none

Specimen usage:

..  literalinclude:: crate_fetch_wordlists_specimen_usage.sh
    :language: bash


.. _crate_fuzzy_id_match:

crate_fuzzy_id_match
~~~~~~~~~~~~~~~~~~~~

**In development.**

See :mod:`crate_anon.preprocess.fuzzy_id_match`.

Options (from ``crate_fuzzy_id_match --allhelp``):

..  literalinclude:: crate_fuzzy_id_match_help.txt
    :language: none
