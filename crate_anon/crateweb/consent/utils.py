#!/usr/bin/env python
# crate_anon/crateweb/consent/utils.py

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

# from functools import lru_cache
import os
from typing import Any, Dict

from django.conf import settings
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string
from django_cache_decorator import django_cache_decorator


def read_static_file_contents(filename: str) -> str:
    with open(os.path.join(settings.LOCAL_STATIC_DIR, filename)) as f:
        return f.read()


def pdf_css(patient: bool = True) -> str:
    contents = read_static_file_contents('base.css')
    context = {
        'fontsize': (settings.PATIENT_FONTSIZE
                     if patient else settings.RESEARCHER_FONTSIZE),
    }
    contents += render_to_string('pdf.css', context)
    return contents


@django_cache_decorator(time=None)
# @lru_cache(maxsize=None)
def pdf_template_dict(patient: bool = True) -> Dict[str, str]:
    return {
        'css': pdf_css(patient),
        'PDF_LOGO_ABS_URL': settings.PDF_LOGO_ABS_URL,
        'PDF_LOGO_WIDTH': settings.PDF_LOGO_WIDTH,
    }


def render_pdf_html_to_string(template: str,
                              context: Dict[str, Any] = None,
                              patient: bool = True) -> str:
    context = context or {}
    context.update(pdf_template_dict(patient))
    return render_to_string(template, context)


def email_css() -> str:
    contents = read_static_file_contents('base.css')
    contents += render_to_string('email.css')
    return contents


@django_cache_decorator(time=None)
# @lru_cache(maxsize=None)
def email_template_dict() -> Dict[str, str]:
    return {
        'css': email_css(),
    }


def render_email_html_to_string(template: str,
                                context: Dict[str, Any] = None) -> str:
    context = context or {}
    context.update(email_template_dict())
    return render_to_string(template, context)


def get_domain_from_email(email: str) -> str:
    # Very simple version...
    try:
        return email.split('@')[1]
    except:
        raise ValidationError("Bad e-mail address: no domain")


def validate_researcher_email_domain(email: str) -> None:
    if not settings.VALID_RESEARCHER_EMAIL_DOMAINS:
        # Anything goes.
        return
    domain = get_domain_from_email(email)
    for valid_domain in settings.VALID_RESEARCHER_EMAIL_DOMAINS:
        if domain.lower() == valid_domain.lower():
            return
    raise ValidationError("Invalid researcher e-mail domain")
