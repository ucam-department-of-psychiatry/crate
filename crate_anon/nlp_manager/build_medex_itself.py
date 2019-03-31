#!/usr/bin/env python

"""
crate_anon/nlp_manager/build_medex_itself.py

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

**Script to compile (and modify slightly) Java source for MedEx-UIMA.**

"""

import argparse
import logging
import os
import subprocess
from typing import Dict, List, Tuple, Union

from cardinal_pythonlib.fileops import purge
from cardinal_pythonlib.logs import configure_logger_for_colour

log = logging.getLogger(__name__)

DEFAULT_MEDEX_DIR = os.path.join(os.path.expanduser('~'), 'dev',
                                 'Medex_UIMA_1.3.6')
DEFAULT_JAVA = 'java'
DEFAULT_JAVAC = 'javac'

EXTRA_ROUTES = [
    "i/m",
    "i.m.",
    "i. m.",
    "intramuscularly",
    "intramuscular inj.",
    "intramuscular injection",
    "inh",
    "inh.",
    "i/v",
    "i.v.",
    "i. v.",
    "nasal",
    "nasally",
    "nebs",
    "nebulised",
    "nebuliser",
    "nebulized",
    "nebulizer",
    "ng",
    "n/g",
    "n.g.",
    "n. g.",
    "nasogastric",
    "nasogastrically",
    "nj",
    "n/j",
    "n.j.",
    "n. j.",
    "p/o",
    "p.o.",
    "p. o.",
    "pr",
    "p/r",
    "p.r.",
    "p. r.",
    "s/c",
    "s.c.",
    "s. c.",
    "top",
    "top.",
]
EXTRA_FREQUENCIES = [  # Tuples of (literal, TIMEX3)
    # EXTRA FOR UK FREQUENCIES; see
    # http://www.evidence.nhs.uk/formulary/bnf/current/general-reference/latin-abbreviations  # noqa
    # TIMEX3 codes:
    # http://www.timeml.org/tempeval2/tempeval2-trial/guidelines/timex3guidelines-072009.pdf

    # qqh, quarta quaque hora
    ("q.q.h.", "R1P4H"),

    # qds, quater die sumendum; MUST BE BEFORE COMPETING "qd" (= per day)
    # expression, e.g. in frequency_rules:
    # expression="[Qq]\.?[ ]?[Dd]\.?",val="R1P24H"
    ("q.d.s.", "R1P6H"),

    # tds, ter die sumendum
    ("t.d.s.", "R1P8H"),

    # bd, bis die
    ("b.d.", "R1P12H"),

    # od, omni die
    ("o.d.", "R1P24H"),

    # mane
    ("mane", "R1P24H"),

    # om, omni mane
    ("o.m.", "R1P24H"),

    # nocte
    ("nocte", "R1P24H"),

    # on, omni nocte -- beware also the word "on"...
    ("o.n.", "R1P24H"),

    # fortnightly and variants
    ("fortnightly", "R1P2W"),  # W: page 9 of TIMEX3 PDF above
    ("2 weekly", "R1P2W"),
    ("two weekly", "R1P2W"),

    # monthly
    ("monthly", "R1P1M"),  # M: page 8 of TIMEX3 PDF above
]
DO_NOT_REMOVE_DOTS = [
    'o.n.'
    # the word "on" is too confusing; e.g. "Start olanzapine 5mg nocte." is
    # fine; "Start olanzapine 5mg on." is tolerable, but too easily confused
    # with "Start olanzapine 5mg on Tuesday."
]

SEM_ENG_TRIGGER_LINE_TRIMMED = "Map regexlist = new Hashtable();"
FREQ_RULE_TRIGGER_LINE_TRIMMED = "FREQUENCY:"
SOURCE_START_MARKER = "// START CRATE MODIFICATIONS"
SOURCE_END_MARKER = "// END CRATE MODIFICATIONS"


def terminate(x: str) -> str:
    """
    Terminates its input with a newline.
    """
    return x + '\n'


def lex_freq(x: str) -> str:
    """
    For MedEx's ``lexicon.cfg``: creates a frequency line.
    """
    return f"{x}\tFREQ"


def lex_route(x: str) -> str:
    """
    For MedEx's ``lexicon.cfg``: creates a route line.
    """
    return f"{x}\tRUT"


def semantic_rule_engine_line(frequency: str,
                              dots_optional: bool = True) -> str:
    """
    For MedEx: create a semantic rule engine line (a line of Java to be
    inserted).

    Args:
        frequency: string representing the frequency, e.g. "b.d."
        dots_optional: if ``frequency`` contains full stops, are they
            optional?

    Returns:
        a line of Java code
    """
    # NB case-insensitive regexes in SemanticRuleEngine.java, so ignore case
    # here
    # If you need to put in a \, double it to \\ for Java's benefit.
    regex_str = ''
    for c in frequency:
        if c == ' ':
            regex_str += r'\\s+'
        elif c == '.':
            if dots_optional:
                regex_str += r'\\.?\\s*'
            else:
                regex_str += r'\\.\\s*'
        else:
            regex_str += c
    return fr'        regexlist.put("^({regex_str})( |$)", "FREQ");  // RNC'


