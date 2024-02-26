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

These implement the maths without regard to the kind of identifier being
compared. Includes classes for full/partial matches, and a function to iterate
through a bunch of comparisons as part of a Bayesian probability calculation.
The hypothesis H throughout is that two people being compared are in fact the
same person.

"""


# =============================================================================
# Imports
# =============================================================================

from typing import Iterable, Optional

from cardinal_pythonlib.reprfunc import auto_repr

from crate_anon.linkage.helpers import (
    log_likelihood_ratio_from_p,
    log_posterior_odds_from_pdh_pdnh,
)
from crate_anon.linkage.constants import INFINITY, MINUS_INFINITY


# =============================================================================
# Simple person-related probability calculations
# =============================================================================


class Comparison:
    """
    Abstract base class for comparing two pieces of information and calculating
    the posterior probability of a person match.

    This code must be fast, so avoid extraneous parameters.
    """

    def __init__(self) -> None:
        pass

    def __str__(self) -> str:
        """
        Returns a brief description.
        """
        return (
            f"{self.d_description} "
            f"[P(D|H)={self.p_d_given_h}, "
            f"P(D|¬H)={self.p_d_given_not_h}]"
        )

    def __repr__(self) -> str:
        return auto_repr(self)

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

    @property
    def log_likelihood_ratio(self) -> float:
        return log_likelihood_ratio_from_p(
            self.p_d_given_h, self.p_d_given_not_h
        )

    def posterior_log_odds(self, prior_log_odds: float) -> float:
        """
        Returns the posterior log odds, given the prior log odds. Often
        overriden in derived classes for a faster version.

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


class ImpossibleComparison(Comparison):
    """
    Special comparison to denote impossibility/failure, i.e. for when P(D | H)
    = 0, that doesn't bother with all the calculations involved in calculating
    a likelihood ratio of 0.
    """

    @property
    def d_description(self) -> str:
        return "ImpossibleComparison"

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


class CertainComparison(Comparison):
    """
    Special comparison to denote failure, i.e. for when P(D | H) = 0, that
    doesn't bother with all the calculations involved in calculating a
    likelihood ratio of 0.
    """

    @property
    def d_description(self) -> str:
        return "CertainComparison"

    @property
    def p_d_given_h(self) -> float:
        # Unimportant as long as it's not 0.
        return 1

    @property
    def p_d_given_not_h(self) -> float:
        # Not used. But zero.
        return 0  # makes things "in principle" calculable

    def posterior_log_odds(self, prior_log_odds: float) -> float:
        # Nice and quick:
        return INFINITY


class DirectComparison(Comparison):
    r"""
    Represents a comparison where the user supplies :math:`P(D | H)` and
    :math:`P(D | \neg H)` directly. This is the fastest real comparison. It
    precalculates the log likelihood ratio for speed; that way, our comparison
    can be re-used fast.
    """

    def __init__(
        self,
        p_d_given_same_person: float,
        p_d_given_diff_person: float,
        d_description: str = "?",
    ) -> None:
        r"""
        Args:
            p_d_given_same_person: :math:`P(D | H)`
            p_d_given_diff_person: :math:`P(D | \neg H)`
        """
        super().__init__()
        self._p_d_given_h = p_d_given_same_person
        self._p_d_given_not_h = p_d_given_diff_person
        self._log_likelihood_ratio = log_likelihood_ratio_from_p(
            p_d_given_h=p_d_given_same_person,
            p_d_given_not_h=p_d_given_diff_person,
        )
        self._description = d_description

    def __str__(self) -> str:
        return (
            f"DirectComparison"
            f"[{self._description}, "
            f"P(D|H)={self.p_d_given_h}, "
            f"P(D|¬H)={self.p_d_given_not_h}, "
            f"log_likelihood_ratio={self._log_likelihood_ratio}]"
        )

    @property
    def d_description(self) -> str:
        return self._description

    @property
    def p_d_given_h(self) -> float:
        return self._p_d_given_h

    @property
    def p_d_given_not_h(self) -> float:
        return self._p_d_given_not_h

    @property
    def log_likelihood_ratio(self) -> float:
        return self._log_likelihood_ratio

    def posterior_log_odds(self, prior_log_odds: float) -> float:
        # Fast version.
        # (You can't use use numba to compile a member function; the only
        # option is numba.jitclass() on the whole class. And making
        # DirectComparison a jitclass actually slowed things down.)
        return prior_log_odds + self._log_likelihood_ratio


class MatchNoMatchComparison(Comparison):
    """
    Represents a comparison when there can be a match or not.

    The purpose of this is to represent this choice CLEARLY. Code that produces
    one of these could equally produce one of two :class:`DirectComparison`
    objects, conditional upon ``match``, but this is often clearer.

    Not currently used in main code.
    """

    def __init__(
        self,
        match: bool,
        p_match_given_same_person: float,
        p_match_given_diff_person: float,
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
        super().__init__()
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

    Not currently used in main code.
    """

    def __init__(
        self,
        full_match: bool,
        p_f: float,
        p_e: float,
        partial_match: bool,
        p_p: float,
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
        super().__init__()
        assert p_f <= p_p, f"p_p={p_p} < p_f={p_f}, but should have p_f <= p_p"
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


class AdjustLogOddsComparison(Comparison):
    """
    Used to adjust log odds (via the log likelihood ratio) directly. See
    :func:`crate_anon.linkage.identifiers.gen_best_comparisons_unordered`.
    """

    BAD_METHOD = "Bad method"

    def __init__(
        self,
        log_odds_delta: float,
        description: str = "?",
    ) -> None:
        super().__init__()
        self._p_d_given_h = None
        self._p_d_given_not_h = None
        self._log_likelihood_ratio = log_odds_delta
        self._description = description

    def __str__(self) -> str:
        return (
            f"AdjustLogOddsComparison[{self._description}, "
            f"log_odds_delta={self._log_likelihood_ratio}]"
        )

    @property
    def d_description(self) -> str:
        return self._description

    @property
    def p_d_given_h(self) -> float:
        raise AssertionError(self.BAD_METHOD)

    @property
    def p_d_given_not_h(self) -> float:
        raise AssertionError(self.BAD_METHOD)

    @property
    def log_likelihood_ratio(self) -> float:
        return self._log_likelihood_ratio

    def posterior_log_odds(self, prior_log_odds: float) -> float:
        return prior_log_odds + self._log_likelihood_ratio


# =============================================================================
# The main Bayesian comparison point
# =============================================================================


def bayes_compare(
    log_odds: float,
    comparisons: Iterable[Optional[Comparison]],
) -> float:
    """
    Works through multiple comparisons and returns posterior log odds.
    Ignore comparisons that are ``None``.

    Args:
        log_odds: prior log odds
        comparisons: an iterable of :class:`Comparison` objects

    Returns:
        float: posterior log odds
    """
    # High speed function.
    # Fractionally faster to call the incoming parameter "log_odds" and not
    # assign it to a further variable here.
    for comparison in filter(None, comparisons):
        log_odds = comparison.posterior_log_odds(log_odds)
        # If there is a realistic chance of hitting -∞, this saves time:
        if log_odds == MINUS_INFINITY:
            return MINUS_INFINITY
        # We could check for +∞ too, but that (via PerfectID) is done outside
        # the Bayesian process.
    return log_odds
