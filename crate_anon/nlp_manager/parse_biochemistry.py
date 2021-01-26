#!/usr/bin/env python

"""
crate_anon/nlp_manager/parse_biochemistry.py

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
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.

===============================================================================

**Python regex-based NLP processors for biochemistry data.**

All inherit from
:class:`crate_anon.nlp_manager.regex_parser.SimpleNumericalResultParser` and
are constructed with these arguments:

nlpdef:
    a :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
cfgsection:
    the name of a CRATE NLP config file section (from which we may
    choose to get extra config information)
commit:
    force a COMMIT whenever we insert data? You should specify this
    in multiprocess mode, or you may get database deadlocks.

"""

import logging
from typing import List, Optional, Tuple, Union

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger

from crate_anon.common.regex_helpers import (
    regex_or,
    WORD_BOUNDARY,
)
from crate_anon.nlp_manager.nlp_definition import NlpDefinition
from crate_anon.nlp_manager.number import to_float
from crate_anon.nlp_manager.regex_parser import (
    make_simple_numeric_regex,
    OPTIONAL_POC,
    SimpleNumericalResultParser,
    ValidatorBase,
)
from crate_anon.nlp_manager.regex_read_codes import (
    ReadCodes,
    regex_components_from_read_codes,
)
from crate_anon.nlp_manager.regex_units import (
    factor_micromolar_from_mg_per_dl,
    factor_millimolar_from_mg_per_dl,
    G,
    G_PER_L,
    MG,
    MG_PER_DL,
    MG_PER_L,
    MICROEQ_PER_L,
    MICROMOLAR,
    micromolar_from_mg_per_dl,
    MICROMOLES_PER_L,
    MICROUNITS_PER_ML,
    MILLIEQ_PER_L,
    MILLIMOLAR,
    millimolar_from_mg_per_dl,
    MILLIMOLES_PER_L,
    MILLIMOLES_PER_MOL,
    MILLIUNITS_PER_L,
    PERCENT,
    UNITS_PER_L,
)

log = logging.getLogger(__name__)


# =============================================================================
# C-reactive protein (CRP)
# =============================================================================

