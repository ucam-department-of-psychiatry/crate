"""
crate_anon/crateweb/nlp_classification/highlight.py

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

**Highlight NLP matches in text.**

"""

from typing import Any

from django.utils.html import escape
from django.utils.safestring import mark_safe

from crate_anon.crateweb.nlp_classification.models import SourceRecord


def highlight(source_record: SourceRecord) -> str:
    nlp_matches = sorted(
        source_record.all_nlp_matches(), key=lambda s: s.start
    )

    sections = []

    index = 0

    source_text = source_record.source_text

    for match in nlp_matches:
        sections.append(escape(source_text[index : match.start]))

        attributes = mark_attributes(match, source_record)

        sections.append(
            mark_element(
                escape(source_text[match.start : match.end]),
                attributes,
            )
        )

        index = match.end

    sections.append(escape(source_text[index:]))

    output = "".join(sections)

    return mark_safe(output)


def mark_element(text: str, attributes: dict[str, Any]) -> str:
    attributes = " ".join([f'{k}="{v}"' for k, v in attributes.items()])

    return f"<mark {attributes}>{text}</mark>"


def mark_attributes(
    match: SourceRecord, this_record: SourceRecord
) -> dict[str, Any]:
    if match.nlp_pk_value == this_record.nlp_pk_value:
        label = "matches this record"
        css_class = "nlp-match"
    else:
        label = "matches another record"
        css_class = "other-nlp-match"

    return {"class": css_class, "aria-label": label, "title": label}
