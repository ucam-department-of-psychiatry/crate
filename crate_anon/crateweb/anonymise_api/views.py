"""
crate_anon/crateweb/anonymise_api/views.py

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

Django REST Framework view. This is the anonymisation API end point.

"""

from django.views.generic import TemplateView

from rest_framework.parsers import JSONParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from crate_anon.crateweb.anonymise_api.serializers import (
    ScrubSerializer,
)


class HomeView(TemplateView):
    """
    Displays the API menu.
    """

    template_name = "anonymise_api/home.html"


class ScrubView(APIView):
    """
    Main CRATE anonymisation end-point.
    """

    # Only needed by drf_spectacular to generate documentation
    serializer_class = ScrubSerializer

    # Not currently supporting MultiPartParser for multipart/form-data.
    # Requires some work to get the nested serializers handling the data
    # correctly, particularly in the Browseable API form. See git history.
    parser_classes = [JSONParser]

    # noinspection PyMethodMayBeStatic
    def post(self, request: Request) -> Response:
        serializer = ScrubSerializer(data=request.data)

        # If the input is valid, this will do the anonymisation
        serializer.is_valid(raise_exception=True)

        return Response(serializer.data)
