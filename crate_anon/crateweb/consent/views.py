#!/usr/bin/env python

"""
crate_anon/crateweb/consent/views.py

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

**Django views for the consent-to-contact system.**

"""

import logging
import mimetypes
from typing import List

from cardinal_pythonlib.django.serve import (
    serve_buffer,
    serve_concatenated_pdf_from_disk,
    serve_file,
)
from cardinal_pythonlib.nhs import generate_random_nhs_number
from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse, Http404, HttpResponseForbidden
from django.http.response import HttpResponseBase
from django.http.request import HttpRequest
from django.shortcuts import get_object_or_404, render

from crate_anon.common.contenttypes import ContentType
from crate_anon.crateweb.consent.forms import (
    ClinicianResponseForm,
    SingleNhsNumberForm,
    SuperuserSubmitContactRequestForm,
    ResearcherSubmitContactRequestForm,
    ClinicianSubmitContactRequestForm,
)
from crate_anon.crateweb.consent.lookup import lookup_consent, lookup_patient
from crate_anon.crateweb.consent.models import (
    CharityPaymentRecord,
    ClinicianResponse,
    ConsentMode,
    ContactRequest,
    Email,
    EmailAttachment,
    Leaflet,
    Letter,
    make_dummy_objects,
    PatientLookup,
    Study,
    TEST_ID_STR,
)
from crate_anon.crateweb.consent.storage import privatestorage
from crate_anon.crateweb.consent.tasks import (
    finalize_clinician_response,
    test_email_rdbm_task,
)
from crate_anon.crateweb.consent.utils import days_to_years
from crate_anon.crateweb.core.utils import (
    is_developer,
    is_superuser,
)
from crate_anon.crateweb.extra.pdf import serve_html_or_pdf
from crate_anon.crateweb.research.research_db_info import research_database_info  # noqa
from crate_anon.crateweb.research.models import PidLookup, get_mpid
from crate_anon.crateweb.userprofile.models import UserProfile

log = logging.getLogger(__name__)


# =============================================================================
# Additional validators
# =============================================================================

def validate_email_request(user: settings.AUTH_USER_MODEL,
                           email: Email) -> None:
    """
    Checks that the current user has permission to view the specified e-mail.

    Args:class
        user: current Django user object
        email: :class:`crate_anon.crateweb.consent.models.Email`

    Raises:
        :exc:`django.core.exceptions.PermissionDenied` on failure

    """
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
    raise PermissionDenied("Not authorized")


def validate_letter_request(user: settings.AUTH_USER_MODEL,
                            letter: Letter) -> None:
    """
    Checks that the current user has permission to view the specified letter.

    Args:
        user: current Django user object
        letter: :class:`crate_anon.crateweb.consent.models.Letter`

    Raises:
        :exc:`django.core.exceptions.PermissionDenied` on failure

    """
    if user.profile.is_developer:
        return  # the developer sees all
    if user.is_superuser:
        return  # RDBM can see any letters generated
    if letter.to_researcher:
        studies = Study.filter_studies_for_researcher(Study.objects.all(),
                                                      user)
        if letter.study in studies:
            return  # this e-mail belongs to this researcher
    raise PermissionDenied("Not authorized")


# =============================================================================
# Fetchers
# =============================================================================

def get_contact_request(request: HttpRequest,
                        contact_request_id: str) -> ContactRequest:
    """
    Return the specified contact request.

    Args:
        request: the :class:`django.http.request.HttpRequest`
        contact_request_id: PK

    Returns:
        :class:`crate_anon.crateweb.consent.models.ContactRequest`

    Raises:
        :exc:`django.http.Http404` if not found
    """
    if contact_request_id == TEST_ID_STR:
        return make_dummy_objects(request).contact_request
    return get_object_or_404(
        ContactRequest, id=contact_request_id)  # type: ContactRequest


