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

Represents various types of person identifier (e.g. name, postcode) that may be
compared between two people.

"""


# =============================================================================
# Imports
# =============================================================================

from abc import ABC, abstractmethod
import logging
from typing import (
    Any,
    Dict,
    Generator,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
)

from cardinal_pythonlib.datetimefunc import coerce_to_pendulum_date
from cardinal_pythonlib.maths_py import round_sf
from cardinal_pythonlib.reprfunc import auto_repr
import pendulum
from pendulum.parsing.exceptions import ParserError
from pendulum import Date

from crate_anon.linkage.constants import NONE_TYPE, Switches, VALID_GENDERS
from crate_anon.linkage.comparison import (
    AdjustLogOddsComparison,
    CertainComparison,
    Comparison,
    DirectComparison,
)
from crate_anon.linkage.helpers import (
    get_first_two_char,
    get_metaphone,
    get_postcode_sector,
    getdictprob,
    getdictval,
    is_valid_isoformat_date,
    isoformat_date_or_none,
    ln,
    mk_blurry_dates,
    POSTCODE_REGEX,
    standardize_name,
    standardize_perfect_id_key,
    standardize_perfect_id_value,
    standardize_postcode,
    surname_alternative_fragments,
    validate_uncertain_prob,
)
from crate_anon.linkage.matchconfig import MatchConfig

log = logging.getLogger(__name__)


# =============================================================================
# Identifier
# =============================================================================


class Identifier(ABC):
    """
    Abstract base class: generic nugget of information about a person, in
    identifiable (plaintext) or de-identified (hashed) form. Optionally, may
    convey start/end dates.

    Note:

    - We trust that probabilities from the config have been validated (i.e. are
      in the range 0-1), but we should check values arising from incoming data,
      primarily via :meth:`from_hashed_dict`. The
      :func:`crate_anon.linkage.helpers.getdictprob` does this, but more checks
      may be required.

    - A typical comparison operation involves comparing a lot of people to
      each other, so it is usually efficient to cache "derived" information
      (e.g. we should calculate metaphones, etc., from names at creation, not
      at comparison). See :meth:`comparison`.
    """

    SEP = "/"  # separator
    NULL_VALUES_LOWERCASE = ["none", "null", "?"]  # must include "none"
    TEMPORAL_ID_FORMAT_HELP = (
        f"Temporal identifier format: either just IDENTIFIER, or "
        f"IDENTIFIER{SEP}STARTDATE{SEP}ENDDATE, where dates are in YYYY-MM-DD "
        f"format or one of {NULL_VALUES_LOWERCASE} (case-insensitive)."
    )

    KEY_START_DATE = "start_date"
    KEY_END_DATE = "end_date"

    ERR_MISSING_FREQ = "Missing frequency information"

    # -------------------------------------------------------------------------
    # Creation, and representations that support creation
    # -------------------------------------------------------------------------

    def __init__(
        self,
        cfg: Optional[MatchConfig],
        is_plaintext: bool,
        temporal: bool = False,
        start_date: Union[str, Date] = None,
        end_date: Union[str, Date] = None,
    ) -> None:
        """
        Args:
            cfg:
                A configuration object. Can be ``None`` but you have to specify
                that manually.
            is_plaintext:
                Is this an identifiable (plaintext) version? If ``False``, then
                it is a de-identified (hashed) version, whose internal
                structure can be more complex.
            temporal:
                Store start/end dates (which can be ``None``) along with the
                information?
            start_date:
                The start date (first valid date), or ``None``.
            end_date:
                The end date (last valid date), or ``None``.
        """
        assert isinstance(cfg, (MatchConfig, NONE_TYPE))
        self.cfg = cfg
        self.is_plaintext = is_plaintext
        self.temporal = temporal
        self.actually_temporal = temporal
        self.start_date = None  # type: Optional[Date]
        self.end_date = None  # type: Optional[Date]
        self._set_dates(start_date, end_date)

    def __str__(self) -> str:
        """
        A string representation used for CSV files.
        """
        if not self:
            # No information
            return ""
        if self.is_plaintext:
            # Identifiable
            id_str = self.plaintext_str_core()
            if self.actually_temporal:
                if self.SEP in id_str:
                    raise ValueError(
                        f"Temporal identifier unsuitable: "
                        f"contains {self.SEP!r}"
                    )
                return self.SEP.join(
                    [
                        id_str,
                        str(self.start_date),
                        str(self.end_date),
                    ]
                )
            else:
                return id_str
        return f"hashed_{self.__class__.__name__}"

    @abstractmethod
    def __eq__(self, other: "Identifier") -> bool:
        """
        Check equality with another, primarily for debugging.

        Just because it's an @abstractmethod doesn't mean that you can't call
        it (from derived classes).
        """
        return self._eq_check(other, ["start_date", "end_date"])

    def _eq_check(self, other: "Identifier", attrs: List[str]) -> bool:
        """
        Helper function to implement equality checks.
        """
        if type(self) != type(other):
            return False
        return all(getattr(self, a) == getattr(other, a) for a in attrs)

    @abstractmethod
    def plaintext_str_core(self) -> str:
        """
        Represents the identifier in plaintext, for CSV. Potentially
        encapsulated within more information by __str__().
        """
        pass

    @classmethod
    @abstractmethod
    def from_plaintext_str(cls, cfg: MatchConfig, x: str) -> "Identifier":
        """
        Restore a plaintext version from a string (which has been read from
        CSV). Reverses __str__(), not plaintext_str_core().
        """
        pass

    @abstractmethod
    def as_dict(
        self, encrypt: bool = True, include_frequencies: bool = True
    ) -> Dict[str, Any]:
        """
        Represents the object in a dictionary suitable for JSON serialization,
        for the de-identified (hashed) version.

        Args:
            encrypt:
                Encrypt the contents as writing, creating a hashed version.
            include_frequencies:
                Include frequency information. If you don't, this makes the
                resulting file suitable for use as a sample, but not as a
                proband file.
        """
        pass

    @classmethod
    @abstractmethod
    def from_dict(
        cls, cfg: MatchConfig, d: Dict[str, Any], hashed: bool
    ) -> "Identifier":
        """
        Restore a hashed or plaintext version from a dictionary (which will
        have been read from JSON).
        """
        pass

    # -------------------------------------------------------------------------
    # Internal methods to support creation
    # -------------------------------------------------------------------------

    def _set_dates(
        self,
        start_date: Union[str, Date] = None,
        end_date: Union[str, Date] = None,
    ) -> None:
        """
        Set date information. Should only be called for temporal identifiers.
        """
        start_date = coerce_to_pendulum_date(start_date)
        if not isinstance(start_date, (Date, NONE_TYPE)):
            raise ValueError(f"Bad start_date: {start_date!r}")

        end_date = coerce_to_pendulum_date(end_date)
        if not isinstance(end_date, (Date, NONE_TYPE)):
            raise ValueError(f"Bad end_date: {end_date!r}")

        if start_date and end_date:
            if start_date > end_date:
                raise ValueError(
                    f"start_date = {start_date!r} > end_date = {end_date!r}"
                )

        self.start_date = start_date
        self.end_date = end_date
        # Save some time later: this is only a temporal identifier if at least
        # one date is set.
        self.actually_temporal = bool(self.start_date) or bool(self.end_date)

    def _set_dates_from_dict(self, d: Dict[str, Any]) -> None:
        """
        Reads from a (JSON-derived) dictionary and sets our dates.
        Assumes we are a temporal identifier.
        """
        self._set_dates(
            start_date=getdictval(d, self.KEY_START_DATE, str),
            end_date=getdictval(d, self.KEY_END_DATE, str),
        )

    def _write_dates_to_dict(self, d: Dict[str, Any]) -> None:
        """
        For creating JSON dictionaries: write our dates to the dictionary (if
        we are a temporal identifier).
        """
        if self.temporal:
            d[self.KEY_START_DATE] = isoformat_date_or_none(self.start_date)
            d[self.KEY_END_DATE] = isoformat_date_or_none(self.end_date)

    @classmethod
    def _get_temporal_triplet(
        cls, x: str
    ) -> Tuple[str, Optional[Date], Optional[Date]]:
        """
        From a string (e.g. from CSV), split into CONTENTS/START_DATE/END_DATE.
        If it contains no "/", treat it as CONTENTS/None/None.

        Args:
            x:
                String to parse.

        Returns:
            tuple:
                contents, start_date, end_date
        """
        # Extract components of the string
        components = x.split(cls.SEP)

        if len(components) == 1:
            # Separator not present.
            contents = components[0]
            return contents, None, None

        if len(components) != 3:
            raise ValueError(
                f"Need three components separated by {cls.SEP!r} (or one with "
                f"no {cls.SEP!r}); got {x!r}"
            )

        contents, start_date_str, end_date_str = components

        # Start date
        if start_date_str.lower() in cls.NULL_VALUES_LOWERCASE:
            start_date = None  # type: Optional[Date]
        else:
            try:
                # noinspection PyTypeChecker
                start_date = pendulum.parse(start_date_str).date()
            except ParserError:
                raise ValueError(f"Bad date: {start_date_str!r}")

        # End date
        if end_date_str.lower() in cls.NULL_VALUES_LOWERCASE:
            end_date = None  # type: Optional[Date]
        else:
            try:
                # noinspection PyTypeChecker
                end_date = pendulum.parse(end_date_str).date()
            except ParserError:
                raise ValueError(f"Bad date: {end_date_str!r}")

        return contents, start_date, end_date

    @classmethod
    def _getval(cls, d: Dict[str, Any], key: str, type_: Type) -> Any:
        """
        Returns a value from a dictionary or raises an exception.
        The key must be in the dictionary, and the value must be non-blank.
        The value must be of type `type_`.
        """
        try:
            v = d[key]
        except KeyError:
            raise ValueError(f"Missing key: {key}")
        if v is None or v == "":
            raise ValueError(f"Missing or blank value: {key}")
        if not isinstance(v, type_):
            raise ValueError(
                f"Value for {key} should be of type {type_} but was of "
                f"type {type(v)}"
            )
        return v

    @classmethod
    def _getprob(cls, d: Dict[str, Any], key: str) -> Any:
        """
        As for :meth:`_getval` but returns a probability and checks that it
        is in range.
        """
        v = getdictval(d, key, float)
        if not 0 <= v <= 1:
            raise ValueError(f"Bad probability for {key}: {v}")

    def _round(self, x: Optional[float], encrypt: bool) -> Optional[float]:
        """
        Implements config-defined rounding for frequency representations of
        hashed values.

        Rounds frequencies to a certain number of significant figures. (Don't
        supply exact floating-point numbers for frequencies; may be more
        identifying. Don't use decimal places; we have to deal with some small
        numbers.)
        """
        if x is None:
            return None
        sf = self.cfg.rounding_sf
        if sf is None or not encrypt:
            return x
        return round_sf(x, sf)

    # -------------------------------------------------------------------------
    # Python standard representation functions
    # -------------------------------------------------------------------------

    def __repr__(self):
        """
        Standardized Python representation.
        """
        return auto_repr(self, sort_attrs=False)

    # -------------------------------------------------------------------------
    # Basic tests
    # -------------------------------------------------------------------------

    @abstractmethod
    def __bool__(self) -> bool:
        """
        Does this object contain information?
        """
        pass

    # -------------------------------------------------------------------------
    # Validation
    # -------------------------------------------------------------------------

    @abstractmethod
    def ensure_has_freq_info_if_id_present(self) -> None:
        """
        If we have ID information but some frequency information is missing,
        raise :exc:`ValueError`. Used to check validity for probands;
        candidates do not have to fulfil this requirement.
        """
        pass

    # -------------------------------------------------------------------------
    # Comparison
    # -------------------------------------------------------------------------

    def comparison_relevant(self, other: "Identifier") -> bool:
        """
        It's only relevant to compare this identifier to another if both have
        some information, and if they are not specifically excluded by a
        temporal check.
        """
        return self and other and self.overlaps(other)

    @abstractmethod
    def comparison(self, candidate_id: "Identifier") -> Optional[Comparison]:
        """
        Return a comparison odds (embodying the change in log odds) for a
        comparison between the "self" identifier (as the proband) and another,
        the candidate. Frequency information is expected to be on the "self"
        (proband) side.
        """
        pass

    def overlaps(self, other: "Identifier") -> bool:
        """
        Do ``self`` and ``other`` overlap in time?

        Args:
            other:
                the other :class:`Identifier`

        For similar logic, see
        :meth:`cardinal_pythonlib.interval.Interval.overlaps`.
        """
        if not self.actually_temporal or not other.actually_temporal:
            return True
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

    # -------------------------------------------------------------------------
    # Debugging
    # -------------------------------------------------------------------------

    def hashed(self, include_frequencies: bool = True) -> "Identifier":
        """
        For testing: hash this identifier by itself.
        """
        encrypt = self.is_plaintext
        d = self.as_dict(
            encrypt=encrypt, include_frequencies=include_frequencies
        )
        cls = type(self)  # type: Type[Identifier]
        return cls.from_dict(self.cfg, d, hashed=True)


# =============================================================================
# IdentifierTwoState
# =============================================================================


class IdentifierTwoState(Identifier, ABC):
    """
    Identifier that supports a two-state comparison.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.comparison_full_match = None  # type: Optional[DirectComparison]
        self.comparison_no_match = None  # type: Optional[DirectComparison]

    def _clear_comparisons(self) -> None:
        """
        Reset our comparison objects.
        """
        self.comparison_full_match = None  # type: Optional[DirectComparison]
        self.comparison_no_match = None  # type: Optional[DirectComparison]

    @abstractmethod
    def fully_matches(self, other: "IdentifierTwoState") -> bool:
        """
        Does this identifier fully match the other?

        You can assume that self.comparison_relevant(other) is True.
        """
        pass

    def comparison(
        self, candidate_id: "IdentifierTwoState"
    ) -> Optional[Comparison]:
        """
        Compare our identifier to another of the same type. Return None if you
        wish to draw no conclusions (e.g. there is missing information, or
        temporally defined identifiers do not overlap).

        You should assume that frequency information must be present on the
        "self" side (this should be the proband); it may be missing from the
        "other" side (the candidate).

        This is a high-speed function; pre-cache any fixed information that
        requires multi-stage lookup.
        """
        if not self.comparison_relevant(candidate_id):
            # Infer no conclusions from absent information.
            return None
        if self.fully_matches(candidate_id):
            return self.comparison_full_match
        return self.comparison_no_match

    def warn_if_llr_order_unexpected(
        self, full: DirectComparison, partials: List[DirectComparison] = None
    ) -> None:
        """
        Partial/full comparisons are not guaranteed to be ordered as you might
        expect; an example is in the validation paper (and in
        other_examples_for_paper.py). Nor are all partial/full matches
        guaranteed to yield better evidence for H than a complete mismatch.
        However, that's what you might expect. This function warns the user if
        that's not the case.

        Args:
            full:
                Comparisons for the "full match" condition.
            partials:
                Comparisons for "partial match" conditions.
        """
        if not self.cfg.check_comparison_order:
            return
        partials = partials or []
        no_match_llr = self.comparison_no_match.log_likelihood_ratio
        if any(
            c.log_likelihood_ratio < no_match_llr for c in [full] + partials
        ):
            log.warning(
                f"{self.__class__.__name__}: a match comparison's log "
                f"likelihood ratio is less than the no-match comparison's. "
                f"Object:\n\n{self!r}"
            )
        full_match_llr = full.log_likelihood_ratio
        if any(p.log_likelihood_ratio > full_match_llr for p in partials):
            log.warning(
                f"{self.__class__.__name__}: a partial match comparison's "
                f"log likelihood ratio exceeds the full-match comparison's. "
                f"Object:\n\n{self!r}"
            )


