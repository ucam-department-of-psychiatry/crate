#!/usr/bin/env python
# crate_anon/crateweb/consent/emails.py

from django.conf import settings
from crate_anon.crateweb.consent.models import (
    ContactRequest,
    ClinicianResponse,
)
from crate_anon.crateweb.consent.utils import render_email_html_to_string


def email_clinician_html(contact_request: ContactRequest) -> str:
    return render_email_html_to_string('email_clinician.html', {
        'ClinicianResponse': ClinicianResponse,
        'consent_mode': contact_request.consent_mode,
        'contact_request': contact_request,
        'patient_lookup': contact_request.patient_lookup,
        'settings': settings,
        'study': contact_request.study,

        # 'url_yes': XXX,
        # 'url_no': XXX,
        # 'url_maybe': XXX,
    })
