#!/usr/bin/env python
# crate_anon/nlp_manager/regex_numbers.py


# =============================================================================
# Numbers
# =============================================================================

# -----------------------------------------------------------------------------
# Mathematical operations and quantities
# -----------------------------------------------------------------------------

def times_ten_to_power(n):
    return r"(?:{MULTIPLY}?\s*10\s*{POWER_INC_E}\s*{n})".format(
        MULTIPLY=MULTIPLY, POWER_INC_E=POWER_INC_E, n=n)

MULTIPLY = r"[x*×⋅]"
POWER = r"(?: \^ | \*\* )"  # ^, **
POWER_INC_E = r"(?: e | \^ | \*\* )"  # e, ^, **
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
