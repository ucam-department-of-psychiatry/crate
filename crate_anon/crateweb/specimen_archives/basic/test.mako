## -*- coding: utf-8 -*-
## crate_anon/crateweb/specimen_archives/basic/test.mako
<%inherit file="base.mako"/>
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
    <li><a href="${get_attachment_url("doctest.odt", ContentType.ODT)}">doctest.odt</a></li>
    <li><a href="${get_attachment_url("doctest.odt")}">doctest.odt</a> (autodetect Content-Type)</li>
    <li><a href="${get_attachment_url("doctest.odt", guess_content_type=False)}">doctest.odt</a> (force generic Content-Type)</li>
    <li><a href="${get_attachment_url("doctest.pdf", ContentType.PDF)}">doctest.pdf</a></li>
    <li><a href="${get_attachment_url("doctest.pdf")}">doctest.pdf</a> (autodetect Content-Type)</li>
    <li><a href="${get_attachment_url("doctest.pdf", guess_content_type=False)}">doctest.pdf</a> (force generic Content-Type)</li>
    <li><a href="${get_attachment_url("subdir/doctest2.pdf", ContentType.PDF)}">subdir/doctest2.pdf</a> (from subdirectory)</li>
    <li><a href="${get_attachment_url("/etc/passwd")}">/etc/passwd</a> (will fail)</li>
    <li><a href="${get_attachment_url("../whitelist.txt")}">../whitelist.txt</a> (will fail)</li>
</ul>

<p>Autocreated "all files" list, via more sophisticated embedded Python:</p>
${attachments.html_ul_all_downloads()}
