#!/usr/bin/env python
# crate_anon/crateweb/consent/models.py

"""
===============================================================================
    Copyright (C) 2015-2018 Rudolf Cardinal (rudolf@pobox.com).

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
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.
===============================================================================
"""

import datetime
from dateutil.relativedelta import relativedelta
import logging
import os
from typing import Any, List, Optional, Tuple, Type, Union

# from audit_log.models import AuthStampedModel  # django-audit-log
from cardinal_pythonlib.django.admin import admin_view_url
from cardinal_pythonlib.django.fields.helpers import choice_explanation
from cardinal_pythonlib.django.fields.restrictedcontentfile import ContentTypeRestrictedFileField  # noqa
from cardinal_pythonlib.django.files import (
    auto_delete_files_on_instance_change,
    auto_delete_files_on_instance_delete,
)
from cardinal_pythonlib.django.reprfunc import modelrepr
from cardinal_pythonlib.logs import BraceStyleAdapter
from cardinal_pythonlib.pdf import get_concatenated_pdf_in_memory
from cardinal_pythonlib.reprfunc import simple_repr
from django import forms
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.core.urlresolvers import reverse
from django.core.validators import validate_email
from django.db import models, transaction
from django.db.models import Q, QuerySet
from django.dispatch import receiver
from django.http import QueryDict, Http404
from django.http.request import HttpRequest
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property

from crate_anon.common.contenttypes import ContentType
from crate_anon.crateweb.config.constants import (
    ClinicalDatabaseType,
    SOURCE_DB_NAME_MAX_LENGTH,
)
from crate_anon.crateweb.core.constants import (
    LEN_ADDRESS,
    LEN_FIELD_DESCRIPTION,
    LEN_NAME,
    LEN_PHONE,
    LEN_TITLE,
    MAX_HASH_LENGTH,
)
from crate_anon.crateweb.core.utils import (
    site_absolute_url,
    string_time_now,
    url_with_querystring,
)
from crate_anon.crateweb.extra.pdf import (
    make_pdf_on_disk_from_html_with_django_settings,
    CratePdfPlan,
)
from crate_anon.crateweb.extra.salutation import (
    forename_surname,
    get_initial_surname_tuple_from_string,
    salutation,
    title_forename_surname,
)
from crate_anon.crateweb.consent.storage import privatestorage
from crate_anon.crateweb.consent.tasks import (
    email_rdbm_task,
    process_contact_request,
)
from crate_anon.crateweb.consent.teamlookup import get_teams
from crate_anon.crateweb.consent.utils import (
    days_to_years,
    make_cpft_email_address,
    render_email_html_to_string,
    render_pdf_html_to_string,
    to_date,
    validate_researcher_email_domain,
)
from crate_anon.crateweb.research.models import get_mpid
from crate_anon.crateweb.research.research_db_info import research_database_info  # noqa

log = BraceStyleAdapter(logging.getLogger(__name__))

CLINICIAN_RESPONSE_FWD_REF = "ClinicianResponse"
CONSENT_MODE_FWD_REF = "ConsentMode"
CONTACT_REQUEST_FWD_REF = "ContactRequest"
EMAIL_FWD_REF = "Email"
EMAIL_TRANSMISSION_FWD_REF = "EmailTransmission"
LEAFLET_FWD_REF = "Leaflet"
LETTER_FWD_REF = "Letter"
STUDY_FWD_REF = "Study"

TEST_ID = -1
TEST_ID_STR = str(TEST_ID)


# =============================================================================
# Study
# =============================================================================

def study_details_upload_to(instance: STUDY_FWD_REF, filename: str) -> str:
    """
    Determines the filename used for study information PDF uploads.
    instance = instance of Study (potentially unsaved)
        ... and you can't call save(); it goes into infinite recursion
    filename = uploaded filename
    """
    extension = os.path.splitext(filename)[1]  # includes the '.' if present
    return os.path.join("study", "{}_details_{}{}".format(
        instance.institutional_id,
        string_time_now(),
        extension))
    # ... as id may not exist yet


def study_form_upload_to(instance: STUDY_FWD_REF, filename: str) -> str:
    """
    Determines the filename used for study clinician-form PDF uploads.
    instance = instance of Study (potentially unsaved)
    filename = uploaded filename
    """
    extension = os.path.splitext(filename)[1]
    return os.path.join("study", "{}_form_{}{}".format(
        instance.institutional_id,
        string_time_now(),
        extension))


class Study(models.Model):
    # implicit 'id' field
    institutional_id = models.PositiveIntegerField(
        verbose_name="Institutional (e.g. NHS Trust) study number",
        unique=True)
    title = models.CharField(max_length=255, verbose_name="Study title")
    lead_researcher = models.ForeignKey(settings.AUTH_USER_MODEL,
                                        related_name="studies_as_lead")
    researchers = models.ManyToManyField(settings.AUTH_USER_MODEL,
                                         related_name="studies_as_researcher",
                                         blank=True)
    registered_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="When was the study registered?")
    summary = models.TextField(verbose_name="Summary of study")
    search_methods_planned = models.TextField(
        blank=True,
        verbose_name="Search methods planned")
    patient_contact = models.BooleanField(
        verbose_name="Involves patient contact?")
    include_under_16s = models.BooleanField(
        verbose_name="Include patients under 16?")
    include_lack_capacity = models.BooleanField(
        verbose_name="Include patients lacking capacity?")
    clinical_trial = models.BooleanField(
        verbose_name="Clinical trial (CTIMP)?")
    include_discharged = models.BooleanField(
        verbose_name="Include discharged patients?")
    request_direct_approach = models.BooleanField(
        verbose_name="Researchers request direct approach to patients?")
    approved_by_rec = models.BooleanField(
        verbose_name="Approved by REC?")
    rec_reference = models.CharField(
        max_length=50, blank=True,
        verbose_name="Research Ethics Committee reference")
    approved_locally = models.BooleanField(
        verbose_name="Approved by local institution?")
    local_approval_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="When approved by local institution?")
    study_details_pdf = ContentTypeRestrictedFileField(
        blank=True,
        storage=privatestorage,
        content_types=[ContentType.PDF],
        max_upload_size=settings.MAX_UPLOAD_SIZE_BYTES,
        upload_to=study_details_upload_to)
    subject_form_template_pdf = ContentTypeRestrictedFileField(
        blank=True,
        storage=privatestorage,
        content_types=[ContentType.PDF],
        max_upload_size=settings.MAX_UPLOAD_SIZE_BYTES,
        upload_to=study_form_upload_to)
    # http://nemesisdesign.net/blog/coding/django-private-file-upload-and-serving/  # noqa
    # http://stackoverflow.com/questions/8609192/differentiate-null-true-blank-true-in-django  # noqa
    AUTODELETE_OLD_FILE_FIELDS = ['study_details_pdf',
                                  'subject_form_template_pdf']

    class Meta:
        verbose_name_plural = "studies"

    def __str__(self):
        return "[Study {}] {}: {} / {}".format(
            self.id,
            self.institutional_id,
            self.lead_researcher.get_full_name(),
            self.title
        )

    def get_lead_researcher_name_address(self) -> List[str]:
        return (
            [self.lead_researcher.profile.get_title_forename_surname()] +
            self.lead_researcher.profile.get_address_components()
        )

    def get_lead_researcher_salutation(self) -> str:
        return self.lead_researcher.profile.get_salutation()

    def get_involves_lack_of_capacity(self) -> str:
        if not self.include_lack_capacity:
            return "No"
        if self.clinical_trial:
            return "Yes (and it is a clinical trial)"
        return "Yes (and it is not a clinical trial)"

    @staticmethod
    def get_queryset_possible_contact_studies() -> QuerySet:
        return (
            Study.objects
            .filter(patient_contact=True)
            .filter(approved_by_rec=True)
            .filter(approved_locally=True)
            .exclude(study_details_pdf='')
            .exclude(lead_researcher__profile__title='')
            .exclude(lead_researcher__first_name='')
            .exclude(lead_researcher__last_name='')
        )

    @staticmethod
    def filter_studies_for_researcher(
            queryset: QuerySet,
            user: settings.AUTH_USER_MODEL) -> QuerySet:
        return queryset.filter(Q(lead_researcher=user) |
                               Q(researchers__in=[user]))\
                       .distinct()


# noinspection PyUnusedLocal
@receiver(models.signals.post_delete, sender=Study)
def auto_delete_study_files_on_delete(sender: Type[Study],
                                      instance: Study,
                                      **kwargs: Any) -> None:
    """Deletes files from filesystem when Study object is deleted."""
    auto_delete_files_on_instance_delete(instance,
                                         Study.AUTODELETE_OLD_FILE_FIELDS)


# noinspection PyUnusedLocal
@receiver(models.signals.pre_save, sender=Study)
def auto_delete_study_files_on_change(sender: Type[Study],
                                      instance: Study,
                                      **kwargs: Any) -> None:
    """Deletes files from filesystem when Study object is changed."""
    auto_delete_files_on_instance_change(instance,
                                         Study.AUTODELETE_OLD_FILE_FIELDS,
                                         Study)


# =============================================================================
# Generic leaflets
# =============================================================================

def leaflet_upload_to(instance: LEAFLET_FWD_REF, filename: str) -> str:
    """
    Determines the filename used for leaflet uploads.
    instance = instance of Leaflet (potentially unsaved)
        ... and you can't call save(); it goes into infinite recursion
    filename = uploaded filename
    """
    extension = os.path.splitext(filename)[1]  # includes the '.' if present
    return os.path.join("leaflet", "{}_{}{}".format(
        instance.name,
        string_time_now(),
        extension))
    # ... as id may not exist yet


class Leaflet(models.Model):
    CPFT_TPIR = 'cpft_tpir'  # mandatory
    NIHR_YHRSL = 'nihr_yhrsl'  # not used automatically
    CPFT_TRAFFICLIGHT_CHOICE = 'cpft_trafficlight_choice'
    CPFT_CLINRES = 'cpft_clinres'

    LEAFLET_CHOICES = (
        (CPFT_TPIR, 'CPFT: Taking part in research [MANDATORY]'),
        (NIHR_YHRSL,
         'NIHR: Your health records save lives [not currently used]'),
        (CPFT_TRAFFICLIGHT_CHOICE,
         'CPFT: traffic-light choice decision form [not currently used: '
         'personalized version created instead]'),
        (CPFT_CLINRES, 'CPFT: clinical research [not currently used]'),
    )
    # https://docs.djangoproject.com/en/dev/ref/models/fields/#django.db.models.Field.choices  # noqa

    name = models.CharField(max_length=50, unique=True,
                            choices=LEAFLET_CHOICES,
                            verbose_name="leaflet name")
    pdf = ContentTypeRestrictedFileField(
        blank=True,
        storage=privatestorage,
        content_types=[ContentType.PDF],
        max_upload_size=settings.MAX_UPLOAD_SIZE_BYTES,
        upload_to=leaflet_upload_to)

    def __str__(self):
        for x in Leaflet.LEAFLET_CHOICES:
            if x[0] == self.name:
                name = x[1]
                if not self.pdf:
                    name += " (MISSING)"
                return name
        return "? (bad name: {})".format(self.name)

    @staticmethod
    def populate() -> None:
        # Pre-create instances
        keys = [x[0] for x in Leaflet.LEAFLET_CHOICES]
        for x in keys:
            if not Leaflet.objects.filter(name=x).exists():
                obj = Leaflet(name=x)
                obj.save()


# noinspection PyUnusedLocal
@receiver(models.signals.post_delete, sender=Leaflet)
def auto_delete_leaflet_files_on_delete(sender: Type[Leaflet],
                                        instance: Leaflet,
                                        **kwargs: Any) -> None:
    """Deletes files from filesystem when Leaflet object is deleted."""
    auto_delete_files_on_instance_delete(instance, ['pdf'])


# noinspection PyUnusedLocal
@receiver(models.signals.pre_save, sender=Leaflet)
def auto_delete_leaflet_files_on_change(sender: Type[Leaflet],
                                        instance: Leaflet,
                                        **kwargs: Any) -> None:
    """Deletes files from filesystem when Leaflet object is changed."""
    auto_delete_files_on_instance_change(instance, ['pdf'], Leaflet)


