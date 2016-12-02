#!/usr/bin/env python
# crate_anon/nlp_manager/parse_cognitive.py

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
from crate_anon.nlp_manager.regex_units import out_of, out_of_anything, SCORE

log = logging.getLogger(__name__)


# =============================================================================
# Mini-mental state examination (MMSE)
# =============================================================================

class Mmse(SimpleNumericalResultParser):
    """Mini-mental state examination (MMSE)."""
    MMSE = r"""
        (?:
            {WORD_BOUNDARY}
            (?:
                MMSE
                | mini[-\s]*mental (?: \s+ state)? (?: \s+ exam(?:ination)? )?
            )
            {WORD_BOUNDARY}
        )
    """.format(WORD_BOUNDARY=WORD_BOUNDARY)
    OUT_OF_30 = out_of(30)
    REGEX = r"""
        ( {MMSE} )                         # group for "MMSE" or equivalent
        {OPTIONAL_RESULTS_IGNORABLES}
        {SCORE}?                           # optional "score" or similar
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?             # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                    # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {SIGNED_FLOAT} )                 # group for value
        {OPTIONAL_RESULTS_IGNORABLES}
        (                                  # group for units
            {OUT_OF_30}                         # good
            | {OUT_OF_ANYTHING}                 # bad
        )?
    """.format(
        MMSE=MMSE,
        OPTIONAL_RESULTS_IGNORABLES=OPTIONAL_RESULTS_IGNORABLES,
        SCORE=SCORE,
        TENSE_INDICATOR=TENSE_INDICATOR,
        RELATION=RELATION,
        SIGNED_FLOAT=SIGNED_FLOAT,
        OUT_OF_30=OUT_OF_30,
        OUT_OF_ANYTHING=out_of_anything(),
    )
    NAME = "MMSE"
    PREFERRED_UNIT_COLUMN = "out_of_30"
    UNIT_MAPPING = {
        OUT_OF_30: 1,       # preferred unit
        # not out_of_anything()
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
            commit=commit,
            take_absolute=True
        )

    def test(self):
        self.test_numerical_parser([
            ("MMSE", []),  # should fail; no values
            ("MMSE 30/30", [30]),
            ("MMSE 25 / 30", [25]),
            ("MMSE 25 / 29", []),
            ("MMSE 25 / 31", []),
            ("mini-mental state exam 30", [30]),
            ("minimental 25", [25]),
            ("MMSE 30", [30]),
            ("MMSE-27", [27]),
            ("MMSE score was 30", [30]),
            ("ACE 79", []),
        ])


class MmseValidator(ValidatorBase):
    """Validator for Mmse (see ValidatorBase for explanation)."""
    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         regex_str_list=[Mmse.MMSE],
                         validated_variable=Mmse.NAME,
                         commit=commit)


# =============================================================================
# Addenbrooke's Cognitive Examination (ACE, ACE-R, ACE-III)
# =============================================================================

