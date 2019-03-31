#!/usr/bin/env python

"""
crate_anon/anonymise/fetch_wordlists.py

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

**Script to fetch wordlists from Internet sources, such as lists of forenames
and surnames.**

See:

- https://stackoverflow.com/questions/1803628/raw-list-of-person-names
- http://www.dicts.info/dictionaries.php

For the Moby project:

- https://en.wikipedia.org/wiki/Moby_Project
- https://www.gutenberg.org/ebooks/3201
- https://www.gutenberg.org/files/3201/3201.txt -- explains other files

and default URLs in command-line parameters

"""

import argparse
import itertools
import logging
from operator import attrgetter
import sys
from typing import Dict, Generator, Iterable, List, Optional, Union

from cardinal_pythonlib.argparse_func import (
    percentage,
    positive_int,
    str2bool,
)
from cardinal_pythonlib.file_io import (
    gen_files_from_zipfiles,
    gen_lines_from_binary_files,
    gen_lines_from_textfiles,
    gen_lower,
    gen_rows_from_csv_binfiles,
    gen_textfiles_from_filenames,
    smart_open,
)
from cardinal_pythonlib.logs import configure_logger_for_colour
from cardinal_pythonlib.network import gen_binary_files_from_urls
import regex
from sortedcontainers import SortedSet

from crate_anon.anonymise.eponyms import get_plain_eponyms

log = logging.getLogger(__name__)


# =============================================================================
# Output
# =============================================================================

def write_words_to_file(filename: str, words: Iterable[str]) -> None:
    """
    Write all the words to a file, one per line.

    Args:
        filename: filename to open (or ``'-'`` for stdout)
        words: iterable of words
    """
    log.info(f"Writing to: {filename}")
    with smart_open(filename, "w") as f:
        for word in words:
            f.write(word + "\n")
    log.info(f"... finished writing to: {filename}")


# =============================================================================
# English words
# =============================================================================

def gen_valid_words_from_words(words: Iterable[str],
                               valid_word_regex_text: str,
                               min_word_length: int = 1,
                               show_rejects: bool = False) -> \
        Generator[str, None, None]:
    """
    Generates valid words from an iterable of words.

    Args:
        words:
            source iterable of words
        valid_word_regex_text:
            regular expression text; every word must match this regex
        min_word_length:
            minimum word length; all words must be at least this long
        show_rejects:
            report rejected words to the Python debug log

    Yields:
        valid words

    """
    valid_word = regex.compile(valid_word_regex_text)
    for word in words:
        if len(word) >= min_word_length and valid_word.match(word):
            yield word
        elif show_rejects:
            log.debug(f"Rejecting word: {word!r}")
            print(word)


def fetch_english_words(url: str, filename: str,
                        valid_word_regex_text: str,
                        min_word_length: int = 1,
                        show_rejects: bool = False) -> None:
    """
    Fetch English words and write them to a file.

    Args:
        url:
            URL to fetch file from
        filename:
            filename to write to
        valid_word_regex_text:
            regular expression text; every word must match this regex
        min_word_length:
            minimum word length; all words must be at least this long
        show_rejects:
            report rejected words to the Python debug log
    """
    pipeline = gen_valid_words_from_words(
        words=gen_lines_from_binary_files(
            gen_binary_files_from_urls([url])
        ),
        valid_word_regex_text=valid_word_regex_text,
        min_word_length=min_word_length,
        show_rejects=show_rejects
    )
    words = list(pipeline)
    words.sort()
    write_words_to_file(filename, words)


# =============================================================================
# Names in general
# =============================================================================

class NameInfo(object):
    """
    Information about a human name.
    """
    def __init__(self, name: str, freq_pct: float = None,
                 cumfreq_pct: float = None) -> None:
        """
        Args:
            name: the name
            freq_pct: frequency (%)
            cumfreq_pct: cumulative frequency (%)
        """
        self.name = name
        self.freq_pct = freq_pct
        self.cumfreq_pct = cumfreq_pct

    def __str__(self) -> str:
        return (
            f"{self.name!r} (freq. {self.freq_pct}%, "
            f"cumulative freq. {self.cumfreq_pct}%)"
        )

    def assert_freq_info(self) -> None:
        """
        Assert that the frequences are reasonable numbers.
        """
        assert (
            isinstance(self.freq_pct, float) and
            isinstance(self.cumfreq_pct, float)
        ), f"Bad frequencies in {self}"


