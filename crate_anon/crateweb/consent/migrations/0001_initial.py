#!/usr/bin/env python

"""
crate_anon/crateweb/consent/migrations/0001_initial.py

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

    This file is part of CRATE.

    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.

===============================================================================

**Consent app, migration 0001.**

"""

from __future__ import unicode_literals

from cardinal_pythonlib.django.fields.restrictedcontentfile import ContentTypeRestrictedFileField  # noqa
from django.db import migrations, models
from django.conf import settings
import crate_anon.crateweb.consent.models as consent_models
import crate_anon.crateweb.consent.storage as consent_storage

# !!! warning !!! some fields hard-code a local file path in /home/rudolf/...
# ... edited; no default is OK here; see
# https://docs.djangoproject.com/en/1.9/ref/files/storage/#the-filesystemstorage-class  # noqa


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CharityPaymentRecord',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, primary_key=True, verbose_name='ID')),  # noqa
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='When created')),  # noqa
                ('payee', models.CharField(max_length=255)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=8)),  # noqa
            ],
        ),
        migrations.CreateModel(
            name='ClinicianResponse',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, primary_key=True, verbose_name='ID')),  # noqa
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='When created')),  # noqa
                ('token', models.CharField(max_length=20)),
                ('responded', models.BooleanField(default=False, verbose_name='Responded?')),  # noqa
                ('responded_at', models.DateTimeField(null=True, verbose_name='When responded')),  # noqa
                ('response_route', models.CharField(choices=[('e', 'E-mail'), ('w', 'Web')], max_length=1)),  # noqa
                ('email_choice', models.CharField(choices=[('y', 'Yes'), ('n', 'No'), ('more', 'Tell me more')], max_length=4)),  # noqa
                ('response', models.CharField(choices=[('R', 'R: Clinician asks RDBM to pass request to patient'), ('A', 'A: Clinician will pass the request to the patient'), ('B', 'B: Clinician vetoes on clinical grounds'), ('C', 'C: Patient is definitely ineligible'), ('D', 'D: Patient is dead/discharged or details are defunct')], max_length=1)),  # noqa
                ('veto_reason', models.TextField(blank=True, verbose_name='Reason for clinical veto')),  # noqa
                ('ineligible_reason', models.TextField(blank=True, verbose_name='Reason patient is ineligible')),  # noqa
                ('pt_uncontactable_reason', models.TextField(blank=True, verbose_name='Reason patient is not contactable')),  # noqa
                ('clinician_confirm_name', models.CharField(verbose_name='Type your name to confirm', max_length=255)),  # noqa
                ('charity_amount_due', models.DecimalField(default=0, decimal_places=2, max_digits=8)),  # noqa
            ],
        ),
        migrations.CreateModel(
            name='ConsentMode',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, primary_key=True, verbose_name='ID')),  # noqa
                ('decision_signed_by_patient', models.BooleanField(default=False, verbose_name='Request signed by patient?')),  # noqa
                ('decision_otherwise_directly_authorized_by_patient', models.BooleanField(default=False, verbose_name='Request otherwise directly authorized by patient?')),  # noqa
                ('decision_under16_signed_by_parent', models.BooleanField(default=False, verbose_name='Patient under 16 and request countersigned by parent?')),  # noqa
                ('decision_under16_signed_by_clinician', models.BooleanField(default=False, verbose_name='Patient under 16 and request countersigned by clinician?')),  # noqa
                ('decision_lack_capacity_signed_by_representative', models.BooleanField(default=False, verbose_name='Patient lacked capacity and request signed by authorized representative?')),  # noqa
                ('decision_lack_capacity_signed_by_clinician', models.BooleanField(default=False, verbose_name='Patient lacked capacity and request countersigned by clinician?')),  # noqa
                ('nhs_number', models.BigIntegerField(verbose_name='NHS number')),  # noqa
                ('current', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='When was this record created?')),  # noqa
                ('exclude_entirely', models.BooleanField(default=False, verbose_name='Exclude patient from Research Database entirely?')),  # noqa
                ('consent_mode', models.CharField(default='', choices=[('red', 'red'), ('yellow', 'yellow'), ('green', 'green')], verbose_name="Consent mode ('red', 'yellow', 'green')", max_length=10)),  # noqa
                ('consent_after_discharge', models.BooleanField(default=False, verbose_name='Consent given to contact patient after discharge?')),  # noqa
                ('max_approaches_per_year', models.PositiveSmallIntegerField(default=0, verbose_name='Maximum number of approaches permissible per year (0 = no limit)')),  # noqa
                ('other_requests', models.TextField(blank=True, verbose_name='Other special requests by patient')),  # noqa
                ('prefers_email', models.BooleanField(default=False, verbose_name='Patient prefers e-mail contact?')),  # noqa
                ('changed_by_clinician_override', models.BooleanField(default=False, verbose_name="Consent mode changed by clinician's override?")),  # noqa
                ('created_by', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.PROTECT)),  # noqa
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='ContactRequest',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, primary_key=True, verbose_name='ID')),  # noqa
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='When created')),  # noqa
                ('request_direct_approach', models.BooleanField(verbose_name='Request direct contact with patient if available (not contact with clinician first)')),  # noqa
                ('lookup_nhs_number', models.BigIntegerField(null=True, verbose_name='NHS number used for lookup')),  # noqa
                ('lookup_rid', models.CharField(verbose_name='Research ID used for lookup', null=True, max_length=128)),  # noqa
                ('lookup_mrid', models.CharField(verbose_name='Master research ID used for lookup', null=True, max_length=128)),  # noqa
                ('processed', models.BooleanField(default=False)),
                ('nhs_number', models.BigIntegerField(null=True, verbose_name='NHS number')),  # noqa
                ('approaches_in_past_year', models.PositiveIntegerField(null=True)),  # noqa
                ('decisions', models.TextField(blank=True, verbose_name='Decisions made')),  # noqa
                ('decided_no_action', models.BooleanField(default=False)),
                ('decided_send_to_researcher', models.BooleanField(default=False)),  # noqa
                ('decided_send_to_clinician', models.BooleanField(default=False)),  # noqa
                ('clinician_involvement', models.PositiveSmallIntegerField(choices=[(0, 'No clinician involvement required or requested'), (1, 'Clinician involvement requested by researchers'), (2, 'Clinician involvement required by YELLOW consent mode'), (3, 'Clinician involvement required by UNKNOWN consent mode')], null=True)),  # noqa
                ('consent_withdrawn', models.BooleanField(default=False)),
                ('consent_withdrawn_at', models.DateTimeField(null=True, verbose_name='When consent withdrawn')),  # noqa
                ('consent_mode', models.ForeignKey(to='consent.ConsentMode', on_delete=models.SET_NULL, null=True)),  # noqa
            ],
        ),
        migrations.CreateModel(
            name='DummyPatientSourceInfo',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, primary_key=True, verbose_name='ID')),  # noqa
                ('pt_local_id_description', models.CharField(blank=True, verbose_name='Description of database-specific ID', max_length=100)),  # noqa
                ('pt_local_id_number', models.BigIntegerField(blank=True, null=True, verbose_name='Database-specific ID')),  # noqa
                ('pt_dob', models.DateField(blank=True, null=True, verbose_name='Patient date of birth')),  # noqa
                ('pt_dod', models.DateField(blank=True, null=True, verbose_name='Patient date of death (NULL if alive)')),  # noqa
                ('pt_dead', models.BooleanField(default=False, verbose_name='Patient is dead')),  # noqa
                ('pt_discharged', models.NullBooleanField(verbose_name='Patient discharged')),  # noqa
                ('pt_sex', models.CharField(choices=[('M', 'Male'), ('F', 'Female'), ('X', 'Inderminate/intersex'), ('?', 'Unknown')], blank=True, verbose_name='Patient sex', max_length=1)),  # noqa
                ('pt_title', models.CharField(blank=True, verbose_name='Patient title', max_length=20)),  # noqa
                ('pt_first_name', models.CharField(blank=True, verbose_name='Patient first name', max_length=100)),  # noqa
                ('pt_last_name', models.CharField(blank=True, verbose_name='Patient last name', max_length=100)),  # noqa
                ('pt_address_1', models.CharField(blank=True, verbose_name='Patient address line 1', max_length=100)),  # noqa
                ('pt_address_2', models.CharField(blank=True, verbose_name='Patient address line 2', max_length=100)),  # noqa
                ('pt_address_3', models.CharField(blank=True, verbose_name='Patient address line 3', max_length=100)),  # noqa
                ('pt_address_4', models.CharField(blank=True, verbose_name='Patient address line 4', max_length=100)),  # noqa
                ('pt_address_5', models.CharField(blank=True, verbose_name='Patient address line 5 (county)', max_length=100)),  # noqa
                ('pt_address_6', models.CharField(blank=True, verbose_name='Patient address line 6 (postcode)', max_length=100)),  # noqa
                ('pt_address_7', models.CharField(blank=True, verbose_name='Patient address line 7 (country)', max_length=100)),  # noqa
                ('pt_telephone', models.CharField(blank=True, verbose_name='Patient telephone', max_length=20)),  # noqa
                ('pt_email', models.EmailField(blank=True, verbose_name='Patient email', max_length=254)),  # noqa
                ('gp_title', models.CharField(blank=True, verbose_name='GP title', max_length=20)),  # noqa
                ('gp_first_name', models.CharField(blank=True, verbose_name='GP first name', max_length=100)),  # noqa
                ('gp_last_name', models.CharField(blank=True, verbose_name='GP last name', max_length=100)),  # noqa
                ('gp_address_1', models.CharField(blank=True, verbose_name='GP address line 1', max_length=100)),  # noqa
                ('gp_address_2', models.CharField(blank=True, verbose_name='GP address line 2', max_length=100)),  # noqa
                ('gp_address_3', models.CharField(blank=True, verbose_name='GP address line 3', max_length=100)),  # noqa
                ('gp_address_4', models.CharField(blank=True, verbose_name='GP address line 4', max_length=100)),  # noqa
                ('gp_address_5', models.CharField(blank=True, verbose_name='GP address line 5 (county)', max_length=100)),  # noqa
                ('gp_address_6', models.CharField(blank=True, verbose_name='GP address line 6 (postcode)', max_length=100)),  # noqa
                ('gp_address_7', models.CharField(blank=True, verbose_name='GP address line 7 (country)', max_length=100)),  # noqa
                ('gp_telephone', models.CharField(blank=True, verbose_name='GP telephone', max_length=20)),  # noqa
                ('gp_email', models.EmailField(blank=True, verbose_name='GP email', max_length=254)),  # noqa
                ('clinician_title', models.CharField(blank=True, verbose_name='Clinician title', max_length=20)),  # noqa
                ('clinician_first_name', models.CharField(blank=True, verbose_name='Clinician first name', max_length=100)),  # noqa
                ('clinician_last_name', models.CharField(blank=True, verbose_name='Clinician last name', max_length=100)),  # noqa
                ('clinician_address_1', models.CharField(blank=True, verbose_name='Clinician address line 1', max_length=100)),  # noqa
                ('clinician_address_2', models.CharField(blank=True, verbose_name='Clinician address line 2', max_length=100)),  # noqa
                ('clinician_address_3', models.CharField(blank=True, verbose_name='Clinician address line 3', max_length=100)),  # noqa
                ('clinician_address_4', models.CharField(blank=True, verbose_name='Clinician address line 4', max_length=100)),  # noqa
                ('clinician_address_5', models.CharField(blank=True, verbose_name='Clinician address line 5 (county)', max_length=100)),  # noqa
                ('clinician_address_6', models.CharField(blank=True, verbose_name='Clinician address line 6 (postcode)', max_length=100)),  # noqa
                ('clinician_address_7', models.CharField(blank=True, verbose_name='Clinician address line 7 (country)', max_length=100)),  # noqa
                ('clinician_telephone', models.CharField(blank=True, verbose_name='Clinician telephone', max_length=20)),  # noqa
                ('clinician_email', models.EmailField(blank=True, verbose_name='Clinician email', max_length=254)),  # noqa
                ('clinician_is_consultant', models.BooleanField(default=False, verbose_name='Clinician is a consultant')),  # noqa
                ('clinician_signatory_title', models.CharField(blank=True, verbose_name="Clinician's title for signature (e.g. 'Consultant psychiatrist')", max_length=100)),  # noqa
                ('nhs_number', models.BigIntegerField(unique=True, verbose_name='NHS number')),  # noqa
            ],
            options={
                'verbose_name_plural': 'Dummy patient source information',
            },
        ),
        migrations.CreateModel(
            name='Email',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, primary_key=True, verbose_name='ID')),  # noqa
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='When created')),  # noqa
                ('sender', models.CharField(default='CPFT Research Database - DO NOT REPLY <noreply@cpft.nhs.uk>', max_length=255)),  # noqa
                ('recipient', models.CharField(max_length=255)),
                ('subject', models.CharField(max_length=255)),
                ('msg_text', models.TextField()),
                ('msg_html', models.TextField()),
                ('to_clinician', models.BooleanField(default=False)),
                ('to_researcher', models.BooleanField(default=False)),
                ('to_patient', models.BooleanField(default=False)),
                ('contact_request', models.ForeignKey(to='consent.ContactRequest', on_delete=models.PROTECT, null=True)),  # noqa
            ],
        ),
        migrations.CreateModel(
            name='EmailAttachment',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, primary_key=True, verbose_name='ID')),  # noqa
                ('file', models.FileField(upload_to='', storage=consent_storage.CustomFileSystemStorage(base_url='download_privatestorage'))),  # noqa
                ('sent_filename', models.CharField(null=True, max_length=255)),
                ('content_type', models.CharField(null=True, max_length=255)),
                ('owns_file', models.BooleanField(default=False)),
                ('email', models.ForeignKey(to='consent.Email', on_delete=models.PROTECT)),  # noqa
            ],
        ),
        migrations.CreateModel(
            name='EmailTransmission',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, primary_key=True, verbose_name='ID')),  # noqa
                ('at', models.DateTimeField(auto_now_add=True, verbose_name='When sent')),  # noqa
                ('sent', models.BooleanField(default=False)),
                ('failure_reason', models.TextField(verbose_name='Reason sending failed')),  # noqa
                ('by', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='emailtransmissions', null=True)),  # noqa
                ('email', models.ForeignKey(to='consent.Email', on_delete=models.PROTECT)),  # noqa
            ],
        ),
        migrations.CreateModel(
            name='Leaflet',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, primary_key=True, verbose_name='ID')),  # noqa
                ('name', models.CharField(choices=[('cpft_tpir', 'CPFT: Taking part in research'), ('nihr_yhrsl', 'NIHR: Your health records save lives'), ('cpft_trafficlight_choice', 'CPFT: traffic-light choice'), ('cpft_clinres', 'CPFT: clinical research')], verbose_name='leaflet name', unique=True, max_length=50)),  # noqa
                ('pdf', ContentTypeRestrictedFileField(upload_to=consent_models.leaflet_upload_to, blank=True, storage=consent_storage.CustomFileSystemStorage(base_url='download_privatestorage'))),  # noqa
            ],
        ),
        migrations.CreateModel(
            name='Letter',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, primary_key=True, verbose_name='ID')),  # noqa
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='When created')),  # noqa
                ('pdf', models.FileField(upload_to='', storage=consent_storage.CustomFileSystemStorage(base_url='download_privatestorage'))),  # noqa
                ('to_clinician', models.BooleanField(default=False)),
                ('to_researcher', models.BooleanField(default=False)),
                ('to_patient', models.BooleanField(default=False)),
                ('rdbm_may_view', models.BooleanField(default=False)),
                ('sent_manually_at', models.DateTimeField(null=True)),
                ('contact_request', models.ForeignKey(to='consent.ContactRequest', on_delete=models.PROTECT, null=True)),  # noqa
            ],
        ),
        migrations.CreateModel(
            name='PatientLookup',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, primary_key=True, verbose_name='ID')),  # noqa
                ('pt_local_id_description', models.CharField(blank=True, verbose_name='Description of database-specific ID', max_length=100)),  # noqa
                ('pt_local_id_number', models.BigIntegerField(blank=True, null=True, verbose_name='Database-specific ID')),  # noqa
                ('pt_dob', models.DateField(blank=True, null=True, verbose_name='Patient date of birth')),  # noqa
                ('pt_dod', models.DateField(blank=True, null=True, verbose_name='Patient date of death (NULL if alive)')),  # noqa
                ('pt_dead', models.BooleanField(default=False, verbose_name='Patient is dead')),  # noqa
                ('pt_discharged', models.NullBooleanField(verbose_name='Patient discharged')),  # noqa
                ('pt_sex', models.CharField(choices=[('M', 'Male'), ('F', 'Female'), ('X', 'Inderminate/intersex'), ('?', 'Unknown')], blank=True, verbose_name='Patient sex', max_length=1)),  # noqa
                ('pt_title', models.CharField(blank=True, verbose_name='Patient title', max_length=20)),  # noqa
                ('pt_first_name', models.CharField(blank=True, verbose_name='Patient first name', max_length=100)),  # noqa
                ('pt_last_name', models.CharField(blank=True, verbose_name='Patient last name', max_length=100)),  # noqa
                ('pt_address_1', models.CharField(blank=True, verbose_name='Patient address line 1', max_length=100)),  # noqa
                ('pt_address_2', models.CharField(blank=True, verbose_name='Patient address line 2', max_length=100)),  # noqa
                ('pt_address_3', models.CharField(blank=True, verbose_name='Patient address line 3', max_length=100)),  # noqa
                ('pt_address_4', models.CharField(blank=True, verbose_name='Patient address line 4', max_length=100)),  # noqa
                ('pt_address_5', models.CharField(blank=True, verbose_name='Patient address line 5 (county)', max_length=100)),  # noqa
                ('pt_address_6', models.CharField(blank=True, verbose_name='Patient address line 6 (postcode)', max_length=100)),  # noqa
                ('pt_address_7', models.CharField(blank=True, verbose_name='Patient address line 7 (country)', max_length=100)),  # noqa
                ('pt_telephone', models.CharField(blank=True, verbose_name='Patient telephone', max_length=20)),  # noqa
                ('pt_email', models.EmailField(blank=True, verbose_name='Patient email', max_length=254)),  # noqa
                ('gp_title', models.CharField(blank=True, verbose_name='GP title', max_length=20)),  # noqa
                ('gp_first_name', models.CharField(blank=True, verbose_name='GP first name', max_length=100)),  # noqa
                ('gp_last_name', models.CharField(blank=True, verbose_name='GP last name', max_length=100)),  # noqa
                ('gp_address_1', models.CharField(blank=True, verbose_name='GP address line 1', max_length=100)),  # noqa
                ('gp_address_2', models.CharField(blank=True, verbose_name='GP address line 2', max_length=100)),  # noqa
                ('gp_address_3', models.CharField(blank=True, verbose_name='GP address line 3', max_length=100)),  # noqa
                ('gp_address_4', models.CharField(blank=True, verbose_name='GP address line 4', max_length=100)),  # noqa
                ('gp_address_5', models.CharField(blank=True, verbose_name='GP address line 5 (county)', max_length=100)),  # noqa
                ('gp_address_6', models.CharField(blank=True, verbose_name='GP address line 6 (postcode)', max_length=100)),  # noqa
                ('gp_address_7', models.CharField(blank=True, verbose_name='GP address line 7 (country)', max_length=100)),  # noqa
                ('gp_telephone', models.CharField(blank=True, verbose_name='GP telephone', max_length=20)),  # noqa
                ('gp_email', models.EmailField(blank=True, verbose_name='GP email', max_length=254)),  # noqa
                ('clinician_title', models.CharField(blank=True, verbose_name='Clinician title', max_length=20)),  # noqa
                ('clinician_first_name', models.CharField(blank=True, verbose_name='Clinician first name', max_length=100)),  # noqa
                ('clinician_last_name', models.CharField(blank=True, verbose_name='Clinician last name', max_length=100)),  # noqa
                ('clinician_address_1', models.CharField(blank=True, verbose_name='Clinician address line 1', max_length=100)),  # noqa
                ('clinician_address_2', models.CharField(blank=True, verbose_name='Clinician address line 2', max_length=100)),  # noqa
                ('clinician_address_3', models.CharField(blank=True, verbose_name='Clinician address line 3', max_length=100)),  # noqa
                ('clinician_address_4', models.CharField(blank=True, verbose_name='Clinician address line 4', max_length=100)),  # noqa
                ('clinician_address_5', models.CharField(blank=True, verbose_name='Clinician address line 5 (county)', max_length=100)),  # noqa
                ('clinician_address_6', models.CharField(blank=True, verbose_name='Clinician address line 6 (postcode)', max_length=100)),  # noqa
                ('clinician_address_7', models.CharField(blank=True, verbose_name='Clinician address line 7 (country)', max_length=100)),  # noqa
                ('clinician_telephone', models.CharField(blank=True, verbose_name='Clinician telephone', max_length=20)),  # noqa
                ('clinician_email', models.EmailField(blank=True, verbose_name='Clinician email', max_length=254)),  # noqa
                ('clinician_is_consultant', models.BooleanField(default=False, verbose_name='Clinician is a consultant')),  # noqa
                ('clinician_signatory_title', models.CharField(blank=True, verbose_name="Clinician's title for signature (e.g. 'Consultant psychiatrist')", max_length=100)),  # noqa
                ('nhs_number', models.BigIntegerField(verbose_name='NHS number used for lookup')),  # noqa
                ('lookup_at', models.DateTimeField(auto_now_add=True, verbose_name='When fetched from clinical database')),  # noqa
                ('source_db', models.CharField(choices=[('dummy_clinical', 'Dummy clinical database for testing'), ('cpft_crs', 'CPFT Care Records System (CRS) 2005-2012'), ('cpft_rio', 'CPFT RiO 2013-')], verbose_name='Source database used for lookup', max_length=20)),  # noqa
                ('decisions', models.TextField(blank=True, verbose_name='Decisions made during lookup')),  # noqa
                ('secret_decisions', models.TextField(blank=True, verbose_name='Secret (identifying) decisions made during lookup')),  # noqa
                ('pt_found', models.BooleanField(default=False, verbose_name='Patient found')),  # noqa
                ('gp_found', models.BooleanField(default=False, verbose_name='GP found')),  # noqa
                ('clinician_found', models.BooleanField(default=False, verbose_name='Clinician found')),  # noqa
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='PatientResponse',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, primary_key=True, verbose_name='ID')),  # noqa
                ('decision_signed_by_patient', models.BooleanField(default=False, verbose_name='Request signed by patient?')),  # noqa
                ('decision_otherwise_directly_authorized_by_patient', models.BooleanField(default=False, verbose_name='Request otherwise directly authorized by patient?')),  # noqa
                ('decision_under16_signed_by_parent', models.BooleanField(default=False, verbose_name='Patient under 16 and request countersigned by parent?')),  # noqa
                ('decision_under16_signed_by_clinician', models.BooleanField(default=False, verbose_name='Patient under 16 and request countersigned by clinician?')),  # noqa
                ('decision_lack_capacity_signed_by_representative', models.BooleanField(default=False, verbose_name='Patient lacked capacity and request signed by authorized representative?')),  # noqa
                ('decision_lack_capacity_signed_by_clinician', models.BooleanField(default=False, verbose_name='Patient lacked capacity and request countersigned by clinician?')),  # noqa
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='When created')),  # noqa
                ('response', models.PositiveSmallIntegerField(choices=[(1, '1: Yes'), (2, '2: No')], null=True, verbose_name="Patient's response")),  # noqa
                ('contact_request', models.OneToOneField(to='consent.ContactRequest', on_delete=models.PROTECT, related_name='patient_response')),  # noqa
                ('recorded_by', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)),  # noqa
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='Study',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, primary_key=True, verbose_name='ID')),  # noqa
                ('institutional_id', models.PositiveIntegerField(unique=True, verbose_name='Institutional (e.g. NHS Trust) study number')),  # noqa
                ('title', models.CharField(verbose_name='Study title', max_length=255)),  # noqa
                ('registered_at', models.DateTimeField(blank=True, null=True, verbose_name='When was the study registered?')),  # noqa
                ('summary', models.TextField(verbose_name='Summary of study')),
                ('search_methods_planned', models.TextField(blank=True, verbose_name='Search methods planned')),  # noqa
                ('patient_contact', models.BooleanField(verbose_name='Involves patient contact?')),  # noqa
                ('include_under_16s', models.BooleanField(verbose_name='Include patients under 16?')),  # noqa
                ('include_lack_capacity', models.BooleanField(verbose_name='Include patients lacking capacity?')),  # noqa
                ('clinical_trial', models.BooleanField(verbose_name='Clinical trial (CTIMP)?')),  # noqa
                ('include_discharged', models.BooleanField(verbose_name='Include discharged patients?')),  # noqa
                ('request_direct_approach', models.BooleanField(verbose_name='Researchers request direct approach to patients?')),  # noqa
                ('approved_by_rec', models.BooleanField(verbose_name='Approved by REC?')),  # noqa
                ('rec_reference', models.CharField(blank=True, verbose_name='Research Ethics Committee reference', max_length=50)),  # noqa
                ('approved_locally', models.BooleanField(verbose_name='Approved by local institution?')),  # noqa
                ('local_approval_at', models.DateTimeField(blank=True, null=True, verbose_name='When approved by local institution?')),  # noqa
                ('study_details_pdf', ContentTypeRestrictedFileField(upload_to=consent_models.study_details_upload_to, blank=True, storage=consent_storage.CustomFileSystemStorage(base_url='download_privatestorage'))),  # noqa
                ('subject_form_template_pdf', ContentTypeRestrictedFileField(upload_to=consent_models.study_form_upload_to, blank=True, storage=consent_storage.CustomFileSystemStorage(base_url='download_privatestorage'))),  # noqa
                ('lead_researcher', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='studies_as_lead')),  # noqa
                ('researchers', models.ManyToManyField(to=settings.AUTH_USER_MODEL, blank=True, related_name='studies_as_researcher')),  # noqa
            ],
            options={
                'verbose_name_plural': 'studies',
            },
        ),
        migrations.CreateModel(
            name='TeamRep',
            fields=[
                ('id', models.AutoField(auto_created=True, serialize=False, primary_key=True, verbose_name='ID')),  # noqa
                ('team', models.CharField(choices=[('dummy_team_one', 'dummy_team_one'), ('dummy_team_two', 'dummy_team_two'), ('dummy_team_three', 'dummy_team_three')], verbose_name='Team description', unique=True, max_length=100)),  # noqa
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.CASCADE)),  # noqa
            ],
            options={
                'verbose_name_plural': 'clinical team representatives',
                'verbose_name': 'clinical team representative',
            },
        ),
        migrations.AddField(
            model_name='letter',
            name='study',
            field=models.ForeignKey(to='consent.Study', on_delete=models.PROTECT, null=True),  # noqa
        ),
        migrations.AddField(
            model_name='email',
            name='letter',
            field=models.ForeignKey(to='consent.Letter', on_delete=models.PROTECT, null=True),  # noqa
        ),
        migrations.AddField(
            model_name='email',
            name='study',
            field=models.ForeignKey(to='consent.Study', on_delete=models.PROTECT, null=True),  # noqa
        ),
        migrations.AddField(
            model_name='contactrequest',
            name='patient_lookup',
            field=models.ForeignKey(to='consent.PatientLookup', on_delete=models.SET_NULL, null=True),  # noqa
        ),
        migrations.AddField(
            model_name='contactrequest',
            name='request_by',
            field=models.ForeignKey(to=settings.AUTH_USER_MODEL, on_delete=models.PROTECT),  # noqa
        ),
        migrations.AddField(
            model_name='contactrequest',
            name='study',
            field=models.ForeignKey(to='consent.Study', on_delete=models.PROTECT),  # noqa
        ),
        migrations.AddField(
            model_name='clinicianresponse',
            name='contact_request',
            field=models.OneToOneField(to='consent.ContactRequest', on_delete=models.PROTECT, related_name='clinician_response'),  # noqa
        ),
    ]
