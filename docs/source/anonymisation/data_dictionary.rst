..  crate_anon/docs/source/anonymisation/data_dictionary.rst

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


.. _data_dictionary:
Data dictionary (DD)
--------------------

The data dictionary is a catalogue of tables and columns (fields) in a source
database (typically containing identifiable data). It tells CRATE how to
transform the data into a de-identified destination database.

The data dictionary is a spreadsheet-style file: a tab-separated values (TSV)
file, OpenOffice Spreadsheet (ODS) file, or Microsoft Excel XLSX (OpenXML,
Excel 2007+) file.

It has a single header row, and columns as defined below.


.. _crate_anon_draft_dd:
Drafting a data dictionary
++++++++++++++++++++++++++

Once you have edited your :ref:`anonymiser config file <anon_config_file>` to
point to your source database, you can generate a **draft data dictionary**
like this:

.. code-block:: bash

    crate_anon_draft_dd --output mydd.xlsx

Now edit the data dictionary as required. (And then edit your config file so it
points to the data dictionary you have created.)

Full options for this tool are:

..  literalinclude:: _crate_anon_draft_dd.txt
    :language: none


Columns in the data dictionary
++++++++++++++++++++++++++++++

- The DD columns can be in any order as long as the header row matches the
  data, and the column headings include the headings shown here.

- In TSV format, lines beginning with a hash (``#``) are treated as comments
  and ignored, as are blank lines.


src_db
~~~~~~

*String.*

This column specifies the source database, using a name that matches one from
the ``source_databases`` list in the config file.


src_table
~~~~~~~~~

*String.*

This column specifies the table name in the source database.


src_field
~~~~~~~~~

*String.*

This column specifies the field (column) name in the source database.


src_datatype
~~~~~~~~~~~~

*String.*

This column gives the source column's SQL data type (e.g. `INT`,
`VARCHAR(50)`).


.. _dd_src_flags:
src_flags
~~~~~~~~~

*String.*

This field can be blank or can contain a string made up of one or more
characters. The characters have the following meanings:

=========== ===================================================================
Character   Meaning
=========== ===================================================================
``K``       | **PK.**
            | This field is the primary key (PK) for the table it's in.

