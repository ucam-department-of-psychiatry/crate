.. crate_anon/docs/source/nlp/run_nlp.rst

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

Run the NLP
-----------

Now you've created and edited your config file, you can run the NLP process in
one of the following ways:

.. code-block:: bash

    crate_nlp --nlpdef NLP_NAME --incremental
    crate_nlp --nlpdef NLP_NAME --full
    crate_nlp_multiprocess --nlpdef NLP_NAME --incremental
    crate_nlp_multiprocess --nlpdef NLP_NAME --full

where `NLP_NAME` is something you’ve configured in the :ref:`NLP config file
<nlp_config>` (e.g. a drug-parsing NLP program or the GATE demonstration
name/location NLP app). Use

The ‘multiprocess’ versions are faster (if you have a multi-core/-CPU
computer). The ‘full’ option destroys the destination database and starts
again. The ‘incremental’ one brings the destination database up to date
(creating it if necessary). The default is ‘incremental’, for safety reasons.

Get more help with

.. code-block:: bash

    crate_nlp --help


crate_nlp
~~~~~~~~~

This runs a single-process NLP controller.

Options as of 2017-02-28:

..  literalinclude:: crate_nlp_help.txt
    :language: none


Current NLP processors
~~~~~~~~~~~~~~~~~~~~~~

NLP processors as of 2017-02-28 (from ``crate_nlp --describeprocessors``):

..  literalinclude:: crate_nlp_describeprocessors.txt
    :language: none


crate_nlp_multiprocess
~~~~~~~~~~~~~~~~~~~~~~

This program runs multiple copies of ``crate_nlp`` in parallel.

Options as of 2017-02-28:

..  literalinclude:: crate_nlp_multiprocess_help.txt
    :language: none
