#!/usr/bin/env python

"""
crate_anon/nlp_manager/tests/regex_units_tests.py

===============================================================================

    Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).

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

Unit tests.

"""

import unittest

from crate_anon.nlp_manager.regex_units import (
    # ---------------------------------------------------------------------
    # Relationships
    # ---------------------------------------------------------------------

    out_of,
    per,

    # ---------------------------------------------------------------------
    # Distance
    # ---------------------------------------------------------------------

    CM,
    FEET,
    INCHES,
    M,
    MM,

    # ---------------------------------------------------------------------
    # Mass
    # ---------------------------------------------------------------------

    G,
    KG,
    LB,
    MCG,
    MG,
    STONES,

    # ---------------------------------------------------------------------
    # Volume
    # ---------------------------------------------------------------------

    CUBIC_MM,
    CUBIC_MM_OR_MICROLITRE,
    DL,
    FEMTOLITRE,
    L,
    MICROLITRE,
    ML,

    # ---------------------------------------------------------------------
    # Reciprocal volume
    # ---------------------------------------------------------------------

    PER_CUBIC_MM,

    # ---------------------------------------------------------------------
    # Time
    # ---------------------------------------------------------------------

    HOUR,

    # ---------------------------------------------------------------------
    # Proportion
    # ---------------------------------------------------------------------

    PERCENT,

    # -------------------------------------------------------------------------
    # Arbitrary count things
    # -------------------------------------------------------------------------

    CELLS,
    MICROUNITS,
    MILLIUNITS,
    SCORE,
    UNITS,

    # -------------------------------------------------------------------------
    # Moles
    # -------------------------------------------------------------------------

    MICROEQ,
    MICROMOLES,
    MILLIEQ,
    MILLIMOLES,
    MOLES,

    # -------------------------------------------------------------------------
    # Concentration (molarity)
    # -------------------------------------------------------------------------

    MILLIMOLAR,
    MILLIMOLES_PER_L,
    MICROEQ_PER_L,
    MICROMOLAR,
    MICROMOLES_PER_L,
    MILLIEQ_PER_L,

    # -------------------------------------------------------------------------
    # Concentration (mass)
    # -------------------------------------------------------------------------

    G_PER_DL,
    G_PER_L,
    MG_PER_DL,
    MG_PER_L,

    # -------------------------------------------------------------------------
    # Concentration (arbitrary count and dimensionless things)
    # -------------------------------------------------------------------------

    BILLION_PER_L,
    CELLS_PER_CUBIC_MM,
    CELLS_PER_CUBIC_MM_OR_MICROLITRE,
    L_PER_L,
    MICROUNITS_PER_ML,
    MILLIMOLES_PER_MOL,
    MILLIUNITS_PER_L,
    TRILLION_PER_L,
    UNITS_PER_L,

    # -------------------------------------------------------------------------
    # Speed
    # -------------------------------------------------------------------------

    MM_PER_H,

    # -------------------------------------------------------------------------
    # Pressure
    # -------------------------------------------------------------------------

    MM_HG,

    # -------------------------------------------------------------------------
    # Area and related
    # -------------------------------------------------------------------------

    SQ_M,
    KG_PER_SQ_M,
)
from crate_anon.nlp_manager.tests.regex_test_helperfunc import (
    assert_text_regex,
)


# =============================================================================
# Unit tests
# =============================================================================

