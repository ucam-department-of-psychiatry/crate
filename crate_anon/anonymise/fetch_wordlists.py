#!/usr/bin/env python

# noinspection HttpUrlsUsage
"""
crate_anon/anonymise/fetch_wordlists.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

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
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

**Script to fetch wordlists from Internet sources, such as lists of forenames,
surnames, and English words.**

For specimen usage: see ancillary.rst, as :ref:`crate_fetch_wordlists
<crate_fetch_wordlists>`.

See:

- https://stackoverflow.com/questions/1803628/raw-list-of-person-names
- https://www.dicts.info/dictionaries.php

For the Moby project (word lists):

- https://en.wikipedia.org/wiki/Moby_Project
- https://www.gutenberg.org/ebooks/3201 (Moby word lists)
- https://www.gutenberg.org/files/3201/3201.txt -- explains other files

and default URLs in command-line parameters. The "crossword" file is good.
However, for frequency information this is a bit sparse (it contains the top
1000 words in various contexts).

Broader corpora with frequencies include:

- Google Books Ngrams,
  https://storage.googleapis.com/books/ngrams/books/datasetsv2.html, where
  "1-grams" means individual words. However, it's large (e.g. the "A" file is
  1.7 Gb), it's split by year, and it has a lot of non-word entities like
  "Amood_ADJ" and "→_ADJ".
- Wikipedia, e.g. https://en.wiktionary.org/wiki/Wiktionary:Frequency_lists,
  but it doesn't seem to have formats oriented to automatic processing.
- British National Corpus,
  http://www.natcorp.ox.ac.uk/corpus/index.xml?ID=intro (but not freely
  distributable).
- Non-free ones, e.g. COCA, https://www.wordfrequency.info/.
- A "frozen" version of the Standardized Project Gutenberg Corpus (SPGC),
  https://doi.org/10.5281/zenodo.2422561 and
  https://github.com/pgcorpus/gutenberg.

For the SPGC, notations like "PG74" refer to books (e.g. PG74 is "The
Adventures of Tom Sawyer"); these are listed in the metadata file. Overall,
the SPGC looks pretty good but one downside is that the SPGC software forces
all words to lower case. See:

- process_data -- calls process_book()
- src.pipeline.process_book -- calls tokenize_text() via "tokenize_f"
- src.tokenizer.tokenize_text -- calls filter_tokens()
- src.tokenizer.filter_tokens -- forces everything to lower-case.

and thus the output contains e.g. "ellen", "james", "jamestown", josephine",
"mary". Cross-referencing to our Scrabble/crossword list will remove some, but
it will retain the problem that "john" (a rare-ish word but a common name) has
its frequency overestimated.

For API access to Project Gutenberg:

- https://www.gutenberg.org/policy/robot_access.html
-
- https://github.com/raduangelescu/gutenbergpy

"""

import argparse
from collections import Counter
import csv
import itertools
import logging
from operator import attrgetter
import sys
from typing import (
    BinaryIO,
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    Set,
    Tuple,
    Union,
)

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
from gutenbergpy.textget import get_text_by_id, strip_headers
import regex
from rich_argparse import ArgumentDefaultsRichHelpFormatter
from sortedcontainers import SortedSet

from crate_anon.anonymise.eponyms import get_plain_eponyms

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

# For "normal" English word filtering from a dictionary file:
DEFAULT_VALID_WORD_REGEX = r"^[a-z](?:[A-Za-z'-]*[a-z])*$"
# - Must start with lower-case letter (removes proper nouns and some
#   abbreviations like "'twas").
# - Restrict content to letters/apostrophe/hyphen (removes e.g. "&c", "c/o").
# - Must end with letter (removes some prefixes).


# =============================================================================
# Output
# =============================================================================


def write_words_to_file(filename: str, words: Iterable[str]) -> None:
    """
    Write all the words to a file, one per line.

    Args:
        filename:
            Filename to open (or ``'-'`` for stdout).
        words:
            Iterable of words.
    """
    log.info(f"Writing to: {filename}")
    with smart_open(filename, "w") as f:
        for word in words:
            f.write(word + "\n")
    log.info(f"... finished writing to: {filename}")


# =============================================================================
# English words: simple dictionary
# =============================================================================


def gen_lines_from_binary_files_with_maxfiles(
    files: Iterable[BinaryIO], encoding: str = "utf8", max_files: int = None
) -> Generator[str, None, None]:
    """
    Generates lines from binary files.
    Strips out newlines.

    Args:
        files: iterable of :class:`BinaryIO` file-like objects
        encoding: encoding to use
        max_files: maximum number of files to read

    Yields:
        each line of all the files

    """
    for n, file in enumerate(files, start=1):
        for byteline in file:
            line = byteline.decode(encoding).strip()
            yield line
        if max_files is not None and n >= max_files:
            log.info(f"Stopping at {max_files} files")
            return


def gen_valid_words_from_words(
    words: Iterable[str],
    valid_word_regex_text: str,
    min_word_length: int = 1,
    show_rejects: bool = False,
) -> Generator[str, None, None]:
    """
    Generates valid words from an iterable of words.

    Args:
        words:
            Source iterable of words.
        valid_word_regex_text:
            Regular expression text; every word must match this regex.
        min_word_length:
            Minimum word length; all words must be at least this long.
        show_rejects:
            Report rejected words to the Python debug log.

    Yields:
        Valid words.

    """
    valid_word = regex.compile(valid_word_regex_text)
    for word in words:
        if len(word) >= min_word_length and valid_word.match(word):
            yield word
        elif show_rejects:
            log.debug(f"Rejecting word: {word!r}")


