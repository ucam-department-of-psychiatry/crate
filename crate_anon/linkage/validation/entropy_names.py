#!/usr/bin/env python

"""
crate_anon/linkage/validation/entropy_names.py

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

**Measure entropy and entropy reduction among names.**

See also:

- https://www.lesswrong.com/posts/SEZqJcSm25XpQMhzr/information-theory-and-the-symmetry-of-updating-beliefs
  denoted [Academian2010].

Summarized:

Probabilistic evidence, pev()
-----------------------------

.. code-block:: none

    pev(A, B) = P(A and B) / [P(A) * P(B)]              [1] [Academian2010]

              = pev(B, A)

Stating Bayes theorem in those terms:

.. code-block:: none

    P(A and B) = P(A) * P(B | A) = P(B) * P(A | B)      [2] Bayes, symmetrical

    P(A | B) = P(A) * P(B | A) / P(B)                   [3] Bayes, conventional

but, from [1] and [2], since

.. code-block:: none

    pev(A, B) = P(B) * P(A | B) / [P(A) * P(B)]         RNC derivation
              = P(A | B) / P(A)
              = P(A) * P(B | A) / [P(A) * P(B)]
              = P(B | A) / P(B)

we reach this version of Bayes' theorem:

.. code-block:: none

    P(A | B) = P(A) * pev(A, B)                         [4a] [Academian2010]
    P(B | A) = P(B) * pev(A, B)                         [4b] [Academian2010]

Probabilistic evidence, being the ratio of two probabilities, has range [0,
+∞]. It is a multiplicative measure of mutual evidence: 1 if A and B are
independent; >1 if they make each other more likely; <1 if they make each other
less likely.


Information value, inf()
------------------------

The information value of an event (a.k.a. surprisal, self-information):

.. code-block:: none

    inf(A) = log_base_half[P(A)] = -log2[P(A)]          [5] [Academian2010]

Range check: p(A) ∈ [0, 1], so inf(A) ∈ [0, +∞]; impossibility (p = 0) gives
inf(A) = +∞, while certainty (p = 1) gives inf(A) = 0; p = 0.5 corresponds to
inf(A) = 1.

This is also "uncertainty" (how many independent bits are required to confirm
that A is true) or "informativity" (how many independent bits are gained if we
are told that A is true).


Informational evidence, iev()
-----------------------------

Redundancy, or mutual information, or informational evidence:

.. code-block:: none

    iev(A, B) = log2[pev(A, B)]                        [6] [Academian2010]

                NOTE the error in the original (twice, in equation and
                preceding paragraph); it cannot be -log2[pev(A, B)], as pointed
                out in the comments, and rechecked here.

              = log2{ P(A and B)  / [P(A)      * P(B)] }            from [1]
              = log2[P(A and B)]  - log2[P(A)] - log2[P(B)]
              = -inf(A and B)     + inf(A)     + inf(B)

              = inf(A) + inf(B) - inf(A and B)          [7] [Academian2010]

              = iev(B, A)

Range check: pev ∈ [0, +∞], so iev ∈ [-∞, +∞].

If iev(A, B) is positive, the uncertainty of A decreases upon observing B
(meaning A becomes more likely). If it is negative, the uncertainty of A
increases (A becomes less likely). A value of -∞ means A and B completely
contradict each other, and +∞ means they completely confirm each other.


Conditional information value
-----------------------------

.. code-block:: none

    inf(A | B) = -log2[P(A | B)]                                [8], from [5]
    
               = -log2{ P(A)   * pev(A, B) }                        from [4a]
               = -{ log2[P(A)] + log2[pev(A, B)] }
               = -log2[P(A)]   - log2[pev(A, B)]
               = inf(A)        - iev(A, B)                          from [5, 6]
               = inf(A)        - [inf(A) + inf(B) - inf(A and B)]   from [7]
               = inf(A)        -  inf(A) - inf(B) + inf(A and B)
               =                         - inf(B) + inf(A and B)

               = inf(A and B) - inf(B)                  [9] [Academian2010]


Information-theoretic Bayes' theorem
------------------------------------

Taking logs of [4a],

.. code-block:: none

    log2[P(A | B)] = log2[P(A)] + log2[pev(A, B)]

so

.. code-block:: none

    -log2[P(A | B)] = -log2[P(A)] - log2[pev(A, B)]

we obtain, from [8], [5], and [6] respectively,

.. code-block:: none

    inf(A | B) = inf(A) - iev(A, B)                     [10] [Academian2010]

or: Bayesian updating is subtracting *mutual evidence* from *uncertainty*.


A worked example
----------------

.. code-block:: bash

    ./entropy_names.py demo_info_theory_bayes_cancer


Other references
----------------

- Bayes theorem:
  https://en.wikipedia.org/wiki/Bayes%27_theorem
  ... ultimately Bayes (1763).

- A probability mass function for a discrete random variable X, which can take
  multiple states each labelled x: p_X(x) = P(X = x).
  https://en.wikipedia.org/wiki/Probability_mass_function

- Information content, self-information, surprisal, Shannon information, inf():
  https://en.wikipedia.org/wiki/Information_content
  ... ultimately e.g. Shannon (1948), Shannon & Weaver (1949).
  For a single event, usually expressed as I(x) = -log[P(x)].
  For a random variable, usually expressed as I_X(x) = -log[p_X(x)].

- Entropy is the expected information content (surprisal) of measurement of X:
  https://en.wikipedia.org/wiki/Entropy_(information_theory)
  Usually written H(X) = E[I(X)] = E[-log(P(X))],
  or (with the minus sign outside): H(X) = -sum_i[P(x_i) * log(P(x_i))],
  i.e. the sum of information for each value, weighted by the probability of
  that value.

- Mutual information (compare "informational evidence" above):
  https://en.wikipedia.org/wiki/Mutual_information
  Typically:

  .. code-block:: none

      I(X; Y) = I(Y; X)                             # symmetric
              = H(X) - H(X | Y)
              = H(Y) - H(Y | X)
              = H(X) + H(Y) - H(X, Y)               # cf. eq. [7]?
              = H(X, Y) - H(X | Y) - H(Y | X)
      I(X; Y) >= 0                                  # non-negative

  where

  - H(X) and H(Y) are marginal entropies,
  - H(X | Y) and H(Y | X) are conditional entropies,
  - H(X, Y) is the joint entropy.

  However, this is not the same quantity; I(X; Y) >= 0 whereas iev ∈ [-∞, +∞].
  This (Wikipedia) is the mutual information of two random variables: the
  amount of information you can observe about one random variable by observing
  the other. The "iev" concept above is about pairs of individual events.

  For two discrete RVs,
  
    I(X; Y) = sum_y{ sum_x{ P_XY(x, y) log[ P_XY(x, y) / (P_X(x) * P_Y(y)) ] }} 

- Mutual information is a consideration across events. The individual-event
  version is "pointwise mutual information", 
  https://en.wikipedia.org/wiki/Pointwise_mutual_information, which is
  
  .. code-block:: none
  
    pmi(x; y) = log[ P(x, y) / (P(x) * P(y) ]
              = log[ P(x | y) / P(x) ]
              = log[ P(y | x) / P(y) ]


Applying to our problem of selecting a good partial representation
------------------------------------------------------------------

Assume we are comparing a proband and a candidate and there is not a full
match. We start with some sort of prior, P(H | information so far); for now,
we'll simplify that to P(H). We want P(H | D) where D is the new information
from the partial identifier -- the options being a partial match, or no match.
We generally use this form of Bayes' theorem:

.. code-block:: none

    ln(posterior odds)       = ln(prior odds)   + ln(likelihood ratio)
    ln[P(H | D) / P(¬H | D)] = ln[P(H) / P(¬H)] + ln[P(D | H) / P(D | ¬H)]

Converting to log2 just involves multiplying by a constant, of course:

.. code-block:: none

    ln(x)   = log2(x) * ln(2) 
    log2(x) = ln(x) * log2(e)

A partial match would provide a log likelihood of

.. code-block:: none

    log(p_ep) − log(p_pnf)

and no match would provide a log likelihood of

.. code-block:: none

    log(p_en) − log(p_n)

We could weight that (or the information equivalent) by the probability of
obtaining a partial match (given no full match) and of obtaining no match
(given no full match) respectively.

... let's skip this and try mutual information.


Note
----

Code largely abandoned; not re-checked since NameFrequencyInfo was refactored,
since this code had served it purpose.

"""  # noqa


