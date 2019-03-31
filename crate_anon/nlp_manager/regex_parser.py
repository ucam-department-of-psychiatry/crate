#!/usr/bin/env python

"""
crate_anon/nlp_manager/regex_parser.py

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

**Shared elements for regex-based NLP work.**

"""

import logging
import sys
from typing import Any, Dict, Generator, List, Optional, TextIO, Tuple

from sqlalchemy import Column, Integer, Float, String, Text

from crate_anon.nlp_manager.constants import (
    MAX_SQL_FIELD_LEN,
    SqlTypeDbIdentifier,
)
from crate_anon.nlp_manager.base_nlp_parser import BaseNlpParser
from crate_anon.nlp_manager.nlp_definition import NlpDefinition
from crate_anon.nlp_manager.number import to_float, to_pos_float
from crate_anon.nlp_manager.regex_func import (
    compile_regex,
    compile_regex_dict,
    get_regex_dict_match,
)
from crate_anon.nlp_manager.regex_numbers import (
    BILLION,
    LIBERAL_NUMBER,
    MINUS_SIGN,
    MULTIPLY,
    PLAIN_INTEGER,
    PLAIN_INTEGER_W_THOUSAND_COMMAS,
    PLUS_SIGN,
    POWER,
    POWER_INC_E,
    SCIENTIFIC_NOTATION_EXPONENT,
    SIGN,
    SIGNED_FLOAT,
    SIGNED_INTEGER,
    UNSIGNED_FLOAT,
    UNSIGNED_INTEGER,
)
from crate_anon.nlp_manager.regex_test import test_text_regex
from crate_anon.nlp_manager.regex_units import (
    CELLS,
    CELLS_PER_CUBIC_MM,
    CUBIC_MM,
    OUT_OF_SEPARATOR,
    PER_CUBIC_MM,
    SCORE,
)

log = logging.getLogger(__name__)


# =============================================================================
# Generic entities
# =============================================================================

WORD_BOUNDARY = r"\b"

# -----------------------------------------------------------------------------
# Blood results
# -----------------------------------------------------------------------------

OPTIONAL_RESULTS_IGNORABLES = r"""
    (?:  # OPTIONAL_RESULTS_IGNORABLES
        \s | \| | \:          # whitespace, bar, colon
        | \bHH?\b | \(HH?\)   # H/HH at a word boundary; (H)/(HH)
        | \bLL?\b | \(LL?\)   # L/LL etc.
        | \* | \(\*\) | \(    # *, (*), isolated left parenthesis
        | — | --              # em dash, double hyphen-minus
        | –\s+ | -\s+ | ‐\s+  # en dash/hyphen-minus/Unicode hyphen; whitespace
    )*
"""
# - you often get | characters when people copy/paste tables
# - blood test abnormality markers can look like e.g.
#       17 (H), 17 (*), 17 HH
# - you can also see things like "CRP (5)"
# - However, if there's a right parenthesis only, that's less good, e.g.
#   "Present: Nicola Adams (NA). 1.0. Minutes of the last meeting."
#   ... which we don't want to be interpreted as "sodium 1.0".
#   HOW BEST TO DO THIS?
# - http://stackoverflow.com/questions/546433/regular-expression-to-match-outer-brackets  # noqa
#   http://stackoverflow.com/questions/7898310/using-regex-to-balance-match-parenthesis  # noqa
# - ... simplest is perhaps: base ignorables, or those with brackets, as above
# - ... even better than a nested thing is just a list of alternatives

# -----------------------------------------------------------------------------
# Tense indicators
# -----------------------------------------------------------------------------

IS = "is"
WAS = "was"
TENSE_INDICATOR = fr"(?: \b {IS} \b | \b {WAS} \b )"

# Standardized result values
PAST = "past"
PRESENT = "present"
TENSE_LOOKUP = compile_regex_dict({
    IS: PRESENT,
    WAS: PAST,
})

# -----------------------------------------------------------------------------
# Mathematical relations
# -----------------------------------------------------------------------------
# ... don't use unnamed groups here; EQ is also used as a return value

LT = r"(?: < | less \s+ than )"
LE = "<="
EQ = r"(?: = | equals | equal \s+ to )"
GE = ">="
GT = r"(?: > | (?:more|greater) \s+ than )"
# OF = "\b of \b"  # as in: "a BMI of 30"... but too likely to be mistaken for a target?  # noqa

RELATION = fr"(?: {LE} | {LT} | {EQ} | {GE} | {GT} )"
# ... ORDER MATTERS: greedier things first, i.e.
# - LE before LT
# - GE before GT

RELATION_LOOKUP = compile_regex_dict({
    # To standardize the output, so (for example) "=" and "equals" can both
    # map to "=".
    LT: "<",
    LE: "<=",
    EQ: "=",
    GE: ">=",
    GT: ">",
})

# -----------------------------------------------------------------------------
# Punctuation
# -----------------------------------------------------------------------------

APOSTROPHE = "[\'’]"  # ASCII apostrophe; right single quote (U+2019)

# =============================================================================
# Generic processors
# =============================================================================

FN_VARIABLE_NAME = 'variable_name'
FN_CONTENT = '_content'
FN_START = '_start'
FN_END = '_end'
FN_VARIABLE_TEXT = 'variable_text'
FN_RELATION_TEXT = 'relation_text'
FN_RELATION = 'relation'
FN_VALUE_TEXT = 'value_text'
FN_UNITS = 'units'
FN_TENSE_TEXT = 'tense_text'
FN_TENSE = 'tense'

