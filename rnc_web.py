#!/usr/bin/python
# -*- encoding: utf8 -*-

"""Support for web scripts.

Author: Rudolf Cardinal (rudolf@pobox.com)
Created: October 2012
Last update: 26 Feb 2015

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


import base64
import binascii
import cgi
import dateutil.parser
import dateutil.tz
import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
logger.setLevel(logging.DEBUG)
import os
import re
import sys

# =============================================================================
# Constants
# =============================================================================

_NEWLINE_REGEX = re.compile("\n", re.MULTILINE)
BASE64_PNG_URL_PREFIX = "data:image/png;base64,"
PNG_SIGNATURE_HEXSTRING = "89504E470D0A1A0A"
# ... http://en.wikipedia.org/wiki/Portable_Network_Graphics#Technical_details
PNG_SIGNATURE_HEX = binascii.unhexlify(PNG_SIGNATURE_HEXSTRING)


# =============================================================================
# Misc
# =============================================================================

def print_utf8(s):
    """Writes a Unicode string to sys.stdout in UTF-8 encoding."""
    sys.stdout.write(s.encode('utf-8'))


def get_int_or_none(s):
    """Returns the integer value of a string, or None if it's not convertible
    to an int."""
    try:
        return int(s)
        # int(x) will return something of type long if it's a big number,
        # but happily
    except (TypeError, ValueError):
        return None


def get_float_or_none(s):
    """Returns the float value of a string, or None if it's not convertible
    to a float."""
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def is_1(s):
    """True if the input is the string literal "1", otherwise False."""
    return True if s == "1" else False


def number_to_dp(number, dp, default="", en_dash_for_minus=True):
    """Format number to dp decimal places, optionally using a UTF-8 en dash
    for minus signs."""
    if number is None:
        return default
    s = u"{:.{precision}f}".format(number, precision=dp)
    if en_dash_for_minus:
        s = s.replace("-", u"–")  # hyphen becomes en dash for minus sign
    return s


# =============================================================================
# CGI
# =============================================================================

def debug_form_contents(form):
    """Writes the keys and values of a CGI form to stderr."""
    for k in form.keys():
        sys.stderr.write("{0} = {1}".format(k, form.getvalue(k)))
    # But note also: cgi.print_form(form)


def cgi_method_is_post(environ):
    method = environ.get("REQUEST_METHOD", None)
    if not method:
        return False
    return method.upper() == "POST"


def get_cgi_parameter_str(form, key, default=None):
    """
    Extracts a string parameter from a CGI form.
    Note: key is CASE-SENSITIVE.
    """
    l = form.getlist(key)
    if len(l) == 0:
        return default
    return l[0]


def get_cgi_parameter_str_or_none(form, key):
    """Extracts a string parameter from a CGI form, or None if the key doesn't
    exist or the string is zero-length."""
    s = get_cgi_parameter_str(form, key)
    if s is None or len(s) == 0:
        return None
    return s


def get_cgi_parameter_list(form, key):
    """Extracts a list of values, all with the same key, from a CGI form."""
    return form.getlist(key)


def get_cgi_parameter_bool(form, key):
    """Extracts a boolean parameter from a CGI form, on the assumption that "1"
    is True and everything else is False."""
    return is_1(get_cgi_parameter_str(form, key))


def get_cgi_parameter_bool_or_default(form, key, default=None):
    """Extracts a boolean parameter from a CGI form ("1" = True,
    other string = False, absent/zero-length string = default value)."""
    s = get_cgi_parameter_str(form, key)
    if s is None or len(s) == 0:
        return default
    return is_1(s)


def get_cgi_parameter_bool_or_none(form, key):
    """Extracts a boolean parameter from a CGI form ("1" = True,
    other string = False, absent/zero-length string = None)."""
    return get_cgi_parameter_bool_or_default(form, key, default=None)


def get_cgi_parameter_int(form, key):
    """Extracts an integer parameter from a CGI form, or None if the key is
    absent or the string value is not convertible to int."""
    return get_int_or_none(get_cgi_parameter_str(form, key))


def get_cgi_parameter_float(form, key):
    """Extracts a float parameter from a CGI form, or None if the key is
    absent or the string value is not convertible to float."""
    return get_float_or_none(get_cgi_parameter_str(form, key))


def get_cgi_parameter_datetime(form, key):
    """Extracts a date/time parameter from a CGI form. Applies the LOCAL
    timezone if none specified."""
    try:
        s = get_cgi_parameter_str(form, key)
        if not s:
            # if you dateutil.parser.parse() an empty string,
            # you get today's date
            return None
        d = dateutil.parser.parse(s)
        if d.tzinfo is None:  # as it will be
            d = d.replace(tzinfo=dateutil.tz.tzlocal())
        return d
    except:
        return None


def get_cgi_parameter_file(form, key):
    """Extracts a file's contents from a "file" input in a CGI form, or None
    if no such file was uploaded."""
    (filename, filecontents) = get_cgi_parameter_filename_and_file(form, key)
    return filecontents


def get_cgi_parameter_filename_and_file(form, key):
    """Extracts a file's name and contents from a "file" input in a CGI form,
    or (None, None) if no such file was uploaded."""
    if not (key in form):
        logger.warning('get_cgi_parameter_file: form has no '
                       'key {}'.format(key))
        return (None, None)
    fileitem = form[key]  # a nested FieldStorage instance; see
    # http://docs.python.org/2/library/cgi.html#using-the-cgi-module
    if isinstance(fileitem, cgi.MiniFieldStorage):
        logger.warning('get_cgi_parameter_file: MiniFieldStorage found - did '
                       'you forget to set enctype="multipart/form-data" in '
                       'your form?')
        return (None, None)
    if not isinstance(fileitem, cgi.FieldStorage):
        logger.warning('get_cgi_parameter_file: no FieldStorage instance with '
                       'key {} found'.format(key))
        return (None, None)
    if fileitem.filename and fileitem.file:  # can check "file" or "filename"
        return (fileitem.filename, fileitem.file.read())
        # as per
        # http://upsilon.cc/~zack/teaching/0607/techweb/02-python-cgi.pdf
        # Alternative:
        # return get_cgi_parameter_str(form, key) # contents of the file
    # Otherwise, information about problems:
    if not fileitem.file:
        logger.warning('get_cgi_parameter_file: fileitem has no file')
    elif not fileitem.filename:
        logger.warning('get_cgi_parameter_file: fileitem has no filename')
    else:
        logger.warning('get_cgi_parameter_file: unknown failure reason')
    return (None, None)

    # "If a field represents an uploaded file, accessing the value
    # via the value attribute or the getvalue() method reads the
    # entire file in memory as a string. This may not be what you
    # want. You can test for an uploaded file by testing either
    # the filename attribute or the file attribute. You can then
    # read the data at leisure from the file attribute:"


def cgi_parameter_exists(form, key):
    """Does a CGI form contain the key?"""
    s = get_cgi_parameter_str(form, key)
    return (s is not None)


def checkbox_checked(b):
    """Returns ' checked="checked"' if b is true; otherwise ''.

    Use to fill the {} in e.g.:
        <label>
            <input type="checkbox" name="myfield" value="1"{}>
            This will be pre-ticked if you insert " checked" where the braces
            are. The newer, more stringent requirement is ' checked="checked"'.
        </label>
    """
    return ' checked="checked"' if b else ''


def option_selected(variable, testvalue):
    """Returns ' selected="selected"' if variable == testvalue else ''; for use
    with HTML select options."""
    return ' selected="selected"' if variable == testvalue else ''


# =============================================================================
# Environment
# =============================================================================

def getenv_escaped(key, default=None):
    """Returns an environment variable's value, CGI-escaped, or None."""
    value = os.getenv(key, default)
    return cgi.escape(value) if value is not None else None


