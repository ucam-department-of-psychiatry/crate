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

from crate_anon.linkage.constants import VALID_GENDERS
from crate_anon.linkage.comparison import (
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
    mk_blurry_dates,
    POSTCODE_REGEX,
    standardize_name,
    standardize_perfect_id_key,
    standardize_perfect_id_value,
    standardize_postcode,
    surname_alternative_fragments,
    validateprob,
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
        if not self.start_date and not self.end_date:
            self.temporal = False  # saves some time later

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

    @abstractmethod
    def comparison(self, other: "Identifier") -> Optional[Comparison]:
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

        You can assume that both sides contain relevant information (or this
        function should not have been called) -- that is, that bool(self) is
        True and bool(other) is True and self.overlaps(other) is True.
        """
        pass

    def comparison(self, other: "IdentifierTwoState") -> Optional[Comparison]:
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
        return self.comparison_no_match


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

        You can assume that both sides contain relevant information (or this
        function should not have been called) -- that is, that bool(self) is
        True and bool(other) is True and self.overlaps(other) is True.
        """
        pass

    def comparison(
        self, other: "IdentifierThreeState"
    ) -> Optional[Comparison]:
        """
        See :meth:`IdentifierTwoState.comparison`.
        """
        if not (self and other and self.overlaps(other)):
            # Infer no conclusions from absent information.
            return None
        if self.fully_matches(other):
            return self.comparison_full_match
        if self.partially_matches(other):
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

        You can assume that both sides contain relevant information (or this
        function should not have been called) -- that is, that bool(self) is
        True and bool(other) is True and self.overlaps(other) is True.
        """
        pass

    def comparison(self, other: "IdentifierFourState") -> Optional[Comparison]:
        """
        See :meth:`IdentifierTwoState.comparison`.
        """
        if not (self and other and self.overlaps(other)):
            # Infer no conclusions from absent information.
            return None
        if self.fully_matches(other):
            return self.comparison_full_match
        if self.partially_matches(other):
            return self.comparison_partial_match
        if self.partially_matches_second(other):
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

    def comparison(self, other: "Identifier") -> Optional[Comparison]:
        raise AssertionError(self.BAD_METHOD)


# =============================================================================
# Postcode
# =============================================================================


class Postcode(IdentifierThreeState):
    """
    Represents a UK postcode.
    """

    KEY_POSTCODE_UNIT = "postcode_unit"
    KEY_POSTCODE_SECTOR = "postcode_sector"
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
        # match, so the "no match" condition is not important, and p_en = 0.
        if self.postcode_unit:
            p_ep = self.cfg.p_ep_postcode_minor_error
            p_f = self.unit_freq
            p_p = self.sector_freq
            p_pnf = p_p - p_f
            validateprob(p_pnf, "Postcode p_pnf = sector_freq - unit_freq")
            self.comparison_full_match = DirectComparison(
                p_d_given_same_person=1 - p_ep,  # p_c
                p_d_given_diff_person=p_f,
            )
            self.comparison_partial_match = DirectComparison(
                p_d_given_same_person=p_ep,
                p_d_given_diff_person=p_pnf,
            )
            self.comparison_no_match = DirectComparison(
                p_d_given_same_person=0,
                p_d_given_diff_person=1 - p_p,  # p_n; unimportant, as above
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
            self.KEY_START_DATE: isoformat_date_or_none(self.start_date),
            self.KEY_END_DATE: isoformat_date_or_none(self.end_date),
            self.KEY_POSTCODE_UNIT: postcode_unit,
            self.KEY_POSTCODE_SECTOR: postcode_sector,
        }
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
            start_date=d[cls.KEY_START_DATE],
            end_date=d[cls.KEY_END_DATE],
        )
        p.is_plaintext = not hashed
        p.postcode_unit = getdictval(d, cls.KEY_POSTCODE_UNIT, str)
        p.postcode_sector = getdictval(d, cls.KEY_POSTCODE_SECTOR, str)
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

        self.dob_str = dob
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
        )
        self.comparison_partial_match = DirectComparison(
            p_d_given_same_person=cfg.p_ep_dob,
            p_d_given_diff_person=cfg.p_pnf_dob,
        )
        self.comparison_no_match = DirectComparison(
            p_d_given_same_person=cfg.p_en_dob,
            p_d_given_diff_person=cfg.p_n_dob,
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

    def as_dict(
        self, encrypt: bool = True, include_frequencies: bool = True
    ) -> Dict[str, Any]:
        """
        For JSON.
        """
        if not self.dob_str:
            dob = None
            dob_md = None
            dob_yd = None
            dob_ym = None
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
            self.comparison_match = DirectComparison(
                p_d_given_same_person=1 - p_e,
                p_d_given_diff_person=p_f,
            )
            self.comparison_no_match = DirectComparison(
                p_d_given_same_person=p_e,
                p_d_given_diff_person=1 - p_f,
            )
        else:
            self._clear_comparisons()

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
            gender = None
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
    """  # noqa

    KEY_NAME = "name"
    KEY_METAPHONE = "metaphone"
    KEY_FIRST_TWO_CHAR = "f2c"

    # Terse in the JSON, to save some space:
    KEY_P_F_NAME_FREQ = "p_f"
    KEY_P_P1NF_METAPHONE_NOT_NAME = "p_p1nf"
    KEY_P_P2NP1_F2C_NOT_METAPHONE_OR_NAME = "p_p2np1"

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
        if not isinstance(name, str):
            raise ValueError(f"Bad name: {name!r}")

        super().__init__(cfg=cfg, is_plaintext=True, temporal=False)

        # Standardization necessary for freq. lookup and metaphone.
        self.name = standardize_name(name)
        self.metaphone = get_metaphone(self.name)
        self.f2c = get_first_two_char(self.name)

        # Population frequencies -- to be overridden
        self.pf_pop_name_freq = None  # type: Optional[float]
        self.p_p1nf_metaphone_not_name = None  # type: Optional[float]
        self.p_p2np1_f2c_not_metaphone_or_name = None  # type: Optional[float]

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
        Clear our population frequencies.
        """
        self.pf_pop_name_freq = None
        self.p_p1nf_metaphone_not_name = None
        self.p_p2np1_f2c_not_metaphone_or_name = None

    @abstractmethod
    def _set_comparisons(self) -> None:
        """
        If we have identifier information, use error information from the
        config, and frequency information from `self`, to create our
        comparisons. Otherwise, call :meth:`_clear_comparisons`.
        """
        pass

    def _set_comparisons_inner(
        self, p_c: float, p_ep1: float, p_ep2np1: float
    ) -> None:
        """
        Args:
            p_c:
                Probability of a correct match between proband/candidate
            p_ep1:
                P(error such that partial match 1 occurs, but not a full
                match).
            p_ep2np1:
                P(error such that partial match 2 occurs, but not a full match
                or partial match 1).
        """
        if self.name:
            p_en = 1 - p_c - p_ep1 - p_ep2np1
            assert 0 <= p_en <= 1, "Bad error probabilities for a BasicName"

            p_n_pop_no_match = (
                1
                - self.pf_pop_name_freq
                - self.p_p1nf_metaphone_not_name
                - self.p_p2np1_f2c_not_metaphone_or_name
            )
            assert (
                0 <= p_n_pop_no_match <= 1
            ), "Bad population probabilities for a BasicName"

            self.comparison_full_match = DirectComparison(
                p_d_given_same_person=p_c,
                p_d_given_diff_person=self.pf_pop_name_freq,
            )
            self.comparison_partial_match = DirectComparison(
                p_d_given_same_person=p_ep1,
                p_d_given_diff_person=self.p_p1nf_metaphone_not_name,
            )
            self.comparison_partial_match_second = DirectComparison(
                p_d_given_same_person=p_ep2np1,
                p_d_given_diff_person=self.p_p2np1_f2c_not_metaphone_or_name,
            )
            self.comparison_no_match = DirectComparison(
                p_d_given_same_person=p_en,
                p_d_given_diff_person=p_n_pop_no_match,
            )
        else:
            self._clear_comparisons()

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
        if include_frequencies:
            d[self.KEY_P_F_NAME_FREQ] = self._round(
                self.pf_pop_name_freq, encrypt
            )
            d[self.KEY_P_P1NF_METAPHONE_NOT_NAME] = self._round(
                self.p_p1nf_metaphone_not_name, encrypt
            )
            d[self.KEY_P_P2NP1_F2C_NOT_METAPHONE_OR_NAME] = self._round(
                self.p_p2np1_f2c_not_metaphone_or_name, encrypt
            )
        return d

    def _set_from_json_dict_internal(self, d: Dict[str, Any], hashed: bool):
        """
        Internal function used by derived classes. Doesn't create the object,
        which is specialized to the derived class, but does the reading from
        the hashed dictionary and sets up the comparisons.
        """
        self.is_plaintext = not hashed

        self.name = getdictval(d, self.KEY_NAME, str)
        self.metaphone = getdictval(d, self.KEY_METAPHONE, str)
        self.f2c = getdictval(d, self.KEY_FIRST_TWO_CHAR, str)

        self.pf_pop_name_freq = getdictprob(d, self.KEY_P_F_NAME_FREQ)
        self.p_p1nf_metaphone_not_name = getdictprob(
            d, self.KEY_P_P1NF_METAPHONE_NOT_NAME
        )
        self.p_p2np1_f2c_not_metaphone_or_name = getdictprob(
            d, self.KEY_P_P2NP1_F2C_NOT_METAPHONE_OR_NAME
        )

        self._set_comparisons()

    def __bool__(self) -> bool:
        return bool(self.name)

    def ensure_has_freq_info_if_id_present(self) -> None:
        if self.name and (
            self.pf_pop_name_freq is None
            or self.p_p1nf_metaphone_not_name is None
            or self.p_p2np1_f2c_not_metaphone_or_name is None
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
        super().__init__(cfg, name=name, gender=gender)
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
            f = self.cfg.get_surname_freq_info(self.name, prestandardized=True)
            self.pf_pop_name_freq = f.p_name
            self.p_p1nf_metaphone_not_name = f.p_metaphone_not_name
            self.p_p2np1_f2c_not_metaphone_or_name = f.p_f2c_not_name_metaphone
        else:
            self._clear_frequencies()
        self._set_comparisons()

    def _set_comparisons(self) -> None:
        cfg = self.cfg
        g = self.gender
        self._set_comparisons_inner(
            p_c=cfg.p_c_surname[g],
            p_ep1=cfg.p_ep1_surname[g],
            p_ep2np1=cfg.p_ep2np1_surname[g],
        )

    # -------------------------------------------------------------------------
    # Unused methods from Identifier
    # -------------------------------------------------------------------------

    def plaintext_str_core(self) -> str:
        raise AssertionError(self.BAD_METHOD)

    @classmethod
    def from_plaintext_str(cls, cfg: MatchConfig, x: str) -> "SurnameFragment":
        raise AssertionError(cls.BAD_METHOD)


# =============================================================================
# Surname
# =============================================================================


class Surname(Identifier):
    """
    Represents a surname (family name).

    We don't inherit from BasicName, but from Identifier, because surnames
    need to deal with fragmen problems.

    Identifiably, we store the unmodified (unstandardized) name.

    We need to be able to match on parts. For example, "van Beethoven" should
    match "van Beethoven" but also "Beethoven". What frequency should we use
    for those parts? This has to be the frequency of the part (not the
    composite). For example, if someone is called "Mozart-Smith", then a match
    on "Mozart-Smith" or "Mozart" is less likely in the population, and thus
    more informative, than a match on "Smith". So, we need frequency
    information associated with each part. Thus, we break the use of
    the monolithic ``comparison_full_match`` etc., even though that is a fast
    method for other identifiers.
    """

    KEY_FRAGMENTS = "fragments"

    # -------------------------------------------------------------------------
    # Creation
    # -------------------------------------------------------------------------

    def __init__(
        self, cfg: MatchConfig, name: str = "", gender: str = ""
    ) -> None:
        super().__init__(cfg, is_plaintext=True, temporal=False)
        self.raw_surname = name

        # There is some duplication here for speed and to cope with the
        # difference between identifiable and hashed versions. We want a set
        # version for rapid overlap checking, and an ordered list to pick by
        # frequency sometimes.
        self.exact_set = set()  # type: Set[str]
        self.partial_set_metaphone = set()  # type: Set[str]
        self.partial_set_f2c = set()  # type: Set[str]
        self.fragments = []  # type: List[SurnameFragment]
        self.gender = ""  # changed in next step
        self.set_gender(gender)  # will reset frequencies/comparisons

    @classmethod
    def from_plaintext_str(cls, cfg: MatchConfig, x: str) -> "Surname":
        """
        Creation from CSV.
        """
        return Surname(cfg=cfg, name=x)

    @classmethod
    def from_dict(
        cls, cfg: MatchConfig, d: Dict[str, Any], hashed: bool
    ) -> "Surname":
        """
        Creation of a hashed name, ultimately from JSON.
        """
        n = Surname(cfg=cfg)
        n.is_plaintext = not hashed
        fragments_json_list = getdictval(d, cls.KEY_FRAGMENTS, list)
        n.fragments = [
            SurnameFragment.from_dict(cfg, fragment_dict, hashed)
            for fragment_dict in fragments_json_list
        ]
        n._reset_name_sets()
        return n

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
        return {self.KEY_FRAGMENTS: fragments}

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
        return bool(self.exact_set.intersection(other.exact_set))

    def partially_matches(self, other: "Surname") -> bool:
        return bool(
            self.partial_set_metaphone.intersection(
                other.partial_set_metaphone
            )
        )

    def partially_matches_second(self, other: "Surname") -> bool:
        return bool(self.partial_set_f2c.intersection(other.partial_set_f2c))

    def comparison(self, other: "Surname") -> Optional[Comparison]:
        """
        Specialized version for surname.
        """
        if not (self and other and self.overlaps(other)):
            # Infer no conclusions from absent information.
            return None

        overlap_exact = self.exact_set.intersection(other.exact_set)
        if overlap_exact:
            # Exact match. But possibly >1, e.g. "Mozart-Smith" has matched
            # "Mozart-Smith", "Mozart", and "Smith". Reasonable to pick the
            # most informative (rarest) version.
            candidates = [f for f in self.fragments if f.name in overlap_exact]
            candidates.sort(key=lambda f: f.exact_freq)
            # Sorted in ascending order, so first is best.
            return candidates[0].comparison_full_match

        overlap_partial_1 = self.partial_set_metaphone.intersection(
            other.partial_set_metaphone
        )
        if overlap_partial_1:
            # Similarly:
            candidates = [
                f for f in self.fragments if f.metaphone in overlap_partial_1
            ]
            candidates.sort(key=lambda f: f.p_p1nf_metaphone_not_name)
            return candidates[0].comparison_partial_match

        overlap_partial_2 = self.partial_set_f2c.intersection(
            other.partial_set_f2c
        )
        if overlap_partial_2:
            # Similarly:
            candidates = [
                f for f in self.fragments if f.f2c in overlap_partial_2
            ]
            candidates.sort(key=lambda f: f.f2c_freq)
            return candidates[0].comparison_partial_match_second

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
        self, cfg: MatchConfig, name: str = "", gender: str = ""
    ) -> None:
        super().__init__(cfg=cfg, name=name, gender=gender)
        # ... will call _reset_frequencies_identifiable()

    def _reset_frequencies_identifiable(self) -> None:
        if self.name:
            f = self.cfg.get_forename_freq_info(
                self.name, self.gender, prestandardized=True
            )
            self.pf_pop_name_freq = f.p_name
            self.p_p1nf_metaphone_not_name = f.p_metaphone_not_name
            self.p_p2np1_f2c_not_metaphone_or_name = f.p_f2c_not_name_metaphone
        else:
            self._clear_frequencies()
        self._set_comparisons()

    def _set_comparisons(self) -> None:
        cfg = self.cfg
        g = self.gender
        self._set_comparisons_inner(
            p_c=cfg.p_c_forename[g],
            p_ep1=cfg.p_ep1_forename[g],
            p_ep2np1=cfg.p_ep2np1_forename[g],
        )

    @classmethod
    def from_plaintext_str(cls, cfg: MatchConfig, x: str) -> "Forename":
        """
        Creation from CSV.
        """
        return Forename(cfg=cfg, name=x)

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
        self, cfg: MatchConfig, identifiers: Dict[str, str] = None
    ) -> None:
        super().__init__(cfg=cfg, is_plaintext=True, temporal=False)
        self.comparison_full_match = CertainComparison()

        self.identifiers = {}
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
        return {k: hash_fn(v) for k, v in self.identifiers}

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

    def comparison(self, other: "PerfectID") -> Optional[Comparison]:
        return (
            self.comparison_full_match if self.fully_matches(other) else None
        )


# =============================================================================
# Comparison of multiple potentially jumbled similar identifiers
# =============================================================================


def gen_best_comparisons(
    proband_identifiers: List[
        Union[IdentifierThreeState, IdentifierFourState]
    ],
    candidate_identifiers: List[
        Union[IdentifierThreeState, IdentifierFourState]
    ],
    no_match_comparison: Optional[DirectComparison] = None,
) -> Generator[DirectComparison, None, None]:
    """
    Generates comparisons for two sequences of identifiers (one from the
    proband, one from the candidate), being indifferent to their order. The
    method is:

    - Identifiers that are explicitly time-stamped cannot be compared with
      explicitly non-overlapping identifiers. (But un-time-stamped
      identifiers can be compared with anything.)

    - No identifier can be used for >1 comparison.

    - Full matches are preferred.

    - Partial matches are sought next.

    - If none are achieved, but there are identifiers, yield a single no-match
      comparison, as specified by the caller. If this is None, we don't bother
      to yield it.

    - Try to be quick.

    Used for postcodes.
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

    # A generator function here would be possible. But slightly less efficient.

    # Look for full matches:
    for c, candidate_id in enumerate(candidate_identifiers):
        for p, proband_id in enumerate(proband_identifiers):
            if p in proband_indexes_used:
                continue  # next proband
            if not candidate_id.overlaps(proband_id):
                non_overlapping_c_p.add((c, p))
                continue  # next proband
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

    if isinstance(candidate_identifiers[0], IdentifierFourState):
        # Try for any partial matches for identifiers not yet fully matched:
        for c, candidate_id in enumerate(
            candidate_identifiers
        ):  # type: int, IdentifierFourState
            if c in candidate_indexes_used:
                continue
            for p, proband_id in enumerate(
                proband_identifiers
            ):  # type: int, IdentifierFourState
                if p in proband_indexes_used:
                    continue
                if (c, p) in non_overlapping_c_p:
                    continue
                if candidate_id.partially_matches_second(proband_id):
                    found_something = True
                    yield proband_id.comparison_partial_match_second
                    candidate_indexes_used.add(c)
                    proband_indexes_used.add(p)
                    break  # next candidate

    # No joy?
    if not found_something and no_match_comparison:
        yield no_match_comparison
