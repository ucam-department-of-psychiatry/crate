#!/usr/bin/python
# -*- encoding: utf8 -*-

"""Support for platform-specific problems.

Author: Rudolf Cardinal (rudolf@pobox.com)
Created: 2013
Last update: 24 Sep 2015

Copyright/licensing:

    Copyright (C) 2013-2015 Rudolf Cardinal (rudolf@pobox.com).

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

import codecs
import six
from six.moves import reload_module
import sys


# =============================================================================
# Fix UTF-8 output problems on Windows
# =============================================================================
# http://stackoverflow.com/questions/5419

def fix_windows_utf8_output():
    if six.PY3:
        return
    reload_module(sys)
    sys.setdefaultencoding('utf-8')
    # print sys.getdefaultencoding()

    if sys.platform == 'win32':
        try:
            import win32console
        except:
            print ("Python Win32 Extensions module is required.\n "
                   "You can download it from "
                   "https://sourceforge.net/projects/pywin32/ "
                   "(x86 and x64 builds are available)\n")
            exit(-1)
        # win32console implementation  of SetConsoleCP does not return a value
        # CP_UTF8 = 65001
        win32console.SetConsoleCP(65001)
        if (win32console.GetConsoleCP() != 65001):
            raise RuntimeError("Cannot set console codepage to 65001 (UTF-8)")
        win32console.SetConsoleOutputCP(65001)
        if (win32console.GetConsoleOutputCP() != 65001):
            raise RuntimeError("Cannot set console output codepage to 65001 "
                               "(UTF-8)")

    sys.stdout = codecs.getwriter('utf8')(sys.stdout)
    sys.stderr = codecs.getwriter('utf8')(sys.stderr)
    # CHECK: does that modify the "global" sys.stdout?
    # You can't use "global sys.stdout"; that raises an error


def test_windows_utf8_output():
    print(u"This is an Е乂αmp١ȅ testing Unicode support using Arabic, Latin, "
          u"Cyrillic, Greek, Hebrew and CJK code points.\n")


if __name__ == '__main__':
    fix_windows_utf8_output()
    test_windows_utf8_output()
