"""
crate_anon/nlp_manager/regex_units.py

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

**Regular expressions to detect physical units.**

"""

from typing import List, Optional, Tuple

from crate_anon.nlp_manager.regex_numbers import (
    BILLION,
    MULTIPLY_OR_SPACE,
    PLAIN_INTEGER,
    POWER,
    TRILLION,
)


# =============================================================================
# Physical units
# =============================================================================

OUT_OF_SEPARATOR = r"(?: \/ | \b out \s+ of \b )"


def per(
    numerator: str,
    denominator: str,
    include_power_minus1: bool = True,
    numerator_optional: bool = False,
) -> str:
    """
    Returns regex text representing "X per Y"; e.g. "millimoles per litre",
    "cells per cubic millimetre".

    Args:
        numerator: regex representing the numerator
        denominator: regex representing the denominator
        include_power_minus1: include the "n d -1" format for "n/d"
        numerator_optional: presence of the numerator is optional
    """
    if numerator:
        if numerator_optional:
            # ensure that the optional whitespace is captured as part of the
            # "optional" bit, so there is no leftover whitespace that can
            # remain
            numerator_part = rf"(?: {numerator} \s* )?"
        else:
            # numerator, optional whitespace
            numerator_part = rf"{numerator} \s*"
        # Use of "\s* \b" rather than "\s+" is so we can have a BLANK
        # numerator.
    else:
        # Blank numerator
        numerator_part = ""
    options = [
        rf"{numerator_part} (?: \/ | \b per \b) \s* {denominator}",
    ]
    if include_power_minus1:
        options.append(rf"{numerator_part} \b {denominator} \s* -1")
    return r"(?: {} )".format(" | ".join(options))


def _out_of_str(n_as_regex: str) -> str:
    """
    Returns regex text representing "out of N".

    Args:
        n_as_regex: the "N", as a regular expression
    """
    # / n
    # out of n
    return rf"(?: {OUT_OF_SEPARATOR} \s* {n_as_regex} \b)"


def out_of(n: int) -> str:
    """
    Returns regex text representing "out of N".

    Args:
        n: the number N
    """
    return _out_of_str(str(n))


def out_of_anything() -> str:
    """
    Returns:
        regex representing "out of N" where N is any number
    """
    return _out_of_str(PLAIN_INTEGER)


def power(x: str, n: int, allow_no_operator: bool = False) -> str:
    """
    Returns regex text representing "x to the power n".

    Args:
        x: base
        n: exponent
        allow_no_operator: make the operator (like ``^`` or ``**``) optional?
    """
    return r"(?: {x} \s* {power}{optional} \s* {n})".format(
        x=x,
        power=POWER,
        optional="?" if allow_no_operator else "",
        n=n,
    )


def units_times(*args: str) -> str:
    """
    Returns regular expression text combining all its inputs with optional
    multiplication.

    For units, where they are notionally multiplied.
    """
    multiply = MULTIPLY_OR_SPACE + "?"
    joined = multiply.join(args)
    return rf"(?: {joined} )"


def units_by_dimension(
    *args: Tuple[str, int],  # specify type of *one* arg!
    allow_no_operator: bool = False,
) -> str:
    """
    Returns regex text for a unit where we specify them by their dimensions.

    Args:
        *args: each is a tuple ``unit, power``
        allow_no_operator: make the operator (like ``^`` or ``**``) optional?
    """
    multiply = " " + MULTIPLY_OR_SPACE + " "
    power_elements = []  # type: List[str]
    for i, unit_exponent in enumerate(args):
        unit, exponent = unit_exponent
        assert exponent != 0
        power_elements.append(
            power(unit, exponent, allow_no_operator=allow_no_operator)
        )
    joined_power_elements = multiply.join(power_elements)
    power_style = rf"(?: {joined_power_elements} )"
    options = [power_style]
    # noinspection PyChainedComparisons
    if len(args) == 2 and args[0][1] > 0 and args[1][1] < 0:
        # x per y
        options.append(per(args[0][0], args[1][0], include_power_minus1=False))
    return r"(?: {} )".format(r" | ".join(options))


# -----------------------------------------------------------------------------
# Distance
# -----------------------------------------------------------------------------

