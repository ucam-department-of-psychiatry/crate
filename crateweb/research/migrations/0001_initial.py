# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Lookup',
            fields=[
                ('pid', models.PositiveIntegerField(db_column='patient_id', serialize=False, primary_key=True)),
                ('mpid', models.PositiveIntegerField(db_column='nhsnum')),
                ('rid', models.CharField(db_column='brcid', max_length=255)),
                ('mrid', models.CharField(db_column='nhshash', max_length=255)),
                ('trid', models.PositiveIntegerField(db_column='trid')),
            ],
            options={
                'managed': False,
                'db_table': 'secret_map',
            },
        ),
    ]
