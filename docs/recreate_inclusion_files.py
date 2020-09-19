#!/usr/bin/env python

"""
docs/recreate_inclusion_files.py

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

**Rebuild inclusion files for documentation.**

That is, e.g. "command --help > somefile.txt".

"""

import datetime
import logging
import os
from os.path import dirname, join, realpath
import shutil
import stat
import subprocess
import sys
from typing import List

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger

from crate_anon.common.constants import (
    CrateDir,
    EnvVar,
)

log = logging.getLogger(__name__)

THIS_DIR = dirname(realpath(__file__))
DOCS_SOURCE_DIR = join(THIS_DIR, "source")
ANCILLARY_DIR = join(DOCS_SOURCE_DIR, "ancillary")
ANON_DIR = join(DOCS_SOURCE_DIR, "anonymisation")
LINKAGE_DIR = join(DOCS_SOURCE_DIR, "linkage")
NLP_DIR = join(DOCS_SOURCE_DIR, "nlp")
PREPROC_DIR = join(DOCS_SOURCE_DIR, "preprocessing")
WEB_DIR = join(DOCS_SOURCE_DIR, "website_config")

EXECUTABLE_PERMISSIONS = (
    stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR |
    stat.S_IRGRP | stat.S_IWGRP | stat.S_IXGRP |
    stat.S_IROTH | stat.S_IXOTH
)  # = 509 = 0o775; try also "stat -c '%a %n' *" to show octal permissions


def run_cmd(cmdargs: List[str],
            output_filename: str,
            timestamp: bool = False,
            comment_prefix: str = "# ",
            encoding: str = sys.getdefaultencoding(),
            executable: bool = False) -> None:
    """
    Args:
        cmdargs: command to run
        output_filename: file to write command's output to
        timestamp: add timestamp?
        comment_prefix: comment prefix for this type of output file
        encoding: encoding to use
        executable: make the output file executable?
    """
    log.info(f"Running: {cmdargs}")

    modified_env = os.environ.copy()
    modified_env[EnvVar.GENERATING_CRATE_DOCS] = "True"
    output = subprocess.check_output(
        cmdargs, env=modified_env
    ).decode(encoding)
    log.info(f"... writing to: {output_filename}")
    with open(output_filename, "wt") as f:
        f.write(output)
        if timestamp:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"\n{comment_prefix}Generated at {now}\n")
    if executable:
        os.chmod(output_filename, EXECUTABLE_PERMISSIONS)


