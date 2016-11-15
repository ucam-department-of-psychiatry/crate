#!/usr/bin/env python
# crate_anon/nlp_manager/regex_units.py

from typing import List, Optional
from crate_anon.nlp_manager.regex_numbers import BILLION, PLAIN_INTEGER, POWER


# =============================================================================
# Physical units
# =============================================================================

def per(numerator: str, denominator: str) -> str:
    # Copes with blank/optional numerators, too.
    return r"""
        (?:  # numerator 'per' denominator
            (?: {numerator} \s* \/ \s* {denominator} )      # n/d, n / d
            | (?: {numerator} \s* \b per \s+ {denominator} )   # n per d
            | (?: {numerator} \s* \b {denominator} \s* -1 )    # n d -1; n d-1
        )
    """.format(numerator=numerator, denominator=denominator)
    # Use of "\s* \b" rather than "\s+" is so we can have a BLANK numerator.


def _out_of_str(n_as_regex: str):
    # / n
    # out of n
    return r"""
        (?:  # 'out of' denominator
            (?: \/ | \b out \s+ of \b ) \s* {n} \b
        )
    """.format(n=n_as_regex)


def out_of(n: int) -> str:
    return _out_of_str(str(n))


def out_of_anything() -> str:
    # out_of(n) where n is any number
    return _out_of_str(PLAIN_INTEGER)


# -----------------------------------------------------------------------------
# Distance
# -----------------------------------------------------------------------------

M = r"(?: m | met(?:re:er)s? )"  # m, metre(s), meter(s)
CM = r"(?: cm | centimet(?:re:er)s? )"   # cm, centimetre(s), centimeter(s)
MM = r"(?: mm | millimet(?:re:er)s? )"   # mm, millimetre(s), millimeter(s)

FEET = r"""(?: f(?:ee|oo)?t | \' )"""  # feet, foot, ft | '
INCHES = r'''(?: in(?:ch(?:e)?)?s? | \" )'''
# ... in, ins, inch, inches, [inchs = typo but clear] | "

# -----------------------------------------------------------------------------
# Mass
# -----------------------------------------------------------------------------

MCG = r"(?: mcg | microgram(?:me)?s? | [μu]g )"  # you won't stop people using ug...  # noqa
MG = r"(?: mg | milligram(?:me)?s? )"  # mg, milligram, milligrams, milligramme, milligrammes  # noqa
G = r"(?: g | gram(?:me)?s? )"  # g, gram, grams, gramme, grammes  # noqa
KG = r"(?: kgs? | kilo(?:gram(?:me)?)?s? )"  # kg, kgs, kilos ... kilogrammes etc.  # noqa
LB = r"(?: pounds? | lbs? )"  # pound(s), lb(s)
STONES = r"(?: stones? | st\.? )"  # stone(s), st, st.

# -----------------------------------------------------------------------------
# Volume
# -----------------------------------------------------------------------------

L = r"(?: L | lit(?:re|er)s? )"  # L, litre(s), liter(s)
DL = r"(?: d(?:eci)?{L} )".format(L=L)
ML = r"(?: m(?:illi)?{L} )".format(L=L)
CUBIC_MM = r"""(?: (?:\b cubic \s+ {MM}) | (?:{MM} \s* \^? \s* 3) )""".format(
    MM=MM)
# cubic mm, etc. | mm^3, mm3, mm 3, etc.

# -----------------------------------------------------------------------------
# Inverse volume
# -----------------------------------------------------------------------------

PER_CUBIC_MM = per("", CUBIC_MM)

# -----------------------------------------------------------------------------
# Time
# -----------------------------------------------------------------------------

HOUR = r"(?:h(?:r|our)?)"   # h, hr, hour

# -----------------------------------------------------------------------------
# Counts, proportions
# -----------------------------------------------------------------------------

PERCENT = r"""(?:%|pe?r?\s?ce?n?t)"""
# must have pct, other characters optional

