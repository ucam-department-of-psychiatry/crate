## -*- coding: utf-8 -*-
## crate_anon/crateweb/specimen_archives/tree/snippets/nlp_section.mako
<%page args="tablename: str, description: str, columns: Iterable[str]"/>

<%!
from typing import Iterable
from cardinal_pythonlib.dbfunc import genrows, get_fieldnames_from_cursor

def nlp_sql(tablename: str, columns: Iterable[str]) -> str:
    colstr = ", ".join(columns)
    return f"""
        SELECT {colstr}
        FROM {tablename}
        WHERE brcid = ?
        ORDER BY _srcdatetimeval ASC
    """
%>

<h2><a id="${tablename}"></a>${description} <a href="#_top">[top]</a></h2>
<% cursor = execute(nlp_sql(tablename, columns), [patient_id]) %>
<%include file="../snippets/results_table.mako" args="cursor=cursor"/>
