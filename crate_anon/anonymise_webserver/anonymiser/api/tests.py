"""
crate_anon/anonymise_webserver/anonymiser/api/tests.py

===============================================================================

    Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).

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

End-to-end API tests

"""

from django.test import TestCase

from cardinal_pythonlib.nhs import generate_random_nhs_number
from faker import Faker
from rest_framework.test import APIClient


class AnonymisationTests(TestCase):
    def setUp(self) -> None:
        super().setUp()

        self.fake = Faker()
        self.fake.seed_instance(1234)

    def test_specified_fields_replaced(self) -> None:
        client = APIClient()

        name = self.fake.name()
        address = self.fake.address()
        nhs_number = generate_random_nhs_number()

        text = (f"{name} {self.fake.text()} {address} {self.fake.text()} "
                f"{nhs_number} {self.fake.text()}")

        payload = {
            "scrub": [name, address],
            "text": text,
        }

        self.assertIn(name, text)
        self.assertIn(address, text)
        self.assertIn(str(nhs_number), text)

        response = client.post("/scrub/", payload, format="json")

        self.assertEqual(response.status_code, 200)

        anonymised = response.data["anonymised"]

        self.assertNotIn(name, anonymised)
        self.assertNotIn(address, anonymised)
        self.assertIn(str(nhs_number), anonymised)

        self.assertEqual(anonymised.count("[---]"), 2)

    def test_expected_fields_returned(self) -> None:
        client = APIClient()

        text = self.fake.text()

        payload = {
            "scrub": [],
            "text": text,
        }

        response = client.post("/scrub/", payload, format="json")
        self.assertEqual(response.status_code, 200)

        self.assertIn("anonymised", response.data)
        self.assertNotIn("scrub", response.data)
        self.assertNotIn("text", response.data)
