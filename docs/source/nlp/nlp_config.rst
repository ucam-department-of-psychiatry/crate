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


.. _nlp_config_truncate_text_at:

truncate_text_at
################

*Integer.* Default: 0. Must be zero or positive.

Use this to truncate very long incoming text fields. If non-zero, this is the
length at which to truncate.


record_truncated_values
#######################

*Boolean.* Default: false.

Record in the progress database that we have processed records for which the
source text was truncated (see :ref:`truncate_text_at
<nlp_config_truncate_text_at>`).

.. todo:: RNC to ask FS for explanation of ``record_truncated_values``, i.e. when should it be used?


.. _cloud_config:

cloud_config
############

*String.* Required to use cloud NLP.

The name of the cloud NLP configuration to use if you ask for cloud-based
processing with this NLP definition.

For example, you might specify:

.. code-block:: ini

    cloud_config = my_uk_cloud_nlp_service

and CRATE would then look for a :ref:`cloud NLP configuration
<nlp_config_section_cloud_nlp>` in a config file section named
``[cloud:my_uk_cloud_nlp_service]``, and use the information there to connect
to a cloud NLP service via the :ref:`NLPRP <nlprp>`.


cloud_request_data_dir
######################

*String.* Required to use cloud NLP.

Directory (on your local filesystem) to hold files containing information for
the retrieval of data which has been sent in queued mode.

For safety (in case the user specifies a foolish directory!), CRATE will make a subdirectory of this directory (whose name is
that of the NLP definition). CRATE will delete files at will within that
subdirectory.


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


destdb
######

*String.*

**Applicable to: all parsers.**

Destination database; the name of a :ref:`database definition
<nlp_config_section_database>` in the config file.


desttable
#########

*String.*

**Applicable to: Cloud, MedEx, all CRATE Python processors.**

The name of the table in the destination database in which the results should
be stored.


assume_preferred_unit
#####################

*Boolean.* Default: True.

**Applicable to: all numerical CRATE Python processors.**

If a unit is not specified, assume that values are in the processor's preferred
units. (For example, :class:`crate_anon.nlp_manager.parse_biochemistry.Crp`
will assume mg/L.)


.. _nlp_config_processor_desttable:

desttable
#########

*String.*

**Applicable to: Cloud.**

Table name in the destination (NLP output) database into which to write results
from the cloud NLP processor. Use this for single-table processors.

The alternative is :ref:`outputtypemap <nlp_config_processor_outputtypemap>`.




.. _nlp_config_processor_outputtypemap:

outputtypemap
#############

*Multiline string.*

**Applicable to: GATE, Cloud.**

For GATE:

    What's GATE? See the section on :ref:`GATE NLP <gate_nlp>`.

    Map GATE '_type' parameters to possible destination tables (in
    case-insensitive fashion). This parameter is follows is a list of pairs,
    one pair per line.

    - The first item of each is the annotation type coming out of the GATE
      system.

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

For cloud:

    - The alternative is :ref:`desttable <nlp_config_processor_desttable>`.

    - If both are present, only :ref:`outputtypemap
      <nlp_config_processor_outputtypemap>` will be used.


.. _nlp_config_section_gate_progargs:

progargs
########

*Multiline string.*

**Applicable to: GATE, MedEx.**

This parameter defines how we will launch GATE. See :ref:`GATE NLP <gate_nlp>`.

GATE NLP is done by an external program.

In this parameter, we specify a program and associated arguments. Here's an
example:

.. code-block:: none

    progargs =
        java
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
##############

*String.*

**Applicable to: GATE, MedEx.**

:ref:`Environment variable config section <nlp_config_section_envvar>` to use
when launching this program.


.. _nlp_config_section_gate_inputterminator:

input_terminator
################

*String.*

**Applicable to: GATE.**

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
#################

*String.*

**Applicable to: GATE.**

See :ref:`input_terminator <nlp_config_section_gate_inputterminator>`.


max_external_prog_uses
######################

*Integer.*

**Applicable to: GATE, MedEx.**

If the external GATE program leaks memory, you may wish to cap the number of
uses before it's restarted. Specify this option if so. Specify 0 or omit the
option entirely to ignore this.


processor_name
##############

*String.*

**Applicable to: Cloud.**

Name of the remote processor; see :ref:`NLPRP list_processors
<nlprp_list_processors>`.


processor_version
#################

*String.* Default: None.

**Applicable to: Cloud.**

Version of the remote processor; see :ref:`NLPRP list_processors
<nlprp_list_processors>`.


processor_format
################

*String.*

**Applicable to: Cloud.**

One of:  ``Standard``, ``GATE``.

.. todo:: explain processor_format (cloud NLP) setting


.. _nlp_config_section_gate_output:

Config file section: GATE output definition
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These are config file sections named ``[output:XXX]`` where ``XXX`` is the
name of one of your GATE output types [#outputuserconfig]_.

This is an additional thing we need for GATE applications, since CRATE doesn't
automatically know what sort of output they will produce. The tables and
SPECIFIC output fields for a given GATE processor are defined here.

They are referred to by the :ref:`outputtypemap
<nlp_config_processor_outputtypemap>` parameter (q.v.).


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


.. _nlp_config_destfields:

destfields
##########

*Multiline string.*

Defines the database field (column) types used in the output database. This is
how you tell the database how much space to allocate for information that will
come out of GATE. Each line is a ``column_name, sql_type`` pair (or,
optionally, a ``column_name, sql_type, comment`` triple. Whitespace is used to
separate the columns. Examples:

.. code-block:: none

    destfields =
        rule        VARCHAR(100)
        firstname   VARCHAR(100)
        surname     VARCHAR(100)
        gender      VARCHAR(7)
        kind        VARCHAR(100)

.. code-block:: none

    destfields =
        rule        VARCHAR(100)    Rule used to find this person (e.g. TitleFirstName, PersonFull)
        firstname   VARCHAR(100)    First name
        surname     VARCHAR(100)    Surname
        gender      VARCHAR(7)      Gender (e.g. male, female, unknown)
        kind        VARCHAR(100)    Kind of name (e.g. personName, fullName)


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

These simply tell CRATE how to connect to different databases.


url
###

*String.*

The URL of the database.  Use SQLAlchemy URLs:
http://docs.sqlalchemy.org/en/latest/core/engines.html.

Example:

.. code-block:: ini

    [database:MY_SOURCE_DATABASE]

    url = mysql+mysqldb://myuser:password@127.0.0.1:3306/anonymous_output_db?charset=utf8


echo
####

*Boolean.* Default: False.

Optional parameter for debugging. If set to True, all SQL being sent to the
database will be logged to the Python console log.


.. _nlp_config_section_cloud_nlp:

Config file section: cloud NLP configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These are config file sections named ``[cloud:XXX]`` where ``XXX`` is the name
of one of your cloud NLP configurations (referred to by the cloud_config_
parameter in a NLP definition) [#cloudconfigclass]_.


.. _nlp_config_cloud_url:

cloud_url
#########

*String.* Required to use cloud NLP.

The URL of the cloud NLP service.


.. _nlp_config_verify_ssl:

verify_ssl
##########

*Boolean.* Default: true.

Should CRATE verify the SSL certificate of the remote NLP server?


compress
########

*Boolean.* Default: true.

Should CRATE compress messages going to the NLP server, using ``gzip``?

CRATE (via the Python ``requests`` library) also always tells the server that
it will accept ``gzip`` compression back; the server should respond to this by
compressing results.


username
########

*String.* Default: "".

Your username for accessing the services at the URL specified in
:ref:`cloud_url <nlp_config_cloud_url>`.


password
########

*String.* Default: "".

Your password for accessing the services at the URL specified in
:ref:`cloud_url <nlp_config_cloud_url>`.


wait_on_conn_err
################

*Integer.* Default: 180.

After a connection error occurs, wait this many seconds before retrying.


.. _nlp_config_max_content_length:

max_content_length
##################

*Integer.* Default: 0.

The maximum size of the packets to be sent. This should be less than or equal
to the limit the service allows. Put 0 for no maximum length.

NOTE: if a single record is larger than the maximum packet size, that record
will not be sent.


.. _nlp_config_max_records_per_request:

max_records_per_request
#######################

*Integer.* Default: 1000.

When sending data: the maximum number of pieces of text that will be sent as
part of a single NLPRP request (subject also to :ref:`max_content_length
<nlp_config_max_content_length>`).


.. _nlp_config_limit_before_commit:

limit_before_commit
###################

*Integer.* Default: 1000.

When receiving results: the number of results that will be processed (and
written to the database) before a ``COMMIT`` command is executed.


stop_at_failure
###############

*Boolean.* Default: true.

Are cloud NLP requests for processing allowed to fail, and CRATE continue? If
not, an error is raised and CRATE will abort on failure. (Some requests are not
allowed to fail, regardless of this setting.)


.. _nlp_config_max_tries:

max_tries
#########

*Integer.* Default: 5.

Maximum number of times to try each HTTP connection to the cloud NLP server,
before giving it up as a bad job.


.. _nlp_config_rate_limit_hz:

rate_limit_hz
#############

*Integer.* Default: 2.

The maximum rate, in Hz (times per second), that the CRATE NLP processor will
send requests. Use this to avoid overloading the cloud NLP server. Specify 0
for no limit.


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

A specimen NLP config is available by running ``crate_nlp --democonfig``.

Here's the specimen NLP config:

..  literalinclude:: specimen_nlp_config_file.ini
    :language: ini


===============================================================================

.. rubric:: Footnotes

.. [#nlpdefinitionclass]
    Internally, the config file section is represented by the
    :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition` class, which
    acts as the master config class.

.. [#inputfieldconfig]
    Internally, this information is represented by the
    :class:`crate_anon.nlp_manager.input_field_config.InputFieldConfig` class.

.. [#nlpparser]
    Internally, this information is represented by classes such as
    :class:`crate_anon.nlp_manager.parse_gate.Gate` and
    :class:`crate_anon.nlp_manager.parse_biochemistry.Crp`, which are
    subclasses of :class:`crate_anon.nlp_manager.base_nlp_parser.BaseNlpParser`.

.. [#cloudconfigclass]
   Internally, this information is represented by the
   :class:`crate_anon.nlp_manager.cloud_config.CloudConfig` class.

.. [#hashcollisions]
    https://en.wikipedia.org/wiki/Hash_function

.. [#outputuserconfig]
   Internally, this information is represented by the
   :class:`crate_anon.nlp_manager.output_user_config.OutputUserConfig` class.