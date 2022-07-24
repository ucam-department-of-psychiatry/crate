#!/usr/bin/env bash
set -e
set -x

FUZZY=crate_fuzzy_id_match

THIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
VALIDATOR=${THIS_DIR}/validate_fuzzy_linkage.py

WORKDIR=${HOME}/.local/share/crate
SAMPLE=${WORKDIR}/crate_fuzzy_sample.csv
SAMPLE_CACHE=${WORKDIR}/crate_fuzzy_sample_cache.jsonl
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

"${FUZZY}" show_names_for_metaphone JMS SM0

"${FUZZY}" show_dob_freq  # no arguments

# -----------------------------------------------------------------------------
# Command tests: main
# -----------------------------------------------------------------------------

"${FUZZY}" hash \
    --allow_default_hash_key \
    --input "${SAMPLE}" \
    --output "${SAMPLE_HASHED}" \
    --rounding_sf None
"${FUZZY}" hash \
    --allow_default_hash_key \
    --input "${SAMPLE}" \
    --output "${WORKDIR}/crate_fuzzy_hashed_no_freq.jsonl" \
    --without_frequencies
"${FUZZY}" hash \
    --allow_default_hash_key \
    --input "${SAMPLE}" \
    --output "${WORKDIR}/crate_fuzzy_hashed_with_other_info.jsonl" \
    --rounding_sf None \
    --include_other_info

rm -f "${SAMPLE_CACHE}"
# This should produce matches for most (comparing a sample to itself):
# (a) From plaintext
"${FUZZY}" compare_plaintext \
    --probands "${SAMPLE}" \
    --sample "${SAMPLE}" \
    --sample_cache "${SAMPLE_CACHE}" \
    --output "${COMPARISON_P2P}"

# (b) From the cache at the previous step
# This should produce matches for most (comparing a sample to itself):
"${FUZZY}" compare_plaintext \
    --probands "${SAMPLE}" \
    --sample "${SAMPLE}" \
    --sample_cache "${SAMPLE_CACHE}" \
    --output "${COMPARISON_P2P}"

# For larger comparisons, see the speedtest script.

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
cmp "${COMPARISON_H2H}" "${COMPARISON_P2P}" || { echo "H2H doesn't match P2P"; exit 1; }

"${FUZZY}" compare_hashed_to_plaintext \
    --allow_default_hash_key \
    --probands "${SAMPLE_HASHED}" \
    --sample "${SAMPLE}" \
    --output "${COMPARISON_H2P}" \
    --n_workers 1 \
    --rounding_sf None
cmp "${COMPARISON_H2P}" "${COMPARISON_P2P}" || { echo "H2P doesn't match P2P"; exit 1; }


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
