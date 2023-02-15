#!/usr/bin/env python

"""
crate_anon/nlp_manager/run_crate_nlp_demo.py

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

**Run the build-in NLP tools for a quick command-line test.**

"""

import argparse
import logging
from pprint import pformat
from typing import Any, Dict, List

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from rich_argparse import ArgumentDefaultsRichHelpFormatter

from crate_anon.common.constants import DEMO_NLP_INPUT_TERMINATOR
from crate_anon.common.inputfunc import gen_chunks_from_files
from crate_anon.nlp_manager.all_processors import (
    get_nlp_parser_class,
    possible_local_processor_names_without_external_tools,
)
from crate_anon.nlp_manager.base_nlp_parser import BaseNlpParser

log = logging.getLogger(__name__)


# =============================================================================
# Processors
# =============================================================================


def get_processors(processor_names: List[str]) -> List[BaseNlpParser]:
    """
    Fetches CRATE NLP processors by name.
    """
    processors = []  # type: List[BaseNlpParser]
    for name in processor_names:
        cls = get_nlp_parser_class(name)
        if not cls:
            raise ValueError(f"Unknown processor: {name}")
        processor = cls(nlpdef=None, cfg_processor_name=None)
        if isinstance(processor, BaseNlpParser):
            processors.append(processor)
        else:
            raise ValueError(
                f"Processor {name} is not a CRATE build-in NLP processor"
            )
    return processors


# =============================================================================
# Do the work
# =============================================================================


def process_text(text: str, processors: List[BaseNlpParser]) -> None:
    """
    Runs a single pieces of text through multiple NLP processors, and reports
    the output.
    """
    log.debug(f"Processing text:\n{text}")
    results = {}  # type: Dict[str, List[Dict[str, Any]]]
    for processor in processors:
        log.debug(f"- Processor: {processor.nlprp_name()}.")
        for tablename, nlp_values in processor.parse(text):
            if not nlp_values:
                continue
            results_this_proc = results.setdefault(tablename, [])
            results_this_proc.append(nlp_values)
    pretty = pformat(results)
    log.info(f"Results:\n" f"{pretty}")
    log.debug("- Text processing complete.")


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    """
    Command-line entry point.
    """
    all_processors = "all"
    possible_proc_names = (
        possible_local_processor_names_without_external_tools()
    )  # noqa
    possible_processor_options = [all_processors] + possible_proc_names

    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        description="Demonstrate CRATE's built-in Python NLP tools",
        formatter_class=ArgumentDefaultsRichHelpFormatter,
    )
    parser.add_argument(
        "inputs", type=str, nargs="+", help="Input files (use '-' for stdin)"
    )
    parser.add_argument(
        "--terminator",
        type=str,
        default=DEMO_NLP_INPUT_TERMINATOR,
        help=(
            "Single-line terminator separating input chunks in an input file."
        ),
    )
    parser.add_argument(
        "--processors",
        type=str,
        required=True,
        nargs="+",
        metavar="PROCESSOR",
        choices=possible_processor_options,
        help=f"NLP processor(s) to apply. Possibilities: "
        f"{','.join(possible_processor_options)}",
    )
    parser.add_argument("--verbose", action="store_true", help="Be verbose")

    args = parser.parse_args()
    main_only_quicksetup_rootlogger(
        level=logging.DEBUG if args.verbose else logging.INFO
    )

    log.debug(f"Input terminator: {args.terminator!r}")
    if all_processors in args.processors:
        processors = get_processors(possible_proc_names)
    else:
        processors = get_processors(args.processors)
    for text in gen_chunks_from_files(
        filenames=args.inputs, chunk_terminator_line=args.terminator
    ):
        if not text:
            continue
        process_text(text, processors)
    log.info("Done.")


if __name__ == "__main__":
    main()