HELP_VARIABLE_NAME = "Variable name"
HELP_CONTENT = "Matching text contents"
HELP_START = "Start position (of matching string within whole text)"
HELP_END = "End position (of matching string within whole text)"
HELP_VARIABLE_TEXT = "Text that matched the variable name"
HELP_RELATION_TEXT = (
    "Text that matched the mathematical relationship between variable and "
    "value (e.g. '=', '<=', 'less than')"
)
HELP_RELATION = (
    "Standardized mathematical relationship between variable and value "
    "(e.g. '=', '<=')"
)
HELP_VALUE_TEXT = "Matched numerical value, as text"
HELP_UNITS = HELP_VALUE_TEXT
HELP_TARGET_UNIT = "Numerical value in preferred units, if known"
HELP_TENSE_TEXT = f"Tense text, if known (e.g. '{IS}', '{WAS}')"
HELP_TENSE = f"Calculated tense, if known (e.g. '{PAST}', '{PRESENT}')"

MAX_RELATION_TEXT_LENGTH = 50
MAX_RELATION_LENGTH = max(len(x) for x in RELATION_LOOKUP.values())
MAX_VALUE_TEXT_LENGTH = 50
MAX_UNITS_LENGTH = 50
MAX_TENSE_TEXT_LENGTH = 50
MAX_TENSE_LENGTH = max(len(x) for x in TENSE_LOOKUP.values())


def common_tense(tense_text: Optional[str], relation_text: Optional[str]) \
        -> Tuple[Optional[str], Optional[str]]:
    """
    Takes strings potentially representing "tense" and "equality" concepts
    and unifies them.

    - Used, for example, to help impute that "CRP was 72" means that relation
      was EQ in the PAST, etc.

    Args:
        tense_text: putative tense information
        relation_text: putative relationship (equals, less than, etc.)

    Returns:
         tuple: ``tense, relation``; either may be ``None``.
    """
    tense = None
    if tense_text:
        _, tense = get_regex_dict_match(tense_text, TENSE_LOOKUP)
    elif relation_text:
        _, tense = get_regex_dict_match(relation_text, TENSE_LOOKUP)

    _, relation = get_regex_dict_match(relation_text, RELATION_LOOKUP, "=")

    return tense, relation


class NumericalResultParser(BaseNlpParser):
    """
    DO NOT USE DIRECTLY. Base class for generic numerical results, where
    a SINGLE variable is produced.
    """

    def __init__(self,
                 nlpdef: NlpDefinition,
                 cfgsection: str,
                 variable: str,
                 target_unit: str,
                 regex_str_for_debugging: str,
                 commit: bool = False) -> None:
        """
        Args:
            nlpdef:
                :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
            cfgsection:
                config section name in the :ref:`NLP config file <nlp_config>`
            variable:
                used by subclasses as the record value for ``variable_name``
            target_unit:
                fieldname used for the primary output quantity
            regex_str_for_debugging:
                string form of regex, for debugging
            commit:
                force a COMMIT whenever we insert data? You should specify this
                in multiprocess mode, or you may get database deadlocks.
        """
        super().__init__(nlpdef=nlpdef, cfgsection=cfgsection, commit=commit)
        self.variable = variable
        self.target_unit = target_unit
        self.regex_str_for_debugging = regex_str_for_debugging

        if nlpdef is None:  # only None for debugging!
            self.tablename = ''
            self.assume_preferred_unit = True
        else:
            self.tablename = nlpdef.opt_str(
                self._sectionname, 'desttable', required=True)
            self.assume_preferred_unit = nlpdef.opt_bool(
                self._sectionname, 'assume_preferred_unit', default=True)

        # Sanity checks
        assert len(self.variable) <= MAX_SQL_FIELD_LEN, (
            f"Variable name too long (max {MAX_SQL_FIELD_LEN} characters)")

    def print_info(self, file: TextIO = sys.stdout) -> None:
        # docstring in superclass
        print(
            f"NLP class to find numerical results. Regular expression: "
            f"\n\n{self.regex_str_for_debugging}", file=file)

    def get_regex_str_for_debugging(self) -> str:
        """
        Returns the string version of the regex, for debugging.
        """
        return self.regex_str_for_debugging

    def set_tablename(self, tablename: str) -> None:
        """
        In case a friend class wants to override.
        """
        self.tablename = tablename

    def dest_tables_columns(self) -> Dict[str, List[Column]]:
        # docstring in superclass
        return {self.tablename: [
            Column(FN_VARIABLE_NAME, SqlTypeDbIdentifier,
                   doc=HELP_VARIABLE_NAME),
            Column(FN_CONTENT, Text, doc=HELP_CONTENT),
            Column(FN_START, Integer, doc=HELP_START),
            Column(FN_END, Integer, doc=HELP_END),
            Column(FN_VARIABLE_TEXT, Text, doc=HELP_VARIABLE_TEXT),
            Column(FN_RELATION_TEXT, String(MAX_RELATION_TEXT_LENGTH),
                   doc=HELP_RELATION_TEXT),
            Column(FN_RELATION, String(MAX_RELATION_LENGTH),
                   doc=HELP_RELATION),
            Column(FN_VALUE_TEXT, Text, doc=HELP_VALUE_TEXT),
            Column(FN_UNITS, String(MAX_UNITS_LENGTH), doc=HELP_UNITS),
            Column(self.target_unit, Float, doc=HELP_TARGET_UNIT),
            Column(FN_TENSE_TEXT, String(MAX_TENSE_TEXT_LENGTH),
                   doc=HELP_TENSE_TEXT),
            Column(FN_TENSE, String(MAX_TENSE_LENGTH), doc=HELP_TENSE),
        ]}

    def parse(self, text: str) -> Generator[Tuple[str, Dict[str, Any]],
                                            None, None]:
        # docstring in superclass
        raise NotImplementedError

    def test_numerical_parser(
            self,
            test_expected_list: List[Tuple[str, List[float]]],
            verbose: bool = False) -> None:
        """
        Args:
            test_expected_list:
                list of tuples ``test_string, expected_values``. The parser
                will parse ``test_string`` and compare the result (each value
                of the target unit) to ``expected_values``, which is a list of
                numerical (``float``), and can be an empty list.
            verbose:
                show the regex string too

        Raises:
            :exc:`AssertionError` if a comparison fails
        """
        print(f"Testing parser: {type(self).__name__}")
        if verbose:
            print(f"... regex string:\n{self.regex_str_for_debugging}")
        for test_string, expected_values in test_expected_list:
            actual_values = list(
                x[self.target_unit] for t, x in self.parse(test_string)
            )
            assert actual_values == expected_values, (
                "Parser {name}: Expected {expected}, got {actual}, when "
                "parsing {test_string}; full result:\n{full}".format(
                    name=type(self).__name__,
                    expected=expected_values,
                    actual=actual_values,
                    test_string=repr(test_string),
                    full=repr(list(self.parse(test_string))),
                )
            )
        print("... OK")

    # noinspection PyUnusedLocal
    def detailed_test(self, text: str, expected: List[Dict[str, Any]],
                      verbose: bool = False) -> None:
        """
        Runs a more detailed check. Whereas :func:`test_numerical_parser` tests
        the primary numerical results, this function tests other key/value
        pairs returned by the parser.

        Args:
            text:
                text to parse
            expected:
                list of ``resultdict`` dictionaries (each mapping column names
                to values).

                - The parser should return one result dictionary for
                  every entry in ``expected``.
                - It's fine for the ``resultdict`` not to include all the
                  columns returned for the parser. However, for any column that
                  is present, the parser must provide the corresponding value.

            verbose:
                unused
        """
        i = 0
        for _, values in self.parse(text):
            if i >= len(expected):
                raise ValueError(
                    f"Too few expected values. Extra result is: {values!r}")
            expected_values = expected[i]
            for key, exp_val in expected_values.items():
                if key not in values:
                    raise ValueError(f"Test built wrong: expected key {key!r} "
                                     f"missing; result was {values!r}")
                if values[key] != exp_val:
                    raise ValueError(
                        f"For key {key!r}, expected {exp_val!r}, "
                        f"got {values[key]!r}; full result is {values!r}; "
                        f"test text is {text!r}")
            i += 1
        print("... detailed_test: pass")


