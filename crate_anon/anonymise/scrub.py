#!/usr/bin/env python3
# crate/anonymise/anon_scrub.py

"""
Scrubber classes for CRATE anonymiser.

Author: Rudolf Cardinal
Created at: 22 Nov 2015
Last update: 9 Mar 2016

Copyright/licensing:

    Copyright (C) 2015-2016 Rudolf Cardinal (rudolf@pobox.com).
    Department of Psychiatry, University of Cambridge.

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

"""

from collections import OrderedDict
import logging

from cardinal_pythonlib.rnc_datetime import (
    coerce_to_date,
)
from cardinal_pythonlib.rnc_db import (
    is_sqltype_date,
    is_sqltype_text_over_one_char,
)

from crate_anon.anonymise.constants import SCRUBMETHOD
from crate_anon.anonymise.anonregex import (
    get_anon_fragments_from_string,
    get_code_regex_elements,
    get_date_regex_elements,
    get_digit_string_from_vaguely_numeric_string,
    get_number_of_length_n_regex_elements,
    get_phrase_regex_elements,
    get_regex_from_elements,
    get_regex_string_from_elements,
    get_string_regex_elements,
    get_uk_postcode_regex_elements,
    reduce_to_alphanumeric,
)

log = logging.getLogger(__name__)


# =============================================================================
# Generic scrubber base class
# =============================================================================

class ScrubberBase(object):
    """Scrubber base class."""

    def __init__(self, hasher):
        """
        :param hasher: object implementing GenericHasher interface
        """
        self.hasher = hasher

    def scrub(self, text):
        """Returns a scrubbed version of the text."""
        raise NotImplementedError()

    def get_hash(self):
        """Returns a hash of the scrubber itself."""
        raise NotImplementedError()


# =============================================================================
# WordList -- this serves a dual function as a whitelist (is a word in the
# list?) and a blacklist (scrub text using the wordlist).
# =============================================================================

def lower_case_words_from_file(fileobj):
    for line in fileobj:
        for word in line.split():
            yield word.lower()


class WordList(ScrubberBase):
    def __init__(self, filenames=None, words=None,
                 replacement_text='[---]', hasher=None,
                 suffixes=None, at_word_boundaries_only=True, max_errors=0):
        filenames = filenames or []
        words = words or []

        super().__init__(hasher)
        self.replacement_text = replacement_text
        self.suffixes = suffixes
        self.at_word_boundaries_only = at_word_boundaries_only
        self.max_errors = max_errors
        self._regex = None
        self._cached_hash = None

        self.words = set()
        # Sets are faster than lists for "is x in s" operations:
        # http://stackoverflow.com/questions/2831212/python-sets-vs-lists
        for f in filenames:
            self.add_file(f, clear_cache=False)
        for w in words:
            self.add_word(w, clear_cache=False)

    def clear_cache(self):
        """Clear cached information."""
        self._regex = None
        self._cached_hash = None

    def add_word(self, word, clear_cache=True):
        if not word:
            return
        self.words.add(word.lower())
        if clear_cache:
            self.clear_cache()

    def add_file(self, filename, clear_cache=True):
        with open(filename) as f:
            wordgen = lower_case_words_from_file(f)
            for w in wordgen:
                self.words.add(w)
        if clear_cache:
            self.clear_cache()

    def contains(self, word):
        return word.lower() in self.words

    def get_hash(self):
        # A set is unordered.
        # We want the hash to be the same if we have the same words, even if
        # they were entered in a different order, so we need to sort:
        if not self._cached_hash:
            self._cached_hash = self.hasher.hash(sorted(self.words))
        return self._cached_hash

    def scrub(self, text):
        if not self._regex:
            self.build_regex()
        return self._regex.sub(self.replacement_text, text)

    def build_regex(self):
        elements = []
        for w in self.words:
            elements.extend(get_string_regex_elements(
                w,
                suffixes=self.suffixes,
                at_word_boundaries_only=self.at_word_boundaries_only,
                max_errors=self.max_errors
            ))
        self._regex = get_regex_from_elements(elements)


# =============================================================================
# NonspecificScrubber
# Scrubs a bunch of things that are independent of any patient-specific data,
# such as removing all UK postcodes, or numbers of a certain length.
# =============================================================================


