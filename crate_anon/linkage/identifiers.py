#!/usr/bin/env python

r"""
crate_anon/linkage/identifiers.py

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

**Helper functions for linkage tools.**

"""


# =============================================================================
# Imports
# =============================================================================

from typing import Optional, Union

from cardinal_pythonlib.reprfunc import auto_repr
import pendulum
from pendulum.parsing.exceptions import ParserError
from pendulum import Date

from crate_anon.linkage.comparison import (
    Comparison,
    FullPartialNoMatchComparison,
    MatchNoMatchComparison,
)


# =============================================================================
# Identifier with associated temporal information
# =============================================================================


class TemporalIdentifier(object):
    """
    Represents an identifier (typically a postcode, postcode fragment, or
    hashed equivalent) along with start and end dates (which may be ``None``).

    Test code:

    .. code-block:: python

        from crate_anon.linkage.fuzzy_id_match import *

        # Basics, using a postcode example
        tp1 = TemporalIdentifier("CB2 0QQ", None, None)
        print(repr(tp1))
        s1 = str(tp1)
        print(s1)

        # Recovery from string representation
        tp2 = TemporalIdentifier.from_str(s1)
        print(repr(tp2))

    """

    SEP = "/"  # separator
    NULL_VALUES_LOWERCASE = ["none", "null", "?"]  # must include "none"
    FORMAT_HELP = (
        f"TemporalIdentifier format: IDENTIFIER{SEP}STARTDATE{SEP}ENDDATE, "
        f"where dates are in YYYY-MM-DD format or one of "
        f"{NULL_VALUES_LOWERCASE} (case-insensitive)."
    )

    def __init__(
        self, identifier: str, start_date: Date = None, end_date: Date = None
    ) -> None:
        """
        Args:
            identifier:
                The identifier (plaintext or hashed).
            start_date:
                The start date (first valid date), or ``None``.
            end_date:
                The end date (last valid date), or ``None``.
        """
        assert isinstance(identifier, str), f"Bad identifier: {identifier!r}"
        if start_date and end_date:
            assert (
                start_date <= end_date
            ), f"start_date = {start_date!r} > end_date = {end_date!r}"

        self.identifier = identifier
        self.start_date = start_date
        self.end_date = end_date

    # -------------------------------------------------------------------------
    # Representation
    # -------------------------------------------------------------------------

    def __repr__(self) -> str:
        """
        Standardized Python representation.
        """
        return auto_repr(self, sort_attrs=False)

    def __str__(self) -> str:
        """
        Standardized string representation. See also :meth:`from_str`.

        - We'll use standard ISO-8601 notation for dates.
        - Avoid semicolons and commas, which are used elsewhere.
        - These and underscores cannot emerge from the hash function, which
          produces hash digests.
        - Postcodes can't contain underscores either.
        """
        assert (
            self.SEP not in self.identifier
        ), f"Class not suitable for identifiers containing {self.SEP!r}"
        return self.SEP.join(
            [self.identifier, str(self.start_date), str(self.end_date)]
        )

    @classmethod
    def from_str(cls, x: str) -> "TemporalIdentifier":
        """
        Takes the string representation (see :meth:`__str__`) and returns a
        :class:`TemporalIdentifier` object.

        Args:
            x:
                String to parse.

        Returns:
            a :class:`TemporalIdentifier` object

        Raises:
            :exc:`ValueError` if the string is bad.
        """
        # Extract components of the string
        components = x.split(cls.SEP)
        if len(components) != 3:
            raise ValueError(
                f"Need 3 components separated by {cls.SEP!r}; got {x!r}"
            )
        i, s, e = components
        # Start date
        if s.lower() in cls.NULL_VALUES_LOWERCASE:
            s = None
        else:
            try:
                s = pendulum.parse(s).date()
            except ParserError:
                raise ValueError(f"Bad date: {s!r}")
        # End date
        if e.lower() in cls.NULL_VALUES_LOWERCASE:
            e = None
        else:
            try:
                e = pendulum.parse(e).date()
            except ParserError:
                raise ValueError(f"Bad date: {e!r}")
        # Return object
        return TemporalIdentifier(identifier=i, start_date=s, end_date=e)

    # -------------------------------------------------------------------------
    # Comparison
    # -------------------------------------------------------------------------

    def overlaps(self, other: "TemporalIdentifier") -> bool:
        """
        Do ``self`` and ``other`` overlap in time?

        Args:
            other:
                the other :class:`TemporalIdentifier`

        For similar logic, see
        :meth:`cardinal_pythonlib.interval.Interval.overlaps`.
        """
        return not (
            # This inner test is for non-overlap.
            # (a) self ends before other starts
            (
                self.end_date
                and other.start_date
                and self.end_date < other.start_date
            )
            or
            # (b) other ends before self starts
            (
                other.end_date
                and self.start_date
                and other.end_date < self.start_date
            )
        )

    def matches(self, other: "TemporalIdentifier") -> bool:
        """
        Does the postcode (or other string entity) match, and also the dates
        overlap?

        Args:
            other:
                the other :class:`TemporalIdentifier`
        """
        return self.identifier == other.identifier and self.overlaps(other)

    def __eq__(self, other: "TemporalIdentifier") -> bool:
        """
        Equality means a match.

        Args:
            other:
                the other :class:`TemporalIdentifier`
        """
        return self.matches(other)

    def __bool__(self) -> bool:
        """
        Used in e.g. ``if x`` constructs.
        """
        return bool(self.identifier)

    # -------------------------------------------------------------------------
    # Hashing and copying
    # -------------------------------------------------------------------------

    def with_new_identifier(self, identifier: str) -> "TemporalIdentifier":
        """
        Returns a new :class:`TemporalIdentifier` with the same dates, but a
        new identifier.

        Args:
            identifier:
                The new identifier to use.

        Returns:
            a new :class:`TemporalIdentifier`
        """
        return TemporalIdentifier(
            identifier=identifier,
            start_date=self.start_date,
            end_date=self.end_date,
        )