# =============================================================================
# Imports
# =============================================================================

import argparse
from collections import defaultdict
from dataclasses import dataclass
import logging
from typing import Dict, Generator, Iterable, List, Tuple

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from cardinal_pythonlib.probability import bayes_posterior
from numba import jit
from numpy import log2, power
from rich_argparse import ArgumentDefaultsRichHelpFormatter

from crate_anon.linkage.constants import GENDER_FEMALE, GENDER_MALE
from crate_anon.linkage.frequencies import NameFrequencyInfo
from crate_anon.linkage.matchconfig import MatchConfig

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

ACCURATE_MIN_NAME_FREQ = 1e-10
FLOAT_TOLERANCE = 1e-10


# =============================================================================
# Information theory calculations
# =============================================================================


@jit(nopython=True)
def p_log2p(p: float) -> float:
    """
    Given p, calculate p * log_2(p).
    """
    return p * log2(p)


def entropy(frequencies: Iterable[float]) -> float:
    """
    Returns the (information/Shannon) entropy of the probability distribution
    supplied, in bits. By definition,

        H = -sum_i[ p_i * log_2(p_i) ]

    https://en.wikipedia.org/wiki/Quantities_of_information
    """
    return -sum(p_log2p(p) for p in frequencies)


@jit(nopython=True)
def p_log2_p_over_q(p: float, q: float) -> float:
    """
    Given p and q, calculate p * log_2(p / q), except return 0 if p == 0.
    Used for KL divergence.
    """
    if p == 0:
        return 0
    return p * log2(p / q)


