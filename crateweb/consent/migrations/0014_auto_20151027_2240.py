# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consent', '0013_auto_20151025_2205'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClinicianResponse',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, primary_key=True, auto_created=True)),
                ('created_when', models.DateTimeField(verbose_name='When created (UTC)', auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='ContactRequest',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, primary_key=True, auto_created=True)),
                ('created_when', models.DateTimeField(verbose_name='When created (UTC)', auto_now_add=True)),
                ('nhs_number', models.BigIntegerField(verbose_name='NHS number', null=True)),
                ('trid', models.BigIntegerField(verbose_name='Transient research ID', null=True)),
                ('rid', models.CharField(verbose_name='Research ID', null=True, max_length=128)),
                ('mrid', models.CharField(verbose_name='Master research ID', null=True, max_length=128)),
                ('consentmode', models.ForeignKey(to='consent.ConsentMode')),
                ('patientlookup', models.ForeignKey(to='consent.PatientLookup')),
                ('study', models.ForeignKey(to='consent.Study')),
            ],
        ),
        migrations.AddField(
            model_name='clinicianresponse',
            name='contactrequest',
            field=models.ForeignKey(to='consent.ContactRequest'),
        ),
    ]
