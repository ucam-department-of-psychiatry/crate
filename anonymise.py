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

CHANGE LOG:

- v0.05, 2015-05-1
  - Ability to vary audit/secret map tablenames.
  - Made date element separators broader in anonymisation regex.
  - min_string_length_for_errors option
  - min_string_length_to_scrub_with option
  - words_not_to_scrub option
  - bugfix: date regex couldn't cope with years prior to 1900
  - gen_all_values_for_patient() was inefficient in that it would process the
    same source table multiple times to retrieve different fields.
  - ddgen_index_fields option
  - simplification of get_anon_fragments_from_string()
  - SCRUBMETHOD.CODE, particularly for postcodes. (Not very different from
    SCRUBMETHOD.NUMERIC, but a little different.)
  - debug_row_limit applies to patient-based tables (as a per-thread limit);
    was previously implemented as a per-patient limit, which was silly.
  - Indirection step in config for destination/admin databases.
  - ignore_fulltext_indexes option, for old MySQL versions.

- v0.04, 2015-04-25
  - Whole bunch of stuff to cope with a limited computer talking to SQL Server
    with some idiosyncrasies.

- v0.03, 2015-03-19
  - Bug fix for incremental update (previous version inserted rather than
    updating when the source content had changed); search for
    update_on_duplicate_key.
  - Checks for missing/extra fields in destination.
  - "No separator" allowed for get_date_regex_elements(), allowing
    anonymisation of e.g. 19Mar2015, 19800101.
  - New default at_word_boundaries_only=False for get_date_regex_elements(),
    allowing anonymisation of ISO8601-format dates (e.g. 1980-10-01T0000), etc.
  - Similar option for get_code_regex_elements().
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
import calendar
import cgi
import csv
import codecs
import ConfigParser
import datetime
import dateutil
import dateutil.tz
# import itertools
import logging
import multiprocessing
import operator
import os
import pytz
import regex  # sudo apt-get install python-regex
import signal
from sortedcontainers import SortedSet  # sudo pip install sortedcontainers
import sys
import threading
import urllib

from rnc_config import (
    read_config_multiline_options,
    read_config_string_options,
)
from rnc_crypto import MD5Hasher
from rnc_datetime import (
    coerce_to_date,
    format_datetime,
    get_now_utc,
    truncate_date_to_first_of_month,
)
import rnc_db
from rnc_db import (
    does_sqltype_merit_fulltext_index,
    does_sqltype_require_index_len,
    ensure_valid_field_name,
    ensure_valid_table_name,
    is_sqltype_binary,
    is_sqltype_date,
    is_sqltype_integer,
    is_sqltype_numeric,
    is_sqltype_text_over_one_char,
    is_sqltype_text_of_length_at_least,
    is_sqltype_valid,
)
from rnc_extract_text import document_to_text
from rnc_lang import (
    AttrDict,
    convert_attrs_to_bool,
    convert_attrs_to_int,
    convert_attrs_to_uppercase,
    count_bool,
    raise_if_attr_blank,
)
import rnc_log

# =============================================================================
# Global constants
# =============================================================================

VERSION = 0.05
VERSION_DATE = "2015-05-01"

MAX_PID_STR = "9" * 10  # e.g. NHS numbers are 10-digit
ENCRYPTED_OUTPUT_LENGTH = len(MD5Hasher("dummysalt").hash(MAX_PID_STR))
SQLTYPE_ENCRYPTED_PID = "VARCHAR({})".format(ENCRYPTED_OUTPUT_LENGTH)
# ... in practice: VARCHAR(32)

DATEFORMAT_ISO8601 = "%Y-%m-%dT%H:%M:%S%z"  # e.g. 2013-07-24T20:04:07+0100
DEFAULT_INDEX_LEN = 20  # for data types where it's mandatory
SEP = "=" * 20 + " "
LONGTEXT = "LONGTEXT"
DEFAULT_MAX_ROWS_BEFORE_COMMIT = 1000
DEFAULT_MAX_BYTES_BEFORE_COMMIT = 80 * 1024 * 1024

SCRUBSRC = AttrDict(
    PATIENT="patient",
    THIRDPARTY="thirdparty"
)
INDEX = AttrDict(
    NORMAL="I",
    UNIQUE="U",
    FULLTEXT="F"
)
SCRUBMETHOD = AttrDict(
    TEXT="text",
    NUMERIC="number",
    DATE="date",
    CODE="code"
)
ALTERMETHOD = AttrDict(
    TRUNCATEDATE="truncatedate",
    SCRUBIN="scrub",
    BIN2TEXT="binary_to_text",
    BIN2TEXT_SCRUB="binary_to_text_scrub",
    FILENAME2TEXT="filename_to_text",
    FILENAME2TEXT_SCRUB="filename_to_text_scrub"
)
SRCFLAG = AttrDict(
    PK="K",
    ADDSRCHASH="H",
    PRIMARYPID="P",
    DEFINESPRIMARYPIDS="*",
    MASTERPID="M",
    CONSTANT="C",
    ADDITION_ONLY="A"
)

RAW_SCRUBBER_FIELDNAME_PATIENT = "_raw_scrubber_patient"
RAW_SCRUBBER_FIELDNAME_TP = "_raw_scrubber_tp"

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
#   src_flags
#       One or more of the following characters:
#       {SRCFLAG.PK}:  This field is the primary key (PK) for the table it's
#           in.
#       {SRCFLAG.ADDSRCHASH}:  Add source hash, for incremental updates?
#           - May only be set for src_pk fields (which cannot then be omitted
#             in the destination, and which require the index={INDEX.UNIQUE}
#             setting, so that a unique index is created for this field).
#           - If set, a field is added to the destination table, with field
#             name as set by the config's source_hash_fieldname variable,
#             containing a hash of the contents of the source record (all
#             fields that are not omitted, OR contain scrubbing information
#             (scrub_src). The field is of type {SQLTYPE_ENCRYPTED_PID}.
#           - This table is then capable of incremental updates.
#       {SRCFLAG.CONSTANT}:  Contents are constant (will not change) for a
#           given PK.
#           - An alternative to '{SRCFLAG.ADDSRCHASH}'. Can't be used with it.
#           - Applicable only to src_pk fields, which can't be omitted in the
#             destination, and which have the same index requirements as
#             the '{SRCFLAG.ADDSRCHASH}' flag.
#           - If set, no hash is added to the destination, but the destination
#             contents are assumed to exist and not to have changed.
#           - Be CAUTIOUS with this flag, i.e. certain that the contents will
#             not change.
#           - Intended for very data-intensive fields, such as BLOB fields
#             containing binary documents, where hashing would be quite slow
#             over many gigabytes of data.
#       {SRCFLAG.ADDITION_ONLY}:  Addition only. It is assumed that records can
#           only be added, not deleted.
#       {SRCFLAG.PRIMARYPID}:  Primary patient ID field.
#           If set,
#           (a) This field will be used to link records for the same patient
#               across all tables. It must therefore be present, and marked in
#               the data dictionary, for ALL tables that contain patient-
#               identifiable information.
#           (b) If the field is not omitted: the field will be hashed as the
#               primary ID (database patient primary key) in the destination.
#       {SRCFLAG.DEFINESPRIMARYPIDS}:  This field *defines* primary PIDs.
#           If set, this row will be used to search for all patient IDs, and
#           will define them for this database. Only those patients will be
#           processed (for all tables containing patient info). Typically, this
#           flag is applied to a SINGLE field in a SINGLE table, usually the
#           principal patient registration/demographics table.
#       {SRCFLAG.MASTERPID}:  Master ID (e.g. NHS number). The field will be
#           hashed with the master PID hasher.
#
#   scrub_src
#       Either "{SCRUBSRC.PATIENT}", "{SCRUBSRC.THIRDPARTY}", or blank.
#       - If "{SCRUBSRC.PATIENT}", contains patient-identifiable information
#         that must be removed from "scrub_in" fields.
#       - If "{SCRUBSRC.THIRDPARTY}", contains identifiable information about
#         carer/family/other third party, which must be removed from
#         "scrub_in" fields.
#   scrub_method
#       Applicable to scrub_src fields. Manner in which this field should be
#       treated for scrubbing.
#       Options:
#       - "{SCRUBMETHOD.TEXT}": treat as text
#         This is the default for all textual fields (e. CHAR, VARCHAR, TEXT).
#       - "{SCRUBMETHOD.NUMERIC}": treat as number
#         This is the default for all numeric fields (e.g. INTEGER, FLOAT).
#         If you have a phone number in a text field, mark it as
#         "{SCRUBMETHOD.NUMERIC}" here. It will be scrubbed regardless of
#         spacing/punctuation.
#       - "{SCRUBMETHOD.CODE}": treat as an alphanumeric code. Suited to
#         postcodes. Very like "{SCRUBMETHOD.NUMERIC}" but permits non-digits.
#       - "{SCRUBMETHOD.DATE}": treat as date.
#         This is the default for all DATE/DATETIME fields.
#
#   omit
#       Boolean. Omit from output entirely?
#   alter_method
#       Manner in which to alter the data. Blank, or one of:
#       - "{ALTERMETHOD.SCRUBIN}": scrub in. Applies to text fields only. The
#         field will have its contents anonymised (using information from other
#         fields).
#       - "{ALTERMETHOD.TRUNCATEDATE}": truncate date to first of the month.
#         Applicable to text or date-as-text fields.
#       - "{ALTERMETHOD.BIN2TEXT}=EXTFIELDNAME": convert a binary field (e.g.
#         VARBINARY, BLOB) to text (e.g. {LONGTEXT}). The field EXTFIELDNAME,
#         which must be in the same source table, must contain the file
#         extension (e.g. "pdf", ".pdf") or a filename with that extension
#         (e.g. "/some/path/mything.pdf").
#       - "{ALTERMETHOD.BIN2TEXT_SCRUB}=EXTFIELDNAME": ditto, but also scrub
#         in.
#       - "{ALTERMETHOD.FILENAME2TEXT}": as for {ALTERMETHOD.BIN2TEXT}, but
#         the field contains a filename (the contents of which is converted
#         to text), rather than binary file contents directly.
#       - "{ALTERMETHOD.FILENAME2TEXT_SCRUB}": ditto, but also scrub in.
#
#   dest_table
#       Table name in destination database.
#   dest_field
#       Field name in destination database.
#   dest_datatype
#       SQL data type in destination database.
#   index
#       One of:
#       - blank: no index.
#       - "{INDEX.NORMAL}": normal index on destination.
#       - "{INDEX.UNIQUE}": unique index on destination.
#       - "{INDEX.FULLTEXT}": create a FULLTEXT index, for rapid searching
#         within long text fields. Only applicable to one field per table.
#   indexlen
#       Integer. Can be blank. If not, sets the prefix length of the index.
#       Mandatory in MySQL if you apply a normal (+/- unique) index to a TEXT
#       or BLOB field. Not required for FULLTEXT indexes.
#   comment
#       Field comment, stored in destination database.

data_dictionary_filename = testdd.tsv

# -----------------------------------------------------------------------------
# Encryption phrases/passwords
# -----------------------------------------------------------------------------

per_table_patient_id_encryption_phrase = SOME_PASSPHRASE_REPLACE_ME

master_patient_id_encryption_phrase = SOME_OTHER_PASSPHRASE_REPLACE_ME

change_detection_encryption_phrase = YETANOTHER

# -----------------------------------------------------------------------------
# Anonymisation
# -----------------------------------------------------------------------------

# Patient information will be replaced with this. For example, XXX or [___];
# the latter is a bit easier to spot, and works better if it directly abuts
# other text.

replace_patient_info_with = [___]

# Third-party information will be replaced by this. For example, YYY or [...].

replace_third_party_info_with = [...]

# Strings to append to every "scrub from" string.
# For example, include "s" if you want to scrub "Roberts" whenever you scrub
# "Robert".
# Multiline field: https://docs.python.org/2/library/configparser.html

scrub_string_suffixes =
    s

# Specify maximum number of errors (insertions, deletions, substitutions) in
# string regex matching. Beware using a high number! Suggest 1-2.

string_max_regex_errors = 1

# Is there a minimum length to apply string_max_regex_errors? For example, if
# you allow one typo and someone is called Ian, all instances of 'in' or 'an'
# will be wiped. Note that this apply to scrub-source data.

