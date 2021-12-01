## -*- coding: utf-8 -*-
<%doc>

crate_anon/crateweb/specimen_archives/tree/panels/test_plot.mako

===============================================================================

    Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).

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

<%inherit file="../inherit/plotting.mako"/>

<h1>Plotly chart</h1>
<div id="plotly_chart"></div>

<script>

// ============================================================================
// Plotly
// ============================================================================
// See https://plot.ly/javascript/reference/

let chart = document.getElementById("plotly_chart");
const data = [{
    x: [1, 2, 3, 4, 5],
    y: [1, 2, 4, 8, 16],
    type: "scatter",
    name: "Fictional data"
    // line: { shape: "spline" }
}];
const layout = {
    width: window.innerWidth,
    // height: window.innerHeight,
    margin: {
        // t: 0  // a top margin of zero wipes out any title
    },
    title: {
        text: "Fictional data"
    },
    xaxis: {
        title: "Some x data"
    },
    yaxis: {
        title: "Some y data"
    }
};

Plotly.plot(chart, data, layout, plotly_config);

</script>
