#!/usr/bin/env python

"""
crate_anon/nlp_manager/run_gate_kcl_lewy_demo.py

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

**Run the GATE ANNIE (people and places) demo via CRATE.**

"""

import logging
import os

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger

from crate_anon.common.constants import (
    CratePath,
    DEMO_NLP_INPUT_TERMINATOR,
    DEMO_NLP_OUTPUT_TERMINATOR,
    EnvVar,
)
from cardinal_pythonlib.subproc import check_call_verbose
from cardinal_pythonlib.sysops import get_envvar_or_die

THIS_DIR = os.path.dirname(os.path.abspath(__file__))
GATE_LOG_CONFIG_DIR = os.path.join(THIS_DIR, "gate_log_config")


def main() -> None:
    """
    Command-line entry point.
    """
    main_only_quicksetup_rootlogger(level=logging.DEBUG)
    gate_home = get_envvar_or_die(EnvVar.GATE_HOME)
    plugin_file = get_envvar_or_die(EnvVar.CRATE_GATE_PLUGIN_FILE)
    kcl_lewy_dir = get_envvar_or_die(EnvVar.KCL_LEWY_BODY_DIAGNOSIS_DIR)
    classpath = os.pathsep.join(
        [CratePath.JAVA_CLASSES_DIR, f"{gate_home}/lib/*", GATE_LOG_CONFIG_DIR]
    )
    check_call_verbose(
        [
            "java",
            "-classpath",
            classpath,
            f"-Dgate.home={gate_home}",
            "CrateGatePipeline",
            "--pluginfile",
            plugin_file,
            "--gate_app",
            os.path.join(kcl_lewy_dir, "application.xgapp"),
            "--set_annotation",
            "",
            "DiagnosisAlmost",
            "--set_annotation",
            "Automatic",
            "cDiagnosis",
            "--input_terminator",
            DEMO_NLP_INPUT_TERMINATOR,
            "--output_terminator",
            DEMO_NLP_OUTPUT_TERMINATOR,
            "--suppress_gate_stdout",
            "--show_contents_on_crash",
        ]
    )


if __name__ == "__main__":
    main()
