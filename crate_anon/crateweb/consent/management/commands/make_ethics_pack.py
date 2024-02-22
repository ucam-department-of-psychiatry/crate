"""
crate_anon/tools/make_ethics_pack.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

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
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

**Django management command to create a pack of PDFs for ethics submission.**

For CPFT.

"""

from argparse import ArgumentParser, Namespace
import logging
from os.path import join
from tempfile import TemporaryDirectory
from typing import Any
from zipfile import ZipFile, ZIP_DEFLATED

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.http import HttpResponse, HttpRequest

from crate_anon.crateweb.extra.pdf import serve_pdf_from_html
from crate_anon.crateweb.consent.models import TEST_ID_STR, TEST_ID_TWO_STR
from crate_anon.crateweb.consent.views import (
    decision_form_to_pt_re_study,
    draft_approval_letter,
    draft_clinician_email,
    draft_confirm_traffic_light_letter,
    draft_first_traffic_light_letter,
    draft_letter_clinician_to_pt_re_study,
    draft_researcher_cover_letter,
    draft_traffic_light_decision_form,
    draft_traffic_light_decision_form_generic,
    draft_withdrawal_letter,
)
from crate_anon.crateweb.userprofile.models import UserProfile

log = logging.getLogger(__name__)


# =============================================================================
# Django debugging request
# =============================================================================


def mk_developer_debug_request() -> HttpRequest:
    """
    Create a debugging HttpRequest with developer privileges.
    """
    User = get_user_model()
    user = User()
    user.is_superuser = True
    user.is_staff = True
    profile = UserProfile()
    profile.is_developer = True
    user.profile = profile
    req = HttpRequest()
    req.user = user
    return req


# =============================================================================
# Save PDF responses to a zip file
# =============================================================================

VIEWTYPE_PDF = "pdf"


def save_pdf_response(
    zipfile: ZipFile, response: HttpResponse, filename: str
) -> None:
    """
    Args:
        zipfile:
            Open zip file object in which to save the PDF.
        response:
            HTTP response object with PDF contents.
        filename:
            Filename within the zip file.
    """
    internal_filename = "tmp.pdf"
    with TemporaryDirectory() as d:
        # With a temporary file:
        tmp_fullpath = join(d, internal_filename)
        with open(tmp_fullpath, "wb") as f:
            # Write bytes from the response to the file
            f.write(response.content)
        # Then store that file in the zip file:
        zipfile.write(tmp_fullpath, filename)


def save_html_response_as_pdf(
    zipfile: ZipFile, response: HttpResponse, filename: str
) -> None:
    """
    Args:
        zipfile:
            Open zip file object in which to save the PDF.
        response:
            HTTP response with HTML contents.
        filename:
            Filename within the zip file.
    """
    html_str = response.content.decode("utf8")
    return save_pdf_response(zipfile, serve_pdf_from_html(html_str), filename)


