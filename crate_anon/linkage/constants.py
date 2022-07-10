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
from typing import Dict

import appdirs
from cardinal_pythonlib.hash import HashMethods
from cardinal_pythonlib.probability import probability_from_log_odds

from crate_anon.common.constants import EnvVar


# =============================================================================
# Helper functions
# =============================================================================


def _mk_dictstr(x: Dict[str, float]) -> str:
    return ",".join(f"{k}:{v}" for k, v in x.items())


# =============================================================================
# Constants
# =============================================================================

# CHECK_BASIC_ASSERTIONS_IN_HIGH_SPEED_FUNCTIONS = False  # for debugging only

INFINITY = math.inf
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
GENDER_MISSING = ""
VALID_GENDERS = [GENDER_MISSING, GENDER_MALE, GENDER_FEMALE, GENDER_OTHER]
# ... standard three gender codes; "" = missing


SIMPLIFY_PUNCTUATION_WHITESPACE_TRANS = str.maketrans(
    {
        "\t": " ",  # tab -> space
        "\n": " ",  # linefeed -> space
        "\r": " ",  # carriage return -> space
        "“": '"',  # curly left double quote -> straight double quote
        "”": '"',  # curly right double quote -> straight double quote
        "‘": "'",  # curly left single quote -> straight single quote
        "’": "'",  # curly right single quote -> straight single quote
        "–": "-",  # en dash -> hyphen
        "—": "-",  # em dash -> hyphen
        "−": "-",  # minus -> hyphen
    }
)


# A capital Eszett was introduced for the first time in 2017. Before that, SS
# was the capital version. See https://en.wikipedia.org/wiki/%C3%9F.
ESZETT_LOWER_CASE = "ß"
ESZETT_UPPER_CASE = "ẞ"
SAFE_UPPER_PRETRANSLATE = str.maketrans({ESZETT_LOWER_CASE: ESZETT_UPPER_CASE})
MANGLE_PRETRANSLATE = str.maketrans(
    {
        ESZETT_LOWER_CASE: "ss",
        ESZETT_UPPER_CASE: "SS",
    }
)


