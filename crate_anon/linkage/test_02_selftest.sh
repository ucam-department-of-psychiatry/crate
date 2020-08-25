#!/usr/bin/env bash
set -e
set -x

# THIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
WORKDIR=${TMPDIR:-/tmp}
SAMPLE="${WORKDIR}/crate_fuzzy_sample.csv"
SAMPLE_10K="${WORKDIR}/crate_fuzzy_sample_10k.csv"
SAMPLE_HASHED="${WORKDIR}/crate_fuzzy_hashed.csv"

crate_fuzzy_id_match selftest
crate_fuzzy_id_match speedtest
crate_fuzzy_id_match validate1 \
    --people "${SAMPLE}" \
    --output "${WORKDIR}/crate_fuzzy_validation1_output.csv"

crate_fuzzy_id_match show_metaphone JANE JOHN ISADORA KIT
crate_fuzzy_id_match show_forename_freq JANE JOHN ISADORA KIT
crate_fuzzy_id_match show_forename_metaphone_freq JN JN ASTR KT

crate_fuzzy_id_match show_metaphone SMITH JONES SHAKESPEARE TELL
crate_fuzzy_id_match show_surname_freq SMITH JONES SHAKESPEARE TELL
crate_fuzzy_id_match show_surname_metaphone_freq SM0 JNS XKSP TL

crate_fuzzy_id_match show_dob_freq  # no arguments

crate_fuzzy_id_match --allow_default_hash_key hash \
    --input "${SAMPLE}" \
    --output "${SAMPLE_HASHED}"
crate_fuzzy_id_match --allow_default_hash_key hash \
    --input "${SAMPLE}" \
    --output "${WORKDIR}/crate_fuzzy_hashed_no_freq.csv" \
    --without_frequencies

# This should produce matches for most (comparing a sample to itself):
crate_fuzzy_id_match compare_plaintext \
    --probands "${SAMPLE}" \
    --sample "${SAMPLE}" \
    --output "${WORKDIR}/crate_fuzzy_output_p2p.csv"

# This should produce matches for none, since they are internally duplicated!
# It's here primarily as a speed test.
crate_fuzzy_id_match compare_plaintext \
    --probands "${SAMPLE_10K}" \
    --sample "${SAMPLE_10K}" \
    --output "${WORKDIR}/crate_fuzzy_output_10k.csv"

crate_fuzzy_id_match compare_hashed_to_hashed \
    --probands "${SAMPLE_HASHED}" \
    --sample "${SAMPLE_HASHED}" \
    --output "${WORKDIR}/crate_fuzzy_output_h2h.csv"

crate_fuzzy_id_match --allow_default_hash_key compare_hashed_to_plaintext \
    --probands "${SAMPLE_HASHED}" \
    --sample "${SAMPLE}" \
    --output "${WORKDIR}/crate_fuzzy_output_h2p.csv"

# validate2_fetch_cdl
# validate2_fetch_rio

# For Figure 3, a demonstration of the Bayesian approach:
crate_fuzzy_id_match compare_plaintext \
    --probands "${WORKDIR}/crate_fuzzy_demo_fig3_probands.csv" \
    --sample "${WORKDIR}/crate_fuzzy_demo_fig3_sample.csv" \
    --output "${WORKDIR}/crate_fuzzy_demo_fig3_output.csv"
