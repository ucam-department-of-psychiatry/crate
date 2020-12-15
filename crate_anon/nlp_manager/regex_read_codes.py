#!/usr/bin/env python

"""
crate_anon/nlp_manager/regex_read_codes.py

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

**Regular expressions to detect some Read codes (CTV3).**

See https://en.wikipedia.org/wiki/Read_code.

"""

import logging
from typing import List
import unittest

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger

from crate_anon.common.regex_helpers import (
    at_start_wb,
    escape_literal_string_for_regex,
    escape_literal_for_regex_allowing_flexible_whitespace,
    LEFT_BRACKET as LB,
    OPTIONAL_WHITESPACE,
    regex_or,
    RIGHT_BRACKET as RB,
)

log = logging.getLogger(__name__)


# =============================================================================
# Represent a Read code
# =============================================================================

class ReadCode(object):
    r"""
    Represents information about the way a quantity is represented as a Read
    code.

    NOTE: Read codes are case-sensitive. (See
    https://www.gp-training.net/it/read-codes/.)

    It would be desirable to mark the Read code as case-sensitive, within a
    regex that is case-insensitive overall. Apparently Tcl supports this via
    the ``(?c)`` flag: https://www.regular-expressions.info/modifiers.html.

    However, others just support the "locally case-insensitive" flag, ``(?i)``.

    Python (via ``regex``) fails to parse the test regex ``(?i)te(?-i)st``,
    from https://www.regular-expressions.info/modifiers.html. It gives the
    error ``regex._regex_core.error: bad inline flags: cannot turn flags off at
    position 11``. No docs at https://pypi.org/project/regex/ or
    https://docs.python.org/3/library/re.html suggest otherwise.

    Since we absolutely want case-insensitive matching for the most part, I
    think we'll live with this limitation.
    """
    def __init__(self,
                 read_code: str,
                 phrases: List[str] = None) -> None:
        """
        Args:
            read_code:
                The Read (CTV3) code, a string of length 5.
            phrases:
                The associated possible phrases.
        """
        assert isinstance(read_code, str)
        assert len(read_code) == 5
        self.read_code = read_code
        self.phrases = phrases or []  # type: List[str]

    def component_regex_strings(self) -> List[str]:
        """
        A list of regular expression strings representing this quantity.

        Provides regexes for:

        .. code-block:: none

            phrase (readcode)
            phrase
        """
        components = []  # type: List[str]
        esc_read = escape_literal_string_for_regex(self.read_code)
        optional_observation = r"(?:\s* - \s+ observation)?"
        for p in self.phrases:
            phrase = at_start_wb(
                escape_literal_for_regex_allowing_flexible_whitespace(p)
            )
            r = (
                f"{phrase}{optional_observation}"
                f"(?:{OPTIONAL_WHITESPACE}{LB}{esc_read}{RB})?"
            )
            components.append(r)
        return components

    def regex_str(self) -> str:
        """
        A single composite regex string representing this quantity.
        """
        return regex_or(
            *self.component_regex_strings(),
            wrap_each_in_noncapture_group=True,
            wrap_result_in_noncapture_group=True
        )


# =============================================================================
# Some known values used by our NLP parsers
# =============================================================================