def main():
    # -------------------------------------------------------------------------
    # ancillary
    # -------------------------------------------------------------------------
    run_cmd(["crate_make_demo_database", "--help"],
            join(ANCILLARY_DIR, "_crate_make_demo_database_help.txt"))
    run_cmd(["crate_test_anonymisation", "--help"],
            join(ANCILLARY_DIR, "_crate_test_anonymisation_help.txt"))
    run_cmd(["crate_test_extract_text", "--help"],
            join(ANCILLARY_DIR, "_crate_test_extract_text_help.txt"))

    # -------------------------------------------------------------------------
    # anonymisation
    # -------------------------------------------------------------------------
    run_cmd(["crate_anonymise", "--help"],
            join(ANON_DIR, "_crate_anonymise_help.txt"))
    run_cmd(["crate_anonymise_multiprocess", "--help"],
            join(ANON_DIR, "_crate_anonymise_multiprocess_help.txt"))
    run_cmd(["crate_anonymise", "--democonfig"],
            join(ANON_DIR, "_specimen_anonymiser_config.ini"))
    log.info("Manually generated: minimal_anonymiser_config.ini")

    # -------------------------------------------------------------------------
    # linkage
    # -------------------------------------------------------------------------
    run_cmd(["crate_bulk_hash", "--help"],
            join(LINKAGE_DIR, "_crate_bulk_hash_help.txt"))

    # -------------------------------------------------------------------------
    # nlp
    # -------------------------------------------------------------------------
    run_cmd(["crate_show_crate_gate_pipeline_options"],
            join(NLP_DIR, "_CrateGatePipeline_help.txt"))
    run_cmd(["crate_show_crate_medex_pipeline_options"],
            join(NLP_DIR, "_CrateMedexPipeline_help.txt"))
    run_cmd(["crate_nlp_build_gate_java_interface", "--help"],
            join(NLP_DIR, "_crate_nlp_build_gate_java_interface_help.txt"))
    run_cmd(["crate_nlp_build_medex_itself", "--help"],
            join(NLP_DIR, "_crate_nlp_build_medex_itself_help.txt"))
    run_cmd(["crate_nlp_build_medex_java_interface", "--help"],
            join(NLP_DIR, "_crate_nlp_build_medex_java_interface_help.txt"))
    run_cmd(["crate_nlp", "--describeprocessors"],
            join(NLP_DIR, "_crate_nlp_describeprocessors.txt"))
    run_cmd(["crate_nlp", "--help"],
            join(NLP_DIR, "_crate_nlp_help.txt"))
    run_cmd(["crate_nlp_multiprocess", "--help"],
            join(NLP_DIR, "_crate_nlp_multiprocess_help.txt"))
    run_cmd(["crate_nlp", "--democonfig"],
            join(NLP_DIR, "_specimen_nlp_config_file.ini"))
    run_cmd(["crate_nlp_webserver_initialize_db", "--help"],
            join(NLP_DIR, "_crate_nlp_webserver_initialize_db_help.txt"))
    run_cmd(["crate_nlp_webserver_print_demo", "--help"],
            join(NLP_DIR, "_crate_nlp_webserver_print_demo_help.txt"))
    run_cmd(["crate_nlp_webserver_print_demo", "--config"],
            join(NLP_DIR, "_nlp_webserver_demo_config.ini"))
    run_cmd(["crate_nlp_webserver_print_demo", "--processors"],
            join(NLP_DIR, "_nlp_webserver_demo_processors.py"),
            executable=True)
    run_cmd(["crate_nlp_webserver_pserve", "--help"],
            join(NLP_DIR, "_crate_nlp_webserver_pserve_help.txt"))
    run_cmd(["crate_nlp_webserver_pserve", "--help"],
            join(NLP_DIR, "_crate_nlp_webserver_pserve_help.txt"))
    run_cmd(["crate_nlp_webserver_launch_gunicorn", "--help"],
            join(NLP_DIR, "_crate_nlp_webserver_launch_gunicorn_help.txt"))
    run_cmd(["crate_nlp_webserver_launch_celery", "--help"],
            join(NLP_DIR, "_crate_nlp_webserver_launch_celery_help.txt"))
    shutil.copy(join(CrateDir.NLP_MANAGER, "specimen_gate_plugin_file.ini"),
                join(NLP_DIR, "_specimen_gate_plugin_file.ini"))
    shutil.copy(join(CrateDir.NLPRP, "nlprp_test_client.py"),
                join(NLP_DIR, "_nlprp_test_client.py"))
    shutil.copy(join(CrateDir.NLPRP, "nlprp_test_server.py"),
                join(NLP_DIR, "_nlprp_test_server.py"))

    # -------------------------------------------------------------------------
    # preprocessing
    # -------------------------------------------------------------------------
    run_cmd(["crate_fetch_wordlists", "--help"],
            join(PREPROC_DIR, "_crate_fetch_wordlists_help.txt"))
    run_cmd(["crate_fuzzy_id_match", "--allhelp"],
            join(PREPROC_DIR, "_crate_fuzzy_id_match_help.txt"))
    run_cmd(["crate_postcodes", "--help"],
            join(PREPROC_DIR, "_crate_postcodes_help.txt"))
    run_cmd(["crate_preprocess_pcmis", "--help"],
            join(PREPROC_DIR, "_crate_preprocess_pcmis_help.txt"))
    run_cmd(["crate_preprocess_rio", "--help"],
            join(PREPROC_DIR, "_crate_preprocess_rio_help.txt"))

    # -------------------------------------------------------------------------
    # website_config
    # -------------------------------------------------------------------------
    run_cmd(["crate_django_manage", "--help"],
            join(WEB_DIR, "_crate_django_manage_help.txt"))

    run_cmd(["crate_django_manage", "help", "changepassword"],
            join(WEB_DIR, "_crate_django_manage_changepassword_help.txt"))
    run_cmd(["crate_django_manage", "help", "collectstatic"],
            join(WEB_DIR, "_crate_django_manage_collectstatic_help.txt"))
    run_cmd(["crate_django_manage", "help", "createsuperuser"],
            join(WEB_DIR, "_crate_django_manage_createsuperuser_help.txt"))
    run_cmd(["crate_django_manage", "help", "email_rdbm"],
            join(WEB_DIR, "_crate_django_manage_email_rdbm_help.txt"))
    run_cmd(["crate_django_manage", "help", "fetch_optouts"],
            join(WEB_DIR, "_crate_django_manage_fetch_optouts_help.txt"))
    run_cmd(["crate_django_manage", "help", "lookup_consent"],
            join(WEB_DIR, "_crate_django_manage_lookup_consent_help.txt"))
    run_cmd(["crate_django_manage", "help", "lookup_patient"],
            join(WEB_DIR, "_crate_django_manage_lookup_patient_help.txt"))
    run_cmd(["crate_django_manage", "help", "populate"],
            join(WEB_DIR, "_crate_django_manage_populate_help.txt"))
    run_cmd(["crate_django_manage", "help", "resubmit_unprocessed_tasks"],
            join(WEB_DIR, "_crate_django_manage_resubmit_unprocessed_tasks_help.txt"))  # noqa
    run_cmd(["crate_django_manage", "help", "runcpserver"],
            join(WEB_DIR, "_crate_django_manage_runcpserver_help.txt"))
    run_cmd(["crate_django_manage", "help", "runserver"],
            join(WEB_DIR, "_crate_django_manage_runserver_help.txt"))
    run_cmd(["crate_django_manage", "help", "test_email"],
            join(WEB_DIR, "_crate_django_manage_test_email_help.txt"))

    run_cmd(["crate_launch_celery", "--help"],
            join(WEB_DIR, "_crate_launch_celery_help.txt"))
    run_cmd(["crate_launch_django_server", "--help"],
            join(WEB_DIR, "_crate_launch_django_server_help.txt"))
    run_cmd(["crate_print_demo_crateweb_config"],
            join(WEB_DIR, "_specimen_web_config.py"))
    log.warning("Skipping crate_windows_service_help.txt (requires Windows)")

    log.info("Done.")


if __name__ == "__main__":
    main_only_quicksetup_rootlogger()
    main()
