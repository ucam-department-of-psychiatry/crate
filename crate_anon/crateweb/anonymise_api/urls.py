"""
crate_anon/anonymise_webserver/anonymiser/urls.py

===============================================================================

    Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).

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

**Django URL configuration for CRATE anonymiser project.**

"""

from django.urls import path

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
)

from crate_anon.crateweb.anonymise_api.views import ScrubView

urlpatterns = [
    path("scrub/", ScrubView.as_view(), name="anon_api"),
    path("schema/", SpectacularAPIView.as_view(), name="anon_api_schema"),
    path(
        "schema/doc/",
        SpectacularRedocView.as_view(url_name="anon_api_schema"),
        name="anon_api_doc",
    ),
]
