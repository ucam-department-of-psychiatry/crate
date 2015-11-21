# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='PidLookup',
            fields=[
                ('pid', models.PositiveIntegerField(serialize=False, primary_key=True, db_column='patient_id')),
                ('mpid', models.PositiveIntegerField(db_column='nhsnum')),
                ('rid', models.CharField(max_length=255, db_column='brcid')),
                ('mrid', models.CharField(max_length=255, db_column='nhshash')),
                ('trid', models.PositiveIntegerField(db_column='trid')),
            ],
            options={
                'db_table': 'secret_map',
                'managed': False,
            },
        ),
    ]
