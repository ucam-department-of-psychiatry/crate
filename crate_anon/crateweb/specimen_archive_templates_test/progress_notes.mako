## progress_notes.mako
<%inherit file="base.mako"/>

<%block name="template_description">Progress Notes</%block>

<%

sql = """
    SELECT
        note_datetime AS 'When',
        note AS 'Note'
    FROM note
    WHERE brcid = ?
    ORDER BY note_datetime DESC
"""
args = [patient_id]
cursor = query(sql, args)

%>

<%include file="snippets/results_table.mako" args="cursor=cursor"/>
