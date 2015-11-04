# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('userprofile', '0003_auto_20151021_2252'),
    ]

    operations = [
        migrations.AddField(
            model_name='userprofile',
            name='is_consultant',
            field=models.BooleanField(default=False, verbose_name='User is an NHS consultant'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='userprofile',
            name='signatory_title',
            field=models.CharField(verbose_name='Title for signature (e.g. "Consultant psychiatrist")', default='', max_length=255),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='userprofile',
            name='title',
            field=models.CharField(blank=True, max_length=20),
        ),
    ]