class SimpleNumericalResultParser(NumericalResultParser):
    """
    Base class for simple single-format numerical results. Use this when not
    only do you have a single variable to produce, but you have a single regex
    (in a standard format) that can produce it.
    """
    def __init__(self,
                 nlpdef: NlpDefinition,
                 cfgsection: str,
                 regex_str: str,
                 variable: str,
                 target_unit: str,
                 units_to_factor: Dict[str, float],
                 take_absolute: bool = False,
                 commit: bool = False,
                 debug: bool = False) -> None:
        """
        Args:

            nlpdef:
                :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`

            cfgsection:
                config section name in the :ref:`NLP config file <nlp_config>`

            regex_str:
                Regular expression, in string format.

                This class operates with compiled regexes having this group
                format (capture groups in this sequence):

                - variable
                - tense_indicator
                - relation
                - value
                - units

            variable:
                used as the record value for ``variable_name``

            target_unit:
                fieldname used for the primary output quantity

            units_to_factor:
                dictionary, mapping

                - FROM (compiled regex for units)
                - TO EITHER a float (multiple) to multiply those units by, to
                  get the preferred unit
                - OR a function taking a text parameter and returning a float
                  value in preferred unit

                Any units present in the regex but absent from
                ``units_to_factor`` will lead the result to be ignored. For
                example, this allows you to ignore a relative neutrophil count
                ("neutrophils 2.2%") while detecting absolute neutrophil counts
                ("neutrophils 2.2"), or ignoring "docusate sodium 100mg" but
                detecting "sodium 140 mM".

            take_absolute:
                Convert negative values to positive ones? Typical text
                requiring this option might look like:

                .. code-block:: none

                    CRP-4
                    CRP-106
                    CRP -97
                    Blood results for today as follows: Na- 142, K-4.1, ...

                ... occurring in 23 out of 8054 hits for CRP of one test set in
                our data.

                For many quantities, we know that they cannot be negative, so
                this is just a notation rather than a minus sign. We have to
                account for it, or it'll distort our values. Preferable to
                account for it here rather than later; see manual.

            commit:
                force a COMMIT whenever we insert data? You should specify this
                in multiprocess mode, or you may get database deadlocks.

            debug:
                print the regex?

        """
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         variable=variable,
                         target_unit=target_unit,
                         regex_str_for_debugging=regex_str,
                         commit=commit)
        if debug:
            print(f"Regex for {type(self).__name__}: {regex_str}")
        self.compiled_regex = compile_regex(regex_str)
        self.units_to_factor = compile_regex_dict(units_to_factor)
        self.take_absolute = take_absolute

    def parse(self, text: str,
              debug: bool = False) -> Generator[Tuple[str, Dict[str, Any]],
                                                None, None]:
        # docstring in superclass
        if not text:
            return
        for m in self.compiled_regex.finditer(text):
            startpos = m.start()
            endpos = m.end()
            # groups = repr(m.groups())  # all matching groups
            matching_text = m.group(0)  # the whole thing
            # matching_text = text[startpos:endpos]  # same thing

            variable_text = m.group(1)
            tense_text = m.group(2)
            relation_text = m.group(3)
            value_text = m.group(4)
            units = m.group(5)

            # If units are known (or we're choosing to assume preferred units
            # if none are specified), calculate an absolute value
            value_in_target_units = None
            if units:
                matched_unit, multiple_or_fn = get_regex_dict_match(
                    units, self.units_to_factor)
                if not matched_unit:
                    # None of our units match. But there is a unit, and the
                    # regex matched. So this is a BAD unit. Skip the value.
                    continue
                # Otherwise: we did match a unit.
                if callable(multiple_or_fn):
                    value_in_target_units = multiple_or_fn(value_text)
                else:
                    value_in_target_units = (to_float(value_text) *
                                             multiple_or_fn)
            elif self.assume_preferred_unit:  # unit is None or empty
                value_in_target_units = to_float(value_text)

            if value_in_target_units is not None and self.take_absolute:
                value_in_target_units = abs(value_in_target_units)

            tense, relation = common_tense(tense_text, relation_text)

            result = {
                FN_VARIABLE_NAME: self.variable,
                FN_CONTENT: matching_text,
                FN_START: startpos,
                FN_END: endpos,

                FN_VARIABLE_TEXT: variable_text,
                FN_RELATION_TEXT: relation_text,
                FN_RELATION: relation,
                FN_VALUE_TEXT: value_text,
                FN_UNITS: units,
                self.target_unit: value_in_target_units,
                FN_TENSE_TEXT: tense_text,
                FN_TENSE: tense,
            }
            # log.critical(result)
            if debug:
                print(f"Match {m} for {repr(text)} -> {result}")
            yield self.tablename, result


