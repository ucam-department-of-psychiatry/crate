#!/usr/bin/env python

"""
docs/recreate_inclusion_files.py

===============================================================================

    Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).

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

**Rebuild inclusion files for documentation.**

That is, e.g. "command --help > somefile.txt".

"""

import argparse
import datetime
import logging
import os
from os.path import join
import shutil
import stat
import subprocess
import sys
from typing import List

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger

from crate_anon.common.constants import CratePath, EnvVar
from crate_anon.version import CRATE_VERSION
from create_all_autodocs import DevPath, RST_COPYRIGHT_COMMENT

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

DEFAULT_ENCODING = sys.getdefaultencoding()

EXECUTABLE_PERMISSIONS = (
    stat.S_IRUSR
    | stat.S_IWUSR
    | stat.S_IXUSR
    | stat.S_IRGRP
    | stat.S_IWGRP
    | stat.S_IXGRP
    | stat.S_IROTH
    | stat.S_IXOTH
)  # = 509 = 0o775; try also "stat -c '%a %n' *" to show octal permissions


# =============================================================================
# Capture command output
# =============================================================================


def run_cmd(
    cmdargs: List[str],
    output_filename: str,
    timestamp: bool = False,
    comment_prefix: str = "# ",
    encoding: str = DEFAULT_ENCODING,
    executable: bool = False,
) -> None:
    """
    Run a command and store its output in a file.

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
    output = subprocess.check_output(cmdargs, env=modified_env).decode(
        encoding
    )
    log.info(f"... writing to: {output_filename}")
    with open(output_filename, "wt") as f:
        f.write(output)
        if timestamp:
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"\n{comment_prefix}Generated at {now}\n")
    if executable:
        os.chmod(output_filename, EXECUTABLE_PERMISSIONS)


# =============================================================================
# Catalogue programs available from the command line
# =============================================================================


def get_bash_completion_commands(
    prefix: str, encoding: str = DEFAULT_ENCODING
) -> List[str]:
    """
    Get available commands starting with the prefix.
    Roughly equivalent to typing the prefix, then pressing Tab in Bash.
    See

    - https://unix.stackexchange.com/questions/151118/understand-compgen-builtin-command
    - https://stackoverflow.com/questions/5460923/run-bash-built-in-commands-in-python

    Args:
        prefix:
            Command prefix.
        encoding:
            Encoding to use.

    Returns:
        A sorted list of possible commands.
    """  # noqa
    subcommand = " ".join(
        ["compgen", "-c", prefix]  # bash built-in  # list possible commands
    )
    output = subprocess.check_output(
        [
            "bash",  # fire up bash
            "-c",  # and run the next (single string!) argument as a command:
            subcommand,
        ]
    ).decode(encoding)
    possibilities = sorted(filter(None, output.split("\n")))
    return possibilities


def make_command_line_index_help(filename: str) -> None:
    """
    Make an RST index of CRATE commands (i.e. programs you can run from the
    command line). Write it to the filename specified.

    For hyperlinks to work, the help must contain a label with the same name as
    each command.
    """
    # Get all possible CRATE-related commands:
    commands = get_bash_completion_commands("crate_")
    commands_text = ""
    for c in commands:
        commands_text += f"""
:ref:`{c} <{c}>`
"""
    full_content = f"""{RST_COPYRIGHT_COMMENT}

