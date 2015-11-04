#!/usr/bin/env python3
# consent/forms.py

import logging
logger = logging.getLogger(__name__)
from django import forms
from django.conf import settings
from django.db.models import Q
from core.nhs import is_valid_nhs_number
from core.extra import (
    MultipleNhsNumberAreaField,
    MultipleWordAreaField,
    SingleNhsNumberField,
)
from .models import (
    # ContactRequest,
    Study,
)


class SingleNhsNumberForm(forms.Form):
    nhs_number = SingleNhsNumberField(label="NHS number")


class SuperuserSubmitContactRequestForm(forms.Form):
    study = forms.ModelChoiceField(
        queryset=Study.objects\
            .filter(patient_contact=True)\
            .exclude(study_details_pdf='')
    )
    request_direct_approach = forms.BooleanField(
        label="Request direct approach to patient, if available",
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


class ResearcherSubmitContactRequestForm(forms.Form):
    study = forms.ModelChoiceField(queryset=Study.objects.all())
    request_direct_approach = forms.BooleanField(
        label="Request direct approach to patient, if available",
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
        self.fields['study'].queryset = Study.objects\
            .filter(patient_contact=True)\
            .exclude(study_details_pdf='')\
            .filter(Q(lead_researcher=user) | Q(researchers__in=[user])
            .distinct()
        )
        # https://docs.djangoproject.com/en/1.8/ref/models/querysets/#field-lookups  # noqa
        # http://stackoverflow.com/questions/5329586/django-modelchoicefield-filtering-query-set-and-setting-default-value-as-an-obj  # noqa
