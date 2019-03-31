#!/usr/bin/env python

"""
crate_anon/nlp_manager/parse_gate.py

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

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

**NLP handler for external GATE NLP tools.**

The pipe encoding (Python -> Java stdin, Java stdout -> Python) is fixed to be
UTF-8, here and in the Java code.

"""

import logging
import os
import shlex
import subprocess
import sys
from typing import Any, Dict, Generator, List, TextIO, Tuple

from cardinal_pythonlib.dicts import (
    rename_keys_in_dict,
    set_null_values_in_dict,
)
from cardinal_pythonlib.lists import chunks
from cardinal_pythonlib.tsv import tsv_pairs_to_dict
from sqlalchemy import Column, Index, Integer, Text

from crate_anon.nlp_manager.base_nlp_parser import BaseNlpParser
from crate_anon.nlp_manager.constants import (
    MAX_SQL_FIELD_LEN,
    SqlTypeDbIdentifier,
)
from crate_anon.nlp_manager.nlp_definition import (
    full_sectionname,
    NlpConfigPrefixes,
    NlpDefinition,
)
from crate_anon.nlp_manager.output_user_config import OutputUserConfig

log = logging.getLogger(__name__)

# These match KEY_* strings in CrateGatePipeline.java:
FN_SET = '_set'
FN_TYPE = '_type'
FN_ID = '_id'
FN_STARTPOS = '_start'
FN_ENDPOS = '_end'
FN_CONTENT = '_content'


