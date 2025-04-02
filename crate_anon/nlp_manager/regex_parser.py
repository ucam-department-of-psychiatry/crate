"""
crate_anon/nlp_manager/regex_parser.py

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

**Shared elements for regex-based NLP work.**

"""

from abc import abstractmethod, ABC
import logging
from typing import Any, Dict, Generator, List, Optional, Tuple

from sqlalchemy import Column, Integer, Float, String, Text

from crate_anon.common.regex_helpers import (
    LEFT_BRACKET as LB,
    RIGHT_BRACKET as RB,
)
from crate_anon.nlp_manager.constants import (
    MAX_SQL_FIELD_LEN,
    ProcessorConfigKeys,
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
    SIGNED_FLOAT,
    IGNORESIGN_INTEGER,
)
from crate_anon.nlp_manager.regex_units import (
    OUT_OF_SEPARATOR,
    SCORE,
)

log = logging.getLogger(__name__)


# =============================================================================
# Generic entities
# =============================================================================

# -----------------------------------------------------------------------------
# Blood results
# -----------------------------------------------------------------------------

OPTIONAL_RESULTS_IGNORABLES = r"""
    (?:  # OPTIONAL_RESULTS_IGNORABLES
        \s | \| | \:          # whitespace, bar, colon
        | \bHH?\b | \(HH?\)   # H/HH at a word boundary; (H)/(HH)
        | \bLL?\b | \(LL?\)   # L/LL etc.
        | \* | \(\*\)         # *, (*)
        | — | --              # em dash, double hyphen-minus
        | –\s+ | -\s+ | ‐\s+  # en dash/hyphen-minus/Unicode hyphen; whitespace
    )*                        # ... any of those, repeated 0 or more times
"""
# - you often get | characters when people copy/paste tables
# - blood test abnormality markers can look like e.g.
#       17 (H), 17 (*), 17 HH
# Re parentheses:
# - you can also see things like "CRP (5)"
#   ... but we'll handle that
# - However, if there's a right parenthesis only, that's less good, e.g.
#   "Present: Nicola Adams (NA). 1.0. Minutes of the last meeting."
#   ... which we don't want to be interpreted as "sodium 1.0".
#   HOW BEST TO DO THIS?
# - https://stackoverflow.com/questions/546433/regular-expression-to-match-outer-brackets  # noqa: E501
#   https://stackoverflow.com/questions/7898310/using-regex-to-balance-match-parenthesis  # noqa: E501
# - ... simplest is perhaps: base ignorables, or those with brackets, as above
# - ... even better than a nested thing is just a list of alternatives

OPTIONAL_POC = r"""
    (?: ,? \s+ POC )?   # OPTIONAL_POC: point-of-care testing, "[,] POC"
"""
# ... e.g. "Glucose, POC"; "Potassium, POC".
# Seen in CUH for
#
#     sodium, POC
#     potassium, POC
#     creatinine, POC
#     urea, POC
#     glucose, POC
#     lactate, POC
#     bilirubin, POC
#     HCT, POC
#     alkaline phosphatase, POC
#     alanine transferase, POC
#
#     HGB, POC
#     WBC, POC
#     PLT, POC
#     MCV, POC
#     MCH, POC
#     neutrophil count, POC
#     lymphocyte count, POC

# -----------------------------------------------------------------------------
# Tense indicators
# -----------------------------------------------------------------------------

IS = "is"
WAS = "was"
TENSE_INDICATOR = rf"(?: \b {IS} \b | \b {WAS} \b )"

# Standardized result values; see MAX_TENSE_TEXT_LENGTH
PAST = "past"
PRESENT = "present"
EVER = "ever"  # e.g. for "never"

TENSE_LOOKUP = compile_regex_dict(
    {
        IS: PRESENT,
        WAS: PAST,
    }
)

# -----------------------------------------------------------------------------
# Mathematical relations
# -----------------------------------------------------------------------------
# ... don't use unnamed groups here; EQ is also used as a return value

LT = r"(?: < | less \s+ than | under )"
LE = "<="
EQ = r"(?: = | equals | equal \s+ to )"
GE = ">="
GT = r"(?: > | (?:more|greater) \s+ than | over )"
# OF = "\b of \b"  # as in: "a BMI of 30"... but too likely to be mistaken for a target?  # noqa: E501

