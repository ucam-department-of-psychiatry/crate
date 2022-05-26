#!/usr/bin/env python

r"""
crate_anon/linkage/fuzzy_id_match.py

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

**Testing the concept of fuzzy matching with hashed identifiers, as part of
work to link UK NHS and education/social care data without sharing direct
patient identifiers.**


.. _TLSH: https://github.com/trendmicro/tlsh
.. _sdhash: https://roussev.net/sdhash/sdhash.html
.. _Nilsimsa: https://en.wikipedia.org/wiki/Nilsimsa_Hash
.. _ssdeep: https://ssdeep-project.github.io/ssdeep/index.html


**See draft paper.**


Other approaches to fuzzy matching of reduced data
--------------------------------------------------

[COVERED IN THE PAPER. FURTHER DETAIL HERE.]

Note the unsuitability of fuzzy hashing algorithms designed for long streams of
bytes or text. In general, these chop the input up into blocks, hash each
block, and then compare the sequence of mini-hashes for similarity.

- the trend micro locality sensitive hash (TLSH_), for fuzzy hashing of byte
  streams of at least 50 bytes;

- sdhash_, comparison of arbitrary data blobs based on common strings of binary
  data.

- Nilsimsa_ (2001/2004) a locality-sensitive hashing algorithm) and ssdeep_, a
  context triggered piecewise hashing (CTPH) algorithm.

  - See Kornblum J (2006), "Identifying almost identical files using context
    triggered piecewise hashing", *Digital Investigation* 3S: S91-S97,
    https://doi.org/10.1016/j.diin.2006.06.015.

... cited in the paper via Kornblum (2006) and Lee & Atkinson (2017), which
covers SSDEEP, TLSH, sdhash, and others.


Geography
---------

[COVERED IN THE PAPER. FURTHER DETAIL HERE.]

UK postcodes have this format:

+---------------------------------+
| Postcode                        |
+-----------------+---------------+
| Outward code    | Inward code   |
+------+----------+--------+------+
| Area | District | Sector | Unit |
+------+----------+--------+------+
| SW   | 1W       | 0      | NY   |
+------+----------+--------+------+

See
https://en.wikipedia.org/wiki/Postcodes_in_the_United_Kingdom#Formatting.

UK census geography is described at
https://www.ons.gov.uk/methodology/geography/ukgeographies/censusgeography.

The most important unit for our purposes is the Output Area (OA), the smallest
unit, which is made up of an integer number of postcode units.

So an OA is bigger than a postcode unit. But is it bigger or smaller than a
postcode sector? Smaller, I think.

- https://data.gov.uk/dataset/7f4e1818-4305-4962-adc4-e4e3effd7784/output-area-to-postcode-sector-december-2011-lookup-in-england-and-wales
- this allows you to look up *from* output area *to* postcode sector, implying
  that postcode sectors must be larger.

"""  # noqa

import argparse
from collections import Counter, defaultdict
import copy
import csv
from io import StringIO
import json
import logging
import math
from multiprocessing import cpu_count, Pool
import os
import pickle
import random
import re
import string
import sys
import time
from typing import (
    Any,
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
    TYPE_CHECKING,
    Union,
)

import appdirs
from cardinal_pythonlib.argparse_func import (
    RawDescriptionArgumentDefaultsHelpFormatter,
    ShowAllSubparserHelpAction,
)
from cardinal_pythonlib.datetimefunc import coerce_to_pendulum_date
from cardinal_pythonlib.hash import HmacSHA256Hasher
from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from cardinal_pythonlib.maths_py import round_sf
from cardinal_pythonlib.probability import (
    log_odds_from_1_in_n,
    log_odds_from_probability,
    log_posterior_odds_from_pdh_pdnh,
    probability_from_log_odds,
)
from cardinal_pythonlib.profile import do_cprofile
from cardinal_pythonlib.reprfunc import auto_repr
from cardinal_pythonlib.stringfunc import mangle_unicode_to_ascii
from fuzzy import DMetaphone
import pendulum
from pendulum.parsing.exceptions import ParserError
from pendulum import Date

from crate_anon.anonymise.anonregex import get_uk_postcode_regex_string
from crate_anon.common.constants import (
    EnvVar,
    EXIT_FAILURE,
    EXIT_SUCCESS,
)
from crate_anon.version import CRATE_VERSION

if TYPE_CHECKING:
    # noinspection PyProtectedMember,PyUnresolvedReferences
    from argparse import _SubParsersAction

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

CHECK_ASSERTIONS_IN_HIGH_SPEED_FUNCTIONS = False  # for debugging only

CRATE_FETCH_WORDLISTS = "crate_fetch_wordlists"
DAYS_PER_YEAR = 365.25  # approximately!
HIGHDEBUG = 15  # in between logging.DEBUG (10) and logging.INFO (20)
MINUS_INFINITY = -math.inf
THIS_DIR = os.path.abspath(os.path.dirname(__file__))
UK_MEAN_OA_POPULATION_2011 = 309
# ... https://www.ons.gov.uk/methodology/geography/ukgeographies/censusgeography  # noqa
UK_POPULATION_2017 = 66040000  # 2017 figure, 66.04m


class FuzzyDefaults:
    """
    Some configuration defaults.
    """

    # -------------------------------------------------------------------------
    # Filenames
    # -------------------------------------------------------------------------
    _appname = "crate"
    if EnvVar.GENERATING_CRATE_DOCS in os.environ:
        DEFAULT_CACHE_DIR = "/path/to/crate/user/data"
        POSTCODES_CSV = "/path/to/postcodes/file"
        N_PROCESSES = 8
    else:
        DEFAULT_CACHE_DIR = os.path.join(
            appdirs.user_data_dir(appname=_appname)
        )
        POSTCODES_CSV = os.path.abspath(
            os.path.expanduser(
                "~/dev/ons/ONSPD_Nov2019/unzipped/Data/ONSPD_NOV_2019_UK.csv"
            )
        )
        N_PROCESSES = cpu_count()
    FORENAME_CACHE_FILENAME = os.path.join(
        DEFAULT_CACHE_DIR, "fuzzy_forename_cache.pickle"
    )
    FORENAME_SEX_FREQ_CSV = os.path.join(
        DEFAULT_CACHE_DIR, "us_forename_sex_freq.csv"
    )
    POSTCODE_CACHE_FILENAME = os.path.join(
        DEFAULT_CACHE_DIR, "fuzzy_postcode_cache.pickle"
    )
    SURNAME_CACHE_FILENAME = os.path.join(
        DEFAULT_CACHE_DIR, "fuzzy_surname_cache.pickle"
    )
    SURNAME_FREQ_CSV = os.path.join(DEFAULT_CACHE_DIR, "us_surname_freq.csv")

    # -------------------------------------------------------------------------
    # Hashing
    # -------------------------------------------------------------------------
    HASH_KEY = "fuzzy_id_match_default_hash_key_DO_NOT_USE_FOR_LIVE_DATA"

    # -------------------------------------------------------------------------
    # Performance
    # -------------------------------------------------------------------------
    MAX_CHUNKSIZE = 500
    MIN_PROBANDS_FOR_PARALLEL = 100
    # ... a machine that takes ~30s to set up a basic parallel run (and 107.9s
    # for a 10k-to-10k comparison) processes single results at about 37/s... so
    # the break-even point is probably around 1000. But that does depend on the
    # sample size too. Call it 100 just to speed up short tests.

    # -------------------------------------------------------------------------
    # Priors/error rates/rouding
    # -------------------------------------------------------------------------
    # See help below.
    BIRTH_YEAR_PSEUDO_RANGE = 90
    MEAN_OA_POPULATION = UK_MEAN_OA_POPULATION_2011
    NAME_MIN_FREQ = 5e-6
    P_FEMALE_GIVEN_MALE_OR_FEMALE = 0.51
    P_GENDER_ERROR = 0.0001
    P_MIDDLE_NAME_N_PRESENT = (0.8, 0.1375)
    P_MINOR_FORENAME_ERROR = 0.001
    P_MINOR_POSTCODE_ERROR = 0.001
    P_MINOR_SURNAME_ERROR = 0.001
    P_NOT_MALE_OR_FEMALE = 0.004
    P_PROBAND_MIDDLE_NAME_MISSING = 0.05
    P_SAMPLE_MIDDLE_NAME_MISSING = 0.05
    POPULATION_SIZE = UK_POPULATION_2017
    ROUNDING_SF = 5
    # ... number of significant figures for frequency rounding; 3 may be too
    # small, e.g. surname Smith 0.01006, corresponding metaphone SM0
    # 0.010129999999999998 would be the same at 3sf.

    # -------------------------------------------------------------------------
    # Matching process
    # -------------------------------------------------------------------------
    MIN_P_FOR_MATCH = 0.999
    LOG_ODDS_FOR_MATCH = log_odds_from_probability(MIN_P_FOR_MATCH)
    EXCEEDS_NEXT_BEST_LOG_ODDS = 10


# =============================================================================
# Hashing
# =============================================================================

Hasher = HmacSHA256Hasher


# =============================================================================
# Metaphones
# =============================================================================

dmeta = DMetaphone()


# =============================================================================
# Caching
# =============================================================================


def cache_load(filename: str) -> Any:
    """
    Reads from a cache.

    Args:
        filename: cache filename (pickle format)

    Returns:
        the result

    Raises:
        :exc:`FileNotFoundError` if it doesn't exist.

    See
    https://stackoverflow.com/questions/82831/how-do-i-check-whether-a-file-exists-without-exceptions

    """  # noqa
    assert filename
    try:
        log.info(f"Reading from cache: {filename}")
        result = pickle.load(open(filename, "rb"))
        log.info("... done")
        return result
    except FileNotFoundError:
        log.info("... cache not found")
        raise


def cache_save(filename: str, data: Any) -> None:
    """
    Writes to a cache.

    Args:
        filename: cache filename (pickle format)
        data: data to write
    """
    assert filename
    log.info(f"Saving to cache: {filename}")
    pickle.dump(data, open(filename, "wb"), protocol=pickle.HIGHEST_PROTOCOL)
    log.info("... done")


# =============================================================================
# String manipulation
# =============================================================================

ISO_DATE_REGEX = re.compile(
    r"[1-9][0-9][0-9][0-9]-(?:1[0-2]|0[1-9])-(?:3[01]|0[1-9]|[12][0-9])"
)  # YYYY-MM-DD
POSTCODE_REGEX = re.compile(
    get_uk_postcode_regex_string(at_word_boundaries_only=False)
)
REMOVE_PUNCTUATION_SPACE_TABLE = str.maketrans("", "", string.punctuation)
REMOVE_PUNCTUATION_SPACE_TABLE[ord(" ")] = None  # also remove spaces


def standardize_name(name: str) -> str:
    """
    Converts names to a standard form: upper case, no spaces, no punctuation.

    Examples:

    .. code-block:: python

        from crate_anon.tools.fuzzy_id_match import *
        standardize_name("Alice")
        standardize_name("Mary Ellen")
        standardize_name("D'Souza")
        standardize_name("de Clérambault")
    """
    return mangle_unicode_to_ascii(
        name.upper().translate(REMOVE_PUNCTUATION_SPACE_TABLE)
    )


