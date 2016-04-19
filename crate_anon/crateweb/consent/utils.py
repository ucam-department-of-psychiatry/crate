#!/usr/bin/env python3
# consent/utils.py

from django.conf import settings
from django.core.exceptions import ValidationError


def pdf_template_dict(patient=True):
    if patient:
        fontsize = settings.PATIENT_FONTSIZE
    else:
        fontsize = settings.RESEARCHER_FONTSIZE
    return {
        'fontsize': fontsize,
        'PDF_LOGO_ABS_URL': settings.PDF_LOGO_ABS_URL,
        'PDF_LOGO_WIDTH': settings.PDF_LOGO_WIDTH,
    }


def get_domain_from_email(email):
    # Very simple version...
    try:
        return email.split('@')[1]
    except:
        raise ValidationError("Bad e-mail address: no domain")


def validate_researcher_email_domain(email):
    if not settings.VALID_RESEARCHER_EMAIL_DOMAINS:
        # Anything goes.
        return
    domain = get_domain_from_email(email)
    for valid_domain in settings.VALID_RESEARCHER_EMAIL_DOMAINS:
        if domain.lower() == valid_domain.lower():
            return
    raise ValidationError("Invalid researcher e-mail domain")
