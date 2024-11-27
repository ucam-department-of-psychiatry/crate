"""
crate_anon/crateweb/research/tests/models_tests.py

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

Test models.py.

"""

from unittest import TestCase

from cardinal_pythonlib.hash import hash64

import pytest

from crate_anon.crateweb.research.models import PatientMultiQuery
from crate_anon.crateweb.research.tests.factories import (
    PatientExplorerFactory,
    QueryFactory,
    SitewideQueryFactory,
    UserFactory,
)


class QueryTest(TestCase):
    @pytest.mark.django_db
    def test_sql_hash_saved_when_update_fields_none(self) -> None:
        query = QueryFactory()
        query.save()

        sql = "SELECT foo from bar"
        query.sql = sql
        query.save()
        query.refresh_from_db()

        self.assertEqual(query.sql_hash, hash64(sql))

    @pytest.mark.django_db
    def test_sql_hash_saved_when_sql_in_update_fields(self) -> None:
        """
        Since Django 4.2 custom save() methods should update the update_fields
        argument.
        """
        query = QueryFactory()
        query.save()

        sql = "SELECT foo from bar"
        query.sql = sql
        query.save(update_fields=["sql"])
        query.refresh_from_db()

        self.assertEqual(query.sql_hash, hash64(sql))

    @pytest.mark.django_db
    def test_sql_hash_not_saved_when_sql_not_in_update_fields(self) -> None:
        """
        Since Django 4.2 custom save() methods should update the update_fields
        argument.
        """
        old_sql = "SELECT foo from old"
        query = QueryFactory(sql=old_sql, raw=False)
        query.save()

        new_sql = "SELECT foo from new"
        query.sql = new_sql
        query.raw = True
        query.save(update_fields=["raw"])
        query.refresh_from_db()

        self.assertEqual(query.sql_hash, hash64(old_sql))

    @pytest.mark.django_db
    def test_formatted_sql_saved_when_update_fields_none(self) -> None:
        """
        Since Django 4.2 custom save() methods should update the update_fields
        argument.
        """
        query = QueryFactory()
        query.save()

        sql = "SELECT foo from bar"
        query.sql = sql
        query.save()
        query.refresh_from_db()

        for word in sql.split():
            self.assertIn(word, query.formatted_sql)

    @pytest.mark.django_db
    def test_formatted_sql_saved_when_sql_in_update_fields(self) -> None:
        """
        Since Django 4.2 custom save() methods should update the update_fields
        argument.
        """
        query = QueryFactory()
        query.save()

        sql = "SELECT foo from bar"
        query.sql = sql
        query.save(update_fields=["sql"])
        query.refresh_from_db()

        for word in sql.split():
            self.assertIn(word, query.formatted_sql)

    @pytest.mark.django_db
    def test_formatted_sql_not_saved_when_sql_not_in_update_fields(
        self,
    ) -> None:
        """
        Since Django 4.2 custom save() methods should update the update_fields
        argument.
        """
        old_sql = "SELECT foo from old"
        query = QueryFactory(raw=False, sql=old_sql)
        query.save()

        new_sql = "SELECT foo from new"
        query.sql = new_sql
        query.raw = True
        query.save(update_fields=["raw"])
        query.refresh_from_db()

        for word in old_sql.split():
            self.assertIn(word, query.formatted_sql)

    @pytest.mark.django_db
    def test_active_query_changes_when_object_saved(self) -> None:
        user = UserFactory()

        query1 = QueryFactory(user=user, active=True)
        query1.save()
        query1.refresh_from_db()
        self.assertTrue(query1.active)

        query2 = QueryFactory(user=user, active=True)
        query2.save()
        query2.refresh_from_db()
        query1.refresh_from_db()

        self.assertTrue(query2.active)
        self.assertFalse(query1.active)


