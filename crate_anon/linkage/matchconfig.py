#!/usr/bin/env python

r"""
crate_anon/linkage/matchconfig.py

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

"""

# =============================================================================
# Imports
# =============================================================================

import logging
from typing import Any, Dict, NoReturn, Optional, Set, Tuple, Union

from cardinal_pythonlib.hash import make_hasher
from cardinal_pythonlib.maths_py import round_sf, normal_round_int
from cardinal_pythonlib.probability import log_odds_from_1_in_n
from cardinal_pythonlib.reprfunc import auto_repr

from crate_anon.linkage.constants import (
    DAYS_PER_MONTH,
    DAYS_PER_YEAR,
    FuzzyDefaults,
    GENDER_FEMALE,
    GENDER_MALE,
    GENDER_MISSING,
    GENDER_OTHER,
    MONTHS_PER_YEAR,
    Switches,
    UK_POPULATION_2017,
    VALID_GENDERS,
)
from crate_anon.linkage.frequencies import (
    BasicNameFreqInfo,
    NameFrequencyInfo,
    PostcodeFrequencyInfo,
)
from crate_anon.linkage.helpers import (
    dict_from_str,
    safe_upper,
    standardize_name,
    standardize_perfect_id_key,
    standardize_perfect_id_value,
)

log = logging.getLogger(__name__)


# =============================================================================
# Main configuration class, supporting frequency-based probability calculations
# =============================================================================


