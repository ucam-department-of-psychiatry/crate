# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings
import django.core.files.storage


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('consent', '0015_auto_20151027_2319'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClinicianToken',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, primary_key=True, auto_created=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='When created (UTC)')),
                ('used_at', models.DateTimeField(verbose_name='When used (UTC)', null=True)),
                ('token', models.CharField(max_length=20)),
            ],
        ),
        migrations.CreateModel(
            name='Letter',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, primary_key=True, auto_created=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='When created (UTC)')),
                ('pdf', models.FileField(upload_to='', storage=django.core.files.storage.FileSystemStorage(base_url='/privatestorage', location='/home/rudolf/Documents/code/crate/working/crateweb/crate_filestorage'))),
                ('to_clinician', models.BooleanField(default=False)),
                ('to_researcher', models.BooleanField(default=False)),
                ('to_patient', models.BooleanField(default=False)),
            ],
        ),
        migrations.CreateModel(
            name='LetterPrinted',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, primary_key=True, auto_created=True)),
                ('printed_at', models.DateTimeField(auto_now_add=True, verbose_name='When printed (UTC)')),
                ('letter', models.ForeignKey(to='consent.Letter')),
            ],
        ),
        migrations.RenameField(
            model_name='charitypaymentrecord',
            old_name='created_when',
            new_name='created_at',
        ),
        migrations.RenameField(
            model_name='clinicianresponse',
            old_name='created_when',
            new_name='created_at',
        ),
        migrations.RenameField(
            model_name='consentmode',
            old_name='created_when',
            new_name='created_at',
        ),
        migrations.RenameField(
            model_name='contactrequest',
            old_name='consentmode',
            new_name='consent_mode',
        ),
        migrations.RenameField(
            model_name='contactrequest',
            old_name='created_when',
            new_name='created_at',
        ),
        migrations.RenameField(
            model_name='contactrequest',
            old_name='patientlookup',
            new_name='patient_lookup',
        ),
        migrations.RenameField(
            model_name='email',
            old_name='created_when',
            new_name='created_at',
        ),
        migrations.RenameField(
            model_name='email',
            old_name='sent_when',
            new_name='sent_at',
        ),
        migrations.RenameField(
            model_name='patientlookup',
            old_name='lookup_when',
            new_name='lookup_at',
        ),
        migrations.RenameField(
            model_name='patientresponse',
            old_name='created_when',
            new_name='created_at',
        ),
        migrations.RenameField(
            model_name='study',
            old_name='local_approval_when',
            new_name='local_approval_at',
        ),
        migrations.RenameField(
            model_name='study',
            old_name='registered_when',
            new_name='registered_at',
        ),
        migrations.RemoveField(
            model_name='clinicianresponse',
            name='contactrequest',
        ),
        migrations.RemoveField(
            model_name='contactrequest',
            name='mrid',
        ),
        migrations.RemoveField(
            model_name='contactrequest',
            name='rid',
        ),
        migrations.RemoveField(
            model_name='contactrequest',
            name='trid',
        ),
        migrations.RemoveField(
            model_name='patientresponse',
            name='contactrequest',
        ),
        migrations.AddField(
            model_name='clinicianresponse',
            name='clinician_confirm_name',
            field=models.CharField(verbose_name='Type your name to confirm', max_length=255, default=''),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='clinicianresponse',
            name='contact_request',
            field=models.OneToOneField(related_name='clinician_response', to='consent.ContactRequest', default=None),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='clinicianresponse',
            name='ineligible_reason',
            field=models.TextField(verbose_name='Reason patient is ineligible', blank=True),
        ),
        migrations.AddField(
            model_name='clinicianresponse',
            name='pt_uncontactable_reason',
            field=models.TextField(verbose_name='Reason patient is not contactable', blank=True),
        ),
        migrations.AddField(
            model_name='clinicianresponse',
            name='response',
            field=models.CharField(max_length=1, default='', choices=[('A', 'A: I will pass the request to the patient'), ('B', 'B: I veto on clinical grounds'), ('C', 'C: Patient is definitely ineligible'), ('D', 'D: Patient is dead/discharged or details are defunct')]),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='clinicianresponse',
            name='response_route',
            field=models.CharField(max_length=1, default='', choices=[('e', 'E-mail'), ('w', 'Web')]),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='clinicianresponse',
            name='veto_reason',
            field=models.TextField(verbose_name='Reason for clinical veto', blank=True),
        ),
        migrations.AddField(
            model_name='contactrequest',
            name='approaches_in_past_year',
            field=models.PositiveIntegerField(default=0),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='contactrequest',
            name='clinician_involvement',
            field=models.PositiveSmallIntegerField(null=True),
        ),
        migrations.AddField(
            model_name='contactrequest',
            name='decided_no_action',
            field=models.BooleanField(default=False),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='contactrequest',
            name='decided_send_to_clinician',
            field=models.BooleanField(default=False),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='contactrequest',
            name='decided_send_to_researcher',
            field=models.BooleanField(default=False),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='contactrequest',
            name='decisions',
            field=models.TextField(verbose_name='Decisions made', blank=True),
        ),
        migrations.AddField(
            model_name='contactrequest',
            name='lookup_mrid',
            field=models.CharField(verbose_name='Master research ID used for lookup', null=True, max_length=128),
        ),
        migrations.AddField(
            model_name='contactrequest',
            name='lookup_nhs_number',
            field=models.BigIntegerField(verbose_name='NHS number used for lookup', null=True),
        ),
        migrations.AddField(
            model_name='contactrequest',
            name='lookup_rid',
            field=models.CharField(verbose_name='Research ID used for lookup', null=True, max_length=128),
        ),
        migrations.AddField(
            model_name='contactrequest',
            name='lookup_trid',
            field=models.BigIntegerField(verbose_name='Transient research ID used for lookup', null=True),
        ),
        migrations.AddField(
            model_name='contactrequest',
            name='request_by',
            field=models.ForeignKey(default=None, to=settings.AUTH_USER_MODEL),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='contactrequest',
            name='request_direct_approach',
            field=models.BooleanField(verbose_name='Request direct contact with patient if available (not contact with clinician first)', default=False),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='dummypatientsourceinfo',
            name='pt_local_id_description',
            field=models.CharField(verbose_name='Description of database-specific ID', max_length=100, blank=True),
        ),
        migrations.AddField(
            model_name='dummypatientsourceinfo',
            name='pt_local_id_number',
            field=models.BigIntegerField(verbose_name='Database-specific ID', null=True, blank=True),
        ),
        migrations.AddField(
            model_name='email',
            name='to_clinician',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='email',
            name='to_patient',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='email',
            name='to_researcher',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='patientlookup',
            name='pt_local_id_description',
            field=models.CharField(verbose_name='Description of database-specific ID', max_length=100, blank=True),
        ),
        migrations.AddField(
            model_name='patientlookup',
            name='pt_local_id_number',
            field=models.BigIntegerField(verbose_name='Database-specific ID', null=True, blank=True),
        ),
        migrations.AddField(
            model_name='patientresponse',
            name='contact_request',
            field=models.OneToOneField(to='consent.ContactRequest', default=None),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='cliniciantoken',
            name='clinician_response',
            field=models.OneToOneField(to='consent.ClinicianResponse'),
        ),
        migrations.AddField(
            model_name='cliniciantoken',
            name='contact_request',
            field=models.OneToOneField(to='consent.ContactRequest'),
        ),
    ]
