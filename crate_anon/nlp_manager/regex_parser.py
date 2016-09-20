#!/usr/bin/env python
# crate_anon/nlp_manager/regex_parser.py

# Shared elements for regex-based NLP work.

import regex
import typing
from typing import Any, Dict, Iterator, List, Tuple

from sqlalchemy import Column, Integer, Float, String, Text

from crate_anon.nlp_manager.constants import (
    MAX_SQL_FIELD_LEN,
    SqlTypeDbIdentifier,
)
from crate_anon.nlp_manager.base_parser import NlpParser
from crate_anon.nlp_manager.nlp_definition import NlpDefinition


# =============================================================================
#  Generic entities
# =============================================================================
# - All will use VERBOSE mode for legibility. (No impact on speed: compiled.)
# - Don't forget to use raw strings for all regex definitions!
# - Beware comments inside regexes. The comment parser isn't quite as benign
#   as you might think.
# - (?: XXX ) makes XXX into an unnamed group.


# -----------------------------------------------------------------------------
# Regex basics
# -----------------------------------------------------------------------------

REGEX_COMPILE_FLAGS = regex.IGNORECASE | regex.MULTILINE | regex.VERBOSE
WORD_BOUNDARY = r"\b"
OPTIONAL_WHITESPACE = r"\s?"


# -----------------------------------------------------------------------------
# Blood results
# -----------------------------------------------------------------------------

OPTIONAL_RESULTS_IGNORABLES = r"""
    (?:
        \s          # whitespace
        | \|        # bar
        | \(        # bracket
        | \)        # bracket
        | \bHH?\b   # H or HH at a word boundary
        | \bLL?\b   # L or LL at a word boundary
        | \*        # asterisk
    )*
"""
# - you often get | characters when people copy/paste tables
# - blood test abnormality markers can look like e.g.
#       17 (H), 17 (*), 17 HH

# -----------------------------------------------------------------------------
# Tense indicators
# -----------------------------------------------------------------------------

IS = "is"
WAS = "was"
TENSE_INDICATOR = r"""
    (?:
        {IS} | {WAS}
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

RELATION = r"""
    (?:
        {LT} | {LE} | {EQ} | {GE} | {GT}
    )
""".format(LT=LT, LE=LE, EQ=EQ, GE=GE, GT=GT,
           IS=IS, WAS=WAS)


# -----------------------------------------------------------------------------
# Mathematical operations and quantities
# -----------------------------------------------------------------------------

def times_ten_to_power(n):
    return r"(?:{MULTIPLY}?\s*10\s*{POWER}\s*{n})".format(
        MULTIPLY=MULTIPLY, POWER=POWER, n=n)

MULTIPLY = r"[x*×⋅]"
POWER = r"(?: e | \^ | \*\* )"  # e, ^, **
BILLION = times_ten_to_power(9)


# -----------------------------------------------------------------------------
# Number components
# -----------------------------------------------------------------------------

OPTIONAL_SIGN = r"[+-]?"
OPTIONAL_POSITIVE_NO_NEGATIVE_SIGN = r"""
    (?:  # optional + but no -
        (?!-)  # negative lookahead assertion
        +?
    )
"""
# OPTIONAL_POSITIVE_NO_NEGATIVE_SIGN = OPTIONAL_SIGN
PLAIN_INTEGER = r"(?:\d+)"
# Numbers with commas: http://stackoverflow.com/questions/5917082
# ... then modified a little, because that fails with Python's regex module;
# (a) the "\d+" grabs things like "12,000" and thinks "aha, 12", so we have to
#     fix that by putting the "thousands" bit first; then
# (b) that has to be modified to contain at least one comma/thousands grouping
#     (or it will treat "9800" as "980").
PLAIN_INTEGER_W_THOUSAND_COMMAS = r"""
    (?:  # plain integer allowing commas as a thousands separator
        (?:                 # a number with thousands separators
            \d{1,3} (?:,\d{3})+
        )
        |                   # or
        \d+                 # plain number
        # NOTE: PUT THE ONE THAT NEEDS TO BE GREEDIER FIRST, i.e. the
        # one with thousands separators
    )
"""
FLOATING_POINT_GROUP = r"""
    (?: \. \d+ )?           # optional decimal point and further digits
"""
SCIENTIFIC_NOTATION_EXPONENT = r"""
    (?:  # integer exponent
        E                   # E
        {OPTIONAL_SIGN}
        \d+                 # number
    )?
