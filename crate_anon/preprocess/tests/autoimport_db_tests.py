"""
crate_anon/preprocess/tests/autoimport_db_tests.py

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

Unit testing.

"""

# =============================================================================
# Imports
# =============================================================================

import datetime
from unittest import TestCase

import pendulum
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    String,
)

from crate_anon.preprocess.autoimport_db import (
    ColumnTypeDetector,
    is_date_like_not_datetime_like,
    is_datetime_or_date_like,
)


# =============================================================================
# Unit tests
# =============================================================================

DUMMY_COLNAME = "somecolumn"

DUMMY_DATE = datetime.date(2000, 12, 31)
DUMMY_DATE_P = pendulum.Date(2000, 12, 31)
DUMMY_DATE_STR = "2000-12-31"

DUMMY_DATETIME = datetime.datetime(2000, 12, 31, 23, 59, 59)
DUMMY_DATETIME_P = pendulum.DateTime(2000, 12, 31, 23, 59, 59)
DUMMY_DATETIME_STR = "2000-12-31T23:59:59"

DUMMY_DATETIME_P_DATEONLY = pendulum.DateTime(2000, 12, 31)


class AutoImportDBTests(TestCase):
    """
    Test automatic column type detection.
    """

    def test_is_date_like(self) -> None:
        self.assertEqual(is_date_like_not_datetime_like(DUMMY_DATE), True)
        self.assertEqual(is_date_like_not_datetime_like(DUMMY_DATE_P), True)
        self.assertEqual(is_date_like_not_datetime_like(DUMMY_DATE_STR), True)

        self.assertEqual(is_date_like_not_datetime_like(DUMMY_DATETIME), False)
        self.assertEqual(
            is_date_like_not_datetime_like(DUMMY_DATETIME_P), False
        )
        self.assertEqual(
            is_date_like_not_datetime_like(DUMMY_DATETIME_STR), False
        )

        self.assertEqual(
            is_date_like_not_datetime_like(DUMMY_DATETIME_P_DATEONLY), True
        )

    def test_is_datetime_like(self) -> None:
        # Dates are also datetime-like.
        self.assertEqual(is_datetime_or_date_like(DUMMY_DATE), True)
        self.assertEqual(is_datetime_or_date_like(DUMMY_DATE_P), True)
        self.assertEqual(is_datetime_or_date_like(DUMMY_DATE_STR), True)

        self.assertEqual(is_datetime_or_date_like(DUMMY_DATETIME), True)
        self.assertEqual(is_datetime_or_date_like(DUMMY_DATETIME_P), True)
        self.assertEqual(is_datetime_or_date_like(DUMMY_DATETIME_STR), True)

        self.assertEqual(
            is_datetime_or_date_like(DUMMY_DATETIME_P_DATEONLY), True
        )

    def test_datatype_detection_missing(self) -> None:
        # No data:
        d = ColumnTypeDetector(DUMMY_COLNAME)
        self.assertRaises(ValueError, d.sqlalchemy_column)

    def test_datatype_detection_null(self) -> None:
        # Only NULL data:
        d = ColumnTypeDetector(DUMMY_COLNAME, [None])
        self.assertRaises(ValueError, d.sqlalchemy_column)

    def test_datatype_detection_int(self) -> None:
        # Integers:
        d = ColumnTypeDetector(DUMMY_COLNAME, [4, -3, None])
        c = d.sqlalchemy_column()
        self.assertEqual(type(c.type), BigInteger)
        self.assertEqual(c.nullable, True)
        # ... and rejecting inappropriate nullable=False:
        self.assertRaises(ValueError, d.sqlalchemy_column, nullable=False)

    def test_datatype_detection_float(self) -> None:
        # Float:
        d = ColumnTypeDetector(DUMMY_COLNAME, [4, -3, 2.5, None])
        c = d.sqlalchemy_column()
        self.assertEqual(type(c.type), Float)
        self.assertEqual(c.nullable, True)

    def test_datatype_detection_str_null(self) -> None:
        # String:
        d = ColumnTypeDetector(DUMMY_COLNAME, ["hello", "world", None])
        c = d.sqlalchemy_column()
        self.assertEqual(type(c.type), String)
        self.assertEqual(c.nullable, True)

    def test_datatype_detection_str_not_null(self) -> None:
        # String, NOT NULL:
        d = ColumnTypeDetector(DUMMY_COLNAME, ["hello", "world"])
        c = d.sqlalchemy_column(nullable=False)
        self.assertEqual(type(c.type), String)
        self.assertEqual(c.nullable, False)

    def test_datatype_detection_bad_mix(self) -> None:
        # Inappropriately mixed data:
        d = ColumnTypeDetector(DUMMY_COLNAME, [4, -3, 2.5, "hello", None])
        self.assertRaises(ValueError, d.sqlalchemy_column)

    def test_datatype_detection_date(self) -> None:
        # Dates
        d = ColumnTypeDetector(
            DUMMY_COLNAME,
            [
                DUMMY_DATE,
                DUMMY_DATE_P,
                DUMMY_DATE_STR,
                DUMMY_DATETIME_P_DATEONLY,
                None,
            ],
        )
        c = d.sqlalchemy_column()
        self.assertEqual(type(c.type), Date)

    def test_datatype_detection_datetime(self) -> None:
        # Dates
        d = ColumnTypeDetector(
            DUMMY_COLNAME,
            [DUMMY_DATETIME, DUMMY_DATETIME_P, DUMMY_DATETIME_STR, None],
        )
        c = d.sqlalchemy_column()
        self.assertEqual(type(c.type), DateTime)

    def test_datatype_detection_mixed_date_datetime(self) -> None:
        # Dates plus datetimes should resolve to datetime.
        d = ColumnTypeDetector(
            DUMMY_COLNAME,
            [
                DUMMY_DATE,
                DUMMY_DATE_STR,
                DUMMY_DATETIME,
                DUMMY_DATETIME_STR,
                None,
            ],
        )
        c = d.sqlalchemy_column()
        self.assertEqual(type(c.type), DateTime)

    def test_datatype_detection_mixed_str_date_datetime(self) -> None:
        # Dates plus datetimes plus other strings should resolve to str.
        d = ColumnTypeDetector(
            DUMMY_COLNAME,
            [
                DUMMY_DATE,
                DUMMY_DATE_STR,
                DUMMY_DATETIME,
                DUMMY_DATETIME_STR,
                "hello",
                None,
            ],
        )
        c = d.sqlalchemy_column()
        self.assertEqual(type(c.type), String)

    def test_datatype_detection_bool(self) -> None:
        # Boolean
        d = ColumnTypeDetector(
            DUMMY_COLNAME,
            [
                True,
                False,
                None,
            ],
        )
        c = d.sqlalchemy_column()
        self.assertEqual(type(c.type), Boolean)
