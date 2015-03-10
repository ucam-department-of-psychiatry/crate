#!/usr/bin/python2.7

"""
From:
    http://davidmburke.com/2014/02/04/python-convert-documents-doc-docx-odt-pdf-to-plain-text-without-libreoffice/  # noqa

Prerequisites:
    sudo apt-get install antiword odt2txt
    sudo easy_install docx pdfminer

See also:
    Word
        http://stackoverflow.com/questions/125222
        http://stackoverflow.com/questions/42482
    PDF
        http://stackoverflow.com/questions/25665
        https://pypi.python.org/pypi/slate
"""


from __future__ import print_function

from subprocess import Popen, PIPE
from docx import opendocx, getdocumenttext

# http://stackoverflow.com/questions/5725278
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfpage import PDFPage
from cStringIO import StringIO

import os


def convert_pdf_to_txt(path):
    rsrcmgr = PDFResourceManager()
    retstr = StringIO()
    codec = 'utf-8'
    laparams = LAParams()
    device = TextConverter(rsrcmgr, retstr, codec=codec, laparams=laparams)
    fp = file(path, 'rb')
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    password = ""
    maxpages = 0
    caching = True
    pagenos = set()
    for page in PDFPage.get_pages(fp, pagenos, maxpages=maxpages,
                                  password=password, caching=caching,
                                  check_extractable=True):
        interpreter.process_page(page)
    fp.close()
    device.close()
    str = retstr.getvalue()
    retstr.close()
    return str


def document_to_text(filename, file_path):
    if filename[-4:] == ".doc":
        cmd = ['antiword', file_path]
        p = Popen(cmd, stdout=PIPE)
        stdout, stderr = p.communicate()
        return stdout.decode('ascii', 'ignore')
    elif filename[-5:] == ".docx":
        document = opendocx(file_path)
        paratextlist = getdocumenttext(document)
        newparatextlist = []
        for paratext in paratextlist:
            newparatextlist.append(paratext.encode("utf-8"))
        return '\n\n'.join(newparatextlist)
    elif filename[-4:] == ".odt":
        cmd = ['odt2txt', file_path]
        p = Popen(cmd, stdout=PIPE)
        stdout, stderr = p.communicate()
        return stdout.decode('ascii', 'ignore')
    elif filename[-4:] == ".pdf":
        return convert_pdf_to_txt(file_path)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("inputfile", nargs="?",
                        help="Input file name")
    args = parser.parse_args()
    if not args.inputfile:
        parser.print_help()
        return
    filename = os.path.basename(args.inputfile)
    file_path = os.path.abspath(args.inputfile)
    result = document_to_text(filename, file_path)
    print(result)


if __name__ == '__main__':
    main()
