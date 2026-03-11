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
--------------------


A tool to match people from two databases that don't share a person-unique
identifier, using information from names, dates of birth, sex/gender, and
address information. This is a probability-based ("fuzzy") matching technique.
It can operate using either identifiable information or in de-identified
fashion.

You will need to download a CSV file of postcode geography from UK Census/ONS
data from e.g. https://geoportal.statistics.gov.uk/search?q=PRD_ONSPD%20NOV_2024
and place it somewhere accessible to CRATE. If you are running CRATE under
Docker this needs to be under the ``files`` directory, which is under the top
level directory of the CRATE installation.


Example
~~~~~~~

In an area with a population size of 100,000:

Institution A has a database with the following patient record table:

.. csv-table::
   :file: fuzzy_linkage_example_patient.csv
   :header-rows: 1
   :class: compact-table

Institution B has a database with the following student record table:

.. csv-table::
   :file: fuzzy_linkage_example_student.csv
   :header-rows: 1
   :class: compact-table

There are no NHS numbers in the student table so we rely on name, date of birth,
gender and postcode to link the two tables.

The database manager at institution A creates a CSV file called
``patients_for_hashing.csv`` like this:

.. literalinclude:: patients_for_hashing.csv
    :language: none

If you are running CRATE under Docker, you must place this file under the ``files``
directory under the top level directory of the CRATE installation. The Docker
container sees this as ``/crate/files``.

The database manager then runs the following script in CRATE:

.. code-block:: bash

    # If using the Docker-based CRATE installer (from the scripts directory)
    ./fuzzy_id_match_hash.sh --population_size=100000 --input /crate/files/patients_for_hashing.csv --key mysecretpassphrase --output /crate/files/hashed_patients.jsonl --postcode_csv_filename=/crate/files/ONSPD_NOV_2024_UK.csv

    # otherwise
    crate_fuzzy_id_match hash --population_size=100000 --input patients_for_hashing.csv --key mysecretpassphrase --output hashed_patients.jsonl --postcode_csv_filename=ONSPD_NOV_2024_UK.csv

This will write a file in JSON Lines format ``hashed_patients.jsonl``. This is
sent, along with the hash key to the database manager at Institution B.

The database manager at institution B creates a CSV file called
``students_for_hashing.csv`` like this:

.. literalinclude:: students_for_hashing.csv
    :language: none


They then run the following script in their CRATE installation:

.. code-block:: bash

    # If using the Docker-based CRATE installer (from the scripts directory)
    ./fuzzy_id_match_compare_hashed_to_plaintext.sh --probands /crate/files/hashed_patients.jsonl --sample /crate/files/students_for_hashing.csv --sample_cache /crate/files/sample_cache.jsonl --output /crate/files/sample_comparison.csv --key mysecretpassphrase --population_size=100000 --postcode_csv_filename=/crate/files/ONSPD_NOV_2024_UK.csv

    # otherwise
    crate_fuzzy_id_match compare_hashed_to_plaintext --probands hashed_patients.jsonl --sample students_for_hashing.csv  --output sample_comparison.csv --key mysecretpassphrase --population_size=100000 --postcode_csv_filename=ONSPD_NOV_2024_UK.csv

This produces the following output ``sample_comparison.csv``:

.. csv-table::
   :file:  sample_comparison.csv
   :header-rows: 1
   :class: compact-table

As you can see from this short example, CRATE has matched the records from the
two tables with the IDs shown in the ``proband_local_id`` and
``sample_match_local_id`` columns. Typically the local IDs would be hashed as
well (with the ``--local_id_hash_key`` option) but for this example we have
left them unmodified for easier identification.

Now the two institutions are able to link records between their databases and
can share de-identified data with each other.

We describe this tool in:

- Cardinal RN, Moore A, Burchell M, Lewis JR (2023).
  De-identified Bayesian personal identity matching for privacy-preserving
  record linkage despite errors: development and validation.
  *BMC Medical Informatics and Decision Making* 23: 85.
  `PubMed ID 37147600 <http://www.pubmed.gov/37147600>`__;
  `DOI 10.1186/s12911-023-02176-6 <https://doi.org/10.1186/s12911-023-02176-6>`__;
  `PDF <https://bmcmedinformdecismak.biomedcentral.com/counter/pdf/10.1186/s12911-023-02176-6.pdf>`__.

.. literalinclude:: _crate_fuzzy_id_match_help.txt
    :language: none

Name frequency data is pre-supplied. It was generated like this:

.. literalinclude:: fetch_name_frequencies.sh
    :language: bash
