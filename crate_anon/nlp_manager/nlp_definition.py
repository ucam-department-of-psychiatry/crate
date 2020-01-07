#!/usr/bin/env python

"""
crate_anon/nlp_manager/nlp_definition.py

===============================================================================

    Copyright (C) 2015-2020 Rudolf Cardinal (rudolf@pobox.com).

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

**NLP definition class.**

"""

# =============================================================================
# Imports
# =============================================================================

import codecs
import datetime
import json
import logging
import os
import sys
from typing import (
    Any, Dict, Iterable, List, Optional, Tuple, Type, TYPE_CHECKING,
)

from cardinal_pythonlib.datetimefunc import get_now_utc_notz_datetime
from cardinal_pythonlib.lists import chunks
from sqlalchemy.engine.base import Engine
from sqlalchemy.orm.session import Session
from sqlalchemy.schema import MetaData

from crate_anon.anonymise.constants import (
    DEFAULT_MAX_BYTES_BEFORE_COMMIT,
    DEFAULT_MAX_ROWS_BEFORE_COMMIT,
)
from crate_anon.anonymise.dbholder import DatabaseHolder
from crate_anon.common.extendedconfigparser import ExtendedConfigParser
from crate_anon.common.sql import TransactionSizeLimiter
from crate_anon.nlp_manager.cloud_config import CloudConfig
from crate_anon.nlp_manager.constants import (
    CloudNlpConfigKeys,
    DatabaseConfigKeys,
    DEFAULT_CLOUD_LIMIT_BEFORE_COMMIT,
    DEFAULT_CLOUD_MAX_CONTENT_LENGTH,
    DEFAULT_CLOUD_MAX_RECORDS_PER_REQUEST,
    DEFAULT_CLOUD_MAX_TRIES,
    DEFAULT_CLOUD_RATE_LIMIT_HZ,
    DEFAULT_CLOUD_WAIT_ON_CONN_ERR_S,
    DEFAULT_TEMPORARY_TABLENAME,
    full_sectionname,
    GATE_PIPELINE_CLASSNAME,
    NlpOutputConfigKeys,
    HashClass,
    InputFieldConfigKeys,
    MAX_SQL_FIELD_LEN,
    NLP_CONFIG_ENV_VAR,
    NlpConfigPrefixes,
    NlpDefConfigKeys,
    ProcessorConfigKeys,
    NlpDefValues,
)
from crate_anon.nlprp.constants import NlprpKeys
from crate_anon.version import CRATE_VERSION, CRATE_VERSION_DATE

if TYPE_CHECKING:
    from crate_anon.nlp_manager.base_nlp_parser import (
        BaseNlpParser,
        TableMaker,
    )
    from crate_anon.nlp_manager.input_field_config import InputFieldConfig

log = logging.getLogger(__name__)


# =============================================================================
# Demo config
# =============================================================================

