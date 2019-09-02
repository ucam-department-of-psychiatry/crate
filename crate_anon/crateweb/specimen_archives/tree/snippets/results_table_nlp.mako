## -*- coding: utf-8 -*-
## crate_anon/crateweb/specimen_archives/tree/snippets/results_table_nlp.mako
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