# =============================================================================
# Generic fields for decisions
# =============================================================================

class Decision(models.Model):
    # Note that Decision._meta.get_fields() doesn't care about the
    # ordering of its fields (and, I think, they can change). So:
    FIELDS = [
        'decision_signed_by_patient',
        'decision_otherwise_directly_authorized_by_patient',
        'decision_under16_signed_by_parent',
        'decision_under16_signed_by_clinician',
        'decision_lack_capacity_signed_by_representative',
        'decision_lack_capacity_signed_by_clinician',
    ]
    decision_signed_by_patient = models.BooleanField(
        default=False,
        verbose_name="Request signed by patient?")
    decision_otherwise_directly_authorized_by_patient = models.BooleanField(
        default=False,
        verbose_name="Request otherwise directly authorized by patient?")
    decision_under16_signed_by_parent = models.BooleanField(
        default=False,
        verbose_name="Patient under 16 and request countersigned by parent?")
    decision_under16_signed_by_clinician = models.BooleanField(
        default=False,
        verbose_name="Patient under 16 and request countersigned by "
                     "clinician?")
    decision_lack_capacity_signed_by_representative = models.BooleanField(
        default=False,
        verbose_name="Patient lacked capacity and request signed by "
                     "authorized representative?")
    decision_lack_capacity_signed_by_clinician = models.BooleanField(
        default=False,
        verbose_name="Patient lacked capacity and request countersigned by "
                     "clinician?")

    class Meta:
        abstract = True

    def decision_valid(self) -> bool:
        # We can never electronically validate being under 16 (time may have
        # passed since the lookup) or, especially, lacking capacity, so let's
        # just trust the user
        return (
            self.decision_signed_by_patient or
            self.decision_otherwise_directly_authorized_by_patient
        ) or (
            # Lacks capacity
            self.decision_lack_capacity_signed_by_representative and
            self.decision_lack_capacity_signed_by_clinician
        ) or (
            # Under 16: 2/3 rule
            int(self.decision_signed_by_patient or
                self.decision_otherwise_directly_authorized_by_patient) +
            int(self.decision_under16_signed_by_parent) +
            int(self.decision_under16_signed_by_clinician) >= 2
            # I know the logic overlaps. But there you go.
        )

    def validate_decision(self) -> None:
        if not self.decision_valid():
            raise forms.ValidationError(
                "Invalid decision. Options are: "
                "(*) Signed/authorized by patient. "
                "(*) Lacks capacity - signed by rep + clinician. "
                "(*) Under 16 - signed by 2/3 of (patient, clinician, "
                "parent); see special rules")


# =============================================================================
# Information about patient captured from clinical database
# =============================================================================

class ClinicianInfoHolder(object):
    CARE_COORDINATOR = 'care_coordinator'
    CONSULTANT = 'consultant'
    HCP = 'HCP'
    TEAM = 'team'

    def __init__(self, clinician_type: str,
                 title: str, first_name: str, surname: str, email: str,
                 signatory_title: str, is_consultant: bool,
                 start_date: Union[datetime.date, datetime.datetime],
                 end_date: Union[datetime.date, datetime.datetime],
                 address_components: List[str] = None) -> None:
        self.clinician_type = clinician_type
        self.title = title
        self.first_name = first_name
        self.surname = surname
        self.email = email or make_cpft_email_address(first_name, surname)
        self.signatory_title = signatory_title
        self.is_consultant = is_consultant
        self.start_date = to_date(start_date)
        self.end_date = to_date(end_date)
        self.address_components = address_components or []  # type: List[str]

        if clinician_type == self.CARE_COORDINATOR:
            self.clinician_preference_order = 1  # best
        elif clinician_type == self.CONSULTANT:
            self.clinician_preference_order = 2
        elif clinician_type == self.HCP:
            self.clinician_preference_order = 3
        elif clinician_type == self.TEAM:
            self.clinician_preference_order = 4
        else:
            self.clinician_preference_order = 99999  # worst

    def __repr__(self) -> str:
        return simple_repr(self, [
            'clinician_type',
            'title',
            'first_name',
            'surname',
            'email',
            'signatory_title',
            'is_consultant',
            'start_date',
            'end_date',
            'address_components',
        ])

    def current(self) -> bool:
        return self.end_date is None or self.end_date >= datetime.date.today()

    def contactable(self) -> bool:
        return bool(self.surname and self.email)


class PatientLookupBase(models.Model):
    """
    Base class for PatientLookup and DummyPatientSourceInfo.
    Must be able to be instantiate with defaults, for the "not found"
    situation.
    """

    MALE = 'M'
    FEMALE = 'F'
    INTERSEX = 'X'
    UNKNOWNSEX = '?'
    SEX_CHOICES = (
        (MALE, 'Male'),
        (FEMALE, 'Female'),
        (INTERSEX, 'Inderminate/intersex'),
        (UNKNOWNSEX, 'Unknown'),
    )

    # Details of lookup
    pt_local_id_description = models.CharField(
        blank=True,
        max_length=LEN_FIELD_DESCRIPTION,
        verbose_name="Description of database-specific ID")
    pt_local_id_number = models.BigIntegerField(
        null=True, blank=True,
        verbose_name="Database-specific ID")
    # Information coming out: patient
    pt_dob = models.DateField(null=True, blank=True,
                              verbose_name="Patient date of birth")
    pt_dod = models.DateField(
        null=True, blank=True,
        verbose_name="Patient date of death (NULL if alive)")
    pt_dead = models.BooleanField(default=False,
                                  verbose_name="Patient is dead")
    pt_discharged = models.NullBooleanField(verbose_name="Patient discharged")
    pt_discharge_date = models.DateField(
        null=True, blank=True,
        verbose_name="Patient date of discharge")
    pt_sex = models.CharField(max_length=1, blank=True, choices=SEX_CHOICES,
                              verbose_name="Patient sex")
    pt_title = models.CharField(max_length=LEN_TITLE, blank=True,
                                verbose_name="Patient title")
    pt_first_name = models.CharField(max_length=LEN_NAME, blank=True,
                                     verbose_name="Patient first name")
    pt_last_name = models.CharField(max_length=LEN_NAME, blank=True,
                                    verbose_name="Patient last name")
    pt_address_1 = models.CharField(
        max_length=LEN_ADDRESS, blank=True,
        verbose_name="Patient address line 1")
    pt_address_2 = models.CharField(
        max_length=LEN_ADDRESS, blank=True,
        verbose_name="Patient address line 2")
    pt_address_3 = models.CharField(
        max_length=LEN_ADDRESS, blank=True,
        verbose_name="Patient address line 3")
    pt_address_4 = models.CharField(
        max_length=LEN_ADDRESS, blank=True,
        verbose_name="Patient address line 4")
    pt_address_5 = models.CharField(
        max_length=LEN_ADDRESS, blank=True,
        verbose_name="Patient address line 5 (county)")
    pt_address_6 = models.CharField(
        max_length=LEN_ADDRESS, blank=True,
        verbose_name="Patient address line 6 (postcode)")
    pt_address_7 = models.CharField(
        max_length=LEN_ADDRESS, blank=True,
        verbose_name="Patient address line 7 (country)")
    pt_telephone = models.CharField(max_length=LEN_PHONE, blank=True,
                                    verbose_name="Patient telephone")
    pt_email = models.EmailField(blank=True, verbose_name="Patient email")

    # Information coming out: GP
    gp_title = models.CharField(max_length=LEN_TITLE, blank=True,
                                verbose_name="GP title")
    gp_first_name = models.CharField(max_length=LEN_NAME, blank=True,
                                     verbose_name="GP first name")
    gp_last_name = models.CharField(max_length=LEN_NAME, blank=True,
                                    verbose_name="GP last name")
    gp_address_1 = models.CharField(
        max_length=LEN_ADDRESS, blank=True,
        verbose_name="GP address line 1")
    gp_address_2 = models.CharField(
        max_length=LEN_ADDRESS, blank=True,
        verbose_name="GP address line 2")
    gp_address_3 = models.CharField(
        max_length=LEN_ADDRESS, blank=True,
        verbose_name="GP address line 3")
    gp_address_4 = models.CharField(
        max_length=LEN_ADDRESS, blank=True,
        verbose_name="GP address line 4")
    gp_address_5 = models.CharField(
        max_length=LEN_ADDRESS, blank=True,
        verbose_name="GP address line 5 (county)")
    gp_address_6 = models.CharField(
        max_length=LEN_ADDRESS, blank=True,
        verbose_name="GP address line 6 (postcode)")
    gp_address_7 = models.CharField(
        max_length=LEN_ADDRESS, blank=True,
        verbose_name="GP address line 7 (country)")
    gp_telephone = models.CharField(max_length=LEN_PHONE, blank=True,
                                    verbose_name="GP telephone")
    gp_email = models.EmailField(blank=True, verbose_name="GP email")

    # Information coming out: clinician
    clinician_title = models.CharField(max_length=LEN_TITLE, blank=True,
                                       verbose_name="Clinician title")
    clinician_first_name = models.CharField(
        max_length=LEN_NAME, blank=True,
        verbose_name="Clinician first name")
    clinician_last_name = models.CharField(
        max_length=LEN_NAME, blank=True,
        verbose_name="Clinician last name")
    clinician_address_1 = models.CharField(
        max_length=LEN_ADDRESS, blank=True,
        verbose_name="Clinician address line 1")
    clinician_address_2 = models.CharField(
        max_length=LEN_ADDRESS, blank=True,
        verbose_name="Clinician address line 2")
    clinician_address_3 = models.CharField(
        max_length=LEN_ADDRESS, blank=True,
        verbose_name="Clinician address line 3")
    clinician_address_4 = models.CharField(
        max_length=LEN_ADDRESS, blank=True,
        verbose_name="Clinician address line 4")
    clinician_address_5 = models.CharField(
        max_length=LEN_ADDRESS, blank=True,
        verbose_name="Clinician address line 5 (county)")
    clinician_address_6 = models.CharField(
        max_length=LEN_ADDRESS, blank=True,
        verbose_name="Clinician address line 6 (postcode)")
    clinician_address_7 = models.CharField(
        max_length=LEN_ADDRESS, blank=True,
        verbose_name="Clinician address line 7 (country)")
    clinician_telephone = models.CharField(max_length=LEN_PHONE, blank=True,
                                           verbose_name="Clinician telephone")
    clinician_email = models.EmailField(blank=True,
                                        verbose_name="Clinician email")
    clinician_is_consultant = models.BooleanField(
        default=False,
        verbose_name="Clinician is a consultant")
    clinician_signatory_title = models.CharField(
        max_length=LEN_NAME, blank=True,
        verbose_name="Clinician's title for signature "
                     "(e.g. 'Consultant psychiatrist')")

    class Meta:
        abstract = True

    # Generic title stuff:

    # -------------------------------------------------------------------------
    # Patient
    # -------------------------------------------------------------------------

    def pt_salutation(self) -> str:
        # noinspection PyTypeChecker
        return salutation(self.pt_title, self.pt_first_name, self.pt_last_name,
                          sex=self.pt_sex)

    def pt_title_forename_surname(self) -> str:
        # noinspection PyTypeChecker
        return title_forename_surname(self.pt_title, self.pt_first_name,
                                      self.pt_last_name)

    def pt_forename_surname(self) -> str:
        # noinspection PyTypeChecker
        return forename_surname(self.pt_first_name, self.pt_last_name)

    def pt_address_components(self) -> List[str]:
        return list(filter(None, [
            self.pt_address_1,
            self.pt_address_2,
            self.pt_address_3,
            self.pt_address_4,
            self.pt_address_5,
            self.pt_address_6,
            self.pt_address_7,
        ]))

    def pt_address_components_str(self) -> str:
        return ", ".join(filter(None, self.pt_address_components()))

    def pt_name_address_components(self) -> List[str]:
        return [
            self.pt_title_forename_surname()
        ] + self.pt_address_components()

    def get_id_numbers_html_bold(self) -> str:
        idnums = ["NHS#: {}".format(self.nhs_number)]
        if self.pt_local_id_description:
            idnums.append("{}: {}".format(self.pt_local_id_description,
                                          self.pt_local_id_number))
        return ". ".join(idnums)

    def get_pt_age_years(self) -> Optional[int]:
        if self.pt_dob is None:
            return None
        now = datetime.datetime.now()  # timezone-naive
        # now = timezone.now()  # timezone-aware
        return relativedelta(now, self.pt_dob).years

    def is_under_16(self) -> bool:
        age = self.get_pt_age_years()
        return age is not None and age < 16

    def is_under_15(self) -> bool:
        age = self.get_pt_age_years()
        return age is not None and age < 15

    def days_since_discharge(self) -> Optional[int]:
        """
        Returns days since discharge, or None if the patient is not
        discharged (or unknown).
        """
        if not self.pt_discharged or not self.pt_discharge_date:
            return None
        try:
            today = datetime.date.today()
            discharged = self.pt_discharge_date  # type: datetime.date
            diff = today - discharged
            return diff.days
        except (AttributeError, TypeError, ValueError):
            return None

    # @property
    # def nhs_number(self) -> int:
    #     raise NotImplementedError()
    #
    # ... NO; do not do this; it makes nhs_number a read-only attribute, so
    # derived class creation fails with
    #
    #   AttributeError: can't set attribute
    #
    # when trying to write nhs_number

    # -------------------------------------------------------------------------
    # GP
    # -------------------------------------------------------------------------

    def gp_title_forename_surname(self) -> str:
        return title_forename_surname(self.gp_title, self.gp_first_name,
                                      self.gp_last_name, always_title=True,
                                      assume_dr=True)

    def gp_address_components(self) -> List[str]:
        return list(filter(None, [
            self.gp_address_1,
            self.gp_address_2,
            self.gp_address_3,
            self.gp_address_4,
            self.gp_address_5,
            self.gp_address_6,
            self.gp_address_7,
        ]))

    def gp_address_components_str(self) -> str:
        return ", ".join(self.gp_address_components())

    def gp_name_address_str(self) -> str:
        return ", ".join(filter(None, [self.gp_title_forename_surname(),
                                       self.gp_address_components_str()]))

    # noinspection PyUnusedLocal
    def set_gp_name_components(self,
                               name: str,
                               decisions: List[str],
                               secret_decisions: List[str]) -> None:
        """
        Takes name, and stores it in the gp_title, gp_first_name, and
        gp_last_name fields.
        """
        secret_decisions.append(
            "Setting GP name components from: {}.".format(name))
        self.gp_title = ''
        self.gp_first_name = ''
        self.gp_last_name = ''
        if name == "No Registered GP" or not name:
            self.gp_last_name = "[No registered GP]"
            return
        if "(" in name:
            # A very odd thing like "LINTON H C (PL)"
            self.gp_last_name = name
            return
        (initial, surname) = get_initial_surname_tuple_from_string(name)
        initial = initial.title()
        surname = surname.title()
        self.gp_title = "Dr"
        self.gp_first_name = initial + ("." if initial else "")
        self.gp_last_name = surname

    # -------------------------------------------------------------------------
    # Clinician
    # -------------------------------------------------------------------------

    def clinician_salutation(self) -> str:
        # noinspection PyTypeChecker
        return salutation(self.clinician_title, self.clinician_first_name,
                          self.clinician_last_name, assume_dr=True)

    def clinician_title_forename_surname(self) -> str:
        # noinspection PyTypeChecker
        return title_forename_surname(self.clinician_title,
                                      self.clinician_first_name,
                                      self.clinician_last_name)

    def clinician_address_components(self) -> List[str]:
        # We're going to put the clinician's postal address into letters to
        # patients. Therefore, we need a sensible fallback, i.e. the RDBM's.
        address_components = [
            self.clinician_address_1,
            self.clinician_address_2,
            self.clinician_address_3,
            self.clinician_address_4,
            self.clinician_address_5,
            self.clinician_address_6,
            self.clinician_address_7,
        ]
        if not any(x for x in address_components):
            address_components = settings.RDBM_ADDRESS.copy()
            if address_components:
                address_components[0] = "c/o " + address_components[0]
        return list(filter(None, address_components))

    def clinician_address_components_str(self) -> str:
        return ", ".join(self.clinician_address_components())

    def clinician_name_address_str(self) -> str:
        return ", ".join(filter(None, [
            self.clinician_title_forename_surname(),
            self.clinician_address_components_str()]))

    # -------------------------------------------------------------------------
    # Paperwork
    # -------------------------------------------------------------------------

    def get_traffic_light_decision_form(self) -> str:
        context = {
            'patient_lookup': self,
            'settings': settings,
        }
        return render_pdf_html_to_string(
            'traffic_light_decision_form.html', context, patient=True)


