# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('consent', '0011_auto_20151022_2219'),
    ]

    operations = [
        migrations.CreateModel(
            name='CharityPayment',
            fields=[
                ('id', models.AutoField(auto_created=True, verbose_name='ID', primary_key=True, serialize=False)),
                ('created_when', models.DateTimeField(auto_now_add=True, verbose_name='When created (UTC)')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=8)),
            ],
        ),
        migrations.AlterField(
            model_name='teamrep',
            name='team',
            field=models.CharField(choices=[('dummy_team_one', 'dummy_team_one'), ('dummy_team_two', 'dummy_team_two'), ('dummy_team_three', 'dummy_team_three')], max_length=100, unique=True, verbose_name='Team description'),
        ),
    ]
