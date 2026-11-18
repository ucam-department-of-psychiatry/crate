"""
crate_anon/crateweb/extra/tests/pdf_tests.py

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

**Test assistance functions for working with PDFs.**

"""

from unittest import mock, TestCase

from weasyprint import CSS

from django.conf import LazySettings

from crate_anon.crateweb.consent.constants import EthicsDocInfo, EthicsInfo
from crate_anon.crateweb.extra.pdf import CratePdfPlan, serve_html_or_pdf


class PdfTestCase(TestCase):
    def setUp(self) -> None:
        super().setUp()

        # MagicMocks are subscriptable
        self.mock_returned_css = mock.Mock(spec=CSS)
        self.mock_css = mock.Mock(return_value=self.mock_returned_css)
        self.mock_docinfo = mock.Mock(
            spec=EthicsDocInfo,
            title="Test title",
            version="v3.14",
            date="2026-11-17",
        )
        self.mock_get_docinfo = mock.Mock(return_value=self.mock_docinfo)
        self.mock_ethics_info = mock.Mock(
            spec=EthicsInfo,
            IRAS_NUMBER="12345",
            REC_REFERENCE="this/that",
            get_docinfo=self.mock_get_docinfo,
        )
        self.mock_settings = mock.MagicMock(
            spec=LazySettings,
            PDF_LETTER_FOOTER_ADDRESS_HTML="Test address",
            ETHICS_INFO=self.mock_ethics_info,
            WKHTMLTOPDF_OPTIONS={},
            WKHTMLTOPDF_FILENAME="",
        )
        self.mock_get_pdf_from_html = mock.Mock()


class ServeHtmlOrPdfTests(PdfTestCase):
    def setUp(self) -> None:
        super().setUp()

    def test_weasyprint_options_when_making_pdf(self) -> None:
        html = ""

        with mock.patch.multiple(
            "crate_anon.crateweb.extra.pdf",
            CSS=self.mock_css,
            settings=self.mock_settings,
            render_to_string=mock.Mock(),
            get_pdf_from_html=self.mock_get_pdf_from_html,
            serve_buffer=mock.Mock(),
        ):
            serve_html_or_pdf(
                html, viewtype="pdf", ethics_doccode="Test doccode"
            )

        self.mock_get_docinfo.assert_called_with("Test doccode")
        kwargs = self.mock_get_pdf_from_html.call_args.kwargs

        expected_options = {
            "stylesheets": [self.mock_returned_css],
        }

        self.assertEqual(kwargs["weasyprint_options"], expected_options)

        css_string = self.mock_css.call_args.kwargs["string"]

        self.assertIn("Test address", css_string)
        self.assertIn("IRAS# 12345", css_string)
        self.assertIn(
            "REC# this/that Test title version v3.14, 2026-11-17", css_string
        )


class CratePdfPlanTests(PdfTestCase):
    def setUp(self) -> None:
        super().setUp()

    def test_weasyprint_options_applied_to_plan(self) -> None:
        with mock.patch.multiple(
            "crate_anon.crateweb.extra.pdf",
            CSS=self.mock_css,
            settings=self.mock_settings,
            render_to_string=mock.Mock(),
        ):
            plan = CratePdfPlan(
                is_html=True, html="", ethics_doccode="Test doccode"
            )

        self.mock_get_docinfo.assert_called_with("Test doccode")
        options = plan.weasyprint_options
        expected_options = {
            "stylesheets": [self.mock_returned_css],
        }

        self.assertEqual(options, expected_options)
