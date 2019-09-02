## -*- coding: utf-8 -*-
## crate_anon/crateweb/specimen_archives/basic/test_subpanel_1.mako
<%inherit file="base.mako"/>
<%namespace name="attachments" file="snippets/attachments.mako"/>

<%block name="template_description">Test subpanels (1)</%block>

<div class="contains_embedded_attachments">

    <p>Some text. Below should be an inline attachment.</p>

    ${attachments.embedded_attachment("doctest.pdf")}

</div>
