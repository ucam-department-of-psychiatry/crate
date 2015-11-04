# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consent', '0005_auto_20151022_1508'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='DummyPatientLookup',
            new_name='DummyPatientSourceInfo',
        ),
    ]
