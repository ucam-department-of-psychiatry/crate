#!/usr/bin/env python

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

Unit tests.

"""

# =============================================================================
# Imports
# =============================================================================

import logging
import unittest
from typing import List, Tuple, Type

from cardinal_pythonlib.probability import probability_from_log_odds
from pendulum import Date

from crate_anon.linkage.constants import (
    GENDER_FEMALE,
    GENDER_MALE,
    VALID_GENDERS,
)
from crate_anon.linkage.identifiers import (
    DateOfBirth,
    Forename,
    Gender,
    Identifier,
    Postcode,
    Surname,
    TemporalIDHolder,
)
from crate_anon.linkage.helpers import (
    get_postcode_sector,
    is_valid_isoformat_date,
    POSTCODE_REGEX,
    standardize_name,
    standardize_postcode,
)
from crate_anon.linkage.matchconfig import MatchConfig
from crate_anon.linkage.person import People, Person

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

BAD_DATE_STRINGS = ["1950-31-12", "1950", "blah", "2000-02-30"]
GOOD_DATE_STRINGS = ["1950-12-31", "1890-01-01", "2000-01-01"]
BAD_POSTCODES = [
    "99XX99",
    "CB99 9XXY",
    "CB99",
    "CB2",
    "NW19TTTEMP",
    "NW19TT TEMP",
]
GOOD_POSTCODES = [
    "CB99 9XY",
    "CB2 0QQ",
    "ZZ99 3VZ",
    "Z Z 9 9 3 V Z",
    "zz993vz",
]  # good once standardized, anyway
BAD_GENDERS = ["Y", "male", "female", "?"]


# =============================================================================
# Helper class
# =============================================================================


class TestCondition(object):
    """
    Two representations of a person and whether they should match.
    """

    def __init__(
        self,
        cfg: MatchConfig,
        person_a: Person,
        person_b: Person,
        should_match: bool,
        debug: bool = True,
    ) -> None:
        """
        Args:
            cfg: the main :class:`MatchConfig` object
            person_a: one representation of a person
            person_b: another representation of a person
            should_match: should they be treated as the same person?
            debug: be verbose?
        """
        self.cfg = cfg
        self.person_a = person_a
        self.person_b = person_b
        self.should_match = should_match

        for id_person in (self.person_a, self.person_b):
            assert id_person.is_plaintext()
            id_person.ensure_valid_as_proband(debug_allow_no_dob=True)
            for identifier in id_person.debug_gen_identifiers():
                assert identifier.is_plaintext

        log.info("- Making hashed versions for later")
        self.hashed_a = self.person_a.hashed()
        self.hashed_b = self.person_b.hashed()
        for h_person in (self.hashed_a, self.hashed_b):
            assert h_person.is_hashed()
            h_person.ensure_valid_as_proband(debug_allow_no_dob=True)
            for identifier in h_person.debug_gen_identifiers():
                assert not identifier.is_plaintext
        self.debug = debug

    def log_odds_same_plaintext(self) -> float:
        """
        Checks whether the plaintext person objects match.

        Returns:
            float: the log odds that they are the same person
        """
        return self.person_a.log_odds_same(self.person_b)

    def log_odds_same_hashed(self) -> float:
        """
        Checks whether the hashed versions match.

        Returns:
            float: the log odds that they are the same person
        """
        return self.hashed_a.log_odds_same(self.hashed_b)

    def matches_plaintext(self) -> Tuple[bool, float]:
        """
        Do the plaintext versions match, by threshold?

        Returns:
            tuple: (matches, log_odds)
        """
        log_odds = self.log_odds_same_plaintext()
        return self.cfg.person_matches(log_odds), log_odds

    def matches_hashed(self) -> Tuple[bool, float]:
        """
        Do the raw versions match, by threshold?

        Returns:
            bool: is there a match?
        """
        log_odds = self.log_odds_same_hashed()
        return self.cfg.person_matches(log_odds), log_odds

    def assert_correct(self) -> None:
        """
        Asserts that both the raw and hashed versions match, or don't match,
        according to ``self.should_match``.
        """
        log.info(f"Comparing:\n- {self.person_a!r}\n- {self.person_b!r}")

        log.info("(1) Comparing plaintext")
        matches_raw, log_odds_plaintext = self.matches_plaintext()
        p_plaintext = probability_from_log_odds(log_odds_plaintext)
        p_plain_str = f"P(match | D) = {p_plaintext}"
        if matches_raw == self.should_match:
            if matches_raw:
                log.info(f"... should and does match: {p_plain_str}")
            else:
                log.info(f"... should not and does not match: {p_plain_str}")
        else:
            log_odds = log_odds_plaintext
            raise AssertionError(
                f"Match failure: "
                f"matches_raw = {matches_raw}, "
                f"should_match = {self.should_match}, "
                f"log_odds = {log_odds}, "
                f"min_log_odds_for_match = {self.cfg.min_log_odds_for_match}, "
                f"P(match) = {probability_from_log_odds(log_odds)}, "
                f"person_a = {self.person_a}, "
                f"person_b = {self.person_b}"
            )

        log.info(
            f"(2) Comparing hashed:\n- {self.hashed_a}\n- {self.hashed_b}"
        )  # noqa
        matches_hashed, log_odds_hashed = self.matches_hashed()
        p_hashed = probability_from_log_odds(log_odds_hashed)
        p_hashed_str = f"P(match | D) = {p_hashed}"
        if matches_hashed == self.should_match:
            if matches_hashed:
                log.info(f"... should and does match: {p_hashed_str}")
            else:
                log.info(f"... should not and does not match: {p_hashed_str}")
        else:
            log_odds = log_odds_hashed
            raise AssertionError(
                f"Match failure: "
                f"matches_hashed = {matches_hashed}, "
                f"should_match = {self.should_match}, "
                f"log_odds = {log_odds}, "
                f"threshold = {self.cfg.min_log_odds_for_match}, "
                f"min_log_odds_for_match = {self.cfg.min_log_odds_for_match}, "
                f"P(match) = {probability_from_log_odds(log_odds)}, "
                f"person_a = {self.person_a}, "
                f"person_b = {self.person_b}, "
                f"hashed_a = {self.hashed_a}, "
                f"hashed_b = {self.hashed_b}"
            )


# =============================================================================
# Unit tests
# =============================================================================


class DummyTemporalIdentifierTests(unittest.TestCase):
    """
    Unit tests for :class:`DummyTemporalIdentifier`.
    """

    def test_overlap(self) -> None:
        d1 = Date(2000, 1, 1)
        d2 = Date(2000, 1, 2)
        d3 = Date(2000, 1, 3)
        d4 = Date(2000, 1, 4)
        p = "dummypostcode"
        # ---------------------------------------------------------------------
        # Overlaps
        # ---------------------------------------------------------------------
        self.assertEqual(
            TemporalIDHolder(p, d1, d2).overlaps(TemporalIDHolder(p, d2, d3)),
            True,
        )
        self.assertEqual(
            TemporalIDHolder(p, d2, d3).overlaps(TemporalIDHolder(p, d1, d2)),
            True,
        )
        self.assertEqual(
            TemporalIDHolder(p, d1, d4).overlaps(TemporalIDHolder(p, d2, d3)),
            True,
        )
        self.assertEqual(
            TemporalIDHolder(p, d1, None).overlaps(
                TemporalIDHolder(p, None, d4)
            ),
            True,
        )
        self.assertEqual(
            TemporalIDHolder(p, None, None).overlaps(
                TemporalIDHolder(p, None, None)
            ),
            True,
        )
        # ---------------------------------------------------------------------
        # Non-overlaps
        # ---------------------------------------------------------------------
        self.assertEqual(
            TemporalIDHolder(p, d1, d2).overlaps(TemporalIDHolder(p, d3, d4)),
            False,
        )
        self.assertEqual(
            TemporalIDHolder(p, None, d1).overlaps(
                TemporalIDHolder(p, d2, None)
            ),
            False,
        )


class FuzzyLinkageTests(unittest.TestCase):
    """
    Tests of the fuzzy linkage system.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.cfg = MatchConfig()
        self.p1 = Postcode(
            cfg=self.cfg,
            postcode="CB2 0QQ",  # Addenbrooke's Hospital
            start_date=Date(2000, 1, 1),
            end_date=Date(2010, 1, 1),
        )
        self.p2 = Postcode(
            cfg=self.cfg,
            postcode="CB2 3EB",  # Department of Psychology
            start_date=Date(2000, 1, 1),
            end_date=Date(2010, 1, 1),
        )
        self.alice_bcd_unique_2000_add = Person(
            cfg=self.cfg,
            local_id="1",
            first_name="Alice",
            middle_names=["Beatrice", "Celia", "Delilah"],
            surname="Rarename",
            dob="2000-01-01",
            postcodes=[self.p1],
        )
        self.alec_bcd_unique_2000_add = Person(
            cfg=self.cfg,
            local_id="2",
            first_name="Alec",  # same metaphone as Alice
            middle_names=["Beatrice", "Celia", "Delilah"],
            surname="Rarename",
            dob="2000-01-01",
            postcodes=[self.p1],
        )
        self.bob_bcd_unique_2000_add = Person(
            cfg=self.cfg,
            local_id="3",
            first_name="Bob",
            middle_names=["Beatrice", "Celia", "Delilah"],
            surname="Rarename",
            dob="2000-01-01",
            postcodes=[self.p1],
        )
        self.alice_bc_unique_2000_add = Person(
            cfg=self.cfg,
            local_id="4",
            first_name="Alice",
            middle_names=["Beatrice", "Celia"],
            surname="Rarename",
            dob="2000-01-01",
            postcodes=[self.p1],
        )
        self.alice_b_unique_2000_add = Person(
            cfg=self.cfg,
            local_id="5",
            first_name="Alice",
            middle_names=["Beatrice"],
            surname="Rarename",
            dob="2000-01-01",
            postcodes=[self.p1],
        )
        self.alice_jones_2000_add = Person(
            cfg=self.cfg,
            local_id="6",
            first_name="Alice",
            surname="Jones",
            dob="2000-01-01",
            postcodes=[self.p1],
        )
        self.bob_smith_1950_psych = Person(
            cfg=self.cfg,
            local_id="7",
            first_name="Bob",
            surname="Smith",
            dob="1950-05-30",
            postcodes=[self.p2],
        )
        self.alice_smith_1930 = Person(
            cfg=self.cfg,
            local_id="8",
            first_name="Alice",
            surname="Smith",
            dob="1930-01-01",
        )
        self.alice_smith_2000 = Person(
            cfg=self.cfg,
            local_id="9",
            first_name="Alice",
            surname="Smith",
            dob="2000-01-01",
        )
        self.alice_smith = Person(
            cfg=self.cfg,
            local_id="10",
            first_name="Alice",
            surname="Smith",
        )
        self.middle_test_1 = Person(
            cfg=self.cfg,
            local_id="11",
            first_name="Alice",
            middle_names=["Betty", "Caroline"],
            surname="Smith",
        )
        self.middle_test_2 = Person(
            cfg=self.cfg,
            local_id="12",
            first_name="Alice",
            middle_names=["Betty", "Dorothy", "Elizabeth"],
            surname="Smith",
        )
        self.all_people = [
            self.alice_bcd_unique_2000_add,
            self.alec_bcd_unique_2000_add,
            self.bob_bcd_unique_2000_add,
            self.alice_bc_unique_2000_add,
            self.alice_b_unique_2000_add,
            self.alice_jones_2000_add,
            self.bob_smith_1950_psych,
            self.alice_smith_1930,
            self.alice_smith_2000,
            self.alice_smith,
            self.middle_test_1,
            self.middle_test_2,
        ]
        self.all_people_hashed = [p.hashed() for p in self.all_people]
        self.people_plaintext = People(cfg=self.cfg)
        self.people_plaintext.add_people(self.all_people)
        self.people_hashed = People(cfg=self.cfg)
        self.people_hashed.add_people(self.all_people_hashed)

    def test_fuzzy_linkage_basics(self) -> None:
        cfg = self.cfg
        for surname in ["Smith", "Jones", "Blair", "Cardinal", "XYZ"]:
            f = cfg.surname_freq(surname)
            log.info(f"Surname frequency for {surname}: {f}")

        for forename, gender in [
            ("James", GENDER_MALE),
            ("Rachel", GENDER_FEMALE),
            ("Phoebe", GENDER_FEMALE),
            ("Elizabeth", GENDER_FEMALE),
            ("Elizabeth", GENDER_MALE),
            ("Elizabeth", ""),
            ("Rowan", GENDER_FEMALE),
            ("Rowan", GENDER_MALE),
            ("Rowan", ""),
            ("XYZ", ""),
        ]:
            f = cfg.forename_freq(forename, gender)
            log.info(
                f"Forename frequency for {forename}, gender {gender}: {f}"
            )

        # Examples are hospitals and colleges in Cambridge (not residential)
        # but it gives a broad idea.
        for postcode in ["CB2 0QQ", "CB2 0SZ", "CB2 3EB", "CB3 9DF"]:
            p = cfg.debug_postcode_unit_population(postcode)
            log.info(
                f"Calculated population for postcode unit {postcode}: {p}"
            )

        for ps in ["CB2 0", "CB2 1", "CB2 2", "CB2 3"]:
            p = cfg.debug_postcode_sector_population(ps)
            log.info(f"Calculated population for postcode sector {ps}: {p}")

    def test_standardize_name(self) -> None:
        tests = (
            # name, standardized version
            ("ALJAZEERA", "ALJAZEERA"),
            ("aljazeera", "ALJAZEERA"),
            ("Al Jazeera", "ALJAZEERA"),
            ("Al'Jazeera", "ALJAZEERA"),
            ("Al'Jazeera'", "ALJAZEERA"),
            ('"Al Jazeera"', "ALJAZEERA"),
        )
        for item, target in tests:
            self.assertEqual(standardize_name(item), target)

    def test_standardize_postcode(self) -> None:
        tests = (
            # name, standardized version
            ("CB20QQ", "CB20QQ"),
            ("   CB2 0QQ   ", "CB20QQ"),
            ("   CB2-0 QQ   ", "CB20QQ"),
            ("cb2 0qq", "CB20QQ"),
        )
        for item, target in tests:
            self.assertEqual(standardize_postcode(item), target)

    def test_get_postcode_sector(self) -> None:
        tests = (
            # postcode, sector
            ("CB20QQ", "CB20"),
            ("   CB2 0QQ   ", "CB20"),
            ("   CB2-0 QQ   ", "CB20"),
            ("cb2 0qq", "CB20"),
        )
        for item, target in tests:
            self.assertEqual(get_postcode_sector(item), target)

    def test_fuzzy_linkage_matches(self) -> None:
        test_values = [
            # Very easy match
            TestCondition(
                cfg=self.cfg,
                person_a=self.alice_bcd_unique_2000_add,
                person_b=self.alice_bcd_unique_2000_add,
                should_match=True,
            ),
            # Easy match
            TestCondition(
                cfg=self.cfg,
                person_a=self.alice_bc_unique_2000_add,
                person_b=self.alice_b_unique_2000_add,
                should_match=True,
            ),
            # Easy non-match
            TestCondition(
                cfg=self.cfg,
                person_a=self.alice_jones_2000_add,
                person_b=self.bob_smith_1950_psych,
                should_match=False,
            ),
            # Very ambiguous (1)
            TestCondition(
                cfg=self.cfg,
                person_a=self.alice_smith,
                person_b=self.alice_smith_1930,
                should_match=False,
            ),
            # Very ambiguous (2)
            TestCondition(
                cfg=self.cfg,
                person_a=self.alice_smith,
                person_b=self.alice_smith_2000,
                should_match=False,
            ),
            TestCondition(
                cfg=self.cfg,
                person_a=self.alice_bcd_unique_2000_add,
                person_b=self.alec_bcd_unique_2000_add,
                should_match=True,
            ),
            TestCondition(
                cfg=self.cfg,
                person_a=self.alice_bcd_unique_2000_add,
                person_b=self.bob_bcd_unique_2000_add,
                should_match=False,
            ),
        ]  # type: List[TestCondition]
        log.info("Testing comparisons...")
        for i, test in enumerate(test_values, start=1):
            log.info(f"Comparison {i}...")
            test.assert_correct()

    def test_fuzzy_more_complex(self) -> None:
        log.info("Testing proband-versus-sample...")
        for i in range(len(self.all_people)):
            proband_plaintext = self.all_people[i]
            log.info(f"Plaintext search with proband: {proband_plaintext}")
            plaintext_winner = self.people_plaintext.get_unique_match(
                proband_plaintext
            )
            log.info(f"... WINNER: {plaintext_winner}")
            log.info(f"Hashed search with proband: {proband_plaintext}\n")
            proband_hashed = self.all_people_hashed[i]  # same order
            hashed_winner = self.people_hashed.get_unique_match(proband_hashed)
            log.info(f"... WINNER: {hashed_winner}")

        log.info(
            f"Testing middle name comparisons between...\n"
            f"{self.middle_test_1}\n"
            f"{self.middle_test_2}"
        )
        # noinspection PyProtectedMember
        for comp in self.middle_test_1._comparisons_middle_names(
            self.middle_test_2
        ):
            log.info(comp)

    def test_date_regex(self) -> None:
        for b in BAD_DATE_STRINGS:
            self.assertFalse(is_valid_isoformat_date(b))
        for g in GOOD_DATE_STRINGS:
            self.assertTrue(is_valid_isoformat_date(g))

    def test_identifier_dob(self) -> None:
        cfg = MatchConfig()
        for b in BAD_DATE_STRINGS:
            with self.assertRaises(ValueError):
                _ = DateOfBirth(cfg, b)
        for g in GOOD_DATE_STRINGS:
            d = DateOfBirth(cfg, g)
            self.assertEqual(d.dob, g)
            self.assertEqual(str(d), g)

    def test_postcode_regex(self) -> None:
        for b in BAD_POSTCODES:
            self.assertIsNone(
                POSTCODE_REGEX.match(b), f"Postcode {b!r} matched but is bad"
            )
            sb = standardize_postcode(b)
            self.assertIsNone(
                POSTCODE_REGEX.match(sb),
                f"Postcode {b!r} matched after standardization to {sb!r} "
                f"but is bad",
            )
        for g in GOOD_POSTCODES:
            sg = standardize_postcode(g)
            self.assertTrue(
                POSTCODE_REGEX.match(sg),
                f"Postcode {sg!r} (from {g!r}) did not match but is good",
            )

    def test_identifier_postcode(self) -> None:
        cfg = MatchConfig()
        for b in BAD_POSTCODES:
            with self.assertRaises(ValueError):
                _ = Postcode(cfg, b)
        early = Date(2020, 1, 1)
        late = Date(2021, 12, 31)
        for g in GOOD_POSTCODES:
            with self.assertRaises(ValueError):
                _ = Postcode(cfg, g, start_date=late, end_date=early)
            p = Postcode(cfg, g)
            self.assertEqual(p.postcode_unit, standardize_postcode(g))
        empty = Postcode(cfg, "")
        self.assertEqual(str(empty), "")

    def test_identifier_gender(self) -> None:
        cfg = MatchConfig()
        for b in BAD_GENDERS:
            with self.assertRaises(ValueError):
                _ = Gender(cfg, b)
        for g in VALID_GENDERS:
            gender = Gender(cfg, g)
            self.assertEqual(gender.gender, g)
            self.assertEqual(str(g), g)
        empty = Gender(cfg, "")
        self.assertEqual(str(empty), "")

    def test_identifier_transformations(self) -> None:
        cfg = MatchConfig()
        identifiable = [
            Postcode(cfg, postcode="CB2 0QQ"),
            DateOfBirth(cfg, dob="2000-12-31"),
            Gender(cfg, gender=GENDER_MALE),
            Forename(cfg, name="Elizabeth", gender=GENDER_FEMALE),
            Surname(cfg, name="Smith", gender=GENDER_FEMALE),
        ]  # type: List[Identifier]
        for i in identifiable:
            self.assertTrue(i.is_plaintext)
            i_class = type(i)  # type: Type[Identifier]
            d = i.hashed_dict(include_frequencies=True)
            h = i_class.from_hashed_dict(cfg, d)
            self.assertFalse(h.is_plaintext)
            h.ensure_has_freq_info_if_id_present()
