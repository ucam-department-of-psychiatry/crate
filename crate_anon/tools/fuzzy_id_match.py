#!/usr/bin/env python

r"""
crate_anon/tools/fuzzy_id_match.py

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

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


Note
----

Duplicates and simplifies some hashing code from CRATE to make this a
standalone program requiring minimal Python libraries.


Terminology
-----------

A **proband** individual is compared to a **sample** and a matching individual
is sought in the sample. There may be a match or no match.

It is assumed that both the proband and every person in the sample is drawn
from a background population (e.g. "everyone in the UK"), and that every person
in the sample is distinct.


Principle of matching people
----------------------------

- find all people whose log odds of matching exceeds the minimum log odds
  required for a match;

- declare the most likely a match if their log odds exceeds the runner-up by a
  certain amount;

- otherwise, there is no match.

.. todo:: revise above


Step 1: probability of a match, given that both are from the same population
----------------------------------------------------------------------------

The program takes the population size :math:`n_p` (e.g. UK population of ~66m)
as a parameter. The baseline probability of two people being a match is taken
as :math:`\frac{1}{n_p}`. Where information can be compared (e.g. if a date of
birth is present in both records), it can alter the match probability via a
Bayesian update process.

This yields an estimate of P(match | both people in population).

Specifically, if

- the hypothesis :math:`H` is that the person is the same;
- `D` indicates the data;

then we calculate

.. math::

    P(H | D) &= \frac{ P(D | H) \cdot P(H) }{ P(D) }  \\

    \text{posterior} &= \frac{ \text{likelihood} \cdot \text{prior} }
                             { \text{marginal likelihood} }
                             
It's more convenient to work with log odds:

.. math::

    P(H | D) &= P(D | H) \frac{ P(H) }{ P(D) }  \\

    P(\neg H | D) &= P(D | \neg H) \frac{ P(\neg H) }{ P(D) }  \\

    \frac{ P(H | D) }{ P(\neg H | D) } &=
        \frac{ P(D | H) }{ P(D | \neg H) }
        \frac{ P(H) }{ P(\neg H) }  \\

    \text{posterior odds} &= \text{likelihood ratio} \cdot \text{prior odds}  \\

    \log \text{posterior odds} &= \log \text{likelihood ratio} + 
                                  \log \text{prior odds}
                                  
That way, the iterative process is to start with log odds for the prior, then
add log likelihood ratios consecutively.


Partial match of information
----------------------------

With plaintext information, a distance measure is possible to give a threshold
for typographical errors. An alternative way that may be suitable for hashed
information is to use an accurate (specific) and a blurry (fuzzy) match.

If

- the probability is :math:`p_e` of there being a data error such that a
  specific match becomes a fuzzy match;
- we will reject anything that is not even a fuzzy match;
- the hypothesis :math:`H` is that the person is the same;
- `D` indicates the data, which in this situation can be one and only one of: a
  specific match, a fuzzy but not a specific match, and no match;
- :math:`p_f` is the probability of a randomly selected person giving a
  full (specific) match to our proband (e.g. same forename, or same postcode
  unit);
- :math:`p_p` is the probability of a randomly selected person giving a
  partial (fuzzy) match to our proband (e.g. same fuzzy forename, or same
  postcode district);
  
then we have the following:

+------------------------------+------------------+-----------------------+
| :math:`D`                    | :math:`P(D | H)` | :math:`P(D | \neg H)` |
+==============================+==================+=======================+
| full match                   | :math:`1 - p_e`  | :math:`p_f`           |
+------------------------------+------------------+-----------------------+
| partial but not full match   | :math:`p_e`      | :math:`p_p - p_f`     |
+------------------------------+------------------+-----------------------+
| no match                     | :math:`0`        | :math:`1 - p_p`       |
+------------------------------+------------------+-----------------------+
| (sum of probabilities)       | :math:`1`        | :math:`1`             |
+------------------------------+------------------+-----------------------+


Stage 2: probability of a match, given our sampling fraction
------------------------------------------------------------

We move now from a comparison between the proband and a single individual in
our database to a comparison between the proband and the whole database.

The final step is to incorporate information about the size of the "database"
(sample) against which the individual is to be compared. This must be a subset
of the population (by our statistical definition of "population") but might be
a large or a small subset. If :math:`n_s` is the sample size, the sampling
fraction :math:`\frac{n_s}{n_p} = p_s` gives a baseline estimate of P(proband
in sample). If :math:`p_s = 1`, then it is certain that the proband is in the
sample.

Let :math:`M_i` indicates a match for item :math:`i` in the sample.

So, we begin with a list of probabilities :math:`P(M_i | D, \text{both people
in population})`. Dropping our constant assumption that everyone is in the
population, this is :math:`P(M_i | D)`. It is always true that

.. math::

    P(M_i | D) &= \frac{ P(D | M_i) P(M_i) }{ P(D) }  \\

               &= \frac{ \text{likelihood} \cdot \text{prior} }
                       { \text{marginal likelihood} }

.. comment

    The ampersand-equals (&=) and "\\" combinations indicates alignment points.
    See https://shimizukawa-sphinx.readthedocs.io/en/latest/ext/math.html.

If it is the case that our proband must be in the sample, then:

.. math::

    P(\text{proband in sample}) &= 1  \\
    
    \sum_{j=1}^{n_s} P(M_j) &= 1  \\
    
    P(M_i | D) &= \frac{ P(D | M_i) P(M_i) / P(D) }
                       { \sum_{j=1}^{n_s} P(D | M_j) P(M_j) / P(D) }  \\

               &= \frac{ \frac{ 1 }{ p(D) } P(D | M_i) P(M_i) }
                       { \frac{ 1 }{ p(D) } \sum_{j=1}^{n_s} P(D | M_j) P(M_j) }  \\

               &= \frac{ P(D | M_i) P(M_i) }
                       { \sum_{j=1}^{n_s} P(D | M_j) P(M_j) }

Compare [#gronau2017]_.

With equal priors, :math:`M_i = M_j \forall i, j`, so this reduces to: 

.. math::

    P(M_i | D) = \frac{ P(D | M_i) }
                      { \sum_{j=1}^{n_s} P(D | M_j) }

In log form (with natural logarithms),

.. math::

    \log P(M_i | D) &= \log P(D | M_i) - 
                       \log \sum_{j=1}^{n_s} e^{ log P(D | M_j) }
                      
or in pseudocode:

.. code-block:: none

   log_posterior_p_match[i] = log_likelihood[i] - logSumExp(log_likelihood)

Now, we know that the probability that our individual is in the sample is not 1
but is :math:`p_s`. Conversely, with probability :math:`1 - p_s`, our
individual is not in the sample (so nobody is a match).

The final probability of each individual being a match is therefore:

.. math::

    P(M_i | D) = p_s \cdot \frac{ P(D | M_i) }
                                { \sum_{j=1}^{n_s} P(D | M_j) }

We will know :math:`n_s` automatically; it's the number of people in our
database (sample). We must just check that :math:`n_p \geq n_s`.


Statistical assumptions include
-------------------------------

- independence of forename, middle name, surname, DOB, postcode


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
- this allows you to look up FROM output area TO postcode sector, implying
  that postcode sectors must be larger.


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
import collections
import csv
import hashlib
import hmac
import logging
import math
import os
import re
import string
import sys
from typing import Any, Dict, List, Set

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from cardinal_pythonlib.probability import (
    log_odds_from_1_in_n,
    log_odds_from_probability,
    log_posterior_odds_from_bool_d_pdh_pdnh,
    log_posterior_odds_from_pdh_pdnh,
    probability_from_log_odds,
)
from cardinal_pythonlib.stringfunc import mangle_unicode_to_ascii
from fuzzy import DMetaphone

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

dmeta = DMetaphone()

DAYS_PER_YEAR = 365.25  # approximately!
MINUS_INFINITY = -math.inf
THIS_DIR = os.path.abspath(os.path.dirname(__file__))
UK_POPULATION_2017 = 66040000  # 2017 figure, 66.04m
UK_MEAN_OA_POPULATION_2011 = 309
# ... https://www.ons.gov.uk/methodology/geography/ukgeographies/censusgeography  # noqa


# =============================================================================
# Hashing
# =============================================================================

class Hasher(object):
    """
    An HMAC SHA-256 hasher.

    - HMAC = hash-based message authentication code
    - SHA = Secure Hash Algorithm
    """
    def __init__(self, key: Any) -> None:
        """
        Args:
            key: the secret key (passphrase)
        """
        self.key_bytes = str(key).encode('utf-8')
        self.digestmod = hashlib.sha256

    def hash(self, raw: Any) -> str:
        """
        Returns a hash of its input, as a hex digest.
        """
        raw_bytes = str(raw).encode('utf-8')
        hmac_obj = hmac.new(key=self.key_bytes, msg=raw_bytes,
                            digestmod=self.digestmod)
        return hmac_obj.hexdigest()

    def output_length(self) -> int:
        """
        Returns the length of the hashes produced by this hasher.
        """
        return len(self.hash("dummytext"))


# =============================================================================
# String manipulation
# =============================================================================

def get_uk_postcode_regex() -> str:
    """
    Returns a regex strings for (exact) UK postcodes. These have a
    well-defined format.
    """
    e = [
        "AN NAA",
        "ANN NAA",
        "AAN NAA",
        "AANN NAA",
        "ANA NAA",
        "AANA NAA",
    ]
    for i in range(len(e)):
        e[i] = e[i].replace("A", "[A-Z]")  # letter
        e[i] = e[i].replace("N", "[0-9]")  # number
        e[i] = e[i].replace(" ", r"\s?")  # zero or one whitespace chars
    return "|".join(f"(?:{x})" for x in e)


ISO_DATE_REGEX = re.compile(
    r"[1-9][0-9][0-9][0-9]-(?:1[0-2]|0[1-9])-(?:3[01]|0[1-9]|[12][0-9])"
)  # YYYY-MM-DD
POSTCODE_REGEX = re.compile(get_uk_postcode_regex())
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
        get_metaphone("Alice")
        get_metaphone("Mary Ellen")
        get_metaphone("D'Souza")
        get_metaphone("de Clerambault")  # won't do accents

    """
    return dmeta(x)[0]  # the first part only


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

