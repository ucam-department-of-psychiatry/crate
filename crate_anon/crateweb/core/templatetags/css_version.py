"""
crate_anon/crateweb/core/templatetags/__init__.py

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

**CSS version template tag.**

"""

import uuid

from django import template
from django.conf import settings

from crate_anon.version import CRATE_VERSION

register = template.Library()


@register.simple_tag
def css_version() -> str:
    # Ensure style sheets update by setting a version template tag
    # e.g.:
    # {% load css_version %}
    # <link rel="stylesheet" href="{% static 'foo.css' %}?v={% css_version %}" type="text/css">  # noqa: E501
    #
    # During development generate a new version every time, in production use
    # the CRATE version.
    if settings.DEBUG:
        return str(uuid.uuid4())

    return CRATE_VERSION.replace(".", "_")
