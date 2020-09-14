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
