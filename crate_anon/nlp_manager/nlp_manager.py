#!/usr/bin/env python3
# nlp_manager/nlp_manager.py

"""
Manage natural-language processing (NLP) via external tools.

Author: Rudolf Cardinal
Created at: 26 Feb 2015
Last update: see VERSION_DATE below

Copyright/licensing:

    Copyright (C) 2015-2016 Rudolf Cardinal (rudolf@pobox.com).
    Department of Psychiatry, University of Cambridge.

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

Speed testing:

    - 8 processes, extracting person, location from a mostly text database
    - commit off during full (non-incremental) processing (much faster)
    - needs lots of RAM; e.g. Java subprocess uses 1.4 Gb per process as an
      average (rises from ~250Mb to ~1.4Gb and falls; steady rise means memory
      leak!); tested on a 16 Gb machine. See also the max_external_prog_uses
      parameter.

from __future__ import division
test_size_mb = 1887
n_person_tags_found =
n_locations_tags_found =
time_s = 10333  # 10333 s for main bit; 10465 including indexing; is 2.9 hours
speed_mb_per_s = test_size_mb / time_s

    ... 0.18 Mb/s
    ... and note that's 1.9 Gb of *text*, not of attachments

    - With incremental option, and nothing to do:
        same run took 18 s
    - During the main run, snapshot CPU usage:
        java about 81% across all processes, everything else close to 0
            (using about 12 Gb RAM total)
        ... or 75-85% * 8 [from top]
        mysqld about 18% [from top]
        nlp_manager.py about 4-5% * 8 [from top]

TO DO:
    - comments for NLP output fields (in table definition, destfields)

"""


# =============================================================================
# Imports
# =============================================================================

import argparse
import ast
import codecs
import configparser
from functools import lru_cache
import logging
import os
import subprocess
import sys

from cardinal_pythonlib.rnc_datetime import (
    get_now_utc,
    get_now_utc_notz
)
from cardinal_pythonlib.rnc_db import (
    ensure_valid_field_name,
    ensure_valid_table_name,
    is_sqltype_valid
)
from cardinal_pythonlib.rnc_lang import chunks

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import Column, Index, MetaData, Table
from sqlalchemy.sql import column, func, select, table
from sqlalchemy.types import BigInteger, DateTime, String

from crate_anon.anonymise.constants import (
    MAX_PID_STR,
    MYSQL_TABLE_ARGS,
    SEP,
)
from crate_anon.anonymise.dbholder import DatabaseHolder
from crate_anon.anonymise.hash import HmacMD5Hasher
from crate_anon.anonymise.logsupport import configure_logger_for_colour
from crate_anon.anonymise.sqla import (
    add_index,
    get_sqla_coltype_from_dialect_str,
    index_exists,
)
from crate_anon.version import VERSION, VERSION_DATE
from crate_anon.nlp_manager.constants import GATE_PIPELINE_CLASSNAME

log = logging.getLogger(__name__)

progress_meta = MetaData()
ProgressBase = declarative_base(metadata=progress_meta)

# =============================================================================
# Global constants
# =============================================================================

HashClass = HmacMD5Hasher
encrypted_length = len(HashClass("dummysalt").hash(MAX_PID_STR))
SqlTypeHash = String(encrypted_length)

NLP_CONFIG_ENV_VAR = 'CRATE_NLP_CONFIG'

MAX_SQL_FIELD_LEN = 64
# ... http://dev.mysql.com/doc/refman/5.0/en/identifiers.html
SqlTypeDb = String(MAX_SQL_FIELD_LEN)

# =============================================================================
# Demo config
# =============================================================================

