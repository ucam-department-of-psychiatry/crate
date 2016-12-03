#!/usr/bin/env python
# crate_anon/nlp_manager/parse_cognitive.py

import logging
from typing import Optional

from crate_anon.nlp_manager.nlp_definition import NlpDefinition
from crate_anon.nlp_manager.regex_parser import (
    APOSTROPHE,
    NumeratorOutOfDenominatorParser,
    ValidatorBase,
    WORD_BOUNDARY,
)

log = logging.getLogger(__name__)


# =============================================================================
# Mini-mental state examination (MMSE)
# =============================================================================

class Mmse(NumeratorOutOfDenominatorParser):
    """Mini-mental state examination (MMSE)."""
    MMSE = r"""
        (?: {WORD_BOUNDARY}
            (?: MMSE | mini[-\s]*mental (?: \s+ state)?
                       (?: \s+ exam(?:ination)? )? )
        {WORD_BOUNDARY} )
    """.format(WORD_BOUNDARY=WORD_BOUNDARY)
    NAME = "MMSE"

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
            commit=commit,
            variable_name=self.NAME,
            variable_regex_str=self.MMSE,
            expected_denominator=30,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        self.test_numerator_denominator_parser([
            ("MMSE", []),  # should fail; no values
            ("MMSE 30/30", [(30, 30)]),
            ("MMSE 25 / 30", [(25, 30)]),
            ("MMSE 25 / 29", [(25, 29)]),
            ("MMSE 25 / 31", [(25, 31)]),
            ("mini-mental state exam 30", [(30, None)]),
            ("minimental 25", [(25, None)]),
            ("MMSE 30", [(30, None)]),
            ("MMSE-27", [(27, None)]),
            ("MMSE score was 30", [(30, None)]),
            ("ACE 79", []),
        ], verbose=verbose)


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

class Ace(NumeratorOutOfDenominatorParser):
    """Addenbrooke's Cognitive Examination (ACE, ACE-R, ACE-III)."""
    ACE = r"""
        (?: {WORD_BOUNDARY}
            (?: ACE | (?: Addenbrooke{APOSTROPHE}?s \s+ cognitive \s+
                          (?: (?:evaluation) | exam(?:ination)? ) ) )
            (?: \s* -? \s* (?: R | III | 3 | 111 ) \b )?
        {WORD_BOUNDARY} )
    """.format(WORD_BOUNDARY=WORD_BOUNDARY, APOSTROPHE=APOSTROPHE)
    NAME = "ACE"

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
            commit=commit,
            variable_name=self.NAME,
            variable_regex_str=self.ACE,
            expected_denominator=100,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        self.test_numerator_denominator_parser([
            ("MMSE", []),
            ("MMSE 30/30", []),
            ("MMSE 25 / 30", []),
            ("mini-mental state exam 30", []),
            ("minimental 25", []),
            ("MMSE 30", []),
            ("ACE 79", [(79, None)]),
            ("ACE 79/100", [(79, 100)]),
            ("ACE 79/95", [(79, 95)]),
            ("ACE 79 / 100", [(79, 100)]),
            ("Addenbrooke's cognitive examination 79", [(79, None)]),
            ("Addenbrookes cognitive evaluation 79", [(79, None)]),
            ("ACE-R 79", [(79, None)]),
            ("ACE-R 79 out of 100", [(79, 100)]),
            ("ACE-III 79", [(79, None)]),
            ("ACE-III score was 79", [(79, None)]),
            ("ACE-3 79", [(79, None)]),
            ("ACE R 79", [(79, None)]),
            ("ACE III 79", [(79, None)]),
            ("ACE 3 79", [(79, None)]),
            ("ACE 3 79/100", [(79, 100)]),
            ("ACE 3 3", [(3, None)]),
            ("ACE 3 3/100", [(3, 100)]),
            ("ACE 111 99", [(99, None)]),  # "ACE 111" from real data
            ("ACE-82", [(82, None)]),
        ], verbose=verbose)


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

class MiniAce(NumeratorOutOfDenominatorParser):
    """Mini-Addenbrooke's Cognitive Examination (M-ACE)."""
    MACE = r"""
        (?: {WORD_BOUNDARY}
            (?: mini | M ) \s* -? \s*
            (?: ACE | (?: Addenbrooke{APOSTROPHE}?s \s+ cognitive \s+
                          (?: (?:evaluation) | exam(?:ination)? ) ) )
        {WORD_BOUNDARY} )
    """.format(WORD_BOUNDARY=WORD_BOUNDARY, APOSTROPHE=APOSTROPHE)
    NAME = "MiniACE"

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
            commit=commit,
            variable_name=self.NAME,
            variable_regex_str=self.MACE,
            expected_denominator=30,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        self.test_numerator_denominator_parser([
            ("MMSE 30", []),
            ("ACE 79", []),
            ("ACE 79/100", []),
            ("Addenbrooke's cognitive examination 79", []),
            ("Addenbrookes cognitive evaluation 79", []),
            ("mini-Addenbrooke's cognitive examination 79", [(79, None)]),
            ("mini-Addenbrooke’s cognitive examination 79", [(79, None)]),
            ("mini-Addenbrookes cognitive evaluation 79", [(79, None)]),
            ("M-ACE 20", [(20, None)]),
            ("M-ACE score is 20", [(20, None)]),
            ("M-ACE 29/30", [(29, 30)]),
            ("M-ACE 29/29", [(29, 29)]),
            ("MACE 29", [(29, None)]),
            ("MACE-29", [(29, None)]),
            ("mini-ACE 29", [(29, None)]),
        ], verbose=verbose)


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

class Moca(NumeratorOutOfDenominatorParser):
    """Montreal Cognitive Assessment (MOCA)."""
    MOCA = r"""
        (?: {WORD_BOUNDARY}
            (?: MOCA | (?: Montreal \s+ cognitive \s+ assessment ) )
        {WORD_BOUNDARY} )
    """.format(WORD_BOUNDARY=WORD_BOUNDARY)
    NAME = "MOCA"

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
            commit=commit,
            variable_name=self.NAME,
            variable_regex_str=self.MOCA,
            expected_denominator=30,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        self.test_numerator_denominator_parser([
            ("MOCA 30", [(30, None)]),
            ("MOCA 30/30", [(30, 30)]),
            ("MOCA 25/30", [(25, 30)]),
            ("MOCA score was 25", [(25, None)]),
            ("MOCA 25/29", [(25, 29)]),
            ("MOCA-25", [(25, None)]),
            ("Montreal Cognitive Assessment 25/30", [(25, 30)]),
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

def test_all(verbose: bool = False) -> None:
    mmse = Mmse(None, None)
    mmse.test(verbose=verbose)
    ace = Ace(None, None)
    ace.test(verbose=verbose)
    mace = MiniAce(None, None)
    mace.test(verbose=verbose)
    moca = Moca(None, None)
    moca.test(verbose=verbose)


if __name__ == '__main__':
    test_all(verbose=True)


# support also "scored X on the MOCA"?
