r"""
crate_anon/nlp_manager/parse_medex.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

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
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

**NLP handler for the external MedEx-UIMA tool, to find references to
drugs (medication.**

- MedEx-UIMA

  - can't find Python version of MedEx (which preceded MedEx-UIMA)
  - paper on Python version is
    https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2995636/; uses Python NLTK
  - see notes in Documents/CRATE directory
  - MedEx-UIMA is in Java, and resolutely uses a file-based processing system;
    ``Main.java`` calls ``MedTagger.java`` (``MedTagger.run_batch_medtag``),
    and even in its core ``MedTagger.medtagging()`` function it's making files
    in directories; that's deep in the core of its NLP thinking so we can't
    change that behaviour without creating a fork. So the obvious way to turn
    this into a proper "live" pipeline would be for the calling code to

    - fire up a receiving process - Python launching custom Java
    - create its own temporary directory - Python
    - receive data - Python
    - stash it on disk - Python
    - call the MedEx function - Python -> stdout -> custom Java -> MedEx
    - return the results - custom Java signals "done" -> Python reads stdin?
    - and clean up - Python

    Not terribly elegant, but might be fast enough (and almost certainly much
    faster than reloading Java regularly!).

  - output comes from its ``MedTagger.print_result()`` function
  - would need a per-process-unique temporary directory, since it scans all
    files in the input directory (and similarly one output directory); would do
    that in Python

MedEx-UIMA is firmly (and internally) wedded to a file-based processing
system. So we need to:

- create a process-specific pair of temporary directories;
- fire up a receiving process
- pass data (1) to file and (2) signal that there's data available;
- await a "data ready" reply and read the data from disk;
- clean up (delete files) in readiness for next data chunk.

NOTE ALSO that MedEx's ``MedTagger`` class writes to ``stdout`` (though not
``stderr``). Option 1: move our logs to ``stdout`` and use ``stderr`` for
signalling. Option 2: keep things as they are and just use a ``stdout`` signal
that's not used by MedEx. Went with option 2; simpler and more consistent esp.
for logging.

How do we clean up the temporary directories?

- ``__del__`` is not the opposite of ``__init__``;
  https://www.algorithm.co.il/blogs/programming/python-gotchas-1-__del__-is-not-the-opposite-of-__init__/
- https://eli.thegreenplace.net/2009/06/12/safely-using-destructors-in-python

PROBLEMS:

- NLP works fine, but UK-style abbreviations e.g. "qds" not recognized where
  "q.i.d." is. US abbreviations: e.g.
  https://www.d.umn.edu/medweb/Modules/Prescription/Abbreviations.html

  - Places to look, and things to try adding:

    .. code-block:: none

        resources/TIMEX/norm_patterns/NormFREQword

            qds=>R1P6H

        resources/TIMEX/rules/frequency_rules

            //QID ( 4 times a day
            expression="[Qq]\.?[Ii]\.?[Dd]\.?[ ]*\((.*?)\)",val="R1P6H"

            // RNC: qds
            expression="[Qq]\.?[Dd]\.?[Ss]\.?[ ]*\((.*?)\)",val="R1P6H"

        ... looked like it was correct, but not working
        ... are this files compiled in, rather than being read live?
        ... do I have the user or the developer version?

    ... not there yet.
    Probably need to recompile. See MedEx's Readme.txt

  - reference to expression/val (as in frequency_rules):

    .. code-block:: none

        TIMEX.Rule._add_rule()
            ... from TIMEX.Rule.Rule via a directory walker
            ... from TIMEX.ProcessingEngine.ProcessingEngine()
                ... via semi-hardcoded file location relative to class's location
                    ... via rule_dir, set to .../TIMEX/rules

  - Detect a file being accessed:

    .. code-block:: bash

        sudo apt install inotify-tools
        inotifywait -m FILE

    ... frequency_rules IS opened.

  - OVERALL SEQUENCE:

    .. code-block:: none

        org.apache.medex.Main [OR: CrateNedexPipeline.java]
        org.apache.medex.MedTagger.run_batch_medtag
        ... creeates an org.apache.NLPTools.Document
            ... not obviously doing frequency stuff, or drug recognition
        ... then runs org.apache.medex.MedTagger.medtagging(doc)
            ... this does most of the heavy lifting, I think
            ... uses ProcessingEngine freq_norm_engine
                ... org.apache.TIMEX.ProcessingEngine
                ... but it may be that this just does frequency NORMALIZATION, not frequency finding
            ... uses SemanticRuleEngine rule_engine
                ... which is org.apache.medex.SemanticRuleEngine
                ... see all the regexlist.put(..., "FREQ") calls
                ... note double-escaping \\ for Java's benefit

- Rebuilding MedEx:

  .. code-block:; bash

    export MEDEX_DIR=~/dev/MedEx_UIMA_1.3.6  # or similar
    cd ${MEDEX_DIR}
    # OPTIONAL # find . -name "*.class" -exec rm {} \;  # remove old compiled files
    javac \
        -classpath "${MEDEX_DIR}/src:${MEDEX_DIR}/lib/*" \
        src/org/apache/medex/Main.java \
        -d bin

    # ... will also compile dependencies

  See build_medex_itself.py

- YES. If you add to ``org.apache.medex.SemanticRuleEngine``, with extra
  entries in the ``regexlist.put(...)`` sequence, new frequencies appear in the
  output.

  To get them normalized as well, add them to frequency_rules.

  Specifics:

  (a) SemanticRuleEngine.java

      .. code-block:: java

        // EXTRA FOR UK FREQUENCIES (see https://www.evidence.nhs.uk/formulary/bnf/current/general-reference/latin-abbreviations)
        // NB case-insensitive regexes in SemanticRuleEngine.java, so ignore case here
        regexlist.put("^(q\\.?q\\.?h\\.?)( |$)", "FREQ");  // qqh, quarta quaque hora (RNC)
        regexlist.put("^(q\\.?d\\.?s\\.?)( |$)", "FREQ");  // qds, quater die sumendum (RNC); must go before existing competing expression: regexlist.put("^q(\\.|)\\d+( |$)","FREQ");
        regexlist.put("^(t\\.?d\\.?s\\.?)( |$)", "FREQ");  // tds, ter die sumendum (RNC)
        regexlist.put("^(b\\.?d\\.?)( |$)", "FREQ");  // bd, bis die (RNC)
        regexlist.put("^(o\\.?d\\.?)( |$)", "FREQ");  // od, omni die (RNC)
        regexlist.put("^(mane)( |$)", "FREQ");  // mane (RNC)
        regexlist.put("^(o\\.?m\\.?)( |$)", "FREQ");  // om, omni mane (RNC)
        regexlist.put("^(nocte)( |$)", "FREQ");  // nocte (RNC)
        regexlist.put("^(o\\.?n\\.?)( |$)", "FREQ");  // on, omni nocte (RNC)
        regexlist.put("^(fortnightly)( |$)", "FREQ");  // fortnightly (RNC)
        regexlist.put("^((?:2|two)\s+weekly)\b", "FREQ");  // fortnightly (RNC)
        regexlist.put("argh", "FREQ");  // fortnightly (RNC)
        // ALREADY IMPLEMENTED BY MedEx: tid (ter in die)
        // NECESSITY, NOT FREQUENCY: prn (pro re nata)
        // TIMING, NOT FREQUENCY: ac (ante cibum); pc (post cibum)

  (b) frequency_rules

      .. code-block:: none

        // EXTRA FOR UK FREQUENCIES (see https://www.evidence.nhs.uk/formulary/bnf/current/general-reference/latin-abbreviations)
        // NB case-sensitive regexes in Rule.java, so offer upper- and lower-case alternatives here
        // qqh, quarta quaque hora (RNC)
        expression="\b[Qq]\.?[Qq]\.?[Hh]\.?\b",val="R1P4H"
        // qds, quater die sumendum (RNC); MUST BE BEFORE COMPETING "qd" (= per day) expression: expression="[Qq]\.?[ ]?[Dd]\.?",val="R1P24H"
        expression="\b[Qq]\.?[Dd]\.?[Ss]\.?\b",val="R1P6H"
        // tds, ter die sumendum (RNC)
        expression="\b[Tt]\.?[Dd]\.?[Ss]\.?\b",val="R1P8H"
        // bd, bis die (RNC)
        expression="\b[Bb]\.?[Dd]\.?\b",val="R1P12H"
        // od, omni die (RNC)
        expression="\b[Oo]\.?[Dd]\.?\b",val="R1P24H"
        // mane (RNC)
        expression="\b[Mm][Aa][Nn][Ee]\b",val="R1P24H"
        // om, omni mane (RNC)
        expression="\b[Oo]\.?[Mm]\.?\b",val="R1P24H"
        // nocte (RNC)
        expression="\b[Nn][Oo][Cc][Tt][Ee]\b",val="R1P24H"
        // on, omni nocte (RNC)
        expression="\b[Oo]\.?[Nn]\.?\b",val="R1P24H"
        // fortnightly and variants (RNC); unsure if TIMEX3 format is right
        expression="\b[Ff][Oo][Rr][Tt][Nn][Ii][Gg][Hh][Tt][Ll][Yy]\b",val="R1P2WEEK"
        expression="\b(?:2|[Tt][Ww][Oo])\s+[Ww][Ee][Ee][Kk][Ll][Yy]\b",val="R1P2WEEK"
        // monthly (RNC)
        expression="\b[Mm][Oo][Nn][Tt][Hh][Ll][Yy]\b",val="R1P1MONTH"
        //
        // ALREADY IMPLEMENTED BY MedEx: tid (ter in die)
        // NECESSITY, NOT FREQUENCY: prn (pro re nata)
        // TIMING, NOT FREQUENCY: ac (ante cibum); pc (post cibum)

  (c) source:

      - https://www.evidence.nhs.uk/formulary/bnf/current/general-reference/latin-abbreviations

- How about routes of administration?

  .. code-block:: none

        MedTagger.printResult()
            route is in FStr_list[5]
        ... called from MedTagger.medtagging()
            route is in FStr_list_final[5]
            before that, is in FStr (separated by \n)
                ... from formatDruglist
                ...
                ... from logs, appears first next to "input for tagger" at
                    which point it's in
                        sent_token_array[j] (e.g. "po")
                        sent_tag_array[j] (e.g. "RUT" = route)
                ... from tag_dict
                ... from filter_tags
                ... from (Document) doc.filtered_drug_tag()
                ...
                ... ?from MedTagger.medtagging() calling doc.add_drug_tag()
                ... no, not really; is in this bit:
                    SuffixArray sa = new SuffixArray(...);
                    Vector<SuffixArrayResult> result = sa.search();
                ... and then each element of result has a "semantic_type"
                    member that can be "RUT"
        ... SuffixArray.search()
            semantic_type=this.lex.sem_list().get(i);

            ... where lex comes from MedTagger:
                this.lex = new Lexicon(this.lex_fname);
        ... Lexicon.sem_list() returns Lexicon.semantic_list
            ... Lexicon.Lexicon() constructs using MedTagger's this.lex_fname
            ... which is lexicon.cfg

        ... aha! There it is. If a line in lexicon.cfg has a RUT tag, it'll
            appear as a route. So:
                grep "RUT$" lexicon.cfg | sort  # and replace tabs with spaces

            bedside    RUT
            by mouth    RUT
            drip    RUT
            gt    RUT
            g tube    RUT
            g-tube    RUT
            gtube    RUT
            im injection    RUT
            im    RUT
            inhalation    RUT
            inhalatn    RUT
            inhaled    RUT
            intramuscular    RUT
            intravenously    RUT
            intravenous    RUT
            iv    RUT
            j tube    RUT
            j-tube    RUT
            jtube    RUT
            nare    RUT
            nares    RUT
            naris    RUT
            neb    RUT
            nostril    RUT
            orally    RUT
            oral    RUT
            ou    RUT
            patch    DDF-DOSEUNIT-RUT
            per gt    RUT
            per mouth    RUT
            per os    RUT
            per rectum    RUT
            per tube    RUT
            p. g    RUT
            pgt    RUT
            png    RUT
            pnj    RUT
            p.o    RUT
            po    RUT
            sc    RUT
            sl    RUT
            sq    RUT
            subc    RUT
            subcu    RUT
            subcutaneously    RUT
            subcutaneous    RUT
            subcut    RUT
            subling    RUT
            sublingual    RUT
            sub q    RUT
            subq    RUT
            swallow    RUT
            swish and spit    RUT
            sw&spit    RUT
            sw&swall    RUT
            topically    RUT
            topical    RUT
            topical tp    RUT
            trans    RUT
            with spacer    RUT

  Looks like these are not using synonyms. Note also format is ``route\tRUT``

  Note also that the first element is always forced to lower case (in
  Lexicon.Lexicon()), so presumably it's case-insensitive.

  There's no specific comment format (though any line that doesn't resolve to
  two items when split on a tab looks like it's ignored).

  So we might want to add more; use

  .. code-block:: bash

        build_medex_itself.py --extraroutes >> lexicon.cfg

- Note that all frequencies and routes must be in the lexicon.
  And all frequencies must be in ``SemanticRuleEngine.java`` (and, to be
  normalized, frequency_rules).

- USEFUL BIT FOR CHECKING RESULTS:

  .. code-block:: sql

    SELECT
        sentence_text,
        drug, generic_name,
        form, strength, dose_amount,
        route, frequency, frequency_timex3,
        duration, necessity
    FROM anonymous_output.drugs;

- ENCODING

  - Pipe encoding (to Java's ``stdin``, from Java's ``stdout``) encoding is the
    less important as we're only likely to send/receive ASCII. It's hard-coded
    to UTF-8.

  - File encoding is vital and is hard-coded to UTF-8 here and in the
    receiving Java.

  - We have no direct influence over the MedTagger code for output (unless we
    modify it). The output function is ``MedTagger.print_result()``, which
    (line 2040 of ``MedTagger.java``) calls ``out.write(stuff)``.

    The out variable is set by

    .. code-block:: java

        this.out = new BufferedWriter(new FileWriter(output_dir
                + File.separator + doc.fname()));

    That form of the FileWriter constructor, ``FileWriter(String fileName)``,
    uses the "default character encoding", as per
    https://docs.oracle.com/javase/7/docs/api/java/io/FileWriter.html

    That default is given by ``System.getProperty("file.encoding")``. However,
    we don't have to do something daft like asking the Java to report its file
    encoding to Python through a pipe; instead, we can set the Java default
    encoding. It can't be done dynamically, but it can be done at JVM launch:
    https://stackoverflow.com/questions/361975/setting-the-default-java-character-encoding.

    Therefore, we should have a Java parameter specified in the config file as
    ``-Dfile.encoding=UTF-8``.

"""  # noqa: E501

