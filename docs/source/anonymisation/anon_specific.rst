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
++++++++++++++++++


Servelec RiO
------------

Servelec RiO_ data exports come in several formats, including:

- raw;

- "RCEP": preprocessed by Servelec's RiO CRIS_ Extraction Program.

Individual organizations may process these too. CRATE provides a preprocessor
(:ref:`crate_preprocess_rio <crate_preprocess_rio>`) to convert a RiO database
to a format suitable for anonymisation via CRATE.


PCMIS
-----

There is a specific preprocessing tool for PCMIS_, namely
:ref:`crate_preprocess_pcmis <crate_preprocess_pcmis>`.


TPP SystmOne
------------

TPP provide a "strategic reporting extract" (SRE) containing SystmOne data.
This contains structured data, but can contain free text too.

The structure of the SRE is good from CRATE's perspective; it does not require
reshaping for anonymisation.

Use the :ref:`crate_anon_draft_dd <crate_anon_draft_dd>` tool to create a data
dictionary from SystmOne_. CRATE knows something about the structure of a
typical SystmOne database.

However, NHS numbers, which are `10-digit integers incorporating a checksum
<https://www.datadictionary.nhs.uk/attributes/nhs_number.html>`_, are
represented in the SRE by the ``VARCHAR(10)`` data type. Therefore, you should
use these lines in your :ref:`anonymiser config file <anon_config_file>`:

.. code-block:: ini

    sqlatype_mpid = String(10)

See :ref:`sqlatype_mpid <anon_config_sqlatype_mpid>`.