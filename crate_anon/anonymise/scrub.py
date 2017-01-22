#!/usr/bin/env python
# crate_anon/anonymise/scrub.py

"""
===============================================================================
    Copyright (C) 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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

Scrubber classes for CRATE anonymiser.
"""

from collections import OrderedDict
import datetime
import logging
from typing import Any, Dict, Iterable, Generator, List, Optional, Union

from cardinal_pythonlib.rnc_datetime import (
    coerce_to_date,
)
from cardinal_pythonlib.rnc_db import (
    is_sqltype_date,
    is_sqltype_text_over_one_char,
)

from crate_anon.common.hash import GenericHasher
from crate_anon.anonymise.constants import SCRUBMETHOD
from crate_anon.anonymise.anonregex import (
    get_anon_fragments_from_string,
    get_code_regex_elements,
    get_date_regex_elements,
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

class ScrubberBase(object):
    """Scrubber base class."""

    def __init__(self, hasher: GenericHasher) -> None:
        """
        :param hasher: object implementing GenericHasher interface
        """
        self.hasher = hasher

    def scrub(self, text: str) -> str:
        """Returns a scrubbed version of the text."""
        raise NotImplementedError()

    def get_hash(self) -> str:
        """Returns a hash of the scrubber itself."""
        raise NotImplementedError()


# =============================================================================
# WordList -- this serves a dual function as a whitelist (is a word in the
# list?) and a blacklist (scrub text using the wordlist).
# =============================================================================

def lower_case_words_from_file(fileobj: Iterable[str]) -> Generator[str, None,
                                                                    None]:
    for line in fileobj:
        for word in line.split():
            yield word.lower()


class WordList(ScrubberBase):
    def __init__(self,
                 filenames: Iterable[str] = None,
                 words: Iterable[str] = None,
                 replacement_text: str = '[---]',
                 hasher: GenericHasher = None,
                 suffixes: List[str] = None,
                 at_word_boundaries_only: bool = True,
                 max_errors: int = 0) -> None:
        filenames = filenames or []
        words = words or []

        super().__init__(hasher)
        self.replacement_text = replacement_text
        self.suffixes = suffixes
        self.at_word_boundaries_only = at_word_boundaries_only
        self.max_errors = max_errors
        self._regex = None
        self._cached_hash = None
        self._regex_built = False

        self.words = set()
        # Sets are faster than lists for "is x in s" operations:
        # http://stackoverflow.com/questions/2831212/python-sets-vs-lists
        # noinspection PyTypeChecker
        for f in filenames:
            self.add_file(f, clear_cache=False)
        # noinspection PyTypeChecker
        for w in words:
            self.add_word(w, clear_cache=False)

    def clear_cache(self) -> None:
        """Clear cached information."""
        self._regex = None
        self._cached_hash = None

    def add_word(self, word: str, clear_cache: bool = True) -> None:
        if not word:
            return
        self.words.add(word.lower())
        if clear_cache:
            self.clear_cache()

    def add_file(self, filename: str, clear_cache: bool = True) -> None:
        with open(filename) as f:
            wordgen = lower_case_words_from_file(f)
            for w in wordgen:
                self.words.add(w)
        if clear_cache:
            self.clear_cache()

    def contains(self, word: str) -> bool:
        return word.lower() in self.words

    def get_hash(self) -> str:
        # A set is unordered.
        # We want the hash to be the same if we have the same words, even if
        # they were entered in a different order, so we need to sort:
        if not self._cached_hash:
            self._cached_hash = self.hasher.hash(sorted(self.words))
        return self._cached_hash

    def scrub(self, text: str) -> str:
        if not self._regex_built:
            self.build_regex()
        if not self._regex:
            return text
        return self._regex.sub(self.replacement_text, text)

    def build_regex(self) -> None:
        elements = []
        for w in self.words:
            elements.extend(get_string_regex_elements(
                w,
                suffixes=self.suffixes,
                at_word_boundaries_only=self.at_word_boundaries_only,
                max_errors=self.max_errors
            ))
        self._regex = get_regex_from_elements(elements)
        self._regex_built = True


# =============================================================================
# NonspecificScrubber
# Scrubs a bunch of things that are independent of any patient-specific data,
# such as removing all UK postcodes, or numbers of a certain length.
# =============================================================================

class NonspecificScrubber(ScrubberBase):
    def __init__(self,
                 replacement_text: str,
                 hasher: GenericHasher,
                 anonymise_codes_at_word_boundaries_only: bool = True,
                 anonymise_numbers_at_word_boundaries_only: bool = True,
                 blacklist: WordList = None,
                 scrub_all_numbers_of_n_digits: List[int] = None,
                 scrub_all_uk_postcodes: bool = False) -> None:
        """
        scrub_all_numbers_of_n_digits: list of values of n
        """
        scrub_all_numbers_of_n_digits = scrub_all_numbers_of_n_digits or []

        super().__init__(hasher)
        self.replacement_text = replacement_text
        self.anonymise_codes_at_word_boundaries_only = (
            anonymise_codes_at_word_boundaries_only)
        self.anonymise_numbers_at_word_boundaries_only = (
            anonymise_numbers_at_word_boundaries_only)
        self.blacklist = blacklist
        self.scrub_all_numbers_of_n_digits = scrub_all_numbers_of_n_digits
        self.scrub_all_uk_postcodes = scrub_all_uk_postcodes

        self._cached_hash = None
        self._regex = None
        self._regex_built = False
        self.build_regex()

    def get_hash(self) -> str:
        if not self._cached_hash:
            self._cached_hash = self.hasher.hash([
                # signature, used for hashing:
                self.anonymise_codes_at_word_boundaries_only,
                self.anonymise_numbers_at_word_boundaries_only,
                self.blacklist.get_hash() if self.blacklist else None,
                self.scrub_all_numbers_of_n_digits,
                self.scrub_all_uk_postcodes,
            ])
        return self._cached_hash

    def scrub(self, text: str) -> str:
        if not self._regex_built:
            self.build_regex()
        if self.blacklist:
            text = self.blacklist.scrub(text)
        if not self._regex:  # possible; may be blank
            return text
        return self._regex.sub(self.replacement_text, text)

    def build_regex(self) -> None:
        elements = []
        if self.scrub_all_uk_postcodes:
            elements.extend(
                get_uk_postcode_regex_elements(
                    at_word_boundaries_only=
                    self.anonymise_codes_at_word_boundaries_only))
        # noinspection PyTypeChecker
        for n in self.scrub_all_numbers_of_n_digits:
            elements.extend(get_number_of_length_n_regex_elements(
                n,
                at_word_boundaries_only=(
                    self.anonymise_numbers_at_word_boundaries_only)
            ))
        self._regex = get_regex_from_elements(elements)
        self._regex_built = True


# =============================================================================
# PersonalizedScrubber
# =============================================================================

class PersonalizedScrubber(ScrubberBase):
    """Accepts patient-specific (patient and third-party) information, and
    uses that to scrub text."""
    def __init__(self,
                 replacement_text_patient: str,
                 replacement_text_third_party: str,
                 hasher: GenericHasher,
                 anonymise_codes_at_word_boundaries_only: bool = True,
                 anonymise_dates_at_word_boundaries_only: bool = True,
                 anonymise_numbers_at_word_boundaries_only: bool = True,
                 anonymise_numbers_at_numeric_boundaries_only: bool = True,
                 anonymise_strings_at_word_boundaries_only: bool = True,
                 min_string_length_for_errors: int = 4,
                 min_string_length_to_scrub_with: int = 3,
                 scrub_string_suffixes: List[str] = None,
                 string_max_regex_errors: int = 0,
                 whitelist: WordList = None,
                 nonspecific_scrubber: NonspecificScrubber = None,
                 debug: bool = False) -> None:
        scrub_string_suffixes = scrub_string_suffixes or []

        super().__init__(hasher)
        self.replacement_text_patient = replacement_text_patient
        self.replacement_text_third_party = replacement_text_third_party
        self.anonymise_codes_at_word_boundaries_only = (
            anonymise_codes_at_word_boundaries_only)
        self.anonymise_dates_at_word_boundaries_only = (
            anonymise_dates_at_word_boundaries_only)
        self.anonymise_numbers_at_word_boundaries_only = (
            anonymise_numbers_at_word_boundaries_only)
        self.anonymise_numbers_at_numeric_boundaries_only = (
            anonymise_numbers_at_numeric_boundaries_only)
        self.anonymise_strings_at_word_boundaries_only = (
            anonymise_strings_at_word_boundaries_only)
        self.min_string_length_for_errors = min_string_length_for_errors
        self.min_string_length_to_scrub_with = min_string_length_to_scrub_with
        self.scrub_string_suffixes = scrub_string_suffixes
        self.string_max_regex_errors = string_max_regex_errors
        self.whitelist = whitelist
        self.nonspecific_scrubber = nonspecific_scrubber
        self.debug = debug

        # Regex information
        self.re_patient = None  # re: regular expression
        self.re_tp = None
        self.regexes_built = False
        self.re_patient_elements = set()
        self.re_tp_elements = set()
        self.elements_tupleset = set()  # patient?, type, value
        self.clear_cache()

    def clear_cache(self) -> None:
        self.regexes_built = False

    @staticmethod
    def get_scrub_method(datatype_long: str,
                         scrub_method: Optional[SCRUBMETHOD]) -> SCRUBMETHOD:
        """
        Return the default scrub method for a given SQL datatype,
        unless overridden.
        """
        if scrub_method is not None:
            return scrub_method
        elif is_sqltype_date(datatype_long):
            return SCRUBMETHOD.DATE
        elif is_sqltype_text_over_one_char(datatype_long):
            return SCRUBMETHOD.WORDS
        else:
            return SCRUBMETHOD.NUMERIC

    def add_value(self,
                  value: Any,
                  scrub_method: SCRUBMETHOD,
                  patient: bool = True,
                  clear_cache: bool = True) -> None:
        """
        Add a specific value via a specific scrub_method.

        The patient flag controls whether it's treated as a patient value or
        a third-party value.
        """
        if value is None:
            return
        self.elements_tupleset.add((patient, scrub_method, repr(value)))
        # Note: object reference
        r = self.re_patient_elements if patient else self.re_tp_elements

        if scrub_method is SCRUBMETHOD.DATE:
            elements = self.get_elements_date(value)
        elif scrub_method is SCRUBMETHOD.WORDS:
            elements = self.get_elements_words(value)
        elif scrub_method is SCRUBMETHOD.PHRASE:
            elements = self.get_elements_phrase(value)
        elif scrub_method is SCRUBMETHOD.NUMERIC:
            elements = self.get_elements_numeric(value)
        elif scrub_method is SCRUBMETHOD.CODE:
            elements = self.get_elements_code(value)
        else:
            raise ValueError("Bug: unknown scrub_method to add_value: "
                             "{}".format(scrub_method))
        r.update(set(elements))  # remembering r is a set, not a list
        if clear_cache:
            self.clear_cache()

    def get_elements_date(self,
                          value: Union[datetime.datetime,
                                       datetime.date]) -> Optional[List[str]]:
        # Source is a date.
        try:
            value = coerce_to_date(value)
        except Exception as e:
            log.warning(
                "Invalid date received to PersonalizedScrubber."
                "get_elements_date(): value={}, exception={}".format(
                    value, e))
            return
        return get_date_regex_elements(
            value,
            at_word_boundaries_only=(
                self.anonymise_dates_at_word_boundaries_only)
        )

    def get_elements_words(self, value: str) -> List[str]:
        # Source is a string containing textual words.
        elements = []
        for s in get_anon_fragments_from_string(str(value)):
            l = len(s)
            if l < self.min_string_length_to_scrub_with:
                # With numbers: if you use the length limit, you may see
                # numeric parts of addresses, e.g. 4 Drury Lane as
                # 4 [___] [___]. However, if you exempt numbers then you
                # mess up a whole bunch of quantitative information, such
                # as "the last 4-5 years" getting wiped to "the last
                # [___]-5 years". So let's apply the length limit
                # consistently.
                continue
            if self.whitelist and self.whitelist.contains(s):
                continue
            if l >= self.min_string_length_for_errors:
                max_errors = self.string_max_regex_errors
            else:
                max_errors = 0
            elements.extend(get_string_regex_elements(
                s,
                self.scrub_string_suffixes,
                max_errors=max_errors,
                at_word_boundaries_only=(
                    self.anonymise_strings_at_word_boundaries_only)
            ))
        return elements

    def get_elements_phrase(self, value: Any) -> List[str]:
        # value = unicode(value)  # Python 2
        value = str(value)
        if not value:
            return []
        l = len(value)
        if l < self.min_string_length_to_scrub_with:
            return []
        if self.whitelist and self.whitelist.contains(value):
            return []
        if l >= self.min_string_length_for_errors:
            max_errors = self.string_max_regex_errors
        else:
            max_errors = 0
        return get_phrase_regex_elements(
            value,
            max_errors=max_errors,
            at_word_boundaries_only=(
                self.anonymise_strings_at_word_boundaries_only)
        )

    def get_elements_numeric(self, value: Any) -> List[str]:
        # Source is a text field containing a number, or an actual number.
        # Remove everything but the digits
        # Particular examples: phone numbers, e.g. "(01223) 123456".
        return get_code_regex_elements(
            get_digit_string_from_vaguely_numeric_string(str(value)),
            at_word_boundaries_only=(
                self.anonymise_numbers_at_word_boundaries_only),
            at_numeric_boundaries_only=(
                self.anonymise_numbers_at_numeric_boundaries_only)
        )

    def get_elements_code(self, value: Any) -> List[str]:
        # Source is a text field containing an alphanumeric code.
        # Remove whitespace.
        # Particular examples: postcodes, e.g. "PE12 3AB".
        return get_code_regex_elements(
            reduce_to_alphanumeric(str(value)),
            at_word_boundaries_only=(
                self.anonymise_codes_at_word_boundaries_only)
        )

    def get_patient_regex_string(self) -> str:
        """Return the string version of the patient regex, sorted."""
        return get_regex_string_from_elements(sorted(self.re_patient_elements))

    def get_tp_regex_string(self) -> str:
        """Return the string version of the third-party regex, sorted."""
        return get_regex_string_from_elements(sorted(self.re_tp_elements))

    def build_regexes(self) -> None:
        self.re_patient = get_regex_from_elements(
            list(self.re_patient_elements))
        self.re_tp = get_regex_from_elements(
            list(self.re_tp_elements))
        self.regexes_built = True
        # Note that the regexes themselves may be None even if they have
        # been built.
        if self.debug:
            log.debug("Patient scrubber: {}".format(
                self.get_patient_regex_string()))
            log.debug("Third party scrubber: {}".format(
                self.get_tp_regex_string()))

    def scrub(self, text: str) -> Optional[str]:
        """Scrub some text and return the scrubbed result."""
        if text is None:
            return None
        if not self.regexes_built:
            self.build_regexes()

        if self.nonspecific_scrubber:
            text = self.nonspecific_scrubber.scrub(text)
        if self.re_patient:
            text = self.re_patient.sub(self.replacement_text_patient, text)
        if self.re_tp:
            text = self.re_tp.sub(self.replacement_text_third_party, text)
        return text

    def get_hash(self) -> str:
        return self.hasher.hash(self.get_raw_info())

    def get_raw_info(self) -> Dict[str, Any]:
        # This is both a summary for debugging and the basis for our
        # change-detection hash (and for the latter reason we need order etc.
        # to be consistent). For anything we put in here, changes will cause
        # data to be re-scrubbed.
        # We use a list of tuples to make the OrderedDict:
        d = (
            ('anonymise_codes_at_word_boundaries_only',
             self.anonymise_codes_at_word_boundaries_only),
            ('anonymise_dates_at_word_boundaries_only',
             self.anonymise_dates_at_word_boundaries_only),
            ('anonymise_numbers_at_word_boundaries_only',
             self.anonymise_numbers_at_word_boundaries_only),
            ('anonymise_strings_at_word_boundaries_only',
             self.anonymise_strings_at_word_boundaries_only),
            ('min_string_length_for_errors',
             self.min_string_length_for_errors),
            ('min_string_length_to_scrub_with',
             self.min_string_length_to_scrub_with),
            ('scrub_string_suffixes', sorted(self.scrub_string_suffixes)),
            ('string_max_regex_errors', self.string_max_regex_errors),
            ('whitelist_hash',
             self.whitelist.get_hash() if self.whitelist else None),
            ('nonspecific_scrubber_hash',
             self.nonspecific_scrubber.get_hash() if self.nonspecific_scrubber
             else None),
            ('elements', sorted(self.elements_tupleset)),
        )
        return OrderedDict(d)
