#!/usr/bin/env python
# crate_anon/nlp_manager/parse_clinical.py

import logging
from typing import Any, Dict, Iterator, List, Optional, Tuple

from sqlalchemy import Column, Integer, Float, String, Text

from crate_anon.nlp_manager.nlp_definition import NlpDefinition
from crate_anon.nlp_manager.regex_parser import (
    BaseNlpParser,
    compile_regex,
    EQ,
    NumericalResultParser,
    OPTIONAL_RESULTS_IGNORABLES,
    PAST,
    PRESENT,
    RE_IS,
    RE_WAS,
    RELATION,
    SimpleNumericalResultParser,
    TENSE_INDICATOR,
    ValidatorBase,
    WORD_BOUNDARY,
)
from crate_anon.nlp_manager.regex_numbers import SIGNED_FLOAT
from crate_anon.nlp_manager.regex_units import (
    kg_from_st_lb_oz,
    KG_PER_SQ_M,
    m_from_ft_in,
    m_from_m_cm,
    MM_HG,
)

log = logging.getLogger(__name__)


# =============================================================================
#  Anthropometrics: height, weight (mass), BMI
# =============================================================================


# class Height(NumericalResultParser):
#     """Height. Handles metric and imperial."""
#     pass # ***


# class Weight(NumericalResultParser):
#     """Weight. Handles metric and imperial."""
#     pass # ***


class Bmi(SimpleNumericalResultParser):
    """Body mass index (in kg m^-2)."""
    BMI = r"""
        (?:
            {WORD_BOUNDARY}
            (?:
                BMI
                | body \s+ mass \s+ index
            )
            {WORD_BOUNDARY}
        )
    """.format(WORD_BOUNDARY=WORD_BOUNDARY)
    REGEX = r"""
        ( {BMI} )                          # group for "BMI" or equivalent
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?             # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                    # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {SIGNED_FLOAT} )                 # group for value
        {OPTIONAL_RESULTS_IGNORABLES}
        (                                  # group for units
            {KG_PER_SQ_M}
        )?
    """.format(
        BMI=BMI,
        OPTIONAL_RESULTS_IGNORABLES=OPTIONAL_RESULTS_IGNORABLES,
        TENSE_INDICATOR=TENSE_INDICATOR,
        RELATION=RELATION,
        SIGNED_FLOAT=SIGNED_FLOAT,
        KG_PER_SQ_M=KG_PER_SQ_M,
    )
    NAME = "BMI"
    PREFERRED_UNIT_COLUMN = "value_kg_per_sq_m"
    UNIT_MAPPING = {
        KG_PER_SQ_M: 1,       # preferred unit
    }
    # deal with "a BMI of 30"?

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
            ("BMI", []),  # should fail; no values
            ("body mass index was 30", [30]),
            ("his BMI (30) is too high", [30]),
            ("BMI 25 kg/sq m", [25]),
            ("BMI was 18.4 kg/m^-2", [18.4]),
            ("ACE 79", []),
        ])


class BmiValidator(ValidatorBase):
    """Validator for Bmi (see ValidatorBase for explanation)."""
    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         regex_str_list=[Bmi.BMI],
                         validated_variable=Bmi.NAME,
                         commit=commit)


# =============================================================================
#  Bedside investigations: BP
# =============================================================================

