"""
crate_anon/crateweb/nlp_classification/tests/templatetags_tests.py

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

**Template tags tests.**

"""

from unittest import mock, TestCase

from django.utils.safestring import SafeString

from crate_anon.crateweb.nlp_classification.models import SourceRecord
from crate_anon.crateweb.nlp_classification.templatetags.highlight import (
    highlight,
)


class HighlightTests(TestCase):
    def test_text_is_highlighted_when_match(self) -> None:
        source_record = mock.Mock(
            spec=SourceRecord,
            match="match",
            before="before",
            after="after",
        )
        highlighted = highlight(source_record)

        highlighted_content = "<mark>match</mark>"

        self.assertEqual(
            highlighted,
            f"before{highlighted_content}after",
        )

    def test_text_is_not_highlighted_when_no_match(self) -> None:
        source_record = mock.Mock(
            spec=SourceRecord,
            match="",
            before="Nothing to see here",
            after="",
        )
        highlighted = highlight(source_record)

        self.assertEqual(highlighted, "Nothing to see here")

    def test_output_is_safe(self) -> None:
        source_record = mock.Mock(
            spec=SourceRecord,
            match="",
            before="",
            after="",
        )
        highlighted = highlight(source_record)

        self.assertIsInstance(highlighted, SafeString)

    def test_search_text_is_escaped(self) -> None:
        source_record = mock.Mock(
            match="<something>",
            before="<before>",
            after="<after>",
        )
        highlighted = highlight(source_record)

        self.assertEqual(
            highlighted,
            "&lt;before&gt;<mark>&lt;something&gt;</mark>&lt;after&gt;",
        )
