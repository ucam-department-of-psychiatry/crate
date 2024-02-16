#!/usr/bin/env python

"""
crate_anon/testing/factories.py

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

**Factory Boy SQL Alchemy test factories.**

"""

import random
from typing import TYPE_CHECKING

from cardinal_pythonlib.classes import all_subclasses
from cardinal_pythonlib.nhs import generate_random_nhs_number
import factory
import factory.random
from faker import Faker

from crate_anon.testing.models import EnumColours, Note, Patient

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


# When running with pytest sqlalchemy_session gets poked in by
# DatabaseTestCase.setUp(). Otherwise call
class BaseFactory(factory.alchemy.SQLAlchemyModelFactory):
    pass


def set_sqlalchemy_session_on_all_factories(dbsession: "Session"):
    for factory_class in all_subclasses(BaseFactory):
        factory_class._meta.sqlalchemy_session = dbsession


# =============================================================================
# Randomness
# =============================================================================


def coin(p: float = 0.5) -> bool:
    """
    Biased coin toss. Returns ``True`` with probability ``p``.
    """
    return random.random() < p


class Fake:
    en = Faker("en")


class DemoFactory(BaseFactory):
    class Meta:
        abstract = True


class DemoPatientFactory(DemoFactory):
    class Meta:
        model = Patient

    class Params:
        first_name = factory.Faker("first_name")
        first_name_male = factory.Faker("first_name_male")
        first_name_female = factory.Faker("first_name_female")

    patient_id = factory.Sequence(lambda n: n + 1)
    sex = factory.Faker("sex")

    @factory.lazy_attribute
    def forename(obj):
        if obj.sex == "M":
            return obj.first_name_male

        if obj.sex == "F":
            return obj.first_name_female

        return obj.first_name[:1]

    surname = factory.Faker("last_name")
    dob = factory.Faker("consistent_date_of_birth")

    @factory.lazy_attribute
    def nhsnum(obj) -> int:
        return generate_random_nhs_number()

    phone = factory.Faker("phone_number")
    postcode = factory.Faker("postcode")

    @factory.lazy_attribute
    def related_patient(obj) -> int:
        if obj.patient_id == 1:
            return None

        related_patient_id = obj.patient_id - 1
        session = DemoPatientFactory._meta.sqlalchemy_session
        related_patient = (
            session.query(Patient)
            .filter(Patient.patient_id == related_patient_id)
            .first()
        )

        return related_patient

    related_patient_relationship = factory.Faker("relationship")

    @factory.lazy_attribute
    def colour(obj) -> EnumColours:
        return EnumColours.blue if coin() else None

    @factory.post_generation
    def notes(obj, create, extracted: int, **kwargs):
        if not create:
            return

        if extracted:
            DemoNoteFactory.create_batch(size=extracted, patient=obj, **kwargs)


class DemoNoteFactory(DemoFactory):
    class Meta:
        model = Note

    class Params:
        words_per_note = 100
        another_date_formatted = factory.Faker("formatted_date_of_birth")
        dob_format = factory.Faker("date_format")
        note_date_format = factory.Faker("date_format")
        alcohol = factory.Faker("alcohol")
        pad_paragraph = factory.Faker(
            "paragraph",
            locale="en_US",  # You get Lorem ipsum with en_GB.
            nb_sentences=words_per_note / 2,  # way more than we need
        )

    note_datetime = factory.Faker("incrementing_date")

    @factory.lazy_attribute
    def note(obj) -> str:
        other_notes = [
            "Start aspirin 75mg od. Remains on Lipitor 40mg nocte",
            "For haloperidol 2mg po prn max qds",
            "Start amoxicillin 500 mg b.i.d. for 7 days",
            f"{obj.patient.possessive_pronoun.capitalize()} CRP is 10",
            (
                f"{obj.patient.possessive_pronoun.capitalize()} "
                "previous CRP was <13 mg/dl"
            ),
            "Sodium 140",
            "TSH 3.5; urea normal",
            "Height 1.82m, weight 75kg, BMI 22.6. BP 135/82",
            "MMSE 28/30. ACE-R 72, ACE-II 73, ACE 73",
            "ESR 16 (H) mm/h",
            (
                "WBC 9.2; neutrophils 4.3; lymphocytes 2.6; "
                "eosinophils 0.4; monocytes 1.2; basophils 0.6"
            ),
            (
                f"{obj.patient.forename} took venlafaxine 375 M/R od, "
                "and is due to start clozapine 75mg bd"
            ),
        ]

        other_note = Fake.en.word(other_notes)

        relation_name = obj.patient.related_patient_name
        formatted_dob = obj.patient.dob.strftime(obj.dob_format)
        note_date_formatted = obj.note_datetime.strftime(obj.note_date_format)

        note_text = (
            f"I saw {obj.patient.forename} {obj.patient.surname} on "
            f"{note_date_formatted} "
            f"(DOB: {formatted_dob}, NHS {obj.patient.nhsnum}, "
            f"Patient id: {obj.patient.patient_id}), "
            f"accompanied by {obj.patient.possessive_pronoun} "
            f"{obj.patient.related_patient_relationship} {relation_name}. "
            f"{obj.alcohol}. "
            f"Another date: {obj.another_date_formatted}. "
            f"{other_note}."
        )

        num_pad_words = obj.words_per_note - len(note_text.split())
        pad_words = " ".join(obj.pad_paragraph.split()[:num_pad_words])
        note_text = f"{note_text} {pad_words}"

        return note_text
