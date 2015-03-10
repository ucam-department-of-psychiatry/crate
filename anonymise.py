#!/usr/bin/python2.7
# -*- encoding: utf8 -*-

"""
Anonymise multiple SQL-based databases using a data dictionary.

Author: Rudolf Cardinal
Created at: 18 Feb 2015
Last update: see VERSION_DATE below

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

Performance:

    For a test source database mostly consisting of text (see makedata.py),
    on a 8-core x 3.5-Ghz machine, including (non-full-text) indexing:

from __future__ import division
test_size_mb = 1887
time_s = 84
speed_mb_per_s = test_size_mb / time_s
cpft_size_gb = 84
estimated_cpft_time_min = cpft_size_gb * 1024 * time_s / (test_size_mb * 60)

    Initial speed tests (Mb/s):
        7.9 Mb/s with 1 process, 8 threads
        8.6 Mb/s with 1 process, 16 threads
        18.0 Mb/s with 8 patient processes + 1 for non-patient tables.
        18.0 Mb/s with 16 patient processes + 1 for non-patient tables.
    Most recent:
        22.5 Mb/s with 8 patient processes + 1 for non-patient tables.
    See launch_multiprocess.sh.
    Guesstimate for Feb 2015 CPFT RiO database (about 84 Gb): 1 h 04 min.
    Note that the full-text indexing is very slow, and would be extra.

Incremental updates:

    Where a full run takes 126s, an incremental run with nothing to do takes
    11s.

MySQL full-text indexing:

    http://dev.mysql.com/doc/refman/5.0/en/fulltext-search.html

    Once indexed, change this conventional SQL:
        SELECT something
        WHERE field1 LIKE '%word%' OR field2 LIKE '%word%';

    to one of these:
        SELECT something
        WHERE MATCH(field1, field2) AGAINST ('word');

        SELECT something
        WHERE MATCH(field1, field2) AGAINST ('word');

    ... and there are some more subtle options.

    Improves speed from e.g.:
        SELECT brcid FROM notes WHERE note LIKE '%Citibank%';
        ... 10.66 s
    to:
        SELECT brcid FROM idxnotes WHERE MATCH(note) AGAINST('citibank');
        ...  0.49 s

    NOTE: requires MySQL 5.6 to use FULLTEXT indexes with InnoDB tables (as
    opposed to MyISAM tables, which don't support transactions).

    On Ubuntu 14.04, default MySQL is 5.5, so use:
        sudo apt-get install mysql-server-5.6 mysql-server-core-5.6 \
            mysql-client-5.6 mysql-client-core-5.6
    ... but it does break dependences on (e.g.) mysql-server, so not yet done.


Encryption/hashing

- A normal PID might be an 'M' number, RiO number, or some other such system-
  specific ID number. A master PID might be an NHS number.
- There must not be collisions in the PID -> RID mapping; we need to keep our
  patients separate.
- The transformation must involve something unknown outside this (open-
  source) code. If we used encrypted = hashlib.sha256(plaintext).hexdigest(),
  then anybody could run that function over a bunch of integers from 0 to
  9,999,999,999 and they'd have a simple way of reversing the algorithm for
  all PIDs up to that value.
- So the options are
  (a) hash with a secret salt;
  (b) hash with a random salt;
  (c) encrypt with a secret key.
- We can't use (b), because we want consistency in our PID -> RID mappings
  when we we re-run the anonymisation.
- We do need to reverse one or both transformations, for consent-to-contact
  methods (and potentially clinicaly use), but only a superuser/research
  database manager should be able to do this.
- Thus, if we hash with a secret salt, we'd have to store the PID/RID mapping
  somewhere safe.
- If we encrypt, we can skip that storage and just keep the secret key.
- We also want a consistent output length.
- With encryption, if the key is leaked, everything encrypted with it is
  available to those with access to the encrypted data. With a secret
  constant salt, the same is true (given a dictionary attack, since the stuff
  being encrypted is just a bunch of integers).
- This is *not* the same problem as password storage, where we don't care if
  two users have the same passwords. Here, we need to distinguish patients
  by the RID. It may be acceptable to use a per-patient salt, and then store
  the PID/RID mapping, but for an incremental update one would have to rely
  on being able to retrieve the old PID/RID mapping, or the mapping would
  change. So: per-patient salt wouldn't be safe for incremental updates.
- We're left with (a) and (c). Both are in principle vulnerable to loss of
  the secret information; but that will always be true of a reversible
  system.
- One benefit of encryption, is that we could use public-key encryption and
  this program would then never need to know the decryption key (whereas with
  a hash, it needs to know the salt, so loss of this program's config file
  will be of concern). The decryption key can be stored somewhere especially
  secret. However, RSA (for example) produces long output, e.g. 1024 bytes.
- Remaining options then include:
  (a) SHA256 hash with secret salt;
  (c) AES256 encryption with secret key.
  I don't think either has a strong advantage over the other, so since we do
  have to be able to reverse the system, we might as well use AES256. But
  then... AES should really have a random initialization vector (IV) used
  (typically stored with the encrypted output, which is fine), but that means
  that a second encryption of the same thing (e.g. for a second anonymisation
  run) gives a different output.
- If we want to use hex encoding and end up with an encrypted thing of length
  32 bytes, then the actual pre-hex value needs to be 16 bytes, etc.
- Anyway, pragmatic weakening of security for practical purposes: let's use
  an MD5 hash with a secret salt.

NOT YET IMPLEMENTED:

    - Incremental updates (with incremental data dictionary changes).
    - Date scrubber doesn't scrub ISO8601 format dates (e.g. 1980-10-01T0000),
      because the word boundary condition isn't met, or even more stripped-down
      date formats like 19801001.

"""

# =============================================================================
# Imports
# =============================================================================

from __future__ import division
from __future__ import print_function
import argparse
import codecs
import ConfigParser
import csv
import itertools
import logging
import multiprocessing
import re
import signal
import sys
import threading

from rnc_crypto import MD5Hasher
from rnc_datetime import (
    format_datetime,
    get_now_utc,
    get_now_utc_notz,
    truncate_date_to_first_of_month
)
import rnc_db
from rnc_db import (
    is_sqltype_numeric,
    is_sqltype_text_over_one_char,
    does_sqltype_require_index_len,
    does_sqltype_merit_fulltext_index,
    is_sqltype_valid,
    is_sqltype_integer,
    is_sqltype_date
)
from rnc_lang import (
    convert_attrs_to_bool,
    convert_attrs_to_uppercase,
    convert_attrs_to_int_or_none,
    raise_if_attr_blank,
    count_bool
)

from shared_anon import (
    SQLTYPE_ENCRYPTED_PID,
    reset_logformat,
    ensure_valid_field_name,
    ensure_valid_table_name,
    read_config_string_options,
    DatabaseConfig,
    get_database
)

# =============================================================================
# Global constants
# =============================================================================

VERSION = 0.02
VERSION_DATE = "2015-03-03"
DEFAULT_INDEX_LEN = 20  # for data types where it's mandatory

logging.basicConfig()  # just in case nobody else has done this
logger = logging.getLogger("anonymise")

config = None
dd = None
SEP = "=" * 20 + " "

# =============================================================================
# Demo config
# =============================================================================

