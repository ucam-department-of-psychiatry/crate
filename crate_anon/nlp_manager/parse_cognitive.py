#!/usr/bin/env python
# crate_anon/nlp_manager/parse_cognitive.py

import logging
from typing import Optional

from crate_anon.nlp_manager.nlp_definition import NlpDefinition
from crate_anon.nlp_manager.regex_parser import (
    NumericalResultParser,
    ValidatorBase,
    OPTIONAL_RESULTS_IGNORABLES,
    out_of,
    RELATION,
    SIGNED_FLOAT,
    TENSE_INDICATOR,
    WORD_BOUNDARY,
)

log = logging.getLogger(__name__)


# =============================================================================
#  Mini-mental state examination (MMSE)
# =============================================================================

class Mmse(NumericalResultParser):
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
        ( {TENSE_INDICATOR} )?             # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                    # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {SIGNED_FLOAT} )                 # group for value
        {OPTIONAL_RESULTS_IGNORABLES}
        (                                  # group for units
            {OUT_OF_30}
        )?
    """.format(
        MMSE=MMSE,
        OPTIONAL_RESULTS_IGNORABLES=OPTIONAL_RESULTS_IGNORABLES,
        TENSE_INDICATOR=TENSE_INDICATOR,
        RELATION=RELATION,
        SIGNED_FLOAT=SIGNED_FLOAT,
        OUT_OF_30=OUT_OF_30,
    )
    NAME = "MMSE"
    PREFERRED_UNIT_COLUMN = "out_of_30"
    UNIT_MAPPING = {
        OUT_OF_30: 1,       # preferred unit
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
        self.test_numerical_parser([
            ("MMSE", []),  # should fail; no values
            ("MMSE 30/30", [30]),
            ("MMSE 25 / 30", [25]),
            ("mini-mental state exam 30", [30]),
            ("minimental 25", [25]),
            ("MMSE 30", [30]),
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
                         regex_str=Mmse.MMSE,
                         validated_variable=Mmse.NAME,
                         commit=commit)


# =============================================================================
#  Command-line entry point
# =============================================================================

if __name__ == '__main__':
    mmse = Mmse(None, None)
    mmse.test()
