..  crate_anon/docs/source/anonymisation/anon_specific.rst

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

.. _CRIS: https://pubmed.ncbi.nlm.nih.gov/23842533/
.. _PCMIS: https://www.york.ac.uk/healthsciences/pc-mis/
.. _RiO: https://www.servelec.co.uk/product-range/rio-epr-system/
.. _SystmOne: https://tpp-uk.com/products/


Specific databases
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

.. contents::
   :local:


Servelec RiO
-------------------------------------------------------------------------------

Servelec RiO_ data exports come in several formats, including:

- raw;

- "RCEP": preprocessed by Servelec's RiO CRIS_ Extraction Program.

Individual organizations may process these too. CRATE provides a preprocessor
(:ref:`crate_preprocess_rio <crate_preprocess_rio>`) to convert a RiO database
to a format suitable for anonymisation via CRATE.


PCMIS
-------------------------------------------------------------------------------

There is a specific preprocessing tool for PCMIS_, namely
:ref:`crate_preprocess_pcmis <crate_preprocess_pcmis>`.


TPP SystmOne
-------------------------------------------------------------------------------

TPP provide a "strategic reporting extract" (SRE) containing SystmOne data.
This contains structured data, but can contain free text too.

The structure of the SRE is good from CRATE's perspective; it does not require
reshaping for anonymisation.

One additional view is helpful to add blurred geographical information. Our
team creates a table ``S1_PatientAddress`` from the source table
``SRPatientAddressHistory``, creating also the column ``PostCode_NoSpaces``.
We use
the :ref:`crate_postcodes <crate_postcodes>` tool to import UK Office for
National Statistics geography data into a database named ``onspd``. This view
is then helpful:

.. code-block:: sql

    USE SystmOne;  -- or whatever your identifiable SystmOne database is named
    CREATE VIEW vwS1_PatientAddressWithResearchGeography
    AS (
        SELECT
            -- Original columns:
            A.*,
            -- Geography columns (with nothing too specific):
            P.bua11,
            P.buasd11,
            P.casward,
            P.imd,
            P.lea,
            P.lsoa01,
            P.lsoa11,
            P.msoa01,
            P.msoa11,
            P.nuts,
            P.oac01,
            P.oac11,
            P.parish,
            P.pcon,
            P.pct,
            P.ru11ind,
            P.statsward,
            P.ur01ind
        FROM
            S1_PatientAddress AS A
            INNER JOIN onspd.dbo.postcode AS P
            ON P.pcd_nospace = A.PostCode_NoSpaces
    )

Use the :ref:`crate_anon_draft_dd <crate_anon_draft_dd>` tool to create a data
dictionary from SystmOne_. CRATE knows something about the structure of a
typical SystmOne database.

However, NHS numbers, which are `10-digit integers incorporating a checksum
<https://www.datadictionary.nhs.uk/attributes/nhs_number.html>`_, are
represented in the SRE by the ``VARCHAR(10)`` data type. Therefore, you should
use these lines in your :ref:`anonymiser config file <anon_config_file>`:

.. code-block:: ini

    sqlatype_mpid = String(10)
    #
    # Within CPFT, we have some locally created columns with string versions of
    # the primary SystmOne ID, and so forth, so we use:
    #
    # sqlatype_pid = String(100)
    # sqlatype_mpid = String(100)

For your source database, use these settings:

.. code-block:: ini

    ddgen_omit_by_default = False
    # ... or use "--systemone_include_generic" with crate_anon_draft_dd
    # ... or use True if you want to hand-review everything

    ddgen_per_table_pid_field = IDPatient
    # ... largely cosmetic; improves the warnings if your local database
    # modifications have an odd structure.

See :ref:`sqlatype_mpid <anon_config_sqlatype_mpid>`.
