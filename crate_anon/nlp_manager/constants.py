#!/usr/bin/env python

"""
crate_anon/nlp_manager/constants.py

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

**Constants for CRATE NLP, including a demo config file.**

"""

from cardinal_pythonlib.hash import HmacMD5Hasher
from sqlalchemy.types import String

# =============================================================================
# Constants
# =============================================================================

DEFAULT_CLOUD_LIMIT_BEFORE_COMMIT = 1000
DEFAULT_CLOUD_MAX_CONTENT_LENGTH = 0  # no limit
DEFAULT_CLOUD_MAX_RECORDS_PER_REQUEST = 1000
DEFAULT_CLOUD_MAX_TRIES = 5
DEFAULT_CLOUD_RATE_LIMIT_HZ = 2
DEFAULT_CLOUD_WAIT_ON_CONN_ERR_S = 180  # in seconds
DEFAULT_REPORT_EVERY_NLP = 500  # low values slow down processing
DEFAULT_TEMPORARY_TABLENAME = "_crate_nlp_temptable"

FN_CRATE_VERSION_FIELD = "_crate_version"  # new in v0.18.53
FN_NLPDEF = "_nlpdef"
FN_PK = "_pk"
FN_SRCDATETIMEFIELD = "_srcdatetimefield"  # new in v0.18.52
FN_SRCDATETIMEVAL = "_srcdatetimeval"  # new in v0.18.52
FN_SRCDB = "_srcdb"
FN_SRCFIELD = "_srcfield"
FN_SRCPKFIELD = "_srcpkfield"
FN_SRCPKSTR = "_srcpkstr"
FN_SRCPKVAL = "_srcpkval"
FN_SRCTABLE = "_srctable"
FN_WHEN_FETCHED = "_when_fetched_utc"  # new in v0.18.53

TRUNCATED_FLAG = "_truncated"  # NOT A FIELD/COLUMN NAME. INTERNAL USE ONLY.

GATE_PIPELINE_CLASSNAME = 'CrateGatePipeline'

HashClass = HmacMD5Hasher

MAX_STRING_PK_LENGTH = 64  # trade-off; space versus capability
MAX_SQL_FIELD_LEN = 64
# ... http://dev.mysql.com/doc/refman/5.0/en/identifiers.html
MAX_SEMANTIC_VERSION_STRING_LENGTH = 147  # https://github.com/mojombo/semver/issues/79  # noqa
MEDEX_PIPELINE_CLASSNAME = "CrateMedexPipeline"
MEDEX_DATA_READY_SIGNAL = "data_ready"
MEDEX_RESULTS_READY_SIGNAL = "results_ready"

NLP_CONFIG_ENV_VAR = "CRATE_NLP_CONFIG"

SqlTypeDbIdentifier = String(MAX_SQL_FIELD_LEN)
# ... text field used for database names, table names, and field names


# =============================================================================
# Simple classes for string constant collections
# =============================================================================

class NlpConfigPrefixes(object):
    """
    Section name prefixes for the NLP config file.
    """
    NLPDEF = "nlpdef"
    PROCESSOR = "processor"
    ENV = "env"
    OUTPUT = "output"
    INPUT = "input"
    DATABASE = "database"
    CLOUD = "cloud"


class NlpDefConfigKeys(object):
    """
    Config file keys for NLP definitions.
    """
    INPUTFIELDDEFS = "inputfielddefs"
    PROCESSORS = "processors"
    PROGRESSDB = "progressdb"
    HASHPHRASE = "hashphrase"
    TEMPORARY_TABLENAME = "temporary_tablename"
    MAX_ROWS_BEFORE_COMMIT = "max_rows_before_commit"
    MAX_BYTES_BEFORE_COMMIT = "max_bytes_before_commit"
    TRUNCATE_TEXT_AT = "truncate_text_at"
    RECORD_TRUNCATED_VALUES = "record_truncated_values"
    CLOUD_CONFIG = "cloud_config"
    CLOUD_REQUEST_DATA_DIR = "cloud_request_data_dir"


class NlpDefValues(object):
    """
    Config file values for NLP definitions
    """
    PROCTYPE_CLOUD = "Cloud"
    # Since any server with the same output format as CRATE's is compatible,
    # we call this format standard
    FORMAT_STANDARD = "Standard"
    FORMAT_GATE = "GATE"


