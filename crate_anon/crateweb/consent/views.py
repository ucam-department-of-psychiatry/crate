#!/usr/bin/env python3
# consent/views.py

import logging
import mimetypes
from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.db import transaction
from django.http import HttpResponse, Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from crate_anon.crateweb.extra.nhs import generate_random_nhs_number
from crate_anon.crateweb.extra.pdf import (
    serve_concatenated_pdf_from_disk,
    serve_html_or_pdf,
)
from crate_anon.crateweb.extra.serve import serve_buffer, serve_file
from crate_anon.crateweb.core.utils import (
    is_developer,
    is_superuser,
)
# from research.models import PidLookup
from crate_anon.crateweb.consent.forms import (
    ClinicianResponseForm,
    SingleNhsNumberForm,
    SuperuserSubmitContactRequestForm,
    ResearcherSubmitContactRequestForm,
)
from crate_anon.crateweb.consent.models import (
    CharityPaymentRecord,
    ClinicianResponse,
    ConsentMode,
    ContactRequest,
    Email,
    EmailAttachment,
    Leaflet,
    Letter,
    lookup_patient,
    PatientLookup,
    Study,
)
from crate_anon.crateweb.consent.storage import privatestorage
from crate_anon.crateweb.consent.tasks import (
    finalize_clinician_response,
    test_email_rdbm_task,
)

log = logging.getLogger(__name__)


# =============================================================================
# Additional validators
# =============================================================================

def validate_email_request(user, email):
    if user.profile.is_developer:
        return  # the developer sees all
    if email.to_researcher:
        # e-mails to clinicians/patients may be restricted
        if user.is_superuser:
            return  # RDBM can see any e-mail to a researcher
        studies = Study.filter_studies_for_researcher(Study.objects.all(),
                                                      user)
        if email.study in studies:
            return  # this e-mail belongs to this researcher
    elif email.to_patient:
        if user.is_superuser:
            return  # RDBM can see any e-mail to a patient
    return HttpResponseForbidden("Not authorized")


def validate_letter_request(user, letter):
    if user.profile.is_developer:
        return  # the developer sees all
    if user.is_superuser:
        return  # RDBM can see any letters generated
    if letter.to_researcher:
        studies = Study.filter_studies_for_researcher(Study.objects.all(),
                                                      user)
        if letter.study in studies:
            return  # this e-mail belongs to this researcher
    return HttpResponseForbidden("Not authorized")


# =============================================================================
# Views
# =============================================================================

# noinspection PyUnusedLocal
def study_details(request, study_id):
    study = get_object_or_404(Study, pk=study_id)
    if not study.study_details_pdf:
        raise Http404("No details")
    return serve_file(study.study_details_pdf.path,
                      content_type="application/pdf",
                      as_inline=True)
study_details.login_required = False


# noinspection PyUnusedLocal
def study_form(request, study_id):
    study = get_object_or_404(Study, pk=study_id)
    if not study.subject_form_template_pdf:
        raise Http404("No study form for clinicians to complete")
    return serve_file(study.subject_form_template_pdf.path,
                      content_type="application/pdf",
                      as_inline=True)
study_form.login_required = False


# noinspection PyUnusedLocal
def study_pack(request, study_id):
    study = get_object_or_404(Study, pk=study_id)
    filenames = filter(None, [
        study.study_details_pdf.path
        if study.study_details_pdf else None,
        study.subject_form_template_pdf.path
        if study.subject_form_template_pdf else None,
    ])
    if not filenames:
        raise Http404("No leaflets")
    return serve_concatenated_pdf_from_disk(
        filenames,
        offered_filename="study_{}_pack.pdf".format(study_id)
    )
study_pack.login_required = False


# noinspection PyUnusedLocal
@user_passes_test(is_superuser)
def download_privatestorage(request, filename):
    """Superuser access function, used for admin interface only."""
    fullpath = privatestorage.path(filename)
    content_type = mimetypes.guess_type(filename, strict=False)[0]
    # ... guess_type returns a (content_type, encoding) tuple
    return serve_file(fullpath, content_type=content_type, as_inline=True)


@user_passes_test(is_developer)
def generate_fake_nhs(request, n=10):
    nhs_numbers = [generate_random_nhs_number()
                   for _ in range(n)]
    return render(request, 'generate_fake_nhs.html', {
        'nhs_numbers': nhs_numbers
    })