def fetch_english_words(
    url: str,
    filename: str = "",
    valid_word_regex_text: str = DEFAULT_VALID_WORD_REGEX,
    min_word_length: int = 1,
    show_rejects: bool = False,
) -> None:
    """
    Fetch English words and write them to a file.

    Args:
        url:
            URL to fetch file from.
        filename:
            Filename to write to.
        valid_word_regex_text:
            Regular expression text; every word must match this regex.
        min_word_length:
            Minimum word length; all words must be at least this long.
        show_rejects:
            Report rejected words to the Python debug log.
    """
    if not filename:
        log.warning("No output filename specified for English words. Skipping")
    pipeline = gen_valid_words_from_words(
        words=gen_lines_from_binary_files(gen_binary_files_from_urls([url])),
        valid_word_regex_text=valid_word_regex_text,
        min_word_length=min_word_length,
        show_rejects=show_rejects,
    )
    words = list(pipeline)
    words.sort()
    write_words_to_file(filename, words)


# =============================================================================
# English words: frequency, from Project Gutenberg books
# =============================================================================


def gen_words_from_gutenberg_ids(
    gutenberg_ids: Iterable[int],
    valid_word_regex_text: str,
    min_word_length: int = 1,
) -> Generator[str, None, None]:
    """
    Generates words from Project Gutenberg books. Does not alter case.

    Args:
        gutenberg_ids:
            Project Gutenberg IDs; e.g. 74 is Tom Sawyer, 100 is the complete
            works of Shakespeare.
        valid_word_regex_text:
            Regular expression text; every word must match this regex.
        min_word_length:
            Minimum word length; all words must be at least this long.

    Yields:
        words

    """
    valid_word = regex.compile(valid_word_regex_text)
    for gutenberg_id in gutenberg_ids:
        log.info(f"Reading Project Gutenberg book {gutenberg_id}...")
        raw_book = get_text_by_id(gutenberg_id)
        log.info("... done; processing...")
        text = strip_headers(raw_book).decode("utf8")
        n = 0
        for line in text.split("\n"):
            for word in line.split():
                if len(word) >= min_word_length and valid_word.match(word):
                    yield word
                    n += 1
        log.info(f"... yielded {n} words")


def gen_word_freq_tuples_from_words(
    words: Iterable[str],
) -> Generator[Tuple[str, float], None, None]:
    """
    Generates valid words and their frequencies from an iterable of SPGC count
    lines.

    Args:
        words:
            Source iterable of words

    Yields:
        (word, count, word_freq, cum_freq) tuples, sorted by frequency
        (ascending).
    """
    c = Counter(words)
    total = sum(c.values())  # from Python 3.10: tc.total()
    log.info(f"Calculating word frequencies across {total} words...")
    cum_freq = 0.0
    # Sort by frequency, from high to low frequency, with word
    # (alphabetical order) as a tiebreaker.
    for word, count in sorted(c.items(), key=lambda x: (-x[1], x[0])):
        word_freq = count / total
        cum_freq += word_freq
        yield word, count, word_freq, cum_freq
    log.info("... done")


KEY_WORD = "word"
KEY_WORD_FREQ = "word_freq"
KEY_CUM_FREQ = "cum_freq"


def fetch_gutenberg_word_freq(
    filename: str = "",
    gutenberg_id_first: int = 1,
    gutenberg_id_last: int = 100,
    valid_word_regex_text: str = DEFAULT_VALID_WORD_REGEX,
    min_word_length: int = 1,
) -> None:
    """
    Fetch English word frequencies from a frozen Standardized Project Gutenberg
    Corpus, and write them to a file. Within the words selected (which might be
    e.g. words of at least 2 characters, per min_word_length, and excluding
    words starting with upper-case letters or containing unusual punctuationg,
    per valid_word_regex_text), it produces a CSV file whose columns are: word,
    word_freq, cum_freq.

    Args:
        filename:
            Filename to write to.
        gutenberg_id_first:
            First book ID to use from Project Gutenberg.
        gutenberg_id_last:
            Last book ID to use from Project Gutenberg.
        valid_word_regex_text:
            Regular expression text; every word must match this regex.
        min_word_length:
            Minimum word length; all words must be at least this long.
    """
    if not filename:
        log.warning("No output filename specified for frequencies. Skipping")
        return
    pipeline = gen_word_freq_tuples_from_words(
        gen_words_from_gutenberg_ids(
            range(gutenberg_id_first, gutenberg_id_last + 1),
            valid_word_regex_text=valid_word_regex_text,
            min_word_length=min_word_length,
        )
    )
    with open(filename, "wt") as f:
        writer = csv.writer(f)
        writer.writerow([KEY_WORD, KEY_WORD_FREQ, KEY_CUM_FREQ])
        for word, _, word_freq, cum_freq in pipeline:
            writer.writerow((word, word_freq, cum_freq))


def filter_words_by_freq(
    input_filename: str,
    output_filename: str,
    min_cum_freq: float = 0.0,
    max_cum_freq: float = 1.0,
) -> None:
    """
    Reads words from our frequency file and filters them.

    Args:
        input_filename:
            Input CSV file. The output of fetch_gutenberg_word_freq().
        output_filename:
            A plain output file, sorted.
        min_cum_freq:
            Minimum cumulative frequency. Set to >0 to exclude common words.
        max_cum_freq:
            Maximum cumulative frequency. Set to <1 to exclude rare words.
    """
    assert 0.0 <= min_cum_freq <= max_cum_freq <= 1.0
    words = set()  # type: Set[str]
    log.info(f"Reading {input_filename}...")
    with open(input_filename) as i:
        reader = csv.DictReader(
            i, fieldnames=[KEY_WORD, KEY_WORD_FREQ, KEY_CUM_FREQ]
        )
        for rowdict in reader:
            try:
                cum_freq = float(rowdict[KEY_CUM_FREQ])
            except (TypeError, ValueError):
                log.warning(f"Bad row: {rowdict!r}")
                continue
            if min_cum_freq <= cum_freq <= max_cum_freq:
                words.add(rowdict[KEY_WORD])
    log.info(f"Writing {output_filename}...")
    with open(output_filename, "wt") as o:
        for word in sorted(words):
            o.write(word + "\n")
    log.info("... done")