def cli_make_ethics_pack(
    zip_filename: str, compression: int = ZIP_DEFLATED
) -> None:
    """
    Make an ethics pack.

    Args:
        zip_filename:
            Name of zip file to create.
        compression:
            Type of compression to use.
    """
    zipfile = ZipFile(zip_filename, mode="w", compression=compression)
    request = mk_developer_debug_request()

    log.info("draft_first_traffic_light_letter")
    save_pdf_response(
        zipfile,
        draft_first_traffic_light_letter(request, TEST_ID_STR, VIEWTYPE_PDF),
        "09_AUTO_Clinician_to_patient_cover_letter_re_traffic_light.pdf",
    )

    log.info("draft_traffic_light_decision_form_generic")
    save_pdf_response(
        zipfile,
        draft_traffic_light_decision_form_generic(request, VIEWTYPE_PDF),
        "10_AUTO_Traffic_light_decision_form_GENERIC.pdf",
    )

    log.info("draft_traffic_light_decision_form")
    save_pdf_response(
        zipfile,
        draft_traffic_light_decision_form(request, TEST_ID_STR, VIEWTYPE_PDF),
        "11_AUTO_Traffic_light_decision_form_PERSONALIZED.pdf",
    )

    log.info("draft_confirm_traffic_light_letter")
    save_pdf_response(
        zipfile,
        draft_confirm_traffic_light_letter(
            request, TEST_ID_TWO_STR, VIEWTYPE_PDF
        ),
        "12_AUTO_RDBM_to_patient_confirming_traffic_light_choice.pdf",
    )

    log.warning(
        "13_Researcher_requests_contact_details_screenshot.pdf: DO BY HAND"
    )
    # ... CSS problems; looks better as a screenshot.

    log.info("draft_clinician_email")
    save_html_response_as_pdf(
        zipfile,
        draft_clinician_email(request, TEST_ID_STR),
        "14_AUTO_Email_to_clinician_requesting_contact.pdf",
    )

    log.warning("15_Clinician_response_page.pdf: DO BY HAND")
    # ... involves CSS, which is normally fetched by the browser; but also, we
    # need to show interactive elements that are conditional on the clinician's
    # choice.

    log.info("draft_letter_clinician_to_pt_re_study: YELLOW")
    save_pdf_response(
        zipfile,
        draft_letter_clinician_to_pt_re_study(
            request, TEST_ID_TWO_STR, VIEWTYPE_PDF
        ),
        "16_AUTO_Clinician_to_patient_cover_letter_specific_study_YELLOW.pdf",
    )

    log.info("draft_letter_clinician_to_pt_re_study: UNKNOWN")
    save_pdf_response(
        zipfile,
        draft_letter_clinician_to_pt_re_study(
            request, TEST_ID_STR, VIEWTYPE_PDF
        ),
        "17_AUTO_Clinician_to_patient_cover_letter_specific_study_UNKNOWN.pdf",
    )

    log.info("decision_form_to_pt_re_study: ADULT")
    save_pdf_response(
        zipfile,
        decision_form_to_pt_re_study(request, TEST_ID_STR, VIEWTYPE_PDF),
        "18_AUTO_Decision_form_about_a_specific_study_ADULT.pdf",
    )

    log.info("decision_form_to_pt_re_study: CHILD")
    save_pdf_response(
        zipfile,
        decision_form_to_pt_re_study(request, TEST_ID_TWO_STR, VIEWTYPE_PDF),
        "19_AUTO_Decision_form_about_a_specific_study_CHILD.pdf",
    )

    log.info("draft_approval_letter")
    save_pdf_response(
        zipfile,
        draft_approval_letter(request, TEST_ID_STR, VIEWTYPE_PDF),
        "20_AUTO_RDBM_to_researcher_giving_permission_to_contact.pdf",
    )

    log.info("draft_researcher_cover_letter")
    save_pdf_response(
        zipfile,
        draft_researcher_cover_letter(request, VIEWTYPE_PDF),
        "21_AUTO_Researcher_cover_letter_to_patient.pdf",
    )

    log.info("draft_withdrawal_letter")
    save_pdf_response(
        zipfile,
        draft_withdrawal_letter(request, TEST_ID_STR, VIEWTYPE_PDF),
        "22_AUTO_RDBM_to_researcher_when_patient_withdraws_consent.pdf",
    )

    log.info(f"Written to: {zip_filename}")


# =============================================================================
# Django management command
# =============================================================================


class Command(BaseCommand):
    """
    Django management command to make an ethics pack of PDFs.
    """

    help = "Make CPFT ethics pack"

    def add_arguments(self, parser: ArgumentParser) -> None:
        # docstring in superclass
        parser.add_argument("filename", help="ZIP filename")
        parser.add_argument(
            "--compression",
            type=int,
            default=ZIP_DEFLATED,
            help="Compression type",
        )

    def handle(self, *args: str, **options: Any) -> None:
        # docstring in superclass
        opts = Namespace(**options)
        cli_make_ethics_pack(
            zip_filename=opts.filename, compression=opts.compression
        )


# =============================================================================
# Command-line entry point
# =============================================================================
# Run as "crate_django_manage make_ethics_pack FILENAME"
