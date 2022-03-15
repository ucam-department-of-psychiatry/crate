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

        self.client = APIClient()

        self.fake = Faker(["en-GB"])
        self.fake.seed_instance(1234)

    def test_denylist_replaced(self) -> None:
        name = self.fake.name()
        address = self.fake.address()
        nhs_number = generate_random_nhs_number()

        text = (f"{name} {self.fake.text()} {address} {self.fake.text()} "
                f"{nhs_number} {self.fake.text()}")

        payload = {
            "denylist": [name, address],
            "text": text,
        }

        self.assertIn(name, text)
        self.assertIn(address, text)
        self.assertIn(str(nhs_number), text)

        response = self.client.post("/scrub/", payload, format="json")
        self.assertEqual(response.status_code, 200, msg=response.data)

        anonymised = response.data["anonymised"]

        self.assertNotIn(name, anonymised)
        self.assertNotIn(address, anonymised)
        self.assertIn(str(nhs_number), anonymised)

        self.assertEqual(anonymised.count("[---]"), 2)

    def test_expected_fields_returned(self) -> None:
        text = self.fake.text()

        payload = {
            "denylist": [],
            "text": text,
        }

        response = self.client.post("/scrub/", payload, format="json")
        self.assertEqual(response.status_code, 200, msg=response.data)

        self.assertIn("anonymised", response.data.keys())
        self.assertEqual(len(response.data), 1)

    def test_patient_date_replaced(self) -> None:
        date_of_birth = self.fake.date_of_birth().strftime("%d %b %Y")
        text = (f"{date_of_birth} {self.fake.text()}")

        payload = {
            "patient": {
                "dates": [date_of_birth],
            },
            "text": text,
        }

        self.assertIn(date_of_birth, text)

        response = self.client.post("/scrub/", payload, format="json")
        self.assertEqual(response.status_code, 200, msg=response.data)

        anonymised = response.data["anonymised"]

        self.assertNotIn(date_of_birth, anonymised)

        self.assertEqual(anonymised.count("[PPP]"), 1)

    def test_patient_words_replaced(self) -> None:
        words = "one two three"

        text = f"one {self.fake.text()} two {self.fake.text()} three"
        payload = {
            "patient": {
                "words": [words],
            },
            "text": text,
        }

        all_words = text.split()

        self.assertIn("one", all_words)
        self.assertIn("two", all_words)
        self.assertIn("three", all_words)

        response = self.client.post("/scrub/", payload, format="json")
        self.assertEqual(response.status_code, 200, msg=response.data)

        anonymised = response.data["anonymised"]
        anonymised_words = anonymised.split()

        self.assertNotIn("one", anonymised_words)
        self.assertNotIn("two", anonymised_words)
        self.assertNotIn("three", anonymised_words)

        self.assertEqual(anonymised.count("[PPP]"), 3)

    def test_patient_phrase_replaced(self) -> None:
        address = self.fake.address()

        text = f"{address} {self.fake.text()}"

        payload = {
            "patient": {
                "phrases": [address],
            },
            "text": text,
        }

        self.assertIn(address, text)

        response = self.client.post("/scrub/", payload, format="json")
        self.assertEqual(response.status_code, 200, msg=response.data)

        anonymised = response.data["anonymised"]

        self.assertNotIn(address, anonymised)

        self.assertEqual(anonymised.count("[PPP]"), 1)

    def test_patient_numeric_replaced(self) -> None:
        phone = self.fake.phone_number()

        text = f"{phone} {self.fake.text()}"

        payload = {
            "patient": {
                "numbers": [phone],
            },
            "text": text,
        }

        self.assertIn(phone, text)

        response = self.client.post("/scrub/", payload, format="json")
        self.assertEqual(response.status_code, 200, msg=response.data)

        anonymised = response.data["anonymised"]

        self.assertNotIn(phone, anonymised)

        self.assertEqual(anonymised.count("[PPP]"), 1)
