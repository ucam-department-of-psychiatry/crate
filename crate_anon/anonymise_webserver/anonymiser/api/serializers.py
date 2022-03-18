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

from django.conf import settings

from cardinal_pythonlib.hash import make_hasher
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

    # Output fields
    anonymised = SerializerMethodField()  # Read-only by default

    def get_anonymised(self, data: OrderedDict) -> str:
        hasher = make_hasher("HMAC_MD5", settings.HASH_KEY)

        try:
            allowlist = WordList(words=data["allowlist"]["words"],
                                 hasher=hasher)
        except KeyError:
            allowlist = None

        try:
            denylist = WordList(words=data["denylist"]["words"],
                                hasher=hasher)
        except KeyError:
            denylist = None

        nonspecific_scrubber = NonspecificScrubber("[---]",  # TODO configure
                                                   hasher,
                                                   denylist=denylist)

        options = (
            "anonymise_codes_at_word_boundaries_only",
            "anonymise_dates_at_word_boundaries_only",
            "anonymise_numbers_at_word_boundaries_only",
            "anonymise_numbers_at_numeric_boundaries_only",
            "anonymise_strings_at_word_boundaries_only",
            "string_max_regex_errors",
            "min_string_length_for_errors",
            "min_string_length_to_scrub_with",
            "scrub_string_suffixes"
        )

        kwargs = {}

        for option in options:
            if option in data:
                kwargs[option] = data[option]

        scrubber = PersonalizedScrubber(
            "[PPP]",  # TODO configure
            "[TTT]",  # TODO configure
            hasher,
            nonspecific_scrubber=nonspecific_scrubber,
            allowlist=allowlist,
            **kwargs
        )

        for label in ("patient", "third_party"):
            if label in data:
                self._add_values_to_scrubber(scrubber, label, data)

        return scrubber.scrub(data["text"])

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
