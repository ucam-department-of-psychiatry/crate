#!/usr/bin/env python
# crate_anon/nlp_manager/build_medex_itself.py

"""
Script to compile Java source for MedEx-UIMA.

Author: Rudolf Cardinal
Copyright (C) 2015-2016 Rudolf Cardinal.
License: http://www.apache.org/licenses/LICENSE-2.0
"""

import argparse
import logging
import os
import subprocess
from typing import List

from crate_anon.common.fileops import purge
from crate_anon.common.logsupport import configure_logger_for_colour


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
    return x + '\n'


def lex_freq(x: str) -> str:
    """For MedEx's lexicon.cfg: a frequency line"""
    return "{}\tFREQ".format(x)


def lex_route(x: str) -> str:
    """For MedEx's lexicon.cfg: a route line"""
    return "{}\tRUT".format(x)


def semantic_rule_engine_line(frequency: str,
                              dots_optional: bool = True) -> str:
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
    return r'        regexlist.put("^({})( |$)", "FREQ");  // RNC'.format(
        regex_str)


def frequency_rules_line(frequency: str, timex: str,
                         dots_optional: bool) -> str:
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
            regex_str += r'[{}{}]'.format(c.upper(), c.lower())
        else:
            regex_str += c
    return r'expression="{}",val="{}"'.format(regex_str, timex)


def add_lines_if_not_in(filename: str, lines: List[str]) -> None:
    """Elements of lines should not have their own \n characters."""
    with open(filename, 'r') as f:
        existing = f.readlines()  # will have trailing newlines
    log.info("Read {} lines from {}".format(len(existing), filename))
    # print(existing[-5:])
    with open(filename, 'a') as f:
        for line in lines:
            if terminate(line) not in existing:
                log.info("Adding {} line: {}".format(filename, repr(line)))
                f.write(terminate(line))


def add_lines_after_trigger(filename: str, trigger: str,
                            start_marker: str, end_marker: str,
                            lines: List[str]) -> None:
    """Elements of lines should not have their own \n characters."""
    with open(filename, 'r') as f:
        existing = f.readlines()
    log.info("Read {} lines from {}".format(len(existing), filename))
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
            log.info("Adding {} line: {}".format(filename, repr(line)))
            f.write(terminate(line))
        f.write(terminate(end_marker))
        # Write the rest
        for line in existing[index:]:
            f.write(line)


def main() -> None:
    # -------------------------------------------------------------------------
    # Arguments
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        description="Compile MedEx-UIMA itself (in Java)")
    parser.add_argument(
        '--medexdir', default=DEFAULT_MEDEX_DIR,
        help="Root directory of MedEx installation (default: {})".format(
            DEFAULT_MEDEX_DIR))
    parser.add_argument(
        '--javac', default=DEFAULT_JAVAC,
        help="Java compiler (default: {})".format(DEFAULT_JAVAC))
    parser.add_argument(
        '--deletefirst', action='store_true',
        help="Delete existing .class files first (optional)")
    parser.add_argument('--verbose', '-v', action='count', default=0,
                        help="Be verbose")
    args = parser.parse_args()

    # -------------------------------------------------------------------------
    # Logging
    # -------------------------------------------------------------------------
    loglevel = logging.DEBUG if args.verbose >= 1 else logging.INFO
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
    log.info("Executing command: {}".format(cmdargs))
    subprocess.check_call(cmdargs)


if __name__ == '__main__':
    main()