# =============================================================================
# IdentifierThreeState
# =============================================================================


class IdentifierThreeState(IdentifierTwoState, ABC):
    """
    Identifier that supports a three-state comparison.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.comparison_partial_match = (
            None
        )  # type: Optional[DirectComparison]

    def _clear_comparisons(self) -> None:
        """
        Reset our comparison objects.
        """
        super()._clear_comparisons()
        self.comparison_partial_match = (
            None
        )  # type: Optional[DirectComparison]

    @abstractmethod
    def partially_matches(self, other: "IdentifierThreeState") -> bool:
        """
        Does this identifier partially match the other?

        You can assume that self.comparison_relevant(other) is True.
        """
        pass

    def comparison(
        self, candidate_id: "IdentifierThreeState"
    ) -> Optional[Comparison]:
        """
        See :meth:`IdentifierTwoState.comparison`.
        """
        if not self.comparison_relevant(candidate_id):
            # Infer no conclusions from absent information.
            return None
        if self.fully_matches(candidate_id):
            return self.comparison_full_match
        if self.partially_matches(candidate_id):
            return self.comparison_partial_match
        return self.comparison_no_match


# =============================================================================
# IdentifierFourState
# =============================================================================


class IdentifierFourState(IdentifierThreeState, ABC):
    """
    Identifier that supports a four-state comparison.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        self.comparison_partial_match_second = (
            None
        )  # type: Optional[DirectComparison]

    def _clear_comparisons(self) -> None:
        """
        Reset our comparison objects.
        """
        super()._clear_comparisons()
        self.comparison_partial_match_second = (
            None
        )  # type: Optional[DirectComparison]

    @abstractmethod
    def partially_matches_second(self, other: "IdentifierFourState") -> bool:
        """
        Does this identifier partially match the other on the first fuzzy
        identifier?

        You can assume that self.comparison_relevant(other) is True.
        """
        pass

    def comparison(
        self, candidate_id: "IdentifierFourState"
    ) -> Optional[Comparison]:
        """
        See :meth:`IdentifierTwoState.comparison`.
        """
        if not self.comparison_relevant(candidate_id):
            # Infer no conclusions from absent information.
            return None
        if self.fully_matches(candidate_id):
            return self.comparison_full_match
        if self.partially_matches(candidate_id):
            return self.comparison_partial_match
        if self.partially_matches_second(candidate_id):
            return self.comparison_partial_match_second
        return self.comparison_no_match


# =============================================================================
# TemporalIDHolder
# =============================================================================


