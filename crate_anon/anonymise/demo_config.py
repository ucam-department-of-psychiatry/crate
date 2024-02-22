#!/usr/bin/env python

"""
crate_anon/anonymise/demo_config.py

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

**Print a demonstration config file for the anonymiser.**

"""

import argparse
import pprint
import re
import sys
from typing import Dict

from cardinal_pythonlib.file_io import smart_open
from rich_argparse import ArgumentDefaultsRichHelpFormatter

from crate_anon.anonymise.constants import DEMO_CONFIG
from crate_anon.common.constants import EXIT_FAILURE
from crate_anon.version import CRATE_VERSION_PRETTY


# =============================================================================
# Get a demo config, with placeholders replaced
# =============================================================================


def search_replace_text(text: str, replace_dict: Dict[str, str]) -> str:
    for (search, replace) in replace_dict.items():
        if replace is None:
            print(f"Can't replace '{search}' with None")
            sys.exit(EXIT_FAILURE)

        text = text.replace(f"@@{search}@@", replace)

    return text


def get_demo_config() -> str:
    replace_dict = {
        "admin_db_url": "mysql+mysqldb://username:password@127.0.0.1:3306/admin_databasename?charset=utf8",  # noqa: E501
        "change_detection_encryption_phrase": "YETANOTHER",
        "data_dictionary_filename": "testdd.tsv",
        "dest_db_url": "mysql+mysqldb://username:password@127.0.0.1:3306/output_databasename?charset=utf8",  # noqa: E501
        "master_patient_id_encryption_phrase": "SOME_OTHER_PASSPHRASE_REPLACE_ME",  # noqa: E501
        "per_table_patient_id_encryption_phrase": "SOME_PASSPHRASE_REPLACE_ME",
        "source_db1_ddgen_include_fields": "",
        "source_db1_ddgen_scrubsrc_patient_fields": "",
        "source_db1_url": "mysql+mysqldb://username:password@127.0.0.1:3306/source_databasename?charset=utf8",  # noqa: E501
    }

    config = search_replace_text(DEMO_CONFIG, replace_dict)

    missing_dict = {}

    regex = r"@@([^@]*)@@"
    for match in re.finditer(regex, config):
        missing_dict[f"{match.group(1)}"] = ""

    if missing_dict:
        print(
            "@@ Placeholders not substituted in DEMO_CONFIG:", file=sys.stderr
        )
        pprint.pprint(missing_dict, stream=sys.stderr)
        sys.exit(EXIT_FAILURE)

    return config.strip()


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    """
    Command-line entry point.
    """
    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        description=f"Print a demo config file for the CRATE anonymiser. "
        f"({CRATE_VERSION_PRETTY})",
        formatter_class=ArgumentDefaultsRichHelpFormatter,
    )

    parser.add_argument(
        "--output", default="-", help="File for output; use '-' for stdout."
    )
    parser.add_argument(
        "--leave_placeholders",
        action="store_true",
        help="Don't substitute @@ placeholders with examples",
    )

    args = parser.parse_args()

    # -------------------------------------------------------------------------
    # Print demo config
    # -------------------------------------------------------------------------

    with smart_open(args.output, "w") as f:
        if args.leave_placeholders:
            contents = DEMO_CONFIG.strip()
        else:
            contents = get_demo_config()
        print(contents, file=f)
