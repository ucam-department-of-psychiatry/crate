#!/usr/bin/env python

"""
crate_anon/crateweb/consent/forms.py

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

**Django forms for the consent-to-contact system.**

"""

import logging

from cardinal_pythonlib.django.forms import (
    MultipleNhsNumberAreaField,
    MultipleWordAreaField,
    SingleNhsNumberField,
)
from django import forms
from django.conf import settings
from django.utils.safestring import mark_safe

from crate_anon.crateweb.consent.models import (
    ClinicianResponse,
    Study,
    TeamInfo,
    TeamRep,
)
from crate_anon.crateweb.research.research_db_info import SingleResearchDatabase  # noqa

log = logging.getLogger(__name__)


class SingleNhsNumberForm(forms.Form):
    """
    Form to capture an NHS number.
    """
    nhs_number = SingleNhsNumberField(label="NHS number")


class AbstractContactRequestForm(forms.Form):
    """
    Base class for contact requets.
    """
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
    """
    Form for superusers (the RDBM) to submit a contact request.
    """
    study = forms.ModelChoiceField(
        queryset=Study.get_queryset_possible_contact_studies())
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

        rids.label = f"{dbinfo.rid_field} ({dbinfo.rid_description}) (RID)"
        mrids.label = f"{dbinfo.mrid_field} ({dbinfo.mrid_description}) (MRID)"


class ResearcherSubmitContactRequestForm(AbstractContactRequestForm):
    """
    Form for researchers to submit a contact request for their own studies.
    """
    study = forms.ModelChoiceField(queryset=None)
    # ... queryset changed below
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

        study.queryset = Study.filter_studies_for_researcher(
            queryset=Study.get_queryset_possible_contact_studies(),
            user=user
        )
        # https://docs.djangoproject.com/en/1.8/ref/models/querysets/#field-lookups  # noqa
        # http://stackoverflow.com/questions/5329586/django-modelchoicefield-filtering-query-set-and-setting-default-value-as-an-obj  # noqa
        rids.label = f"{dbinfo.rid_field} ({dbinfo.rid_description}) (RID)"
        mrids.label = f"{dbinfo.mrid_field} ({dbinfo.mrid_description}) (MRID)"


class ClinicianSubmitContactRequestForm(AbstractContactRequestForm):
    """
    Form for clinician to request that a patient of their's gets contacted
    about a study.
    """
    study = forms.ModelChoiceField(
        queryset=Study.get_queryset_possible_contact_studies())
    nhs_numbers = MultipleNhsNumberAreaField(label='NHS numbers',
                                             required=False)
    rids = MultipleWordAreaField(required=False)
    mrids = MultipleWordAreaField(required=False)
    email = forms.EmailField(
        required=True,
        label=mark_safe("Please ensure we have the correct details for you."
                        "<br />Email"))
    signatory_title = forms.CharField(
        required=False,
        label="Title for signature (e.g. 'Consultant psychiatrist')")
    title = forms.CharField(required=True, label="Title")
    firstname = forms.CharField(required=True, label="First name")
    lastname = forms.CharField(required=True, label="Last name")
    let_rdbm_contact_pt = forms.BooleanField(
        label="Get the database manager to contact the patient directly",
        required=False)

    def __init__(self,
                 *args,
                 dbinfo: SingleResearchDatabase,
                 email_addr: str,
                 title: str,
                 firstname: str,
                 lastname: str,
                 **kwargs) -> None:
        super().__init__(*args, **kwargs)
        rids = self.fields['rids']  # type: MultipleWordAreaField
        mrids = self.fields['mrids']  # type: MultipleWordAreaField

        rids.label = f"{dbinfo.rid_field} ({dbinfo.rid_description}) (RID)"
        mrids.label = f"{dbinfo.mrid_field} ({dbinfo.mrid_description}) (MRID)"
        email = self.fields['email']
        clinician_title = self.fields['title']
        first = self.fields['firstname']
        last = self.fields['lastname']
        email.initial = email_addr
        clinician_title.initial = title
        first.initial = firstname
        last.initial = lastname


class ClinicianResponseForm(forms.ModelForm):
    """
    Form for clinicians to respond to a contact request.
    """
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


class TeamRepAdminForm(forms.ModelForm):
    """
    Custom form for the RDBM to edit team reps.

    The purposes is so that we only ask the database for team information at
    the point of use (and not e.g. to run database migrations from the command
    line!).
    """
    class Meta:
        model = TeamRep
        fields = [
            'team',
            'user',
        ]

    def __init__(self, *args, **kwargs) -> None:
        """
        Set the possible teams.
        """
        super().__init__(*args, **kwargs)
        self.fields['team'] = forms.ChoiceField(
            choices=TeamInfo.team_choices()
        )