def postlogodds_dob(log_prior_odds_same_person: float,
                    same_dob: bool,
                    debug: bool = False) -> float:
    """
    Returns the posterior log odds of two people being the same person,
    given that they do or don't share a birthday.

    There is no special treatment of 29 Feb (since this DOB is approximately 4
    times less common than other birthdays, in principle it does merit special
    treatment, but we ignore that).

    Args:
        log_prior_odds_same_person:
            log prior odds that they're the same person
        same_dob:
            do they share a birthday?
        debug:
            report debugging information to log?

    Returns:
        float: posterior log odds, as above

    Test code:

    .. code-block:: python

        from crate_anon.tools.fuzzy_id_match import *
        postlogodds_dob(0, True)
        postlogodds_dob(0, False)

    """
    p_same_dob_given_same_person = 1  # no typos allowed in dates of birth
    p_same_dob_given_not_same_person = 1 / DAYS_PER_YEAR
    posterior = log_posterior_odds_from_bool_d_pdh_pdnh(
        log_prior_odds=log_prior_odds_same_person,
        d=same_dob,
        p_d_given_h=p_same_dob_given_same_person,
        p_d_given_not_h=p_same_dob_given_not_same_person
    )
    if debug:
        log.debug(f"postlogodds_dob: same_dob={same_dob}, "
                  f"{log_prior_odds_same_person} -> {posterior}")
    return posterior


