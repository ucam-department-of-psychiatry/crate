"""
crate_anon/crateweb/anonymise_api/tests.py

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

End-to-end API tests. Not an exhaustive test of anonymisation.

"""

import secrets
from tempfile import NamedTemporaryFile
from typing import Dict

from cardinal_pythonlib.httpconst import HttpStatus
from cardinal_pythonlib.nhs import generate_random_nhs_number
from django.test import override_settings, TestCase
from faker import Faker
from rest_framework.response import Response
from rest_framework.test import APIClient

from crate_anon.anonymise.constants import AnonymiseConfigKeys as ConfigKeys
from crate_anon.crateweb.anonymise_api.constants import (
    ApiKeys,
    ApiSettingsKeys,
)

DEFAULT_SETTINGS = {ApiSettingsKeys.HASH_KEY: secrets.token_urlsafe(16)}


@override_settings(ANONYMISE_API=DEFAULT_SETTINGS)
class AnonymisationTests(TestCase):
    def setUp(self) -> None:
        super().setUp()

        self.client = APIClient()

        self.fake = Faker(["en-GB"])
        self.fake.seed_instance(1234)

    def scrub_post(self, payload: Dict) -> Response:
        return self.client.post("/anon_api/scrub/", payload, format="json")

    def test_denylist_replaced(self) -> None:
        name = self.fake.name()
        address = self.fake.address()
        nhs_number = generate_random_nhs_number()

        text = (
            f"{name} {self.fake.text()} {address} {self.fake.text()} "
            f"{nhs_number} {self.fake.text()}"
        )

        payload = {
            ApiKeys.DENYLIST: {
                ApiKeys.WORDS: [name, address],
            },
            ApiKeys.TEXT: {"test": text},
        }

        self.assertIn(name, text)
        self.assertIn(address, text)
        self.assertIn(str(nhs_number), text)

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertNotIn(name, anonymised)
        self.assertNotIn(address, anonymised)
        self.assertIn(str(nhs_number), anonymised)

        self.assertEqual(anonymised.count("[~~~]"), 2)

    def test_denylist_files(self) -> None:
        payload = {
            ApiKeys.DENYLIST: {ApiKeys.FILES: ["test"]},
            ApiKeys.TEXT: {"test": "secret private confidential"},
        }

        with NamedTemporaryFile(delete=False, mode="w") as f:
            filename = f.name
            f.write("secret\n")
            f.write("private\n")
            f.write("confidential\n")

        filename_map = {"test": filename}
        settings = DEFAULT_SETTINGS.copy()
        settings[ApiSettingsKeys.DENYLIST_FILENAMES] = filename_map

        with override_settings(ANONYMISE_API=settings):
            response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertNotIn("secret", anonymised)
        self.assertNotIn("private", anonymised)
        self.assertNotIn("confidential", anonymised)
        self.assertEqual(anonymised.count("[~~~]"), 3)

    def test_denylist_replacement_text(self) -> None:
        word = "secret"

        payload = {
            ApiKeys.DENYLIST: {
                ApiKeys.WORDS: [word],
            },
            ConfigKeys.REPLACE_NONSPECIFIC_INFO_WITH: "[REDACTED]",
            ApiKeys.TEXT: {"test": word},
        }

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertEqual(anonymised.count("[REDACTED]"), 1)

    def test_patient_date_replaced(self) -> None:
        date_of_birth = self.fake.date_of_birth().strftime("%d %b %Y")
        text = f"{date_of_birth} {self.fake.text()}"

        payload = {
            ApiKeys.PATIENT: {
                ApiKeys.DATES: [date_of_birth],
            },
            ApiKeys.TEXT: {"test": text},
        }

        self.assertIn(date_of_birth, text)

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertNotIn(date_of_birth, anonymised)

        self.assertEqual(anonymised.count("[__PPP__]"), 1)

    def test_patient_words_replaced(self) -> None:
        words = "one two three"

        text = f"one {self.fake.text()} two {self.fake.text()} three"
        payload = {
            ApiKeys.PATIENT: {
                ApiKeys.WORDS: [words],
            },
            ApiKeys.TEXT: {"test": text},
        }

        all_words = text.split()

        self.assertIn("one", all_words)
        self.assertIn("two", all_words)
        self.assertIn("three", all_words)

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]
        anonymised_words = anonymised.split()

        self.assertNotIn("one", anonymised_words)
        self.assertNotIn("two", anonymised_words)
        self.assertNotIn("three", anonymised_words)

        self.assertEqual(anonymised.count("[__PPP__]"), 3)

    def test_patient_replacement_text(self) -> None:
        word = "secret"
        payload = {
            ApiKeys.PATIENT: {
                ApiKeys.WORDS: [word],
            },
            ConfigKeys.REPLACE_PATIENT_INFO_WITH: "[REDACTED]",
            ApiKeys.TEXT: {"test": word},
        }

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]
        self.assertEqual(anonymised.count("[REDACTED]"), 1)

    def test_patient_phrase_replaced(self) -> None:
        address = self.fake.address()

        text = f"{address} {self.fake.text()}"

        payload = {
            ApiKeys.PATIENT: {
                ApiKeys.PHRASES: [address],
            },
            ApiKeys.TEXT: {"test": text},
        }

        self.assertIn(address, text)

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertNotIn(address, anonymised)

        self.assertEqual(anonymised.count("[__PPP__]"), 1)

    def test_patient_non_numeric_phrases_replaced(self) -> None:
        non_numeric_phrase = "5 High Street"
        numeric_phrase = "5"

        payload = {
            ApiKeys.PATIENT: {
                ApiKeys.NON_NUMERIC_PHRASES: [
                    non_numeric_phrase,
                    numeric_phrase,
                ],
            },
            ApiKeys.TEXT: {
                "test": "Address is 5 High Street haloperidol 5 mg"
            },
        }

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertEqual(anonymised, "Address is [__PPP__] haloperidol 5 mg")

    def test_patient_numeric_replaced(self) -> None:
        phone = self.fake.phone_number()

        text = f"{phone} {self.fake.text()}"

        payload = {
            ApiKeys.PATIENT: {
                ApiKeys.NUMBERS: [phone],
            },
            ApiKeys.TEXT: {"test": text},
        }

        self.assertIn(phone, text)

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertNotIn(phone, anonymised)

        self.assertEqual(anonymised.count("[__PPP__]"), 1)

    def test_patient_code_replaced(self) -> None:
        postcode = self.fake.postcode()
        text = f"{postcode} {self.fake.text()}"

        payload = {
            ApiKeys.PATIENT: {
                ApiKeys.CODES: [postcode],
            },
            ApiKeys.TEXT: {"test": text},
        }

        self.assertIn(postcode, text)

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertNotIn(postcode, anonymised)

        self.assertEqual(anonymised.count("[__PPP__]"), 1)

    def test_third_party_code_replaced(self) -> None:
        postcode = self.fake.postcode()
        text = f"{postcode} {self.fake.text()}"

        payload = {
            ApiKeys.THIRD_PARTY: {
                ApiKeys.CODES: [postcode],
            },
            ApiKeys.TEXT: {"test": text},
        }

        self.assertIn(postcode, text)

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertNotIn(postcode, anonymised)

        self.assertEqual(anonymised.count("[__TTT__]"), 1)

    def test_third_party_replacement_text(self) -> None:
        postcode = self.fake.postcode()

        payload = {
            ApiKeys.THIRD_PARTY: {
                ApiKeys.CODES: [postcode],
            },
            ApiKeys.TEXT: {"test": postcode},
            ConfigKeys.REPLACE_THIRD_PARTY_INFO_WITH: "[REDACTED]",
        }

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertNotIn(postcode, anonymised)

        self.assertEqual(anonymised.count("[REDACTED]"), 1)

    def test_anonymise_codes_ignoring_word_boundaries(self) -> None:
        postcode = self.fake.postcode()
        text = f"text{postcode}text"

        payload = {
            ConfigKeys.ANONYMISE_CODES_AT_WORD_BOUNDARIES_ONLY: False,
            ApiKeys.THIRD_PARTY: {
                ApiKeys.CODES: [postcode],
            },
            ApiKeys.TEXT: {"test": text},
        }

        self.assertIn(postcode, text)

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertNotIn(postcode, anonymised)

        self.assertEqual(anonymised.count("[__TTT__]"), 1)

    def test_anonymise_dates_ignoring_word_boundaries(self) -> None:
        date_of_birth = self.fake.date_of_birth().strftime("%d %b %Y")
        text = f"text{date_of_birth}text"

        payload = {
            ConfigKeys.ANONYMISE_DATES_AT_WORD_BOUNDARIES_ONLY: False,
            ApiKeys.THIRD_PARTY: {
                ApiKeys.DATES: [date_of_birth],
            },
            ApiKeys.TEXT: {"test": text},
        }

        self.assertIn(date_of_birth, text)

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertNotIn(date_of_birth, anonymised)

        self.assertEqual(anonymised.count("[__TTT__]"), 1)

    def test_anonymise_numbers_ignoring_word_boundaries(self) -> None:
        phone = self.fake.phone_number()
        text = f"text{phone}text"

        payload = {
            ConfigKeys.ANONYMISE_NUMBERS_AT_NUMERIC_BOUNDARIES_ONLY: False,
            ConfigKeys.ANONYMISE_NUMBERS_AT_WORD_BOUNDARIES_ONLY: False,
            ApiKeys.THIRD_PARTY: {
                ApiKeys.NUMBERS: [phone],
            },
            ApiKeys.TEXT: {"test": text},
        }

        self.assertIn(phone, text)

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertNotIn(phone, anonymised)
        self.assertEqual(anonymised.count("[__TTT__]"), 1)

    def test_anonymise_numbers_ignoring_numeric_boundaries(self) -> None:
        phone = self.fake.phone_number()
        text = f"1234{phone}5678"

        payload = {
            ConfigKeys.ANONYMISE_NUMBERS_AT_NUMERIC_BOUNDARIES_ONLY: False,
            ConfigKeys.ANONYMISE_NUMBERS_AT_WORD_BOUNDARIES_ONLY: False,
            ApiKeys.THIRD_PARTY: {
                ApiKeys.NUMBERS: [phone],
            },
            ApiKeys.TEXT: {"test": text},
        }

        self.assertIn(phone, text)

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertNotIn(phone, anonymised)
        self.assertEqual(anonymised.count("[__TTT__]"), 1)

    def test_anonymise_strings_ignoring_word_boundaries(self) -> None:
        word = "secret"
        text = f"text{word}text"

        payload = {
            ConfigKeys.ANONYMISE_STRINGS_AT_WORD_BOUNDARIES_ONLY: False,
            ApiKeys.THIRD_PARTY: {
                ApiKeys.WORDS: [word],
            },
            ApiKeys.TEXT: {"test": text},
        }

        self.assertIn(word, text)

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertNotIn(word, anonymised)
        self.assertEqual(anonymised.count("[__TTT__]"), 1)

    def test_string_max_regex_errors(self) -> None:
        word = "secret"
        typo = "sceret"
        text = f"{typo}"

        payload = {
            ConfigKeys.STRING_MAX_REGEX_ERRORS: 2,  # delete 1, insert 1
            ApiKeys.THIRD_PARTY: {
                ApiKeys.WORDS: [word],
            },
            ApiKeys.TEXT: {"test": text},
        }

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertNotIn(typo, anonymised)
        self.assertEqual(anonymised.count("[__TTT__]"), 1)

    def test_min_string_length_for_errors(self) -> None:
        word1 = "secret"
        typo1 = "sceret"

        word2 = "private"
        typo2 = "prviate"
        text = f"{typo1} {typo2}"

        payload = {
            ConfigKeys.STRING_MAX_REGEX_ERRORS: 2,  # delete 1, insert 1
            ConfigKeys.MIN_STRING_LENGTH_FOR_ERRORS: 7,
            ApiKeys.THIRD_PARTY: {
                ApiKeys.WORDS: [word1, word2],
            },
            ApiKeys.TEXT: {"test": text},
        }

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertIn(typo1, anonymised)
        self.assertNotIn(typo2, anonymised)
        self.assertEqual(anonymised.count("[__TTT__]"), 1)

    def test_min_string_length_to_scrub_with(self) -> None:
        payload = {
            ConfigKeys.MIN_STRING_LENGTH_TO_SCRUB_WITH: 6,
            ApiKeys.THIRD_PARTY: {
                ApiKeys.WORDS: ["Craig Buchanan"],
            },
            ApiKeys.TEXT: {"test": "Craig Buchanan"},
        }

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertIn("Craig", anonymised)
        self.assertNotIn("Buchanan", anonymised)
        self.assertEqual(anonymised.count("[__TTT__]"), 1)

    def test_scrub_string_suffixes(self) -> None:
        word = "secret"

        payload = {
            ConfigKeys.SCRUB_STRING_SUFFIXES: ["s"],
            ApiKeys.THIRD_PARTY: {
                ApiKeys.WORDS: [word],
            },
            ApiKeys.TEXT: {"test": "secrets"},
        }

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertNotIn("secrets", anonymised)
        self.assertEqual(anonymised.count("[__TTT__]"), 1)

    def test_allowlist_words(self) -> None:
        # A bit of a contrived example but the allowlist should
        # take precedence.
        payload = {
            ApiKeys.THIRD_PARTY: {
                ApiKeys.WORDS: ["secret", "private", "confidential"],
            },
            ApiKeys.ALLOWLIST: {"words": ["secret"]},
            ApiKeys.TEXT: {"test": "secret private confidential"},
        }

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertIn("secret", anonymised)
        self.assertNotIn("private", anonymised)
        self.assertNotIn("confidential", anonymised)
        self.assertEqual(anonymised.count("[__TTT__]"), 2)

    def test_allowlist_files(self) -> None:
        payload = {
            ApiKeys.THIRD_PARTY: {
                ApiKeys.WORDS: ["secret", "private", "confidential"],
            },
            ApiKeys.ALLOWLIST: {"files": ["test"]},
            ApiKeys.TEXT: {"test": "secret private confidential"},
        }

        with NamedTemporaryFile(delete=False, mode="w") as f:
            filename = f.name
            f.write("secret\n")

        filename_map = {"test": filename}
        settings = DEFAULT_SETTINGS.copy()
        settings[ApiSettingsKeys.ALLOWLIST_FILENAMES] = filename_map

        with override_settings(ANONYMISE_API=settings):
            response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertIn("secret", anonymised)
        self.assertNotIn("private", anonymised)
        self.assertNotIn("confidential", anonymised)
        self.assertEqual(anonymised.count("[__TTT__]"), 2)

    def test_phrase_alternatives(self) -> None:
        payload = {
            ApiKeys.THIRD_PARTY: {
                ApiKeys.PHRASES: ["22 Acacia Avenue"],
            },
            ApiKeys.ALTERNATIVES: [["Avenue", "Ave"]],
            ApiKeys.TEXT: {"test": "22 Acacia Ave"},
        }

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertNotIn("22 Acacia Ave", anonymised)
        self.assertEqual(anonymised.count("[__TTT__]"), 1)

    def test_scrub_all_numbers_of_n_digits(self) -> None:
        nhs_number = str(generate_random_nhs_number())

        text = f"{self.fake.text()} {nhs_number} {self.fake.text()}"

        self.assertIn(nhs_number, text)

        payload = {
            ConfigKeys.SCRUB_ALL_NUMBERS_OF_N_DIGITS: [10],
            ApiKeys.TEXT: {"test": text},
        }

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertNotIn(nhs_number, anonymised)
        self.assertEqual(anonymised.count("[~~~]"), 1)

    def test_scrub_all_numbers_of_n_digits_ignoring_word_boundaries(
        self,
    ) -> None:
        nhs_number = str(generate_random_nhs_number())

        text = f"text{nhs_number}text"

        self.assertIn(nhs_number, text)

        payload = {
            ConfigKeys.SCRUB_ALL_NUMBERS_OF_N_DIGITS: [10],
            ConfigKeys.ANONYMISE_NUMBERS_AT_WORD_BOUNDARIES_ONLY: False,
            ApiKeys.TEXT: {"test": text},
        }

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertNotIn(nhs_number, anonymised)
        self.assertEqual(anonymised.count("[~~~]"), 1)

    def test_scrub_all_uk_postcodes(self) -> None:
        postcode = self.fake.postcode()

        text = f"{self.fake.text()} {postcode} {self.fake.text()}"

        self.assertIn(postcode, text)

        payload = {
            ConfigKeys.SCRUB_ALL_UK_POSTCODES: True,
            ApiKeys.TEXT: {"test": text},
        }

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertNotIn(postcode, anonymised)
        self.assertEqual(anonymised.count("[~~~]"), 1)

    def test_scrub_all_uk_postcodes_ignoring_word_boundary(self) -> None:
        postcode = self.fake.postcode()

        text = f"text{postcode}text"

        self.assertIn(postcode, text)

        payload = {
            ConfigKeys.ANONYMISE_CODES_AT_WORD_BOUNDARIES_ONLY: False,
            ConfigKeys.SCRUB_ALL_UK_POSTCODES: True,
            ApiKeys.TEXT: {"test": text},
        }

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertNotIn(postcode, anonymised)
        self.assertEqual(anonymised.count("[~~~]"), 1)

    def test_scrub_all_uk_postcodes_replacement_text(self) -> None:
        postcode = self.fake.postcode()

        payload = {
            ConfigKeys.SCRUB_ALL_UK_POSTCODES: True,
            ConfigKeys.REPLACE_NONSPECIFIC_INFO_WITH: "[REDACTED]",
            ApiKeys.TEXT: {"test": postcode},
        }

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertNotIn(postcode, anonymised)
        self.assertEqual(anonymised.count("[REDACTED]"), 1)

    def test_scrub_all_dates(self) -> None:
        dob = self.fake.date_of_birth().strftime("%d %b %Y")

        text = f"{self.fake.text()} {dob} {self.fake.text()}"

        self.assertIn(dob, text)

        payload = {
            ConfigKeys.SCRUB_ALL_DATES: True,
            ApiKeys.TEXT: {"test": text},
        }

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertNotIn(dob, anonymised)
        self.assertEqual(anonymised.count("[~~~]"), 1)

    def test_blur_all_dates(self) -> None:
        dob = self.fake.date_of_birth()
        dob_string = dob.strftime("%d %b %Y")

        text = f"{self.fake.text()} {dob_string} {self.fake.text()}"

        self.assertIn(dob_string, text)

        payload = {
            ConfigKeys.SCRUB_ALL_DATES: True,
            ConfigKeys.REPLACE_ALL_DATES_WITH: "%b '%y",
            ApiKeys.TEXT: {"test": text},
        }

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertNotIn(dob_string, anonymised)
        expected = dob.strftime("%b '%y")
        self.assertEqual(anonymised.count(expected), 1)

    def test_scrub_all_email_addresses(self) -> None:
        email = self.fake.email()

        text = f"{self.fake.text()} {email} {self.fake.text()}"

        self.assertIn(email, text)

        payload = {
            ConfigKeys.SCRUB_ALL_EMAIL_ADDRESSES: True,
            ApiKeys.TEXT: {"test": text},
        }

        response = self.scrub_post(payload)
        self.assertEqual(
            response.status_code, HttpStatus.OK, msg=response.data
        )

        anonymised = response.data[ApiKeys.ANONYMISED]["test"]

        self.assertNotIn(email, anonymised)
        self.assertEqual(anonymised.count("[~~~]"), 1)
