#!/usr/bin/env python
# crate_anon/nlp_manager/parse_clinical.py

import logging
from typing import Any, Dict, Generator, List, Optional, Tuple

from sqlalchemy import Column, Integer, Float, String, Text

from crate_anon.nlp_manager.nlp_definition import NlpDefinition
from crate_anon.nlp_manager.regex_parser import (
    BaseNlpParser,
    common_tense,
    compile_regex,
    FN_CONTENT,
    FN_END,
    FN_RELATION,
    FN_RELATION_TEXT,
    FN_START,
    FN_TENSE,
    FN_TENSE_TEXT,
    FN_UNITS,
    FN_VALUE_TEXT,
    FN_VARIABLE_NAME,
    FN_VARIABLE_TEXT,
    HELP_CONTENT,
    HELP_END,
    HELP_RELATION,
    HELP_RELATION_TEXT,
    HELP_START,
    HELP_TENSE,
    HELP_UNITS,
    HELP_VALUE_TEXT,
    HELP_VARIABLE_TEXT,
    MAX_RELATION_LENGTH,
    MAX_RELATION_TEXT_LENGTH,
    MAX_TENSE_LENGTH,
    MAX_UNITS_LENGTH,
    MAX_VALUE_TEXT_LENGTH,
    NumericalResultParser,
    OPTIONAL_RESULTS_IGNORABLES,
    RELATION,
    SimpleNumericalResultParser,
    TENSE_INDICATOR,
    to_float,
    to_pos_float,
    ValidatorBase,
    WORD_BOUNDARY,
)
from crate_anon.nlp_manager.regex_numbers import SIGNED_FLOAT
from crate_anon.nlp_manager.regex_units import (
    assemble_units,
    CM,
    FEET,
    INCHES,
    KG,
    kg_from_st_lb_oz,
    KG_PER_SQ_M,
    LB,
    M,
    m_from_ft_in,
    m_from_m_cm,
    MM_HG,
    STONES,
)

log = logging.getLogger(__name__)


# =============================================================================
#  Anthropometrics
# =============================================================================

# -----------------------------------------------------------------------------
# Height
# -----------------------------------------------------------------------------

