"""
crate_anon/crateweb/consent/factories.py

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

**Factory Boy Django test factories.**

"""

from typing import TYPE_CHECKING

import factory
from faker_file.providers.pdf_file.generators.reportlab_generator import (
    ReportlabPdfGenerator,
)
from faker_file.storages.filesystem import FileSystemStorage
from django.conf import settings

from crate_anon.crateweb.consent.models import (
    CharityPaymentRecord,
    ClinicianResponse,
    ConsentMode,
    ContactRequest,
    Decision,
    DummyPatientSourceInfo,
    Email,
    EmailAttachment,
    EmailTransmission,
    Leaflet,
    Letter,
    PatientLookup,
    PatientResponse,
    Study,
    TeamRep,
)
from crate_anon.crateweb.userprofile.factories import UserFactory
from crate_anon.testing.factories import Fake

FS_STORAGE = FileSystemStorage(root_path=settings.MEDIA_ROOT, rel_path="tmp")

if TYPE_CHECKING:
    from factory.builder import Resolver


class StudyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Study

    institutional_id = factory.Sequence(lambda n: n + 1)
    title = factory.Sequence(lambda n: f"study-{n + 1}")
    lead_researcher = factory.SubFactory(UserFactory)

    patient_contact = True
    include_under_16s = True
    include_lack_capacity = True
    clinical_trial = True
    include_discharged = True
    request_direct_approach = True
    approved_by_rec = True
    approved_locally = True

    @factory.lazy_attribute
    def study_details_pdf(obj: "Resolver") -> str:
        return Fake.en_gb.pdf_file(
            pdf_generator_cls=ReportlabPdfGenerator,
            storage=FS_STORAGE,
        )


class LeafletFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Leaflet

    name = factory.Sequence(lambda n: f"leaflet-{n + 1}")


class DecisionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Decision


class ConsentModeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ConsentMode

    nhs_number = factory.LazyFunction(Fake.en_gb.nhs_number)
    created_by = factory.SubFactory(UserFactory)


class PatientLookupFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PatientLookup

    nhs_number = factory.LazyFunction(Fake.en_gb.nhs_number)


class DummyPatientSourceInfoFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DummyPatientSourceInfo
        exclude = (
            "patient_address_dict",
            "gp_address_dict",
            "clinician_address_dict",
        )

    nhs_number = factory.LazyFunction(Fake.en_gb.nhs_number)

    pt_dob = factory.LazyFunction(Fake.en_gb.consistent_date_of_birth)
    pt_sex = factory.LazyFunction(Fake.en_gb.sex)

    @factory.lazy_attribute
    def pt_first_name(obj: "Resolver") -> str:
        return Fake.en_gb.forename(obj.pt_sex)

    pt_last_name = factory.LazyFunction(Fake.en_gb.last_name)

    @factory.lazy_attribute
    def patient_address_dict(obj: "Resolver") -> dict[int, str]:
        return {k: v for k, v in enumerate(Fake.en_gb.address().split("\n"))}

    @factory.lazy_attribute
    def pt_address_1(obj: "Resolver") -> str:
        return obj.patient_address_dict.get(0, "")

    @factory.lazy_attribute
    def pt_address_2(obj: "Resolver") -> str:
        return obj.patient_address_dict.get(1, "")

    @factory.lazy_attribute
    def pt_address_3(obj: "Resolver") -> str:
        return obj.patient_address_dict.get(2, "")

    @factory.lazy_attribute
    def pt_address_4(obj: "Resolver") -> str:
        return obj.patient_address_dict.get(3, "")

    @factory.lazy_attribute
    def pt_address_5(obj: "Resolver") -> str:
        return obj.patient_address_dict.get(4, "")

    @factory.lazy_attribute
    def pt_address_6(obj: "Resolver") -> str:
        return obj.patient_address_dict.get(5, "")

    @factory.lazy_attribute
    def pt_address_7(obj: "Resolver") -> str:
        return obj.patient_address_dict.get(6, "")

    pt_telephone = factory.LazyFunction(Fake.en_gb.phone_number)
    pt_email = factory.LazyFunction(Fake.en_gb.email)

    gp_title = "Dr"
    gp_first_name = factory.LazyFunction(Fake.en_gb.first_name)
    gp_last_name = factory.LazyFunction(Fake.en_gb.last_name)

    @factory.lazy_attribute
    def gp_address_dict(obj: "Resolver") -> dict[int, str]:
        return {
            k: v
            for k, v in enumerate(
                Fake.en_gb.healthcare_facility_address().split("\n")
            )
        }

    @factory.lazy_attribute
    def gp_address_1(obj: "Resolver") -> str:
        return obj.gp_address_dict.get(0, "")

    @factory.lazy_attribute
    def gp_address_2(obj: "Resolver") -> str:
        return obj.gp_address_dict.get(1, "")

    @factory.lazy_attribute
    def gp_address_3(obj: "Resolver") -> str:
        return obj.gp_address_dict.get(2, "")

    @factory.lazy_attribute
    def gp_address_4(obj: "Resolver") -> str:
        return obj.gp_address_dict.get(3, "")

    @factory.lazy_attribute
    def gp_address_5(obj: "Resolver") -> str:
        return obj.gp_address_dict.get(4, "")

    @factory.lazy_attribute
    def gp_address_6(obj: "Resolver") -> str:
        return obj.gp_address_dict.get(5, "")

    @factory.lazy_attribute
    def gp_address_7(obj: "Resolver") -> str:
        return obj.gp_address_dict.get(6, "")

    gp_telephone = factory.LazyFunction(Fake.en_gb.phone_number)
    gp_email = factory.LazyFunction(Fake.en_gb.email)

    clinician_title = "Dr"
    clinician_first_name = factory.LazyFunction(Fake.en_gb.first_name)
    clinician_last_name = factory.LazyFunction(Fake.en_gb.last_name)

    @factory.lazy_attribute
    def clinician_address_dict(obj: "Resolver") -> dict[int, str]:
        return {
            k: v
            for k, v in enumerate(
                Fake.en_gb.healthcare_facility_address().split("\n")
            )
        }

    @factory.lazy_attribute
    def clinician_address_1(obj: "Resolver") -> str:
        return obj.clinician_address_dict.get(0, "")

    @factory.lazy_attribute
    def clinician_address_2(obj: "Resolver") -> str:
        return obj.clinician_address_dict.get(1, "")

    @factory.lazy_attribute
    def clinician_address_3(obj: "Resolver") -> str:
        return obj.clinician_address_dict.get(2, "")

    @factory.lazy_attribute
    def clinician_address_4(obj: "Resolver") -> str:
        return obj.clinician_address_dict.get(3, "")

    @factory.lazy_attribute
    def clinician_address_5(obj: "Resolver") -> str:
        return obj.clinician_address_dict.get(4, "")

    @factory.lazy_attribute
    def clinician_address_6(obj: "Resolver") -> str:
        return obj.clinician_address_dict.get(5, "")

    @factory.lazy_attribute
    def clinician_address_7(obj: "Resolver") -> str:
        return obj.clinician_address_dict.get(6, "")

    clinician_telephone = factory.LazyFunction(Fake.en_gb.phone_number)
    clinician_email = factory.LazyFunction(Fake.en_gb.email)
    clinician_signatory_title = factory.LazyFunction(
        Fake.en_gb.medical_job_title
    )


class TeamRepFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TeamRep

    team = factory.Sequence(lambda n: f"team-{n + 1}")
    user = factory.SubFactory(UserFactory)


class CharityPaymentRecordFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CharityPaymentRecord


class ContactRequestFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ContactRequest

    request_by = factory.SubFactory(UserFactory)
    study = factory.SubFactory(StudyFactory)
    request_direct_approach = True

    patient_lookup = factory.SubFactory(PatientLookupFactory)
    consent_mode = factory.SubFactory(ConsentModeFactory)


class PatientResponseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PatientResponse

    contact_request = factory.SubFactory(ContactRequestFactory)
    recorded_by = factory.SubFactory(UserFactory)


class ClinicianResponseFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = ClinicianResponse


class LetterFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Letter

    study = factory.SubFactory(StudyFactory)
    contact_request = factory.SubFactory(ContactRequestFactory)


class EmailFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Email

    study = factory.SubFactory(StudyFactory)
    contact_request = factory.SubFactory(ContactRequestFactory)


class EmailAttachmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailAttachment

    email = factory.SubFactory(EmailFactory)


class EmailTransmissionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = EmailTransmission

    email = factory.SubFactory(EmailFactory)
    by = factory.SubFactory(UserFactory)