def view_email_html(request, email_id):
    email = get_object_or_404(Email, pk=email_id)
    validate_email_request(request.user, email)
    return HttpResponse(email.msg_html)


def view_email_attachment(request, attachment_id):
    attachment = get_object_or_404(EmailAttachment, pk=attachment_id)
    validate_email_request(request.user, attachment.email)
    if not attachment.file:
        raise Http404("Attachment missing")
    return serve_file(attachment.file.path,
                      content_type=attachment.content_type,
                      as_inline=True)


@user_passes_test(is_developer)
def test_patient_lookup(request):
    form = SingleNhsNumberForm(
        request.POST if request.method == 'POST' else None)
    if form.is_valid():
        lookup = lookup_patient(nhs_number=form.cleaned_data['nhs_number'],
                                save=False)
        # Don't use a Form. https://code.djangoproject.com/ticket/17031
        return render(request, 'patient_lookup_result.html',
                      {'lookup': lookup})
    return render(request, 'patient_lookup_get_nhs.html', {'form': form})


# noinspection PyUnusedLocal
def view_leaflet(request, leaflet_name):
    leaflet = get_object_or_404(Leaflet, name=leaflet_name)
    if not leaflet.pdf:
        raise Http404("Missing leaflet")
    return serve_file(leaflet.pdf.path,
                      content_type="application/pdf",
                      as_inline=True)
view_leaflet.login_required = False


def view_letter(request, letter_id):
    letter = get_object_or_404(Letter, pk=letter_id)
    validate_letter_request(request.user, letter)
    if not letter.pdf:
        raise Http404("Missing letter")
    return serve_file(letter.pdf.path,
                      content_type="application/pdf",
                      as_inline=True)


def submit_contact_request(request):
    if request.user.is_superuser:
        form = SuperuserSubmitContactRequestForm(
            request.POST if request.method == 'POST' else None)
    else:
        form = ResearcherSubmitContactRequestForm(
            request.user,
            request.POST if request.method == 'POST' else None)
    if not form.is_valid():
        return render(request, 'contact_request_submit.html', {'form': form})

    study = form.cleaned_data['study']
    request_direct_approach = form.cleaned_data['request_direct_approach']
    contact_requests = []

    # NHS numbers
    if request.user.is_superuser:
        for nhs_number in form.cleaned_data['nhs_numbers']:
            contact_requests.append(
                ContactRequest.create(
                    request=request,
                    study=study,
                    request_direct_approach=request_direct_approach,
                    lookup_nhs_number=nhs_number))
    # RIDs
    for rid in form.cleaned_data['rids']:
        contact_requests.append(
            ContactRequest.create(
                request=request,
                study=study,
                request_direct_approach=request_direct_approach,
                lookup_rid=rid))
    # MRIDs
    for mrid in form.cleaned_data['mrids']:
        contact_requests.append(
            ContactRequest.create(
                request=request,
                study=study,
                request_direct_approach=request_direct_approach,
                lookup_mrid=mrid))

    # Show results.
    # Don't use a Form. https://code.djangoproject.com/ticket/17031
    return render(request, 'contact_request_result.html', {
        'contact_requests': contact_requests,
    })


def finalize_clinician_response_in_background(request, clinician_response):
    clinician_response.finalize_a()  # first part of processing
    transaction.on_commit(
        lambda: finalize_clinician_response.delay(clinician_response.id)
    )  # Asynchronous
    return render(request, 'clinician_confirm_response.html', {
        'clinician_response': clinician_response,
    })