Index of CRATE commands
=======================
{commands_text}
(Documentation built with CRATE {CRATE_VERSION}.)
"""
    with open(filename, "wt") as f:
        f.write(full_content)


# =============================================================================
# main
# =============================================================================


def main():
    """
    - Build an index of all commands.
    - Generate specimen help files, demo config files, etc., and save them
      for the help.
    """
    # -------------------------------------------------------------------------
    # Options
    # -------------------------------------------------------------------------
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip_medex",
        action="store_true",
        help="Don't try to build Medex files",
        default=False,
    )
    args = parser.parse_args()

    # -------------------------------------------------------------------------
    # Command-line index
    # -------------------------------------------------------------------------
    make_command_line_index_help(
        join(DevPath.DOCS_AUTODOC_EXTRA_DIR, "_command_line_index.rst")
    )

    # Follow the sequence in setup.py for clarity:

    # -------------------------------------------------------------------------
    # Preprocessing
    # -------------------------------------------------------------------------
    run_cmd(
        ["crate_fetch_wordlists", "--help"],
        join(DevPath.DOCS_PREPROC_DIR, "_crate_fetch_wordlists_help.txt"),
    )
    run_cmd(
        ["crate_fuzzy_id_match", "--allhelp"],
        join(DevPath.DOCS_PREPROC_DIR, "_crate_fuzzy_id_match_help.txt"),
    )
    run_cmd(
        ["crate_postcodes", "--help"],
        join(DevPath.DOCS_PREPROC_DIR, "_crate_postcodes_help.txt"),
    )
    run_cmd(
        ["crate_preprocess_pcmis", "--help"],
        join(DevPath.DOCS_PREPROC_DIR, "_crate_preprocess_pcmis_help.txt"),
    )
    run_cmd(
        ["crate_preprocess_rio", "--help"],
        join(DevPath.DOCS_PREPROC_DIR, "_crate_preprocess_rio_help.txt"),
    )
    run_cmd(
        ["crate_preprocess_systmone", "--help"],
        join(DevPath.DOCS_PREPROC_DIR, "_crate_preprocess_systmone_help.txt"),
    )

    # -------------------------------------------------------------------------
    # Linkage
    # -------------------------------------------------------------------------
    run_cmd(
        ["crate_bulk_hash", "--help"],
        join(DevPath.DOCS_LINKAGE_DIR, "_crate_bulk_hash_help.txt"),
    )
    # NOT YET, BUT WHEN IT'S RELEASED:
    # run_cmd(["crate_fuzzy_id_match", "--help"],
    #         join(LINKAGE_DIR, "_crate_fuzzy_id_match.txt"))

    # -------------------------------------------------------------------------
    # Anonymisation
    # -------------------------------------------------------------------------
    run_cmd(
        ["crate_anon_check_text_extractor", "--help"],
        join(DevPath.DOCS_ANON_DIR, "_crate_anon_check_text_extractor.txt"),
    )
    run_cmd(
        ["crate_anon_demo_config", "--help"],
        join(DevPath.DOCS_ANON_DIR, "_crate_anon_demo_config_help.txt"),
    )
    run_cmd(
        ["crate_anon_demo_config"],
        join(DevPath.DOCS_ANON_DIR, "_specimen_anonymiser_config.ini"),
    )
    run_cmd(
        ["crate_anon_draft_dd", "--help"],
        join(DevPath.DOCS_ANON_DIR, "_crate_anon_draft_dd.txt"),
    )
    run_cmd(
        ["crate_anon_show_counts", "--help"],
        join(DevPath.DOCS_ANON_DIR, "_crate_anon_show_counts_help.txt"),
    )
    run_cmd(
        ["crate_anon_summarize_dd", "--help"],
        join(DevPath.DOCS_ANON_DIR, "_crate_anon_summarize_dd_help.txt"),
    )
    run_cmd(
        ["crate_anonymise", "--help"],
        join(DevPath.DOCS_ANON_DIR, "_crate_anonymise_help.txt"),
    )
    run_cmd(
        ["crate_anonymise_multiprocess", "--help"],
        join(DevPath.DOCS_ANON_DIR, "_crate_anonymise_multiprocess_help.txt"),
    )
    run_cmd(
        ["crate_make_demo_database", "--help"],
        join(DevPath.DOCS_ANCILLARY_DIR, "_crate_make_demo_database_help.txt"),
    )
    run_cmd(
        ["crate_test_anonymisation", "--help"],
        join(DevPath.DOCS_ANCILLARY_DIR, "_crate_test_anonymisation_help.txt"),
    )
    run_cmd(
        ["crate_test_extract_text", "--help"],
        join(DevPath.DOCS_ANCILLARY_DIR, "_crate_test_extract_text_help.txt"),
    )

    log.info("Manually generated: minimal_anonymiser_config.ini")

    # -------------------------------------------------------------------------
    # Anonymisation API
    # -------------------------------------------------------------------------
    run_cmd(
        ["crate_anon_web_django_manage", "--help"],
        join(DevPath.DOCS_ANON_DIR, "_crate_anon_web_django_manage_help.txt"),
    )
    api_schema_file = join(DevPath.DOCS_ANON_DIR, "_crate_api_schema.yaml")
    run_cmd(["crate_anon_web_django_manage", "spectacular"], api_schema_file)

    # Ideally we would use https://github.com/sphinx-contrib/openapi but it
    # hasn't been maintained since 2020 and doesn't work with our schema.
    # Plus the lead contributor is based in Ukraine and probably has more
    # important things to worry about right now.
    #
    # So we create a static HTML page of the API docs and include this in
    # docs/source/anonymisation/api.rst
    try:
        subprocess.run(
            [
                # npx runs npm package binaries, installing anything necessary.
                "npx",
                # Command, version:
                "redoc-cli@0.13.10",
                # ... https://www.npmjs.com/package/redoc-cli
                # ... https://github.com/Redocly/redoc
                # ... https://redocly.com/
                # Args to redoc-cli:
                "build",
                api_schema_file,
                # Output file:
                "-o",
                join(DevPath.DOCS_ANON_DIR, "_crate_api.html"),
                # Don't display search box
                "--options.disableSearch=true",
                # Force single column layout
                # https://boyter.org/static/books/CfYA-8BXEAAtz2k.jpg
                "--options.theme.breakpoints.small=999999rem",
                "--options.theme.breakpoints.medium=1000000rem",
                "--options.theme.breakpoints.large=1000000rem",
                # Do not inject Authentication section automatically:
                "--options.noAutoAuth=true",
                # Do not collapse response documentation:
                "--options.expandResponses=all",
            ],
            check=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        log.error(
            """Error advice:
