## -*- coding: utf-8 -*-
## crate_anon/crateweb/specimen_archives/tree/snippets/single_nlp_page.mako
<%inherit file="../base.mako"/>

<%doc>

Page parameters (from URL):

    tablename:
        str: table to query
    description:
        str: description of the NLP tool
    columns:
        str: CSV of column names, other than the ever-present ones

</%doc>

<%!
from typing import Iterable
from cardinal_pythonlib.dbfunc import genrows, get_fieldnames_from_cursor
from crate_anon.crateweb.research.archive_func import delimit_sql_identifier
from crate_anon.crateweb.research.views import (
    FN_SRCDB,
    FN_SRCTABLE,
    FN_SRCFIELD,
    FN_SRCPKFIELD,
    FN_SRCPKVAL,
    FN_SRCPKSTR,
)

SILENT_COLS = [
    FN_SRCDB,
    FN_SRCTABLE,
    FN_SRCFIELD,
    FN_SRCPKFIELD,
    FN_SRCPKVAL,
    FN_SRCPKSTR,
]  # hard-coded special order; MUST MATCH results_table_nlp.mako
STARTCOLS = [
    "_srcdatetimeval AS 'Source time'",
]
ENDCOLS = [
    "_when_fetched_utc AS 'NLP time'",
] + SILENT_COLS


def nlp_sql(tablename: str, columns: Iterable[str]) -> str:
    tablename = delimit_sql_identifier(tablename)
    final_columns = (
        STARTCOLS +
        [delimit_sql_identifier(c) for c in columns] +
        ENDCOLS
    )
    colstr = ", ".join(final_columns)
    return (
        f"SELECT {colstr} "
        f"FROM {tablename} "
        f"WHERE brcid = ? "
        f"ORDER BY _srcdatetimeval ASC"
    )

%>

<%

columns = column_csv.split(",")
cursor = execute(nlp_sql(tablename, columns), [patient_id])

%>

<div class="pad">
    <h1>${description}</h1>

    <p>Natural Language Processing (NLP) results.
        “Source time” is when the record relates to.
        “NLP time” is when the NLP software processed this data.
        <b>NLP is imperfect:</b> it may miss mentions (false negatives), or
        misinterpret something irrelevant/incorrect (false positives).</p>

    <%include file="results_table_nlp.mako" args="cursor=cursor"/>
</div>
