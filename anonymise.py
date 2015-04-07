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

- Incremental updates following small data dictionary changes, e.g. field
  addition. Currently, these require a full re-run.

CHANGE LOG:

- v0.03, 2015-03-19
  - Bug fix for incremental update (previous version inserted rather than
    updating when the source content had changed); search for
    update_on_duplicate_key.
  - Checks for missing/extra fields in destination.
  - "No separator" allowed for get_date_regex_elements(), allowing
    anonymisation of e.g. 19Mar2015, 19800101.
  - New default at_word_boundaries_only=False for get_date_regex_elements(),
    allowing anonymisation of ISO8601-format dates (e.g. 1980-10-01T0000), etc.
  - Similar option for get_numeric_regex_elements().
  - Similar option for get_string_regex_elements().
  - Options in config to control these.
  - Fuzzy matching for get_string_regex_elements(); string_max_regex_errors
    option in config. The downside is the potential for greedy matching; for
    example, if you anonymise "Ronald MacDonald" with "Ronald" and "MacDonald",
    you can end up with "XXX MacXXX", as the regex greedy-matches "Donald" to
    "Ronald" with a typo, and therefore fails to process the whole "MacDonald".
    On the other hand, this protects against simple typos, which are probably
    more common.
  - Audit database/table.
  - Create an incremental update to the data dictionary (i.e. existing DD plus
    any new fields in the source, with safe draft entries).
  - Data dictionary optimizations.

