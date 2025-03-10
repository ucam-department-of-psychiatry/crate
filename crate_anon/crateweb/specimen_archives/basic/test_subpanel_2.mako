## -*- coding: utf-8 -*-
<%doc>

crate_anon/crateweb/specimen_archives/basic/test_subpanel_2.mako

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

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
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

</%doc>

<%inherit file="inherit/base.mako"/>
<%namespace name="attachments" file="snippets/attachments.mako"/>

<%block name="template_description">Test subpanels (2)</%block>

<div class="contains_embedded_attachments">

    <p>Some text. Below should be an inline attachment.</p>

    ${attachments.embedded_attachment("doctest.odt")}

</div>