class Height(NumericalResultParser):
    """Height. Handles metric and imperial."""
    METRIC_HEIGHT = r"""
        (                           # capture group 4
            (?:
                ( {SIGNED_FLOAT} )          # capture group 5
                {OPTIONAL_RESULTS_IGNORABLES}
                ( {M} )                     # capture group 6
                {OPTIONAL_RESULTS_IGNORABLES}
                ( {SIGNED_FLOAT} )          # capture group 7
                {OPTIONAL_RESULTS_IGNORABLES}
                ( {CM} )                    # capture group 8
            )
            | (?:
                ( {SIGNED_FLOAT} )          # capture group 9
                {OPTIONAL_RESULTS_IGNORABLES}
                ( {M} )                     # capture group 10
            )
            | (?:
                ( {SIGNED_FLOAT} )          # capture group 11
                {OPTIONAL_RESULTS_IGNORABLES}
                ( {CM} )                    # capture group 12
            )
        )
    """.format(
        SIGNED_FLOAT=SIGNED_FLOAT,
        OPTIONAL_RESULTS_IGNORABLES=OPTIONAL_RESULTS_IGNORABLES,
        M=M,
        CM=CM
    )
    IMPERIAL_HEIGHT = r"""
        (                           # capture group 13
            (?:
                ( {SIGNED_FLOAT} )      # capture group 14
                {OPTIONAL_RESULTS_IGNORABLES}
                ( {FEET} )              # capture group 15
                {OPTIONAL_RESULTS_IGNORABLES}
                ( {SIGNED_FLOAT} )      # capture group 16
                {OPTIONAL_RESULTS_IGNORABLES}
                ( {INCHES} )            # capture group 17
            )
            | (?:
                ( {SIGNED_FLOAT} )      # capture group 18
                {OPTIONAL_RESULTS_IGNORABLES}
                ( {FEET} )              # capture group 19
            )
            | (?:
                ( {SIGNED_FLOAT} )      # capture group 20
                {OPTIONAL_RESULTS_IGNORABLES}
                ( {INCHES} )            # capture group 21
            )
        )
    """.format(
        SIGNED_FLOAT=SIGNED_FLOAT,
        OPTIONAL_RESULTS_IGNORABLES=OPTIONAL_RESULTS_IGNORABLES,
        FEET=FEET,
        INCHES=INCHES
    )
    HEIGHT = r"(?: \b height \b)"
    REGEX = r"""
        ( {HEIGHT} )                       # group 1 for "height" or equivalent
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?             # optional group 2 for tense
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                    # optional group 3 for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        (?:
            {METRIC_HEIGHT}
            | {IMPERIAL_HEIGHT}
        )
    """.format(
        HEIGHT=HEIGHT,
        OPTIONAL_RESULTS_IGNORABLES=OPTIONAL_RESULTS_IGNORABLES,
        TENSE_INDICATOR=TENSE_INDICATOR,
        RELATION=RELATION,
        METRIC_HEIGHT=METRIC_HEIGHT,
        IMPERIAL_HEIGHT=IMPERIAL_HEIGHT,
        SIGNED_FLOAT=SIGNED_FLOAT,
        KG_PER_SQ_M=KG_PER_SQ_M,
    )

    COMPILED_REGEX = compile_regex(REGEX)
    NAME = "Height"
    PREFERRED_UNIT_COLUMN = "value_m"

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False,
                 debug: bool = False) -> None:
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            regex_str_for_debugging=self.REGEX,
            commit=commit
        )
        if debug:
            print("Regex for {}: {}".format(type(self).__name__, self.REGEX))

    def parse(self, text: str,
              debug: bool = False) -> Generator[Tuple[str, Dict[str, Any]],
                                                None, None]:
        """Parser for Height. Specialized for complex unit conversion."""
        for m in self.COMPILED_REGEX.finditer(text):  # watch out: 'm'/metres
            if debug:
                print("Match {} for {}".format(m, repr(text)))
            startpos = m.start()
            endpos = m.end()
            matching_text = m.group(0)  # the whole thing
            variable_text = m.group(1)
            tense_text = m.group(2)
            relation_text = m.group(3)
            metric_expression = m.group(4)
            metric_m_and_cm_m = m.group(5)
            metric_m_and_cm_m_units = m.group(6)
            metric_m_and_cm_cm = m.group(7)
            metric_m_and_cm_cm_units = m.group(8)
            metric_m_only_m = m.group(9)
            metric_m_only_m_units = m.group(10)
            metric_cm_only_cm = m.group(11)
            metric_cm_only_cm_units = m.group(12)
            imperial_expression = m.group(13)
            imperial_ft_and_in_ft = m.group(14)
            imperial_ft_and_in_ft_units = m.group(15)
            imperial_ft_and_in_in = m.group(16)
            imperial_ft_and_in_in_units = m.group(17)
            imperial_ft_only_ft = m.group(18)
            imperial_ft_only_ft_units = m.group(19)
            imperial_in_only_in = m.group(20)
            imperial_in_only_in_units = m.group(21)

            expression = None
            value_m = None
            units = None
            if metric_expression:
                expression = metric_expression
                if metric_m_and_cm_m and metric_m_and_cm_cm:
                    metres = to_pos_float(metric_m_and_cm_m)
                    # ... beware: 'm' above
                    cm = to_pos_float(metric_m_and_cm_cm)
                    value_m = m_from_m_cm(metres=metres, centimetres=cm)
                    units = assemble_units([metric_m_and_cm_m_units,
                                            metric_m_and_cm_cm_units])
                elif metric_m_only_m:
                    value_m = to_pos_float(metric_m_only_m)
                    units = metric_m_only_m_units
                elif metric_cm_only_cm:
                    cm = to_pos_float(metric_cm_only_cm)
                    value_m = m_from_m_cm(centimetres=cm)
                    units = metric_cm_only_cm_units
            elif imperial_expression:
                expression = imperial_expression
                if imperial_ft_and_in_ft and imperial_ft_and_in_in:
                    ft = to_pos_float(imperial_ft_and_in_ft)
                    inches = to_pos_float(imperial_ft_and_in_in)
                    value_m = m_from_ft_in(feet=ft, inches=inches)
                    units = assemble_units([imperial_ft_and_in_ft_units,
                                            imperial_ft_and_in_in_units])
                elif imperial_ft_only_ft:
                    ft = to_pos_float(imperial_ft_only_ft)
                    value_m = m_from_ft_in(feet=ft)
                    units = imperial_ft_only_ft_units
                elif imperial_in_only_in:
                    inches = to_pos_float(imperial_in_only_in)
                    value_m = m_from_ft_in(inches=inches)
                    units = imperial_in_only_in_units

            tense, relation = common_tense(tense_text, relation_text)

            result = {
                FN_VARIABLE_NAME: self.variable,
                FN_CONTENT: matching_text,
                FN_START: startpos,
                FN_END: endpos,

                FN_VARIABLE_TEXT: variable_text,
                FN_RELATION_TEXT: relation_text,
                FN_RELATION: relation,
                FN_VALUE_TEXT: expression,
                FN_UNITS: units,
                self.target_unit: value_m,
                FN_TENSE_TEXT: tense_text,
                FN_TENSE: tense,
            }
            # log.critical(result)
            yield self.tablename, result

    def test(self, verbose: bool = False) -> None:
        self.test_numerical_parser([
            ("Height", []),  # should fail; no values
            ("her height was 1.6m", [1.6]),
            ("Height = 1.23 m", [1.23]),
            ("her height is 1.5m", [1.5]),
            ('''Height 5'8" ''', [m_from_ft_in(feet=5, inches=8)]),
            ("Height 5 ft 8 in", [m_from_ft_in(feet=5, inches=8)]),
            ("Height 5 feet 8 inches", [m_from_ft_in(feet=5, inches=8)]),
        ], verbose=verbose)
        self.detailed_test("Height 5 ft 11 in", [{
            self.target_unit: m_from_ft_in(feet=5, inches=11),
            FN_UNITS: "ft in",
        }], verbose=verbose)
        # *** deal with "tall" and plain "is", e.g.
        # she is 6'2"; she is 1.5m tall


