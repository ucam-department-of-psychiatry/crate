## -*- coding: utf-8 -*-
## crate_anon/crateweb/specimen_archives/basic/snippets/results_table.mako
<%page args="cursor"/>

<%!
from cardinal_pythonlib.dbfunc import genrows, get_fieldnames_from_cursor
from markupsafe import escape
# ... the "h" filter used by Mako; see
# https://docs.makotemplates.org/en/latest/filtering.html

NULL_HTML = "<i>NULL</i>"
%>

<table>
    <tr>
        %for col in get_fieldnames_from_cursor(cursor):
            <th>${col}</th>
        %endfor
    </tr>
    %for row in genrows(cursor):
        <tr>
            %for cell in row:
                <td>${NULL_HTML if cell is None else escape(cell)}</td>
            %endfor
        </tr>
    %endfor
</table>
