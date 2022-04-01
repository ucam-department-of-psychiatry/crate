"""
crate_anon/anonymise_webserver/anonymiser/api/serializers.py

===============================================================================

    Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).

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

Django REST Framework serializer to anonymise the data.

"""


from collections import OrderedDict
from typing import Dict, List, Optional

from django.conf import settings

from cardinal_pythonlib.hash import GenericHasher, make_hasher
from rest_framework.serializers import (
    BooleanField,
    CharField,
    DictField,
    IntegerField,
    ListField,
    Serializer,
    SerializerMethodField,
)

from crate_anon.anonymise.constants import (
    AnonymiseConfigDefaults as Defaults,
    ScrubMethod
)
from crate_anon.anonymise.scrub import (
    NonspecificScrubber,
    PersonalizedScrubber,
    WordList,
)


class SpecificSerializer(Serializer):
    dates = ListField(child=CharField(), required=False,
                      help_text="List of dates to be scrubbed.")
    phrases = ListField(
        child=CharField(), required=False,
        help_text=("List of phrases (words appearing consecutively) to "
                   "be scrubbed.")
    )
    non_numeric_phrases = ListField(
        child=CharField(), required=False,
        help_text=("List of phrases (words appearing consecutively) to "
                   "be scrubbed. If a phrase is purely numeric it will be "
                   "ignored.")
    )
    words = ListField(child=CharField(), required=False,
                      help_text="List of words to be scrubbed.")
    numbers = ListField(child=CharField(), required=False,
                        help_text="List of numbers to be scrubbed.")
    codes = ListField(
        child=CharField(), required=False,
        help_text="List of codes (e.g. postcodes) to be scrubbed."
    )


class AllowlistSerializer(Serializer):
    words = ListField(child=CharField(), required=False, write_only=True,
                      help_text="Do not scrub these specific words.")
    files = ListField(child=CharField(), required=False, write_only=True,
                      help_text=("Do not scrub words from these files "
                                 "(aliased from Django settings)."))


class DenylistSerializer(Serializer):
    words = ListField(child=CharField(), required=False, write_only=True,
                      help_text="Scrub these specific words.")


