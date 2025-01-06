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
import factory
import factory.random
from faker import Faker

from crate_anon.testing.models import EnumColours, FilenameDoc, Note, Patient
from crate_anon.testing.providers import register_all_providers

if TYPE_CHECKING:
    from factory.builder import Resolver
    from sqlalchemy.orm.session import Session


# When running with pytest sqlalchemy_session gets poked in by
# DatabaseTestCase.setUp(). Otherwise call
# set_sqlalchemy_session_on_all_factories()
class BaseFactory(factory.alchemy.SQLAlchemyModelFactory):
    pass


def set_sqlalchemy_session_on_all_factories(dbsession: "Session") -> None:
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
    # MB 2024-02-19
    # Factory Boy has its own interface to Faker (factory.Faker()). This
    # takes a function to be called at object generation time and as far as I
    # can tell this doesn't support being able to create fake data based on
    # other fake attributes such as notes for a patient. You can work
    # around this by adding a lot of logic to the factories. To me it makes
    # sense to keep the factories simple and do as much as possible of the
    # content generation in the providers. So we call Faker directly instead.
    en_gb = Faker("en_GB")  # For UK postcodes, phone numbers etc
    en_us = Faker("en_US")  # en_GB gives Lorem ipsum for pad words.


register_all_providers(Fake.en_gb)


class DemoFactory(BaseFactory):
    class Meta:
        abstract = True


class DemoPatientFactory(DemoFactory):
    class Meta:
        model = Patient

    patient_id = factory.Sequence(lambda n: n + 1)

    sex = factory.LazyFunction(Fake.en_gb.sex)

    @factory.lazy_attribute
    def forename(obj: "Resolver") -> str:
        return Fake.en_gb.forename(obj.sex)

    surname = factory.LazyFunction(Fake.en_gb.last_name)
    dob = factory.LazyFunction(Fake.en_gb.consistent_date_of_birth)
    nhsnum = factory.LazyFunction(Fake.en_gb.nhs_number)

    phone = factory.LazyFunction(Fake.en_gb.phone_number)
    postcode = factory.LazyFunction(Fake.en_gb.postcode)

    @factory.lazy_attribute
    def related_patient(obj: "Resolver") -> int:
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

    related_patient_relationship = factory.LazyFunction(
        Fake.en_gb.relationship
    )

    @factory.lazy_attribute
    def colour(obj: "Resolver") -> EnumColours:
        return EnumColours.blue if coin() else None

    @factory.post_generation
    def notes(obj: "Resolver", create: bool, extracted: int, **kwargs) -> None:
        if not create:
            return

        if extracted:
            DemoNoteFactory.create_batch(size=extracted, patient=obj, **kwargs)


class DemoNoteFactory(DemoFactory):
    class Meta:
        model = Note

    class Params:
        words_per_note = 100

    note_datetime = factory.LazyFunction(Fake.en_gb.incrementing_date)

    @factory.lazy_attribute
    def note(obj: "Resolver") -> str:
        # Use en_US because you get Lorem ipsum with en_GB.
        pad_paragraph = Fake.en_us.paragraph(
            nb_sentences=obj.words_per_note / 2,  # way more than we need
        )

        return Fake.en_gb.patient_note(
            forename=obj.patient.forename,
            surname=obj.patient.surname,
            sex=obj.patient.sex,
            dob=obj.patient.dob,
            nhs_number=obj.patient.nhsnum,
            patient_id=obj.patient.patient_id,
            note_datetime=obj.note_datetime,
            relation_name=obj.patient.related_patient_name,
            relation_relationship=obj.patient.related_patient_relationship,
            words_per_note=obj.words_per_note,
            pad_paragraph=pad_paragraph,
        )


class DemoFilenameDocFactory(DemoFactory):
    class Meta:
        model = FilenameDoc

    file_datetime = factory.LazyFunction(Fake.en_gb.incrementing_date)

    @factory.lazy_attribute
    def filename(obj: "Resolver") -> str:
        # Use en_US because you get Lorem ipsum with en_GB.
        pad_paragraph = Fake.en_us.paragraph(nb_sentences=50)

        return Fake.en_gb.patient_filename(
            forename=obj.patient.forename,
            surname=obj.patient.surname,
            sex=obj.patient.sex,
            dob=obj.patient.dob,
            nhs_number=obj.patient.nhsnum,
            patient_id=obj.patient.patient_id,
            pad_paragraph=pad_paragraph,
        )