def gen_sufficiently_frequent_names(infolist: Iterable[NameInfo],
                                    min_cumfreq_pct: float = 0,
                                    max_cumfreq_pct: float = 100,
                                    show_rejects: bool = False) -> \
        Generator[NameInfo, None, None]:
    """
    Generate names of a chosen kind of frequency.

    Args:
        infolist:
            iterable of :class:`NameInfo` objects
        min_cumfreq_pct:
            minimum cumulative frequency (%): 0 for no limit, or above 0 to
            exclude common names
        max_cumfreq_pct:
            maximum cumulative frequency (%): 100 for no limit, or below 100 to
            exclude rare names
        show_rejects:
            report rejected words to the Python debug log

    Yields:
        :class:`NameInfo` objects

    """
    assert min_cumfreq_pct <= max_cumfreq_pct
    if min_cumfreq_pct > 0 or max_cumfreq_pct < 100:
        log.info(
            f"Restricting to surnames with "
            f"{min_cumfreq_pct} <= cumfreq_pct <= {max_cumfreq_pct}")
        for info in infolist:
            info.assert_freq_info()
            if min_cumfreq_pct <= info.cumfreq_pct <= max_cumfreq_pct:
                yield info
            elif show_rejects:
                log.debug(f"Rejecting name {info}")
                print(info.name)
    else:
        for info in infolist:
            yield info


def gen_name_from_name_info(infolist: Iterable[NameInfo],
                            min_word_length: int = 1) -> \
        Generator[str, None, None]:
    """
    Generates names from :class:`NameInfo` objects.

    Args:
        infolist:
            iterable of :class:`NameInfo` objects
        min_word_length:
            minimum word length; all words must be at least this long

    Yields:
        names as strings

    """
    for info in infolist:
        if len(info.name) >= min_word_length:
            yield info.name


# =============================================================================
# US forenames
# =============================================================================

class UsForenameInfo(NameInfo):
    """
    Information about a forename in the United States of America.
    """
    def __init__(self, name: str, sex: str, frequency: str) -> None:
        """
        Args:
            name: the name
            sex: the sex, as ``"M"`` or ``"F"``
            frequency: a string version of an integer giving the number of
                times the name appeared in a certain time period
        """
        super().__init__(name)
        self.sex = sex
        self.frequency = int(frequency)


def gen_us_forename_info(lines: Iterable[str]) -> \
        Generator[UsForenameInfo, None, None]:
    """
    Generate US forenames from an iterable of lines in a specific textfile
    format, where each line looks like:

    .. code-block:: none

        Mary,F,7065

    representing name, sex, frequency (count).

    Args:
        lines: iterable of lines

    Yields:
        :class:`UsForenameInfo` objects

    """
    # We need to calculate cumulative frequencies manually.
    # So this needs to accumulate all the instances before yielding any.
    seen = dict()  # type: Dict[str, UsForenameInfo]
    total = 0
    for line in lines:
        # Each textfile has lines like "Mary,F,7065".
        parts = line.split(",")
        info = UsForenameInfo(*parts)
        total += info.frequency
        if info.name in seen:
            seen[info.name].frequency += info.frequency
        else:
            seen[info.name] = info
    # Now sort in descending order of frequency
    log.info(f"Seen names for {total} people")
    infolist = list(seen.values())
    infolist.sort(key=attrgetter('frequency'), reverse=True)
    cumfreq_pct = 0.0
    for info in infolist:
        info.freq_pct = 100.0 * info.frequency / total
        cumfreq_pct += info.freq_pct
        info.cumfreq_pct = cumfreq_pct
        yield info


