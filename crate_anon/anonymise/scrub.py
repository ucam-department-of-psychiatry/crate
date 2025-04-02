"""
crate_anon/anonymise/scrub.py

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

**Scrubber classes for CRATE anonymiser.**

"""

from abc import ABC, abstractmethod
from collections import OrderedDict
import datetime
import logging
import re
import string
from typing import (
    Any,
    Dict,
    Iterable,
    Generator,
    List,
    Optional,
    Pattern,
    Set,
    Tuple,
    TYPE_CHECKING,
    Union,
)

if TYPE_CHECKING:
    from re import Match

from cardinal_pythonlib.datetimefunc import coerce_to_datetime
from cardinal_pythonlib.file_io import gen_lines_without_comments
from cardinal_pythonlib.hash import GenericHasher
from cardinal_pythonlib.sql.validation import (
    is_sqltype_date,
    is_sqltype_text_over_one_char,
)
from cardinal_pythonlib.text import get_unicode_characters

# from flashtext import KeywordProcessor
from crate_anon.common.bugfix_flashtext import KeywordProcessorFixed

# ... temp bugfix

# noinspection PyPep8Naming
from crate_anon.anonymise.constants import (
    AnonymiseConfigDefaults as DA,
    DATE_BLURRING_DIRECTIVES,
    DATE_BLURRING_DIRECTIVES_CSV,
    MONTH_3_LETTER_INDEX,
    ScrubMethod,
)
from crate_anon.anonymise.anonregex import (
    EMAIL_REGEX_STR,
    DateRegexNames,
    get_anon_fragments_from_string,
    get_code_regex_elements,
    get_date_regex_elements,
    get_generic_date_regex_elements,
    get_number_of_length_n_regex_elements,
    get_phrase_regex_elements,
    get_regex_from_elements,
    get_regex_string_from_elements,
    get_string_regex_elements,
    get_uk_postcode_regex_elements,
)
from crate_anon.common.stringfunc import (
    get_digit_string_from_vaguely_numeric_string,
    reduce_to_alphanumeric,
)

log = logging.getLogger(__name__)


# =============================================================================
# Generic scrubber base class
# =============================================================================


class ScrubberBase(ABC):
    """
    Scrubber base class.
    """

    def __init__(self, hasher: GenericHasher) -> None:
        """
        Args:
            hasher:
                :class:`GenericHasher` to use to hash this scrubber (for
                change-detection purposes); should be a secure hasher
        """
        self.hasher = hasher

    @abstractmethod
    def scrub(self, text: str) -> str:
        """
        Returns a scrubbed version of the text.

        Args:
            text: the raw text, potentially containing sensitive information

        Returns:
            the de-identified text
        """
        raise NotImplementedError("Implement in derived class")

    @abstractmethod
    def get_hash(self) -> str:
        """
        Returns a hash of our scrubber -- so we can store it, and later see if
        it's changed. In an incremental update, if the scrubber has changed, we
        should re-anonymise all data for this patient.
        """
        raise NotImplementedError("Implement in derived class")


# =============================================================================
# WordList
# =============================================================================


def lower_case_words_from_file(filename: str) -> Generator[str, None, None]:
    """
    Generates lower-case words from a file.
    """
    for line in gen_lines_without_comments(
        filename, comment_at_start_only=True
    ):
        for word in line.split():
            if word:
                yield word.lower()


def lower_case_phrase_lines_from_file(
    filename: str,
) -> Generator[str, None, None]:
    """
    Generates lower-case phrases from a file, one per line.
    """
    for line in gen_lines_without_comments(
        filename, comment_at_start_only=True
    ):
        # line is pre-stripped (left/right) and not empty
        yield line.lower()


FLASHTEXT_WORD_CHARACTERS = set(
    string.digits
    + string.ascii_letters  # part of flashtext default
    + "_"  # part of flashtext default
    + get_unicode_characters("Latin_Alphabetic")  # part of flashtext default
)
# Why do we do this? So e.g. "naïve" isn't truncated to "naï[~~~]".
# Check: FLASHTEXT_WORDCHAR_STR = "".join(sorted(FLASHTEXT_WORD_CHARACTERS))


