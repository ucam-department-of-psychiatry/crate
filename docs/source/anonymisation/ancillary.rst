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

..  literalinclude:: crate_postcodes_help.txt
    :language: none


.. _crate_fetch_wordlists:

crate_fetch_wordlists
~~~~~~~~~~~~~~~~~~~~~

This tool assists in fetching common word lists, such as name lists for global
blacklisting, and words to exclude from such lists (such as English words or
medical eponyms). It also provides an exclusion filter system, to find lines in
some files that are absent from others.

Options as of 2018-03-27:

..  literalinclude:: crate_fetch_wordlists_help.txt
    :language: none


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