class Ace(SimpleNumericalResultParser):
    """Addenbrooke's Cognitive Examination (ACE, ACE-R, ACE-III)."""
    ACE = r"""
        (?:
            {WORD_BOUNDARY}
            (?:
                ACE
                | (?:
                    Addenbrooke'?s \s+ cognitive \s+
                    (?: (?:evaluation) | exam(?:ination)? )
                )
            )
            (?:
                (?: -? 3 )
                | (?: \s* -? \s* (?: R | III ) )
            )?
            {WORD_BOUNDARY}
        )
    """.format(WORD_BOUNDARY=WORD_BOUNDARY)
    OUT_OF_100 = out_of(100)
    REGEX = r"""
        ( {ACE} )                          # group for "ACE" or equivalent
        {OPTIONAL_RESULTS_IGNORABLES}
        {SCORE}?                           # optional "score" or similar
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?             # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                    # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {SIGNED_FLOAT} )                 # group for value
        {OPTIONAL_RESULTS_IGNORABLES}
        (                                  # group for units
            {OUT_OF_100}                        # good
            | {OUT_OF_ANYTHING}                 # bad
        )?
    """.format(
        ACE=ACE,
        OPTIONAL_RESULTS_IGNORABLES=OPTIONAL_RESULTS_IGNORABLES,
        SCORE=SCORE,
        TENSE_INDICATOR=TENSE_INDICATOR,
        RELATION=RELATION,
        SIGNED_FLOAT=SIGNED_FLOAT,
        OUT_OF_100=OUT_OF_100,
        OUT_OF_ANYTHING=out_of_anything(),
    )
    NAME = "ACE"
    PREFERRED_UNIT_COLUMN = "out_of_100"
    UNIT_MAPPING = {
        OUT_OF_100: 1,       # preferred unit
        # not out_of_anything()
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
            commit=commit,
            take_absolute=True
        )

    def test(self):
        self.test_numerical_parser([
            ("MMSE", []),
            ("MMSE 30/30", []),
            ("MMSE 25 / 30", []),
            ("mini-mental state exam 30", []),
            ("minimental 25", []),
            ("MMSE 30", []),
            ("ACE 79", [79]),
            ("ACE 79/100", [79]),
            ("ACE 79/95", []),
            ("ACE 79 / 100", [79]),
            ("Addenbrooke's cognitive examination 79", [79]),
            ("Addenbrookes cognitive evaluation 79", [79]),
            ("ACE-R 79", [79]),
            ("ACE-R 79 out of 100", [79]),
            ("ACE-III 79", [79]),
            ("ACE-III score was 79", [79]),
            ("ACE-3 79", [79]),
            ("ACE R 79", [79]),
            ("ACE III 79", [79]),
            ("ACE 3 79", [3]),  # nasty; not easy to cope with this well.
            ("ACE 3", [3]),
            ("ACE-82", [82]),
        ])


class AceValidator(ValidatorBase):
    """Validator for Ace (see ValidatorBase for explanation)."""
    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         regex_str_list=[Ace.ACE],
                         validated_variable=Ace.NAME,
                         commit=commit)


# =============================================================================
# Mini-Addenbrooke's Cognitive Examination (M-ACE)
# =============================================================================

class MiniAce(SimpleNumericalResultParser):
    """Mini-Addenbrooke's Cognitive Examination (M-ACE)."""
    MACE = r"""
        (?:
            {WORD_BOUNDARY}
            (?:
                mini | M
            )
            \s* -? \s*
            (?:
                ACE
                | (?:
                    Addenbrooke'?s \s+ cognitive \s+
                    (?: (?:evaluation) | exam(?:ination)? )
                )
            )
            {WORD_BOUNDARY}
        )
    """.format(WORD_BOUNDARY=WORD_BOUNDARY)
    OUT_OF_30 = out_of(30)
    REGEX = r"""
        ( {MACE} )                         # group for "M-ACE" or equivalent
        {OPTIONAL_RESULTS_IGNORABLES}
        {SCORE}?                           # optional "score" or similar
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?             # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                    # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {SIGNED_FLOAT} )                 # group for value
        {OPTIONAL_RESULTS_IGNORABLES}
        (                                  # group for units
            {OUT_OF_30}                         # good
            | {OUT_OF_ANYTHING}                 # bad
        )?
    """.format(
        MACE=MACE,
        OPTIONAL_RESULTS_IGNORABLES=OPTIONAL_RESULTS_IGNORABLES,
        SCORE=SCORE,
        TENSE_INDICATOR=TENSE_INDICATOR,
        RELATION=RELATION,
        SIGNED_FLOAT=SIGNED_FLOAT,
        OUT_OF_30=OUT_OF_30,
        OUT_OF_ANYTHING=out_of_anything(),
    )
    NAME = "MiniACE"
    PREFERRED_UNIT_COLUMN = "out_of_30"
    UNIT_MAPPING = {
        OUT_OF_30: 1,       # preferred unit
        # not out_of_anything()
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
            commit=commit,
            take_absolute=True
        )

    def test(self):
        self.test_numerical_parser([
            ("MMSE 30", []),
            ("ACE 79", []),
            ("ACE 79/100", []),
            ("Addenbrooke's cognitive examination 79", []),
            ("Addenbrookes cognitive evaluation 79", []),
            ("mini-Addenbrooke's cognitive examination 79", [79]),
            ("mini-Addenbrookes cognitive evaluation 79", [79]),
            ("M-ACE 20", [20]),
            ("M-ACE score is 20", [20]),
            ("M-ACE 29/30", [29]),
            ("M-ACE 29/29", []),
            ("MACE 29", [29]),
            ("MACE-29", [29]),
            ("mini-ACE 29", [29]),
        ])