import logging
import os
import shlex
import subprocess
import tempfile
from typing import Any, Dict, Generator, List, Optional, Tuple

from cardinal_pythonlib.cmdline import cmdline_quote
from cardinal_pythonlib.fileops import mkdir_p
from sqlalchemy import Column, Index, Integer, String, Text

from crate_anon.nlp_manager.base_nlp_parser import (
    BaseNlpParser,
    TextProcessingFailed,
)
from crate_anon.nlp_manager.constants import (
    MEDEX_DATA_READY_SIGNAL,
    MEDEX_RESULTS_READY_SIGNAL,
    ProcessorConfigKeys,
)
from crate_anon.nlp_manager.nlp_definition import (
    NlpDefinition,
)

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

DATA_FILENAME = "crate_medex.txt"
DATA_FILENAME_KEEP = "crate_medex_{}.txt"

USE_TEMP_DIRS = True
# ... True for production; False to see e.g. logs afterwards, by keeping
# everything in a subdirectory of the user's home directory (see hard-coded
# nastiness -- for debugging only)

SKIP_IF_NO_GENERIC = True
# ... Probably should be True. MedEx returns hits for drug "Thu" with no
# generic drug; this from its weekday lexicon, I think.

# -----------------------------------------------------------------------------
# Maximum field lengths
# -----------------------------------------------------------------------------
# https://phekb.org/sites/phenotype/files/MedEx_UIMA_eMERGE_short.pdf
#
# RxNorm: https://www.nlm.nih.gov/research/umls/rxnorm/overview.html
#
# UMLS: https://www.nlm.nih.gov/research/umls/new_users/glossary.html
# UMLS CUI max length: https://www.nlm.nih.gov/research/umls/knowledge_sources/metathesaurus/release/columns_data_elements.html  # noqa: E501
UMLS_CUI_MAX_LENGTH = 8  # definite

