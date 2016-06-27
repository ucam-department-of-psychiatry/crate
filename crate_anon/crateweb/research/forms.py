#!/usr/bin/env python3
# research/forms.py

import datetime
import logging

from django import forms
from django.conf import settings
from django.forms import (
    BooleanField,
    CharField,
    ChoiceField,
    DateField,
    FileField,
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
from crate_anon.crateweb.research.sql_writer import (
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


class QueryBuilderColForm(forms.Form):
    """
    Using an "AND NOT" button becomes confusing the first time you enter a
    condition. Offer negated conditions, but only AND as a where-condition
    joiner.

    Using OR becomes tricky in terms of precedence; use SQL.

    Using IN becomes tricky using standard input fields (e.g. an int-validation
    field won't allow int CSV input).

    Not equals: <> in ANSI SQL, but != is supported by MySQL and clearer.
    """
    COMPARISON_CHOICES_NUMBER_DATE = (
        ('<', '<'),
        ('<=', '<='),
        ('=', '='),
        ('!=', '!= (not equals)'),
        ('>=', '>='),
        ('>', '>'),
        ('IN', 'IN (from file contents)'),
        ('NOT IN', 'NOT IN (from file contents)'),
        ('IS NULL', 'IS NULL'),
        ('IS NOT NULL', 'IS NOT NULL'),
    )
    COMPARISON_CHOICES_STRING = (
        ('=', '='),
        ('!=', '!= (not equals)'),
        ('LIKE', 'LIKE (use % as wildcard)'),
        ('IN', 'IN (from file contents)'),
        ('NOT IN', 'NOT IN (from file contents)'),
        ('IS NULL', 'IS NULL'),
        ('IS NOT NULL', 'IS NOT NULL'),
    )
    COMPARISON_CHOICES_STRING_FULLTEXT = (
        ('=', '='),
        ('!= (not equals)', '!='),
        ('LIKE', 'LIKE (use % as wildcard)'),
        ('MATCH', 'MATCH (match whole words)'),  # ***
        ('IN', 'IN (from file contents)'),
        ('NOT IN', 'NOT IN (from file contents)'),
        ('IS NULL', 'IS NULL'),
        ('IS NOT NULL', 'IS NOT NULL'),
    )
    COMPARISON_OPTION_IN = ()
    DATATYPE_INTEGER = "int"
    DATATYPE_FLOAT = "float"
    DATATYPE_DATE = "date"
    DATATYPE_STRING = "string"
    DATATYPE_STRING_FULLTEXT = "string_fulltext"
    DATATYPE_UNKNOWN = "unknown"
    STRING_TYPES = [DATATYPE_STRING, DATATYPE_STRING_FULLTEXT]
    VALUE_UNNECESSARY = ['IS NULL', 'IS NOT NULL',
                         'IN', 'NOT IN']
    FILE_REQUIRED = ['IN', 'NOT IN']

    table = CharField(label="Table", required=True)
    column = CharField(label="Column", required=True)
    datatype = CharField(label="Data type", required=True)

    comparison_type = ChoiceField(choices=COMPARISON_CHOICES_NUMBER_DATE,
                                  label="Comparison type", required=False)
    int_value = IntegerField(label="Integer value", required=False)
    float_value = FloatField(label="Float value", required=False)
    date_value = DateField(label="Date value (e.g. 1900-01-31)",
                           required=False)
    string_value = CharField(label="String value", required=False)
    file = FileField(label="File (for IN)", required=False)

    def hide_field(self, fieldname):
        self.fields[fieldname].widget = HiddenInput()

    def __init__(self, *args, **kwargs):
        self.file_values_list = ''
        self.offer_where = kwargs.pop('offer_where', True)
        self.offer_file = kwargs.pop('offer_file', True)
        arg_table = kwargs.pop('table', None)
        arg_column = kwargs.pop('column', None)
        arg_datatype = kwargs.pop('datatype', self.DATATYPE_INTEGER)
        kwargs['initial'] = dict(table=arg_table,
                                 column=arg_column,
                                 datatype=arg_datatype,
                                 comparison_type="=")
        super().__init__(*args, **kwargs)

        # Hide fields that just pass data back
        self.hide_field('table')
        self.hide_field('column')
        self.hide_field('datatype')

        # Data may either come from code (via named arguments to this function)
        # or from the form (via the 'data' argument, passed to super()).
        # So choose the best:
        offer_where = self.offering_where()
        datatype = self.get_datatype()

        # Hide fields that we won't use
        if not offer_where or datatype == self.DATATYPE_UNKNOWN:
            self.hide_field('comparison_type')
        value_fieldname = self.get_value_fieldname()
        for f in ['int_value', 'float_value', 'date_value', 'string_value']:
            if not offer_where or f != value_fieldname:
                self.hide_field(f)
        if not offer_where or not self.offer_file:
            self.hide_field('file')

        # What choices will we offer for the WHERE part?
        if datatype in [self.DATATYPE_INTEGER,
                        self.DATATYPE_FLOAT,
                        self.DATATYPE_DATE]:
            self.fields['comparison_type'].choices = \
                self.COMPARISON_CHOICES_NUMBER_DATE
        elif datatype == self.DATATYPE_STRING:
            self.fields['comparison_type'].choices = \
                self.COMPARISON_CHOICES_STRING
        elif datatype == self.DATATYPE_STRING_FULLTEXT:
            self.fields['comparison_type'].choices = \
                self.COMPARISON_CHOICES_STRING_FULLTEXT
        elif datatype == self.DATATYPE_UNKNOWN:
            self.fields['comparison_type'].choices = ()
        else:
            raise ValueError("Invalid field type")

    def get_datatype(self):
        return self.data.get('datatype',
                             self.initial.get('datatype', None))

    def offering_where(self):
        if self.get_datatype() == self.DATATYPE_UNKNOWN:
            return False
        return self.offer_where

    def offering_file(self):
        return self.offer_file

    def get_value_fieldname(self):
        datatype = self.get_datatype()
        if datatype == self.DATATYPE_INTEGER:
            return "int_value"
        if datatype == self.DATATYPE_FLOAT:
            return "float_value"
        if datatype == self.DATATYPE_DATE:
            return "date_value"
        if datatype in [self.DATATYPE_STRING, self.DATATYPE_STRING_FULLTEXT]:
            return "string_value"
        if datatype == self.DATATYPE_UNKNOWN:
            return ""
        raise ValueError("Invalid field type")

    def get_cleaned_where_value(self):
        # Only call this if you've already cleaned/validated the form!
        return self.cleaned_data[self.get_value_fieldname()]

    def clean(self):
        # Check the WHERE information is sufficient.
        if 'add_result_column' in self.data:
            # Form submitted via the "Add" method, so no checks required.
            # http://stackoverflow.com/questions/866272/how-can-i-build-multiple-submit-buttons-django-form  # noqa
            return
        if not self.offering_where():
            return
        cleaned_data = super().clean()
        if not cleaned_data['comparison_type']:
            self.add_error('comparison_type',
                           forms.ValidationError("Must specify comparison"))

        # No need for a value for NULL-related comparisons. But otherwise:
        comparison_type = cleaned_data['comparison_type']
        if comparison_type not in self.VALUE_UNNECESSARY:
            value_fieldname = self.get_value_fieldname()
            value = cleaned_data.get(value_fieldname)
            if not value:
                self.add_error(
                    value_fieldname,
                    forms.ValidationError("Must specify WHERE condition"))

        if comparison_type not in self.FILE_REQUIRED:
            return
        file = cleaned_data['file']
        # ... is an instance of InMemoryUploadedFile
        if not file:
            self.add_error('file', forms.ValidationError("Must specify file"))
            return

        datatype = self.get_datatype()
        if datatype in QueryBuilderColForm.STRING_TYPES:
            form_to_python_fn = str
            literal_func = sql_string_literal
        elif datatype == QueryBuilderColForm.DATATYPE_DATE:
            form_to_python_fn = lambda x: datetime.datetime.strptime(
                x, "%Y-%m-%d")
            literal_func = sql_date_literal
        else:
            form_to_python_fn = str
            literal_func = str
        # Or: http://www.dabeaz.com/generators/Generators.pdf
        literals = []
        for line in file.read().decode("utf8").splitlines():
            for raw_item in line.split():
                # noinspection PyBroadException
                try:
                    value = form_to_python_fn(raw_item)
                except:
                    self.add_error('file', forms.ValidationError(
                        "File contains bad value: {}".format(raw_item)))
                    return
                literals.append(literal_func(value))
        if not literals:
            self.add_error('file', forms.ValidationError(
                "No values found in file"))
        self.file_values_list = "({})".format(", ".join(literals))