class TemporalIDHolder(Identifier):
    """
    Limited class that allows no config and stores a plain string identifier.
    Used for representing postcodes between a database and CSV for validation.
    """

    BAD_METHOD = "Inappropriate function called for TemporalIDHolder"

    def __init__(
        self, identifier: str, start_date: Date = None, end_date: Date = None
    ) -> None:
        super().__init__(
            cfg=None,
            is_plaintext=True,
            temporal=True,
            start_date=start_date,
            end_date=end_date,
        )
        self.identifier = identifier or ""
        if not isinstance(self.identifier, str):
            raise ValueError(f"Bad identifier: {identifier!r}")

    def __eq__(self, other: Identifier) -> bool:
        return super().__eq__(other) and self._eq_check(other, ["identifier"])

    def plaintext_str_core(self) -> str:
        return self.identifier

    @classmethod
    def from_plaintext_str(
        cls, cfg: MatchConfig, x: str
    ) -> "TemporalIDHolder":
        contents, start_date, end_date = cls._get_temporal_triplet(x)
        return TemporalIDHolder(
            identifier=contents, start_date=start_date, end_date=end_date
        )

    # noinspection PyTypeChecker
    def as_dict(
        self, encrypt: bool = True, include_frequencies: bool = True
    ) -> Dict[str, Any]:
        raise AssertionError(self.BAD_METHOD)

    # noinspection PyTypeChecker
    @classmethod
    def from_dict(
        cls, cfg: MatchConfig, d: Dict[str, Any], hashed: bool
    ) -> "TemporalIDHolder":
        raise AssertionError(cls.BAD_METHOD)

    def __bool__(self) -> bool:
        return bool(self.identifier)

    def ensure_has_freq_info_if_id_present(self) -> None:
        pass

    def comparison(self, candidate_id: "Identifier") -> Optional[Comparison]:
        raise AssertionError(self.BAD_METHOD)


# =============================================================================
# Postcode
# =============================================================================


class Postcode(IdentifierThreeState):
    """
    Represents a UK postcode.

    Note that we store nationwide frequencies. Final adjustment by k_postcode
    is only done at the last moment, allowing k_postcode to vary without having
    to change a hashed frequency file. Similarly for the probability of a
    postcode being unknown. So stored frequencies may be None.
    """

    KEY_POSTCODE_UNIT = "postcode_unit"
    KEY_POSTCODE_SECTOR = "postcode_sector"
    KEY_UNIT_FREQ = "unit_freq"  # national fraction, f_f_postcode
    KEY_SECTOR_FREQ = "sector_freq"  # national fraction, f_p_postcode

    def __init__(
        self,
        cfg: MatchConfig,
        postcode: str = "",
        start_date: Union[str, Date] = None,
        end_date: Union[str, Date] = None,
    ):
        """
        Plaintext creation of a postcode.
        """
        super().__init__(
            cfg=cfg,
            is_plaintext=True,
            temporal=True,
            start_date=start_date,
            end_date=end_date,
        )

        if not isinstance(postcode, str):
            raise ValueError(f"Bad postcode: {postcode!r}")
        postcode = standardize_postcode(postcode)
        if postcode and not POSTCODE_REGEX.match(postcode):
            raise ValueError(f"Bad postcode: {postcode!r}")

        if postcode:
            self.postcode_unit = postcode
            self.postcode_sector = get_postcode_sector(
                self.postcode_unit, prestandardized=True
            )
            self.unit_freq, self.sector_freq = cfg.postcode_unit_sector_freq(
                self.postcode_unit, prestandardized=True
            )
            # ... national fractions, f_f_postcode and f_p_postcode
        else:
            self.postcode_unit = ""
            self.postcode_sector = ""
            self.unit_freq = None  # type: Optional[float]
            self.sector_freq = None  # type: Optional[float]

        # Precalculate comparisons, for speed, but in a way that we can update
        # them if we are being created via from_hashed_dict().
        self._set_comparisons()

    def _set_comparisons(self) -> None:
        if self.postcode_unit:
            cfg = self.cfg

            # -----------------------------------------------------------------
            # Population probabilities.
            # -----------------------------------------------------------------
            # Here we apply any comparison-time adjustments, e.g. for the
            # probability of an unknown postcode or pseudopostcode, or the
            # potential that our comparison population is a geographic subset
            # of the UK.

            # Unit probability, p_f
            f_f = self.unit_freq  # national fraction (full), or None
            unit_unknown = f_f is None
            if unit_unknown:
                # Unknown postcode unit. This has been specified directly.
                p_f = cfg.p_unknown_or_pseudo_postcode_unit
            else:
                # Known postcode
                p_f = cfg.k_postcode * f_f * cfg.p_known_postcode

            # Total sector probability, p_p
            f_p = self.sector_freq  # national fraction (partial), or None
            sector_unknown = f_p is None
            if sector_unknown:
                # Unknown sector. This has been specified directly.
                p_p = cfg.p_unknown_or_pseudo_postcode_sector
                # A sanity check:
                assert unit_unknown, (
                    "Should be impossible that the postcode unit is known but "
                    "the sector is not."
                )
            else:
                # Known sector
                p_p = cfg.k_postcode * f_p * cfg.p_known_postcode
                # It is possible, though, that the postcode is unknown but the
                # sector is known (e.g. a typo in the postcode).
                if unit_unknown and p_p < p_f:
                    log.warning(
                        f"Unknown postcode unit in known sector and "
                        f"user-specified unknown unit probability "
                        f"p_f = {Switches.P_UNKNOWN_OR_PSEUDO_POSTCODE} "
                        f"exceeds the calculated probability of the known "
                        f"sector, p_p = k_postcode[{cfg.k_postcode}]"
                        f" * f_p[{f_p}]"
                        f" * p_known_postcode[{cfg.p_known_postcode}]"
                        f" = {p_p}. Adjusting the sector probability up to "
                        f"the unknown sector probability, "
                        f"p_p = {cfg.p_unknown_or_pseudo_postcode_sector}, "
                        f"but this may be a configuration error."
                    )
                    p_p = cfg.p_unknown_or_pseudo_postcode_sector

            validate_uncertain_prob(
                p_f,
                "Postcode p_f = k_postcode * f_f * p_known_postcode",
            )
            validate_uncertain_prob(
                p_p, "Postcode p_p = k_postcode * f_p * p_known_postcode"
            )
            # ... it's not reasonable that a postcode unit or sector is
            # impossible or certain.

            # Sector-not-unit probability, p_pnf
            p_pnf = p_p - p_f
            validate_uncertain_prob(
                p_pnf, "Postcode p_pnf = p_p[sector] - p_f[unit]"
            )
            # ... It is not completely unreasonable for this to be 0, e.g. for
            # pseudopostcodes that occupy all of their sector. But it's
            # dangerous, because if a partial-not-full match then does occur,
            # that will give P(D | ¬H) = 0 and log LR = +∞. We now enforce
            # k_pseudopostcode > 1 and thus p_pnf > 0.

            # -----------------------------------------------------------------
            # Error probabilities
            # -----------------------------------------------------------------
            p_ep = cfg.p_ep_postcode
            p_en = cfg.p_en_postcode

            # -----------------------------------------------------------------
            # Comparisons
            # -----------------------------------------------------------------
            self.comparison_full_match = DirectComparison(
                p_d_given_same_person=1 - p_ep,  # p_c
                p_d_given_diff_person=p_f,
                d_description="postcode_full_match",
            )
            self.comparison_partial_match = DirectComparison(
                p_d_given_same_person=p_ep,
                p_d_given_diff_person=p_pnf,
                d_description="postcode_partial_not_full_match",
            )
            self.comparison_no_match = DirectComparison(
                p_d_given_same_person=p_en,
                p_d_given_diff_person=1 - p_p,  # p_n
                d_description="postcode_no_match",
            )
            self.warn_if_llr_order_unexpected(
                full=self.comparison_full_match,
                partials=[self.comparison_partial_match],
            )
        else:
            self._clear_comparisons()

    def __eq__(self, other: Identifier) -> bool:
        return super().__eq__(other) and self._eq_check(other, ["postcode"])

    def plaintext_str_core(self) -> str:
        """
        For CSV.
        """
        return self.postcode_unit

    @classmethod
    def from_plaintext_str(cls, cfg: MatchConfig, x: str) -> "Postcode":
        """
        Creation from CSV.
        """
        postcode_unit, start_date, end_date = cls._get_temporal_triplet(x)
        return Postcode(
            cfg=cfg,
            postcode=postcode_unit,
            start_date=start_date,
            end_date=end_date,
        )

    def as_dict(
        self, encrypt: bool = True, include_frequencies: bool = True
    ) -> Dict[str, Any]:
        """
        For JSON.
        """
        if not self.postcode_unit:
            postcode_unit = None
            postcode_sector = None
        elif self.is_plaintext and encrypt:
            postcode_unit = self.cfg.hash_fn(self.postcode_unit)
            postcode_sector = self.cfg.hash_fn(self.postcode_sector)
        else:
            # Was already hashed, or keeping plaintext
            postcode_unit = self.postcode_unit
            postcode_sector = self.postcode_sector
        d = {
            self.KEY_POSTCODE_UNIT: postcode_unit,
            self.KEY_POSTCODE_SECTOR: postcode_sector,
        }
        self._write_dates_to_dict(d)
        if include_frequencies:
            d[self.KEY_UNIT_FREQ] = self._round(self.unit_freq, encrypt)
            d[self.KEY_SECTOR_FREQ] = self._round(self.sector_freq, encrypt)
        return d

    @classmethod
    def from_dict(
        cls, cfg: MatchConfig, d: Dict[str, Any], hashed: bool
    ) -> "Postcode":
        """
        Creation of a hashed postcode, ultimately from JSON.
        """
        p = Postcode(
            cfg=cfg,
            start_date=getdictval(d, cls.KEY_START_DATE, str),
            end_date=getdictval(d, cls.KEY_END_DATE, str),
        )
        p.is_plaintext = not hashed
        p.postcode_unit = getdictval(d, cls.KEY_POSTCODE_UNIT, str)
        p.postcode_sector = getdictval(d, cls.KEY_POSTCODE_SECTOR, str)
        p.unit_freq = getdictprob(d, cls.KEY_UNIT_FREQ)  # permits None
        p.sector_freq = getdictprob(d, cls.KEY_SECTOR_FREQ)  # permits None
        p._set_comparisons()
        return p

    def __bool__(self) -> bool:
        return bool(self.postcode_unit)

    def ensure_has_freq_info_if_id_present(self) -> None:
        pass
        # It's fine for frequency information to be missing; that means the
        # postcode is unknown or a pseudopostcode. We cope in
        # _set_comparisons().

    def fully_matches(self, other: "Postcode") -> bool:
        return self.postcode_unit == other.postcode_unit

    def partially_matches(self, other: "Postcode") -> bool:
        return self.postcode_sector == other.postcode_sector