def getconfigvar_escaped(config, section, key):
    """Returns a CGI-escaped version of the value read from an INI file using
    ConfigParser, or None."""
    value = config.get(section, key)
    return cgi.escape(value) if value is not None else None


def get_cgi_fieldstorage_from_wsgi_env(env, includeQueryString=True):
    """Returns a cgi.FieldStorage object from the WSGI environment."""
    # http://stackoverflow.com/questions/530526/accessing-post-data-from-wsgi
    post_env = env.copy()
    if not includeQueryString:
        post_env['QUERY_STRING'] = ''
    form = cgi.FieldStorage(
        fp=env['wsgi.input'],
        environ=post_env,
        keep_blank_values=True
    )
    return form


# =============================================================================
# Blobs, pictures...
# =============================================================================

def is_valid_png(blob):
    """Does a blob have a valid PNG signature?"""
    if not blob:
        return False
    return blob[:8] == PNG_SIGNATURE_HEX


def get_png_data_url(blob):
    """Converts a PNG blob into a local URL encapsulating the PNG."""
    return BASE64_PNG_URL_PREFIX + base64.b64encode(blob)


def get_png_img_html(blob, extra_html_class=None):
    """Converts a PNG blob to an HTML IMG tag with embedded data."""
    return """<img {}src="{}" />""".format(
        'class="{}" '.format(extra_html_class) if extra_html_class else "",
        get_png_data_url(blob)
    )


