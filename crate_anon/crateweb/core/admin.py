#!/usr/bin/env python

"""
crate_anon/crateweb/core/admin.py

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

**The Django admin site, with parts for researchers (staff), parts for RDBMs
(superusers) and parts for developers (superusers with the developer flag
set).**

"""

# NOTE that
# - Objects for which a user is not authorized, via get_queryset(), will
#   causes an Http404 error.
# - You can't filter on Python properties via the Django QuerySet ORM.

import logging
from typing import Any, Dict, Iterable, Tuple

from cardinal_pythonlib.django.admin import (
    admin_view_fk_link,
    admin_view_reverse_fk_links,
    disable_bool_icon,
)
from cardinal_pythonlib.stringfunc import replace_in_list
from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.db import transaction
from django.db.models import Q, QuerySet
from django.http.request import HttpRequest
from django.template.defaultfilters import yesno
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy

from crate_anon.crateweb.consent.forms import TeamRepAdminForm
from crate_anon.crateweb.consent.models import (
    CharityPaymentRecord,
    ClinicianResponse,
    ConsentMode,
    ContactRequest,
    Decision,
    DummyPatientSourceInfo,
    Email,
    Leaflet,
    Letter,
    PatientLookup,
    PatientResponse,
    Study,
    TeamRep,
)
from crate_anon.crateweb.consent.tasks import (
    process_consent_change,
    process_patient_response,
    resend_email,
)
from crate_anon.crateweb.extra.admin import (
    AddOnlyModelAdmin,
    AllStaffReadOnlyModelAdmin,
    EditOnceOnlyModelAdmin,
    EditOnlyModelAdmin,
    ReadOnlyModelAdmin,
)
from crate_anon.crateweb.research.models import (
    QueryAudit,
)
from crate_anon.crateweb.userprofile.models import UserProfile

log = logging.getLogger(__name__)


# =============================================================================
# Research
# =============================================================================

class QueryMgrAdmin(ReadOnlyModelAdmin):
    """
    Read-only admin view to inspect SQL queries used by researchers (that is,
    to perform a query audit).
    """
    model = QueryAudit
    # Make all fields read-only (see also ReadOnlyModelAdmin):
    readonly_fields = ('id', 'when', 'get_user', 'get_sql', 'get_count_only',
                       'n_records', 'get_failed', 'fail_msg')
    fields = readonly_fields  # or other things could appear
    # Group entries by date conveniently:
    date_hierarchy = 'when'
    # Prefetch related objects (hugely reduces number of SQL queries):
    list_select_related = ('query', 'query__user')
    # What to show in the list:
    list_display = ('id', 'when', 'get_user', 'get_sql', 'get_count_only',
                    'n_records', 'get_failed', 'fail_msg')
    # Filter on Booleans on the right-hand side:
    list_filter = ('count_only', 'failed')
    # Search text content of these:
    search_fields = ('query__sql', 'query__user__username')

    def get_sql(self, obj: QueryAudit) -> str:
        return obj.query.sql
    get_sql.short_description = "SQL"
    get_sql.admin_order_field = 'query__sql'

    def get_user(self, obj: QueryAudit) -> str:
        return obj.query.user
    get_user.short_description = "User"
    get_user.admin_order_field = 'query__user'

    def get_count_only(self, obj: QueryAudit) -> str:
        return yesno(obj.count_only)
    get_count_only.short_description = "Count only?"
    get_count_only.admin_order_field = 'count_only'

    def get_failed(self, obj: QueryAudit) -> str:
        return yesno(obj.failed)
    get_failed.short_description = "Failed?"
    get_failed.admin_order_field = 'failed'


# =============================================================================
# Consent
# =============================================================================

# -----------------------------------------------------------------------------
# Study
# -----------------------------------------------------------------------------

class StudyInline(admin.TabularInline):
    """
    Use this to represent :class:`crate_anon.crateweb.consent.models.Study`
    inline.
    """
    model = Study


class StudyMgrAdmin(admin.ModelAdmin):
    """
    RDBM admin view on :class:`crate_anon.crateweb.consent.models.Study`.
    """
    fields = (
        'institutional_id',
        'title', 'lead_researcher', 'registered_at',
        'summary', 'summary_is_html',
        'search_methods_planned', 'patient_contact', 'include_under_16s',
        'include_lack_capacity', 'clinical_trial', 'include_discharged',
        'request_direct_approach', 'approved_by_rec', 'rec_reference',
        'approved_locally', 'local_approval_at',
        'study_details_pdf', 'subject_form_template_pdf',
        'researchers',
    )
    list_display = ('id', 'institutional_id', 'title', 'lead_researcher')
    list_display_links = ('id', 'institutional_id', 'title')
    filter_horizontal = ('researchers', )


class StudyResAdmin(AllStaffReadOnlyModelAdmin):
    """
    Researcher admin view on RDBM admin view on
    :class:`crate_anon.crateweb.consent.models.Study`.
    """
    fields = (
        'institutional_id',
        'title', 'lead_researcher', 'registered_at',
        'summary', 'summary_is_html',
        'search_methods_planned', 'patient_contact', 'include_under_16s',
        'include_lack_capacity', 'clinical_trial', 'include_discharged',
        'request_direct_approach', 'approved_by_rec', 'rec_reference',
        'approved_locally', 'local_approval_at',
        'study_details_pdf', 'subject_form_template_pdf',
        'researchers',
    )
    readonly_fields = fields
    list_display = ('id', 'institutional_id', 'title', 'lead_researcher')
    list_display_links = ('id', 'institutional_id', 'title')

    # Restrict to studies that this researcher is affiliated to
    def get_queryset(self, request: HttpRequest) -> QuerySet:
        qs = super().get_queryset(request)
        return Study.filter_studies_for_researcher(qs, request.user)


# -----------------------------------------------------------------------------
# Leaflet
# -----------------------------------------------------------------------------

class LeafletMgrAdmin(EditOnlyModelAdmin):
    """
    RDBM admin view on :class:`crate_anon.crateweb.consent.models.Leaflet`.
    """
    fields = ('name', 'pdf')
    readonly_fields = ('name', )


