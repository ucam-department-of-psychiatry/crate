#!/bin/bash
set -e

cd ~/.local/share/crate/

SOURCE_1K=crate_fuzzy_sample_1k.csv
SOURCE_10K=crate_fuzzy_sample_10k.csv
OUTPUT_1K_SERIAL=crate_fuzzy_output_1k_serial.csv
OUTPUT_1K_PARALLEL=crate_fuzzy_output_1k_parallel.csv
OUTPUT_10K_SERIAL=crate_fuzzy_output_10k_serial.csv
OUTPUT_10K_PARALLEL=crate_fuzzy_output_10k_parallel.csv

if true; then
    crate_fuzzy_id_match compare_plaintext \
        --probands "${SOURCE_1K}" \
        --sample "${SOURCE_1K}" \
        --output "${OUTPUT_1K_SERIAL}" \
        --n_workers 1

    crate_fuzzy_id_match compare_plaintext \
        --probands "${SOURCE_1K}" \
        --sample "${SOURCE_1K}" \
        --output "${OUTPUT_1K_PARALLEL}"
    cmp "${OUTPUT_1K_SERIAL}" "${OUTPUT_1K_PARALLEL}" || { echo "parallel/serial mismatch"; exit 1; }
fi

if true; then
    crate_fuzzy_id_match compare_plaintext \
        --probands "${SOURCE_10K}" \
        --sample "${SOURCE_10K}" \
        --output "${OUTPUT_10K_SERIAL}" \
        --n_workers 1

    crate_fuzzy_id_match compare_plaintext \
        --probands "${SOURCE_10K}" \
        --sample "${SOURCE_10K}" \
        --output "${OUTPUT_10K_PARALLEL}"
    cmp "${OUTPUT_10K_SERIAL}" "${OUTPUT_10K_PARALLEL}" || { echo "parallel/serial mismatch"; exit 1; }
fi