class TestUnitRegexes(unittest.TestCase):

    @staticmethod
    def test_unit_regexes() -> None:
        """
        Test all "unit" regexes.
        """
        verbose = True

        # ---------------------------------------------------------------------
        # Relationships
        # ---------------------------------------------------------------------

        assert_text_regex("out_of(5)", out_of(5), [
            ("4 out of 5", ["out of 5"]),
            ("4/5", ["/5"]),
            ("4 / 5", ["/ 5"]),
        ], verbose=verbose)
        assert_text_regex("per(n, d)", per("n", "d"), [
            ("blah n per d blah", ["n per d"]),
            ("blah n/d blah", ["n/d"]),
            ("n / d", ["n / d"]),
            ("n d -1", ["n d -1"]),
            ("n d -1", ["n d -1"]),
            ("n blah d", []),
        ], verbose=verbose)
        assert_text_regex(
            "per(n, d, numerator_optional=True)",
            per("n", "d", numerator_optional=True),
            [
                ("blah n per d blah", ["n per d"]),
                ("blah n/d blah", ["n/d"]),
                ("n / d", ["n / d"]),
                ("n d -1", ["n d -1"]),
                ("n d -1", ["n d -1"]),
                ("n blah d", []),
                ("/ d", ["/ d"]),
                (" / d", ["/ d"]),
                (" per d", ["per d"]),
            ],
            verbose=verbose
        )

        # ---------------------------------------------------------------------
        # Distance
        # ---------------------------------------------------------------------

        assert_text_regex("CM", CM, [
            ("5 centimetres long", ["centimetres"]),
            ("5 centimeters long", ["centimeters"]),
            ("5cm long", ["cm"]),
        ], verbose=verbose)
        assert_text_regex("FEET", FEET, [
            ("5 feet long", ["feet"]),
            ("5 foot long", ["foot"]),
            ("5' long", ["'"]),  # ASCII apostrophe
            ("5’ long", ["’"]),  # right single quote (U+2019)
            ("5′ long", ["′"]),  # prime (U+2032)
        ], verbose=verbose)
        assert_text_regex("INCHES", INCHES, [
            ("5 inches long", ["inches"]),
            ("5 in long", ["in"]),
            ('5" long', ['"']),  # ASCII double quote
            ("5” long", ["”"]),  # right double quote (U+2014)
            ("5″ long", ["″"]),  # double prime (U+2033)
        ], verbose=verbose)
        assert_text_regex("M", M, [
            ("5 metres long", ["metres"]),
            ("5 meters long", ["meters"]),
            ("5m long", ["m"]),
        ], verbose=verbose)
        assert_text_regex("MM", MM, [
            ("5 millimetres long", ["millimetres"]),
            ("5 millimeters long", ["millimeters"]),
            ("5mm long", ["mm"]),
        ], verbose=verbose)

        # ---------------------------------------------------------------------
        # Mass
        # ---------------------------------------------------------------------

        assert_text_regex("G", G, [
            ("5 grams", ["grams"]),
            ("5 g", ["g"]),
        ], verbose=verbose)
        assert_text_regex("KG", KG, [
            ("5 kilograms", ["kilograms"]),
            ("5 kg", ["kg"]),
        ], verbose=verbose)
        assert_text_regex("LB", LB, [
            ("5 pounds", ["pounds"]),
            ("5 lb", ["lb"]),
        ], verbose=verbose)
        assert_text_regex("MCG", MCG, [
            ("5 micrograms", ["micrograms"]),
            ("5 mcg", ["mcg"]),
            ("5 ug", ["ug"]),
            ("5 μg", ["μg"]),
        ], verbose=verbose)
        assert_text_regex("MG", MG, [
            ("5 milligrams", ["milligrams"]),
            ("5 mg", ["mg"]),
        ], verbose=verbose)
        assert_text_regex("STONES", STONES, [
            ("5 stones", ["stones"]),
            ("5 stone", ["stone"]),
            ("5 st", ["st"]),
        ], verbose=verbose)

        # ---------------------------------------------------------------------
        # Volume
        # ---------------------------------------------------------------------

        assert_text_regex("CUBIC_MM", CUBIC_MM, [
            ("mm3", ["mm3"]),
            ("blibble", []),
            ("5 mm^3", ["mm^3"]),
            ("5 cubic mm", ["cubic mm"]),
            ("5 cubic millimetres", ["cubic millimetres"]),
        ], verbose=verbose)
        assert_text_regex("CUBIC_MM_OR_MICROLITRE", CUBIC_MM_OR_MICROLITRE, [
            ("5 mm^3", ["mm^3"]),
            ("5 cubic mm", ["cubic mm"]),
            ("5 cubic millimetres", ["cubic millimetres"]),
            ("5 microlitre", ["microlitre"]),
            ("5 microL", ["microL"]),
            ("5 microliters", ["microliters"]),
            ("5 μL", ["μL"]),
            ("5 ul", ["ul"]),
        ], verbose=verbose)
        assert_text_regex("DL", DL, [
            ("5 decilitres", ["decilitres"]),
            ("5 deciliters", ["deciliters"]),
            ("5 dl", ["dl"]),
            ("5 dL", ["dL"]),
        ], verbose=verbose)
        assert_text_regex("FEMTOLITRE", FEMTOLITRE, [
            ("5 femtolitres", ["femtolitres"]),
            ("5 femtoliters", ["femtoliters"]),
            ("5 fl", ["fl"]),
            ("5 fL", ["fL"]),
        ], verbose=verbose)
        assert_text_regex("L", L, [
            ("5 litres", ["litres"]),
            ("5 liters", ["liters"]),
            ("5 l", ["l"]),
            ("5 L", ["L"]),
        ], verbose=verbose)
        assert_text_regex("MICROLITRE", MICROLITRE, [
            ("5 microlitre", ["microlitre"]),
            ("5 microL", ["microL"]),
            ("5 microliters", ["microliters"]),
            ("5 μL", ["μL"]),
            ("5 ul", ["ul"]),
        ], verbose=verbose)
        assert_text_regex("ML", ML, [
            ("5 millilitres", ["millilitres"]),
            ("5 milliliters", ["milliliters"]),
            ("5 ml", ["ml"]),
            ("5 mL", ["mL"]),
        ], verbose=verbose)

        # ---------------------------------------------------------------------
        # Reciprocal volume
        # ---------------------------------------------------------------------

        assert_text_regex("PER_CUBIC_MM", PER_CUBIC_MM, [
            ("per cubic mm", ["per cubic mm"]),
            ("5/mm^3", ["/mm^3"]),
            ("5 per cubic mm", ["per cubic mm"]),
            ("5 per cubic millimetres", ["per cubic millimetres"]),
        ], verbose=verbose)

        # ---------------------------------------------------------------------
        # Time
        # ---------------------------------------------------------------------

        assert_text_regex("HOUR", HOUR, [
            ("5 hours", ["hours"]),
            ("5 hr", ["hr"]),
            ("5 h", ["h"]),
        ], verbose=verbose)

        # ---------------------------------------------------------------------
        # Proportion
        # ---------------------------------------------------------------------

        assert_text_regex("PERCENT", PERCENT, [
            ("5 percent", ["percent"]),
            ("5 per cent", ["per cent"]),
            ("5 pct", ["pct"]),
            ("5%", ["%"]),
        ], verbose=verbose)

        # ---------------------------------------------------------------------
        # Arbitrary count things
        # ---------------------------------------------------------------------

        assert_text_regex("CELLS", CELLS, [
            ("cells", ["cells"]),
            ("blibble", []),
            ("5 cells", ["cells"]),
            ("5 cell", ["cell"]),
        ], verbose=verbose)
        assert_text_regex("MICROUNITS", MICROUNITS, [
            ("5 uU", ["uU"]),
            ("5 μU", ["μU"]),
            ("5 uIU", ["uIU"]),
            ("5 μIU", ["μIU"]),
        ], verbose=verbose)
        assert_text_regex("MILLIUNITS", MILLIUNITS, [
            ("5 mU", ["mU"]),
            ("5 mIU", ["mIU"]),
        ], verbose=verbose)
        assert_text_regex("SCORE", SCORE, [
            ("I scored 5", ["scored"]),
            ("MMSE score 5", ["score"]),
        ], verbose=verbose)
        assert_text_regex("UNITS", UNITS, [
            ("5 U", ["U"]),
            ("5 IU", ["IU"]),
        ], verbose=verbose)

        # ---------------------------------------------------------------------
        # Moles
        # ---------------------------------------------------------------------

        assert_text_regex("MICROEQ", MICROEQ, [
            ("5 μEq", ["μEq"]),
            ("5 uEq", ["uEq"]),
        ], verbose=verbose)
        assert_text_regex("MICROMOLES", MICROMOLES, [
            ("5 micromoles", ["micromoles"]),
            ("5 micromol", ["micromol"]),
            ("5 umol", ["umol"]),
            ("5 μmol", ["μmol"]),
        ], verbose=verbose)
        assert_text_regex("MILLIEQ", MILLIEQ, [
            ("5 mEq", ["mEq"]),
        ], verbose=verbose)
        assert_text_regex("MILLIMOLES", MILLIMOLES, [
            ("5 millimoles", ["millimoles"]),
            ("5 millimol", ["millimol"]),
            ("5 mmol", ["mmol"]),
        ], verbose=verbose)
        assert_text_regex("MOLES", MOLES, [
            ("5 moles", ["moles"]),
            ("5 mol", ["mol"]),
        ], verbose=verbose)

        # -------------------------------------------------------------------------
        # Concentration (molarity)
        # -------------------------------------------------------------------------

        assert_text_regex("MILLIMOLAR", MILLIMOLAR, [
            ("5 mM", ["mM"]),
        ], verbose=verbose)
        assert_text_regex("MILLIMOLES_PER_L", MILLIMOLES_PER_L, [
            ("5 mmol/L", ["mmol/L"]),
            ("5 millimoles per litre", ["millimoles per litre"]),
        ], verbose=verbose)
        assert_text_regex("MICROEQ_PER_L", MICROEQ_PER_L, [
            ("5 μEq/L", ["μEq/L"]),
            ("5 microequivalents per litre", []),  # not supported
            ("5 microEq per litre", ["microEq per litre"]),
        ], verbose=verbose)
        assert_text_regex("MICROMOLAR", MICROMOLAR, [
            ("5 micromolar", ["micromolar"]),
            ("5 μM", ["μM"]),
            ("5 uM", ["uM"]),
        ], verbose=verbose)
        assert_text_regex("MICROMOLES_PER_L", MICROMOLES_PER_L, [
            ("5 micromol/L", ["micromol/L"]),
            ("5 micromoles/litre", ["micromoles/litre"]),
            ("5 umol/L", ["umol/L"]),
            ("5 μmol/L", ["μmol/L"]),
        ], verbose=verbose)
        assert_text_regex("MILLIEQ_PER_L", MILLIEQ_PER_L, [
            ("5 mEq/L", ["mEq/L"]),
            ("5 milliequivalents per litre", []),  # not supported
            ("5 milliEq per litre", ["milliEq per litre"]),
        ], verbose=verbose)

        # -------------------------------------------------------------------------
        # Concentration (mass)
        # -------------------------------------------------------------------------

        assert_text_regex("G_PER_DL", G_PER_DL, [
            ("5 g/dL", ["g/dL"]),
            ("5 grams per deciliter", ["grams per deciliter"]),
        ], verbose=verbose)
        assert_text_regex("G_PER_L", G_PER_L, [
            ("5 g/L", ["g/L"]),
            ("5 g L-1", ["g L-1"]),
            ("5 grams per liter", ["grams per liter"]),
        ], verbose=verbose)
        assert_text_regex("MG_PER_DL", MG_PER_DL, [
            ("5 mg/dL", ["mg/dL"]),
            ("5 milligrams per deciliter", ["milligrams per deciliter"]),
        ], verbose=verbose)
        assert_text_regex("MG_PER_L", MG_PER_L, [
            ("5 mg/L", ["mg/L"]),
            ("5 mg L-1", ["mg L-1"]),
            ("5 milligrams per liter", ["milligrams per liter"]),
        ], verbose=verbose)

        # -------------------------------------------------------------------------
        # Concentration (arbitrary count and dimensionless things)
        # -------------------------------------------------------------------------

        assert_text_regex("BILLION_PER_L", BILLION_PER_L, [
            ("5 × 10^9/L", ["× 10^9/L"]),
            ("5 * 10e9/L", ["* 10e9/L"]),
            ("5 x 10e9 per litre", ["x 10e9 per litre"]),
        ], verbose=verbose)
        assert_text_regex("CELLS_PER_CUBIC_MM", CELLS_PER_CUBIC_MM, [
            ("cells/mm3", ["cells/mm3"]),
            ("blibble", []),
            ("9800 / mm3", ["/ mm3"]),
            ("9800 cell/mm3", ["cell/mm3"]),
            ("9800 cells/mm3", ["cells/mm3"]),
            ("9800 cells per cubic mm", ["cells per cubic mm"]),
            ("9800 per cubic mm", ["per cubic mm"]),
            ("9800 per cmm", ["per cmm"]),
        ], verbose=verbose)
        assert_text_regex(
            "CELLS_PER_CUBIC_MM_OR_MICROLITRE",
            CELLS_PER_CUBIC_MM_OR_MICROLITRE, [
                ("9800 / mm3", ["/ mm3"]),
                ("9800 cell/mm3", ["cell/mm3"]),
                ("9800 cells/mm3", ["cells/mm3"]),
                ("9800 cells per cubic mm", ["cells per cubic mm"]),
                ("9800 per cubic mm", ["per cubic mm"]),
                ("9800 per cmm", ["per cmm"]),
                ("9800 per μL", ["per μL"]),
                ("9800 per microliter", ["per microliter"]),
                ("9800 / microlitre", ["/ microlitre"]),
            ],
            verbose=verbose
        )
        assert_text_regex("L_PER_L", L_PER_L, [
            ("5 L/L", ["L/L"]),
            ("5 l/l", ["l/l"]),
            ("5 litre per liter", ["litre per liter"]),
        ], verbose=verbose)
        assert_text_regex("MICROUNITS_PER_ML", MICROUNITS_PER_ML, [
            ("5 microunits/mL", ["microunits/mL"]),
            ("5 microU/millilitre", ["microU/millilitre"]),
            ("5 uU/mL", ["uU/mL"]),
            ("5 μIU/ml", ["μIU/ml"]),
        ], verbose=verbose)
        assert_text_regex("MILLIMOLES_PER_MOL", MILLIMOLES_PER_MOL, [
            ("5 mmol/mol", ["mmol/mol"]),
            ("5 millimoles per mole", ["millimoles per mole"]),
        ], verbose=verbose)
        assert_text_regex("MILLIUNITS_PER_L", MILLIUNITS_PER_L, [
            ("5 milliunits/L", ["milliunits/L"]),
            ("5 milliU/litre", ["milliU/litre"]),
            ("5 mIU/litre", ["mIU/litre"]),
            ("5 mU/L", ["mU/L"]),
        ], verbose=verbose)
        assert_text_regex("TRILLION_PER_L", TRILLION_PER_L, [
            ("5 × 10^12/L", ["× 10^12/L"]),
            ("5 * 10e12/L", ["* 10e12/L"]),
            ("5 x 10e12 per litre", ["x 10e12 per litre"]),
        ], verbose=verbose)
        assert_text_regex("UNITS_PER_L", UNITS_PER_L, [
            ("5 units/L", ["units/L"]),
            ("5 U/litre", ["U/litre"]),
            ("5 U/L", ["U/L"]),
        ], verbose=verbose)

        # -------------------------------------------------------------------------
        # Speed
        # -------------------------------------------------------------------------

        assert_text_regex("MM_PER_H", MM_PER_H, [
            ("5 mm/h", ["mm/h"]),
            ("5 mm per h", ["mm per h"]),
        ], verbose=verbose)

        # -------------------------------------------------------------------------
        # Pressure
        # -------------------------------------------------------------------------

        assert_text_regex("MM_HG", MM_HG, [
            ("5 mmHg", ["mmHg"]),
            ("5 mm Hg", ["mm Hg"]),
        ], verbose=verbose)

        # -------------------------------------------------------------------------
        # Area and related
        # -------------------------------------------------------------------------

        assert_text_regex("SQ_M", SQ_M, [
            ("5 square metres", ["square metres"]),
            ("5 sq m", ["sq m"]),
            ("5 m^2", ["m^2"]),
        ], verbose=verbose)
        assert_text_regex("KG_PER_SQ_M", KG_PER_SQ_M, [
            ("5 kg per square metre", ["kg per square metre"]),
            ("5 kg/sq m", ["kg/sq m"]),
            ("5 kg/m^2", ["kg/m^2"]),
            ("5 kg*m^-2", ["kg*m^-2"]),
        ], verbose=verbose)