class DummyPatientSourceInfo(PatientLookupBase):
    # Key
    nhs_number = models.BigIntegerField(verbose_name="NHS number",
                                        unique=True)

    class Meta:
        verbose_name_plural = "Dummy patient source information"

    def __str__(self):
        return (
            "[DummyPatientSourceInfo {}] "
            "Dummy patient lookup for NHS# {}".format(
                self.id,
                self.nhs_number))


class PatientLookup(PatientLookupBase):
    """
    Represents a moment of lookup up identifiable data about patient, GP,
    and clinician from the relevant clinical database.

    Inherits from PatientLookupBase so it has the same fields, and more.
    """

    nhs_number = models.BigIntegerField(
        verbose_name="NHS number used for lookup")
    lookup_at = models.DateTimeField(
        verbose_name="When fetched from clinical database",
        auto_now_add=True)

    # Information going in
    source_db = models.CharField(
        max_length=SOURCE_DB_NAME_MAX_LENGTH,
        choices=ClinicalDatabaseType.DATABASE_CHOICES,
        verbose_name="Source database used for lookup")

    # Information coming out: general
    decisions = models.TextField(
        blank=True, verbose_name="Decisions made during lookup")
    secret_decisions = models.TextField(
        blank=True,
        verbose_name="Secret (identifying) decisions made during lookup")

    # Information coming out: patient
    pt_found = models.BooleanField(default=False, verbose_name="Patient found")

    # Information coming out: GP
    gp_found = models.BooleanField(default=False, verbose_name="GP found")

    # Information coming out: clinician
    clinician_found = models.BooleanField(default=False,
                                          verbose_name="Clinician found")

    def __repr__(self):
        return modelrepr(self)

    def __str__(self):
        return "[PatientLookup {}] NHS# {}".format(
            self.id,
            self.nhs_number,
        )

    def get_first_traffic_light_letter_html(self) -> str:
        """
        REC DOCUMENT 06. Covering letter to patient for first enquiry about
        research preference
        """
        context = {
            # Letter bits
            'address_from': self.clinician_address_components(),
            'address_to': self.pt_name_address_components(),
            'salutation': self.pt_salutation(),
            'signatory_name': self.clinician_title_forename_surname(),
            'signatory_title': self.clinician_signatory_title,
            # Specific bits
            'settings': settings,
            'patient_lookup': self,
        }
        return render_pdf_html_to_string(
            'letter_patient_first_traffic_light.html', context, patient=True)

    def set_from_clinician_info_holder(
            self, info: ClinicianInfoHolder) -> None:
        self.clinician_found = True
        self.clinician_title = info.title
        self.clinician_first_name = info.first_name
        self.clinician_last_name = info.surname
        self.clinician_email = info.email
        self.clinician_is_consultant = info.is_consultant
        self.clinician_signatory_title = info.signatory_title
        # Slice notation returns an empty list, rather than an exception,
        # if the index is out of range
        self.clinician_address_1 = info.address_components[0:1] or ''
        self.clinician_address_2 = info.address_components[1:2] or ''
        self.clinician_address_3 = info.address_components[2:3] or ''
        self.clinician_address_4 = info.address_components[3:4] or ''
        self.clinician_address_5 = info.address_components[4:5] or ''
        self.clinician_address_6 = info.address_components[5:6] or ''
        self.clinician_address_7 = info.address_components[6:7] or ''


# =============================================================================
# Clinical team representative
# =============================================================================

class TeamInfo(object):
    """Class only exists to be able to use @cached_property."""
    @cached_property
    def teams(self) -> List[str]:
        log.debug("Fetching/caching clinical teams")
        return get_teams()

    @cached_property
    def team_choices(self) -> List[Tuple[str, str]]:
        teams = self.teams
        return [(team, team) for team in teams]


all_teams_info = TeamInfo()


class TeamRep(models.Model):
    """
    Clinical team representatives are recorded in CRATE.
    """
    team = models.CharField(max_length=LEN_NAME, unique=True,
                            choices=all_teams_info.team_choices,
                            verbose_name="Team description")
    user = models.ForeignKey(settings.AUTH_USER_MODEL)

    class Meta:
        verbose_name = "clinical team representative"
        verbose_name_plural = "clinical team representatives"


# =============================================================================
# Record of payments to charity
# =============================================================================
# In passing - singleton objects:
#   http://goodcode.io/articles/django-singleton-models/

class CharityPaymentRecord(models.Model):
    created_at = models.DateTimeField(verbose_name="When created",
                                      auto_now_add=True)
    payee = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=8, decimal_places=2)


# =============================================================================
# Record of consent mode for a patient
# =============================================================================

