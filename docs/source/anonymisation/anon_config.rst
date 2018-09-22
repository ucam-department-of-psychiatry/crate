.. crate_anon/docs/source/anonymisation/anon_config.rst

..  Copyright (C) 2015-2018 Rudolf Cardinal (rudolf@pobox.com).
    .
    This file is part of CRATE.
    .
    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    .
    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.
    .
    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.


.. _anon_config_file:

The anonymiser config file
--------------------------

This file controls the behaviour of the anonymiser, and tells it where to find
the source, destination, and secret databases, and the data dictionary that
controls the conversion process for each database column.

You can generate a specimen config file with

.. code-block:: bash

    crate_anonymise --democonfig > test_anon_config.ini

You should save this, then edit it to your own needs.

For convenience, you may want the `CRATE_ANON_CONFIG` environment variable to
point to this file. (Otherwise you must specify it each time.)



Minimal anonymiser config
~~~~~~~~~~~~~~~~~~~~~~~~~

Here's an extremely minimal version for a hypothetical test database.
Many options are not shown and most comments have been removed.
See the :ref:`specimen config <specimen_anonymiser_config>` below.

.. code-block:: ini

    # Configuration file for CRATE anonymiser (crate_anonymise).

    # =============================================================================
    # Main settings
    # =============================================================================

    [main]

    data_dictionary_filename = testdd.tsv

    hash_method = HMAC_MD5
    per_table_patient_id_encryption_phrase = SOME_PASSPHRASE_REPLACE_ME
    master_patient_id_encryption_phrase = SOME_OTHER_PASSPHRASE_REPLACE_ME
    change_detection_encryption_phrase = YETANOTHER

    replace_patient_info_with = [XXXXXX]
    replace_third_party_info_with = [QQQQQQ]
    replace_nonspecific_info_with = [~~~~~~]

    research_id_fieldname = rid
    trid_fieldname = trid
    master_research_id_fieldname = mrid

    source_hash_fieldname = _src_hash

    temporary_tablename = _temp_table

    source_databases =
        mysourcedb1

    destination_database = my_destination_database

    admin_database = my_admin_database

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
    # Source database. (Just one in this example.)
    # User should have READ access only for safety.
    # =============================================================================

    [mysourcedb1]

    url = mysql+mysqldb://username:password@127.0.0.1:3306/source_databasename?charset=utf8


.. todo:: Check minimal anonymiser config example works.


.. _specimen_anonymiser_config:

Specimen anonymiser config
~~~~~~~~~~~~~~~~~~~~~~~~~~

Here's the specimen anonymiser config as of 2018-06-09:

.. code-block:: ini

    # Configuration file for CRATE anonymiser (crate_anonymise).
    # Version 0.18.51 (2018-06-29).
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
    # row. SEE HELP FOR DETAILS.

    data_dictionary_filename = testdd.tsv

    # -----------------------------------------------------------------------------
    # Critical field types
    # -----------------------------------------------------------------------------
    # We need to know PID and MPID types from the config so that we can set up our
    # secret mapping tables. You can leave these blank, in which case they will be
    # assumed to be large integers, using SQLAlchemy's BigInteger (e.g.
    # SQL Server's BIGINT). If you do specify them, you may specify EITHER
    # "BigInteger" or a string type such as "String(50)".

    sqlatype_pid =
    sqlatype_mpid =

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

        # If you are using the "hash" field alteration method
        # (see above), you need to list the hash methods here, for internal
        # initialization order/performance reasons.
    extra_hash_config_sections =

    # -----------------------------------------------------------------------------
    # Text extraction
    # -----------------------------------------------------------------------------

        # extract_text_extensions_permitted and extract_text_extensions_prohibited
        # govern what kinds of files are accepted for text extraction. It is very
        # likely that you'll want to apply such restrictions; for example, if your
        # database contains .jpg files, it's a waste of trying to extract text from
        # them (and in theory, if your text extraction tool provided sufficient
        # detail, such as binary-encoding the JPEG, you might leak identifiable
        # information, such as a photo).
        #
        # - The "permitted" and "prohibited" settings are both lists of strings.
        # - If the "permitted" list is not empty then a file will be processed
        #   only if its extension is in the permitted list. Otherwise, it will be
        #   processed only if it is not in the prohibited list.
        # - The extensions must include the "." prefix.
        # - Case sensitivity is controlled by the extra flag.

    extract_text_extensions_case_sensitive = False
    extract_text_extensions_permitted =
    extract_text_extensions_prohibited =

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

        # For fields marked as scrub_src = thirdparty_xref_pid,
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
        # Applies to words, but not to phrase.
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
        # ... applies to code
    anonymise_dates_at_word_boundaries_only = True
        # ... applies to date
    anonymise_numbers_at_word_boundaries_only = False
        # ... applies to number
    anonymise_numbers_at_numeric_boundaries_only = True
        # ... applies to number
        # ... if True, will not scrub "234" from "123456"
        # ... setting this to False is extremely conservative
    anonymise_strings_at_word_boundaries_only = True
        # ... applies to words and phrase

    # -----------------------------------------------------------------------------
    # Output fields and formatting
    # -----------------------------------------------------------------------------

        # Research ID field name. This will be a VARCHAR of length determined by
        # hash_method. Used to replace patient ID fields from source tables.
    research_id_fieldname = brcid

        # Transient integer research ID (TRID) fieldname.
        # An unsigned integer field with this name will be added to every table
        # containing a primary patient ID (in the source) or research ID (in the
        # destination).
    trid_fieldname = trid

        # Similarly, used to replace master patient ID fields in source tables:
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
        # Default is 1000.
    max_rows_before_commit = 1000

        # Specify the maximum number of source-record bytes (approximately!) that
        # are processed before a COMMIT is issued on the database transaction. This
        # prevents the transaction growing too large. The COMMIT will be issued
        # *after* this limit has been met/exceeded, so it may be exceeded if the
        # transaction just before the limit takes the cumulative total over the
        # limit.
        # Default is 83886080.
    max_bytes_before_commit = 83886080

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

        # Specify a list of patient IDs, for debugging? If specified, this
        # list will be used directly (overriding the patient ID source specified in
        # the data dictionary, and overriding debug_max_n_patients).
    debug_pid_list =

    # -----------------------------------------------------------------------------
    # Opting out entirely
    # -----------------------------------------------------------------------------

    # Patients who elect to opt out entirely have their PIDs stored in the OptOut
    # table of the admin database. ENTRIES ARE NEVER REMOVED FROM THIS LIST BY
    # CRATE. It can be populated in three ways:
    #   1. Manually, by adding a PID to the column opt_out.pid).
    #   2. By maintaining a text file list of integer PIDs. Any PIDs in this file
    #      are added to the opt-out list.
    #   3. By flagging a source database field as indicating an opt-out, using the
    #      src_flags = "!" marker.

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
        #       optout_col_values = [True, 1, '1', 'Yes', 'yes', 'Y', 'y']
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

        # List any fields that all tables MUST contain. If a table doesn't contain
        # all of the field(s) listed here, it will be skipped.
    ddgen_table_require_field_absolute =

        # List any fields that are required conditional on other fields.
        # List them as one or more pairs: "A, B" where B is required if A is
        # present (or the table will be skipped).
    ddgen_table_require_field_conditional =

        # Blacklist any fields (regardless of their table) when creating new data
        # dictionaries? Wildcards of */? operate as above.
    ddgen_field_blacklist =

        # Whitelist any fields? (Whitelists override blacklists.)
    ddgen_field_whitelist =

        # Fieldnames assumed to be their table's PK:
    ddgen_pk_fields =

        # Assume that content stays constant?
        # (Applies C to PK fields; q.v.)
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
        # data in at least one row (or the patient will be skipped)?
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
        # "skip_if_extract_fails":
    ddgen_skip_row_if_extract_text_fails_fields =

        # Automatic renaming of tables
        # (Typical use: you make a view with a suffix "_x" as a working step, then
        # you want the suffix removed for users.)
    ddgen_rename_tables_remove_suffixes =

        # Fields that are used as patient opt-out fields:
    ddgen_patient_opt_out_fields =

        # Are there any fields you want hashed, in addition to the normal PID/MPID
        # fields? Specify these a list of FIELDSPEC, EXTRA_HASH_NAME pairs.
        # For example:
        #       ddgen_extra_hash_fields = CaseNumber*, case_number_hashdef
        # where case_number_hashdef is an extra hash definition (see
        # "extra_hash_config_sections", and "alter_method" in the data dictionary).
        #
    ddgen_extra_hash_fields =

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
