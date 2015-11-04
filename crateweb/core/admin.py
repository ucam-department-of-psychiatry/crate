#!/usr/bin/env python3
# core/admin.py

import logging
logger = logging.getLogger(__name__)
# from django import forms
from django.conf import settings
from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.template.defaultfilters import yesno
from django.template.loader import render_to_string
from django.utils.translation import ugettext_lazy
from core.extra import (
    AddOnlyModelAdmin,
    EditOnlyModelAdmin,
    disable_bool_icon,
    ReadOnlyModelAdmin,
)
from core.utils import replace_in_list
from userprofile.models import UserProfile
from consent.models import (
    CharityPaymentRecord,
    ClinicianResponse,
    ClinicianToken,
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
from research.models import (
    QueryAudit,
)


# =============================================================================
# Research
# =============================================================================

# -----------------------------------------------------------------------------
# Admin
# -----------------------------------------------------------------------------

class QueryAuditAdmin(ReadOnlyModelAdmin):
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

    def get_sql(self, obj):
        return obj.query.sql
    get_sql.short_description = "SQL"
    get_sql.admin_order_field = 'query__sql'

    def get_user(self, obj):
        return obj.query.user
    get_user.short_description = "User"
    get_user.admin_order_field = 'query__user'

    def get_count_only(self, obj):
        return yesno(obj.count_only)
    get_count_only.short_description = "Count only?"
    get_count_only.admin_order_field = 'count_only'

    def get_failed(self, obj):
        return yesno(obj.failed)
    get_failed.short_description = "Failed?"
    get_failed.admin_order_field = 'failed'


# =============================================================================
# Consent
# =============================================================================

# -----------------------------------------------------------------------------
# Inline
# -----------------------------------------------------------------------------

class StudyInline(admin.TabularInline):
    model = Study


class ConsentModeInline(admin.TabularInline):
    model = ConsentMode


# -----------------------------------------------------------------------------
# Admin
# -----------------------------------------------------------------------------

class ConsentModeAdmin(AddOnlyModelAdmin):
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

    fields = [
        'nhs_number',
        'exclude_entirely', 'consent_mode', 'consent_after_discharge',
        'max_approaches_per_year', 'other_requests', 'prefers_email',
        'changed_by_clinician_override',
    ] + Decision._meta.get_all_field_names()
    list_display = ('id', 'nhs_number', 'consent_mode',
                    'consent_after_discharge')
    list_display_links = ('id', 'nhs_number')
    search_fields = ('nhs_number', )
    list_filter = ('consent_mode', 'consent_after_discharge',
                   'exclude_entirely', 'prefers_email')
    date_hierarchy = 'created_at'

    fields_for_viewing = replace_in_list(fields, {
        'exclude_entirely': 'exclude_entirely2',
        'consent_after_discharge': 'consent_after_discharge2',
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
    def save_model(self, request, obj, form, change):
        obj.created_by = request.user
        obj.save()

    def save_formset(self, request, form, formset, change):
        if formset.model == ConsentMode:
            instances = formset.save(commit=False)
            for instance in instances:
                instance.created_by = request.user
                instance.save()
        else:
            formset.save()

    # Restrict to current ones
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.filter(current=True)

    # *** decision validator


class ConsentModeDevAdmin(ReadOnlyModelAdmin):
    readonly_fields = [
        'nhs_number',
        'current', 'created_at', 'created_by',
        'exclude_entirely', 'consent_mode', 'consent_after_discharge',
        'max_approaches_per_year', 'other_requests', 'prefers_email',
        'changed_by_clinician_override',
    ] + Decision._meta.get_all_field_names()
    fields = readonly_fields
    list_display = ('id', 'current', 'nhs_number', 'consent_mode',
                    'consent_after_discharge')
    search_fields = ('nhs_number', )
    list_filter = ('current', 'consent_mode', 'consent_after_discharge',
                   'exclude_entirely', 'prefers_email')


class LeafletAdmin(EditOnlyModelAdmin):
    fields = ('name', 'pdf')
    readonly_fields = ('name', )


class LeafletResAdmin(ReadOnlyModelAdmin):
    fields = ('name', 'pdf')
    readonly_fields = fields


class StudyAdmin(admin.ModelAdmin):
    fields = (
        'institutional_id',
        'title', 'lead_researcher', 'registered_at', 'summary',
        'search_methods_planned', 'patient_contact', 'include_under_16s',
        'include_lack_capacity', 'clinical_trial', 'include_discharged',
        'request_direct_approach', 'approved_by_rec', 'rec_reference',
        'approved_locally', 'local_approval_at',
        'study_details_pdf', 'subject_form_template_pdf',
        'researchers',
    )
    list_display = ('id', 'institutional_id', 'title', 'lead_researcher')
    list_display_links = ('id', 'institutional_id', 'title')


class StudyResAdmin(ReadOnlyModelAdmin):
    fields = (
        'institutional_id',
        'title', 'lead_researcher', 'registered_at', 'summary',
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
    def get_queryset(self, request):
        user = request.user
        qs = super().get_queryset(request)
        return qs.filter(Q(lead_researcher=user)
                         | Q(researchers__in=[user])).distinct()

    
class EmailAdmin(ReadOnlyModelAdmin):
    model = Email
    readonly_fields = ('id', 'created_at', 'sender', 'recipient',
                       'subject', 'msg_text', 'get_view_msg_html',
                       'get_view_attachments',
                       'sent', 'sent_at', 'failure_reason')
    fields = readonly_fields  # or other things appear
    date_hierarchy = 'created_at'
    list_display = ('id', 'created_at', 'recipient', 'subject', 'sent',
                    'sent_at', 'failure_reason')
    list_filter = ('sent', )
    search_fields = ('recipient', 'subject')

    def get_view_msg_html(self, obj):
        url = reverse('view_email_html', args=[obj.id])
        return '<a href="{}">View HTML message</a> ({} bytes)'.format(
            url, len(obj.msg_html))
    get_view_msg_html.short_description = "Message HTML"
    get_view_msg_html.allow_tags = True

    def get_view_attachments(self, obj):
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
        return html
    get_view_attachments.short_description = "Attachments"
    get_view_attachments.allow_tags = True


class DummyPatientSourceInfoAdmin(admin.ModelAdmin):
    fields = (
        # Patient
        'nhs_number',
        'pt_dob', 'pt_dod', 'pt_dead', 'pt_discharged', 'pt_sex',
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


class PatientLookupAdmin(ReadOnlyModelAdmin):
    readonly_fields = (
        # Lookup details
        'lookup_at', 'source_db', 'nhs_number',

        # Patient
        'pt_dob', 'pt_dod', 'pt_dead', 'pt_discharged', 'pt_sex',
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

        # Decisions
        'decisions', 'secret_decisions',
    )
    fields = readonly_fields
    date_hierarchy = 'lookup_at'
    list_display = ('id', 'nhs_number', 'pt_first_name', 'pt_last_name')
    search_fields = ('nhs_number', 'pt_first_name', 'pt_last_name')


class TeamRepAdmin(admin.ModelAdmin):
    fields = ('team', 'user')
    list_display = ('team', 'user')
    search_fields = ('team', )


class CharityPaymentRecordAdmin(AddOnlyModelAdmin):
    fields = ('payee', 'amount')
    fields_for_viewing = fields
    list_display = ('id', 'created_at', 'payee', 'amount')
    list_display_links = ('id', 'created_at')
    search_fields = ('payee', )
    date_hierarchy = 'created_at'


class ContactRequestAdmin(ReadOnlyModelAdmin):
    fields = ContactRequest._meta.get_all_field_names()
    readonly_fields = fields
    date_hierarchy = 'created_at'


class ClinicianResponseAdmin(ReadOnlyModelAdmin):
    fields = ClinicianResponse._meta.get_all_field_names()
    readonly_fields = fields
    date_hierarchy = 'created_at'


class PatientResponseAdmin(AddOnlyModelAdmin):
    fields = [
        # ***
    ] + Decision._meta.get_all_field_names()
    date_hierarchy = 'created_at'

    # Populate the created_by field automatically, with the two functions below
    def save_model(self, request, obj, form, change):
        obj.created_by = request.user
        obj.save()

    def save_formset(self, request, form, formset, change):
        if formset.model == PatientResponse:
            instances = formset.save(commit=False)
            for instance in instances:
                instance.created_by = request.user
                instance.save()
        else:
            formset.save()

    # *** decision validator


class PatientResponseDevAdmin(ReadOnlyModelAdmin):
    fields = PatientResponse._meta.get_all_field_names()
    readonly_fields = fields
    date_hierarchy = 'created_at'


class ClinicianTokenAdmin(ReadOnlyModelAdmin):
    fields = ClinicianToken._meta.get_all_field_names()
    readonly_fields = fields
    date_hierarchy = 'created_at'


class LetterAdmin(ReadOnlyModelAdmin):
    fields = Letter._meta.get_all_field_names()
    readonly_fields = fields
    date_hierarchy = 'created_at'


# =============================================================================
# User profiles
# =============================================================================

# -----------------------------------------------------------------------------
# Inline
# -----------------------------------------------------------------------------

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    max_num = 1
    can_delete = False
    inlines = [StudyInline]
    fields = ('per_page', 'line_length', 'collapse_at',
              'is_developer',
              'title',
              'telephone',
              'address_1', 'address_2', 'address_3', 'address_4',
              'address_5', 'address_6', 'address_7',
              'get_studies_as_lead', 'get_studies_as_researcher')
    readonly_fields = ('get_studies_as_lead', 'get_studies_as_researcher')

    def get_studies_as_lead(self, obj):
        studies = obj.user.studies_as_lead.all()
        return render_to_string('shortlist_studies.html', {'studies': studies})
    get_studies_as_lead.short_description = "Studies as lead researcher"
    get_studies_as_lead.allow_tags = True

    def get_studies_as_researcher(self, obj):
        studies = obj.user.studies_as_researcher.all()
        return render_to_string('shortlist_studies.html', {'studies': studies})
    get_studies_as_researcher.short_description = "Studies as researcher"
    get_studies_as_researcher.allow_tags = True


# -----------------------------------------------------------------------------
# Admin
# -----------------------------------------------------------------------------

class ExtendedUserAdmin(UserAdmin):
    inlines = [UserProfileInline]


# =============================================================================
# Assemble main admin site
# =============================================================================
# http://stackoverflow.com/questions/4938491/django-admin-change-header-django-administration-text  # noqa
# http://stackoverflow.com/questions/3400641/how-do-i-inline-edit-a-django-user-profile-in-the-admin-interface  # noqa

class CrateAdminSite(admin.AdminSite):
    # Text to put at the end of each page's <title>.
    site_title = ugettext_lazy(settings.RESEARCH_DB_TITLE + ' manager admin')
    # Text to put in each page's <h1>.
    site_header = ugettext_lazy(settings.RESEARCH_DB_TITLE + ": manager admin")
    # Text to put at the top of the admin index page.
    index_title = ugettext_lazy(settings.RESEARCH_DB_TITLE +
                                ' site administration')


admin_site = CrateAdminSite(name="admin")
admin_site.index_template = 'admin/viewchange_admin_index.html'
admin_site.register(CharityPaymentRecord, CharityPaymentRecordAdmin)
admin_site.register(ConsentMode, ConsentModeAdmin)
admin_site.register(Leaflet, LeafletAdmin)
admin_site.register(QueryAudit, QueryAuditAdmin)
admin_site.register(Study, StudyAdmin)
admin_site.register(TeamRep, TeamRepAdmin)
admin_site.register(User, ExtendedUserAdmin)
admin_site.register(PatientResponse, PatientResponseAdmin)
admin_site.register(Letter, LetterAdmin)
# *** letter printing


# =============================================================================
# Assemble secondary (developer) admin site
# =============================================================================
# http://stackoverflow.com/questions/4938491/django-admin-change-header-django-administration-text  # noqa
# http://stackoverflow.com/questions/3400641/how-do-i-inline-edit-a-django-user-profile-in-the-admin-interface  # noqa

class DevAdminSite(admin.AdminSite):
    site_title = ugettext_lazy(settings.RESEARCH_DB_TITLE + ' dev admin')
    site_header = ugettext_lazy(settings.RESEARCH_DB_TITLE
                                + ": developer admin")
    index_title = ugettext_lazy(settings.RESEARCH_DB_TITLE +
                                ' developer administration')


dev_admin_site = DevAdminSite(name="devadmin")
dev_admin_site.index_template = 'admin/viewchange_admin_index.html'
dev_admin_site.register(ConsentMode, ConsentModeDevAdmin)
dev_admin_site.register(DummyPatientSourceInfo, DummyPatientSourceInfoAdmin)
dev_admin_site.register(Email, EmailAdmin)
dev_admin_site.register(PatientLookup, PatientLookupAdmin)
dev_admin_site.register(ContactRequest, ContactRequestAdmin)
dev_admin_site.register(ClinicianResponse, ClinicianResponseAdmin)
dev_admin_site.register(PatientResponse, PatientResponseDevAdmin)
dev_admin_site.register(ClinicianToken, ClinicianTokenAdmin)


# =============================================================================
# Assemble tertiary (researcher) admin site
# =============================================================================

class ResearcherAdminSite(admin.AdminSite):
    site_title = ugettext_lazy(settings.RESEARCH_DB_TITLE
                               + ' researcher admin views')
    site_header = ugettext_lazy(settings.RESEARCH_DB_TITLE
                                + ": researcher admin")
    index_title = ugettext_lazy(settings.RESEARCH_DB_TITLE +
                                ' researcher administration')

res_admin_site = ResearcherAdminSite(name="resadmin")
res_admin_site.index_template = 'admin/viewchange_admin_index.html'
res_admin_site.register(Study, StudyResAdmin)
res_admin_site.register(Leaflet, LeafletResAdmin)
