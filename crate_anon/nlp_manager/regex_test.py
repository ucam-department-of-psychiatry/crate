#!/usr/bin/env python
# crate_anon/nlp_manager/regex_test.py

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

import typing
from typing import List, Tuple
from crate_anon.nlp_manager.regex_func import compile_regex


def f_score(precision: float, recall: float, beta: float = 1) -> float:
    # https://en.wikipedia.org/wiki/F1_score
    beta_sq = beta ** 2
    return (
        (1 + beta_sq) * precision * recall / ((beta_sq * precision) + recall)
    )


def get_compiled_regex_results(compiled_regex: typing.re.Pattern,
                               text: str) -> List[str]:
    results = []
    for m in compiled_regex.finditer(text):
        results.append(m.group(0))
    return results


def print_compiled_regex_results(compiled_regex: typing.re.Pattern, text: str,
                                 prefix_spaces: int = 4) -> None:
    results = get_compiled_regex_results(compiled_regex, text)
    print("{}{} -> {}".format(' ' * prefix_spaces,
                              repr(text), repr(results)))


def test_text_regex(name: str,
                    regex_text: str,
                    test_expected_list: List[Tuple[str, List[str]]],
                    verbose: bool = False) -> None:
    print("Testing regex named {}".format(name))
    compiled_regex = compile_regex(regex_text)
    if verbose:
        print("... regex text:\n{}".format(regex_text))
    for test_string, expected_values in test_expected_list:
        actual_values = get_compiled_regex_results(compiled_regex, test_string)
        assert actual_values == expected_values, (
            "Regex {name}: Expected {expected_values}, got {actual_values}, "
            "when parsing {test_string}. Regex text:\n{regex_text}]".format(
                name=name,
                expected_values=expected_values,
                actual_values=actual_values,
                test_string=repr(test_string),
                regex_text=regex_text,
            )
        )
    print("... OK")
    # print_compiled_regex_results(compiled_regex, text,
    #                              prefix_spaces=prefix_spaces)