def clinician_response_view(request, clinician_response_id):
    """
    REC DOCUMENTS 09, 11, 13 (B): Web form for clinicians to respond with
    """
    clinician_response = get_object_or_404(ClinicianResponse,
                                           pk=clinician_response_id)
    contact_request = clinician_response.contact_request
    study = contact_request.study
    patient_lookup = contact_request.patient_lookup
    consent_mode = contact_request.consent_mode

    # Build form.
    # - We have an existing clinician_response and wish to modify it
    #   (potentially).
    # - If the clinician is responding to an e-mail, they will be passing
    #   a couple of parameters (including the token) via GET query parameters.
    #   If they're clicking "Submit", they'll be using POST.
    if request.method == 'GET':
        from_email = True
        clinician_response.response_route = ClinicianResponse.ROUTE_EMAIL
        data = request.GET
    else:
        from_email = False
        clinician_response.response_route = ClinicianResponse.ROUTE_WEB
        data = request.POST
    form = ClinicianResponseForm(instance=clinician_response, data=data)
    # log.debug("Form data: {}".format(form.data))

    # Token valid? Check raw data. Say goodbye otherwise.
    # - The raw data in the form is not influenced by the form's instance.
    if form.data['token'] != clinician_response.token:
        return HttpResponseForbidden(
            "Not authorized. The token you passed doesn't match the one you "
            "were sent.")

    # Already responded?
    if clinician_response.responded:
        passed_to_pt = (clinician_response.response ==
                        ClinicianResponse.RESPONSE_A)
        return render(request, 'clinician_already_responded.html', {
            'ClinicianResponse': ClinicianResponse,
            'clinician_response': clinician_response,
            'consent_mode': consent_mode,
            'contact_request': contact_request,
            'Leaflet': Leaflet,
            'passed_to_pt': passed_to_pt,
            'patient_lookup': patient_lookup,
            'settings': settings,
            'study': study,
        })

    # Is the clinician saying yes or no (direct from e-mail)?
    if (from_email and form.data['email_choice'] in [
            ClinicianResponse.EMAIL_CHOICE_Y,
            ClinicianResponse.EMAIL_CHOICE_N]):
        # We can't use form.save() as the data may not validate.
        # It won't validate because the response/clinician name is blank.
        # We can't write to the form directly. So...
        clinician_response.email_choice = form.data['email_choice']
        if clinician_response.email_choice == ClinicianResponse.EMAIL_CHOICE_Y:
            # Ask RDBM to do the work
            clinician_response.response = ClinicianResponse.RESPONSE_R
        else:
            # Veto on clinical grounds
            clinician_response.response = ClinicianResponse.RESPONSE_B
        return finalize_clinician_response_in_background(request,
                                                         clinician_response)

    # Has the clinician made a decision via the web form?
    if form.is_valid():
        clinician_response = form.save(commit=False)  # return unsaved instance
        return finalize_clinician_response_in_background(request,
                                                         clinician_response)

    # If we get here, we need to offer the form up for editing,
    # and mark it as a web response.
    clinician_involvement_requested = (
        contact_request.clinician_involvement ==
        ContactRequest.CLINICIAN_INVOLVEMENT_REQUESTED)
    clinician_involvement_required_yellow = (
        contact_request.clinician_involvement ==
        ContactRequest.CLINICIAN_INVOLVEMENT_REQUIRED_YELLOW)
    clinician_involvement_required_unknown = (
        contact_request.clinician_involvement ==
        ContactRequest.CLINICIAN_INVOLVEMENT_REQUIRED_UNKNOWN)
    extra_form = contact_request.is_extra_form()
    return render(request, 'clinician_response.html', {
        'clinician_response': clinician_response,
        'ClinicianResponse': ClinicianResponse,
        'consent_mode': consent_mode,
        'contact_request': contact_request,
        'Leaflet': Leaflet,
        'patient_lookup': patient_lookup,
        'settings': settings,
        'study': study,

        'form': form,

        'clinician_involvement_requested': clinician_involvement_requested,
        'clinician_involvement_required_yellow':
        clinician_involvement_required_yellow,
        'clinician_involvement_required_unknown':
        clinician_involvement_required_unknown,
        'option_c_available': clinician_involvement_requested,
        'option_r_available': not extra_form,
        'extra_form': extra_form,
        'unknown_consent_mode': contact_request.is_consent_mode_unknown(),
    })

clinician_response_view.login_required = False


# noinspection PyUnusedLocal
def clinician_pack(request, clinician_response_id, token):
    clinician_response = get_object_or_404(ClinicianResponse,
                                           pk=clinician_response_id)
    contact_request = clinician_response.contact_request
    # Check token authentication
    if token != clinician_response.token:
        return HttpResponseForbidden(
            "Not authorized. The token you passed doesn't match the one you "
            "were sent.")
    # Build and serve
    pdf = contact_request.get_clinician_pack_pdf()
    offered_filename = "clinician_pack_{}.pdf".format(clinician_response_id)
    return serve_buffer(pdf,
                        offered_filename=offered_filename,
                        content_type="application/pdf",
                        as_attachment=False,
                        as_inline=True)

