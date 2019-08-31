## base.mako

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
            <link rel="icon" type="image/png" href="${URL_FAVICON_PNG}" >
            <style type="text/css">
                <%include file="css/archive.css" />
            </style>
            <%block name="extra_head_end"></%block>
        </%block>
    </head>
    <body>
        <div class="title_bar contains_floats">
            <%block name="title_bar">
                <div class="left">CRATE archive: BRCID <b>${patient_id}</b>.</div>
                <div class="right">
                    [<a href="${CRATE_HOME_URL}">Return to CRATE home</a>
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
                <a href="${archive_url("root.mako")}">Go to top</a>
            </div>
        </%block>

        ${next.body()}

        <%block name="body_end"></%block>
    </body>
</html>
