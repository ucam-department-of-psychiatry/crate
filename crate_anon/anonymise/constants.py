#!/usr/bin/env python
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

from enum import unique

from sqlalchemy import BigInteger, Integer
from cardinal_pythonlib.rnc_lang import StrEnum

from crate_anon.version import VERSION, VERSION_DATE

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

BIGSEP = "=" * 20 + " "
SEP = "-" * 20 + " "

# =============================================================================
# Defaults for command-line options
# =============================================================================

DEFAULT_REPORT_EVERY = 100000  # 100k
DEFAULT_CHUNKSIZE = 100000  # 100k

# =============================================================================
# Environment
# =============================================================================

CONFIG_ENV_VAR = 'CRATE_ANON_CONFIG'

# =============================================================================
# Data dictionary
# =============================================================================

DATEFORMAT_ISO8601 = "%Y-%m-%dT%H:%M:%S%z"  # e.g. 2013-07-24T20:04:07+0100
DEFAULT_INDEX_LEN = 20  # for data types where it's mandatory
DEFAULT_MAX_ROWS_BEFORE_COMMIT = 1000
DEFAULT_MAX_BYTES_BEFORE_COMMIT = 80 * 1024 * 1024

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


@unique
class ALTERMETHOD(StrEnum):
    TRUNCATEDATE = "truncate_date"
    SCRUBIN = "scrub"
    BIN2TEXT = "binary_to_text"
    FILENAME2TEXT = "filename_to_text"
    SKIP_IF_TEXT_EXTRACT_FAILS = "skip_if_extract_fails"
    # HTML_ESCAPE = "html_escape"
    HTML_UNESCAPE = "html_unescape"
    HTML_UNTAG = "html_untag"


@unique
class DECISION(StrEnum):
    OMIT = "OMIT"
    INCLUDE = "include"


@unique
class INDEX(StrEnum):
    NORMAL = "I"
    UNIQUE = "U"
    FULLTEXT = "F"


@unique
class SCRUBMETHOD(StrEnum):
    WORDS = "words"
    PHRASE = "phrase"
    NUMERIC = "number"
    DATE = "date"
    CODE = "code"


@unique
class SCRUBSRC(StrEnum):
    PATIENT = "patient"
    THIRDPARTY = "thirdparty"
    THIRDPARTY_XREF_PID = "thirdparty_xref_pid"


@unique
class SRCFLAG(StrEnum):
    PK = "K"
    ADD_SRC_HASH = "H"
    PRIMARY_PID = "P"
    DEFINES_PRIMARY_PIDS = "*"
    MASTER_PID = "M"
    CONSTANT = "C"
    ADDITION_ONLY = "A"
    OPT_OUT = "!"
    REQUIRED_SCRUBBER = "R"


# =============================================================================
# Databases
# =============================================================================

MYSQL_CHARSET = 'utf8'
MYSQL_TABLE_KWARGS = {
    'mysql_charset': MYSQL_CHARSET,
    'mysql_engine': 'InnoDB',
}

MYSQL_MAX_IDENTIFIER_LENGTH = 64
# http://dev.mysql.com/doc/refman/5.7/en/identifiers.html

# =============================================================================
# Demo config
# =============================================================================