class ConsentMode(Decision):
    RED = 'red'
    YELLOW = 'yellow'
    GREEN = 'green'

    VALID_CONSENT_MODES = [RED, YELLOW, GREEN]
    CONSENT_MODE_CHOICES = (
        (RED, 'red'),
        (YELLOW, 'yellow'),
        (GREEN, 'green'),
    )
    # ... http://stackoverflow.com/questions/12822847/best-practice-for-python-django-constants  # noqa

    SOURCE_USER_ENTRY = "crate_user_entry"
    SOURCE_AUTOCREATED = "crate_auto_created"
    SOURCE_LEGACY = "legacy"  # default, for old versions

    nhs_number = models.BigIntegerField(verbose_name="NHS number")
    current = models.BooleanField(default=False)
    # see save() and process_change() below
    created_at = models.DateTimeField(
        verbose_name="When was this record created?",
        auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL)

    exclude_entirely = models.BooleanField(
        default=False,
        verbose_name="Exclude patient from Research Database entirely?")
    consent_mode = models.CharField(
        max_length=10, default="", choices=CONSENT_MODE_CHOICES,
        verbose_name="Consent mode (red/yellow/green)")
    consent_after_discharge = models.BooleanField(
        default=False,
        verbose_name="Consent given to contact patient after discharge?")
    max_approaches_per_year = models.PositiveSmallIntegerField(
        verbose_name="Maximum number of approaches permissible per year "
                     "(0 = no limit)",
        default=0)
    other_requests = models.TextField(
        blank=True,
        verbose_name="Other special requests by patient")
    prefers_email = models.BooleanField(
        default=False,
        verbose_name="Patient prefers e-mail contact?")
    changed_by_clinician_override = models.BooleanField(
        default=False,
        verbose_name="Consent mode changed by clinician's override?")

    source = models.CharField(
        max_length=SOURCE_DB_NAME_MAX_LENGTH,
        default=SOURCE_USER_ENTRY,
        verbose_name="Source of information")

    # class Meta:
    #     get_latest_by = "created_at"

    def save(self, *args, **kwargs) -> None:
        """
        Custom save method.
        Ensures that only one ConsentMode has current == True for a given
        patient.

        Better than a get_latest_by clause, because with a flag like this, we
        can have a simple query that says "get the current records for all
        patients" -- harder if done by date (group by patient, order by
        patient/date, pick last one for each patient...).
        """
        # http://stackoverflow.com/questions/1455126/unique-booleanfield-value-in-django  # noqa
        if self.current:
            ConsentMode.objects\
                       .filter(nhs_number=self.nhs_number, current=True)\
                       .update(current=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return "[ConsentMode {}] NHS# {}, {}".format(
            self.id,
            self.nhs_number,
            self.consent_mode,
        )

    @classmethod
    def get_or_create(
            cls,
            nhs_number: int,
            created_by: settings.AUTH_USER_MODEL) -> CONSENT_MODE_FWD_REF:
        """
        Fetches the current ConsentMode for this patient.
        If there isn't one, creates a default one and returns that.
        """
        try:
            consent_mode = cls.objects.get(nhs_number=nhs_number,
                                           current=True)
        except cls.DoesNotExist:
            consent_mode = cls(nhs_number=nhs_number,
                               created_by=created_by,
                               source=cls.SOURCE_AUTOCREATED,
                               current=True)
            consent_mode.save()
        except cls.MultipleObjectsReturned:
            log.warning("bug: ConsentMode.get_or_create() received "
                        "exception ConsentMode.MultipleObjectsReturned")
            consent_mode = cls(nhs_number=nhs_number,
                               created_by=created_by,
                               source=cls.SOURCE_AUTOCREATED,
                               current=True)
            consent_mode.save()
        return consent_mode

    @classmethod
    def get_or_none(cls,
                    nhs_number: int) -> Optional[CONSENT_MODE_FWD_REF]:
        """
        Fetches the current ConsentMode for this patient.
        If there isn't one, returns None
        """
        try:
            return cls.objects.get(nhs_number=nhs_number, current=True)
        except cls.DoesNotExist:
            return None

    @classmethod
    def refresh_from_primary_clinical_record(
            cls,
            nhs_number: int,
            created_by: settings.AUTH_USER_MODEL,
            source_db: str = None) -> List[str]:
        """
        Checks the primary clinical record and CRATE's own records for consent
        modes for this patient. If the most recent one is in the external
        database, copies it to CRATE's database and marks that one as current.

        This has the effect that external primary clinical records (e.g. RiO)
        take priority, but if there's no record in RiO, we can still proceed.

        Returns a list of human-readable decisions.

        Internally, we do this:
        - Fetch the most recent record.
        - If its date is later than the most recent CRATE record:
          - create a new ConsentMode with (..., source=source_db)
          - save it

        *** also: use celery beat to refresh regularly +/- trigger withdrawal
            of consent if consent mode changed;
            http://docs.celeryproject.org/en/latest/userguide/periodic-tasks.html
        *** also make automatic opt-out list

        """
        from crate_anon.crateweb.consent.lookup import lookup_consent  # delayed import  # noqa

        decisions = []  # type: List[str]
        source_db = source_db or settings.CLINICAL_LOOKUP_CONSENT_DB
        decisions.append("source_db = {}".format(source_db))

        latest = lookup_consent(
            nhs_number=nhs_number,
            source_db=source_db,
            decisions=decisions
        )
        if latest is None:
            decisions.append("No consent decision found in primary clinical "
                             "record")
            return decisions

        crate_version = cls.get_or_none(nhs_number=nhs_number)

        if crate_version and crate_version.created_at >= latest.created_at:
            decisions.append(
                "CRATE stored version is at least as recent ({}) as the "
                "version from the clinical record ({}); ignoring".format(
                    crate_version.created_at,
                    latest.created_at
                ))
            return decisions

        # If we get here, we've found a newer version in the clinical record.
        latest.created_by = created_by
        latest.source = source_db
        latest.current = True
        latest.save()  # This now becomes the current CRATE consent mode.
        return decisions

    def consider_withdrawal(self) -> None:
        """
        If required, withdraw consent for other studies.
        Call this before setting current=True and calling save().
        Note that as per Major Amendment 1 to 12/EE/0407, this happens
        automatically, rather than having a special flag to control it.
        """
        try:
            previous = ConsentMode.objects.get(
                nhs_number=self.nhs_number,
                current=True)
            if (previous.consent_mode == ConsentMode.GREEN and
                    self.consent_mode != ConsentMode.GREEN):
                contact_requests = (
                    ContactRequest.objects
                    .filter(nhs_number=self.nhs_number)
                    .filter(consent_mode__consent_mode=ConsentMode.GREEN)
                    .filter(decided_send_to_researcher=True)
                    .filter(consent_withdrawn=False)
                )
                for contact_request in contact_requests:
                    (letter,
                     email_succeeded) = contact_request.withdraw_consent()
                    if not email_succeeded:
                        self.notify_rdbm_of_work(letter, to_researcher=True)
        except ConsentMode.DoesNotExist:
            pass  # no previous ConsentMode; nothing to do.
        except ConsentMode.MultipleObjectsReturned:
            log.warning("bug: ConsentMode.consider_withdrawal() received "
                        "exception ConsentMode.MultipleObjectsReturned")
            # do nothing else

    def get_latest_patient_lookup(self) -> PatientLookup:
        from crate_anon.crateweb.consent.lookup import lookup_patient  # delayed import  # noqa
        # noinspection PyTypeChecker
        return lookup_patient(self.nhs_number, existing_ok=True)

    def get_confirm_traffic_to_patient_letter_html(self) -> str:
        """
        REC DOCUMENT 07. Confirming patient's traffic-light choice.
        """
        patient_lookup = self.get_latest_patient_lookup()
        context = {
            # Letter bits
            'address_from': settings.RDBM_ADDRESS + [settings.RDBM_EMAIL],
            'address_to': patient_lookup.pt_name_address_components(),
            'salutation': patient_lookup.pt_salutation(),
            'signatory_name': settings.RDBM_NAME,
            'signatory_title': settings.RDBM_TITLE,
            # Specific bits
            'consent_mode': self,
            'patient_lookup': patient_lookup,
            'settings': settings,
            # URLs
            # 'red_img_url': site_absolute_url(static('red.png')),
            # 'yellow_img_url': site_absolute_url(static('yellow.png')),
            # 'green_img_url': site_absolute_url(static('green.png')),
        }
        # 1. Building a static URL in code:
        #    http://stackoverflow.com/questions/11721818/django-get-the-static-files-url-in-view  # noqa
        # 2. Making it an absolute URL means that wkhtmltopdf will also see it
        #    (by fetching it from this web server).
        # 3. Works with Django testing server.
        # 4. Works with Apache, + proxying to backend, + SSL
        return render_pdf_html_to_string('letter_patient_confirm_traffic.html',
                                         context, patient=True)

    def notify_rdbm_of_work(self,
                            letter: LETTER_FWD_REF,
                            to_researcher: bool = False) -> None:
        subject = ("WORK FROM RESEARCH DATABASE COMPUTER"
                   " - consent mode {}".format(self.id))
        if to_researcher:
            template = 'email_rdbm_new_work_researcher.html'
        else:
            template = 'email_rdbm_new_work_pt_from_rdbm.html'
        html = render_email_html_to_string(template, {'letter': letter})
        email = Email.create_rdbm_email(subject, html)
        email.send()

    def process_change(self) -> None:
        """
        Called upon saving.
        Will create a letter to patient.
        May create a withdrawal-of-consent letter to researcher.
        -- Major Amendment 1 (Oct 2014) to 12/EE/0407: always withdraw consent
           and tell researchers, i.e. "active cancellation" of ongoing
           permission, where the researchers have not yet made contact.
        """
        # noinspection PyTypeChecker
        letter = Letter.create_consent_confirmation_to_patient(self)
        # ... will save
        self.notify_rdbm_of_work(letter, to_researcher=False)
        self.consider_withdrawal()
        self.current = True  # will disable current flag for others
        self.save()


# =============================================================================
# Request for patient contact
# =============================================================================

class ContactRequest(models.Model):
    CLINICIAN_INVOLVEMENT_NONE = 0
    CLINICIAN_INVOLVEMENT_REQUESTED = 1
    CLINICIAN_INVOLVEMENT_REQUIRED_YELLOW = 2
    CLINICIAN_INVOLVEMENT_REQUIRED_UNKNOWN = 3

    CLINICIAN_CONTACT_MODE_CHOICES = (
        (CLINICIAN_INVOLVEMENT_NONE,
         'No clinician involvement required or requested'),
        (CLINICIAN_INVOLVEMENT_REQUESTED,
         'Clinician involvement requested by researchers'),
        (CLINICIAN_INVOLVEMENT_REQUIRED_YELLOW,
         'Clinician involvement required by YELLOW consent mode'),
        (CLINICIAN_INVOLVEMENT_REQUIRED_UNKNOWN,
         'Clinician involvement required by UNKNOWN consent mode'),
    )

    # Created initially:
    created_at = models.DateTimeField(verbose_name="When created",
                                      auto_now_add=True)
    request_by = models.ForeignKey(settings.AUTH_USER_MODEL)
    study = models.ForeignKey(Study)  # type: Study
    request_direct_approach = models.BooleanField(
        verbose_name="Request direct contact with patient if available"
                     " (not contact with clinician first)")
    # One of these will be non-NULL
    lookup_nhs_number = models.BigIntegerField(
        null=True,
        verbose_name="NHS number used for lookup")
    lookup_rid = models.CharField(
        max_length=MAX_HASH_LENGTH, null=True,
        verbose_name="Research ID used for lookup")
    lookup_mrid = models.CharField(
        max_length=MAX_HASH_LENGTH, null=True,
        verbose_name="Master research ID used for lookup")

    processed = models.BooleanField(default=False)
    # Below: created during processing.

    # Those numbers translate to this:
    nhs_number = models.BigIntegerField(null=True, verbose_name="NHS number")
    # ... from which:
    patient_lookup = models.ForeignKey(PatientLookup, null=True)
    consent_mode = models.ForeignKey(ConsentMode, null=True)
    # Now decisions:
    approaches_in_past_year = models.PositiveIntegerField(null=True)
    decisions = models.TextField(
        blank=True, verbose_name="Decisions made")
    decided_no_action = models.BooleanField(default=False)
    decided_send_to_researcher = models.BooleanField(default=False)
    decided_send_to_clinician = models.BooleanField(default=False)
    clinician_involvement = models.PositiveSmallIntegerField(
        choices=CLINICIAN_CONTACT_MODE_CHOICES,
        null=True)
    consent_withdrawn = models.BooleanField(default=False)
    consent_withdrawn_at = models.DateTimeField(
        verbose_name="When consent withdrawn", null=True)

    def __str__(self):
        return "[ContactRequest {}] Study {}".format(
            self.id,
            self.study_id,
        )

    @classmethod
    def create(cls,
               request: HttpRequest,
               study: Study,
               request_direct_approach: bool,
               lookup_nhs_number: int = None,
               lookup_rid: str = None,
               lookup_mrid: str = None) -> CONTACT_REQUEST_FWD_REF:
        """Create a contact request and act on it."""
        # https://docs.djangoproject.com/en/1.9/ref/request-response/
        # noinspection PyTypeChecker
        cr = cls(request_by=request.user,
                 study=study,
                 request_direct_approach=request_direct_approach,
                 lookup_nhs_number=lookup_nhs_number,
                 lookup_rid=lookup_rid,
                 lookup_mrid=lookup_mrid)
        cr.save()
        transaction.on_commit(
            lambda: process_contact_request.delay(cr.id)
        )  # Asynchronous
        return cr

    def process_request(self) -> None:
        self.decisionlist = []
        self.process_request_main()
        self.decisions = " ".join(self.decisionlist)
        self.processed = True
        self.save()

    def process_request_main(self) -> None:
        """
        =======================================================================
        Act on a contact request and store the decisions made.
        CORE DECISION-MAKING FUNCTION FOR THE CONSENT-TO-CONTACT PROCESS.
        =======================================================================
        The decisions parameter is a list that's appended to.
        """
        from crate_anon.crateweb.consent.lookup import lookup_patient  # delayed import  # noqa

        # Translate to an NHS number
        dbinfo = research_database_info.dbinfo_for_contact_lookup
        if self.lookup_nhs_number is not None:
            self.nhs_number = self.lookup_nhs_number
        elif self.lookup_rid is not None:
            self.nhs_number = get_mpid(dbinfo=dbinfo,
                                       rid=self.lookup_rid)
        elif self.lookup_mrid is not None:
            self.nhs_number = get_mpid(dbinfo=dbinfo,
                                       mrid=self.lookup_mrid)
        else:
            raise ValueError("No NHS number, RID, or MRID supplied.")
        # Look up patient details (afresh)
        self.patient_lookup = lookup_patient(self.nhs_number, save=True)
        # Establish consent mode (always do this to avoid NULL problem)
        ConsentMode.refresh_from_primary_clinical_record(
            nhs_number=self.nhs_number,
            created_by=self.request_by)
        self.consent_mode = ConsentMode.get_or_create(
            nhs_number=self.nhs_number,
            created_by=self.request_by)
        # Rest of processing
        self.calc_approaches_in_past_year()

        # ---------------------------------------------------------------------
        # Main decision process
        # ---------------------------------------------------------------------

        # Simple failures
        if not self.patient_lookup.pt_found:
            self.stop("no patient found")
            return
        if self.consent_mode.exclude_entirely:
            self.stop(
                "patient has exclude_entirely flag set; "
                " POTENTIALLY SERIOUS ERROR in that this patient shouldn't"
                " have been in the anonymised database.")
            return
        if self.patient_lookup.pt_dead:
            self.stop("patient is dead")
            return
        if self.consent_mode.consent_mode == ConsentMode.RED:
            self.stop("patient's consent mode is RED")
            return

        # Age?
        if self.patient_lookup.pt_dob is None:
            self.stop("patient DOB unknown")
            return
        if (not self.study.include_under_16s and
                self.patient_lookup.is_under_16()):
            self.stop("patient is under 16 and study not approved for that")
            return

        # Discharged/outside discharge criteria?
        if self.patient_lookup.pt_discharged:
            if not self.study.include_discharged:
                self.stop(
                    "patient is discharged and study not approved for that")
                return
            # if self.consent_mode.consent_mode not in (ConsentMode.GREEN,
            #                                           ConsentMode.YELLOW):
            #     self.stop("patient is discharged and consent mode is not "
            #               "GREEN or YELLOW")
            #     return
            days_since_discharge = self.patient_lookup.days_since_discharge()
            permitted_n_days = settings.PERMITTED_TO_CONTACT_DISCHARGED_PATIENTS_FOR_N_DAYS  # noqa
            if not self.consent_mode.consent_after_discharge:
                if days_since_discharge is None:
                    self.stop("patient is discharged; patient did not consent "
                              "to contact after discharge; unable to "
                              "determine days since discharge")
                    return
                if days_since_discharge > permitted_n_days:
                    self.stop(
                        "patient was discharged {} days ago; "
                        "permission exists only for up to {} days; "
                        "patient did not consent to contact after "
                        "discharge".format(
                            days_since_discharge,
                            permitted_n_days,
                        ))
                    return

        # Maximum number of approaches exceeded?
        if self.consent_mode.max_approaches_per_year > 0:
            if (self.approaches_in_past_year >=
                    self.consent_mode.max_approaches_per_year):
                self.stop(
                    "patient has had {} approaches in the past year and has "
                    "set a cap of {} per year".format(
                        self.approaches_in_past_year,
                        self.consent_mode.max_approaches_per_year,
                    )
                )
                return

        # ---------------------------------------------------------------------
        # OK. If we get here, we're going to try to contact someone!
        # ---------------------------------------------------------------------

        # Direct?
        self.save()  # makes self.id, needed for FKs
        if (self.consent_mode.consent_mode == ConsentMode.GREEN and
                self.request_direct_approach):
            # noinspection PyTypeChecker
            letter = Letter.create_researcher_approval(self)  # will save
            self.decided_send_to_researcher = True
            self.clinician_involvement = (
                ContactRequest.CLINICIAN_INVOLVEMENT_NONE)
            self.decide("GREEN: Researchers prefer direct approach and patient"
                        " has chosen green mode: send approval to researcher.")
            researcher_emailaddr = self.study.lead_researcher.email
            try:
                validate_email(researcher_emailaddr)
                # noinspection PyTypeChecker
                email = Email.create_researcher_approval_email(self, letter)
                emailtransmission = email.send()
                if emailtransmission.sent:
                    self.decide("Sent approval to researcher at {}".format(
                        researcher_emailaddr))
                    return
                self.decide(
                    "Failed to e-mail approval to researcher at {}.".format(
                        researcher_emailaddr))
                # noinspection PyTypeChecker
                self.decide(emailtransmission.failure_reason)
            except ValidationError:
                pass
            self.decide("Approval letter to researcher created and needs "
                        "printing")
            self.notify_rdbm_of_work(letter, to_researcher=True)
            return

        # All other routes are via clinician.

        # noinspection PyTypeChecker
        self.clinician_involvement = self.get_clinician_involvement(
            consent_mode_str=self.consent_mode.consent_mode,
            request_direct_approach=self.request_direct_approach)

        # Do we have a clinician?
        if not self.patient_lookup.clinician_found:
            self.stop("don't know clinician; can't proceed")
            return
        clinician_emailaddr = self.patient_lookup.clinician_email
        try:
            validate_email(clinician_emailaddr)
        except ValidationError:
            self.stop("clinician e-mail ({}) is invalid".format(
                clinician_emailaddr))
            return
        try:
            # noinspection PyTypeChecker
            validate_researcher_email_domain(clinician_emailaddr)
        except ValidationError:
            self.stop(
                "clinician e-mail ({}) is not in a permitted domain".format(
                    clinician_emailaddr))
            return

        # Warnings
        if (ContactRequest.objects
                .filter(nhs_number=self.nhs_number)
                .filter(study=self.study)
                .filter(decided_send_to_clinician=True)
                .filter(clinician_response__responded=False)
                .exists()):
            self.decide("WARNING: outstanding request to clinician for same "
                        "patient/study.")
        if (ContactRequest.objects
                .filter(nhs_number=self.nhs_number)
                .filter(study=self.study)
                .filter(decided_send_to_clinician=True)
                .filter(clinician_response__responded=True)
                .filter(clinician_response__response__in=[
                    ClinicianResponse.RESPONSE_B,
                    ClinicianResponse.RESPONSE_C,
                    ClinicianResponse.RESPONSE_D,
                ])
                .exists()):
            self.decide("WARNING: clinician has already rejected a request "
                        "about this patient/study.")

        # Send e-mail to clinician
        # noinspection PyTypeChecker
        email = Email.create_clinician_email(self)
        # ... will also create a ClinicianResponse
        emailtransmission = email.send()
        if not emailtransmission.sent:
            # noinspection PyTypeChecker
            self.decide(emailtransmission.failure_reason)
            self.stop("Failed to send e-mail to clinician at {}".format(
                clinician_emailaddr))
            # We don't set decided_send_to_clinician because this attempt has
            # failed, and we don't want to put anyone off trying again
            # immediately.
        self.decided_send_to_clinician = True
        self.decide(
            "Sent request to clinician at {}".format(clinician_emailaddr))

    @staticmethod
    def get_clinician_involvement(consent_mode_str: str,
                                  request_direct_approach: bool) -> int:
        # Let's be precise about why the clinician is involved.
        if not request_direct_approach:
            return ContactRequest.CLINICIAN_INVOLVEMENT_REQUESTED
        elif consent_mode_str == ConsentMode.YELLOW:
            return ContactRequest.CLINICIAN_INVOLVEMENT_REQUIRED_YELLOW
        else:
            # Only other possibility
            return ContactRequest.CLINICIAN_INVOLVEMENT_REQUIRED_UNKNOWN

    def decide(self, msg: str) -> None:
        self.decisionlist.append(msg)

    def stop(self, msg: str) -> None:
        self.decide("Stopping: " + msg)
        self.decided_no_action = True

    def calc_approaches_in_past_year(self) -> None:
        # How best to count this?
        # Not by e.g. calendar year, with a flag that gets reset to zero
        # annually, because you might have a limit of 5, and get 4 requests in
        # Dec 2020 and then another 4 in Jan 2021 just after the flag resets.
        # Instead, we count the number of requests to that patient in the past
        # year.
        one_year_ago = timezone.now() - datetime.timedelta(days=365)

        self.approaches_in_past_year = ContactRequest.objects.filter(
            Q(decided_send_to_researcher=True) |
            (Q(decided_send_to_clinician=True) &
                (Q(clinician_response__response=ClinicianResponse.RESPONSE_A) |
                 Q(clinician_response__response=ClinicianResponse.RESPONSE_R))),  # noqa
            nhs_number=self.nhs_number,
            created_at__gte=one_year_ago
        ).count()

    def withdraw_consent(self) -> Tuple[LETTER_FWD_REF, bool]:
        self.consent_withdrawn = True
        self.consent_withdrawn_at = timezone.now()
        self.save()
        # noinspection PyTypeChecker
        letter = Letter.create_researcher_withdrawal(self)  # will save
        researcher_emailaddr = self.study.lead_researcher.email
        email_succeeded = False
        try:
            validate_email(researcher_emailaddr)
            # noinspection PyTypeChecker
            email = Email.create_researcher_withdrawal_email(self, letter)
            emailtransmission = email.send()
            email_succeeded = emailtransmission.sent
        except ValidationError:
            pass
        return letter, email_succeeded

    def get_permission_date(self) -> Optional[datetime.datetime]:
        """When was the researcher given permission? Used for the letter
        withdrawing permission."""
        if self.decided_no_action:
            return None
        if self.decided_send_to_researcher:
            # Green route
            # noinspection PyTypeChecker
            return self.created_at
        if self.decided_send_to_clinician:
            # Yellow route -> patient -> said yes
            if hasattr(self, 'patient_response'):
                if self.patient_response.response == PatientResponse.YES:
                    return self.patient_response.created_at
        return None

    def notify_rdbm_of_work(self,
                            letter: LETTER_FWD_REF,
                            to_researcher: bool = False) -> None:
        subject = ("CHEERFUL WORK FROM RESEARCH DATABASE COMPUTER"
                   " - contact request {}".format(self.id))
        if to_researcher:
            template = 'email_rdbm_new_work_researcher.html'
        else:
            template = 'email_rdbm_new_work_pt_from_clinician.html'
        html = render_email_html_to_string(template, {'letter': letter})
        email = Email.create_rdbm_email(subject, html)
        email.send()

    def notify_rdbm_of_bad_progress(self) -> None:
        subject = ("INFO ONLY - clinician refused Research Database request"
                   " - contact request {}".format(self.id))
        html = render_email_html_to_string('email_rdbm_bad_progress.html', {
            'id': self.id,
            'response': self.clinician_response.response,
            'explanation': self.clinician_response.get_response_explanation(),
        })
        email = Email.create_rdbm_email(subject, html)
        email.send()

    def notify_rdbm_of_good_progress(self) -> None:
        subject = ("INFO ONLY - clinician agreed to Research Database request"
                   " - contact request {}".format(self.id))
        html = render_email_html_to_string('email_rdbm_good_progress.html', {
            'id': self.id,
            'response': self.clinician_response.response,
            'explanation': self.clinician_response.get_response_explanation(),
        })
        email = Email.create_rdbm_email(subject, html)
        email.send()

    def get_clinician_email_html(self, save: bool = True) -> str:
        """
        REC DOCUMENTS 09, 11, 13 (A): E-mail to clinician
        E-mail to clinician asking them to pass on contact request.

        URL method (path, querystring, both?): see notes in core/utils.py

        In this case, decision: since we are creating a ClinicianResponse, we
        should use its ModelForm.
            - URL path for PK
            - querystring for other parameters, with form-based validation
        """
        clinician_response = ClinicianResponse.create(self, save=save)
        if not save:
            clinician_response.id = -1  # dummy PK, guaranteed to fail
        context = {
            'contact_request': self,
            'study': self.study,
            'patient_lookup': self.patient_lookup,
            'consent_mode': self.consent_mode,
            'settings': settings,
            'url_yes': clinician_response.get_abs_url_yes(),
            'url_no': clinician_response.get_abs_url_no(),
            'url_maybe': clinician_response.get_abs_url_maybe(),
            'permitted_to_contact_discharged_patients_for_n_days':
                settings.PERMITTED_TO_CONTACT_DISCHARGED_PATIENTS_FOR_N_DAYS,
            'permitted_to_contact_discharged_patients_for_n_years':
                days_to_years(
                    settings.PERMITTED_TO_CONTACT_DISCHARGED_PATIENTS_FOR_N_DAYS),  # noqa
        }
        return render_email_html_to_string('email_clinician.html', context)

    def get_approval_letter_html(self) -> str:
        """
        REC DOCUMENT 15.
        Letter to researcher approving contact.
        """
        context = {
            # Letter bits
            'address_from': (
                settings.RDBM_ADDRESS +
                [settings.RDBM_TELEPHONE, settings.RDBM_EMAIL]
            ),
            'address_to': self.study.get_lead_researcher_name_address(),
            'salutation': self.study.get_lead_researcher_salutation(),
            'signatory_name': settings.RDBM_NAME,
            'signatory_title': settings.RDBM_TITLE,
            # Specific bits
            'contact_request': self,
            'study': self.study,
            'patient_lookup': self.patient_lookup,
            'consent_mode': self.consent_mode,

            'permitted_to_contact_discharged_patients_for_n_days':
                settings.PERMITTED_TO_CONTACT_DISCHARGED_PATIENTS_FOR_N_DAYS,
            'permitted_to_contact_discharged_patients_for_n_years':
                days_to_years(
                    settings.PERMITTED_TO_CONTACT_DISCHARGED_PATIENTS_FOR_N_DAYS),  # noqa

            'RDBM_ADDRESS': settings.RDBM_ADDRESS,
        }
        return render_pdf_html_to_string('letter_researcher_approve.html',
                                         context, patient=False)

    def get_withdrawal_letter_html(self) -> str:
        """
        REC DOCUMENT 16.
        Letter to researcher notifying them of withdrawal of consent.
        """
        context = {
            # Letter bits
            'address_from': (
                settings.RDBM_ADDRESS +
                [settings.RDBM_TELEPHONE, settings.RDBM_EMAIL]
            ),
            'address_to': self.study.get_lead_researcher_name_address(),
            'salutation': self.study.get_lead_researcher_salutation(),
            'signatory_name': settings.RDBM_NAME,
            'signatory_title': settings.RDBM_TITLE,
            # Specific bits
            'contact_request': self,
            'study': self.study,
            'patient_lookup': self.patient_lookup,
            'consent_mode': self.consent_mode,
        }
        return render_pdf_html_to_string('letter_researcher_withdraw.html',
                                         context, patient=False)

    def get_approval_email_html(self) -> str:
        """Simple e-mail to researcher attaching letter."""
        context = {
            'contact_request': self,
            'study': self.study,
            'patient_lookup': self.patient_lookup,
            'consent_mode': self.consent_mode,
        }
        return render_email_html_to_string('email_researcher_approval.html',
                                           context)

    def get_withdrawal_email_html(self) -> str:
        """Simple e-mail to researcher attaching letter."""
        context = {
            'contact_request': self,
            'study': self.study,
            'patient_lookup': self.patient_lookup,
            'consent_mode': self.consent_mode,
        }
        return render_email_html_to_string('email_researcher_withdrawal.html',
                                           context)

    def get_letter_clinician_to_pt_re_study(self) -> str:
        """
        REC DOCUMENTS 10, 12, 14: draft letters from clinician to patient, with
        decision form.
        """
        patient_lookup = self.patient_lookup
        if not patient_lookup:
            raise Http404("No patient_lookup: is the back-end message queue "
                          "(e.g. Celery + RabbitMQ) running?")
        yellow = (self.clinician_involvement ==
                  ContactRequest.CLINICIAN_INVOLVEMENT_REQUIRED_YELLOW)
        context = {
            # Letter bits
            'address_from': patient_lookup.clinician_address_components(),
            'address_to': patient_lookup.pt_name_address_components(),
            'salutation': patient_lookup.pt_salutation(),
            'signatory_name':
            patient_lookup.clinician_title_forename_surname(),
            'signatory_title': patient_lookup.clinician_signatory_title,
            # Specific bits
            'contact_request': self,
            'study': self.study,
            'patient_lookup': patient_lookup,
            'settings': settings,

            'extra_form': self.is_extra_form(),
            'yellow': yellow,
            'unknown_consent_mode': self.is_consent_mode_unknown(),
        }
        return render_pdf_html_to_string(
            'letter_patient_from_clinician_re_study.html',
            context, patient=True)

    def is_extra_form(self) -> bool:
        study = self.study
        clinician_requested = not self.request_direct_approach
        extra_form = (clinician_requested and
                      study.subject_form_template_pdf.name)
        # log.debug("clinician_requested: {}".format(clinician_requested))
        # log.debug("extra_form: {}".format(extra_form))
        return extra_form

    def is_consent_mode_unknown(self) -> bool:
        return not self.consent_mode.consent_mode

    def get_decision_form_to_pt_re_study(self) -> str:
        n_forms = 1
        extra_form = self.is_extra_form()
        if extra_form:
            n_forms += 1
        yellow = (self.clinician_involvement ==
                  ContactRequest.CLINICIAN_INVOLVEMENT_REQUIRED_YELLOW)
        unknown = (self.clinician_involvement ==
                   ContactRequest.CLINICIAN_INVOLVEMENT_REQUIRED_UNKNOWN)
        if unknown:
            n_forms += 1
        context = {
            'contact_request': self,
            'study': self.study,
            'patient_lookup': self.patient_lookup,
            'settings': settings,

            'extra_form': extra_form,
            'n_forms': n_forms,
            'yellow': yellow,
        }
        return render_pdf_html_to_string(
            'decision_form_to_patient_re_study.html', context, patient=True)

    def get_clinician_pack_pdf(self) -> bytes:
        # Order should match letter...

        # Letter to patient from clinician
        pdf_plans = [CratePdfPlan(
            is_html=True,
            html=self.get_letter_clinician_to_pt_re_study()
        )]
        # Study details
        if self.study.study_details_pdf:
            pdf_plans.append(CratePdfPlan(
                is_filename=True,
                filename=self.study.study_details_pdf.path
            ))
        # Decision form about this study
        pdf_plans.append(CratePdfPlan(
            is_html=True,
            html=self.get_decision_form_to_pt_re_study()
        ))
        # Additional form for this study
        if self.is_extra_form():
            if self.study.subject_form_template_pdf:
                pdf_plans.append(CratePdfPlan(
                    is_filename=True,
                    filename=self.study.subject_form_template_pdf.path
                ))
        # Traffic-light decision form, if consent mode unknown
        if self.is_consent_mode_unknown():
            # 2017-03-03: changed to a personalized version

            # try:
            #     leaflet = Leaflet.objects.get(
            #         name=Leaflet.CPFT_TRAFFICLIGHT_CHOICE)
            #     pdf_plans.append(PdfPlan(is_filename=True,
            #                              filename=leaflet.pdf.path))
            # except ObjectDoesNotExist:
            #     log.warning("Missing traffic-light leaflet!")
            #     email_rdbm_task.delay(
            #         subject="ERROR FROM RESEARCH DATABASE COMPUTER",
            #         text=(
            #             "Missing traffic-light leaflet! Incomplete clinician "
            #             "pack accessed for contact request {}.".format(
            #                 self.id)
            #         )
            #     )

            pdf_plans.append(CratePdfPlan(
                is_html=True,
                html=self.patient_lookup.get_traffic_light_decision_form()
            ))
        # General info leaflet
        try:
            leaflet = Leaflet.objects.get(name=Leaflet.CPFT_TPIR)
            pdf_plans.append(CratePdfPlan(is_filename=True,
                                          filename=leaflet.pdf.path))
        except ObjectDoesNotExist:
            log.warning("Missing taking-part-in-research leaflet!")
            email_rdbm_task.delay(
                subject="ERROR FROM RESEARCH DATABASE COMPUTER",
                text=(
                    "Missing taking-part-in-research leaflet! Incomplete "
                    "clinician pack accessed for contact request {}.".format(
                        self.id)
                )
            )
        return get_concatenated_pdf_in_memory(pdf_plans, start_recto=True)

    def get_mgr_admin_url(self) -> str:
        from crate_anon.crateweb.core.admin import mgr_admin_site  # delayed import  # noqa
        return admin_view_url(mgr_admin_site, self)


# =============================================================================
# Clinician response
# =============================================================================

class ClinicianResponse(models.Model):
    TOKEN_LENGTH_CHARS = 20
    # info_bits = math.log(math.pow(26 + 26 + 10, TOKEN_LENGTH_CHARS), 2)
    # p_guess = math.pow(0.5, info_bits)

    RESPONSE_A = 'A'
    RESPONSE_B = 'B'
    RESPONSE_C = 'C'
    RESPONSE_D = 'D'
    RESPONSE_R = 'R'
    RESPONSES = (
        (RESPONSE_R, 'R: Clinician asks RDBM to pass request to patient'),
        (RESPONSE_A, 'A: Clinician will pass the request to the patient'),
        (RESPONSE_B, 'B: Clinician vetoes on clinical grounds'),
        (RESPONSE_C, 'C: Patient is definitely ineligible'),
        (RESPONSE_D, 'D: Patient is dead/discharged or details are defunct'),
    )

    ROUTE_EMAIL = 'e'
    ROUTE_WEB = 'w'
    RESPONSE_ROUTES = (
        (ROUTE_EMAIL, 'E-mail'),
        (ROUTE_WEB, 'Web'),
    )

    EMAIL_CHOICE_Y = 'y'
    EMAIL_CHOICE_N = 'n'
    EMAIL_CHOICE_TELL_ME_MORE = 'more'
    EMAIL_CHOICES = (
        (EMAIL_CHOICE_Y, 'Yes'),
        (EMAIL_CHOICE_N, 'No'),
        (EMAIL_CHOICE_TELL_ME_MORE, 'Tell me more'),
    )

    created_at = models.DateTimeField(verbose_name="When created",
                                      auto_now_add=True)
    contact_request = models.OneToOneField(ContactRequest,
                                           related_name="clinician_response")
    token = models.CharField(max_length=TOKEN_LENGTH_CHARS)
    responded = models.BooleanField(default=False, verbose_name="Responded?")
    responded_at = models.DateTimeField(verbose_name="When responded",
                                        null=True)
    response_route = models.CharField(max_length=1, choices=RESPONSE_ROUTES)
    email_choice = models.CharField(max_length=4, choices=EMAIL_CHOICES)
    response = models.CharField(max_length=1, choices=RESPONSES)
    veto_reason = models.TextField(
        blank=True,
        verbose_name="Reason for clinical veto")
    ineligible_reason = models.TextField(
        blank=True,
        verbose_name="Reason patient is ineligible")
    pt_uncontactable_reason = models.TextField(
        blank=True,
        verbose_name="Reason patient is not contactable")
    clinician_confirm_name = models.CharField(
        max_length=255, verbose_name="Type your name to confirm")
    charity_amount_due = models.DecimalField(max_digits=8, decimal_places=2,
                                             default=0)
    # ... set to settings.CHARITY_AMOUNT_CLINICIAN_RESPONSE upon response

    def get_response_explanation(self) -> str:
        # log.debug("get_response_explanation: {}".format(self.response))
        # noinspection PyTypeChecker
        return choice_explanation(self.response, ClinicianResponse.RESPONSES)

    @classmethod
    def create(cls,
               contact_request: ContactRequest,
               save: bool = True) -> CLINICIAN_RESPONSE_FWD_REF:
        newtoken = get_random_string(ClinicianResponse.TOKEN_LENGTH_CHARS)
        # https://github.com/django/django/blob/master/django/utils/crypto.py#L51  # noqa
        clinician_response = cls(
            contact_request=contact_request,
            token=newtoken,
        )
        if save:
            clinician_response.save()
        return clinician_response

    def get_abs_url_path(self) -> str:
        rev = reverse('clinician_response', args=[self.id])
        url = site_absolute_url(rev)
        return url

    def get_common_querydict(self, email_choice: str) -> QueryDict:
        querydict = QueryDict(mutable=True)
        querydict['token'] = self.token
        querydict['email_choice'] = email_choice
        return querydict

    def get_abs_url(self, email_choice: str) -> str:
        path = self.get_abs_url_path()
        querydict = self.get_common_querydict(email_choice)
        return url_with_querystring(path, querydict)

    def get_abs_url_yes(self) -> str:
        return self.get_abs_url(ClinicianResponse.EMAIL_CHOICE_Y)

    def get_abs_url_no(self) -> str:
        return self.get_abs_url(ClinicianResponse.EMAIL_CHOICE_N)

    def get_abs_url_maybe(self) -> str:
        return self.get_abs_url(ClinicianResponse.EMAIL_CHOICE_TELL_ME_MORE)

    def __str__(self):
        return "[ClinicianResponse {}] ContactRequest {}".format(
            self.id,
            self.contact_request_id,
        )

    def finalize_a(self) -> None:
        """
        Call this when the clinician completes their response.
        Part A: immediate, for acknowledgement.
        """
        self.responded = True
        self.responded_at = timezone.now()
        self.charity_amount_due = settings.CHARITY_AMOUNT_CLINICIAN_RESPONSE
        self.save()

    def finalize_b(self) -> None:
        """
        Call this when the clinician completes their response.
        Part B: background.
        """
        if self.response == ClinicianResponse.RESPONSE_R:
            # noinspection PyTypeChecker
            letter = Letter.create_request_to_patient(
                self.contact_request, rdbm_may_view=True)
            # ... will save
            # noinspection PyTypeChecker
            PatientResponse.create(self.contact_request)
            # ... will save
            self.contact_request.notify_rdbm_of_work(letter)
        elif self.response == ClinicianResponse.RESPONSE_A:
            # noinspection PyTypeChecker
            Letter.create_request_to_patient(
                self.contact_request, rdbm_may_view=False)
            # ... return value not used
            # noinspection PyTypeChecker
            PatientResponse.create(self.contact_request)
            self.contact_request.notify_rdbm_of_good_progress()
        elif self.response in (ClinicianResponse.RESPONSE_B,
                               ClinicianResponse.RESPONSE_C,
                               ClinicianResponse.RESPONSE_D):
            self.contact_request.notify_rdbm_of_bad_progress()
        self.save()


# =============================================================================
# Patient response
# =============================================================================

PATIENT_RESPONSE_FWD_REF = "PatientResponse"


class PatientResponse(Decision):
    YES = 1
    NO = 2
    RESPONSES = (
        (YES, '1: Yes'),
        (NO, '2: No'),
    )
    created_at = models.DateTimeField(verbose_name="When created",
                                      auto_now_add=True)
    contact_request = models.OneToOneField(ContactRequest,
                                           related_name="patient_response")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True)
    response = models.PositiveSmallIntegerField(
        null=True,
        choices=RESPONSES, verbose_name="Patient's response")

    def __str__(self):
        if self.response:
            # noinspection PyTypeChecker
            suffix = "response was {}".format(choice_explanation(
                self.response, PatientResponse.RESPONSES))
        else:
            suffix = "AWAITING RESPONSE"
        return "Patient response {} (contact request {}, study {}): {}".format(
            self.id,
            self.contact_request.id,
            self.contact_request.study.id,
            suffix,
        )

    @classmethod
    def create(cls, contact_request: ContactRequest) \
            -> PATIENT_RESPONSE_FWD_REF:
        patient_response = cls(contact_request=contact_request)
        patient_response.save()
        return patient_response

    def process_response(self) -> None:
        # log.debug("process_response: PatientResponse: {}".format(
        #     modelrepr(self)))
        if self.response == PatientResponse.YES:
            contact_request = self.contact_request
            # noinspection PyTypeChecker
            letter = Letter.create_researcher_approval(contact_request)
            # ... will save
            # noinspection PyTypeChecker
            email = Email.create_researcher_approval_email(contact_request,
                                                           letter)
            emailtransmission = email.send()
            emailed = emailtransmission.sent
            if not emailed:
                contact_request.notify_rdbm_of_work(letter, to_researcher=True)


