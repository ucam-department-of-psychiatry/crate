#!/usr/bin/env python
# crate_anon/nlp_manager/test_all_regex.py

import argparse

from crate_anon.nlp_manager import (
    all_processors,
    regex_parser,
    regex_units,
)


def test_all_regex_nlp(verbose: bool = False) -> None:
    regex_parser.test_all(verbose=verbose)  # basic regexes
    regex_units.test_all(verbose=verbose)
    all_processors.test_all_processors(verbose=verbose)
    # ... tests all parser classes


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', '-v', action="store_true", help="Verbose")
    args = parser.parse_args()
    test_all_regex_nlp(verbose=args.verbose)
