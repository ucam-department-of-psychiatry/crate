#!/usr/bin/env python
# crate_anon/crateweb/extra/forms.py

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

from typing import List

from django import forms

from crate_anon.common.nhs import is_valid_nhs_number


# =============================================================================
# Multiple values from a text area
# =============================================================================

def clean_int(x) -> int:
    try:
        return int(x)
    except ValueError:
        raise forms.ValidationError(
            "Cannot convert to integer: {}".format(repr(x)))


def clean_nhs_number(x) -> int:
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

    def clean(self, value) -> List[int]:
        return [clean_int(x) for x in value.split()]


class MultipleNhsNumberAreaField(forms.Field):
    widget = forms.Textarea

    def clean(self, value) -> List[int]:
        return [clean_nhs_number(x) for x in value.split()]


class MultipleWordAreaField(forms.Field):
    widget = forms.Textarea

    def clean(self, value) -> List[str]:
        return value.split()


class SingleNhsNumberField(forms.IntegerField):
    def clean(self, value) -> int:
        return clean_nhs_number(value)
