#!/usr/bin/env python3
# core/utils.py

import io
import logging
logger = logging.getLogger(__name__)
import os
import re
import pdfkit  # sudo apt-get install wkhtmltopdf; sudo pip install pdfkit
from PyPDF2 import PdfFileMerger, PdfFileReader, PdfFileWriter
import tempfile
import urllib
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import FileResponse, HttpResponse
from django.utils.encoding import smart_str
from userprofile.models import get_or_create_user_profile, get_per_page


# =============================================================================
# User tests/user profile
# =============================================================================

def is_superuser(user):
    """
    Function for user with decorator, e.g.
        @user_passes_test(is_superuser)
    """
    # https://docs.djangoproject.com/en/dev/topics/auth/default/#django.contrib.auth.decorators.user_passes_test  # noqa
    return user.is_superuser


def is_developer(user):
    if not user.is_authenticated():
        return False  # won't have a profile
    profile = get_or_create_user_profile(user)
    return profile.is_developer


# =============================================================================
# Forms
# =============================================================================

def paginate(request, all_items):
    per_page = get_per_page(request)
    paginator = Paginator(all_items, per_page)
    page = request.GET.get('page')
    try:
        items = paginator.page(page)
    except PageNotAnInteger:
        items = paginator.page(1)
    except EmptyPage:
        items = paginator.page(paginator.num_pages)
    return items


# =============================================================================
# URL creation
# =============================================================================

def url_with_querystring(path, **kwargs):
    """Add GET arguments to a URL."""
    return path + '?' + urllib.urlencode(kwargs)


# =============================================================================
# Formatting
# =============================================================================

def get_friendly_date(date):
    if date is None:
        return ""
    try:
        return date.strftime("%d %B %Y")  # e.g. 03 December 2013
    except Exception as e:
        raise type(e)(e.message + ' [value was {}]'.format(repr(date)))


def modelrepr(instance):
    """Default repr version of a Django model object, for debugging."""
    elements = []
    for fieldname in instance._meta.get_all_field_names():
        try:
            value = repr(getattr(instance, fieldname))
        except ObjectDoesNotExist:
            value = "<RelatedObjectDoesNotExist>"
        elements.append("{}: {}".format(fieldname, value))
    return "<{} <{}>>".format(type(instance).__name__,
                              "; ".join(elements))
    # - type(instance).__name__ gives the Python class name from an instance
    # - ... as does ModelClass.__name__ but we don't have that directly here
    # - instance._meta.model_name gives a lower-case version


# =============================================================================
# String parsing
# =============================================================================

def replace_in_list(stringlist, replacedict):
    newlist = []
    for i in range(len(stringlist)):
        newlist.append(multiple_replace(stringlist[i], replacedict))
    return newlist


def multiple_replace(text, rep):
    """Returns text in which the keys of rep (a dict) have been replaced by
    their values."""
    # http://stackoverflow.com/questions/6116978/python-replace-multiple-strings  # noqa
    rep = dict((re.escape(k), v) for k, v in rep.items())
    pattern = re.compile("|".join(rep.keys()))
    return pattern.sub(lambda m: rep[re.escape(m.group(0))], text)


def get_initial_surname_tuple_from_string(s):
    """
    Parses a name-like string into plausible parts. Try:

        get_initial_surname_tuple_from_string("AJ VAN DEN BERG")
        get_initial_surname_tuple_from_string("VAN DEN BERG AJ")
        get_initial_surname_tuple_from_string("J Smith")
        get_initial_surname_tuple_from_string("J. Smith")
        get_initial_surname_tuple_from_string("Smith J.")
        get_initial_surname_tuple_from_string("Smith JKC")
        get_initial_surname_tuple_from_string("Dr Bob Smith")
        get_initial_surname_tuple_from_string("LINTON H C (PL)")
    """
    parts = s.split() if s else []
    nparts = len(parts)
    if nparts == 0:
        return ("", "")
    elif "(" in s:
        # something v. odd like "Linton H C (PL)", for Linton Health Centre
        # partners or similar. We can't fix it, but...
        return ("", parts[0])
    elif nparts == 1:
        # hmm... assume "Smith"
        return ("", parts[0])
    elif nparts == 2:
        if len(parts[0]) < len(parts[1]):
            # probably "J Smith"
            return (parts[0][0], parts[1])
        else:
            # probably "Smith JKC"
            return (parts[1][0], parts[0])
    else:
        # Lots of parts.
        if parts[0].lower() == "dr":
            parts = parts[1:]
            nparts = nparts - 1
        if len(parts[0]) < len(parts[-1]):
            # probably "AJ VAN DEN BERG"
            return (parts[0][0], " ".join(parts[1:]))
        else:
            # probably "VAN DEN BERG AJ"
            return (parts[-1][0], " ".join(parts[:-1]))


