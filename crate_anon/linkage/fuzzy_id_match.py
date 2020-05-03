#!/usr/bin/env python

r"""
crate_anon/linkage/fuzzy_id_match.py

===============================================================================

    Copyright (C) 2015-2020 Rudolf Cardinal (rudolf@pobox.com).

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
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.

===============================================================================

**Testing the concept of fuzzy matching with hashed identifiers, as part of
work to link UK NHS and education/social care data without sharing direct
patient identifiers.**


.. _TLSH: https://github.com/trendmicro/tlsh
.. _sdhash: http://roussev.net/sdhash/sdhash.html
.. _Nilsimsa: https://en.wikipedia.org/wiki/Nilsimsa_Hash
.. _ssdeep: https://ssdeep-project.github.io/ssdeep/index.html


**See draft paper.**


Other approaches to fuzzy matching of reduced data
--------------------------------------------------

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


Geography
---------

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


Speed of "validate1" test
-------------------------

On a test 3 GHz desktop, this code takes approximately 100 μs to hash a person
record, and 14-40 μs to compare two records (see timing tests).

A comparison of 1000 pre-hashed subjects to 50m records requiring hashing,
without any caching, is going to take about 1000 * 50m * 120 μs, or quite a
long time -- a big part of which would be pointless re-hashing. A reasonable
strategy for a large database would therefore be to:

- pre-hash the sample with the agreed key (e.g. about 1.8 hours for 66m
  records);
- for each hashed proband, restrict the comparison to those with a matching
  hashed DOB, and either a partial or a full match on surname (e.g. for
  "SMITH", with a frequency of about 0.01, this would give about 1800 records
  to check; checking would take up to about 40 μs each (so up to 72 ms per
  proband) -- plus some query time;
- checking 1000 probands would therefore take about 72 seconds; checking
  200k probands about 4 hours.
- So we'd be talking about a time of the order of 6 hours to compare an NHS
  Trust's entire data set to a UK national database.

For validation, we are thinking about a much larger, :math:`n^2`, comparison.
Again, we should pre-hash. So if :math:`h` is the hashing time and :math:`c` is
the comparison time, we're talking about :math:`hn + cn^2`. If we work
backwards and say :math:`h` is 100 μs, :math:`c` is 20 μs on average, and we
want this achievable in 1 hour, then that gives a value for n of about 19,000,
so let's say 20,000 (sample size 10,000, "other" size 10,000).

Subsequent speedup 2020-04-24: see comments in timing tests; ``h`` now down
from 100 to 71; ``c`` now down from 14-40 to 6-22 (6 for DOB mismatch, 22 for
match). So realistically ``c = 10`` or thereabouts. 

.. code-block:: r

    h <- 71 / 1e6  # microseconds to seconds
    c <- 10 / 1e6  # 20 microseconds
    t <- function(n) { h * n + c * n^2 / 2 }  # function relating time to n
    target <- 60 * 60  # target time: 1 hour = 3600 seconds
    errfunc <- function(n) { (t(n) - target) ^ 2 }  # function giving error
    result <- optim(par=50, fn=errfunc)  # minimize error, start n=50; gives 26825


For Figure 3
------------

.. code-block:: none

    crate_fuzzy_id_match compare_plaintext \
        --probands demo_fig3_probands.csv \
        --sample demo_fig3_sample.csv \
        --output demo_fig3_output.csv

.. code-block:: R

    odds_from_p <- function(p) p/(1-p)
    log_odds_from_p <- function(p) log(odds_from_p(p))
    p_from_odds <- function(odds) odds/(1 + odds)
    p_from_log_odds <- function(log_odds) p_from_odds(exp(log_odds))
    log_posterior_odds_1 <- function(log_prior_odds, log_lr) log_prior_odds + log_lr
    log_posterior_odds_2 <- function(log_prior_odds, p_d_h, p_d_not_h) {
        log_lr <- log(p_d_h / p_d_not_h)
        return(log_prior_odds + log_lr)
    }

===============================================================================

.. rubric:: Footnotes

.. [#gronau2017]

    Gronau QF, Sarafoglou A, Matzke D, Ly A, Boehm U, Marsman M, Leslie DS,
    Forster JJ, Wagenmakers E, Steingroever H (2017).
    A tutorial on bridge sampling.
    *Journal of Mathematical Psychology* 81: 80–97.
    https://doi.org/10.1016/j.jmp.2017.09.005.


"""  # noqa

import argparse
from collections import Counter, defaultdict, OrderedDict
import copy
import csv
import logging
import math
from multiprocessing import cpu_count, Pool
import os
import pdb
import pickle
import random
import re
import string
import sys
import time
import timeit
from typing import (
    Any, Dict, Generator, Iterable, List, Optional, Set, Tuple,
    TYPE_CHECKING, Union,
)

import appdirs
from cardinal_pythonlib.argparse_func import (
    RawDescriptionArgumentDefaultsHelpFormatter,
    ShowAllSubparserHelpAction,
)
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
from cardinal_pythonlib.stringfunc import mangle_unicode_to_ascii
from fuzzy import DMetaphone
from sqlalchemy.engine import create_engine
from sqlalchemy.engine.base import Engine
from sqlalchemy.engine.result import ResultProxy
from sqlalchemy.sql import text

from crate_anon.anonymise.anonregex import get_uk_postcode_regex_string
from crate_anon.common.constants import EXIT_FAILURE, EXIT_SUCCESS
from crate_anon.version import CRATE_VERSION

if TYPE_CHECKING:
    # noinspection PyProtectedMember
    from argparse import _SubParsersAction

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

CHECK_ASSERTIONS_IN_HIGH_SPEED_FUNCTIONS = True  # for debugging only

dmeta = DMetaphone()

CRATE_FETCH_WORDLISTS = "crate_fetch_wordlists"
CPU_COUNT = cpu_count()
DAYS_PER_YEAR = 365.25  # approximately!
DEFAULT_HASH_KEY = "fuzzy_id_match_default_hash_key_DO_NOT_USE_FOR_LIVE_DATA"
DEFAULT_MAX_CHUNKSIZE = 500
HIGHDEBUG = 15  # in between logging.DEBUG (10) and logging.INFO (20)
MINUS_INFINITY = -math.inf
THIS_DIR = os.path.abspath(os.path.dirname(__file__))
UK_POPULATION_2017 = 66040000  # 2017 figure, 66.04m
UK_MEAN_OA_POPULATION_2011 = 309
# ... https://www.ons.gov.uk/methodology/geography/ukgeographies/censusgeography  # noqa


# =============================================================================
# Hashing
# =============================================================================

Hasher = HmacSHA256Hasher


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
    pickle.dump(
        data,
        open(filename, "wb"),
        protocol=pickle.HIGHEST_PROTOCOL
    )
    log.info("... done")


# =============================================================================
# String manipulation
# =============================================================================

ISO_DATE_REGEX = re.compile(
    r"[1-9][0-9][0-9][0-9]-(?:1[0-2]|0[1-9])-(?:3[01]|0[1-9]|[12][0-9])"
)  # YYYY-MM-DD
POSTCODE_REGEX = re.compile(get_uk_postcode_regex_string(
    at_word_boundaries_only=False))
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

    - http://www.b-eye-network.com/view/1596
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
        raise NotImplementedError

    @property
    def p_d_given_h(self) -> float:
        """
        Returns :math:`P(D | H)`, the probability of the observed data given
        the hypothesis of a match.
        """
        raise NotImplementedError

    @property
    def p_d_given_not_h(self) -> float:
        """
        Returns :math:`P(D | H)`, the probability of the observed data given
        the hypothesis of a match.
        """
        raise NotImplementedError

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
            p_d_given_not_h=self.p_d_given_not_h
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
    """
    Represents a comparison where the user supplies P(D | H) and P(D | ¬H)
    directly.
    """
    def __init__(self,
                 p_d_given_same_person: float,
                 p_d_given_diff_person: float,
                 **kwargs) -> None:
        """
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
    objects, condition upon ``match``, but this is often clearer.
    """
    def __init__(self,
                 match: bool,
                 p_match_given_same_person: float,
                 p_match_given_diff_person: float,
                 **kwargs) -> None:
        """
        Args:
            match:
                D; is there a match?
            p_match_given_same_person:
                If match: :math:`P(D | H) = P(\text{match given same person})
                 = 1 - p_e`.
                If no match: :math:`P(D | H) = 1 - P(\text{match given same
                person}) = p_e`.
            p_match_given_diff_person:
                If match: :math:`P(D | \neg H) = P(\text{match given different
                person}) = p_f`.
                If no match: :math:`P(D | \neg H) = 1 - P(\text{match given
                different person}) = 1 - p_f`.
        """
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

    Again, this is for clarity. Code that produces one of these could equally
    produce one of three :class:`DirectComparison` objects, condition upon
    ``full_match`` and ``partial_match``, but this is generally much clearer.
    """
    def __init__(self,
                 full_match: bool,
                 p_f: float,
                 p_e: float,
                 partial_match: bool,
                 p_p: float,
                 **kwargs) -> None:
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
            assert p_p >= p_f, (
                f"p_p={p_p}, p_f={p_f}, but should have p_p >= p_f"
            )
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


def bayes_compare(prior_log_odds: float,
                  comparisons: Iterable[Optional[Comparison]],
                  debug: bool = False) -> float:
    """
    Works through multiple comparisons and returns posterior log odds.

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
            log.debug(f"{comparison}: "
                      f"{log_odds} -> {next_log_odds} ({change})")
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
    def __init__(self,
                 csv_filename: str,
                 cache_filename: str,
                 by_gender: bool = False,
                 min_frequency: float = 5e-6) -> None:
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
        self._metaphone_freq = {}  # type: Dict[Union[str, Tuple[str, str]], float]  # noqa
        self._by_gender = by_gender

        try:
            self._name_freq, self._metaphone_freq = cache_load(cache_filename)
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

    def name_frequency(self, name: str, gender: str = "",
                       prestandardized: bool = True) -> float:
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
        key = name, gender if self._by_gender else name
        return self._name_freq.get(key, self._min_frequency)

    def metaphone_frequency(self, metaphone: str, gender: str = "") -> float:
        """
        Returns the frequency of a metaphone
        """
        key = metaphone, gender if self._by_gender else metaphone
        return self._metaphone_freq.get(key, self._min_frequency)


# =============================================================================
# PostcodeFrequencyInfo
# =============================================================================

