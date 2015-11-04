#!/usr/bin/env python3
# consent/models.py

import datetime
from dateutil.relativedelta import relativedelta
import logging
logger = logging.getLogger(__name__)
import os
# from audit_log.models import AuthStampedModel  # django-audit-log
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.core.mail import EmailMessage, EmailMultiAlternatives
from django.db import connections, models
from django.db.models import Q
from django.dispatch import receiver
from django.utils import timezone
from django.utils.crypto import get_random_string
from django.utils.functional import cached_property
from core.constants import (
    LEN_ADDRESS,
    LEN_FIELD_DESCRIPTION,
    LEN_NAME,
    LEN_PHONE,
    LEN_TITLE,
    MAX_HASH_LENGTH,
)
from core.dbfunc import dictfetchall, dictfetchone, fetchallfirstvalues
from core.extra import (
    auto_delete_files_on_instance_change,
    auto_delete_files_on_instance_delete,
    ContentTypeRestrictedFileField,
)
from core.utils import (
    get_friendly_date,
    get_initial_surname_tuple_from_string,
    modelrepr,
)
from userprofile.models import get_or_create_user_profile
from .storage import privatestorage


# =============================================================================
# Record of sent e-mails
# =============================================================================

class Email(models.Model):
    # Let's not record host/port/user. It's configured into the settings.
    created_at = models.DateTimeField(verbose_name="When created (UTC)",
                                      auto_now_add=True)
    sender = models.CharField(max_length=255, default=settings.EMAIL_SENDER)
    recipient = models.CharField(max_length=255)
    subject = models.CharField(max_length=255)
    msg_text = models.TextField()
    msg_html = models.TextField()
    sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True,
                                   verbose_name="When sent (UTC)")
    failure_reason = models.TextField(verbose_name="Reason sending failed")
    # Other flags:
    to_clinician = models.BooleanField(default=False)
    to_researcher = models.BooleanField(default=False)
    to_patient = models.BooleanField(default=False)

    def __str__(self):
        return "<Email id={} to {}>".format(self.id, self.recipient)

    def send(self, resend=False):
        if self.sent_at and not resend:
            logger.error("Trying to send e-mail twice: ID={}".format(self.id))
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
                msg.send()
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
                path = attachment.file.path
                if not path:
                    continue
                if not attachment.sent_filename:
                    attachment.sent_filename = os.path.basename(path)
                    attachment.save()
                with open(path, 'rb') as f:
                    content = f.read()
                msg.attach(attachment.sent_filename,
                           content,
                           attachment.content_type or None)
            msg.send()
            self.sent = True
            self.sent_at = timezone.now()
            self.failure_reason = ''
        except Exception as e:
            self.sent = False
            self.sent_at = None
            self.failure_reason = str(e)
        self.save()


class EmailAttachment(models.Model):
    email = models.ForeignKey(Email)
    file = models.FileField(storage=privatestorage)
    sent_filename = models.CharField(null=True, max_length=255)
    content_type = models.CharField(null=True, max_length=255)

    def exists(self):
        logger.debug("testing existence of: {}".format(self.file.path))
        if not self.file.path:
            return False
        return os.path.isfile(self.file.path)

    def size(self):
        if not self.file.path:
            return 0
        return os.path.getsize(self.file.path)

# *** method for creation/file copying/filename setting

@receiver(models.signals.post_delete, sender=EmailAttachment)
def auto_delete_emailattachment_files_on_delete(sender, instance, **kwargs):
    """Deletes files from filesystem when EmailAttachment object is deleted."""
    auto_delete_files_on_instance_delete(instance, ['file'])


@receiver(models.signals.pre_save, sender=EmailAttachment)
def auto_delete_emailattachment_files_on_change(sender, instance, **kwargs):
    """Deletes files from filesystem when EmailAttachment object is changed."""
    auto_delete_files_on_instance_change(instance, ['file'], EmailAttachment)


# =============================================================================
# Letter, and record of letter being printed
# =============================================================================

class Letter(models.Model):
    created_at = models.DateTimeField(verbose_name="When created (UTC)",
                                      auto_now_add=True)
    pdf = models.FileField(storage=privatestorage)
    # Other flags:
    to_clinician = models.BooleanField(default=False)
    to_researcher = models.BooleanField(default=False)
    to_patient = models.BooleanField(default=False)


