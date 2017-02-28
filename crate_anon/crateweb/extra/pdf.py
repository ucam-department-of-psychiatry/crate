#!/usr/bin/env python
# crate_anon/crateweb/extra/pdf.py

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

import io
import logging
import os
import tempfile
from typing import Any, Dict, Iterable, Union

import pdfkit  # sudo apt-get install wkhtmltopdf; sudo pip install pdfkit
from PyPDF2 import PdfFileMerger, PdfFileReader, PdfFileWriter
from django.conf import settings
from django.http import HttpResponse
from crate_anon.crateweb.extra.serve import serve_buffer

log = logging.getLogger(__name__)


# =============================================================================
# Serve concatenated PDFs
# =============================================================================
# Two ways in principle to do this:
# (1) Load data from each PDF into memory; concatenate; serve the result.
# (2) With each PDF on disk, create a temporary file (e.g. with pdftk),
#     serve the result (e.g. in one go), then delete the temporary file.
#     This may be more memory-efficient.
#     However, there can be problems:
#       http://stackoverflow.com/questions/7543452/how-to-launch-a-pdftk-subprocess-while-in-wsgi  # noqa
# Others' examples:
#   https://gist.github.com/zyegfryed/918403
#   https://gist.github.com/grantmcconnaughey/ce90a689050c07c61c96
#   http://stackoverflow.com/questions/3582414/removing-tmp-file-after-return-httpresponse-in-django  # noqa

# def append_disk_pdf_to_writer(filename, writer):
#     """Appends a PDF from disk to a pyPDF writer."""
#     if writer.getNumPages() % 2 != 0:
#         writer.addBlankPage()
#         # ... keeps final result suitable for double-sided printing
#     with open(filename, mode='rb') as infile:
#         reader = PdfFileReader(infile)
#         for page_num in range(reader.numPages):
#             writer.addPage(reader.getPage(page_num))


def append_memory_pdf_to_writer(input_pdf: bytes,
                                writer: PdfFileWriter,
                                start_recto: bool = True) -> None:
    """Appends a PDF (as bytes in memory) to a PyPDF2 writer."""
    if not input_pdf:
        return
    if start_recto and writer.getNumPages() % 2 != 0:
        writer.addBlankPage()
        # ... suitable for double-sided printing
    infile = io.BytesIO(input_pdf)
    reader = PdfFileReader(infile)
    for page_num in range(reader.numPages):
        writer.addPage(reader.getPage(page_num))


def pdf_from_writer(writer: Union[PdfFileWriter, PdfFileMerger]) -> bytes:
    """
    Extracts a PDF (as binary data) from a PyPDF2 writer or merger object.
    """
    memfile = io.BytesIO()
    writer.write(memfile)
    memfile.seek(0)
    return memfile.read()


def get_concatenated_pdf_from_disk(filenames: Iterable[str],
                                   start_recto: bool = True) -> bytes:
    """
    Concatenates PDFs from disk and returns them as an in-memory binary PDF.
    """
    # http://stackoverflow.com/questions/17104926/pypdf-merging-multiple-pdf-files-into-one-pdf  # noqa
    # https://en.wikipedia.org/wiki/Recto_and_verso
    if start_recto:
        writer = PdfFileWriter()
        for filename in filenames:
            if filename:
                if writer.getNumPages() % 2 != 0:
                    writer.addBlankPage()
                writer.appendPagesFromReader(
                    PdfFileReader(open(filename, 'rb')))
        return pdf_from_writer(writer)
    else:
        merger = PdfFileMerger()
        for filename in filenames:
            if filename:
                merger.append(open(filename, 'rb'))
        return pdf_from_writer(merger)


def serve_concatenated_pdf_from_disk(
        filenames: Iterable[str],
        offered_filename: str = "crate_download.pdf",
        **kwargs) -> HttpResponse:
    """
    Concatenates PDFs from disk and serves them.
    """
    pdf = get_concatenated_pdf_from_disk(filenames, **kwargs)
    return serve_buffer(pdf,
                        offered_filename=offered_filename,
                        content_type="application/pdf",
                        as_attachment=False,
                        as_inline=True)


class PdfPlan(object):
    def __init__(self,
                 # HTML mode
                 is_html: bool = False,
                 html: str = None,
                 header_html: str = None,
                 footer_html: str = None,
                 wkhtmltopdf_filename: str = None,
                 wkhtmltopdf_options: Dict[str, Any] = None,
                 # Filename mode
                 is_filename: bool = False,
                 filename: str = None):
        assert is_html != is_filename, "Specify is_html XOR is_filename"
        self.is_html = is_html
        self.html = html
        self.header_html = header_html
        self.footer_html = footer_html
        self.wkhtmltopdf_filename = wkhtmltopdf_filename
        self.wkhtmltopdf_options = wkhtmltopdf_options
        self.is_filename = is_filename
        self.filename = filename

    def add_to_writer(self,
                      writer: PdfFileWriter,
                      start_recto: bool = True) -> None:
        if self.is_html:
            pdf = pdf_from_html(html=self.html,
                                header_html=self.header_html,
                                footer_html=self.footer_html,
                                wkhtmltopdf_filename=self.wkhtmltopdf_filename,
                                wkhtmltopdf_options=self.wkhtmltopdf_options,
                                output_path=None)
            append_memory_pdf_to_writer(pdf, writer, start_recto=start_recto)
        elif self.is_filename:
            if start_recto and writer.getNumPages() % 2 != 0:
                writer.addBlankPage()
            writer.appendPagesFromReader(PdfFileReader(
                open(self.filename, 'rb')))
        else:
            raise AssertionError("PdfPlan: shouldn't get here!")


