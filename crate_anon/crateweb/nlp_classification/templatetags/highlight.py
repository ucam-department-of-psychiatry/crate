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
    nlp_matches = sorted(
        source_record.all_nlp_matches(), key=lambda s: s.start
    )

    sections = []

    index = 0

    for match in nlp_matches:
        if match.nlp_pk_value == source_record.nlp_pk_value:
            css_class = "nlp-match"
        else:
            css_class = "other-nlp-match"

        sections.append(escape(source_record.source_text[index : match.start]))
        sections.append(
            mark_element(
                css_class,
                escape(source_record.source_text[match.start : match.end]),
            )
        )

        index = match.end

    sections.append(escape(source_record.source_text[index:]))

    output = "".join(sections)

    return mark_safe(output)


def mark_element(css_class: str, text: str) -> str:
    return f'<mark class="{css_class}">{text}</mark>'