# TIMEX3:
# - http://www.timeml.org/tempeval2/tempeval2-trial/guidelines/timex3guidelines-072009.pdf  # noqa: E501
# - http://www.timeml.org/publications/timeMLdocs/timeml_1.2.1.html#timex3  # noqa: E501
TIMEX3_MAX_LENGTH = 50  # guess

# Drug length:
# There are long ones, like
#   "influenza virus vaccine, inactivated a-brisbane-59-2007, ivr-148 (h1n1) strain" (78)  # noqa: E501
# See e.g. resources/rxcui_generic.cfg, and:
# $ wc -L filename  # shows length of longest line
# $ egrep -n "^.{$(wc -L < filename)}$" filename  # shows longest line
#   ... possibly this gets a bit confused by tabs, can also put a length in:
# $ egrep -n "^.{302}$" filename  # shows lines of length 302
# And we find a drug of length 286:
#   1-oxa-7-azacyclopentadecan-15-one,13-((2,6-dideoy-3-c-methyl-3-o-methyl-alpha-l-ribo-hexopyranosyl)oxy)-2-ethyl-3,4,10-trihydroxy 3,5,8,10,12,14-hexamethyl-7-propyl-11-((3,4,6-trideoxy-3-(dimethylamino)-beta-d-xylo-hexopyranosyl)oxy)-, ((2r*, 3s*,4r*,5s*,8r*,10r*,11r*,12s*,13s*,14r*))-  # noqa: E501
# Then there are multivitamin things in brand_generic with length >600.
# So we should use an unlimited field; SQLAlchemy helpfully seems to translate
# Text to VARCHAR(MAX) under SQL Server, which is the more efficient:
# https://stackoverflow.com/questions/834788/using-varcharmax-vs-text-on-sql-server  # noqa: E501
MEDEX_MAX_FORM_LENGTH = 255  # guess; "Powder For Oral Suspension" (26) is one
MEDEX_MAX_STRENGTH_LENGTH = 50  # guess
MEDEX_MAX_DOSE_AMOUNT_LENGTH = 50  # guess
MEDEX_MAX_ROUTE_LENGTH = 50  # guess
MEDEX_MAX_FREQUENCY_LENGTH = 50  # guess
MEDEX_MAX_DURATION_LENGTH = 50  # guess
MEDEX_MAX_NECESSITY_LENGTH = 50  # guess