def get_concatenated_pdf_in_memory(
        pdf_plans: Iterable[PdfPlan],
        start_recto: bool = True) -> bytes:
    """
    Concatenates PDFs and returns them as an in-memory binary PDF.
    """
    writer = PdfFileWriter()
    for pdfplan in pdf_plans:
        pdfplan.add_to_writer(writer, start_recto=start_recto)
    return pdf_from_writer(writer)


def serve_concatenated_pdf_from_memory(
        pdf_plans: Iterable[PdfPlan],
        start_recto: bool = True,
        offered_filename: str = "crate_download.pdf") -> HttpResponse:
    """
    Concatenates PDFs into memory and serves it.
    """
    pdf = get_concatenated_pdf_in_memory(pdf_plans, start_recto=start_recto)
    return serve_buffer(pdf,
                        offered_filename=offered_filename,
                        content_type="application/pdf",
                        as_attachment=False,
                        as_inline=True)


# =============================================================================
# Create PDFs from HTML
# =============================================================================

FIX_PDFKIT_ENCODING_BUG = True  # needs to be True for pdfkit==0.5.0


def pdf_from_html(html: str,
                  header_html: str = None,
                  footer_html: str = None,
                  wkhtmltopdf_filename: str = None,
                  wkhtmltopdf_options: Dict[str, Any] = None,
                  output_path: str = None) -> Union[bytes, bool]:
    """
    Takes HTML and either:
        - returns a PDF (as a binary object in memory), if output_path is None
        - creates a PDF in the file specified by output_path
    Uses wkhtmltopdf (with pdfkit)
        - faster than xhtml2pdf
        - tables not buggy like Weasyprint
        - however, doesn't support CSS Paged Media, so we have the
          header_html and footer_html options to allow you to pass appropriate
          HTML content to serve as the header/footer (rather than passing it
          within the main HTML).
    """
    # Customized for this Django site
    if wkhtmltopdf_filename is None:
        wkhtmltopdf_filename = settings.WKHTMLTOPDF_FILENAME
    if wkhtmltopdf_options is None:
        wkhtmltopdf_options = settings.WKHTMLTOPDF_OPTIONS
    if not wkhtmltopdf_options:
        wkhtmltopdf_options = {}

    # Generic
    if not wkhtmltopdf_filename:
        config = None
    else:
        if FIX_PDFKIT_ENCODING_BUG:
            config = pdfkit.configuration(
                wkhtmltopdf=wkhtmltopdf_filename.encode('utf-8'))
            # the bug is that pdfkit.pdfkit.PDFKit.__init__ will attempt to
            # decode the string in its configuration object;
            # https://github.com/JazzCore/python-pdfkit/issues/32
        else:
            config = pdfkit.configuration(wkhtmltopdf=wkhtmltopdf_filename)
    # Temporary files that a subprocess can read:
    #   http://stackoverflow.com/questions/15169101
    # wkhtmltopdf requires its HTML files to have ".html" extensions:
    #   http://stackoverflow.com/questions/5776125
    h_filename = None
    f_filename = None
    try:
        if header_html:
            h_fd, h_filename = tempfile.mkstemp(suffix='.html')
            os.write(h_fd, header_html.encode('utf8'))
            os.close(h_fd)
            wkhtmltopdf_options["header-html"] = h_filename
        if footer_html:
            f_fd, f_filename = tempfile.mkstemp(suffix='.html')
            os.write(f_fd, footer_html.encode('utf8'))
            os.close(f_fd)
            wkhtmltopdf_options["footer-html"] = f_filename
        kit = pdfkit.pdfkit.PDFKit(html, 'string', configuration=config,
                                   options=wkhtmltopdf_options)
        return kit.to_pdf(path=output_path)
        # ... if path is None, will return the PDF
        # ... if path is specified, will return True
        # https://github.com/JazzCore/python-pdfkit/blob/master/pdfkit/pdfkit.py  # noqa
    finally:
        if h_filename:
            os.remove(h_filename)
        if f_filename:
            os.remove(f_filename)


def serve_pdf_from_html(html: str,
                        offered_filename: str = "test.pdf",
                        **kwargs) -> HttpResponse:
    """Same args as pdf_from_html."""
    log.critical("kwargs: " + repr(kwargs))
    pdf = pdf_from_html(html, **kwargs)
    return serve_buffer(pdf,
                        offered_filename=offered_filename,
                        content_type="application/pdf",
                        as_attachment=False,
                        as_inline=True)


def serve_html_or_pdf(html: str, viewtype: str) -> HttpResponse:
    """
    For development.

    HTML = contents
    viewtype = "pdf" or "html"
    """
    if viewtype == "pdf":
        return serve_pdf_from_html(
            html,
            header_html=settings.PDF_LETTER_HEADER_HTML,
            footer_html=settings.PDF_LETTER_FOOTER_HTML)
    elif viewtype == "html":
        return HttpResponse(html)
    else:
        raise ValueError("Bad viewtype")
