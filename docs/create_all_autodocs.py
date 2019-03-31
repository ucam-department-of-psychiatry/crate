#!/usr/bin/env python

"""
docs/create_all_autodocs.py

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

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

"""

import argparse
import logging
import os
import sys

from cardinal_pythonlib.fileops import rmtree
from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from cardinal_pythonlib.sphinxtools import AutodocIndex

if sys.version_info[0] < 3:
    raise AssertionError("Need Python 3")
log = logging.getLogger(__name__)

# Work out directories
THIS_DIR = os.path.dirname(os.path.realpath(__file__))  # .../docs
PACKAGE_ROOT_DIR = os.path.abspath(os.path.join(THIS_DIR, os.pardir))  # .../
CODE_ROOT_DIR = os.path.join(PACKAGE_ROOT_DIR, "crate_anon")
AUTODOC_DIR = os.path.join(THIS_DIR, "source", "autodoc")
INDEX_FILENAME = "_index.rst"
TOP_AUTODOC_INDEX = os.path.join(AUTODOC_DIR, INDEX_FILENAME)

COPYRIGHT_COMMENT = r"""
..  Copyright © 2015-2018 Rudolf Cardinal (rudolf@pobox.com).
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
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.

"""

SKIP_GLOBS = [
    # we include "__init__.py"
    # "crateweb_local_settings.py",
    "jquery*",
    "modernizr*",
    "**/jquery*/*",
    "**/static_collected/*",
]


def make_subindex(directory: str) -> AutodocIndex:
    return AutodocIndex(
        index_filename=os.path.join(AUTODOC_DIR, directory, INDEX_FILENAME),
        project_root_dir=PACKAGE_ROOT_DIR,
        autodoc_rst_root_dir=AUTODOC_DIR,
        highest_code_dir=CODE_ROOT_DIR,
        source_filenames_or_globs=[
            os.path.join(CODE_ROOT_DIR, directory, "**/*.css"),
            os.path.join(CODE_ROOT_DIR, directory, "**/*.html"),
            os.path.join(CODE_ROOT_DIR, directory, "**/*.py"),
            os.path.join(CODE_ROOT_DIR, directory, "**/*.java"),
            os.path.join(CODE_ROOT_DIR, directory, "**/*.js"),
        ],
        rst_prefix=COPYRIGHT_COMMENT,
        title="crate_anon/" + directory,  # path style, not module style
        skip_globs=SKIP_GLOBS,
        # source_rst_title_style_python=False,
    )


def make_autodoc(make: bool, destroy_first: bool) -> None:
    if destroy_first:
        if make and os.path.exists(AUTODOC_DIR):
            log.info(f"Deleting directory {AUTODOC_DIR!r}")
            rmtree(AUTODOC_DIR)
        else:
            log.warning(
                f"Would delete directory {AUTODOC_DIR!r} "
                f"(not doing so as in mock mode)")
    top_idx = AutodocIndex(
        index_filename=TOP_AUTODOC_INDEX,
        project_root_dir=PACKAGE_ROOT_DIR,
        autodoc_rst_root_dir=AUTODOC_DIR,
        highest_code_dir=CODE_ROOT_DIR,
        toctree_maxdepth=2,
        rst_prefix=COPYRIGHT_COMMENT,
    )
    top_idx.add_indexes([
        make_subindex("anonymise"),
        make_subindex("common"),
        make_subindex("crateweb"),
        make_subindex("nlp_manager"),
        make_subindex("nlp_web"),
        make_subindex("preprocess"),
        make_subindex("tools"),
    ])
    top_idx.write_index_and_rst_files(overwrite=True, mock=not make)
    # print(top_idx.index_content())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--make", action="store_true",
        help="Do things! Otherwise will just show its intent.")
    parser.add_argument(
        "--destroy_first", action="store_true",
        help="Destroy all existing autodocs first")
    parser.add_argument(
        "--verbose", action="store_true",
        help="Be verbose")
    args = parser.parse_args()

    main_only_quicksetup_rootlogger(
        level=logging.DEBUG if args.verbose else logging.INFO)

    make_autodoc(make=args.make,
                 destroy_first=args.destroy_first)


if __name__ == '__main__':
    main()
