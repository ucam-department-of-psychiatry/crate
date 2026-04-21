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

import re
from unittest import mock

from django.test import TestCase
from django.utils.safestring import SafeString

from crate_anon.crateweb.nlp_classification.templatetags.highlight import (
    highlight,
)
from crate_anon.crateweb.nlp_classification.tests.factories import (
    SourceRecordFactory,
)

from crate_anon.nlp_manager.regex_parser import (
    FN_CONTENT,
    FN_END,
    FN_START,
)


class HighlightTests(TestCase):
    def test_text_is_highlighted_when_match(self) -> None:
        source_record = SourceRecordFactory()
        fake_source_text = "before match after"
        content = "match"
        match = re.search(content, fake_source_text)

        fake_nlp_dict = {
            FN_CONTENT: content,
            FN_START: match.start(),
            FN_END: match.end(),
        }

        with mock.patch.multiple(
            source_record,
            _source_text=fake_source_text,
            _nlp_dict=fake_nlp_dict,
        ):
            highlighted = highlight(source_record)

        highlighted_content = f"<mark>{content}</mark>"

        self.assertEqual(
            highlighted,
            f"before {highlighted_content} after",
        )

    def test_text_is_not_highlighted_when_no_match(self) -> None:
        source_record = SourceRecordFactory()
        fake_source_text = "Nothing to see here"

        with mock.patch.multiple(
            source_record,
            _source_text=fake_source_text,
            _nlp_dict={},
        ):
            highlighted = highlight(source_record)

        self.assertEqual(highlighted, fake_source_text)

    def test_output_is_safe(self) -> None:
        source_record = SourceRecordFactory()

        with mock.patch.multiple(
            source_record,
            _source_text="",
            _nlp_dict={},
        ):
            highlighted = highlight(source_record)

        self.assertIsInstance(highlighted, SafeString)

    def test_search_text_is_escaped(self) -> None:
        source_record = SourceRecordFactory()
        fake_source_text = "<before> <something> <after>"
        content = "<something>"
        match = re.search(content, fake_source_text)

        fake_nlp_dict = {
            FN_CONTENT: content,
            FN_START: match.start(),
            FN_END: match.end(),
        }

        with mock.patch.multiple(
            source_record,
            _source_text=fake_source_text,
            _nlp_dict=fake_nlp_dict,
        ):
            highlighted = highlight(source_record)

        self.assertEqual(
            highlighted,
            "&lt;before&gt; <mark>&lt;something&gt;</mark> &lt;after&gt;",
        )
