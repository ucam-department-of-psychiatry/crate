#!/usr/bin/env python
# crate_anon/nlp_manager/constants.py

from sqlalchemy.types import String
from crate_anon.anonymise.constants import (
    DEFAULT_MAX_BYTES_BEFORE_COMMIT,
    DEFAULT_MAX_ROWS_BEFORE_COMMIT,
)
from crate_anon.common.hash import HmacMD5Hasher
from crate_anon.version import VERSION, VERSION_DATE

DEFAULT_REPORT_EVERY_NLP = 500  # low values slow down processing

DEFAULT_TEMPORARY_TABLENAME = '_crate_nlp_temptable'

FN_NLPDEF = '_nlpdef'
FN_PK = '_pk'
FN_SRCDB = '_srcdb'
FN_SRCTABLE = '_srctable'
FN_SRCPKFIELD = '_srcpkfield'
FN_SRCPKVAL = '_srcpkval'
FN_SRCPKSTR = '_srcpkstr'
FN_SRCFIELD = '_srcfield'

GATE_PIPELINE_CLASSNAME = 'CrateGatePipeline'
MEDEX_PIPELINE_CLASSNAME = 'CrateMedexPipeline'

MEDEX_DATA_READY_SIGNAL = "data_ready"
MEDEX_RESULTS_READY_SIGNAL = "results_ready"

NLP_CONFIG_ENV_VAR = 'CRATE_NLP_CONFIG'

MAX_STRING_PK_LENGTH = 64  # trade-off; space versus capability

MAX_SQL_FIELD_LEN = 64
# ... http://dev.mysql.com/doc/refman/5.0/en/identifiers.html
SqlTypeDbIdentifier = String(MAX_SQL_FIELD_LEN)  # text field used for database
# names, table names, and field names

HashClass = HmacMD5Hasher


# =============================================================================
# Demo config
# =============================================================================

