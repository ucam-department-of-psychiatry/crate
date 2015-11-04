# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('consent', '0014_auto_20151027_2240'),
    ]

    operations = [
        migrations.CreateModel(
            name='PatientResponse',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True, verbose_name='ID', auto_created=True)),
                ('decision_signed_by_patient', models.BooleanField(verbose_name='Request signed by patient?')),
                ('decision_under16_signed_by_parent', models.BooleanField(verbose_name='Patient under 16 and request countersigned by parent?')),
                ('decision_under16_signed_by_clinician', models.BooleanField(verbose_name='Patient under 16 and request countersigned by clinician?')),
                ('decision_lack_capacity_signed_by_representative', models.BooleanField(verbose_name='Patient lacked capacity and request signed by authorized representative?')),
                ('decision_lack_capacity_signed_by_clinician', models.BooleanField(verbose_name='Patient lacked capacity and request countersigned by clinician?')),
                ('created_when', models.DateTimeField(verbose_name='When created (UTC)', auto_now_add=True)),
                ('contactrequest', models.ForeignKey(to='consent.ContactRequest')),
                ('created_by', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='clinicianresponse',
            name='charity_amount_due',
            field=models.DecimalField(default=1.0, decimal_places=2, max_digits=8),
        ),
    ]
