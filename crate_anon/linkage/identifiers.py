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

from crate_anon.common.logfunc import warn_once
from crate_anon.linkage.constants import VALID_GENDERS
from crate_anon.linkage.comparison import (
    Comparison,
    DirectComparison,
    mk_comparison_duo,
    mk_comparison_trio_full_error_prohibitive,
)
from crate_anon.linkage.helpers import (
    get_metaphone,
    get_postcode_sector,
    getdictprob,
    getdictval,
    is_valid_isoformat_date,
    isoformat_date_or_none,
    POSTCODE_REGEX,
    standardize_name,
    standardize_postcode,
)
from crate_anon.linkage.matchconfig import MatchConfig

log = logging.getLogger(__name__)


# =============================================================================
# Generic nugget of identification information for comparison
# =============================================================================


class Identifier(ABC):
    """
    Abstract base class: generic nugget of information about a person, in
    identifiable (plaintext) or de-identified (hashed) form. Optionally, may
    convey start/end dates.

    Note:

    - We trust that probabilities from the config have been validated (i.e. are
      in the range 0-1), but we should check values arising from incoming data,
      primarily via :meth:`from_hashed_dict`.
    - A typical comparison operation involves comparing a lot of people to
      each other, so it is usually efficient to cache "derived" information
      (e.g. we should calculate metaphones from names at creation, not at
      comparison). See :meth:`comparison`.
    """

    SEP = "/"  # separator
    NULL_VALUES_LOWERCASE = ["none", "null", "?"]  # must include "none"
    TEMPORAL_ID_FORMAT_HELP = (
        f"Temporal identifier format: IDENTIFIER{SEP}STARTDATE{SEP}ENDDATE, "
        f"where dates are in YYYY-MM-DD format or one of "
        f"{NULL_VALUES_LOWERCASE} (case-insensitive). The simpler format of "
        f"IDENTIFIER (which must not contain {SEP!r}) will also work."
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
        supports_partial_match: bool = True,
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
            supports_partial_match:
                Supports a partial match, as well as a full match comparison.
            temporal:
                Store start/end dates (which can be ``None``) along with the
                information?
            start_date:
                The start date (first valid date), or ``None``.
            end_date:
                The end date (last valid date), or ``None``.
        """
        nonetype = type(None)
        assert isinstance(cfg, (MatchConfig, nonetype))

        start_date = coerce_to_pendulum_date(start_date)
        if not isinstance(start_date, (Date, nonetype)):
            raise ValueError(f"Bad start_date: {start_date!r}")

        end_date = coerce_to_pendulum_date(end_date)
        if not isinstance(end_date, (Date, nonetype)):
            raise ValueError(f"Bad end_date: {end_date!r}")

        if start_date and end_date:
            if start_date > end_date:
                raise ValueError(
                    f"start_date = {start_date!r} > end_date = {end_date!r}"
                )

        self.cfg = cfg
        self.is_plaintext = is_plaintext
        self.supports_partial_match = supports_partial_match
        self.temporal = temporal
        self.start_date = start_date
        self.end_date = end_date

        self.comparison_full_match = None  # type: Optional[DirectComparison]
        self.comparison_partial_match = (
            None
        )  # type: Optional[DirectComparison]
        self.comparison_no_match = None  # type: Optional[DirectComparison]

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
            if self.temporal:
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
    def hashed_dict(self, include_frequencies: bool = True) -> Dict[str, Any]:
        """
        Represents the object in a dictionary suitable for JSON serialization,
        for the de-identified (hashed) version.

        Args:
            include_frequencies:
                Include frequency information. If you don't, this makes the
                resulting file suitable for use as a sample, but not as a
                proband file.
        """
        pass

    @classmethod
    @abstractmethod
    def from_hashed_dict(
        cls, cfg: MatchConfig, d: Dict[str, Any]
    ) -> "Identifier":
        """
        Restore a hashed version from a dictionary (which has been read from
        JSON).
        """
        pass

    # -------------------------------------------------------------------------
    # Internal methods to support creation
    # -------------------------------------------------------------------------

    def _clear_comparisons(self) -> None:
        """
        Reset our comparison objects.
        """
        self.comparison_full_match = None
        self.comparison_partial_match = None
        self.comparison_no_match = None

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

    def _round(self, x: Optional[float]) -> Optional[float]:
        """
        Implements config-defined rounding for frequency representations of
        hashed values.

        Rounds frequencies to a certain number of significant figures.
        (Don't supply exact floating-point numbers for frequencies; may be
        more identifying. Don't use decimal places; we have to deal with
        some small numbers.)
        """
        if x is None:
            return None
        sf = self.cfg.rounding_sf
        if sf is None:
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

    @abstractmethod
    def fully_matches(self, other: "Identifier") -> bool:
        """
        Does this identifier fully match the other?

        You can assume that both sides contain relevant information (or this
        function should not have been called) -- that is, that bool(self) is
        True and bool(other) is True and self.overlaps(other) is True.
        """
        pass

    @abstractmethod
    def partially_matches(self, other: "Identifier") -> bool:
        """
        Does this identifier fully match the other?

        You can assume that both sides contain relevant information (or this
        function should not have been called) -- that is, that bool(self) is
        True and bool(other) is True and self.overlaps(other) is True.
        """
        pass

    def comparison(self, other: "Identifier") -> Optional[Comparison]:
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
        if not (self and other and self.overlaps(other)):
            # Infer no conclusions from absent information.
            return None
        if self.fully_matches(other):
            return self.comparison_full_match
        if self.supports_partial_match and self.partially_matches(other):
            return self.comparison_partial_match
        return self.comparison_no_match

    def overlaps(self, other: "Identifier") -> bool:
        """
        Do ``self`` and ``other`` overlap in time?

        Args:
            other:
                the other :class:`Identifier`

        For similar logic, see
        :meth:`cardinal_pythonlib.interval.Interval.overlaps`.
        """
        if not self.temporal or not other.temporal:
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
    def hashed_dict(self, include_frequencies: bool = True) -> Dict[str, Any]:
        raise AssertionError(self.BAD_METHOD)

    # noinspection PyTypeChecker
    @classmethod
    def from_hashed_dict(
        cls, cfg: MatchConfig, d: Dict[str, Any]
    ) -> "TemporalIDHolder":
        raise AssertionError(cls.BAD_METHOD)

    # noinspection PyTypeChecker
    def _round(self, x: Optional[float]) -> Optional[float]:
        raise AssertionError(self.BAD_METHOD)

    def __bool__(self) -> bool:
        return bool(self.identifier)

    def ensure_has_freq_info_if_id_present(self) -> None:
        pass

    def fully_matches(self, other: "Identifier") -> bool:
        raise AssertionError(self.BAD_METHOD)

    def partially_matches(self, other: "Identifier") -> bool:
        raise AssertionError(self.BAD_METHOD)

    def comparison(self, other: "Identifier") -> Optional[Comparison]:
        raise AssertionError(self.BAD_METHOD)


# =============================================================================
# Postcode
# =============================================================================


class Postcode(Identifier):
    """
    Represents a UK postcode.
    """

    KEY_HASHED_POSTCODE_UNIT = "hashed_postcode_unit"
    KEY_HASHED_POSTCODE_SECTOR = "hashed_postcode_sector"
    KEY_UNIT_FREQ = "unit_freq"
    KEY_SECTOR_FREQ = "sector_freq"

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
        else:
            self.postcode_unit = ""
            self.postcode_sector = ""
            self.unit_freq = None  # type: Optional[float]
            self.sector_freq = None  # type: Optional[float]

        # Precalculate comparisons, for speed, but in a way that we can update
        # them if we are being created via from_hashed_dict().
        self._set_comparisons()

    def _set_comparisons(self) -> None:
        # We only perform a postcode comparison if there is at least a partial
        # match, so the "no match" condition is not important.
        if self.postcode_unit:
            (
                self.comparison_full_match,
                self.comparison_partial_match,
                self.comparison_no_match,
            ) = mk_comparison_trio_full_error_prohibitive(
                p_f=self.unit_freq,
                p_p=self.sector_freq,
                p_ep=self.cfg.p_minor_postcode_error,
            )
        else:
            self._clear_comparisons()

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

    def hashed_dict(self, include_frequencies: bool = True) -> Dict[str, Any]:
        """
        For JSON.
        """
        if not self.postcode_unit:
            hashed_postcode_unit = None
            hashed_postcode_sector = None
        elif self.is_plaintext:
            hashed_postcode_unit = self.cfg.hash_fn(self.postcode_unit)
            hashed_postcode_sector = self.cfg.hash_fn(self.postcode_sector)
        else:
            # Was already hashed
            hashed_postcode_unit = self.postcode_unit
            hashed_postcode_sector = self.postcode_sector
        d = {
            self.KEY_START_DATE: isoformat_date_or_none(self.start_date),
            self.KEY_END_DATE: isoformat_date_or_none(self.end_date),
            self.KEY_HASHED_POSTCODE_UNIT: hashed_postcode_unit,
            self.KEY_HASHED_POSTCODE_SECTOR: hashed_postcode_sector,
        }
        if include_frequencies:
            d[self.KEY_UNIT_FREQ] = self._round(self.unit_freq)
            d[self.KEY_SECTOR_FREQ] = self._round(self.sector_freq)
        return d

    @classmethod
    def from_hashed_dict(
        cls, cfg: MatchConfig, d: Dict[str, Any]
    ) -> "Postcode":
        """
        Creation of a hashed postcode, ultimately from JSON.
        """
        p = Postcode(
            cfg=cfg,
            start_date=d[cls.KEY_START_DATE],
            end_date=d[cls.KEY_END_DATE],
        )
        p.is_plaintext = False
        p.postcode_unit = getdictval(d, cls.KEY_HASHED_POSTCODE_UNIT, str)
        p.postcode_sector = getdictval(d, cls.KEY_HASHED_POSTCODE_SECTOR, str)
        p.unit_freq = getdictprob(d, cls.KEY_UNIT_FREQ)
        p.sector_freq = getdictprob(d, cls.KEY_SECTOR_FREQ)
        p._set_comparisons()
        return p

    def __bool__(self) -> bool:
        return bool(self.postcode_unit)

    def ensure_has_freq_info_if_id_present(self) -> None:
        if self.postcode_unit and (
            self.unit_freq is None or self.sector_freq is None
        ):
            raise ValueError(
                self.ERR_MISSING_FREQ + f" for postcode {self.postcode_unit!r}"
            )

    def fully_matches(self, other: "Postcode") -> bool:
        return self.postcode_unit == other.postcode_unit

    def partially_matches(self, other: "Postcode") -> bool:
        return self.postcode_sector == other.postcode_sector


# =============================================================================
# Date of birth
# =============================================================================


class DateOfBirth(Identifier):
    """
    Represents a date of birth.
    """

    KEY_HASHED_DOB = "hashed_dob"
    KEY_HASHED_DOB_MD = "hashed_dob_md"
    KEY_HASHED_DOB_YD = "hashed_dob_yd"
    KEY_HASHED_DOB_YM = "hashed_dob_ym"

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

        self.dob_str = dob
        # In our validation data, 93.3% of DOB errors were "single component"
        # errors, e.g. year wrong but month/day right. Within that, there was
        # no very dominant pattern.
        if dob:
            dob_date = coerce_to_pendulum_date(dob)
            # ISO format is %Y-%m-%d; see
            # https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes  # noqa
            # Here we want the shortest full representation; these are not
            # intended to be human-legible.
            self.dob_md = dob_date.strftime("%m%d")
            self.dob_yd = dob_date.strftime("%Y%d")
            self.dob_ym = dob_date.strftime("%Y%m")
        else:
            self.dob_md = ""
            self.dob_yd = ""
            self.dob_ym = ""

        # Precalculate our comparison objects, for speed.
        # We don't need a separate function here, because these frequencies are
        # all set from the config, not our data.
        self.comparison_full_match = DirectComparison(
            p_d_given_same_person=cfg.p_dob_correct,
            p_d_given_diff_person=cfg.p_two_people_share_dob_ymd,
        )
        self.comparison_partial_match = DirectComparison(
            p_d_given_same_person=cfg.p_dob_single_component_error,
            p_d_given_diff_person=cfg.p_two_people_partial_not_full_dob_match,
        )
        self.comparison_no_match = DirectComparison(
            p_d_given_same_person=cfg.p_dob_major_error,
            p_d_given_diff_person=cfg.p_two_people_no_dob_similarity,
        )

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

    def hashed_dict(self, include_frequencies: bool = True) -> Dict[str, Any]:
        """
        For JSON.
        """
        if not self.dob_str:
            hashed_dob = None
            hashed_dob_md = None
            hashed_dob_yd = None
            hashed_dob_ym = None
        elif self.is_plaintext:
            hash_fn = self.cfg.hash_fn
            hashed_dob = hash_fn(self.dob_str)
            hashed_dob_md = hash_fn(self.dob_md)
            hashed_dob_yd = hash_fn(self.dob_yd)
            hashed_dob_ym = hash_fn(self.dob_ym)
        else:
            # Was already hashed
            hashed_dob = self.dob_str
            hashed_dob_md = self.dob_md
            hashed_dob_yd = self.dob_yd
            hashed_dob_ym = self.dob_ym
        return {
            self.KEY_HASHED_DOB: hashed_dob,
            self.KEY_HASHED_DOB_MD: hashed_dob_md,
            self.KEY_HASHED_DOB_YD: hashed_dob_yd,
            self.KEY_HASHED_DOB_YM: hashed_dob_ym,
        }

    @classmethod
    def from_hashed_dict(
        cls, cfg: MatchConfig, d: Dict[str, Any]
    ) -> "DateOfBirth":
        """
        Creation of a hashed DOB, ultimately from JSON.
        """
        x = DateOfBirth(cfg=cfg)
        x.is_plaintext = False
        x.dob_str = getdictval(d, cls.KEY_HASHED_DOB, str)
        x.dob_md = getdictval(d, cls.KEY_HASHED_DOB_MD, str)
        x.dob_yd = getdictval(d, cls.KEY_HASHED_DOB_YD, str)
        x.dob_ym = getdictval(d, cls.KEY_HASHED_DOB_YM, str)
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


class Gender(Identifier):
    KEY_HASHED_GENDER = "hashed_gender"
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
            supports_partial_match=False,
            temporal=False,
        )

        gender = gender or ""
        if gender not in VALID_GENDERS:
            raise ValueError(f"Bad gender: {gender!r}")

        self.gender = gender
        if gender:
            self.gender_freq = cfg.gender_freq(gender)
        else:
            self.gender_freq = None  # type: Optional[float]

        self._set_comparisons()

    def _set_comparisons(self) -> None:
        if self.gender_freq:
            (
                self.comparison_full_match,
                self.comparison_no_match,
            ) = mk_comparison_duo(
                p_match_given_same_person=1 - self.cfg.p_gender_error,
                p_match_given_diff_person=self.gender_freq,
            )
        else:
            self._clear_comparisons()

    def plaintext_str_core(self) -> str:
        """
        For CSV.
        """
        return self.gender

    @classmethod
    def from_plaintext_str(cls, cfg: MatchConfig, x: str) -> "Gender":
        """
        Creation from CSV.
        """
        return Gender(cfg=cfg, gender=x)

    def hashed_dict(self, include_frequencies: bool = True) -> Dict[str, Any]:
        """
        For JSON.
        """
        if not self.gender:
            hashed_gender = None
        elif self.is_plaintext:
            hashed_gender = self.cfg.hash_fn(self.gender)
        else:
            # Was already hashed
            hashed_gender = self.gender
        d = {
            self.KEY_HASHED_GENDER: hashed_gender,
        }
        if include_frequencies:
            d[self.KEY_GENDER_FREQ] = self._round(self.gender_freq)
        return d

    @classmethod
    def from_hashed_dict(cls, cfg: MatchConfig, d: Dict[str, Any]) -> "Gender":
        """
        Creation of a hashed gender, ultimately from JSON.
        """
        g = Gender(cfg=cfg)
        g.is_plaintext = False
        g.gender = getdictval(d, cls.KEY_HASHED_GENDER, str)
        g.gender_freq = getdictprob(d, cls.KEY_GENDER_FREQ)
        g._set_comparisons()
        return g

    def __bool__(self) -> bool:
        return bool(self.gender)

    def ensure_has_freq_info_if_id_present(self) -> None:
        if self.gender and self.gender_freq is None:
            raise ValueError(
                self.ERR_MISSING_FREQ + f" for gender {self.gender!r}"
            )

    def fully_matches(self, other: "Gender") -> bool:
        return self.gender == other.gender

    def partially_matches(self, other: "Identifier") -> bool:
        """
        Gender is treated as a yes/no match.
        """
        return False


# =============================================================================
# Names
# =============================================================================


class Name(Identifier, ABC):
    """
    Base class for names.

    We will need some special gender features for both forenames and surnames:

    - UK forename frequency depends on gender.
    - The probability that someone's surname changes depends on gender.
    """

    KEY_HASHED_NAME = "hashed_name"
    KEY_HASHED_METAPHONE = "hashed_metaphone"
    KEY_NAME_FREQ = "name_freq"
    KEY_METAPHONE_FREQ = "metaphone_freq"

    def __init__(
        self, cfg: MatchConfig, name: str = "", gender: str = ""
    ) -> None:
        """
        Plaintext creation of a name.

        Args:
            cfg:
                The config object.
            name:
                (PLAINTEXT.) The name.
        """
        super().__init__(cfg=cfg, is_plaintext=True, temporal=False)

        if not isinstance(name, str):
            raise ValueError(f"Bad name: {name!r}")

        self.name = standardize_name(name)
        self.metaphone = get_metaphone(self.name)

        self.name_freq = None  # type: Optional[float]
        self.metaphone_freq = None  # type: Optional[float]

        self.gender = ""
        self.set_gender(gender)  # may reset frequencies; will set comparisons

    def set_gender(self, gender: str) -> None:
        """
        Special operation for identifiable reading.
        """
        if gender not in VALID_GENDERS:
            raise ValueError(f"Bad gender: {gender!r}")
        self.gender = gender
        self._reset_frequencies_identifiable()
        self._set_comparisons()

    @abstractmethod
    def _reset_frequencies_identifiable(self) -> None:
        """
        Gender may have changed. Update any probabilities accordingly.
        """
        pass

    @abstractmethod
    def _set_comparisons(self) -> None:
        """
        Set comparison objects.
        """
        pass

    def plaintext_str_core(self) -> str:
        """
        For CSV.
        """
        return self.name

    def hashed_dict(self, include_frequencies: bool = True) -> Dict[str, Any]:
        """
        For JSON.
        """
        if not self.name:
            hashed_name = None
            hashed_metaphone = None
        elif self.is_plaintext:
            hashed_name = self.cfg.hash_fn(self.name)
            hashed_metaphone = self.cfg.hash_fn(self.metaphone)
        else:
            # Was already hashed
            hashed_name = self.name
            hashed_metaphone = self.metaphone
        d = {
            self.KEY_HASHED_NAME: hashed_name,
            self.KEY_HASHED_METAPHONE: hashed_metaphone,
        }
        if include_frequencies:
            d[self.KEY_NAME_FREQ] = self._round(self.name_freq)
            d[self.KEY_METAPHONE_FREQ] = self._round(self.metaphone_freq)
        return d

    def __bool__(self) -> bool:
        return bool(self.name)

    def ensure_has_freq_info_if_id_present(self) -> None:
        if self.name and (
            self.name_freq is None or self.metaphone_freq is None
        ):
            raise ValueError(
                self.ERR_MISSING_FREQ + f" for name {self.name!r}"
            )

    def fully_matches(self, other: "Name") -> bool:
        return self.name == other.name

    def partially_matches(self, other: "Name") -> bool:
        return self.metaphone == other.metaphone


class Forename(Name):
    """
    Represents a forename (given name).
    """

    def __init__(
        self, cfg: MatchConfig, name: str = "", gender: str = ""
    ) -> None:
        super().__init__(cfg=cfg, name=name, gender=gender)

    def _reset_frequencies_identifiable(self) -> None:
        if self.name:
            self.name_freq = self.cfg.forename_freq(
                self.name, self.gender, prestandardized=True
            )
            self.metaphone_freq = self.cfg.forename_metaphone_freq(
                self.metaphone, self.gender
            )
        else:
            self.name_freq = None
            self.metaphone_freq = None
        self._set_comparisons()

    def _set_comparisons(self) -> None:
        if self.name:
            (
                self.comparison_full_match,
                self.comparison_partial_match,
                self.comparison_no_match,
            ) = mk_comparison_trio_full_error_prohibitive(
                p_f=self.name_freq,
                p_p=self.metaphone_freq,
                p_ep=self.cfg.p_minor_forename_error,
            )
        else:
            self._clear_comparisons()

    @classmethod
    def from_plaintext_str(cls, cfg: MatchConfig, x: str) -> "Forename":
        """
        Creation from CSV.
        """
        return Forename(cfg=cfg, name=x)

    @classmethod
    def from_hashed_dict(
        cls, cfg: MatchConfig, d: Dict[str, Any]
    ) -> "Forename":
        """
        Creation of a hashed name, ultimately from JSON.
        """
        n = Forename(cfg=cfg)
        n.is_plaintext = False
        n.name = getdictval(d, cls.KEY_HASHED_NAME, str)
        n.metaphone = getdictval(d, cls.KEY_HASHED_METAPHONE, str)
        n.name_freq = getdictprob(d, cls.KEY_NAME_FREQ)
        n.metaphone_freq = getdictprob(d, cls.KEY_METAPHONE_FREQ)
        n._set_comparisons()
        return n


class Surname(Name):
    """
    Represents a surname (family name).
    """

    def __init__(
        self, cfg: MatchConfig, name: str = "", gender: str = ""
    ) -> None:
        super().__init__(cfg=cfg, name=name, gender=gender)

    def _reset_frequencies_identifiable(self) -> None:
        if self.name:
            self.name_freq = self.cfg.surname_freq(
                self.name, prestandardized=True
            )
            self.metaphone_freq = self.cfg.surname_metaphone_freq(
                self.metaphone
            )
        warn_once(
            "TODO: implement gender aspects of "
            "Surname._reset_frequencies_identifiable"
        )

    def _set_comparisons(self) -> None:
        if self.name:
            (
                self.comparison_full_match,
                self.comparison_partial_match,
                self.comparison_no_match,
            ) = mk_comparison_trio_full_error_prohibitive(
                p_f=self.name_freq,
                p_p=self.metaphone_freq,
                p_ep=self.cfg.p_minor_surname_error,
            )
        else:
            self._clear_comparisons()

    @classmethod
    def from_plaintext_str(cls, cfg: MatchConfig, x: str) -> "Surname":
        """
        Creation from CSV.
        """
        return Surname(cfg=cfg, name=x)

    @classmethod
    def from_hashed_dict(
        cls, cfg: MatchConfig, d: Dict[str, Any]
    ) -> "Surname":
        """
        Creation of a hashed name, ultimately from JSON.
        """
        n = Surname(cfg=cfg)
        n.is_plaintext = False
        n.name = getdictval(d, cls.KEY_HASHED_NAME, str)
        n.metaphone = getdictval(d, cls.KEY_HASHED_METAPHONE, str)
        n.name_freq = getdictprob(d, cls.KEY_NAME_FREQ)
        n.metaphone_freq = getdictprob(d, cls.KEY_METAPHONE_FREQ)
        n._set_comparisons()
        return n


# =============================================================================
# Comparison of multiple potentially jumbled similar identifiers
# =============================================================================


def gen_best_comparisons(
    proband_identifiers: List[Identifier],
    candidate_identifiers: List[Identifier],
    no_match_comparison: Optional[DirectComparison] = None,
) -> Generator[DirectComparison, None, None]:
    """
    Generates comparisons for two sequences of identifiers (one from the
    proband, one from the candidate), being indifferent to their order. The
    method is:

    - Identifiers that are explicitly time-stamped cannot be compared with
      explicitly non-overlapping identifiers. (But un-time-stamped
      identifiers can be compared with anything).

    - No identifier can be used for >1 comparison.

    - Full matches are preferred.

    - Partial matches are sought next.

    - If none are achieved, but there are identifiers, yield a single no-match
      comparison, as specified by the caller. If this is None, we don't bother
      to yield it.

    - Try to be quick.

    This method is typically used instead of identifier.comparison(other) if
    there are a collection on both/either side (e.g. surname), not just a
    single (e.g. DOB).
    """
    # Remove uninformative identifiers (for which bool(x) gives False):
    proband_identifiers = list(filter(None, proband_identifiers))
    candidate_identifiers = list(filter(None, candidate_identifiers))
    if not proband_identifiers or not candidate_identifiers:
        return

    found_something = False
    candidate_indexes_used = set()  # type: Set[int]
    proband_indexes_used = set()  # type: Set[int]
    non_overlapping_c_p = set()  # type: Set[Tuple[int, int]]

    # Look for full matches:
    for c, candidate_id in enumerate(candidate_identifiers):
        for p, proband_id in enumerate(proband_identifiers):
            if p in proband_indexes_used:
                continue
            if not candidate_id.overlaps(proband_id):
                non_overlapping_c_p.add((c, p))
                continue
            if candidate_id.fully_matches(proband_id):
                found_something = True
                yield proband_id.comparison_full_match
                candidate_indexes_used.add(c)
                proband_indexes_used.add(p)
                break  # next candidate

    # Try for any partial matches for identifiers not yet fully matched:
    for c, candidate_id in enumerate(candidate_identifiers):
        if c in candidate_indexes_used:
            continue
        for p, proband_id in enumerate(proband_identifiers):
            if p in proband_indexes_used:
                continue
            if (c, p) in non_overlapping_c_p:
                # This method avoids calling the overlap() function twice.
                continue
            if candidate_id.partially_matches(proband_id):
                found_something = True
                yield proband_id.comparison_partial_match
                candidate_indexes_used.add(c)
                proband_indexes_used.add(p)
                break  # next candidate

    # No joy.
    if not found_something and no_match_comparison:
        yield no_match_comparison
