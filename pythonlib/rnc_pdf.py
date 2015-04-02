#!/usr/bin/python
# -*- encoding: utf8 -*-

"""Support functions to serve PDFs from CGI scripts.

Author: Rudolf Cardinal (rudolf@pobox.com)
Created: October 2012
Last update: 22 Feb 2015

Copyright/licensing:

    Copyright (C) 2012-2015 Rudolf Cardinal (rudolf@pobox.com).

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

"""

import io
import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
logger.setLevel(logging.INFO)
import pyPdf  # sudo apt-get install python-pypdf
import sys

try:
    import xhtml2pdf.document
    # sudo easy_install pip; sudo pip install xhtml2pdf
    XHTML2PDF_AVAILABLE = True
except ImportError:
    XHTML2PDF_AVAILABLE = False

try:
    import weasyprint
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False

if not XHTML2PDF_AVAILABLE and not WEASYPRINT_AVAILABLE:
    raise RuntimeError("Neither xhtml2pdf nor Weasyprint available; can't "
                       "load")

# =============================================================================
# Ancillary functions for PDFs
# =============================================================================

XHTML2PDF = "xhtml2pdf"
WEASYPRINT = "weasyprint"
processor = WEASYPRINT if WEASYPRINT_AVAILABLE else XHTML2PDF


def set_processor(new_processor=WEASYPRINT):
    """Set the PDF processor."""
    global processor
    if new_processor not in [XHTML2PDF, WEASYPRINT]:
        raise AssertionError("rnc_pdf.set_pdf_processor: invalid PDF processor"
                             " specified")
    if new_processor == WEASYPRINT and not WEASYPRINT_AVAILABLE:
        raise RuntimeError("rnc_pdf: Weasyprint requested, but not available")
    if new_processor == XHTML2PDF and not XHTML2PDF_AVAILABLE:
        raise RuntimeError("rnc_pdf: xhtml2pdf requested, but not available")
    processor = new_processor
    logger.info("PDF processor set to: " + processor)


def pdf_from_html(html):
    """Takes HTML and returns a PDF (as a buffer)."""
    if processor == XHTML2PDF:
        memfile = io.BytesIO()
        xhtml2pdf.document.pisaDocument(html, memfile)
        # ... returns a document, but we don't use it, so we don't store it to
        # stop pychecker complaining
        # http://xhtml2pdf.appspot.com/static/pisa-en.html
        memfile.seek(0)
        return buffer(memfile.read())
        # http://stackoverflow.com/questions/3310584
    else:
        # http://ampad.de/blog/generating-pdfs-django/
        return weasyprint.HTML(string=html).write_pdf()


def pdf_from_writer(writer):
    """Extracts a PDF (as a buffer) from a pyPdf writer."""
    memfile = io.BytesIO()
    writer.write(memfile)
    memfile.seek(0)
    return buffer(memfile.read())


def serve_pdf_to_stdout(pdf):
    """Serves a PDF to stdout.

    Writes a "Content-Type: application/pdf" header and then the PDF to stdout.
    """
    # http://stackoverflow.com/questions/312230/proper-mime-type-for-pdf-files
    # http://www.askapache.com/htaccess/pdf-cookies-headers-rewrites.html
    # http://stackoverflow.com/questions/2374427
    # print "Content-type: text/plain\n" # for debugging
    print "Content-Type: application/pdf\n"
    sys.stdout.write(pdf)


def make_pdf_writer():
    """Creates a pyPdf writer."""
    return pyPdf.PdfFileWriter()


def append_pdf(input_pdf, output_writer):
    """Appends a PDF to a pyPDF writer."""
    if input_pdf is None:
        return
    if output_writer.getNumPages() % 2 != 0:
        output_writer.addBlankPage()
        # ... suitable for double-sided printing
    infile = io.BytesIO(input_pdf)
    reader = pyPdf.PdfFileReader(infile)
    [
        output_writer.addPage(reader.getPage(page_num))
        for page_num in range(reader.numPages)
    ]
