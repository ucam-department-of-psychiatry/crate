## -*- coding: utf-8 -*-
## crate_anon/crateweb/specimen_archives/basic/base.mako

<%!
from crate_anon.common.constants import HelpUrl
%>

<!DOCTYPE html> <!-- HTML 5 -->
<html lang="en">
    <head>
        <%block name="head">
            <%block name="title">
                <title>CRATE Archive: ${patient_id}</title>
            </%block>
            <meta charset="utf-8">
            <%block name="extra_head_start"></%block>
            <link rel="icon" type="image/png" href="${get_static_url("scrubber.png")}" >
            <link rel="stylesheet" type="text/css" href="${get_static_url("archive.css")}" >
            <%block name="extra_head_end"></%block>
        </%block>
    </head>
    <body <%block name="body_tags"></%block>>
        <div class="title_bar row">
            <%block name="title_bar">
                <div class="float_left">CRATE basic archive demo: BRCID <b>${patient_id}</b>.</div>
                <div class="float_right">
                    [ <a href="${CRATE_HOME_URL}">Return to CRATE home</a>
                    | <a href="<%block name="helpurl">${HelpUrl.archive()}</%block>">Help</a>
                    ]
                </div>
            </%block>
        </div>
        <div class="template_description">
            <%block name="template_description">
                <div class="warning">Missing template_description for ${template}</div>
            </%block>
        </div>
        <%block name="navigate_to_root">
            <div class="navigation">
                <a href="${get_template_url("root.mako")}">Go to top</a>
            </div>
        </%block>

        ${next.body()}

        <%block name="body_end"></%block>
    </body>
</html>
