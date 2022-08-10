#!/bin/bash
# Fetch/generate name/frequency files for de-identified fuzzy linkage.

# 1. Fetch our source data.
wget https://www.ssa.gov/OACT/babynames/names.zip -O forenames.zip
wget http://www2.census.gov/topics/genealogy/1990surnames/dist.all.last -O surnames_1990.txt
wget https://www2.census.gov/topics/genealogy/2010surnames/names.zip -O surnames_2010.zip

# 2. Create our frequency lists.
crate_fetch_wordlists \
    --us_forenames \
        --us_forenames_url "file://${PWD}/forenames.zip" \
        --us_forenames_sex_freq_output us_forename_sex_freq.csv \
    --us_surnames \
        --us_surnames_1990_census_url "file://${PWD}/surnames_1990.txt" \
        --us_surnames_2010_census_url "file://${PWD}/surnames_2010.zip" \
        --us_surnames_freq_output us_surname_freq.csv
