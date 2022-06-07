#!/usr/bin/env python

r"""
crate_anon/linkage/person.py

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

**Person/people representations for fuzzy matching.**

"""


# =============================================================================
# Imports
# =============================================================================

from collections import defaultdict
import copy
import logging

import random
from typing import (
    Any,
    Dict,
    Generator,
    List,
    Optional,
    Set,
)

from cardinal_pythonlib.maths_py import round_sf

from crate_anon.linkage.helpers import (
    get_metaphone,
    get_postcode_sector,
    standardize_postcode,
)
from crate_anon.linkage.comparison import (
    bayes_compare,
    Comparison,
    DirectComparison,
)
from crate_anon.linkage.constants import (
    MINUS_INFINITY,
    VALID_GENDERS,
)
from crate_anon.linkage.helpers import (
    ISO_DATE_REGEX,
    mutate_name,
    mutate_postcode,
    POSTCODE_REGEX,
    standardize_name,
)
from crate_anon.linkage.identifiers import (
    FuzzyIdFreq,
    IdFreq,
    TemporalIdentifier,
)
from crate_anon.linkage.matchconfig import MatchConfig

log = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class DuplicateLocalIDError(Exception):
    pass


# =============================================================================
# BasePerson
# =============================================================================


class BasePerson:
    """
    Simple information about a person, without frequency calculations.
    Does not need a config.
    """

    ATTR_OTHER_INFO = "other_info"  # anything the user may want to attach

    _COMMON_ATTRS = [
        "local_id",  # person ID within the relevant database (proband/sample)
    ]
    PLAINTEXT_ATTRS = (
        _COMMON_ATTRS
        + [
            "first_name",
            "middle_names",
            "surname",
            "dob",
            "gender",
            "postcodes",
        ]
        + [ATTR_OTHER_INFO]
    )

    # For reading CSV:
    INT_ATTRS = []
    FLOAT_ATTRS = []
    SEMICOLON_DELIMIT = [
        "middle_names",
        "postcodes",
    ]
    TEMPORAL_IDENTIFIERS = [
        "postcodes",
    ]
    PLAINTEXT_CSV_FORMAT_HELP = (
        f"Header row present. Columns: {PLAINTEXT_ATTRS}. "
        f"The fields {sorted(TEMPORAL_IDENTIFIERS)} "
        f"are in TemporalIdentifier format. {TemporalIdentifier.FORMAT_HELP} "
        f"Semicolon-separated values are allowed within "
        f"{sorted(SEMICOLON_DELIMIT)}."
    )

    # -------------------------------------------------------------------------
    # Creation
    # -------------------------------------------------------------------------

    def __init__(
        self,
        local_id: str = "",
        other_info: str = "",
        first_name: str = "",
        middle_names: List[str] = None,
        surname: str = "",
        dob: str = "",
        gender: str = "",
        postcodes: List[TemporalIdentifier] = None,
        standardize: bool = True,
    ) -> None:
        """
        Args:
            local_id:
                Identifier within this person's local database (e.g. proband ID
                or sample ID). Typically a research pseudonym, not itself
                identifying.
            other_info:
                String containing any other attributes the user may wish to
                remember (e.g. in JSON). Only used for validation research
                (e.g. ensuring linkage is not biased by ethnicity).

            first_name:
                (PLAINTEXT.) The person's first name.
            middle_names:
                (PLAINTEXT.) Any middle names.
            surname:
                (PLAINTEXT.) The person's surname.
            dob:
                (PLAINTEXT.) The date of birth in ISO-8061 "YYYY-MM-DD" string
                format.
            gender:
                (PLAINTEXT.) The gender: 'M', 'F', 'X', or ''.
            postcodes:
                (PLAINTEXT.) Any UK postcodes for this person.

            standardize:
                Standardize names/postcodes etc. internally. Only turn this
                off for demonstration purposes.
        """
        self.local_id = str(local_id) if local_id is not None else None
        assert self.local_id, f"Bad local_id: {local_id!r}"

        self.other_info = other_info or ""
        assert isinstance(
            self.other_info, str
        ), f"Bad other_info: {self.other_info!r}"

        self.first_name = first_name or ""
        assert isinstance(
            self.first_name, str
        ), f"Bad first_name: {self.first_name!r}"

        self.middle_names = middle_names or []
        assert isinstance(
            self.middle_names, list
        ), f"Bad middle_names: {self.middle_names!r}"
        for m in self.middle_names:
            assert isinstance(m, str), f"Bad middle name: {m!r}"

        self.surname = surname or ""
        assert isinstance(self.surname, str), f"Bad surname: {self.surname!r}"

        self.dob = dob or ""
        assert isinstance(self.dob, str), f"Bad date: {dob!r}"
        if self.dob:
            assert ISO_DATE_REGEX.match(dob), f"Bad date: {dob!r}"

        self.gender = gender or ""
        assert self.gender in VALID_GENDERS, f"Bad gender: {gender!r}"

        self.postcodes = postcodes or []
        for p in self.postcodes:
            assert isinstance(p, TemporalIdentifier) and POSTCODE_REGEX.match(
                p.identifier
            ), f"Bad postcode: {p.identifier!r}"

        if standardize:
            self.first_name = standardize_name(self.first_name)
            self.middle_names = [
                standardize_name(x) for x in self.middle_names if x
            ]
            self.surname = standardize_name(self.surname)
            for p in self.postcodes:
                if p.identifier:
                    p.identifier = standardize_postcode(p.identifier)

    @classmethod
    def _from_csv(
        cls,
        cfg: MatchConfig,
        rowdict: Dict[str, str],
        attrs: List[str],
        is_hashed: bool,
    ) -> "Person":
        """
        Returns a :class:`Person` object from a CSV row.

        Args:
            cfg: a configuration object
            rowdict: a CSV row, read via :class:`csv.DictReader`.
        """
        kwargs = {}  # type: Dict[str, Any]
        for attr in attrs:
            v = rowdict[attr]
            if attr in cls.SEMICOLON_DELIMIT:
                v = [x.strip() for x in v.split(";") if x]
                if attr in cls.INT_ATTRS:
                    v = [int(x) for x in v]
                elif attr in cls.FLOAT_ATTRS:
                    v = [float(x) for x in v]
                elif attr in cls.TEMPORAL_IDENTIFIERS:
                    v = [TemporalIdentifier.from_str(x) for x in v]
            elif attr in cls.INT_ATTRS:
                v = int(v) if v else None
            elif attr in cls.FLOAT_ATTRS:
                v = float(v) if v else None
            elif attr in cls.TEMPORAL_IDENTIFIERS:
                v = TemporalIdentifier.from_str(v) if v else None
            kwargs[attr] = v
        return Person(cfg=cfg, is_hashed=is_hashed, **kwargs)

    @classmethod
    def from_plaintext_csv(
        cls, cfg: MatchConfig, rowdict: Dict[str, str]
    ) -> "Person":
        """
        Returns a :class:`Person` object from a plaintext CSV row.

        Args:
            cfg: a configuration object
            rowdict: a CSV row, read via :class:`csv.DictReader`.
        """
        return cls._from_csv(
            cfg, rowdict, cls.PLAINTEXT_ATTRS, is_hashed=False
        )

    # -------------------------------------------------------------------------
    # Representation, reading, writing
    # -------------------------------------------------------------------------

    def __str__(self) -> str:
        names = " ".join(
            [self.first_name] + self.middle_names + [self.surname]
        )
        postcodes = " - ".join(str(x) for x in self.postcodes)
        details = ", ".join(
            [
                f"local_id={self.local_id}",
                f"name={names}",
                f"gender={self.gender}",
                f"dob={self.dob}",
                f"postcode={postcodes}",
                f"other={self.other_info!r}",
            ]
        )
        return f"Person with {details}"

    def _csv_dict(self, attrs: List[str]) -> Dict[str, Any]:
        """
        Returns a dictionary suitable for :class:`csv.DictWriter`.
        """
        d = {}  # type: Dict[str, Any]
        for k in attrs:
            a = getattr(self, k)
            if k in self.SEMICOLON_DELIMIT:
                v = ";".join(str(x) for x in a)
            else:
                v = a
            d[k] = v
        return d

    def plaintext_csv_columns(self) -> List[str]:
        """
        CSV column names -- including user-specified "other" information.
        """
        return self.PLAINTEXT_ATTRS

    def plaintext_csv_dict(self) -> Dict[str, Any]:
        """
        Returns a dictionary suitable for :class:`csv.DictWriter`.
        """
        return self._csv_dict(self.PLAINTEXT_ATTRS)