M = r"(?: met(?:re|er)s? | m )"  # m, metre(s), meter(s)
CM = r"(?: cm | centimet(?:re|er)s? )"  # cm, centimetre(s), centimeter(s)
MM = r"(?: mm | millimet(?:re|er)s? )"  # mm, millimetre(s), millimeter(s)

FEET = r"""(?: f(?:ee|oo)?t | \' | ’ | ′ )"""
# ... feet, foot, ft
# ... apostrophe, right single quote (U+2019), prime (U+2032)
INCHES = r"""(?: in(?:ch(?:e)?)?s? | \" | ” | ″)"""
# ... in, ins, inch, inches, [inchs = typo but clear]
# ... ", right double quote (U+2014), double prime (U+2033)

# -----------------------------------------------------------------------------
# Mass
# -----------------------------------------------------------------------------

MCG = r"(?: mcg | microgram(?:me)?s? | [μu]g )"  # you won't stop people using ug...  # noqa
MG = r"(?: mg | milligram(?:me)?s? )"  # mg, milligram, milligrams, milligramme, milligrammes  # noqa
G = r"(?: gram(?:me)?s? | g )"  # g, gram, grams, gramme, grammes  # noqa
KG = r"(?: kgs? | kilo(?:gram(?:me)?)?s? )"  # kg, kgs, kilos ... kilogrammes etc.  # noqa
LB = r"(?: pounds? | lbs? )"  # pound(s), lb(s)
STONES = r"(?: stones? | st\.? )"  # stone(s), st, st.

# -----------------------------------------------------------------------------
# Volume
# -----------------------------------------------------------------------------

L = r"(?: lit(?:re|er)s? | L )"  # L, litre(s), liter(s)
DL = rf"(?: d(?:eci)?{L} )"  # 10^-1
ML = rf"(?: m(?:illi)?{L} )"  # 10^-3
MICROLITRE = rf"(?: micro{L} | [μu]L )"  # 10^-6: microL, microliter(s), microlitre(s), μL, uL  # noqa
NANOLITRE = rf"(?: nano{L} | nL )"  # 10^-9: nanoL, nanoliter(s), nanolitre(s), nL  # noqa
PICOLITRE = rf"(?: pico{L} | pL )"  # 10^-12: picoL, picoliter(s), picolitre(s), pL  # noqa
FEMTOLITRE = rf"(?: femto{L} | fL )"  # 10^-15: femtoL, femtoliter(s), femtolitre(s), fL  # noqa
# CUBIC_MM = r"""(?: (?:\b cubic \s+ {mm}) | {mm_cubed} )""".format(  # noqa
CUBIC_MM = r"""(?: (?:\b cubic \s+ {mm}) | {mm_cubed} | (?: \b cmm \b ) )""".format(  # noqa
    mm=MM, mm_cubed=power(MM, 3, allow_no_operator=True)
)
# cubic mm, etc. | mm^3, mm3, mm 3, etc. | cmm
# "cmm" added 2018-09-07 having seen this in the wild (albeit urinary results).

# A microlitre is of course the same as a cubic millimetre:
CUBIC_MM_OR_MICROLITRE = rf"(?: {MICROLITRE} | {CUBIC_MM} )"

# -----------------------------------------------------------------------------
# Inverse (reciprocal) volume
# -----------------------------------------------------------------------------

PER_CUBIC_MM = per("", CUBIC_MM, numerator_optional=True)

# -----------------------------------------------------------------------------
# Time
# -----------------------------------------------------------------------------

HOUR = r"(?: \b h(?:rs?|ours?)? \b)"  # h, hr, hrs, hour, hours
DAY = r"(?: \b d(?:y?|ay?)? \b )"  # d, dy, day
WEEK = r"(?: \b w(?:k?|eek?)? \b)"  # w, wk, week
MONTH = r"(?:\b month \b)"  # month
YEAR = r"(?:\b y(?:(?:ea)?r)? \b)"  # y, yr, year

DAYS_PER_WEEK = 7

# The mean month (across a normal 4-year cycle ignoring century non-leap years)
# is 30.4375 days:
# n <- c(28, rep(30, 4), rep(31, 7))  # mean 30.41667
# l <- c(29, rep(30, 4), rep(31, 7))  # mean 30.5
# fouryearcycle <- c(n, n, n, l)  # mean 30.4375
# century <- c(rep(n, 76), rep(l, 24))  # mean 30.43667
# mean(n) / 7  # 4.345238
# mean(fouryearcycle) / 7  # 4.348214
# mean(century) / 7  # 4.348095
# ... the Google answer for weeks per month is 4.34524, i.e. a normal year.
# But let's not be spuriouly precise:
WEEKS_PER_MONTH_APPROX = 4.35
WEEKS_PER_YEAR_APPROX = 52

