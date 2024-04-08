"""
crate_anon/testing/providers.py

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

**Faker test data providers.**

There may be some interest in a Faker Medical community provider if we felt it
was worth the effort.

https://github.com/joke2k/faker/issues/1142

"""

import datetime
from typing import Any, List

from cardinal_pythonlib.datetimefunc import pendulum_to_datetime
from cardinal_pythonlib.nhs import generate_random_nhs_number
from faker import Faker
from faker.providers import BaseProvider
import pendulum
from pendulum import DateTime as Pendulum


class ChoiceProvider(BaseProvider):
    def random_choice(self, choices: List, **kwargs) -> Any:
        """
        Given a list of choices return a random value
        """
        choices = self.generator.random.choices(choices, **kwargs)

        return choices[0]


class DateFormatProvider(ChoiceProvider):
    """
    Return a random date format.
    """

    def date_format(self) -> str:
        return self.random_choice(
            [
                "%d %b %Y",  # e.g. 24 Jul 2013
                "%d %B %Y",  # e.g. 24 July 2013
                "%Y-%m-%d",  # e.g. 2013-07-24
                "%Y-%m-%d",  # e.g. 20130724
                "%Y%m%d",  # e.g. 20130724
            ]
        )


class SexProvider(ChoiceProvider):
    """
    Return a random sex, with realistic distribution.
    """

    def sex(self) -> str:
        return self.random_choice(["M", "F", "X"], weights=[49.8, 49.8, 0.4])


class ForenameProvider(BaseProvider):
    """
    Return a forename given the sex of the person
    """

    def forename(self, sex: str) -> str:
        if sex == "M":
            return self.generator.first_name_male()

        if sex == "F":
            return self.generator.first_name_female()

        return self.generator.first_name()[:1]


class FormattedDateOfBirthProvider(BaseProvider):
    """
    Return a random date of birth in a random format
    """

    def formatted_date_of_birth(self) -> str:
        dob = self.generator.date_of_birth()
        format = self.generator.date_format()

        return dob.strftime(format)


# No one is born after this
_max_birth_datetime = Pendulum(year=2000, month=1, day=1, hour=9)
_datetime = _max_birth_datetime


class IncrementingDateProvider(BaseProvider):
    """
    Return a datetime one day more than the previous one.
    Starts at 1st January 2000.
    """

    def incrementing_date(self) -> datetime.datetime:
        global _datetime
        _p = _datetime
        _datetime = _datetime.add(days=1)
        return pendulum_to_datetime(_p)


class FormattedIncrementingDateProvider(BaseProvider):
    """
    Returns an incrementing date in a random format.
    """

    def formatted_incrementing_date(self) -> datetime.datetime:
        date = self.generator.incrementing_date()
        format = self.generator.date_format()

        return date.strftime(format)


class ConsistentDateOfBirthProvider(BaseProvider):
    """
    Returns a date of birth no greater than 1st January 2000. All patient notes
    are created after this date.

    Faker date_of_birth calculates from the current time so gives different
    results on different days. In our case we don't want the date of birth to
    be greater than the date stamp on the note.
    """

    def consistent_date_of_birth(self) -> datetime.datetime:
        return self.generator.date_between_dates(
            date_start=pendulum.date(1900, 1, 1),
            date_end=_max_birth_datetime,
        )


class RelationshipProvider(ChoiceProvider):
    def relationship(self) -> str:
        # independent of sex for now
        return self.random_choice(
            [
                "child",
                "parent",
                "sibling",
                "spouse",
                "partner",
                "carer",
            ]
        )


class AlcoholProvider(ChoiceProvider):
    def alcohol(self) -> str:
        units = self.generator.pyint(max_value=100)
        alcohol = self.random_choice(
            [
                f"Alcohol {units} u/w",
                f"EtOH = {units} u/w",
                f"Alcohol (units/week): {units}",
                f"alcohol {units} I.U./week",
                f"Was previously drinking {units} u/w",
                "teetotal",
                "Alcohol: no",
                "Abstinent from alcohol",
                f"Alcohol: presently less than {units} u/w",
            ]
        )

        return alcohol


