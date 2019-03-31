#!/usr/bin/env python

"""
crate_anon/nlp_manager/parse_clinical.py

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

**Python regex-based NLP processors for clinical assessment data.**

Most inherit from
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

± these:

debug:
    show debugging information

"""

import logging
import sys
from typing import Any, Dict, Generator, List, Optional, TextIO, Tuple

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
# Anthropometrics
# =============================================================================

# -----------------------------------------------------------------------------
# Height
# -----------------------------------------------------------------------------

class Height(NumericalResultParser):
    """
    Height. Handles metric (e.g. "1.8m") and imperial (e.g. "5 ft 2 in").
    """
    METRIC_HEIGHT = fr"""
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
    """
    IMPERIAL_HEIGHT = fr"""
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
    """
    HEIGHT = r"(?: \b height \b)"
    REGEX = fr"""
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
    """

    COMPILED_REGEX = compile_regex(REGEX)
    NAME = "Height"
    PREFERRED_UNIT_COLUMN = "value_m"

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False,
                 debug: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            regex_str_for_debugging=self.REGEX,
            commit=commit
        )
        if debug:
            print(f"Regex for {type(self).__name__}: {self.REGEX}")

    def parse(self, text: str,
              debug: bool = False) -> Generator[Tuple[str, Dict[str, Any]],
                                                None, None]:
        """
        Parser for Height. Specialized for complex unit conversion.
        """
        for m in self.COMPILED_REGEX.finditer(text):  # watch out: 'm'/metres
            if debug:
                print(f"Match {m} for {repr(text)}")
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
        # docstring in superclass
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
        # *** Height NLP: deal with "tall" and plain "is", e.g.
        # she is 6'2"; she is 1.5m tall


class HeightValidator(ValidatorBase):
    """
    Validator for Height
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
                         regex_str_list=[Height.HEIGHT],
                         validated_variable=Height.NAME,
                         commit=commit)


# -----------------------------------------------------------------------------
# Weight (mass)
# -----------------------------------------------------------------------------

class Weight(NumericalResultParser):
    """
    Weight. Handles metric (e.g. "57kg") and imperial (e.g. "10 st 2 lb").
    """
    METRIC_WEIGHT = fr"""
        (                           # capture group 4
            ( {SIGNED_FLOAT} )          # capture group 5
            {OPTIONAL_RESULTS_IGNORABLES}
            ( {KG} )                    # capture group 6
        )
    """
    IMPERIAL_WEIGHT = fr"""
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
    """
    WEIGHT = r"(?: \b weigh[ts] \b )"  # weight, weighs
    REGEX = fr"""
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
    """

    COMPILED_REGEX = compile_regex(REGEX)
    NAME = "Weight"
    PREFERRED_UNIT_COLUMN = "value_kg"

    def __init__(self,
                 nlpdef: Optional[NlpDefinition],
                 cfgsection: Optional[str],
                 commit: bool = False,
                 debug: bool = False) -> None:
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
            variable=self.NAME,
            target_unit=self.PREFERRED_UNIT_COLUMN,
            regex_str_for_debugging=self.REGEX,
            commit=commit
        )
        if debug:
            print(f"Regex for {type(self).__name__}: {self.REGEX}")

    def parse(self, text: str,
              debug: bool = False) -> Generator[Tuple[str, Dict[str, Any]],
                                                None, None]:
        """
        Parser for Weight. Specialized for complex unit conversion.
        """
        for m in self.COMPILED_REGEX.finditer(text):
            if debug:
                print(f"Match {m} for {repr(text)}")
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
        # docstring in superclass
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
    """
    Validator for Weight
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
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
    """
    Body mass index (BMI) (in kg / m^2).
    """
    BMI = fr"""
        (?: {WORD_BOUNDARY}
            (?: BMI | body \s+ mass \s+ index )
        {WORD_BOUNDARY} )
    """
    REGEX = fr"""
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
    """
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
            ("BMI", []),  # should fail; no values
            ("body mass index was 30", [30]),
            ("his BMI (30) is too high", [30]),
            ("BMI 25 kg/sq m", [25]),
            ("BMI was 18.4 kg/m^-2", [18.4]),
            ("ACE 79", []),
            ("BMI-23", [23]),
        ], verbose=verbose)


class BmiValidator(ValidatorBase):
    """
    Validator for Bmi
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
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
# Bedside investigations: BP
# =============================================================================

class Bp(BaseNlpParser):
    """
    Blood pressure, in mmHg. (Systolic and diastolic.)
    
    (Since we produce two variables, SBP and DBP, and we use something a little
    more complex than
    :class:`crate_anon.nlp_manager.regex_parser.NumeratorOutOfDenominatorParser`,
    we subclass :class:`crate_anon.nlp_manager.regex_parser.BaseNlpParser`
    directly.)
    """  # noqa
    BP = r"(?: \b blood \s+ pressure \b | \b B\.?P\.? \b )"
    SYSTOLIC_BP = fr"(?: \b systolic \s+ {BP} | \b S\.?B\.?P\.? \b )"
    DIASTOLIC_BP = fr"(?: \b diastolic \s+ {BP} | \b D\.?B\.?P\.? \b )"

    TWO_NUMBER_BP = fr"""
        ( {SIGNED_FLOAT} )
        \s* (?: \b over \b | \/ ) \s*
        ( {SIGNED_FLOAT} )
    """
    ONE_NUMBER_BP = SIGNED_FLOAT

    COMPILED_BP = compile_regex(BP)
    COMPILED_SBP = compile_regex(SYSTOLIC_BP)
    COMPILED_DBP = compile_regex(DIASTOLIC_BP)
    COMPILED_ONE_NUMBER_BP = compile_regex(ONE_NUMBER_BP)
    COMPILED_TWO_NUMBER_BP = compile_regex(TWO_NUMBER_BP)
    REGEX = fr"""
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
    """
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
        # see documentation above
        super().__init__(
            nlpdef=nlpdef,
            cfgsection=cfgsection,
            commit=commit
        )
        if nlpdef is None:  # only None for debugging!
            self.tablename = ''
        else:
            self.tablename = nlpdef.opt_str(
                self._sectionname, 'desttable', required=True)

    @classmethod
    def print_info(cls, file: TextIO = sys.stdout) -> None:
        # docstring in superclass
        print(f"Blood pressure finder. Regular expression: \n{cls.REGEX}",
              file=file)

    def dest_tables_columns(self) -> Dict[str, List[Column]]:
        # docstring in superclass
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
        """
        Parser for BP. Specialized because we're fetching two numbers.
        """
        for m in self.COMPILED_REGEX.finditer(text):
            if debug:
                print(f"Match {m} for {repr(text)}")
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
        """
        Called by :func:`test`.

        Args:
            test_expected_list:
                tuple ``source_text, expected_values`` where
                ``expected_values`` is a list of tuples like ``sbp, dbp``.
            verbose:
                be verbose?
        """
        print(f"Testing parser: {type(self).__name__}")
        if verbose:
            print(f"... regex:\n{self.REGEX}")
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
        # docstring in superclass
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
    """
    Validator for Bp
    (see :class:`crate_anon.nlp_manager.regex_parser.ValidatorBase` for
    explanation).
    """
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
# Command-line entry point
# =============================================================================

def test_all(verbose: bool = False) -> None:
    """
    Test all parsers in this module.
    """
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
