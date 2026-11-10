"""
crate_anon/anonymise/tests/researcher_report_tests.py

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

Researcher report tests.

"""

import os.path
import random
import re
from tempfile import TemporaryDirectory
from typing import Any, TYPE_CHECKING
from unittest import mock, TestCase

import factory
from pypdf import PdfReader
import pytest
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Text,
)
from sqlalchemy.orm import relationship
from weasyprint import CSS

from crate_anon.anonymise.dbholder import DatabaseHolder
from crate_anon.anonymise.researcher_report import (
    mk_researcher_report_pdf,
    parse_args,
    ResearcherReportConfig,
    TEMPLATE_DIR,
)
from crate_anon.testing import AnonTestBase
from crate_anon.testing.classes import DatabaseTestCase
from crate_anon.testing.factories import AnonTestBaseFactory, Fake
from crate_anon.testing.models import SexColType

if TYPE_CHECKING:
    from django.conf import LazySettings
    from factory.builder import Resolver


class AnonNote(AnonTestBase):
    __tablename__ = "anon_note"

    note_id = Column(Integer, primary_key=True, comment="Note ID")
    patient_id = Column(
        Integer, ForeignKey("anon_patient.patient_id"), comment="Patient ID"
    )
    note = Column(Text, comment="Text of the note")
    note_datetime = Column(DateTime, comment="Date/time of the note")

    patient = relationship("AnonPatient")


class AnonPatient(AnonTestBase):
    __tablename__ = "anon_patient"

    patient_id = Column(
        Integer,
        primary_key=True,
        autoincrement=False,
        comment="Patient ID",
    )
    sex = Column(
        SexColType,
        comment="Sex (M, F, X)",
    )
    age = Column(Integer, comment="Age")


class AnonPatientFactory(AnonTestBaseFactory):
    class Meta:
        model = AnonPatient

    patient_id = factory.Sequence(lambda n: n + 1)

    sex = factory.LazyFunction(Fake.en_gb.sex)
    age = factory.LazyFunction(Fake.en_gb.age)

    @factory.post_generation
    def notes(
        obj: "Resolver", create: bool, extracted: int, **kwargs: Any
    ) -> None:
        if not create:
            return

        if extracted:
            AnonNoteFactory.create_batch(size=extracted, patient=obj, **kwargs)


class AnonNoteFactory(AnonTestBaseFactory):
    class Meta:
        model = AnonNote

    class Params:
        words_per_note = 100

    note_datetime = factory.LazyFunction(Fake.en_gb.incrementing_date)

    @factory.lazy_attribute
    def note(obj: "Resolver") -> str:
        # Use en_US because you get Lorem ipsum with en_GB.
        paragraph = Fake.en_us.paragraph(
            nb_sentences=obj.words_per_note / 2,  # way more than we need
        )

        return " ".join(paragraph.split()[: obj.words_per_note])


@pytest.fixture
def django_test_settings(settings: "LazySettings") -> None:
    settings.TEMPLATES = [
        {
            "BACKEND": "django.template.backends.django.DjangoTemplates",
            "DIRS": [TEMPLATE_DIR],
        }
    ]


class MkResearcherReportPdfTests(DatabaseTestCase):
    def setUp(self) -> None:
        super().setUp()

        self.num_patients = 100
        self.notes_per_patient = 5
        seed = 1234

        # Seed both the global python RNG and Faker's RNG as we don't use Faker
        # for everything and Factory Boy's interface with Faker doesn't seem to
        # allow for sharing with the global RNG used by python (though Faker on
        # its own does). The value of the seed isn't particularly important
        # unless we're checking particular details but it's better to have one
        # for consistency of tests.
        random.seed(seed)
        factory.random.reseed_random(seed)

        AnonPatientFactory.create_batch(
            self.num_patients, notes=self.notes_per_patient
        )
        self.anon_dbsession.commit()

        self.tempdir = TemporaryDirectory()

    @pytest.mark.usefixtures("django_test_settings")
    def test_report_has_pages_for_each_table(self) -> None:
        anon_config = mock.Mock()

        reportfilename = os.path.join(self.tempdir.name, "tmpreport.pdf")

        with open(reportfilename, mode="w") as f:
            mock_db = mock.Mock(
                table_names=["anon_patient", "anon_note"],
                metadata=AnonTestBase.metadata,
            )
            report_config = ResearcherReportConfig(
                output_filename=reportfilename,
                anonconfig=anon_config,
                use_dd=False,
            )
            report_config.db_session = self.anon_dbsession
            report_config.db = mock_db
            mk_researcher_report_pdf(report_config)

        with open(reportfilename, "rb") as f:
            reader = PdfReader(f)

            patient_found = False
            note_found = False
            for page in reader.pages:
                text = page.extract_text()

                regex = r"(.*)\nNumber of rows in this table:\s*(\d+)"
                # The label text here is from
                # crate_anon/anonymise/templates/researcher_report/table.html.

                if (m := re.match(regex, text)) is None:
                    continue

                table_name = m.group(1)
                num_rows = int(m.group(2))

                if table_name == "anon_patient":
                    patient_found = True
                    self.assertEqual(num_rows, self.num_patients)

                elif table_name == "anon_note":
                    note_found = True
                    self.assertEqual(
                        num_rows, self.num_patients * self.notes_per_patient
                    )

            self.assertTrue(patient_found)
            self.assertTrue(note_found)


