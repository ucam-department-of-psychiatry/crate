r"""
crate_anon/linkage/tests/person_tests.py

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

**Fuzzy matching tests for person representations.**

"""

from crate_anon.linkage.helpers import standardize_name, standardize_postcode
from crate_anon.linkage.matchconfig import mk_dummy_match_config
from crate_anon.linkage.person import Person
from crate_anon.testing.classes import CrateTestCase


class PersonTests(CrateTestCase):
    def test_person_created_from_plaintext_csv(self) -> None:
        local_id = "12345"
        gender = self.fake.sex()
        forename_1 = self.fake.forename(gender)
        forename_2 = self.fake.forename(gender)
        surname_1 = self.fake.last_name()
        surname_2 = self.fake.last_name()
        dob = self.fake.consistent_date_of_birth().strftime("%Y-%m-%d")
        postcode = self.fake.postcode()
        nhs_number = str(self.fake.nhs_number())

        rowdict = {
            "local_id": local_id,
            "forenames": f"{forename_1}; {forename_2}",
            "surnames": f"{surname_1}; {surname_2}",
            "dob": dob,
            "gender": gender,
            "postcodes": f"{postcode}",
            "perfect_id": f"nhsnum:{nhs_number}",
            "other_info": "",
        }

        config = mk_dummy_match_config()

        person = Person.from_plaintext_csv(config, rowdict)
        standardized_forenames = [f.name for f in person.forenames]
        raw_surnames = [s.raw_surname for s in person.surnames]

        self.assertEqual(person.local_id, local_id)
        self.assertIn(standardize_name(forename_1), standardized_forenames)
        self.assertIn(standardize_name(forename_2), standardized_forenames)
        self.assertIn(surname_1, raw_surnames)
        self.assertIn(surname_2, raw_surnames)
        self.assertEqual(person.dob.dob_str, dob)
        self.assertEqual(person.gender.gender_str, gender)
        self.assertEqual(
            person.postcodes[0].postcode_unit, standardize_postcode(postcode)
        )
        self.assertEqual(person.perfect_id.identifiers, {"nhsnum": nhs_number})