DEMO_CONFIG = ("""
# Configuration file for nlp_manager.py

# =============================================================================
# Overview
# =============================================================================
# - NOTE THAT THE FOLLOWING FIELDNAMES ARE USED AS STANDARD, AND WILL BE
#   AUTOCREATED:
#
#   From nlp_manager.py:
#       _pk         INT             PK within this table.
#       _srcdb      {SqlTypeDb}     Source database name
#       _srctable   {SqlTypeDb}         Source table name
#       _srcpkfield {SqlTypeDb}         Source primary key (PK) field name
#       _srcpkval   INT             Source PK value
#       _srcfield   {SqlTypeDb}         Source field containing text content
#
#   From CrateGatePipeline.java:
#       _type       VARCHAR     Annotation type name (e.g. 'Person')
#       _id         INT         Annotation ID, from GATE. Not clear that this
#                               is particularly useful.
#       _start      INT         Start position in the content
#       _end        INT         End position in the content
#       _content    TEXT        Full content marked as relevant. (Not the
#                               entire content of the source field.)
#                               (You don't have to keep this!)
#
#   The length of the VARCHAR fields is set by the MAX_SQL_FIELD_LEN constant.
#
#   Then individual GATE annotation systems might add their own fields.
#   For example, the ANNIE example has a "Person" annotation.
#
# - Output type section names MUST be in lower case (and output types will be
#   converted to lower case internally on receipt from the NLP program).

# =============================================================================
# Individual NLP definitions
# - referred to by the nlp_manager.py's command-line arguments
# =============================================================================

[MY_NAME_LOCATION_NLP]

# -----------------------------------------------------------------------------
# Input is from one or more source databases/tables/fields.
# This list refers to config sections that define those fields in more detail.
# -----------------------------------------------------------------------------

inputfielddefs =
    INPUT_FIELD_CLINICAL_DOCUMENTS
    INPUT_FIELD_PROGRESS_NOTES
    ...

# -----------------------------------------------------------------------------
# The output's _type parameter is used to look up possible destination tables
# (in case-insensitive fashion). What follows is a list of pairs: the first
# item is the annotation type coming out of the GATE system, and the second is
# the output type section defined in this file.
# -----------------------------------------------------------------------------

outputtypemap =
    person output_person
    location output_location

# -----------------------------------------------------------------------------
# NLP is done by an external program.
# Here we specify a program and associated arguments. The example shows how to
# use Java to launch a specific Java program ({{CLASSNAME}}), having set
# a path to find other Java classes, and then to pass arguments to the program
# itself.
# -----------------------------------------------------------------------------
# Substitutable parameters:
#   {{X}}         Substitutes variable X from the environment.
#   {{NLPLOGTAG}} Additional environment variable that indicates the process
#               being run; used to label the output from {{CLASSNAME}}.

progenvsection = MY_ENV_SECTION

progargs = java
    -classpath {{NLPPROGDIR}}:{{GATEDIR}}/bin/gate.jar:{{GATEDIR}}/lib/*
    {{CLASSNAME}}
    -g {{GATEDIR}}/plugins/ANNIE/ANNIE_with_defaults.gapp
    -a Person
    -a Location
    -it END_OF_TEXT_FOR_NLP
    -ot END_OF_NLP_OUTPUT_RECORD
    -lt {{NLPLOGTAG}}
    -v -v

# ... to which the text will be passed via stdin
# ... and the result will be expected via stdout, as a set of TSV
#     lines corresponding to the fields in destfields below

# -----------------------------------------------------------------------------
# The external program is slow, because NLP is slow. Therefore, we set up the
# external program and use it repeatedly for a whole bunch of text. Individual
# pieces of text are sent to it (via its stdin). We finish our piece of text
# with a delimiter, which should (a) be specified in the -it parameter above,
# and (b) be set below, TO THE SAME VALUE. The external program should return a
# TSV-delimited set of field/value pairs, like this:
#
#       field1\tvalue1\tfield2\tvalue2...
#       field1\tvalue3\tfield2\tvalue4...
#       ...
#       TERMINATOR
#
# ... where TERMINATOR is something that you (a) specify with the -ot parameter
# above, and (b) set below, TO THE SAME VALUE.
# -----------------------------------------------------------------------------

input_terminator = END_OF_TEXT_FOR_NLP
output_terminator = END_OF_NLP_OUTPUT_RECORD

# -----------------------------------------------------------------------------
# If the external program leaks memory, you may wish to cap the number of uses
# before it's restarted. Specify the max_external_prog_uses option if so.
# Specify 0 or omit the option entirely to ignore this.
# -----------------------------------------------------------------------------

# max_external_prog_uses = 1000

# -----------------------------------------------------------------------------
# To allow incremental updates, information is stored in a progress table.
# -----------------------------------------------------------------------------

progressdb = MY_DESTINATION_DATABASE
hashphrase = doesnotmatter

# =============================================================================
# Environment variable definitions (for external program, and progargs).
# The environment will start by inheriting the parent environment, then add
# variables here. Keys are case-sensitive
# =============================================================================

[MY_ENV_SECTION]

GATEDIR = /home/myuser/GATE_Developer_8.0
NLPPROGDIR = /home/myuser/somewhere/crate/nlp_manager/compiled_nlp_classes

# =============================================================================
# Output types
# =============================================================================

[output_person]

# -----------------------------------------------------------------------------
# The output is defined here. See the list of common fields above.
# Define your table's output fields below. The destfields list contains
# (fieldname, datatype) pairs.
# Anything from the output that matches what's below (in case-insensitive
# fashion) will be kept, and anything else will be discarded.
# Similarly, if any fields below are present in the 'copyfields' from the
# source, they will be copied.
# -----------------------------------------------------------------------------

destdb = MY_DESTINATION_DATABASE
desttable = PERSON
destfields =
    _srcdb      {SqlTypeDb}
    _srctable   {SqlTypeDb}
    _srcpkfield {SqlTypeDb}
    _srcpkval   INT
    _srcfield   {SqlTypeDb}
    _type       {SqlTypeDb}
    _id         INT
    _start      INT
    _end        INT
    _content    TEXT
    rule        VARCHAR(100)
    firstname   VARCHAR(100)
    surname     VARCHAR(100)
    gender      VARCHAR(6)
    kind        VARCHAR(100)
    RID_FIELD   VARCHAR(64)
    TRID_FIELD  INT

indexdefs =
    firstname   64
    surname     64

# ... a set of (indexed field, index length) pairs; length can be "None"

[output_location]

destdb = MY_DESTINATION_DATABASE
desttable = LOCATION
destfields =
    _srcdb      {SqlTypeDb}
    _srctable   {SqlTypeDb}
    _srcpkfield {SqlTypeDb}
    _srcpkval   INT
    _srcfield   {SqlTypeDb}
    _type       {SqlTypeDb}
    _id         INT
    _start      INT
    _end        INT
    _content    TEXT
    rule        VARCHAR(100)
    loctype     VARCHAR(100)
    RID_FIELD   VARCHAR(64)
    TRID_FIELD  INT

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

""".format(
    SqlTypeDb=SqlTypeDb,
    CLASSNAME=GATE_PIPELINE_CLASSNAME,
))


# =============================================================================
# Classes for various bits of config
# =============================================================================