def relative_entropy_kl_divergence(
    pairs: Iterable[Tuple[float, float]]
) -> float:
    """
    Returns the relative entropy, or Kullback-Leibler divergence, D_KL(P || Q),
    in bits; https://en.wikipedia.org/wiki/Kullback%E2%80%93Leibler_divergence.

    The iterable should contain pairs P(x), Q(x) for all values of x in the
    distribution. We calculate

        D_KL(P || Q) = sum_x{ P(x) * log[P(x) / Q(x)] }
    """
    kl = sum(p_log2_p_over_q(p, q) for p, q in pairs)
    assert kl >= 0, "Bug: K-L divergence must be >=0"
    return kl


@jit(nopython=True)
def inf_bits_from_p(p: float) -> float:
    """
    The information value (surprisal, self-information) of an event from its
    probability, p; see equation [5] above.
    """  # noqa
    return -log2(p)


@jit(nopython=True)
def p_from_inf(inf_bits: float) -> float:
    """
    The information value (surprisal, self-information) of an event from its
    probability, p; see equation [5] above.
    """  # noqa
    return power(2, -inf_bits)


# =============================================================================
# Gender-weighted version of a frequency dictionary
# =============================================================================


def gen_gender_weighted_frequencies(
    freqdict: Dict[Tuple[str, str], float], p_female: float
) -> Generator[float, None, None]:
    """
    Generates gender-weighted frequencies. Requires p_female + p_male = 1.
    """
    p_male = 1 - p_female
    for (name, gender), p in freqdict.items():
        if gender == GENDER_FEMALE:
            yield p * p_female
        elif gender == GENDER_MALE:
            yield p * p_male
        else:
            raise ValueError("bad gender in frequency info")


def get_frequencies(
    nf: NameFrequencyInfo,
    p_female: float = None,
    metaphones: bool = False,
    first_two_char: bool = False,
) -> List[float]:
    """
    Returns raw frequencies for a category of identifier, optionally combining
    (weighting by gender) for those stored separately by gender.
    """
    assert not (metaphones and first_two_char)
    if nf.by_gender:
        assert p_female is not None
    if metaphones:
        return [i.p_metaphone for i in gen_name_frequency_tuples(nf, p_female)]
    elif first_two_char:
        return [i.p_f2c for i in gen_name_frequency_tuples(nf, p_female)]
    else:
        return [i.p_name for i in gen_name_frequency_tuples(nf, p_female)]


@dataclass
class ValidationNameFreqInfo:
    """
    Used for validation calculations.
    """

    name: str
    p_name: float
    metaphone: str
    p_metaphone: float
    f2c: str
    p_f2c: float