min_string_length_for_errors = 4

# Is there a minimum length of string to scrub WITH? For example, if you
# specify 2, you allow two-letter names such as Al to be scrubbed, but you
# allow initials through, and therefore prevent e.g. 'A' from being scrubbed
# from the destination. Note that this applies to scrub-source data.

min_string_length_to_scrub_with = 2

# Are there any words not to scrub? For example, "the", "road", "street" often
# appear in addresses, but you might not want them removed. Be careful in case
# these could be names (e.g. "Lane").

words_not_to_scrub = am
    an
    as
    at
    bd
    by
    he
    if
    is
    it
    me
    mg
    od
    of
    on
    or
    re
    so
    to
    us
    we
    her
    him
    tds
    she
    the
    you
    road
    street

# Anonymise at word boundaries? True is more conservative; False is more
# liberal and will deal with accidental word concatenation. With ID numbers,
# beware if you use a prefix, e.g. people write 'M123456' or 'R123456'; in that
# case you will need anonymise_numbers_at_word_boundaries_only = False.

anonymise_codes_at_word_boundaries_only = True
anonymise_dates_at_word_boundaries_only = True
anonymise_numbers_at_word_boundaries_only = False
anonymise_strings_at_word_boundaries_only = True

# -----------------------------------------------------------------------------
# Output fields and formatting
# -----------------------------------------------------------------------------

# Name used for the primary patient ID in the mapping table.

mapping_patient_id_fieldname = patient_id

# Research ID field name. This will be a {SQLTYPE_ENCRYPTED_PID}.
# Used to replace per_table_patient_id_field.

research_id_fieldname = brcid

# Name used for the master patient ID in the mapping table.

mapping_master_id_fieldname = nhsnum

# Similarly, used to replace ddgen_master_pid_fieldname:

master_research_id_fieldname = nhshash

# Change-detection hash fieldname. This will be a {SQLTYPE_ENCRYPTED_PID}.

source_hash_fieldname = _src_hash

# Date-to-text conversion formats

date_to_text_format = %Y-%m-%d
# ... ISO-8601, e.g. 2013-07-24
datetime_to_text_format = %Y-%m-%dT%H:%M:%S
# ... ISO-8601, e.g. 2013-07-24T20:04:07

# Append source table/field to the comment? Boolean.

append_source_info_to_comment = True

# -----------------------------------------------------------------------------
# Database password security
# -----------------------------------------------------------------------------

# Set this to True. Only set it to False to debug database opening failures,
# under supervision, then set it back to True again afterwards.

open_databases_securely = True

# -----------------------------------------------------------------------------
# Destination database configuration
# See the [destination_database] section for connection details.
# -----------------------------------------------------------------------------

# Specify the maximum number of rows to be processed before a COMMIT is issued
# on the database transaction. This prevents the transaction growing too large.
# Default is None (no limit).

max_rows_before_commit = {DEFAULT_MAX_ROWS_BEFORE_COMMIT}

# Specify the maximum number of source-record bytes (approximately!) that are
# processed before a COMMIT is issued on the database transaction. This
# prevents the transaction growing too large. The COMMIT will be issued *after*
# this limit has been met/exceeded, so it may be exceeded if the transaction
# just before the limit takes the cumulative total over the limit.
# Default is None (no limit).

max_bytes_before_commit = {DEFAULT_MAX_BYTES_BEFORE_COMMIT}

# We need a temporary table name for incremental updates. This can't be the
# name of a real destination table.

temporary_tablename = _temp_table

# Ignore full-text indexes, for databases that don't support them?
ignore_fulltext_indexes = False

# -----------------------------------------------------------------------------
# Admin database configuration
# See the [admin_database] section for connection details.
# -----------------------------------------------------------------------------

# Table name to use for the secret patient ID to research ID mapping.
# Usually no need to change the default.

secret_map_tablename = secret_map

# Table name to use for the audit trail of various types of access.
# Usually no need to change the default.

audit_tablename = audit

# -----------------------------------------------------------------------------
# Choose databases (defined in their own sections).
# -----------------------------------------------------------------------------

#   Source database list. Can be lots.
source_databases =
    mysourcedb1
    mysourcedb2

#   Destination database. Just one.
destination_database = my_destination_database

#   Admin database. Just one.
admin_database = my_admin_database

# =============================================================================
# Destination database details. User should have WRITE access.
# =============================================================================

[my_destination_database]

engine = mysql
host = localhost
port = 3306
user = XXX
password = XXX
db = XXX

# =============================================================================
# Administrative database. User should have WRITE access.
# =============================================================================

[my_admin_database]

engine = mysql
host = localhost
port = 3306
user = XXX
password = XXX
db = XXX

# In general, specify some of:
#   - engine: one of:
#       mysql
#       sqlserver
#   - interface: one of:
#       mysqldb [default for mysql engine]
#       odbc [default otherwise]
#       jdbc
#   - host, port, db [for mysqldb, JDBC]
#   - dsn, odbc_connection_string [for ODBC]
#   - username, password
# ... see rnc_db.py

# =============================================================================
# SOURCE DATABASE DETAILS BELOW HERE.
# User should have READ access only for safety.
# =============================================================================

[mysourcedb1]

# CONNECTION DETAILS

engine = mysql
host = localhost
port = 3306
user = XXX
password = XXX
db = XXX

# INPUT FIELDS, FOR THE AUTOGENERATION OF DATA DICTIONARIES

#   Force all tables/fields to lower case? Generally a good idea. Boolean;
#   default is True.
ddgen_force_lower_case = True

#   Allow the absence of patient info? Used to copy databases; WILL NOT
#   ANONYMISE. Boolean; default is False.
ddgen_allow_no_patient_info = False

#   Specify the (typically integer) patient identifier present in EVERY
#   table. It will be replaced by the research ID in the destination
#   database.
ddgen_per_table_pid_field = patient_id

#   Master patient ID fieldname. Used for e.g. NHS numbers.
ddgen_master_pid_fieldname = nhsnum

#   Blacklist any tables when creating new data dictionaries?
ddgen_table_blacklist =

#   Blacklist any fields (regardless of their table) when creating new data
#   dictionaries?
ddgen_field_blacklist =

#   Fieldnames assumed to be their table's PK:
ddgen_pk_fields =

#   Assume that content stays constant?
ddgen_constant_content = False

#   Assume that records can only be added, not deleted?
ddgen_addition_only = False

#   Predefine field(s) that define the existence of patient IDs? UNUSUAL.
ddgen_pid_defining_fieldnames =

#   Default fields to scrub from
ddgen_scrubsrc_patient_fields =
ddgen_scrubsrc_thirdparty_fields =

#   Override default scrubbing methods
ddgen_scrubmethod_code_fields =
ddgen_scrubmethod_date_fields =
ddgen_scrubmethod_number_fields =

#   Known safe fields, exempt from scrubbing
ddgen_safe_fields_exempt_from_scrubbing =

#   Define minimum text field length for scrubbing (shorter is assumed safe)
ddgen_min_length_for_scrubbing = 4

#   Other default manipulations
ddgen_truncate_date_fields =

#   Fields containing filenames, which files should be converted to text
ddgen_filename_to_text_fields =

#   Fields containing raw binary data from files (binary large objects; BLOBs),
#   whose contents should be converted to text -- paired with fields in the
#   same table containing their file extension (e.g. "pdf", ".PDF") or a
#   filename having that extension.
#   Specify it as a list of comma-joined pairs, e.g.
#       ddgen_binary_to_text_field_pairs = binary1field, ext1field
#           binary2field, ext2field
#           ...
ddgen_binary_to_text_field_pairs =

#   Fields to apply an index to
ddgen_index_fields =

# PROCESSING OPTIONS, TO LIMIT DATA QUANTITY FOR TESTING

#   Specify 0 (the default) for no limit, or a number of rows (e.g. 1000) to
#   apply to any tables listed in debug_limited_tables. For those tables, only
#   this many rows will be taken from the source database.
#   If you run a multiprocess/multithreaded anonymisation, this limit applies
#   per *process* (or task), not overall.
debug_row_limit =

#   List of tables to which to apply debug_row_limit (see above).
debug_limited_tables =

[mysourcedb2]

engine = mysql
host = localhost
port = 3306
user = XXX
password = XXX
db = XXX

ddgen_force_lower_case = True
ddgen_per_table_pid_field = patient_id
ddgen_master_pid_fieldname = nhsnum
ddgen_table_blacklist =
ddgen_field_blacklist =
ddgen_pk_fields =
ddgen_constant_content = False
ddgen_scrubsrc_patient_fields =
ddgen_scrubsrc_thirdparty_fields =
ddgen_scrubmethod_code_fields =
ddgen_scrubmethod_date_fields =
ddgen_scrubmethod_number_fields =
ddgen_safe_fields_exempt_from_scrubbing =
ddgen_min_length_for_scrubbing = 4
ddgen_truncate_date_fields =
ddgen_filename_to_text_fields =
ddgen_binary_to_text_field_pairs =

[camcops]
# Example for the CamCOPS anonymisation staging database

engine = mysql
host = localhost
port = 3306
user = XXX
password = XXX
db = XXX
db = camcops_anon_staging

# FOR EXAMPLE:
ddgen_force_lower_case = True
ddgen_per_table_pid_field = _patient_idnum1
ddgen_pid_defining_fieldnames = _patient_idnum1
ddgen_master_pid_fieldname = _patient_idnum2

ddgen_table_blacklist =

ddgen_field_blacklist = _patient_iddesc1
    _patient_idshortdesc1
    _patient_iddesc2
    _patient_idshortdesc2
    _patient_iddesc3
    _patient_idshortdesc3
    _patient_iddesc4
    _patient_idshortdesc4
    _patient_iddesc5
    _patient_idshortdesc5
    _patient_iddesc6
    _patient_idshortdesc6
    _patient_iddesc7
    _patient_idshortdesc7
    _patient_iddesc8
    _patient_idshortdesc8
    id
    patient_id
    _device
    _era
    _current
    _when_removed_exact
    _when_removed_batch_utc
    _removing_user
    _preserving_user
    _forcibly_preserved
    _predecessor_pk
    _successor_pk
    _manually_erased
    _manually_erased_at
    _manually_erasing_user
    _addition_pending
    _removal_pending
    _move_off_tablet

ddgen_pk_fields = _pk
ddgen_constant_content = False

ddgen_scrubsrc_patient_fields = _patient_forename
    _patient_surname
    _patient_dob
    _patient_idnum1
    _patient_idnum2
    _patient_idnum3
    _patient_idnum4
    _patient_idnum5
    _patient_idnum6
    _patient_idnum7
    _patient_idnum8

ddgen_scrubsrc_thirdparty_fields =

ddgen_scrubmethod_code_fields =
ddgen_scrubmethod_date_fields = _patient_dob
ddgen_scrubmethod_number_fields =

ddgen_safe_fields_exempt_from_scrubbing = _device
    _era
    _when_added_exact
    _adding_user
    _when_removed_exact
    _removing_user
    _preserving_user
    _manually_erased_at
    _manually_erasing_user
    when_last_modified
    when_created
    when_firstexit
    clinician_specialty
    clinician_name
    clinician_post
    clinician_professional_registration
    clinician_contact_details
# ... now some task-specific ones
    bdi_scale
    pause_start_time
    pause_end_time
    trial_start_time
    cue_start_time
    target_start_time
    detection_start_time
    iti_start_time
    iti_end_time
    trial_end_time
    response_time
    target_time
    choice_time
    discharge_date
    discharge_reason_code
    diagnosis_psych_1_icd10code
    diagnosis_psych_1_description
    diagnosis_psych_2_icd10code
    diagnosis_psych_2_description
    diagnosis_psych_3_icd10code
    diagnosis_psych_3_description
    diagnosis_psych_4_icd10code
    diagnosis_psych_4_description
    diagnosis_medical_1
    diagnosis_medical_2
    diagnosis_medical_3
    diagnosis_medical_4
    category_start_time
    category_response_time
    category_chosen
    gamble_fixed_option
    gamble_lottery_option_p
    gamble_lottery_option_q
    gamble_start_time
    gamble_response_time
    likelihood

ddgen_min_length_for_scrubbing = 4

ddgen_truncate_date_fields = _patient_dob
ddgen_filename_to_text_fields =
ddgen_binary_to_text_field_pairs =

