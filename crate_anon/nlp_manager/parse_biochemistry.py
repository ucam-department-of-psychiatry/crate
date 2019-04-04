#!/usr/bin/env python

"""
crate_anon/nlp_manager/parse_biochemistry.py

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
from typing import Optional, Union

from crate_anon.nlp_manager.nlp_definition import NlpDefinition
from crate_anon.nlp_manager.number import to_float
from crate_anon.nlp_manager.regex_parser import (
    OPTIONAL_RESULTS_IGNORABLES,
    RELATION,
    SimpleNumericalResultParser,
    TENSE_INDICATOR,
    ValidatorBase,
    WORD_BOUNDARY,
)
from crate_anon.nlp_manager.regex_numbers import SIGNED_FLOAT
from crate_anon.nlp_manager.regex_units import (
    factor_micromolar_from_mg_per_dl,
    factor_millimolar_from_mg_per_dl,
    G,
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
      Hinchingbrooke, and Dundee)

    - values of <=6 mg/L or <10 mg/L are normal, and e.g. 70-250 mg/L in
      pneumonia.

    - Refs include:
      - http://www.ncbi.nlm.nih.gov/pubmed/7705110
      - http://emedicine.medscape.com/article/2086909-overview

    - 1 mg/dL = 10 mg/L, so normal in mg/dL is <=1 roughly.

    """

    CRP = fr"""
        (?: {WORD_BOUNDARY}
            (?: (?: C [-\s]+ reactive [\s]+ protein ) | (?: CRP ) )
        {WORD_BOUNDARY} )
    """
    REGEX = fr"""
        ( {CRP} )                          # group for "CRP" or equivalent
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?             # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                    # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {SIGNED_FLOAT} )                 # group for value
        {OPTIONAL_RESULTS_IGNORABLES}
        (                                  # optional group for units
            {MG_PER_DL}
            | {MG_PER_L}
        )?
    """
    NAME = "CRP"
    PREFERRED_UNIT_COLUMN = "value_mg_l"
    UNIT_MAPPING = {
        MG_PER_L: 1,       # preferred unit
        MG_PER_DL: 10,     # 1 mg/dL -> 10 mg/L
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
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
        ], verbose=verbose)


class CrpValidator(ValidatorBase):
    """
    Validator for CRP
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         regex_str_list=[Crp.CRP],
                         validated_variable=Crp.NAME,
                         commit=commit)


# =============================================================================
# Sodium (Na)
# =============================================================================
# ... handy to check approximately expected distribution of results!

class Sodium(SimpleNumericalResultParser):
    """
    Sodium (Na).
    """
    SODIUM = fr"""
        (?: {WORD_BOUNDARY} (?: Na | Sodium ) {WORD_BOUNDARY} )
    """
    REGEX = fr"""
        ( {SODIUM} )                       # group for "Na" or equivalent
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?             # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                    # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {SIGNED_FLOAT} )                 # group for value
        {OPTIONAL_RESULTS_IGNORABLES}
        (                                  # optional group for units
            {MILLIMOLAR}                        # good
            | {MILLIMOLES_PER_L}                # good
            | {MILLIEQ_PER_L}                   # good
            | {MG}                              # bad
        )?
    """
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
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
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
            ("Na-145", [145])
        ], verbose=verbose)


class SodiumValidator(ValidatorBase):
    """
    Validator for Sodium
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         regex_str_list=[Sodium.SODIUM],
                         validated_variable=Sodium.NAME,
                         commit=commit)


# =============================================================================
# Potassium (K)
# =============================================================================

class Potassium(SimpleNumericalResultParser):
    """
    Potassium (K).
    """
    POTASSIUM = fr"""
        (?: {WORD_BOUNDARY} (?: K | Potassium ) {WORD_BOUNDARY} )
    """
    REGEX = fr"""
        ( {POTASSIUM} )                    # group for "K" or equivalent
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?             # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                    # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {SIGNED_FLOAT} )                 # group for value
        {OPTIONAL_RESULTS_IGNORABLES}
        (                                  # optional group for units
            {MILLIMOLAR}                        # good
            | {MILLIMOLES_PER_L}                # good
            | {MILLIEQ_PER_L}                   # good
            | {MG}                              # bad
        )?
    """
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
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
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
            ("K-3.2", [3.2])
        ], verbose=verbose)


