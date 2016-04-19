#!/usr/bin/env python3
# extra/nhs.py

import logging
import random

log = logging.getLogger(__name__)


# =============================================================================
# NHS number validation
# =============================================================================

NHS_DIGIT_WEIGHTINGS = [10, 9, 8, 7, 6, 5, 4, 3, 2]


def nhs_check_digit(ninedigits):
    """
    Calculates an NHS number check digit.
    ninedigits: string or list

    1. Multiply each of the first nine digits by the corresponding
       digit weighting (see NHS_DIGIT_WEIGHTINGS).
    2. Sum the results.
    3. Take remainder after division by 11.
    4. Subtract the remainder from 11
    5. If this is 11, use 0 instead
    If it's 10, the number is invalid
    If it doesn't match the actual check digit, the number is invalid
    """
    if len(ninedigits) != 9 or not [str(x).isdigit() for x in ninedigits]:
        raise ValueError("bad string to nhs_check_digit")
    check_digit = 11 - (sum([
        d * f
        for (d, f) in zip(ninedigits, NHS_DIGIT_WEIGHTINGS)
    ]) % 11)
    # ... % 11 yields something in the range 0-10
    # ... 11 - that yields something in the range 1-11
    if check_digit == 11:
        check_digit = 0
    return check_digit


def is_valid_nhs_number(n):
    """
    Validates an integer as an NHS number.
    Checksum details are at
        http://www.datadictionary.nhs.uk/version2/data_dictionary/data_field_notes/n/nhs_number_de.asp  # noqa
    """
    if not isinstance(n, int):
        log.debug("is_valid_nhs_number: parameter was not of integer type")
        return False

    s = str(n)
    # Not 10 digits long?
    if len(s) != 10:
        log.debug("is_valid_nhs_number: not 10 digits")
        return False

    main_digits = [int(s[i]) for i in range(9)]
    actual_check_digit = int(s[9])  # tenth digit
    expected_check_digit = nhs_check_digit(main_digits)
    if expected_check_digit == 10:
        log.debug("is_valid_nhs_number: calculated check digit invalid")
        return False
    if expected_check_digit != actual_check_digit:
        log.debug("is_valid_nhs_number: check digit mismatch")
        return False
    # Hooray!
    return True


def generate_random_nhs_number():
    """Returns a random valid NHS number, as an int."""
    check_digit = 10  # NHS numbers with this check digit are all invalid
    while check_digit == 10:
        digits = [random.randint(1, 9)]  # don't start with a zero
        digits.extend([random.randint(0, 9) for _ in range(8)])
        # ... length now 9
        check_digit = nhs_check_digit(digits)
    # noinspection PyUnboundLocalVariable
    digits.append(check_digit)
    return int("".join([str(d) for d in digits]))
