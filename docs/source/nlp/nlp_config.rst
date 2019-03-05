.. crate_anon/docs/source/nlp/nlp_config.rst

..  Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).
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

.. _shlex: https://docs.python.org/3/library/shlex.html

.. _nlp_config:

NLP config file
---------------

.. contents::
   :local:

Overview
~~~~~~~~

The CRATE NLP config file controls the behaviour of the NLP manager. It defines
source and destination databases, and one or more **NLP definitions**.

You can generate a specimen config file with

.. code-block:: bash

    crate_nlp --democonfig > test_nlp_config.ini

You should save this, then edit it to your own needs.

Make it point to other necessary things, like your GATE installation if you
want to use GATE NLP.

For convenience, you may want the `CRATE_NLP_CONFIG` environment variable to
point to this file. (Otherwise you must specify it each time.)


Detail
~~~~~~

The config file describes NLP definitions, such as ‘people_and_places’,
‘drugs_and_doses’, or ‘haematology_white_cell_differential’. You choose the
names of these NLP definitions as you define them. You select one when you run
the NLP manager (using the ``--nlpdef`` argument) [#nlpdefinitionclass]_.

The NLP definition sets out the following things.

- *“Where am I going to find my source text?”* You specify this by giving one
  or more ``inputfielddefs``. Each one of those specifies (via its own config
  section) a database/table/field combination, such as the ‘Notes’ field of the
  ‘Progress Notes’ table in the ‘RiO’ database, or the ‘text_content’ field of
  the ‘Clinical_Documents’ table in the ‘CDL’ database, or some such
  [#inputfieldconfig]_.

  - CRATE will always store minimal source information (database, table,
    integer PK) with the NLP output. However, for convenience you are also
    likely to want to copy some other key information over to the output, such
    as patients’ research identifiers (RIDs). You can specify these via the
    ``copyfields`` option to the input field definitions. For validation
    purposes, you might even choose to copy the full source text (just for
    convenience), but it’s unlikely you’d want to do this routinely (because it
    wastes space).

- *“Which NLP processor will run, and where will it store its output?”* This
  might be an external GATE program specializing in finding drug names, or one
  of CRATE’s built-in regular expression (regex) parsers, such as for
  inflammatory markers from blood tests. The choice of NLP processor also
  determines the fields that will appear in the output; for example, a
  drug-detecting NLP program might provide fields such as ‘drug’, ‘dose’,
  ‘units’, and ‘route’, while a white-cell differential processor might provide
  output such as ‘cell type’, ‘value_in_billion_per_litre’, and so on
  [#nlpparser]_.

  - In fact, GATE applications can simultaneously provide *more than one type*
    of output; for example, GATE’s demonstration people-and-places application
    yields both ‘person’ information (rule, firstname, surname, gender...) and
    ‘location’ information (rule, loctype...), and it can be computationally
    more efficient to run them together. Therefore, CRATE supports multiple
    types of output from ‘single’ NLP processors.

  - Each NLP processor may have its own set of options. For example, the GATE
    controller requires information about the specific external GATE app to
    run, and about any necessary environment variables. Others, such as CRATE’s
    build-in regular expression parsers, are simpler.

  - You might want all of your “drugs and doses” information to be stored in a
    single table (such that drugs found in your Progress_Notes and drugs found
    in your Clinical_Documents get stored together); this would be common and
    sensible (and CRATE will keep a record of where the information came from).
    However, it’s possible that you might want to segregate them (e.g. having
    C-reactive protein information extracted from your Progress_Notes stored in
    a different table to C-reactive protein information extracted from your
    High_Sensitivity_CRP_Notes_For_Bobs_Project table).

  - For GATE apps that provide more than one type of output structure, you will
    need to specify more than one output table.

  - You can batch different NLP processors together. For example, the demo
    config batches up CRATE’s internal regular expression NLP processors
    together. This is more efficient, because one record fetched from the
    source database can then be sent to multiple NLP processors. However, it’s
    less helpful if you are developing new NLP tools and want to be able to
    re-run just one NLP tool frequently.

All NLP configuration ‘chunks’ are sections within the NLP config file, which
is in standard .INI format. For example, an input field definition is a
section; a database definition is a section; an environment variable section
for use with external programs is a section; and so on.

To allow incremental updates, CRATE will keep a master progress table, storing
a reference to the source information (database, table, PK), a hash of the
source information (to work out later on if the source has changed), and a
date/time when the NLP was last run, and the name of the NLP definition that
was run.

It’s definitely better if your source table has integer PKs, but you might not
have a choice in the matter (and be unable to add one to a read-only source
database), so CRATE also supports string PKs. In this instance it will create
an integer by hashing the string and store that along with the string PK
itself. (That integer is not guaranteed to be unique, because of *hash
collisions* [#hashcollisions]_, but it allows some efficiency to be added.)


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


.. _nlp_config_section_nlpdef:

Config file section: NLP definition
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These are config file sections named ``[nlpdef:XXX]`` where ``XXX`` is the name
of one of your NLP definitions.

These map from *inputs (from your database)* to *processors* and a
*progress-tracking database*, and give names to those mappings.

**These are the "top-level" configuration sections, referred to when you launch
CRATE's NLP tools from the command line. Start here.**

inputfielddefs
##############

*Multiline string.*

List of input fields to parse. Each is the name of an :ref:`input field
definition <nlp_config_section_input>` in the config file.

Input to the NLP processor(s) comes from one or more source fields (columns),
each within a table within a database. This list refers to config sections that
define those fields in more detail.

.. _nlp_config_nlpdef_processors:

processors
##########

*Multiline string.*

Which NLP processors shall we use?

Specify these as a list of ``processor_type, processor_config_section`` pairs.
For example, one might be:

.. code-block:: none

    GATE mygateproc_name_location

and CRATE would then look for a :ref:`processor definition
<nlp_config_section_processor>` in a config file section named
``[processor:mygateproc_name_location]``, and expect it to have the information
required for a GATE processor.

For possible processor types, see ``crate_nlp --listprocessors``.

progressdb
##########

*String.*

Secret progress database; the name of a :ref:`database definition
<nlp_config_section_database>` in the config file.

To allow incremental updates, information is stored in a progress table.
The database name is a cross-reference to another section in this config
file. The table name within this database is hard-coded to
``crate_nlp_progress``.

hashphrase
##########

*String.*

You should insert a hash phrase of your own here. However, it's not especially
secret (it's only used for change detection and users are likely to have access
to the source material anyway), and its specific value is unimportant.

temporary_tablename
###################

*String.* Default: ``_crate_nlp_temptable``.

Temporary table name to use (in progress and destination databases).

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


.. _nlp_config_section_input:

Config file section: input field definition
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These are config file sections named ``[input:XXX]`` where ``XXX`` is the name
of one of your input field definitions.

These define database "inputs" in more detail, including the database, table,
and field (column) containing the input, the associated primary key field, and
fields that should be copied to the destination to make subsequent work easier
(e.g. patient research IDs).

They are referred to by the :ref:`NLP definition <nlp_config_section_nlpdef>`.

srcdb
#####

*String.*

Source database; the name of a :ref:`database definition
<nlp_config_section_database>` in the config file.

srctable
########

*String.*

The name of the table in the source database.

srcpkfield
##########

*String.*

The name of the primary key field (column) in the source table.

srcfield
########

*String.*

The name of the field (column) in the source table that contains the data of
interest.

srcdatetimefield
################

*String.* Optional (but advisable).

The name of the ``DATETIME`` field (column) in the source table that represents
the date/time of the source data. If present, this information will be copied
to the output; see :ref:`Standard NLP output columns
<standard_nlp_output_columns>`.

.. _nlp_config_input_copyfields:

copyfields
##########

*Multiline string.* Optional.

Names of fields to copy from the source table to the destination (NLP output)
table.

indexed_copyfields
##################

*Multiline string.*

Optional subset of :ref:`copyfields <nlp_config_input_copyfields>` that should
be indexed in the destination (NLP output) table.

debug_row_limit
###############

*Integer.* Default: 0.

Debugging option. Specify this to set the maximum number of rows to be fetched
from the source table. Specifying 0 means "no limit".


.. _nlp_config_section_processor:

Config file section: processor definition
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These are config file sections named ``[processor:XXX]`` where ``XXX`` is the
name of one of your NLP processors.

These control the behaviour of individual NLP processors.

In the case of CRATE's built-in processors, the only configuration needed is
the destination database/table, but for some, like GATE applications, you need
to define more -- such as how to run the external program, and what sort of
table structure should be created to receive the results.

The format depends on the specific processor *type* (see :ref:`processors
<nlp_config_nlpdef_processors>`).

Parameters for all NLP parsers
##############################

destdb
++++++

*String.*

Destination database; the name of a :ref:`database definition
<nlp_config_section_database>` in the config file.

Parameters for CRATE Python regular expression NLP parsers
##########################################################

desttable
+++++++++

*String.*

The name of the table in the destination database in which the results should
be stored.

Parameters for GATE processors
##############################

What's GATE? See the section on :ref:`GATE NLP <gate_nlp>`.

outputtypemap
+++++++++++++

*Multiline string.*

Map GATE '_type' parameters to possible destination tables (in
case-insensitive fashion). This parameter is follows is a list of pairs, one pair per line.

- The first item of each is the annotation type coming out of the GATE system.

- The second is the output type section defined in this file (as a separate
  section). Those sections (q.v.) define tables and columns (fields).

Example:

.. code-block:: none

    outputtypemap =
        Person output_person
        Location output_location

This example would take output from GATE labelled with ``_type=Person`` and
send it to output defined in the ``[output:output_person]`` section of the
config file -- see :ref:`GATE output definitions
<nlp_config_section_gate_output>`. Equivalently for the ``Location`` type.

.. _nlp_config_section_gate_progargs:

progargs
++++++++

*Multiline string.*

This parameter defines how we will launch GATE. See :ref:`GATE NLP <gate_nlp>`.

GATE NLP is done by an external program.

In this parameter, we specify a program and associated arguments. Here's an
example:

.. code-block:: none

    progargs = java
        -classpath "{NLPPROGDIR}"{OS_PATHSEP}"{GATEDIR}/bin/gate.jar"{OS_PATHSEP}"{GATEDIR}/lib/*"
        -Dgate.home="{GATEDIR}"
        CrateGatePipeline
        --gate_app "{GATEDIR}/plugins/ANNIE/ANNIE_with_defaults.gapp"
        --annotation Person
        --annotation Location
        --input_terminator END_OF_TEXT_FOR_NLP
        --output_terminator END_OF_NLP_OUTPUT_RECORD
        --log_tag {NLPLOGTAG}
        --verbose

The example shows how to use Java to launch a specific Java program
(``CrateGatePipeline``), having set a path to find other Java classes, and how
to to pass arguments to the program itself.

NOTE IN PARTICULAR:

- Use double quotes to encapsulate any filename that may have spaces within it
  (e.g. ``C:/Program Files/...``).

- Use a **forward slash directory separator, even under Windows.**

- ... ? If that doesn't work, use a double backslash, ``\\``.

- Under Windows, use a semicolon to separate parts of the Java classpath.
  Under Linux, use a colon.

  So a Linux Java classpath looks like

  .. code-block:: none

    /some/path:/some/other/path:/third/path

  and a Windows one looks like

  .. code-block:: none

    C:/some/path;C:/some/other/path;C:/third/path

- To make this simpler, we can define the environment variable ``OS_PATHSEP``
  (by analogy to Python's os.pathsep). See the :ref:`environment variable
  <nlp_config_section_envvar>` section below.

- You can use substitutable parameters:

  +-----------------+---------------------------------------------------------+
  | ``{X}``         | Substitutes variable X from the environment you specify |
  |                 | (see below).                                            |
  +-----------------+---------------------------------------------------------+
  | ``{NLPLOGTAG}`` | Additional environment variable that indicates the      |
  |                 | process being run; used to label the output from        |
  |                 | the ``CrateGatePipeline`` application.                  |
  +-----------------+---------------------------------------------------------+

.. _nlp_config_section_gate_progenvsection:

progenvsection
++++++++++++++

*String.*

:ref:`Environment variable config section <nlp_config_section_envvar>` to use
when launching this program.

.. _nlp_config_section_gate_inputterminator:

input_terminator
++++++++++++++++

*String.*

The external GATE program is slow, because NLP is slow. Therefore, we set up
the external program and use it repeatedly for a whole bunch of text.
Individual pieces of text are sent to it (via its ``stdin``). We finish our
piece of text with a delimiter, which should (a) be specified in the ``-it`` or
``--input_terminator` parameter to the CRATE ``CrateGatePipeline`` interface
(above), and (b) be set here, TO THE SAME VALUE. The external program will
return a TSV-delimited set of field/value pairs, like this:

.. code-block:: none

    field1\\tvalue1\\tfield2\\tvalue2...
    field1\\tvalue3\\tfield2\\tvalue4...
    ...
    OUTPUTTERMINATOR

... where ``OUTPUTTERMINATOR`` is something that you (a) specify with the
``-ot`` or ``--output_terminator`` parameter above, and (b) set via the config
file :ref:`output_terminator <nlp_config_section_gate_outputterminator>`, TO
THE SAME VALUE.

.. _nlp_config_section_gate_outputterminator:

output_terminator
+++++++++++++++++

*String.*

See :ref:`input_terminator <nlp_config_section_gate_inputterminator>`.

max_external_prog_uses
++++++++++++++++++++++

*Integer.*

If the external GATE program leaks memory, you may wish to cap the number of
uses before it's restarted. Specify this option if so. Specify 0 or omit the
option entirely to ignore this.


.. _nlp_config_section_gate_output:

Config file section: GATE output definition
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These are config file sections named ``[output:XXX]`` where ``XXX`` is the
name of one of your GATE output types.

This is an additional thing we need for GATE applications, since CRATE doesn't
automatically know what sort of output they will produce. The tables and
SPECIFIC output fields for a given GATE processor are defined here.

desttable
#########

*String.*

Table name in the destination (NLP output) database into which to write results
from the GATE NLP application.

renames
#######

*Multiline string.*

A list of ``from, to`` things to rename from the GATE output en route to the
database. In each case, the ``from`` item is the name of a GATE output
annotation. The ``to`` item is the destination field/column name.

Specify one pair per line. You can can quote, using shlex_ rules.
Case-sensitive.

This example:

.. code-block:: none

    renames =
        firstName   firstname

renames ``firstName`` to ``firstname``.

A more relevant example, in which the GATE annotation names are clearly
not well suited to being database column names:

.. code-block:: none

    renames =
        drug-type           drug_type
        dose-value          dose_value
        dose-unit           dose_unit
        dose-multiple       dose_multiple
        Directionality      directionality
        Experiencer         experiencer
        "Length of Time"    length_of_time
        Temporality         temporality
        "Unit of Time"      unit_of_time

null_literals
#############

*Multiline string.*

Define values that will be treated as ``NULL`` in SQL. For example, sometimes
GATE provides the string ``null`` for a NULL value; we can convert to a proper
SQL NULL.

The parameter is treated as a sequence of words; shlex_ quoting rules apply.

Example:

.. code-block:: none

    null_literals =
        null
        ""

destfields
##########

*Multiline string.*

Defines the database field (column) types used in the output database. This is
how you tell the database how much space to allocate for information that will
come out of GATE. Each line is a ``column_name, sql_type`` pair. Example:

.. code-block:: none

    destfields =
        rule        VARCHAR(100)
        firstname   VARCHAR(100)
        surname     VARCHAR(100)
        gender      VARCHAR(7)
        kind        VARCHAR(100)

indexdefs
#########

*Multiline string.*

Fields to index in the destination table.

Each line is a ``indexed_field, index_length`` pairs. The ``index_length``
should be an integer or ``None``. Example:

.. code-block:: none

    indexdefs =
        firstname   64
        surname     64


.. _nlp_config_section_envvar:

Config file section: environment variables definition
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These are config file sections named ``[env:XXX]`` where ``XXX`` is the
name of one of your environment variable definition blocks.

We define environment variable groups here, with one group per section.

When a section is selected (e.g. by a :ref:`progenvsection
<nlp_config_section_gate_progenvsection>` parameter in a GATE NLP processor
definition as above), these variables can be substituted into the
:ref:`progargs <nlp_config_section_gate_progargs>` part of the NLP definition
(for when external programs are called) and are available in the operating
system environment for those programs themselves.

- The environment will start by inheriting the parent environment, then add
  variables here.

- Keys are case-sensitive.

Example:

.. code-block:: ini

    [env:MY_ENV_SECTION]

    GATEDIR = /home/myuser/somewhere/GATE_Developer_8.0
    NLPPROGDIR = /home/myuser/somewhere/crate_anon/nlp_manager/compiled_nlp_classes
    MEDEXDIR = /home/myuser/somewhere/Medex_UIMA_1.3.6
    KCONNECTDIR = /home/myuser/somewhere/yodie-pipeline-1-2-umls-only
    OS_PATHSEP = :


.. _nlp_config_section_database:

Config file section: database definition
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These are config file sections named ``[database:XXX]`` where ``XXX`` is the
name of one of your database definitions.

These are simply URLs that define how to connect to different databases.

url
###

*String.*

The URL of the database.  Use SQLAlchemy URLs:
http://docs.sqlalchemy.org/en/latest/core/engines.html.

Example:

.. code-block:: ini

    [database:MY_SOURCE_DATABASE]

    url = mysql+mysqldb://myuser:password@127.0.0.1:3306/anonymous_output_db?charset=utf8


Parallel processing
~~~~~~~~~~~~~~~~~~~

There are two ways to parallelize CRATE NLP.

#. You can run multiple NLP processors at the same time, by specifying multiple
   NLP processors in a single NLP definition within your configuration file.

   There can be different source of bottlenecks. One is if database access is
   limiting. Specifying multiple NLP processors means that text is fetched once
   (for a given set of input fields) and then run through multiple NLP
   processors in one go.

   However, GATE apps can take e.g. 1 Gb RAM per process, so be careful if
   trying to run several of those! CRATE’s regular expression parsers use very
   little RAM (and can go quite fast: e.g. 2 CPUs processing about 15,000
   records through 10 regex parsers in about 166 s, or of the order of 1 kHz).

#. You can run multiple simultaneous copies of CRATE's NLP manager.

   This will divide up the work across the copies (by dividing up the records
   retrieved from the database).

You can use both strategies simultaneously.


.. _specimen_nlp_config:

Specimen config
~~~~~~~~~~~~~~~

A specimen NLP config is available by running ``crate_nlp --democonfig``. In
the source, it is :data:`crate_anon.nlp_manager.constants.DEMO_CONFIG`.

Here's the specimen NLP config as of 2019-07-02:

.. code-block:: ini

    # Configuration file for CRATE NLP manager (crate_nlp).
    # Version 0.18.63 (2019-02-12).
    #
    # PLEASE SEE THE HELP.

    # =============================================================================
    # A. Individual NLP definitions
    #
    #    These map from INPUTS FROM YOUR DATABASE to PROCESSORS and a PROGRESS-
    #    TRACKING DATABASE, and give names to those mappings.
    # =============================================================================
    # - referred to by the nlp_manager.py's command-line arguments
    # - You are likely to need to alter these (particularly the bits in capital
    #   letters) to refer to your own database(s).

    # -----------------------------------------------------------------------------
    # GATE people-and-places demo
    # -----------------------------------------------------------------------------

    [nlpdef:MY_NLPDEF_NAME_LOCATION_NLP]

        # Input is from one or more source databases/tables/fields.
        # This list refers to config sections that define those fields in more
        # detail.

    inputfielddefs =
        INPUT_FIELD_CLINICAL_DOCUMENTS
        INPUT_FIELD_PROGRESS_NOTES

        # Which NLP processors shall we use?
        # Specify these as a list of (processor_type, config_section) pairs.
        # For possible processor types, see "crate_nlp --listprocessors".

    processors =
        GATE procdef_gate_name_location

        # To allow incremental updates, information is stored in a progress table.
        # The database name is a cross-reference to another section in this config
        # file. The table name is hard-coded to 'crate_nlp_progress'.

    progressdb = DESTINATION_DATABASE
    hashphrase = doesnotmatter
        # ... you should replace this with a hash phrase of your own, but it's not
        # especially secret (it's only used for change detection and users are
        # likely to have access to the source material anyway), and its specific
        # value is unimportant.

        # Temporary tablename to use (in progress and destination databases).
        # Default is _crate_nlp_temptable
    # temporary_tablename = _crate_nlp_temptable

    # -----------------------------------------------------------------------------
    # KConnect (Bio-YODIE) GATE app
    # -----------------------------------------------------------------------------

    [nlpdef:MY_NLPDEF_KCONNECT]

    inputfielddefs =
        INPUT_FIELD_CLINICAL_DOCUMENTS
        INPUT_FIELD_PROGRESS_NOTES
    processors =
        GATE procdef_gate_kconnect
    progressdb = DESTINATION_DATABASE
    hashphrase = doesnotmatter

    # -----------------------------------------------------------------------------
    # Medex-UIMA drug-finding app
    # -----------------------------------------------------------------------------

    [nlpdef:MY_NLPDEF_MEDEX_DRUGS]

    inputfielddefs =
        INPUT_FIELD_CLINICAL_DOCUMENTS
        INPUT_FIELD_PROGRESS_NOTES
    processors =
        Medex procdef_medex_drugs
    progressdb = DESTINATION_DATABASE
    hashphrase = doesnotmatter

    # -----------------------------------------------------------------------------
    # CRATE number-finding Python regexes
    # -----------------------------------------------------------------------------

    [nlpdef:MY_NLPDEF_BIOMARKERS]

    inputfielddefs =
        INPUT_FIELD_CLINICAL_DOCUMENTS
        INPUT_FIELD_PROGRESS_NOTES

    processors =
        # -------------------------------------------------------------------------
        # Biochemistry
        # -------------------------------------------------------------------------
        CRP procdef_crp
        CRPValidator procdef_validate_crp
        Sodium procdef_sodium
        SodiumValidator procdef_validate_sodium
        TSH procdef_tsh
        TSHValidator procdef_validate_tsh
        # -------------------------------------------------------------------------
        # Clinical
        # -------------------------------------------------------------------------
        Height procdef_height
        HeightValidator procdef_validate_height
        Weight procdef_weight
        WeightValidator procdef_validate_weight
        Bmi procdef_bmi
        BmiValidator procdef_validate_bmi
        Bp procdef_bp
        BpValidator procdef_validate_bp
        # -------------------------------------------------------------------------
        # Cognitive
        # -------------------------------------------------------------------------
        MMSE procdef_mmse
        MMSEValidator procdef_validate_mmse
        ACE procdef_ace
        ACEValidator procdef_validate_ace
        MiniACE procdef_mini_ace
        MiniACEValidator procdef_validate_mini_ace
        MOCA procdef_moca
        MOCAValidator procdef_validate_moca
        # -------------------------------------------------------------------------
        # Haematology
        # -------------------------------------------------------------------------
        ESR procdef_esr
        ESRValidator procdef_validate_esr
        WBC procdef_wbc
        WBCValidator procdef_validate_wbc
        Basophils procdef_basophils
        BasophilsValidator procdef_validate_basophils
        Eosinophils procdef_eosinophils
        EosinophilsValidator procdef_validate_eosinophils
        Lymphocytes procdef_lymphocytes
        LymphocytesValidator procdef_validate_lymphocytes
        Monocytes procdef_monocytes
        MonocytesValidator procdef_validate_monocytes
        Neutrophils procdef_neutrophils
        NeutrophilsValidator procdef_validate_neutrophils

    progressdb = DESTINATION_DATABASE
    hashphrase = doesnotmatter

        # Specify the maximum number of rows to be processed before a COMMIT is
        # issued on the database transaction(s). This prevents the transaction(s)
        # growing too large.
        # Default is 1000.
    max_rows_before_commit = 1000

        # Specify the maximum number of source-record bytes (approximately!) that
        # are processed before a COMMIT is issued on the database transaction(s).
        # This prevents the transaction(s) growing too large. The COMMIT will be
        # issued *after* this limit has been met/exceeded, so it may be exceeded if
        # the transaction just before the limit takes the cumulative total over the
        # limit.
        # Default is 83886080.
    max_bytes_before_commit = 83886080


    # =============================================================================
    # B. NLP processor definitions
    #
    #    These control the behaviour of individual NLP processors.
    #    In the case of CRATE's built-in processors, the only configuration needed
    #    is the destination database/table, but for some, like GATE applications,
    #    you need to define more -- such as how to run the external program, and
    #    what sort of table structure should be created to receive the results.
    # =============================================================================
    # - You're likely to have to modify the destination databases these point to,
    #   but otherwise you can probably leave them as they are.

    # -----------------------------------------------------------------------------
    # Specimen CRATE regular expression processor definitions
    # -----------------------------------------------------------------------------

        # Most of these are very simple, and just require a destination database
        # (as a cross-reference to a database section within this file) and a
        # destination table.

        # Biochemistry

    [processor:procdef_crp]
    destdb = DESTINATION_DATABASE
    desttable = crp
    [processor:procdef_validate_crp]
    destdb = DESTINATION_DATABASE
    desttable = validate_crp

    [processor:procdef_sodium]
    destdb = DESTINATION_DATABASE
    desttable = sodium
    [processor:procdef_validate_sodium]
    destdb = DESTINATION_DATABASE
    desttable = validate_sodium

    [processor:procdef_tsh]
    destdb = DESTINATION_DATABASE
    desttable = tsh
    [processor:procdef_validate_tsh]
    destdb = DESTINATION_DATABASE
    desttable = validate_tsh

        # Clinical

    [processor:procdef_height]
    destdb = DESTINATION_DATABASE
    desttable = height
    [processor:procdef_validate_height]
    destdb = DESTINATION_DATABASE
    desttable = validate_height

    [processor:procdef_weight]
    destdb = DESTINATION_DATABASE
    desttable = weight
    [processor:procdef_validate_weight]
    destdb = DESTINATION_DATABASE
    desttable = validate_weight

    [processor:procdef_bmi]
    destdb = DESTINATION_DATABASE
    desttable = bmi
    [processor:procdef_validate_bmi]
    destdb = DESTINATION_DATABASE
    desttable = validate_bmi

    [processor:procdef_bp]
    destdb = DESTINATION_DATABASE
    desttable = bp
    [processor:procdef_validate_bp]
    destdb = DESTINATION_DATABASE
    desttable = validate_bp

        # Cognitive

    [processor:procdef_mmse]
    destdb = DESTINATION_DATABASE
    desttable = mmse
    [processor:procdef_validate_mmse]
    destdb = DESTINATION_DATABASE
    desttable = validate_mmse

    [processor:procdef_ace]
    destdb = DESTINATION_DATABASE
    desttable = ace
    [processor:procdef_validate_ace]
    destdb = DESTINATION_DATABASE
    desttable = validate_ace

    [processor:procdef_mini_ace]
    destdb = DESTINATION_DATABASE
    desttable = mini_ace
    [processor:procdef_validate_mini_ace]
    destdb = DESTINATION_DATABASE
    desttable = validate_mini_ace

    [processor:procdef_moca]
    destdb = DESTINATION_DATABASE
    desttable = moca
    [processor:procdef_validate_moca]
    destdb = DESTINATION_DATABASE
    desttable = validate_moca

        # Haematology

    [processor:procdef_esr]
    destdb = DESTINATION_DATABASE
    desttable = esr
    [processor:procdef_validate_esr]
    destdb = DESTINATION_DATABASE
    desttable = validate_esr

    [processor:procdef_wbc]
    destdb = DESTINATION_DATABASE
    desttable = wbc
    [processor:procdef_validate_wbc]
    destdb = DESTINATION_DATABASE
    desttable = validate_wbc

    [processor:procdef_basophils]
    destdb = DESTINATION_DATABASE
    desttable = basophils
    [processor:procdef_validate_basophils]
    destdb = DESTINATION_DATABASE
    desttable = validate_basophils

    [processor:procdef_eosinophils]
    destdb = DESTINATION_DATABASE
    desttable = eosinophils
    [processor:procdef_validate_eosinophils]
    destdb = DESTINATION_DATABASE
    desttable = validate_eosinophils

    [processor:procdef_lymphocytes]
    destdb = DESTINATION_DATABASE
    desttable = lymphocytes
    [processor:procdef_validate_lymphocytes]
    destdb = DESTINATION_DATABASE
    desttable = validate_lymphocytes

    [processor:procdef_monocytes]
    destdb = DESTINATION_DATABASE
    desttable = monocytes
    [processor:procdef_validate_monocytes]
    destdb = DESTINATION_DATABASE
    desttable = validate_monocytes

    [processor:procdef_neutrophils]
    destdb = DESTINATION_DATABASE
    desttable = neutrophils
    [processor:procdef_validate_neutrophils]
    destdb = DESTINATION_DATABASE
    desttable = validate_neutrophils

    # -----------------------------------------------------------------------------
    # Specimen GATE demo people/places processor definition
    # -----------------------------------------------------------------------------

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Define the processor
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    [processor:procdef_gate_name_location]

        # Which database will this processor write to?

    destdb = DESTINATION_DATABASE

        # Map GATE '_type' parameters to possible destination tables (in
        # case-insensitive fashion). What follows is a list of pairs: the first
        # item is the annotation type coming out of the GATE system, and the second
        # is the output type section defined in this file (as a separate section).
        # Those sections (q.v.) define tables and columns (fields).

    outputtypemap =
        Person output_person
        Location output_location

        # GATE NLP is done by an external program.
        # SEE THE MANUAL FOR DETAIL.
        #
        # Here we specify a program and associated arguments, and an optional
        # environment variable section.
        # The example shows how to use Java to launch a specific Java program
        # (CrateGatePipeline), having set a path to find other Java classes, and then to
        # pass arguments to the program itself.
        #
        # NOTE IN PARTICULAR:
        # - Use double quotes to encapsulate any filename that may have spaces
        #   within it (e.g. C:/Program Files/...).
        #   Use a forward slash director separator, even under Windows.
        #   ... ? If that doesn't work, use a double backslash, \.
        # - Under Windows, use a semicolon to separate parts of the Java classpath.
        #   Under Linux, use a colon.
        # - So a Linux Java classpath looks like
        #       /some/path:/some/other/path:/third/path
        #   and a Windows one looks like
        #       C:/some/path;C:/some/other/path;C:/third/path
        # - To make this simpler, we can define the environment variable OS_PATHSEP
        #   (by analogy to Python's os.pathsep), as below.
        #
        # You can use substitutable parameters:
        #
        #   {X}
        #       Substitutes variable X from the environment you specify (see
        #       below).
        #   {NLPLOGTAG}
        #       Additional environment variable that indicates the process being
        #       run; used to label the output from CrateGatePipeline.

    progargs = java
        -classpath "{NLPPROGDIR}"{OS_PATHSEP}"{GATEDIR}/bin/gate.jar"{OS_PATHSEP}"{GATEDIR}/lib/*"
        -Dgate.home="{GATEDIR}"
        CrateGatePipeline
        --gate_app "{GATEDIR}/plugins/ANNIE/ANNIE_with_defaults.gapp"
        --annotation Person
        --annotation Location
        --input_terminator END_OF_TEXT_FOR_NLP
        --output_terminator END_OF_NLP_OUTPUT_RECORD
        --log_tag {NLPLOGTAG}
        --verbose

    progenvsection = MY_ENV_SECTION

        # The external program is slow, because NLP is slow. Therefore, we set up
        # the external program and use it repeatedly for a whole bunch of text.
        # Individual pieces of text are sent to it (via its stdin). We finish our
        # piece of text with a delimiter, which should (a) be specified in the -it
        # parameter above, and (b) be set below, TO THE SAME VALUE. The external
        # program should return a TSV-delimited set of field/value pairs, like
        # this:
        #
        #       field1\tvalue1\tfield2\tvalue2...
        #       field1\tvalue3\tfield2\tvalue4...
        #       ...
        #       TERMINATOR
        #
        # ... where TERMINATOR is something that you (a) specify with the -ot
        # parameter above, and (b) set below, TO THE SAME VALUE.

    input_terminator = END_OF_TEXT_FOR_NLP
    output_terminator = END_OF_NLP_OUTPUT_RECORD

        # If the external program leaks memory, you may wish to cap the number of
        # uses before it's restarted. Specify the max_external_prog_uses option if
        # so. Specify 0 or omit the option entirely to ignore this.

    # max_external_prog_uses = 1000

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Define the output tables used by this GATE processor
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # (This is an additional thing we need for GATE applications, since CRATE
        # doesn't automatically know what sort of output they will produce.)

    [output:output_person]

        # The tables and SPECIFIC output fields for a given GATE processor are
        # defined here.

    desttable = person

    renames =  # one pair per line; can quote, using shlex rules; case-sensitive
        firstName   firstname

    destfields =
        rule        VARCHAR(100)
        firstname   VARCHAR(100)
        surname     VARCHAR(100)
        gender      VARCHAR(7)
        kind        VARCHAR(100)

        # ... longest gender: "unknown" (7)

    indexdefs =
        firstname   64
        surname     64

        # ... a set of (indexed field, index length) pairs; length can be "None"

    [output:output_location]

    desttable = location
    renames =
        locType     loctype
    destfields =
        rule        VARCHAR(100)
        loctype     VARCHAR(100)
    indexdefs =
        rule    100
        loctype 100


    # -----------------------------------------------------------------------------
    # Specimen Sheffield/KCL KConnect (Bio-YODIE) processor definition
    # -----------------------------------------------------------------------------
    # https://gate.ac.uk/applications/bio-yodie.html

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Define the processor
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    [processor:procdef_gate_kconnect]

    destdb = DESTINATION_DATABASE
    outputtypemap =
        Disease_or_Syndrome output_disease_or_syndrome
    progargs = java
        -classpath "{NLPPROGDIR}"{OS_PATHSEP}"{GATEDIR}/bin/gate.jar"{OS_PATHSEP}"{GATEDIR}/lib/*"
        -Dgate.home="{GATEDIR}"
        CrateGatePipeline
        --gate_app "{KCONNECTDIR}/main-bio/main-bio.xgapp"
        --annotation Disease_or_Syndrome
        --input_terminator END_OF_TEXT_FOR_NLP
        --output_terminator END_OF_NLP_OUTPUT_RECORD
        --log_tag {NLPLOGTAG}
        --suppress_gate_stdout
        --verbose
    progenvsection = MY_ENV_SECTION
    input_terminator = END_OF_TEXT_FOR_NLP
    output_terminator = END_OF_NLP_OUTPUT_RECORD
    # max_external_prog_uses = 1000

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Define the output tables used by this GATE processor
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    [output:output_disease_or_syndrome]

    desttable = kconnect_diseases
    renames =
        Experiencer     experiencer
        Negation        negation
        PREF            pref
        STY             sty
        TUI             tui
        Temporality     temporality
        VOCABS          vocabs
    destfields =
        # Found by manual inspection of KConnect/Bio-YODIE output from the GATE console:
        experiencer  VARCHAR(100)  # e.g. "Patient"
        negation     VARCHAR(100)  # e.g. "Affirmed"
        pref         VARCHAR(100)  # e.g. "Rheumatic gout"; PREFferred name
        sty          VARCHAR(100)  # e.g. "Disease or Syndrome"; Semantic Type (STY) [semantic type name]
        tui          VARCHAR(4)    # e.g. "T047"; Type Unique Identifier (TUI) [semantic type identifier]; 4 characters; https://www.ncbi.nlm.nih.gov/books/NBK9679/
        temporality  VARCHAR(100)  # e.g. "Recent"
        vocabs       VARCHAR(255)  # e.g. "AIR,MSH,NDFRT,MEDLINEPLUS,NCI,LNC,NCI_FDA,NCI,MTH,AIR,ICD9CM,LNC,SNOMEDCT_US,LCH_NW,HPO,SNOMEDCT_US,ICD9CM,SNOMEDCT_US,COSTAR,CST,DXP,QMR,OMIM,OMIM,AOD,CSP,NCI_NCI-GLOSS,CHV"; list of UMLS vocabularies
        inst         VARCHAR(8)    # e.g. "C0003873"; looks like a Concept Unique Identifier (CUI); 1 letter then 7 digits
        inst_full    VARCHAR(255)  # e.g. "http://linkedlifedata.com/resource/umls/id/C0003873"
        language     VARCHAR(100)  # e.g. ""; ?will look like "ENG" for English? See https://www.nlm.nih.gov/research/umls/implementation_resources/query_diagrams/er1.html
        tui_full     VARCHAR(255)  # e.g. "http://linkedlifedata.com/resource/semanticnetwork/id/T047"
    indexdefs =
        pref    100
        sty     100
        tui     4
        inst    8

    # -----------------------------------------------------------------------------
    # Specimen KCL GATE pharmacotherapy processor definition
    # -----------------------------------------------------------------------------
    # https://github.com/KHP-Informatics/brc-gate-pharmacotherapy

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Define the processor
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    [processor:procdef_gate_pharmacotherapy]

    destdb = DESTINATION_DATABASE
    outputtypemap =
        Prescription output_prescription
    progargs = java
        -classpath "{NLPPROGDIR}"{OS_PATHSEP}"{GATEDIR}/bin/gate.jar"{OS_PATHSEP}"{GATEDIR}/lib/*"
        -Dgate.home="{GATEDIR}"
        CrateGatePipeline
        --gate_app "{GATE_PHARMACOTHERAPY_DIR}/application.xgapp"
        --include_set Output
        --annotation Prescription
        --input_terminator END_OF_TEXT_FOR_NLP
        --output_terminator END_OF_NLP_OUTPUT_RECORD
        --log_tag {NLPLOGTAG}
        --suppress_gate_stdout
        --show_contents_on_crash

    #    -v
    progenvsection = CPFT_ENV_SECTION
    input_terminator = END_OF_TEXT_FOR_NLP
    output_terminator = END_OF_NLP_OUTPUT_RECORD
    # max_external_prog_uses = 1000

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Define the output tables used by this GATE processor
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    # Note new "renames" option, because the names of the annotations are not
    # always valid SQL column names.

    [output:output_prescription]

    desttable = medications_gate
    renames =  # one pair per line; can quote, using shlex rules; case-sensitive
        drug-type           drug_type
        dose-value          dose_value
        dose-unit           dose_unit
        dose-multiple       dose_multiple
        Directionality      directionality
        Experiencer         experiencer
        "Length of Time"    length_of_time
        Temporality         temporality
        "Unit of Time"      unit_of_time
    null_literals =
        # Sometimes GATE provides "null" for a NULL value; we can convert to SQL NULL.
        # Sequence of words; shlex rules.
        null
        ""
    destfields =
        # Found by (a) manual inspection of BRC GATE pharmacotherapy output from
        # the GATE console; (b) inspection of
        # application-resources/schemas/Prescription.xml
        # Note preference for DECIMAL over FLOAT/REAL; see
        # https://stackoverflow.com/questions/1056323
        # Note that not all annotations appear for all texts. Try e.g.:
        #   Please start haloperidol 5mg tds.
        #   I suggest you start haloperidol 5mg tds for one week.
        rule            VARCHAR(100)  # not in XML but is present in a subset: e.g. "weanOff"; max length unclear
        drug            VARCHAR(200)  # required string; e.g. "haloperidol"; max length 47 from "wc -L BNF_generic.lst", 134 from BNF_trade.lst
        drug_type       VARCHAR(100)  # required string; from "drug-type"; e.g. "BNF_generic"; ?length of longest drug ".lst" filename
        dose            VARCHAR(100)  # required string; e.g. "5mg"; max length unclear
        dose_value      DECIMAL       # required numeric; from "dose-value"; "double" in the XML but DECIMAL probably better; e.g. 5.0
        dose_unit       VARCHAR(100)  # required string; from "dose-unit"; e.g. "mg"; max length unclear
        dose_multiple   INT           # required integer; from "dose-multiple"; e.g. 1
        route           VARCHAR(7)    # required string; one of: "oral", "im", "iv", "rectal", "sc", "dermal", "unknown"
        status          VARCHAR(10)   # required; one of: "start", "continuing", "stop"
        tense           VARCHAR(7)    # required; one of: "past", "present"
        date            VARCHAR(100)  # optional string; max length unclear
        directionality  VARCHAR(100)  # optional string; max length unclear
        experiencer     VARCHAR(100)  # optional string; e.g. "Patient"
        frequency       DECIMAL       # optional numeric; "double" in the XML but DECIMAL probably better
        interval        DECIMAL       # optional numeric; "double" in the XML but DECIMAL probably better
        length_of_time  VARCHAR(100)  # optional string; from "Length of Time"; max length unclear
        temporality     VARCHAR(100)  # optional string; e.g. "Recent"
        time_unit       VARCHAR(100)  # optional string; from "time-unit"; e.g. "day"; max length unclear
        unit_of_time    VARCHAR(100)  # optional string; from "Unit of Time"; max length unclear
        when            VARCHAR(100)  # optional string; max length unclear
    indexdefs =
        rule    100
        drug    200
        route   7
        status  10
        tense   7

    # -----------------------------------------------------------------------------
    # Specimen KCL Lewy Body Diagnosis Application (LBDA) processor definition
    # -----------------------------------------------------------------------------
    # https://github.com/KHP-Informatics/brc-gate-LBD

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Define the processor
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    [processor:procdef_gate_kcl_lbda]

        # "cDiagnosis" is the "confirmed diagnosis" field, as d/w Jyoti Jyoti
        # 2018-03-20; see also README.md. This appears in the "Automatic" and the
        # unnamed set. There is also a near-miss one, "DiagnosisAlmost", which
        # appears in the unnamed set.
        #   "Mr Jones has Lewy body dementia."
        #       -> DiagnosisAlmost
        #   "Mr Jones has a diagnosis of Lewy body dementia."
        #       -> DiagnosisAlmost, cDiagnosis
        # Note that we must use lower case in the outputtypemap.

    destdb = DESTINATION_DATABASE
    outputtypemap =
        cDiagnosis output_lbd_diagnosis
        DiagnosisAlmost output_lbd_diagnosis
    progargs = java
        -classpath "{NLPPROGDIR}"{OS_PATHSEP}"{GATEDIR}/bin/gate.jar"{OS_PATHSEP}"{GATEDIR}/lib/*"
        -Dgate.home="{GATEDIR}"
        CrateGatePipeline
        --gate_app "{KCL_LBDA_DIR}/application.xgapp"
        --set_annotation "" DiagnosisAlmost
        --set_annotation Automatic cDiagnosis
        --input_terminator END_OF_TEXT_FOR_NLP
        --output_terminator END_OF_NLP_OUTPUT_RECORD
        --log_tag {NLPLOGTAG}
        --suppress_gate_stdout
        --verbose
    progenvsection = MY_ENV_SECTION
    input_terminator = END_OF_TEXT_FOR_NLP
    output_terminator = END_OF_NLP_OUTPUT_RECORD
    # max_external_prog_uses = 1000

        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        # Define the output tables used by this GATE processor
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    [output:output_lbd_diagnosis]

    desttable = lewy_body_dementia_gate
    null_literals =
        null
        ""
    destfields =
        # Found by
        # (a) manual inspection of output from the GATE Developer console:
        # - e.g. {rule=Includefin, text=Lewy body dementia}
        # (b) inspection of contents:
        # - run a Cygwin shell
        # - find . -type f -exec grep cDiagnosis -l {} \;
        # - 3 hits:
        #       ./application-resources/jape/DiagnosisExclude2.jape
        #           ... part of the "Lewy"-detection apparatus
        #       ./application-resources/jape/text-feature.jape
        #           ... adds "text" annotation to cDiagnosis Token
        #       ./application.xgapp
        #           ... in annotationTypes
        # On that basis:
        rule            VARCHAR(100)  #
        text            VARCHAR(200)  #
    indexdefs =
        rule    100
        text    200

    # -----------------------------------------------------------------------------
    # Specimen MedEx processor definition
    # -----------------------------------------------------------------------------
    # https://sbmi.uth.edu/ccb/resources/medex.htm

    [processor:procdef_medex_drugs]

    destdb = DESTINATION_DATABASE
    desttable = drugs
    progargs = java
        -classpath {NLPPROGDIR}:{MEDEXDIR}/bin:{MEDEXDIR}/lib/*
        -Dfile.encoding=UTF-8
        CrateMedexPipeline
        -lt {NLPLOGTAG}
        -v -v
    # ... other arguments are added by the code
    progenvsection = MY_ENV_SECTION


    # =============================================================================
    # C. Environment variable definitions
    #
    #    We define environment variable groups here, with one group per section.
    #    When a section is selected (e.g. by a "progenvsection" command in an NLP
    #    processor definition), these variables can be substituted into the
    #    "progargs" part of the NLP definition (for when external programs are
    #    called) and are available in the operating system environment for those
    #    programs themselves.
    # =============================================================================
    # - The environment will start by inheriting the parent environment, then add
    #   variables here.
    # - Keys are case-sensitive.
    # - You'll need to modify this according to your local configuration.

    [env:MY_ENV_SECTION]

    GATEDIR = /home/myuser/somewhere/GATE_Developer_8.0
    NLPPROGDIR = /home/myuser/somewhere/crate_anon/nlp_manager/compiled_nlp_classes
    MEDEXDIR = /home/myuser/somewhere/Medex_UIMA_1.3.6
    KCONNECTDIR = /home/myuser/somewhere/yodie-pipeline-1-2-umls-only
    OS_PATHSEP = :


    # =============================================================================
    # D. Input field definitions
    #
    #    These define database "inputs" in more detail, including the database,
    #    table, and field (column) containing the input, the associated primary key
    #    field, and fields that should be copied to the destination to make
    #    subsequent work easier (e.g. patient research IDs).
    # =============================================================================
    # - Referred to within the NLP definition, and cross-referencing database
    #   definitions.
    # - The 'srcdatetimefield' is optional (but advisable).
    # - The 'copyfields' are optional.
    # - The 'indexed_copyfields' are an optional subset of 'copyfields'; they'll be
    #   indexed.

    [input:INPUT_FIELD_CLINICAL_DOCUMENTS]

    srcdb = SOURCE_DATABASE
    srctable = EXTRACTED_CLINICAL_DOCUMENTS
    srcpkfield = DOCUMENT_PK
    srcfield = DOCUMENT_TEXT
    srcdatetimefield = DOCUMENT_DATE
    copyfields = RID_FIELD
        TRID_FIELD
    indexed_copyfields = RID_FIELD
        TRID_FIELD

        # Optional: specify 0 (the default) for no limit, or a number of rows (e.g.
        # 1000) to limit fetching, for debugging purposes.
    # debug_row_limit = 0

    [input:INPUT_FIELD_PROGRESS_NOTES]

    srcdb = SOURCE_DATABASE
    srctable = PROGRESS_NOTES
    srcpkfield = PN_PK
    srcfield = PN_TEXT
    srcdatetimefield = PN_DATE
    copyfields = RID_FIELD
        TRID_FIELD
    indexed_copyfields = RID_FIELD
        TRID_FIELD


    # =============================================================================
    # E. Database definitions, each in its own section
    #
    #    These are simply URLs that define how to connect to different databases.
    # =============================================================================
    # Use SQLAlchemy URLs: http://docs.sqlalchemy.org/en/latest/core/engines.html

    [database:SOURCE_DATABASE]

    url = mysql+mysqldb://anontest:XXX@127.0.0.1:3306/anonymous_output?charset=utf8

    [database:DESTINATION_DATABASE]

    url = mysql+mysqldb://anontest:XXX@127.0.0.1:3306/anonymous_output?charset=utf8



.. rubric:: Footnotes

.. [#nlpdefinitionclass]
    Internally, the config file section is represented by the `NlpDefinition`
    class, which acts as the master config class.

.. [#inputfieldconfig]
    Internally, this information is represented by the `InputFieldConfig`
    class.

.. [#nlpparser]
    Internally, this information is represented by classes such as
    `GateExtProgController` and `NumericalResultParser`, which are subclasses
    of `NlpParser`.

.. [#hashcollisions]
    https://en.wikipedia.org/wiki/Hash_function
