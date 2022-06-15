#!/usr/bin/env python

r"""
crate_anon/linkage/constants.py

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

**Constants for linkage tools.**

"""

# =============================================================================
# Imports
# =============================================================================

import math
from multiprocessing import cpu_count
import os
import platform

import appdirs
from cardinal_pythonlib.hash import HashMethods
from cardinal_pythonlib.probability import probability_from_log_odds

from crate_anon.common.constants import EnvVar


# =============================================================================
# Constants
# =============================================================================

# CHECK_BASIC_ASSERTIONS_IN_HIGH_SPEED_FUNCTIONS = False  # for debugging only

MINUS_INFINITY = -math.inf

DAYS_PER_YEAR = 365.25  # approximately!
MONTHS_PER_YEAR = 12
DAYS_PER_MONTH = DAYS_PER_YEAR / MONTHS_PER_YEAR  # on average

THIS_DIR = os.path.abspath(os.path.dirname(__file__))

UK_MEAN_OA_POPULATION_2011 = 309
# ... https://www.ons.gov.uk/methodology/geography/ukgeographies/censusgeography  # noqa
UK_POPULATION_2017 = 66040000  # 2017 figure, 66.04m

GENDER_MALE = "M"
GENDER_FEMALE = "F"
GENDER_OTHER = "X"
VALID_GENDERS = ["", GENDER_MALE, GENDER_FEMALE, GENDER_OTHER]
# ... standard three gender codes; "" = missing