def get_patient_lookup(request: HttpRequest,
                       patient_lookup_id: str) -> PatientLookup:
    """
    Return the specified patient lookup.

    Args:
        request: the :class:`django.http.request.HttpRequest`
        patient_lookup_id: PK

    Returns:
        :class:`crate_anon.crateweb.consent.models.PatientLookup`

    Raises:
        :exc:`django.http.Http404` if not found
    """
    if patient_lookup_id == TEST_ID_STR:
        return make_dummy_objects(request).patient_lookup
    return get_object_or_404(
        PatientLookup, id=patient_lookup_id)  # type: PatientLookup


def get_consent_mode(request: HttpRequest,
                     consent_mode_id: str) -> ConsentMode:
    """
    Return the specified consent mode.

    Args:
        request: the :class:`django.http.request.HttpRequest`
        consent_mode_id: PK

    Returns:
        :class:`crate_anon.crateweb.consent.models.ConsentMode`

    Raises:
        :exc:`django.http.Http404` if not found
    """
    if consent_mode_id == TEST_ID_STR:
        return make_dummy_objects(request).consent_mode
    return get_object_or_404(
        ConsentMode, id=consent_mode_id)  # type: ConsentMode


# =============================================================================
# Views
# =============================================================================

# noinspection PyUnusedLocal
def study_details(request: HttpRequest, study_id: str) -> HttpResponseBase:
    """
    View details of a study.

    Args:
        request: the :class:`django.http.request.HttpRequest`
        study_id: PK for :class:`crate_anon.crateweb.consent.models.Study`
    """
    if study_id == TEST_ID_STR:
        study = make_dummy_objects(request).study
    else:
        study = get_object_or_404(Study, pk=study_id)  # type: Study
    if not study.study_details_pdf:
        raise Http404("No details")
    # noinspection PyUnresolvedReferences
    return serve_file(study.study_details_pdf.path,
                      content_type=ContentType.PDF,
                      as_inline=True)


study_details.login_required = False


# noinspection PyUnusedLocal
def study_form(request: HttpRequest, study_id: str) -> HttpResponseBase:
    """
    For a study, view the PDF form that researchers would like clinicians to
    complete.

    Args:
        request: the :class:`django.http.request.HttpRequest`
        study_id: PK for :class:`crate_anon.crateweb.consent.models.Study`
    """
    study = get_object_or_404(Study, pk=study_id)  # type: Study
    if not study.subject_form_template_pdf:
        raise Http404("No study form for clinicians to complete")
    # noinspection PyUnresolvedReferences
    return serve_file(study.subject_form_template_pdf.path,
                      content_type=ContentType.PDF,
                      as_inline=True)


study_form.login_required = False


# noinspection PyUnusedLocal
def study_pack(request: HttpRequest, study_id: str) -> HttpResponseBase:
    """
    View a PDF "pack" for a study, including the study details and its
    additional form for clinicians, if provided.

    Args:
        request: the :class:`django.http.request.HttpRequest`
        study_id: PK for :class:`crate_anon.crateweb.consent.models.Study`
    """
    study = get_object_or_404(Study, pk=study_id)  # type: Study
    # noinspection PyUnresolvedReferences
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
        offered_filename=f"study_{study_id}_pack.pdf"
    )


study_pack.login_required = False


# noinspection PyUnusedLocal
@user_passes_test(is_superuser)
def download_privatestorage(request: HttpRequest,
                            filename: str) -> HttpResponseBase:
    """
    Download a file from the private storage area.

    Superuser access function, used for admin interface only.

    Args:
        request: the :class:`django.http.request.HttpRequest`
        filename: filename within the private storage area
    """
    fullpath = privatestorage.path(filename)
    content_type = mimetypes.guess_type(filename, strict=False)[0]
    # ... guess_type returns a (content_type, encoding) tuple
    return serve_file(fullpath, content_type=content_type, as_inline=True)


@user_passes_test(is_developer)
def generate_random_nhs(request: HttpRequest, n: str = 10) -> HttpResponse:
    """
    Display random NHS numbers to the requestor.

    Args:
        request: the :class:`django.http.request.HttpRequest`
        n: how many random NHS numbers to generate?
    """
    nhs_numbers = [generate_random_nhs_number()
                   for _ in range(int(n))]
    return render(request, 'generate_random_nhs.html', {
        'nhs_numbers': nhs_numbers
    })


