# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consent', '0008_auto_20151022_2006'),
    ]

    operations = [
        migrations.RenameField(
            model_name='consentmode',
            old_name='created_by_user',
            new_name='created_by',
        ),
    ]
