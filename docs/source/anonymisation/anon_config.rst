..  crate_anon/docs/source/anonymisation/anon_config.rst

..  Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).
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

.. |ddgen_only| replace::
    This section relates to **automatic creation of data dictionaries** only.
    In normal use, none of these settings does anything.

.. _fnmatch: https://docs.python.org/3.4/library/fnmatch.html
.. _MD5: https://en.wikipedia.org/wiki/MD5
.. _SHA256: https://en.wikipedia.org/wiki/SHA-2
.. _SHA512: https://en.wikipedia.org/wiki/SHA-2


.. _anon_config_file:

The anonymiser config file
--------------------------

.. contents::
   :local:

This file controls the behaviour of the anonymiser, and tells it where to find
the source, destination, and secret databases, and the data dictionary that
controls the conversion process for each database column.

You can generate a specimen config file with

.. code-block:: bash

    crate_anon_demo_config > test_anon_config.ini

You should save this, then edit it to your own needs. A copy is shown
:ref:`below <specimen_anonymiser_config>`.

For convenience, you may want the `CRATE_ANON_CONFIG` environment variable to
point to this file. (Otherwise you must specify it each time.)


Format of the configuration file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- The config file is in standard `INI file format
  <https://en.wikipedia.org/wiki/INI_file>`_.

