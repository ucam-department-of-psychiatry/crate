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
import csv
from dataclasses import dataclass, field
import json
from io import TextIOBase
import logging
import random
from types import TracebackType
from typing import (
    Any,
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    Set,
    Type,
    Union,
)

from cardinal_pythonlib.reprfunc import auto_repr
import jsonlines

from crate_anon.linkage.comparison import (
    bayes_compare,
    Comparison,
    DirectComparison,
)
from crate_anon.linkage.constants import MINUS_INFINITY
from crate_anon.linkage.helpers import (
    getdictval,
    mutate_name,
    mutate_postcode,
)
from crate_anon.linkage.identifiers import (
    DateOfBirth,
    Forename,
    gen_best_comparisons,
    Gender,
    Identifier,
    Postcode,
    Surname,
    TemporalIDHolder,
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
    Core functions for person classes.
    """

    class PersonKey:
        LOCAL_ID = "local_id"
        # ... person ID within the relevant database (proband/sample)
        FIRST_NAME = "first_name"
        MIDDLE_NAMES = "middle_names"
        SURNAME = "surname"
        DOB = "dob"
        GENDER = "gender"
        POSTCODES = "postcodes"
        OTHER_INFO = "other_info"
        # ... anything the user may want to attach

    # [getattr(PersonKey, x) for x in vars(PersonKey)...] does not work here as
    # PersonKey is not in scope within a list comprehension here; see
    # check_inner_class_attr_access.py and
    # https://stackoverflow.com/questions/13905741. But this works:
    ALL_PERSON_KEYS = []  # type: List[str]
    for tmp in vars(PersonKey):
        if not tmp.startswith("_"):
            ALL_PERSON_KEYS.append(getattr(PersonKey, tmp))
    del tmp

    # For reading CSV:
    SEMICOLON_DELIMIT = [PersonKey.MIDDLE_NAMES, PersonKey.POSTCODES]
    TEMPORAL_IDENTIFIERS = [PersonKey.POSTCODES]
    PLAINTEXT_CSV_FORMAT_HELP = (
        f"CSV format. Header row present. Columns: {ALL_PERSON_KEYS}. "
        f"The fields {TEMPORAL_IDENTIFIERS} are in TemporalIdentifier format. "
        f"{Identifier.TEMPORAL_ID_FORMAT_HELP} "
        f"Semicolon-separated values are allowed within {SEMICOLON_DELIMIT}."
    )
    HASHED_JSONLINES_FORMAT_HELP = (
        "File created by CRATE in JSON Lines (.jsonl) format. (Note the 'jq' "
        "tool for inspecting these.)"
    )

    def __repr__(self):
        return auto_repr(self)

    @classmethod
    def plaintext_csv_columns(cls) -> List[str]:
        """
        CSV column names -- including user-specified "other" information.
        """
        return cls.ALL_PERSON_KEYS

    def plaintext_csv_dict(self) -> Dict[str, str]:
        """
        Returns a dictionary suitable for :class:`csv.DictWriter`.
        This is for writing identifiable content.
        """
        d = {}  # type: Dict[str, str]
        for k in self.ALL_PERSON_KEYS:
            a = getattr(self, k)
            if k in self.SEMICOLON_DELIMIT:
                v = ";".join(str(x) for x in a)
            else:
                v = str(a)
            d[k] = v
        return d


# =============================================================================
# String representation of several person classes
# =============================================================================


def identifiable_person_str(self: Union["SimplePerson", "Person"]) -> str:
    """
    A bit ugly; this function refers to attributes of two separate classes.
    However:

    - There's no point making BasePerson an abstract base class, because there
      are no abstract methods.
    - I don't think Person can sensible inherit from the dataclass SimplePerson
      because its attributes are of different types.

    So, while ugly, this works and the type checker is happy.
    """
    names = " ".join(
        [str(self.first_name)]
        + [str(m) for m in self.middle_names]
        + [str(self.surname)]
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
    classname = type(self).__name__
    return f"{classname} with {details}"


# =============================================================================
# SimplePerson
# =============================================================================


@dataclass
class SimplePerson(BasePerson):
    """
    Simple information about a person, without frequency calculations.
    Does not need a config.
    Used for two purposes:

    1. Demonstration purposes.
    2. Validation data fetching -- between database and CSV output.

    Will write CSV, but not read.
    Will not standardize its content.
    """

    # Names must match ALL_PERSON_KEYS:
    local_id: str = ""
    other_info: str = ""
    first_name: str = ""
    middle_names: List[str] = field(default_factory=lambda: [])
    surname: str = ""
    dob: str = ""
    gender: str = ""
    postcodes: List[TemporalIDHolder] = field(default_factory=lambda: [])

    def __str__(self) -> str:
        return identifiable_person_str(self)


# =============================================================================
# Person
# =============================================================================


class Person(BasePerson):
    """
    A proper representation of a person that can do hashing and comparisons.
    The information may be incomplete or slightly wrong.
    Includes frequency information and requires a config.
    """

    @staticmethod
    def plain_or_hashed_txt(plaintext: bool) -> str:
        """
        Used for error messages.
        """
        return "plaintext" if plaintext else "hashed"

    # -------------------------------------------------------------------------
    # Creation
    # -------------------------------------------------------------------------

    def __init__(
        self,
        cfg: MatchConfig,
        local_id: str = "",
        other_info: str = "",
        first_name: Union[str, Forename] = "",
        middle_names: List[Union[str, Forename]] = None,
        surname: Union[str, Surname] = "",
        dob: Union[str, DateOfBirth] = "",
        gender: Union[str, Gender] = "",
        postcodes: List[Union[Postcode, TemporalIDHolder]] = None,
    ) -> None:
        """
        Args:
            cfg:
                The config object.
            local_id:
                Identifier within this person's local database (e.g. proband ID
                or sample ID). Typically a research pseudonym, not itself
                identifying.
            other_info:
                String containing any other attributes the user may wish to
                remember (e.g. in JSON). Only used for validation research
                (e.g. ensuring linkage is not biased by ethnicity).

            first_name:
                The person's first name, as a string or a Forename object.
            middle_names:
                Any middle names, as strings or Forename objects.
            surname:
                The person's surname, as a string or a Surname object.
            dob:
                The date of birth, in ISO-8061 "YYYY-MM-DD" string format,
                or as a DateOfBirth object.
            gender:
                The gender: 'M', 'F', 'X', or '', or a Gender object.
            postcodes:
                Any UK postcodes for this person, with optional associated
                dates.
        """
        self._is_plaintext = None  # type: Optional[bool]

        def chk_plaintext(new_identifier: Identifier) -> None:
            """
            Ensure we don't mix plaintext and hashed data.
            """
            new_plaintext = new_identifier.is_plaintext
            if self._is_plaintext is None:
                self._is_plaintext = new_plaintext
            elif new_plaintext != self._is_plaintext:
                new = self.plain_or_hashed_txt(new_plaintext)
                old = self.plain_or_hashed_txt(self._is_plaintext)
                raise ValueError(
                    f"Trying to add {new} information to a Person containing "
                    f"only {old} information; new data was "
                    f"{new_identifier!r}; current is {self!r}"
                )

        assert isinstance(cfg, MatchConfig)
        self.cfg = cfg
        self.baseline_log_odds_same_person = (
            self.cfg.baseline_log_odds_same_person
        )  # for speed

        # local_id
        self.local_id = str(local_id) if local_id is not None else None
        if not self.local_id:
            raise ValueError(f"Bad local_id: {local_id!r}")

        # other_info
        self.other_info = other_info or ""
        if not isinstance(self.other_info, str):
            raise ValueError(f"Bad other_info: {self.other_info!r}")

        # gender
        gender = "" if gender is None else gender
        # DO NOT DO: gender = gender or ""
        # ... because bool(Gender(cfg, gender="")) == False.
        if isinstance(gender, Gender):
            self.gender = gender
        else:
            self.gender = Gender(cfg=cfg, gender=gender)
        chk_plaintext(self.gender)

        # first_name
        first_name = "" if first_name is None else first_name
        if isinstance(first_name, Forename):
            self.first_name = first_name
        else:
            self.first_name = Forename(
                cfg=cfg, name=first_name, gender=self.gender.gender
            )
        chk_plaintext(self.first_name)

        # middle_names
        middle_names = middle_names or []
        if not isinstance(middle_names, list):
            raise ValueError(f"Bad middle_names: {middle_names!r}")
        self.middle_names = []  # type: List[Forename]
        for m in middle_names:
            if not m:
                continue
            if not isinstance(m, Forename):
                m = Forename(cfg=cfg, name=m, gender=self.gender.gender)
            chk_plaintext(m)
            self.middle_names.append(m)

        # surname
        surname = "" if surname is None else surname
        if isinstance(surname, Surname):
            self.surname = surname
        else:
            self.surname = Surname(
                cfg=cfg, name=surname, gender=self.gender.gender
            )
        chk_plaintext(self.surname)

        # dob (NB mandatory for real work but we still want to be able to
        # create Person objects without a DOB inc. for testing)
        dob = "" if dob is None else dob
        if isinstance(dob, DateOfBirth):
            self.dob = dob
        else:
            self.dob = DateOfBirth(cfg=cfg, dob=dob)
        chk_plaintext(self.dob)

        # postcodes
        postcodes = postcodes or []
        if not isinstance(postcodes, list):
            raise ValueError(f"Bad postcodes: {postcodes!r}")
        self.postcodes = []  # type: List[Postcode]
        for p in postcodes:
            if not p:
                continue
            if isinstance(p, Postcode):
                pass
            elif isinstance(p, TemporalIDHolder):
                p = Postcode(
                    cfg=cfg,
                    postcode=p.identifier,
                    start_date=p.start_date,
                    end_date=p.end_date,
                )
            else:
                raise ValueError(f"Bad data structure for postcode: {p!r}")
            chk_plaintext(p)
            self.postcodes.append(p)

    @classmethod
    def from_plaintext_csv(
        cls, cfg: MatchConfig, rowdict: Dict[str, str]
    ) -> "Person":
        """
        Returns a :class:`Person` object from a CSV row.

        Args:
            cfg: a configuration object
            rowdict: a CSV row, read via :class:`csv.DictReader`.
        """
        kwargs = {}  # type: Dict[str, Any]
        for attr in cls.ALL_PERSON_KEYS:
            v = rowdict[attr]
            if attr in cls.SEMICOLON_DELIMIT:
                v = [x.strip() for x in v.split(";") if x]
                if attr in cls.TEMPORAL_IDENTIFIERS:
                    v = [
                        TemporalIDHolder.from_plaintext_str(cfg, x) for x in v
                    ]
            else:
                # All TEMPORAL_IDENTIFIERS are in SEMICOLON_DELIMIT
                assert attr not in cls.TEMPORAL_IDENTIFIERS
            kwargs[attr] = v
        return Person(cfg=cfg, **kwargs)

    @classmethod
    def from_hashed_dict(cls, cfg: MatchConfig, d: Dict[str, Any]) -> "Person":
        """
        Restore a hashed version from a dictionary (which has been read from
        JSON).
        """
        pk = cls.PersonKey
        middle_names = []  # type: List[Forename]
        for mnd in getdictval(d, pk.MIDDLE_NAMES, list):
            if not isinstance(mnd, dict):
                raise ValueError(
                    f"{pk.MIDDLE_NAMES} contains something that is not a "
                    f"dict: {mnd!r}"
                )
            middle_names.append(Forename.from_hashed_dict(cfg, mnd))
        postcodes = []  # type: List[Postcode]
        for pd in getdictval(d, pk.POSTCODES, list):
            if not isinstance(pd, dict):
                raise ValueError(
                    f"{pk.POSTCODES} contains something that is not a "
                    f"dict: {pd!r}"
                )
            postcodes.append(Postcode.from_hashed_dict(cfg, pd))
        return Person(
            cfg=cfg,
            local_id=getdictval(d, pk.LOCAL_ID, str),
            other_info=getdictval(d, pk.OTHER_INFO, str, mandatory=False),
            first_name=Forename.from_hashed_dict(
                cfg, getdictval(d, pk.FIRST_NAME, dict)
            ),
            middle_names=middle_names,
            surname=Surname.from_hashed_dict(
                cfg, getdictval(d, pk.SURNAME, dict)
            ),
            dob=DateOfBirth.from_hashed_dict(cfg, getdictval(d, pk.DOB, dict)),
            gender=Gender.from_hashed_dict(
                cfg, getdictval(d, pk.GENDER, dict)
            ),
            postcodes=postcodes,
        )

    @classmethod
    def from_json_str(cls, cfg: MatchConfig, s: str) -> "Person":
        """
        Restore a hashed version from a string representing JSON.
        """
        d = json.loads(s)
        return cls.from_hashed_dict(cfg, d)

    # -------------------------------------------------------------------------
    # Equality, hashing -- local_id should be unique
    # -------------------------------------------------------------------------
    # Be careful:
    # - https://inventwithpython.com/blog/2019/02/01/hashable-objects-must-be-immutable/  # noqa
    # - https://docs.python.org/3/glossary.html [re "hashable"]
    # Here, we define equality based on local_id, which will not change. In
    # practice, nothing else will either.

    def __eq__(self, other: "Person") -> bool:
        return self.local_id == other.local_id

    def __hash__(self) -> int:
        return hash(self.local_id)

    # -------------------------------------------------------------------------
    # Representation
    # -------------------------------------------------------------------------

    def is_plaintext(self) -> bool:
        """
        Is this a plaintext (identifiable) Person?
        """
        return self._is_plaintext

    def is_hashed(self) -> bool:
        """
        Is this a hashed (de-identified) Person?
        """
        return not self.is_plaintext()

    def __str__(self) -> str:
        if self.is_hashed():
            return f"Hashed person with local_id={self.local_id!r}"
        return identifiable_person_str(self)

    def hashed_dict(
        self,
        include_frequencies: bool = True,
        include_other_info: bool = False,
    ) -> Dict[str, Any]:
        """
        For JSON.

        Args:
            include_frequencies:
                Include frequency information. If you don't, this makes the
                resulting file suitable for use as a sample, but not as a
                proband file.
            include_other_info:
                include the (potentially identifying) ``other_info`` data?
                Usually ``False``; may be ``True`` for validation.
        """
        pk = self.PersonKey
        d = {
            pk.LOCAL_ID: self.cfg.local_id_hash_fn(self.local_id),
            pk.FIRST_NAME: self.first_name.hashed_dict(include_frequencies),
            pk.MIDDLE_NAMES: [
                m.hashed_dict(include_frequencies) for m in self.middle_names
            ],
            pk.SURNAME: self.surname.hashed_dict(include_frequencies),
            pk.DOB: self.dob.hashed_dict(include_frequencies),
            pk.GENDER: self.gender.hashed_dict(include_frequencies),
            pk.POSTCODES: [
                p.hashed_dict(include_frequencies) for p in self.postcodes
            ],
        }
        if include_other_info:
            d[pk.OTHER_INFO] = self.other_info
        return d

    def hashed_json_str(
        self,
        include_frequencies: bool = True,
        include_other_info: bool = False,
    ) -> str:
        """
        A string version of the hashed person in JSON format.

        Args:
            include_frequencies:
                Include frequency information. If you don't, this makes the
                resulting file suitable for use as a sample, but not as a
                proband file.
            include_other_info:
                include the (potentially identifying) ``other_info`` data?
                Usually ``False``; may be ``True`` for validation.
        """
        d = self.hashed_dict(
            include_frequencies=include_frequencies,
            include_other_info=include_other_info,
        )
        return json.dumps(d)

    def copy(self) -> "Person":
        """
        Returns a copy of this object.

        - :func:`copy.deepcopy` is incredibly slow, yet :func:`copy.copy` isn't
          enough when we want to mutate this object.
        - So we do it quasi-manually. It's just lists that we want to treat as
          special.
        """
        copy_attrs = self.ALL_PERSON_KEYS
        kwargs = {}  # type: Dict[str, Any]
        for attrname in copy_attrs:
            value = getattr(self, attrname)
            if isinstance(value, list):  # special handling here
                value = [copy.copy(x) for x in value]
            kwargs[attrname] = value
        return Person(cfg=self.cfg, **kwargs)
        # todo: *** check this works

    # -------------------------------------------------------------------------
    # Created hashed version
    # -------------------------------------------------------------------------

    def hashed(
        self,
        include_frequencies: bool = True,
        include_other_info: bool = False,
    ) -> "Person":
        """
        Returns a :class:`Person` object but with all the elements hashed (if
        they are not blank).

        Note that you do NOT need to do this just to write a hashed version to
        disk. This function is primarily for comparing an entire sample of
        hashed people to plaintext people, or vice versa; we hash the plaintext
        version first.

        Args:
            include_frequencies:
                Include frequency information. If you don't, this makes the
                resulting file suitable for use as a sample, but not as a
                proband file.
            include_other_info:
                include the (potentially identifying) ``other_info`` data?
                Usually ``False``; may be ``True`` for validation.
        """
        d = self.hashed_dict(
            include_frequencies=include_frequencies,
            include_other_info=include_other_info,
        )
        return self.from_hashed_dict(self.cfg, d)

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
        # High speed function.
        return bayes_compare(
            log_odds=self.baseline_log_odds_same_person,
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
            proband: another :class:`Person` object.

        **Note**

        In general, frequency information is associated with the proband,
        not the candidate, so use ``proband.thing.comparison(self.thing)``.

        """
        # The shortlisting process will already have ensured a DOB match.
        # Therefore, while we need to process DOB to get the probabilities
        # right for good candidates, we can do other things first to eliminate
        # bad ones quicker.

        # Surname (might eliminate)
        yield proband.surname.comparison(self.surname)

        # First name (might eliminate)
        yield proband.first_name.comparison(self.first_name)

        # Gender (won't absolutely eliminate)
        yield proband.gender.comparison(self.gender)

        # DOB (see above)
        # There is no special treatment of 29 Feb (since this DOB is
        # approximately 4 times less common than other birthdays, in principle
        # it does merit special treatment, but we ignore that).

        yield proband.dob.comparison(self.dob)

        # Middle names (slowest)
        yield from self._comparisons_middle_names(proband)

        # Postcodes (doesn't eliminate)
        yield from gen_best_comparisons(
            proband_identifiers=proband.postcodes,
            candidate_identifiers=self.postcodes,
            no_match_comparison=None,
        )

    def _comparisons_middle_names(
        self, proband: "Person"
    ) -> Generator[Comparison, None, None]:
        """
        Generates comparisons for middle names.
        """
        cfg = self.cfg
        n_candidate_middle_names = len(self.middle_names)
        n_proband_middle_names = len(proband.middle_names)
        max_n_middle_names = max(
            n_candidate_middle_names, n_proband_middle_names
        )
        min_n_middle_names = min(
            n_candidate_middle_names, n_proband_middle_names
        )

        for i in range(max_n_middle_names):
            if i < min_n_middle_names:
                # -------------------------------------------------------------
                # Name present in both. Exact and partial matches
                # -------------------------------------------------------------
                yield proband.middle_names[i].comparison(self.middle_names[i])
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
                    p_d_given_same_person=p_d_given_same_person,
                    p_d_given_diff_person=cfg.p_middle_name_present(n),
                )

    # -------------------------------------------------------------------------
    # Info functions
    # -------------------------------------------------------------------------

    def has_first_name(self) -> bool:
        """
        Does this person have a first name?
        """
        return bool(self.first_name)

    def n_middle_names(self) -> int:
        """
        How many names does this person have?
        """
        return len(self.middle_names)

    def has_dob(self) -> bool:
        """
        Do we have a DOB?
        """
        return bool(self.dob)

    def n_postcodes(self) -> int:
        """
        How many postcodes does this person have?
        """
        return len(self.postcodes)

    def ensure_valid_as_proband(
        self, debug_allow_no_dob: bool = False
    ) -> None:
        """
        Ensures this person has sufficient information to act as a proband, or
        raises :exc:`ValueError`.
        """
        if not self.has_dob() and not debug_allow_no_dob:
            raise ValueError("Proband: missing DOB")
        self.first_name.ensure_has_freq_info_if_id_present()
        for m in self.middle_names:
            m.ensure_has_freq_info_if_id_present()
        self.surname.ensure_has_freq_info_if_id_present()
        self.dob.ensure_has_freq_info_if_id_present()
        self.gender.ensure_has_freq_info_if_id_present()
        for p in self.postcodes:
            p.ensure_has_freq_info_if_id_present()

    def ensure_valid_as_candidate(
        self, debug_allow_no_dob: bool = False
    ) -> None:
        """
        Ensures this person has sufficient information to act as a candidate,
        or raises :exc:`AssertionError`.
        """
        if not self.has_dob() and not debug_allow_no_dob:
            raise ValueError("Candidate: missing DOB")

    # -------------------------------------------------------------------------
    # Debugging functions to check this object
    # -------------------------------------------------------------------------

    def debug_gen_identifiers(self) -> Generator[Identifier, None, None]:
        """
        Yield all identifiers.
        """
        if self.first_name:
            yield self.first_name
        for m in self.middle_names:
            yield m
        if self.surname:
            yield self.surname
        if self.dob:
            yield self.dob
        if self.gender:
            yield self.gender
        for p in self.postcodes:
            yield p

    # -------------------------------------------------------------------------
    # Debugging functions to mutate this object
    # -------------------------------------------------------------------------

    def debug_delete_something(self) -> None:
        """
        Randomly delete one of: first name, a middle name, or a postcode.
        """
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
                self.first_name = Forename(self.cfg)
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
        has_first_name = self.has_first_name()
        n_middle_names = self.n_middle_names()
        n_postcodes = self.n_postcodes()
        n_possibilities = int(has_first_name) + n_middle_names + n_postcodes
        if n_possibilities == 0:
            log.warning(f"Unable to mutate info from {self}")
            return
        which = random.randrange(n_possibilities)

        cfg = self.cfg
        if has_first_name:
            if which == 0:
                oldname = self.first_name
                assert oldname.is_plaintext
                self.first_name = Forename(
                    cfg, name=mutate_name(oldname.name), gender=oldname.gender
                )
                return
            which -= 1

        if which < n_middle_names:
            oldname = self.middle_names[which]
            assert oldname.is_plaintext
            self.middle_names[which] = Forename(
                cfg, name=mutate_name(oldname.name), gender=oldname.gender
            )
            return
        which -= n_middle_names

        oldpostcode = self.postcodes[which]
        assert oldpostcode.is_plaintext
        self.postcodes[which] = Postcode(
            cfg, postcode=mutate_postcode(oldpostcode.postcode_unit, cfg)
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
        people: Iterable[Person] = None,
    ) -> None:
        """
        Creates a blank collection.

        Raises :exc:`crate_anon.linkage.fuzzy_id_match.DuplicateLocalIDError`
        if some people have duplicate ``local_id`` values.
        """
        self.cfg = cfg
        self.people = []  # type: List[Person]
        # ... list is preferable to set, as we may slice it for parallel
        # processing, and it maintains order.

        # These may be plaintext or hashed DOB strings depending on our people:
        self.dob_md_to_people = defaultdict(
            list
        )  # type: Dict[str, List[Person]]  # noqa
        self.dob_yd_to_people = defaultdict(
            list
        )  # type: Dict[str, List[Person]]  # noqa
        self.dob_ym_to_people = defaultdict(
            list
        )  # type: Dict[str, List[Person]]  # noqa
        self.dob_ymd_to_people = defaultdict(
            list
        )  # type: Dict[str, List[Person]]  # noqa

        self._known_ids = set()  # type: Set[str]
        self._people_are_plaintext = None  # type: Optional[bool]

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
        if self.people:
            # Not the first person.
            if person.is_plaintext() != self._people_are_plaintext:
                new = Person.plain_or_hashed_txt(person.is_plaintext())
                old = Person.plain_or_hashed_txt(self._people_are_plaintext)
                raise ValueError(
                    f"Trying to add a {new} person but all existing people "
                    f"are {old}"
                )
        else:
            # First person
            self._people_are_plaintext = person.is_plaintext()

        if person.local_id in self._known_ids:
            raise DuplicateLocalIDError(
                f"Person with duplicate local ID {person.local_id!r}"
            )
        self._known_ids.add(person.local_id)
        self.people.append(person)

        dob = person.dob
        if dob:
            self.dob_md_to_people[dob.dob_md].append(person)
            self.dob_yd_to_people[dob.dob_yd].append(person)
            self.dob_ym_to_people[dob.dob_ym].append(person)
            self.dob_ymd_to_people[dob.dob_str].append(person)

    def add_people(self, people: Iterable[Person]) -> None:
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

    def ensure_valid_as_probands(self) -> None:
        """
        Ensures all people have sufficient information to act as a proband,
        or raises :exc:`ValueError`.
        """
        log.info("Validating probands...")
        for p in self.people:
            p.ensure_valid_as_proband()
        log.info("... OK")

    def ensure_valid_as_sample(self) -> None:
        """
        Ensures all people have sufficient information to act as a candidate
        from a sample, or raises :exc:`ValueError`.
        """
        log.info("Validating sample...")
        for p in self.people:
            p.ensure_valid_as_candidate()
        log.info("... OK")

    def gen_shortlist(self, proband: Person) -> Generator[Person, None, None]:
        """
        Generates a shortlist of potential candidates, by date of birth.

        Yields:
            proband: a :class:`Person`
        """
        # A high-speed function.
        cfg = self.cfg
        dob = proband.dob
        if not dob:
            return
        if cfg.complete_dob_mismatch_allowed:
            # No shortlisting; everyone's a candidate. Slow.
            for person in self.people:
                yield person
        else:
            # Implement the shortlist by DOB.
            # Most efficient to let set operations determine uniqueness, then
            # iterate through the set.

            # First, exact matches:
            shortlist = set(self.dob_ymd_to_people[dob.dob_str])

            # Now, we'll slow it all down with partial matches:
            if cfg.partial_dob_mismatch_allowed:
                shortlist.update(self.dob_md_to_people[dob.dob_md])
                shortlist.update(self.dob_yd_to_people[dob.dob_yd])
                shortlist.update(self.dob_ym_to_people[dob.dob_ym])

            for person in shortlist:
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