class HeightValidator(ValidatorBase):
    """Validator for Height (see ValidatorBase for explanation)."""
    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         regex_str_list=[Height.HEIGHT],
                         validated_variable=Height.NAME,
                         commit=commit)


# -----------------------------------------------------------------------------
# Weight (mass)
# -----------------------------------------------------------------------------

class Weight(NumericalResultParser):
    """Weight. Handles metric and imperial."""
    METRIC_WEIGHT = r"""
        (                           # capture group 4
            ( {SIGNED_FLOAT} )          # capture group 5
            {OPTIONAL_RESULTS_IGNORABLES}
            ( {KG} )                    # capture group 6
        )
    """.format(
        SIGNED_FLOAT=SIGNED_FLOAT,
        OPTIONAL_RESULTS_IGNORABLES=OPTIONAL_RESULTS_IGNORABLES,
        KG=KG
    )
    IMPERIAL_WEIGHT = r"""
        (                           # capture group 7
            (?:
                ( {SIGNED_FLOAT} )      # capture group 8
                {OPTIONAL_RESULTS_IGNORABLES}
                ( {STONES} )            # capture group 9
                {OPTIONAL_RESULTS_IGNORABLES}
                ( {SIGNED_FLOAT} )      # capture group 10
                {OPTIONAL_RESULTS_IGNORABLES}
                ( {LB} )                # capture group 11
            )
            | (?:
                ( {SIGNED_FLOAT} )      # capture group 12
                {OPTIONAL_RESULTS_IGNORABLES}
                ( {STONES} )            # capture group 13
            )
            | (?:
                ( {SIGNED_FLOAT} )      # capture group 14
                {OPTIONAL_RESULTS_IGNORABLES}
                ( {LB} )                # capture group 15
            )
        )
    """.format(
        SIGNED_FLOAT=SIGNED_FLOAT,
        OPTIONAL_RESULTS_IGNORABLES=OPTIONAL_RESULTS_IGNORABLES,
        STONES=STONES,
        LB=LB
    )
    WEIGHT = r"(?: \b weigh[ts] \b )"  # weight, weighs
    REGEX = r"""
        ( {WEIGHT} )                       # group 1 for "weight" or equivalent
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {TENSE_INDICATOR} )?             # optional group 2 for tense
        {OPTIONAL_RESULTS_IGNORABLES}
        ( {RELATION} )?                    # optional group 3 for relation
        {OPTIONAL_RESULTS_IGNORABLES}
        (?:
            {METRIC_WEIGHT}
            | {IMPERIAL_WEIGHT}
        )
    """.format(
        WEIGHT=WEIGHT,
        OPTIONAL_RESULTS_IGNORABLES=OPTIONAL_RESULTS_IGNORABLES,
        TENSE_INDICATOR=TENSE_INDICATOR,
        RELATION=RELATION,
        METRIC_WEIGHT=METRIC_WEIGHT,
        IMPERIAL_WEIGHT=IMPERIAL_WEIGHT,
        SIGNED_FLOAT=SIGNED_FLOAT,
        KG_PER_SQ_M=KG_PER_SQ_M,
    )

    COMPILED_REGEX = compile_regex(REGEX)
    NAME = "Weight"
    PREFERRED_UNIT_COLUMN = "value_kg"

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False,
                 debug: bool = False) -> None:
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            regex_str_for_debugging=self.REGEX,
            commit=commit
        )
        if debug:
            print("Regex for {}: {}".format(type(self).__name__, self.REGEX))

    def parse(self, text: str,
              debug: bool = False) -> Generator[Tuple[str, Dict[str, Any]],
                                                None, None]:
        """Parser for Weight. Specialized for complex unit conversion."""
        for m in self.COMPILED_REGEX.finditer(text):
            if debug:
                print("Match {} for {}".format(m, repr(text)))
            startpos = m.start()
            endpos = m.end()
            matching_text = m.group(0)  # the whole thing
            variable_text = m.group(1)
            tense_text = m.group(2)
            relation_text = m.group(3)
            metric_expression = m.group(4)
            metric_value = m.group(5)
            metric_units = m.group(6)
            imperial_expression = m.group(7)
            imperial_st_and_lb_st = m.group(8)
            imperial_st_and_lb_st_units = m.group(9)
            imperial_st_and_lb_lb = m.group(10)
            imperial_st_and_lb_lb_units = m.group(11)
            imperial_st_only_st = m.group(12)
            imperial_st_only_st_units = m.group(13)
            imperial_lb_only_lb = m.group(14)
            imperial_lb_only_lb_units = m.group(15)

            expression = None
            value_kg = None
            units = None
            if metric_expression:
                expression = metric_expression
                value_kg = to_float(metric_value)
                units = metric_units
            elif imperial_expression:
                expression = imperial_expression
                if imperial_st_and_lb_st and imperial_st_and_lb_lb:
                    st = to_float(imperial_st_and_lb_st)
                    lb = to_float(imperial_st_and_lb_lb)
                    value_kg = kg_from_st_lb_oz(stones=st, pounds=lb)
                    units = assemble_units([imperial_st_and_lb_st_units,
                                            imperial_st_and_lb_lb_units])
                elif imperial_st_only_st:
                    st = to_float(imperial_st_only_st)
                    value_kg = kg_from_st_lb_oz(stones=st)
                    units = imperial_st_only_st_units
                elif imperial_lb_only_lb:
                    lb = to_float(imperial_lb_only_lb)
                    value_kg = kg_from_st_lb_oz(pounds=lb)
                    units = imperial_lb_only_lb_units

            # All left as signed float, as you definitely see things like
            # "weight -0.3 kg" for weight changes.

            tense, relation = common_tense(tense_text, relation_text)

            result = {
                FN_VARIABLE_NAME: self.variable,
                FN_CONTENT: matching_text,
                FN_START: startpos,
                FN_END: endpos,

                FN_VARIABLE_TEXT: variable_text,
                FN_RELATION_TEXT: relation_text,
                FN_RELATION: relation,
                FN_VALUE_TEXT: expression,
                FN_UNITS: units,
                self.target_unit: value_kg,
                FN_TENSE_TEXT: tense_text,
                FN_TENSE: tense,
            }
            # log.critical(result)
            yield self.tablename, result

    def test(self, verbose: bool = False) -> None:
        self.test_numerical_parser([
            ("Weight", []),  # should fail; no values
            ("her weight was 60.2kg", [60.2]),
            ("Weight = 52.3kg", [52.3]),
            ("Weight: 80.8kgs", [80.8]),
            ("she weighs 61kg", [61]),
            ("she weighs 61 kg", [61]),
            ("she weighs 61 kgs", [61]),
            ("she weighs 61 kilo", [61]),
            ("she weighs 61 kilos", [61]),
            ("she weighs 8 stones ", [kg_from_st_lb_oz(stones=8)]),
            ("she weighs 200 lb", [kg_from_st_lb_oz(pounds=200)]),
            ("she weighs 200 pounds", [kg_from_st_lb_oz(pounds=200)]),
            ("she weighs 6 st 12 lb", [kg_from_st_lb_oz(stones=6, pounds=12)]),
            ("change in weight -0.4kg", [-0.4]),
            ("change in weight - 0.4kg", [0.4]),  # ASCII hyphen (hyphen-minus)
            ("change in weight ‐ 0.4kg", [0.4]),  # Unicode hyphen
            # ("failme", [999]),
            ("change in weight −0.4kg", [-0.4]),  # Unicode minus
            ("change in weight –0.4kg", [-0.4]),  # en dash
            ("change in weight —0.4kg", [0.4]),  # em dash
        ], verbose=verbose)
        self.detailed_test("Weight: 80.8kgs", [{
            self.target_unit: 80.8,
            FN_UNITS: "kgs",
        }], verbose=verbose)