def get_metaphone(x: str) -> str:
    """
    Returns a string representing a metaphone of the string -- specifically,
    the first (primary) part of a Double Metaphone.

    See

    - https://www.b-eye-network.com/view/1596
    - https://dl.acm.org/citation.cfm?id=349132

    The implementation is from https://pypi.org/project/Fuzzy/.

    Alternatives (soundex, NYSIIS) are in ``fuzzy`` and also in ``jellyfish``
    (https://jellyfish.readthedocs.io/en/latest/).

    .. code-block:: python

        from crate_anon.tools.fuzzy_id_match import *
        get_metaphone("Alice")  # ALK
        get_metaphone("Alec")  # matches Alice; ALK
        get_metaphone("Mary Ellen")  # MRLN
        get_metaphone("D'Souza")  # TSS
        get_metaphone("de Clerambault")  # TKRM; won't do accents

    """
    if not x:
        return ""
    metaphones = dmeta(x)
    first_part = metaphones[0]  # the first part only
    if first_part is None:
        log.warning(f"No metaphone for {x!r}; dmeta() returned {metaphones}")
        return ""
    return first_part.decode("ascii")


def standardize_postcode(postcode_unit_or_sector: str) -> str:
    """
    Standardizes postcodes to "no space" format.
    """
    return postcode_unit_or_sector.translate(REMOVE_PUNCTUATION_SPACE_TABLE)


def get_postcode_sector(postcode_unit: str) -> str:
    """
    Returns the postcode sector from a postcode. For example, converts "AB12
    3CD" to "AB12 3".
    """
    return postcode_unit[:-2]


# =============================================================================
# Functions to introduce errors (for testing)
# =============================================================================


def mutate_name(name: str) -> str:
    """
    Introduces typos into a (standardized, capitalized,
    no-space-no-punctuation) name.
    """
    n = len(name)
    a = ord("A")
    z = ord("Z")
    which = random.randrange(n)
    start_ord = ord(name[which])
    while True:
        replacement_ord = random.randint(a, z)
        if replacement_ord != start_ord:
            break
    return (
        name[:which] + chr(replacement_ord) + name[which + 1 :]  # noqa: E203
    )


def mutate_postcode(postcode: str, cfg: "MatchConfig") -> str:
    """
    Introduces typos into a UK postcode, keeping the letter/digit format.

    Args:
        postcode: the postcode to alter
        cfg: the master :class:`MatchConfig` object
    """
    n = len(postcode)
    a = ord("A")
    z = ord("Z")
    zero = ord("0")
    nine = ord("9")
    while True:
        while True:
            which = random.randrange(n)
            if postcode[which] != " ":
                break
        # noinspection PyUnboundLocalVariable
        start_ord = ord(postcode[which])
        replacement_ord = start_ord
        if postcode[which].isdigit():
            while replacement_ord == start_ord:
                replacement_ord = random.randint(zero, nine)
        else:
            while replacement_ord == start_ord:
                replacement_ord = random.randint(a, z)
        mutated = (
            postcode[:which]
            + chr(replacement_ord)
            + postcode[which + 1 :]  # noqa: E203
        )
        if cfg.is_valid_postcode(mutated):
            return mutated


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
        self.identifier = identifier
        self.start_date = start_date
        self.end_date = end_date
        if start_date and end_date:
            assert start_date <= end_date

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
        Returns :math:`P(D | H)`, the probability of the observed data given
        the hypothesis of a match.
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
        p_d_given_h = self.p_d_given_h
        if p_d_given_h == 0:
            # Shortcut, since P(H | D) must be 0 (since likelihood ratio is 0):
            return MINUS_INFINITY
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
        if CHECK_ASSERTIONS_IN_HIGH_SPEED_FUNCTIONS:
            assert 0 <= p_d_given_same_person <= 1
            assert 0 <= p_d_given_diff_person <= 1
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
        if CHECK_ASSERTIONS_IN_HIGH_SPEED_FUNCTIONS:
            assert 0 <= p_match_given_same_person <= 1
            assert 0 <= p_match_given_diff_person <= 1
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
        if CHECK_ASSERTIONS_IN_HIGH_SPEED_FUNCTIONS:
            assert (
                p_p >= p_f
            ), f"p_p={p_p}, p_f={p_f}, but should have p_p >= p_f"
            assert 0 <= p_f <= 1
            assert 0 <= p_e <= 1
            assert 0 <= p_p <= 1
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


def bayes_compare(
    prior_log_odds: float,
    comparisons: Iterable[Optional[Comparison]],
    debug: bool = False,
) -> float:
    """
    Works through multiple comparisons and returns posterior log odds.
    Ignore comparisons that are ``None``.

    Args:
        prior_log_odds: prior log odds
        comparisons: an iterable of :class:`Comparison` objects
        debug: be verbose?

    Returns:
        float: posterior log odds
    """
    log_odds = prior_log_odds
    for comparison in comparisons:
        if comparison is None:
            continue
        next_log_odds = comparison.posterior_log_odds(log_odds)
        if debug:
            if next_log_odds > log_odds:
                change = "more likely"
            elif next_log_odds < log_odds:
                change = "less likely"
            else:
                change = "no change"
            log.debug(
                f"{comparison}: " f"{log_odds} -> {next_log_odds} ({change})"
            )
        log_odds = next_log_odds
        if log_odds == MINUS_INFINITY:
            break
    return log_odds


# =============================================================================
# NameFrequencyInfo
# =============================================================================


class NameFrequencyInfo(object):
    """
    Holds frequencies of a class of names (e.g. first names or surnames), and
    also of their hashed versions.
    """

    def __init__(
        self,
        csv_filename: str,
        cache_filename: str,
        by_gender: bool = False,
        min_frequency: float = 5e-6,
    ) -> None:
        """
        Initializes the object from a CSV file.

        Args:
            csv_filename:
                CSV file, with no header, of "name, frequency" pairs.
            cache_filename:
                File in which to cache information, for faster loading.
            by_gender:
                read, split, and key by gender as well as name
            min_frequency:
                minimum frequency to allow; see command-line help.
        """
        assert csv_filename and cache_filename
        self._csv_filename = csv_filename
        self._cache_filename = cache_filename
        self._min_frequency = min_frequency
        self._name_freq = {}  # type: Dict[Union[str, Tuple[str, str]], float]
        self._metaphone_freq = (
            {}
        )  # type: Dict[Union[str, Tuple[str, str]], float]  # noqa
        self._by_gender = by_gender

        try:
            self._name_freq, self._metaphone_freq = cache_load(cache_filename)
            for d in [self._name_freq, self._metaphone_freq]:
                keytype = tuple if by_gender else str
                for k in d.keys():
                    assert isinstance(k, keytype), (
                        f"Cache file {cache_filename!r} has the wrong key "
                        f"type (is {type(k)}, should be {keytype}. "
                        f"Please delete this file and try again."
                    )
        except FileNotFoundError:
            log.info(f"Reading file: {csv_filename}")
            # For extra speed:
            name_freq = self._name_freq
            metaphone_freq = self._metaphone_freq
            # Load
            with open(csv_filename, "rt") as f:
                csvreader = csv.reader(f)
                for row in csvreader:
                    name = standardize_name(row[0])
                    if by_gender:
                        gender = row[1]
                        freq_str = row[2]
                    else:
                        freq_str = row[1]
                    freq = max(float(freq_str), min_frequency)
                    metaphone = get_metaphone(name)
                    if by_gender:
                        name_key = name, gender
                        metaphone_key = metaphone, gender
                    else:
                        name_key = name
                        metaphone_key = metaphone
                    name_freq[name_key] = freq
                    # https://stackoverflow.com/questions/12992165/python-dictionary-increment  # noqa
                    metaphone_freq[metaphone_key] = (
                        metaphone_freq.get(metaphone_key, 0) + freq
                    )
            log.info("... done")
            # Save to cache
            cache_save(cache_filename, [name_freq, metaphone_freq])

    def name_frequency(
        self, name: str, gender: str = "", prestandardized: bool = True
    ) -> float:
        """
        Returns the frequency of a name.

        Args:
            name: the name to check
            gender: the gender, if created with ``by_gender=True``
            prestandardized: was the name pre-standardized in format?

        Returns:
            the name's frequency in the population
        """
        if not prestandardized:
            name = standardize_name(name)
        key = (name, gender) if self._by_gender else name
        # Note operator precedence! Do NOT do this:
        # key = name, gender if self._by_gender else name
        return self._name_freq.get(key, self._min_frequency)

    def metaphone_frequency(self, metaphone: str, gender: str = "") -> float:
        """
        Returns the frequency of a metaphone
        """
        key = (metaphone, gender) if self._by_gender else metaphone
        # ... as above!
        return self._metaphone_freq.get(key, self._min_frequency)


# =============================================================================
# PostcodeFrequencyInfo
# =============================================================================


class PostcodeFrequencyInfo(object):
    """
    Holds frequencies of a class of names (e.g. first names or surnames), and
    also of their hashed versions.
    """

    def __init__(
        self,
        csv_filename: str,
        cache_filename: str,
        mean_oa_population: float = FuzzyDefaults.MEAN_OA_POPULATION,
    ) -> None:
        """
        Initializes the object from a CSV file.

        Args:
            csv_filename:
                CSV file from the UK Office of National Statistics, usually
                ``ONSPD_MAY_2016_UK.csv``. Columns include "pdcs" (one of the
                postcode formats) and "oa11" (Output Area from the 2011
                Census).
            cache_filename:
                Filename to hold pickle format cached data, because the CSV
                read process is slow (it's a 1.4 Gb CSV).
            mean_oa_population:
                Mean population of each census Output Area.
        """
        assert csv_filename and cache_filename
        self._csv_filename = csv_filename
        self._cache_filename = cache_filename
        self._mean_oa_population = mean_oa_population

        self._postcode_unit_freq = {}  # type: Dict[str, float]
        self._postcode_sector_freq = {}  # type: Dict[str, float]
        self._total_population = 0

        try:
            (
                self._postcode_unit_freq,
                self._postcode_sector_freq,
                self._total_population,
            ) = cache_load(cache_filename)
        except FileNotFoundError:
            log.info(f"Reading file: {csv_filename}")
            oa_unit_counter = Counter()
            unit_to_oa = {}  # type: Dict[str, str]
            sector_to_oas = {}  # type: Dict[str, Set[str]]

            # Load data
            report_every = 10000
            with open(csv_filename, "rt") as f:
                csvreader = csv.DictReader(f)
                for rownum, row in enumerate(csvreader, start=1):
                    unit = standardize_postcode(row["pcds"])
                    sector = get_postcode_sector(unit)
                    oa = row["oa11"]
                    if rownum % report_every == 0:
                        log.debug(
                            f"Row# {rownum}: postcode unit {unit}, "
                            f"postcode sector {sector}, Output Area {oa}"
                        )

                    unit_to_oa[unit] = oa
                    oa_unit_counter[oa] += 1  # one more unit for this OA
                    if sector in sector_to_oas:
                        sector_to_oas[sector].add(oa)
                    else:
                        sector_to_oas[sector] = {oa}
            log.info("... done")

            # Calculate
            log.info("Calculating population frequencies for postcodes...")
            unit_freq = self._postcode_unit_freq
            sector_freq = self._postcode_sector_freq
            n_oas = len(oa_unit_counter)
            log.info(f"Number of Output Areas: {n_oas}")
            self._total_population = n_oas * mean_oa_population
            log.info(f"Calculated total population: {self._total_population}")
            for unit, oa in unit_to_oa.items():
                n_units_in_this_oa = oa_unit_counter[oa]
                unit_population = mean_oa_population / n_units_in_this_oa
                unit_freq[unit] = unit_population / self._total_population
            for sector, oas in sector_to_oas.items():
                n_oas_in_this_sector = len(oas)
                sector_population = mean_oa_population * n_oas_in_this_sector
                sector_freq[sector] = (
                    sector_population / self._total_population
                )  # noqa
            log.info("... done")
            # Save to cache
            cache_save(
                cache_filename,
                [unit_freq, sector_freq, self._total_population],
            )

    def postcode_unit_frequency(
        self, postcode_unit: str, prestandardized: bool = False
    ) -> float:
        """
        Returns the frequency of a name.

        Args:
            postcode_unit: the postcode unit to check
            prestandardized: was the postcode pre-standardized in format?

        Returns:
            the name's frequency in the population
        """
        stpu = (
            postcode_unit
            if prestandardized
            else standardize_postcode(postcode_unit)
        )
        try:
            return self._postcode_unit_freq[stpu]
        except KeyError:
            raise ValueError(f"Unknown postcode: {postcode_unit}")

    def postcode_sector_frequency(
        self, postcode_sector: str, prestandardized: bool = False
    ) -> float:
        """
        Returns the frequency of a postcode sector.
        """
        stps = (
            postcode_sector
            if prestandardized
            else standardize_postcode(postcode_sector)
        )
        return self._postcode_sector_freq[stps]

    def is_valid_postcode(self, postcode_unit: str) -> bool:
        """
        Is this a valid postcode?
        """
        return postcode_unit in self._postcode_unit_freq

    def postcode_unit_population(
        self, postcode_unit: str, prestandardized: bool = False
    ) -> float:
        """
        Returns the calculated population of a postcode unit.

        Args:
            postcode_unit: the postcode unit to check
            prestandardized: was the postcode pre-standardized in format?
        """
        stpu = (
            postcode_unit
            if prestandardized
            else standardize_postcode(postcode_unit)
        )
        return self.postcode_unit_frequency(stpu) * self._total_population

    def postcode_sector_population(
        self, postcode_sector: str, prestandardized: bool = False
    ) -> float:
        """
        Returns the calculated population of a postcode sector.

        Args:
            postcode_sector: the postcode sector to check
            prestandardized: was the postcode pre-standardized in format?
        """
        stps = (
            postcode_sector
            if prestandardized
            else standardize_postcode(postcode_sector)
        )
        return self.postcode_sector_frequency(stps) * self._total_population