# =============================================================================
# Loading people data
# =============================================================================


def gen_person_from_file(
    cfg: MatchConfig, filename: str, plaintext: bool = True
) -> Generator[Person, None, None]:
    """
    Read a list of people from a CSV/JSONLines file. See
    :class:`BasePerson.PersonKey` for the column details.

    Args:
        cfg:
            Configuration object.
        filename:
            Filename to read.
        plaintext:
            Read in plaintext (from CSV), rather than hashed (from JSON Lines),
            format?

    Yields:
        Person objects
    """
    log.info(f"Reading file: {filename}")
    assert filename
    if plaintext:
        # CSV file
        with open(filename, "rt") as f:
            reader = csv.DictReader(f)
            for rowdict in reader:
                yield Person.from_plaintext_csv(cfg, rowdict)
    else:
        # JSON Lines file
        with jsonlines.open(filename) as reader:
            for obj in reader:
                yield Person.from_hashed_dict(cfg, obj)
    log.info(f"... finished reading from {filename}")


# =============================================================================
# Saving people data
# =============================================================================


class PersonWriter:
    """
    A context manager for writing :class:`Person` objects to CSV (plaintext) or
    JSONL (hashed).
    """

    def __init__(
        self,
        file: TextIOBase = None,
        filename: str = None,
        plaintext: bool = False,
        include_frequencies: bool = True,
        include_other_info: bool = False,
    ) -> None:
        """
        Args:
            file:
                File-like object to which to write. Use either this or
                ``filename``, not both.
            filename:
                Filename to which to write. Use either this or ``file``, not
                both.
            plaintext:
                Plaintext (in CSV)? If False, will be written hashed (in
                JSONL).
            include_frequencies:
                (For hashed writing only.) Include frequency information.
                Without this, the resulting file is suitable for use as a
                sample, but not as a proband file.
            include_other_info:
                (For hashed writing only.) Include the (potentially
                identifying) ``other_info`` data? Usually ``False``; may be
                ``True`` for validation.
        """
        assert bool(file) != bool(
            filename
        ), "Specify either file or filename (and not both)"
        if include_other_info:
            log.warning(
                "include_other_info is set; use this for validation only"
            )

        self.filename = filename
        self.file = file
        self.plaintext = plaintext
        self.include_frequencies = include_frequencies
        self.include_other_info = include_other_info

        self.csv_writer = None  # type: Optional[csv.DictWriter]

    def __enter__(self) -> "PersonWriter":
        """
        Used by the ``with`` statement; the thing returned is what you get
        from ``with``.
        """
        # 1. Ensure we have a file.
        if self.filename:
            log.info(f"Saving to: {self.filename}")
            self.file = open(self.filename, "wt")
            # Don't write to the log if we're not using a filename; we may be
            # writing to an in-memory structure, in which case the user
            # probably doesn't care.
        # 2. Create a writer.
        if self.plaintext:
            self.csv_writer = csv.DictWriter(
                self.file, fieldnames=SimplePerson.ALL_PERSON_KEYS
            )
            self.csv_writer.writeheader()
        else:
            self.jsonl_writer = jsonlines.Writer(self.file)
        return self

    def write(self, person: Union[SimplePerson, Person]) -> None:
        """
        Write a person to the file.
        """
        if self.plaintext:
            self.csv_writer.writerow(person.plaintext_csv_dict())
        else:
            if isinstance(person, SimplePerson):
                raise ValueError(
                    "Cannot write a hashed version of a SimplePerson"
                )
            self.jsonl_writer.write(
                person.hashed_dict(
                    include_frequencies=self.include_frequencies,
                    include_other_info=self.include_other_info,
                )
            )

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """
        Reverse the operations of __enter__().
        """
        # 2. Close the writers.
        if self.plaintext:
            pass
        else:
            self.jsonl_writer.close()
        # 1. If we opened a file, ensure we close it.
        if self.filename:
            self.file.close()
            if exc_val is None:
                log.info(f"... finished saving to {self.filename}")
            else:
                log.info(f"... exception raised; closing {self.filename}")
            # As above, we won't write to the log if we don't have a filename.