""".format(
    OPTIONAL_SIGN=OPTIONAL_SIGN,
)
# Scientific notation does NOT offer non-integer exponents.
# Specifically, float("-3.4e-27") is fine, but float("-3.4e-27.1") isn't.


# -----------------------------------------------------------------------------
# Number types
# -----------------------------------------------------------------------------
# Beware of unsigned types. You may not want a sign, but if you use an
# unsigned type, "-3" will be read as "3".

UNSIGNED_INTEGER = PLAIN_INTEGER_W_THOUSAND_COMMAS
SIGNED_INTEGER = r"""
    (?:  # signed integer
        {OPTIONAL_SIGN}
        {PLAIN_INTEGER_W_THOUSAND_COMMAS}
    )
""".format(
    OPTIONAL_SIGN=OPTIONAL_SIGN,
    PLAIN_INTEGER_W_THOUSAND_COMMAS=PLAIN_INTEGER_W_THOUSAND_COMMAS,
)
UNSIGNED_FLOAT = r"""
    (?:  # unsigned float
        {PLAIN_INTEGER_W_THOUSAND_COMMAS}
        {FLOATING_POINT_GROUP}
    )
""".format(
    OPTIONAL_POSITIVE_NO_NEGATIVE_SIGN=OPTIONAL_POSITIVE_NO_NEGATIVE_SIGN,
    PLAIN_INTEGER_W_THOUSAND_COMMAS=PLAIN_INTEGER_W_THOUSAND_COMMAS,
    FLOATING_POINT_GROUP=FLOATING_POINT_GROUP,
)
SIGNED_FLOAT = r"""
    (?:  # signed float
        {OPTIONAL_SIGN}
        {PLAIN_INTEGER_W_THOUSAND_COMMAS}
        {FLOATING_POINT_GROUP}
    )
""".format(
    OPTIONAL_SIGN=OPTIONAL_SIGN,
    PLAIN_INTEGER_W_THOUSAND_COMMAS=PLAIN_INTEGER_W_THOUSAND_COMMAS,
    FLOATING_POINT_GROUP=FLOATING_POINT_GROUP,
)
LIBERAL_NUMBER = r"""
    (?:  # liberal number
        {OPTIONAL_SIGN}
        {PLAIN_INTEGER_W_THOUSAND_COMMAS}
        {FLOATING_POINT_GROUP}
        {SCIENTIFIC_NOTATION_EXPONENT}
    )
""".format(
    OPTIONAL_SIGN=OPTIONAL_SIGN,
    PLAIN_INTEGER_W_THOUSAND_COMMAS=PLAIN_INTEGER_W_THOUSAND_COMMAS,
    FLOATING_POINT_GROUP=FLOATING_POINT_GROUP,
    SCIENTIFIC_NOTATION_EXPONENT=SCIENTIFIC_NOTATION_EXPONENT,
)


# -----------------------------------------------------------------------------
# Units
# -----------------------------------------------------------------------------

def per(numerator: str, denominator: str) -> str:
    # Copes with blank/optional numerators, too.
    return r"""
        (?:
            (?: {numerator} \s* \/ \s* {denominator} )      # n/d, n / d
            | (?: {numerator} \s* \b per \s+ {denominator} )   # n per d
            | (?: {numerator} \s* \b {denominator} \s? -1 )    # n d -1
        )
    """.format(numerator=numerator, denominator=denominator)


def out_of(n: int) -> str:
    return r"(?: (?: \/ | \b out \s+ of \b ) \s* n \b )".format(n=n)


MM = r"(?:mm|millimet(?:re:er)[s]?)"  # mm, millimetre(s), millimeter(s)
MG = r"(?:mg|milligram[s]?)"  # mg, milligram, milligrams
L = r"(?:L|lit(?:re|er)[s]?)"  # L, litre(s), liter(s)
DL = r"(?:d(?:eci)?{L})".format(L=L)
HOUR = r"(?:h(?:r|our)?)"   # h, hr, hour
CUBIC_MM = r"""
    (?:
        (?: cubic [\s]+ {MM} )      # cubic mm, etc
        | (?: {MM} [\s]* [\^]? [\s]*3 )        # mm^3, mm3, mm 3, etc.
    )
