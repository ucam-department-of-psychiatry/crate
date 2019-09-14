## -*- coding: utf-8 -*-
<%doc>

crate_anon/crateweb/specimen_archives/basic/patient_root.mako

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

## Alter the "navigate to root" link on the root page.
<%block name="navigate_to_root">
    <a href="${get_template_url("root.mako")}">Choose another patient</a>
    |
</%block>

<%block name="template_description">Choose an area to explore for this patient:</%block>

<div class="navigation">
  <ul>
    <li><a href="${get_patient_template_url("clinical_documents.mako")}">Clinical documents</a></li>
    <li><a href="${get_patient_template_url("diagnoses.mako")}">Diagnoses</a></li>
    <li><a href="${get_patient_template_url("progress_notes.mako")}">Progress notes</a></li>
    <li><a href="${get_patient_template_url("search.mako")}">Search</a></li>
    <li><a href="${get_patient_template_url("test.mako")}">Test page</a></li>
    <li><a href="${get_patient_template_url("test_subpanel_1.mako")}">Test sub-panels (1)</a></li>
    <li><a href="${get_patient_template_url("test_subpanel_2.mako")}">Test sub-panels (2)</a></li>
  </ul>
</div>