def frequency_rules_line(frequency: str, timex: str,
                         dots_optional: bool) -> str:
    """
    Creates a line for MedEx's ``frequency_rules`` file.

    Args:
        frequency: the string representing a drug frequency, e.g. "b.d."
        timex: a TIMEX version of this frequency
        dots_optional: if ``frequency`` contains full stops, are they
            optional?

    Returns:
        a line to go into the ``frequency_rules`` file

    """
    # NB case-sensitive regexes in Rule.java, so offer upper- and lower-case
    # alternatives here.
    # No need for word boundaries with \b, since at this stage all words have
    # already been separated by the tokenization process.
    regex_str = ''
    for c in frequency:
        if c == ' ':
            regex_str += r'\s+'
        elif c == '.':
            if dots_optional:
                regex_str += r'\.?\s?'
            else:
                regex_str += r'\.\s?'
        elif c.isalpha():
            # Case-insensitive here.
            regex_str += fr'[{c.upper()}{c.lower()}]'
        else:
            regex_str += c
    return fr'expression="{regex_str}",val="{timex}"'


def add_lines_if_not_in(filename: str, lines: List[str]) -> None:
    r"""
    Adds lines to a file, if they're not already there.

    Args:
        filename: name of file to modify
        lines: lines to insert

    Elements of lines should not have their own ``\n`` characters.
    """
    with open(filename, 'r') as f:
        existing = f.readlines()  # will have trailing newlines
    log.info(f"Read {len(existing)} lines from {filename}")
    # print(existing[-5:])
    with open(filename, 'a') as f:
        for line in lines:
            if terminate(line) not in existing:
                log.info(f"Adding {filename} line: {line!r}")
                f.write(terminate(line))


def add_lines_after_trigger(filename: str, trigger: str,
                            start_marker: str, end_marker: str,
                            lines: List[str]) -> None:
    r"""
    Adds lines to a file, after a triggering line.

    Args:
        filename:
            name of file to modify
        trigger:
            line that begins the section of interest; we don't start paying
            attention until this is encountered
        start_marker:
            see below
        end_marker:
            see below
        lines:
            lines to insert

    Immediately after we've encountered ``trigger``, we insert
    ``start_marker``, then ``lines``, then ``end_marker``.

    If the file already has such a block, we chop out the old block before
    inserting the new.

    Elements of lines should not have their own ``\n`` characters.
    """
    with open(filename, 'r') as f:
        existing = f.readlines()
    log.info(f"Read {len(existing)} lines from {filename}")
    with open(filename, 'w') as f:
        index = 0
        for line in existing:
            f.write(line)
            index += 1
            if line.strip() == trigger:
                break
        # ... index now pointing to one after the trigger line
        # Excise an existing block of ours?
        if (index < len(existing) and
                existing[index] == terminate(start_marker)):
            while (index < len(existing) and
                   existing[index] != terminate(end_marker)):
                index += 1
            index += 1  # line after end_marker
        # Add stuff
        f.write(terminate(start_marker))
        for line in lines:
            log.info(f"Adding {filename} line: {repr(line)}")
            f.write(terminate(line))
        f.write(terminate(end_marker))
        # Write the rest
        for line in existing[index:]:
            f.write(line)


def replace_in_file(filename: str, changes: List[Tuple[str, str]],
                    count: int = -1, encoding: str = 'utf8',
                    backup_suffix: str = "~") -> None:
    """
    Replaces content in a file.

    Args:
        filename:
            name of file to modify
        changes:
            list of ``old, new`` tuples; we will replace ``old`` by ``new`` in
            each case
        count:
            up to how many times should we perform the replacement?
            See :func:`str.replace`.
        encoding:
            character encoding to be used
        backup_suffix:
            we'll create a backup file; what should we append to the filename
            to give the name of the backup file?
    """
    log.info(f"Replacing code in file: {filename}")
    # Read contents
    with open(filename, encoding=encoding) as input_file:
        original_content = input_file.read()
    # Replace
    new_content = original_content
    for old, new in changes:
        new_content = new_content.replace(old, new, count)
    # Check for differences
    if new_content == original_content:
        log.info("... nothing to do")
        return
    # Make backup, if different
    backup_name = filename + backup_suffix
    os.rename(filename, backup_name)
    log.info(f"... backup is: {repr(backup_name)}")
    # Write out new
    with open(filename, 'w', encoding=encoding) as output_file:
        output_file.write(new_content)