class OutputTypeConfig(object):
    """
    Class defining configuration for the output of a given GATE app.
    """

    def __init__(self, parser, section):
        """
        Read config from a configparser section.
        """
        if not parser.has_section(section):
            raise ValueError("config missing section: " + section)

        def opt_str(option, required=False):
            s = parser.get(section, option, fallback=None)
            if required and not s:
                raise ValueError("Missing: {}".format(option))
            return s

        def opt_strlist(option, required=False, lower=True):
            text = parser.get(section, option, fallback='')
            if lower:
                text = text.lower()
            opts = [x.strip() for x in text.strip().split() if x.strip()]
            if required and not opts:
                raise ValueError("Missing: {}".format(option))
            return opts

        self.destdb = opt_str('destdb', required=True)

        self.desttable = opt_str('desttable', required=True)
        ensure_valid_table_name(self.desttable)

        self.destfields = []
        self.dest_datatypes = []
        dest_fields_datatypes = opt_strlist('destfields', required=True)
        for c in chunks(dest_fields_datatypes, 2):
            field = c[0]
            datatype = c[1].upper()
            ensure_valid_field_name(field)
            if not is_sqltype_valid(datatype):
                raise Exception(
                    "Invalid datatype for {}: {}".format(field, datatype))
            self.destfields.append(field)
            self.dest_datatypes.append(datatype)

        special_fields = ["_srcdb", "_srctable", "_srcpkfield", "_srcpkval",
                          "_srcfield"]
        for special in special_fields:
            if special in self.destfields:
                raise Exception(
                    "For section {}, special destfield {} is auto-supplied; "
                    "do not add it manually".format(
                        section,
                        special,
                    )
                )

        allfields = special_fields + self.destfields
        if len(allfields) != len(set(allfields)):
            raise ValueError(
                "Duplicate field in section {} (or field overlaps "
                "with {})".format(section, special_fields))

        self.indexfields = []
        self.indexlengths = []
        indexdefs = opt_strlist('indexdefs')
        if indexdefs:
            for c in chunks(indexdefs, 2):  # pairs: field, length
                indexfieldname = c[0]
                lengthstr = c[1]
                if indexfieldname not in allfields:
                    raise ValueError(
                        "Index field {} not in destination fields {}".format(
                            indexfieldname, allfields))
                try:
                    length = ast.literal_eval(lengthstr)
                    if length is not None:
                        length = int(length)
                except ValueError:
                    raise ValueError(
                        "Bad index length: {}".format(lengthstr))
                self.indexfields.append(indexfieldname)
                self.indexlengths.append(length)


class InputFieldConfig(object):
    """
    Class defining configuration for an input field (containing text).
    """

    def __init__(self, parser, section):
        """
        Read config from a configparser section.
        """
        def opt_str(option):
            s = parser.get(section, option, fallback=None)
            if not s:
                raise ValueError("Missing: {}".format(option))
            return s

        def opt_strlist(option, required=False, lower=True):
            text = parser.get(section, option, fallback='')
            if lower:
                text = text.lower()
            opts = [x.strip() for x in text.strip().split() if x.strip()]
            if required and not opts:
                raise ValueError("Missing: {}".format(option))
            return opts

        self.srcdb = opt_str('srcdb')
        self.srctable = opt_str('srctable')
        self.srcpkfield = opt_str('srcpkfield')
        self.srcfield = opt_str('srcfield')
        self.copyfields = opt_strlist('copyfields')
        ensure_valid_table_name(self.srctable)
        ensure_valid_field_name(self.srcpkfield)
        ensure_valid_field_name(self.srcfield)
        allfields = [self.srcpkfield, self.srcfield] + self.copyfields
        if len(allfields) != len(set(allfields)):
            raise ValueError(
                "Field overlap in InputFieldConfig: {}".format(section))


# =============================================================================
# Config class
# =============================================================================

