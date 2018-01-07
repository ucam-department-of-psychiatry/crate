#!/usr/bin/env python
# crate_anon/anonymise/fetch_wordlists.py

"""
===============================================================================
    Copyright (C) 2015-2018 Rudolf Cardinal (rudolf@pobox.com).

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

See:

    https://stackoverflow.com/questions/1803628/raw-list-of-person-names
    http://www.dicts.info/dictionaries.php
    https://en.wikipedia.org/wiki/Moby_Project

and default URLs in command-line parameters

"""

import argparse
import itertools
import logging
from typing import Generator, Iterable

from cardinal_pythonlib.file_io import (
    gen_files_from_zipfiles,
    gen_lines_from_binary_files,
    gen_lines_from_textfiles,
    gen_lower,
    gen_part_from_iterables,
    gen_part_from_line,
    gen_rows_from_csv_binfiles,
    gen_textfiles_from_filenames,
)
from cardinal_pythonlib.logs import configure_logger_for_colour
from cardinal_pythonlib.network import gen_binary_files_from_urls
import regex
from sortedcontainers import SortedSet

log = logging.getLogger(__name__)


# =============================================================================
# Output
# =============================================================================

def write_words_to_file(filename: str, words: Iterable[str]) -> None:
    log.info("Writing to: {}".format(filename))
    with open(filename, "w") as f:
        for word in words:
            f.write(word + "\n")
    log.info("... finished writing to: {}".format(filename))


# =============================================================================
# Input generators
# =============================================================================

def gen_valid_words_from_lines(
        lines: Iterable[str],
        valid_word_regex_text: str,
        debug: bool = True) -> Generator[str, None, None]:
    valid_word = regex.compile(valid_word_regex_text)
    for line in lines:
        if valid_word.match(line):
            yield line
        elif debug:
            log.debug("Rejecting: {!r}".format(line))


# =============================================================================
# Specifics
# =============================================================================

def fetch_english_words(url: str, filename: str,
                        valid_word_regex_text: str) -> None:
    pipeline = gen_valid_words_from_lines(
        lines=gen_lines_from_binary_files(
            gen_binary_files_from_urls([url])
        ),
        valid_word_regex_text=valid_word_regex_text
    )
    words = list(pipeline)
    words.sort()
    write_words_to_file(filename, words)


def fetch_us_forenames(url: str, filename: str) -> None:
    pipeline = gen_part_from_line(
        lines=gen_lines_from_binary_files(
            gen_files_from_zipfiles(
                gen_binary_files_from_urls([url], on_disk=True),
                # The zip file contains a README and then a bunch of files
                # named yob<year>.txt (e.g. yob1997.txt).
                filespec="*.txt"
            )
        ),
        # Each textfile has lines like "Mary,F,7065".
        splitter=",",
        part_index=0
    )
    names = SortedSet(pipeline)
    write_words_to_file(filename, names)


def fetch_us_surnames(url_1990: str, url_2010: str, filename: str) -> None:
    p1 = gen_part_from_line(
        lines=gen_lines_from_binary_files(
            gen_binary_files_from_urls([url_1990])
        ),
        # Format is e.g. "SMITH          1.006  1.006      1",
        # which is: name, frequency (%), cumulative frequency (%), rank
        part_index=0
    )
    p2 = gen_part_from_iterables(
        iterables=gen_rows_from_csv_binfiles(
            csv_files=gen_files_from_zipfiles(
                gen_binary_files_from_urls([url_2010], on_disk=True),  # a zip
                # The zip file contains a .CSV and a .XLS
                filespec="*.csv",
                on_disk=True,
            ),
            skip_header=True
        ),
        # Each CSV line is like "Mary,F,7065".
        part_index=0
    )
    pipeline = itertools.chain(p1, p2)
    names = SortedSet(pipeline)
    write_words_to_file(filename, names)


