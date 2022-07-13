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

from crate_anon.linkage.comparison import DirectComparison
from crate_anon.linkage.identifiers import Forename
from crate_anon.linkage.matchconfig import MatchConfig

log = logging.getLogger(__name__)


def main() -> None:
    main_only_quicksetup_rootlogger(level=logging.INFO)

    cfg = MatchConfig()  # use defaults
    james = Forename(cfg, name="JAMES")
    log.info(repr(james))

    p_f = 0.0295
    p_p1nf = 0.000133

    p_ep1 = 0.0084
    p_c = 0.978

    comparison_full_match = DirectComparison(
        p_d_given_same_person=p_c,
        p_d_given_diff_person=p_f,
        d_description="full_match",
    )
    comparison_partial_match = DirectComparison(
        p_d_given_same_person=p_ep1,
        p_d_given_diff_person=p_p1nf,
        d_description="partial_match_1_metaphone_not_full",
    )
    log.info(repr(comparison_full_match))
    log.info(repr(comparison_partial_match))


if __name__ == "__main__":
    main()
