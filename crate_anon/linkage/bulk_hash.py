#!/usr/bin/env python

"""
crate_anon/linkage/bulk_hash.py

===============================================================================

    Copyright (C) 2015-2020 Rudolf Cardinal (rudolf@pobox.com).

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

Tool to hash multiple IDs from the command line.

Test code to look at different types of digest:

.. code-block:: python

    import hashlib
    import hmac

    msg = "This is an ex-parrot!"
    key = "voom"

    key_bytes = str(key).encode('utf-8')
    msg_bytes = str(msg).encode('utf-8')
    digestmod = hashlib.sha256
    hmac_obj = hmac.new(key=key_bytes, msg=msg_bytes, digestmod=digestmod)

    # These are the two default kinds of digest:
    print(hmac_obj.digest())  # 8-bit binary
    print(hmac_obj.hexdigest())  # hexadecimal

    # Hex carries 4 bits per character. There are other possibilities,
    # notably:
    # - Base64 with 6 bits per character;
    # - Base32 with 5 bits per character.

"""

import argparse
import logging
from typing import Optional, TextIO

from cardinal_pythonlib.file_io import (
    gen_noncomment_lines,
    smart_open,
    writeline_nl,
)
from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from cardinal_pythonlib.hash import (
    HashMethods,
    make_hasher,
)

log = logging.getLogger(__name__)


def get_first_noncomment_line(filename: str) -> Optional[str]:
    try:
        with open(filename) as f:
            return next(gen_noncomment_lines(f))
    except StopIteration:
        return None


def bulk_hash(input_filename: str,
              output_filename: str,
              hash_method: str,
              key: str,
              keep_id: bool = True):
    """
    Hash lines from one file to another.

    Args:
        input_filename:
            input filename, or "-" for stdin
        output_filename:
            output filename, or "-" for stdin
        hash_method:
            method to use; e.g. ``HMAC_SHA256``
        key:
            secret key for hasher
        keep_id:
            produce CSV with ``hash,id`` pairs, rather than just lines with
            the hashes?

    Note that the hash precedes the ID with the ``keep_id`` option, which
    works best if the ID might contain commas.
    """
    log.info(f"Reading from: {input_filename}")
    log.info(f"Writing to: {output_filename}")
    log.info(f"Using hash method: {hash_method}")
    log.info(f"keep_id: {keep_id}")
    log.debug(f"Using key: {key!r}")  # NB security warning in help
    hasher = make_hasher(hash_method=hash_method, key=key)
    with smart_open(input_filename, "rt") as i:  # type: TextIO
        with smart_open(output_filename, "wt") as o:  # type: TextIO
            for line in gen_noncomment_lines(i):
                hashed = hasher.hash(line) if line else ""
                outline = f"{hashed},{line}" if keep_id else hashed
                # log.debug(f"{line!r} -> {hashed!r}")
                writeline_nl(o, outline)


def main() -> None:
    """
    Command-line entry point.
    """
    parser = argparse.ArgumentParser(
        description="Hash IDs in bulk, using a cryptographic hash function.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument(
        'infile', type=str,
        help="Input file, or '-' for stdin. "
             "Use one line per thing to be hashed. "
             "Comments (marked with '#') and blank lines are ignored. "
             "Lines have whitespace stripped left and right.")
    parser.add_argument(
        '--outfile', type=str, default="-",
        help="Output file, or '-' for stdout. "
             "One line will be written for every input line. "
             "Blank lines will be written for commented or blank input.")
    parser.add_argument(
        '--key', type=str,
        help="Secret key for hasher (warning: may be visible in process list; "
             "see also --keyfile)")
    parser.add_argument(
        '--keyfile', type=str,
        help="File whose first noncomment line contains the secret key for "
             "the hasher. (It will be whitespace-stripped right and left.)")
    parser.add_argument(
        '--method', choices=[HashMethods.HMAC_MD5,
                             HashMethods.HMAC_SHA256,
                             HashMethods.HMAC_SHA512],
        default=HashMethods.HMAC_MD5,
        help="Hash method")
    parser.add_argument(
        '--keepid', action="store_true",
        help="Produce CSV output with (hash,id) rather than just the hash")
    parser.add_argument(
        '--verbose', '-v', action="store_true",
        help="Be verbose (NB will write key to stderr)")

    args = parser.parse_args()
    main_only_quicksetup_rootlogger(logging.DEBUG if args.verbose
                                    else logging.INFO)

    assert bool(args.key) != bool(args.keyfile), (
        "Specify either --key or --keyfile (and not both)."
    )
    if args.keyfile:
        key = get_first_noncomment_line(args.keyfile)
        assert key, f"No key found in keyfile: {args.keyfile}"
    else:
        key = args.key

    bulk_hash(
        input_filename=args.infile,
        output_filename=args.outfile,
        hash_method=args.method,
        key=key,
        keep_id=args.keepid,
    )


if __name__ == "__main__":
    main()
