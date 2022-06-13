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
from typing import Any, Dict, Optional, Tuple, Type, Union

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
    FullPartialNoMatchComparison,
    MatchNoMatchComparison,
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
        f"{NULL_VALUES_LOWERCASE} (case-insensitive)."
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
        self.temporal = temporal
        self.start_date = start_date
        self.end_date = end_date

    def __str__(self) -> str:
        """
        A string representation used for CSV files.
        """
        if not self:
            # No information
            return ""
        if not self.is_plaintext:
            raise AssertionError("Don't use str() with de-identified info")
        # Identifiable
        id_str = self.plaintext_str_core()
        if self.temporal:
            if self.SEP in id_str:
                raise ValueError(
                    f"Temporal identifier unsuitable: contains {self.SEP!r}"
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

    @classmethod
    def _get_temporal_triplet(
        cls, x: str
    ) -> Tuple[str, Optional[Date], Optional[Date]]:
        """
        From a string (e.g. from CSV), split into CONTENTS/START_DATE/END_DATE.

        Args:
            x:
                String to parse.

        Returns:
            tuple:
                contents, start_date, end_date
        """
        # Extract components of the string
        components = x.split(cls.SEP)
        if len(components) != 3:
            raise ValueError(
                f"Need 3 components separated by {cls.SEP!r}; got {x!r}"
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
            end_date = None
        else:
            try:
                end_date = pendulum.parse(end_date_str).date()
            except ParserError:
                raise ValueError(f"Bad date: {end_date_str!r}")
        # Return the elements
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
        raise AssertionError("Do not use hashed_dict() with this class")

    # noinspection PyTypeChecker
    @classmethod
    def from_hashed_dict(
        cls, cfg: MatchConfig, d: Dict[str, Any]
    ) -> "TemporalIDHolder":
        raise AssertionError("Do not use from_hashed_dict() with this class")

    # noinspection PyTypeChecker
    def _round(self, x: Optional[float]) -> Optional[float]:
        raise AssertionError("Do not use _round() with this class")

    def __bool__(self) -> bool:
        return bool(self.identifier)

    def ensure_has_freq_info_if_id_present(self) -> None:
        pass

    def comparison(self, other: "Identifier") -> Optional[Comparison]:
        raise AssertionError("Do not use hashed_dict() with this class")


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

        self.p_minor_postcode_error = self.cfg.p_minor_postcode_error

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

    def comparison(self, other: "Postcode") -> Optional[Comparison]:
        """
        Compare one postcode to another.
        """
        # assert self.is_plaintext == other.is_plaintext
        if (
            not self.postcode_unit
            or not other.postcode_unit
            or not self.overlaps(other)
        ):
            # Infer no conclusions from missing information.
            # If postcode_unit is present, we've guaranteed that
            # postcode_sector will be.
            return None
        return FullPartialNoMatchComparison(
            full_match=(self.postcode_unit == other.postcode_unit),
            p_f=self.unit_freq,
            p_e=self.p_minor_postcode_error,
            partial_match=(self.postcode_sector == other.postcode_sector),
            p_p=self.sector_freq,
        )

    # -------------------------------------------------------------------------
    # Extras
    # -------------------------------------------------------------------------

    def fully_matches(self, other: "Postcode") -> bool:
        """
        For postcode comparison, we ignore wholly dissimilar postcodes (rather
        than treating them as evidence against a match).
        """
        return self.postcode_unit and self.postcode_unit == other.postcode_unit

    def partially_matches(self, other: "Postcode") -> bool:
        """
        See :meth:`fully_matches`. Does not exclude a full match also.
        """
        return (
            self.postcode_sector
            and self.postcode_sector == other.postcode_sector
        )


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

    def comparison(self, other: "DateOfBirth") -> Optional[Comparison]:
        if not self.dob_str or not other.dob_str:
            # Missing information; infer nothing.
            return None
        cfg = self.cfg
        if self.dob_str == other.dob_str:
            # Exact match
            return DirectComparison(
                p_d_given_same_person=cfg.p_dob_correct,
                p_d_given_diff_person=cfg.p_two_people_share_dob_ymd,
            )
        elif (
            self.dob_md == other.dob_md
            or self.dob_yd == other.dob_yd
            or self.dob_ym == other.dob_ym
        ):
            # Partial match. (But not a full match, from the previous test.)
            return DirectComparison(
                p_d_given_same_person=cfg.p_dob_single_component_error,
                p_d_given_diff_person=cfg.p_two_people_partial_dob_match,
            )
        else:
            # No match
            return DirectComparison(
                p_d_given_same_person=cfg.p_dob_major_error,
                p_d_given_diff_person=cfg.p_two_people_no_dob_similarity,
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
        super().__init__(cfg=cfg, is_plaintext=True, temporal=False)

        gender = gender or ""
        if gender not in VALID_GENDERS:
            raise ValueError(f"Bad gender: {gender!r}")

        self.gender = gender
        if gender:
            self.gender_freq = cfg.gender_freq(gender)
        else:
            self.gender_freq = None  # type: Optional[float]
        self.p_gender_error = cfg.p_gender_error
        self.p_match_given_same_person = 1 - self.p_gender_error

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
        x = Gender(cfg=cfg)
        x.is_plaintext = False
        x.gender = getdictval(d, cls.KEY_HASHED_GENDER, str)
        x.gender_freq = getdictprob(d, cls.KEY_GENDER_FREQ)
        return x

    def __bool__(self) -> bool:
        return bool(self.gender)

    def ensure_has_freq_info_if_id_present(self) -> None:
        if self.gender and self.gender_freq is None:
            raise ValueError(
                self.ERR_MISSING_FREQ + f" for gender {self.gender!r}"
            )

    def comparison(self, other: "Gender") -> Optional[Comparison]:
        if not self.gender or not other.gender:
            # Missing information; infer nothing.
            return None
        return MatchNoMatchComparison(
            match=(self.gender == other.gender),
            p_match_given_same_person=self.p_match_given_same_person,
            p_match_given_diff_person=self.gender_freq,
        )


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
        self.set_gender(gender)  # may reset frequencies

    def set_gender(self, gender: str) -> None:
        """
        Special operation for identifiable reading.
        """
        if gender not in VALID_GENDERS:
            raise ValueError(f"Bad gender: {gender!r}")
        self.gender = gender
        if self.name:
            self._reset_frequencies_identifiable()

    @abstractmethod
    def _reset_frequencies_identifiable(self) -> None:
        """
        Gender may have changed. Update any probabilities accordingly.
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


class Forename(Name):
    """
    Represents a forename (given name).
    """

    def __init__(
        self, cfg: MatchConfig, name: str = "", gender: str = ""
    ) -> None:
        super().__init__(cfg=cfg, name=name, gender=gender)

        self.p_minor_name_error = self.cfg.p_minor_forename_error

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
        return n

    def comparison(self, other: "Forename") -> Optional[Comparison]:
        if not self.name or not other.name:
            # No information
            return None
        return FullPartialNoMatchComparison(
            full_match=(self.name == other.name),
            p_f=self.name_freq,
            p_e=self.p_minor_name_error,
            partial_match=(self.metaphone == other.metaphone),
            p_p=self.metaphone_freq,
        )


class Surname(Name):
    """
    Represents a surname (family name).
    """

    def __init__(
        self, cfg: MatchConfig, name: str = "", gender: str = ""
    ) -> None:
        super().__init__(cfg=cfg, name=name, gender=gender)

        self.p_minor_name_error = self.cfg.p_minor_surname_error

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
        return n

    def comparison(self, other: "Surname") -> Optional[Comparison]:
        if not self.name or not other.name:
            # No information
            return None
        return FullPartialNoMatchComparison(
            full_match=(self.name == other.name),
            p_f=self.name_freq,
            p_e=self.p_minor_name_error,
            partial_match=(self.metaphone == other.metaphone),
            p_p=self.metaphone_freq,
        )