DEMO_CONFIG = """
# Configuration file for anonymise.py

# =============================================================================
# Main settings
# =============================================================================

[main]

# -----------------------------------------------------------------------------
# Data dictionary
# -----------------------------------------------------------------------------
# Specify a data dictionary in TSV (tab-separated value) format, with a header
# row. Boolean values can be 0/1, Y/N, T/F, True/False.
# Columns in the data dictionary:
#
#   src_db
#       Specify the source database.
#       Database names are those used in source_databases list below; they
#       don't have to be SQL database names.
#   src_table
#       Table name in source database.
#   src_field
#       Field name in source database.
#   src_datatype
#       SQL data type in source database, e.g. INT, VARCHAR(50).
#   src_pk
#       Boolean. Is this field the primary key for the table it's in?
#
#   primary_pid
#       Boolean. If set:
#       (a) This field will be used to link records for the same patient across
#           all tables. It must therefore be present, and marked in the data
#           dictionary, for ALL tables that contain patient-identifiable
#           information,
#       (b) If the field is not omitted: the field will be hashed as the
#           primary ID (database patient primary key) in the destination.
#   defines_primary_pids
#       Boolean. This row should be used to search for all patient IDs, and
#       will define them for this database. Only those patients will be
#       processed (for all tables containing patient info). Typically, this
#       flag is applied to a SINGLE field in a SINGLE table, the master patient
#       ID.
#
#   scrubsrc_patient
#       Boolean. If true, contains patient-identifiable information that must
#       be removed from "scrub_in" fields.
#   scrubsrc_thirdparty
#       Boolean. If true, contains identifiable information about carer/family/
#       other third party, which must be removed from "scrub_in" fields.
#       (tp = third party)
#   scrubsrc_numeric
#       Boolean. If true, this field (even if textual) is treated as a number
#       for the purposes of scrubbing. Use this for ID numbers, phone numbers,
#       and the like.
#
#   omit
#       Boolean. Omit from output entirely?
#   scrub_in
#       Boolean. Applies to text fields only. If true, the field will have its
#       contents anonymised (using information from other fields).
#   truncate_date
#       Boolean. For date fields; truncate to first of month?
#   master_pid
#       Boolean. Hash this field as the master ID (e.g. NHS number)?
#
#   dest_table
#       Table name in destination database.
#   dest_field
#       Field name in destination database.
#   dest_datatype
#       SQL data type in destination database.
#   add_src_hash
#       Boolean. May only be set for src_pk fields. If set, a field is added to
#       the destination table, with field name as set by the config's
#       source_hash_fieldname variable, containing a hash of the contents of
#       the source record (all fields that are not omitted, OR contain
#       scrubbing information [scrubsrc_patient or scrubsrc_thirdparty]).
#       The field is of type {SQLTYPE_ENCRYPTED_PID}.
#       This table is then capable of incremental updates.
#   index
#       Boolean. Index this field?
#   indexlen
#       Integer. Can be blank. If not, sets the prefix length of the index.
#       Mandatory in MySQL if you apply a normal index to a TEXT or BLOB field.
#   fulltextindex
#       Boolean. Create a FULLTEXT index, for rapid searching within long text
#       fields. (Does not require indexlen.)
#   comment
#       Field comment, stored in destination database.

data_dictionary_filename = testdd.tsv

# -----------------------------------------------------------------------------
# Input fields
# -----------------------------------------------------------------------------

# Specify the (typically integer) patient identifier present in EVERY table.
# It will be replaced by the research ID in the destination database.

per_table_patient_id_field = patient_id

# Master patient ID fieldname. Used for e.g. NHS numbers.

master_pid_fieldname = nhsnum

# -----------------------------------------------------------------------------
# Encryption phrases/passwords
# -----------------------------------------------------------------------------

per_table_patient_id_encryption_phrase = SOME_PASSPHRASE_REPLACE_ME

master_patient_id_encryption_phrase = SOME_OTHER_PASSPHRASE_REPLACE_ME

change_detection_encryption_phrase = YETANOTHER

# -----------------------------------------------------------------------------
# Anonymisation
# -----------------------------------------------------------------------------

# Patient information will be replaced with this

replace_patient_info_with = XXX

# Third-party information will be replaced by this

replace_third_party_info_with = YYY

# Strings to append to every "scrub from" string.
# For example, include "s" if you want to scrub "Roberts" whenever you scrub
# "Robert".
# Multiline field: https://docs.python.org/2/library/configparser.html

scrub_string_suffixes =
    s

# -----------------------------------------------------------------------------
# Output fields and formatting
# -----------------------------------------------------------------------------

# Research ID field name. This will be a {SQLTYPE_ENCRYPTED_PID}.

research_id_fieldname = brcid

# Change-detection hash fieldname. This will be a {SQLTYPE_ENCRYPTED_PID}.

source_hash_fieldname = _src_hash

# Date-to-text conversion formats

date_to_text_format = %Y-%m-%d
# ... ISO-8601, e.g. 2013-07-24
datetime_to_text_format = %Y-%m-%dT%H:%M:%S
# ... ISO-8601, e.g. 2013-07-24T20:04:07

# -----------------------------------------------------------------------------
# Table to be written to in mapping database
# -----------------------------------------------------------------------------

mapping_table = secret_map

# -----------------------------------------------------------------------------
# List of source databases (each of which is defined in its own section).
# -----------------------------------------------------------------------------

# Source database list.
# Multiline field: https://docs.python.org/2/library/configparser.html

source_databases =
    mysourcedb1
    mysourcedb2

# ...

# =============================================================================
# Destination database details. User should have WRITE access.
# =============================================================================

[destination_database]

engine = mysql
host = localhost
port = 3306
user = XXX
password = XXX
db = XXX

# =============================================================================
# Mapping database, containing secret patient ID to research ID mapping.
# User should have WRITE access.
# =============================================================================

[mapping_database]

engine = mysql
host = localhost
port = 3306
user = XXX
password = XXX
db = XXX

# =============================================================================
# SOURCE DATABASE DETAILS BELOW HERE.
# User should have READ access only for safety.
# =============================================================================

[mysourcedb1]

engine = mysql
host = localhost
port = 3306
user = XXX
password = XXX
db = XXX

[mysourcedb2]

engine = mysql
host = localhost
port = 3306
user = XXX
password = XXX
db = XXX

""".format(SQLTYPE_ENCRYPTED_PID=SQLTYPE_ENCRYPTED_PID)

# For the style:
#       [source_databases]
#       source1 = blah
#       source2 = thing
# ... you can't have multiple keys with the same name.
# http://stackoverflow.com/questions/287757


# =============================================================================
# Anonymisation regexes
# =============================================================================

def get_date_regex_elements(dt):
    """Takes a datetime object and returns a list of regex strings with which
    to scrub."""
    # Reminders: ? zero or one, + one or more, * zero or more
    # Non-capturing groups: (?:...)
    # ... https://docs.python.org/2/howto/regex.html
    # ... http://stackoverflow.com/questions/3512471/non-capturing-group
    wb = r"\b"  # word boundary; escape the slash if not using a raw string
    ws = r"\s"  # whitespace; includes newlines
    # Day, allowing leading zeroes and e.g. "1st, 2nd"
    day = "0*" + str(dt.day) + "(?:st|nd|rd|th)?"
    # Month, allowing leading zeroes for numeric and e.g. Feb/February
    month_numeric = "0*" + str(dt.month)
    month_word = dt.strftime("%B")
    month_word = month_word[0:3] + "(?:" + month_word[3:] + ")?"
    month = "(?:" + month_numeric + "|" + month_word + ")"
    # Year
    year = str(dt.year)
    if len(year) == 4:
        year = "(?:" + year[0:2] + ")?" + year[2:4]
        # ... makes e.g. (19)?86, to match 1986 or 86
    # Separator: one or more of: whitespace, /, -, comma
    SEP = "[" + ws + "/,-]+"
    # ... note that the hyphen has to be at the start or end, otherwise it
    #     denotes a range.
    # Regexes
    basic_regexes = [
        day + SEP + month + SEP + year,  # e.g. 13 Sep 2014
        month + SEP + day + SEP + year,  # e.g. Sep 13, 2014
        year + SEP + month + SEP + day,  # e.g. 2014/09/13
    ]
    return [wb + x + wb for x in basic_regexes]


def get_numeric_regex_elements(s, liberal=True):
    """Takes a STRING representation of a number, which may include leading
    zeros (as for phone numbers), and produces a list of regex strings for
    scrubbing.

    We allow all sorts of separators. For example, 0123456789 might appear as
        (01234) 56789
        0123 456 789
        01234-56789
        0123.456.789
    """
    wb = ur"\b"  # word boundary
    s = s.replace(".", r"\.")  # escape any decimal points
    if liberal:
        separators = "[\W]*"  # zero or more non-alphanumeric characters...
        s = separators.join([c for c in s])  # ... can appear anywhere
    return [wb + s + wb]


REGEX_METACHARS = ["\\", "^", "$", ".",
                   "|", "?", "*", "+",
                   "(", ")", "[", "{"]
# http://www.regular-expressions.info/characters.html
# Start with \, for replacement.


def escape_literal_string_for_regex(s):
    # Escape any regex characters. Start with \ -> \\.
    for c in REGEX_METACHARS:
        s.replace(c, "\\" + c)
    return s


def get_digit_string_from_vaguely_numeric_string(s):
    """For example, converts "(01223) 123456" to "01223123456"."""
    return "".join([d for d in s if d.isdigit()])


def remove_whitespace(s):
    return ''.join(s.split())


NON_WHITESPACE_SPLITTERS = re.compile("['’-]+", re.UNICODE)


def get_anon_fragments_from_string(s):
    """
    - Try the examples listed below the function.
    - Note that this is a LIBERAL algorithm, i.e. one prone to anonymise too
      much (e.g. all instances of "Street" if someone has that as part of their
      address).
    - NOTE THAT WE USE THE "WORD BOUNDARY" FACILITY WHEN REPLACING, AND THAT
      TREATS APOSTROPHES AND HYPHENS AS WORD BOUNDARIES.
      Therefore, we don't need the largest-level chunks, like D'Souza.
    """
    #bigfragments = []
    smallfragments = []
    combinedsmallfragments = []
    for chunk in s.split():  # split on whitespace
        #bigfragments.append(chunk)
        for smallchunk in NON_WHITESPACE_SPLITTERS.split(chunk):
            smallfragments.append(smallchunk)
            # OVERLAP here, but we need it for the combination bit, and
            # we remove the overlap at the end.
    # Now we have chunks with e.g. apostrophes in, and all chunks split by
    # everything. Finally, we want all of these lumped together.
    for L in xrange(len(smallfragments) + 1):
        for subset in itertools.combinations(smallfragments, L):
            if subset:
                combinedsmallfragments.append("".join(subset))
    return list(set(smallfragments + combinedsmallfragments))
# EXAMPLES:
# get_anon_fragments_from_string("Bob D'Souza")
# get_anon_fragments_from_string("Jemima Al-Khalaim")
# get_anon_fragments_from_string("47 Russell Square")


def get_string_regex_elements(s, suffixes=None):
    """Takes a string (+/- suffixes, typically ["s"], and returns a list of
    regex strings with which to scrub."""
    wb = ur"\b"  # word boundary
    s = escape_literal_string_for_regex(s)
    if suffixes:
        suffixstr = (
            "(?:"
            + "|".join([escape_literal_string_for_regex(x)
                        for x in suffixes])
            + "|)"  # allows for no suffix at all
        )
    else:
        suffixstr = ""
    return [
        wb + s + suffixstr + wb
    ]