class PotassiumValidator(ValidatorBase):
    """
    Validator for Potassium
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         regex_str_list=[Potassium.POTASSIUM],
                         validated_variable=Potassium.NAME,
                         commit=commit)


# =============================================================================
# Urea
# =============================================================================

class Urea(SimpleNumericalResultParser):
    """
    Urea.
    """
    UREA = fr"""
        (?: {WORD_BOUNDARY} (?: U(?:r(?:ea)?)? ) {WORD_BOUNDARY} )
    """
    REGEX = fr"""
        ( {UREA} )                         # group for "urea" or equivalent
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?             # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                    # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {SIGNED_FLOAT} )                 # group for value
        {OPTIONAL_RESULTS_IGNORABLES}
        (                                  # optional group for units
            {MILLIMOLAR}                        # good
            | {MILLIMOLES_PER_L}                # good
            | {MILLIEQ_PER_L}                   # good
            | {MG}                              # bad
        )?
    """
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
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
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
            ("U-3.2", [3.2])
        ], verbose=verbose)


class UreaValidator(ValidatorBase):
    """
    Validator for Urea
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         regex_str_list=[Urea.UREA],
                         validated_variable=Urea.NAME,
                         commit=commit)


# =============================================================================
# Creatinine
# =============================================================================

class Creatinine(SimpleNumericalResultParser):
    """
    Creatinine. Default units are micromolar (SI).
    """
    CREATININE = fr"""
        (?: {WORD_BOUNDARY} (?: Cr(?:eat(?:inine)?)? ) {WORD_BOUNDARY} )
    """
    # ... Cr, Creat, Creatinine
    # Possible that "creatine" is present as a typo... but it's wrong...
    REGEX = fr"""
        ( {CREATININE} )                 # group for "creatinine" or equivalent
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?           # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                  # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {SIGNED_FLOAT} )               # group for value
        {OPTIONAL_RESULTS_IGNORABLES}
        (                                # optional group for units
            {MICROMOLAR}                        # good
            | {MICROMOLES_PER_L}                # good
            | {MICROEQ_PER_L}                   # good
            | {MG_PER_DL}                       # good but needs conversion
            | {MG}                              # bad
        )?
    """
    # ... note that MG_PER_DL must precede MG
    CREATININE_MOLECULAR_MASS_G_PER_MOL = 113.12
    # ... https://pubchem.ncbi.nlm.nih.gov/compound/creatinine
    NAME = "Creatinine"
    PREFERRED_UNIT_COLUMN = "value_mmol_L"
    UNIT_MAPPING = {
        MICROMOLAR: 1,       # preferred unit
        MICROMOLES_PER_L: 1,
        MICROEQ_PER_L: 1,
        MG_PER_DL: factor_micromolar_from_mg_per_dl(CREATININE_MOLECULAR_MASS_G_PER_MOL)  # noqa
        # but not MG
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
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
            ("blah (creat) 5.6 uM", []),
            ("Creatinine (200) something", [200]),
            ("Creatinine (200 micromolar), others", [200]),
            ("Cr-75", [75]),
            ("creatinine 3 mg/dl", [convert(3)]),
            ("creatinine 3 mg", []),
        ], verbose=verbose)


class CreatinineValidator(ValidatorBase):
    """
    Validator for Creatinine
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         regex_str_list=[Creatinine.CREATININE],
                         validated_variable=Creatinine.NAME,
                         commit=commit)


# =============================================================================
# Lithium (Li)
# =============================================================================

class Lithium(SimpleNumericalResultParser):
    """
    Lithium (Li) levels (for blood tests, not doses).
    """
    LITHIUM = fr"""
        (?: {WORD_BOUNDARY} (?: Li | Lithium ) {WORD_BOUNDARY} )
    """
    REGEX = fr"""
        ( {LITHIUM} )                      # group for "Li" or equivalent
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?             # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                    # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {SIGNED_FLOAT} )                 # group for value
        {OPTIONAL_RESULTS_IGNORABLES}
        (                                  # optional group for units
            {MILLIMOLAR}                        # good
            | {MILLIMOLES_PER_L}                # good
            | {MILLIEQ_PER_L}                   # good
            | {MG}                              # bad
            | {G}                               # bad
        )?
    """
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
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
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
            ("Li-0.4", [0.4])
        ], verbose=verbose)


class LithiumValidator(ValidatorBase):
    """
    Validator for Lithium
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         regex_str_list=[Lithium.LITHIUM],
                         validated_variable=Lithium.NAME,
                         commit=commit)


# =============================================================================
# Thyroid-stimulating hormone (TSH)
# =============================================================================

class Tsh(SimpleNumericalResultParser):
    """
    Thyroid-stimulating hormone (TSH).
    """
    TSH = fr"""
        (?: {WORD_BOUNDARY}
            (?: TSH | thyroid [-\s]+ stimulating [-\s]+ hormone )
        {WORD_BOUNDARY} )
    """
    REGEX = fr"""
        ( {TSH} )                          # group for "TSH" or equivalent
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?             # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                    # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {SIGNED_FLOAT} )                 # group for value
        {OPTIONAL_RESULTS_IGNORABLES}
        (                                  # optional group for units
            {MILLIUNITS_PER_L}                 # good
            | {MICROUNITS_PER_ML}              # good
        )?
    """
    NAME = "TSH"
    PREFERRED_UNIT_COLUMN = "value_mU_L"
    UNIT_MAPPING = {
        MILLIUNITS_PER_L: 1,       # preferred unit
        MICROUNITS_PER_ML: 1,
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
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
            ("TSH-2.3", [2.3])
        ])


