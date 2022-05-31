#!/usr/bin/env bash
set -e

# THIS_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
WORKDIR=${HOME}/.local/share/crate
SAMPLE_BASE=${WORKDIR}/crate_fuzzy_sample.csv
SAMPLE_10K=${WORKDIR}/crate_fuzzy_sample_10k.csv

echo - Creating "${SAMPLE_BASE}"
crate_fuzzy_id_match print_demo_sample > "${SAMPLE_BASE}"

echo - Creating "${SAMPLE_10K}"
cp "${SAMPLE_BASE}" "${SAMPLE_10K}"
# https://github.com/koalaman/shellcheck/wiki/SC2034
for _ in {1..908}; do
    tail -n +2 "${SAMPLE_BASE}" >> "${SAMPLE_10K}"
    # ... everything except first line
done

echo - Creating "${WORKDIR}/crate_fuzzy_demo_fig3_sample.csv"
cat <<EOT > "${WORKDIR}/crate_fuzzy_demo_fig3_sample.csv"
local_id,first_name,middle_names,surname,dob,gender,postcodes,other_info
1,Alice,,Jones,1950-01-01,F,,
2,Alice,,Smith,1994-07-29,F,,
3,Alice,,Smith,1950-01-01,F,,
4,Alys,,Smith,1950-01-01,F,,
5,Alys,,Smythe,1950-01-01,F,,
EOT

echo - Creating "${WORKDIR}/crate_fuzzy_demo_fig3_probands.csv"
cat <<EOT > "${WORKDIR}/crate_fuzzy_demo_fig3_probands.csv"
local_id,first_name,middle_names,surname,dob,gender,postcodes,other_info
3,Alice,,Smith,1950-01-01,F,,
EOT
