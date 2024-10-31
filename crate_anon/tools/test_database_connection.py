#!/usr/bin/env python

"""
installer/test_database_connection.py

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

**Test a database connection from a SQLAlchemy URL.**

"""

import argparse

from sqlalchemy import create_engine


def test_connection(url: str) -> None:
    engine = create_engine(url)

    try:
        connection = engine.connect()
    except Exception:
        print(f"Failed to connect to {engine.url!r}")

        raise

    print(f"Successfully connected to {engine.url!r}")
    connection.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "url",
        type=str,
        help="SQLAlchemy URL to test",
    )
    args = parser.parse_args()

    test_connection(args.url)


if __name__ == "__main__":
    main()
