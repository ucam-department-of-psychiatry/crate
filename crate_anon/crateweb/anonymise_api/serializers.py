"""
crate_anon/crateweb/anonymise_api/serializers.py

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
    DATE_BLURRING_DIRECTIVES_CSV,
    ScrubMethod,
)
from crate_anon.anonymise.scrub import (
    NonspecificScrubber,
    PersonalizedScrubber,
    WordList,
)


class SpecificSerializer(Serializer):
    """
    Represents scrubbing information about a specific person or group of people
    (e.g. patient data, third-party data).
    """

    dates = ListField(
        child=CharField(),
        help_text="List of dates to be scrubbed.",
        default=[],
        initial=[],
    )
    phrases = ListField(
        child=CharField(),
        help_text=(
            "List of phrases (words appearing consecutively) to "
            "be scrubbed."
        ),
        default=[],
        initial=[],
    )
    non_numeric_phrases = ListField(
        child=CharField(),
        help_text=(
            "List of phrases (words appearing consecutively) to "
            "be scrubbed. If a phrase is purely numeric it will be "
            "ignored."
        ),
        default=[],
        initial=[],
    )
    words = ListField(
        child=CharField(),
        help_text="List of words to be scrubbed.",
        default=[],
        initial=[],
    )
    numbers = ListField(
        child=CharField(),
        help_text="List of numbers to be scrubbed.",
        default=[],
        initial=[],
    )
    codes = ListField(
        child=CharField(),
        help_text="List of codes (e.g. postcodes) to be scrubbed.",
        default=[],
        initial=[],
    )


class AllowlistSerializer(Serializer):
    """
    Represents allowlist options.
    """

    words = ListField(
        child=CharField(),
        help_text="Do not scrub these specific words.",
        default=[],
        initial=[],
    )
    files = ListField(
        child=CharField(),
        help_text=(
            "Do not scrub words from these filename aliases "
            "(defined on the server)."
        ),
        default=[],
        initial=[],
    )


class DenylistSerializer(Serializer):
    """
    Represents denylist options.
    """

    words = ListField(
        child=CharField(),
        help_text="Scrub these specific words.",
        default=[],
        initial=[],
    )
    files = ListField(
        child=CharField(),
        help_text=(
            "Scrub words from these filename aliases (defined on the server)."
        ),
        default=[],
        initial=[],
    )


class ScrubSerializer(Serializer):
    """
    Represents all scrubber settings, including data to be scrubbed and
    scrubber configuration settings.
    """

    # Input/Output fields
    # default implies required=False
    text = DictField(
        child=CharField(help_text="Text to be scrubbed."),
        help_text=(
            "The lines of text to be scrubbed, each keyed on a unique "
            "ID supplied by the caller."
        ),
    )
    patient = SpecificSerializer(
        required=False, help_text="Specific patient data to be scrubbed."
    )
    third_party = SpecificSerializer(
        required=False,
        help_text="Third party (e.g. family members') data to be scrubbed.",
    )
    anonymise_codes_at_word_boundaries_only = BooleanField(
        default=Defaults.ANONYMISE_CODES_AT_WORD_BOUNDARIES_ONLY,
        initial=Defaults.ANONYMISE_CODES_AT_WORD_BOUNDARIES_ONLY,
        help_text=(
            "Ensure the codes to be scrubbed begin and end with a word "
            "boundary."
        ),
    )
    anonymise_dates_at_word_boundaries_only = BooleanField(
        default=Defaults.ANONYMISE_DATES_AT_WORD_BOUNDARIES_ONLY,
        initial=Defaults.ANONYMISE_DATES_AT_WORD_BOUNDARIES_ONLY,
        help_text=(
            "Ensure the codes to be scrubbed begin and end with a word "
            "boundary."
        ),
    )
    anonymise_numbers_at_word_boundaries_only = BooleanField(
        default=Defaults.ANONYMISE_NUMBERS_AT_WORD_BOUNDARIES_ONLY,
        initial=Defaults.ANONYMISE_NUMBERS_AT_WORD_BOUNDARIES_ONLY,
        help_text=(
            "Ensure the numbers to be scrubbed begin and end with a "
            "word boundary."
        ),
    )
    anonymise_numbers_at_numeric_boundaries_only = BooleanField(
        default=Defaults.ANONYMISE_NUMBERS_AT_NUMERIC_BOUNDARIES_ONLY,
        initial=Defaults.ANONYMISE_NUMBERS_AT_NUMERIC_BOUNDARIES_ONLY,
        help_text=(
            "Ensure the numbers to be scrubbed begin and end with a "
            "numeric boundary."
        ),
    )
    anonymise_strings_at_word_boundaries_only = BooleanField(
        default=Defaults.ANONYMISE_STRINGS_AT_WORD_BOUNDARIES_ONLY,
        initial=Defaults.ANONYMISE_STRINGS_AT_WORD_BOUNDARIES_ONLY,
        help_text=(
            "Ensure the numbers to be scrubbed begin and end with a "
            "word boundary."
        ),
    )
    string_max_regex_errors = IntegerField(
        default=Defaults.STRING_MAX_REGEX_ERRORS,
        initial=Defaults.STRING_MAX_REGEX_ERRORS,
        help_text=(
            "The maximum number of typographical insertion/deletion/"
            "substitution errors to permit."
        ),
    )
    min_string_length_for_errors = IntegerField(
        default=Defaults.MIN_STRING_LENGTH_FOR_ERRORS,
        initial=Defaults.MIN_STRING_LENGTH_FOR_ERRORS,
        help_text=(
            "The minimum string length at which typographical "
            "errors will be permitted."
        ),
    )
    min_string_length_to_scrub_with = IntegerField(
        default=Defaults.MIN_STRING_LENGTH_TO_SCRUB_WITH,
        initial=Defaults.MIN_STRING_LENGTH_TO_SCRUB_WITH,
        help_text="Do not scrub strings shorter than this length.",
    )
    scrub_string_suffixes = ListField(
        child=CharField(),
        help_text=(
            'A list of suffixes to permit on strings. e.g. ["s"] '
            "for plural forms."
        ),
        default=[],
        initial=[],
    )
    allowlist = AllowlistSerializer(
        required=False, help_text="Allowlist options."
    )
    denylist = DenylistSerializer(
        required=False, help_text="Denylist options."
    )
    replace_patient_info_with = CharField(
        default=Defaults.REPLACE_PATIENT_INFO_WITH,
        initial=Defaults.REPLACE_PATIENT_INFO_WITH,
        help_text="Replace sensitive patient content with this.",
    )
    replace_third_party_info_with = CharField(
        default=Defaults.REPLACE_THIRD_PARTY_INFO_WITH,
        initial=Defaults.REPLACE_THIRD_PARTY_INFO_WITH,
        help_text=(
            "Replace sensitive third party (e.g. family members') "
            "content with this."
        ),
    )
    replace_nonspecific_info_with = CharField(
        default=Defaults.REPLACE_NONSPECIFIC_INFO_WITH,
        initial=Defaults.REPLACE_NONSPECIFIC_INFO_WITH,
        help_text="Replace any other sensitive content with this.",
    )
    replace_all_dates_with = CharField(
        required=False,
        help_text=(
            "When scrubbing all dates, replace with this text. If the "
            "replacement text includes supported datetime.directives "
            f"({DATE_BLURRING_DIRECTIVES_CSV}), the date is 'blurred' "
            "to include just those components."
        ),
    )
    scrub_all_numbers_of_n_digits = ListField(
        child=IntegerField(),
        help_text=(
            "Scrub all numbers with these lengths "
            "(e.g. [10] for all UK NHS numbers)."
        ),
        default=[],
        initial=[],
    )
    scrub_all_uk_postcodes = BooleanField(
        default=Defaults.SCRUB_ALL_UK_POSTCODES,
        initial=Defaults.SCRUB_ALL_UK_POSTCODES,
        help_text="Scrub all UK postcodes.",
    )
    scrub_all_dates = BooleanField(
        default=Defaults.SCRUB_ALL_DATES,
        initial=Defaults.SCRUB_ALL_DATES,
        help_text=(
            "Scrub all dates. Currently assumes the default locale "
            "for month names and ordinal suffixes."
        ),
    )
    alternatives = ListField(
        child=ListField(child=CharField()),
        help_text=(
            "List of alternative words to scrub. "
            'e.g.: [["Street", "St"], ["Road", "Rd"], ["Avenue", "Ave"]]'
        ),
        default=[[]],
        initial=[[]],
    )

    # Output-only fields
    # SerializerMethodField is read-only by default
    anonymised = SerializerMethodField(
        help_text=(
            "The anonymised text, keyed on the unique IDs supplied by "
            "the caller in the 'text' parameter of the request."
        )
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

    def _get_personalized_scrubber(
        self, data: OrderedDict
    ) -> PersonalizedScrubber:
        """
        Create a CRATE scrubber representing patient and third-party scrubbing
        settings.
        """
        hasher = make_hasher("HMAC_MD5", settings.ANONYMISE_API["HASH_KEY"])

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
            **kwargs,
        )

        for label in ("patient", "third_party"):
            if label in data:
                self._add_values_to_scrubber(scrubber, label, data)

        return scrubber

    @staticmethod
    def _get_alternatives(data: OrderedDict) -> Optional[List[List[str]]]:
        """
        Returns a list of list of equivalents; see
        :func:`crate_anon.anonymise.config.get_word_alternatives` and
        :class:`crate_anon.anonymise.scrub.PersonalizedScrubber`.
        """
        try:
            return [
                [word.upper() for word in words]
                for words in data["alternatives"]
            ]
        except KeyError:
            return None

    @staticmethod
    def _get_allowlist(
        data: OrderedDict, hasher: GenericHasher
    ) -> Optional[WordList]:
        """
        Returns a :class:`crate_anon.anonymise.scrub.WordList` of words to be
        allowed through.
        """
        try:
            allowlist_data = data["allowlist"]
        except KeyError:
            return None

        options = ("words",)

        kwargs = {k: v for (k, v) in allowlist_data.items() if k in options}
        files = allowlist_data["files"]
        filename_lookup = settings.ANONYMISE_API.get("ALLOWLIST_FILENAMES", {})

        filenames = [
            filename
            for label, filename in filename_lookup.items()
            if label in files
        ]
        kwargs.update(filenames=filenames)

        return WordList(hasher=hasher, **kwargs)

    def _get_nonspecific_scrubber(
        self, data: OrderedDict, hasher: GenericHasher
    ) -> NonspecificScrubber:
        """
        Returns a nonspecific scrubber for the current settings.
        """
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

        try:
            kwargs["replacement_text_all_dates"] = data[
                "replace_all_dates_with"
            ]
        except KeyError:
            pass

        return NonspecificScrubber(
            hasher,
            replacement_text=replacement_text,
            denylist=denylist,
            **kwargs,
        )

    @staticmethod
    def _get_denylist(
        data: OrderedDict, hasher: GenericHasher
    ) -> Optional[WordList]:
        """
        Returns a :class:`crate_anon.anonymise.scrub.WordList` of words to be
        scrubbed.
        """
        try:
            denylist_data = data["denylist"]
        except KeyError:
            return None

        options = ("words",)

        kwargs = {k: v for (k, v) in denylist_data.items() if k in options}
        kwargs["replacement_text"] = data["replace_nonspecific_info_with"]

        files = denylist_data["files"]
        filename_lookup = settings.ANONYMISE_API.get("DENYLIST_FILENAMES", {})

        filenames = [
            filename
            for label, filename in filename_lookup.items()
            if label in files
        ]
        kwargs.update(filenames=filenames)

        # TODO: None of these are currently configurable
        # from crate_anon/anonymise/config.py
        # Do we care about them here?
        # suffixes
        # at_word_boundaries_only (for regex_method=True)
        # max_errors
        # regex_method: True
        return WordList(hasher=hasher, **kwargs)

    @staticmethod
    def _add_values_to_scrubber(
        scrubber: PersonalizedScrubber, label: str, data: OrderedDict
    ) -> None:
        """
        Adds values to be scrubbed to either the patient or the third-party
        component of a scrubber.
        """
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