def main() -> None:
    """
    Command-line processor. See command-line help.
    """
    # -------------------------------------------------------------------------
    # Arguments
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description="Compile MedEx-UIMA itself (in Java)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        '--medexdir', default=DEFAULT_MEDEX_DIR,
        help="Root directory of MedEx installation")
    parser.add_argument(
        '--javac', default=DEFAULT_JAVAC,
        help="Java compiler")
    parser.add_argument(
        '--deletefirst', action='store_true',
        help="Delete existing .class files first (optional)")
    parser.add_argument('--verbose', '-v', action='store_true',
                        help="Be verbose")
    args = parser.parse_args()

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    loglevel = logging.DEBUG if args.verbose else logging.INFO
    rootlogger = logging.getLogger()
    configure_logger_for_colour(rootlogger, level=loglevel)

    # -------------------------------------------------------------------------
    # Add lexicon entries
    # -------------------------------------------------------------------------
    lexfilename = os.path.join(args.medexdir, 'resources', 'lexicon.cfg')
    lexlines = [lex_route(route)
                for route in EXTRA_ROUTES]
    for frequency, _ in EXTRA_FREQUENCIES:
        lexlines.append(lex_freq(frequency))
        if '.' in frequency:
            lexlines.append(lex_freq(frequency.replace('.', '. ')))
            if frequency not in DO_NOT_REMOVE_DOTS:
                lexlines.append(lex_freq(frequency.replace('.', '')))
    # Need to add variants, e.g. "om" for "o.m."?
    add_lines_if_not_in(lexfilename, lexlines)

    # -------------------------------------------------------------------------
    # Add frequency tags to SemanticRuleEngine.java
    # -------------------------------------------------------------------------
    semengfilename = os.path.join(args.medexdir, 'src', 'org', 'apache',
                                  'medex', 'SemanticRuleEngine.java')
    semlines = [semantic_rule_engine_line(frequency,
                                          frequency not in DO_NOT_REMOVE_DOTS)
                for frequency, _ in EXTRA_FREQUENCIES]
    add_lines_after_trigger(semengfilename, SEM_ENG_TRIGGER_LINE_TRIMMED,
                            SOURCE_START_MARKER, SOURCE_END_MARKER,
                            semlines)

    # -------------------------------------------------------------------------
    # Add frequency tags to frequency_rules
    # -------------------------------------------------------------------------
    freqrulefilename = os.path.join(args.medexdir, 'resources', 'TIMEX',
                                    'rules', 'frequency_rules')
    frlines = [frequency_rules_line(frequency, timex,
                                    frequency not in DO_NOT_REMOVE_DOTS)
               for frequency, timex in EXTRA_FREQUENCIES]
    add_lines_after_trigger(freqrulefilename, FREQ_RULE_TRIGGER_LINE_TRIMMED,
                            SOURCE_START_MARKER, SOURCE_END_MARKER,
                            frlines)

    # -------------------------------------------------------------------------
    # Fix bugs! Argh.
    # -------------------------------------------------------------------------
    bugfixes = [
        {
            "filename": os.path.join(args.medexdir, 'src', 'org', 'apache',
                                     'NLPTools', 'Document.java'),
            "changes": [
                {
                    "comment": """
Medex confuses & and &&, leading to

Exception in thread "main" java.lang.StringIndexOutOfBoundsException: String index out of range: 2
    at java.lang.String.charAt(Unknown Source)
    at org.apache.NLPTools.Document.<init>(Document.java:134)
    at org.apache.medex.MedTagger.run_batch_medtag(MedTagger.java:256)
    at CrateMedexPipeline.processInput(CrateMedexPipeline.java:302)
    at CrateMedexPipeline.<init>(CrateMedexPipeline.java:128)
    at CrateMedexPipeline.main(CrateMedexPipeline.java:320)
                    """,  # noqa
                    "wrong": r"while(cur_pos<llen & (txt.charAt(cur_pos)==' ' || txt.charAt(cur_pos)=='\n' || txt.charAt(cur_pos)=='\r') ){",  # noqa
                    "right": r"while(cur_pos<llen && (txt.charAt(cur_pos)==' ' || txt.charAt(cur_pos)=='\n' || txt.charAt(cur_pos)=='\r') ){"  # noqa
                    # -----------------------------^
                },
            ],
        },
        # ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
        {
            "filename": os.path.join(args.medexdir, 'src', 'org', 'apache',
                                     'algorithms', 'SuffixArray.java'),
            "changes": [
                {
                    "comment": """

java.lang.StringIndexOutOfBoundsException: String index out of range: 1
    at java.lang.String.charAt(Unknown Source)
    at org.apache.algorithms.SuffixArray.construct_tree_word(SuffixArray.java:375)
    at org.apache.algorithms.SuffixArray.re_build(SuffixArray.java:97)
    at org.apache.algorithms.SuffixArray.<init>(SuffixArray.java:60)
    at org.apache.medex.MedTagger.medtagging(MedTagger.java:359)
    at org.apache.medex.MedTagger.run_batch_medtag(MedTagger.java:264)
    at CrateMedexPipeline.processInput(CrateMedexPipeline.java:302)
    at CrateMedexPipeline.<init>(CrateMedexPipeline.java:128)
    at CrateMedexPipeline.main(CrateMedexPipeline.java:320)

Offending code in SuffixArray.java:

    for (int i=0;i<this.N;i++){
        int pos=this.SA[i];
        if (this.otext.charAt(pos) != ' ' && this.otext.charAt(pos) != '\n' && this.otext.charAt(pos) != this.end_char && (pos == 0 || (this.otext.charAt(pos-1) == ' ' || this.otext.charAt(pos-1) == '\n'))){
            this.insert_SF_tree(this.SA[i], 0, 0); //# 0 denote the root in __SA;
        }
    }

The bug may relate to what's in SA[i]... but as a simple fix:

                    """,  # noqa
                    "wrong": r"if (this.otext.charAt(pos) != ' ' && this.otext.charAt(pos) != '\n' && this.otext.charAt(pos) != this.end_char && (pos == 0 || (this.otext.charAt(pos-1) == ' ' || this.otext.charAt(pos-1) == '\n'))){",  # noqa
                    "right": r"if (pos < this.otext.length() && this.otext.charAt(pos) != ' ' && this.otext.charAt(pos) != '\n' && this.otext.charAt(pos) != this.end_char && (pos == 0 || (this.otext.charAt(pos-1) == ' ' || this.otext.charAt(pos-1) == '\n'))){"  # noqa
                    # -------------^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                },
            ],
        },
    ]  # type: List[Dict[str, Union[str, List[Dict[str, str]]]]]

    _ = """

BUGS IN MEDEX-UIMA NOT YET FIXED:

java.lang.ArrayIndexOutOfBoundsException: -1
    at java.util.Vector.elementData(Unknown Source)
    at java.util.Vector.get(Unknown Source)
    at org.apache.NLPTools.SentenceBoundary.detect_boundaries(SentenceBoundary.java:329)
    at org.apache.medex.MedTagger.medtagging(MedTagger.java:354)
    at org.apache.medex.MedTagger.run_batch_medtag(MedTagger.java:264)
    at CrateMedexPipeline.processInput(CrateMedexPipeline.java:312)
    at CrateMedexPipeline.runPipeline(CrateMedexPipeline.java:138)
    at CrateMedexPipeline.<init>(CrateMedexPipeline.java:112)
    at CrateMedexPipeline.main(CrateMedexPipeline.java:330)

java.lang.NullPointerException
    at org.apache.algorithms.SuffixArray.search(SuffixArray.java:636)
    at org.apache.medex.MedTagger.medtagging(MedTagger.java:362)
    at org.apache.medex.MedTagger.run_batch_medtag(MedTagger.java:264)
    at CrateMedexPipeline.processInput(CrateMedexPipeline.java:312)
    at CrateMedexPipeline.runPipeline(CrateMedexPipeline.java:138)
    at CrateMedexPipeline.<init>(CrateMedexPipeline.java:112)
    at CrateMedexPipeline.main(CrateMedexPipeline.java:330)

... frankly, it's just badly written. That's clearly why it uses the "catch
all exceptions" strategy, but one would imagine the errors are unintentional
(certainly the &/&& one!) or else they wouldn't print a stack trace and chug
on.

    """  # noqa

    for bf in bugfixes:
        filename = bf["filename"]
        changes = []  # type: List[Tuple[str, str]]
        for change in bf["changes"]:
            changes.append((change["wrong"], change["right"]))
        replace_in_file(filename, changes)

    # -------------------------------------------------------------------------
    # Clean up first?
    # -------------------------------------------------------------------------
    if args.deletefirst:
        purge(args.medexdir, '*.class')

    # -------------------------------------------------------------------------
    # Compile
    # -------------------------------------------------------------------------
    bindir = os.path.join(args.medexdir, 'bin')
    classpath = os.pathsep.join([
        os.path.join(args.medexdir, 'src'),
        os.path.join(args.medexdir, 'lib', '*'),  # jar files
    ])
    classpath_options = ['-classpath', classpath]
    os.chdir(args.medexdir)
    cmdargs = (
        [args.javac] +
        classpath_options +
        ['src/org/apache/medex/Main.java'] +
        # ... compiling this compiles everything else necessary
        ['-d', bindir]  # put the binaries here
    )
    log.info(f"Executing command: {cmdargs}")
    subprocess.check_call(cmdargs)


if __name__ == '__main__':
    main()