# =============================================================================
# Letter, and record of letter being printed
# =============================================================================

class Letter(models.Model):
    created_at = models.DateTimeField(verbose_name="When created",
                                      auto_now_add=True)
    pdf = models.FileField(storage=privatestorage)
    # Other flags:
    to_clinician = models.BooleanField(default=False)
    to_researcher = models.BooleanField(default=False)
    to_patient = models.BooleanField(default=False)
    rdbm_may_view = models.BooleanField(default=False)
    study = models.ForeignKey(Study, null=True)
    contact_request = models.ForeignKey(ContactRequest, null=True)
    sent_manually_at = models.DateTimeField(null=True)

    def __str__(self):
        return "Letter {}".format(self.id)

    @classmethod
    def create(cls,
               basefilename: str,
               html: str = None,
               pdf: bytes = None,
               to_clinician: bool = False,
               to_researcher: bool = False,
               to_patient: bool = False,
               rdbm_may_view: bool = False,
               study: Study = None,
               contact_request: ContactRequest = None,
               debug_store_html: bool = False) -> LETTER_FWD_REF:
        # Writing to a FileField directly: you can use field.save(), but then
        # you having to write one file and copy to another, etc.
        # Here we use the method of assigning to field.name (you can't assign
        # to field.path). Also, note that you should never read
        # the path attribute if name is blank; it raises an exception.
        if (html and pdf) or (not html and not pdf):
            raise ValueError("Invalid html/pdf options to Letter.create")
        filename_in_storage = os.path.join("letter", basefilename)
        abs_filename = os.path.join(settings.PRIVATE_FILE_STORAGE_ROOT,
                                    filename_in_storage)
        os.makedirs(os.path.dirname(abs_filename), exist_ok=True)
        if html:
            # HTML supplied
            if debug_store_html:
                with open(abs_filename + ".html", 'w') as f:
                    f.write(html)
            make_pdf_on_disk_from_html_with_django_settings(
                html,
                output_path=abs_filename,
                header_html=None,
                footer_html=None)
        else:
            # PDF supplied in memory
            with open(abs_filename, 'wb') as f:
                f.write(pdf)
        letter = cls(to_clinician=to_clinician,
                     to_researcher=to_researcher,
                     to_patient=to_patient,
                     rdbm_may_view=rdbm_may_view,
                     study=study,
                     contact_request=contact_request)
        letter.pdf.name = filename_in_storage
        letter.save()
        return letter

    @classmethod
    def create_researcher_approval(cls, contact_request: ContactRequest) \
            -> LETTER_FWD_REF:
        basefilename = "cr{}_res_approve_{}.pdf".format(
            contact_request.id,
            string_time_now(),
        )
        html = contact_request.get_approval_letter_html()
        # noinspection PyTypeChecker
        return cls.create(basefilename,
                          html=html,
                          to_researcher=True,
                          study=contact_request.study,
                          contact_request=contact_request,
                          rdbm_may_view=True)

    @classmethod
    def create_researcher_withdrawal(cls, contact_request: ContactRequest) \
            -> LETTER_FWD_REF:
        basefilename = "cr{}_res_withdraw_{}.pdf".format(
            contact_request.id,
            string_time_now(),
        )
        html = contact_request.get_withdrawal_letter_html()
        # noinspection PyTypeChecker
        return cls.create(basefilename,
                          html=html,
                          to_researcher=True,
                          study=contact_request.study,
                          contact_request=contact_request,
                          rdbm_may_view=True)

    @classmethod
    def create_request_to_patient(cls,
                                  contact_request: ContactRequest,
                                  rdbm_may_view: bool = False) \
            -> LETTER_FWD_REF:
        basefilename = "cr{}_to_pt_{}.pdf".format(
            contact_request.id,
            string_time_now(),
        )
        pdf = contact_request.get_clinician_pack_pdf()
        # noinspection PyTypeChecker
        letter = cls.create(basefilename,
                            pdf=pdf,
                            to_patient=True,
                            study=contact_request.study,
                            contact_request=contact_request,
                            rdbm_may_view=rdbm_may_view)
        if not rdbm_may_view:
            # Letter is from clinician directly; clinician will print
            letter.mark_sent()
        return letter

    @classmethod
    def create_consent_confirmation_to_patient(
            cls, consent_mode: ConsentMode) -> LETTER_FWD_REF:
        basefilename = "cm{}_to_pt_{}.pdf".format(
            consent_mode.id,
            string_time_now(),
        )
        html = consent_mode.get_confirm_traffic_to_patient_letter_html()
        return cls.create(basefilename,
                          html=html,
                          to_patient=True,
                          rdbm_may_view=True)

    def mark_sent(self):
        self.sent_manually_at = timezone.now()
        self.save()


