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


from __future__ import print_function
import argparse
import cStringIO
import docx  # sudo pip install docx
import io
import os
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter  # sudo pip install pdfminer  # noqa
from pdfminer.converter import TextConverter  # sudo pip install pdfminer  # noqa
from pdfminer.layout import LAParams  # sudo pip install pdfminer  # noqa
from pdfminer.pdfpage import PDFPage  # sudo pip install pdfminer  # noqa
from subprocess import Popen, PIPE
import sys
from xml.etree import cElementTree as ElementTree
import zipfile

ENCODING = "utf-8"


def convert_pdf_to_txt(filename=None, blob=None):
    """Pass either a filename or a binary object."""
    if filename:
        fp = file(filename, 'rb')
    else:
        fp = io.BytesIO(blob)
    rsrcmgr = PDFResourceManager()
    retstr = cStringIO.StringIO()
    codec = ENCODING
    laparams = LAParams()
    device = TextConverter(rsrcmgr, retstr, codec=codec, laparams=laparams)
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    password = ""
    maxpages = 0
    caching = True
    pagenos = set()
    for page in PDFPage.get_pages(fp, pagenos, maxpages=maxpages,
                                  password=password, caching=caching,
                                  check_extractable=True):
        interpreter.process_page(page)
    text = retstr.getvalue().decode(ENCODING)
    return text


def convert_docx_to_text(filename=None, blob=None):
    """Pass either a filename or a binary object."""
    if filename:
        fp = filename
        # docx.opendocx(file) uses zipfile.ZipFile, which can take either a
        # filename or a file-like object
        #   https://github.com/mikemaccana/python-docx/blob/master/docx.py
        #   https://docs.python.org/2/library/zipfile.html
    else:
        fp = io.BytesIO(blob)
    document = docx.opendocx(fp)
    paratextlist = docx.getdocumenttext(document)
    return '\n\n'.join(paratextlist)


def convert_odt_to_text(filename=None, blob=None):
    """Pass either a filename or a binary object."""
    # We can't use exactly the same method as for DOCX files, using docx:
    # sometimes that works, but sometimes it falls over with:
    # KeyError: "There is no item named 'word/document.xml' in the archive"
    if filename:
        fp = filename
        # docx.opendocx(file) uses zipfile.ZipFile, which can take either a
        # filename or a file-like object
        #   https://github.com/mikemaccana/python-docx/blob/master/docx.py
        #   https://docs.python.org/2/library/zipfile.html
    else:
        fp = io.BytesIO(blob)
    z = zipfile.ZipFile(fp)
    tree = ElementTree.fromstring(z.read('content.xml'))
    # ... may raise zipfile.BadZipfile
    textlist = []
    for element in tree.iter():
        if element.text:
            textlist.append(element.text.strip())
    return '\n\n'.join(textlist)


def get_cmd_output(*args):
    p = Popen(args, stdout=PIPE)
    stdout, stderr = p.communicate()
    return stdout.decode(ENCODING, errors='ignore')


def get_cmd_output_from_stdin(stdin_content, *args):
    p = Popen(args, stdin=PIPE, stdout=PIPE)
    stdout, stderr = p.communicate(input=stdin_content)
    return stdout.decode(ENCODING, errors='ignore')


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
    if extension == ".doc":
        if filename:
            return get_cmd_output('antiword', filename)  # IN CASE OF FAILURE: sudo apt-get install antiword  # noqa
        else:
            return get_cmd_output_from_stdin(blob, 'antiword', '-')  # IN CASE OF FAILURE: sudo apt-get install antiword  # noqa
    elif extension == ".docx":
        return convert_docx_to_text(filename=filename, blob=blob)
    elif extension == ".odt":
        return convert_odt_to_text(filename=filename, blob=blob)
    elif extension == ".pdf":
        return convert_pdf_to_txt(filename=filename, blob=blob)
    else:
        return ValueError(
            "document_to_text: Unknown filetype: {}".format(extension))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("inputfile", nargs="?",
                        help="Input file name")
    args = parser.parse_args()
    if not args.inputfile:
        parser.print_help(sys.stderr)
        return
    result = document_to_text(filename=args.inputfile)
    if result:
        print(result.encode(ENCODING))


if __name__ == '__main__':
    main()