- **UTF-8 encoding.** Use this! The file is explicitly opened in UTF-8 mode.
- **Comments.** Hashes (``#``) and semicolons (``;``) denote comments.
- **Sections.** Sections are indicated with: ``[section]``
- **Name/value (key/value) pairs.** The parser used is `ConfigParser
  <https://docs.python.org/3/library/configparser.html>`_. It allows
  ``name=value`` or ``name:value``.
- **Avoid indentation of parameters.** (Indentation is used to indicate
  the continuation of previous parameters.)
- **Parameter types,** referred to below, are:

  - **String.** Single-line strings are simple.
  - **Multiline string.** Here, a series of lines is read and split into a list
    of strings (one for each line). You should indent all lines except the
    first beyond the level of the parameter name, and then they will be treated
    as one parameter value.
  - **Integer.** Simple.
  - **Boolean.** For Boolean options, true values are any of: ``1, yes, true,
    on`` (case-insensitive). False values are any of: ``0, no, false, off``.


.. _anon_config_main_section:

[main] section
~~~~~~~~~~~~~~

Data dictionary
+++++++++++++++

data_dictionary_filename
########################

*String.*

Specify the filename of a data dictionary in TSV (tab-separated value) format,
with a header row. See :ref:`Data Dictionary <data_dictionary>`.


Critical field types
++++++++++++++++++++

sqlatype_pid
############

*String.*

See :ref:`sqlatype_mpid <anon_config_sqlatype_mpid>` below.


.. _anon_config_sqlatype_mpid:

sqlatype_mpid
#############

*String.*

We need to know PID and MPID types from the config so that we can set up our
secret mapping tables. You can leave these blank, in which case they will be
assumed to be large integers, using SQLAlchemy's ``BigInteger`` (e.g.
SQL Server's ``BIGINT``). If you do specify them, you may specify EITHER
``BigInteger`` or a string type such as ``String(50)``.


Encryption phrases/passwords
++++++++++++++++++++++++++++

.. _anon_config_hash_method:

hash_method
###########

*String.*

PID-to-RID hashing method. Options are:

- ``HMAC_MD5`` -- use MD5_ and produce a 32-character digest
- ``HMAC_SHA256`` -- use SHA256_ and produce a 64-character digest
- ``HMAC_SHA512`` -- use SHA512_ and produce a 128-character digest


per_table_patient_id_encryption_phrase
######################################

*String.*

Secret phrase with which to hash the PID (creating the RID).


master_patient_id_encryption_phrase
###################################

*String.*

Secret phrase with which to hash the MPID (creating the MRID).


change_detection_encryption_phrase
##################################

*String.*

Secret phrase with which to hash content (storing the result in the output
database), so that changes in content can be detected.


.. _anon_config_extra_hash_config_sections:

extra_hash_config_sections
##########################

*Multiline string.*

If you are using the "hash" field alteration method (see :ref:`alter_method
<dd_alter_method>`), you need to list the hash methods here, for internal
initialization order/performance reasons.

See :ref:`hasher definitions <anon_config_hasher_definitions>` for how to
define these.


Text extraction
+++++++++++++++

.. _anon_config_extract_text_extensions_permitted:

extract_text_extensions_permitted
#################################

*Multiline string.*

``extract_text_extensions_permitted`` and
``extract_text_extensions_prohibited`` govern what kinds of files are accepted
for text extraction. It is very likely that you'll want to apply such
restrictions; for example, if your database contains ``.jpg`` files, it's a
waste of trying to extract text from them (and in theory, if your text
extraction tool provided sufficient detail, such as binary-encoding the JPEG,
you might leak identifiable information, such as a photo).

- The "permitted" and "prohibited" settings are both lists of strings.

- If the "permitted" list is not empty then a file will be processed only if
  its extension is in the permitted list. Otherwise, it will be processed only
  if it is not in the prohibited list.

- The extensions must include the "." prefix.

- Case sensitivity is controlled by the extra flag,
  ``extract_text_extensions_case_sensitive``.


extract_text_extensions_prohibited
##################################

*Multiline string.*

See :ref:`extract_text_extensions_permitted
<anon_config_extract_text_extensions_permitted>`.


extract_text_extensions_case_sensitive
######################################

*Boolean.* Default: false.

See :ref:`extract_text_extensions_permitted
<anon_config_extract_text_extensions_permitted>`.


extract_text_plain
##################

*Boolean.* Default: true. (Changed to true from v0.18.88.)

Use the plainest possible layout for text extraction?

``False`` = better for human layout. Table example from DOCX:

.. code-block:: none

    ┼─────────────┼─────────────┼
    │ Row 1 col 1 │ Row 1 col 2 │
    ┼─────────────┼─────────────┼
    │ Row 2 col 1 │ Row 2 col 2 │
    ┼─────────────┼─────────────┼

``True`` = good for natural language processing. Table example from DOCX:

.. code-block:: none

    ╔═════════════════════════════════════════════════════════════════╗
    Row 1 col 1
    ───────────────────────────────────────────────────────────────────
    Row 1 col 2
    ═══════════════════════════════════════════════════════════════════
    Row 2 col 1
    ───────────────────────────────────────────────────────────────────
    Row 2 col 2
    ╚═════════════════════════════════════════════════════════════════╝

... note the absence of vertical interruptions, and that text from one cell
remains contiguous.


extract_text_width
##################

*Integer.* Default: 80.

Default width (in columns) to word-wrap extracted text to.


Anonymisation
+++++++++++++

replace_patient_info_with
#########################

*String.*

Patient information will be replaced with this. For example, ``XXXXXX`` or
``[___]`` or ``[__PPP__]`` or ``[__ZZZ__]``; the bracketed forms can be a bit
easier to spot, and work better if they directly abut other text.


replace_third_party_info_with
#############################

*String.*

Third-party information (e.g. information about family members) will be
replaced by this. For example, ``YYYYYY`` or ``[...]`` or ``[__TTT__]`` or
``[__QQQ__]``.


thirdparty_xref_max_depth
#########################

*Integer.* Default 1.

For fields marked as ``scrub_src = thirdparty_xref_pid`` (see :ref:`scrub_src
<dd_scrub_src>`), how deep should we recurse? Beware making this too large; the
recursion trawls a lot of information (and also uses an extra simultaneous
database cursor for each recursion).


.. _anon_config_replace_nonspecific_info_with:

replace_nonspecific_info_with
#############################

*String.*

Things to be removed irrespective of patient-specific information will be
replaced by this (for example, if you opt to remove all things looking like
telephone numbers). For example, ``ZZZZZZ`` or ``[~~~]``.


scrub_string_suffixes
#####################

*Multiline string.*

Strings to append to every "scrub from" string.

For example, include "s" if you want to scrub "Roberts" whenever you scrub
"Robert".

Applies to scrub methods ``words``, but not to ``phrase`` (see
:ref:`scrub_method <dd_scrub_method>`).


.. _anon_config_string_max_regex_errors:

string_max_regex_errors
#######################

*Integer.* Default: 0.

Specify maximum number of errors (insertions, deletions, substitutions) in
string regex matching. Beware using a high number! Suggest 1-2.


min_string_length_for_errors
############################

*Integer.* Default: 1.

Is there a minimum length to apply :ref:`string_max_regex_errors
<anon_config_string_max_regex_errors>`? For example, if you allow one typo and
someone is called Ian, all instances of 'in' or 'an' will be wiped. Note that
this applies to scrub-source data.


min_string_length_to_scrub_with
###############################

*Integer.* Default: 2.

Is there a minimum length of string to scrub WITH? For example, if you specify
2, you allow two-letter names such as Al to be scrubbed, but you allow initials
through, and therefore prevent e.g. 'A' from being scrubbed from the
destination. Note that this applies to scrub-source data.


allowlist_filenames
###################

*Multiline string.*

Allowlist.

Are there any words not to scrub? For example, "the", "road", "street" often
appear in addresses, but you might not want them removed. Be careful in case
these could be names (e.g. "Lane").

Specify these as a list of *filenames*, where the files contain words; e.g.

.. code-block:: ini

    allowlist_filenames = /some/path/short_english_words.txt

Here's a suggestion for some of the sorts of words you might include:

.. code-block:: none

    am
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

.. note::
    Formerly ``whitelist_filenames``; changed 2020-07-20 as part of neutral
    language review.


denylist_filenames
##################

*Multiline string.*

Denylist.

Are there any words you always want to remove?

Specify these as a list of filenames, e.g

.. code-block:: ini

    denylist_filenames =
        /some/path/boy_names.txt
        /some/path/girl_names.txt
        /some/path/common_surnames.txt

.. note::
    Formerly ``blacklist_filenames``; changed 2020-07-20 as part of neutral
    language review.


phrase_alternative_word_filenames
#################################

*Multiline string.*

Alternatives for common words. These will be used to find alternative phrases
which will be scrubbed. The files specified should be in comma separated
variable (CSV) form.

Examples of alternative words include street types:
https://en.wikipedia.org/wiki/Street_suffix.


scrub_all_numbers_of_n_digits
#############################

*Multiline list of integers.*

Use nonspecific scrubbing of numbers of a certain length?

For example, scrubbing all 11-digit numbers will remove modern UK telephone
numbers in conventional format. To do this, specify
``scrub_all_numbers_of_n_digits = 11``. You could scrub both 10- and 11-digit
numbers by specifying both numbers (in multiline format, as above); 10-digit
numbers would include all NHS numbers. Avoid using this for short numbers; you
may lose valuable numeric data!


scrub_all_uk_postcodes
######################

*Boolean.* Default: false.

Nonspecific scrubbing of UK postcodes?

See https://www.mrs.org.uk/pdf/postcodeformat.pdf; these can look like

.. code-block:: none

    FORMAT    EXAMPLE
    AN NAA    M1 1AA
    ANN NAA   M60 1NW
    AAN NAA   CR2 6XH
    AANN NAA  DN55 1PT
    ANA NAA   W1A 1HQ
    AANA NAA  EC1A 1BB


.. _anon_config_anonymise_codes_at_word_boundaries_only:

anonymise_codes_at_word_boundaries_only
#######################################

*Boolean.* Default: true.

Anonymise codes only when they are found at word boundaries?

Applies to the ``code`` scrub method (see :ref:`scrub_method
<dd_scrub_method>`).

``True`` is more liberal (produces less scrubbing); ``False`` is more
conservative (more scrubbing; higher chance of over-scrubbing) and will deal
with accidental word concatenation. With ID numbers, beware if you use a
prefix, e.g. if people write ``M123456`` or ``R123456``; in that case you will
need ``anonymise_numbers_at_word_boundaries_only = False``.


anonymise_dates_at_word_boundaries_only
#######################################

*Boolean.* Default: true.

As for :ref:`anonymise_codes_at_word_boundaries_only
<anon_config_anonymise_codes_at_word_boundaries_only>`, but applies to the
``date`` scrub method (see :ref:`scrub_method <dd_scrub_method>`).


.. _anon_config_anonymise_numbers_at_word_boundaries_only:

anonymise_numbers_at_word_boundaries_only
#########################################

*Boolean.* Default: false.

As for :ref:`anonymise_codes_at_word_boundaries_only
<anon_config_anonymise_codes_at_word_boundaries_only>`, but applies to the
``number`` scrub method (see :ref:`scrub_method <dd_scrub_method>`).


anonymise_numbers_at_numeric_boundaries_only
############################################

*Boolean.* Default: true.

Similar to :ref:`anonymise_numbers_at_word_boundaries_only
<anon_config_anonymise_numbers_at_word_boundaries_only>`, and similarly applies
to the ``number`` scrub method (see :ref:`scrub_method <dd_scrub_method>`);
however, this relates to whether numbers are scrubbed only at *numeric*
boundaries.

If ``True``, CRATE will not scrub "234" from "123456". Setting this to
``False`` is extremely conservative (all sorts of numbers may be scrubbed). You
probably want this set to ``True``.


anonymise_strings_at_word_boundaries_only
#########################################

*Boolean.* Default: true.

As for :ref:`anonymise_codes_at_word_boundaries_only
<anon_config_anonymise_codes_at_word_boundaries_only>`, but applies to the
``words`` and the ``phrase`` scrub methods (see :ref:`scrub_method
<dd_scrub_method>`).


Other anonymisation options
+++++++++++++++++++++++++++

You can also specify additional "nonspecific" regular expressions yourself.
See :ref:`extra_regexes <anon_config_extra_regexes>`.


Output fields and formatting
++++++++++++++++++++++++++++

timefield_name
##############

*String.*

Name of the ``DATETIME`` column to be created in every output table indicating
when CRATE processed that row (see
:func:`crate_anon.anonymise.anonymise.process_table`).

An example might be ``_when_processed_utc``.


research_id_fieldname
#####################

*String.*

Research ID (RID) field name for destination tables. This will be a ``VARCHAR``
of length determined by :ref:`hash_method <anon_config_hash_method>`. Used to
replace patient ID fields from source tables.


trid_fieldname
##############

*String.*

Transient integer research ID (TRID) fieldname. An unsigned integer field with
this name will be added to every table containing a primary patient ID (in the
source) or research ID (in the destination). It will be indexed (and whether
that index is unique or not depends on the settings for the PID field).


master_research_id_fieldname
############################

*String.*

Master research ID (MRID) field name for destination tables. This will be a
``VARCHAR`` of length determined by :ref:`hash_method
<anon_config_hash_method>`. Used to replace master patient ID fields from
source tables.


.. _add_mrid_wherever_rid_added:

add_mrid_wherever_rid_added
###########################

*Boolean.* Default: true.

Whenever adding a RID field to a destination table (replacing the PID field
from the source, and adding a TRID field), should we also add an MRID field?
It will be indexed (non-uniquely; the MRID is not always guaranteed to be
present just because the PID is present).


source_hash_fieldname
#####################

*String.*

Change-detection hash fieldname for destination tables. This will be a
``VARCHAR`` of length determined by :ref:`hash_method
<anon_config_hash_method>`. Used to hash entire rows to see if they've changed
later.


ddgen_append_source_info_to_comment
###################################

*Boolean.* Default: true.

When drafting a data dictionary, append the source table/field name to the
column comment?


Destination database configuration
++++++++++++++++++++++++++++++++++

max_rows_before_commit
######################

*Integer.* Default: 1000.

Specify the maximum number of rows to be processed before a ``COMMIT`` is
issued on the database transaction(s). This prevents the transaction(s) growing
too large.


max_bytes_before_commit
#######################

*Integer.* Default: 80 Mb (80 * 1024 * 1024 = 83886080).

Specify the maximum number of source-record bytes (approximately!) that are
processed before a ``COMMIT`` is issued on the database transaction(s). This
prevents the transaction(s) growing too large. The ``COMMIT`` will be issued
*after* this limit has been met/exceeded, so it may be exceeded if the
transaction just before the limit takes the cumulative total over the limit.


temporary_tablename
###################

*String.*

We need a temporary table name for incremental updates. This can't be the name
of a real destination table. It lives in the destination database.


Choose databases (defined in their own sections)
++++++++++++++++++++++++++++++++++++++++++++++++

Parameter values in this section are themselves config file section names.
For example, if you refer to a database called ``mydb``, CRATE will look for a
:ref:`database config section <anon_config_db_section>` named ``[mydb]``.


source_databases
################

*Multiline string (of database config section names).*

Source database list. Can be lots.


destination_database
####################

*String (a database config section name).*

Destination database. Just one.


admin_database
##############

*String (a database config section name).*

Secret admin database. Just one.


Processing options, to limit data quantity for testing
++++++++++++++++++++++++++++++++++++++++++++++++++++++

.. _anon_config_debug_max_n_patients:

debug_max_n_patients
####################

*Integer.* Default: 0.

Limit the number of patients to be processed? Specify 0 (the default) for no
limit.


debug_pid_list
##############

*Multiline string.*

Specify a list of patient IDs to use, for debugging? If specified, only these
patients will be processed -- this list will be used directly (overriding the
patient ID source specified in the data dictionary, and overriding
:ref:`debug_max_n_patients <anon_config_debug_max_n_patients>`).


Opting out entirely
+++++++++++++++++++

Patients who elect to opt out entirely have their PIDs stored in the ``OptOut``
table of the admin database. ENTRIES ARE NEVER REMOVED FROM THIS LIST BY
CRATE. It can be populated in several ways:

1. Manually, by adding a PID to the column ``opt_out_pid.pid`` in the admin
   database. See :class:`crate_anon.anonymise.models.OptOutPid`.
2. Similarly, by adding an MPID to the column ``opt_out_mpid.mpid`` in the
   admin database. See :class:`crate_anon.anonymise.models.OptOutMpid`.
3. By maintaining a text file list of integer PIDs/MPIDs. Any PIDs/MPIDs in
   this file/files are added to the opt-out list. See below.
4. By flagging a source database field as indicating an opt-out, using the
   ``!`` marker in :ref:`src_flags <dd_src_flags>`). See below.


