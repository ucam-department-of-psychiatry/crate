# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consent', '0010_remove_email_source_db'),
    ]

    operations = [
        migrations.AlterField(
            model_name='teamrep',
            name='team',
            field=models.CharField(verbose_name='Team description', unique=True, max_length=100),
        ),
    ]