@receiver(models.signals.post_delete, sender=Letter)
def auto_delete_letter_files_on_delete(sender, instance, **kwargs):
    """Deletes files from filesystem when Letter object is deleted."""
    auto_delete_files_on_instance_delete(instance, ['pdf'])


@receiver(models.signals.pre_save, sender=Letter)
def auto_delete_letter_files_on_change(sender, instance, **kwargs):
    """Deletes files from filesystem when Letter object is changed."""
    auto_delete_files_on_instance_change(instance, ['pdf'], Letter)


class LetterPrinted(models.Model):
    letter = models.ForeignKey(Letter)
    printed_at = models.DateTimeField(verbose_name="When printed (UTC)",
                                      auto_now_add=True)


# =============================================================================
# Study
# =============================================================================

def string_time_now():
    """Returns current time in short-form ISO-8601 UTC, for filenames."""
    return timezone.now().strftime("%Y%m%dT%H%M%SZ")


def study_details_upload_to(instance, filename):
    """
    Determines the filename used for study information PDF uploads.
    instance = instance of Study (potentially unsaved)
        ... and you can't call save(); it goes into infinite recursion
    filename = uploaded filename
    """
    extension = os.path.splitext(filename)[1]  # includes the '.' if present
    return "study/{}_details_{}{}".format(
        instance.institutional_id,
        string_time_now(),
        extension)
    # ... as id may not exist yet


def study_form_upload_to(instance, filename):
    """
    Determines the filename used for study clinician-form PDF uploads.
    instance = instance of Study (potentially unsaved)
    filename = uploaded filename
    """
    extension = os.path.splitext(filename)[1]
    return "study/{}_form_{}{}".format(
        instance.institutional_id,
        string_time_now(),
        extension)


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
        return "[{}] {}: {} / {}".format(
            self.id,
            self.institutional_id,
            self.lead_researcher.get_full_name(),
            self.title
        )

    def get_involves_lack_of_capacity(self):
        if not self.include_lack_capacity:
            return "No"
        if self.clinical_trial:
            return "Yes (and it is a clinical trial)"
        return "Yes (and it is not a clinical trial)"


@receiver(models.signals.post_delete, sender=Study)
def auto_delete_study_files_on_delete(sender, instance, **kwargs):
    """Deletes files from filesystem when Study object is deleted."""
    auto_delete_files_on_instance_delete(instance,
                                         Study.AUTODELETE_OLD_FILE_FIELDS)


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
    return "leaflet/{}_{}{}".format(
        instance.name,
        string_time_now(),
        extension)
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
    def prepopulate():
        # Pre-create instances
        keys = [x[0] for x in Leaflet.LEAFLET_CHOICES]
        for x in keys:
            if not Leaflet.objects.filter(name=x).exists():
                obj = Leaflet(name=x)
                obj.save()


# Leaflet.prepopulate()   # *** move to data migration


@receiver(models.signals.post_delete, sender=Study)
def auto_delete_leaflet_files_on_delete(sender, instance, **kwargs):
    """Deletes files from filesystem when Leaflet object is deleted."""
    auto_delete_files_on_instance_delete(instance, ['pdf'])


@receiver(models.signals.pre_save, sender=Study)
def auto_delete_leaflet_files_on_change(sender, instance, **kwargs):
    """Deletes files from filesystem when Leaflet object is changed."""
    auto_delete_files_on_instance_change(instance, ['pdf'], Leaflet)


# =============================================================================
# Generic fields for decisions
# =============================================================================

