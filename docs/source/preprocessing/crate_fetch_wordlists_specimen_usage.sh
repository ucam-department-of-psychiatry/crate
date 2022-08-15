#!/bin/bash
# Generating name files under Linux, for nonspecific name removal.

# -----------------------------------------------------------------------------
# 1. Fetch our source data.
# -----------------------------------------------------------------------------
# Downloading these and then using a file:// URL is unnecessary, but it makes
# the processing steps faster if we need to retry with new settings.
wget https://www.gutenberg.org/files/3201/files/CROSSWD.TXT -O dictionary.txt
wget https://www.ssa.gov/OACT/babynames/names.zip -O forenames.zip
wget http://www2.census.gov/topics/genealogy/1990surnames/dist.all.last -O surnames_1990.txt
wget https://www2.census.gov/topics/genealogy/2010surnames/names.zip -O surnames_2010.zip

# -----------------------------------------------------------------------------
# 2. Create our wordlists.
# -----------------------------------------------------------------------------
# Fetch forenames, surnames, medical eponyms, and words valid for Scrabble.
# Via --debug_names, we'll illustrate frequencies for some names that are also
# words.
crate_fetch_wordlists \
    --english_words \
        --english_words_url "file://${PWD}/dictionary.txt" \
        --english_words_output english_crossword_words.txt \
    --us_forenames \
        --us_forenames_url "file://${PWD}/forenames.zip" \
        --us_forenames_max_cumfreq_pct 100 \
        --us_forenames_output us_forenames.txt \
    --us_surnames \
        --us_surnames_1990_census_url "file://${PWD}/surnames_1990.txt" \
        --us_surnames_2010_census_url "file://${PWD}/surnames_2010.zip" \
        --us_surnames_max_cumfreq_pct 100 \
        --us_surnames_output us_surnames.txt \
    --eponyms \
        --eponyms_output medical_eponyms.txt \
    --debug_names \
        excellent fought friend games he hope husband john joyful kitten \
        knuckle libel limp lovely man memory mood music no power powers sad \
        stress true veronica yes you young zone

# Count frequencies for a few books (preserving case, filtering for words of
# length 2+ and meeting a valid pattern which includes starting with a
# lower-case letter), across 1,134,142 words:
crate_fetch_wordlists \
      --gutenberg_word_freq \
      --gutenberg_id_first 100 \
      --gutenberg_id_last 110 \
      --gutenberg_word_freq_output english_word_freq_gutenberg.csv
# 100 is Shakespeare: https://www.gutenberg.org/ebooks/100

# Filter to common words, that account together for the top 99% of usage.
crate_fetch_wordlists \
    --filter_words_by_freq \
    --wordfreqfilter_input english_word_freq_gutenberg.csv \
    --wordfreqfilter_min_cum_freq 0.0 \
    --wordfreqfilter_max_cum_freq 0.99 \
    --wordfreqfilter_output english_gutenberg_common_words.txt
# In this corpus, "john" comes in at about 0.9923.

# Create a list of common English words -- the overlap between "common words in
# Project Gutenberg books" and "valid Scrabble words".
crate_fetch_wordlists \
    --filter_input english_gutenberg_common_words.txt \
    --filter_include english_crossword_words.txt \
    --filter_output common_english_words.txt

# -----------------------------------------------------------------------------
# 3. Generate an amalgamated and filtered wordlist.
# -----------------------------------------------------------------------------
crate_fetch_wordlists \
    --filter_input us_forenames.txt us_surnames.txt \
    --filter_exclude medical_eponyms.txt common_english_words.txt \
    --filter_output filtered_names.txt
#                   ^^^^^^^^^^^^^^^^^^
# This may be useful for the CRATE anonymiser option --denylist_filenames.

# As a check, these are then names that are *rare* English words:
comm -12 \
    <(sort filtered_names.txt | tr "[:upper:]" "[:lower:]") \
    <(sort english_crossword_words.txt | tr "[:upper:]" "[:lower:]") \
    > remaining_names_that_are_english_crossword_words.txt