def a_not_b(a_filename: str, b_filename: str, output_filename: str) -> None:
    log.info(
        "Finding lines in A={a} that are not in B={b} (in case-insensitive "
        "fashion); writing to OUT={o}".format(
            a=a_filename, b=b_filename, o=output_filename))
    a_count = 0
    output_count = 0
    log.debug("... reading from B")
    exclusion_lines_lower = set(
        gen_lower(
            gen_lines_from_textfiles(
                gen_textfiles_from_filenames([b_filename])
            )
        )
    )
    log.debug("... finished reading from B")
    b_count = len(exclusion_lines_lower)
    log.debug("... reading from A, writing to OUT")
    with open(output_filename, 'w') as outfile:
        with open(a_filename, 'r') as a_file:
            for a_line in a_file:
                a_count += 1
                if a_line.lower() not in exclusion_lines_lower:
                    outfile.write(a_line)
                    output_count += 1
    log.info(
        "... done (line counts: A {a}, B {b}, OUT {o})".format(
            a=a_count, b=b_count, o=output_count))


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help="Be verbose")

    english_group = parser.add_argument_group("English words")
    english_group.add_argument(
        '--english_words', action='store_true',
        help="Fetch English words (for reducing nonspecific blacklist, not as "
             "whitelist; consider words like smith)")
    english_group.add_argument(
        '--english_words_output', type=str, default="english_words.txt",
        help="Output file for English words")
    english_group.add_argument(
        '--english_words_url', type=str,
        default="https://www.gutenberg.org/files/3201/files/SINGLE.TXT",
        help="URL for a textfile containing all English words (will then be "
             "filtered)"
    )
    english_group.add_argument(
        '--valid_word_regex', type=str,
        default=r"^[a-z][A-Za-z'-]+[a-z]$",
        # ... must start with lower-case letter (removes proper nouns)
        # ... must end with letter (removes some prefixes)
        help="Regular expression to determine valid English words"
    )

    us_forename_group = parser.add_argument_group("US forenames")
    us_forename_group.add_argument(
        '--us_forenames', action='store_true',
        help="Fetch US forenames (for blacklist)")
    us_forename_group.add_argument(
        '--us_forenames_url', type=str,
        default="https://www.ssa.gov/OACT/babynames/names.zip",
        help="URL to Zip file of US Census-derived forenames lists (excludes "
             "names with national frequency <5; see "
             "https://www.ssa.gov/OACT/babynames/limits.html)"
    )
    us_forename_group.add_argument(
        '--us_forenames_output', type=str,
        default="us_forenames.txt",
        help="Output file for US forenames")

    us_surname_group = parser.add_argument_group("US surnames")
    us_surname_group.add_argument(
        '--us_surnames', action='store_true',
        help="Fetch US surnames (for blacklist)")
    us_surname_group.add_argument(
        '--us_surnames_output', type=str, default="us_surnames.txt",
        help="Output file for UK surnames")
    us_surname_group.add_argument(
        '--us_surnames_1990_census_url', type=str,
        default="http://www2.census.gov/topics/genealogy/1990surnames/dist.all.last",  # noqa
        help="URL for textfile of US 1990 Census surnames"
    )
    us_surname_group.add_argument(
        '--us_surnames_2010_census_url', type=str,
        default="https://www2.census.gov/topics/genealogy/2010surnames/names.zip",  # noqa
        help="URL for zip of US 2010 Census surnames"
    )

    filter_group = parser.add_argument_group(
        "Filter functions",
        "Extra functions to filter wordlists"
    )
    filter_group.add_argument(
        '--a_not_b', type=str, nargs=3,
        help="In case-insensitive fashion, find lines in file A that are not "
             "in file B and write them to file C. Specimen use: "
             "'--a_not_b us_surnames.txt english_words.txt "
             "filtered_surnames.txt' -- this will produce US surnames that "
             "are not themselves English words.",
        metavar=('A', 'B', 'C'),
    )

    args = parser.parse_args()

    loglevel = logging.DEBUG if args.verbose else logging.INFO
    rootlogger = logging.getLogger()
    configure_logger_for_colour(rootlogger, level=loglevel)

    if args.english_words:
        fetch_english_words(url=args.english_words_url,
                            filename=args.english_words_output,
                            valid_word_regex_text=args.valid_word_regex)

    if args.us_forenames:
        fetch_us_forenames(url=args.us_forenames_url,
                           filename=args.us_forenames_output)

    if args.us_surnames:
        fetch_us_surnames(url_1990=args.us_surnames_1990_census_url,
                          url_2010=args.us_surnames_2010_census_url,
                          filename=args.us_surnames_output)

    if args.a_not_b:
        a_not_b(a_filename=args.a_not_b[0],
                b_filename=args.a_not_b[1],
                output_filename=args.a_not_b[2])


if __name__ == '__main__':
    main()


_TEST_COMMANDS = r"""

~/Documents/code/crate/crate_anon/anonymise/fetch_wordlists.py \
    --english_words --us_forenames --us_surnames

~/Documents/code/crate/crate_anon/anonymise/fetch_wordlists.py \
    --a_not_b us_surnames.txt english_words.txt filtered_surnames.txt

"""
