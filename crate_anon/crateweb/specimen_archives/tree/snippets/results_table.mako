## -*- coding: utf-8 -*-
<%doc>

crate_anon/crateweb/specimen_archives/tree/snippets/results_table.mako

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
<div><i>${cursor.rowcount} rows.</i></div>
