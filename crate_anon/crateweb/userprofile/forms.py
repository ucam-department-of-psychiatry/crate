#!/usr/bin/env python

"""
crate_anon/crateweb/userprofile/forms.py

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

**Forms for editing user profiles.**

"""

from django.forms import ModelForm
from crate_anon.crateweb.userprofile.models import UserProfile


class UserProfileForm(ModelForm):
    """
    Form to edit a :class:`crate_anon.crateweb.userprofile.models.UserProfile`.
    """
    class Meta:
        model = UserProfile
        fields = ['per_page', 'patients_per_page',
                  'line_length', 'collapse_at_len', 'collapse_at_n_lines']