class Config(object):
    """
    Class representing configuration as read from config file.
    """

    # noinspection PyUnresolvedReferences
    def __init__(self, nlpname, logtag=""):
        """
        Read config from file.
        """
        log.info("Loading config for section: {}".format(nlpname))
        # Get filename
        try:
            self.config_filename = os.environ[NLP_CONFIG_ENV_VAR]
            assert self.config_filename
        except (KeyError, AssertionError):
            print(
                "You must set the {} environment variable to point to a CRATE "
                "anonymisation config file. Run crate_print_demo_anon_config "
                "to see a specimen config.".format(NLP_CONFIG_ENV_VAR))
            sys.exit(1)

        # Read config from file.
        parser = configparser.RawConfigParser()
        parser.optionxform = str  # make it case-sensitive
        parser.read_file(codecs.open(self.config_filename, "r", "utf8"))
        section = nlpname

        def opt_str(option, required=False, default=None):
            s = parser.get(section, option, fallback=default)
            if required and not s:
                raise ValueError("Missing: {} in section {}".format(option,
                                                                    section))
            return s

        def opt_strlist(option, required=False, lower=True):
            text = parser.get(section, option, fallback='')
            if lower:
                text = text.lower()
            opts = [s.strip() for s in text.strip().split() if s.strip()]
            if required and not opts:
                raise ValueError("Missing: {} in section {}".format(option,
                                                                    section))
            return opts

        def opt_int(option, default):
            return parser.getint(nlpname, option, fallback=default)

        def get_database(name_and_cfg_section, with_session=True,
                         with_conn=False, reflect=False):
            url = parser.get(name_and_cfg_section, 'url', fallback=None)
            if not url:
                raise ValueError(
                    "Missing 'url' parameter in section {}".format(
                        name_and_cfg_section))
            return DatabaseHolder(name_and_cfg_section, url, srccfg=None,
                                  with_session=with_session,
                                  with_conn=with_conn,
                                  reflect=reflect)

        self.max_external_prog_uses = opt_int('max_external_prog_uses',
                                              default=0)
        self.progressdb = opt_str('progressdb', required=True)
        self.input_terminator = opt_str('input_terminator', required=True)
        self.output_terminator = opt_str('output_terminator', required=True)

        # inputfielddefs, inputfieldmap, databases
        self.inputfieldmap = {}
        self.databases = {}
        self.inputfielddefs = opt_strlist('inputfielddefs', required=True,
                                          lower=False)
        for x in self.inputfielddefs:
            if x in self.inputfieldmap.keys():
                continue
            c = InputFieldConfig(parser, x)
            self.inputfieldmap[x] = c
            dbname = c.srcdb
            if dbname not in self.databases.keys():
                self.databases[dbname] = get_database(dbname)

        # outputtypemap, databases
        typepairs = opt_strlist('outputtypemap', required=True, lower=False)
        self.outputtypemap = {}
        for c in chunks(typepairs, 2):
            annottype = c[0]
            outputsection = c[1]
            if annottype != annottype.lower():
                raise Exception(
                    "Section {}: annotation types in outputtypemap must be in "
                    "lower case: change {}".format(section, annottype))
            c = OutputTypeConfig(parser, outputsection)
            self.outputtypemap[annottype] = c
            dbname = c.destdb
            if dbname not in self.databases.keys():
                self.databases[dbname] = get_database(dbname)

        # progenvsection, env, progargs, logtag
        self.env = os.environ.copy()
        self.progenvsection = opt_str('progenvsection')
        if self.progenvsection:
            newitems = [(str(k), str(v))
                        for k, v in parser.items(self.progenvsection)]
            self.env = dict(list(self.env.items()) + newitems)
        progargs = opt_str('progargs', required=True)
        logtag = logtag or '.'
        # ... because passing a "-lt" switch with no parameter will make
        # CrateGatePipeline.java complain and stop
        self.env["NLPLOGTAG"] = logtag
        formatted_progargs = progargs.format(**self.env)
        self.progargs = formatted_progargs.split()

        # progressdb, hashphrase
        self.progdb = get_database(self.progressdb)
        self.hashphrase = opt_str('hashphrase', required=True)
        self.hasher = HashClass(self.hashphrase)

        # other
        self.now = get_now_utc_notz()

    def hash(self, text):
        return self.hasher.hash(text)

    def set_echo(self, echo):
        self.progdb.engine.echo = echo
        for db in self.databases.values():
            db.engine.echo = echo
        # Now, SQLAlchemy will mess things up by adding an additional handler.
        # So, bye-bye:
        for logname in ['sqlalchemy.engine.base.Engine',
                        'sqlalchemy.engine.base.OptionEngine']:
            logger = logging.getLogger(logname)
            logger.handlers = []


# =============================================================================
# Input support methods
# =============================================================================

def tsv_pairs_to_dict(line, key_lower=True):
    """
    Converts a TSV line into sequential key/value pairs as a dictionary.
    """
    items = line.split("\t")
    d = {}
    for chunk in chunks(items, 2):
        key = chunk[0]
        value = unescape_tabs_newlines(chunk[1])
        if key_lower:
            key = key.lower()
        d[key] = value
    return d


def escape_tabs_newlines(s):
    """
    Escapes CR, LF, tab, and backslashes. (Here just for testing; mirrors the
    equivalent function in the Java code.)
    """
    if not s:
        return s
    s = s.replace("\\", r"\\")  # replace \ with \\
    s = s.replace("\n", r"\n")  # escape \n; note ord("\n") == 10
    s = s.replace("\r", r"\r")  # escape \r; note ord("\r") == 13
    s = s.replace("\t", r"\t")  # escape \t; note ord("\t") == 9
    return s


def unescape_tabs_newlines(s):
    """
    Reverses escape_tabs_newlines.
    """
    # See also http://stackoverflow.com/questions/4020539
    if not s:
        return s
    d = ""  # the destination string
    in_escape = False
    for i in range(len(s)):
        c = s[i]  # the character being processed
        if in_escape:
            if c == "r":
                d += "\r"
            elif c == "n":
                d += "\n"
            elif c == "t":
                d += "\t"
            else:
                d += c
            in_escape = False
        else:
            if c == "\\":
                in_escape = True
            else:
                d += c
    return d


# =============================================================================
# Process handling
# =============================================================================
# Have Python host the client process, communicating with stdin/stdout?
#   http://eyalarubas.com/python-subproc-nonblock.html
#   http://stackoverflow.com/questions/2715847/python-read-streaming-input-from-subprocess-communicate  # noqa
# Java process could be a network server.
#   http://docs.oracle.com/javase/tutorial/networking/sockets/clientServer.html
#   http://www.tutorialspoint.com/java/java_networking.htm
# OK, first one works; that's easier.