class PatientNoteProvider(BaseProvider):
    @staticmethod
    def _possessive_pronoun(sex: str) -> str:
        possessive_pronouns = {
            "M": "his",
            "F": "her",
            "X": "their",
        }

        return possessive_pronouns[sex]

    def patient_note(
        self,
        forename: str = None,
        surname: str = None,
        sex: str = None,
        dob: datetime.datetime = None,
        nhs_number: int = None,
        patient_id: int = None,
        note_datetime: datetime.datetime = None,
        relation_name: str = None,
        relation_relationship: str = None,
        words_per_note: int = 1000,
        pad_paragraph: str = None,
    ) -> str:

        if sex is None:
            sex = self.generator.sex()

        if forename is None:
            forename = self.generator.forename(sex)

        if surname is None:
            surname = self.generator.last_name()

        if dob is None:
            dob = self.generator.consistent_date_of_birth()

        if nhs_number is None:
            nhs_number = self.generator.nhs_number()

        if patient_id is None:
            patient_id = self.generator.pyint(min_value=1, max_value=100000)

        if note_datetime is None:
            note_datetime = self.generator.incrementing_date()

        if relation_name is None:
            relation_name = f"{self.generator.name()}"

        if relation_relationship is None:
            relation_relationship = self.generator.relationship()

        if pad_paragraph is None:
            pad_paragraph = self.generator.paragraph(
                nb_sentences=words_per_note / 2,  # way more than we need
            )

        possessive_pronoun = self._possessive_pronoun(sex)

        other_notes = [
            "Start aspirin 75mg od. Remains on Lipitor 40mg nocte",
            "For haloperidol 2mg po prn max qds",
            "Start amoxicillin 500 mg b.i.d. for 7 days",
            f"{possessive_pronoun.capitalize()} CRP is 10",
            (
                f"{possessive_pronoun.capitalize()} "
                "previous CRP was <13 mg/dl"
            ),
            "Sodium 140",
            "TSH 3.5; urea normal",
            "Height 1.82m, weight 75kg, BMI 22.6. BP 135/82",
            "MMSE 28/30. ACE-R 72, ACE-II 73, ACE 73",
            "ESR 16 (H) mm/h",
            (
                "WBC 9.2; neutrophils 4.3; lymphocytes 2.6; "
                "eosinophils 0.4; monocytes 1.2; basophils 0.6"
            ),
            (
                f"{forename} took venlafaxine 375 M/R od, "
                "and is due to start clozapine 75mg bd"
            ),
        ]

        other_note = self.generator.word(other_notes)

        formatted_dob = dob.strftime(self.generator.date_format())
        note_date_formatted = note_datetime.strftime(
            self.generator.date_format()
        )
        another_date_formatted = self.generator.formatted_date_of_birth()
        alcohol = self.generator.alcohol()

        note_text = (
            f"I saw {forename} {surname} on "
            f"{note_date_formatted} "
            f"(DOB: {formatted_dob}, NHS {nhs_number}, "
            f"Patient id: {patient_id}), "
            f"accompanied by {possessive_pronoun} "
            f"{relation_relationship} {relation_name}. "
            f"{alcohol}. "
            f"Another date: {another_date_formatted}. "
            f"{other_note}."
        )

        num_pad_words = words_per_note - len(note_text.split())
        pad_words = " ".join(pad_paragraph.split()[:num_pad_words])
        return f"{note_text} {pad_words}"


class NhsNumberProvider(BaseProvider):
    def nhs_number(self) -> str:
        return generate_random_nhs_number()


def register_all_providers(fake: Faker) -> None:
    fake.add_provider(AlcoholProvider)
    fake.add_provider(ChoiceProvider)
    fake.add_provider(ConsistentDateOfBirthProvider)
    fake.add_provider(DateFormatProvider)
    fake.add_provider(ForenameProvider)
    fake.add_provider(FormattedDateOfBirthProvider)
    fake.add_provider(FormattedIncrementingDateProvider)
    fake.add_provider(IncrementingDateProvider)
    fake.add_provider(NhsNumberProvider)
    fake.add_provider(PatientNoteProvider)
    fake.add_provider(RelationshipProvider)
    fake.add_provider(SexProvider)