# -----------------------------------------------------------------------------
# Proportions
# -----------------------------------------------------------------------------

PERCENT = r"""(?:%|pe?r?\s?ce?n?t)"""
# "%" or some subset of "percent" -- for the latter, must have "pct", other
# characters optional

# -----------------------------------------------------------------------------
# Arbitrary count things
# -----------------------------------------------------------------------------

CELLS = r"(?:\b cells? \b)"

UNITS = r"(?: (?:I\.?)? U(?:nits?|\.)? )"  # U, IU, I.U., unit, units...
# (IU for international units)
MICROUNITS = rf"(?: (?:micro|μ|u) {UNITS} )"
MILLIUNITS = rf"(?: m(?:illi)? {UNITS} )"

UK = r"(?: U(?:nited\s+|\.\s*)? K(?:ingdom|\.)? )"
ALCOHOL = r"(?: \b(?:alcohol|ethanol|EtOH)\b )"
UK_ALCOHOL_UNITS = rf"(?: (?: {UK} \s+)? ({ALCOHOL} \s+)? {UNITS} )"
# U, unit, units, UK units, UK alcohol units...
# I thought not "IU" as they are not international units; however, RS used that
# term, so whether correct or in error, that's sufficient for me to include it!
UK_ALCOHOL_UNITS_PER_DAY = per(
    UK_ALCOHOL_UNITS, DAY, include_power_minus1=False
)
UK_ALCOHOL_UNITS_PER_WEEK = per(
    UK_ALCOHOL_UNITS, WEEK, include_power_minus1=False
)
UK_ALCOHOL_UNITS_PER_MONTH = per(
    UK_ALCOHOL_UNITS, MONTH, include_power_minus1=False
)
UK_ALCOHOL_UNITS_PER_YEAR = per(
    UK_ALCOHOL_UNITS, YEAR, include_power_minus1=False
)

SCORE = r"(?:scored?)"  # score(d)

# -----------------------------------------------------------------------------
# Moles
# -----------------------------------------------------------------------------

MOLES = r"(?:\b mole?s? \b)"  # mol, mole, mols, moles
MICROMOLES = r"(?: (?:micro|μ|u)mole?s? )"
MILLIMOLES = r"(?: m(?:illi)?mole?s? )"

MICROEQ = r"(?: (?:micro|μ|u)Eq )"
MILLIEQ = r"(?: m(?:illi)?Eq )"

# -----------------------------------------------------------------------------
# Concentration (molarity)
# -----------------------------------------------------------------------------

MICROMOLAR = r"(?:[μu]M | micromolar)"
MILLIMOLAR = r"(?:mM)"  # NB case-insensitive... confusable with millimetres

MICROEQ_PER_L = per(MICROEQ, L)
MICROMOLES_PER_L = per(MICROMOLES, L)
MILLIEQ_PER_L = per(MILLIEQ, L)
MILLIMOLES_PER_L = per(MILLIMOLES, L)

# -----------------------------------------------------------------------------
# Concentration (mass)
# -----------------------------------------------------------------------------

G_PER_DL = per(G, DL)
G_PER_L = per(G, L)
L_PER_L = per(L, L)
MG_PER_DL = per(MG, DL)
MG_PER_L = per(MG, L)

# -----------------------------------------------------------------------------
# Concentration (arbitrary count and dimensionless things)
# -----------------------------------------------------------------------------

BILLION_PER_L = per(BILLION, L)
TRILLION_PER_L = per(TRILLION, L)

CELLS_PER_CUBIC_MM = per(CELLS, CUBIC_MM, numerator_optional=True)
CELLS_PER_CUBIC_MM_OR_MICROLITRE = per(
    CELLS, CUBIC_MM_OR_MICROLITRE, numerator_optional=True
)

MICROUNITS_PER_ML = per(MICROUNITS, ML)
MILLIUNITS_PER_L = per(MILLIUNITS, L)
UNITS_PER_L = per(UNITS, L)

MILLIMOLES_PER_MOL = per(MILLIMOLES, MOLES)

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
# Area and related
# -----------------------------------------------------------------------------

