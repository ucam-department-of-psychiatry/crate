#!/usr/bin/env python

r"""
crate_anon/linkage/people.py

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

**People representations for fuzzy matching.**

"""


# =============================================================================
# Imports
# =============================================================================

from collections import defaultdict
import logging
from typing import (
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    Set,
)

from ordered_set import OrderedSet

from crate_anon.linkage.constants import INFINITY, MINUS_INFINITY
from crate_anon.linkage.matchconfig import MatchConfig
from crate_anon.linkage.matchresult import MatchResult
from crate_anon.linkage.person import Person

log = logging.getLogger(__name__)


# =============================================================================
# Exceptions
# =============================================================================


class DuplicateIDError(Exception):
    pass


# =============================================================================
# People: a collection of Person objects
# =============================================================================
# Try staring at the word "people" for a while and watch it look odd...


class People:
    """
    Represents a group of people, and implements a shortlist.
    """

    def __init__(
        self,
        cfg: MatchConfig,
        person: Person = None,
        people: Iterable[Person] = None,
    ) -> None:
        """
        Creates a blank collection.

        Raises :exc:`crate_anon.linkage.fuzzy_id_match.DuplicateLocalIDError`
        if some people have duplicate ``local_id`` values.
        """
        self.cfg = cfg
        self.people = []  # type: List[Person]
        # ... list is preferable to set, as we may slice it for parallel
        # processing, and it maintains order.

        # These may be plaintext or hashed DOB strings depending on our people:
        self.dob_md_to_people = defaultdict(
            list
        )  # type: Dict[str, List[Person]]
        self.dob_yd_to_people = defaultdict(
            list
        )  # type: Dict[str, List[Person]]
        self.dob_ym_to_people = defaultdict(
            list
        )  # type: Dict[str, List[Person]]
        self.dob_ymd_to_people = defaultdict(
            list
        )  # type: Dict[str, List[Person]]

        self.perfect_id_map = defaultdict(
            dict
        )  # type: Dict[str, Dict[str, Person]]

        self._known_local_ids = set()  # type: Set[str]
        self._people_are_plaintext = None  # type: Optional[bool]

        if person:
            self.add_person(person)
        if people:
            self.add_people(people)

    def add_person(self, person: Person) -> None:
        """
        Adds a single person.

        Raises :exc:`crate_anon.linkage.fuzzy_id_match.DuplicateLocalIDError`
        if the person has a ``local_id`` value already in our collection.
        """
        # Plaintext or hashed?
        if self.people:
            # Not the first person.
            if person.is_plaintext() != self._people_are_plaintext:
                new = Person.plain_or_hashed_txt(person.is_plaintext())
                old = Person.plain_or_hashed_txt(self._people_are_plaintext)
                raise ValueError(
                    f"Trying to add a {new} person but all existing people "
                    f"are {old}"
                )
        else:
            # First person.
            self._people_are_plaintext = person.is_plaintext()

        # Check local ID not duplicated.
        if person.local_id in self._known_local_ids:
            raise DuplicateIDError(
                f"Person with duplicate local ID {person.local_id!r}"
            )
        self._known_local_ids.add(person.local_id)

        # Build perfect ID map and ensure no duplication.
        for key, value in person.perfect_id.identifiers.items():
            # e.g. key = "nhsnum", value = some NHS number as a string, or a
            # hashed equivalent.
            id_to_person = self.perfect_id_map[key]  # e.g. for NHS#
            if value in id_to_person:
                raise DuplicateIDError(
                    f"Person with duplicate perfect ID {key} = {value!r}"
                )
            id_to_person[value] = person

        # Add to DOB maps.
        dob = person.dob
        if dob:
            self.dob_md_to_people[dob.dob_md].append(person)
            self.dob_yd_to_people[dob.dob_yd].append(person)
            self.dob_ym_to_people[dob.dob_ym].append(person)
            self.dob_ymd_to_people[dob.dob_str].append(person)
        else:
            # DOB absent.
            # We do need a way to retrieve people with no DOB.
            # We use a blank string key for this:
            self.dob_ymd_to_people[""].append(person)
            # It's also true that dob.dob_str will be "", so this is just for
            # clarity.
            # We do not need to add to the partial DOB maps. See
            # gen_shortlist().

        # Add the person.
        self.people.append(person)

    def add_people(self, people: Iterable[Person]) -> None:
        """
        Adds multiple people.

        Raises :exc:`crate_anon.linkage.fuzzy_id_match.DuplicateLocalIDError`
        if some people have duplicate ``local_id`` values with respect to those
        we already know.
        """
        for person in people:
            self.add_person(person)

    def size(self) -> int:
        """
        Returns the number of people in this object.
        """
        return len(self.people)

    def ensure_valid_as_probands(self) -> None:
        """
        Ensures all people have sufficient information to act as a proband,
        or raises :exc:`ValueError`.
        """
        log.info("Validating probands...")
        for p in self.people:
            p.ensure_valid_as_proband()
        log.debug("... OK")

    def ensure_valid_as_sample(self) -> None:
        """
        Ensures all people have sufficient information to act as a candidate
        from a sample, or raises :exc:`ValueError`.
        """
        log.info("Validating sample...")
        for p in self.people:
            p.ensure_valid_as_candidate()
        log.debug("... OK")

    def get_perfect_match(self, proband: Person) -> Optional[Person]:
        """
        Returns the first person who matches on a perfect (person-unique) ID,
        or ``None``.
        """
        for key, value in proband.perfect_id.identifiers.items():
            key = self.cfg.remap_perfect_id_key(key)
            winner = self.perfect_id_map[key].get(value)
            if winner:
                return winner
        return None

    def gen_shortlist(self, proband: Person) -> Generator[Person, None, None]:
        """
        Generates a shortlist of potential candidates for fuzzy matching (e.g.
        by restriction to same/similar dates of birth -- or with no such
        restriction, if preferred).

        Yields:
            proband: a :class:`Person`
        """
        # A high-speed function.
        cfg = self.cfg
        dob = proband.dob

        # 2023-02-28 update for referees:
        # - Allow comparison where the DOB is missing.
        # - Of necessity, probands with no DOBs must be compared to all
        #   candidates.
        # - Likewise, if we permit a complete DOB mismatch (where DOBs are
        #   present), we must compare to all candidates.
        if cfg.complete_dob_mismatch_allowed or not dob:
            # No shortlisting; everyone's a candidate. Slow.
            for person in self.people:
                # self.people is a list, so order is consistent and matches
                # the input.
                yield person
        else:
            # Implement the shortlist by DOB.
            # Most efficient to let set operations determine uniqueness, then
            # iterate through the set.
            # We use an OrderedSet to be sure of consistency; the precise
            # ordering is as below (e.g. people with the same DOB, then those
            # with the partial matches as shown below). Within each category,
            # the ordering will be as the input. (Thus, if configured for
            # duplicate detection, which entails identical DOBs, the earliest
            # winner will always be the first in the input.)

            # First, exact matches:
            shortlist = OrderedSet(self.dob_ymd_to_people[dob.dob_str])

            # Now, we'll slow it all down with partial matches:
            if cfg.partial_dob_mismatch_allowed:
                shortlist.update(self.dob_md_to_people[dob.dob_md])
                shortlist.update(self.dob_yd_to_people[dob.dob_yd])
                shortlist.update(self.dob_ym_to_people[dob.dob_ym])

            # But also, we must include any candidates who have no DOB.
            # (We already know that our proband has a DOB, or we wouldn't be
            # in this part of the if statement.)
            shortlist.update(self.dob_ymd_to_people[""])

            for person in shortlist:
                yield person

    def get_unique_match_detailed(self, proband: Person) -> MatchResult:
        """
        Returns a single person matching the proband, or ``None`` if there is
        no match (as defined by the probability settings in ``cfg``).

        Args:
            proband: a :class:`Person`
        """

        # 2020-04-25: Do this in one pass.
        # A bit like
        # https://www.geeksforgeeks.org/python-program-to-find-second-largest-number-in-a-list/  # noqa
        # ... but modified, as that fails to deal with joint winners
        # ... and it's not a super algorithm anyway.

        # Step 1. Scan everything in a single pass, establishing the best
        # candidate and the runner-up.
        cfg = self.cfg
        best_log_odds = MINUS_INFINITY
        second_best_log_odds = MINUS_INFINITY

        second_best_candidate = None  # type: Optional[Person]
        best_candidate = self.get_perfect_match(proband)
        if best_candidate:
            best_log_odds = INFINITY
        else:
            # Fuzzy matching
            proband_log_odds_same = proband.log_odds_same  # for speed
            for candidate in self.gen_shortlist(proband):
                log_odds = proband_log_odds_same(candidate)
                if log_odds > best_log_odds:
                    second_best_log_odds = best_log_odds
                    second_best_candidate = best_candidate
                    best_log_odds = log_odds
                    best_candidate = candidate
                elif log_odds > second_best_log_odds:
                    second_best_log_odds = log_odds
                    second_best_candidate = candidate
                # If log_odds == best_log_odds, we don't change the winner,
                # i.e. the first-encountered candidate continues in the lead.
                # The shortlist is generated in a consistent order.

        result = MatchResult(
            best_log_odds=best_log_odds,
            second_best_log_odds=second_best_log_odds,
            best_candidate=best_candidate,
            second_best_candidate=second_best_candidate,
            proband=proband,
        )

        # Is there a winner?
        if (
            best_candidate
            and best_log_odds >= cfg.min_log_odds_for_match
            and best_log_odds
            >= (second_best_log_odds + cfg.exceeds_next_best_log_odds)
        ):
            # (a) There needs to be a best candidate.
            # (b) The best needs to be good enough.
            # (c) The best must beat the runner-up by a sufficient margin.
            result.winner = best_candidate

        return result

    def get_unique_match(self, proband: Person) -> Optional[Person]:
        """
        Returns a single person matching the proband, or ``None`` if there is
        no match (as defined by the probability settings in ``cfg``).

        Args:
            proband: a :class:`Person`

        Returns:
            the winner (a :class:`Person`) or ``None``
        """
        result = self.get_unique_match_detailed(proband)
        return result.winner

    def hashed(self) -> "People":
        """
        Returns a hashed version of itself.
        """
        return People(cfg=self.cfg, people=[p.hashed() for p in self.people])

    def copy(self) -> "People":
        """
        Returns a copy of itself.
        """
        return People(cfg=self.cfg, people=[p.copy() for p in self.people])
