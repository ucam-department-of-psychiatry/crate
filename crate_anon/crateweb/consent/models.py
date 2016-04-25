#!/usr/bin/env python3
# crate_anon/crateweb/consent/models.py

import datetime
from dateutil.relativedelta import relativedelta
import logging
import os
# from audit_log.models import AuthStampedModel  # django-audit-log
from django import forms
from django.conf import settings
from django.core.exceptions import (
    MultipleObjectsReturned,
    ObjectDoesNotExist,
    ValidationError,
)
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.core.urlresolvers import reverse
from django.core.validators import validate_email
from django.db import connections, models, transaction
from django.db.models import Q
from django.dispatch import receiver
from django.http import QueryDict
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property
from crate_anon.crateweb.core.constants import (
    LEN_ADDRESS,
    LEN_FIELD_DESCRIPTION,
    LEN_NAME,
    LEN_PHONE,
    LEN_TITLE,
    MAX_HASH_LENGTH,
)
from crate_anon.crateweb.core.dbfunc import (
    dictfetchall,
    dictfetchone,
    fetchallfirstvalues,
)
from crate_anon.crateweb.core.utils import (
    get_friendly_date,
    get_initial_surname_tuple_from_string,
    modelrepr,
    site_absolute_url,
    string_time_now,
    url_with_querystring,
)
from crate_anon.crateweb.extra.admin import admin_view_url
from crate_anon.crateweb.extra.fields import (
    auto_delete_files_on_instance_change,
    auto_delete_files_on_instance_delete,
    choice_explanation,
    ContentTypeRestrictedFileField,
    # IsoDateTimeTzField,
)
from crate_anon.crateweb.extra.pdf import (
    get_concatenated_pdf_in_memory,
    pdf_from_html,
)
from crate_anon.crateweb.research.models import get_mpid
from crate_anon.crateweb.consent.storage import privatestorage
from crate_anon.crateweb.consent.tasks import (
    email_rdbm_task,
    process_contact_request,
)
from crate_anon.crateweb.consent.utils import (
    pdf_template_dict,
    validate_researcher_email_domain,
)

log = logging.getLogger(__name__)


# =============================================================================
# Study
# =============================================================================

def study_details_upload_to(instance, filename):
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


