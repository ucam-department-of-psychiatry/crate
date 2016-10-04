#!/usr/bin/env python
# crate_anon/nlp_manager/parse_medex.py

"""
- MedEx-UIMA
  ... can't find Python version of MedEx (which preceded MedEx-UIMA)
  ... paper on Python version is https://www.ncbi.nlm.nih.gov/pmc/articles/PMC2995636/
        ... uses Python NLTK
  ... see notes in Documents/CRATE directory
  ... MedEx-UIMA is in Java, and resolutely uses a file-based processing
      system; Main.java calls MedTagger.java (MedTagger.run_batch_medtag), and
      even in its core MedTagger.medtagging() function it's making files in
      directories; that's deep in the core of its NLP thinking so we can't
      change that behaviour without creating a fork.
      So the obvious way to turn this into a proper "live" pipeline would be
      for the calling code to
            fire up a receiving process - Python launching custom Java
            create its own temporary directory - Python
            receive data - Python
            stash it on disk - Python
            call the MedEx function - Python -> stdout -> custom Java -> MedEx
            return the results - custom Java signals "done" -> Python reads stdin?
            and clean up - Python
      Not terribly elegant, but might be fast enough (and almost certainly
      much faster than reloading Java regularly!).
  ... output comes from its MedTagger.print_result() function
  ... would need a per-process-unique temporary directory, since it scans all
      files in the input directory (and similarly one output directory); would
      do that in Python


MedEx-UIMA is firmly (and internally) wedded to a file-based processing
system. So we need to:

    - create a process-specific pair of temporary directories;
    - fire up a receiving process
    - pass data (1) to file and (2) signal that there's data available;
    - await a "data ready" reply and read the data from disk;
    - clean up (delete files) in readiness for next data chunk.

NOTE ALSO that MedEx's MedTagger class writes to stdout (though not
stderr). Option 1: move our logs to stdout and use stderr for signalling.
Option 2: keep things as they are and just use a stdout signal that's
not used by MedEx. Went with option 2; simpler and more consistent esp.
for logging.

How do we clean up the temporary directories?
- __del__ is not the opposite of __init__
  http://www.algorithm.co.il/blogs/programming/python-gotchas-1-__del__-is-not-the-opposite-of-__init__/
- http://eli.thegreenplace.net/2009/06/12/safely-using-destructors-in-python  # noqa

PROBLEMS:
-   NLP works fine, but UK-style abbreviations e.g. "qds" not recognized where
    "q.i.d." is. US abbreviations: e.g.
    http://www.d.umn.edu/medweb/Modules/Prescription/Abbreviations.html

    Places to look, and things to try adding:

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

    reference to expression/val (as in frequency_rules)
    TIMEX.Rule._add_rule()
        ... from TIMEX.Rule.Rule via a directory walker
        ... from TIMEX.ProcessingEngine.ProcessingEngine()
            ... via semi-hardcoded file location relative to class's location
                ... via rule_dir, set to .../TIMEX/rules

    Detect a file being accessed:

        sudo apt install inotify-tools
        inotifywait -m FILE

    ... frequency_rules IS opened.

    OVERALL SEQUENCE:

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

-   Rebuilding MedEx:

    export MEDEX_HOME=~/dev/MedEx_UIMA_1.3.6  # or similar
    cd ${MEDEX_HOME}
    # OPTIONAL # find . -name "*.class" -exec rm {} \;  # remove old compiled files
    javac \
        -classpath "${MEDEX_HOME}/src:${MEDEX_HOME}/lib/*" \
        src/org/apache/medex/Main.java \
        -d bin

    # ... will also compile dependencies

    See build_medex_itself.py

-   YES. If you add to org.apache.medex.SemanticRuleEngine, with extra entries
    in the "regexlist.put(...)" sequence, new frequencies appear in the output.

    To get them normalized as well, add them to frequency_rules.

    Specifics:
    (a) SemanticRuleEngine.java

        // EXTRA FOR UK FREQUENCIES (see http://www.evidence.nhs.uk/formulary/bnf/current/general-reference/latin-abbreviations)
        // NB case-insensitive regexes in SemanticRuleEngine.java, so ignore case here
        regexlist.put("^(q\\.?q\\.?h\\.?)( |$)","FREQ");  // qqh, quarta quaque hora (RNC)
        regexlist.put("^(q\\.?d\\.?s\\.?)( |$)","FREQ");  // qds, quater die sumendum (RNC); must go before existing competing expression: regexlist.put("^q(\\.|)\\d+( |$)","FREQ");
        regexlist.put("^(t\\.?d\\.?s\\.?)( |$)","FREQ");  // tds, ter die sumendum (RNC)
        regexlist.put("^(b\\.?d\\.?)( |$)","FREQ");  // bd, bis die (RNC)
        regexlist.put("^(o\\.?d\\.?)( |$)","FREQ");  // od, omni die (RNC)
        regexlist.put("^(mane)( |$)","FREQ");  // mane (RNC)
        regexlist.put("^(o\\.?m\\.?)( |$)","FREQ");  // om, omni mane (RNC)
        regexlist.put("^(nocte)( |$)","FREQ");  // nocte (RNC)
        regexlist.put("^(o\\.?n\\.?)( |$)","FREQ");  // on, omni nocte (RNC)
        // ALREADY IMPLEMENTED BY MedEx: tid (ter in die)
        // NECESSITY, NOT FREQUENCY: prn (pro re nata)
        // TIMING, NOT FREQUENCY: ac (ante cibum); pc (post cibum)

    (b) frequency_rules

// EXTRA FOR UK FREQUENCIES (see http://www.evidence.nhs.uk/formulary/bnf/current/general-reference/latin-abbreviations)
// NB case-sensitive regexes in Rule.java, so offer upper- and lower-case alternatives here
// qqh, quarta quaque hora (RNC)
expression="[Qq]\.?[Qq]\.?[Hh]\.?",val="R1P4H"
// qds, quater die sumendum (RNC); MUST BE BEFORE COMPETING "qd" (= per day) expression: expression="[Qq]\.?[ ]?[Dd]\.?",val="R1P24H"
expression="[Qq]\.?[Dd]\.?[Ss]\.?",val="R1P6H"
// tds, ter die sumendum (RNC)
expression="[Tt]\.?[Dd]\.?[Ss]\.?",val="R1P8H"
// bd, bis die (RNC)
expression="[Bb]\.?[Dd]\.?[ ]",val="R1P12H"
// od, omni die (RNC)
expression="[Oo]\.?[Dd]\.?[ ]",val="R1P24H"
// mane (RNC)
expression="[Mm][Aa][Nn][Ee]",val="R1P24H"
// om, omni mane (RNC)
expression="[Oo]\.?[Mm]\.?[ ]",val="R1P24H"
// nocte (RNC)
expression="[Nn][Oo][Cc][Tt][Ee]",val="R1P24H"
// on, omni nocte (RNC)
expression="[Oo]\.?[Nn]\.?[ ]",val="R1P24H"
// ALREADY IMPLEMENTED BY MedEx: tid (ter in die)
// NECESSITY, NOT FREQUENCY: prn (pro re nata)
// TIMING, NOT FREQUENCY: ac (ante cibum); pc (post cibum)

    (c) source:

        http://www.evidence.nhs.uk/formulary/bnf/current/general-reference/latin-abbreviations

-   How about routes of administration?

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
                grep "RUT$" lexicon.cfg | sort

            bedside	RUT
            by mouth	RUT
            drip	RUT
            gt	RUT
            g tube	RUT
            g-tube	RUT
            gtube	RUT
            im injection	RUT
            im	RUT
            inhalation	RUT
            inhalatn	RUT
            inhaled	RUT
            intramuscular	RUT
            intravenously	RUT
            intravenous	RUT
            iv	RUT
            j tube	RUT
            j-tube	RUT
            jtube	RUT
            nare	RUT
            nares	RUT
            naris	RUT
            neb	RUT
            nostril	RUT
            orally	RUT
            oral	RUT
            ou	RUT
            patch	DDF-DOSEUNIT-RUT
            per gt	RUT
            per mouth	RUT
            per os	RUT
            per rectum	RUT
            per tube	RUT
            p. g	RUT
            pgt	RUT
            png	RUT
            pnj	RUT
            p.o	RUT
            po	RUT
            sc	RUT
            sl	RUT
            sq	RUT
            subc	RUT
            subcu	RUT
            subcutaneously	RUT
            subcutaneous	RUT
            subcut	RUT
            subling	RUT
            sublingual	RUT
            sub q	RUT
            subq	RUT
            swallow	RUT
            swish and spit	RUT
            sw&spit	RUT
            sw&swall	RUT
            topically	RUT
            topical	RUT
            topical tp	RUT
            trans	RUT
            with spacer	RUT

    Looks like these are not using synonyms. Note also format is route\tRUT
    Note also that the first element is always forced to lower case (in
        Lexicon.Lexicon()), so presumably it's case-insensitive.
    There's no specific comment format (though any line that doesn't resolve
        to two items when split on a tab looks like it's ignored).
    So we might want to add more; use

        build_medex_itself.py --extraroutes >> lexicon.cfg

-   USEFUL BIT FOR CHECKING RESULTS:

    SELECT
        sentence_text,
        drug, generic_name,
        form, strength, dose_amount,
        route, frequency, frequency_timex3,
        duration, necessity
    FROM anonymous_output.drugs;

"""  # noqa

