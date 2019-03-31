#!/usr/bin/env python

"""
crate_anon/crateweb/consent/utils.py

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

**Utility functions for the consent-to-contact system.**

"""

import datetime
# from functools import lru_cache
import os
import re
from typing import Any, Dict, Optional, Union

from cardinal_pythonlib.django.function_cache import django_cache_function
from django.conf import settings
from django.core.exceptions import ValidationError
from django.template.loader import render_to_string


# =============================================================================
# Read files
# =============================================================================

def read_static_file_contents(filename: str) -> str:
    """
    Returns the text contents of a static file.

    Args:
        filename:
            filename (within the local static directory as determined by
            ``settings.LOCAL_STATIC_DIR``
    """
    with open(os.path.join(settings.LOCAL_STATIC_DIR, filename)) as f:
        return f.read()


# =============================================================================
# CSS, plus assistance for PDF/e-mail rendering to HTML
# =============================================================================

def pdf_css(patient: bool = True) -> str:
    """
    Returns CSS for use in PDF letters etc.

    Args:
        patient:
            patient settings (e.g. "large print"), rather than researcher
            settings ("cram it in")?
    """
    contents = read_static_file_contents('base.css')
    context = {
        'fontsize': (settings.PATIENT_FONTSIZE
                     if patient else settings.RESEARCHER_FONTSIZE),
    }
    contents += render_to_string('pdf.css', context)
    return contents


@django_cache_function(timeout=None)
# @lru_cache(maxsize=None)
def pdf_template_dict(patient: bool = True) -> Dict[str, str]:
    """
    Returns a template dictionary for use in generating PDF letters etc.

    Args:
        patient:
            patient CSS settings (e.g. "large print"), rather than researcher
            CSS settings ("cram it in")?
    """
    return {
        'css': pdf_css(patient),
        'PDF_LOGO_ABS_URL': settings.PDF_LOGO_ABS_URL,
        'PDF_LOGO_WIDTH': settings.PDF_LOGO_WIDTH,
        'TRAFFIC_LIGHT_RED_ABS_URL': settings.TRAFFIC_LIGHT_RED_ABS_URL,
        'TRAFFIC_LIGHT_YELLOW_ABS_URL': settings.TRAFFIC_LIGHT_YELLOW_ABS_URL,
        'TRAFFIC_LIGHT_GREEN_ABS_URL': settings.TRAFFIC_LIGHT_GREEN_ABS_URL,
    }


def render_pdf_html_to_string(template: str,
                              context: Dict[str, Any] = None,
                              patient: bool = True) -> str:
    """
    Renders a template into HTML that can be used for making PDFs.

    Args:
        template:
            filename of the Django template
        context:
            template context dictionary (which will be augmented with
            PDF-specific content)
        patient:
            patient CSS settings (e.g. "large print"), rather than researcher
            CSS settings ("cram it in")?

    Returns:
        HTML
    """
    context = context or {}
    context.update(pdf_template_dict(patient))
    return render_to_string(template, context)


def email_css() -> str:
    """
    Returns CSS for use in e-mails to clinicians.
    """
    contents = read_static_file_contents('base.css')
    contents += render_to_string('email.css')
    return contents


@django_cache_function(timeout=None)
# @lru_cache(maxsize=None)
def email_template_dict() -> Dict[str, str]:
    """
    Returns a template dictionary for use in generating e-mails.
    """
    return {
        'css': email_css(),
    }


def render_email_html_to_string(template: str,
                                context: Dict[str, Any] = None) -> str:
    """
    Renders a template into HTML that can be used for making PDFs.

    Args:
        template:
            filename of the Django template
        context:
            template context dictionary (which will be augmented with
            email-specific content)

    Returns:
        HTML
    """
    context = context or {}
    context.update(email_template_dict())
    return render_to_string(template, context)


# =============================================================================
# E-mail addresses
# =============================================================================

