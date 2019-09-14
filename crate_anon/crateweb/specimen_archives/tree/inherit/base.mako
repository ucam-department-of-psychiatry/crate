## -*- coding: utf-8 -*-
<%doc>

crate_anon/crateweb/specimen_archives/tree/inherit/base.mako

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

Base template for CRATE "tree-style" demo archive.

</%doc>

<!DOCTYPE html> <!-- HTML 5 -->
<html lang="en">
    <head>
        <%block name="head">
            <%block name="title">
                %if patient_id:
                    <title>CRATE Archive: patient ${patient_id}</title>
                %else:
                    <title>CRATE Archive</title>
                %endif
            </%block>
            <meta charset="utf-8">
            <%block name="extra_head_start"></%block>
            <link rel="icon" type="image/png" href="${get_static_url("scrubber.png")}" >
            <link rel="stylesheet" type="text/css" href="${get_static_url("archive.css")}" >
            <%block name="extra_head_end"></%block>
        </%block>
    </head>
    <body <%block name="body_tags"></%block>>
        ${next.body()}

        <%block name="body_end"></%block>
    </body>
</html>
