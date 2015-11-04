# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consent', '0012_auto_20151025_2203'),
    ]

    operations = [
        migrations.CreateModel(
            name='CharityPaymentRecord',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created_when', models.DateTimeField(verbose_name='When created (UTC)', auto_now_add=True)),
                ('payee', models.CharField(max_length=255)),
                ('amount', models.DecimalField(max_digits=8, decimal_places=2)),
            ],
        ),
        migrations.DeleteModel(
            name='CharityPayment',
        ),
    ]
