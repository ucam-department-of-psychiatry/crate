#!/usr/bin/env python3
# crate/anonymise/anon_config.py

"""
Config class for CRATE anonymiser.

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

# =============================================================================
# Imports
# =============================================================================

import cgi
import codecs
import configparser
import datetime
import dateutil
import dateutil.tz
import logging
log = logging.getLogger(__name__)
import os
import pytz
import urllib

from cardinal_pythonlib.rnc_config import (
    read_config_multiline_options,
    read_config_string_options,
)
from cardinal_pythonlib.rnc_datetime import (
    format_datetime,
)
import cardinal_pythonlib.rnc_db as rnc_db
from cardinal_pythonlib.rnc_db import (
    ensure_valid_field_name,
    ensure_valid_table_name,
)
from cardinal_pythonlib.rnc_lang import (
    convert_attrs_to_bool,
    convert_attrs_to_int,
)

from crate.anonymise.constants import (
    ALTERMETHOD,
    MAX_PID_STR,
    INDEX,
    LONGTEXT,
    SCRUBMETHOD,
    SCRUBSRC,
    SEP,
    SRCFLAG,
)
from crate.anonymise.dd import DataDictionary
from crate.anonymise.hash import (
    # MD5Hasher,
    # SHA256Hasher,
    # SHA512Hasher,
    HmacMD5Hasher,
    HmacSHA256Hasher,
    HmacSHA512Hasher,
)
from crate.anonymise.scrub import (
    NonspecificScrubber,
    WordList,
)

# =============================================================================
# Constants
# =============================================================================

DATEFORMAT_ISO8601 = "%Y-%m-%dT%H:%M:%S%z"  # e.g. 2013-07-24T20:04:07+0100
DEFAULT_MAX_ROWS_BEFORE_COMMIT = 1000
DEFAULT_MAX_BYTES_BEFORE_COMMIT = 80 * 1024 * 1024

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
#             (scrub_src). The field is of type VARCHAR and its length is
#             determined by the hash_method parameter (see below).
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
#               primary ID (database patient primary key) in the destination,
#               and a transient research ID (TRID) also added.
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
#       - "{SCRUBMETHOD.WORDS}": treat as a set of textual words
#         This is the default for all textual fields (e. CHAR, VARCHAR, TEXT).
#         Typically used for names.
#       - "{SCRUBMETHOD.PHRASE}": treat as a textual phrase (a sequence of
#         words to be replaced only when they occur in sequence). Typically
#         used for address components.
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

# PID-to-RID hashing method. Options are:
#   MD5 - DEPRECATED - produces a 32-character digest; cryptographically poor
#   SHA256 - DEPRECATED - produces a 64-character digest
#   SHA512 - DEPRECATED - produces a 128-character digest
#   HMAC_MD5 - produces a 32-character digest
#   HMAC_SHA256 - produces a 64-character digest (default)
#   HMAC_SHA512 - produces a 64-character digest

***

hash_method = HMAC_SHA256

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

# Things to be removed irrespective of patient-specific information will be
# replaced by this (for example, if you opt to remove all things looking like
# telephone numbers). For example, ZZZ or [~~~].

replace_nonspecific_info_with = [~~~]

# Strings to append to every "scrub from" string.
# For example, include "s" if you want to scrub "Roberts" whenever you scrub
# "Robert".
# Applies to {SCRUBMETHOD.WORDS}, but not to {SCRUBMETHOD.PHRASE}.
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

# WHITELIST.
# Are there any words not to scrub? For example, "the", "road", "street" often
# appear in addresses, but you might not want them removed. Be careful in case
# these could be names (e.g. "Lane").
# Specify these as a list of FILENAMES, where the filenames contain words; e.g.
#
# whitelist_filenames = /some/path/short_english_words.txt
#
# Here's a suggestion for some of the sorts of words you might include:
#     am
#     an
#     as
#     at
#     bd
#     by
#     he
#     if
#     is
#     it
#     me
#     mg
#     od
#     of
#     on
#     or
#     re
#     so
#     to
#     us
#     we
#     her
#     him
#     tds
#     she
#     the
#     you
#     road
#     street

whitelist_filenames =

# BLACKLIST
# Are there any words you always want to remove?
# Specify these as a list of filenames, e.g
#
# blacklist_filenames = /some/path/boy_names.txt
#     /some/path/girl_names.txt
#     /some/path/common_surnames.txt

blacklist_filenames =

# Nonspecific scrubbing of numbers of a certain length?
# For example, scrubbing all 11-digit numbers will remove modern UK telephone
# numbers in conventional format. To do this, specify
# scrub_all_numbers_of_n_digits = 11. You could scrub both 10- and 11-digit
# numbers by specifying both numbers (in multiline format, as above); 10-digit
# numbers would include all NHS numbers. Avoid using this for short numbers;
# you may lose valuable numeric data!

scrub_all_numbers_of_n_digits =

# Nonspecific scrubbing of UK postcodes?
# See https://www.mrs.org.uk/pdf/postcodeformat.pdf ; these can look like
# FORMAT    EXAMPLE
# AN NAA    M1 1AA
# ANN NAA   M60 1NW
# AAN NAA   CR2 6XH
# AANN NAA  DN55 1PT
# ANA NAA   W1A 1HQ
# AANA NAA  EC1A 1BB

scrub_all_uk_postcodes = False

# Anonymise at word boundaries? True is more conservative; False is more
# liberal and will deal with accidental word concatenation. With ID numbers,
# beware if you use a prefix, e.g. people write 'M123456' or 'R123456'; in that
# case you will need anonymise_numbers_at_word_boundaries_only = False.

anonymise_codes_at_word_boundaries_only = True
# ... applies to {SCRUBMETHOD.CODE}
anonymise_dates_at_word_boundaries_only = True
# ... applies to {SCRUBMETHOD.DATE}
anonymise_numbers_at_word_boundaries_only = False
# ... applies to {SCRUBMETHOD.NUMERIC}
anonymise_strings_at_word_boundaries_only = True
# ... applies to {SCRUBMETHOD.WORDS} and {SCRUBMETHOD.PHRASE}

# -----------------------------------------------------------------------------
# Output fields and formatting
# -----------------------------------------------------------------------------

# Name used for the primary patient ID in the mapping table.

mapping_patient_id_fieldname = patient_id

# Research ID field name. This will be a VARCHAR of length determined by
# hash_method. Used to replace per_table_patient_id_field.

research_id_fieldname = brcid

# Transient integer research ID (TRID) fieldname.
# An unsigned integer field with this name will be added to every table
# containing a primary patient ID (in the source) or research ID (in the
# destination).

trid_fieldname = trid

# Name used for the master patient ID in the mapping table.

mapping_master_id_fieldname = nhsnum

# Similarly, used to replace ddgen_master_pid_fieldname:

master_research_id_fieldname = nhshash

# Change-detection hash fieldname. This will be a VARCHAR of length determined
# by hash_method.

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

# -----------------------------------------------------------------------------
# Admin database configuration
# See the [admin_database] section for connection details.
# -----------------------------------------------------------------------------

# Table name to use for the secret patient ID to research ID mapping.
# Usually no need to change the default.

secret_map_tablename = secret_map

# Table name to use for the transient research ID cache (also secret).
# Usually no need to change the default.

secret_trid_cache_tablename = secret_trid_cache

# Table name to use for the audit trail of various types of access.
# Usually no need to change the default.

audit_tablename = audit

# Table name to use for the opt-out list of patient PKs.
# Usually no need to change the default.

opt_out_tablename = opt_out

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

# -----------------------------------------------------------------------------
# PROCESSING OPTIONS, TO LIMIT DATA QUANTITY FOR TESTING
# -----------------------------------------------------------------------------

#   Limit the number of patients to be processed? Specify 0 (the default) for
#   no limit.
debug_max_n_patients =

#   Specify a list of integer patient IDs, for debugging? If specified, this
#   list will be used directly (overriding the patient ID source specified in
#   the data dictionary, and overriding debug_max_n_patients).
debug_pid_list =


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
#       mysql [default for mysql engine]
#       odbc [default otherwise]
#       jdbc
#   - host, port, db [for mysql, JDBC]
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

#   Convert spaces in table/fieldnames (yuk!) to underscores? Default: true.
ddgen_convert_odd_chars_to_underscore = True

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
ddgen_scrubmethod_phrase_fields =

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

#   Allow full-text index creation? Default true. Disable for databases that
#   don't support them?
ddgen_allow_fulltext_indexing = True

# PROCESSING OPTIONS, TO LIMIT DATA QUANTITY FOR TESTING

#   Specify 0 (the default) for no limit, or a number of rows (e.g. 1000) to
#   apply to any tables listed in debug_limited_tables. For those tables, only
#   this many rows will be taken from the source database. Use this, for
#   example, to reduce the number of large documents fetched.
#   If you run a multiprocess/multithreaded anonymisation, this limit applies
#   per *process* (or task), not overall.
#   Note that these limits DO NOT APPLY to the fetching of patient identifiable
#   information for anonymisation -- when a patient is processed, all
#   identifiable information for that patient is trawled.
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
ddgen_scrubmethod_phrase_fields =
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
ddgen_scrubmethod_phrase_fields =

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
# DestinationFieldInfo
# =============================================================================

class DestinationFieldInfo(object):
    """Class representing information about a destination field."""

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
# Config/databases
# =============================================================================

class DatabaseSafeConfig(object):
    """Class representing non-sensitive configuration information about a
    source database."""

    def __init__(self, parser, section):
        """Read from a configparser section."""
        read_config_string_options(self, parser, section, [
            "ddgen_force_lower_case",
            "ddgen_convert_odd_chars_to_underscore",
            "ddgen_allow_no_patient_info",
            "ddgen_per_table_pid_field",
            "ddgen_master_pid_fieldname",
            "ddgen_constant_content",
            "ddgen_addition_only",
            "ddgen_min_length_for_scrubbing",
            "ddgen_allow_fulltext_indexing",
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
            "ddgen_scrubmethod_phrase_fields",
            "ddgen_safe_fields_exempt_from_scrubbing",
            "ddgen_truncate_date_fields",
            "ddgen_filename_to_text_fields",
            "ddgen_binary_to_text_field_pairs",
            "ddgen_index_fields",
            "debug_limited_tables",
        ])
        convert_attrs_to_bool(self, [
            "ddgen_force_lower_case",
            "ddgen_convert_odd_chars_to_underscore",
            "ddgen_allow_fulltext_indexing",
        ], default=True)
        convert_attrs_to_bool(self, [
            "ddgen_allow_no_patient_info",
            "ddgen_constant_content",
            "ddgen_addition_only",
        ], default=False)
        convert_attrs_to_int(self, [
            "debug_row_limit",
            "ddgen_min_length_for_scrubbing",
        ], default=0)
        self.bin2text_dict = {}
        for pair in self.ddgen_binary_to_text_field_pairs:
            items = [item.strip() for item in pair.split(",")]
            if len(items) != 2:
                raise ValueError("ddgen_binary_to_text_field_pairs: specify "
                                 "fields in pairs")
            self.bin2text_dict[items[0]] = items[1]


# =============================================================================
# Config
# =============================================================================

class Config(object):
    """Class representing the main configuration."""

    MAIN_HEADINGS = [
        "data_dictionary_filename",
        "hash_method",
        "ddgen_master_pid_fieldname",
        "per_table_patient_id_encryption_phrase",
        "master_patient_id_encryption_phrase",
        "change_detection_encryption_phrase",
        "replace_patient_info_with",
        "replace_third_party_info_with",
        "replace_nonspecific_info_with",
        "string_max_regex_errors",
        "min_string_length_for_errors",
        "min_string_length_to_scrub_with",
        "scrub_all_uk_postcodes",
        "anonymise_codes_at_word_boundaries_only",
        "anonymise_dates_at_word_boundaries_only",
        "anonymise_numbers_at_word_boundaries_only",
        "anonymise_strings_at_word_boundaries_only",
        "mapping_patient_id_fieldname",
        "research_id_fieldname",
        "trid_fieldname",
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
        "secret_map_tablename",
        "secret_trid_cache_tablename",
        "audit_tablename",
        "opt_out_tablename",
        "destination_database",
        "admin_database",
        "debug_max_n_patients",
    ]
    MAIN_MULTILINE_HEADINGS = [
        "scrub_string_suffixes",
        "whitelist_filenames",
        "blacklist_filenames",
        "scrub_all_numbers_of_n_digits",
        "source_databases",
        "debug_pid_list",
    ]

    def __init__(self):
        """Set some defaults."""
        self.config_filename = None
        self.dd = None
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
        self._warned_re_limits = {}
        self.re_nonspecific = None

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
        """Set up process-local storage. Read from config unless we've done
        that already in a previous WSGI incarnation."""
        self.set_always()
        if self.PERSISTENT_CONSTANTS_INITIALIZED:
            self.init_row_counts()
            return
        log.info(SEP + "Loading config: {}".format(filename))
        if filename and environ:
            raise ValueError("Config.set(): mis-called")
        if environ:
            self.read_environ(environ)
        else:
            self.read_environ(os.environ)
            self.config_filename = filename
        self.read_config(include_sources=include_sources)
        self.check_valid(include_sources=include_sources)
        self.dd = DataDictionary(self)
        if load_dd:
            log.info(SEP + "Loading data dictionary: {}".format(
                self.data_dictionary_filename))
            self.dd.read_from_file(self.data_dictionary_filename)
            self.dd.check_valid(check_against_source_db=include_sources,
                                prohibited_fieldnames=[
                                    self.source_hash_fieldname,
                                    self.trid_fieldname,
                                ])
        self.init_row_counts()
        self.PERSISTENT_CONSTANTS_INITIALIZED = True

    def set_always(self):
        """Set the things we set every time the script is invoked via WSGI
        (such as the current time, and some counters)."""
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
        """Initialize row counts for all source tables."""
        self._rows_inserted_per_table = {}
        for db_table_tuple in self.dd.get_src_db_tablepairs():
            self._rows_inserted_per_table[db_table_tuple] = 0
            self._warned_re_limits[db_table_tuple] = False

    def read_environ(self, environ):
        """Read from the WSGI environment."""
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
        url += urllib.parse.quote(environ.get("SCRIPT_NAME", ""))
        url += urllib.parse.quote(environ.get("PATH_INFO", ""))
        # But not the query string:
        # if environ.get("QUERY_STRING"):
        #    url += "?" + environ.get("QUERY_STRING")
        self.SCRIPT_PUBLIC_URL_ESCAPED = cgi.escape(url)

    def read_config(self, include_sources=False):
        """Read config from file."""
        log.debug("Opening config: {}".format(self.config_filename))
        parser = configparser.RawConfigParser()
        parser.readfp(codecs.open(self.config_filename, "r", "utf8"))
        read_config_string_options(self, parser, "main", Config.MAIN_HEADINGS)
        read_config_multiline_options(self, parser, "main",
                                      Config.MAIN_MULTILINE_HEADINGS)
        # Processing of parameters
        convert_attrs_to_bool(self, [
            "scrub_all_uk_postcodes",
            "anonymise_codes_at_word_boundaries_only",
            "anonymise_dates_at_word_boundaries_only",
            "anonymise_numbers_at_word_boundaries_only",
            "anonymise_strings_at_word_boundaries_only",
            "append_source_info_to_comment",
            "open_databases_securely",
        ])
        convert_attrs_to_int(self, [
            "string_max_regex_errors",
            "min_string_length_for_errors",
            "min_string_length_to_scrub_with",
            "max_rows_before_commit",
            "max_bytes_before_commit",
        ])
        convert_attrs_to_int(self, [
            "debug_max_n_patients",
        ], default=0)

        # These should all be integers:
        self.scrub_all_numbers_of_n_digits = [
            int(x) for x in self.scrub_all_numbers_of_n_digits if int(x) > 0]
        self.debug_pid_list = self.debug_pid_list or []  # replace None
        self.debug_pid_list = [int(x) for x in self.debug_pid_list if x]

        # Databases
        if self.destination_database == self.admin_database:
            raise ValueError(
                "Destination and admin databases mustn't be the same")
        self.destdb = self.get_database(self.destination_database)
        self.admindb = self.get_database(self.admin_database)
        self.sources = {}
        self.srccfg = {}
        self.src_db_names = []
        for sourcedb_name in self.source_databases:
            if (sourcedb_name == self.destination_database
                    or sourcedb_name == self.admin_database):
                raise ValueError("Source database can't be the same as "
                                 "destination or admin database")
            self.src_db_names.append(sourcedb_name)
            self.srccfg[sourcedb_name] = DatabaseSafeConfig(
                parser, sourcedb_name)
            if include_sources:
                self.sources[sourcedb_name] = self.get_database(sourcedb_name)

        # Load encryption keys and create hashers
        assert self.hash_method not in ["MD5", "SHA256", "SHA512"], (
            "Non-HMAC hashers are deprecated for security reasons. You have: "
            "{}".format(self.hash_method))
        if self.hash_method == "HMAC_MD5":
            HashClass = HmacMD5Hasher
        elif self.hash_method == "HMAC_SHA256" or not self.hash_method:
            HashClass = HmacSHA256Hasher
        elif self.hash_method == "HMAC_SHA512":
            HashClass = HmacSHA512Hasher
        else:
            raise ValueError("Unknown value for hash_method")
        encrypted_length = len(HashClass("dummysalt").hash(MAX_PID_STR))
        self.SQLTYPE_ENCRYPTED_PID = "VARCHAR({})".format(encrypted_length)
        # ... VARCHAR(32) for MD5; VARCHAR(64) for SHA-256; VARCHAR(128) for
        # SHA-512.

        if not self.per_table_patient_id_encryption_phrase:
            raise ValueError("Missing per_table_patient_id_encryption_phrase")
        self.primary_pid_hasher = HashClass(
            self.per_table_patient_id_encryption_phrase)

        if not self.master_patient_id_encryption_phrase:
            raise ValueError("Missing master_patient_id_encryption_phrase")
        self.master_pid_hasher = HashClass(
            self.master_patient_id_encryption_phrase)

        if not self.change_detection_encryption_phrase:
            raise ValueError("Missing change_detection_encryption_phrase")
        self.change_detection_hasher = HashClass(
            self.change_detection_encryption_phrase)

        # Whitelist, blacklist, nonspecific scrubber
        self.whitelist = WordList(
            filenames=self.whitelist_filenames,
            hasher=self.change_detection_hasher,
        )
        self.blacklist = WordList(
            filenames=self.blacklist_filenames,
            replacement_text=self.replace_nonspecific_info_with,
            hasher=self.change_detection_hasher,
            at_word_boundaries_only=(
                self.anonymise_strings_at_word_boundaries_only),
            max_errors=0,
        )
        self.nonspecific_scrubber = NonspecificScrubber(
            replacement_text=self.replace_nonspecific_info_with,
            hasher=self.change_detection_hasher,
            anonymise_codes_at_word_boundaries_only=(
                self.anonymise_codes_at_word_boundaries_only),
            anonymise_numbers_at_word_boundaries_only=(
                self.anonymise_numbers_at_word_boundaries_only),
            blacklist=self.blacklist,
            scrub_all_numbers_of_n_digits=self.scrub_all_numbers_of_n_digits,
            scrub_all_uk_postcodes=self.scrub_all_uk_postcodes,
        )

    def get_database(self, section):
        """Return an rnc_db database object from information in a section of
        the config file (a section that will contain password and other
        connection information)."""
        parser = configparser.RawConfigParser()
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
        ensure_valid_table_name(self.temporary_tablename)
        if not self.secret_map_tablename:
            raise ValueError("No secret_map_tablename specified.")
        ensure_valid_table_name(self.secret_map_tablename)
        if not self.secret_trid_cache_tablename:
            raise ValueError("No secret_trid_cache_tablename specified.")
        ensure_valid_table_name(self.secret_trid_cache_tablename)
        if not self.audit_tablename:
            raise ValueError("No audit_tablename specified.")
        ensure_valid_table_name(self.audit_tablename)
        if not self.opt_out_tablename:
            raise ValueError("No opt_out_tablename specified.")
        ensure_valid_table_name(self.opt_out_tablename)

        # Test field names
        def validate_fieldattr(name):
            if not getattr(self, name):
                raise ValueError("Blank fieldname: " + name)
            ensure_valid_field_name(getattr(self, name))

        specialfieldlist = [
            "mapping_patient_id_fieldname",
            "research_id_fieldname",
            "trid_fieldname",
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
        if not self.replace_nonspecific_info_with:
            raise ValueError("Blank replace_nonspecific_info_with")
        replacements = list(set([self.replace_patient_info_with,
                                 self.replace_third_party_info_with,
                                 self.replace_nonspecific_info_with]))
        if len(replacements) != 3:
            raise ValueError(
                "Inadvisable: replace_patient_info_with, "
                "replace_third_party_info_with, and "
                "replace_nonspecific_info_with should all be distinct")

        # Regex
        if self.string_max_regex_errors < 0:
            raise ValueError("string_max_regex_errors < 0, nonsensical")
        if self.min_string_length_for_errors < 1:
            raise ValueError("min_string_length_for_errors < 1, nonsensical")
        if self.min_string_length_to_scrub_with < 1:
            raise ValueError(
                "min_string_length_to_scrub_with < 1, nonsensical")

        # Test date conversions
        format_datetime(self.NOW_UTC_NO_TZ, self.date_to_text_format)
        format_datetime(self.NOW_UTC_NO_TZ, self.datetime_to_text_format)

        # Source databases
        if not include_sources:
            return
        if not self.sources:
            raise ValueError("No source databases specified.")
        for dbname, cfg in self.srccfg.items():
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
        log.debug("Config validated.")

    def encrypt_primary_pid(self, pid):
        """Encrypt a primary PID, producing a RID."""
        return self.primary_pid_hasher.hash(pid)

    def encrypt_master_pid(self, pid):
        """Encrypt a master PID, producing a master RID."""
        if pid is None:
            return None  # or risk of revealing the hash?
        return self.master_pid_hasher.hash(pid)

    def hash_list(self, l):
        """
        Hashes a list with Python's built-in hash function.

        We could use Python's build-in hash() function, which produces a 64-bit
        unsigned integer (calculated from: sys.maxint).
        However, there is an outside chance that someone uses a single-field
        table and therefore that this is vulnerable to content discovery via a
        dictionary attack. Thus, we should use a better version.
        """
        return self.change_detection_hasher.hash(repr(l))

    def load_destination_fields(self, force=False):
        """Fetches field information from the destination database, unless
        we've cached that information already."""
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
