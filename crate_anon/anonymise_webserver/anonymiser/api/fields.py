"""
crate_anon/anonymise_webserver/anonymiser/api/fields.py

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

Custom Django REST Framework serializer fields.

"""

import json
from typing import Any, Mapping

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
        If the JSON editor is used in the browseable API, convert the value
        from the input element into a list.

        https://github.com/encode/django-rest-framework/issues/5495
        """
        value = super().get_value(dictionary)

        # True if the request originated from an HTML form
        # https://docs.djangoproject.com/en/3.2/ref/request-response/#querydict-objects  # noqa: E501
        is_querydict = hasattr(dictionary, "getlist")
        if value and is_querydict:
            try:
                value = json.loads(value[0])
            except ValueError:
                pass

        return value
