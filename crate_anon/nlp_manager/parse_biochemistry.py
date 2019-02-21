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
from typing import Optional

from crate_anon.nlp_manager.nlp_definition import NlpDefinition
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
    G,
    MG,
    MG_PER_DL,
    MG_PER_L,
    MICROUNITS_PER_ML,
    MILLIMOLAR,
    MILLIMOLES_PER_L,
    MILLIEQ_PER_L,
    MILLIUNITS_PER_L,
)

log = logging.getLogger(__name__)


# =============================================================================
#  C-reactive protein (CRP)
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

    CRP = r"""
        (?: {WORD_BOUNDARY}
            (?: (?: C [-\s]+ reactive [\s]+ protein ) | (?: CRP ) )
        {WORD_BOUNDARY} )
    """.format(WORD_BOUNDARY=WORD_BOUNDARY)
    REGEX = r"""
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
    """.format(
        CRP=CRP,
        OPTIONAL_RESULTS_IGNORABLES=OPTIONAL_RESULTS_IGNORABLES,
        TENSE_INDICATOR=TENSE_INDICATOR,
        RELATION=RELATION,
        SIGNED_FLOAT=SIGNED_FLOAT,
        MG_PER_DL=MG_PER_DL,
        MG_PER_L=MG_PER_L,
    )
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
#  Sodium (Na)
# =============================================================================
# ... handy to check approximately expected distribution of results!

class Sodium(SimpleNumericalResultParser):
    """
    Sodium (Na).
    """
    SODIUM = r"""
        (?: {WORD_BOUNDARY} (?: Na | Sodium ) {WORD_BOUNDARY} )
    """.format(WORD_BOUNDARY=WORD_BOUNDARY)
    REGEX = r"""
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
    """.format(
        SODIUM=SODIUM,
        OPTIONAL_RESULTS_IGNORABLES=OPTIONAL_RESULTS_IGNORABLES,
        TENSE_INDICATOR=TENSE_INDICATOR,
        RELATION=RELATION,
        SIGNED_FLOAT=SIGNED_FLOAT,
        MILLIMOLAR=MILLIMOLAR,
        MILLIMOLES_PER_L=MILLIMOLES_PER_L,
        MILLIEQ_PER_L=MILLIEQ_PER_L,
        MG=MG,
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
#  Lithium (Li)
# =============================================================================

class Lithium(SimpleNumericalResultParser):
    """
    Lithium (Li) levels (for blood tests, not doses).
    """
    LITHIUM = r"""
        (?: {WORD_BOUNDARY} (?: Li | Lithium ) {WORD_BOUNDARY} )
    """.format(WORD_BOUNDARY=WORD_BOUNDARY)
    REGEX = r"""
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
    """.format(
        LITHIUM=LITHIUM,
        OPTIONAL_RESULTS_IGNORABLES=OPTIONAL_RESULTS_IGNORABLES,
        TENSE_INDICATOR=TENSE_INDICATOR,
        RELATION=RELATION,
        SIGNED_FLOAT=SIGNED_FLOAT,
        MILLIMOLAR=MILLIMOLAR,
        MILLIMOLES_PER_L=MILLIMOLES_PER_L,
        MILLIEQ_PER_L=MILLIEQ_PER_L,
        MG=MG,
        G=G,
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
#  Thyroid-stimulating hormone (TSH)
# =============================================================================

class Tsh(SimpleNumericalResultParser):
    """
    Thyroid-stimulating hormone (TSH).
    """
    TSH = r"""
        (?: {WORD_BOUNDARY}
            (?: TSH | thyroid [-\s]+ stimulating [-\s]+ hormone )
        {WORD_BOUNDARY} )
    """.format(WORD_BOUNDARY=WORD_BOUNDARY)
    REGEX = r"""
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
    """.format(
        TSH=TSH,
        OPTIONAL_RESULTS_IGNORABLES=OPTIONAL_RESULTS_IGNORABLES,
        TENSE_INDICATOR=TENSE_INDICATOR,
        RELATION=RELATION,
        SIGNED_FLOAT=SIGNED_FLOAT,
        MILLIUNITS_PER_L=MILLIUNITS_PER_L,
        MICROUNITS_PER_ML=MICROUNITS_PER_ML,
    )
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
#  Command-line entry point
# =============================================================================

def test_all(verbose: bool = False) -> None:
    crp = Crp(None, None)
    crp.test(verbose=verbose)
    na = Sodium(None, None)
    na.test(verbose=verbose)
    li = Lithium(None, None)
    li.test(verbose=verbose)
    tsh = Tsh(None, None)
    tsh.test(verbose=verbose)


if __name__ == '__main__':
    test_all(verbose=True)
