# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('userprofile', '0002_auto_20151021_1630'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='collapse_at',
            field=models.PositiveSmallIntegerField(default=400, verbose_name='Number of characters beyond which results field starts collapsed (0 for none)'),
        ),
        migrations.AddField(
            model_name='userprofile',
            name='line_length',
            field=models.PositiveSmallIntegerField(default=80, verbose_name='Characters to word-wrap text at in results display (0 for no wrap)'),
        ),
    ]