class LeafletResAdmin(AllStaffReadOnlyModelAdmin):
    """
    Researcher admin view on
    :class:`crate_anon.crateweb.consent.models.Leaflet`.
    """
    fields = ('name', 'get_pdf')
    readonly_fields = fields

    def get_pdf(self, obj: Leaflet) -> str:
        if not obj.pdf:
            return "(Missing)"
        return mark_safe('<a href="{}">PDF</a>'.format(
            reverse("leaflet", args=[obj.name])))
    get_pdf.short_description = "Leaflet PDF"


# -----------------------------------------------------------------------------
# E-mail
# -----------------------------------------------------------------------------

class EmailSentListFilter(SimpleListFilter):
    """
    Filter for :class:`crate_anon.crateweb.consent.models.Email` based on
    whether they're sent or not.
    """
    title = 'email sent'
    parameter_name = 'email_sent'

    def lookups(self,
                request: HttpRequest,
                model_admin: admin.ModelAdmin) -> Iterable[Tuple[str, str]]:
        return (
            ('y', "E-mail sent at least once"),
            ('n', "E-mail not sent"),
        )

    def queryset(self, request: HttpRequest, queryset: QuerySet) -> QuerySet:
        if self.value() == 'y':
            return queryset.filter(emailtransmission__sent=True).distinct()
        if self.value() == 'n':
            return queryset.exclude(emailtransmission__sent=True)


class EmailDevAdmin(ReadOnlyModelAdmin):
    """
    Developer admin view on :class:`crate_anon.crateweb.consent.models.Email`.
    """
    model = Email
    readonly_fields = (
        'id', 'created_at', 'sender', 'recipient', 'subject',
        'msg_text', 'get_view_msg_html', 'get_view_attachments',
        'to_clinician', 'to_researcher', 'to_patient',
        'get_study', 'get_contact_request', 'get_letter',
        'get_sent', 'get_transmissions',
    )
    fields = readonly_fields  # or other things appear
    date_hierarchy = 'created_at'
    list_display = ('id', 'created_at', 'recipient', 'subject', 'get_sent')
    list_filter = (EmailSentListFilter, )
    search_fields = ('recipient', 'subject')
    actions = ['resend']
    # ... alternative method (per instance):
    # http://stackoverflow.com/questions/2805701/is-there-a-way-to-get-custom-django-admin-actions-to-appear-on-the-change-view  # noqa

    # - We can't use list_select_related for things that have a foreign key to
    #   us (rather than things we have an FK to).
    # - prefetch_related (in the queryset) just uses Python, not SQL.
    # - http://blog.roseman.org.uk/2010/01/11/django-patterns-part-2-efficient-reverse-lookups/  # noqa
    # Anyway, premature optimization is the root of all evil, and all that.

    def get_view_msg_html(self, obj: Email) -> str:
        url = reverse('view_email_html', args=[obj.id])
        return mark_safe(
            '<a href="{}">View HTML message</a> ({} bytes)'.format(
                url, len(obj.msg_html)))
    get_view_msg_html.short_description = "Message HTML"

    def get_view_attachments(self, obj: Email) -> str:
        attachments = obj.emailattachment_set.all()
        if not attachments:
            return "(No attachments)"
        html = ""
        for i, attachment in enumerate(attachments):
            if attachment.exists():
                html += (
                    'Attachment {}: <a href="{}"><b>{}</b></a> '
                    '({} bytes), sent as <b>{}</b></a><br>'
                ).format(
                    i + 1,
                    reverse('view_email_attachment', args=[attachment.id]),
                    attachment.file,
                    attachment.size(),
                    attachment.sent_filename,
                )
            else:
                html += (
                    'Attachment {}: <b>{}</b> (missing), '
                    'sent as <b>{}</b><br>'
                ).format(
                    i + 1,
                    attachment.file,
                    attachment.sent_filename,
                )
        return mark_safe(html)
    get_view_attachments.short_description = "Attachments"

    def resend(self, request: HttpRequest, queryset: QuerySet) -> None:
        email_ids = []
        for email in queryset:
            email_ids.append(email.id)
            # transaction.on_commit not required (no changes made to emails)
            resend_email.delay(email.id, request.user.id)  # Asynchronous
        if email_ids:
            self.message_user(
                request,
                f"{len(email_ids)} e-mails were queued for resending: "
                f"IDs {str(email_ids)}.")
    resend.short_description = "Resend selected e-mails"

    def get_transmissions(self, obj: Email) -> str:
        return mark_safe(
            "<br>".join(str(x) for x in obj.emailtransmission_set.all()))
    get_transmissions.short_description = "Transmissions"

    def get_sent(self, obj: Email) -> bool:
        return obj.has_been_sent()
    get_sent.short_description = "Sent"
    get_sent.boolean = True

    def get_letter(self, obj: Email) -> str:
        return mark_safe(admin_view_fk_link(self, obj, "letter"))
    get_letter.short_description = "Letter"

    def get_study(self, obj: Email) -> str:
        return mark_safe(admin_view_fk_link(self, obj, "study"))
    get_study.short_description = "Study"

    def get_contact_request(self, obj: Email) -> str:
        return mark_safe(admin_view_fk_link(self, obj, "contact_request"))
    get_contact_request.short_description = "Contact request"


class EmailMgrAdmin(EmailDevAdmin):
    """
    RDBM admin view on :class:`crate_anon.crateweb.consent.models.Email`.

    Restrict to e-mails/information visible to the RDBM. Also, since we're not
    inhering from :class:`AllStaffReadOnlyModelAdmin`, give admin read
    permissions to all staff.
    """
    readonly_fields = (
        'id', 'created_at', 'sender', 'recipient', 'subject',

        # subject should not be confidential
        # no text, HTML, or attachments
        'get_restricted_msg_text', 'get_restricted_msg_html',
        'get_restricted_attachments',

        'to_clinician', 'to_researcher', 'to_patient',
        'get_study', 'get_contact_request', 'get_letter',
        'get_sent', 'get_transmissions',
    )
    fields = readonly_fields  # or other things appear
    actions = ['resend']

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        qs = super().get_queryset(request).filter(Q(to_researcher=True) |
                                                  Q(to_patient=True))
        return qs

    @staticmethod
    def rdbm_may_view(obj: Email) -> bool:
        return obj.to_patient or obj.to_researcher

    def get_restricted_msg_text(self, obj: Email) -> str:
        if not self.rdbm_may_view(obj):
            return "(Not authorized)"
        return obj.msg_text
    get_restricted_msg_text.short_description = "Message text"

    def get_restricted_msg_html(self, obj: Email) -> str:
        if not self.rdbm_may_view(obj):
            return "(Not authorized)"
        return mark_safe(self.get_view_msg_html(obj))
    get_restricted_msg_html.short_description = "Message HTML"

    def get_restricted_attachments(self, obj: Email) -> str:
        if not self.rdbm_may_view(obj):
            return "(Not authorized)"
        return mark_safe(self.get_view_attachments(obj))
    get_restricted_attachments.short_description = "Attachments"


