"""
crate_anon/crateweb/nlp_classification/tests/highlight_tests.py

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

**Test highlighting of NLP matches.**

"""

import re
from unittest import mock, TestCase

from django.utils.html import escape
from django.utils.safestring import SafeString

from crate_anon.crateweb.nlp_classification.models import SourceRecord
from crate_anon.crateweb.nlp_classification.highlight import highlight


class HighlightTests(TestCase):
    this_mark_attributes = (
        'class="nlp-match" '
        'aria-label="matches this record" '
        'title="matches this record"'
    )
    other_mark_attributes = (
        'class="other-nlp-match" '
        'aria-label="matches another record" '
        'title="matches another record"'
    )

    def test_text_is_highlighted_when_match(self) -> None:
        source_text = "before match after"
        match_text = "match"

        match = re.search(match_text, source_text)

        source_record = mock.Mock(
            spec=SourceRecord,
            start=match.start(),
            end=match.end(),
            content=match_text,
            source_text=source_text,
        )
        source_record.all_nlp_matches = mock.Mock(return_value=[source_record])
        highlighted = highlight(source_record)

        highlighted_content = self.mark_element(
            match_text, self.this_mark_attributes
        )

        self.assertEqual(
            highlighted,
            f"before {highlighted_content} after",
        )

    def test_text_is_not_highlighted_when_no_match(self) -> None:
        source_text = "Nothing to see here & there"
        source_record = mock.Mock(
            spec=SourceRecord,
            source_text=source_text,
            all_nlp_matches=mock.Mock(return_value=[]),
        )
        highlighted = highlight(source_record)

        self.assertEqual(highlighted, "Nothing to see here &amp; there")

    def test_output_is_safe(self) -> None:
        source_record = mock.Mock(
            spec=SourceRecord,
            source_text="",
            all_nlp_matches=mock.Mock(return_value=[]),
        )
        highlighted = highlight(source_record)

        self.assertIsInstance(highlighted, SafeString)

    def test_search_text_is_escaped(self) -> None:
        source_text = "<before><something><after>"
        match_text = "<something>"

        match = re.search(match_text, source_text)

        source_record = mock.Mock(
            spec=SourceRecord,
            start=match.start(),
            end=match.end(),
            content=match_text,
            source_text=source_text,
        )
        source_record.all_nlp_matches = mock.Mock(return_value=[source_record])
        highlighted = highlight(source_record)

        mark_element = self.mark_element(match_text, self.this_mark_attributes)

        self.assertEqual(
            highlighted,
            f"&lt;before&gt;{mark_element}&lt;after&gt;",
        )

    def test_other_nlp_matches_shown(self) -> None:
        # TODO: Fix brittle HTML comparison

        this_match = "CRP = 40"
        other_match_1 = "CRP < 10"
        other_match_2 = "CRP 30 mg/L"

        # Deliberate ampersands to test escaping
        crp_list = [
            "Filler text at the start & stuff",
            other_match_1,
            this_match,
            other_match_2,
            "Filler text at the end & stuff",
        ]

        source_text = ". ".join(crp_list)

        match = re.search(other_match_1, source_text)
        other_source_record_1 = mock.Mock(
            spec=SourceRecord,
            content=other_match_1,
            start=match.start(),
            end=match.end(),
        )

        match = re.search(other_match_2, source_text)
        other_source_record_2 = mock.Mock(
            spec=SourceRecord,
            content=other_match_2,
            start=match.start(),
            end=match.end(),
        )

        match = re.search(this_match, source_text)
        source_record = mock.Mock(
            spec=SourceRecord,
            content=this_match,
            start=match.start(),
            end=match.end(),
            source_text=source_text,
        )
        source_record.all_nlp_matches = mock.Mock(
            return_value=[
                source_record,
                other_source_record_1,
                other_source_record_2,
            ]
        )

        highlighted = highlight(source_record)

        this_mark_element = self.mark_element(
            this_match,
            self.this_mark_attributes,
        )
        other_mark_element_1 = self.mark_element(
            other_match_1,
            self.other_mark_attributes,
        )
        other_mark_element_2 = self.mark_element(
            other_match_2,
            self.other_mark_attributes,
        )

        expected = (
            "Filler text at the start &amp; stuff. "
            f"{other_mark_element_1}. "
            f"{this_mark_element}. "
            f"{other_mark_element_2}. "
            "Filler text at the end &amp; stuff"
        )

        self.assertEqual(highlighted, expected)

    def mark_element(self, text: str, attributes: str) -> str:
        escaped = escape(text)
        return f"<mark {attributes}>{escaped}</mark>"