``H``       | **ADD SOURCE HASH.**
            | Add source hash of the record, for incremental updates?

            - This flag may only be set for source PK (``K``) fields (which
              cannot then be omitted in the destination, and which require the
              `index=U` setting, so that a unique index is created for this
              field).

            - If set, a field is added to the destination table, with field
              name as set by the config's :ref:`source_hash_fieldname
              <source_hash_fieldname>` variable, containing a hash of the
              contents of the source record -- all fields that are not omitted,
              OR contain scrubbing information (``scrub_src``). The field is of
              type ``VARCHAR`` and its length is determined by the
              :ref:`hash_method <anon_config_hash_method>` option.

            - This table is then capable of incremental updates.

``C``       | **CONSTANT.**
            | Record contents are constant (will not change) for a given PK.

            - An alternative to ``H``. Can't be used with it.

            - The flag can be set only on ``src_pk`` fields, which can't be
              omitted in the destination, and which have the same index
              requirements as the ``H`` flag.

            - If set, no hash is added to the destination, but the destination
              contents are assumed to exist and not to have changed.

            - Be CAUTIOUS with this flag, i.e. certain that the contents will
              not change.

            - Intended for very data-intensive fields, such as BLOB fields
              containing binary documents, where hashing would be quite slow
              over many gigabytes of data.

            - Does not imply that the whole table cannot change!

``A``       | **ADDITION ONLY.**
            | Marks an addition-only table. It is assumed that records can only
              be added to this table, not deleted.

            - The field is permitted only for PK (``K``) fields.

``P``       | **PRIMARY PID.**
            | Primary patient ID field. If set,

            (a) This field will be used to link records for the same patient
                across all tables. It must therefore be present, and marked in
                the data dictionary, for ALL tables that contain
                patient-identifiable information.

            (b) If the field is not omitted: the field will be hashed as the
                primary ID (database patient primary key) in the destination,
                and a transient research ID (TRID) also added.

``*``       | **DEFINES PRIMARY PIDS.**
            | This field *defines* primary PIDs. If set, this row will be used
              to search for all patient IDs, and will define them for this
              database. Only those patients will be processed (for all tables
              containing patient info). Typically, this flag is applied to a
              SINGLE field in a SINGLE table, usually the principal patient
              registration/demographics table.

``M``       | **MASTER PID.**
            | Master ID (e.g. NHS number).
            | The field will be hashed with the master PID hasher.

``!``       | **OPT OUT.**
            | This field is used to mark that the patient wishes to opt out
              entirely. It must be in a table that also has a primary patient
              ID field (because that's the ID that will be omitted). If the
              opt-out field contains a value that's defined in the
              ``optout_col_values`` setting (see :ref:`config file
              <anon_config_file>`), that patient will be opted out entirely
              from the anonymised database.

``R``       | **REQUIRED SCRUBBER.**
            | If this field is a ``scrub_src`` field (see below), and this flag
              is set, then at least one non-NULL value for this field must be
              present for each patient, or no information will be processed for
              this patient. (Typical use: where you have a master patient index
              separate from the patient name table, and data might have been
              brought across partially, so there are some missing names. In
              this situation, text might go unscrubbed because the names are
              missing. Setting this flag for the name field will prevent this.)

=========== ===================================================================


.. _dd_scrub_src:
scrub_src
~~~~~~~~~

*String.*

One of the following values, or blank:

======================= =======================================================
Value                   Meaning
======================= =======================================================
``patient``             Contains patient-identifiable information that must be
                        removed from ``scrub_in`` fields.

``thirdparty``          Contains identifiable information about a carer,
                        family member, or other third party, which must be
                        removed from ``scrub_in`` fields.

``thirdparty_xref_pid`` This field is a patient identifier for ANOTHER patient
                        (such as a relative). The scrubber should recursively
                        include THAT patient's identifying information as
                        third-party information for THIS patient.

                        Fields marked thus, if included in the destination
                        database (see :ref:`decision <dd_decision>`), are
                        automatically hashed with the "primary" PID hasher,
                        allowing you to link connected records in the research
                        database. You cannot specify another :ref:`alter_method
                        <dd_alter_method>`.

======================= =======================================================


.. _dd_scrub_method:
scrub_method
~~~~~~~~~~~~

*String.*

Applicable to `scrub_src` fields, this column determines the manner in which
this field should be treated for scrubbing. It must be one of the following
values (or blank):

=========================== ===================================================
Value                       Meaning
=========================== ===================================================
``words``                   Treat as a set of textual words. This is the
                            default for all textual fields (e.g. `CHAR`,
                            `VARCHAR`, `TEXT`). Typically used for names: for
                            example, "John Smith" will scrub both "John" and
                            "Smith" separately. Also OK for e-mail addresses.

``phrase``                  Treat as a textual phrase (a sequence of words to
                            be replaced only when they occur in sequence).
                            Any superfluous whitespace at the start/end, or
                            between words, is ignored. Typically used for
                            address components: for example, "5 Tree Avenue"
                            will not scrub "tree" or "avenue" by themselves,
                            but this phrase will be scrubbed.

``phrase_unless_numeric``   If the value is numeric, ignore it. Otherwise,
                            treat it as ``phrase``. For example, if you have
                            an address field that is meant to be "building
                            number" (e.g. "5") but someone might put a name
                            (e.g. "Seaview") or an address line (e.g. "5 Tree
                            Road"), this will remove the more complex pieces of
                            information but will ignore "5" (preserving e.g.
                            "haloperidol 5 mg" elsewhere).

``number``                  Treat as a number. This is the default for all
                            numeric fields (e.g. `INTEGER`, `FLOAT`). If you
                            have a phone number in a text field, use this
                            method; it will be scrubbed regardless of
                            spacing/punctuation.

``code``                    Treat as an alphanumeric code. Suited to postcodes.
                            Very like the numeric method, but permits
                            non-digits.

``date``                    Treat as a date, and scrub any recognizable
                            representations of that date. This is the default
                            for all `DATE`/`DATETIME` fields.
=========================== ===================================================


.. _dd_decision:
decision
~~~~~~~~

*String.*

One of the following two values:

=========== ===================================================================
Value       Meaning
=========== ===================================================================
``OMIT``    Omit the field from the output entirely.
``include`` Include it.
=========== ===================================================================

This is case sensitive, for safety.


inclusion_values
~~~~~~~~~~~~~~~~

*String.*

Either blank, or an expression that evaluates to a Python iterable (e.g. list
or tuple) with Python's `ast.literal_eval()` function (see
https://docs.python.org/3.4/library/ast.html).

- If this is not blank/None, then it serves as a **ROW INCLUSION LIST** -- the
  source row will only be processed if the field's value is one of the
  inclusion values.

- It applies to the raw value from the database (before any transformation via
  ``alter_method``).

- This is not applied to ``scrub_src`` fields (which contribute to the scrubber
  regardless).

- Note that ``[None]`` is a list with one member, `None`, whereas ``None`` is
  equivalent to leaving the field blank.

Examples:

- ``[None, 0]``
- ``[True, 1, 'yes', 'true', 'Yes', 'True']``


exclusion_values
~~~~~~~~~~~~~~~~

*String.*

As for ``inclusion_values``, but the row is excluded if the field's value is in
the exclusion_values list.


.. _dd_alter_method:
alter_method
~~~~~~~~~~~~

*String.*

Manner in which to alter the data. Blank, or a comma-separated list of one or
more of the following. (You should replace aspects in capitals with appropriate
values.)

=============================== ===============================================
Component                       Meaning
=============================== ===============================================
``scrub``                       **Scrub in.** Applies to text fields only. The
                                field will have its contents anonymised (using
                                information from other fields). Use this for
                                any text field that end users might store
                                free-text comments in.

``truncate_date``               **Truncate this date to the first of the
                                month.** Applicable to text or date-as-text
                                fields.

``binary_to_text=EXTFIELDNAME`` **Convert a binary field (e.g. `VARBINARY`,
                                `BLOB`) to text (e.g. `LONGTEXT`).** Insert
                                your chosen field name in place of
                                `EXTFIELDNAME`. The binary data is taken to be
                                the representation of a document. The field
                                must be in the same source table, must contain
                                the file extension (e.g. ``'pdf'``, ``'.pdf'``)
                                or a filename with that extension (e.g.
                                ``'/some/path/mything.pdf'``), so that the
                                anonymiser knows how to treat the binary data
                                to extract text from it.

``filename_to_text``            As for the binary-to-text option, but the field
                                contains a full filename (the contents of which
                                is converted to text), rather than containing
                                binary data directly.

``filename_format_to_text=FMT`` A more powerful way of specifying a filename
                                that can be created using data from this table.
                                Replace `FMT` with an unquoted Python
                                str.format() string; see
                                https://docs.python.org/3.4/library/stdtypes.html#str.format.
                                The dictionary passed to `format()` is created
                                from all fields in the row.

                                Using an example from RiO: if your
                                ClientDocuments table contains a `ClientID`
                                column (with a value like ``999999``) and a
                                `Path` column (with a value like
                                ``appointment_letter.pdf``), and you know that
                                the actual file will then be found at
                                ``C:\some\path\999999\docs\appointment_letter.pdf``,
                                then you can specify this with

                                .. code-block:: none

                                    filename_format_to_text=C:\some\path\{ClientID}\docs\{Path}

                                You probably want to apply this
                                ``alter_method`` to the `Path` column in this
                                example, though that's not mandatory.

``skip_if_extract_fails``       If one of the text extraction methods is
                                specified, and this flag is also specified,
                                then the data row will be skipped if text
                                extraction fails (rather than inserted with a
                                NULL value for the text). This is helpful, for
                                example, if your text-processing pipeline
                                breaks; the option prevents rows being created
                                erroneously with NULL text values, so that a
                                subsequent incremental update will fix the
                                problems once you've fixed your text extraction
                                tools.

``html_unescape``               HTML encoding is removed, e.g. convert
                                ``&amp;`` to ``&`` and ``&lt;`` to ``<``

``html_untag``                  HTML tags are removed, e.g. from
                                ``<a href="http://somewhere">see link</a>``
                                to ``see link``

``hash=HASH_CONFIG_SECTION``    Hash this field, using the hasher specified in
                                the config file section that you name.

=============================== ===============================================

You can specify multiple options separated by commas.

Not all are compatible (e.g. scrubbing is for text; date truncation is for
dates).

If there's more than one, text extraction from BLOBs/files is performed first.
After that, they are executed in sequence. (The position of the
skip-if-text-extraction-fails flag is immaterial.)

A typical combination might be:

.. code-block:: none

    filename_to_text,skip_if_extract_fails,scrub

or:

.. code-block:: none

    html_untag,html_unescape,scrub


dest_table
~~~~~~~~~~

*String.*

Table name in the destination database.


dest_field
~~~~~~~~~~

*String.*

Field (column) name in the destination database.


dest_datatype
~~~~~~~~~~~~~

*String.* Default: none.

SQL data type in the destination database.

If omitted, the source SQL data type is translated appropriately.


index
~~~~~

*String.*

One of:

=========== ===================================================================
Value       Meaning
=========== ===================================================================
(blank)     No index.

``I``       Create a normal index on the destination field.

``U``       Create a unique index on the destination field.

``F``       Create a `FULLTEXT` index, for rapid searching within long text
            fields. Only applicable to one field per table.
=========== ===================================================================


indexlen
~~~~~~~~

*Integer.* Default: none.

Can be blank. If not, sets the prefix length of the index. This is mandatory in
MySQL if you apply a normal (+/- unique) index to a `TEXT` or `BLOB` field. It
is not required for `FULLTEXT` indexes.


comment
~~~~~~~

*String.*

Field (column) comment, stored in the destination database.


Minimal data dictionary example
+++++++++++++++++++++++++++++++

This illustrates a data dictionary for a fictional database.

Some more specialist columns (``inclusion_values``, ``exclusion_values``) are
not shown for clarity.

.. code-block:: none

    src_db  src_table  src_field    src_datatype  src_flags  scrub_src  scrub_method  decision  alter_method            dest_table  dest_field  dest_datatype  index  indexlen  comment
    ------- ---------- ------------ ------------- ---------- ---------- ------------- --------- ----------------------- ----------- ----------- -------------- ------ --------- ----------------------------------------------------

    # The source table "patients" defines our patients.
    # This is also a primary source of information that is used to build our scrubbers.
    # Most information shouldn't come through to the destination database, but some (e.g. DOB) is helpful in a truncated form.
    # This table also includes our master opt-out switch.

    mydb    patients   patientnum   INTEGER(11)   K*H        patient    number        OMIT                                                                                      Local patient ID (PID); will be replaced by RID+TRID
    mydb    patients   nhsnum       INTEGER(11)   M          patient    number        OMIT                                                                                      NHS number (MPID); will be replaced by MRID
    mydb    patients   dob          DATE                     patient    date          include   truncate_date           patients    dob         DATE                            Date of birth (truncated to first of month)
    mydb    patients   dod          DATE                                              include                           patients    dod         DATE                            Date of death, or NULL if alive
    mydb    patients   forename     VARCHAR(255)             patient    words         OMIT
    mydb    patients   surname      VARCHAR(255)             patient    words         OMIT
    mydb    patients   telephone    VARCHAR(255)             patient    number        OMIT                                                                                      A phone number.
    mydb    patients   opt_out_anon BIT           !

    # The "addresses" table gives (potentially several) addresses per patient.

    mydb    addresses  pk           INTEGER(11)   KH                                  include                           addresses   pk          INTEGER(11)     U               Arbitrary address PK.
    mydb    addresses  patientnum   INTEGER(11)   P                                   OMIT
    mydb    addresses  from_date    DATE                                              include                           addresses   from_date                   I
    mydb    addresses  to_date      DATE                                              include                           addresses   to_date                     I
    mydb    addresses  line1        VARCHAR(255)             patient    phrase        OMIT
    mydb    addresses  line2        VARCHAR(255)             patient    phrase        OMIT
    mydb    addresses  line3        VARCHAR(255)             patient    phrase        OMIT
    mydb    addresses  line4        VARCHAR(255)             patient    phrase        OMIT
    mydb    addresses  line5        VARCHAR(255)             patient    phrase        OMIT
    mydb    addresses  postcode     VARCHAR(10)              patient    code          OMIT                                                                                      UK postcode.
    mydb    addresses  lsoa         VARCHAR(10)                                       include                           addresses   lsoa                                        Lower Super Output Area, added by CRATE preprocessor (calculated from postcode).
    mydb    addresses  imd          INTEGER                                           include                           addresses   imd                                         UK Index of Multiple Deprivation, added by CRATE preprocessor.

    # The "relatives" table gives us some third-party information to add to our scrubbers.

    mydb    relatives  pk           INTEGER(11)   KH                                  OMIT
    mydb    relatives  patientnum   INTEGER(11)   P                                   OMIT
    mydb    relatives  relationship VARCHAR(255)                                      OMIT
    mydb    relatives  forename     VARCHAR(255)             thirdparty words         OMIT
    mydb    relatives  surname      VARCHAR(255)             thirdparty words         OMIT

    # The "notes" table contains simple text that needs scrubbing.

    mydb    notes      pk           INTEGER(11)   KH                                  include                           notes       pk          INTEGER(11)      U
    mydb    notes      patientnum   INTEGER(11)   P                                   OMIT                                                                                      Patient ID will be replaced by RID+TRID
    mydb    notes      when         DATETIME                                          include                           notes       when        DATETIME         I
    mydb    notes      note         VARCHAR(MAX)                                      include   scrub                   notes       note        LONGTEXT                        Gives the scrubbed note.

    # The "documents" table uses filenames to refer to binary documents on disk, which need scrubbing.
    # (If binary documents won't change once added, you might want to set the "C" flag on "doc_id", instead of "H", for efficiency.)

    mydb    documents  doc_id       INTEGER(11)   KH                                  include                           documents   doc_id      INTEGER(11)      U              Document PK
    mydb    documents  patientnum   INTEGER(11)   P                                   OMIT                                                                                      Patient ID will be replaced by RID+TRID
    mydb    documents  when_added   DATETIME                                          include                           documents   when_added  DATETIME         I
    mydb    documents  filename     VARCHAR(255)                                      include   filename_to_text,scrub  documents   contents    LONGTEXT         F              Becomes scrubbed document contents with FULLTEXT index.



.. todo:: Check minimal data dictionary example works.
