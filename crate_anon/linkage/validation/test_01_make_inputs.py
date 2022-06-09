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
    SimplePerson,
    FuzzyDefaults,
    get_demo_people,
)


def mk_large(filename: str, n: int) -> None:
    print(f"- Creating {filename}")
    people = get_demo_people()
    with open(filename, "wt") as f_:
        writer = csv.DictWriter(f_, fieldnames=SimplePerson.ALL_PERSON_KEYS)
        writer.writeheader()
        i = 1
        done = False
        while not done:
            for person in people:
                person.local_id = f"id_{i}"
                writer.writerow(person.plaintext_csv_dict())
                i += 1
                if i > n:
                    done = True
                    break


def write_file(filename: str, contents: str) -> None:
    print(f"- Creating {filename}")
    with open(filename, "wt") as f:
        writeline_nl(f, contents.strip())


SAMPLE_BASE = os.path.join(
    FuzzyDefaults.DEFAULT_CACHE_DIR, "crate_fuzzy_sample.csv"
)
print(f"- Creating {SAMPLE_BASE}")
os.system(f'crate_fuzzy_id_match print_demo_sample > "{SAMPLE_BASE}"')

mk_large(
    os.path.join(FuzzyDefaults.DEFAULT_CACHE_DIR, "crate_fuzzy_sample_1k.csv"),
    1000,
)
mk_large(
    os.path.join(
        FuzzyDefaults.DEFAULT_CACHE_DIR, "crate_fuzzy_sample_10k.csv"
    ),
    10000,
)
write_file(
    filename=os.path.join(
        FuzzyDefaults.DEFAULT_CACHE_DIR, "crate_fuzzy_demo_fig3_sample.csv"
    ),
    contents="""
local_id,first_name,middle_names,surname,dob,gender,postcodes,other_info
1,Alice,,Jones,1950-01-01,F,,
2,Alice,,Smith,1994-07-29,F,,
3,Alice,,Smith,1950-01-01,F,,
4,Alys,,Smith,1950-01-01,F,,
5,Alys,,Smythe,1950-01-01,F,,
    """,
)
write_file(
    filename=os.path.join(
        FuzzyDefaults.DEFAULT_CACHE_DIR, "crate_fuzzy_demo_fig3_probands.csv"
    ),
    contents="""
local_id,first_name,middle_names,surname,dob,gender,postcodes,other_info
3,Alice,,Smith,1950-01-01,F,,
    """,
)