class FuzzyDefaults:
    """
    Some configuration defaults.
    """

    # -------------------------------------------------------------------------
    # Filenames
    # -------------------------------------------------------------------------
    _appname = "crate"

    # Public data that we provide a local copy of
    _THIS_DIR = os.path.abspath(os.path.dirname(__file__))
    _DATA_DIR = os.path.join(_THIS_DIR, "data")
    FORENAME_SEX_FREQ_CSV = os.path.join(_DATA_DIR, "us_forename_sex_freq.zip")
    SURNAME_FREQ_CSV = os.path.join(_DATA_DIR, "us_surname_freq.zip")
    POSTCODES_CSV = os.path.join(_DATA_DIR, "ONSPD_MAY_2022_UK.zip")

    if EnvVar.GENERATING_CRATE_DOCS in os.environ:
        DEFAULT_CACHE_DIR = "/path/to/crate/user/data"
        N_PROCESSES = 8
    else:
        DEFAULT_CACHE_DIR = os.path.join(
            appdirs.user_data_dir(appname=_appname)
        )
        if platform.system() == "Windows":
            N_PROCESSES = 1  # *much* faster!
        else:
            N_PROCESSES = cpu_count()

    # Caches
    FORENAME_CACHE_FILENAME = os.path.join(
        DEFAULT_CACHE_DIR, "fuzzy_forename_cache.pickle"
    )
    POSTCODE_CACHE_FILENAME = os.path.join(
        DEFAULT_CACHE_DIR, "fuzzy_postcode_cache.pickle"
    )
    SURNAME_CACHE_FILENAME = os.path.join(
        DEFAULT_CACHE_DIR, "fuzzy_surname_cache.pickle"
    )

    # -------------------------------------------------------------------------
    # Hashing, rounding
    # -------------------------------------------------------------------------
    HASH_KEY = "fuzzy_id_match_default_hash_key_DO_NOT_USE_FOR_LIVE_DATA"
    HASH_METHOD = HashMethods.HMAC_SHA256
    ROUNDING_SF = 5
    # ... number of significant figures for frequency rounding; 3 may be too
    # small, e.g. surname Smith 0.01006, corresponding metaphone SM0
    # 0.010129999999999998 would be the same at 3sf.

    # -------------------------------------------------------------------------
    # Performance
    # -------------------------------------------------------------------------
    MIN_PROBANDS_FOR_PARALLEL = 1000
    # ... a machine that takes ~30s to set up a basic parallel run (and 107.9s
    # for a 10k-to-10k comparison) processes single results at about 37/s... so
    # the break-even point is probably around 1000. But that does depend on the
    # sample size too.

    # -------------------------------------------------------------------------
    # Population priors
    # -------------------------------------------------------------------------
    # See command-line help.
    # (E) Empirical; see validation paper.
    BIRTH_YEAR_PSEUDO_RANGE = 90
    MEAN_OA_POPULATION = UK_MEAN_OA_POPULATION_2011
    NAME_MIN_FREQ = 5e-6
    P_FEMALE_GIVEN_MALE_OR_FEMALE = 0.51  # (E)
    P_MIDDLE_NAME_N_PRESENT = (0.8, 0.1375)  # (E)
    P_NOT_MALE_OR_FEMALE = 0.004  # (E)
    P_UNKNOWN_OR_PSEUDO_POSTCODE = 0.000203  # (E)
    # - Pseudo-postcodes: e.g. ZZ99 3VZ, no fixed abode; ZZ99 3CZ, England/UK
    #   not otherwise specified [4].
    # - These postcodes are not in the ONS Postcode Directory.
    # - In Apr-Jun 2019, 11.4% of households in England who were {homeless or
    #   threatened with homelessness} had no fixed abode [1, Table 2].
    # - That table totals 68,180 households, so that probably matches the
    #   68,170 households in England used as the summary figure on p1 [1].
    # - In 2020, there were ~27.8 million households in the UK [2].
    # - The mean household size in the UK is 2.4 [2]. (Although the proportion
    #   who are homeless is likely biased towards single individuals?)
    #   Yes, "Nearly two-thirds of these were single households (households
    #   without children)."
    # - 0.843 of the UK population live in England
    # - So, the fraction of homelessness can be estimated as
    _ = """
        avg_people_per_household = 2.4
        n_people_per_homeless_household = (2 / 3) * 1 + (1 / 3) * avg_people_per_household
        n_people_homeless_england = (11.4 / 100) * 68180 * n_people_per_homeless_household 
        n_people_uk = 27.8e6 * 2.4  # 66.7 million, so that's about right
        n_people_england = 0.843 * n_people_uk
        p_homeless = n_people_homeless_england / n_people_england
    """  # noqa
    #              = 0.0002026794
    #   We'll round: 0.000203
    #   (So that's about 13.5k people with postcode ZZ99 3VZ, estimated.)
    # [1] https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/852953/Statutory_Homelessness_Statistical_Release_Apr-Jun_2019.pdf  # noqa
    # [2] https://www.ons.gov.uk/peoplepopulationandcommunity/birthsdeathsandmarriages/families/bulletins/familiesandhouseholds/2020  # noqa
    # [3] https://pubmed.ncbi.nlm.nih.gov/35477868/
    # [4] http://www.datadictionary.wales.nhs.uk/index.html#!WordDocuments/postcode.htm  # noqa
    POPULATION_SIZE = UK_POPULATION_2017

    # -------------------------------------------------------------------------
    # Error rates
    # -------------------------------------------------------------------------
    # (E) Empirical; see validation paper.
    # (*) Using the empirical value is much less efficient computationally.
    P_MINOR_FORENAME_ERROR = 0.001
    P_PROBAND_MIDDLE_NAME_MISSING = 0.05
    P_SAMPLE_MIDDLE_NAME_MISSING = 0.05
    P_MINOR_SURNAME_ERROR = 0.001
    P_DOB_ERROR = 0.00492  # (E)
    # P_DOB_SINGLE_COMPONENT_ERROR_IF_ERROR = 0.933  # (E) (*)
    P_DOB_SINGLE_COMPONENT_ERROR_IF_ERROR = 1  # Much faster (*)
    P_GENDER_ERROR = 0.0033  # (E)
    P_MINOR_POSTCODE_ERROR = 0.0097  # (E)

    # -------------------------------------------------------------------------
    # Matching process
    # -------------------------------------------------------------------------
    MIN_LOG_ODDS_FOR_MATCH = 5  # theta, in the validation paper
    EXCEEDS_NEXT_BEST_LOG_ODDS = 10  # delta, in the validation paper
    REPORT_EVERY = 100  # cosmetic only

    # -------------------------------------------------------------------------
    # Derived
    # -------------------------------------------------------------------------

    MIN_P_FOR_MATCH = probability_from_log_odds(MIN_LOG_ODDS_FOR_MATCH)
    P_MIDDLE_NAME_N_PRESENT_STR = ",".join(
        str(x) for x in P_MIDDLE_NAME_N_PRESENT
    )