def view_email_html(request: HttpRequest, email_id: str) -> HttpResponse:
    """
    View the HTML for an e-mail.

    Args:
        request: the :class:`django.http.request.HttpRequest`
        email_id: PK for :class:`crate_anon.crateweb.consent.models.Email`

    Raises:
        :exc:`django.http.Http404` if not found
    """
    email = get_object_or_404(Email, pk=email_id)  # type: Email
    # noinspection PyTypeChecker
    validate_email_request(request.user, email)
    return HttpResponse(email.msg_html)


def view_email_attachment(request: HttpRequest,
                          attachment_id: str) -> HttpResponseBase:
    """
    View the HTML for an e-mail.

    Args:
        request: the :class:`django.http.request.HttpRequest`
        attachment_id: PK for
            :class:`crate_anon.crateweb.consent.models.EmailAttachment`

    Raises:
        :exc:`django.http.Http404` if not found
    """
    attachment = get_object_or_404(EmailAttachment, pk=attachment_id)  # type: EmailAttachment  # noqa
    # noinspection PyTypeChecker
    validate_email_request(request.user, attachment.email)
    if not attachment.file:
        raise Http404("Attachment missing")
    return serve_file(attachment.file.path,
                      content_type=attachment.content_type,
                      as_inline=True)


@user_passes_test(is_developer)
def test_patient_lookup(request: HttpRequest) -> HttpResponse:
    """
    Looks up a patient's details and shows the results without saving the
    lookup.

    Args:
        request: the :class:`django.http.request.HttpRequest`
    """
    form = SingleNhsNumberForm(
        request.POST if request.method == 'POST' else None)
    if form.is_valid():
        lookup = lookup_patient(nhs_number=form.cleaned_data['nhs_number'],
                                save=False)
        # Don't use a Form. https://code.djangoproject.com/ticket/17031
        return render(request, 'patient_lookup_result.html',
                      {'lookup': lookup})
    return render(request, 'patient_lookup_get_nhs.html', {'form': form})


@user_passes_test(is_developer)
def test_consent_lookup(request: HttpRequest) -> HttpResponse:
    """
    Looks up a patient's consent mode and shows the results without saving the
    lookup.

    Args:
        request: the :class:`django.http.request.HttpRequest`
    """
    form = SingleNhsNumberForm(
        request.POST if request.method == 'POST' else None)
    if form.is_valid():
        decisions = []  # type: List[str]
        nhs_number = form.cleaned_data['nhs_number']
        consent_mode = lookup_consent(nhs_number=nhs_number,
                                      decisions=decisions)
        # Don't use a Form. https://code.djangoproject.com/ticket/17031
        return render(
            request,
            'consent_lookup_result.html',
            {
                'consent_mode': consent_mode,
                'nhs_number': nhs_number,
                'decisions': decisions,
            }
        )
    return render(request, 'consent_lookup_get_nhs.html', {'form': form})


# noinspection PyUnusedLocal
def view_leaflet(request: HttpRequest, leaflet_name: str) -> HttpResponseBase:
    """
    Views a system-wide leaflet.

    Args:
        request: the :class:`django.http.request.HttpRequest`
        leaflet_name: name of the leaflet; see
            :class:`crate_anon.crateweb.consent.models.Leaflet`
    """
    leaflet = get_object_or_404(Leaflet, name=leaflet_name)  # type: Leaflet
    if not leaflet.pdf:
        raise Http404("Missing leaflet")
    # noinspection PyUnresolvedReferences
    return serve_file(leaflet.pdf.path,
                      content_type=ContentType.PDF,
                      as_inline=True)


view_leaflet.login_required = False


def view_letter(request: HttpRequest, letter_id: str) -> HttpResponseBase:
    """
    View a letter (as a PDF).

    Args:
        request: the :class:`django.http.request.HttpRequest`
        letter_id: PK for :class:`crate_anon.crateweb.consent.models.Letter`

    Raises:
        :exc:`django.http.Http404` if not found
    """
    letter = get_object_or_404(Letter, pk=letter_id)  # type: Letter
    # noinspection PyTypeChecker
    validate_letter_request(request.user, letter)
    if not letter.pdf:
        raise Http404("Missing letter")
    return serve_file(letter.pdf.path,
                      content_type=ContentType.PDF,
                      as_inline=True)


