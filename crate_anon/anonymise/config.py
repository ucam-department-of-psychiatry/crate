#!/usr/bin/env python

"""
crate_anon/anonymise/config.py

===============================================================================

    Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).

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

**Config class for CRATE anonymiser.**

Thoughts on configuration method

-   First version used a ``Config()`` class, which initializes with blank
    values. The ``anonymise_cli.py`` file creates a config singleton and passes
    it around. Then when its ``set()`` method is called, it reads a config file
    and instantiates its settings. An option exists to print a draft config
    without ever reading one from disk.

    Advantage: easy to start the program without a valid config file (e.g. to
    print one).

    Disadvantage: modules can't be sure that a config is properly instantiated
    before they are loaded, so you can't easily define a class according to
    config settings (you'd have to have a class factory, which gets ugly).

-   The Django method is to have a configuration file (e.g. ``settings.py``,
    which can import from other things) that is read by Django and then becomes
    importable by anything at startup as ``django.conf.settings``. (I've added
    local settings via an environment variable.) The way Django knows where to
    look is via this in ``manage.py``:

    .. code-block:: python

        os.environ.setdefault("DJANGO_SETTINGS_MODULE",
                              "crate_anon.crateweb.config.settings")

    Advantage: setting the config file via an environment variable (read when
    the config file loads) allows guaranteed config existence as other modules
    start.

    Further advantage: config filenames not on command line, therefore not
    visible to ``ps``.

    Disadvantage: how do you override with a command-line (argparse) setting?
    .. though: who cares?

    To print a config using that file: raise an exception on nonexistent
    config, and catch it with a special entry point script.

-   See also
    https://stackoverflow.com/questions/7443366/argument-passing-strategy-environment-variables-vs-command-line

"""  # noqa

# =============================================================================
# Imports
# =============================================================================

import fnmatch
from io import StringIO
import logging
import os
import sys
import traceback
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING, Union, Set

from cardinal_pythonlib.hash import GenericHasher, make_hasher
from cardinal_pythonlib.logs import remove_all_logger_handlers
from cardinal_pythonlib.sql.validation import (
    ensure_valid_field_name,
    ensure_valid_table_name,
)
from cardinal_pythonlib.sqlalchemy.schema import (
    hack_in_mssql_xml_type,
    is_sqlatype_integer,
)
from cardinal_pythonlib.sizeformatter import sizeof_fmt
from cardinal_pythonlib.sqlalchemy.insert_on_duplicate import (
    monkeypatch_TableClause,
)
import regex
from sqlalchemy import BigInteger, create_engine, String
from sqlalchemy.dialects.mssql.base import dialect as ms_sql_server_dialect
from sqlalchemy.dialects.mysql.base import dialect as mysql_dialect
from sqlalchemy.engine.base import Engine
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.sql.sqltypes import TypeEngine

# noinspection PyPep8Naming
from crate_anon.anonymise.constants import (
    ANON_CONFIG_ENV_VAR,
    AnonymiseConfigDefaults as DA,
    AnonymiseConfigKeys as AK,
    AnonymiseDatabaseSafeConfigDefaults as DS,
    AnonymiseDatabaseSafeConfigKeys as SK,
    DEFAULT_CHUNKSIZE,
    DEFAULT_REPORT_EVERY,
    DEMO_CONFIG,
    HashConfigKeys as HK,
    SEP,
)
from crate_anon.anonymise.dd import DataDictionary
from crate_anon.anonymise.scrub import (
    NonspecificScrubber,
    WordList,
)
from crate_anon.common.constants import RUNNING_WITHOUT_CONFIG
from crate_anon.common.extendedconfigparser import (
    ConfigSection,
    ExtendedConfigParser,
)
from crate_anon.common.sql import TransactionSizeLimiter
from crate_anon.nlp_manager.constants import DatabaseConfigKeys

if TYPE_CHECKING:
    from crate_anon.anonymise.dbholder import DatabaseHolder

log = logging.getLogger(__name__)

# The Config class is loaded very early, via the nasty singleton.
# This is therefore the appropriate moment to make any changes to SQLAlchemy.
monkeypatch_TableClause()
hack_in_mssql_xml_type()  # support XML type under SQL Server


# =============================================================================
# Config/databases
# =============================================================================

