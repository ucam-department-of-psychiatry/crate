#!/usr/bin/env python

"""
crate_anon/anonymise/check_text_extractor.py

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

**Check if text extraction tools are available (for anonymisation).**

"""

import argparse

from cardinal_pythonlib.extract_text import is_text_extractor_available
from rich_argparse import ArgumentDefaultsRichHelpFormatter

from crate_anon.version import CRATE_VERSION_PRETTY


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    """
    Command-line entry point
    """
    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        description=f"Check availability of tools to extract text from "
        f"different document formats. ({CRATE_VERSION_PRETTY})",
        formatter_class=ArgumentDefaultsRichHelpFormatter,
    )

    parser.add_argument(
        "checkextractor",
        nargs="*",
        help="File extensions to check for availability of a text extractor. "
        "Try, for example, '.doc .docx .odt .pdf .rtf .txt None' "
        "(use a '.' prefix for all extensions, and use the special "
        "extension 'None' to check the fallback processor).",
    )

    args = parser.parse_args()

    for ext in args.checkextractor:
        if ext.lower() == "none":
            ext = None
        available = is_text_extractor_available(ext)
        print(f"Text extractor for extension {ext} present: {available}")


if __name__ == "__main__":
    main()
