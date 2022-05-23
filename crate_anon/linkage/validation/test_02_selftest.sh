#!/usr/bin/env bash
set -e
set -x

THIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
WORKDIR=${TMPDIR:-/tmp}
SAMPLE="${WORKDIR}/crate_fuzzy_sample.csv"
SAMPLE_10K="${WORKDIR}/crate_fuzzy_sample_10k.csv"
SAMPLE_HASHED="${WORKDIR}/crate_fuzzy_hashed.csv"
VALIDATOR="${THIS_DIR}/validate_fuzzy_linkage.py"
FUZZY=crate_fuzzy_id_match

"${VALIDATOR}" speedtest
"${VALIDATOR}" validate1 \
    --people "${SAMPLE}" \
    --output "${WORKDIR}/crate_fuzzy_validation1_output.csv"

"${FUZZY}" show_metaphone JANE JOHN ISADORA KIT
"${FUZZY}" show_forename_freq JANE JOHN ISADORA KIT
"${FUZZY}" show_forename_metaphone_freq JN JN ASTR KT

"${FUZZY}" show_metaphone SMITH JONES SHAKESPEARE TELL
"${FUZZY}" show_surname_freq SMITH JONES SHAKESPEARE TELL
"${FUZZY}" show_surname_metaphone_freq SM0 JNS XKSP TL

"${FUZZY}" show_dob_freq  # no arguments

"${FUZZY}" --allow_default_hash_key hash \
    --input "${SAMPLE}" \
    --output "${SAMPLE_HASHED}"
"${FUZZY}" --allow_default_hash_key hash \
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

"${FUZZY}" compare_hashed_to_hashed \
    --probands "${SAMPLE_HASHED}" \
    --sample "${SAMPLE_HASHED}" \
    --output "${WORKDIR}/crate_fuzzy_output_h2h.csv"

"${FUZZY}" --allow_default_hash_key compare_hashed_to_plaintext \
    --probands "${SAMPLE_HASHED}" \
    --sample "${SAMPLE}" \
    --output "${WORKDIR}/crate_fuzzy_output_h2p.csv"

# validate2_fetch_cdl
# validate2_fetch_rio

# For Figure 3, a demonstration of the Bayesian approach:
"${FUZZY}" compare_plaintext \
    --probands "${WORKDIR}/crate_fuzzy_demo_fig3_probands.csv" \
    --sample "${WORKDIR}/crate_fuzzy_demo_fig3_sample.csv" \
    --output "${WORKDIR}/crate_fuzzy_demo_fig3_output.csv"
