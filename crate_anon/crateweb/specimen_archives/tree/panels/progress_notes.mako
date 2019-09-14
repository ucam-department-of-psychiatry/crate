## -*- coding: utf-8 -*-
<%doc>

crate_anon/crateweb/specimen_archives/tree/panels/progress_notes.mako

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

<%inherit file="../inherit/base.mako"/>
<%!
import logging

log = logging.getLogger(__name__)
%>

<%

sql = """
    SELECT
        note_datetime AS 'When',
        note AS 'Note'
    FROM note
    WHERE brcid = ?
    ORDER BY note_datetime ASC
"""
args = [patient_id]
cursor = execute(sql, args)

%>

<div class="pad">
    <h1>Progress Notes</h1>
    <p><i>Old at the top, new at the bottom.</i></p>
    %for row in cursor:
        ## <% log.debug(repr(row)) %>
        <h2>${row[0]}</h2>
        <div>${row[1] | h}</div>
    %endfor
</div>
