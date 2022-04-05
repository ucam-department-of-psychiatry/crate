#!/usr/bin/env python

"""
crate_anon/nlp_manager/run_crate_nlp_demo.py

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

**Read from files or stdin.**

"""

import logging
from typing import Iterable, List

from cardinal_pythonlib.file_io import smart_open

log = logging.getLogger(__name__)


# =============================================================================
# Input
# =============================================================================


def gen_chunks_from_files(
    filenames: List[str],
    chunk_terminator_line: str = None,
    stdin_prompt: str = None,
) -> Iterable[str]:
    """
    Iterates through filenames (also permitting '-' for stdin).
    Generates multi-line chunks, separated by a terminator.

    Args:
        filenames:
            Filenames (or '-' for stdin).
        chunk_terminator_line:
            Single-line string used to separate chunks within a file. If this
            is an empty string, then enter a blank line to terminate. If it is
            ``None``, then lines are yielded one by one (multi-line input is
            not possible).
        stdin_prompt:
            Optional prompt to show (to the log) before each request.

    Yields:
        str:
            Each chunk.

    """
    current_lines = []  # type: List[str]
    use_prompt = False

    def thing_to_yield() -> str:
        nonlocal current_lines
        chunk = "\n".join(current_lines)
        current_lines.clear()
        return chunk

    def prompt_if_necessary() -> None:
        if use_prompt:
            log.warning(stdin_prompt)

    stdin_filename = "-"
    for filename in filenames:
        log.info(f"Reading from: {filename}")
        use_prompt = stdin_filename and stdin_prompt
        with smart_open(filename) as f:
            prompt_if_necessary()
            for line in f:
                line = line.rstrip("\n")  # remove trailing newline
                if chunk_terminator_line is None:
                    yield line
                    prompt_if_necessary()
                elif line == chunk_terminator_line:
                    yield thing_to_yield()
                    prompt_if_necessary()
                else:
                    current_lines.append(line)
            # End of file: yield any leftovers
            yield thing_to_yield()
        log.debug(f"Finished file: {filename}")
