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

import os

from crate_anon.linkage.constants import FuzzyDefaults, GENDER_FEMALE
from crate_anon.linkage.fuzzy_id_match import (
    Commands,
    get_demo_people,
)
from crate_anon.linkage.matchconfig import mk_dummy_match_config
from crate_anon.linkage.person import Person
from crate_anon.linkage.person_io import PersonWriter, write_people


def mk_large(filename: str, n: int) -> None:
    print(f"- Creating {filename}")
    people = get_demo_people()
    with PersonWriter(filename=filename, plaintext=True) as writer:
        i = 1
        done = False
        while not done:
            for person in people:
                person.local_id = f"id_{i}"
                writer.write(person)
                i += 1
                if i > n:
                    done = True
                    break


def main() -> None:
    cfg = mk_dummy_match_config()
    p1 = Person(
        cfg=cfg,
        local_id="1",
        forenames=["Alice"],
        surnames=["Jones"],
        dob="1950-01-01",
        gender=GENDER_FEMALE,
    )
    p2 = Person(
        cfg=cfg,
        local_id="2",
        forenames=["Alice"],
        surnames=["Smith"],
        dob="1994-07-29",
        gender=GENDER_FEMALE,
    )
    p3 = Person(
        cfg=cfg,
        local_id="3",
        forenames=["Alice"],
        surnames=["Smith"],
        dob="1950-01-01",
        gender=GENDER_FEMALE,
    )
    p4 = Person(
        cfg=cfg,
        local_id="4",
        forenames=["Alys"],
        surnames=["Smith"],
        dob="1950-01-01",
        gender=GENDER_FEMALE,
    )
    p5 = Person(
        cfg=cfg,
        local_id="5",
        forenames=["Alys"],
        surnames=["Smythe"],
        dob="1950-01-01",
        gender=GENDER_FEMALE,
    )

    sample_base = os.path.join(
        FuzzyDefaults.DEFAULT_CACHE_DIR, "crate_fuzzy_sample.csv"
    )
    print(f"- Creating {sample_base}")
    os.system(
        f'crate_fuzzy_id_match {Commands.PRINT_DEMO_SAMPLE} > "{sample_base}"'
    )

    mk_large(
        os.path.join(
            FuzzyDefaults.DEFAULT_CACHE_DIR, "crate_fuzzy_sample_1k.csv"
        ),
        1000,
    )
    mk_large(
        os.path.join(
            FuzzyDefaults.DEFAULT_CACHE_DIR, "crate_fuzzy_sample_10k.csv"
        ),
        10000,
    )
    write_people(
        filename=os.path.join(
            FuzzyDefaults.DEFAULT_CACHE_DIR, "crate_fuzzy_demo_fig3_sample.csv"
        ),
        people=[p1, p2, p3, p4, p5],
        plaintext=True,
    )
    write_people(
        filename=os.path.join(
            FuzzyDefaults.DEFAULT_CACHE_DIR,
            "crate_fuzzy_demo_fig3_probands.csv",
        ),
        people=[p3],
        plaintext=True,
    )


if __name__ == "__main__":
    main()