def get_regex_string_from_elements(elementlist):
    if not elementlist:
        return ""
    return u"|".join(elementlist)
    # The or operator | has the lowest precedence.
    # ... http://www.regular-expressions.info/alternation.html
    # We also want to minimize the number of brackets.
    # THEREFORE, ANYTHING CONTRIBUTING FRAGMENTS HERE SHOULD NOT HAVE |
    # OPERATORS AT ITS TOP LEVEL. If it does, it should encapsulate them in a
    # non-capturing group, (?:...)


def get_regex_from_elements(elementlist):
    if not elementlist:
        return None
    try:
        s = get_regex_string_from_elements(elementlist)
        return re.compile(s, re.IGNORECASE | re.UNICODE)
    except:
        logger.exception(u"Failed regex: {}".format(s))
        raise


# Testing:
if False:
    TEST_REGEXES = '''
from __future__ import print_function
import dateutil.parser
import re

testnumber = 34
testnumber_as_text = "123456"
testdate = dateutil.parser.parse("7 Jan 2013")
teststring = "mother"

s = u"""
   I was born on 07 Jan 2013, m'lud.
   It was 7 January 13, or 7/1/13, or 1/7/13, or
   Jan 7 2013, or 2013/01/07, or 2013-01-07,
   or 7th January
   13 (split over a line)
   or Jan 7th 13
   or a host of other variations.

   BUT NOT 8 Jan 2013, or 2013/02/07, or 2013
   Jan 17, or just a number like 7, or a month
   like January, or a nonspecific date like
   Jan 2013 or 7 January.

   I am 34 years old. My mother was 348, or 834, or perhaps 8348.
   Was she 34.6? Don't think so.

   Her IDs include NHS#123456, or 123 456, or (123) 456, or 123456.

   I am 34 years old. My mother was 348, or 834, or perhaps 8348.
   She wasn't my step-mother, or my grandmother, or my mother-in-law.
   She was my MOTHER!

   Unicode apostrophe: the thread’s possession
"""

regex_date = get_regex_from_elements(get_date_regex_elements(testdate))
regex_number = get_regex_from_elements(
    get_numeric_regex_elements(str(testnumber)))
regex_number_as_text = get_regex_from_elements(
    get_numeric_regex_elements(
        get_digit_string_from_vaguely_numeric_string(testnumber_as_text)))
regex_string = get_regex_from_elements(get_string_regex_elements(teststring))
all_elements = (
    get_date_regex_elements(testdate)
    + get_numeric_regex_elements(str(testnumber))
    + get_numeric_regex_elements(
        get_digit_string_from_vaguely_numeric_string(testnumber_as_text))
    + get_string_regex_elements(teststring)
)
regex_all = get_regex_from_elements(all_elements)
print(regex_date.sub("DATE_GONE", s))
print(regex_number.sub("NUMBER_GONE", s))
print(regex_number_as_text.sub("NUMBER_AS_TEXT_GONE", s))
print(regex_string.sub("STRING_GONE", s))
print(regex_all.sub("EVERYTHING_GONE", s))
print(get_regex_string_from_elements(all_elements))
'''


# =============================================================================
# Data dictionary
# =============================================================================
# - Data dictionary as a TSV file, for ease of editing by multiple authors,
#   rather than a database table.

class DataDictionaryRow(object):
    ROWNAMES = [
        "src_db",
        "src_table",
        "src_field",
        "src_datatype",
        "src_pk",

        "primary_pid",
        "defines_primary_pids",

        "scrubsrc_patient",
        "scrubsrc_thirdparty",
        "scrubsrc_numeric",

        "omit",
        "scrub_in",
        "truncate_date",
        "master_pid",

        "dest_table",
        "dest_field",
        "dest_datatype",
        "add_src_hash",
        "index",
        "indexlen",
        "fulltextindex",
        "comment",
    ]

    def __init__(self):
        self.blank()

    def blank(self):
        for x in DataDictionaryRow.ROWNAMES:
            setattr(self, x, None)

    def __str__(self):
        return ", ".join(["{}: {}".format(a, getattr(self, a))
                          for a in DataDictionaryRow.ROWNAMES])

    def set_from_elements(self, elements):
        self.blank()
        if len(elements) != len(DataDictionaryRow.ROWNAMES):
            raise Exception("Bad data dictionary row. Values:\n" +
                            "\n".join(elements))
        for i in xrange(len(elements)):
            setattr(self, DataDictionaryRow.ROWNAMES[i], elements[i])
        convert_attrs_to_bool(self, [
            "src_pk",

            "primary_pid",
            "defines_primary_pids",

            "scrubsrc_patient",
            "scrubsrc_thirdparty",
            "scrubsrc_numeric",

            "omit",
            "scrub_in",
            "truncate_date",
            "master_pid",

            "add_src_hash",
            "index",
            "fulltextindex",
        ])
        convert_attrs_to_uppercase(self, [
            "src_datatype",
            "dest_datatype",
        ])
        convert_attrs_to_int_or_none(self, [
            "indexlen"
        ])
        self.check_valid()

    def set_from_src_db_info(self, db, table, field, datatype_short,
                             datatype_full, comment=None):
        self.blank()

        self.src_db = db
        self.src_table = table
        self.src_field = field
        self.src_datatype = datatype_full
        self.src_pk = False

        self.primary_pid = (
            self.src_field == config.per_table_patient_id_field)
        self.defines_primary_pids = False

        self.scrubsrc_patient = False
        self.scrubsrc_thirdparty = False
        self.scrubsrc_numeric = (
            is_sqltype_numeric(datatype_full)
            or self.src_field == config.per_table_patient_id_field
            or self.src_field == config.master_pid_fieldname)

        self.omit = True  # for extra safety
        self.scrub_in = is_sqltype_text_over_one_char(datatype_full)
        # ... for safety
        self.truncate_date = False
        self.master_pid = (
            self.src_field == config.master_pid_fieldname)

        self.dest_table = table
        self.dest_field = (config.research_id_fieldname
                           if self.primary_pid else field)
        self.dest_datatype = (SQLTYPE_ENCRYPTED_PID
                              if self.primary_pid or self.master_pid
                              else datatype_full)
        self.add_src_hash = False
        self.index = (self.dest_field ==
                      config.research_id_fieldname)
        self.indexlen = (
            DEFAULT_INDEX_LEN
            if does_sqltype_require_index_len(self.dest_datatype)
            else None)
        self.fulltextindex = does_sqltype_merit_fulltext_index(
            self.dest_datatype)
        self.comment = comment

    def get_tsv(self):
        values = []
        for x in DataDictionaryRow.ROWNAMES:
            v = getattr(self, x)
            if v is None:
                v = ""
            v = str(v)
            values.append(v)
        return "\t".join(values)

    def check_valid(self):
        try:
            self._check_valid()
        except:
            logger.exception("Offending DD row: {}".format(str(self)))
            raise

    def _check_valid(self):
        raise_if_attr_blank(self, [
            "src_db",
            "src_table",
            "src_field",
            "src_datatype",
        ])
        if not self.omit:
            raise_if_attr_blank(self, [
                "dest_table",
                "dest_field",
                "dest_datatype",
            ])

        if self.src_db not in config.src_db_names:
            raise Exception(
                "Data dictionary row references non-existent source "
                "database: {}".format(self.src_db))
        ensure_valid_table_name(self.src_table)
        ensure_valid_field_name(self.src_field)
        if not is_sqltype_valid(self.src_datatype):
            raise Exception(
                "Source field {db}.{t} has invalid data type: {dt}".format(
                    db=self.src_db,
                    t=self.src_table,
                    dt=self.src_datatype,
                )
            )

        if (self.src_field == config.per_table_patient_id_field
                and not is_sqltype_integer(self.src_datatype)):
            raise Exception(
                "All fields with src_field = {} should be "
                "integer, for work distribution purposes".format(
                    self.src_field
                )
            )

        if self.defines_primary_pids and not self.primary_pid:
            raise Exception("All fields with defines_primary_pids set must "
                            "have primary_pid set")

        if self.scrubsrc_patient and self.scrubsrc_thirdparty:
            raise Exception("Can't treat as both patient and third-party info")

        if count_bool([self.primary_pid, self.master_pid,
                       self.truncate_date, self.scrub_in]) > 1:
            raise Exception(
                "Field can be any ONE of: primary_pid, master_pid, "
                "truncate_date, scrub_in.")

        if not self.omit:
            ensure_valid_table_name(self.dest_table)
            ensure_valid_field_name(self.dest_field)
            if self.dest_field == config.source_hash_fieldname:
                raise Exception(
                    "Destination fields can't be named {f}, as that's the "
                    "name set in the config's source_hash_fieldname "
                    "variable".format(config.source_hash_fieldname))
            if not is_sqltype_valid(self.dest_datatype):
                raise Exception(
                    "Source field {db}.{t} has invalid data type: {dt}".format(
                        db=self.destination_database,
                        t=self.dest_table,
                        dt=self.dest_datatype,
                    )
                )
            if self.src_field == config.per_table_patient_id_field:
                if not self.primary_pid:
                    raise Exception(
                        "All fields with src_field = {} used in output should "
                        "have primary_pid set.".format(self.src_field))
                if self.dest_field != config.research_id_fieldname:
                    raise Exception(
                        "All fields with src_field = {} used in output should "
                        "have dest_field = {}".format(
                            config.per_table_patient_id_field,
                            config.research_id_fieldname))
            if (self.src_field == config.master_pid_fieldname
                    and not self.master_pid):
                raise Exception(
                    "All fields with src_field = {} used in output should have"
                    " master_pid set.".format(config.master_pid_fieldname))

            if self.truncate_date and not is_sqltype_date(self.src_datatype):
                raise Exception("Can't set truncate_date for non-date field")
            if (self.scrub_in
                    and not is_sqltype_text_over_one_char(self.src_datatype)):
                raise Exception("Can't scrub in non-text field or "
                                "single-character text field")

            if ((self.primary_pid or self.master_pid) and
                    self.dest_datatype != SQLTYPE_ENCRYPTED_PID):
                raise Exception(
                    "All primary_pid/master_pid fields used in output must "
                    "have destination_datatype = {}".format(
                        SQLTYPE_ENCRYPTED_PID))

            if self.index and self.fulltextindex:
                raise Exception("Choose either normal or full-text index, "
                                "not both.")
            if (self.index and self.indexlen is None
                    and does_sqltype_require_index_len(self.dest_datatype)):
                raise Exception(
                    "Must specify indexlen to index a TEXT or BLOB field.")

        if self.add_src_hash:
            if not self.src_pk:
                raise Exception(
                    "add_src_hash can only be set on src_pk fields")
            if self.omit:
                raise Exception("Do not set omit on add_src_hash fields")