class NumeratorOutOfDenominatorParser(BaseNlpParser):
    """
    Base class for X-out-of-Y numerical results, e.g. for MMSE/ACE.

    - Integer denominator, expected to be positive.
    - Otherwise similar to :class:`SimpleNumericalResultParser`.
    """
    def __init__(self,
                 nlpdef: NlpDefinition,
                 cfgsection: str,
                 variable_name: str,  # e.g. "MMSE"
                 variable_regex_str: str,  # e.g. regex for MMSE
                 expected_denominator: int,
                 numerator_text_fieldname: str = "numerator_text",
                 numerator_fieldname: str = "numerator",
                 denominator_text_fieldname: str = "denominator_text",
                 denominator_fieldname: str = "denominator",
                 correct_numerator_fieldname: str = None,  # default below
                 take_absolute: bool = True,
                 commit: bool = False,
                 debug: bool = False) -> None:
        """
        This class operates with compiled regexes having this group format:
          - quantity_regex_str: e.g. to find "MMSE"

        Args:
            nlpdef:
                a :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
            cfgsection:
                the name of a CRATE NLP config file section (from which we may
                choose to get extra config information)
            variable_name:
                becomes the content of the ``variable_name`` output column
            variable_regex_str:
                regex for the text that states the variable
            expected_denominator:
                the integer value that's expected as the "out of Y" part. For
                example, an MMSE is out of 30; an ACE-III total is out of 100.
                If the text just says "MMSE 17", we will infer "17 out of 30";
                so, for the MMSE, ``expected_denominator`` should be 30.
            numerator_text_fieldname:
                field (column) name in which to store the text retrieved as the
                numerator
            numerator_fieldname:
                field (column) name in which to store the numerical value
                retrieved as the numerator
            denominator_text_fieldname:
                field (column) name in which to store the text retrieved as the
                denominator
            denominator_fieldname:
                field (column) name in which to store the numerical value
                retrieved as the denominator
            correct_numerator_fieldname:
                field (column) name in which we store the principal validated
                numerator. For example, if an MMSE processor sees "17" or
                "17/30", this field will end up containing 17; but if it sees
                "17/100", it will remain NULL.
            take_absolute:
                Convert negative values to positive ones?
                As for :class:`SimpleNumericalResultParser`.
            commit:
                force a COMMIT whenever we insert data? You should specify this
                in multiprocess mode, or you may get database deadlocks.
            debug:
                print the regex?

        """
        self.variable_name = variable_name
        assert(expected_denominator > 0)
        self.expected_denominator = expected_denominator
        self.numerator_text_fieldname = numerator_text_fieldname
        self.numerator_fieldname = numerator_fieldname
        self.denominator_text_fieldname = denominator_text_fieldname
        self.denominator_fieldname = denominator_fieldname
        self.correct_numerator_fieldname = (
            correct_numerator_fieldname or
            f"out_of_{expected_denominator}")
        self.take_absolute = take_absolute

        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         commit=commit)
        if nlpdef is None:  # only None for debugging!
            self.tablename = ''
        else:
            self.tablename = nlpdef.opt_str(
                self._sectionname, 'desttable', required=True)

        regex_str = fr"""
            ( {variable_regex_str} )           # 1. group for variable (thing being measured)
            {OPTIONAL_RESULTS_IGNORABLES}
            {SCORE}?                           # optional "score" or similar
            {OPTIONAL_RESULTS_IGNORABLES}
            ( {TENSE_INDICATOR} )?             # 2. optional group for tense indicator
            {OPTIONAL_RESULTS_IGNORABLES}
            ( {RELATION} )?                    # 3. optional group for relation
            {OPTIONAL_RESULTS_IGNORABLES}
            ( {SIGNED_FLOAT} )                 # 4. group for numerator
            (?:                                # optional "/ denominator"
                \s* {OUT_OF_SEPARATOR} \s*
                ( {UNSIGNED_INTEGER} )         # 5. group for denominator
            )?
        """  # noqa
        if debug:
            print(f"Regex for {type(self).__name__}: {regex_str}")
        self.regex_str = regex_str
        self.compiled_regex = compile_regex(regex_str)

    def print_info(self, file: TextIO = sys.stdout) -> None:
        # docstring in superclass
        print(
            f"NLP class to find X-out-of-Y results. Regular expression: "
            f"\n\n{self.regex_str}", file=file)

    def dest_tables_columns(self) -> Dict[str, List[Column]]:
        # docstring in superclass
        return {self.tablename: [
            Column(FN_VARIABLE_NAME, SqlTypeDbIdentifier,
                   doc=HELP_VARIABLE_NAME),
            Column(FN_CONTENT, Text, doc=HELP_CONTENT),
            Column(FN_START, Integer, doc=HELP_START),
            Column(FN_END, Integer, doc=HELP_END),
            Column(FN_VARIABLE_TEXT, Text, doc=HELP_VARIABLE_TEXT),
            Column(FN_RELATION_TEXT, String(MAX_RELATION_TEXT_LENGTH),
                   doc=HELP_RELATION_TEXT),
            Column(FN_RELATION, String(MAX_RELATION_LENGTH),
                   doc=HELP_RELATION),
            Column(self.numerator_text_fieldname,
                   String(MAX_VALUE_TEXT_LENGTH),
                   doc="Numerator, as text"),
            Column(self.numerator_fieldname, Float,
                   doc="Numerator"),
            Column(self.denominator_text_fieldname,
                   String(MAX_VALUE_TEXT_LENGTH),
                   doc="Denominator, as text"),
            Column(self.denominator_fieldname, Float,
                   doc="Denominator"),
            Column(self.correct_numerator_fieldname, Float,
                   doc="Numerator, if denominator is as expected (units are "
                       "correct)"),
            Column(FN_TENSE, String(MAX_TENSE_LENGTH), doc=HELP_TENSE),
        ]}

    def parse(self, text: str,
              debug: bool = False) -> Generator[Tuple[str, Dict[str, Any]],
                                                None, None]:
        # docstring in superclass
        for m in self.compiled_regex.finditer(text):
            startpos = m.start()
            endpos = m.end()
            # groups = repr(m.groups())  # all matching groups
            matching_text = m.group(0)  # the whole thing
            # matching_text = text[startpos:endpos]  # same thing

            variable_text = m.group(1)
            tense_text = m.group(2)
            relation_text = m.group(3)
            numerator_text = m.group(4)
            denominator_text = m.group(5)

            if self.take_absolute:
                numerator = to_pos_float(numerator_text)
            else:
                numerator = to_float(numerator_text)
            denominator = to_float(denominator_text)

            if numerator is None:
                log.critical("bug - numerator is None, should be impossible")
                continue
            correct_numerator = None
            if denominator is None:
                if numerator <= self.expected_denominator:
                    correct_numerator = numerator
            else:
                if numerator <= denominator == self.expected_denominator:
                    correct_numerator = numerator

            tense, relation = common_tense(tense_text, relation_text)

            result = {
                FN_VARIABLE_NAME: self.variable_name,
                FN_CONTENT: matching_text,
                FN_START: startpos,
                FN_END: endpos,

                FN_VARIABLE_TEXT: variable_text,
                FN_RELATION_TEXT: relation_text,
                FN_RELATION: relation,
                self.numerator_text_fieldname: numerator_text,
                self.numerator_fieldname: numerator,
                self.denominator_text_fieldname: denominator_text,
                self.denominator_fieldname: denominator,
                self.correct_numerator_fieldname: correct_numerator,
                FN_TENSE_TEXT: tense_text,
                FN_TENSE: tense,
            }
            # log.critical(result)
            if debug:
                print(f"Match {m} for {repr(text)} -> {result}")
            yield self.tablename, result

    def test_numerator_denominator_parser(
            self,
            test_expected_list: List[
                Tuple[str, List[Tuple[float, float]]]
            ],
            verbose: bool = False) -> None:
        """
        Test the parser.

        Args:
            test_expected_list:
                list of tuples ``test_string, expected_values``. The parser
                will parse ``test_string`` and compare the result (each value
                of the target unit) to ``expected_values``, which is a list of
                tuples ``numerator, denominator``, and can be an empty list.
            verbose:
                print the regex?

        Raises:
            :exc:`AssertionError` if a comparison fails
        """
        print(f"Testing parser: {type(self).__name__}")
        if verbose:
            print(f"... regex:\n{self.regex_str}")
        for test_string, expected_values in test_expected_list:
            actual_values = list(
                (x[self.numerator_fieldname], x[self.denominator_fieldname])
                for t, x in self.parse(test_string)
            )
            assert actual_values == expected_values, (
                "Parser {name}: Expected {expected}, got {actual}, when "
                "parsing {test_string}; full result:\n{full}".format(
                    name=type(self).__name__,
                    expected=expected_values,
                    actual=actual_values,
                    test_string=repr(test_string),
                    full=repr(list(self.parse(test_string))),
                )
            )