# =============================================================================
# Main configuration class, supporting frequency-based probability calculations
# =============================================================================


class MatchConfig(object):
    """
    Master config class. It's more convenient to pass one of these round than
    lots of its components.

    Default arguments are there for testing.
    """

    def __init__(
        self,
        hash_key: str = FuzzyDefaults.HASH_KEY,
        rounding_sf: int = FuzzyDefaults.ROUNDING_SF,
        forename_sex_csv_filename: str = FuzzyDefaults.FORENAME_SEX_FREQ_CSV,
        forename_cache_filename: str = FuzzyDefaults.FORENAME_CACHE_FILENAME,
        surname_csv_filename: str = FuzzyDefaults.SURNAME_FREQ_CSV,
        surname_cache_filename: str = FuzzyDefaults.SURNAME_CACHE_FILENAME,
        min_name_frequency: float = FuzzyDefaults.NAME_MIN_FREQ,
        p_middle_name_n_present: List[float] = (
            FuzzyDefaults.P_MIDDLE_NAME_N_PRESENT
        ),
        population_size: int = FuzzyDefaults.POPULATION_SIZE,
        birth_year_pseudo_range: float = FuzzyDefaults.BIRTH_YEAR_PSEUDO_RANGE,
        postcode_csv_filename: str = FuzzyDefaults.POSTCODES_CSV,
        postcode_cache_filename: str = FuzzyDefaults.POSTCODE_CACHE_FILENAME,
        mean_oa_population: float = FuzzyDefaults.MEAN_OA_POPULATION,
        min_log_odds_for_match: float = FuzzyDefaults.LOG_ODDS_FOR_MATCH,
        exceeds_next_best_log_odds: float = (
            FuzzyDefaults.EXCEEDS_NEXT_BEST_LOG_ODDS
        ),
        p_minor_forename_error: float = FuzzyDefaults.P_MINOR_FORENAME_ERROR,
        p_minor_surname_error: float = FuzzyDefaults.P_MINOR_SURNAME_ERROR,
        p_proband_middle_name_missing: float = (
            FuzzyDefaults.P_PROBAND_MIDDLE_NAME_MISSING
        ),
        p_sample_middle_name_missing: float = (
            FuzzyDefaults.P_SAMPLE_MIDDLE_NAME_MISSING
        ),
        p_minor_postcode_error: float = FuzzyDefaults.P_MINOR_POSTCODE_ERROR,
        p_gender_error: float = FuzzyDefaults.P_GENDER_ERROR,
        p_not_male_or_female: float = FuzzyDefaults.P_NOT_MALE_OR_FEMALE,
        p_female_given_male_or_female: float = (
            FuzzyDefaults.P_FEMALE_GIVEN_MALE_OR_FEMALE
        ),
        verbose: bool = False,
    ) -> None:
        """
        Args:
            hash_key:
                Key (passphrase) for hasher.
            rounding_sf:
                Number of significant figures to use when rounding frequency
                information in hashed copies.
            forename_sex_csv_filename:
                Forename frequencies. CSV file, with no header, of "name,
                frequency" pairs.
            forename_cache_filename:
                File in which to cache forename information for faster loading.
            surname_csv_filename:
                Surname frequencies. CSV file, with no header, of "name,
                frequency" pairs.
            surname_cache_filename:
                File in which to cache forename information for faster loading.
            min_name_frequency:
                minimum name frequency; see command-line help.
            p_middle_name_n_present:
                List of probabilities. The first is P(middle name 1 present).
                The second is P(middle name 2 present | middle name 1 present),
                and so on. The last value is re-used ad infinitum as required.
            population_size:
                The size of the entire population (not our sample). See
                docstrings above.
            birth_year_pseudo_range:
                b, such that P(two people share a DOB) = 1/(365.25 * b).
            postcode_csv_filename:
                Postcode mapping. CSV file. Special format; see
                :class:`PostcodeFrequencyInfo`.
            postcode_cache_filename:
                File in which to cache postcode information for faster loading.
            mean_oa_population:
                the mean population of a UK Census Output Area
            min_log_odds_for_match:
                minimum log odds of a match, to consider two people a match
            exceeds_next_best_log_odds:
                In a multi-person comparison, the log odds of the best match
                must exceed those of the next-best match by this much for the
                best to be considered a unique winner.
            p_minor_forename_error:
                Probability that a forename fails a full match but passes a
                partial match.
            p_minor_surname_error:
                Probability that a surname fails a full match but passes a
                partial match.
            p_proband_middle_name_missing:
                Probability that a middle name, present in the sample, is
                missing from the proband.
            p_sample_middle_name_missing:
                Probability that a middle name, present in the proband, is
                missing from the sample.
            p_minor_postcode_error:
                Probability that a postcode fails a full match but passes a
                partial match.
            p_gender_error:
                Probability that a gender match fails because of a data
                error.
            p_not_male_or_female:
                Probability that a person in the population has gender 'X'.
            p_female_given_male_or_female:
                Probability that a person in the population is female, given
                that they are either male or female.

            verbose:
                Be verbose?
        """
        # Probabilities
        assert all(0 <= x <= 1 for x in p_middle_name_n_present)
        assert 0 <= p_minor_forename_error <= 1
        assert 0 <= p_minor_surname_error <= 1
        assert 0 <= p_proband_middle_name_missing <= 1
        assert 0 <= p_sample_middle_name_missing <= 1
        assert 0 <= p_minor_postcode_error <= 1
        assert 0 <= p_gender_error <= 1
        assert 0 <= p_not_male_or_female <= 1
        assert 0 <= p_female_given_male_or_female <= 1

        # Other checks
        assert population_size > 0
        assert birth_year_pseudo_range > 0

        if verbose:
            log.debug("Building MatchConfig...")

        self.hasher = Hasher(hash_key)
        self.rounding_sf = rounding_sf
        self.forename_csv_filename = forename_sex_csv_filename
        self.surname_csv_filename = surname_csv_filename
        self.min_name_frequency = min_name_frequency
        self.p_middle_name_n_present = p_middle_name_n_present
        self.population_size = population_size
        self.birth_year_pseudo_range = birth_year_pseudo_range
        self.min_log_odds_for_match = min_log_odds_for_match
        self.exceeds_next_best_log_odds = exceeds_next_best_log_odds
        self.p_minor_forename_error = p_minor_forename_error
        self.p_minor_surname_error = p_minor_surname_error
        self.p_proband_middle_name_missing = p_proband_middle_name_missing
        self.p_sample_middle_name_missing = p_sample_middle_name_missing
        self.p_minor_postcode_error = p_minor_postcode_error
        self.verbose = verbose

        self.p_gender_error = p_gender_error
        self.p_not_male_or_female = p_not_male_or_female
        p_male_or_female = 1 - p_not_male_or_female
        self.p_female = p_female_given_male_or_female * p_male_or_female
        self.p_male = p_male_or_female - self.p_female

        self._forename_freq = NameFrequencyInfo(
            csv_filename=forename_sex_csv_filename,
            cache_filename=forename_cache_filename,
            min_frequency=min_name_frequency,
            by_gender=True,
        )
        self._surname_freq = NameFrequencyInfo(
            csv_filename=surname_csv_filename,
            cache_filename=surname_cache_filename,
            min_frequency=min_name_frequency,
            by_gender=False,
        )
        self._postcode_freq = PostcodeFrequencyInfo(
            csv_filename=postcode_csv_filename,
            cache_filename=postcode_cache_filename,
            mean_oa_population=mean_oa_population,
        )

        self.p_two_people_share_dob = 1 / (
            DAYS_PER_YEAR * birth_year_pseudo_range
        )

        if verbose:
            log.debug("... MatchConfig built")

    # -------------------------------------------------------------------------
    # Baseline priors
    # -------------------------------------------------------------------------

    @property
    def baseline_log_odds_same_person(self) -> float:
        """
        Returns the log odds that a proband randomly selected from the
        population matches a SPECIFIC person in our sample.
        """
        return log_odds_from_1_in_n(self.population_size)

    # -------------------------------------------------------------------------
    # Identifier frequency information
    # -------------------------------------------------------------------------

    def mean_across_genders(self, value_f: float, value_m: float) -> float:
        """
        Given frequencies for M and F, return the population mean.

        Args:
            value_f: female value
            value_m: male value
        """
        return value_f * self.p_female + value_m * self.p_male

    def forename_freq(
        self, name: str, gender: str, prestandardized: bool = False
    ) -> float:
        """
        Returns the baseline frequency of a forename.

        Args:
            name: the name to check
            gender: the gender to look up for
            prestandardized: was the name pre-standardized?
        """
        if not prestandardized:
            name = standardize_name(name)
        if gender in (GENDER_MALE, GENDER_FEMALE):
            freq = self._forename_freq.name_frequency(
                name, gender, prestandardized=True
            )
        else:
            freq_f = self._forename_freq.name_frequency(
                name, GENDER_FEMALE, prestandardized=True
            )
            freq_m = self._forename_freq.name_frequency(
                name, GENDER_MALE, prestandardized=True
            )
            freq = self.mean_across_genders(freq_f, freq_m)
        if self.verbose:
            log.debug(
                f"    Forename frequency for {name}, gender {gender!r}: "
                f"{freq}"
            )
        return freq

    def forename_metaphone_freq(self, metaphone: str, gender: str) -> float:
        """
        Returns the baseline frequency of a forename's metaphone.

        Args:
            metaphone: the metaphone to check
            gender: the gender to look up for
        """
        if gender in (GENDER_MALE, GENDER_FEMALE):
            freq = self._forename_freq.metaphone_frequency(metaphone, gender)
        else:
            freq_f = self._forename_freq.metaphone_frequency(
                metaphone, GENDER_FEMALE
            )
            freq_m = self._forename_freq.metaphone_frequency(
                metaphone, GENDER_MALE
            )
            freq = self.mean_across_genders(freq_f, freq_m)
        if self.verbose:
            log.debug(
                f"    Forename metaphone frequency for {metaphone}, "
                f"gender {gender!r}: {freq}"
            )
        return freq

    def p_middle_name_present(self, n: int) -> float:
        """
        Returns the probability (in the population) that someone has a middle
        name n, given that they have middle name n - 1.

        (For example, n = 1 gives the probability of having a middle name; n =
        2 is the probability of having a second middle name, given that you
        have a first middle name.)
        """
        if CHECK_ASSERTIONS_IN_HIGH_SPEED_FUNCTIONS:
            assert n >= 1
        if not self.p_middle_name_n_present:
            return 0
        if n > len(self.p_middle_name_n_present):
            return self.p_middle_name_n_present[-1]
        return self.p_middle_name_n_present[n - 1]

    def surname_freq(self, name: str, prestandardized: bool = False) -> float:
        """
        Returns the baseline frequency of a surname.

        Args:
            name: the name to check
            prestandardized: was it pre-standardized?
        """
        freq = self._surname_freq.name_frequency(
            name, prestandardized=prestandardized
        )
        if self.verbose:
            log.debug(f"    Surname frequency for {name}: {freq}")
        return freq

    def surname_metaphone_freq(self, metaphone: str) -> float:
        """
        Returns the baseline frequency of a surname's metaphone.

        Args:
            metaphone: the metaphone to check
        """
        freq = self._surname_freq.metaphone_frequency(metaphone)
        if self.verbose:
            log.debug(
                f"    Surname metaphone frequency for {metaphone}: " f"{freq}"
            )
        return freq

    def gender_freq(self, gender: str) -> Optional[float]:
        if not gender:
            return None
        elif gender == GENDER_FEMALE:
            return self.p_female
        elif gender == GENDER_MALE:
            return self.p_male
        else:
            return self.p_not_male_or_female

    def is_valid_postcode(self, postcode_unit: str) -> bool:
        """
        Is this a valid postcode?
        """
        return self._postcode_freq.is_valid_postcode(postcode_unit)

    def postcode_unit_freq(
        self, postcode_unit: str, prestandardized: bool = True
    ) -> float:
        """
        Returns the frequency for a full postcode, or postcode unit (the
        proportion of the population who live in that postcode).
        """
        freq = self._postcode_freq.postcode_unit_frequency(
            postcode_unit, prestandardized=prestandardized
        )
        if self.verbose:
            log.debug(f"Postcode unit frequency for {postcode_unit}: {freq}")
        return freq

    def postcode_unit_population(
        self, postcode_unit: str, prestandardized: bool = False
    ) -> float:
        """
        Returns the calculated population of a postcode unit.

        Args:
            postcode_unit: the postcode unit to check
            prestandardized: was the postcode pre-standardized in format?
        """
        return self._postcode_freq.postcode_unit_population(
            postcode_unit, prestandardized=prestandardized
        )

    def postcode_sector_freq(
        self, postcode_sector: str, prestandardized: bool = True
    ) -> float:
        """
        Returns the frequency for a postcode sector; see
        :meth:`postcode_freq`.
        """
        freq = self._postcode_freq.postcode_sector_frequency(
            postcode_sector, prestandardized=prestandardized
        )
        if self.verbose:
            log.debug(
                f"Postcode sector frequency for {postcode_sector}: " f"{freq}"
            )
        return freq

    def postcode_sector_population(
        self, postcode_sector: str, prestandardized: bool = False
    ) -> float:
        """
        Returns the calculated population of a postcode sector.

        Args:
            postcode_sector: the postcode sector to check
            prestandardized: was the postcode pre-standardized in format?
        """
        return self._postcode_freq.postcode_sector_population(
            postcode_sector, prestandardized=prestandardized
        )

    # -------------------------------------------------------------------------
    # Comparisons
    # -------------------------------------------------------------------------

    def person_matches(self, log_odds_match: float) -> bool:
        """
        Decides as to whether two :class:`Person` objects are a sufficient
        match, based on our threshold.

        Args:
            log_odds_match: log odds that they're the same person

        Returns:
            bool: binary decision
        """
        return log_odds_match >= self.min_log_odds_for_match


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
        candidate_id = self.identifier
        proband_id = proband.identifier
        if not candidate_id or not proband_id:
            # Infer no conclusions from missing information.
            return None
        matches = candidate_id == proband_id
        return MatchNoMatchComparison(
            name=self.comparison_name,
            match=matches,
            p_match_given_same_person=proband.p_no_error,
            p_match_given_diff_person=proband.frequency,
        )

    def matches(self, other: "IdFreq") -> bool:
        """
        Is there a match with ``other``?
        """
        self_id = self.identifier
        other_id = other.identifier
        if not (self_id and other_id):
            return False
        return self_id == other_id

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

        if exact_identifier and exact_identifier_frequency is not None:
            assert 0 <= exact_identifier_frequency <= 1
        if fuzzy_identifier and fuzzy_identifier_frequency is not None:
            assert 0 <= fuzzy_identifier_frequency <= 1

    def comparison(self, proband: "FuzzyIdFreq") -> Optional[Comparison]:
        """
        Comparison against a proband's version.
        """
        candidate_exact = self.exact_identifier
        proband_exact = proband.exact_identifier
        if not (candidate_exact and proband_exact):
            # Infer no conclusions from missing information.
            return None
        candidate_fuzzy = self.fuzzy_identifier
        proband_fuzzy = proband.fuzzy_identifier
        if not (candidate_fuzzy and proband_fuzzy):
            # Infer no conclusions from missing information.
            return None
        full_match = candidate_exact == proband_exact
        partial_match = candidate_fuzzy == proband_fuzzy
        return FullPartialNoMatchComparison(
            name=self.comparison_name,
            full_match=full_match,
            p_f=proband.exact_identifier_frequency,
            p_e=self.p_error,
            partial_match=partial_match,
            p_p=proband.fuzzy_identifier_frequency,
        )

    def fully_matches(self, other: "FuzzyIdFreq") -> bool:
        """
        Is there a full match with ``other``?
        """
        self_exact = self.exact_identifier
        other_exact = other.exact_identifier
        if not (self_exact and other_exact):
            return False
        return self_exact == other_exact

    def partially_matches(self, other: "FuzzyIdFreq") -> bool:
        """
        Is there a partial match with ``other``?
        """
        self_fuzzy = self.fuzzy_identifier
        other_fuzzy = other.fuzzy_identifier
        if not (self_fuzzy and other_fuzzy):
            return False
        return self_fuzzy == other_fuzzy

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


