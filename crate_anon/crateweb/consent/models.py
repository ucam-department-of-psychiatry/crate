#!/usr/bin/env python

"""
crate_anon/crateweb/consent/models.py

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

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

**Django ORM models for the consent-to-contact system.**

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
from django.core.validators import validate_email
from django.db import models, transaction
from django.db.models import Q, QuerySet
from django.dispatch import receiver
from django.http import QueryDict, Http404
from django.http.request import HttpRequest
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.html import escape

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
    process_consent_change,
    process_contact_request,
    finalize_clinician_response,
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
from crate_anon.crateweb.userprofile.models import UserProfile

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

    Args:
        instance: instance of :class:`Study` (potentially unsaved;
            and you can't call :func:`save`; it goes into infinite recursion)
        filename: uploaded filename

    Returns:
        filename with extension but without path, to be used on the server
        filesystem
    """
    extension = os.path.splitext(filename)[1]  # includes the '.' if present
    return os.path.join(
        "study",
        f"{instance.institutional_id}_details_{string_time_now()}{extension}")
    # ... as id may not exist yet


def study_form_upload_to(instance: STUDY_FWD_REF, filename: str) -> str:
    """
    Determines the filename used for study clinician-form PDF uploads.

    Args:
        instance: instance of :class:`Study` (potentially unsaved
            and you can't call :func:`save`; it goes into infinite recursion)
        filename: uploaded filename

    Returns:
        filename with extension but without path, to be used on the server
        filesystem
    """
    extension = os.path.splitext(filename)[1]
    return os.path.join(
        "study",
        f"{instance.institutional_id}_form_{string_time_now()}{extension}")


class Study(models.Model):
    """
    Represents a research study.
    """
    # implicit 'id' field
    institutional_id = models.PositiveIntegerField(
        verbose_name="Institutional (e.g. NHS Trust) study number",
        unique=True)
    title = models.CharField(max_length=255, verbose_name="Study title")
    lead_researcher = models.ForeignKey(settings.AUTH_USER_MODEL,
                                        on_delete=models.PROTECT,
                                        related_name="studies_as_lead")
    researchers = models.ManyToManyField(settings.AUTH_USER_MODEL,
                                         related_name="studies_as_researcher",
                                         blank=True)
    registered_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="When was the study registered?")
    summary = models.TextField(verbose_name="Summary of study")
    summary_is_html = models.BooleanField(
        default=False,
        verbose_name="Is the summary in HTML (not plain text) format?")
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

    def __str__(self) -> str:
        # noinspection PyUnresolvedReferences
        return (
            f"[Study {self.id}] {self.institutional_id}: "
            f"{self.lead_researcher.get_full_name()} / {self.title}"
        )

    def get_lead_researcher_name_address(self) -> List[str]:
        """
        Returns name/address components (as lines you might use on a letter or
        envelope) for the study's lead researcher.
        """
        # noinspection PyUnresolvedReferences
        return (
            [self.lead_researcher.profile.get_title_forename_surname()] +
            self.lead_researcher.profile.get_address_components()
        )

    def get_lead_researcher_salutation(self) -> str:
        """
        Returns the salutation for the study's lead researcher (e.g.
        "Prof. Jones").
        """
        # noinspection PyUnresolvedReferences
        return self.lead_researcher.profile.get_salutation()

    def get_involves_lack_of_capacity(self) -> str:
        """
        Returns a human-readable string indicating whether or not the study
        involves patients lacking capacity (and if so, whether it's a clinical
        trial [CTIMP]).
        """
        if not self.include_lack_capacity:
            return "No"
        if self.clinical_trial:
            return "Yes (and it is a clinical trial)"
        return "Yes (and it is not a clinical trial)"

    @staticmethod
    def get_queryset_possible_contact_studies() -> QuerySet:
        """
        Returns all approved studies involving direct patient contact that
        have a properly identifiable lead researcher.
        """
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
        """
        Filters the supplied query set down to those studies for which the
        given user is a researcher on.
        """
        return queryset.filter(Q(lead_researcher=user) |
                               Q(researchers__in=[user]))\
                       .distinct()

    @property
    def html_summary(self) -> str:
        """
        Returns a version of the study's summary with HTML tags marking up
        paragraphs. If the summary is already in HTML format, just return
        that.
        """
        # Check if summary exists and if not return the empty string
        summary = self.summary
        if not summary:
            return ""

        # If the summary is already HTML, return it as it is.
        if self.summary_is_html:
            return summary

        # Split lines and ensure each line is HTML-escaped (e.g. if there's a
        # "<" or similar in the raw text).
        paragraphs = [escape(x) for x in summary.splitlines() if x]

        # NB an equivalent to
        #   [x for x in something if x]
        # is
        #   list(filter(None, something))

        if len(paragraphs) <= 1:
            # 0 or 1 paragraphs; no point using <p>
            return "".join(paragraphs)
        # Otherwise:

        # Method 1: with <p>
        # Visually better once CSS fixed.
        return "".join(f"<p>{x}</p>" for x in paragraphs)

        # Method 2: with <br>
        # Wider gaps.
        # return "<br><br>".join(paragraphs)


# noinspection PyUnusedLocal
@receiver(models.signals.post_delete, sender=Study)
def auto_delete_study_files_on_delete(sender: Type[Study],
                                      instance: Study,
                                      **kwargs: Any) -> None:
    """
    Django signal receiver.

    Deletes files from filesystem when :class:`Study` object is deleted.
    """
    auto_delete_files_on_instance_delete(instance,
                                         Study.AUTODELETE_OLD_FILE_FIELDS)


# noinspection PyUnusedLocal
@receiver(models.signals.pre_save, sender=Study)
def auto_delete_study_files_on_change(sender: Type[Study],
                                      instance: Study,
                                      **kwargs: Any) -> None:
    """
    Django signal receiver.

    Deletes files from filesystem when :class:`Study` object is changed.
    """
    auto_delete_files_on_instance_change(instance,
                                         Study.AUTODELETE_OLD_FILE_FIELDS,
                                         Study)


# =============================================================================
# Generic leaflets
# =============================================================================

def leaflet_upload_to(instance: LEAFLET_FWD_REF, filename: str) -> str:
    """
    Determines the filename used for leaflet uploads.

    Args:
        instance: instance of :class:`Leaflet` (potentially unsaved;
            and you can't call :func:`save`; it goes into infinite recursion)
        filename: uploaded filename

    Returns:
        filename with extension but without path, to be used on the server
        filesystem
    """
    extension = os.path.splitext(filename)[1]  # includes the '.' if present
    return os.path.join(
        "leaflet",
        f"{instance.name}_{string_time_now()}{extension}")
    # ... as id may not exist yet


class Leaflet(models.Model):
    """
    Represents a system-wide patient information leaflet.
    """
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

    def __str__(self) -> str:
        for x in Leaflet.LEAFLET_CHOICES:
            if x[0] == self.name:
                name = x[1]
                if not self.pdf:
                    name += " (MISSING)"
                return name
        return f"? (bad name: {self.name})"

    @staticmethod
    def populate() -> None:
        """
        Pre-create records for all the system-wide leaflets we use.
        """
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
    """
    Django signal receiver.

    Deletes files from filesystem when :class:`Leaflet` object is deleted.
    """
    auto_delete_files_on_instance_delete(instance, ['pdf'])


# noinspection PyUnusedLocal
@receiver(models.signals.pre_save, sender=Leaflet)
def auto_delete_leaflet_files_on_change(sender: Type[Leaflet],
                                        instance: Leaflet,
                                        **kwargs: Any) -> None:
    """
    Django signal receiver.
    Deletes files from filesystem when Leaflet object is changed.
    """
    auto_delete_files_on_instance_change(instance, ['pdf'], Leaflet)


# =============================================================================
# Generic fields for decisions
# =============================================================================