# noinspection PyPep8
DEMO_CONFIG = """# Configuration file for CRATE anonymiser (crate_anonymise).
# Version {VERSION} ({VERSION_DATE}).
#
# Boolean values can be 0/1, Y/N, T/F, True/False.

# =============================================================================
# Main settings
# =============================================================================

[main]

# -----------------------------------------------------------------------------
# Data dictionary
# -----------------------------------------------------------------------------
# Specify a data dictionary in TSV (tab-separated value) format, with a header
# row.
# Columns in the data dictionary (which can be in any order as long as the
# header row matches the data):
#
# src_db
#     Specify the source database.
#     Database names are those used in source_databases list below; they
#     don't have to be SQL database names.
# src_table
#     Table name in source database.
# src_field
#     Field name in source database.
# src_datatype
#     SQL data type in source database, e.g. INT, VARCHAR(50).
#
# src_flags
#     One or more of the following characters:
#
#     {SRCFLAG.PK}
#         PK
#         This field is the primary key (PK) for the table it's in.
#
#     {SRCFLAG.ADD_SRC_HASH}
#         ADD SOURCE HASH
#         Add source hash of the record, for incremental updates?
#         - This flag may only be set for src_pk fields (which cannot then be
#           omitted in the destination, and which require the index={INDEX.UNIQUE}
#           setting, so that a unique index is created for this field).
#         - If set, a field is added to the destination table, with field
#           name as set by the config's source_hash_fieldname variable,
#           containing a hash of the contents of the source record -- all
#           fields that are not omitted, OR contain scrubbing information
#           (scrub_src). The field is of type VARCHAR and its length is
#           determined by the hash_method parameter (see below).
#         - This table is then capable of incremental updates.
#
#     {SRCFLAG.CONSTANT}
#         CONSTANT
#         Record contents are constant (will not change) for a given PK.
#         - An alternative to '{SRCFLAG.ADD_SRC_HASH}'. Can't be used with it.
#         - The flag can be set only on src_pk fields, which can't be omitted
#           in the destination, and which have the same index requirements as
#           the '{SRCFLAG.ADD_SRC_HASH}' flag.
#         - If set, no hash is added to the destination, but the destination
#           contents are assumed to exist and not to have changed.
#         - Be CAUTIOUS with this flag, i.e. certain that the contents will
#           not change.
#         - Intended for very data-intensive fields, such as BLOB fields
#           containing binary documents, where hashing would be quite slow
#           over many gigabytes of data.
#         - Does not imply that the whole table cannot change!
#
#     {SRCFLAG.ADDITION_ONLY}
#         ADDITION ONLY
#         Addition only. It is assumed that records can only be added, not
#         deleted.
#
#     {SRCFLAG.PRIMARY_PID}
#         PRIMARY PID
#         Primary patient ID field. If set,
#         (a) This field will be used to link records for the same patient
#             across all tables. It must therefore be present, and marked in
#             the data dictionary, for ALL tables that contain patient-
#             identifiable information.
#         (b) If the field is not omitted: the field will be hashed as the
#             primary ID (database patient primary key) in the destination,
#             and a transient research ID (TRID) also added.
#
#     {SRCFLAG.DEFINES_PRIMARY_PIDS}
#         DEFINES PRIMARY PIDS.
#         This field *defines* primary PIDs. If set, this row will be used to
#         search for all patient IDs, and will define them for this database.
#         Only those patients will be processed (for all tables containing
#         patient info). Typically, this flag is applied to a SINGLE field in a
#         SINGLE table, usually the principal patient registration/demographics
#         table.
#
#     {SRCFLAG.MASTER_PID}
#         MASTER PID
#         Master ID (e.g. NHS number).
#         The field will be hashed with the master PID hasher.
#
#     {SRCFLAG.OPT_OUT}
#         OPT OUT
#         This field is used to mark that the patient wishes to opt out
#         entirely. It must be in a field that also has a primary patient ID
#         field (because that's the ID that will be omitted). If the opt-out
#         field contains a value that's defined in the optout_col_values
#         setting (see below), that patient will be opted out entirely from
#         the anonymised database.
#
#     {SRCFLAG.REQUIRED_SCRUBBER}
#         REQUIRED SCRUBBER
#         If this field is a scrub_src field (see below), and this flag is set,
#         then at least one non-NULL value for this field must be present for
#         each patient, or no information will be processed for this patient.
#         (Typical use: where you have a master patient index separate from the
#         patient name table, and data might have been brought across
#         partially, so there are some missing names. In this situation, text
#         might go unscrubbed because the names are missing. Setting this flag
#         for the name field will prevent this.)
#
# scrub_src
#     One of:
#           "{SCRUBSRC.PATIENT}",
#           "{SCRUBSRC.THIRDPARTY}",
#           "{SCRUBSRC.THIRDPARTY_XREF_PID}",
#           or blank.
#     Explanations:
#     - "{SCRUBSRC.PATIENT}":
#       Contains patient-identifiable information that must be removed from
#       "scrub_in" fields.
#     - "{SCRUBSRC.THIRDPARTY}":
#       Contains identifiable information about carer/family/other third party,
#       which must be removed from "scrub_in" fields.
#     - "{SCRUBSRC.THIRDPARTY_XREF_PID}":
#       This field is a patient identifier for ANOTHER patient (such as a
#       relative). The scrubber should recursively include THAT patient's
#       identifying information as third-party information for THIS patient.
#
# scrub_method
#     Applicable to scrub_src fields. Manner in which this field should be
#     treated for scrubbing.
#     Options:
#
#     - "{SCRUBMETHOD.WORDS}"
#       Treat as a set of textual words. This is the default for all textual
#       fields (e.g. CHAR, VARCHAR, TEXT). Typically used for names.
#       Also OK for e-mail addresses.
#
#     - "{SCRUBMETHOD.PHRASE}"
#       Treat as a textual phrase (a sequence of words to be replaced only when
#       they occur in sequence). Typically used for address components.
#
#     - "{SCRUBMETHOD.NUMERIC}"
#       Treat as a number. This is the default for all numeric fields (e.g.
#       INTEGER, FLOAT). If you have a phone number in a text field, use this
#       method; it will be scrubbed regardless of spacing/punctuation.
#
#     - "{SCRUBMETHOD.CODE}"
#       Teat as an alphanumeric code. Suited to postcodes. Very like the
#       numeric method, but permits non-digits.
#
#     - "{SCRUBMETHOD.DATE}"
#       Treat as a date. This is the default for all DATE/DATETIME fields.
#
# decision
#     One of:
#     - "{DECISION.OMIT}": omit the field from the output entirely;
#     - "{DECISION.INCLUDE}": include it.
#     This is case sensitive, for safety.
#
# inclusion_values
#     - Either blank, or an expression that evaluates to a Python iterable
#       (e.g. list or tuple) with Python's ast.literal_eval() function (see
#       https://docs.python.org/3.4/library/ast.html).
#     - Examples:
#           [None, 0]
#           [True, 1, 'yes', 'true', 'Yes', 'True']
#     - If this is not blank/None, then it serves as a ROW INCLUSION LIST -
#       the source row will only be processed if the field's value is one of
#       the inclusion values.
#     - It applies to the raw value from the database (before any
#       transformation via alter_method).
#     - This is not applied to scrub_src fields (which contribute to the
#       scrubber regardless.
#     - Note that "[None]" is a list with one member, None, whereas "None"
#       is equivalent to leaving the field blank.
#
# exclusion_values
#     - As for inclusion_values, but the row is excluded if the field's value
#       is in the exclusion_values list.
#
# alter_method
#     Manner in which to alter the data. Blank, or one or more of:
#
#     - "{ALTERMETHOD.SCRUBIN}"
#       Scrub in. Applies to text fields only. The field will have its contents
#       anonymised (using information from other fields). Use this for any
#       text field that end users might store free-text comments in.
#
#     - "{ALTERMETHOD.TRUNCATEDATE}"
#       Truncate this date to the first of the month. Applicable to text or
#       date-as-text fields.
#
#     - "{ALTERMETHOD.BIN2TEXT}=EXTFIELDNAME"
#       Convert a binary field (e.g. VARBINARY, BLOB) to text (e.g. LONGTEXT).
#       The binary data is taken to be the representation of a document.
#       The field EXTFIELDNAME, which must be in the same source table, must
#       contain the file extension (e.g. "pdf", ".pdf") or a filename with that
#       extension (e.g. "/some/path/mything.pdf"), so that the anonymiser knows
#       how to treat the binary data to extract text from it.
#
#     - "{ALTERMETHOD.FILENAME2TEXT}"
#       As for the binary-to-text option, but the field contains a filename
#       (the contents of which is converted to text), rather than containing
#       binary data directly.
#
#     - "{ALTERMETHOD.SKIP_IF_TEXT_EXTRACT_FAILS}"
#       If one of the text extraction methods is specified, and this flag is
#       also specified, then the data row will be skipped if text extrcation
#       fails (rather than inserted with a NULL value for the text). This is
#       helpful, for example, if your text-processing pipeline breaks; the
#       option prevents rows being created erroneously with NULL text values,
#       so that a subsequent incremental update will fix the problems once
#       you've fixed your text extraction tools.
#
#     - "{ALTERMETHOD.HTML_UNESCAPE}"
#       HTML encoding is removed, e.g. convert "&amp;" to "&" and "&lt;" to "<"
#
#     - "{ALTERMETHOD.HTML_UNTAG}"
#       HTML tags are removed, e.g. from
#           <a href="http://somewhere">see link</a>
#       to
#           see link
#
#     You can specify multiple options separated by commas.
#     Not all are compatible (e.g. scrubbing is for text; date truncation is
#     for dates).
#     If there's more than one, text extraction from BLOBs/files is performed
#     first. After that, they are executed in sequence. (The position of the
#     skip-if-text-extraction-fails flag is immaterial.)
#     A typical combination might be:
#           {ALTERMETHOD.FILENAME2TEXT},{ALTERMETHOD.SKIP_IF_TEXT_EXTRACT_FAILS},{ALTERMETHOD.SCRUBIN}
#     or:
#           {ALTERMETHOD.HTML_UNTAG},{ALTERMETHOD.HTML_UNESCAPE},{ALTERMETHOD.SCRUBIN}
#
# dest_table
#     Table name in destination database.
# dest_field
#     Field name in destination database.
# dest_datatype
#     SQL data type in destination database.
#     If omitted, the source SQL data type is translated appropriately.
# index
#     One of:
#     - blank: no index.
#     - "{INDEX.NORMAL}"
#       ... create a normal index on the destination field.
#     - "{INDEX.UNIQUE}"
#       ... create a unique index on the destination field.
#     - "{INDEX.FULLTEXT}"
#       ... create a FULLTEXT index, for rapid searching within long text
#       fields. Only applicable to one field per table.
# indexlen
#     Integer. Can be blank. If not, sets the prefix length of the index.
#     Mandatory in MySQL if you apply a normal (+/- unique) index to a TEXT
#     or BLOB field. Not required for FULLTEXT indexes.
# comment
#     Field comment, stored in destination database.

data_dictionary_filename = testdd.tsv

# -----------------------------------------------------------------------------
# Encryption phrases/passwords
# -----------------------------------------------------------------------------

    # PID-to-RID hashing method. Options are:
    # - HMAC_MD5 - produces a 32-character digest
    # - HMAC_SHA256 - produces a 64-character digest
    # - HMAC_SHA512 - produces a 128-character digest
hash_method = HMAC_MD5

per_table_patient_id_encryption_phrase = SOME_PASSPHRASE_REPLACE_ME

master_patient_id_encryption_phrase = SOME_OTHER_PASSPHRASE_REPLACE_ME

change_detection_encryption_phrase = YETANOTHER

# -----------------------------------------------------------------------------
# Text extraction
# -----------------------------------------------------------------------------

    # Use the plainest possible layout for text extraction?
    # False = better for human layout. Table example from DOCX:
    #     +---------+---------+
    #     | AAA AAA | BBB BBB |
    #     | AAA AAA | BBB BBB |
    #     +---------+---------+
    # True = good for natural language processing. Table example from DOCX:
    #     ---------------------
    #       AAA AAA
    #       AAA AAA
    #     ---------------------
    #                 BBB BBB
    #                 BBB BBB
    #     ---------------------
    # ... note the absence of vertical interruptions, and that text from one
    # cell remains contiguous.
extract_text_plain = False

    # Default width to word-wrap extracted text to
extract_text_width = 80

# -----------------------------------------------------------------------------
# Anonymisation
# -----------------------------------------------------------------------------

    # Patient information will be replaced with this. For example, XXXXXX or
    # [___] or [__PPP__] or [__ZZZ__]; the bracketed forms can be a bit easier
    # to spot, and work better if they directly abut other text.
replace_patient_info_with = [__PPP__]

    # Third-party information will be replaced by this.
    # For example, YYYYYY or [...] or [__TTT__] or [__QQQ__].
replace_third_party_info_with = [__TTT__]

    # For fields marked as scrub_src = {SCRUBSRC.THIRDPARTY_XREF_PID},
    # how deep should we recurse? The default is 1. Beware making this too
    # large; the recursion trawls a lot of information (and also uses an
    # extra simultaneous database cursor for each recursion).
thirdparty_xref_max_depth = 1

    # Things to be removed irrespective of patient-specific information will be
    # replaced by this (for example, if you opt to remove all things looking
    # like telephone numbers). For example, ZZZZZZ or [~~~].
replace_nonspecific_info_with = [~~~]

    # Strings to append to every "scrub from" string.
    # For example, include "s" if you want to scrub "Roberts" whenever you
    # scrub "Robert".
    # Applies to {SCRUBMETHOD.WORDS}, but not to {SCRUBMETHOD.PHRASE}.
    # Multiline field: https://docs.python.org/2/library/configparser.html
scrub_string_suffixes =
    s

    # Specify maximum number of errors (insertions, deletions, substitutions)
    # in string regex matching. Beware using a high number! Suggest 1-2.
string_max_regex_errors = 1

    # Is there a minimum length to apply string_max_regex_errors? For example,
    # if you allow one typo and someone is called Ian, all instances of 'in' or
    # 'an' will be wiped. Note that this apply to scrub-source data.
min_string_length_for_errors = 4

    # Is there a minimum length of string to scrub WITH? For example, if you
    # specify 2, you allow two-letter names such as Al to be scrubbed, but you
    # allow initials through, and therefore prevent e.g. 'A' from being
    # scrubbed from the destination. Note that this applies to scrub-source
    # data.
min_string_length_to_scrub_with = 2

    # WHITELIST.
    # Are there any words not to scrub? For example, "the", "road", "street"
    # often appear in addresses, but you might not want them removed. Be
    # careful in case these could be names (e.g. "Lane").
    # Specify these as a list of FILENAMES, where the files contain words; e.g.
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
    # For example, scrubbing all 11-digit numbers will remove modern UK
    # telephone numbers in conventional format. To do this, specify
    # scrub_all_numbers_of_n_digits = 11. You could scrub both 10- and 11-digit
    # numbers by specifying both numbers (in multiline format, as above);
    # 10-digit numbers would include all NHS numbers. Avoid using this for
    # short numbers; you may lose valuable numeric data!
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
    # liberal and will deal with accidental word concatenation. With ID
    # numbers, beware if you use a prefix, e.g. if people write 'M123456' or
    # 'R123456'; in that case you will need
    #       anonymise_numbers_at_word_boundaries_only = False.
anonymise_codes_at_word_boundaries_only = True
    # ... applies to {SCRUBMETHOD.CODE}
anonymise_dates_at_word_boundaries_only = True
    # ... applies to {SCRUBMETHOD.DATE}
anonymise_numbers_at_word_boundaries_only = False
    # ... applies to {SCRUBMETHOD.NUMERIC}
anonymise_numbers_at_numeric_boundaries_only = True
    # ... applies to {SCRUBMETHOD.NUMERIC}
    # ... if True, will not scrub "234" from "123456"
    # ... setting this to False is extremely conservative
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

    # Change-detection hash fieldname. This will be a VARCHAR of length
    # determined by hash_method.
source_hash_fieldname = _src_hash

    # Date-to-text conversion formats
date_to_text_format = %Y-%m-%d
    # ... ISO-8601, e.g. 2013-07-24
datetime_to_text_format = %Y-%m-%dT%H:%M:%S
    # ... ISO-8601, e.g. 2013-07-24T20:04:07

    # Append source table/field to the comment? Boolean.
append_source_info_to_comment = True

# -----------------------------------------------------------------------------
# Destination database configuration
# See the [destination_database] section for connection details.
# -----------------------------------------------------------------------------

    # Specify the maximum number of rows to be processed before a COMMIT is
    # issued on the database transaction. This prevents the transaction growing
    # too large.
    # Default is {DEFAULT_MAX_ROWS_BEFORE_COMMIT}.
max_rows_before_commit = {DEFAULT_MAX_ROWS_BEFORE_COMMIT}

    # Specify the maximum number of source-record bytes (approximately!) that
    # are processed before a COMMIT is issued on the database transaction. This
    # prevents the transaction growing too large. The COMMIT will be issued
    # *after* this limit has been met/exceeded, so it may be exceeded if the
    # transaction just before the limit takes the cumulative total over the
    # limit.
    # Default is {DEFAULT_MAX_BYTES_BEFORE_COMMIT}.
max_bytes_before_commit = {DEFAULT_MAX_BYTES_BEFORE_COMMIT}

    # We need a temporary table name for incremental updates. This can't be the
    # name of a real destination table. It lives in the destination database.
temporary_tablename = _temp_table

# -----------------------------------------------------------------------------
# Choose databases (defined in their own sections).
# -----------------------------------------------------------------------------

    # Source database list. Can be lots.
source_databases =
    mysourcedb1
    mysourcedb2

    # Destination database. Just one.
destination_database = my_destination_database

    # Admin database. Just one.
admin_database = my_admin_database

# -----------------------------------------------------------------------------
# PROCESSING OPTIONS, TO LIMIT DATA QUANTITY FOR TESTING
# -----------------------------------------------------------------------------

    # Limit the number of patients to be processed? Specify 0 (the default) for
    # no limit.
debug_max_n_patients =

    # Specify a list of integer patient IDs, for debugging? If specified, this
    # list will be used directly (overriding the patient ID source specified in
    # the data dictionary, and overriding debug_max_n_patients).
debug_pid_list =

# =============================================================================
# Opting out entirely
# =============================================================================
# Patients who elect to opt out entirely have their PIDs stored in the OptOut
# table of the admin database. ENTRIES ARE NEVER REMOVED FROM THIS LIST BY
# CRATE. It can be populated in three ways:
#   1. Manually, by adding a PID to the column opt_out.pid).
#   2. By maintaining a text file list of integer PIDs. Any PIDs in this file
#      are added to the opt-out list.
#   3. By flagging a source database field as indicating an opt-out, using the
#      src_flags = "{SRCFLAG.OPT_OUT}" marker.

    # If you set this, each line of the file(s) is scanned for an integer,
    # taken to the PID of a patient who wishes to opt out.
optout_pid_filenames =

    # If you set this, each line of the file(s) is scanned for an integer,
    # taken to the MPID of a patient who wishes to opt out.
optout_mpid_filenames =

    # If you mark a field in the data dictionary as an opt-out field (see
    # above), that says "the field tells you whether the patient opts out or
    # not". But is it "opt out" or "not"? If the actual value matches one
    # below, then it's "opt out". Specify a LIST OF PYTHON VALUES; for example:
    #       optout_col_values = [True, 'Yes', 'Y']
optout_col_values =

# =============================================================================
# Destination database details. User should have WRITE access.
# =============================================================================
# Use SQLAlchemy URLs: see
#       http://docs.sqlalchemy.org/en/latest/core/engines.html
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

# -----------------------------------------------------------------------------
# Source database example 1
# -----------------------------------------------------------------------------

[mysourcedb1]

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # CONNECTION DETAILS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

url = mysql+mysqldb://username:password@127.0.0.1:3306/source_databasename?charset=utf8

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # INPUT FIELDS, FOR THE AUTOGENERATION OF DATA DICTIONARIES
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # - For field specifications, fields can either be specified as "column"
    #   (to match any table) or "table.column", to match a specific table.
    #   They are case-insensitive.
    #   Wildcards (*, ?) may also be used (as per Python's fnmatch).

    # By default, most fields (except PKs and patient ID codes) are marked
    # as "OMIT", pending human review. If you want to live dangerously, set
    # this to False, and they will be marked as "include" from the outset.
ddgen_omit_by_default = True

    # You can specify additional fields to omit...
ddgen_omit_fields =

    # ... or include. "Omit" overrides "include".
    # If a field contains scrubbing source information, it will also be omitted
    # pending human review, regardless of other settings.
ddgen_include_fields =

    # Allow the absence of patient info? Used to copy databases; WILL NOT
    # ANONYMISE. Boolean; default is False.
ddgen_allow_no_patient_info = False

    # Specify the (typically integer) patient identifier present in EVERY
    # table. It will be replaced by the research ID in the destination
    # database.
ddgen_per_table_pid_field = patient_id

    # Add every instance of a per-table PID field to the patient scrubber?
    # This is a very conservative setting, and should be unnecessary as the
    # single master "PID-defining" column (see ddgen_pid_defining_fieldnames)
    # should be enough.
    # (Note that per-table PIDs are always replaced by RIDs - this setting
    # governs whether the scrubber used to scrub free-text fields also
    # works through every single per-table PID).
ddgen_add_per_table_pids_to_scrubber = False

    # Master patient ID fieldname. Used for e.g. NHS numbers.
ddgen_master_pid_fieldname = nhsnum

    # Blacklist any tables when creating new data dictionaries?
    # This is case-insensitive, and you can use */? wildcards (as per Python's
    # fnmatch module).
ddgen_table_blacklist =

    # Whitelist any tables? (Whitelists override blacklists.)
ddgen_table_whitelist =

    # Blacklist any fields (regardless of their table) when creating new data
    # dictionaries? Wildcards of */? operate as above.
ddgen_field_blacklist =

    # Whitelist any fields? (Whitelists override blacklists.)
ddgen_field_whitelist =

    # Fieldnames assumed to be their table's PK:
ddgen_pk_fields =

    # Assume that content stays constant?
    # (Applies {SRCFLAG.CONSTANT} to PK fields; q.v.)
    # This is the default; then ddgen_constant_content_tables and
    # ddgen_nonconstant_content_tables can override (of which,
    # ddgen_nonconstant_content_tables takes priority if a table matches both).
ddgen_constant_content = False

    # Table-specific overrides for ddgen_constant_content, as above.
ddgen_constant_content_tables =
ddgen_nonconstant_content_tables =

    # Assume that records can only be added, not deleted?
ddgen_addition_only = False

    # Table-specific overrides for ddgen_addition_only, similarly.
ddgen_addition_only_tables =
ddgen_deletion_possible_tables =

    # Predefine field(s) that define the existence of patient IDs? UNUSUAL.
ddgen_pid_defining_fieldnames =

    # Default fields to scrub from
ddgen_scrubsrc_patient_fields =
ddgen_scrubsrc_thirdparty_fields =
ddgen_scrubsrc_thirdparty_xref_pid_fields =

    # Are any scrub_src fields required (mandatory), i.e. must have non-NULL
    # data in at least one row?
ddgen_required_scrubsrc_fields =

    # Override default scrubbing methods
ddgen_scrubmethod_code_fields =
ddgen_scrubmethod_date_fields =
ddgen_scrubmethod_number_fields =
ddgen_scrubmethod_phrase_fields =

    # Known safe fields, exempt from scrubbing
ddgen_safe_fields_exempt_from_scrubbing =

    # Define minimum text field length for scrubbing (shorter is assumed safe)
ddgen_min_length_for_scrubbing = 4

    # Other default manipulations
ddgen_truncate_date_fields =

    # Fields containing filenames, which files should be converted to text
ddgen_filename_to_text_fields =

    # Fields containing raw binary data from files (binary large objects;
    # BLOBs), whose contents should be converted to text -- paired with fields
    # in the same table containing their file extension (e.g. "pdf", ".PDF") or
    # a filename having that extension.
    # Specify it as a list of comma-joined pairs, e.g.
    #     ddgen_binary_to_text_field_pairs = binary1field, ext1field
    #         binary2field, ext2field
    #         ...
    # The first (binaryfield) can be specified as column or table.column,
    # but the second must be column only.
ddgen_binary_to_text_field_pairs =

    # Specify any text-extraction rows for which you also want to set the flag
    # "{ALTERMETHOD.SKIP_IF_TEXT_EXTRACT_FAILS}":
ddgen_skip_row_if_extract_text_fails_fields =

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # DESTINATION INDEXING
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    # Fields to apply an index to
ddgen_index_fields =

    # Allow full-text index creation? Default true. Disable for databases that
    # don't support them?
ddgen_allow_fulltext_indexing = True

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # DATA DICTIONARY MANIPULATION TO DESTINATION TABLE/FIELD NAMES
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    # Force all destination tables/fields to lower case?
    # Boolean; default is True.
ddgen_force_lower_case = True

    # Convert spaces in table/fieldnames (yuk!) to underscores? Default: true.
ddgen_convert_odd_chars_to_underscore = True

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # PROCESSING OPTIONS, TO LIMIT DATA QUANTITY FOR TESTING
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    # Specify 0 (the default) for no limit, or a number of rows (e.g. 1000) to
    # apply to any tables listed in debug_limited_tables. For those tables,
    # only this many rows will be taken from the source database. Use this, for
    # example, to reduce the number of large documents fetched.
    # If you run a multiprocess/multithreaded anonymisation, this limit applies
    # per *process* (or task), not overall.
    # Note that these limits DO NOT APPLY to the fetching of patient-
    # identifiable information for anonymisation -- when a patient is
    # processed, all identifiable information for that patient is trawled.
debug_row_limit =

    # List of tables to which to apply debug_row_limit (see above).
debug_limited_tables =

# -----------------------------------------------------------------------------
# Source database example 2
# -----------------------------------------------------------------------------

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

# -----------------------------------------------------------------------------
# Source database example 3
# -----------------------------------------------------------------------------

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

""".format(  # noqa
    SCRUBSRC=SCRUBSRC,
    INDEX=INDEX,
    SCRUBMETHOD=SCRUBMETHOD,
    ALTERMETHOD=ALTERMETHOD,
    SRCFLAG=SRCFLAG,
    LONGTEXT=LONGTEXT,
    DEFAULT_MAX_ROWS_BEFORE_COMMIT=DEFAULT_MAX_ROWS_BEFORE_COMMIT,
    DEFAULT_MAX_BYTES_BEFORE_COMMIT=DEFAULT_MAX_BYTES_BEFORE_COMMIT,
    DECISION=DECISION,
    VERSION=VERSION,
    VERSION_DATE=VERSION_DATE,
)

# For the style:
#       [source_databases]
#       source1 = blah
#       source2 = thing
# ... you can't have multiple keys with the same name.
# http://stackoverflow.com/questions/287757