RELATION = rf"(?: {LE} | {LT} | {EQ} | {GE} | {GT} )"
# ... ORDER MATTERS: greedier things first, i.e.
# - LE before LT
# - GE before GT

RELATION_LOOKUP = compile_regex_dict(
    {
        # To standardize the output, so (for example) "=" and "equals" can both
        # map to "=".
        LT: "<",
        LE: "<=",
        EQ: "=",
        GE: ">=",
        GT: ">",
    }
)

# -----------------------------------------------------------------------------
# Punctuation
# -----------------------------------------------------------------------------

APOSTROPHE = "['’]"  # ASCII apostrophe; right single quote (U+2019)


# =============================================================================
# Regex assembly functions
# =============================================================================


# =============================================================================
# Functions to handle processed data
# =============================================================================


def common_tense(
    tense_text: Optional[str], relation_text: Optional[str]
) -> Tuple[Optional[str], Optional[str]]:
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


# =============================================================================
# Constants for generic processors
# =============================================================================

FN_VARIABLE_NAME = "variable_name"
FN_CONTENT = "_content"
FN_START = "_start"
FN_END = "_end"
FN_VARIABLE_TEXT = "variable_text"
FN_RELATION_TEXT = "relation_text"
FN_RELATION = "relation"
FN_VALUE_TEXT = "value_text"
FN_UNITS = "units"
FN_TENSE_TEXT = "tense_text"
FN_TENSE = "tense"

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
HELP_UNITS = "Matched units, as text"
HELP_TARGET_UNIT = "Numerical value in preferred units, if known"
HELP_TENSE_TEXT = f"Tense text, if known (e.g. '{IS}', '{WAS}')"
HELP_TENSE = f"Calculated tense, if known (e.g. '{PAST}', '{PRESENT}')"

MAX_RELATION_TEXT_LENGTH = 50
MAX_RELATION_LENGTH = max(len(x) for x in RELATION_LOOKUP.values())
MAX_VALUE_TEXT_LENGTH = 50
MAX_UNITS_LENGTH = 50
MAX_TENSE_TEXT_LENGTH = 50
MAX_TENSE_LENGTH = max(len(x) for x in TENSE_LOOKUP.values())


# =============================================================================
# Generic processors
# =============================================================================

# -----------------------------------------------------------------------------
# NumericalResultParser
# -----------------------------------------------------------------------------


