#!/usr/bin/python
# -*- encoding: utf8 -*-

"""Miscellaneous mathematical functions

Author: Rudolf Cardinal (rudolf@pobox.com)
Created: June 2013
Last update: 22 Feb 2015

Copyright/licensing:

    Copyright (C) 2013-2015 Rudolf Cardinal (rudolf@pobox.com).

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

# =============================================================================
# Imports
# =============================================================================

import logging
logging.basicConfig()
logger = logging.getLogger("rnc_math")
logger.setLevel(logging.WARNING)
import numpy as np
import sys

# =============================================================================
# Constants
# =============================================================================

DEBUG = True

EQUALS_SEPARATOR = "=" * 79


# =============================================================================
# Softmax
# =============================================================================

def softmax(x, b=1.0):
    # x: vector of values
    # b: exploration parameter, or inverse temperature [Daw2009], or 1/t where:
    # t: temperature (towards infinity: all actions equally likely;
    #       towards zero: probability of action with highest value tends to 1)
    # DO NOT USE TEMPERATURE DIRECTLY: optimizers may take it to zero,
    #       giving an infinity.
    # return value: vector of probabilities
    constant = np.mean(x)
    products = x * b - constant
    # ... softmax is invariant to addition of a constant: Daw article and
    # http://www.faqs.org/faqs/ai-faq/neural-nets/part2/section-12.html#b
    if products.max() > sys.float_info.max_exp:
        # ... max_exp for base e; max_10_exp for base 10
        logger.warn("OVERFLOW in softmax(): x = {}, b = {}, constant = {}, "
                    "x*b - constant = {}".format(x, b, constant, products))
        # map the maximum to 1, other things to zero
        n = len(x)
        index_of_max = np.argmax(products)
        answer = np.zeros(n)
        answer[index_of_max] = 1.0
    else:
        exponented = np.exp(products)
        answer = exponented / np.sum(exponented)
    return answer


# =============================================================================
# Testing
# =============================================================================

if __name__ == '__main__':
    print EQUALS_SEPARATOR
    print "Test softmax"
    print EQUALS_SEPARATOR

    x1 = np.array([1, 2, 3, 4, 5.0**400])
    x2 = np.array([1, 2, 3, 4, 5])
    x3 = np.array([1, 1, 1, 1, 1.01])
    print softmax(x1)
    print softmax(x2)
    print softmax(x3)
    print softmax(x3, b=100.0)