# =============================================================================
# DateOfBirth
# =============================================================================


class DateOfBirth(IdentifierThreeState):
    """
    Represents a date of birth (DOB).

    We don't store any frequencies with the hashed version, since they are all
    obtainable from the config (they are not specific to a particular DOB).
    """

    KEY_DOB = "dob"
    KEY_DOB_MD = "dob_md"
    KEY_DOB_YD = "dob_yd"
    KEY_DOB_YM = "dob_ym"

    def __init__(self, cfg: MatchConfig, dob: str = "") -> None:
        """
        Plaintext creation of a DOB.

        Args:
            cfg:
                The config object.
            dob:
                (PLAINTEXT.) The date of birth in ISO-8061 "YYYY-MM-DD" string
                format.
        """
        super().__init__(cfg=cfg, is_plaintext=True, temporal=False)

        dob = dob or ""
        if not (
            isinstance(dob, str) and (not dob or is_valid_isoformat_date(dob))
        ):
            raise ValueError(f"Bad date: {dob!r}")

        self.dob_str = dob or ""
        # In our validation data, 93.3% of DOB errors were "single component"
        # errors, e.g. year wrong but month/day right. Within that, there was
        # no very dominant pattern.
        if dob:
            self.dob_md, self.dob_yd, self.dob_ym = mk_blurry_dates(dob)
        else:
            self.dob_md = ""
            self.dob_yd = ""
            self.dob_ym = ""

        # Precalculate our comparison objects, for speed.
        # We don't need a separate function here, because these frequencies are
        # all set from the config, not our data.
        self.comparison_full_match = DirectComparison(
            p_d_given_same_person=cfg.p_c_dob,
            p_d_given_diff_person=cfg.p_f_dob,
            d_description="dob_full_match",
        )
        self.comparison_partial_match = DirectComparison(
            p_d_given_same_person=cfg.p_ep_dob,
            p_d_given_diff_person=cfg.p_pnf_dob,
            d_description="dob_partial_not_full_match",
        )
        self.comparison_no_match = DirectComparison(
            p_d_given_same_person=cfg.p_en_dob,
            p_d_given_diff_person=cfg.p_n_dob,
            d_description="dob_no_match",
        )
        self.warn_if_llr_order_unexpected(
            full=self.comparison_full_match,
            partials=[self.comparison_partial_match],
        )

    def __eq__(self, other: Identifier) -> bool:
        return super().__eq__(other) and self._eq_check(other, ["dob_str"])

    def plaintext_str_core(self) -> str:
        """
        For CSV.
        """
        return self.dob_str

    @classmethod
    def from_plaintext_str(cls, cfg: MatchConfig, x: str) -> "DateOfBirth":
        """
        Creation from CSV.
        """
        return DateOfBirth(cfg=cfg, dob=x)

    def as_dict(
        self, encrypt: bool = True, include_frequencies: bool = True
    ) -> Dict[str, Any]:
        """
        For JSON.
        """
        if not self.dob_str:
            dob = ""
            dob_md = ""
            dob_yd = ""
            dob_ym = ""
        elif self.is_plaintext and encrypt:
            hash_fn = self.cfg.hash_fn
            dob = hash_fn(self.dob_str)
            dob_md = hash_fn(self.dob_md)
            dob_yd = hash_fn(self.dob_yd)
            dob_ym = hash_fn(self.dob_ym)
        else:
            # Was already hashed, or staying plaintext
            dob = self.dob_str
            dob_md = self.dob_md
            dob_yd = self.dob_yd
            dob_ym = self.dob_ym
        return {
            self.KEY_DOB: dob,
            self.KEY_DOB_MD: dob_md,
            self.KEY_DOB_YD: dob_yd,
            self.KEY_DOB_YM: dob_ym,
        }

    @classmethod
    def from_dict(
        cls, cfg: MatchConfig, d: Dict[str, Any], hashed: bool
    ) -> "DateOfBirth":
        """
        Creation of a hashed DOB, ultimately from JSON.
        """
        x = DateOfBirth(cfg=cfg)
        x.is_plaintext = not hashed
        x.dob_str = getdictval(d, cls.KEY_DOB, str)
        x.dob_md = getdictval(d, cls.KEY_DOB_MD, str)
        x.dob_yd = getdictval(d, cls.KEY_DOB_YD, str)
        x.dob_ym = getdictval(d, cls.KEY_DOB_YM, str)
        return x

    def __bool__(self) -> bool:
        return bool(self.dob_str)

    def ensure_has_freq_info_if_id_present(self) -> None:
        pass  # That info is always in the config; none stored here.

    def fully_matches(self, other: "DateOfBirth") -> bool:
        return self.dob_str == other.dob_str

    def partially_matches(self, other: "DateOfBirth") -> bool:
        return (
            self.dob_md == other.dob_md
            or self.dob_yd == other.dob_yd
            or self.dob_ym == other.dob_ym
        )


# =============================================================================
# Gender
# =============================================================================


class Gender(IdentifierTwoState):
    """
    Represents a gender.
    """

    KEY_GENDER = "gender"
    KEY_GENDER_FREQ = "gender_freq"

    def __init__(self, cfg: MatchConfig, gender: str = "") -> None:
        """
        Plaintext creation of a gender.

        Args:
            cfg:
                The config object.
            gender:
                (PLAINTEXT.) The gender.
        """
        super().__init__(
            cfg=cfg,
            is_plaintext=True,
            temporal=False,
        )

        gender = gender or ""
        if gender not in VALID_GENDERS:
            raise ValueError(f"Bad gender: {gender!r}")

        self.gender_str = gender
        if gender:
            self.gender_freq = cfg.gender_freq(gender)
        else:
            self.gender_freq = None  # type: Optional[float]

        self._set_comparisons()

    def _set_comparisons(self) -> None:
        if self.gender_freq:
            p_e = self.cfg.p_e_gender_error
            p_f = self.gender_freq
            self.comparison_full_match = DirectComparison(
                p_d_given_same_person=1 - p_e,
                p_d_given_diff_person=p_f,
                d_description="gender_match",
            )
            self.comparison_no_match = DirectComparison(
                p_d_given_same_person=p_e,
                p_d_given_diff_person=1 - p_f,
                d_description="gender_no_match",
            )
            self.warn_if_llr_order_unexpected(full=self.comparison_full_match)
        else:
            self._clear_comparisons()

    def __eq__(self, other: Identifier) -> bool:
        return super().__eq__(other) and self._eq_check(other, ["gender_str"])

    def plaintext_str_core(self) -> str:
        """
        For CSV.
        """
        return self.gender_str

    @classmethod
    def from_plaintext_str(cls, cfg: MatchConfig, x: str) -> "Gender":
        """
        Creation from CSV.
        """
        return Gender(cfg=cfg, gender=x)

    def as_dict(
        self, encrypt: bool = True, include_frequencies: bool = True
    ) -> Dict[str, Any]:
        """
        For JSON.
        """
        if not self.gender_str:
            gender = ""
        elif self.is_plaintext and encrypt:
            gender = self.cfg.hash_fn(self.gender_str)
        else:
            # Was already hashed, or staying plaintext
            gender = self.gender_str
        d = {
            self.KEY_GENDER: gender,
        }
        if include_frequencies:
            d[self.KEY_GENDER_FREQ] = self._round(self.gender_freq, encrypt)
        return d

    @classmethod
    def from_dict(
        cls, cfg: MatchConfig, d: Dict[str, Any], hashed: bool
    ) -> "Gender":
        """
        Creation of a hashed gender, ultimately from JSON.
        """
        g = Gender(cfg=cfg)
        g.is_plaintext = not hashed
        g.gender_str = getdictval(d, cls.KEY_GENDER, str)
        g.gender_freq = getdictprob(d, cls.KEY_GENDER_FREQ)
        g._set_comparisons()
        return g

    def __bool__(self) -> bool:
        return bool(self.gender_str)

    def ensure_has_freq_info_if_id_present(self) -> None:
        if self.gender_str and self.gender_freq is None:
            raise ValueError(
                self.ERR_MISSING_FREQ + f" for gender {self.gender_str!r}"
            )

    def fully_matches(self, other: "Gender") -> bool:
        return self.gender_str == other.gender_str


