#!/usr/bin/env python
# crate_anon/nlp_manager/parse_biochemistry.py

import logging
from typing import Optional

from crate_anon.nlp_manager.nlp_definition import NlpDefinition
from crate_anon.nlp_manager.regex_parser import (
    NumericalResultParser,
    ValidatorBase,
    OPTIONAL_RESULTS_IGNORABLES,
    RELATION,
    SIGNED_FLOAT,
    TENSE_INDICATOR,
    MG_PER_DL,
    MG_PER_L,
    WORD_BOUNDARY,
    MILLIMOLAR,
    MILLIMOLES_PER_L,
    MILLIEQ_PER_L,
)

log = logging.getLogger(__name__)


# =============================================================================
#  C-reactive protein (CRP)
# =============================================================================

class Crp(NumericalResultParser):
    """C-reactive protein.

    CRP units:
    - mg/L is commonest in the UK (or at least standard at Addenbrooke's,
      Hinchingbrooke, and Dundee)
    - values of <=6 mg/L or <10 mg/L are normal, and e.g. 70-250 mg/L in
      pneumonia.
    - Refs include:
            http://www.ncbi.nlm.nih.gov/pubmed/7705110
            http://emedicine.medscape.com/article/2086909-overview
    - 1 mg/dL = 10 mg/L
        ... so normal in mg/dL is <=1 roughly.
    """

    CRP = r"""
        (?:
            {WORD_BOUNDARY}
            (?:
                (?: C [-\s]+ reactive [\s]+ protein )
                | (?: CRP )
            )
            {WORD_BOUNDARY}
        )
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
        ( {UNITS_MG_DL} | {UNITS_MG_L} )?  # optional group for units
    """.format(
        CRP=CRP,
        OPTIONAL_RESULTS_IGNORABLES=OPTIONAL_RESULTS_IGNORABLES,
        TENSE_INDICATOR=TENSE_INDICATOR,
        RELATION=RELATION,
        SIGNED_FLOAT=SIGNED_FLOAT,
        UNITS_MG_DL=MG_PER_DL,
        UNITS_MG_L=MG_PER_L,
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
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit
        )

    def test(self):
        self.test_parser([
            "CRP",  # should fail; no values
            "CRP 6",
            "CRP = 6",
            "CRP 6 mg/dl",
            "CRP <1",
            "CRP <1 mg/dl",
            "CRP >250",
            "CRP >250 mg/dl",
            "CRP was 62",
            "CRP was 62 mg/l",
            "CRP was <1",
            "CRP is 19",
            "CRP is >250",
            "CRP is 19 mg dl-1",
            "CRP is 19 mg dl -1",
            "CRP 1.9 mg/L",
            "CRP 1.9 mg L-1",
            "CRP        |       1.9 (H)      | mg/L",
        ])


class CrpValidator(ValidatorBase):
    """Validator for CRP (see ValidatorBase for explanation)."""
    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         regex_str=Crp.CRP,
                         validated_variable=Crp.NAME,
                         commit=commit)


# =============================================================================
#  Sodium (Na)
# =============================================================================
# ... handy to check approximately expected distribution of results!

class Sodium(NumericalResultParser):
    """Sodium (Na)."""
    SODIUM = r"""
        (?:
            {WORD_BOUNDARY}
            (?:
                Na
                | Sodium
            )
            {WORD_BOUNDARY}
        )
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
            {MILLIMOLAR}
            | {UNITS_MILLIMOLES_L}
            | {UNITS_MILLIEQ_L}
        )?
    """.format(
        SODIUM=SODIUM,
        OPTIONAL_RESULTS_IGNORABLES=OPTIONAL_RESULTS_IGNORABLES,
        TENSE_INDICATOR=TENSE_INDICATOR,
        RELATION=RELATION,
        SIGNED_FLOAT=SIGNED_FLOAT,
        MILLIMOLAR=MILLIMOLAR,
        UNITS_MILLIMOLES_L=MILLIMOLES_PER_L,
        UNITS_MILLIEQ_L=MILLIEQ_PER_L,
    )
    NAME = "Sodium"
    PREFERRED_UNIT_COLUMN = "value_mmol_L"
    UNIT_MAPPING = {
        MILLIMOLAR: 1,       # preferred unit
        MILLIMOLES_PER_L: 1,
        MILLIEQ_PER_L: 1,
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
            regex_str=self.REGEX,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            units_to_factor=self.UNIT_MAPPING,
            commit=commit
        )

    def test(self):
        self.test_parser([
            "Na",  # should fail; no values
            "Na 120",
            "sodium 153",
            "Na 135 mEq/L",
            "Na 139 mM",
        ])


class SodiumValidator(ValidatorBase):
    """Validator for Sodium (see ValidatorBase for explanation)."""
    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         regex_str=Sodium.SODIUM,
                         validated_variable=Sodium.NAME,
                         commit=commit)


# =============================================================================
#  Command-line entry point
# =============================================================================

if __name__ == '__main__':
    crp = Crp(None, None)
    crp.test()
    na = Sodium(None, None)
    na.test()