def fetch_us_forenames(url: str, filename: str,
                       min_cumfreq_pct: float = 0,
                       max_cumfreq_pct: float = 100,
                       min_word_length: int = 1,
                       show_rejects: bool = False) -> None:
    """
    Fetch US forenames and store them in a file, one per line.

    Args:
        url:
            URL to fetch file from
        filename:
            filename to write to
        min_cumfreq_pct:
            minimum cumulative frequency (%): 0 for no limit, or above 0 to
            exclude common names
        max_cumfreq_pct:
            maximum cumulative frequency (%): 100 for no limit, or below 100 to
            exclude rare names
        min_word_length:
            minimum word length; all words must be at least this long
        show_rejects:
            report rejected words to the Python debug log
    """
    pipeline = (
        gen_name_from_name_info(
            gen_sufficiently_frequent_names(
                gen_us_forename_info(
                    gen_lines_from_binary_files(
                        gen_files_from_zipfiles(
                            gen_binary_files_from_urls([url], on_disk=True),
                            # The zip file contains a README and then a bunch
                            # of files named yob<year>.txt (e.g. yob1997.txt).
                            filespec="*.txt"
                        )
                    )
                ),
                min_cumfreq_pct=min_cumfreq_pct,
                max_cumfreq_pct=max_cumfreq_pct,
                show_rejects=show_rejects
            ),
            min_word_length=min_word_length,
        )
    )
    names = SortedSet(pipeline)
    write_words_to_file(filename, names)


# =============================================================================
# US surnames
# =============================================================================

class UsSurname1990Info(NameInfo):
    """
    Represents US surnames from the 1990 census.
    """
    def __init__(self, name: str, freq_pct: str, cumfreq_pct: str,
                 rank: int) -> None:
        """
        Args:
            name: the name
            freq_pct: frequency (%) in string form
            cumfreq_pct: cumulative frequency (%) in string form
            rank: integer rank of frequency, in string form
        """
        super().__init__(name=name,
                         freq_pct=float(freq_pct),
                         cumfreq_pct=float(cumfreq_pct))
        self.rank = int(rank)


def float_or_na_for_us_surnames(x: Union[float, str]) -> Optional[float]:
    """
    The US surname data replaces low-frequency numbers with ``"(S)"`` for
    suppressed. Return a float representation of our input, but convert the
    suppression marker to ``None``.

    Args:
        x: input

    Returns:
        float version of input, or ``None``

    Raises:
        :exc:`ValueError` for bad input

    """
    try:
        return float(x)
    except ValueError:
        if x == "(S)":  # suppressed for small numbers
            return None
        raise ValueError(
            f"Unknown value to float_or_na_for_us_surnames: {x!r}")


class UsSurname2010Info(NameInfo):
    """
    Represents US surnames from the 2010 census.
    """
    def __init__(self, name: str, rank: str, count: str, prop100k: str,
                 cum_prop100k: str, pct_white: str, pct_black: str,
                 pct_api: str, pct_aian: str, pct_2prace: str,
                 pct_hispanic: str) -> None:
        """
        Args:
            name:
                the name
            rank:
                integer rank of frequency, in string form
            count:
                frequency/count of the number of uses nationally
            prop100k:
                "proportion per 100,000 population", in string format, or a
                percentage times 1000
            cum_prop100k:
                cumulative "proportion per 100,000 population" [1]
            pct_white:
                "Percent Non-Hispanic White Alone" [1, 2]
            pct_black:
                "Percent Non-Hispanic Black or African American Alone"  [1, 2]
            pct_api:
                "Percent Non-Hispanic Asian and Native Hawaiian and Other
                Pacific Islander Alone" [1, 2]
            pct_aian:
                "Percent Non-Hispanic American Indian and Alaska Native Alone"
                 [1, 2]
            pct_2prace:
                "Percent Non-Hispanic Two or More Races" [1, 2]
            pct_hispanic:
                "Percent Hispanic or Latino origin" [1, 2]

        [1] will be filtered through :func:`float_or_na_for_us_surnames`.

        [2] these mean "of people with this name, the percentage who are X
        race"
        """
        self.rank = int(rank)
        self.count = int(count)
        self.prop100k = float(prop100k)  # "proportion per 100,000 population"
        # ... by which they mean "number per 100,000 population"
        self.cum_prop100k = float_or_na_for_us_surnames(cum_prop100k)
        self.pct_white = float_or_na_for_us_surnames(pct_white)
        self.pct_black = float_or_na_for_us_surnames(pct_black)
        self.pct_api = float_or_na_for_us_surnames(pct_api)
        self.pct_aian = float_or_na_for_us_surnames(pct_aian)
        self.pct_2prace = float_or_na_for_us_surnames(pct_2prace)
        self.pct_hispanic = float_or_na_for_us_surnames(pct_hispanic)
        # And calculated:
        super().__init__(name,
                         freq_pct=self.prop100k / 1000,
                         cumfreq_pct=self.cum_prop100k / 1000)


