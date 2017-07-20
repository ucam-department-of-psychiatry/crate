#!/usr/bin/env python
# crate_anon/nlp_manager/constants.py

"""
===============================================================================
    Copyright (C) 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.
===============================================================================
"""

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
# Notes on default fields
# =============================================================================
# - NOTE THAT THE FOLLOWING FIELDNAMES ARE USED AS STANDARD, AND WILL BE
#   AUTOCREATED:
#
#   For *all* NLP processors (from input_field_config.py):
#
#       _pk BIGINT
#           -- Arbitrary primary key (PK) within this table.
#       _nlpdef {IdentType}
#           -- Name of the NLP definition producing this row.
#       _srcdb {IdentType}
#           -- Source database name (from CRATE NLP config file)
#       _srctable {IdentType}
#           -- Source table name
#       _srcpkfield {IdentType}
#           -- PK field (column) name in source table
#       _srcpkval BIGINT
#           -- Source PK value
#       _srcpkstr VARCHAR({MAX_STRING_PK_LENGTH})
#           -- NULL if the table has an integer PK, but the PK if
#              the PK was a string, to deal with hash collisions.
#       _srcfield {IdentType}
#           -- Field (column) name of source text
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
# A. Individual NLP definitions
# =============================================================================
# - referred to by the nlp_manager.py's command-line arguments
# - You are likely to need to alter these (particularly the bits in capital
#   letters) to refer to your own database(s).

# -----------------------------------------------------------------------------
# GATE people-and-places demo
# -----------------------------------------------------------------------------

[MY_NLPDEF_NAME_LOCATION_NLP]

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
    # Default is {DEFAULT_TEMPORARY_TABLENAME}
# temporary_tablename = {DEFAULT_TEMPORARY_TABLENAME}

# -----------------------------------------------------------------------------
# KConnect (Bio-YODIE) GATE app
# -----------------------------------------------------------------------------

[MY_NLPDEF_KCONNECT]

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

[MY_NLPDEF_MEDEX_DRUGS]

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

[MY_NLPDEF_BIOMARKERS]

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
# B. NLP processor definitions
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
# Specimen GATE demo people/places processor definition
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
    #   ... ? If that doesn't work, use a double backslash, \\.
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
    #   {{X}}
    #       Substitutes variable X from the environment you specify (see
    #       below).
    #   {{NLPLOGTAG}}
    #       Additional environment variable that indicates the process being
    #       run; used to label the output from {CLASSNAME}.

progargs = java
    -classpath "{{NLPPROGDIR}}"{{OS_PATHSEP}}"{{GATEDIR}}/bin/gate.jar"{{OS_PATHSEP}}"{{GATEDIR}}/lib/*"
    -Dgate.home="{{GATEDIR}}"
    {CLASSNAME}
    -g "{{GATEDIR}}/plugins/ANNIE/ANNIE_with_defaults.gapp"
    -a Person
    -a Location
    -it END_OF_TEXT_FOR_NLP
    -ot END_OF_NLP_OUTPUT_RECORD
    -lt {{NLPLOGTAG}}
    -v

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
# Specimen KConnect (Bio-YODIE) processor definition
# -----------------------------------------------------------------------------

[procdef_gate_kconnect]

destdb = DESTINATION_DATABASE
outputtypemap =
    disease_or_syndrome output_disease_or_syndrome
progargs = java
    -classpath "{{NLPPROGDIR}}"{{OS_PATHSEP}}"{{GATEDIR}}/bin/gate.jar"{{OS_PATHSEP}}"{{GATEDIR}}/lib/*"
    -Dgate.home="{{GATEDIR}}"
    CrateGatePipeline
    -g "{{KCONNECTDIR}}/main-bio/main-bio.xgapp"
    -a Disease_or_Syndrome
    -it END_OF_TEXT_FOR_NLP
    -ot END_OF_NLP_OUTPUT_RECORD
    -lt {{NLPLOGTAG}}
    -s
    -v
progenvsection = MY_ENV_SECTION
input_terminator = END_OF_TEXT_FOR_NLP
output_terminator = END_OF_NLP_OUTPUT_RECORD
# max_external_prog_uses = 1000

# -----------------------------------------------------------------------------
# Specimen MedEx processor definition
# -----------------------------------------------------------------------------

[procdef_medex_drugs]

destdb = DESTINATION_DATABASE
desttable = drugs
progargs = java
    -classpath {{NLPPROGDIR}}:{{MEDEXDIR}}/bin:{{MEDEXDIR}}/lib/*
    -Dfile.encoding=UTF-8
    CrateMedexPipeline
    -lt {{NLPLOGTAG}}
    -v -v
# ... other arguments are added by the code
progenvsection = MY_ENV_SECTION

# =============================================================================
# C. Environment variable definitions (for external program, and progargs).
# =============================================================================
# - The environment will start by inheriting the parent environment, then add
#   variables here.
# - Keys are case-sensitive.
# - You'll need to modify this according to your local configuration.

[MY_ENV_SECTION]

GATEDIR = /home/myuser/somewhere/GATE_Developer_8.0
NLPPROGDIR = /home/myuser/somewhere/crate_anon/nlp_manager/compiled_nlp_classes
MEDEXDIR = /home/myuser/somewhere/Medex_UIMA_1.3.6
KCONNECTDIR = /home/myuser/somewhere/yodie-pipeline-1-2-umls-only
OS_PATHSEP = :


# =============================================================================
# D. Output definitions (for GATE apps)
# =============================================================================
# - These define the tables that will receive GATE output.
# - You probably don't have to modify these, unless you're adding a new GATE
#   app.

# -----------------------------------------------------------------------------
# Output types for GATE people-and-places demo
# -----------------------------------------------------------------------------

[output_person]

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

[output_location]

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
# Output types for KConnect/Bio-YODIE
# -----------------------------------------------------------------------------

[output_disease_or_syndrome]

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
# Output types for SLAM BRC GATE Pharmacotherapy
# -----------------------------------------------------------------------------
# Note new "renames" option, because the names of the annotations are not 
# always valid SQL column names.

[output_prescription]

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

# =============================================================================
# E. Input field definitions
# =============================================================================
# - Referred to within the NLP definition, and cross-referencing database
#   definitions.
# - The 'copyfields' are optional.
# - The 'indexed_copyfields' are an optional subset of 'copyfields'; they'll be
#   indexed.

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
# F. Database definitions, each in its own section
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
    MAX_STRING_PK_LENGTH=MAX_STRING_PK_LENGTH,
    VERSION=VERSION,
    VERSION_DATE=VERSION_DATE,
))
