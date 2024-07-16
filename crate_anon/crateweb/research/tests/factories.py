"""
crate_anon/crateweb/research/tests/factories.py

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

Factory Boy test factories.

"""

import factory

from django.conf import settings

from crate_anon.crateweb.research.models import (
    PatientExplorer,
    Query,
    SitewideQuery,
)


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = settings.AUTH_USER_MODEL

    username = factory.Sequence(lambda n: f"user-{n}")


class QueryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Query

    user = factory.SubFactory(UserFactory)


class SitewideQueryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SitewideQuery


class PatientExplorerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PatientExplorer

    user = factory.SubFactory(UserFactory)