def demo_nlp_config() -> str:
    """
    Returns a demo NLP config file for CRATE.
    """
    from crate_anon.nlp_manager.parse_biochemistry import ALL_BIOCHEMISTRY_NLP_AND_VALIDATORS  # delayed import  # noqa
    from crate_anon.nlp_manager.parse_clinical import ALL_CLINICAL_NLP_AND_VALIDATORS  # delayed import  # noqa
    from crate_anon.nlp_manager.parse_cognitive import ALL_COGNITIVE_NLP_AND_VALIDATORS  # delayed import  # noqa
    from crate_anon.nlp_manager.parse_haematology import ALL_HAEMATOLOGY_NLP_AND_VALIDATORS  # delayed import  # noqa

    destdb = "DESTINATION_DATABASE"
    hashphrase = "doesnotmatter"
    if_clin_docs = "INPUT_FIELD_CLINICAL_DOCUMENTS"
    if_prog_notes = "INPUT_FIELD_PROGRESS_NOTES"
    inputfields = (
        f"{if_clin_docs}\n"
        f"    {if_prog_notes}"
    )
    truncate_text_at = "32766"
    my_env = "MY_ENV_SECTION"
    my_src_db = "SOURCE_DATABASE"
    my_cloud = "my_uk_cloud_service"
    ridfield = "RID_FIELD"
    tridfield = "TRID_FIELD"
    nlp_input_terminator = "END_OF_TEXT_FOR_NLP"
    nlp_output_terminator = "END_OF_NLP_OUTPUT_RECORD"

    def _make_procdef_pair(name: str) -> str:
        return (f"""[{NlpConfigPrefixes.PROCESSOR}:procdef_{name}]
{ProcessorConfigKeys.DESTDB} = {destdb}
{ProcessorConfigKeys.DESTTABLE} = {name}
[{NlpConfigPrefixes.PROCESSOR}:procdef_validate_{name}]
{ProcessorConfigKeys.DESTDB} = {destdb}
{ProcessorConfigKeys.DESTTABLE} = validate_{name}""")

    def _make_module_procdef_block(
            nlp_and_validators: List[Tuple[Type["BaseNlpParser"],
                                           Type["BaseNlpParser"]]]) -> str:
        _procdeflist = []  # type: List[str]
        for nlpclass, validatorclass in nlp_and_validators:
            _procdeflist.append(
                _make_procdef_pair(nlpclass.classname().lower()))
        return "\n\n".join(_procdeflist)

    def _make_proclist(
            nlp_and_validators: List[Tuple[Type["BaseNlpParser"],
                                           Type["BaseNlpParser"]]]) -> str:
        _proclist = []  # type: List[str]
        for nlpclass, validatorclass in nlp_and_validators:
            _name = nlpclass.classname().lower()
            _proclist.append(
                f"    {nlpclass.classname()} procdef_{_name}\n"
                f"    {validatorclass.classname()} procdef_validate_{_name}"
            )
        return "\n".join(_proclist)

    procdefs_biochemistry = _make_module_procdef_block(ALL_BIOCHEMISTRY_NLP_AND_VALIDATORS)  # noqa
    procdefs_clinical = _make_module_procdef_block(ALL_CLINICAL_NLP_AND_VALIDATORS)  # noqa
    procdefs_cognitive = _make_module_procdef_block(ALL_COGNITIVE_NLP_AND_VALIDATORS)  # noqa
    procdefs_haematology = _make_module_procdef_block(ALL_HAEMATOLOGY_NLP_AND_VALIDATORS)  # noqa

    proclist_biochemistry = _make_proclist(ALL_BIOCHEMISTRY_NLP_AND_VALIDATORS)
    proclist_clinical = _make_proclist(ALL_CLINICAL_NLP_AND_VALIDATORS)
    proclist_cognitive = _make_proclist(ALL_COGNITIVE_NLP_AND_VALIDATORS)
    proclist_haematology = _make_proclist(ALL_HAEMATOLOGY_NLP_AND_VALIDATORS)

    return (
        f"""# Configuration file for CRATE NLP manager (crate_nlp).
# Version {CRATE_VERSION} ({CRATE_VERSION_DATE}).
#
# PLEASE SEE THE HELP.

# =============================================================================
# A. Individual NLP definitions
# =============================================================================
# - referred to by the NLP manager's command-line arguments
# - You are likely to need to alter these (particularly the bits in capital
#   letters) to refer to your own database(s).

# -----------------------------------------------------------------------------
# GATE people-and-places demo
# -----------------------------------------------------------------------------

[{NlpConfigPrefixes.NLPDEF}:gate_name_location_demo]

{NlpDefConfigKeys.INPUTFIELDDEFS} =
    {inputfields}
{NlpDefConfigKeys.PROCESSORS} =
    GATE procdef_gate_name_location
{NlpDefConfigKeys.PROGRESSDB} = {destdb}
{NlpDefConfigKeys.HASHPHRASE} = {hashphrase}


# -----------------------------------------------------------------------------
# KConnect (Bio-YODIE) disease-finding GATE app
# -----------------------------------------------------------------------------

[{NlpConfigPrefixes.NLPDEF}:gate_kconnect_diseases]

{NlpDefConfigKeys.INPUTFIELDDEFS} =
    {inputfields}
{NlpDefConfigKeys.PROCESSORS} =
    GATE procdef_gate_kconnect
{NlpDefConfigKeys.PROGRESSDB} = {destdb}
{NlpDefConfigKeys.HASHPHRASE} = {hashphrase}


# -----------------------------------------------------------------------------
# KCL Lewy body dementia GATE app
# -----------------------------------------------------------------------------

[{NlpConfigPrefixes.NLPDEF}:gate_kcl_lbd]

{NlpDefConfigKeys.INPUTFIELDDEFS} =
    {inputfields}
{NlpDefConfigKeys.PROCESSORS} =
    GATE procdef_gate_kcl_lbda
{NlpDefConfigKeys.PROGRESSDB} = {destdb}
{NlpDefConfigKeys.HASHPHRASE} = {hashphrase}


# -----------------------------------------------------------------------------
# KCL pharmacotherapy GATE app
# -----------------------------------------------------------------------------

[{NlpConfigPrefixes.NLPDEF}:gate_kcl_pharmacotherapy]

{NlpDefConfigKeys.INPUTFIELDDEFS} =
    {inputfields}
{NlpDefConfigKeys.PROCESSORS} =
    GATE procdef_gate_pharmacotherapy
{NlpDefConfigKeys.PROGRESSDB} = {destdb}
{NlpDefConfigKeys.HASHPHRASE} = {hashphrase}


# -----------------------------------------------------------------------------
# Medex-UIMA medication-finding app
# -----------------------------------------------------------------------------

[{NlpConfigPrefixes.NLPDEF}:medex_medications]

{NlpDefConfigKeys.INPUTFIELDDEFS} =
    {inputfields}
{NlpDefConfigKeys.PROCESSORS} =
    Medex procdef_medex_medications
{NlpDefConfigKeys.PROGRESSDB} = {destdb}
{NlpDefConfigKeys.HASHPHRASE} = {hashphrase}


# -----------------------------------------------------------------------------
# CRATE number-finding Python regexes
# -----------------------------------------------------------------------------

[{NlpConfigPrefixes.NLPDEF}:crate_biomarkers]

{NlpDefConfigKeys.INPUTFIELDDEFS} =
    {inputfields}
{NlpDefConfigKeys.PROCESSORS} =
    # -------------------------------------------------------------------------
    # Biochemistry
    # -------------------------------------------------------------------------
{proclist_biochemistry}
    # -------------------------------------------------------------------------
    # Clinical
    # -------------------------------------------------------------------------
{proclist_clinical}
    # -------------------------------------------------------------------------
    # Cognitive
    # -------------------------------------------------------------------------
{proclist_cognitive}
    # -------------------------------------------------------------------------
    # Haematology
    # -------------------------------------------------------------------------
{proclist_haematology}

{NlpDefConfigKeys.PROGRESSDB} = {destdb}
{NlpDefConfigKeys.HASHPHRASE} = {hashphrase}
# {NlpDefConfigKeys.TRUNCATE_TEXT_AT} = {truncate_text_at}
# {NlpDefConfigKeys.RECORD_TRUNCATED_VALUES} = False
{NlpDefConfigKeys.MAX_ROWS_BEFORE_COMMIT} = {DEFAULT_MAX_ROWS_BEFORE_COMMIT}
{NlpDefConfigKeys.MAX_BYTES_BEFORE_COMMIT} = {DEFAULT_MAX_BYTES_BEFORE_COMMIT}

# -----------------------------------------------------------------------------
# Cloud NLP demo
# -----------------------------------------------------------------------------

[{NlpConfigPrefixes.NLPDEF}:cloud_nlp_demo]

{NlpDefConfigKeys.INPUTFIELDDEFS} =
    {inputfields}
{NlpDefConfigKeys.PROCESSORS} =
    Cloud procdef_cloud_crp
{NlpDefConfigKeys.PROGRESSDB} = {destdb}
{NlpDefConfigKeys.HASHPHRASE} = {hashphrase}
{NlpDefConfigKeys.CLOUD_CONFIG} = {my_cloud}
{NlpDefConfigKeys.CLOUD_REQUEST_DATA_DIR} = /srv/crate/clouddata


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

{procdefs_biochemistry}

    # Clinical

{procdefs_clinical}

    # Cognitive

{procdefs_cognitive}

    # Haematology

{procdefs_haematology}


# -----------------------------------------------------------------------------
# Specimen GATE demo people/places processor definition
# -----------------------------------------------------------------------------

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Define the processor
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

[{NlpConfigPrefixes.PROCESSOR}:procdef_gate_name_location]

{ProcessorConfigKeys.DESTDB} = {destdb}
{ProcessorConfigKeys.OUTPUTTYPEMAP} =
    Person output_person
    Location output_location
{ProcessorConfigKeys.PROGARGS} =
    java
    -classpath "{{NLPPROGDIR}}"{{OS_PATHSEP}}"{{GATEDIR}}/bin/gate.jar"{{OS_PATHSEP}}"{{GATEDIR}}/lib/*"
    -Dgate.home="{{GATEDIR}}"
    {GATE_PIPELINE_CLASSNAME}
    --gate_app "{{GATEDIR}}/plugins/ANNIE/ANNIE_with_defaults.gapp"
    --annotation Person
    --annotation Location
    --input_terminator {nlp_input_terminator}
    --output_terminator {nlp_output_terminator}
    --log_tag {{NLPLOGTAG}}
    --verbose
{ProcessorConfigKeys.PROGENVSECTION} = {my_env}
{ProcessorConfigKeys.INPUT_TERMINATOR} = {nlp_input_terminator}
{ProcessorConfigKeys.OUTPUT_TERMINATOR} = {nlp_output_terminator}
# {ProcessorConfigKeys.MAX_EXTERNAL_PROG_USES} = 1000

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Define the output tables used by this GATE processor
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

[{NlpConfigPrefixes.OUTPUT}:output_person]

{NlpOutputConfigKeys.DESTTABLE} = person
{NlpOutputConfigKeys.RENAMES} =
    firstName   firstname
{NlpOutputConfigKeys.DESTFIELDS} =
    rule        VARCHAR(100)    Rule used to find this person (e.g. TitleFirstName, PersonFull)
    firstname   VARCHAR(100)    First name
    surname     VARCHAR(100)    Surname
    gender      VARCHAR(7)      Gender (e.g. male, female, unknown)
    kind        VARCHAR(100)    Kind of name (e.g. personName, fullName)
    # ... longest gender: "unknown" (7)
{NlpOutputConfigKeys.INDEXDEFS} =
    firstname   64
    surname     64

[{NlpConfigPrefixes.OUTPUT}:output_location]

{NlpOutputConfigKeys.DESTTABLE} = location
{NlpOutputConfigKeys.RENAMES} =
    locType     loctype
{NlpOutputConfigKeys.DESTFIELDS} =
    rule        VARCHAR(100)    Rule used (e.g. Location1)
    loctype     VARCHAR(100)    Location type (e.g. city)
{NlpOutputConfigKeys.INDEXDEFS} =
    rule    100
    loctype 100


# -----------------------------------------------------------------------------
# Specimen Sheffield/KCL KConnect (Bio-YODIE) processor definition
# -----------------------------------------------------------------------------
# https://gate.ac.uk/applications/bio-yodie.html

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Define the processor
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

[{NlpConfigPrefixes.PROCESSOR}:procdef_gate_kconnect]

{ProcessorConfigKeys.DESTDB} = {destdb}
{ProcessorConfigKeys.OUTPUTTYPEMAP} =
    Disease_or_Syndrome output_disease_or_syndrome
{ProcessorConfigKeys.PROGARGS} =
    java
    -classpath "{{NLPPROGDIR}}"{{OS_PATHSEP}}"{{GATEDIR}}/bin/gate.jar"{{OS_PATHSEP}}"{{GATEDIR}}/lib/*"
    -Dgate.home="{{GATEDIR}}"
    CrateGatePipeline
    --gate_app "{{KCONNECTDIR}}/main-bio/main-bio.xgapp"
    --annotation Disease_or_Syndrome
    --input_terminator {nlp_input_terminator}
    --output_terminator {nlp_output_terminator}
    --log_tag {{NLPLOGTAG}}
    --suppress_gate_stdout
    --verbose
{ProcessorConfigKeys.PROGENVSECTION} = {my_env}
{ProcessorConfigKeys.INPUT_TERMINATOR} = {nlp_input_terminator}
{ProcessorConfigKeys.OUTPUT_TERMINATOR} = {nlp_output_terminator}
# {ProcessorConfigKeys.MAX_EXTERNAL_PROG_USES} = 1000

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Define the output tables used by this GATE processor
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

[{NlpConfigPrefixes.OUTPUT}:output_disease_or_syndrome]

{NlpOutputConfigKeys.DESTTABLE} = kconnect_diseases
{NlpOutputConfigKeys.RENAMES} =
    Experiencer     experiencer
    Negation        negation
    PREF            pref
    STY             sty
    TUI             tui
    Temporality     temporality
    VOCABS          vocabs
{NlpOutputConfigKeys.DESTFIELDS} =
    # Found by manual inspection of KConnect/Bio-YODIE output from the GATE console:
    experiencer  VARCHAR(100)  Who experienced it; e.g. "Patient", "Other"
    negation     VARCHAR(100)  Was it negated or not; e.g. "Affirmed", "Negated"
    pref         VARCHAR(100)  PREFferred name; e.g. "Rheumatic gout"
    sty          VARCHAR(100)  Semantic Type (STY) [semantic type name]; e.g. "Disease or Syndrome"
    tui          VARCHAR(4)    Type Unique Identifier (TUI) [semantic type identifier]; 4 characters; https://www.ncbi.nlm.nih.gov/books/NBK9679/; e.g. "T047"
    temporality  VARCHAR(100)  Occurrence in time; e.g. "Recent", "historical", "hypothetical"
    vocabs       VARCHAR(255)  List of UMLS vocabularies; e.g. "AIR,MSH,NDFRT,MEDLINEPLUS,NCI,LNC,NCI_FDA,NCI,MTH,AIR,ICD9CM,LNC,SNOMEDCT_US,LCH_NW,HPO,SNOMEDCT_US,ICD9CM,SNOMEDCT_US,COSTAR,CST,DXP,QMR,OMIM,OMIM,AOD,CSP,NCI_NCI-GLOSS,CHV"
    inst         VARCHAR(8)    Looks like a Concept Unique Identifier (CUI); 1 letter then 7 digits; e.g. "C0003873"
    inst_full    VARCHAR(255)  Looks like a URL to a CUI; e.g. "http://linkedlifedata.com/resource/umls/id/C0003873"
    language     VARCHAR(100)  Language; e.g. ""; ?will look like "ENG" for English? See https://www.nlm.nih.gov/research/umls/implementation_resources/query_diagrams/er1.html
    tui_full     VARCHAR(255)  TUI (?); e.g. "http://linkedlifedata.com/resource/semanticnetwork/id/T047"
{NlpOutputConfigKeys.INDEXDEFS} =
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

[{NlpConfigPrefixes.PROCESSOR}:procdef_gate_pharmacotherapy]

{ProcessorConfigKeys.DESTDB} = {destdb}
{ProcessorConfigKeys.OUTPUTTYPEMAP} =
    Prescription output_prescription
{ProcessorConfigKeys.PROGARGS} =
    java
    -classpath "{{NLPPROGDIR}}"{{OS_PATHSEP}}"{{GATEDIR}}/bin/gate.jar"{{OS_PATHSEP}}"{{GATEDIR}}/lib/*"
    -Dgate.home="{{GATEDIR}}"
    CrateGatePipeline
    --gate_app "{{GATE_PHARMACOTHERAPY_DIR}}/application.xgapp"
    --include_set Output
    --annotation Prescription
    --input_terminator {nlp_input_terminator}
    --output_terminator {nlp_output_terminator}
    --log_tag {{NLPLOGTAG}}
    --suppress_gate_stdout
    --show_contents_on_crash
{ProcessorConfigKeys.PROGENVSECTION} = {my_env}
{ProcessorConfigKeys.INPUT_TERMINATOR} = {nlp_input_terminator}
{ProcessorConfigKeys.OUTPUT_TERMINATOR} = {nlp_output_terminator}
# {ProcessorConfigKeys.MAX_EXTERNAL_PROG_USES} = 1000

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Define the output tables used by this GATE processor
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

[{NlpConfigPrefixes.OUTPUT}:output_prescription]

{NlpOutputConfigKeys.DESTTABLE} = medications_gate
{NlpOutputConfigKeys.RENAMES} =
    drug-type           drug_type
    dose-value          dose_value
    dose-unit           dose_unit
    dose-multiple       dose_multiple
    Directionality      directionality
    Experiencer         experiencer
    "Length of Time"    length_of_time
    Temporality         temporality
    "Unit of Time"      unit_of_time
{NlpOutputConfigKeys.NULL_LITERALS} =
    null
    ""
{NlpOutputConfigKeys.DESTFIELDS} =
    # Found by (a) manual inspection of BRC GATE pharmacotherapy output from
    # the GATE console; (b) inspection of
    # application-resources/schemas/Prescription.xml
    # Note preference for DECIMAL over FLOAT/REAL; see
    # https://stackoverflow.com/questions/1056323
    # Note that not all annotations appear for all texts. Try e.g.:
    #   Please start haloperidol 5mg tds.
    #   I suggest you start haloperidol 5mg tds for one week.
    rule            VARCHAR(100)  Rule yielding this drug. Not in XML but is present in a subset: e.g. "weanOff"; max length unclear
    drug            VARCHAR(200)  Drug name. Required string; e.g. "haloperidol"; max length 47 from "wc -L BNF_generic.lst", 134 from BNF_trade.lst
    drug_type       VARCHAR(100)  Type of drug name. Required string; from "drug-type"; e.g. "BNF_generic"; ?length of longest drug ".lst" filename
    dose            VARCHAR(100)  Dose text. Required string; e.g. "5mg"; max length unclear
    dose_value      DECIMAL       Numerical dose value. Required numeric; from "dose-value"; "double" in the XML but DECIMAL probably better; e.g. 5.0
    dose_unit       VARCHAR(100)  Text of dose units. Required string; from "dose-unit"; e.g. "mg"; max length unclear
    dose_multiple   INT           Dose count (multiple). Required integer; from "dose-multiple"; e.g. 1
    route           VARCHAR(7)    Route of administration. Required string; one of: "oral", "im", "iv", "rectal", "sc", "dermal", "unknown"
    status          VARCHAR(10)   Change in drug status. Required; one of: "start", "continuing", "stop"
    tense           VARCHAR(7)    Tense in which drug is referred to. Required; one of: "past", "present"
    date            VARCHAR(100)  ?. Optional string; max length unclear
    directionality  VARCHAR(100)  ?. Optional string; max length unclear
    experiencer     VARCHAR(100)  Person experiencing the drug-related event. Optional string; e.g. "Patient"
    frequency       DECIMAL       Frequency (times per <time_unit>). Optional numeric; "double" in the XML but DECIMAL probably better
    interval        DECIMAL       The n in "every n <time_unit>s" (1 for "every <time_unit>"). Optional numeric; "double" in the XML but DECIMAL probably better
    length_of_time  VARCHAR(100)  ?. Optional string; from "Length of Time"; max length unclear
    temporality     VARCHAR(100)  ?. Optional string; e.g. "Recent", "Historical"
    time_unit       VARCHAR(100)  Unit of time (see frequency, interval). Optional string; from "time-unit"; e.g. "day"; max length unclear
    unit_of_time    VARCHAR(100)  ?. Optional string; from "Unit of Time"; max length unclear
    when            VARCHAR(100)  ?. Optional string; max length unclear
{NlpOutputConfigKeys.INDEXDEFS} =
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

[{NlpConfigPrefixes.PROCESSOR}:procdef_gate_kcl_lbda]

    # "cDiagnosis" is the "confirmed diagnosis" field, as d/w Jyoti Jyoti
    # 2018-03-20; see also README.md. This appears in the "Automatic" and the
    # unnamed set. There is also a near-miss one, "DiagnosisAlmost", which
    # appears in the unnamed set.
    #   "Mr Jones has Lewy body dementia."
    #       -> DiagnosisAlmost
    #   "Mr Jones has a diagnosis of Lewy body dementia."
    #       -> DiagnosisAlmost, cDiagnosis
    # Note that we must use lower case in the outputtypemap.

{ProcessorConfigKeys.DESTDB} = {destdb}
{ProcessorConfigKeys.OUTPUTTYPEMAP} =
    cDiagnosis output_lbd_diagnosis
    DiagnosisAlmost output_lbd_diagnosis
{ProcessorConfigKeys.PROGARGS} =
    java
    -classpath "{{NLPPROGDIR}}"{{OS_PATHSEP}}"{{GATEDIR}}/bin/gate.jar"{{OS_PATHSEP}}"{{GATEDIR}}/lib/*"
    -Dgate.home="{{GATEDIR}}"
    CrateGatePipeline
    --gate_app "{{KCL_LBDA_DIR}}/application.xgapp"
    --set_annotation "" DiagnosisAlmost
    --set_annotation Automatic cDiagnosis
    --input_terminator {nlp_input_terminator}
    --output_terminator {nlp_output_terminator}
    --log_tag {{NLPLOGTAG}}
    --suppress_gate_stdout
    --verbose
{ProcessorConfigKeys.PROGENVSECTION} = {my_env}
{ProcessorConfigKeys.INPUT_TERMINATOR} = {nlp_input_terminator}
{ProcessorConfigKeys.OUTPUT_TERMINATOR} = {nlp_output_terminator}
# {ProcessorConfigKeys.MAX_EXTERNAL_PROG_USES} = 1000

    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    # Define the output tables used by this GATE processor
    # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

[{NlpConfigPrefixes.OUTPUT}:output_lbd_diagnosis]

{NlpOutputConfigKeys.DESTTABLE} = lewy_body_dementia_gate
{NlpOutputConfigKeys.NULL_LITERALS} =
    null
    ""
{NlpOutputConfigKeys.DESTFIELDS} =
    # Found by
    # (a) manual inspection of output from the GATE Developer console:
    # - e.g. {{rule=Includefin, text=Lewy body dementia}}
    # (b) inspection of contents:
    # - run a Cygwin shell
    # - find . -type f -exec grep cDiagnosis -l {{}} \;
    # - 3 hits:
    #       ./application-resources/jape/DiagnosisExclude2.jape
    #           ... part of the "Lewy"-detection apparatus
    #       ./application-resources/jape/text-feature.jape
    #           ... adds "text" annotation to cDiagnosis Token
    #       ./application.xgapp
    #           ... in annotationTypes
    # On that basis:
    rule            VARCHAR(100)  Rule that generated the hit.
    text            VARCHAR(200)  Text that matched the rule.
{NlpOutputConfigKeys.INDEXDEFS} =
    rule    100
    text    200


# -----------------------------------------------------------------------------
# Specimen MedEx processor definition
# -----------------------------------------------------------------------------
# https://sbmi.uth.edu/ccb/resources/medex.htm

[{NlpConfigPrefixes.PROCESSOR}:procdef_medex_medications]

{ProcessorConfigKeys.DESTDB} = {destdb}
{ProcessorConfigKeys.DESTTABLE} = medications_medex
{ProcessorConfigKeys.PROGARGS} =
    java
    -classpath {{NLPPROGDIR}}:{{MEDEXDIR}}/bin:{{MEDEXDIR}}/lib/*
    -Dfile.encoding=UTF-8
    CrateMedexPipeline
    -lt {{NLPLOGTAG}}
    -v -v
# ... other arguments are added by the code
{ProcessorConfigKeys.PROGENVSECTION} = {my_env}


# =============================================================================
# C. Environment variable definitions
# =============================================================================
# - You'll need to modify this according to your local configuration.

[{NlpConfigPrefixes.ENV}:{my_env}]

GATEDIR = /home/myuser/dev/GATE_Developer_8.0
GATE_PHARMACOTHERAPY_DIR = /home/myuser/dev/brc-gate-pharmacotherapy
KCL_LBDA_DIR = /home/myuser/dev/brc-gate-LBD/Lewy_Body_Diagnosis
KCONNECTDIR = /home/myuser/dev/yodie-pipeline-1-2-umls-only
MEDEXDIR = /home/myuser/dev/Medex_UIMA_1.3.6
NLPPROGDIR = /home/myuser/dev/crate_anon/nlp_manager/compiled_nlp_classes
OS_PATHSEP = :


# =============================================================================
# D. Input field definitions
# =============================================================================

[{NlpConfigPrefixes.INPUT}:{if_clin_docs}]

{InputFieldConfigKeys.SRCDB} = {my_src_db}
{InputFieldConfigKeys.SRCTABLE} = EXTRACTED_CLINICAL_DOCUMENTS
{InputFieldConfigKeys.SRCPKFIELD} = DOCUMENT_PK
{InputFieldConfigKeys.SRCFIELD} = DOCUMENT_TEXT
{InputFieldConfigKeys.SRCDATETIMEFIELD} = DOCUMENT_DATE
{InputFieldConfigKeys.COPYFIELDS} =
    {ridfield}
    {tridfield}
{InputFieldConfigKeys.INDEXED_COPYFIELDS} =
    {ridfield}
    {tridfield}
# {InputFieldConfigKeys.DEBUG_ROW_LIMIT} = 0

[{NlpConfigPrefixes.INPUT}:{if_prog_notes}]

{InputFieldConfigKeys.SRCDB} = {my_src_db}
{InputFieldConfigKeys.SRCTABLE} = PROGRESS_NOTES
{InputFieldConfigKeys.SRCPKFIELD} = PN_PK
{InputFieldConfigKeys.SRCFIELD} = PN_TEXT
{InputFieldConfigKeys.SRCDATETIMEFIELD} = PN_DATE
{InputFieldConfigKeys.COPYFIELDS} =
    {ridfield}
    {tridfield}
{InputFieldConfigKeys.INDEXED_COPYFIELDS} =
    {ridfield}
    {tridfield}


# =============================================================================
# E. Database definitions, each in its own section
# =============================================================================

[{NlpConfigPrefixes.DATABASE}:{my_src_db}]

{DatabaseConfigKeys.URL} = mysql+mysqldb://anontest:XXX@127.0.0.1:3306/anonymous_output?charset=utf8

[{NlpConfigPrefixes.DATABASE}:{destdb}]

{DatabaseConfigKeys.URL} = mysql+mysqldb://anontest:XXX@127.0.0.1:3306/anonymous_output?charset=utf8


# =============================================================================
# F. Information for using cloud-based NLP
# =============================================================================

[{NlpConfigPrefixes.CLOUD}:{my_cloud}]

{CloudNlpConfigKeys.CLOUD_URL} = https://your_url
{CloudNlpConfigKeys.USERNAME} = your_username
{CloudNlpConfigKeys.PASSWORD} = your_password
{CloudNlpConfigKeys.WAIT_ON_CONN_ERR} = {DEFAULT_CLOUD_WAIT_ON_CONN_ERR_S}
{CloudNlpConfigKeys.MAX_CONTENT_LENGTH} = {DEFAULT_CLOUD_MAX_CONTENT_LENGTH}
{CloudNlpConfigKeys.MAX_RECORDS_PER_REQUEST} = {DEFAULT_CLOUD_MAX_RECORDS_PER_REQUEST}
{CloudNlpConfigKeys.LIMIT_BEFORE_COMMIT} = {DEFAULT_CLOUD_LIMIT_BEFORE_COMMIT}
{CloudNlpConfigKeys.STOP_AT_FAILURE} = true
{CloudNlpConfigKeys.MAX_TRIES} = {DEFAULT_CLOUD_MAX_TRIES}
{CloudNlpConfigKeys.RATE_LIMIT_HZ} = {DEFAULT_CLOUD_RATE_LIMIT_HZ}

[{NlpConfigPrefixes.PROCESSOR}:procdef_cloud_crp]

{ProcessorConfigKeys.DESTDB} = {destdb}
{ProcessorConfigKeys.DESTTABLE} = crp_test
{ProcessorConfigKeys.PROCESSOR_NAME} = crate_anon.nlp_manager.parse_biochemistry.Crp
{ProcessorConfigKeys.PROCESSOR_FORMAT} = {NlpDefValues.FORMAT_STANDARD}

"""  # noqa
    )


