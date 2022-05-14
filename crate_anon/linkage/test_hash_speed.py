#!/usr/bin/env python

"""
crate_anon/linkage/test_hash_speed.py

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

**Test the speed of hashing.**

The question is: if someone malicious learned a secret hash key, how long would
it take them to generate a reverse map from a known identifier space?

Specimen results, for padding length 9 and the HMAC_MD5 algorithm, on Wombat
(3.5 GHz CPU), tested with 100000 (1e5) iterations (which took 0.72 s, piping
to ``/dev/null``):

- 1e9 operations will take about 7200 s = 2 hours.
  This is the right order of magniture for NHS numbers (9 digits plus a
  checksum; other rules might restrict that a bit more).

- 7.3e12 operations will take about 52667022 s = 1.7 years
  This is the right order of magnitude for NHS numbers plus dates of birth
  covering 20 years (1e9 for NHS number * 365 days/year * 20 years).

- 3.65e13 operations will take about 263335113 s = 8.4 years
  This is the right order of magnitude for NHS numbers plus DOBs covering
  a century (1e9 for NHS number * 365 days/year * 100 years).

The hash algorithm isn't a major factor; moving from HMAC_MD5 to HMAC_SHA512,
for example, only takes the time for 1e5 iterations from 0.72s to 0.86.

"""

import argparse
import logging
import time
from typing import Iterable, List, TextIO

from cardinal_pythonlib.file_io import smart_open, writeline_nl
from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from cardinal_pythonlib.hash import HashMethods, make_hasher
from cardinal_pythonlib.randomness import generate_random_string

log = logging.getLogger(__name__)


def gen_dummy_data(n: int, n_padding_chars: int) -> Iterable[str]:
    """
    Generate some random strings.
    """
    padding = "x" * n_padding_chars
    for i in range(n):
        yield padding + str(i)


def test_hash_speed(
    output_filename: str,
    hash_method: str,
    key: str,
    ntests: int,
    intended_possibilities: List[int],
    n_padding_chars: int,
):
    """
    Hash lines from one file to another.

    Args:
        output_filename:
            Output filename, or "-" for stdin
        hash_method:
            Method to use; e.g. ``HMAC_SHA256``
        key:
            Secret key for hasher
        ntests:
            Number of hashes to perform.
        intended_possibilities:
            Number of hashes to estimate time for.
        n_padding_chars:
            Length of padding (characters).

    Note that the hash precedes the ID with the ``keep_id`` option, which
    works best if the ID might contain commas.
    """
    log.info(f"Writing to: {output_filename}")
    log.info(f"Using hash method: {hash_method}")
    log.info(f"Hashing some random data {ntests} times, using one CPU")
    log.info(f"Padding length: {n_padding_chars}")
    log.debug(f"Using key: {key!r}")  # NB security warning in help

    hasher = make_hasher(hash_method=hash_method, key=key)
    with smart_open(output_filename, "wt") as o:  # type: TextIO
        start_time = time.time()
        for data in gen_dummy_data(ntests, n_padding_chars):
            hashed = hasher.hash(data)
            writeline_nl(o, f"{data} -> {hashed}")
        end_time = time.time()

    time_taken_s = end_time - start_time
    log.info(f"Start time (s): {start_time}")
    log.info(f"End time (s): {end_time}")
    log.info(f"Time taken (s): {time_taken_s}")
    log.info(f"Number of hash operations: {ntests}")
    for intended in intended_possibilities:
        estimated_time_s = intended * time_taken_s / ntests
        log.info(
            f"For {intended} operations (on a single CPU), "
            f"estimated time (s): {estimated_time_s}"
        )


def main() -> None:
    """
    Command-line entry point.
    """
    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        description="Hash IDs in bulk, using a cryptographic hash function.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--outfile",
        type=str,
        default="-",
        help="Output file; can use '-' for stdout (and pipe to /dev/null).",
    )
    parser.add_argument(
        "--key",
        type=str,
        help="Key for hasher. Ordinarily this would be secret, but this is "
        "just for testing. Default is random.",
    )
    parser.add_argument(
        "--keyfile",
        type=str,
        help="File whose first noncomment line contains the secret key for "
        "the hasher. (It will be whitespace-stripped right and left.)",
    )
    parser.add_argument(
        "--method",
        choices=[
            HashMethods.HMAC_MD5,
            HashMethods.HMAC_SHA256,
            HashMethods.HMAC_SHA512,
        ],
        default=HashMethods.HMAC_MD5,
        help="Hash method",
    )
    parser.add_argument(
        "--ntests",
        type=int,
        default=100000,
        help="Number of hash tests to time for real (a small number).",
    )
    parser.add_argument(
        "--padding",
        type=int,
        default=9,
        help="Number of padding characters (appended to a string version of "
        "a consecutive integer covering the range of --ntests).",
    )
    parser.add_argument(
        "--intended",
        type=int,
        nargs="+",
        default=[1000000000, 7300000000000, 36500000000000],
        help="Number of hash tests to calculate time for (a big number). For"
        "example, approx. 1000000000 (1e9) for NHS number; "
        "36500000000000 (3.65e13) for NHS number "
        "plus DOBs covering a century; "
        "7300000000000 (7.3e12) for NHS number "
        "plus DOBs covering two decades.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Be verbose (NB will write key to stderr)",
    )

    args = parser.parse_args()
    main_only_quicksetup_rootlogger(
        logging.DEBUG if args.verbose else logging.INFO
    )

    key = generate_random_string(length=64) if args.key is None else args.key

    test_hash_speed(
        output_filename=args.outfile,
        hash_method=args.method,
        key=key,
        n_padding_chars=args.padding,
        ntests=args.ntests,
        intended_possibilities=args.intended,
    )


if __name__ == "__main__":
    main()