def gen_us_surname_1990_info(lines: Iterable[str]) -> \
        Generator[UsSurname1990Info, None, None]:
    """
    Process a series of lines from a textfile and generate US surname
    information from the 1990 census data.
    
    Args:
        lines:
            iterable of lines, with this format:
        
            .. code-block:: none

                # Format is e.g.
                SMITH          1.006  1.006      1
                # which is:
                # name, frequency (%), cumulative frequency (%), rank

    Yields:
        :class:`UsSurname1990Info` objects

    """
    for line in lines:
        parts = line.split()
        yield UsSurname1990Info(*parts)


def gen_us_surname_2010_info(rows: Iterable[Iterable[str]]) -> \
        Generator[UsSurname2010Info, None, None]:
    """
    Process a series of rows and generate US surname information from the 2010
    census data.
    
    Args:
        rows:
            iterable giving "row" objects, where each row is an iterable of
            strings

    Yields:
        :class:`UsSurname2010Info` objects

    """
    for row in rows:
        yield UsSurname2010Info(*row)


def fetch_us_surnames(url_1990: str, url_2010: str, filename: str,
                      min_cumfreq_pct: float = 0,
                      max_cumfreq_pct: float = 100,
                      min_word_length: int = 1,
                      show_rejects: bool = False) -> None:
    """
    Fetches US surnames from the 1990 and 2010 census data. Writes them to a
    file.
    
    Args:
        url_1990:
            URL for 1990 US census data
        url_2010:
            URL for 2010 US census data 
        filename:
            filename to write to
        min_cumfreq_pct:
            minimum cumulative frequency (%): 0 for no limit, or above 0 to
            exclude common names
        max_cumfreq_pct:
            maximum cumulative frequency (%): 100 for no limit, or below 100 to
            exclude rare names
        min_word_length:
            minimum word length; all words must be at least this long
        show_rejects:
            report rejected words to the Python debug log
    """
    p1 = (
        gen_name_from_name_info(
            gen_sufficiently_frequent_names(
                gen_us_surname_1990_info(
                    gen_lines_from_binary_files(
                        gen_binary_files_from_urls([url_1990])
                    )
                ),
                min_cumfreq_pct=min_cumfreq_pct,
                max_cumfreq_pct=max_cumfreq_pct,
                show_rejects=show_rejects
            ),
            min_word_length=min_word_length
        )
    )
    p2 = (
        gen_name_from_name_info(
            gen_sufficiently_frequent_names(
                gen_us_surname_2010_info(
                    gen_rows_from_csv_binfiles(
                        gen_files_from_zipfiles(
                            gen_binary_files_from_urls([url_2010],
                                                       on_disk=True),  # a zip
                            #  The zip file contains a .CSV and a .XLS
                            filespec="*.csv",
                            on_disk=True
                        ),
                        skip_header=True
                    )
                ),
                min_cumfreq_pct=min_cumfreq_pct,
                max_cumfreq_pct=max_cumfreq_pct,
                show_rejects=show_rejects
            ),
            min_word_length=min_word_length
        )
    )
    pipeline = itertools.chain(p1, p2)
    names = SortedSet(pipeline)
    write_words_to_file(filename, names)


# =============================================================================
# Medical eponyms
# =============================================================================

