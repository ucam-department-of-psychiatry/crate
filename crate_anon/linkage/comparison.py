#!/usr/bin/env python

r"""
crate_anon/linkage/comparison.py

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

**Comparison classes for linkage tools.**

These implement the maths without regard to what sort of identifier is being
compared. Includes classes for full/partial matches, and a function to iterate
through a bunch of comparisons as part of a Bayesian probability calculation.
The hypothesis H throughout is that two people being compared are in fact the
same person.

"""


# =============================================================================
# Imports
# =============================================================================

from typing import Iterable, Optional

from crate_anon.linkage.helpers import log_posterior_odds_from_pdh_pdnh
from crate_anon.linkage.constants import MINUS_INFINITY


# =============================================================================
# Simple person-related probability calculations
# =============================================================================


class Comparison(object):
    """
    Abstract base class for comparing two pieces of information and calculating
    the posterior probability of a person match.
    """

    def __init__(self, name: str) -> None:
        """
        Args:
            name: name of this comparison, for cosmetic purposes
        """
        self.name = name

    def __str__(self) -> str:
        """
        Returns a brief description.
        """
        return (
            f"{self.name}: {self.d_description} "
            f"[P(D|H)={self.p_d_given_h}, "
            f"P(D|¬H)={self.p_d_given_not_h}]"
        )

    @property
    def d_description(self) -> str:
        """
        A description of D, the data (e.g. "match" or "mismatch").
        """
        raise NotImplementedError("Implement in derived class!")

    @property
    def p_d_given_h(self) -> float:
        """
        Returns :math:`P(D | H)`, the probability of the observed data given
        the hypothesis of a match.
        """
        raise NotImplementedError("Implement in derived class!")

    @property
    def p_d_given_not_h(self) -> float:
        """
        Returns :math:`P(D | ¬H)`, the probability of the observed data given
        no match.
        """
        raise NotImplementedError("Implement in derived class!")

    def posterior_log_odds(self, prior_log_odds: float) -> float:
        """
        Args:
            prior_log_odds:
                prior log odds that they're the same person

        Returns:
            float: posterior log odds, O(H | D), as above
        """
        # if self.p_d_given_h == 0:
        #     # Shortcut: P(H | D) must be 0 (since likelihood ratio is 0)
        #     return MINUS_INFINITY
        # ... but: a Python shortcut is slower than a compiled log.
        return log_posterior_odds_from_pdh_pdnh(
            log_prior_odds=prior_log_odds,
            p_d_given_h=self.p_d_given_h,
            p_d_given_not_h=self.p_d_given_not_h,
        )


class FailureComparison(Comparison):
    """
    Special comparison to denote failure, i.e. for when P(D | H) = 0, that
    doesn't bother with all the calculations involved in calculating a
    likelihood ratio of 0.

    Currently unused.
    """

    @property
    def d_description(self) -> str:
        return "FailureComparison"

    @property
    def p_d_given_h(self) -> float:
        return 0

    @property
    def p_d_given_not_h(self) -> float:
        # Unimportant!
        return 1  # makes things "in principle" calculable

    def posterior_log_odds(self, prior_log_odds: float) -> float:
        # Nice and quick:
        return MINUS_INFINITY


class DirectComparison(Comparison):
    r"""
    Represents a comparison where the user supplies :math:`P(D | H)` and
    :math:`P(D | \neg H)` directly.
    """

    def __init__(
        self,
        p_d_given_same_person: float,
        p_d_given_diff_person: float,
        **kwargs,
    ) -> None:
        r"""
        Args:
            p_d_given_same_person: :math:`P(D | H)`
            p_d_given_diff_person: :math:`P(D | \neg H)`
        """
        super().__init__(**kwargs)
        # if CHECK_BASIC_ASSERTIONS_IN_HIGH_SPEED_FUNCTIONS:
        #     assert 0 <= p_d_given_same_person <= 1
        #     assert 0 <= p_d_given_diff_person <= 1
        self._p_d_given_h = p_d_given_same_person
        self._p_d_given_not_h = p_d_given_diff_person

    @property
    def d_description(self) -> str:
        return ""

    @property
    def p_d_given_h(self) -> float:
        return self._p_d_given_h

    @property
    def p_d_given_not_h(self) -> float:
        return self._p_d_given_not_h


