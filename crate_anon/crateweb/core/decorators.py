"""
crate_anon/crateweb/core/decorators.py

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

**Decorators shared by all apps.**

"""

from functools import wraps

from django.shortcuts import render

from crate_anon.crateweb.core.constants import (
    NLP_DB_CONNECTION_NAME,
)
from crate_anon.crateweb.raw_sql.database_connection import DatabaseConnection


def ensure_nlp_connection_exists(view_func):
    @wraps(view_func)
    def decorator(request, *args, **kwargs):
        if not DatabaseConnection(NLP_DB_CONNECTION_NAME).exists():
            error = (
                f"No database connection named '{NLP_DB_CONNECTION_NAME}' "
                "exists. Check your local_settings.py file."
            )

            context = dict(error=error)
            return render(
                request,
                "generic_error.html",
                context=context,
            )

        return view_func(request, *args, **kwargs)

    return decorator