class NumericalResultParser(BaseNlpParser):
    """
    DO NOT USE DIRECTLY. Base class for generic numerical results, where
    a SINGLE variable is produced.
    """

    def __init__(
        self,
        nlpdef: NlpDefinition,
        cfg_processor_name: str,
        variable: str,
        target_unit: str,
        regex_str_for_debugging: str,
        commit: bool = False,
    ) -> None:
        r"""
        Init function for NumericalResultParser.

        Args:
            nlpdef:
                A :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`.

            cfg_processor_name:
                Config section name in the :ref:`NLP config file <nlp_config>`.

            variable:
                Used by subclasses as the record value for ``variable_name``.

            target_unit:
                Fieldname used for the primary output quantity.

            regex_str_for_debugging:
                String form of regex, for debugging.

            commit:
                Force a COMMIT whenever we insert data? You should specify this
                in multiprocess mode, or you may get database deadlocks.

        Subclasses will extend this method.
        """
        # NB This docstring was associated with Sphinx errors!
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            commit=commit,
            friendly_name=variable,
        )
        self.variable = variable
        self.target_unit = target_unit
        self.regex_str_for_debugging = regex_str_for_debugging

        if nlpdef is None:  # only None for debugging!
            self.tablename = self.classname().lower()
            self.assume_preferred_unit = True
        else:
            self.tablename = self._cfgsection.opt_str(
                ProcessorConfigKeys.DESTTABLE, required=True
            )
            self.assume_preferred_unit = self._cfgsection.opt_bool(
                ProcessorConfigKeys.ASSUME_PREFERRED_UNIT, default=True
            )

        # Sanity checks
        assert (
            len(self.variable) <= MAX_SQL_FIELD_LEN
        ), f"Variable name too long (max {MAX_SQL_FIELD_LEN} characters)"

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
        return {
            self.tablename: [
                Column(
                    FN_VARIABLE_NAME,
                    SqlTypeDbIdentifier,
                    comment=HELP_VARIABLE_NAME,
                ),
                Column(FN_CONTENT, Text, comment=HELP_CONTENT),
                Column(FN_START, Integer, comment=HELP_START),
                Column(FN_END, Integer, comment=HELP_END),
                Column(FN_VARIABLE_TEXT, Text, comment=HELP_VARIABLE_TEXT),
                Column(
                    FN_RELATION_TEXT,
                    String(MAX_RELATION_TEXT_LENGTH),
                    comment=HELP_RELATION_TEXT,
                ),
                Column(
                    FN_RELATION,
                    String(MAX_RELATION_LENGTH),
                    comment=HELP_RELATION,
                ),
                Column(FN_VALUE_TEXT, Text, comment=HELP_VALUE_TEXT),
                Column(FN_UNITS, String(MAX_UNITS_LENGTH), comment=HELP_UNITS),
                Column(self.target_unit, Float, comment=HELP_TARGET_UNIT),
                Column(
                    FN_TENSE_TEXT,
                    String(MAX_TENSE_TEXT_LENGTH),
                    comment=HELP_TENSE_TEXT,
                ),
                Column(FN_TENSE, String(MAX_TENSE_LENGTH), comment=HELP_TENSE),
            ]
        }

    @abstractmethod
    def parse(
        self, text: str
    ) -> Generator[Tuple[str, Dict[str, Any]], None, None]:
        # docstring in superclass
        raise NotImplementedError

    def test_numerical_parser(
        self,
        test_expected_list: List[Tuple[str, List[float]]],
        add_test_no_plain_number: bool = True,
        verbose: bool = False,
    ) -> None:
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

        Compare also :func:`test_numerical_parser_detailed`.
        """
        log.info(f"Testing parser: {self.classname()}")
        if verbose:
            log.debug(f"... regex string:\n{self.regex_str_for_debugging}")
        if add_test_no_plain_number:
            test_expected_list = test_expected_list + [
                ("999", [])  # no quantity specified
            ]  # use "+ [...]", not append(), so as not to modify for caller
        for test_string, expected_values in test_expected_list:
            full_result = list(self.parse(test_string))
            actual_values = list(x[self.target_unit] for t, x in full_result)
            assert actual_values == expected_values, (
                f"Parser {self.classname()}: Expected {expected_values!r}, "
                f"got {actual_values!r}, when parsing {test_string!r}; "
                f"full result:\n{full_result!r}"
            )
        log.info("... OK")

    def detailed_test(
        self, text: str, expected: List[Dict[str, Any]], verbose: bool = False
    ) -> None:
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
                be verbose
        """
        full_result = list(self.parse(text))
        if len(full_result) != len(expected):
            raise ValueError(
                f"Parser {self.classname()}: expected {len(expected)} results "
                f"but got {len(full_result)} when parsing {text!r}; "
                f"full result:\n{full_result!r}"
            )
        if verbose:
            log.info(f"detailed_test: {text!r} -> {full_result!r}")
        for i, text_result in enumerate(full_result):
            _, result = text_result
            expected_dict = expected[i]
            for k, expected_value in expected_dict.items():
                if k not in result:
                    raise ValueError(
                        f"Parser {self.classname()}: Expected value dict "
                        f"had key {k!r} but this is absent from result "
                        f"{result!r}"
                    )
                observed_value = result[k]
                if observed_value != expected_value:
                    raise ValueError(
                        f"Parser {self.classname()}: expected {k} = "
                        f"{expected_value!r}, got {observed_value!r}, "
                        f"when parsing {text!r}; full result:\n"
                        f"{full_result!r}"
                    )

    def detailed_test_multiple(
        self,
        tests: List[Tuple[str, List[Dict[str, Any]]]],
        verbose: bool = False,
    ) -> None:
        """
        Args:
            tests:
                list of tuples ``test_string, expected``. The parser will parse
                ``test_string`` and compare the result(s) to ``expected``. This
                is list of dictionaries with keys that can be like ``values``,
                ``tense``, etc. Each dictionary value is the corresponding
                expected value.
            verbose:
                show the regex string too

        Raises:
            :exc:`AssertionError` if a comparison fails
        """
        log.info(f"Detailed tests for parser: {self.classname()}")
        if verbose:
            log.debug(f"... regex string:\n{self.regex_str_for_debugging}")
        for test_string, expected_dict_list in tests:
            self.detailed_test(
                test_string, expected_dict_list, verbose=verbose
            )
        log.info("... OK")


