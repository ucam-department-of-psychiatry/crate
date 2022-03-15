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
    CharField,
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


class PatientSerializer(Serializer):
    dates = ListField(child=CharField(), required=False)
    phrases = ListField(child=CharField(), required=False)


class ScrubSerializer(Serializer):
    # Input fields. write_only means they aren't returned in the response
    denylist = ListField(child=CharField(), required=False, write_only=True)
    text = CharField(write_only=True)
    patient = PatientSerializer(required=False, write_only=True)

    # Output fields
    anonymised = SerializerMethodField()  # Read-only by default

    def get_anonymised(self, data: OrderedDict) -> str:
        hasher = make_hasher("HMAC_MD5", settings.HASH_KEY)

        denylist = None
        if "denylist" in data:
            denylist = WordList(words=data["denylist"], hasher=hasher)

        nonspecific_scrubber = NonspecificScrubber("[---]",  # TODO configure
                                                   hasher,
                                                   denylist=denylist)
        scrubber = PersonalizedScrubber(
            "[PPP]",  # TODO configure
            "[TTT]",  # TODO configure
            hasher,
            nonspecific_scrubber=nonspecific_scrubber
        )

        if "patient" in data:
            self._add_patient_values_to_scrubber(scrubber, data)

        return scrubber.scrub(data["text"])

    def _add_patient_values_to_scrubber(self,
                                        scrubber: PersonalizedScrubber,
                                        data: OrderedDict) -> None:
        method_lookup = {
            "dates": SCRUBMETHOD.DATE,
            "phrases": SCRUBMETHOD.PHRASE,
        }

        for name, values in data["patient"].items():
            method = method_lookup[name]
            for value in values:
                scrubber.add_value(value, method)
