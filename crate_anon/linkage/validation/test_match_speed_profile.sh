#!/bin/bash
set -e

cd ~/.local/share/crate/

crate_fuzzy_id_match compare_plaintext \
    --probands crate_fuzzy_sample_1k.csv \
    --sample crate_fuzzy_sample_1k.csv \
    --output crate_fuzzy_output_1k.csv \
    --profile \
    --n_workers 1

# 2022-06-14: 4.2245 s, good profile
# 2022-06-16: 2.9859 s with exact DOB matches only, 8.111899 s with partials
