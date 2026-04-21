"""
crate_anon/crateweb/core/templatetags/highlight.py

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

**Highlight template tag.**

"""

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

from crate_anon.crateweb.nlp_classification.models import SourceRecord

register = template.Library()


@register.filter
def highlight(source_record: SourceRecord) -> str:

    if match := source_record.match:
        match = f"<mark>{escape(source_record.match)}</mark>"

    return mark_safe(
        f"{escape(source_record.before)}{match}{escape(source_record.after)}"
    )