class EmailResAdmin(EmailDevAdmin):
    """
    Researcher RDBM admin view on
    :class:`crate_anon.crateweb.consent.models.Email`.

    Restrict to e-mails visible to a researcher. Also, since we're not inhering
    from :class:`AllStaffReadOnlyModelAdmin`, give admin read permissions to
    all staff.
    """
    readonly_fields = (
        'id', 'created_at', 'sender', 'recipient', 'subject',
        'msg_text', 'get_view_msg_html', 'get_view_attachments',
        'to_clinician', 'to_researcher', 'to_patient',
        'get_study', 'get_contact_request', 'get_letter',
        'get_sent', 'get_transmissions',
    )
    fields = readonly_fields  # or other things appear
    actions = None  # not [], which allows site-wide things

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        qs = super().get_queryset(request).filter(to_researcher=True)
        studies = Study.filter_studies_for_researcher(Study.objects.all(),
                                                      request.user)
        return qs.filter(study__in=studies)

    def has_module_permission(self, request: HttpRequest) -> bool:
        return request.user.is_staff

    def has_change_permission(self,
                              request: HttpRequest,
                              obj: Email = None) -> bool:
        return request.user.is_staff


# -----------------------------------------------------------------------------
# Dummy patient source info
# -----------------------------------------------------------------------------

class DummyPatientSourceInfoDevAdmin(admin.ModelAdmin):
    """
    Developer admin view on
    :class:`crate_anon.crateweb.consent.models.DummyPatientSourceInfo`.
    """
    fields = (
        # Patient
        'nhs_number',
        'pt_dob', 'pt_dod', 'pt_dead', 'pt_discharged', 'pt_discharge_date',
        'pt_sex',
        'pt_title', 'pt_first_name', 'pt_last_name',
        'pt_address_1', 'pt_address_2', 'pt_address_3', 'pt_address_4',
        'pt_address_5', 'pt_address_6', 'pt_address_7',
        'pt_telephone', 'pt_email',

        # GP
        'gp_title', 'gp_first_name', 'gp_last_name',
        'gp_address_1', 'gp_address_2', 'gp_address_3', 'gp_address_4',
        'gp_address_5', 'gp_address_6', 'gp_address_7',
        'gp_telephone', 'gp_email',

        # Clinician
        'clinician_title', 'clinician_first_name', 'clinician_last_name',
        'clinician_address_1', 'clinician_address_2', 'clinician_address_3',
        'clinician_address_4', 'clinician_address_5', 'clinician_address_6',
        'clinician_address_7',
        'clinician_telephone', 'clinician_email',
        'clinician_is_consultant', 'clinician_signatory_title',
    )
    list_display = ('id', 'nhs_number', 'pt_first_name', 'pt_last_name')
    list_display_links = ('id', 'nhs_number')
    search_fields = ('nhs_number', 'pt_first_name', 'pt_last_name')


# -----------------------------------------------------------------------------
# Patient lookup
# -----------------------------------------------------------------------------

class PatientLookupDevAdmin(ReadOnlyModelAdmin):
    """
    Developer admin view on
    :class:`crate_anon.crateweb.consent.models.PatientLookup`.
    """
    readonly_fields = (
        # Lookup details
        'lookup_at', 'source_db', 'nhs_number',

        # Patient
        'pt_found',
        'pt_local_id_description', 'pt_local_id_number',
        'pt_dob', 'pt_dod', 'pt_dead', 'pt_discharged', 'pt_sex',
        'pt_title', 'pt_first_name', 'pt_last_name',
        'pt_address_1', 'pt_address_2', 'pt_address_3', 'pt_address_4',
        'pt_address_5', 'pt_address_6', 'pt_address_7',
        'pt_telephone', 'pt_email',

        # GP
        'gp_found',
        'gp_title', 'gp_first_name', 'gp_last_name',
        'gp_address_1', 'gp_address_2', 'gp_address_3', 'gp_address_4',
        'gp_address_5', 'gp_address_6', 'gp_address_7',
        'gp_telephone', 'gp_email',

        # Clinician
        'clinician_found',
        'clinician_title', 'clinician_first_name', 'clinician_last_name',
        'clinician_address_1', 'clinician_address_2', 'clinician_address_3',
        'clinician_address_4', 'clinician_address_5', 'clinician_address_6',
        'clinician_address_7',
        'clinician_telephone', 'clinician_email',
        'clinician_is_consultant', 'clinician_signatory_title',

        # Decisions
        'decisions', 'secret_decisions',

        # Extras
        'get_test_views',
    )
    fields = readonly_fields
    date_hierarchy = 'lookup_at'
    list_display = ('id', 'nhs_number',
                    'pt_first_name', 'pt_last_name', 'pt_dob')
    search_fields = ('nhs_number', 'pt_first_name', 'pt_last_name')

    def get_test_views(self, obj: PatientLookup) -> str:
        return mark_safe(
            '''
                <a href="{}">Draft letter to patient re first traffic-light
                    choice (as HTML)</a><br>
                <a href="{}">Draft letter to patient re first traffic-light
                    choice (as PDF)</a>
            '''.format(
                reverse('draft_first_traffic_light_letter',
                        args=[obj.id, "html"]),
                reverse('draft_first_traffic_light_letter',
                        args=[obj.id, "pdf"]),
            )
        )
    get_test_views.short_description = "Test views"


# -----------------------------------------------------------------------------
# Consent mode
# -----------------------------------------------------------------------------

class ConsentModeInline(admin.TabularInline):
    """
    Use this to represent
    :class:`crate_anon.crateweb.consent.models.ConsentMode` inline.
    """
    model = ConsentMode


class ConsentModeAdminForm(forms.ModelForm):
    """
    Admin form to edit a
    :class:`crate_anon.crateweb.consent.models.ConsentMode`.
    """
    def clean(self) -> Dict[str, Any]:
        if not self.cleaned_data.get('changed_by_clinician_override'):
            kwargs = {}
            for field in Decision.FIELDS:
                kwargs[field] = self.cleaned_data.get(field)
            decision = Decision(**kwargs)
            decision.validate_decision()
        return self.cleaned_data


