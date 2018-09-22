.. crate_anon/docs/source/anonymisation/anonymise.rst

..  Copyright (C) 2015-2018 Rudolf Cardinal (rudolf@pobox.com).
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

crate_anonymise
~~~~~~~~~~~~~~~

This runs a single-process anonymiser.

Options as of 2017-02-28:

.. code-block:: none

    usage: crate_anonymise [-h] [--version] [--democonfig] [--config CONFIG]
                           [--verbose] [--reportevery [REPORTEVERY]]
                           [--chunksize [CHUNKSIZE]] [--process [PROCESS]]
                           [--nprocesses [NPROCESSES]]
                           [--processcluster PROCESSCLUSTER] [--draftdd]
                           [--incrementaldd] [--debugscrubbers] [--savescrubbers]
                           [--count] [--dropremake] [--optout]
                           [--nonpatienttables] [--patienttables] [--index]
                           [--skip_dd_check] [-i | -f] [--skipdelete]
                           [--seed SEED] [--echo]
                           [--checkextractor [CHECKEXTRACTOR [CHECKEXTRACTOR ...]]]

    Database anonymiser. Version 0.18.12 (2017-02-26). By Rudolf Cardinal.

    optional arguments:
      -h, --help            show this help message and exit
      --version             show program's version number and exit
      --democonfig          Print a demo config file
      --config CONFIG       Config file (overriding environment variable
                            CRATE_ANON_CONFIG)
      --verbose, -v         Be verbose
      --reportevery [REPORTEVERY]
                            Report insert progress every n rows in verbose mode
                            (default 100000)
      --chunksize [CHUNKSIZE]
                            Number of records copied in a chunk when copying PKs
                            from one database to another (default 100000)
      --process [PROCESS]   For multiprocess mode: specify process number
      --nprocesses [NPROCESSES]
                            For multiprocess mode: specify total number of
                            processes (launched somehow, of which this is to be
                            one)
      --processcluster PROCESSCLUSTER
                            Process cluster name
      --draftdd             Print a draft data dictionary
      --incrementaldd       Print an INCREMENTAL draft data dictionary
      --debugscrubbers      Report sensitive scrubbing information, for debugging
      --savescrubbers       Saves sensitive scrubbing information in admin
                            database, for debugging
      --count               Count records in source/destination databases, then
                            stop
      --dropremake          Drop/remake destination tables, then stop
      --optout              Build opt-out list, then stop
      --nonpatienttables    Process non-patient tables only
      --patienttables       Process patient tables only
      --index               Create indexes only
      --skip_dd_check       Skip data dictionary validity check
      -i, --incremental     Process only new/changed information, where possible
                            (* default)
      -f, --full            Drop and remake everything
      --skipdelete          For incremental updates, skip deletion of rows present
                            in the destination but not the source
      --seed SEED           String to use as the basis of the seed for the random
                            number generator used for the transient integer RID
                            (TRID). Leave blank to use the default seed (system
                            time).
      --echo                Echo SQL
      --checkextractor [CHECKEXTRACTOR [CHECKEXTRACTOR ...]]
                            File extensions to check for availability of a text
                            extractor (use a '.' prefix, and use the special
                            extension 'None' to check the fallback processor

crate_anonymise_multiprocess
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This runs multiple copies of ``crate_anonymise`` in parallel.

Options as of 2017-02-28:

.. code-block:: none

    usage: crate_anonymise_multiprocess [-h] [--nproc [NPROC]] [--verbose]

    Runs the CRATE anonymiser in parallel. Version 0.18.12 (2017-02-26). Note that
    all arguments not specified here are passed to the underlying script (see
    crate_anonymise --help).

    optional arguments:
      -h, --help            show this help message and exit
      --nproc [NPROC], -n [NPROC]
                            Number of processes (default on this machine: 8)
      --verbose, -v         Be verbose
