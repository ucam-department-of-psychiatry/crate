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
            "denylist": {
                "words": [name, address],
            },
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

    def test_denylist_replacement_text(self) -> None:
        word = "secret"

        payload = {
            "denylist": {
                "words": [word],
            },
            "replace_nonspecific_info_with": "[REDACTED]",
            "text": word,
        }

        response = self.client.post("/scrub/", payload, format="json")
        self.assertEqual(response.status_code, 200, msg=response.data)

        anonymised = response.data["anonymised"]

        self.assertEqual(anonymised.count("[REDACTED]"), 1)

    def test_expected_fields_returned(self) -> None:
        text = self.fake.text()

        payload = {
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

    def test_patient_code_replaced(self) -> None:
        postcode = self.fake.postcode()
        text = f"{postcode} {self.fake.text()}"

        payload = {
            "patient": {
                "codes": [postcode],
            },
            "text": text,
        }

        self.assertIn(postcode, text)

        response = self.client.post("/scrub/", payload, format="json")
        self.assertEqual(response.status_code, 200, msg=response.data)

        anonymised = response.data["anonymised"]

        self.assertNotIn(postcode, anonymised)

        self.assertEqual(anonymised.count("[PPP]"), 1)

    def test_third_party_code_replaced(self) -> None:
        postcode = self.fake.postcode()
        text = f"{postcode} {self.fake.text()}"

        payload = {
            "third_party": {
                "codes": [postcode],
            },
            "text": text,
        }

        self.assertIn(postcode, text)

        response = self.client.post("/scrub/", payload, format="json")
        self.assertEqual(response.status_code, 200, msg=response.data)

        anonymised = response.data["anonymised"]

        self.assertNotIn(postcode, anonymised)

        self.assertEqual(anonymised.count("[TTT]"), 1)

    def test_anonymise_codes_ignoring_word_boundaries(self) -> None:
        postcode = self.fake.postcode()
        text = f"text{postcode}text"

        payload = {
            "anonymise_codes_at_word_boundaries_only": False,
            "third_party": {
                "codes": [postcode],
            },
            "text": text,
        }

        self.assertIn(postcode, text)

        response = self.client.post("/scrub/", payload, format="json")
        self.assertEqual(response.status_code, 200, msg=response.data)

        anonymised = response.data["anonymised"]

        self.assertNotIn(postcode, anonymised)

        self.assertEqual(anonymised.count("[TTT]"), 1)

    def test_anonymise_dates_ignoring_word_boundaries(self) -> None:
        date_of_birth = self.fake.date_of_birth().strftime("%d %b %Y")
        text = (f"text{date_of_birth}text")

        payload = {
            "anonymise_dates_at_word_boundaries_only": False,
            "third_party": {
                "dates": [date_of_birth],
            },
            "text": text,
        }

        self.assertIn(date_of_birth, text)

        response = self.client.post("/scrub/", payload, format="json")
        self.assertEqual(response.status_code, 200, msg=response.data)

        anonymised = response.data["anonymised"]

        self.assertNotIn(date_of_birth, anonymised)

        self.assertEqual(anonymised.count("[TTT]"), 1)

    def test_anonymise_numbers_ignoring_word_boundaries(self) -> None:
        phone = self.fake.phone_number()
        text = (f"text{phone}text")

        payload = {
            "anonymise_numbers_at_numeric_boundaries_only": False,
            "anonymise_numbers_at_word_boundaries_only": False,
            "third_party": {
                "numbers": [phone],
            },
            "text": text,
        }

        self.assertIn(phone, text)

        response = self.client.post("/scrub/", payload, format="json")
        self.assertEqual(response.status_code, 200, msg=response.data)

        anonymised = response.data["anonymised"]

        self.assertNotIn(phone, anonymised)
        self.assertEqual(anonymised.count("[TTT]"), 1)

    def test_anonymise_numbers_ignoring_numeric_boundaries(self) -> None:
        phone = self.fake.phone_number()
        text = (f"1234{phone}5678")

        payload = {
            "anonymise_numbers_at_numeric_boundaries_only": False,
            "anonymise_numbers_at_word_boundaries_only": False,
            "third_party": {
                "numbers": [phone],
            },
            "text": text,
        }

        self.assertIn(phone, text)

        response = self.client.post("/scrub/", payload, format="json")
        self.assertEqual(response.status_code, 200, msg=response.data)

        anonymised = response.data["anonymised"]

        self.assertNotIn(phone, anonymised)
        self.assertEqual(anonymised.count("[TTT]"), 1)

    def test_anonymise_strings_ignoring_word_boundaries(self) -> None:
        word = "secret"
        text = f"text{word}text"

        payload = {
            "anonymise_strings_at_word_boundaries_only": False,
            "third_party": {
                "words": [word],
            },
            "text": text,
        }

        self.assertIn(word, text)

        response = self.client.post("/scrub/", payload, format="json")
        self.assertEqual(response.status_code, 200, msg=response.data)

        anonymised = response.data["anonymised"]

        self.assertNotIn(word, anonymised)
        self.assertEqual(anonymised.count("[TTT]"), 1)

    def test_string_max_regex_errors(self) -> None:
        word = "secret"
        typo = "sceret"
        text = f"{typo}"

        payload = {
            "string_max_regex_errors": 2,  # delete 1, insert 1
            "third_party": {
                "words": [word],
            },
            "text": text,
        }

        response = self.client.post("/scrub/", payload, format="json")
        self.assertEqual(response.status_code, 200, msg=response.data)

        anonymised = response.data["anonymised"]

        self.assertNotIn(typo, anonymised)
        self.assertEqual(anonymised.count("[TTT]"), 1)

    def test_min_string_length_for_errors(self) -> None:
        word1 = "secret"
        typo1 = "sceret"

        word2 = "private"
        typo2 = "prviate"
        text = f"{typo1} {typo2}"

        payload = {
            "string_max_regex_errors": 2,  # delete 1, insert 1
            "min_string_length_for_errors": 7,
            "third_party": {
                "words": [word1, word2],
            },
            "text": text,
        }

        response = self.client.post("/scrub/", payload, format="json")
        self.assertEqual(response.status_code, 200, msg=response.data)

        anonymised = response.data["anonymised"]

        self.assertIn(typo1, anonymised)
        self.assertNotIn(typo2, anonymised)
        self.assertEqual(anonymised.count("[TTT]"), 1)

    def test_min_string_length_to_scrub_with(self) -> None:
        payload = {
            "min_string_length_to_scrub_with": 6,
            "third_party": {
                "words": ["Craig Buchanan"],
            },
            "text": "Craig Buchanan",
        }

        response = self.client.post("/scrub/", payload, format="json")
        self.assertEqual(response.status_code, 200, msg=response.data)

        anonymised = response.data["anonymised"]

        self.assertIn("Craig", anonymised)
        self.assertNotIn("Buchanan", anonymised)
        self.assertEqual(anonymised.count("[TTT]"), 1)

    def test_scrub_string_suffixes(self) -> None:
        word = "secret"

        payload = {
            "scrub_string_suffixes": ["s"],
            "third_party": {
                "words": [word],
            },
            "text": "secrets",
        }

        response = self.client.post("/scrub/", payload, format="json")
        self.assertEqual(response.status_code, 200, msg=response.data)

        anonymised = response.data["anonymised"]

        self.assertNotIn("secrets", anonymised)
        self.assertEqual(anonymised.count("[TTT]"), 1)

    def test_allowlist_words(self) -> None:
        # A bit of a contrived example but the allowlist should
        # take precedence.
        payload = {
            "third_party": {
                "words": ["secret", "private", "confidential"],
            },
            "allowlist": {
                "words": ["secret"]
            },
            "text": "secret private confidential",
        }

        response = self.client.post("/scrub/", payload, format="json")
        self.assertEqual(response.status_code, 200, msg=response.data)

        anonymised = response.data["anonymised"]

        self.assertIn("secret", anonymised)
        self.assertNotIn("private", anonymised)
        self.assertNotIn("confidential", anonymised)
        self.assertEqual(anonymised.count("[TTT]"), 2)

    def test_phrase_alternatives(self) -> None:
        payload = {
            "third_party": {
                "phrases": ["22 Acacia Avenue"],
            },
            "alternatives": [
                ["Avenue", "Ave"]
            ],
            "text": "22 Acacia Ave",
        }

        response = self.client.post("/scrub/", payload, format="json")
        self.assertEqual(response.status_code, 200, msg=response.data)

        anonymised = response.data["anonymised"]

        self.assertNotIn("22 Acacia Ave", anonymised)
        self.assertEqual(anonymised.count("[TTT]"), 1)

    def test_scrub_all_numbers_of_n_digits(self) -> None:
        nhs_number = str(generate_random_nhs_number())

        text = f"{self.fake.text()} {nhs_number} {self.fake.text()}"

        self.assertIn(nhs_number, text)

        payload = {
            "scrub_all_numbers_of_n_digits": [10],
            "text": text,
        }

        response = self.client.post("/scrub/", payload, format="json")
        self.assertEqual(response.status_code, 200, msg=response.data)

        anonymised = response.data["anonymised"]

        self.assertNotIn(nhs_number, anonymised)
        self.assertEqual(anonymised.count("[---]"), 1)

    def test_scrub_all_uk_postcodes(self) -> None:
        postcode = self.fake.postcode()

        text = f"{self.fake.text()} {postcode} {self.fake.text()}"

        self.assertIn(postcode, text)

        payload = {
            "scrub_all_uk_postcodes": True,
            "text": text,
        }

        response = self.client.post("/scrub/", payload, format="json")
        self.assertEqual(response.status_code, 200, msg=response.data)

        anonymised = response.data["anonymised"]

        self.assertNotIn(postcode, anonymised)
        self.assertEqual(anonymised.count("[---]"), 1)