optout_pid_filenames
####################

*Multiline string.*

If you set this, each line of each named file is scanned for an integer, taken
to be the PID of a patient who wishes to opt out.


optout_mpid_filenames
#####################

*Multiline string.*

If you set this, each line of each named file is scanned for an integer, taken
to be the MPID of a patient who wishes to opt out.


optout_col_values
#################

*List of Python values.*

If you mark a field in the data dictionary as an opt-out field (see above and
:ref:`src_flags <dd_src_flags>`), that says "the field tells you whether the
patient opts out or not". But is it "opt out" or "not"? If the actual value
matches a value specified here, then it's "opt out".

Specify a LIST OF PYTHON VALUES; for example:

.. code-block:: ini

    optout_col_values = [True, 1, '1', 'Yes', 'yes', 'Y', 'y']


.. _anon_config_extra_regexes:

[extra_regexes] section
~~~~~~~~~~~~~~~~~~~~~~~

*Arbitrary number of name (string), value (string) pairs.*

This section is optional.

Here, you can specify extra regular expression patterns (regexes) that you wish
to be scrubbed from the text as nonspecific information (see
:ref:`replace_nonspecific_info_with
<anon_config_replace_nonspecific_info_with>`).

These regexes can be multiline and contain comments -- just remember to escape
spaces and hash signs which you actually want to be part of the regex.