""".format(
    SQLTYPE_ENCRYPTED_PID=SQLTYPE_ENCRYPTED_PID,
    SCRUBSRC=SCRUBSRC,
    INDEX=INDEX,
    SCRUBMETHOD=SCRUBMETHOD,
    ALTERMETHOD=ALTERMETHOD,
    SRCFLAG=SRCFLAG,
    LONGTEXT=LONGTEXT,
    DEFAULT_MAX_ROWS_BEFORE_COMMIT=DEFAULT_MAX_ROWS_BEFORE_COMMIT,
    DEFAULT_MAX_BYTES_BEFORE_COMMIT=DEFAULT_MAX_BYTES_BEFORE_COMMIT
)

# For the style:
#       [source_databases]
#       source1 = blah
#       source2 = thing
# ... you can't have multiple keys with the same name.
# http://stackoverflow.com/questions/287757


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
        "src_flags",

        "scrub_src",
        "scrub_method",

        "omit",
        "alter_method",

        "dest_table",
        "dest_field",
        "dest_datatype",
        "index",
        "indexlen",
        "comment",
    ]

    def __init__(self):
        for x in DataDictionaryRow.ROWNAMES:
            setattr(self, x, None)
        self._signature = None
        self._from_file = False
        # For alter_method:
        self._scrub = False
        self._truncate_date = False
        self._extract_text = False
        self._extract_from_filename = False
        self._extract_ext_field = ""

    def alter_method_to_components(self):
        self._scrub = False
        self._truncate_date = False
        self._extract_text = False
        self._extract_from_filename = False
        self._extract_ext_field = ""
        secondhalf = ""
        if "=" in self.alter_method:
            secondhalf = self.alter_method[self.alter_method.index("=") + 1:]
        if self.alter_method == ALTERMETHOD.TRUNCATEDATE:
            self._truncate_date = True
        elif self.alter_method.startswith(ALTERMETHOD.SCRUBIN):
            self._scrub = True
        elif self.alter_method.startswith(ALTERMETHOD.BIN2TEXT):
            self._extract_text = True
            self._extract_ext_field = secondhalf
        elif self.alter_method.startswith(ALTERMETHOD.BIN2TEXT_SCRUB):
            self._extract_text = True
            self._extract_ext_field = secondhalf
            self._scrub = True
        elif self.alter_method.startswith(ALTERMETHOD.FILENAME2TEXT):
            self._extract_text = True
            self._extract_from_filename = True
        elif self.alter_method.startswith(ALTERMETHOD.FILENAME2TEXT_SCRUB):
            self._extract_text = True
            self._extract_from_filename = True
            self._scrub = True

    def get_alter_method(self):
        if self._truncate_date:
            return ALTERMETHOD.TRUNCATEDATE
        if self._extract_text:
            if self._extract_ext_field:
                if self._scrub:
                    return (ALTERMETHOD.BIN2TEXT_SCRUB + "=" +
                            self._extract_ext_field)
                else:
                    return ALTERMETHOD.BIN2TEXT + "=" + self._extract_ext_field
            else:
                if self._scrub:
                    return ALTERMETHOD.FILENAME2TEXT_SCRUB
                else:
                    return ALTERMETHOD.FILENAME2TEXT
        if self._scrub:
            return ALTERMETHOD.SCRUBIN
        return ""

    def components_to_alter_method(self):
        self.alter_method = self.get_alter_method()

    def __str__(self):
        self.components_to_alter_method()
        return ", ".join(["{}: {}".format(a, getattr(self, a))
                          for a in DataDictionaryRow.ROWNAMES])

    def get_signature(self):
        return "{}.{}.{}".format(self.src_db,
                                 self.src_table,
                                 self.src_field)

    def set_from_elements(self, elements):
        if len(elements) != len(DataDictionaryRow.ROWNAMES):
            raise ValueError("Bad data dictionary row. Values:\n" +
                             "\n".join(elements))
        for i in xrange(len(elements)):
            setattr(self, DataDictionaryRow.ROWNAMES[i], elements[i])
        convert_attrs_to_bool(self, [
            "omit",
        ])
        convert_attrs_to_uppercase(self, [
            "src_datatype",
            "dest_datatype",
        ])
        convert_attrs_to_int(self, [
            "indexlen"
        ])
        self._from_file = True
        self.alter_method_to_components()
        self.check_valid()

    def set_from_src_db_info(self, db, table, field, datatype_short,
                             datatype_full, cfg, comment=None,
                             default_omit=True):
        self.src_db = db
        self.src_table = table
        self.src_field = field
        self.src_datatype = datatype_full

        # Is the field special, such as a PK?
        self.src_flags = ""
        if self.src_field in cfg.ddgen_pk_fields:
            self.src_flags += SRCFLAG.PK
            if cfg.ddgen_constant_content:
                self.src_flags += SRCFLAG.CONSTANT
            else:
                self.src_flags += SRCFLAG.ADDSRCHASH
            if cfg.ddgen_addition_only:
                self.src_flags += SRCFLAG.ADDITION_ONLY
        if self.src_field == cfg.ddgen_per_table_pid_field:
            self.src_flags += SRCFLAG.PRIMARYPID
        if self.src_field == cfg.ddgen_master_pid_fieldname:
            self.src_flags += SRCFLAG.MASTERPID
        if self.src_field in cfg.ddgen_pid_defining_fieldnames:  # unusual!
            self.src_flags += SRCFLAG.DEFINESPRIMARYPIDS

        # Does the field contain sensitive data?
        if (self.src_field in cfg.ddgen_scrubsrc_patient_fields
                or self.src_field == cfg.ddgen_per_table_pid_field
                or self.src_field == cfg.ddgen_master_pid_fieldname
                or self.src_field in cfg.ddgen_pid_defining_fieldnames):
            self.scrub_src = SCRUBSRC.PATIENT
        elif self.src_field in cfg.ddgen_scrubsrc_thirdparty_fields:
            self.scrub_src = SCRUBSRC.THIRDPARTY
        elif (self.src_field in cfg.ddgen_scrubmethod_code_fields
                or self.src_field in cfg.ddgen_scrubmethod_date_fields
                or self.src_field in cfg.ddgen_scrubmethod_number_fields):
            # We're not sure what sort these are, but it seems conservative to
            # include these! Easy to miss them otherwise, and better to be
            # overly conservative.
            self.scrub_src = SCRUBSRC.PATIENT
        else:
            self.scrub_src = ""

        # What kind of sensitive data? Date, text, number, code?
        if not self.scrub_src:
            self.scrub_method = ""
        elif (is_sqltype_numeric(datatype_full)
                or self.src_field == cfg.ddgen_per_table_pid_field
                or self.src_field == cfg.ddgen_master_pid_fieldname
                or self.src_field in cfg.ddgen_scrubmethod_number_fields):
            self.scrub_method = SCRUBMETHOD.NUMERIC
        elif (is_sqltype_date(datatype_full)
              or self.src_field in cfg.ddgen_scrubmethod_date_fields):
            self.scrub_method = SCRUBMETHOD.DATE
        elif self.src_field in cfg.ddgen_scrubmethod_code_fields:
            self.scrub_method = SCRUBMETHOD.CODE
        else:
            self.scrub_method = SCRUBMETHOD.TEXT

        # Should we omit it (at least until a human has looked at the DD)?
        self.omit = (
            (default_omit or bool(self.scrub_src))
            and not (SRCFLAG.PK in self.src_flags)
            and not (SRCFLAG.PRIMARYPID in self.src_flags)
            and not (SRCFLAG.MASTERPID in self.src_flags)
        )

        # Do we want to change the destination fieldname?
        if SRCFLAG.PRIMARYPID in self.src_flags:
            self.dest_field = config.research_id_fieldname
        elif SRCFLAG.MASTERPID in self.src_flags:
            self.dest_field = config.master_research_id_fieldname
        else:
            self.dest_field = field

        # Do we want to change the destination field SQL type?
        self.dest_datatype = (
            SQLTYPE_ENCRYPTED_PID
            if (SRCFLAG.PRIMARYPID in self.src_flags
                or SRCFLAG.MASTERPID in self.src_flags)
            else rnc_db.full_datatype_to_mysql(datatype_full))

        # How should we manipulate the destination?
        if self.src_field in cfg.ddgen_truncate_date_fields:
            self._truncate_date = True
        elif self.src_field in cfg.ddgen_filename_to_text_fields:
            self._extract_text = True
            self._extract_from_filename = True
            self.dest_datatype = LONGTEXT
            if (self.src_field not in
                    cfg.ddgen_safe_fields_exempt_from_scrubbing):
                self._scrub = True
        elif self.src_field in cfg.bin2text_dict.keys():
            self._extract_text = True
            self._extract_from_filename = False
            self._extract_ext_field = cfg.bin2text_dict[self.src_field]
            self.dest_datatype = LONGTEXT
            if (self.src_field not in
                    cfg.ddgen_safe_fields_exempt_from_scrubbing):
                self._scrub = True
        elif (is_sqltype_text_of_length_at_least(
                datatype_full, cfg.ddgen_min_length_for_scrubbing)
                and not self.omit
                and SRCFLAG.PRIMARYPID not in self.src_flags
                and SRCFLAG.MASTERPID not in self.src_flags
                and self.src_field not in
                cfg.ddgen_safe_fields_exempt_from_scrubbing):
            self._scrub = True

        self.dest_table = table

        # Should we index the destination?
        if SRCFLAG.PK in self.src_flags:
            self.index = INDEX.UNIQUE
        elif (self.dest_field == config.research_id_fieldname
                or SRCFLAG.PRIMARYPID in self.src_flags
                or SRCFLAG.MASTERPID in self.src_flags
                or SRCFLAG.DEFINESPRIMARYPIDS in self.src_flags):
            self.index = INDEX.NORMAL
        elif does_sqltype_merit_fulltext_index(self.dest_datatype):
            self.index = INDEX.FULLTEXT
        elif self.src_field in cfg.ddgen_index_fields:
            self.index = INDEX.NORMAL
        else:
            self.index = ""

        self.indexlen = (
            DEFAULT_INDEX_LEN
            if (does_sqltype_require_index_len(self.dest_datatype)
                and self.index != INDEX.FULLTEXT)
            else None
        )

        self.comment = comment
        self._from_file = False
        self.check_valid()

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
        self.components_to_alter_method()
        offenderdest = "" if not self.omit else " -> {}.{}".format(
            self.dest_table, self.dest_field)
        offender = "{}.{}.{}{}".format(
            self.src_db, self.src_table, self.src_field, offenderdest)
        try:
            self._check_valid()
        except:
            logger.exception(
                "Offending DD row [{}]: {}".format(offender, str(self)))
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
            raise ValueError(
                "Data dictionary row references non-existent source "
                "database")
        srccfg = config.srccfg[self.src_db]
        ensure_valid_table_name(self.src_table)
        ensure_valid_field_name(self.src_field)
        if not is_sqltype_valid(self.src_datatype):
            raise ValueError(
                "Field has invalid source data type: {}".format(
                    self.src_datatype))

        if (self.src_field == srccfg.ddgen_per_table_pid_field
                and not is_sqltype_integer(self.src_datatype)):
            raise ValueError(
                "All fields with src_field = {} should be integer, for work "
                "distribution purposes".format(self.src_field))

        if (SRCFLAG.DEFINESPRIMARYPIDS in self.src_flags
                and SRCFLAG.PRIMARYPID not in self.src_flags):
            raise ValueError(
                "All fields with src_flags={} set must have src_flags={} "
                "set".format(
                    SRCFLAG.DEFINESPRIMARYPIDS,
                    SRCFLAG.PRIMARYPID
                ))

        if count_bool([SRCFLAG.PRIMARYPID in self.src_flags,
                       SRCFLAG.MASTERPID in self.src_flags,
                       bool(self.alter_method)]) > 1:
            raise ValueError(
                "Field can be any ONE of: src_flags={}, src_flags={}, "
                "alter_method".format(
                    SRCFLAG.PRIMARYPID,
                    SRCFLAG.MASTERPID
                ))

        valid_scrubsrc = [SCRUBSRC.PATIENT, SCRUBSRC.THIRDPARTY, ""]
        if self.scrub_src not in valid_scrubsrc:
            raise ValueError(
                "Invalid scrub_src - must be one of [{}]".format(
                    ",".join(valid_scrubsrc)))

        if (self.scrub_src and self.scrub_method
                and self.scrub_method not in SCRUBMETHOD.values()):
            raise ValueError(
                "Invalid scrub_method - must be blank or one of [{}]".format(
                    ",".join(SCRUBMETHOD.values())))

        if not self.omit:
            ensure_valid_table_name(self.dest_table)
            if self.dest_table == config.temporary_tablename:
                raise ValueError(
                    "Destination tables can't be named {f}, as that's the "
                    "name set in the config's temporary_tablename "
                    "variable".format(config.temporary_tablename))
            ensure_valid_field_name(self.dest_field)
            if self.dest_field == config.source_hash_fieldname:
                raise ValueError(
                    "Destination fields can't be named {f}, as that's the "
                    "name set in the config's source_hash_fieldname "
                    "variable".format(config.source_hash_fieldname))
            if not is_sqltype_valid(self.dest_datatype):
                raise ValueError(
                    "Field has invalid destination data type: "
                    "{}".format(self.dest_datatype))
            if self.src_field == srccfg.ddgen_per_table_pid_field:
                if SRCFLAG.PRIMARYPID not in self.src_flags:
                    raise ValueError(
                        "All fields with src_field={} used in output should "
                        "have src_flag={} set".format(self.src_field,
                                                      SRCFLAG.PRIMARYPID))
                if self.dest_field != config.research_id_fieldname:
                    raise ValueError(
                        "Primary PID field should have "
                        "dest_field = {}".format(
                            config.research_id_fieldname))
            if (self.src_field == srccfg.ddgen_master_pid_fieldname
                    and SRCFLAG.MASTERPID not in self.src_flags):
                raise ValueError(
                    "All fields with src_field = {} used in output should have"
                    " src_flags={} set".format(
                        srccfg.ddgen_master_pid_fieldname,
                        SRCFLAG.MASTERPID))

            if self._truncate_date:
                if not (is_sqltype_date(self.src_datatype)
                        or is_sqltype_text_over_one_char(self.src_datatype)):
                    raise ValueError("Can't set truncate_date for non-date/"
                                     "non-text field")
            if self._extract_text:
                if self._extract_from_filename:
                    if not is_sqltype_text_over_one_char(self.src_datatype):
                        raise ValueError(
                            "For alter_method = {ALTERMETHOD.FILENAME2TEXT} or"
                            " {ALTERMETHOD.FILENAME2TEXT_SCRUB}, source field "
                            "must contain filename and therefore must be text "
                            "type of >1 character".format(
                                ALTERMETHOD=ALTERMETHOD))
                else:
                    if not is_sqltype_binary(self.src_datatype):
                        raise ValueError(
                            "For alter_method = {ALTERMETHOD.BIN2TEXT} or "
                            "{ALTERMETHOD.BIN2TEXT_SCRUB}, source field "
                            "must be of binary type".format(
                                ALTERMETHOD=ALTERMETHOD))
                    if not self._extract_ext_field:
                        raise ValueError(
                            "For alter_method = {ALTERMETHOD.BIN2TEXT} or "
                            "{ALTERMETHOD.BIN2TEXT_SCRUB}, must also specify "
                            "field containing extension (or filename with "
                            "extension) in the alter_method parameter".format(
                                ALTERMETHOD=ALTERMETHOD))
            if self._scrub and not self._extract_text:
                if not is_sqltype_text_over_one_char(self.src_datatype):
                    raise ValueError("Can't scrub in non-text field or "
                                     "single-character text field")

            if ((SRCFLAG.PRIMARYPID in self.src_flags
                 or SRCFLAG.MASTERPID in self.src_flags) and
                    self.dest_datatype != SQLTYPE_ENCRYPTED_PID):
                raise ValueError(
                    "All src_flags={}/src_flags={} fields used in output must "
                    "have destination_datatype = {}".format(
                        SRCFLAG.PRIMARYPID,
                        SRCFLAG.MASTERPID,
                        SQLTYPE_ENCRYPTED_PID))

            valid_index = [INDEX.NORMAL, INDEX.UNIQUE, INDEX.FULLTEXT, ""]
            if self.index not in valid_index:
                raise ValueError("Index must be one of: [{}]".format(
                    ",".join(valid_index)))

            if (self.index in [INDEX.NORMAL, INDEX.UNIQUE]
                    and self.indexlen is None
                    and does_sqltype_require_index_len(self.dest_datatype)):
                raise ValueError(
                    "Must specify indexlen to index a TEXT or BLOB field")

        if SRCFLAG.ADDSRCHASH in self.src_flags:
            if SRCFLAG.PK not in self.src_flags:
                raise ValueError(
                    "src_flags={} can only be set on "
                    "src_flags={} fields".format(
                        SRCFLAG.ADDSRCHASH,
                        SRCFLAG.PK))
            if self.omit:
                raise ValueError(
                    "Do not set omit on src_flags={} fields".format(
                        SRCFLAG.ADDSRCHASH))
            if self.index != INDEX.UNIQUE:
                raise ValueError(
                    "src_flags={} fields require index=={}".format(
                        SRCFLAG.ADDSRCHASH,
                        INDEX.UNIQUE))
            if SRCFLAG.CONSTANT in self.src_flags:
                raise ValueError(
                    "cannot mix {} flag with {} flag".format(
                        SRCFLAG.ADDSRCHASH,
                        SRCFLAG.CONSTANT))

        if SRCFLAG.CONSTANT in self.src_flags:
            if SRCFLAG.PK not in self.src_flags:
                raise ValueError(
                    "src_flags={} can only be set on "
                    "src_flags={} fields".format(
                        SRCFLAG.CONSTANT,
                        SRCFLAG.PK))
            if self.omit:
                raise ValueError(
                    "Do not set omit on src_flags={} fields".format(
                        SRCFLAG.CONSTANT))
            if self.index != INDEX.UNIQUE:
                raise ValueError(
                    "src_flags={} fields require index=={}".format(
                        SRCFLAG.CONSTANT,
                        INDEX.UNIQUE))


class DataDictionary(object):
    def __init__(self):
        self.rows = []

    def read_from_file(self, filename, check_against_source_db=True):
        self.rows = []
        logger.debug("Opening data dictionary: {}".format(filename))
        with open(filename, 'rb') as tsvfile:
            tsv = csv.reader(tsvfile, delimiter='\t')
            headerlist = tsv.next()
            if headerlist != DataDictionaryRow.ROWNAMES:
                raise ValueError(
                    "Bad data dictionary file. Must be a tab-separated value "
                    "(TSV) file with the following row headings:\n" +
                    "\n".join(DataDictionaryRow.ROWNAMES)
                )
            logger.debug("Data dictionary has correct header. "
                         "Loading content...")
            for rowelements in tsv:
                ddr = DataDictionaryRow()
                ddr.set_from_elements(rowelements)
                self.rows.append(ddr)
            logger.debug("... content loaded.")
        self.cache_stuff()
        self.check_valid(check_against_source_db)

    def read_from_source_databases(self, report_every=100,
                                   default_omit=True):
        logger.info("Reading information for draft data dictionary")
        for pretty_dbname, db in config.sources.iteritems():
            cfg = config.srccfg[pretty_dbname]
            schema = db.get_schema()
            logger.info("... database nice name = {}, schema = {}".format(
                pretty_dbname, schema))
            if db.db_flavour == rnc_db.DatabaseSupporter.FLAVOUR_SQLSERVER:
                sql = """
                    SELECT table_name, column_name, data_type, {}, NULL
                    FROM information_schema.columns
                    WHERE table_schema=?
                """.format(rnc_db.DatabaseSupporter.SQLSERVER_COLUMN_TYPE_EXPR)
            else:
                sql = """
                    SELECT table_name, column_name, data_type, column_type,
                        column_comment
                    FROM information_schema.columns
                    WHERE table_schema=?
                """
            args = [schema]
            i = 0
            signatures = []
            for r in db.gen_fetchall(sql, *args):
                i += 1
                if report_every and i % report_every == 0:
                    logger.debug("... reading source field {}".format(i))
                t = r[0]
                f = r[1]
                datatype_short = r[2].upper()
                datatype_full = r[3].upper()
                c = r[4]
                if cfg.ddgen_force_lower_case:
                    t = t.lower()
                    f = f.lower()
                if (t in cfg.ddgen_table_blacklist
                        or f in cfg.ddgen_field_blacklist):
                    continue
                ddr = DataDictionaryRow()
                ddr.set_from_src_db_info(
                    pretty_dbname, t, f, datatype_short,
                    datatype_full,
                    cfg=cfg,
                    comment=c,
                    default_omit=default_omit)
                sig = ddr.get_signature()
                if sig not in signatures:
                    self.rows.append(ddr)
                    signatures.append(sig)
        logger.info("... done")
        self.cache_stuff()
        logger.info("Revising draft data dictionary")
        for ddr in self.rows:
            if ddr._from_file:
                continue
            # Don't scrub_in non-patient tables
            if (ddr.src_table
                    not in self.cached_src_tables_w_pt_info[ddr.src_db]):
                ddr._scrub = False
                ddr.components_to_alter_method()
        logger.info("... done")
        logger.info("Sorting draft data dictionary")
        self.rows = sorted(self.rows,
                           key=operator.attrgetter("src_db",
                                                   "src_table",
                                                   "src_field"))
        logger.info("... done")

    def cache_stuff(self):
        logger.debug("Caching data dictionary information...")
        self.cached_dest_tables = SortedSet()
        self.cached_source_databases = SortedSet()
        self.cached_srcdb_table_pairs = SortedSet()
        self.cached_srcdb_table_pairs_w_pt_info = SortedSet()  # w = with
        self.cached_scrub_from_db_table_pairs = SortedSet()
        self.cached_scrub_from_rows = {}
        self.cached_src_tables = {}
        self.cached_src_tables_w_pt_info = {}  # w = with
        src_tables_with_dest = {}
        self.cached_pt_src_tables_w_dest = {}
        self.cached_rows_for_src_table = {}
        self.cached_rows_for_dest_table = {}
        self.cached_fieldnames_for_src_table = {}
        self.cached_src_dbtables_for_dest_table = {}
        self.cached_pk_ddr = {}
        self.cached_has_active_destination = {}
        self.cached_dest_tables_for_src_db_table = {}
        self.cached_srcdb_table_pairs_to_int_pk = {}  # (db, table): pkname
        for ddr in self.rows:

            # Database-oriented maps
            if ddr.src_db not in self.cached_src_tables:
                self.cached_src_tables[ddr.src_db] = SortedSet()
            if ddr.src_db not in self.cached_pt_src_tables_w_dest:
                self.cached_pt_src_tables_w_dest[ddr.src_db] = SortedSet()
            if ddr.src_db not in self.cached_src_tables_w_pt_info:
                self.cached_src_tables_w_pt_info[ddr.src_db] = SortedSet()
            if ddr.src_db not in src_tables_with_dest:
                src_tables_with_dest[ddr.src_db] = SortedSet()

            # (Database + table)-oriented maps
            db_t_key = (ddr.src_db, ddr.src_table)
            if db_t_key not in self.cached_rows_for_src_table:
                self.cached_rows_for_src_table[db_t_key] = SortedSet()
            if db_t_key not in self.cached_fieldnames_for_src_table:
                self.cached_fieldnames_for_src_table[db_t_key] = SortedSet()
            if db_t_key not in self.cached_dest_tables_for_src_db_table:
                self.cached_dest_tables_for_src_db_table[db_t_key] = \
                    SortedSet()
            if db_t_key not in self.cached_scrub_from_rows:
                self.cached_scrub_from_rows[db_t_key] = SortedSet()

            # Destination table-oriented maps
            if ddr.dest_table not in self.cached_src_dbtables_for_dest_table:
                self.cached_src_dbtables_for_dest_table[ddr.dest_table] = \
                    SortedSet()
            if ddr.dest_table not in self.cached_rows_for_dest_table:
                self.cached_rows_for_dest_table[ddr.dest_table] = SortedSet()

            # Regardless...
            self.cached_rows_for_src_table[db_t_key].add(ddr)
            self.cached_fieldnames_for_src_table[db_t_key].add(ddr.src_field)
            self.cached_srcdb_table_pairs.add(db_t_key)
            self.cached_src_dbtables_for_dest_table[ddr.dest_table].add(
                db_t_key)
            self.cached_rows_for_dest_table[ddr.dest_table].add(ddr)

            if db_t_key not in self.cached_has_active_destination:
                self.cached_has_active_destination[db_t_key] = False

            # Is it a scrub-from row?
            if ddr.scrub_src:
                self.cached_scrub_from_db_table_pairs.add(db_t_key)
                self.cached_scrub_from_rows[db_t_key].add(ddr)
                # ... even if omit flag set

            # Is it a src_pk row, contributing to src_hash info?
            if SRCFLAG.PK in ddr.src_flags:
                logger.debug("SRCFLAG.PK found: {}".format(ddr))
                self.cached_pk_ddr[db_t_key] = ddr
                if rnc_db.is_sqltype_integer(ddr.src_datatype):
                    self.cached_srcdb_table_pairs_to_int_pk[db_t_key] = \
                        ddr.src_field

            # Is it a relevant contribution from a source table?
            pt_info = (
                bool(ddr.scrub_src)
                or SRCFLAG.PRIMARYPID in ddr.src_flags
                or SRCFLAG.MASTERPID in ddr.src_flags
            )
            omit = ddr.omit
            if pt_info or not omit:
                # Ensure our source lists contain that table.
                self.cached_source_databases.add(ddr.src_db)
                self.cached_src_tables[ddr.src_db].add(ddr.src_table)

            # Does it indicate that the table contains patient info?
            if pt_info:
                self.cached_src_tables_w_pt_info[ddr.src_db].add(
                    ddr.src_table)
                self.cached_srcdb_table_pairs_w_pt_info.add(db_t_key)

            # Does it contribute to our destination?
            if not omit:
                self.cached_dest_tables.add(ddr.dest_table)
                self.cached_has_active_destination[db_t_key] = True
                src_tables_with_dest[ddr.src_db].add(ddr.dest_table)
                self.cached_dest_tables_for_src_db_table[db_t_key].add(
                    ddr.dest_table
                )

        db_table_pairs_w_int_pk = set(
            self.cached_srcdb_table_pairs_to_int_pk.keys()
        )

        # Set calculations...
        self.cached_srcdb_table_pairs_wo_pt_info_no_pk = sorted(
            self.cached_srcdb_table_pairs
            - self.cached_srcdb_table_pairs_w_pt_info
            - db_table_pairs_w_int_pk
        )
        self.cached_srcdb_table_pairs_wo_pt_info_int_pk = sorted(
            (self.cached_srcdb_table_pairs
                - self.cached_srcdb_table_pairs_w_pt_info)
            & db_table_pairs_w_int_pk
        )
        for s in self.cached_source_databases:
            self.cached_pt_src_tables_w_dest[s] = sorted(
                self.cached_src_tables_w_pt_info[s]
                & src_tables_with_dest[s]  # & is intersection
            )

        # Debugging
        logger.debug("cached_srcdb_table_pairs_w_pt_info: {}".format(
            list(self.cached_srcdb_table_pairs_w_pt_info)))
        logger.debug("cached_srcdb_table_pairs_wo_pt_info_no_pk: {}".format(
            self.cached_srcdb_table_pairs_wo_pt_info_no_pk))
        logger.debug("cached_srcdb_table_pairs_wo_pt_info_int_pk: {}".format(
            self.cached_srcdb_table_pairs_wo_pt_info_int_pk))

    def check_against_source_db(self):
        logger.debug("Checking DD: source tables...")
        for d in self.get_source_databases():
            db = config.sources[d]
            for t in self.get_src_tables(d):

                dt = self.get_dest_tables_for_src_db_table(d, t)
                if len(dt) > 1:
                    raise ValueError(
                        "Source table {d}.{t} maps to >1 destination "
                        "table: {dt}".format(
                            d=d,
                            t=t,
                            dt=", ".join(dt),
                        )
                    )

                rows = self.get_rows_for_src_table(d, t)
                fieldnames = self.get_fieldnames_for_src_table(d, t)

                if any([r._scrub or SRCFLAG.MASTERPID in r.src_flags
                        for r in rows if not r.omit]):
                    if not config.srccfg[d].ddgen_per_table_pid_field \
                            in fieldnames:
                        raise ValueError(
                            "Source table {d}.{t} has a scrub_in or "
                            "src_flags={f} field but no {p} field".format(
                                d=d,
                                t=t,
                                f=SRCFLAG.MASTERPID,
                                p=config.srccfg[d].ddgen_per_table_pid_field,
                            )
                        )

                for r in rows:
                    if r._extract_text and not r._extract_from_filename:
                        extrow = next(
                            (r2 for r2 in rows
                                if r2.src_field == r._extract_ext_field),
                            None)
                        if extrow is None:
                            raise ValueError(
                                "alter_method = {am}, but field {f} not "
                                "found in the same table".format(
                                    am=r.alter_method,
                                    f=r._extract_ext_field
                                )
                            )
                        if not is_sqltype_text_over_one_char(
                                extrow.src_datatype):
                            raise ValueError(
                                "alter_method = {am}, but field {f}, which"
                                " should contain an extension or filename,"
                                " is not text of >1 character".format(
                                    am=r.alter_method,
                                    f=r._extract_ext_field
                                )
                            )

                n_pks = sum([1 if SRCFLAG.PK in x.src_flags else 0
                             for x in rows])
                if n_pks > 1:
                    raise ValueError(
                        "Table {d}.{t} has >1 source PK set".format(
                            d=d, t=t))

                if not db.table_exists(t):
                    raise ValueError(
                        "Table {t} missing from source database "
                        "{d}".format(
                            t=t,
                            d=d
                        )
                    )

    def check_valid(self, check_against_source_db):
        logger.info("Checking data dictionary...")
        if not self.rows:
            raise ValueError("Empty data dictionary")
        if not self.cached_dest_tables:
            raise ValueError("Empty data dictionary after removing "
                             "redundant tables")

        # Individual rows will already have been checked
        # for r in self.rows:
        #    r.check_valid()
        # Now check collective consistency

        logger.debug("Checking DD: destination tables...")
        for t in self.get_dest_tables():
            sdt = self.get_src_dbs_tables_for_dest_table(t)
            if len(sdt) > 1:
                raise ValueError(
                    "Destination table {t} is mapped to by multiple "
                    "source databases: {s}".format(
                        t=t,
                        s=", ".join(["{}.{}".format(s[0], s[1]) for s in sdt]),
                    )
                )

        if check_against_source_db:
            self.check_against_source_db()

        logger.debug("Checking DD: global checks...")
        self.n_definers = sum(
            [1 if SRCFLAG.DEFINESPRIMARYPIDS in x.src_flags else 0
             for x in self.rows])
        if self.n_definers == 0:
            if all([x.ddgen_allow_no_patient_info
                    for x in config.srccfg.itervalues()]):
                logger.warning("NO PATIENT-DEFINING FIELD! DATABASE(S) WILL "
                               "BE COPIED, NOT ANONYMISED.")
            else:
                raise ValueError(
                    "Must have at least one field with "
                    "src_flags={} set.".format(SRCFLAG.DEFINESPRIMARYPIDS))
        if self.n_definers > 1:
            logger.warning(
                "Unusual: >1 field with src_flags={} set.".format(
                    SRCFLAG.DEFINESPRIMARYPIDS))

    def get_dest_tables(self):
        return self.cached_dest_tables

    def get_dest_tables_for_src_db_table(self, src_db, src_table):
        return self.cached_dest_tables_for_src_db_table[(src_db, src_table)]

    def get_dest_table_for_src_db_table(self, src_db, src_table):
        return self.cached_dest_tables_for_src_db_table[(src_db, src_table)][0]

    def get_source_databases(self):
        return self.cached_source_databases

    def get_src_dbs_tables_for_dest_table(self, dest_table):
        return self.cached_src_dbtables_for_dest_table[dest_table]

    def get_src_tables(self, src_db):
        return self.cached_src_tables[src_db]

    def get_patient_src_tables_with_active_dest(self, src_db):
        return self.cached_pt_src_tables_w_dest[src_db]

    def get_src_tables_with_patient_info(self, src_db):
        return self.cached_src_tables_w_pt_info[src_db]

    def get_rows_for_src_table(self, src_db, src_table):
        return self.cached_rows_for_src_table[(src_db, src_table)]

    def get_rows_for_dest_table(self, dest_table):
        return self.cached_rows_for_dest_table[dest_table]

    def get_fieldnames_for_src_table(self, src_db, src_table):
        return self.cached_fieldnames_for_src_table[(src_db, src_table)]

    def get_scrub_from_db_table_pairs(self):
        return self.cached_scrub_from_db_table_pairs

    def get_scrub_from_rows(self, src_db, src_table):
        return self.cached_scrub_from_rows[(src_db, src_table)]

    def get_tsv(self):
        return "\n".join(
            ["\t".join(DataDictionaryRow.ROWNAMES)]
            + [r.get_tsv() for r in self.rows]
        )

    def get_src_db_tablepairs(self):
        return self.cached_srcdb_table_pairs

    def get_src_dbs_tables_with_no_pt_info_no_pk(self):
        return self.cached_srcdb_table_pairs_wo_pt_info_no_pk

    def get_src_dbs_tables_with_no_pt_info_int_pk(self):
        return self.cached_srcdb_table_pairs_wo_pt_info_int_pk

    def get_int_pk_name(self, src_db, src_table):
        return self.cached_srcdb_table_pairs_to_int_pk[(src_db, src_table)]

    def get_pk_ddr(self, src_db, src_table):
        # Will return None if no such data dictionary row
        return self.cached_pk_ddr.get((src_db, src_table), None)

    def has_active_destination(self, src_db, src_table):
        return self.cached_has_active_destination[(src_db, src_table)]


# =============================================================================
# Config/databases
# =============================================================================

class DatabaseSafeConfig(object):
    def __init__(self, parser, section):
        read_config_string_options(self, parser, section, [
            "ddgen_force_lower_case",
            "ddgen_allow_no_patient_info",
            "ddgen_per_table_pid_field",
            "ddgen_master_pid_fieldname",
            "ddgen_constant_content",
            "ddgen_addition_only",
            "ddgen_min_length_for_scrubbing",
            "debug_row_limit",
        ])
        read_config_multiline_options(self, parser, section, [
            "ddgen_pk_fields",
            "ddgen_pid_defining_fieldnames",
            "ddgen_table_blacklist",
            "ddgen_field_blacklist",
            "ddgen_scrubsrc_patient_fields",
            "ddgen_scrubsrc_thirdparty_fields",
            "ddgen_scrubmethod_code_fields",
            "ddgen_scrubmethod_date_fields",
            "ddgen_scrubmethod_number_fields",
            "ddgen_safe_fields_exempt_from_scrubbing",
            "ddgen_truncate_date_fields",
            "ddgen_filename_to_text_fields",
            "ddgen_binary_to_text_field_pairs",
            "ddgen_index_fields",
            "debug_limited_tables",
        ])
        convert_attrs_to_bool(self, [
            "ddgen_force_lower_case",
        ], default=True)
        convert_attrs_to_bool(self, [
            "ddgen_allow_no_patient_info",
            "ddgen_constant_content",
            "ddgen_addition_only",
        ], default=False)
        convert_attrs_to_int(self, [
            "debug_row_limit",
            "ddgen_min_length_for_scrubbing"
        ], default=0)
        self.bin2text_dict = {}
        for pair in self.ddgen_binary_to_text_field_pairs:
            items = [item.strip() for item in pair.split(",")]
            if len(items) != 2:
                raise ValueError("ddgen_binary_to_text_field_pairs: specify "
                                 "fields in pairs")
            self.bin2text_dict[items[0]] = items[1]


# =============================================================================
# DestinationFieldInfo
# =============================================================================

class DestinationFieldInfo(object):
    def __init__(self, table, field, fieldtype, comment):
        self.table = table
        self.field = field
        self.fieldtype = fieldtype
        self.comment = comment

    def __str__(self):
        return "table={}, field={}, fieldtype={}, comment={}".format(
            self.table, self.field, self.fieldtype, self.comment
        )


# =============================================================================
# Config
# =============================================================================

class Config(object):
    MAIN_HEADINGS = [
        "data_dictionary_filename",
        "ddgen_master_pid_fieldname",
        "per_table_patient_id_encryption_phrase",
        "master_patient_id_encryption_phrase",
        "change_detection_encryption_phrase",
        "replace_patient_info_with",
        "replace_third_party_info_with",
        "string_max_regex_errors",
        "min_string_length_for_errors",
        "min_string_length_to_scrub_with",
        "anonymise_codes_at_word_boundaries_only",
        "anonymise_dates_at_word_boundaries_only",
        "anonymise_numbers_at_word_boundaries_only",
        "anonymise_strings_at_word_boundaries_only",
        "mapping_patient_id_fieldname",
        "research_id_fieldname",
        "mapping_master_id_fieldname",
        "master_research_id_fieldname",
        "source_hash_fieldname",
        "date_to_text_format",
        "datetime_to_text_format",
        "append_source_info_to_comment",
        "open_databases_securely",
        "max_rows_before_commit",
        "max_bytes_before_commit",
        "temporary_tablename",
        "ignore_fulltext_indexes",
        "secret_map_tablename",
        "audit_tablename",
        "destination_database",
        "admin_database",
    ]
    MAIN_MULTILINE_HEADINGS = [
        "scrub_string_suffixes",
        "words_not_to_scrub",
        "source_databases",
    ]

    def __init__(self):
        self.config_filename = None
        for x in Config.MAIN_HEADINGS:
            setattr(self, x, None)
        self.report_every_n_rows = 100
        self.PERSISTENT_CONSTANTS_INITIALIZED = False
        self.DESTINATION_FIELDS_LOADED = False
        self.destfieldinfo = []
        self._rows_in_transaction = 0
        self._bytes_in_transaction = 0
        self.debug_scrubbers = False
        self.save_scrubbers = False
        self._rows_inserted_per_table = {}

    def set(self, filename=None, environ=None, include_sources=True,
            load_dd=True, load_destfields=True):
        """Set up process-local storage from the incoming environment (which
        may be very fast if already cached) and ensure we have an active
        database connection."""
        # 1. Set up process-local storage
        self.set_internal(filename, environ, include_sources=include_sources,
                          load_dd=load_dd)
        if load_destfields:
            self.load_destination_fields()
        # 2. Ping MySQL connection, to reconnect if it's timed out.
        self.admindb.ping()
        self.destdb.ping()
        for db in self.sources.values():
            db.ping()

    def set_internal(self, filename=None, environ=None, include_sources=True,
                     load_dd=True):
        self.set_always()
        if self.PERSISTENT_CONSTANTS_INITIALIZED:
            self.init_row_counts()
            return
        logger.info(SEP + "Loading config")
        if filename and environ:
            raise ValueError("Config.set(): mis-called")
        if environ:
            self.read_environ(environ)
        else:
            self.read_environ(os.environ)
            self.config_filename = filename
        self.read_config(include_sources=include_sources)
        self.check_valid(include_sources=include_sources)
        self.dd = DataDictionary()
        if load_dd:
            logger.info(SEP + "Loading data dictionary")
            self.dd.read_from_file(config.data_dictionary_filename,
                                   check_against_source_db=include_sources)
        self.init_row_counts()
        self.PERSISTENT_CONSTANTS_INITIALIZED = True

    def set_always(self):
        """Set the things we set every time the script is invoked (time!)."""
        localtz = dateutil.tz.tzlocal()
        self.NOW_LOCAL_TZ = datetime.datetime.now(localtz)
        self.NOW_UTC_WITH_TZ = self.NOW_LOCAL_TZ.astimezone(pytz.utc)
        self.NOW_UTC_NO_TZ = self.NOW_UTC_WITH_TZ.replace(tzinfo=None)
        self.NOW_LOCAL_TZ_ISO8601 = self.NOW_LOCAL_TZ.strftime(
            DATEFORMAT_ISO8601)
        self.TODAY = datetime.date.today()  # fetches the local date
        self._rows_in_transaction = 0
        self._bytes_in_transaction = 0

    def init_row_counts(self):
        self._rows_inserted_per_table = {}
        for db_table_tuple in self.dd.get_src_db_tablepairs():
            self._rows_inserted_per_table[db_table_tuple] = 0

    def read_environ(self, environ):
        self.remote_addr = environ.get("REMOTE_ADDR", "")
        self.remote_port = environ.get("REMOTE_PORT", "")
        self.SCRIPT_NAME = environ.get("SCRIPT_NAME", "")
        self.SERVER_NAME = environ.get("SERVER_NAME", "")

        # Reconstruct URL:
        # http://www.python.org/dev/peps/pep-0333/#url-reconstruction
        url = environ.get("wsgi.url_scheme", "") + "://"
        if environ.get("HTTP_HOST"):
            url += environ.get("HTTP_HOST")
        else:
            url += environ.get("SERVER_NAME", "")
        if environ.get("wsgi.url_scheme") == "https":
            if environ.get("SERVER_PORT") != "443":
                url += ':' + environ.get("SERVER_PORT", "")
        else:
            if environ.get("SERVER_PORT") != "80":
                url += ':' + environ.get("SERVER_PORT", "")
        url += urllib.quote(environ.get("SCRIPT_NAME", ""))
        url += urllib.quote(environ.get("PATH_INFO", ""))
        # But not the query string:
        # if environ.get("QUERY_STRING"):
        #    url += "?" + environ.get("QUERY_STRING")
        self.SCRIPT_PUBLIC_URL_ESCAPED = cgi.escape(url)

    def read_config(self, include_sources=False):
        """Read config from file."""
        logger.debug("Opening config: {}".format(self.config_filename))
        parser = ConfigParser.RawConfigParser()
        parser.readfp(codecs.open(self.config_filename, "r", "utf8"))
        read_config_string_options(self, parser, "main", Config.MAIN_HEADINGS)
        read_config_multiline_options(self, parser, "main",
                                      Config.MAIN_MULTILINE_HEADINGS)
        # Processing of parameters
        convert_attrs_to_bool(self, [
            "anonymise_codes_at_word_boundaries_only",
            "anonymise_dates_at_word_boundaries_only",
            "anonymise_numbers_at_word_boundaries_only",
            "anonymise_strings_at_word_boundaries_only",
            "append_source_info_to_comment",
            "open_databases_securely",
            "ignore_fulltext_indexes",
        ])
        convert_attrs_to_int(self, [
            "string_max_regex_errors",
            "min_string_length_for_errors",
            "min_string_length_to_scrub_with",
            "max_rows_before_commit",
            "max_bytes_before_commit",
        ])
        # Force words_not_to_scrub to lower case for speed later
        self.words_not_to_scrub = [x.lower() for x in self.words_not_to_scrub]

        # Databases
        self.destdb = self.get_database(self.destination_database)
        self.admindb = self.get_database(self.admin_database)
        self.sources = {}
        self.srccfg = {}
        self.src_db_names = []
        for sourcedb_name in self.source_databases:
            self.src_db_names.append(sourcedb_name)
            if not include_sources:
                continue
            self.sources[sourcedb_name] = self.get_database(sourcedb_name)
            self.srccfg[sourcedb_name] = DatabaseSafeConfig(
                parser, sourcedb_name)
        # Hashers
        self.primary_pid_hasher = None
        self.master_pid_hasher = None
        self.change_detection_hasher = None

    def get_database(self, section):
        parser = ConfigParser.RawConfigParser()
        parser.readfp(codecs.open(self.config_filename, "r", "utf8"))
        return rnc_db.get_database_from_configparser(
            parser, section, securely=self.open_databases_securely)

    def check_valid(self, include_sources=False):
        """Raise exception if config is invalid."""

        # Destination databases
        if not self.destdb:
            raise ValueError("No destination database specified.")
        if not self.admindb:
            raise ValueError("No admin database specified.")

        # Test table names
        if not self.temporary_tablename:
            raise ValueError("No temporary_tablename specified.")
        ensure_valid_field_name(self.temporary_tablename)
        if not self.secret_map_tablename:
            raise ValueError("No secret_map_tablename specified.")
        ensure_valid_field_name(self.secret_map_tablename)
        if not self.audit_tablename:
            raise ValueError("No audit_tablename specified.")
        ensure_valid_field_name(self.audit_tablename)

        # Test field names
        def validate_fieldattr(name):
            if not getattr(self, name):
                raise ValueError("Blank fieldname: " + name)
            ensure_valid_field_name(getattr(self, name))

        specialfieldlist = [
            "mapping_patient_id_fieldname",
            "research_id_fieldname",
            "master_research_id_fieldname",
            "mapping_master_id_fieldname",
            "source_hash_fieldname",
        ]
        fieldset = set()
        for attrname in specialfieldlist:
            validate_fieldattr(attrname)
            fieldset.add(getattr(self, attrname))
        if len(fieldset) != len(specialfieldlist):
            raise ValueError("Config: these must all be DIFFERENT fieldnames: "
                             + ",".join(specialfieldlist))

        # Test strings
        if not self.replace_patient_info_with:
            raise ValueError("Blank replace_patient_info_with")
        if not self.replace_third_party_info_with:
            raise ValueError("Blank replace_third_party_info_with")
        if (self.replace_patient_info_with ==
                self.replace_third_party_info_with):
            raise ValueError("Inadvisable: replace_patient_info_with == "
                             "replace_third_party_info_with")

        # Regex
        if self.string_max_regex_errors < 0:
            raise ValueError("string_max_regex_errors < 0, nonsensical")
        if self.min_string_length_for_errors < 0:
            raise ValueError("min_string_length_for_errors < 0, nonsensical")
        if self.min_string_length_to_scrub_with < 0:
            raise ValueError(
                "min_string_length_to_scrub_with < 0, nonsensical")

        # Test date conversions
        format_datetime(self.NOW_UTC_NO_TZ, self.date_to_text_format)
        format_datetime(self.NOW_UTC_NO_TZ, self.datetime_to_text_format)

        # Load encryption keys
        if not self.per_table_patient_id_encryption_phrase:
            raise ValueError("Missing per_table_patient_id_encryption_phrase")
        self.primary_pid_hasher = MD5Hasher(
            self.per_table_patient_id_encryption_phrase)

        if not self.master_patient_id_encryption_phrase:
            raise ValueError("Missing master_patient_id_encryption_phrase")
        self.master_pid_hasher = MD5Hasher(
            self.master_patient_id_encryption_phrase)

        if not self.change_detection_encryption_phrase:
            raise ValueError("Missing change_detection_encryption_phrase")
        self.change_detection_hasher = MD5Hasher(
            self.change_detection_encryption_phrase)

        # Source databases
        if not include_sources:
            return
        if not self.sources:
            raise ValueError("No source databases specified.")
        for dbname, cfg in self.srccfg.iteritems():
            if not cfg.ddgen_allow_no_patient_info:
                if not cfg.ddgen_per_table_pid_field:
                    raise ValueError(
                        "Missing ddgen_per_table_pid_field in config for "
                        "database {}".format(dbname))
                ensure_valid_field_name(cfg.ddgen_per_table_pid_field)
                if cfg.ddgen_per_table_pid_field == self.source_hash_fieldname:
                    raise ValueError("Config: ddgen_per_table_pid_field can't "
                                     "be the same as source_hash_fieldname")
            if cfg.ddgen_master_pid_fieldname:
                ensure_valid_field_name(cfg.ddgen_master_pid_fieldname)

        # OK!
        logger.debug("Config validated.")

    def encrypt_primary_pid(self, pid):
        return self.primary_pid_hasher.hash(pid)

    def encrypt_master_pid(self, pid):
        if pid is None:
            return None  # or risk of revealing the hash?
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

    def load_destination_fields(self, force=False):
        if self.DESTINATION_FIELDS_LOADED and not force:
            return
        # Everything that was in the data dictionary should now be in the
        # destination, commented... so just process actual destination fields,
        # which will encompass all oddities including NLP fields.
        for t in self.destdb.get_all_table_names():
            for c in self.destdb.fetch_column_names(t):
                fieldtype = self.destdb.get_column_type(t, c)
                comment = self.destdb.get_comment(t, c)
                dfi = DestinationFieldInfo(t, c, fieldtype, comment)
                self.destfieldinfo.append(dfi)
        self.DESTINATION_FIELDS_LOADED = True


# =============================================================================
# Regexes
# =============================================================================

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
    # month_word = dt.strftime("%B")  # can't cope with years < 1900
    month_word = calendar.month_name[dt.month]
    month_word = month_word[0:3] + "(?:" + month_word[3:] + ")?"
    month = "(?:" + month_numeric + "|" + month_word + ")"
    # Year
    year = str(dt.year)
    if len(year) == 4:
        year = "(?:" + year[0:2] + ")?" + year[2:4]
        # ... converts e.g. 1986 to (19)?86, to match 1986 or 86
    SEP = "[\W]*"  # zero or more non-alphanumeric characters...
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


def get_code_regex_elements(s, liberal=True, at_word_boundaries_only=True):
    """Takes a STRING representation of a number or an alphanumeric code, which
    may include leading zeros (as for phone numbers), and produces a list of
    regex strings for scrubbing.

    We allow all sorts of separators. For example, 0123456789 might appear as
        (01234) 56789
        0123 456 789
        01234-56789
        0123.456.789

    This can also be used for postcodes, which should have whitespace
    prestripped, so e.g. PE123AB might appear as
        PE123AB
        PE12 3AB
        PE 12 3 AB
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


