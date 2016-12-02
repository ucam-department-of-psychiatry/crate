#!/usr/bin/env python
# crate_anon/nlp_manager/test_all_regex.py

from crate_anon.nlp_manager import (
    all_processors,
    regex_parser,

    parse_biochemistry,
    parse_clinical,
    parse_cognitive,
    parse_haematology,
)


def test_all_regex_nlp() -> None:
    regex_parser.test_all()  # basic regexes
    all_processors.test_all_processors()  # framework classes

    parse_biochemistry.test_all()
    parse_clinical.test_all()
    parse_cognitive.test_all()
    parse_haematology.test_all()


if __name__ == '__main__':
    test_all_regex_nlp()
