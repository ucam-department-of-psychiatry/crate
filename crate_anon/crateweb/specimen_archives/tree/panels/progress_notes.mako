## -*- coding: utf-8 -*-
## crate_anon/crateweb/specimen_archives/tree/panels/progress_notes.mako
<%inherit file="../base.mako"/>
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
