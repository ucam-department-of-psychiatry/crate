#!/usr/bin/env python3
# research/forms.py

import logging

from django import forms
from django.conf import settings
from django.forms import (
    BooleanField,
    CharField,
    ChoiceField,
    DateField,
    FloatField,
    IntegerField,
    ModelForm,
)
from django.forms.widgets import HiddenInput
from crate_anon.crateweb.extra.forms import (
    MultipleIntAreaField,
    MultipleWordAreaField,
)
from crate_anon.crateweb.research.models import Highlight, Query

log = logging.getLogger(__name__)


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


class SQLHelperTextAnywhereForm(forms.Form):
    fkname = CharField(label="Field name containing patient ID", required=True)
    min_length = IntegerField(
        label="Minimum length of textual field (suggest e.g. 50)",
        min_value=1, required=True)
    fragment = CharField(label="String fragment to find", required=True)
    use_fulltext_index = BooleanField(
        label="Use full-text indexing where available "
        "(faster, but requires whole words)",
        required=False)
    include_content = BooleanField(
        label="Include content from fields where found (slower)",
        required=False)


class QueryBuilderColumnForm(forms.Form):
    WHERE_CHOICES = (
        ('AND', 'AND'),
        ('OR', 'OR'),
        ('AND NOT', 'AND NOT'),
    )
    COMPARISON_CHOICES_NUMBER_DATE = (
        ('<', '<'),
        ('<=', '<='),
        ('=', '='),
        ('>=', '>='),
        ('>', '>'),
        ('IN', 'IN'),
        ('IS NULL', 'IS NULL'),
        ('IS NOT NULL', 'IS NOT NULL'),
    )
    COMPARISON_CHOICES_STRING = (
        ('=', '='),
        ('LIKE', 'LIKE'),
        ('IN', 'IN'),
        ('IS NULL', 'IS NULL'),
        ('IS NOT NULL', 'IS NOT NULL'),
    )
    COMPARISON_CHOICES_STRING_FULLTEXT = (
        ('=', '='),
        ('LIKE', 'LIKE'),
        ('MATCH', 'MATCH'),
        ('IN', 'IN'),
        ('IS NULL', 'IS NULL'),
        ('IS NOT NULL', 'IS NOT NULL'),
    )

    table = CharField(label="Table", required=True)
    column = CharField(label="Column", required=True)
    comparison_type = ChoiceField(choices=COMPARISON_CHOICES_NUMBER_DATE,
                                  label="Comparison type")
    int_value = IntegerField(label="Value (integer)", required=False)
    float_value = IntegerField(label="Value (float)", required=False)
    date_value = DateField(label="Value (date)", required=False)
    string_value = CharField(label="Value (string)", required=False)
    # *** file picker for IN

    def __init__(self, *args, **kwargs):
        table = kwargs.pop('table', None)
        column = kwargs.pop('column', None)
        self.as_integer = kwargs.pop('as_integer', True)
        self.as_float = kwargs.pop('as_float', False)
        self.as_date = kwargs.pop('as_date', False)
        self.as_string = kwargs.pop('as_string', False)
        self.string_fulltext = kwargs.pop('string_fulltext', False) # *** not implemented

        kwargs['initial'] = dict(table=table, column=column)
        super().__init__(*args, **kwargs)

        self.fields['table'].widget = HiddenInput()
        self.fields['column'].widget = HiddenInput()
        if not self.as_integer:
            self.fields['int_value'].widget = HiddenInput()
        if not self.as_float:
            self.fields['float_value'].widget = HiddenInput()
        if not self.as_date:
            self.fields['date_value'].widget = HiddenInput()
        if not self.as_string:
            self.fields['string_value'].widget = HiddenInput()

        if self.as_integer or self.as_float or self.as_date:
            self.fields['comparison_type'].choices = \
                self.COMPARISON_CHOICES_NUMBER_DATE
        elif self.as_string:
            if self.string_fulltext:
                self.fields['comparison_type'].choices = \
                    self.COMPARISON_CHOICES_STRING
            else:
                self.fields['comparison_type'].choices = \
                    self.COMPARISON_CHOICES_STRING_FULLTEXT
        else:
            raise ValueError("Invalid field type")