class NlpController(object):
    """
    Class controlling the external process.
    """

    # -------------------------------------------------------------------------
    # Interprocess comms
    # -------------------------------------------------------------------------
    def __init__(self, progargs, input_terminator, output_terminator,
                 max_external_prog_uses, commit=False, encoding='utf8'):
        self.progargs = progargs
        self.input_terminator = input_terminator
        self.output_terminator = output_terminator
        self.max_external_prog_uses = max_external_prog_uses
        self.commit = commit
        self.starting_fields_values = {}
        self.n_uses = 0
        self.encoding = encoding
        self.p = None

    def start(self):
        """
        Launch the external process.
        """
        args = self.progargs
        log.info("launching command: " + " ".join(args))
        self.p = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            # stderr=subprocess.PIPE,
            shell=False,
            bufsize=1
        )
        # ... don't ask for stderr to be piped if you don't want it; firstly,
        # there's a risk that if you don't consume it, something hangs, and
        # secondly if you don't consume it, you see it on the console, which is
        # helpful.

    def _encode_to_subproc_stdin(self, text):
        log.debug("SENDING: " + text)
        bytes_ = text.encode(self.encoding)
        self.p.stdin.write(bytes_)

    def _flush_subproc_stdin(self):
        self.p.stdin.flush()

    def _decode_from_subproc_stdout(self):
        bytes_ = self.p.stdout.readline()
        text = bytes_.decode(self.encoding)
        log.debug("RECEIVING: " + text)
        return text

    def send(self, text, starting_fields_values=None):
        """
        Send text to the external process and receive the result.
        Associated data -- in starting_fields_values -- is kept in the Python
        environment, so we can't get any problems with garbling it to/from
        the Java program. All we send to the subprocess is the text (and an
        input_terminator). Then, we may receive MULTIPLE sets of data back
        ("your text contains the following 7 people/drug references/whatever"),
        followed eventually by the output_terminator, at which point this set
        is complete.
        """
        self.starting_fields_values = starting_fields_values or {}
        # Send
        log.debug("writing: " + text)
        self._encode_to_subproc_stdin(text)
        self._encode_to_subproc_stdin("\n")
        self._encode_to_subproc_stdin(self.input_terminator + "\n")
        self._flush_subproc_stdin()  # required in the Python 3 system
        # Receive
        for line in iter(self._decode_from_subproc_stdout,
                         self.output_terminator + "\n"):
            # ... iterate until the sentinel output_terminator is received
            line = line.rstrip()  # remove trailing newline
            log.debug("stdout received: " + line)
            self.receive(line)
        self.n_uses += 1
        # Restart subprocess?
        if 0 < self.max_external_prog_uses <= self.n_uses:
            log.info("relaunching app after {} uses".format(self.n_uses))
            self.finish()
            self.start()
            self.n_uses = 0

    def finish(self):
        """
        Close down the external process.
        """
        self.p.communicate()  # close p.stdout, wait for the subprocess to exit

    # -------------------------------------------------------------------------
    # Input processing
    # -------------------------------------------------------------------------

    @lru_cache(maxsize=None)
    def get_dest_info(self, annottype):
        annottype = annottype.lower()
        ok = False
        destfields = []
        session = None
        sqla_table = None
        if annottype not in config.outputtypemap.keys():
            log.warning(
                "Unknown annotation type, skipping: {}".format(annottype))
        else:
            ok = True
            ot = config.outputtypemap[annottype]
            session = config.databases[ot.destdb].session
            engine = config.databases[ot.destdb].engine
            sqla_table = get_dest_sqla_table(engine, ot)
            destfields = sqla_table.columns.keys()
        return ok, destfields, session, sqla_table

    def receive(self, line):
        """
        Receive a line from the external process and send the results to our
        database.
        """
        d = tsv_pairs_to_dict(line)
        log.debug("dictionary received: {}".format(d))
        # Merge dictionaries so EXISTING FIELDS/VALUES (starting_fields_values)
        # HAVE PRIORITY.
        d.update(self.starting_fields_values)
        log.debug("dictionary now: {}".format(d))
        try:
            annottype = d['_type']
        except KeyError:
            raise ValueError("_type information not in data received")
        ok, destfields, session, sqla_table = self.get_dest_info(annottype)
        if not ok:
            return
        # Restrict to fields we know about
        d = dict((k, d[k]) for k in destfields if k in d)
        insertquery = sqla_table.insert().values(d)
        session.execute(insertquery)
        if self.commit:
            session.commit()  # or we get deadlocks

    # -------------------------------------------------------------------------
    # Test
    # -------------------------------------------------------------------------

    def _test(self):
        """
        Test the send function.
        """
        datalist = [
            "Bob Hope visited Seattle.",
            "James Joyce wrote Ulysses."
        ]
        for i in range(len(datalist)):
            self.send(datalist[i], {"_item_number": i})


# =============================================================================
# Models
# =============================================================================

class NlpRecord(ProgressBase):
    __tablename__ = 'crate_nlp_progress'
    __table_args__ = MYSQL_TABLE_ARGS

    pk = Column(
        'pk', BigInteger, primary_key=True, autoincrement=True,
        doc="PK of NLP record (no specific use)")
    srcdb = Column(
        'srcdb', SqlTypeDb,
        doc="Source database")
    srctable = Column(
        'srctable', SqlTypeDb,
        doc="Source table name")
    srcpkfield = Column(
        'srcpkfield', SqlTypeDb,
        doc="Primary key column name in source table")
    srcpkval = Column(
        'srcpkval', BigInteger,
        doc="Primary key value in source table")
    srcfield = Column(
        'srcfield', SqlTypeDb,
        doc="Name of column in source field containing actual data")
    whenprocessedutc = Column(
        'whenprocessedutc', DateTime,
        doc="Time that NLP record was processed")
    srchash = Column(
        'srchash', SqlTypeHash,
        doc='Secure hash of source field contents')