# =============================================================================
# Person
# =============================================================================


class Person(BasePerson):
    """
    Represents a person. The information may be incomplete or slightly wrong.
    Includes frequency information and requires a config.
    """

    HASHED_ATTRS = (
        BasePerson._COMMON_ATTRS
        + [
            # not: "is_hashed",
            "hashed_first_name",
            "first_name_frequency",
            "hashed_first_name_metaphone",
            "first_name_metaphone_frequency",
            "hashed_middle_names",
            "middle_name_frequencies",
            "hashed_middle_name_metaphones",
            "middle_name_metaphone_frequencies",
            "hashed_surname",
            "surname_frequency",
            "hashed_surname_metaphone",
            "surname_metaphone_frequency",
            "hashed_dob",
            "hashed_gender",
            "gender_frequency",
            "hashed_postcode_units",
            "postcode_unit_frequencies",
            "hashed_postcode_sectors",
            "postcode_sector_frequencies",
        ]
        + [BasePerson.ATTR_OTHER_INFO]
    )
    HASHED_FREQUENCY_ATTRS = [
        "first_name_frequency",
        "first_name_metaphone_frequency",
        "middle_name_frequencies",
        "middle_name_metaphone_frequencies",
        "surname_frequency",
        "surname_metaphone_frequency",
        "gender_frequency",
        "postcode_unit_frequencies",
        "postcode_sector_frequencies",
    ]
    FLOAT_ATTRS = BasePerson.FLOAT_ATTRS + [
        "first_name_frequency",
        "first_name_metaphone_frequency",
        "middle_name_frequencies",
        "middle_name_metaphone_frequencies",
        "surname_frequency",
        "surname_metaphone_frequency",
        "gender_frequency",
        "postcode_unit_frequencies",
        "postcode_sector_frequencies",
    ]
    SEMICOLON_DELIMIT = BasePerson.SEMICOLON_DELIMIT + [
        # hashed
        "hashed_middle_names",
        "middle_name_frequencies",
        "hashed_middle_name_metaphones",
        "middle_name_metaphone_frequencies",
        "hashed_postcode_units",
        "postcode_unit_frequencies",
        "hashed_postcode_sectors",
        "postcode_sector_frequencies",
    ]
    TEMPORAL_IDENTIFIERS = BasePerson.TEMPORAL_IDENTIFIERS + [
        "hashed_postcode_units",
        "hashed_postcode_sectors",
    ]
    HASHED_CSV_FORMAT_HELP = (
        f"Header row present. Columns: {HASHED_ATTRS}. "
        f"The fields "
        f"{sorted(list(set(TEMPORAL_IDENTIFIERS).intersection(HASHED_ATTRS)))} "  # noqa
        f"are in TemporalIdentifier format. {TemporalIdentifier.FORMAT_HELP} "
        f"Semicolon-separated values are allowed within "
        f"{sorted(list(set(SEMICOLON_DELIMIT).intersection(HASHED_ATTRS)))}."
    )

    # -------------------------------------------------------------------------
    # __init__, __repr__, copy
    # -------------------------------------------------------------------------

    def __init__(
        self,
        cfg: MatchConfig,
        # State
        is_hashed: bool = False,
        # Reference codes
        local_id: str = "",
        other_info: str = "",
        # Plaintext
        first_name: str = "",
        middle_names: List[str] = None,
        surname: str = "",
        dob: str = "",
        gender: str = "",
        postcodes: List[TemporalIdentifier] = None,
        # Hashed
        hashed_first_name: str = "",
        first_name_frequency: float = None,
        hashed_first_name_metaphone: str = "",
        first_name_metaphone_frequency: float = None,
        hashed_middle_names: List[str] = None,
        middle_name_frequencies: List[float] = None,
        hashed_middle_name_metaphones: List[str] = None,
        middle_name_metaphone_frequencies: List[float] = None,
        hashed_surname: str = "",
        surname_frequency: float = None,
        hashed_surname_metaphone: str = "",
        surname_metaphone_frequency: float = None,
        hashed_dob: str = "",
        hashed_gender: str = "",
        gender_frequency: float = None,
        hashed_postcode_units: List[TemporalIdentifier] = None,
        postcode_unit_frequencies: List[float] = None,
        hashed_postcode_sectors: List[TemporalIdentifier] = None,
        postcode_sector_frequencies: List[float] = None,
    ) -> None:
        """
        Args:
            cfg:
                Configuration object. It is more efficient to use this while
                creating a Person object; it saves lookup time later.
            is_hashed:
                Is this a hashed representation? If so, matching works
                differently.

            local_id:
                Identifier within this person's local database (e.g. proband ID
                or sample ID). Typically a research pseudonym, not itself
                identifying.
            other_info:
                String containing any other attributes the user may wish to
                remember (e.g. in JSON). Only used for validation research
                (e.g. ensuring linkage is not biased by ethnicity).

            first_name:
                The person's first name.
            middle_names:
                Any middle names.
            surname:
                The person's surname.
            dob:
                The date of birth in ISO-8061 "YYYY-MM-DD" string format.
            gender:
                The gender: 'M', 'F', 'X', or ''.
            postcodes:
                Any UK postcodes for this person.

            hashed_first_name:
                The first name, irreversibly hashed.
            first_name_frequency:
                The first name's frequency in the population, range [0, 1].
            hashed_first_name_metaphone:
                The first name's metaphone ("sounds like"), irreversibly
                hashed.
            first_name_metaphone_frequency:
                The first name metaphone's frequency in the population.

            hashed_middle_names:
                Any middle names, hashed.
            middle_name_frequencies:
                Corresponding middle name frequencies.
            hashed_middle_name_metaphones:
                Any middle names' metaphones, hashed.
            middle_name_metaphone_frequencies:
                Any middle name metaphone frequencies.

            hashed_surname:
                The surname, hashed.
            surname_frequency:
                The surname's frequency.
            hashed_surname_metaphone:
                The surname's metaphone.
            surname_metaphone_frequency:
                The surname metaphone's frequency.

            hashed_dob:
                The DOB, hashed.

            hashed_gender:
                The gender, hashed.
            gender_frequency:
                The gender's frequency.

            hashed_postcode_units:
                Full postcodes (postcode units), hashed.
            postcode_unit_frequencies:
                Frequencies of each postcode unit.
            hashed_postcode_sectors:
                Postcode sectors, hashed.
            postcode_sector_frequencies:
                Frequencies of each postcode sector.
        """
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Superclass init
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        super().__init__(
            local_id=local_id,
            other_info=other_info,
            first_name=first_name,
            middle_names=middle_names,
            surname=surname,
            dob=dob,
            gender=gender,
            postcodes=postcodes,
        )

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Store info
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        self.cfg = cfg
        self.is_hashed = is_hashed

        self.hashed_first_name = hashed_first_name
        self.first_name_frequency = first_name_frequency
        self.hashed_first_name_metaphone = hashed_first_name_metaphone
        self.first_name_metaphone_frequency = first_name_metaphone_frequency

        self.hashed_middle_names = hashed_middle_names or []
        n_hashed_middle_names = len(self.hashed_middle_names)
        self.middle_name_frequencies = (
            middle_name_frequencies or [None] * n_hashed_middle_names
        )
        self.hashed_middle_name_metaphones = (
            hashed_middle_name_metaphones or []
        )
        self.middle_name_metaphone_frequencies = (
            middle_name_metaphone_frequencies or [None] * n_hashed_middle_names
        )

        self.hashed_surname = hashed_surname
        self.surname_frequency = surname_frequency
        self.hashed_surname_metaphone = hashed_surname_metaphone
        self.surname_metaphone_frequency = surname_metaphone_frequency

        self.hashed_dob = hashed_dob

        self.hashed_gender = hashed_gender
        self.gender_frequency = gender_frequency

        self.hashed_postcode_units = hashed_postcode_units or []
        n_hashed_postcodes = len(self.hashed_postcode_units)
        self.postcode_unit_frequencies = (
            postcode_unit_frequencies or [None] * n_hashed_postcodes
        )
        self.hashed_postcode_sectors = hashed_postcode_sectors or []
        self.postcode_sector_frequencies = (
            postcode_sector_frequencies or [None] * n_hashed_postcodes
        )

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Validation
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        if is_hashed:
            # hashed
            assert (
                not self.first_name
                and not self.middle_names
                and not self.surname
                and not self.dob
                and not self.postcodes
            ), "Don't supply plaintext information for a hashed Person"
            # Note that frequency information can be absent for candidates from
            # the sample; we check it's present for probands via
            # assert_valid_as_proband().
            if self.hashed_first_name:
                assert self.hashed_first_name_metaphone
            if self.hashed_middle_names:
                assert (
                    len(self.middle_name_frequencies) == n_hashed_middle_names
                    and len(self.hashed_middle_name_metaphones)  # noqa
                    == n_hashed_middle_names
                    and len(self.middle_name_metaphone_frequencies)  # noqa
                    == n_hashed_middle_names  # noqa
                )
            if self.hashed_surname:
                assert self.hashed_surname_metaphone
            if self.hashed_postcode_units:
                assert (
                    len(self.postcode_unit_frequencies) == n_hashed_postcodes
                    and len(self.hashed_postcode_sectors)  # noqa
                    == n_hashed_postcodes
                    and len(self.postcode_sector_frequencies)
                    == n_hashed_postcodes
                )
        else:
            # Plain text
            assert (
                not self.hashed_first_name
                and self.first_name_frequency is None
                and not self.hashed_first_name_metaphone
                and self.first_name_metaphone_frequency is None
                and not self.hashed_middle_names
                and not self.middle_name_frequencies
                and not self.hashed_middle_name_metaphones
                and not self.middle_name_metaphone_frequencies
                and not self.hashed_surname
                and self.surname_frequency is None
                and not self.hashed_surname_metaphone
                and self.surname_metaphone_frequency is None
                and not self.hashed_dob
                and not self.hashed_gender
                and self.gender_frequency is None
                and not self.hashed_postcode_units
                and not self.postcode_unit_frequencies
                and not self.hashed_postcode_sectors
                and not self.postcode_sector_frequencies
            ), "Don't supply hashed information for a plaintext Person"

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Precalculate things, for speed
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        self.middle_names_info = []  # type: List[FuzzyIdFreq]
        self.postcodes_info = []  # type: List[FuzzyIdFreq]

        if is_hashed:  # more efficient as an outer test
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            # Hashed info
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

            self.first_name_info = FuzzyIdFreq(
                comparison_name="first_name",
                exact_identifier=self.hashed_first_name,
                exact_identifier_frequency=self.first_name_frequency,
                fuzzy_identifier=self.hashed_first_name_metaphone,
                fuzzy_identifier_frequency=self.first_name_metaphone_frequency,
                p_error=cfg.p_minor_forename_error,
            )
            for i in range(len(self.hashed_middle_names)):
                n = i + 1
                self.middle_names_info.append(
                    FuzzyIdFreq(
                        comparison_name=f"middle_name_{n}",
                        exact_identifier=self.hashed_middle_names[i],
                        exact_identifier_frequency=self.middle_name_frequencies[  # noqa: E501
                            i
                        ],
                        fuzzy_identifier=self.hashed_middle_name_metaphones[i],
                        fuzzy_identifier_frequency=self.middle_name_metaphone_frequencies[  # noqa: E501
                            i
                        ],  # noqa
                        p_error=cfg.p_minor_forename_error,
                    )
                )
            self.surname_info = FuzzyIdFreq(
                comparison_name="surname",
                exact_identifier=self.hashed_surname,
                exact_identifier_frequency=self.surname_frequency,
                fuzzy_identifier=self.hashed_surname_metaphone,
                fuzzy_identifier_frequency=self.surname_metaphone_frequency,
                p_error=cfg.p_minor_surname_error,
            )
            self.dob_info = IdFreq(
                comparison_name="DOB",
                identifier=self.hashed_dob,
                frequency=cfg.p_two_people_share_dob,
                p_error=0,  # no typos allowed in dates of birth
            )
            self.gender_info = IdFreq(
                comparison_name="gender",
                identifier=self.hashed_gender,
                frequency=self.gender_frequency,
                p_error=cfg.p_gender_error,
            )
            for i in range(len(self.hashed_postcode_units)):
                unit_hashed = self.hashed_postcode_units[i].identifier
                sector_hashed = self.hashed_postcode_sectors[i].identifier
                unit_freq = self.postcode_unit_frequencies[i]
                sector_freq = self.postcode_sector_frequencies[i]
                self.postcodes_info.append(
                    FuzzyIdFreq(
                        comparison_name="postcode",
                        exact_identifier=unit_hashed,
                        exact_identifier_frequency=unit_freq,
                        fuzzy_identifier=sector_hashed,
                        fuzzy_identifier_frequency=sector_freq,
                        p_error=cfg.p_minor_postcode_error,
                    )
                )

        else:
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            # Plaintext info
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

            first_name_metaphone = get_metaphone(self.first_name)
            self.first_name_info = FuzzyIdFreq(
                comparison_name="first_name",
                exact_identifier=self.first_name,
                exact_identifier_frequency=cfg.forename_freq(
                    self.first_name, self.gender, prestandardized=True
                ),
                fuzzy_identifier=first_name_metaphone,
                fuzzy_identifier_frequency=cfg.forename_metaphone_freq(
                    first_name_metaphone, self.gender
                ),
                p_error=cfg.p_minor_forename_error,
            )
            for i in range(len(self.middle_names)):
                n = i + 1
                middle_name = self.middle_names[i]
                middle_name_metaphone = get_metaphone(middle_name)
                middle_name_freq = cfg.forename_freq(
                    middle_name, self.gender, prestandardized=True
                )
                middle_name_metaphone_freq = cfg.forename_metaphone_freq(
                    middle_name_metaphone, self.gender
                )
                self.middle_names_info.append(
                    FuzzyIdFreq(
                        comparison_name=f"middle_name_{n}",
                        exact_identifier=middle_name,
                        exact_identifier_frequency=middle_name_freq,
                        fuzzy_identifier=middle_name_metaphone,
                        fuzzy_identifier_frequency=middle_name_metaphone_freq,
                        p_error=cfg.p_minor_forename_error,
                    )
                )
            surname_metaphone = get_metaphone(self.surname)
            self.surname_info = FuzzyIdFreq(
                comparison_name="surname",
                exact_identifier=self.surname,
                exact_identifier_frequency=cfg.surname_freq(
                    self.surname, prestandardized=True
                ),
                fuzzy_identifier=surname_metaphone,
                fuzzy_identifier_frequency=cfg.surname_metaphone_freq(
                    surname_metaphone
                ),
                p_error=cfg.p_minor_surname_error,
            )
            self.dob_info = IdFreq(
                comparison_name="DOB",
                identifier=self.dob,
                frequency=cfg.p_two_people_share_dob,
                p_error=0,  # no typos allowed in dates of birth
            )
            self.gender_info = IdFreq(
                comparison_name="gender",
                identifier=self.gender,
                frequency=cfg.gender_freq(self.gender),
                p_error=cfg.p_gender_error,
            )
            for i in range(len(self.postcodes)):
                unit = self.postcodes[i].identifier
                sector = get_postcode_sector(unit)
                unit_freq, sector_freq = cfg.postcode_unit_sector_freq(
                    unit, prestandardized=True
                )
                try:
                    self.postcodes_info.append(
                        FuzzyIdFreq(
                            comparison_name="postcode",
                            exact_identifier=unit,
                            exact_identifier_frequency=unit_freq,
                            fuzzy_identifier=sector,
                            fuzzy_identifier_frequency=sector_freq,
                            p_error=cfg.p_minor_postcode_error,
                        )
                    )
                except AssertionError:
                    log.critical(
                        f"Frequency error with postcode unit {unit}, "
                        f"postcode sector {sector}"
                    )
                    raise

    def copy(self) -> "Person":
        """
        Returns a copy of this object.

        - :func:`copy.deepcopy` is incredibly slow, yet :func:`copy.copy` isn't
          enough when we want to mutate this object.
        - So we do it quasi-manually. It's just lists that we want to treat as
          special.
        """
        # return copy.deepcopy(self)
        copy_attrs = (
            self.HASHED_ATTRS if self.is_hashed else self.PLAINTEXT_ATTRS
        )
        kwargs = {}  # type: Dict[str, Any]
        for attrname in copy_attrs:
            value = getattr(self, attrname)
            if isinstance(value, list):  # special handling here
                value = [copy.copy(x) for x in value]
            kwargs[attrname] = value
        return Person(cfg=self.cfg, is_hashed=self.is_hashed, **kwargs)

    @classmethod
    def from_hashed_csv(
        cls, cfg: MatchConfig, rowdict: Dict[str, str]
    ) -> "Person":
        """
        Returns a :class:`Person` object from a hashed CSV row.

        Args:
            cfg: a configuration object
            rowdict: a CSV row, read via :class:`csv.DictReader`.
        """
        return cls._from_csv(cfg, rowdict, cls.HASHED_ATTRS, is_hashed=True)

    # -------------------------------------------------------------------------
    # String and CSV formats
    # -------------------------------------------------------------------------

    def __repr__(self) -> str:
        """
        Returns a string representation that can be used for reconstruction.
        """
        attrs = ["is_hashed"]
        attrs += self.HASHED_ATTRS if self.is_hashed else self.PLAINTEXT_ATTRS
        attrlist = [f"{a}={getattr(self, a)!r}" for a in attrs]
        return f"Person({', '.join(attrlist)})"

    def __str__(self) -> str:
        if self.is_hashed:
            return f"Hashed person with local_id={self.local_id!r}"
        else:
            return super().__str__()

    def hashed_csv_dict(
        self,
        without_frequencies: bool = False,
        include_other_info: bool = False,
    ) -> Dict[str, Any]:
        """
        Returns a dictionary suitable for :class:`csv.DictWriter`.

        Args:
            without_frequencies:
                Do not include frequency information. This makes the resulting
                file suitable for use as a sample, but not as a proband file.
            include_other_info:
                include the (potentially identifying) ``other_info`` data?
                Usually ``False``; may be ``True`` for validation.
        """
        assert self.is_hashed
        attrs = self.HASHED_ATTRS.copy()
        if without_frequencies:
            for a in self.HASHED_FREQUENCY_ATTRS:
                attrs.remove(a)
        if not include_other_info:
            attrs.remove(BasePerson.ATTR_OTHER_INFO)
        return self._csv_dict(attrs)

    # -------------------------------------------------------------------------
    # Created hashed version
    # -------------------------------------------------------------------------

    def hashed(self) -> "Person":
        """
        Returns a :class:`Person` object but with all the elements hashed (if
        they are not blank).
        """
        # Speeded up 2020-04-24, based on profiling.

        # Functions that we may call several times:
        cfg = self.cfg
        _hash = cfg.hasher.hash  # main hashing function
        _forename_freq = cfg.forename_freq
        _forename_metaphone_freq = cfg.forename_metaphone_freq
        _pcode_frequencies = cfg.postcode_unit_sector_freq
        _sf = cfg.rounding_sf

        def fr(f: float) -> float:
            """
            Rounds frequencies to a certain number of significant figures.
            (Don't supply exact floating-point numbers for frequencies; may be
            more identifying. Don't use decimal places; we have to deal with
            some small numbers.)
            """
            return round_sf(f, _sf)

        first_name = self.first_name
        gender = self.gender
        if first_name:
            hashed_first_name = _hash(first_name)
            first_name_frequency = fr(
                _forename_freq(first_name, gender, prestandardized=True)
            )
            fn_metaphone = get_metaphone(first_name)
            hashed_first_name_metaphone = _hash(fn_metaphone)
            first_name_metaphone_frequency = fr(
                _forename_metaphone_freq(fn_metaphone, gender)
            )
        else:
            hashed_first_name = ""
            first_name_frequency = None
            hashed_first_name_metaphone = ""
            first_name_metaphone_frequency = None

        middle_names = self.middle_names
        hashed_middle_names = []
        middle_name_frequencies = []
        hashed_middle_name_metaphones = []
        middle_name_metaphone_frequencies = []
        for i, p in enumerate(middle_names):
            if p:
                mn_metaphone = get_metaphone(p)
                hashed_middle_names.append(_hash(p))
                middle_name_frequencies.append(
                    fr(_forename_freq(p, gender, prestandardized=True))
                )
                hashed_middle_name_metaphones.append(_hash(mn_metaphone))
                middle_name_metaphone_frequencies.append(
                    fr(_forename_metaphone_freq(mn_metaphone, gender))
                )

        surname = self.surname
        if surname:
            hashed_surname = _hash(surname)
            surname_frequency = fr(
                cfg.surname_freq(surname, prestandardized=True)
            )
            sn_metaphone = get_metaphone(surname)
            hashed_surname_metaphone = _hash(sn_metaphone)
            surname_metaphone_frequency = fr(
                cfg.surname_metaphone_freq(sn_metaphone)
            )
        else:
            hashed_surname = ""
            surname_frequency = None
            hashed_surname_metaphone = ""
            surname_metaphone_frequency = None

        hashed_dob = _hash(self.dob) if self.dob else ""

        if gender:
            hashed_gender = _hash(gender)
            gender_frequency = fr(cfg.gender_freq(gender))
        else:
            hashed_gender = ""
            gender_frequency = None

        postcodes = self.postcodes
        hashed_postcode_units = []
        postcode_unit_frequencies = []
        hashed_postcode_sectors = []
        postcode_sector_frequencies = []
        for p in postcodes:
            if p:
                unit = p.identifier
                sector = get_postcode_sector(unit)
                unit_freq, sector_freq = _pcode_frequencies(
                    unit, prestandardized=True
                )
                hashed_postcode_units.append(
                    p.with_new_identifier(_hash(unit))
                )
                postcode_unit_frequencies.append(fr(unit_freq))
                hashed_postcode_sectors.append(
                    p.with_new_identifier(_hash(sector))
                )
                postcode_sector_frequencies.append(fr(sector_freq))

        return Person(
            cfg=cfg,
            is_hashed=True,
            local_id=(
                cfg.local_id_hasher.hash(self.local_id)
                if cfg.local_id_hasher
                else self.local_id
            ),
            other_info=self.other_info,
            hashed_first_name=hashed_first_name,
            first_name_frequency=first_name_frequency,
            hashed_first_name_metaphone=hashed_first_name_metaphone,
            first_name_metaphone_frequency=first_name_metaphone_frequency,
            hashed_middle_names=hashed_middle_names,
            middle_name_frequencies=middle_name_frequencies,
            hashed_middle_name_metaphones=hashed_middle_name_metaphones,
            middle_name_metaphone_frequencies=middle_name_metaphone_frequencies,  # noqa
            hashed_surname=hashed_surname,
            surname_frequency=surname_frequency,
            hashed_surname_metaphone=hashed_surname_metaphone,
            surname_metaphone_frequency=surname_metaphone_frequency,
            hashed_dob=hashed_dob,
            hashed_gender=hashed_gender,
            gender_frequency=gender_frequency,
            hashed_postcode_units=hashed_postcode_units,
            postcode_unit_frequencies=postcode_unit_frequencies,
            hashed_postcode_sectors=hashed_postcode_sectors,
            postcode_sector_frequencies=postcode_sector_frequencies,
        )

    # -------------------------------------------------------------------------
    # Main comparison function
    # -------------------------------------------------------------------------

    def log_odds_same(self, proband: "Person") -> float:
        """
        Returns the log odds that ``self`` and ``other`` are the same person.

        Args:
            proband: another :class:`Person` object

        Returns:
            float: the log odds they're the same person
        """
        return bayes_compare(
            prior_log_odds=self.cfg.baseline_log_odds_same_person,
            comparisons=self._gen_comparisons(proband),
        )

    # -------------------------------------------------------------------------
    # Comparison helper functions
    # -------------------------------------------------------------------------

    def _gen_comparisons(
        self, proband: "Person"
    ) -> Generator[Optional[Comparison], None, None]:
        """
        Generates all relevant comparisons.

        Try to do the comparisons first that are most likely to eliminate a
        person.

        Args:
            proband: another :class:`Person` object

        **Note**

        Where these functions are symmetric, they refer to ``self`` and
        ``other``. In the few cases that are directional, they refer to
        ``cand_*`` (candidate, ``self``) and ``proband``.
        """
        # The shortlisting process will already have ensured a DOB match.
        # Therefore, while we need to process DOB to get the probabilities
        # right for good candidates, we can do other things first to eliminate
        # bad ones quicker.
        yield self._comparison_surname(proband)  # might eliminate
        yield self._comparison_firstname(proband)  # might eliminate
        yield self._comparison_gender(proband)  # won't absolutely eliminate
        yield self._comparison_dob(proband)  # see above
        for c in self._comparisons_middle_names(proband):  # slowest
            yield c
        for c in self._comparisons_postcodes(proband):  # doesn't eliminate
            yield c

    def _comparison_dob(self, other: "Person") -> Optional[Comparison]:
        """
        Returns a comparison for date of birth.

        There is no special treatment of 29 Feb (since this DOB is
        approximately 4 times less common than other birthdays, in principle it
        does merit special treatment, but we ignore that).
        """
        return self.dob_info.comparison(other.dob_info)

    def _comparison_gender(self, proband: "Person") -> Optional[Comparison]:
        """
        Returns a comparison for gender (sex).

        We use values "F" (female), "M" (male), "X" (other), "" (unknown).
        """
        return self.gender_info.comparison(proband.gender_info)

    def _comparison_surname(self, other: "Person") -> Optional[Comparison]:
        """
        Returns a comparison for surname.
        """
        return self.surname_info.comparison(other.surname_info)

    def _comparison_firstname(self, other: "Person") -> Optional[Comparison]:
        """
        Returns a comparison for first name.
        """
        return self.first_name_info.comparison(other.first_name_info)

    def _comparisons_middle_names(
        self, proband: "Person"
    ) -> Generator[Comparison, None, None]:
        """
        Generates comparisons for middle names.
        """
        cfg = self.cfg
        n_candidate_middle_names = len(self.middle_names_info)
        n_proband_middle_names = len(proband.middle_names_info)
        max_n_middle_names = max(
            n_candidate_middle_names, n_proband_middle_names
        )  # noqa
        min_n_middle_names = min(
            n_candidate_middle_names, n_proband_middle_names
        )  # noqa

        for i in range(max_n_middle_names):
            if i < min_n_middle_names:
                # -------------------------------------------------------------
                # Name present in both. Exact and partial matches
                # -------------------------------------------------------------
                yield self.middle_names_info[i].comparison(
                    proband.middle_names_info[i]
                )
            else:
                # -------------------------------------------------------------
                # Name present in one but not the other. Surplus name.
                # -------------------------------------------------------------
                n = i + 1  # from zero-based to one-based
                if n > n_candidate_middle_names:
                    # ``self`` is the candidate, from the sample.
                    p_d_given_same_person = cfg.p_sample_middle_name_missing
                else:
                    # Otherwise, n > n_proband_middle_names.
                    p_d_given_same_person = cfg.p_proband_middle_name_missing
                yield DirectComparison(
                    name="middle_name_surplus",
                    p_d_given_same_person=p_d_given_same_person,
                    p_d_given_diff_person=cfg.p_middle_name_present(n),
                )

    def _comparisons_postcodes(
        self, other: "Person"
    ) -> Generator[Comparison, None, None]:
        """
        Generates comparisons for postcodes.
        """
        other_postcodes_info = other.postcodes_info
        # We prefer full matches to partial matches, and we don't allow the
        # same postcode to be used for both.
        indexes_of_full_matches = set()  # type: Set[int]
        try:
            for i, self_pi in enumerate(self.postcodes_info):
                for other_pi in other_postcodes_info:
                    if self_pi.fully_matches(other_pi):
                        yield self_pi.comparison(other_pi)
                        indexes_of_full_matches.add(i)
                        break
            # Try for any partial matches for postcodes not yet fully matched:
            for i, self_pi in enumerate(self.postcodes_info):
                if i in indexes_of_full_matches:
                    continue
                for other_pi in other_postcodes_info:
                    if self_pi.partially_matches(other_pi):
                        yield self_pi.comparison(other_pi)
                        break
        except AssertionError:
            log.critical(
                f"Postcode comparison error: "
                f"self.postcodes_info = {self.postcodes_info}; "
                f"other.postcodes_info = {other.postcodes_info}"
            )
            raise

    # -------------------------------------------------------------------------
    # Info functions
    # -------------------------------------------------------------------------

    def has_first_name(self) -> bool:
        """
        Does this person have a first name?
        """
        if self.is_hashed:
            return bool(self.hashed_first_name)
        else:
            return bool(self.first_name)

    def n_middle_names(self) -> int:
        """
        How many names does this person have?
        """
        if self.is_hashed:
            return len(self.hashed_middle_names)
        else:
            return len(self.middle_names)

    def has_dob(self) -> bool:
        """
        Do we have a DOB?
        """
        return bool(self.hashed_dob) if self.is_hashed else bool(self.dob)

    def n_postcodes(self) -> int:
        """
        How many postcodes does this person have?
        """
        if self.is_hashed:
            return len(self.hashed_postcode_units)
        else:
            return len(self.postcodes)

    def assert_valid_as_proband(self) -> None:
        """
        Ensures this person has sufficient information to act as a proband, or
        raises :exc:`AssertionError`.
        """
        assert self.has_dob(), "Proband: missing DOB"
        self.first_name_info.assert_has_freq_info_if_id_present()
        for mni in self.middle_names_info:
            mni.assert_has_freq_info_if_id_present()
        self.surname_info.assert_has_freq_info_if_id_present()
        self.dob_info.assert_has_freq_info_if_id_present()
        self.gender_info.assert_has_freq_info_if_id_present()
        for pi in self.postcodes_info:
            pi.assert_has_freq_info_if_id_present()

    def assert_valid_as_candidate(self) -> None:
        """
        Ensures this person has sufficient information to act as a candidate,
        or raises :exc:`AssertionError`.
        """
        assert self.has_dob(), "Candidate: missing DOB"

    # -------------------------------------------------------------------------
    # Debugging functions to mutate this object
    # -------------------------------------------------------------------------

    def debug_delete_something(self) -> None:
        """
        Randomly delete one of: first name, a middle name, or a postcode.
        """
        assert not self.is_hashed
        has_first_name = self.has_first_name()
        n_middle_names = self.n_middle_names()
        n_postcodes = self.n_postcodes()
        n_possibilities = int(has_first_name) + n_middle_names + n_postcodes
        if n_possibilities == 0:
            log.warning(f"Unable to delete info from {self}")
            return
        which = random.randint(0, n_possibilities - 1)

        if has_first_name:
            if which == 0:
                self.first_name = ""
                return
            which -= 1

        if which < n_middle_names:
            del self.middle_names[which]
            return
        which -= n_middle_names

        del self.postcodes[which]

    def debug_mutate_something(self) -> None:
        """
        Randomly mutate one of: first name, a middle name, or a postcode.
        """
        assert not self.is_hashed
        has_first_name = self.has_first_name()
        n_middle_names = self.n_middle_names()
        n_postcodes = self.n_postcodes()
        n_possibilities = int(has_first_name) + n_middle_names + n_postcodes
        if n_possibilities == 0:
            log.warning(f"Unable to mutate info from {self}")
            return
        which = random.randrange(n_possibilities)

        if has_first_name:
            if which == 0:
                self.first_name = mutate_name(self.first_name)
                return
            which -= 1

        if which < n_middle_names:
            self.middle_names[which] = mutate_name(self.middle_names[which])
            return
        which -= n_middle_names

        self.postcodes[which].identifier = mutate_postcode(
            self.postcodes[which].identifier, self.cfg
        )