# =============================================================================
# BasicName
# =============================================================================


class BasicName(IdentifierFourState, ABC):
    """
    Base class for names.

    Note that this is a pretty difficult generic problem. See
    https://www.kalzumeus.com/2010/06/17/falsehoods-programmers-believe-about-names/

    The sequence of preferences is (1) full match, (2) metaphone match, (3)
    first two character (F2C) match, (4) no match. Reasons are discussed in the
    validation paper. Frequency representations here are slightly more complex
    as the fuzzy representations are not subsets/supersets of each other, but
    overlap, so we need to represent explicitly e.g. P(F2C match but not
    metaphone or name match).

    We will need some special gender features for both forenames and surnames:

    - UK forename frequency depends on gender.
    - The probability that someone's surname changes depends on gender.

    As a result, because we can't access gender once hashed, we need to store
    error frequencies as well as population frequencies.

    Since names can change, we also support optional start/end dates. If none
    are supplied, it simply becomes a non-temporal identifier.
    """  # noqa

    KEY_NAME = "name"
    KEY_METAPHONE = "metaphone"
    KEY_FIRST_TWO_CHAR = "f2c"

    # Terse in the JSON, to save some space:
    KEY_P_F = "p_f"  # name frequency
    KEY_P_P1NF = "p_p1nf"  # metaphone, not name
    KEY_P_P2NP1 = "p_p2np1"  # F2C, not name or metaphone

    KEY_P_C = "p_c"
    KEY_P_EP1 = "p_ep1"
    KEY_P_EP2NP1 = "p_ep2np1"

    def __init__(
        self,
        cfg: MatchConfig,
        name: str = "",
        gender: str = "",
        temporal: bool = False,
        start_date: Union[str, Date] = None,
        end_date: Union[str, Date] = None,
        description: str = "name",
    ) -> None:
        """
        Plaintext creation of a name.

        Args:
            cfg:
                The config object.
            name:
                (PLAINTEXT.) The name.
            description:
                Used internally for verbose comparisons.
        """
        if not isinstance(name, str):
            raise ValueError(f"Bad name: {name!r}")

        super().__init__(
            cfg=cfg,
            is_plaintext=True,
            temporal=temporal,
            start_date=start_date,
            end_date=end_date,
        )
        self.description = description

        # Standardization necessary for freq. lookup and metaphone.
        self.name = standardize_name(name)
        self.metaphone = get_metaphone(self.name)
        self.f2c = get_first_two_char(self.name)

        # Population frequencies -- to be overridden
        self.p_f = None  # type: Optional[float]
        self.p_p1nf = None  # type: Optional[float]
        self.p_p2np1 = None  # type: Optional[float]

        # Error probabilities -- to be overridden
        self.p_c = None  # type: Optional[float]
        self.p_ep1 = None  # type: Optional[float]
        self.p_ep2np1 = None  # type: Optional[float]

        self.gender = ""  # changed in next step
        self.set_gender(gender)  # will reset frequencies and comparisons

    def set_gender(self, gender: str) -> None:
        """
        Special operation for identifiable reading.
        """
        if gender not in VALID_GENDERS:
            raise ValueError(f"Bad gender: {gender!r}")
        self.gender = gender
        self._reset_frequencies_identifiable()  # will set comparisons

    @abstractmethod
    def _reset_frequencies_identifiable(self) -> None:
        """
        Gender may have changed. Update any probabilities accordingly,
        and call self._set_comparisons().
        """
        pass

    def _clear_frequencies(self) -> None:
        """
        Clear our population/error frequencies.
        """
        self.p_f = None
        self.p_p1nf = None
        self.p_p2np1 = None

        self.p_c = None
        self.p_ep1 = None
        self.p_ep2np1 = None

    @property
    def p_en(self) -> float:
        """
        For internal use. Only call if frequencies are set up.
        """
        p_en = 1 - self.p_c - self.p_ep1 - self.p_ep2np1
        assert 0 <= p_en <= 1, "Bad error probabilities for a BasicName"
        return p_en

    @property
    def p_n(self) -> float:
        """
        For internal use. Only call if frequencies are set up.
        """
        p_n = 1 - self.p_f - self.p_p1nf - self.p_p2np1
        assert 0 <= p_n <= 1, "Bad population probabilities for a BasicName"
        return p_n

    def _set_comparisons(self) -> None:
        """
        If we have identifier information, use error information from `self`
        (unusually), and frequency information from `self`, to create our
        comparisons. Otherwise, call :meth:`_clear_comparisons`.
        """
        if self.name:
            desc = self.description
            self.comparison_full_match = DirectComparison(
                p_d_given_same_person=self.p_c,
                p_d_given_diff_person=self.p_f,
                d_description=f"{desc}_full_match",
            )
            self.comparison_partial_match = DirectComparison(
                p_d_given_same_person=self.p_ep1,
                p_d_given_diff_person=self.p_p1nf,
                d_description=f"{desc}_partial_match_1_metaphone_not_full",
            )
            self.comparison_partial_match_second = DirectComparison(
                p_d_given_same_person=self.p_ep2np1,
                p_d_given_diff_person=self.p_p2np1,
                d_description=f"{desc}_partial_match_2_f2c_not_name_metaphone",
            )
            self.comparison_no_match = DirectComparison(
                p_d_given_same_person=self.p_en,
                p_d_given_diff_person=self.p_n,
                d_description=f"{desc}_no_match",
            )
            self.warn_if_llr_order_unexpected(
                full=self.comparison_full_match,
                partials=[
                    self.comparison_partial_match,
                    self.comparison_partial_match_second,
                ],
            )
        else:
            self._clear_comparisons()

    def __eq__(self, other: Identifier) -> bool:
        return super().__eq__(other) and self._eq_check(
            other, ["name", "gender"]
        )

    def plaintext_str_core(self) -> str:
        """
        For CSV.
        """
        return self.name

    def as_dict(
        self, encrypt: bool = True, include_frequencies: bool = True
    ) -> Dict[str, Any]:
        """
        For JSON.
        """
        if not self.name:
            name = None
            metaphone = None
            f2c = None
        elif self.is_plaintext and encrypt:
            hash_fn = self.cfg.hash_fn
            name = hash_fn(self.name)
            metaphone = hash_fn(self.metaphone)
            f2c = hash_fn(self.f2c)
        else:
            # Was already hashed, or staying plaintext
            name = self.name
            metaphone = self.metaphone
            f2c = self.f2c
        d = {
            self.KEY_NAME: name,
            self.KEY_METAPHONE: metaphone,
            self.KEY_FIRST_TWO_CHAR: f2c,
        }
        self._write_dates_to_dict(d)
        if include_frequencies:
            d[self.KEY_P_F] = self._round(self.p_f, encrypt)
            d[self.KEY_P_P1NF] = self._round(self.p_p1nf, encrypt)
            d[self.KEY_P_P2NP1] = self._round(self.p_p2np1, encrypt)
            d[self.KEY_P_C] = self._round(self.p_c, encrypt)
            d[self.KEY_P_EP1] = self._round(self.p_ep1, encrypt)
            d[self.KEY_P_EP2NP1] = self._round(self.p_ep2np1, encrypt)
        return d

    def _set_from_json_dict_internal(self, d: Dict[str, Any], hashed: bool):
        """
        Internal function used by derived classes. Doesn't create the object,
        which is specialized to the derived class, but does the reading from
        the hashed dictionary and sets up the comparisons.
        """
        self.is_plaintext = not hashed

        if self.temporal:
            self._set_dates_from_dict(d)

        self.name = getdictval(d, self.KEY_NAME, str)
        self.metaphone = getdictval(d, self.KEY_METAPHONE, str)
        self.f2c = getdictval(d, self.KEY_FIRST_TWO_CHAR, str)

        self.p_f = getdictprob(d, self.KEY_P_F)
        self.p_p1nf = getdictprob(d, self.KEY_P_P1NF)
        self.p_p2np1 = getdictprob(d, self.KEY_P_P2NP1)

        self.p_c = getdictprob(d, self.KEY_P_C)
        self.p_ep1 = getdictprob(d, self.KEY_P_EP1)
        self.p_ep2np1 = getdictprob(d, self.KEY_P_EP2NP1)

        self._set_comparisons()

    def __bool__(self) -> bool:
        return bool(self.name)

    def ensure_has_freq_info_if_id_present(self) -> None:
        if self.name and (
            self.p_f is None or self.p_p1nf is None or self.p_p2np1 is None
        ):
            raise ValueError(
                self.ERR_MISSING_FREQ + f" for name {self.name!r}"
            )

    def fully_matches(self, other: "BasicName") -> bool:
        return self.name == other.name

    def partially_matches(self, other: "BasicName") -> bool:
        return self.metaphone == other.metaphone

    def partially_matches_second(self, other: "BasicName") -> bool:
        return self.f2c == other.f2c


# =============================================================================
# SurnameFragment
# =============================================================================


