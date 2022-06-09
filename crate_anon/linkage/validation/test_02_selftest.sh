#!/usr/bin/env bash
set -e
set -x

FUZZY=crate_fuzzy_id_match

THIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
VALIDATOR=${THIS_DIR}/validate_fuzzy_linkage.py

WORKDIR=${HOME}/.local/share/crate
SAMPLE=${WORKDIR}/crate_fuzzy_sample.csv
SAMPLE_10K=${WORKDIR}/crate_fuzzy_sample_10k.csv
SAMPLE_HASHED=${WORKDIR}/crate_fuzzy_hashed.jsonl

COMPARISON_P2P=${WORKDIR}/crate_fuzzy_output_p2p.csv
COMPARISON_H2P=${WORKDIR}/crate_fuzzy_output_h2p.csv
COMPARISON_H2H=${WORKDIR}/crate_fuzzy_output_h2h.csv

# -----------------------------------------------------------------------------
# Command tests: demo/debugging
# -----------------------------------------------------------------------------

"${FUZZY}" print_demo_sample

"${FUZZY}" show_metaphone JANE JOHN ISADORA KIT
"${FUZZY}" show_forename_freq JANE JOHN ISADORA KIT
"${FUZZY}" show_forename_metaphone_freq JN JN ASTR KT

"${FUZZY}" show_metaphone SMITH JONES SHAKESPEARE TELL
"${FUZZY}" show_surname_freq SMITH JONES SHAKESPEARE TELL
"${FUZZY}" show_surname_metaphone_freq SM0 JNS XKSP TL

"${FUZZY}" show_dob_freq  # no arguments

# -----------------------------------------------------------------------------
# Command tests: main
# -----------------------------------------------------------------------------

"${FUZZY}" hash \
    --allow_default_hash_key \
    --input "${SAMPLE}" \
    --output "${SAMPLE_HASHED}"
"${FUZZY}" hash \
    --allow_default_hash_key \
    --input "${SAMPLE}" \
    --output "${WORKDIR}/crate_fuzzy_hashed_no_freq.jsonl" \
    --without_frequencies
"${FUZZY}" hash \
    --allow_default_hash_key \
    --input "${SAMPLE}" \
    --output "${WORKDIR}/crate_fuzzy_hashed_with_other_info.jsonl" \
    --include_other_info

# This should produce matches for most (comparing a sample to itself):
# Using "--n_workers 1" preserves order.
"${FUZZY}" compare_plaintext \
    --probands "${SAMPLE}" \
    --sample "${SAMPLE}" \
    --output "${COMPARISON_P2P}" \
    --n_workers 1

# This should produce matches for none, since they are internally duplicated!
# It's here primarily as a speed test.
"${FUZZY}" compare_plaintext \
    --probands "${SAMPLE_10K}" \
    --sample "${SAMPLE_10K}" \
    --output "${WORKDIR}/crate_fuzzy_output_10k.csv"

# For Figure 3, a demonstration of the Bayesian approach:
"${FUZZY}" compare_plaintext \
    --probands "${WORKDIR}/crate_fuzzy_demo_fig3_probands.csv" \
    --sample "${WORKDIR}/crate_fuzzy_demo_fig3_sample.csv" \
    --output "${WORKDIR}/crate_fuzzy_demo_fig3_output.csv"

"${FUZZY}" compare_hashed_to_hashed \
    --probands "${SAMPLE_HASHED}" \
    --sample "${SAMPLE_HASHED}" \
    --output "${COMPARISON_H2H}" \
    --n_workers 1
# cmp "${COMPARISON_H2H}" "${COMPARISON_P2P}" || { echo "H2H/P2P mismatch"; exit 1; }
# The comparisons fail at e.g. the fourth decimal place of the log odds,
# because fuzzy frequencies are slightly blurred...

"${FUZZY}" compare_hashed_to_plaintext \
    --allow_default_hash_key \
    --probands "${SAMPLE_HASHED}" \
    --sample "${SAMPLE}" \
    --output "${COMPARISON_H2P}" \
    --n_workers 1
# cmp "${COMPARISON_H2P}" "${COMPARISON_P2P}" || { echo "H2P/P2P mismatch"; exit 1; }


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------

"${VALIDATOR}" speedtest

"${VALIDATOR}" validate1 \
    --people "${SAMPLE}" \
    --output "${WORKDIR}/crate_fuzzy_validation1_output.csv"

# validate2_fetch_cdl
# validate2_fetch_pcmis
# validate2_fetch_rio
# validate2_fetch_systmone