class ConsentModeMgrAdmin(AddOnlyModelAdmin):
    """
    RDBM admin view on a
    :class:`crate_anon.crateweb.consent.models.ConsentMode`.
    """

    # To switch off the Boolean icons: replace exclude_entirely with
    # exclude_entirely_col in the fieldlist, and define the function as:
    #
    # def exclude_entirely_col(self, obj):
    #     return obj.exclude_entirely
    # exclude_entirely_col.boolean = False
    #
    # Can use get_fields(self, request, obj=None) and get_readonly_fields(...)
    # to customize icon behaviour depending on whether we're adding or
    # editing.

    form = ConsentModeAdminForm
    fields = [
        'nhs_number',
        'exclude_entirely',
        'consent_mode',
        # 'consent_after_discharge',
        # 'max_approaches_per_year',
        # 'other_requests',
        'prefers_email',
        'changed_by_clinician_override',
    ] + Decision.FIELDS
    list_display = (
        'id', 'nhs_number', 'consent_mode',
        # 'consent_after_discharge'
        'source',
    )
    list_display_links = ('id', 'nhs_number')
    search_fields = ('nhs_number', )
    list_filter = (
        'consent_mode',
        # 'consent_after_discharge',
        'exclude_entirely',
        'prefers_email'
    )
    date_hierarchy = 'created_at'

    fields_for_viewing = replace_in_list(fields, {
        'exclude_entirely': 'exclude_entirely2',
        # 'consent_after_discharge': 'consent_after_discharge2',
        'prefers_email': 'prefers_email2',
        'changed_by_clinician_override': 'changed_by_clinician_override2',
    })
    exclude_entirely2 = disable_bool_icon('exclude_entirely', ConsentMode)
    consent_after_discharge2 = disable_bool_icon(
        'consent_after_discharge', ConsentMode)
    prefers_email2 = disable_bool_icon('prefers_email', ConsentMode)
    changed_by_clinician_override2 = disable_bool_icon(
        'changed_by_clinician_override', ConsentMode)

    # Populate the created_by field automatically, with the two functions below
    # https://code.djangoproject.com/wiki/CookBookNewformsAdminAndUser
    def save_model(self,
                   request: HttpRequest,
                   obj: ConsentMode,
                   form: forms.ModelForm,
                   change: bool) -> None:
        obj.current = True
        obj.needs_processing = True
        obj.created_by = request.user
        obj.save()
        transaction.on_commit(
            lambda: process_consent_change.delay(obj.id)
        )  # Asynchronous
        # Without transaction.on_commit, we get a RACE CONDITION:
        # object is received in the pre-save() state.
        self.message_user(
            request,
            "Consent mode will be changed. You will be e-mailed regarding "
            "the letter to patient (+/- re withdrawal of consent to "
            "researchers).")

    # def save_formset(self, request, form, formset, change):
    #     if formset.model == ConsentMode:
    #         instances = formset.save(commit=False)
    #         for instance in instances:
    #             instance.created_by = request.user
    #             instance.save()
    #     else:
    #         formset.save()

    # Restrict to current ones
    def get_queryset(self, request: HttpRequest) -> QuerySet:
        qs = super().get_queryset(request)
        return qs.filter(current=True)


class ConsentModeDevAdmin(ReadOnlyModelAdmin):
    """
    Developer admin view on a
    :class:`crate_anon.crateweb.consent.models.ConsentMode`.
    """
    readonly_fields = [
        'nhs_number',
        'current', 'created_at', 'created_by',
        'exclude_entirely', 'consent_mode', 'consent_after_discharge',
        'max_approaches_per_year', 'other_requests', 'prefers_email',
        'changed_by_clinician_override',
        'source',
    ] + Decision.FIELDS + [
        'get_test_views',
    ]
    fields = readonly_fields
    list_display = (
        'id',
        'current',
        'nhs_number',
        'consent_mode',
        # 'consent_after_discharge'
        'source',
    )
    search_fields = ('nhs_number', )
    list_filter = (
        'current',
        'consent_mode',
        # 'consent_after_discharge',
        'exclude_entirely',
        'prefers_email'
    )

    def get_test_views(self, obj: ConsentMode) -> str:
        return mark_safe(
            '''
                <a href="{}">Draft letter to patient confirming traffic-light
                    choice (as HTML)</a><br>
                <a href="{}">Draft letter to patient confirming traffic-light
                    choice (as PDF)</a>
            '''.format(
                reverse('draft_confirm_traffic_light_letter',
                        args=[obj.id, "html"]),
                reverse('draft_confirm_traffic_light_letter',
                        args=[obj.id, "pdf"]),
            )
        )
    get_test_views.short_description = "Test views"


# -----------------------------------------------------------------------------
# Team rep
# -----------------------------------------------------------------------------

class TeamRepMgrAdmin(admin.ModelAdmin):
    """
    RDBM admin view on a :class:`crate_anon.crateweb.consent.models.TeamRep`.
    """
    fields = ('team', 'user')
    list_display = ('team', 'user')
    search_fields = ('team', )
    form = TeamRepAdminForm


# -----------------------------------------------------------------------------
# Charity payments
# -----------------------------------------------------------------------------

class CharityPaymentRecordMgrAdmin(AddOnlyModelAdmin):
    """
    RDBM admin view on a
    :class:`crate_anon.crateweb.consent.models.CharityPaymentRecord`.
    """
    fields = ('payee', 'amount')
    fields_for_viewing = fields
    list_display = ('id', 'created_at', 'payee', 'amount')
    list_display_links = ('id', 'created_at')
    search_fields = ('payee', )
    date_hierarchy = 'created_at'


# -----------------------------------------------------------------------------
# Contact request
# -----------------------------------------------------------------------------

