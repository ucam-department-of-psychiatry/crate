#!/usr/bin/env python3
# consent/views.py

import logging
logger = logging.getLogger(__name__)
import mimetypes
from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponse, Http404
from django.shortcuts import get_object_or_404, render
from consent.models import Email, EmailAttachment, Leaflet, Study
from consent.storage import privatestorage
from core.nhs import generate_random_nhs_number
from core.utils import (
    is_developer,
    is_superuser,
    serve_concatenated_pdf_from_disk,
    serve_file,
)
from .forms import (
    SingleNhsNumberForm,
    SuperuserSubmitContactRequestForm,
    ResearcherSubmitContactRequestForm,
)
from .models import (
    ClinicianToken,
    ContactRequest,
    lookup_patient,
)


def study_details(request, study_id):
    study = get_object_or_404(Study, pk=study_id)
    return serve_file(study.study_details_pdf.path,
                      content_type="application/pdf",
                      as_inline=True)
study_details.login_required = False


def study_form(request, study_id):
    study = get_object_or_404(Study, pk=study_id)
    return serve_file(study.subject_form_template_pdf.path,
                      content_type="application/pdf",
                      as_inline=True)
study_form.login_required = False


def study_pack(request, study_id):
    study = get_object_or_404(Study, pk=study_id)
    filenames = [
        study.study_details_pdf.path,
        study.subject_form_template_pdf.path
    ]
    return serve_concatenated_pdf_from_disk(
        filenames,
        offered_filename="study_{}_pack.pdf".format(study_id)
    )
study_pack.login_required = False


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


@user_passes_test(is_developer)
def view_email_html(request, email_id):
    email = get_object_or_404(Email, pk=email_id)
    return HttpResponse(email.msg_html)


@user_passes_test(is_developer)
def view_email_attachment(request, attachment_id):
    attachment = get_object_or_404(EmailAttachment, pk=attachment_id)
    return serve_file(attachment.file.path,
                      content_type=attachment.content_type,
                      as_inline=True)


@user_passes_test(is_developer)
def test_patient_lookup(request):
    form = SingleNhsNumberForm(request.POST or None)
    if form.is_valid():
        lookup = lookup_patient(nhs_number=form.cleaned_data['nhs_number'],
                                save=False)
        # Don't use a Form. https://code.djangoproject.com/ticket/17031
        return render(request, 'patient_lookup_result.html',
                      {'lookup': lookup})
    return render(request, 'patient_lookup_get_nhs.html', {'form': form})


def leaflet(request, leaflet_name):
    leaflet = get_object_or_404(Leaflet, name=leaflet_name)
    if not leaflet.pdf:
        raise Http404("Missing leaflet")
    return serve_file(leaflet.pdf.path,
                      content_type="application/pdf",
                      as_inline=True)
leaflet.login_required = False


def clinician_response(request, token):
    token = get_object_or_404(ClinicianToken, token=token)
    contact_request = token.contact_request
    study = contact_request.study
    patient_lookup = contact_request.patient_lookup
    consent_mode = contact_request.consent_mode

    clinician_involvement_requested = (
        contact_request.clinician_involvement
        == ContactRequest.CLINICIAN_INVOLVEMENT_REQUESTED)
    clinician_involvement_required_yellow = (
        contact_request.clinician_involvement
        == ContactRequest.CLINICIAN_INVOLVEMENT_REQUIRED_YELLOW)
    clinician_involvement_required_unknown = (
        contact_request.clinician_involvement
        == ContactRequest.CLINICIAN_INVOLVEMENT_REQUIRED_UNKNOWN)
    option_c_available = clinician_involvement_requested

    if token.used_at:
        clinician_response = token.clinician_response
        return render(request, 'clinician_already_responded.html', {
            'clinician_response': clinician_response,
            'consent_mode': consent_mode,
            'contact_request': contact_request,
            'Leaflet': Leaflet,
            'patient_lookup': patient_lookup,
            'settings': settings,
            'study': study,
        })

    return render(request, 'clinician_response.html', {
        'consent_mode': consent_mode,
        'contact_request': contact_request,
        'Leaflet': Leaflet,
        'patient_lookup': patient_lookup,
        'settings': settings,
        'study': study,

        'clinician_involvement_requested': clinician_involvement_requested,
        'clinician_involvement_required_yellow':
        clinician_involvement_required_yellow,
        'clinician_involvement_required_unknown':
        clinician_involvement_required_unknown,
        'option_c_available': option_c_available,
    })


def submit_contact_request(request):
    if request.user.is_superuser:
        form = SuperuserSubmitContactRequestForm(request.POST or None)
    else:
        form = ResearcherSubmitContactRequestForm(request.user,
                                                  request.POST or None)
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
    return render(request, 'contact_request_result.html',
                  {'contact_requests': contact_requests})
