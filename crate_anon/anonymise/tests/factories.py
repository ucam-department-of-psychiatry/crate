"""
crate_anon/anonymise/tests/factories.py

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

**Factory Boy SQL Alchemy test factories for anonymisation.**

"""

from typing import TYPE_CHECKING

from cardinal_pythonlib.hash import HashMethods, make_hasher
import factory

from crate_anon.anonymise.models import PatientInfo
from crate_anon.testing.factories import SecretBaseFactory, Fake

if TYPE_CHECKING:
    from factory.builder import Resolver


class PatientInfoFactory(SecretBaseFactory):
    class Meta:
        exclude = ("hasher",)
        model = PatientInfo

    hasher = make_hasher(HashMethods.HMAC_MD5, "encryptionphrase")
    pid = factory.Sequence(lambda n: n + 1)
    mpid = factory.LazyFunction(Fake.en_gb.nhs_number)

    @factory.lazy_attribute
    def rid(obj: "Resolver") -> str:
        return obj.hasher.hash(obj.pid)