class PostcodeFrequencyInfo(object):
    """
    Holds frequencies of a class of names (e.g. first names or surnames), and
    also of their hashed versions.
    """
    def __init__(self,
                 csv_filename: str,
                 cache_filename: str,
                 mean_oa_population: float = UK_MEAN_OA_POPULATION_2011) \
            -> None:
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
            (self._postcode_unit_freq,
             self._postcode_sector_freq,
             self._total_population) = cache_load(cache_filename)
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
                            f"postcode sector {sector}, Output Area {oa}")

                    unit_to_oa[unit] = oa
                    oa_unit_counter[oa] += 1  # one more unit for this OA
                    if sector in sector_to_oas:
                        sector_to_oas[sector].add(oa)
                    else:
                        sector_to_oas[sector] = {oa}
            log.info("... done")

            # Calculate
            log.info(f"Calculating population frequencies for postcodes...")
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
                sector_freq[sector] = sector_population / self._total_population  # noqa
            log.info("... done")
            # Save to cache
            cache_save(cache_filename, [
                unit_freq, sector_freq, self._total_population])

    def postcode_unit_frequency(self, postcode_unit: str,
                                prestandardized: bool = False) -> float:
        """
        Returns the frequency of a name.

        Args:
            postcode_unit: the postcode unit to check
            prestandardized: was the postcode pre-standardized in format?

        Returns:
            the name's frequency in the population
        """
        stpu = (postcode_unit if prestandardized
                else standardize_postcode(postcode_unit))
        try:
            return self._postcode_unit_freq[stpu]
        except KeyError:
            raise ValueError(f"Unknown postcode: {postcode_unit}")

    def postcode_sector_frequency(self, postcode_sector: str,
                                  prestandardized: bool = False) -> float:
        """
        Returns the frequency of a postcode sector.
        """
        stps = (postcode_sector if prestandardized
                else standardize_postcode(postcode_sector))
        return self._postcode_sector_freq[stps]

    def is_valid_postcode(self, postcode_unit: str) -> bool:
        """
        Is this a valid postcode?
        """
        return postcode_unit in self._postcode_unit_freq

    def postcode_unit_population(self, postcode_unit: str,
                                 prestandardized: bool = False) -> float:
        """
        Returns the calculated population of a postcode unit.

        Args:
            postcode_unit: the postcode unit to check
            prestandardized: was the postcode pre-standardized in format?
        """
        stpu = (postcode_unit if prestandardized
                else standardize_postcode(postcode_unit))
        return self.postcode_unit_frequency(stpu) * self._total_population

    def postcode_sector_population(self, postcode_sector: str,
                                   prestandardized: bool = False) -> float:
        """
        Returns the calculated population of a postcode sector.

        Args:
            postcode_sector: the postcode sector to check
            prestandardized: was the postcode pre-standardized in format?
        """
        stps = (
            postcode_sector if prestandardized
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
    """
    def __init__(
            self,
            hash_key: str,
            rounding_sf: int,
            forename_sex_csv_filename: str,
            forename_cache_filename: str,
            surname_csv_filename: str,
            surname_cache_filename: str,
            min_name_frequency: float,
            p_middle_name_n_present: List[float],
            population_size: int,
            birth_year_pseudo_range: float,
            postcode_csv_filename: str,
            postcode_cache_filename: str,
            mean_oa_population: float,
            min_log_odds_for_match: float,
            exceeds_next_best_log_odds: float,
            p_minor_forename_error: float,
            p_minor_surname_error: float,
            p_proband_middle_name_missing: float,
            p_sample_middle_name_missing: float,
            p_minor_postcode_error: float,
            p_gender_error: float,
            p_not_male_or_female: float,
            p_female_given_male_or_female: float,
            verbose: bool = False) -> None:
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
            by_gender=True)
        self._surname_freq = NameFrequencyInfo(
            csv_filename=surname_csv_filename,
            cache_filename=surname_cache_filename,
            min_frequency=min_name_frequency)
        self._postcode_freq = PostcodeFrequencyInfo(
            csv_filename=postcode_csv_filename,
            cache_filename=postcode_cache_filename,
            mean_oa_population=mean_oa_population)

        self.p_two_people_share_dob = 1 / (DAYS_PER_YEAR *
                                           birth_year_pseudo_range)

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

    def forename_freq(self,
                      name: str,
                      gender: str,
                      prestandardized: bool = False) -> float:
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
            freq = self._forename_freq.name_frequency(name, gender,
                                                      prestandardized=True)
        else:
            freq_f = self._forename_freq.name_frequency(name, GENDER_FEMALE,
                                                        prestandardized=True)
            freq_m = self._forename_freq.name_frequency(name, GENDER_MALE,
                                                        prestandardized=True)
            freq = self.mean_across_genders(freq_f, freq_m)
        if self.verbose:
            log.debug(f"    Forename frequency for {name}, gender {gender!r}: "
                      f"{freq}")
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
                metaphone, GENDER_FEMALE)
            freq_m = self._forename_freq.metaphone_frequency(
                metaphone, GENDER_MALE)
            freq = self.mean_across_genders(freq_f, freq_m)
        if self.verbose:
            log.debug(f"    Forename metaphone frequency for {metaphone}, "
                      f"gender {gender!r}: {freq}")
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
            name, prestandardized=prestandardized)
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
            log.debug(f"    Surname metaphone frequency for {metaphone}: "
                      f"{freq}")
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

    def postcode_unit_freq(self, postcode_unit: str,
                           prestandardized: bool = True) -> float:
        """
        Returns the frequency for a full postcode, or postcode unit (the
        proportion of the population who live in that postcode).
        """
        freq = self._postcode_freq.postcode_unit_frequency(
            postcode_unit, prestandardized=prestandardized)
        if self.verbose:
            log.debug(f"Postcode unit frequency for {postcode_unit}: {freq}")
        return freq

    def postcode_unit_population(self, postcode_unit: str,
                                 prestandardized: bool = False) -> float:
        """
        Returns the calculated population of a postcode unit.

        Args:
            postcode_unit: the postcode unit to check
            prestandardized: was the postcode pre-standardized in format?
        """
        return self._postcode_freq.postcode_unit_population(
            postcode_unit, prestandardized=prestandardized)

    def postcode_sector_freq(self, postcode_sector: str,
                             prestandardized: bool = True) -> float:
        """
        Returns the frequency for a postcode sector; see
        :meth:`postcode_freq`.
        """
        freq = self._postcode_freq.postcode_sector_frequency(
            postcode_sector, prestandardized=prestandardized)
        if self.verbose:
            log.debug(f"Postcode sector frequency for {postcode_sector}: "
                      f"{freq}")
        return freq

    def postcode_sector_population(self, postcode_sector: str,
                                   prestandardized: bool = False) -> float:
        """
        Returns the calculated population of a postcode sector.

        Args:
            postcode_sector: the postcode sector to check
            prestandardized: was the postcode pre-standardized in format?
        """
        return self._postcode_freq.postcode_sector_population(
            postcode_sector, prestandardized=prestandardized)

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
    Represents a identifier (plaintext or hashed) and its accompanying
    frequency.
    """
    def __init__(self,
                 comparison_name: str,
                 identifier: Optional[str],
                 frequency: Optional[float],
                 p_error: float) -> None:
        """
        Args:
            comparison_name:
                Name for the comparison.
            identifier:
                The identifier (plaintext or hashed).
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
            return None
        matches = candidate_id == proband_id
        return MatchNoMatchComparison(
            name=self.comparison_name,
            match=matches,
            p_match_given_same_person=proband.p_no_error,
            p_match_given_diff_person=proband.frequency
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

    def assert_has_frequency_info(self) -> None:
        """
        Ensures that frequency information is present, or raises
        :exc:`AssertionError`.
        """
        if self.identifier:
            assert self.frequency is not None, (
                f"{self.comparison_name}: missing frequency"
            )


class FuzzyIdFreq(object):
    """
    Represents a hashed identifier with its frequency, and a hashed fuzzy
    version, with its frequency.
    """
    def __init__(self,
                 comparison_name: str,
                 exact_identifier: Optional[str],
                 exact_identifier_frequency: Optional[float],
                 fuzzy_identifier: Optional[str],
                 fuzzy_identifier_frequency: Optional[float],
                 p_error: float) -> None:
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
            return None
        candidate_fuzzy = self.fuzzy_identifier
        proband_fuzzy = proband.fuzzy_identifier
        if not (candidate_fuzzy and proband_fuzzy):
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

    def assert_has_frequency_info(self) -> None:
        """
        Ensures that frequency information is present, or raises
        :exc:`AssertionError`.
        """
        if self.exact_identifier:
            assert self.exact_identifier_frequency is not None, (
                f"{self.comparison_name}: missing exact identifier frequency"
            )
            assert self.fuzzy_identifier, (
                f"{self.comparison_name}: missing fuzzy identifier"
            )
            assert self.fuzzy_identifier_frequency is not None, (
                f"{self.comparison_name}: missing fuzzy identifier frequency"
            )


# =============================================================================
# Person
# =============================================================================

GENDER_MALE = "M"
GENDER_FEMALE = "F"
GENDER_OTHER = "X"
VALID_GENDERS = ["", GENDER_MALE, GENDER_FEMALE, GENDER_OTHER]
# ... standard three gender codes; "" = missing


class Person(object):
    """
    Represents a person. The information may be incomplete or slightly wrong.
    """
    _COMMON_ATTRS = [
        # not: "is_hashed",
        "original_id",
        "research_id",
    ]
    PLAINTEXT_ATTRS = _COMMON_ATTRS + [
        "first_name",
        "middle_names",
        "surname",
        "dob",
        "gender",
        "postcodes",
    ]
    HASHED_ATTRS = _COMMON_ATTRS + [
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
    INT_ATTRS = [
        "original_id",
    ]
    FLOAT_ATTRS = [
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
    SEMICOLON_DELIMIT = [
        # plaintext
        "middle_names",
        "postcodes",

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
    PLAINTEXT_CSV_FORMAT_HELP = (
        f"Header row present. Columns: {PLAINTEXT_ATTRS}. "
        f"Semicolon-separated values may be within "
        f"{sorted(list(set(SEMICOLON_DELIMIT).intersection(PLAINTEXT_ATTRS)))}."
    )
    HASHED_CSV_FORMAT_HELP = (
        f"Header row present. Columns: {HASHED_ATTRS}. "
        f"Semicolon-separated values may be within "
        f"{sorted(list(set(SEMICOLON_DELIMIT).intersection(HASHED_ATTRS)))}."
    )

    # -------------------------------------------------------------------------
    # __init__, __repr__, copy
    # -------------------------------------------------------------------------

    def __init__(self,
                 cfg: MatchConfig,

                 # State
                 is_hashed: bool = False,

                 # Reference codes
                 original_id: int = None,
                 research_id: str = "",

                 # Plaintext
                 first_name: str = "",
                 middle_names: List[str] = None,
                 surname: str = "",
                 dob: str = "",
                 gender: str = "",
                 postcodes: List[str] = None,

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

                 hashed_postcode_units: List[str] = None,
                 postcode_unit_frequencies: List[float] = None,
                 hashed_postcode_sectors: List[str] = None,
                 postcode_sector_frequencies: List[float] = None,

                 other: Dict[str, Any] = None) -> None:
        """
        Args:
            cfg:
                Configuration object. It is more efficient to use this while
                creating a Person object; it saves lookup time later.

            is_hashed:
                Is this a hashed representation? If so, matching works
                differently.

            original_id:
                Unique integer ID. Not used at all for comparison; simply used
                to retrieve an identity after a match has been confirmed.
            research_id:
                Research pseudonym (not itself identifying).

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
                The first name's metaphone ("sounds like"), irreversibly hashed.
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

            other:
                Dictionary of other attributes (only used for validation
                research, e.g. ensuring linkage is not biased by ethnicity).
        """
        # ---------------------------------------------------------------------
        # Store info
        # ---------------------------------------------------------------------
        self.cfg = cfg
        self.is_hashed = is_hashed
        self.original_id = original_id
        self.research_id = research_id

        self.first_name = standardize_name(first_name)
        self.middle_names = [
            standardize_name(x) for x in middle_names if x
        ] if middle_names else []
        self.surname = standardize_name(surname)
        self.dob = dob
        self.gender = gender
        self.postcodes = [standardize_postcode(x)
                          for x in postcodes if x] if postcodes else []

        self.hashed_first_name = hashed_first_name
        self.first_name_frequency = first_name_frequency
        self.hashed_first_name_metaphone = hashed_first_name_metaphone
        self.first_name_metaphone_frequency = first_name_metaphone_frequency

        self.hashed_middle_names = hashed_middle_names or []
        n_hashed_middle_names = len(self.hashed_middle_names)
        self.middle_name_frequencies = (
            middle_name_frequencies or [None] * n_hashed_middle_names
        )
        self.hashed_middle_name_metaphones = hashed_middle_name_metaphones or []  # noqa
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

        self.other = other or {}  # type: Dict[str, Any]

        # ---------------------------------------------------------------------
        # Validation
        # ---------------------------------------------------------------------
        assert self.original_id or self.research_id
        if is_hashed:
            # hashed
            assert (
                not self.first_name and
                not self.middle_names and
                not self.surname and
                not self.dob and
                not self.postcodes
            ), "Don't supply plaintext information for a hashed Person"
            # Note that frequency information can be absent for candidates from
            # the sample; we check it's present for probands via
            # assert_valid_as_proband().
            if self.hashed_first_name:
                assert self.hashed_first_name_metaphone
            if self.hashed_middle_names:
                assert (
                    len(self.middle_name_frequencies) == n_hashed_middle_names and  # noqa
                    len(self.hashed_middle_name_metaphones) == n_hashed_middle_names and  # noqa
                    len(self.middle_name_metaphone_frequencies) == n_hashed_middle_names  # noqa
                )
            if self.hashed_surname:
                assert self.hashed_surname_metaphone
            if self.hashed_postcode_units:
                assert (
                    len(self.postcode_unit_frequencies) == n_hashed_postcodes and  # noqa
                    len(self.hashed_postcode_sectors) == n_hashed_postcodes and
                    len(self.postcode_sector_frequencies) == n_hashed_postcodes
                )
        else:
            # Plain text
            assert (
                not self.hashed_first_name and
                self.first_name_frequency is None and
                not self.hashed_first_name_metaphone and
                self.first_name_metaphone_frequency is None and

                not self.hashed_middle_names and
                not self.middle_name_frequencies and
                not self.hashed_middle_name_metaphones and
                not self.middle_name_metaphone_frequencies and

                not self.hashed_surname and
                self.surname_frequency is None and
                not self.hashed_surname_metaphone and
                self.surname_metaphone_frequency is None and

                not self.hashed_dob and

                not self.hashed_gender and
                self.gender_frequency is None and

                not self.hashed_postcode_units and
                not self.postcode_unit_frequencies and
                not self.hashed_postcode_sectors and
                not self.postcode_sector_frequencies
            ), "Don't supply hashed information for a plaintext Person"
            if self.dob:
                assert ISO_DATE_REGEX.match(dob), f"Bad date: {dob}"
            assert self.gender in VALID_GENDERS
            for postcode in self.postcodes:
                assert POSTCODE_REGEX.match(postcode), (
                    f"Bad postcode: {postcode}"
                )

        # ---------------------------------------------------------------------
        # Precalculate things, for speed
        # ---------------------------------------------------------------------

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
                p_error=cfg.p_minor_forename_error
            )
            for i in range(len(self.hashed_middle_names)):
                n = i + 1
                self.middle_names_info.append(FuzzyIdFreq(
                    comparison_name=f"middle_name_{n}",
                    exact_identifier=self.hashed_middle_names[i],
                    exact_identifier_frequency=self.middle_name_frequencies[i],
                    fuzzy_identifier=self.hashed_middle_name_metaphones[i],
                    fuzzy_identifier_frequency=self.middle_name_metaphone_frequencies[i],  # noqa
                    p_error=cfg.p_minor_forename_error
                ))
            self.surname_info = FuzzyIdFreq(
                comparison_name="surname",
                exact_identifier=self.hashed_surname,
                exact_identifier_frequency=self.surname_frequency,
                fuzzy_identifier=self.hashed_surname_metaphone,
                fuzzy_identifier_frequency=self.surname_metaphone_frequency,
                p_error=cfg.p_minor_surname_error
            )
            self.dob_info = IdFreq(
                comparison_name="DOB",
                identifier=self.hashed_dob,
                frequency=cfg.p_two_people_share_dob,
                p_error=0  # no typos allowed in dates of birth
            )
            self.gender_info = IdFreq(
                comparison_name="gender",
                identifier=self.hashed_gender,
                frequency=self.gender_frequency,
                p_error=cfg.p_gender_error
            )
            for i in range(len(self.hashed_postcode_units)):
                self.postcodes_info.append(FuzzyIdFreq(
                    comparison_name=f"postcode",
                    exact_identifier=self.hashed_postcode_units[i],
                    exact_identifier_frequency=self.postcode_unit_frequencies[i],  # noqa
                    fuzzy_identifier=self.hashed_postcode_sectors[i],
                    fuzzy_identifier_frequency=self.postcode_sector_frequencies[i],  # noqa
                    p_error=cfg.p_minor_postcode_error
                ))

        else:
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            # Plaintext info
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

            first_name_metaphone = get_metaphone(self.first_name)
            self.first_name_info = FuzzyIdFreq(
                comparison_name="first_name",
                exact_identifier=self.first_name,
                exact_identifier_frequency=cfg.forename_freq(
                    self.first_name,
                    self.gender,
                    prestandardized=True
                ),
                fuzzy_identifier=first_name_metaphone,
                fuzzy_identifier_frequency=cfg.forename_metaphone_freq(
                    first_name_metaphone,
                    self.gender
                ),
                p_error=cfg.p_minor_forename_error
            )
            for i in range(len(self.middle_names)):
                n = i + 1
                middle_name = self.middle_names[i]
                middle_name_metaphone = get_metaphone(middle_name)
                self.middle_names_info.append(FuzzyIdFreq(
                    comparison_name=f"middle_name_{n}",
                    exact_identifier=middle_name,
                    exact_identifier_frequency=cfg.forename_freq(
                        middle_name,
                        self.gender,
                        prestandardized=True
                    ),
                    fuzzy_identifier=middle_name_metaphone,
                    fuzzy_identifier_frequency=cfg.forename_metaphone_freq(
                        middle_name_metaphone,
                        self.gender
                    ),
                    p_error=cfg.p_minor_forename_error
                ))
            surname_metaphone = get_metaphone(self.surname)
            self.surname_info = FuzzyIdFreq(
                comparison_name="surname",
                exact_identifier=self.surname,
                exact_identifier_frequency=cfg.surname_freq(
                    self.surname, prestandardized=True),
                fuzzy_identifier=surname_metaphone,
                fuzzy_identifier_frequency=cfg.surname_metaphone_freq(
                    surname_metaphone),
                p_error=cfg.p_minor_surname_error
            )
            self.dob_info = IdFreq(
                comparison_name="DOB",
                identifier=self.dob,
                frequency=cfg.p_two_people_share_dob,
                p_error=0  # no typos allowed in dates of birth
            )
            self.gender_info = IdFreq(
                comparison_name="gender",
                identifier=self.gender,
                frequency=cfg.gender_freq(self.gender),
                p_error=cfg.p_gender_error
            )
            for i in range(len(self.postcodes)):
                postcode_unit = self.postcodes[i]
                postcode_sector = get_postcode_sector(postcode_unit)
                self.postcodes_info.append(FuzzyIdFreq(
                    comparison_name=f"postcode",
                    exact_identifier=postcode_unit,
                    exact_identifier_frequency=cfg.postcode_unit_freq(
                        postcode_unit, prestandardized=True),
                    fuzzy_identifier=postcode_sector,
                    fuzzy_identifier_frequency=cfg.postcode_sector_freq(
                        postcode_sector, prestandardized=True),
                    p_error=cfg.p_minor_postcode_error
                ))

    def __repr__(self) -> str:
        """
        Returns a string representation that can be used for reconstruction.
        """
        attrs = ["is_hashed"]
        attrs += self.HASHED_ATTRS if self.is_hashed else self.PLAINTEXT_ATTRS
        attrlist = [f"{a}={getattr(self, a)!r}" for a in attrs]
        return f"Person({', '.join(attrlist)})"

    def copy(self) -> "Person":
        """
        Returns a copy of this object.
        """
        return copy.deepcopy(self)

    # -------------------------------------------------------------------------
    # String and CSV formats
    # -------------------------------------------------------------------------

    def __str__(self) -> str:
        if self.is_hashed:
            return (
                f"Person("
                f"original_id={self.original_id}, "
                f"research_id={self.research_id},"
                f"hashed)"
            )
        else:
            details = ", ".join([
                f"original_id={self.original_id}",
                f"research_id={self.research_id}",
                " ".join([self.first_name] +
                         self.middle_names +
                         [self.surname]),
                f"gender={self.gender}",
                self.dob,
                " - ".join(self.postcodes)
            ])
            return f"Person({details}"

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
        return self.PLAINTEXT_ATTRS + list(self.other.keys())

    def plaintext_csv_dict(self) -> Dict[str, Any]:
        """
        Returns a dictionary suitable for :class:`csv.DictWriter`.
        """
        assert not self.is_hashed
        return self._csv_dict(self.PLAINTEXT_ATTRS)

    def hashed_csv_dict(self,
                        without_frequencies: bool = False,
                        include_original_id: bool = False) -> Dict[str, Any]:
        """
        Returns a dictionary suitable for :class:`csv.DictWriter`.

        Args:
            without_frequencies:
                Do not include frequency information. This makes the resulting
                file suitable for use as a sample, but not as a proband file.
            include_original_id:
                include the (potentially identifying) ``original_id`` data?
                Usually ``False``; may be ``True`` for validation.
        """
        assert self.is_hashed
        attrs = self.HASHED_ATTRS.copy()
        if without_frequencies:
            for a in self.HASHED_FREQUENCY_ATTRS:
                attrs.remove(a)
        if not include_original_id:
            attrs.remove("original_id")
        return self._csv_dict(attrs)

    @classmethod
    def _from_csv(cls,
                  cfg: MatchConfig,
                  rowdict: Dict[str, str],
                  attrs: List[str],
                  is_hashed: bool) -> "Person":
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
            elif attr in cls.INT_ATTRS:
                v = int(v) if v else None
            elif attr in cls.FLOAT_ATTRS:
                v = float(v) if v else None
            kwargs[attr] = v
        return Person(cfg=cfg, is_hashed=is_hashed, **kwargs)

    @classmethod
    def from_plaintext_csv(cls, cfg: MatchConfig,
                           rowdict: Dict[str, str]) -> "Person":
        """
        Returns a :class:`Person` object from a plaintext CSV row.

        Args:
            cfg: a configuration object
            rowdict: a CSV row, read via :class:`csv.DictReader`.
        """
        return cls._from_csv(cfg, rowdict,
                             cls.PLAINTEXT_ATTRS, is_hashed=False)

    @classmethod
    def from_hashed_csv(cls, cfg: MatchConfig,
                        rowdict: Dict[str, str]) -> "Person":
        """
        Returns a :class:`Person` object from a hashed CSV row.

        Args:
            cfg: a configuration object
            rowdict: a CSV row, read via :class:`csv.DictReader`.
        """
        return cls._from_csv(cfg, rowdict,
                             cls.HASHED_ATTRS, is_hashed=True)

    # -------------------------------------------------------------------------
    # Created hashed version
    # -------------------------------------------------------------------------

    def as_hashed(self) -> "Person":
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
            first_name_frequency = fr(_forename_freq(
                first_name, gender, prestandardized=True))
            fn_metaphone = get_metaphone(first_name)
            hashed_first_name_metaphone = _hash(fn_metaphone)
            first_name_metaphone_frequency = fr(_forename_metaphone_freq(
                fn_metaphone, gender))
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
        for i, mn in enumerate(middle_names):
            if mn:
                mn_metaphone = get_metaphone(mn)
                hashed_middle_names.append(
                    _hash(mn)
                )
                middle_name_frequencies.append(
                    fr(_forename_freq(mn, gender, prestandardized=True))
                )
                hashed_middle_name_metaphones.append(
                    _hash(mn_metaphone)
                )
                middle_name_metaphone_frequencies.append(
                    fr(_forename_metaphone_freq(mn_metaphone, gender))
                )

        surname = self.surname
        if surname:
            hashed_surname = _hash(surname)
            surname_frequency = fr(
                cfg.surname_freq(surname, prestandardized=True))
            sn_metaphone = get_metaphone(surname)
            hashed_surname_metaphone = _hash(sn_metaphone)
            surname_metaphone_frequency = fr(
                cfg.surname_metaphone_freq(sn_metaphone))
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
        for mn in postcodes:
            if mn:
                hashed_postcode_units.append(
                    _hash(mn)
                )
                postcode_unit_frequencies.append(
                    fr(_postcode_unit_freq(mn, prestandardized=True))
                )
                sector = get_postcode_sector(mn)
                hashed_postcode_sectors.append(
                    _hash(sector)
                )
                postcode_sector_frequencies.append(
                    fr(_postcode_sector_freq(sector))
                )

        return Person(
            cfg=cfg,
            is_hashed=True,

            original_id=self.original_id,
            research_id=self.research_id,

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
            debug=debug
        )

    # -------------------------------------------------------------------------
    # Comparison helper functions
    # -------------------------------------------------------------------------

    def _gen_comparisons(self, proband: "Person") \
            -> Generator[Optional[Comparison], None, None]:
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
            self, proband: "Person") -> Generator[Comparison, None, None]:
        """
        Generates comparisons for middle names.
        """
        cfg = self.cfg
        n_candidate_middle_names = len(self.middle_names_info)
        n_proband_middle_names = len(proband.middle_names_info)
        max_n_middle_names = max(n_candidate_middle_names, n_proband_middle_names)  # noqa
        min_n_middle_names = min(n_candidate_middle_names, n_proband_middle_names)  # noqa

        for i in range(max_n_middle_names):
            if i < min_n_middle_names:
                # -------------------------------------------------------------
                # Name present in both. Exact and partial matches
                # -------------------------------------------------------------
                yield self.middle_names_info[i].comparison(
                    proband.middle_names_info[i])
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

    def _comparisons_postcodes(self, other: "Person") -> \
            Generator[Comparison, None, None]:
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
        self.first_name_info.assert_has_frequency_info()
        for mni in self.middle_names_info:
            mni.assert_has_frequency_info()
        self.surname_info.assert_has_frequency_info()
        self.dob_info.assert_has_frequency_info()
        self.gender_info.assert_has_frequency_info()
        for pi in self.postcodes_info:
            pi.assert_has_frequency_info()

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

        self.postcodes[which] = mutate_postcode(self.postcodes[which],
                                                self.cfg)


# =============================================================================
# Result of a match attempt
# =============================================================================

class MatchResult(object):
    """
    Result of a comparison between a proband (person) and a sample (group of
    people).
    """
    def __init__(self,
                 winner: Person = None,
                 best_log_odds: float = MINUS_INFINITY,
                 second_best_log_odds: float = MINUS_INFINITY,
                 best_person: Person = None,
                 second_best_person: Person = None,
                 proband: Person = None):
        """
        Args:
            winner:
                The person in the sample who matches the proband, if there is
                a winner by our rules; ``None`` if there is no winner.
            best_log_odds:
                Natural log odds of the best candidate being the same as the
                proband, –∞ if there are no candidates
            second_best_log_odds:
                The log odds of the closest other contender, which may be  –∞.
            best_person:
                The person in the sample who is the closest match to the
                proband. May be ``None``. If there is a winner, this is also
                the best person -- but the best person may not be the winner
                (if they are not likely enough, or if there is another close
                contender).
            second_best_person:
                The runner-up (second-best) person, or ``None``.
            proband:
                The proband used for the comparison. (Helpful for parallel
                processing.)
        """
        self.winner = winner
        self.best_log_odds = best_log_odds
        self.second_best_log_odds = second_best_log_odds
        self.best_person = best_person
        self.second_best_person = second_best_person
        self.proband = proband

    @property
    def matched(self) -> bool:
        return self.winner is not None

    def __repr__(self) -> str:
        attrs = [
            f"winner={self.winner}",
            f"best_log_odds={self.best_log_odds}",
            f"second_best_log_odds={self.second_best_log_odds}",
            f"best_person={self.best_person}",
            f"second_best_person={self.second_best_person}",
            f"proband={self.proband}",
        ]
        return f"MatchResult({', '.join(attrs)}"


# =============================================================================
# People: a collection of Person objects
# =============================================================================
# Try staring at the word "people" for a while and watch it look odd...

class People(object):
    def __init__(self,
                 cfg: MatchConfig,
                 verbose: bool = False,
                 person: Person = None,
                 people: List[Person] = None) -> None:
        """
        Creates a blank collection.
        """
        self.cfg = cfg
        self.verbose = verbose
        self.people = []  # type: List[Person]
        self.dob_to_people = defaultdict(list)  # type: Dict[str, List[Person]]
        self.hashed_dob_to_people = defaultdict(list)  # type: Dict[str, List[Person]]  # noqa

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
            log.debug(f"Proband: {proband}. Sample size: {len(self.people)}. "
                      f"Shortlist ({len(shortlist)}): {txt_shortlist}")
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
            best_person=shortlist[best_idx] if best_idx >= 0 else None,
            second_best_person=(
                shortlist[second_best_idx] if second_best_idx >= 0 else None
            ),
            proband=proband,
        )
        result.winner = result.best_person

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
        elif best_log_odds < second_best_log_odds + cfg.exceeds_next_best_log_odds:  # noqa
            if verbose:
                log.debug(f"Second-best is too close to best")
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
        return People(cfg=self.cfg,
                      people=[p.as_hashed() for p in self.people])


# =============================================================================
# Test equivalence
# =============================================================================

class TestCondition(object):
    """
    Two representations of a person and whether they should match.
    """
    def __init__(self,
                 cfg: MatchConfig,
                 person_a: Person,
                 person_b: Person,
                 should_match: bool,
                 debug: bool = True) -> None:
        """
        Args:
            cfg: the master :class:`MatchConfig` object
            person_a: one representation of a person
            person_b: another representation of a person
            should_match: should they be treated as the same person?
            debug: be verbose?
        """
        self.cfg = cfg
        self.person_a = person_a
        self.person_b = person_b
        self.should_match = should_match
        log.info("- Making hashed versions for later")
        self.hashed_a = self.person_a.as_hashed()
        self.hashed_b = self.person_b.as_hashed()
        self.debug = debug

    def log_odds_same_plaintext(self) -> float:
        """
        Checks whether the plaintext person objects match.

        Returns:
            float: the log odds that they are the same person
        """
        return self.person_a.log_odds_same(self.person_b, debug=self.debug)

    def log_odds_same_hashed(self) -> float:
        """
        Checks whether the hashed versions match.

        Returns:
            float: the log odds that they are the same person
        """
        return self.hashed_a.log_odds_same(self.hashed_b, debug=self.debug)

    def matches_plaintext(self) -> Tuple[bool, float]:
        """
        Do the plaintext versions match, by threshold?

        Returns:
            tuple: (matches, log_odds)
        """
        log_odds = self.log_odds_same_plaintext()
        return self.cfg.person_matches(log_odds), log_odds

    def matches_hashed(self) -> Tuple[bool, float]:
        """
        Do the raw versions match, by threshold?

        Returns:
            bool: is there a match?
        """
        log_odds = self.log_odds_same_hashed()
        return self.cfg.person_matches(log_odds), log_odds

    def assert_correct(self) -> None:
        """
        Asserts that both the raw and hashed versions match, or don't match,
        according to ``self.should_match``.
        """
        log.info(f"Comparing:\n- {self.person_a!r}\n- {self.person_b!r}")

        log.info("(1) Comparing plaintext")
        matches_raw, log_odds_plaintext = self.matches_plaintext()
        p_plaintext = probability_from_log_odds(log_odds_plaintext)
        p_plain_str = f"P(match | D) = {p_plaintext}"
        if matches_raw == self.should_match:
            if matches_raw:
                log.info(f"... should and does match: {p_plain_str}")
            else:
                log.info(f"... should not and does not match: {p_plain_str}")
        else:
            log_odds = log_odds_plaintext
            msg = (
                f"Match failure: "
                f"matches_raw = {matches_raw}, "
                f"should_match = {self.should_match}, "
                f"log_odds = {log_odds}, "
                f"min_log_odds_for_match = {self.cfg.min_log_odds_for_match}, "
                f"P(match) = {probability_from_log_odds(log_odds)}, "
                f"person_a = {self.person_a}, "
                f"person_b = {self.person_b}"
            )
            log.critical(msg)
            raise AssertionError(msg)

        log.info(f"(2) Comparing hashed:\n- {self.hashed_a}\n- {self.hashed_b}")  # noqa
        matches_hashed, log_odds_hashed = self.matches_hashed()
        p_hashed = probability_from_log_odds(log_odds_hashed)
        p_hashed_str = f"P(match | D) = {p_hashed}"
        if matches_hashed == self.should_match:
            if matches_hashed:
                log.info(f"... should and does match: {p_hashed_str}")
            else:
                log.info(f"... should not and does not match: {p_hashed_str}")
        else:
            log_odds = log_odds_hashed
            msg = (
                f"Match failure: "
                f"matches_hashed = {matches_hashed}, "
                f"should_match = {self.should_match}, "
                f"log_odds = {log_odds}, "
                f"threshold = {self.cfg.min_log_odds_for_match}, "
                f"min_log_odds_for_match = {self.cfg.min_log_odds_for_match}, "
                f"P(match) = {probability_from_log_odds(log_odds)}, "
                f"person_a = {self.person_a}, "
                f"person_b = {self.person_b}, "
                f"hashed_a = {self.hashed_a}, "
                f"hashed_b = {self.hashed_b}"
            )
            log.critical(msg)
            raise AssertionError(msg)


# =============================================================================
# Comparing people
# =============================================================================

COMPARISON_OUTPUT_COLNAMES = [
    "proband_original_id",
    "proband_research_id",
    "matched",
    "log_odds_match",
    "p_match",
    "sample_match_original_id",
    "sample_match_research_id",
    "second_best_log_odds",
]
COMPARISON_EXTRA_COLNAMES = [
    "best_person_original_id",
    "best_person_research_id",
]


def compare_probands_to_sample(cfg: MatchConfig,
                               probands: People,
                               sample: People,
                               output_csv: str,
                               report_every: int = 100,
                               extra_validation_output: bool = False,
                               n_workers: int = CPU_COUNT,
                               max_chunksize: int = 100) -> None:
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
        rowdata = dict(
            proband_original_id=p.original_id,
            proband_research_id=p.research_id,
            matched=int(matched),
            log_odds_match=r.best_log_odds,
            p_match=probability_from_log_odds(r.best_log_odds),
            sample_match_original_id=w.original_id if matched else None,
            sample_match_research_id=w.research_id if matched else None,
            second_best_log_odds=r.second_best_log_odds,
        )
        if extra_validation_output:
            best_person = r.best_person
            rowdata["best_person_original_id"] = (
                best_person.original_id if best_person else None
            )
            rowdata["best_person_research_id"] = (
                best_person.research_id if best_person else None
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

    log.info(f"Comparing each proband to sample. There are "
             f"{n_probands} probands and {n_sample} in the sample.")
    parallel = n_workers > 1 and n_probands > 1
    colnames = COMPARISON_OUTPUT_COLNAMES
    if extra_validation_output:
        colnames += COMPARISON_EXTRA_COLNAMES
    rownum = 0
    time_start = time.time()
    with open(output_csv, "wt") as f:
        writer = csv.DictWriter(f, fieldnames=colnames)
        writer.writeheader()

        if parallel:
            chunksize = max(1, min(n_probands // n_workers, max_chunksize))
            # ... chunksize must be >= 1
            log.info(f"Using parallel processing with {n_workers} workers and "
                     f"chunksize of {chunksize}.")

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
                        chunksize=chunksize):
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
        n_workers: int = CPU_COUNT,
        max_chunksize: int = DEFAULT_MAX_CHUNKSIZE) -> None:
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
    """
    # Sample
    log.info("Loading (or caching) sample data")
    if sample_plaintext:
        if sample_cache_filename:
            log.info(f"Using sample cache: {sample_cache_filename}")
            try:
                (sample, ) = cache_load(sample_cache_filename)
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
    compare_fn = (do_cprofile(compare_probands_to_sample, sort="cumtime")
                  if profile else compare_probands_to_sample)
    compare_fn(
        cfg=cfg,
        probands=probands,
        sample=sample,
        output_csv=output_csv,
        extra_validation_output=extra_validation_output,
        n_workers=n_workers,
        max_chunksize=max_chunksize
    )


# =============================================================================
# Self-testing
# =============================================================================

def selftest(cfg: MatchConfig, set_breakpoint: bool = False,
             speedtest: bool = False) -> None:
    """
    Run self-tests or timing tests.

    Args:
        cfg:
            the master :class:`MatchConfig` object
        set_breakpoint:
            set a pdb breakpoint to explore objects from the Python console?
        speedtest:
            run speed tests only?
    """
    log.warning("Running tests...")
    log.warning("Building test conditions...")
    alice_bcd_unique_2000_add = Person(
        cfg=cfg,
        original_id=1,
        first_name="Alice",
        middle_names=["Beatrice", "Celia", "Delilah"],
        surname="Rarename",
        dob="2000-01-01",
        postcodes=["CB2 0QQ"]  # Addenbrooke's Hospital
    )
    alec_bcd_unique_2000_add = Person(
        cfg=cfg,
        original_id=2,
        first_name="Alec",  # same metaphone as Alice
        middle_names=["Beatrice", "Celia", "Delilah"],
        surname="Rarename",
        dob="2000-01-01",
        postcodes=["CB2 0QQ"]  # Addenbrooke's Hospital
    )
    bob_bcd_unique_2000_add = Person(
        cfg=cfg,
        original_id=3,
        first_name="Bob",
        middle_names=["Beatrice", "Celia", "Delilah"],
        surname="Rarename",
        dob="2000-01-01",
        postcodes=["CB2 0QQ"]  # Addenbrooke's Hospital
    )
    alice_bc_unique_2000_add = Person(
        cfg=cfg,
        original_id=4,
        first_name="Alice",
        middle_names=["Beatrice", "Celia"],
        surname="Rarename",
        dob="2000-01-01",
        postcodes=["CB2 0QQ"]  # Addenbrooke's Hospital
    )
    alice_b_unique_2000_add = Person(
        cfg=cfg,
        original_id=5,
        first_name="Alice",
        middle_names=["Beatrice"],
        surname="Rarename",
        dob="2000-01-01",
        postcodes=["CB2 0QQ"]  # Addenbrooke's Hospital
    )
    alice_jones_2000_add = Person(
        cfg=cfg,
        original_id=6,
        first_name="Alice",
        surname="Jones",
        dob="2000-01-01",
        postcodes=["CB2 0QQ"]  # Addenbrooke's Hospital
    )
    bob_smith_1950_psych = Person(
        cfg=cfg,
        original_id=7,
        first_name="Bob",
        surname="Smith",
        dob="1950-05-30",
        postcodes=["CB2 3EB"]  # Department of Psychology
        # postcodes=["AB12 3CD"]  # nonexistent postcode; will raise
    )
    alice_smith_1930 = Person(
        cfg=cfg,
        original_id=8,
        first_name="Alice",
        surname="Smith",
        dob="1930-01-01",
    )
    alice_smith_2000 = Person(
        cfg=cfg,
        original_id=9,
        first_name="Alice",
        surname="Smith",
        dob="2000-01-01",
    )
    alice_smith = Person(
        cfg=cfg,
        original_id=10,
        first_name="Alice",
        surname="Smith",
    )
    middle_test_1 = Person(
        cfg=cfg,
        original_id=11,
        first_name="Alice",
        middle_names=["Betty", "Caroline"],
        surname="Smith"
    )
    middle_test_2 = Person(
        cfg=cfg,
        original_id=12,
        first_name="Alice",
        middle_names=["Betty", "Dorothy", "Elizabeth"],
        surname="Smith"
    )
    all_people = [
        alice_bcd_unique_2000_add,
        alec_bcd_unique_2000_add,
        bob_bcd_unique_2000_add,
        alice_bc_unique_2000_add,
        alice_b_unique_2000_add,
        alice_jones_2000_add,
        bob_smith_1950_psych,
        alice_smith_1930,
        alice_smith_2000,
        alice_smith,
        middle_test_1,
        middle_test_2,
    ]
    all_people_hashed = [p.as_hashed() for p in all_people]
    test_values = [
        # Very easy match
        TestCondition(cfg=cfg,
                      person_a=alice_bcd_unique_2000_add,
                      person_b=alice_bcd_unique_2000_add,
                      should_match=True),
        # Easy match
        TestCondition(cfg=cfg,
                      person_a=alice_bc_unique_2000_add,
                      person_b=alice_b_unique_2000_add,
                      should_match=True),
        # Easy non-match
        TestCondition(cfg=cfg,
                      person_a=alice_jones_2000_add,
                      person_b=bob_smith_1950_psych,
                      should_match=False),
        # Very ambiguous (1)
        TestCondition(cfg=cfg,
                      person_a=alice_smith,
                      person_b=alice_smith_1930,
                      should_match=False),
        # Very ambiguous (2)
        TestCondition(cfg=cfg,
                      person_a=alice_smith,
                      person_b=alice_smith_2000,
                      should_match=False),
        TestCondition(cfg=cfg,
                      person_a=alice_bcd_unique_2000_add,
                      person_b=alec_bcd_unique_2000_add,
                      should_match=True),
        TestCondition(cfg=cfg,
                      person_a=alice_bcd_unique_2000_add,
                      person_b=bob_bcd_unique_2000_add,
                      should_match=False),
    ]  # type: List[TestCondition]
    people_plaintext = People(cfg=cfg, verbose=True)
    people_plaintext.add_people(all_people)
    people_hashed = People(cfg=cfg, verbose=True)
    people_hashed.add_people(all_people_hashed)

    if set_breakpoint:
        pdb.set_trace()

    if speedtest:
        # ---------------------------------------------------------------------
        # Timing tests
        # ---------------------------------------------------------------------
        log.warning("Testing comparison speed (do NOT use verbose logging)...")
        # NB Python has locals() and globals() but not nonlocals() so it's hard
        # to make this code work with a temporary function as you might hope.
        microsec_per_sec = 1e6
        n_for_speedtest = 10000

        t = microsec_per_sec * timeit.timeit(
            "alice_bcd_unique_2000_add.log_odds_same(alice_bcd_unique_2000_add)",  # noqa
            number=n_for_speedtest,
            globals=locals()
        ) / n_for_speedtest
        log.info(f"Plaintext full match: {t} μs per comparison")
        # On Wombat: 146 microseconds.
        # On Wombat 2020-04-24: 64 microseconds.

        t = microsec_per_sec * timeit.timeit(
            "alice_bcd_unique_2000_add.hashed().log_odds_same(alice_bcd_unique_2000_add.hashed())",  # noqa
            number=n_for_speedtest,
            globals=locals()
        ) / n_for_speedtest
        log.info(f"Hash two objects + full match: {t} μs per comparison")
        # On Wombat: 631 microseconds.
        # On Wombat 2020-04-24: 407 microseconds.

        t = microsec_per_sec * timeit.timeit(
            "alice_smith_1930.log_odds_same(alice_smith_2000, )",
            number=n_for_speedtest,
            globals=locals()
        ) / n_for_speedtest
        log.info(f"Plaintext DOB mismatch: {t} μs per comparison")
        # On Wombat: 13.6 microseconds.
        # On Wombat 2020-04-24: 6.1 microseconds.

        t = microsec_per_sec * timeit.timeit(
            "alice_smith_1930.hashed().log_odds_same(alice_smith_2000.hashed())",  # noqa
            number=n_for_speedtest,
            globals=locals()
        ) / n_for_speedtest
        log.info(f"Hash two objects + DOB mismatch: {t} μs per comparison")
        # On Wombat: 240 microseconds.
        # On Wombat 2020-04-24: 153 microseconds.

        t = microsec_per_sec * timeit.timeit(
            "alice_smith_1930.hashed()",
            number=n_for_speedtest,
            globals=locals()
        ) / n_for_speedtest
        log.info(f"Hash one object: {t} μs per comparison")
        # On Wombat: 104 microseconds.
        # On Wombat 2020-04-24: 71 microseconds.

        hashed_alice_smith_1930 = alice_smith_1930.as_hashed()
        hashed_alice_smith_2000 = alice_smith_2000.as_hashed()

        t = microsec_per_sec * timeit.timeit(
            "hashed_alice_smith_1930.log_odds_same(hashed_alice_smith_1930)",
            number=n_for_speedtest,
            globals=locals()
        ) / n_for_speedtest
        log.info(f"Compare two identical hashed objects: {t} μs per comparison")  # noqa
        # On Wombat 2020-04-024: 21.7 microseconds.

        t = microsec_per_sec * timeit.timeit(
            "hashed_alice_smith_1930.log_odds_same(hashed_alice_smith_2000)",
            number=n_for_speedtest,
            globals=locals()
        ) / n_for_speedtest
        log.info(f"Compare two DOB-mismatched hashed objects: {t} μs per comparison")  # noqa
        # On Wombat 2020-04-024: 6.4 microseconds.

        return  # timing tests only

    # -------------------------------------------------------------------------
    # Main self-tests
    # -------------------------------------------------------------------------

    for surname in ["Smith", "Jones", "Blair", "Cardinal", "XYZ"]:
        f = cfg.surname_freq(surname)
        log.info(f"Surname frequency for {surname}: {f}")

    for forename, gender in [("James", GENDER_MALE),
                             ("Rachel", GENDER_FEMALE),
                             ("Phoebe", GENDER_FEMALE),
                             ("Elizabeth", GENDER_FEMALE),
                             ("Elizabeth", GENDER_MALE),
                             ("Elizabeth", ""),
                             ("Rowan", GENDER_FEMALE),
                             ("Rowan", GENDER_MALE),
                             ("Rowan", ""),
                             ("XYZ", "")]:
        f = cfg.forename_freq(forename, gender)
        log.info(f"Forename frequency for {forename}, gender {gender}: {f}")

    # Examples are hospitals and colleges in Cambridge (not residential) but
    # it gives a broad idea.
    for postcode in ["CB2 0QQ", "CB2 0SZ", "CB2 3EB", "CB3 9DF"]:
        p = cfg.postcode_unit_population(postcode)
        log.info(f"Calculated population for postcode unit {postcode}: {p}")

    for ps in ["CB2 0", "CB2 1", "CB2 2", "CB2 3"]:
        p = cfg.postcode_sector_population(ps)
        log.info(f"Calculated population for postcode sector {ps}: {p}")

    log.warning("Testing comparisons...")
    for i, test in enumerate(test_values, start=1):
        log.warning(f"Comparison {i}...")
        test.assert_correct()

    log.warning("Testing proband-versus-sample...")
    for i in range(len(all_people)):
        proband_plaintext = all_people[i]
        log.warning(f"Plaintext search with proband: {proband_plaintext}")
        plaintext_winner = people_plaintext.get_unique_match(proband_plaintext)
        log.warning(f"... WINNER: {plaintext_winner}")
        log.warning(f"Hashed search with proband: {proband_plaintext}\n")
        proband_hashed = all_people_hashed[i]  # same order
        hashed_winner = people_hashed.get_unique_match(proband_hashed)
        log.warning(f"... WINNER: {hashed_winner}")

    log.warning(f"Testing middle name comparisons between...\n"
                f"{middle_test_1}\n"
                f"{middle_test_2}")
    # noinspection PyProtectedMember
    for comp in middle_test_1._comparisons_middle_names(middle_test_2):
        log.info(comp)

    log.warning("... tests complete.")


# =============================================================================
# Loading people data
# =============================================================================

def read_people_2(cfg: MatchConfig,
                  csv_filename: str,
                  plaintext: bool = True,
                  alternate_groups: bool = False) -> Tuple[People, People]:
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


def read_people(cfg: MatchConfig,
                csv_filename: str,
                plaintext: bool = True) -> People:
    """
    Read a list of people from a CSV file.

    See :func:`read_people_2`, but this version doesn't offer the feature of
    splitting into two groups, and returns only a single :class:`People`
    object.
    """
    people, _ = read_people_2(cfg,
                              csv_filename,
                              plaintext=plaintext,
                              alternate_groups=False)
    return people


# =============================================================================
# Validation 1
# =============================================================================

def make_deletion_data(people: People, cfg: MatchConfig) -> People:
    """
    Makes a copy of the supplied data set with deliberate deletions applied.

    Surnames and DOBs are excepted as we require exact matches for those.
    """
    deletion_data = People(cfg)
    for person in people.people:
        modified_person = person.copy()
        modified_person.debug_delete_something()
        log.debug(f"Deleted:\nFROM: {person}\nTO  : {modified_person}")
        deletion_data.add_person(modified_person)
    return deletion_data


def make_typo_data(people: People, cfg: MatchConfig) -> People:
    """
    Makes a copy of the supplied data set with deliberate typos applied.

    Surnames and DOBs are excepted as we require exact matches for those.
    """
    typo_data = People(cfg)
    for person in people.people:
        modified_person = person.copy()
        modified_person.debug_mutate_something()
        log.debug(f"Mutated:\nFROM: {person}\nTO  : {modified_person}")
        typo_data.add_person(modified_person)
    return typo_data


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
    return name[:which] + chr(replacement_ord) + name[which + 1:]


def mutate_postcode(postcode: str, cfg: MatchConfig) -> str:
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
        mutated = postcode[:which] + chr(replacement_ord) + postcode[which + 1:]
        if cfg.is_valid_postcode(mutated):
            return mutated


VALIDATION_OUTPUT_COLNAMES = [
    "collection_name",
    "in_sample",
    "deletions",
    "typos",

    "is_hashed",
    "original_id",
    "winner_id",
    "best_match_id",
    "best_log_odds",
    "second_best_log_odds",
    "second_best_match_id",

    "correct_if_winner",
    "leader_advantage",
]
VALIDATION_OUTPUT_CSV_HELP = (
    f"Header row present. Columns: {VALIDATION_OUTPUT_COLNAMES}.")


def validate_1(cfg: MatchConfig,
               people_csv: str,
               output_csv: str,
               cache_filename: str = None,
               seed: int = 1234,
               report_every: int = 100) -> None:
    """
    Read data and perform split-half validation.

    Args:
        cfg: the master :class:`MatchConfig` object
        people_csv: CSV of people; see :func:`read_people`.
        cache_filename: cache filename, for faster loading
        output_csv: output filename
        seed: RNG seed
        report_every: report progress every n rows
    """
    # -------------------------------------------------------------------------
    # Load and hash data
    # -------------------------------------------------------------------------
    try:
        if not cache_filename:
            raise FileNotFoundError
        (
            in_plaintext, out_plaintext,
            in_hashed, out_hashed,
            in_deletions, out_deletions,
            in_deletions_hashed, out_deletions_hashed,
            in_typos, out_typos,
            in_typos_hashed, out_typos_hashed,
        ) = cache_load(cache_filename)
        log.info(f"Read from cache: {cache_filename}")
    except FileNotFoundError:
        in_plaintext, out_plaintext = read_people_2(
            cfg, people_csv, alternate_groups=True)
        log.info(f"Seeding random number generator with: {seed}")
        random.seed(seed)
        log.info("Making copies with deliberate deletions...")
        in_deletions = make_deletion_data(in_plaintext, cfg)
        out_deletions = make_deletion_data(out_plaintext, cfg)
        log.info("Making copies with deliberate typos...")
        in_typos = make_typo_data(in_plaintext, cfg)
        out_typos = make_typo_data(out_plaintext, cfg)

        log.info("Hashing...")
        in_hashed = in_plaintext.hashed()
        out_hashed = out_plaintext.hashed()
        in_deletions_hashed = in_deletions.hashed()
        out_deletions_hashed = out_deletions.hashed()
        in_typos_hashed = in_typos.hashed()
        out_typos_hashed = out_typos.hashed()
        log.info("... done")

        if cache_filename:
            cache_save(cache_filename, [
                in_plaintext, out_plaintext,
                in_hashed, out_hashed,
                in_deletions, out_deletions,
                in_deletions_hashed, out_deletions_hashed,
                in_typos, out_typos,
                in_typos_hashed, out_typos_hashed,
            ])
    # -------------------------------------------------------------------------
    # Calculate validation data and save it
    # -------------------------------------------------------------------------
    data = [
        # people, collection_name, sample, in_sample, deletions, typos
        (in_plaintext, "in_plaintext", in_plaintext, True, False, False),
        (out_plaintext, "out_plaintext", in_plaintext, False, False, False),
        (in_hashed, "in_hashed", in_hashed, True, False, False),
        (out_hashed, "out_hashed", in_hashed, False, False, False),

        (in_deletions, "in_deletions", in_plaintext, True, True, False),
        (out_deletions, "out_deletions", in_plaintext, False, True, False),
        (in_deletions_hashed, "in_deletions_hashed", in_hashed, True, True, False),  # noqa
        (out_deletions_hashed, "out_deletions_hashed", in_hashed, False, True, False),  # noqa

        (in_typos, "in_typos", in_plaintext, True, False, True),
        (out_typos, "out_typos", in_plaintext, False, False, True),
        (in_typos_hashed, "in_typos_hashed", in_hashed, True, False, True),
        (out_typos_hashed, "out_typos_hashed", in_hashed, False, False, True),
    ]  # type: List[Tuple[People, str, People, bool, bool, bool]]
    log.info(f"Writing to: {output_csv}")
    with open(output_csv, "wt") as f:
        writer = csv.DictWriter(f, fieldnames=VALIDATION_OUTPUT_COLNAMES)
        writer.writeheader()
        i = 1  # row 1 is the header
        for people, collection_name, sample, in_sample, deletions, typos in data:  # noqa
            for person in people.people:
                i += 1
                if i % report_every == 0:
                    log.info(f"... creating CSV row {i}")
                result = sample.get_unique_match_detailed(person)

                if (math.isfinite(result.best_log_odds) and
                        math.isfinite(result.second_best_log_odds)):
                    leader_advantage = (
                        result.best_log_odds - result.second_best_log_odds
                    )
                else:
                    leader_advantage = None
                best_match_id = (
                    result.best_person.original_id if result.best_person
                    else None
                )
                correct_if_winner = (
                    int(best_match_id == person.original_id) if result.winner
                    else None
                )

                rowdata = dict(
                    # As of Python 3.6, keyword order is preserved:
                    # https://docs.python.org/3/library/collections.html#collections.OrderedDict  # noqa
                    # https://www.python.org/dev/peps/pep-0468/
                    # ... but it doesn't matter since we're using a DictWriter.
                    collection_name=collection_name,
                    in_sample=int(in_sample),
                    deletions=int(deletions),
                    typos=int(typos),

                    is_hashed=int(person.is_hashed),
                    original_id=person.original_id,
                    winner_id=(
                        result.winner.original_id if result.winner else None
                    ),
                    best_match_id=best_match_id,
                    best_log_odds=result.best_log_odds,
                    second_best_log_odds=result.second_best_log_odds,
                    second_best_match_id=(
                        result.second_best_person.original_id
                        if result.second_best_person else None
                    ),

                    correct_if_winner=correct_if_winner,
                    leader_advantage=leader_advantage,
                )
                writer.writerow(rowdata)
    log.info("... done")


# =============================================================================
# Hash plaintext to encrypted CSV
# =============================================================================

def hash_identity_file(cfg: MatchConfig,
                       input_csv: str,
                       output_csv: str,
                       without_frequencies: bool = False,
                       include_original_id: bool = False) -> None:
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
        include_original_id:
            Include the (potentially identifying) ``original_id`` data? Usually
            ``False``; may be ``True`` for validation.
    """
    if include_original_id:
        log.warning("include_original_id is set; use this for validation only")
    with open(input_csv, "rt") as infile, open(output_csv, "wt") as outfile:
        reader = csv.DictReader(infile)
        writer = csv.DictWriter(outfile, fieldnames=Person.HASHED_ATTRS)
        writer.writeheader()
        for inputrow in reader:
            plaintext_person = Person.from_plaintext_csv(cfg, inputrow)
            hashed_person = plaintext_person.as_hashed()
            writer.writerow(hashed_person.hashed_csv_dict(
                without_frequencies=without_frequencies,
                include_original_id=include_original_id))


# =============================================================================
# Validation 2
# =============================================================================

# -----------------------------------------------------------------------------
# CRS/CDL
# -----------------------------------------------------------------------------

def _get_cdl_postcodes(engine: Engine,
                       cdl_m_number: int) -> List[str]:
    """
    Fetches distinct valid postcodes for a given person, from CRS/CDL.

    Args:
        engine:
            SQLAlchemy engine
        cdl_m_number:
            CRS/CDL primary key ("M number")

    Returns:
        list: of postcodes
    """
    raise NotImplementedError("CDL postcodes: in chronological order")


def _get_cdl_middle_names(engine: Engine,
                          cdl_m_number: int) -> List[str]:
    """
    Fetches distinct middle names for a given person, from CRS/CDL.

    Args:
        engine:
            SQLAlchemy engine
        cdl_m_number:
            CRS/CDL primary key ("M number")

    Returns:
        list: of middle names

    """
    raise NotImplementedError


def validate_2_fetch_cdl(cfg: MatchConfig,
                         url: str,
                         hash_key: str,
                         echo: bool = False) -> Generator[Person, None, None]:
    """
    Generates IDENTIFIED people from CPFT's CRS/CRL source database.

    See :func:`validate_2_fetch_rio` for notes.
    """
    raise NotImplementedError("Fix SQL as below")
    raise NotImplementedError("ethnicity, icd10_dx_present, age_at_first_referral")
    sql = text("""

        SELECT
            XXX AS cdl_m_number  -- ***
            CAST(ci.NHS_IDENTIFIER AS BIGINT) AS nhs_number,
            mpi.FORENAME AS first_name,
            mpi.SURNAME AS surname,
            gender = CASE mpi.GENDER
                WHEN 'Female' THEN 'F'
                WHEN 'Male' THEN 'M'
                WHEN 'Not Specified' THEN 'X'
                ELSE ''  
                -- 'Not Known' is the CRS/CDL "unknown" value
            END AS gender,
            CAST(mpi.DTTM_OF_BIRTH, DATE) AS dob
        FROM
            MPI as mpi

    """)
    hasher = Hasher(hash_key)
    _hash = hasher.hash  # hashing function
    engine = create_engine(url, echo=echo)
    result = engine.execute(sql)  # type: ResultProxy
    for row in result:
        cdl_m_number = row["cdl_m_number"]
        middle_names = _get_cdl_middle_names(engine, cdl_m_number)
        postcodes = _get_cdl_postcodes(engine, cdl_m_number)
        nhs_number = row["nhs_number"]
        research_id = _hash(nhs_number)
        other["age_at_first_referral"] = XXX
        other["ethnicity"] = XXX
        other["icd10_dx_present"] = XXX
        p = Person(
            cfg=cfg,
            original_id=nhs_number,
            research_id=research_id,
            first_name=row["first_name"] or "",
            middle_names=middle_names,
            surname=row["surname"] or "",
            gender=row["gender"] or "",
            dob=row["dob"] or "",
            postcodes=postcodes,
            other=other
        )
        yield p


# -----------------------------------------------------------------------------
# RiO
# -----------------------------------------------------------------------------

def _get_rio_postcodes(engine: Engine,
                       rio_client_id: str) -> List[str]:
    """
    Fetches distinct valid postcodes for a given person, from RiO.

    Args:
        engine:
            SQLAlchemy engine
        rio_client_id:
            RiO primary key (``ClientId``)

    Returns:
        list: of postcodes

    """
    raise NotImplementedError("RiO postcodes: change order to chronological")
    sql = text("""

        SELECT
            DISTINCT UPPER(PostCode) AS upper_postcode
        FROM
            ClientAddress
        WHERE
            ClientID = :client_id
            AND PostCode IS NOT NULL
            AND LEN(PostCode) >= 6  -- minimum for valid postcode
        ORDER BY
            upper_postcode

    """)
    rows = engine.execute(sql, client_id=rio_client_id)
    postcodes = [
        row[0] for row in rows
        if POSTCODE_REGEX.match(row[0])
    ]
    return postcodes


def _get_rio_middle_names(engine: Engine,
                          rio_client_id: str) -> List[str]:
    """
    Fetches distinct middle names for a given person, from RiO.

    Args:
        engine:
            SQLAlchemy engine
        rio_client_id:
            RiO primary key (``ClientId``)

    Returns:
        list: of middle names

    """
    sql = text("""

        SELECT
            -- OK to use UPPER() with NULL values. Result is, of course, NULL.
            -- GivenName1 should be the first name.
            UPPER(GivenName2) AS middle_name_1,
            UPPER(GivenName3) AS middle_name_2
            UPPER(GivenName4) AS middle_name_3
            UPPER(GivenName5) AS middle_name_4
        FROM
            ClientName
        WHERE
            ClientID = :client_id

    """)
    rows = engine.execute(sql, client_id=rio_client_id)
    raise NotImplementedError("fetch only one row? Ensure names are ordered")
    return middle_names


def validate_2_fetch_rio(cfg: MatchConfig,
                         url: str,
                         hash_key: str,
                         echo: bool = False) -> Generator[Person, None, None]:
    """
    Generates IDENTIFIED people from CPFT's RiO source database.

    The connection to any such database is HIGHLY confidential; it sits on a
    secure server within a secure network and access to this specific database
    is very restricted -- to administrators only.

    Args:
        cfg:
            Configuration object. 
        url:
            SQLAlchemy URL.
        hash_key:
            Key for hashing NHS number (original ID) to research ID.
        echo:
            Echo SQL?

    Yields:
        :class:`Person` objects
        
    Generating postcodes in SQL as semicolon-separated values: pretty hard.
    The challenges are:

    - String concatenation

      - Prior to SQL Server 2017:
        https://stackoverflow.com/questions/6899/how-to-create-a-sql-server-function-to-join-multiple-rows-from-a-subquery-into

        .. code-block:: none

            SELECT
                CAST(ci.NNN AS BIGINT) AS original_id,  -- NHS number
                -- ...

                STUFF(
                    (
                        SELECT
                            ';' + ca.PostCode
                        FROM
                            ClientAddress AS ca
                        WHERE
                            ca.ClientID = ci.ClientID
                            AND ca.PostCode IS NOT NULL
                            AND ca.PostCode != ''
                        FOR XML PATH('')
                    ),
                    1, 1, ''
                ) AS postcodes
            FROM
                ClientIndex AS ci

      - From SQL Server 2017: the ``STRING_AGG(..., ';')`` construct.
        Still tricky, though.

    - We need to return people with no postcodes.

    - We must deal with a profusion of invalid postcodes -- and SQL Server 
      doesn't support proper regular expressions.

    SQLAlchemy Core query to Python dict:
    
    - https://stackoverflow.com/questions/1958219/convert-sqlalchemy-row-object-to-python-dict

    """  # noqa

    raise NotImplementedError("ethnicity, icd10_dx_present, age_at_first_referral")
    sql = text("""
    
        -- We use the original raw RiO database, not the CRATE-processed one.
    
        SELECT
            ci.ClientID AS rio_client_id,
            CAST(ci.NNN AS BIGINT) AS nhs_number,
            ci.Firstname AS first_name,
            ci.Surname AS surname,
            gender = CASE ci.Gender
                WHEN 'F' THEN 'F'
                WHEN 'M' THEN 'M'
                WHEN 'X' THEN 'X'
                ELSE ''  
                -- 'U' is the RiO "unknown" value
            END AS gender,
            CAST(ci.DateOfBirth AS DATE) AS dob
        FROM
            ClientIndex AS ci
        WHERE
            -- Restrict to patients with NHS numbers:
            (ci.NNNStatus = 1 OR ci.NNNStatus = 2)
            AND NOT (ci.NNN IS NULL OR ci.NNN = '') 
            -- 2 = NHS number verified; see table NNNStatus
            -- Most people have status 1 (about 119k people), compared to
            -- about 80k for status 2 (on 2020-04-28). Then about 6k have
            -- status 0 ("trace/verification required"), and about 800 have
            -- status 3 ("no match found"). Other codes not present.
            -- A very small number (~40) have a null NHS number despite an
            -- OK-looking status flag; we'll skip them.
    
    """)
    hasher = Hasher(hash_key)
    _hash = hasher.hash  # hashing function
    engine = create_engine(url, echo=echo)
    result = engine.execute(sql)  # type: ResultProxy
    for row in result:
        rio_client_id = row["rio_client_id"]
        middle_names = _get_rio_middle_names(engine, rio_client_id)
        postcodes = _get_rio_postcodes(engine, rio_client_id)
        nhs_number = row["nhs_number"]
        research_id = _hash(nhs_number)
        other = OrderedDict()
        other["age_at_first_referral"] = XXX
        other["ethnicity"] = XXX
        other["icd10_dx_present"] = XXX
        p = Person(
            cfg=cfg,
            original_id=nhs_number,
            research_id=research_id,
            first_name=row["first_name"] or "",
            middle_names=middle_names,
            surname=row["surname"] or "",
            gender=row["gender"] or "",
            dob=row["dob"] or "",
            postcodes=postcodes,
            other=other
        )
        yield p


# -----------------------------------------------------------------------------
# Comon functions
# -----------------------------------------------------------------------------

def save_people_from_db(people: Iterable[Person],
                        output_csv: str,
                        report_every: int = 1000) -> None:
    """
    Saves people (in plaintext) from a function that generates them from a
    database.

    Args:
        people:
            iterable of :class:`Person`
        output_csv:
            output filename
        report_every:
            report progress every n people
    """
    rownum = 0
    with open(output_csv, "wt") as f:
        for i, p in enumerate(people):
            if i == 0:
                # This allows us to do custom headers for "other" info
                writer = csv.DictWriter(f, fieldnames=p.plaintext_csv_columns())  # noqa
                writer.writeheader()
            writer.writerow(p.plaintext_csv_dict())
            rownum += 1
            if rownum % report_every == 0:
                log.info(f"Processing person #{rownum}")


# =============================================================================
# Long help strings
# =============================================================================

HELP_COMPARISON = f"""
    Comparison rules:

    - People MUST match on DOB and surname (or surname metaphone), or hashed
      equivalents, to be considered a plausible match.
    - Only plausible matches proceed to the Bayesian comparison.
    
    Output file format:
    
    - CSV file with header.
    - Columns: {COMPARISON_OUTPUT_COLNAMES}

      - proband_original_id
        Original (identifiable?) ID of the proband. Taken from the input.
        Optional -- may be blank for de-identified comparisons.

      - proband_research_id
        Research ID (de-identified?) of the proband. Taken from the input.
      
      - matched
        Boolean. Was a matching person (a "winner") found in the sample, who
        is to be considered a match to the proband? To give a match requires
        (a) that the log odds for the winner reaches a threshold, and (b) that
        the log odds for the winner exceeds the log odds for the runner-up by
        a certain amount (because a mismatch may be worse than a failed match).

      - log_odds_match
        Log (ln) odds that the winner in the sample is a match to the proband.

      - p_match
        Probability that the winner in the sample is a match.

      - sample_match_original_id
        Original ID of the "winner" in the sample (the closest match to the
        proband). Optional -- may be blank for de-identified comparisons.

      - sample_match_research_id
        Research ID of the winner in the sample.

      - second_best_log_odds
        Log odds of the runner up (the second-closest match) being the same
        person as the proband.

    - If '--extra_validation_output' is used, the following columns are added:

      - best_person_original_id
        Original ID of the closest-matching person in the sample, EVEN IF THEY
        DID NOT WIN.

      - best_person_research_id
        Research ID of the closest-matching person in the sample, EVEN IF THEY
        DID NOT WIN.

    - The results file is NOT necessarily sorted as the input proband file was
      (not sorting improves parallel processing efficiency).
"""

HELP_VALIDATE_1 = """
    Takes an identifiable list of people (typically a short list of imaginary
    people!) and validates the matching process.

    This is done by splitting the input list into two groups (alternating),
    then comparing a list of probands either against itself (there should be
    matches) or against the other group (there should generally not be).
    The process is carried out in cleartext (plaintext) and hashed. At times
    it's made harder by introducing deletions or mutations (typos) into one of
    the groups.

    Here's a specimen test CSV file to use, with entirely made-up people and
    institutional (not personal) postcodes in Cambridge:

original_id,research_id,first_name,middle_names,surname,dob,gender,postcodes
1,r1,Alice,Zara,Smith,1931-01-01,F,CB2 0QQ
2,r2,Bob,Yorick,Jones,1932-01-01,M,CB2 3EB
3,r3,Celia,Xena,Wright,1933-01-01,F,CB2 1TP
4,r4,David,William;Wallace,Cartwright,1934-01-01,M,CB2 8PH;CB2 1TP
5,r5,Emily,Violet,Fisher,1935-01-01,F,CB3 9DF
6,r6,Frank,Umberto,Williams,1936-01-01,M,CB2 1TQ
7,r7,Greta,Tilly,Taylor,1937-01-01,F,CB2 1DQ
8,r8,Harry,Samuel,Davies,1938-01-01,M,CB3 9ET
9,r9,Iris,Ruth,Evans,1939-01-01,F,CB3 0DG
10,r10,James,Quentin,Thomas,1940-01-01,M,CB2 0SZ
11,r11,Alice,,Smith,1931-01-01,F,CB2 0QQ

    Explanation of the output format:

    - 'collection_name' is a human-readable name summarizing the next four;
    - 'in_sample' (boolean) is whether the probands are in the sample;
    - 'deletions' (boolean) is whether random items have been deleted from
       the probands;
    - 'typos' (boolean) is whether random typos have been made in the
       probands;

    - 'is_hashed' (boolean) is whether the proband and sample are hashed;
    - 'original_id' is the gold-standard ID of the proband;
    - 'winner_id' is the ID of the best-matching person in the sample if they
      were a good enough match to win;
    - 'best_match_id' is the ID of the best-matching person in the sample;
    - 'best_log_odds' is the calculated log (ln) odds that the proband and the 
      sample member identified by 'winner_id' are the sample person (ideally
      high if there is a true match, low if not);
    - 'second_best_log_odds' is the calculated log odds of the proband and the
      runner-up being the same person (ideally low);
    - 'second_best_match_id' is the ID of the second-best matching person, if
      there is one;

    - 'correct_if_winner' is whether the proband and winner IDs are te same
      (ideally true);
    - 'leader_advantage' is the log odds by which the winner beats the
      runner-up (ideally high indicating a strong preference for the winner
      over the runner-up).

    Clearly, if the probands are in the sample, then a match may occur; if not,
    no match should occur. If hashing is in use, this tests de-identified
    linkage; if not, this tests identifiable linkage. Deletions and typos
    may reduce (but we hope not always eliminate) the likelihood of a match,
    and we don't want to see mismatches.

    For n input rows, each basic set test involves n^2/2 comparisons.
    Then we repeat for typos and deletions. (There is no point in DOB typos
    as our rules preclude that.)

    Examine:
    - P(unique plaintext match | proband in sample) -- should be close to 1.
    - P(unique plaintext match | proband in others) -- should be close to 0.
    - P(unique hashed match | proband in sample) -- should be close to 1.
    - P(unique hashed match | proband in others) -- should be close to 0.
"""

DEFAULT_CDL_PLAINTEXT = "validate2_cdl_DANGER_IDENTIFIABLE.csv"
DEFAULT_RIO_PLAINTEXT = "validate2_rio_DANGER_IDENTIFIABLE.csv"
DEFAULT_CDL_HASHED = "validate2_cdl_hashed.csv"
DEFAULT_RIO_HASHED = "validate2_rio_hashed.csv"
CAMBS_POPULATION = 852523  # 2018 estimate; https://cambridgeshireinsight.org.uk/population/  # noqa
HELP_VALIDATE_2_CDL = f"""
    Validation #2. Sequence:

    1. Fetch

    - crate_fuzzy_id_match validate2_fetch_cdl --output {DEFAULT_CDL_PLAINTEXT} --url <SQLALCHEMY_URL_CDL>
    - crate_fuzzy_id_match validate2_fetch_rio --output {DEFAULT_RIO_PLAINTEXT} --url <SQLALCHEMY_URL_RIO>

    2. Hash

    - crate_fuzzy_id_match hash --input {DEFAULT_CDL_PLAINTEXT} --output {DEFAULT_CDL_HASHED} --include_original_id --allow_default_hash_key
    - crate_fuzzy_id_match hash --input {DEFAULT_RIO_PLAINTEXT} --output {DEFAULT_RIO_HASHED} --include_original_id --allow_default_hash_key

    3. Compare

    - crate_fuzzy_id_match compare_plaintext --population_size {CAMBS_POPULATION} --probands {DEFAULT_CDL_PLAINTEXT} --sample {DEFAULT_RIO_PLAINTEXT} --output cdl_to_rio_plaintext.csv --extra_validation_output
    - crate_fuzzy_id_match compare_hashed_to_hashed --population_size {CAMBS_POPULATION} --probands {DEFAULT_CDL_HASHED} --sample {DEFAULT_RIO_HASHED} --output cdl_to_rio_hashed.csv --extra_validation_output
    - crate_fuzzy_id_match compare_plaintext --population_size {CAMBS_POPULATION} --probands {DEFAULT_RIO_PLAINTEXT} --sample {DEFAULT_CDL_PLAINTEXT} --output rio_to_cdl_plaintext.csv --extra_validation_output
    - crate_fuzzy_id_match compare_hashed_to_hashed --population_size {CAMBS_POPULATION} --probands {DEFAULT_RIO_HASHED} --sample {DEFAULT_CDL_HASHED} --output rio_to_cdl_hashed.csv --extra_validation_output
"""  # noqa


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    """
    Command-line entry point.
    """
    default_names_dir = os.path.abspath(os.path.join(
        THIS_DIR, "..", "..", "working"))
    default_postcodes_csv = os.path.abspath(os.path.expanduser(
        "~/dev/ons/ONSPD_Nov2019/unzipped/Data/ONSPD_NOV_2019_UK.csv"))
    appname = "crate"
    default_cache_dir = os.path.join(appdirs.user_data_dir(appname=appname))

    # -------------------------------------------------------------------------
    # Argument parser
    # -------------------------------------------------------------------------

    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        description="Identity matching via hashed fuzzy identifiers",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--version", action="version",
        version=f"CRATE {CRATE_VERSION}")
    parser.add_argument(
        '--allhelp',
        action=ShowAllSubparserHelpAction,
        help='show help for all commands and exit')

    # -------------------------------------------------------------------------
    # Common arguments
    # -------------------------------------------------------------------------

    display_group = parser.add_argument_group("display options")
    display_group.add_argument(
        "--verbose", action="store_true",
        help="Be verbose"
    )

    hasher_group = parser.add_argument_group("hasher (secrecy) options")
    hasher_group.add_argument(
        "--key", type=str,
        default=DEFAULT_HASH_KEY,
        help="Key (passphrase) for hasher"
    )
    hasher_group.add_argument(
        "--allow_default_hash_key", action="store_true",
        help="Allow the default hash key to be used beyond tests. INADVISABLE!"
    )
    hasher_group.add_argument(
        "--rounding_sf", type=int, default=5,
        help="Number of significant figures to use when rounding frequencies "
             "in hashed version"
        # 3 may be too small, e.g.
        # surname Smith 0.01006, metaphone SM0 0.010129999999999998
        # ... would be the same at 3sf.
    )

    priors_group = parser.add_argument_group(
        "frequency information for prior probabilities")
    priors_group.add_argument(
        "--forename_sex_freq_csv", type=str,
        default=os.path.join(default_names_dir, "us_forename_sex_freq.csv"),
        help=f'CSV file of "name, sex, frequency" pairs for forenames. '
             f'You can generate one via {CRATE_FETCH_WORDLISTS}.'
    )
    priors_group.add_argument(
        "--forename_cache_filename", type=str,
        default=os.path.join(default_cache_dir, "fuzzy_forename_cache.pickle"),
        help="File in which to store cached forename info (to speed loading)"
    )
    priors_group.add_argument(
        "--surname_freq_csv", type=str,
        default=os.path.join(default_names_dir, "us_surname_freq.csv"),
        help=f'CSV file of "name, frequency" pairs for forenames. '
             f'You can generate one via {CRATE_FETCH_WORDLISTS}.'
    )
    priors_group.add_argument(
        "--surname_cache_filename", type=str,
        default=os.path.join(default_cache_dir, "fuzzy_surname_cache.pickle"),
        help="File in which to store cached surname info (to speed loading)"
    )
    priors_group.add_argument(
        "--name_min_frequency", type=float, default=5e-6,
        help="Minimum base frequency for names. If a frequency is less than "
             "this, use this minimum. Allowing extremely low frequencies may "
             "increase the chances of a spurious match. Note also that "
             "typical name frequency tables don't give very-low-frequency "
             "information. For example, for US census forename/surname "
             "information, below 0.001 percent they report 0.000 percent; so "
             "a reasonable minimum is 0.0005 percent or 0.000005 or 5e-6."
    )
    priors_group.add_argument(
        "--p_middle_name_n_present", type=str, default="0.8,0.1375",
        help="CSV list of probabilities that a randomly selected person has a "
             "certain number of middle names. The first number is P(has a "
             "first middle name). The second number is P(has a second middle "
             "name | has a first middle name), and so on. The last number "
             "present will be re-used ad infinitum if someone has more names."
    )
    priors_group.add_argument(
        "--population_size", type=int, default=UK_POPULATION_2017,
        help="Size of the whole population, from which we calculate the "
             "baseline log odds that two people, randomly selected (and "
             "replaced) from the population are the same person."
    )
    priors_group.add_argument(
        "--birth_year_pseudo_range", type=float, default=90,
        help=f"Birth year pseudo-range. The sole purpose is to calculate the "
             f"probability of two random people sharing a DOB, which is taken "
             f"as 1/({DAYS_PER_YEAR} * b). This option is b."
    )
    priors_group.add_argument(
        "--postcode_csv_filename", type=str, default=default_postcodes_csv,
        help='CSV file of postcode geography from UK Census/ONS data'
    )
    # noinspection PyUnresolvedReferences
    priors_group.add_argument(
        "--postcode_cache_filename", type=str,
        default=os.path.join(default_cache_dir, "fuzzy_postcode_cache.pickle"),
        help="File in which to store cached postcodes (to speed loading)"
    )
    priors_group.add_argument(
        "--mean_oa_population", type=float, default=UK_MEAN_OA_POPULATION_2011,
        help="Mean population of a UK Census Output Area, from which we "
             "estimate the population of postcode-based units."
    )
    priors_group.add_argument(
        "--p_not_male_or_female", type=float, default=0.004,
        help=f"Probability that a person in the population has gender 'X'."
    )
    priors_group.add_argument(
        "--p_female_given_male_or_female", type=float, default=0.51,
        help="Probability that a person in the population is female, given "
             "that they are either male or female."
    )

    error_p_group = parser.add_argument_group("error probabilities")
    error_p_group.add_argument(
        "--p_minor_forename_error", type=float, default=0.001,
        help="Assumed probability that a forename has an error in that means "
             "it fails a full match but satisfies a partial (metaphone) match."
    )
    error_p_group.add_argument(
        "--p_minor_surname_error", type=float, default=0.001,
        help="Assumed probability that a surname has an error in that means "
             "it fails a full match but satisfies a partial (metaphone) match."
    )
    error_p_group.add_argument(
        "--p_proband_middle_name_missing", type=float, default=0.05,
        help="Probability that a middle name, present in the sample, is "
             "missing from the proband."
    )
    error_p_group.add_argument(
        "--p_sample_middle_name_missing", type=float, default=0.05,
        help="Probability that a middle name, present in the proband, is "
             "missing from the sample."
    )
    error_p_group.add_argument(
        "--p_minor_postcode_error", type=float, default=0.001,
        help="Assumed probability that a postcode has an error in that means "
             "it fails a full (postcode unit) match but satisfies a partial "
             "(postcode sector) match."
    )
    error_p_group.add_argument(
        "--p_gender_error", type=float, default=0.0001,
        help="Assumed probability that a gender is wrong leading to a "
             "proband/candidate mismatch."
    )

    match_rule_group = parser.add_argument_group("matching rules")
    default_min_p_for_match = 0.999
    default_log_odds_for_match = log_odds_from_probability(default_min_p_for_match)  # noqa
    match_rule_group.add_argument(
        "--min_log_odds_for_match", type=float,
        default=default_log_odds_for_match,
        help=f"Minimum natural log (ln) odds of two people being the same, "
             f"before a match will be considered. (Default is equivalent to "
             f"p = {default_min_p_for_match}.)"
    )
    match_rule_group.add_argument(
        "--exceeds_next_best_log_odds", type=float, default=10,
        help="Minimum log (ln) odds by which a best match must exceed the "
             "next-best match to be considered a unique match."
    )

    # -------------------------------------------------------------------------
    # Subcommand subparser
    # -------------------------------------------------------------------------

    subparsers = parser.add_subparsers(
        title="commands",
        description="Valid commands are as follows.",
        help='Specify one command.',
        dest='command',  # sorts out the help for the command being mandatory
    )  # type: _SubParsersAction  # noqa
    subparsers.required = True  # requires a command

    # -------------------------------------------------------------------------
    # selftest command
    # -------------------------------------------------------------------------

    subparsers.add_parser(
        "selftest",
        help="Run self-tests and stop",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="""
        This will run a bunch of self-tests and crash out if one fails.
        """
    )

    # -------------------------------------------------------------------------
    # speedtest command
    # -------------------------------------------------------------------------

    speedtest_parser = subparsers.add_parser(
        "speedtest",
        help="Run speed tests and stop",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        description="""
        This will run several comparisons to test hashing and comparison
        speed. Results are reported as microseconds per comparison.
        """
    )
    speedtest_parser.add_argument(
        "--profile", action="store_true",
        help="Profile (makes things slower but shows you what's taking the "
             "time)."
    )

    # -------------------------------------------------------------------------
    # validate1 command
    # -------------------------------------------------------------------------

    validate1_parser = subparsers.add_parser(
        "validate1",
        help="Run validation test 1 and stop. In this test, a list of people "
             "is compared to a version of itself, at times with elements "
             "deleted or with typos introduced. ",
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
        description=HELP_VALIDATE_1,
    )
    validate1_parser.add_argument(
        "--people", type=str,
        default=os.path.join(default_names_dir, "fuzzy_validation1_people.csv"),
        help="CSV filename for validation 1 data. " +
             Person.PLAINTEXT_CSV_FORMAT_HELP
    )
    validate1_parser.add_argument(
        "--output", type=str,
        default=os.path.join(default_names_dir,
                             "fuzzy_validation1_output.csv"),
        help="Output CSV file for validation. " + VALIDATION_OUTPUT_CSV_HELP
    )
    validate1_parser.add_argument(
        "--seed", type=int, default=1234,
        help="Random number seed, for introducing deliberate errors in "
             "validation test 1"
    )

    # -------------------------------------------------------------------------
    # validate2 and ancillary commands
    # -------------------------------------------------------------------------

    validate2_cdl_parser = subparsers.add_parser(
        "validate2_fetch_cdl",
        help="Validation 2A: fetch people from CPFT CDL database",
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
        description=HELP_VALIDATE_2_CDL
    )
    validate2_cdl_parser.add_argument(
        "--url", type=str, required=True,
        help="SQLAlchemy URL for CPFT CDL source (IDENTIFIABLE) database"
    )
    validate2_cdl_parser.add_argument(
        "--echo", action="store_true",
        help="Echo SQL?"
    )
    validate2_cdl_parser.add_argument(
        "--output", type=str,
        default=os.path.join(default_names_dir, DEFAULT_CDL_PLAINTEXT),
        help="CSV filename for output (plaintext, IDENTIFIABLE) data. " +
             Person.PLAINTEXT_CSV_FORMAT_HELP
    )

    validate2_rio_parser = subparsers.add_parser(
        "validate2_fetch_rio",
        help="Validation 2B: fetch people from CPFT RiO database",
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
        description="See validate2_fetch_cdl command."
    )
    validate2_rio_parser.add_argument(
        "--url", type=str, required=True,
        help="SQLAlchemy URL for CPFT RiO source (IDENTIFIABLE) database"
    )
    validate2_rio_parser.add_argument(
        "--echo", action="store_true",
        help="Echo SQL?"
    )
    validate2_rio_parser.add_argument(
        "--output", type=str,
        default=os.path.join(default_names_dir, DEFAULT_RIO_PLAINTEXT),
        help="CSV filename for output (plaintext, IDENTIFIABLE) data. " +
             Person.PLAINTEXT_CSV_FORMAT_HELP
    )

    # -------------------------------------------------------------------------
    # hash command
    # -------------------------------------------------------------------------

    hash_parser = subparsers.add_parser(
        "hash",
        help="STEP 1 OF DE-IDENTIFIED LINKAGE. "
             "Hash an identifiable CSV file into an encrypted one. ",
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
        description="""
    Takes an identifiable list of people (with name, DOB, and postcode
    information) and creates a hashed, de-identified equivalent.
    
    The research ID (presumed not to be a direct identifier) is preserved.
    Optionally, the unique original ID (e.g. NHS number, presumed to be a 
    direct identifier) is preserved, but you have to ask for that explicitly.
        """
    )
    hash_parser.add_argument(
        "--input", type=str,
        default=os.path.join(default_names_dir, "fuzzy_probands.csv"),
        help="CSV filename for input (plaintext) data. " +
             Person.PLAINTEXT_CSV_FORMAT_HELP
    )
    # noinspection PyUnresolvedReferences
    hash_parser.add_argument(
        "--output", type=str,
        default=os.path.join(default_names_dir, "fuzzy_probands_hashed.csv"),
        help="Output CSV file for hashed version. " +
             Person.HASHED_CSV_FORMAT_HELP
    )
    hash_parser.add_argument(
        "--without_frequencies", action="store_true",
        help="Do not include frequency information. This makes the result "
             "suitable for use as a sample file, but not a proband file."
    )
    hash_parser.add_argument(
        "--include_original_id", action="store_true",
        help="Include the (potentially identifying) 'original_id' data? "
             "Usually False; may be set to True for validation."
    )

    # -------------------------------------------------------------------------
    # Common options for comparison functions
    # -------------------------------------------------------------------------

    def add_comparison_options(
            p: argparse.ArgumentParser,
            proband_fn_default: str,
            sample_fn_default: str,
            output_fn_default: str) -> None:
        p.add_argument(
            "--probands", type=str,
            default=os.path.join(default_names_dir, proband_fn_default),
            help="CSV filename for probands data. " +
                 Person.HASHED_CSV_FORMAT_HELP
        )
        p.add_argument(
            "--sample", type=str,
            default=os.path.join(default_names_dir, sample_fn_default),
            help="CSV filename for sample data. " +
                 Person.HASHED_CSV_FORMAT_HELP
        )
        p.add_argument(
            "--sample_cache", type=str, default=None,
            # The cache might contain sensitive information; don't offer it by
            # default.
            help="File in which to store cached sample info (to speed loading)"
        )
        p.add_argument(
            "--output", type=str,
            default=os.path.join(default_names_dir, output_fn_default),
            help="Output CSV file for proband/sample comparison."
        )
        p.add_argument(
            "--extra_validation_output", action="store_true",
            help="Add extra output for validation purposes."
        )
        p.add_argument(
            "--n_workers", type=int, default=CPU_COUNT,
            help="Number of processes to use in parallel."
        )
        p.add_argument(
            "--max_chunksize", type=int, default=DEFAULT_MAX_CHUNKSIZE,
            help="Maximum chunk size (number of probands to pass to a "
                 "subprocess each time)."
        )
        p.add_argument(
            "--profile", action="store_true",
            help="Profile the code (for development only)."
        )

    # -------------------------------------------------------------------------
    # compare_plaintext command
    # -------------------------------------------------------------------------

    compare_plaintext_parser = subparsers.add_parser(
        "compare_plaintext",
        help="IDENTIFIABLE LINKAGE COMMAND. "
             "Compare a list of probands against a sample (both in "
             "plaintext). ",
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
        description=HELP_COMPARISON
    )
    add_comparison_options(
        compare_plaintext_parser,
        proband_fn_default="fuzzy_probands.csv",
        sample_fn_default="fuzzy_sample.csv",
        output_fn_default="fuzzy_output_p2p.csv",
    )

    # -------------------------------------------------------------------------
    # compare_hashed_to_hashed command
    # -------------------------------------------------------------------------

    compare_h2h_parser = subparsers.add_parser(
        "compare_hashed_to_hashed",
        help="STEP 2 OF DE-IDENTIFIED LINKAGE (for when you have de-identified "
             "both sides in advance). "
             "Compare a list of probands against a sample (both hashed).",
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
        description=HELP_COMPARISON
    )
    add_comparison_options(
        compare_h2h_parser,
        proband_fn_default="fuzzy_probands_hashed.csv",
        sample_fn_default="fuzzy_sample_hashed.csv",
        output_fn_default="fuzzy_output_h2h.csv",
    )

    # -------------------------------------------------------------------------
    # compare_hashed_to_plaintext command
    # -------------------------------------------------------------------------

    compare_h2p_parser = subparsers.add_parser(
        "compare_hashed_to_plaintext",
        help="STEP 2 OF DE-IDENTIFIED LINKAGE (for when you have received "
             "de-identified data and you want to link to your identifiable "
             "data, producing a de-identified result). "
             "Compare a list of probands (hashed) against a sample "
             "(plaintext).",
        formatter_class=RawDescriptionArgumentDefaultsHelpFormatter,
        description=HELP_COMPARISON
    )
    add_comparison_options(
        compare_h2p_parser,
        proband_fn_default="fuzzy_probands_hashed.csv",
        sample_fn_default="fuzzy_sample.csv",
        output_fn_default="fuzzy_output_h2p.csv",
    )

    # -------------------------------------------------------------------------
    # Debugging commands
    # -------------------------------------------------------------------------

    show_metaphone_parser = subparsers.add_parser(
        "show_metaphone",
        help="Show metaphones of words"
    )
    show_metaphone_parser.add_argument(
        "words", nargs="+",
        help="Words to check"
    )

    show_forename_freq_parser = subparsers.add_parser(
        "show_forename_freq",
        help="Show frequencies of forenames"
    )
    show_forename_freq_parser.add_argument(
        "forenames", nargs="+",
        help="Forenames to check"
    )

    show_forename_metaphone_freq_parser = subparsers.add_parser(
        "show_forename_metaphone_freq",
        help="Show frequencies of forename metaphones"
    )
    show_forename_metaphone_freq_parser.add_argument(
        "metaphones", nargs="+",
        help="Forenames to check"
    )

    show_surname_freq_parser = subparsers.add_parser(
        "show_surname_freq",
        help="Show frequencies of surnames"
    )
    show_surname_freq_parser.add_argument(
        "surnames", nargs="+",
        help="surnames to check"
    )

    show_surname_metaphone_freq_parser = subparsers.add_parser(
        "show_surname_metaphone_freq",
        help="Show frequencies of surname metaphones"
    )
    show_surname_metaphone_freq_parser.add_argument(
        "metaphones", nargs="+",
        help="surnames to check"
    )

    _ = subparsers.add_parser(
        "show_dob_freq",
        help="Show the frequency of any DOB"
    )

    # -------------------------------------------------------------------------
    # Parse arguments and set up
    # -------------------------------------------------------------------------

    args = parser.parse_args()
    main_only_quicksetup_rootlogger(
        level=logging.DEBUG if args.verbose else logging.INFO,
        with_process_id=True)
    log.debug(f"Ensuring default cache directory exists: {default_cache_dir}")
    os.makedirs(default_cache_dir, exist_ok=True)

    p_middle_name_n_present = [
        float(x) for x in args.p_middle_name_n_present.split(",")]
    min_p_for_match = probability_from_log_odds(args.min_log_odds_for_match)

    log.debug(f"Using population size: {args.population_size}")
    log.debug(f"Using min_log_odds_for_match: {args.min_log_odds_for_match} "
              f"(p = {min_p_for_match})")
    cfg = MatchConfig(
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

    def warn_or_fail_if_default_key() -> None:
        if args.key == DEFAULT_HASH_KEY:
            if args.allow_default_hash_key:
                log.warning("Proceeding with default hash key at user's "
                            "explicit request.")
            else:
                log.error(
                    "You have not specified a hash key, so are using the "
                    "default! Stopping, because this is a very bad idea for "
                    "real data. Specify --allow_default_hash_key to use the "
                    "default for testing purposes.")
                sys.exit(EXIT_FAILURE)

    # pdb.set_trace()

    # -------------------------------------------------------------------------
    # Run a command
    # -------------------------------------------------------------------------

    log.info(f"Command: {args.command}")
    if args.command == "selftest":
        selftest(cfg, speedtest=False)

    elif args.command == "speedtest":
        fn = do_cprofile(selftest) if args.profile else selftest
        fn(cfg, speedtest=True)

    elif args.command == "validate1":
        log.info("Running validation test 1.")
        validate_1(
            cfg,
            people_csv=args.people,
            output_csv=args.output,
            seed=args.seed,
        )
        log.warning("Validation test 1 complete.")

    elif args.command == "validate2_fetch_cdl":
        warn_or_fail_if_default_key()
        save_people_from_db(
            people=validate_2_fetch_cdl(cfg=cfg,
                                        url=args.url,
                                        hash_key=args.key,
                                        echo=args.echo),
            output_csv=args.output,
        )

    elif args.command == "validate2_fetch_rio":
        warn_or_fail_if_default_key()
        save_people_from_db(
            people=validate_2_fetch_rio(cfg=cfg,
                                        url=args.url,
                                        hash_key=args.key,
                                        echo=args.echo),
            output_csv=args.output,
        )

    elif args.command == "hash":
        warn_or_fail_if_default_key()
        log.info(f"Hashing identity file: {args.input}")
        hash_identity_file(cfg=cfg,
                           input_csv=args.input,
                           output_csv=args.output,
                           without_frequencies=args.without_frequencies,
                           include_original_id=args.include_original_id)
        log.info(f"... finished; written to {args.output}")

    elif args.command == "compare_plaintext":
        log.info(f"Comparing files:\n"
                 f"- plaintext probands: {args.probands}\n"
                 f"- plaintext sample: {args.sample}")
        compare_probands_to_sample_from_csv(
            cfg=cfg,
            extra_validation_output=args.extra_validation_output,
            max_chunksize=args.max_chunksize,
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
        log.info(f"Comparing files:\n"
                 f"- hashed probands: {args.probands}\n"
                 f"- hashed sample: {args.sample}")
        compare_probands_to_sample_from_csv(
            cfg=cfg,
            extra_validation_output=args.extra_validation_output,
            max_chunksize=args.max_chunksize,
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
        warn_or_fail_if_default_key()
        log.info(f"Comparing files:\n"
                 f"- hashed probands: {args.probands}\n"
                 f"- plaintext sample: {args.sample}")
        compare_probands_to_sample_from_csv(
            cfg=cfg,
            extra_validation_output=args.extra_validation_output,
            max_chunksize=args.max_chunksize,
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
            log.info(f"Forename {forename!r}: "
                     f"F {cfg.forename_freq(forename, GENDER_FEMALE)}, "
                     f"M {cfg.forename_freq(forename, GENDER_MALE)}, "
                     f"overall {cfg.forename_freq(forename, '')}")

    elif args.command == "show_forename_metaphone_freq":
        for metaphone in args.metaphones:
            log.info(f"Forename metaphone {metaphone!r}: "
                     f"F {cfg.forename_metaphone_freq(metaphone, GENDER_FEMALE)}, "  # noqa
                     f"M {cfg.forename_metaphone_freq(metaphone, GENDER_MALE)}, "  # noqa
                     f"overall {cfg.forename_metaphone_freq(metaphone, '')}")

    elif args.command == "show_surname_freq":
        for surname in args.surnames:
            log.info(f"Surname {surname!r}: {cfg.surname_freq(surname)}")

    elif args.command == "show_surname_metaphone_freq":
        for metaphone in args.metaphones:
            log.info(f"Surname metaphone {metaphone!r}: "
                     f"{cfg.surname_metaphone_freq(metaphone)}")

    elif args.command == "show_dob_freq":
        log.info(f"DOB frequency: {cfg.p_two_people_share_dob}")

    else:
        # Shouldn't get here.
        log.error(f"Unknown command: {args.command}")
        sys.exit(EXIT_FAILURE)


if __name__ == "__main__":
    main()
    sys.exit(EXIT_SUCCESS)
