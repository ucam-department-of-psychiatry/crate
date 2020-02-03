.. crate_anon/docs/source/linkage/index.rst

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


Linkage tools
=============

..  toctree::
    :maxdepth: 2

    crate_bulk_hash.rst


Linkage is about joining two databases together using common keys or
identifiers. In the context of de-identified clinical records linkage, it is
often desirable to link without using any identity information.

One way to do so is to "pseudonymise" both databases, creating a research ID
(pseudonym, tag) from an identifier (such as an NHS number in the UK). A common
operation is for institution A to say to institution B: "please send me
de-identified data for the following people". If the two institutions share a
common passphrase (secret key), they can both "hash" their identifiers in the
same way, and then check for matches using the resulting pseudonyms. This could
work as follows:

- Institutions A and B agree a secret passphrase.
- Institution A hashes the identifiers of relevant people, for whom it would
  like de-identified data from institution B.
- Institution A sends the resulting pseudonyms to institution B.
- Institution B hashes all its identifiers with the same passphrase.
- Institution B looks for pseudonyms that match those requested by A.
- Institution B sends de-identified data for those people (only) back to A.

For example, using the passphrase "tiger" and the HMAC-MD5 algorithm, the
following hashes (expressed as hexadecimal) can be generated consistently:

.. code-block:: none

    Identifier      Hash (research pseudonym)
    ------------------------------------------------
    1234567890      35b102550cd6b3118153d0372dffb0aa
    2345678901      4aa6ca6d046b6fcffd2e465061bf19de
    3456789012      71597eb16547ab2a87bad4139ff73693

The :ref:`crate_bulk_hash <crate_bulk_hash>` tool allows you to generate these
sorts of pseudonyms en masse.


.. todo: add fuzzy_id_match details to linkage docs, once validated
