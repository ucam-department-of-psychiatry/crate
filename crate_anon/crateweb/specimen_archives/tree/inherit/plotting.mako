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

</%doc>

<%inherit file="../inherit/base.mako"/>

<%block name="extra_head_end">
    <script src="${get_static_url("plotly.min.js")}" type="text/javascript"></script>
</%block>

<script>

// https://community.plot.ly/t/save-as-svg-instead-of-png-in-modebar/4560
// https://codepen.io/etpinard/pen/zzzBXv?editors=0010
var default_plotly_config = {
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
        },
    ]
};

</script>

${next.body()}