"""

# =============================================================================
# Imports
# =============================================================================

from __future__ import division
from __future__ import print_function

import logging
LOG_FORMAT = '%(asctime)s.%(msecs)03d:%(levelname)s:%(name)s:%(message)s'
LOG_DATEFMT = '%Y-%m-%d %H:%M:%S'
logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATEFMT)
logger = logging.getLogger("anonymise")

import argparse
import itertools
import multiprocessing
import operator
import regex  # sudo apt-get install python-regex
import signal
import sys
import threading

from rnc_datetime import (
    coerce_to_date,
    get_now_utc,
    truncate_date_to_first_of_month
)
import rnc_db
from rnc_db import (
    is_sqltype_date,
    is_sqltype_text_over_one_char,
)
from rnc_extract_text import document_to_text
import rnc_log
import shared_anon
from shared_anon import (
    ALTERMETHOD,
    AUDIT_FIELDSPECS,
    AUDIT_TABLE,
    config,
    DEMO_CONFIG,
    escape_literal_string_for_regex,
    INDEX,
    SCRUBSRC,
    SCRUBMETHOD,
    SEP,
    SRCFLAG,
    SQLTYPE_ENCRYPTED_PID
)

# =============================================================================
# Global constants
# =============================================================================

VERSION = 0.03
VERSION_DATE = "2015-03-19"

MAPPING_TABLE = "secret_map"


# =============================================================================
# Anonymisation regexes
# =============================================================================
# Note, for strings, several typo-detecting methods:
#   http://en.wikipedia.org/wiki/Levenshtein_distance
#   http://mwh.geek.nz/2009/04/26/python-damerau-levenshtein-distance/
#   http://en.wikipedia.org/wiki/TRE_(computing)
#   https://pypi.python.org/pypi/regex
# ... let's go with the fuzzy regex method (Python regex module).

def get_date_regex_elements(dt, at_word_boundaries_only=False):
    """Takes a datetime object and returns a list of regex strings with which
    to scrub."""
    # Reminders: ? zero or one, + one or more, * zero or more
    # Non-capturing groups: (?:...)
    # ... https://docs.python.org/2/howto/regex.html
    # ... http://stackoverflow.com/questions/3512471/non-capturing-group
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
    # Separator: one or more of: whitespace, /, -, comma, nothing
    ws = r"\s"  # whitespace; includes newlines
    SEP = "[" + ws + "/,-]*"
    # ... note that the hyphen has to be at the start or end, otherwise it
    #     denotes a range.
    # Regexes
    basic_regexes = [
        day + SEP + month + SEP + year,  # e.g. 13 Sep 2014
        month + SEP + day + SEP + year,  # e.g. Sep 13, 2014
        year + SEP + month + SEP + day,  # e.g. 2014/09/13
    ]
    if at_word_boundaries_only:
        wb = r"\b"  # word boundary; escape the slash if not using a raw string
        return [wb + x + wb for x in basic_regexes]
    else:
        return basic_regexes


def get_numeric_regex_elements(s, liberal=True, at_word_boundaries_only=False):
    """Takes a STRING representation of a number, which may include leading
    zeros (as for phone numbers), and produces a list of regex strings for
    scrubbing.

    We allow all sorts of separators. For example, 0123456789 might appear as
        (01234) 56789
        0123 456 789
        01234-56789
        0123.456.789
    """
    s = escape_literal_string_for_regex(s)  # escape any decimal points, etc.
    if liberal:
        separators = "[\W]*"  # zero or more non-alphanumeric characters...
        s = separators.join([c for c in s])  # ... can appear anywhere
    if at_word_boundaries_only:
        wb = ur"\b"  # word boundary
        return [wb + s + wb]
    else:
        return [s]


def get_digit_string_from_vaguely_numeric_string(s):
    """For example, converts "(01223) 123456" to "01223123456"."""
    return "".join([d for d in s if d.isdigit()])


def remove_whitespace(s):
    return ''.join(s.split())


NON_WHITESPACE_SPLITTERS = regex.compile("['’-]+", regex.UNICODE)


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
    smallfragments = []
    combinedsmallfragments = []
    for chunk in s.split():  # split on whitespace
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


def get_string_regex_elements(s, suffixes=None, at_word_boundaries_only=False,
                              max_errors=2):
    """Takes a string (+/- suffixes, typically ["s"], and returns a list of
    regex strings with which to scrub."""
    s = escape_literal_string_for_regex(s)
    if max_errors > 0:
        s = "(" + s + "){e<" + str(max_errors + 1) + "}"
    if suffixes:
        suffixstr = (
            "(?:"
            + "|".join([escape_literal_string_for_regex(x)
                        for x in suffixes])
            + "|)"  # allows for no suffix at all
        )
    else:
        suffixstr = ""
    if at_word_boundaries_only:
        wb = ur"\b"  # word boundary
        return [wb + s + suffixstr + wb]
    else:
        return [s + suffixstr]


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
        return regex.compile(s, regex.IGNORECASE | regex.UNICODE)
    except:
        logger.exception(u"Failed regex: {}".format(s))
        raise


# Testing:
if False:
    TEST_REGEXES = '''
from __future__ import print_function
import dateutil.parser
import regex

import logging
logging.basicConfig()  # just in case nobody else has done this
logger = logging.getLogger("anonymise")

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

   And ISO-8601 formats like 20130107T0123, or just 20130107.

   BUT NOT 8 Jan 2013, or 2013/02/07, or 2013
   Jan 17, or just a number like 7, or a month
   like January, or a nonspecific date like
   Jan 2013 or 7 January.

   But not ISO-8601 formats like 20130108T0123, or just 20130108.

   I am 34 years old. My mother was 348, or 834, or perhaps 8348.
   Was she 34.6? Don't think so.

   Her IDs include NHS#123456, or 123 456, or (123) 456, or 123456.

   I am 34 years old. My mother was 348, or 834, or perhaps 8348.
   She wasn't my step-mother, or my grandmother, or my mother-in-law.
   She was my MOTHER!
   A typo is mther.

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
# Scrubber
# =============================================================================

class Scrubber(object):
    def __init__(self, sources, pid):
        self.pid = pid
        self.mpid = None
        self.re_patient = None  # re: regular expression
        self.re_tp = None
        self.re_patient_elements = set()
        self.re_tp_elements = set()
        logger.debug("building scrubber")
        for ddr in config.dd.get_scrub_from_rows():
            scrub_method = self.get_scrub_method(ddr.src_datatype,
                                                 ddr.scrub_method)
            is_patient = ddr.scrub_src == SCRUBSRC.PATIENT
            for v in gen_all_values_for_patient(sources,
                                                ddr.src_db,
                                                ddr.src_table,
                                                ddr.src_field, pid):
                self.add_value(v, scrub_method, is_patient)
                if self.mpid is None and SRCFLAG.MASTERPID in ddr.src_flags:
                    # We've come across the master ID.
                    self.mpid = v
        self.finished_adding()

    @staticmethod
    def get_scrub_method(datatype_long, scrub_method):
        if scrub_method:
            return scrub_method
        elif is_sqltype_date(datatype_long):
            return SCRUBMETHOD.DATE
        elif is_sqltype_text_over_one_char(datatype_long):
            return SCRUBMETHOD.TEXT
        else:
            return SCRUBMETHOD.NUMERIC

    def add_value(self, value, scrub_method, patient=True):
        if value is None:
            return

        # Note: object reference
        r = self.re_patient_elements if patient else self.re_tp_elements

        if scrub_method == SCRUBMETHOD.DATE:
            # Source is a date.
            try:
                value = coerce_to_date(value)
            except Exception as e:
                logger.warning(
                    "Invalid date received to Scrubber.add_value(): value={}, "
                    "exception={}".format(
                        value, e))
                return
            wbo = config.anonymise_dates_at_word_boundaries_only
            elements = get_date_regex_elements(
                value, at_word_boundaries_only=wbo)
        elif scrub_method == SCRUBMETHOD.TEXT:
            # Source is text.
            value = unicode(value)
            strings = get_anon_fragments_from_string(value)
            wbo = config.anonymise_strings_at_word_boundaries_only
            elements = []
            for s in strings:
                elements.extend(get_string_regex_elements(
                    s,
                    config.scrub_string_suffixes,
                    max_errors=config.string_max_regex_errors,
                    at_word_boundaries_only=wbo))
        elif scrub_method == SCRUBMETHOD.NUMERIC:
            # Source is a text field containing a number, or an actual number.
            # Remove everything but the digits
            # Particular examples: phone numbers, e.g. "(01223) 123456".
            wbo = config.anonymise_numbers_at_word_boundaries_only
            elements = get_numeric_regex_elements(
                get_digit_string_from_vaguely_numeric_string(str(value)),
                at_word_boundaries_only=wbo)
        else:
            raise ValueError("Bug: unknown scrub_method to add_value")
        for element in elements:
            r.add(element)

    def finished_adding(self):
        # Create regexes:
        self.re_patient = get_regex_from_elements(
            list(self.re_patient_elements))
        self.re_tp = get_regex_from_elements(
            list(self.re_tp_elements))
        # Announce pointlessly
        # logger.debug("Scrubber: {}".format(self.get_hash_string()))

    def get_hash_string(self):
        return repr(self.re_patient_elements | self.re_tp_elements)
        # | for union

    def scrub(self, text):
        # logger.debug("scrubbing")
        if text is None:
            return None
        if self.re_patient:
            text = self.re_patient.sub(config.replace_patient_info_with, text)
        if self.re_tp:
            text = self.re_tp.sub(config.replace_third_party_info_with, text)
        return text

    def get_pid(self):
        return self.pid

    def get_mpid(self):
        return self.mpid


# =============================================================================
# Database queries
# =============================================================================

def patient_scrubber_unchanged(admindb, patient_id, scrubber):
    new_scrub_hash = config.hash_scrubber(scrubber)
    sql = """
        SELECT 1
        FROM {table}
        WHERE {patient_id} = ?
        AND {scrubber_hash} = ?
    """.format(
        table=MAPPING_TABLE,
        patient_id=config.mapping_patient_id_fieldname,
        scrubber_hash=config.source_hash_fieldname,
    )
    row = admindb.fetchone(sql, patient_id, new_scrub_hash)
    return True if row is not None and row[0] == 1 else False


def patient_in_map(admindb, patient_id):
    sql = """
        SELECT 1
        FROM {table}
        WHERE {patient_id} = ?
    """.format(
        table=MAPPING_TABLE,
        patient_id=config.mapping_patient_id_fieldname,
    )
    row = admindb.fetchone(sql, patient_id)
    return True if row is not None and row[0] == 1 else False


def identical_record_exists_by_hash(destdb, dest_table, pkfield, pkvalue,
                                    hashvalue):
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
    return (row is not None and row[0] == 1)


def identical_record_exists_by_pk(destdb, dest_table, pkfield, pkvalue):
    sql = """
        SELECT 1
        FROM {table}
        WHERE {pkfield}=?
    """.format(
        table=dest_table,
        pkfield=pkfield,
    )
    args = [pkvalue]
    row = destdb.fetchone(sql, *args)
    return (row is not None and row[0] == 1)


# =============================================================================
# Database actions
# =============================================================================

def recreate_audit_table(db):
    logger.debug("recreate_audit_table")
    db.create_or_update_table(
        AUDIT_TABLE,
        AUDIT_FIELDSPECS,
        drop_superfluous_columns=True,
        dynamic=True,
        compressed=False)
    if not db.mysql_table_using_barracuda(AUDIT_TABLE):
        db.mysql_convert_table_to_barracuda(AUDIT_TABLE, compressed=False)


def insert_into_mapping_db(admindb, scrubber):
    pid = scrubber.get_pid()
    rid = config.encrypt_primary_pid(pid)
    mpid = scrubber.get_mpid()
    mrid = config.encrypt_master_pid(mpid)
    scrubber_hash = config.hash_scrubber(scrubber)
    if patient_in_map(admindb, pid):
        sql = """
            UPDATE {table}
            SET {master_id} = ?, {master_research_id} = ?, {scrubber_hash} = ?
            WHERE {patient_id} = ?
        """.format(
            table=MAPPING_TABLE,
            master_id=config.mapping_master_id_fieldname,
            master_research_id=config.master_research_id_fieldname,
            scrubber_hash=config.source_hash_fieldname,
            patient_id=config.mapping_patient_id_fieldname,
        )
        args = [mpid, mrid, scrubber_hash, pid]
    else:
        sql = """
            INSERT INTO {table} (
                {patient_id}, {research_id},
                {master_id}, {master_research_id},
                {scrubber_hash}
            )
            VALUES (
                ?, ?,
                ?, ?,
                ?
            )
        """.format(
            table=MAPPING_TABLE,
            patient_id=config.mapping_patient_id_fieldname,
            research_id=config.research_id_fieldname,
            master_id=config.mapping_master_id_fieldname,
            master_research_id=config.master_research_id_fieldname,
            scrubber_hash=config.source_hash_fieldname,
        )
        args = [pid, rid, mpid, mrid, scrubber_hash]
    admindb.db_exec(sql, *args)
    admindb.commit()
    # Commit immediately, because other processes may need this table promptly.
    # Otherwise, get:
    #   Deadlock found when trying to get lock; try restarting transaction


def wipe_and_recreate_mapping_table(admindb, incremental=False):
    logger.debug("wipe_and_recreate_mapping_table")
    if not incremental:
        admindb.drop_table(MAPPING_TABLE)
    sql = """
        CREATE TABLE IF NOT EXISTS {table} (
            {patient_id} BIGINT UNSIGNED PRIMARY KEY,
            {research_id} {hash_type} NOT NULL,
            {master_id} BIGINT UNSIGNED,
            {master_research_id} {hash_type},
            {scrubber_hash} {hash_type}
        )
    """.format(
        table=MAPPING_TABLE,
        hash_type=SQLTYPE_ENCRYPTED_PID,
        patient_id=config.mapping_patient_id_fieldname,
        research_id=config.research_id_fieldname,
        master_id=config.mapping_master_id_fieldname,
        master_research_id=config.master_research_id_fieldname,
        scrubber_hash=config.source_hash_fieldname,
    )
    admindb.db_exec(sql)
    admindb.commit()


def wipe_and_recreate_destination_db(destdb, dynamic=True, compressed=False,
                                     incremental=False):
    logger.debug("wipe_and_recreate_destination_db, incremental={}".format(
        incremental))
    if destdb.db_flavour != rnc_db.DatabaseSupporter.FLAVOUR_MYSQL:
        dynamic = False
        compressed = False

    for t in config.dd.get_dest_tables():
        # Drop
        if not incremental:
            logger.debug("dropping table {}".format(t))
            destdb.drop_table(t)

        # Recreate
        ddr = config.dd.get_rows_for_dest_table(t)
        ddr = sorted(ddr, key=operator.attrgetter("dest_field"))
        fieldspecs = []
        dest_fieldnames = []
        for r in ddr:
            if r.omit:
                continue
            fs = r.dest_field + " " + r.dest_datatype
            dest_fieldnames.append(r.dest_field)
            if r.comment or config.append_source_info_to_comment:
                comment = r.comment or ""
                if config.append_source_info_to_comment:
                    comment += " [from {t}.{f}]".format(
                        t=r.src_table,
                        f=r.src_field,
                    )
                fs += " COMMENT " + rnc_db.sql_quote_string(comment)
            fieldspecs.append(fs)
            if SRCFLAG.ADDSRCHASH in r.src_flags:
                # append a special field
                fieldspecs.append(
                    config.source_hash_fieldname + " " +
                    SQLTYPE_ENCRYPTED_PID +
                    " COMMENT 'Hashed amalgamation of all source fields'")
                dest_fieldnames.append(config.source_hash_fieldname)
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
        resulting_fieldnames = destdb.fetch_column_names(t)
        target_set = set(dest_fieldnames)
        outcome_set = set(resulting_fieldnames)
        missing = list(target_set - outcome_set)
        extra = list(outcome_set - target_set)
        if missing:
            raise Exception(
                "Missing fields in destination table {t}: {l}".format(
                    t=t,
                    l=missing,
                )
            )
        if extra:
            logger.warning(
                "Extra fields in destination table {t}: {l}".format(
                    t=t,
                    l=extra,
                )
            )


def delete_dest_rows_with_no_src_row(srcdb, srcdbname, src_table):
    # - Can't do this in a single SQL command, since the engine can't
    #   necessarily see both databases.
    # - Can't do this in a multiprocess way, because we're trying to do a
    #   DELETE WHERE NOT IN.
    if not config.dd.has_active_destination(srcdbname, src_table):
        return
    dest_table = config.dd.get_dest_table_for_src_db_table(srcdbname,
                                                           src_table)
    pkddr = config.dd.get_pk_ddr(srcdbname, src_table)
    logger.debug("delete_dest_rows_with_no_src_row: source table {}, "
                 "destination table {}".format(src_table, dest_table))
    pks = []
    if pkddr:
        sql = "SELECT {src_pk} FROM {src_table}".format(
            src_pk=pkddr.src_field,
            src_table=src_table,
        )
        pks = srcdb.fetchallfirstvalues(sql)
    if not pks:
        logger.debug("... deleting all")
        sql = "DELETE FROM {dest_table}".format(dest_table=dest_table)
        config.destdb.db_exec(sql)
    else:
        logger.debug("... deleting selectively")

        # The PKs may be translated:
        if SRCFLAG.PRIMARYPID in pkddr.src_flags:
            pks = [config.encrypt_primary_pid(x) for x in pks]
        elif SRCFLAG.MASTERPID in pkddr.src_flags:
            pks = [config.encrypt_master_pid(x) for x in pks]

        value_string = ','.join(['?'] * len(pks))
        sql = """
            DELETE FROM {dest_table}
            WHERE {dest_pk} NOT IN ({value_string})
        """.format(
            dest_table=pkddr.dest_table,
            dest_pk=pkddr.dest_field,
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
    # If we're going to define based on >1 table, we need to keep track of
    # what we've processed. However, if we only have one table, we don't.
    # We can't use the mapping table easily (*), because it leads to thread/
    # process locking for database access. So we use a set.
    # (*) if not patient_id_exists_in_mapping_db(admindb, patient_id): ...
    keeping_track = config.dd.n_definers > 1
    if keeping_track:
        processed_ids = set()
    for ddr in config.dd.rows:
        if SRCFLAG.DEFINESPRIMARYPIDS not in ddr.src_flags:
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
            if keeping_track:
                if patient_id in processed_ids:
                    row = cursor.fetchone()
                    continue
                processed_ids.add(patient_id)
            logger.debug("Found patient id: {}".format(patient_id))
            yield patient_id
            row = cursor.fetchone()


def gen_all_values_for_patient(sources, dbname, table, field, pid):
    cfg = config.srccfg[dbname]
    if not cfg.per_table_pid_field:
        return
        # http://stackoverflow.com/questions/13243766
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
        patient_id_field=cfg.per_table_pid_field
    )
    args = [pid]
    cursor = db.cursor()
    db.db_exec_with_cursor(cursor, sql, *args)
    row = cursor.fetchone()
    while row is not None:
        yield row[0]
        row = cursor.fetchone()


def gen_rows(sourcedb, sourcedbname, sourcetable, sourcefields, pid=None,
             pkname=None, tasknum=None, ntasks=None, debuglimit=0):
    """ Generates a series of lists of values, each value corresponding to a
    field in sourcefields.
    """
    args = []
    whereconds = []

    # Restrict to one patient?
    if pid is not None:
        whereconds.append("{}=?".format(
            config.srccfg[sourcedbname].per_table_pid_field))
        args.append(pid)

    # Divide up rows across tasks?
    if pkname is not None and tasknum is not None and ntasks is not None:
        whereconds.append("{pk} % {ntasks} = {tasknum}".format(
            pk=pkname,
            ntasks=ntasks,
            tasknum=tasknum,
        ))

    where = ""
    if whereconds:
        where = " WHERE " + " AND ".join(whereconds)
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
    nrows = 1
    while row is not None:
        if debuglimit > 0 and nrows > debuglimit:
            logger.warning(
                "Table {}: stopping at {} rows due to debugging limits".format(
                    sourcetable, debuglimit))
            return
        yield list(row)  # convert from tuple to list so we can modify it
        row = cursor.fetchone()
        nrows += 1


def gen_index_row_sets_by_table(tasknum=0, ntasks=1):
    indexrows = [ddr for ddr in config.dd.rows
                 if ddr.index and not ddr.omit]
    tables = list(set([r.dest_table for r in indexrows]))
    for i, t in enumerate(tables):
        if i % ntasks != tasknum:
            continue
        tablerows = [r for r in indexrows if r.dest_table == t]
        yield (t, tablerows)


def gen_nonpatient_tables_without_int_pk(tasknum=0, ntasks=1):
    db_table_pairs = config.dd.get_src_dbs_tables_with_no_pt_info_no_pk()
    for i, pair in enumerate(db_table_pairs):
        if i % ntasks != tasknum:
            continue
        yield pair  # will be a (dbname, table) tuple


def gen_nonpatient_tables_with_int_pk():
    db_table_pairs = config.dd.get_src_dbs_tables_with_no_pt_info_int_pk()
    for pair in db_table_pairs:
        db = pair[0]
        table = pair[1]
        pkname = config.dd.get_int_pk_name(db, table)
        yield (db, table, pkname)


# =============================================================================
# Core functions
# =============================================================================
# - For multithreaded use, the patients are divvied up across the threads.
# - KEY THREADING RULE: ALL THREADS MUST HAVE FULLY INDEPENDENT DATABASE
#   CONNECTIONS.

def process_table(sourcedb, sourcedbname, sourcetable, destdb,
                  pid=None, scrubber=None, incremental=False,
                  pkname=None, tasknum=None, ntasks=None):
    logger.debug(
        "process_table: {}.{}, pid={}, incremental={}".format(
            sourcedbname, sourcetable, pid, incremental))

    # Limit the data quantity for debugging?
    srccfg = config.srccfg[sourcedbname]
    if sourcetable in srccfg.debug_limited_tables:
        debuglimit = srccfg.debug_row_limit
    else:
        debuglimit = 0

    ddrows = config.dd.get_rows_for_src_table(sourcedbname, sourcetable)
    addhash = any([SRCFLAG.ADDSRCHASH in ddr.src_flags for ddr in ddrows])
    constant = any([SRCFLAG.CONSTANT in ddr.src_flags for ddr in ddrows])
    # If addhash or constant is true, there will also be at least one non-
    # omitted row, namely the source PK (by the data dictionary's validation
    # process).
    ddrows = [ddr
              for ddr in ddrows
              if (not ddr.omit) or (addhash and ddr.scrub_src)]
    if not ddrows:
        return
    dest_table = ddrows[0].dest_table
    sourcefields = []
    destfields = []
    pkfield_index = None
    for i, ddr in enumerate(ddrows):
        logger.debug("DD row: {}".format(str(ddr)))
        if SRCFLAG.PK in ddr.src_flags:
            pkfield_index = i
        sourcefields.append(ddr.src_field)
        if not ddr.omit:
            destfields.append(ddr.dest_field)
    if addhash:
        destfields.append(config.source_hash_fieldname)
    n = 0
    for row in gen_rows(sourcedb, sourcedbname, sourcetable, sourcefields,
                        pid, debuglimit=debuglimit,
                        pkname=pkname, tasknum=tasknum, ntasks=ntasks):
        n += 1
        if n % config.report_every_n_rows == 0:
            logger.info("... processing row {} of task set".format(n))
        if addhash:
            srchash = config.hash_list(row)
            if incremental and identical_record_exists_by_hash(
                    destdb, dest_table, ddrows[pkfield_index].dest_field,
                    row[pkfield_index], srchash):
                logger.debug(
                    "... ... skipping unchanged record (identical by hash): "
                    "{sd}.{st}.{spkf} = "
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
        if constant:
            if incremental and identical_record_exists_by_pk(
                    destdb, dest_table, ddrows[pkfield_index].dest_field,
                    row[pkfield_index]):
                logger.debug(
                    "... ... skipping unchanged record (identical by PK and "
                    "marked as constant): {sd}.{st}.{spkf} = "
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
        for i, ddr in enumerate(ddrows):
            if ddr.omit:
                continue
            value = row[i]
            if SRCFLAG.PRIMARYPID in ddr.src_flags:
                value = config.encrypt_primary_pid(value)
            elif SRCFLAG.MASTERPID in ddr.src_flags:
                value = config.encrypt_master_pid(value)
            elif ddr._truncate_date:
                try:
                    value = coerce_to_date(value)
                    value = truncate_date_to_first_of_month(value)
                except:
                    logger.warning(
                        "Invalid date received to {ALTERMETHOD.TRUNCATEDATE} "
                        "method: {v}".format(ALTERMETHOD=ALTERMETHOD, v=value))
                    value = None
            elif ddr._extract_text:
                filename = None
                blob = None
                extension = None
                if ddr._extract_from_filename:
                    filename = value
                else:
                    blob = value
                    extindex = next(
                        (i for i, x in enumerate(ddrows)
                            if x.src_field == ddr._extract_ext_field),
                        None)
                    if extindex is None:
                        raise ValueError(
                            "Bug: missing extension field for "
                            "alter_method={}".format(ddr.alter_method))
                    extension = row[extindex]
                try:
                    value = document_to_text(filename=filename,
                                             blob=blob,
                                             extension=extension)
                except Exception as e:
                    logger.error(
                        "Exception from document_to_text: {}".format(e))
                    value = None

            if ddr._scrub:
                # Main point of anonymisation!
                value = scrubber.scrub(value)

            destvalues.append(value)
        if addhash:
            destvalues.append(srchash)
        destdb.insert_record(dest_table, destfields, destvalues,
                             update_on_duplicate_key=True)

        # Trigger an early commit?
        early_commit = False
        if config.max_rows_before_commit is not None:
            config._rows_in_transaction += 1
            if config._rows_in_transaction >= config.max_rows_before_commit:
                early_commit = True
        if config.max_bytes_before_commit is not None:
            config._bytes_in_transaction += sys.getsizeof(destvalues)
            # ... approximate!
            # Quicker than e.g. len(repr(...)), as judged by a timeit() call.
            if config._bytes_in_transaction >= config.max_bytes_before_commit:
                early_commit = True
        if early_commit:
            logger.info("Triggering early commit...")
            destdb.commit()
            logger.info("... done")
            config._rows_in_transaction = 0
            config._bytes_in_transaction = 0


def create_indexes(tasknum=0, ntasks=1):
    logger.info(SEP + "Create indexes")
    for (table, tablerows) in gen_index_row_sets_by_table(tasknum=tasknum,
                                                          ntasks=ntasks):
        # Process a table as a unit; this makes index creation faster.
        # http://dev.mysql.com/doc/innodb/1.1/en/innodb-create-index-examples.html  # noqa
        sqlbits_normal = []
        sqlbits_fulltext = []
        for tr in tablerows:
            column = tr.dest_field
            length = tr.indexlen
            is_unique = tr.index == INDEX.UNIQUE
            is_fulltext = tr.index == INDEX.FULLTEXT
            if is_fulltext:
                idxname = "_idxft_{}".format(column)
                sqlbit = "ADD FULLTEXT INDEX {name} ({column})".format(
                    name=idxname,
                    column=column,
                )
            else:
                idxname = "_idx_{}".format(column)
                sqlbit = "ADD {unique} INDEX {name} ({column}{length})".format(
                    name=idxname,
                    column=column,
                    length="" if length is None else "({})".format(length),
                    unique="UNIQUE" if is_unique else "",
                )
            if config.destdb.index_exists(table, idxname):
                continue  # because it will crash if you add it again!
            if is_fulltext:
                sqlbits_fulltext.append(sqlbit)
            else:
                sqlbits_normal.append(sqlbit)

        if sqlbits_normal:
            sql = "ALTER TABLE {table} {add_indexes}".format(
                table=table,
                add_indexes=", ".join(sqlbits_normal),
            )
            logger.info(sql)
            config.destdb.db_exec(sql)
        for sqlbit in sqlbits_fulltext:  # must add one by one
            sql = "ALTER TABLE {table} {add_indexes}".format(
                table=table,
                add_indexes=sqlbit,
            )
            logger.info(sql)
            config.destdb.db_exec(sql)
        # Index creation doesn't require a commit.


class PatientThread(threading.Thread):
    def __init__(self, sources, destdb, admindb, nthreads, threadnum,
                 abort_event, subthread_error_event,
                 incremental):
        threading.Thread.__init__(self)
        self.sources = sources
        self.destdb = destdb
        self.admindb = admindb
        self.nthreads = nthreads
        self.threadnum = threadnum
        self.abort_event = abort_event
        self.subthread_error_event = subthread_error_event
        self.exception = None
        self.incremental = incremental

    def run(self):
        try:
            patient_processing_fn(
                self.sources, self.destdb, self.admindb,
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


def patient_processing_fn(sources, destdb, admindb,
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

        scrubber_unchanged = patient_scrubber_unchanged(admindb, pid, scrubber)
        if incremental:
            if scrubber_unchanged:
                logger.debug("Scrubber unchanged; may save some time")
            else:
                logger.debug("Scrubber new or changed; reprocessing in full")

        # For each source database/table...
        for d in config.dd.get_source_databases():
            logger.debug("Processing database: {}".format(d))
            db = sources[d]
            for t in config.dd.get_patient_src_tables_with_active_dest(d):
                logger.debug(
                    threadprefix + "Patient {}, processing table {}.{}".format(
                        pid, d, t))
                process_table(db, d, t, destdb, pid=pid, scrubber=scrubber,
                              incremental=(incremental and scrubber_unchanged))

        # Insert into mapping db
        insert_into_mapping_db(admindb, scrubber)

    logger.info(SEP + threadprefix + "Commit")
    destdb.commit()


def drop_remake(incremental=False):
    recreate_audit_table(config.admindb)
    wipe_and_recreate_mapping_table(config.admindb, incremental=incremental)
    wipe_and_recreate_destination_db(config.destdb, incremental=incremental)
    if incremental:
        for d in config.dd.get_source_databases():
            db = config.sources[d]
            for t in config.dd.get_src_tables(d):
                delete_dest_rows_with_no_src_row(db, d, t)


def process_nonpatient_tables(tasknum=0, ntasks=1, incremental=False):
    logger.info(SEP + "Non-patient tables: (a) with integer PK")
    for (d, t, pkname) in gen_nonpatient_tables_with_int_pk():
        db = config.sources[d]
        logger.info("Processing non-patient table {}.{} (PK: {})...".format(
            d, t, pkname))
        process_table(db, d, t, config.destdb, pid=None, scrubber=None,
                      incremental=incremental,
                      pkname=pkname, tasknum=tasknum, ntasks=ntasks)
        logger.info("... committing")
        config.destdb.commit()
        logger.info("... done")
    logger.info(SEP + "Non-patient tables: (b) without integer PK")
    for (d, t) in gen_nonpatient_tables_without_int_pk(tasknum=tasknum,
                                                       ntasks=ntasks):
        db = config.sources[d]
        logger.info("Processing non-patient table {}.{}...".format(d, t))
        process_table(db, d, t, config.destdb, pid=None, scrubber=None,
                      incremental=incremental,
                      pkname=None, tasknum=None, ntasks=None)
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
            config.sources, config.destdb, config.admindb,
            tasknum=0, ntasks=1, multiprocess=False,
            incremental=incremental)
    elif nprocesses > 1:
        logger.info("PROCESS {} (numbered from zero) OF {} PROCESSES".format(
            process, nprocesses))
        patient_processing_fn(
            config.sources, config.destdb, config.admindb,
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
            destdb = config.get_database("destination_database")
            admindb = config.get_database("admin_database")
            sources = {}
            for srcname in config.src_db_names:
                sources[srcname] = config.get_database(srcname)
            thread = PatientThread(sources, destdb, admindb,
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

Sample usage (having set PYTHONPATH):
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
    parser.add_argument("--democonfig", action="store_true",
                        help="Print a demo config file (INCLUDES MORE HELP)")
    parser.add_argument("--draftdd", action="store_true",
                        help="Print a draft data dictionary")
    parser.add_argument("--incrementaldd", action="store_true",
                        help="Print an INCREMENTAL draft data dictionary")
    parser.add_argument("--makeddpermitbydefaultdangerous",
                        action="store_true",
                        help="When creating or adding to a data dictionary, "
                             "set the 'omit' flag to False. DANGEROUS.")
    parser.add_argument("--dropremake", action="store_true",
                        help="Drop/remake destination tables only")
    parser.add_argument("--nonpatienttables", action="store_true",
                        help="Process non-patient tables only")
    parser.add_argument("--patienttables", action="store_true",
                        help="Process patient tables only")
    parser.add_argument("--index", action="store_true",
                        help="Create indexes only")
    parser.add_argument("-i", "--incremental", action="store_true",
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
    if args.incrementaldd and args.draftdd:
        logger.error("Can't use --incrementaldd and --draftdd")
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
    rnc_log.reset_logformat_timestamped(
        logger,
        extraname=" ".join(mynames),
        debug=(args.verbose >= 1)
    )
    rnc_log.reset_logformat_timestamped(
        shared_anon.logger,
        extraname=" ".join(mynames),
        debug=(args.verbose >= 1)
    )
    rnc_db.set_loglevel(logging.DEBUG if args.verbose >= 2 else logging.INFO)

    # Load/validate config
    config.set(filename=args.configfile, load_dd=(not args.draftdd),
               load_destfields=False)
    config.report_every_n_rows = args.report

    if args.draftdd or args.incrementaldd:
        # Note: the difference is that for incrementaldd, the data dictionary
        # will have been loaded from disk; for draftdd, it won't (so a
        # completely fresh one will be generated).
        config.dd.read_from_source_databases(
            default_omit=(not args.makeddpermitbydefaultdangerous))
        print(config.dd.get_tsv())
        return

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
                               incremental=args.incremental,
                               debuglimit=args.debuglimitpertable)

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
