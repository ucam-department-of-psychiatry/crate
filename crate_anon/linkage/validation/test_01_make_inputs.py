#!/usr/bin/env python

"""
crate_anon/linkage/validation/test_01_make_inputs.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

    This file is part of CRATE.

    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

Create some test data for fuzzy linkage validation.

"""

import csv
import os

from cardinal_pythonlib.file_io import writeline_nl
from crate_anon.linkage.fuzzy_id_match import (
    BasePerson,
    FuzzyDefaults,
    get_demo_people,
)

SAMPLE_BASE = os.path.join(
    FuzzyDefaults.DEFAULT_CACHE_DIR, "crate_fuzzy_sample.csv"
)
SAMPLE_10K = os.path.join(
    FuzzyDefaults.DEFAULT_CACHE_DIR, "crate_fuzzy_sample_10k.csv"
)

print(f"- Creating {SAMPLE_BASE}")
os.system(f'crate_fuzzy_id_match print_demo_sample > "{SAMPLE_BASE}"')

print(f"- Creating {SAMPLE_10K}")
people = get_demo_people()
with open(SAMPLE_10K, "wt") as f:
    writer = csv.DictWriter(f, fieldnames=BasePerson.PLAINTEXT_ATTRS)
    writer.writeheader()
    i = 1
    n_to_write = 10000
    done = False
    while not done:
        for person in people:
            person.local_id = f"id_{i}"
            writer.writerow(person.plaintext_csv_dict())
            i += 1
            if i > n_to_write:
                done = True
                break

FIG3_SAMPLE = os.path.join(
    FuzzyDefaults.DEFAULT_CACHE_DIR, "crate_fuzzy_demo_fig3_sample.csv"
)
print(f"- Creating {FIG3_SAMPLE}")
fig3_sample_lines = """
local_id,first_name,middle_names,surname,dob,gender,postcodes,other_info
1,Alice,,Jones,1950-01-01,F,,
2,Alice,,Smith,1994-07-29,F,,
3,Alice,,Smith,1950-01-01,F,,
4,Alys,,Smith,1950-01-01,F,,
5,Alys,,Smythe,1950-01-01,F,,
""".strip()
with open(FIG3_SAMPLE, "wt") as f:
    writeline_nl(f, fig3_sample_lines)

FIG3_PROBANDS = os.path.join(
    FuzzyDefaults.DEFAULT_CACHE_DIR, "crate_fuzzy_demo_fig3_probands.csv"
)
print(f"- Creating {FIG3_PROBANDS}")
fig3_proband_lines = """
local_id,first_name,middle_names,surname,dob,gender,postcodes,other_info
3,Alice,,Smith,1950-01-01,F,,
""".strip()
with open(FIG3_SAMPLE, "wt") as f:
    writeline_nl(f, fig3_sample_lines)