class Decision(models.Model):
    """
    Abstract class to represent how a decision has been made (e.g. by a patient
    or their surrogate decision-maker or clinician).
    """
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
        """
        Does the decision meet our rules about who can make decisions?
        """
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
        """
        Ensure that the decision is valid according to our rules, or raise
        :exc:`django.forms.ValidationError`.
        """
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
    """
    Represents information about a clinician (relating to a patient, whose
    details are not held here). Also embodies information about which sort of
    clinician we prefer to ask about patient contact requests (via
    :attr:`clinician_preference_order`).

    Python object only; not stored in the database.
    """
    CARE_COORDINATOR = 'care_coordinator'
    CONSULTANT = 'consultant'
    HCP = 'HCP'
    TEAM = 'team'

    def __init__(self, clinician_type: str,
                 title: str, first_name: str, surname: str, email: str,
                 signatory_title: str, is_consultant: bool,
                 start_date: Union[datetime.date, datetime.datetime],
                 end_date: Optional[Union[datetime.date, datetime.datetime]],
                 address_components: List[str] = None) -> None:
        """
        Args:
            clinician_type: one of our special strings indicating what type
                of clinician (e.g. care coordinator, consultant, other
                healthcare professional, authorized clinical team
                representative).
            title: clinician's title
            first_name: clinician's first name
            surname: clinician's surname
            email: clinician's e-mail address
            signatory_title: when the clinician signs a letter, what should
                go under their name to say what job they do? (For example:
                "Consultant psychiatrist"; "Care coordinator").
            is_consultant: is the clinician an NHS consultant? (Relates to
                special legal rules regarding CTIMPs.)
            start_date:
                when did this clinician's involvement start?
            end_date:
                when did this clinician's involvement end?
            address_components:
                address lines for the clinician
        """
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
        """
        Is the clinician currently involved (with this patient's care)?
        """
        return self.end_date is None or self.end_date >= datetime.date.today()

    def contactable(self) -> bool:
        """
        Do we have enough information to contact the clinician
        (electronically)?
        """
        return bool(self.surname and self.email)


class PatientLookupBase(models.Model):
    """
    Base class for :class:`PatientLookup` and :class:`DummyPatientSourceInfo`.

    Must be able to be instantiate with defaults, for the "not found"
    situation.

    Note that derived classes must implement ``nhs_number`` as a column.
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
        """
        Returns a salutation for the patient, like "Mrs Smith".
        """
        # noinspection PyTypeChecker
        return salutation(self.pt_title, self.pt_first_name, self.pt_last_name,
                          sex=self.pt_sex)

    def pt_title_forename_surname(self) -> str:
        """
        Returns the patient's title/forename/surname, like "Mrs Ann Smith".
        """
        # noinspection PyTypeChecker
        return title_forename_surname(self.pt_title, self.pt_first_name,
                                      self.pt_last_name)

    def pt_forename_surname(self) -> str:
        """
        Returns the patient's forename/surname, like "Ann Smith".
        """
        # noinspection PyTypeChecker
        return forename_surname(self.pt_first_name, self.pt_last_name)

    def pt_address_components(self) -> List[str]:
        """
        Returns lines of the patient's address (e.g. for letter headings or
        envelopes).
        """
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
        """
        Returns the patient's address as a single (one-line) string.
        """
        return ", ".join(filter(None, self.pt_address_components()))

    def pt_name_address_components(self) -> List[str]:
        """
        Returns the patient's name and address, as lines (e.g. for an
        envelope).
        """
        return [
            self.pt_title_forename_surname()
        ] + self.pt_address_components()

    def get_id_numbers_as_str(self) -> str:
        """
        Returns ID numbers, in a format like "NHS#: 123. RiO# 456."
        """
        # Note that self.nhs_number must be implemented by derived classes:
        # noinspection PyUnresolvedReferences
        idnums = [f"NHS#: {self.nhs_number}"]
        if self.pt_local_id_description:
            idnums.append(
                f"{self.pt_local_id_description}: {self.pt_local_id_number}")
        return ". ".join(idnums)

    def get_pt_age_years(self) -> Optional[int]:
        """
        Returns the patient's current age in years, or ``None`` if unknown.
        """
        if self.pt_dob is None:
            return None
        now = datetime.datetime.now()  # timezone-naive
        # now = timezone.now()  # timezone-aware
        return relativedelta(now, self.pt_dob).years

    def is_under_16(self) -> bool:
        """
        Is the patient under 16?
        """
        age = self.get_pt_age_years()
        return age is not None and age < 16

    def is_under_15(self) -> bool:
        """
        Is the patient under 15?
        """
        age = self.get_pt_age_years()
        return age is not None and age < 15

    def days_since_discharge(self) -> Optional[int]:
        """
        Returns the number of days since discharge, or ``None`` if the patient
        is not discharged (or if we don't know).
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
        """
        Returns the title/forename/surname for the patient's GP, like
        "Dr Joe Bloggs".
        """
        return title_forename_surname(self.gp_title, self.gp_first_name,
                                      self.gp_last_name, always_title=True,
                                      assume_dr=True)

    def gp_address_components(self) -> List[str]:
        """
        Returns address lines for the GP (e.g. for an envelope).
        """
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
        """
        Returns the GP's address as a single line.
        """
        return ", ".join(self.gp_address_components())

    def gp_name_address_str(self) -> str:
        """
        Returns the GP's name and address as a single line.
        """
        return ", ".join(filter(None, [self.gp_title_forename_surname(),
                                       self.gp_address_components_str()]))

    # noinspection PyUnusedLocal
    def set_gp_name_components(self,
                               name: str,
                               decisions: List[str],
                               secret_decisions: List[str]) -> None:
        """
        Takes a name, splits it into components as best it can, and stores it
        in the ``gp_title``, ``gp_first_name``, and ``gp_last_name`` fields.

        Args:
            name: GP name, e.g. "Dr Joe Bloggs"
            decisions: list of human-readable decisions; will be modified
            secret_decisions: list of human-readable decisions containing
                secret (identifiable) information; will be modified
        """
        secret_decisions.append(
            f"Setting GP name components from: {name}.")
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
        initial, surname = get_initial_surname_tuple_from_string(name)
        initial = initial.title()  # title case
        surname = surname.title()  # title case
        self.gp_title = "Dr"
        self.gp_first_name = initial + ("." if initial else "")
        self.gp_last_name = surname

    # -------------------------------------------------------------------------
    # Clinician
    # -------------------------------------------------------------------------

    def clinician_salutation(self) -> str:
        """
        Returns the salutation for the patient's clinician (e.g. "Dr
        Paroxetine").
        """
        # noinspection PyTypeChecker
        return salutation(self.clinician_title, self.clinician_first_name,
                          self.clinician_last_name, assume_dr=True)

    def clinician_title_forename_surname(self) -> str:
        """
        Returns the title/forename/surname for the patient's clinician (e.g.
        "Dr Petra Paroxetine").
        """
        # noinspection PyTypeChecker
        return title_forename_surname(self.clinician_title,
                                      self.clinician_first_name,
                                      self.clinician_last_name)

    def clinician_address_components(self) -> List[str]:
        """
        Returns the clinician's address -- or the Research Database Manager's
        (with "c/o") if we don't know the clinician's.

        (We're going to put the clinician's postal address into letters to
        patients. Therefore, we need a sensible fallback, i.e. the RDBM's.)
        """
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
        """
        Returns the clinician's address in single-line format.
        """
        return ", ".join(self.clinician_address_components())

    def clinician_name_address_str(self) -> str:
        """
        Returns the clinician's name and address in single-line format.
        """
        return ", ".join(filter(None, [
            self.clinician_title_forename_surname(),
            self.clinician_address_components_str()]))

    # -------------------------------------------------------------------------
    # Paperwork
    # -------------------------------------------------------------------------

    def get_traffic_light_decision_form(self) -> str:
        """
        Returns HTML for a traffic-light decision form, customized to this
        patient.
        """
        context = {
            'patient_lookup': self,
            'settings': settings,
        }
        return render_pdf_html_to_string(
            'traffic_light_decision_form.html', context, patient=True)


class DummyPatientSourceInfo(PatientLookupBase):
    """
    A patient lookup class that is a dummy one, for testing.
    """
    # Key
    nhs_number = models.BigIntegerField(verbose_name="NHS number",
                                        unique=True)

    class Meta:
        verbose_name_plural = "Dummy patient source information"

    def __str__(self) -> str:
        return (
            f"[DummyPatientSourceInfo {self.id}] "
            f"Dummy patient lookup for NHS# {self.nhs_number}")


class PatientLookup(PatientLookupBase):
    """
    Represents a moment of lookup up identifiable data about patient, GP,
    and clinician from the relevant clinical database.

    Inherits from :class:`PatientLookupBase` so it has the same fields, and
    more.
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

    def __repr__(self) -> str:
        return modelrepr(self)

    def __str__(self) -> str:
        return f"[PatientLookup {self.id}] NHS# {self.nhs_number}"

    def get_first_traffic_light_letter_html(self) -> str:
        """
        **REC DOCUMENT 06. Covering letter to patient for first enquiry about
        research preference.**

        Returns HTML for this document, customized to the patient.
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
        """
        Sets the clinician information fields from the supplied
        :class:`ClinicianInfoHolder`.
        """
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
    """
    Represents information about all clinical teams, fetched from a clinical
    source database.

    Provides some simple views on
    :func:`crate_anon.crateweb.consent.teamlookup.get_teams`.
    """
    @staticmethod
    def teams() -> List[str]:
        """
        Returns all clinical team names.
        """
        return get_teams()  # cached function

    @classmethod
    def team_choices(cls) -> List[Tuple[str, str]]:
        """
        Returns a Django choice list, i.e. a list of tuples like ``value,
        description``.
        """
        teams = cls.teams()
        return [(team, team) for team in teams]


class TeamRep(models.Model):
    """
    Represents a clinical team representative, which is recorded in CRATE.
    """
    team = models.CharField(max_length=LEN_NAME, unique=True,
                            verbose_name="Team description")
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE)

    class Meta:
        verbose_name = "clinical team representative"
        verbose_name_plural = "clinical team representatives"