# =============================================================================
# Config class
# =============================================================================

class NlpDefinition(object):
    """
    Class representing an NLP master definition as read from config file.

    An NLP definition represents the combination of

    - one or more NLP processors (e.g. "CRATE's C-reactive protein finder")
    - one or more input fields in the source database

    The NLP definition can therefore be used to say "run this set of NLP
    processors over this set of textual fields in my database".

    See the documentation for the :ref:`NLP config file <nlp_config>`.
    """

    # noinspection PyUnresolvedReferences
    def __init__(self, nlpname: str, logtag: str = "") -> None:
        """
        Read config from file.

        Args:
            nlpname: config section name for this NLP definition
            logtag: text that may be passed to child processes to identify
                the NLP definition in their log output
        """

        # DELAYED IMPORTS (to make life simpler for classes deriving from
        # NlpParser and using NlpDefinition -- they can now do it directly,
        # not just via forward reference).
        from crate_anon.nlp_manager.all_processors import make_nlp_parser
        from crate_anon.nlp_manager.input_field_config import InputFieldConfig

        self._nlpname = nlpname
        self._logtag = logtag
        nlpsection = full_sectionname(NlpConfigPrefixes.NLPDEF, nlpname)

        log.info(f"Loading config for section: {nlpname}")
        # Get filename
        try:
            self._config_filename = os.environ[NLP_CONFIG_ENV_VAR]
            assert self._config_filename
        except (KeyError, AssertionError):
            print(
                f"You must set the {NLP_CONFIG_ENV_VAR} environment variable "
                f"to point to a CRATE anonymisation config file. Run "
                f"crate_print_demo_anon_config to see a specimen config.")
            sys.exit(1)

        # Read config from file.
        self._parser = ExtendedConfigParser()
        self._parser.optionxform = str  # make it case-sensitive
        log.info(f"Reading config file: {self._config_filename}")
        self._parser.read_file(codecs.open(self._config_filename, "r", "utf8"))

        if not self._parser.has_section(nlpsection):
            raise ValueError(f"No section named {nlpsection} present")

        # ---------------------------------------------------------------------
        # Our own stuff
        # ---------------------------------------------------------------------
        self._databases = {}  # type: Dict[str, DatabaseHolder]
        self._progressdb_name = self.opt_str(
            nlpsection, NlpDefConfigKeys.PROGRESSDB,
            required=True)
        self._progdb = self.get_database(self._progressdb_name)
        self._temporary_tablename = self.opt_str(
            nlpsection, NlpDefConfigKeys.TEMPORARY_TABLENAME,
            default=DEFAULT_TEMPORARY_TABLENAME)
        self._hashphrase = self.opt_str(
            nlpsection, NlpDefConfigKeys.HASHPHRASE,
            required=True)
        self._hasher = HashClass(self._hashphrase)
        self._max_rows_before_commit = self.opt_int(
            nlpsection, NlpDefConfigKeys.MAX_ROWS_BEFORE_COMMIT,
            DEFAULT_MAX_ROWS_BEFORE_COMMIT)
        self._max_bytes_before_commit = self.opt_int(
            nlpsection, NlpDefConfigKeys.MAX_BYTES_BEFORE_COMMIT,
            DEFAULT_MAX_BYTES_BEFORE_COMMIT)
        self._now = get_now_utc_notz_datetime()
        self.truncate_text_at = self.opt_int(
            nlpsection, NlpDefConfigKeys.TRUNCATE_TEXT_AT,
            default=0)
        assert self.truncate_text_at >= 0
        self.record_truncated_values = self.opt_bool(
            nlpsection, NlpDefConfigKeys.RECORD_TRUNCATED_VALUES,
            default=False)
        self._cloud_config_name = self.opt_str(
            nlpsection, NlpDefConfigKeys.CLOUD_CONFIG)
        self._cloud_request_data_dir = self.opt_str(
            nlpsection, NlpDefConfigKeys.CLOUD_REQUEST_DATA_DIR)

        # ---------------------------------------------------------------------
        # Input field definitions
        # ---------------------------------------------------------------------
        self._inputfielddefs = self.opt_strlist(
            nlpsection, NlpDefConfigKeys.INPUTFIELDDEFS,
            required=True, lower=False)
        self._inputfieldmap = {}  # type: Dict[str, InputFieldConfig]
        for x in self._inputfielddefs:
            if x in self._inputfieldmap:
                continue
            self._inputfieldmap[x] = InputFieldConfig(self, x)

        # ---------------------------------------------------------------------
        # NLP processors
        # ---------------------------------------------------------------------
        self._processors = []  # type: List[TableMaker]
        processorpairs = self.opt_strlist(
            nlpsection, NlpDefConfigKeys.PROCESSORS,
            required=True, lower=False)
        # self._procstmp = {}
        try:
            for proctype, procname in chunks(processorpairs, 2):
                self.require_section(
                    full_sectionname(NlpConfigPrefixes.PROCESSOR, procname))
                processor = make_nlp_parser(
                    classname=proctype, nlpdef=self, cfgsection=procname)
                # self._procstmp[proctype] = procname
                self._processors.append(processor)
        except ValueError:
            log.critical(f"Bad {NlpDefConfigKeys.PROCESSORS} specification")
            raise

        # ---------------------------------------------------------------------
        # Transaction sizes, for early commit
        # ---------------------------------------------------------------------
        self._transaction_limiters = {}  # type: Dict[Session, TransactionSizeLimiter]  # noqa
        # dictionary of session -> TransactionSizeLimiter

        # ---------------------------------------------------------------------
        # Cloud config (loaded on request, then cached)
        # ---------------------------------------------------------------------
        self._cloudcfg = None  # type: Optional[CloudConfig]

    def get_name(self) -> str:
        """
        Returns the name of the NLP definition.
        """
        return self._nlpname

    def get_logtag(self) -> str:
        """
        Returns the log tag of the NLP definition (may be used by child
        processes to provide more information for logs).
        """
        return self._logtag

    def get_parser(self) -> ExtendedConfigParser:
        """
        Returns the
        :class:`crate_anon.common.extendedconfigparser.ExtendedConfigParser` in
        use.
        """
        return self._parser

    def hash(self, text: str) -> str:
        """
        Hash text via this NLP definition's hasher. The hash will be stored in
        a secret progress database and to detect later changes in the source
        records.

        Args:
            text: text (typically from the source database) to be hashed

        Returns:
            the hashed value
        """
        return self._hasher.hash(text)

    def get_temporary_tablename(self) -> str:
        """
        Temporary tablename to use.

        See the documentation for the :ref:`NLP config file <nlp_config>`.
        """
        return self._temporary_tablename

    def set_echo(self, echo: bool) -> None:
        """
        Set the SQLAlchemy ``echo`` parameter (to echo SQL) for all our
        source databases.
        """
        self._progdb.engine.echo = echo
        for db in self._databases.values():
            db.engine.echo = echo
        # Now, SQLAlchemy will mess things up by adding an additional handler.
        # So, bye-bye:
        for logname in ('sqlalchemy.engine.base.Engine',
                        'sqlalchemy.engine.base.OptionEngine'):
            logger = logging.getLogger(logname)
            logger.handlers = []  # ... of type: List[logging.Handler]

    def require_section(self, section: str) -> None:
        """
        Require that the config file has a section with the specified name, or
        raise :exc:`ValueError`.
        """
        if not self._parser.has_section(section):
            msg = f"Missing config section: {section}"
            log.critical(msg)
            raise ValueError(msg)

    def opt_str(self, section: str, option: str, required: bool = False,
                default: str = None) -> str:
        """
        Returns a string option from the config file.

        Args:
            section: config section name
            option: parameter (option) name
            required: is the parameter required?
            default: default if not found and not required
        """
        return self._parser.get_str(section, option, default=default,
                                    required=required)

    def opt_strlist(self, section: str, option: str, required: bool = False,
                    lower: bool = True, as_words: bool = True) -> List[str]:
        """
        Returns a list of strings from the config file.

        Args:
            section: config section name
            option: parameter (option) name
            required: is the parameter required?
            lower: convert to lower case?
            as_words: split as words, rather than as lines?
        """
        return self._parser.get_str_list(section, option, as_words=as_words,
                                         lower=lower, required=required)

    def opt_int(self, section: str, option: str,
                default: Optional[int]) -> Optional[int]:
        """
        Returns an integer parameter from the config file.

        Args:
            section: config section name
            option: parameter (option) name
            default: default if not found and not required
        """
        return self._parser.getint(section, option, fallback=default)

    def opt_bool(self, section: str, option: str, default: bool) -> bool:
        """
        Returns a Boolean parameter from the config file.

        Args:
            section: config section name
            option: parameter (option) name
            default: default if not found and not required
        """
        return self._parser.getboolean(section, option, fallback=default)

    def get_database(self, name_and_cfg_section: str,
                     with_session: bool = True,
                     with_conn: bool = False,
                     reflect: bool = False) -> DatabaseHolder:
        """
        Returns a :class:`crate_anon.anonymise.dbholder.DatabaseHolder` from
        the config file, containing information abuot a database.

        Args:
            name_and_cfg_section:
                string that is the name of the database, and also the config
                file section name describing the database
            with_session: create an SQLAlchemy Session?
            with_conn: create an SQLAlchemy connection (via an Engine)?
            reflect: read the database structure (when required)?
        """
        if name_and_cfg_section in self._databases:
            return self._databases[name_and_cfg_section]
        dbsection = full_sectionname(NlpConfigPrefixes.DATABASE,
                                     name_and_cfg_section)
        assert len(name_and_cfg_section) <= MAX_SQL_FIELD_LEN
        db = self._parser.get_database(dbsection,
                                       with_session=with_session,
                                       with_conn=with_conn,
                                       reflect=reflect)
        self._databases[name_and_cfg_section] = db
        return db

    def get_env_dict(
            self,
            section: str,
            parent_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        Gets an operating system environment variable dictionary (``variable:
        value`` mapping) from the config file.

        Args:
            section: config section name
            parent_env: optional starting point (e.g. parent OS environment)

        Returns:
            a dictionary suitable for use as an OS environment

        """
        return self._parser.get_env_dict(section, parent_env=parent_env)

    def get_progdb_session(self) -> Session:
        """
        Returns an SQLAlchemy ORM :class:`Session` for the progress database.
        """
        return self._progdb.session

    def get_progdb_engine(self) -> Engine:
        """
        Returns an SQLAlchemy Core :class:`Engine` for the progress database.
        """
        return self._progdb.engine

    def get_progdb_metadata(self) -> MetaData:
        """
        Returns the SQLAlchemy :class:`MetaData` for the progress database.
        """
        return self._progdb.metadata

    def commit_all(self) -> None:
        """
        Execute a COMMIT on all databases (all destination database and the
        progress database).
        """
        self.commit(self.get_progdb_session())
        for db in self._databases.values():
            self.commit(db.session)

    def get_transation_limiter(self,
                               session: Session) -> TransactionSizeLimiter:
        """
        Returns (or creates and returns) a transaction limiter for a given
        SQLAlchemy session.

        Args:
            session: SQLAlchemy ORM :class:`Session`

        Returns:
            a :class:`crate_anon.common.sql.TransactionSizeLimiter`

        """
        if session not in self._transaction_limiters:
            self._transaction_limiters[session] = TransactionSizeLimiter(
                session,
                max_rows_before_commit=self._max_rows_before_commit,
                max_bytes_before_commit=self._max_bytes_before_commit)
        return self._transaction_limiters[session]

    def notify_transaction(self, session: Session,
                           n_rows: int, n_bytes: int,
                           force_commit: bool = False) -> None:
        """
        Tell our transaction limiter about a transaction that's occurred on
        one of our databases. This may trigger a COMMIT.

        Args:
            session: SQLAlchemy ORM :class:`Session` that was used
            n_rows: number of rows inserted
            n_bytes: number of bytes inserted
            force_commit: force a COMMIT?
        """
        tl = self.get_transation_limiter(session)
        tl.notify(n_rows=n_rows, n_bytes=n_bytes, force_commit=force_commit)

    def commit(self, session: Session) -> None:
        """
        Executes a COMMIT on a specific session.

        Args:
            session: SQLAlchemy ORM :class:`Session`
        """
        tl = self.get_transation_limiter(session)
        tl.commit()

    # noinspection PyUnresolvedReferences
    def get_noncloud_processors(self) -> List['BaseNlpParser']:
        """
        Returns all local (non-cloud) NLP processors used by this NLP
        definition.

        Returns:
            list of objects derived from
            :class:`crate_anon.nlp_manager.base_nlp_parser.BaseNlpParser`

        """
        # noinspection PyTypeChecker
        return [x for x in self._processors if
                x.classname() != NlpDefValues.PROCTYPE_CLOUD]

    # noinspection PyUnresolvedReferences
    def get_processors(self) -> List['TableMaker']:
        """
        Returns all NLP processors used by this NLP definition.

        Returns:
            list of objects derived from
            :class:`crate_anon.nlp_manager.base_nlp_parser.BaseNlpParser`

        """
        return self._processors

    # noinspection PyUnresolvedReferences
    def get_ifconfigs(self) -> Iterable['InputFieldConfig']:
        """
        Returns all input field configurations used by this NLP definition.

        Returns:
            list of
            `crate_anon.nlp_manager.input_field_config.InputFieldConfig`
            objects

        """
        return self._inputfieldmap.values()

    def get_now(self) -> datetime.datetime:
        """
        Returns the time this NLP definition was created (in UTC). Used to
        time-stamp NLP runs.
        """
        return self._now

    def get_progdb(self) -> DatabaseHolder:
        """
        Returns the progress database.
        """
        return self._progdb

    # -------------------------------------------------------------------------
    # NLPRP info
    # -------------------------------------------------------------------------

    def nlprp_local_processors(self,
                               sql_dialect: str = None) -> Dict[str, Any]:
        """
        Returns a draft list of processors as per the NLPRP
        :ref:`list_processors <nlprp_list_processors>` command.
        """
        processors = []  # type: List[Dict, str, Any]
        for proc in self.get_noncloud_processors():
            processors.append(proc.nlprp_processor_info(sql_dialect))
        return {
            NlprpKeys.PROCESSORS: processors,
        }

    def nlprp_local_processors_json(self,
                                    indent: int = 4,
                                    sort_keys: bool = True,
                                    sql_dialect: str = None) -> Dict[str, Any]:
        """
        Returns a formatted JSON string from :func:`nlprp_list_processors`.
        This is primarily for debugging.

        Args:
            indent: number of spaces for indentation
            sort_keys: sort keys?
            sql_dialect: preferred SQL dialect for ``tabular_schema``, or
                ``None`` for default
        """
        json_structure = self.nlprp_local_processors(sql_dialect=sql_dialect)
        return json.dumps(json_structure, indent=indent, sort_keys=sort_keys)

    # -------------------------------------------------------------------------
    # Cloud NLP
    # -------------------------------------------------------------------------

    def get_cloud_config(self) -> Optional[CloudConfig]:
        """
        Returns the :class:`crate_anon.nlp_manager.cloud_config.CloudConfig`
        object associated with this NLP definition, or ``None`` if there isn't
        one.
        """
        our_name = self.get_name()
        if self._cloudcfg is None:
            if not self._cloud_config_name:
                raise ValueError(
                    f"No {NlpDefConfigKeys.CLOUD_CONFIG!r} parameter "
                    f"specified for NLP definition {our_name!r}")
            if not self._cloud_request_data_dir:
                raise ValueError(
                    f"No {NlpDefConfigKeys.CLOUD_REQUEST_DATA_DIR!r} parameter "  # noqa
                    f"specified for NLP definition {our_name!r}")
            req_root_dir = os.path.abspath(self._cloud_request_data_dir)
            if not os.path.isdir(req_root_dir):
                raise ValueError(
                    f"Directory {req_root_dir!r}, specified by config "
                    f"parameter {NlpDefConfigKeys.CLOUD_REQUEST_DATA_DIR!r} "
                    f"for NLP definition {our_name!r}")
            req_data_dir = os.path.join(req_root_dir, our_name)
            os.makedirs(req_data_dir, exist_ok=True)
            self._cloudcfg = CloudConfig(self,
                                         name=self._cloud_config_name,
                                         req_data_dir=req_data_dir)
        return self._cloudcfg

    def get_cloud_config_or_raise(self) -> CloudConfig:
        """
        Returns the :class:`crate_anon.nlp_manager.cloud_config.CloudConfig`
        object associated with this NLP definition, or raise :exc:`ValueError`
        if there isn't one.
        """
        cloudcfg = self.get_cloud_config()
        if cloudcfg is None:
            raise ValueError(f"No cloud NLP configuration for NLP definition "
                             f"{self.get_name()!r}")
        if not cloudcfg.remote_processors:
            raise ValueError(f"No remote (cloud) processors configured for "
                             f"NLP definition {self.get_name()!r}")
        return cloudcfg
