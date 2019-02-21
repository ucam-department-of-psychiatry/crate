#!/usr/bin/env python

"""
crate_anon/anonymise/constants.py

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

    This file is part of CRATE.

    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.

===============================================================================

**Shared constants for CRATE anonymiser.**

"""

from enum import unique

from sqlalchemy import Integer
from cardinal_pythonlib.enumlike import StrEnum

from crate_anon.version import CRATE_VERSION, CRATE_VERSION_DATE

# =============================================================================
# Logging
# =============================================================================

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
    BINARY_TO_TEXT = "binary_to_text"
    FILENAME_FORMAT_TO_TEXT = "filename_format_to_text"  # new in v0.18.18
    FILENAME_TO_TEXT = "filename_to_text"
    HASH = "hash"
    # HTML_ESCAPE = "html_escape"
    HTML_UNESCAPE = "html_unescape"
    HTML_UNTAG = "html_untag"
    SCRUBIN = "scrub"
    SKIP_IF_TEXT_EXTRACT_FAILS = "skip_if_extract_fails"
    TRUNCATEDATE = "truncate_date"


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

CHARSET = 'utf8'
TABLE_KWARGS = {
    # MySQL:
    'mysql_charset': CHARSET,
    'mysql_engine': 'InnoDB',
}

MAX_IDENTIFIER_LENGTH = 64
# MySQL: 64 -- http://dev.mysql.com/doc/refman/5.7/en/identifiers.html

# =============================================================================
# Demo config
# =============================================================================

# noinspection PyPep8
DEMO_CONFIG = r"""# Configuration file for CRATE anonymiser (crate_anonymise).
# Version {VERSION} ({VERSION_DATE}).
#
# SEE HELP FOR DETAILS.

# =============================================================================
# Main settings
# =============================================================================

[main]

# -----------------------------------------------------------------------------
# Data dictionary
# -----------------------------------------------------------------------------

data_dictionary_filename = testdd.tsv

# -----------------------------------------------------------------------------
# Critical field types
# -----------------------------------------------------------------------------

sqlatype_pid =
sqlatype_mpid =

# -----------------------------------------------------------------------------
# Encryption phrases/passwords
# -----------------------------------------------------------------------------

hash_method = HMAC_MD5

per_table_patient_id_encryption_phrase = SOME_PASSPHRASE_REPLACE_ME

master_patient_id_encryption_phrase = SOME_OTHER_PASSPHRASE_REPLACE_ME

change_detection_encryption_phrase = YETANOTHER

extra_hash_config_sections =

# -----------------------------------------------------------------------------
# Text extraction
# -----------------------------------------------------------------------------

extract_text_extensions_permitted =
extract_text_extensions_prohibited =
extract_text_extensions_case_sensitive = False

extract_text_plain = False

extract_text_width = 80

# -----------------------------------------------------------------------------
# Anonymisation
# -----------------------------------------------------------------------------

replace_patient_info_with = [__PPP__]

replace_third_party_info_with = [__TTT__]

thirdparty_xref_max_depth = 1

replace_nonspecific_info_with = [~~~]

scrub_string_suffixes =
    s

string_max_regex_errors = 1

min_string_length_for_errors = 4

min_string_length_to_scrub_with = 2

whitelist_filenames =

blacklist_filenames =

phrase_alternative_word_filenames =

scrub_all_numbers_of_n_digits =

scrub_all_uk_postcodes = False

anonymise_codes_at_word_boundaries_only = True
anonymise_dates_at_word_boundaries_only = True
anonymise_numbers_at_word_boundaries_only = False
anonymise_numbers_at_numeric_boundaries_only = True
anonymise_strings_at_word_boundaries_only = True

timefield_name = _when_processed_utc

# -----------------------------------------------------------------------------
# Output fields and formatting
# -----------------------------------------------------------------------------

research_id_fieldname = brcid
trid_fieldname = trid
master_research_id_fieldname = nhshash

source_hash_fieldname = _src_hash

ddgen_append_source_info_to_comment = True

# -----------------------------------------------------------------------------
# Destination database configuration
# See the [destination_database] section for connection details.
# -----------------------------------------------------------------------------

max_rows_before_commit = {DEFAULT_MAX_ROWS_BEFORE_COMMIT}
max_bytes_before_commit = {DEFAULT_MAX_BYTES_BEFORE_COMMIT}

temporary_tablename = _temp_table

# -----------------------------------------------------------------------------
# Choose databases (defined in their own sections).
# -----------------------------------------------------------------------------

source_databases =
    mysourcedb1
    mysourcedb2

destination_database = my_destination_database

admin_database = my_admin_database

# -----------------------------------------------------------------------------
# PROCESSING OPTIONS, TO LIMIT DATA QUANTITY FOR TESTING
# -----------------------------------------------------------------------------

debug_max_n_patients =
debug_pid_list =

# -----------------------------------------------------------------------------
# Opting out entirely
# -----------------------------------------------------------------------------

optout_pid_filenames =
optout_mpid_filenames =

optout_col_values =

# =============================================================================
# Destination database details. User should have WRITE access.
# =============================================================================

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

ddgen_omit_by_default = True
ddgen_omit_fields =
ddgen_include_fields =

ddgen_allow_no_patient_info = False

ddgen_per_table_pid_field = patient_id

ddgen_add_per_table_pids_to_scrubber = False

ddgen_master_pid_fieldname = nhsnum

ddgen_table_blacklist =
ddgen_table_whitelist =

ddgen_table_require_field_absolute =
ddgen_table_require_field_conditional =

ddgen_field_blacklist =
ddgen_field_whitelist =

ddgen_pk_fields =

ddgen_constant_content = False
ddgen_constant_content_tables =
ddgen_nonconstant_content_tables =
ddgen_addition_only = False
ddgen_addition_only_tables =
ddgen_deletion_possible_tables =

ddgen_pid_defining_fieldnames =

ddgen_scrubsrc_patient_fields =
ddgen_scrubsrc_thirdparty_fields =
ddgen_scrubsrc_thirdparty_xref_pid_fields =

ddgen_required_scrubsrc_fields =

ddgen_scrubmethod_code_fields =
ddgen_scrubmethod_date_fields =
ddgen_scrubmethod_number_fields =
ddgen_scrubmethod_phrase_fields =

ddgen_safe_fields_exempt_from_scrubbing =

ddgen_min_length_for_scrubbing = 4

ddgen_truncate_date_fields =

ddgen_filename_to_text_fields =
ddgen_binary_to_text_field_pairs =

ddgen_skip_row_if_extract_text_fails_fields =

ddgen_rename_tables_remove_suffixes =

ddgen_patient_opt_out_fields =

ddgen_extra_hash_fields =

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # DESTINATION INDEXING
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

ddgen_index_fields =
ddgen_allow_fulltext_indexing = True

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # DATA DICTIONARY MANIPULATION TO DESTINATION TABLE/FIELD NAMES
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

ddgen_force_lower_case = True
ddgen_convert_odd_chars_to_underscore = True

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # PROCESSING OPTIONS, TO LIMIT DATA QUANTITY FOR TESTING
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

debug_row_limit =
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
ddgen_table_require_field_absolute =
ddgen_table_require_field_conditional =
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

ddgen_table_require_field_absolute =
ddgen_table_require_field_conditional =
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
    VERSION=CRATE_VERSION,
    VERSION_DATE=CRATE_VERSION_DATE,
)

# For the style:
#       [source_databases]
#       source1 = blah
#       source2 = thing
# ... you can't have multiple keys with the same name.
# http://stackoverflow.com/questions/287757