def gen_name_frequency_tuples(
    nf: NameFrequencyInfo,
    p_female: float = None,
) -> Generator[ValidationNameFreqInfo, None, None]:
    """
    Generates frequency tuples (name, p_name, metaphone, p_metaphone, f2c,
    p_firsttwochar).
    """
    by_gender = nf.by_gender
    if by_gender:
        assert p_female is not None
        p_male = 1 - p_female
    else:
        p_male = None
    for info in nf.infolist:
        if by_gender:
            if info.gender == GENDER_FEMALE:
                multiple = p_female
            elif info.gender == GENDER_MALE:
                multiple = p_male
            else:
                raise ValueError("bad gender")
        else:
            multiple = 1
        yield ValidationNameFreqInfo(
            name=info.name,
            p_name=multiple * info.p_name,
            metaphone=info.metaphone,
            p_metaphone=multiple * info.p_metaphone,
            f2c=info.f2c,
            p_f2c=multiple * info.p_f2c,
        )


# =============================================================================
# Demonstration of the information-based version of Bayes' theorem
# =============================================================================


def demo_info_theory_bayes_cancer() -> None:
    """
    From the comments in [Academian2010]:

    1% of women at age forty who participate in routine screening have breast
    cancer. 80% of women with breast cancer will get positive mammographies.
    9.6% of women without breast cancer will also get positive mammographies. A
    woman in this age group had a positive mammography in a routine screening.
    What is the probability that she actually has breast cancer?
    """
    # Problem
    p_cancer = 0.01
    p_pos_given_cancer = 0.8
    p_pos_given_no_cancer = 0.096
    print(demo_info_theory_bayes_cancer.__doc__)
    print(
        f"p(cancer) = {p_cancer}, p(pos | cancer) = {p_pos_given_cancer}, "
        f"p(pos | ¬cancer) = {p_pos_given_no_cancer}"
    )
    # Goal: calculate p_cancer_given_pos

    # Derived
    p_no_cancer = 1 - p_cancer
    p_pos_and_cancer = p_cancer * p_pos_given_cancer
    p_pos_and_no_cancer = p_no_cancer * p_pos_given_no_cancer
    p_pos = p_pos_and_cancer + p_pos_and_no_cancer

    # Conventional Bayes:
    p_cancer_given_pos_std = bayes_posterior(
        prior=p_cancer,
        likelihood=p_pos_given_cancer,
        marginal_likelihood=p_pos,
    )
    print(f"(plain Bayes)    p(cancer | pos) = {p_cancer_given_pos_std}")

    # Either info theory version:
    inf_pos = inf_bits_from_p(p_pos)
    inf_pos_and_cancer = inf_bits_from_p(p_pos_and_cancer)

    # Version 1:
    inf_cancer_given_pos_v1 = inf_pos_and_cancer - inf_pos  # eq. [9]
    p_cancer_given_pos_v1 = p_from_inf(inf_cancer_given_pos_v1)
    print(f"(info theory v1) p(cancer | pos) = {p_cancer_given_pos_v1}")

    # Version 2:
    inf_cancer = inf_bits_from_p(p_cancer)
    iev_pos_cancer = inf_pos + inf_cancer - inf_pos_and_cancer
    inf_cancer_given_pos_v2 = inf_cancer - iev_pos_cancer  # eq. [10]
    p_cancer_given_pos_v2 = p_from_inf(inf_cancer_given_pos_v2)
    print(f"(info theory v2) p(cancer | pos) = {p_cancer_given_pos_v2}")

    # Same answer, within rounding error:
    assert abs(p_cancer_given_pos_v1 - p_cancer_given_pos_v2) < FLOAT_TOLERANCE


# =============================================================================
# Mutual information examples
# =============================================================================


def mutual_info(
    iterable_xy_x_y: Iterable[Tuple[float, float, float]],
    verbose: bool = False,
) -> float:
    """
    See https://en.wikipedia.org/wiki/Mutual_information: mutual information of
    two jointly discrete random variables X and Y. The expectation from the
    iterable is that for all x ∈ X and y ∈ Y, the iterable delivers the tuple
    P_X_Y(x, y), P_X(x), P_Y(y). Uses log2 and therefore the units are bits.
    """
    # Verbose version:
    if verbose:
        mutual_info_bits = 0.0
        for i, (p_xy, p_x, p_y) in enumerate(iterable_xy_x_y):
            bits = p_xy * log2(p_xy / (p_x * p_y))
            if i % 10000 == 0:
                log.info(
                    f"p_xy = {p_xy}, p_x = {p_x}, p_y = {p_y}, bits = {bits}"
                )
            mutual_info_bits += bits
        return mutual_info_bits

    # Terse version:
    return sum(
        p_xy * log2(p_xy / (p_x * p_y)) for p_xy, p_x, p_y in iterable_xy_x_y
    )


