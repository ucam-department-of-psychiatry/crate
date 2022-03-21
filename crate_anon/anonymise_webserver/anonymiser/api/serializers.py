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
from typing import List, Optional

from django.conf import settings

from cardinal_pythonlib.hash import GenericHasher, make_hasher
from rest_framework.serializers import (
    BooleanField,
    CharField,
    IntegerField,
    ListField,
    Serializer,
    SerializerMethodField,
)

from crate_anon.anonymise.constants import SCRUBMETHOD
from crate_anon.anonymise.scrub import (
    NonspecificScrubber,
    PersonalizedScrubber,
    WordList,
)


class SpecificSerializer(Serializer):
    dates = ListField(child=CharField(), required=False)
    phrases = ListField(child=CharField(), required=False)
    words = ListField(child=CharField(), required=False)
    numbers = ListField(child=CharField(), required=False)
    codes = ListField(child=CharField(), required=False)


class AllowlistSerializer(Serializer):
    words = ListField(child=CharField(), required=False, write_only=True)


class DenylistSerializer(Serializer):
    words = ListField(child=CharField(), required=False, write_only=True)


class ScrubSerializer(Serializer):
    # Input fields. write_only means they aren't returned in the response
    text = CharField(write_only=True)
    patient = SpecificSerializer(required=False, write_only=True)
    third_party = SpecificSerializer(required=False, write_only=True)
    anonymise_codes_at_word_boundaries_only = BooleanField(required=False,
                                                           write_only=True)
    anonymise_dates_at_word_boundaries_only = BooleanField(required=False,
                                                           write_only=True)
    # TODO: These can't both be True (in fact this is the default for
    # PersonalizedScrubber but word boundaries take precedence).
    anonymise_numbers_at_word_boundaries_only = BooleanField(required=False,
                                                             write_only=True)
    anonymise_numbers_at_numeric_boundaries_only = BooleanField(required=False,
                                                                write_only=True)
    anonymise_strings_at_word_boundaries_only = BooleanField(required=False,
                                                             write_only=True)
    string_max_regex_errors = IntegerField(required=False, write_only=True)
    min_string_length_for_errors = IntegerField(required=False, write_only=True)
    min_string_length_to_scrub_with = IntegerField(required=False,
                                                   write_only=True)
    scrub_string_suffixes = ListField(child=CharField(), required=False,
                                      write_only=True)
    allowlist = AllowlistSerializer(required=False, write_only=True)
    denylist = DenylistSerializer(required=False, write_only=True)
    replace_nonspecific_info_with = CharField(required=False, write_only=True)
    replace_patient_info_with = CharField(required=False, write_only=True)
    replace_third_party_info_with = CharField(required=False, write_only=True)
    scrub_all_numbers_of_n_digits = ListField(child=IntegerField(),
                                              required=False, write_only=True)
    scrub_all_uk_postcodes = BooleanField(required=False, write_only=True)
    alternatives = ListField(child=ListField(), required=False, write_only=True)

    # Output fields
    anonymised = SerializerMethodField()  # Read-only by default

    def get_anonymised(self, data: OrderedDict) -> str:
        scrubber = self._get_personalized_scrubber(data)

        return scrubber.scrub(data["text"])

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

        replacement_text_patient = data.get("replace_patient_info_with",
                                            "[__PPP__]")
        replacement_text_third_party = data.get("replace_third_party_info_with",
                                                "[__TTT__]")

        scrubber = PersonalizedScrubber(
            replacement_text_patient,
            replacement_text_third_party,
            hasher,
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
            return WordList(words=data["allowlist"]["words"],
                            hasher=hasher)
        except KeyError:
            return None

    def _get_nonspecific_scrubber(self,
                                  data: OrderedDict,
                                  hasher: GenericHasher) -> NonspecificScrubber:
        denylist = self._get_denylist(data, hasher)
        options = (
            "scrub_all_numbers_of_n_digits",
            "scrub_all_uk_postcodes",
            "anonymise_codes_at_word_boundaries_only",
            "anonymise_numbers_at_word_boundaries_only",
        )
        kwargs = {k: v for (k, v) in data.items() if k in options}

        # TODO: extra_regexes (might be a security no-no)
        return NonspecificScrubber("[---]",  # TODO configure
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

            # TODO:
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
            "dates": SCRUBMETHOD.DATE,
            "phrases": SCRUBMETHOD.PHRASE,
            "words": SCRUBMETHOD.WORDS,
            "numbers": SCRUBMETHOD.NUMERIC,
            "codes": SCRUBMETHOD.CODE,
        }

        is_patient = label == "patient"

        for name, values in data[label].items():
            method = method_lookup[name]
            for value in values:
                scrubber.add_value(value, method, patient=is_patient)
