"""
crate_anon/crateweb/consent/management/commands/make_test_consent_data.py

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

**Django management command to create test data for the consent app.**


"""

from argparse import ArgumentParser
from dataclasses import dataclass
import datetime
import random
from typing import Any

from dateutil.relativedelta import relativedelta
import factory

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.urls import reverse

from crate_anon.crateweb.consent.models import (
    ClinicianResponse,
    ConsentMode,
    ContactRequest,
    DummyPatientSourceInfo,
    Email,
    EmailTransmission,
    Study,
)
from crate_anon.crateweb.consent.factories import (
    ConsentModeFactory,
    ContactRequestFactory,
    DummyPatientSourceInfoFactory,
    StudyFactory,
)
from crate_anon.crateweb.core.utils import site_absolute_url
from crate_anon.crateweb.userprofile.factories import UserFactory
from crate_anon.crateweb.userprofile.models import UserProfile


@dataclass
class ConsentDataMaker:
    age: int
    age_months: int
    consent_mode: str
    request_direct_approach: bool
    seed: int

    def __post_init__(self) -> None:
        self.admin_username = "test_admin"
        self.lead_researcher_username = "test_lead_researcher"
        self.study_title = "Test study title"
        self.nhs_number = 9991106847
        today = datetime.date.today()
        self.dob = today - relativedelta(
            years=self.age, months=self.age_months
        )

    def make(self) -> None:
        random.seed(self.seed)
        factory.random.reseed_random(self.seed)

        self.delete_old_test_data()

        self.create_new_test_data()
        self.contact_request.process_request()
        self.dump_html()

    def create_new_test_data(self) -> None:
        admin = UserFactory(
            username=self.admin_username, first_name="Adam", last_name="Inn"
        )
        admin.profile.title = "Mr"
        admin.profile.save()

        lead_researcher = UserFactory(
            username=self.lead_researcher_username,
            first_name="Lee",
            last_name="Dresearcher",
        )
        lead_researcher.profile.title = "Dr"
        lead_researcher.profile.save()

        clinician_involvement = ContactRequest.get_clinician_involvement(
            consent_mode_str=self.consent_mode,
            request_direct_approach=self.request_direct_approach,
        )
        study = StudyFactory(
            title=self.study_title,
            lead_researcher=lead_researcher,
            request_direct_approach=self.request_direct_approach,
        )
        self.consent_mode = ConsentModeFactory(
            created_by=admin, consent_mode=self.consent_mode
        )
        DummyPatientSourceInfoFactory(
            nhs_number=self.nhs_number, pt_dob=self.dob
        )
        self.contact_request = ContactRequestFactory(
            request_by=admin,
            study=study,
            consent_mode=self.consent_mode,
            lookup_nhs_number=self.nhs_number,
            clinician_involvement=clinician_involvement,
        )

    def dump_html(self) -> None:
        contact_request_pk = self.contact_request.pk
        patient_lookup_pk = self.contact_request.patient_lookup.pk
        consent_mode_pk = self.contact_request.consent_mode.pk
        clinician_response = self.contact_request.clinician_response
        clincian_response_pk = clinician_response.pk
        token = clinician_response.token

        print("""
        <!doctype html>
        <html lang="en">
        <body>
        <ul>
        """)

        self.dump_link(
            "Covering letter for first traffic-light decision form (PDF)",
            "draft_first_traffic_light_letter",
            patient_lookup_id=patient_lookup_pk,
            viewtype="pdf",
        )
        self.dump_link(
            "Covering letter for first traffic-light decision form (HTML)",
            "draft_first_traffic_light_letter",
            patient_lookup_id=patient_lookup_pk,
            viewtype="html",
        )
        self.dump_link(
            "Traffic-light decision form, personalized (PDF)",
            "draft_traffic_light_decision_form",
            patient_lookup_id=patient_lookup_pk,
            viewtype="pdf",
        )
        self.dump_link(
            "Traffic-light decision form, personalized (HTML)",
            "draft_traffic_light_decision_form",
            patient_lookup_id=patient_lookup_pk,
            viewtype="html",
        )
        self.dump_link(
            "Traffic-light decision form, generic (PDF)",
            "draft_traffic_light_decision_form_generic",
            viewtype="pdf",
        )
        self.dump_link(
            "Traffic-light decision form, generic (HTML)",
            "draft_traffic_light_decision_form_generic",
            viewtype="html",
        )
        self.dump_link(
            "Letter confirming traffic-light decision (PDF)",
            "draft_confirm_traffic_light_letter",
            consent_mode_id=consent_mode_pk,
            viewtype="pdf",
        )
        self.dump_link(
            "Letter confirming traffic-light decision (HTML)",
            "draft_confirm_traffic_light_letter",
            consent_mode_id=consent_mode_pk,
            viewtype="html",
        )
        self.dump_link(
            "E-mail to clinician",
            "draft_clinician_email",
            contact_request_id=contact_request_pk,
        )
        self.dump_link(
            'Clinician "tell me more" response view',
            "clinician_response",
            query=f"?token={token}&email_choice=more",
            clinician_response_id=clincian_response_pk,
        )
        self.dump_link(
            "Letter from clinician to patient re study (HTML)",
            "draft_letter_clinician_to_pt_re_study",
            contact_request_id=contact_request_pk,
            viewtype="html",
        )
        self.dump_link(
            "Letter from clinician to patient re study (PDF)",
            "draft_letter_clinician_to_pt_re_study",
            contact_request_id=contact_request_pk,
            viewtype="pdf",
        )
        self.dump_link(
            "Decision form to patient re study (HTML)",
            "decision_form_to_pt_re_study",
            contact_request_id=contact_request_pk,
            viewtype="html",
        )
        self.dump_link(
            "Decision form to patient re study (PDF)",
            "decision_form_to_pt_re_study",
            contact_request_id=contact_request_pk,
            viewtype="pdf",
        )
        self.dump_link(
            "Approval letter to researcher (HTML)",
            "draft_approval_letter",
            contact_request_id=contact_request_pk,
            viewtype="html",
        )
        self.dump_link(
            "Approval letter to researcher (PDF)",
            "draft_approval_letter",
            contact_request_id=contact_request_pk,
            viewtype="pdf",
        )
        self.dump_link(
            "Approval covering e-mail to researcher",
            "draft_approval_email",
            contact_request_id=contact_request_pk,
        )
        self.dump_link(
            "Template cover letter from researcher to patient (HTML)",
            "draft_researcher_cover_letter",
            viewtype="html",
        )
        self.dump_link(
            "Template cover letter from researcher to patient (PDF)",
            "draft_researcher_cover_letter",
            viewtype="pdf",
        )
        self.dump_link(
            "Withdrawal letter to researcher (HTML)",
            "draft_withdrawal_letter",
            contact_request_id=contact_request_pk,
            viewtype="html",
        )
        self.dump_link(
            "Withdrawal letter to researcher (PDF)",
            "draft_withdrawal_letter",
            contact_request_id=contact_request_pk,
            viewtype="pdf",
        )
        self.dump_link(
            "Withdrawal covering e-mail to researcher",
            "draft_withdrawal_email",
            contact_request_id=contact_request_pk,
        )
        print("""
        </ul>
        </body>
        </html>
        """)

    def dump_link(
        self, text: str, view_name: str, query: str = "", **kwargs: Any
    ) -> None:
        url = site_absolute_url(reverse(view_name, kwargs=kwargs))

        print(f'<li><a href="{url}{query}">{text}</a></li>')

    def delete_old_test_data(self) -> None:
        DummyPatientSourceInfo.objects.filter(
            nhs_number=self.nhs_number
        ).delete()
        EmailTransmission.objects.filter(
            email__contact_request__request_by__username=self.admin_username
        ).delete()
        Email.objects.filter(
            contact_request__request_by__username=self.admin_username
        ).delete()
        ClinicianResponse.objects.filter(
            contact_request__request_by__username=self.admin_username
        ).delete()
        ContactRequest.objects.filter(
            request_by__username=self.admin_username
        ).delete()
        ConsentMode.objects.filter(
            created_by__username=self.admin_username
        ).delete()
        Study.objects.filter(title=self.study_title).delete()
        UserProfile.objects.filter(
            user__username=self.lead_researcher_username
        ).delete()
        User.objects.filter(username=self.lead_researcher_username).delete()
        User.objects.filter(username=self.admin_username).delete()


class Command(BaseCommand):
    help = "Developer command to create test data for the consent app"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--seed", type=int, default=123456, help="Random seed"
        )
        parser.add_argument(
            "--age", type=int, default=40, help="Age of patient"
        )
        parser.add_argument(
            "--age_months",
            type=int,
            default=0,
            help="Add this number of months to the patient's age",
        )
        parser.add_argument(
            "--consent_mode",
            choices=[
                ConsentMode.RED,
                ConsentMode.YELLOW,
                ConsentMode.GREEN,
            ],
            default="",
        )
        parser.add_argument(
            "--request_direct_approach",
            action="store_true",
            default=True,
            help="Request direct approach",
        )
        parser.add_argument(
            "--no_request_direct_approach",
            dest="request_direct_approach",
            action="store_false",
            default=False,
            help="Don't request direct approach",
        )

    def handle(self, *args: str, **options: Any) -> None:
        options_dict = {
            k: v
            for (k, v) in options.items()
            if k
            in [
                "seed",
                "age",
                "age_months",
                "consent_mode",
                "request_direct_approach",
            ]
        }
        maker = ConsentDataMaker(**options_dict)
        maker.make()