class GateConfigKeys(object):
    MAX_EXTERNAL_PROG_USES = "max_external_prog_uses"
    INPUT_TERMINATOR = "input_terminator"
    OUTPUT_TERMINATOR = "output_terminator"
    OUTPUTTYPEMAP = "outputtypemap"
    PROGENVSECTION = "progenvsection"
    PROGARGS = "progargs"


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
    """
    Class controlling an external process, typically our Java interface to
    GATE programs, ``CrateGatePipeline.java`` (but it could be any external
    program).

    We send text to it, it parses the text, and it sends us back results, which
    we return as dictionaries. The specific text sought depends on the
    configuration file and the specific GATE program used.

    Notes:

    - PROBLEM when attempting to use KConnect (Bio-YODIE): its source code is
      full of direct calls to ``System.out.println()``.

      POTENTIAL SOLUTIONS:

      - named pipes:

        - ``os.mkfifo()`` - Unix only.
        - ``win32pipe`` - http://stackoverflow.com/questions/286614

      - ZeroMQ with some sort of security

        - ``pip install zmq``
        - some sort of Java binding (``jzmq``, ``jeromq``...)

      - redirect ``stdout`` in our Java handler

        - ``System.setOut()``... yes, that works.
        - Implemented and exposed as ``--suppress_gate_stdout``.

    """
    NAME = "GATE"

    def __init__(self,
                 nlpdef: NlpDefinition,
                 cfgsection: str,
                 commit: bool = False) -> None:
        """
        Args:
            nlpdef:
                a :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
            cfgsection:
                the name of a CRATE NLP config file section (from which we may
                choose to get extra config information)
            commit:
                force a COMMIT whenever we insert data? You should specify this
                in multiprocess mode, or you may get database deadlocks.
        """
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
                self._sectionname, GateConfigKeys.MAX_EXTERNAL_PROG_USES,
                default=0)
            self._input_terminator = nlpdef.opt_str(
                self._sectionname, GateConfigKeys.INPUT_TERMINATOR,
                required=True)
            self._output_terminator = nlpdef.opt_str(
                self._sectionname, GateConfigKeys.OUTPUT_TERMINATOR,
                required=True)
            typepairs = nlpdef.opt_strlist(
                self._sectionname, GateConfigKeys.OUTPUTTYPEMAP,
                required=True, lower=False)
            self._progenvsection = nlpdef.opt_str(
                self._sectionname, GateConfigKeys.PROGENVSECTION)
            progargs = nlpdef.opt_str(
                self._sectionname, GateConfigKeys.PROGARGS,
                required=True)
            logtag = nlpdef.get_logtag() or '.'

        self._outputtypemap = {}  # type: Dict[str, OutputUserConfig]
        self._type_to_tablename = {}  # type: Dict[str, str]
        for c in chunks(typepairs, 2):
            annottype = c[0]
            outputsection = c[1]
            # 2018-03-27: not clear why we need to force the user to specify
            # in lower case! We just said it's case-insensitive. So ditch this:
            #
            # if annottype != annottype.lower():
            #     raise Exception(
            #         "Section {}: annotation types in outputtypemap must be in "  # noqa
            #         "lower case: change {}".format(cfgsection, annottype))
            #
            # and add this:
            annottype = annottype.lower()
            # log.critical(outputsection)
            c = OutputUserConfig(nlpdef.get_parser(), outputsection)
            self._outputtypemap[annottype] = c
            self._type_to_tablename[annottype] = c.get_tablename()

        if self._progenvsection:
            self._env = nlpdef.get_env_dict(
                full_sectionname(NlpConfigPrefixes.ENV,
                                 self._progenvsection),
                os.environ)
        else:
            self._env = os.environ.copy()
        self._env["NLPLOGTAG"] = logtag
        # ... We have ensured that this is not empty for real use, because
        # passing a "-lt" switch with no parameter will make
        # CrateGatePipeline.java complain and stop. The environment variable
        # is read via the "progargs" config argument, as follows.

        formatted_progargs = progargs.format(**self._env)
        self._progargs = shlex.split(formatted_progargs)

        self._n_uses = 0
        self._pipe_encoding = 'utf8'
        self._p = None  # the subprocess
        self._started = False

        # Sanity checks
        for ty, tn in self._type_to_tablename.items():
            assert len(tn) <= MAX_SQL_FIELD_LEN, (
                f"Table name too long (max {MAX_SQL_FIELD_LEN} characters)")

    @classmethod
    def print_info(cls, file: TextIO = sys.stdout) -> None:
        # docstring in superclass
        print("NLP class to talk to GATE apps (https://www.gate.ac.uk/).",
              file=file)

    # -------------------------------------------------------------------------
    # External process control
    # -------------------------------------------------------------------------

    def _start(self) -> None:
        """
        Launch the external process, with stdin/stdout connections to it.
        """
        if self._started:
            return
        args = self._progargs
        log.info(f"launching command: {args}")
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
        """
        Send text to the external program (via its stdin), encoding it in the
        process (typically to UTF-8).
        """
        log.debug("SENDING: " + text)
        bytes_ = text.encode(self._pipe_encoding)
        self._p.stdin.write(bytes_)

    def _flush_subproc_stdin(self) -> None:
        """
        Flushes what we're sending to the external program via its stdin.
        """
        self._p.stdin.flush()

    def _decode_from_subproc_stdout(self) -> str:
        """
        Decode what we've received from the external program's stdout, from its
        specific encoding (usually UTF-8) to a Python string.
        """
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
            log.debug(f"dictionary received: {d}")
            try:
                annottype = d['_type'].lower()
            except KeyError:
                raise ValueError("_type information not in data received")
            if annottype not in self._type_to_tablename:
                log.warning(
                    f"Unknown annotation type, skipping: {annottype}")
                continue
            c = self._outputtypemap[annottype]
            rename_keys_in_dict(d, c.renames())
            set_null_values_in_dict(d, c.null_literals())
            yield self._type_to_tablename[annottype], d

        self._n_uses += 1
        # Restart subprocess?
        if 0 < self._max_external_prog_uses <= self._n_uses:
            log.info(f"relaunching app after {self._n_uses} uses")
            self._finish()
            self._start()
            self._n_uses = 0

    # -------------------------------------------------------------------------
    # Test
    # -------------------------------------------------------------------------

    def test(self, verbose: bool = False) -> None:
        """
        Test the :func:`send` function.
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
        """
        Returns standard columns for GATE output.
        """
        return [
            Column(FN_SET, SqlTypeDbIdentifier,
                   doc="GATE output set name"),
            Column(FN_TYPE, SqlTypeDbIdentifier,
                   doc="GATE annotation type name"),
            Column(FN_ID, Integer,
                   doc="GATE annotation ID (not clear this is very useful)"),
            Column(FN_STARTPOS, Integer,
                   doc="Start position in the content"),
            Column(FN_ENDPOS, Integer,
                   doc="End position in the content"),
            Column(FN_CONTENT, Text,
                   doc="Full content marked as relevant."),
        ]

    @staticmethod
    def _standard_indexes() -> List[Index]:
        """
        Returns standard indexes for GATE output.
        """
        return [
            Index('_idx__set', FN_SET, mysql_length=MAX_SQL_FIELD_LEN),
        ]

    def dest_tables_columns(self) -> Dict[str, List[Column]]:
        # docstring in superclass
        tables = {}  # type: Dict[str, List[Column]]
        for anottype, otconfig in self._outputtypemap.items():
            tables[otconfig.get_tablename()] = (
                self._standard_columns() +
                otconfig.get_columns(self.get_engine())
            )
        return tables

    def dest_tables_indexes(self) -> Dict[str, List[Index]]:
        # docstring in superclass
        tables = {}  # type: Dict[str, List[Index]]
        for anottype, otconfig in self._outputtypemap.items():
            tables[otconfig.get_tablename()] = (
                self._standard_indexes() +
                otconfig.get_indexes()
            )
        return tables