class MatchConfig:
    """
    Master config class. It's more convenient to pass one of these round than
    lots of its components.

    Default arguments are there for testing.
    """

    def __init__(
        self,
        hash_key: str = FuzzyDefaults.HASH_KEY,
        hash_method: str = FuzzyDefaults.HASH_METHOD,
        rounding_sf: Optional[int] = FuzzyDefaults.ROUNDING_SF,
        local_id_hash_key: str = None,
        population_size: int = FuzzyDefaults.POPULATION_SIZE,
        forename_sex_csv_filename: str = FuzzyDefaults.FORENAME_SEX_FREQ_CSV,
        forename_cache_filename: str = FuzzyDefaults.FORENAME_CACHE_FILENAME,
        surname_csv_filename: str = FuzzyDefaults.SURNAME_FREQ_CSV,
        surname_cache_filename: str = FuzzyDefaults.SURNAME_CACHE_FILENAME,
        min_name_frequency: float = FuzzyDefaults.NAME_MIN_FREQ,
        accent_transliterations_csv: str = (
            FuzzyDefaults.ACCENT_TRANSLITERATIONS_SLASH_CSV
        ),
        nonspecific_name_components_csv: str = (
            FuzzyDefaults.NONSPECIFIC_NAME_COMPONENTS_CSV
        ),
        birth_year_pseudo_range: float = FuzzyDefaults.BIRTH_YEAR_PSEUDO_RANGE,
        p_not_male_or_female: float = FuzzyDefaults.P_NOT_MALE_OR_FEMALE,
        p_female_given_male_or_female: float = (
            FuzzyDefaults.P_FEMALE_GIVEN_MALE_OR_FEMALE
        ),
        postcode_csv_filename: str = FuzzyDefaults.POSTCODES_CSV,
        postcode_cache_filename: str = FuzzyDefaults.POSTCODE_CACHE_FILENAME,
        k_postcode: Optional[float] = FuzzyDefaults.K_POSTCODE,
        p_unknown_or_pseudo_postcode: float = (
            FuzzyDefaults.P_UNKNOWN_OR_PSEUDO_POSTCODE
        ),
        k_pseudopostcode: float = FuzzyDefaults.K_PSEUDOPOSTCODE,
        p_ep1_forename: str = FuzzyDefaults.P_EP1_FORENAME_CSV,
        p_ep2np1_forename: str = FuzzyDefaults.P_EP2NP1_FORENAME_CSV,
        p_u_forename: float = FuzzyDefaults.P_U_FORENAME,
        p_en_forename: str = FuzzyDefaults.P_EN_FORENAME_CSV,
        p_ep1_surname: str = FuzzyDefaults.P_EP1_SURNAME_CSV,
        p_ep2np1_surname: str = FuzzyDefaults.P_EP2NP1_SURNAME_CSV,
        p_en_surname: str = FuzzyDefaults.P_EN_SURNAME_CSV,
        p_ep_dob: float = FuzzyDefaults.P_EP_DOB,
        p_en_dob: float = FuzzyDefaults.P_EN_DOB,
        p_e_gender: float = FuzzyDefaults.P_E_GENDER,
        p_ep_postcode: float = FuzzyDefaults.P_EP_POSTCODE,
        p_en_postcode: float = FuzzyDefaults.P_EN_POSTCODE,
        min_log_odds_for_match: float = FuzzyDefaults.MIN_LOG_ODDS_FOR_MATCH,
        exceeds_next_best_log_odds: float = (
            FuzzyDefaults.EXCEEDS_NEXT_BEST_LOG_ODDS
        ),
        perfect_id_translation: Union[
            Dict[str, str], str
        ] = FuzzyDefaults.PERFECT_ID_TRANSLATION,
        extra_validation_output: bool = False,
        report_every: int = FuzzyDefaults.REPORT_EVERY,
        min_probands_for_parallel: int = (
            FuzzyDefaults.MIN_PROBANDS_FOR_PARALLEL
        ),
        n_workers: int = FuzzyDefaults.N_PROCESSES,
        verbose: bool = False,
    ) -> None:
        """
        Args:
            hash_key:
                Key (passphrase) for hasher.
            hash_method:
                Method to use for hashhing.
            rounding_sf:
                Number of significant figures to use when rounding frequency
                information in hashed copies. Use ``None`` for no rounding.
            local_id_hash_key:
                If specified, then for hash operations, the local_id values
                will also be hashed, using this key.

            population_size:
                The size of the entire population (not our sample). See
                docstrings above.

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
                Minimum name frequency; see command-line help.
            accent_transliterations_csv:
                Accent transliteration map. String of the form "Ä/AE,Ö/OE" --
                comma-separated pairs, with slashed separating each pair.
            nonspecific_name_components_csv:
                CSV-separated list of nonspecific name components (e.g.
                nobiliary particles), which will be avoided as equivalent name
                fragments.

            birth_year_pseudo_range:
                b, such that P(two people share a DOB) = 1/(365.25 * b).

            p_not_male_or_female:
                Probability that a person in the population has gender 'X'.
            p_female_given_male_or_female:
                Probability that a person in the population is female, given
                that they are either male or female.

            postcode_csv_filename:
                Postcode mapping. CSV (or ZIP) file. Special format; see
                :class:`PostcodeFrequencyInfo`.
            postcode_cache_filename:
                File in which to cache postcode information for faster loading.
            k_postcode:
                Multiple applied to postcode unit/sector frequencies, such that
                p_f_postcode = k_postcode * f_f_postcode and p_p_postcode =
                k_postcode * f_p_postcode. If None, defaults to
                UK_POPULATION_2017 / population_size, appropriate if the
                population under consideration is geographically constrained
                (rather than sampled from across the UK).
            p_unknown_or_pseudo_postcode:
                Probability that a random person will have a pseudo-postcode,
                e.g. ZZ99 3VZ (no fixed above) or a postcode not known to our
                database. Specifically, P(each pseudopostcode or unknown
                postcode unit | ¬H).
            k_pseudopostcode:
                Probability multiple: P(pseudopostcode sector or unknown
                postcode sector match | ¬H) = k_pseudopostcode *
                p_unknown_or_pseudo_postcode. Must strictly be >=1 and we
                enforce >1; see paper.

            p_ep1_forename:
                Error probability that a forename fails a full match but passes
                a partial 1 (metaphone) match. [GPD]
            p_ep2np1_forename:
                Error probability that a forename fails a full match and a
                partial 1 match but passes a partial 2 (F2C) match. [GPD]
            p_en_forename:
                Error probability that a forename yields no match at all. [GPD]
            p_ep1_surname:
                Error probability that a surname fails a full match but passes
                a partial 1 (metaphone) match. [GPD]
            p_ep2np1_surname:
                Error probability that a surname fails a full match and a
                partial 1 match but passes a partial 2 (F2C) match. [GPD]
            p_en_surname:
                Error probability that a surname yields no match at all. [GPD]
            p_ep_dob:
                Error probability that a DOB fails a full (YMD) match but
                passes a partial (YM, MD, or YD) match.
            p_en_dob:
                Error probability that a DOB produces no match at all.
            p_e_gender:
                Error probability of no gender match.
            p_ep_postcode:
                Probability that a postcode fails a full (unit) match but
                passes a partial (sector) match (due to error or a move within
                a sector).
            p_en_postcode:
                Probability that a postcode gives no match at all.
            min_log_odds_for_match:
                minimum log odds of a match, to consider two people a match
            exceeds_next_best_log_odds:
                In a multi-person comparison, the log odds of the best match
                must exceed those of the next-best match by this much for the
                best to be considered a unique winner.
            perfect_id_translation:
                Option dictionary mapping the perfect ID names in the proband
                to the equivalents in the sample, e.g. {"nhsnum": "nhsnumber"}.

            extra_validation_output:
                Add extra columns to the output for validation purposes?
            report_every:
                Report progress every n probands.
            min_probands_for_parallel:
                Minimum number of probands for which we will bother to use
                parallel processing.
            n_workers:
                Number of parallel processes to use, if parallel processing
                is used.
            verbose:
                Be verbose on creation?

        - [GPD] In ``{gender:p, ...}`` dict-as-string format.

        - F2C = First two characters.
        """
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Input validation
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        def raise_bad(x_: Any, name_: str) -> NoReturn:
            """
            Raise an informative ValueError.
            """
            raise ValueError(f"Bad {name_}: {x_!r}")

        def check_prob(
            p_: float, name_: str, not_certain: bool = False
        ) -> float:
            """
            Ensure that something is a probability, and return it.
            """
            if not_certain:
                if not 0 < p_ < 1:
                    raise_bad(p_, name_ + " [must be in range (0, 1)]")
            else:
                if not 0 <= p_ <= 1:
                    raise_bad(p_, name_)
            return p_

        def mk_gender_p_dict(csv_: str, name_: str) -> Dict[str, float]:
            """
            Transform a comma-separated list of ``gender:p`` values into
            a corresponding dictionary, and fill in the blanks.
            """
            d = {}  # type: Dict[str, float]
            for gender_p_str in csv_.split(","):
                g_p_components = gender_p_str.split(":")
                if len(g_p_components) != 2:
                    raise ValueError(f"Bad {name_}: {csv_!r}")
                g = g_p_components[0].strip()
                try:
                    p = check_prob(float(g_p_components[1].strip()), name_)
                except (ValueError, TypeError):
                    raise ValueError(f"Bad probability in {name_}: {csv_!r}")
                d[g] = p
            if GENDER_FEMALE not in d:
                raise ValueError(
                    f"Gender {GENDER_FEMALE} not specified in {name_}"
                )
            if GENDER_MALE not in d:
                raise ValueError(
                    f"Gender {GENDER_MALE} not specified in {name_}"
                )
            weighted_mean_m_f = (
                self.p_female_given_m_or_f * d[GENDER_FEMALE]
                + self.p_male_given_m_or_f * d[GENDER_MALE]
            )
            d.setdefault(GENDER_OTHER, weighted_mean_m_f)
            d.setdefault(GENDER_MISSING, weighted_mean_m_f)
            if set(d.keys()) != set(VALID_GENDERS):
                raise ValueError(
                    f"Missing or bad genders in {name_}: {csv_!r} -- genders "
                    f"should be {VALID_GENDERS}"
                )
            return d

        def mk_p_c_dict(
            p_ep1_: Dict[str, float],
            p_ep2np1_: Dict[str, float],
            p_en_: Dict[str, float],
        ) -> Dict[str, float]:
            """
            Calculates p_c = 1 - p_ep1 - p_ep2np1 = p_en.
            """
            d = {}  # type: Dict[str, float]
            for g in VALID_GENDERS:
                p_c_ = 1 - p_ep1_[g] - p_ep2np1_[g] - p_en_[g]
                assert 0 <= p_c_ <= 1
                d[g] = p_c_
            return d

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Basic creation
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        if verbose:
            log.debug("Building MatchConfig...")

        # Hash information

        self.hash_fn = make_hasher(hash_method=hash_method, key=hash_key).hash
        if not (rounding_sf is None or 1 <= rounding_sf):
            raise_bad(rounding_sf, Switches.ROUNDING_SF)
        self.rounding_sf = rounding_sf
        if local_id_hash_key:
            self.local_id_hash_fn = make_hasher(
                hash_method=hash_method, key=local_id_hash_key
            ).hash
        else:
            # Convert to string if necessary; otherwise, an identity function:
            self.local_id_hash_fn = str

        # Overall population

        if not (population_size > 0):
            raise_bad(population_size, Switches.POPULATION_SIZE)
        self.population_size = population_size
        # Precalculate this, for access speed:
        self.baseline_log_odds_same_person = log_odds_from_1_in_n(
            self.population_size
        )

        # Name handling: generic

        self.min_name_frequency = check_prob(
            min_name_frequency, Switches.MIN_NAME_FREQUENCY
        )
        accent_dict = {}  # type: Dict[str, str]
        for accent_pair in accent_transliterations_csv.split(","):
            accent_components = accent_pair.split("/")
            if len(accent_components) != 2:
                raise ValueError(
                    f"Bad accent_transliterations_csv: "
                    f"{accent_transliterations_csv!r}"
                )
            accented = safe_upper(accent_components[0].strip())
            plain = safe_upper(accent_components[1].strip())
            if len(accented) != 1:
                raise ValueError(
                    f"Bad accent_transliterations_csv: "
                    f"{accent_transliterations_csv!r} -- contains accented "
                    f"character {accented!r}, which should be of length 1"
                )
            accent_dict[accented] = plain
        self.accent_transliterations = str.maketrans(accent_dict)
        self.nonspecific_name_components = set()  # type: Set[str]
        for nonspec in nonspecific_name_components_csv.split(","):
            self.nonspecific_name_components.add(nonspec.strip().upper())

        # Name handling: forenames

        self.forename_csv_filename = forename_sex_csv_filename
        self.forename_cache_filename = forename_cache_filename
        self.forename_freq_info = NameFrequencyInfo(
            csv_filename=forename_sex_csv_filename,
            cache_filename=forename_cache_filename,
            min_frequency=min_name_frequency,
            by_gender=True,
        )

        # Name handling: surnames

        self.surname_csv_filename = surname_csv_filename
        self.surname_cache_filename = surname_cache_filename
        self.surname_freq_info = NameFrequencyInfo(
            csv_filename=surname_csv_filename,
            cache_filename=surname_cache_filename,
            min_frequency=min_name_frequency,
            by_gender=False,
        )

        # Population frequencies: DOB

        self.birth_year_pseudo_range = birth_year_pseudo_range
        if not (birth_year_pseudo_range >= 1):
            raise_bad(
                birth_year_pseudo_range, Switches.BIRTH_YEAR_PSEUDO_RANGE
            )

        # Population frequencies: sex/gender

        # ... Check this before using mk_gender_p_dict:
        self.p_female_given_m_or_f = check_prob(
            p_female_given_male_or_female,
            Switches.P_FEMALE_GIVEN_MALE_OR_FEMALE,
        )
        self.p_male_given_m_or_f = 1 - self.p_female_given_m_or_f
        self.p_not_male_or_female = check_prob(
            p_not_male_or_female, Switches.P_NOT_MALE_OR_FEMALE
        )
        p_male_or_female = 1 - p_not_male_or_female
        self.p_female = p_female_given_male_or_female * p_male_or_female
        self.p_male = p_male_or_female - self.p_female

        # Population frequencies: postcode

        self.postcode_freq = PostcodeFrequencyInfo(
            csv_filename=postcode_csv_filename,
            cache_filename=postcode_cache_filename,
        )
        self.p_unknown_or_pseudo_postcode_unit = check_prob(
            p_unknown_or_pseudo_postcode,
            Switches.P_UNKNOWN_OR_PSEUDO_POSTCODE,
            not_certain=True,
        )
        if k_pseudopostcode <= 1:
            raise ValueError(f"Bad {Switches.K_PSEUDOPOSTCODE}: must be >1")
        self.k_pseudopostcode = k_pseudopostcode
        self.p_unknown_or_pseudo_postcode_sector = check_prob(
            k_pseudopostcode * p_unknown_or_pseudo_postcode,
            f"P(unknown postcode or pseudopostcode sector | ¬H) = "
            f"{Switches.K_PSEUDOPOSTCODE} * "
            f"{Switches.P_UNKNOWN_OR_PSEUDO_POSTCODE}",
            not_certain=True,
        )
        self.k_postcode = (
            UK_POPULATION_2017 / self.population_size
            if k_postcode is None
            else k_postcode
        )
        self.p_known_postcode = 1 - self.p_unknown_or_pseudo_postcode_sector

        # Error probabilities: forenames

        self.p_ep1_forename = mk_gender_p_dict(
            p_ep1_forename, Switches.P_EP1_FORENAME
        )
        self.p_ep2np1_forename = mk_gender_p_dict(
            p_ep2np1_forename, Switches.P_EP2NP1_FORENAME
        )
        self.p_en_forename = mk_gender_p_dict(
            p_en_forename, Switches.P_EN_FORENAME
        )
        self.p_c_forename = mk_p_c_dict(
            p_ep1_=self.p_ep1_forename,
            p_ep2np1_=self.p_ep2np1_forename,
            p_en_=self.p_en_forename,
        )
        self.p_u_forename = check_prob(p_u_forename, Switches.P_U_FORENAME)

        # Error probabilities: surnames

        self.p_ep1_surname = mk_gender_p_dict(
            p_ep1_surname, Switches.P_EP1_SURNAME
        )
        self.p_ep2np1_surname = mk_gender_p_dict(
            p_ep2np1_surname, Switches.P_EP2NP1_SURNAME
        )
        self.p_en_surname = mk_gender_p_dict(
            p_en_surname, Switches.P_EN_SURNAME
        )
        self.p_c_surname = mk_p_c_dict(
            p_ep1_=self.p_ep1_surname,
            p_ep2np1_=self.p_ep2np1_surname,
            p_en_=self.p_en_surname,
        )

        # Error probabilities: DOB

        self.p_ep_dob = check_prob(p_ep_dob, Switches.P_EP_DOB)
        self.p_en_dob = check_prob(p_en_dob, Switches.P_EN_DOB)

        # Error probabilities: gender

        self.p_e_gender_error = check_prob(
            p_e_gender,
            Switches.P_E_GENDER,
        )

        # Error probabilities: postcode

        self.p_ep_postcode = check_prob(p_ep_postcode, Switches.P_EP_POSTCODE)
        self.p_en_postcode = check_prob(p_en_postcode, Switches.P_EN_POSTCODE)

        # Matching rules

        self.min_log_odds_for_match = min_log_odds_for_match
        self.exceeds_next_best_log_odds = exceeds_next_best_log_odds
        if perfect_id_translation is None:
            perfect_id_xlate_raw = {}
        elif isinstance(perfect_id_translation, dict):
            perfect_id_xlate_raw = perfect_id_translation
        elif isinstance(perfect_id_translation, str):
            perfect_id_xlate_raw = dict_from_str(perfect_id_translation)
        else:
            raise ValueError(
                f"Bad perfect_id_translation: {perfect_id_translation!r}"
            )
        self.perfect_id_translation = {
            standardize_perfect_id_key(k): standardize_perfect_id_value(v)
            for k, v in perfect_id_xlate_raw.values()
        }
        if self.perfect_id_translation:
            log.info(
                f"Using proband-to-sample perfect ID translation: "
                f"{self.perfect_id_translation}"
            )

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Some derived frequencies
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        # DOB:

        self.p_c_dob = 1 - self.p_ep_dob - self.p_en_dob
        assert 0 <= self.p_c_dob <= 1
        # These ignore the specialness of 29 February:
        self.p_f_dob = 1 / (DAYS_PER_YEAR * birth_year_pseudo_range)
        p_share_dob_md_not_ymd = (1 / DAYS_PER_YEAR) - self.p_f_dob
        p_share_dob_yd_not_ymd = (
            1 / (DAYS_PER_MONTH * birth_year_pseudo_range)
        ) - self.p_f_dob
        p_share_dob_ym_not_ymd = (
            1 / (MONTHS_PER_YEAR * birth_year_pseudo_range)
        ) - self.p_f_dob
        # These three are mutually exclusive possibilities (e.g. you can't
        # share YM and MD without sharing YMD), so we can just sum:
        self.p_pnf_dob = (
            p_share_dob_md_not_ymd
            + p_share_dob_yd_not_ymd
            + p_share_dob_ym_not_ymd
        )
        # To find p_pnf_dob in terms of b, using Octave:
        #   pkg load symbolic
        #   syms b
        #   simplify(1/365.25 + 1/(30.4375 * b) + 1/(12 * b) - 3/(365.25 * b))
        # gives
        #   (16 * b + 631) / (5844 * b)

        self.p_n_dob = 1 - self.p_f_dob - self.p_pnf_dob
        assert 0 <= self.p_f_dob <= 1
        assert 0 <= p_share_dob_md_not_ymd <= 1
        assert 0 <= p_share_dob_yd_not_ymd <= 1
        assert 0 <= p_share_dob_ym_not_ymd <= 1
        assert 0 <= self.p_pnf_dob <= 1
        assert 0 <= self.p_n_dob <= 1

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Technical
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        self.extra_validation_output = extra_validation_output
        self.report_every = report_every
        self.min_probands_for_parallel = min_probands_for_parallel
        self.n_workers = n_workers

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Reporting
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        self.partial_dob_mismatch_allowed = self.p_c_dob < 1
        self.complete_dob_mismatch_allowed = self.p_en_dob > 0
        if self.complete_dob_mismatch_allowed:
            potential_speedup_factor = round_sf(
                normal_round_int(1 / (1 - self.p_n_dob)),
                n=3,
            )
            log.warning(
                f"You are allowing a person's DOB to be completely different, "
                f"with p = {self.p_en_dob}. That is valid but much less "
                f"efficient computationally (by an estimated factor of about "
                f"{potential_speedup_factor})."
            )
            # ... for a 90-year range, this is a factor of about 252.
            # For a single year, it's about 9; if I'm born on 1 Jan, allowing
            # single-component errors mean we need to consider 1 Jan, but also
            # all of Jan, and all other firsts of the month -- total 42 out of
            # 365 days, or 1/8.69 of the year.
            # For a multi-year range, the speedup increases: if I'm born on 1
            # Jan 1950 and we are considering 1900-1999, we'd need to consider
            # 1950-01-01 (1), ????-01-01 (100), 1950-01-?? (31), 1950-??-01
            # (12), minus the overlaps (3), giving 141 possibilities but out
            # of about 36500, i.e. considering only 1/259 of the candidates.

        if verbose:
            log.debug(f"... MatchConfig built. Settings: {self}")
            # log.debug(
            #     f"p_dob_correct = {self.p_dob_correct}, "
            #     f"p_dob_single_component_error = "
            #     f"{self.p_dob_single_component_error}, "
            #     f"p_dob_major_error = {self.p_dob_major_error}"
            # )
            # log.debug(
            #     f"p_two_people_share_dob_ymd = "
            #     f"{self.p_two_people_share_dob_ymd}, "
            #     f"p_share_dob_md_not_ymd = {p_share_dob_md_not_ymd}, "
            #     f"p_share_dob_yd_not_ymd = {p_share_dob_yd_not_ymd}, "
            #     f"p_share_dob_ym_not_ymd = {p_share_dob_ym_not_ymd}, "
            #     f"p_two_people_have_partial_dob_match = "
            #     f"{self.p_two_people_partial_dob_match}, "
            #     f"p_two_people_no_dob_similarity = "
            #     f"{self.p_two_people_no_dob_similarity}"
            # )

    # -------------------------------------------------------------------------
    # String representation
    # -------------------------------------------------------------------------

    def __str__(self) -> str:
        return auto_repr(self)

    # not __repr__(), or it clutters up all the other objects

    # -------------------------------------------------------------------------
    # Identifier frequency information
    # -------------------------------------------------------------------------

    def get_forename_freq_info(
        self, name: str, gender: str, prestandardized: bool = False
    ) -> BasicNameFreqInfo:
        """
        Returns the baseline frequency of a forename.

        Args:
            name: the name to check
            gender: the gender to look up for
            prestandardized: was the name pre-standardized?
        """
        if not prestandardized:
            name = standardize_name(name)
        freq_func = self.forename_freq_info.name_frequency_info
        if gender in (GENDER_FEMALE, GENDER_MALE):
            return freq_func(name, gender, prestandardized=True)
        # Otherwise, take the mean across genders:
        return BasicNameFreqInfo.weighted_mean(
            objects=[
                freq_func(name, GENDER_FEMALE, prestandardized=True),
                freq_func(name, GENDER_MALE, prestandardized=True),
            ],
            weights=[self.p_female, self.p_male],
        )

    def get_surname_freq_info(
        self, name: str, prestandardized: bool = False
    ) -> BasicNameFreqInfo:
        """
        Returns the baseline frequency of a surname.

        Args:
            name: the name to check
            prestandardized: was it pre-standardized?
        """
        return self.surname_freq_info.name_frequency_info(
            name, prestandardized=prestandardized
        )

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
        return self.postcode_freq.debug_is_valid_postcode(postcode_unit)

    def postcode_unit_sector_freq(
        self, postcode_unit: str, prestandardized: bool = False
    ) -> Tuple[float, float]:
        """
        Returns the frequency for a full postcode, or postcode unit (the
        proportion of the population who live in that postcode), and the
        corresponding larger-scale postcode sector.

        The underlying function ensures that the sector frequency is as least
        as big as the unit frequency.
        """
        return self.postcode_freq.postcode_unit_sector_frequency(
            postcode_unit, prestandardized=prestandardized
        )

    def debug_postcode_unit_population(
        self, postcode_unit: str, prestandardized: bool = False
    ) -> float:
        """
        Returns the calculated population of a postcode unit.

        Args:
            postcode_unit: the postcode unit to check
            prestandardized: was the postcode pre-standardized in format?
        """
        return self.postcode_freq.debug_postcode_unit_population(
            postcode_unit, prestandardized=prestandardized
        )

    def debug_postcode_sector_population(
        self, postcode_sector: str, prestandardized: bool = False
    ) -> float:
        """
        Returns the calculated population of a postcode sector.

        Args:
            postcode_sector: the postcode sector to check
            prestandardized: was the postcode pre-standardized in format?
        """
        return self.postcode_freq.debug_postcode_sector_population(
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

    # -------------------------------------------------------------------------
    # Perfect ID handling
    # -------------------------------------------------------------------------

    def remap_perfect_id_key(self, key: str) -> str:
        return self.perfect_id_translation.get(key, key)


# =============================================================================
# Dummy config that doesn't load frequency information
# =============================================================================


def mk_dummy_match_config() -> MatchConfig:
    """
    Returns a dummy config with empty frequency information.
    """
    return MatchConfig(
        forename_cache_filename="",
        forename_sex_csv_filename="",
        surname_cache_filename="",
        surname_csv_filename="",
        postcode_cache_filename="",
        postcode_csv_filename="",
    )