class Decision(models.Model):
    decision_signed_by_patient = models.BooleanField(
        verbose_name="Request signed by patient?")
    decision_under16_signed_by_parent = models.BooleanField(
        verbose_name="Patient under 16 and request countersigned by parent?")
    decision_under16_signed_by_clinician = models.BooleanField(
        verbose_name="Patient under 16 and request countersigned by "
                     "clinician?")
    decision_lack_capacity_signed_by_representative = models.BooleanField(
        verbose_name="Patient lacked capacity and request signed by "
                     "authorized representative?")
    decision_lack_capacity_signed_by_clinician = models.BooleanField(
        verbose_name="Patient lacked capacity and request countersigned by "
                     "clinician?")

    class Meta:
        abstract = True

    def decision_valid(self, under16, lacks_capacity):
        if lacks_capacity:
            return (self.decision_lack_capacity_signed_by_representative
                    and self.decision_lack_capacity_signed_by_clinician)
        elif under16:
            return (self.decision_signed_by_patient
                    and (self.decision_under16_signed_by_parent
                         or self.decision_under16_signed_by_clinician))
        else:
            return self.decision_signed_by_patient


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
    current = models.BooleanField(default=True)  # see save() below
    created_at = models.DateTimeField(
        verbose_name="When was this record created (UTC)?",
        auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL)

    exclude_entirely = models.BooleanField(
        verbose_name="Exclude patient from Research Database entirely?")
    consent_mode = models.CharField(
        max_length=10, default="", choices=CONSENT_MODE_CHOICES,
        verbose_name="Consent mode ('red', 'yellow', 'green')")
    consent_after_discharge = models.BooleanField(
        verbose_name="Consent given to contact patient after discharge?")
    max_approaches_per_year = models.PositiveSmallIntegerField(
        verbose_name="Maximum number of approaches permissible per year "
                     "(0 = no limit)",
        default=0)
    other_requests = models.TextField(
        blank=True,
        verbose_name="Other special requests by patient")
    prefers_email = models.BooleanField(
        verbose_name="Patient prefers e-mail contact?")
    changed_by_clinician_override = models.BooleanField(
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
        return "[{}] NHS# {}, {}".format(
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
                               created_by=created_by)
            consent_mode.save()
        return consent_mode


# =============================================================================
# Information about patient captured from clinical database
# =============================================================================

class PatientLookupBase(models.Model):
    """
    Base class for PatientLookup and DummyPatientSourceInfo.
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
    pt_dead = models.BooleanField(verbose_name="Patient is dead")
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
    pt_telephone = models.CharField(max_length=LEN_PHONE,  blank=True,
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
    gp_telephone = models.CharField(max_length=LEN_PHONE,  blank=True,
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
        verbose_name="Clinician's title for signature")

    class Meta:
        abstract = True

    # -------------------------------------------------------------------------
    # Patient
    # -------------------------------------------------------------------------

    def pt_title_forename_surname_str(self):
        return " ".join(filter(None, [self.pt_title, self.pt_first_name,
                                      self.pt_last_name]))

    def pt_address_components(self):
        return [
            self.pt_address_1,
            self.pt_address_2,
            self.pt_address_3,
            self.pt_address_4,
            self.pt_address_5,
            self.pt_address_6,
            self.pt_address_7,
        ]

    def pt_address_components_str(self):
        return " ".join(filter(None, self.pt_address_components()))

    def get_id_numbers_html_bold(self):
        descriptions_numbers = self.get_id_descriptions_numbers()
        return " ".join(
            "{}: <b>{}</b>.".format(x[0], x[1])
            for x in descriptions_numbers
        )

    def get_pt_age_years(self):
        if self.pt_dob is None:
            return None
        return relativedelta(timezone.now(), self.pt_dob).years

    def is_under_16(self):
        age = self.get_pt_age_years()
        return age is not None and age < 16

    # -------------------------------------------------------------------------
    # GP
    # -------------------------------------------------------------------------

    def gp_title_forename_surname_str(self):
        return " ".join(filter(None, [self.gp_title, self.gp_first_name,
                                      self.gp_last_name]))

    def gp_address_components(self):
        return [
            self.gp_address_1,
            self.gp_address_2,
            self.gp_address_3,
            self.gp_address_4,
            self.gp_address_5,
            self.gp_address_6,
            self.gp_address_7,
        ]

    def gp_address_components_str(self):
        return " ".join(filter(None, self.gp_address_components()))

    def gp_name_address_str(self):
        return ", ".join(filter(None, [self.gp_title_forename_surname_str(),
                                       self.gp_address_components_str()]))

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

    def clinician_name_address_str(self):
        return ", ".join(filter(None, [
            self.clinician_title_forename_surname_str(),
            self.clinician_address_components()]))


class DummyPatientSourceInfo(PatientLookupBase):
    # Key
    nhs_number = models.BigIntegerField(verbose_name="NHS number",
                                        unique=True)

    class Meta:
        verbose_name_plural = "Dummy patient source information"


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
        verbose_name="When fetched from clinical database (UTC)",
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


def lookup_patient(nhs_number, source_db=None, save=True):
    if source_db is None:
        source_db = settings.CLINICAL_LOOKUP_DB
    if source_db not in [x[0] for x in PatientLookup.DATABASE_CHOICES]:
        raise ValueError("Bad source_db: {}".format(source_db))
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


def lookup_dummy_clinical(lookup, decisions, secret_decisions):
    dummylookup = DummyPatientSourceInfo.objects.get(
        nhs_number=lookup.nhs_number)
    fieldnames = PatientLookupBase._meta.get_all_field_names()
    for fieldname in fieldnames:
        setattr(lookup, fieldname, getattr(dummylookup, fieldname))
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
            profile = teamrep.get_profile()
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
            profile = teamrep.get_profile()
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
        logger.debug("Fetching/caching clinical teams")
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

    def get_profile(self):
        return get_or_create_user_profile(self.user)


# =============================================================================
# Record of payments to charity
# =============================================================================
# In passing - singleton objects:
#   http://goodcode.io/articles/django-singleton-models/

class CharityPaymentRecord(models.Model):
    created_at = models.DateTimeField(verbose_name="When created (UTC)",
                                      auto_now_add=True)
    payee = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=8, decimal_places=2)


# =============================================================================
# Request for patient contact
# =============================================================================

class ContactRequest(models.Model):
    CLINICIAN_INVOLVEMENT_REQUESTED = 0
    CLINICIAN_INVOLVEMENT_REQUIRED_YELLOW = 1
    CLINICIAN_INVOLVEMENT_REQUIRED_UNKNOWN = 2

    CLINICIAN_CONTACT_MODE_CHOICES = (
        (CLINICIAN_INVOLVEMENT_REQUESTED,
         'Clinician involvement requested by researchers'),
        (CLINICIAN_INVOLVEMENT_REQUIRED_YELLOW,
         'Clinician involvement required by YELLOW consent mode'),
        (CLINICIAN_INVOLVEMENT_REQUIRED_UNKNOWN,
         'Clinician involvement required by UNKNOWN consent mode'),
    )

    created_at = models.DateTimeField(verbose_name="When created (UTC)",
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
    # Those numbers translate to this:
    nhs_number = models.BigIntegerField(null=True, verbose_name="NHS number")
    # ... from which:
    patient_lookup = models.ForeignKey(PatientLookup)
    consent_mode = models.ForeignKey(ConsentMode)
    # Now decisions:
    approaches_in_past_year = models.PositiveIntegerField()
    decisions = models.TextField(
        blank=True, verbose_name="Decisions made")
    decided_no_action = models.BooleanField(default=False)
    decided_send_to_researcher = models.BooleanField(default=False)
    decided_send_to_clinician = models.BooleanField(default=False)
    clinician_involvement = models.PositiveSmallIntegerField(null=True)

    """


        "researcher_told",
        "researcher_told_datetime",
        "letter_to_researcher_id",
        "other_requests",
        "consent_withdrawal_notification_sent",
        "letter_withdrawing_consent_id",
        "initial_decisions_human_readable_msg"

    """

    def calc_approaches_in_past_year(self):
        # How best to count this?
        # Not by e.g. calendar year, with a flag that gets reset to zero
        # annually, because you might have a limit of 5, and get 4 requests in
        # Dec 2020 and then another 4 in Jan 2021 just after the flag resets.
        # Instead, we count the number of requests to that patient in the past
        # year.
        one_year_ago = timezone.now() - datetime.timedelta(days=365)

        self.approaches_in_past_year = ContactRequest.objects.filter(
            Q(decided_send_to_researcher=True)
            | (Q(decided_send_to_clinician=True)
               & Q(clinician_response__response=
                   ClinicianResponse.RESPONSE_A)),
            nhs_number=self.nhs_number,
            created_at__gte=one_year_ago
        ).count()
        
    @classmethod
    def create(cls, request, study, request_direct_approach,
               lookup_nhs_number=None, lookup_rid=None, lookup_mrid=None):
        # Create contact request
        cr = cls(request_by=request.user,
                 study=study,
                 request_direct_approach=request_direct_approach,
                 lookup_nhs_number=lookup_nhs_number,
                 lookup_rid=lookup_rid,
                 lookup_mrid=lookup_mrid)
        # Translate to an NHS number
        if lookup_nhs_number is not None:
            cr.nhs_number = lookup_nhs_number
        elif lookup_rid is not None:
            pass  # ***
        elif lookup_mrid is not None:
            pass  # ***
        else:
            return None
        # Look up patient details (afresh)
        cr.patient_lookup = lookup_patient(cr.nhs_number)
        # Establish consent mode
        cr.consent_mode = ConsentMode.get_or_create(cr.nhs_number,
                                                    cr.request_by)
        # Rest of processing
        cr.calc_approaches_in_past_year()
        # *** do the main processing here
        # Done
        cr.save()
        return cr
        


# =============================================================================
# Clinician response
# =============================================================================

class ClinicianResponse(models.Model):
    RESPONSE_A = 'A'
    RESPONSE_B = 'B'
    RESPONSE_C = 'C'
    RESPONSE_D = 'D'
    RESPONSES = (
        (RESPONSE_A, 'A: I will pass the request to the patient'),
        (RESPONSE_B, 'B: I veto on clinical grounds'),
        (RESPONSE_C, 'C: Patient is definitely ineligible'),
        (RESPONSE_D, 'D: Patient is dead/discharged or details are defunct'),
    )
    EMAIL = 'e'
    WEB = 'w'
    RESPONSE_ROUTES = (
        (EMAIL, 'E-mail'),
        (WEB, 'Web'),
    )
    EMAIL_CHOICE_Y = 'y'
    EMAIL_CHOICE_N = 'n'
    EMAIL_CHOICE_MAYBE = 'maybe'
    created_at = models.DateTimeField(verbose_name="When created (UTC)",
                                      auto_now_add=True)
    contact_request = models.OneToOneField(ContactRequest,
                                           related_name="clinician_response")
    charity_amount_due = models.DecimalField(
        max_digits=8, decimal_places=2,
        default=settings.CHARITY_AMOUNT_CLINICIAN_RESPONSE)
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
    response_route = models.CharField(max_length=1, choices=RESPONSE_ROUTES)

    def get_response_explanation(self):
        return [x[1] for x in ClinicianResponse.RESPONSES
                if x[0] == self.response] or ""


# =============================================================================
# Token for clinician response
# =============================================================================

class ClinicianToken(models.Model):
    LENGTH_CHARS = 20
    # info_bits = math.log(math.pow(26 + 26 + 10, LENGTH_CHARS), 2)
    # p_guess = math.pow(0.5, info_bits)

    created_at = models.DateTimeField(verbose_name="When created (UTC)",
                                      auto_now_add=True)
    used_at = models.DateTimeField(verbose_name="When used (UTC)", null=True)
    contact_request = models.OneToOneField(ContactRequest)
    token = models.CharField(max_length=LENGTH_CHARS)
    clinician_response = models.OneToOneField(ClinicianResponse)

    @staticmethod
    def get_new_token(contact_request):
        # https://github.com/django/django/blob/master/django/utils/crypto.py#L51  # noqa
        exists = True
        while exists:
            newtoken = get_random_string(ClinicianToken.LENGTH_CHARS)
            exists = ClinicianToken.objects.filter(token=newtoken).exists()
        return ClinicianToken(contact_request=contact_request,
                              token=newtoken)

    def mark_used(self, clinician_response):
        self.clinician_response = clinician_response
        self.used_at = timezone.now()
        self.save()

    def is_valid(self):
        if self.id is None:
            return False
        if self.token_used_at is None:  # valid, unused token
            return True
        expiry_datetime = self.used_at + settings.USED_TOKEN_TIMEOUT
        if timezone.now() > expiry_datetime:
            return False  # token has expired
        return True


# =============================================================================
# Patient response
# =============================================================================

class PatientResponse(Decision):
    created_at = models.DateTimeField(verbose_name="When created (UTC)",
                                      auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL)
    contact_request = models.OneToOneField(ContactRequest)
    # ***