# =============================================================================
# NameFrequencyInfo
# =============================================================================

class NameFrequencyInfo(object):
    """
    Holds frequencies of a class of names (e.g. forenames or surnames), and
    also of their hashed versions.
    """
    def __init__(self,
                 csv_filename: str,
                 min_frequency: float = 5e-6) -> None:
        """
        Initializes the object from a CSV file.

        Args:
            csv_filename:
                CSV file, with no header, of "name, frequency" pairs
            min_frequency:
                minimum frequency to allow; see command-line help.
        """
        self._csv_filename = csv_filename
        self._min_frequency = min_frequency
        self._name_freq = {}  # type: Dict[str, float]
        self._metaphone_freq = {}  # type: Dict[str, float]

        log.info(f"Reading file: {csv_filename}")
        # For extra speed:
        name_freq = self._name_freq
        metaphone_freq = self._metaphone_freq
        with open(csv_filename, "rt") as f:
            csvreader = csv.reader(f)
            for row in csvreader:
                name = standardize_name(row[0])
                freq = max(float(row[1]), min_frequency)
                metaphone = get_metaphone(name)
                name_freq[name] = freq
                # https://stackoverflow.com/questions/12992165/python-dictionary-increment  # noqa
                metaphone_freq[metaphone] = (
                    metaphone_freq.get(metaphone, 0) + freq
                )
        log.info(f"... finished reading file: {csv_filename}")

    def name_frequency(self, name: str, prestandardized: bool) -> float:
        """
        Returns the frequency of a name.

        Args:
            name: the name to check
            prestandardized: was the name pre-standardized in format?

        Returns:
            the name's frequency in the population
        """
        stname = name if prestandardized else standardize_name(name)
        return self._name_freq.get(stname, self._min_frequency)

    def metaphone_frequency(self, metaphone: str) -> float:
        """
        Returns the frequency of a metaphone
        """
        return self._metaphone_freq.get(metaphone, self._min_frequency)


# =============================================================================
# PostcodeFrequencyInfo
# =============================================================================

