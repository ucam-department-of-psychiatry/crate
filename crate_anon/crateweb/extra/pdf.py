#!/usr/bin/env python3
# extra/pdf.py

import io
import logging
import os
import pdfkit  # sudo apt-get install wkhtmltopdf; sudo pip install pdfkit
from PyPDF2 import PdfFileMerger, PdfFileReader, PdfFileWriter
import tempfile
from django.conf import settings
from django.http import HttpResponse
from crate_anon.crateweb.extra.serve import serve_buffer

logger = logging.getLogger(__name__)


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


def append_memory_pdf_to_writer(input_pdf, writer, start_recto=True):
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


def pdf_from_writer(writer):
    """
    Extracts a PDF (as binary data) from a PyPDF2 writer or merger object.
    """
    memfile = io.BytesIO()
    writer.write(memfile)
    memfile.seek(0)
    return memfile.read()


def get_concatenated_pdf_from_disk(filenames, start_recto=True):
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


def serve_concatenated_pdf_from_disk(filenames,
                                     offered_filename="crate_download.pdf",
                                     **kwargs):
    """
    Concatenates PDFs from disk and serves them.
    """
    pdf = get_concatenated_pdf_from_disk(filenames, **kwargs)
    return serve_buffer(pdf,
                        offered_filename=offered_filename,
                        content_type="application/pdf",
                        as_attachment=False,
                        as_inline=True)


# noinspection PyUnusedLocal
def get_concatenated_pdf_in_memory(html_or_filename_tuple_list,
                                   start_recto=True,
                                   **kwargs):
    """
    Concatenates PDFs and returns them as an in-memory binary PDF.
    html_or_filename_tuple_list: e.g. [
        ('html': {... dictionary to be passed to pdf_to_html ...}),
        ('filename': some_filename),
        # ...
    ]
    """
    writer = PdfFileWriter()
    for x in html_or_filename_tuple_list:
        if x[0] == 'html':
            optiondict = x[1]
            optiondict['output_path'] = None
            pdf = pdf_from_html(**optiondict)
            append_memory_pdf_to_writer(pdf, writer, start_recto=start_recto)
        elif x[0] == 'filename':
            filename = x[1]
            if start_recto and writer.getNumPages() % 2 != 0:
                writer.addBlankPage()
            writer.appendPagesFromReader(PdfFileReader(open(filename, 'rb')))
        else:
            raise ValueError("Bad html_or_filename_tuple_list")
    return pdf_from_writer(writer)


def serve_concatenated_pdf_from_memory(html_or_filename_tuple_list,
                                       offered_filename="crate_download.pdf",
                                       **kwargs):
    """
    Concatenates PDFs into memory and serves it.
    """
    pdf = get_concatenated_pdf_in_memory(html_or_filename_tuple_list,
                                         **kwargs)
    return serve_buffer(pdf,
                        offered_filename=offered_filename,
                        content_type="application/pdf",
                        as_attachment=False,
                        as_inline=True)


# =============================================================================
# Create PDFs from HTML
# =============================================================================

def pdf_from_html(html, header_html=None, footer_html=None,
                  wkhtmltopdf_filename=None, wkhtmltopdf_options=None,
                  output_path=None):
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
            os.write(h_fd, header_html)
            os.close(h_fd)
            wkhtmltopdf_options["header-html"] = h_filename
        if footer_html:
            f_fd, f_filename = tempfile.mkstemp(suffix='.html')
            os.write(f_fd, footer_html)
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


def serve_pdf_from_html(html, offered_filename="test.pdf", **kwargs):
    """Same args as pdf_from_html."""
    pdf = pdf_from_html(html, **kwargs)
    return serve_buffer(pdf,
                        offered_filename=offered_filename,
                        content_type="application/pdf",
                        as_attachment=False,
                        as_inline=True)


def serve_html_or_pdf(html, viewtype):
    """
    For development.

    HTML = contents
    viewtype = "pdf" or "html"
    """
    if viewtype == "pdf":
        return serve_pdf_from_html(html)
    elif viewtype == "html":
        return HttpResponse(html)
    else:
        raise ValueError("Bad viewtype")
