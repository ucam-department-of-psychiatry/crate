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

**Person representations for fuzzy matching.**

"""


# =============================================================================
# Imports
# =============================================================================

from dataclasses import dataclass, field
import json
import logging
import random
from typing import (
    Any,
    Dict,
    Generator,
    List,
    Optional,
    Union,
)

from cardinal_pythonlib.reprfunc import auto_repr

from crate_anon.linkage.comparison import (
    bayes_compare,
    Comparison,
    DirectComparison,
)
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
    PerfectID,
    Postcode,
    Surname,
    TemporalIDHolder,
)
from crate_anon.linkage.matchconfig import MatchConfig

log = logging.getLogger(__name__)


# =============================================================================
# BasePerson
# =============================================================================


class BasePerson:
    """
    Core functions for person classes.
    """

    class PersonKey:
        LOCAL_ID = "local_id"  # person ID within relevant DB (proband/sample)
        FIRST_NAME = "first_name"
        MIDDLE_NAMES = "middle_names"
        SURNAME = "surname"
        DOB = "dob"
        GENDER = "gender"
        POSTCODES = "postcodes"
        PERFECT_ID = "perfect_id"
        OTHER_INFO = "other_info"  # anything the user may want to attach

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
        f"CSV format with header row. Columns: {ALL_PERSON_KEYS}. "
        f"The fields {TEMPORAL_IDENTIFIERS} are in TemporalIdentifier format. "
        f"{Identifier.TEMPORAL_ID_FORMAT_HELP} "
        f"Semicolon-separated values are allowed within {SEMICOLON_DELIMIT}. "
        f"{PersonKey.PERFECT_ID}, if specified, contains one or more "
        f"perfect person identifiers as key:value pairs, e.g. "
        f"'nhs:12345;ni:AB6789XY'. The keys will be forced to lower case; "
        f"values will be forced to upper case. "
        f"{PersonKey.OTHER_INFO!r} is an arbitrary string for you to use "
        f"(e.g. for validation)."
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
            if k in self.SEMICOLON_DELIMIT and k != self.PersonKey.PERFECT_ID:
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
    k = BasePerson.PersonKey
    details = ", ".join(
        [
            f"{k.LOCAL_ID}={self.local_id}",
            f"{k.PERFECT_ID}={self.perfect_id}",
            f"name={names}",
            f"{k.GENDER}={self.gender}",
            f"{k.DOB}={self.dob}",
            f"{k.POSTCODES}={postcodes}",
            f"{k.OTHER_INFO}={self.other_info!r}",
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
    perfect_keys: Dict[str, str] = field(default_factory=lambda: {})
    perfect_id: str = ""  # a bit mangled

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
        perfect_id: Union[PerfectID, Dict[str, str]] = None,
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
            perfect_id:
                Any named person-unique identifiers (e.g. UK NHS numbers, UK
                National Insurance numbers), for non-fuzzy matching. Dictionary
                keys will be forced to lower case, and dictionary values to
                upper case.
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
                cfg=cfg, name=first_name, gender=self.gender.gender_str
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
                m = Forename(cfg=cfg, name=m, gender=self.gender.gender_str)
            chk_plaintext(m)
            self.middle_names.append(m)

        # surname
        surname = "" if surname is None else surname
        if isinstance(surname, Surname):
            self.surname = surname
        else:
            self.surname = Surname(
                cfg=cfg, name=surname, gender=self.gender.gender_str
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

        # perfect_id
        if isinstance(perfect_id, PerfectID):
            self.perfect_id = perfect_id
        else:
            self.perfect_id = PerfectID(cfg=cfg, identifiers=perfect_id)
        chk_plaintext(self.perfect_id)

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
            vstr = rowdict[attr]
            if attr in cls.SEMICOLON_DELIMIT:
                v = [x.strip() for x in vstr.split(";") if x]
                if attr == cls.PersonKey.PERFECT_ID:
                    v = PerfectID.from_plaintext_str(cfg, vstr)
                elif attr in cls.TEMPORAL_IDENTIFIERS:
                    v = [
                        TemporalIDHolder.from_plaintext_str(cfg, x) for x in v
                    ]
            else:
                # All TEMPORAL_IDENTIFIERS are in SEMICOLON_DELIMIT
                assert attr not in cls.TEMPORAL_IDENTIFIERS
                v = vstr
            kwargs[attr] = v
        return Person(cfg=cfg, **kwargs)

    @classmethod
    def from_json_dict(
        cls, cfg: MatchConfig, d: Dict[str, Any], hashed: bool = True
    ) -> "Person":
        """
        Restore a hashed or plaintext version from a dictionary (which has been
        read from JSONL).
        """
        pk = cls.PersonKey
        middle_names = []  # type: List[Forename]
        for mnd in getdictval(d, pk.MIDDLE_NAMES, list):
            if not isinstance(mnd, dict):
                raise ValueError(
                    f"{pk.MIDDLE_NAMES} contains something that is not a "
                    f"dict: {mnd!r}"
                )
            middle_names.append(Forename.from_dict(cfg, mnd, hashed))
        postcodes = []  # type: List[Postcode]
        for pd in getdictval(d, pk.POSTCODES, list):
            if not isinstance(pd, dict):
                raise ValueError(
                    f"{pk.POSTCODES} contains something that is not a "
                    f"dict: {pd!r}"
                )
            postcodes.append(Postcode.from_dict(cfg, pd, hashed))
        return Person(
            cfg=cfg,
            local_id=getdictval(d, pk.LOCAL_ID, str),
            other_info=getdictval(d, pk.OTHER_INFO, str, mandatory=False),
            first_name=Forename.from_dict(
                cfg, getdictval(d, pk.FIRST_NAME, dict), hashed
            ),
            middle_names=middle_names,
            surname=Surname.from_dict(
                cfg, getdictval(d, pk.SURNAME, dict), hashed
            ),
            dob=DateOfBirth.from_dict(
                cfg, getdictval(d, pk.DOB, dict), hashed
            ),
            gender=Gender.from_dict(
                cfg, getdictval(d, pk.GENDER, dict), hashed
            ),
            postcodes=postcodes,
            perfect_id=PerfectID.from_dict(
                cfg, getdictval(d, pk.PERFECT_ID, dict), hashed
            ),
        )

    @classmethod
    def from_json_str(cls, cfg: MatchConfig, s: str) -> "Person":
        """
        Restore a hashed version from a string representing JSON.
        """
        d = json.loads(s)
        return cls.from_json_dict(cfg, d)

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

    def as_dict(
        self,
        hashed: bool = True,
        include_frequencies: bool = True,
        include_other_info: bool = False,
    ) -> Dict[str, Any]:
        """
        For JSON.

        Args:
            hashed:
                Create a hashed/encrypted version?
            include_frequencies:
                Include frequency information. If you don't, this makes the
                resulting file suitable for use as a sample, but not as a
                proband file.
            include_other_info:
                include the (potentially identifying) ``other_info`` data?
                Usually ``False``; may be ``True`` for validation.
        """
        pk = self.PersonKey

        # This could be terser, but to be clear:
        if hashed:
            if self._is_plaintext:
                encrypt = True
                local_id = self.cfg.local_id_hash_fn(self.local_id)
            else:
                encrypt = False  # already encrypted; don't do it twice
                local_id = self.local_id
        else:
            if self._is_plaintext:
                encrypt = False
                local_id = self.local_id
            else:
                raise AssertionError(
                    "Can't create plaintext from hashed Person"
                )

        d = {
            pk.LOCAL_ID: local_id,
            pk.FIRST_NAME: self.first_name.as_dict(
                encrypt, include_frequencies
            ),
            pk.MIDDLE_NAMES: [
                m.as_dict(encrypt, include_frequencies)
                for m in self.middle_names
            ],
            pk.SURNAME: self.surname.as_dict(encrypt, include_frequencies),
            pk.DOB: self.dob.as_dict(encrypt, include_frequencies),
            pk.GENDER: self.gender.as_dict(encrypt, include_frequencies),
            pk.POSTCODES: [
                p.as_dict(encrypt, include_frequencies) for p in self.postcodes
            ],
            pk.PERFECT_ID: self.perfect_id.as_dict(encrypt),
        }
        if include_other_info:
            d[pk.OTHER_INFO] = self.other_info
        return d

    def copy(self) -> "Person":
        """
        Returns a copy of this object.

        - :func:`copy.deepcopy` is incredibly slow, yet :func:`copy.copy` isn't
          enough when we want to mutate this object.
        - We did do it quasi-manually, copying attributes but using
          ``[copy.copy(x) for x in value]`` if the value was a list.
        - However, since we have functions to convert to/from a dict
          representation, we may as well use them.
        """
        hashed = self.is_hashed()
        return self.from_json_dict(
            self.cfg,
            self.as_dict(
                hashed=hashed,
                include_frequencies=True,
                include_other_info=True,
            ),
            hashed=hashed,
        )

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
        d = self.as_dict(
            hashed=True,
            include_frequencies=include_frequencies,
            include_other_info=include_other_info,
        )
        return self.from_json_dict(self.cfg, d)

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
