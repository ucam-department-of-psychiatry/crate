"""
crate_anon/nlp_manager/parse_cognitive.py

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

**Python regex-based NLP processors for cognitive tests.**

All inherit from
:class:`crate_anon.nlp_manager.regex_parser.NumeratorOutOfDenominatorParser`
and are constructed with these arguments:

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
from typing import List, Optional, Tuple

from crate_anon.common.regex_helpers import WORD_BOUNDARY
from crate_anon.nlp_manager.nlp_definition import NlpDefinition
from crate_anon.nlp_manager.regex_numbers import IGNORESIGN_INTEGER
from crate_anon.nlp_manager.regex_parser import (
    APOSTROPHE,
    NumeratorOutOfDenominatorParser,
    ValidatorBase,
)
from crate_anon.nlp_manager.regex_units import OUT_OF_SEPARATOR

log = logging.getLogger(__name__)


# =============================================================================
# Mini-mental state examination (MMSE)
# =============================================================================


class Mmse(NumeratorOutOfDenominatorParser):
    """
    COGNITIVE.

    Mini-mental state examination (MMSE).

    The default denominator is 30, but it supports other values if given
    explicitly.
    """

    MMSE = rf"""
        (?: {WORD_BOUNDARY}
            (?: MMSE | mini[-\s]*mental (?: \s+ state)?
                       (?: \s+ exam(?:ination)? )? )
        {WORD_BOUNDARY} )
    """
    NAME = "MMSE"

    def __init__(
        self,
        nlpdef: Optional[NlpDefinition],
        cfg_processor_name: Optional[str],
        commit: bool = False,
    ) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            commit=commit,
            variable_name=self.NAME,
            variable_regex_str=self.MMSE,
            expected_denominator=30,
            take_absolute=True,
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in superclass
        self.test_numerator_denominator_parser(
            [
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
            ],
            verbose=verbose,
        )


class MmseValidator(ValidatorBase):
    """
    Validator for Mmse (see help for explanation).
    """

    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return Mmse.NAME, [Mmse.MMSE]


# =============================================================================
# Addenbrooke's Cognitive Examination (ACE, ACE-R, ACE-III)
# =============================================================================


class Ace(NumeratorOutOfDenominatorParser):
    """
    COGNITIVE.

    Addenbrooke's Cognitive Examination (ACE, ACE-R, ACE-III) total score.

    The default denominator is 100 but it supports other values if given
    explicitly.
    """

    NAME = "ACE"
    ACE = rf"""
        (?: {WORD_BOUNDARY}
            (?: ACE | (?: Addenbrooke{APOSTROPHE}?s \s+ cognitive \s+
                          (?: (?:evaluation) | exam(?:ination)? ) ) )
            (?: \s* -? \s*
                (?: R | III | 111
                    # or: 3 when not followed by an "out of X" expression
                    | (?: 3 (?! \s* {OUT_OF_SEPARATOR} \s* {IGNORESIGN_INTEGER}))
                ) \b
            )?+
        {WORD_BOUNDARY} )
    """  # noqa: E501
    # ... note the possessive "?+" above; see tests below.

    def __init__(
        self,
        nlpdef: Optional[NlpDefinition],
        cfg_processor_name: Optional[str],
        commit: bool = False,
    ) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            commit=commit,
            variable_name=self.NAME,
            variable_regex_str=self.ACE,
            expected_denominator=100,
            take_absolute=True,
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in superclass
        self.test_numerator_denominator_parser(
            [
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
                ("ACE R 79", [(79, None)]),
                ("ACE III 79", [(79, None)]),
                ("ACE-82", [(82, None)]),
                (
                    "ACE 111 99",
                    [(99, None)],
                ),  # "ACE 111" (for III) from real data
                # Note the difficulties created by the "ACE-3" representation
                # of the task's name. We have to get these right:
                ("ACE-3 79", [(79, None)]),
                ("ACE 3 79", [(79, None)]),
                ("ACE 3 79/100", [(79, 100)]),
                ("ACE 3 3", [(3, None)]),
                ("ACE 3 3/100", [(3, 100)]),
                # ... but also a score of 3 (!) on the older ACE:
                ("ACE 3/100", [(3, 100)]),
                ("ACE 3 out of 100", [(3, 100)]),
                # - This next one is ambiguous. Reference to new task? To old
                #   score? Making the "3" optional as part of the task name
                #   means that this will be accepted by the regex as a score.
                # - We need a special exception to get "ACE 3" not to give a
                #   score.
                # - We do this with a "possessive" quantifier on the "3" (or
                #   similar) part of the ACE descriptor.
                # - http://www.rexegg.com/regex-quantifiers.html
                # - Possessive quantifiers are in regex, not re:
                #   https://pypi.python.org/pypi/regex
                #   https://docs.python.org/3.5/library/re.html
                # - Ah, no. That makes "ACE 3/100" fail.
                # - But if we combine a possessive "3" with saying "3 unless
                #   it's "3 out of...", then we win.
                ("ACE 3", []),
                ("ACE 3/MOCA", []),
                ("ACE 3 / MOCA", []),
            ],
            verbose=verbose,
        )


class AceValidator(ValidatorBase):
    """
    Validator for Ace (see help for explanation).
    """

    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return Ace.NAME, [Ace.ACE]

    def test(self, verbose: bool = False) -> None:
        # docstring in superclass
        self.test_validator(
            [
                ("pass me my mace, my boy", False),
                ("he scored 10 on the ACE today", True),
                ("he scored 10 on the ACE 3 today", True),
                ("he scored 10 on the ACE3 today", True),
                ("ACE 3/100", True),
                ("ACE 3 3/100", True),
                ("ACE3 4", True),
                ("ACE 3", True),
                ("ACE3", True),
                ("ACE 3/MOCA", True),
                ("ACE 3 / MOCA", True),
            ],
            verbose=verbose,
        )


# =============================================================================
# Mini-Addenbrooke's Cognitive Examination (M-ACE)
# =============================================================================


class MiniAce(NumeratorOutOfDenominatorParser):
    """
    COGNITIVE.

    Mini-Addenbrooke's Cognitive Examination (M-ACE).

    The default denominator is 30, but it supports other values if given
    explicitly.
    """

    MACE = rf"""
        (?: {WORD_BOUNDARY}
            (?: mini | M ) \s* -? \s*
            (?: ACE | (?: Addenbrooke{APOSTROPHE}?s \s+ cognitive \s+
                          (?: (?:evaluation) | exam(?:ination)? ) ) )
        {WORD_BOUNDARY} )
    """
    NAME = "MiniACE"

    def __init__(
        self,
        nlpdef: Optional[NlpDefinition],
        cfg_processor_name: Optional[str],
        commit: bool = False,
    ) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            commit=commit,
            variable_name=self.NAME,
            variable_regex_str=self.MACE,
            expected_denominator=30,  # mini-ACE is out of 30
            take_absolute=True,
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in superclass
        self.test_numerator_denominator_parser(
            [
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
            ],
            verbose=verbose,
        )


class MiniAceValidator(ValidatorBase):
    """
    Validator for MiniAce (see help for explanation).
    """

    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return MiniAce.NAME, [MiniAce.MACE]


# =============================================================================
# Montreal Cognitive Assessment (MOCA)
# =============================================================================


class Moca(NumeratorOutOfDenominatorParser):
    """
    COGNITIVE.

    Montreal Cognitive Assessment (MOCA).

    The default denominator is 30, but it supports other values if given
    explicitly.
    """

    # todo:: MOCA NLP parser: support also "scored X on the MOCA"?
    MOCA = rf"""
        (?: {WORD_BOUNDARY}
            (?: MOCA | (?: Montreal \s+ cognitive \s+ assessment ) )
        {WORD_BOUNDARY} )
    """
    NAME = "MOCA"

    def __init__(
        self,
        nlpdef: Optional[NlpDefinition],
        cfg_processor_name: Optional[str],
        commit: bool = False,
    ) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            commit=commit,
            variable_name=self.NAME,
            variable_regex_str=self.MOCA,
            expected_denominator=30,
            take_absolute=True,
        )

    def test(self, verbose: bool = False) -> None:
        # docstring in superclass
        self.test_numerator_denominator_parser(
            [
                ("MOCA 30", [(30, None)]),
                ("MOCA 30/30", [(30, 30)]),
                ("MOCA 25/30", [(25, 30)]),
                ("MOCA score was 25", [(25, None)]),
                ("MOCA 25/29", [(25, 29)]),
                ("MOCA-25", [(25, None)]),
                ("Montreal Cognitive Assessment 25/30", [(25, 30)]),
            ]
        )


class MocaValidator(ValidatorBase):
    """
    Validator for Moca (see help for explanation).
    """

    @classmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        return Moca.NAME, [Moca.MOCA]


# =============================================================================
# All classes in this module
# =============================================================================

ALL_COGNITIVE_NLP_AND_VALIDATORS = [
    (Ace, AceValidator),
    (MiniAce, MiniAceValidator),
    (Mmse, MmseValidator),
    (Moca, MocaValidator),
]