class PostcodeFrequencyInfo(object):
    """
    Holds frequencies of a class of names (e.g. forenames or surnames), and
    also of their hashed versions.
    """
    def __init__(self,
                 csv_filename: str,
                 mean_oa_population: float = UK_MEAN_OA_POPULATION_2011) \
            -> None:
        """
        Initializes the object from a CSV file.

        Args:
            csv_filename:
                CSV file of special format. **DESCRIBE IT**
            mean_oa_population:
                Mean population of each census Output Area.
        """
        self._csv_filename = csv_filename
        self._mean_oa_population = mean_oa_population
        self._postcode_unit_freq = {}  # type: Dict[str, float]
        self._postcode_sector_freq = {}  # type: Dict[str, float]

        log.info(f"Reading file: {csv_filename}")
        units_per_oa = collections.Counter()
        unit_to_oa = {}  # type: Dict[str, str]
        sector_to_oas = {}  # type: Dict[str, Set[str]]
        with open(csv_filename, "rt") as f:
            csvreader = csv.reader(f)
            for row in csvreader:
                unit = standardize_postcode(row[0])
                sector = get_postcode_sector(unit)
                oa = row[1] # fixme

                unit_to_oa[unit] = oa
                units_per_oa[oa] += 1  # one more unit for this OA
                if sector in sector_to_oas:
                    sector_to_oas[sector] = {oa}
                else:
                    sector_to_oas[sector].add(oa)
        log.info(f"... finished reading file: {csv_filename}")

        log.info(f"Calculating population frequencies for postcodes...")
        unit_freq = self._postcode_unit_freq
        sector_freq = self._postcode_sector_freq
        n_oas = len(units_per_oa)
        total_population = n_oas * mean_oa_population
        for unit, oa in unit_to_oa.values():
            n_units_in_this_oa = units_per_oa[oa]
            unit_population = mean_oa_population / n_units_in_this_oa
            unit_freq[unit] = unit_population / total_population
        for sector, oas in sector_to_oas.values():
            n_oas_in_this_sector = len(oas)
            sector_population = mean_oa_population * n_oas_in_this_sector
            sector_freq[sector] = sector_population / total_population
        log.info(f"... done")

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
        stpu = (
            postcode_unit if prestandardized
            else standardize_postcode(postcode_unit)
        )
        return self._postcode_unit_freq[stpu]

    def postcode_sector_frequency(self, postcode_sector: str,
                                  prestandardized: bool = False) -> float:
        """
        Returns the frequency of a postcode sector.
        """
        stps = (
            postcode_sector if prestandardized
            else standardize_postcode(postcode_sector)
        )
        return self._postcode_sector_freq[stps]


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
            hasher_key: str,
            forename_csv_filename: str,
            surname_csv_filename: str,
            min_name_frequency: float,
            baseline_log_odds_same_person: float,
            postcode_csv_filename: str,
            mean_oa_population: float,
            min_log_odds_for_match: float,
            p_minor_forename_error: float,
            p_minor_surname_error: float,
            p_minor_postcode_error: float) -> None:
        """
        Args:
            hasher_key:
                key (passphrase) for hasher
            forename_csv_filename:
                Forename frequencies. CSV file, with no header, of "name,
                frequency" pairs.
            surname_csv_filename:
                Surname frequencies. CSV file, with no header, of "name,
                frequency" pairs.
            min_name_frequency:
                minimum name frequency; see command-line help.
            baseline_log_odds_same_person:
                baseline (prior) log odds that two randomly selected people are
                the same
            postcode_csv_filename:
                Postcode mapping. CSV file. Special format; see
                :class:`PostcodeFrequencyInfo`.
            mean_oa_population:
                the mean population of a UK Census Output Area
            min_log_odds_for_match:
                minimum log odds of a match, to consider two people a match
            p_minor_forename_error:
                Probability that a forename fails a full match but passes a
                partial match.
            p_minor_surname_error:
                Probability that a surname fails a full match but passes a
                partial match.
            p_minor_postcode_error:
                Probability that a postcode fails a full match but passes a
                partial match.
        """
        self.hasher = Hasher(hasher_key)
        self.forename_csv_filename = forename_csv_filename
        self.surname_csv_filename = surname_csv_filename
        self.min_name_frequency = min_name_frequency
        self.baseline_log_odds_same_person = baseline_log_odds_same_person
        self.min_log_odds_for_match = min_log_odds_for_match
        self.p_minor_forename_error = p_minor_forename_error
        self.p_minor_surname_error = p_minor_surname_error
        self.p_minor_postcode_error = p_minor_postcode_error

        self._forename_freq = NameFrequencyInfo(forename_csv_filename,
                                                min_name_frequency)
        self._surname_freq = NameFrequencyInfo(surname_csv_filename,
                                               min_name_frequency)
        self._postcode_freq = PostcodeFrequencyInfo(postcode_csv_filename,
                                                    mean_oa_population)

    def forename_freq(self, name: str, prestandardized: bool = False) -> float:
        """
        Returns the baseline frequency of a forename.

        Args:
            name: the name to check
            prestandardized: was it pre-standardized?
        """
        return self._forename_freq.name_frequency(name, prestandardized)

    def forename_metaphone_freq(self, metaphone: str) -> float:
        """
        Returns the baseline frequency of a forename's metaphone.

        Args:
            metaphone: the metaphone to check
        """
        return self._forename_freq.metaphone_frequency(metaphone)

    def surname_freq(self, name: str, prestandardized: bool = False) -> float:
        """
        Returns the baseline frequency of a surname.

        Args:
            name: the name to check
            prestandardized: was it pre-standardized?
        """
        return self._surname_freq.name_frequency(name, prestandardized)

    def surname_metaphone_freq(self, metaphone: str) -> float:
        """
        Returns the baseline frequency of a surname's metaphone.

        Args:
            metaphone: the metaphone to check
        """
        return self._surname_freq.metaphone_frequency(metaphone)

    def postcode_unit_freq(self, postcode_unit: str,
                           prestandardized: bool = True) -> float:
        """
        Returns the frequency for a full postcode, or postcode unit (the
        proportion of the population who live in that postcode).
        """
        return self._postcode_freq.postcode_unit_frequency(
            postcode_unit, prestandardized=prestandardized)

    def postcode_sector_freq(self, postcode_sector: str,
                             prestandardized: bool = True) -> float:
        """
        Returns the frequency for a postcode sector; see
        :meth:`postcode_freq`.
        """
        return self._postcode_freq.postcode_sector_frequency(
            postcode_sector, prestandardized=prestandardized)

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

    def posterior_log_odds_surname(
            self,
            log_prior_odds: float,
            proband_surname: str,
            other_surname: str,
            prestandardized: bool = False) -> float:
        """
        Returns the log odds of two people being the same person based on a
        comparison of surnames.

        Args:
            log_prior_odds:
                prior log odds
            proband_surname:
                one surname
            other_surname:
                the other surname
            prestandardized:
                assume the surnames are in our standard format?

        Returns:
            float: the posterior log odds, as above
        """
        if not prestandardized:
            proband_surname = standardize_name(proband_surname)
            other_surname = standardize_name(other_surname)
        if proband_surname == other_surname:
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            # Full match
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            p_d_given_same = 1 - self.p_minor_surname_error  # 1 - p_e
            p_d_given_diff = self.surname_freq(
                proband_surname, prestandardized=True)  # p_f
        else:
            self_metaphone = get_metaphone(proband_surname)
            other_metaphone = get_metaphone(other_surname)
            if self_metaphone == other_metaphone:
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # Partial match
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                p_d_given_same = self.p_minor_surname_error  # p_e
                p_d_given_diff = (
                    self.surname_metaphone_freq(self_metaphone) -
                    self.surname_freq(proband_surname, prestandardized=True)
                )  # p_p - p_f
            else:
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # No match
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                p_d_given_same = 0
                p_d_given_diff = (
                    1 - self.surname_metaphone_freq(self_metaphone)
                )  # 1 - p_p
        posterior_log_odds = log_posterior_odds_from_pdh_pdnh(
            log_prior_odds=log_prior_odds,
            p_d_given_h=p_d_given_same,
            p_d_given_not_h=p_d_given_diff
        )
        log.debug(
            f"plaintext surname: {proband_surname!r}, {other_surname!r}: "
            f"log odds {log_prior_odds} -> {posterior_log_odds}")
        return posterior_log_odds

    def posterior_log_odds_forename(
            self,
            log_prior_odds: float,
            proband_forename: str,
            other_forename: str,
            prestandardized: bool = True) -> float:
        """
        Returns the log odds of two people being the same person based on a
        comparison of forenames.

        Args:
            log_prior_odds:
                prior log odds
            proband_forename:
                one forename
            other_forename:
                the other forename
            prestandardized:
                assume the forenames are in our standard format?

        Returns:
            float: the posterior log odds, as above
        """
        if not prestandardized:
            proband_forename = standardize_name(proband_forename)
            other_forename = standardize_name(other_forename)
        if proband_forename == other_forename:
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            # Full match
            # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
            p_d_given_same = 1 - self.p_minor_forename_error  # 1 - p_e
            p_d_given_diff = self.forename_freq(
                proband_forename, prestandardized=True)  # p_f
        else:
            self_metaphone = get_metaphone(proband_forename)
            other_metaphone = get_metaphone(other_forename)
            if self_metaphone == other_metaphone:
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # Partial match
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                p_d_given_same = self.p_minor_forename_error  # p_e
                p_d_given_diff = (
                    self.forename_metaphone_freq(self_metaphone) -
                    self.forename_freq(proband_forename, prestandardized=True)
                )  # p_p - p_f
            else:
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                # No match
                # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
                p_d_given_same = 0
                p_d_given_diff = (
                    1 - self.forename_metaphone_freq(self_metaphone)
                )  # 1 - p_p
        posterior_log_odds = log_posterior_odds_from_pdh_pdnh(
            log_prior_odds=log_prior_odds,
            p_d_given_h=p_d_given_same,
            p_d_given_not_h=p_d_given_diff
        )
        log.debug(
            f"plaintext forename: {proband_forename!r}, {other_forename!r}: "
            f"log odds {log_prior_odds} -> {posterior_log_odds}")
        return posterior_log_odds

    def posterior_log_odds_middle_names(
            self,
            log_prior_odds: float,
            proband_middle_names: List[str],
            other_middle_names: List[str],
            prestandardized: bool = True) -> float:
        """
        Returns the log odds of two people being the same person based on a
        comparison of middle names.

        Args:
            log_prior_odds:
                prior log odds
            proband_middle_names:
                one list of middle names
            other_middle_names:
                the other list of middle names
            prestandardized:
                assume the forenames are in our standard format?

        Returns:
            float: the posterior log odds, as above
        """
        # "mn": middle names
        if not prestandardized:
            proband_middle_names = [standardize_name(x)
                                    for x in proband_middle_names]
            other_middle_names = [standardize_name(x)
                                  for x in other_middle_names]
        mn_self = set(proband_middle_names)
        mn_othr = set(other_middle_names)
        shared_mn = mn_self.intersection(mn_othr)

        log_odds = log_prior_odds

        # For full matches:
        mn_p_d_given_same = 1 - self.p_minor_forename_error  # 1 - p_e
        for mn in shared_mn:
            mn_p_d_given_diff = self.forename_freq(mn, prestandardized=True)  # p_f  # noqa
            log_odds = log_posterior_odds_from_pdh_pdnh(
                log_prior_odds=log_odds,
                p_d_given_h=mn_p_d_given_same,
                p_d_given_not_h=mn_p_d_given_diff
            )
            if log_odds == MINUS_INFINITY:
                return log_odds

        # For partial (metaphone) matches (that are not also full matches):
        exclusive_mn_self = mn_self - shared_mn
        exclusive_mn_othr = mn_othr - shared_mn
        metaphones_other = set(get_metaphone(x) for x in exclusive_mn_othr)
        metamn_p_d_given_same = self.p_minor_forename_error  # p_e
        self_metaphones_seen = set()  # type: Set[str]
        for mn in exclusive_mn_self:
            metaphone = get_metaphone(mn)
            if metaphone in self_metaphones_seen:
                continue
            self_metaphones_seen.add(metaphone)
            if metaphone in metaphones_other:
                # We have found a middle name, present in self but not other,
                # whose metaphone matches that of a middle name present in
                # other but not self.
                metamn_p_d_given_diff = (
                    self.forename_metaphone_freq(metaphone) -
                    self.forename_freq(mn)
                )  # p_p - p_f
                log_odds = log_posterior_odds_from_pdh_pdnh(
                    log_prior_odds=log_odds,
                    p_d_given_h=metamn_p_d_given_same,
                    p_d_given_not_h=metamn_p_d_given_diff
                )
                if log_odds == MINUS_INFINITY:
                    return log_odds

        log.debug(
            f"plaintext middle names: {mn_self!r}, {mn_othr!r}: "
            f"log odds {log_prior_odds} -> {log_odds}")
        return log_odds

    def posterior_log_odds_postcodes(
            self,
            log_prior_odds: float,
            proband_postcodes: List[str],
            other_postcodes: List[str]) -> float:
        """
        Returns the log odds of two people being the same person based on a
        comparison of postcodes.

        Args:
            log_prior_odds:
                prior log odds
            proband_postcodes:
                one list of postcodes
            other_postcodes:
                the other list of postcodes

        Returns:
            float: the posterior log odds, as above
        """
        # "pu" = postcode unit; "ps" = postcode sector
        pu_self = set(proband_postcodes)
        pu_othr = set(other_postcodes)
        shared_pu = pu_self.intersection(pu_othr)

        log_odds = log_prior_odds

        # For full (postcode unit) matches:
        pu_p_d_given_same = 1 - self.p_minor_postcode_error  # 1 - p_e
        for pu in shared_pu:
            pu_p_d_given_diff = self.postcode_unit_freq(pu)  # p_f
            log_odds = log_posterior_odds_from_pdh_pdnh(
                log_prior_odds=log_odds,
                p_d_given_h=pu_p_d_given_same,
                p_d_given_not_h=pu_p_d_given_diff
            )
            if log_odds == MINUS_INFINITY:
                return log_odds

        # For partial (postcode area) matches (that are not also full matches):
        exclusive_pu_self = pu_self - shared_pu
        exclusive_pu_othr = pu_othr - shared_pu
        ps_other = set(get_postcode_sector(x) for x in exclusive_pu_othr)
        ps_p_d_given_same = self.p_minor_postcode_error  # p_e
        self_ps_seen = set()  # type: Set[str]
        for pu in exclusive_pu_self:
            ps = get_postcode_sector(pu)
            if ps in self_ps_seen:
                continue
            self_ps_seen.add(ps)
            if ps in ps_other:
                # We've found a postcode unit, present in self but not other,
                # whose postcode sector matches that of a postcode unit present
                # in other but not self.
                pa_p_d_given_diff = (
                    self.postcode_sector_freq(ps) -
                    self.postcode_unit_freq(pu)
                )  # p_p - p_f
                log_odds = log_posterior_odds_from_pdh_pdnh(
                    log_prior_odds=log_odds,
                    p_d_given_h=ps_p_d_given_same,
                    p_d_given_not_h=pa_p_d_given_diff
                )
                if log_odds == MINUS_INFINITY:
                    return log_odds

        log.debug(
            f"plaintext postcodes: {pu_self!r}, {pu_othr!r}: "
            f"log odds {log_prior_odds} -> {log_odds}")
        return log_odds