def gen_mutual_info_name_probabilities(
    nf: NameFrequencyInfo,
    p_female: float = None,
    name_metaphone: bool = False,
    name_firsttwochar: bool = False,
    metaphone_firsttwochar: bool = False,
) -> Generator[Tuple[float, float, float], None, None]:
    """
    Generates mutual information probabilities for name/fuzzy name comparisons.
    """
    assert (
        sum([name_metaphone, name_firsttwochar, metaphone_firsttwochar]) == 1
    )
    for info in gen_name_frequency_tuples(
        nf=nf,
        p_female=p_female,
    ):
        if name_metaphone:
            # Names are mapped many-to-one to metaphones. Therefore, P(name_x ∧
            # metaphone_for_name_x) = P(name_x). However,
            # P(metaphone_for_name_x) ≥ P(name_x).
            p_xy, p_x, p_y = info.p_name, info.p_name, info.p_metaphone
        elif name_firsttwochar:
            # Similarly for first-two-character representations.
            p_xy, p_x, p_y = info.p_name, info.p_name, info.p_f2c
        else:  # metaphone_firsttwochar
            # Here there is overlap. So we use p_name as the joint probability;
            # there may be some duplication but I think that is OK (they'll add
            # up).
            p_xy, p_x, p_y = info.p_name, info.p_metaphone, info.p_f2c
        yield p_xy, p_x, p_y


# =============================================================================
# Information theory summaries
# =============================================================================


def show_info_theory_calcs() -> None:
    """
    Show some information theory calculations.
    """
    # Special options:
    # - Get the probabilities right (very low minimum frequency).
    # - Load details of first-two-character fuzzy representations.
    cfg = MatchConfig(
        min_name_frequency=ACCURATE_MIN_NAME_FREQ,
    )

    # -------------------------------------------------------------------------
    # Surnames
    # -------------------------------------------------------------------------

    surname_p = get_frequencies(cfg.surname_freq_info)
    # Test: surname_p = [1/100000] * 100000
    log.info(f"Number of surnames: {len(surname_p)}")
    h_surnames = entropy(surname_p)
    log.info(f"Surname entropy: H = {h_surnames} bits")

    surname_metaphone_p = get_frequencies(
        cfg.surname_freq_info, metaphones=True
    )
    log.info(f"Number of surname metaphones: {len(surname_metaphone_p)}")
    h_surname_metaphones = entropy(surname_metaphone_p)
    log.info(f"Surname metaphone entropy: H = {h_surname_metaphones} bits")

    surname_f2c_p = get_frequencies(cfg.surname_freq_info, first_two_char=True)
    log.info(f"Number of surname first-two-chars: {len(surname_f2c_p)}")
    h_surname_f2c = entropy(surname_f2c_p)
    log.info(f"Surname first-two-char entropy: H = {h_surname_f2c} bits")

    # kl_name_metaphone = relative_entropy_kl_divergence(
    #     gen_name_pairs(cfg.surname_freq_info, metaphones=True)
    # )
    # log.info(
    #     f"Surname name/metaphone relative entropy: "
    #     f"D_KL = {kl_name_metaphone} bits"
    # )

    surname_name_meta_mi = mutual_info(
        gen_mutual_info_name_probabilities(
            nf=cfg.surname_freq_info, name_metaphone=True
        )
    )
    log.info(
        f"Surname: name/metaphone mutual information: "
        f"I = {surname_name_meta_mi} bits"
    )

    surname_name_f2c_mi = mutual_info(
        gen_mutual_info_name_probabilities(
            nf=cfg.surname_freq_info, name_firsttwochar=True
        )
    )
    log.info(
        f"Surname: name/first-two-char mutual information: "
        f"I = {surname_name_f2c_mi} bits"
    )

    surname_meta_f2c_mi = mutual_info(
        gen_mutual_info_name_probabilities(
            nf=cfg.surname_freq_info, metaphone_firsttwochar=True
        )
    )
    log.info(
        f"Surname: metaphone/first-two-char mutual information: "
        f"I = {surname_meta_f2c_mi} bits"
    )

    # -------------------------------------------------------------------------
    # Forenames
    # -------------------------------------------------------------------------

    p_female = cfg.p_female_given_m_or_f

    forename_p = get_frequencies(nf=cfg.forename_freq_info, p_female=p_female)
    log.info(
        f"Number of forenames (M/F versions count separately): "
        f"{len(forename_p)}"
    )
    h_forenames = entropy(forename_p)
    log.info(f"Forename entropy: H = {h_forenames} bits")

    forename_metaphone_p = get_frequencies(
        nf=cfg.forename_freq_info,
        p_female=p_female,
        metaphones=True,
    )
    log.info(
        f"Number of forename metaphones (M/F versions count separately): "
        f"{len(forename_metaphone_p)}"
    )
    h_forename_metaphones = entropy(forename_metaphone_p)
    log.info(f"Forename metaphone entropy: H = {h_forename_metaphones} bits")

    forename_f2c_p = get_frequencies(
        cfg.forename_freq_info,
        p_female=p_female,
        first_two_char=True,
    )
    log.info(
        f"Number of forename first-two-chars (M/F versions count separately): "
        f"{len(forename_f2c_p)}"
    )
    h_forename_f2c = entropy(forename_f2c_p)
    log.info(f"Forename first-two-char entropy: H = {h_forename_f2c} bits")

    forename_name_meta_mi = mutual_info(
        gen_mutual_info_name_probabilities(
            nf=cfg.forename_freq_info, p_female=p_female, name_metaphone=True
        )
    )
    log.info(
        f"Forename: name/metaphone mutual information: "
        f"I = {forename_name_meta_mi} bits"
    )

    forename_name_f2c_mi = mutual_info(
        gen_mutual_info_name_probabilities(
            nf=cfg.forename_freq_info,
            p_female=p_female,
            name_firsttwochar=True,
        )
    )
    log.info(
        f"Forename: name/first-two-char mutual information: "
        f"I = {forename_name_f2c_mi} bits"
    )

    forename_meta_f2c_mi = mutual_info(
        gen_mutual_info_name_probabilities(
            nf=cfg.forename_freq_info,
            p_female=p_female,
            metaphone_firsttwochar=True,
        )
    )
    log.info(
        f"Forename: metaphone/first-two-char mutual information: "
        f"I = {forename_meta_f2c_mi} bits"
    )