class MatchNoMatchComparison(Comparison):
    """
    Represents a comparison when there can be a match or not.

    The purpose of this is to represent this choice CLEARLY. Code that produces
    one of these could equally produce one of two :class:`DirectComparison`
    objects, conditional upon ``match``, but this is often clearer.
    """

    def __init__(
        self,
        match: bool,
        p_match_given_same_person: float,
        p_match_given_diff_person: float,
        **kwargs,
    ) -> None:
        r"""
        Args:
            match:
                D; is there a match?
            p_match_given_same_person:
                If match:
                :math:`P(D | H) = P(\text{match given same person}) = 1 - p_e`.
                If no match:
                :math:`P(D | H) = 1 - P(\text{match given same person}) = p_e`.
            p_match_given_diff_person:
                If match:
                :math:`P(D | \neg H) = P(\text{match given different person}) = p_f`.
                If no match:
                :math:`P(D | \neg H) = 1 - P(\text{match given different person}) = 1 - p_f`.
        """  # noqa
        super().__init__(**kwargs)
        # if CHECK_BASIC_ASSERTIONS_IN_HIGH_SPEED_FUNCTIONS:
        #     assert 0 <= p_match_given_same_person <= 1
        #     assert 0 <= p_match_given_diff_person <= 1
        self.match = match
        self.p_match_given_same_person = p_match_given_same_person
        self.p_match_given_diff_person = p_match_given_diff_person

    @property
    def d_description(self) -> str:
        return "match" if self.match else "mismatch"

    @property
    def p_d_given_h(self) -> float:
        if self.match:
            return self.p_match_given_same_person  # 1 - p_e
        else:
            return 1 - self.p_match_given_same_person  # p_e

    @property
    def p_d_given_not_h(self) -> float:
        if self.match:
            return self.p_match_given_diff_person  # p_f
        else:
            return 1 - self.p_match_given_diff_person  # 1 - p_f


class FullPartialNoMatchComparison(Comparison):
    """
    Represents a comparison where there can be a full or a partial match.
    (If there is neither a full nor a partial match, the hypothesis is
    rejected.)

    Again, this is for clarity. Code that produces one of these could equally
    produce one of three :class:`DirectComparison` objects, conditional upon
    ``full_match`` and ``partial_match``, but this is generally much clearer.
    """

    def __init__(
        self,
        full_match: bool,
        p_f: float,
        p_e: float,
        partial_match: bool,
        p_p: float,
        **kwargs,
    ) -> None:
        r"""
        Args:
            full_match:
                was there a full match?
            p_f:
                :math:`p_f = P(\text{full match} | \neg H)`
            p_e:
                :math:`p_e = P(\text{partial but not full match} | H)`
            partial_match:
                was there a partial match?
            p_p:
                :math:`p_p = P(\text{partial match} | \neg H)`
        """
        super().__init__(**kwargs)
        # if CHECK_BASIC_ASSERTIONS_IN_HIGH_SPEED_FUNCTIONS:
        #     assert 0 <= p_f <= 1
        #     assert 0 <= p_e <= 1
        #     assert 0 <= p_p <= 1
        # This one is worth checking dynamically:
        assert p_f <= p_p, f"p_f={p_f}, p_p={p_p}, but should have p_f <= p_p"
        self.full_match = full_match
        self.p_f = p_f
        self.p_e = p_e
        self.partial_match = partial_match
        self.p_p = p_p

    @property
    def d_description(self) -> str:
        if self.full_match:
            return "full match"
        elif self.partial_match:
            return "partial match"
        else:
            return "mismatch"

    @property
    def p_d_given_h(self) -> float:
        if self.full_match:
            return 1 - self.p_e
        elif self.partial_match:
            return self.p_e
        else:
            return 0

    @property
    def p_d_given_not_h(self) -> float:
        if self.full_match:
            return self.p_f
        elif self.partial_match:
            return self.p_p - self.p_f
        else:
            return 1 - self.p_p  # IRRELEVANT since p_d_given_h == 0

    def posterior_log_odds(self, prior_log_odds: float) -> float:
        if not self.full_match and not self.partial_match:
            # No match.
            # Shortcut, since p_d_given_h is 0 and therefore LR is 0:
            return MINUS_INFINITY
        return super().posterior_log_odds(prior_log_odds)


# =============================================================================
# The main Bayesian comparison point
# =============================================================================


def bayes_compare(
    prior_log_odds: float,
    comparisons: Iterable[Optional[Comparison]],
) -> float:
    """
    Works through multiple comparisons and returns posterior log odds.
    Ignore comparisons that are ``None``.

    Args:
        prior_log_odds: prior log odds
        comparisons: an iterable of :class:`Comparison` objects

    Returns:
        float: posterior log odds
    """
    log_odds = prior_log_odds
    for comparison in filter(None, comparisons):
        log_odds = comparison.posterior_log_odds(log_odds)
        if log_odds == MINUS_INFINITY:
            return MINUS_INFINITY
    return log_odds