# =============================================================================
# Medex
# =============================================================================


class PseudoTempDir:
    """
    This class exists so that a TemporaryDirectory and a manually specified
    directory can be addressed via the same (very simple!) interface.
    """

    def __init__(self, name: str) -> None:
        self.name = name


class Medex(BaseNlpParser):
    """
    EXTERNAL.

    Class controlling a Medex-UIMA external process, via our custom Java
    interface, ``CrateMedexPipeline.java``.

    MedEx-UIMA is a medication-finding tool:
    https://www.ncbi.nlm.nih.gov/pubmed/25954575.
    """

    uses_external_tool = True

    def __init__(
        self,
        nlpdef: NlpDefinition,
        cfg_processor_name: str,
        commit: bool = False,
    ) -> None:
        """
        Args:
            nlpdef:
                a :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
            cfg_processor_name:
                the name of a CRATE NLP config file section (from which we may
                choose to get extra config information)
            commit:
                force a COMMIT whenever we insert data? You should specify this
                in multiprocess mode, or you may get database deadlocks.
        """
        super().__init__(
            nlpdef=nlpdef,
            cfg_processor_name=cfg_processor_name,
            commit=commit,
            friendly_name="MedEx",
        )

        if nlpdef is None:  # only None for debugging!
            self._debug_mode = True
            self._tablename = self.classname().lower()
            self._max_external_prog_uses = 1
            self._progenvsection = ""
            self._env = {}  # type: Dict[str, str]
            progargs = ""
        else:
            self._debug_mode = False

            self._tablename = self._cfgsection.opt_str(
                ProcessorConfigKeys.DESTTABLE, required=True
            )

            self._max_external_prog_uses = self._cfgsection.opt_int_positive(
                ProcessorConfigKeys.MAX_EXTERNAL_PROG_USES, default=0
            )

            self._progenvsection = self._cfgsection.opt_str(
                ProcessorConfigKeys.PROGENVSECTION
            )

            if self._progenvsection:
                # noinspection PyTypeChecker
                self._env = nlpdef.get_env_dict(
                    self._progenvsection, os.environ
                )
            else:
                self._env = os.environ.copy()
            self._env["NLPLOGTAG"] = nlpdef.logtag or "."
            # ... because passing a "-lt" switch with no parameter will make
            # CrateMedexPipeline.java complain and stop

            progargs = self._cfgsection.opt_str(
                ProcessorConfigKeys.PROGARGS, required=True
            )

        if USE_TEMP_DIRS:
            self._inputdir = tempfile.TemporaryDirectory()
            self._outputdir = tempfile.TemporaryDirectory()
            self._workingdir = tempfile.TemporaryDirectory()
            # ... these are autodeleted when the object goes out of scope; see
            #     https://docs.python.org/3/library/tempfile.html
            # ... which manages it using weakref.finalize
        else:
            homedir = os.path.expanduser("~")
            self._inputdir = PseudoTempDir(
                os.path.join(homedir, "medextemp", "input")
            )
            mkdir_p(self._inputdir.name)
            self._outputdir = PseudoTempDir(
                os.path.join(homedir, "medextemp", "output")
            )
            mkdir_p(self._outputdir.name)
            self._workingdir = PseudoTempDir(
                os.path.join(homedir, "medextemp", "working")
            )
            mkdir_p(self._workingdir.name)

        formatted_progargs = progargs.format(**self._env)
        self._progargs = shlex.split(formatted_progargs)
        self._progargs.extend(
            [
                "-data_ready_signal",
                MEDEX_DATA_READY_SIGNAL,
                "-results_ready_signal",
                MEDEX_RESULTS_READY_SIGNAL,
                "-i",
                self._inputdir.name,
                "-o",
                self._outputdir.name,
            ]
        )

        self._n_uses = 0
        self._pipe_encoding = "utf8"
        self._file_encoding = "utf8"
        self._p = None  # the subprocess
        self._started = False

    # -------------------------------------------------------------------------
    # External process control
    # -------------------------------------------------------------------------

    def _start(self) -> None:
        """
        Launch the external process. We will save and retrieve data via files,
        and send signals ("data ready", "results ready) via stdin/stout.
        """
        if self._started or self._debug_mode:
            return
        args = self._progargs

        # Nasty MedEx hacks
        cwd = os.getcwd()
        log.info(
            f"For MedEx's benefit, changing to directory: "
            f"{self._workingdir.name}"
        )
        os.chdir(self._workingdir.name)
        sentsdir = os.path.join(self._workingdir.name, "sents")
        log.info(f"Making temporary sentences directory: {sentsdir}")
        mkdir_p(sentsdir)
        logdir = os.path.join(self._workingdir.name, "log")
        log.info(f"Making temporary log directory: {logdir}")
        mkdir_p(logdir)

        log.info(f"Launching command: {cmdline_quote(args)}")
        self._p = subprocess.Popen(
            args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            # stderr=subprocess.PIPE,
            shell=False,
            bufsize=1,
        )
        # ... don't ask for stderr to be piped if you don't want it; firstly,
        # there's a risk that if you don't consume it, something hangs, and
        # secondly if you don't consume it, you see it on the console, which is
        # helpful.
        self._started = True
        log.info(f"Returning to working directory {cwd}")
        os.chdir(cwd)

    def _encode_to_subproc_stdin(self, text: str) -> None:
        """
        Send text to the external program (via its stdin), encoding it in
        the process (typically to UTF-8).
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
        Decode what we've received from the external program's stdout,
        from its specific encoding (usually UTF-8) to a Python string.
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
        self._p.communicate()  # close p.stdout, wait for the subprocess to exit  # noqa: E501
        self._started = False

    def _signal_data_ready(self) -> bool:
        """
        Signals to the child process that we have written data to files, and
        it's now ready for reading by MedEx.

        Returns: OK?
        """
        if self._finished():
            return False
        self._encode_to_subproc_stdin(MEDEX_DATA_READY_SIGNAL + os.linesep)
        self._flush_subproc_stdin()
        return True

    def _await_results_ready(self) -> bool:
        """
        Waits until MedEx has signalled us that results are ready.

        Returns: OK?
        """
        while True:
            if self._finished():
                return False
            line = self._decode_from_subproc_stdout()
            if line == MEDEX_RESULTS_READY_SIGNAL + os.linesep:
                return True

    def _finished(self) -> bool:
        """
        Has MedEx finished?
        """
        if not self._started:
            return True
        self._p.poll()
        finished = self._p.returncode is not None
        if finished:
            self._started = False
        return finished

    def _restart(self) -> None:
        """
        Close down the external process and restart it.
        """
        self._finish()
        self._start()

    # -------------------------------------------------------------------------
    # Input processing
    # -------------------------------------------------------------------------

    def parse(
        self, text: str
    ) -> Generator[Tuple[str, Dict[str, Any]], None, None]:
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
        self._n_uses += 1
        self._start()  # ensure started
        if USE_TEMP_DIRS:
            basefilename = DATA_FILENAME
        else:
            basefilename = DATA_FILENAME_KEEP.format(self._n_uses)
        inputfilename = os.path.join(self._inputdir.name, basefilename)
        outputfilename = os.path.join(self._outputdir.name, basefilename)
        # ... MedEx gives output files the SAME NAME as input files.

        try:
            with open(
                inputfilename, mode="w", encoding=self._file_encoding
            ) as infile:
                # log.info(f"text: {text!r}")
                infile.write(text)

            if (
                not self._signal_data_ready()
                or not self._await_results_ready()  # send
            ):  # receive
                log.critical("Subprocess terminated unexpectedly")
                os.remove(inputfilename)
                # We were using "log.critical()" and "return", but if the Medex
                # processor is misconfigured, the failed processor can be run
                # over thousands of records over many hours before the failure
                # is obvious. Changed 2017-03-17.
                raise ValueError(
                    "Java interface to Medex failed - miconfigured?"
                )

            with open(
                outputfilename, mode="r", encoding=self._file_encoding
            ) as infile:
                resultlines = infile.readlines()
            for line in resultlines:
                # log.critical(f"received: {line}")
                # Output code, from MedTagger.print_result():
                # out.write(
                #     index + 1 + "\t" + sent_text + "|" +
                #     drug + "|" + brand + "|" + dose_form + "|" +
                #     strength + "|" + dose_amt + "|" +
                #     route + "|" + frequency + "|" + duration + "|" +
                #     necessity + "|" +
                #     umls_code + "|" + rx_code + "|" + generic_code + "|" +
                #     generic_name + "\n");
                # NOTE that the text can contain | characters. So work from the
                # right.
                line = line.rstrip()  # remove any trailing newline
                fields = line.split("|")
                if len(fields) < 14:
                    log.warning(f"Bad result received: {line!r}")
                    continue
                generic_name = self.str_or_none(fields[-1])
                if not generic_name and SKIP_IF_NO_GENERIC:
                    continue
                generic_code = self.int_or_none(fields[-2])
                rx_code = self.int_or_none(fields[-3])
                umls_code = self.str_or_none(fields[-4])
                (
                    necessity,
                    necessity_startpos,
                    necessity_endpos,
                ) = self.get_text_start_end(fields[-5])
                (
                    duration,
                    duration_startpos,
                    duration_endpos,
                ) = self.get_text_start_end(fields[-6])
                (
                    _freq_text,
                    frequency_startpos,
                    frequency_endpos,
                ) = self.get_text_start_end(fields[-7])
                frequency, frequency_timex = self.frequency_and_timex(
                    _freq_text
                )
                (
                    route,
                    route_startpos,
                    route_endpos,
                ) = self.get_text_start_end(fields[-8])
                (
                    dose_amount,
                    dose_amount_startpos,
                    dose_amount_endpos,
                ) = self.get_text_start_end(fields[-9])
                (
                    strength,
                    strength_startpos,
                    strength_endpos,
                ) = self.get_text_start_end(fields[-10])
                (form, form_startpos, form_endpos) = self.get_text_start_end(
                    fields[-11]
                )
                (
                    brand,
                    brand_startpos,
                    brand_endpos,
                ) = self.get_text_start_end(fields[-12])
                (drug, drug_startpos, drug_endpos) = self.get_text_start_end(
                    fields[-13]
                )
                _start_bit = "|".join(fields[0:-13])
                _index_text, sent_text = _start_bit.split("\t", maxsplit=1)
                index = self.int_or_none(_index_text)
                yield self._tablename, {
                    "sentence_index": index,
                    "sentence_text": sent_text,
                    "drug": drug,
                    "drug_startpos": drug_startpos,
                    "drug_endpos": drug_endpos,
                    "brand": brand,
                    "brand_startpos": brand_startpos,
                    "brand_endpos": brand_endpos,
                    "form": form,
                    "form_startpos": form_startpos,
                    "form_endpos": form_endpos,
                    "strength": strength,
                    "strength_startpos": strength_startpos,
                    "strength_endpos": strength_endpos,
                    "dose_amount": dose_amount,
                    "dose_amount_startpos": dose_amount_startpos,
                    "dose_amount_endpos": dose_amount_endpos,
                    "route": route,
                    "route_startpos": route_startpos,
                    "route_endpos": route_endpos,
                    "frequency": frequency,
                    "frequency_startpos": frequency_startpos,
                    "frequency_endpos": frequency_endpos,
                    "frequency_timex3": frequency_timex,
                    "duration": duration,
                    "duration_startpos": duration_startpos,
                    "duration_endpos": duration_endpos,
                    "necessity": necessity,
                    "necessity_startpos": necessity_startpos,
                    "necessity_endpos": necessity_endpos,
                    "umls_code": umls_code,
                    "rx_code": rx_code,
                    "generic_code": generic_code,
                    "generic_name": generic_name,
                }

            # Since MedEx scans all files in the input directory, then if we're
            # not using temporary directories (and are therefore using a new
            # filename per item), we should remove the old one.
            os.remove(inputfilename)

            # Restart subprocess?
            if (
                self._max_external_prog_uses > 0
                and self._n_uses % self._max_external_prog_uses == 0
            ):
                log.info(
                    f"relaunching app after "
                    f"{self._max_external_prog_uses} uses"
                )
                self._restart()

        except BrokenPipeError:
            log.error("Broken pipe; relaunching app")
            self._restart()
            raise TextProcessingFailed()

    @staticmethod
    def get_text_start_end(
        medex_str: Optional[str],
    ) -> Tuple[Optional[str], Optional[int], Optional[int]]:
        """
        MedEx returns "drug", "strength", etc. as ``aspirin[7,14]``, where the
        text is followed by the start position (zero-indexed) and the end
        position (one beyond the last character) (zero-indexed). This function
        converts a string like ``aspirin[7,14]`` to a tuple like ``"aspirin",
        7, 14``.

        Args:
            medex_str: string from MedEx

        Returns:
            tuple: ``text, start_pos, end_pos``; values may be ``None``
        """
        if not medex_str:
            return None, None, None
        lbracket = medex_str.rfind("[")  # -1 for not found
        comma = medex_str.rfind(",")
        rbracket = medex_str.rfind("]")
        try:
            if lbracket == -1 or not (lbracket < comma < rbracket):
                raise ValueError()
            text = medex_str[:lbracket]
            lpos = int(medex_str[lbracket + 1 : comma])
            rpos = int(medex_str[comma + 1 : rbracket])
            return text, lpos, rpos
        except (TypeError, ValueError):
            log.warning(f"Bad string[left, right] format: {medex_str!r}")
            return None, None, None

    @staticmethod
    def int_or_none(text: Optional[str]) -> Optional[int]:
        """
        Takes text and returns an integer version or ``None``.
        """
        try:
            return int(text)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def str_or_none(text: Optional[str]) -> Optional[str]:
        """
        If the string is non-empty, return the string; otherwise return
        ``None``.
        """
        return None if not text else text

    @staticmethod
    def frequency_and_timex(text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Splits a MedEx frequency/TIMEX strings to its frequency and TIMEX
        parts; e.g. splits ``b.i.d.(R1P12H)`` to ``"b.i.d.", "R1P12H"``.
        """
        if not text:
            return None, None
        lbracket = text.rfind("(")
        rbracket = text.rfind(")")
        if (
            lbracket == -1
            or not (lbracket < rbracket)
            or rbracket != len(text) - 1
        ):
            return None, None
        return text[0:lbracket], text[lbracket + 1 : rbracket]

    # -------------------------------------------------------------------------
    # Test
    # -------------------------------------------------------------------------

    def test(self, verbose: bool = False) -> None:
        """
        Test the send function.
        """
        if self._debug_mode:
            return
        self.test_parser(
            [
                "Bob Hope visited Seattle and took venlafaxine M/R 375mg od.",
                "James Joyce wrote Ulysses whilst taking aspirin 75mg mane.",
            ]
        )

    # -------------------------------------------------------------------------
    # Database structure
    # -------------------------------------------------------------------------

    def dest_tables_columns(self) -> Dict[str, List[Column]]:
        # docstring in superclass
        startposdef = "Start position (zero-based) of "
        endposdef = (
            "End position (zero-based index of one beyond last character) of "
        )
        return {
            self._tablename: [
                Column(
                    "sentence_index",
                    Integer,
                    comment="One-based index of sentence in text",
                ),
                Column(
                    "sentence_text",
                    Text,
                    comment="Text recognized as a sentence by MedEx",
                ),
                Column("drug", Text, comment="Drug name, as in the text"),
                Column("drug_startpos", Integer, comment=startposdef + "drug"),
                Column("drug_endpos", Integer, comment=endposdef + "drug"),
                Column(
                    "brand",
                    Text,
                    comment="Drug brand name (?lookup ?only if given)",
                ),
                Column(
                    "brand_startpos", Integer, comment=startposdef + "brand"
                ),
                Column("brand_endpos", Integer, comment=endposdef + "brand"),
                Column(
                    "form",
                    String(MEDEX_MAX_FORM_LENGTH),
                    comment="Drug/dose form (e.g. 'tablet')",
                ),
                Column("form_startpos", Integer, comment=startposdef + "form"),
                Column("form_endpos", Integer, comment=endposdef + "form"),
                Column(
                    "strength",
                    String(MEDEX_MAX_STRENGTH_LENGTH),
                    comment="Strength (e.g. '75mg')",
                ),
                Column(
                    "strength_startpos",
                    Integer,
                    comment=startposdef + "strength",
                ),
                Column(
                    "strength_endpos", Integer, comment=endposdef + "strength"
                ),
                Column(
                    "dose_amount",
                    String(MEDEX_MAX_DOSE_AMOUNT_LENGTH),
                    comment="Dose amount (e.g. '2 tablets')",
                ),
                Column(
                    "dose_amount_startpos",
                    Integer,
                    comment=startposdef + "dose_amount",
                ),
                Column(
                    "dose_amount_endpos",
                    Integer,
                    comment=endposdef + "dose_amount",
                ),
                Column(
                    "route",
                    String(MEDEX_MAX_ROUTE_LENGTH),
                    comment="Route (e.g. 'by mouth')",
                ),
                Column(
                    "route_startpos", Integer, comment=startposdef + "route"
                ),
                Column("route_endpos", Integer, comment=endposdef + "route"),
                Column(
                    "frequency",
                    String(MEDEX_MAX_FREQUENCY_LENGTH),
                    comment="Frequency (e.g. 'b.i.d.')",
                ),
                Column(
                    "frequency_startpos",
                    Integer,
                    comment=startposdef + "frequency",
                ),
                Column(
                    "frequency_endpos",
                    Integer,
                    comment=endposdef + "frequency",
                ),
                Column(
                    "frequency_timex3",
                    String(TIMEX3_MAX_LENGTH),
                    comment=(
                        "Normalized frequency in TIMEX3 format "
                        "(e.g. 'R1P12H')"
                    ),
                ),
                Column(
                    "duration",
                    String(MEDEX_MAX_DURATION_LENGTH),
                    comment="Duration (e.g. 'for 10 days')",
                ),
                Column(
                    "duration_startpos",
                    Integer,
                    comment=startposdef + "duration",
                ),
                Column(
                    "duration_endpos", Integer, comment=endposdef + "duration"
                ),
                Column(
                    "necessity",
                    String(MEDEX_MAX_NECESSITY_LENGTH),
                    comment="Necessity (e.g. 'prn')",
                ),
                Column(
                    "necessity_startpos",
                    Integer,
                    comment=startposdef + "necessity",
                ),
                Column(
                    "necessity_endpos",
                    Integer,
                    comment=endposdef + "necessity",
                ),
                Column(
                    "umls_code",
                    String(UMLS_CUI_MAX_LENGTH),
                    comment="UMLS CUI",
                ),
                Column("rx_code", Integer, comment="RxNorm RxCUI for drug"),
                Column(
                    "generic_code",
                    Integer,
                    comment="RxNorm RxCUI for generic name",
                ),
                Column(
                    "generic_name",
                    Text,
                    comment="Generic drug name (associated with RxCUI code)",
                ),
            ]
        }

    def dest_tables_indexes(self) -> Dict[str, List[Index]]:
        # docstring in superclass
        return {}
        # return {
        #     self._tablename: [
        #         Index('idx_generic_name', 'generic_name'),
        #     ]
        # }