# =============================================================================
# Pair objects for used with hashed comparisons
# =============================================================================


class IdFreq(object):
    """
    Represents an identifier (plaintext or hashed) and its accompanying
    frequency. Performs comparisons using a match/no-match system.
    """

    def __init__(
        self,
        comparison_name: str,
        identifier: Union[str, TemporalIdentifier, None],
        frequency: Optional[float],
        p_error: float,
    ) -> None:
        """
        Args:
            comparison_name:
                Name for the comparison.
            identifier:
                The identifier (plaintext or hashed). Can be a string or a
                :class:`TemporalIdentifier`.
            frequency:
                Its population frequency.
            p_error:
                Probability of a data error transforming "match" to "no match";
                :math:`p_e`.
        """
        assert 0 <= p_error <= 1

        self.comparison_name = comparison_name
        self.identifier = identifier
        self.frequency = frequency
        self.p_no_error = 1 - p_error

        if identifier and frequency is not None:
            assert 0 <= frequency <= 1

    def comparison(self, proband: "IdFreq") -> Optional[Comparison]:
        """
        Comparison against a proband's version.
        """
        if not self.identifier or not proband.identifier:
            # Infer no conclusions from missing information.
            return None
        return MatchNoMatchComparison(
            name=self.comparison_name,
            match=(self.identifier == proband.identifier),
            p_match_given_same_person=proband.p_no_error,
            p_match_given_diff_person=proband.frequency,
        )

    def matches(self, other: "IdFreq") -> bool:
        """
        Is there a match with ``other``?
        """
        if not self.identifier or not other.identifier:
            return False
        return self.identifier == other.identifier

    def assert_has_freq_info_if_id_present(self) -> None:
        """
        If the identifier is present, ensure that frequency information is
        present, or raise :exc:`AssertionError`.
        """
        if self.identifier:
            assert (
                self.frequency is not None
            ), f"{self.comparison_name}: missing frequency"


