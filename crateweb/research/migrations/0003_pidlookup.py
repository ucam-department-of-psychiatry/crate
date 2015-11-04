# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('research', '0002_highlight_query_queryaudit'),
    ]

    operations = [
        migrations.CreateModel(
            name='PidLookup',
            fields=[
                ('pid', models.PositiveIntegerField(serialize=False, primary_key=True, db_column='patient_id')),
                ('mpid', models.PositiveIntegerField(db_column='nhsnum')),
                ('rid', models.CharField(db_column='brcid', max_length=255)),
                ('mrid', models.CharField(db_column='nhshash', max_length=255)),
                ('trid', models.PositiveIntegerField(db_column='trid')),
            ],
            options={
                'db_table': 'secret_map',
                'managed': False,
            },
        ),
    ]
