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

Show some comparisons in detail. For interactive exploration.

"""

import logging

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger

from crate_anon.linkage.fuzzy_id_match import get_demo_people
from crate_anon.linkage.matchconfig import MatchConfig

log = logging.getLogger(__name__)


def main(
    wholly_different: bool = True,
    asymmetry_forename_count: bool = True,
    asymmetry_surname_frequency: bool = True,
    use_dummy_frequencies: bool = True,
    forename_order_1: bool = True,
    forename_order_2: bool = True,
    no_dob: bool = True,
    verbose: bool = False,
) -> None:
    """
    Command-line entry point.
    """
    main_only_quicksetup_rootlogger(level=logging.INFO)

    if use_dummy_frequencies:
        cfg = None  # dummy frequencies; should still work
    else:
        cfg = MatchConfig()  # proper frequencies

    pp = get_demo_people(cfg)
    az_smith = pp[0]  # Alice Zara SMITH, one postcode
    dww_cartwright = pp[3]  # David William Wallace CARTWRIGHT, two postcodes
    a_smith = pp[10]  # Alice SMITH, one postcode
    a_abadilla = pp[11]  # Alice ABADILLA, one postcode
    za_smith = pp[12]  # Zara Alice SMITH, one postcode
    s_holmes = pp[13]  # Sherlock HOLMES, no DOB

    if wholly_different:
        log.warning("Wholly different")
        az_smith.debug_compare(candidate=dww_cartwright, verbose=verbose)
        dww_cartwright.debug_compare(candidate=az_smith, verbose=verbose)

    if asymmetry_forename_count:
        log.warning("Asymmetric forename count")
        az_smith.debug_compare(candidate=a_smith, verbose=verbose)
        a_smith.debug_compare(candidate=az_smith, verbose=verbose)

    if asymmetry_surname_frequency:
        log.warning("Asymmetric surname frequency")
        a_smith.debug_compare(candidate=a_abadilla, verbose=verbose)
        a_abadilla.debug_compare(candidate=a_smith, verbose=verbose)

    if forename_order_1:
        log.warning("Forename order 1")
        az_smith.debug_compare(candidate=az_smith, verbose=verbose)
        az_smith.debug_compare(candidate=za_smith, verbose=verbose)

    if forename_order_2:
        log.warning("Forename order 2")
        a_smith.debug_compare(candidate=az_smith, verbose=verbose)
        a_smith.debug_compare(candidate=za_smith, verbose=verbose)

    if no_dob:
        log.warning("No DOB")
        s_holmes.debug_compare(candidate=s_holmes, verbose=verbose)


if __name__ == "__main__":
    main()