class WordList(ScrubberBase):
    """
    A scrubber that removes all words in a wordlist, in case-insensitive
    fashion.

    This serves a dual function as an allowlist (is a word in the list?) and a
    denylist (scrub text using the wordlist).
    """

    def __init__(
        self,
        filenames: Iterable[str] = None,
        words: Iterable[str] = None,
        as_phrases: bool = False,
        replacement_text: str = "[---]",
        hasher: GenericHasher = None,
        suffixes: List[str] = None,
        at_word_boundaries_only: bool = True,
        max_errors: int = 0,
        regex_method: bool = False,
    ) -> None:
        """
        Args:
            filenames:
                Filenames to read words from.
            words:
                Additional words to add.
            as_phrases:
                Keep lines in the source file intact (as phrases), rather than
                splitting them into individual words, and (if ``regex_method``
                is True) scrub as phrases.
            replacement_text:
                Replace sensitive content with this string.
            hasher:
                :class:`GenericHasher` to use to hash this scrubber (for
                change-detection purposes); should be a secure hasher.
            suffixes:
                Append each of these suffixes to each word.
            at_word_boundaries_only:
                Boolean. If set, ensure that the regex begins and ends with a
                word boundary requirement. (If false: will scrub ``ANN`` from
                ``bANNed``, for example.)
            max_errors:
                The maximum number of typographical insertion / deletion /
                substitution errors to permit. Applicable only if
                ``regex_method`` is True.
            regex_method:
                Use regular expressions? If True: slower, but phrase scrubbing
                deals with variable whitespace. If False: much faster (uses
                FlashText), but whitespace is inflexible.
        """
        if not regex_method and at_word_boundaries_only is False:
            raise ValueError(
                "FlashText (chosen by regex_method=False) will only work at "
                "word boundaries, but at_word_boundaries_only is False"
            )
        filenames = filenames or []
        words = words or []

        super().__init__(hasher)
        self.replacement_text = replacement_text
        self.as_phrases = as_phrases
        self.suffixes = suffixes or []  # type: List[str]
        self.at_word_boundaries_only = at_word_boundaries_only
        self.max_errors = max_errors
        self.regex_method = regex_method
        self._regex = None  # type: Optional[Pattern[str]]
        self._processor = None  # type: Optional[KeywordProcessorFixed]
        self._cached_hash = None  # type: Optional[str]
        self._built = False

        self.words = set()  # type: Set[str]
        # Sets are faster than lists for "is x in s" operations:
        # https://stackoverflow.com/questions/2831212/python-sets-vs-lists
        # noinspection PyTypeChecker
        for f in filenames:
            self.add_file(f, clear_cache=False)
        # noinspection PyTypeChecker
        for w in words:
            self.add_word(w, clear_cache=False)
        # log.debug(f"Created wordlist with {len(self.words)} words")

    def clear_cache(self) -> None:
        """
        Clear cached information (e.g. the compiled regex, the cached hash of
        this scrubber).
        """
        self._built = False
        self._regex = None  # type: Optional[Pattern[str]]
        self._processor = None  # type: Optional[KeywordProcessorFixed]
        self._cached_hash = None  # type: Optional[str]

    def add_word(self, word: str, clear_cache: bool = True) -> None:
        """
        Add a word to our wordlist.

        Args:
            word: word to add
            clear_cache: also clear our cache?
        """
        if not word:
            return
        self.words.add(word.lower())
        if clear_cache:
            self.clear_cache()

    def add_file(self, filename: str, clear_cache: bool = True) -> None:
        """
        Add all words from a file.

        Args:
            filename:
                File to read.
            clear_cache:
                Also clear our cache?
        """
        if self.as_phrases:
            wordgen = lower_case_phrase_lines_from_file(filename)
        else:
            wordgen = lower_case_words_from_file(filename)
        for w in wordgen:
            self.words.add(w)
        if clear_cache:
            self.clear_cache()

    def contains(self, word: str) -> bool:
        """
        Does our wordlist contain this word?
        """
        return word.lower() in self.words

    def get_hash(self) -> str:
        # docstring in parent class

        # A set is unordered.
        # We want the hash to be the same if we have the same words, even if
        # they were entered in a different order, so we need to sort:
        if not self._cached_hash:
            self._cached_hash = self.hasher.hash(sorted(self.words))
        return self._cached_hash

    def scrub(self, text: str) -> str:
        # docstring in parent class
        if not self._built:
            self.build()
        if self.regex_method:
            if not self._regex:
                return text
            return self._regex.sub(self.replacement_text, text)
        else:
            if not self._processor:
                return text
            return self._processor.replace_keywords(text)

    def _gen_word_and_suffixed(self, w: str) -> Iterable[str]:
        """
        Yields the word supplied plus suffixed versions.
        """
        yield w
        for s in self.suffixes:
            yield w + s

    def build(self) -> None:
        """
        Compiles a high-speed scrubbing device, be it a regex or a FlashText
        processor. Called only when we have collected all our words.
        """
        if self.regex_method:
            elements = []  # type: List[str]
            for w in self.words:
                if self.as_phrases:
                    elements.extend(
                        get_phrase_regex_elements(
                            w,
                            suffixes=self.suffixes,
                            at_word_boundaries_only=self.at_word_boundaries_only,  # noqa: E501
                            max_errors=self.max_errors,
                        )
                    )
                else:
                    elements.extend(
                        get_string_regex_elements(
                            w,
                            suffixes=self.suffixes,
                            at_word_boundaries_only=self.at_word_boundaries_only,  # noqa: E501
                            max_errors=self.max_errors,
                        )
                    )
            log.debug(f"Building regex with {len(elements)} elements")
            self._regex = get_regex_from_elements(elements)
        else:
            if self.words:
                self._processor = KeywordProcessorFixed(case_sensitive=False)
                self._processor.set_non_word_boundaries(
                    FLASHTEXT_WORD_CHARACTERS
                )
                replacement = self.replacement_text
                log.debug(
                    f"Building FlashText processor with "
                    f"{len(self.words)} keywords"
                )
                for w in self.words:
                    for sw in self._gen_word_and_suffixed(w):
                        self._processor.add_keyword(sw, replacement)
            else:
                self._processor = None  # type: Optional[KeywordProcessorFixed]
        self._built = True