class NonspecificScrubber(ScrubberBase):
    def __init__(self, replacement_text, hasher,
                 anonymise_codes_at_word_boundaries_only=True,
                 anonymise_numbers_at_word_boundaries_only=True,
                 blacklist=None,
                 scrub_all_numbers_of_n_digits=None,
                 scrub_all_uk_postcodes=False):
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

    def get_hash(self):
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

    def scrub(self, text):
        if not self._regex_built:
            self.build_regex()

        if self.blacklist:
            text = self.blacklist.scrub(text)
        if not self._regex:  # possible; may be blank
            return text
        return self._regex.sub(self.replacement_text, text)

    def build_regex(self):
        elements = []
        if self.scrub_all_uk_postcodes:
            elements.extend(
                get_uk_postcode_regex_elements(
                    at_word_boundaries_only=
                    self.anonymise_codes_at_word_boundaries_only))
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
    def __init__(self, replacement_text_patient,
                 replacement_text_third_party,
                 hasher,
                 anonymise_codes_at_word_boundaries_only=True,
                 anonymise_dates_at_word_boundaries_only=True,
                 anonymise_numbers_at_word_boundaries_only=True,
                 anonymise_strings_at_word_boundaries_only=True,
                 min_string_length_for_errors=4,
                 min_string_length_to_scrub_with=3,
                 scrub_string_suffixes=None,
                 string_max_regex_errors=0,
                 whitelist=None,
                 nonspecific_scrubber=None,
                 debug=False):
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

    def clear_cache(self):
        self.regexes_built = False

    @staticmethod
    def get_scrub_method(datatype_long, scrub_method):
        """
        Return the default scrub method for a given SQL datatype,
        unless overridden.
        """
        if scrub_method:
            return scrub_method
        elif is_sqltype_date(datatype_long):
            return SCRUBMETHOD.DATE
        elif is_sqltype_text_over_one_char(datatype_long):
            return SCRUBMETHOD.WORDS
        else:
            return SCRUBMETHOD.NUMERIC

    def add_value(self, value, scrub_method, patient=True, clear_cache=True):
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

        if scrub_method == SCRUBMETHOD.DATE:
            elements = self.get_elements_date(value)
        elif scrub_method == SCRUBMETHOD.WORDS:
            elements = self.get_elements_words(value)
        elif scrub_method == SCRUBMETHOD.PHRASE:
            elements = self.get_elements_phrase(value)
        elif scrub_method == SCRUBMETHOD.NUMERIC:
            elements = self.get_elements_numeric(value)
        elif scrub_method == SCRUBMETHOD.CODE:
            elements = self.get_elements_code(value)
        else:
            raise ValueError("Bug: unknown scrub_method to add_value")
        r.update(set(elements))  # remembering r is a set, not a list
        if clear_cache:
            self.clear_cache()

    def get_elements_date(self, value):
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

    def get_elements_words(self, value):
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

    def get_elements_phrase(self, value):
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

    def get_elements_numeric(self, value):
        # Source is a text field containing a number, or an actual number.
        # Remove everything but the digits
        # Particular examples: phone numbers, e.g. "(01223) 123456".
        return get_code_regex_elements(
            get_digit_string_from_vaguely_numeric_string(str(value)),
            at_word_boundaries_only=(
                self.anonymise_numbers_at_word_boundaries_only)
        )

    def get_elements_code(self, value):
        # Source is a text field containing an alphanumeric code.
        # Remove whitespace.
        # Particular examples: postcodes, e.g. "PE12 3AB".
        return get_code_regex_elements(
            reduce_to_alphanumeric(str(value)),
            at_word_boundaries_only=(
                self.anonymise_codes_at_word_boundaries_only)
        )

    def get_patient_regex_string(self):
        """Return the string version of the patient regex, sorted."""
        return get_regex_string_from_elements(sorted(self.re_patient_elements))

    def get_tp_regex_string(self):
        """Return the string version of the third-party regex, sorted."""
        return get_regex_string_from_elements(sorted(self.re_tp_elements))

    def build_regexes(self):
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

    def scrub(self, text):
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

    def get_hash(self):
        return self.hasher.hash(self.get_raw_info())

    def get_raw_info(self):
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