class TshValidator(ValidatorBase):
    """
    Validator for TSH
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         regex_str_list=[Tsh.TSH],
                         validated_variable=Tsh.NAME,
                         commit=commit)


# =============================================================================
# Glucose
# =============================================================================

class Glucose(SimpleNumericalResultParser):
    """
    Glucose.

    - By Emanuele Osimo, Feb 2019.
    - Some modifications by Rudolf Cardinal, Feb 2019.
    """
    GLUCOSE = fr"""
        (?: {WORD_BOUNDARY} (?: glu(?:c(?:ose)?)? ) {WORD_BOUNDARY} )
        # glu, gluc, glucose
    """
    REGEX = fr"""
        ( {GLUCOSE} )                      # group for glucose or equivalent
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?             # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                    # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {SIGNED_FLOAT} )                 # group for value
        {OPTIONAL_RESULTS_IGNORABLES}
        (                                  # optional group for units
            {MILLIMOLAR}                        # good
            | {MILLIMOLES_PER_L}                # good
            | {MG_PER_DL}                       # good but needs conversion
        )?
    """
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
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
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
        ], verbose=verbose)


class GlucoseValidator(ValidatorBase):
    """
    Validator for glucose
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         regex_str_list=[Glucose.GLUCOSE],
                         validated_variable=Glucose.NAME,
                         commit=commit)


# =============================================================================
# LDL cholesterol
# =============================================================================

class LDLCholesterol(SimpleNumericalResultParser):
    """
    Low density lipoprotein (LDL) cholesterol.

    - By Emanuele Osimo, Feb 2019.
    - Some modifications by Rudolf Cardinal, Feb 2019.
    """
    LDL = fr"""
        (?: {WORD_BOUNDARY}
            (?: LDL [-\s]* (?:chol(?:esterol)? )? )
        {WORD_BOUNDARY} )
    """
    REGEX = fr"""
        ( {LDL} )                       # group for LDL or equivalent
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?             # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                    # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {SIGNED_FLOAT} )                 # group for value
        {OPTIONAL_RESULTS_IGNORABLES}
        (                                  # optional group for units
            {MILLIMOLAR}                        # good
            | {MILLIMOLES_PER_L}                # good
            | {MG_PER_DL}                       # OK but needs conversion
        )?
    """
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
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
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
            ("LDL chol. 4 mmol", []),
            # ... NOT picked up at present; see word boundary condition; problem?  # noqa
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
        ], verbose=verbose)


class LDLCholesterolValidator(ValidatorBase):
    """
    Validator for LDL cholesterol
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         regex_str_list=[LDLCholesterol.LDL],
                         validated_variable=LDLCholesterol.NAME,
                         commit=commit)


# =============================================================================
# HDL cholesterol
# =============================================================================

class HDLCholesterol(SimpleNumericalResultParser):
    """
    High-density lipoprotein (HDL) cholesterol.

    - By Emanuele Osimo, Feb 2019.
    - Some modifications by Rudolf Cardinal, Feb 2019.
    """
    HDL = fr"""
        (?: {WORD_BOUNDARY}
            (?: HDL [-\s]* (?:chol(?:esterol)? )? )
        {WORD_BOUNDARY} )
    """
    REGEX = fr"""
        ( {HDL} )                       # group for HDL or equivalent
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?             # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                    # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {SIGNED_FLOAT} )                 # group for value
        {OPTIONAL_RESULTS_IGNORABLES}
        (                                  # optional group for units
            {MILLIMOLAR}                        # good
            | {MILLIMOLES_PER_L}                # good
            | {MG_PER_DL}                       # OK but needs conversion
        )?
    """
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
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
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
            ("HDL chol. 4 mmol", []),
            # ... NOT picked up at present; see word boundary condition; problem?  # noqa
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
        ], verbose=verbose)


class HDLCholesterolValidator(ValidatorBase):
    """
    Validator for HDL cholesterol
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         regex_str_list=[HDLCholesterol.HDL],
                         validated_variable=HDLCholesterol.NAME,
                         commit=commit)


# =============================================================================
# Total cholesterol
# =============================================================================

