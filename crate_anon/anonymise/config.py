#!/usr/bin/env python3
# crate_anon/anonymise/anon_config.py

"""
Config class for CRATE anonymiser.

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

Thoughts on configuration method

-   First version used a Config() class, which initializes with blank values.
    The anonymise_main.py file creates a config singleton and passes it around.
    Then when its set() method is called, it reads a config file and
    instantiates its settings.
    An option exists to print a draft config without ever reading one from
    disk.

    Advantage: easy to start the program without a valid config file (e.g. to
        print one).
    Disadvantage: modules can't be sure that a config is properly instantiated
        before they are loaded, so you can't easily define a class according to
        config settings (you'd have to have a class factory, which gets ugly).

-   The Django method is to have a configuration file (e.g. settings.py, which
    can import from other things) that is read by Django and then becomes
    importable by anything at startup as "django.conf.settings". (I've added
    local settings via an environment variable.) The way Django knows where
    to look is via this in manage.py:

        os.environ.setdefault("DJANGO_SETTINGS_MODULE",
                              "crate_anon.crateweb.config.settings")

    Advantage: setting the config file via an environment variable (read when
        the config file loads) allows guaranteed config existence as other
        modules start.
    Further advantage: config filenames not on command line, therefore not
        visible to ps.
    Disadvantage: how do you override with a command-line (argparse) setting?
        ... though: who cares?
    To print a config using that file: raise an exception on nonexistent
        config, and catch it with a special entry point script.

-   See also
    http://stackoverflow.com/questions/7443366/argument-passing-strategy-environment-variables-vs-command-line  # noqa
"""

# =============================================================================
# Imports
# =============================================================================

import codecs
import configparser
import logging
import os
import sys

from sqlalchemy import String

from cardinal_pythonlib.rnc_log import remove_all_logger_handlers
from cardinal_pythonlib.rnc_db import (
    ensure_valid_field_name,
    ensure_valid_table_name,
)

from crate_anon.anonymise.constants import (
    CONFIG_ENV_VAR,
    DEFAULT_MAX_ROWS_BEFORE_COMMIT,
    DEFAULT_MAX_BYTES_BEFORE_COMMIT,
    MAX_PID_STR,
    SEP,
)
from crate_anon.anonymise.dbholder import DatabaseHolder
from crate_anon.anonymise.dd import DataDictionary
from crate_anon.anonymise.hash import (
    # MD5Hasher,
    # SHA256Hasher,
    # SHA512Hasher,
    HmacMD5Hasher,
    HmacSHA256Hasher,
    HmacSHA512Hasher,
)
from crate_anon.anonymise.scrub import (
    NonspecificScrubber,
    WordList,
)
from crate_anon.anonymise.sqla import monkeypatch_TableClause

log = logging.getLogger(__name__)
monkeypatch_TableClause()


# =============================================================================
# Config/databases
# =============================================================================