class ReadCodes(object):
    """
    Some known Read codes.

    From ``v3ReadCode_PBCL.xlsx``.
    """

    # -------------------------------------------------------------------------
    # Biochemistry
    # -------------------------------------------------------------------------

    ALBUMIN_PLASMA = ReadCode(
        read_code="XaIRc",
        phrases=["Plasma albumin level"]
    )
    ALBUMIN_SERUM = ReadCode(
        read_code="XE2eA",
        phrases=["Serum albumin level"]
    )
    ALKPHOS = ReadCode(
        read_code="44F3.",
        phrases=["Alkaline phosphatase level"]
    )
    ALKPHOS_PLASMA = ReadCode(
        read_code="XaIRj",
        phrases=["Plasma alkaline phosphatase level"]
    )
    ALKPHOS_SERUM = ReadCode(
        read_code="XE2px",
        phrases=["Serum alkaline phosphatase level"]
    )
    ALT = ReadCode(
        read_code="44G3.",
        phrases=["ALT/SGPT serum level"]
    )

    BILIRUBIN_PLASMA_TOTAL = ReadCode(
        read_code="XaETf",
        phrases=["Plasma total bilirubin level"]
    )
    BILIRUBIN_SERUM = ReadCode(
        read_code="44E..",
        phrases=["Serum bilirubin level"]
    )
    BILIRUBIN_SERUM_TOTAL = ReadCode(
        read_code="XaERu",
        phrases=["Serum total bilirubin level"]
    )
    BILIRUBIN_TOTAL = ReadCode(
        read_code="XE2qu",
        phrases=["Total bilirubin level"]
    )

    CHOLESTEROL_SERUM = ReadCode(
        read_code="XE2eD",
        phrases=["Serum cholesterol level"]
    )
    CHOLESTEROL_TOTAL_PLASMA = ReadCode(
        read_code="XaIRd",
        phrases=["Plasma total cholesterol level"]
    )
    CHOLESTEROL_TOTAL_SERUM = ReadCode(
        read_code="XaJe9",
        phrases=["Serum total cholesterol level"]
    )
    CREATININE = ReadCode(
        read_code="X771Q",
        phrases=["Creatinine level"]
    )
    CREATININE_PLASMA = ReadCode(
        read_code="XaETQ",
        phrases=["Plasma creatinine level"]
    )
    CREATININE_PLASMA_CORRECTED = ReadCode(
        read_code="XaERX",
        phrases=["Cor plasma creatinine level"]
    )
    CREATININE_SERUM = ReadCode(
        read_code="XE2q5",
        phrases=["Serum creatinine level"]
    )
    CREATININE_SERUM_CORRECTED = ReadCode(
        read_code="XaERc",
        phrases=["Cor serum creatinine level"]
    )
    CRP_PLASMA = ReadCode(
        read_code="XE2dy",
        phrases=["Plasma C-reactive protein level"]
    )
    CRP_SERUM = ReadCode(
        read_code="XaINL",
        phrases=["Serum C reactive protein level"]
    )

    GAMMA_GT = ReadCode(
        read_code="44G4.",
        phrases=["Gamma-glutamyl transferase lev"]
    )
    GAMMA_GT_PLASMA = ReadCode(
        read_code="XaES4",
        phrases=["Plasma gamma-glutamyl transferase level"]
    )
    GAMMA_GT_SERUM = ReadCode(
        read_code="XaES3",
        phrases=["Serum gamma-glutamyl transferase level"]
    )
    GLUCOSE = ReadCode(
        read_code="X772y",
        phrases=["Glucose level"]
    )
    GLUCOSE_BLOOD = ReadCode(
        read_code="X772z",
        phrases=["Blood glucose level"]
    )
    GLUCOSE_BLOOD_2H_POSTPRANDIAL = ReadCode(
        read_code="44U7.",
        phrases=["2 hour post-prand blood gluc"]
    )
    GLUCOSE_BLOOD_150_MIN = ReadCode(
        read_code="XaEOS",
        phrases=["150 minute blood glucose level"]
    )
    GLUCOSE_PLASMA_RANDOM = ReadCode(
        read_code="44g0.",
        phrases=["Plasma random glucose level"]
    )
    GLUCOSE_PLASMA_FASTING = ReadCode(
        read_code="44g1.",
        phrases=["Plasma fasting glucose level"]
    )
    GLUCOSE_PLASMA_30_MIN = ReadCode(
        read_code="XaEOT",
        phrases=["30 minute plasma glucose level"]
    )
    GLUCOSE_PLASMA_60_MIN = ReadCode(
        read_code="XaEOU",
        phrases=["60 minute plasma glucose level"]
    )
    GLUCOSE_PLASMA_90_MIN = ReadCode(
        read_code="XaEPc",
        phrases=["90 minute plasma glucose level"]
    )
    GLUCOSE_PLASMA_120_MIN = ReadCode(
        read_code="XaEOV",
        phrases=["120 minute plasma glucose level"]
    )
    GLUCOSE_PLASMA_2H_POSTPRANDIAL = ReadCode(
        read_code="44g2.",
        phrases=["Plasma 2-hr post-pran gluc lev"]
    )
    GLUCOSE_PLASMA_150_MIN = ReadCode(
        read_code="XaEOW",
        phrases=["150 min plasma glucose level"]
    )
    GLUCOSE_SERUM = ReadCode(
        read_code="44f..",
        phrases=["Serum glucose level"]
    )
    GLUCOSE_SERUM_RANDOM = ReadCode(
        read_code="44f0.",
        phrases=["Serum random glucose level"]
    )
    GLUCOSE_SERUM_FASTING = ReadCode(
        read_code="44f1.",
        phrases=["Serum fasting glucose level"]
    )
    GLUCOSE_SERUM_30_MIN = ReadCode(
        read_code="XaEOX",
        phrases=["30 minute serum glucose level"]
    )
    GLUCOSE_SERUM_60_MIN = ReadCode(
        read_code="XaEOY",
        phrases=["60 minute serum glucose level"]
    )
    GLUCOSE_SERUM_90_MIN = ReadCode(
        read_code="XaEPd",
        phrases=["90 minute serum glucose level"]
    )
    GLUCOSE_SERUM_120_MIN = ReadCode(
        read_code="XaEOZ",
        phrases=["120 minute serum glucose level"]
    )
    GLUCOSE_SERUM_2H_POSTPRANDIAL = ReadCode(
        read_code="44f2.",
        phrases=["Serum 2-hr post-prand gluc lev"]
    )
    GLUCOSE_SERUM_150_MIN = ReadCode(
        read_code="XaERQ",
        phrases=["150 minute serum glucose level"]
    )

    HBA1C = ReadCode(
        read_code="X772q",
        phrases=["Haemoglobin A1c level"]
    )
    HBA1C_DCCT = ReadCode(
        read_code="XaERp",
        phrases=["HbA1c level (DCCT aligned)"]
    )
    HBA1C_IFCC = ReadCode(
        read_code="XaPbt",
        phrases=["HbA1c levl - IFCC standardised"]
    )
    HDL_PLASMA = ReadCode(
        read_code="XaEVr",
        phrases=["Plasma HDL cholesterol level"]
    )
    HDL_PLASMA_RANDOM = ReadCode(
        read_code="44d2.",
        phrases=["Plasma rndm HDL cholest level"]
    )
    HDL_PLASMA_FASTING = ReadCode(
        read_code="44d3.",
        phrases=["Plasma fast HDL cholest level"]
    )
    HDL_SERUM = ReadCode(
        read_code="44P5.",
        phrases=["Serum HDL cholesterol level"]
    )
    HDL_SERUM_FASTING = ReadCode(
        read_code="44PB.",
        phrases=["Serum fast HDL cholesterol lev"]
    )
    HDL_SERUM_RANDOM = ReadCode(
        read_code="44PC.",
        phrases=["Ser random HDL cholesterol lev"]
    )

    LITHIUM_SERUM = ReadCode(
        read_code="XE25g",
        phrases=["Serum lithium level"]
    )
    LDL_PLASMA = ReadCode(
        read_code="XaEVs",
        phrases=["Plasma LDL cholesterol level"]
    )
    LDL_PLASMA_RANDOM = ReadCode(
        read_code="44d4.",
        phrases=["Plasma rndm LDL cholest level"]
    )
    LDL_PLASMA_FASTING = ReadCode(
        read_code="44d5.",
        phrases=["Plasma fast LDL cholest level"]
    )
    LDL_SERUM = ReadCode(
        read_code="44P6.",
        phrases=["Serum LDL cholesterol level"]
    )
    LDL_SERUM_FASTING = ReadCode(
        read_code="44PD.",
        phrases=["Serum fast LDL cholesterol lev"]
    )
    LDL_SERUM_RANDOM = ReadCode(
        read_code="44PE.",
        phrases=["Ser random LDL cholesterol lev"]
    )

    POTASSIUM = ReadCode(
        read_code="X771S",
        phrases=["Potassium level"]
    )
    POTASSIUM_BLOOD = ReadCode(
        read_code="XaDvZ",
        phrases=["Blood potassium level"]
    )
    POTASSIUM_PLASMA = ReadCode(
        read_code="XaIRl",
        phrases=["Plasma potassium level"]
    )
    POTASSIUM_SERUM = ReadCode(
        read_code="XE2pz",
        phrases=["Serum potassium level"]
    )

    TG = ReadCode(
        read_code="X772O",
        phrases=["Triglyceride level"]
    )
    TG_PLASMA = ReadCode(
        read_code="44e..",
        phrases=["Plasma triglyceride level"]
    )
    TG_PLASMA_RANDOM = ReadCode(
        read_code="44e0.",
        phrases=["Plasma rndm triglyceride level"]
    )
    TG_PLASMA_FASTING = ReadCode(
        read_code="44e1.",
        phrases=["Plasma fast triglyceride level"]
    )
    TG_SERUM = ReadCode(
        read_code="XE2q9",
        phrases=["Serum triglyceride levels"]
    )
    TG_SERUM_FASTING = ReadCode(
        read_code="44Q4.",
        phrases=["Serum fasting triglyceride lev"]
    )
    TG_SERUM_RANDOM = ReadCode(
        read_code="44Q5.",
        phrases=["Serum random triglyceride lev"]
    )
    TSH_PLASMA = ReadCode(
        read_code="XaELW",
        phrases=["Plasma TSH level"]
    )
    TSH_PLASMA_30_MIN = ReadCode(
        read_code="XaET7",
        phrases=["30 minute plasma TSH level"]
    )
    TSH_PLASMA_60_MIN = ReadCode(
        read_code="XaESa",
        phrases=["60 minute plasma TSH level"]
    )
    TSH_PLASMA_90_MIN = ReadCode(
        read_code="XaET2",
        phrases=["90 minute plasma TSH level"]
    )
    TSH_PLASMA_120_MIN = ReadCode(
        read_code="XaESb",
        phrases=["120 minute plasma TSH level"]
    )
    TSH_PLASMA_150_MIN = ReadCode(
        read_code="XaESc",
        phrases=["150 minute plasma TSH level"]
    )
    TSH_SERUM = ReadCode(
        read_code="XaELV",
        phrases=["Serum TSH level"]
    )
    TSH_SERUM_60_MIN = ReadCode(
        read_code="XaESX",
        phrases=["60 minute serum TSH level"]
    )
    TSH_SERUM_90_MIN = ReadCode(
        read_code="XaESY",
        phrases=["90 minute serum TSH level"]
    )
    TSH_SERUM_120_MIN = ReadCode(
        read_code="XaET1",
        phrases=["120 minute serum TSH level"]
    )
    TSH_SERUM_150_MIN = ReadCode(
        read_code="XaESZ",
        phrases=["150 minute serum TSH level"]
    )

    SODIUM = ReadCode(
        read_code="X771T",
        phrases=["Sodium level"]
    )
    SODIUM_BLOOD = ReadCode(
        read_code="XaDva",
        phrases=["Blood sodium level"]
    )
    SODIUM_PLASMA = ReadCode(
        read_code="XaIRf",
        phrases=["Plasma sodium level"]
    )
    SODIUM_SERUM = ReadCode(
        read_code="XE2q0",
        phrases=["Serum sodium level"]
    )

    UREA_BLOOD = ReadCode(
        read_code="X771P",
        phrases=["Blood urea"]
    )
    UREA_PLASMA = ReadCode(
        read_code="XaDvl",
        phrases=["Plasma urea level"]
    )
    UREA_SERUM = ReadCode(
        read_code="XM0lt",
        phrases=["Serum urea level"]
    )

    # -------------------------------------------------------------------------
    # Haematology
    # -------------------------------------------------------------------------

    BASOPHIL_COUNT = ReadCode(
        read_code="42L..",
        phrases=["Basophil count"]
    )

    EOSINOPHIL_COUNT = ReadCode(
        read_code="42K..",
        phrases=["Eosinophil count"]
    )
    ESR = ReadCode(
        read_code="XE2m7",
        phrases=["Erythrocyte sedimentation rate"]
    )

    HAEMATOCRIT = ReadCode(
        read_code="X76tb",
        phrases=["Haematocrit"]
    )
    HAEMOGLOBIN_CONCENTRATION = ReadCode(
        read_code="Xa96v",
        phrases=["Haemoglobin concentration"]
    )

    LYMPHOCYTE_COUNT = ReadCode(
        read_code="42M..",
        phrases=["Lymphocyte count"]
    )

    MONOCYTE_COUNT = ReadCode(
        read_code="42N..",
        phrases=["Monocyte count"]
    )

    NEUTROPHIL_COUNT = ReadCode(
        read_code="42J..",
        phrases=["Neutrophil count"]
    )

    PLATELET_COUNT = ReadCode(
        read_code="42P..",
        phrases=["Platelet count"]
    )
    POLYMORPH_COUNT = ReadCode(  # = neutrophils
        read_code="XaIao",
        phrases=["Polymorph count"]
    )

    RBC_COUNT = ReadCode(
        read_code="426..",
        phrases=["Red blood cell count"]
    )

    WBC_COUNT = ReadCode(
        read_code="XaIdY",
        phrases=["Total white blood count"]
    )