class SurnameFragment(BasicName):
    """
    Collate information about a name fragment. This identifier is unlikely to
    be used directly for comparisons, but is used by Surname.

    We don't store dates; they are stored with the surname.
    """

    BAD_METHOD = "Inappropriate function called for SurnameFragment"

    # -------------------------------------------------------------------------
    # Creation
    # -------------------------------------------------------------------------

    def __init__(
        self,
        cfg: MatchConfig,
        name: str = "",
        gender: str = "",
    ) -> None:
        super().__init__(cfg, name=name, gender=gender, description="surname")
        # ... will call _reset_frequencies_identifiable()

    @classmethod
    def from_dict(
        cls, cfg: MatchConfig, d: Dict[str, Any], hashed: bool
    ) -> "SurnameFragment":
        f = SurnameFragment(cfg)
        f._set_from_json_dict_internal(d, hashed)
        return f

    # -------------------------------------------------------------------------
    # Creation helper functions
    # -------------------------------------------------------------------------

    def _reset_frequencies_identifiable(self) -> None:
        if self.name:
            cfg = self.cfg
            f = cfg.get_surname_freq_info(self.name, prestandardized=True)
            g = self.gender

            self.p_f = f.p_name
            self.p_p1nf = f.p_metaphone_not_name
            self.p_p2np1 = f.p_f2c_not_name_metaphone

            self.p_c = cfg.p_c_surname[g]
            self.p_ep1 = cfg.p_ep1_surname[g]
            self.p_ep2np1 = cfg.p_ep2np1_surname[g]
        else:
            self._clear_frequencies()
        self._set_comparisons()

    # -------------------------------------------------------------------------
    # Unused methods from Identifier
    # -------------------------------------------------------------------------

    def plaintext_str_core(self) -> str:
        raise AssertionError(self.BAD_METHOD)

    @classmethod
    def from_plaintext_str(cls, cfg: MatchConfig, x: str) -> "SurnameFragment":
        raise AssertionError(cls.BAD_METHOD)

    # -------------------------------------------------------------------------
    # Sorting methods, to use the linter
    # -------------------------------------------------------------------------

    @staticmethod
    def sort_exact_freq(x: "SurnameFragment") -> float:
        return x.p_f

    @staticmethod
    def sort_partial_1_freq(x: "SurnameFragment") -> float:
        return x.p_p1nf

    @staticmethod
    def sort_partial_2_freq(x: "SurnameFragment") -> float:
        return x.p_p2np1


# =============================================================================
# Surname
# =============================================================================


class Surname(Identifier):
    """
    Represents a surname (family name).

    Identifiably, we store the unmodified (unstandardized) name.

    We don't inherit from BasicName, but from Identifier, because surnames
    need to deal with "fragment" problems.

    We need to be able to match on parts. For example, "van Beethoven" should
    match "van Beethoven" but also "Beethoven". What frequency should we use
    for those parts? This has to be the frequency of the part (not the
    composite). For example, if someone is called "Mozart-Smith", then a match
    on "Mozart-Smith" or "Mozart" is less likely in the population, and thus
    more informative, than a match on "Smith". So, we need frequency
    information associated with each part.
    """

    KEY_FRAGMENTS = "fragments"

    # -------------------------------------------------------------------------
    # Creation
    # -------------------------------------------------------------------------

    def __init__(
        self,
        cfg: MatchConfig,
        name: str = "",
        gender: str = "",
        start_date: Union[str, Date] = None,
        end_date: Union[str, Date] = None,
    ) -> None:
        super().__init__(
            cfg,
            is_plaintext=True,
            temporal=True,
            start_date=start_date,
            end_date=end_date,
        )
        self.raw_surname = name.strip()  # but retain case, internal spaces
        # ... because "case" is complex for UTF8 characters.

        # There is some duplication here for speed and to cope with the
        # difference between identifiable and hashed versions. We want a set
        # version for rapid overlap checking, and an ordered list to pick by
        # frequency sometimes.
        self.exact_set = set()  # type: Set[str]
        self.partial_set_metaphone = set()  # type: Set[str]
        self.partial_set_f2c = set()  # type: Set[str]
        self.fragments = []  # type: List[SurnameFragment]
        # ... set properly by _reset_identifiable() and from_dict()
        self.gender = ""  # changed in next step
        self.set_gender(gender)  # will reset frequencies/comparisons

    @classmethod
    def from_plaintext_str(cls, cfg: MatchConfig, x: str) -> "Surname":
        """
        Creation from CSV.
        """
        name, start_date, end_date = cls._get_temporal_triplet(x)
        return Surname(
            cfg=cfg, name=x, start_date=start_date, end_date=end_date
        )

    @classmethod
    def from_dict(
        cls, cfg: MatchConfig, d: Dict[str, Any], hashed: bool
    ) -> "Surname":
        """
        Creation of a hashed name, ultimately from JSON.
        """
        n = Surname(cfg=cfg)
        n.is_plaintext = not hashed
        n._set_dates_from_dict(d)
        fragments_json_list = getdictval(d, cls.KEY_FRAGMENTS, list)
        n.fragments = [
            SurnameFragment.from_dict(cfg, fragment_dict, hashed)
            for fragment_dict in fragments_json_list
        ]
        n._reset_name_sets()
        return n

    def __eq__(self, other: Identifier) -> bool:
        return super().__eq__(other) and self._eq_check(
            other, ["gender", "fragments"]
        )

    # -------------------------------------------------------------------------
    # Representation
    # -------------------------------------------------------------------------

    def plaintext_str_core(self) -> str:
        return self.raw_surname

    def as_dict(
        self, encrypt: bool = True, include_frequencies: bool = True
    ) -> Dict[str, Any]:
        fragments = [
            f.as_dict(encrypt=encrypt, include_frequencies=include_frequencies)
            for f in self.fragments
        ]
        d = {self.KEY_FRAGMENTS: fragments}
        self._write_dates_to_dict(d)
        return d

    # -------------------------------------------------------------------------
    # Methods to support creation
    # -------------------------------------------------------------------------

    def set_gender(self, gender: str) -> None:
        """
        Special operation for identifiable reading.
        """
        if gender not in VALID_GENDERS:
            raise ValueError(f"Bad gender: {gender!r}")
        self.gender = gender
        self._reset_identifiable()  # will set comparisons

    def _reset_identifiable(self) -> None:
        """
        If the name or gender has changed, in an identifiable copy, reset our
        fragment information (with their comparisons), and the name fragment
        sets for fast comparison.
        """
        cfg = self.cfg
        self.fragments = []
        if self.raw_surname:
            for exact in surname_alternative_fragments(
                surname=self.raw_surname,
                accent_transliterations=cfg.accent_transliterations,
                nonspecific_name_components=cfg.nonspecific_name_components,
            ):
                # The first of these is the full name.
                fragment = SurnameFragment(
                    cfg=cfg, name=exact, gender=self.gender
                )
                self.fragments.append(fragment)
                self.exact_set.add(fragment.name)
                self.partial_set_metaphone.add(fragment.metaphone)
                self.partial_set_f2c.add(fragment.f2c)
        self._reset_name_sets()

    def _reset_name_sets(self) -> None:
        """
        Reset our fast comparison sets from the name fragments.
        """
        self.exact_set = set()
        self.partial_set_metaphone = set()
        self.partial_set_f2c = set()
        for f in self.fragments:
            self.exact_set.add(f.name)
            self.partial_set_metaphone.add(f.metaphone)
            self.partial_set_f2c.add(f.f2c)

    # -------------------------------------------------------------------------
    # Basic tests
    # -------------------------------------------------------------------------

    def __bool__(self) -> bool:
        return bool(self.fragments)

    def ensure_has_freq_info_if_id_present(self) -> None:
        for f in self.fragments:
            f.ensure_has_freq_info_if_id_present()

    # -------------------------------------------------------------------------
    # Comparison
    # -------------------------------------------------------------------------

    def fully_matches(self, other: "Surname") -> bool:
        """
        Primarily for debugging; :meth:`comparison` is used for real work.
        """
        return bool(self.exact_set.intersection(other.exact_set))

    def partially_matches(self, other: "Surname") -> bool:
        """
        Primarily for debugging; :meth:`comparison` is used for real work.
        """
        return bool(
            self.partial_set_metaphone.intersection(
                other.partial_set_metaphone
            )
        )

    def partially_matches_second(self, other: "Surname") -> bool:
        """
        Primarily for debugging; :meth:`comparison` is used for real work.
        """
        return bool(self.partial_set_f2c.intersection(other.partial_set_f2c))

    def comparison(self, candidate_id: "Surname") -> Optional[Comparison]:
        """
        Specialized version for surname.
        """
        if not self.comparison_relevant(candidate_id):
            # Infer no conclusions from absent information.
            return None

        overlap_exact = self.exact_set.intersection(candidate_id.exact_set)
        if overlap_exact:
            # Exact match. But possibly >1, e.g. "Mozart-Smith" has matched
            # "Mozart-Smith", "Mozart", and "Smith". Reasonable to pick the
            # most informative (rarest) version.
            possibilities = [
                f for f in self.fragments if f.name in overlap_exact
            ]  # type: List[SurnameFragment]
            possibilities.sort(key=SurnameFragment.sort_exact_freq)
            # Sorted in ascending order, so first (lowest frequency) is best.
            return possibilities[0].comparison_full_match

        overlap_partial_1 = self.partial_set_metaphone.intersection(
            candidate_id.partial_set_metaphone
        )
        if overlap_partial_1:
            # Similarly:
            possibilities = [
                f for f in self.fragments if f.metaphone in overlap_partial_1
            ]  # type: List[SurnameFragment]
            possibilities.sort(key=SurnameFragment.sort_partial_1_freq)
            # Sorted in ascending order, so first (lowest frequency) is best.
            return possibilities[0].comparison_partial_match

        overlap_partial_2 = self.partial_set_f2c.intersection(
            candidate_id.partial_set_f2c
        )
        if overlap_partial_2:
            # Similarly:
            possibilities = [
                f for f in self.fragments if f.f2c in overlap_partial_2
            ]  # type: List[SurnameFragment]
            possibilities.sort(key=SurnameFragment.sort_partial_2_freq)
            # Sorted in ascending order, so first (lowest frequency) is best.
            return possibilities[0].comparison_partial_match_second

        # For "no match", we use the whole original name and its frequencies:
        return self.fragments[0].comparison_no_match


