#!/usr/bin/env python
# crate_anon/nlp_manager/regex_parser.py

# Shared elements for regex-based NLP work.

import regex
from regex import _regex_core
import typing
from typing import Any, Dict, Iterator, List, Optional, Tuple

from sqlalchemy import Column, Integer, Float, String, Text

from crate_anon.nlp_manager.constants import (
    MAX_SQL_FIELD_LEN,
    SqlTypeDbIdentifier,
)
from crate_anon.nlp_manager.base_nlp_parser import BaseNlpParser
from crate_anon.nlp_manager.nlp_definition import NlpDefinition
from crate_anon.nlp_manager.regex_numbers import (
    LIBERAL_NUMBER,
    SIGNED_FLOAT,
    SIGNED_INTEGER,
    UNSIGNED_FLOAT,
    UNSIGNED_INTEGER,
)
from crate_anon.nlp_manager.regex_units import (
    CELLS,
    CELLS_PER_CUBIC_MM,
    CUBIC_MM,
    PER_CUBIC_MM,
)


# =============================================================================
#  Generic entities
# =============================================================================
# - All will use VERBOSE mode for legibility. (No impact on speed: compiled.)
# - Don't forget to use raw strings for all regex definitions!
# - Beware comments inside regexes. The comment parser isn't quite as benign
#   as you might think. Use very plain text only.
# - (?: XXX ) makes XXX into an unnamed group.


# -----------------------------------------------------------------------------
# Regex basics
# -----------------------------------------------------------------------------

REGEX_COMPILE_FLAGS = regex.IGNORECASE | regex.MULTILINE | regex.VERBOSE
WORD_BOUNDARY = r"\b"
OPTIONAL_WHITESPACE = r"\s?"


def at_wb_start_end(regex_str: str) -> str:
    """
    Caution using this. Digits do not end a word, so "mm3" will not match if
    your "mm" group ends in a word boundary.
    """
    return "\b(?: {} )\b".format(regex_str)


def at_start_wb(regex_str: str) -> str:
    """
    With word boundary at start. Beware, though; e.g. "3kg" is reasonable, and
    this does NOT have a word boundary in.
    """
    return "(?: \b (?: {} ) )".format(regex_str)


def compile_regex(regex_str: str) -> typing.re.Pattern:
    try:
        return regex.compile(regex_str, REGEX_COMPILE_FLAGS)
    except _regex_core.error:
        print("FAILING REGEX:\n{}".format(regex_str))
        raise


# -----------------------------------------------------------------------------
# Blood results
# -----------------------------------------------------------------------------

OPTIONAL_RESULTS_IGNORABLES = r"""
    (?:  # OPTIONAL_RESULTS_IGNORABLES
        \s          # whitespace
        | \|        # bar
        | \bHH?\b   # H or HH at a word boundary
        | \(HH?\)   # (H) or (HH)
        | \bLL?\b   # L or LL at a word boundary
        | \(LL?\)   # (L) or (LL)
        | \*        # *
        | \(\*\)    # (*)
        | \(        # isolated left parenthesis
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
TENSE_INDICATOR = r"""
    (?:  # TENSE_INDICATOR
        \b {IS} \b
        | \b {WAS} \b
    )
""".format(IS=IS, WAS=WAS)


# -----------------------------------------------------------------------------
# Mathematical relations
# -----------------------------------------------------------------------------
# ... don't use unnamed groups here; EQ is also used as a return value

LT = "<"
LE = "<="
EQ = "="
GE = ">="
GT = ">"
# OF = "\b of \b"  # as in: "a BMI of 30"... but too likely to be mistaken for a target?  # noqa

RELATION = r"""
    (?:  # RELATION
        {LT} | {LE} | {EQ} | {GE} | {GT}
    )