def fetch_eponyms(filename: str, add_unaccented_versions: bool) -> None:
    """
    Writes medical eponyms to a file.
    
    Args:
        filename:
            filename to write to
        add_unaccented_versions:
            Add unaccented (mangled) versions of names, too? For example, do
            you want Sjogren as well as Sjögren?
    """
    names = get_plain_eponyms(add_unaccented_versions=add_unaccented_versions)
    write_words_to_file(filename, names)


# =============================================================================
# File processing: A-not-B
# =============================================================================

def filter_files(input_filenames: List[str],  # "A"
                 exclusion_filenames: List[str],  # "B"
                 output_filename: str,  # "OUT"
                 min_line_length: int = 0) -> None:
    """
    Provides an "A-not-B" file filtering function.
    
    Finds all lines in files defined by ``input_filenames`` (A) that are not
    present in any files defined by ``exclusion_filenames`` (B). Writes them
    to ``output_filename`` (OUT).
    
    Args:
        input_filenames: a list of "A" filenames
        exclusion_filenames: a list of "B" filenames
        output_filename: the "OUT" file
        min_line_length: skip any A lines that are shorter than this value
    """
    # Check inputs
    input_output_overlap = set(input_filenames).intersection(
        set(exclusion_filenames))
    if len(input_output_overlap) > 0:
        raise ValueError(f"Input and exclusion files cannot overlap; "
                         f"overlap is {input_output_overlap}")
        # ... because it's pointless, and/or it's unsafe to use stdin for
        # both A and B
    if output_filename != "-":
        if output_filename in input_filenames:
            raise ValueError("Output cannot be one of the input files")
            # ... would be reading from A whilst writing to OUT
        if output_filename in exclusion_filenames:
            raise ValueError("Output cannot be one of the exclusion files")
            # ... you don't want to overwrite your exclusion file! (Maybe you
            # might want to overwrite A, but our method below reads all of B,
            # then streams A to OUT, which prohibits A and OUT being the same,
            # as above.)
    # Announce intention
    log.info(
        f"Finding lines in A={input_filenames} that are not in "
        f"B={exclusion_filenames} (in case-insensitive fashion); "
        f"writing to OUT={output_filename}")
    # Do it
    a_count = 0
    output_count = 0
    log.debug("... reading from B")
    exclusion_lines_lower = set(
        gen_lower(
            gen_lines_from_textfiles(
                gen_textfiles_from_filenames(exclusion_filenames)
            )
        )
    )
    log.debug("... finished reading from B")
    b_count = len(exclusion_lines_lower)
    log.debug("... reading from A, writing to OUT")
    with smart_open(output_filename, 'w') as outfile:
        for ifilename in input_filenames:
            with smart_open(ifilename, 'r') as a_file:
                for a_line in a_file:
                    a_count += 1
                    if len(a_line) < min_line_length:
                        continue
                    if a_line.lower() in exclusion_lines_lower:
                        continue
                    outfile.write(a_line)
                    output_count += 1
    log.info(f"... done (line counts: A {a_count}, B {b_count}, "
             f"OUT {output_count})")


# =============================================================================
# Main
# =============================================================================

