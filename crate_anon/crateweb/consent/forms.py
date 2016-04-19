#!/usr/bin/env python3
# crate_anon/crateweb/consent/forms.py

import logging
from django import forms
from django.conf import settings
from django.db.models import Q
from crate_anon.crateweb.extra.forms import (
    MultipleNhsNumberAreaField,
    MultipleWordAreaField,
    SingleNhsNumberField,
)
from crate_anon.crateweb.consent.models import (
    ClinicianResponse,
    Study,
)

logger = logging.getLogger(__name__)


class SingleNhsNumberForm(forms.Form):
    nhs_number = SingleNhsNumberField(label="NHS number")


def get_queryset_possible_contact_studies():
    return (
        Study.objects
        .filter(patient_contact=True)
        .filter(approved_by_rec=True)
        .filter(approved_locally=True)
        .exclude(study_details_pdf='')
        .exclude(lead_researcher__profile__title='')
        .exclude(lead_researcher__first_name='')
        .exclude(lead_researcher__last_name='')
    )


class AbstractContactRequestForm(forms.Form):
    def clean(self):
        cleaned_data = super().clean()
        study = cleaned_data.get("study")
        request_direct_approach = cleaned_data.get("request_direct_approach")

        if request_direct_approach and not study.request_direct_approach:
            raise forms.ValidationError(
                "Study not approved for direct approach.")


class SuperuserSubmitContactRequestForm(AbstractContactRequestForm):
    study = forms.ModelChoiceField(
        queryset=get_queryset_possible_contact_studies())
    request_direct_approach = forms.BooleanField(
        label="Request direct approach to patient, if available "
              "(UNTICK to ask clinician for additional info)",
        required=False,
        initial=True)
    nhs_numbers = MultipleNhsNumberAreaField(label='NHS numbers',
                                             required=False)
    rids = MultipleWordAreaField(
        label='{} (RID)'.format(settings.SECRET_MAP['RID_FIELD']),
        required=False)
    mrids = MultipleWordAreaField(
        label='{} (MRID)'.format(settings.SECRET_MAP['MASTER_RID_FIELD']),
        required=False)


class ResearcherSubmitContactRequestForm(AbstractContactRequestForm):
    study = forms.ModelChoiceField(queryset=Study.objects.all())
    request_direct_approach = forms.BooleanField(
        label="Request direct approach to patient, if available "
              "(UNTICK to ask clinician for additional info)",
        required=False,
        initial=True)
    rids = MultipleWordAreaField(
        label='{} (RID)'.format(settings.SECRET_MAP['RID_FIELD']),
        required=False)
    mrids = MultipleWordAreaField(
        label='{} (MRID)'.format(settings.SECRET_MAP['MASTER_RID_FIELD']),
        required=False)

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['study'].queryset = (
            get_queryset_possible_contact_studies()
            .filter(Q(lead_researcher=user) | Q(researchers__in=[user]))
            .distinct()
        )
        # https://docs.djangoproject.com/en/1.8/ref/models/querysets/#field-lookups  # noqa
        # http://stackoverflow.com/questions/5329586/django-modelchoicefield-filtering-query-set-and-setting-default-value-as-an-obj  # noqa


class ClinicianResponseForm(forms.ModelForm):
    class Meta:
        model = ClinicianResponse
        fields = [
            'token',
            'email_choice',
            'response',
            'veto_reason',
            'ineligible_reason',
            'pt_uncontactable_reason',
            'clinician_confirm_name',
        ]
        widgets = {
            'token': forms.HiddenInput(),
            'email_choice': forms.HiddenInput(),
        }