# -----------------------------------------------------------------------------
# SimpleNumericalResultParser
# -----------------------------------------------------------------------------

GROUP_NUMBER_WHOLE_EXPRESSION = 0

GROUP_NAME_QUANTITY = "quantity"
GROUP_NAME_RELATION = "relation"
GROUP_NAME_TENSE = "tense"
GROUP_NAME_UNITS = "units"
GROUP_NAME_VALUE = "value"


def make_simple_numeric_regex(
    quantity: str,
    units: str,
    value: str = SIGNED_FLOAT,
    tense_indicator: str = TENSE_INDICATOR,
    relation: str = RELATION,
    optional_results_ignorables: str = OPTIONAL_RESULTS_IGNORABLES,
    optional_ignorable_after_quantity: str = "",
    units_optional: bool = True,
) -> str:
    r"""
    Makes a regex with named groups to handle simple numerical results.

    Copes with formats like:

    .. code-block:: none

        sodium 132 mM
        sodium (mM) 132
        sodium (132 mM)

    ... and lots more.

    Args:
        quantity:
            Regex for the quantity (e.g. for "sodium" or "Na").
        units:
            Regex for units.
        value:
            Regex for the numerical value (e.g. our ``SIGNED_FLOAT`` regex).
        tense_indicator:
            Regex for tense indicator.
        relation:
            Regex for mathematical relationship (e.g. equals, less than).
        optional_results_ignorables:
            Regex for junk to ignore in between the other things.
            Should include its own "optionality" (e.g. ``*``).
        optional_ignorable_after_quantity:
            Regex for additional things that can be ignored right after the
            quantity. Should include its own "optionality" (e.g. ``?``).
        units_optional:
            The units are allowed to be omitted. Usually true.

    The resulting regex groups are named, not numbered:

    .. code-block:: none

        0:          Whole thing; integer, as in: m.group(0)
        'quantity': Quantity
        'tense':    Tense (optional)
        'relation': Relation (optional)
        'value':    Value
        'units':    Units (optional)

    ... as used by :class:`SimpleNumericalResultParser`.

    Just to check re overlap:

    .. code-block:: python

        import regex
        s1 = r"(?P<quantity>Sodium)\s+(?P<value>\d+)\s+(?P<units>mM)"
        s2 = r"(?P<quantity>Sodium)\s+\((?P<units>mM)\)\s+(?P<value>\d+)"
        s = f"{s1}|{s2}"
        r = regex.compile(s)
        t1 = "Sodium 132 mM"
        t2 = "Sodium (mM) 127"
        m1 = r.match(t1)
        m2 = r.match(t2)

        print(m1.group(0))  # Sodium 132 mM
        print(m1.group("quantity"))  # Sodium
        print(m1.group("value"))  # 132
        print(m1.group("units"))  # mM

        print(m2.group(0))  # Sodium (mM) 127
        print(m2.group("quantity"))  # Sodium
        print(m2.group("value"))  # 127
        print(m2.group("units"))  # mM

    ... so it's fine in that multiple groups can have the same name.

    """

    def group(groupname: str, contents: str, optional: bool = False) -> str:
        opt_str = "?" if optional else ""
        return f"(?P<{groupname}> {contents} ){opt_str}"

    def bracketed(s: str) -> str:
        return rf"{LB} \s* {s} \s* {RB}"

    group_quantity = group(GROUP_NAME_QUANTITY, quantity)
    group_tense_optional = group(GROUP_NAME_TENSE, tense_indicator, True)
    group_relation_optional = group(GROUP_NAME_RELATION, relation, True)
    group_units = group(GROUP_NAME_UNITS, units)
    group_units_bracketed = bracketed(group_units)
    group_value = group(GROUP_NAME_VALUE, value)
    group_value_bracketed = bracketed(group_value)
    value_units_all_bracketed = bracketed(rf"{group_value} \s+ {group_units}")
    units_optional_descriptor = "optional" if units_optional else "required"
    qmark_if_units_optional = "?" if units_optional else ""

    return rf"""
        # - Either: quantity [tense] [relation] value [units]
        #   or:     quantity (units value)
        #   or:     quantity (units) [tense] [relation] value
        # Quantity:
        {group_quantity}
        # Ignorable:
        {optional_ignorable_after_quantity}
        {optional_results_ignorables}
        (?:
            (?:
                # (units) ... [tense] ... [relation] ... value
                # Units, in brackets:
                {group_units_bracketed}
                # Tense indicator (optional):
                {group_tense_optional}
                # Ignorable:
                {optional_results_ignorables}
                # Relation (optional):
                {group_relation_optional}
                # Ignorable:
                {optional_results_ignorables}
                # Value:
                {group_value}
            )
            |
            (?:
                # (value units)
                {value_units_all_bracketed}
            )
            |
            (?:
                # [tense] ... [relation] ... value|(value) ... [units]
                # Tense indicator (optional):
                {group_tense_optional}
                # Ignorable:
                {optional_results_ignorables}
                # Relation (optional):
                {group_relation_optional}
                # Ignorable:
                {optional_results_ignorables}
                # Value or (value):
                (?:
                    {group_value} |
                    {group_value_bracketed}
                )
                # Ignorable:
                {optional_results_ignorables}
                # Units ({units_optional_descriptor}):
                {group_units}{qmark_if_units_optional}
            )
        )
    """


