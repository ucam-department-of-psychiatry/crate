# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        ('consent', '0002_auto_20151021_1630'),
    ]

    operations = [
        migrations.AlterField(
            model_name='study',
            name='rec_reference',
            field=models.CharField(verbose_name='Research Ethics Committee reference', max_length=50, blank=True),
        ),
        migrations.AlterField(
            model_name='study',
            name='researchers',
            field=models.ManyToManyField(to=settings.AUTH_USER_MODEL, related_name='studies_as_researcher', blank=True),
        ),
        migrations.AlterField(
            model_name='study',
            name='search_methods_planned',
            field=models.TextField(verbose_name='Search methods planned', blank=True),
        ),
    ]