class ClinicianRespondedListFilter(SimpleListFilter):
    """
    Filter for :class:`crate_anon.crateweb.consent.models.ContactRequest` based
    on whether the clinician has responded.
    """
    title = 'clinician responded'
    parameter_name = 'clinician_responded'

    def lookups(self,
                request: HttpRequest,
                model_admin: admin.ModelAdmin) -> Iterable[Tuple[str, str]]:
        return (
            ('y', "Clinician responded"),
            ('n', "Clinician asked but hasn’t responded"),
        )

    def queryset(self, request: HttpRequest, queryset: QuerySet) -> QuerySet:
        if self.value() == 'y':
            return (
                queryset
                .filter(decided_send_to_clinician=True)
                .filter(clinician_response__responded=True)
            )
        if self.value() == 'n':
            return (
                queryset
                .filter(decided_send_to_clinician=True)
                .filter(clinician_response__responded=False)
            )


class ContactRequestMgrAdmin(ReadOnlyModelAdmin):
    """
    RDBM admin view on
    :class:`crate_anon.crateweb.consent.models.ContactRequest`.
    """
    NONCONFIDENTIAL_FIELDS = (
        'id', 'created_at', 'request_by', 'get_study',
        'request_direct_approach',
        'lookup_nhs_number', 'lookup_rid', 'lookup_mrid',
        'processed',
        'get_consent_mode',
        'approaches_in_past_year',
        'decisions',
        'decided_no_action',
        'decided_send_to_researcher',
        'decided_send_to_clinician',
        'clinician_involvement',
        'consent_withdrawn',
        'consent_withdrawn_at',
        'get_letters', 'get_emails',
    )
    fields = NONCONFIDENTIAL_FIELDS + ('get_clinician_email_address',
                                       'get_clinician_responded')
    readonly_fields = fields
    NONCONFIDENTIAL_LIST_DISPLAY = (
        'id', 'created_at', 'request_by', 'study',
        'lookup_nhs_number', 'lookup_rid', 'lookup_mrid',
        'decided_no_action', 'decided_send_to_researcher',
        'decided_send_to_clinician', 'get_clinician_responded',
    )
    list_display = NONCONFIDENTIAL_LIST_DISPLAY + (
        'get_clinician_email_address',
    )
    list_filter = ('decided_no_action', 'decided_send_to_researcher',
                   'decided_send_to_clinician', ClinicianRespondedListFilter)
    list_select_related = (
        'clinician_response',
        'request_by',
        'study__lead_researcher',
        'patient_lookup',
        'consent_mode',
    )
    date_hierarchy = 'created_at'

    def get_consent_mode(self, obj: ContactRequest) -> ConsentMode:
        consent_mode = obj.consent_mode
        return consent_mode.consent_mode
    get_consent_mode.short_description = "Consent mode"

    def get_study(self, obj: ContactRequest) -> str:
        return mark_safe(admin_view_fk_link(self, obj, "study"))
    get_study.short_description = "Study"

    def get_clinician_email_address(self, obj: ContactRequest) -> str:
        if obj.decided_send_to_clinician:
            return obj.patient_lookup.clinician_email
        else:
            return ''
    get_clinician_email_address.short_description = "Clinician e-mail address"

    def get_clinician_responded(self, obj: ContactRequest) -> bool:
        if not hasattr(obj, 'clinician_response'):
            return False
        return obj.clinician_response.responded
    get_clinician_responded.short_description = "Clinician responded"
    get_clinician_responded.boolean = True

    def get_letters(self, obj: ContactRequest) -> str:
        return mark_safe(admin_view_reverse_fk_links(self, obj, "letter_set"))
    get_letters.short_description = "Letter(s)"

    def get_emails(self, obj: ContactRequest) -> str:
        return mark_safe(admin_view_reverse_fk_links(self, obj, "email_set"))
    get_emails.short_description = "E-mail(s)"


class ContactRequestResAdmin(ContactRequestMgrAdmin):
    """
    Researcher admin view on
    :class:`crate_anon.crateweb.consent.models.ContactRequest`.
    """
    fields = ContactRequestMgrAdmin.NONCONFIDENTIAL_FIELDS
    readonly_fields = fields
    list_display = ContactRequestMgrAdmin.NONCONFIDENTIAL_LIST_DISPLAY

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        qs = super().get_queryset(request)
        studies = Study.filter_studies_for_researcher(Study.objects.all(),
                                                      request.user)
        return qs.filter(study__in=studies)

    def has_module_permission(self, request: HttpRequest) -> bool:
        return request.user.is_staff

    def has_change_permission(self,
                              request: HttpRequest,
                              obj: ContactRequest = None) -> bool:
        return request.user.is_staff


class ContactRequestDevAdmin(ContactRequestMgrAdmin):
    """
    Developer admin view on
    :class:`crate_anon.crateweb.consent.models.ContactRequest`.
    """
    fields = ContactRequestMgrAdmin.NONCONFIDENTIAL_FIELDS + (
        # RDBM can also see
        'get_clinician_email_address',
        'get_link_clinician_email',
        'get_clinician_responded',
        'get_link_clinician_response',

        # properly secret
        'nhs_number',
        'get_patient_lookup',

        # exploratory test views
        'get_test_views',
    )
    readonly_fields = fields
    list_display = (
        'id', 'created_at', 'request_by', 'study',
        'nhs_number',
        'decided_no_action', 'decided_send_to_researcher',
        'decided_send_to_clinician', 'get_clinician_responded',
        'get_clinician_email_address',
    )

    def get_link_clinician_email(self, obj: ContactRequest) -> str:
        return mark_safe(admin_view_reverse_fk_links(self, obj, "email_set"))
    get_link_clinician_email.short_description = "E-mail to clinician"

    def get_link_clinician_response(self, obj: ContactRequest) -> str:
        return mark_safe(admin_view_fk_link(self, obj, "clinician_response"))
    get_link_clinician_response.short_description = "Clinician response"

    def get_patient_lookup(self, obj: ContactRequest) -> str:
        return mark_safe(admin_view_fk_link(self, obj, "patient_lookup"))
    get_patient_lookup.short_description = "Patient lookup"

    def get_consent_mode(self, obj: ContactRequest) -> str:
        return mark_safe(admin_view_fk_link(self, obj, "consent_mode"))
    get_consent_mode.short_description = "Consent mode"

    def get_letters(self, obj: ContactRequest) -> str:
        return mark_safe(admin_view_reverse_fk_links(self, obj, "letter_set"))
    get_letters.short_description = "Letter(s)"

    def get_test_views(self, obj: ContactRequest) -> str:
        html = '''
            <a href="{}">Draft e-mail to clinician</a><br>
            <a href="{}">Draft letter from clinician to patient re study
                (HTML)</a></br>
            <a href="{}">Draft letter from clinician to patient re study
                (PDF)</a></br>
            <a href="{}">Decision form to patient re study (HTML)</a><br>
            <a href="{}">Decision form to patient re study (PDF)</a><br>
            <a href="{}">Draft approval letter to researcher (HTML)</a><br>
            <a href="{}">Draft approval letter to researcher (PDF)</a><br>
            <a href="{}">Draft approval covering e-mail to researcher</a><br>
            <a href="{}">Draft withdrawal letter to researcher (HTML)</a><br>
            <a href="{}">Draft withdrawal letter to researcher (PDF)</a><br>
            <a href="{}">Draft withdrawal covering e-mail to researcher</a>
        '''.format(
            reverse('draft_clinician_email', args=[obj.id]),
            reverse('draft_letter_clinician_to_pt_re_study',
                    args=[obj.id, "html"]),
            reverse('draft_letter_clinician_to_pt_re_study',
                    args=[obj.id, "pdf"]),
            reverse('decision_form_to_pt_re_study',
                    args=[obj.id, "html"]),
            reverse('decision_form_to_pt_re_study',
                    args=[obj.id, "pdf"]),
            reverse('draft_approval_letter', args=[obj.id, "html"]),
            reverse('draft_approval_letter', args=[obj.id, "pdf"]),
            reverse('draft_approval_email', args=[obj.id]),
            reverse('draft_withdrawal_letter', args=[obj.id, "html"]),
            reverse('draft_withdrawal_letter', args=[obj.id, "pdf"]),
            reverse('draft_withdrawal_email', args=[obj.id]),
        )
        return mark_safe(html)
    get_test_views.short_description = "Test views"


