# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings
import django.core.files.storage
import consent.models
import core.extra


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ConsentMode',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('decision_signed_by_patient', models.BooleanField(verbose_name='Request signed by patient?')),
                ('decision_under16_signed_by_parent', models.BooleanField(verbose_name='Patient under 16 and request countersigned by parent?')),
                ('decision_under16_signed_by_clinician', models.BooleanField(verbose_name='Patient under 16 and request countersigned by clinician?')),
                ('decision_lack_capacity_signed_by_representative', models.BooleanField(verbose_name='Patient lacked capacity and request signed by authorized representative?')),
                ('decision_lack_capacity_signed_by_clinician', models.BooleanField(verbose_name='Patient lacked capacity and request countersigned by clinician?')),
                ('exclude_entirely', models.BooleanField(verbose_name='Exclude patient from Research Database entirely?')),
                ('consent_mode', models.CharField(default='', max_length=10, choices=[('red', 'red'), ('yellow', 'yellow'), ('green', 'green')], verbose_name="Consent mode ('red', 'yellow', 'green')")),
                ('consent_after_discharge', models.BooleanField(verbose_name='Consent given to contact patient after discharge?')),
                ('max_approaches_per_year', models.PositiveSmallIntegerField(default=0, verbose_name='Maximum number of approaches permissible per year (0 = no limit)')),
                ('other_requests', models.TextField(blank=True, verbose_name='Other special requests by patient')),
                ('prefers_email', models.BooleanField(verbose_name='Patient prefers e-mail contact?')),
                ('changed_by_clinician_override', models.BooleanField(verbose_name="Consent mode changed by clinician's override?")),
                ('created_when', models.DateTimeField(auto_now_add=True, verbose_name='When was this record created (UTC)?')),
                ('created_by_user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'get_latest_by': 'created_when',
            },
        ),
        migrations.CreateModel(
            name='Email',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created_when', models.DateTimeField(auto_now_add=True, verbose_name='When created (UTC)')),
                ('sender', models.CharField(default='CPFT Research Database - DO NOT REPLY <noreply@cpft.nhs.uk>', max_length=255)),
                ('recipient', models.CharField(max_length=255)),
                ('subject', models.CharField(max_length=255)),
                ('msg_text', models.TextField()),
                ('msg_html', models.TextField()),
                ('source_db', models.CharField(max_length=255, verbose_name='Source database in use when e-mail created')),
                ('sent', models.BooleanField(default=False)),
                ('sent_when', models.DateTimeField(verbose_name='When sent (UTC)', null=True)),
                ('failure_reason', models.TextField(verbose_name='Reason sending failed')),
            ],
        ),
        migrations.CreateModel(
            name='EmailAttachment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('file', models.FileField(upload_to='', storage=django.core.files.storage.FileSystemStorage(location='/srv/crate_filestorage', base_url='/privatestorage'))),
                ('sent_filename', models.CharField(max_length=255, null=True)),
                ('content_type', models.CharField(max_length=255, null=True)),
                ('email', models.ForeignKey(to='consent.Email')),
            ],
        ),
        migrations.CreateModel(
            name='Patient',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('nhs_number', models.BigIntegerField(verbose_name='NHS number')),
            ],
        ),
        migrations.CreateModel(
            name='Study',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('institutional_id', models.PositiveIntegerField(unique=True, verbose_name='Institutional (e.g. NHS Trust) study number')),
                ('title', models.CharField(max_length=255, verbose_name='Study title')),
                ('registered_when', models.DateTimeField(blank=True, verbose_name='When was the study registered?', null=True)),
                ('summary', models.TextField(verbose_name='Summary of study')),
                ('search_methods_planned', models.TextField(verbose_name='Search methods planned')),
                ('patient_contact', models.BooleanField(verbose_name='Involves patient contact?')),
                ('include_under_16s', models.BooleanField(verbose_name='Include patients under 16?')),
                ('include_lack_capacity', models.BooleanField(verbose_name='Include patients lacking capacity?')),
                ('clinical_trial', models.BooleanField(verbose_name='Clinical trial (CTIMP)?')),
                ('include_discharged', models.BooleanField(verbose_name='Include discharged patients?')),
                ('request_direct_approach', models.BooleanField(verbose_name='Researchers request direct approach to patients?')),
                ('approved_by_rec', models.BooleanField(verbose_name='Approved by REC?')),
                ('rec_reference', models.CharField(max_length=50, verbose_name='Research Ethics Committee reference')),
                ('approved_locally', models.BooleanField(verbose_name='Approved by local institution?')),
                ('local_approval_when', models.DateTimeField(blank=True, verbose_name='When approved by local institution?', null=True)),
                ('study_details_pdf', core.extra.ContentTypeRestrictedFileField(blank=True, upload_to=consent.models.study_details_upload_to, storage=django.core.files.storage.FileSystemStorage(location='/srv/crate_filestorage', base_url='/privatestorage'))),
                ('subject_form_template_pdf', core.extra.ContentTypeRestrictedFileField(blank=True, upload_to=consent.models.study_form_upload_to, storage=django.core.files.storage.FileSystemStorage(location='/srv/crate_filestorage', base_url='/privatestorage'))),
                ('lead_researcher', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name_plural': 'studies',
            },
        ),
        migrations.AddField(
            model_name='consentmode',
            name='patient',
            field=models.ForeignKey(to='consent.Patient'),
        ),
    ]