class DatabaseSafeConfig(object):
    """Class representing non-sensitive configuration information about a
    source database."""

    def __init__(self, parser, section):
        """Read from a configparser section."""
        if not parser.has_section(section):
            raise ValueError("config missing section: " + section)

        def opt_str(option):
            return parser.get(section, option, fallback=None)

        def opt_multiline(option):
            multiline = parser.get(section, option, fallback='')
            return [x.strip() for x in multiline.splitlines() if x.strip()]

        def opt_bool(option, default):
            return parser.getboolean(section, option, fallback=default)

        def opt_int(option, default):
            return parser.getint(section, option, fallback=default)

        self.ddgen_force_lower_case = opt_bool('ddgen_force_lower_case', True)
        self.ddgen_convert_odd_chars_to_underscore = opt_bool(
            'ddgen_convert_odd_chars_to_underscore', True)
        self.ddgen_allow_no_patient_info = opt_bool(
            'ddgen_allow_no_patient_info', False)
        self.ddgen_per_table_pid_field = opt_str('ddgen_per_table_pid_field')
        self.ddgen_master_pid_fieldname = opt_str('ddgen_master_pid_fieldname')
        self.ddgen_constant_content = opt_bool(
            'ddgen_constant_content', False)
        self.ddgen_addition_only = opt_bool('ddgen_addition_only', False)
        self.ddgen_min_length_for_scrubbing = opt_int(
            'ddgen_min_length_for_scrubbing', 0)
        self.ddgen_allow_fulltext_indexing = opt_bool(
            'ddgen_allow_fulltext_indexing', True)
        self.debug_row_limit = opt_int('debug_row_limit', 0)

        self.ddgen_pid_defining_fieldnames = opt_multiline(
            'ddgen_pid_defining_fieldnames')
        self.ddgen_pk_fields = opt_multiline('ddgen_pk_fields')
        self.ddgen_table_blacklist = opt_multiline('ddgen_table_blacklist')
        self.ddgen_field_blacklist = opt_multiline('ddgen_field_blacklist')
        self.ddgen_scrubsrc_patient_fields = opt_multiline(
            'ddgen_scrubsrc_patient_fields')
        self.ddgen_scrubsrc_thirdparty_fields = opt_multiline(
            'ddgen_scrubsrc_thirdparty_fields')
        self.ddgen_scrubmethod_code_fields = opt_multiline(
            'ddgen_scrubmethod_code_fields')
        self.ddgen_scrubmethod_date_fields = opt_multiline(
            'ddgen_scrubmethod_date_fields')
        self.ddgen_scrubmethod_number_fields = opt_multiline(
            'ddgen_scrubmethod_number_fields')
        self.ddgen_scrubmethod_phrase_fields = opt_multiline(
            'ddgen_scrubmethod_phrase_fields')
        self.ddgen_safe_fields_exempt_from_scrubbing = opt_multiline(
            'ddgen_safe_fields_exempt_from_scrubbing')
        self.ddgen_truncate_date_fields = opt_multiline(
            'ddgen_truncate_date_fields')
        self.ddgen_filename_to_text_fields = opt_multiline(
            'ddgen_filename_to_text_fields')
        self.ddgen_index_fields = opt_multiline('ddgen_index_fields')
        self.debug_limited_tables = opt_multiline('debug_limited_tables')

        ddgen_binary_to_text_field_pairs = opt_multiline(
            'ddgen_binary_to_text_field_pairs')
        self.bin2text_dict = {}
        for pair in ddgen_binary_to_text_field_pairs:
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

    def __init__(self):
        """
        Read config from file
        """
        # Get filename
        try:
            self.config_filename = os.environ[CONFIG_ENV_VAR]
            assert self.config_filename
        except (KeyError, AssertionError):
            print(
                "You must set the {} environment variable to point to a CRATE "
                "anonymisation config file. Run crate_print_demo_anon_config "
                "to see a specimen config.".format(CONFIG_ENV_VAR))
            sys.exit(1)

        # Read config from file.
        parser = configparser.RawConfigParser()
        parser.read_file(codecs.open(self.config_filename, "r", "utf8"))
        section = "main"

        def opt_str(option):
            return parser.get(section, option, fallback=None)

        def opt_multiline(option):
            multiline = parser.get(section, option, fallback='')
            return [x.strip() for x in multiline.splitlines() if x.strip()]

        def opt_multiline_int(option, minimum=None, maximum=None):
            values = [int(x) for x in opt_multiline(option) if x]
            if minimum is not None:
                values = [x for x in values if x >= minimum]
            if maximum is not None:
                values = [x for x in values if x <= maximum]
            return values

        def opt_bool(option, default):
            return parser.getboolean(section, option, fallback=default)

        def opt_int(option, default):
            return parser.getint(section, option, fallback=default)

        def get_database(section_, name, srccfg_=None, with_session=False,
                         with_conn=True, reflect=True):
            url = parser.get(section_, 'url', fallback=None)
            if not url:
                return None
            return DatabaseHolder(name, url, srccfg_,
                                  with_session=with_session,
                                  with_conn=with_conn,
                                  reflect=reflect)

        self.data_dictionary_filename = opt_str('data_dictionary_filename')
        self.hash_method = opt_str('hash_method')
        self.ddgen_master_pid_fieldname = opt_str('ddgen_master_pid_fieldname')
        self.per_table_patient_id_encryption_phrase = opt_str(
            'per_table_patient_id_encryption_phrase')
        self.master_patient_id_encryption_phrase = opt_str(
            'master_patient_id_encryption_phrase')
        self.change_detection_encryption_phrase = opt_str(
            'change_detection_encryption_phrase')
        self.replace_patient_info_with = opt_str('replace_patient_info_with')
        self.replace_third_party_info_with = opt_str(
            'replace_third_party_info_with')
        self.replace_nonspecific_info_with = opt_str(
            'replace_nonspecific_info_with')
        self.string_max_regex_errors = opt_int('string_max_regex_errors', 0)
        self.min_string_length_for_errors = opt_int(
            'min_string_length_for_errors', 1)
        self.min_string_length_to_scrub_with = opt_int(
            'min_string_length_to_scrub_with', 2)
        self.scrub_all_uk_postcodes = opt_bool('scrub_all_uk_postcodes', False)
        self.anonymise_codes_at_word_boundaries_only = opt_bool(
            'anonymise_codes_at_word_boundaries_only', True)
        self.anonymise_dates_at_word_boundaries_only = opt_bool(
            'anonymise_dates_at_word_boundaries_only', True)
        self.anonymise_numbers_at_word_boundaries_only = opt_bool(
            'anonymise_numbers_at_word_boundaries_only', False)
        self.anonymise_strings_at_word_boundaries_only = opt_bool(
            'anonymise_strings_at_word_boundaries_only', True)
        self.mapping_patient_id_fieldname = opt_str(
            'mapping_patient_id_fieldname')
        self.research_id_fieldname = opt_str('research_id_fieldname')
        self.trid_fieldname = opt_str('trid_fieldname')
        self.mapping_master_id_fieldname = opt_str(
            'mapping_master_id_fieldname')
        self.master_research_id_fieldname = opt_str(
            'master_research_id_fieldname')
        self.source_hash_fieldname = opt_str('source_hash_fieldname')
        self.date_to_text_format = opt_str('date_to_text_format')
        self.datetime_to_text_format = opt_str('datetime_to_text_format')
        self.append_source_info_to_comment = opt_bool(
            'append_source_info_to_comment', True)
        self.open_databases_securely = opt_bool(
            'open_databases_securely', True)
        self.max_rows_before_commit = opt_int('max_rows_before_commit',
                                              DEFAULT_MAX_ROWS_BEFORE_COMMIT)
        self.max_bytes_before_commit = opt_int('max_bytes_before_commit',
                                               DEFAULT_MAX_BYTES_BEFORE_COMMIT)
        self.temporary_tablename = opt_str('temporary_tablename')
        self.debug_max_n_patients = opt_int('debug_max_n_patients', 0)

        self.scrub_string_suffixes = opt_multiline('scrub_string_suffixes')
        self.whitelist_filenames = opt_multiline('whitelist_filenames')
        self.blacklist_filenames = opt_multiline('blacklist_filenames')
        self.scrub_all_numbers_of_n_digits = opt_multiline_int(
            'scrub_all_numbers_of_n_digits', minimum=1)
        self.debug_pid_list = opt_multiline_int('debug_pid_list')

        # Databases
        destination_database_cfg_section = opt_str('destination_database')
        admin_database_cfg_section = opt_str('admin_database')
        if destination_database_cfg_section == admin_database_cfg_section:
            raise ValueError(
                "Destination and admin databases mustn't be the same")
        source_database_cfg_sections = opt_multiline('source_databases')
        self.source_db_names = source_database_cfg_sections
        if destination_database_cfg_section in source_database_cfg_sections:
            raise ValueError("Destination database mustn't be listed as a "
                             "source database")
        if admin_database_cfg_section in source_database_cfg_sections:
            raise ValueError("Admin database mustn't be listed as a "
                             "source database")
        self.destdb = get_database(destination_database_cfg_section,
                                   name=destination_database_cfg_section,
                                   with_session=True,
                                   with_conn=False,
                                   reflect=False)
        if not self.destdb:
            raise ValueError("Destination database misconfigured")
        self.admindb = get_database(admin_database_cfg_section,
                                    name=admin_database_cfg_section,
                                    with_session=True,
                                    with_conn=False,
                                    reflect=True)
        if not self.admindb:
            raise ValueError("Admin database misconfigured")
        self.sources = {}
        for sourcedb_name in source_database_cfg_sections:
            log.info("Adding source database: {}".format(sourcedb_name))
            srccfg = DatabaseSafeConfig(parser, sourcedb_name)
            srcdb = get_database(sourcedb_name,
                                 srccfg_=srccfg,
                                 name=sourcedb_name,
                                 with_session=True,
                                 with_conn=False,
                                 reflect=True)
            if not srcdb:
                raise ValueError("Source database {} misconfigured".format(
                    sourcedb_name))
            self.sources[sourcedb_name] = srcdb

        # Load encryption keys and create hashers
        assert self.hash_method not in ["MD5", "SHA256", "SHA512"], (
            "Non-HMAC hashers are deprecated for security reasons. You have: "
            "{}".format(self.hash_method))
        if self.hash_method == "HMAC_MD5":
            # noinspection PyPep8Naming
            HashClass = HmacMD5Hasher
        elif self.hash_method == "HMAC_SHA256" or not self.hash_method:
            # noinspection PyPep8Naming
            HashClass = HmacSHA256Hasher
        elif self.hash_method == "HMAC_SHA512":
            # noinspection PyPep8Naming
            HashClass = HmacSHA512Hasher
        else:
            raise ValueError("Unknown value for hash_method")
        encrypted_length = len(HashClass("dummysalt").hash(MAX_PID_STR))

        self.SqlTypeEncryptedPid = String(encrypted_length)
        self.sqltype_encrypted_pid_as_sql = str(self.SqlTypeEncryptedPid)
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

        self.dd = DataDictionary(self)

        self.rows_in_transaction = 0
        self.bytes_in_transaction = 0
        self.rows_inserted_per_table = {}
        self.warned_re_limits = {}

        self.report_every_n_rows = 100
        self.debug_scrubbers = False
        self.save_scrubbers = False

    def load_dd(self):
        log.info(SEP + "Loading data dictionary: {}".format(
            self.data_dictionary_filename))
        self.dd.read_from_file(self.data_dictionary_filename)
        self.dd.check_valid(
            prohibited_fieldnames=[self.source_hash_fieldname,
                                   self.trid_fieldname])
        self.init_row_counts()

    def init_row_counts(self):
        """Initialize row counts for all source tables."""
        self.rows_inserted_per_table = {}
        for db_table_tuple in self.dd.get_src_db_tablepairs():
            self.rows_inserted_per_table[db_table_tuple] = 0
            self.warned_re_limits[db_table_tuple] = False

    def check_valid(self):
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
            raise ValueError(
                "Config: these must all be DIFFERENT fieldnames: " +
                ",".join(specialfieldlist))

        # Test strings
        if not self.replace_patient_info_with:
            raise ValueError("Blank replace_patient_info_with")
        if not self.replace_third_party_info_with:
            raise ValueError("Blank replace_third_party_info_with")
        if not self.replace_nonspecific_info_with:
            raise ValueError("Blank replace_nonspecific_info_with")
        replacements = list({self.replace_patient_info_with,
                             self.replace_third_party_info_with,
                             self.replace_nonspecific_info_with})
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

        # Source databases
        if not self.sources:
            raise ValueError("No source databases specified.")
        for dbname, dbinfo in self.sources.items():
            cfg = dbinfo.srccfg
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

    def hash_object(self, l):
        """
        Hashes a list with Python's built-in hash function.

        We could use Python's build-in hash() function, which produces a 64-bit
        unsigned integer (calculated from: sys.maxint).
        However, there is an outside chance that someone uses a single-field
        table and therefore that this is vulnerable to content discovery via a
        dictionary attack. Thus, we should use a better version.
        """
        return self.change_detection_hasher.hash(repr(l))

    def get_source_db_names(self):
        return self.source_db_names

    def set_echo(self, echo):
        self.admindb.engine.echo = echo
        self.destdb.engine.echo = echo
        for db in self.sources.values():
            db.engine.echo = echo
        # Now, SQLAlchemy will mess things up by adding an additional handler.
        # So, bye-bye:
        for logname in ['sqlalchemy.engine.base.Engine',
                        'sqlalchemy.engine.base.OptionEngine']:
            logger = logging.getLogger(logname)
            # log.critical(logger.__dict__)
            remove_all_logger_handlers(logger)


# =============================================================================
# Singleton config
# =============================================================================

config = Config()
