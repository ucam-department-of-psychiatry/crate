#!/usr/bin/env python
# crate_anon/nlp_manager/regex_numbers.py


# =============================================================================
# Numbers
# =============================================================================

# -----------------------------------------------------------------------------
# Mathematical operations and quantities
# -----------------------------------------------------------------------------

def times_ten_to_power(n):
    return r"(?: {MULTIPLY}? \s* 10 \s* {POWER_INC_E} \s* {n})".format(
        MULTIPLY=MULTIPLY, POWER_INC_E=POWER_INC_E, n=n)

MULTIPLY = r"[x\*×⋅]"  # x, *, ×, ⋅
POWER = r"(?: \^ | \*\* )"  # ^, **
POWER_INC_E = r"(?: e | \^ | \*\* )"  # e, ^, **
BILLION = times_ten_to_power(9)


# -----------------------------------------------------------------------------
# Number components
# -----------------------------------------------------------------------------
# Don't create components that are entirely optional; they're hard to test!

PLUS_SIGN = r"\+"  # don't forget to escape it
MINUS_SIGN = r"[-−–]"  # any of: ASCII hyphen-minus, Unicode minus, en dash
SIGN = r"(?: {plus} | {minus} )".format(plus=PLUS_SIGN, minus=MINUS_SIGN)

NO_MINUS_SIGN = r"(?!{minus})".format(minus=MINUS_SIGN)
# ... (?! something ) is a negative lookahead assertion

PLAIN_INTEGER = r"(?:\d+)"
# Numbers with commas: http://stackoverflow.com/questions/5917082
# ... then modified a little, because that fails with Python's regex module;
# (a) the "\d+" grabs things like "12,000" and thinks "aha, 12", so we have to
#     fix that by putting the "thousands" bit first; then
# (b) that has to be modified to contain at least one comma/thousands grouping
#     (or it will treat "9800" as "980").

PLAIN_INTEGER_W_THOUSAND_COMMAS = r"(?: (?: \d{1,3} (?:,\d{3})+ ) | \d+ )"
# ... plain integer allowing commas as a thousands separator
#       (1) a number with thousands separators, or
#       (2) a plain number
# ... NOTE: PUT THE ONE THAT NEEDS TO BE GREEDIER FIRST, i.e. the one with
# thousands separators

FLOATING_POINT_GROUP = r"(?: \. \d+ )"  # decimal point and further digits
SCIENTIFIC_NOTATION_EXPONENT = r"(?: E {sign}? \d+ )".format(
    sign=SIGN,  # optional
)
# ... Scientific notation does NOT offer non-integer exponents.
# Specifically, float("-3.4e-27") is fine, but float("-3.4e-27.1") isn't.


# -----------------------------------------------------------------------------
# Number types
# -----------------------------------------------------------------------------
# Beware of unsigned types. You may not want a sign, but if you use an
# unsigned type, "-3" will be read as "3".

UNSIGNED_INTEGER = PLAIN_INTEGER_W_THOUSAND_COMMAS
SIGNED_INTEGER = r"(?: {sign}? {integer} )".format(
    sign=SIGN,  # optional
    integer=PLAIN_INTEGER_W_THOUSAND_COMMAS,
)
UNSIGNED_FLOAT = r"(?: {nominus} {plus}? {integer} {fp}? )".format(
    nominus=NO_MINUS_SIGN,
    plus=PLUS_SIGN,  # optional
    integer=PLAIN_INTEGER_W_THOUSAND_COMMAS,
    fp=FLOATING_POINT_GROUP,  # optional
)
SIGNED_FLOAT = r"(?: {sign}? {integer} {fp}? )".format(
    sign=SIGN,  # optional
    integer=PLAIN_INTEGER_W_THOUSAND_COMMAS,
    fp=FLOATING_POINT_GROUP,  # optional
)
LIBERAL_NUMBER = r"(?: {sign}? {integer} {fp}? {exp}? )".format(
    sign=SIGN,  # optional
    integer=PLAIN_INTEGER_W_THOUSAND_COMMAS,
    fp=FLOATING_POINT_GROUP,  # optional
    exp=SCIENTIFIC_NOTATION_EXPONENT,  # optional
)