class SimpleNumericalResultParser(NumericalResultParser, ABC):
    """
    Base class for simple single-format numerical results. Use this when not
    only do you have a single variable to produce, but you have a single regex
    (in a standard format) that can produce it.
    """

    def __init__(
        self,
        nlpdef: NlpDefinition,
        cfg_processor_name: str,
        regex_str: str,
        variable: str,
        target_unit: str,
        units_to_factor: Dict[str, float],
        take_absolute: bool = False,
        commit: bool = False,
        debug: bool = False,
    ) -> None:
        """
        Args:

            nlpdef:
                :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`

            cfg_processor_name:
                config section suffix in the :ref:`NLP config file
                <nlp_config>`

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
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            variable=variable,
            target_unit=target_unit,
            regex_str_for_debugging=regex_str,
            commit=commit,
        )
        if debug:
            log.debug(f"Regex for {self.classname()}: {regex_str}")
        self.compiled_regex = compile_regex(regex_str)
        self.units_to_factor = compile_regex_dict(units_to_factor)
        self.take_absolute = take_absolute

    def parse(
        self, text: str, debug: bool = False
    ) -> Generator[Tuple[str, Dict[str, Any]], None, None]:
        # docstring in superclass
        if not text:
            return
        for m in self.compiled_regex.finditer(text):
            startpos = m.start()
            endpos = m.end()
            # groups = repr(m.groups())  # all matching groups
            matching_text = m.group(GROUP_NUMBER_WHOLE_EXPRESSION)
            # matching_text = text[startpos:endpos]  # same thing

            variable_text = m.group(GROUP_NAME_QUANTITY)
            tense_text = m.group(GROUP_NAME_TENSE)
            relation_text = m.group(GROUP_NAME_RELATION)
            value_text = m.group(GROUP_NAME_VALUE)
            units = m.group(GROUP_NAME_UNITS)

            # If units are known (or we're choosing to assume preferred units
            # if none are specified), calculate an absolute value
            value_in_target_units = None
            if units:
                matched_unit, multiple_or_fn = get_regex_dict_match(
                    units, self.units_to_factor
                )
                if not matched_unit:
                    # None of our units match. But there is a unit, and the
                    # regex matched. So this is a BAD unit. Skip the value.
                    continue
                # Otherwise: we did match a unit.
                if callable(multiple_or_fn):
                    value_in_target_units = multiple_or_fn(value_text)
                else:
                    value_in_target_units = (
                        to_float(value_text) * multiple_or_fn
                    )
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
            if debug:
                log.debug(f"Match {m} for {text!r} -> {result}")
            yield self.tablename, result


# -----------------------------------------------------------------------------
# NumeratorOutOfDenominatorParser
# -----------------------------------------------------------------------------


class NumeratorOutOfDenominatorParser(BaseNlpParser, ABC):
    """
    Base class for X-out-of-Y numerical results, e.g. for MMSE/ACE.

    - Integer denominator, expected to be positive.
    - Otherwise similar to :class:`SimpleNumericalResultParser`.
    """

    def __init__(
        self,
        nlpdef: NlpDefinition,
        cfg_processor_name: str,
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
        debug: bool = False,
    ) -> None:
        """
        This class operates with compiled regexes having this group format:
          - quantity_regex_str: e.g. to find "MMSE"

        Args:
            nlpdef:
                a :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
            cfg_processor_name:
                the suffix (name) of a CRATE NLP config file processor section
                (from which we may choose to get extra config information)
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
        assert expected_denominator > 0
        self.expected_denominator = expected_denominator
        self.numerator_text_fieldname = numerator_text_fieldname
        self.numerator_fieldname = numerator_fieldname
        self.denominator_text_fieldname = denominator_text_fieldname
        self.denominator_fieldname = denominator_fieldname
        self.correct_numerator_fieldname = (
            correct_numerator_fieldname or f"out_of_{expected_denominator}"
        )
        self.take_absolute = take_absolute

        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            commit=commit,
            friendly_name=variable_name,
        )
        if nlpdef is None:  # only None for debugging!
            self.tablename = self.classname().lower()
        else:
            self.tablename = self._cfgsection.opt_str(
                ProcessorConfigKeys.DESTTABLE, required=True
            )

        regex_str = rf"""
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
                ( {IGNORESIGN_INTEGER} )         # 5. group for denominator
            )?
        """  # noqa: E501
        if debug:
            log.debug(f"Regex for {self.classname()}: {regex_str}")
        self.regex_str = regex_str
        self.compiled_regex = compile_regex(regex_str)

    def dest_tables_columns(self) -> Dict[str, List[Column]]:
        # docstring in superclass
        return {
            self.tablename: [
                Column(
                    FN_VARIABLE_NAME,
                    SqlTypeDbIdentifier,
                    comment=HELP_VARIABLE_NAME,
                ),
                Column(FN_CONTENT, Text, comment=HELP_CONTENT),
                Column(FN_START, Integer, comment=HELP_START),
                Column(FN_END, Integer, comment=HELP_END),
                Column(FN_VARIABLE_TEXT, Text, comment=HELP_VARIABLE_TEXT),
                Column(
                    FN_RELATION_TEXT,
                    String(MAX_RELATION_TEXT_LENGTH),
                    comment=HELP_RELATION_TEXT,
                ),
                Column(
                    FN_RELATION,
                    String(MAX_RELATION_LENGTH),
                    comment=HELP_RELATION,
                ),
                Column(
                    self.numerator_text_fieldname,
                    String(MAX_VALUE_TEXT_LENGTH),
                    comment="Numerator, as text",
                ),
                Column(self.numerator_fieldname, Float, comment="Numerator"),
                Column(
                    self.denominator_text_fieldname,
                    String(MAX_VALUE_TEXT_LENGTH),
                    comment="Denominator, as text",
                ),
                Column(
                    self.denominator_fieldname, Float, comment="Denominator"
                ),
                Column(
                    self.correct_numerator_fieldname,
                    Float,
                    comment="Numerator, if denominator is as expected (units "
                    "are correct)",
                ),
                Column(
                    FN_TENSE_TEXT,
                    String(MAX_TENSE_TEXT_LENGTH),
                    comment=HELP_TENSE_TEXT,
                ),
                Column(FN_TENSE, String(MAX_TENSE_LENGTH), comment=HELP_TENSE),
            ]
        }

    def parse(
        self, text: str, debug: bool = False
    ) -> Generator[Tuple[str, Dict[str, Any]], None, None]:
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
            if debug:
                log.debug(f"Match {m} for {text!r} -> {result}")
            yield self.tablename, result

    def test_numerator_denominator_parser(
        self,
        test_expected_list: List[Tuple[str, List[Tuple[float, float]]]],
        verbose: bool = False,
    ) -> None:
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
        log.info(f"Testing parser: {self.classname()}")
        if verbose:
            log.debug(f"... regex:\n{self.regex_str}")
        for test_string, expected_values in test_expected_list:
            actual_values = list(
                (x[self.numerator_fieldname], x[self.denominator_fieldname])
                for t, x in self.parse(test_string)
            )
            assert actual_values == expected_values, (
                "Parser {name}: Expected {expected}, got {actual}, when "
                "parsing {test_string}; full result:\n{full}".format(
                    name=self.classname(),
                    expected=expected_values,
                    actual=actual_values,
                    test_string=repr(test_string),
                    full=repr(list(self.parse(test_string))),
                )
            )
        log.info("... OK")