class DataDictionary(object):
    def __init__(self):
        self.rows = []

    def read_from_file(self, filename):
        self.rows = []
        with open(filename, 'rb') as tsvfile:
            tsv = csv.reader(tsvfile, delimiter='\t')
            headerlist = tsv.next()
            if headerlist != DataDictionaryRow.ROWNAMES:
                raise Exception(
                    "Bad data dictionary file. Must be a tab-separated value "
                    "(TSV) file with the following row headings:\n" +
                    "\n".join(DataDictionaryRow.ROWNAMES)
                )
            logger.debug("Data dictionary has correct header.")
            for rowelements in tsv:
                ddr = DataDictionaryRow()
                ddr.set_from_elements(rowelements)
                self.rows.append(ddr)
        self.check_valid()

    def read_from_source_databases(self):
        self.rows = []
        logger.info("Reading information for draft data dictionary")
        for pretty_dbname, db in config.sources.iteritems():
            schema = db.get_schema()
            logger.info("... database nice name = {}, schema = {}".format(
                pretty_dbname, schema))
            if db.db_flavour == rnc_db.DatabaseSupporter.FLAVOUR_MYSQL:
                sql = """
                    SELECT table_name, column_name, data_type, column_type,
                        column_comment
                    FROM information_schema.columns
                    WHERE table_schema=?
                """
            else:
                sql = """
                    SELECT table_name, column_name, data_type, column_type,
                        NULL
                    FROM information_schema.columns
                    WHERE table_schema=?
                """
            args = [schema]
            rows = db.fetchall(sql, *args)
            for r in rows:
                t = r[0]
                f = r[1]
                datatype_short = r[2].upper()
                datatype_full = r[3].upper()
                c = r[4]
                dd = DataDictionaryRow()
                dd.set_from_src_db_info(pretty_dbname, t, f, datatype_short,
                                        datatype_full, c)
                self.rows.append(dd)

    def cache_stuff(self):
        logger.debug("Caching data dictionary information...")
        self.cached_dest_tables = self._get_dest_tables()
        self.cached_source_databases = self._get_source_databases()
        self.cached_src_tables = {}
        self.cached_src_tables_with_patient_info = {}
        self.cached_patient_src_tables_with_active_destination = {}
        for d in self.cached_source_databases:
            self.cached_src_tables[d] = self._get_src_tables(d)
            self.cached_src_tables_with_patient_info[d] = (
                self._get_src_tables_with_patient_info(d)
            )
            self.cached_patient_src_tables_with_active_destination[d] = (
                self._get_patient_src_tables_with_active_destination(d)
            )
        self.cached_scrub_from_rows = self._get_scrub_from_rows()

    def check_valid(self):
        logger.debug("Checking data dictionary...")
        if not self.rows:
            raise Exception("Empty data dictionary")

        # Remove tables that are entirely redundant
        skiptables = []
        for t in self._get_dest_tables():
            ddr = self.get_rows_for_dest_table(t)
            if all([(r.omit and not r.scrubsrc_patient
                     and not r.scrubsrc_thirdparty) for r in ddr]):
                skiptables.append(t)
        self.rows = [r for r in self.rows
                     if not r.dest_table in skiptables]
        if not self.rows:
            raise Exception("Empty data dictionary after removing "
                            "redundant tables")
        self.cache_stuff()

        # Check individual rows
        for r in self.rows:
            r.check_valid()
        # Now check collective consistency

        logger.debug("Checking DD: destination tables...")
        for t in self.get_dest_tables():
            sdt = self.get_src_dbs_tables_for_dest_table(t)
            if len(sdt) > 1:
                raise Exception(
                    "Destination table {t} is mapped to by multiple "
                    "source databases: {s}".format(
                        t=t,
                        s=", ".join(["{}.{}".format(s[0], s[1]) for s in sdt]),
                    )
                )

        logger.debug("Checking DD: source tables...")
        for d in self.get_source_databases():
            db = config.sources[d]
            for t in self.get_src_tables(d):

                dt = self.get_dest_tables_for_src_db_table(d, t)
                if len(dt) > 1:
                    raise Exception(
                        "Source table {d}.{t} maps to >1 destination table: "
                        "{dt}".format(
                            d=d,
                            t=t,
                            dt=", ".join(dt),
                        )
                    )

                rows = self.get_rows_for_src_table(d, t)
                if any([r.scrub_in or r.master_pid
                        for r in rows if not r.omit]):
                    fieldnames = self.get_fieldnames_for_src_table(d, t)
                    if not config.per_table_patient_id_field in fieldnames:
                        raise Exception(
                            "Source table {d}.{t} has a scrub_in or "
                            "master_pid field but no {p} field".format(
                                d=d,
                                t=t,
                                p=config.per_table_patient_id_field,
                            )
                        )

                n_pks = sum([1 if x.src_pk else 0 for x in rows])
                if n_pks > 1:
                    raise Exception("Table {d}.{t} has >1 src_pk set".format(
                        d=d, t=t))

                if not db.table_exists(t):
                    raise Exception(
                        "Table {t} missing from source database {d}".format(
                            t=t,
                            d=d
                        )
                    )

        logger.debug("Checking DD: global checks...")
        n_definers = sum([1 if x.defines_primary_pids else 0
                          for x in self.rows])
        if n_definers == 0:
            raise Exception("Must have at least one field with "
                            "'defines_primary_pids' set.")
        if n_definers > 1:
            logger.warning("Unusual: >1 field with "
                           "defines_primary_pids set.")

    def _get_dest_tables(self):
        return list(set([ddr.dest_table for ddr in self.rows
                         if ddr.dest_table
                         and not ddr.omit]))

    def get_dest_tables(self):
        return self.cached_dest_tables

    def get_dest_tables_for_src_db_table(self, src_db, src_table):
        return list(set([ddr.dest_table for ddr in self.rows
                         if ddr.src_db == src_db
                         and ddr.src_table == src_table
                         and not ddr.omit]))

    def _get_source_databases(self):
        return list(set([ddr.src_db for ddr in self.rows]))

    def get_source_databases(self):
        return self.cached_source_databases

    def get_src_dbs_tables_for_dest_table(self, dest_table):
        return list(set([
            (ddr.src_db, ddr.src_table)
            for ddr in self.rows
            if ddr.dest_table == dest_table
        ]))

    def _get_src_tables(self, src_db):
        return list(set([ddr.src_table for ddr in self.rows
                         if ddr.src_db == src_db]))

    def get_src_tables(self, src_db):
        return self.cached_src_tables[src_db]

    def _get_patient_src_tables_with_active_destination(self, src_db):
        potential_tables = self._get_src_tables_with_patient_info(
            src_db)
        tables = []
        for t in potential_tables:
            ddrows = self.get_rows_for_src_table(src_db, t)
            if any(not ddr.omit for ddr in ddrows):
                tables.append(t)
        return tables

    def get_patient_src_tables_with_active_destination(self, src_db):
        return self.cached_patient_src_tables_with_active_destination[
            src_db]

    def get_src_tables_with_no_patient_info(self, src_db):
        potential_tables = self.get_src_tables(src_db)
        tables = []
        for t in potential_tables:
            if any([ddr.primary_pid or ddr.master_pid
                    for ddr in self.get_rows_for_src_table(src_db, t)]):
                continue
            tables.append(t)
        return tables

    def _get_src_tables_with_patient_info(self, src_db):
        potential_tables = self.get_src_tables(src_db)
        tables = []
        for t in potential_tables:
            if not any([ddr.primary_pid or ddr.master_pid
                        for ddr in self.get_rows_for_src_table(
                            src_db, t)]):
                continue
            tables.append(t)
        return tables

    def get_src_tables_with_patient_info(self, src_db):
        return self.cached_src_tables_with_patient_info[src_db]

    def get_rows_for_src_table(self, src_db, src_table):
        return [ddr for ddr in self.rows
                if ddr.src_db == src_db
                and ddr.src_table == src_table]

    def get_rows_for_dest_table(self, dest_table):
        return [ddr for ddr in self.rows
                if ddr.dest_table == dest_table]

    def get_fieldnames_for_src_table(self, src_db, src_table):
        return [ddr.src_field for ddr in self.rows
                if ddr.src_db == src_db
                and ddr.src_table == src_table]

    def _get_scrub_from_rows(self):
        return [ddr for ddr in self.rows
                if (ddr.scrubsrc_patient
                    or ddr.scrubsrc_thirdparty)]
        # ... even if omit flag set

    def get_scrub_from_rows(self):
        return self.cached_scrub_from_rows

    def get_tsv(self):
        return "\n".join(
            ["\t".join(DataDictionaryRow.ROWNAMES)]
            + [r.get_tsv() for r in self.rows]
        )

    def get_src_dbs_tables_with_no_patient_info(self):
        db_table_tuple_list = []
        for db in self.get_source_databases():
            for t in self.get_src_tables(db):
                if any([ddr.primary_pid or ddr.master_pid
                        for ddr in self.get_rows_for_src_table(db, t)]):
                    continue
            db_table_tuple_list.append((db, t))
        return db_table_tuple_list

    def get_srchash_info(self, src_db, src_table):
        dest_table = None
        src_pk = None
        dest_pk = None
        src_hash = False
        ddrows = self.get_rows_for_src_table(src_db, src_table)
        for ddr in ddrows:
            if not dest_table:
                dest_table = ddr.dest_table
            if ddr.src_pk:
                src_pk = ddr.src_field
                dest_pk = ddr.dest_field
                src_hash = ddr.add_src_hash
        return (src_pk, src_hash, dest_table, dest_pk)

    def has_active_destination(self, src_db, src_table):
        ddrows = self.get_rows_for_src_table(src_db, src_table)
        return any([not x.omit for x in ddrows])


