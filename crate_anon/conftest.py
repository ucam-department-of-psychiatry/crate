#!/usr/bin/env python

"""
crate_anon/conftest.py

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

pytest configuration

"""


import os

import pytest

from crate_anon.common.constants import EnvVar

os.environ[EnvVar.RUNNING_TESTS] = "True"


@pytest.fixture
def db_access_without_rollback_and_truncate(
    request, django_db_setup, django_db_blocker
):
    django_db_blocker.unblock()
    request.addfinalizer(django_db_blocker.restore)
