..  crate_anon/docs/source/anonymisation/anonymise.rst

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


Run the anonymiser
------------------

.. contents::
   :local:

Now you've created and edited your config file and data dictionary, you can run
the anonymiser in one of the following ways:

.. code-block:: bash

    crate_anonymise --full
    crate_anonymise --incremental
    crate_anonymise_multiprocess --full
    crate_anonymise_multiprocess --incremental

The ‘multiprocess’ versions are faster (if you have a multi-core/-CPU
computer). The ‘full’ option destroys the destination database and starts
again. The ‘incremental’ one brings the destination database up to date
(creating it if necessary). The default is ‘incremental’, for safety reasons.

Get more help with

.. code-block:: bash

    crate_anonymise --help


.. _crate_anonymise:

crate_anonymise
~~~~~~~~~~~~~~~

This runs a single-process anonymiser.

Options:

..  literalinclude:: _crate_anonymise_help.txt
    :language: none


.. _crate_anonymise_multiprocess:

crate_anonymise_multiprocess
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This runs multiple copies of ``crate_anonymise`` in parallel.

Options:

..  literalinclude:: _crate_anonymise_multiprocess_help.txt
    :language: none


.. _crate_anon_show_counts:

crate_anon_show_counts
~~~~~~~~~~~~~~~~~~~~~~

This ancillary tool prints record counts from your source and destination
databases.

..  literalinclude:: _crate_anon_show_counts_help.txt
    :language: none


.. _crate_anon_check_text_extractor:

crate_anon_check_text_extractor
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This ancillary tool checks that you have the text extraction software that you
might want. See :ref:`third-party text extractors
<third_party_text_extractors>`.

..  literalinclude:: _crate_anon_check_text_extractor.txt
    :language: none


.. _crate_anon_summarize_dd:

crate_anon_summarize_dd
~~~~~~~~~~~~~~~~~~~~~~~

This ancillary tool reads your data dictionary and summarizes facts about
each table. It may be helpful to find problems with large data dictionaries.

..  literalinclude:: _crate_anon_summarize_dd_help.txt
    :language: none


.. _crate_anon_researcher_report:

crate_anon_researcher_report
~~~~~~~~~~~~~~~~~~~~~~~

This ancillary tool reads your destination database (and data dictionary) and
generates a PDF report intended for use by researchers. Optionally, it can
include row counts and specimen values or value ranges.

..  literalinclude:: _crate_anon_researcher_report_help.txt
    :language: none
