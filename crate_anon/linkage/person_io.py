#!/usr/bin/env python

r"""
crate_anon/linkage/person_io.py

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

**Read/write people from/to disk.**

"""


# =============================================================================
# Imports
# =============================================================================

import csv
from io import TextIOBase
import logging
import os
from types import TracebackType
from typing import (
    Generator,
    Iterable,
    Optional,
    Type,
    Union,
)

import jsonlines

from crate_anon.linkage.matchconfig import MatchConfig
from crate_anon.linkage.people import People
from crate_anon.linkage.person import Person

log = logging.getLogger(__name__)


# =============================================================================
# Loading people data
# =============================================================================


def gen_person_from_file(
    cfg: MatchConfig,
    filename: str,
    plaintext: bool = True,
    jsonl: Optional[bool] = None,
) -> Generator[Person, None, None]:
    """
    Read a list of people from a CSV/JSONLines file. See
    :class:`Person.PersonKey` for the column details.

    Args:
        cfg:
            Configuration object.
        filename:
            Filename to read.
        plaintext:
            Read in plaintext (from CSV or JSONL), rather than hashed (from
            JSONL), format?
        jsonl:
            True = read from JSONL; False = read from CSV; None = autodetect
            from filename.

    Yields:
        Person objects
    """
    log.info(f"Reading file: {filename}")
    assert filename
    if jsonl is None:
        ext = os.path.splitext(filename)[1]
        if ext == ".csv":
            jsonl = False
        elif ext == ".jsonl":
            jsonl = True
        else:
            raise ValueError(f"Unknown file type: {filename}")
    if not jsonl and not plaintext:
        raise ValueError(
            "Options set wrong: can't read hashed data from CSV format, for "
            f"file {filename}"
        )

    if jsonl:
        # JSON Lines file
        hashed = not plaintext
        with jsonlines.open(filename) as reader:
            for obj in reader:
                yield Person.from_json_dict(cfg, obj, hashed=hashed)
    else:
        # CSV plaintext file
        with open(filename, "rt") as f:
            reader = csv.DictReader(f)
            for rowdict in reader:
                yield Person.from_plaintext_csv(cfg, rowdict)
    log.info(f"... finished reading from {filename}")


# =============================================================================
# Saving people data
# =============================================================================


class PersonWriter:
    """
    A context manager for writing :class:`Person` objects to CSV (plaintext) or
    JSONL (hashed).
    """

    def __init__(
        self,
        file: TextIOBase = None,
        filename: str = None,
        plaintext: bool = False,
        plaintext_jsonl: bool = False,
        include_frequencies: bool = True,
        include_other_info: bool = False,
    ) -> None:
        """
        Args:
            file:
                File-like object to which to write. Use either this or
                ``filename``, not both.
            filename:
                Filename to which to write. Use either this or ``file``, not
                both.
            plaintext:
                Plaintext (in CSV or JSONL)? If False, will be written hashed
                (in JSONL).
            plaintext_jsonl:
                (For plaintext.) Use JSONL rather than CSV?
            include_frequencies:
                (For hashed writing only.) Include frequency information.
                Without this, the resulting file is suitable for use as a
                sample, but not as a proband file.
            include_other_info:
                (For hashed writing only.) Include the (potentially
                identifying) ``other_info`` data? Usually ``False``; may be
                ``True`` for validation.
        """
        assert bool(file) != bool(
            filename
        ), "Specify either file or filename (and not both)"
        if include_other_info:
            log.warning(
                "include_other_info is set; use this for validation only"
            )

        self.filename = filename
        self.file = file
        self.plaintext = plaintext
        self.plaintext_jsonl = plaintext_jsonl
        self.include_frequencies = include_frequencies
        self.include_other_info = include_other_info
        self.using_csv = self.plaintext and not self.plaintext_jsonl
        self.csv_writer = None  # type: Optional[csv.DictWriter]

    def __enter__(self) -> "PersonWriter":
        """
        Used by the ``with`` statement; the thing returned is what you get
        from ``with``.
        """
        # 1. Ensure we have a file.
        if self.filename:
            log.info(f"Saving to: {self.filename}")
            self.file = open(self.filename, "wt")
            # Don't write to the log if we're not using a filename; we may be
            # writing to an in-memory structure, in which case the user
            # probably doesn't care.
        # 2. Create a writer.
        if self.using_csv:
            self.csv_writer = csv.DictWriter(
                self.file, fieldnames=Person.ALL_PERSON_KEYS
            )
            self.csv_writer.writeheader()
        else:
            self.jsonl_writer = jsonlines.Writer(self.file)
        return self

    def write(self, person: Person) -> None:
        """
        Write a person to the file.
        """
        if self.using_csv:
            self.csv_writer.writerow(person.plaintext_csv_dict())
        else:
            self.jsonl_writer.write(
                person.as_dict(
                    hashed=not self.plaintext,
                    include_frequencies=self.include_frequencies,
                    include_other_info=self.include_other_info,
                )
            )

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """
        Reverse the operations of __enter__().
        """
        # 2. Close the writers.
        if self.using_csv:
            pass
        else:
            self.jsonl_writer.close()
        # 1. If we opened a file, ensure we close it.
        if self.filename:
            self.file.close()
            if exc_val is None:
                log.info(f"... finished saving to {self.filename}")
            else:
                log.info(f"... exception raised; closing {self.filename}")
            # As above, we won't write to the log if we don't have a filename.


def write_people(
    people: Union[People, Iterable[Person]],
    file: TextIOBase = None,
    filename: str = None,
    plaintext: bool = False,
    plaintext_jsonl: bool = False,
    include_frequencies: bool = True,
    include_other_info: bool = False,
) -> None:
    """
    Writes from a :class:`People` object, or an iterable of :class:`Person`
    objects, to a file (specified by name or as a file-like object). See
    :class:`PeopleWriter`.
    """
    with PersonWriter(
        file=file,
        filename=filename,
        plaintext=plaintext,
        plaintext_jsonl=plaintext_jsonl,
        include_frequencies=include_frequencies,
        include_other_info=include_other_info,
    ) as writer:
        iter_people = people.people if isinstance(people, People) else people
        for person in iter_people:
            writer.write(person)
