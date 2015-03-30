#!/usr/bin/python2.7

"""
Converts a bunch of stuff to text, either from external files or from in-memory
binary objects (BLOBs).

Prerequisites:

    sudo apt-get install antiword
    sudo pip install docx pdfminer

Author: Rudolf Cardinal (rudolf@pobox.com)
Created: Feb 2015
Last update: 25 Mar 2015

Copyright/licensing:

    Copyright (C) 2015-2015 Rudolf Cardinal (rudolf@pobox.com).

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

See also:
    Word
        http://stackoverflow.com/questions/125222
        http://stackoverflow.com/questions/42482
    PDF
        http://stackoverflow.com/questions/25665
        https://pypi.python.org/pypi/slate

    http://stackoverflow.com/questions/5725278

    https://pypi.python.org/pypi/fulltext/
    https://media.readthedocs.org/pdf/textract/latest/textract.pdf
"""


# =============================================================================
# Imports
# =============================================================================

from __future__ import print_function
import argparse
import bs4  # sudo apt-get install python-bs4
import cStringIO
import docx  # sudo pip install docx
import io
import os
import pdfminer.pdfinterp  # sudo pip install pdfminer
import pdfminer.converter  # sudo pip install pdfminer
import pdfminer.layout  # sudo pip install pdfminer
import pdfminer.pdfpage   # sudo pip install pdfminer
import pyth.plugins.rtf15.reader  # sudo apt-get install python-pyth
import pyth.plugins.plaintext.writer  # sudo apt-get install python-pyth
import subprocess
import sys
import xml.etree
import zipfile

import logging
logging.basicConfig()
logger = logging.getLogger("rnc_extract_text")
logger.setLevel(logging.DEBUG)

# =============================================================================
# Constants
# =============================================================================

ENCODING = "utf-8"


# =============================================================================
# Support functions
# =============================================================================

def get_filelikeobject(filename=None, blob=None):
    """Guard the use of this function with 'with'."""
    if not filename and not blob:
        raise ValueError("no filename and no blob")
    if filename and blob:
        raise ValueError("specify either filename or blob")
    if filename:
        return open(filename, 'r')
    else:
        return io.BytesIO(blob)


def get_file_contents(filename=None, blob=None):
    if not filename and not blob:
        raise ValueError("no filename and no blob")
    if filename and blob:
        raise ValueError("specify either filename or blob")
    if blob:
        return blob
    with open(filename, 'r') as f:
        return f.read()


def get_cmd_output(*args):
    p = subprocess.Popen(args, stdout=subprocess.PIPE)
    stdout, stderr = p.communicate()
    return stdout.decode(ENCODING, errors='ignore')


def get_cmd_output_from_stdin(stdin_content, *args):
    p = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE)
    stdout, stderr = p.communicate(input=stdin_content)
    return stdout.decode(ENCODING, errors='ignore')


def get_plain_blob(blob):
    # From jaydebeapi, may get: <class 'jpype._jarray.byte[]'>
    if blob is None:
        return None
    return str(blob)
    


# =============================================================================
# Converters
# =============================================================================

def convert_pdf_to_txt(filename=None, blob=None):
    """Pass either a filename or a binary object."""
    with get_filelikeobject(filename, blob) as fp:
        rsrcmgr = pdfminer.pdfinterp.PDFResourceManager()
        retstr = cStringIO.StringIO()
        codec = ENCODING
        laparams = pdfminer.layout.LAParams()
        device = pdfminer.converter.TextConverter(rsrcmgr, retstr, codec=codec,
                                                  laparams=laparams)
        interpreter = pdfminer.pdfinterp.PDFPageInterpreter(rsrcmgr, device)
        password = ""
        maxpages = 0
        caching = True
        pagenos = set()
        for page in pdfminer.pdfpage.PDFPage.get_pages(
                fp, pagenos, maxpages=maxpages, password=password,
                caching=caching, check_extractable=True):
            interpreter.process_page(page)
        text = retstr.getvalue().decode(ENCODING)
    return text


def convert_docx_to_text(filename=None, blob=None):
    """Pass either a filename or a binary object."""
    # docx.opendocx(file) uses zipfile.ZipFile, which can take either a
    # filename or a file-like object
    #   https://github.com/mikemaccana/python-docx/blob/master/docx.py
    #   https://docs.python.org/2/library/zipfile.html
    with get_filelikeobject(filename, blob) as fp:
        document = docx.opendocx(fp)
        paratextlist = docx.getdocumenttext(document)
    return '\n\n'.join(paratextlist)