# -----------------------------------------------------------------------------
# Clinician response
# -----------------------------------------------------------------------------

class ClinicianResponseDevAdmin(ReadOnlyModelAdmin):
    """
    Developer admin view on
    :class:`crate_anon.crateweb.consent.models.ClinicianResponse`.
    """
    fields = [
        'created_at', 'contact_request', 'token',
        'responded', 'responded_at', 'response_route',
        'email_choice', 'response',
        'veto_reason', 'ineligible_reason', 'pt_uncontactable_reason',
        'clinician_confirm_name',
        'charity_amount_due',

        'get_contact_request',
    ]
    readonly_fields = fields
    date_hierarchy = 'created_at'

    def get_contact_request(self, obj: ClinicianResponse) -> str:
        return mark_safe(admin_view_fk_link(self, obj, "contact_request"))
    get_contact_request.short_description = "Contact request"


# -----------------------------------------------------------------------------
# Patient response
# -----------------------------------------------------------------------------

class PatientResponseAdminForm(forms.ModelForm):
    """
    Admin form to edit a
    :class:`crate_anon.crateweb.consent.models.PatientResponse`.
    """
    def clean(self) -> Dict[str, Any]:
        kwargs = {}
        for field in Decision.FIELDS:
            kwargs[field] = self.cleaned_data.get(field)
        decision = Decision(**kwargs)
        decision.validate_decision()
        return self.cleaned_data


class PatientResponseMgrAdmin(EditOnceOnlyModelAdmin):
    """
    RDBM admin view on a
    :class:`crate_anon.crateweb.consent.models.PatientResponse`.
    """
    form = PatientResponseAdminForm
    fields = [
        'id', 'created_at', 'get_contact_request', 'response'
    ] + Decision.FIELDS
    readonly_fields = ['id', 'created_at', 'get_contact_request']
    date_hierarchy = 'created_at'

    # Populate the created_by field automatically, with the two functions below
    def save_model(self,
                   request: HttpRequest,
                   obj: PatientResponse,
                   form: forms.ModelForm,
                   change: bool) -> None:
        obj.recorded_by = request.user
        obj.save()
        # log.debug(f"PatientResponse: {modelrepr(obj)}")
        transaction.on_commit(
            lambda: process_patient_response.delay(obj.id)
        )  # Asynchronous
        if obj.response == PatientResponse.YES:
            self.message_user(
                request,
                "Approval to researcher will be generated. You will be "
                "e-mailed if the system can't send it to the researcher.")

    def has_change_permission(self,
                              request: HttpRequest,
                              obj: PatientResponse = None) -> bool:
        if obj and obj.response:
            return False  # already saved
        return True

    def get_contact_request(self, obj: PatientResponse) -> str:
        return mark_safe(admin_view_fk_link(self, obj, "contact_request"))
    get_contact_request.short_description = "Contact request"

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        # Restrict to unresponded ones
        return super().get_queryset(request).filter(response__isnull=True)


class PatientResponseDevAdmin(ReadOnlyModelAdmin):
    """
    Developer admin view on a
    :class:`crate_anon.crateweb.consent.models.PatientResponse`.
    """
    fields = PatientResponseMgrAdmin.fields
    readonly_fields = fields
    date_hierarchy = 'created_at'

    def get_contact_request(self, obj: PatientResponse) -> str:
        return mark_safe(admin_view_fk_link(self, obj, "contact_request"))
    get_contact_request.short_description = "Contact request"


# -----------------------------------------------------------------------------
# Letters
# -----------------------------------------------------------------------------

class LetterSendingStatusFilter(SimpleListFilter):
    """
    Filter for :class:`crate_anon.crateweb.consent.models.Letter` based on
    whether they're sent or not.
    """
    title = "sending status"
    parameter_name = 'sending_status'

    def lookups(self,
                request: HttpRequest,
                model_admin: admin.ModelAdmin) -> Iterable[Tuple[str, str]]:
        return (
            ('sent_manually', "Sent manually"),
            ('not_sent_manually', "Not sent manually"),
            ('sent_by_email', "Sent by e-mail"),
            ('not_sent_by_email', "Not sent by e-mail"),
            ('require_sending', "REQUIRE SENDING"),
        )

    def queryset(self, request: HttpRequest, queryset: QuerySet) -> QuerySet:
        if self.value() == 'sent_manually':
            return queryset.filter(sent_manually_at__isnull=False)
        if self.value() == 'not_sent_manually':
            return queryset.filter(sent_manually_at__isnull=True)
        if self.value() == 'sent_by_email':
            return (
                queryset
                .filter(email__emailtransmission__sent=True)
                .distinct()
            )
        if self.value() == 'not_sent_by_email':
            return queryset.exclude(email__emailtransmission__sent=True)
        if self.value() == 'require_sending':
            return (
                queryset
                # Restrict to letters not sent manually
                .filter(sent_manually_at__isnull=True)
                # Exclude letters successfully sent by e-mail
                .exclude(email__emailtransmission__sent=True)
            )