# =============================================================================
# NonspecificScrubber
# =============================================================================


class Replacer:
    """
    Custom regex replacement called from regex.sub().
    This base class doesn't do much and is the equivalent of just passing the
    replacement text to regex.sub().
    """

    def __init__(self, replacement_text: str) -> None:
        self.replacement_text = replacement_text

    def replace(self, match: "Match") -> str:
        """
        When re.sub() or regex.sub() is called, the "repl" argument can be
        a function. If so, it's a function that takes a :class:`re.Match`
        argument and returns the replacement text.
        """
        return self.replacement_text


class NonspecificReplacer(Replacer):
    """
    Custom regex replacement for the Nonspecific scrubber. Currently this
    will "blur" dates if replacement_text_all_dates contains any formatting
    directives.
    """

    def __init__(self, replacement_text: str, replacement_text_all_dates: str):
        """
        Args:
            replacement_text:
                Generic text to use.
            replacement_text_all_dates:
                Replacement text to use if the matched text is a date. Can
                include format specifiers to blur the date rather than
                scrubbing it out entirely.
        """
        super().__init__(replacement_text)

        self.replacement_text_all_dates = replacement_text_all_dates
        self.slow_date_replacement = "%" in replacement_text_all_dates

    def replace(self, match: "Match") -> str:
        groupdict = match.groupdict()
        if not self.is_a_date(groupdict):
            return super().replace(match)

        if self.slow_date_replacement:
            date = self.parse_date(match, groupdict)
            return date.strftime(self.replacement_text_all_dates)

        return self.replacement_text_all_dates

    @staticmethod
    def is_a_date(groupdict: Dict[str, Any]) -> bool:
        """
        Is the match result a date? We detect this via our named regex groups.
        """
        return any(
            groupdict.get(groupname) is not None
            for groupname in (
                DateRegexNames.DAY_MONTH_YEAR,
                DateRegexNames.MONTH_DAY_YEAR,
                DateRegexNames.YEAR_MONTH_DAY,
                DateRegexNames.ISODATE_NO_SEP,
            )
        )

    @staticmethod
    def parse_date(
        match: "Match", groupdict: Dict[str, Any]
    ) -> datetime.datetime:
        """
        Retrieve a valid date from the Match object for blurring.

        Valid regex group name combinations, where D == DateRegexNames:

        D.ISODATE_NO_SEP: D.FOUR_DIGIT_YEAR,

        D.DAY_MONTH_YEAR: D.NUMERIC_DAY, D.NUMERIC_MONTH, D.TWO_DIGIT_YEAR,
        D.DAY_MONTH_YEAR: D.NUMERIC_DAY, D.NUMERIC_MONTH, D.FOUR_DIGIT_YEAR,
        D.DAY_MONTH_YEAR: D.NUMERIC_DAY, D.ALPHABETICAL_MONTH, D.TWO_DIGIT_YEAR,
        D.DAY_MONTH_YEAR: D.NUMERIC_DAY, D.ALPHABETICAL_MONTH, D.FOUR_DIGIT_YEAR,

        D.MONTH_DAY_YEAR: D.NUMERIC_DAY, D.NUMERIC_MONTH, D.TWO_DIGIT_YEAR,
        D.MONTH_DAY_YEAR: D.NUMERIC_DAY, D.NUMERIC_MONTH, D.FOUR_DIGIT_YEAR,
        D.MONTH_DAY_YEAR: D.NUMERIC_DAY, D.ALPHABETICAL_MONTH, D.TWO_DIGIT_YEAR,
        D.MONTH_DAY_YEAR: D.NUMERIC_DAY, D.ALPHABETICAL_MONTH, D.FOUR_DIGIT_YEAR,

        D.YEAR_MONTH_DAY: D.NUMERIC_DAY, D.NUMERIC_MONTH, D.TWO_DIGIT_YEAR,
        D.YEAR_MONTH_DAY: D.NUMERIC_DAY, D.NUMERIC_MONTH, D.FOUR_DIGIT_YEAR,
        D.YEAR_MONTH_DAY: D.NUMERIC_DAY, D.ALPHABETICAL_MONTH, D.TWO_DIGIT_YEAR,
        D.YEAR_MONTH_DAY: D.NUMERIC_DAY, D.ALPHABETICAL_MONTH, D.FOUR_DIGIT_YEAR,
        """  # noqa: E501

        # Simple special handling for ISO date format without separators.
        isodate_no_sep = groupdict.get(DateRegexNames.ISODATE_NO_SEP)
        if isodate_no_sep is not None:
            return datetime.datetime.strptime(isodate_no_sep, "%Y%m%d")

        # For all others, extract D/M/Y information.

        year = groupdict.get(DateRegexNames.FOUR_DIGIT_YEAR)
        if year is None:
            two_digit_year = match.group(DateRegexNames.TWO_DIGIT_YEAR)

            # Will convert:
            #    00-68 -> 2000-2068
            #    69-99 -> 1969-1999
            year = datetime.datetime.strptime(two_digit_year, "%y").year

        numeric_day = match.group(DateRegexNames.NUMERIC_DAY)

        numeric_month = groupdict.get(DateRegexNames.NUMERIC_MONTH)
        if numeric_month is None:
            three_letter_month = match.group(
                DateRegexNames.ALPHABETICAL_MONTH
            )[:3]
            numeric_month = MONTH_3_LETTER_INDEX.get(three_letter_month)

        return datetime.datetime(
            int(year), int(numeric_month), int(numeric_day)
        )