SQ_M = r"""
    (?:  # square metres
        (?: sq(?:uare)? \s+ {m} )       # sq m, square metres, etc.
        | (?: {m} \s+ sq(?:uared?)? )   # m sq, metres square(d), etc.
        | {m_sq}                        # m ^ 2, etc.
    )
""".format(
    m=M, m_sq=power(M, 2)
)

# BMI
KG_PER_SQ_M = r"(?: {kg_per_sqm} | {kg_sqm_pow_minus2} )".format(
    kg_per_sqm=per(KG, SQ_M, include_power_minus1=False),
    kg_sqm_pow_minus2=units_times(KG, power(M, -2)),
)


# =============================================================================
#  Generic conversion functions
# =============================================================================


def kg_from_st_lb_oz(
    stones: float = 0, pounds: float = 0, ounces: float = 0
) -> Optional[float]:
    """
    Convert Imperial to metric mass.

    Returns:
        mass in kg

    """
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


def m_from_ft_in(feet: float = 0, inches: float = 0) -> Optional[float]:
    """
    Converts Imperial to metric length.

    Returns:
        length in m

    """
    # 12 inches in a foot
    # 1 inch = 25.4 mm
    try:
        total_inches = (feet * 12) + inches
        return total_inches * 25.4 / 1000
    except (TypeError, ValueError):
        return None


def m_from_m_cm(metres: float = 0, centimetres: float = 0) -> Optional[float]:
    """
    Converts metres/centimetres to metres.
    """
    try:
        return metres + (centimetres / 100)
    except (TypeError, ValueError):
        return None


def assemble_units(components: List[Optional[str]]) -> str:
    """
    Takes e.g. ``["ft", "in"]`` and makes ``"ft in"``.
    """
    active_components = [c for c in components if c]
    return " ".join(active_components)


def factor_millimolar_from_mg_per_dl(molecular_mass_g_per_mol: float) -> float:
    """
    Returns the conversion factor that you should multiple a "mg/dL" number by
    to get a "mM" (mmol/L) number.

    Principle:

    .. code-block:: none

        mmol_per_L
            = 0.001 * mol_per_L
            = 0.001 * (g_per_L / g_per_mol)
            = 0.001 * ((10 * g_per_dL) / g_per_mol)
            = 0.001 * ((10 * 1000 * mg_per_dL) / g_per_mol)
            = (0.001 * 10 * 1000 / g_per_mol) * mg_per_dL
            = (10 / g_per_mol) * mg_per_dl

        Example:
            glucose, molecular mass 180.156 g/mol
            => conversion factor is (10 / 180.156)
            90 mg/dL -> (10 / 180.156) * 90 mM = 5.0 mM

    Args:
        molecular_mass_g_per_mol: molecular mass in g/mol

    Returns:
        conversion factor

    """
    return 10 / molecular_mass_g_per_mol


def factor_micromolar_from_mg_per_dl(molecular_mass_g_per_mol: float) -> float:
    """
    Returns the conversion factor that you should multiple a "mg/dL" number by
    to get a "μM" (μmol/L) number.

    Args:
        molecular_mass_g_per_mol: molecular mass in g/mol

    Returns:
        conversion factor

    """
    return 1000 * factor_millimolar_from_mg_per_dl(molecular_mass_g_per_mol)


def millimolar_from_mg_per_dl(
    mg_per_dl: float, molecular_mass_g_per_mol: float
) -> float:
    """
    Converts a concentration from mg/dL to mM (mmol/L).

    Args:
        mg_per_dl: value in mg/dL
        molecular_mass_g_per_mol: molecular mass in g/mol

    Returns:
        value in mM = mmol/L

    """
    return mg_per_dl * factor_millimolar_from_mg_per_dl(
        molecular_mass_g_per_mol
    )


def micromolar_from_mg_per_dl(
    mg_per_dl: float, molecular_mass_g_per_mol: float
) -> float:
    """
    Converts a concentration from mg/dL to μM (μmol/L).

    Args:
        mg_per_dl: value in mg/dL
        molecular_mass_g_per_mol: molecular mass in g/mol

    Returns:
        value in μM = μmol/L

    """
    return mg_per_dl * factor_micromolar_from_mg_per_dl(
        molecular_mass_g_per_mol
    )
