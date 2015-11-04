# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import core.extra
import consent.models
import django.core.files.storage


class Migration(migrations.Migration):

    dependencies = [
        ('consent', '0006_auto_20151022_1547'),
    ]

    operations = [
        migrations.CreateModel(
            name='Leaflet',
            fields=[
                ('id', models.AutoField(serialize=False, verbose_name='ID', primary_key=True, auto_created=True)),
                ('name', models.CharField(verbose_name='leaflet name', choices=[('cpft_tpir', 'CPFT: Taking part in research'), ('nihr_yhrsl', 'NIHR: Your health records save lives'), ('cpft_trafficlight_choice', 'CPFT: traffic-light choice'), ('cpft_clinres', 'CPFT: clinical research')], max_length=50, unique=True)),
                ('pdf', core.extra.ContentTypeRestrictedFileField(storage=django.core.files.storage.FileSystemStorage(location='/home/rudolf/Documents/code/crate/working/crateweb/crate_filestorage', base_url='/privatestorage'), upload_to=consent.models.study_details_upload_to, blank=True)),
            ],
        ),
    ]
