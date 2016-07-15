#!/usr/bin/env python3
# crate_anon/crateweb/research/forms.py

import datetime
import logging

from django import forms
from django.conf import settings
from django.forms import (
    BooleanField,
    CharField,
    # ChoiceField,
    DateField,
    FileField,
    FloatField,
    IntegerField,
    ModelForm,
)
# from django.forms.widgets import HiddenInput
from crate_anon.crateweb.extra.forms import (
    MultipleIntAreaField,
    MultipleWordAreaField,
)
from crate_anon.crateweb.research.models import ColumnInfo, Highlight, Query
from crate_anon.common.sql import (
    sql_date_literal,
    sql_string_literal,
)

log = logging.getLogger(__name__)


class AddQueryForm(ModelForm):
    class Meta:
        model = Query
        fields = ['sql']
        widgets = {
            'sql': forms.Textarea(attrs={'rows': 20, 'cols': 80}),
        }


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


def html_form_date_to_python(text):
    return datetime.datetime.strptime(text, "%Y-%m-%d")


def int_validator(text):
    return str(int(text))  # may raise ValueError, TypeError


def float_validator(text):
    return str(float(text))  # may raise ValueError, TypeError


class QueryBuilderForm(forms.Form):
    # See also querybuilder.js
    VALUE_UNNECESSARY = ['IS NULL', 'IS NOT NULL']
    SINGLE_VALUE_UNNECESSARY = ['IS NULL', 'IS NOT NULL',
                                'IN', 'NOT IN']
    FILE_REQUIRED = ['IN', 'NOT IN']

    schema = CharField(label="Schema", required=True)
    table = CharField(label="Table", required=True)
    column = CharField(label="Column", required=True)
    datatype = CharField(label="Data type", required=True)
    offer_where = BooleanField(label="Offer WHERE?", required=False)
    # BooleanField generally needs "required=False", or you can't have False!
    where_op = CharField(label="WHERE comparison", required=False)

    date_value = DateField(label="Date value (e.g. 1900-01-31)",
                           required=False)
    int_value = IntegerField(label="Integer value", required=False)
    float_value = FloatField(label="Float value", required=False)
    string_value = CharField(label="String value", required=False)
    file = FileField(label="File (for IN)", required=False)

    def __init__(self, *args, **kwargs):
        self.file_values_list = ''
        super().__init__(*args, **kwargs)

    def get_datatype(self):
        return self.data.get('datatype', None)

    def is_datatype_unknown(self):
        return self.get_datatype() == ColumnInfo.DATATYPE_UNKNOWN

    def offering_where(self):
        if self.is_datatype_unknown():
            return False
        return self.data.get('offer_where', False)

    def get_value_fieldname(self):
        datatype = self.get_datatype()
        if datatype == ColumnInfo.DATATYPE_INTEGER:
            return "int_value"
        if datatype == ColumnInfo.DATATYPE_FLOAT:
            return "float_value"
        if datatype == ColumnInfo.DATATYPE_DATE:
            return "date_value"
        if datatype in ColumnInfo.STRING_TYPES:
            return "string_value"
        if datatype == ColumnInfo.DATATYPE_UNKNOWN:
            return ""
        raise ValueError("Invalid field type")

    def get_cleaned_where_value(self):
        # Only call this if you've already cleaned/validated the form!
        return self.cleaned_data[self.get_value_fieldname()]

    def clean(self):
        # Check the WHERE information is sufficient.
        if 'submit_select' in self.data:
            # Form submitted via the "Add" method, so no checks required.
            # http://stackoverflow.com/questions/866272/how-can-i-build-multiple-submit-buttons-django-form  # noqa
            return
        if not self.offering_where():
            return
        cleaned_data = super().clean()
        if not cleaned_data['where_op']:
            self.add_error('where_op',
                           forms.ValidationError("Must specify comparison"))

        # No need for a value for NULL-related comparisons. But otherwise:
        where_op = cleaned_data['where_op']
        if where_op not in self.SINGLE_VALUE_UNNECESSARY:
            value_fieldname = self.get_value_fieldname()
            value = cleaned_data.get(value_fieldname)
            if not value:
                self.add_error(
                    value_fieldname,
                    forms.ValidationError("Must specify WHERE condition"))

        # ---------------------------------------------------------------------
        # Special processing for file upload operations
        # ---------------------------------------------------------------------
        if where_op not in self.FILE_REQUIRED:
            return
        file = cleaned_data['file']
        # ... is an instance of InMemoryUploadedFile
        if not file:
            self.add_error('file', forms.ValidationError("Must specify file"))
            return

        datatype = self.get_datatype()
        if datatype in ColumnInfo.STRING_TYPES:
            form_to_python_fn = str
            literal_func = sql_string_literal
        elif datatype == ColumnInfo.DATATYPE_DATE:
            form_to_python_fn = html_form_date_to_python
            literal_func = sql_date_literal
        elif datatype == ColumnInfo.DATATYPE_INTEGER:
            form_to_python_fn = int_validator
            literal_func = str
        elif datatype == ColumnInfo.DATATYPE_FLOAT:
            form_to_python_fn = float_validator
            literal_func = str
        else:
            # Safe defaults
            form_to_python_fn = str
            literal_func = sql_string_literal
        # Or: http://www.dabeaz.com/generators/Generators.pdf
        literals = []
        for line in file.read().decode("utf8").splitlines():
            raw_item = line.strip()
            if not raw_item or raw_item.startswith('#'):
                continue
            try:
                value = form_to_python_fn(raw_item)
            except (TypeError, ValueError):
                self.add_error('file', forms.ValidationError(
                    "File contains bad value: {}".format(repr(raw_item))))
                return
            literals.append(literal_func(value))
        if not literals:
            self.add_error('file', forms.ValidationError(
                "No values found in file"))
        self.file_values_list = "({})".format(", ".join(literals))