def get_domain_from_email(email: str) -> str:
    """
    Extracts the domain part from an e-mail address.

    Args:
        email: the e-mail address, e.g. "someone@cam.ac.uk"

    Returns:
        the domain part, e.g. "cam.ac.uk"

    Very simple algorithm...
    """
    try:
        return email.split('@')[1]
    except (AttributeError, IndexError):
        raise ValidationError("Bad e-mail address: no domain")


def validate_researcher_email_domain(email: str) -> None:
    """
    Ensures that an e-mail address is acceptable as a researcher e-mail
    address. We may be sending patient-identifiable information (with consent)
    via this method, so we want to be sure that nobody's put dodgy researcher
    e-mails in our system.

    We validate the e-mail domain against
    ``settings.VALID_RESEARCHER_EMAIL_DOMAINS``, if set.

    Args:
        email: an e-mail address

    Raises:
        :class:`django.core.exceptions.ValidationError` on failure

    """
    if not settings.VALID_RESEARCHER_EMAIL_DOMAINS:
        # Anything goes.
        return
    domain = get_domain_from_email(email)
    for valid_domain in settings.VALID_RESEARCHER_EMAIL_DOMAINS:
        if domain.lower() == valid_domain.lower():
            return
    raise ValidationError("Invalid researcher e-mail domain")


APPROX_EMAIL_REGEX = re.compile(  # http://emailregex.com/
    r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)")


def make_forename_surname_email_address(forename: str,
                                        surname: str,
                                        domain: str,
                                        default: str = '') -> str:
    """
    Converts a forename and surname into an e-mail address of the form
    ``forename.surname@domain``. Not guaranteed to work.

    Args:
        forename: forename
        surname: surname
        domain: domain, e.g. "cpft.nhs.uk"
        default: value to return if something looks wrong

    Returns:
        e-mail address (or ``default``)

    """
    if not forename or not surname:  # in case one is None
        return default
    forename = forename.replace(" ", "")
    surname = surname.replace(" ", "")
    if not forename or not surname:  # in case one is empty
        return default
    if len(forename) == 1:
        # Initial only; that won't do.
        return default
    # Other duff things we see: John Smith (CALT), where "Smith (CALT)" is the
    # surname and CALT is Cambridge Adult Locality Team. This can map to
    # something unpredictable, like JohnSmithOT@cpft.nhs.uk, so we can't use
    # it.
    # Formal definition is at http://stackoverflow.com/questions/2049502/what-characters-are-allowed-in-email-address  # noqa
    # See also: http://emailregex.com/
    attempt = f"{forename}.{surname}@{domain}"
    if APPROX_EMAIL_REGEX.match(attempt):
        return attempt
    else:
        return default


def make_cpft_email_address(forename: str, surname: str,
                            default: str = '') -> str:
    """
    Make a CPFT e-mail address. Not guaranteed to work.

    Args:
        forename: forename
        surname: surname
        default: value to return if something looks wrong

    Returns:
        e-mail address: ``forename.surname@cpft.nhs.uk``, or ``default``

    """
    return make_forename_surname_email_address(forename, surname,
                                               "cpft.nhs.uk", default)


# =============================================================================
# Date/time
# =============================================================================

def days_to_years(days: int, dp: int = 1) -> str:
    """
    Converts days to years, in string form.

    Args:
        days: number of days
        dp: number of decimal places

    Returns:
        str: number of years

    - For "consent after discharge", primarily.
    - Assumes 365 days/year, not 365.24.
    """
    try:
        years = days / 365
        if years % 1:  # needs decimals
            return f"{years:.{dp}f}"
        else:
            return str(int(years))
    except (TypeError, ValueError):
        return "?"


def latest_date(*args) -> Optional[datetime.date]:
    """
    Returns the latest of a bunch of dates, or ``None`` if there are no dates
    specified at all.
    """
    latest = None
    for d in args:
        if d is None:
            continue
        if latest is None:
            latest = d
        else:
            latest = max(d, latest)
    return latest


def to_date(d: Optional[Union[datetime.date,
                              datetime.datetime]]) -> Optional[datetime.date]:
    """
    Converts any of various date-like things to ``datetime.date`` objects.
    """
    if isinstance(d, datetime.datetime):
        return d.date()
    return d  # datetime.date, or None
