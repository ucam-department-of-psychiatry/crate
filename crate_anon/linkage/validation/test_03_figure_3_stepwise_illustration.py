#!/usr/bin/env python

"""
crate_anon/linkage/validation/test_04_verbose_comparison.py

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

Create an illustration for Figure 3. This compares a fictional proband to
themself and a few other people of varying similarity.

"""

import logging
from typing import List

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger

from crate_anon.linkage.constants import GENDER_FEMALE
from crate_anon.linkage.matchconfig import MatchConfig
from crate_anon.linkage.person import Person

log = logging.getLogger(__name__)


def main(verbose: bool = False, postcodes: bool = True) -> None:
    """
    Command-line entry point.
    """
    main_only_quicksetup_rootlogger(level=logging.INFO)

    cfg = MatchConfig()

    def maybe_postcode(p: str) -> List[str]:
        return [p] if postcodes else []

    proband = Person(
        cfg,
        local_id="proband",
        surnames=["SMITH"],
        forenames=["Elizabeth"],
        dob="1950-01-01",
        gender=GENDER_FEMALE,
        postcodes=maybe_postcode("CB2 0QQ"),
    )
    other1 = Person(
        cfg,
        local_id="other1",
        surnames=["JONES"],
        forenames=["Elizabeth"],
        dob="1950-01-01",
        gender=GENDER_FEMALE,
        postcodes=maybe_postcode("CB2 0ZZ"),  # same sector
    )
    other2 = Person(
        cfg,
        local_id="other2",
        surnames=["SMITH"],
        forenames=["Elizabeth"],
        dob="1984-07-29",
        gender=GENDER_FEMALE,
        postcodes=maybe_postcode("CB2 1TP"),  # no match
    )
    other3 = Person(
        cfg,
        local_id="other3",
        surnames=["SMALL"],
        forenames=["Elisabeth"],
        dob="1950-01-01",
        gender=GENDER_FEMALE,
        postcodes=maybe_postcode("CB99 9XY"),  # no match
    )
    other4 = Person(
        cfg,
        local_id="other4",
        surnames=["SMYTHE"],
        forenames=["Elisabeth"],
        dob="1960-01-01",
        gender=GENDER_FEMALE,
        postcodes=maybe_postcode("ZZ99 3VZ"),  # no match, pseudopostcode
    )

    test_people = [other1, other2, proband, other3, other4]
    # test_people = [proband]

    spacer = "=" * 79

    for p in test_people:
        log.info(spacer)
        if verbose:
            log.warning(p.as_dict(hashed=False))
            log.warning(p.as_dict(hashed=True))
        proband.debug_compare(p, verbose=False)


if __name__ == "__main__":
    main()