class InputFieldConfigKeys(object):
    """
    Config file keys for input database fields (columns).
    """
    SRCDB = "srcdb"
    SRCTABLE = "srctable"
    SRCPKFIELD = "srcpkfield"
    SRCFIELD = "srcfield"
    SRCDATETIMEFIELD = "srcdatetimefield"
    COPYFIELDS = "copyfields"
    INDEXED_COPYFIELDS = "indexed_copyfields"
    DEBUG_ROW_LIMIT = "debug_row_limit"


class ProcessorConfigKeys(object):
    """
    Config file keys for NLP processors.
    """
    ASSUME_PREFERRED_UNIT = "assume_preferred_unit"
    DESTDB = "destdb"
    DESTTABLE = "desttable"
    OUTPUTTYPEMAP = "outputtypemap"
    PROGARGS = "progargs"
    PROGENVSECTION = "progenvsection"
    INPUT_TERMINATOR = "input_terminator"
    OUTPUT_TERMINATOR = "output_terminator"
    MAX_EXTERNAL_PROG_USES = "max_external_prog_uses"
    PROCESSOR_NAME = "processor_name"
    PROCESSOR_VERSION = "processor_version"
    PROCESSOR_FORMAT = "processor_format"


class NlpOutputConfigKeys(object):
    """
    Config file keys for output tables from GATE or Cloud NLP processors.
    """
    DESTTABLE = "desttable"
    RENAMES = "renames"
    NULL_LITERALS = "null_literals"
    DESTFIELDS = "destfields"
    INDEXDEFS = "indexdefs"


class DatabaseConfigKeys(object):
    """
    Config file keys for database definitions.
    """
    URL = "url"
    ECHO = "echo"


class CloudNlpConfigKeys(object):
    """
    Config file keys for cloud NLP.
    """
    CLOUD_URL = "cloud_url"
    VERIFY_SSL = "verify_ssl"
    COMPRESS = "compress"
    USERNAME = "username"
    PASSWORD = "password"
    WAIT_ON_CONN_ERR = "wait_on_conn_err"
    MAX_CONTENT_LENGTH = "max_content_length"
    LIMIT_BEFORE_COMMIT = "limit_before_commit"
    MAX_RECORDS_PER_REQUEST = "max_records_per_request"
    STOP_AT_FAILURE = "stop_at_failure"
    MAX_TRIES = "max_tries"
    RATE_LIMIT_HZ = "rate_limit_hz"
    TEST_LENGTH_FUNCTION_SPEED = "test_length_function_speed"


class GateApiKeys(object):
    """
    Dictionary keys for the direct API to GATE.

    See https://cloud.gate.ac.uk/info/help/online-api.html for format of
    response from processor. The GATE JSON format is:

    .. code-block:: json

        {
          "text":"The text of the document",
          "entities":{
            "SampleAnnotationType1":[
              {
                "indices":[0,3],
                "feature1":"value1",
                "feature2":"value2"
              }
            ],
            "SampleAnnotationType2":[
              {
                "indices":[12,15],
                "feature3":"value3"
              }
            ]
          }
        }
    """
    ENTITIES = "entities"
    INDICES = "indices"
    TEXT = "text"


class GateResultKeys(object):
    """
    Dictionary keys to represent GATE results in our NLPRP server.
    """
    TYPE = "type"
    START = "start"
    END = "end"
    SET = "set"
    FEATURES = "features"


class GateFieldNames(object):
    """
    Field (column) names for results from GATE.
    These match KEY_* strings in ``CrateGatePipeline.java``.
    """
    SET = '_set'
    TYPE = '_type'
    ID = '_id'
    STARTPOS = '_start'
    ENDPOS = '_end'
    CONTENT = '_content'


# =============================================================================
# Config helpers
# =============================================================================

_ALL_NLPRP_SECTION_PREFIXES = [
    v for k, v in NlpConfigPrefixes.__dict__.items()
    if not k.startswith("_")
]


def full_sectionname(section_type: str, section: str) -> str:
    if section_type in _ALL_NLPRP_SECTION_PREFIXES:
        return section_type + ":" + section
    raise ValueError(f"Unrecognised section type: {section_type}")