@lru_cache(maxsize=None)
def get_dest_sqla_table(engine, otconfig):
    metadata = config.databases[otconfig.destdb].metadata
    columns = [
        Column('_pk', BigInteger, primary_key=True, autoincrement=True),
        Column('_srcdb', SqlTypeDb),
        Column('_srctable', SqlTypeDb),
        Column('_srcpkfield', SqlTypeDb),
        Column('_srcpkval', BigInteger),
        Column('_srcfield', SqlTypeDb),
    ]
    for i in range(len(otconfig.destfields)):
        colname = otconfig.destfields[i]
        datatype = get_sqla_coltype_from_dialect_str(
            engine, otconfig.dest_datatypes[i])
        col = Column(colname, datatype)
        columns.append(col)
    return Table(otconfig.desttable, metadata,
                 *columns, **MYSQL_TABLE_ARGS)


# =============================================================================
# Database queries
# =============================================================================

def get_progress_record(ifconfig, srcpkval, srchash=None):
    session = config.progdb.session
    query = (
        session.query(NlpRecord).
        filter(NlpRecord.srcdb == ifconfig.srcdb).
        filter(NlpRecord.srctable == ifconfig.srctable).
        filter(NlpRecord.srcpkfield == ifconfig.srcpkfield).
        filter(NlpRecord.srcpkval == srcpkval).
        filter(NlpRecord.srcfield == ifconfig.srcfield)
    )
    if srchash is not None:
        query = query.filter(NlpRecord.srchash == srchash)
    return query.one_or_none()


# =============================================================================
# Database operations
# =============================================================================

def insert_into_progress_db(ifconfig, srcpkval, srchash, commit=False):
    """
    Make a note in the progress database that we've processed a source record.
    """
    session = config.progdb.session
    progrec = get_progress_record(ifconfig, srcpkval, srchash=None)
    if progrec is None:
        progrec = NlpRecord(
            srcdb=ifconfig.srcdb,
            srctable=ifconfig.srctable,
            srcpkfield=ifconfig.srcpkfield,
            srcpkval=srcpkval,
            srcfield=ifconfig.srcfield,
            whenprocessedutc=config.now,
            srchash=srchash,
        )
        session.add(progrec)
    else:
        progrec.whenprocessedutc = config.now
        progrec.srchash = srchash
    if commit:
        session.commit()
    # Commit immediately, because other processes may need this table promptly.


def delete_where_no_source(ifconfig):
    """
    Delete destination records where source records no longer exist.

    - Can't do this in a single SQL command, since the engine can't necessarily
      see both databases.
    - Can't use a single temporary table, since the progress database isn't
      necessarily the same as any of the destination database(s).
    - Can't do this in a multiprocess way, because we're trying to do a
      DELETE WHERE NOT IN.
    """

    # 1. Progress database
    log.debug(
        "delete_where_no_source... {}.{} -> progressdb".format(
            ifconfig.srcdb,
            ifconfig.srctable,
        ))
    progsession = config.progdb.session
    src_pks = list(gen_src_pks(ifconfig))
    prog_deletion_query = (
        progsession.query(NlpRecord).
        filter(NlpRecord.srcdb == ifconfig.srcdb).
        filter(NlpRecord.srctable == ifconfig.srctable).
        filter(NlpRecord.srcpkfield == ifconfig.srcpkfield)
    )
    if src_pks:
        log.debug("... deleting selectively")
        prog_deletion_query = prog_deletion_query.filter(
            ~NlpRecord.srcpkval.in_(src_pks)
        )
    else:
        log.debug("... deleting all")
    progsession.execute(prog_deletion_query)

    # 2. Others. Combine in the same function as we re-use the source PKs.
    for otconfig in config.outputtypemap.values():
        log.debug(
            "delete_where_no_source... {}.{} -> {}.{}".format(
                ifconfig.srcdb,
                ifconfig.srctable,
                otconfig.destdb,
                otconfig.desttable,
            ))
        destsession = config.databases[otconfig.destdb].session
        destengine = config.databases[otconfig.destdb].engine
        desttable = get_dest_sqla_table(destengine, otconfig)
        # noinspection PyProtectedMember
        dest_deletion_query = (
            desttable.delete().
            where(desttable.c._srcdb == ifconfig.srcdb).
            where(desttable.c._srctable == ifconfig.srctable).
            where(desttable.c._srcpkfield == ifconfig.srcpkfield)
        )
        if src_pks:
            log.debug("... deleting selectively")
            # noinspection PyProtectedMember
            dest_deletion_query = dest_deletion_query.where(
                ~desttable.c._srcpkval.in_(src_pks)
            )
        else:
            log.debug("... deleting all")
        destsession.execute(dest_deletion_query)
        destsession.commit()

    # 3. Clean up.
    progsession.commit()


def delete_from_dest_dbs(ifconfig, srcpkval, commit=False):
    """
    For when a record has been updated; wipe older entries for it.
    """
    for otconfig in config.outputtypemap.values():
        log.debug(
            "delete_from_dest_dbs... {}.{} -> {}.{}".format(
                ifconfig.srcdb,
                ifconfig.srctable,
                otconfig.destdb,
                otconfig.desttable,
            ))
        destsession = config.databases[otconfig.destdb].session
        destengine = config.databases[otconfig.destdb].engine
        desttable = get_dest_sqla_table(destengine, otconfig)
        # noinspection PyProtectedMember
        delquery = (
            desttable.delete().
            where(desttable.c._srcdb == ifconfig.srcdb).
            where(desttable.c._srctable == ifconfig.srctable).
            where(desttable.c._srcpkfield == ifconfig.srcpkfield).
            where(desttable.c._srcpkval == srcpkval)
        )
        destsession.execute(delquery)
        if commit:
            destsession.commit()
        # ... or we get deadlocks
        # http://dev.mysql.com/doc/refman/5.5/en/innodb-deadlocks.html


