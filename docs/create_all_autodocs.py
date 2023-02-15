#!/usr/bin/env python

"""
docs/create_all_autodocs.py

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

"""

import argparse
import logging
import os
from os.path import abspath, dirname, join, realpath

from cardinal_pythonlib.fileops import rmtree
from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from cardinal_pythonlib.sphinxtools import AutodocIndex
from rich_argparse import RichHelpFormatter

from crate_anon.common.constants import CratePath

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================


class DevPath:
    """
    Directories for development (including documentation), and some filenames.
    """

    # -------------------------------------------------------------------------
    # Directories
    # -------------------------------------------------------------------------
    DOC_ROOT_DIR = dirname(realpath(__file__))  # .../docs

    # Python package, code
    PACKAGE_ROOT_DIR = abspath(join(DOC_ROOT_DIR, os.pardir))  # .../

    # Docs
    DOCS_SOURCE_DIR = join(DOC_ROOT_DIR, "source")

    DOCS_ANCILLARY_DIR = join(DOCS_SOURCE_DIR, "ancillary")
    DOCS_ANON_DIR = join(DOCS_SOURCE_DIR, "anonymisation")
    DOCS_AUTODOC_DIR = join(DOCS_SOURCE_DIR, "autodoc")
    DOCS_AUTODOC_EXTRA_DIR = join(DOCS_SOURCE_DIR, "autodoc_extra")
    DOCS_LINKAGE_DIR = join(DOCS_SOURCE_DIR, "linkage")
    DOCS_NLP_DIR = join(DOCS_SOURCE_DIR, "nlp")
    DOCS_PREPROC_DIR = join(DOCS_SOURCE_DIR, "preprocessing")
    DOCS_WEB_DIR = join(DOCS_SOURCE_DIR, "website_config")

    # -------------------------------------------------------------------------
    # Filenames without paths
    # -------------------------------------------------------------------------
    INDEX_FILENAME = "_index.rst"

    # -------------------------------------------------------------------------
    # Filenames
    # -------------------------------------------------------------------------
    TOP_AUTODOC_INDEX = os.path.join(DOCS_AUTODOC_DIR, INDEX_FILENAME)


RST_COPYRIGHT_COMMENT = r"""
..  Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).
    .
    This file is part of CRATE.
    .
    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    .
    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.
    .
    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.
""".strip()

SKIP_GLOBS = [
    # we include "__init__.py"
    # "crateweb_local_settings.py",
    "jquery*",
    "modernizr*",
    "plotly*",
    "**/jquery*/*",
    "**/static_collected/*",
    "**/compiled_nlp_classes/*",
]

PYGMENTS_LANGUAGE_OVERRIDE = {"*.html": "html+django", "*.css": "css+django"}


# =============================================================================
# Autodoc creation
# =============================================================================


def make_subindex(directory: str) -> AutodocIndex:
    return AutodocIndex(
        index_filename=os.path.join(
            DevPath.DOCS_AUTODOC_DIR, directory, DevPath.INDEX_FILENAME
        ),
        project_root_dir=DevPath.PACKAGE_ROOT_DIR,
        autodoc_rst_root_dir=DevPath.DOCS_AUTODOC_DIR,
        highest_code_dir=CratePath.CRATE_ANON_DIR,
        source_filenames_or_globs=[
            os.path.join(CratePath.CRATE_ANON_DIR, directory, "**/*.css"),
            os.path.join(CratePath.CRATE_ANON_DIR, directory, "**/*.html"),
            os.path.join(CratePath.CRATE_ANON_DIR, directory, "**/*.mako"),
            os.path.join(CratePath.CRATE_ANON_DIR, directory, "**/*.py"),
            os.path.join(CratePath.CRATE_ANON_DIR, directory, "**/*.java"),
            os.path.join(CratePath.CRATE_ANON_DIR, directory, "**/*.js"),
        ],
        rst_prefix=RST_COPYRIGHT_COMMENT,
        title="crate_anon/" + directory,  # path style, not module style
        skip_globs=SKIP_GLOBS,
        pygments_language_override=PYGMENTS_LANGUAGE_OVERRIDE,
        # source_rst_title_style_python=False,
    )


def make_autodoc(make: bool, destroy_first: bool) -> None:
    if destroy_first:
        if make and os.path.exists(DevPath.DOCS_AUTODOC_DIR):
            log.info(f"Deleting directory {DevPath.DOCS_AUTODOC_DIR!r}")
            rmtree(DevPath.DOCS_AUTODOC_DIR)
        else:
            log.warning(
                f"Would delete directory {DevPath.DOCS_AUTODOC_DIR!r} "
                f"(not doing so as in mock mode)"
            )
    top_idx = AutodocIndex(
        index_filename=DevPath.TOP_AUTODOC_INDEX,
        project_root_dir=DevPath.PACKAGE_ROOT_DIR,
        autodoc_rst_root_dir=DevPath.DOCS_AUTODOC_DIR,
        highest_code_dir=CratePath.CRATE_ANON_DIR,
        toctree_maxdepth=2,
        rst_prefix=RST_COPYRIGHT_COMMENT,
    )
    top_idx.add_indexes(
        [
            make_subindex("anonymise"),
            make_subindex("common"),
            make_subindex("crateweb"),
            make_subindex("linkage"),
            make_subindex("nlp_manager"),
            make_subindex("nlp_webserver"),
            make_subindex("preprocess"),
            make_subindex("tools"),
        ]
    )
    top_idx.write_index_and_rst_files(overwrite=True, mock=not make)
    # print(top_idx.index_content())


# =============================================================================
# Command-line entry point
# =============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(formatter_class=RichHelpFormatter)
    parser.add_argument(
        "--make",
        action="store_true",
        help="Do things! Otherwise will just show its intent.",
    )
    parser.add_argument(
        "--destroy_first",
        action="store_true",
        help="Destroy all existing autodocs first",
    )
    parser.add_argument("--verbose", action="store_true", help="Be verbose")
    args = parser.parse_args()

    main_only_quicksetup_rootlogger(
        level=logging.DEBUG if args.verbose else logging.INFO
    )

    make_autodoc(make=args.make, destroy_first=args.destroy_first)


if __name__ == "__main__":
    main()
