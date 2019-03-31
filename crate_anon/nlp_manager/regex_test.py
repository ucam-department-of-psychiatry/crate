#!/usr/bin/env python

"""
crate_anon/nlp_manager/regex_test.py

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

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

**Regular expression testing.**

"""

from typing import List, Pattern, Tuple
from crate_anon.nlp_manager.regex_func import compile_regex


def f_score(precision: float, recall: float, beta: float = 1) -> float:
    """
    Calculates an F score (e.g. an F1 score for ``beta == 1``).
    See https://en.wikipedia.org/wiki/F1_score.

    Args:
        precision: precision of the test, P(really positive | test positive)
        recall: recall of the test, P(test positive | really positive)
        beta: controls the type of the F score (the relative emphasis on
            precision versus recall)

    Returns:
        the F score

    """
    beta_sq = beta ** 2
    return (
        (1 + beta_sq) * precision * recall / ((beta_sq * precision) + recall)
    )


def get_compiled_regex_results(compiled_regex: Pattern,
                               text: str) -> List[str]:
    """
    Finds all the hits for a regex when applied to text.

    Args:
        compiled_regex: a compiled regular expression
        text: text to parse

    Returns:
        a list of all the (entire) hits for this regex in ``text``

    """
    results = []  # type: List[str]
    for m in compiled_regex.finditer(text):
        results.append(m.group(0))
    return results


def print_compiled_regex_results(compiled_regex: Pattern, text: str,
                                 prefix_spaces: int = 4) -> None:
    """
    Applies a regex to text and prints (to stdout) all its hits.

    Args:
        compiled_regex: a compiled regular expression
        text: text to parse
        prefix_spaces: number of spaces to begin each answer with
    """
    results = get_compiled_regex_results(compiled_regex, text)
    print(f"{' ' * prefix_spaces}{text!r} -> {results!r}")


def test_text_regex(name: str,
                    regex_text: str,
                    test_expected_list: List[Tuple[str, List[str]]],
                    verbose: bool = False) -> None:
    """
    Test a regex upon some text.

    Args:
        name: regex name (for display purposes only)
        regex_text: text that should be compiled to give our regex
        test_expected_list:
            list of tuples ``teststring, expected_results``, where
            ``teststring`` is some text and ``expected_results`` is a list of
            expected hits for the regex within ``teststring``
        verbose: be verbose?

    Returns:

    """
    print(f"Testing regex named {name}")
    compiled_regex = compile_regex(regex_text)
    if verbose:
        print(f"... regex text:\n{regex_text}")
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