# -----------------------------------------------------------------------------
# Arbitrary count things
# -----------------------------------------------------------------------------

CELLS = r"(?:\b cells? \b)"
OPTIONAL_CELLS = CELLS + "?"
MILLIMOLES = r"(?: mmol(?:es?) )"
MILLIEQ = r"(?:mEq)"

UNITS = r"(?:[I]?U)"  # U units, IU international units
MILLIUNITS = r"(?:m[I]?U)"
MICROUNITS = r"(?:[μu][I]?U)"

SCORE = r"(?:scored?)"  # score(d)

# -----------------------------------------------------------------------------
# Concentration
# -----------------------------------------------------------------------------

MILLIMOLAR = r"(?:mM)"  # NB case-insensitive... confusable with millimetres
MG_PER_DL = per(MG, DL)
MG_PER_L = per(MG, L)
MILLIMOLES_PER_L = per(MILLIMOLES, L)
MILLIEQ_PER_L = per(MILLIEQ, L)
BILLION_PER_L = per(BILLION, L)
CELLS_PER_CUBIC_MM = per(OPTIONAL_CELLS, CUBIC_MM)

MILLIUNITS_PER_L = per(MILLIUNITS, L)
MICROUNITS_PER_ML = per(MICROUNITS, ML)

# -----------------------------------------------------------------------------
# Speed
# -----------------------------------------------------------------------------

MM_PER_H = per(MM, HOUR)

# -----------------------------------------------------------------------------
# Pressure
# -----------------------------------------------------------------------------

MM_HG = r"(?: mm \s* Hg )"  # mmHg, mm Hg
# ... likelihood of "millimetres of mercury" quite small?

# -----------------------------------------------------------------------------
# Things to powers
# -----------------------------------------------------------------------------

SQ_M = r"""
    (?:  # square metres
        (?: sq(?:uare)? \s+ {M} )            # sq m, square metres, etc.
        | (?: {M} \s+ sq(?:uared?)? )       # m sq, metres square(d), etc.
        | (?: {M} \s+ {POWER} \s+ 2 )        # m ^ 2, etc.
    )
""".format(M=M, POWER=POWER)

# BMI
KG_PER_SQ_M = r"""
    (?:  # kg per square metre
        (?: {KG} \s+ per \s+ {SQ_M} )                       # (kg) per (sq m)
        | (?: {KG} \s* / \s* {SQ_M} )                       # (kg) / (sq m)
        | (?: {KG} \s+ {SQ_M} \s* {POWER} \s* - \s* 2 )     # (kg) (sq m) ^ -2
    )
""".format(KG=KG, SQ_M=SQ_M, POWER=POWER)


# =============================================================================
#  Generic conversion functions
# =============================================================================

def kg_from_st_lb_oz(stones: float = 0,
                     pounds: float = 0,
                     ounces: float = 0) -> float:
    # 16 ounces in a pound
    # 14 pounds in a stone
    # 1 avoirdupois pound = 0.45359237 kg
    # https://en.wikipedia.org/wiki/Pound_(mass)
    # Have you the peas? "Goods of weight"; aveir de peis (OFr.; see OED).
    try:
        total_pounds = (stones * 14) + pounds + (ounces / 16)
        return 0.45359237 * total_pounds
    except (TypeError, ValueError):
        return None


def m_from_ft_in(feet: float = 0, inches: float = 0) -> float:
    # 12 inches in a foot
    # 1 inch = 25.4 mm
    try:
        total_inches = (feet * 12) + inches
        return total_inches * 25.4 / 1000
    except (TypeError, ValueError):
        return None


def m_from_m_cm(metres: float = 0, centimetres: float = 0) -> float:
    try:
        return metres + (centimetres / 100)
    except (TypeError, ValueError):
        return None


def assemble_units(components: List[Optional[str]]) -> str:
    """Takes e.g. ["ft", "in"] and makes "ft in"."""
    active_components = [c for c in components if c]
    return " ".join(active_components)