# noinspection PyUnusedLocal
@receiver(models.signals.post_delete, sender=Letter)
def auto_delete_letter_files_on_delete(sender: Type[Letter],
                                       instance: Letter,
                                       **kwargs: Any) -> None:
    """Deletes files from filesystem when Letter object is deleted."""
    auto_delete_files_on_instance_delete(instance, ['pdf'])


# noinspection PyUnusedLocal
@receiver(models.signals.pre_save, sender=Letter)
def auto_delete_letter_files_on_change(sender: Type[Letter],
                                       instance: Letter,
                                       **kwargs: Any) -> None:
    """Deletes files from filesystem when Letter object is changed."""
    auto_delete_files_on_instance_change(instance, ['pdf'], Letter)


# =============================================================================
# Record of sent e-mails
# =============================================================================

class Email(models.Model):
    # Let's not record host/port/user. It's configured into the settings.
    created_at = models.DateTimeField(verbose_name="When created",
                                      auto_now_add=True)
    sender = models.CharField(max_length=255, default=settings.EMAIL_SENDER)
    recipient = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    msg_text = models.TextField()
    msg_html = models.TextField()
    # Other flags and links:
    to_clinician = models.BooleanField(default=False)
    to_researcher = models.BooleanField(default=False)
    to_patient = models.BooleanField(default=False)
    study = models.ForeignKey(Study, null=True)
    contact_request = models.ForeignKey(ContactRequest, null=True)
    letter = models.ForeignKey(Letter, null=True)
    # Transmission attempts are in EmailTransmission.
    # Except that filtering in the admin

    def __str__(self):
        return "Email {} to {}".format(self.id, self.recipient)

    @classmethod
    def create_clinician_email(cls, contact_request: ContactRequest) \
            -> EMAIL_FWD_REF:
        recipient = contact_request.patient_lookup.clinician_email
        subject = (
            "RESEARCH REQUEST on behalf of {researcher}, contact request "
            "code {contact_req_code}".format(
                researcher=contact_request.study.lead_researcher.
                profile.get_title_forename_surname(),
                contact_req_code=contact_request.id
            )
        )
        html = contact_request.get_clinician_email_html()
        email = cls(recipient=recipient,
                    subject=subject,
                    msg_html=html,
                    study=contact_request.study,
                    contact_request=contact_request,
                    to_clinician=True)
        email.save()
        return email

    @classmethod
    def create_researcher_approval_email(
            cls,
            contact_request: ContactRequest,
            letter: Letter) -> EMAIL_FWD_REF:
        recipient = contact_request.study.lead_researcher.email
        subject = (
            "APPROVAL TO CONTACT PATIENT: contact request "
            "code {contact_req_code}".format(
                contact_req_code=contact_request.id
            )
        )
        html = contact_request.get_approval_email_html()
        email = cls(recipient=recipient,
                    subject=subject,
                    msg_html=html,
                    study=contact_request.study,
                    contact_request=contact_request,
                    letter=letter,
                    to_researcher=True)
        email.save()
        # noinspection PyTypeChecker
        EmailAttachment.create(email=email,
                               fileobj=letter.pdf,
                               content_type=ContentType.PDF)  # will save
        return email

    @classmethod
    def create_researcher_withdrawal_email(
            cls,
            contact_request: ContactRequest,
            letter: Letter) -> EMAIL_FWD_REF:
        recipient = contact_request.study.lead_researcher.email
        subject = (
            "WITHDRAWAL OF APPROVAL TO CONTACT PATIENT: contact request "
            "code {contact_req_code}".format(
                contact_req_code=contact_request.id
            )
        )
        html = contact_request.get_withdrawal_email_html()
        email = cls(recipient=recipient,
                    subject=subject,
                    msg_html=html,
                    study=contact_request.study,
                    contact_request=contact_request,
                    letter=letter,
                    to_researcher=True)
        email.save()
        # noinspection PyTypeChecker
        EmailAttachment.create(email=email,
                               fileobj=letter.pdf,
                               content_type=ContentType.PDF)  # will save
        return email

    @classmethod
    def create_rdbm_email(cls, subject: str, html: str) -> EMAIL_FWD_REF:
        email = cls(recipient=settings.RDBM_EMAIL,
                    subject=subject,
                    msg_html=html)
        email.save()
        return email

    @classmethod
    def create_rdbm_text_email(cls, subject: str, text: str) -> EMAIL_FWD_REF:
        email = cls(recipient=settings.RDBM_EMAIL,
                    subject=subject,
                    msg_text=text)
        email.save()
        return email

    def has_been_sent(self) -> bool:
        return self.emailtransmission_set.filter(sent=True).exists()

    def send(self,
             user: settings.AUTH_USER_MODEL = None,
             resend: bool = False) -> Optional[EMAIL_TRANSMISSION_FWD_REF]:
        if self.has_been_sent() and not resend:
            log.error("Trying to send e-mail twice: ID={}".format(self.id))
            return None
        if settings.SAFETY_CATCH_ON:
            self.recipient = settings.DEVELOPER_EMAIL
        try:
            if self.msg_html and not self.msg_text:
                # HTML-only email
                # http://www.masnun.com/2014/01/09/django-sending-html-only-email.html  # noqa
                msg = EmailMessage(subject=self.subject,
                                   body=self.msg_html,
                                   from_email=self.sender,
                                   to=[self.recipient])
                msg.content_subtype = "html"  # Main content is now text/html
            else:
                # Text only, or separate text/HTML
                msg = EmailMultiAlternatives(subject=self.subject,
                                             body=self.msg_text,
                                             from_email=self.sender,
                                             to=[self.recipient])
                if self.msg_html:
                    msg.attach_alternative(self.msg_html, "text/html")
            for attachment in self.emailattachment_set.all():
                # don't use msg.attach_file() if you want to control
                # the outbound filename; use msg.attach()
                if not attachment.file:
                    continue
                path = attachment.file.path
                if not attachment.sent_filename:
                    attachment.sent_filename = os.path.basename(path)
                    attachment.save()
                with open(path, 'rb') as f:
                    content = f.read()
                msg.attach(attachment.sent_filename,
                           content,
                           attachment.content_type or None)
            msg.send()
            sent = True
            failure_reason = ''
        except Exception as e:
            sent = False
            failure_reason = str(e)
        self.save()
        emailtransmission = EmailTransmission(email=self, by=user, sent=sent,
                                              failure_reason=failure_reason)
        emailtransmission.save()
        return emailtransmission

    def resend(self, user: settings.AUTH_USER_MODEL) -> None:
        return self.send(user=user, resend=True)


