#!/usr/bin/python2.7
# -*- encoding: utf8 -*-

"""
Shared functions for anonymiser.py, nlp_manager.py, webview_anon.py

Author: Rudolf Cardinal
Created at: 26 Feb 2015
Last update: 19 Mar 2015

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

import cgi
import csv
import codecs
import ConfigParser
import datetime
import dateutil
import dateutil.tz
import logging
logging.basicConfig()  # just in case nobody else has done this
logger = logging.getLogger("anonymise")
import operator
import os
from sortedcontainers import SortedSet  # sudo pip install sortedcontainers
import pytz
import urllib

from rnc_crypto import MD5Hasher
from rnc_datetime import format_datetime
import rnc_db
from rnc_db import (
    does_sqltype_merit_fulltext_index,
    does_sqltype_require_index_len,
    is_sqltype_binary,
    is_sqltype_date,
    is_sqltype_integer,
    is_sqltype_numeric,
    is_sqltype_text_over_one_char,
    is_sqltype_valid,
    is_valid_field_name,
    is_valid_table_name
)
from rnc_lang import (
    AttrDict,
    convert_attrs_to_bool,
    convert_attrs_to_int_or_none,
    convert_attrs_to_uppercase,
    count_bool,
    raise_if_attr_blank
)
import rnc_log


# =============================================================================
# Constants
# =============================================================================

MAX_PID_STR = "9" * 10  # e.g. NHS numbers are 10-digit
ENCRYPTED_OUTPUT_LENGTH = len(MD5Hasher("dummysalt").hash(MAX_PID_STR))
SQLTYPE_ENCRYPTED_PID = "VARCHAR({})".format(ENCRYPTED_OUTPUT_LENGTH)
# ... in practice: VARCHAR(32)
DATEFORMAT_ISO8601 = "%Y-%m-%dT%H:%M:%S%z"  # e.g. 2013-07-24T20:04:07+0100
DEFAULT_INDEX_LEN = 20  # for data types where it's mandatory
SEP = "=" * 20 + " "
LONGTEXT = "LONGTEXT"

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
    DATE="date"
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
    MASTERPID="M"
)

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
#         "{SCRUBMETHOD.NUMERIC}" here.
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
# Database password security
# -----------------------------------------------------------------------------

# Set this to True. Only set it to False to debug database opening failures,
# under supervision, then set it back to True again afterwards.
open_databases_securely = True

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

# Specify maximum number of errors (insertions, deletions, substitutions) in
# string regex matching. Beware using a high number! Suggest 1-2.

string_max_regex_errors = 1

# Anonymise at word boundaries? True is more conservative; False is more
# liberal and will deal with accidental word concatenation.

anonymise_dates_at_word_boundaries_only = False
anonymise_numbers_at_word_boundaries_only = True
anonymise_strings_at_word_boundaries_only = False

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

# Similarly, used to replace master_pid_fieldname:

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
# Administrative database, containing these tables:
# - secret_map: secret patient ID to research ID mapping.
# - audit: audit trail of various types of access
# User should have WRITE access.
# =============================================================================

[admin_database]

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
force_lower_case = True

#   Allow the absence of patient info? Used to copy databases; WILL NOT
#   ANONYMISE. Boolean; default is False.
allow_no_patient_info = False

#   Specify the (typically integer) patient identifier present in EVERY
#   table. It will be replaced by the research ID in the destination
#   database.
per_table_pid_field = patient_id

#   Master patient ID fieldname. Used for e.g. NHS numbers.
master_pid_fieldname = nhsnum

#   Blacklist any tables when creating new data dictionaries?
table_blacklist =

#   Blacklist any fields (regardless of their table) when creating new data
#   dictionaries?
field_blacklist =

#   Fieldnames assumed to be their table's PK:
possible_pk_fields =

#   Predefine field(s) that define the existence of patient IDs? UNUSUAL.
pid_defining_fieldnames =

#   Default fields to scrub from
scrubsrc_patient_fields =
scrubsrc_thirdparty_fields =

#   Override default scrubbing methods
scrubmethod_date_fields =
scrubmethod_number_fields =

#   Known safe fields, exempt from scrubbing
safe_fields_exempt_from_scrubbing =

#   Other default manipulations
truncate_date_fields =

#   Fields containing filenames, which files should be converted to text
filename_to_text_fields =

#   Fields containing raw binary data from files (binary large objects; BLOBs),
#   whose contents should be converted to text -- paired with fields in the
#   same table containing their file extension (e.g. "pdf", ".PDF") or a
#   filename having that extension.
#   Specify it as a list of comma-joined pairs, e.g.
#       binary_to_text_field_pairs = binary1field, ext1field
#           binary2field, ext2field
#           ...
binary_to_text_field_pairs =

[mysourcedb2]

engine = mysql
host = localhost
port = 3306
user = XXX
password = XXX
db = XXX

force_lower_case = True
per_table_pid_field = patient_id
master_pid_fieldname = nhsnum
table_blacklist =
field_blacklist =
possible_pk_fields =
scrubsrc_patient_fields =
scrubsrc_thirdparty_fields =
scrubmethod_date_fields =
scrubmethod_number_fields =
safe_fields_exempt_from_scrubbing =
truncate_date_fields =
filename_to_text_fields =
binary_to_text_field_pairs =

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
force_lower_case = True
per_table_pid_field = _patient_idnum1
pid_defining_fieldnames = _patient_idnum1
master_pid_fieldname = _patient_idnum2

table_blacklist =

field_blacklist = _patient_iddesc1
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

possible_pk_fields = _pk

scrubsrc_patient_fields = _patient_forename
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

scrubsrc_thirdparty_fields =

scrubmethod_date_fields = _patient_dob

scrubmethod_number_fields =

safe_fields_exempt_from_scrubbing = _device
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

truncate_date_fields = _patient_dob
filename_to_text_fields =
binary_to_text_field_pairs =

""".format(
    SQLTYPE_ENCRYPTED_PID=SQLTYPE_ENCRYPTED_PID,
    SCRUBSRC=SCRUBSRC,
    INDEX=INDEX,
    SCRUBMETHOD=SCRUBMETHOD,
    ALTERMETHOD=ALTERMETHOD,
    SRCFLAG=SRCFLAG,
    LONGTEXT=LONGTEXT,
)

