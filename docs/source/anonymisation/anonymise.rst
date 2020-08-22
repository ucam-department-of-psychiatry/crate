..  crate_anon/docs/source/anonymisation/anonymise.rst

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


Run the anonymiser
------------------

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

..  literalinclude:: crate_anonymise_help.txt
    :language: none


.. _crate_anonymise_multiprocess:

crate_anonymise_multiprocess
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This runs multiple copies of ``crate_anonymise`` in parallel.

Options:

..  literalinclude:: crate_anonymise_multiprocess_help.txt
    :language: none
