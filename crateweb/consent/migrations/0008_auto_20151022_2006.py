# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import core.extra
import consent.models
import django.core.files.storage


class Migration(migrations.Migration):

    dependencies = [
        ('consent', '0007_leaflet'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='consentmode',
            options={},
        ),
        migrations.AddField(
            model_name='consentmode',
            name='current',
            field=models.BooleanField(default=True),
        ),
        migrations.AlterField(
            model_name='leaflet',
            name='pdf',
            field=core.extra.ContentTypeRestrictedFileField(upload_to=consent.models.leaflet_upload_to, storage=django.core.files.storage.FileSystemStorage(base_url='/privatestorage', location='/home/rudolf/Documents/code/crate/working/crateweb/crate_filestorage'), blank=True),
        ),
    ]