# =============================================================================
# HTTP results
# =============================================================================

# Also, filenames:
#   http://stackoverflow.com/questions/151079
#   http://greenbytes.de/tech/tc2231/#inlwithasciifilenamepdf

def pdf_result(pdf_binary, extraheaders=[], filename=None):
    """Returns (contenttype, extraheaders, data) tuple for a PDF."""
    if filename:
        extraheaders.append(
            ('content-disposition', 'inline; filename="{}"'.format(filename))
        )
    contenttype = 'application/pdf'
    if filename:
        contenttype += '; filename="{}"'.format(filename)
    return (contenttype, extraheaders, str(pdf_binary))


def zip_result(zip_binary, extraheaders=[], filename=None):
    """Returns (contenttype, extraheaders, data) tuple for a ZIP."""
    if filename:
        extraheaders.append(
            ('content-disposition', 'inline; filename="{}"'.format(filename))
        )
    contenttype = 'application/zip'
    if filename:
        contenttype += '; filename="{}"'.format(filename)
    return (contenttype, extraheaders, str(zip_binary))


def html_result(html, extraheaders=[]):
    """Returns (contenttype, extraheaders, data) tuple for UTF-8 HTML."""
    return ('text/html; charset=utf-8', extraheaders, html.encode("utf-8"))


def xml_result(xml, extraheaders=[]):
    """Returns (contenttype, extraheaders, data) tuple for UTF-8 XML."""
    return ('text/xml; charset=utf-8', extraheaders, xml.encode("utf-8"))


def text_result(text, extraheaders=[], filename=None):
    """Returns (contenttype, extraheaders, data) tuple for UTF-8 text."""
    if filename:
        extraheaders.append(
            ('content-disposition', 'inline; filename="{}"'.format(filename))
        )
    contenttype = 'text/plain; charset=utf-8'
    if filename:
        contenttype += '; filename="{}"'.format(filename)
    return (contenttype, extraheaders, text.encode("utf-8"))


def tsv_result(text, extraheaders=[], filename=None):
    """Returns (contenttype, extraheaders, data) tuple for UTF-8 TSV."""
    if filename:
        extraheaders.append(
            ('content-disposition', 'inline; filename="{}"'.format(filename))
        )
    contenttype = 'text/tab-separated-values; charset=utf-8'
    if filename:
        contenttype += '; filename="{}"'.format(filename)
    return (contenttype, extraheaders, text.encode("utf-8"))


