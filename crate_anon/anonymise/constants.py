#!/usr/bin/env python3
# crate_anon/anonymise/anon_constants.py

"""
Shared constants for CRATE anonymiser.

Author: Rudolf Cardinal
Created at: 18 Feb 2015
Last update: 22 Nov 2015

Copyright/licensing:

    Copyright (C) 2015-2016 Rudolf Cardinal (rudolf@pobox.com).
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

from sqlalchemy import (
    BigInteger,
    Integer,
)
from cardinal_pythonlib.rnc_lang import AttrDict


# =============================================================================
# Logging
# =============================================================================

LOG_FORMAT = '%(asctime)s.%(msecs)03d:%(levelname)s:%(name)s:%(message)s'
LOG_DATEFMT = '%Y-%m-%d %H:%M:%S'

LOG_COLORS = {
    'DEBUG': 'cyan',
    'INFO': 'green',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'red,bg_white',
}

# =============================================================================
# Cosmetic
# =============================================================================

SEP = "=" * 20 + " "

# =============================================================================
# Environment
# =============================================================================

CONFIG_ENV_VAR = 'CRATE_ANON_CONFIG'

# =============================================================================
# Data dictionary
# =============================================================================

ALTERMETHOD = AttrDict(
    TRUNCATEDATE="truncatedate",
    SCRUBIN="scrub",
    BIN2TEXT="binary_to_text",
    BIN2TEXT_SCRUB="binary_to_text_scrub",
    FILENAME2TEXT="filename_to_text",
    FILENAME2TEXT_SCRUB="filename_to_text_scrub"
)

DATEFORMAT_ISO8601 = "%Y-%m-%dT%H:%M:%S%z"  # e.g. 2013-07-24T20:04:07+0100
DEFAULT_INDEX_LEN = 20  # for data types where it's mandatory
DEFAULT_MAX_ROWS_BEFORE_COMMIT = 1000
DEFAULT_MAX_BYTES_BEFORE_COMMIT = 80 * 1024 * 1024

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

SRCFLAG = AttrDict(
    PK="K",
    ADDSRCHASH="H",
    PRIMARYPID="P",
    DEFINESPRIMARYPIDS="*",
    MASTERPID="M",
    CONSTANT="C",
    ADDITION_ONLY="A"
)

PidType = BigInteger
TridType = Integer
MAX_TRID = 2 ** 31 - 1
# https://dev.mysql.com/doc/refman/5.0/en/numeric-type-overview.html
# Maximum INT UNSIGNED is              4294967295 == 2 ** 32 - 1.
# INT range is                        -2147483648 == -(2 **  31) to
#                                     +2147483647 == 2 ** 31 - 1
# ... note that this is inadequate for 10-digit NHS numbers.
# Maximum BIGINT UNSIGNED is 18446744073709551615 == 2 ** 64 - 1.
# BIGINT range is            -9223372036854775808 == -(2 ** 63) to
#                            +9223372036854775807 == 2 ** 64 - 1


# =============================================================================
# Databases
# =============================================================================

MYSQL_CHARSET = 'utf8'
MYSQL_TABLE_ARGS = {
    'mysql_charset': MYSQL_CHARSET,
    'mysql_engine': 'InnoDB',
}

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
#       If omitted, the source SQL data type is translated appropriately.
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
# name of a real destination table. It lives in the destination database.

temporary_tablename = _temp_table

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
# Use SQLAlchemy URLs: see http://docs.sqlalchemy.org/en/latest/core/engines.html
# You may need to install additional drivers, e.g.
#       pip install SOME_DRIVER
# ... see the documentation.

[my_destination_database]

url = mysql+mysqldb://username:password@127.0.0.1:3306/output_databasename?charset=utf8

# =============================================================================
# Administrative database. User should have WRITE access.
# =============================================================================

[my_admin_database]

url = mysql+mysqldb://username:password@127.0.0.1:3306/admin_databasename?charset=utf8

# =============================================================================
# SOURCE DATABASE DETAILS BELOW HERE.
# User should have READ access only for safety.
# =============================================================================

[mysourcedb1]

# CONNECTION DETAILS

url = mysql+mysqldb://username:password@127.0.0.1:3306/source_databasename?charset=utf8

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

url = mysql+mysqldb://username:password@127.0.0.1:3306/source2_databasename?charset=utf8

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

url = mysql+mysqldb://username:password@127.0.0.1:3306/camcops_databasename?charset=utf8

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