DEMO_CONFIG = ("""# Configuration file for CRATE NLP manager (crate_nlp).
# Version {VERSION} ({VERSION_DATE}).
#
# PLEASE SEE THE MANUAL FOR AN OVERVIEW.
#
# =============================================================================
# Default fields
# =============================================================================
# - NOTE THAT THE FOLLOWING FIELDNAMES ARE USED AS STANDARD, AND WILL BE
#   AUTOCREATED:
#
#   From nlp_manager.py, for *all* NLP processors:
#
#       _pk INT
#           -- PK within this table.
#       _srcdb {IdentType}
#           -- Source database name
#       _srctable {IdentType}
#           -- Source table name
#       _srcpkfield {IdentType}
#           -- Source primary key (PK) field name
#       _srcpkval INT
#           -- Source PK value
#       _srcfield {IdentType}
#           -- Source field containing text content
#
#   The length of the VARCHAR fields is set by the MAX_SQL_FIELD_LEN constant.
#
# - Pipelines using GATE add these:
#
#       _type {IdentType}
#           -- Annotation type name (e.g. 'Person')
#       _id INT
#           -- Annotation ID, from GATE. Not clear that this is very useful.
#       _start INT
#           -- Start position in the content
#       _end INT
#           -- End position in the content
#       _content TEXT
#           -- Full content marked as relevant. (Not the entire content of the
#              source field.)
#
# - CRATE's numerical regular-expression pipelines add these:
#
#       variable_name  {IdentType}
#           -- variable name as determined by the NLP processor
#       _content TEXT
#           -- matching text contents
#       _start INT
#           -- start position within the full text
#       _end INT
#           -- end position within the full text
#       variable_text TEXT
#           -- text that actually matched the target variable name
#       relation VARCHAR(3)
#           -- mathematical relation of variable to value, e.g. '<=', '='
#       value_text TEXT
#           -- numerical value as text
#       units TEXT
#           -- text that matched some definition of a possible unit
#
#   ... plus a NLP-specific field with the actual value.


# =============================================================================
# Individual NLP definitions
# - referred to by the nlp_manager.py's command-line arguments
# =============================================================================

[NLPDEF_NAME_LOCATION_NLP]

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
    # -------------------------------------------------------------------------
    # GATE
    # -------------------------------------------------------------------------
    GATE procdef_gate_name_location

    # To allow incremental updates, information is stored in a progress table.
    # The database name is a cross-reference to another section in this config
    # file. The table name is hard-coded to 'crate_nlp_progress'.

progressdb = DESTINATION_DATABASE
hashphrase = doesnotmatter

    # Temporary tablename to use (in progress and destination databases).
    # Default is {DEFAULT_TEMPORARY_TABLENAME}
# temporary_tablename = {DEFAULT_TEMPORARY_TABLENAME}


[NLPDEF_BIOMARKERS]

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
    # Default is {DEFAULT_MAX_ROWS_BEFORE_COMMIT}.
max_rows_before_commit = {DEFAULT_MAX_ROWS_BEFORE_COMMIT}

    # Specify the maximum number of source-record bytes (approximately!) that
    # are processed before a COMMIT is issued on the database transaction(s).
    # This prevents the transaction(s) growing too large. The COMMIT will be
    # issued *after* this limit has been met/exceeded, so it may be exceeded if
    # the transaction just before the limit takes the cumulative total over the
    # limit.
    # Default is {DEFAULT_MAX_BYTES_BEFORE_COMMIT}.
max_bytes_before_commit = {DEFAULT_MAX_BYTES_BEFORE_COMMIT}


# =============================================================================
# NLP processor definitions
# =============================================================================

# -----------------------------------------------------------------------------
# Specimen CRATE regular expression processor definitions
# -----------------------------------------------------------------------------

    # Most of these are very simple, and just require a destination database
    # (as a cross-reference to a database section within this file) and a
    # destination table.

    # Biochemistry

[procdef_crp]
destdb = DESTINATION_DATABASE
desttable = crp
[procdef_validate_crp]
destdb = DESTINATION_DATABASE
desttable = validate_crp

[procdef_sodium]
destdb = DESTINATION_DATABASE
desttable = sodium
[procdef_validate_sodium]
destdb = DESTINATION_DATABASE
desttable = validate_sodium

[procdef_tsh]
destdb = DESTINATION_DATABASE
desttable = tsh
[procdef_validate_tsh]
destdb = DESTINATION_DATABASE
desttable = validate_tsh

    # Clinical

[procdef_height]
destdb = DESTINATION_DATABASE
desttable = height
[procdef_validate_height]
destdb = DESTINATION_DATABASE
desttable = validate_height

[procdef_weight]
destdb = DESTINATION_DATABASE
desttable = weight
[procdef_validate_weight]
destdb = DESTINATION_DATABASE
desttable = validate_weight

[procdef_bmi]
destdb = DESTINATION_DATABASE
desttable = bmi
[procdef_validate_bmi]
destdb = DESTINATION_DATABASE
desttable = validate_bmi

[procdef_bp]
destdb = DESTINATION_DATABASE
desttable = bp
[procdef_validate_bp]
destdb = DESTINATION_DATABASE
desttable = validate_bp

    # Cognitive

[procdef_mmse]
destdb = DESTINATION_DATABASE
desttable = mmse
[procdef_validate_mmse]
destdb = DESTINATION_DATABASE
desttable = validate_mmse

[procdef_ace]
destdb = DESTINATION_DATABASE
desttable = ace
[procdef_validate_ace]
destdb = DESTINATION_DATABASE
desttable = validate_ace

[procdef_mini_ace]
destdb = DESTINATION_DATABASE
desttable = mini_ace
[procdef_validate_mini_ace]
destdb = DESTINATION_DATABASE
desttable = validate_mini_ace

[procdef_moca]
destdb = DESTINATION_DATABASE
desttable = moca
[procdef_validate_moca]
destdb = DESTINATION_DATABASE
desttable = validate_moca

    # Haematology

[procdef_esr]
destdb = DESTINATION_DATABASE
desttable = esr
[procdef_validate_esr]
destdb = DESTINATION_DATABASE
desttable = validate_esr

[procdef_wbc]
destdb = DESTINATION_DATABASE
desttable = wbc
[procdef_validate_wbc]
destdb = DESTINATION_DATABASE
desttable = validate_wbc

[procdef_basophils]
destdb = DESTINATION_DATABASE
desttable = basophils
[procdef_validate_basophils]
destdb = DESTINATION_DATABASE
desttable = validate_basophils

[procdef_eosinophils]
destdb = DESTINATION_DATABASE
desttable = eosinophils
[procdef_validate_eosinophils]
destdb = DESTINATION_DATABASE
desttable = validate_eosinophils

[procdef_lymphocytes]
destdb = DESTINATION_DATABASE
desttable = lymphocytes
[procdef_validate_lymphocytes]
destdb = DESTINATION_DATABASE
desttable = validate_lymphocytes

[procdef_monocytes]
destdb = DESTINATION_DATABASE
desttable = monocytes
[procdef_validate_monocytes]
destdb = DESTINATION_DATABASE
desttable = validate_monocytes

[procdef_neutrophils]
destdb = DESTINATION_DATABASE
desttable = neutrophils
[procdef_validate_neutrophils]
destdb = DESTINATION_DATABASE
desttable = validate_neutrophils

# -----------------------------------------------------------------------------
# Specimen GATE processor definition
# -----------------------------------------------------------------------------

[procdef_gate_name_location]

    # Which database will this processor write to?

destdb = DESTINATION_DATABASE

    # Map GATE '_type' parameters to possible destination tables (in
    # case-insensitive fashion). What follows is a list of pairs: the first
    # item is the annotation type coming out of the GATE system, and the second
    # is the output type section defined in this file (as a separate section).
    # Those sections (q.v.) define tables and columns (fields).

outputtypemap =
    person output_person
    location output_location

    # GATE NLP is done by an external program.
    # SEE THE MANUAL FOR DETAIL.
    #
    # Here we specify a program and associated arguments, and an optional
    # environment variable section.
    # The example shows how to use Java to launch a specific Java program
    # ({CLASSNAME}), having set a path to find other Java classes, and then to
    # pass arguments to the program itself.
    #
    # NOTE IN PARTICULAR:
    # - Use double quotes to encapsulate any filename that may have spaces
    #   within it (e.g. C:/Program Files/...).
    #   Use a forward slash director separator, even under Windows.
    # - Under Windows, use a semicolon to separate parts of the Java classpath.
    #   Under Linux, use a colon.
    #
    # You can use substitutable parameters:
    #
    #   {{X}}
    #       Substitutes variable X from the environment you specify (see
    #       below).
    #   {{NLPLOGTAG}}
    #       Additional environment variable that indicates the process being
    #       run; used to label the output from {CLASSNAME}.

progargs = java
    -classpath "{{NLPPROGDIR}}":"{{GATEDIR}}/bin/gate.jar":"{{GATEDIR}}/lib/*"
    {CLASSNAME}
    -g "{{GATEDIR}}/plugins/ANNIE/ANNIE_with_defaults.gapp"
    -a Person
    -a Location
    -it END_OF_TEXT_FOR_NLP
    -ot END_OF_NLP_OUTPUT_RECORD
    -lt {{NLPLOGTAG}}
    -v -v

progenvsection = MY_ENV_SECTION

    # The external program is slow, because NLP is slow. Therefore, we set up
    # the external program and use it repeatedly for a whole bunch of text.
    # Individual pieces of text are sent to it (via its stdin). We finish our
    # piece of text with a delimiter, which should (a) be specified in the -it
    # parameter above, and (b) be set below, TO THE SAME VALUE. The external
    # program should return a TSV-delimited set of field/value pairs, like
    # this:
    #
    #       field1\\tvalue1\\tfield2\\tvalue2...
    #       field1\\tvalue3\\tfield2\\tvalue4...
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

# -----------------------------------------------------------------------------
# Specimen MedEx processor definition
# -----------------------------------------------------------------------------

[procdef_medex_drugs]
destdb = DESTINATION_DATABASE
desttable = drugs
progargs = java
    -classpath {{NLPPROGDIR}}:{{MEDEXDIR}}/bin:{{MEDEXDIR}}/lib/*
    CrateMedexPipeline
    -lt {{NLPLOGTAG}}
    -v -v
# ... other arguments are added by the code
progenvsection = MY_ENV_SECTION

# =============================================================================
# Environment variable definitions (for external program, and progargs).
# The environment will start by inheriting the parent environment, then add
# variables here. Keys are case-sensitive
# =============================================================================

[MY_ENV_SECTION]

GATEDIR = /home/myuser/somewhere/GATE_Developer_8.0
NLPPROGDIR = /home/myuser/somewhere/crate_anon/nlp_manager/compiled_nlp_classes
MEDEXDIR = /home/myuser/somewhere/Medex_UIMA_1.3.6

# =============================================================================
# Output types for GATE
# =============================================================================

[output_person]

    # The tables and SPECIFIC output fields for a given GATE processor are
    # defined here.

desttable = person
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

[output_location]

destdb = DESTINATION_DATABASE
desttable = location
destfields =
    rule        VARCHAR(100)
    loctype     VARCHAR(100)

indexdefs =
    rule    100
    loctype 100

# =============================================================================
# Input field definitions, referred to within the NLP definition, and cross-
# referencing database definitions.
# - The 'copyfields' are optional.
# - The 'indexed_copyfields' are an optional subset of 'copyfields'; they'll be
#   indexed.
# =============================================================================

[INPUT_FIELD_CLINICAL_DOCUMENTS]

srcdb = SOURCE_DATABASE
srctable = EXTRACTED_CLINICAL_DOCUMENTS
srcpkfield = DOCUMENT_PK
srcfield = DOCUMENT_TEXT
copyfields = RID_FIELD
    TRID_FIELD
indexed_copyfields = RID_FIELD
    TRID_FIELD

    # Optional: specify 0 (the default) for no limit, or a number of rows (e.g.
    # 1000) to limit fetching, for debugging purposes.
# debug_row_limit = 0

[INPUT_FIELD_PROGRESS_NOTES]

srcdb = SOURCE_DATABASE
srctable = PROGRESS_NOTES
srcpkfield = PN_PK
srcfield = PN_TEXT
copyfields = RID_FIELD
    TRID_FIELD
indexed_copyfields = RID_FIELD
    TRID_FIELD

# =============================================================================
# Database definitions, each in its own section
# =============================================================================
# Use SQLAlchemy URLs: http://docs.sqlalchemy.org/en/latest/core/engines.html

[SOURCE_DATABASE]

url = mysql+mysqldb://anontest:XXX@127.0.0.1:3306/anonymous_output?charset=utf8

[DESTINATION_DATABASE]

url = mysql+mysqldb://anontest:XXX@127.0.0.1:3306/anonymous_output?charset=utf8

""".format(  # noqa
    IdentType=SqlTypeDbIdentifier,
    CLASSNAME=GATE_PIPELINE_CLASSNAME,
    DEFAULT_TEMPORARY_TABLENAME=DEFAULT_TEMPORARY_TABLENAME,
    DEFAULT_MAX_ROWS_BEFORE_COMMIT=DEFAULT_MAX_ROWS_BEFORE_COMMIT,
    DEFAULT_MAX_BYTES_BEFORE_COMMIT=DEFAULT_MAX_BYTES_BEFORE_COMMIT,
    VERSION=VERSION,
    VERSION_DATE=VERSION_DATE,
))
