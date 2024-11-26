..  crate_anon/docs/source/anonymisation/preprocessing.rst

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

.. _ONS: https://www.ons.gov.uk/
.. _PCMIS: https://www.york.ac.uk/healthsciences/pc-mis/
.. _RiO: https://www.servelec.co.uk/product-range/rio-epr-system/
.. _SystmOne: https://tpp-uk.com/products/


Preprocessing tools
-------------------

These tools:

- reshape specific databases for CRATE:

  - crate_preprocess_pcmis_ -- preprocess a PCMIS_ database
  - crate_preprocess_rio_ -- preprocess a RiO_ database
  - crate_preprocess_systmone_ -- index a SystmOne_ database

- fetch external data used for anonymisation:

  - crate_postcodes_ -- fetch ONS_ postcode information
  - crate_fetch_wordlists_ -- fetch forenames, surnames, and medical eponyms

- import tabular data to a database:

  - crate_autoimport_db_ -- import tabular data from files to a database

- perform fuzzy identity matching for linking different databases securely:

  - :ref:`crate_fuzzy_id_match <crate_fuzzy_id_match>`

Although they are usually run before anonymisation, it's probably more helpful
to read the :ref:`Anonymisation <anonymisation>` section first.


.. _crate_preprocess_pcmis:

crate_preprocess_pcmis
~~~~~~~~~~~~~~~~~~~~~~

Options:

..  literalinclude:: _crate_preprocess_pcmis_help.txt
    :language: none


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

..  literalinclude:: _crate_preprocess_rio_help.txt
    :language: none


.. _crate_preprocess_systmone:

crate_preprocess_systmone
~~~~~~~~~~~~~~~~~~~~~~~~~

Preprocess SystmOne_ data, by indexing it. (It shouldn't need further
reshaping.)

Options:

..  literalinclude:: _crate_preprocess_systmone_help.txt
    :language: none


.. _crate_postcodes:

crate_postcodes
~~~~~~~~~~~~~~~

Options:

..  literalinclude:: _crate_postcodes_help.txt
    :language: none


.. _crate_fetch_wordlists:

crate_fetch_wordlists
~~~~~~~~~~~~~~~~~~~~~

This tool assists in fetching common word lists, such as name lists for global
denial, and words to exclude from such lists (such as English words or medical
eponyms). It also provides an exclusion filter system, to find lines in some
files that are absent from others.

The purpose of creating large name lists is usually to remove more names.
However, it's likely that you want to remove medical eponyms, like Parkinson
(for Parkinson's disease). CRATE has a hand-curated list of these. (If a
patient is named Parkinson, though, and CRATE is told to remove that as a
patient-specific identifier, that name will be removed from phrases like
"Parkinson's disease", which may itself be a potential identifying clue,
however, e.g. "[XXX]'s disease", but 100% reliable text de-identification is
impossible.)

The overlap between names and English words is really tricky.

- If you use all names from this set and exclude all valid English words (e.g.
  from a "valid answers in Scrabble or crosswords" list), you will remove from
  the namelist -- and thus NOT remove from text being nonspecifically scrubbed
  -- names such as John (john is a noun) and Veronica (veronica is also a
  noun).

- If you keep all names in the exclusion namelist, though, you will scrub words
  like excellent, fought, friend, games, he, hope, husband, joyful, kitten,
  knuckle, libel, limp, lovely, man, memory, mood, music, no, power, powers,
  sad, stress, true, yes, you, young, zone (to list but a few); these are all
  names.

- A compromise may be to start with all names, remove medical eponyms, and
  remove *common* English words. CRATE provides tools to count words in a
  subset of the Project Gutenberg corpus. For example, removing English words
  that account for the top 99% of this corpus (and are also valid Scrabble
  clues) does this. The process is shown in the specimen usage below.

Options:

..  literalinclude:: _crate_fetch_wordlists_help.txt
    :language: none

Specimen usage:

..  literalinclude:: crate_fetch_wordlists_specimen_usage.sh
    :language: bash


.. _crate_autoimport_db:

crate_autoimport_db
~~~~~~~~~~~~~~~~~~~

This tool reads tabular data from files, which may be the following types:

- CSV (comma-separated value)
- ODS (OpenOffice Spreadsheet)
- TSV (tab-separated value)
- XLSX (Microsoft Excel/OpenXML, Excel 2007+)

or archive files of the following formats containing those files:

- ZIP

It stores the data in a database, via SQLAlchemy.

The filename of each tabular data file is taken to be the name of the
destination table.

Options:

..  literalinclude:: _crate_fetch_wordlists_help.txt
    :language: none
