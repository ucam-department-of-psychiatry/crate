#!/usr/bin/env python
# crate_anon/crateweb/consent/emails.py

"""
===============================================================================
    Copyright (C) 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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