# =============================================================================
# File serving
# =============================================================================

# I thought this function was superseded django-filetransfers:
# http://nemesisdesign.net/blog/coding/django-private-file-upload-and-serving/
# https://www.allbuttonspressed.com/projects/django-filetransfers
# ... but it turns out that filetransfers.api.serve_file uses a file object,
# not a filename. Not impossible, but never mind.

def add_http_headers_for_attachment(response, offered_filename=None,
                                    content_type=None, as_attachment=False,
                                    as_inline=False, content_length=None):
    """
    Add HTTP headers to a Django response class object.

    as_attachment: if True, browsers will generally save to disk.
        If False, they may display it inline.
        http://www.w3.org/Protocols/rfc2616/rfc2616-sec19.html
    as_inline: attempt to force inline (only if not as_attachment)
    """
    if offered_filename is None:
        offered_filename = ''
    if content_type is None:
        content_type = 'application/force-download'
    response['Content-Type'] = content_type
    if as_attachment:
        prefix = 'attachment; '
    elif as_inline:
        prefix = 'inline; '
    else:
        prefix = ''
    fname = 'filename=%s' % smart_str(offered_filename)
    response['Content-Disposition'] = prefix + fname
    if content_length is not None:
        response['Content-Length'] = content_length


def serve_file(path_to_file, offered_filename=None,
               content_type=None, as_attachment=False,
               as_inline=False):
    """
    Serve up a file from disk.
    Two methods:
    (a) serve directly
    (b) serve by asking the web server to do so via the X-SendFile directive.

    """
    # http://stackoverflow.com/questions/1156246/having-django-serve-downloadable-files  # noqa
    # https://docs.djangoproject.com/en/dev/ref/request-response/#telling-the-browser-to-treat-the-response-as-a-file-attachment  # noqa
    # https://djangosnippets.org/snippets/365/
    if offered_filename is None:
        offered_filename = os.path.basename(path_to_file) or ''
    if settings.XSENDFILE:
        response = HttpResponse()
        response['X-Sendfile'] = smart_str(path_to_file)
        content_length = os.path.getsize(path_to_file)
    else:
        response = FileResponse(open(path_to_file, mode='rb'))
        content_length = None
    add_http_headers_for_attachment(response,
                                    offered_filename=offered_filename,
                                    content_type=content_type,
                                    as_attachment=as_attachment,
                                    as_inline=as_inline,
                                    content_length=content_length)
    return response
    # Note for debugging: Chrome may request a file more than once (e.g. with a
    # GET request that's then marked 'canceled' in the Network tab of the
    # developer console); this is normal:
    #   http://stackoverflow.com/questions/4460661/what-to-do-with-chrome-sending-extra-requests  # noqa


def serve_buffer(data, offered_filename=None,
                 content_type=None, as_attachment=True,
                 as_inline=False):
    """
    Serve up binary data from a buffer.
    Options as for serve_file().
    """
    response = HttpResponse(data)
    add_http_headers_for_attachment(response,
                                    offered_filename=offered_filename,
                                    content_type=content_type,
                                    as_attachment=as_attachment,
                                    as_inline=as_inline,
                                    content_length=len(data))
    return response

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
                                     offered_filename="crate_download.pdf"):
    """
    Concatenates PDFs from disk and serves them.
    """
    pdf = get_concatenated_pdf_from_disk(filenames)
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
            if not wkhtmltopdf_options:
                wkhtmltopdf_options = {}
            h_fd, h_filename = tempfile.mkstemp(suffix='.html')
            os.write(h_fd, header_html)
            os.close(h_fd)
            wkhtmltopdf_options["header-html"] = h_filename
        if footer_html:
            if not wkhtmltopdf_options:
                wkhtmltopdf_options = {}
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