def commit_all():
    """
    Execute a COMMIT on all databases.
    """
    config.progdb.session.commit()
    for db in config.databases.values():
        db.session.commit()


# =============================================================================
# Generators
# =============================================================================

def gen_src_pks(ifconfig):
    session = config.databases[ifconfig.srcdb].session
    query = (
        select([column(ifconfig.srcpkfield)]).
        select_from(table(ifconfig.srctable))
    )
    result = session.execute(query)
    for row in result:
        yield row[0]


def gen_text(ifconfig, tasknum=0, ntasks=1):
    """
    Generate text strings from the input database.
    Return value is: pk, text, copyfields...
    """
    if 1 < ntasks <= tasknum:
            raise Exception("Invalid tasknum {}; must be <{}".format(
                tasknum, ntasks))
    session = config.databases[ifconfig.srcdb].session
    pkcol = column(ifconfig.srcpkfield)
    selectcols = [pkcol, column(ifconfig.srcfield)]
    for extracol in ifconfig.copyfields:
        selectcols.append(column(extracol))
    query = (
        select(selectcols).
        select_from(table(ifconfig.srctable)).
        order_by(pkcol)
    )
    if ntasks > 1:
        query = query.where(func.mod(pkcol, ntasks) == tasknum)
    return session.execute(query)  # ... a generator itself


def get_count_max(ifconfig):
    """Used for progress monitoring"""
    session = config.databases[ifconfig.srcdb].session
    pkcol = column(ifconfig.srcpkfield)
    query = (
        select([func.count(), func.max(pkcol)]).
        select_from(table(ifconfig.srctable)).
        order_by(pkcol)
    )
    result = session.execute(query)
    return result.fetchone()  # count, maximum


# =============================================================================
# Core functions
# =============================================================================

def process_nlp(incremental=False, tasknum=0, ntasks=1):
    """
    Main NLP processing function. Fetch text, send it to the GATE app
    (storing the results), and make a note in the progress database.
    """
    log.info(SEP + "NLP")
    controller = NlpController(
        progargs=config.progargs,
        input_terminator=config.input_terminator,
        output_terminator=config.output_terminator,
        max_external_prog_uses=config.max_external_prog_uses,
        commit=incremental
    )
    controller.start()
    for ifconfig in config.inputfieldmap.values():
        count, maximum = get_count_max(ifconfig)
        for row in gen_text(ifconfig, tasknum=tasknum, ntasks=ntasks):
            pkval = row[0]
            text = row[1]
            copyvals = list(row[2:])
            fieldnames = [
                "_srcdb",
                "_srctable",
                "_srcpkfield",
                "_srcfield",
                "_srcpkval",
            ] + ifconfig.copyfields
            values = [
                ifconfig.srcdb,
                ifconfig.srctable,
                ifconfig.srcpkfield,
                ifconfig.srcfield,
                pkval,
            ] + copyvals
            log.info(
                "Processing {db}.{t}.{c}, {pkf}={pkv} "
                "(max={maximum}, n={count})".format(
                    db=ifconfig.srcdb,
                    t=ifconfig.srctable,
                    c=ifconfig.srcfield,
                    pkf=ifconfig.srcpkfield,
                    pkv=pkval,
                    maximum=maximum,
                    count=count,
                )
            )
            srchash = config.hash(text)
            if incremental:
                if get_progress_record(ifconfig, pkval, srchash) is not None:
                    log.debug("Record previously processed; skipping")
                    continue
            starting_fields_values = list(zip(fieldnames, values))
            if incremental:
                delete_from_dest_dbs(ifconfig, pkval,
                                     commit=incremental)
            controller.send(text, starting_fields_values)
            insert_into_progress_db(ifconfig, pkval, srchash,
                                    commit=incremental)
    controller.finish()
    commit_all()


def drop_remake(incremental=False):
    """
    Drop output tables and recreate them.
    """
    # Not parallel.
    # -------------------------------------------------------------------------
    # 1. Progress database
    # -------------------------------------------------------------------------
    progengine = config.progdb.engine
    if not incremental:
        log.debug("Dropping admin tables")
        NlpRecord.__table__.drop(progengine, checkfirst=True)
    log.info("Creating admin tables")
    NlpRecord.__table__.create(progengine, checkfirst=True)
    log.info("Creating admin indexes")
    idxname = '_idx1'
    if not index_exists(progengine, NlpRecord.__table__.name, idxname):
        index = Index(idxname,
                      NlpRecord.srcdb,
                      NlpRecord.srctable,
                      NlpRecord.srcpkfield,
                      NlpRecord.srcpkval,
                      NlpRecord.srcfield,
                      unique=True)
        index.create(progengine)

    # -------------------------------------------------------------------------
    # 2. Output database(s)
    # -------------------------------------------------------------------------
    for otconfig in config.outputtypemap.values():
        destengine = config.databases[otconfig.destdb].engine
        sqla_table = get_dest_sqla_table(destengine, otconfig)
        if not incremental:
            log.info("dropping table {}".format(sqla_table.name))
            sqla_table.drop(destengine, checkfirst=True)
        log.info("creating table {}".format(sqla_table.name))
        sqla_table.create(destengine, checkfirst=True)

    # -------------------------------------------------------------------------
    # 3. Delete WHERE NOT IN for incremental
    # -------------------------------------------------------------------------
    if incremental:
        for ifconfig in config.inputfieldmap.values():
            delete_where_no_source(ifconfig)

    # -------------------------------------------------------------------------
    # 4. Overall commit
    # -------------------------------------------------------------------------
    commit_all()