class LetterDevAdmin(ReadOnlyModelAdmin):
    """
    Developer admin view on :class:`crate_anon.crateweb.consent.models.Letter`.
    """
    fields = ('id', 'created_at', 'pdf',
              'to_clinician', 'to_researcher', 'to_patient',
              'get_study', 'get_contact_request',
              'sent_manually_at', 'get_emails')
    readonly_fields = fields
    list_display = ('id', 'created_at',
                    'to_clinician', 'to_researcher', 'to_patient',
                    'study', 'contact_request',
                    'sent_manually_at')
    list_filter = (LetterSendingStatusFilter,
                   'to_clinician', 'to_researcher', 'to_patient')
    list_select_related = (
        'study__lead_researcher',
        'contact_request',
    )
    date_hierarchy = 'created_at'
    # ... see also http://stackoverflow.com/questions/991926/custom-filter-in-django-admin-on-django-1-3-or-below  # noqa
    actions = ['mark_sent']

    def mark_sent(self, request: HttpRequest, queryset: QuerySet) -> None:
        ids = []
        for letter in queryset:
            letter.mark_sent()
            ids.append(letter.id)
        self.message_user(
            request,
            f"{len(ids)} letter(s) were marked as sent: IDs {str(ids)}.")
    mark_sent.short_description = "Mark selected letters as printed/sent"

    def get_study(self, obj: Letter) -> str:
        return mark_safe(admin_view_fk_link(self, obj, "study"))
    get_study.short_description = "Study"

    def get_contact_request(self, obj: Letter) -> str:
        return mark_safe(admin_view_fk_link(self, obj, "contact_request"))
    get_contact_request.short_description = "Contact request"

    def get_emails(self, obj: Letter) -> str:
        return mark_safe(admin_view_reverse_fk_links(self, obj, "email_set"))
    get_emails.short_description = "E-mail(s)"


class LetterMgrAdmin(LetterDevAdmin):
    """
    RDBM admin view on :class:`crate_anon.crateweb.consent.models.Letter`.
    """
    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return (
            super().get_queryset(request)
            .filter(Q(to_researcher=True) | Q(rdbm_may_view=True))
        )


class LetterResAdmin(LetterDevAdmin):
    """
    Researcher admin view on
    :class:`crate_anon.crateweb.consent.models.Letter`.

    Restrict to letters visible to a researcher.
    """
    fields = ('id', 'created_at', 'get_pdf',
              'to_clinician', 'to_researcher', 'to_patient',
              'study', 'contact_request',
              'sent_manually_at', 'email')
    readonly_fields = fields

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        qs = super().get_queryset(request).filter(to_researcher=True)
        studies = Study.filter_studies_for_researcher(Study.objects.all(),
                                                      request.user)
        return qs.filter(study__in=studies)

    def has_module_permission(self, request: HttpRequest) -> bool:
        return request.user.is_staff

    def has_change_permission(self,
                              request: HttpRequest,
                              obj: Letter = None) -> bool:
        return request.user.is_staff

    def get_pdf(self, obj: Letter) -> str:
        if not obj.pdf:
            return "(Missing)"
        return mark_safe('<a href="{}">PDF</a>'.format(
            reverse("letter", args=[obj.id])))
    get_pdf.short_description = "Letter PDF"


# =============================================================================
# User profiles
# =============================================================================

class UserProfileInline(admin.StackedInline):
    """
    Use this to represent
    :class:`crate_anon.crateweb.userprofile.models.UserProfile` inline.
    """
    model = UserProfile
    max_num = 1
    can_delete = False
    inlines = [StudyInline]
    fields = ('per_page', 'line_length',
              'collapse_at_len', 'collapse_at_n_lines',
              'is_developer',
              'title',
              'telephone',
              'address_1', 'address_2', 'address_3', 'address_4',
              'address_5', 'address_6', 'address_7',
              'is_clinician', 'is_consultant',
              'get_studies_as_lead', 'get_studies_as_researcher',
              'enough_info_for_researcher')
    readonly_fields = ('get_studies_as_lead', 'get_studies_as_researcher',
                       'enough_info_for_researcher')

    def get_studies_as_lead(self, obj: settings.AUTH_USER_MODEL) -> str:
        studies = obj.user.studies_as_lead.all()
        return mark_safe(
            render_to_string('shortlist_studies.html', {'studies': studies}))
    get_studies_as_lead.short_description = "Studies as lead researcher"

    def get_studies_as_researcher(self, obj: settings.AUTH_USER_MODEL) -> str:
        studies = obj.user.studies_as_researcher.all()
        return mark_safe(
            render_to_string('shortlist_studies.html', {'studies': studies}))
    get_studies_as_researcher.short_description = "Studies as researcher"

    def enough_info_for_researcher(self,
                                   obj: settings.AUTH_USER_MODEL) -> bool:
        return (
            bool(obj.title) and
            bool(obj.user.first_name) and
            bool(obj.user.last_name)
        )
    enough_info_for_researcher.short_description = (
        "Enough info for researcher status (title, firstname, lastname)?"
    )
    enough_info_for_researcher.boolean = True


class ExtendedUserMgrAdmin(UserAdmin):
    """
    RDBM admin view on the Django user class with its associated
    :class:`crate_anon.crateweb.userprofile.models.UserProfile`.
    """
    inlines = [UserProfileInline]
    list_display = (
        'username', 'email', 'first_name', 'last_name', 'is_staff',
        'enough_info_for_researcher',
    )

    def enough_info_for_researcher(self,
                                   obj: settings.AUTH_USER_MODEL) -> bool:
        return (
            bool(obj.profile.title) and
            bool(obj.first_name) and
            bool(obj.last_name)
        )
    enough_info_for_researcher.short_description = (
        "Enough researcher info?"
    )
    enough_info_for_researcher.boolean = True


# =============================================================================
# Assemble main admin site
# =============================================================================
# http://stackoverflow.com/questions/4938491/django-admin-change-header-django-administration-text  # noqa
# http://stackoverflow.com/questions/3400641/how-do-i-inline-edit-a-django-user-profile-in-the-admin-interface  # noqa