# =============================================================================
# Config
# =============================================================================

class Config(object):
    def __init__(self, filename):
        self.read(filename)
        self.check_valid()
        self.report_every_n_rows = 100

    def read(self, filename):
        """Read config from file."""
        parser = ConfigParser.RawConfigParser()
        parser.readfp(codecs.open(filename, "r", "utf8"))
        read_config_string_options(self, parser, "main", [
            "data_dictionary_filename",
            "per_table_patient_id_field",
            "master_pid_fieldname",
            "per_table_patient_id_encryption_phrase",
            "master_patient_id_encryption_phrase",
            "change_detection_encryption_phrase",
            "replace_patient_info_with",
            "replace_third_party_info_with",
            "scrub_string_suffixes",
            "research_id_fieldname",
            "source_hash_fieldname",
            "date_to_text_format",
            "datetime_to_text_format",
            "mapping_table",
            "source_databases",
        ])
        # Processing of parameters
        if self.scrub_string_suffixes is None:
            self.scrub_string_suffixes = ""
        self.scrub_string_suffixes = [
            x.strip() for x in self.scrub_string_suffixes.splitlines()]
        self.scrub_string_suffixes = [x for x in self.scrub_string_suffixes
                                      if x]
        # Databases
        self.destdb_config = DatabaseConfig(parser, "destination_database")
        self.destdb = get_database(self.destdb_config)
        self.mapdb_config = DatabaseConfig(parser, "mapping_database")
        self.mapdb = get_database(self.mapdb_config)
        self.src_db_configs = []
        self.sources = {}
        self.src_db_names = []
        for sourcedb_name in [x.strip()
                              for x in self.source_databases.splitlines()]:
            if not sourcedb_name:
                continue
            self.src_db_names.append(sourcedb_name)
            dbc = DatabaseConfig(parser, sourcedb_name)
            self.src_db_configs.append(dbc)
            db = get_database(dbc)
            self.sources[sourcedb_name] = db
        # Hashers
        self.primary_pid_hasher = None
        self.master_pid_hasher = None
        self.change_detection_hasher = None

    def check_valid(self):
        """Raise exception if config is invalid."""

        # Test databases
        if not self.sources:
            raise Exception("No source databases specified.")
        if not self.destdb:
            raise Exception("No destination database specified.")
        if not self.mapdb:
            raise Exception("No mapping database specified.")

        # Test field names
        if not self.per_table_patient_id_field:
            raise Exception("Blank fieldname: per_table_patient_id_field")
        ensure_valid_field_name(self.per_table_patient_id_field)

        if not self.research_id_fieldname:
            raise Exception("Blank fieldname: research_id_fieldname")
        ensure_valid_field_name(self.research_id_fieldname)

        if self.master_pid_fieldname:
            ensure_valid_field_name(self.master_pid_fieldname)

        if self.source_hash_fieldname:
            ensure_valid_field_name(self.source_hash_fieldname)

        if self.per_table_patient_id_field == self.source_hash_fieldname:
            raise Exception("Config: per_table_patient_id_field can't be the "
                            "same as source_hash_fieldname")
        if self.research_id_fieldname == self.source_hash_fieldname:
            raise Exception("Config: research_id_fieldname can't be the "
                            "same as source_hash_fieldname")

        # Test valid table names
        ensure_valid_table_name(self.mapping_table)

        # Test strings
        if not self.replace_patient_info_with:
            raise Exception("Blank replace_patient_info_with")
        if not self.replace_third_party_info_with:
            raise Exception("Blank replace_third_party_info_with")
        if (self.replace_patient_info_with ==
                self.replace_third_party_info_with):
            raise Exception("Inadvisable: replace_patient_info_with == "
                            "replace_third_party_info_with")

        # Test date conversions
        testtime = get_now_utc_notz()
        format_datetime(testtime, self.date_to_text_format)
        format_datetime(testtime, self.datetime_to_text_format)

        # Load encryption keys
        if not self.per_table_patient_id_encryption_phrase:
            raise Exception("Missing per_table_patient_id_encryption_phrase")
        self.primary_pid_hasher = MD5Hasher(
            self.per_table_patient_id_encryption_phrase)

        if not self.master_patient_id_encryption_phrase:
            raise Exception("Missing master_patient_id_encryption_phrase")
        self.master_pid_hasher = MD5Hasher(
            self.master_patient_id_encryption_phrase)

        if not self.change_detection_encryption_phrase:
            raise Exception("Missing change_detection_encryption_phrase")
        self.change_detection_hasher = MD5Hasher(
            self.change_detection_encryption_phrase)

        # OK!
        logger.debug("Config validated.")

    def encrypt_primary_pid(self, pid):
        return self.primary_pid_hasher.hash(pid)

    def encrypt_master_pid(self, pid):
        return self.master_pid_hasher.hash(pid)

    def hash_list(self, l):
        """ Hashes a list with Python's built-in hash function.
        We could use Python's build-in hash() function, which produces a 64-bit
        unsigned integer (calculated from: sys.maxint).
        However, there is an outside chance that someone uses a single-field
        table and therefore that this is vulnerable to content discovery via a
        dictionary attack. Thus, we should use a better version.
        """
        return self.change_detection_hasher.hash(repr(l))

    def hash_scrubber(self, scrubber):
        return self.change_detection_hasher.hash(scrubber.get_hash_string())


# =============================================================================
# Scrubber
# =============================================================================

class Scrubber(object):
    def __init__(self, sources, pid):
        self.re_patient = None  # re: regular expression
        self.re_tp = None
        self.re_patient_elements = []
        self.re_tp_elements = []
        logger.debug("building scrubber")
        for ddr in dd.get_scrub_from_rows():
            scrub_type = self.get_scrub_type(ddr.src_datatype,
                                             ddr.scrubsrc_numeric)
            is_patient = ddr.scrubsrc_patient
            for v in gen_all_values_for_patient(sources,
                                                ddr.src_db,
                                                ddr.src_table,
                                                ddr.src_field, pid):
                self.add_value(v, scrub_type, is_patient)
        self.finished_adding()

    @staticmethod
    def get_scrub_type(datatype_long, scrubsrc_numeric):
        if is_sqltype_date(datatype_long):
            return "D"
        elif is_sqltype_text_over_one_char(datatype_long):
            if scrubsrc_numeric:
                return "t"
            else:
                return "T"
        else:
            return "N"

    def add_value(self, value, scrub_type, patient=True):
        if value is None:
            return

        # Note: object reference
        r = self.re_patient_elements if patient else self.re_tp_elements

        if scrub_type == "D":
            # Source is a date.
            r.extend(get_date_regex_elements(value))
        elif scrub_type == "T":
            # Source is text.
            value = unicode(value)
            strings = get_anon_fragments_from_string(value)
            for s in strings:
                r.extend(get_string_regex_elements(
                    s, config.scrub_string_suffixes))
        elif scrub_type == "t":
            # Source is a text field containing a number.
            # Remove everything but the digits
            # Particular examples: phone numbers, e.g. "(01223) 123456".
            r.extend(get_numeric_regex_elements(
                get_digit_string_from_vaguely_numeric_string(value)))
        elif scrub_type == "N":
            # Source is an actual number, to be processed using the fancy
            # number-recognizing refex.
            r.extend(get_numeric_regex_elements(str(value)))
        else:
            raise Exception("Bug: unknown scrub_type to add_value")

    def finished_adding(self):
        #print("PATIENT REGEX PARTS:\n"
        #      + "\n".join(self.re_patient_elements)
        #      + "\n")
        #print("THIRD PARTY REGEX PARTS:\n"
        #      + "\n".join(self.re_tp_elements)
        #      + "\n")
        # Remove duplicates
        self.re_patient_elements = list(set(self.re_patient_elements))
        self.re_tp_elements = list(set(self.re_tp_elements))
        # Create regexes:
        self.re_patient = get_regex_from_elements(self.re_patient_elements)
        self.re_tp = get_regex_from_elements(self.re_tp_elements)

    def get_hash_string(self):
        return repr(self.re_patient_elements + self.re_tp_elements)

    def scrub(self, text):
        # logger.debug("scrubbing")
        if self.re_patient:
            text = self.re_patient.sub(config.replace_patient_info_with, text)
        if self.re_tp:
            text = self.re_tp.sub(config.replace_third_party_info_with, text)
        return text