GENERAL SOLUTION: Install recent version of nvm:
    curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.38.0/install.sh | bash
    source ~/.bashrc
    nvm install lts/erbium

IF ERROR: [Errno 2] No such file or directory: 'npx'
EXPLANATION: You don't have (a modern version of) npm installed.
SOLUTION: sudo apt install npm

IF ERROR: Cannot find module 'libnpx'
EXPLANATION: Your node.js installation is out of date.
SOLUTION: sudo n stable  # update npm

IF ERROR: TypeError: log.gauge.isEnabled is not a function
EXPLANATION: Your npm/node.js installation is broken
    (https://github.com/npm/npmlog/issues/48). Check with:
    nodejs --version
    npm --version
SOLUTION: Clean/reinstall it; see https://askubuntu.com/questions/1152570/;
    e.g.
    sudo apt-get purge nodejs npm
    sudo apt autoremove
    sudo rm -rf /usr/local/bin/npm /usr/local/share/man/man1/node* ~/.npm
    sudo rm -rf /usr/lib/node*
    sudo rm -rf /usr/local/lib/node*
    sudo rm -rf /usr/local/bin/node*
    sudo rm -rf /usr/local/include/node*
    sudo apt update
    sudo apt install nodejs npm

IF ERROR: yargs parser supports a minimum Node.js version of 12
EXPLANATION: Out-of-date node.js
SOLUTION:
    sudo npm cache clean -f
        # ... if you get:
        #     ERROR: npm is known not to run on Node.js v10.19.0
        # ... then do [https://askubuntu.com/questions/1382565/]:
        #     curl -fsSL https://deb.nodesource.com/setup_12.x | sudo -E bash -
        #     sudo apt-get install -y nodejs
    sudo npm install -g n
    sudo n stable
    sudo npm install npm@latest -g
"""  # noqa
        )
        raise

    # -------------------------------------------------------------------------
    # NLP
    # -------------------------------------------------------------------------
    run_cmd(
        ["crate_nlp", "--democonfig"],
        join(DevPath.DOCS_NLP_DIR, "_specimen_nlp_config_file.ini"),
    )
    run_cmd(
        ["crate_nlp", "--describeprocessors"],
        join(DevPath.DOCS_NLP_DIR, "_crate_nlp_describeprocessors.txt"),
    )
    run_cmd(
        ["crate_nlp", "--help"],
        join(DevPath.DOCS_NLP_DIR, "_crate_nlp_help.txt"),
    )

    run_cmd(
        ["crate_nlp_build_gate_java_interface", "--help"],
        join(
            DevPath.DOCS_NLP_DIR,
            "_crate_nlp_build_gate_java_interface_help.txt",
        ),
    )
    if not args.skip_medex:
        # When running from the GitHub action, it isn't possible to
        # download and build Medex automatically, so we just skip this
        # step.
        run_cmd(
            ["crate_nlp_build_medex_itself", "--help"],
            join(
                DevPath.DOCS_NLP_DIR, "_crate_nlp_build_medex_itself_help.txt"
            ),
        )
        run_cmd(
            ["crate_nlp_build_medex_java_interface", "--help"],
            join(
                DevPath.DOCS_NLP_DIR,
                "_crate_nlp_build_medex_java_interface_help.txt",
            ),
        )

    run_cmd(
        ["crate_nlp_multiprocess", "--help"],
        join(DevPath.DOCS_NLP_DIR, "_crate_nlp_multiprocess_help.txt"),
    )
    run_cmd(
        ["crate_nlp_prepare_ymls_for_bioyodie", "--help"],
        join(DevPath.DOCS_NLP_DIR, "_crate_nlp_prepare_ymls_for_bioyodie.txt"),
    )
    run_cmd(
        ["crate_run_crate_nlp_demo", "--help"],
        join(DevPath.DOCS_NLP_DIR, "_crate_run_crate_nlp_demo.txt"),
    )
    # No help: crate_run_gate_annie_demo
    # No help: crate_run_gate_kcl_kconnect_demo
    # No help: crate_run_gate_kcl_lewy_demo
    # No help: crate_run_gate_kcl_pharmacotherapy_demo
    run_cmd(
        ["crate_show_crate_gate_pipeline_options"],
        join(DevPath.DOCS_NLP_DIR, "_CrateGatePipeline_help.txt"),
    )
    if not args.skip_medex:
        run_cmd(
            ["crate_show_crate_medex_pipeline_options"],
            join(DevPath.DOCS_NLP_DIR, "_CrateMedexPipeline_help.txt"),
        )
    shutil.copy(
        join(CratePath.NLP_MANAGER_DIR, "specimen_gate_plugin_file.ini"),
        join(DevPath.DOCS_NLP_DIR, "_specimen_gate_plugin_file.ini"),
    )

    # -------------------------------------------------------------------------
    # Research web site
    # -------------------------------------------------------------------------
    run_cmd(
        ["crate_django_manage", "--help"],
        join(DevPath.DOCS_WEB_DIR, "_crate_django_manage_help.txt"),
    )

    run_cmd(
        ["crate_django_manage", "help", "changepassword"],
        join(
            DevPath.DOCS_WEB_DIR,
            "_crate_django_manage_changepassword_help.txt",
        ),
    )
    run_cmd(
        ["crate_django_manage", "help", "collectstatic"],
        join(
            DevPath.DOCS_WEB_DIR, "_crate_django_manage_collectstatic_help.txt"
        ),
    )
    run_cmd(
        ["crate_django_manage", "help", "createsuperuser"],
        join(
            DevPath.DOCS_WEB_DIR,
            "_crate_django_manage_createsuperuser_help.txt",
        ),
    )
    run_cmd(
        ["crate_django_manage", "help", "email_rdbm"],
        join(DevPath.DOCS_WEB_DIR, "_crate_django_manage_email_rdbm_help.txt"),
    )
    run_cmd(
        ["crate_django_manage", "help", "fetch_optouts"],
        join(
            DevPath.DOCS_WEB_DIR, "_crate_django_manage_fetch_optouts_help.txt"
        ),
    )
    run_cmd(
        ["crate_django_manage", "help", "lookup_consent"],
        join(
            DevPath.DOCS_WEB_DIR,
            "_crate_django_manage_lookup_consent_help.txt",
        ),
    )
    run_cmd(
        ["crate_django_manage", "help", "lookup_patient"],
        join(
            DevPath.DOCS_WEB_DIR,
            "_crate_django_manage_lookup_patient_help.txt",
        ),
    )
    run_cmd(
        ["crate_django_manage", "help", "populate"],
        join(DevPath.DOCS_WEB_DIR, "_crate_django_manage_populate_help.txt"),
    )
    run_cmd(
        ["crate_django_manage", "help", "resubmit_unprocessed_tasks"],
        join(
            DevPath.DOCS_WEB_DIR,
            "_crate_django_manage_resubmit_unprocessed_tasks_help.txt",
        ),
    )
    run_cmd(
        ["crate_django_manage", "help", "runcpserver"],
        join(
            DevPath.DOCS_WEB_DIR, "_crate_django_manage_runcpserver_help.txt"
        ),
    )
    run_cmd(
        ["crate_django_manage", "help", "runserver"],
        join(DevPath.DOCS_WEB_DIR, "_crate_django_manage_runserver_help.txt"),
    )
    run_cmd(
        ["crate_django_manage", "help", "test_email"],
        join(DevPath.DOCS_WEB_DIR, "_crate_django_manage_test_email_help.txt"),
    )

    run_cmd(
        ["crate_launch_celery", "--help"],
        join(DevPath.DOCS_WEB_DIR, "_crate_launch_celery_help.txt"),
    )
    run_cmd(
        ["crate_launch_django_server", "--help"],
        join(DevPath.DOCS_WEB_DIR, "_crate_launch_django_server_help.txt"),
    )
    run_cmd(
        ["crate_print_demo_crateweb_config"],
        join(DevPath.DOCS_WEB_DIR, "_specimen_web_config.py"),
    )

    log.warning("Skipping crate_windows_service_help.txt (requires Windows)")

    # skip: crate_launch_cherrypy_server
    # skip: crate_launch_django_server

    # -------------------------------------------------------------------------
    # NLPRP/NLP web server
    # -------------------------------------------------------------------------
    # No help: crate_nlp_webserver_generate_encryption_key
    run_cmd(
        ["crate_nlp_webserver_initialize_db", "--help"],
        join(
            DevPath.DOCS_NLP_DIR, "_crate_nlp_webserver_initialize_db_help.txt"
        ),
    )
    run_cmd(
        ["crate_nlp_webserver_launch_celery", "--help"],
        join(
            DevPath.DOCS_NLP_DIR, "_crate_nlp_webserver_launch_celery_help.txt"
        ),
    )
    # No help: crate_nlp_webserver_launch_flower
    run_cmd(
        ["crate_nlp_webserver_launch_gunicorn", "--help"],
        join(
            DevPath.DOCS_NLP_DIR,
            "_crate_nlp_webserver_launch_gunicorn_help.txt",
        ),
    )
    run_cmd(
        ["crate_nlp_webserver_manage_users", "--help"],
        join(DevPath.DOCS_NLP_DIR, "_crate_nlp_webserver_manage_users.txt"),
    )

    run_cmd(
        ["crate_nlp_webserver_print_demo", "--help"],
        join(DevPath.DOCS_NLP_DIR, "_crate_nlp_webserver_print_demo_help.txt"),
    )
    run_cmd(
        ["crate_nlp_webserver_print_demo", "--config"],
        join(DevPath.DOCS_NLP_DIR, "_nlp_webserver_demo_config.ini"),
    )
    run_cmd(
        ["crate_nlp_webserver_print_demo", "--processors"],
        join(DevPath.DOCS_NLP_DIR, "_nlp_webserver_demo_processors.py"),
        executable=True,
    )

    run_cmd(
        ["crate_nlp_webserver_pserve", "--help"],
        join(DevPath.DOCS_NLP_DIR, "_crate_nlp_webserver_pserve_help.txt"),
    )
    run_cmd(
        ["crate_nlp_webserver_pserve", "--help"],
        join(DevPath.DOCS_NLP_DIR, "_crate_nlp_webserver_pserve_help.txt"),
    )

    shutil.copy(
        join(CratePath.NLPRP_DIR, "nlprp_test_client.py"),
        join(DevPath.DOCS_NLP_DIR, "_nlprp_test_client.py"),
    )
    shutil.copy(
        join(CratePath.NLPRP_DIR, "nlprp_test_server.py"),
        join(DevPath.DOCS_NLP_DIR, "_nlprp_test_server.py"),
    )

    # -------------------------------------------------------------------------
    # Done.
    # -------------------------------------------------------------------------
    log.info("Done.")


if __name__ == "__main__":
    main_only_quicksetup_rootlogger()
    main()
