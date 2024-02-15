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

"""

import datetime
from typing import Any, List

from cardinal_pythonlib.datetimefunc import pendulum_to_datetime
from faker.providers import BaseProvider
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


class FormattedDateOfBirthProvider(BaseProvider):
    """
    Return a random date of birth in a random format
    """

    def formatted_date_of_birth(self) -> str:
        dob = self.generator.date_of_birth()
        format = self.generator.date_format()

        return dob.strftime(format)


# No one is born after this
first_datetime = Pendulum(year=2000, month=1, day=1, hour=9)
_datetime = first_datetime


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
                "Abstinant from alcohol",
                f"Alcohol: presently less than {units} u/w",
            ]
        )

        return alcohol
