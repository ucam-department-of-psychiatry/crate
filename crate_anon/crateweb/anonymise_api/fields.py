"""
crate_anon/crateweb/anonymise_api/fields.py

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

Custom Django REST Framework serializer fields.

"""

import json
from typing import Any, Mapping

from rest_framework.fields import empty
from rest_framework.serializers import (
    DictField,
    ListField,
)


class JsonDictField(DictField):
    """
    This class is only needed to display JSON editors in the browseable API
    HTML form.
    """

    def __init__(self, *args, **kwargs):
        style = {"base_template": "json.html"}
        super().__init__(*args, style=style, **kwargs)

    def get_value(self, dictionary: Mapping[Any, Any]) -> Any:
        """
        For content-type application/json, dictionary will be of the form:
        {
            "text": {
                "id1": "text 1 to be anonymised",
                "id2": "text 2 to be anonymised",
                ...
            },
            "patient": {
                "dates": ["1970-01-01"],
                ...
            }
            ...
        }

        For content-type multipart-formdata:
        {
            "text": ['{"id1": "text 1"}', '{"id2": "text 2"}', ...],
            "patient.dates": ['["1970-01-01"]'],
            ...
        }
        """
        if hasattr(dictionary, "getlist"):
            value = dictionary.getlist(self.field_name, empty)

            if value is not empty:
                value = value[0].replace("\n", "\\n")
                try:
                    value = json.loads(value)
                except ValueError:
                    pass
        else:
            value = super().get_value(dictionary)

        return value


class JsonListField(ListField):
    """
    This class is only needed to display JSON editors in the browseable API
    HTML form.
    """

    def __init__(self, *args, **kwargs):
        style = {"base_template": "json.html"}
        super().__init__(*args, style=style, **kwargs)

    def get_value(self, dictionary: Mapping[Any, Any]) -> Any:
        """
        For content-type application/json, dictionary will be of the form:
        {
            "words": ["secret", "private", "confidential"]
        }

        For content-type multipart-formdata:
        {
            "words": ['["secret", "private", "confidential"]']
        }
        """

        if hasattr(dictionary, "getlist"):
            value = dictionary.getlist(self.field_name, empty)

            if value is not empty:
                value = value[0].replace("\n", "\\n")
                try:
                    value = json.loads(value)
                except ValueError:
                    pass
        else:
            value = super().get_value(dictionary)

        return value
