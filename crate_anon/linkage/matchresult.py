#!/usr/bin/env python

r"""
crate_anon/linkage/matchresult.py

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

**Match result for fuzzy matching.**

"""

# =============================================================================
# Imports
# =============================================================================

from crate_anon.linkage.constants import MINUS_INFINITY
from crate_anon.linkage.person import Person


# =============================================================================
# Result of a match attempt
# =============================================================================


class MatchResult:
    """
    Result of a comparison between a proband (person) and a sample (group of
    people).
    """

    def __init__(
        self,
        winner: Person = None,
        best_log_odds: float = MINUS_INFINITY,
        second_best_log_odds: float = MINUS_INFINITY,
        best_candidate: Person = None,
        second_best_candidate: Person = None,
        proband: Person = None,
    ):
        """
        Args:
            winner:
                The person in the sample (candidate) who matches the proband,
                if there is a winner by our rules; ``None`` if there is no
                winner.
            best_log_odds:
                Natural log odds of the best candidate being the same as the
                proband, –∞ if there are no candidates
            second_best_log_odds:
                The log odds of the closest other contender, which may be  –∞.
            best_candidate:
                The person in the sample (candidate) who is the closest match
                to the proband. May be ``None``. If there is a winner, this is
                also the best person -- but the best person may not be the
                winner (if they are not likely enough, or if there is another
                close contender).
            second_best_candidate:
                The runner-up (second-best) candidate person, or ``None``.
            proband:
                The proband used for the comparison. (Helpful for parallel
                processing.)
        """
        self.winner = winner
        self.best_log_odds = best_log_odds
        self.second_best_log_odds = second_best_log_odds
        self.best_candidate = best_candidate
        self.second_best_candidate = second_best_candidate
        self.proband = proband

    @property
    def matched(self) -> bool:
        return self.winner is not None

    def __repr__(self) -> str:
        attrs = [
            f"winner={self.winner}",
            f"best_log_odds={self.best_log_odds}",
            f"second_best_log_odds={self.second_best_log_odds}",
            f"best_candidate={self.best_candidate}",
            f"second_best_candidate={self.second_best_candidate}",
            f"proband={self.proband}",
        ]
        return f"MatchResult({', '.join(attrs)}"
