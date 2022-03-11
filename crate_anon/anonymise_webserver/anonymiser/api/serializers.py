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

from crate_anon.anonymise.scrub import WordList


class ScrubSerializer(Serializer):
    # Input fields. write_only means they aren't returned in the response
    scrub = ListField(child=CharField(), write_only=True)
    text = CharField(write_only=True)

    # Output fields
    anonymised = SerializerMethodField()  # Read-only by default

    def get_anonymised(self, data: OrderedDict) -> str:
        hasher = make_hasher("HMAC_MD5", settings.HASH_KEY)
        scrubber = WordList(words=data["scrub"], hasher=hasher)

        return scrubber.scrub(data["text"])
