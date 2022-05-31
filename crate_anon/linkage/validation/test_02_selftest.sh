#!/usr/bin/env bash
set -e
set -x

FUZZY=crate_fuzzy_id_match

THIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
VALIDATOR=${THIS_DIR}/validate_fuzzy_linkage.py

WORKDIR=${HOME}/.local/share/crate
SAMPLE=${WORKDIR}/crate_fuzzy_sample.csv
SAMPLE_10K=${WORKDIR}/crate_fuzzy_sample_10k.csv
SAMPLE_HASHED=${WORKDIR}/crate_fuzzy_hashed.csv

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
    --output "${WORKDIR}/crate_fuzzy_hashed_no_freq.csv" \
    --without_frequencies

# This should produce matches for most (comparing a sample to itself):
"${FUZZY}" compare_plaintext \
    --probands "${SAMPLE}" \
    --sample "${SAMPLE}" \
    --output "${WORKDIR}/crate_fuzzy_output_p2p.csv"

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
    --output "${WORKDIR}/crate_fuzzy_output_h2h.csv"

"${FUZZY}" compare_hashed_to_plaintext \
    --allow_default_hash_key \
    --probands "${SAMPLE_HASHED}" \
    --sample "${SAMPLE}" \
    --output "${WORKDIR}/crate_fuzzy_output_h2p.csv"

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