def reduce_to_alphanumeric(s):
    return "".join([d for d in s if d.isalnum()])


def remove_whitespace(s):
    return ''.join(s.split())


NON_ALPHANUMERIC_SPLITTERS = regex.compile("[\W]+", regex.UNICODE)
# 1 or more non-alphanumeric characters...


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
    return NON_ALPHANUMERIC_SPLITTERS.split(s)
    #smallfragments = []
    #combinedsmallfragments = []
    #for chunk in s.split():  # split on whitespace
    #    for smallchunk in NON_WHITESPACE_SPLITTERS.split(chunk):
    #        if smallchunk.lower() in config.words_not_to_scrub:
    #            continue
    #        smallfragments.append(smallchunk)
    #        # OVERLAP here, but we need it for the combination bit, and
    #        # we remove the overlap at the end.
    ## Now we have chunks with e.g. apostrophes in, and all chunks split by
    ## everything. Finally, we want all of these lumped together.
    #for L in xrange(len(smallfragments) + 1):
    #    for subset in itertools.combinations(smallfragments, L):
    #        if subset:
    #            combinedsmallfragments.append("".join(subset))
    #return list(set(smallfragments + combinedsmallfragments))
# EXAMPLES:
# get_anon_fragments_from_string("Bob D'Souza")
# get_anon_fragments_from_string("Jemima Al-Khalaim")
# get_anon_fragments_from_string("47 Russell Square")