# =============================================================================
# Names in general
# =============================================================================


class NameInfo:
    """
    Information about a human name.
    """

    def __init__(
        self, name: str, freq_pct: float = None, cumfreq_pct: float = None
    ) -> None:
        """
        Args:
            name:
                The name.
            freq_pct:
                Frequency (%).
            cumfreq_pct:
                Cumulative frequency (%) when names are ordered from most to
                least common; therefore, close to 0 for common names, and close
                to 100 for rare names.

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
        assert isinstance(self.freq_pct, float) and isinstance(
            self.cumfreq_pct, float
        ), f"Bad frequencies in {self}"

    @property
    def freq_p(self) -> float:
        """
        Frequency as a probability or proportion, range [0, 1].
        """
        return self.freq_pct / 100


def gen_sufficiently_frequent_names(
    infolist: Iterable[NameInfo],
    min_cumfreq_pct: float = 0,
    max_cumfreq_pct: float = 100,
    show_rejects: bool = False,
    debug_names: List[str] = None,
) -> Generator[NameInfo, None, None]:
    """
    Generate names of a chosen kind of frequency.

    Args:
        infolist:
            Iterable of :class:`NameInfo` objects.
        min_cumfreq_pct:
            Minimum cumulative frequency (%): 0 for no limit, or above 0 to
            exclude common names.
        max_cumfreq_pct:
            Maximum cumulative frequency (%): 100 for no limit, or below 100 to
            exclude rare names.
        show_rejects:
            Report rejected words to the Python debug log.
        debug_names:
            Names to show extra information about (e.g. to discover the right
            thresholds).

    Yields:
        :class:`NameInfo` objects

    """
    debug_names = debug_names or []  # type: List[str]
    debug_names = [x.upper() for x in debug_names]
    assert min_cumfreq_pct <= max_cumfreq_pct
    if min_cumfreq_pct > 0 or max_cumfreq_pct < 100:
        log.info(
            f"Restricting to surnames with "
            f"{min_cumfreq_pct} <= cumfreq_pct <= {max_cumfreq_pct}"
        )
        for info in infolist:
            info.assert_freq_info()
            if info.name.upper() in debug_names:
                log.warning(info)
            if min_cumfreq_pct <= info.cumfreq_pct <= max_cumfreq_pct:
                yield info
            elif show_rejects:
                log.debug(f"Rejecting name {info}")
                print(info.name)
    else:
        for info in infolist:
            yield info


def gen_name_info_via_min_length(
    info_iter: Iterable[NameInfo], min_name_length: int = 1
) -> Generator[NameInfo, None, None]:
    """
    Generates :class:`NameInfo` objects matching a name length criterion.

    Args:
        info_iter:
            Iterable of :class:`NameInfo` objects.
        min_name_length:
            Minimum name length; all names must be at least this long.

    Yields:
        Names as strings.

    """
    for info in info_iter:
        if len(info.name) >= min_name_length:
            yield info


def gen_name_from_name_info(
    info_iter: Iterable[NameInfo],
) -> Generator[str, None, None]:
    """
    Generates names from :class:`NameInfo` objects.

    Args:
        info_iter:
            Iterable of :class:`NameInfo` objects.

    Yields:
        Names as strings.

    """
    for info in info_iter:
        yield info.name


# =============================================================================
# US forenames
# =============================================================================


class UsForenameInfo(NameInfo):
    """
    Information about a forename in the United States of America.
    """

    def __init__(self, name: str, sex: str, count: str) -> None:
        """
        Args:
            name:
                The name.
            sex:
                The sex, as ``"M"`` or ``"F"``.
            count:
                A string version of an integer, giving the number of times the
                name appeared in a certain time period.
        """
        super().__init__(name)
        self.sex = sex
        self.count = int(count)


def gen_us_forename_info(
    lines: Iterable[str],
) -> Generator[UsForenameInfo, None, None]:
    """
    Generate US forenames from an iterable of lines in a specific textfile
    format, where each line looks like:

    .. code-block:: none

        Mary,F,7065

    representing name, sex, frequency (count).

    Args:
        lines:
            Iterable of lines.

    Yields:
        :class:`UsForenameInfo` objects, one per name, with frequency
        information added.

    """
    # We need to calculate cumulative frequencies manually.
    # So this needs to accumulate all the instances before yielding any.
    seen = dict()  # type: Dict[str, UsForenameInfo]
    total = 0  # number of people seen
    for line in lines:
        # Each textfile has lines like "Mary,F,7065".
        parts = line.split(",")
        info = UsForenameInfo(*parts)
        total += info.count
        if info.name in seen:
            seen[info.name].count += info.count
        else:
            seen[info.name] = info
    # Now sort in descending order of frequency
    log.info(f"Seen names for {total} people")
    infolist = list(seen.values())
    infolist.sort(key=attrgetter("count"), reverse=True)
    cumfreq_pct = 0.0
    for info in infolist:
        info.freq_pct = 100.0 * info.count / total
        cumfreq_pct += info.freq_pct
        info.cumfreq_pct = cumfreq_pct
        yield info


def gen_us_forename_info_by_sex(
    lines: Iterable[str],
) -> Generator[UsForenameInfo, None, None]:
    """
    Generate US forenames from an iterable of lines in a specific textfile
    format, where each line looks like:

    .. code-block:: none

        Mary,F,7065

    representing name, sex, frequency (count).

    Args:
        lines:
            Iterable of lines.

    Yields:
        :class:`UsForenameInfo` objects, one per name/sex combination present,
        with frequency information added.

    """
    # We need to calculate cumulative frequencies manually.
    # So this needs to accumulate all the instances before yielding any.
    male_seen = dict()  # type: Dict[str, UsForenameInfo]
    female_seen = dict()  # type: Dict[str, UsForenameInfo]
    male_total = 0  # number of males seen
    female_total = 0  # number of females seen
    for line in lines:
        # Each textfile has lines like "Mary,F,7065".
        parts = line.split(",")
        info = UsForenameInfo(*parts)
        name = info.name
        sex = info.sex
        if sex == "M":
            male_total += info.count
            if name in male_seen:
                male_seen[name].count += info.count
            else:
                male_seen[name] = info
        elif sex == "F":
            female_total += info.count
            if name in female_seen:
                female_seen[name].count += info.count
            else:
                female_seen[name] = info
        else:
            raise ValueError(f"Unknown sex: {sex}")

    # Now sort in descending order of frequency
    log.info(f"Seen names for {male_total} males, {female_total} females")

    male_infolist = list(male_seen.values())
    male_infolist.sort(key=attrgetter("count"), reverse=True)
    male_cumfreq_pct = 0.0
    for info in male_infolist:
        info.freq_pct = 100.0 * info.count / male_total
        male_cumfreq_pct += info.freq_pct
        info.cumfreq_pct = male_cumfreq_pct
        yield info

    female_infolist = list(female_seen.values())
    female_infolist.sort(key=attrgetter("count"), reverse=True)
    female_cumfreq_pct = 0.0
    for info in female_infolist:
        info.freq_pct = 100.0 * info.count / female_total
        female_cumfreq_pct += info.freq_pct
        info.cumfreq_pct = female_cumfreq_pct
        yield info


def fetch_us_forenames(
    url: str,
    filename: str = "",
    freq_csv_filename: str = "",
    freq_sex_csv_filename: str = "",
    min_cumfreq_pct: float = 0,
    max_cumfreq_pct: float = 100,
    min_name_length: int = 1,
    show_rejects: bool = False,
    debug_names: List[str] = None,
) -> None:
    """
    Fetch US forenames and store them in a file, one per line.

    Args:
        url:
            URL to fetch file from.
        filename:
            Filename to write names to.
        freq_csv_filename:
            Optional CSV to write "name, frequency" pairs to, one name per
            line.
        freq_sex_csv_filename:
            Optional CSV to write "name, gender, frequency" rows to.
        min_cumfreq_pct:
            Minimum cumulative frequency (%): 0 for no limit, or above 0 to
            exclude common names.
        max_cumfreq_pct:
            Maximum cumulative frequency (%): 100 for no limit, or below 100 to
            exclude rare names.
        min_name_length:
            Minimum word length; all words must be at least this long.
        show_rejects:
            Report rejected words to the Python debug log.
        debug_names:
            Names to show extra information about (e.g. to discover the right
            thresholds).
    """
    if not filename and not freq_csv_filename and not freq_sex_csv_filename:
        log.warning(
            "No output filenames specified for US forenames. Skipping."
        )
        return

    # -------------------------------------------------------------------------
    # Ignoring sex
    # -------------------------------------------------------------------------
    if filename or freq_csv_filename:
        # 1. Read
        pipeline = gen_name_info_via_min_length(
            gen_sufficiently_frequent_names(
                gen_us_forename_info(
                    gen_lines_from_binary_files(
                        gen_files_from_zipfiles(
                            gen_binary_files_from_urls([url], on_disk=True),
                            # The zip file contains a README and then a
                            # bunch of files named yob<year>.txt (e.g.
                            # yob1997.txt).
                            filespec="*.txt",
                        )
                    )
                ),
                min_cumfreq_pct=min_cumfreq_pct,
                max_cumfreq_pct=max_cumfreq_pct,
                show_rejects=show_rejects,
                debug_names=debug_names,
            ),
            min_name_length=min_name_length,
        )
        # 2. Build
        names = SortedSet()
        freq = {}  # type: Dict[str, float]
        for nameinfo in pipeline:
            name = nameinfo.name
            if name not in names:
                names.add(name)
                freq[name] = nameinfo.freq_p

        # 3. Write
        # (a) without frequency
        if filename:
            write_words_to_file(filename, names)

        # (b) with frequency
        if freq_csv_filename:
            log.info(f"Writing to: {freq_csv_filename}")
            with open(freq_csv_filename, "wt") as f:
                csvwriter = csv.writer(f)
                for name in names:
                    csvwriter.writerow([name, freq[name]])
            log.info(f"... finished writing to: {freq_csv_filename}")

    # -------------------------------------------------------------------------
    # By sex
    # -------------------------------------------------------------------------
    if freq_sex_csv_filename:
        # 1. Read
        pipeline_by_sex = (
            # As above, but by sex
            gen_name_info_via_min_length(
                gen_sufficiently_frequent_names(
                    gen_us_forename_info_by_sex(
                        gen_lines_from_binary_files(
                            gen_files_from_zipfiles(
                                gen_binary_files_from_urls(
                                    [url], on_disk=True
                                ),
                                filespec="*.txt",
                            )
                        )
                    ),
                    min_cumfreq_pct=min_cumfreq_pct,
                    max_cumfreq_pct=max_cumfreq_pct,
                    show_rejects=show_rejects,
                ),
                min_name_length=min_name_length,
            )
        )
        # 2. Build
        name_sex_pairs = SortedSet()
        sexfreq = {}  # type: Dict[Tuple[str, str], float]
        for nameinfo in pipeline_by_sex:  # type: UsForenameInfo
            name = nameinfo.name
            sex = nameinfo.sex
            name_sex = name, sex
            if name_sex not in name_sex_pairs:
                name_sex_pairs.add(name_sex)
                sexfreq[name_sex] = nameinfo.freq_p
        # 3. Write
        log.info(f"Writing to: {freq_sex_csv_filename}")
        with open(freq_sex_csv_filename, "wt") as f:
            csvwriter = csv.writer(f)
            for name_sex in name_sex_pairs:
                csvwriter.writerow(
                    [name_sex[0], name_sex[1], sexfreq[name_sex]]
                )
        log.info(f"... finished writing to: {freq_sex_csv_filename}")


# =============================================================================
# US surnames
# =============================================================================


class UsSurname1990Info(NameInfo):
    """
    Represents US surnames from the 1990 census.
    """

    def __init__(
        self, name: str, freq_pct: str, cumfreq_pct: str, rank: int
    ) -> None:
        """
        Args:
            name:
                The name.
            freq_pct:
                Frequency (%) in string form.
            cumfreq_pct:
                Cumulative frequency (%) in string form.
            rank:
                Integer rank of frequency, in string form.
        """
        super().__init__(
            name=name, freq_pct=float(freq_pct), cumfreq_pct=float(cumfreq_pct)
        )
        self.rank = int(rank)


def float_or_na_for_us_surnames(x: Union[float, str]) -> Optional[float]:
    """
    The US surname data replaces low-frequency numbers with ``"(S)"`` for
    suppressed. Return a float representation of our input, but convert the
    suppression marker to ``None``.

    Args:
        x:
            Input.

    Returns:
        Float version of input, or ``None``.

    Raises:
        :exc:`ValueError` for bad input.

    """
    try:
        return float(x)
    except ValueError:
        if x == "(S)":  # suppressed for small numbers
            return None
        raise ValueError(
            f"Unknown value to float_or_na_for_us_surnames: {x!r}"
        )


class UsSurname2010Info(NameInfo):
    """
    Represents US surnames from the 2010 census.
    """

    def __init__(
        self,
        name: str,
        rank: str,
        count: str,
        prop100k: str,
        cum_prop100k: str,
        pct_white: str,
        pct_black: str,
        pct_api: str,
        pct_aian: str,
        pct_2prace: str,
        pct_hispanic: str,
    ) -> None:
        """
        Args:
            name:
                The name.
            rank:
                Integer rank of frequency, in string form.
            count:
                Frequency/count of the number of uses nationally.
            prop100k:
                "Proportion per 100,000 population", in string format, or a
                percentage times 1000.
            cum_prop100k:
                Cumulative "proportion per 100,000 population" [1].
            pct_white:
                "Percent Non-Hispanic White Alone" [1, 2].
            pct_black:
                "Percent Non-Hispanic Black or African American Alone" [1, 2].
            pct_api:
                "Percent Non-Hispanic Asian and Native Hawaiian and Other
                Pacific Islander Alone" [1, 2].
            pct_aian:
                "Percent Non-Hispanic American Indian and Alaska Native Alone"
                 [1, 2].
            pct_2prace:
                "Percent Non-Hispanic Two or More Races" [1, 2].
            pct_hispanic:
                "Percent Hispanic or Latino origin" [1, 2].

        [1] These will be filtered through :func:`float_or_na_for_us_surnames`.

        [2] These mean "of people with this name, the percentage who are X
        race".
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
        super().__init__(
            name,
            freq_pct=self.prop100k / 1000,
            cumfreq_pct=self.cum_prop100k / 1000,
        )


