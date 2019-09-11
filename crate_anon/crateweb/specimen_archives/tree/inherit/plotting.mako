## -*- coding: utf-8 -*-
<%doc>

crate_anon/crateweb/specimen_archives/tree/inherit/plotting.mako

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

Base template that pre-loads the Plotly chart library.

SVG METHOD 1:

var plotly_config = {
    // https://community.plot.ly/t/save-as-svg-instead-of-png-in-modebar/4560
    // https://codepen.io/etpinard/pen/zzzBXv?editors=0010
    modeBarButtonsToRemove: ['toImage', 'sendDataToCloud'],
    modeBarButtonsToAdd: [
        {
            name: 'Save as PNG',
            icon: Plotly.Icons.camera,
            click: function(gd) {
                Plotly.downloadImage(gd, {format: 'png'})
            }
        },
        {
            name: 'Save as SVG',
            icon: Plotly.Icons.camera,
            click: function(gd) {
                Plotly.downloadImage(gd, {format: 'svg'})
            }
        }
    ]
};


SVG METHOD 2:


</%doc>

<%inherit file="../inherit/base.mako"/>

<%block name="extra_head_end">
    <script src="${get_static_url("plotly-1.49.4.min.js")}" type="text/javascript"></script>
</%block>

<script>

// Default plotly config, which may be modified by inherited pages.
var plotly_config = {
    // https://plot.ly/javascript/configuration-options/
    modeBarButtonsToRemove: ['sendDataToCloud'],
    scrollZoom: true,
    toImageButtonOptions: {
        format: "svg"
    }
};

</script>

${next.body()}