class TotalCholesterol(SimpleNumericalResultParser):
    """
    Total cholesterol.
    """
    CHOLESTEROL = fr"""
        (?: 
            {WORD_BOUNDARY}
            (?<!HDL[-\s]+) (?<!LDL[-\s]+)  # not preceded by HDL or LDL 
            (?: tot(?:al) [-\s] )?         # optional "total" prefix
            (?: chol(?:esterol)? )         # cholesterol
        {WORD_BOUNDARY} )
    """
    # ... (?<! something ) is a negative lookbehind assertion
    REGEX = fr"""
        ( {CHOLESTEROL} )                  # group for cholesterol or equivalent
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?             # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                    # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {SIGNED_FLOAT} )                 # group for value
        {OPTIONAL_RESULTS_IGNORABLES}
        (                                  # optional group for units
            {MILLIMOLAR}                        # good
            | {MILLIMOLES_PER_L}                # good
            | {MG_PER_DL}                       # OK but needs conversion
        )?
    """
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
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
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
            ("chol. 4 mmol", []),
            # ... NOT picked up at present; see word boundary condition; problem?  # noqa
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
        ], verbose=verbose)


class TotalCholesterolValidator(ValidatorBase):
    """
    Validator for total cholesterol
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         regex_str_list=[TotalCholesterol.CHOLESTEROL],
                         validated_variable=TotalCholesterol.NAME,
                         commit=commit)


# =============================================================================
# Triglycerides
# =============================================================================

class Triglycerides(SimpleNumericalResultParser):
    """
    Triglycerides.

    - By Emanuele Osimo, Feb 2019.
    - Some modifications by Rudolf Cardinal, Feb 2019.
    """
    TG = fr"""
        (?: {WORD_BOUNDARY}
            (?: (?: Triglyceride[s]? | TG ) )
        {WORD_BOUNDARY} )
    """
    REGEX = fr"""
        ( {TG} )                        # group for triglycerides or equivalent
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?             # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                    # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {SIGNED_FLOAT} )                 # group for value
        {OPTIONAL_RESULTS_IGNORABLES}
        (                                  # optional group for units
            {MILLIMOLAR}                        # good
            | {MILLIMOLES_PER_L}                # good
            | {MG_PER_DL}                       # OK but needs conversion
        )?
    """
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
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
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
        ], verbose=verbose)


class TriglyceridesValidator(ValidatorBase):
    """
    Validator for triglycerides
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         regex_str_list=[Triglycerides.TG],
                         validated_variable=Triglycerides.NAME,
                         commit=commit)


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
    """
    HBA1C = fr"""
        (?: {WORD_BOUNDARY}
            (?: (?: Glyc(?:osyl)?ated [-\s]+ (?:ha?emoglobin|Hb) ) |
                (?: HbA1c )
            )
        {WORD_BOUNDARY} )
    """
    REGEX = fr"""
        ( {HBA1C} )                       # group for HbA1c or equivalent
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?             # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                    # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {SIGNED_FLOAT} )                 # group for value
        {OPTIONAL_RESULTS_IGNORABLES}
        (                                  # optional group for units
            {MILLIMOLES_PER_MOL}                # standard
            | {PERCENT}                         # good but needs conversion
            | {MILLIMOLES_PER_L}                # bad; may be an eAG value
            | {MG_PER_DL}                       # bad; may be an eAG value
        )?
    """
    NAME = "HBA1C"
    PREFERRED_UNIT_COLUMN = "value_mmol_L"
    UNIT_MAPPING = {
        MILLIMOLES_PER_MOL: 1,       # preferred unit
        PERCENT: hba1c_mmol_per_mol_from_percent,
        # but not MILLIMOLES_PER_L
        # and not MG_PER_DL
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
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
        ], verbose=verbose)


class HbA1cValidator(ValidatorBase):
    """
    Validator for HbA1c
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        # see documentation above
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         regex_str_list=[HbA1c.HBA1C],
                         validated_variable=HbA1c.NAME,
                         commit=commit)


# =============================================================================
# Command-line entry point
# =============================================================================

def test_all(verbose: bool = False) -> None:
    Crp(None, None).test(verbose=verbose)
    Sodium(None, None).test(verbose=verbose)
    Potassium(None, None).test(verbose=verbose)
    Urea(None, None).test(verbose=verbose)
    Creatinine(None, None).test(verbose=verbose)
    Lithium(None, None).test(verbose=verbose)
    Tsh(None, None).test(verbose=verbose)
    Glucose(None, None).test(verbose=verbose)
    LDLCholesterol(None, None).test(verbose=verbose)
    HDLCholesterol(None, None).test(verbose=verbose)
    TotalCholesterol(None, None).test(verbose=verbose)
    Triglycerides(None, None).test(verbose=verbose)
    HbA1c(None, None).test(verbose=verbose)


if __name__ == '__main__':
    test_all(verbose=True)