class ResearcherReportTests(TestCase):
    def setUp(self) -> None:
        super().setUp()

        # MagicMocks are subscriptable
        self.mock_weasyprint_css = mock.MagicMock(spec=CSS)
        self.mock_db_holder = mock.MagicMock(spec=DatabaseHolder)
        self.mock_make_pdf_on_disk_from_html = mock.Mock()
        self.mock_render_to_string = mock.Mock()

        # needs to be str even though argparse will check it is an int
        self.test_db_name = "test_db_name"
        self.test_db_url = "test_db_url"
        self.test_header_footer_spacing_mm = "123"
        self.test_margin_left_right = "20mm"
        self.test_margin_top_bottom = "25mm"
        self.test_orientation = "portrait"
        self.test_output = "output_file"
        self.test_page_size = "A5"

        self.maxDiff = None

    def test_wkhtmltopdf_options_when_making_pdf(self) -> None:
        arg_list = [
            self.test_output,
            "--db_name",
            self.test_db_name,
            "--db_url",
            self.test_db_url,
            "--header_footer_spacing_mm",
            self.test_header_footer_spacing_mm,
            "--margin_left_right",
            self.test_margin_left_right,
            "--margin_top_bottom",
            self.test_margin_top_bottom,
            "--noconfig",
            "--orientation",
            self.test_orientation,
            "--page_size",
            self.test_page_size,
        ]

        with mock.patch.multiple(
            "crate_anon.anonymise.researcher_report",
            DatabaseHolder=self.mock_db_holder,
            render_to_string=self.mock_render_to_string,
            make_pdf_on_disk_from_html=self.mock_make_pdf_on_disk_from_html,
            CSS=self.mock_weasyprint_css,
        ):
            parse_args(arg_list)

        kwargs = self.mock_make_pdf_on_disk_from_html.call_args.kwargs

        expected_options = {
            "page-size": self.test_page_size,
            "margin-left": self.test_margin_left_right,
            "margin-right": self.test_margin_left_right,
            "margin-top": self.test_margin_top_bottom,
            "margin-bottom": self.test_margin_top_bottom,
            "header-spacing": self.test_header_footer_spacing_mm,
            "footer-spacing": self.test_header_footer_spacing_mm,
            "orientation": self.test_orientation,
        }

        self.assertEqual(kwargs["wkhtmltopdf_options"], expected_options)

    def test_wkhtmltopdf_header_and_footer_when_making_pdf(self) -> None:
        arg_list = [
            self.test_output,
            "--db_name",
            self.test_db_name,
            "--db_url",
            self.test_db_url,
            "--noconfig",
        ]

        mock_css = mock.MagicMock(spec=str)
        mock_header_html = mock.MagicMock(spec=str)
        mock_footer_html = mock.MagicMock(spec=str)
        mock_html = mock.MagicMock(spec=str)
        test_now = "Mon 09 November 2026, 11:00 +0000"

        self.mock_render_to_string.side_effect = [
            mock_css,
            mock_header_html,
            mock_footer_html,
            mock_html,
        ]

        with mock.patch.multiple(
            "crate_anon.anonymise.researcher_report",
            DatabaseHolder=self.mock_db_holder,
            render_to_string=self.mock_render_to_string,
            make_pdf_on_disk_from_html=self.mock_make_pdf_on_disk_from_html,
            CSS=self.mock_weasyprint_css,
            format_datetime=mock.Mock(return_value=test_now),
        ):
            parse_args(arg_list)

        render_args_list = self.mock_render_to_string.call_args_list

        header_args = render_args_list[1].args
        footer_args = render_args_list[2].args

        expected_title = (
            f"{self.test_db_name}: CRATE researcher report, {test_now}"
        )
        expected_coredict = dict(
            title=expected_title, css=mock_css, now=test_now
        )

        self.assertEqual(header_args[1], expected_coredict)
        self.assertEqual(footer_args[1], expected_coredict)

    def test_weasyprint_options_when_making_pdf(self) -> None:
        arg_list = [
            self.test_output,
            "--db_name",
            self.test_db_name,
            "--db_url",
            self.test_db_url,
            "--header_footer_spacing_mm",
            self.test_header_footer_spacing_mm,
            "--margin_left_right",
            self.test_margin_left_right,
            "--margin_top_bottom",
            self.test_margin_top_bottom,
            "--noconfig",
            "--orientation",
            self.test_orientation,
            "--page_size",
            self.test_page_size,
        ]

        mock_returned_css = mock.Mock()
        self.mock_weasyprint_css.return_value = mock_returned_css

        with mock.patch.multiple(
            "crate_anon.anonymise.researcher_report",
            DatabaseHolder=self.mock_db_holder,
            render_to_string=self.mock_render_to_string,
            make_pdf_on_disk_from_html=self.mock_make_pdf_on_disk_from_html,
            CSS=self.mock_weasyprint_css,
        ):
            parse_args(arg_list)

        kwargs = self.mock_make_pdf_on_disk_from_html.call_args.kwargs

        expected_options = {
            "stylesheets": [mock_returned_css],
        }

        self.assertEqual(kwargs["weasyprint_options"], expected_options)

        css_string = self.mock_weasyprint_css.call_args.kwargs["string"]

        self.assertIn(
            f"size: {self.test_page_size} {self.test_orientation};", css_string
        )
        self.assertIn(
            f"margin: {self.test_margin_top_bottom} {self.test_margin_left_right};",  # noqa: E501
            css_string,
        )