class SitewideQueryTest(TestCase):
    @pytest.mark.django_db
    def test_sql_hash_saved_when_update_fields_none(self) -> None:
        query = SitewideQueryFactory()
        query.save()

        sql = "SELECT foo from bar"
        query.sql = sql
        query.save()
        query.refresh_from_db()

        self.assertEqual(query.sql_hash, hash64(sql))

    @pytest.mark.django_db
    def test_sql_hash_saved_when_sql_in_update_fields(self) -> None:
        """
        Since Django 4.2 custom save() methods should update the update_fields
        argument.
        """
        query = SitewideQueryFactory()
        query.save()

        sql = "SELECT foo from bar"
        query.sql = sql
        query.save(update_fields=["sql"])
        query.refresh_from_db()

        self.assertEqual(query.sql_hash, hash64(sql))

    @pytest.mark.django_db
    def test_sql_hash_not_saved_when_sql_not_in_update_fields(self) -> None:
        """
        Since Django 4.2 custom save() methods should update the update_fields
        argument.
        """
        old_sql = "SELECT foo from old"
        query = SitewideQueryFactory(sql=old_sql, raw=False)
        query.save()

        new_sql = "SELECT foo from new"
        query.sql = new_sql
        query.raw = True
        query.save(update_fields=["raw"])
        query.refresh_from_db()

        self.assertEqual(query.sql_hash, hash64(old_sql))

    @pytest.mark.django_db
    def test_formatted_sql_saved_when_update_fields_none(self) -> None:
        """
        Since Django 4.2 custom save() methods should update the update_fields
        argument.
        """
        query = SitewideQueryFactory()
        query.save()

        sql = "SELECT foo from bar"
        query.sql = sql
        query.save()
        query.refresh_from_db()

        for word in sql.split():
            self.assertIn(word, query.formatted_sql)

    @pytest.mark.django_db
    def test_formatted_sql_saved_when_sql_in_update_fields(self) -> None:
        """
        Since Django 4.2 custom save() methods should update the update_fields
        argument.
        """
        query = SitewideQueryFactory()
        query.save()

        sql = "SELECT foo from bar"
        query.sql = sql
        query.save(update_fields=["sql"])
        query.refresh_from_db()

        for word in sql.split():
            self.assertIn(word, query.formatted_sql)

    @pytest.mark.django_db
    def test_formatted_sql_not_saved_when_sql_not_in_update_fields(
        self,
    ) -> None:
        """
        Since Django 4.2 custom save() methods should update the update_fields
        argument.
        """
        old_sql = "SELECT foo from old"
        query = SitewideQueryFactory(raw=False, sql=old_sql)
        query.save()

        new_sql = "SELECT foo from new"
        query.sql = new_sql
        query.raw = True
        query.save(update_fields=["raw"])
        query.refresh_from_db()

        for word in old_sql.split():
            self.assertIn(word, query.formatted_sql)


class PatientExplorerTest(TestCase):
    @pytest.mark.django_db
    def test_pmq_hash_saved_when_update_fields_none(self) -> None:
        explorer = PatientExplorerFactory()
        explorer.save()

        explorer.patient_multiquery = PatientMultiQuery()
        explorer.save()
        explorer.refresh_from_db()

        self.assertEqual(explorer.pmq_hash, explorer.patient_multiquery.hash64)

    @pytest.mark.django_db
    def test_pmq_hash_saved_when_patient_multiquery_in_update_fields(
        self,
    ) -> None:
        """
        Since Django 4.2 custom save() methods should update the update_fields
        argument.
        """
        explorer = PatientExplorerFactory()
        explorer.save()

        explorer.patient_multiquery = PatientMultiQuery(
            manual_patient_id_query="SELECT foo FROM bar"
        )
        explorer.save(update_fields=["patient_multiquery"])
        explorer.refresh_from_db()

        self.assertEqual(explorer.pmq_hash, explorer.patient_multiquery.hash64)

    @pytest.mark.django_db
    def test_pmq_hash_not_saved_when_pmq_not_in_update_fields(self) -> None:
        """
        Since Django 4.2 custom save() methods should update the update_fields
        argument.
        """
        old_multiquery = PatientMultiQuery(
            manual_patient_id_query="SELECT foo FROM old"
        )
        explorer = PatientExplorerFactory(
            patient_multiquery=old_multiquery, audited=False
        )
        explorer.save()

        new_multiquery = PatientMultiQuery(
            manual_patient_id_query="SELECT foo FROM new"
        )
        explorer.patient_multiquery = new_multiquery
        explorer.audited = True

        explorer.save(update_fields=["audited"])
        explorer.refresh_from_db()

        self.assertNotEqual(old_multiquery.hash64, new_multiquery.hash64)
        self.assertEqual(explorer.pmq_hash, old_multiquery.hash64)

    @pytest.mark.django_db
    def test_active_patient_explorer_changes_when_object_saved(self) -> None:
        user = UserFactory()

        explorer1 = PatientExplorerFactory(user=user, active=True)
        explorer1.save()
        explorer1.refresh_from_db()
        self.assertTrue(explorer1.active)

        explorer2 = PatientExplorerFactory(user=user, active=True)
        explorer2.save()
        explorer2.refresh_from_db()
        explorer1.refresh_from_db()

        self.assertTrue(explorer2.active)
        self.assertFalse(explorer1.active)
