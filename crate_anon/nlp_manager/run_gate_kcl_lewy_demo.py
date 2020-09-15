#!/usr/bin/env python

"""
crate_anon/nlp_manager/run_gate_kcl_lewy_demo.py

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
import os

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger

from crate_anon.common.constants import (
    CRATE_DIR_JAVA_CLASSES,
    DEMO_NLP_INPUT_TERMINATOR,
    DEMO_NLP_OUTPUT_TERMINATOR,
    ENVVAR_CRATE_GATE_PLUGIN_FILE,
    ENVVAR_GATE_HOME,
    ENVVAR_KCL_LEWY_BODY_DIAGNOSIS_DIR,
)
from crate_anon.common.sysops import check_call_verbose, get_envvar_or_die


def main() -> None:
    """
    Command-line entry point.
    """
    main_only_quicksetup_rootlogger(level = logging.DEBUG)
    gate_home = get_envvar_or_die(ENVVAR_GATE_HOME)
    plugin_file = get_envvar_or_die(ENVVAR_CRATE_GATE_PLUGIN_FILE)
    kcl_lewy_dir = get_envvar_or_die(ENVVAR_KCL_LEWY_BODY_DIAGNOSIS_DIR)
    check_call_verbose([
        "java",
        "-classpath", f"{CRATE_DIR_JAVA_CLASSES}:{gate_home}/lib/*",
        f"-Dgate.home={gate_home}",
        "CrateGatePipeline",
        "--pluginfile", plugin_file,
        "--gate_app", os.path.join(kcl_lewy_dir, "application.xgapp"),
        "--set_annotation", "", "DiagnosisAlmost",
        "--set_annotation", "Automatic", "cDiagnosis",
        "--input_terminator", DEMO_NLP_INPUT_TERMINATOR,
        "--output_terminator", DEMO_NLP_OUTPUT_TERMINATOR,
        "--suppress_gate_stdout",
        "--show_contents_on_crash",
        "-v", "-v",
    ])


if __name__ == "__main__":
    main()
