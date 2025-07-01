"""
crate_anon/crateweb/config/apps.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

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
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

**Django apps, for crate_anon.crateweb.config.settings.INSTALLED_APPS.**

These classes point Django to directories within the CRATE tree.

"""

from django.apps import AppConfig


class ConsentAppConfig(AppConfig):
    """
    Django :class:`django.apps.AppConfig` for the consent system.
    """

    name = "crate_anon.crateweb.consent"


class ResearchAppConfig(AppConfig):
    """
    Django :class:`django.apps.AppConfig` for the researcher's views.
    """

    name = "crate_anon.crateweb.research"


class UserProfileAppConfig(AppConfig):
    """
    Django :class:`django.apps.AppConfig` for extended user profiles.
    """

    name = "crate_anon.crateweb.userprofile"


class CoreAppConfig(AppConfig):
    """
    Django :class:`django.apps.AppConfig` for the core app.
    """

    name = "crate_anon.crateweb.core"


class ApiConfig(AppConfig):
    """
    Django :class:`django.apps.AppConfig` for the anonymiser API.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "crate_anon.crateweb.anonymise_api"


class NlpClassificationConfig(AppConfig):
    """
    Django :class:`django.apps.AppConfig` for NLP Classification.
    """

    name = "crate_anon.crateweb.nlp_classification"