""".format(MM=MM)
CELLS = r"(?: cell[s]? )"
OPTIONAL_CELLS = CELLS + "?"

MILLIMOLES = r"(?:mmol(?:es?))"
MILLIEQ = r"(?:mEq)"
MILLIMOLAR = r"(?:mM)"

MM_PER_H = per(MM, HOUR)
MG_PER_DL = per(MG, DL)
MG_PER_L = per(MG, L)
MILLIMOLES_PER_L = per(MILLIMOLES, L)
MILLIEQ_PER_L = per(MILLIEQ, L)

BILLION_PER_L = per(BILLION, L)
PER_CUBIC_MM = per("", CUBIC_MM)
CELLS_PER_CUBIC_MM = per(OPTIONAL_CELLS, CUBIC_MM)

PERCENT = r"""
    (?:
        %
        | pe?r?\s?ce?n?t    # must have pct, other characters optional
    )
"""

# =============================================================================
# Regexes based on some of the fragments above
# =============================================================================

RE_IS = regex.compile(IS, REGEX_COMPILE_FLAGS)
RE_WAS = regex.compile(WAS, REGEX_COMPILE_FLAGS)


# =============================================================================
# Standardized result values
# =============================================================================

PAST = "past"
PRESENT = "present"


# =============================================================================
#  Generic processors
# =============================================================================

def to_float(s: str) -> float:
    if ',' in s:
        s = s.replace(',', '')
    return float(s)


class NumericalResultParser(NlpParser):
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
                 regex_str: str,
                 variable: str,
                 target_unit: str,
                 units_to_factor: Dict[typing.re.Pattern, float],
                 commit: bool = False) -> None:
        """
        This class operates with compiled regexes having this group format:
          - variable
          - tense_indicator
          - relation
          - value
          - units

        units_to_factor: dictionary, mapping
            (compiled regex for units)
            -> (factor [multiple] to multiple those units by, to get preferred
                unit)
        """
        super().__init__(nlpdef=nlpdef, cfgsection=cfgsection, commit=commit)
        self.compiled_regex = regex.compile(regex_str, REGEX_COMPILE_FLAGS)
        self.variable = variable
        self.target_unit = target_unit
        self.units_to_factor = {
            regex.compile(k, REGEX_COMPILE_FLAGS): v
            for k, v in units_to_factor.items()
        }

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

    # noinspection PyMethodMayBeStatic
    def set_tablename(self, tablename: str) -> None:
        """Used occasionally by friend classes to override """
        pass

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
        for m in self.compiled_regex.finditer(text):
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

            # If units are known (or we're choosing to assume preferred units if
            # none are specified), calculate an absolute value
            value_in_target_units = None
            if units:
                for unit_regex, multiple in self.units_to_factor.items():
                    if unit_regex.match(units):
                        value_in_target_units = to_float(value_text) * multiple
                        break
            elif self.assume_preferred_unit:  # unit is None or empty
                value_in_target_units = to_float(value_text)

            # Sort out tense, if known, and impute that "CRP was 72" means that
            # relation was EQ in the PAST, etc.
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

def test_compiled_regex(compiled_regex: typing.re.Pattern, text: str,
                        prefix_spaces: int = 4) -> None:
    results = []
    for m in compiled_regex.finditer(text):
        results.append(m.group(0))
    print("{}{} -> {}".format(' ' * prefix_spaces,
                              repr(text), repr(results)))


def test_text_regex(regex_text: str, text: str,
                    prefix_spaces: int = 4) -> None:
    compiled_regex = regex.compile(regex_text, REGEX_COMPILE_FLAGS)
    test_compiled_regex(compiled_regex, text, prefix_spaces=prefix_spaces)


def test_base_regexes() -> None:
    numbers = ["1", "12345", "-1", "1.2", "-3.4", "+3.4",
               "-3.4e27.3", "3.4e-27", "9,800", "17,600.34", "-17,300.6588"]

    print("UNSIGNED_INTEGER:")
    for s in numbers:
        test_text_regex(UNSIGNED_INTEGER, s)

    print("SIGNED_INTEGER:")
    for s in numbers:
        test_text_regex(SIGNED_INTEGER, s)

    print("UNSIGNED_FLOAT:")
    for s in numbers:
        test_text_regex(UNSIGNED_FLOAT, s)

    print("SIGNED_FLOAT:")
    for s in numbers:
        test_text_regex(SIGNED_FLOAT, s)

    print("LIBERAL_NUMBER:")
    for s in numbers:
        test_text_regex(LIBERAL_NUMBER, s)

    print("UNITS_CELLS_PER_CUBIC_MM:")
    test_text_regex(CELLS_PER_CUBIC_MM, "cells/mm3")
    test_text_regex(CELLS_PER_CUBIC_MM, "blibble")


# =============================================================================
#  Command-line entry point
# =============================================================================

if __name__ == '__main__':
    test_base_regexes()
