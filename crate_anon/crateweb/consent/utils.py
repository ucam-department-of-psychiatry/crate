#!/usr/bin/env python3
# consent/utils.py

from functools import lru_cache
import os
from django.conf import settings
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string


def read_static_file_contents(filename):
    with open(os.path.join(settings.LOCAL_STATIC_DIR, filename)) as f:
        return f.read()


def pdf_css(patient=True):
    contents = read_static_file_contents('base.css')
    context = {
        'fontsize': (settings.PATIENT_FONTSIZE
                     if patient else settings.RESEARCHER_FONTSIZE),
    }
    contents += render_to_string('pdf.css', context)
    return contents


@lru_cache(maxsize=None)
def pdf_template_dict(patient=True):
    return {
        'css': pdf_css(patient),
        'PDF_LOGO_ABS_URL': settings.PDF_LOGO_ABS_URL,
        'PDF_LOGO_WIDTH': settings.PDF_LOGO_WIDTH,
    }


def render_pdf_html_to_string(template, context=None, patient=True):
    context = context or {}
    context.update(pdf_template_dict(patient))
    return render_to_string(template, context)


def email_css():
    contents = read_static_file_contents('base.css')
    contents += render_to_string('email.css')
    return contents


@lru_cache(maxsize=None)
def email_template_dict():
    return {
        'css': email_css(),
    }


def render_email_html_to_string(template, context=None):
    context = context or {}
    context.update(email_template_dict())
    return render_to_string(template, context)


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
