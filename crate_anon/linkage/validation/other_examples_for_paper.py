#!/usr/bin/env python

"""
crate_anon/linkage/validation/other_examples_for_paper.py

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

Some specific examples used in the validation paper for demonstration.

"""

import logging

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger

from crate_anon.linkage.constants import GENDER_MALE
from crate_anon.linkage.identifiers import Forename, SurnameFragment
from crate_anon.linkage.matchconfig import MatchConfig

log = logging.getLogger(__name__)


def main() -> None:
    main_only_quicksetup_rootlogger(level=logging.INFO)

    cfg = MatchConfig()  # use defaults

    j = Forename(cfg, name="JAMES", gender=GENDER_MALE)
    log.info(repr(j))
    log.info(
        f"Compare full (p_c = {j.p_c} / p_f = {j.p_f}) "
        f"and partial1 (p_ep1 = {j.p_ep1} / p_p1nf = {j.p_p1nf}))"
    )

    a = SurnameFragment(cfg, name="ALLEN")
    log.info(repr(a))
    log.info(
        f"Compare partial2 (p_ep2np1 = {a.p_ep2np1} / p_p2np1 = {a.p_p2np1}) "
        f"and nonmatch (p_en = {a.p_en} / p_n = {a.p_n})"
    )


if __name__ == "__main__":
    main()
