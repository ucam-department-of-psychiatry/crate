#!/bin/bash

# installer/example_scripts/fetch_wordlists.sh

# ==============================================================================
#
#     Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
#     Created by Rudolf Cardinal (rnc1001@cam.ac.uk).
#
#     This file is part of CRATE.
#
#     CRATE is free software: you can redistribute it and/or modify
#     it under the terms of the GNU General Public License as published by
#     the Free Software Foundation, either version 3 of the License, or
#     (at your option) any later version.
#
#     CRATE is distributed in the hope that it will be useful,
#     but WITHOUT ANY WARRANTY; without even the implied warranty of
#     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#     GNU General Public License for more details.
#
#     You should have received a copy of the GNU General Public License
#     along with CRATE. If not, see <https://www.gnu.org/licenses/>.
#
# ==============================================================================

# Example script to fetch wordlists
# Based on the example script at
# https://crateanon.readthedocs.io/en/latest/preprocessing/index.html#crate-fetch-wordlists

set -euo pipefail

THISDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
# shellcheck source-path=SCRIPTDIR source=set_crate_environment_vars
source "${THISDIR}"/set_crate_environment_vars

# Generating name files under Linux, for nonspecific name removal.

# -----------------------------------------------------------------------------
# 1. Fetch our source data.
# -----------------------------------------------------------------------------
# Downloading these and then using a file:// URL is unnecessary, but it makes
# the processing steps faster if we need to retry with new settings.
HOST_WORDLIST_DIR=${CRATE_HOST_BASE_DIR}/files/wordlists

mkdir -p ${HOST_WORDLIST_DIR}

wget https://www.gutenberg.org/files/3201/files/crosswd.txt -O ${HOST_WORDLIST_DIR}/dictionary.txt
wget https://www.ssa.gov/OACT/babynames/names.zip -O ${HOST_WORDLIST_DIR}/forenames.zip
wget http://www2.census.gov/topics/genealogy/1990surnames/dist.all.last -O ${HOST_WORDLIST_DIR}/surnames_1990.txt
wget https://www2.census.gov/topics/genealogy/2010surnames/names.zip -O ${HOST_WORDLIST_DIR}/surnames_2010.zip

CONTAINER_WORDLIST_DIR=${CRATE_CONTAINER_FILES_DIR}/wordlists

# -----------------------------------------------------------------------------
# 2. Create our wordlists.
# -----------------------------------------------------------------------------
# Fetch forenames, surnames, medical eponyms, and words valid for Scrabble.
# Via --debug_names, we'll illustrate frequencies for some names that are also
# words.
${PYTHON} "${CRATE_HOST_INSTALLER_BASE_DIR}/installer.py" exec "cd ${CONTAINER_WORDLIST_DIR} && crate_fetch_wordlists \
    --english_words \
        --english_words_url "file://${CONTAINER_WORDLIST_DIR}/dictionary.txt" \
        --english_words_output ${CONTAINER_WORDLIST_DIR}/english_crossword_words.txt \
    --us_forenames \
        --us_forenames_url "file://${CONTAINER_WORDLIST_DIR}/forenames.zip" \
        --us_forenames_max_cumfreq_pct 100 \
        --us_forenames_output ${CONTAINER_WORDLIST_DIR}/us_forenames.txt \
    --us_surnames \
        --us_surnames_1990_census_url "file://${CONTAINER_WORDLIST_DIR}/surnames_1990.txt" \
        --us_surnames_2010_census_url "file://${CONTAINER_WORDLIST_DIR}/surnames_2010.zip" \
        --us_surnames_max_cumfreq_pct 100 \
        --us_surnames_output ${CONTAINER_WORDLIST_DIR}/us_surnames.txt \
    --eponyms \
        --eponyms_output ${CONTAINER_WORDLIST_DIR}/medical_eponyms.txt \
    --debug_names \
        excellent fought friend games he hope husband john joyful kitten \
        knuckle libel limp lovely man memory mood music no power powers sad \
        stress true veronica yes you young zone"

# Count frequencies for a few books (preserving case, filtering for words of
# length 2+ and meeting a valid pattern which includes starting with a
# lower-case letter), across 1,134,142 words:
${PYTHON} "${CRATE_HOST_INSTALLER_BASE_DIR}/installer.py" exec "cd ${CONTAINER_WORDLIST_DIR} && crate_fetch_wordlists \
      --gutenberg_word_freq \
      --gutenberg_id_first 100 \
      --gutenberg_id_last 110 \
      --gutenberg_word_freq_output ${CONTAINER_WORDLIST_DIR}/english_word_freq_gutenberg.csv"
# 100 is Shakespeare: https://www.gutenberg.org/ebooks/100

# Filter to common words, that account together for the top 99% of usage.
${PYTHON} "${CRATE_HOST_INSTALLER_BASE_DIR}/installer.py" exec "cd ${CONTAINER_WORDLIST_DIR} && crate_fetch_wordlists \
    --filter_words_by_freq \
    --wordfreqfilter_input ${CONTAINER_WORDLIST_DIR}/english_word_freq_gutenberg.csv \
    --wordfreqfilter_min_cum_freq 0.0 \
    --wordfreqfilter_max_cum_freq 0.99 \
    --wordfreqfilter_output ${CONTAINER_WORDLIST_DIR}/english_gutenberg_common_words.txt"
# In this corpus, "john" comes in at about 0.9923.

# Create a list of common English words -- the overlap between "common words in
# Project Gutenberg books" and "valid Scrabble words".
${PYTHON} "${CRATE_HOST_INSTALLER_BASE_DIR}/installer.py" exec "cd ${CONTAINER_WORDLIST_DIR} && crate_fetch_wordlists \
    --filter_input ${CONTAINER_WORDLIST_DIR}/english_gutenberg_common_words.txt \
    --filter_include ${CONTAINER_WORDLIST_DIR}/english_crossword_words.txt \
    --filter_output ${CONTAINER_WORDLIST_DIR}/common_english_words.txt"

# -----------------------------------------------------------------------------
# 3. Generate an amalgamated and filtered wordlist.
# -----------------------------------------------------------------------------
${PYTHON} "${CRATE_HOST_INSTALLER_BASE_DIR}/installer.py" exec "cd ${CONTAINER_WORDLIST_DIR} && crate_fetch_wordlists \
    --filter_input ${CONTAINER_WORDLIST_DIR}/us_forenames.txt ${CONTAINER_WORDLIST_DIR}/us_surnames.txt \
    --filter_exclude ${CONTAINER_WORDLIST_DIR}/medical_eponyms.txt ${CONTAINER_WORDLIST_DIR}/common_english_words.txt \
    --filter_output ${CONTAINER_WORDLIST_DIR}/filtered_names.txt"
#                   ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# This may be useful for the CRATE anonymiser option --denylist_filenames.

# As a check, these are then names that are *rare* English words:
comm -12 \
    <(sort ${HOST_WORDLIST_DIR}/filtered_names.txt | tr "[:upper:]" "[:lower:]") \
    <(sort ${HOST_WORDLIST_DIR}/english_crossword_words.txt | tr "[:upper:]" "[:lower:]") \
    > ${HOST_WORDLIST_DIR}/remaining_names_that_are_english_crossword_words.txt
