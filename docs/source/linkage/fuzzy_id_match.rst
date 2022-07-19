..  crate_anon/docs/source/linkage/fuzzy_id_match.rst

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


.. _crate_fuzzy_id_match:

crate_fuzzy_id_match
~~~~~~~~~~~~~~~~~~~~

A tool to match people from two databases that don't share a person-unique
identifier, using information from names, dates of birth, sex/gender, and
address information. This is a probability-based ("fuzzy") matching technique.
It can operate using either identifiable information or in de-identified
fashion.

**In development.**
**More detail will follow then the validation paper is published.**

.. todo:: fuzzy_id_match: expand on method

.. todo:: fuzzy_id_match: cite paper when published

.. literalinclude:: _crate_fuzzy_id_match_help.txt
    :language: none