They have their own section so that you can use the parameter name as a helpful
descriptive name (these names are ignored, and you could specify a giant regex
combining them yourself, but CRATE will do that for you to enhance config file
legibility and convenience). You can name each of them anything, e.g.

.. code-block:: ini

    [extra_regexes]

    my_regex_canadian_postcodes = [a-zA-Z][0-9][a-zA-Z]\w+[0-9][a-zA-Z][0-9]

    another_regex =
       \d+\#x    # a number then a hash sign then an 'x'
       \d+\ y    # then another number then a space then 'y'


.. _anon_config_db_section:

Database config sections
~~~~~~~~~~~~~~~~~~~~~~~~

Config file sections that define databases always have the ``url`` parameter.
Destination and admin databases need *only* this. Source databases have other
options, as below.

.. warning::

    You should permit CRATE write access to the destination and admin
    databases, but only read access to source databases. It doesn't need more,
    so read-only is safer.


Connection details
++++++++++++++++++

url
###

*String.*

Use SQLAlchemy URLs: see http://docs.sqlalchemy.org/en/latest/core/engines.html.

For example:

.. code-block:: ini

    url = mysql+mysqldb://username:password@127.0.0.1:3306/output_databasename?charset=utf8

You may need to install additional drivers, e.g.

.. code-block:: bash

    pip install SOME_DRIVER