# =============================================================================
# Partial match frequencies
# =============================================================================


def partial_calcs(
    nf: NameFrequencyInfo,
    p_female: float = None,
    report_every: int = 10000,
    debug_stop: int = None,
) -> None:
    """
    Show e.g. p(match metaphone but not name). This has the potential to be
    really slow (e.g. 175k^2 = 3e10) though it should only need to be done once
    -- however, we can optimize beyond an n^2 comparison. Uses examples from
    the public US name databases.

    Maths is e.g.

    .. code-block:: none

        integral_over_a(integral_over_b(p_a * p_b * binary(conjunction event)))

    Examples:

    - Share metaphone, not first two characters (F2C) or name:

      .. code-block:: none

        AABERG [APRK, AA] / WIBBERG [APRK, WI]
        AABY [AP, AA] / ABAY [AP, AB]
        AAKRE [AKR, AA] / OKYERE [AKR, OK]

    - Share F2C, not metaphone or name:

      .. code-block:: none

        AALDERS [ALTR, AA] / AASEN [ASN, AA]
        (etc.; these are obvious)

    """

    # def debug_report(
    #     event: str, a_: ValidationNameFreqInfo, b_: ValidationNameFreqInfo
    # ) -> None:
    #     log.info(
    #         f"{event}: {a.name} [{a.metaphone}, {a.f2c}] / "
    #         f"{b.name} [{b.metaphone}, {b.f2c}]"
    #     )

    # We optimize thus:
    metaphone_to_infolist = defaultdict(
        list
    )  # type: Dict[str, List[ValidationNameFreqInfo]]
    f2c_to_infolist = defaultdict(
        list
    )  # type: Dict[str, List[ValidationNameFreqInfo]]
    for i in gen_name_frequency_tuples(nf, p_female):
        metaphone_to_infolist[i.metaphone].append(i)
        f2c_to_infolist[i.f2c].append(i)
    # This improved the performance for 10k names in A from about 1h7min to
    # about 4 seconds, so that was definitely worth it.

    total_p_a = 0.0  # for normalization, in case this is not 1
    # ... might differ from total_p_a only if we break via our debugging loop
    total_p_b = sum(
        info_.p_name for info_ in gen_name_frequency_tuples(nf, p_female)
    )
    # ... we always iterate through all of b for all a, even if debugging;
    # ... and even if we iterate through b implicitly (via the dictionaries).

    p_share_metaphone = 0.0
    p_share_metaphone_not_name = 0.0
    p_share_metaphone_not_f2c_or_name = 0.0
    p_share_f2c = 0.0
    p_share_f2c_not_name = 0.0
    p_share_f2c_not_metaphone_or_name = 0.0
    n = len(nf.infolist)
    for idx_a, a in enumerate(
        gen_name_frequency_tuples(nf, p_female), start=1
    ):
        if idx_a % report_every == 0:
            log.info(f"... processing name {idx_a} / {n}")
        if debug_stop and idx_a > debug_stop:
            break  # for debugging

        # For speed:
        a_p_name = a.p_name
        a_name = a.name
        a_metaphone = a.metaphone
        a_f2c = a.f2c

        total_p_a += a_p_name

        for b in f2c_to_infolist[a_f2c]:
            # Iterate only through names sharing first two characters.
            p_product = a_p_name * b.p_name
            p_share_f2c += p_product
            if a_name != b.name:
                p_share_f2c_not_name += p_product
                # debug_report("share_f2c_not_name", a, b)
                if a_metaphone != b.metaphone:
                    p_share_f2c_not_metaphone_or_name += p_product
                    # debug_report("share_f2c_not_metaphone_or_name", a, b)

        for b in metaphone_to_infolist[a_metaphone]:
            # Iterate only through names sharing metaphones.
            p_product = a_p_name * b.p_name
            p_share_metaphone += p_product
            if a_name != b.name:
                p_share_metaphone_not_name += p_product
                # debug_report("share_metaphone_not_name", a, b)
                if a_f2c != b.f2c:
                    p_share_metaphone_not_f2c_or_name += p_product
                    # debug_report("share_metaphone_not_f2c_or_name", a, b)

    # Normalized probabilities:
    nf = 1 / (total_p_a * total_p_b)  # normalizing factor
    np_share_metaphone = p_share_metaphone * nf
    np_share_metaphone_not_name = p_share_metaphone_not_name * nf
    np_share_metaphone_not_f2c_or_name = p_share_metaphone_not_f2c_or_name * nf
    np_share_f2c = p_share_f2c * nf
    np_share_f2c_not_name = p_share_f2c_not_name * nf
    np_share_f2c_not_metaphone_or_name = p_share_f2c_not_metaphone_or_name * nf

    log.info(
        f"Unnormalized: total_p_a = {total_p_a}, "
        f"total_p_b = {total_p_b}, "
        f"nf = {nf}, "
        f"p_share_metaphone = {p_share_metaphone}, "
        f"p_share_metaphone_not_name = {p_share_metaphone_not_name}, "
        f"p_share_metaphone_not_f2c_or_name = "
        f"{p_share_metaphone_not_f2c_or_name}, "
        f"p_share_f2c = {p_share_f2c}, "
        f"p_share_f2c_not_name = {p_share_f2c_not_name}, "
        f"p_share_f2c_not_metaphone_or_name = "
        f"{p_share_f2c_not_metaphone_or_name}"
    )
    log.info(
        f"Normalized: P(share metaphone) = {np_share_metaphone}, "
        f"P(share metaphone, not name) = {np_share_metaphone_not_name}, "
        f"P(share metaphone, not first two char or name) = "
        f"{np_share_metaphone_not_f2c_or_name}, "
        f"P(share first two char) = {np_share_f2c}, "
        f"P(share first two char, not name) = {np_share_f2c_not_name}, "
        f"P(share first two char, not metaphone or name) = "
        f"{np_share_f2c_not_metaphone_or_name}"
    )