# =============================================================================
# Record of payments to charity
# =============================================================================
# In passing - singleton objects:
#   http://goodcode.io/articles/django-singleton-models/

class CharityPaymentRecord(models.Model):
    """
    A record of a payment made to charity.
    """
    created_at = models.DateTimeField(verbose_name="When created",
                                      auto_now_add=True)
    payee = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=8, decimal_places=2)


# =============================================================================
# Record of consent mode for a patient
# =============================================================================

class ConsentMode(Decision):
    """
    Represents a consent-to-contact consent mode for a patient.
    """
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
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                   on_delete=models.PROTECT)

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

    skip_letter_to_patient = models.BooleanField(default=False)  # added 2018-06-29  # noqa
    needs_processing = models.BooleanField(default=False)  # added 2018-06-29
    processed = models.BooleanField(default=False)  # added 2018-06-29
    processed_at = models.DateTimeField(null=True)  # added 2018-06-29

    # class Meta:
    #     get_latest_by = "created_at"

    def save(self, *args, **kwargs) -> None:
        """
        Custom save method. Ensures that only one :class:`ConsentMode` has
        ``current == True`` for a given patient.

        This is better than a ``get_latest_by`` clause, because with a flag
        like this, we can have a simple query that says "get the current
        records for all patients" -- which is harder if done by date (group by
        patient, order by patient/date, pick last one for each patient...).
        
        See
        http://stackoverflow.com/questions/1455126/unique-booleanfield-value-in-django
        """  # noqa
        if self.current:
            ConsentMode.objects\
                       .filter(nhs_number=self.nhs_number, current=True)\
                       .update(current=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return (
            f"[ConsentMode {self.id}] "
            f"NHS# {self.nhs_number}, {self.consent_mode}"
        )

    @classmethod
    def get_or_create(
            cls,
            nhs_number: int,
            created_by: settings.AUTH_USER_MODEL) -> CONSENT_MODE_FWD_REF:
        """
        Fetches the current :class:`ConsentMode` for this patient.
        If there isn't one, creates a default one and returns that.
        """
        try:
            consent_mode = cls.objects.get(nhs_number=nhs_number,
                                           current=True)
        except cls.DoesNotExist:
            consent_mode = cls(nhs_number=nhs_number,
                               created_by=created_by,
                               source=cls.SOURCE_AUTOCREATED,
                               needs_processing=False,
                               current=True)
            consent_mode.save()
        except cls.MultipleObjectsReturned:
            log.warning("bug: ConsentMode.get_or_create() received "
                        "exception ConsentMode.MultipleObjectsReturned")
            consent_mode = cls(nhs_number=nhs_number,
                               created_by=created_by,
                               source=cls.SOURCE_AUTOCREATED,
                               needs_processing=False,
                               current=True)
            consent_mode.save()
        return consent_mode

    @classmethod
    def get_or_none(cls,
                    nhs_number: int) -> Optional[CONSENT_MODE_FWD_REF]:
        """
        Fetches the current :class:`ConsentMode` for this patient.
        If there isn't one, returns ``None``.
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

        .. todo:: also: use celery beat to refresh regularly +/- trigger
            withdrawal of consent if consent mode changed;
            http://docs.celeryproject.org/en/latest/userguide/periodic-tasks.html

        .. todo:: also make automatic opt-out list

        """
        from crate_anon.crateweb.consent.lookup import lookup_consent  # delayed import  # noqa

        decisions = []  # type: List[str]
        source_db = source_db or settings.CLINICAL_LOOKUP_CONSENT_DB
        decisions.append(f"source_db = {source_db}")

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
                f"CRATE stored version is at least as recent "
                f"({crate_version.created_at}) as the version from the "
                f"clinical record ({latest.created_at}); ignoring")
            return decisions

        # If we get here, we've found a newer version in the clinical record.
        latest.created_by = created_by
        latest.source = source_db
        latest.current = True
        latest.needs_processing = True
        latest.skip_letter_to_patient = True  # the patient already knows;
        # they made the decision with the clinician who entered this into the
        # primary clinical record.
        latest.save()  # This now becomes the current CRATE consent mode.
        transaction.on_commit(
            lambda: process_consent_change.delay(latest.id)
        )  # Asynchronous
        # Without transaction.on_commit, we get a RACE CONDITION:
        # object is received in the pre-save() state.
        return decisions

    def consider_withdrawal(self) -> None:
        """
        If required, withdraw consent for other studies.

        Note that as per Major Amendment 1 to 12/EE/0407, this happens
        automatically, rather than having a special flag to control it.
        """
        try:
            previous = ConsentMode.objects\
                .filter(nhs_number=self.nhs_number, current=False,
                        created_at__isnull=False)\
                .latest('created_at')
            # ... https://docs.djangoproject.com/en/dev/ref/models/querysets/#latest  # noqa
            if not previous:
                return  # no previous ConsentMode; nothing to do
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
        """
        Returns the latest :class:`PatientLookup` information (from the CRATE
        admin database) for this patient.
        """
        from crate_anon.crateweb.consent.lookup import lookup_patient  # delayed import  # noqa
        # noinspection PyTypeChecker
        return lookup_patient(self.nhs_number, existing_ok=True)

    def get_confirm_traffic_to_patient_letter_html(self) -> str:
        """
        **REC DOCUMENT 07. Confirming patient's traffic-light choice.**

        Returns HTML for this letter, customized to the patient.
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
        """
        E-mail the RDBM saying that there's new work to do: a letter to be
        sent.

        Args:
            letter: :class:`Letter`
            to_researcher: is it a letter that needs to go to a researcher,
                rather than to a patient?
        """
        subject = (
            f"WORK FROM RESEARCH DATABASE COMPUTER - consent mode {self.id}")
        if to_researcher:
            template = 'email_rdbm_new_work_researcher.html'
        else:
            template = 'email_rdbm_new_work_pt_from_rdbm.html'
        html = render_email_html_to_string(template, {'letter': letter})
        email = Email.create_rdbm_email(subject, html)
        email.send()

    @staticmethod
    def get_unprocessed() -> QuerySet:
        """
        Return all :class:`ConsentMode` objects that need processing.

        See :func:`crate_anon.crateweb.consent.tasks.process_consent_change`
        and :func:`process_change`, which does the work.
        """
        return ConsentMode.objects.filter(
            needs_processing=True,
            current=True,
            processed=False,
        )

    def process_change(self) -> None:
        """
        Called upon saving.

        - Will create a letter to patient.
        - May create a withdrawal-of-consent letter to researcher.
        - Marks the :class:`ConsentMode` as having been processed.

        **Major Amendment 1 (Oct 2014) to 12/EE/0407:** always withdraw consent
        and tell researchers, i.e. "active cancellation" of ongoing permission,
        where the researchers have not yet made contact.
        """
        if self.processed:
            log.warning(f"ConsentMode #{self.id}: already processed; "
                        f"not processing again")
            return
        if not self.needs_processing:
            return
        if not self.current:
            # No point processing non-current things.
            return

        if not self.skip_letter_to_patient:
            # noinspection PyTypeChecker
            letter = Letter.create_consent_confirmation_to_patient(self)
            # ... will save
            self.notify_rdbm_of_work(letter, to_researcher=False)

        self.consider_withdrawal()

        self.processed = True
        self.needs_processing = False
        self.processed_at = timezone.now()
        self.save()


# =============================================================================
# Request for patient contact
# =============================================================================

class ContactRequest(models.Model):
    """
    Represents a contact request to a patient (directly or indirectly) about a
    study.
    """
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
    request_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                   on_delete=models.PROTECT)
    study = models.ForeignKey(Study, on_delete=models.PROTECT)  # type: Study
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
    processed_at = models.DateTimeField(null=True)  # added 2018-06-29
    # Below: created during processing.

    # Those numbers translate to this:
    nhs_number = models.BigIntegerField(null=True, verbose_name="NHS number")
    # ... from which:
    patient_lookup = models.ForeignKey(PatientLookup,
                                       on_delete=models.SET_NULL,
                                       null=True)
    consent_mode = models.ForeignKey(ConsentMode,
                                     on_delete=models.SET_NULL,
                                     null=True)
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
    clinician_initiated = models.BooleanField(default=False)
    clinician_email = models.TextField(null=True, default=None)
    # Specifically for clinician-initiated case:
    rdbm_to_contact_pt = models.BooleanField(default=False)
    # Should be in form 'title firstname lastname'
    clinician_signatory_name = models.TextField(null=True, default=None)
    clinician_signatory_title = models.TextField(null=True, default=None)

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.decisionlist = []  # type: List[str]

    def __str__(self) -> str:
        return f"[ContactRequest {self.id}] Study {self.study_id}"

    @classmethod
    def create(cls,
               request: HttpRequest,
               study: Study,
               request_direct_approach: bool,
               lookup_nhs_number: int = None,
               lookup_rid: str = None,
               lookup_mrid: str = None,
               clinician_initiated: bool = False,
               clinician_email: str = None,
               rdbm_to_contact_pt: bool = False,
               clinician_signatory_name: Optional[str] = None,
               clinician_signatory_title: Optional[str] = None)\
            -> CONTACT_REQUEST_FWD_REF:
        """
        Create a contact request and act on it.

        Args:
            request: the :class:`django.http.request.HttpRequest`
            study: the :class:`Study`
            request_direct_approach: would the researchers prefer to approach
                the patient directly, if permitted?
            lookup_nhs_number: NHS number to look up patient from
            lookup_rid: research ID (RID) to look up patient from
            lookup_mrid: master research ID (MRID) to look up patient from
            clinician_initiated: contact request initiated by the clinician?
            clinician_email: override the clinician email in patient_lookup
            rdbm_to_contact_pt: should the rbdm contact the patient - for cases
                where the request was initiated by clinician
            clinician_signatory_name: name of clinician for letter - if None
                will use PatientLookup
            clinician_signatory_title: signatory title of clinician - if None
                will use PatientLookup

        Returns:
            a :class:`ContactRequest`
        """
        # https://docs.djangoproject.com/en/1.9/ref/request-response/
        # noinspection PyTypeChecker
        cr = cls(request_by=request.user,
                 study=study,
                 request_direct_approach=request_direct_approach,
                 lookup_nhs_number=lookup_nhs_number,
                 lookup_rid=lookup_rid,
                 lookup_mrid=lookup_mrid,
                 clinician_initiated=clinician_initiated,
                 clinician_email=clinician_email,
                 rdbm_to_contact_pt=rdbm_to_contact_pt,
                 clinician_signatory_name=clinician_signatory_name,
                 clinician_signatory_title=clinician_signatory_title)
        cr.save()
        transaction.on_commit(
            lambda: process_contact_request.delay(cr.id)
        )  # Asynchronous
        return cr

    @staticmethod
    def get_unprocessed() -> QuerySet:
        """
        Return all :class:`ContactRequest` objects that need processing.

        See :func:`crate_anon.crateweb.consent.tasks.process_contact_request`
        and :func:`process_request`, which does the work.
        """
        return ContactRequest.objects.filter(processed=False)

    def process_request(self) -> None:
        """
        Processes the :class:`ContactRequest` and marks it as processed. The
        main work is done by :func:`process_request_main`.
        """
        if self.processed:
            log.warning(f"ContactRequest #{self.id}: already processed; "
                        f"not processing again")
            return
        self.decisionlist = []  # type: List[str]
        self.process_request_main()
        self.decisions = " ".join(self.decisionlist)
        self.processed = True
        self.processed_at = timezone.now()
        self.save()

    def process_request_main(self) -> None:
        """
        Act on a contact request and store the decisions made.

        **CORE DECISION-MAKING FUNCTION FOR THE CONSENT-TO-CONTACT PROCESS.**

        Writes to :attr:`decisionlist`.
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
        # We may need to input clinician email manually, otherwise use default
        if not self.clinician_email:
            self.clinician_email = self.patient_lookup.clinician_email
        if not self.clinician_signatory_name:
            self.clinician_signatory_name = (
                self.patient_lookup.clinician_title_forename_surname())
        if not self.clinician_signatory_title:
            self.clinician_signatory_title = (
                self.patient_lookup.clinician_signatory_title)
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
                        f"patient was discharged {days_since_discharge} days "
                        f"ago; permission exists only for up to "
                        f"{permitted_n_days} days; patient did not consent to "
                        f"contact after discharge")
                    return

        # Maximum number of approaches exceeded?
        if self.consent_mode.max_approaches_per_year > 0:
            if (self.approaches_in_past_year >=
                    self.consent_mode.max_approaches_per_year):
                self.stop(
                    f"patient has had {self.approaches_in_past_year} "
                    f"approaches in the past year and has set a cap of "
                    f"{self.consent_mode.max_approaches_per_year} per year"
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

            # CLARIFICATION, CPFT Research Database Oversight Committee
            # 2018-11-12: even for CTIMPs, if patient is GREEN, researchers can
            # contact directly -- but will need consultant involvement at the
            # later (consent) stage.

            # noinspection PyUnresolvedReferences
            researcher_emailaddr = self.study.lead_researcher.email
            try:
                validate_email(researcher_emailaddr)
                # noinspection PyTypeChecker
                email = Email.create_researcher_approval_email(self, letter)
                emailtransmission = email.send()
                if emailtransmission.sent:
                    self.decide(f"Sent approval to researcher at "
                                f"{researcher_emailaddr}")
                    return
                self.decide(f"Failed to e-mail approval to researcher at "
                            f"{researcher_emailaddr}.")
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
        clinician_emailaddr = self.clinician_email
        try:
            validate_email(clinician_emailaddr)
        except ValidationError:
            self.stop(f"clinician e-mail ({clinician_emailaddr}) is invalid")
            return
        try:
            # noinspection PyTypeChecker
            validate_researcher_email_domain(clinician_emailaddr)
        except ValidationError:
            self.stop(f"clinician e-mail ({clinician_emailaddr}) "
                      f"is not in a permitted domain")
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

        # If the request is clinician initiated, we need to send a different
        # email. This will also create a clinician response and set the
        # clinician's response to either 'yes I will contact the patient' or
        # 'yes but let the RDBM contact them for me'
        if self.clinician_initiated:
            email = Email.create_clinician_initiated_cr_email(self)
            emailtransmission = email.send()
            if not emailtransmission.sent:
                # noinspection PyTypeChecker
                self.decide(emailtransmission.failure_reason)
                self.stop(f"Failed to send e-mail to clinician at "
                          f"{clinician_emailaddr}")
            self.decided_send_to_clinician = True
            self.decide(f"Sent request to clinician at {clinician_emailaddr}")
            return

        # Send e-mail to clinician
        # noinspection PyTypeChecker
        email = Email.create_clinician_email(self)
        # ... will also create a ClinicianResponse
        emailtransmission = email.send()
        if not emailtransmission.sent:
            # noinspection PyTypeChecker
            self.decide(emailtransmission.failure_reason)
            self.stop(f"Failed to send e-mail to clinician at "
                      f"{clinician_emailaddr}")
            # We don't set decided_send_to_clinician because this attempt has
            # failed, and we don't want to put anyone off trying again
            # immediately.
        self.decided_send_to_clinician = True
        self.decide(f"Sent request to clinician at {clinician_emailaddr}")

    @staticmethod
    def get_clinician_involvement(consent_mode_str: str,
                                  request_direct_approach: bool) -> int:
        """
        Returns a number indicating why a clinician is involved.

        Args:
            consent_mode_str: consent mode in use (see :class:`ConsentMode`)
            request_direct_approach: do the researchers request direct
                approach to the patient, if permitted?

        Returns:
            an integer constant; see :class:`ContactRequest`

        """
        # Let's be precise about why the clinician is involved.
        if not request_direct_approach:
            return ContactRequest.CLINICIAN_INVOLVEMENT_REQUESTED
        elif consent_mode_str == ConsentMode.YELLOW:
            return ContactRequest.CLINICIAN_INVOLVEMENT_REQUIRED_YELLOW
        else:
            # Only other possibility
            return ContactRequest.CLINICIAN_INVOLVEMENT_REQUIRED_UNKNOWN

    def decide(self, msg: str) -> None:
        """
        Make a note of a decision.
        """
        self.decisionlist.append(msg)

    def stop(self, msg: str) -> None:
        """
        Make a note of a decision and that we have finished processing this
        contact request, taking no further action.
        """
        self.decide("Stopping: " + msg)
        self.decided_no_action = True

    def calc_approaches_in_past_year(self) -> None:
        """
        Sets :attr:`approaches_in_past_year` to indicate the number of
        approaches in the past year to this patient via CRATE.

        How best to count this? Not by e.g. calendar year, with a flag that
        gets reset to zero annually, because you might have a limit of 5, and
        get 4 requests in Dec 2020 and then another 4 in Jan 2021 just after
        the flag resets. Instead, we count the number of requests to that
        patient in the past year.

        """
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
        """
        Withdraws consent that had previously been given. Will e-mail the
        researcher to let them know, if it can.

        Returns:
            tuple: ``letter, email_succeeded`` where ``letter`` is a
            :class:`Letter` to the researcher and ``email_succeeded`` indicates
            whether we managed to e-mail the researcher.

        """
        self.consent_withdrawn = True
        self.consent_withdrawn_at = timezone.now()
        self.save()
        # noinspection PyTypeChecker
        letter = Letter.create_researcher_withdrawal(self)  # will save
        # noinspection PyUnresolvedReferences
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
        """
        When was the researcher given permission? Used for the letter
        withdrawing permission.
        """
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
        """
        E-mail the RDBM to say that there's work to do.

        Args:
            letter: a :class:`Letter`
            to_researcher: is it a letter that needs to go to a researcher
                manually, rather than a letter that a clinician wants the
                RDBM to send on their behalf?
        """
        subject = (f"CHEERFUL WORK FROM RESEARCH DATABASE COMPUTER - "
                   f"contact request {self.id}")
        if to_researcher:
            template = 'email_rdbm_new_work_researcher.html'
        else:
            template = 'email_rdbm_new_work_pt_from_clinician.html'
        html = render_email_html_to_string(template, {'letter': letter})
        email = Email.create_rdbm_email(subject, html)
        email.send()

    def notify_rdbm_of_bad_progress(self) -> None:
        """
        Lets the RDBM know that a clinician refused (vetoed) a request.
        """
        subject = (f"INFO ONLY - clinician refused Research Database request "
                   f"- contact request {self.id}")
        html = render_email_html_to_string('email_rdbm_bad_progress.html', {
            'id': self.id,
            'response': self.clinician_response.response,
            'explanation': self.clinician_response.get_response_explanation(),
        })
        email = Email.create_rdbm_email(subject, html)
        email.send()

    def notify_rdbm_of_good_progress(self) -> None:
        """
        Lets the RDBM know that a clinician said yes to a request and wishes to
        do the work themselves.
        """
        subject = (f"INFO ONLY - clinician agreed to Research Database request"
                   f" - contact request {self.id}")
        html = render_email_html_to_string('email_rdbm_good_progress.html', {
            'id': self.id,
            'response': self.clinician_response.response,
            'explanation': self.clinician_response.get_response_explanation(),
        })
        email = Email.create_rdbm_email(subject, html)
        email.send()

    def get_clinician_email_html(self, save: bool = True) -> str:
        """
        **REC DOCUMENTS 09, 11, 13 (A): E-mail to clinician asking them to pass
        on contact request.**

        Args:
            save: save the e-mail to the database? (Only false for testing.)

        Returns:
            HTML for this e-mail

        - When we create a URL, should we put parameters in the path,
          querystring, or both?

          - see notes in ``core/utils.py``
          - In this case, we decide as follows: since we are creating a
            :class:`ClinicianResponse`, we should use its ModelForm.
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

    def get_clinician_initiated_email_html(self, save: bool = True) -> str:
        """
        Email to clinician confirming a clinician-initiated contact request.
        Will inlcude a link to the clinician pack if they do not want the RDBM
        to contact the patient for them. Also sets the clinician's response.

        Args:
            save: save the e-mail to the database? (Only false for testing.)

        Returns:
            HTML for this e-mail

        """
        clinician_response = ClinicianResponse.create(self, save=save)
        if not save:
            clinician_response.id = -1  # dummy PK, guaranteed to fail
        if self.rdbm_to_contact_pt:
            clinician_response.response = ClinicianResponse.RESPONSE_R
        else:
            clinician_response.response = ClinicianResponse.RESPONSE_A
        clinician_response.finalize_a()  # first part of processing
        transaction.on_commit(
            lambda: finalize_clinician_response.delay(clinician_response.id)
        )
        rev = reverse("clinician_pack", args=[clinician_response.id,
                                              clinician_response.token])
        url_pack = site_absolute_url(rev)
        context = {
            'contact_request': self,
            'study': self.study,
            'patient_lookup': self.patient_lookup,
            'consent_mode': self.consent_mode,
            'clinician_response': clinician_response,
            'settings': settings,
            'url_pack': url_pack,
        }
        return render_email_html_to_string('email_clinician_initiated_cr.html',
                                           context)

    def get_approval_letter_html(self) -> str:
        """
        **REC DOCUMENT 15. Letter to researcher approving contact.**

        Returns the HTML for this letter.
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
        **REC DOCUMENT 16. Letter to researcher notifying them of withdrawal of
        consent.**

        Returns the HTML for this letter.
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
        """
        Returns HTML for a simple e-mail to the researcher attaching an
        approval letter.
        """
        context = {
            'contact_request': self,
            'study': self.study,
            'patient_lookup': self.patient_lookup,
            'consent_mode': self.consent_mode,
        }
        return render_email_html_to_string('email_researcher_approval.html',
                                           context)

    def get_withdrawal_email_html(self) -> str:
        """
        Returns HTML for a simple e-mail to the researcher attaching an
        withdrawal-of-previous-consent letter.
        """
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
        **REC DOCUMENTS 10, 12, 14: draft letters from clinician to patient,
        with decision form.**

        Returns the HTML for this letter.
        """
        patient_lookup = self.patient_lookup
        if not patient_lookup:
            raise Http404("No patient_lookup: is the back-end message queue "
                          "(e.g. Celery + RabbitMQ) running?")
        yellow = (self.clinician_involvement ==
                  ContactRequest.CLINICIAN_INVOLVEMENT_REQUIRED_YELLOW)
        if self.clinician_initiated:
            clinician_address_components = self.request_by_address_components()
        else:
            clinician_address_components = (
                patient_lookup.clinician_address_components())
        context = {
            # Letter bits
            'address_from': clinician_address_components,
            'address_to': patient_lookup.pt_name_address_components(),
            'salutation': patient_lookup.pt_salutation(),
            'signatory_name': self.clinician_signatory_name,
            'signatory_title': self.clinician_signatory_title,
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
        """
        Is there an extra form from the researchers that they wish passed on to
        the patient?
        """
        study = self.study
        clinician_requested = not self.request_direct_approach
        extra_form = (clinician_requested and
                      study.subject_form_template_pdf.name)
        # log.debug(f"clinician_requested: {clinician_requested}")
        # log.debug(f"extra_form: {extra_form}")
        return extra_form

    def is_consent_mode_unknown(self) -> bool:
        """
        Is the consent mode "unknown" (NULL in the database)?
        """
        return not self.consent_mode.consent_mode

    def get_decision_form_to_pt_re_study(self) -> str:
        """
        Returns HTML for the form for the patient to decide about this
        study.
        """
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
        """
        Returns a PDF of the "clinician pack": a cover letter, decision forms,
        and any other information required, customized for this request.
        """
        # Order should match letter...

        # Letter to patient from clinician
        pdf_plans = [CratePdfPlan(
            is_html=True,
            html=self.get_letter_clinician_to_pt_re_study()
        )]
        # Study details
        if self.study.study_details_pdf:
            # noinspection PyUnresolvedReferences
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
                # noinspection PyUnresolvedReferences
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
                    f"Missing taking-part-in-research leaflet! Incomplete "
                    f"clinician pack accessed for contact request {self.id}."
                )
            )
        return get_concatenated_pdf_in_memory(pdf_plans, start_recto=True)

    def get_mgr_admin_url(self) -> str:
        """
        Returns the URL for the admin site to view this
        :class:`ContactRequest`.
        """
        from crate_anon.crateweb.core.admin import mgr_admin_site  # delayed import  # noqa
        return admin_view_url(mgr_admin_site, self)

    def request_by_address_components(self) -> List[str]:
        """
        Returns the address of the person who made the contact request -- or
        the Research Database Manager's (with "c/o") if we don't know the
        requester's.

        This will be used in cases of a clinician-iniated request, for use in
        letters to the patient.
        """
        try:
            userprofile = UserProfile.objects.get(user=self.request_by)
        except UserProfile.DoesNotExist:
            log.warning("ContactRequest object needs 'request_by' to be "
                        "a valid user for 'request_by_address_components'.")
            address_components = []
        else:
            address_components = [
                userprofile.address_1,
                userprofile.address_2,
                userprofile.address_3,
                userprofile.address_4,
                userprofile.address_5,
                userprofile.address_6,
                userprofile.address_7,
            ]
        if not any(x for x in address_components):
            address_components = settings.RDBM_ADDRESS.copy()
            if address_components:
                address_components[0] = "c/o " + address_components[0]
        return list(filter(None, address_components))


# =============================================================================
# Clinician response
# =============================================================================

class ClinicianResponse(models.Model):
    """
    Represents the response of a clinician to a :class:`ContactRequest` that
    was routed to them.
    """
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
                                           on_delete=models.PROTECT,
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

    processed = models.BooleanField(default=False)  # added 2018-06-29
    processed_at = models.DateTimeField(null=True)  # added 2018-06-29

    def get_response_explanation(self) -> str:
        """
        Returns the human-readable description of the clinician's response.
        """
        # log.debug(f"get_response_explanation: {self.response}")
        # noinspection PyTypeChecker
        return choice_explanation(self.response, ClinicianResponse.RESPONSES)

    @classmethod
    def create(cls,
               contact_request: ContactRequest,
               save: bool = True) -> CLINICIAN_RESPONSE_FWD_REF:
        """
        Creates a new clinician response object.

        Args:
            contact_request: a :class:`ContactRequest`
            save: save to the database? (Only false for debugging.)

        Returns:
            a :class:`ClinicianResponse`

        """
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
        """
        Returns an absolute URL path to the page that lets the clinician
        respond for this :class:`ClinicianResponse`.

        This is used in the e-mail to the clinician.
        """
        rev = reverse('clinician_response', args=[self.id])
        url = site_absolute_url(rev)
        return url

    def get_common_querydict(self, email_choice: str) -> QueryDict:
        """
        Returns a query dictionary that will contribute to our final URLs. That
        is, information about the clinician's choice (and also a security
        token) that will be added to the base "response" URL path.

        Args:
            email_choice: code for the clinician's choice

        Returns:
            a :class:`django.http.request.QueryDict`

        """
        querydict = QueryDict(mutable=True)
        querydict['token'] = self.token
        querydict['email_choice'] = email_choice
        return querydict

    def get_abs_url(self, email_choice: str) -> str:
        """
        Returns an absolute URL representing a specific choice for the
        clinician.

        Args:
            email_choice: code for the clinician's choice

        Returns:
            a URL

        """
        path = self.get_abs_url_path()
        querydict = self.get_common_querydict(email_choice)
        return url_with_querystring(path, querydict)

    def get_abs_url_yes(self) -> str:
        """
        Returns an absolute URL for "clinician says yes".
        """
        return self.get_abs_url(ClinicianResponse.EMAIL_CHOICE_Y)

    def get_abs_url_no(self) -> str:
        """
        Returns an absolute URL for "clinician says no".
        """
        return self.get_abs_url(ClinicianResponse.EMAIL_CHOICE_N)

    def get_abs_url_maybe(self) -> str:
        """
        Returns an absolute URL for "clinician says tell me more".
        """
        return self.get_abs_url(ClinicianResponse.EMAIL_CHOICE_TELL_ME_MORE)

    def __str__(self) -> str:
        return (
            f"[ClinicianResponse {self.id}] "
            f"ContactRequest {self.contact_request_id}"
        )

    def finalize_a(self) -> None:
        """
        Call this when the clinician completes their response.

        Part A: immediate, called from the web front end, for acknowledgement.
        """
        self.responded = True
        self.responded_at = timezone.now()
        self.charity_amount_due = settings.CHARITY_AMOUNT_CLINICIAN_RESPONSE
        self.save()

    @staticmethod
    def get_unprocessed() -> QuerySet:
        return ClinicianResponse.objects.filter(processed=False)

    def finalize_b(self) -> None:
        """
        Call this when the clinician completes their response.

        Part B: called by the background task processor, for the slower
        aspects.
        """
        if self.processed:
            log.warning(f"ClinicianResponse #{self.id}: already processed; "
                        f"not processing again")
            return
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
        self.processed = True
        self.processed_at = timezone.now()
        self.save()


# =============================================================================
# Patient response
# =============================================================================

PATIENT_RESPONSE_FWD_REF = "PatientResponse"


class PatientResponse(Decision):
    """
    Represents the patient's decision about a specific study. (We get one of
    these if the clinician passed details to the patient and the patient has
    responded.)
    """
    YES = 1
    NO = 2
    RESPONSES = (
        (YES, '1: Yes'),
        (NO, '2: No'),
    )
    created_at = models.DateTimeField(verbose_name="When created",
                                      auto_now_add=True)
    contact_request = models.OneToOneField(ContactRequest,
                                           on_delete=models.PROTECT,
                                           related_name="patient_response")
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                    on_delete=models.PROTECT,
                                    null=True)
    response = models.PositiveSmallIntegerField(
        null=True,
        choices=RESPONSES, verbose_name="Patient's response")
    processed = models.BooleanField(default=False)  # added 2018-06-29
    processed_at = models.DateTimeField(null=True)  # added 2018-06-29

    def __str__(self) -> str:
        if self.response:
            # noinspection PyTypeChecker
            suffix = "response was {}".format(choice_explanation(
                self.response, PatientResponse.RESPONSES))
        else:
            suffix = "AWAITING RESPONSE"
        return (
            f"Patient response {self.id} "
            f"(contact request {self.contact_request.id}, "
            f"study {self.contact_request.study.id}): {suffix}"
        )

    @classmethod
    def create(cls, contact_request: ContactRequest) \
            -> PATIENT_RESPONSE_FWD_REF:
        """
        Creates a patient response object for a given contact request.

        Args:
            contact_request: a :class:`ContactRequest`

        Returns:
            :class:`PatientResponse`

        """
        patient_response = cls(contact_request=contact_request)
        patient_response.save()
        return patient_response

    @staticmethod
    def get_unprocessed() -> QuerySet:
        """
        Return all :class:`PatientResponse` objects that need processing.

        See :func:`crate_anon.crateweb.consent.tasks.process_patient_response`
        and :func:`process_response`, which does the work.
        """
        return PatientResponse.objects.filter(processed=False)

    def process_response(self) -> None:
        """
        Processes the :class:`PatientResponse` and marks it as processed.

        If the patient said yes, this triggers a letter to the researcher.
        """
        # log.debug(f"process_response: PatientResponse: {modelrepr(self)}")
        if self.processed:
            log.warning(f"PatientResponse #{self.id}: already processed; "
                        f"not processing again")
            return
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
        self.processed = True
        self.processed_at = timezone.now()
        self.save()


# =============================================================================
# Letter, and record of letter being printed
# =============================================================================

class Letter(models.Model):
    """
    Represents a letter (e.g. to a patient, clinician, or researcher).
    """
    created_at = models.DateTimeField(verbose_name="When created",
                                      auto_now_add=True)
    pdf = models.FileField(storage=privatestorage)
    # Other flags:
    to_clinician = models.BooleanField(default=False)
    to_researcher = models.BooleanField(default=False)
    to_patient = models.BooleanField(default=False)
    rdbm_may_view = models.BooleanField(default=False)
    study = models.ForeignKey(Study, on_delete=models.PROTECT, null=True)
    contact_request = models.ForeignKey(ContactRequest,
                                        on_delete=models.PROTECT, null=True)
    sent_manually_at = models.DateTimeField(null=True)

    def __str__(self) -> str:
        return f"Letter {self.id}"

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
        """
        Creates a letter.

        Args:
            basefilename: filename to be used to store a PDF copy of the letter
                on disk (without a path)
            html: for letters supplied as HTML, the HTML
            pdf: for letters supplied as PDF, the PDF
            to_clinician: is the letter to a clinician?
            to_researcher: is the letter to a researcher?
            to_patient: is the letter to a patient?
            rdbm_may_view: may the RDBM view this letter?
            study: which :class:`Study` does it relate to, if any?
            contact_request: which :class:`ContactRequest` does it relate to,
                if any?
            debug_store_html: should we store the HTML of the letter, as well
                as the PDF (for letters originating in HTML only)?

        Returns:
            a :class:`Letter`

        """
        # Writing to a FileField directly: you can use field.save(), but then
        # you having to write one file and copy to another, etc.
        # Here we use the method of assigning to field.name (you can't assign
        # to field.path). Also, note that you should never read
        # the path attribute if name is blank; it raises an exception.
        if bool(html) == bool(pdf):
            # One or the other!
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
        """
        Creates a letter to a researcher giving approval to contact a patient.

        Args:
            contact_request: a :class:`ContactRequest`

        Returns:
            a :class:`Letter`

        """
        basefilename = (
            f"cr{contact_request.id}_res_approve_{string_time_now()}.pdf"
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
        """
        Creates a letter to a researcher withdrawing previous approval to
        contact a patient.

        Args:
            contact_request: a :class:`ContactRequest`

        Returns:
            a :class:`Letter`

        """
        basefilename = (
            f"cr{contact_request.id}_res_withdraw_{string_time_now()}.pdf"
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
        """
        Creates a letter to a patient asking them about a specific study.

        Args:
            contact_request: a :class:`ContactRequest`
            rdbm_may_view: is this a request that the Research Database
                Manager (RDBM) is allowed to see under our information
                governance rules?

        Returns:
            a :class:`Letter`

        """
        basefilename = f"cr{contact_request.id}_to_pt_{string_time_now()}.pdf"
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
        """
        Creates a letter to a patient confirming their traffic-light
        consent-mode choice.

        Args:
            consent_mode: a :class:`ConsentMode`

        Returns:
            a :class:`Letter`

        """
        basefilename = f"cm{consent_mode.id}_to_pt_{string_time_now()}.pdf"
        html = consent_mode.get_confirm_traffic_to_patient_letter_html()
        return cls.create(basefilename,
                          html=html,
                          to_patient=True,
                          rdbm_may_view=True)

    def mark_sent(self):
        """
        Mark the letter as having been sent now.
        """
        self.sent_manually_at = timezone.now()
        self.save()


# noinspection PyUnusedLocal
@receiver(models.signals.post_delete, sender=Letter)
def auto_delete_letter_files_on_delete(sender: Type[Letter],
                                       instance: Letter,
                                       **kwargs: Any) -> None:
    """
    Django signal receiver.

    Deletes files from filesystem when a :class:`Letter` object is deleted.
    """
    auto_delete_files_on_instance_delete(instance, ['pdf'])


# noinspection PyUnusedLocal
@receiver(models.signals.pre_save, sender=Letter)
def auto_delete_letter_files_on_change(sender: Type[Letter],
                                       instance: Letter,
                                       **kwargs: Any) -> None:
    """
    Django signal receiver.

    Deletes files from filesystem when a :class:`Letter` object is changed.
    """
    auto_delete_files_on_instance_change(instance, ['pdf'], Letter)


# =============================================================================
# Record of sent e-mails
# =============================================================================

def _get_default_email_sender() -> str:
    """
    Returns the default e-mail sender.
    
    Using a callable, ``default=_get_default_email_sender``, rather than a
    value, ``default=settings.EMAIL_SENDER``, makes the Django migration system
    stop implementing pointless changes when local settings change.
    
    See
    https://docs.djangoproject.com/en/2.1/ref/models/fields/#django.db.models.Field.default
    """  # noqa
    return settings.EMAIL_SENDER


class Email(models.Model):
    """
    Represents an e-mail sent (or to be sent) from CRATE.
    """
    # Let's not record host/port/user. It's configured into the settings.
    created_at = models.DateTimeField(verbose_name="When created",
                                      auto_now_add=True)
    sender = models.CharField(max_length=255,
                              default=_get_default_email_sender)
    recipient = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    msg_text = models.TextField()
    msg_html = models.TextField()
    # Other flags and links:
    to_clinician = models.BooleanField(default=False)
    to_researcher = models.BooleanField(default=False)
    to_patient = models.BooleanField(default=False)
    study = models.ForeignKey(Study, on_delete=models.PROTECT, null=True)
    contact_request = models.ForeignKey(ContactRequest,
                                        on_delete=models.PROTECT, null=True)
    letter = models.ForeignKey(Letter, on_delete=models.PROTECT, null=True)
    # Transmission attempts are in EmailTransmission.
    # Except that filtering in the admin

    def __str__(self) -> str:
        return f"Email {self.id} to {self.recipient}"

    @classmethod
    def create_clinician_email(cls, contact_request: ContactRequest) \
            -> EMAIL_FWD_REF:
        """
        Creates an e-mail to a clinician, asking them to consider a request
        from a study about a patient.

        Args:
            contact_request: a :class:`ContactRequest`

        Returns:
            an :class:`Email`

        """
        recipient = contact_request.clinician_email
        # noinspection PyUnresolvedReferences
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
    def create_clinician_initiated_cr_email(
            cls,
            contact_request: ContactRequest)-> EMAIL_FWD_REF:
        """
        Creates an e-mail to a clinician when they have initiated a contact
        request. This email will give them a link to the clinician pack if
        they said they'd contact the patient.

        Args:
            contact_request: a :class:`ContactRequest`

        Returns:
            an :class:`Email`

        """
        recipient = contact_request.clinician_email
        # noinspection PyUnresolvedReferences
        subject = (
            f"Confirmation of request for patient to be included in study. "
            f"Contact request code {contact_request.id}"
        )
        html = contact_request.get_clinician_initiated_email_html()
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
        """
        Creates an e-mail to a researcher, enclosing a letter giving them
        permission to contact a patient.

        Args:
            contact_request: a :class:`ContactRequest`
            letter: a :class:`Letter`

        Returns:
            an :class:`Email`

        """
        # noinspection PyUnresolvedReferences
        recipient = contact_request.study.lead_researcher.email
        subject = (
            f"APPROVAL TO CONTACT PATIENT: contact request code "
            f"{contact_request.id}"
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
        """
        Creates an e-mail to a researcher, enclosing a letter withdrawing their
        permission to contact a patient.

        Args:
            contact_request: a :class:`ContactRequest`
            letter: a :class:`Letter`

        Returns:
            an :class:`Email`

        """
        # noinspection PyUnresolvedReferences
        recipient = contact_request.study.lead_researcher.email
        subject = (
            f"WITHDRAWAL OF APPROVAL TO CONTACT PATIENT: contact request code "
            f"{contact_request.id}"
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
        """
        Create an HTML-based e-mail to the RDBM.

        Args:
            subject: subject line
            html: HTML body

        Returns:
            an :class:`Email`

        """
        email = cls(recipient=settings.RDBM_EMAIL,
                    subject=subject,
                    msg_html=html)
        email.save()
        return email

    @classmethod
    def create_rdbm_text_email(cls, subject: str, text: str) -> EMAIL_FWD_REF:
        """
        Create an text-based e-mail to the RDBM.

        Args:
            subject: subject line
            text: message body

        Returns:
            an :class:`Email`

        """
        email = cls(recipient=settings.RDBM_EMAIL,
                    subject=subject,
                    msg_text=text)
        email.save()
        return email

    def has_been_sent(self) -> bool:
        """
        Has this e-mail been sent?

        (Internally: does an :class:`EmailTransmission` for this e-mail
        exist with its ``sent`` flag set?)
        """
        return self.emailtransmission_set.filter(sent=True).exists()

    def send(self,
             user: settings.AUTH_USER_MODEL = None,
             resend: bool = False) -> Optional[EMAIL_TRANSMISSION_FWD_REF]:
        """
        Sends the e-mail. Makes a record.

        Args:
            user: the sender.
            resend: say that it's OK to resend one that's already been sent.

        Returns:
            an :class:`EmailTransmission` object.
        """
        if self.has_been_sent() and not resend:
            log.error(f"Trying to send e-mail twice: ID={self.id}")
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
        """
        Resend this e-mail.
        """
        return self.send(user=user, resend=True)


EMAIL_ATTACHMENT_FWD_REF = "EmailAttachment"


class EmailAttachment(models.Model):
    """
    E-mail attachment class.

    Typically, this does NOT manage its own files (i.e. if the attachment
    object is deleted, the files won't be). Use this method for referencing
    files already stored elsewhere in the database.

    If the :attr:`owns_file` attribute is set, however, the associated file
    *is* "owned" by this object, and the file will be deleted when the database
    object is.
    """
    email = models.ForeignKey(Email, on_delete=models.PROTECT)
    file = models.FileField(storage=privatestorage)
    sent_filename = models.CharField(null=True, max_length=255)
    content_type = models.CharField(null=True, max_length=255)
    owns_file = models.BooleanField(default=False)

    def exists(self) -> bool:
        """
        Does the attached file exist on disk?
        """
        if not self.file:
            return False
        return os.path.isfile(self.file.path)

    def size(self) -> int:
        """
        Returns the size of the attachment in bytes, if it exists on disk
        (otherwise 0).
        """
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
        """
        Creates an e-mail attachment object and attaches it to an e-mail.
        When the e-mail is sent, the file thus referenced will be sent along
        with the e-mail; see :meth:`Email.send`.

        Args:
            email: an :class:`Email`, to which this attachment is attached
            fileobj: a :class:`django.db.models.FileField` representing the
                file (on disk) to be attached
            content_type: HTTP content type string
            sent_filename: name of the filename as seen within the e-mail
            owns_file: (see class help) Should the file on disk be deleted
                if/when this database object is deleted?

        Returns:
            a :class:`EmailAttachment`

        """
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
    """
    Django signal receiver.

    Deletes files from filesystem when :class:`EmailAttachment` object is
    deleted, if its :attr:`owns_file` flag is set.
    """
    if instance.owns_file:
        auto_delete_files_on_instance_delete(instance, ['file'])


# noinspection PyUnusedLocal
@receiver(models.signals.pre_save, sender=EmailAttachment)
def auto_delete_emailattachment_files_on_change(sender: Type[EmailAttachment],
                                                instance: EmailAttachment,
                                                **kwargs: Any) -> None:
    """
    Django signal receiver.

    Deletes files from filesystem when :class:`EmailAttachment` object is
    changed, if its :attr:`owns_file` flag is set.
    """
    if instance.owns_file:
        auto_delete_files_on_instance_change(instance, ['file'],
                                             EmailAttachment)


class EmailTransmission(models.Model):
    """
    Represents an e-mail transmission attempt.
    """
    email = models.ForeignKey(Email, on_delete=models.PROTECT)
    at = models.DateTimeField(verbose_name="When sent", auto_now_add=True)
    by = models.ForeignKey(settings.AUTH_USER_MODEL,
                           on_delete=models.PROTECT,
                           null=True,
                           related_name="emailtransmissions")
    sent = models.BooleanField(default=False)
    failure_reason = models.TextField(verbose_name="Reason sending failed")

    def __str__(self) -> str:
        return "Email transmission at {} by {}: {}".format(
            self.at,
            self.by or "(system)",
            "success" if self.sent
            else f"failure: {self.failure_reason}"
        )


# =============================================================================
# A dummy set of objects, for template testing.
# Linked, so cross-references work.
# Don't save() them!
# =============================================================================

class DummyObjectCollection(object):
    """
    A collection of dummy objects within the consent-to-contact system, for
    testing templates.
    """
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
    Returns a collection of dummy objects, for testing consent-to-contact
    templates without using live patient data.

    Args:
        request: the :class:`django.http.request.HttpRequest`

    Returns:
        a :class:`DummyObjectCollection`

    We want to create these objects in memory, without saving to the DB.
    However, Django is less good at SQLAlchemy for this, and saves.

    - http://stackoverflow.com/questions/7908349/django-making-relationships-in-memory-without-saving-to-db  # noqa
    - https://code.djangoproject.com/ticket/17253
    - http://stackoverflow.com/questions/23372786/django-models-assigning-foreignkey-object-without-saving-to-database  # noqa
    - http://stackoverflow.com/questions/7121341/django-adding-objects-to-a-related-set-without-saving-to-db  # noqa

    A simple method works for an SQLite backend database but fails with
    an IntegrityError for MySQL/SQL Server. For example:

    .. code-block:: none

        IntegrityError at /draft_traffic_light_decision_form/-1/html/
        (1452, 'Cannot add or update a child row: a foreign key constraint
        fails (`crate_django`.`consent_study_researchers`, CONSTRAINT
        `consent_study_researchers_study_id_19bb255f_fk_consent_study_id`
        FOREIGN KEY (`study_id`) REFERENCES `consent_study` (`id`))')

    This occurs in the first creation, of a :class:`Study`, and only if you
    specify ``researchers``.

    The reason for the crash is that ``researchers`` is a ManyToManyField, and
    Django is trying to set the ``user.studies_as_researcher`` back-reference,
    but can't do so because the :class:`Study` doesn't have a PK yet.

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
    # log.critical(f"consent_mode_str: {consent_mode_str!r}")
    if consent_mode_str not in (None, ConsentMode.RED, ConsentMode.YELLOW,
                                ConsentMode.GREEN):
        consent_mode_str = None

    request_direct_approach = bool(get_int('request_direct_approach', 1))
    clinician_involvement = ContactRequest.get_clinician_involvement(
        consent_mode_str=consent_mode_str,
        request_direct_approach=request_direct_approach)

    consent_after_discharge = bool(get_int('consent_after_discharge', 0))

    nhs_number = 1234567890
    study_summary_plaintext = (
        "An investigation of the change in blood-oxygen-level-"
        "dependent (BOLD) functional magnetic resonance imaging "
        "(fMRI) signals during the experience of quaint and "
        "fanciful humorous activity.\n"
        "\n"
        "This is paragraph 2.\n"
        "\n"
        "For patients aged >18 and <65."
    )
    study_summary_html = """
        <p>An investigation of the change in <b>blood-oxygen-level-dependent
        (BOLD)</b> <i>functional magnetic resonance imaging (fMRI)</i> signals
        during the experience of quaint and fanciful humour activity.</p>
        
        <p>Now with extra HTML.</p>
        
        <p>For patients aged &gt;18 and &lt;65.</p> 
    """
    use_html = False
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
        summary=study_summary_html if use_html else study_summary_plaintext,
        summary_is_html=use_html,
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
