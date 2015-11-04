# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('consent', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='study',
            name='researchers',
            field=models.ManyToManyField(to=settings.AUTH_USER_MODEL, related_name='studies_as_researcher'),
        ),
        migrations.AlterField(
            model_name='study',
            name='lead_researcher',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, related_name='studies_as_lead'),
        ),
    ]
