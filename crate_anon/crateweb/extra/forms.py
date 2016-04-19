#!/usr/bin/env python3
# extra/forms.py

from django import forms
from crate_anon.crateweb.extra.nhs import is_valid_nhs_number


# =============================================================================
# Multiple values from a text area
# =============================================================================

def clean_int(x):
    try:
        return int(x)
    except ValueError:
        raise forms.ValidationError(
            "Cannot convert to integer: {}".format(repr(x)))


def clean_nhs_number(x):
    try:
        x = int(x)
        if not is_valid_nhs_number(x):
            raise ValueError
        return x
    except ValueError:
        raise forms.ValidationError(
            "Not a valid NHS number: {}".format(repr(x)))


class MultipleIntAreaField(forms.Field):
    # See also http://stackoverflow.com/questions/29303902/django-form-with-list-of-integers  # noqa
    widget = forms.Textarea

    def clean(self, value):
        return [clean_int(x) for x in value.split()]


class MultipleNhsNumberAreaField(forms.Field):
    widget = forms.Textarea

    def clean(self, value):
        return [clean_nhs_number(x) for x in value.split()]


class MultipleWordAreaField(forms.Field):
    widget = forms.Textarea

    def clean(self, value):
        return value.split()


class SingleNhsNumberField(forms.IntegerField):
    def clean(self, value):
        return clean_nhs_number(value)