# =============================================================================
# Result of a match attempt
# =============================================================================


class MatchResult(object):
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


# =============================================================================
# People: a collection of Person objects
# =============================================================================
# Try staring at the word "people" for a while and watch it look odd...


class People(object):
    """
    Represents a group of people, and implements a shortlist.
    """

    def __init__(
        self,
        cfg: MatchConfig,
        person: Person = None,
        people: List[Person] = None,
    ) -> None:
        """
        Creates a blank collection.

        Raises :exc:`crate_anon.linkage.fuzzy_id_match.DuplicateLocalIDError`
        if some people have duplicate ``local_id`` values.
        """
        self.cfg = cfg
        self.people = []  # type: List[Person]
        self.dob_to_people = defaultdict(list)  # type: Dict[str, List[Person]]
        self.hashed_dob_to_people = defaultdict(
            list
        )  # type: Dict[str, List[Person]]  # noqa
        self._known_ids = set()  # type: Set[str]

        if person:
            self.add_person(person)
        if people:
            self.add_people(people)

    def add_person(self, person: Person) -> None:
        """
        Adds a single person.

        Raises :exc:`crate_anon.linkage.fuzzy_id_match.DuplicateLocalIDError`
        if the person has a ``local_id`` value already in our collection.
        """
        if person.local_id in self._known_ids:
            raise DuplicateLocalIDError(
                f"Person with duplicate local ID {person.local_id!r}"
            )
        self._known_ids.add(person.local_id)
        self.people.append(person)
        dob = person.dob
        if dob:
            self.dob_to_people[dob].append(person)
        hashed_dob = person.hashed_dob
        if hashed_dob:
            self.hashed_dob_to_people[hashed_dob].append(person)

    def add_people(self, people: List[Person]) -> None:
        """
        Adds multiple people.

        Raises :exc:`crate_anon.linkage.fuzzy_id_match.DuplicateLocalIDError`
        if some people have duplicate ``local_id`` values with respect to those
        we already know.
        """
        for person in people:
            self.add_person(person)

    def size(self) -> int:
        """
        Returns the number of people in this object.
        """
        return len(self.people)

    def assert_valid_as_probands(self) -> None:
        """
        Ensures all people have sufficient information to act as a proband,
        or raises :exc:`AssertionError`.
        """
        log.info("Validating probands...")
        for p in self.people:
            p.assert_valid_as_proband()
        log.info("... OK")

    def assert_valid_as_sample(self) -> None:
        """
        Ensures all people have sufficient information to act as a candidate
        from a sample, or raises :exc:`AssertionError`.
        """
        log.info("Validating sample...")
        for p in self.people:
            p.assert_valid_as_candidate()
        log.info("... OK")

    def gen_shortlist(self, proband: Person) -> Generator[Person, None, None]:
        """
        Generates a shortlist of potential candidates, by date of birth.

        Yields:
            proband: a :class:`Person`
        """
        if proband.is_hashed:
            hashed_dob = proband.hashed_dob
            if not hashed_dob:
                return
            for person in self.hashed_dob_to_people[proband.hashed_dob]:
                yield person
        else:
            dob = proband.dob
            if not dob:
                return
            for person in self.dob_to_people[dob]:
                yield person

    def get_unique_match_detailed(self, proband: Person) -> MatchResult:
        """
        Returns a single person matching the proband, or ``None`` if there is
        no match (as defined by the probability settings in ``cfg``).

        Args:
            proband: a :class:`Person`
        """

        # 2020-04-25: Do this in one pass.
        # A bit like
        # https://www.geeksforgeeks.org/python-program-to-find-second-largest-number-in-a-list/  # noqa
        # ... but modified, as that fails to deal with joint winners
        # ... and it's not a super algorithm anyway.

        # Step 1. Scan everything in a single pass, establishing the best
        # candidate and the runner-up.
        cfg = self.cfg
        best_log_odds = MINUS_INFINITY
        second_best_log_odds = MINUS_INFINITY

        best_candidate = None  # type: Optional[Person]
        second_best_candidate = None  # type: Optional[Person]
        for candidate in self.gen_shortlist(proband):
            log_odds = candidate.log_odds_same(proband)
            if log_odds > best_log_odds:
                second_best_log_odds = best_log_odds
                second_best_candidate = best_candidate
                best_log_odds = log_odds
                best_candidate = candidate
            elif log_odds > second_best_log_odds:
                second_best_log_odds = log_odds
                second_best_candidate = candidate

        result = MatchResult(
            best_log_odds=best_log_odds,
            second_best_log_odds=second_best_log_odds,
            best_candidate=best_candidate,
            second_best_candidate=second_best_candidate,
            proband=proband,
        )

        # Is there a winner?
        if (
            best_candidate
            and best_log_odds >= cfg.min_log_odds_for_match
            and best_log_odds
            >= (second_best_log_odds + cfg.exceeds_next_best_log_odds)
        ):
            # (a) There needs to be a best candidate.
            # (b) The best needs to be good enough.
            # (c) The best must beat the runner-up by a sufficient margin.
            result.winner = best_candidate

        return result

    def get_unique_match(self, proband: Person) -> Optional[Person]:
        """
        Returns a single person matching the proband, or ``None`` if there is
        no match (as defined by the probability settings in ``cfg``).

        Args:
            proband: a :class:`Person`

        Returns:
            the winner (a :class:`Person`) or ``None``
        """
        result = self.get_unique_match_detailed(proband)
        return result.winner

    def hashed(self) -> "People":
        """
        Returns a hashed version of itself.
        """
        return People(cfg=self.cfg, people=[p.hashed() for p in self.people])

    def copy(self) -> "People":
        """
        Returns a copy of itself.
        """
        return People(cfg=self.cfg, people=[p.copy() for p in self.people])