# For the style:
#       [source_databases]
#       source1 = blah
#       source2 = thing
# ... you can't have multiple keys with the same name.
# http://stackoverflow.com/questions/287757


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
        convert_attrs_to_int_or_none(self, [
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

        self.src_flags = ""
        if self.src_field in cfg.possible_pk_fields:
            self.src_flags += SRCFLAG.PK
            self.src_flags += SRCFLAG.ADDSRCHASH
        if self.src_field == cfg.per_table_pid_field:
            self.src_flags += SRCFLAG.PRIMARYPID
        if self.src_field == cfg.master_pid_fieldname:
            self.src_flags += SRCFLAG.MASTERPID
        if self.src_field in cfg.pid_defining_fieldnames:  # unusual!
            self.src_flags += SRCFLAG.DEFINESPRIMARYPIDS

        if self.src_field in cfg.scrubsrc_patient_fields:
            self.scrub_src = SCRUBSRC.PATIENT
        elif self.src_field in cfg.scrubsrc_thirdparty_fields:
            self.scrub_src = SCRUBSRC.THIRDPARTY
        else:
            self.scrub_src = ""

        if not self.scrub_src:
            self.scrub_method = ""
        elif (is_sqltype_numeric(datatype_full)
                or self.src_field == cfg.per_table_pid_field
                or self.src_field == cfg.master_pid_fieldname
                or self.src_field in cfg.scrubmethod_number_fields):
            self.scrub_method = SCRUBMETHOD.NUMERIC
        elif (is_sqltype_date(datatype_full)
              or self.src_field in cfg.scrubmethod_date_fields):
            self.scrub_method = SCRUBMETHOD.DATE
        else:
            self.scrub_method = SCRUBMETHOD.TEXT

        self.omit = (
            (default_omit or bool(self.scrub_src))
            and not (SRCFLAG.PK in self.src_flags)
            and not (SRCFLAG.PRIMARYPID in self.src_flags)
            and not (SRCFLAG.MASTERPID in self.src_flags)
        )

        if SRCFLAG.PRIMARYPID in self.src_flags:
            self.dest_field = config.research_id_fieldname
        elif SRCFLAG.MASTERPID in self.src_flags:
            self.dest_field = config.master_research_id_fieldname
        else:
            self.dest_field = field

        self.dest_datatype = (
            SQLTYPE_ENCRYPTED_PID
            if (SRCFLAG.PRIMARYPID in self.src_flags
                or SRCFLAG.MASTERPID in self.src_flags)
            else rnc_db.full_datatype_to_mysql(datatype_full))

        if self.src_field in cfg.truncate_date_fields:
            self._truncate_date = True
        elif self.src_field in cfg.filename_to_text_fields:
            self._extract_text = True
            self._extract_from_filename = True
            self.dest_datatype = LONGTEXT
            if not self.src_field in cfg.safe_fields_exempt_from_scrubbing:
                self._scrub = True
        elif self.src_field in cfg.bin2text_dict.keys():
            self._extract_text = True
            self._extract_from_filename = False
            self._extract_ext_field = cfg.bin2text_dict[self.src_field]
            self.dest_datatype = LONGTEXT
            if not self.src_field in cfg.safe_fields_exempt_from_scrubbing:
                self._scrub = True
        elif (is_sqltype_text_over_one_char(datatype_full)
                and not self.omit
                and not SRCFLAG.PRIMARYPID in self.src_flags
                and not SRCFLAG.MASTERPID in self.src_flags
                and not self.src_field in
                cfg.safe_fields_exempt_from_scrubbing):
            self._scrub = True

        self.dest_table = table

        if SRCFLAG.PK in self.src_flags:
            self.index = INDEX.UNIQUE
        elif self.dest_field == config.research_id_fieldname:
            self.index = INDEX.NORMAL
        elif does_sqltype_merit_fulltext_index(self.dest_datatype):
            self.index = INDEX.FULLTEXT
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

        if (self.src_field == srccfg.per_table_pid_field
                and not is_sqltype_integer(self.src_datatype)):
            raise ValueError(
                "All fields with src_field = {} should be integer, for work "
                "distribution purposes".format(self.src_field))

        if (SRCFLAG.DEFINESPRIMARYPIDS in self.src_flags
                and not SRCFLAG.PRIMARYPID in self.src_flags):
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

        valid_scrubmethods = [SCRUBMETHOD.DATE, SCRUBMETHOD.NUMERIC,
                              SCRUBMETHOD.TEXT, ""]
        if self.scrub_src and self.scrub_method not in valid_scrubmethods:
            raise ValueError(
                "Invalid scrub_method - must be one of [{}]".format(
                    ",".join(valid_scrubmethods)))

        if not self.omit:
            ensure_valid_table_name(self.dest_table)
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
            if self.src_field == srccfg.per_table_pid_field:
                if not SRCFLAG.PRIMARYPID in self.src_flags:
                    raise ValueError(
                        "All fields with src_field={} used in output should "
                        "have src_flag={} set".format(self.src_field,
                                                      SRCFLAG.PRIMARYPID))
                if self.dest_field != config.research_id_fieldname:
                    raise ValueError(
                        "Primary PID field should have "
                        "dest_field = {}".format(
                            config.research_id_fieldname))
            if (self.src_field == srccfg.master_pid_fieldname
                    and not SRCFLAG.MASTERPID in self.src_flags):
                raise ValueError(
                    "All fields with src_field = {} used in output should have"
                    " src_flags={} set".format(srccfg.master_pid_fieldname,
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


class DataDictionary(object):
    def __init__(self):
        self.rows = []

    def read_from_file(self, filename, check_against_source_db=True):
        self.rows = []
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
            if db.db_flavour == rnc_db.DatabaseSupporter.FLAVOUR_MYSQL:
                sql = """
                    SELECT table_name, column_name, data_type, column_type,
                        column_comment
                    FROM information_schema.columns
                    WHERE table_schema=?
                """
            else:
                sql = """
                    SELECT table_name, column_name, data_type, {}, NULL
                    FROM information_schema.columns
                    WHERE table_schema=?
                """.format(rnc_db.DatabaseSupporter.SQLSERVER_COLUMN_TYPE_EXPR)
            args = [schema]
            i = 0
            signatures = []
            for r in db.gen_fetchall(sql, *args):
                i += 1
                if report_every and i % report_every == 0:
                    logger.debug("... reading source field {}".format(i))
                t = r[0]
                if cfg.force_lower_case:
                    t = t.lower()
                if t in cfg.table_blacklist:
                    continue
                f = r[1]
                if cfg.force_lower_case:
                    f = f.lower()
                if f in cfg.field_blacklist:
                    continue
                datatype_short = r[2].upper()
                datatype_full = r[3].upper()
                c = r[4]
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
        self.rows = sorted(
            self.rows,
            key=operator.attrgetter(
                "src_db",
                "src_table",
                "src_field"))
        logger.info("... done")

    def cache_stuff(self):
        logger.debug("Caching data dictionary information...")
        self.cached_dest_tables = SortedSet()
        self.cached_source_databases = SortedSet()
        self.cached_srcdb_table_pairs = SortedSet()
        self.cached_srcdb_table_pairs_w_pt_info = SortedSet()  # w = with
        self.cached_scrub_from_rows = []
        self.cached_src_tables = {}
        self.cached_src_tables_w_pt_info = {}  # w = with
        src_tables_with_dest = {}
        self.cached_pt_src_tables_w_dest = {}
        self.cached_rows_for_src_table = {}
        self.cached_rows_for_dest_table = {}
        self.cached_fieldnames_for_src_table = {}
        self.cached_src_dbtables_for_dest_table = {}
        self.cached_srchash_info = {}
        self.cached_has_active_destination = {}
        self.cached_dest_tables_for_src_db_table = {}
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
            if db_t_key not in self.cached_srchash_info:
                self.cached_srchash_info[db_t_key] = (
                    None, False, ddr.dest_table, None
                )

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
                self.cached_scrub_from_rows.append(ddr)
                # ... even if omit flag set

            # Is it a src_pk row, contributing to src_hash info?
            if SRCFLAG.PK in ddr.src_flags:
                self.cached_srchash_info[db_t_key] = (
                    ddr.src_field,
                    SRCFLAG.ADDSRCHASH in ddr.src_flags,
                    ddr.dest_table,
                    ddr.dest_field
                )

            # Is it a relevant contribution from a source table?
            pt_info = bool(ddr.scrub_src)
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

        # A subtraction...
        self.cached_srcdb_table_pairs_wo_pt_info = sorted(
            self.cached_srcdb_table_pairs
            - self.cached_srcdb_table_pairs_w_pt_info
        )

        # An intersection, and some sorting/conversion to lists
        for s in self.cached_source_databases:
            self.cached_pt_src_tables_w_dest[s] = sorted(
                self.cached_src_tables_w_pt_info[s]
                & src_tables_with_dest[s]  # & is intersection
            )

    def check_valid(self, check_against_source_db):
        logger.info("Checking data dictionary...")
        if not self.rows:
            raise ValueError("Empty data dictionary")
        if not self.cached_dest_tables:
            raise ValueError("Empty data dictionary after removing "
                             "redundant tables")

        # Individual rows will already have been checked
        #for r in self.rows:
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
                        if not config.srccfg[d].per_table_pid_field \
                                in fieldnames:
                            raise ValueError(
                                "Source table {d}.{t} has a scrub_in or "
                                "src_flags={f} field but no {p} field".format(
                                    d=d,
                                    t=t,
                                    f=SRCFLAG.MASTERPID,
                                    p=config.srccfg[d].per_table_pid_field,
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

        logger.debug("Checking DD: global checks...")
        self.n_definers = sum(
            [1 if SRCFLAG.DEFINESPRIMARYPIDS in x.src_flags else 0
             for x in self.rows])
        if self.n_definers == 0:
            if all([x.allow_no_patient_info
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

    def get_scrub_from_rows(self):
        return self.cached_scrub_from_rows

    def get_tsv(self):
        return "\n".join(
            ["\t".join(DataDictionaryRow.ROWNAMES)]
            + [r.get_tsv() for r in self.rows]
        )

    def get_src_dbs_tables_with_no_patient_info(self):
        return self.cached_srcdb_table_pairs_wo_pt_info

    def get_srchash_info(self, src_db, src_table):
        return self.cached_srchash_info[(src_db, src_table)]

    def has_active_destination(self, src_db, src_table):
        return self.cached_has_active_destination[(src_db, src_table)]


# =============================================================================
# Config/databases
# =============================================================================

def read_config_string_options(obj, parser, section, options,
                               enforce_str=False):
    if not parser.has_section(section):
        raise ValueError("config missing section: " + section)
    for o in options:
        if parser.has_option(section, o):
            value = parser.get(section, o)
            setattr(obj, o, str(value) if enforce_str else value)
        else:
            setattr(obj, o, None)


def read_config_multiline_options(obj, parser, section, options):
    if not parser.has_section(section):
        raise ValueError("config missing section: " + section)
    for o in options:
        if parser.has_option(section, o):
            multiline = parser.get(section, o)
            values = [x.strip() for x in multiline.splitlines() if x.strip()]
            setattr(obj, o, values)
        else:
            setattr(obj, o, [])


class DatabaseSafeConfig(object):
    def __init__(self, parser, section):
        read_config_string_options(self, parser, section, [
            "force_lower_case",
            "allow_no_patient_info",
            "per_table_pid_field",
            "master_pid_fieldname",
        ])
        read_config_multiline_options(self, parser, section, [
            "possible_pk_fields",
            "pid_defining_fieldnames",
            "table_blacklist",
            "field_blacklist",
            "scrubsrc_patient_fields",
            "scrubsrc_thirdparty_fields",
            "scrubmethod_date_fields",
            "scrubmethod_number_fields",
            "safe_fields_exempt_from_scrubbing",
            "truncate_date_fields",
            "filename_to_text_fields",
            "binary_to_text_field_pairs",
        ])
        convert_attrs_to_bool(self, [
            "force_lower_case",
        ], default=True)
        convert_attrs_to_bool(self, [
            "allow_no_patient_info",
        ], default=False)
        self.bin2text_dict = {}
        for pair in self.binary_to_text_field_pairs:
            items = [item.strip() for item in pair.split(",")]
            if len(items) != 2:
                raise ValueError(
                    "binary_to_text_field_pairs: specify fields in pairs")
            self.bin2text_dict[items[0]] = items[1]


def ensure_valid_field_name(f):
    if not is_valid_field_name(f):
        raise ValueError("Field name invalid: {}".format(f))


def ensure_valid_table_name(f):
    if not is_valid_table_name(f):
        raise ValueError("Table name invalid: {}".format(f))


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
        "master_pid_fieldname",
        "per_table_patient_id_encryption_phrase",
        "master_patient_id_encryption_phrase",
        "change_detection_encryption_phrase",
        "replace_patient_info_with",
        "replace_third_party_info_with",
        "string_max_regex_errors",
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
    ]
    MAIN_MULTILINE_HEADINGS = [
        "scrub_string_suffixes",
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
        parser = ConfigParser.RawConfigParser()
        parser.readfp(codecs.open(self.config_filename, "r", "utf8"))
        read_config_string_options(self, parser, "main", Config.MAIN_HEADINGS)
        read_config_multiline_options(self, parser, "main",
                                      Config.MAIN_MULTILINE_HEADINGS)
        # Processing of parameters
        self.string_max_regex_errors = int(self.string_max_regex_errors)
        convert_attrs_to_bool(self, [
            "anonymise_dates_at_word_boundaries_only",
            "anonymise_numbers_at_word_boundaries_only",
            "anonymise_strings_at_word_boundaries_only",
            "append_source_info_to_comment",
            "open_databases_securely",
        ])

        # Databases
        self.destdb = self.get_database("destination_database")
        self.admindb = self.get_database("admin_database")
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
            if not cfg.allow_no_patient_info:
                if not cfg.per_table_pid_field:
                    raise ValueError(
                        "Missing per_table_pid_field in config for database "
                        "{}".format(dbname))
                ensure_valid_field_name(cfg.per_table_pid_field)
                if cfg.per_table_pid_field == self.source_hash_fieldname:
                    raise ValueError("Config: per_table_pid_field can't be the"
                                     " same as source_hash_fieldname")
            if cfg.master_pid_fieldname:
                ensure_valid_field_name(cfg.master_pid_fieldname)

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
# Config instance, as process-local storage
# =============================================================================

config = Config()


# =============================================================================
# Logger manipulation
# =============================================================================

def reset_logformat(logger, name="", debug=False):
    # logging.basicConfig() won't reset the formatter if another module
    # has called it, so always set the formatter like this.
    if name:
        namebit = name + ":"
    else:
        namebit = ""
    fmt = "%(levelname)s:%(name)s:" + namebit + "%(message)s"
    rnc_log.reset_logformat(logger, fmt=fmt)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)


# =============================================================================
# Audit
# =============================================================================

AUDIT_TABLE = "audit"
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
        """.format(table=AUDIT_TABLE),
        config.NOW_UTC_NO_TZ,  # when_access_utc
        source,
        remote_addr,
        user,
        query,
        details
    )