class NonspecificScrubber(ScrubberBase):
    """
    Scrubs a bunch of things that are independent of any patient-specific data,
    such as removing all UK postcodes, or numbers of a certain length.
    """

    def __init__(
        self,
        hasher: GenericHasher,
        replacement_text: str = DA.REPLACE_NONSPECIFIC_INFO_WITH,
        anonymise_codes_at_word_boundaries_only: bool = DA.ANONYMISE_CODES_AT_WORD_BOUNDARIES_ONLY,  # noqa: E501
        anonymise_dates_at_word_boundaries_only: bool = DA.ANONYMISE_DATES_AT_WORD_BOUNDARIES_ONLY,  # noqa: E501
        anonymise_numbers_at_word_boundaries_only: bool = DA.ANONYMISE_NUMBERS_AT_WORD_BOUNDARIES_ONLY,  # noqa: E501
        denylist: WordList = None,
        scrub_all_numbers_of_n_digits: List[int] = None,
        scrub_all_uk_postcodes: bool = DA.SCRUB_ALL_UK_POSTCODES,
        scrub_all_dates: bool = DA.SCRUB_ALL_DATES,
        replacement_text_all_dates: str = DA.REPLACE_ALL_DATES_WITH,
        scrub_all_email_addresses: bool = DA.SCRUB_ALL_EMAIL_ADDRESSES,
        extra_regexes: Optional[List[str]] = None,
    ) -> None:
        """
        Args:
            replacement_text:
                Replace sensitive content with this string.
            hasher:
                :class:`GenericHasher` to use to hash this scrubber (for
                change-detection purposes); should be a secure hasher
            anonymise_codes_at_word_boundaries_only:
                For codes: Boolean. Ensure that the regex begins and ends with
                a word boundary requirement.
            anonymise_dates_at_word_boundaries_only:
                Scrub dates only if they occur at word boundaries. (Even if you
                say no, there are *some* restrictions or very odd things would
                happen; see
                :func:`crate_anon.anonymise.anonregex.get_generic_date_regex_elements`.)
            anonymise_numbers_at_word_boundaries_only:
                For numbers: Boolean. If set, ensure that the regex begins and
                ends with a word boundary requirement. If not set, the regex
                must be surrounded by non-digits. (If it were surrounded by
                more digits, it wouldn't be an n-digit number!)
            denylist:
                Words to scrub.
            scrub_all_numbers_of_n_digits:
                List of values of n; number lengths to scrub.
            scrub_all_uk_postcodes:
                Scrub all UK postcodes?
            scrub_all_dates:
                Scrub all dates? (Currently assumes the default locale for
                month names and ordinal suffixes.)
            replacement_text_all_dates:
                When scrub_all_dates is True, replace with this text.
                Supports limited datetime.strftime directives for "blurring" of
                dates. Example: "%b %Y" for abbreviated month and year.
            scrub_all_email_addresses:
                Scrub all e-mail addresses?
            extra_regexes:
                List of user-defined extra regexes to scrub.
        """
        scrub_all_numbers_of_n_digits = scrub_all_numbers_of_n_digits or []

        super().__init__(hasher)
        self.replacement_text = replacement_text
        self.anonymise_codes_at_word_boundaries_only = (
            anonymise_codes_at_word_boundaries_only
        )
        self.anonymise_dates_at_word_boundaries_only = (
            anonymise_dates_at_word_boundaries_only
        )
        self.anonymise_numbers_at_word_boundaries_only = (
            anonymise_numbers_at_word_boundaries_only
        )
        self.denylist = denylist
        self.scrub_all_numbers_of_n_digits = scrub_all_numbers_of_n_digits
        self.scrub_all_uk_postcodes = scrub_all_uk_postcodes
        self.scrub_all_dates = scrub_all_dates

        self.replacement_text_all_dates = replacement_text_all_dates
        self.check_replacement_text_all_dates()
        self.replacer = self.get_replacer()

        self.scrub_all_email_addresses = scrub_all_email_addresses
        self.extra_regexes = extra_regexes

        self._cached_hash = None  # type: Optional[str]
        self._regex = None  # type: Optional[Pattern[str]]
        self._regex_built = False
        self.build_regex()

    def get_replacer(self) -> Replacer:
        """
        Return a function that can be used as the "repl" (replacer) argument
        to a re.sub() or regex.sub() call.
        """
        if (
            self.replacement_text == self.replacement_text_all_dates
            and "%" not in self.replacement_text_all_dates
        ):
            # Fast, simple
            return Replacer(self.replacement_text)

        # Handle dates in a more complex way, e.g. blurring them:
        return NonspecificReplacer(
            self.replacement_text, self.replacement_text_all_dates
        )

    def check_replacement_text_all_dates(self) -> None:
        """
        Ensure our date-replacement text is legitimate in terms of e.g.
        "%Y"-style directives.
        """
        bad = False
        possible_percent_chars = "".join(DATE_BLURRING_DIRECTIVES)
        if re.search(
            rf"%[^{possible_percent_chars}]", self.replacement_text_all_dates
        ):
            bad = True
        else:
            # Double-check:
            test_date = datetime.date(2000, 12, 31)
            try:
                test_date.strftime(self.replacement_text_all_dates)
            except ValueError:
                bad = True
        if bad:
            raise ValueError(
                f"Bad format {self.replacement_text_all_dates!r} for date "
                "scrubbing. Allowed directives are: "
                f"{DATE_BLURRING_DIRECTIVES_CSV}"
            )

    def get_hash(self) -> str:
        # docstring in parent class
        if not self._cached_hash:
            self._cached_hash = self.hasher.hash(
                [
                    # signature, used for hashing:
                    self.anonymise_codes_at_word_boundaries_only,
                    self.anonymise_numbers_at_word_boundaries_only,
                    self.denylist.get_hash() if self.denylist else None,
                    self.scrub_all_numbers_of_n_digits,
                    self.scrub_all_uk_postcodes,
                ]
            )
        return self._cached_hash

    def scrub(self, text: str) -> str:
        # docstring in parent class
        if not self._regex_built:
            self.build_regex()
        if self.denylist:
            text = self.denylist.scrub(text)
        if not self._regex:  # possible; may be blank
            return text
        return self._regex.sub(self.replacer.replace, text)

    def build_regex(self) -> None:
        """
        Compile our high-speed regex.
        """
        elements = []  # type: List[str]
        if self.scrub_all_uk_postcodes:
            elements.extend(
                get_uk_postcode_regex_elements(
                    at_word_boundaries_only=(
                        self.anonymise_codes_at_word_boundaries_only
                    )
                )
            )
        # noinspection PyTypeChecker
        for n in self.scrub_all_numbers_of_n_digits:
            elements.extend(
                get_number_of_length_n_regex_elements(
                    n,
                    at_word_boundaries_only=(
                        self.anonymise_numbers_at_word_boundaries_only
                    ),
                )
            )
        if self.scrub_all_dates:
            elements.extend(
                get_generic_date_regex_elements(
                    at_word_boundaries_only=self.anonymise_dates_at_word_boundaries_only  # noqa: E501
                )
            )
        if self.scrub_all_email_addresses:
            elements.append(EMAIL_REGEX_STR)
        if self.extra_regexes:
            elements.extend(self.extra_regexes)
        self._regex = get_regex_from_elements(elements)
        self._regex_built = True