EMAIL_ATTACHMENT_FWD_REF = "EmailAttachment"


class EmailAttachment(models.Model):
    """E-mail attachment class that does NOT manage its own files, i.e. if
    the attachment object is deleted, the files won't be. Use this for
    referencing files already stored elsewhere in the database."""
    email = models.ForeignKey(Email)
    file = models.FileField(storage=privatestorage)
    sent_filename = models.CharField(null=True, max_length=255)
    content_type = models.CharField(null=True, max_length=255)
    owns_file = models.BooleanField(default=False)

    def exists(self) -> bool:
        if not self.file:
            return False
        return os.path.isfile(self.file.path)

    def size(self) -> int:
        if not self.file:
            return 0
        return os.path.getsize(self.file.path)

    @classmethod
    def create(cls,
               email: Email,
               fileobj: models.FileField,
               content_type: str,
               sent_filename: str = None,
               owns_file=False) -> EMAIL_ATTACHMENT_FWD_REF:
        if sent_filename is None:
            sent_filename = os.path.basename(fileobj.name)
        attachment = cls(email=email,
                         file=fileobj,
                         sent_filename=sent_filename,
                         content_type=content_type,
                         owns_file=owns_file)
        attachment.save()
        return attachment


# noinspection PyUnusedLocal
@receiver(models.signals.post_delete, sender=EmailAttachment)
def auto_delete_emailattachment_files_on_delete(sender: Type[EmailAttachment],
                                                instance: EmailAttachment,
                                                **kwargs: Any) -> None:
    """Deletes files from filesystem when EmailAttachment object is deleted."""
    if instance.owns_file:
        auto_delete_files_on_instance_delete(instance, ['file'])