def get_string_regex_elements(s, suffixes=None, at_word_boundaries_only=True,
                              max_errors=0):
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
import calendar
import dateutil.parser
import regex

import logging
logging.basicConfig()  # just in case nobody else has done this
logger = logging.getLogger("anonymise")

testnumber = 34
testnumber_as_text = "123456"
testdate = dateutil.parser.parse("7 Jan 2013")
teststring = "mother"
old_testdate = dateutil.parser.parse("3 Sep 1847")

s = u"""

SHOULD REPLACE:
   I was born on 07 Jan 2013, m'lud.
   It was 7 January 13, or 7/1/13, or 1/7/13, or
   Jan 7 2013, or 2013/01/07, or 2013-01-07,
   or 7th January
   13 (split over a line)
   or Jan 7th 13
   or 07.01.13 or 7.1.2013
   or a host of other variations.
   And ISO-8601 formats like 20130107T0123, or just 20130107.

   BUT NOT 8 Jan 2013, or 2013/02/07, or 2013
   Jan 17, or just a number like 7, or a month
   like January, or a nonspecific date like
   Jan 2013 or 7 January.
   And not ISO-8601-formatted other dates like 20130108T0123, or just 20130108.

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
    get_code_regex_elements(str(testnumber)))
regex_number_as_text = get_regex_from_elements(
    get_code_regex_elements(
        get_digit_string_from_vaguely_numeric_string(testnumber_as_text)))
regex_string = get_regex_from_elements(get_string_regex_elements(teststring))
all_elements = (
    get_date_regex_elements(testdate)
    + get_code_regex_elements(str(testnumber))
    + get_code_regex_elements(
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
print(get_regex_string_from_elements(get_date_regex_elements(testdate)))
print(get_regex_string_from_elements(get_date_regex_elements(old_testdate)))
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
        db_table_pair_list = config.dd.get_scrub_from_db_table_pairs()
        for (src_db, src_table) in db_table_pair_list:
            ddrows = config.dd.get_scrub_from_rows(src_db, src_table)
            fields = []
            scrub_methods = []
            is_patient = []
            is_mpid = []
            for ddr in ddrows:
                fields.append(ddr.src_field)
                scrub_methods.append(self.get_scrub_method(ddr.src_datatype,
                                                           ddr.scrub_method))
                is_patient.append(ddr.scrub_src == SCRUBSRC.PATIENT)
                is_mpid.append(SRCFLAG.MASTERPID in ddr.src_flags)
            for vlist in gen_all_values_for_patient(sources, src_db, src_table,
                                                    fields, pid):
                for i in xrange(len(vlist)):
                    self.add_value(vlist[i], scrub_methods[i], is_patient[i])
                    if self.mpid is None and is_mpid[i]:
                        # We've come across the master ID.
                        self.mpid = vlist[i]
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
                l = len(s)
                if l < config.min_string_length_to_scrub_with:
                    # With numbers: if you use the length limit, you may see
                    # numeric parts of addresses, e.g. 4 Drury Lane as
                    # 4 [___] [___]. However, if you exempt numbers then you
                    # mess up a whole bunch of quantitative information, such
                    # as "the last 4-5 years" getting wiped to "the last
                    # [___]-5 years". So let's apply the length limit
                    # consistently.
                    continue
                if s.lower() in config.words_not_to_scrub:
                    continue
                if l >= config.min_string_length_for_errors:
                    max_errors = config.string_max_regex_errors
                else:
                    max_errors = 0
                elements.extend(get_string_regex_elements(
                    s,
                    config.scrub_string_suffixes,
                    max_errors=max_errors,
                    at_word_boundaries_only=wbo))
        elif scrub_method == SCRUBMETHOD.NUMERIC:
            # Source is a text field containing a number, or an actual number.
            # Remove everything but the digits
            # Particular examples: phone numbers, e.g. "(01223) 123456".
            wbo = config.anonymise_numbers_at_word_boundaries_only
            elements = get_code_regex_elements(
                get_digit_string_from_vaguely_numeric_string(str(value)),
                at_word_boundaries_only=wbo)
        elif scrub_method == SCRUBMETHOD.CODE:
            # Source is a text field containing an alphanumeric code.
            # Remove whitespace.
            # Particular examples: postcodes, e.g. "PE12 3AB".
            wbo = config.anonymise_codes_at_word_boundaries_only
            elements = get_code_regex_elements(
                reduce_to_alphanumeric(str(value)),
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
        if config.debug_scrubbers:
            logger.debug(
                "Patient scrubber: {}".format(self.get_patient_regex_string()))
            logger.debug(
                "Third party scrubber: {}".format(self.get_tp_regex_string()))

    def get_patient_regex_string(self):
        return get_regex_string_from_elements(self.re_patient_elements)

    def get_tp_regex_string(self):
        return get_regex_string_from_elements(self.re_tp_elements)

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
        table=config.secret_map_tablename,
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
        table=config.secret_map_tablename,
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
        config.audit_tablename,
        AUDIT_FIELDSPECS,
        drop_superfluous_columns=True,
        dynamic=True,
        compressed=False)
    if not db.mysql_table_using_barracuda(config.audit_tablename):
        db.mysql_convert_table_to_barracuda(config.audit_tablename,
                                            compressed=False)


def insert_into_mapping_db(admindb, scrubber):
    pid = scrubber.get_pid()
    rid = config.encrypt_primary_pid(pid)
    mpid = scrubber.get_mpid()
    mrid = config.encrypt_master_pid(mpid)
    scrubber_hash = config.hash_scrubber(scrubber)
    raw_pt = None
    raw_tp = None
    if config.save_scrubbers:
        raw_pt = scrubber.get_patient_regex_string()
        raw_tp = scrubber.get_tp_regex_string()
    if patient_in_map(admindb, pid):
        sql = """
            UPDATE {table}
            SET {master_id} = ?, {master_research_id} = ?, {scrubber_hash} = ?,
                {RAW_SCRUBBER_FIELDNAME_PATIENT} = ?,
                {RAW_SCRUBBER_FIELDNAME_TP} = ?
            WHERE {patient_id} = ?
        """.format(
            table=config.secret_map_tablename,
            master_id=config.mapping_master_id_fieldname,
            master_research_id=config.master_research_id_fieldname,
            scrubber_hash=config.source_hash_fieldname,
            patient_id=config.mapping_patient_id_fieldname,
            RAW_SCRUBBER_FIELDNAME_PATIENT=RAW_SCRUBBER_FIELDNAME_PATIENT,
            RAW_SCRUBBER_FIELDNAME_TP=RAW_SCRUBBER_FIELDNAME_TP,
        )
        args = [mpid, mrid, scrubber_hash, raw_pt, raw_tp, pid]
    else:
        sql = """
            INSERT INTO {table} (
                {patient_id}, {research_id},
                {master_id}, {master_research_id},
                {scrubber_hash},
                {RAW_SCRUBBER_FIELDNAME_PATIENT}, {RAW_SCRUBBER_FIELDNAME_TP}
            )
            VALUES (
                ?, ?,
                ?, ?,
                ?,
                ?, ?
            )
        """.format(
            table=config.secret_map_tablename,
            patient_id=config.mapping_patient_id_fieldname,
            research_id=config.research_id_fieldname,
            master_id=config.mapping_master_id_fieldname,
            master_research_id=config.master_research_id_fieldname,
            scrubber_hash=config.source_hash_fieldname,
            RAW_SCRUBBER_FIELDNAME_PATIENT=RAW_SCRUBBER_FIELDNAME_PATIENT,
            RAW_SCRUBBER_FIELDNAME_TP=RAW_SCRUBBER_FIELDNAME_TP,
        )
        args = [pid, rid, mpid, mrid, scrubber_hash, raw_pt, raw_tp]
    admindb.db_exec(sql, *args)
    admindb.commit()
    # Commit immediately, because other processes may need this table promptly.
    # Otherwise, get:
    #   Deadlock found when trying to get lock; try restarting transaction


def wipe_and_recreate_mapping_table(admindb, incremental=False):
    logger.debug("wipe_and_recreate_mapping_table")
    if not incremental:
        admindb.drop_table(config.secret_map_tablename)
    fieldspecs = [
        dict(name=config.mapping_patient_id_fieldname,
             sqltype="BIGINT UNSIGNED", pk=True,
             comment="Patient ID (PK)"),
        dict(name=config.research_id_fieldname,
             sqltype=SQLTYPE_ENCRYPTED_PID, notnull=True,
             comment="Research ID"),
        dict(name=config.mapping_master_id_fieldname,
             sqltype="BIGINT UNSIGNED",
             comment="Master ID"),
        dict(name=config.master_research_id_fieldname,
             sqltype=SQLTYPE_ENCRYPTED_PID,
             comment="Master research ID"),
        dict(name=config.source_hash_fieldname,
             sqltype=SQLTYPE_ENCRYPTED_PID,
             comment="Scrubber hash (for change detection)"),
        dict(name=RAW_SCRUBBER_FIELDNAME_PATIENT,
             sqltype="TEXT",
             comment="Raw patient scrubber (for debugging only)"),
        dict(name=RAW_SCRUBBER_FIELDNAME_TP,
             sqltype="TEXT",
             comment="Raw third-party scrubber (for debugging only)"),
    ]
    admindb.create_or_update_table(
        config.secret_map_tablename,
        fieldspecs,
        drop_superfluous_columns=True,
        dynamic=True,
        compressed=False)
    if not admindb.mysql_table_using_barracuda(config.secret_map_tablename):
        admindb.mysql_convert_table_to_barracuda(config.secret_map_tablename,
                                                 compressed=False)


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


def delete_dest_rows_with_no_src_row(srcdb, srcdbname, src_table,
                                     report_every=1000, chunksize=10000):
    # - Can't do this in a single SQL command, since the engine can't
    #   necessarily see both databases.
    # - Can't do this in a multiprocess way, because we're trying to do a
    #   DELETE WHERE NOT IN.
    # - However, we can get stupidly long query lists if we try to SELECT all
    #   the values and use a DELETE FROM x WHERE y NOT IN (v1, v2, v3, ...)
    #   query. This crashes the MySQL connection, etc.
    # - Therefore, we need a temporary table in the destination.
    if not config.dd.has_active_destination(srcdbname, src_table):
        return
    dest_table = config.dd.get_dest_table_for_src_db_table(srcdbname,
                                                           src_table)
    pkddr = config.dd.get_pk_ddr(srcdbname, src_table)
    PKFIELD = "srcpk"
    START = "delete_dest_rows_with_no_src_row: {}.{} -> {}.{}: ".format(
        srcdbname, src_table, config.destination_database, dest_table
    )
    logger.info(START + "[WARNING: MAY BE SLOW]")

    # 0. If there's no source PK, we just delete everythong
    if not pkddr:
        logger.info("... No source PK; deleting everything")
        config.destdb.db_exec("DELETE FROM {}".format(dest_table))
        commit(config.destdb)
        return

    if SRCFLAG.ADDITION_ONLY in pkddr.src_flags:
        logger.info("... Table marked as addition-only; not deleting anything")
        return

    # 1. Drop temporary table
    logger.debug("... dropping temporary table")
    config.destdb.drop_table(config.temporary_tablename)

    # 2. Make temporary table
    logger.debug("... making temporary table")
    create_sql = """
        CREATE TABLE IF NOT EXISTS {table} (
            {pkfield} BIGINT UNSIGNED PRIMARY KEY
        )
    """.format(
        table=config.temporary_tablename,
        pkfield=PKFIELD,
    )
    config.destdb.db_exec(create_sql)

    # 3. Populate temporary table, +/- PK translation
    def insert(records):
        logger.debug(START + "... inserting {} records".format(len(records)))
        config.destdb.insert_multiple_records(
            config.temporary_tablename,
            [PKFIELD],
            records
        )

    n = srcdb.count_where(src_table)
    logger.debug("... populating temporary table")
    i = 0
    records = []
    for pk in gen_pks(srcdb, src_table, pkddr.src_field):
        i += 1
        if report_every and i % report_every == 0:
            logger.debug(START + "... src row# {} / {}".format(i, n))
        if SRCFLAG.PRIMARYPID in pkddr.src_flags:
            pk = config.encrypt_primary_pid(pk)
        elif SRCFLAG.MASTERPID in pkddr.src_flags:
            pk = config.encrypt_master_pid(pk)
        records.append([pk])
        if i % chunksize == 0:
            insert(records)
            records = []
    if records:
        insert(records)
        records = []
    commit(config.destdb)

    # 4. Index
    logger.debug("... creating index on temporary table")
    config.destdb.create_index(config.temporary_tablename, PKFIELD)

    # 5. DELETE FROM ... WHERE NOT IN ...
    logger.debug("... deleting from destination where appropriate")
    delete_sql = """
        DELETE FROM {dest_table}
        WHERE {dest_pk} NOT IN (
            SELECT {pkfield} FROM {temptable}
        )
    """.format(
        dest_table=pkddr.dest_table,
        dest_pk=pkddr.dest_field,
        pkfield=PKFIELD,
        temptable=config.temporary_tablename,
    )
    config.destdb.db_exec(delete_sql)

    # 6. Drop temporary table
    logger.debug("... dropping temporary table")
    config.destdb.drop_table(config.temporary_tablename)

    # 6. Commit
    commit(config.destdb)


def commit(destdb):
    logger.info("Committing...")
    destdb.commit()
    logger.info("... done")
    config._rows_in_transaction = 0
    config._bytes_in_transaction = 0


# =============================================================================
# Audit
# =============================================================================

AUDIT_FIELDSPECS = [
    dict(name="id", sqltype="INT UNSIGNED", pk=True, autoincrement=True,
         comment="Arbitrary primary key"),
    dict(name="when_access_utc", sqltype="DATETIME", notnull=True,
         comment="Date/time of access (UTC)", indexed=True),
    dict(name="source", sqltype="VARCHAR(20)", notnull=True,
         comment="Source (e.g. tablet, webviewer)"),
    dict(name="remote_addr",
         sqltype="VARCHAR(45)",  # http://stackoverflow.com/questions/166132
         comment="IP address of the remote computer"),
    dict(name="user", sqltype="VARCHAR(255)",
         comment="User name, where applicable"),
    dict(name="query", sqltype="TEXT",
         comment="SQL query (with arguments)"),
    dict(name="details", sqltype="TEXT",
         comment="Details of the access"),
]


def audit(details,
          from_console=False, remote_addr=None, user=None, query=None):
    """Write an entry to the audit log."""
    if not remote_addr:
        remote_addr = config.session.ip_address if config.session else None
    if not user:
        user = config.session.user if config.session else None
    if from_console:
        source = "console"
    else:
        source = "webviewer"
    config.admindb.db_exec(
        """
            INSERT INTO {table}
                (when_access_utc, source, remote_addr, user, query, details)
            VALUES
                (?,?,?,?,?,?)
        """.format(table=config.audit_tablename),
        config.NOW_UTC_NO_TZ,  # when_access_utc
        source,
        remote_addr,
        user,
        query,
        details
    )


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


def gen_all_values_for_patient(sources, dbname, table, fields, pid):
    cfg = config.srccfg[dbname]
    if not cfg.ddgen_per_table_pid_field:
        return
        # http://stackoverflow.com/questions/13243766
    logger.debug(
        "gen_all_values_for_patient: PID {p}, table {d}.{t}, "
        "fields: {f}".format(
            d=dbname, t=table, f=",".join(fields), p=pid))
    db = sources[dbname]
    sql = rnc_db.get_sql_select_all_fields_by_key(
        table, fields, cfg.ddgen_per_table_pid_field, delims=db.delims)
    args = [pid]
    cursor = db.cursor()
    db.db_exec_with_cursor(cursor, sql, *args)
    row = cursor.fetchone()
    while row is not None:
        yield row
        row = cursor.fetchone()


def gen_rows(db, dbname, sourcetable, sourcefields, pid=None,
             pkname=None, tasknum=None, ntasks=None, debuglimit=0):
    """ Generates a series of lists of values, each value corresponding to a
    field in sourcefields.
    """
    args = []
    whereconds = []

    # Restrict to one patient?
    if pid is not None:
        whereconds.append("{}=?".format(
            config.srccfg[dbname].ddgen_per_table_pid_field))
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
    cursor = db.cursor()
    db.db_exec_with_cursor(cursor, sql, *args)
    row = cursor.fetchone()
    db_table_tuple = (dbname, sourcetable)
    while row is not None:
        if (debuglimit > 0 and
                config._rows_inserted_per_table[db_table_tuple] >= debuglimit):
            logger.warning(
                "Table {}.{}: stopping at {} rows due to debugging "
                "limits".format(dbname, sourcetable, debuglimit))
            row = None  # terminate while loop
            continue
        yield list(row)  # convert from tuple to list so we can modify it
        row = cursor.fetchone()
        config._rows_inserted_per_table[db_table_tuple] += 1
    logger.debug("About to close cursor...")
    cursor.close()
    logger.debug("... cursor closed")
    db.java_garbage_collect()  # for testing


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


def gen_pks(db, table, pkname):
    sql = "SELECT {pk} FROM {table}".format(pk=pkname, table=table)
    return db.gen_fetchfirst(sql)


# =============================================================================
# Core functions
# =============================================================================
# - For multithreaded use, the patients are divvied up across the threads.
# - KEY THREADING RULE: ALL THREADS MUST HAVE FULLY INDEPENDENT DATABASE
#   CONNECTIONS.

def process_table(sourcedb, sourcedbname, sourcetable, destdb,
                  pid=None, scrubber=None, incremental=False,
                  pkname=None, tasknum=None, ntasks=None):
    START = "process_table: {}.{}: ".format(sourcedbname, sourcetable)
    logger.debug(START + "pid={}, incremental={}".format(pid, incremental))

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
        # logger.debug("DD row: {}".format(str(ddr)))
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
            logger.info(START + "processing row {} of task set".format(n))
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
            logger.info(START + "Triggering early commit")
            commit(destdb)

    logger.debug(START + "finished: pid={}".format(pid))
    commit(destdb)


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
            if is_fulltext and config.ignore_fulltext_indexes:
                logger.warning(
                    "Skipping FULLTEXT index on {}.{} (disabled by "
                    "config)".format(
                        config.destination_database, table))
                continue
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
    commit(destdb)


def drop_remake(incremental=False):
    recreate_audit_table(config.admindb)
    wipe_and_recreate_mapping_table(config.admindb, incremental=incremental)
    wipe_and_recreate_destination_db(config.destdb, incremental=incremental)
    if incremental:
        for d in config.dd.get_source_databases():
            db = config.sources[d]
            for t in config.dd.get_src_tables(d):
                delete_dest_rows_with_no_src_row(
                    db, d, t, report_every=config.report_every_n_rows)


def process_nonpatient_tables(tasknum=0, ntasks=1, incremental=False):
    logger.info(SEP + "Non-patient tables: (a) with integer PK")
    for (d, t, pkname) in gen_nonpatient_tables_with_int_pk():
        db = config.sources[d]
        logger.info("Processing non-patient table {}.{} (PK: {})...".format(
            d, t, pkname))
        process_table(db, d, t, config.destdb, pid=None, scrubber=None,
                      incremental=incremental,
                      pkname=pkname, tasknum=tasknum, ntasks=ntasks)
        commit(config.destdb)
    logger.info(SEP + "Non-patient tables: (b) without integer PK")
    for (d, t) in gen_nonpatient_tables_without_int_pk(tasknum=tasknum,
                                                       ntasks=ntasks):
        db = config.sources[d]
        logger.info("Processing non-patient table {}.{}...".format(d, t))
        process_table(db, d, t, config.destdb, pid=None, scrubber=None,
                      incremental=incremental,
                      pkname=None, tasknum=None, ntasks=None)
        commit(config.destdb)


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
        for threadnum in xrange(nthreads):
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
    commit(config.destdb)


def show_source_counts():
    logger.info("SOURCE TABLE RECORD COUNTS:")
    for d in config.dd.get_source_databases():
        db = config.sources[d]
        for t in config.dd.get_src_tables(d):
            n = db.count_where(t)
            logger.info("{}.{}: {} records".format(d, t, n))


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
    parser.add_argument("--debugscrubbers", action="store_true",
                        help="Report sensitive scrubbing information, for "
                             "debugging")
    parser.add_argument("--savescrubbers", action="store_true",
                        help="Saves sensitive scrubbing information in admin "
                             "database, for debugging")
    parser.add_argument("--count", action="store_true",
                        help="Count records in source database(s) only")
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
    rnc_db.set_loglevel(logging.DEBUG if args.verbose >= 2 else logging.INFO)

    # Load/validate config
    config.set(filename=args.configfile, load_dd=(not args.draftdd),
               load_destfields=False)
    config.report_every_n_rows = args.report
    config.debug_scrubbers = args.debugscrubbers
    config.save_scrubbers = args.savescrubbers

    if args.draftdd or args.incrementaldd:
        # Note: the difference is that for incrementaldd, the data dictionary
        # will have been loaded from disk; for draftdd, it won't (so a
        # completely fresh one will be generated).
        config.dd.read_from_source_databases(
            default_omit=(not args.makeddpermitbydefaultdangerous))
        print(config.dd.get_tsv())
        return

    if args.count:
        show_source_counts()
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
                               incremental=args.incremental)

    # 4. Indexes. ALWAYS FASTEST TO DO THIS LAST. Process PER TABLE.
    if args.index or everything:
        create_indexes(tasknum=args.process, ntasks=args.nprocesses)

    logger.info(SEP + "Finished")
    end = get_now_utc()
    time_taken = end - start
    logger.info("Time taken: {} seconds".format(time_taken.total_seconds()))


# =============================================================================
# Config instance, as process-local storage
# =============================================================================

config = Config()


# =============================================================================
# Command-line entry point
# =============================================================================

if __name__ == '__main__':
    main()