class Crp(SimpleNumericalResultParser):
    """
    C-reactive protein (CRP).

    CRP units:

    - mg/L is commonest in the UK (or at least standard at Addenbrooke's,
      Hinchingbrooke, and Dundee);

    - values of <=6 mg/L or <10 mg/L are normal, and e.g. 70-250 mg/L in
      pneumonia.

    - Refs include:

      - http://www.ncbi.nlm.nih.gov/pubmed/7705110
      - http://emedicine.medscape.com/article/2086909-overview

    - 1 mg/dL = 10 mg/L, so normal in mg/dL is <=1 roughly.

    """

    CRP_BASE = fr"""
        {WORD_BOUNDARY}
            (?: (?: C [-\s]+ reactive [\s]+ protein ) | CRP )
        {WORD_BOUNDARY}
    """
    CRP = regex_or(
        *regex_components_from_read_codes(
            ReadCodes.CRP_PLASMA,
            ReadCodes.CRP_SERUM,
        ),
        CRP_BASE,
        wrap_each_in_noncapture_group=True,
        wrap_result_in_noncapture_group=False
    )
    REGEX = make_simple_numeric_regex(
        quantity=CRP,
        units=regex_or(
            MG_PER_DL,
            MG_PER_L
        ),
        optional_ignorable_after_quantity=OPTIONAL_POC
    )
    NAME = "CRP"
    PREFERRED_UNIT_COLUMN = "value_mg_L"
    UNIT_MAPPING = {
        MG_PER_L: 1,       # preferred unit
        MG_PER_DL: 10,     # 1 mg/dL -> 10 mg/L
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfg_processor_name: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in parent class
        self.test_numerical_parser([
            ("CRP", []),  # should fail; no values
            ("CRP 6", [6]),
            ("C-reactive protein 6", [6]),
            ("C reactive protein 6", [6]),
            ("CRP = 6", [6]),
            ("CRP 6 mg/dl", [60]),
            ("CRP: 6", [6]),
            ("CRP equals 6", [6]),
            ("CRP is equal to 6", [6]),
            ("CRP <1", [1]),
            ("CRP less than 1", [1]),
            ("CRP <1 mg/dl", [10]),
            ("CRP >250", [250]),
            ("CRP more than 1", [1]),
            ("CRP greater than 1", [1]),
            ("CRP >250 mg/dl", [2500]),
            ("CRP was 62", [62]),
            ("CRP was 62 mg/l", [62]),
            ("CRP was <1", [1]),
            ("CRP is 19.2", [19.2]),
            ("CRP is >250", [250]),
            ("CRP is 19 mg dl-1", [190]),
            ("CRP is 19 mg dl -1", [190]),
            ("CRP 1.9 mg/L", [1.9]),
            ("CRP-97", [97]),
            ("CRP 1.9 mg L-1", [1.9]),
            ("CRP        |       1.9 (H)      | mg/L", [1.9]),
            ("Plasma C-reactive protein level (XE2dy) 45 mg/L", [45]),
            ("Serum C reactive protein level (XaINL) 45 mg/L", [45]),
            ("CRP (mg/L) 62", [62]),
        ], verbose=verbose)


class CrpValidator(ValidatorBase):
    """
    Validator for CRP
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return Crp.NAME, [Crp.CRP]


# =============================================================================
# Sodium (Na)
# =============================================================================
# ... handy to check approximately expected distribution of results!

class Sodium(SimpleNumericalResultParser):
    """
    Sodium (Na).
    """
    SODIUM_BASE = fr"""
        {WORD_BOUNDARY} (?: Na | Sodium ) {WORD_BOUNDARY}
    """
    SODIUM = regex_or(
        *regex_components_from_read_codes(
            ReadCodes.SODIUM,
            ReadCodes.SODIUM_BLOOD,
            ReadCodes.SODIUM_PLASMA,
            ReadCodes.SODIUM_SERUM,
        ),
        SODIUM_BASE,
        wrap_each_in_noncapture_group=True,
        wrap_result_in_noncapture_group=False
    )
    REGEX = make_simple_numeric_regex(
        quantity=SODIUM,
        units=regex_or(
            MILLIMOLAR,  # good
            MILLIMOLES_PER_L,  # good
            MILLIEQ_PER_L,  # good
            MG,  # bad
        ),
        optional_ignorable_after_quantity=OPTIONAL_POC
    )
    NAME = "Sodium"
    PREFERRED_UNIT_COLUMN = "value_mmol_L"
    UNIT_MAPPING = {
        MILLIMOLAR: 1,       # preferred unit
        MILLIMOLES_PER_L: 1,
        MILLIEQ_PER_L: 1,
        # but not MG
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfg_processor_name: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in parent class
        self.test_numerical_parser([
            ("Na", []),  # should fail; no values
            ("Na 120", [120]),
            ("sodium 153", [153]),
            ("Na 135 mEq/L", [135]),
            ("Na 139 mM", [139]),
            ("docusate sodium 100mg", []),
            ("Present: Nicola Adams (NA). 1.0 Minutes of last meeting", []),
            ("Present: Nicola Adams (NA) 1.0 Minutes of last meeting", []),
            ("Na (H) 145 mM", [145]),
            ("Na (*) 145 mM", [145]),
            ("Na (X) 145 mM", []),
            ("blah (Na) 145 mM", []),
            ("Na (145) something", [145]),
            ("Na (145 mM), others", [145]),
            ("Na-145", [145]),
            ("Sodium level (X771T) 145", [145]),
            ("Blood sodium level (XaDva) 145", [145]),
            ("Plasma sodium level (XaIRf) 145", [145]),
            ("Serum sodium level (XE2q0) 145", [145]),
            ("Serum sodium level (mmol/L) 137", [137]),
        ], verbose=verbose)


class SodiumValidator(ValidatorBase):
    """
    Validator for Sodium
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return Sodium.NAME, [Sodium.SODIUM]


# =============================================================================
# Potassium (K)
# =============================================================================

class Potassium(SimpleNumericalResultParser):
    """
    Potassium (K).
    """
    POTASSIUM_BASE = fr"""
        {WORD_BOUNDARY} (?: K | Potassium ) {WORD_BOUNDARY}
    """
    POTASSIUM = regex_or(
        POTASSIUM_BASE,
        *regex_components_from_read_codes(
            ReadCodes.POTASSIUM,
            ReadCodes.POTASSIUM_BLOOD,
            ReadCodes.POTASSIUM_PLASMA,
            ReadCodes.POTASSIUM_SERUM,
        ),
        wrap_each_in_noncapture_group=True,
        wrap_result_in_noncapture_group=False
    )
    REGEX = make_simple_numeric_regex(
        quantity=POTASSIUM,
        units=regex_or(
            MILLIMOLAR,  # good
            MILLIMOLES_PER_L,  # good
            MILLIEQ_PER_L,  # good
            MG,  # bad
        ),
        optional_ignorable_after_quantity=OPTIONAL_POC
    )
    NAME = "Potassium"
    PREFERRED_UNIT_COLUMN = "value_mmol_L"
    UNIT_MAPPING = {
        MILLIMOLAR: 1,       # preferred unit
        MILLIMOLES_PER_L: 1,
        MILLIEQ_PER_L: 1,
        # but not MG
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfg_processor_name: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in parent class
        self.test_numerical_parser([
            ("K", []),  # should fail; no values
            ("K 4", [4]),
            ("Potassium 4.3", [4.3]),
            ("K 4.5 mEq/L", [4.5]),
            ("K 4.5 mM", [4.5]),
            ("losartan potassium 50mg", []),
            ("Present: Kerry Smith (K). 1.0 Minutes of last meeting", []),
            ("Present: Kerry Smith (K) 1.0 Minutes of last meeting", []),
            ("K (H) 5.6 mM", [5.6]),
            ("K (*) 5.6 mM", [5.6]),
            ("K (X) 5.6 mM", []),
            ("blah (K) 5.6 mM", []),
            ("K (5.6) something", [5.6]),
            ("K (5.6 mM), others", [5.6]),
            ("K-3.2", [3.2]),
            ("Potassium level (X771S) 3.2", [3.2]),
            ("Blood potassium level (XaDvZ) 3.2", [3.2]),
            ("Plasma potassium level (XaIRl) 3.2", [3.2]),
            ("Serum potassium level (XE2pz) 3.2", [3.2]),
            ("Serum potassium level (XaIRl) 3.2", []),  # wrong code
        ], verbose=verbose)


class PotassiumValidator(ValidatorBase):
    """
    Validator for Potassium
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return Potassium.NAME, [Potassium.POTASSIUM]


# =============================================================================
# Urea
# =============================================================================

class Urea(SimpleNumericalResultParser):
    """
    Urea.
    """
    UREA_BASE = fr"""
        {WORD_BOUNDARY} U(?:r(?:ea)?)? {WORD_BOUNDARY}
    """
    UREA = regex_or(
        *regex_components_from_read_codes(
            ReadCodes.UREA_BLOOD,
            ReadCodes.UREA_PLASMA,
            ReadCodes.UREA_SERUM,
        ),
        UREA_BASE,
        wrap_each_in_noncapture_group=True,
        wrap_result_in_noncapture_group=False
    )
    REGEX = make_simple_numeric_regex(
        quantity=UREA,
        units=regex_or(
            MILLIMOLAR,  # good
            MILLIMOLES_PER_L,  # good
            MILLIEQ_PER_L,  # good
            MG,  # bad
        ),
        optional_ignorable_after_quantity=OPTIONAL_POC
    )
    NAME = "Urea"
    PREFERRED_UNIT_COLUMN = "value_mmol_L"
    UNIT_MAPPING = {
        MILLIMOLAR: 1,       # preferred unit
        MILLIMOLES_PER_L: 1,
        MILLIEQ_PER_L: 1,
        # but not MG
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfg_processor_name: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in parent class
        self.test_numerical_parser([
            ("Urea", []),  # should fail; no values
            ("U 4", [4]),
            ("Urea 4.3", [4.3]),
            ("U 4.5 mEq/L", [4.5]),
            ("Ur 4.5 mM", [4.5]),
            ("Present: Ursula Rogers (U). 1.0 Minutes of last meeting", []),
            ("Present: Ursula Rogers (UR) 1.0 Minutes of last meeting", []),
            ("U (H) 5.6 mM", [5.6]),
            ("Ur (*) 5.6 mM", [5.6]),
            ("Urea (X) 5.6 mM", []),
            ("blah (U) 5.6 mM", []),
            ("Urea (5.6) something", [5.6]),
            ("Urea (5.6 mM), others", [5.6]),
            ("U-3.2", [3.2]),
            ("Blood urea (X771P) 3.2", [3.2]),
            ("Plasma urea level (XaDvl) 3.2", [3.2]),
            ("Serum urea level (XM0lt) 3.2", [3.2]),
        ], verbose=verbose)


class UreaValidator(ValidatorBase):
    """
    Validator for Urea
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return Urea.NAME, [Urea.UREA]


# =============================================================================
# Creatinine
# =============================================================================

class Creatinine(SimpleNumericalResultParser):
    """
    Creatinine. Default units are micromolar (SI).
    """
    CREATININE_BASE = fr"""
        {WORD_BOUNDARY} Cr(?:eat(?:inine)?)? {WORD_BOUNDARY}
    """
    # ... Cr, Creat, Creatinine
    # Possible that "creatine" is present as a typo... but it's wrong...
    CREATININE = regex_or(
        *regex_components_from_read_codes(
            ReadCodes.CREATININE,
            ReadCodes.CREATININE_PLASMA,
            ReadCodes.CREATININE_PLASMA_CORRECTED,
            ReadCodes.CREATININE_SERUM,
            ReadCodes.CREATININE_SERUM_CORRECTED,
        ),
        CREATININE_BASE,
        wrap_each_in_noncapture_group=True,
        wrap_result_in_noncapture_group=False
    )
    REGEX = make_simple_numeric_regex(
        quantity=CREATININE,
        units=regex_or(
            MICROMOLAR,  # good
            MICROMOLES_PER_L,  # good
            MICROEQ_PER_L,  # good
            MG_PER_DL,  # good but needs conversion
            # ... note that MG_PER_DL must precede MG
            MG,  # bad
        ),
        optional_ignorable_after_quantity=OPTIONAL_POC
    )
    CREATININE_MOLECULAR_MASS_G_PER_MOL = 113.12
    # ... https://pubchem.ncbi.nlm.nih.gov/compound/creatinine
    NAME = "Creatinine"
    PREFERRED_UNIT_COLUMN = "value_micromol_L"
    UNIT_MAPPING = {
        MICROMOLAR: 1,       # preferred unit
        MICROMOLES_PER_L: 1,
        MICROEQ_PER_L: 1,
        MG_PER_DL: factor_micromolar_from_mg_per_dl(
            CREATININE_MOLECULAR_MASS_G_PER_MOL
        )
        # but not MG
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfg_processor_name: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in parent class
        def convert(mg_dl: float) -> float:
            # Convert mg/dl to μM
            return micromolar_from_mg_per_dl(
                mg_dl, self.CREATININE_MOLECULAR_MASS_G_PER_MOL)

        self.test_numerical_parser([
            ("Creatinine", []),  # should fail; no values
            ("Cr 50", [50]),
            ("Creat 125.5", [125.5]),
            ("Creat 75 uEq/L", [75]),
            ("Cr 75 μM", [75]),
            ("Present: Chloe Rogers (CR). 1.0 Minutes of last meeting", []),
            ("Creatinine (H) 200 uM", [200]),
            ("Creatinine (*) 200 micromol/L", [200]),
            ("Creatinine (X) 200 uM", []),
            ("Creatinine 200 micromolar", [200]),
            ("Creatinine 200 micromolar, others", [200]),
            ("blah (creat) 5.6 uM", []),
            ("Creatinine (200) something", [200]),
            ("Creatinine (200 micromolar)", [200]),
            ("Creatinine (200 micromolar), others", [200]),
            ("Cr-75", [75]),
            ("creatinine 3 mg/dl", [convert(3)]),
            ("creatinine 3 mg", []),
            ("Creatinine level (X771Q) 75", [75]),
            ("Plasma creatinine level (XaETQ) 75", [75]),
            ("Cor plasma creatinine level (XaERX) 75", [75]),
            ("Serum creatinine level (XE2q5) 75", [75]),
            ("Cor serum creatinine level (XaERc) 75", [75]),
        ], verbose=verbose)


class CreatinineValidator(ValidatorBase):
    """
    Validator for Creatinine
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return Creatinine.NAME, [Creatinine.CREATININE]


# =============================================================================
# Lithium (Li)
# =============================================================================

class Lithium(SimpleNumericalResultParser):
    """
    Lithium (Li) levels (for blood tests, not doses).
    """
    LITHIUM_BASE = fr"""
        {WORD_BOUNDARY} Li(?:thium)? {WORD_BOUNDARY}
    """
    LITHIUM = regex_or(
        *regex_components_from_read_codes(
            ReadCodes.LITHIUM_SERUM,
        ),
        LITHIUM_BASE,
        wrap_each_in_noncapture_group=True,
        wrap_result_in_noncapture_group=False
    )
    REGEX = make_simple_numeric_regex(
        quantity=LITHIUM,
        units=regex_or(
            MILLIMOLAR,  # good
            MILLIMOLES_PER_L,  # good
            MILLIEQ_PER_L,  # good
            MG,  # bad
            G,  # bad
        )
    )
    NAME = "Lithium"
    PREFERRED_UNIT_COLUMN = "value_mmol_L"
    UNIT_MAPPING = {
        MILLIMOLAR: 1,       # preferred unit
        MILLIMOLES_PER_L: 1,
        MILLIEQ_PER_L: 1,
        # but not MG
        # and not G
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfg_processor_name: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in parent class
        self.test_numerical_parser([
            ("Li", []),  # should fail; no values
            ("Li 0.4", [0.4]),
            ("li 1200 mg", []),  # that's a dose
            ("li 1.2 g", []),  # that's a dose
            ("lithium 1200 mg", []),  # that's a dose
            ("lithium 153", [153]),  # an unhappy patient...
            ("Li 135 mEq/L", [135]),
            ("Li 139 mM", [139]),
            ("lithium carbonate 800mg", []),
            ("Present: Linda Ingles (LI). 1.0 Minutes of last meeting", []),
            ("Present: Linda Ingles (LI) 1.0 Minutes of last meeting", []),
            ("Li (H) 1.3 mM", [1.3]),
            ("Li (*) 1.3 mM", [1.3]),
            ("Li (X) 1.3 mM", []),
            ("blah (Li) 1.2 mM", []),
            ("Li (1.3) something", [1.3]),
            ("Li (0.4 mM), others", [0.4]),
            ("Li-0.4", [0.4]),
            ("Serum lithium level (XE25g) 0.4", [0.4]),
        ], verbose=verbose)


class LithiumValidator(ValidatorBase):
    """
    Validator for Lithium
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return Lithium.NAME, [Lithium.LITHIUM]


# =============================================================================
# Thyroid-stimulating hormone (TSH)
# =============================================================================

class Tsh(SimpleNumericalResultParser):
    """
    Thyroid-stimulating hormone (TSH).
    """
    TSH_BASE = fr"""
        {WORD_BOUNDARY}
            (?: TSH | thyroid [-\s]+ stimulating [-\s]+ hormone )
        {WORD_BOUNDARY}
    """
    TSH = regex_or(
        *regex_components_from_read_codes(
            ReadCodes.TSH_PLASMA,
            ReadCodes.TSH_PLASMA_30_MIN,
            ReadCodes.TSH_PLASMA_60_MIN,
            ReadCodes.TSH_PLASMA_90_MIN,
            ReadCodes.TSH_PLASMA_120_MIN,
            ReadCodes.TSH_PLASMA_150_MIN,
            ReadCodes.TSH_SERUM,
            ReadCodes.TSH_SERUM_60_MIN,
            ReadCodes.TSH_SERUM_90_MIN,
            ReadCodes.TSH_SERUM_120_MIN,
            ReadCodes.TSH_SERUM_150_MIN,
        ),
        TSH_BASE,
        wrap_each_in_noncapture_group=True,
        wrap_result_in_noncapture_group=False
    )
    REGEX = make_simple_numeric_regex(
        quantity=TSH,
        units=regex_or(
            MILLIUNITS_PER_L,  # good
            MICROUNITS_PER_ML,  # good
        )
    )
    NAME = "TSH"
    PREFERRED_UNIT_COLUMN = "value_mU_L"
    UNIT_MAPPING = {
        MILLIUNITS_PER_L: 1,       # preferred unit
        MICROUNITS_PER_ML: 1
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfg_processor_name: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in superclass
        self.test_numerical_parser([
            ("TSH", []),  # should fail; no values
            ("TSH 1.5", [1.5]),
            ("thyroid-stimulating hormone 1.5", [1.5]),
            ("TSH 1.5 mU/L", [1.5]),
            ("TSH 1.5 mIU/L", [1.5]),
            ("TSH 1.5 μU/mL", [1.5]),
            ("TSH 1.5 μIU/mL", [1.5]),
            ("TSH 1.5 uU/mL", [1.5]),
            ("TSH 1.5 uIU/mL", [1.5]),
            ("TSH-2.3", [2.3]),
            ("Plasma TSH level (XaELW) 2.3", [2.3]),
            ("Serum TSH level (XaELV) 2.3", [2.3]),
            # etc.; not all Read codes tested here
        ], verbose=verbose)


class TshValidator(ValidatorBase):
    """
    Validator for TSH
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return Tsh.NAME, [Tsh.TSH]


# =============================================================================
# Alkaline phosphatase
# =============================================================================

class AlkPhos(SimpleNumericalResultParser):
    """
    Alkaline phosphatase (ALP, AlkP, AlkPhos).
    """
    ALKP_BASE = fr"""
        {WORD_BOUNDARY}
        (?:
            (?: ALk?P (?:\. | {WORD_BOUNDARY}) ) |
            (?:
                alk(?:aline | \.)?
                [-\s]*
                phos(?:phatase{WORD_BOUNDARY} | \. | {WORD_BOUNDARY})
            )
        )
    """
    ALKP = regex_or(
        *regex_components_from_read_codes(
            ReadCodes.ALKPHOS_PLASMA,
            ReadCodes.ALKPHOS_SERUM,
            ReadCodes.ALKPHOS,  # least specific; at end
        ),
        ALKP_BASE,
        wrap_each_in_noncapture_group=True,
        wrap_result_in_noncapture_group=False
    )
    REGEX = make_simple_numeric_regex(
        quantity=ALKP,
        units=UNITS_PER_L
    )
    NAME = "AlkPhos"
    PREFERRED_UNIT_COLUMN = "value_U_L"
    UNIT_MAPPING = {
        UNITS_PER_L: 1      # preferred unit
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfg_processor_name: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in superclass
        self.test_numerical_parser([
            ("ALP", []),  # should fail; no values
            ("was 7", []),  # no quantity
            ("ALP 55", [55]),
            ("Alkaline-Phosphatase 55", [55]),
            ("Alkaline Phosphatase    55 U/L ", [55]),
            ("ALP 55 U/L", [55]),
            ("ALP-55", [55]),
            ("AlkP 55", [55]),
            ("alk.phos. 55", [55]),
            ("alk. phos. 55", [55]),
            ("alkphos 55", [55]),
            ("Alkaline phosphatase level (44F3.) 55", [55]),
            ("Alkaline phosphatase level (44F3x) 55", []),  # test "." in regex
            ("Plasma alkaline phosphatase level (XaIRj) 55", [55]),
            ("Serum alkaline phosphatase level (XE2px) 55", [55]),
        ], verbose=verbose)


class AlkPhosValidator(ValidatorBase):
    """
    Validator for ALP
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return AlkPhos.NAME, [AlkPhos.ALKP]


# =============================================================================
# Alanine aminotransferase (ALT)
# =============================================================================

class ALT(SimpleNumericalResultParser):
    """
    Alanine aminotransferase (ALT), a.k.a. alanine transaminase (ALT).

    A.k.a. serum glutamate-pyruvate transaminase (SGPT), or serum
    glutamate-pyruvic transaminase (SGPT), but not a.k.a. those in recent
    memory!
    """
    ALT_BASE = fr"""
        {WORD_BOUNDARY}
        (?:
            ALT |
            alanine [-\s]+ (?: aminotransferase | transaminase )
        )
        {WORD_BOUNDARY}
    """
    ALT = regex_or(
        *regex_components_from_read_codes(
            ReadCodes.ALT,
        ),
        ALT_BASE,
        wrap_each_in_noncapture_group=True,
        wrap_result_in_noncapture_group=False
    )
    REGEX = make_simple_numeric_regex(
        quantity=ALT,
        units=UNITS_PER_L
    )
    NAME = "ALT"
    PREFERRED_UNIT_COLUMN = "value_U_L"
    UNIT_MAPPING = {
        UNITS_PER_L: 1      # preferred unit
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfg_processor_name: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in superclass
        self.test_numerical_parser([
            ("ALT", []),  # should fail; no values
            ("was 7", []),  # no quantity
            ("ALT 55", [55]),
            ("alanine-aminotransferase 55", [55]),
            ("Alanine aminotransferase    55 U/L ", [55]),
            ("alanine transaminase    55 U/L ", [55]),
            ("ALT 55 U/L", [55]),
            ("ALT-55", [55]),
            ("ALP 55", []),  # wrong thing
            ("ALT/SGPT serum level (44G3.) 55", [55]),
        ], verbose=verbose)


class ALTValidator(ValidatorBase):
    """
    Validator for ALT
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return ALT.NAME, [ALT.ALT]


# =============================================================================
# Gamma GT (gGT)
# =============================================================================

class GammaGT(SimpleNumericalResultParser):
    """
    Gamma-glutamyl transferase (gGT).
    """
    GGT_BASE = fr"""
        {WORD_BOUNDARY}
        (?:
            (?: γ | G | gamma)
            [-\s]*
            (?:
                GT |
                glutamyl [-\s]+ transferase
            )
        )
        {WORD_BOUNDARY}
    """
    GGT = regex_or(
        *regex_components_from_read_codes(
            ReadCodes.GAMMA_GT,
            ReadCodes.GAMMA_GT_PLASMA,
            ReadCodes.GAMMA_GT_SERUM,
        ),
        GGT_BASE,
        wrap_each_in_noncapture_group=True,
        wrap_result_in_noncapture_group=False
    )
    REGEX = make_simple_numeric_regex(
        quantity=GGT,
        units=UNITS_PER_L
    )
    NAME = "GammaGT"
    PREFERRED_UNIT_COLUMN = "value_U_L"
    UNIT_MAPPING = {
        UNITS_PER_L: 1      # preferred unit
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfg_processor_name: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in superclass
        self.test_numerical_parser([
            ("gGT", []),  # should fail; no values
            ("was 7", []),  # no quantity
            ("gGT 55", [55]),
            ("gamma Glutamyl Transferase 19  U/L", [19]),
            ("Gamma GT    55 U/L ", [55]),
            ("GGT 55 U/L", [55]),
            ("ggt-55", [55]),
            ("γGT 55", [55]),
            ("Gamma-glutamyl transferase lev (44G4.) 55", [55]),
            ("Plasma gamma-glutamyl transferase level (XaES4) 55", [55]),
            ("Serum gamma-glutamyl transferase level (XaES3) 55", [55]),
        ], verbose=verbose)


class GammaGTValidator(ValidatorBase):
    """
    Validator for gGT
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return GammaGT.NAME, [GammaGT.GGT]


# =============================================================================
# Total bilirubin
# =============================================================================

class Bilirubin(SimpleNumericalResultParser):
    """
    Total bilirubin.
    """
    BILIRUBIN_BASE = fr"""
        {WORD_BOUNDARY}
        (?: t(?: ot(?:al | \.)? | \.) \s+ )?
        bili?(?: \. | rubin{WORD_BOUNDARY})?
    """
    BILIRUBIN = regex_or(
        *regex_components_from_read_codes(
            ReadCodes.BILIRUBIN_PLASMA_TOTAL,
            ReadCodes.BILIRUBIN_SERUM,
            ReadCodes.BILIRUBIN_SERUM_TOTAL,
            ReadCodes.BILIRUBIN_TOTAL,
        ),
        BILIRUBIN_BASE,
        wrap_each_in_noncapture_group=True,
        wrap_result_in_noncapture_group=False
    )
    REGEX = make_simple_numeric_regex(
        quantity=BILIRUBIN,
        units=regex_or(
            MICROMOLAR,  # good
            MICROMOLES_PER_L,  # good
        )
    )
    NAME = "Bilirubin"
    PREFERRED_UNIT_COLUMN = "value_micromol_L"
    UNIT_MAPPING = {
        MICROMOLAR: 1,       # preferred unit
        MICROMOLES_PER_L: 1
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfg_processor_name: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in superclass
        self.test_numerical_parser([
            ("tot Bil", []),  # should fail; no values
            ("was 7", []),  # no quantity
            ("tot Bil 6", [6]),
            ("Total Bilirubin: 6", [6]),
            ("Total Bilirubin 6 umol/L", [6]),
            ("bilirubin 17 μM", [17]),
            ("t.bilirubin 17 μM", [17]),
            ("t. bilirubin 17 μM", [17]),
            ("bili. 17 μM", [17]),
            ("bili 17 μM", [17]),
            ("Plasma total bilirubin level (XaETf) 17", [17]),
            ("Serum bilirubin level (44E..) 17", [17]),
            ("Serum total bilirubin level (XaERu) 17", [17]),
            ("Total bilirubin level (XE2qu) 17", [17]),
            ("Total   bilirubin \t  level \n (XE2qu) 17", [17]),  # test whitespace  # noqa
            ("xTotal bilirubin level (XE2qu) 17", []),  # test word boundary
            ("Serum total bilirubin level (XaERu) 6 umol/L", [6]),
        ], verbose=verbose)


class BilirubinValidator(ValidatorBase):
    """
    Validator for bilirubin.
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return Bilirubin.NAME, [Bilirubin.BILIRUBIN]


# =============================================================================
# Albumin (Alb)
# =============================================================================

class Albumin(SimpleNumericalResultParser):
    """
    Albumin (Alb).
    """
    ALBUMIN_BASE = fr"""
        {WORD_BOUNDARY}
        (?:
            alb(?:\. | umin{WORD_BOUNDARY})?
            (?: \s+ level{WORD_BOUNDARY})?
        )
    """
    ALBUMIN = regex_or(
        *regex_components_from_read_codes(
            ReadCodes.ALBUMIN_PLASMA,
            ReadCodes.ALBUMIN_SERUM,
        ),
        ALBUMIN_BASE,
        wrap_each_in_noncapture_group=True,
        wrap_result_in_noncapture_group=False
    )
    REGEX = make_simple_numeric_regex(
        quantity=ALBUMIN,
        units=G_PER_L
    )
    NAME = "Albumin"
    PREFERRED_UNIT_COLUMN = "value_g_L"
    UNIT_MAPPING = {
        G_PER_L: 1       # preferred unit
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfg_processor_name: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in superclass
        self.test_numerical_parser([
            ("Alb", []),  # should fail; no values
            ("was 7", []),  # no quantity
            ("ALP 6", []),  # wrong quantity
            ("Alb 6", [6]),
            ("Albumin: 48", [48]),
            ("Albumin 48 g/L", [48]),
            ("alb. 48", [48]),
            ("albumin level 48", [48]),
            ("Plasma albumin level (XaIRc) 48", [48]),
            ("Serum albumin level (XE2eA) 48", [48]),
        ], verbose=verbose)


class AlbuminValidator(ValidatorBase):
    """
    Validator for Albumin
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return Albumin.NAME, [Albumin.ALBUMIN]


# =============================================================================
# Glucose
# =============================================================================

class Glucose(SimpleNumericalResultParser):
    """
    Glucose.

    - By Emanuele Osimo, Feb 2019.
    - Some modifications by Rudolf Cardinal, Feb 2019.
    """
    GLUCOSE_BASE = fr"""
        {WORD_BOUNDARY} glu(?:c(?:ose)?)? {WORD_BOUNDARY}
        # glu, gluc, glucose
    """
    GLUCOSE = regex_or(
        *regex_components_from_read_codes(
            ReadCodes.GLUCOSE,
            ReadCodes.GLUCOSE_BLOOD,
            ReadCodes.GLUCOSE_BLOOD_2H_POSTPRANDIAL,
            ReadCodes.GLUCOSE_BLOOD_150_MIN,
            ReadCodes.GLUCOSE_PLASMA_RANDOM,
            ReadCodes.GLUCOSE_PLASMA_FASTING,
            ReadCodes.GLUCOSE_PLASMA_30_MIN,
            ReadCodes.GLUCOSE_PLASMA_60_MIN,
            ReadCodes.GLUCOSE_PLASMA_90_MIN,
            ReadCodes.GLUCOSE_PLASMA_120_MIN,
            ReadCodes.GLUCOSE_PLASMA_2H_POSTPRANDIAL,
            ReadCodes.GLUCOSE_PLASMA_150_MIN,
            ReadCodes.GLUCOSE_SERUM,
            ReadCodes.GLUCOSE_SERUM_RANDOM,
            ReadCodes.GLUCOSE_SERUM_FASTING,
            ReadCodes.GLUCOSE_SERUM_30_MIN,
            ReadCodes.GLUCOSE_SERUM_60_MIN,
            ReadCodes.GLUCOSE_SERUM_90_MIN,
            ReadCodes.GLUCOSE_SERUM_120_MIN,
            ReadCodes.GLUCOSE_SERUM_2H_POSTPRANDIAL,
            ReadCodes.GLUCOSE_SERUM_150_MIN,
            # !
        ),
        GLUCOSE_BASE,
        wrap_each_in_noncapture_group=True,
        wrap_result_in_noncapture_group=False
    )
    REGEX = make_simple_numeric_regex(
        quantity=GLUCOSE,
        units=regex_or(
            MILLIMOLAR,  # good
            MILLIMOLES_PER_L,  # good
            MG_PER_DL,  # good but needs conversion
        ),
        optional_ignorable_after_quantity=OPTIONAL_POC
    )
    GLUCOSE_MOLECULAR_MASS_G_PER_MOL = 180.156
    # ... https://pubchem.ncbi.nlm.nih.gov/compound/D-glucose
    NAME = "Glucose"
    PREFERRED_UNIT_COLUMN = "value_mmol_L"
    UNIT_MAPPING = {
        MILLIMOLAR: 1,       # preferred unit
        MILLIMOLES_PER_L: 1,
        MG_PER_DL: factor_millimolar_from_mg_per_dl(GLUCOSE_MOLECULAR_MASS_G_PER_MOL)  # noqa
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfg_processor_name: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in parent class

        def convert(mg_dl: float) -> float:
            # Convert mg/dl to mM
            return millimolar_from_mg_per_dl(
                mg_dl, self.GLUCOSE_MOLECULAR_MASS_G_PER_MOL)

        self.test_numerical_parser([
            ("glu", []),  # should fail; no values
            ("glucose 6 mM", [6]),
            ("glucose 6 mmol", [6]),
            ("glucose 6", [6]),
            ("glu 6", [6]),
            ("glucose 90 mg/dl", [convert(90)]),  # unit conversion
            ("gluc = 6", [6]),
            ("glucose: 6", [6]),
            ("glu equals 6", [6]),
            ("glucose is equal to 6", [6]),
            ("glu <4", [4]),
            ("glucose less than 1", [1]),  # would be bad news...
            ("glu more than 20", [20]),
            ("glucose was 15", [15]),
            ("glucose was 90 mg/dl", [convert(90)]),
            ("glu is 90 mg dl-1", [convert(90)]),
            ("glucose is 90 mg dl -1", [convert(90)]),
            ("glu-5", [5]),
            ("glucose        |       20.3 (H)      | mmol/L", [20.3]),
            ("Glucose level (X772y) 5", [5]),
            ("Blood glucose level (X772z) 5", [5]),
            # Not all Read codes tested.
        ], verbose=verbose)


class GlucoseValidator(ValidatorBase):
    """
    Validator for glucose
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return Glucose.NAME, [Glucose.GLUCOSE]


# =============================================================================
# LDL cholesterol
# =============================================================================

class LDLCholesterol(SimpleNumericalResultParser):
    """
    Low density lipoprotein (LDL) cholesterol.

    - By Emanuele Osimo, Feb 2019.
    - Some modifications by Rudolf Cardinal, Feb 2019.
    """
    LDL_BASE = fr"""
        {WORD_BOUNDARY}
        LDL [-\s]*
        (?:
            chol(?:esterol)?{WORD_BOUNDARY} |
            chol\. |
            {WORD_BOUNDARY}  # allows LDL by itself
        )
    """
    LDL = regex_or(
        *regex_components_from_read_codes(
            ReadCodes.LDL_PLASMA,
            ReadCodes.LDL_PLASMA_FASTING,
            ReadCodes.LDL_PLASMA_RANDOM,
            ReadCodes.LDL_SERUM,
            ReadCodes.LDL_SERUM_FASTING,
            ReadCodes.LDL_SERUM_RANDOM,
        ),
        LDL_BASE,
        wrap_each_in_noncapture_group=True,
        wrap_result_in_noncapture_group=False
    )
    REGEX = make_simple_numeric_regex(
        quantity=LDL,
        units=regex_or(
            MILLIMOLAR,  # good
            MILLIMOLES_PER_L,  # good
            MG_PER_DL,  # good but needs conversion
        )
    )
    NAME = "LDL cholesterol"
    PREFERRED_UNIT_COLUMN = "value_mmol_L"
    FACTOR_MG_DL_TO_MMOL_L = 0.02586
    # ... https://www.ncbi.nlm.nih.gov/books/NBK33478/
    UNIT_MAPPING = {
        MILLIMOLAR: 1,       # preferred unit
        MILLIMOLES_PER_L: 1,
        MG_PER_DL: FACTOR_MG_DL_TO_MMOL_L,
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfg_processor_name: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in parent class

        def convert(mg_dl: float) -> float:
            # Convert mg/dl to mM
            return self.FACTOR_MG_DL_TO_MMOL_L * mg_dl

        self.test_numerical_parser([
            ("LDL", []),  # should fail; no values
            ("LDL 4 mM", [4]),
            ("LDL chol 4 mmol", [4]),
            ("LDL chol. 4 mmol", [4]),
            ("LDL 4", [4]),
            ("chol 4", []),  # that's total cholesterol
            ("HDL chol 4", []),  # that's HDL cholesterol
            ("LDL cholesterol 140 mg/dl", [convert(140)]),  # unit conversion
            ("LDL = 4", [4]),
            ("LDL: 4", [4]),
            ("LDL equals 4", [4]),
            ("LDL is equal to 4", [4]),
            ("LDL <4", [4]),
            ("LDLchol less than 4", [4]),
            ("LDL cholesterol more than 20", [20]),
            ("LDL was 4", [4]),
            ("LDL chol was 140 mg/dl", [convert(140)]),
            ("chol was 140 mg/dl", []),
            ("LDL is 140 mg dl-1", [convert(140)]),
            ("ldl chol is 140 mg dl -1", [convert(140)]),
            ("ldl-4", [4]),
            ("LDL chol     |       6.2 (H)      | mmol/L", [6.2]),
            ("Plasma LDL cholesterol level (XaEVs) 4", [4]),
            ("Plasma rndm LDL cholest level (44d4.) 4", [4]),
            ("Plasma fast LDL cholest level (44d5.) 4", [4]),
            ("Serum LDL cholesterol level (44P6.) 4", [4]),
            ("Serum fast LDL cholesterol lev (44PD.) 4", [4]),
            ("Ser random LDL cholesterol lev (44PE.) 4", [4]),
        ], verbose=verbose)


class LDLCholesterolValidator(ValidatorBase):
    """
    Validator for LDL cholesterol
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return LDLCholesterol.NAME, [LDLCholesterol.LDL]


# =============================================================================
# HDL cholesterol
# =============================================================================

class HDLCholesterol(SimpleNumericalResultParser):
    """
    High-density lipoprotein (HDL) cholesterol.

    - By Emanuele Osimo, Feb 2019.
    - Some modifications by Rudolf Cardinal, Feb 2019.
    """
    HDL_BASE = fr"""
        {WORD_BOUNDARY}
        HDL [-\s]*
        (?:
            chol(?:esterol)?{WORD_BOUNDARY} |
            chol\. |
            {WORD_BOUNDARY}  # allows HDL by itself
        )
    """
    HDL = regex_or(
        *regex_components_from_read_codes(
            ReadCodes.HDL_PLASMA,
            ReadCodes.HDL_PLASMA_FASTING,
            ReadCodes.HDL_PLASMA_RANDOM,
            ReadCodes.HDL_SERUM,
            ReadCodes.HDL_SERUM_FASTING,
            ReadCodes.HDL_SERUM_RANDOM,
        ),
        HDL_BASE,
        wrap_each_in_noncapture_group=True,
        wrap_result_in_noncapture_group=False
    )
    REGEX = make_simple_numeric_regex(
        quantity=HDL,
        units=regex_or(
            MILLIMOLAR,  # good
            MILLIMOLES_PER_L,  # good
            MG_PER_DL,  # good but needs conversion
        )
    )
    NAME = "HDL cholesterol"
    PREFERRED_UNIT_COLUMN = "value_mmol_L"
    FACTOR_MG_DL_TO_MMOL_L = 0.02586
    # ... https://www.ncbi.nlm.nih.gov/books/NBK33478/
    UNIT_MAPPING = {
        MILLIMOLAR: 1,       # preferred unit
        MILLIMOLES_PER_L: 1,
        MG_PER_DL: FACTOR_MG_DL_TO_MMOL_L,
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfg_processor_name: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in parent class

        def convert(mg_dl: float) -> float:
            # Convert mg/dl to mM
            return self.FACTOR_MG_DL_TO_MMOL_L * mg_dl

        self.test_numerical_parser([
            ("HDL", []),  # should fail; no values
            ("HDL 4 mM", [4]),
            ("HDL chol 4 mmol", [4]),
            ("HDL chol. 4 mmol", [4]),
            ("HDL 4", [4]),
            ("chol 4", []),  # that's total cholesterol
            ("LDL chol 4", []),  # that's LDL cholesterol
            ("HDL cholesterol 140 mg/dl", [convert(140)]),  # unit conversion
            ("HDL = 4", [4]),
            ("HDL: 4", [4]),
            ("HDL equals 4", [4]),
            ("HDL is equal to 4", [4]),
            ("HDL <4", [4]),
            ("HDLchol less than 4", [4]),
            ("HDL cholesterol more than 20", [20]),
            ("HDL was 4", [4]),
            ("HDL chol was 140 mg/dl", [convert(140)]),
            ("chol was 140 mg/dl", []),
            ("HDL is 140 mg dl-1", [convert(140)]),
            ("Hdl chol is 140 mg dl -1", [convert(140)]),
            ("hdl-4", [4]),
            ("HDL chol     |       6.2 (H)      | mmol/L", [6.2]),
            ("Plasma HDL cholesterol level (XaEVr) 4", [4]),
            ("Plasma rndm HDL cholest level (44d2.) 4", [4]),
            ("Plasma fast HDL cholest level (44d3.) 4", [4]),
            ("Serum HDL cholesterol level (44P5.) 4", [4]),
            ("Serum fast HDL cholesterol lev (44PB.) 4", [4]),
            ("Ser random HDL cholesterol lev (44PC.) 4", [4]),
        ], verbose=verbose)


class HDLCholesterolValidator(ValidatorBase):
    """
    Validator for HDL cholesterol
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return HDLCholesterol.NAME, [HDLCholesterol.HDL]


# =============================================================================
# Total cholesterol
# =============================================================================

class TotalCholesterol(SimpleNumericalResultParser):
    """
    Total or undifferentiated cholesterol.
    """
    CHOLESTEROL_BASE = fr"""
        {WORD_BOUNDARY}
        (?<!HDL[-\s]+) (?<!LDL[-\s]+)  # not preceded by HDL or LDL
        (?: tot(?:al) [-\s] )?         # optional "total" prefix
        (?:
            chol(?:esterol)?{WORD_BOUNDARY} |
            chol\.
        )
    """
    # ... (?<! something ) is a negative lookbehind assertion
    CHOLESTEROL = regex_or(
        *regex_components_from_read_codes(
            ReadCodes.CHOLESTEROL_SERUM,
            ReadCodes.CHOLESTEROL_TOTAL_PLASMA,
            ReadCodes.CHOLESTEROL_TOTAL_SERUM,
        ),
        CHOLESTEROL_BASE,
        wrap_each_in_noncapture_group=True,
        wrap_result_in_noncapture_group=False
    )
    REGEX = make_simple_numeric_regex(
        quantity=CHOLESTEROL,
        units=regex_or(
            MILLIMOLAR,  # good
            MILLIMOLES_PER_L,  # good
            MG_PER_DL,  # good but needs conversion
        )
    )
    NAME = "Total cholesterol"
    PREFERRED_UNIT_COLUMN = "value_mmol_L"
    FACTOR_MG_DL_TO_MMOL_L = 0.02586
    # ... https://www.ncbi.nlm.nih.gov/books/NBK33478/
    UNIT_MAPPING = {
        MILLIMOLAR: 1,       # preferred unit
        MILLIMOLES_PER_L: 1,
        MG_PER_DL: FACTOR_MG_DL_TO_MMOL_L,
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfg_processor_name: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in parent class

        def convert(mg_dl: float) -> float:
            # Convert mg/dl to mM
            return self.FACTOR_MG_DL_TO_MMOL_L * mg_dl

        self.test_numerical_parser([
            ("chol", []),  # should fail; no values
            ("chol 4 mM", [4]),
            ("total chol 4 mmol", [4]),
            ("chol. 4 mmol", [4]),
            ("chol 4", [4]),
            ("HDL chol 4", []),  # that's HDL cholesterol
            ("LDL chol 4", []),  # that's LDL cholesterol
            ("total cholesterol 140 mg/dl", [convert(140)]),  # unit conversion
            ("chol = 4", [4]),
            ("chol: 4", [4]),
            ("chol equals 4", [4]),
            ("chol is equal to 4", [4]),
            ("chol <4", [4]),
            ("chol less than 4", [4]),
            ("cholesterol more than 20", [20]),
            ("chol was 4", [4]),
            ("chol was 140 mg/dl", [convert(140)]),
            ("chol was 140", [140]),  # but probably wrong interpretation!
            ("chol is 140 mg dl-1", [convert(140)]),
            ("chol is 140 mg dl -1", [convert(140)]),
            ("chol-4", [4]),
            ("chol     |       6.2 (H)      | mmol/L", [6.2]),
            ("Serum cholesterol level (XE2eD) 4", [4]),
            ("Plasma total cholesterol level (XaIRd) 4", [4]),
            ("Serum total cholesterol level (XaJe9) 4", [4]),
        ], verbose=verbose)


class TotalCholesterolValidator(ValidatorBase):
    """
    Validator for total cholesterol
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return TotalCholesterol.NAME, [TotalCholesterol.CHOLESTEROL]


# =============================================================================
# Triglycerides
# =============================================================================

class Triglycerides(SimpleNumericalResultParser):
    """
    Triglycerides.

    - By Emanuele Osimo, Feb 2019.
    - Some modifications by Rudolf Cardinal, Feb 2019.
    """
    TG_BASE = fr"""
        {WORD_BOUNDARY}
        (?: Triglyceride[s]? | TG )
        {WORD_BOUNDARY}
    """
    TG = regex_or(
        *regex_components_from_read_codes(
            ReadCodes.TG,
            ReadCodes.TG_PLASMA,
            ReadCodes.TG_PLASMA_FASTING,
            ReadCodes.TG_PLASMA_RANDOM,
            ReadCodes.TG_SERUM,
            ReadCodes.TG_SERUM_FASTING,
            ReadCodes.TG_SERUM_RANDOM,
        ),
        TG_BASE,
        wrap_each_in_noncapture_group=True,
        wrap_result_in_noncapture_group=False
    )
    REGEX = make_simple_numeric_regex(
        quantity=TG,
        units=regex_or(
            MILLIMOLAR,  # good
            MILLIMOLES_PER_L,  # good
            MG_PER_DL,  # good but needs conversion
        )
    )
    NAME = "Triglycerides"
    PREFERRED_UNIT_COLUMN = "value_mmol_L"
    FACTOR_MG_DL_TO_MMOL_L = 0.01129  # reciprocal of 88.57
    # ... https://www.ncbi.nlm.nih.gov/books/NBK33478/
    # ... https://www.ncbi.nlm.nih.gov/books/NBK83505/
    UNIT_MAPPING = {
        MILLIMOLAR: 1,       # preferred unit
        MILLIMOLES_PER_L: 1,
        MG_PER_DL: FACTOR_MG_DL_TO_MMOL_L,
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfg_processor_name: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in parent class

        def convert(mg_dl: float) -> float:
            # Convert mg/dl to mM
            return self.FACTOR_MG_DL_TO_MMOL_L * mg_dl

        self.test_numerical_parser([
            ("TG", []),  # should fail; no values
            ("triglycerides", []),  # should fail; no values
            ("TG 4 mM", [4]),
            ("triglycerides 4 mmol", [4]),
            ("triglyceride 4 mmol", [4]),
            ("TG 4", [4]),
            ("TG 140 mg/dl", [convert(140)]),  # unit conversion
            ("TG = 4", [4]),
            ("TG: 4", [4]),
            ("TG equals 4", [4]),
            ("TG is equal to 4", [4]),
            ("TG <4", [4]),
            ("TG less than 4", [4]),
            ("TG more than 20", [20]),
            ("TG was 4", [4]),
            ("TG was 140 mg/dl", [convert(140)]),
            ("TG was 140", [140]),  # but probably wrong interpretation!
            ("TG is 140 mg dl-1", [convert(140)]),
            ("TG is 140 mg dl -1", [convert(140)]),
            ("TG-4", [4]),
            ("triglycerides    |       6.2 (H)      | mmol/L", [6.2]),
            ("Triglyceride level (X772O) 4", [4]),
            ("Plasma triglyceride level (44e..) 4", [4]),
            ("Plasma rndm triglyceride level (44e0.) 4", [4]),
            ("Plasma fast triglyceride level (44e1.) 4", [4]),
            ("Serum triglyceride levels (XE2q9) 4", [4]),
            ("Serum fasting triglyceride lev (44Q4.) 4", [4]),
            ("Serum random triglyceride lev (44Q5.) 4", [4]),
        ], verbose=verbose)


class TriglyceridesValidator(ValidatorBase):
    """
    Validator for triglycerides
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return Triglycerides.NAME, [Triglycerides.TG]


# =============================================================================
# HbA1c
# =============================================================================

def hba1c_mmol_per_mol_from_percent(percent: Union[float, str]) \
        -> Optional[float]:
    """
    Convert an HbA1c value from old percentage units -- DCCT (Diabetes Control
    and Complications Trial), UKPDS (United Kingdom Prospective Diabetes Study)
    or NGSP (National Glycohemoglobin Standardization Program) -- to newer IFCC
    (International Federation of Clinical Chemistry) mmol/mol units (mmol HbA1c
    / mol Hb).

    Args:
        percent: DCCT value as a percentage

    Returns:
        IFCC value in mmol/mol

    Example: 5% becomes 31.1 mmol/mol.

    By Emanuele Osimo, Feb 2019.
    Some modifications by Rudolf Cardinal, Feb 2019.

    References:

    - Emanuele had mmol_per_mol = (percent - 2.14) * 10.929 -- primary source
      awaited.
    - Jeppsson 2002, https://www.ncbi.nlm.nih.gov/pubmed/11916276 -- no, that's
      the chemistry
    - https://www.ifcchba1c.org/
    - http://www.ngsp.org/ifccngsp.asp -- gives master equation of
      NGSP = [0.09148 × IFCC] + 2.152), therefore implying
      IFCC = (NGSP – 2.152) × 10.93135.
    - Little & Rohlfing 2013: https://www.ncbi.nlm.nih.gov/pubmed/23318564;
      also gives NGSP = [0.09148 * IFCC] + 2.152.

    Note also that you may see eAG values (estimated average glucose), in
    mmol/L or mg/dl; see http://www.ngsp.org/A1ceAG.asp; these are not direct
    measurements of HbA1c.

    """
    if isinstance(percent, str):
        percent = to_float(percent)
    if not percent:
        return None
    percent = abs(percent)  # deals with e.g. "HbA1c-8%" -> -8
    return (percent - 2.152) * 10.93135


class HbA1c(SimpleNumericalResultParser):
    """
    Glycosylated (glycated) haemoglobin (HbA1c).

    - By Emanuele Osimo, Feb 2019.
    - Some modifications by Rudolf Cardinal, Feb 2019.

    Note: HbA1 is different
    (https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2541274).
    """
    HBA1C_BASE = fr"""
        {WORD_BOUNDARY}
        (?:
            (?: Glyc(?:osyl)?ated [-\s]+ (?:ha?emoglobin|Hb) ) |
            HbA1c
        )
        {WORD_BOUNDARY}
    """
    HBA1C = regex_or(
        *regex_components_from_read_codes(
            ReadCodes.HBA1C,
            ReadCodes.HBA1C_DCCT,
            ReadCodes.HBA1C_IFCC,
        ),
        HBA1C_BASE,
        wrap_each_in_noncapture_group=True,
        wrap_result_in_noncapture_group=False
    )
    REGEX = make_simple_numeric_regex(
        quantity=HBA1C,
        units=regex_or(
            MILLIMOLES_PER_MOL,  # standard
            PERCENT,  # good but needs conversion
            MILLIMOLES_PER_L,  # bad; may be an eAG value
            MG_PER_DL,  # bad; may be an eAG value
        )
    )
    NAME = "HBA1C"
    PREFERRED_UNIT_COLUMN = "value_mmol_mol"
    UNIT_MAPPING = {
        MILLIMOLES_PER_MOL: 1,       # preferred unit
        PERCENT: hba1c_mmol_per_mol_from_percent,
        # but not MILLIMOLES_PER_L
        # and not MG_PER_DL
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfg_processor_name: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in parent class

        def convert(percent: float) -> float:
            # Convert % to mmol/mol
            return hba1c_mmol_per_mol_from_percent(percent)

        self.test_numerical_parser([
            ("HbA1c", []),  # should fail; no values
            ("glycosylated haemoglobin", []),  # should fail; no values
            ("HbA1c 31", [31]),
            ("HbA1c 31 mmol/mol", [31]),
            ("HbA1c 31 mg/dl", []),  # wrong units
            ("HbA1c 31 mmol/L", []),  # wrong units
            ("glycosylated haemoglobin 31 mmol/mol", [31]),
            ("glycated hemoglobin 31 mmol/mol", [31]),
            ("HbA1c 8%", [convert(8)]),
            ("HbA1c = 8%", [convert(8)]),
            ("HbA1c: 31", [31]),
            ("HbA1c equals 31", [31]),
            ("HbA1c is equal to 31", [31]),
            ("HbA1c <31.2", [31.2]),
            ("HbA1c less than 4", [4]),
            ("HbA1c more than 20", [20]),
            ("HbA1c was 31", [31]),
            ("HbA1c was 15%", [convert(15)]),
            ("HbA1c-31", [31]),
            ("HbA1c-8%", [convert(8)]),
            ("HbA1c    |       40 (H)      | mmol/mol", [40]),
            ("Haemoglobin A1c level (X772q) 8%", [convert(8)]),
            ("HbA1c level (DCCT aligned) (XaERp) 8%", [convert(8)]),
            ("HbA1c levl - IFCC standardised (XaPbt) 31 mmol/mol", [31]),
        ], verbose=verbose)


class HbA1cValidator(ValidatorBase):
    """
    Validator for HbA1c
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return HbA1c.NAME, [HbA1c.HBA1C]


# =============================================================================
# All classes in this module
# =============================================================================

ALL_BIOCHEMISTRY_NLP_AND_VALIDATORS = [
    (Albumin, AlbuminValidator),
    (AlkPhos, AlkPhosValidator),
    (ALT, ALTValidator),
    (Bilirubin, BilirubinValidator),
    (Creatinine, CreatinineValidator),
    (Crp, CrpValidator),
    (GammaGT, GammaGTValidator),
    (Glucose, GlucoseValidator),
    (HbA1c, HbA1cValidator),
    (HDLCholesterol, HDLCholesterolValidator),
    (LDLCholesterol, LDLCholesterolValidator),
    (Lithium, LithiumValidator),
    (Potassium, PotassiumValidator),
    (Sodium, SodiumValidator),
    (TotalCholesterol, TotalCholesterolValidator),
    (Triglycerides, TriglyceridesValidator),
    (Tsh, TshValidator),
    (Urea, UreaValidator),
]
ALL_BIOCHEMISTRY_NLP, ALL_BIOCHEMISTRY_VALIDATORS = zip(*ALL_BIOCHEMISTRY_NLP_AND_VALIDATORS)  # noqa


# =============================================================================
# Command-line entry point
# =============================================================================

def test_all(verbose: bool = False) -> None:
    """
    Test all parsers in this module.
    """
    for cls in ALL_BIOCHEMISTRY_NLP:
        cls(None, None).test(verbose=verbose)


if __name__ == '__main__':
    main_only_quicksetup_rootlogger(level=logging.DEBUG)
    test_all(verbose=True)