# =============================================================================
# Database queries
# =============================================================================

def patient_scrubber_unchanged(mapdb, patient_id, scrubber):
    new_scrub_hash = config.hash_scrubber(scrubber)
    sql = """
        SELECT 1
        FROM {table}
        WHERE {patient_id} = ?
        AND {scrubber_hash} = ?
    """.format(
        table=config.mapping_table,
        patient_id=config.per_table_patient_id_field,
        scrubber_hash=config.source_hash_fieldname,
    )
    row = mapdb.fetchone(sql, patient_id, new_scrub_hash)
    return True if row is not None and row[0] == 1 else False


def patient_in_mapdb(mapdb, patient_id):
    sql = """
        SELECT 1
        FROM {table}
        WHERE {patient_id} = ?
    """.format(
        table=config.mapping_table,
        patient_id=config.per_table_patient_id_field,
    )
    row = mapdb.fetchone(sql, patient_id)
    return True if row is not None and row[0] == 1 else False


def record_exists_by_hash(destdb, dest_table, pkfield, pkvalue, hashvalue):
    sql = """
        SELECT 1
        FROM {table}
        WHERE {pkfield}=?
        AND {srchashfield}=?
    """.format(
        table=dest_table,
        pkfield=pkfield,
        srchashfield=config.source_hash_fieldname,
    )
    args = [pkvalue, hashvalue]
    row = destdb.fetchone(sql, *args)
    return True if row is not None and row[0] == 1 else False


# =============================================================================
# Database actions
# =============================================================================

def insert_into_mapping_db(mapdb, pid, rid, scrubber):
    scrubber_hash = config.hash_scrubber(scrubber)
    if patient_in_mapdb(mapdb, pid):
        sql = """
            UPDATE {table}
            SET {scrubber_hash} = ?
            WHERE {patient_id} = ?
        """.format(
            table=config.mapping_table,
            scrubber_hash=config.source_hash_fieldname,
            patient_id=config.per_table_patient_id_field,
        )
        args = [scrubber_hash, pid]
    else:
        sql = """
            INSERT INTO {table}
                ({patient_id}, {research_id}, {scrubber_hash})
            VALUES (?, ?, ?)
        """.format(
            table=config.mapping_table,
            patient_id=config.per_table_patient_id_field,
            research_id=config.research_id_fieldname,
            scrubber_hash=config.source_hash_fieldname,
        )
        args = [pid, rid, scrubber_hash]
    mapdb.db_exec(sql, *args)
    mapdb.commit()
    # Commit immediately, because other processes may need this table promptly.
    # Otherwise, get:
    #   Deadlock found when trying to get lock; try restarting transaction


def wipe_and_recreate_mapping_db(mapdb, incremental=False):
    logger.debug("wipe_and_recreate_mapping_db")
    if not incremental:
        mapdb.drop_table(config.mapping_table)
    sql = """
        CREATE TABLE IF NOT EXISTS {table} (
            {patient_id} INT PRIMARY KEY,
            {research_id} {hash_type} NOT NULL UNIQUE,
            {scrubber_hash} {hash_type}
        )
    """.format(
        table=config.mapping_table,
        hash_type=SQLTYPE_ENCRYPTED_PID,
        patient_id=config.per_table_patient_id_field,
        research_id=config.research_id_fieldname,
        scrubber_hash=config.source_hash_fieldname,
    )
    mapdb.db_exec(sql)
    mapdb.commit()


def wipe_and_recreate_destination_db(destdb, dynamic=False, compressed=False,
                                     incremental=False):
    logger.debug("wipe_and_recreate_destination_db, incremental={}".format(
        incremental))
    if destdb.db_flavour != rnc_db.DatabaseSupporter.FLAVOUR_MYSQL:
        dynamic = False
        compressed = False

    for t in dd.get_dest_tables():
        # Drop
        if not incremental:
            logger.debug("dropping table {}".format(t))
            destdb.drop_table(t)

        # Recreate
        ddr = dd.get_rows_for_dest_table(t)
        fieldspecs = []
        for r in ddr:
            if r.omit:
                continue
            fs = r.dest_field + " " + r.dest_datatype
            if r.comment:
                fs += " COMMENT " + rnc_db.sql_quote_string(r.comment)
            fieldspecs.append(fs)
            if r.add_src_hash:
                # append a special field
                fieldspecs.append(
                    config.source_hash_fieldname + " " +
                    SQLTYPE_ENCRYPTED_PID +
                    " COMMENT 'Hashed amalgamation of all source fields'")
        logger.debug("creating table {}".format(t))
        sql = """
            CREATE TABLE IF NOT EXISTS {table} (
                {fieldspecs}
            )
            {dynamic}
            {compressed}
            CHARACTER SET utf8
            COLLATE utf8_general_ci
        """.format(
            table=t,
            fieldspecs=",".join(fieldspecs),
            dynamic="ROW_FORMAT=DYNAMIC" if dynamic else "",
            compressed="ROW_FORMAT=COMPRESSED" if compressed else "",
        )
        destdb.db_exec_literal(sql)


def delete_dest_rows_with_no_src_row(srcdb, srcdbname, src_table):
    # - Can't do this in a single SQL command, since the engine can't
    #   necessarily see both databases.
    # - Can't do this in a multiprocess way, because we're trying to do a
    #   DELETE WHERE NOT IN.
    if not dd.has_active_destination(srcdbname, src_table):
        return
    (src_pk, src_hash, dest_table, dest_pk) = dd.get_srchash_info(srcdbname,
                                                                  src_table)
    logger.debug("delete_dest_rows_with_no_src_row: source table {}, "
                 "destination table {}".format(src_table, dest_table))
    pks = []
    if src_pk:
        sql = "SELECT {src_pk} FROM {src_table}".format(
            src_pk=src_pk,
            src_table=src_table,
        )
        pks = srcdb.fetchallfirstvalues(sql)
    if not pks:
        logger.debug("... deleting all")
        sql = "DELETE FROM {dest_table}".format(dest_table=dest_table)
        config.destdb.db_exec(sql)
    else:
        logger.debug("... deleting selectively")
        value_string = ','.join(['?'] * len(pks))
        sql = """
            DELETE FROM {dest_table}
            WHERE {dest_pk} NOT IN ({value_string})
        """.format(
            dest_table=dest_table,
            dest_pk=dest_pk,
            value_string=value_string
        )
        config.destdb.db_exec(sql, *pks)
        # http://stackoverflow.com/questions/589284


# =============================================================================
# Generators. Anything reading the main database should use a generator, so the
# script can scale to databases of arbitrary size.
# =============================================================================

def gen_patient_ids(sources, tasknum=0, ntasks=1):
    # ASSIGNS WORK TO THREADS/PROCESSES, via the simple expedient of processing
    # only those patient ID numbers where patientnum % ntasks == tasknum.
    if ntasks > 1 and tasknum >= ntasks:
            raise Exception("Invalid tasknum {}; must be <{}".format(
                tasknum, ntasks))
    for ddr in dd.rows:
        if not ddr.defines_primary_pids:
            continue
        threadcondition = ""
        if ntasks > 1:
            threadcondition = """
                AND {pidfield} % {ntasks} = {tasknum}
            """.format(
                pidfield=ddr.src_field,
                ntasks=ntasks,
                tasknum=tasknum,
            )
        sql = """
            SELECT DISTINCT {pidfield}
            FROM {table}
            WHERE {pidfield} IS NOT NULL
            {threadcondition}
            ORDER BY {pidfield}
        """.format(
            pidfield=ddr.src_field,
            table=ddr.src_table,
            threadcondition=threadcondition,
        )
        db = sources[ddr.src_db]
        cursor = db.cursor()
        db.db_exec_with_cursor(cursor, sql)
        row = cursor.fetchone()
        while row is not None:
            patient_id = row[0]
            logger.debug("Found patient id: {}".format(patient_id))
            # Check that we haven't processed that patient_id already.
            # -- NO, SKIP: (a) was redundant, and (b) breaks for incremental.
            #if not patient_id_exists_in_mapping_db(mapdb, patient_id):
            yield patient_id
            row = cursor.fetchone()


def gen_all_values_for_patient(sources, dbname, table, field, pid):
    logger.debug("gen_all_values_for_patient: {d}.{t}.{f} for PID {p}".format(
        d=dbname, t=table, f=field, p=pid))
    db = sources[dbname]
    sql = """
        SELECT {field}
        FROM {table}
        WHERE {patient_id_field} = ?
    """.format(
        field=field,
        table=table,
        patient_id_field=config.per_table_patient_id_field
    )
    args = [pid]
    cursor = db.cursor()
    db.db_exec_with_cursor(cursor, sql, *args)
    row = cursor.fetchone()
    while row is not None:
        yield row[0]
        row = cursor.fetchone()


