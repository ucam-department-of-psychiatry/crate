#!/usr/bin/env python
# crate_anon/nlp_manager/test_all_regex.py

import argparse

from crate_anon.nlp_manager import (
    all_processors,
    regex_parser,

    parse_biochemistry,
    parse_clinical,
    parse_cognitive,
    parse_haematology,
)


def test_all_regex_nlp(verbose: bool = False) -> None:
    regex_parser.test_all(verbose=verbose)  # basic regexes
    all_processors.test_all_processors()  # framework classes

    parse_biochemistry.test_all()
    parse_clinical.test_all()
    parse_cognitive.test_all()
    parse_haematology.test_all()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', '-v', action="store_true", help="Verbose")
    args = parser.parse_args()
    test_all_regex_nlp(verbose=args.verbose)