def show_partial_match_frequencies() -> None:
    """
    Show population-level frequency/probability calculations from our name
    frequency databases, e.g. p(match metaphone but not name), p(match first
    two characters but not metaphone or name).
    """
    cfg = MatchConfig(
        min_name_frequency=ACCURATE_MIN_NAME_FREQ,
    )
    log.info("Partial match frequencies for surnames:")
    partial_calcs(cfg.surname_freq_info)
    log.info("Partial match frequencies for forenames:")
    partial_calcs(cfg.forename_freq_info, p_female=cfg.p_female_given_m_or_f)


_ = """

Saved results:

2022-06-26 14:40:35.939 __main__:INFO: Partial match frequencies for surnames:
2022-06-26 14:40:36.191 crate_anon.linkage.helpers:WARNING: No metaphone for 'HWA'
2022-06-26 14:40:36.191 crate_anon.linkage.helpers:WARNING: No metaphone for 'HWEE'
2022-06-26 14:40:36.192 crate_anon.linkage.helpers:WARNING: No metaphone for 'HWU'
2022-06-26 14:40:39.924 __main__:INFO: ... processing name 10000 / 175880
...
2022-06-26 14:41:39.135 __main__:INFO: ... processing name 170000 / 175880
2022-06-26 14:41:40.034 __main__:INFO: Unnormalized: total_p_a =
0.9555555960002395, total_p_b = 0.9555555960002395, nf = 1.0951864946351493,
p_share_metaphone = 0.011339587936127086, p_share_metaphone_not_name =
0.000768652112738086, p_share_metaphone_not_f2c_or_name =
0.0005779216890297886, p_share_f2c = 0.02015927698649681, p_share_f2c_not_name
= 0.009588341150670168, p_share_f2c_not_metaphone_or_name =
0.009397610726948866

2022-06-26 14:41:40.034 __main__:INFO: Normalized: P(share metaphone) =
0.01241896356237405, P(share metaphone, not name) = 0.000841817412943526,
P(share metaphone, not first two char or name) = 0.0006329320287821591, P(share
first two char) = 0.022078167897220478, P(share first two char, not name) =
0.010501021734168415, P(share first two char, not metaphone or name) =
0.010292136349992806

~~~

2022-06-26 14:41:40.054 __main__:INFO: Partial match frequencies for forenames:
2022-06-26 14:41:43.254 __main__:INFO: ... processing name 10000 / 106695
...
2022-06-26 14:42:13.711 __main__:INFO: ... processing name 100000 / 106695

2022-06-26 14:42:14.506 __main__:INFO: Unnormalized: total_p_a =
0.9999999999997667, total_p_b = 0.9999999999997667, nf = 1.0000000000004665,
p_share_metaphone = 0.005028025327852539, p_share_metaphone_not_name =
0.0025948399071387762, p_share_metaphone_not_f2c_or_name =
0.0014685292424996006, p_share_f2c = 0.018453783690030413, p_share_f2c_not_name
= 0.01602059826926657, p_share_f2c_not_metaphone_or_name = 0.014894287604555126

2022-06-26 14:42:14.506 __main__:INFO: Normalized: P(share metaphone) =
0.005028025327854884, P(share metaphone, not name) = 0.0025948399071399867,
P(share metaphone, not first two char or name) = 0.0014685292425002856, P(share
first two char) = 0.01845378369003902, P(share first two char, not name) =
0.016020598269274045, P(share first two char, not metaphone or name) =
0.014894287604562073


Note in particular that metaphone-sharing is rarer than F2C-sharing:

Surnames:

P(share metaphone)      = 0.01241896356237405
P(share first two char) = 0.022078167897220478

P(share metaphone, not name) =      0.000841817412943526
P(share first two char, not name) = 0.010501021734168415

P(share metaphone, not first two char or name) = 0.0006329320287821591
P(share first two char, not metaphone or name) = 0.010292136349992806

Forenames:

P(share metaphone)      = 0.005028025327854884
P(share first two char) = 0.01845378369003902

P(share metaphone, not name) =      0.0025948399071399867
P(share first two char, not name) = 0.016020598269274045

P(share metaphone, not first two char or name) = 0.0014685292425002856
P(share first two char, not metaphone or name) = 0.014894287604562073

"""  # noqa


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    """
    Command-line entry point.
    """
    function_map = {
        "infotheory": show_info_theory_calcs,
        "demobayes": demo_info_theory_bayes_cancer,
        "partials": show_partial_match_frequencies,
    }
    parser = argparse.ArgumentParser(
        formatter_class=ArgumentDefaultsRichHelpFormatter
    )
    parser.add_argument("command", choices=function_map.keys())
    args = parser.parse_args()
    main_only_quicksetup_rootlogger(level=logging.INFO)
    func = function_map[args.command]
    func()


if __name__ == "__main__":
    main()
