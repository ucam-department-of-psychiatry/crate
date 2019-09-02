## -*- coding: utf-8 -*-
## crate_anon/crateweb/specimen_archives/basic/root.mako
<%inherit file="base.mako"/>

<%block name="template_description">Choose an area to explore:</%block>

## Don't show the "navigate to root" link on the root page.
<%block name="navigate_to_root"></%block>

<div class="navigation">
  <ul>
    <li><a href="${archive_url("clinical_documents.mako")}">Clinical documents</a></li>
    <li><a href="${archive_url("diagnoses.mako")}">Diagnoses</a></li>
    <li><a href="${archive_url("progress_notes.mako")}">Progress notes</a></li>
    <li><a href="${archive_url("search.mako")}">Search</a></li>
    <li><a href="${archive_url("test.mako")}">Test page</a></li>
    <li><a href="${archive_url("test_subpanel_1.mako")}">Test sub-panels (1)</a></li>
    <li><a href="${archive_url("test_subpanel_2.mako")}">Test sub-panels (2)</a></li>
  </ul>
</div>