def gen_rows(sourcedb, sourcetable, sourcefields, pid=None):
    """ Generates a series of lists of values, each value corresponding to a
    field in sourcefields.
    """
    if pid is None:
        args = []
        where = ""
    else:
        args = [pid]
        where = "WHERE {}=?".format(config.per_table_patient_id_field)
    sql = """
        SELECT {fields}
        FROM {table}
        {where}
    """.format(
        fields=",".join(sourcefields),
        table=sourcetable,
        where=where,
    )
    cursor = sourcedb.cursor()
    sourcedb.db_exec_with_cursor(cursor, sql, *args)
    row = cursor.fetchone()
    while row is not None:
        yield list(row)  # convert from tuple to list so we can modify it
        row = cursor.fetchone()


def gen_index_row_sets_by_table(tasknum=0, ntasks=1):
    indexrows = [ddr for ddr in dd.rows
                 if not ddr.omit and (ddr.index or ddr.fulltextindex)]
    tables = list(set([r.dest_table for r in indexrows]))
    for i in xrange(len(tables)):
        if i % ntasks != tasknum:
            continue
        t = tables[i]
        tablerows = [r for r in indexrows if r.dest_table == t]
        yield (t, tablerows)


def gen_nonpatient_tables(tasknum=0, ntasks=1):
    db_table_pairs = dd.get_src_dbs_tables_with_no_patient_info()
    for i in xrange(len(db_table_pairs)):
        if i % ntasks != tasknum:
            continue
        yield db_table_pairs[i]  # will be a (dbname, table) tuple


# =============================================================================
# Core functions
# =============================================================================
# - For multithreaded use, the patients are divvied up across the threads.
# - KEY THREADING RULE: ALL THREADS MUST HAVE FULLY INDEPENDENT DATABASE
#   CONNECTIONS.

def print_draft_data_dictionary():
    dd = DataDictionary()
    dd.read_from_source_databases()
    print(dd.get_tsv())


def process_table(sourcedb, sourcedbname, sourcetable, destdb,
                  pid=None, scrubber=None, incremental=False):
    logger.debug(
        "process_table: {}.{}, pid={}, incremental={}".format(
            sourcedbname, sourcetable, pid, incremental))
    ddrows = dd.get_rows_for_src_table(sourcedbname, sourcetable)
    addhash = any([ddr.add_src_hash for ddr in ddrows])
    # If addhash is true, there will also be at least one non-omitted row,
    # namely the source PK (by the data dictionary's validation process).
    ddrows = [ddr
              for ddr in ddrows
              if (not ddr.omit) or (addhash and (ddr.scrubsrc_patient
                                                 or ddr.scrubsrc_thirdparty))]
    if not ddrows:
        return
    dest_table = ddrows[0].dest_table
    sourcefields = []
    destfields = []
    pkfield_index = None
    for i in xrange(len(ddrows)):
        ddr = ddrows[i]
        if ddr.src_pk:
            pkfield_index = i
        sourcefields.append(ddr.src_field)
        if not ddr.omit:
            destfields.append(ddr.dest_field)
    if addhash:
        destfields.append(config.source_hash_fieldname)
    n = 0
    for row in gen_rows(sourcedb, sourcetable, sourcefields, pid):
        n += 1
        if n % config.report_every_n_rows == 0:
            logger.info("... processing row {}".format(n))
        else:
            logger.debug("... processing row {}".format(n))
        if addhash:
            srchash = config.hash_list(row)
            if incremental and record_exists_by_hash(
                    destdb, dest_table, ddrows[pkfield_index].dest_field,
                    row[pkfield_index], srchash):
                logger.debug(
                    "... ... skipping unchanged record: {sd}.{st}.{spkf} = "
                    "(destination) {dt}.{dpkf} = {pkv}".format(
                        sd=sourcedbname,
                        st=sourcetable,
                        spkf=ddrows[pkfield_index].src_field,
                        dt=dest_table,
                        dpkf=ddrows[pkfield_index].dest_field,
                        pkv=row[pkfield_index],
                    )
                )
                continue
        destvalues = []
        for i in xrange(len(ddrows)):
            if ddrows[i].omit:
                continue
            value = row[i]
            if ddrows[i].scrub_in:
                # Main point of anonymisation!
                value = scrubber.scrub(value)
            elif ddrows[i].primary_pid:
                value = config.encrypt_primary_pid(value)
            elif ddrows[i].master_pid:
                value = config.encrypt_master_pid(value)
            elif ddrows[i].truncate_date:
                value = truncate_date_to_first_of_month(value)
            destvalues.append(value)
        if addhash:
            destvalues.append(srchash)
        destdb.insert_record(dest_table, destfields, destvalues)


def create_indexes(tasknum=0, ntasks=1):
    logger.info(SEP + "Create indexes")
    for (table, tablerows) in gen_index_row_sets_by_table(tasknum=tasknum,
                                                          ntasks=ntasks):
        # Process a table as a unit; this makes index creation faster.
        # http://dev.mysql.com/doc/innodb/1.1/en/innodb-create-index-examples.html  # noqa
        sqlbits = []
        for tr in tablerows:
            column = tr.dest_field
            length = tr.indexlen
            if tr.fulltextindex:
                idxname = "_idxft_{}".format(column)
                sqlbit = "ADD FULLTEXT INDEX {name} ({column})".format(
                    name=idxname,
                    column=column,
                )
            else:
                idxname = "_idx_{}".format(column)
                sqlbit = "ADD INDEX {name} ({column}{length})".format(
                    name=idxname,
                    column=column,
                    length="" if length is None else "({})".format(length),
                )
            if config.destdb.index_exists(table, idxname):
                continue  # because it will crash if you add it again!
            sqlbits.append(sqlbit)
        if not sqlbits:
            continue
        sql = "ALTER TABLE {table} {add_indexes}".format(
            table=table,
            add_indexes=", ".join(sqlbits),
        )
        logger.debug(sql)
        config.destdb.db_exec(sql)
        # Index creation doesn't require a commit.


class PatientThread(threading.Thread):
    def __init__(self, sources, destdb, mapdb, nthreads, threadnum,
                 abort_event, subthread_error_event,
                 incremental):
        threading.Thread.__init__(self)
        self.sources = sources
        self.destdb = destdb
        self.mapdb = mapdb
        self.nthreads = nthreads
        self.threadnum = threadnum
        self.abort_event = abort_event
        self.subthread_error_event = subthread_error_event
        self.exception = None
        self.incremental = incremental

    def run(self):
        try:
            patient_processing_fn(
                self.sources, self.destdb, self.mapdb,
                tasknum=self.threadnum, ntasks=self.nthreads,
                abort_event=self.abort_event,
                incremental=self.incremental)
        except Exception as e:
            logger.exception(
                "Setting subthread_error_event from thread {}".format(
                    self.threadnum))
            self.subthread_error_event.set()
            self.exception = e
            raise e  # to kill the thread

    def get_exception(self):
        return self.exception


def patient_processing_fn(sources, destdb, mapdb,
                          tasknum=0, ntasks=1,
                          abort_event=None, multiprocess=False,
                          incremental=False):
    threadprefix = ""
    if ntasks > 1 and not multiprocess:
        threadprefix = "Thread {}: ".format(tasknum)
        logger.info(
            threadprefix +
            "Started thread {} (of {} threads, numbered from 0)".format(
                tasknum, ntasks))
    for pid in gen_patient_ids(sources, tasknum, ntasks):
        # gen_patient_ids() assigns the work to the appropriate thread/process
        # Check for an abort signal once per patient processed
        if abort_event is not None and abort_event.is_set():
            logger.error(threadprefix + "aborted")
            return
        logger.info(threadprefix + "Processing patient ID: {}".format(pid))

        # Gather scrubbing information
        scrubber = Scrubber(sources, pid)

        scrubber_unchanged = patient_scrubber_unchanged(mapdb, pid, scrubber)
        if incremental:
            if scrubber_unchanged:
                logger.debug("Scrubber unchanged; may save some time")
            else:
                logger.debug("Scrubber new or changed; reprocessing in full")

        # For each source database/table...
        for d in dd.get_source_databases():
            db = sources[d]
            for t in dd.get_patient_src_tables_with_active_destination(d):
                logger.debug(
                    threadprefix + "Patient {}, processing table {}.{}".format(
                        pid, d, t))
                process_table(db, d, t, destdb, pid=pid, scrubber=scrubber,
                              incremental=(incremental and scrubber_unchanged))

        # Insert into mapping db
        rid = config.encrypt_primary_pid(pid)
        insert_into_mapping_db(mapdb, pid, rid, scrubber)

    logger.info(SEP + threadprefix + "Commit")
    destdb.commit()


def drop_remake(incremental=False):
    wipe_and_recreate_mapping_db(config.mapdb, incremental=incremental)
    wipe_and_recreate_destination_db(config.destdb, incremental=incremental)
    if incremental:
        for d in dd.get_source_databases():
            db = config.sources[d]
            for t in dd.get_src_tables(d):
                delete_dest_rows_with_no_src_row(db, d, t)