# =============================================================================
# PersonalizedScrubber
# =============================================================================


class PersonalizedScrubber(ScrubberBase):
    """
    Accepts patient-specific (patient and third-party) information, and uses
    that to scrub text.
    """

    def __init__(
        self,
        hasher: GenericHasher,
        replacement_text_patient: str = DA.REPLACE_PATIENT_INFO_WITH,
        replacement_text_third_party: str = DA.REPLACE_THIRD_PARTY_INFO_WITH,  # noqa: E501
        anonymise_codes_at_word_boundaries_only: bool = DA.ANONYMISE_CODES_AT_WORD_BOUNDARIES_ONLY,  # noqa: E501
        anonymise_codes_at_numeric_boundaries_only: bool = DA.ANONYMISE_CODES_AT_NUMERIC_BOUNDARIES_ONLY,  # noqa: E501
        anonymise_dates_at_word_boundaries_only: bool = DA.ANONYMISE_DATES_AT_WORD_BOUNDARIES_ONLY,  # noqa: E501
        anonymise_numbers_at_word_boundaries_only: bool = DA.ANONYMISE_NUMBERS_AT_WORD_BOUNDARIES_ONLY,  # noqa: E501
        anonymise_numbers_at_numeric_boundaries_only: bool = DA.ANONYMISE_NUMBERS_AT_NUMERIC_BOUNDARIES_ONLY,  # noqa: E501
        anonymise_strings_at_word_boundaries_only: bool = DA.ANONYMISE_STRINGS_AT_WORD_BOUNDARIES_ONLY,  # noqa: E501
        min_string_length_for_errors: int = DA.MIN_STRING_LENGTH_FOR_ERRORS,
        min_string_length_to_scrub_with: int = DA.MIN_STRING_LENGTH_TO_SCRUB_WITH,  # noqa: E501
        scrub_string_suffixes: List[str] = None,
        string_max_regex_errors: int = DA.STRING_MAX_REGEX_ERRORS,
        allowlist: WordList = None,
        alternatives: List[List[str]] = None,
        nonspecific_scrubber: NonspecificScrubber = None,
        nonspecific_scrubber_first: bool = DA.NONSPECIFIC_SCRUBBER_FIRST,
        debug: bool = False,
    ) -> None:
        """
        Args:
            hasher:
                :class:`GenericHasher` to use to hash this scrubber (for
                change-detection purposes); should be a secure hasher.
            replacement_text_patient:
                Replace sensitive "patient" content with this string.
            replacement_text_third_party:
                Replace sensitive "third party" content with this string.
            anonymise_codes_at_word_boundaries_only:
                For codes: Boolean. Ensure that the regex begins and ends with
                a word boundary requirement.
            anonymise_codes_at_numeric_boundaries_only:
                For codes: Boolean. Only applicable if
                anonymise_codes_at_word_boundaries_only is False. Ensure that
                the code is only recognized when surrounded by non-numbers;
                that is, only at the boundaries of numbers (at numeric
                boundaries). See
                :func:`crate_anon.anonymise.anonregex.get_code_regex_elements`.
            anonymise_dates_at_word_boundaries_only:
                For dates: Boolean. Ensure that the regex begins and ends with
                a word boundary requirement.
            anonymise_numbers_at_word_boundaries_only:
                For numbers: Boolean. Ensure that the regex begins and ends
                with a word boundary requirement. See
                :func:`crate_anon.anonymise.anonregex.get_code_regex_elements`.
            anonymise_numbers_at_numeric_boundaries_only:
                For numbers: Boolean. Only applicable if
                anonymise_numbers_at_word_boundaries_only is False. Ensure that
                the number is only recognized when surrounded by
                non-numbers; that is, only at the boundaries of numbers (at
                numeric boundaries). See
                :func:`crate_anon.anonymise.anonregex.get_code_regex_elements`.
            anonymise_strings_at_word_boundaries_only:
                For strings: Boolean. Ensure that the regex begins and ends
                with a word boundary requirement.
            min_string_length_for_errors:
                For strings: minimum string length at which typographical
                errors will be permitted.
            min_string_length_to_scrub_with:
                For strings: minimum string length at which the string will be
                permitted to be scrubbed with.
            scrub_string_suffixes:
                A list of suffixes to permit on strings.
            string_max_regex_errors:
                The maximum number of typographical insertion / deletion /
                substitution errors to permit.
            allowlist:
                :class:`WordList` of words to allow (not to scrub).
            alternatives:
                This allows words to be substituted by equivalents; such as
                ``St`` for ``Street`` or ``Rd`` for ``Road``. The parameter is
                a list of lists of equivalents; see
                :func:`crate_anon.anonymise.config.get_word_alternatives`.
            nonspecific_scrubber:
                :class:`NonspecificScrubber` to apply to remove information
                that is generic.
            nonspecific_scrubber_first:
                If one is provided, run the nonspecific scrubber first (rather
                than last)?
            debug:
                Show the final scrubber regex text as we compile our regexes.
        """
        scrub_string_suffixes = scrub_string_suffixes or []

        super().__init__(hasher)
        self.replacement_text_patient = replacement_text_patient
        self.replacement_text_third_party = replacement_text_third_party
        self.anonymise_codes_at_word_boundaries_only = (
            anonymise_codes_at_word_boundaries_only
        )
        self.anonymise_codes_at_numeric_boundaries_only = (
            anonymise_codes_at_numeric_boundaries_only
        )
        self.anonymise_dates_at_word_boundaries_only = (
            anonymise_dates_at_word_boundaries_only
        )
        self.anonymise_numbers_at_word_boundaries_only = (
            anonymise_numbers_at_word_boundaries_only
        )
        self.anonymise_numbers_at_numeric_boundaries_only = (
            anonymise_numbers_at_numeric_boundaries_only
        )
        self.anonymise_strings_at_word_boundaries_only = (
            anonymise_strings_at_word_boundaries_only
        )
        self.min_string_length_for_errors = min_string_length_for_errors
        self.min_string_length_to_scrub_with = min_string_length_to_scrub_with
        self.scrub_string_suffixes = scrub_string_suffixes
        self.string_max_regex_errors = string_max_regex_errors
        self.allowlist = allowlist
        self.alternatives = alternatives
        self.nonspecific_scrubber = nonspecific_scrubber
        self.nonspecific_scrubber_first = nonspecific_scrubber_first
        self.debug = debug

        # Regex information
        self.re_patient = None  # type: Optional[Pattern[str]]
        self.re_tp = None  # type: Optional[Pattern[str]]
        self.regexes_built = False
        self.re_patient_elements = []  # type: List[str]
        self.re_tp_elements = []  # type: List[str]
        # ... both changed from set to list to reflect referee's point re
        #     potential importance of scrubber order
        self.elements_tuplelist = (
            []
        )  # type: List[Tuple[bool, ScrubMethod, str]]
        # ... list of tuples: (patient?, type, value)
        # ... used for get_raw_info(); since we've made the order important,
        #     we should detect changes in order here as well
        self.clear_cache()

    def clear_cache(self) -> None:
        """
        Clear the internal cache (the compiled regex).
        """
        self.regexes_built = False

    @staticmethod
    def get_scrub_method(
        datatype_long: str, scrub_method: Optional[ScrubMethod]
    ) -> ScrubMethod:
        """
        Return the default scrub method for a given SQL datatype, unless
        overridden. For example, dates are scrubbed via a date method; numbers
        by a numeric method.

        Args:
            datatype_long: SQL datatype as a string
            scrub_method: optional method to enforce

        Returns:
             :class:`crate_anon.anonymise.constants.SCRUBMETHOD` value
        """
        if scrub_method is not None:
            return scrub_method
        elif is_sqltype_date(datatype_long):
            return ScrubMethod.DATE
        elif is_sqltype_text_over_one_char(datatype_long):
            return ScrubMethod.WORDS
        else:
            return ScrubMethod.NUMERIC

    def add_value(
        self,
        value: Any,
        scrub_method: ScrubMethod,
        patient: bool = True,
        clear_cache: bool = True,
    ) -> None:
        """
        Add a specific value via a specific scrub_method.

        Args:
            value:
                value to add to the scrubber
            scrub_method:
                :class:`crate_anon.anonymise.constants.SCRUBMETHOD` value
            patient:
                Boolean; controls whether it's treated as a patient value or a
                third-party value.
            clear_cache:
                also clear our cache?
        """
        if value is None:
            return
        new_tuple = (patient, scrub_method, repr(value))
        if new_tuple not in self.elements_tuplelist:
            self.elements_tuplelist.append(new_tuple)
        # Note: object reference
        r = self.re_patient_elements if patient else self.re_tp_elements

        if scrub_method is ScrubMethod.DATE:
            elements = self.get_elements_date(value)
        elif scrub_method is ScrubMethod.WORDS:
            elements = self.get_elements_words(value)
        elif scrub_method is ScrubMethod.PHRASE:
            elements = self.get_elements_phrase(value)
        elif scrub_method is ScrubMethod.PHRASE_UNLESS_NUMERIC:
            elements = self.get_elements_phrase_unless_numeric(value)
        elif scrub_method is ScrubMethod.NUMERIC:
            elements = self.get_elements_numeric(value)
        elif scrub_method is ScrubMethod.CODE:
            elements = self.get_elements_code(value)
        else:
            raise ValueError(
                f"Bug: unknown scrub_method to add_value: " f"{scrub_method}"
            )
        r.extend(elements)
        if clear_cache:
            self.clear_cache()

    def get_elements_date(
        self, value: Union[datetime.datetime, datetime.date]
    ) -> Optional[List[str]]:
        """
        Returns a list of regex elements for a given date value.
        """
        try:
            value = coerce_to_datetime(value)
        except Exception as e:
            log.warning(
                f"Invalid date received to PersonalizedScrubber. "
                f"get_elements_date(): value={value}, exception={e}"
            )
            return
        return get_date_regex_elements(
            value,
            at_word_boundaries_only=(
                self.anonymise_dates_at_word_boundaries_only
            ),
        )

    def get_elements_words(self, value: str) -> List[str]:
        """
        Returns a list of regex elements for a given string that contains
        textual words.
        """
        elements = []  # type: List[str]
        for s in get_anon_fragments_from_string(str(value)):
            length = len(s)
            if length < self.min_string_length_to_scrub_with:
                # With numbers: if you use the length limit, you may see
                # numeric parts of addresses, e.g. 4 Drury Lane as
                # 4 [___] [___]. However, if you exempt numbers then you
                # mess up a whole bunch of quantitative information, such
                # as "the last 4-5 years" getting wiped to "the last
                # [___]-5 years". So let's apply the length limit
                # consistently.
                continue
            if self.allowlist and self.allowlist.contains(s):
                continue
            if length >= self.min_string_length_for_errors:
                max_errors = self.string_max_regex_errors
            else:
                max_errors = 0
            elements.extend(
                get_string_regex_elements(
                    s,
                    self.scrub_string_suffixes,
                    max_errors=max_errors,
                    at_word_boundaries_only=(
                        self.anonymise_strings_at_word_boundaries_only
                    ),
                )
            )
        return elements

    def get_elements_phrase(self, value: Any) -> List[str]:
        """
        Returns a list of regex elements for a given phrase.
        """
        value = str(value).strip()
        if not value:
            return []
        length = len(value)
        if length < self.min_string_length_to_scrub_with:
            return []
        if self.allowlist and self.allowlist.contains(value):
            return []
        if length >= self.min_string_length_for_errors:
            max_errors = self.string_max_regex_errors
        else:
            max_errors = 0
        return get_phrase_regex_elements(
            value,
            max_errors=max_errors,
            at_word_boundaries_only=(
                self.anonymise_strings_at_word_boundaries_only
            ),
            alternatives=self.alternatives,
        )

    def get_elements_phrase_unless_numeric(self, value: Any) -> List[str]:
        """
        If the value is numeric, return an empty list. Otherwise, returns a
        list of regex elements for the given phrase.
        """
        try:
            _ = float(value)
            return []
        except (TypeError, ValueError):
            return self.get_elements_phrase(value)

    def get_elements_numeric(self, value: Any) -> List[str]:
        """
        Start with a number. Remove everything but the digits. Build a regex
        that scrubs the number.

        Particular examples: phone numbers, e.g. ``"(01223) 123456"``.

        Args:
            value: a string containing a number, or an actual number.

        Returns:
            a list of regex elements
        """
        return get_code_regex_elements(
            get_digit_string_from_vaguely_numeric_string(str(value)),
            at_word_boundaries_only=(
                self.anonymise_numbers_at_word_boundaries_only
            ),
            at_numeric_boundaries_only=(
                self.anonymise_numbers_at_numeric_boundaries_only
            ),
        )

    def get_elements_code(self, value: Any) -> List[str]:
        """
        Start with an alphanumeric code. Remove whitespace. Build a regex that
        scrubs the code.

        Particular examples: postcodes, e.g. ``"PE12 3AB"``.

        Args:
            value: a string containing containing an alphanumeric code

        Returns:
            a list of regex elements
        """
        return get_code_regex_elements(
            reduce_to_alphanumeric(str(value)),
            at_word_boundaries_only=(
                self.anonymise_codes_at_word_boundaries_only
            ),
            at_numeric_boundaries_only=(
                self.anonymise_codes_at_numeric_boundaries_only
            ),
        )

    def get_patient_regex_string(self) -> str:
        """
        Return the string version of the patient regex, sorted.
        """
        return get_regex_string_from_elements(self.re_patient_elements)

    def get_tp_regex_string(self) -> str:
        """
        Return the string version of the third-party regex, sorted.
        """
        return get_regex_string_from_elements(self.re_tp_elements)

    def build_regexes(self) -> None:
        """
        Compile our regexes.
        """
        self.re_patient = get_regex_from_elements(self.re_patient_elements)
        self.re_tp = get_regex_from_elements(self.re_tp_elements)
        self.regexes_built = True
        # Note that the regexes themselves may be None even if they have
        # been built.
        if self.debug:
            log.debug(f"Patient scrubber: {self.get_patient_regex_string()}")
            log.debug(f"Third party scrubber: {self.get_tp_regex_string()}")

    def scrub(self, text: str) -> Optional[str]:
        # docstring in parent class
        if text is None:
            return None
        if not self.regexes_built:
            self.build_regexes()

        # If nonspecific_scrubber_first:
        #   (1) nonspecific, (2) patient, (3) third party.
        # Otherwise:
        #   (1) patient, (2) third party, (3) nonspecific.
        if self.nonspecific_scrubber and self.nonspecific_scrubber_first:
            text = self.nonspecific_scrubber.scrub(text)
        if self.re_patient:
            text = self.re_patient.sub(self.replacement_text_patient, text)
        if self.re_tp:
            text = self.re_tp.sub(self.replacement_text_third_party, text)
        if self.nonspecific_scrubber and not self.nonspecific_scrubber_first:
            text = self.nonspecific_scrubber.scrub(text)
        return text

    def get_hash(self) -> str:
        # docstring in parent class
        return self.hasher.hash(self.get_raw_info())

    def get_raw_info(self) -> Dict[str, Any]:
        """
        Summarizes settings and (sensitive) data for this scrubber.

        This is both a summary for debugging and the basis for our
        change-detection hash (and for the latter reason we need order etc. to
        be consistent). For any information we put in here, changes will cause
        data to be re-scrubbed.

        Note that the hasher should be a secure one, because this is sensitive
        information.
        """
        # We use a list of tuples to make an OrderedDict.
        d = (
            (
                "anonymise_codes_at_word_boundaries_only",
                self.anonymise_codes_at_word_boundaries_only,
            ),
            (
                "anonymise_codes_at_numeric_boundaries_only",
                self.anonymise_codes_at_numeric_boundaries_only,
            ),
            (
                "anonymise_dates_at_word_boundaries_only",
                self.anonymise_dates_at_word_boundaries_only,
            ),
            (
                "anonymise_numbers_at_word_boundaries_only",
                self.anonymise_numbers_at_word_boundaries_only,
            ),
            (
                "anonymise_numbers_at_numeric_boundaries_only",
                self.anonymise_numbers_at_numeric_boundaries_only,
            ),
            (
                "anonymise_strings_at_word_boundaries_only",
                self.anonymise_strings_at_word_boundaries_only,
            ),
            (
                "min_string_length_for_errors",
                self.min_string_length_for_errors,
            ),
            (
                "min_string_length_to_scrub_with",
                self.min_string_length_to_scrub_with,
            ),
            ("scrub_string_suffixes", sorted(self.scrub_string_suffixes)),
            ("string_max_regex_errors", self.string_max_regex_errors),
            (
                "allowlist_hash",
                self.allowlist.get_hash() if self.allowlist else None,
            ),
            (
                "nonspecific_scrubber_hash",
                (
                    self.nonspecific_scrubber.get_hash()
                    if self.nonspecific_scrubber
                    else None
                ),
            ),
            ("elements", self.elements_tuplelist),
        )
        return OrderedDict(d)
