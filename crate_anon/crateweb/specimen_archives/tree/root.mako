## -*- coding: utf-8 -*-
<%doc>

crate_anon/crateweb/specimen_archives/tree/launch_archive.mako

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

<%inherit file="inherit/base.mako"/>

<%!

from crate_anon.common.constants import HelpUrl

%>

<div class="pad">
    [ <a href="${CRATE_HOME_URL}">Return to CRATE home</a> ]

    <h1>Launch archive view for a specific patient</h1>

    <form action="${get_template_url()}" method="GET">
        <input type="text" name="patient_id" title="Patient ID" placeholder="Patient ID" />
        <input type="submit" name="submit" value="Launch" />
        ## The query parameters in the URL will be REPLACED, as per
        ## https://stackoverflow.com/questions/1116019/, so we also need:
        <input type="hidden" name="template" value="patient_root.mako" />
    </form>

    <h1>Archive views for multiple patients simultaneously</h1>

    <a href="${get_template_url("nonpatient_root.mako")}">Nonpatient archive page</a>

</div>