""".format(LT=LT, LE=LE, EQ=EQ, GE=GE, GT=GT)


# =============================================================================
# Regexes based on some of the fragments above
# =============================================================================

RE_IS = compile_regex(IS)
RE_WAS = compile_regex(WAS)


# =============================================================================
# Standardized result values
# =============================================================================

PAST = "past"
PRESENT = "present"


# =============================================================================
#  Generic processors
# =============================================================================

def to_float(s: str) -> Optional[float]:
    try:
        if ',' in s:  # comma as thousands separator
            s = s.replace(',', '')
        return float(s)
    except (TypeError, ValueError):
        return None


def to_pos_float(s: str) -> Optional[float]:
    try:
        return abs(to_float(s))
    except TypeError:  # to_float() returned None
        return None


def common_tense(tense_indicator: str, relation: str) -> Tuple[str, str]:
    """
    Sort out tense, if known, and impute that "CRP was 72" means that
    relation was EQ in the PAST, etc.

    Returns (tense, relation).
    """
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

    return tense, relation


class NumericalResultParser(BaseNlpParser):
    """DO NOT USE DIRECTLY. Base class for generic numerical results, where
    a SINGLE variable is produced."""
    FN_VARIABLE_NAME = 'variable_name'
    FN_CONTENT = '_content'
    FN_START = '_start'
    FN_END = '_end'
    FN_VARIABLE_TEXT = 'variable_text'
    FN_RELATION = 'relation'
    FN_VALUE_TEXT = 'value_text'
    FN_UNITS = 'units'
    FN_TENSE = 'tense'

    MAX_RELATION_LENGTH = 3
    MAX_VALUE_TEXT_LENGTH = 255
    MAX_UNITS_LENGTH = 255
    MAX_TENSE_LENGTH = len(PRESENT)

    def __init__(self,
                 nlpdef: NlpDefinition,
                 cfgsection: str,
                 variable: str,
                 target_unit: str,
                 commit: bool = False) -> None:
        super().__init__(nlpdef=nlpdef, cfgsection=cfgsection, commit=commit)
        self.variable = variable
        self.target_unit = target_unit

        if nlpdef is None:  # only None for debugging!
            self.tablename = ''
            self.assume_preferred_unit = True
        else:
            self.tablename = nlpdef.opt_str(
                cfgsection, 'desttable', required=True)
            self.assume_preferred_unit = nlpdef.opt_bool(
                cfgsection, 'assume_preferred_unit', default=True)

        # Sanity checks
        assert len(self.variable) <= MAX_SQL_FIELD_LEN, (
            "Variable name too long (max {} characters)".format(
                MAX_SQL_FIELD_LEN))

    def set_tablename(self, tablename: str) -> None:
        """In case a friend class wants to override."""
        self.tablename = tablename

    def dest_tables_columns(self) -> Dict[str, List[Column]]:
        return {self.tablename: [
            Column(self.FN_VARIABLE_NAME, SqlTypeDbIdentifier,
                   doc="Variable name"),
            Column(self.FN_CONTENT, Text,
                   doc="Matching text contents"),
            Column(self.FN_START, Integer,
                   doc="Start position (of matching string within whole "
                       "text)"),
            Column(self.FN_END, Integer,
                   doc="End position (of matching string within whole text)"),
            Column(self.FN_VARIABLE_TEXT, Text,
                   doc="Text that matched the variable name"),
            Column(self.FN_RELATION, String(self.MAX_RELATION_LENGTH),
                   doc="Text that matched the mathematical relationship "
                       "between variable and value (e.g. '=', '<='"),
            Column(self.FN_VALUE_TEXT, String(self.MAX_VALUE_TEXT_LENGTH),
                   doc="Matched numerical value, as text"),
            Column(self.FN_UNITS, String(self.MAX_UNITS_LENGTH),
                   doc="Matched units, as text"),
            Column(self.target_unit, Float,
                   doc="Numerical value in preferred units, if known"),
            Column(self.FN_TENSE, String(self.MAX_TENSE_LENGTH),
                   doc="Tense indicator, if known (e.g. '{}', '{}')".format(
                       PAST, PRESENT)),
        ]}

    def parse(self, text: str) -> Iterator[Tuple[str, Dict[str, Any]]]:
        """Default parser."""
        raise NotImplementedError

    def test_numerical_parser(
            self,
            test_expected_list: List[Tuple[str, List[float]]]) -> None:
        """
        :param test_expected_list: list of tuples of (a) test string and
         (b) list of expected numerical (float) results, which can be an
         empty list
        :return: none; will assert on failure
        """
        print("Testing parser: {}".format(type(self).__name__))
        for test_string, expected_values in test_expected_list:
            actual_values = list(
                x[self.target_unit] for t, x in self.parse(test_string)
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


class SimpleNumericalResultParser(NumericalResultParser):
    """Base class for simple single-format numerical results. Use this when
    not only do you have a single variable to produce, but you have a single
    regex (in a standard format) that can produce it."""
    def __init__(self,
                 nlpdef: NlpDefinition,
                 cfgsection: str,
                 regex_str: str,
                 variable: str,
                 target_unit: str,
                 units_to_factor: Dict[typing.re.Pattern, float],
                 commit: bool = False,
                 debug: bool = False) -> None:
        """
        This class operates with compiled regexes having this group format:
          - variable
          - tense_indicator
          - relation
          - value
          - units

        units_to_factor: dictionary, mapping
            FROM (compiled regex for units)
            TO EITHER
                - float [multiple] to multiple those units by, to get preferred
                   unit
            OR  - function taking text parameter and returning float value
                  in preferred unit

            - any units present in the regex but absent from units_to_factor
              will lead the result to be ignored -- for example, allowing you
              to ignore a relative neutrophil count ("neutrophils 2.2%") while
              detecting absolute neutrophil counts ("neutrophils 2.2"), or
              ignoring "docusate sodium 100mg" but detecting "sodium 140 mM".
        """
        super().__init__(nlpdef=nlpdef,
                         cfgsection=cfgsection,
                         variable=variable,
                         target_unit=target_unit,
                         commit=commit)
        if debug:
            print("Regex for {}: {}".format(type(self).__name__, regex_str))
        self.compiled_regex = compile_regex(regex_str)
        self.units_to_factor = {
            compile_regex(k): v
            for k, v in units_to_factor.items()
        }

    def parse(self, text: str,
              debug: bool = False) -> Iterator[Tuple[str, Dict[str, Any]]]:
        """Default parser."""
        for m in self.compiled_regex.finditer(text):
            if debug:
                print("Match {} for {}".format(m, repr(text)))
            startpos = m.start()
            endpos = m.end()
            # groups = repr(m.groups())  # all matching groups
            matching_text = m.group(0)  # the whole thing
            # matching_text = text[startpos:endpos]  # same thing

            variable_text = m.group(1)
            tense_indicator = m.group(2)
            relation = m.group(3)
            value_text = m.group(4)
            units = m.group(5)

            # If units are known (or we're choosing to assume preferred units
            # if none are specified), calculate an absolute value
            value_in_target_units = None
            if units:
                matched_unit = False
                for unit_regex, multiple_or_fn in self.units_to_factor.items():
                    if unit_regex.match(units):
                        if callable(multiple_or_fn):
                            value_in_target_units = multiple_or_fn(value_text)
                        else:
                            value_in_target_units = (to_float(value_text) *
                                                     multiple_or_fn)
                        matched_unit = True
                        break
                if not matched_unit:
                    # None of our units match. But there is a unit, and the
                    # regex matched. So this is a BAD unit. Skip the value.e
                    continue
            elif self.assume_preferred_unit:  # unit is None or empty
                value_in_target_units = to_float(value_text)

            tense, relation = common_tense(tense_indicator, relation)

            yield self.tablename, {
                self.FN_VARIABLE_NAME: self.variable,
                self.FN_CONTENT: matching_text,
                self.FN_START: startpos,
                self.FN_END: endpos,
                # 'groups': groups,
                self.FN_VARIABLE_TEXT: variable_text,
                self.FN_RELATION: relation,
                self.FN_VALUE_TEXT: value_text,
                self.FN_UNITS: units,
                self.target_unit: value_in_target_units,
                self.FN_TENSE: tense,
            }


# =============================================================================
#  More general testing
# =============================================================================

class ValidatorBase(BaseNlpParser):
    """DO NOT USE DIRECTLY. Base class for validating regex parser sensitivity.
    The validator will find fields that refer to the variable, whether or not
    they meet the other criteria of the actual NLP processors (i.e. whether or
    not they contain a valid value). More explanation below.

    Suppose we're validating C-reactive protein (CRP). Key concepts:
        - source (true state of the world): Pr present, Ab absent
        - software decision: Y yes, N no
        - signal detection theory classification:
            hit = Pr & Y = true positive
            miss = Pr & N = false negative
            false alarm = Ab & Y = false positive
            correct rejection = Ab & N = true negative
        - common SDT metrics:
            positive predictive value, PPV = P(Pr | Y) = precision (*)
            negative predictive value, NPV = P(Ab | N)
            sensitivity = P(Y | Pr) = recall (*) = true positive rate
            specificity = P(N | Ab) = true negative rate
            (*) common names used in the NLP context.
        - other common classifier metric:
            F_beta score = (1 + beta^2) * precision * recall /
                           ((beta^2 * precision) + recall)
            ... which measures performance when you value recall beta times as
            much as precision; e.g. the F1 score when beta = 1. See
            https://en.wikipedia.org/wiki/F1_score

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
        SELECT textfield FROM sometable WHERE (
            textfield LIKE '%CRP%'
            OR textfield LIKE '%C-reactive protein%');
    or similar, but really we want the best "CRP detector" possible. That is
    probably to use a regex, either in SQL (... "WHERE textfield REGEX
    'myregex'") or using these validator classes. (The main NLP regexes don't
    distinguish between "CRP present, no valid value" and "CRP absent",
    because regexes either match or don't.)

    Each validator class implements the core variable-finding part of its
    corresponding NLP regex class, but without the value or units. For example,
    the CRP class looks for things like "CRP is 6" or "CRP 20 mg/L", whereas
    the CRP validator looks for things like "CRP".
    """
    FN_VARIABLE_NAME = 'variable_name'
    FN_CONTENT = '_content'
    FN_START = '_start'
    FN_END = '_end'

    def __init__(self,
                 nlpdef: NlpDefinition,
                 cfgsection: str,
                 regex_str_list: List[str],
                 validated_variable: str,
                 commit: bool = False) -> None:
        """
        This class operates with compiled regexes having this group format:
          - variable
        """
        super().__init__(nlpdef=nlpdef, cfgsection=cfgsection, commit=commit)
        self.compiled_regex_list = [compile_regex(r) for r in regex_str_list]
        self.variable = "{}_validator".format(validated_variable)
        self.NAME = self.variable

        if nlpdef is None:  # only None for debugging!
            self.tablename = ''
        else:
            self.tablename = nlpdef.opt_str(
                cfgsection, 'desttable', required=True)

    def set_tablename(self, tablename: str) -> None:
        """In case a friend class wants to override."""
        self.tablename = tablename

    def dest_tables_columns(self) -> Dict[str, List[Column]]:
        return {self.tablename: [
            Column(self.FN_VARIABLE_NAME, SqlTypeDbIdentifier,
                   doc="Variable name"),
            Column(self.FN_CONTENT, Text,
                   doc="Matching text contents"),
            Column(self.FN_START, Integer,
                   doc="Start position (of matching string within whole "
                       "text)"),
            Column(self.FN_END, Integer,
                   doc="End position (of matching string within whole text)"),
        ]}

    def parse(self, text: str) -> Iterator[Tuple[str, Dict[str, Any]]]:
        for compiled_regex in self.compiled_regex_list:
            for m in compiled_regex.finditer(text):
                startpos = m.start()
                endpos = m.end()
                # groups = repr(m.groups())  # all matching groups
                matching_text = m.group(0)  # the whole thing
                # matching_text = text[startpos:endpos]  # same thing

                yield self.tablename, {
                    self.FN_VARIABLE_NAME: self.variable,
                    self.FN_CONTENT: matching_text,
                    self.FN_START: startpos,
                    self.FN_END: endpos,
                }


# =============================================================================
#  More general testing
# =============================================================================

def f_score(precision: float, recall: float, beta: float = 1) -> float:
    # https://en.wikipedia.org/wiki/F1_score
    beta_sq = beta ** 2
    return (
        (1 + beta_sq) * precision * recall / ((beta_sq * precision) + recall)
    )


def learning_alternative_regex_groups():
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
    for test_str in ["a", "b", "a c", "d", "e", "a fish", "c c c"]:
        m = compiled_regex.match(test_str)
        print("Match: {}; groups: {}".format(m, m.groups()))
    """
    So:
        - groups can overlap
        - groups are ordered by their opening bracket
        - matches are filled in neatly
    """


def get_compiled_regex_results(compiled_regex: typing.re.Pattern,
                               text: str) -> List[str]:
    results = []
    for m in compiled_regex.finditer(text):
        results.append(m.group(0))
    return results


def print_compiled_regex_results(compiled_regex: typing.re.Pattern, text: str,
                                 prefix_spaces: int = 4) -> None:
    results = get_compiled_regex_results(compiled_regex, text)
    print("{}{} -> {}".format(' ' * prefix_spaces,
                              repr(text), repr(results)))


def test_text_regex(name: str,
                    regex_text: str,
                    test_expected_list: List[Tuple[str, List[str]]]) -> None:
    compiled_regex = compile_regex(regex_text)
    print("Testing regex named {}".format(name))
    for test_string, expected_values in test_expected_list:
        actual_values = get_compiled_regex_results(compiled_regex, test_string)
        assert actual_values == expected_values, (
            """Regex {}: Expected {}, got {}, when parsing {}""".format(
                name,
                expected_values,
                actual_values,
                repr(test_string)
            )
        )
    print("... OK")
    # print_compiled_regex_results(compiled_regex, text,
    #                              prefix_spaces=prefix_spaces)


def test_base_regexes() -> None:
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
    ])
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
    ])
    test_text_regex("UNSIGNED_FLOAT", UNSIGNED_FLOAT, [
        ("1", ["1"]),
        ("12345", ["12345"]),
        ("-1", ["1"]),
        ("1.2", ["1.2"]),
        ("-3.4", ["3.4"]),
        ("+3.4", ["3.4"]),
        ("-3.4e27.3", ["3.4", "27.3"]),
        ("3.4e-27", ["3.4", "27"]),
        ("9,800", ["9,800"]),
        ("17,600.34", ["17,600.34"]),
        ("-17,300.6588", ["17,300.6588"]),
    ])
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
    ])
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
    ])
    test_text_regex("CELLS", CELLS, [
        ("cells", ["cells"]),
        ("blibble", []),
    ])
    test_text_regex("CUBIC_MM", CUBIC_MM, [
        ("mm3", ["mm3"]),
        ("blibble", []),
    ])
    test_text_regex("PER_CUBIC_MM", PER_CUBIC_MM, [
        ("per cubic mm", ["per cubic mm"]),
    ])
    test_text_regex("CELLS_PER_CUBIC_MM", CELLS_PER_CUBIC_MM, [
        ("cells/mm3", ["cells/mm3"]),
        ("blibble", []),
    ])
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
        ]
    )


# =============================================================================
#  Command-line entry point
# =============================================================================

if __name__ == '__main__':
    test_base_regexes()
    learning_alternative_regex_groups()
