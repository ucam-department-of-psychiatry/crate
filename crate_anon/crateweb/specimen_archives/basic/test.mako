## -*- coding: utf-8 -*-
<%doc>

crate_anon/crateweb/specimen_archives/basic/test.mako

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
<%namespace name="attachments" file="snippets/attachments.mako"/>

<%!
from cardinal_pythonlib.httpconst import ContentType
%>

<%block name="template_description">Test page</%block>

<p>Results of an SQL query:</p>

<%
# Note the important difference between <%! ... %> for a module-level Python
# block, and <% ... %> for an "inline" Python block.

sql = """
    SELECT 1 AS one, 2 AS two, 3 AS three;
"""
cursor = execute(sql)  # or: context["query"](sql)

%>

<%include file="snippets/results_table.mako" args="cursor=cursor"/>

<p>Some files:</p>

<ul>
    <li><a href="${get_attachment_url("doctest.odt", content_type=ContentType.ODT)}">doctest.odt</a></li>
    <li><a href="${get_attachment_url("doctest.odt")}">doctest.odt</a> (autodetect Content-Type)</li>
    <li><a href="${get_attachment_url("doctest.odt", guess_content_type=False)}">doctest.odt</a> (force generic Content-Type)</li>
    <li><a href="${get_attachment_url("doctest.pdf", content_type=ContentType.PDF)}">doctest.pdf</a></li>
    <li><a href="${get_attachment_url("doctest.pdf")}">doctest.pdf</a> (autodetect Content-Type)</li>
    <li><a href="${get_attachment_url("doctest.pdf", guess_content_type=False)}">doctest.pdf</a> (force generic Content-Type)</li>
    <li><a href="${get_attachment_url("subdir/doctest2.pdf", content_type=ContentType.PDF)}">subdir/doctest2.pdf</a> (from subdirectory)</li>
    <li><a href="${get_attachment_url("/etc/passwd")}">/etc/passwd</a> (will fail)</li>
    <li><a href="${get_attachment_url("../whitelist.txt")}">../whitelist.txt</a> (will fail)</li>
</ul>

<p>Autocreated "all files" list, via more sophisticated embedded Python:</p>
${attachments.html_ul_all_downloads()}