# =============================================================================
#  More general testing
# =============================================================================

class ValidatorBase(BaseNlpParser):
    """
    DO NOT USE DIRECTLY. Base class for **validating** regex parser
    sensitivity.

    The validator will find fields that refer to the variable, whether or not
    they meet the other criteria of the actual NLP processors (i.e. whether or
    not they contain a valid value). More explanation below.

    Suppose we're validating C-reactive protein (CRP). Key concepts:

    - source (true state of the world): Pr present, Ab absent
    - software decision: Y yes, N no
    - signal detection theory classification:

      - hit = Pr & Y = true positive
      - miss = Pr & N = false negative
      - false alarm = Ab & Y = false positive
      - correct rejection = Ab & N = true negative

    - common SDT metrics:

      - positive predictive value, PPV = P(Pr | Y) = precision (\*)
      - negative predictive value, NPV = P(Ab | N)
      - sensitivity = P(Y | Pr) = recall (*) = true positive rate
      - specificity = P(N | Ab) = true negative rate

      (\*) common names used in the NLP context.

    - other common classifier metric:

      .. code-block:: none

        F_beta score = (1 + beta^2) * precision * recall /
                       ((beta^2 * precision) + recall)

      ... which measures performance when you value recall beta times as much
      as precision (thus, for example, the F1 score when beta = 1). See
      https://en.wikipedia.org/wiki/F1_score/

    Working from source to NLP, we can see there are a few types of "absent":

    - X. unselected database field containing text

        - Q. field contains "CRP", "C-reactive protein", etc.; something
          that a human (or as a proxy: a machine) would judge as
          containing a textual reference to CRP.

            - Pr. Present: a human would judge that a CRP value is present,
                e.g. "today her CRP is 7, which I am not concerned about."

                - H.  Hit: software reports the value.
                - M.  Miss: software misses the value.
                  (maybe: "his CRP was twenty-one".)

            - Ab1. Absent: reference to CRP, but no numerical information,
              e.g. "her CRP was normal".

                - FA1. False alarm: software reports a numerical value.
                  (maybe: "my CRP was 7 hours behind my boss's deadline")
                - CR1. Correct rejection: software doesn't report a value.

        - Ab2. field contains no reference to CRP at all.

                - FA2. False alarm: software reports a numerical value.
                  (a bit hard to think of examples...)

                - CR2. Correct rejection: software doesn't report a value.

    From NLP backwards to source:

    - Y. Software says value present.

        - H. Hit: value is present.
        - FA. False alarm: value is absent.

    - N. Software says value absent.

        - CR. Correct rejection: value is absent.
        - M. Miss: value is present.

    The key metrics are:

    - precision = positive predictive value = P(Pr | Y)

      ... relatively easy to check; find all the "Y" records and check
      manually that they're correct.

    - sensitivity = recall = P(Y | Pr)

      ... Here, we want a sample that is enriched for "symptom actually
      present", for human reasons. For example, if 0.1% of text entries
      refer to CRP, then to assess 100 "Pr" samples we would have to
      review 100,000 text records, 99,900 of which are completely
      irrelevant. So we want an automated way of finding "Pr" records.
      That's what the validator classes do.

    You can enrich for "Pr" records with SQL, e.g.

    .. code-block:: sql

        SELECT textfield FROM sometable WHERE (
            textfield LIKE '%CRP%'
            OR textfield LIKE '%C-reactive protein%');

    or similar, but really we want the best "CRP detector" possible. That is
    probably to use a regex, either in SQL (... ``WHERE textfield REGEX
    'myregex'``) or using these validator classes. (The main NLP regexes don't
    distinguish between "CRP present, no valid value" and "CRP absent",
    because regexes either match or don't.)

    Each validator class implements the core variable-finding part of its
    corresponding NLP regex class, but without the value or units. For example,
    the CRP class looks for things like "CRP is 6" or "CRP 20 mg/L", whereas
    the CRP validator looks for things like "CRP".

    """

    def __init__(self,
                 nlpdef: NlpDefinition,
                 cfgsection: str,
                 regex_str_list: List[str],
                 validated_variable: str,
                 commit: bool = False) -> None:
        """
        Args:
            nlpdef:
                :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`

            cfgsection:
                config section name in the :ref:`NLP config file <nlp_config>`

            regex_str_list:
                List of regular expressions, each in string format.

                This class operates with compiled regexes having this group
                format (capture groups in this sequence):

                - variable

            validated_variable:
                used to set our ``variable`` attribute and thus the value of
                the field ``variable_name`` in the NLP output; for example, if
                ``validated_variable == 'crp'``, then the ``variable_name``
                field will be set to ``crp_validator``.

            commit:
                force a COMMIT whenever we insert data? You should specify this
                in multiprocess mode, or you may get database deadlocks.
        """
        super().__init__(nlpdef=nlpdef, cfgsection=cfgsection, commit=commit)
        self.regex_str_list = regex_str_list  # for debugging only
        self.compiled_regex_list = [compile_regex(r) for r in regex_str_list]
        self.variable = f"{validated_variable}_validator"
        self.NAME = self.variable

        if nlpdef is None:  # only None for debugging!
            self.tablename = ''
        else:
            self.tablename = nlpdef.opt_str(
                self._sectionname, 'desttable', required=True)

    def print_info(self, file: TextIO = sys.stdout) -> None:
        # docstring in superclass
        print("NLP class to validate other NLP processors. Regular "
              "expressions:\n\n", file=file)
        print("\n\n".join(self.regex_str_list), file=file)

    def set_tablename(self, tablename: str) -> None:
        """In case a friend class wants to override."""
        self.tablename = tablename

    def dest_tables_columns(self) -> Dict[str, List[Column]]:
        # docstring in superclass
        return {self.tablename: [
            Column(FN_VARIABLE_NAME, SqlTypeDbIdentifier,
                   doc=HELP_VARIABLE_NAME),
            Column(FN_CONTENT, Text, doc=HELP_CONTENT),
            Column(FN_START, Integer, doc=HELP_START),
            Column(FN_END, Integer, doc=HELP_END),
        ]}

    def parse(self, text: str) -> Generator[Tuple[str, Dict[str, Any]],
                                            None, None]:
        # docstring in superclass
        for compiled_regex in self.compiled_regex_list:
            for m in compiled_regex.finditer(text):
                startpos = m.start()
                endpos = m.end()
                # groups = repr(m.groups())  # all matching groups
                matching_text = m.group(0)  # the whole thing
                # matching_text = text[startpos:endpos]  # same thing

                yield self.tablename, {
                    FN_VARIABLE_NAME: self.variable,
                    FN_CONTENT: matching_text,
                    FN_START: startpos,
                    FN_END: endpos,
                }

    def test_validator(self, test_expected_list: List[Tuple[str, bool]],
                       verbose: bool = False) -> None:
        """
        The 'bool' part of test_expected_list is: should it match any?
        ... noting that "match anywhere" is the "search" function, whereas
        "match" matches at the beginning:

            https://docs.python.org/3/library/re.html#re.regex.match
        """
        print(f"Testing validator: {type(self).__name__}")
        if verbose:
            n = len(self.regex_str_list)
            for i, r in enumerate(self.regex_str_list):
                print(f"... regex #{i + 1}/{n}: {r}\n")
        for test_string, expected_match in test_expected_list:
            actual_match = any(r.search(test_string)
                               for r in self.compiled_regex_list)
            assert actual_match == expected_match, (
                "Validator {name}: Expected 'any search'={expected}, got "
                "{actual}, when parsing {test_string}; full={full}".format(
                    name=type(self).__name__,
                    expected=expected_match,
                    actual=actual_match,
                    test_string=repr(test_string),
                    full=list(r.search(test_string)
                              for r in self.compiled_regex_list),
                )
            )
        print("... OK")

    def test(self, verbose: bool = False) -> None:
        print(f"... no tests implemented for validator {type(self).__name__}")


