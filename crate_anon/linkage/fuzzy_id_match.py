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


Terminology
-----------

A **proband** (index individual) is compared to a **sample** and a matching
individual is sought in the sample. There may be a match or no match.

It is assumed that both the proband and every person in the sample is drawn
from a background population (e.g. "everyone in the UK"), and that every person
in the sample is distinct.

A prototypical example: suppose a research organization wants to (and is
permitted to) send basic identifiers about a person to a government department
to obtain additional information on them. This person is the "proband"; the
government database is the "sample"; the whole population of that country is
the "population".

We'd like to ensure we can match people, in the absence of a helpful unique
numerical identifier, and in the presence of potential "errors" in the
information (e.g. alternative name spellings) -- directly (using plaintext
information such as names), and if possible, without using plaintext
information.

The term **forename** refers to all names that precede a surname (i.e. first
names and middle names).


Probability of a match, given that both are from the same population
--------------------------------------------------------------------

Given a description of a proband and a description of a specific member of the
sample, what is the probability that they are the same person?

The program takes the population size :math:`n_p` (e.g. UK population of ~66m)
as a parameter. The baseline probability of two people being a match is taken
as :math:`\frac{1}{n_p}`. Where information can be compared (e.g. if a date of
birth is present in both records), it can alter the match probability via a
Bayesian update process.

This yields an estimate of P(match | both people in population).

Specifically, if

- the hypothesis :math:`H` is that the two records are from the same person;
- the alternative hypothesis :math:`\neg H` is that they are from different
  people;
- :math:`D` indicates the data -- specifically (where it makes a difference)
  the data from the proband;

then we calculate

.. math::

    P(H | D) &= \frac{ P(D | H) \cdot P(H) }{ P(D) }  \\

    \text{posterior} &= \frac{ \text{likelihood} \cdot \text{prior} }
                             { \text{marginal likelihood} }

It's more convenient to work with log odds:

.. math::

    P(H | D) &= \frac{ P(D | H) \cdot P(H) }{ P(D) }  \\

    P(\neg H | D) &= \frac{ P(D | \neg H) \cdot P(\neg H) }{ P(D) }  \\

    \frac{ P(H | D) }{ P(\neg H | D) } &=
        \frac{ P(D | H) }{ P(D | \neg H) } \cdot
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
information is to use an accurate (specific) and a blurry (fuzzy) match. Let's
develop a method that could be generalized to hashed information.

For a given single piece of information (e.g. surname), if

- :math:`p_e` is the probability of there being a data error such that a
  full match becomes a partial (fuzzy) match;
- we will reject anything that is neither a full match nor a partial match;
- the hypothesis :math:`H` is that the person is the same;
- :math:`D` indicates the data (in this situation there are three
  possibilities: a full match, a partial but not a full match, and no match);
- :math:`p_f` is the probability of a randomly selected person giving a
  full match to our proband (e.g. same first name, or same postcode unit);
