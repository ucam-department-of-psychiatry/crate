# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consent', '0004_auto_20151022_1338'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='consentmode',
            name='patient',
        ),
        migrations.RemoveField(
            model_name='patientlookup',
            name='patient',
        ),
        migrations.AddField(
            model_name='consentmode',
            name='nhs_number',
            field=models.BigIntegerField(default=None, verbose_name='NHS number'),
            preserve_default=False,
        ),
        migrations.DeleteModel(
            name='Patient',
        ),
    ]