class MiniAceValidator(ValidatorBase):
    """Validator for MiniAce (see ValidatorBase for explanation)."""
    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         regex_str_list=[MiniAce.MACE],
                         validated_variable=MiniAce.NAME,
                         commit=commit)


# =============================================================================
# Montreal Cognitive Assessment (MOCA)
# =============================================================================

class Moca(SimpleNumericalResultParser):
    """Montreal Cognitive Assessment (MOCA)."""
    MOCA = r"""
        (?:
            {WORD_BOUNDARY}
            (?:
                MOCA
                | (?:
                    Montreal \s+ cognitive \s+ assessment
                )
            )
            {WORD_BOUNDARY}
        )
    """.format(WORD_BOUNDARY=WORD_BOUNDARY)
    OUT_OF_30 = out_of(30)
    REGEX = r"""
        ( {MOCA} )                         # group for "M-ACE" or equivalent
        {OPTIONAL_RESULTS_IGNORABLES}
        {SCORE}?                           # optional "score" or similar
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?             # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                    # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {SIGNED_FLOAT} )                 # group for value
        {OPTIONAL_RESULTS_IGNORABLES}
        (                                  # group for units
            {OUT_OF_30}                         # good
            | {OUT_OF_ANYTHING}                 # bad
        )?
    """.format(
        MOCA=MOCA,
        OPTIONAL_RESULTS_IGNORABLES=OPTIONAL_RESULTS_IGNORABLES,
        SCORE=SCORE,
        TENSE_INDICATOR=TENSE_INDICATOR,
        RELATION=RELATION,
        SIGNED_FLOAT=SIGNED_FLOAT,
        OUT_OF_30=OUT_OF_30,
        OUT_OF_ANYTHING=out_of_anything(),
    )
    NAME = "MOCA"
    PREFERRED_UNIT_COLUMN = "out_of_30"
    UNIT_MAPPING = {
        OUT_OF_30: 1,       # preferred unit
        # not out_of_anything()
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
            commit=commit,
            take_absolute=True
        )

    def test(self):
        self.test_numerical_parser([
            ("MOCA 30", [30]),
            ("MOCA 30/30", [30]),
            ("MOCA 25/30", [25]),
            ("MOCA score was 25", [25]),
            ("MOCA 25/29", []),
            ("MOCA-25", [25]),
            ("Montreal Cognitive Assessment 25/30", [25]),
        ])


class MocaValidator(ValidatorBase):
    """Validator for MiniAce (see ValidatorBase for explanation)."""
    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         regex_str_list=[MiniAce.MACE],
                         validated_variable=MiniAce.NAME,
                         commit=commit)


# =============================================================================
#  Command-line entry point
# =============================================================================

def test_all() -> None:
    mmse = Mmse(None, None)
    mmse.test()
    ace = Ace(None, None)
    ace.test()
    mace = MiniAce(None, None)
    mace.test()
    moca = Moca(None, None)
    moca.test()


if __name__ == '__main__':
    test_all()


# support also "scored X on the MOCA"?