def print_result_for_plain_cgi_script_from_tuple(contenttype_headers_content,
                                                 status='200 OK'):
    """Writes HTTP result to stdout.

    contenttype_headers_content is a tuple containing:
        (contenttype, extraheaders, data)
    """
    contenttype, headers, content = contenttype_headers_content
    print_result_for_plain_cgi_script(contenttype, headers, content, status)


def print_result_for_plain_cgi_script(contenttype, headers, content,
                                      status='200 OK'):
    """Writes HTTP request result to stdout."""
    headers = [
        ("Status", status),
        ("Content-Type", contenttype),
        ("Content-Length", str(len(content))),
    ] + headers
    sys.stdout.write("\n".join([h[0] + ": " + h[1] for h in headers]) + "\n\n")
    sys.stdout.write(content)


# =============================================================================
# HTML
# =============================================================================

def webify(v, preserve_newlines=True):
    """Converts a value into an HTML-safe str/unicode.

    Converts value v to a string (or unicode); escapes it to be safe in HTML
    format (escaping ampersands, replacing newlines with <br>, etc.).
    Returns str/unicode, depending on input. Returns "" for blank input.
    """
    nl = "<br>" if preserve_newlines else " "
    if v is None:
        return ""
    elif isinstance(v, unicode):
        return cgi.escape(v).replace("\n", nl).replace("\\n", nl)
    else:
        return cgi.escape(str(v)).replace("\n", nl).replace("\\n", nl)


def websafe(value):
    """Makes a string safe for inclusion in ASCII-encoded HTML."""
    return cgi.escape(value).encode('ascii', 'xmlcharrefreplace')
    # http://stackoverflow.com/questions/1061697


def replace_nl_with_html_br(str):
    """Replaces newlines with <br>."""
    return _NEWLINE_REGEX.sub("<br>", str)


def bold_if_not_blank(x):
    """HTML-emboldens content, unless blank."""
    if x is None:
        return u"{}".format(x)
    return u"<b>{}</b>".format(x)


def make_urls_hyperlinks(text):
    """Adds hyperlinks to text that appears to contain URLs."""
    # http://stackoverflow.com/questions/1071191
    # http://stackp.online.fr/?p=19
    pat_url = re.compile(r'''
        (?x)(              # verbose identify URLs within text
        (http|ftp|gopher)  # make sure we find a resource type
        ://                # ...needs to be followed by colon-slash-slash
        (\w+[:.]?){2,}     # at least two domain groups, e.g. (gnosis.)(cx)
        (/?|               # could be just the domain name (maybe w/ slash)
        [^ \n\r"]+         # or stuff then space, newline, tab, quote
        [\w/])             # resource name ends in alphanumeric or slash
        (?=[\s\.,>)'"\]])  # assert: followed by white or clause ending
        )                  # end of match group
    ''')
    pat_email = re.compile('([\w\-\.]+@(\w[\w\-]+\.)+[\w\-]+)')
    for url in re.findall(pat_url, text):
        text = text.replace(
            url[0],
            '<a href="%(url)s">%(url)s</a>' % {"url": url[0]}
        )
    for email in re.findall(pat_email, text):
        text = text.replace(
            email[0],
            '<a href="mailto:%(email)s">%(email)s</a>' % {"email": email[0]}
        )
    return text


def html_table_from_query(rows, descriptions):
    """
    Converts rows from an SQL query result to an HTML table.
    Suitable for processing output from rnc_db / fetchall_with_fieldnames(sql)
    """
    html = u"<table>\n"

    # Header row
    html += u"<tr>"
    for x in descriptions:
        if x is None:
            x = u""
        html += u"<th>{}</th>".format(webify(x))
    html += u"</tr>\n"

    # Data rows
    for row in rows:
        html += u"<tr>"
        for x in row:
            if x is None:
                x = u""
            html += u"<td>{}</td>".format(webify(x))
        html += u"<tr>\n"

    html += u"</table>\n"
    return html