MIN_CUMFREQ_PCT_HELP = (
    "Fetch only names where the cumulative frequency percentage up "
    "to and including this name was at least this value. "
    "Range is 0-100. Use 0 for no limit. Setting this above 0 "
    "excludes COMMON names. (This is a trade-off between being "
    "comprehensive and operating at a reasonable speed. Higher "
    "numbers are more comprehensive but slower.)"
)
MAX_CUMFREQ_PCT_HELP = (
    "Fetch only names where the cumulative frequency percentage up "
    "to and including this name was less than or equal to this "
    "value. "
    "Range is 0-100. Use 100 for no limit. Setting this below 100 "
    "excludes RARE names. (This is a trade-off between being "
    "comprehensive and operating at a reasonable speed. Higher "
    "numbers are more comprehensive but slower.)"
)
SPECIMEN_USAGE = r"""
# -----------------------------------------------------------------------------
# Specimen usage under Linux
# -----------------------------------------------------------------------------

cd ~/Documents/code/crate/working

# Downloading these and then using a file:// URL is unnecessary, but it makes
# the processing steps faster if we need to retry with new settings.
wget https://www.gutenberg.org/files/3201/files/CROSSWD.TXT -O dictionary.txt
wget https://www.ssa.gov/OACT/babynames/names.zip -O forenames.zip
wget http://www2.census.gov/topics/genealogy/1990surnames/dist.all.last -O surnames_1990.txt
wget https://www2.census.gov/topics/genealogy/2010surnames/names.zip -O surnames_2010.zip

crate_fetch_wordlists --help

crate_fetch_wordlists \
    --english_words \
        --english_words_url file://$PWD/dictionary.txt \
    --us_forenames \
        --us_forenames_url file://$PWD/forenames.zip \
        --us_forenames_max_cumfreq_pct 100 \
    --us_surnames \
        --us_surnames_1990_census_url file://$PWD/surnames_1990.txt \
        --us_surnames_2010_census_url file://$PWD/surnames_2010.zip \
        --us_surnames_max_cumfreq_pct 100 \
    --eponyms

#    --show_rejects \
#    --verbose

# Forenames encompassing the top 95% gives 5874 forenames (of 96174).
# Surnames encompassing the top 85% gives 74525 surnames (of 175880).

crate_fetch_wordlists \
    --filter_input \
        us_forenames.txt \
        us_surnames.txt \
    --filter_exclude \
        english_words.txt \
        medical_eponyms.txt \
    --filter_output \
        filtered_names.txt

"""  # noqa


