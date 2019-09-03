## -*- coding: utf-8 -*-
<%doc>

crate_anon/crateweb/specimen_archives/tree/snippets/results_table_nlp.mako

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

</%doc>

<%page args="cursor"/>

<%!
import logging
from cardinal_pythonlib.dbfunc import genrows, get_fieldnames_from_cursor
from markupsafe import escape
# ... the "h" filter used by Mako; see
# https://docs.makotemplates.org/en/latest/filtering.html
from crate_anon.crateweb.research.archive_func import (
    nlp_source_url,
    SILENT_NLP_XREF_COLS,
)


log = logging.getLogger(__name__)

NULL_HTML = "<i>NULL</i>"
N_SILENT_COLS = len(SILENT_NLP_XREF_COLS)

%>
<%

# As per crate_anon.crateweb.research.views.resultset_html_table():

fieldnames = get_fieldnames_from_cursor(cursor)[:-N_SILENT_COLS]
# log.critical(fieldnames)

%>

<table>
    <tr>
        %for col in fieldnames:
            <th>${col}</th>
        %endfor
        <th>Source</th>
    </tr>
    %for row in genrows(cursor):
        <% truncated_row = row[:-N_SILENT_COLS] %>
        <tr>
            %for cell in truncated_row:
                <td>${NULL_HTML if cell is None else escape(cell)}</td>
            %endfor
            <td><a href="${nlp_source_url(row)}">src</a></td>
        </tr>
    %endfor
</table>
<div><i>${cursor.rowcount} rows.</i></div>
