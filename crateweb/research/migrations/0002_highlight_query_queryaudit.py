# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings
import picklefield.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('research', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Highlight',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('colour', models.PositiveSmallIntegerField(verbose_name='Colour number')),
                ('text', models.CharField(max_length=255, verbose_name='Text to highlight')),
                ('active', models.BooleanField(default=True)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Query',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('sql', models.TextField(verbose_name='SQL query')),
                ('args', picklefield.fields.PickledObjectField(verbose_name='Pickled arguments', null=True, editable=False)),
                ('raw', models.BooleanField(verbose_name='SQL is raw, not parameter-substituted', default=False)),
                ('qmark', models.BooleanField(verbose_name='Parameter-substituted SQL uses ?, not %s, as placeholders', default=True)),
                ('active', models.BooleanField(default=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('deleted', models.BooleanField(verbose_name="Deleted from the user's perspective. Audited queries are never properly deleted.", default=False)),
                ('audited', models.BooleanField(default=False)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='QueryAudit',
            fields=[
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('when', models.DateTimeField(auto_now_add=True)),
                ('count_only', models.BooleanField(default=False)),
                ('n_records', models.PositiveIntegerField(default=0)),
                ('failed', models.BooleanField(default=False)),
                ('fail_msg', models.TextField()),
                ('query', models.ForeignKey(to='research.Query')),
            ],
        ),
    ]
