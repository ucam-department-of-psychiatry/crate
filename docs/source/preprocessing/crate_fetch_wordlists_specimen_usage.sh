#!/bin/bash
# Generating name files under Linux, for nonspecific name removal.

# 1. Fetch our source data.
# Downloading these and then using a file:// URL is unnecessary, but it makes
# the processing steps faster if we need to retry with new settings.
wget https://www.gutenberg.org/files/3201/files/CROSSWD.TXT -O dictionary.txt
wget https://www.ssa.gov/OACT/babynames/names.zip -O forenames.zip
wget http://www2.census.gov/topics/genealogy/1990surnames/dist.all.last -O surnames_1990.txt
wget https://www2.census.gov/topics/genealogy/2010surnames/names.zip -O surnames_2010.zip

# 2. Create our wordlists.
#    (We'll illustrate frequencies for some names that are also words.)
crate_fetch_wordlists \
    --english_words \
        --english_words_url "file://${PWD}/dictionary.txt" \
        --english_words_output english_words.txt \
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

# 3. Generate an amalgamated and filtered wordlist.
crate_fetch_wordlists \
    --filter_input us_forenames.txt us_surnames.txt \
    --filter_exclude medical_eponyms.txt \
    --filter_output filtered_names.txt

# If we don't "--filter_exclude english_words.txt", then this is the overlap:
comm -12 \
    <(sort filtered_names.txt | tr "[:upper:]" "[:lower:]") \
    <(sort english_words.txt | tr "[:upper:]" "[:lower:]") \
    > names_that_are_english_words.txt