def process_nonpatient_tables(tasknum=0, ntasks=1, incremental=False):
    logger.info(SEP + "Non-patient tables")
    # Processing tables as chunks, so probably best to commit after each.
    for (d, t) in gen_nonpatient_tables(tasknum=tasknum, ntasks=ntasks):
        db = config.sources[d]
        logger.info("Processing non-patient table {}.{}...".format(d, t))
        process_table(db, d, t, config.destdb, pid=None, scrubber=None,
                      incremental=incremental)
        logger.info("... committing")
        config.destdb.commit()
        logger.info("... done")


def process_patient_tables(nthreads=1, process=0, nprocesses=1,
                           incremental=False):
    # We'll use multiple destination tables, so commit right at the end.

    def ctrl_c_handler(signum, frame):
        logger.exception("CTRL-C")
        abort_threads()

    def abort_threads():
        abort_event.set()  # threads will notice and terminate themselves

    logger.info(SEP + "Patient tables")
    if nthreads == 1 and nprocesses == 1:
        logger.info("Single-threaded, single-process mode")
        patient_processing_fn(
            config.sources, config.destdb, config.mapdb,
            tasknum=0, ntasks=1, multiprocess=False,
            incremental=incremental)
    elif nprocesses > 1:
        logger.info("PROCESS {} (numbered from zero) OF {} PROCESSES".format(
            process, nprocesses))
        patient_processing_fn(
            config.sources, config.destdb, config.mapdb,
            tasknum=process, ntasks=nprocesses, multiprocess=True,
            incremental=incremental)
    else:
        logger.info(SEP + "ENTERING SINGLE-PROCESS, MULTITHREADING MODE")
        signal.signal(signal.SIGINT, ctrl_c_handler)
        threads = []
        mainthreadprefix = "Main thread: "
        # Start the threads. Each needs its own set of database connections.
        abort_event = threading.Event()
        abort_event.clear()
        subthread_error_event = threading.Event()
        subthread_error_event.clear()
        for threadnum in range(nthreads):
            destdb = get_database(config.destdb_config)
            mapdb = get_database(config.mapdb_config)
            sources = {}
            for i in xrange(len(config.src_db_names)):
                sources[config.src_db_names[i]] = get_database(
                    config.src_db_configs[i])
            thread = PatientThread(sources, destdb, mapdb,
                                   nthreads, threadnum,
                                   abort_event, subthread_error_event,
                                   incremental)
            thread.start()
            threads.append(thread)
            logger.info(mainthreadprefix +
                        "Started thread {}".format(threadnum))
        # Run; wait for the threads to finish, or crash, or for a user abort
        try:
            running = True
            while running:
                # logger.debug(mainthreadprefix + "ping")
                running = False
                if subthread_error_event.is_set():
                    logger.exception(mainthreadprefix + "A thread has crashed")
                    for t in threads:
                        e = t.get_exception()
                        if e:
                            logger.exception(
                                mainthreadprefix +
                                "Found crashed thread {}".format(
                                    t.threadnum))
                            raise e
                else:
                    for t in threads:
                        if t.is_alive():
                            running = True
                            t.join(1)  # timeout so it does NOT block
                        else:
                            logger.debug(
                                mainthreadprefix +
                                "Found finished thread {}".format(
                                    t.threadnum))
                # time.sleep(1)
        except Exception as e:
            logger.exception(mainthreadprefix +
                             "Exception detected in main thread")
            abort_threads()
            raise e  # will terminate main thread
        logger.info(SEP + "LEAVING MULTITHREADING MODE")
        if abort_event.is_set():
            logger.exception("Threads terminated abnormally")
            raise Exception("Threads terminated abnormally")
    if nprocesses > 1:
        logger.info("Process {}: FINISHED ANONYMISATION".format(process))
    else:
        logger.info("FINISHED ANONYMISATION")

    # Main-thread commit (should be redundant)
    config.destdb.commit()


# =============================================================================
# Main
# =============================================================================

def fail():
    sys.exit(1)


def main():
    version = "Version {} ({})".format(VERSION, VERSION_DATE)
    description = """
Database anonymiser. {version}. By Rudolf Cardinal.

Sample usage:
    export PYTHONPATH=$PYTHONPATH:/srv/www/pythonlib  # to find rnc_db.py

    anonymise.py -c > testconfig.ini  # generate sample config file
    anonymise.py -d testconfig.ini > testdd.tsv  # generate draft data dict.
    anonymise.py testconfig.ini  # run""".format(version=version)
    ncpus = multiprocessing.cpu_count()

    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-n", "--version", action="version", version=version)
    parser.add_argument('--verbose', '-v', action='count',
                        help="Be verbose (use twice for extra verbosity)")
    parser.add_argument('-r', '--report', nargs="?", type=int, default=1000,
                        help="Report insert progress every n rows in verbose "
                             "mode (default 1000)")
    parser.add_argument('-t', '--threads', nargs="?", type=int, default=1,
                        help="For multithreaded mode: number of threads to "
                             "use (default 1; this machine has {} "
                             "CPUs)".format(ncpus))
    parser.add_argument("configfile", nargs="?",
                        help="Configuration file name")
    parser.add_argument("--process", nargs="?", type=int, default=0,
                        help="For multiprocess patient-table mode: specify "
                             "process number")
    parser.add_argument("--nprocesses", nargs="?", type=int, default=1,
                        help="For multiprocess patient-table mode: specify "
                             "total number of processes (launched somehow, of "
                             "which this is to be one)")
    parser.add_argument("--processcluster", default="",
                        help="Process cluster name")
    parser.add_argument("-c", "--democonfig", action="store_true",
                        help="Print a demo config file")
    parser.add_argument("-d", "--draftdd", action="store_true",
                        help="Print a draft data dictionary")
    parser.add_argument("--dropremake", action="store_true",
                        help="Drop/remake destination tables only")
    parser.add_argument("--nonpatienttables", action="store_true",
                        help="Process non-patient tables only")
    parser.add_argument("--patienttables", action="store_true",
                        help="Process patient tables only")
    parser.add_argument("--index", action="store_true",
                        help="Create indexes only")
    parser.add_argument("--incremental", action="store_true",
                        help="Process only new/changed information, where "
                             "possible")
    args = parser.parse_args()

    # Demo config?
    if args.democonfig:
        print(DEMO_CONFIG)
        return

    # Validate args
    if not args.configfile:
        parser.print_help()
        fail()
    if args.nprocesses < 1:
        logger.error("--nprocesses must be >=1")
        fail()
    if args.process < 0 or args.process >= args.nprocesses:
        logger.error(
            "--process argument must be from 0 to (nprocesses - 1) inclusive")
        fail()
    if args.nprocesses > 1 and args.threads > 1:
        logger.error("Can't use multithreading and multi-process mode. "
                     "In multi-process mode, specify --threads=1")
        fail()
    # Inefficient code but helpful error messages:
    if args.threads > 1 and args.dropremake:
        logger.error("Can't use nthreads > 1 with --dropremake")
        fail()
    if args.threads > 1 and args.nonpatienttables:
        logger.error("Can't use nthreads > 1 with --nonpatienttables")
        fail()
    if args.threads > 1 and args.index:
        logger.error("Can't use nthreads > 1 with --index")
        fail()
    if args.nprocesses > 1 and args.dropremake:
        logger.error("Can't use nprocesses > 1 with --dropremake")
        fail()

    everything = not any([args.dropremake, args.nonpatienttables,
                          args.patienttables, args.index])

    # -------------------------------------------------------------------------

    # Verbosity
    mynames = []
    if args.processcluster:
        mynames.append(args.processcluster)
    if args.nprocesses > 1:
        mynames.append("process {}".format(args.process))
    reset_logformat(
        logger,
        name=" ".join(mynames),
        debug=(args.verbose >= 1)
    )
    rnc_db.set_loglevel(logging.DEBUG if args.verbose >= 2 else logging.INFO)

    # Load/validate config
    logger.info(SEP + "Loading config")
    global config
    config = Config(args.configfile)
    config.report_every_n_rows = args.report

    if args.draftdd:
        print_draft_data_dictionary()
        return

    logger.info(SEP + "Loading data dictionary")
    global dd
    dd = DataDictionary()
    dd.read_from_file(config.data_dictionary_filename)

    # -------------------------------------------------------------------------

    logger.info(SEP + "Starting")
    start = get_now_utc()

    # 1. Drop/remake tables. Single-tasking only.
    if args.dropremake or everything:
        drop_remake(incremental=args.incremental)

    # 2. Tables without any patient ID (e.g. lookup tables). Process PER TABLE.
    if args.nonpatienttables or everything:
        process_nonpatient_tables(tasknum=args.process,
                                  ntasks=args.nprocesses,
                                  incremental=args.incremental)

    # 3. Tables with patient info. (This bit supports multithreading.)
    #    Process PER PATIENT, across all tables, because we have to synthesize
    #    information to scrub across the entirety of that patient's record.
    if args.patienttables or everything:
        process_patient_tables(nthreads=args.threads,
                               process=args.process,
                               nprocesses=args.nprocesses,
                               incremental=args.incremental)

    # 4. Indexes. ALWAYS FASTEST TO DO THIS LAST. Process PER TABLE.
    if args.index or everything:
        create_indexes(tasknum=args.process, ntasks=args.nprocesses)

    logger.info(SEP + "Finished")
    end = get_now_utc()
    time_taken = end - start
    logger.info("Time taken: {} seconds".format(time_taken.total_seconds()))


# =============================================================================
# Command-line entry point
# =============================================================================

if __name__ == '__main__':
    main()
