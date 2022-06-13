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
from typing import List, NoReturn, Optional, Tuple

from cardinal_pythonlib.hash import make_hasher
from cardinal_pythonlib.probability import log_odds_from_1_in_n
from cardinal_pythonlib.reprfunc import auto_repr

from crate_anon.linkage.constants import (
    DAYS_PER_MONTH,
    DAYS_PER_YEAR,
    FuzzyDefaults,
    GENDER_MALE,
    GENDER_FEMALE,
    MONTHS_PER_YEAR,
)
from crate_anon.linkage.frequencies import (
    NameFrequencyInfo,
    PostcodeFrequencyInfo,
)
from crate_anon.linkage.helpers import standardize_name

log = logging.getLogger(__name__)


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
        hash_method: str = FuzzyDefaults.HASH_METHOD,
        rounding_sf: Optional[int] = FuzzyDefaults.ROUNDING_SF,
        local_id_hash_key: str = None,
        population_size: int = FuzzyDefaults.POPULATION_SIZE,
        forename_cache_filename: str = FuzzyDefaults.FORENAME_CACHE_FILENAME,
        forename_sex_csv_filename: str = FuzzyDefaults.FORENAME_SEX_FREQ_CSV,
        surname_cache_filename: str = FuzzyDefaults.SURNAME_CACHE_FILENAME,
        surname_csv_filename: str = FuzzyDefaults.SURNAME_FREQ_CSV,
        min_name_frequency: float = FuzzyDefaults.NAME_MIN_FREQ,
        p_middle_name_n_present: List[float] = (
            FuzzyDefaults.P_MIDDLE_NAME_N_PRESENT
        ),
        birth_year_pseudo_range: float = FuzzyDefaults.BIRTH_YEAR_PSEUDO_RANGE,
        p_not_male_or_female: float = FuzzyDefaults.P_NOT_MALE_OR_FEMALE,
        p_female_given_male_or_female: float = (
            FuzzyDefaults.P_FEMALE_GIVEN_MALE_OR_FEMALE
        ),
        postcode_cache_filename: str = FuzzyDefaults.POSTCODE_CACHE_FILENAME,
        postcode_csv_filename: str = FuzzyDefaults.POSTCODES_CSV,
        mean_oa_population: float = FuzzyDefaults.MEAN_OA_POPULATION,
        p_unknown_or_pseudo_postcode: float = (
            FuzzyDefaults.P_UNKNOWN_OR_PSEUDO_POSTCODE
        ),
        p_minor_forename_error: float = FuzzyDefaults.P_MINOR_FORENAME_ERROR,
        p_proband_middle_name_missing: float = (
            FuzzyDefaults.P_PROBAND_MIDDLE_NAME_MISSING
        ),
        p_sample_middle_name_missing: float = (
            FuzzyDefaults.P_SAMPLE_MIDDLE_NAME_MISSING
        ),
        p_minor_surname_error: float = FuzzyDefaults.P_MINOR_SURNAME_ERROR,
        p_dob_error: float = FuzzyDefaults.P_DOB_ERROR,
        p_dob_single_component_error_if_error: float = (
            FuzzyDefaults.P_DOB_SINGLE_COMPONENT_ERROR_IF_ERROR
        ),
        p_gender_error: float = FuzzyDefaults.P_GENDER_ERROR,
        p_minor_postcode_error: float = FuzzyDefaults.P_MINOR_POSTCODE_ERROR,
        min_log_odds_for_match: float = FuzzyDefaults.MIN_LOG_ODDS_FOR_MATCH,
        exceeds_next_best_log_odds: float = (
            FuzzyDefaults.EXCEEDS_NEXT_BEST_LOG_ODDS
        ),
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

            forename_cache_filename:
                File in which to cache forename information for faster loading.
            forename_sex_csv_filename:
                Forename frequencies. CSV file, with no header, of "name,
                frequency" pairs.
            surname_cache_filename:
                File in which to cache forename information for faster loading.
            surname_csv_filename:
                Surname frequencies. CSV file, with no header, of "name,
                frequency" pairs.
            min_name_frequency:
                Minimum name frequency; see command-line help.
            p_middle_name_n_present:
                List of probabilities. The first is P(middle name 1 present).
                The second is P(middle name 2 present | middle name 1 present),
                and so on. The last value is re-used ad infinitum as required.

            birth_year_pseudo_range:
                b, such that P(two people share a DOB) = 1/(365.25 * b).

            p_not_male_or_female:
                Probability that a person in the population has gender 'X'.
            p_female_given_male_or_female:
                Probability that a person in the population is female, given
                that they are either male or female.

            postcode_cache_filename:
                File in which to cache postcode information for faster loading.
            postcode_csv_filename:
                Postcode mapping. CSV (or ZIP) file. Special format; see
                :class:`PostcodeFrequencyInfo`.
            mean_oa_population:
                The mean population of a UK Census Output Area.
            p_unknown_or_pseudo_postcode:
                Probability that a random person will have a pseudo-postcode,
                e.g. ZZ99 3VZ (no fixed above) or a postcode not known to our
                database.

            p_minor_forename_error:
                Probability that a forename fails a full match but passes a
                partial match.
            p_proband_middle_name_missing:
                Probability that a middle name, present in the sample, is
                missing from the proband.
            p_sample_middle_name_missing:
                Probability that a middle name, present in the proband, is
                missing from the sample.
            p_minor_surname_error:
                Probability that a surname fails a full match but passes a
                partial match.
            p_dob_error:
                Probability that a DOB is wrong, for the same person.
            p_dob_single_component_error_if_error:
                Probability, given that a DOB is wrong, that it is wrong in one
                (and one only) of year, month, day.
            p_gender_error:
                Probability that a gender match fails because of a data
                error.
            p_minor_postcode_error:
                Probability that a postcode fails a full match but passes a
                partial match.

            min_log_odds_for_match:
                minimum log odds of a match, to consider two people a match
            exceeds_next_best_log_odds:
                In a multi-person comparison, the log odds of the best match
                must exceed those of the next-best match by this much for the
                best to be considered a unique winner.

            verbose:
                Be verbose on creation?
        """
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Input validation
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        def raise_bad(x_, name_) -> NoReturn:
            raise ValueError(f"Bad {name_}: {x_!r}")

        def check_prob(p_, name_) -> None:
            if not 0 <= p_ <= 1:
                raise_bad(p_, name_)

        if not (rounding_sf is None or 1 <= rounding_sf):
            raise_bad(rounding_sf, "rounding_sf")

        if not (population_size > 0):
            raise_bad(population_size, "population_size")

        check_prob(min_name_frequency, "min_name_frequency")
        for i, x in enumerate(p_middle_name_n_present):
            check_prob(x, f"p_middle_name_n_present[{i}]")

        if not (birth_year_pseudo_range >= 1):
            raise_bad(birth_year_pseudo_range, "birth_year_pseudo_range")

        check_prob(p_not_male_or_female, "p_not_male_or_female")
        check_prob(
            p_female_given_male_or_female, "p_female_given_male_or_female"
        )

        if not (mean_oa_population > 0):
            raise_bad(mean_oa_population, "mean_oa_population")
        check_prob(
            p_unknown_or_pseudo_postcode, "p_unknown_or_pseudo_postcode"
        )

        check_prob(p_minor_forename_error, "p_minor_forename_error")
        check_prob(p_minor_surname_error, "p_minor_surname_error")
        check_prob(
            p_proband_middle_name_missing, "p_proband_middle_name_missing"
        )
        check_prob(
            p_sample_middle_name_missing, "p_sample_middle_name_missing"
        )
        check_prob(p_dob_error, "p_dob_error")
        check_prob(
            p_dob_single_component_error_if_error,
            "p_dob_single_component_error_if_error",
        )
        check_prob(p_gender_error, "p_gender_error")
        check_prob(p_minor_postcode_error, "p_minor_postcode_error")

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Basic creation
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        if verbose:
            log.debug("Building MatchConfig...")

        # Hash information

        self.hash_fn = make_hasher(hash_method=hash_method, key=hash_key).hash
        self.rounding_sf = rounding_sf
        if local_id_hash_key:
            self.local_id_hash_fn = make_hasher(
                hash_method=hash_method, key=local_id_hash_key
            ).hash
        else:
            # Convert to string if necessary; otherwise, an identity function:
            self.local_id_hash_fn = str

        # Population frequencies

        self.population_size = population_size
        # Precalculate this, for access speed:
        self.baseline_log_odds_same_person = log_odds_from_1_in_n(
            self.population_size
        )

        self.forename_csv_filename = forename_sex_csv_filename
        self.surname_csv_filename = surname_csv_filename
        self.min_name_frequency = min_name_frequency
        self.p_middle_name_n_present = p_middle_name_n_present

        self.birth_year_pseudo_range = birth_year_pseudo_range

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
            p_unknown_or_pseudo_postcode=p_unknown_or_pseudo_postcode,
        )

        # Error probabilities

        self.p_minor_forename_error = p_minor_forename_error
        self.p_minor_surname_error = p_minor_surname_error
        self.p_proband_middle_name_missing = p_proband_middle_name_missing
        self.p_sample_middle_name_missing = p_sample_middle_name_missing
        self.p_dob_error = p_dob_error
        self.p_dob_single_component_error_if_error = (
            p_dob_single_component_error_if_error
        )
        self.p_minor_postcode_error = p_minor_postcode_error

        # Matching rules

        self.min_log_odds_for_match = min_log_odds_for_match
        self.exceeds_next_best_log_odds = exceeds_next_best_log_odds

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Some derived frequencies
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        self.p_dob_correct = 1 - self.p_dob_error
        self.p_dob_single_component_error = (
            self.p_dob_error * self.p_dob_single_component_error_if_error
        )
        self.p_dob_major_error = 1 - (
            self.p_dob_correct + self.p_dob_single_component_error
        )
        assert 0 <= self.p_dob_correct <= 1
        assert 0 <= self.p_dob_single_component_error <= 1
        assert 0 <= self.p_dob_major_error <= 1
        if self.p_dob_major_error > 0:
            log.warning(
                f"You are allowing a person's DOB to be completely different, "
                f"with p = {self.p_dob_major_error}. That is valid but much "
                f"less efficient computationally."
            )

        # These ignore the specialness of 29 February:
        self.p_two_people_share_dob_ymd = 1 / (
            DAYS_PER_YEAR * birth_year_pseudo_range
        )
        p_share_dob_md_not_ymd = (
            1 / DAYS_PER_YEAR
        ) - self.p_two_people_share_dob_ymd
        p_share_dob_yd_not_ymd = (
            1 / (DAYS_PER_MONTH * birth_year_pseudo_range)
        ) - self.p_two_people_share_dob_ymd
        p_share_dob_ym_not_ymd = (
            1 / (MONTHS_PER_YEAR * birth_year_pseudo_range)
        ) - self.p_two_people_share_dob_ymd
        self.p_two_people_partial_dob_match = (
            p_share_dob_md_not_ymd
            + p_share_dob_yd_not_ymd
            + p_share_dob_ym_not_ymd
        )
        self.p_two_people_no_dob_similarity = (
            1
            - self.p_two_people_share_dob_ymd
            - self.p_two_people_partial_dob_match
        )
        assert 0 <= self.p_two_people_share_dob_ymd <= 1
        assert 0 <= p_share_dob_md_not_ymd <= 1
        assert 0 <= p_share_dob_yd_not_ymd <= 1
        assert 0 <= p_share_dob_ym_not_ymd <= 1
        assert 0 <= self.p_two_people_partial_dob_match <= 1
        assert 0 <= self.p_two_people_no_dob_similarity <= 1

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Reporting
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

        self.complete_dob_mismatch_allowed = self.p_dob_major_error > 0
        if self.complete_dob_mismatch_allowed:
            log.warning(
                f"You are allowing a person's DOB to be completely different, "
                f"with p = {self.p_dob_major_error}. That is valid but much "
                f"less efficient computationally."
            )

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
        return freq

    def p_middle_name_present(self, n: int) -> float:
        """
        Returns the probability (in the population) that someone has a middle
        name n, given that they have middle name n - 1.

        (For example, n = 1 gives the probability of having a middle name; n =
        2 is the probability of having a second middle name, given that you
        have a first middle name.)
        """
        # if CHECK_BASIC_ASSERTIONS_IN_HIGH_SPEED_FUNCTIONS:
        #     assert n >= 1
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
        return freq

    def surname_metaphone_freq(self, metaphone: str) -> float:
        """
        Returns the baseline frequency of a surname's metaphone.

        Args:
            metaphone: the metaphone to check
        """
        freq = self._surname_freq.metaphone_frequency(metaphone)
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
        return self._postcode_freq.debug_is_valid_postcode(postcode_unit)

    def postcode_unit_sector_freq(
        self, postcode_unit: str, prestandardized: bool = False
    ) -> Tuple[float, float]:
        """
        Returns the frequency for a full postcode, or postcode unit (the
        proportion of the population who live in that postcode).
        """
        return self._postcode_freq.postcode_unit_sector_frequency(
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
        return self._postcode_freq.debug_postcode_unit_population(
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
        return self._postcode_freq.debug_postcode_sector_population(
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
