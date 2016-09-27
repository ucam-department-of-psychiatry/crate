#!/usr/bin/env python
# crate_anon/nlp_manager/constants.py

from sqlalchemy.types import String
from crate_anon.common.hash import HmacMD5Hasher


GATE_PIPELINE_CLASSNAME = 'CrateGatePipeline'

NLP_CONFIG_ENV_VAR = 'CRATE_NLP_CONFIG'

MAX_SQL_FIELD_LEN = 64
# ... http://dev.mysql.com/doc/refman/5.0/en/identifiers.html
SqlTypeDbIdentifier = String(MAX_SQL_FIELD_LEN)  # text field used for database
# names, table names, and field names

HashClass = HmacMD5Hasher


# =============================================================================
# Demo config
# =============================================================================

DEMO_CONFIG = ("""
# Configuration file for CRATE NLP manager (crate_nlp).
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

progressdb = MY_DESTINATION_DATABASE
hashphrase = doesnotmatter



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
    # -------------------------------------------------------------------------
    # Cognitive
    # -------------------------------------------------------------------------
    MMSE procdef_mmse
    MMSEValidator procdef_validate_mmse
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

progressdb = MY_DESTINATION_DATABASE
hashphrase = doesnotmatter


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
destdb = anonymous_output
desttable = crp
[procdef_validate_crp]
destdb = anonymous_output
desttable = validate_crp

[procdef_sodium]
destdb = anonymous_output
desttable = sodium
[procdef_validate_sodium]
destdb = anonymous_output
desttable = validate_sodium

    # Cognitive

[procdef_mmse]
destdb = anonymous_output
desttable = mmse
[procdef_validate_mmse]
destdb = anonymous_output
desttable = validate_mmse

    # Haematology

[procdef_esr]
destdb = anonymous_output
desttable = esr
[procdef_validate_esr]
destdb = anonymous_output
desttable = validate_esr

[procdef_wbc]
destdb = anonymous_output
desttable = wbc
[procdef_validate_wbc]
destdb = anonymous_output
desttable = validate_wbc

[procdef_basophils]
destdb = anonymous_output
desttable = basophils
[procdef_validate_basophils]
destdb = anonymous_output
desttable = validate_basophils

[procdef_eosinophils]
destdb = anonymous_output
desttable = eosinophils
[procdef_validate_eosinophils]
destdb = anonymous_output
desttable = validate_eosinophils

[procdef_lymphocytes]
destdb = anonymous_output
desttable = lymphocytes
[procdef_validate_lymphocytes]
destdb = anonymous_output
desttable = validate_lymphocytes

[procdef_monocytes]
destdb = anonymous_output
desttable = monocytes
[procdef_validate_monocytes]
destdb = anonymous_output
desttable = validate_monocytes

[procdef_neutrophils]
destdb = anonymous_output
desttable = neutrophils
[procdef_validate_neutrophils]
destdb = anonymous_output
desttable = validate_neutrophils

# -----------------------------------------------------------------------------
# Specimen GATE processor definition
# -----------------------------------------------------------------------------

[procdef_gate_name_location]

    # Which database will this processor write to?

destdb = MY_DESTINATION_DATABASE

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


# =============================================================================
# Environment variable definitions (for external program, and progargs).
# The environment will start by inheriting the parent environment, then add
# variables here. Keys are case-sensitive
# =============================================================================

[MY_ENV_SECTION]

GATEDIR = /home/myuser/GATE_Developer_8.0
NLPPROGDIR = /home/myuser/somewhere/crate_anon/nlp_manager/compiled_nlp_classes

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

destdb = MY_DESTINATION_DATABASE
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
# The 'copyfields' are optional.
# =============================================================================

[INPUT_FIELD_CLINICAL_DOCUMENTS]

srcdb = MY_SOURCE_DATABASE
srctable = EXTRACTED_CLINICAL_DOCUMENTS
srcpkfield = DOCUMENT_PK
srcfield = DOCUMENT_TEXT
copyfields = RID_FIELD
    TRID_FIELD

[INPUT_FIELD_PROGRESS_NOTES]

srcdb = MY_SOURCE_DATABASE
srctable = PROGRESS_NOTES
srcpkfield = PN_PK
srcfield = PN_TEXT
copyfields = RID_FIELD
    TRID_FIELD

# =============================================================================
# Database definitions, each in its own section
# =============================================================================
# Use SQLAlchemy URLs: http://docs.sqlalchemy.org/en/latest/core/engines.html

[MY_SOURCE_DATABASE]

url = mysql+mysqldb://anontest:XXX@127.0.0.1:3306/anonymous_output?charset=utf8

[MY_DESTINATION_DATABASE]

url = mysql+mysqldb://anontest:XXX@127.0.0.1:3306/anonymous_output?charset=utf8

""".format(  # noqa
    IdentType=SqlTypeDbIdentifier,
    CLASSNAME=GATE_PIPELINE_CLASSNAME,
))