# =============================================================================
# More general testing
# =============================================================================

def learning_alternative_regex_groups():
    """
    Function to learn about regex syntax.
    """
    regex_str = r"""
        (
            (?:
                \s*
                (?: (a) | (b) | (c) | (d) )
                \s*
            )*
            ( fish )?
        )
    """
    compiled_regex = compile_regex(regex_str)
    for test_str in ("a", "b", "a c", "d", "e", "a fish", "c c c"):
        m = compiled_regex.match(test_str)
        print(f"Match: {m}; groups: {m.groups()}")
    """
    So:
        - groups can overlap
        - groups are ordered by their opening bracket
        - matches are filled in neatly
    """


def test_base_regexes(verbose: bool = False) -> None:
    """
    Test all the base regular expressions.
    """
    # -------------------------------------------------------------------------
    # Operators, etc.
    # -------------------------------------------------------------------------
    test_text_regex("MULTIPLY", MULTIPLY, [
        ("a * b", ["*"]),
        ("a x b", ["x"]),
        ("a × b", ["×"]),
        ("a ⋅ b", ["⋅"]),
        ("a blah b", []),
    ], verbose=verbose)
    test_text_regex("POWER", POWER, [
        ("a ^ b", ["^"]),
        ("a ** b", ["**"]),
        ("10e5", []),
        ("10E5", []),
        ("a blah b", []),
    ], verbose=verbose)
    test_text_regex("POWER_INC_E", POWER_INC_E, [
        ("a ^ b", ["^"]),
        ("a ** b", ["**"]),
        ("10e5", ["e"]),
        ("10E5", ["E"]),
        ("a blah b", []),
    ], verbose=verbose)
    test_text_regex("BILLION", BILLION, [
        ("10 x 10^9/l", ["x 10^9"]),
    ], verbose=verbose)
    test_text_regex("PLUS_SIGN", PLUS_SIGN, [
        ("a + b", ["+"]),
        ("a blah b", []),
    ], verbose=verbose)
    test_text_regex("MINUS_SIGN", MINUS_SIGN, [
        # good:
        ("a - b", ["-"]),  # ASCII hyphen-minus
        ("a − b", ["−"]),  # Unicode minus
        ("a – b", ["–"]),  # en dash
        # bad:
        ("a — b", []),  # em dash
        ("a ‐ b", []),  # Unicode formal hyphen
        ("a blah b", []),
    ], verbose=verbose)
    # Can't test optional regexes very easily! They match nothing.
    test_text_regex("SIGN", SIGN, [
        # good:
        ("a + b", ["+"]),
        ("a - b", ["-"]),  # ASCII hyphen-minus
        ("a − b", ["−"]),  # Unicode minus
        ("a – b", ["–"]),  # en dash
        # bad:
        ("a — b", []),  # em dash
        ("a ‐ b", []),  # Unicode formal hyphen
        ("a blah b", []),
    ], verbose=verbose)

    # -------------------------------------------------------------------------
    # Number elements
    # -------------------------------------------------------------------------
    test_text_regex("PLAIN_INTEGER", PLAIN_INTEGER, [
        ("a 1234 b", ["1234"]),
        ("a 1234.5 b", ["1234", "5"]),
        ("a 12,000 b", ["12", "000"]),
    ], verbose=verbose)
    test_text_regex(
        "PLAIN_INTEGER_W_THOUSAND_COMMAS",
        PLAIN_INTEGER_W_THOUSAND_COMMAS,
        [
            ("a 1234 b", ["1234"]),
            ("a 1234.5 b", ["1234", "5"]),
            ("a 12,000 b", ["12,000"]),
        ],
        verbose=verbose
    )
    test_text_regex(
        "SCIENTIFIC_NOTATION_EXPONENT",
        SCIENTIFIC_NOTATION_EXPONENT,
        [
            ("a 1234 b", []),
            ("E-4", ["E-4"]),
            ("e15", ["e15"]),
            ("e15.3", ["e15"]),
        ],
        verbose=verbose
    )

    # -------------------------------------------------------------------------
    # Number types
    # -------------------------------------------------------------------------

    test_text_regex("UNSIGNED_INTEGER", UNSIGNED_INTEGER, [
        ("1", ["1"]),
        ("12345", ["12345"]),
        ("-1", ["1"]),  # will drop sign
        ("1.2", ["1", "2"]),
        ("-3.4", ["3", "4"]),
        ("+3.4", ["3", "4"]),
        ("-3.4e27.3", ["3", "4", "27", "3"]),
        ("3.4e-27", ["3", "4", "27"]),
        ("9,800", ["9,800"]),
        ("17,600.34", ["17,600", "34"]),
        ("-17,300.6588", ["17,300", "6588"]),
    ], verbose=verbose)
    test_text_regex("SIGNED_INTEGER", SIGNED_INTEGER, [
        ("1", ["1"]),
        ("12345", ["12345"]),
        ("-1", ["-1"]),
        ("1.2", ["1", "2"]),
        ("-3.4", ["-3", "4"]),
        ("+3.4", ["+3", "4"]),
        ("-3.4e27.3", ["-3", "4", "27", "3"]),
        ("3.4e-27", ["3", "4", "-27"]),
        ("9,800", ["9,800"]),
        ("17,600.34", ["17,600", "34"]),
        ("-17,300.6588", ["-17,300", "6588"]),
    ], verbose=verbose)
    test_text_regex("UNSIGNED_FLOAT", UNSIGNED_FLOAT, [
        ("1", ["1"]),
        ("12345", ["12345"]),
        ("-1", ["1"]),
        ("1.2", ["1.2"]),
        ("-3.4", ["3.4"]),
        ("+3.4", ["+3.4"]),
        ("-3.4e27.3", ["3.4", "27.3"]),
        ("3.4e-27", ["3.4", "27"]),
        ("9,800", ["9,800"]),
        ("17,600.34", ["17,600.34"]),
        ("-17,300.6588", ["17,300.6588"]),
    ], verbose=verbose)
    test_text_regex("SIGNED_FLOAT", SIGNED_FLOAT, [
        ("1", ["1"]),
        ("12345", ["12345"]),
        ("-1", ["-1"]),
        ("1.2", ["1.2"]),
        ("-3.4", ["-3.4"]),
        ("+3.4", ["+3.4"]),
        ("-3.4e27.3", ["-3.4", "27.3"]),
        ("3.4e-27", ["3.4", "-27"]),
        ("9,800", ["9,800"]),
        ("17,600.34", ["17,600.34"]),
        ("-17,300.6588", ["-17,300.6588"]),
    ], verbose=verbose)
    test_text_regex("LIBERAL_NUMBER", LIBERAL_NUMBER, [
        ("1", ["1"]),
        ("12345", ["12345"]),
        ("-1", ["-1"]),
        ("1.2", ["1.2"]),
        ("-3.4", ["-3.4"]),
        ("+3.4", ["+3.4"]),
        ("-3.4e27.3", ["-3.4e27", "3"]),  # not valid scientific notation
        ("3.4e-27", ["3.4e-27"]),
        ("9,800", ["9,800"]),
        ("17,600.34", ["17,600.34"]),
        ("-17,300.6588", ["-17,300.6588"]),
    ], verbose=verbose)

    # -------------------------------------------------------------------------
    # Units
    # -------------------------------------------------------------------------

    test_text_regex("CELLS", CELLS, [
        ("cells", ["cells"]),
        ("blibble", []),
    ], verbose=verbose)
    test_text_regex("CUBIC_MM", CUBIC_MM, [
        ("mm3", ["mm3"]),
        ("blibble", []),
    ], verbose=verbose)
    test_text_regex("PER_CUBIC_MM", PER_CUBIC_MM, [
        ("per cubic mm", ["per cubic mm"]),
    ], verbose=verbose)
    test_text_regex("CELLS_PER_CUBIC_MM", CELLS_PER_CUBIC_MM, [
        ("cells/mm3", ["cells/mm3"]),
        ("blibble", []),
    ], verbose=verbose)

    # -------------------------------------------------------------------------
    # Things to ignore
    # -------------------------------------------------------------------------

    test_text_regex(
        "OPTIONAL_RESULTS_IGNORABLES",
        OPTIONAL_RESULTS_IGNORABLES, [
            ("(H)", ['(H)', '']),
            (" (H) ", [' (H) ', '']),
            (" (H) mg/L", [' (H) ', '', '', '', 'L', '']),
            ("(HH)", ['(HH)', '']),
            ("(L)", ['(L)', '']),
            ("(LL)", ['(LL)', '']),
            ("(*)", ['(*)', '']),
            ("  |  (H)  |  ", ['  |  (H)  |  ', '']),
        ],
        verbose=verbose
    )

    # -------------------------------------------------------------------------
    # Tense indicators
    # -------------------------------------------------------------------------

    test_text_regex("TENSE_INDICATOR", TENSE_INDICATOR, [
        ("a is b", ["is"]),
        ("a was b", ["was"]),
        ("a blah b", []),
    ], verbose=verbose)

    # -------------------------------------------------------------------------
    # Mathematical relations
    # -------------------------------------------------------------------------

    test_text_regex("RELATION", RELATION, [
        ("a < b", ["<"]),
        ("a less than b", ["less than"]),
        ("a <= b", ["<="]),
        ("a = b", ["="]),
        ("a equals b", ["equals"]),
        ("a equal to b", ["equal to"]),
        ("a >= b", [">="]),
        ("a > b", [">"]),
        ("a more than b", ["more than"]),
        ("a greater than b", ["greater than"]),
        ("a blah b", []),
    ], verbose=verbose)


# =============================================================================
# Command-line entry point
# =============================================================================

def test_all(verbose: bool = False) -> None:
    """
    Test all regexes in this module.
    """
    test_base_regexes(verbose=verbose)
    # learning_alternative_regex_groups()


if __name__ == '__main__':
    test_all()
