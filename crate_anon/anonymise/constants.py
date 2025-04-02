"""
crate_anon/anonymise/constants.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

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
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

**Shared constants for CRATE anonymiser.**

"""

import calendar
from enum import unique

from sqlalchemy import Integer
from cardinal_pythonlib.enumlike import StrEnum

from crate_anon.version import CRATE_VERSION, CRATE_VERSION_DATE
from crate_anon.nlp_manager.constants import DatabaseConfigKeys


# =============================================================================
# Logging
# =============================================================================

LOG_DATEFMT = "%Y-%m-%d %H:%M:%S"

LOG_COLORS = {
    "DEBUG": "cyan",
    "INFO": "green",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "red,bg_white",
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

ANON_CONFIG_ENV_VAR = "CRATE_ANON_CONFIG"

# =============================================================================
# Data dictionary
# =============================================================================

DATEFORMAT_ISO8601 = "%Y-%m-%dT%H:%M:%S%z"  # e.g. 2013-07-24T20:04:07+0100
DEFAULT_INDEX_LEN = 20  # for data types where it's mandatory

LONGTEXT = "LONGTEXT"

MAX_PID_STR = "9" * 10  # e.g. NHS numbers are 10-digit

TridType = Integer
MAX_TRID = 2**31 - 1
# https://dev.mysql.com/doc/refman/5.0/en/numeric-type-overview.html
# Maximum INT UNSIGNED is              4294967295 == 2 ** 32 - 1.
# INT range is                        -2147483648 == -(2 **  31) to
#                                     +2147483647 == 2 ** 31 - 1 == 2.1 billion
# ... note that this is inadequate for 10-digit NHS numbers.
# Maximum BIGINT UNSIGNED is 18446744073709551615 == 2 ** 64 - 1.
# BIGINT range is            -9223372036854775808 == -(2 ** 63) to
#                            +9223372036854775807 == 2 ** 64 - 1


# When scrub_all_dates is True and the replacement text is a date format
# string, allow these directives.
# https://docs.python.org/3/library/datetime.html#strftime-strptime-behavior
DATE_BLURRING_DIRECTIVES = (
    "b",  # Month as locale's abbreviated name
    "B",  # Month as locale's full name
    "m",  # Month as zero-padded decimal number
    "Y",  # Year with century as decimal number
    "y",  # Year without century as zero-padded decimal number
    # Among things that are not currently supported: %% (literal %).
)
DATE_BLURRING_DIRECTIVES_CSV = ", ".join(
    [f"%{d}" for d in DATE_BLURRING_DIRECTIVES]
)

# https://stackoverflow.com/questions/3418050/month-name-to-month-number-and-vice-versa-in-python
MONTH_3_LETTER_INDEX = {
    # See _month_word_regex_fragment() in anonregex.py
    # Assuming this may not be the same as calendar.month_abbr in some locales
    month[:3]: index
    for index, month in enumerate(calendar.month_name)
    if month
}


@unique
class AlterMethodType(StrEnum):
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
class Decision(StrEnum):
    OMIT = "OMIT"
    INCLUDE = "include"


@unique
class IndexType(StrEnum):
    NONE = ""
    NORMAL = "I"
    UNIQUE = "U"
    FULLTEXT = "F"


@unique
class ScrubMethod(StrEnum):
    WORDS = "words"
    PHRASE = "phrase"
    PHRASE_UNLESS_NUMERIC = "phrase_unless_numeric"
    NUMERIC = "number"
    DATE = "date"
    CODE = "code"


@unique
class ScrubSrc(StrEnum):
    PATIENT = "patient"
    THIRDPARTY = "thirdparty"
    THIRDPARTY_XREF_PID = "thirdparty_xref_pid"


@unique
class SrcFlag(StrEnum):
    PK = "K"
    NOT_NULL = "N"
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

CHARSET = "utf8"
TABLE_KWARGS = {
    # MySQL:
    "mysql_charset": CHARSET,
    "mysql_engine": "InnoDB",
}
COMMENT = "comment"

MYSQL_MAX_IDENTIFIER_LENGTH = 64
# MySQL: 64 -- http://dev.mysql.com/doc/refman/5.7/en/identifiers.html
SQLSERVER_MAX_IDENTIFIER_LENGTH = 128
# Microsoft SQL Server: 128 --
# https://docs.microsoft.com/en-us/sql/relational-databases/databases/database-identifiers  # noqa: E501


# =============================================================================
# Config keys
# =============================================================================


class AnonymiseConfigKeys:
    # Sections
    SECTION_MAIN = "main"
    SECTION_EXTRA_REGEXES = "extra_regexes"

    # Data dictionary
    DATA_DICTIONARY_FILENAME = "data_dictionary_filename"

    # Critical field types
    SQLATYPE_MPID = "sqlatype_mpid"
    SQLATYPE_PID = "sqlatype_pid"

    # Encryption phrases/passwords
    CHANGE_DETECTION_ENCRYPTION_PHRASE = "change_detection_encryption_phrase"
    EXTRA_HASH_CONFIG_SECTIONS = "extra_hash_config_sections"
    HASH_METHOD = "hash_method"
    MASTER_PATIENT_ID_ENCRYPTION_PHRASE = "master_patient_id_encryption_phrase"
    PER_TABLE_PATIENT_ID_ENCRYPTION_PHRASE = (
        "per_table_patient_id_encryption_phrase"
    )

    # Text extraction
    EXTRACT_TEXT_EXTENSIONS_CASE_SENSITIVE = (
        "extract_text_extensions_case_sensitive"
    )
    EXTRACT_TEXT_EXTENSIONS_PERMITTED = "extract_text_extensions_permitted"
    EXTRACT_TEXT_EXTENSIONS_PROHIBITED = "extract_text_extensions_prohibited"
    EXTRACT_TEXT_PLAIN = "extract_text_plain"
    EXTRACT_TEXT_WIDTH = "extract_text_width"

    # Anonymisation
    ALLOWLIST_FILENAMES = "allowlist_filenames"
    ALLOW_NO_PATIENT_INFO = "allow_no_patient_info"
    ANONYMISE_CODES_AT_WORD_BOUNDARIES_ONLY = (
        "anonymise_codes_at_word_boundaries_only"
    )
    ANONYMISE_CODES_AT_NUMERIC_BOUNDARIES_ONLY = (
        "anonymise_codes_at_numeric_boundaries_only"
    )
    ANONYMISE_DATES_AT_WORD_BOUNDARIES_ONLY = (
        "anonymise_dates_at_word_boundaries_only"
    )
    ANONYMISE_NUMBERS_AT_NUMERIC_BOUNDARIES_ONLY = (
        "anonymise_numbers_at_numeric_boundaries_only"
    )
    ANONYMISE_NUMBERS_AT_WORD_BOUNDARIES_ONLY = (
        "anonymise_numbers_at_word_boundaries_only"
    )
    ANONYMISE_STRINGS_AT_WORD_BOUNDARIES_ONLY = (
        "anonymise_strings_at_word_boundaries_only"
    )
    DENYLIST_FILENAMES = "denylist_filenames"
    DENYLIST_FILES_AS_PHRASES = "denylist_files_as_phrases"
    DENYLIST_USE_REGEX = "denylist_use_regex"
    DEPRECATED_BLACKLIST_FILENAMES = "blacklist_filenames"
    DEPRECATED_WHITELIST_FILENAMES = "whitelist_filenames"
    MIN_STRING_LENGTH_FOR_ERRORS = "min_string_length_for_errors"
    MIN_STRING_LENGTH_TO_SCRUB_WITH = "min_string_length_to_scrub_with"
    NONSPECIFIC_SCRUBBER_FIRST = "nonspecific_scrubber_first"
    PHRASE_ALTERNATIVE_WORD_FILENAMES = "phrase_alternative_word_filenames"
    REPLACE_ALL_DATES_WITH = "replace_all_dates_with"
    REPLACE_NONSPECIFIC_INFO_WITH = "replace_nonspecific_info_with"
    REPLACE_PATIENT_INFO_WITH = "replace_patient_info_with"
    REPLACE_THIRD_PARTY_INFO_WITH = "replace_third_party_info_with"
    SCRUB_ALL_DATES = "scrub_all_dates"
    SCRUB_ALL_EMAIL_ADDRESSES = "scrub_all_email_addresses"
    SCRUB_ALL_NUMBERS_OF_N_DIGITS = "scrub_all_numbers_of_n_digits"
    SCRUB_ALL_UK_POSTCODES = "scrub_all_uk_postcodes"
    SCRUB_STRING_SUFFIXES = "scrub_string_suffixes"
    STRING_MAX_REGEX_ERRORS = "string_max_regex_errors"
    THIRDPARTY_XREF_MAX_DEPTH = "thirdparty_xref_max_depth"
    TIMEFIELD_NAME = "timefield_name"

    # Output fields and formatting
    RESEARCH_ID_FIELDNAME = "research_id_fieldname"
    TRID_FIELDNAME = "trid_fieldname"
    MASTER_RESEARCH_ID_FIELDNAME = "master_research_id_fieldname"
    ADD_MRID_WHEREVER_RID_ADDED = "add_mrid_wherever_rid_added"
    SOURCE_HASH_FIELDNAME = "source_hash_fieldname"

    # Destination database configuration
    MAX_ROWS_BEFORE_COMMIT = "max_rows_before_commit"
    MAX_BYTES_BEFORE_COMMIT = "max_bytes_before_commit"
    TEMPORARY_TABLENAME = "temporary_tablename"

    # Databases
    ADMIN_DATABASE = "admin_database"
    DESTINATION_DATABASE = "destination_database"
    SOURCE_DATABASES = "source_databases"

    # Processing options
    DEBUG_MAX_N_PATIENTS = "debug_max_n_patients"
    DEBUG_PID_LIST = "debug_pid_list"

    # Opting out
    OPTOUT_COL_VALUES = "optout_col_values"
    OPTOUT_MPID_FILENAMES = "optout_mpid_filenames"
    OPTOUT_PID_FILENAMES = "optout_pid_filenames"


class AnonymiseConfigDefaults:
    # Critical field types
    SQLATYPE_MPID = "BigInteger"
    SQLATYPE_PID = "BigInteger"

    # Encryption phrases/passwords
    HASH_METHOD = "HMAC_MD5"

    # Text extraction
    EXTRACT_TEXT_EXTENSIONS_CASE_SENSITIVE = False
    EXTRACT_TEXT_PLAIN = True
    EXTRACT_TEXT_WIDTH = 80

    # Anonymisation
    ALLOW_NO_PATIENT_INFO = False
    ANONYMISE_CODES_AT_WORD_BOUNDARIES_ONLY = True
    ANONYMISE_CODES_AT_NUMERIC_BOUNDARIES_ONLY = True
    ANONYMISE_DATES_AT_WORD_BOUNDARIES_ONLY = True
    ANONYMISE_NUMBERS_AT_NUMERIC_BOUNDARIES_ONLY = True
    ANONYMISE_NUMBERS_AT_WORD_BOUNDARIES_ONLY = False
    ANONYMISE_STRINGS_AT_WORD_BOUNDARIES_ONLY = True
    DENYLIST_FILES_AS_PHRASES = False
    DENYLIST_USE_REGEX = False
    MIN_STRING_LENGTH_FOR_ERRORS = 3
    MIN_STRING_LENGTH_TO_SCRUB_WITH = 2
    NONSPECIFIC_SCRUBBER_FIRST = False
    REPLACE_ALL_DATES_WITH = "[~~~]"
    REPLACE_NONSPECIFIC_INFO_WITH = "[~~~]"
    REPLACE_PATIENT_INFO_WITH = "[__PPP__]"
    REPLACE_THIRD_PARTY_INFO_WITH = "[__TTT__]"
    SCRUB_ALL_DATES = False
    SCRUB_ALL_EMAIL_ADDRESSES = False
    SCRUB_ALL_UK_POSTCODES = False
    STRING_MAX_REGEX_ERRORS = 0
    THIRDPARTY_XREF_MAX_DEPTH = 1
    TIMEFIELD_NAME = "_when_processed_utc"

    # Output fields and formatting
    RESEARCH_ID_FIELDNAME = "rid"
    TRID_FIELDNAME = "trid"
    MASTER_RESEARCH_ID_FIELDNAME = "mrid"
    ADD_MRID_WHEREVER_RID_ADDED = True
    SOURCE_HASH_FIELDNAME = "_src_hash"

    # Destination database configuration
    MAX_ROWS_BEFORE_COMMIT = 1000
    MAX_BYTES_BEFORE_COMMIT = 80 * 1024 * 1024  # 80 Mb
    TEMPORARY_TABLENAME = "_crate_temp_table"

    # Processing options
    DEBUG_MAX_N_PATIENTS = 0


class AnonymiseDatabaseSafeConfigKeys:
    """
    Non-sensitive config keys relating to a specific database.
    """

    DDGEN_ADD_PER_TABLE_PIDS_TO_SCRUBBER = (
        "ddgen_add_per_table_pids_to_scrubber"
    )
    DDGEN_ADDITION_ONLY = "ddgen_addition_only"
    DDGEN_ADDITION_ONLY_TABLES = "ddgen_addition_only_tables"
    DDGEN_ALLOW_FULLTEXT_INDEXING = "ddgen_allow_fulltext_indexing"
    DDGEN_APPEND_SOURCE_INFO_TO_COMMENT = "ddgen_append_source_info_to_comment"
    DDGEN_BINARY_TO_TEXT_FIELD_PAIRS = "ddgen_binary_to_text_field_pairs"
    DDGEN_CONSTANT_CONTENT = "ddgen_constant_content"
    DDGEN_CONSTANT_CONTENT_TABLES = "ddgen_constant_content_tables"
    DDGEN_CONVERT_ODD_CHARS_TO_UNDERSCORE = (
        "ddgen_convert_odd_chars_to_underscore"
    )
    DDGEN_DELETION_POSSIBLE_TABLES = "ddgen_deletion_possible_tables"
    DDGEN_EXTRA_HASH_FIELDS = "ddgen_extra_hash_fields"
    DDGEN_FIELD_ALLOWLIST = "ddgen_field_allowlist"
    DDGEN_FIELD_DENYLIST = "ddgen_field_denylist"
    DDGEN_FILENAME_TO_TEXT_FIELDS = "ddgen_filename_to_text_fields"
    DDGEN_FORCE_LOWER_CASE = "ddgen_force_lower_case"
    DDGEN_FREETEXT_INDEX_MIN_LENGTH = "ddgen_freetext_index_min_length"
    DDGEN_INCLUDE_FIELDS = "ddgen_include_fields"
    DDGEN_INDEX_FIELDS = "ddgen_index_fields"
    DDGEN_MASTER_PID_FIELDNAME = "ddgen_master_pid_fieldname"
    DDGEN_MIN_LENGTH_FOR_SCRUBBING = "ddgen_min_length_for_scrubbing"
    DDGEN_NONCONSTANT_CONTENT_TABLES = "ddgen_nonconstant_content_tables"
    DDGEN_OMIT_BY_DEFAULT = "ddgen_omit_by_default"
    DDGEN_OMIT_FIELDS = "ddgen_omit_fields"
    DDGEN_PATIENT_OPT_OUT_FIELDS = "ddgen_patient_opt_out_fields"
    DDGEN_PER_TABLE_PID_FIELD = "ddgen_per_table_pid_field"
    DDGEN_PID_DEFINING_FIELDNAMES = "ddgen_pid_defining_fieldnames"
    DDGEN_PK_FIELDS = "ddgen_pk_fields"
    DDGEN_PREFER_ORIGINAL_PK = "ddgen_prefer_original_pk"
    DDGEN_RENAME_TABLES_REMOVE_SUFFIXES = "ddgen_rename_tables_remove_suffixes"
    DDGEN_REQUIRED_SCRUBSRC_FIELDS = "ddgen_required_scrubsrc_fields"
    DDGEN_SAFE_FIELDS_EXEMPT_FROM_SCRUBBING = (
        "ddgen_safe_fields_exempt_from_scrubbing"
    )
    DDGEN_SCRUBMETHOD_CODE_FIELDS = "ddgen_scrubmethod_code_fields"
    DDGEN_SCRUBMETHOD_DATE_FIELDS = "ddgen_scrubmethod_date_fields"
    DDGEN_SCRUBMETHOD_NUMBER_FIELDS = "ddgen_scrubmethod_number_fields"
    DDGEN_SCRUBMETHOD_PHRASE_FIELDS = "ddgen_scrubmethod_phrase_fields"
    DDGEN_SCRUBSRC_PATIENT_FIELDS = "ddgen_scrubsrc_patient_fields"
    DDGEN_SCRUBSRC_THIRDPARTY_FIELDS = "ddgen_scrubsrc_thirdparty_fields"
    DDGEN_SCRUBSRC_THIRDPARTY_XREF_PID_FIELDS = (
        "ddgen_scrubsrc_thirdparty_xref_pid_fields"
    )
    DDGEN_SKIP_ROW_IF_EXTRACT_TEXT_FAILS_FIELDS = (
        "ddgen_skip_row_if_extract_text_fails_fields"
    )
    DDGEN_TABLE_ALLOWLIST = "ddgen_table_allowlist"
    DDGEN_TABLE_DEFINES_PIDS = "ddgen_table_defines_pids"
    DDGEN_TABLE_DENYLIST = "ddgen_table_denylist"
    DDGEN_TABLE_REQUIRE_FIELD_ABSOLUTE = "ddgen_table_require_field_absolute"
    DDGEN_TABLE_REQUIRE_FIELD_CONDITIONAL = (
        "ddgen_table_require_field_conditional"
    )
    DDGEN_TRUNCATE_DATE_FIELDS = "ddgen_truncate_date_fields"
    DEBUG_LIMITED_TABLES = "debug_limited_tables"
    DEBUG_ROW_LIMIT = "debug_row_limit"
    DEPRECATED_DDGEN_FIELD_BLACKLIST = "ddgen_field_blacklist"
    DEPRECATED_DDGEN_FIELD_WHITELIST = "ddgen_field_whitelist"
    DEPRECATED_DDGEN_TABLE_BLACKLIST = "ddgen_table_blacklist"
    DEPRECATED_DDGEN_TABLE_WHITELIST = "ddgen_table_whitelist"


class AnonymiseDatabaseSafeConfigDefaults:
    """
    Defaults for the keys above
    """

    DDGEN_ADD_PER_TABLE_PIDS_TO_SCRUBBER = False
    DDGEN_ADDITION_ONLY = False
    DDGEN_ALLOW_FULLTEXT_INDEXING = True
    DDGEN_APPEND_SOURCE_INFO_TO_COMMENT = True
    DDGEN_CONSTANT_CONTENT = False
    DDGEN_CONVERT_ODD_CHARS_TO_UNDERSCORE = True
    DDGEN_FORCE_LOWER_CASE = False
    DDGEN_FREETEXT_INDEX_MIN_LENGTH = 1000
    DDGEN_MIN_LENGTH_FOR_SCRUBBING = 50
    DDGEN_OMIT_BY_DEFAULT = True
    DDGEN_PREFER_ORIGINAL_PK = False
    DEBUG_ROW_LIMIT = 0


class AnonymiseColumnComments:
    TIMEFIELD_COMMENT = "Date/time that CRATE processed the source row (UTC)"


class HashConfigKeys:
    """
    Config file keys for defining extra hashers.
    """

    HASH_METHOD = "hash_method"
    SECRET_KEY = "secret_key"


# =============================================================================
# Demo config
# =============================================================================
# This does not need to vary with Docker status.

_AK = AnonymiseConfigKeys
_DA = AnonymiseConfigDefaults
_DK = DatabaseConfigKeys
_SK = AnonymiseDatabaseSafeConfigKeys
_DS = AnonymiseDatabaseSafeConfigDefaults
# noinspection PyPep8
DEMO_CONFIG = rf"""# Configuration file for CRATE anonymiser (crate_anonymise).
# Version {CRATE_VERSION} ({CRATE_VERSION_DATE}).
#
# SEE HELP FOR DETAILS.

# =============================================================================
# Main settings
# =============================================================================

[{_AK.SECTION_MAIN}]

# -----------------------------------------------------------------------------
# Data dictionary
# -----------------------------------------------------------------------------

{_AK.DATA_DICTIONARY_FILENAME} = @@data_dictionary_filename@@

# -----------------------------------------------------------------------------
# Critical field types
# -----------------------------------------------------------------------------

{_AK.SQLATYPE_PID} =
{_AK.SQLATYPE_MPID} =

# -----------------------------------------------------------------------------
# Encryption phrases/passwords
# -----------------------------------------------------------------------------

{_AK.HASH_METHOD} = {_DA.HASH_METHOD}
{_AK.PER_TABLE_PATIENT_ID_ENCRYPTION_PHRASE} = @@per_table_patient_id_encryption_phrase@@
{_AK.MASTER_PATIENT_ID_ENCRYPTION_PHRASE} = @@master_patient_id_encryption_phrase@@
{_AK.CHANGE_DETECTION_ENCRYPTION_PHRASE} = @@change_detection_encryption_phrase@@
{_AK.EXTRA_HASH_CONFIG_SECTIONS} =

# -----------------------------------------------------------------------------
# Text extraction
# -----------------------------------------------------------------------------

{_AK.EXTRACT_TEXT_EXTENSIONS_PERMITTED} =
{_AK.EXTRACT_TEXT_EXTENSIONS_PROHIBITED} =
{_AK.EXTRACT_TEXT_EXTENSIONS_CASE_SENSITIVE} = {_DA.EXTRACT_TEXT_EXTENSIONS_CASE_SENSITIVE}
{_AK.EXTRACT_TEXT_PLAIN} = {_DA.EXTRACT_TEXT_PLAIN}
{_AK.EXTRACT_TEXT_WIDTH} = {_DA.EXTRACT_TEXT_WIDTH}

# -----------------------------------------------------------------------------
# Anonymisation
# -----------------------------------------------------------------------------

{_AK.ALLOW_NO_PATIENT_INFO} = {_DA.ALLOW_NO_PATIENT_INFO}
{_AK.REPLACE_ALL_DATES_WITH} = {_DA.REPLACE_ALL_DATES_WITH}
{_AK.REPLACE_PATIENT_INFO_WITH} = {_DA.REPLACE_PATIENT_INFO_WITH}
{_AK.REPLACE_THIRD_PARTY_INFO_WITH} = {_DA.REPLACE_THIRD_PARTY_INFO_WITH}
{_AK.REPLACE_NONSPECIFIC_INFO_WITH} = {_DA.REPLACE_NONSPECIFIC_INFO_WITH}
{_AK.THIRDPARTY_XREF_MAX_DEPTH} = {_DA.THIRDPARTY_XREF_MAX_DEPTH}
{_AK.SCRUB_STRING_SUFFIXES} =
    s
{_AK.STRING_MAX_REGEX_ERRORS} = {_DA.STRING_MAX_REGEX_ERRORS}
{_AK.MIN_STRING_LENGTH_FOR_ERRORS} = {_DA.MIN_STRING_LENGTH_FOR_ERRORS}
{_AK.MIN_STRING_LENGTH_TO_SCRUB_WITH} = {_DA.MIN_STRING_LENGTH_TO_SCRUB_WITH}
{_AK.ALLOWLIST_FILENAMES} =
{_AK.DENYLIST_FILENAMES} =
{_AK.DENYLIST_FILES_AS_PHRASES} = {_DA.DENYLIST_FILES_AS_PHRASES}
{_AK.DENYLIST_USE_REGEX} = {_DA.DENYLIST_USE_REGEX}
{_AK.PHRASE_ALTERNATIVE_WORD_FILENAMES} =
{_AK.SCRUB_ALL_DATES} = {_DA.SCRUB_ALL_DATES}
{_AK.SCRUB_ALL_EMAIL_ADDRESSES} = {_DA.SCRUB_ALL_EMAIL_ADDRESSES}
{_AK.SCRUB_ALL_NUMBERS_OF_N_DIGITS} =
{_AK.SCRUB_ALL_UK_POSTCODES} = {_DA.SCRUB_ALL_UK_POSTCODES}
{_AK.NONSPECIFIC_SCRUBBER_FIRST} = {_DA.NONSPECIFIC_SCRUBBER_FIRST}
{_AK.ANONYMISE_CODES_AT_WORD_BOUNDARIES_ONLY} = {_DA.ANONYMISE_CODES_AT_WORD_BOUNDARIES_ONLY}
{_AK.ANONYMISE_CODES_AT_NUMERIC_BOUNDARIES_ONLY} = {_DA.ANONYMISE_CODES_AT_NUMERIC_BOUNDARIES_ONLY}
{_AK.ANONYMISE_DATES_AT_WORD_BOUNDARIES_ONLY} = {_DA.ANONYMISE_DATES_AT_WORD_BOUNDARIES_ONLY}
{_AK.ANONYMISE_NUMBERS_AT_WORD_BOUNDARIES_ONLY} = {_DA.ANONYMISE_NUMBERS_AT_WORD_BOUNDARIES_ONLY}
{_AK.ANONYMISE_NUMBERS_AT_NUMERIC_BOUNDARIES_ONLY} = {_DA.ANONYMISE_NUMBERS_AT_NUMERIC_BOUNDARIES_ONLY}
{_AK.ANONYMISE_STRINGS_AT_WORD_BOUNDARIES_ONLY} = {_DA.ANONYMISE_STRINGS_AT_WORD_BOUNDARIES_ONLY}

# -----------------------------------------------------------------------------
# Output fields and formatting
# -----------------------------------------------------------------------------

{_AK.TIMEFIELD_NAME} = {_DA.TIMEFIELD_NAME}
{_AK.RESEARCH_ID_FIELDNAME} = {_DA.RESEARCH_ID_FIELDNAME}
{_AK.TRID_FIELDNAME} = {_DA.TRID_FIELDNAME}
{_AK.MASTER_RESEARCH_ID_FIELDNAME} = {_DA.MASTER_RESEARCH_ID_FIELDNAME}
{_AK.SOURCE_HASH_FIELDNAME} = {_DA.SOURCE_HASH_FIELDNAME}

# -----------------------------------------------------------------------------
# Destination database configuration
# See the [destination_database] section for connection details.
# -----------------------------------------------------------------------------

{_AK.MAX_ROWS_BEFORE_COMMIT} = {_DA.MAX_ROWS_BEFORE_COMMIT}
{_AK.MAX_BYTES_BEFORE_COMMIT} = {_DA.MAX_BYTES_BEFORE_COMMIT}
{_AK.TEMPORARY_TABLENAME} = {_DA.TEMPORARY_TABLENAME}

# -----------------------------------------------------------------------------
# Choose databases (defined in their own sections).
# -----------------------------------------------------------------------------

{_AK.SOURCE_DATABASES} =
    sourcedb1
#    sourcedb2
{_AK.DESTINATION_DATABASE} = destination_database
{_AK.ADMIN_DATABASE} = admin_database

# -----------------------------------------------------------------------------
# PROCESSING OPTIONS, TO LIMIT DATA QUANTITY FOR TESTING
# -----------------------------------------------------------------------------

{_AK.DEBUG_MAX_N_PATIENTS} =
{_AK.DEBUG_PID_LIST} =

# -----------------------------------------------------------------------------
# Opting out entirely
# -----------------------------------------------------------------------------

{_AK.OPTOUT_PID_FILENAMES} =
{_AK.OPTOUT_MPID_FILENAMES} =
{_AK.OPTOUT_COL_VALUES} =


# =============================================================================
# Extra regular expression patterns you wish to be scrubbed from the text
# as nonspecific information. See help.
# =============================================================================

[{_AK.SECTION_EXTRA_REGEXES}]


# =============================================================================
# Destination database details. User should have WRITE access.
# =============================================================================

[destination_database]

{_DK.URL} = @@dest_db_url@@


# =============================================================================
# Administrative database. User should have WRITE access.
# =============================================================================

[admin_database]

{_DK.URL} = @@admin_db_url@@


# =============================================================================
# SOURCE DATABASE DETAILS BELOW HERE.
# User should have READ access only for safety.
# =============================================================================

# -----------------------------------------------------------------------------
# Source database example 1
# -----------------------------------------------------------------------------

[sourcedb1]

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # CONNECTION DETAILS
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

{_DK.URL} = @@source_db1_url@@

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # INPUT FIELDS, FOR THE AUTOGENERATION OF DATA DICTIONARIES
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

{_SK.DDGEN_OMIT_BY_DEFAULT} = {_DS.DDGEN_OMIT_BY_DEFAULT}
{_SK.DDGEN_OMIT_FIELDS} =
{_SK.DDGEN_INCLUDE_FIELDS} =  @@source_db1_ddgen_include_fields@@
{_SK.DDGEN_PER_TABLE_PID_FIELD} = patient_id
{_SK.DDGEN_TABLE_DEFINES_PIDS} = patient
{_SK.DDGEN_ADD_PER_TABLE_PIDS_TO_SCRUBBER} = {_DS.DDGEN_ADD_PER_TABLE_PIDS_TO_SCRUBBER}
{_SK.DDGEN_MASTER_PID_FIELDNAME} = nhsnum
{_SK.DDGEN_TABLE_DENYLIST} =
{_SK.DDGEN_TABLE_ALLOWLIST} =
{_SK.DDGEN_TABLE_REQUIRE_FIELD_ABSOLUTE} =
{_SK.DDGEN_TABLE_REQUIRE_FIELD_CONDITIONAL} =
{_SK.DDGEN_FIELD_DENYLIST} =
{_SK.DDGEN_FIELD_ALLOWLIST} =
{_SK.DDGEN_PK_FIELDS} =
{_SK.DDGEN_PREFER_ORIGINAL_PK} = {_DS.DDGEN_PREFER_ORIGINAL_PK}
{_SK.DDGEN_CONSTANT_CONTENT} = {_DS.DDGEN_CONSTANT_CONTENT}
{_SK.DDGEN_CONSTANT_CONTENT_TABLES} =
{_SK.DDGEN_NONCONSTANT_CONTENT_TABLES} =
{_SK.DDGEN_ADDITION_ONLY} = {_DS.DDGEN_ADDITION_ONLY}
{_SK.DDGEN_ADDITION_ONLY_TABLES} =
{_SK.DDGEN_DELETION_POSSIBLE_TABLES} =
{_SK.DDGEN_PID_DEFINING_FIELDNAMES} =
{_SK.DDGEN_SCRUBSRC_PATIENT_FIELDS} = @@source_db1_ddgen_scrubsrc_patient_fields@@
{_SK.DDGEN_SCRUBSRC_THIRDPARTY_FIELDS} =
{_SK.DDGEN_SCRUBSRC_THIRDPARTY_XREF_PID_FIELDS} =
{_SK.DDGEN_REQUIRED_SCRUBSRC_FIELDS} =
{_SK.DDGEN_SCRUBMETHOD_CODE_FIELDS} =
{_SK.DDGEN_SCRUBMETHOD_DATE_FIELDS} =
{_SK.DDGEN_SCRUBMETHOD_NUMBER_FIELDS} =
{_SK.DDGEN_SCRUBMETHOD_PHRASE_FIELDS} =
{_SK.DDGEN_SAFE_FIELDS_EXEMPT_FROM_SCRUBBING} =
{_SK.DDGEN_MIN_LENGTH_FOR_SCRUBBING} = {_DS.DDGEN_MIN_LENGTH_FOR_SCRUBBING}
{_SK.DDGEN_TRUNCATE_DATE_FIELDS} =
{_SK.DDGEN_FILENAME_TO_TEXT_FIELDS} =
{_SK.DDGEN_BINARY_TO_TEXT_FIELD_PAIRS} =
{_SK.DDGEN_SKIP_ROW_IF_EXTRACT_TEXT_FAILS_FIELDS} =
{_SK.DDGEN_RENAME_TABLES_REMOVE_SUFFIXES} =
{_SK.DDGEN_PATIENT_OPT_OUT_FIELDS} =
{_SK.DDGEN_EXTRA_HASH_FIELDS} =

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # DESTINATION INDEXING
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

{_SK.DDGEN_INDEX_FIELDS} =
{_SK.DDGEN_ALLOW_FULLTEXT_INDEXING} = {_DS.DDGEN_ALLOW_FULLTEXT_INDEXING}

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # DATA DICTIONARY MANIPULATION TO DESTINATION TABLE/FIELD NAMES
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

{_SK.DDGEN_FORCE_LOWER_CASE} = {_DS.DDGEN_FORCE_LOWER_CASE}
{_SK.DDGEN_CONVERT_ODD_CHARS_TO_UNDERSCORE} = {_DS.DDGEN_CONVERT_ODD_CHARS_TO_UNDERSCORE}

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # PROCESSING OPTIONS, TO LIMIT DATA QUANTITY FOR TESTING
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

{_SK.DEBUG_ROW_LIMIT} =
{_SK.DEBUG_LIMITED_TABLES} =

# -----------------------------------------------------------------------------
# Source database example 2
# -----------------------------------------------------------------------------

[mysourcedb2]

{_DK.URL} = mysql+mysqldb://username:password@127.0.0.1:3306/source2_databasename?charset=utf8

{_SK.DDGEN_FORCE_LOWER_CASE} = {_DS.DDGEN_FORCE_LOWER_CASE}
{_SK.DDGEN_APPEND_SOURCE_INFO_TO_COMMENT} = {_DS.DDGEN_APPEND_SOURCE_INFO_TO_COMMENT}
{_SK.DDGEN_PER_TABLE_PID_FIELD} = patient_id
{_SK.DDGEN_MASTER_PID_FIELDNAME} = nhsnum
{_SK.DDGEN_TABLE_DENYLIST} =
{_SK.DDGEN_FIELD_DENYLIST} =
{_SK.DDGEN_TABLE_REQUIRE_FIELD_ABSOLUTE} =
{_SK.DDGEN_TABLE_REQUIRE_FIELD_CONDITIONAL} =
{_SK.DDGEN_PK_FIELDS} =
{_SK.DDGEN_PREFER_ORIGINAL_PK} = {_DS.DDGEN_PREFER_ORIGINAL_PK}
{_SK.DDGEN_CONSTANT_CONTENT} = {_DS.DDGEN_CONSTANT_CONTENT}
{_SK.DDGEN_SCRUBSRC_PATIENT_FIELDS} =
{_SK.DDGEN_SCRUBSRC_THIRDPARTY_FIELDS} =
{_SK.DDGEN_SCRUBMETHOD_CODE_FIELDS} =
{_SK.DDGEN_SCRUBMETHOD_DATE_FIELDS} =
{_SK.DDGEN_SCRUBMETHOD_NUMBER_FIELDS} =
{_SK.DDGEN_SCRUBMETHOD_PHRASE_FIELDS} =
{_SK.DDGEN_SAFE_FIELDS_EXEMPT_FROM_SCRUBBING} =
{_SK.DDGEN_MIN_LENGTH_FOR_SCRUBBING} = {_DS.DDGEN_MIN_LENGTH_FOR_SCRUBBING}
{_SK.DDGEN_TRUNCATE_DATE_FIELDS} =
{_SK.DDGEN_FILENAME_TO_TEXT_FIELDS} =
{_SK.DDGEN_BINARY_TO_TEXT_FIELD_PAIRS} =

# -----------------------------------------------------------------------------
# Source database example 3
# -----------------------------------------------------------------------------

[camcops]
# Example for the CamCOPS anonymisation staging database

{_DK.URL} = mysql+mysqldb://username:password@127.0.0.1:3306/camcops_databasename?charset=utf8

# FOR EXAMPLE:
{_SK.DDGEN_FORCE_LOWER_CASE} = False
{_SK.DDGEN_PER_TABLE_PID_FIELD} = _patient_idnum1
{_SK.DDGEN_PID_DEFINING_FIELDNAMES} = _patient_idnum1
{_SK.DDGEN_MASTER_PID_FIELDNAME} = _patient_idnum2
{_SK.DDGEN_TABLE_DENYLIST} =
{_SK.DDGEN_FIELD_DENYLIST} = _patient_iddesc1
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

{_SK.DDGEN_TABLE_REQUIRE_FIELD_ABSOLUTE} =
{_SK.DDGEN_TABLE_REQUIRE_FIELD_CONDITIONAL} =
{_SK.DDGEN_PK_FIELDS} = _pk
{_SK.DDGEN_PREFER_ORIGINAL_PK} = {_DS.DDGEN_PREFER_ORIGINAL_PK}
{_SK.DDGEN_CONSTANT_CONTENT} = False
{_SK.DDGEN_SCRUBSRC_PATIENT_FIELDS} = _patient_forename
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
{_SK.DDGEN_SCRUBSRC_THIRDPARTY_FIELDS} =
{_SK.DDGEN_SCRUBMETHOD_CODE_FIELDS} =
{_SK.DDGEN_SCRUBMETHOD_DATE_FIELDS} = _patient_dob
{_SK.DDGEN_SCRUBMETHOD_NUMBER_FIELDS} =
{_SK.DDGEN_SCRUBMETHOD_PHRASE_FIELDS} =
{_SK.DDGEN_SAFE_FIELDS_EXEMPT_FROM_SCRUBBING} = _device
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
{_SK.DDGEN_MIN_LENGTH_FOR_SCRUBBING} = {_DS.DDGEN_MIN_LENGTH_FOR_SCRUBBING}
{_SK.DDGEN_TRUNCATE_DATE_FIELDS} = _patient_dob
{_SK.DDGEN_FILENAME_TO_TEXT_FIELDS} =
{_SK.DDGEN_BINARY_TO_TEXT_FIELD_PAIRS} =

"""  # noqa: E501

# For the style:
#       [source_databases]
#       source1 = blah
#       source2 = thing
# ... you can't have multiple keys with the same name.
# https://stackoverflow.com/questions/287757


class PatientInfoConstants:
    SECRET_MAP_TABLENAME = "secret_map"
    PID_FIELDNAME = "pid"
    MPID_FIELDNAME = "mpid"
    RID_FIELDNAME = "rid"
    MRID_FIELDNAME = "mrid"
    TRID_FIELDNAME = "trid"