def study_form_upload_to(instance, filename):
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
        content_types=['application/pdf'],
        max_upload_size=settings.MAX_UPLOAD_SIZE_BYTES,
        upload_to=study_details_upload_to)
    subject_form_template_pdf = ContentTypeRestrictedFileField(
        blank=True,
        storage=privatestorage,
        content_types=['application/pdf'],
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

    def get_lead_researcher_name_address(self):
        return (
            [self.lead_researcher.profile.get_title_forename_surname()] +
            self.lead_researcher.profile.get_address_components()
        )

    def get_lead_researcher_salutation(self):
        return self.lead_researcher.profile.get_title_surname()

    def get_involves_lack_of_capacity(self):
        if not self.include_lack_capacity:
            return "No"
        if self.clinical_trial:
            return "Yes (and it is a clinical trial)"
        return "Yes (and it is not a clinical trial)"

    @staticmethod
    def filter_studies_for_researcher(queryset, user):
        return queryset.filter(Q(lead_researcher=user) |
                               Q(researchers__in=[user]))\
                       .distinct()


# noinspection PyUnusedLocal
@receiver(models.signals.post_delete, sender=Study)
def auto_delete_study_files_on_delete(sender, instance, **kwargs):
    """Deletes files from filesystem when Study object is deleted."""
    auto_delete_files_on_instance_delete(instance,
                                         Study.AUTODELETE_OLD_FILE_FIELDS)


# noinspection PyUnusedLocal
@receiver(models.signals.pre_save, sender=Study)
def auto_delete_study_files_on_change(sender, instance, **kwargs):
    """Deletes files from filesystem when Study object is changed."""
    auto_delete_files_on_instance_change(instance,
                                         Study.AUTODELETE_OLD_FILE_FIELDS,
                                         Study)


# =============================================================================
# Generic leaflets
# =============================================================================

def leaflet_upload_to(instance, filename):
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
    CPFT_TPIR = 'cpft_tpir'
    NIHR_YHRSL = 'nihr_yhrsl'
    CPFT_TRAFFICLIGHT_CHOICE = 'cpft_trafficlight_choice'
    CPFT_CLINRES = 'cpft_clinres'

    LEAFLET_CHOICES = (
        (CPFT_TPIR, 'CPFT: Taking part in research'),
        (NIHR_YHRSL, 'NIHR: Your health records save lives'),
        (CPFT_TRAFFICLIGHT_CHOICE, 'CPFT: traffic-light choice'),
        (CPFT_CLINRES, 'CPFT: clinical research'),
    )
    # https://docs.djangoproject.com/en/dev/ref/models/fields/#django.db.models.Field.choices  # noqa

    name = models.CharField(max_length=50, unique=True,
                            choices=LEAFLET_CHOICES,
                            verbose_name="leaflet name")
    pdf = ContentTypeRestrictedFileField(
        blank=True,
        storage=privatestorage,
        content_types=['application/pdf'],
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
    def populate():
        # Pre-create instances
        keys = [x[0] for x in Leaflet.LEAFLET_CHOICES]
        for x in keys:
            if not Leaflet.objects.filter(name=x).exists():
                obj = Leaflet(name=x)
                obj.save()


# noinspection PyUnusedLocal
@receiver(models.signals.post_delete, sender=Study)
def auto_delete_leaflet_files_on_delete(sender, instance, **kwargs):
    """Deletes files from filesystem when Leaflet object is deleted."""
    auto_delete_files_on_instance_delete(instance, ['pdf'])


# noinspection PyUnusedLocal
@receiver(models.signals.pre_save, sender=Study)
def auto_delete_leaflet_files_on_change(sender, instance, **kwargs):
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

    def decision_valid(self):
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

    def validate_decision(self):
        if not self.decision_valid():
            raise forms.ValidationError(
                "Invalid decision. Options are: "
                "(*) Signed/authorized by patient. "
                "(*) Lacks capacity - signed by rep + clinician. "
                "(*) Under 16 - signed by 2/3 of (patient, clinician, "
                "parent); see special rules")


# =============================================================================
# Record of consent mode for a patient
# =============================================================================

class ConsentMode(Decision):
    RED = 'red'
    YELLOW = 'yellow'
    GREEN = 'green'

    CONSENT_MODE_CHOICES = (
        (RED, 'red'),
        (YELLOW, 'yellow'),
        (GREEN, 'green'),
    )
    # ... http://stackoverflow.com/questions/12822847/best-practice-for-python-django-constants  # noqa

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
        verbose_name="Consent mode ('red', 'yellow', 'green')")
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

    # class Meta:
    #     get_latest_by = "created_at"

    def save(self, *args, **kwargs):
        """
        Custom save method.
        Ensures that only one Query has active == True for a given user.

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
    def get_or_create(cls, nhs_number, created_by):
        try:
            consent_mode = cls.objects.get(nhs_number=nhs_number,
                                           current=True)
        except cls.DoesNotExist:
            consent_mode = cls(nhs_number=nhs_number,
                               created_by=created_by,
                               current=True)
            consent_mode.save()
        return consent_mode

    def consider_withdrawal(self):
        """
        If required, withdraw consent for other studies.
        Call this before setting current=True and calling save().
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
        except ContactRequest.DoesNotExist:
            pass  # no previous ConsentMode; nothing to do.
        except ContactRequest.MultipleObjectsReturned:
            pass  # but this is a bug

    def get_latest_patient_lookup(self):
        return lookup_patient(self.nhs_number, existing_ok=True)

    def get_confirm_traffic_to_patient_letter_html(self):
        """
        REC DOCUMENT 07. Confirming patient's traffic-light choice.
        """
        patient_lookup = self.get_latest_patient_lookup()
        context = {
            # Letter bits
            'address_from': settings.RDBM_ADDRESS + [settings.RDBM_EMAIL],
            'address_to': patient_lookup.pt_name_address_components(),
            'salutation': patient_lookup.pt_title_surname_str(),
            'signatory_name': settings.RDBM_NAME,
            'signatory_title': settings.RDBM_TITLE,
            # Specific bits
            'consent_mode': self,
            'patient_lookup': patient_lookup,
            'settings': settings,
            # URLs
            'red_img_url': site_absolute_url(static('red.png')),
            'yellow_img_url': site_absolute_url(static('yellow.png')),
            'green_img_url': site_absolute_url(static('green.png')),
        }
        # 1. Building a static URL in code:
        #    http://stackoverflow.com/questions/11721818/django-get-the-static-files-url-in-view  # noqa
        # 2. Making it an absolute URL means that wkhtmltopdf will also see it
        #    (by fetching it from this web server).
        # 3. Works with Django testing server.
        # 4. Works with Apache, + proxying to backend, + SSL
        context.update(pdf_template_dict(patient=True))
        return render_to_string('letter_patient_confirm_traffic.html', context)

    def notify_rdbm_of_work(self, letter, to_researcher=False):
        subject = ("WORK FROM RESEARCH DATABASE COMPUTER"
                   " - consent mode {}".format(self.id))
        if to_researcher:
            template = 'email_rdbm_new_work_researcher.html'
        else:
            template = 'email_rdbm_new_work_pt_from_rdbm.html'
        html = render_to_string(template, {'letter': letter})
        email = Email.create_rdbm_email(subject, html)
        email.send()

    def process_change(self):
        """
        Called upon saving.
        Will create a letter to patient.
        May create a withdrawal-of-consent letter to researcher.
        """
        # noinspection PyTypeChecker
        letter = Letter.create_consent_confirmation_to_patient(self)
        # ... will save
        self.notify_rdbm_of_work(letter, to_researcher=False)
        self.consider_withdrawal()
        self.current = True  # will disable current flag for others
        self.save()


# =============================================================================
# Information about patient captured from clinical database
# =============================================================================

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

    # -------------------------------------------------------------------------
    # Patient
    # -------------------------------------------------------------------------

    def pt_title_surname_str(self):
        return " ".join(filter(None, [self.pt_title, self.pt_last_name]))

    def pt_title_forename_surname_str(self):
        return " ".join(filter(None, [self.pt_title, self.pt_first_name,
                                      self.pt_last_name]))

    def pt_forename_surname_str(self):
        return " ".join(filter(None, [self.pt_first_name, self.pt_last_name]))

    def pt_address_components(self):
        return list(filter(None, [
            self.pt_address_1,
            self.pt_address_2,
            self.pt_address_3,
            self.pt_address_4,
            self.pt_address_5,
            self.pt_address_6,
            self.pt_address_7,
        ]))

    def pt_address_components_str(self):
        return ", ".join(filter(None, self.pt_address_components()))

    def pt_name_address_components(self):
        return [
            self.pt_title_forename_surname_str()
        ] + self.pt_address_components()

    def get_id_numbers_html_bold(self):
        idnums = ["NHS#: {}".format(self.nhs_number)]
        if self.pt_local_id_description:
            idnums.append("{}: {}".format(self.pt_local_id_description,
                                          self.pt_local_id_number))
        return ". ".join(idnums)

    def get_pt_age_years(self):
        if self.pt_dob is None:
            return None
        now = datetime.datetime.now()  # timezone-naive
        # now = timezone.now()  # timezone-aware
        return relativedelta(now, self.pt_dob).years

    def is_under_16(self):
        age = self.get_pt_age_years()
        return age is not None and age < 16

    def is_under_15(self):
        age = self.get_pt_age_years()
        return age is not None and age < 15

    # -------------------------------------------------------------------------
    # GP
    # -------------------------------------------------------------------------

    def gp_title_forename_surname_str(self):
        return " ".join(filter(None, [self.gp_title, self.gp_first_name,
                                      self.gp_last_name]))

    def gp_address_components(self):
        return list(filter(None, [
            self.gp_address_1,
            self.gp_address_2,
            self.gp_address_3,
            self.gp_address_4,
            self.gp_address_5,
            self.gp_address_6,
            self.gp_address_7,
        ]))

    def gp_address_components_str(self):
        return ", ".join(self.gp_address_components())

    def gp_name_address_str(self):
        return ", ".join(filter(None, [self.gp_title_forename_surname_str(),
                                       self.gp_address_components_str()]))

    # noinspection PyUnusedLocal
    def set_gp_name_components(self, name, decisions, secret_decisions):
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

    def clinician_title_surname_str(self):
        return " ".join(filter(None, [self.clinician_title,
                                      self.clinician_last_name]))

    def clinician_title_forename_surname_str(self):
        return " ".join(filter(None, [self.clinician_title,
                                      self.clinician_first_name,
                                      self.clinician_last_name]))

    def clinician_address_components(self):
        return [
            self.clinician_address_1,
            self.clinician_address_2,
            self.clinician_address_3,
            self.clinician_address_4,
            self.clinician_address_5,
            self.clinician_address_6,
            self.clinician_address_7,
        ]

    def clinician_address_components_str(self):
        return ", ".join(filter(None, self.clinician_address_components()))

    def clinician_name_address_str(self):
        return ", ".join(filter(None, [
            self.clinician_title_forename_surname_str(),
            self.clinician_address_components_str()]))


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

    Inherits from DummyPatientSourceInfo so it has the same fields, and more.
    """

    DUMMY_CLINICAL = 'dummy_clinical'
    CPFT_IAPT = 'cpft_iapt'
    CPFT_CRS = 'cpft_crs'
    CPFT_RIO = 'cpft_rio'
    DATABASE_CHOICES = (
        # First key must match a database entry in Django local settings.
        (DUMMY_CLINICAL, 'Dummy clinical database for testing'),
        # (CPFT_IAPT, 'CPFT IAPT'),
        (CPFT_CRS, 'CPFT Care Records System (CRS) 2005-2012'),
        (CPFT_RIO, 'CPFT RiO 2013-'),
    )

    nhs_number = models.BigIntegerField(
        verbose_name="NHS number used for lookup")
    lookup_at = models.DateTimeField(
        verbose_name="When fetched from clinical database",
        auto_now_add=True)

    # Information going in
    source_db = models.CharField(
        max_length=20, choices=DATABASE_CHOICES,
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

    def get_first_traffic_light_letter_html(self):
        """
        REC DOCUMENT 06. Covering letter to patient for first enquiry about
        research preference
        """
        context = {
            # Letter bits
            'address_from': self.clinician_address_components(),
            'address_to': self.pt_name_address_components(),
            'salutation': self.pt_title_surname_str(),
            'signatory_name': self.clinician_title_forename_surname_str(),
            'signatory_title': self.clinician_signatory_title,
            # Specific bits
            'settings': settings,
            'patient_lookup': self,
        }
        context.update(pdf_template_dict(patient=True))
        return render_to_string('letter_patient_first_traffic_light.html',
                                context)


def make_cpft_email_address(forename, surname):
    if not forename or not surname:  # in case one is None
        return None
    forename = forename.replace(" ", "")
    surname = forename.replace(" ", "")
    if not forename or not surname:  # in case one is empty
        return None
    if len(forename) == 1:
        # Initial only; that won't do.
        return None
    return "{}.{}@cpft.nhs.uk".format(forename, surname)


def lookup_patient(nhs_number, source_db=None, save=True,
                   existing_ok=False):
    if source_db is None:
        source_db = settings.CLINICAL_LOOKUP_DB
    if source_db not in [x[0] for x in PatientLookup.DATABASE_CHOICES]:
        raise ValueError("Bad source_db: {}".format(source_db))
    if existing_ok:
        try:
            lookup = PatientLookup.objects.filter(nhs_number=nhs_number)\
                                          .latest('lookup_at')
            return lookup
        except PatientLookup.DoesNotExist:
            # No existing lookup, so proceed to do it properly (below).
            pass
    lookup = PatientLookup(nhs_number=nhs_number,
                           source_db=source_db)
    decisions = []
    secret_decisions = []
    if source_db == "dummy_clinical":
        lookup_dummy_clinical(lookup, decisions, secret_decisions)
    # elif source_db == "cpft_iapt":
    #     lookup_cpft_iapt(lookup, decisions, secret_decisions)
    elif source_db == "cpft_crs":
        lookup_cpft_crs(lookup, decisions, secret_decisions)
    elif source_db == "cpft_rio":
        lookup_cpft_rio(lookup, decisions, secret_decisions)
    else:
        raise AssertionError("Bug in lookup_patient")
    lookup.decisions = " ".join(decisions)
    lookup.secret_decisions = " ".join(secret_decisions)
    if save:
        lookup.save()
    return lookup


# noinspection PyUnusedLocal
def lookup_dummy_clinical(lookup, decisions, secret_decisions):
    try:
        dummylookup = DummyPatientSourceInfo.objects.get(
            nhs_number=lookup.nhs_number)
    except ObjectDoesNotExist:
        decisions.append("Patient not found in dummy lookup")
        return
    # noinspection PyProtectedMember
    fieldnames = [f.name for f in PatientLookupBase._meta.get_fields()]
    for fieldname in fieldnames:
        setattr(lookup, fieldname, getattr(dummylookup, fieldname))
    lookup.pt_found = True
    lookup.gp_found = True
    lookup.clinician_found = True
    decisions.append("Copying all information from dummy lookup")


def lookup_cpft_rio(lookup, decisions, secret_decisions):
    """
    ---------------------------------------------------------------------------
    RiO notes, 2015-05-19
    ---------------------------------------------------------------------------
    For speed, RiO needs these indexes:

    CREATE INDEX _idx_cdd_nhs ON Client_Demographic_Details (NHS_Number);
    CREATE INDEX _idx_cnh_id ON Client_Name_History (Client_ID);
    CREATE INDEX _idx_cnh_eff ON Client_Name_History (Effective_Date);
    CREATE INDEX _idx_cnh_end ON Client_Name_History (End_Date_);
    CREATE INDEX _idx_cah_id ON Client_Address_History (Client_ID);
    CREATE INDEX _idx_cah_from ON Client_Address_History (Address_From_Date);
    CREATE INDEX _idx_cah_to ON Client_Address_History (Address_To_Date);
    CREATE INDEX _idx_cgh_id ON Client_GP_History (Client_ID);
    CREATE INDEX _idx_cgh_from ON Client_GP_History (GP_From_Date);
    CREATE INDEX _idx_cgh_to ON Client_GP_History (GP_To_Date);
    CREATE INDEX _idx_cc_id ON CPA_CareCoordinator (Client_ID);
    CREATE INDEX _idx_cc_start ON CPA_CareCoordinator (Start_Date);
    CREATE INDEX _idx_cc_end ON CPA_CareCoordinator (End_Date);
    CREATE INDEX _idx_ref_id ON Main_Referral_Data (Client_ID);
    CREATE INDEX _idx_ref_recv ON Main_Referral_Data (Referral_Received_Date);
    CREATE INDEX _idx_ref_removal ON Main_Referral_Data (Removal_DateTime);
    CREATE INDEX _idx_rsh_id ON Referral_Staff_History (Client_ID);
    CREATE INDEX _idx_rsh_start ON Referral_Staff_History (Start_Date);
    CREATE INDEX _idx_rsh_end ON Referral_Staff_History (End_Date);
    CREATE INDEX _idx_rth_id ON Referral_Team_History (Client_ID);
    CREATE INDEX _idx_rth_start ON Referral_Team_History (Start_Date);
    CREATE INDEX _idx_rth_end ON Referral_Team_History (End_Date);
    CREATE INDEX _idx_rth_teamdesc ON Referral_Team_History (Team_Description);

    Main:
      Client_Demographic_Details
          Client_ID -- PK; RiO number; integer in VARCHAR(15) field
          Date_of_Birth -- DATETIME
          Date_of_Death -- DATETIME; NULL if not dead
          Death_Flag -- INT; 0 for alive, 1 for dead
          Deleted_Flag -- INT; 0 normally; 1 for deleted
          NHS_Number -- CHAR(10)
          Gender_Code -- 'F', 'M', 'U', 'X'
          Gender_Description -- 'Male', 'Female', ...

    Then, linked to it:

      Client_Name_History
          Client_ID -- integer in VARCHAR(15)
          Effective_Date -- DATETIME
          End_Date_  -- DATETIME, typically NULL
          Name_Type_Code  -- '1' for 'usual name', '2' for 'Alias', '3'
              for 'Preferred name', '4' for 'Birth name', '5' for
              'Maiden name', '7' for 'Other', 'CM' for 'Client Merge';
              NVARCHAR(10)
          Name_Type_Description  -- e.g. 'Usual name', 'Alias'
          Deleted_Flag -- INT

          title
          Given_Name_1  -- through to Given_Name_5
          Family_Name
          suffix
          ...

      Client_Address_History
          Client_ID -- integer in VARCHAR(15)
          Address_Type_Code -- e.g. 'PRIMARY' but also 'CA', 'FCH'...
          Address_Type_Description
          Address_From_Date -- DATETIME
          Address_To_Date -- DATETIME; NULL for active ones

          Address_Line_1
          Address_Line_2
          Address_Line_3
          Address_Line_4
          Address_Line_5
          Post_Code
          ... -- no e-mail address field

      Client_GP_History
          Client_ID -- integer in VARCHAR(15)
          GP_From_Date -- DATETIME
          GP_To_Date -- DATETIME; NULL for active ones

          GP_Name -- e.g. 'Smith JT'
          GP_Practice_Address_Line1
          GP_Practice_Address_Line2
          GP_Practice_Address_Line3
          GP_Practice_Address_Line4
          GP_Practice_Address_Line5
          GP_Practice_Post_code
          ...

    CPFT clinician details/?discharged info appear to be here:

      CPA_CareCoordinator
          Client_ID -- integer in VARCHAR(15)
          Start_Date -- DATETIME
          End_Date -- DATETIME
          End_Reason_Code
          End_Reason_Description
          End_Reason_National_Code

          Care_Coordinator_User_title
          Care_Coordinator_User_first_name
          Care_Coordinator_User_surname
          Care_Coordinator_User_email
          Care_Coordinator_User_Consultant_Flag -- INT; 0 or 1 (or NULL?)

      Main_Referral_Data
          Client_ID -- integer in VARCHAR(15)
          Referral_Received_Date -- DATETIME
          Removal_DateTime -- DATETIME
          # Care_Spell_Start_Date
          # Care_Spell_End_Date -- never non-NULL in our data set
          # Discharge_HCP -- ??user closing the referral

          Referred_Consultant_User_title
          Referred_Consultant_User_first_name
          Referred_Consultant_User_surname
          Referred_Consultant_User_email
          Referred_Consultant_User_Consultant_Flag  -- 0, 1, NULL

      Referral_Staff_History
          Client_ID -- integer in VARCHAR(15)
          Start_Date -- DATETIME
          End_Date -- DATETIME
          Current_At_Discharge -- INT -- ? -- 1 or NULL

          HCP_User_title
          HCP_User_first_name
          HCP_User_surname
          HCP_User_email
          HCP_User_Consultant_Flag  -- 0, 1, NULL

      Referral_Team_History
              -- similar, but for teams; no individual info
          Client_ID -- integer in VARCHAR(15)
          Start_Date -- DATETIME
          End_Date -- DATETIME
          Current_At_Discharge -- INT -- ? -- 1 or NULL

          Team_Code -- NVARCHAR -- e.g. 'TCGMH712'
          Team_Description -- NVARCHAR -- e.g. 'George Mackenzie'
          Team_Classification_Group_Code -- NVARCHAR -- e.g. 'FS'
          Team_Classification_Group_Description -- NVARCHAR -- e.g.
                                                          'Forensic Service'

    Not obviously relevant:

      Client_CPA -- records CPA start/end, etc.
      Client_Professional_Contacts -- empty table!

    Note in passing, but not used:

      Client_Communications_History -- email/phone
          Client_ID -- integer in VARCHAR(15)
          Method_Code -- NVARCHAR(10); '1' for 'Telephone number', '3'
              for 'Email address', '4' for 'Minicom/textphone number'
          Method_Description
          Context_Code -- e.g. '1' for 'Communication address at home',
              other codes for 'Vacation home...', etc.
          Context_Description
          Contact_Details -- NVARCHAR(80)

    """
    cursor = connections[lookup.source_db].cursor()
    # -------------------------------------------------------------------------
    # RiO 1. Get RiO PK
    # -------------------------------------------------------------------------
    cursor.execute(
        """
            SELECT
                Client_ID, -- RiO number (PK)
                -- NHS_Number,
                Date_of_Birth,
                Date_of_Death,
                Death_Flag,
                -- Deleted_Flag,
                Gender_Code
                -- Gender_Description,
            FROM Client_Demographic_Details
            WHERE
                NHS_Number = %s -- CHAR comparison
                AND NOT Deleted_Flag
        """,
        [str(lookup.nhs_number)]
    )
    rows = dictfetchall(cursor)
    if not rows:
        decisions.append(
            "NHS number not found in Client_Demographic_Details table.")
        return
    if len(rows) > 1:
        decisions.append("Two patients found with that NHS number; aborting.")
        return
    row = rows[0]
    rio_client_id = row['Client_ID']
    lookup.pt_local_id_description = "CPFT RiO number"
    lookup.pt_local_id_number = rio_client_id
    secret_decisions.append("RiO number: {}.".format(rio_client_id))
    lookup.pt_dob = row['Date_of_Birth']
    lookup.pt_dod = row['Date_of_Death']
    lookup.pt_dead = bool(lookup.pt_dod or row['Death_Flag'])
    lookup.pt_sex = "?" if row['Gender_Code'] == "U" else row['Gender_Code']
    # -------------------------------------------------------------------------
    # RiO 2. Name
    # -------------------------------------------------------------------------
    cursor.execute(
        """
            SELECT
                title,
                Given_Name_1,
                Family_Name
            FROM Client_Name_History
            WHERE
                Client_ID = %s
                AND Effective_Date <= GETDATE()
                AND (End_Date_ IS NULL OR End_Date_ > GETDATE())
                AND (Deleted_Flag IS NULL OR Deleted_Flag = 0)
            ORDER BY Name_Type_Code
        """,
        [rio_client_id]
    )
    row = dictfetchone(cursor)
    if not row:
        decisions.append(
            "No name/address information found in Client_Name_History.")
        return
    lookup.pt_found = True
    lookup.pt_title = row['title'] or ''
    lookup.pt_first_name = row['Given_Name_1'] or ''
    lookup.pt_last_name = row['Family_Name'] or ''
    # Deal with dodgy case
    lookup.pt_title = lookup.pt_title.title()
    lookup.pt_first_name = lookup.pt_first_name.title()
    lookup.pt_last_name = lookup.pt_last_name.title()
    # -------------------------------------------------------------------------
    # RiO 3. Address
    # -------------------------------------------------------------------------
    cursor.execute(
        """
            SELECT
                Address_Line_1,
                Address_Line_2,
                Address_Line_3,
                Address_Line_4,
                Address_Line_5,
                Post_Code
            FROM Client_Address_History
            WHERE
                Client_ID = %s
                AND Address_From_Date <= GETDATE()
                AND (Address_To_Date IS NULL
                     OR Address_To_Date > GETDATE())
            ORDER BY CASE WHEN Address_Type_Code = 'PRIMARY' THEN '1'
                          ELSE Address_Type_Code END ASC
        """,
        [rio_client_id]
    )
    row = dictfetchone(cursor)
    if not row:
        decisions.append("No address found in Client_Address_History table.")
    else:
        lookup.pt_address_1 = row['Address_Line_1'] or ''
        lookup.pt_address_2 = row['Address_Line_2'] or ''
        lookup.pt_address_3 = row['Address_Line_3'] or ''
        lookup.pt_address_4 = row['Address_Line_4'] or ''
        lookup.pt_address_5 = row['Address_Line_5'] or ''
        lookup.pt_address_6 = row['Post_Code'] or ''
    # -------------------------------------------------------------------------
    # RiO 4. GP
    # -------------------------------------------------------------------------
    cursor.execute(
        """
            SELECT
                GP_Name,
                GP_Practice_Address_Line1,
                GP_Practice_Address_Line2,
                GP_Practice_Address_Line3,
                GP_Practice_Address_Line4,
                GP_Practice_Address_Line5,
                GP_Practice_Post_code
            FROM Client_GP_History
            WHERE
                Client_ID = %s
                AND GP_From_Date <= GETDATE()
                AND (GP_To_Date IS NULL OR GP_To_Date > GETDATE())
        """,
        [rio_client_id]
    )
    row = dictfetchone(cursor)
    if not row:
        decisions.append("No GP found in Client_GP_History table.")
    else:
        lookup.gp_found = True
        lookup.set_gp_name_components(row['GP_Name'] or '',
                                      decisions, secret_decisions)
        lookup.gp_address_1 = row['GP_Practice_Address_Line1'] or ''
        lookup.gp_address_2 = row['GP_Practice_Address_Line2'] or ''
        lookup.gp_address_3 = row['GP_Practice_Address_Line3'] or ''
        lookup.gp_address_4 = row['GP_Practice_Address_Line4'] or ''
        lookup.gp_address_5 = row['GP_Practice_Address_Line5'] or ''
        lookup.gp_address_6 = row['GP_Practice_Post_code']
    # -------------------------------------------------------------------------
    # RiO 5. Clinician.
    # -------------------------------------------------------------------------
    # This bit is complicated! We do it last, so we can return upon success.
    lookup.pt_discharged = True  # assume this; may change
    #
    # (a) Active care coordinator?
    #
    cursor.execute(
        """
            SELECT
                Care_Coordinator_User_title,
                Care_Coordinator_User_first_name,
                Care_Coordinator_User_surname,
                Care_Coordinator_User_email,
                Care_Coordinator_User_Consultant_Flag,
                Start_Date
            FROM CPA_CareCoordinator
            WHERE
                Client_ID = %s
                AND Start_Date <= GETDATE()
                AND (End_Date IS NULL OR End_Date > GETDATE())
            ORDER BY Start_Date ASC
        """,
        [rio_client_id]
    )
    row = dictfetchone(cursor)
    if row:
        lookup.pt_discharged = False
        decisions.append("Active care coordinator.")
    if row and row['Care_Coordinator_User_surname']:
        decisions.append(
            "Active care coordinator ({}).".format(
                get_friendly_date(row['Start_Date'])
            )
        )
        lookup.clinician_found = True
        lookup.clinician_title = row['Care_Coordinator_User_title'] or ''
        lookup.clinician_first_name = \
            row['Care_Coordinator_User_first_name'] or ''
        lookup.clinician_last_name = row['Care_Coordinator_User_surname'] or ''
        lookup.clinician_email = row['Care_Coordinator_User_email'] or ''
        lookup.clinician_is_consultant = bool(
            row['Care_Coordinator_User_Consultant_Flag'])
        lookup.clinician_signatory_title = "Care coordinator"
        return
    decisions.append("No active named care coordinator.")
    #
    # (b) Active named consultant referral?
    #
    cursor.execute(
        """
            SELECT
                Referred_Consultant_User_title,
                Referred_Consultant_User_first_name,
                Referred_Consultant_User_surname,
                Referred_Consultant_User_email,
                Referred_Consultant_User_Consultant_Flag,
                Referral_Received_Date
            FROM Main_Referral_Data
            WHERE
                Client_ID = %s
                AND Referral_Received_Date <= GETDATE()
                AND (Removal_DateTime IS NULL
                     OR Removal_DateTime > GETDATE())
            ORDER BY Referral_Received_Date ASC
        """,
        [rio_client_id]
    )
    row = dictfetchone(cursor)
    if row:
        lookup.pt_discharged = False
        decisions.append("Active consultant referral.")
    if row and row['Referred_Consultant_User_surname']:
        decisions.append(
            "Active named consultant referral ({}).".format(
                get_friendly_date(row['Referral_Received_Date'])
            )
        )
        lookup.clinician_found = True
        lookup.clinician_title = row['Referred_Consultant_User_title'] or ''
        lookup.clinician_first_name = \
            row['Referred_Consultant_User_first_name'] or ''
        lookup.clinician_last_name = \
            row['Referred_Consultant_User_surname'] or ''
        lookup.clinician_email = row['Referred_Consultant_User_email'] or ''
        lookup.clinician_is_consultant = \
            bool(row['Referred_Consultant_User_Consultant_Flag'])
        # ... would be odd if this were not true!
        lookup.clinician_signatory_title = "Consultant psychiatrist"
        return
    decisions.append("No active named consultant referral.")
    #
    # (c) Active other named staff referral?
    #
    cursor.execute(
        """
            SELECT
                HCP_User_title,
                HCP_User_first_name,
                HCP_User_surname,
                HCP_User_email,
                HCP_User_Consultant_Flag,
                Start_Date
            FROM Referral_Staff_History
            WHERE
                Client_ID = %s
                AND Start_Date <= GETDATE()
                AND (End_Date IS NULL OR End_Date > GETDATE())
            ORDER BY Start_Date ASC
        """,
        [rio_client_id]
    )
    row = dictfetchone(cursor)
    if row:
        lookup.pt_discharged = False
        decisions.append("Active HCP referral.")
    if row and row['Referred_Consultant_User_surname']:
        decisions.append(
            "Active named HCP referral ({}).".format(
                get_friendly_date(row['Start_Date'])
            )
        )
        lookup.clinician_found = True
        lookup.clinician_title = row['HCP_User_title'] or ''
        lookup.clinician_first_name = row['HCP_User_first_name'] or ''
        lookup.clinician_last_name = row['HCP_User_surname'] or ''
        lookup.clinician_email = row['HCP_User_email'] or ''
        lookup.clinician_is_consultant = bool(row['HCP_User_Consultant_Flag'])
        lookup.clinician_signatory_title = "Clinician"
        return
    decisions.append("No active named HCP referral.")
    #
    # (d) Active team referral?
    #
    cursor.execute(
        """
            SELECT
                Team_Description,
                Start_Date
            FROM Referral_Team_History
            WHERE
                Client_ID = %s
                AND Start_Date <= GETDATE()
                AND (End_Date IS NULL OR End_Date > GETDATE())
            ORDER BY Start_Date ASC
        """,
        [rio_client_id]
    )
    row = dictfetchone(cursor)
    if row:
        lookup.pt_discharged = False
        # We know a team - do we have a team representative?
        team_description = row['Team_Description']
        startdate = row['Start_Date']
        decisions.append(
            "Active named team referral ({}, {}).".format(
                team_description,
                get_friendly_date(startdate)
            )
        )
        try:
            teamrep = TeamRep.objects.get(team=team_description)
            decisions.append("Clinical team representative found.")
            profile = teamrep.user.profile
            lookup.clinician_found = True
            lookup.clinician_title = profile.title
            lookup.clinician_first_name = teamrep.user.first_name
            lookup.clinician_last_name = teamrep.user.last_name
            lookup.clinician_email = teamrep.user.email
            lookup.clinician_is_consultant = profile.is_consultant
            lookup.clinician_signatory_title = profile.signatory_title
        except ObjectDoesNotExist:
            decisions.append("No team representative found.")
        except MultipleObjectsReturned:
            decisions.append("Confused: >1 team representative found")
    else:
        decisions.append("No active named team referral.")
    #
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Below here, the patient is discharged, but we still may have a contact.
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    #
    # (e) Previous care coordinator?
    #
    cursor.execute(
        """
            SELECT
                Care_Coordinator_User_title,
                Care_Coordinator_User_first_name,
                Care_Coordinator_User_surname,
                Care_Coordinator_User_email,
                Care_Coordinator_User_Consultant_Flag,
                Start_Date
            FROM CPA_CareCoordinator
            WHERE
                Client_ID = %s
                AND Start_Date <= GETDATE()
            ORDER BY End_Date DESC
        """,
        [rio_client_id]
    )
    row = dictfetchone(cursor)
    if row and row['Care_Coordinator_User_surname']:
        decisions.append(
            "Previous care coordinator ({}).".format(
                get_friendly_date(row['Start_Date'])
            )
        )
        lookup.clinician_found = True
        lookup.clinician_title = row['Care_Coordinator_User_title'] or ''
        lookup.clinician_first_name = \
            row['Care_Coordinator_User_first_name'] or ''
        lookup.clinician_last_name = row['Care_Coordinator_User_surname'] or ''
        lookup.clinician_email = row['Care_Coordinator_User_email'] or ''
        lookup.clinician_is_consultant = bool(
            row['Care_Coordinator_User_Consultant_Flag'])
        lookup.clinician_signatory_title = "Care coordinator"
        return
    decisions.append("No previous care coordinator.")
    #
    # (f) Previous named consultant referral?
    #
    cursor.execute(
        """
            SELECT
                Referred_Consultant_User_title,
                Referred_Consultant_User_first_name,
                Referred_Consultant_User_surname,
                Referred_Consultant_User_email,
                Referred_Consultant_User_Consultant_Flag,
                Referral_Received_Date
            FROM Main_Referral_Data
            WHERE
                Client_ID = %s
                AND Referral_Received_Date <= GETDATE()
            ORDER BY Removal_DateTime DESC
        """,
        [rio_client_id]
    )
    row = dictfetchone(cursor)
    if row and row['Referred_Consultant_User_surname']:
        decisions.append(
            "Previous named consultant referral ({}).".format(
                get_friendly_date(row['Referral_Received_Date'])
            )
        )
        lookup.clinician_found = True
        lookup.clinician_title = row['Referred_Consultant_User_title'] or ''
        lookup.clinician_first_name = \
            row['Referred_Consultant_User_first_name'] or ''
        lookup.clinician_last_name = \
            row['Referred_Consultant_User_surname'] or ''
        lookup.clinician_email = row['Referred_Consultant_User_email'] or ''
        lookup.clinician_is_consultant = \
            bool(row['Referred_Consultant_User_Consultant_Flag'])
        # ... would be odd if this were not true!
        lookup.clinician_signatory_title = "Consultant psychiatrist"
        return
    decisions.append("No previous named consultant referral.")
    #
    # (g) Previous other named staff referral?
    #
    cursor.execute(
        """
            SELECT
                HCP_User_title,
                HCP_User_first_name,
                HCP_User_surname,
                HCP_User_email,
                HCP_User_Consultant_Flag,
                Start_Date
            FROM Referral_Staff_History
            WHERE
                Client_ID = %s
                AND Start_Date <= GETDATE()
            ORDER BY End_Date DESC
        """,
        [rio_client_id]
    )
    row = dictfetchone(cursor)
    if row and row['Referred_Consultant_User_surname']:
        decisions.append(
            "Previous named HCP referral ({}).".format(
                get_friendly_date(row['Start_Date'])
            )
        )
        lookup.clinician_found = True
        lookup.clinician_title = row['HCP_User_title'] or ''
        lookup.clinician_first_name = row['HCP_User_first_name'] or ''
        lookup.clinician_last_name = row['HCP_User_surname'] or ''
        lookup.clinician_email = row['HCP_User_email'] or ''
        lookup.clinician_is_consultant = bool(row['HCP_User_Consultant_Flag'])
        lookup.clinician_signatory_title = "Clinician"
        return
    decisions.append("No previous named HCP referral.")
    #
    # (h) Previous team referral?
    #
    cursor.execute(
        """
            SELECT
                Team_Description,
                Start_Date
            FROM Referral_Team_History
            WHERE
                Client_ID = %s
                AND Start_Date <= GETDATE()
            ORDER BY End_Date DESC
        """,
        [rio_client_id]
    )
    row = dictfetchone(cursor)
    if row:
        # We know a team - do we have a team representative?
        team_description = row['Team_Description']
        startdate = row['Start_Date']
        decisions.append(
            "Previous named team referral ({}, {}).".format(
                team_description,
                get_friendly_date(startdate)
            )
        )
        try:
            teamrep = TeamRep.objects.get(team=team_description)
            decisions.append("Clinical team representative found.")
            profile = teamrep.user.profile
            lookup.clinician_found = True
            lookup.clinician_title = profile.title
            lookup.clinician_first_name = teamrep.user.first_name
            lookup.clinician_last_name = teamrep.user.last_name
            lookup.clinician_email = teamrep.user.email
            lookup.clinician_is_consultant = profile.is_consultant
            lookup.clinician_signatory_title = profile.signatory_title
        except ObjectDoesNotExist:
            decisions.append("No team representative found.")
        except MultipleObjectsReturned:
            decisions.append("Confused: >1 team representative found")
    else:
        decisions.append("No previous named team referral.")
    #
    # (i) no idea
    #
    decisions.append("Failed to establish clinician.")


def lookup_cpft_crs(lookup, decisions, secret_decisions):
    cursor = connections[lookup.source_db].cursor()
    # -------------------------------------------------------------------------
    # CRS 1. Fetch basic details
    # -------------------------------------------------------------------------
    # Incoming nhs_number will be a number. However, the database has a VARCHAR
    # field (nhs_identifier) that may include spaces. So we compare a
    # whitespace-stripped field to our value converted to a VARCHAR:
    #       WHERE REPLACE(nhs_identifier, ' ', '') = CAST(%s AS VARCHAR)
    # ... or the other way round:
    #       WHERE CAST(nhs_identifier AS BIGINT) = %s
    cursor.execute(
        """
            SELECT
                patient_id, -- M number (PK)
                -- nhs_identifier,
                title,
                forename,
                surname,
                gender,
                -- ethnicity,
                -- marital_status,
                -- religion,
                dttm_of_birth,
                dttm_of_death
            FROM mpi
            WHERE CAST(nhs_identifier AS BIGINT) = %s
        """,
        [lookup.nhs_number]
    )
    rows = dictfetchall(cursor)
    if not rows:
        decisions.append("NHS number not found in mpi table.")
        return
    if len(rows) > 1:
        decisions.append("Two patients found with that NHS number; aborting.")
        return
    row = rows[0]
    crs_patient_id = row['patient_id']
    lookup.pt_local_id_description = "CPFT M number"
    lookup.pt_local_id_number = crs_patient_id
    secret_decisions.append("CPFT M number: {}.".format(crs_patient_id))
    lookup.pt_found = True
    lookup.pt_title = row['title'] or ''
    lookup.pt_first_name = row['forename'] or ''
    lookup.pt_last_name = row['surname'] or ''
    lookup.pt_sex = row['gender'] or ''
    lookup.pt_dob = row['dttm_of_birth']
    lookup.pt_dod = row['dttm_of_death']
    lookup.pt_dead = bool(lookup.pt_dod)
    # Deal with dodgy case
    lookup.pt_title = lookup.pt_title.title()
    lookup.pt_first_name = lookup.pt_first_name.title()
    lookup.pt_last_name = lookup.pt_last_name.title()
    # -------------------------------------------------------------------------
    # CRS 2. Address
    # -------------------------------------------------------------------------
    cursor.execute(
        """
            SELECT
                -- document_id, -- PK
                address1,
                address2,
                address3,
                address4,
                postcode,
                email
                -- startdate
                -- enddate
                -- patient_id

            FROM Address
            WHERE
                patient_id = %s
                AND enddate IS NULL
        """,
        [crs_patient_id]
    )
    row = dictfetchone(cursor)
    if not row:
        decisions.append("No address found in Address table.")
    else:
        lookup.pt_address_1 = row['address1'] or ''
        lookup.pt_address_2 = row['address2'] or ''
        lookup.pt_address_3 = row['address3'] or ''
        lookup.pt_address_4 = row['address4'] or ''
        lookup.pt_address_6 = row['postcode'] or ''
        lookup.pt_email = row['email'] or ''
    # -------------------------------------------------------------------------
    # CRS 3. GP
    # -------------------------------------------------------------------------
    cursor.execute(
        """
            SELECT
                -- sourcesystempk,  # PK
                -- patient_id,  # FK
                -- national_gp_id,
                gpname,
                -- national_practice_id,
                practicename,
                address1,
                address2,
                address3,
                address4,
                address5,
                postcode,
                telno
                -- startdate,
                -- enddate,
            FROM PracticeGP
            WHERE
                patient_id = %s
                AND enddate IS NULL
        """,
        [crs_patient_id]
    )
    row = dictfetchone(cursor)
    if not row:
        decisions.append("No GP found in PracticeGP table.")
    else:
        lookup.gp_found = True
        lookup.set_gp_name_components(row['gpname'] or '',
                                      decisions, secret_decisions)
        lookup.gp_address_1 = row['practicename'] or ''
        lookup.gp_address_2 = row['address1'] or ''
        lookup.gp_address_3 = row['address2'] or ''
        lookup.gp_address_4 = row['address3'] or ''
        lookup.gp_address_5 = ", ".join([row['address4'] or '',
                                         row['address5'] or ''])
        lookup.gp_address_6 = row['postcode']
        lookup.gp_telephone = row['telno']
    # -------------------------------------------------------------------------
    # CRS 4. Clinician
    # -------------------------------------------------------------------------
    cursor.execute(
        """
            SELECT
                -- patient_id,  # PK
                -- trustarea,
                consultanttitle,
                consultantfirstname,
                consultantlastname,
                carecoordinatortitle,
                carecoordinatorfirstname,
                carecoordinatorlastname,
                carecoordinatoraddress1,
                carecoordinatoraddress2,
                carecoordinatoraddress3,
                carecoordinatortown,
                carecoordinatorcounty,
                carecoordinatorpostcode,
                carecoordinatoremailaddress,
                carecoordinatormobilenumber,
                carecoordinatorlandlinenumber
            FROM CDLPatient
            WHERE
                patient_id = %s
        """,
        [crs_patient_id]
    )
    row = dictfetchone(cursor)
    if not row:
        decisions.append("No clinician info found in CDLPatient table.")
    else:
        lookup.clinician_address_1 = row['carecoordinatoraddress1'] or ''
        lookup.clinician_address_2 = row['carecoordinatoraddress2'] or ''
        lookup.clinician_address_3 = row['carecoordinatoraddress3'] or ''
        lookup.clinician_address_4 = row['carecoordinatortown'] or ''
        lookup.clinician_address_5 = row['carecoordinatorcounty'] or ''
        lookup.clinician_address_6 = row['carecoordinatorpostcode'] or ''
        lookup.clinician_telephone = " / ".join([
            row['carecoordinatorlandlinenumber'] or '',
            row['carecoordinatormobilenumber'] or ''
        ])
        careco_email = (
            row['carecoordinatoremailaddress'] or make_cpft_email_address(
                row['carecoordinatorfirstname'],
                row['carecoordinatorlastname'])
        )
        cons_email = make_cpft_email_address(
            row['consultantfirstname'],
            row['consultantlastname'])
        if careco_email:
            # Use care coordinator information
            lookup.clinician_found = True
            lookup.clinician_title = row['carecoordinatortitle'] or ''
            lookup.clinician_first_name = row['carecoordinatorfirstname'] or ''
            lookup.clinician_last_name = row['carecoordinatorlastname'] or ''
            lookup.clinician_email = careco_email
            lookup.clinician_signatory_title = "Care coordinator"
            decisions.append("Clinician found: care coordinator (CDL).")
        elif cons_email:
            # Use consultant information
            lookup.clinician_found = True
            lookup.clinician_title = row['consultanttitle'] or ''
            lookup.clinician_first_name = row['consultantfirstname'] or ''
            lookup.clinician_last_name = row['consultantlastname'] or ''
            lookup.clinician_email = cons_email
            lookup.clinician_signatory_title = "Consultant psychiatrist"
            lookup.clinician_is_consultant = True
            decisions.append("Clinician found: consultant psychiatrist (CDL).")
        else:
            # Don't know
            decisions.append(
                "No/insufficient clinician information found (CDL).")


# =============================================================================
# Clinical team representative
# =============================================================================

class TeamInfo(object):
    """Class only exists to be able to use @cached_property."""
    @cached_property
    def teams(self):
        log.debug("Fetching/caching clinical teams")
        if settings.CLINICAL_LOOKUP_DB == 'cpft_rio':
            cursor = connections[settings.CLINICAL_LOOKUP_DB].cursor()
            cursor.execute("""
                SELECT DISTINCT Team_Description
                FROM Referral_Team_History
            """)
            return fetchallfirstvalues(cursor)
        elif settings.CLINICAL_LOOKUP_DB == 'dummy_clinical':
            return ["dummy_team_one", "dummy_team_two", "dummy_team_three"]
        else:
            return []

    @cached_property
    def team_choices(self):
        teams = self.teams
        return [(team, team) for team in teams]


team_info = TeamInfo()


class TeamRep(models.Model):
    team = models.CharField(max_length=LEN_NAME, unique=True,
                            choices=team_info.team_choices,
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
    study = models.ForeignKey(Study)
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
    def create(cls, request, study, request_direct_approach,
               lookup_nhs_number=None, lookup_rid=None, lookup_mrid=None):
        """Create a contact request and act on it."""
        # Create contact request
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

    def process_request(self):
        self.decisionlist = []
        self.process_request_inner()
        self.decisions = " ".join(self.decisionlist)
        self.processed = True
        self.save()

    def process_request_inner(self):
        """Act on a contact request and store the decisions made.
        The decisions parameter is a list that's appended to."""
        # Translate to an NHS number
        if self.lookup_nhs_number is not None:
            self.nhs_number = self.lookup_nhs_number
        elif self.lookup_rid is not None:
            self.nhs_number = get_mpid(rid=self.lookup_rid)
        elif self.lookup_mrid is not None:
            self.nhs_number = get_mpid(mrid=self.lookup_mrid)
        else:
            raise ValueError("No NHS number, RID, or MRID supplied.")
        # Look up patient details (afresh)
        self.patient_lookup = lookup_patient(self.nhs_number, save=True)
        # Establish consent mode (always do this to avoid NULL problem)
        self.consent_mode = ConsentMode.get_or_create(self.nhs_number,
                                                      self.request_by)
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
        # Discharged?
        if self.patient_lookup.pt_discharged:
            if not self.study.include_discharged:
                self.stop(
                    "patient is discharged and study not approved for that")
                return
            if self.consent_mode.consent_mode not in [ConsentMode.GREEN,
                                                      ConsentMode.YELLOW]:
                self.stop("patient is discharged and consent mode is not GREEN"
                          " or YELLOW")
                return
            if not self.consent_mode.consent_after_discharge:
                self.stop("patient is discharged and patient did not consent "
                          "to contact after discharge")
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
                self.decide(emailtransmission.failure_reason)
            except ValidationError:
                pass
            self.decide("Approval letter to researcher created and needs "
                        "printing")
            self.notify_rdbm_of_work(letter, to_researcher=True)
            return

        # All other routes are via clinician.

        # Let's be precise about why the clinician is involved.
        if not self.request_direct_approach:
            self.clinician_involvement = (
                ContactRequest.CLINICIAN_INVOLVEMENT_REQUESTED)
        elif self.consent_mode.consent_mode == ConsentMode.YELLOW:
            self.clinician_involvement = (
                ContactRequest.CLINICIAN_INVOLVEMENT_REQUIRED_YELLOW)
        else:
            # Only other possibility
            self.clinician_involvement = (
                ContactRequest.CLINICIAN_INVOLVEMENT_REQUIRED_UNKNOWN)

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
            validate_researcher_email_domain(clinician_emailaddr)
        except ValidationError:
            self.stop(
                "clinician e-mail ({}) is not in a permitted domain".format(
                    clinician_emailaddr))
            return

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

        # noinspection PyTypeChecker
        email = Email.create_clinician_email(self)
        # ... will also create a ClinicianResponse
        emailtransmission = email.send()
        if not emailtransmission.sent:
            self.decide(emailtransmission.failure_reason)
            self.stop("Failed to send e-mail to clinician at {}".format(
                clinician_emailaddr))
            # We don't set decided_send_to_clinician because this attempt has
            # failed, and we don't want to put anyone off trying again
            # immediately.
        self.decided_send_to_clinician = True
        self.decide(
            "Sent request to clinician at {}".format(clinician_emailaddr))

    def decide(self, msg):
        self.decisionlist.append(msg)

    def stop(self, msg):
        self.decide("Stopping: " + msg)
        self.decided_no_action = True

    def calc_approaches_in_past_year(self):
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

    def withdraw_consent(self):
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

    def get_permission_date(self):
        """When was the researcher given permission? Used for the letter
        withdrawing permission."""
        if self.decided_no_action:
            return None
        if self.decided_send_to_researcher:
            # Green route
            return self.created_at
        if self.decided_send_to_clinician:
            # Yellow route -> patient -> said yes
            if hasattr(self, 'patient_response'):
                if self.patient_response.response == PatientResponse.YES:
                    return self.patient_response.created_at
        return None

    def notify_rdbm_of_work(self, letter, to_researcher=False):
        subject = ("CHEERFUL WORK FROM RESEARCH DATABASE COMPUTER"
                   " - contact request {}".format(self.id))
        if to_researcher:
            template = 'email_rdbm_new_work_researcher.html'
        else:
            template = 'email_rdbm_new_work_pt_from_clinician.html'
        html = render_to_string(template, {'letter': letter})
        email = Email.create_rdbm_email(subject, html)
        email.send()

    def notify_rdbm_of_bad_progress(self):
        subject = ("INFO ONLY - clinician refused Research Database request"
                   " - contact request {}".format(self.id))
        html = render_to_string('email_rdbm_bad_progress.html', {
            'id': self.id,
            'response': self.clinician_response.response,
            'explanation': self.clinician_response.get_response_explanation(),
        })
        email = Email.create_rdbm_email(subject, html)
        email.send()

    def notify_rdbm_of_good_progress(self):
        subject = ("INFO ONLY - clinician agreed to Research Database request"
                   " - contact request {}".format(self.id))
        html = render_to_string('email_rdbm_good_progress.html', {
            'id': self.id,
            'response': self.clinician_response.response,
            'explanation': self.clinician_response.get_response_explanation(),
        })
        email = Email.create_rdbm_email(subject, html)
        email.send()

    def get_clinician_email_html(self, save=True):
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
        }
        return render_to_string('email_clinician.html', context)

    def get_approval_letter_html(self):
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
        }
        context.update(pdf_template_dict(patient=False))
        return render_to_string('letter_researcher_approve.html', context)

    def get_withdrawal_letter_html(self):
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
        context.update(pdf_template_dict(patient=False))
        return render_to_string('letter_researcher_withdraw.html', context)

    def get_approval_email_html(self):
        """Simple e-mail to researcher attaching letter."""
        context = {
            'contact_request': self,
            'study': self.study,
            'patient_lookup': self.patient_lookup,
            'consent_mode': self.consent_mode,
        }
        return render_to_string('email_researcher_approval.html', context)

    def get_withdrawal_email_html(self):
        """Simple e-mail to researcher attaching letter."""
        context = {
            'contact_request': self,
            'study': self.study,
            'patient_lookup': self.patient_lookup,
            'consent_mode': self.consent_mode,
        }
        return render_to_string('email_researcher_withdrawal.html', context)

    def get_letter_clinician_to_pt_re_study(self):
        """
        REC DOCUMENTS 10, 12, 14: draft letters from clinician to patient, with
        decision form.
        """
        patient_lookup = self.patient_lookup
        yellow = (self.clinician_involvement ==
                  ContactRequest.CLINICIAN_INVOLVEMENT_REQUIRED_YELLOW)
        context = {
            # Letter bits
            'address_from': patient_lookup.clinician_address_components(),
            'address_to': patient_lookup.pt_name_address_components(),
            'salutation': patient_lookup.pt_title_surname_str(),
            'signatory_name':
            patient_lookup.clinician_title_forename_surname_str(),
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
        context.update(pdf_template_dict(patient=True))
        return render_to_string('letter_patient_from_clinician_re_study.html',
                                context)

    def is_extra_form(self):
        study = self.study
        clinician_requested = not self.request_direct_approach
        extra_form = (clinician_requested and
                      study.subject_form_template_pdf.name)
        # log.debug("clinician_requested: {}".format(clinician_requested))
        # log.debug("extra_form: {}".format(extra_form))
        return extra_form

    def is_consent_mode_unknown(self):
        return not self.consent_mode.consent_mode

    def get_decision_form_to_pt_re_study(self):
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
        context.update(pdf_template_dict(patient=True))
        return render_to_string('decision_form_to_patient_re_study.html',
                                context)

    def get_clinician_pack_pdf(self):
        # Order should match letter...

        # Letter to patient from clinician
        html_or_filename_tuple_list = [('html', {
            'html': self.get_letter_clinician_to_pt_re_study()
        })]
        # Study details
        if self.study.study_details_pdf:
            html_or_filename_tuple_list.append(
                ('filename', self.study.study_details_pdf.path)
            )
        # Decision form about this study
        html_or_filename_tuple_list.append(('html', {
            'html': self.get_decision_form_to_pt_re_study()
        }))
        # Additional form for this study
        if self.is_extra_form():
            if self.study.subject_form_template_pdf:
                html_or_filename_tuple_list.append(
                    ('filename', self.study.subject_form_template_pdf.path)
                )
        # Traffic-light decision form, if consent mode unknown
        if self.is_consent_mode_unknown():
            try:
                leaflet = Leaflet.objects.get(
                    name=Leaflet.CPFT_TRAFFICLIGHT_CHOICE)
                html_or_filename_tuple_list.append(
                    ('filename', leaflet.pdf.path))
            except ObjectDoesNotExist:
                log.warn("Missing traffic-light leaflet!")
                email_rdbm_task.delay(
                    subject="ERROR FROM RESEARCH DATABASE COMPUTER",
                    text=(
                        "Missing traffic-light leaflet! Incomplete clinician "
                        "pack accessed for contact request {}.".format(
                            self.id)
                    )
                )
        # General info leaflet
        try:
            leaflet = Leaflet.objects.get(name=Leaflet.CPFT_TPIR)
            html_or_filename_tuple_list.append(('filename', leaflet.pdf.path))
        except ObjectDoesNotExist:
            log.warn("Missing taking-part-in-research leaflet!")
            email_rdbm_task.delay(
                subject="ERROR FROM RESEARCH DATABASE COMPUTER",
                text=(
                    "Missing taking-part-in-research leaflet! Incomplete "
                    "clinician pack accessed for contact request {}.".format(
                        self.id)
                )
            )
        return get_concatenated_pdf_in_memory(html_or_filename_tuple_list,
                                              start_recto=True)

    def get_mgr_admin_url(self):
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

    def get_response_explanation(self):
        # log.debug("get_response_explanation: {}".format(self.response))
        return choice_explanation(self.response, ClinicianResponse.RESPONSES)

    @classmethod
    def create(cls, contact_request, save=True):
        newtoken = get_random_string(ClinicianResponse.TOKEN_LENGTH_CHARS)
        # https://github.com/django/django/blob/master/django/utils/crypto.py#L51  # noqa
        clinician_response = cls(
            contact_request=contact_request,
            token=newtoken,
        )
        if save:
            clinician_response.save()
        return clinician_response

    def get_abs_url_path(self):
        rev = reverse('clinician_response', args=[self.id])
        url = site_absolute_url(rev)
        return url

    def get_common_querydict(self, email_choice):
        querydict = QueryDict(mutable=True)
        querydict['token'] = self.token
        querydict['email_choice'] = email_choice
        return querydict

    def get_abs_url(self, email_choice):
        path = self.get_abs_url_path()
        querydict = self.get_common_querydict(email_choice)
        return url_with_querystring(path, querydict)

    def get_abs_url_yes(self):
        return self.get_abs_url(ClinicianResponse.EMAIL_CHOICE_Y)

    def get_abs_url_no(self):
        return self.get_abs_url(ClinicianResponse.EMAIL_CHOICE_N)

    def get_abs_url_maybe(self):
        return self.get_abs_url(ClinicianResponse.EMAIL_CHOICE_TELL_ME_MORE)

    def __str__(self):
        return "[ClinicianResponse {}] ContactRequest {}".format(
            self.id,
            self.contact_request_id,
        )

    def finalize_a(self):
        """
        Call this when the clinician completes their response.
        Part A: immediate, for acknowledgement.
        """
        self.responded = True
        self.responded_at = timezone.now()
        self.charity_amount_due = settings.CHARITY_AMOUNT_CLINICIAN_RESPONSE
        self.save()

    def finalize_b(self):
        """
        Call this when the clinician completes their response.
        Part B: background.
        """
        if self.response == ClinicianResponse.RESPONSE_R:
            # noinspection PyTypeChecker
            letter = Letter.create_request_to_patient(
                self.contact_request, rdbm_may_view=True)
            # ... will save
            PatientResponse.create(self.contact_request)
            # ... will save
            self.contact_request.notify_rdbm_of_work(letter)
        elif self.response == ClinicianResponse.RESPONSE_A:
            # noinspection PyTypeChecker
            Letter.create_request_to_patient(
                self.contact_request, rdbm_may_view=False)
            # ... return value not used
            PatientResponse.create(self.contact_request)
            self.contact_request.notify_rdbm_of_good_progress()
        elif self.response in [ClinicianResponse.RESPONSE_B,
                               ClinicianResponse.RESPONSE_C,
                               ClinicianResponse.RESPONSE_D]:
            self.contact_request.notify_rdbm_of_bad_progress()
        self.save()


# =============================================================================
# Patient response
# =============================================================================

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
    def create(cls, contact_request):
        patient_response = cls(contact_request=contact_request)
        patient_response.save()
        return patient_response

    def process_response(self):
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
    def create(cls, basefilename, html=None, pdf=None,
               to_clinician=False, to_researcher=False, to_patient=False,
               rdbm_may_view=False, study=None, contact_request=None,
               debug_store_html=False):
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
            pdf_from_html(html,
                          header_html=None,
                          footer_html=None,
                          output_path=abs_filename)
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
    def create_researcher_approval(cls, contact_request):
        basefilename = "cr{}_res_approve_{}.pdf".format(
            contact_request.id,
            string_time_now(),
        )
        html = contact_request.get_approval_letter_html()
        return cls.create(basefilename,
                          html=html,
                          to_researcher=True,
                          study=contact_request.study,
                          contact_request=contact_request,
                          rdbm_may_view=True)

    @classmethod
    def create_researcher_withdrawal(cls, contact_request):
        basefilename = "cr{}_res_withdraw_{}.pdf".format(
            contact_request.id,
            string_time_now(),
        )
        html = contact_request.get_withdrawal_letter_html()
        return cls.create(basefilename,
                          html=html,
                          to_researcher=True,
                          study=contact_request.study,
                          contact_request=contact_request,
                          rdbm_may_view=True)

    @classmethod
    def create_request_to_patient(cls, contact_request,
                                  rdbm_may_view=False):
        basefilename = "cr{}_to_pt_{}.pdf".format(
            contact_request.id,
            string_time_now(),
        )
        pdf = contact_request.get_clinician_pack_pdf()
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
    def create_consent_confirmation_to_patient(cls, consent_mode):
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
def auto_delete_letter_files_on_delete(sender, instance, **kwargs):
    """Deletes files from filesystem when Letter object is deleted."""
    auto_delete_files_on_instance_delete(instance, ['pdf'])


# noinspection PyUnusedLocal
@receiver(models.signals.pre_save, sender=Letter)
def auto_delete_letter_files_on_change(sender, instance, **kwargs):
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
    def create_clinician_email(cls, contact_request):
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
    def create_researcher_approval_email(cls, contact_request, letter):
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
        EmailAttachment.create(email=email,
                               file=letter.pdf,
                               content_type="application/pdf")  # will save
        return email

    @classmethod
    def create_researcher_withdrawal_email(cls, contact_request, letter):
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
        EmailAttachment.create(email=email,
                               file=letter.pdf,
                               content_type="application/pdf")  # will save
        return email

    @classmethod
    def create_rdbm_email(cls, subject, html):
        email = cls(recipient=settings.RDBM_EMAIL,
                    subject=subject,
                    msg_html=html)
        email.save()
        return email

    @classmethod
    def create_rdbm_text_email(cls, subject, text):
        email = cls(recipient=settings.RDBM_EMAIL,
                    subject=subject,
                    msg_text=text)
        email.save()
        return email

    def has_been_sent(self):
        return self.emailtransmission_set.filter(sent=True).exists()

    def send(self, user=None, resend=False):
        if self.has_been_sent() and not resend:
            log.error("Trying to send e-mail twice: ID={}".format(self.id))
            return
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
                # Separate text/HTML
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

    def resend(self, user):
        return self.send(user=user, resend=True)


class EmailAttachment(models.Model):
    """E-mail attachment class that does NOT manage its own files, i.e. if
    the attachment object is deleted, the files won't be. Use this for
    referencing files already stored elsewhere in the database."""
    email = models.ForeignKey(Email)
    file = models.FileField(storage=privatestorage)
    sent_filename = models.CharField(null=True, max_length=255)
    content_type = models.CharField(null=True, max_length=255)
    owns_file = models.BooleanField(default=False)

    def exists(self):
        if not self.file:
            return False
        return os.path.isfile(self.file.path)

    def size(self):
        if not self.file:
            return 0
        return os.path.getsize(self.file.path)

    @classmethod
    def create(cls, email, file, content_type, sent_filename=None,
               owns_file=False):
        if sent_filename is None:
            sent_filename = os.path.basename(file.name)
        attachment = cls(email=email,
                         file=file,
                         sent_filename=sent_filename,
                         content_type=content_type,
                         owns_file=owns_file)
        attachment.save()
        return attachment


# noinspection PyUnusedLocal
@receiver(models.signals.post_delete, sender=EmailAttachment)
def auto_delete_emailattachment_files_on_delete(sender, instance, **kwargs):
    """Deletes files from filesystem when EmailAttachment object is deleted."""
    if instance.owns_file:
        auto_delete_files_on_instance_delete(instance, ['file'])


# noinspection PyUnusedLocal
@receiver(models.signals.pre_save, sender=EmailAttachment)
def auto_delete_emailattachment_files_on_change(sender, instance, **kwargs):
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
        return "{} by {}: {}".format(
            self.at,
            self.by or "(system)",
            "success" if self.sent
            else "failure: {}".format(self.failure_reason)
        )


# =============================================================================
# Testing an ISO-based millisecond-precision date/time field with timezone
# =============================================================================

# class BlibbleTest(models.Model):
#     at = IsoDateTimeTzField()
#
#     class Meta:
#         managed = True
#         db_table = 'consent_test'
#         verbose_name_plural = "no ideas"

"""
import logging
logging.basicConfig()
import datetime
import dateutil
import pytz
from django.utils import timezone
from consent.models import BlibbleTest

now = datetime.datetime.now(pytz.utc)
t = BlibbleTest(at=now)
time1 = dateutil.parser.parse("2015-11-11T22:21:37.000000+05:00")
t.save()
# BlibbleTest.objects.filter(at__lt=time1)

# Explicitly use transform:
BlibbleTest.objects.filter(at__utc=time1)
BlibbleTest.objects.filter(at__utc=now)
BlibbleTest.objects.filter(at__utcdate=time1)
BlibbleTest.objects.filter(at__utcdate=now)
BlibbleTest.objects.filter(at__sourcedate=time1)
BlibbleTest.objects.filter(at__sourcedate=now)

# Use 'exact' lookup
BlibbleTest.objects.filter(at=time1)
BlibbleTest.objects.filter(at=now)
"""