class DatabaseSafeConfig(object):
    """
    Class representing non-sensitive configuration information about a
    source database.
    """

    def __init__(self, parser: ExtendedConfigParser, section: str) -> None:
        """
        Read from a configparser section.

        Args:
            parser: configparser object
            section: section name
        """
        cfg = ConfigSection(section=section, parser=parser)

        cfg.require_absent(
            SK.DEPRECATED_DDGEN_TABLE_BLACKLIST,
            f"Replace {SK.DEPRECATED_DDGEN_TABLE_BLACKLIST!r} with "
            f"{SK.DDGEN_TABLE_DENYLIST!r}"
        )
        cfg.require_absent(
            SK.DEPRECATED_DDGEN_TABLE_WHITELIST,
            f"Replace {SK.DEPRECATED_DDGEN_TABLE_WHITELIST!r} with "
            f"{SK.DDGEN_TABLE_ALLOWLIST!r}"
        )
        cfg.require_absent(
            SK.DEPRECATED_DDGEN_FIELD_BLACKLIST,
            f"Replace {SK.DEPRECATED_DDGEN_FIELD_BLACKLIST!r} with "
            f"{SK.DDGEN_FIELD_DENYLIST!r}"
        )
        cfg.require_absent(
            SK.DEPRECATED_DDGEN_FIELD_WHITELIST,
            f"Replace {SK.DEPRECATED_DDGEN_FIELD_WHITELIST!r} with "
            f"{SK.DDGEN_FIELD_ALLOWLIST!r}"
        )

        self.ddgen_append_source_info_to_comment = cfg.opt_bool(
            SK.DDGEN_APPEND_SOURCE_INFO_TO_COMMENT,
            DS.DDGEN_APPEND_SOURCE_INFO_TO_COMMENT)
        self.ddgen_omit_by_default = cfg.opt_bool(
            SK.DDGEN_OMIT_BY_DEFAULT,
            DS.DDGEN_OMIT_BY_DEFAULT)
        self.ddgen_omit_fields = cfg.opt_multiline(SK.DDGEN_OMIT_FIELDS)
        self.ddgen_include_fields = cfg.opt_multiline(SK.DDGEN_INCLUDE_FIELDS)

        self.ddgen_per_table_pid_field = cfg.opt_str(
            SK.DDGEN_PER_TABLE_PID_FIELD)
        self.ddgen_table_defines_pids = cfg.opt_str(
            SK.DDGEN_TABLE_DEFINES_PIDS)
        self.ddgen_add_per_table_pids_to_scrubber = cfg.opt_bool(
            SK.DDGEN_ADD_PER_TABLE_PIDS_TO_SCRUBBER,
            DS.DDGEN_ADD_PER_TABLE_PIDS_TO_SCRUBBER)
        self.ddgen_master_pid_fieldname = cfg.opt_str(
            SK.DDGEN_MASTER_PID_FIELDNAME)
        self.ddgen_table_denylist = cfg.opt_multiline(
            SK.DDGEN_TABLE_DENYLIST)
        self.ddgen_table_allowlist = cfg.opt_multiline(
            SK.DDGEN_TABLE_ALLOWLIST)
        self.ddgen_table_require_field_absolute = cfg.opt_multiline(
            SK.DDGEN_TABLE_REQUIRE_FIELD_ABSOLUTE)
        self.ddgen_table_require_field_conditional = \
            cfg.opt_multiline_csv_pairs(
                SK.DDGEN_TABLE_REQUIRE_FIELD_CONDITIONAL)
        self.ddgen_field_denylist = cfg.opt_multiline(
            SK.DDGEN_FIELD_DENYLIST)
        self.ddgen_field_allowlist = cfg.opt_multiline(
            SK.DDGEN_FIELD_ALLOWLIST)
        self.ddgen_pk_fields = cfg.opt_multiline(SK.DDGEN_PK_FIELDS)

        self.ddgen_constant_content = cfg.opt_bool(
            SK.DDGEN_CONSTANT_CONTENT,
            DS.DDGEN_CONSTANT_CONTENT)
        self.ddgen_constant_content_tables = cfg.opt_str(
            SK.DDGEN_CONSTANT_CONTENT_TABLES)
        self.ddgen_nonconstant_content_tables = cfg.opt_str(
            SK.DDGEN_NONCONSTANT_CONTENT_TABLES)
        self.ddgen_addition_only = cfg.opt_bool(
            SK.DDGEN_ADDITION_ONLY,
            DS.DDGEN_ADDITION_ONLY)
        self.ddgen_addition_only_tables = cfg.opt_str(
            SK.DDGEN_ADDITION_ONLY_TABLES)
        self.ddgen_deletion_possible_tables = cfg.opt_str(
            SK.DDGEN_DELETION_POSSIBLE_TABLES)

        self.ddgen_pid_defining_fieldnames = cfg.opt_multiline(
            SK.DDGEN_PID_DEFINING_FIELDNAMES)
        self.ddgen_scrubsrc_patient_fields = cfg.opt_multiline(
            SK.DDGEN_SCRUBSRC_PATIENT_FIELDS)
        self.ddgen_scrubsrc_thirdparty_fields = cfg.opt_multiline(
            SK.DDGEN_SCRUBSRC_THIRDPARTY_FIELDS)
        self.ddgen_scrubsrc_thirdparty_xref_pid_fields = cfg.opt_multiline(
            SK.DDGEN_SCRUBSRC_THIRDPARTY_XREF_PID_FIELDS)
        self.ddgen_required_scrubsrc_fields = cfg.opt_multiline(
            SK.DDGEN_REQUIRED_SCRUBSRC_FIELDS)
        self.ddgen_scrubmethod_code_fields = cfg.opt_multiline(
            SK.DDGEN_SCRUBMETHOD_CODE_FIELDS)
        self.ddgen_scrubmethod_date_fields = cfg.opt_multiline(
            SK.DDGEN_SCRUBMETHOD_DATE_FIELDS)
        self.ddgen_scrubmethod_number_fields = cfg.opt_multiline(
            SK.DDGEN_SCRUBMETHOD_NUMBER_FIELDS)
        self.ddgen_scrubmethod_phrase_fields = cfg.opt_multiline(
            SK.DDGEN_SCRUBMETHOD_PHRASE_FIELDS)
        self.ddgen_safe_fields_exempt_from_scrubbing = cfg.opt_multiline(
            SK.DDGEN_SAFE_FIELDS_EXEMPT_FROM_SCRUBBING)
        self.ddgen_min_length_for_scrubbing = cfg.opt_int(
            SK.DDGEN_MIN_LENGTH_FOR_SCRUBBING,
            DS.DDGEN_MIN_LENGTH_FOR_SCRUBBING)

        self.ddgen_truncate_date_fields = cfg.opt_multiline(
            SK.DDGEN_TRUNCATE_DATE_FIELDS)
        self.ddgen_filename_to_text_fields = cfg.opt_multiline(
            SK.DDGEN_FILENAME_TO_TEXT_FIELDS)

        self.bin2text_dict = cfg.opt_multiline_csv_pairs(
            SK.DDGEN_BINARY_TO_TEXT_FIELD_PAIRS)
        self.ddgen_skip_row_if_extract_text_fails_fields = cfg.opt_multiline(
            SK.DDGEN_SKIP_ROW_IF_EXTRACT_TEXT_FAILS_FIELDS)
        self.ddgen_rename_tables_remove_suffixes = cfg.opt_multiline(
            SK.DDGEN_RENAME_TABLES_REMOVE_SUFFIXES, as_words=True)

        self.ddgen_index_fields = cfg.opt_multiline(SK.DDGEN_INDEX_FIELDS)
        self.ddgen_allow_fulltext_indexing = cfg.opt_bool(
            SK.DDGEN_ALLOW_FULLTEXT_INDEXING,
            DS.DDGEN_ALLOW_FULLTEXT_INDEXING)
        self.ddgen_freetext_index_min_length = cfg.opt_int(
            SK.DDGEN_FREETEXT_INDEX_MIN_LENGTH,
            DS.DDGEN_FREETEXT_INDEX_MIN_LENGTH)

        self.ddgen_force_lower_case = cfg.opt_bool(
            SK.DDGEN_FORCE_LOWER_CASE,
            DS.DDGEN_FORCE_LOWER_CASE)
        self.ddgen_convert_odd_chars_to_underscore = cfg.opt_bool(
            SK.DDGEN_CONVERT_ODD_CHARS_TO_UNDERSCORE,
            DS.DDGEN_CONVERT_ODD_CHARS_TO_UNDERSCORE)

        self.debug_row_limit = cfg.opt_int(
            SK.DEBUG_ROW_LIMIT,
            DS.DEBUG_ROW_LIMIT)
        self.debug_limited_tables = cfg.opt_multiline(SK.DEBUG_LIMITED_TABLES)

        self.ddgen_patient_opt_out_fields = cfg.opt_multiline(
            SK.DDGEN_PATIENT_OPT_OUT_FIELDS)

        self.ddgen_extra_hash_fields = cfg.opt_multiline_csv_pairs(
            SK.DDGEN_EXTRA_HASH_FIELDS)
        # ... key: fieldspec
        # ... value: hash_config_section_name

        self.pidtype = BigInteger()
        self.mpidtype = BigInteger()

    def is_table_denied(self, table: str) -> bool:
        """
        Is the table name denylisted (and not also allowlisted)?
        """
        for allow in self.ddgen_table_allowlist:
            r = regex.compile(fnmatch.translate(allow), regex.IGNORECASE)
            if r.match(table):
                return False
        for deny in self.ddgen_table_denylist:
            r = regex.compile(fnmatch.translate(deny), regex.IGNORECASE)
            if r.match(table):
                return True
        return False

    def is_field_denied(self, field: str) -> bool:
        """
        Is the field name denylisted (and not also allowlisted)?
        """
        for allow in self.ddgen_field_allowlist:
            r = regex.compile(fnmatch.translate(allow), regex.IGNORECASE)
            if r.match(field):
                return True
        for deny in self.ddgen_field_denylist:
            r = regex.compile(fnmatch.translate(deny), regex.IGNORECASE)
            if r.match(field):
                return True
        return False

    def does_table_fail_minimum_fields(self, colnames: List[str]) -> bool:
        """
        For use when creating a data dictionary automatically:

        Does a table with the specified column names fail our minimum
        requirements? These requirements are set by our
        ``ddgen_table_require_field_absolute`` and
        ``ddgen_table_require_field_conditional`` configuration parameters.

        Args:
            colnames: list of column names for the table

        Returns:
            does it fail?
        """
        for abs_req in self.ddgen_table_require_field_absolute:
            if abs_req not in colnames:
                log.debug(f"Table fails minimum field requirements: no column "
                          f"named {abs_req!r}")
                return True
        for if_field, then_field in self.ddgen_table_require_field_conditional.items():  # noqa
            if if_field in colnames and then_field not in colnames:
                log.debug(f"Table fails minimum field requirements: "
                          f"field {if_field!r} present but "
                          f"field {then_field!r} absent")
                return True
        return False


