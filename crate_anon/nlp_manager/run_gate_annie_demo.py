#!/usr/bin/env python

"""
crate_anon/nlp_manager/run_gate_annie_demo.py

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

**Run the GATE ANNIE (people and places) demo via CRATE.**

"""

import logging

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger

from crate_anon.common.constants import (
    CrateDir,
    DEMO_NLP_INPUT_TERMINATOR,
    DEMO_NLP_OUTPUT_TERMINATOR,
    EnvVar,
)
from cardinal_pythonlib.subproc import check_call_verbose
from cardinal_pythonlib.sysops import get_envvar_or_die

log = logging.getLogger(__name__)


def main() -> None:
    """
    Command-line entry point.
    """
    main_only_quicksetup_rootlogger(level=logging.DEBUG)
    gate_home = get_envvar_or_die(EnvVar.GATE_HOME)
    log.info(f"Note the unrealistic use of {DEMO_NLP_INPUT_TERMINATOR!r} as "
             f"an end-of-input marker. Don't use that for real!")
    check_call_verbose([
        "java",
        "-classpath", f"{CrateDir.JAVA_CLASSES}:{gate_home}/lib/*",
        f"-Dgate.home={gate_home}",
        "CrateGatePipeline",
        "--annotation", "Person",
        "--annotation", "Location",
        "--input_terminator", DEMO_NLP_INPUT_TERMINATOR,
        "--output_terminator", DEMO_NLP_OUTPUT_TERMINATOR,
        "--log_tag", ".",
        "-v", "-v",
        "--demo"
    ])


if __name__ == "__main__":
    main()