def main() -> None:
    """
    Command-line processor. See command-line help.
    """
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '--specimen', action='store_true',
        help="Show some specimen usages and exit"
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help="Be verbose")
    parser.add_argument(
        '--min_word_length', type=positive_int, default=2,
        help="Minimum word length to allow"
    )
    parser.add_argument(
        '--show_rejects', action='store_true',
        help="Print to stdout (and, in verbose mode, log) the words being "
             "rejected"
    )

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
        # default="https://www.gutenberg.org/files/3201/files/SINGLE.TXT",
        # ... contains all sorts of names like "cheung"
        default="https://www.gutenberg.org/files/3201/files/CROSSWD.TXT",
        # ... much better; all possible Scrabble words
        help="URL for a textfile containing all English words (will then be "
             "filtered)"
    )
    english_group.add_argument(
        '--valid_word_regex', type=str,
        default=r"^[a-z](?:[A-Za-z'-]*[a-z])*$",
        # ... must start with lower-case letter (removes proper nouns and some
        #     abbreviations like "'twas")
        # ... restrict content to letters/apostrophe/hyphen (removes e.g. "&c",
        #     "c/o")
        # ... must end with letter (removes some prefixes)
        help="Regular expression to determine valid English words"
    )

    us_forename_group = parser.add_argument_group("US forenames")
    us_forename_group.add_argument(
        '--us_forenames', action='store_true',
        help="Fetch US forenames (for blacklist)"
    )
    us_forename_group.add_argument(
        '--us_forenames_url', type=str,
        default="https://www.ssa.gov/OACT/babynames/names.zip",
        help="URL to Zip file of US Census-derived forenames lists (excludes "
             "names with national frequency <5; see "
             "https://www.ssa.gov/OACT/babynames/limits.html)"
    )
    us_forename_group.add_argument(
        '--us_forenames_min_cumfreq_pct', type=percentage, default=0,
        help=MIN_CUMFREQ_PCT_HELP
    )
    us_forename_group.add_argument(
        '--us_forenames_max_cumfreq_pct', type=percentage, default=100,
        help=MAX_CUMFREQ_PCT_HELP
    )
    us_forename_group.add_argument(
        '--us_forenames_output', type=str,
        default="us_forenames.txt",
        help="Output file for US forenames"
    )

    us_surname_group = parser.add_argument_group("US surnames")
    us_surname_group.add_argument(
        '--us_surnames', action='store_true',
        help="Fetch US surnames (for blacklist)"
    )
    us_surname_group.add_argument(
        '--us_surnames_output', type=str, default="us_surnames.txt",
        help="Output file for UK surnames"
    )
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
    us_surname_group.add_argument(
        '--us_surnames_min_cumfreq_pct', type=percentage, default=0,
        help=MIN_CUMFREQ_PCT_HELP
    )
    us_surname_group.add_argument(
        '--us_surnames_max_cumfreq_pct', type=percentage, default=100,
        help=MAX_CUMFREQ_PCT_HELP
    )

    eponyms_group = parser.add_argument_group("Medical eponyms")
    eponyms_group.add_argument(
        '--eponyms', action='store_true',
        help="Write medical eponyms (to remove from blacklist)"
    )
    eponyms_group.add_argument(
        '--eponyms_output', type=str, default="medical_eponyms.txt",
        help="Output file for medical eponyms"
    )
    eponyms_group.add_argument(
        '--eponyms_add_unaccented_versions', type=str2bool, nargs='?',
        const=True, default=True,
        help="Add unaccented versions (e.g. Sjogren as well as Sjögren)"
    )

    filter_group = parser.add_argument_group(
        "Filter functions",
        "Extra functions to filter wordlists. Specify an input file (or "
        "files), whose lines will be included; optional exclusion file(s), "
        "whose lines will be excluded (in case-insensitive fashion); and an "
        "output file. You can use '-' for the output file to mean 'stdout', "
        "and for one input file to mean 'stdin'. No filenames (other than "
        "'-' for input and output) may overlap. The --min_line_length option "
        "also applies. Duplicates are not removed."
    )
    filter_group.add_argument(
        '--filter_input', type=str, nargs='*',
        help="Input file(s). See above.",
    )
    filter_group.add_argument(
        '--filter_exclude', type=str, nargs='*',
        help="Exclusion file(s). See above.",
    )
    filter_group.add_argument(
        '--filter_output', type=str, nargs='?',
        help="Exclusion file(s). See above.",
    )
    args = parser.parse_args()

    if bool(args.filter_input) != bool(args.filter_output):
        print("Specify both --filter_input and --filter_output, or none.")
        parser.print_usage()
        sys.exit(1)

    loglevel = logging.DEBUG if args.verbose else logging.INFO
    rootlogger = logging.getLogger()
    configure_logger_for_colour(rootlogger, level=loglevel)

    if args.specimen:
        print(SPECIMEN_USAGE)
        sys.exit(0)

    if args.min_word_length > 1:
        log.info(f"Restricting to words of length >= {args.min_word_length}")

    if args.english_words:
        fetch_english_words(url=args.english_words_url,
                            filename=args.english_words_output,
                            valid_word_regex_text=args.valid_word_regex,
                            min_word_length=args.min_word_length,
                            show_rejects=args.show_rejects)

    if args.us_forenames:
        fetch_us_forenames(url=args.us_forenames_url,
                           filename=args.us_forenames_output,
                           min_cumfreq_pct=args.us_forenames_min_cumfreq_pct,
                           max_cumfreq_pct=args.us_forenames_max_cumfreq_pct,
                           min_word_length=args.min_word_length,
                           show_rejects=args.show_rejects)

    if args.us_surnames:
        fetch_us_surnames(url_1990=args.us_surnames_1990_census_url,
                          url_2010=args.us_surnames_2010_census_url,
                          filename=args.us_surnames_output,
                          min_cumfreq_pct=args.us_surnames_min_cumfreq_pct,
                          max_cumfreq_pct=args.us_surnames_max_cumfreq_pct,
                          min_word_length=args.min_word_length,
                          show_rejects=args.show_rejects)

    if args.eponyms:
        fetch_eponyms(
            filename=args.eponyms_output,
            add_unaccented_versions=args.eponyms_add_unaccented_versions)

    if args.filter_input:
        filter_files(input_filenames=args.filter_input,
                     exclusion_filenames=args.filter_exclude,
                     output_filename=args.filter_output,
                     min_line_length=args.min_word_length)


if __name__ == '__main__':
    main()
