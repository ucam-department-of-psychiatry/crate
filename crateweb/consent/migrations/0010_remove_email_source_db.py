# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consent', '0009_auto_20151022_2020'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='email',
            name='source_db',
        ),
    ]