class FuzzyIdFreq(object):
    """
    Represents an identifier (plaintext or hashed) with its frequency, and a
    fuzzy version, with its frequency. Performs comparisons using a full
    match/partial match/no match system (rejecting the hypothesis completely if
    there is no match).
    """

    def __init__(
        self,
        comparison_name: str,
        exact_identifier: Optional[str],
        exact_identifier_frequency: Optional[float],
        fuzzy_identifier: Optional[str],
        fuzzy_identifier_frequency: Optional[float],
        p_error: float,
    ) -> None:
        """
        Args:
            comparison_name:
                Name for the comparison.
            exact_identifier:
                The full identifier (plaintext or hashed).
            exact_identifier_frequency:
                Its population frequency.
            fuzzy_identifier:
                The fuzzy identifier (plaintext or hashed).
            fuzzy_identifier_frequency:
                Its population frequency.
            p_error:
                Probability of a data error transforming "full match" to
                "partial match"; :math:`p_e`.
        """
        assert 0 <= p_error <= 1

        self.comparison_name = comparison_name
        self.exact_identifier = exact_identifier
        self.exact_identifier_frequency = exact_identifier_frequency
        self.fuzzy_identifier = fuzzy_identifier
        self.fuzzy_identifier_frequency = fuzzy_identifier_frequency
        self.p_error = p_error

        know_exact = (
            exact_identifier and exact_identifier_frequency is not None
        )
        know_fuzzy = (
            fuzzy_identifier and fuzzy_identifier_frequency is not None
        )
        if know_exact:
            assert 0 <= exact_identifier_frequency <= 1
        if know_fuzzy:
            assert 0 <= fuzzy_identifier_frequency <= 1
        if know_exact and know_fuzzy:
            assert exact_identifier_frequency <= fuzzy_identifier_frequency, (
                f"exact_identifier_frequency = {exact_identifier_frequency}, "
                f"fuzzy_identifier_frequency = {fuzzy_identifier_frequency}, "
                f"but should have "
                f"exact_identifier_frequency <= fuzzy_identifier_frequency"
            )

    def __repr__(self) -> str:
        return auto_repr(self)

    def comparison(self, proband: "FuzzyIdFreq") -> Optional[Comparison]:
        """
        Comparison against a proband's version.
        """
        if (
            not self.exact_identifier
            or not proband.exact_identifier
            or not self.fuzzy_identifier
            or not proband.fuzzy_identifier
        ):
            # Infer no conclusions from missing information.
            return None
        return FullPartialNoMatchComparison(
            name=self.comparison_name,
            full_match=(self.exact_identifier == proband.exact_identifier),
            p_f=proband.exact_identifier_frequency,
            p_e=self.p_error,
            partial_match=(self.fuzzy_identifier == proband.fuzzy_identifier),
            p_p=proband.fuzzy_identifier_frequency,
        )

    def fully_matches(self, other: "FuzzyIdFreq") -> bool:
        """
        Is there a full match with ``other``?
        """
        if not self.exact_identifier or not other.exact_identifier:
            return False
        return self.exact_identifier == other.exact_identifier

    def partially_matches(self, other: "FuzzyIdFreq") -> bool:
        """
        Is there a partial match with ``other``?
        """
        if not self.fuzzy_identifier or not other.fuzzy_identifier:
            return False
        return self.fuzzy_identifier == other.fuzzy_identifier

    def fully_or_partially_matches(self, other: "FuzzyIdFreq") -> bool:
        """
        Is there a full or a partial match with ``other``?
        """
        return self.fully_matches(other) or self.partially_matches(other)

    def assert_has_freq_info_if_id_present(self) -> None:
        """
        If the identifier is present, ensure that frequency information is
        present, or raise :exc:`AssertionError`.
        """
        if self.exact_identifier:
            assert (
                self.exact_identifier_frequency is not None
            ), f"{self.comparison_name}: missing exact identifier frequency"
            assert (
                self.fuzzy_identifier
            ), f"{self.comparison_name}: missing fuzzy identifier"
            assert (
                self.fuzzy_identifier_frequency is not None
            ), f"{self.comparison_name}: missing fuzzy identifier frequency"