# =============================================================================
# Forename
# =============================================================================


class Forename(BasicName):
    """
    Represents a forename (given name).
    """

    def __init__(
        self,
        cfg: MatchConfig,
        name: str = "",
        gender: str = "",
        start_date: Union[str, Date] = None,
        end_date: Union[str, Date] = None,
    ) -> None:
        super().__init__(
            cfg=cfg,
            name=name,
            gender=gender,
            temporal=True,
            start_date=start_date,
            end_date=end_date,
            description="forename",
        )
        # ... will call _reset_frequencies_identifiable()

    def _reset_frequencies_identifiable(self) -> None:
        if self.name:
            cfg = self.cfg
            g = self.gender
            f = cfg.get_forename_freq_info(self.name, g, prestandardized=True)

            self.p_f = f.p_name
            self.p_p1nf = f.p_metaphone_not_name
            self.p_p2np1 = f.p_f2c_not_name_metaphone

            self.p_c = cfg.p_c_forename[g]
            self.p_ep1 = cfg.p_ep1_forename[g]
            self.p_ep2np1 = cfg.p_ep2np1_forename[g]
        else:
            self._clear_frequencies()
        self._set_comparisons()

    @classmethod
    def from_plaintext_str(cls, cfg: MatchConfig, x: str) -> "Forename":
        """
        Creation from CSV.
        """
        name, start_date, end_date = cls._get_temporal_triplet(x)
        return Forename(
            cfg=cfg, name=x, start_date=start_date, end_date=end_date
        )

    @classmethod
    def from_dict(
        cls, cfg: MatchConfig, d: Dict[str, Any], hashed: bool
    ) -> "Forename":
        """
        Creation of a hashed name, ultimately from JSON.
        """
        n = Forename(cfg=cfg)
        n._set_from_json_dict_internal(d, hashed)
        return n


# =============================================================================
# PerfectID
# =============================================================================


class PerfectID(IdentifierTwoState):
    """
    For comparing people based on one or more perfect ID values.
    """

    def __init__(
        self, cfg: MatchConfig, identifiers: Dict[str, Any] = None
    ) -> None:
        """
        The identifier values will be converted to strings, if they aren't
        already.
        """
        super().__init__(cfg=cfg, is_plaintext=True, temporal=False)
        self.comparison_full_match = CertainComparison()

        self.identifiers = {}  # type: Dict[str, str]
        self.key_set = set()  # type: Set[str]
        if identifiers:
            self._set_identifiers(identifiers)

    def _set_identifiers(self, identifiers: Dict[str, str] = None) -> None:
        identifiers = identifiers or {}
        for k, v in identifiers.items():
            self.identifiers[
                standardize_perfect_id_key(k)
            ] = standardize_perfect_id_value(v)
        self.key_set = set(self.identifiers.keys())

    @classmethod
    def from_plaintext_str(cls, cfg: MatchConfig, x: str) -> "PerfectID":
        d = {}  # type: Dict[str, str]
        pair_strings = x.split(";")
        for pair_str in pair_strings:
            if pair_str.count(":") != 1:
                raise ValueError(f"Bad PerfectID string {x!r}")
            k, v = pair_str.split(":")
            d[k] = v
        return PerfectID(cfg=cfg, identifiers=d)

    def __eq__(self, other: Identifier) -> bool:
        return super().__eq__(other) and self._eq_check(other, ["identifiers"])

    def plaintext_str_core(self) -> str:
        return ";".join(f"{k}={v}" for k, v in self.identifiers)

    @classmethod
    def from_dict(
        cls, cfg: MatchConfig, d: Dict[str, Any], hashed: bool
    ) -> "PerfectID":
        p = PerfectID(cfg=cfg)
        p.is_plaintext = not hashed
        p._set_identifiers(d)
        return p

    def as_dict(
        self, encrypt: bool = True, include_frequencies: bool = True
    ) -> Dict[str, Any]:
        if not self.is_plaintext or not encrypt:
            # Was already hashed, or staying plaintext
            return self.identifiers
        hash_fn = self.cfg.hash_fn
        return {k: hash_fn(v) for k, v in self.identifiers.items()}

    def __bool__(self) -> bool:
        return bool(self.identifiers)

    def ensure_has_freq_info_if_id_present(self) -> None:
        pass

    def fully_matches(self, other: "PerfectID") -> bool:
        for k in self.key_set.intersection(other.key_set):
            if self.identifiers[k] == other.identifiers[k]:
                # Match
                return True
        return False

    def comparison(self, candidate_id: "PerfectID") -> Optional[Comparison]:
        return (
            self.comparison_full_match
            if self.fully_matches(candidate_id)
            else None
        )


# =============================================================================
# Comparison of multiple potentially jumbled similar identifiers
# =============================================================================

NOTES_MULTIPLE_COMPARISONS = """

What can be compared?
---------------------

Identifiers that are explicitly time-stamped cannot be compared with explicitly
non-overlapping identifiers. (But un-time-stamped identifiers can be compared
with anything.) And only information that is "present" is used for comparison.
These checks are implemented by each identifier in their `comparison` method.


What is a good match?
---------------------

Implicitly, we prefer full > partial > no match (and similarly for comparisons
with more or fewer than 3 options). But this is implemented more explicitly by
log likelihood ratio: we prefer higher values.


No re-use
---------

No identifier can be used for >1 comparison simultaneously. "Surplus"
identifiers therefore provide no evidence. For example, if candidate_identifers
= [A, B, C] and proband_identifiers = [A, B], then C will be ignored (the
comparisons will likely be A/A, B/B). But [A, B, C] versus [A, B, D] will
likely lead to comparisons A/A, B/B, C/D.

Suppose our proband has n identifiers, and our candidate has m. Then we can
make c = min(n, m) comparisons.


Unordered comparisons: picking the best involves implicit comparison
--------------------------------------------------------------------

In unordered comparisons, if we pick the best, we have implicitly made many
more comparisons. We need to adjust for that.

To illustrate, suppose the population of all names is {A, B, ..., Z}, giving a
set of size s = 26, and that every name is equiprobable in the population with
frequency q = 1/s = 1/26.

PROBABILITY OF A POPULATION (RANDOM PERSON) MATCH FOR MULTIPLE IDENTIFIERS. If
we have a proband with names [A] and a candidate with a single name such as [A]
or [Z], then we will declare a match if the candidate is named [A] and P(D |
¬H) = P(match | randomly selected other person) = 1/26. If our candidate has
two unordered names, then we would declare a match regardless of whether the
candidate was [A, B] or [B, A], and so would declare a match with a random
candidate with probability 1/26 + 1/26 - 1/(26 ^ 2), or more generally 2/s -
1/(s ^ 2) = 2q - q^2. The subtracted component is for a candidate named [A, A],
who would otherwise be counted twice for [A, *] and [*, A]. More generally, for
a proband with one name and a candidate with m names, the match probability is
1 - (1 - q) ^ m. That is, the probability of no match for each is (1 - q), and
it takes m failures to match for an overall failure to match. By the Bonferroni
approximation or Boole's inequality [1], this is approximately (and never more
than) m * q. So mq is a slightly conservative correction for multiple
comparisons.

For a proband with n <= m names, we can work sequentially: the first proband
named is matched by the candidate with approximately P = m * q_1; then, having
used up one candidate name, the second proband name is matched by the candidate
with approximately P = (m - 1) * q_2, and so on.

If n > m, we simply stop the process.

No correction is required for P(D | H), since (ignoring identifier errors) the
probability of an unordered match given H is 1.

This does NOT apply to "non-match" comparisons, where we have not gone
"fishing" for the best order.

[1] https://en.wikipedia.org/wiki/Boole%27s_inequality


Implementing via the Bayesian log-odds system
---------------------------------------------

Using this approximation makes things straightforward. The posterior log odds
is the prior log odds plus the log likelihood ratio. The log likelihood ratio
(LLR) for a match is ln(p_c) - ln(match probability), where p_c is the
probability of a correct match given the hypothesis that the proband and
candidate are the same person.

So if we were using LLR = ln(p_c) - ln(q), but we actually wanted to multiply
the probability q by some factor f to give LLR = ln(p_c) - ln(fq), then since
ln(fq) = ln(f) + ln(q), we can simply add -ln(f) to the running total.

We can therefore keep track of f = m * (m - 1) * ..., as above, and add that as
a "dummy" comparison.


Asymmetry
---------

The method above implies asymmetry, in that the unordered comparisons

    - proband = [A]
    - candidate = [A, B]

or

    - proband = [A]
    - candidate = [B, A]

would be less likely than

    - proband = [A, B]
    - candidate = [A]

because the correction (which increases the probability of a population match
by chance and therefore decreases the chance of the proband/candidate being the
same) relates to the number of candidate identifiers available.

This is probably fine and is a defence against a "cuckoo" candidate (cf.
"keyword stuffing" on web sites for search engines). For example, in our A-Z
situation, a candidate called [A, B, C, ..., X, Y, Z] is "trying" to be a good
match for everyone and perhaps shouldn't get the same probability of matching
[A] as a candidate simply named [A].

Note that there are other asymmetries already, though less obvious ones; for
example, using a very common surname and a rarer early example from the US name
database:

    - proband = Alice SMITH, same gender/DOB/postcode
    - candidate = Alice ABADILLA, same gender/DOB/postcode

      ... surname P(D|¬H) = 0.987 = P(no match | candidate not proband)
      ... log odds 12.455

    - proband = Alice ABADILLA, same gender/DOB/postcode
    - candidate = Alice SMITH, same gender/DOB/postcode

      ... surname P(D|¬H) = 0.996 = P(no match | candidate not proband)
      ... log odds 12.447

... because it's rarer for a randomly selected candidate to match ABADILLA than
SMITH, so P(D | ¬H) for a no-match is higher for proband ABADILLA, and that
provides slightly less evidence for a match when ABADILLA is the proband.

We use this unordered comparison for postcodes and surnames. So this multiple
comparisons correction is equivalent to saying "be a little bit more careful
about declaring a match against people with multiple postcodes and multiple
surnames, because they have a higher chance of appearing to match other people
at random".


Ordered comparisons
-------------------

Consider a proband such as [A, B, C] (n = 3) and a candidate such as [A, B] (m
= 2), where we wish to use the information that an ordered match is superior to
an unordered match. A simple way is as follows.

- Establish the "best" set of comparisons (highest LLR) following our standard
  rules. (In this case, that would be A/A, B/B, for c = 2.)

- Establish if that best match was strictly ordered. There should only be one
  way (for this method) that is defined as "strictly ordered", and we will
  define this as that the indexes of the comparisons, 1 ... c, exactly match
  the contributing indices of the proband (1 ... n) and the candidate (1 ...
  m). That is: strict order, no gaps.

- For a first draft, declare a probability p_o, the probability that if the
  proband/candidate are the same (H is true), the identifiers are correct and
  in same strict order, and a probability p_u that they are correct but
  unordered (not in strict order), and a probability p_e that they are wrong,
  such that p_o + p_u + p_e = 1.

  Then if there is an ordered match,

  - P(D | H) = p_o
  - P(D | ¬H) = P(random ordered match)

  and if there is an unordered match,

  - P(D | H) = p_u
  - P(D | ¬H) = P(random unordered match) - P(random unordered match)

  and if no match,

  - P(D | H) = p_e
  - P(D | ¬H) = 1 - [P(random unordered match) - P(random unordered match)]

- Then, to superimpose that on identifier comparisons that are themselves
  fuzzy, we note that much of those (e.g. p_e) are already dealt with. So
  if we restrict p_o and p_u to situations where there is a match (full or
  partial) involving two or more identifiers, and we continue to use the
  Bonferroni correction, it becomes straightforward.

"""


