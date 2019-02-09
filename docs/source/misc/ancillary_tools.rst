.. crate_anon/docs/source/misc/ancillary_tools.rst

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

Ancillary tools
===============

.. contents::
   :local:

crate_docs
~~~~~~~~~~

Launches this documentation via your web browser.

crate_make_demo_database
~~~~~~~~~~~~~~~~~~~~~~~~

Options as of 2016-07-21:

.. code-block:: none

    usage: crate_make_demo_database [-h] [--size {0,1,2,3}] [--verbose] [--echo]
                                    [--doctest-doc DOCTEST_DOC]
                                    [--doctest-docx DOCTEST_DOCX]
                                    [--doctest-odt DOCTEST_ODT]
                                    [--doctest-pdf DOCTEST_PDF]
                                    url

    positional arguments:
      url                   SQLAlchemy database URL. Append ?charset=utf8, e.g. my
                            sql+mysqldb://root:password@127.0.0.1:3306/test?charse
                            t=utf8 . WARNING: If you get the error 'MySQL has gone
                            away', increase the max_allowed_packet parameter in
                            my.cnf (e.g. to 32M).

    optional arguments:
      -h, --help            show this help message and exit
      --size {0,1,2,3}      Make tiny (0), small (1), medium (2), or large (3)
                            database (default=0)
      --verbose, -v         Be verbose (use twice for extra verbosity)
      --echo                Echo SQL
      --doctest-doc DOCTEST_DOC
                            Test file for .DOC (default: /home/rudolf/Documents/co
                            de/crate/crate_anon/anonymise/../../testdocs_for_text_
                            extraction/doctest.doc)
      --doctest-docx DOCTEST_DOCX
                            Test file for .DOCX (default: /home/rudolf/Documents/c
                            ode/crate/crate_anon/anonymise/../../testdocs_for_text
                            _extraction/doctest.docx)
      --doctest-odt DOCTEST_ODT
                            Test file for .ODT (default: /home/rudolf/Documents/co
                            de/crate/crate_anon/anonymise/../../testdocs_for_text_
                            extraction/doctest.odt)
      --doctest-pdf DOCTEST_PDF
                            Test file for .PDF (default: /home/rudolf/Documents/co
                            de/crate/crate_anon/anonymise/../../testdocs_for_text_
                            extraction/doctest.pdf)


crate_test_extract_text
~~~~~~~~~~~~~~~~~~~~~~~

Options as of 2019-02-09:

.. code-block:: none

    usage: crate_test_extract_text [-h] [--plain] [--width WIDTH] [--silent]
                                   filename

    Test CRATE text extraction and/or detect text in files.

    Exit codes:
    - 0 for "text found"
    - 1 for "no text found"
    - 2 for "error" (e.g. file not found)


    positional arguments:
      filename       File from which to extract text

    optional arguments:
      -h, --help     show this help message and exit
      --plain        Use plainest format (not e.g. table layouts) (default: False)
      --width WIDTH  Width to word-wrap to (default: 80)
      --silent       Don't print the text, just exit with a code (default: False)


crate_test_anonymisation
~~~~~~~~~~~~~~~~~~~~~~~~

Options as of 2016-07-21:

.. code-block:: none

    usage: crate_test_anonymisation [-h] --config CONFIG --dsttable DSTTABLE
                                    --dstfield DSTFIELD [--limit LIMIT]
                                    [--rawdir RAWDIR] [--anondir ANONDIR]
                                    [--resultsfile RESULTSFILE]
                                    [--scrubfile SCRUBFILE] [--verbose]
                                    [--pkfromsrc | --pkfromdest]
                                    [--uniquepatients | --nonuniquepatients]

    Test anonymisation

    optional arguments:
      -h, --help            show this help message and exit
      --config CONFIG       Configuration file name (input) (default: None)
      --dsttable DSTTABLE   Destination table (default: None)
      --dstfield DSTFIELD   Destination column (default: None)
      --limit LIMIT         Limit on number of documents (default: 100)
      --rawdir RAWDIR       Directory for raw output text files (default: raw)
      --anondir ANONDIR     Directory for anonymised output text files (default:
                            anon)
      --resultsfile RESULTSFILE
                            Results output CSV file name (default:
                            testanon_results.csv)
      --scrubfile SCRUBFILE
                            Scrubbing information text file name (default:
                            testanon_scrubber.txt)
      --verbose, -v         Be verbose (use twice for extra verbosity) (default:
                            0)
      --pkfromsrc           Fetch PKs (document IDs) from source (default)
                            (default: True)
      --pkfromdest          Fetch PKs (document IDs) from destination (default:
                            True)
      --uniquepatients      Only one document per patient (the first by PK)
                            (default) (default: True)
      --nonuniquepatients   Documents in sequence, with potentially >1
                            document/patient (default: True)


crate_estimate_mysql_memory_usage
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Options as of 2016-07-21:

.. code-block:: none

    usage: crate_estimate_mysql_memory_usage [-h] [--mysql MYSQL] [--host HOST]
                                             [--port PORT] [--user USER]

    optional arguments:
      -h, --help     show this help message and exit
      --mysql MYSQL  MySQL program (default=mysql)
      --host HOST    MySQL server/host (prefer '127.0.0.1' to 'localhost')
      --port PORT    MySQL port (default=3306)
      --user USER    MySQL user (default=root)