class MgrAdminSite(admin.AdminSite):
    """
    RDBM admin site.
    """
    # Text to put at the end of each page's <title>.
    site_title = ugettext_lazy(settings.RESEARCH_DB_TITLE + ' manager admin')
    # Text to put in each page's <h1>.
    site_header = ugettext_lazy(settings.RESEARCH_DB_TITLE + ": manager admin")
    # URL for the "View site" link at the top of each admin page.
    site_url = settings.FORCE_SCRIPT_NAME + "/"
    # Text to put at the top of the admin index page.
    index_title = ugettext_lazy(settings.RESEARCH_DB_TITLE +
                                ' site administration for RDBM')
    index_template = 'admin/viewchange_admin_index.html'
    app_index_template = 'admin/viewchange_admin_app_index.html'


mgr_admin_site = MgrAdminSite(name="mgradmin")
mgr_admin_site.disable_action('delete_selected')
# ... particularly for e-mail where we manually specify a bulk action (resend)
# https://docs.djangoproject.com/en/1.8/ref/contrib/admin/actions/
mgr_admin_site.register(CharityPaymentRecord, CharityPaymentRecordMgrAdmin)
mgr_admin_site.register(ConsentMode, ConsentModeMgrAdmin)
mgr_admin_site.register(ContactRequest, ContactRequestMgrAdmin)
mgr_admin_site.register(Email, EmailMgrAdmin)
mgr_admin_site.register(Leaflet, LeafletMgrAdmin)
mgr_admin_site.register(Letter, LetterMgrAdmin)
mgr_admin_site.register(PatientResponse, PatientResponseMgrAdmin)
mgr_admin_site.register(QueryAudit, QueryMgrAdmin)
mgr_admin_site.register(Study, StudyMgrAdmin)
mgr_admin_site.register(TeamRep, TeamRepMgrAdmin)
mgr_admin_site.register(User, ExtendedUserMgrAdmin)


# =============================================================================
# Assemble secondary (developer) admin site
# =============================================================================
# http://stackoverflow.com/questions/4938491/django-admin-change-header-django-administration-text  # noqa
# http://stackoverflow.com/questions/3400641/how-do-i-inline-edit-a-django-user-profile-in-the-admin-interface  # noqa

class DevAdminSite(admin.AdminSite):
    """
    Developer admin site.
    """
    site_title = ugettext_lazy(settings.RESEARCH_DB_TITLE + ' dev admin')
    site_header = ugettext_lazy(settings.RESEARCH_DB_TITLE +
                                ": developer admin")
    site_url = settings.FORCE_SCRIPT_NAME + "/"
    index_title = ugettext_lazy(settings.RESEARCH_DB_TITLE +
                                ' developer administration')
    index_template = 'admin/viewchange_admin_index.html'
    app_index_template = 'admin/viewchange_admin_app_index.html'


dev_admin_site = DevAdminSite(name="devadmin")
dev_admin_site.disable_action('delete_selected')
# Where no specific DevAdmin version exists, use the MgrAdmin
dev_admin_site.register(CharityPaymentRecord, CharityPaymentRecordMgrAdmin)
dev_admin_site.register(ClinicianResponse, ClinicianResponseDevAdmin)
dev_admin_site.register(ConsentMode, ConsentModeDevAdmin)
dev_admin_site.register(ContactRequest, ContactRequestDevAdmin)
dev_admin_site.register(DummyPatientSourceInfo, DummyPatientSourceInfoDevAdmin)
dev_admin_site.register(Email, EmailDevAdmin)
dev_admin_site.register(Leaflet, LeafletMgrAdmin)
dev_admin_site.register(Letter, LetterDevAdmin)
dev_admin_site.register(PatientLookup, PatientLookupDevAdmin)
dev_admin_site.register(PatientResponse, PatientResponseDevAdmin)
dev_admin_site.register(QueryAudit, QueryMgrAdmin)
dev_admin_site.register(Study, StudyMgrAdmin)
dev_admin_site.register(TeamRep, TeamRepMgrAdmin)
dev_admin_site.register(User, ExtendedUserMgrAdmin)


# =============================================================================
# Assemble tertiary (researcher) admin site
# =============================================================================

class ResearcherAdminSite(admin.AdminSite):
    """
    Researcher admin site.
    """
    site_title = ugettext_lazy(settings.RESEARCH_DB_TITLE +
                               ' researcher admin views')
    site_header = ugettext_lazy(settings.RESEARCH_DB_TITLE +
                                ": researcher admin")
    site_url = settings.FORCE_SCRIPT_NAME + "/"
    index_title = ugettext_lazy("View/manage your studies")
    index_template = 'admin/viewchange_admin_index.html'
    app_index_template = 'admin/viewchange_admin_app_index.html'


res_admin_site = ResearcherAdminSite(name="resadmin")
res_admin_site.disable_action('delete_selected')
res_admin_site.register(Study, StudyResAdmin)
res_admin_site.register(Leaflet, LeafletResAdmin)
res_admin_site.register(Email, EmailResAdmin)
res_admin_site.register(Letter, LetterResAdmin)
res_admin_site.register(ContactRequest, ContactRequestResAdmin)

"""
Problem with non-superusers not seeing any apps:
- http://stackoverflow.com/questions/1929707/django-admin-not-seeing-any-app-permission-problem  # noqa
  ... but django.contrib.auth.backends.ModelBackend won't load in INSTALLED_APPS  # noqa
- log.debug(f"registered: {res_admin_site.is_registered(Leaflet)!r}")
  ... OK
  ... and anyway, it works for superusers
- app_list is blank in the template; this is set in AdminSite.index()
  (in django/contrib/admin/sites.py)
  So the failure is either in
        model_admin.has_module_permission(request)
            return request.user.has_module_perms(self.opts.app_label)
    or  model_admin.get_model_perms(request)
  They're in django/contrib/admin/options.py; ModelAdmin and BaseModelAdmin

  From a Werkzeug console in home view:

    from core.admin import LeafletResAdmin
    LeafletResAdmin.has_module_permission(request)
    # ... fails (class not instance!) but shows code, so:
    request.user.has_module_perms('resadmin')
    # ... False - so HERE'S a problem.

  Solution: add these to relevant ModelAdmin classes:

    def has_module_permission(self, request):
        return request.user.is_staff

    def has_change_permission(self, request, obj=None):
        return request.user.is_staff
"""