def submit_contact_request(request: HttpRequest) -> HttpResponse:
    """
    Submits a contact request for a study, potentially for multiple patients.

    Args:
        request: the :class:`django.http.request.HttpRequest`
    """
    dbinfo = research_database_info.dbinfo_for_contact_lookup
    if request.user.is_superuser:
        form = SuperuserSubmitContactRequestForm(
            request.POST if request.method == 'POST' else None,
            dbinfo=dbinfo)
    else:
        form = ResearcherSubmitContactRequestForm(
            user=request.user,
            data=request.POST if request.method == 'POST' else None,
            dbinfo=dbinfo)
    if not form.is_valid():
        return render(request, 'contact_request_submit.html', {
            'db_description': dbinfo.description,
            'form': form,
        })

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


def clinician_initiated_contact_request(request: HttpRequest) -> HttpResponse:
    """
    For clinicians to request that their patient is contacted about a study.

    Args:
        request: the :class:`django.http.request.HttpRequest`
    """
    dbinfo = research_database_info.dbinfo_for_contact_lookup
    email = request.user.email
    userprofile = UserProfile.objects.get(user=request.user)
    title = userprofile.title
    firstname = request.user.first_name
    lastname = request.user.last_name
    form = ClinicianSubmitContactRequestForm(
            data=request.POST if request.method == 'POST' else None,
            dbinfo=dbinfo,
            email_addr=email,
            title=title,
            firstname=firstname,
            lastname=lastname)
    if not form.is_valid():
        return render(request, 'clinician_contact_request_submit.html', {
            'db_description': dbinfo.description,
            'form': form,
            'permitted_to_contact_discharged_patients_for_n_days':
                settings.PERMITTED_TO_CONTACT_DISCHARGED_PATIENTS_FOR_N_DAYS,
            'permitted_to_contact_discharged_patients_for_n_years':
                days_to_years(
                    settings.PERMITTED_TO_CONTACT_DISCHARGED_PATIENTS_FOR_N_DAYS),  # noqa
        })
    study = form.cleaned_data['study']
    let_rdbm_contact_pt = form.cleaned_data['let_rdbm_contact_pt']
    signatory_name = "{} {} {}".format(form.cleaned_data['title'],
                                       form.cleaned_data['firstname'],
                                       form.cleaned_data['lastname'])
    signatory_title = form.cleaned_data['signatory_title']
    contact_requests = []
    msgs = []

    # NHS numbers
    for nhs_number in form.cleaned_data['nhs_numbers']:
        patient = PatientLookup.objects.filter(nhs_number=nhs_number).first()
        if patient:
            contact_requests.append(
                ContactRequest.create(
                    request=request,
                    study=study,
                    request_direct_approach=False,
                    lookup_nhs_number=nhs_number,
                    clinician_initiated=True,
                    clinician_email=form.cleaned_data['email'],
                    rdbm_to_contact_pt=let_rdbm_contact_pt,
                    clinician_signatory_name=signatory_name,
                    clinician_signatory_title=signatory_title
                )
            )
        else:
            msgs.append("Patient with nhs number {} does not exist".format(
                nhs_number))

    # RIDs
    for rid in form.cleaned_data['rids']:
        patient_does_not_exist = False
        try:
            get_mpid(dbinfo=dbinfo, rid=rid)
        except PidLookup.DoesNotExist:
            msgs.append("Patient with rid {} does not exist".format(rid))
            patient_does_not_exist = True
        if not patient_does_not_exist:
            contact_requests.append(
                ContactRequest.create(
                    request=request,
                    study=study,
                    request_direct_approach=False,
                    lookup_rid=rid,
                    clinician_initiated=True,
                    clinician_email=form.cleaned_data['email'],
                    rdbm_to_contact_pt=let_rdbm_contact_pt,
                    clinician_signatory_name=signatory_name,
                    clinician_signatory_title=signatory_title
                )
            )

    # MRIDs
    for mrid in form.cleaned_data['mrids']:
        patient_does_not_exist = False
        try:
            get_mpid(dbinfo=dbinfo, mrid=mrid)
        except PidLookup.DoesNotExist:
            msgs.append("Patient with mrid {} does not exist".format(mrid))
            patient_does_not_exist = True
        if not patient_does_not_exist:
            contact_requests.append(
                ContactRequest.create(
                    request=request,
                    study=study,
                    request_direct_approach=False,
                    lookup_mrid=mrid,
                    clinician_initiated=True,
                    clinician_email=form.cleaned_data['email'],
                    rdbm_to_contact_pt=let_rdbm_contact_pt,
                    clinician_signatory_name=signatory_name,
                    clinician_signatory_title=signatory_title
                )
            )

    # for contact_request in contact_requests:
    #     # consent_mode = contact_request.consent_mode.consent_mode
    #     # if (consent_mode == ConsentMode.GREEN or
    #     #         consent_mode == ConsentMode.YELLOW):
    #     generate_automatic_yes.delay(
    #         contact_request.id,
    #         rdbm_to_contact_pt=let_rdbm_contact_pt)
            
    return render(request, 'clinician_contact_request_result.html', {
        'contact_requests': contact_requests,
        'msgs': msgs,
        'let_rdbm_contact_pt': let_rdbm_contact_pt,
    })


