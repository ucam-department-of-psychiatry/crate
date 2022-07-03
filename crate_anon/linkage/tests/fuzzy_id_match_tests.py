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
    GENDER_MISSING,
    GENDER_OTHER,
    VALID_GENDERS,
)
from crate_anon.linkage.identifiers import (
    DateOfBirth,
    Forename,
    Gender,
    Identifier,
    Postcode,
    Surname,
    SurnameFragment,
    TemporalIDHolder,
)
from crate_anon.linkage.helpers import (
    get_postcode_sector,
    is_valid_isoformat_date,
    POSTCODE_REGEX,
    remove_redundant_whitespace,
    safe_upper,
    standardize_name,
    standardize_postcode,
    surname_alternative_fragments,
)
from crate_anon.linkage.matchconfig import MatchConfig
from crate_anon.linkage.people import DuplicateIDError, People
from crate_anon.linkage.person import Person

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
    " zz993vz ",
]  # good once standardized, anyway
BAD_GENDERS = ["Y", "male", "female", "?"]


# =============================================================================
# Helper class
# =============================================================================


class TestCondition:
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

    def check_comparison_as_expected(self) -> None:
        """
        Asserts that both the raw and hashed versions match, or don't match,
        according to ``self.should_match``.
        """
        log.info(
            f"Comparing:\n" f"- {self.person_a!r}\n" f"- {self.person_b!r}"
        )
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
            f"(2) Comparing hashed:\n"
            f"- {self.hashed_a}\n"
            f"- {self.hashed_b}"
        )
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

        log.info(
            "(3) Results of plaintext match should equal result of hashed "
            "match"
        )
        if log_odds_hashed != log_odds_plaintext:
            raise AssertionError(
                "Plaintext/hashed comparison discrepancy: "
                f"person_a = {self.person_a}, "
                f"person_b = {self.person_b}, "
                "log_odds_plaintext = {log_odds_plaintext}, "
                f"log_odds_hashed = {log_odds_hashed}"
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
        self.cfg = MatchConfig(rounding_sf=None)
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
        self.alice_bcd_rarename_2000_add = Person(
            cfg=self.cfg,
            local_id="1",
            first_name="Alice",
            middle_names=["Beatrice", "Celia", "Delilah"],
            surnames=["Rarename"],
            dob="2000-01-01",
            postcodes=[self.p1],
        )
        self.alec_bcd_rarename_2000_add = Person(
            cfg=self.cfg,
            local_id="2",
            first_name="Alec",  # same metaphone as Alice
            middle_names=["Beatrice", "Celia", "Delilah"],
            surnames=["Rarename"],
            dob="2000-01-01",
            postcodes=[self.p1],
        )
        self.bob_bcd_rarename_2000_add = Person(
            cfg=self.cfg,
            local_id="3",
            first_name="Bob",
            middle_names=["Beatrice", "Celia", "Delilah"],
            surnames=["Rarename"],
            dob="2000-01-01",
            postcodes=[self.p1],
        )
        self.alice_bc_rarename_2000_add = Person(
            cfg=self.cfg,
            local_id="4",
            first_name="Alice",
            middle_names=["Beatrice", "Celia"],
            surnames=["Rarename"],
            dob="2000-01-01",
            postcodes=[self.p1],
        )
        self.alice_b_rarename_2000_add = Person(
            cfg=self.cfg,
            local_id="5",
            first_name="Alice",
            middle_names=["Beatrice"],
            surnames=["Rarename"],
            dob="2000-01-01",
            postcodes=[self.p1],
        )
        self.alice_jones_2000_add = Person(
            cfg=self.cfg,
            local_id="6",
            first_name="Alice",
            surnames=["Jones"],
            dob="2000-01-01",
            postcodes=[self.p1],
        )
        self.bob_smith_1950_psych = Person(
            cfg=self.cfg,
            local_id="7",
            first_name="Bob",
            surnames=["Smith"],
            dob="1950-05-30",
            postcodes=[self.p2],
        )
        self.alice_smith_1930 = Person(
            cfg=self.cfg,
            local_id="8",
            first_name="Alice",
            surnames=["Smith"],
            dob="1930-01-01",
        )
        self.alice_smith_2000 = Person(
            cfg=self.cfg,
            local_id="9",
            first_name="Alice",
            surnames=["Smith"],
            dob="2000-01-01",
        )
        self.alice_smith = Person(
            cfg=self.cfg,
            local_id="10",
            first_name="Alice",
            surnames=["Smith"],
        )
        self.alice_bc_smith = Person(
            cfg=self.cfg,
            local_id="11",
            first_name="Alice",
            middle_names=["Betty", "Caroline"],
            surnames=["Smith"],
        )
        self.alice_bde_smith = Person(
            cfg=self.cfg,
            local_id="12",
            first_name="Alice",
            middle_names=["Betty", "Dorothy", "Elizabeth"],
            surnames=["Smith"],
        )
        self.all_people = [
            self.alice_bcd_rarename_2000_add,
            self.alec_bcd_rarename_2000_add,
            self.bob_bcd_rarename_2000_add,
            self.alice_bc_rarename_2000_add,
            self.alice_b_rarename_2000_add,
            self.alice_jones_2000_add,
            self.bob_smith_1950_psych,
            self.alice_smith_1930,
            self.alice_smith_2000,
            self.alice_smith,
            self.alice_bc_smith,
            self.alice_bde_smith,
        ]
        self.all_people_hashed = [p.hashed() for p in self.all_people]
        self.people_plaintext = People(cfg=self.cfg)
        self.people_plaintext.add_people(self.all_people)
        self.people_hashed = People(cfg=self.cfg)
        self.people_hashed.add_people(self.all_people_hashed)

    # -------------------------------------------------------------------------
    # Basic string transformations
    # -------------------------------------------------------------------------

    def test_standardize_name(self) -> None:
        tests = (
            # name, standardized version
            ("Al Jazeera", "ALJAZEERA"),
            ("Al'Jazeera", "ALJAZEERA"),
            ("Al'Jazeera'", "ALJAZEERA"),
            ("Alice", "ALICE"),
            ("ALJAZEERA", "ALJAZEERA"),
            ("aljazeera", "ALJAZEERA"),
            ("D'Souza", "DSOUZA"),
            ("de Clérambault", "DECLERAMBAULT"),
            ("Mary Ellen", "MARYELLEN"),
            ('"Al Jazeera"', "ALJAZEERA"),
        )
        for item, target in tests:
            self.assertEqual(standardize_name(item), target)

    def test_safe_upper(self) -> None:
        tests = (
            ("Beethoven", "BEETHOVEN"),
            ("Clérambault", "CLÉRAMBAULT"),
            ("Straße", "STRAẞE"),
        )
        for a, b in tests:
            self.assertEqual(safe_upper(a), b)

    def test_remove_redundant_whitespace(self) -> None:
        tests = (
            (" van \t \r \n Beethoven ", "van Beethoven"),
            ("‘John said “hello”.’", "'John said \"hello\".'"),
            ("a–b—c−d-e", "a-b-c-d-e"),
        )
        for a, b in tests:
            self.assertEqual(remove_redundant_whitespace(a), b)

    def test_surname_fragments(self) -> None:
        cfg = self.cfg
        accent_transliterations = cfg.accent_transliterations
        nonspecific_name_components = cfg.nonspecific_name_components
        tests = (
            # In the expected answer, the original name comes first; then
            # alphabetical order. Some examples are silly.
            #
            # France/French:
            (
                "Côte d'Ivoire",
                ["CÔTE D'IVOIRE", "COTE", "COTE D'IVOIRE", "CÔTE", "IVOIRE"],
            ),
            (
                "de Clérambault",
                [
                    "DE CLÉRAMBAULT",
                    "CLERAMBAULT",
                    "CLÉRAMBAULT",
                    "DE CLERAMBAULT",
                ],
            ),
            (
                "de la Billière",
                ["DE LA BILLIÈRE", "BILLIERE", "BILLIÈRE", "DE LA BILLIERE"],
            ),
            ("Façade", ["FAÇADE", "FACADE"]),
            ("Giscard d'Estaing", ["GISCARD D'ESTAING", "ESTAING", "GISCARD"]),
            ("L'Estrange", ["L'ESTRANGE", "ESTRANGE"]),
            ("L’Estrange", ["L'ESTRANGE", "ESTRANGE"]),
            # Germany (and in Beethoven's case, ancestrally Belgium):
            ("Beethoven", ["BEETHOVEN"]),
            ("Müller", ["MÜLLER", "MUELLER", "MULLER"]),
            ("Straße", ["STRAẞE", "STRASSE"]),
            ("van  Beethoven", ["VAN BEETHOVEN", "BEETHOVEN"]),
            # Italy:
            ("Calabrò", ["CALABRÒ", "CALABRO"]),
            ("De Marinis", ["DE MARINIS", "MARINIS"]),
            ("di Bisanzio", ["DI BISANZIO", "BISANZIO"]),
            # Sweden:
            ("Nyström", ["NYSTRÖM", "NYSTROEM", "NYSTROM"]),
            # Hmm. NYSTROEM is a German-style transliteration. Still, OK-ish.
        )
        for surname, target_fragments in tests:
            self.assertEqual(
                surname_alternative_fragments(
                    surname=surname,
                    accent_transliterations=accent_transliterations,
                    nonspecific_name_components=nonspecific_name_components,
                ),
                target_fragments,
            )

    def test_date_regex(self) -> None:
        for b in BAD_DATE_STRINGS:
            self.assertFalse(is_valid_isoformat_date(b))
        for g in GOOD_DATE_STRINGS:
            self.assertTrue(is_valid_isoformat_date(g))

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

    # -------------------------------------------------------------------------
    # Frequencies
    # -------------------------------------------------------------------------

    def test_fuzzy_linkage_frequencies_name(self) -> None:
        cfg = self.cfg
        for surname in ["Smith", "Jones", "Blair", "Cardinal", "XYZ"]:
            f = cfg.get_surname_freq_info(surname)
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
            f = cfg.get_forename_freq_info(forename, gender)
            log.info(
                f"Forename frequency for {forename}, gender {gender}: {f}"
            )

    def test_fuzzy_linkage_frequencies_postcode(self) -> None:
        cfg = self.cfg
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

    # -------------------------------------------------------------------------
    # Identifiers
    # -------------------------------------------------------------------------

    def test_identifier_dob(self) -> None:
        cfg = self.cfg
        for b in BAD_DATE_STRINGS:
            with self.assertRaises(ValueError):
                _ = DateOfBirth(cfg, b)
        for g in GOOD_DATE_STRINGS:
            d = DateOfBirth(cfg, g)
            self.assertEqual(d.dob_str, g)
            self.assertEqual(str(d), g)
            self.assertTrue(d.fully_matches(d))
            self.assertGreater(d.comparison(d).posterior_log_odds(0), 0)
        partial_matches = (
            ("2000-01-01", "2007-01-01"),
            ("2000-01-01", "2000-07-01"),
            ("2000-01-01", "2000-01-07"),
        )
        for d1_str, d2_str in partial_matches:
            d1 = DateOfBirth(cfg, d1_str)
            d2 = DateOfBirth(cfg, d2_str)
            self.assertFalse(d1.fully_matches(d2))
            self.assertFalse(d2.fully_matches(d1))
            self.assertTrue(d1.partially_matches(d2))
            self.assertTrue(d2.partially_matches(d1))
            self.assertGreater(d1.comparison(d2).posterior_log_odds(0), 0)
        not_partial_matches = (
            ("2000-01-01", "2007-07-01"),
            ("2000-01-01", "2000-07-07"),
            ("2000-01-01", "2007-01-07"),
        )
        for d1_str, d2_str in not_partial_matches:
            d1 = DateOfBirth(cfg, d1_str)
            d2 = DateOfBirth(cfg, d2_str)
            self.assertFalse(d1.fully_matches(d2))
            self.assertFalse(d2.fully_matches(d1))
            self.assertFalse(d1.partially_matches(d2))
            self.assertFalse(d2.partially_matches(d1))
            self.assertLess(d1.comparison(d2).posterior_log_odds(0), 0)

    def test_identifier_postcode(self) -> None:
        cfg = self.cfg
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
            self.assertTrue(p.fully_matches(p))
            self.assertGreater(p.comparison(p).posterior_log_odds(0), 0)
        empty = Postcode(cfg, "")
        self.assertEqual(str(empty), "")
        partial_matches = (
            ("CB99 9XY", "CB99 9AB"),
            ("CB9 9XY", "CB9 9ZZ"),
        )
        for p1_str, p2_str in partial_matches:
            p1 = Postcode(cfg, p1_str)
            p2 = Postcode(cfg, p2_str)
            self.assertFalse(p1.fully_matches(p2))
            self.assertFalse(p2.fully_matches(p1))
            self.assertTrue(p1.partially_matches(p2))
            self.assertTrue(p2.partially_matches(p1))
            self.assertGreater(p1.comparison(p2).posterior_log_odds(0), 0)
        not_partial_matches = (
            ("CB99 9XY", "CB99 7AB"),
            ("CB9 9XY", "CB9 7ZZ"),
        )
        for p1_str, p2_str in not_partial_matches:
            p1 = Postcode(cfg, p1_str)
            p2 = Postcode(cfg, p2_str)
            self.assertFalse(p1.fully_matches(p2))
            self.assertFalse(p2.fully_matches(p1))
            self.assertFalse(p1.partially_matches(p2))
            self.assertFalse(p2.partially_matches(p1))
            self.assertLess(p1.comparison(p2).posterior_log_odds(0), 0)

    def test_identifier_gender(self) -> None:
        cfg = self.cfg
        for b in BAD_GENDERS:
            with self.assertRaises(ValueError):
                _ = Gender(cfg, b)
        for g_str in VALID_GENDERS:
            g = Gender(cfg, g_str)
            log.critical(f"g = {g!r}")
            self.assertEqual(g.gender_str, g_str)
            self.assertEqual(str(g), g_str)
            if not g:
                continue
            self.assertTrue(g.fully_matches(g))
            comp = g.comparison(g)
            if comp:
                self.assertGreater(comp.posterior_log_odds(0), 0)

        empty = Gender(cfg, GENDER_MISSING)
        m = Gender(cfg, GENDER_MALE)
        f = Gender(cfg, GENDER_FEMALE)
        x = Gender(cfg, GENDER_OTHER)

        empty.ensure_has_freq_info_if_id_present()
        m.ensure_has_freq_info_if_id_present()
        f.ensure_has_freq_info_if_id_present()
        x.ensure_has_freq_info_if_id_present()

        self.assertEqual(str(empty), "")

        self.assertTrue(bool(m))
        self.assertTrue(bool(f))
        self.assertTrue(bool(x))
        self.assertFalse(bool(empty))

        self.assertTrue(m.fully_matches(m))
        self.assertTrue(m.comparison_relevant(m))

        self.assertTrue(f.comparison_relevant(f))
        self.assertTrue(f.comparison_relevant(f))

        self.assertFalse(m.fully_matches(f))
        self.assertFalse(m.fully_matches(x))
        self.assertFalse(f.fully_matches(m))
        self.assertFalse(f.fully_matches(x))

        f_comp_f = f.comparison(f)
        self.assertIsNotNone(f_comp_f)
        self.assertGreater(f.comparison(f).posterior_log_odds(0), 0)
        self.assertLess(f.comparison(m).posterior_log_odds(0), 0)

    def test_identifier_surname_fragment(self) -> None:
        cfg = self.cfg
        f1 = SurnameFragment(cfg, name="Smith", gender=GENDER_MALE)
        h1 = f1.hashed()
        self.assertTrue(f1.fully_matches(f1))
        self.assertTrue(f1.partially_matches(f1))
        self.assertFalse(f1.fully_matches(h1))
        self.assertFalse(f1.partially_matches(h1))
        self.assertTrue(h1.fully_matches(h1))
        self.assertTrue(h1.partially_matches(h1))

    def test_identifier_surname(self) -> None:
        # https://en.wikipedia.org/wiki/Double-barrelled_name
        cfg = self.cfg
        g = GENDER_FEMALE
        jones = Surname(cfg, name="Jones", gender=g)
        mozart = Surname(cfg, name="Mozart", gender=g)
        mozart_smith_hy = Surname(cfg, name="Mozart-Smith", gender=g)
        mozart_smith_sp = Surname(cfg, name="Mozart Smith", gender=g)
        smith = Surname(cfg, name="Smith", gender=g)
        smythe = Surname(cfg, name="Smythe", gender=g)
        mozart_hashed = mozart.hashed()
        mozart_smith_hashed = mozart_smith_hy.hashed()
        smith_hashed = smith.hashed()
        smythe_hashed = smythe.hashed()
        matching = [
            (jones, jones),
            (mozart_smith_hy, mozart),
            (mozart_smith_hy, mozart_smith_hy),
            (mozart_smith_hy, mozart_smith_sp),
            (mozart_smith_hy, smith),
            (mozart_smith_sp, mozart),
            (mozart_smith_sp, mozart_smith_hy),
            (mozart_smith_sp, smith),
            (smith, smith),
            (smythe, smythe),
            (mozart_hashed, mozart_hashed),
            (mozart_smith_hashed, mozart_smith_hashed),
            (smith_hashed, smith_hashed),
            (smythe_hashed, smythe_hashed),
        ]
        partially_matching = [
            (mozart_smith_hy, smythe),
            (mozart_smith_sp, smythe),
            (smith, smythe),
            (smith_hashed, smythe_hashed),
            (mozart_smith_hashed, smythe_hashed),
        ]
        nonmatching = [
            (jones, mozart_smith_hy),
            (jones, mozart_smith_sp),
            (smith, jones),
            (smith, mozart),
            (smith, smith_hashed),
            (smythe, smythe_hashed),
        ]
        for a, b in matching:
            self.assertTrue(a.fully_matches(b))
        for a, b in partially_matching:
            self.assertFalse(a.fully_matches(b))
            self.assertTrue(a.partially_matches(b))
        for a, b in nonmatching:
            self.assertFalse(a.fully_matches(b))
            self.assertFalse(a.partially_matches(b))

    # -------------------------------------------------------------------------
    # Lots of identifiers
    # -------------------------------------------------------------------------

    def test_identifier_transformations(self) -> None:
        """
        Creating hashed and plaintext JSON representation and loading an
        identifier back from them.
        """
        cfg = self.cfg
        identifiable = [
            Postcode(cfg, postcode="CB2 0QQ"),
            DateOfBirth(cfg, dob="2000-12-31"),
            Gender(cfg, gender=GENDER_MALE),
            Forename(cfg, name="Elizabeth", gender=GENDER_FEMALE),
            SurnameFragment(cfg, name="Smith", gender=GENDER_MALE),
            Surname(cfg, name="Smith", gender=GENDER_FEMALE),
        ]  # type: List[Identifier]
        for i in identifiable:
            self.assertTrue(i.is_plaintext)
            i_class = type(i)  # type: Type[Identifier]

            hd = i.as_dict(encrypt=True, include_frequencies=True)
            h = i_class.from_dict(cfg, hd, hashed=True)
            self.assertFalse(h.is_plaintext)
            h.ensure_has_freq_info_if_id_present()

            pd = i.as_dict(encrypt=False, include_frequencies=True)
            p = i_class.from_dict(cfg, pd, hashed=False)
            self.assertTrue(p.is_plaintext)
            p.ensure_has_freq_info_if_id_present()

    # -------------------------------------------------------------------------
    # Person checks
    # -------------------------------------------------------------------------

    def test_person_equality(self) -> None:
        cfg = self.cfg
        p1 = Person(cfg, local_id="hello")
        p2 = Person(cfg, local_id="world")
        p3 = Person(cfg, local_id="world")
        self.assertNotEqual(p1, p2)
        self.assertEqual(p2, p3)

        people = People(cfg)
        people.add_person(p1)
        people.add_person(p2)
        self.assertRaises(DuplicateIDError, people.add_person, p3)

    def test_person_copy(self) -> None:
        persons = [self.alice_smith]
        for orig in persons:
            cp = orig.copy()
            for attr in Person.ALL_PERSON_KEYS:
                orig_value = getattr(orig, attr)
                copy_value = getattr(cp, attr)
                self.assertEqual(
                    orig_value,
                    copy_value,
                    f"mismatch for {attr}:\n"
                    f"{orig_value!r}\n!=\n{copy_value!r}",
                )

    # -------------------------------------------------------------------------
    # Person comparisons
    # -------------------------------------------------------------------------

    def test_fuzzy_linkage_matches(self) -> None:
        test_values = [
            # Very easy match
            TestCondition(
                cfg=self.cfg,
                person_a=self.alice_bcd_rarename_2000_add,
                person_b=self.alice_bcd_rarename_2000_add,
                should_match=True,
            ),
            # Easy match
            TestCondition(
                cfg=self.cfg,
                person_a=self.alice_bc_rarename_2000_add,
                person_b=self.alice_b_rarename_2000_add,
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
                person_a=self.alice_bcd_rarename_2000_add,
                person_b=self.alec_bcd_rarename_2000_add,
                should_match=True,
            ),
            TestCondition(
                cfg=self.cfg,
                person_a=self.alice_bcd_rarename_2000_add,
                person_b=self.bob_bcd_rarename_2000_add,
                should_match=True,  # used to be False
            ),
        ]  # type: List[TestCondition]
        log.info("Testing comparisons...")
        for i, test in enumerate(test_values, start=1):
            log.info(f"Comparison {i}...")
            test.check_comparison_as_expected()

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
            f"{self.alice_bc_smith}\n"
            f"{self.alice_bde_smith}"
        )
        # noinspection PyProtectedMember
        for comp in self.alice_bc_smith._comparisons_middle_names(
            self.alice_bde_smith
        ):
            log.info(comp)