# =============================================================================
# Person
# =============================================================================

class Person(object):
    """
    Represents a person. The information may be incomplete or slightly wrong.
    """
    def __init__(self,
                 forename: str = "",
                 middle_names: List[str] = None,
                 surname: str = "",
                 dob: str = "",
                 postcodes: List[str] = None,
                 is_hashed: bool = False) -> None:
        """
        Args:
            forename: the person's forename
            middle_names: any middle names
            surname: the person's surname
            dob: the date of birth in ISO-8061 "YYYY-MM-DD" string format
            postcodes: any UK postcodes
            is_hashed: is this a hashed representation? If so, matching works
                differently and DOB/postcodes are not (cannot be) checked.
        """
        self.forename = standardize_name(forename)
        self.middle_names = [standardize_name(x)
                             for x in middle_names] if middle_names else []
        self.surname = standardize_name(surname)
        self.dob = dob
        self.postcodes = [standardize_postcode(x)
                          for x in postcodes] if postcodes else []
        self.is_hashed = is_hashed
        # Validation:
        if not is_hashed:
            if dob:
                assert ISO_DATE_REGEX.match(dob), f"Bad date: {dob}"
            for postcode in self.postcodes:
                assert POSTCODE_REGEX.match(postcode), f"Bad postcode: {postcode}"  # noqa

    def __repr__(self) -> str:
        """
        Returns a string representation that can be used for reconstruction.
        """
        return (
            f"Person("
            f"forename={self.forename!r}"
            f", middle_names={self.middle_names!r}"
            f", surname={self.surname!r}"
            f", dob={self.dob!r}"
            f", postcodes={self.postcodes!r}"
            f")"
        )

    def hashed(self, hasher: Hasher) -> "Person":
        """
        Returns a :class:`Person` object but with all the elements hashed (if
        they are not blank).
        """
        forename = (
            hasher.hash(self.forename)
            if self.forename else ""
        )
        middle_names = [
            hasher.hash(x)
            for x in self.middle_names if x
        ]
        surname = (
            hasher.hash(self.surname)
            if self.surname else ""
        )
        dob = hasher.hash(self.dob) if self.dob else ""
        postcodes = [hasher.hash(x) for x in self.postcodes if x]
        return Person(
            forename=forename,
            middle_names=middle_names,
            surname=surname,
            dob=dob,
            postcodes=postcodes,
            is_hashed=True
        )

    def log_odds_same(self, other: "Person", cfg: MatchConfig) -> float:
        """
        Returns the log odds that this and ``other`` are the same person.

        Args:
            other: another :class:`Person` object
            cfg: the master :class:`MatchConfig` object

        Returns:
            float: the log odds they're the same person
        """
        if self.is_hashed:
            return self._log_odds_same_hashed(other, cfg)
        return self._log_odds_same_plaintext(other, cfg)

    def _log_odds_same_plaintext(self, other: "Person",
                                 cfg: MatchConfig) -> float:
        """
        Returns the log odds that this and ``other`` are the same person,
        using plaintext information.

        Args:
            other: another :class:`Person` object
            cfg: the master :class:`MatchConfig` object

        Returns:
            float: the log odds they're the same person
        """
        log_odds = cfg.baseline_log_odds_same_person

        # ---------------------------------------------------------------------
        # DOB
        # ---------------------------------------------------------------------
        if self.dob and other.dob:
            # If we don't have two DOBs to compare, we skip this.
            same_dob = self.dob == other.dob
            log_odds = postlogodds_dob(log_odds, same_dob)
            # As soon as we hit -inf, there's no point continuing.
            if log_odds == MINUS_INFINITY:
                return log_odds

        # ---------------------------------------------------------------------
        # Surname
        # ---------------------------------------------------------------------
        if self.surname and other.surname:  # We have surnames to compare.
            log_odds = cfg.posterior_log_odds_surname(
                log_prior_odds=log_odds,
                proband_surname=self.surname,
                other_surname=other.surname,
                prestandardized=True
            )
            if log_odds == MINUS_INFINITY:
                return log_odds

        # ---------------------------------------------------------------------
        # Forename
        # ---------------------------------------------------------------------
        if self.forename and other.forename:  # We have forenames to compare.
            log_odds = cfg.posterior_log_odds_forename(
                log_prior_odds=log_odds,
                proband_forename=self.forename,
                other_forename=other.forename,
                prestandardized=True
            )
            if log_odds == MINUS_INFINITY:
                return log_odds

        # ---------------------------------------------------------------------
        # Middle names
        # ---------------------------------------------------------------------
        if self.middle_names and other.middle_names:
            log_odds = cfg.posterior_log_odds_middle_names(
                log_prior_odds=log_odds,
                proband_middle_names=self.middle_names,
                other_middle_names=other.middle_names,
                prestandardized=True
            )
            if log_odds == MINUS_INFINITY:
                return log_odds

        # ---------------------------------------------------------------------
        # Postcodes
        # ---------------------------------------------------------------------
        if self.postcodes and other.postcodes:
            log_odds = cfg.posterior_log_odds_postcodes(
                log_prior_odds=log_odds,
                proband_postcodes=self.postcodes,
                other_postcodes=other.postcodes,
            )
            if log_odds == MINUS_INFINITY:
                return log_odds

        # ---------------------------------------------------------------------
        # Done
        # ---------------------------------------------------------------------
        return log_odds

    def _log_odds_same_hashed(self, other: "Person",
                              cfg: MatchConfig) -> float:
        """
        Returns the log odds that this and ``other`` are the same person,
        using plaintext information.

        Args:
            other: another :class:`Person` object
            cfg: the master :class:`MatchConfig` object

        Returns:
            float: the log odds they're the same person
        """
        raise NotImplementedError


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
                 should_match: bool) -> None:
        """
        Args:
            cfg: the master :class:`MatchConfig` object
            person_a: one representation of a person
            person_b: another representation of a person
            should_match: should they be treated as the same person?
        """
        self.cfg = cfg
        self.person_a = person_a
        self.person_b = person_b
        self.should_match = should_match

    def log_odds_same_plaintext(self) -> float:
        """
        Checks whether the plaintext person objects match.

        Returns:
            float: the log odds that they are the same person
        """
        return self.person_a.log_odds_same(self.person_b, self.cfg)

    def log_odds_same_hashed(self) -> float:
        """
        Checks whether the hashed versions match.

        Returns:
            float: the log odds that they are the same person
        """
        hashed_a = self.person_a.hashed(self.cfg.hasher)
        hashed_b = self.person_b.hashed(self.cfg.hasher)
        return hashed_a.log_odds_same(hashed_b, self.cfg)

    def matches_plaintext(self) -> bool:
        """
        Do the plaintext versions match, by threshold?

        Returns:
            bool: is there a match?
        """
        log_odds = self.log_odds_same_plaintext()
        return self.cfg.person_matches(log_odds)

    def matches_hashed(self) -> bool:
        """
        Do the raw versions match, by threshold?

        Returns:
            bool: is there a match?
        """
        log_odds = self.log_odds_same_hashed()
        return self.cfg.person_matches(log_odds)

    def assert_correct(self) -> None:
        """
        Asserts that both the raw and hashed versions match, or don't match,
        according to ``self.should_match``.
        """
        matches_raw = self.matches_plaintext()
        if matches_raw != self.should_match:
            log_odds = self.log_odds_same_plaintext()
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
        matches_hashed = self.matches_hashed()
        if matches_hashed != self.should_match:
            log_odds = self.log_odds_same_hashed()
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
                f"hashed_a = {self.person_a.hashed(self.cfg.hasher)}, "
                f"hashed_b = {self.person_b.hashed(self.cfg.hasher)}"
            )
            log.critical(msg)
            raise AssertionError(msg)