def finalize_clinician_response_in_background(
        request: HttpRequest,
        clinician_response: ClinicianResponse) -> HttpResponse:
    """
    Submits a background processing job to complete processing a clinician's
    response, and return a short thank-you response to the clinician.

    Args:
        request: the :class:`django.http.request.HttpRequest`
        clinician_response:
            :class:`crate_anon.crateweb.consent.models.ClinicianResponse`
            object
    """
    clinician_response.finalize_a()  # first part of processing
    transaction.on_commit(
        lambda: finalize_clinician_response.delay(clinician_response.id)
    )  # Asynchronous
    return render(request, 'clinician_confirm_response.html', {
        'clinician_response': clinician_response,
    })


def clinician_response_view(request: HttpRequest,
                            clinician_response_id: str) -> HttpResponse:
    """
    Shows the response choices to the clinician. They'll get here by clicking
    on a link in an e-mail.

    **REC DOCUMENTS 09, 11, 13 (B): Web form for clinicians to respond with.**

    Args:
        request: the :class:`django.http.request.HttpRequest`
        clinician_response_id: PK for
            :class:`crate_anon.crateweb.consent.models.ClinicianResponse`
    """
    if clinician_response_id == TEST_ID_STR:
        dummies = make_dummy_objects(request)
        clinician_response = dummies.clinician_response
        contact_request = dummies.contact_request
        study = dummies.study
        patient_lookup = dummies.patient_lookup
        consent_mode = dummies.consent_mode
    else:
        clinician_response = get_object_or_404(
            ClinicianResponse, pk=clinician_response_id)  # type: ClinicianResponse  # noqa
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
        # log.critical("Token from user: {!r}".format(form.data['token']))
        # log.critical("Original token: {!r}".format(clinician_response.token))
        return HttpResponseForbidden(
            "Not authorized. The token you passed doesn't match the one you "
            "were sent.")

    # Already responded?
    if clinician_response.responded:
        passed_to_pt = (clinician_response.response ==
                        ClinicianResponse.RESPONSE_A)
        return render(request, 'clinician_already_responded.html', {
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
    if (from_email and form.data['email_choice'] in (
            ClinicianResponse.EMAIL_CHOICE_Y,
            ClinicianResponse.EMAIL_CHOICE_N)):
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

        'permitted_to_contact_discharged_patients_for_n_days':
            settings.PERMITTED_TO_CONTACT_DISCHARGED_PATIENTS_FOR_N_DAYS,
        'permitted_to_contact_discharged_patients_for_n_years':
            days_to_years(
                settings.PERMITTED_TO_CONTACT_DISCHARGED_PATIENTS_FOR_N_DAYS),
    })


clinician_response_view.login_required = False


