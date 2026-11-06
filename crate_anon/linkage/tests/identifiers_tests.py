"""
crate_anon/linkage/tests/fuzzy_id_match_tests.py

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

Test various types of person identifier that may be compared between two
people.

"""

from typing import Any
from unittest import TestCase

from pendulum import Date

from crate_anon.linkage.comparison import Comparison
from crate_anon.linkage.identifiers import Identifier
from crate_anon.linkage.matchconfig import MatchConfig


class TestIdentifier(Identifier):
    def __eq__(self, other: "Identifier") -> bool:
        return super().__eq__(other)

    def plaintext_str_core(self) -> str:
        return ""

    def as_dict(
        self, encrypt: bool = True, include_frequencies: bool = True
    ) -> dict[str, Any]:
        return {}

    def __bool__(self) -> bool:
        return True

    def ensure_has_freq_info_if_id_present(self) -> None:
        pass

    def comparison(self, candidate_id: "Identifier") -> Comparison | None:
        return None


class TestIdentifier1(TestIdentifier):
    def from_plaintext_str(cls, cfg: MatchConfig, x: str) -> "Identifier":
        return TestIdentifier1()

    @classmethod
    def from_dict(
        cls, cfg: MatchConfig, d: dict[str, Any], hashed: bool
    ) -> "Identifier":
        return TestIdentifier1()


class TestIdentifier2(TestIdentifier):
    def from_plaintext_str(cls, cfg: MatchConfig, x: str) -> "Identifier":
        return TestIdentifier2()

    @classmethod
    def from_dict(
        cls, cfg: MatchConfig, d: dict[str, Any], hashed: bool
    ) -> "Identifier":
        return TestIdentifier2()


class IdentifierTests(TestCase):
    def test_identifiers_with_different_types_not_equal(self) -> None:
        identifier_1 = TestIdentifier1(None, False)
        identifier_2 = TestIdentifier2(None, False)

        self.assertNotEqual(identifier_1, identifier_2)

    def test_different_identifiers_with_same_types_not_equal(self) -> None:
        identifier_1 = TestIdentifier1(
            None, False, start_date=Date(2026, 11, 3)
        )
        identifier_2 = TestIdentifier1(
            None, False, start_date=Date(2025, 2, 7)
        )

        self.assertNotEqual(identifier_1, identifier_2)

    def test_identifiers_with_same_attributes_equal(self) -> None:
        identifier_1 = TestIdentifier1(None, False)
        identifier_2 = TestIdentifier1(None, False)

        self.assertEqual(identifier_1, identifier_2)