# =============================================================================
# ExtraHashconfig
# =============================================================================

def get_extra_hasher(parser: ExtendedConfigParser,
                     section: str) -> GenericHasher:
    """
    Read hasher configuration from a configparser section, and return the
    hasher.

    Args:
        parser: configparser object
        section: section name

    Returns:
        the hasher
    """
    cfg = ConfigSection(section=section, parser=parser)
    hash_method = cfg.opt_str(HK.HASH_METHOD, required=True)
    secret_key = cfg.opt_str(HK.SECRET_KEY, required=True)
    return make_hasher(hash_method, secret_key)


# =============================================================================
# WordAlternatives
# =============================================================================

def get_word_alternatives(filenames: List[str]) -> List[List[str]]:
    """
    Reads in a list of word alternatives, from one or more
    comma-separated-value (CSV) text files (also accepting comment lines
    starting with #, and allowing different numbers of columns on different
    lines).

    All entries on one line will be substituted for each other, if alternatives
    are enabled.

    Produces a list of equivalent-word lists.

    Arbitrarily, uses upper case internally. (All CRATE regex replacements are
    case-insensitive.)

    An alternatives file might look like this:

    .. code-block:: none

        # Street types
        # https://en.wikipedia.org/wiki/Street_suffix

        avenue, circus, close, crescent, drive, gardens, grove, hill, lane, mead, mews, place, rise, road, row, square, street, vale, way, wharf

    Args:
        filenames: filenames to read from

    Returns:
        a list of lists of equivalent words

    """  # noqa
    alternatives = []  # type: List[List[str]]
    all_words_seen = set()  # type: Set[str]
    for filename in filenames:
        with open(filename, "r") as alt_file:
            for line in alt_file:
                line = line.strip()
                if not line:  # blank line
                    continue
                if line.startswith("#"):  # comment line
                    continue
                equivalent_words = [w.strip().upper() for w in line.split(",")]
                equivalent_words = [w for w in equivalent_words if w]  # remove empties  # noqa
                if len(equivalent_words) < 2:
                    continue
                for w in equivalent_words:
                    if w in all_words_seen:
                        raise ValueError(f"Word {w!r} appears twice in "
                                         f"alternatives list! Invalid")
                    all_words_seen.add(w)
                alternatives.append(equivalent_words)
    return alternatives


# =============================================================================
# get_sqlatype
# =============================================================================

def get_sqlatype(sqlatype: str) -> TypeEngine:
    """
    Converts a string, like "VARCHAR(10)", to an SQLAlchemy type.

    Since we might have to return String(length=...), we have to return
    an instance, not a class.
    """
    if sqlatype == "BigInteger":
        return BigInteger()
    r = regex.compile(r"String\((\d+)\)")  # e.g. String(50)
    try:
        m = r.match(sqlatype)
        length = int(m.group(1))
        return String(length)
    except (AttributeError, ValueError):
        raise ValueError(f"Bad SQLAlchemy type specification for "
                         f"PID/MPID columns: {sqlatype!r}")


# =============================================================================
# Config
# =============================================================================