# noinspection PyUnusedLocal
@receiver(models.signals.pre_save, sender=EmailAttachment)
def auto_delete_emailattachment_files_on_change(sender: Type[EmailAttachment],
                                                instance: EmailAttachment,
                                                **kwargs: Any) -> None:
    """Deletes files from filesystem when EmailAttachment object is changed."""
    if instance.owns_file:
        auto_delete_files_on_instance_change(instance, ['file'],
                                             EmailAttachment)


class EmailTransmission(models.Model):
    email = models.ForeignKey(Email)
    at = models.DateTimeField(verbose_name="When sent", auto_now_add=True)
    by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                           related_name="emailtransmissions")
    sent = models.BooleanField(default=False)
    failure_reason = models.TextField(verbose_name="Reason sending failed")

    def __str__(self):
        return "Email transmission at {} by {}: {}".format(
            self.at,
            self.by or "(system)",
            "success" if self.sent
            else "failure: {}".format(self.failure_reason)
        )


# =============================================================================
# A dummy set of objects, for template testing.
# Linked, so cross-references work.
# Don't save() them!
# =============================================================================

class DummyObjectCollection(object):
    def __init__(self,
                 contact_request: ContactRequest,
                 consent_mode: ConsentMode,
                 patient_lookup: PatientLookup,
                 study: Study,
                 clinician_response: ClinicianResponse):
        self.contact_request = contact_request
        self.consent_mode = consent_mode
        self.patient_lookup = patient_lookup
        self.study = study
        self.clinician_response = clinician_response


def make_dummy_objects(request: HttpRequest) -> DummyObjectCollection:
    """
    We want to create these objects in memory, without saving to the DB.
    However, Django  is less good at SQLAlchemy for this, and saves.

    - http://stackoverflow.com/questions/7908349/django-making-relationships-in-memory-without-saving-to-db  # noqa
    - https://code.djangoproject.com/ticket/17253
    - http://stackoverflow.com/questions/23372786/django-models-assigning-foreignkey-object-without-saving-to-database  # noqa
    - http://stackoverflow.com/questions/7121341/django-adding-objects-to-a-related-set-without-saving-to-db  # noqa

    A simple method works for an SQLite backend database but fails with
    an IntegrityError for MySQL/SQL Server. For example:

        IntegrityError at /draft_traffic_light_decision_form/-1/html/
        (1452, 'Cannot add or update a child row: a foreign key constraint
        fails (`crate_django`.`consent_study_researchers`, CONSTRAINT
        `consent_study_researchers_study_id_19bb255f_fk_consent_study_id`
        FOREIGN KEY (`study_id`) REFERENCES `consent_study` (`id`))')

    This occurs in the first creation, of a Study, and only if you specify
    'researchers'.

    The reason for the crash is that 'researchers' is a ManyToManyField, and
    Django is trying to set the user.studies_as_researcher back-reference, but
    can't do so because the Study doesn't have a PK yet.

    Since this is a minor thing, and templates are unaffected, and this is only
    for debugging, let's ignore it.
    """
    def get_int(query_param_name: str, default: Optional[int]) -> int:
        try:
            # noinspection PyCallByClass,PyTypeChecker
            return int(request.GET.get(query_param_name, default))
        except (TypeError, ValueError):
            return default

    def get_str(query_param_name: str, default: Optional[str]) -> str:
        # noinspection PyCallByClass,PyTypeChecker
        return request.GET.get(query_param_name, default)

    age = get_int('age', 40)
    age_months = get_int('age_months', 2)
    today = datetime.date.today()
    dob = today - relativedelta(years=age, months=age_months)

    consent_mode_str = get_str('consent_mode', None)
    # log.critical("consent_mode_str: {!r}".format(consent_mode_str))
    if consent_mode_str not in (None, ConsentMode.RED, ConsentMode.YELLOW,
                                ConsentMode.GREEN):
        consent_mode_str = None

    request_direct_approach = bool(get_int('request_direct_approach', 1))
    clinician_involvement = ContactRequest.get_clinician_involvement(
        consent_mode_str=consent_mode_str,
        request_direct_approach=request_direct_approach)

    consent_after_discharge = bool(get_int('consent_after_discharge', 0))

    nhs_number = 1234567890
    study = Study(
        id=TEST_ID,
        institutional_id=9999999999999,
        title="Functional neuroimaging of whimsy",
        lead_researcher=request.user,
        # researchers=[request.user],  # THIS BREAKS IT.
        # ... actual crash is in
        #   django/db/models/fields/related_descriptors.py:500, in
        #   ReverseManyToOneDescriptor.__set__(), calling
        #   manager.set(value)
        registered_at=datetime.datetime.now(),
        summary="An investigation of the change in blood-oxygen-level-"
                "dependent (BOLD) functional magnetic resonance imaging "
                "(fMRI) signals during the experience of quaint and "
                "fanciful humorous activity",
        search_methods_planned="Generalized trawl",
        patient_contact=True,
        include_under_16s=True,
        include_lack_capacity=True,
        clinical_trial=True,
        request_direct_approach=clinician_involvement,
        approved_by_rec=True,
        rec_reference="blah/999",
        approved_locally=True,
        local_approval_at=True,
        study_details_pdf=None,
        subject_form_template_pdf=None,
    )
    # import pdb; pdb.set_trace()
    consent_mode = ConsentMode(
        id=TEST_ID,
        nhs_number=nhs_number,
        current=True,
        created_by=request.user,
        exclude_entirely=False,
        consent_mode=consent_mode_str,
        consent_after_discharge=consent_after_discharge,
        max_approaches_per_year=0,
        other_requests="",
        prefers_email=False,
        changed_by_clinician_override=False,
        source="Fictional",
    )
    patient_lookup = PatientLookup(
        id=TEST_ID,
        # PatientLookupBase
        pt_local_id_description="MyEMR#",
        pt_local_id_number=987654,
        pt_dob=dob,
        pt_dod=None,
        pt_dead=False,
        pt_discharged=False,
        pt_discharge_date=None,
        pt_sex=PatientLookupBase.MALE,
        pt_title="Mr",
        pt_first_name="John",
        pt_last_name="Smith",
        pt_address_1="The Farthings",
        pt_address_2="1 Penny Lane",
        pt_address_3="Mordenville",
        pt_address_4="Slowtown",
        pt_address_5="Cambridgeshire",
        pt_address_6="CB1 0ZZ",
        pt_address_7="UK",
        pt_telephone="01223 000000",
        pt_email="john@smith.com",
        gp_title="Dr",
        gp_first_name="Gordon",
        gp_last_name="Generalist",
        gp_address_1="Honeysuckle Medical Practice",
        gp_address_2="99 Bloom Street",
        gp_address_3="Mordenville",
        gp_address_4="Slowtown",
        gp_address_5="Cambridgeshire",
        gp_address_6="CB1 9QQ",
        gp_address_7="UK",
        gp_telephone="01223 111111",
        gp_email="g.generalist@honeysuckle.nhs.uk",
        clinician_title="Dr",
        clinician_first_name="Petra",
        clinician_last_name="Paroxetine",
        clinician_address_1="Union House",
        clinician_address_2="37 Union Lane",
        clinician_address_3="Chesterton",
        clinician_address_4="Cambridge",
        clinician_address_5="Cambridgeshire",
        clinician_address_6="CB4 1PR",
        clinician_address_7="UK",
        clinician_telephone="01223 222222",
        clinician_email="p.paroxetine@cpft_or_similar.nhs.uk",
        clinician_is_consultant=True,
        clinician_signatory_title="Consultant psychiatrist",
        # PatientLookup
        nhs_number=nhs_number,
        source_db="Fictional database",
        decisions="No real decisions",
        secret_decisions="No real secret decisions",
        pt_found=True,
        gp_found=True,
        clinician_found=True,
    )
    contact_request = ContactRequest(
        id=TEST_ID,
        request_by=request.user,
        study=study,
        lookup_rid=9999999,
        processed=True,
        nhs_number=nhs_number,
        patient_lookup=patient_lookup,
        consent_mode=consent_mode,
        approaches_in_past_year=0,
        decisions="No decisions required",
        decided_no_action=False,
        decided_send_to_researcher=False,
        decided_send_to_clinician=True,
        clinician_involvement=clinician_involvement,
        consent_withdrawn=False,
        consent_withdrawn_at=None,
    )
    clinician_response = ClinicianResponse(
        id=TEST_ID,
        contact_request=contact_request,
        token="dummytoken",
        responded=False,
    )

    return DummyObjectCollection(
        contact_request=contact_request,
        consent_mode=consent_mode,
        patient_lookup=patient_lookup,
        study=study,
        clinician_response=clinician_response,
    )