# noinspection PyUnusedLocal
def clinician_pack(request: HttpRequest,
                   clinician_response_id: str,
                   token: str) -> HttpResponse:
    """
    Shows a clinician "pack" as a PDF, including a letter from them to the
    patient, details of the study, forms for the patient to respond, etc.

    Args:
        request: the :class:`django.http.request.HttpRequest`
        clinician_response_id: PK for
            :class:`crate_anon.crateweb.consent.models.ClinicianResponse`
        token: security token (which we'll check against the one we sent to
            the clinician)
    """
    if clinician_response_id == TEST_ID_STR:
        dummies = make_dummy_objects(request)
        clinician_response = dummies.clinician_response
        contact_request = dummies.contact_request
    else:
        clinician_response = get_object_or_404(
            ClinicianResponse, pk=clinician_response_id)  # type: ClinicianResponse  # noqa
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
                        content_type=ContentType.PDF,
                        as_attachment=False,
                        as_inline=True)


clinician_pack.login_required = False


# -----------------------------------------------------------------------------
# Draft e-mails
# -----------------------------------------------------------------------------

@user_passes_test(is_developer)
def draft_clinician_email(request: HttpRequest,
                          contact_request_id: str) -> HttpResponse:
    """
    Developer view: draft e-mail to clinician.

    Args:
        request: the :class:`django.http.request.HttpRequest`
        contact_request_id: PK for
            :class:`crate_anon.crateweb.consent.models.ContactRequest`
    """
    contact_request = get_contact_request(request, contact_request_id)
    return HttpResponse(
        contact_request.get_clinician_email_html(save=False)
    )


@user_passes_test(is_developer)
def draft_approval_email(request: HttpRequest,
                         contact_request_id: str) -> HttpResponse:
    """
    Developer view: draft e-mail to researcher, giving permission.

    Args:
        request: the :class:`django.http.request.HttpRequest`
        contact_request_id: PK for
            :class:`crate_anon.crateweb.consent.models.ContactRequest`
    """
    contact_request = get_contact_request(request, contact_request_id)
    return HttpResponse(contact_request.get_approval_email_html())


@user_passes_test(is_developer)
def draft_withdrawal_email(request: HttpRequest,
                           contact_request_id: str) -> HttpResponse:
    """
    Developer view: draft e-mail to researcher, withdrawing permission.

    Args:
        request: the :class:`django.http.request.HttpRequest`
        contact_request_id: PK for
            :class:`crate_anon.crateweb.consent.models.ContactRequest`
    """
    contact_request = get_contact_request(request, contact_request_id)
    return HttpResponse(contact_request.get_withdrawal_email_html())


# -----------------------------------------------------------------------------
# Draft letters
# -----------------------------------------------------------------------------

@user_passes_test(is_developer)
def draft_approval_letter(request: HttpRequest,
                          contact_request_id: str,
                          viewtype: str) -> HttpResponse:
    """
    Developer view: draft letter to researcher, giving permission.

    Args:
        request: the :class:`django.http.request.HttpRequest`
        contact_request_id: PK for
            :class:`crate_anon.crateweb.consent.models.ContactRequest`
        viewtype: ``"pdf"`` or ``"html"``
    """
    contact_request = get_contact_request(request, contact_request_id)
    html = contact_request.get_approval_letter_html()
    return serve_html_or_pdf(html, viewtype)


@user_passes_test(is_developer)
def draft_withdrawal_letter(request: HttpRequest,
                            contact_request_id: str,
                            viewtype: str) -> HttpResponse:
    """
    Developer view: draft letter to researcher, withdrawing permission.

    Args:
        request: the :class:`django.http.request.HttpRequest`
        contact_request_id: PK for
            :class:`crate_anon.crateweb.consent.models.ContactRequest`
        viewtype: ``"pdf"`` or ``"html"``
    """
    contact_request = get_contact_request(request, contact_request_id)
    html = contact_request.get_withdrawal_letter_html()
    return serve_html_or_pdf(html, viewtype)