# =============================================================================
# Combiner function
# =============================================================================

def regex_components_from_read_codes(*read_codes: ReadCode) -> List[str]:
    """
    Returns all components from the specified Read code objects.
    """
    code_strings = []  # type: List[str]
    for rc in read_codes:
        code_strings += rc.component_regex_strings()
    return code_strings


def any_read_code_of(*read_codes: ReadCode) -> str:
    """
    Returns a regex allowing any of the specified Read codes.
    """
    code_strings = regex_components_from_read_codes(*read_codes)
    return regex_or(
        *code_strings,
        wrap_each_in_noncapture_group=True,
        wrap_result_in_noncapture_group=True
    )


# =============================================================================
# Unit tests
# =============================================================================

class TestReadCodeRegexes(unittest.TestCase):
    def test_read_code_regexes(self) -> None:
        spacer = "    "
        for name, rc in ReadCodes.__dict__.items():
            if name.startswith("_"):
                continue
            assert isinstance(rc, ReadCode)
            phrases = "\n".join(
                f"{spacer}{x}" for x in rc.phrases
            )
            regexes = "\n".join(
                f"{spacer}{x}" for x in rc.component_regex_strings()
            )
            regex_str = rc.regex_str()
            log.info(f"Name: {name!r}.\n"
                     f"- Read code:\n{spacer}{rc.read_code}\n"
                     f"- Phrases:\n{phrases}\n"
                     f"- Regular expressions:\n{regexes}\n"
                     f"- Single regex string:\n{spacer}{regex_str}")
        log.warning("No testing performed; just printed.")


if __name__ == '__main__':
    main_only_quicksetup_rootlogger(level=logging.DEBUG)
    unittest.main()
