#!/usr/bin/env python3
# anonymise/anon_constants.py

"""
Shared constants for CRATE anonymiser.

Author: Rudolf Cardinal
Created at: 18 Feb 2015
Last update: 22 Nov 2015

Copyright/licensing:

    Copyright (C) 2015-2015 Rudolf Cardinal (rudolf@pobox.com).
    Department of Psychiatry, University of Cambridge.

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

from pythonlib.rnc_lang import AttrDict

ALTERMETHOD = AttrDict(
    TRUNCATEDATE="truncatedate",
    SCRUBIN="scrub",
    BIN2TEXT="binary_to_text",
    BIN2TEXT_SCRUB="binary_to_text_scrub",
    FILENAME2TEXT="filename_to_text",
    FILENAME2TEXT_SCRUB="filename_to_text_scrub"
)

DEFAULT_INDEX_LEN = 20  # for data types where it's mandatory

INDEX = AttrDict(
    NORMAL="I",
    UNIQUE="U",
    FULLTEXT="F"
)

LONGTEXT = "LONGTEXT"

MAX_PID_STR = "9" * 10  # e.g. NHS numbers are 10-digit

# Better overall than string.maketrans:
ODD_CHARS_TRANSLATE = [chr(x) for x in range(0, 256)]
for c in '()/ ':
    ODD_CHARS_TRANSLATE[ord(c)] = '_'
for i in range(0, 32):
    ODD_CHARS_TRANSLATE[i] = '_'
for i in range(127, 256):
    ODD_CHARS_TRANSLATE[i] = '_'
ODD_CHARS_TRANSLATE = "".join(ODD_CHARS_TRANSLATE)

SCRUBMETHOD = AttrDict(
    WORDS="words",
    PHRASE="phrase",
    NUMERIC="number",
    DATE="date",
    CODE="code"
)

SCRUBSRC = AttrDict(
    PATIENT="patient",
    THIRDPARTY="thirdparty"
)

SEP = "=" * 20 + " "

SRCFLAG = AttrDict(
    PK="K",
    ADDSRCHASH="H",
    PRIMARYPID="P",
    DEFINESPRIMARYPIDS="*",
    MASTERPID="M",
    CONSTANT="C",
    ADDITION_ONLY="A"
)

TRID_CACHE_PID_FIELDNAME = "pid"
TRID_CACHE_TRID_FIELDNAME = "trid"

RAW_SCRUBBER_FIELDNAME_PATIENT = "_raw_scrubber_patient"
RAW_SCRUBBER_FIELDNAME_TP = "_raw_scrubber_tp"
BIGINT_UNSIGNED = "BIGINT UNSIGNED"
TRID_TYPE = "INT UNSIGNED"
MAX_TRID = 4294967295
# https://dev.mysql.com/doc/refman/5.0/en/numeric-type-overview.html
# Maximum INT UNSIGNED is              4294967295.
# Maximum BIGINT UNSIGNED is 18446744073709551615.
