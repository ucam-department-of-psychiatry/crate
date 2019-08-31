## root.mako
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
  </ul>
</div>