class ComparisonInfo:
    """
    Used by :func:`gen_best_comparisons`.
    """

    def __init__(
        self, proband_idx: int, candidate_idx: int, comparison: Comparison
    ) -> None:
        self.proband_idx = proband_idx
        self.candidate_idx = candidate_idx
        self.comparison = comparison

        # Precalculate these for speed (see sort_asc_best_to_worst):
        self.log_likelihood_ratio = comparison.log_likelihood_ratio
        self._distance = (proband_idx - candidate_idx) ** 2

    @staticmethod
    def sort_asc_best_to_worst(x: "ComparisonInfo") -> Tuple[float, int]:
        """
        Returns a sort value suitable for ASCENDING (standard, reverse=False)
        sorting to give a best-to-worst sort order.

        - The first part of the tuple is negative log likelihood ratio, so
          higher values are worse (because higher values of log likelihood
          ratio are better).

        - The second part of the tuple (the tie-breaker if NLLR is identical)
          is the square of the distance between the proband and candidate
          indexes. We prefer to use identical values (distance = squared
          distance = 0), so higher values are worse. This tiebreaker means
          that if we compare Alice Alice SMITH to Alice Alice SMITH on first
          names, we will choose index pairs (1, 1) and (2, 2), not (1, 2) and
          (2, 1).
        """
        return -x.log_likelihood_ratio, x._distance


def gen_best_comparisons(
    proband_identifiers: List[Identifier],
    candidate_identifiers: List[Identifier],
    ordered: bool = False,
    p_u: Optional[float] = None,
) -> Generator[Comparison, None, None]:
    """
    Generates comparisons for two sequences of identifiers (one from the
    proband, one from the candidate), being indifferent to their order. The
    method -- which needs to be fast -- is as described above in
    NOTES_MULTIPLE_COMPARISONS.

    Args:

        proband_identifiers:
            List of identifiers from the proband.
        candidate_identifiers:
            List of comparable identifiers from the candidate.
        ordered:
            Treat the comparison as an ordered one?
        p_u:
            (Applicable if ordered is True.) The probability of being
            "unordered", and the complement of p_o, where p_o is the
            probability, given the hypothesis H (proband and candidate are the
            same person) and that c > 1 identifiers are being compared, that
            the candidate identifiers will be in exactly the right order (that
            is, for all matches, the index of the candidate's identifier is the
            same as the index of the proband's identifier).
    """
    # Compare all pairs.
    ci_list = []  # type: List[ComparisonInfo]
    for p_idx, proband_id in enumerate(proband_identifiers):
        for c_idx, candidate_id in enumerate(candidate_identifiers):
            ci = proband_id.comparison(candidate_id)
            if ci is None:
                # This will happen if either is missing information, or if the
                # identifiers explicitly do not overlap temporally.
                continue
            ci_list.append(
                ComparisonInfo(
                    proband_idx=p_idx,
                    candidate_idx=c_idx,
                    comparison=ci,
                )
            )
    if not ci_list:
        # No comparisons. Abort before we do something silly with a correction
        # procedure.
        return

    # Iterate through comparisons in descending order of log likelihood ratio,
    # i.e. best to worst. See ComparisonInfo.sort_asc_best_to_worst().
    ci_list.sort(key=ComparisonInfo.sort_asc_best_to_worst)
    candidate_indexes_used = set()  # type: Set[int]
    proband_indexes_used = set()  # type: Set[int]
    n_candidates_available = n_candidates = len(candidate_identifiers)
    n_positive = 0
    n_implicit_comparisons = 1
    correct_order = True
    for ci in ci_list:
        if (
            ci.proband_idx in proband_indexes_used
            or ci.candidate_idx in candidate_indexes_used
        ):
            # Each identifier can use used as part of only one comparison.
            continue
        candidate_indexes_used.add(ci.candidate_idx)
        proband_indexes_used.add(ci.proband_idx)
        yield ci.comparison
        if ci.log_likelihood_ratio > 0:
            # This was some form of match, so we apply our correction.
            n_implicit_comparisons *= n_candidates_available
            n_positive += 1
            if ordered and ci.proband_idx != ci.candidate_idx:
                # Note that the index of ci itself is irrelevant; that will
                # vary depending on the frequency of the identifiers, e.g. John
                # Zachariah versus Zachariah John.
                correct_order = False
        n_candidates_available -= 1

    # Any corrections required.
    if ordered:
        # Ordered comparison requested.
        # Action only required if there is an ordering to be considered.
        p_o = 1 - p_u  # ordered, unordered
        if n_positive > 0 and n_candidates > 1:
            # There was a "hit", and there was a choice of candidate
            # identifiers, so there is an order to think about. ASSUMING unique
            # identifiers (within proband, within candidate):
            if correct_order:
                # - Adjust P(D | H) by p_o.
                # - No adjustment to P(D | ¬H) required.
                yield AdjustLogOddsComparison(
                    log_odds_delta=ln(p_o),
                    description=(
                        f"order match: adjust P(D|H) by "
                        f"P(correct order) = {p_o}"
                    ),
                )
            else:
                # - Adjust P(D | H) by p_u = 1 - p_o.
                # - Adjust P(D | ¬H) by the number of unordered possibilities
                #   considered (n_implicit_comparisons), minus the one (the
                #   correctly ordered option) that by definition we are not
                #   considering here. This uses a Bonferroni approximation, as
                #   above.
                n_unordered_possibilities = n_implicit_comparisons - 1
                description = (
                    f"order mismatch: "
                    f"adjust P(D|H) by P(incorrect order) = {p_u}"
                )
                if n_unordered_possibilities > 1:
                    description += (
                        f", and P(D|¬H) for {n_positive} hits from "
                        f"{n_unordered_possibilities} comparisons"
                    )
                yield AdjustLogOddsComparison(
                    log_odds_delta=ln(p_u) - ln(n_unordered_possibilities),
                    description=description,
                )

    else:
        # Unordered comparison requested.
        if n_implicit_comparisons > 1:
            # - P(D | H) does not require adjustment.
            # - Correct P(D | ¬H) for the fact that we would have considered
            #   any order acceptable, and we made multiple comparisons to pick
            #   the best. This uses a Bonferroni approximation, as above.
            yield AdjustLogOddsComparison(
                log_odds_delta=-ln(n_implicit_comparisons),
                description=(
                    f"unordered: adjust P(D|¬H) for {n_positive} "
                    f"hits from {n_implicit_comparisons} comparisons"
                ),
            )