class ScrubSerializer(Serializer):
    # Input fields
    # write_only means they aren't returned in the response
    # default implies required=False
    text = DictField(
        child=CharField(help_text=("Text to be scrubbed")), write_only=True,
        help_text=("The lines of text to be scrubbed, each keyed on a unique "
                   "ID supplied by the caller")
    )
    patient = SpecificSerializer(
        required=False, write_only=True,
        help_text="Specific patient data to be scrubbed."
    )
    third_party = SpecificSerializer(
        required=False, write_only=True,
        help_text="Third party (e.g. family members') data to be scrubbed."
    )
    anonymise_codes_at_word_boundaries_only = BooleanField(
        write_only=True,
        default=Defaults.ANONYMISE_CODES_AT_WORD_BOUNDARIES_ONLY,
        help_text=("Ensure the codes to be scrubbed begin and end with a word "
                   "boundary.")
    )
    anonymise_dates_at_word_boundaries_only = BooleanField(
        write_only=True,
        default=Defaults.ANONYMISE_DATES_AT_WORD_BOUNDARIES_ONLY,
        help_text=("Ensure the codes to be scrubbed begin and end with a word "
                   "boundary.")
    )
    # TODO: These can't both be True (in fact this is the default for
    # PersonalizedScrubber but word boundaries take precedence).
    anonymise_numbers_at_word_boundaries_only = BooleanField(
        write_only=True,
        default=Defaults.ANONYMISE_NUMBERS_AT_WORD_BOUNDARIES_ONLY,
        help_text=("Ensure the numbers to be scrubbed begin and end with a "
                   "word boundary.")
    )
    anonymise_numbers_at_numeric_boundaries_only = BooleanField(
        write_only=True,
        default=Defaults.ANONYMISE_NUMBERS_AT_NUMERIC_BOUNDARIES_ONLY,
        help_text=("Ensure the numbers to be scrubbed begin and end with a "
                   "numeric boundary.")
    )
    anonymise_strings_at_word_boundaries_only = BooleanField(
        write_only=True,
        default=Defaults.ANONYMISE_STRINGS_AT_WORD_BOUNDARIES_ONLY,
        help_text=("Ensure the numbers to be scrubbed begin and end with a "
                   "word boundary.")
    )
    string_max_regex_errors = IntegerField(
        write_only=True, default=Defaults.STRING_MAX_REGEX_ERRORS,
        help_text=("The maximum number of typographical insertion / deletion / "
                   "substitution errors to permit.")
    )
    min_string_length_for_errors = IntegerField(
        write_only=True, default=Defaults.MIN_STRING_LENGTH_FOR_ERRORS,
        help_text=("The minimum string length at which typographical "
                   "errors will be permitted.")
    )
    min_string_length_to_scrub_with = IntegerField(
        write_only=True, default=Defaults.MIN_STRING_LENGTH_TO_SCRUB_WITH,
        help_text=("Do not scrub strings shorter than this length.")
    )
    scrub_string_suffixes = ListField(
        child=CharField(), required=False,
        write_only=True,
        help_text=('A list of suffixes to permit on strings. e.g. ["s"] '
                   'for plural forms.')
    )
    allowlist = AllowlistSerializer(required=False, write_only=True,
                                    help_text="Allowlist options.")
    denylist = DenylistSerializer(required=False, write_only=True,
                                  help_text="Denylist options.")
    replace_patient_info_with = CharField(
        write_only=True, default=Defaults.REPLACE_PATIENT_INFO_WITH,
        help_text=("Replace sensitive patient content with this.")
    )
    replace_third_party_info_with = CharField(
        write_only=True, default=Defaults.REPLACE_THIRD_PARTY_INFO_WITH,
        help_text=("Replace sensitive third party (e.g. family members') "
                   "content with this.")
    )
    replace_nonspecific_info_with = CharField(
        write_only=True, default=Defaults.REPLACE_NONSPECIFIC_INFO_WITH,
        help_text=("Replace any other sensitive content with this.")
    )
    scrub_all_numbers_of_n_digits = ListField(
        child=IntegerField(),
        required=False, write_only=True,
        help_text=("Scrub all numbers with these lengths. "
                   "e.g. [10] for all UK NHS numbers.")
    )
    scrub_all_uk_postcodes = BooleanField(
        write_only=True, default=Defaults.SCRUB_ALL_UK_POSTCODES,
        help_text=("Scrub all UK postcodes.")
    )
    scrub_all_dates = BooleanField(
        write_only=True, default=Defaults.SCRUB_ALL_DATES,
        help_text=("Scrub all dates. Currently assumes the default locale "
                   "for month names and ordinal suffixes.")
    )
    alternatives = ListField(
        child=ListField(child=CharField()),
        required=False, write_only=True,
        help_text=(
            'List of alternative words to scrub. '
            'e.g.: [["Street", "St"], ["Road", "Rd"], ["Avenue", "Ave"]]'
        )
    )

    # Output fields
    # SerializerMethodField is read-only by default
    anonymised = SerializerMethodField(
        help_text=("The anonymised text, keyed on the unique IDs supplied by "
                   "the caller in the 'text' parameter of the request.")
    )

    def get_anonymised(self, data: OrderedDict) -> Dict[str, str]:
        """
        Returns the anonymised text keyed on the unique IDs supplied by the
        caller.
        """
        scrubber = self._get_personalized_scrubber(data)

        anonymised = dict()

        for key, value in data["text"].items():
            anonymised[key] = scrubber.scrub(value)

        return anonymised

    def _get_personalized_scrubber(self,
                                   data: OrderedDict) -> PersonalizedScrubber:
        hasher = make_hasher("HMAC_MD5", settings.HASH_KEY)

        options = (
            "anonymise_codes_at_word_boundaries_only",
            "anonymise_dates_at_word_boundaries_only",
            "anonymise_numbers_at_word_boundaries_only",
            "anonymise_numbers_at_numeric_boundaries_only",
            "anonymise_strings_at_word_boundaries_only",
            "string_max_regex_errors",
            "min_string_length_for_errors",
            "min_string_length_to_scrub_with",
            "scrub_string_suffixes",
        )

        kwargs = {k: v for (k, v) in data.items() if k in options}

        replacement_text_patient = data["replace_patient_info_with"]
        replacement_text_third_party = data["replace_third_party_info_with"]

        scrubber = PersonalizedScrubber(
            hasher,
            replacement_text_patient,
            replacement_text_third_party,
            nonspecific_scrubber=self._get_nonspecific_scrubber(data, hasher),
            allowlist=self._get_allowlist(data, hasher),
            alternatives=self._get_alternatives(data),
            **kwargs
        )

        for label in ("patient", "third_party"):
            if label in data:
                self._add_values_to_scrubber(scrubber, label, data)

        return scrubber

    def _get_alternatives(self, data: OrderedDict) -> List[List[str]]:
        try:
            return [[word.upper() for word in words]
                    for words in data["alternatives"]]
        except KeyError:
            return None

    def _get_allowlist(self,
                       data: OrderedDict,
                       hasher: GenericHasher) -> Optional[WordList]:

        try:
            allowlist_data = data["allowlist"]
        except KeyError:
            return None

        options = ("words",)

        try:
            kwargs = {k: v for (k, v) in allowlist_data.items()
                      if k in options}
        except KeyError:
            return None

        try:
            files = allowlist_data["files"]
            filename_lookup = settings.CRATE["ALLOWLIST_FILENAMES"]

            filenames = [filename for label, filename in filename_lookup.items()
                         if label in files]
            kwargs.update(filenames=filenames)
        except KeyError:
            pass

        return WordList(hasher=hasher, **kwargs)

    def _get_nonspecific_scrubber(self,
                                  data: OrderedDict,
                                  hasher: GenericHasher) -> NonspecificScrubber:
        denylist = self._get_denylist(data, hasher)
        options = (
            "scrub_all_numbers_of_n_digits",
            "scrub_all_uk_postcodes",
            "scrub_all_dates",
            "anonymise_codes_at_word_boundaries_only",
            "anonymise_numbers_at_word_boundaries_only",
        )
        kwargs = {k: v for (k, v) in data.items() if k in options}

        # TODO: extra_regexes (might be a security no-no)
        replacement_text = data["replace_nonspecific_info_with"]
        return NonspecificScrubber(replacement_text,
                                   hasher,
                                   denylist=denylist,
                                   **kwargs)

    def _get_denylist(self,
                      data: OrderedDict,
                      hasher: GenericHasher) -> Optional[WordList]:
        try:
            words = data["denylist"]["words"]
            kwargs = {}

            try:
                kwargs["replacement_text"] = data[
                    "replace_nonspecific_info_with"
                ]
            except KeyError:
                pass

            # TODO: None of these are currently configurable
            # from crate_anon/anonymise/config.py
            # Do we care about them here?
            # suffixes
            # at_word_boundaries_only (for regex_method=True)
            # max_errors
            # regex_method: True
            return WordList(words=words, hasher=hasher, **kwargs)
        except KeyError:
            return None

    def _add_values_to_scrubber(self,
                                scrubber: PersonalizedScrubber,
                                label: str,
                                data: OrderedDict) -> None:
        method_lookup = {
            "dates": ScrubMethod.DATE,
            "phrases": ScrubMethod.PHRASE,
            "non_numeric_phrases": ScrubMethod.PHRASE_UNLESS_NUMERIC,
            "words": ScrubMethod.WORDS,
            "numbers": ScrubMethod.NUMERIC,
            "codes": ScrubMethod.CODE,
        }

        is_patient = label == "patient"

        for name, values in data[label].items():
            method = method_lookup[name]
            for value in values:
                scrubber.add_value(value, method, patient=is_patient)