# =============================================================================
# Validator base class (for testing regex NLP classes)
# =============================================================================


class ValidatorBase(BaseNlpParser):
    r"""
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
      - sensitivity = P(Y | Pr) = recall (\*) = true positive rate
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
                  (Maybe: "his CRP was twenty-one".)

            - Ab1. Absent: reference to CRP, but no numerical information,
              e.g. "her CRP was normal".

                - FA1. False alarm: software reports a numerical value.
                  (Maybe: "my CRP was 7 hours behind my boss's deadline")
                - CR1. Correct rejection: software doesn't report a value.

        - Ab2. field contains no reference to CRP at all.

                - FA2. False alarm: software reports a numerical value.
                  (A bit harder to think of examples... but imagine a bug
                  that gives a hit for "number of carp: 7". Or an alternative
                  abbreviation meaning, e.g. "took part in a cardiac
                  rehabilitation programme (CRP) 4 hours/week".)

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

    def __init__(
        self,
        nlpdef: Optional[NlpDefinition],
        cfg_processor_name: Optional[str],
        commit: bool = False,
    ) -> None:
        """
        Args:
            nlpdef:
                :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`

            cfg_processor_name:
                config section suffix in the :ref:`NLP config file
                <nlp_config>`

            commit:
                force a COMMIT whenever we insert data? You should specify this
                in multiprocess mode, or you may get database deadlocks.
        """
        (
            validated_variable,
            regex_str_list,
        ) = self.get_variablename_regexstrlist()
        vname = f"{validated_variable}_validator"
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            commit=commit,
            friendly_name=vname,
        )
        self.regex_str_list = regex_str_list  # for debugging only
        self.compiled_regex_list = [compile_regex(r) for r in regex_str_list]
        self.variable = vname
        self.NAME = self.variable

        if nlpdef is None:  # only None for debugging!
            self.tablename = self.classname().lower()
        else:
            self.tablename = self._cfgsection.opt_str(
                ProcessorConfigKeys.DESTTABLE, required=True
            )

    @classmethod
    @abstractmethod
    def get_variablename_regexstrlist(cls) -> Tuple[str, List[str]]:
        """
        To be overridden.

        Returns:
            tuple: ``(validated_variable_name, regex_str_list)``, where:

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

        """
        raise NotImplementedError

    def set_tablename(self, tablename: str) -> None:
        """
        In case a friend class wants to override.
        """
        self.tablename = tablename

    def dest_tables_columns(self) -> Dict[str, List[Column]]:
        # docstring in superclass
        return {
            self.tablename: [
                Column(
                    FN_VARIABLE_NAME,
                    SqlTypeDbIdentifier,
                    comment=HELP_VARIABLE_NAME,
                ),
                Column(FN_CONTENT, Text, comment=HELP_CONTENT),
                Column(FN_START, Integer, comment=HELP_START),
                Column(FN_END, Integer, comment=HELP_END),
            ]
        }

    def parse(
        self, text: str
    ) -> Generator[Tuple[str, Dict[str, Any]], None, None]:
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

    def test_validator(
        self, test_expected_list: List[Tuple[str, bool]], verbose: bool = False
    ) -> None:
        """
        The 'bool' part of test_expected_list is: should it match any?
        ... noting that "match anywhere" is the "search" function, whereas
        "match" matches at the beginning:

            https://docs.python.org/3/library/re.html#re.regex.match
        """
        log.info(f"Testing validator: {self.classname()}")
        if verbose:
            n = len(self.regex_str_list)
            for i, r in enumerate(self.regex_str_list, start=1):
                log.debug(f"... regex #{i}/{n}: {r}\n")
        for test_string, expected_match in test_expected_list:
            results = list(
                r.search(test_string) for r in self.compiled_regex_list
            )
            actual_match = any(results)
            assert actual_match == expected_match, (
                f"Validator {self.classname()}: Expected 'at least one regex "
                f"should match somewhere (search)' to be {expected_match}, "
                f"got {actual_match}, when parsing {test_string!r}; "
                f"full results = {results}"
            )
        log.info("... OK")

    def test(self, verbose: bool = False) -> None:
        log.info(f"... no tests implemented for validator {self.classname()}")


# =============================================================================
# More general testing
# =============================================================================


def learning_alternative_regex_groups() -> None:
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
        log.info(f"Match: {m}; groups: {m.groups()}")
    """
    So:
        - groups can overlap
        - groups are ordered by their opening bracket
        - matches are filled in neatly
    """
