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

import random
from tempfile import NamedTemporaryFile
from typing import List, TYPE_CHECKING
from unittest import mock

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


from crate_anon.anonymise.researcher_report import (
    mk_researcher_report_pdf,
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
    def notes(obj: "Resolver", create: bool, extracted: int, **kwargs) -> None:
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


class ResearcherReportTests(DatabaseTestCase):
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

    @pytest.mark.usefixtures("django_test_settings")
    def test_report_has_pages_for_each_table(self) -> None:
        def index_of_list_substring(items: List[str], substr: str) -> int:
            for i, item in enumerate(items):
                if substr in item:
                    return i

            return -1

        anon_config = mock.Mock()

        with NamedTemporaryFile(delete=False, mode="w") as f:
            mock_db = mock.Mock(
                table_names=["anon_patient", "anon_note"],
                metadata=AnonTestBase.metadata,
            )

            with mock.patch.multiple(
                "crate_anon.anonymise.researcher_report.ResearcherReportConfig",  # noqa: E501
                __post_init__=mock.Mock(),
            ):
                report_config = ResearcherReportConfig(
                    output_filename=f.name,
                    anonconfig=anon_config,
                    use_dd=False,
                )
                report_config.db_session = self.anon_dbsession
                report_config.db = mock_db
                mk_researcher_report_pdf(report_config)

        with open(f.name, "rb") as f:
            reader = PdfReader(f)

            patient_found = False
            note_found = False
            for page in reader.pages:
                lines = page.extract_text().replace("\t", " ").splitlines()
                # Sometimes spaces come back as tabs; fix that.

                rows_index = index_of_list_substring(
                    lines,
                    "Number of rows in this table:",
                )
                # The label text here is from
                # crate_anon/anonymise/templates/researcher_report/table.html.

                if rows_index < 0:
                    continue

                num_rows = int(lines[rows_index + 1])
                table_name = lines[0]

                if table_name == "patient":
                    patient_found = True
                    self.assertEqual(num_rows, self.num_patients)

                elif table_name == "anon_note":
                    note_found = True
                    self.assertEqual(
                        num_rows, self.num_patients * self.notes_per_patient
                    )

            self.assertTrue(patient_found)
            self.assertTrue(note_found)
