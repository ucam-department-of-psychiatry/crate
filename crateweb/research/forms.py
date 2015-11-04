#!/usr/bin/env python3
# research/forms.py

from django import forms
from django.conf import settings
from django.forms import ModelForm
from core.extra import (
    MultipleIntAreaField,
    MultipleWordAreaField,
)
from .models import Highlight, Query


class AddQueryForm(ModelForm):
    class Meta:
        model = Query
        fields = ['sql']


class BlankQueryForm(ModelForm):
    class Meta:
        model = Query
        fields = []


class AddHighlightForm(ModelForm):
    class Meta:
        model = Highlight
        fields = ['colour', 'text']


class BlankHighlightForm(ModelForm):
    class Meta:
        model = Highlight
        fields = []


class PidLookupForm(forms.Form):
    trids = MultipleIntAreaField(
        label='{} (TRID)'.format(settings.SECRET_MAP['TRID_FIELD']),
        required=False)
    rids = MultipleWordAreaField(
        label='{} (RID)'.format(settings.SECRET_MAP['RID_FIELD']),
        required=False)
    mrids = MultipleWordAreaField(
        label='{} (MRID)'.format(settings.SECRET_MAP['MASTER_RID_FIELD']),
        required=False)
