#!/usr/bin/env python

"""
crate_anon/anonymise/draft_dd.py

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

**Draft an anonymisation data dictionary.**

"""

import argparse
import logging
import os

from cardinal_pythonlib.enumlike import keys_descriptions_from_enum
from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger

from crate_anon.anonymise.config import Config
from crate_anon.anonymise.constants import ANON_CONFIG_ENV_VAR
from crate_anon.preprocess.systmone_ddgen import (
    DEFAULT_SYSTMONE_CONTEXT,
    modify_dd_for_systmone,
    SystmOneContext,
)
from crate_anon.version import CRATE_VERSION_PRETTY

log = logging.getLogger(__name__)


# =============================================================================
# Draft a data dictionary
# =============================================================================

def draft_dd(config: Config,
             dd_output_filename: str,
             incremental: bool = False,
             skip_dd_check: bool = False,
             explicit_dest_datatype: bool = False,
             systmone: bool = False,
             systmone_context: SystmOneContext = None,
             systmone_sre_spec_csv_filename: str = None,
             systmone_append_comments: bool = False,
             systmone_include_generic: bool = False,
             systmone_allow_unprefixed_tables: bool = False,
             systmone_alter_loaded_rows: bool = False) -> None:
    """
    Draft a data dictionary.

    Args:
        config:
            Anonymisation config object.
        incremental:
            If true: make it an incremental data dictionary, using only fields
            present in the database but absent from the existing data
            dictionary referred to in the config.
        dd_output_filename:
            File for output ('-' for stdout).
        skip_dd_check:
            If true: skip data dictionary validity check when loading the
            pre-existing data dictionary in "incremental" mode.
        explicit_dest_datatype:
            Make destination datatypes explicit, not implicit. (Primarily for
            debugging.)
        systmone:
            Process data dictionary for SystmOne data?
        systmone_context:
            (For SystmOne.) Source database context for SystmOne use.
        systmone_sre_spec_csv_filename:
            (For SystmOne.) Optional filename for TPP Strategic Reporting
            Extract (SRE) specification CSV.
        systmone_append_comments:
            (For SystmOne.) Append, rather than replacing, existing comments?
            Usually better as False -- if you use
            ``systmone_sre_spec_csv_filename`, this will provide better
            comments.
        systmone_include_generic:
            (For SystmOne.) Include all fields that are not known about by this
            code and treated specially? If False, the config file settings are
            used (which may omit or include). If True, all such fields are
            included.
        systmone_allow_unprefixed_tables:
            (For SystmOne.) Permit tables that don't start with the expected
            prefix? (That prefix is e.g. 'SR' for the TPP SRE context, 'S1_'
            for the CPFT Data Warehouse context.) Discouraged; you may get odd
            tables and views.
        systmone_alter_loaded_rows:
            Alter rows that were loaded from disk (not read from a database)?
            The default is to leave such rows untouched.
    """
    if incremental:
        # For "incremental", we load the data dictionary from disk.
        # Otherwise, we don't, so a completely fresh one will be generated.
        config.load_dd(check_against_source_db=not skip_dd_check)

    dd = config.dd

    dd.draft_from_source_databases()
    # Will skip source columns that it knows about already (and thus generate
    # an incremental data dictionary if we had pre-loaded some).

    if systmone:
        if not systmone_context:
            raise ValueError("Requires SystmOne context to be specified")
        modify_dd_for_systmone(
            dd=dd,
            context=systmone_context,
            sre_spec_csv_filename=systmone_sre_spec_csv_filename,
            append_comments=systmone_append_comments,
            include_generic=systmone_include_generic,
            allow_unprefixed_tables=systmone_allow_unprefixed_tables,
            alter_loaded_rows=systmone_alter_loaded_rows,
        )
    if explicit_dest_datatype:
        dd.make_dest_datatypes_explicit()
    dd.check_valid(check_against_source_db=not skip_dd_check)
    dd.write(dd_output_filename)


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    """
    Command-line entry point.
    """
    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        description=f"Draft a data dictionary for the anonymiser. "
                    f"({CRATE_VERSION_PRETTY})",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--config",
        help=f"Config file (overriding environment variable "
             f"{ANON_CONFIG_ENV_VAR}). Note that the config file has several "
             f"options governing the automatic generation of data "
             f"dictionaries."
    )
    parser.add_argument(
        '--verbose', '-v', action="store_true",
        help="Be verbose"
    )
    parser.add_argument(
        "--incremental", action="store_true",
        help="Drafts an INCREMENTAL draft data dictionary (containing fields "
             "in the database that aren't in the existing data dictionary "
             "referred to by the config file)."
    )
    parser.add_argument(
        "--skip_dd_check", action="store_true",
        help="Skip validity check (against the source database) for the "
             "data dictionary."
    )
    parser.add_argument(
        "--output", default="-",
        help="File for output; use '-' for stdout."
    )
    parser.add_argument(
        "--explicit_dest_datatype", action="store_true",
        help="(Primarily for debugging.) CRATE will convert the source column "
             "data type (e.g. INTEGER, FLOAT, VARCHAR(25)) to a datatype for "
             "the destination database, sometimes with modifications. "
             "However, this is usually implicit: the draft data dictionary "
             "doesn't show these data types unless they require modification. "
             "Use this option to make them all explicit."
    )
    parser.add_argument(
        "--systmone", action="store_true",
        help="Modify the data dictionary for SystmOne."
    )

    s1_options = parser.add_argument_group(
        "SystmOne options (for when --systmone is used)"
    )
    context_k, context_d = keys_descriptions_from_enum(
        SystmOneContext, keys_to_lower=True)
    s1_options.add_argument(
        "--systmone_context", type=str, choices=context_k,
        default=DEFAULT_SYSTMONE_CONTEXT.name.lower(),
        help="Context of the SystmOne database that you are reading. "
             f"[{context_d}]"
    )
    s1_options.add_argument(
        "--systmone_sre_spec",
        help="SystmOne Strategic Reporting Extract (SRE) specification CSV "
             "filename (from TPP, containing table/field comments)."
    )
    s1_options.add_argument(
        "--systmone_append_comments", action="store_true",
        help="Append to comments, rather than replacing them."
    )
    s1_options.add_argument(
        "--systmone_include_generic", action="store_true",
        help="Include all 'generic' fields, overriding preferences set via "
             "the config file options."
    )
    s1_options.add_argument(
        "--systmone_allow_unprefixed_tables", action="store_true",
        help="Permit tables that don't start with the expected prefix "
             "(which is e.g. 'SR' for the TPP SRE context, 'S1_' for the CPFT "
             "Data Warehouse context). Discouraged; you may get odd tables "
             "and views."
    )
    s1_options.add_argument(
        "--systmone_alter_loaded_rows", action="store_true",
        help="(For --incremental.) Alter rows that were loaded from disk "
             "(not read from a database)? The default is to leave such rows "
             "untouched."
    )

    args = parser.parse_args()

    # -------------------------------------------------------------------------
    # Verbosity, logging
    # -------------------------------------------------------------------------

    loglevel = logging.DEBUG if args.verbose else logging.INFO
    main_only_quicksetup_rootlogger(level=loglevel)

    # -------------------------------------------------------------------------
    # Onwards
    # -------------------------------------------------------------------------

    if args.config:
        os.environ[ANON_CONFIG_ENV_VAR] = args.config
    from crate_anon.anonymise.config_singleton import config  # delayed import

    draft_dd(
        config=config,
        dd_output_filename=args.output,
        incremental=args.incremental,
        skip_dd_check=args.skip_dd_check,
        explicit_dest_datatype=args.explicit_dest_datatype,
        systmone=args.systmone,
        systmone_context=SystmOneContext[args.systmone_context],
        systmone_sre_spec_csv_filename=args.systmone_sre_spec,
        systmone_append_comments=args.systmone_append_comments,
        systmone_include_generic=args.systmone_include_generic,
        systmone_allow_unprefixed_tables=args.systmone_allow_unprefixed_tables,
        systmone_alter_loaded_rows=args.systmone_alter_loaded_rows,
    )