@user_passes_test(is_developer)
def draft_first_traffic_light_letter(request: HttpRequest,
                                     patient_lookup_id: str,
                                     viewtype: str) -> HttpResponse:
    """
    Developer view: draft first traffic-light letter to patient.

    Args:
        request: the :class:`django.http.request.HttpRequest`
        patient_lookup_id: PK for
            :class:`crate_anon.crateweb.consent.models.PatientLookup`
        viewtype: ``"pdf"`` or ``"html"``
    """
    patient_lookup = get_patient_lookup(request, patient_lookup_id)
    html = patient_lookup.get_first_traffic_light_letter_html()
    return serve_html_or_pdf(html, viewtype)


@user_passes_test(is_developer)
def draft_confirm_traffic_light_letter(request: HttpRequest,
                                       consent_mode_id: str,
                                       viewtype: str) -> HttpResponse:
    """
    Developer view: draft letter to patient confirming traffic-light decision.

    Args:
        request: the :class:`django.http.request.HttpRequest`
        consent_mode_id: PK for
            :class:`crate_anon.crateweb.consent.models.ConsentMode`
        viewtype: ``"pdf"`` or ``"html"``
    """
    consent_mode = get_consent_mode(request, consent_mode_id)
    html = consent_mode.get_confirm_traffic_to_patient_letter_html()
    return serve_html_or_pdf(html, viewtype)


@user_passes_test(is_developer)
def draft_traffic_light_decision_form(request: HttpRequest,
                                      patient_lookup_id: str,
                                      viewtype: str) -> HttpResponse:
    """
    Developer view: draft traffic-light decision form.

    Args:
        request: the :class:`django.http.request.HttpRequest`
        patient_lookup_id: PK for
            :class:`crate_anon.crateweb.consent.models.PatientLookup`
        viewtype: ``"pdf"`` or ``"html"``
    """
    patient_lookup = get_patient_lookup(request, patient_lookup_id)
    html = patient_lookup.get_traffic_light_decision_form()
    return serve_html_or_pdf(html, viewtype)


@user_passes_test(is_developer)
def draft_letter_clinician_to_pt_re_study(request: HttpRequest,
                                          contact_request_id: str,
                                          viewtype: str) -> HttpResponse:
    """
    Developer view: draft letter from clinician to patient, offering a study.

    Args:
        request: the :class:`django.http.request.HttpRequest`
        contact_request_id: PK for
            :class:`crate_anon.crateweb.consent.models.ContactRequest`
        viewtype: ``"pdf"`` or ``"html"``
    """
    contact_request = get_contact_request(request, contact_request_id)
    html = contact_request.get_letter_clinician_to_pt_re_study()
    return serve_html_or_pdf(html, viewtype)


@user_passes_test(is_developer)
def decision_form_to_pt_re_study(request: HttpRequest,
                                 contact_request_id: str,
                                 viewtype: str) -> HttpResponse:
    """
    Developer view: decision form to patient about a study.

    Args:
        request: the :class:`django.http.request.HttpRequest`
        contact_request_id: PK for
            :class:`crate_anon.crateweb.consent.models.ContactRequest`
        viewtype: ``"pdf"`` or ``"html"``
    """
    contact_request = get_contact_request(request, contact_request_id)
    html = contact_request.get_decision_form_to_pt_re_study()
    return serve_html_or_pdf(html, viewtype)


@user_passes_test(is_superuser)
def charity_report(request: HttpRequest) -> HttpResponse:
    """
    Show a summary of charity payments (triggered in response to clinicians
    answering requests).

    Args:
        request: the :class:`django.http.request.HttpRequest`
    """
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
def exclusion_report(request: HttpRequest) -> HttpResponse:
    """
    Show NHS numbers of patients to exclude from the anonymised database
    entirely.

    Args:
        request: the :class:`django.http.request.HttpRequest`
    """
    consent_modes = ConsentMode.objects.filter(current=True,
                                               exclude_entirely=True)
    return render(request, 'exclusion_report.html', {
        'consent_modes': consent_modes,
    })


@user_passes_test(is_superuser)
def test_email_rdbm(request: HttpRequest) -> HttpResponse:
    """
    Tests the backend system (Celery etc.) by sending an e-mail to the RDBM.

    Args:
        request: the :class:`django.http.request.HttpRequest`
    """
    test_email_rdbm_task.delay()
    return render(request, 'test_email_rdbm_ack.html', {
        'settings': settings,
    })
