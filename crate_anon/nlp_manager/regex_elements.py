#!/usr/bin/env python
# crate_anon/nlp_manager/regex_elements.py

# Shared elements for regex-based NLP work.

import regex
import typing
from typing import List, Dict

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
    [
        \s \| \( \) H L \*
    ]*
"""
# - whitespace
# - you often get | characters when people copy/paste tables
# - brackets, H/L, and *, for things like
#       17 (H), 17 (*), 17 HH
#   i.e. blood test abnormality markers


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

UNITS_MM_H = per(MM, HOUR)
UNITS_MG_DL = per(MG, DL)
UNITS_MG_L = per(MG, L)

UNITS_BILLION_PER_L = per(BILLION, L)
UNITS_PER_CUBIC_MM = per("", CUBIC_MM)
UNITS_CELLS_PER_CUBIC_MM = per(OPTIONAL_CELLS, CUBIC_MM)


# =============================================================================
# Regexes based on some of the fragments above
# =============================================================================

RE_IS = regex.compile(IS, REGEX_COMPILE_FLAGS)
RE_WAS = regex.compile(WAS, REGEX_COMPILE_FLAGS)
RE_UNITS_MG_DL = regex.compile(UNITS_MG_DL, REGEX_COMPILE_FLAGS)
RE_UNITS_MG_L = regex.compile(UNITS_MG_L, REGEX_COMPILE_FLAGS)
RE_UNITS_MM_H = regex.compile(UNITS_MM_H, REGEX_COMPILE_FLAGS)
RE_UNITS_BILLION_PER_L = regex.compile(UNITS_BILLION_PER_L,
                                       REGEX_COMPILE_FLAGS)
RE_UNITS_PER_CUBIC_MM = regex.compile(UNITS_PER_CUBIC_MM, REGEX_COMPILE_FLAGS)
RE_UNITS_CELLS_PER_CUBIC_MM = regex.compile(UNITS_CELLS_PER_CUBIC_MM,
                                            REGEX_COMPILE_FLAGS)


# =============================================================================
# Standardized result values
# =============================================================================

PAST = "past"
PRESENT = "present"


# =============================================================================
#  Generic processor
# =============================================================================

def to_float(s: str) -> float:
    if ',' in s:
        s = s.replace(',', '')
    return float(s)


def numerical_result_finder(text: str,
                            compiled_regex: typing.re.Pattern,
                            variable: str,
                            target_unit: str,
                            unitregex_to_multiple_dict: Dict,
                            assume_preferred_unit: bool = False) -> List[Dict]:
    # This function operates with compiled regexes having this format:
    #   - variable
    #   - tense_indicator
    #   - relation
    #   - value
    #   - units
    # For performance reasons, we do not take the regex and assemble or
    results = []
    for m in compiled_regex.finditer(text):
        startpos = m.start()
        endpos = m.end()
        # groups = repr(m.groups())  # all matching groups
        matching_text = m.group(0)  # the whole thing
        # matching_text = text[startpos:endpos]  # same thing

        variable_text = m.group(1)
        tense_indicator = m.group(2)
        relation = m.group(3)
        value = m.group(4)
        units = m.group(5)

        # If units are known (or we're choosing to assume preferred units if
        # none are specified), calculate an absolute value
        value_in_target_units = None
        if units:
            for unit_regex, multiple in unitregex_to_multiple_dict.items():
                if unit_regex.match(units):
                    value_in_target_units = to_float(value) * multiple
                    break
        elif assume_preferred_unit:  # unit is None or empty
            value_in_target_units = to_float(value)

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

        results.append({
            'variable': variable,

            'matching_text': matching_text,
            'startpos': startpos,
            'endpos': endpos,

            # 'groups': groups,

            'variable_text': variable_text,
            'relation': relation,
            'value': value,
            'units': units,
            target_unit: value_in_target_units,
            'tense': tense,
        })
    return results


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

    print("RE_UNITS_CELLS_PER_CUBIC_MM:")
    test_compiled_regex(RE_UNITS_CELLS_PER_CUBIC_MM, "cells/mm3")
    test_compiled_regex(RE_UNITS_CELLS_PER_CUBIC_MM, "blibble")


# =============================================================================
#  Command-line entry point
# =============================================================================

if __name__ == '__main__':
    test_base_regexes()