# =============================================================================
# Self-testing
# =============================================================================

def selftest(cfg: MatchConfig) -> None:
    for surname in ["Smith", "Jones", "Blair", "Cardinal", "XYZ"]:
        f = cfg.surname_freq(surname)
        log.info(f"Surname frequency for {surname}: {f}")

    for forename in ["James", "Rachel", "Phoebe", "XYZ"]:
        f = cfg.forename_freq(forename)
        log.info(f"Forename frequency for {forename}: {f}")

    test_values = [
        # Easy match
        TestCondition(
            cfg=cfg,
            person_a=Person(
                forename="Alice",
                middle_names=["Beatrice", "Celia"],
                surname="Jones",
                dob="2000-01-01",
                postcodes=["CB98 7YZ"]
            ),
            person_b=Person(
                forename="Alice",
                middle_names=["Beatrice"],
                surname="Jones",
                dob="2000-01-01",
                postcodes=["CB98 7YZ"]
            ),
            should_match=True
        ),
        # Easy non-match
        TestCondition(
            cfg=cfg,
            person_a=Person(
                forename="Alice",
                surname="Jones",
                dob="2000-01-01",
                postcodes=["CB98 7YZ"]
            ),
            person_b=Person(
                forename="Bob",
                surname="Smith",
                dob="1950-05-30",
                postcodes=["AB12 3CD"]
            ),
            should_match=False
        ),
    ]  # type: List[TestCondition]
    for test in test_values:
        test.assert_correct()


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    """
    Command-line entry point.
    """
    defaultdir = os.path.abspath(os.path.join(THIS_DIR, "..", "..", "working"))

    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Be verbose"
    )
    parser.add_argument(
        "--key", type=str,
        default="_?6~2+#)1VUr)(&v'19F$KXR*d0cV?ve'2UlO)r5V/L28n{9JdAU/1^]-Ss?'<",  # noqa
        help="Key (passphrase) for hasher"
    )
    parser.add_argument(
        "--selftest", action="store_true",
        help="Run self-tests and stop"
    )
    parser.add_argument(
        "--forename_freq_csv", type=str,
        default=os.path.join(defaultdir, "us_forename_freq.csv"),
        help='CSV file of "name, frequency" pairs for forenames'
    )
    parser.add_argument(
        "--surname_freq_csv", type=str,
        default=os.path.join(defaultdir, "us_surname_freq.csv"),
        help='CSV file of "name, frequency" pairs for forenames'
    )
    parser.add_argument(
        "--name_min_frequency", type=float, default=5e-6,
        help="Minimum base frequency for names. If a frequency is less than "
             "this, use this minimum. Allowing extremely low frequencies may "
             "increase the chances of a spurious match. Note also that "
             "typical name frequency tables don't give very-low-frequency "
             "information. For example, for US census forename/surname "
             "information, below 0.001 percent they report 0.000 percent; so "
             "a reasonable minimum is 0.0005 percent or 0.000005 or 5e-6."
    )
    parser.add_argument(
        "--population_size", type=int, default=UK_POPULATION_2017,
        help="Size of the whole population, from which we calculate the "
             "baseline log odds that two people, randomly selected (and "
             "replaced) from the population are the same person."
    )
    parser.add_argument(
        "--postcode_csv_filename", type=str,
        default=os.path.join(defaultdir, "INSERT_DEFAULT.csv"),
        help='CSV file of postcode geography from UK Census/ONS data'
    )
    parser.add_argument(
        "--mean_oa_population", type=int, default=UK_MEAN_OA_POPULATION_2011,
        help="Mean population of a UK Census Output Area, from which we "
             "estimate the population of postcode-based units."
    )
    default_min_p_for_match = 0.999999
    # .. want >=99.9999% posterior probability to declare a match
    parser.add_argument(
        "--min_log_odds_for_match", type=float,
        default=log_odds_from_probability(default_min_p_for_match),
        help=f"Minimum log odds of two people being the same, before a match "
             f"will be considered. Default is based on "
             f"p={default_min_p_for_match}."
    )
    parser.add_argument(
        "--p_minor_forename_error", type=float, default=0.001,
        help="Assumed probability that a forename has an error in that means "
             "it fails a full match but satisfies a partial (metaphone) match."
    )
    parser.add_argument(
        "--p_minor_surname_error", type=float, default=0.001,
        help="Assumed probability that a surname has an error in that means "
             "it fails a full match but satisfies a partial (metaphone) match."
    )
    parser.add_argument(
        "--p_minor_postcode_error", type=float, default=0.001,
        help="Assumed probability that a postcode has an error in that means "
             "it fails a full (postcode unit) match but satisfies a partial "
             "(postcode sector) match."
    )
    args = parser.parse_args()
    main_only_quicksetup_rootlogger(
        level=logging.DEBUG if args.verbose else logging.INFO)

    baseline_log_odds_same_person = log_odds_from_1_in_n(args.population_size)
    log.debug(f"Using population size: {args.population_size}")
    log.debug(f"Using baseline_log_odds_same_person: "
              f"{baseline_log_odds_same_person}")
    log.debug(f"Using min_log_odds_for_match: {args.min_log_odds_for_match}")
    cfg = MatchConfig(
        hasher_key=args.key,
        forename_csv_filename=args.forename_freq_csv,
        surname_csv_filename=args.surname_freq_csv,
        min_name_frequency=args.name_min_frequency,
        baseline_log_odds_same_person=baseline_log_odds_same_person,
        postcode_csv_filename=args.postcode_csv_filename,
        mean_oa_population=float(args.mean_oa_population),
        min_log_odds_for_match=args.min_log_odds_for_match,
        p_minor_forename_error=args.p_minor_forename_error,
        p_minor_surname_error=args.p_minor_surname_error,
        p_minor_postcode_error=args.p_minor_postcode_error,
    )

    if args.selftest:
        selftest(cfg)
        sys.exit(0)

    raise NotImplementedError


if __name__ == "__main__":
    main()
