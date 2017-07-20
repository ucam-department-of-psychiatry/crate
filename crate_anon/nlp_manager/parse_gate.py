#!/usr/bin/env python
# crate_anon/nlp_manager/parse_gate.py

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

The pipe encoding (Python -> Java stdin, Java stdout -> Python) is fixed at
UTF-8 here and in the Java code.

"""

import logging
import os
import shlex
import subprocess
import sys
from typing import Any, Dict, Generator, List, Tuple

from cardinal_pythonlib.rnc_lang import chunks
from sqlalchemy import Column, Index, Integer, Text

from crate_anon.common.lang import rename_keys_in_dict, set_null_values_in_dict
from crate_anon.nlp_manager.base_nlp_parser import BaseNlpParser
from crate_anon.nlp_manager.constants import (
    MAX_SQL_FIELD_LEN,
    SqlTypeDbIdentifier,
)
from crate_anon.nlp_manager.nlp_definition import NlpDefinition
from crate_anon.nlp_manager.output_user_config import OutputUserConfig
from crate_anon.nlp_manager.text_handling import tsv_pairs_to_dict

log = logging.getLogger(__name__)


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

class Gate(BaseNlpParser):
    """Class controlling an external process, typically our Java interface to
    GATE programs, CrateGatePipeline.java (but it could be any external
    program).

    We send text to it, it parses the text, and it sends us back results, which
    we return as dictionaries. The specific text sought depends on the
    configuration file and the specific GATE program used.

    PROBLEM when attempting to use KConnect (Bio-YODIE): its source code is
    full of direct calls to System.out.println().

    POTENTIAL SOLUTIONS
    - named pipes:
        os.mkfifo() - Unix only.
        win32pipe - http://stackoverflow.com/questions/286614
    - ZeroMQ with some sort of security
        - pip install zmq
        - some sort of Java binding (jzmq, jeromq...)
    - redirect stdout in our Java handler
        System.setOut()
        ... yes, that works.
    """
    NAME = "GATE"

    def __init__(self,
                 nlpdef: NlpDefinition,
                 cfgsection: str,
                 commit: bool = False) -> None:
        super().__init__(nlpdef=nlpdef, cfgsection=cfgsection, commit=commit)

        if not nlpdef and not cfgsection:
            # Debugging only
            self._max_external_prog_uses = 0
            self._input_terminator = 'input_terminator'
            self._output_terminator = 'output_terminator'
            typepairs = []  # type: List[str]
            self._progenvsection = ''
            progargs = ''
            logtag = ''
        else:
            self._max_external_prog_uses = nlpdef.opt_int(
                cfgsection, 'max_external_prog_uses', default=0)
            self._input_terminator = nlpdef.opt_str(
                cfgsection, 'input_terminator', required=True)
            self._output_terminator = nlpdef.opt_str(
                cfgsection, 'output_terminator', required=True)
            typepairs = nlpdef.opt_strlist(cfgsection, 'outputtypemap',
                                           required=True, lower=False)
            self._progenvsection = nlpdef.opt_str(cfgsection, 'progenvsection')
            progargs = nlpdef.opt_str(cfgsection, 'progargs', required=True)
            logtag = nlpdef.get_logtag() or '.'

        self._outputtypemap = {}  # type: Dict[str, OutputUserConfig]
        self._type_to_tablename = {}  # type: Dict[str, str]
        for c in chunks(typepairs, 2):
            annottype = c[0]
            outputsection = c[1]
            if annottype != annottype.lower():
                raise Exception(
                    "Section {}: annotation types in outputtypemap must be in "
                    "lower case: change {}".format(cfgsection, annottype))
            # log.critical(outputsection)
            c = OutputUserConfig(nlpdef.get_parser(), outputsection)
            self._outputtypemap[annottype] = c
            self._type_to_tablename[annottype] = c.get_tablename()

        if self._progenvsection:
            self._env = nlpdef.get_env_dict(self._progenvsection, os.environ)
        else:
            self._env = os.environ.copy()
        self._env["NLPLOGTAG"] = logtag
        # ... because passing a "-lt" switch with no parameter will make
        # CrateGatePipeline.java complain and stop

        formatted_progargs = progargs.format(**self._env)
        self._progargs = shlex.split(formatted_progargs)

        self._n_uses = 0
        self._pipe_encoding = 'utf8'
        self._p = None  # the subprocess
        self._started = False

        # Sanity checks
        for ty, tn in self._type_to_tablename.items():
            assert len(tn) <= MAX_SQL_FIELD_LEN, (
                "Table name too long (max {} characters)".format(
                    MAX_SQL_FIELD_LEN))

    @classmethod
    def print_info(cls, file=sys.stdout):
        print("NLP class to talk to GATE apps (https://www.gate.ac.uk/).",
              file=file)

    # -------------------------------------------------------------------------
    # External process control
    # -------------------------------------------------------------------------

    def _start(self) -> None:
        """
        Launch the external process.
        """
        if self._started:
            return
        args = self._progargs
        log.info("launching command: {}".format(args))
        self._p = subprocess.Popen(args,
                                   stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE,
                                   # stderr=subprocess.PIPE,
                                   shell=False,
                                   bufsize=1)
        # ... don't ask for stderr to be piped if you don't want it; firstly,
        # there's a risk that if you don't consume it, something hangs, and
        # secondly if you don't consume it, you see it on the console, which is
        # helpful.
        self._started = True

    def _encode_to_subproc_stdin(self, text: str) -> None:
        """Send text to the external program (via its stdin), encoding it in
        the process (typically to UTF-8)."""
        log.debug("SENDING: " + text)
        bytes_ = text.encode(self._pipe_encoding)
        self._p.stdin.write(bytes_)

    def _flush_subproc_stdin(self) -> None:
        """Flushes what we're sending to the external program via its stdin."""
        self._p.stdin.flush()

    def _decode_from_subproc_stdout(self) -> str:
        """Translate what we've received from the external program's stdout,
        from its specific encoding (usually UTF-8) to a Python string."""
        bytes_ = self._p.stdout.readline()
        text = bytes_.decode(self._pipe_encoding)
        log.debug("RECEIVING: " + repr(text))
        return text

    def _finish(self) -> None:
        """
        Close down the external process.
        """
        if not self._started:
            return
        self._p.communicate()  # close p.stdout, wait for the subprocess to exit
        self._started = False

    # -------------------------------------------------------------------------
    # Input processing
    # -------------------------------------------------------------------------

    def parse(self, text: str) -> Generator[Tuple[str, Dict[str, Any]],
                                            None, None]:
        """
        - Send text to the external process, and receive the result.
        - Note that associated data is not passed into this function, and is
          kept in the Python environment, so we can't run into any problems
          with the transfer to/from the Java program garbling important data.
          All we send to the subprocess is the text (and an input_terminator).
          Then, we may receive MULTIPLE sets of data back ("your text contains
          the following 7 people/drug references/whatever"), followed
          eventually by the output_terminator, at which point this set is
          complete.
        """
        self._start()  # ensure started
        # Send
        log.debug("writing: " + text)
        self._encode_to_subproc_stdin(text)
        self._encode_to_subproc_stdin(os.linesep)
        self._encode_to_subproc_stdin(self._input_terminator + os.linesep)
        self._flush_subproc_stdin()  # required in the Python 3 system

        # Receive
        for line in iter(self._decode_from_subproc_stdout,
                         self._output_terminator + os.linesep):
            # ... iterate until the sentinel output_terminator is received
            line = line.rstrip()  # remove trailing newline
            log.debug("stdout received: " + line)
            d = tsv_pairs_to_dict(line)
            log.debug("dictionary received: {}".format(d))
            try:
                annottype = d['_type'].lower()
            except KeyError:
                raise ValueError("_type information not in data received")
            if annottype not in self._type_to_tablename:
                log.warning(
                    "Unknown annotation type, skipping: {}".format(annottype))
                continue
            c = self._outputtypemap[annottype]
            rename_keys_in_dict(d, c.renames())
            set_null_values_in_dict(d, c.null_literals())
            yield self._type_to_tablename[annottype], d

        self._n_uses += 1
        # Restart subprocess?
        if 0 < self._max_external_prog_uses <= self._n_uses:
            log.info("relaunching app after {} uses".format(self._n_uses))
            self._finish()
            self._start()
            self._n_uses = 0

    # -------------------------------------------------------------------------
    # Test
    # -------------------------------------------------------------------------

    def test(self, verbose: bool=False) -> None:
        """
        Test the send function.
        """
        self.test_parser([
            "Bob Hope visited Seattle.",
            "James Joyce wrote Ulysses."
        ])

    # -------------------------------------------------------------------------
    # Database structure
    # -------------------------------------------------------------------------

    @staticmethod
    def _standard_columns() -> List[Column]:
        return [
            Column('_set', SqlTypeDbIdentifier,
                   doc="GATE output set name"),
            Column('_type', SqlTypeDbIdentifier,
                   doc="GATE annotation type name"),
            Column('_id', Integer,
                   doc="GATE annotation ID (not clear this is very useful)"),
            Column('_start', Integer,
                   doc="Start position in the content"),
            Column('_end', Integer,
                   doc="End position in the content"),
            Column('_content', Text,
                   doc="Full content marked as relevant."),
        ]

    @staticmethod
    def _standard_indexes() -> List[Index]:
        return [
            Index('_idx__set', '_set', mysql_length=MAX_SQL_FIELD_LEN),
        ]

    def dest_tables_columns(self) -> Dict[str, List[Column]]:
        tables = {}  # type: Dict[str, List[Column]]
        for anottype, otconfig in self._outputtypemap.items():
            tables[otconfig.get_tablename()] = (
                self._standard_columns() +
                otconfig.get_columns(self.get_engine())
            )
        return tables

    def dest_tables_indexes(self) -> Dict[str, List[Index]]:
        tables = {}  # type: Dict[str, List[Index]]
        for anottype, otconfig in self._outputtypemap.items():
            tables[otconfig.get_tablename()] = (
                self._standard_indexes() +
                otconfig.get_indexes()
            )
        return tables