clinician_pack.login_required = False


# -----------------------------------------------------------------------------
# Draft e-mails
# -----------------------------------------------------------------------------

# noinspection PyUnusedLocal
@user_passes_test(is_developer)
def draft_clinician_email(request, contact_request_id):
    contact_request = get_object_or_404(ContactRequest, id=contact_request_id)
    return HttpResponse(
        contact_request.get_clinician_email_html(save=False)
    )


# noinspection PyUnusedLocal
@user_passes_test(is_developer)
def draft_approval_email(request, contact_request_id):
    contact_request = get_object_or_404(ContactRequest, id=contact_request_id)
    return HttpResponse(contact_request.get_approval_email_html())


# noinspection PyUnusedLocal
@user_passes_test(is_developer)
def draft_withdrawal_email(request, contact_request_id):
    contact_request = get_object_or_404(ContactRequest, id=contact_request_id)
    return HttpResponse(contact_request.get_withdrawal_email_html())


# -----------------------------------------------------------------------------
# Draft letters
# -----------------------------------------------------------------------------

# noinspection PyUnusedLocal
@user_passes_test(is_developer)
def draft_approval_letter(request, contact_request_id, viewtype):
    contact_request = get_object_or_404(ContactRequest, id=contact_request_id)
    html = contact_request.get_approval_letter_html()
    return serve_html_or_pdf(html, viewtype)


# noinspection PyUnusedLocal
@user_passes_test(is_developer)
def draft_withdrawal_letter(request, contact_request_id, viewtype):
    contact_request = get_object_or_404(ContactRequest, id=contact_request_id)
    html = contact_request.get_withdrawal_letter_html()
    return serve_html_or_pdf(html, viewtype)


# noinspection PyUnusedLocal
@user_passes_test(is_developer)
def draft_first_traffic_light_letter(request, patient_lookup_id, viewtype):
    patient_lookup = get_object_or_404(PatientLookup, id=patient_lookup_id)
    html = patient_lookup.get_first_traffic_light_letter_html()
    return serve_html_or_pdf(html, viewtype)


# noinspection PyUnusedLocal
@user_passes_test(is_developer)
def draft_confirm_traffic_light_letter(request, consent_mode_id, viewtype):
    consent_mode = get_object_or_404(ConsentMode, id=consent_mode_id)
    html = consent_mode.get_confirm_traffic_to_patient_letter_html()
    return serve_html_or_pdf(html, viewtype)


# noinspection PyUnusedLocal
@user_passes_test(is_developer)
def draft_letter_clinician_to_pt_re_study(request, contact_request_id,
                                          viewtype):
    contact_request = get_object_or_404(ContactRequest, id=contact_request_id)
    html = contact_request.get_letter_clinician_to_pt_re_study()
    return serve_html_or_pdf(html, viewtype)


# noinspection PyUnusedLocal
@user_passes_test(is_developer)
def decision_form_to_pt_re_study(request, contact_request_id, viewtype):
    contact_request = get_object_or_404(ContactRequest, id=contact_request_id)
    html = contact_request.get_decision_form_to_pt_re_study()
    return serve_html_or_pdf(html, viewtype)


@user_passes_test(is_superuser)
def charity_report(request):
    responses = ClinicianResponse.objects.filter(charity_amount_due__gt=0)
    payments = CharityPaymentRecord.objects.all()
    total_due = sum([x.charity_amount_due for x in responses])
    total_paid = sum([x.amount for x in payments])
    outstanding = total_due - total_paid
    return render(request, 'charity_report.html', {
        'responses': responses,
        'payments': payments,
        'total_due': total_due,
        'total_paid': total_paid,
        'outstanding': outstanding,
    })


@user_passes_test(is_superuser)
def exclusion_report(request):
    consent_modes = ConsentMode.objects.filter(current=True,
                                               exclude_entirely=True)
    return render(request, 'exclusion_report.html', {
        'consent_modes': consent_modes,
    })


@user_passes_test(is_superuser)
def test_email_rdbm(request):
    test_email_rdbm_task.delay()
    return render(request, 'test_email_rdbm_ack.html', {
        'settings': settings,
    })
