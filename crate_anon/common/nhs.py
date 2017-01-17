#!/usr/bin/env python
# crate_anon/crateweb/extra/nhs.py

"""
===============================================================================
    Copyright © 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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
"""

import logging
import random
from typing import List, Optional, Union

log = logging.getLogger(__name__)


# =============================================================================
# NHS number validation
# =============================================================================

NHS_DIGIT_WEIGHTINGS = [10, 9, 8, 7, 6, 5, 4, 3, 2]


def nhs_check_digit(ninedigits: Union[str, List[Union[str, int]]]) -> int:
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
    if len(ninedigits) != 9 or not all(str(x).isdigit() for x in ninedigits):
        raise ValueError("bad string to nhs_check_digit")
    check_digit = 11 - (sum([
        int(d) * f
        for (d, f) in zip(ninedigits, NHS_DIGIT_WEIGHTINGS)
    ]) % 11)
    # ... % 11 yields something in the range 0-10
    # ... 11 - that yields something in the range 1-11
    if check_digit == 11:
        check_digit = 0
    return check_digit


def is_valid_nhs_number(n: int) -> bool:
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


def generate_random_nhs_number() -> int:
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


def generate_nhs_number_from_first_9_digits(first9digits: str) -> Optional[int]:
    """
    Returns a valid NHS number, as an int, given the first 9 digits.
    The particular purpose is to make NHS numbers that *look* fake.
    Specifically:
        123456789_ : no; checksum 10
        987654321_ : yes, for 9876543210
        999999999_ : yes, for 9999999999
    """
    if len(first9digits) != 9:
        log.warning("Not 9 digits")
        return None
    try:
        first9int = int(first9digits)
    except (TypeError, ValueError):
        log.warning("Not an integer")
        return None  # not an int
    if len(str(first9int)) != len(first9digits):
        # e.g. leading zeros, or some such
        log.warning("Leading zeros?")
        return None
    check_digit = nhs_check_digit(first9digits)
    if check_digit == 10:  # NHS numbers with this check digit are all invalid
        log.warning("Can't have check digit of 10")
        return None
    return int(first9digits + str(check_digit))