class WeightValidator(ValidatorBase):
    """Validator for Weight (see ValidatorBase for explanation)."""
    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False) -> None:
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         regex_str_list=[Weight.WEIGHT],
                         validated_variable=Weight.NAME,
                         commit=commit)


# -----------------------------------------------------------------------------
# Body mass index (BMI)
# -----------------------------------------------------------------------------

class Bmi(SimpleNumericalResultParser):
    """Body mass index (in kg / m^2)."""
    BMI = r"""
        (?: {WORD_BOUNDARY}
            (?: BMI | body \s+ mass \s+ index )
        {WORD_BOUNDARY} )
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
            commit=commit,
            take_absolute=True
        )

    def test(self, verbose: bool = False) -> None:
        self.test_numerical_parser([
            ("BMI", []),  # should fail; no values
            ("body mass index was 30", [30]),
            ("his BMI (30) is too high", [30]),
            ("BMI 25 kg/sq m", [25]),
            ("BMI was 18.4 kg/m^-2", [18.4]),
            ("ACE 79", []),
            ("BMI-23", [23]),
        ], verbose=verbose)


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
    and we use something a little more complex than
    NumeratorOutOfDenominatorParser, we subclass BaseNlpParser directly.)"""
    BP = r"(?: \b blood \s+ pressure \b | \b B\.?P\.? \b )"
    SYSTOLIC_BP = r"(?: \b systolic \s+ {BP} | \b S\.?B\.?P\.? \b )".format(
        BP=BP)
    DIASTOLIC_BP = r"(?: \b diastolic \s+ {BP} | \b D\.?B\.?P\.? \b )".format(
        BP=BP)

    TWO_NUMBER_BP = r"""
        ( {SIGNED_FLOAT} )
        \s* (?: \b over \b | \/ ) \s*
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
        (
            {SIGNED_FLOAT}                      # systolic
            (?:
                \s* (?: \b over \b | \/ ) \s*   # /
                {SIGNED_FLOAT}                  # diastolic
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
            Column(FN_CONTENT, Text, doc=HELP_CONTENT),
            Column(FN_START, Integer, doc=HELP_START),
            Column(FN_END, Integer, doc=HELP_END),
            Column(FN_VARIABLE_TEXT, Text, doc=HELP_VARIABLE_TEXT),
            Column(FN_RELATION_TEXT, String(MAX_RELATION_TEXT_LENGTH),
                   doc=HELP_RELATION_TEXT),
            Column(FN_RELATION, String(MAX_RELATION_LENGTH),
                   doc=HELP_RELATION),
            Column(FN_VALUE_TEXT, String(MAX_VALUE_TEXT_LENGTH),
                   doc=HELP_VALUE_TEXT),
            Column(FN_UNITS, String(MAX_UNITS_LENGTH), doc=HELP_UNITS),
            Column(self.FN_SYSTOLIC_BP_MMHG, Float,
                   doc="Systolic blood pressure in mmHg"),
            Column(self.FN_DIASTOLIC_BP_MMHG, Float,
                   doc="Diastolic blood pressure in mmHg"),
            Column(FN_TENSE, String(MAX_TENSE_LENGTH), doc=HELP_TENSE),
        ]}

    def parse(self, text: str,
              debug: bool = False) -> Generator[Tuple[str, Dict[str, Any]],
                                                None, None]:
        """Parser for BP. Specialized because we're fetching two numbers."""
        for m in self.COMPILED_REGEX.finditer(text):
            if debug:
                print("Match {} for {}".format(m, repr(text)))
            startpos = m.start()
            endpos = m.end()
            matching_text = m.group(0)  # the whole thing
            variable_text = m.group(1)
            tense_indicator = m.group(2)
            relation_text = m.group(3)
            value_text = m.group(4)
            units = m.group(5)

            sbp = None
            dbp = None
            if self.COMPILED_SBP.match(variable_text):
                if self.COMPILED_ONE_NUMBER_BP.match(value_text):
                    sbp = to_pos_float(value_text)
            elif self.COMPILED_DBP.match(variable_text):
                if self.COMPILED_ONE_NUMBER_BP.match(value_text):
                    dbp = to_pos_float(value_text)
            elif self.COMPILED_BP.match(variable_text):
                bpmatch = self.COMPILED_TWO_NUMBER_BP.match(value_text)
                if bpmatch:
                    sbp = to_pos_float(bpmatch.group(1))
                    dbp = to_pos_float(bpmatch.group(2))
            if sbp is None and dbp is None:
                # This is OK; e.g. "BP 110", which we will ignore.
                # log.warning(
                #     "Failed interpretation: matching_text={matching_text}, "
                #     "variable_text={variable_text}, "
                #     "tense_indicator={tense_indicator}, "
                #     "relation={relation}, "
                #     "value_text={value_text}, "
                #     "units={units}".format(
                #         matching_text=repr(matching_text),
                #         variable_text=repr(variable_text),
                #         tense_indicator=repr(tense_indicator),
                #         relation=repr(relation),
                #         value_text=repr(value_text),
                #         units=repr(units),
                #     )
                # )
                continue

            tense, relation = common_tense(tense_indicator, relation_text)

            yield self.tablename, {
                FN_CONTENT: matching_text,
                FN_START: startpos,
                FN_END: endpos,
                FN_VARIABLE_TEXT: variable_text,
                FN_RELATION_TEXT: relation_text,
                FN_RELATION: relation,
                FN_VALUE_TEXT: value_text,
                FN_UNITS: units,
                self.FN_SYSTOLIC_BP_MMHG: sbp,
                self.FN_DIASTOLIC_BP_MMHG: dbp,
                FN_TENSE: tense,
            }

    def test_bp_parser(
            self,
            test_expected_list: List[
                Tuple[str, List[Tuple[float, float]]]
            ],
            verbose: bool = False) -> None:
        print("Testing parser: {}".format(type(self).__name__))
        if verbose:
            print("... regex:\n{}".format(self.REGEX))
        for test_string, expected_values in test_expected_list:
            actual_values = list(
                (x[self.FN_SYSTOLIC_BP_MMHG], x[self.FN_DIASTOLIC_BP_MMHG])
                for t, x in self.parse(test_string)
            )
            assert actual_values == expected_values, (
                "Parser {name}: Expected {expected}, got {actual}, when "
                "parsing {test_string}; full result={full}".format(
                    name=type(self).__name__,
                    expected=expected_values,
                    actual=actual_values,
                    test_string=repr(test_string),
                    full=repr(list(self.parse(test_string))),
                )
            )
        print("... OK")

    def test(self, verbose: bool = False) -> None:
        self.test_bp_parser([
            ("BP", []),  # should fail; no values
            ("his blood pressure was 120/80", [(120, 80)]),
            ("BP 120/80 mmhg", [(120, 80)]),
            ("systolic BP 120", [(120, None)]),
            ("diastolic BP 80", [(None, 80)]),
            ("BP-130/70", [(130, 70)]),
            ("BP 110 /80", [(110, 80)]),
            ("BP 110 /80 -", [(110, 80)]),  # real example
            ("BP 120 / 70 -", [(120, 70)]),  # real example
            ("BP :115 / 70 -", [(115, 70)]),  # real example
            ("B.P 110", []),  # real example
        ], verbose=verbose)
        # 1. Unsure if best to take abs value.
        #    One reason not to might be if people express changes, e.g.
        #    "BP change -40/-10", but I very much doubt it.
        #    Went with abs value using to_pos_float().
        # 2. "BP 110" - too unreliable; not definitely a blood pressure.


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

def test_all(verbose: bool = False) -> None:
    height = Height(None, None)
    height.test(verbose=verbose)
    weight = Weight(None, None)
    weight.test(verbose=verbose)
    bmi = Bmi(None, None)
    bmi.test(verbose=verbose)
    bp = Bp(None, None)
    bp.test(verbose=verbose)


if __name__ == '__main__':
    test_all(verbose=True)