# =============================================================================
# Person
# =============================================================================

GENDER_MALE = "M"
GENDER_FEMALE = "F"
GENDER_OTHER = "X"
VALID_GENDERS = ["", GENDER_MALE, GENDER_FEMALE, GENDER_OTHER]
# ... standard three gender codes; "" = missing


class BasePerson:
    """
    Simple information about a person, without frequency calculations.
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
        self.local_id = local_id
        self.other_info = other_info
        self.first_name = first_name
        self.middle_names = middle_names or []
        self.surname = surname
        self.dob = dob
        self.gender = gender
        self.postcodes = postcodes or []

        if standardize:
            self.first_name = standardize_name(self.first_name)
            self.middle_names = [
                standardize_name(x) for x in self.middle_names if x
            ]
            self.surname = standardize_name(self.surname)
            for p in self.postcodes:
                if p.identifier:
                    p.identifier = standardize_postcode(p.identifier)

        assert self.local_id, "Need local_id"
        if self.dob:
            assert ISO_DATE_REGEX.match(dob), f"Bad date: {dob!r}"
        assert self.gender in VALID_GENDERS
        for p in self.postcodes:
            assert POSTCODE_REGEX.match(
                p.identifier
            ), f"Bad postcode: {p.identifier!r}"

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


class Person(BasePerson):
    """
    Represents a person. The information may be incomplete or slightly wrong.
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
                self.postcodes_info.append(
                    FuzzyIdFreq(
                        comparison_name="postcode",
                        exact_identifier=self.hashed_postcode_units[
                            i
                        ].identifier,
                        exact_identifier_frequency=self.postcode_unit_frequencies[  # noqa: E501
                            i
                        ],
                        fuzzy_identifier=self.hashed_postcode_sectors[
                            i
                        ].identifier,
                        fuzzy_identifier_frequency=self.postcode_sector_frequencies[  # noqa: E501
                            i
                        ],
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
                self.middle_names_info.append(
                    FuzzyIdFreq(
                        comparison_name=f"middle_name_{n}",
                        exact_identifier=middle_name,
                        exact_identifier_frequency=cfg.forename_freq(
                            middle_name, self.gender, prestandardized=True
                        ),
                        fuzzy_identifier=middle_name_metaphone,
                        fuzzy_identifier_frequency=cfg.forename_metaphone_freq(
                            middle_name_metaphone, self.gender
                        ),
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
                postcode_unit = self.postcodes[i]
                postcode_sector = get_postcode_sector(postcode_unit.identifier)
                self.postcodes_info.append(
                    FuzzyIdFreq(
                        comparison_name="postcode",
                        exact_identifier=postcode_unit.identifier,
                        exact_identifier_frequency=cfg.postcode_unit_freq(
                            postcode_unit.identifier, prestandardized=True
                        ),
                        fuzzy_identifier=postcode_sector,
                        fuzzy_identifier_frequency=cfg.postcode_sector_freq(
                            postcode_sector, prestandardized=True
                        ),
                        p_error=cfg.p_minor_postcode_error,
                    )
                )

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
        _hash = cfg.hasher.hash  # hashing function
        _postcode_unit_freq = cfg.postcode_unit_freq
        _postcode_sector_freq = cfg.postcode_sector_freq
        _forename_freq = cfg.forename_freq
        _forename_metaphone_freq = cfg.forename_metaphone_freq

        def fr(f: float, sf: int = cfg.rounding_sf) -> float:
            """
            Rounds frequencies to a certain number of significant figures.
            (Don't supply exact floating-point numbers for frequencies; may be
            more identifying. Don't use decimal places; we have to deal with
            some small numbers.)
            """
            return round_sf(f, sf)

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
                hashed_postcode_units.append(
                    p.with_new_identifier(_hash(p.identifier))
                )
                postcode_unit_frequencies.append(
                    fr(_postcode_unit_freq(p.identifier, prestandardized=True))
                )
                sector = get_postcode_sector(p.identifier)
                hashed_postcode_sectors.append(
                    p.with_new_identifier(_hash(sector))
                )
                postcode_sector_frequencies.append(
                    fr(_postcode_sector_freq(sector))
                )

        return Person(
            cfg=cfg,
            is_hashed=True,
            local_id=self.local_id,
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

    def log_odds_same(self, proband: "Person", debug: bool = False) -> float:
        """
        Returns the log odds that ``self`` and ``other`` are the same person.

        Args:
            proband: another :class:`Person` object
            debug: be verbose?

        Returns:
            float: the log odds they're the same person
        """
        if debug:
            log.debug(f"Comparing self={self}; other={proband}")
        return bayes_compare(
            prior_log_odds=self.cfg.baseline_log_odds_same_person,
            comparisons=self._gen_comparisons(proband),
            debug=debug,
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
    def __init__(
        self,
        cfg: MatchConfig,
        verbose: bool = False,
        person: Person = None,
        people: List[Person] = None,
    ) -> None:
        """
        Creates a blank collection.
        """
        self.cfg = cfg
        self.verbose = verbose
        self.people = []  # type: List[Person]
        self.dob_to_people = defaultdict(list)  # type: Dict[str, List[Person]]
        self.hashed_dob_to_people = defaultdict(
            list
        )  # type: Dict[str, List[Person]]  # noqa

        if person:
            self.add_person(person)
        if people:
            self.add_people(people)

    def add_person(self, person: Person) -> None:
        """
        Adds a single person.
        """
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
        for p in self.people:
            p.assert_valid_as_proband()

    def assert_valid_as_sample(self) -> None:
        """
        Ensures all people have sufficient information to act as a candidate
        from a sample, or raises :exc:`AssertionError`.
        """
        for p in self.people:
            p.assert_valid_as_candidate()

    def shortlist(self, proband: Person) -> List[Person]:
        """
        Returns a shortlist of potential candidates, by date of birth.

        Args:
            proband: a :class:`Person`
        """
        if proband.is_hashed:
            hashed_dob = proband.hashed_dob
            if not hashed_dob:
                return []
            return self.hashed_dob_to_people[hashed_dob]
        else:
            dob = proband.dob
            if not dob:
                return []
            return self.dob_to_people[dob]

    def get_unique_match_detailed(self, proband: Person) -> MatchResult:
        """
        Returns a single person matching the proband, or ``None`` if there is
        no match (as defined by the probability settings in ``cfg``).

        Args:
            proband: a :class:`Person`
        """
        verbose = self.verbose

        # 2020-04-25: Do this in one pass.
        # A bit like
        # https://www.geeksforgeeks.org/python-program-to-find-second-largest-number-in-a-list/  # noqa
        # ... but modified, as that fails to deal with joint winners
        # ... and it's not a super algorithm anyway.

        # Step 1. Scan everything in a single pass, establishing the winner
        # and the runner-up.
        # log.info("hello")
        cfg = self.cfg
        best_idx = -1
        second_best_idx = -1
        best_log_odds = MINUS_INFINITY
        second_best_log_odds = MINUS_INFINITY
        shortlist = self.shortlist(proband)
        if verbose:
            txt_shortlist = "; ".join(str(x) for x in shortlist)
            log.debug(
                f"Proband: {proband}. Sample size: {len(self.people)}. "
                f"Shortlist ({len(shortlist)}): {txt_shortlist}"
            )
        for idx, candidate in enumerate(shortlist):
            log_odds = candidate.log_odds_same(proband)
            if log_odds > best_log_odds:
                second_best_log_odds = best_log_odds
                second_best_idx = best_idx
                best_idx = idx
                best_log_odds = log_odds
            elif log_odds > second_best_log_odds:
                second_best_idx = idx
                second_best_log_odds = log_odds

        result = MatchResult(
            best_log_odds=best_log_odds,
            second_best_log_odds=second_best_log_odds,
            best_candidate=shortlist[best_idx] if best_idx >= 0 else None,
            second_best_candidate=(
                shortlist[second_best_idx] if second_best_idx >= 0 else None
            ),
            proband=proband,
        )
        result.winner = result.best_candidate

        if not result.winner:
            if verbose:
                log.debug("No candidates")

        # Step 2: is the best good enough?
        elif best_log_odds < cfg.min_log_odds_for_match:
            if verbose:
                log.debug("Best is not good enough")
            result.winner = None

        # Step 3: is the runner-up too close, so we have >1 match and cannot
        # decide with sufficient confidence (so must reject)?
        elif (
            best_log_odds
            < second_best_log_odds + cfg.exceeds_next_best_log_odds
        ):  # noqa
            if verbose:
                log.debug("Second-best is too close to best")
            result.winner = None

        # Step 4: clear-enough winner found.
        elif verbose:
            log.debug("Found a winner")

        if verbose:
            log.debug(repr(result))
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
# Comparing people
# =============================================================================


class ComparisonOutputColnames:
    PROBAND_LOCAL_ID = "proband_local_id"
    MATCHED = "matched"
    LOG_ODDS_MATCH = "log_odds_match"
    P_MATCH = "p_match"
    SAMPLE_MATCH_LOCAL_ID = "sample_match_local_id"
    SECOND_BEST_LOG_ODDS = "second_best_log_odds"

    BEST_CANDIDATE_LOCAL_ID = "best_candidate_local_id"

    COMPARISON_OUTPUT_COLNAMES = [
        PROBAND_LOCAL_ID,
        MATCHED,
        LOG_ODDS_MATCH,
        P_MATCH,
        SAMPLE_MATCH_LOCAL_ID,
        SECOND_BEST_LOG_ODDS,
    ]
    COMPARISON_EXTRA_COLNAMES = [BEST_CANDIDATE_LOCAL_ID]


def compare_probands_to_sample(
    cfg: MatchConfig,
    probands: People,
    sample: People,
    output_csv: str,
    report_every: int = 100,
    extra_validation_output: bool = False,
    n_workers: int = FuzzyDefaults.N_PROCESSES,
    max_chunksize: int = FuzzyDefaults.MAX_CHUNKSIZE,
    min_probands_for_parallel: int = FuzzyDefaults.MIN_PROBANDS_FOR_PARALLEL,
) -> None:
    r"""
    Compares each proband to the sample. Writes to an output file.

    Args:
        cfg:
            the master :class:`MatchConfig` object.
        probands:
            :class:`People`
        sample:
            :class:`People`
        output_csv:
            output CSV filename
        report_every:
            report progress every n probands
        extra_validation_output:
            Add extra columns to the output for validation purposes?
        n_workers:
            Number of parallel processes to use.
        max_chunksize:
            Maximum chunksize for parallel processing.
        min_probands_for_parallel:
            Minimum number of probands for which we will bother to use parallel
            processing.

    Profiling with 10,000 probands and the exact same people in the sample, on
    Wombat:

    - Start (2020-04-25, 11:52): 52 seconds for the first 1,000 probands.
    - next: 50.99. Not much improvement!
    - multiprocessing didn't help (overheads?)
    - multithreading didn't help (GIL?)
    - we remain at about 25.889 seconds per 400 probands within a
      10k * 10k set (= 15 probands/sec).
    - down to 22.5 seconds with DOB shortlisting, and that is with a highly
      self-similar sample, so that may improve dramatically.
    - retried multithreading with ThreadPoolExecutor: 20.9 seconds for 400,
      compared to 23.58 with single-threading; pretty minimal difference.
    - retried multiprocessing with ProcessPoolExecutor: maybe 2/8 cores at high
      usage at any given time? Not properly profiled.
    - then with multiprocessing.Pool...

      - https://stackoverflow.com/questions/18671528/processpoolexecutor-from-concurrent-futures-way-slower-than-multiprocessing-pool
      - https://helpful.knobs-dials.com/index.php/Python_usage_notes/Multiprocessing_notes
      - slow, but then added ``chunksize = n_probands // n_workers`` (I think
        it's the interprocess communication/setup that is slow)...

      - 147.168 seconds -- but for all 10k rows, so that is equivalent to
        5.88 seconds for 400, and much better.
      - Subsequently reached 111.8 s for 10k probands (and 10k sample),
        for 89 probands/sec.

    - This is an O(n^2) algorithm, in that its time grows linearly with the
      number of probands to check, and with the number of sample members to
      check against -- though on average at 1/(365*b) = 1/32850 the gradient
      for the latter, since we use birthday prefiltering.

    - Different DOB, middle name methods and gender check takes us to
      150.15 s for 10k*10k (2020-05-02). The fake data has lots of DOB overlap
      so real-world performance is likely to be much better.

    - Using generic ID/frequency structures took this down to 130.5s
      (2020-05-02), and some simplification to 124.76s, for 10k*10k.

    .. code-block:: none

        crate_fuzzy_id_match compare_plaintext \
            --probands fuzzy_sample_10k.csv \
            --sample fuzzy_sample_10k.csv \
            --output fuzzy_output_10k.csv

        # to profile, add: --profile --n_workers 1

    """  # noqa

    def process_result(r: MatchResult) -> None:
        # Uses "rownum" and "writer" from outer scope.
        nonlocal rownum
        rownum += 1
        if rownum % report_every == 0:
            log.info(f"Processing result {rownum}/{n_probands}")
        p = r.proband
        w = r.winner
        matched = r.matched
        c = ComparisonOutputColnames
        rowdata = {
            c.PROBAND_LOCAL_ID: p.local_id,
            c.MATCHED: int(matched),
            c.LOG_ODDS_MATCH: r.best_log_odds,
            c.P_MATCH: probability_from_log_odds(r.best_log_odds),
            c.SAMPLE_MATCH_LOCAL_ID: w.local_id if matched else None,
            c.SECOND_BEST_LOG_ODDS: r.second_best_log_odds,
        }
        if extra_validation_output:
            rowdata[c.BEST_CANDIDATE_LOCAL_ID] = (
                r.best_candidate.local_id if r.best_candidate else None
            )
        writer.writerow(rowdata)

    log.info("Validating probands...")
    n_probands = probands.size()
    probands.assert_valid_as_probands()

    log.info("Validating sample...")
    n_sample = sample.size()
    if n_sample > cfg.population_size:
        log.critical(
            f"Sample size exceeds population size of {cfg.population_size}; "
            f"assumptions violated! In particular, the prior probability for "
            f"each candidate is guaranteed to be wrong. Aborting."
        )
        sys.exit(EXIT_FAILURE)
    sample.assert_valid_as_sample()

    log.info(
        f"Comparing each proband to sample. There are "
        f"{n_probands} probands and {n_sample} in the sample."
    )
    parallel = n_workers > 1 and n_probands >= min_probands_for_parallel
    colnames = ComparisonOutputColnames.COMPARISON_OUTPUT_COLNAMES
    if extra_validation_output:
        colnames += ComparisonOutputColnames.COMPARISON_EXTRA_COLNAMES
    rownum = 0
    time_start = time.time()
    with open(output_csv, "wt") as f:
        writer = csv.DictWriter(f, fieldnames=colnames)
        writer.writeheader()

        if parallel:
            chunksize = max(1, min(n_probands // n_workers, max_chunksize))
            # ... chunksize must be >= 1
            log.info(
                f"Using parallel processing with {n_workers} workers and "
                f"chunksize of {chunksize}."
            )

            # This is slow:
            #
            # executor = ProcessPoolExecutor(max_workers=max_workers)
            # for result in executor.map(sample.get_unique_match_detailed,
            #                            probands.people,
            #                            cycle([cfg])):
            #     process_result(result)
            #
            # This doesn't work as you can't pickle a local function:
            #
            # with Pool(processes=n_workers) as pool:
            #     for result in pool.imap_unordered(  # one arg per call
            #             make_result,  # local function
            #             probands.people,
            #             chunksize=chunksize):
            #         process_result(result)
            #
            # This is fine, though it only collects results at the end:
            # with Pool(processes=n_workers) as pool:
            #     for result in pool.starmap(  # many args
            #             sample.get_unique_match_detailed,
            #             zip(probands.people, cycle([cfg])),
            #             chunksize=chunksize):
            #         process_result(result)

            with Pool(processes=n_workers) as pool:
                for result in pool.imap_unordered(  # one arg per call
                    sample.get_unique_match_detailed,
                    probands.people,
                    chunksize=chunksize,
                ):
                    process_result(result)

        else:
            log.info("Not using parallel processing.")
            for rownum, proband in enumerate(probands.people, start=1):
                result = sample.get_unique_match_detailed(proband)
                process_result(result)

    time_end = time.time()
    total_dur = time_end - time_start

    log.info(f"... comparisons done. Time taken: {total_dur} s")


def compare_probands_to_sample_from_csv(
    cfg: MatchConfig,
    probands_csv: str,
    sample_csv: str,
    output_csv: str,
    probands_plaintext: bool = True,
    sample_plaintext: bool = True,
    sample_cache_filename: str = "",
    extra_validation_output: bool = False,
    profile: bool = False,
    n_workers: int = FuzzyDefaults.N_PROCESSES,
    max_chunksize: int = FuzzyDefaults.MAX_CHUNKSIZE,
    min_probands_for_parallel: int = FuzzyDefaults.MIN_PROBANDS_FOR_PARALLEL,
) -> None:
    """
    Compares each of the people in the probands file to the sample file.

    Args:
        cfg:
            the master :class:`MatchConfig` object.
        probands_csv:
            CSV of people (probands); see :func:`read_people`.
        sample_csv:
            CSV of people (sample); see :func:`read_people`.
        output_csv:
            output CSV filename
        sample_cache_filename:
            file in which to cache sample, for speed
        probands_plaintext:
            is the probands file plaintext (not hashed)?
        sample_plaintext:
            is the sample file plaintext (not hashed)?
        extra_validation_output:
            Add extra columns to the output for validation purposes?
        profile:
            profile the code?
        n_workers:
            Number of parallel processes to use.
        max_chunksize:
            Maximum chunksize for parallel processing.
        min_probands_for_parallel:
            Minimum number of probands for which we will bother to use parallel
            processing.
    """
    # Sample
    log.info("Loading (or caching) sample data")
    if sample_plaintext:
        if sample_cache_filename:
            log.info(f"Using sample cache: {sample_cache_filename}")
            try:
                (sample,) = cache_load(sample_cache_filename)
            except FileNotFoundError:
                sample = read_people(cfg, sample_csv)
                cache_save(sample_cache_filename, [sample])
        else:
            # You may want to avoid a cache, for security.
            log.info("No sample cache in use.")
            sample = read_people(cfg, sample_csv)
    else:
        sample = read_people(cfg, sample_csv, plaintext=False)

    # Probands
    log.info("Loading proband data")
    probands = read_people(cfg, probands_csv, plaintext=probands_plaintext)

    # Ensure they are comparable
    if sample_plaintext and not probands_plaintext:
        log.info("Hashing sample...")
        sample = sample.hashed()
        log.info("... done")
    elif probands_plaintext and not sample_plaintext:
        log.warning("Odd: comparing plaintext probands to hashed sample!")
        log.info("Hashing probands...")
        probands = probands.hashed()
        log.info("... done")

    # Compare
    compare_fn = (
        do_cprofile(compare_probands_to_sample, sort="cumtime")
        if profile
        else compare_probands_to_sample
    )
    compare_fn(
        cfg=cfg,
        probands=probands,
        sample=sample,
        output_csv=output_csv,
        extra_validation_output=extra_validation_output,
        n_workers=n_workers,
        max_chunksize=max_chunksize,
        min_probands_for_parallel=min_probands_for_parallel,
    )


# =============================================================================
# Loading people data
# =============================================================================


def read_people_2(
    cfg: MatchConfig,
    csv_filename: str,
    plaintext: bool = True,
    alternate_groups: bool = False,
) -> Tuple[People, People]:
    """
    Read a list of people from a CSV file. See :class:`People` for the
    column details.

    Args:
        cfg:
            Configuration object
        csv_filename:
            filename to read
        plaintext:
            read in plaintext, rather than hashed, format?
        alternate_groups:
            split consecutive people into "first group", "second group"?
            (A debugging/validation feature.)

    Returns:
        tuple: ``first_group``, ``second_group`` (or ``None``)

    """
    log.info(f"Reading file: {csv_filename}")
    assert csv_filename
    a = People(cfg=cfg)
    b = People(cfg=cfg)
    with open(csv_filename, "rt") as f:
        reader = csv.DictReader(f)
        for i, rowdict in enumerate(reader):
            if plaintext:
                person = Person.from_plaintext_csv(cfg, rowdict)
            else:
                person = Person.from_hashed_csv(cfg, rowdict)
            if alternate_groups and i % 2 == 1:
                b.add_person(person)
            else:
                a.add_person(person)
    log.info("... done")
    return a, b


def read_people(
    cfg: MatchConfig, csv_filename: str, plaintext: bool = True
) -> People:
    """
    Read a list of people from a CSV file.

    See :func:`read_people_2`, but this version doesn't offer the feature of
    splitting into two groups, and returns only a single :class:`People`
    object.
    """
    people, _ = read_people_2(
        cfg, csv_filename, plaintext=plaintext, alternate_groups=False
    )
    return people


# =============================================================================
# Hash plaintext to encrypted CSV
# =============================================================================


def hash_identity_file(
    cfg: MatchConfig,
    input_csv: str,
    output_csv: str,
    without_frequencies: bool = False,
    include_other_info: bool = False,
) -> None:
    """
    Hash a file of identifiable people to a hashed version.

    Args:
        cfg:
            The master :class:`MatchConfig` object.
        input_csv:
            Input (plaintext) CSV filename to read.
        output_csv:
            Iutput (hashed) CSV filename to write.
        without_frequencies:
            Do not include frequency information. This makes the resulting file
            suitable for use as a sample, but not as a proband file.
        include_other_info:
            Include the (potentially identifying) ``other_info`` data? Usually
            ``False``; may be ``True`` for validation.
    """
    if include_other_info:
        log.warning("include_other_info is set; use this for validation only")
    with open(input_csv, "rt") as infile, open(output_csv, "wt") as outfile:
        reader = csv.DictReader(infile)
        writer = csv.DictWriter(outfile, fieldnames=Person.HASHED_ATTRS)
        writer.writeheader()
        for inputrow in reader:
            plaintext_person = Person.from_plaintext_csv(cfg, inputrow)
            hashed_person = plaintext_person.hashed()
            writer.writerow(
                hashed_person.hashed_csv_dict(
                    without_frequencies=without_frequencies,
                    include_other_info=include_other_info,
                )
            )


# =============================================================================
# Demonstration data
# =============================================================================


def get_demo_people() -> List[Person]:
    """
    Some demonstration records. All data are fictional. The postcodes are real
    but are institutional, not residential, addresses in Cambridge.
    """
    d = coerce_to_pendulum_date

    def p(postcode: str) -> TemporalIdentifier:
        return TemporalIdentifier(
            identifier=postcode,
            start_date=d("2000-01-01"),
            end_date=d("2010-12-31"),
        )

    def mkother(original_id: str) -> str:
        return json.dumps({"original_id": original_id, "other_info": "?"})

    standardize = False

    return [
        BasePerson(
            local_id="r1",
            other_info=mkother("1"),
            first_name="Alice",
            middle_names=["Zara"],
            surname="Smith",
            dob="1931-01-01",
            gender=GENDER_FEMALE,
            postcodes=[p("CB2 0QQ")],
            standardize=standardize,
        ),
        BasePerson(
            local_id="r2",
            other_info=mkother("2"),
            first_name="Bob",
            middle_names=["Yorick"],
            surname="Jones",
            dob="1932-01-01",
            gender=GENDER_MALE,
            postcodes=[p("CB2 3EB")],
            standardize=standardize,
        ),
        BasePerson(
            local_id="r3",
            other_info=mkother("3"),
            first_name="Celia",
            middle_names=["Xena"],
            surname="Wright",
            dob="1933-01-01",
            gender=GENDER_FEMALE,
            postcodes=[p("CB2 1TP")],
            standardize=standardize,
        ),
        BasePerson(
            local_id="r4",
            other_info=mkother("4"),
            first_name="David",
            middle_names=["William", "Wallace"],
            surname="Cartwright",
            dob="1934-01-01",
            gender=GENDER_MALE,
            postcodes=[p("CB2 8PH"), p("CB2 1TP")],
            standardize=standardize,
        ),
        BasePerson(
            local_id="r5",
            other_info=mkother("5"),
            first_name="Emily",
            middle_names=["Violet"],
            surname="Fisher",
            dob="1935-01-01",
            gender=GENDER_FEMALE,
            postcodes=[p("CB3 9DF")],
            standardize=standardize,
        ),
        BasePerson(
            local_id="r6",
            other_info=mkother("6"),
            first_name="Frank",
            middle_names=["Umberto"],
            surname="Williams",
            dob="1936-01-01",
            gender=GENDER_MALE,
            postcodes=[p("CB2 1TQ")],
            standardize=standardize,
        ),
        BasePerson(
            local_id="r7",
            other_info=mkother("7"),
            first_name="Greta",
            middle_names=["Tilly"],
            surname="Taylor",
            dob="1937-01-01",
            gender=GENDER_FEMALE,
            postcodes=[p("CB2 1DQ")],
            standardize=standardize,
        ),
        BasePerson(
            local_id="r8",
            other_info=mkother("8"),
            first_name="Harry",
            middle_names=["Samuel"],
            surname="Davies",
            dob="1938-01-01",
            gender=GENDER_MALE,
            postcodes=[p("CB3 9ET")],
            standardize=standardize,
        ),
        BasePerson(
            local_id="r9",
            other_info=mkother("9"),
            first_name="Iris",
            middle_names=["Ruth"],
            surname="Evans",
            dob="1939-01-01",
            gender=GENDER_FEMALE,
            postcodes=[p("CB3 0DG")],
            standardize=standardize,
        ),
        BasePerson(
            local_id="r10",
            other_info=mkother("10"),
            first_name="James",
            middle_names=["Quentin"],
            surname="Thomas",
            dob="1940-01-01",
            gender=GENDER_MALE,
            postcodes=[p("CB2 0SZ")],
            standardize=standardize,
        ),
        BasePerson(
            local_id="r11",
            other_info=mkother("11"),
            first_name="Alice",
            middle_names=[],
            surname="Smith",
            dob="1931-01-01",
            gender=GENDER_FEMALE,
            postcodes=[p("CB2 0QQ")],
            standardize=standardize,
        ),
    ]


def get_demo_csv() -> str:
    """
    A demonstration CSV file, as text.
    """
    people = get_demo_people()
    assert len(people) >= 1
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=BasePerson.PLAINTEXT_ATTRS)
    writer.writeheader()
    for person in people:
        writer.writerow(person.plaintext_csv_dict())
    return output.getvalue()


# =============================================================================
# Command-line entry point
# =============================================================================


class Switches:
    """
    Argparse option switches that are used in several places.
    """

    EXTRA_VALIDATION_OUTPUT = "--extra_validation_output"


# -----------------------------------------------------------------------------
# Long help strings
# -----------------------------------------------------------------------------

HELP_COMPARISON = f"""
    Comparison rules:

    - People MUST match on DOB and surname (or surname metaphone), or hashed
      equivalents, to be considered a plausible match.

    - Only plausible matches proceed to the Bayesian comparison.

    The output file is a CSV (comma-separated value) file with a header and
    these columns:

    - {ComparisonOutputColnames.PROBAND_LOCAL_ID}
      Local ID (identifiable or de-identified as the user chooses) of the
      proband. Taken from the input.

    - {ComparisonOutputColnames.MATCHED}
      Boolean. Was a matching person (a "winner") found in the sample, who is
      to be considered a match to the proband? To give a match requires (a)
      that the log odds for the winner reaches a threshold, and (b) that the
      log odds for the winner exceeds the log odds for the runner-up by a
      certain amount (because a mismatch may be worse than a failed match).

    - {ComparisonOutputColnames.LOG_ODDS_MATCH}
      Log (ln) odds that the winner in the sample is a match to the proband.

    - {ComparisonOutputColnames.P_MATCH}
      Probability that the winner in the sample is a match.

    - {ComparisonOutputColnames.SAMPLE_MATCH_LOCAL_ID}
      Original local ID of the "winner" in the sample (the candidate who is the
      closest match to the proband).

    - {ComparisonOutputColnames.SECOND_BEST_LOG_ODDS}
      Log odds of the runner up (the candidate from the sample who is the
      second-closest match) being the same person as the proband.

    If {Switches.EXTRA_VALIDATION_OUTPUT!r} is used, the following columns are
    added:

    - {ComparisonOutputColnames.BEST_CANDIDATE_LOCAL_ID}
      Local ID of the closest-matching person (candidate) in the sample, EVEN
      IF THEY DID NOT WIN.

    The results file is NOT necessarily sorted as the input proband file was
    (not sorting improves parallel processing efficiency).
"""


# -----------------------------------------------------------------------------
# Helper functions for main argument parser
# -----------------------------------------------------------------------------


def warn_or_fail_if_default_key(args: argparse.Namespace) -> None:
    """
    Ensure that we are not using the default (insecure) hash key unless the
    user has specifically authorized this.
    """
    if args.key == FuzzyDefaults.HASH_KEY:
        if args.allow_default_hash_key:
            log.warning(
                "Proceeding with default hash key at user's "
                "explicit request."
            )
        else:
            log.error(
                "You have not specified a hash key, so are using the "
                "default! Stopping, because this is a very bad idea for "
                "real data. Specify --allow_default_hash_key to use the "
                "default for testing purposes."
            )
            sys.exit(EXIT_FAILURE)


def add_common_groups(parser: argparse.ArgumentParser):
    """
    Sets up standard argparse groups.
    """
    display_group = parser.add_argument_group("display options")
    display_group.add_argument(
        "--verbose", action="store_true", help="Be verbose"
    )

    hasher_group = parser.add_argument_group("hasher (secrecy) options")
    hasher_group.add_argument(
        "--key",
        type=str,
        default=FuzzyDefaults.HASH_KEY,
        help="Key (passphrase) for hasher",
    )
    hasher_group.add_argument(
        "--allow_default_hash_key",
        action="store_true",
        help=(
            "Allow the default hash key to be used beyond tests. INADVISABLE!"
        ),
    )
    hasher_group.add_argument(
        "--rounding_sf",
        type=int,
        default=FuzzyDefaults.ROUNDING_SF,
        help="Number of significant figures to use when rounding frequencies "
        "in hashed version",
    )

    priors_group = parser.add_argument_group(
        "frequency information for prior probabilities"
    )
    priors_group.add_argument(
        "--forename_sex_freq_csv",
        type=str,
        default=FuzzyDefaults.FORENAME_SEX_FREQ_CSV,
        help=f'CSV file of "name, sex, frequency" pairs for forenames. '
        f"You can generate one via {CRATE_FETCH_WORDLISTS}.",
    )
    priors_group.add_argument(
        "--forename_cache_filename",
        type=str,
        default=FuzzyDefaults.FORENAME_CACHE_FILENAME,
        help="File in which to store cached forename info (to speed loading)",
    )
    priors_group.add_argument(
        "--surname_freq_csv",
        type=str,
        default=FuzzyDefaults.SURNAME_FREQ_CSV,
        help=f'CSV file of "name, frequency" pairs for forenames. '
        f"You can generate one via {CRATE_FETCH_WORDLISTS}.",
    )
    priors_group.add_argument(
        "--surname_cache_filename",
        type=str,
        default=FuzzyDefaults.SURNAME_CACHE_FILENAME,
        help="File in which to store cached surname info (to speed loading)",
    )
    priors_group.add_argument(
        "--name_min_frequency",
        type=float,
        default=FuzzyDefaults.NAME_MIN_FREQ,
        help="Minimum base frequency for names. If a frequency is less than "
        "this, use this minimum. Allowing extremely low frequencies may "
        "increase the chances of a spurious match. Note also that "
        "typical name frequency tables don't give very-low-frequency "
        "information. For example, for US census forename/surname "
        "information, below 0.001 percent they report 0.000 percent; so "
        "a reasonable minimum is 0.0005 percent or 0.000005 or 5e-6.",
    )
    priors_group.add_argument(
        "--p_middle_name_n_present",
        type=str,
        default=",".join(
            str(x) for x in FuzzyDefaults.P_MIDDLE_NAME_N_PRESENT
        ),
        help="CSV list of probabilities that a randomly selected person has a "
        "certain number of middle names. The first number is P(has a "
        "first middle name). The second number is P(has a second middle "
        "name | has a first middle name), and so on. The last number "
        "present will be re-used ad infinitum if someone has more names.",
    )
    priors_group.add_argument(
        "--population_size",
        type=int,
        default=FuzzyDefaults.POPULATION_SIZE,
        help="Size of the whole population, from which we calculate the "
        "baseline log odds that two people, randomly selected (and "
        "replaced) from the population are the same person.",
    )
    priors_group.add_argument(
        "--birth_year_pseudo_range",
        type=float,
        default=FuzzyDefaults.BIRTH_YEAR_PSEUDO_RANGE,
        help=f"Birth year pseudo-range. The sole purpose is to calculate the "
        f"probability of two random people sharing a DOB, which is taken "
        f"as 1/({DAYS_PER_YEAR} * b). This option is b.",
    )
    priors_group.add_argument(
        "--postcode_csv_filename",
        type=str,
        default=FuzzyDefaults.POSTCODES_CSV,
        help="CSV file of postcode geography from UK Census/ONS data",
    )
    # noinspection PyUnresolvedReferences
    priors_group.add_argument(
        "--postcode_cache_filename",
        type=str,
        default=FuzzyDefaults.POSTCODE_CACHE_FILENAME,
        help="File in which to store cached postcodes (to speed loading)",
    )
    priors_group.add_argument(
        "--mean_oa_population",
        type=float,
        default=FuzzyDefaults.MEAN_OA_POPULATION,
        help="Mean population of a UK Census Output Area, from which we "
        "estimate the population of postcode-based units.",
    )
    priors_group.add_argument(
        "--p_not_male_or_female",
        type=float,
        default=FuzzyDefaults.P_NOT_MALE_OR_FEMALE,
        help="Probability that a person in the population has gender 'X'.",
    )
    priors_group.add_argument(
        "--p_female_given_male_or_female",
        type=float,
        default=FuzzyDefaults.P_FEMALE_GIVEN_MALE_OR_FEMALE,
        help="Probability that a person in the population is female, given "
        "that they are either male or female.",
    )

    error_p_group = parser.add_argument_group("error probabilities")
    error_p_group.add_argument(
        "--p_minor_forename_error",
        type=float,
        default=FuzzyDefaults.P_MINOR_FORENAME_ERROR,
        help="Assumed probability that a forename has an error in that means "
        "it fails a full match but satisfies a partial (metaphone) match.",
    )
    error_p_group.add_argument(
        "--p_minor_surname_error",
        type=float,
        default=FuzzyDefaults.P_MINOR_SURNAME_ERROR,
        help="Assumed probability that a surname has an error in that means "
        "it fails a full match but satisfies a partial (metaphone) match.",
    )
    error_p_group.add_argument(
        "--p_proband_middle_name_missing",
        type=float,
        default=FuzzyDefaults.P_PROBAND_MIDDLE_NAME_MISSING,
        help="Probability that a middle name, present in the sample, is "
        "missing from the proband.",
    )
    error_p_group.add_argument(
        "--p_sample_middle_name_missing",
        type=float,
        default=FuzzyDefaults.P_SAMPLE_MIDDLE_NAME_MISSING,
        help="Probability that a middle name, present in the proband, is "
        "missing from the sample.",
    )
    error_p_group.add_argument(
        "--p_minor_postcode_error",
        type=float,
        default=FuzzyDefaults.P_MINOR_POSTCODE_ERROR,
        help="Assumed probability that a postcode has an error in that means "
        "it fails a full (postcode unit) match but satisfies a partial "
        "(postcode sector) match.",
    )
    error_p_group.add_argument(
        "--p_gender_error",
        type=float,
        default=FuzzyDefaults.P_GENDER_ERROR,
        help="Assumed probability that a gender is wrong leading to a "
        "proband/candidate mismatch.",
    )

    match_rule_group = parser.add_argument_group("matching rules")
    match_rule_group.add_argument(
        "--min_log_odds_for_match",
        type=float,
        default=FuzzyDefaults.LOG_ODDS_FOR_MATCH,
        help=f"Minimum natural log (ln) odds of two people being the same, "
        f"before a match will be considered. (Default is equivalent to "
        f"p = {FuzzyDefaults.MIN_P_FOR_MATCH}.)",
    )
    match_rule_group.add_argument(
        "--exceeds_next_best_log_odds",
        type=float,
        default=FuzzyDefaults.EXCEEDS_NEXT_BEST_LOG_ODDS,
        help="Minimum log (ln) odds by which a best match must exceed the "
        "next-best match to be considered a unique match.",
    )


def add_comparison_options(
    p: argparse.ArgumentParser,
    proband_is_hashed: bool = True,
    sample_is_hashed: bool = True,
) -> None:
    """
    Common argparse options for comparison commands.
    """
    proband_csv_help = (
        Person.HASHED_CSV_FORMAT_HELP
        if proband_is_hashed
        else Person.PLAINTEXT_CSV_FORMAT_HELP
    )
    sample_csv_help = (
        Person.HASHED_CSV_FORMAT_HELP
        if sample_is_hashed
        else Person.PLAINTEXT_CSV_FORMAT_HELP
    )
    p.add_argument(
        "--probands",
        type=str,
        required=True,
        help="CSV filename for probands data. " + proband_csv_help,
    )
    p.add_argument(
        "--sample",
        type=str,
        required=True,
        help="CSV filename for sample data. " + sample_csv_help,
    )
    p.add_argument(
        "--sample_cache",
        type=str,
        default=None,
        # The cache might contain sensitive information; don't offer it by
        # default.
        help="File in which to store cached sample info (to speed loading)",
    )
    p.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output CSV file for proband/sample comparison.",
    )
    p.add_argument(
        Switches.EXTRA_VALIDATION_OUTPUT,
        action="store_true",
        help="Add extra output for validation purposes.",
    )
    p.add_argument(
        "--n_workers",
        type=int,
        default=FuzzyDefaults.N_PROCESSES,
        help=(
            "Number of processes to use in parallel. "
            "Defaults to number of CPUs on your system."
        ),
    )
    p.add_argument(
        "--max_chunksize",
        type=int,
        default=FuzzyDefaults.MAX_CHUNKSIZE,
        help="Maximum chunk size (number of probands to pass to a "
        "subprocess each time).",
    )
    p.add_argument(
        "--min_probands_for_parallel",
        type=int,
        default=FuzzyDefaults.MIN_PROBANDS_FOR_PARALLEL,
        help="Minimum number of probands for which we will bother to use "
        "parallel processing.",
    )
    p.add_argument(
        "--profile",
        action="store_true",
        help="Profile the code (for development only).",
    )


def get_cfg_from_args(args: argparse.Namespace) -> MatchConfig:
    """
    Return a MatchConfig object from our standard arguments.
    """
    p_middle_name_n_present = [
        float(x) for x in args.p_middle_name_n_present.split(",")
    ]
    min_p_for_match = probability_from_log_odds(args.min_log_odds_for_match)

    log.debug(f"Using population size: {args.population_size}")
    log.debug(
        f"Using min_log_odds_for_match: {args.min_log_odds_for_match} "
        f"(p = {min_p_for_match})"
    )
    return MatchConfig(
        hash_key=args.key,
        rounding_sf=args.rounding_sf,
        forename_sex_csv_filename=args.forename_sex_freq_csv,
        forename_cache_filename=args.forename_cache_filename,
        surname_csv_filename=args.surname_freq_csv,
        surname_cache_filename=args.surname_cache_filename,
        min_name_frequency=args.name_min_frequency,
        p_middle_name_n_present=p_middle_name_n_present,
        population_size=args.population_size,
        birth_year_pseudo_range=args.birth_year_pseudo_range,
        postcode_csv_filename=args.postcode_csv_filename,
        postcode_cache_filename=args.postcode_cache_filename,
        mean_oa_population=args.mean_oa_population,
        min_log_odds_for_match=args.min_log_odds_for_match,
        exceeds_next_best_log_odds=args.exceeds_next_best_log_odds,
        p_minor_forename_error=args.p_minor_forename_error,
        p_minor_surname_error=args.p_minor_surname_error,
        p_proband_middle_name_missing=args.p_proband_middle_name_missing,
        p_sample_middle_name_missing=args.p_sample_middle_name_missing,
        p_minor_postcode_error=args.p_minor_postcode_error,
        p_gender_error=args.p_gender_error,
        p_not_male_or_female=args.p_not_male_or_female,
        p_female_given_male_or_female=args.p_female_given_male_or_female,
        verbose=args.verbose,
    )


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------


def main() -> int:
    """
    Command-line entry point.

    Returns:
        program exit status code
    """

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Argument parser
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        description="Identity matching via hashed fuzzy identifiers",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--version", action="version", version=f"CRATE {CRATE_VERSION}"
    )
    parser.add_argument(
        "--allhelp",
        action=ShowAllSubparserHelpAction,
        help="show help for all commands and exit",
    )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Common arguments
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    add_common_groups(parser)

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Subcommand subparser
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    subparsers = parser.add_subparsers(
        title="commands",
        description="Valid commands are as follows.",
        help="Specify one command.",
        dest="command",  # sorts out the help for the command being mandatory
    )  # type: _SubParsersAction  # noqa
    subparsers.required = True  # requires a command

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # commands to print demo sample files
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    _ = subparsers.add_parser(
        "print_demo_sample", help="Print a demo sample .CSV file."
    )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # hash command
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    hash_parser = subparsers.add_parser(
        "hash",
        help="STEP 1 OF DE-IDENTIFIED LINKAGE. "
        "Hash an identifiable CSV file into an encrypted one. ",
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
        description="""
    Takes an identifiable list of people (with name, DOB, and postcode
    information) and creates a hashed, de-identified equivalent.

    The local ID (presumed not to be a direct identifier) is preserved exactly.

    Optionally, the "other" information (you can choose, e.g. attaching a
    direct identifier) is preserved, but you have to ask for that explicitly;
    that is normally for testing.""",
    )
    hash_parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="CSV filename for input (plaintext) data. "
        + Person.PLAINTEXT_CSV_FORMAT_HELP,
    )
    hash_parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Output CSV file for hashed version. "
        + Person.HASHED_CSV_FORMAT_HELP,
    )
    hash_parser.add_argument(
        "--without_frequencies",
        action="store_true",
        help="Do not include frequency information. This makes the result "
        "suitable for use as a sample file, but not a proband file.",
    )
    hash_parser.add_argument(
        "--include_other_info",
        action="store_true",
        help=(
            f"Include the (potentially identifying) "
            f"{BasePerson.ATTR_OTHER_INFO!r} data? "
            "Usually False; may be set to True for validation."
        ),
    )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # compare_plaintext command
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    compare_plaintext_parser = subparsers.add_parser(
        "compare_plaintext",
        help="IDENTIFIABLE LINKAGE COMMAND. "
        "Compare a list of probands against a sample (both in "
        "plaintext). ",
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
        description=HELP_COMPARISON,
    )
    add_comparison_options(
        compare_plaintext_parser,
        proband_is_hashed=False,
        sample_is_hashed=False,
    )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # compare_hashed_to_hashed command
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    compare_h2h_parser = subparsers.add_parser(
        "compare_hashed_to_hashed",
        help=(
            "STEP 2 OF DE-IDENTIFIED LINKAGE (for when you have de-identified "
            "both sides in advance). "
            "Compare a list of probands against a sample (both hashed)."
        ),
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
        description=HELP_COMPARISON,
    )
    add_comparison_options(
        compare_h2h_parser, proband_is_hashed=True, sample_is_hashed=True
    )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # compare_hashed_to_plaintext command
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    compare_h2p_parser = subparsers.add_parser(
        "compare_hashed_to_plaintext",
        help="STEP 2 OF DE-IDENTIFIED LINKAGE (for when you have received "
        "de-identified data and you want to link to your identifiable "
        "data, producing a de-identified result). "
        "Compare a list of probands (hashed) against a sample "
        "(plaintext).",
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
        description=HELP_COMPARISON,
    )
    add_comparison_options(
        compare_h2p_parser,
        proband_is_hashed=True,
        sample_is_hashed=False,
    )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Debugging commands
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    show_metaphone_parser = subparsers.add_parser(
        "show_metaphone", help="Show metaphones of words"
    )
    show_metaphone_parser.add_argument(
        "words", nargs="+", help="Words to check"
    )

    show_forename_freq_parser = subparsers.add_parser(
        "show_forename_freq", help="Show frequencies of forenames"
    )
    show_forename_freq_parser.add_argument(
        "forenames", nargs="+", help="Forenames to check"
    )

    show_forename_metaphone_freq_parser = subparsers.add_parser(
        "show_forename_metaphone_freq",
        help="Show frequencies of forename metaphones",
    )
    show_forename_metaphone_freq_parser.add_argument(
        "metaphones", nargs="+", help="Forenames to check"
    )

    show_surname_freq_parser = subparsers.add_parser(
        "show_surname_freq", help="Show frequencies of surnames"
    )
    show_surname_freq_parser.add_argument(
        "surnames", nargs="+", help="surnames to check"
    )

    show_surname_metaphone_freq_parser = subparsers.add_parser(
        "show_surname_metaphone_freq",
        help="Show frequencies of surname metaphones",
    )
    show_surname_metaphone_freq_parser.add_argument(
        "metaphones", nargs="+", help="surnames to check"
    )

    _ = subparsers.add_parser(
        "show_dob_freq", help="Show the frequency of any DOB"
    )

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Parse arguments and set up
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    args = parser.parse_args()
    main_only_quicksetup_rootlogger(
        level=logging.DEBUG if args.verbose else logging.INFO,
        with_process_id=True,
    )
    log.debug(
        f"Ensuring default cache directory exists: "
        f"{FuzzyDefaults.DEFAULT_CACHE_DIR}"
    )
    os.makedirs(FuzzyDefaults.DEFAULT_CACHE_DIR, exist_ok=True)

    cfg = get_cfg_from_args(args)

    # pdb.set_trace()

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Run a command
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    log.info(f"Command: {args.command}")

    if args.command == "print_demo_sample":
        print(get_demo_csv())

    elif args.command == "hash":
        warn_or_fail_if_default_key(args)
        log.info(f"Hashing identity file: {args.input}")
        hash_identity_file(
            cfg=cfg,
            input_csv=args.input,
            output_csv=args.output,
            without_frequencies=args.without_frequencies,
            include_other_info=args.include_other,
        )
        log.info(f"... finished; written to {args.output}")

    elif args.command == "compare_plaintext":
        log.info(
            f"Comparing files:\n"
            f"- plaintext probands: {args.probands}\n"
            f"- plaintext sample: {args.sample}"
        )
        compare_probands_to_sample_from_csv(
            cfg=cfg,
            extra_validation_output=args.extra_validation_output,
            max_chunksize=args.max_chunksize,
            min_probands_for_parallel=args.min_probands_for_parallel,
            n_workers=args.n_workers,
            output_csv=args.output,
            probands_csv=args.probands,
            probands_plaintext=True,
            profile=args.profile,
            sample_cache_filename=args.sample_cache,
            sample_csv=args.sample,
            sample_plaintext=True,
        )
        log.info(f"... comparison finished; results are in {args.output}")

    elif args.command == "compare_hashed_to_hashed":
        log.info(
            f"Comparing files:\n"
            f"- hashed probands: {args.probands}\n"
            f"- hashed sample: {args.sample}"
        )
        compare_probands_to_sample_from_csv(
            cfg=cfg,
            extra_validation_output=args.extra_validation_output,
            max_chunksize=args.max_chunksize,
            min_probands_for_parallel=args.min_probands_for_parallel,
            n_workers=args.n_workers,
            output_csv=args.output,
            probands_csv=args.probands,
            probands_plaintext=False,
            profile=args.profile,
            sample_csv=args.sample,
            sample_plaintext=False,
        )
        log.info(f"... comparison finished; results are in {args.output}")

    elif args.command == "compare_hashed_to_plaintext":
        warn_or_fail_if_default_key(args)
        log.info(
            f"Comparing files:\n"
            f"- hashed probands: {args.probands}\n"
            f"- plaintext sample: {args.sample}"
        )
        compare_probands_to_sample_from_csv(
            cfg=cfg,
            extra_validation_output=args.extra_validation_output,
            max_chunksize=args.max_chunksize,
            min_probands_for_parallel=args.min_probands_for_parallel,
            n_workers=args.n_workers,
            output_csv=args.output,
            probands_csv=args.probands,
            probands_plaintext=False,
            profile=args.profile,
            sample_cache_filename=args.sample_cache,
            sample_csv=args.sample,
            sample_plaintext=True,
        )
        log.info(f"... comparison finished; results are in {args.output}")

    elif args.command == "show_metaphone":
        for word in args.words:
            log.info(f"Metaphone for {word!r}: {get_metaphone(word)}")

    elif args.command == "show_forename_freq":
        for forename in args.forenames:
            log.info(
                f"Forename {forename!r}: "
                f"F {cfg.forename_freq(forename, GENDER_FEMALE)}, "
                f"M {cfg.forename_freq(forename, GENDER_MALE)}, "
                f"overall {cfg.forename_freq(forename, '')}"
            )

    elif args.command == "show_forename_metaphone_freq":
        for metaphone in args.metaphones:
            log.info(
                f"Forename metaphone {metaphone!r}: "
                f"F {cfg.forename_metaphone_freq(metaphone, GENDER_FEMALE)}, "  # noqa
                f"M {cfg.forename_metaphone_freq(metaphone, GENDER_MALE)}, "  # noqa
                f"overall {cfg.forename_metaphone_freq(metaphone, '')}"
            )

    elif args.command == "show_surname_freq":
        for surname in args.surnames:
            log.info(f"Surname {surname!r}: {cfg.surname_freq(surname)}")

    elif args.command == "show_surname_metaphone_freq":
        for metaphone in args.metaphones:
            log.info(
                f"Surname metaphone {metaphone!r}: "
                f"{cfg.surname_metaphone_freq(metaphone)}"
            )

    elif args.command == "show_dob_freq":
        log.info(f"DOB frequency: {cfg.p_two_people_share_dob}")

    else:
        # Shouldn't get here.
        log.error(f"Unknown command: {args.command}")
        return EXIT_FAILURE

    return EXIT_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
