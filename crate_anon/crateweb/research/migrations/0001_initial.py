#!/usr/bin/env python

"""
crate_anon/crateweb/research/migrations/0001_initial.py

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

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
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.

===============================================================================

**Research app, migration 0001.**

"""

from __future__ import unicode_literals

from django.db import migrations, models
# noinspection PyPackageRequirements
import picklefield.fields
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PidLookup',
            fields=[
                ('pid', models.PositiveIntegerField(serialize=False, primary_key=True, db_column='patient_id')),  # noqa
                ('mpid', models.PositiveIntegerField(db_column='nhsnum')),
                ('rid', models.CharField(max_length=255, db_column='brcid')),
                ('mrid', models.CharField(max_length=255, db_column='nhshash')),
                ('trid', models.PositiveIntegerField(db_column='trid')),
            ],
            options={
                'managed': False,
                'db_table': 'secret_map',
            },
        ),
        migrations.CreateModel(
            name='Highlight',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('colour', models.PositiveSmallIntegerField(verbose_name='Colour number')),  # noqa
                ('text', models.CharField(max_length=255, verbose_name='Text to highlight')),  # noqa
                ('active', models.BooleanField(default=True)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),  # noqa
            ],
        ),
        migrations.CreateModel(
            name='Query',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('sql', models.TextField(verbose_name='SQL query')),
                ('args', picklefield.fields.PickledObjectField(verbose_name='Pickled arguments', null=True, editable=False)),  # noqa
                ('raw', models.BooleanField(verbose_name='SQL is raw, not parameter-substituted', default=False)),  # noqa
                ('qmark', models.BooleanField(verbose_name='Parameter-substituted SQL uses ?, not %s, as placeholders', default=True)),  # noqa
                ('active', models.BooleanField(default=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('deleted', models.BooleanField(verbose_name="Deleted from the user's perspective. Audited queries are never properly deleted.", default=False)),  # noqa
                ('audited', models.BooleanField(default=False)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),  # noqa
            ],
        ),
        migrations.CreateModel(
            name='QueryAudit',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('when', models.DateTimeField(auto_now_add=True)),
                ('count_only', models.BooleanField(default=False)),
                ('n_records', models.PositiveIntegerField(default=0)),
                ('failed', models.BooleanField(default=False)),
                ('fail_msg', models.TextField()),
                ('query', models.ForeignKey(to='research.Query', on_delete=models.PROTECT)),  # noqa
            ],
        ),
    ]