... see :ref:`database drivers <database_drivers>`.


Data dictionary generation: input fields
++++++++++++++++++++++++++++++++++++++++

|ddgen_only|

In this section, fields (columns) can either be specified as ``column`` (to
match a column with that name any table) or ``table.column``, to match a
specific column in a specific table.

The specifications are case-insensitive.

Wildcards (``*`` and ``?``) may also be used (as per Python's fnmatch_). Thus,
one can write specifications like ``addr*.address_line_*`` to match all of
``address_current.address_line_1``, ``address_previous.address_line_4``, etc.


ddgen_omit_by_default
#####################

*Boolean.* Default: true.

By default, most fields (except PKs and patient ID codes) are marked as
``OMIT`` (see :ref:`decision <dd_decision>`), pending human review. If you want
to live dangerously, set this to False, and they will be marked as ``include``
from the outset.


ddgen_omit_fields
#################

*Multiline string, of field/column specifications.*

You can specify additional fields to omit (see :ref:`decision <dd_decision>`)
here. Settings here override :ref:`ddgen_include_fields
<anon_config_ddgen_include_fields>` -- that is, "omit" overrides "include".


.. _anon_config_ddgen_include_fields:

ddgen_include_fields
####################

*Multiline string, of field/column specifications.*

You can specify additional fields to include (see :ref:`decision
<dd_decision>`) here.

If a field contains scrubbing source information (see :ref:`scrub_src
<dd_scrub_src>`), it will also be omitted pending human review, regardless of
other settings.


ddgen_allow_no_patient_info
############################

*Boolean.* Default: false.

Allow the absence of patient info? Used to copy databases; WILL NOT ANONYMISE.


ddgen_per_table_pid_field
#########################

*String.*

Specify the name of a (typically integer) patient identifier (PID) field
present in EVERY table. It will be replaced by the research ID (RID) in the
destination database.


ddgen_table_defines_pids
########################

*String*

Specify a table which will define patient identifiers (PIDs) in the field
specified above. Only the PIDs in this field (and any other field defining
PIDs - see ``ddgen_pid_defining_fieldnames`` below) will be included in the
anonymisation. If both this option and ``ddgen_pid_defining_fieldnames`` are
left blank, the data dictionary will not work without manual editing.


ddgen_add_per_table_pids_to_scrubber
####################################

*Boolean.* Default: false.

Add every instance of a per-table PID field to the patient scrubber?

This is a very conservative setting, and should be unnecessary as the single
master "PID-defining" column (see :ref:`ddgen_pid_defining_fieldnames
<anon_config_ddgen_pid_defining_fieldnames>`) should be enough.

(Note that per-table PIDs are always replaced by RIDs -- this setting governs
whether the scrubber used to scrub free-text fields also works through every
single per-table PID.)


ddgen_master_pid_fieldname
##########################

*String.*

Master patient ID fieldname. Used for e.g. NHS numbers. This information will
be replaced by the MRID in the destination database.


ddgen_table_denylist
####################

*Multiline string.*

Denylist any tables when creating new data dictionaries?

This is case-insensitive, and you can use ``*`` and ``?`` wildcards (as per
Python's fnmatch_ module).

.. note::
    Formerly ``ddgen_table_blacklist``; changed 2020-07-20 as part of neutral
    language review.


ddgen_table_allowlist
#####################

*Multiline string.*

Allowlist any tables? (Allowlists override denylists.)

.. note::
    Formerly ``ddgen_table_whitelist``; changed 2020-07-20 as part of neutral
    language review.


ddgen_table_require_field_absolute
##################################

*Multiline string.*

List any fields that all tables MUST contain. If a table doesn't contain all of
the field(s) listed here, it will be skipped.


ddgen_table_require_field_conditional
#####################################

*Multiline string (one pair per line).*

List any fields that are required conditional on other fields. List them as one
or more pairs: ``A, B`` where B is required if A is present (or the table will
be skipped).


ddgen_field_denylist
####################

*Multiline string.*

Denylist any fields (regardless of their table) when creating new data
dictionaries? Wildcards of ``*`` and ``?`` operate as above.

.. note::
    Formerly ``ddgen_field_blacklist``; changed 2020-07-20 as part of neutral
    language review.


ddgen_field_allowlist
#####################

*Multiline string.*

Allowlist any fields? (Allowlists override denylists.)

.. note::
    Formerly ``ddgen_field_whitelist``; changed 2020-07-20 as part of neutral
    language review.


ddgen_pk_fields
###############

*Multiline string.*

Fieldnames assumed to be their table's PK.


.. _anon_config_ddgen_constant_content:

ddgen_constant_content
######################

*Boolean.* Default: false.

Assume that content stays constant?

Applies the ``C`` flags to PK fields; see :ref:`src_flags <dd_src_flags>`. This
then becomes the default, after which :ref:`ddgen_constant_content_tables
<anon_config_ddgen_constant_content_tables>` and
:ref:`ddgen_nonconstant_content_tables
<anon_config_ddgen_nonconstant_content_tables>` can override (of which,
:ref:`ddgen_nonconstant_content_tables
<anon_config_ddgen_nonconstant_content_tables>` takes priority if a table
matches both).


.. _anon_config_ddgen_constant_content_tables:

ddgen_constant_content_tables
#############################

*Multiline string.*

Table-specific overrides for :ref:`ddgen_constant_content
<anon_config_ddgen_constant_content>`, as above.


.. _anon_config_ddgen_nonconstant_content_tables:

ddgen_nonconstant_content_tables
################################

Table-specific overrides for :ref:`ddgen_constant_content
<anon_config_ddgen_constant_content>`, as above.


.. _anon_config_ddgen_addition_only:

ddgen_addition_only
###################

*Boolean.* Default: false.

Assume that records can only be added, not deleted?


ddgen_addition_only_tables
##########################

*Multiline string.*

Table-specific overrides for :ref:`ddgen_addition_only
<anon_config_ddgen_addition_only>`, similarly.


ddgen_deletion_possible_tables
##############################

*Multiline string.*

Table-specific overrides for :ref:`ddgen_addition_only
<anon_config_ddgen_addition_only>`, similarly.


.. _anon_config_ddgen_pid_defining_fieldnames:

ddgen_pid_defining_fieldnames
#############################

*Multiline string.*

Predefine field(s) that define the existence of patient IDs? UNUSUAL to want to
do this.


ddgen_scrubsrc_patient_fields
#############################

*Multiline string.*

Field names assumed to provide patient information for scrubbing.


ddgen_scrubsrc_thirdparty_fields
################################

*Multiline string.*

Field names assumed to provide third-party information for scrubbing.


ddgen_scrubsrc_thirdparty_xref_pid_fields
#########################################

*Multiline string.*

Field names assumed to contain PIDs of third parties (e.g. relatives also in
the patient database), to be used to look up the third party in a recursive
way, for scrubbing.


ddgen_required_scrubsrc_fields
##############################

*Multiline string.*

Are any :ref:`scrub_src <dd_scrub_src>` fields required (mandatory), i.e. must
have non-NULL data in at least one row (or the patient will be skipped)?


ddgen_scrubmethod_code_fields
#############################

*Multiline string.*

Fields to enforce the ``code`` :ref:`scrub_method <dd_scrub_method>` upon,
overriding the default method.


ddgen_scrubmethod_date_fields
#############################

*Multiline string.*

Fields to enforce the ``date`` :ref:`scrub_method <dd_scrub_method>` upon,
overriding the default method.


ddgen_scrubmethod_number_fields
###############################

*Multiline string.*

Fields to enforce the ``number`` :ref:`scrub_method <dd_scrub_method>` upon,
overriding the default method.


ddgen_scrubmethod_phrase_fields
###############################

*Multiline string.*

Fields to enforce the ``phrase`` :ref:`scrub_method <dd_scrub_method>` upon,
overriding the default method.


ddgen_safe_fields_exempt_from_scrubbing
#######################################

*Multiline string.*

Known safe fields, exempt from scrubbing.


ddgen_min_length_for_scrubbing
##############################

*Integer.* Default: 0.

Define minimum text column length for scrubbing (fields shorter than this value
are assumed safe). For example, specifying 10 will mean that ``VARCHAR(9)``
columns are assumed not to need scrubbing.


ddgen_truncate_date_fields
##########################

*Multiline string.*

Fields whose date should be truncated to the first of the month.


ddgen_filename_to_text_fields
#############################

*Multiline string.*

Fields containing filenames, which files should be converted to text.


ddgen_binary_to_text_field_pairs
################################

*Multiline string (one pair per line).*

Fields containing raw binary data from files (binary large objects; BLOBs),
whose contents should be converted to text -- paired with fields in the same
table containing their file extension (e.g. "pdf", ".PDF") or a filename having
that extension.

Specify it as a list of comma-joined pairs, e.g.

.. code-block:: ini

    ddgen_binary_to_text_field_pairs =
        binary1field, ext1field
        binary2field, ext2field
        ...

The first (``binaryfield``) can be specified as ``column`` or ``table.column``,
but the second must be ``column`` only.


ddgen_skip_row_if_extract_text_fails_fields
###########################################

*Multiline string.*

Specify any text-extraction rows for which you also want to set the flag
``skip_if_extract_fails`` (see :ref:`alter_method <dd_alter_method>`).


ddgen_rename_tables_remove_suffixes
###################################

*Multiline string.*

Automatic renaming of tables. This option specifies a list of suffixes to
remove from table names. (Typical use: you make a view with a suffix ``_x`` as
a working step, then you want the suffix removed for users.)


ddgen_patient_opt_out_fields
############################

*Multiline string.*

Fields that are used as patient opt-out fields (see above and :ref:`src_flags
<dd_src_flags>`).


ddgen_extra_hash_fields
#######################

*Multiline string (one pair per line; see below).*

Are there any fields you want hashed, in addition to the normal PID/MPID
fields? Specify these a list of ``FIELDSPEC, EXTRA_HASH_NAME`` pairs. For
example:

.. code-block:: ini

    ddgen_extra_hash_fields = CaseNumber*, case_number_hashdef

where ``case_number_hashdef`` is an extra hash definition (see
:ref:`extra_hash_config_sections <anon_config_extra_hash_config_sections>`, and
:ref:`alter_method <dd_alter_method>` in the data dictionary).


Data dictionary generation: destination indexing
++++++++++++++++++++++++++++++++++++++++++++++++

|ddgen_only|

ddgen_index_fields
##################

*Multiline string.*

Fields to apply an index to.


ddgen_allow_fulltext_indexing
#############################

*Boolean.* Default: true.

Allow full-text index creation?

(Disable for databases that don't support full-text indexes?)


Data dictionary generation: altering destination table/field names
++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

|ddgen_only|

ddgen_force_lower_case
######################

*Boolean.* Default: true.

Force all destination table/field names to lower case?


ddgen_convert_odd_chars_to_underscore
#####################################

*Boolean.* Default: true.

Convert spaces in table/fieldnames (yuk!) to underscores?


Other options for source databases
++++++++++++++++++++++++++++++++++

.. _anon_config_debug_row_limit:

debug_row_limit
###############

*Integer.* Default: 0.

Specify 0 (the default) for no limit, or a number of rows (e.g. 1000) to apply
to any tables listed in :ref:`debug_limited_tables
<anon_config_debug_limited_tables>`. For those tables, only this many rows will
be taken from the source database.

Use this, for example, to reduce the number of large documents fetched.

If you run a multiprocess/multithreaded anonymisation, this limit applies per
*process* (or task), not overall.

Note that these limits DO NOT APPLY to the fetching of patient- identifiable
information for anonymisation -- when a patient is processed, all identifiable
information for that patient is trawled.


.. _anon_config_debug_limited_tables:

debug_limited_tables
####################

*Multiline string.*

List of tables to which to apply :ref:`debug_row_limit
<anon_config_debug_row_limit>`.


.. _anon_config_hasher_definitions:

Hasher definitions
~~~~~~~~~~~~~~~~~~

If you use the ``hash`` :ref:`alter_method <dd_alter_method>`, you must specify
a config section there that is cross-referenced in the
:ref:`extra_hash_config_sections <anon_config_extra_hash_config_sections>`
parameter of the :ref:`[main] <anon_config_main_section>` section of the config
file.

Such config sections, named e.g. ``[my_extra_hasher]``, must have the following
parameters:


hash_method
+++++++++++

*String.*

Options are as for the :ref:`hash_method <anon_config_hash_method>` parameter
of the :ref:`[main] <anon_config_main_section>` section.


secret_key
++++++++++

*String.*

Secret key for the hasher.


Minimal anonymiser config
~~~~~~~~~~~~~~~~~~~~~~~~~

Here's an extremely minimal version for a hypothetical test database.
Many options are not shown and most comments have been removed.

..  literalinclude:: minimal_anonymiser_config.ini
    :language: ini


.. todo:: Check minimal anonymiser config example works.


.. _specimen_anonymiser_config:

Specimen config
~~~~~~~~~~~~~~~

A specimen anonymiser config file is available by running
``crate_anon_demo_config``. You can send its output to a file using ``>`` or
the ``--output`` option:

..  literalinclude:: _crate_anon_demo_config_help.txt
    :language: none

Here's the specimen anonymisation config file:

..  literalinclude:: _specimen_anonymiser_config.ini
    :language: ini
