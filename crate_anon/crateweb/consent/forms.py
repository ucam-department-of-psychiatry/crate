#!/usr/bin/env python
# crate_anon/crateweb/consent/forms.py

"""
===============================================================================
    Copyright (C) 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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
"""

import logging

from cardinal_pythonlib.django.forms import (
    MultipleNhsNumberAreaField,
    MultipleWordAreaField,
    SingleNhsNumberField,
)
from django import forms
from django.conf import settings
from django.db.models import Q, QuerySet

from crate_anon.crateweb.consent.models import (
    ClinicianResponse,
    Study,
)
from crate_anon.crateweb.research.research_db_info import SingleResearchDatabase  # noqa

log = logging.getLogger(__name__)


class SingleNhsNumberForm(forms.Form):
    nhs_number = SingleNhsNumberField(label="NHS number")


def get_queryset_possible_contact_studies() -> QuerySet:
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
    def clean(self) -> None:
        cleaned_data = super().clean()

        study = cleaned_data.get("study")
        if not study:
            raise forms.ValidationError("Must specify study")

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
    rids = MultipleWordAreaField(required=False)
    mrids = MultipleWordAreaField(required=False)

    def __init__(self,
                 *args,
                 dbinfo: SingleResearchDatabase,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        rids = self.fields['rids']  # type: MultipleWordAreaField
        mrids = self.fields['mrids']  # type: MultipleWordAreaField

        rids.label = "{} ({}) (RID)".format(dbinfo.rid_field,
                                            dbinfo.rid_description)
        mrids.label = "{} ({}) (MRID)".format(dbinfo.mrid_field,
                                              dbinfo.mrid_description)


class ResearcherSubmitContactRequestForm(AbstractContactRequestForm):
    study = forms.ModelChoiceField(queryset=Study.objects.all())
    request_direct_approach = forms.BooleanField(
        label="Request direct approach to patient, if available "
              "(UNTICK to ask clinician for additional info)",
        required=False,
        initial=True)
    rids = MultipleWordAreaField(required=False)
    mrids = MultipleWordAreaField(required=False)

    def __init__(self,
                 *args,
                 user: settings.AUTH_USER_MODEL,
                 dbinfo: SingleResearchDatabase,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        study = self.fields['study']  # type: forms.ModelChoiceField
        rids = self.fields['rids']  # type: MultipleWordAreaField
        mrids = self.fields['mrids']  # type: MultipleWordAreaField

        study.queryset = (
            get_queryset_possible_contact_studies()
            .filter(Q(lead_researcher=user) | Q(researchers__in=[user]))
            .distinct()
        )
        # https://docs.djangoproject.com/en/1.8/ref/models/querysets/#field-lookups  # noqa
        # http://stackoverflow.com/questions/5329586/django-modelchoicefield-filtering-query-set-and-setting-default-value-as-an-obj  # noqa
        rids.label = "{} ({}) (RID)".format(dbinfo.rid_field,
                                            dbinfo.rid_description)
        mrids.label = "{} ({}) (MRID)".format(dbinfo.mrid_field,
                                              dbinfo.mrid_description)


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