def create_indexes(tasknum=0, ntasks=1):
    """
    Create indexes on destination table(s).
    """
    # Parallelize by table.
    log.info(SEP + "Create indexes")
    outputtypes_list = list(config.outputtypemap.values())
    for i in range(len(outputtypes_list)):
        if i % ntasks != tasknum:
            continue
        ot = outputtypes_list[i]
        if not ot.indexfields:
            continue
        engine = config.databases[ot.destdb].engine
        sqla_table = get_dest_sqla_table(engine, ot)
        # Default indexes for most mandatory fields
        add_index(engine, sqla_table.columns['_srcdb'],
                  unique=False, length=MAX_SQL_FIELD_LEN)
        add_index(engine, sqla_table.columns['_srctable'],
                  unique=False, length=MAX_SQL_FIELD_LEN)
        add_index(engine, sqla_table.columns['_srcpkfield'],
                  unique=False, length=MAX_SQL_FIELD_LEN)
        add_index(engine, sqla_table.columns['_srcpkval'],
                  unique=False, length=None)
        for j in range(len(ot.indexfields)):
            add_index(engine, sqla_table.columns[ot.indexfields[j]],
                      unique=False, fulltext=False,
                      length=ot.indexlengths[j])


# =============================================================================
# Main
# =============================================================================

def main():
    """
    Command-line entry point.
    """
    version = "Version {} ({})".format(VERSION, VERSION_DATE)
    description = """
NLP manager. {version}. By Rudolf Cardinal.""".format(version=version)

    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-n", "--version", action="version", version=version)
    parser.add_argument('--verbose', '-v', action='count', default=0,
                        help="Be verbose (use twice for extra verbosity)")
    parser.add_argument("nlpname",
                        help="NLP definition name (from config file)")
    parser.add_argument("--process", nargs="?", type=int, default=0,
                        help="For multiprocess patient-table mode: specify "
                             "process number")
    parser.add_argument("--nprocesses", nargs="?", type=int, default=1,
                        help="For multiprocess patient-table mode: specify "
                             "total number of processes (launched somehow, of "
                             "which this is to be one)")
    parser.add_argument("--processcluster", default="",
                        help="Process cluster name")
    parser.add_argument("--democonfig", action="store_true",
                        help="Print a demo config file")
    parser.add_argument("--incremental", action="store_true",
                        help="Process only new/changed information, where "
                             "possible")
    parser.add_argument("--full",
                        dest="incremental", action="store_false",
                        help="Drop and remake everything")
    parser.set_defaults(incremental=True)
    parser.add_argument("--dropremake", action="store_true",
                        help="Drop/remake destination tables only")
    parser.add_argument("--nlp", action="store_true",
                        help="Perform NLP processing only")
    parser.add_argument("--index", action="store_true",
                        help="Create indexes only")
    parser.add_argument("--echo", action="store_true",
                        help="Echo SQL")
    args = parser.parse_args()

    # Demo config?
    if args.democonfig:
        print(DEMO_CONFIG)
        return

    # Validate args
    if args.nprocesses < 1:
        raise ValueError("--nprocesses must be >=1")
    if args.process < 0 or args.process >= args.nprocesses:
        raise ValueError(
            "--process argument must be from 0 to (nprocesses - 1) inclusive")

    everything = not any([args.dropremake, args.nlp, args.index])

    # -------------------------------------------------------------------------

    # Verbosity
    mynames = []
    if args.processcluster:
        mynames.append(args.processcluster)
    if args.nprocesses > 1:
        mynames.append("proc{}".format(args.process))
    loglevel = logging.DEBUG if args.verbose >= 1 else logging.INFO
    rootlogger = logging.getLogger()
    configure_logger_for_colour(rootlogger, level=loglevel, extranames=mynames)

    # Report args
    log.debug("arguments: {}".format(args))

    # Load/validate config
    global config
    config = Config(args.nlpname,
                    logtag="_".join(mynames).replace(" ", "_"))
    config.set_echo(args.echo)

    # -------------------------------------------------------------------------

    log.info("Starting")
    start = get_now_utc()

    # 1. Drop/remake tables. Single-tasking only.
    if args.dropremake or everything:
        drop_remake(incremental=args.incremental)

    # 2. NLP
    if args.nlp or everything:
        process_nlp(incremental=args.incremental,
                    tasknum=args.process, ntasks=args.nprocesses)

    # 3. Indexes.
    if args.index or everything:
        create_indexes(tasknum=args.process, ntasks=args.nprocesses)

    log.info("Finished")
    end = get_now_utc()
    time_taken = end - start
    log.info("Time taken: {} seconds".format(time_taken.total_seconds()))


# =============================================================================
# Config singleton (set in main)
# =============================================================================

config = None

# =============================================================================
# Command-line entry point
# =============================================================================

if __name__ == '__main__':
    main()