class Config(object):
    """
    Class representing the main CRATE anonymiser configuration.
    """

    def __init__(self,
                 open_databases: bool = True,
                 mock: bool = False) -> None:
        """
        Read the config from the file specified in the ``CRATE_ANON_CONFIG``
        environment variable.

        Args:
            open_databases: open SQLAlchemy connections to the databases?
            mock: create mock (dummy) config?
        """

        # Get filename
        try:
            self.config_filename = os.environ[ANON_CONFIG_ENV_VAR]  # may raise
            assert self.config_filename  # may raise
            filename = self.config_filename
            fileobj = None
        except (KeyError, AssertionError):
            if RUNNING_WITHOUT_CONFIG or mock:
                # Running in a mock environment; no config required
                filename = None
                fileobj = StringIO(DEMO_CONFIG)
            else:
                print(
                    f"You must set the {ANON_CONFIG_ENV_VAR} environment "
                    f"variable to point to a CRATE anonymisation config file, "
                    f"or specify it on the command line.")
                traceback.print_stack()
                sys.exit(1)

        cfg = ConfigSection(
            section=AK.SECTION_MAIN,
            filename=filename,
            fileobj=fileobj
        )
        parser = cfg.parser

        def get_database(section_: str,
                         name: str,
                         srccfg_: DatabaseSafeConfig = None,
                         with_session: bool = False,
                         with_conn: bool = True,
                         reflect: bool = True) -> "DatabaseHolder":
            return parser.get_database(section_,
                                       dbname=name,
                                       srccfg=srccfg_,
                                       with_session=with_session,
                                       with_conn=with_conn,
                                       reflect=reflect)

        # ---------------------------------------------------------------------
        # Data dictionary
        # ---------------------------------------------------------------------

        self.data_dictionary_filename = cfg.opt_str(
            AK.DATA_DICTIONARY_FILENAME)

        # ---------------------------------------------------------------------
        # Critical field types
        # ---------------------------------------------------------------------

        self.pidtype = get_sqlatype(cfg.opt_str(AK.SQLATYPE_PID,
                                                DA.SQLATYPE_PID))
        self.pidtype_is_integer = is_sqlatype_integer(self.pidtype)
        self.mpidtype = get_sqlatype(cfg.opt_str(AK.SQLATYPE_MPID,
                                                 DA.SQLATYPE_MPID))
        self.mpidtype_is_integer = is_sqlatype_integer(self.mpidtype)

        # ---------------------------------------------------------------------
        # Encryption phrases/passwords
        # ---------------------------------------------------------------------

        self.hash_method = cfg.opt_str(AK.HASH_METHOD,
                                       DA.HASH_METHOD)
        self.per_table_patient_id_encryption_phrase = cfg.opt_str(
            AK.PER_TABLE_PATIENT_ID_ENCRYPTION_PHRASE)
        self.master_patient_id_encryption_phrase = cfg.opt_str(
            AK.MASTER_PATIENT_ID_ENCRYPTION_PHRASE)
        self.change_detection_encryption_phrase = cfg.opt_str(
            AK.CHANGE_DETECTION_ENCRYPTION_PHRASE)
        _extra_hash_config_section_names = cfg.opt_multiline(
            AK.EXTRA_HASH_CONFIG_SECTIONS)

        self.extra_hashers = {}  # type: Dict[str, GenericHasher]
        for hasher_name in _extra_hash_config_section_names:
            self.extra_hashers[hasher_name] = get_extra_hasher(parser,
                                                               hasher_name)
        # Load encryption keys and create hashers
        dummyhash = make_hasher(self.hash_method, "dummysalt")
        encrypted_length = dummyhash.output_length()

        self.sqltype_encrypted_pid = String(encrypted_length)
        self.sqltype_encrypted_pid_as_sql = str(self.sqltype_encrypted_pid)
        # ... VARCHAR(32) for MD5; VARCHAR(64) for SHA-256; VARCHAR(128) for
        # SHA-512.

        if not self.per_table_patient_id_encryption_phrase:
            raise ValueError(
                f"Missing {AK.PER_TABLE_PATIENT_ID_ENCRYPTION_PHRASE}")
        self.primary_pid_hasher = make_hasher(
            self.hash_method, self.per_table_patient_id_encryption_phrase)

        if not self.master_patient_id_encryption_phrase:
            raise ValueError(
                f"Missing {AK.MASTER_PATIENT_ID_ENCRYPTION_PHRASE}")
        self.master_pid_hasher = make_hasher(
            self.hash_method, self.master_patient_id_encryption_phrase)

        if not self.change_detection_encryption_phrase:
            raise ValueError(
                f"Missing {AK.CHANGE_DETECTION_ENCRYPTION_PHRASE}")
        self.change_detection_hasher = make_hasher(
            self.hash_method, self.change_detection_encryption_phrase)

        # ---------------------------------------------------------------------
        # Text extraction
        # ---------------------------------------------------------------------

        self.extract_text_extensions_case_sensitive = cfg.opt_bool(
            AK.EXTRACT_TEXT_EXTENSIONS_CASE_SENSITIVE,
            DA.EXTRACT_TEXT_EXTENSIONS_CASE_SENSITIVE)
        self.extract_text_extensions_permitted = cfg.opt_multiline(
            AK.EXTRACT_TEXT_EXTENSIONS_PERMITTED)
        self.extract_text_extensions_prohibited = cfg.opt_multiline(
            AK.EXTRACT_TEXT_EXTENSIONS_PROHIBITED)
        self.extract_text_plain = cfg.opt_bool(AK.EXTRACT_TEXT_PLAIN,
                                               DA.EXTRACT_TEXT_PLAIN)
        self.extract_text_width = cfg.opt_int(AK.EXTRACT_TEXT_WIDTH,
                                              DA.EXTRACT_TEXT_WIDTH)

        # ---------------------------------------------------------------------
        # Anonymisation
        # ---------------------------------------------------------------------

        cfg.require_absent(
            AK.DEPRECATED_WHITELIST_FILENAMES,
            f"Replace {AK.DEPRECATED_WHITELIST_FILENAMES!r} with "
            f"{AK.ALLOWLIST_FILENAMES!r}"
        )
        cfg.require_absent(
            AK.DEPRECATED_BLACKLIST_FILENAMES,
            f"Replace {AK.DEPRECATED_BLACKLIST_FILENAMES!r} with "
            f"{AK.DENYLIST_FILENAMES!r}"
        )

        self.allow_no_patient_info = cfg.opt_bool(
            AK.ALLOW_NO_PATIENT_INFO,
            DA.ALLOW_NO_PATIENT_INFO)
        self.allowlist_filenames = cfg.opt_multiline(AK.ALLOWLIST_FILENAMES)
        self.anonymise_codes_at_word_boundaries_only = cfg.opt_bool(
            AK.ANONYMISE_CODES_AT_WORD_BOUNDARIES_ONLY,
            DA.ANONYMISE_CODES_AT_WORD_BOUNDARIES_ONLY)
        self.anonymise_codes_at_numeric_boundaries_only = cfg.opt_bool(
            AK.ANONYMISE_CODES_AT_NUMERIC_BOUNDARIES_ONLY,
            DA.ANONYMISE_CODES_AT_NUMERIC_BOUNDARIES_ONLY)
        self.anonymise_dates_at_word_boundaries_only = cfg.opt_bool(
            AK.ANONYMISE_DATES_AT_WORD_BOUNDARIES_ONLY,
            DA.ANONYMISE_DATES_AT_WORD_BOUNDARIES_ONLY)
        self.anonymise_numbers_at_word_boundaries_only = cfg.opt_bool(
            AK.ANONYMISE_NUMBERS_AT_WORD_BOUNDARIES_ONLY,
            DA.ANONYMISE_NUMBERS_AT_WORD_BOUNDARIES_ONLY)
        self.anonymise_numbers_at_numeric_boundaries_only = cfg.opt_bool(
            AK.ANONYMISE_NUMBERS_AT_NUMERIC_BOUNDARIES_ONLY,
            DA.ANONYMISE_NUMBERS_AT_NUMERIC_BOUNDARIES_ONLY)
        self.anonymise_strings_at_word_boundaries_only = cfg.opt_bool(
            AK.ANONYMISE_STRINGS_AT_WORD_BOUNDARIES_ONLY,
            DA.ANONYMISE_STRINGS_AT_WORD_BOUNDARIES_ONLY)
        self.denylist_filenames = cfg.opt_multiline(AK.DENYLIST_FILENAMES)
        self.denylist_files_as_phrases = cfg.opt_bool(
            AK.DENYLIST_FILES_AS_PHRASES,
            DA.DENYLIST_FILES_AS_PHRASES)
        self.denylist_use_regex = cfg.opt_bool(
            AK.DENYLIST_USE_REGEX,
            DA.DENYLIST_USE_REGEX)
        self.min_string_length_for_errors = cfg.opt_int(
            AK.MIN_STRING_LENGTH_FOR_ERRORS,
            DA.MIN_STRING_LENGTH_FOR_ERRORS)
        self.min_string_length_to_scrub_with = cfg.opt_int(
            AK.MIN_STRING_LENGTH_TO_SCRUB_WITH,
            DA.MIN_STRING_LENGTH_TO_SCRUB_WITH)
        self.nonspecific_scrubber_first = cfg.opt_bool(
            AK.NONSPECIFIC_SCRUBBER_FIRST,
            DA.NONSPECIFIC_SCRUBBER_FIRST)
        self.phrase_alternative_word_filenames = cfg.opt_multiline(
            AK.PHRASE_ALTERNATIVE_WORD_FILENAMES)
        self.replace_patient_info_with = cfg.opt_str(
            AK.REPLACE_PATIENT_INFO_WITH,
            DA.REPLACE_PATIENT_INFO_WITH)
        self.replace_third_party_info_with = cfg.opt_str(
            AK.REPLACE_THIRD_PARTY_INFO_WITH,
            DA.REPLACE_THIRD_PARTY_INFO_WITH)
        self.replace_nonspecific_info_with = cfg.opt_str(
            AK.REPLACE_NONSPECIFIC_INFO_WITH,
            DA.REPLACE_NONSPECIFIC_INFO_WITH)
        self.scrub_all_dates = cfg.opt_bool(
            AK.SCRUB_ALL_DATES,
            DA.SCRUB_ALL_DATES)
        self.scrub_all_numbers_of_n_digits = cfg.opt_multiline_int(
            AK.SCRUB_ALL_NUMBERS_OF_N_DIGITS, minimum=1)
        self.scrub_all_uk_postcodes = cfg.opt_bool(
            AK.SCRUB_ALL_UK_POSTCODES,
            DA.SCRUB_ALL_UK_POSTCODES)
        self.scrub_string_suffixes = cfg.opt_multiline(
            AK.SCRUB_STRING_SUFFIXES)
        self.string_max_regex_errors = cfg.opt_int(
            AK.STRING_MAX_REGEX_ERRORS,
            DA.STRING_MAX_REGEX_ERRORS)
        self.thirdparty_xref_max_depth = cfg.opt_int(
            AK.THIRDPARTY_XREF_MAX_DEPTH,
            DA.THIRDPARTY_XREF_MAX_DEPTH)
        self.timefield = cfg.opt_str(
            AK.TIMEFIELD_NAME,
            DA.TIMEFIELD_NAME)

        # Get all extra regexes
        if parser.has_section(AK.SECTION_EXTRA_REGEXES):
            self.extra_regexes = [
                x[1] for x in parser.items(AK.SECTION_EXTRA_REGEXES)
            ]
        else:
            self.extra_regexes = []  # type: List[str]

        if not self.extract_text_extensions_case_sensitive:
            self.extract_text_extensions_permitted = [
                x.upper() for x in self.extract_text_extensions_permitted]
            self.extract_text_extensions_permitted = [
                x.upper() for x in self.extract_text_extensions_permitted]

        # allowlist, denylist, nonspecific scrubber, alternative words
        self.allowlist = WordList(
            filenames=self.allowlist_filenames,
            hasher=self.change_detection_hasher,
        )
        self.denylist = WordList(
            filenames=self.denylist_filenames,
            as_phrases=self.denylist_files_as_phrases,
            replacement_text=self.replace_nonspecific_info_with,
            hasher=self.change_detection_hasher,
            at_word_boundaries_only=(
                self.anonymise_strings_at_word_boundaries_only  # flexible
                if self.denylist_use_regex
                else True  # required by Flashtext
            ),
            max_errors=0,
            regex_method=self.denylist_use_regex,
        )
        self.nonspecific_scrubber = NonspecificScrubber(
            replacement_text=self.replace_nonspecific_info_with,
            hasher=self.change_detection_hasher,
            anonymise_codes_at_word_boundaries_only=(
                self.anonymise_codes_at_word_boundaries_only),
            anonymise_dates_at_word_boundaries_only=(
                self.anonymise_dates_at_word_boundaries_only),
            anonymise_numbers_at_word_boundaries_only=(
                self.anonymise_numbers_at_word_boundaries_only),
            denylist=self.denylist,
            scrub_all_numbers_of_n_digits=self.scrub_all_numbers_of_n_digits,
            scrub_all_uk_postcodes=self.scrub_all_uk_postcodes,
            scrub_all_dates=self.scrub_all_dates,
            extra_regexes=self.extra_regexes,
        )
        self.phrase_alternative_words = get_word_alternatives(
            self.phrase_alternative_word_filenames)

        # ---------------------------------------------------------------------
        # Output fields and formatting
        # ---------------------------------------------------------------------

        self.research_id_fieldname = cfg.opt_str(
            AK.RESEARCH_ID_FIELDNAME,
            DA.RESEARCH_ID_FIELDNAME)
        self.trid_fieldname = cfg.opt_str(
            AK.TRID_FIELDNAME,
            DA.TRID_FIELDNAME)
        self.master_research_id_fieldname = cfg.opt_str(
            AK.MASTER_RESEARCH_ID_FIELDNAME,
            DA.MASTER_RESEARCH_ID_FIELDNAME)
        self.add_mrid_wherever_rid_added = cfg.opt_bool(
            AK.ADD_MRID_WHEREVER_RID_ADDED,
            DA.ADD_MRID_WHEREVER_RID_ADDED)
        self.source_hash_fieldname = cfg.opt_str(
            AK.SOURCE_HASH_FIELDNAME,
            DA.SOURCE_HASH_FIELDNAME)

        # ---------------------------------------------------------------------
        # Destination database configuration
        # ---------------------------------------------------------------------

        self.max_rows_before_commit = cfg.opt_int(
            AK.MAX_ROWS_BEFORE_COMMIT,
            DA.MAX_ROWS_BEFORE_COMMIT)
        self.max_bytes_before_commit = cfg.opt_int(
            AK.MAX_BYTES_BEFORE_COMMIT,
            DA.MAX_BYTES_BEFORE_COMMIT)
        self.temporary_tablename = cfg.opt_str(
            AK.TEMPORARY_TABLENAME,
            DA.TEMPORARY_TABLENAME)

        # ---------------------------------------------------------------------
        # Databases
        # ---------------------------------------------------------------------

        destination_database_cfg_section = cfg.opt_str(AK.DESTINATION_DATABASE)
        self._destination_database_url = parser.get_str(
            destination_database_cfg_section,
            DatabaseConfigKeys.URL,
            required=True
        )
        admin_database_cfg_section = cfg.opt_str(AK.ADMIN_DATABASE)
        if destination_database_cfg_section == admin_database_cfg_section:
            raise ValueError(
                "Destination and admin databases mustn't be the same")
        source_database_cfg_sections = cfg.opt_multiline(AK.SOURCE_DATABASES)
        self._source_db_names = source_database_cfg_sections
        if destination_database_cfg_section in source_database_cfg_sections:
            raise ValueError("Destination database mustn't be listed as a "
                             "source database")
        if admin_database_cfg_section in source_database_cfg_sections:
            raise ValueError("Admin database mustn't be listed as a "
                             "source database")

        if RUNNING_WITHOUT_CONFIG:
            self.destdb = None  # type: Optional[DatabaseHolder]
            self._dest_dialect = mysql_dialect
        else:
            self.destdb = get_database(destination_database_cfg_section,
                                       name=destination_database_cfg_section,
                                       with_session=open_databases,
                                       with_conn=False,
                                       reflect=False)
            if not self.destdb:
                raise ValueError("Destination database misconfigured")
            if open_databases:
                self._dest_dialect = self.destdb.engine.dialect
            else:  # in context of web framework, some sort of default
                self._dest_dialect = mysql_dialect
            self._destdb_transaction_limiter = TransactionSizeLimiter(
                session=self.destdb.session,
                max_bytes_before_commit=self.max_bytes_before_commit,
                max_rows_before_commit=self.max_rows_before_commit
            )

        if RUNNING_WITHOUT_CONFIG:
            self.admindb = None  # type: Optional[DatabaseHolder]
        else:
            self.admindb = get_database(admin_database_cfg_section,
                                        name=admin_database_cfg_section,
                                        with_session=open_databases,
                                        with_conn=False,
                                        reflect=open_databases)
            if not self.admindb:
                raise ValueError("Admin database misconfigured")

        self.sources = {}  # type: Dict[str, DatabaseHolder]
        self.src_dialects = {}  # type: Dict[str, Dialect]
        for sourcedb_name in source_database_cfg_sections:
            if RUNNING_WITHOUT_CONFIG:
                continue
            log.info(f"Adding source database: {sourcedb_name}")
            srccfg = DatabaseSafeConfig(parser, sourcedb_name)
            srcdb = get_database(sourcedb_name,
                                 srccfg_=srccfg,
                                 name=sourcedb_name,
                                 with_session=open_databases,
                                 with_conn=False,
                                 reflect=open_databases)
            if not srcdb:
                raise ValueError(
                    f"Source database {sourcedb_name} misconfigured")
            self.sources[sourcedb_name] = srcdb
            if open_databases:
                self.src_dialects[sourcedb_name] = srcdb.engine.dialect
            else:  # in context of web framework
                self.src_dialects[sourcedb_name] = ms_sql_server_dialect

        # ---------------------------------------------------------------------
        # Processing options
        # ---------------------------------------------------------------------

        self.debug_max_n_patients = cfg.opt_int(AK.DEBUG_MAX_N_PATIENTS,
                                                DA.DEBUG_MAX_N_PATIENTS)
        self.debug_pid_list = cfg.opt_multiline(AK.DEBUG_PID_LIST)

        # ---------------------------------------------------------------------
        # Opting out entirely
        # ---------------------------------------------------------------------

        self.optout_pid_filenames = cfg.opt_multiline(AK.OPTOUT_PID_FILENAMES)
        self.optout_mpid_filenames = cfg.opt_multiline(
            AK.OPTOUT_MPID_FILENAMES)
        self.optout_col_values = cfg.opt_pyvalue_list(AK.OPTOUT_COL_VALUES)

        # ---------------------------------------------------------------------
        # Rest of initialization
        # ---------------------------------------------------------------------

        self.dd = DataDictionary(self)

        self.rows_in_transaction = 0
        self.bytes_in_transaction = 0
        self.rows_inserted_per_table = {}  # type: Dict[Tuple[str, str], int]
        self.warned_re_limits = {}  # type: Dict[Tuple[str, str], bool]

        self.report_every_n_rows = DEFAULT_REPORT_EVERY
        self.chunksize = DEFAULT_CHUNKSIZE
        self.debug_scrubbers = False
        self.save_scrubbers = False

        self._src_bytes_read = 0
        self._dest_bytes_written = 0
        self._echo = False

    def get_destdb_engine_outside_transaction(
            self, encoding: str = 'utf-8') -> Engine:
        """
        Get a standalone SQLAlchemy Engine for the destination database, and
        configure itself so transactions aren't used (equivalently:
        ``autocommit`` is True; equivalently, the database commits after every
        statement).

        See
        https://github.com/mkleehammer/pyodbc/wiki/Database-Transaction-Management

        Args:
            encoding: passed to the SQLAlchemy :func:`create_engine` function

        Returns:
            the Engine
        """  # noqa
        url = self._destination_database_url
        return create_engine(
            url,
            encoding=encoding,
            echo=self._echo,
            connect_args={'autocommit': True}  # for pyodbc
        )

    def overall_progress(self) -> str:
        """
        Returns a formatted description of the number of bytes read from the
        source database(s) and written to the destination database.

        (The Config is used to keep track of progress, via
        :func:`notify_src_bytes_read` and :func:`notify_dest_db_transaction`.)
        """
        return (
            f"{sizeof_fmt(self._src_bytes_read)} read, "
            f"{sizeof_fmt(self._dest_bytes_written)} written"
        )

    def load_dd(self, check_against_source_db: bool = True) -> None:
        """
        Loads the data dictionary (DD) into the config.

        Args:
            check_against_source_db:
                check DD validity against the source database?
        """
        log.info(SEP +
                 f"Loading data dictionary: {self.data_dictionary_filename}")
        self.dd.read_from_file(self.data_dictionary_filename)
        self.dd.check_valid(
            prohibited_fieldnames=[self.source_hash_fieldname,
                                   self.trid_fieldname],
            check_against_source_db=check_against_source_db)
        self.init_row_counts()

    def init_row_counts(self) -> None:
        """
        Initialize the "number of rows inserted" counts to zero for all source
        tables.
        """
        self.rows_inserted_per_table = {}  # type: Dict[Tuple[str, str], int]
        for db_table_tuple in self.dd.get_src_db_tablepairs():
            self.rows_inserted_per_table[db_table_tuple] = 0
            self.warned_re_limits[db_table_tuple] = False

    def check_valid(self) -> None:
        """
        Raise :exc:`ValueError` if the config is invalid.
        """

        # Destination databases
        if not self.destdb:
            raise ValueError(f"No {AK.DESTINATION_DATABASE} specified.")
        if not self.admindb:
            raise ValueError(f"No {AK.ADMIN_DATABASE} specified.")

        # Test table names
        if not self.temporary_tablename:
            raise ValueError(f"No {AK.TEMPORARY_TABLENAME} specified.")
        ensure_valid_table_name(self.temporary_tablename)

        # Test field names
        def validate_fieldattr(name: str) -> None:
            if not getattr(self, name):
                raise ValueError("Blank fieldname: " + name)
            ensure_valid_field_name(getattr(self, name))

        specialfieldlist = [
            # Our attributes have the same names as these parameters:
            AK.RESEARCH_ID_FIELDNAME,
            AK.TRID_FIELDNAME,
            AK.MASTER_RESEARCH_ID_FIELDNAME,
            AK.SOURCE_HASH_FIELDNAME,
        ]
        fieldset = set()  # type: Set[str]
        for attrname in specialfieldlist:
            validate_fieldattr(attrname)
            fieldset.add(getattr(self, attrname))
        if len(fieldset) != len(specialfieldlist):
            raise ValueError(
                "Config: these must all be DIFFERENT fieldnames: " +
                ",".join(specialfieldlist))

        # Test strings
        if not self.replace_patient_info_with:
            raise ValueError(f"Blank {AK.REPLACE_PATIENT_INFO_WITH}")
        if not self.replace_third_party_info_with:
            raise ValueError(f"Blank {AK.REPLACE_THIRD_PARTY_INFO_WITH}")
        if not self.replace_nonspecific_info_with:
            raise ValueError(f"Blank {AK.REPLACE_NONSPECIFIC_INFO_WITH}")
        replacements = list({self.replace_patient_info_with,
                             self.replace_third_party_info_with,
                             self.replace_nonspecific_info_with})
        if len(replacements) != 3:
            # So inadvisable that we prevent it.
            raise ValueError(
                f"{AK.REPLACE_PATIENT_INFO_WITH}, "
                f"{AK.REPLACE_THIRD_PARTY_INFO_WITH}, and "
                f"{AK.REPLACE_NONSPECIFIC_INFO_WITH} should all be distinct")

        # Regex
        if self.string_max_regex_errors < 0:
            raise ValueError(f"{AK.STRING_MAX_REGEX_ERRORS} < 0, nonsensical")
        if self.min_string_length_for_errors < 1:
            raise ValueError(
                f"{AK.MIN_STRING_LENGTH_FOR_ERRORS} < 1, nonsensical")
        if self.min_string_length_to_scrub_with < 1:
            raise ValueError(
                f"{AK.MIN_STRING_LENGTH_TO_SCRUB_WITH} < 1, nonsensical")

        # Source databases
        if not self.sources:
            raise ValueError("No source databases specified.")
        for dbname, dbinfo in self.sources.items():
            cfg = dbinfo.srccfg
            if cfg.ddgen_per_table_pid_field:
                ensure_valid_field_name(cfg.ddgen_per_table_pid_field)
                if cfg.ddgen_per_table_pid_field == self.source_hash_fieldname:
                    raise ValueError(
                        f"Config: {SK.DDGEN_PER_TABLE_PID_FIELD} "
                        f"parameter can't be the same as "
                        f"{AK.SOURCE_HASH_FIELDNAME}")
            if cfg.ddgen_master_pid_fieldname:
                ensure_valid_field_name(cfg.ddgen_master_pid_fieldname)
                if cfg.ddgen_master_pid_fieldname == self.source_hash_fieldname:
                    raise ValueError(
                        f"Config: {SK.DDGEN_MASTER_PID_FIELDNAME} "
                        f"parameter can't be the same as "
                        f"{AK.SOURCE_HASH_FIELDNAME}")

        # OK!
        log.debug("Config validated.")

    def encrypt_primary_pid(self, pid: Union[int, str]) -> str:
        """
        Encrypt a primary patient ID (PID), producing a research ID (RID).
        """
        if pid is None:  # this is very unlikely!
            raise ValueError("Trying to hash NULL PID!")
            # ... see encrypt_master_pid() below
        return self.primary_pid_hasher.hash(pid)

    def encrypt_master_pid(self, mpid: Union[int, str]) -> Optional[str]:
        """
        Encrypt a master PID, producing a master RID (MRID).
        """
        if mpid is None:
            return None
            # potentially: risk of revealing the hash
            # and DEFINITELY: two patients, both with no NHS number, must not
            # be equated on the hash (e.g. hash(None) -> hash("None") -> ...)!
        return self.master_pid_hasher.hash(mpid)

    def hash_object(self, x: Any) -> str:
        """
        Hashes an object using our ``change_detection_hasher``.

        We could use Python's build-in :func:`hash` function, which produces a
        64-bit unsigned integer (calculated from: ``sys.maxint``). However,
        there is an outside chance that someone uses a single-field table and
        therefore that this is vulnerable to content discovery via a dictionary
        attack. Thus, we should use a better version.
        """
        return self.change_detection_hasher.hash(repr(x))

    def get_extra_hasher(self, hasher_name: str) -> GenericHasher:
        """
        Return a named hasher from our ``extra_hashers`` dictionary.

        Args:
            hasher_name: name of the hasher

        Returns:
            the hasher

        Raises:
            :exc:`ValueError` if it doesn't exist
        """
        if hasher_name not in self.extra_hashers.keys():
            raise ValueError(
                f"Extra hasher {hasher_name} requested but doesn't exist; "
                f"check you have listed it in "
                f"{AK.EXTRA_HASH_CONFIG_SECTIONS!r} in the config file")
        return self.extra_hashers[hasher_name]

    @property
    def source_db_names(self) -> List[str]:
        """
        Get all source database names.
        """
        return self._source_db_names

    def set_echo(self, echo: bool) -> None:
        """
        Sets the "echo" property for all our SQLAlchemy database connections.

        Args:
            echo: show SQL?
        """
        self._echo = echo
        self.admindb.engine.echo = echo
        self.destdb.engine.echo = echo
        for db in self.sources.values():
            db.engine.echo = echo
        # Now, SQLAlchemy will mess things up by adding an additional handler.
        # So, bye-bye:
        for logname in ('sqlalchemy.engine.base.Engine',
                        'sqlalchemy.engine.base.OptionEngine'):
            logger = logging.getLogger(logname)
            # log.critical(logger.__dict__)
            remove_all_logger_handlers(logger)

    def get_src_dialect(self, src_db: str) -> Dialect:
        """
        Returns the SQLAlchemy :class:`Dialect` (e.g. MySQL, SQL Server...) for
        the specified source database.
        """
        return self.src_dialects[src_db]

    @property
    def dest_dialect(self) -> Dialect:
        """
        Returns the SQLAlchemy :class:`Dialect` (e.g. MySQL, SQL Server...) for
        the destination database.
        """
        return self._dest_dialect

    @property
    def dest_dialect_name(self) -> str:
        """
        Returns the SQLAlchemy name for the destination database dialect (e.g.
        ``mysql``).
        """
        return self._dest_dialect.name

    def commit_dest_db(self) -> None:
        """
        Executes a ``COMMIT`` on the destination database.
        """
        self._destdb_transaction_limiter.commit()

    def notify_src_bytes_read(self, n_bytes: int) -> None:
        """
        Use this function to tell the config how many bytes have been read
        from the source database. See, for example, :func:`overall_progress`.

        Args:
            n_bytes: the number of bytes read
        """
        self._src_bytes_read += n_bytes

    def notify_dest_db_transaction(self, n_rows: int, n_bytes: int) -> None:
        """
        Use this function to tell the config how many rows and bytes have been
        written to the source database. See, for example,
        :func:`overall_progress`.

        Note that this may trigger a ``COMMIT``, via our
        :class:`crate_anon.common.sql.TransactionSizeLimiter`.

        Args:
            n_rows: the number of rows written
            n_bytes: the number of bytes written
        """
        self._destdb_transaction_limiter.notify(n_rows=n_rows, n_bytes=n_bytes)
        # ... may trigger a commit
        self._dest_bytes_written += n_bytes

    def extract_text_extension_permissible(self, extension: str) -> bool:
        """
        Is this file extension (e.g. ``.doc``, ``.txt``) one that the config
        permits to use for text extraction?

        See the config options ``extract_text_extensions_permitted`` and
        ``extract_text_extensions_prohibited``.

        Args:
            extension: file extension, beginning with ``.``

        Returns:
            permitted?

        """
        if not self.extract_text_extensions_case_sensitive:
            extension = extension.upper()
        if self.extract_text_extensions_permitted:
            return extension in self.extract_text_extensions_permitted
        return extension not in self.extract_text_extensions_prohibited