class Switches:
    """
    Argparse option switches that are used in several places, and also the
    names of MatchConfig parameters, used for error messages.
    """

    ALLOW_DEFAULT_HASH_KEY = "allow_default_hash_key"
    EXTRA_VALIDATION_OUTPUT = "extra_validation_output"
    INCLUDE_OTHER_INFO = "include_other_info"
    INPUT = "input"
    OUTPUT = "output"
    MIN_PROBANDS_FOR_PARALLEL = "min_probands_for_parallel"
    N_WORKERS = "n_workers"
    REPORT_EVERY = "report_every"

    KEY = "key"
    HASH_METHOD = "hash_method"
    ROUNDING_SF = "rounding_sf"
    LOCAL_ID_HASH_KEY = "local_id_hash_key"

    POPULATION_SIZE = "population_size"

    ACCENT_TRANSLITERATIONS = "accent_transliterations"
    FORENAME_CACHE_FILENAME = "forename_cache_filename"
    FORENAME_SEX_FREQ_CSV = "forename_sex_freq_csv"
    MIN_NAME_FREQUENCY = "min_name_frequency"
    NONSPECIFIC_NAME_COMPONENTS = "nonspecific_name_components"
    SURNAME_CACHE_FILENAME = "surname_cache_filename"
    SURNAME_FREQ_CSV = "surname_freq_csv"

    BIRTH_YEAR_PSEUDO_RANGE = "birth_year_pseudo_range"

    P_NOT_MALE_OR_FEMALE = "p_not_male_or_female"
    P_FEMALE_GIVEN_MALE_OR_FEMALE = "p_female_given_male_or_female"

    POSTCODE_CACHE_FILENAME = "postcode_cache_filename"
    POSTCODE_CSV_FILENAME = "postcode_csv_filename"
    MEAN_OA_POPULATION = "mean_oa_population"
    P_UNKNOWN_OR_PSEUDO_POSTCODE = "p_unknown_or_pseudo_postcode"

    P_EP1_FORENAME = "p_ep1_forename"
    P_EP2NP1_FORENAME = "p_ep2np1_forename"
    P_EN_FORENAME = "p_en_forename"
    P_U_FORENAME = "p_u_forename"

    P_EP1_SURNAME = "p_ep1_surname"
    P_EP2NP1_SURNAME = "p_ep2np1_surname"
    P_EN_SURNAME = "p_en_surname"

    P_EP_DOB = "p_ep_dob"
    P_EN_DOB = "p_en_dob"

    P_E_GENDER = "p_e_gender"

    P_EP_POSTCODE = "p_ep_postcode"
    P_EN_POSTCODE = "p_en_postcode"

    MIN_LOG_ODDS_FOR_MATCH = "min_log_odds_for_match"
    EXCEEDS_NEXT_BEST_LOG_ODDS = "exceeds_next_best_log_odds"
    PERFECT_ID_TRANSLATION = "perfect_id_translation"


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
            N_PROCESSES = 1  # usually faster!
        else:
            N_PROCESSES = cpu_count()

    # Caches
    FORENAME_CACHE_FILENAME = os.path.join(
        DEFAULT_CACHE_DIR, "fuzzy_forename_cache.jsonl"
    )
    POSTCODE_CACHE_FILENAME = os.path.join(
        DEFAULT_CACHE_DIR, "fuzzy_postcode_cache.json"
    )
    SURNAME_CACHE_FILENAME = os.path.join(
        DEFAULT_CACHE_DIR, "fuzzy_surname_cache.jsonl"
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
    P_EP1_FORENAME = {
        GENDER_FEMALE: 0.00894,  # (E)
        GENDER_MALE: 0.00840,  # (E)
    }
    P_EP2NP1_FORENAME = {
        GENDER_FEMALE: 0.00881,  # (E)
        GENDER_MALE: 0.00688,  # (E)
    }
    P_EN_FORENAME = {
        GENDER_FEMALE: 0.00572,  # (E)
        GENDER_MALE: 0.00625,  # (E)
    }

    P_U_FORENAME = 0.00191  # (E)

    P_EP1_SURNAME = {
        GENDER_FEMALE: 0.00551,  # (E)
        GENDER_MALE: 0.00471,  # (E)
    }
    P_EP2NP1_SURNAME = {
        GENDER_FEMALE: 0.00378,  # (E)
        GENDER_MALE: 0.00247,  # (E)
    }
    P_EN_SURNAME = {
        GENDER_FEMALE: 0.0567,  # (E)
        GENDER_MALE: 0.0134,  # (E)
    }

    _P_E_DOB = 0.00492  # DOB not full match (E)
    _P_EP_DOB_GIVEN_P_E_DOB = 0.933  # P(partial | not full); (E)
    P_EP_DOB = _P_E_DOB * _P_EP_DOB_GIVEN_P_E_DOB  # (E)
    P_EN_DOB_TRUE = _P_E_DOB * (1 - _P_EP_DOB_GIVEN_P_E_DOB)  # (E) (*)
    P_EN_DOB = 0  # Much faster (*)

    P_E_GENDER = 0.0033  # (E)

    P_EP_POSTCODE = 0.0097  # (E)
    P_EN_POSTCODE = 0.300  # (E)

    # -------------------------------------------------------------------------
    # Matching process
    # -------------------------------------------------------------------------
    MIN_LOG_ODDS_FOR_MATCH = 5  # theta, in the validation paper
    EXCEEDS_NEXT_BEST_LOG_ODDS = 10  # delta, in the validation paper
    PERFECT_ID_TRANSLATION = ""
    REPORT_EVERY = 100  # cosmetic only

    # -------------------------------------------------------------------------
    # Name handling
    # -------------------------------------------------------------------------

    NONSPECIFIC_NAME_COMPONENTS = set(
        # Includes nobiliary particles:
        # https://en.wikipedia.org/wiki/Nobiliary_particle. Typically "of", "of
        # the". See also
        # https://en.wikipedia.org/wiki/List_of_family_name_affixes;
        # https://en.wikipedia.org/wiki/Suffix_(name).
        x.upper()
        for x in (
            # Arabic-speaking countries
            "Al",
            "El",
            # Belgian
            "de",
            "der",
            "van",
            # Danish
            "af",
            # Dutch
            "tot",
            "thoe",
            "van",
            # English, Welsh, Scottish
            "of",
            # French
            "d",  # e.g. Giscard d'Estaing
            "de",
            "des",
            "du",
            "l",  # e.g. L'Estrange
            "la",
            "le",
            # German
            "auf",
            "von",
            "zu",
            # Italian
            "da",
            "dai",
            "dal",
            "dalla",
            "dei",
            "del",
            "dell",
            "della",
            "di",
            # Portuguese,
            "da",
            "das",
            "do",
            "dos",
            # Somali
            "Aw",
            # Spanish
            "de",
            # Swedish
            "af",
            "av",
            "von",
            # Swiss
            "de",
            "von",
            # Thai
            "na",
            "Phra",
            "Sri",
            # USA: seniority
            "Jnr",
            "Jr",
            "Snr",
            "Sr",
            # USA: numbering
            "I",
            "II",
            "III",
            "IV",
            "V",
            "VI",
            "VII",
            "VIII",
            "IX",
            "X",
        )
    )
    ACCENT_TRANSLITERATIONS = [
        # Only upper-case versions are required.
        # German: https://en.wikipedia.org/wiki/German_orthography
        ("Ä", "AE"),
        ("Ö", "OE"),
        ("Ü", "UE"),
        (ESZETT_UPPER_CASE, "SS"),
    ]

    # -------------------------------------------------------------------------
    # Derived
    # -------------------------------------------------------------------------

    MIN_P_FOR_MATCH = probability_from_log_odds(MIN_LOG_ODDS_FOR_MATCH)

    P_EP1_FORENAME_CSV = _mk_dictstr(P_EP1_FORENAME)
    P_EP2NP1_FORENAME_CSV = _mk_dictstr(P_EP2NP1_FORENAME)
    P_EN_FORENAME_CSV = _mk_dictstr(P_EN_FORENAME)

    P_EP1_SURNAME_CSV = _mk_dictstr(P_EP1_SURNAME)
    P_EP2NP1_SURNAME_CSV = _mk_dictstr(P_EP2NP1_SURNAME)
    P_EN_SURNAME_CSV = _mk_dictstr(P_EN_SURNAME)

    NONSPECIFIC_NAME_COMPONENTS_CSV = ",".join(
        sorted(NONSPECIFIC_NAME_COMPONENTS)
    )
    ACCENT_TRANSLITERATIONS_SLASH_CSV = ",".join(
        f"{accent}/{plain}" for accent, plain in ACCENT_TRANSLITERATIONS
    )
    ACCENT_TRANSLITERATIONS_TRANS = str.maketrans(
        {accent: plain for accent, plain in ACCENT_TRANSLITERATIONS}
    )
