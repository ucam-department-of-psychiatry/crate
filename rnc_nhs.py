#!/usr/bin/python
# -*- encoding: utf8 -*-

"""Support functions regarding NHS numbers, etc.

Author: Rudolf Cardinal (rudolf@pobox.com)
Created: Feb 2014
Last update: 22 Feb 2015

Copyright/licensing:

    Copyright (C) 2014-2015 Rudolf Cardinal (rudolf@pobox.com).

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
"""

import re
import logging
logging.basicConfig()
logger = logging.getLogger("rnc_nhs")
logger.setLevel(logging.INFO)

WHITESPACE_REGEX = re.compile('\s')
NON_NUMERIC_REGEX = re.compile("[^0-9]")  # or "\D"
DIGIT_WEIGHTINGS = [10, 9, 8, 7, 6, 5, 4, 3, 2]


# =============================================================================
# NHS numbers
# =============================================================================

def is_valid_nhs_number(n):
    """Validates an integer as an NHS number."""
    if not (type(n) is int or type(n) is long):
        logger.debug("is_valid_nhs_number: parameter was not an integer or "
                     "a long")
        return False
    try:
        s = str(n)
        # Not 10 digits long?
        if len(s) != 10:
            logger.debug("is_valid_nhs_number: not 10 digits")
            return False

        main_digits = [int(s[i]) for i in range(9)]
        actual_check_digit = int(s[9])  # tenth digit

        # 1. Multiply each of the first nine digits by the corresponding
        #    digit weighting.
        # 2. Sum the results.
        # 3. Take remainder after division by 11.
        remainder = sum([
            d * f
            for (d, f) in zip(main_digits, DIGIT_WEIGHTINGS)
        ]) % 11
        # 4. Subtract the remainder from 11
        expected_check_digit = 11 - remainder
        # 5. If this is 11, use 0 instead
        if expected_check_digit == 11:
            expected_check_digit = 0
        # 6. If it's 10, the number is invalid
        if expected_check_digit == 10:
            logger.debug("is_valid_nhs_number: calculated check digit invalid")
            return False
        # 7. If it doesn't match the check digit, it's invalid
        if expected_check_digit != actual_check_digit:
            logger.debug("is_valid_nhs_number: check digit mismatch")
            return False
        # 8. Hooray!
        return True

    except:
        # Something went wrong.
        logger.debug("is_valid_nhs_number: exception thrown")
        return False


def nhs_number_from_text_or_none(s):
    """Returns a validated NHS number (as an integer) from a string, or None.
    It's a 10-digit number, so note that database 32-bit INT values are
    insufficient; use BIGINT. Python will handle large integers happily.
    NHS number rules:
    http://www.datadictionary.nhs.uk/version2/data_dictionary/
           data_field_notes/n/nhs_number_de.asp?shownav=0
    """
    # None in, None out.
    FUNCNAME = "nhs_number_from_text_or_none: "
    if not s:
        logger.debug(FUNCNAME + "incoming parameter was None")
        return None

    try:
        # (a) If it's not a 10-digit number, bye-bye.

        # Remove whitespace
        s = WHITESPACE_REGEX.sub("", s)  # replaces all instances
        # Contains non-numeric characters?
        if NON_NUMERIC_REGEX.search(s):
            logger.debug(FUNCNAME + "contains non-numeric characters")
            return None
        # Not 10 digits long?
        if len(s) != 10:
            logger.debug(FUNCNAME + "not 10 digits long")
            return None

        # (b) Validation
        n = int(s)
        if not is_valid_nhs_number(n):
            logger.debug(FUNCNAME + "failed validation")
            return None

        # Happy!
        return n

    except:
        logger.debug(FUNCNAME + "exception thrown")
        return None


def generate_random_nhs_number():
    import random
    digits = [random.randint(1, 9)]  # don't start with a zero
    digits.extend([random.randint(0, 9) for x in range(8)])
    check_digit = 11 - (sum([
        d * f
        for (d, f) in zip(digits, DIGIT_WEIGHTINGS)
    ]) % 11)
    if check_digit == 11:
        check_digit = 0
    digits.append(check_digit)
    return int("".join([str(d) for d in digits]))