- :math:`p_p` is the probability of a randomly selected person giving a
  partial (fuzzy) match to our proband (e.g. same fuzzy first name, or same
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
| (sum of probabilities)       | 1                | 1                     |
+------------------------------+------------------+-----------------------+


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


Role of the sampling fraction
-----------------------------

We move now from a comparison between the proband and a single individual in
our database to a comparison between the proband and the whole database.

The sampling fraction makes no difference, but the population size is
important. Some illustrations follow, in which we assume there are no spelling
mistakes and we match only on first name.


**Situation A.**

The population and sample are the same (n = 2) and are {Alice, Bob}. The
proband is named Alice (is, in fact, the only Alice).

+---------------+-----------------------------------------------------------+
|               | Proband Alice versus:                                     |
+---------------+---------------------------+-------------------------------+
| Sample member | Alice                     | Bob                           |
+---------------+---------------------------+-------------------------------+
| P(H)          | :math:`\frac{1}{2}`                                       |
+---------------+-----------------------------------------------------------+
| odds(H)       | :math:`\frac{1}{1}`                                       |
+---------------+---------------------------+-------------------------------+
| P(D | H)      | 1                         | 0                             |
+---------------+---------------------------+-------------------------------+
| P(D | ¬H)     | 0 :sup:`*`                | 1                             |
+---------------+---------------------------+-------------------------------+
| LR            | :math:`\infty`            | 0                             |
+---------------+---------------------------+-------------------------------+
| odds(H | D)   | :math:`\infty`            | 0                             |
+---------------+---------------------------+-------------------------------+
| P(H | D)      | 1                         | 0                             |
+---------------+---------------------------+-------------------------------+

:sup:`*` In this situation, if the proband is not Alice, they're definitely not
called Alice.


**Situation B.**

The sample remains {Alice, Bob}, but now the population (n = 100) has 50
different people named Alice and 50 different people named Bob. The proband is
one of the Alices.

+---------------+-----------------------------------------------------------+
|               | Proband Alice versus:                                     |
+---------------+---------------------------+-------------------------------+
| Sample member | Alice                     | Bob                           |
+---------------+---------------------------+-------------------------------+
| P(H)          | :math:`\frac{1}{100}`                                     |
+---------------+-----------------------------------------------------------+
| odds(H)       | :math:`\frac{1}{99}`                                      |
+---------------+---------------------------+-------------------------------+
| P(D | H)      | 1                         | 0                             |
+---------------+---------------------------+-------------------------------+
| P(D | ¬H)     | :math:`\frac{49}{99}`     | :math:`\frac{50}{100}`        |
+---------------+---------------------------+-------------------------------+
| LR            | :math:`\frac{99}{49}`     | 0                             |
+---------------+---------------------------+-------------------------------+
| odds(H | D)   | :math:`\frac{1}{49}`      | 0                             |
+---------------+---------------------------+-------------------------------+
| P(H | D)      | 0.02                      | 0                             |
+---------------+---------------------------+-------------------------------+

This demonstrates the role of the population size in the calculations.

However, the numbers would be exactly the same if the sampling fraction were
increased by adding another Bob, or another 50 Bobs, to the sample. This
demonstrates the irrelevance of the sampling fraction.


**Situation C: a tie.**

There are two people named Alice, and they constitute the sample. The
population (n = 100) is them plus 98 people called Bob. The proband is one of
the Alices.

+---------------+-----------------------------------------------------------+
|               | Proband Alice versus:                                     |
+---------------+---------------------------+-------------------------------+
| Sample member | Alice 1                   | Alice 2                       |
+---------------+---------------------------+-------------------------------+
| P(H)          | :math:`\frac{1}{100}`                                     |
+---------------+-----------------------------------------------------------+
| odds(H)       | :math:`\frac{1}{99}`                                      |
+---------------+---------------------------+-------------------------------+
| P(D | H)      | 1                         | 1                             |
+---------------+---------------------------+-------------------------------+
| P(D | ¬H)     | :math:`\frac{1}{99}`      | :math:`\frac{1}{99}`          |
+---------------+---------------------------+-------------------------------+
| LR            | 99                        | 99                            |
+---------------+---------------------------+-------------------------------+
| odds(H | D)   | 1                         | 1                             |
+---------------+---------------------------+-------------------------------+
| P(H | D)      | 0.5                       | 0.5                           |
+---------------+---------------------------+-------------------------------+


**Situation D: a frequency error.**

The situation is as in C -- but now we underestimate the frequency of the name
Alice, calling it **0.001** (rather than the correct value of approximately
0.01). Bold indicates the errors.

+---------------+-----------------------------------------------------------+
|               | Proband Alice versus:                                     |
+---------------+---------------------------+-------------------------------+
| Sample member | Alice 1                   | Alice 2                       |
+---------------+---------------------------+-------------------------------+
| P(H)          | :math:`\frac{1}{100}`                                     |
+---------------+-----------------------------------------------------------+
| odds(H)       | :math:`\frac{1}{99}`                                      |
+---------------+---------------------------+-------------------------------+
| P(D | H)      | 1                         | 1                             |
+---------------+---------------------------+-------------------------------+
| P(D | ¬H)     | **0.001**                 | **0.001**                     |
+---------------+---------------------------+-------------------------------+
| LR            | **1000**                  | **1000**                      |
+---------------+---------------------------+-------------------------------+
| odds(H | D)   | **10.1**                  | **10.1**                      |
+---------------+---------------------------+-------------------------------+
| P(H | D)      | **0.91**                  | **0.91**                      |
+---------------+---------------------------+-------------------------------+

The possibility of such errors is a real one. As a result, a probability
threshold on the winner is not enough -- inaccuracies may mean that there is
more than one "winner".

However, we cannot pitch candidate winners against each other by their
estimated probabilities. We show that as follows:

  - Let :math:`n_s` be the sample size and :math:`n_p` be the population size.

  - Let :math:`H_i` indicate the hypothesis that person :math:`i` in the sample
    is the proband.

  - So, we begin with a list of probabilities :math:`P(H_i | D, \text{both
    people in population})`. Dropping our constant assumption that everyone is
    in the population, this is :math:`P(H_i | D)`. It is always true that

    .. math::

        P(H_i | D) &= \frac{ P(D | H_i) P(H_i) }{ P(D) }  \\

                   &= \frac{ \text{likelihood} \cdot \text{prior} }
                           { \text{marginal likelihood} }

    .. comment

        The ampersand-equals (&=) and "\\" combinations indicates alignment
        points. See
        https://shimizukawa-sphinx.readthedocs.io/en/latest/ext/math.html.

If it is the case that our proband *must* be in the sample, then we could
proceed as follows.

    .. math::

        P(\text{proband in sample}) &= 1  \\

        \sum_{j=1}^{n_s} P(H_j) &= 1  \\

        P(H_i | D) &= \frac{ P(D | H_i) P(H_i) / P(D) }
                           { \sum_{j=1}^{n_s} P(D | H_j) P(H_j) / P(D) }  \\

                   &= \frac{ \frac{ 1 }{ p(D) } P(D | H_i) P(H_i) }
                           { \frac{ 1 }{ p(D) } \sum_{j=1}^{n_s} P(D | H_j) P(H_j) }  \\

                   &= \frac{ P(D | H_i) P(H_i) }
                           { \sum_{j=1}^{n_s} P(D | H_j) P(H_j) }

    Compare [#gronau2017]_.

    With equal priors, :math:`H_i = H_j \forall i, j` and the expression above
    reduces to:

    .. math::

        P(H_i | D) = \frac{ P(D | H_i) }
                          { \sum_{j=1}^{n_s} P(D | H_j) }

    In log form (with natural logarithms),

    .. math::

        \log P(H_i | D) &= \log P(D | H_i) -
                           \log \sum_{j=1}^{n_s} e^{ log P(D | H_j) }

    or in pseudocode:

    .. code-block:: none

        log_posterior_p_match[i] = log_likelihood[i] - logSumExp(log_likelihood)

But the proband is not necessarily in the sample.

The probability of the proband being in the sample is :math:`p_s =
\frac{n_s}{n_p}`. But it is clearly not the case that we can multiple our
per-item probabilities by :math:`p_s`:

    .. math::

        P(H_i | D) \neq p_s \frac{ P(D | H_i) }
                                 { \sum_{j=1}^{n_s} P(D | H_j) }

For example, if :math:`p_s = 0.02` as in situation C above, it would be wrong
to cap the posterior probability at 0.02.

We have already seen that changing the sampling fraction is irrelevant; thus
:math:`p_s` is too.

So, the correct posterior probability is given by :math:`P(H_i | D), \forall
i`. All we have to do is add some sanity check for incorrect priors. We
implement that by requiring that the winner exceed the runner up by a certain
log odds.


Strategy for matching people
----------------------------

- find all people whose probability (or log odds) of matching exceeds the
  minimum probability (or log odds) required for a match;

- declare the most likely a match if their log odds exceeds that of the
  runner-up by a certain amount;

- otherwise, there is no match.


Specific implementations for names, DOB, and postcode
-----------------------------------------------------

Fairly easy: first name, surname, DOB (very unlikely to be absent).

- First names are assumed to be fixed (not e.g. interchangeable with a middle
  name). This may be too restrictive (leading to under-recognition of matches)
  if e.g. someone is formally named Arthur Brian JONES but is always known as
  Brian.

- Surnames are assumed to be fixed (not e.g. interchangeable with a first
  name). This assumption may be too restrictive (leading to under-recognition
  of matches) with e.g. Chinese names (written and spoken in Chinese as:
  SURNAME Firstname, sometimes Anglicized as Firstname SURNAME, and often
  confused by English-speaking people).

- Dates of birth are assumed to be error-free (which may be incorrect) (*).

  - (*) Known real-world categories of DOB error include:

    - day/month transposition
    - plain numerical typographical errors
    - entering today's date as a date of birth

Harder: middle names

- We could consider only "shared middle names". Then, the order of middle names
  is ignored; the test is "sharing a middle name" (or more than one middle
  names). So "A B C D" is just a good a match to "A B C D" as "A C B D" is.

  However, with a proband "A D", that makes "A D" and "A B C D" equally good
  matches; perhaps that is not so plausible (you might expect "A D" to be
  slightly more likely).

  We could extend this by considering (a) middle names present in the proband
  but absent from the sample, and (b) middle names present in the proband but
  absent in the sample.

- We end up with a more full scheme:

  .. code-block:: none

    define global P(proband middle name omitted) (e.g. 0.1)
    define global P(sample middle name omitted) (e.g. 0.1)

    n_proband_middle_names = ...
    n_sample_middle_names = ...
    for mn in shared_exact_match_middle_names:
        P(D | H) = 1 - p_e
        P(D | ¬H) = name_frequency
    for mn in shared_partial_but_not_exact_match_middle_names:
        P(D | H) = p_e
        P(D | ¬H) = metaphone_frequency - name_frequency
    for mn in mismatched_middle_names:
        P(D | H) = 0
        P(D | ¬H) = 1 - metaphone_frequency
    for i, mn in enumerate(proband_but_not_sample_middle_names, start=1):
        P(D | H) = P(sample middle name omitted)
        # ... rationale: they are the same person, but this middle name is
        #     not present in the sample record
        P(D | ¬H) = P(person has a "n_sample_middle_names + i"th middle name,
                      given that they have "n_sample_middle_names + i - 1" of
                      them)
        # ... rationale: they are not the same person; the proband has an
        #     additional middle name at position n (sort of -- exact order is
        #     ignored!); how likely is that?
    for i, mn in enumerate(sample_but_not_proband_middle_names, start=1):
        P(D | H) = P(proband middle name omitted)
        # ... rationale: they are the same person, but this middle name is
        #     not present in the proband record
        P(D | ¬H) = P(person has a "n_sample_middle_names + i"th middle name,
                      given that they have "n_sample_middle_names + i - 1" of
                      them)
        # ... rationale: they are not the same person; the sample has an
        #     additional middle name at position n (sort of -- exact order is
        #     ignored!); how likely is that?

    # Roughly 80% of UK children in ~2013 had a middle name [1].
    # Roughly 11% of people have at least two. So P(two | one) = 0.1375.

    # [1] Daily Mail, 29 Nov 2013:
    # https://www.dailymail.co.uk/news/article-2515376/Middle-names-booming-80-children-given-parents-chosen-honour-lost-relatives.html

Harder: postcodes

- Postcodes are assumed to provide evidence if there is a match, but not to
  weaken the case if they don't match. This is appropriate for historical
  records; e.g. if they lived as postcode A when they went to school, so that's
  their postcode in a national education database, but then live for more than
  a decade at postcode B before first presenting to mental health NHS services,
  that's all perfectly plausible -- the lack of match doesn't provide clear
  evidence against a match, but an overlap would provide evidence for. A given
  person may have a long series of postcodes where they've lived. So we just
  pick the matches, if there are any.

Note that partial matches can certainly make a match a bit *less* likely
(relative to absence of information). For example, a first name of "Alice"
matching "Alice" might substantially increase the probability; an absent first
name in a record won't change the probability (i.e. will tend to leave it at a
low level); "Alec" versus "Alice" might decrease the probability even though
they have the same metaphone (because the "typo" error probability is low
relative to the metaphone frequency); "Bob" versus "Alice" is a mismatch and
will take the probability to zero.


Statistical assumptions include
-------------------------------

- independence of first name, middle name(s), surname, DOB, postcode


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


Validation strategy
-------------------

- Create a collection of people from a real data set with the following
  details:

  - unique identifier (for internal checks only; not for comparison)
  - first name
  - any middle names (ordered)
  - surname
  - DOB
  - a single specimen postcode

- Split that data set into two (arbitrarily, 50:50). One half is the "sample",
  one is the "others".

- Establish P(unique plaintext match | proband in sample) -- should be close to
  1.

- Establish P(unique plaintext match | proband in others) -- should be close to
  0.

- Establish P(unique hashed match | proband in sample).

- Establish P(unique hashed match | proband in others).

- More broadly, for every individual (sample and others), treat that person as
  a proband and establish P(match) and P(next best match), represented as log
  odds. That allows generation of a ROC curve based on the "match" threshold
  and the "better than the next one" threshold.

- For a data set of size :math:`n`, this gives :math:`\frac{n^2}{2}`
  comparisons.

- Then, repeat these with "typos" or "deletions".

  - No point in surname or DOB typo as our rule excludes that.


Speed
-----

On a test 3 GHz desktop, this code takes approximately 100 μs to hash a person
record, and 14-40 μs to compare two records (see timing tests).

A comparison of 1000 pre-hashed subjects to 50m records requiring hashing,
without any caching, is going to take about 1000 * 50m * 120 μs, or quite a
long time -- a big part of which would be pointless re-hashing. A reasonable
strategy for a large database would therefore be to:

- pre-hash the sample with the agreed key (e.g. about 1.8 hours for 66m
  records);
- for each hashed proband, restrict the comparison to those with a matching
  hashed DOB, and either a partial or a full match on surname (e.g. for "SMITH",
  with a frequency of about 0.01, this would give about 1800 records to check;
  checking would take up to about 40 μs each (so up to 72 ms per proband) --
  plus some query time;
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

.. code-block:: r

    h <- 100 / 1e6  # 100 microseconds, in seconds
    c <- 20 / 1e6  # 20 microseconds
    t <- function(n) { h * n + c * n^2 / 2 }  # function relating time to n
    target <- 60 * 60  # target time: 1 hour = 3600 seconds
    errfunc <- function(n) { (t(n) - target) ^ 2 }  # function giving error
    result <- optim(par=50, fn=errfunc)  # minimize error, start n=50; gives 18967.5


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
import copy
import csv
import logging
import math
import os
import pdb
import pickle
import random
import re
import string
import sys
import timeit
from typing import (
    Any, Dict, Generator, Iterable, List, Optional, Set, Tuple, TYPE_CHECKING,
)

import appdirs
from cardinal_pythonlib.argparse_func import ShowAllSubparserHelpAction
from cardinal_pythonlib.hash import HmacSHA256Hasher
from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from cardinal_pythonlib.maths_py import round_sf
from cardinal_pythonlib.probability import (
    log_odds_from_1_in_n,
    log_odds_from_probability,
    log_posterior_odds_from_pdh_pdnh,
    log_probability_from_log_odds,
    probability_from_log_odds,
)
from cardinal_pythonlib.stringfunc import mangle_unicode_to_ascii
from fuzzy import DMetaphone

from crate_anon.anonymise.anonregex import get_uk_postcode_regex_elements
from crate_anon.common.constants import EXIT_FAILURE, EXIT_SUCCESS
from crate_anon.version import CRATE_VERSION

if TYPE_CHECKING:
    # noinspection PyProtectedMember
    from argparse import _SubParsersAction

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

dmeta = DMetaphone()

DAYS_PER_YEAR = 365.25  # approximately!
DEFAULT_HASH_KEY = "fuzzy_id_match_default_hash_key_DO_NOT_USE_FOR_LIVE_DATA"
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

def get_uk_postcode_regex() -> str:
    """
    Returns a regex strings for (exact) UK postcodes. These have a
    well-defined format.
    """
    e = get_uk_postcode_regex_elements(at_word_boundaries_only=False)
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
        get_metaphone("Alice")  # ALK
        get_metaphone("Alec")  # matches Alice; ALK
        get_metaphone("Mary Ellen")  # MRLN
        get_metaphone("D'Souza")  # TSS
        get_metaphone("de Clerambault")  # TKRM; won't do accents

    """
    metaphones = dmeta(x)
    first_part = metaphones[0]  # the first part only
    if first_part is None:
        log.warning(f"No metaphone for {x!r}; dmeta() returned {metaphones}")
        return ""
    return dmeta(x)[0].decode("ascii")


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
            f"[P(D|H)={self.p_d_given_h},"
            f" P(D|¬H)={self.p_d_given_not_h}]"
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
            float: posterior log odds, as above
        """
        return log_posterior_odds_from_pdh_pdnh(
            log_prior_odds=prior_log_odds,
            p_d_given_h=self.p_d_given_h,
            p_d_given_not_h=self.p_d_given_not_h
        )


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
            p_d_given_same_person: P(D | H)
            p_d_given_diff_person: P(D | ¬H)
        """
        super().__init__(**kwargs)
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


class SimpleComparison(Comparison):
    """
    Represents a comparison when there can be a match or not.
    """
    def __init__(self,
                 match: bool,
                 p_match_given_same_person: float,
                 p_match_given_diff_person: float,
                 **kwargs) -> None:
        """
        Args:
            match: data
            p_d_given_h: P(D | H)
            p_d_given_not_h: P(D | ¬H)
        """
        super().__init__(**kwargs)
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
            return self.p_match_given_same_person
        else:
            return 1 - self.p_match_given_same_person

    @property
    def p_d_given_not_h(self) -> float:
        if self.match:
            return self.p_match_given_diff_person
        else:
            return 1 - self.p_match_given_diff_person


class FullOrPartialComparison(Comparison):
    """
    Represents a comparison where there can be a full or a partial match.
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
            full_match: was there a full match?
            p_f: :math:`p_f = P(\text{full match} | \neg H)`
            p_e: :math:`p_e = P(\text{partial but not full match} | H)`
            partial_match: was there a partial match?
            p_p: :math:`p_p = P(\text{partial match} | \neg H)`
        """
        super().__init__(**kwargs)
        assert p_p >= p_f, f"p_p={p_p}, p_f={p_f}, but should have p_p >= p_f"
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
            return 1 - self.p_p


def bayes_compare(prior_log_odds: float,
                  comparisons: Iterable[Optional[Comparison]]) -> float:
    """
    Works through multiple comparisons and returns posterior log odds.

    Args:
        prior_log_odds: prior log odds
        comparisons: an iterable of :class:`Comparison` objects

    Returns:
        float: posterior log odds
    """
    log_odds = prior_log_odds
    for comparison in comparisons:
        if comparison is None:
            continue
        next_log_odds = comparison.posterior_log_odds(log_odds)
        if next_log_odds > log_odds:
            change = "more likely"
        elif next_log_odds < log_odds:
            change = "less likely"
        else:
            change = "no change"
        log.debug(f"{comparison}: {log_odds} -> {next_log_odds} ({change})")
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
                 min_frequency: float = 5e-6) -> None:
        """
        Initializes the object from a CSV file.

        Args:
            csv_filename:
                CSV file, with no header, of "name, frequency" pairs.
            cache_filename:
                File in which to cache information, for faster loading.
            min_frequency:
                minimum frequency to allow; see command-line help.
        """
        assert csv_filename and cache_filename
        self._csv_filename = csv_filename
        self._cache_filename = cache_filename
        self._min_frequency = min_frequency
        self._name_freq = {}  # type: Dict[str, float]
        self._metaphone_freq = {}  # type: Dict[str, float]

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
                    freq = max(float(row[1]), min_frequency)
                    metaphone = get_metaphone(name)
                    name_freq[name] = freq
                    # https://stackoverflow.com/questions/12992165/python-dictionary-increment  # noqa
                    metaphone_freq[metaphone] = (
                        metaphone_freq.get(metaphone, 0) + freq
                    )
            log.info("... done")
            # Save to cache
            cache_save(cache_filename, [name_freq, metaphone_freq])

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
            oa_unit_counter = collections.Counter()
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
            hasher_key: str,
            rounding_sf: int,
            forename_csv_filename: str,
            forename_cache_filename: str,
            surname_csv_filename: str,
            surname_cache_filename: str,
            min_name_frequency: float,
            p_middle_name_n_present: List[float],
            population_size: int,
            postcode_csv_filename: str,
            postcode_cache_filename: str,
            mean_oa_population: float,
            min_log_odds_for_match: float,
            exceeds_next_best_log_odds: float,
            p_minor_forename_error: float,
            p_minor_surname_error: float,
            p_proband_middle_name_missing: float,
            p_sample_middle_name_missing: float,
            p_minor_postcode_error: float) -> None:
        """
        Args:
            hasher_key:
                Key (passphrase) for hasher.
            rounding_sf:
                Number of significant figures to use when rounding frequency
                information in hashed copies.
            forename_csv_filename:
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
        """
        assert all(0 <= x <= 1 for x in p_middle_name_n_present)
        assert population_size > 0
        assert 0 <= p_minor_forename_error <= 1
        assert 0 <= p_minor_surname_error <= 1
        assert 0 <= p_proband_middle_name_missing <= 1
        assert 0 <= p_sample_middle_name_missing <= 1
        assert 0 <= p_minor_postcode_error <= 1

        log.debug("Building MatchConfig...")

        self.hasher = Hasher(hasher_key)
        self.rounding_sf = rounding_sf
        self.forename_csv_filename = forename_csv_filename
        self.surname_csv_filename = surname_csv_filename
        self.min_name_frequency = min_name_frequency
        self.p_middle_name_n_present = p_middle_name_n_present
        self.population_size = population_size
        self.min_log_odds_for_match = min_log_odds_for_match
        self.exceeds_next_best_log_odds = exceeds_next_best_log_odds
        self.p_minor_forename_error = p_minor_forename_error
        self.p_minor_surname_error = p_minor_surname_error
        self.p_proband_middle_name_missing = p_proband_middle_name_missing
        self.p_sample_middle_name_missing = p_sample_middle_name_missing
        self.p_minor_postcode_error = p_minor_postcode_error

        self._forename_freq = NameFrequencyInfo(
            csv_filename=forename_csv_filename,
            cache_filename=forename_cache_filename,
            min_frequency=min_name_frequency)
        self._surname_freq = NameFrequencyInfo(
            csv_filename=surname_csv_filename,
            cache_filename=surname_cache_filename,
            min_frequency=min_name_frequency)
        self._postcode_freq = PostcodeFrequencyInfo(
            csv_filename=postcode_csv_filename,
            cache_filename=postcode_cache_filename,
            mean_oa_population=mean_oa_population)

        log.debug("... MatchConfig built")

    @property
    def baseline_log_odds_same_person(self) -> float:
        """
        Returns the log odds that a proband randomly selected from the
        population matches someone in our sample.
        """
        return log_odds_from_1_in_n(self.population_size)

    def forename_freq(self, name: str, prestandardized: bool = False) -> float:
        """
        Returns the baseline frequency of a forename.

        Args:
            name: the name to check
            prestandardized: was it pre-standardized?
        """
        freq = self._forename_freq.name_frequency(name, prestandardized)
        log.debug(f"    Forename frequency for {name}: {freq}")
        return freq

    def forename_metaphone_freq(self, metaphone: str) -> float:
        """
        Returns the baseline frequency of a forename's metaphone.

        Args:
            metaphone: the metaphone to check
        """
        freq = self._forename_freq.metaphone_frequency(metaphone)
        log.debug(f"    Forename metaphone frequency for {metaphone}: {freq}")
        return freq

    def surname_freq(self, name: str, prestandardized: bool = False) -> float:
        """
        Returns the baseline frequency of a surname.

        Args:
            name: the name to check
            prestandardized: was it pre-standardized?
        """
        freq = self._surname_freq.name_frequency(name, prestandardized)
        log.debug(f"    Surname frequency for {name}: {freq}")
        return freq

    def surname_metaphone_freq(self, metaphone: str) -> float:
        """
        Returns the baseline frequency of a surname's metaphone.

        Args:
            metaphone: the metaphone to check
        """
        freq = self._surname_freq.metaphone_frequency(metaphone)
        log.debug(f"    Surname metaphone frequency for {metaphone}: {freq}")
        return freq

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
        log.debug(f"Postcode sector frequency for {postcode_sector}: {freq}")
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

    def p_middle_name_present(self, n: int) -> float:
        """
        Returns the probability (in the population) that someone has a middle
        name n, given that they have middle name n - 1.

        (For example, n = 1 gives the probability of having a middle name; n =
        2 is the probability of having a second middle name, given that you
        have a first middle name.)
        """
        assert n >= 1
        if not self.p_middle_name_n_present:
            return 0
        if n > len(self.p_middle_name_n_present):
            return self.p_middle_name_n_present[-1]
        return self.p_middle_name_n_present[n - 1]


# =============================================================================
# Person
# =============================================================================

class Person(object):
    """
    Represents a person. The information may be incomplete or slightly wrong.
    """
    _COMMON_ATTRS = [
        # not: "is_hashed",
        "unique_id",
        "research_id",
    ]
    PLAINTEXT_ATTRS = _COMMON_ATTRS + [
        "first_name",
        "middle_names",
        "surname",
        "dob",
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
        "hashed_postcode_units",
        "postcode_unit_frequencies",
        "hashed_postcode_sectors",
        "postcode_sector_frequencies",
    ]
    INT_ATTRS = [
        "unique_id",
    ]
    FLOAT_ATTRS = [
        "first_name_frequency",
        "first_name_metaphone_frequency",
        "middle_name_frequencies",
        "middle_name_metaphone_frequencies",
        "surname_frequency",
        "surname_metaphone_frequency",
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
        f"(Header row. Columns: {PLAINTEXT_ATTRS}. "
        f"Use semicolon-separated values for "
        f"{sorted(list(set(SEMICOLON_DELIMIT).intersection(PLAINTEXT_ATTRS)))}."
    )
    HASHED_CSV_FORMAT_HELP = (
        f"(Header row. Columns: {HASHED_ATTRS}. "
        f"Use semicolon-separated values for "
        f"{sorted(list(set(SEMICOLON_DELIMIT).intersection(HASHED_ATTRS)))}."
    )

    # -------------------------------------------------------------------------
    # __init__, __repr__, copy
    # -------------------------------------------------------------------------

    def __init__(self,
                 # State
                 is_hashed: bool = False,
                 # Reference codes
                 unique_id: int = None,
                 research_id: str = "",
                 # Plaintext
                 first_name: str = "",
                 middle_names: List[str] = None,
                 surname: str = "",
                 dob: str = "",
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
                 hashed_postcode_units: List[str] = None,
                 postcode_unit_frequencies: List[float] = None,
                 hashed_postcode_sectors: List[str] = None,
                 postcode_sector_frequencies: List[float] = None) -> None:
        """
        Args:
            is_hashed:
                Is this a hashed representation? If so, matching works
                differently.

            unique_id:
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
            postcodes:
                Any UK postcodes for this person.

            hashed_first_name:
                The forename, irreversibly hashed.
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
            hashed_postcode_units:
                Full postcodes (postcode units), hashed.
            postcode_unit_frequencies:
                Frequencies of each postcode unit.
            hashed_postcode_sectors:
                Postcode sectors, hashed.
            postcode_sector_frequencies:
                Frequencies of each postcode sector.
        """
        self.is_hashed = is_hashed
        self.unique_id = unique_id
        self.research_id = research_id

        self.first_name = standardize_name(first_name)
        self.middle_names = [
            standardize_name(x) for x in middle_names if x
        ] if middle_names else []
        self.surname = standardize_name(surname)
        self.dob = dob
        self.postcodes = [standardize_postcode(x)
                          for x in postcodes if x] if postcodes else []

        self.hashed_first_name = hashed_first_name
        self.first_name_frequency = first_name_frequency
        self.hashed_first_name_metaphone = hashed_first_name_metaphone
        self.first_name_metaphone_frequency = first_name_metaphone_frequency
        self.hashed_middle_names = hashed_middle_names or []
        self.middle_name_frequencies = middle_name_frequencies or []
        self.hashed_middle_name_metaphones = hashed_middle_name_metaphones or []  # noqa
        self.middle_name_metaphone_frequencies = middle_name_metaphone_frequencies or []  # noqa
        self.hashed_surname = hashed_surname
        self.surname_frequency = surname_frequency
        self.hashed_surname_metaphone = hashed_surname_metaphone
        self.surname_metaphone_frequency = surname_metaphone_frequency
        self.hashed_dob = hashed_dob
        self.hashed_postcode_units = hashed_postcode_units or []
        self.postcode_unit_frequencies = postcode_unit_frequencies or []
        self.hashed_postcode_sectors = hashed_postcode_sectors or []
        self.postcode_sector_frequencies = postcode_sector_frequencies or []

        # Validation:
        if is_hashed:
            # hashed
            assert (
                not self.first_name and
                not self.middle_names and
                not self.surname and
                not self.dob and
                not self.postcodes
            ), "Don't supply plaintext information for a hashed Person"
            if self.hashed_first_name:
                assert (
                    self.first_name_frequency is not None and
                    self.hashed_first_name_metaphone and
                    self.first_name_metaphone_frequency is not None
                )
            if self.hashed_middle_names:
                n_middle = len(hashed_middle_names)
                assert (
                    len(self.middle_name_frequencies) == n_middle and
                    len(self.hashed_middle_name_metaphones) == n_middle and
                    len(self.middle_name_metaphone_frequencies) == n_middle
                )
            if self.hashed_surname:
                assert (
                    self.surname_frequency is not None and
                    self.hashed_surname_metaphone and
                    self.surname_metaphone_frequency is not None
                )
            if self.dob:
                assert self.hashed_dob
            if self.hashed_postcode_units:
                n_postcodes = len(self.hashed_postcode_units)
                assert (
                    len(self.postcode_unit_frequencies) == n_postcodes and
                    len(self.hashed_postcode_sectors) == n_postcodes and
                    len(self.postcode_sector_frequencies) == n_postcodes
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
                not self.hashed_postcode_units and
                not self.postcode_unit_frequencies and
                not self.hashed_postcode_sectors and
                not self.postcode_sector_frequencies
            ), "Don't supply hashed information for a plaintext Person"
            if dob:
                assert ISO_DATE_REGEX.match(dob), f"Bad date: {dob}"
            for postcode in self.postcodes:
                assert POSTCODE_REGEX.match(postcode), f"Bad postcode: {postcode}"  # noqa

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
            return f"ID#{self.unique_id}, RID {self.research_id} (hashed)"
        else:
            return ", ".join([
                f"#{self.unique_id}",
                f"RID {self.research_id}",
                " ".join([self.first_name] +
                         self.middle_names +
                         [self.surname]),
                self.dob,
                " - ".join(self.postcodes)
            ])

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

    def plaintext_csv_dict(self) -> Dict[str, Any]:
        """
        Returns a dictionary suitable for :class:`csv.DictWriter`.
        """
        assert not self.is_hashed
        return self._csv_dict(self.PLAINTEXT_ATTRS)

    def hashed_csv_dict(self,
                        include_unique_id: bool = False) -> Dict[str, Any]:
        """
        Returns a dictionary suitable for :class:`csv.DictWriter`.

        Args:
            include_unique_id:
                include the (potentially identifying) ``unique_id`` data?
                Usually ``False``; may be ``True`` for validation.
        """
        assert self.is_hashed
        attrs = self.HASHED_ATTRS.copy()
        if not include_unique_id:
            attrs.remove("unique_id")
        return self._csv_dict(attrs)

    @classmethod
    def _from_csv(cls, rowdict: Dict[str, str], attrs: List[str],
                  is_hashed: bool) -> "Person":
        """
        Returns a :class:`Person` object from a CSV row.

        Args:
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
        return Person(is_hashed=is_hashed, **kwargs)

    @classmethod
    def from_plaintext_csv(cls, rowdict: Dict[str, str]) -> "Person":
        """
        Returns a :class:`Person` object from a plaintext CSV row.

        Args:
            rowdict: a CSV row, read via :class:`csv.DictReader`.
        """
        return cls._from_csv(rowdict, cls.PLAINTEXT_ATTRS, is_hashed=False)

    @classmethod
    def from_hashed_csv(cls, rowdict: Dict[str, str]) -> "Person":
        """
        Returns a :class:`Person` object from a hashed CSV row.

        Args:
            rowdict: a CSV row, read via :class:`csv.DictReader`.
        """
        return cls._from_csv(rowdict, cls.HASHED_ATTRS, is_hashed=True)

    # -------------------------------------------------------------------------
    # Created hashed version
    # -------------------------------------------------------------------------

    def hashed(self, cfg: MatchConfig) -> "Person":
        """
        Returns a :class:`Person` object but with all the elements hashed (if
        they are not blank).

        Args:
            cfg: the master :class:`MatchConfig` object
        """
        hasher = cfg.hasher

        def fr(f: float, sf: int = cfg.rounding_sf) -> float:
            """
            Rounds frequencies to a certain number of significant figures.
            (Don't supply exact floating-point numbers for frequencies; may be
            more identifying. Don't use decimal places; we have to deal with
            some small numbers.)
            """
            return round_sf(f, sf)

        return Person(
            is_hashed=True,
            unique_id=self.unique_id,
            research_id=self.research_id,
            hashed_first_name=(
                hasher.hash(self.first_name)
                if self.first_name else ""
            ),
            first_name_frequency=(
                fr(cfg.forename_freq(self.first_name, prestandardized=True))
                if self.first_name else None
            ),
            hashed_first_name_metaphone=(
                hasher.hash(get_metaphone(self.first_name))
                if self.first_name else ""
            ),
            first_name_metaphone_frequency=(
                fr(cfg.forename_metaphone_freq(get_metaphone(self.first_name)))
                if self.first_name else None
            ),
            hashed_middle_names=[
                hasher.hash(x)
                for x in self.middle_names if x
            ],
            middle_name_frequencies=[
                fr(cfg.forename_freq(x, prestandardized=True))
                for x in self.middle_names if x
            ],
            hashed_middle_name_metaphones=[
                hasher.hash(get_metaphone(x))
                for x in self.middle_names if x
            ],
            middle_name_metaphone_frequencies=[
                fr(cfg.forename_metaphone_freq(get_metaphone(x)))
                for x in self.middle_names if x
            ],
            hashed_surname=(
                hasher.hash(self.surname)
                if self.surname else ""
            ),
            surname_frequency=(
                fr(cfg.surname_freq(self.surname, prestandardized=True))
                if self.surname else None
            ),
            hashed_surname_metaphone=(
                hasher.hash(get_metaphone(self.surname))
                if self.surname else ""
            ),
            surname_metaphone_frequency=(
                fr(cfg.surname_metaphone_freq(get_metaphone(self.surname)))
                if self.surname else ""
            ),
            hashed_dob=(
                hasher.hash(self.dob)
                if self.dob else ""
            ),
            hashed_postcode_units=[
                hasher.hash(x)
                for x in self.postcodes if x
            ],
            postcode_unit_frequencies=[
                fr(cfg.postcode_unit_freq(x, prestandardized=True))
                for x in self.postcodes if x
            ],
            hashed_postcode_sectors=[
                hasher.hash(get_postcode_sector(x))
                for x in self.postcodes if x
            ],
            postcode_sector_frequencies=[
                fr(cfg.postcode_sector_freq(get_postcode_sector(x)))
                for x in self.postcodes if x
            ]
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
        log.debug(f"Comparing self={self}; other={other}")
        return bayes_compare(
            prior_log_odds=cfg.baseline_log_odds_same_person,
            comparisons=self._gen_comparisons(other, cfg)
        )

    # -------------------------------------------------------------------------
    # Bayesian comparison
    # -------------------------------------------------------------------------

    def _gen_comparisons(self, other: "Person", cfg: MatchConfig) \
            -> Generator[Optional[Comparison], None, None]:
        """
        Generates all relevant comparisons.

        Args:
            other: another :class:`Person` object
            cfg: the master :class:`MatchConfig` object
        """
        yield self._comparison_dob(other)
        yield self._comparison_surname(other, cfg)
        yield self._comparison_forename(other, cfg)
        for c in self._comparisons_middle_names(other, cfg):
            yield c
        for c in self._comparisons_postcodes(other, cfg):
            yield c

    def _comparison_dob(self, other: "Person") -> Optional[Comparison]:
        """
        Returns a comparison for date of birth.

        There is no special treatment of 29 Feb (since this DOB is
        approximately 4 times less common than other birthdays, in principle it
        does merit special treatment, but we ignore that).
        """
        if self.is_hashed:
            # -----------------------------------------------------------------
            # Hashed
            # -----------------------------------------------------------------
            if not self.hashed_dob or not other.hashed_dob:
                return None
            matches = self.hashed_dob == other.hashed_dob
        else:
            # -----------------------------------------------------------------
            # Plaintext
            # -----------------------------------------------------------------
            if not self.dob or not other.dob:
                return None
            matches = self.dob == other.dob
        return SimpleComparison(
            name="DOB",
            match=matches,
            p_match_given_same_person=1,  # no typos allows in dates of birth
            p_match_given_diff_person=1 / DAYS_PER_YEAR
        )

    def _comparison_surname(self, other: "Person",
                            cfg: MatchConfig) -> Optional[Comparison]:
        """
        Returns a comparison for surname.
        """
        if self.is_hashed:
            # -----------------------------------------------------------------
            # Hashed
            # -----------------------------------------------------------------
            if (not self.hashed_surname or
                    not other.hashed_surname or
                    not self.hashed_surname_metaphone or
                    not other.hashed_surname_metaphone):
                return None
            full_match = self.hashed_surname == other.hashed_surname
            p_f = self.surname_frequency
            partial_match = (self.hashed_surname_metaphone ==
                             other.hashed_surname_metaphone)
            p_p = self.surname_metaphone_frequency
        else:
            # -----------------------------------------------------------------
            # Plaintext
            # -----------------------------------------------------------------
            if not self.surname or not other.surname:
                return None
            self_metaphone = get_metaphone(self.surname)
            other_metaphone = get_metaphone(other.surname)
            full_match = self.surname == other.surname
            p_f = cfg.surname_freq(self.surname, prestandardized=True)
            partial_match = self_metaphone == other_metaphone
            p_p = cfg.surname_metaphone_freq(self_metaphone)
        return FullOrPartialComparison(
            name="surname",
            full_match=full_match,
            p_f=p_f,
            p_e=cfg.p_minor_surname_error,
            partial_match=partial_match,
            p_p=p_p,
        )

    def _comparison_forename(self, other: "Person",
                             cfg: MatchConfig) -> Optional[Comparison]:
        """
        Returns a comparison for forename.
        """
        if self.is_hashed:
            # -----------------------------------------------------------------
            # Hashed
            # -----------------------------------------------------------------
            if (not self.hashed_first_name or
                    not other.hashed_first_name or
                    not self.hashed_first_name_metaphone or
                    not other.hashed_first_name_metaphone):
                return None
            full_match = self.hashed_first_name == other.hashed_first_name
            p_f = self.first_name_frequency
            partial_match = (self.hashed_first_name_metaphone ==
                             other.hashed_first_name_metaphone)
            p_p = self.first_name_metaphone_frequency
        else:
            # -----------------------------------------------------------------
            # Plaintext
            # -----------------------------------------------------------------
            if not self.first_name or not other.first_name:
                return None
            self_metaphone = get_metaphone(self.first_name)
            other_metaphone = get_metaphone(other.first_name)
            full_match = self.first_name == other.first_name
            p_f = cfg.forename_freq(self.first_name, prestandardized=True)
            partial_match = self_metaphone == other_metaphone
            p_p = cfg.forename_metaphone_freq(self_metaphone)
        return FullOrPartialComparison(
            name="forename",
            full_match=full_match,
            p_f=p_f,
            p_e=cfg.p_minor_forename_error,
            partial_match=partial_match,
            p_p=p_p,
        )

    def _comparisons_middle_names(
            self, other: "Person",
            cfg: MatchConfig) -> Generator[Comparison, None, None]:
        """
        Generates comparisons for middle names.
        """
        p_e = cfg.p_minor_forename_error
        if self.is_hashed:
            n_proband_middle_names = len(self.hashed_middle_names)
            n_sample_middle_names = len(other.hashed_middle_names)
        else:
            n_proband_middle_names = len(self.middle_names)
            n_sample_middle_names = len(other.middle_names)
        unused_proband_indexes = list(range(n_proband_middle_names))
        unused_sample_indexes = list(range(n_sample_middle_names))
        if self.is_hashed:
            # -----------------------------------------------------------------
            # Hashed
            # -----------------------------------------------------------------
            # Full matches
            for i, mn in enumerate(self.hashed_middle_names):
                if mn in other.hashed_middle_names:
                    unused_proband_indexes.remove(i)
                    unused_sample_indexes.remove(
                        other.hashed_middle_names.index(mn))
                    yield DirectComparison(
                        name="middle_name_hash_exact_match",
                        p_d_given_same_person=1 - p_e,
                        p_d_given_diff_person=self.middle_name_frequencies[i]
                    )
            # Partial matches
            for i, hmeta in enumerate(self.hashed_middle_name_metaphones):
                if i not in unused_proband_indexes:
                    continue  # this one already matched in full
                if hmeta in other.hashed_middle_name_metaphones:
                    unused_proband_indexes.remove(i)
                    unused_sample_indexes.remove(
                        other.hashed_middle_name_metaphones.index(hmeta))
                    yield DirectComparison(
                        name="middle_name_hash_metaphone_match",
                        p_d_given_same_person=p_e,
                        p_d_given_diff_person=(
                            self.middle_name_metaphone_frequencies[i] -
                            self.middle_name_frequencies[i]
                        )
                    )
        else:
            # -----------------------------------------------------------------
            # Plaintext
            # -----------------------------------------------------------------
            # Full matches
            for i, mn in enumerate(self.middle_names):
                if mn in other.middle_names:
                    unused_proband_indexes.remove(i)
                    unused_sample_indexes.remove(other.middle_names.index(mn))
                    yield DirectComparison(
                        name="middle_name_exact_match",
                        p_d_given_same_person=1 - p_e,
                        p_d_given_diff_person=cfg.forename_freq(
                            mn, prestandardized=True)
                    )
            # Partial matches
            other_metaphones = [get_metaphone(x) for x in other.middle_names]
            for i, mn in enumerate(self.middle_names):
                if i not in unused_proband_indexes:
                    continue  # this one already matched in full
                metaphone = get_metaphone(mn)
                if metaphone in other_metaphones:
                    unused_proband_indexes.remove(i)
                    unused_sample_indexes.append(
                        other_metaphones.index(metaphone))
                    yield DirectComparison(
                        name="middle_name_metaphone_match",
                        p_d_given_same_person=p_e,
                        p_d_given_diff_person=cfg.forename_metaphone_freq(metaphone)  # noqa
                    )
        # ---------------------------------------------------------------------
        # Both hashed and plaintext
        # ---------------------------------------------------------------------
        # Mismatches
        for i in unused_proband_indexes:
            if not unused_sample_indexes:
                break  # no "other" name left to mismatch against
            yield DirectComparison(
                name="middle_name_mismatch",
                p_d_given_same_person=0,
                p_d_given_diff_person=(
                    1 - self.middle_name_metaphone_frequencies[i]
                )
            )
            # Faster to remove elements from the end than the start:
            # https://stackoverflow.com/questions/33626623/the-most-efficient-way-to-remove-first-n-elements-in-a-list  # noqa
            del unused_sample_indexes[-1]
        # Proband names beyond length of sample
        n = n_proband_middle_names + 1
        for i in range(len(unused_proband_indexes)):
            yield DirectComparison(
                name="middle_name_proband_beyond_sample",
                p_d_given_same_person=cfg.p_sample_middle_name_missing,
                p_d_given_diff_person=cfg.p_middle_name_present(n),
            )
            n += 1
        # Sample names beyond length of proband
        n = n_sample_middle_names + 1
        for i in range(len(unused_sample_indexes)):
            yield DirectComparison(
                name="middle_name_sample_beyond_proband",
                p_d_given_same_person=cfg.p_proband_middle_name_missing,
                p_d_given_diff_person=cfg.p_middle_name_present(n),
            )
            n += 1

    def _comparisons_postcodes(
            self, other: "Person",
            cfg: MatchConfig) -> Generator[Comparison, None, None]:
        """
        Generates comparisons for postcodes.
        """
        p_e = cfg.p_minor_postcode_error
        indexes_of_full_matches = []  # type: List[int]
        if self.is_hashed:
            # -----------------------------------------------------------------
            # Hashed
            # -----------------------------------------------------------------
            for i, pu in enumerate(self.hashed_postcode_units):
                if pu in other.hashed_postcode_units:
                    indexes_of_full_matches.append(i)
                    yield SimpleComparison(
                        name="postcode_exact",
                        match=True,
                        p_match_given_same_person=1 - p_e,
                        p_match_given_diff_person=self.postcode_unit_frequencies[i]  # noqa
                    )
            for i, ps in enumerate(self.hashed_postcode_sectors):
                if i in indexes_of_full_matches:
                    continue  # this one already matched in full
                if ps in other.hashed_postcode_sectors:
                    yield SimpleComparison(
                        name="postcode_sector",
                        match=True,
                        p_match_given_same_person=p_e,
                        p_match_given_diff_person=self.postcode_sector_frequencies[i]  # noqa
                    )
        else:
            # -----------------------------------------------------------------
            # Plaintext
            # -----------------------------------------------------------------
            for i, pu in enumerate(self.postcodes):
                if pu in other.postcodes:
                    indexes_of_full_matches.append(i)
                    yield SimpleComparison(
                        name="postcode_exact",
                        match=True,
                        p_match_given_same_person=1 - p_e,
                        p_match_given_diff_person=cfg.postcode_unit_freq(
                            pu, prestandardized=True)
                    )
            other_ps_list = [get_postcode_sector(x) for x in other.postcodes]
            for i, pu in enumerate(self.postcodes):
                if i in indexes_of_full_matches:
                    continue  # this one already matched in full
                ps = get_postcode_sector(pu)
                if ps in other_ps_list:
                    yield SimpleComparison(
                        name="postcode_sector",
                        match=True,
                        p_match_given_same_person=p_e,
                        p_match_given_diff_person=cfg.postcode_sector_freq(ps)
                    )

    def plausible_candidate(self, other: "Person") -> bool:
        """
        Not all people are remotely plausible matches for each other. This
        function can be used to filter down a large group of people to the
        plausible candidates.

        Plausible candidates are those that share:

        - a DOB (since we require exact DOB matching); and
        - a surname or surname metaphone

        Args:
            other: a :class:`Person` object

        Returns:
            bool: is ``self`` a plausible match? See above.
        """
        if self.is_hashed:
            result = bool(
                self.hashed_dob and
                self.hashed_dob == other.hashed_dob and
                (
                    (self.hashed_surname and
                     self.hashed_surname == other.hashed_surname) or
                    (self.hashed_surname_metaphone and
                     self.hashed_surname_metaphone ==
                     other.hashed_surname_metaphone)
                )
            )
        else:
            result = bool(
                self.dob and
                self.dob == other.dob and
                self.surname and
                (self.surname == other.surname or
                 get_metaphone(self.surname) == get_metaphone(other.surname))
            )
        # log.critical(f"{self} //\n{other} //\n{result!r}")
        return result

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

    def n_postcodes(self) -> int:
        """
        How many postcodes does this person have?
        """
        if self.is_hashed:
            return len(self.hashed_postcode_units)
        else:
            return len(self.postcodes)

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

    def debug_mutate_something(self, cfg: MatchConfig) -> None:
        """
        Randomly mutate one of: first name, a middle name, or a postcode.

        Args:
            cfg: the master :class:`MatchConfig` object
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
                                                cfg)


# =============================================================================
# People: a collection of Person objects
# =============================================================================
# Try staring at the word "people" for a while and watch it look odd...

class People(object):
    def __init__(self,
                 verbose: bool = False,
                 person: Person = None,
                 people: List[Person] = None) -> None:
        """
        Creates a blank collection.
        """
        self.verbose = verbose
        self.people = []  # type: List[Person]
        if person:
            self.add_person(person)
        if people:
            self.add_people(people)

    def add_person(self, person: Person) -> None:
        """
        Adds a single person.
        """
        self.people.append(person)

    def add_people(self, people: List[Person]) -> None:
        """
        Adds multiple people.
        """
        self.people.extend(people)

    def size(self) -> int:
        """
        Returns the number of people in this object.
        """
        return len(self.people)

    def plausible_candidates(self, proband: Person) -> \
            Tuple[List[Person], List[int]]:
        """
        Returns a list of plausible candidates.

        Args:
            proband: a :class:`Person`

        Returns:
            tuple: candidates, candidate_indexes
        """
        candidates = []  # type: List[Person]
        candidate_indexes = []  # type: List[int]
        for i, p in enumerate(self.people):
            if p.plausible_candidate(proband):
                candidates.append(p)
                candidate_indexes.append(i)
        return candidates, candidate_indexes

    def get_unique_match_detailed(self,
                                  proband: Person,
                                  cfg: MatchConfig,
                                  scan_everyone: bool = False) \
            -> Tuple[Optional[Person], float, Optional[int], Optional[float]]:
        """
        Returns a single person matching the proband, or ``None`` if there is
        no match (as defined by the probability settings in ``cfg``).

        Args:
            proband: a :class:`Person`
            cfg: the master :class:`MatchConfig` object
            scan_everyone: be inefficient and return next-best log odds even
                if failure has occurred; ONLY FOR VALIDATION

        Returns:
            tuple:
                winner (:class:`Person`), best_log_odds (float),
                first_best_index (int), next_best_log_odds (float)

        Note that:

        - ``winner`` will be ``None`` if there is no winner
        - ``best_log_odds`` is the log odds of the best candidate (the winner,
          if it passes a threshold test), or –∞ if there are no candidates
        - ``first_best_index`` is the index of the first person whose log odds
          are ``best_log_odds``, or –∞ if there are no candidates
        - ``next_best_log_odds`` will be the log odds of the closest other
          contender scanned (but, in the event of no match being declared, this
          will only be the true second-place candidate if ``scan_everyone`` is
          ``True``; if ``scan_everyone`` is ``False``, then it will be the
          true second-place contender in the event of a match being declared,
          but might be the third-place or worse also-ran if a match was not
          declared).
        """
        verbose = self.verbose
        if verbose:
            log.info(f"{len(self.people)} people to be considered")
        # Stage 1: filter
        candidates, candidate_indexes = self.plausible_candidates(proband)
        if verbose:
            log.info(f"{len(candidates)} plausible candidates")
        if not candidates:
            return None, MINUS_INFINITY, None, None
        log_odds = [
            p.log_odds_same(proband, cfg)
            for p in candidates
        ]
        best_log_odds = max(log_odds)
        if verbose:
            log.info(f"best_log_odds = {best_log_odds}")
        first_best_idx_in_cand = log_odds.index(best_log_odds)  # candidate winner  # noqa
        first_best_idx_overall = candidate_indexes[first_best_idx_in_cand]
        if best_log_odds < cfg.min_log_odds_for_match:
            if verbose:
                log.info("Best is not good enough")
            return None, best_log_odds, None, None
        all_others_must_be_le = best_log_odds - cfg.exceeds_next_best_log_odds
        next_best_log_odds = MINUS_INFINITY
        failed = False
        for i, lo in enumerate(log_odds):
            if i == first_best_idx_in_cand:  # ignore the candidate winner
                continue
            next_best_log_odds = max(next_best_log_odds, lo)
            if lo > all_others_must_be_le:
                # Another person has log-odds that are high enough to exclude
                # a unique match.
                failed = True
                if verbose:
                    log.info(f"Another is too similar, with log odds {lo}")
                if not scan_everyone:
                    return (None, best_log_odds, first_best_idx_overall,
                            next_best_log_odds)
        if verbose and not failed:
            log.info("Found a winner")
        return (
            candidates[first_best_idx_in_cand] if not failed else None,
            best_log_odds,
            first_best_idx_overall,
            next_best_log_odds
        )

    def get_unique_match(self,
                         proband: Person,
                         cfg: MatchConfig) -> Optional[Person]:
        """
        Returns a single person matching the proband, or ``None`` if there is
        no match (as defined by the probability settings in ``cfg``).

        Args:
            proband: a :class:`Person`
            cfg: the master :class:`MatchConfig` object

        Returns:
            the winner (a :class:`Person`) or ``None``
        """
        winner, _, _, _ = self.get_unique_match_detailed(
            proband=proband,
            cfg=cfg,
            scan_everyone=False,
        )
        return winner

    def hashed(self, cfg: MatchConfig) -> "People":
        """
        Returns a hashed version of itself.

        Args:
            cfg: the master :class:`MatchConfig` object
        """
        return People(people=[p.hashed(cfg) for p in self.people])


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
        log.info("- Making hashed versions for later")
        self.hashed_a = self.person_a.hashed(self.cfg)
        self.hashed_b = self.person_b.hashed(self.cfg)

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
        return self.hashed_a.log_odds_same(self.hashed_b, self.cfg)

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
        unique_id=1,
        first_name="Alice",
        middle_names=["Beatrice", "Celia", "Delilah"],
        surname="Rarename",
        dob="2000-01-01",
        postcodes=["CB2 0QQ"]  # Addenbrooke's Hospital
    )
    alec_bcd_unique_2000_add = Person(
        unique_id=2,
        first_name="Alec",  # same metaphone as Alice
        middle_names=["Beatrice", "Celia", "Delilah"],
        surname="Rarename",
        dob="2000-01-01",
        postcodes=["CB2 0QQ"]  # Addenbrooke's Hospital
    )
    bob_bcd_unique_2000_add = Person(
        unique_id=3,
        first_name="Bob",
        middle_names=["Beatrice", "Celia", "Delilah"],
        surname="Rarename",
        dob="2000-01-01",
        postcodes=["CB2 0QQ"]  # Addenbrooke's Hospital
    )
    alice_bc_unique_2000_add = Person(
        unique_id=4,
        first_name="Alice",
        middle_names=["Beatrice", "Celia"],
        surname="Rarename",
        dob="2000-01-01",
        postcodes=["CB2 0QQ"]  # Addenbrooke's Hospital
    )
    alice_b_unique_2000_add = Person(
        unique_id=5,
        first_name="Alice",
        middle_names=["Beatrice"],
        surname="Rarename",
        dob="2000-01-01",
        postcodes=["CB2 0QQ"]  # Addenbrooke's Hospital
    )
    alice_jones_2000_add = Person(
        unique_id=6,
        first_name="Alice",
        surname="Jones",
        dob="2000-01-01",
        postcodes=["CB2 0QQ"]  # Addenbrooke's Hospital
    )
    bob_smith_1950_psych = Person(
        unique_id=7,
        first_name="Bob",
        surname="Smith",
        dob="1950-05-30",
        postcodes=["CB2 3EB"]  # Department of Psychology
        # postcodes=["AB12 3CD"]  # nonexistent postcode; will raise
    )
    alice_smith_1930 = Person(
        unique_id=8,
        first_name="Alice",
        surname="Smith",
        dob="1930-01-01",
    )
    alice_smith_2000 = Person(
        unique_id=9,
        first_name="Alice",
        surname="Smith",
        dob="2000-01-01",
    )
    alice_smith = Person(
        unique_id=10,
        first_name="Alice",
        surname="Smith",
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
    ]
    all_people_hashed = [p.hashed(cfg) for p in all_people]
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
    people_plaintext = People(verbose=True)
    people_plaintext.add_people(all_people)
    people_hashed = People(verbose=True)
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
            "alice_bcd_unique_2000_add.log_odds_same(alice_bcd_unique_2000_add, cfg)",  # noqa
            number=n_for_speedtest,
            globals=locals()
        ) / n_for_speedtest
        log.info(f"Plaintext full match: {t} μs per comparison")
        # On Wombat: 146 microseconds.

        t = microsec_per_sec * timeit.timeit(
            "alice_bcd_unique_2000_add.hashed(cfg).log_odds_same(alice_bcd_unique_2000_add.hashed(cfg), cfg)",  # noqa
            number=n_for_speedtest,
            globals=locals()
        ) / n_for_speedtest
        log.info(f"Hash two objects + full match: {t} μs per comparison")
        # On Wombat: 631 microseconds.

        t = microsec_per_sec * timeit.timeit(
            "alice_smith_1930.log_odds_same(alice_smith_2000, cfg)",
            number=n_for_speedtest,
            globals=locals()
        ) / n_for_speedtest
        log.info(f"Plaintext DOB mismatch: {t} μs per comparison")
        # On Wombat: 13.6 microseconds.

        t = microsec_per_sec * timeit.timeit(
            "alice_smith_1930.hashed(cfg).log_odds_same(alice_smith_2000.hashed(cfg), cfg)",  # noqa
            number=n_for_speedtest,
            globals=locals()
        ) / n_for_speedtest
        log.info(f"Hash two objects + DOB mismatch: {t} μs per comparison")
        # On Wombat: 240 microseconds.

        t = microsec_per_sec * timeit.timeit(
            "alice_smith_1930.hashed(cfg)",
            number=n_for_speedtest,
            globals=locals()
        ) / n_for_speedtest
        log.info(f"Hash one object: {t} μs per comparison")
        # On Wombat: 104 microseconds.

        return  # timing tests only

    # -------------------------------------------------------------------------
    # Main self-tests
    # -------------------------------------------------------------------------

    for surname in ["Smith", "Jones", "Blair", "Cardinal", "XYZ"]:
        f = cfg.surname_freq(surname)
        log.info(f"Surname frequency for {surname}: {f}")

    for forename in ["James", "Rachel", "Phoebe", "XYZ"]:
        f = cfg.forename_freq(forename)
        log.info(f"Forename frequency for {forename}: {f}")

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

    log.warning("Testing proband-versus-sample")
    for i in range(len(all_people)):
        proband_plaintext = all_people[i]
        log.warning(f"Plaintext search with proband: {proband_plaintext}")
        plaintext_winner = people_plaintext.get_unique_match(proband_plaintext, cfg)  # noqa
        log.warning(f"... WINNER: {plaintext_winner}")
        log.warning(f"Hashed search with proband: {proband_plaintext}\n")
        proband_hashed = all_people_hashed[i]  # same order
        hashed_winner = people_hashed.get_unique_match(proband_hashed, cfg)
        log.warning(f"... WINNER: {hashed_winner}")

    log.warning("... tests complete.")


# =============================================================================
# Loading people data
# =============================================================================

def read_people_2(csv_filename: str,
                  plaintext: bool = True,
                  alternate_groups: bool = False) -> Tuple[People, People]:
    """
    Read a list of people from a CSV file. See :class:`People` for the
    column details.

    Args:
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
    a = People()
    b = People()
    with open(csv_filename, "rt") as f:
        reader = csv.DictReader(f)
        for i, rowdict in enumerate(reader):
            if plaintext:
                person = Person.from_plaintext_csv(rowdict)
            else:
                person = Person.from_hashed_csv(rowdict)
            if alternate_groups and i % 2 == 1:
                b.add_person(person)
            else:
                a.add_person(person)
    log.info("... done")
    return a, b


def read_people(csv_filename: str, plaintext: bool = True) -> People:
    """
    Read a list of people from a CSV file.

    See :func:`read_people_2`, but this version doesn't offer the feature of
    splitting into two groups, and returns only a single :class:`People`
    object.
    """
    people, _ = read_people_2(csv_filename,
                              plaintext=plaintext,
                              alternate_groups=False)
    return people


# =============================================================================
# Validation
# =============================================================================

def make_deletion_data(people: People) -> People:
    """
    Makes a copy of the supplied data set with deliberate deletions applied.

    Surnames and DOBs are excepted as we require exact matches for those.
    """
    deletion_data = People()
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
    typo_data = People()
    for person in people.people:
        modified_person = person.copy()
        modified_person.debug_mutate_something(cfg)
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


def validate(cfg: MatchConfig,
             people_csv: str,
             cache_filename: str,
             output_csv: str,
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
        (
            in_plaintext, out_plaintext,
            in_hashed, out_hashed,
            in_deletions, out_deletions,
            in_deletions_hashed, out_deletions_hashed,
            in_typos, out_typos,
            in_typos_hashed, out_typos_hashed,
        ) = cache_load(cache_filename)
    except FileNotFoundError:
        in_plaintext, out_plaintext = read_people_2(
            people_csv, alternate_groups=True)
        log.info(f"Seeding random number generator with: {seed}")
        random.seed(seed)
        log.info("Making copies with deliberate deletions...")
        in_deletions = make_deletion_data(in_plaintext)
        out_deletions = make_deletion_data(out_plaintext)
        log.info("Making copies with deliberate typos...")
        in_typos = make_typo_data(in_plaintext, cfg)
        out_typos = make_typo_data(out_plaintext, cfg)

        log.info("Hashing...")
        in_hashed = in_plaintext.hashed(cfg)
        out_hashed = out_plaintext.hashed(cfg)
        in_deletions_hashed = in_deletions.hashed(cfg)
        out_deletions_hashed = out_deletions.hashed(cfg)
        in_typos_hashed = in_typos.hashed(cfg)
        out_typos_hashed = out_typos.hashed(cfg)
        log.info("... done")

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
        writer = csv.DictWriter(f, fieldnames=[
            "collection_name",
            "in_sample",
            "deletions",
            "typos",

            "is_hashed",
            "unique_id",
            "winner_id",
            "best_match_id",
            "best_log_odds",
            "next_best_log_odds",

            "correct_if_winner",
            "winner_advantage",
        ])
        writer.writeheader()
        i = 1  # row 1 is the header
        for people, collection_name, sample, in_sample, deletions, typos in data:  # noqa
            for person in people.people:
                i += 1
                if i % report_every == 0:
                    log.info(f"... creating CSV row {i}")
                (winner,
                 best_log_odds,
                 first_best_index,
                 next_best_log_odds) = sample.get_unique_match_detailed(
                    person, cfg, scan_everyone=True)
                if (next_best_log_odds is not None and
                        math.isfinite(next_best_log_odds)):
                    winner_advantage = best_log_odds - next_best_log_odds
                elif math.isfinite(best_log_odds):
                    winner_advantage = best_log_odds
                else:
                    winner_advantage = None
                best_match = (
                     people.people[first_best_index]
                     if first_best_index is not None else None
                )
                best_match_id = best_match.unique_id if best_match else None
                if best_match:
                    correct_if_winner = int(best_match_id ==
                                            person.unique_id)
                else:
                    correct_if_winner = None
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
                    unique_id=person.unique_id,
                    winner_id=winner.unique_id if winner else None,
                    best_match_id=best_match_id,
                    best_log_odds=best_log_odds,
                    next_best_log_odds=next_best_log_odds,

                    correct_if_winner=correct_if_winner,
                    winner_advantage=winner_advantage,
                )
                writer.writerow(rowdata)
    log.info("... done")


# =============================================================================
# Hash plaintext to encrypted CSV
# =============================================================================

def hash_identity_file(cfg: MatchConfig,
                       input_csv: str,
                       output_csv: str,
                       include_unique_id: bool = False) -> None:
    """
    Hash a file of identifiable people to a hashed version.

    Args:
        cfg:
            the master :class:`MatchConfig` object
        input_csv:
            input (plaintext) CSV filename to read
        output_csv:
            output (hashed) CSV filename to write
        include_unique_id:
            include the (potentially identifying) ``unique_id`` data? Usually
            ``False``; may be ``True`` for validation.
    """
    if include_unique_id:
        log.warning("include_unique_id is set -- use this for validation only")
    with open(input_csv, "rt") as infile, open(output_csv, "wt") as outfile:
        reader = csv.DictReader(infile)
        writer = csv.DictWriter(outfile, fieldnames=Person.HASHED_ATTRS)
        writer.writeheader()
        for inputrow in reader:
            plaintext_person = Person.from_plaintext_csv(inputrow)
            hashed_person = plaintext_person.hashed(cfg)
            writer.writerow(hashed_person.hashed_csv_dict(
                include_unique_id=include_unique_id))


# =============================================================================
# Main comparisons
# =============================================================================

def compare_probands_to_sample(cfg: MatchConfig,
                               probands: People,
                               sample: People,
                               output_csv: str,
                               report_every: int = 100) -> None:
    """
    Compares each proband to the sample. Writes to an output file.

    Args:
        cfg: the master :class:`MatchConfig` object.
        probands: :class:`People`
        sample: :class:`People`
        output_csv: output CSV filename
        report_every: report progress every n probands
    """
    log.info("Comparing each proband to sample")
    with open(output_csv, "wt") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "proband_unique_id",
            "proband_research_id",
            "matched",
            "log_odds_match",
            "p_match",
            "log_p_match",
            "sample_match_unique_id",
            "sample_match_research_id",
            "next_best_log_odds",
        ])
        writer.writeheader()
        for rownum, proband in enumerate(probands.people, start=1):
            if rownum % report_every == 0:
                log.info(f"Processing proband row {rownum}")
            match, log_odds, _, next_best_log_odds = \
                sample.get_unique_match_detailed(proband, cfg)
            rowdata = dict(
                proband_unique_id=proband.unique_id,
                proband_research_id=proband.research_id,
                matched=int(bool(match)),
                log_odds_match=log_odds,
                p_match=probability_from_log_odds(log_odds),
                log_p_match=log_probability_from_log_odds(log_odds),
                sample_match_unique_id=match.unique_id if match else None,
                sample_match_research_id=match.research_id if match else None,
                next_best_log_odds=next_best_log_odds,
            )
            writer.writerow(rowdata)
    log.info("... comparisons done.")


def compare_probands_to_sample_from_csv(
        cfg: MatchConfig,
        probands_csv: str,
        sample_csv: str,
        output_csv: str,
        probands_plaintext: bool = True,
        sample_plaintext: bool = True,
        sample_cache_filename: str = "") -> None:
    """
    Compares each of the people in the probands file to the sample file.

    Args:
        cfg: the master :class:`MatchConfig` object.
        probands_csv: CSV of people (probands); see :func:`read_people`.
        sample_csv: CSV of people (sample); see :func:`read_people`.
        output_csv: output CSV filename
        sample_cache_filename: file in which to cache sample, for speed
        probands_plaintext: is the probands file plaintext (not hashed)?
        sample_plaintext: is the sample file plaintext (not hashed)?
    """
    # Sample
    log.info("Loading (or caching) sample data")
    if sample_plaintext:
        assert sample_cache_filename
        try:
            (sample, ) = cache_load(sample_cache_filename)
        except FileNotFoundError:
            sample = read_people(sample_csv)
            cache_save(sample_cache_filename, [sample])
    else:
        sample = read_people(sample_csv, plaintext=False)

    # Probands
    log.info("Loading proband data")
    probands = read_people(probands_csv, plaintext=probands_plaintext)

    # Ensure they are comparable
    if sample_plaintext and not probands_plaintext:
        log.info("Hashing sample...")
        sample = sample.hashed(cfg)
        log.info("... done")
    elif probands_plaintext and not sample_plaintext:
        log.warning("Odd: comparing plaintext probands to hashed sample!")
        log.info("Hashing probands...")
        probands = probands.hashed(cfg)
        log.info("... done")

    # Compare
    compare_probands_to_sample(
        cfg=cfg,
        probands=probands,
        sample=sample,
        output_csv=output_csv
    )


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
        "~/dev/onspd/Data/ONSPD_MAY_2016_UK.csv"))
    appname = "crate"
    default_cache_dir = os.path.join(appdirs.user_data_dir(appname=appname))

    # -------------------------------------------------------------------------
    # Argument parser
    # -------------------------------------------------------------------------

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
        "--rounding_sf", type=int, default=3,
        help="Number of significant figures to use when rounding frequencies "
             "in hashed version"
    )

    priors_group = parser.add_argument_group(
        "frequency information for prior probabilities")
    priors_group.add_argument(
        "--forename_freq_csv", type=str,
        default=os.path.join(default_names_dir, "us_forename_freq.csv"),
        help='CSV file of "name, frequency" pairs for forenames'
    )
    priors_group.add_argument(
        "--forename_cache_filename", type=str,
        default=os.path.join(default_cache_dir, "fuzzy_forename_cache.pickle"),
        help="File in which to store cached forename info (to speed loading)"
    )
    priors_group.add_argument(
        "--surname_freq_csv", type=str,
        default=os.path.join(default_names_dir, "us_surname_freq.csv"),
        help='CSV file of "name, frequency" pairs for forenames'
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

    match_rule_group = parser.add_argument_group("matching rules")
    default_min_p_for_match = 0.999
    default_log_odds_for_match = log_odds_from_probability(default_min_p_for_match)  # noqa
    match_rule_group.add_argument(
        "--min_log_odds_for_match", type=float,
        default=default_log_odds_for_match,
        help=f"Minimum probability of two people being the same, before a "
             f"match will be considered. (Default is equivalent to "
             f"p = {default_min_p_for_match}.)"
    )
    match_rule_group.add_argument(
        "--exceeds_next_best_log_odds", type=float, default=10,
        help="Minimum log odds by which a best match must exceed the next-best "
             "match to be considered a unique match."
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
        help="Run self-tests and stop"
    )

    # -------------------------------------------------------------------------
    # speedtest command
    # -------------------------------------------------------------------------

    subparsers.add_parser(
        "speedtest",
        help="Run speed tests and stop"
    )

    # -------------------------------------------------------------------------
    # validate1 command
    # -------------------------------------------------------------------------

    validate1_parser = subparsers.add_parser(
        "validate1",
        help="Run validation test 1 and stop. In this test, a list of people "
             "is compared to a version of itself, at times with elements "
             "deleted or with typos introduced."
    )
    validate1_parser.add_argument(
        "--people_csv", type=str,
        default=os.path.join(default_names_dir, "fuzzy_validation1_people.csv"),
        help="CSV filename for validation 1 data. " +
             Person.PLAINTEXT_CSV_FORMAT_HELP
    )
    validate1_parser.add_argument(
        "--people_cache_filename", type=str,
        default=os.path.join(default_cache_dir,
                             "fuzzy_validation1_people_cache.pickle"),
        help="File in which to store cached people info (to speed loading)"
    )
    validate1_parser.add_argument(
        "--output_csv", type=str,
        default=os.path.join(default_names_dir,
                             "fuzzy_validation1_output.csv"),
        help="Output CSV file for validation"
    )
    validate1_parser.add_argument(
        "--seed", type=int, default=1234,
        help="Random number seed, for introducing deliberate errors in "
             "validation test 1"
    )

    # -------------------------------------------------------------------------
    # hash command
    # -------------------------------------------------------------------------

    hash_parser = subparsers.add_parser(
        "hash",
        help="Hash an identifiable CSV file into an encrypted one."
    )
    hash_parser.add_argument(
        "--input", type=str,
        default=os.path.join(default_names_dir, "fuzzy_probands.csv"),
        help="CSV filename for input (plaintext) data. " +
             Person.PLAINTEXT_CSV_FORMAT_HELP
    )
    hash_parser.add_argument(
        "--output", type=str,
        default=os.path.join(default_names_dir, "fuzzy_probands_hashed.csv"),
        help="Output CSV file for hashed version. "
    )
    hash_parser.add_argument(
        "--include_unique_id", action="store_true",
        help="Include the (potentially identifying) 'unique_id' data? "
             "Usually False; may be set to True for validation."
    )

    # -------------------------------------------------------------------------
    # compare_plaintext command
    # -------------------------------------------------------------------------

    compare_plaintext_parser = subparsers.add_parser(
        "compare_plaintext",
        help="Compare a list of probands against a sample (both in plaintext)."
    )
    compare_plaintext_parser.add_argument(
        "--probands", type=str,
        default=os.path.join(default_names_dir, "fuzzy_probands.csv"),
        help="CSV filename for probands data. " +
             Person.PLAINTEXT_CSV_FORMAT_HELP
    )
    compare_plaintext_parser.add_argument(
        "--sample", type=str,
        default=os.path.join(default_names_dir, "fuzzy_sample.csv"),
        help="CSV filename for sample data. " +
             Person.PLAINTEXT_CSV_FORMAT_HELP
    )
    compare_plaintext_parser.add_argument(
        "--sample_cache", type=str,
        default=os.path.join(default_cache_dir, "fuzzy_sample_cache.pickle"),
        help="File in which to store cached sample info (to speed loading)"
    )
    compare_plaintext_parser.add_argument(
        "--output", type=str,
        default=os.path.join(default_names_dir, "fuzzy_output_p2p.csv"),
        help="Output CSV file for proband/sample comparison"
    )

    # -------------------------------------------------------------------------
    # compare_hashed_to_hashed command
    # -------------------------------------------------------------------------

    compare_h2h_parser = subparsers.add_parser(
        "compare_hashed_to_hashed",
        help="Compare a list of probands against a sample (both hashed)."
    )
    compare_h2h_parser.add_argument(
        "--probands", type=str,
        default=os.path.join(default_names_dir, "fuzzy_probands_hashed.csv"),
        help="CSV filename for probands data. " +
             Person.HASHED_CSV_FORMAT_HELP
    )
    compare_h2h_parser.add_argument(
        "--sample", type=str,
        default=os.path.join(default_names_dir, "fuzzy_sample_hashed.csv"),
        help="CSV filename for sample data. " +
             Person.HASHED_CSV_FORMAT_HELP
    )
    compare_h2h_parser.add_argument(
        "--output", type=str,
        default=os.path.join(default_names_dir, "fuzzy_output_h2h.csv"),
        help="Output CSV file for proband/sample comparison"
    )

    # -------------------------------------------------------------------------
    # compare_hashed_to_plaintext command
    # -------------------------------------------------------------------------

    compare_h2p_parser = subparsers.add_parser(
        "compare_hashed_to_plaintext",
        help="Compare a list of probands (hashed) against a sample "
             "(plaintext)."
    )
    compare_h2p_parser.add_argument(
        "--probands", type=str,
        default=os.path.join(default_names_dir, "fuzzy_probands_hashed.csv"),
        help="CSV filename for probands data. " +
             Person.HASHED_CSV_FORMAT_HELP
    )
    compare_h2p_parser.add_argument(
        "--sample", type=str,
        default=os.path.join(default_names_dir, "fuzzy_sample.csv"),
        help="CSV filename for sample data. " +
             Person.PLAINTEXT_CSV_FORMAT_HELP
    )
    compare_h2p_parser.add_argument(
        "--sample_cache", type=str,
        default=os.path.join(default_cache_dir, "fuzzy_sample_cache.pickle"),
        help="File in which to store cached sample info (to speed loading)"
    )
    compare_h2p_parser.add_argument(
        "--output", type=str,
        default=os.path.join(default_names_dir, "fuzzy_output_h2p.csv"),
        help="Output CSV file for proband/sample comparison"
    )

    # -------------------------------------------------------------------------
    # Parse arguments and set up
    # -------------------------------------------------------------------------

    args = parser.parse_args()
    main_only_quicksetup_rootlogger(
        level=logging.DEBUG if args.verbose else logging.INFO)
    log.debug(f"Ensuring default cache directory exists: {default_cache_dir}")
    os.makedirs(default_cache_dir, exist_ok=True)

    p_middle_name_n_present = [
        float(x) for x in args.p_middle_name_n_present.split(",")]
    min_p_for_match = probability_from_log_odds(args.min_log_odds_for_match)

    log.debug(f"Using population size: {args.population_size}")
    log.debug(f"Using min_log_odds_for_match: {args.min_log_odds_for_match} "
              f"(p = {min_p_for_match})")
    cfg = MatchConfig(
        hasher_key=args.key,
        rounding_sf=args.rounding_sf,
        forename_csv_filename=args.forename_freq_csv,
        forename_cache_filename=args.forename_cache_filename,
        surname_csv_filename=args.surname_freq_csv,
        surname_cache_filename=args.surname_cache_filename,
        min_name_frequency=args.name_min_frequency,
        p_middle_name_n_present=p_middle_name_n_present,
        population_size=args.population_size,
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
    )

    def warn_if_default_key() -> None:
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
        selftest(cfg, speedtest=True)

    elif args.command == "validate1":
        log.info("Running validation test 1.")
        validate(
            cfg,
            people_csv=args.people_csv,
            cache_filename=args.people_cache_filename,
            output_csv=args.output_csv,
            seed=args.seed,
        )
        log.warning("Validation test 1 complete.")

    elif args.command == "hash":
        warn_if_default_key()
        log.info(f"Hashing identity file: {args.input}")
        hash_identity_file(cfg=cfg,
                           input_csv=args.input,
                           output_csv=args.output,
                           include_unique_id=args.include_unique_id)
        log.info(f"... finished; written to {args.output}")

    elif args.command == "compare_plaintext":
        log.info(f"Comparing files:\n"
                 f"- plaintext probands: {args.probands}\n"
                 f"- plaintext sample: {args.sample}")
        compare_probands_to_sample_from_csv(
            cfg=cfg,
            probands_csv=args.probands,
            sample_csv=args.sample,
            output_csv=args.output,
            probands_plaintext=True,
            sample_plaintext=True,
            sample_cache_filename=args.sample_cache,
        )
        log.info(f"... comparison finished; results are in {args.output}")

    elif args.command == "compare_hashed_to_hashed":
        log.info(f"Comparing files:\n"
                 f"- hashed probands: {args.probands}\n"
                 f"- hashed sample: {args.sample}")
        compare_probands_to_sample_from_csv(
            cfg=cfg,
            probands_csv=args.probands,
            sample_csv=args.sample,
            output_csv=args.output,
            probands_plaintext=False,
            sample_plaintext=False,
        )
        log.info(f"... comparison finished; results are in {args.output}")

    elif args.command == "compare_hashed_to_plaintext":
        warn_if_default_key()
        log.info(f"Comparing files:\n"
                 f"- hashed probands: {args.probands}\n"
                 f"- plaintext sample: {args.sample}")
        compare_probands_to_sample_from_csv(
            cfg=cfg,
            probands_csv=args.probands,
            sample_csv=args.sample,
            output_csv=args.output,
            probands_plaintext=False,
            sample_plaintext=True,
            sample_cache_filename=args.sample_cache,
        )
        log.info(f"... comparison finished; results are in {args.output}")

    else:
        # Shouldn't get here.
        log.error(f"Unknown command: {args.command}")
        sys.exit(EXIT_FAILURE)


if __name__ == "__main__":
    main()
    sys.exit(EXIT_SUCCESS)
