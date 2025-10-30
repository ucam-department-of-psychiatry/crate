#!/usr/bin/env python

"""
docs/process_doctree.py

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

**Processes docutils .doctree files, reporting any problems with the headings
in the source. Options to dump and try to fix headings.**

"""

import argparse
import os
import pickle
import re
import sys

from docutils import nodes

HEADING_CHARS = "?=-~^#"


class DoctreeParser:
    def __init__(
        self,
        doctree_path: str,
        source_path: str,
        dump_headings: bool,
        fix_headings: bool,
    ) -> None:
        self.doctree_path = doctree_path
        self.source_path = source_path
        self.dump_headings = dump_headings
        self.fix_headings = fix_headings

    def parse(self) -> None:
        print(self.source_path)

        doctree = pickle.load(open(self.doctree_path, "rb"))

        if self.doctree_path.endswith("index.doctree"):
            depth = 0
        else:
            depth = 1

        with open(self.source_path, "r", encoding="utf-8") as f:
            source_text = f.read()
            for node in doctree:
                self.find_title_node(source_text, node, depth)

    def update_source(self, search: str, replace: str) -> None:
        # This is not perfect, currently it will not get it right
        # if two or more headings have the same text in the same
        # file.
        print(f"Updating {self.source_path}...")
        with open(self.source_path, "r", encoding="utf-8") as f:
            content = f.read()
            new_content = re.sub(
                search, replace, content, count=1, flags=re.MULTILINE
            )

        with open(self.source_path, "w", encoding="utf-8") as f:
            f.write(new_content)

    def find_title_node(
        self, source_text: str, node: nodes.Element, depth: int
    ) -> None:
        if isinstance(node, nodes.title):
            title = node.astext()

            # Characters such as ellipsis (...) will be converted to their
            # Unicode equivalents (…) in the doctree and ultimately the HTML.
            # Easiest to ensure the source does not contain any Unicode.
            replace_dict = {
                "…": "...",
                "’": "'",
                "“": '"',
                "”": '"',
                "‘": "'",
            }

            for k, v in replace_dict.items():
                title = title.replace(k, v)

            title_len = len(title)
            underline = HEADING_CHARS[depth] * title_len
            if self.dump_headings:
                indent = depth * "  "
                print(f"{indent}{title}\n{indent}{underline}")

            search = rf"^{re.escape(title)}\n([^a-zA-Z0-9]{{{title_len}}})$"
            m = re.search(search, source_text, flags=re.MULTILINE)
            if m:
                if self.fix_headings and m.group(1) != underline:
                    self.update_source(search, f"{title}\n{underline}\n")
            else:
                print(
                    f"{self.doctree_path}: Could not find {search}",
                    file=sys.stderr,
                )

        for child_node in node.children:
            self.find_title_node(source_text, child_node, depth + 1)


def main() -> None:
    arg_parser = argparse.ArgumentParser(
        description=(
            "Process docutils .doctree files in the given directory. These "
            "will not be processed in the same order that they appear in "
            "the document."
        )
    )

    arg_parser.add_argument("docs_dir")

    arg_parser.add_argument(
        "--dump",
        action="store_true",
        default=False,
        help="Dump the headings to stdout, indented to the correct level",
    )

    arg_parser.add_argument(
        "--fix",
        action="store_true",
        default=False,
        help=(
            "Attempt to fix headings (not perfect, will fail if two headings "
            "have the same text in the same file)"
        ),
    )

    args = arg_parser.parse_args()

    doctrees_dir = os.path.join(args.docs_dir, "build", "doctrees")

    for root, dirs, filenames in os.walk(doctrees_dir, topdown=True):
        dirs[:] = [d for d in dirs if d not in "autodoc"]

        for doctree_filename in filenames:
            doctree_path = os.path.join(root, doctree_filename)

            doctree_path_without_ext, ext = os.path.splitext(doctree_path)
            if ext == ".doctree":
                source_path = (
                    doctree_path_without_ext.replace(
                        "/build/doctrees/", "/source/"
                    )
                    + ".rst"
                )

                doctree_parser = DoctreeParser(
                    doctree_path, source_path, args.dump, args.fix
                )
                doctree_parser.parse()


if __name__ == "__main__":
    main()