def convert_odt_to_text(filename=None, blob=None):
    """Pass either a filename or a binary object."""
    # We can't use exactly the same method as for DOCX files, using docx:
    # sometimes that works, but sometimes it falls over with:
    # KeyError: "There is no item named 'word/document.xml' in the archive"
    with get_filelikeobject(filename, blob) as fp:
        z = zipfile.ZipFile(fp)
        tree = xml.etree.cElementTree.fromstring(z.read('content.xml'))
        # ... may raise zipfile.BadZipfile
        textlist = []
        for element in tree.iter():
            if element.text:
                textlist.append(element.text.strip())
    return '\n\n'.join(textlist)


def convert_html_to_text(filename=None, blob=None):
    with get_filelikeobject(filename, blob) as fp:
        soup = bs4.BeautifulSoup(fp)
        return soup.get_text()


def convert_xml_to_text(filename=None, blob=None):
    with get_filelikeobject(filename, blob) as fp:
        soup = bs4.BeautifulStoneSoup(fp)
        return soup.get_text()


def convert_rtf_to_text(filename=None, blob=None):
    with get_filelikeobject(filename, blob) as fp:
        doc = pyth.plugins.rtf15.reader.Rtf15Reader.read(fp)
    # https://github.com/brendonh/pyth/blob/master/pyth/plugins/rtf15/reader.py
    return pyth.plugins.plaintext.writer.PlaintextWriter.write(doc).getvalue()


def convert_doc_to_text(filename=None, blob=None):
    if filename:
        return get_cmd_output(
            'antiword',  # IN CASE OF FAILURE: sudo apt-get install antiword
            filename)
    else:
        return get_cmd_output_from_stdin(
            get_plain_blob(blob),
            'antiword',  # IN CASE OF FAILURE: sudo apt-get install antiword
            '-')  


def convert_anything_to_text(filename=None, blob=None):
    # strings is a standard Unix command to get text from any old rubbish
    if filename:
        return get_cmd_output('strings', filename)
    else:
        return get_cmd_output_from_stdin(blob, 'strings')

# =============================================================================
# Decider
# =============================================================================

def document_to_text(filename=None, blob=None, extension=None):
    """Pass either a filename or a binary object.
    - Raises an exception for malformed arguments, missing files, bad
      filetypes, etc.
    - Returns a string if the file was processed (potentially an empty string).
    """
    if not filename and not blob:
        raise ValueError("document_to_text: no filename and no blob")
    if filename and blob:
        raise ValueError("document_to_text: specify either filename or blob")
    if blob and not extension:
        raise ValueError("document_to_text: need extension hint for blob")
    if filename:
        stub, extension = os.path.splitext(filename)
    else:
        if extension[0] != ".":
            extension = "." + extension
    extension = extension.lower()

    # Ensure blob is an appropriate type
    logger.debug("filename: {}, blob: {}".format(type(filename), type(blob)))
    
    # Choose method
    if extension in [".doc", ".dot"]:
        return convert_doc_to_text(filename, blob)
    elif extension in [".docx", ".docm"]:
        return convert_docx_to_text(filename, blob)
    elif extension in [".odt"]:
        return convert_odt_to_text(filename, blob)
    elif extension in [".pdf"]:
        return convert_pdf_to_txt(filename, blob)
    elif extension in [".html", ".htm"]:
        return convert_html_to_text(filename, blob)
    elif extension in [".xml"]:
        return convert_xml_to_text(filename, blob)
    elif extension in [".log", ".txt"]:
        return get_file_contents(filename, blob)
    elif extension in [".rtf"]:
        return convert_rtf_to_text(filename, blob)
    else:
        raise ValueError(
            "document_to_text: Unknown filetype: {}".format(extension))


# =============================================================================
# main, for command-line use
# =============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("inputfile", nargs="?",
                        help="Input file name")
    args = parser.parse_args()
    if not args.inputfile:
        parser.print_help(sys.stderr)
        return
    result = document_to_text(filename=args.inputfile)
    if result is None:
        return
    elif isinstance(result, unicode):
        print(result.encode(ENCODING))
    else:
        print(result)


if __name__ == '__main__':
    main()
