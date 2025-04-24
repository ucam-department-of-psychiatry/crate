"""
crate_anon/anonymise/tests/models_tests.py

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

"""

import random
from unittest import mock

from crate_anon.anonymise.models import PatientInfo
from crate_anon.testing.classes import SlowSecretDatabaseTestCase


class PatientInfoTests(SlowSecretDatabaseTestCase):
    def test_patient_saved_with_random_trid(self) -> None:
        expected_trids = [7, 1, 5, 6, 4, 10, 3, 2, 9, 8]

        with mock.patch.multiple(
            "crate_anon.anonymise.models",
            MAX_TRID=10,
        ):
            random.seed(12345)

            for i, expected_trid in enumerate(expected_trids):
                patient = PatientInfo(pid=i + 1)
                patient.ensure_trid(self.secret_dbsession)
                self.assertEqual(patient.trid, expected_trid)
