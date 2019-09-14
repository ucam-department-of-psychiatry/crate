## -*- coding: utf-8 -*-
<%doc>

crate_anon/crateweb/specimen_archives/basic/root.mako

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

## Don't show the "navigate to root" link on the root page.
<%block name="navigate_to_root"></%block>

<%block name="template_description">Choose a patient:</%block>

<div class="pad">
    <h1>Launch archive view for a specific patient</h1>

    <form action="${get_template_url()}" method="GET">
        <input type="text" name="patient_id" title="Patient ID" placeholder="Patient ID" />
        <input type="submit" name="submit" value="Launch" />
        ## The query parameters in the URL will be REPLACED, as per
        ## https://stackoverflow.com/questions/1116019/, so we also need:
        <input type="hidden" name="template" value="patient_root.mako" />
    </form>

</div>
