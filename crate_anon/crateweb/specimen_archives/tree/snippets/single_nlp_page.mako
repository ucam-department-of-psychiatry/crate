## -*- coding: utf-8 -*-
<%doc>

crate_anon/crateweb/specimen_archives/tree/snippets/single_nlp_page.mako

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

Query parameters (from URL):

    tablename:
        str: table to query
    description:
        str: description of the NLP tool
    column_csv:
        str: CSV of column names, other than the ever-present ones

</%doc>

<%inherit file="../inherit/plotting.mako"/>

<%!
import logging
from typing import Iterable

from cardinal_pythonlib.dbfunc import genrows, get_fieldnames_from_cursor

from crate_anon.crateweb.research.archive_func import (
    delimit_sql_identifier,
    json_compact,
)
from crate_anon.crateweb.research.views import (
    FN_SRCDB,
    FN_SRCTABLE,
    FN_SRCFIELD,
    FN_SRCPKFIELD,
    FN_SRCPKVAL,
    FN_SRCPKSTR,
)

log = logging.getLogger(__name__)

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
DATECOLNAME = "_srcdatetimeval"


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

tablename = query_params["tablename"]
description = query_params["description"]
column_csv = query_params["column_csv"]
n_graph_columns = int(query_params["n_graph_columns"])

columns = column_csv.split(",")
cursor = execute(nlp_sql(tablename, columns), [patient_id])

nrows = cursor.rowcount
datecolidx = 0

if n_graph_columns > 0 and datecolidx is not None and nrows > 0:
    do_chart = True
    data = []
    for idx_in_columns in range(n_graph_columns):
        idx_in_query = idx_in_columns + len(STARTCOLS)
        d_v = [(row[datecolidx].isoformat(),
                row[idx_in_query]) for row in cursor]
        dates, values = zip(*d_v)
        data.append({
            "type": "scatter",
            "x": dates,
            "y": values,
            "name": columns[idx_in_columns],
            "mode": "lines+markers",
            "showlegend": True,
        })
    # log.critical(f"data: {data!r}")
    layout = {
        "title": description
    }
    filename = f"{patient_id}_{tablename}"
else:
    do_chart = False

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

%if do_chart:

    <div id="chart"></div>

    <script>

        // ====================================================================
        // Graph
        // ====================================================================

        var chart = document.getElementById("chart");
        var data = ${json_compact(data)};
        var layout = ${json_compact(layout)};

        plotly_config["toImageButtonOptions"]["filename"] = ${json_compact(filename)};
        console.log(plotly_config);

        Plotly.plot(chart, data, layout, plotly_config);

    </script>

%endif
