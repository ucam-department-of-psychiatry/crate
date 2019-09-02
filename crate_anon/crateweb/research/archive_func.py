#!/usr/bin/env python

"""
crate_anon/crateweb/research/archive_func.py

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

**Assistance functions for archive Mako templates.**

"""

import logging
from typing import Any, List

from cardinal_pythonlib.httpconst import ContentType
from cardinal_pythonlib.logs import BraceStyleAdapter
from django.urls import reverse

from crate_anon.crateweb.core.utils import (
    guess_mimetype,
    url_with_querystring,
)
from crate_anon.crateweb.research.research_db_info import (
    research_database_info,
)
from crate_anon.crateweb.research.views import (
    archive_attachment_url,
    FN_SRCDB,
    FN_SRCTABLE,
    FN_SRCFIELD,
    FN_SRCPKFIELD,
    FN_SRCPKVAL,
    FN_SRCPKSTR,
)

log = BraceStyleAdapter(logging.getLogger(__name__))

SILENT_NLP_XREF_COLS = [
    FN_SRCDB,
    FN_SRCTABLE,
    FN_SRCFIELD,
    FN_SRCPKFIELD,
    FN_SRCPKVAL,
    FN_SRCPKSTR,
]


# =============================================================================
# Functions for use by Mako archive templates (not common enough to be in
# context; templates can import them as required).
# =============================================================================

def embedded_attachment_html(filename: str,
                             object_class: str = "embedded_attachment",
                             alt_div_class: str = "obscure_spinner") -> str:
    """
    HTML element to show an attachment (such as a PDF) inline.

    Args:
        filename:
            filename to use, within the archive
        object_class:
            CSS class of the <object>
        alt_div_class:
            CSS class of the <div> to show on load failure
    """
    url = archive_attachment_url(filename)
    content_type = guess_mimetype(filename, default=ContentType.TEXT)
    return (
        f'<object class="{object_class}" data="{url}" type="{content_type}">'
        f'<div class="{alt_div_class}">'
        f'The attachment couldn’t be displayed inline. Download it as '
        f'<a href="{url}">{filename}</a>'
        f'</div>'
        f'</object>'
    )


def template_html(url: str, iframe_class: str = "embedded_attachment",
                  **qparams) -> str:
    """
    HTML element to show aonther archive template inline.

    Args:
        url: patient-specific URL for the template
        iframe_class: CSS class for the <iframe>
        qparams: query parameters to pass to the template
    """
    final_url = url_with_querystring(url, **qparams)
    return f'<iframe class="{iframe_class}" src="{final_url}"></iframe>'


def delimit_sql_identifier(identifer: str) -> str:
    """
    Delimits (quotes) an SQL identifier, if required.
    """
    return research_database_info.grammar.quote_identifier_if_required(identifer)  # noqa


def nlp_source_url(row: List[Any]) -> str:
    """
    Returns a URL to the source text for some NLP, ON THE ASSUMPTION that the
    last columns of a query are :data:`SILENT_NLP_XREF_COLS`.

    Args:
        row: result row
    """
    return reverse('srcinfo', kwargs={
        'srcdb': row[-6],
        'srctable': row[-5],
        'srcfield': row[-4],
        'srcpkfield': row[-3],
        'srcpkval': row[-2],
        'srcpkstr': row[-1]
    })