class Bp(BaseNlpParser):
    """Blood pressure, in mmHg. (Since we produce two variables, SBP and DBP,
    we subclass BaseNlpParser directly.)"""
    BP = r"""
        (?:
            \b blood \s+ pressure \b
            | \b B\.?P\.? \b
        )
    """
    SYSTOLIC_BP = r"""
        (?:
            \b systolic \s+ {BP}
            | \b S\.?B\.?P\.? \b
        )
    """.format(BP=BP)
    DIASTOLIC_BP = r"""
        (?:
            \b diastolic \s+ {BP}
            | \b D\.?B\.?P\.? \b
        )
    """.format(BP=BP)

    TWO_NUMBER_BP = r"""
        ( {SIGNED_FLOAT} )
        (?:
            \b over \b
            | \/
        )
        ( {SIGNED_FLOAT} )
    """.format(SIGNED_FLOAT=SIGNED_FLOAT)
    ONE_NUMBER_BP = SIGNED_FLOAT

    COMPILED_BP = compile_regex(BP)
    COMPILED_SBP = compile_regex(SYSTOLIC_BP)
    COMPILED_DBP = compile_regex(DIASTOLIC_BP)
    COMPILED_ONE_NUMBER_BP = compile_regex(ONE_NUMBER_BP)
    COMPILED_TWO_NUMBER_BP = compile_regex(TWO_NUMBER_BP)
    REGEX = r"""
        (                               # group for "BP" or equivalent
            {SYSTOLIC_BP}               # ... from more to less specific
            | {DIASTOLIC_BP}
            | {BP}
        )
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?         # optional group for tense indicator
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                # optional group for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        (                              # BP
            {SIGNED_FLOAT}                  # 120
            (?:
                \s*
                (?: \b over \b | \/ )       # /
                \s*
                {SIGNED_FLOAT}              # 80
            )?
        )
        {OPTIONAL_RESULTS_IGNORABLES}
        (                              # group for units
            {MM_HG}
        )?
    """.format(
        BP=BP,
        SYSTOLIC_BP=SYSTOLIC_BP,
        DIASTOLIC_BP=DIASTOLIC_BP,
        OPTIONAL_RESULTS_IGNORABLES=OPTIONAL_RESULTS_IGNORABLES,
        TENSE_INDICATOR=TENSE_INDICATOR,
        RELATION=RELATION,
        SIGNED_FLOAT=SIGNED_FLOAT,
        MM_HG=MM_HG,
    )
    COMPILED_REGEX = compile_regex(REGEX)

    FN_SYSTOLIC_BP_MMHG = 'systolic_bp_mmhg'
    FN_DIASTOLIC_BP_MMHG = 'diastolic_bp_mmhg'

    NAME = "BP"
    UNIT_MAPPING = {
        MM_HG: 1,       # preferred unit
    }

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
            commit=commit
        )
        if nlpdef is None:  # only None for debugging!
            self.tablename = ''
        else:
            self.tablename = nlpdef.opt_str(
                cfgsection, 'desttable', required=True)

    def dest_tables_columns(self) -> Dict[str, List[Column]]:
        return {self.tablename: [
            Column(NumericalResultParser.FN_CONTENT, Text,
                   doc="Matching text contents"),
            Column(NumericalResultParser.FN_START, Integer,
                   doc="Start position (of matching string within whole "
                       "text)"),
            Column(NumericalResultParser.FN_END, Integer,
                   doc="End position (of matching string within whole text)"),
            Column(NumericalResultParser.FN_VARIABLE_TEXT, Text,
                   doc="Text that matched the variable name"),
            Column(NumericalResultParser.FN_RELATION,
                   String(NumericalResultParser.MAX_RELATION_LENGTH),
                   doc="Text that matched the mathematical relationship "
                       "between variable and value (e.g. '=', '<='"),
            Column(NumericalResultParser.FN_VALUE_TEXT,
                   String(NumericalResultParser.MAX_VALUE_TEXT_LENGTH),
                   doc="Matched numerical value, as text"),
            Column(NumericalResultParser.FN_UNITS,
                   String(NumericalResultParser.MAX_UNITS_LENGTH),
                   doc="Matched units, as text"),
            Column(self.FN_SYSTOLIC_BP_MMHG, Float,
                   doc="Systolic BP in mmHg"),
            Column(self.FN_DIASTOLIC_BP_MMHG, Float,
                   doc="Diastolic BP in mmHg"),
            Column(NumericalResultParser.FN_TENSE,
                   String(NumericalResultParser.MAX_TENSE_LENGTH),
                   doc="Tense indicator, if known (e.g. '{}', '{}')".format(
                       PAST, PRESENT)),
        ]}

    def parse(self, text: str,
              debug: bool = False) -> Iterator[Tuple[str, Dict[str, Any]]]:
        for m in self.COMPILED_REGEX.finditer(text):
            if debug:
                print("Match {} for {}".format(m, repr(text)))
            startpos = m.start()
            endpos = m.end()
            matching_text = m.group(0)  # the whole thing
            variable_text = m.group(1)
            tense_indicator = m.group(2)
            relation = m.group(3)
            value_text = m.group(4)
            units = m.group(5)

            sbp = None
            dbp = None
            if self.COMPILED_SBP.match(variable_text):
                if self.COMPILED_ONE_NUMBER_BP.match(value_text):
                    sbp = float(value_text)
            elif self.COMPILED_DBP.match(variable_text):
                if self.COMPILED_ONE_NUMBER_BP.match(value_text):
                    dbp = float(value_text)
            elif self.COMPILED_BP.match(variable_text):
                bpmatch = self.COMPILED_TWO_NUMBER_BP.match(value_text)
                if bpmatch:
                    sbp = float(bpmatch.group(1))
                    dbp = float(bpmatch.group(2))
            if sbp is None and dbp is None:
                log.warning("Failed interpretation: {}".format(matching_text))
                continue

            tense = None
            if tense_indicator:
                if RE_IS.match(tense_indicator):
                    tense = PRESENT
                elif RE_WAS.match(tense_indicator):
                    tense = PAST
            elif relation:
                if RE_IS.match(relation):
                    tense = PRESENT
                elif RE_IS.match(relation):
                    tense = PAST

            if not relation:
                relation = EQ

            yield self.tablename, {
                NumericalResultParser.FN_CONTENT: matching_text,
                NumericalResultParser.FN_START: startpos,
                NumericalResultParser.FN_END: endpos,
                NumericalResultParser.FN_VARIABLE_TEXT: variable_text,
                NumericalResultParser.FN_RELATION: relation,
                NumericalResultParser.FN_VALUE_TEXT: value_text,
                NumericalResultParser.FN_UNITS: units,
                self.FN_SYSTOLIC_BP_MMHG: sbp,
                self.FN_DIASTOLIC_BP_MMHG: dbp,
                NumericalResultParser.FN_TENSE: tense,
            }

    def test_bp_parser(
            self,
            test_expected_list: List[Tuple[str, List[Tuple[float,
                                                           float]]]]) -> None:
        print("Testing parser: {}".format(type(self).__name__))
        for test_string, expected_values in test_expected_list:
            actual_values = list(
                (x[self.FN_SYSTOLIC_BP_MMHG], x[self.FN_DIASTOLIC_BP_MMHG])
                for t, x in self.parse(test_string)
            )
            assert actual_values == expected_values, (
                """Parser {}: Expected {}, got {}, when parsing {}""".format(
                    type(self).__name__,
                    expected_values,
                    actual_values,
                    repr(test_string)
                )
            )
        print("... OK")

    def test(self):
        self.test_bp_parser([
            ("BP", []),  # should fail; no values
            ("his blood pressure was 120/80", [(120, 80)]),
            ("BP 120/80 mmhg", [(120, 80)]),
            ("systolic BP 120", [(120, None)]),
            ("diastolic BP 80", [(None, 80)]),
        ])


class BpValidator(ValidatorBase):
    """Validator for Bp (see ValidatorBase for explanation)."""
    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         regex_str_list=[Bp.REGEX],
                         validated_variable=Bp.NAME,
                         commit=commit)


# =============================================================================
#  Command-line entry point
# =============================================================================

if __name__ == '__main__':
    # height = Height(None, None)
    # height.test()
    # weight = Weight(None, None)
    # weight.test()
    bmi = Bmi(None, None)
    bmi.test()
    bp = Bp(None, None)
    bp.test()