import logging
import os
import shlex
import subprocess
import tempfile
from typing import Any, Dict, Iterator, List, Optional, Tuple

from cardinal_pythonlib.rnc_lang import AttrDict
from sqlalchemy import Column, Index, Integer, String, Text

from crate_anon.common.fileops import mkdir_p
from crate_anon.nlp_manager.base_nlp_parser import BaseNlpParser
from crate_anon.nlp_manager.constants import (
    MEDEX_DATA_READY_SIGNAL,
    MEDEX_RESULTS_READY_SIGNAL,
)
from crate_anon.nlp_manager.nlp_definition import NlpDefinition

log = logging.getLogger(__name__)


DATA_FILENAME = "crate_medex.txt"
DATA_FILENAME_KEEP = "crate_medex_{}.txt"

USE_TEMP_DIRS = True
# ... True for production; False to see e.g. logs afterwards, by keeping
# everything in a subdirectory of the user's home directory (see hard-coded
# nastiness -- for debugging only)

SKIP_IF_NO_GENERIC = True
# ... Probably should be True. MedEx returns hits for drug "Thu" with no
# generic drug; this from its weekday lexicon, I think.


class Medex(BaseNlpParser):
    """Class controlling a Medex-UIMA external process, via our custom
    Java interface, CrateMedexPipeline.java.
    """

    NAME = "MedEx"

    def __init__(self,
                 nlpdef: NlpDefinition,
                 cfgsection: str,
                 commit: bool = False) -> None:
        super().__init__(nlpdef=nlpdef, cfgsection=cfgsection, commit=commit)

        self._tablename = nlpdef.opt_str(
            cfgsection, 'desttable', required=True)

        self._max_external_prog_uses = nlpdef.opt_int(
            cfgsection, 'max_external_prog_uses', default=0)

        self._progenvsection = nlpdef.opt_str(cfgsection, 'progenvsection')
        if self._progenvsection:
            self._env = nlpdef.get_env_dict(self._progenvsection, os.environ)
        else:
            self._env = os.environ.copy()
        self._env["NLPLOGTAG"] = nlpdef.get_logtag() or '.'
        # ... because passing a "-lt" switch with no parameter will make
        # CrateGatePipeline.java complain and stop

        if USE_TEMP_DIRS:
            self._inputdir = tempfile.TemporaryDirectory()
            self._outputdir = tempfile.TemporaryDirectory()
            self._workingdir = tempfile.TemporaryDirectory()
            # ... these are autodeleted when the object goes out of scope; see
            #     https://docs.python.org/3/library/tempfile.html
            # ... which manages it using weakref.finalize
        else:
            homedir = os.path.expanduser("~")
            self._inputdir = AttrDict(
                name=os.path.join(homedir, "medextemp", "input"))
            mkdir_p(self._inputdir.name)
            self._outputdir = AttrDict(
                name=os.path.join(homedir, "medextemp", "output"))
            mkdir_p(self._outputdir.name)
            self._workingdir = AttrDict(
                name=os.path.join(homedir, "medextemp", "working"))
            mkdir_p(self._workingdir.name)

        progargs = nlpdef.opt_str(cfgsection, 'progargs', required=True)
        formatted_progargs = progargs.format(**self._env)
        self._progargs = shlex.split(formatted_progargs)
        self._progargs.extend([
            "-data_ready_signal", MEDEX_DATA_READY_SIGNAL,
            "-results_ready_signal", MEDEX_RESULTS_READY_SIGNAL,
            "-i", self._inputdir.name,
            "-o", self._outputdir.name,
        ])

        self._n_uses = 0
        self._encoding = 'utf8'
        self._p = None  # the subprocess
        self._started = False

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

        # Nasty MedEx hacks
        cwd = os.getcwd()
        log.info("for MedEx's benefit, changing to directory: {}".format(
            self._workingdir.name))
        os.chdir(self._workingdir.name)
        sentsdir = os.path.join(self._workingdir.name, "sents")
        log.info("making temporary sentences directory: {}".format(sentsdir))
        mkdir_p(sentsdir)
        logdir = os.path.join(self._workingdir.name, "log")
        log.info("making temporary log directory: {}".format(logdir))
        mkdir_p(logdir)

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
        log.info("returning to working directory {}".format(cwd))
        os.chdir(cwd)

    def _encode_to_subproc_stdin(self, text: str) -> None:
        """Send text to the external program (via its stdin), encoding it in
        the process (typically to UTF-8)."""
        log.debug("SENDING: " + text)
        bytes_ = text.encode(self._encoding)
        self._p.stdin.write(bytes_)

    def _flush_subproc_stdin(self) -> None:
        """Flushes what we're sending to the external program via its stdin."""
        self._p.stdin.flush()

    def _decode_from_subproc_stdout(self) -> str:
        """Translate what we've received from the external program's stdout,
        from its specific encoding (usually UTF-8) to a Python string."""
        bytes_ = self._p.stdout.readline()
        text = bytes_.decode(self._encoding)
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

    def _signal_data_ready(self) -> bool:
        """Returns: OK?"""
        if self._finished():
            return False
        self._encode_to_subproc_stdin(MEDEX_DATA_READY_SIGNAL + os.linesep)
        self._flush_subproc_stdin()
        return True

    def _await_results_ready(self) -> bool:
        """Returns: ok?"""
        while True:
            if self._finished():
                return False
            line = self._decode_from_subproc_stdout()
            if line == MEDEX_RESULTS_READY_SIGNAL + os.linesep:
                return True

    def _finished(self) -> bool:
        if not self._started:
            return True
        self._p.poll()
        finished = self._p.returncode is not None
        if finished:
            self._started = False
        return finished

    # -------------------------------------------------------------------------
    # Input processing
    # -------------------------------------------------------------------------

    def parse(self, text: str) -> Iterator[Tuple[str, Dict[str, Any]]]:
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

        with open(inputfilename, mode='w') as infile:
            # log.critical("text: {}".format(repr(text)))
            infile.write(text)

        if (not self._signal_data_ready() or  # send
                not self._await_results_ready()):  # receive
            log.warning("Subprocess terminated unexpectedly")
            os.remove(inputfilename)
            return

        with open(outputfilename, mode='r') as infile:
            resultlines = infile.readlines()
        for line in resultlines:
            # log.critical("received: {}".format(line))
            # Output code, from MedTagger.print_result():
            # out.write(
            #     index + 1 + "\t" + sent_text + "|" + drug + "|" + brand + "|"
            #     + dose_form + "|" + strength + "|" + dose_amt + "|" + route
            #     + "|" + frequency + "|" + duration + "|" + necessity + "|"
            #     + umls_code + "|" + rx_code + "|" + generic_code + "|" + generic_name + "\n");  # noqa
            # NOTE that the text can contain | characters. So work from the
            # right.
            line = line.rstrip()  # remove any trailing newline
            fields = line.split('|')
            if len(fields) < 14:
                log.warning("Bad result received: {}".format(repr(line)))
                continue
            generic_name = self.str_or_none(fields[-1])
            if not generic_name and SKIP_IF_NO_GENERIC:
                continue
            generic_code = self.int_or_none(fields[-2])
            rx_code = self.int_or_none(fields[-3])
            umls_code = self.str_or_none(fields[-4])
            (necessity, necessity_startpos, necessity_endpos) = \
                self.get_text_start_end(fields[-5])
            (duration, duration_startpos, duration_endpos) = \
                self.get_text_start_end(fields[-6])
            (_freq_text, frequency_startpos, frequency_endpos) = \
                self.get_text_start_end(fields[-7])
            frequency, frequency_timex = self.frequency_and_timex(_freq_text)
            (route, route_startpos, route_endpos) = \
                self.get_text_start_end(fields[-8])
            (dose_amount, dose_amount_startpos, dose_amount_endpos) = \
                self.get_text_start_end(fields[-9])
            (strength, strength_startpos, strength_endpos) = \
                self.get_text_start_end(fields[-10])
            (form, form_startpos, form_endpos) = \
                self.get_text_start_end(fields[-11])
            (brand, brand_startpos, brand_endpos) = \
                self.get_text_start_end(fields[-12])
            (drug, drug_startpos, drug_endpos) = \
                self.get_text_start_end(fields[-13])
            _start_bit = '|'.join(fields[0:-13])
            _index_text, sent_text = _start_bit.split('\t', maxsplit=1)
            index = self.int_or_none(_index_text)
            yield self._tablename, {
                'sentence_index': index,
                'sentence_text': sent_text,

                'drug': drug,
                'drug_startpos': drug_startpos,
                'drug_endpos': drug_endpos,

                'brand': brand,
                'brand_startpos': brand_startpos,
                'brand_endpos': brand_endpos,

                'form': form,
                'form_startpos': form_startpos,
                'form_endpos': form_endpos,

                'strength': strength,
                'strength_startpos': strength_startpos,
                'strength_endpos': strength_endpos,

                'dose_amount': dose_amount,
                'dose_amount_startpos': dose_amount_startpos,
                'dose_amount_endpos': dose_amount_endpos,

                'route': route,
                'route_startpos': route_startpos,
                'route_endpos': route_endpos,

                'frequency': frequency,
                'frequency_startpos': frequency_startpos,
                'frequency_endpos': frequency_endpos,
                'frequency_timex3': frequency_timex,

                'duration': duration,
                'duration_startpos': duration_startpos,
                'duration_endpos': duration_endpos,

                'necessity': necessity,
                'necessity_startpos': necessity_startpos,
                'necessity_endpos': necessity_endpos,

                'umls_code': umls_code,
                'rx_code': rx_code,
                'generic_code': generic_code,
                'generic_name': generic_name,
            }

        # Since MedEx scans all files in the input directory, then if we're
        # not using temporary directories (and are therefore using a new
        # filename per item), we should remove the old one.
        os.remove(inputfilename)

        # Restart subprocess?
        if (self._max_external_prog_uses > 0 and
                self._n_uses % self._max_external_prog_uses == 0):
            log.info("relaunching app after {} uses".format(
                self._max_external_prog_uses))
            self._finish()
            self._start()

    @staticmethod
    def get_text_start_end(medex_str: Optional[str]) -> Tuple[Optional[str],
                                                              Optional[int],
                                                              Optional[int]]:
        """
        MedEx returns 'drug', 'strength', etc. as "aspirin[7,14]", where the
        text is followed by the start position (zero-indexed) and the end
        position (one beyond the last character) (zero-indexed).
        """
        if not medex_str:
            return None, None, None
        lbracket = medex_str.rfind('[')  # -1 for not found
        comma = medex_str.rfind(',')
        rbracket = medex_str.rfind(']')
        try:
            if lbracket == -1 or not (lbracket < comma < rbracket):
                raise ValueError()
            text = medex_str[:lbracket]
            lpos = int(medex_str[lbracket + 1:comma])
            rpos = int(medex_str[comma + 1:rbracket])
            return text, lpos, rpos
        except (TypeError, ValueError):
            log.warning("Bad string[left, right] format: {}".format(
                repr(medex_str)))
            return None, None, None

    @staticmethod
    def int_or_none(text: Optional[str]) -> Optional[int]:
        try:
            return int(text)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def str_or_none(text: Optional[str]) -> Optional[str]:
        return None if not text else text

    @staticmethod
    def frequency_and_timex(text: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Splits e.g. b.i.d.(R1P12H)
        """
        if not text:
            return None, None
        lbracket = text.rfind('(')
        rbracket = text.rfind(')')
        if (lbracket == -1 or
                not (lbracket < rbracket) or
                rbracket != len(text) - 1):
            return None, None
        return text[0:lbracket], text[lbracket + 1:rbracket]

    # -------------------------------------------------------------------------
    # Test
    # -------------------------------------------------------------------------

    def test(self) -> None:
        """
        Test the send function.
        """
        self.test_parser([
            "Bob Hope visited Seattle and took venlafaxine M/R 375mg od.",
            "James Joyce wrote Ulysses whilst taking aspirin 75mg mane."
        ])

    # -------------------------------------------------------------------------
    # Database structure
    # -------------------------------------------------------------------------

    def dest_tables_columns(self) -> Dict[str, List[Column]]:
        # https://phekb.org/sites/phenotype/files/MedEx_UIMA_eMERGE_short.pdf
        # RxNorm: https://www.nlm.nih.gov/research/umls/rxnorm/overview.html
        # UMLS: https://www.nlm.nih.gov/research/umls/new_users/glossary.html
        # UMLS CUI max length: https://www.nlm.nih.gov/research/umls/knowledge_sources/metathesaurus/release/columns_data_elements.html  # noqa
        # TIMEX3: http://www.timeml.org/tempeval2/tempeval2-trial/guidelines/timex3guidelines-072009.pdf  # noqa
        drug_length = 50  # guess
        form_length = 25  # guess
        strength_length = 25  # guess
        dose_amount_length = 25  # guess
        route_length = 25  # guess
        frequency_length = 30  # guess
        timex3_length = 30  # guess
        duration_length = 30  # guess
        necessity_length = 30  # guess
        umls_cui_max_length = 8  # definite
        startposdef = "Start position (zero-based) of "
        endposdef = (
            "End position (zero-based index of one beyond last character) of ")
        return {
            self._tablename: [
                Column('sentence_index', Integer,
                       doc="One-based index of sentence in text"),
                Column('sentence_text', Text,
                       doc="Text recognized as a sentence by MedEx"),

                Column('drug', String(drug_length),
                       doc="Drug name, as in the text"),
                Column('drug_startpos', Integer,
                       doc=startposdef + "drug"),
                Column('drug_endpos', Integer,
                       doc=endposdef + "drug"),

                Column('brand', String(drug_length),
                       doc="Drug brand name (?lookup ?only if given)"),
                Column('brand_startpos', Integer,
                       doc=startposdef + "brand"),
                Column('brand_endpos', Integer,
                       doc=endposdef + "brand"),

                Column('form', String(form_length),
                       doc="Drug/dose form (e.g. 'tablet')"),
                Column('form_startpos', Integer,
                       doc=startposdef + "form"),
                Column('form_endpos', Integer,
                       doc=endposdef + "form"),

                Column('strength', String(strength_length),
                       doc="Strength (e.g. '75mg')"),
                Column('strength_startpos', Integer,
                       doc=startposdef + "strength"),
                Column('strength_endpos', Integer,
                       doc=endposdef + "strength"),

                Column('dose_amount', String(dose_amount_length),
                       doc="Dose amount (e.g. '2 tablets')"),
                Column('dose_amount_startpos', Integer,
                       doc=startposdef + "dose_amount"),
                Column('dose_amount_endpos', Integer,
                       doc=endposdef + "dose_amount"),

                Column('route', String(route_length),
                       doc="Route (e.g. 'by mouth')"),
                Column('route_startpos', Integer,
                       doc=startposdef + "route"),
                Column('route_endpos', Integer,
                       doc=endposdef + "route"),

                Column('frequency', String(frequency_length),
                       doc="Frequency (e.g. 'b.i.d.')"),
                Column('frequency_startpos', Integer,
                       doc=startposdef + "frequency"),
                Column('frequency_endpos', Integer,
                       doc=endposdef + "frequency"),
                Column('frequency_timex3', String(timex3_length),
                       doc="Normalized frequency in TIMEX3 format "
                           "(e.g. 'R1P12H')"),

                Column('duration', String(duration_length),
                       doc="Duration (e.g. 'for 10 days')"),
                Column('duration_startpos', Integer,
                       doc=startposdef + "duration"),
                Column('duration_endpos', Integer,
                       doc=endposdef + "duration"),

                Column('necessity', String(necessity_length),
                       doc="Necessity (e.g. 'prn')"),
                Column('necessity_startpos', Integer,
                       doc=startposdef + "necessity"),
                Column('necessity_endpos', Integer,
                       doc=endposdef + "necessity"),

                Column('umls_code', String(umls_cui_max_length),
                       doc="UMLS CUI"),
                Column('rx_code', Integer,
                       doc="RxNorm RxCUI for drug"),
                Column('generic_code', Integer,
                       doc="RxNorm RxCUI for generic name"),
                Column('generic_name', String(drug_length),
                       doc="Generic drug name (associated with RxCUI code)"),
            ]
        }

    def dest_tables_indexes(self) -> Dict[str, List[Index]]:
        # return {
        #     self._tablename: [
        #         Index('idx_generic_name', 'generic_name'),
        #     ]
        # }
        return {}
