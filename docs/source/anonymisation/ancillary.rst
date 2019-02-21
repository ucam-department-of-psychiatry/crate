.. crate_anon/docs/source/anonymisation/ancillary.rst

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


Ancillary tools
---------------

These fetch useful data from elsewhere, for use by CRATE.


crate_postcodes
~~~~~~~~~~~~~~~

Options as of 2017-02-28:

.. code-block:: none

    usage: crate_postcodes [-h] [--dir DIR] [--url URL] [--echo]
                           [--reportevery REPORTEVERY] [--commitevery COMMITEVERY]
                           [--startswith STARTSWITH [STARTSWITH ...]] [--replace]
                           [--skiplookup]
                           [--specific_lookup_tables [SPECIFIC_LOOKUP_TABLES [SPECIFIC_LOOKUP_TABLES ...]]]
                           [--list_lookup_tables] [--skippostcodes] [--docsonly]
                           [-v]

    -   This program reads data from the UK Office of National Statistics Postcode
        Database (ONSPD) and inserts it into a database.

    -   You will need to download the ONSPD from
            https://geoportal.statistics.gov.uk/geoportal/catalog/content/filelist.page
        e.g. ONSPD_MAY_2016_csv.zip (79 Mb), and unzip it (>1.4 Gb) to a directory.
        Tell this program which directory you used.

    -   Specify your database as an SQLAlchemy connection URL: see
            http://docs.sqlalchemy.org/en/latest/core/engines.html
        The general format is:
            dialect[+driver]://username:password@host[:port]/database[?key=value...]

    -   If you get an error like:
            UnicodeEncodeError: 'latin-1' codec can't encode character '\u2019' in
            position 33: ordinal not in range(256)
        then try appending "?charset=utf8" to the connection URL.

    -   ONS POSTCODE DATABASE LICENSE.
        Output using this program must add the following attribution statements:

        Contains OS data © Crown copyright and database right [year]
        Contains Royal Mail data © Royal Mail copyright and database right [year]
        Contains National Statistics data © Crown copyright and database right [year]

        See http://www.ons.gov.uk/methodology/geography/licences


    optional arguments:
      -h, --help            show this help message and exit
      --dir DIR             Root directory of unzipped ONSPD download (default:
                            /home/rudolf/dev/onspd)
      --url URL             SQLAlchemy database URL
      --echo                Echo SQL
      --reportevery REPORTEVERY
                            Report every n rows (default: 1000)
      --commitevery COMMITEVERY
                            Commit every n rows (default: 10000). If you make this
                            too large (relative e.g. to your MySQL
                            max_allowed_packet setting, you may get crashes with
                            errors like 'MySQL has gone away'.
      --startswith STARTSWITH [STARTSWITH ...]
                            Restrict to postcodes that start with one of these
                            strings
      --replace             Replace tables even if they exist (default: skip
                            existing tables)
      --skiplookup          Skip generation of code lookup tables
      --specific_lookup_tables [SPECIFIC_LOOKUP_TABLES [SPECIFIC_LOOKUP_TABLES ...]]
                            Within the lookup tables, process only specific named
                            tables
      --list_lookup_tables  List all possible lookup tables, then stop
      --skippostcodes       Skip generation of main (large) postcode table
      --docsonly            Show help for postcode table then stop
      -v, --verbose         Verbose


crate_fetch_wordlists
~~~~~~~~~~~~~~~~~~~~~

This tool assists in fetching common word lists, such as name lists for global
blacklisting, and words to exclude from such lists (such as English words or
medical eponyms). It also provides an exclusion filter system, to find lines in
some files that are absent from others.

Options as of 2018-03-27:

.. code-block:: none

    usage: crate_fetch_wordlists [-h] [--specimen] [--verbose]
                                 [--min_word_length MIN_WORD_LENGTH]
                                 [--show_rejects] [--english_words]
                                 [--english_words_output ENGLISH_WORDS_OUTPUT]
                                 [--english_words_url ENGLISH_WORDS_URL]
                                 [--valid_word_regex VALID_WORD_REGEX]
                                 [--us_forenames]
                                 [--us_forenames_url US_FORENAMES_URL]
                                 [--us_forenames_min_cumfreq_pct US_FORENAMES_MIN_CUMFREQ_PCT]
                                 [--us_forenames_max_cumfreq_pct US_FORENAMES_MAX_CUMFREQ_PCT]
                                 [--us_forenames_output US_FORENAMES_OUTPUT]
                                 [--us_surnames]
                                 [--us_surnames_output US_SURNAMES_OUTPUT]
                                 [--us_surnames_1990_census_url US_SURNAMES_1990_CENSUS_URL]
                                 [--us_surnames_2010_census_url US_SURNAMES_2010_CENSUS_URL]
                                 [--us_surnames_min_cumfreq_pct US_SURNAMES_MIN_CUMFREQ_PCT]
                                 [--us_surnames_max_cumfreq_pct US_SURNAMES_MAX_CUMFREQ_PCT]
                                 [--eponyms] [--eponyms_output EPONYMS_OUTPUT]
                                 [--eponyms_add_unaccented_versions [EPONYMS_ADD_UNACCENTED_VERSIONS]]
                                 [--filter_input [FILTER_INPUT [FILTER_INPUT ...]]]
                                 [--filter_exclude [FILTER_EXCLUDE [FILTER_EXCLUDE ...]]]
                                 [--filter_output [FILTER_OUTPUT]]

    optional arguments:
      -h, --help            show this help message and exit
      --specimen            Show some specimen usages and exit (default: False)
      --verbose, -v         Be verbose (default: False)
      --min_word_length MIN_WORD_LENGTH
                            Minimum word length to allow (default: 2)
      --show_rejects        Print to stdout (and, in verbose mode, log) the words
                            being rejected (default: False)

    English words:
      --english_words       Fetch English words (for reducing nonspecific
                            blacklist, not as whitelist; consider words like
                            smith) (default: False)
      --english_words_output ENGLISH_WORDS_OUTPUT
                            Output file for English words (default:
                            english_words.txt)
      --english_words_url ENGLISH_WORDS_URL
                            URL for a textfile containing all English words (will
                            then be filtered) (default: https://www.gutenberg.org/
                            files/3201/files/CROSSWD.TXT)
      --valid_word_regex VALID_WORD_REGEX
                            Regular expression to determine valid English words
                            (default: ^[a-z](?:[A-Za-z'-]*[a-z])*$)

    US forenames:
      --us_forenames        Fetch US forenames (for blacklist) (default: False)
      --us_forenames_url US_FORENAMES_URL
                            URL to Zip file of US Census-derived forenames lists
                            (excludes names with national frequency <5; see
                            https://www.ssa.gov/OACT/babynames/limits.html)
                            (default:
                            https://www.ssa.gov/OACT/babynames/names.zip)
      --us_forenames_min_cumfreq_pct US_FORENAMES_MIN_CUMFREQ_PCT
                            Fetch only names where the cumulative frequency
                            percentage up to and including this name was at least
                            this value. Range is 0-100. Use 0 for no limit.
                            Setting this above 0 excludes COMMON names. (This is a
                            trade-off between being comprehensive and operating at
                            a reasonable speed. Higher numbers are more
                            comprehensive but slower.) (default: 0)
      --us_forenames_max_cumfreq_pct US_FORENAMES_MAX_CUMFREQ_PCT
                            Fetch only names where the cumulative frequency
                            percentage up to and including this name was less than
                            or equal to this value. Range is 0-100. Use 100 for no
                            limit. Setting this below 100 excludes RARE names.
                            (This is a trade-off between being comprehensive and
                            operating at a reasonable speed. Higher numbers are
                            more comprehensive but slower.) (default: 100)
      --us_forenames_output US_FORENAMES_OUTPUT
                            Output file for US forenames (default:
                            us_forenames.txt)

    US surnames:
      --us_surnames         Fetch US surnames (for blacklist) (default: False)
      --us_surnames_output US_SURNAMES_OUTPUT
                            Output file for UK surnames (default: us_surnames.txt)
      --us_surnames_1990_census_url US_SURNAMES_1990_CENSUS_URL
                            URL for textfile of US 1990 Census surnames (default:
                            http://www2.census.gov/topics/genealogy/1990surnames/d
                            ist.all.last)
      --us_surnames_2010_census_url US_SURNAMES_2010_CENSUS_URL
                            URL for zip of US 2010 Census surnames (default: https
                            ://www2.census.gov/topics/genealogy/2010surnames/names
                            .zip)
      --us_surnames_min_cumfreq_pct US_SURNAMES_MIN_CUMFREQ_PCT
                            Fetch only names where the cumulative frequency
                            percentage up to and including this name was at least
                            this value. Range is 0-100. Use 0 for no limit.
                            Setting this above 0 excludes COMMON names. (This is a
                            trade-off between being comprehensive and operating at
                            a reasonable speed. Higher numbers are more
                            comprehensive but slower.) (default: 0)
      --us_surnames_max_cumfreq_pct US_SURNAMES_MAX_CUMFREQ_PCT
                            Fetch only names where the cumulative frequency
                            percentage up to and including this name was less than
                            or equal to this value. Range is 0-100. Use 100 for no
                            limit. Setting this below 100 excludes RARE names.
                            (This is a trade-off between being comprehensive and
                            operating at a reasonable speed. Higher numbers are
                            more comprehensive but slower.) (default: 100)

    Medical eponyms:
      --eponyms             Write medical eponyms (to remove from blacklist)
                            (default: False)
      --eponyms_output EPONYMS_OUTPUT
                            Output file for medical eponyms (default:
                            medical_eponyms.txt)
      --eponyms_add_unaccented_versions [EPONYMS_ADD_UNACCENTED_VERSIONS]
                            Add unaccented versions (e.g. Sjogren as well as
                            Sjögren) (default: True)

    Filter functions:
      Extra functions to filter wordlists. Specify an input file (or files),
      whose lines will be included; optional exclusion file(s), whose lines will
      be excluded (in case-insensitive fashion); and an output file. You can use
      '-' for the output file to mean 'stdout', and for one input file to mean
      'stdin'. No filenames (other than '-' for input and output) may overlap.
      The --min_line_length option also applies. Duplicates are not removed.

      --filter_input [FILTER_INPUT [FILTER_INPUT ...]]
                            Input file(s). See above. (default: None)
      --filter_exclude [FILTER_EXCLUDE [FILTER_EXCLUDE ...]]
                            Exclusion file(s). See above. (default: None)
      --filter_output [FILTER_OUTPUT]
                            Exclusion file(s). See above. (default: None)

Specimen usage:

.. code-block:: bash

    #!/bin/bash
    # -----------------------------------------------------------------------------
    # Specimen usage under Linux
    # -----------------------------------------------------------------------------

    cd ~/Documents/code/crate/working

    # Downloading these and then using a file:// URL is unnecessary, but it makes
    # the processing steps faster if we need to retry with new settings.
    wget https://www.gutenberg.org/files/3201/files/CROSSWD.TXT -O dictionary.txt
    wget https://www.ssa.gov/OACT/babynames/names.zip -O forenames.zip
    wget http://www2.census.gov/topics/genealogy/1990surnames/dist.all.last -O surnames_1990.txt
    wget https://www2.census.gov/topics/genealogy/2010surnames/names.zip -O surnames_2010.zip

    crate_fetch_wordlists --help

    crate_fetch_wordlists \
        --english_words \
            --english_words_url file://$PWD/dictionary.txt \
        --us_forenames \
            --us_forenames_url file://$PWD/forenames.zip \
            --us_forenames_max_cumfreq_pct 100 \
        --us_surnames \
            --us_surnames_1990_census_url file://$PWD/surnames_1990.txt \
            --us_surnames_2010_census_url file://$PWD/surnames_2010.zip \
            --us_surnames_max_cumfreq_pct 100 \
        --eponyms

    #    --show_rejects \
    #    --verbose

    # Forenames encompassing the top 95% gives 5874 forenames (of 96174).
    # Surnames encompassing the top 85% gives 74525 surnames (of 175880).

    crate_fetch_wordlists \
        --filter_input \
            us_forenames.txt \
            us_surnames.txt \
        --filter_exclude \
            english_words.txt \
            medical_eponyms.txt \
        --filter_output \
            filtered_names.txt