def gen_us_surname_1990_info(
    lines: Iterable[str],
) -> Generator[UsSurname1990Info, None, None]:
    """
    Process a series of lines from a textfile and generate US surname
    information from the 1990 census data.

    Args:
        lines:
            Iterable of lines, with this format:

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


def gen_us_surname_2010_info(
    rows: Iterable[Iterable[str]],
) -> Generator[UsSurname2010Info, None, None]:
    """
    Process a series of rows and generate US surname information from the 2010
    census data.

    Args:
        rows:
            Iterable giving "row" objects, where each row is an iterable of
            strings.

    Yields:
        :class:`UsSurname2010Info` objects

    """
    for row in rows:
        yield UsSurname2010Info(*row)


def fetch_us_surnames(
    url_1990: str,
    url_2010: str,
    filename: str = "",
    freq_csv_filename: str = "",
    min_cumfreq_pct: float = 0,
    max_cumfreq_pct: float = 100,
    min_word_length: int = 1,
    show_rejects: bool = False,
    debug_names: List[str] = None,
) -> None:
    """
    Fetches US surnames from the 1990 and 2010 census data. Writes them to a
    file.

    Args:
        url_1990:
            URL for 1990 US census data
        url_2010:
            URL for 2010 US census data
        filename:
            Text filename to write names to (one name per line).
        freq_csv_filename:
            Optional CSV to write "name, frequency" pairs to, one name per
            line.
        min_cumfreq_pct:
            Minimum cumulative frequency (%): 0 for no limit, or above 0 to
            exclude common names.
        max_cumfreq_pct:
            Maximum cumulative frequency (%): 100 for no limit, or below 100 to
            exclude rare names.
        min_word_length:
            Minimum word length; all words must be at least this long.
        show_rejects:
            Report rejected words to the Python debug log.
        debug_names:
            Names to show extra information about (e.g. to discover the right
            thresholds).
    """
    if not filename and not freq_csv_filename:
        log.warning(
            "No output filenames specified for US forenames; skipping."
        )
        return

    nameinfo_p1 = gen_name_info_via_min_length(
        gen_sufficiently_frequent_names(
            gen_us_surname_1990_info(
                gen_lines_from_binary_files(
                    gen_binary_files_from_urls([url_1990])
                )
            ),
            min_cumfreq_pct=min_cumfreq_pct,
            max_cumfreq_pct=max_cumfreq_pct,
            show_rejects=show_rejects,
            debug_names=debug_names,
        ),
        min_name_length=min_word_length,
    )
    nameinfo_p2 = gen_name_info_via_min_length(
        gen_sufficiently_frequent_names(
            gen_us_surname_2010_info(
                gen_rows_from_csv_binfiles(
                    gen_files_from_zipfiles(
                        gen_binary_files_from_urls(
                            [url_2010], on_disk=True
                        ),  # a zip
                        #  The zip file contains a .CSV and a .XLS
                        filespec="*.csv",
                        on_disk=True,
                    ),
                    skip_header=True,
                )
            ),
            min_cumfreq_pct=min_cumfreq_pct,
            max_cumfreq_pct=max_cumfreq_pct,
            show_rejects=show_rejects,
        ),
        min_name_length=min_word_length,
    )
    pipeline = itertools.chain(nameinfo_p1, nameinfo_p2)
    names = SortedSet()
    freq = {}  # type: Dict[str, float]
    for nameinfo in pipeline:
        name = nameinfo.name
        if name not in names:
            names.add(nameinfo.name)
            freq[name] = nameinfo.freq_p

    if filename:
        write_words_to_file(filename, names)

    if freq_csv_filename:
        log.info(f"Writing to: {freq_csv_filename}")
        with open(freq_csv_filename, "wt") as f:
            csvwriter = csv.writer(f)
            for name in names:
                csvwriter.writerow([name, freq[name]])
        log.info(f"... finished writing to: {freq_csv_filename}")


# =============================================================================
# Medical eponyms
# =============================================================================


def fetch_eponyms(filename: str, add_unaccented_versions: bool) -> None:
    """
    Writes medical eponyms to a file.

    Args:
        filename:
            Filename to write to.
        add_unaccented_versions:
            Add unaccented (mangled) versions of names, too? For example, do
            you want Sjogren as well as Sjögren?
    """
    names = get_plain_eponyms(add_unaccented_versions=add_unaccented_versions)
    write_words_to_file(filename, names)


# =============================================================================
# File processing: A-not-B
# =============================================================================


def filter_files(
    input_filenames: List[str],
    output_filename: str,
    exclusion_filenames: List[str] = None,
    inclusion_filenames: List[str] = None,
    min_line_length: int = 0,
) -> None:
    """
    Read lines from input files, filters them, and writes them to the output
    file.

    Args:
        input_filenames:
            Read lines from these files.
        output_filename:
            The output file.
        exclusion_filenames:
            If a line is present in any of these files, it is excluded
        inclusion_filenames:
            If any files are specified here, lines must be present in at least
            one inclusion file to pass through.
        min_line_length:
            Skip any A lines that are shorter than this value.
    """
    exclusion_filenames = exclusion_filenames or []  # type: List[str]
    inclusion_filenames = inclusion_filenames or []  # type: List[str]
    # Check inputs
    input_output_overlap = set(input_filenames).intersection(
        set(exclusion_filenames)
    )
    if len(input_output_overlap) > 0:
        raise ValueError(
            f"Input and exclusion files cannot overlap; "
            f"overlap is {input_output_overlap}"
        )
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
        if output_filename in inclusion_filenames:
            raise ValueError("Output cannot be one of the inclusion files")
    # Announce intention
    msg = [f"Finding lines in {input_filenames}"]
    if exclusion_filenames:
        msg.append(f"excluding any lines from {exclusion_filenames}")
    if inclusion_filenames:
        msg.append(f"requiring they be in {inclusion_filenames}")
    msg.append(f"writing to {output_filename}")
    log.info("; ".join(msg))
    # Do it
    input_count = 0
    output_count = 0
    exclusion_lines_lower = set(
        gen_lower(
            gen_lines_from_textfiles(
                gen_textfiles_from_filenames(exclusion_filenames)
            )
        )
    )
    using_inclusion = bool(inclusion_filenames)
    inclusion_lines_lower = set(
        gen_lower(
            gen_lines_from_textfiles(
                gen_textfiles_from_filenames(inclusion_filenames)
            )
        )
    )
    log.debug("... reading from A, writing to OUT")
    with smart_open(output_filename, "w") as outfile:
        for ifilename in input_filenames:
            with smart_open(ifilename, "r") as a_file:
                for a_line in a_file:
                    input_count += 1
                    if len(a_line) < min_line_length:
                        continue
                    a_line_lower = a_line.lower()
                    if a_line_lower in exclusion_lines_lower:
                        continue
                    if (
                        using_inclusion
                        and a_line_lower not in inclusion_lines_lower
                    ):
                        continue
                    outfile.write(a_line)
                    output_count += 1
    log.info(
        f"... done (line counts: input {input_count}, "
        f"exclusion {len(exclusion_lines_lower)}, "
        f"inclusion {len(inclusion_lines_lower)}, "
        f"output {output_count})"
    )


# =============================================================================
# Main
# =============================================================================

MIN_CUMFREQ_PCT_HELP = (
    "Fetch only names where the cumulative frequency percentage, up "
    "to and including this name, was at least this value. "
    "Range is 0-100. Use 0 for no limit. Setting this above 0 "
    "excludes COMMON names. (This is a trade-off between being "
    "comprehensive and operating at a reasonable speed. Lower "
    "numbers are more comprehensive but slower.)"
)
MAX_CUMFREQ_PCT_HELP = (
    "Fetch only names where the cumulative frequency percentage, up "
    "to and including this name, was less than or equal to this "
    "value. "
    "Range is 0-100. Use 100 for no limit. Setting this below 100 "
    "excludes RARE names. (This is a trade-off between being "
    "comprehensive and operating at a reasonable speed. Higher "
    "numbers are more comprehensive but slower.)"
)


def main() -> None:
    """
    Command-line processor. See command-line help.
    """
    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        formatter_class=ArgumentDefaultsRichHelpFormatter
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Be verbose"
    )
    parser.add_argument(
        "--min_word_length",
        type=positive_int,
        default=2,
        help="Minimum word (or name) length to allow",
    )
    parser.add_argument(
        "--show_rejects",
        action="store_true",
        help="Print to stdout (and, in verbose mode, log) the words being "
        "rejected",
    )
    parser.add_argument(
        "--debug_names",
        nargs="*",
        help="Show extra detail about these names (e.g. to work out your "
        "preferred frequency thresholds)",
    )

    english_group = parser.add_argument_group("English words")
    english_group.add_argument(
        "--english_words",
        action="store_true",
        help="Fetch English words (e.g. to remove from the nonspecific "
        "denylist, not to add to an allowlist; consider words like smith)",
    )
    english_group.add_argument(
        "--english_words_output",
        type=str,
        help="Output file for English words",
    )
    english_group.add_argument(
        "--english_words_url",
        type=str,
        # default="https://www.gutenberg.org/files/3201/files/SINGLE.TXT",
        # ... contains all sorts of names like "cheung"
        default="https://www.gutenberg.org/files/3201/files/CROSSWD.TXT",
        # ... much better; all possible Scrabble words
        help="URL for a textfile containing all English words (will then be "
        "filtered)",
    )
    english_group.add_argument(
        "--valid_word_regex",
        type=str,
        default=DEFAULT_VALID_WORD_REGEX,
        help="Regular expression to determine valid English words",
    )
    english_group.add_argument(
        "--gutenberg_word_freq",
        action="store_true",
        help="Fetch words from Project Gutenberg with frequencies",
    )
    english_group.add_argument(
        "--gutenberg_word_freq_output",
        type=str,
        help="Output file for English words with frequencies. CSV file with "
        "columns: word, word_freq, cum_freq.",
    )
    english_group.add_argument(
        "--gutenberg_id_first",
        type=int,
        default=100,
        # Complete Works of Shakespeare
        # https://www.gutenberg.org/ebooks/100
        help="For word counting: first Project Gutenberg book ID",
    )
    english_group.add_argument(
        "--gutenberg_id_last",
        type=int,
        default=110,
        help="For word counting: last Project Gutenberg book ID",
    )

    wordfreqfilter_group = parser.add_argument_group(
        "Filter English words by frequency"
    )
    wordfreqfilter_group.add_argument(
        "--filter_words_by_freq",
        action="store_true",
        help="Read a CSV file from --gutenberg_word_freq, filter it by "
        "cumulative word frequency, and write a plain list of words.",
    )
    wordfreqfilter_group.add_argument(
        "--wordfreqfilter_input",
        help="Input filename. Usually the output of "
        "--gutenberg_word_freq_output.",
    )
    wordfreqfilter_group.add_argument(
        "--wordfreqfilter_output", help="Output filename. Plain text file."
    )
    wordfreqfilter_group.add_argument(
        "--wordfreqfilter_min_cum_freq",
        type=float,
        default=0.0,
        help="Minimum cumulative frequency. "
        "(Set to >0 to exclude common words.)",
    )
    wordfreqfilter_group.add_argument(
        "--wordfreqfilter_max_cum_freq",
        type=float,
        default=1.0,
        help="Maximum cumulative frequency. "
        "(Set to <1 to exclude rare words.)",
    )

    us_forename_group = parser.add_argument_group("US forenames")
    us_forename_group.add_argument(
        "--us_forenames",
        action="store_true",
        help="Fetch US forenames (for denylist)",
    )
    us_forename_group.add_argument(
        "--us_forenames_freq_output",
        type=str,
        help="Output CSV file for US forename with frequencies (columns are: "
        "name, frequency)",
    )
    us_forename_group.add_argument(
        "--us_forenames_sex_freq_output",
        type=str,
        help="Output CSV file for US forename with sex and frequencies "
        "(columns are: name, gender, frequency)",
    )
    us_forename_group.add_argument(
        "--us_forenames_url",
        type=str,
        default="https://www.ssa.gov/OACT/babynames/names.zip",
        help="URL to Zip file of US Census-derived forenames lists (excludes "
        "names with national frequency <5; see "
        "https://www.ssa.gov/OACT/babynames/limits.html)",
    )
    us_forename_group.add_argument(
        "--us_forenames_min_cumfreq_pct",
        type=percentage,
        default=0,
        help=MIN_CUMFREQ_PCT_HELP,
    )
    us_forename_group.add_argument(
        "--us_forenames_max_cumfreq_pct",
        type=percentage,
        default=100,
        help=MAX_CUMFREQ_PCT_HELP,
    )
    us_forename_group.add_argument(
        "--us_forenames_output",
        type=str,
        help="Output file for US forenames",
    )

    us_surname_group = parser.add_argument_group("US surnames")
    us_surname_group.add_argument(
        "--us_surnames",
        action="store_true",
        help="Fetch US surnames (for denylist)",
    )
    us_surname_group.add_argument(
        "--us_surnames_output",
        type=str,
        help="Output text file for US surnames",
    )
    us_surname_group.add_argument(
        "--us_surnames_freq_output",
        type=str,
        help="Output CSV file for US surnames with frequencies (columns are: "
        "name, frequency)",
    )
    us_surname_group.add_argument(
        "--us_surnames_1990_census_url",
        type=str,
        default="http://www2.census.gov/topics/genealogy/1990surnames/dist.all.last",  # noqa
        help="URL for textfile of US 1990 Census surnames",
    )
    us_surname_group.add_argument(
        "--us_surnames_2010_census_url",
        type=str,
        default="https://www2.census.gov/topics/genealogy/2010surnames/names.zip",  # noqa
        help="URL for zip of US 2010 Census surnames",
    )
    us_surname_group.add_argument(
        "--us_surnames_min_cumfreq_pct",
        type=percentage,
        default=0,
        help=MIN_CUMFREQ_PCT_HELP,
    )
    us_surname_group.add_argument(
        "--us_surnames_max_cumfreq_pct",
        type=percentage,
        default=100,
        help=MAX_CUMFREQ_PCT_HELP,
    )

    eponyms_group = parser.add_argument_group("Medical eponyms")
    eponyms_group.add_argument(
        "--eponyms",
        action="store_true",
        help="Write medical eponyms (to remove from denylist)",
    )
    eponyms_group.add_argument(
        "--eponyms_output",
        type=str,
        default="medical_eponyms.txt",
        help="Output file for medical eponyms",
    )
    eponyms_group.add_argument(
        "--eponyms_add_unaccented_versions",
        type=str2bool,
        nargs="?",
        const=True,
        default=True,
        help="Add unaccented versions (e.g. Sjogren as well as Sjögren)",
    )

    filter_group = parser.add_argument_group(
        "Filter functions",
        "Extra functions to filter wordlists."
        "Specify an input file, optional exclusion and/or inclusion file(s), "
        "and an output file. "
        "You can use '-' for the output file to mean 'stdout', "
        "and for one input file to mean 'stdin'. No filenames (other than "
        "'-' for input and output) may overlap. The --min_line_length option "
        "also applies. Duplicates are not removed.",
    )
    filter_group.add_argument(
        "--filter_input",
        type=str,
        nargs="*",
        help="Input file(s). Words will be drawn from these files.",
    )
    filter_group.add_argument(
        "--filter_include",
        type=str,
        nargs="*",
        help="Inclusion file(s). If any inclusion files are specified, words "
        "from the input must be present in at least one inclusion file to "
        "pass.",
    )
    filter_group.add_argument(
        "--filter_exclude",
        type=str,
        nargs="*",
        help="Exclusion file(s). Any words present in the exclusion files do "
        "not pass.",
    )
    filter_group.add_argument(
        "--filter_output",
        type=str,
        nargs="?",
        help="Output file. Words are written here.",
    )
    args = parser.parse_args()

    if bool(args.filter_input) != bool(args.filter_output):
        print("Specify both --filter_input and --filter_output, or none.")
        parser.print_usage()
        sys.exit(1)

    loglevel = logging.DEBUG if args.verbose else logging.INFO
    rootlogger = logging.getLogger()
    configure_logger_for_colour(rootlogger, level=loglevel)

    if args.min_word_length > 1:
        log.info(f"Restricting to words of length >= {args.min_word_length}")

    if args.english_words:
        fetch_english_words(
            url=args.english_words_url,
            filename=args.english_words_output,
            valid_word_regex_text=args.valid_word_regex,
            min_word_length=args.min_word_length,
            show_rejects=args.show_rejects,
        )

    if args.gutenberg_word_freq:
        fetch_gutenberg_word_freq(
            filename=args.gutenberg_word_freq_output,
            gutenberg_id_first=args.gutenberg_id_first,
            gutenberg_id_last=args.gutenberg_id_last,
            valid_word_regex_text=args.valid_word_regex,
            min_word_length=args.min_word_length,
        )

    if args.filter_words_by_freq:
        filter_words_by_freq(
            input_filename=args.wordfreqfilter_input,
            output_filename=args.wordfreqfilter_output,
            min_cum_freq=args.wordfreqfilter_min_cum_freq,
            max_cum_freq=args.wordfreqfilter_max_cum_freq,
        )

    if args.us_forenames:
        fetch_us_forenames(
            url=args.us_forenames_url,
            filename=args.us_forenames_output,
            freq_csv_filename=args.us_forenames_freq_output,
            freq_sex_csv_filename=args.us_forenames_sex_freq_output,  # noqa
            min_cumfreq_pct=args.us_forenames_min_cumfreq_pct,
            max_cumfreq_pct=args.us_forenames_max_cumfreq_pct,
            min_name_length=args.min_word_length,
            show_rejects=args.show_rejects,
            debug_names=args.debug_names,
        )

    if args.us_surnames:
        fetch_us_surnames(
            url_1990=args.us_surnames_1990_census_url,
            url_2010=args.us_surnames_2010_census_url,
            filename=args.us_surnames_output,
            freq_csv_filename=args.us_surnames_freq_output,
            min_cumfreq_pct=args.us_surnames_min_cumfreq_pct,
            max_cumfreq_pct=args.us_surnames_max_cumfreq_pct,
            min_word_length=args.min_word_length,
            show_rejects=args.show_rejects,
            debug_names=args.debug_names,
        )

    if args.eponyms:
        fetch_eponyms(
            filename=args.eponyms_output,
            add_unaccented_versions=args.eponyms_add_unaccented_versions,
        )

    if args.filter_input:
        filter_files(
            input_filenames=args.filter_input,
            inclusion_filenames=args.filter_include,
            exclusion_filenames=args.filter_exclude,
            output_filename=args.filter_output,
            min_line_length=args.min_word_length,
        )


if __name__ == "__main__":
    main()
