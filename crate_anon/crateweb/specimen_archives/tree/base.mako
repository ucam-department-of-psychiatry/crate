## -*- coding: utf-8 -*-
## crate_anon/crateweb/specimen_archives/tree/base.mako

<!DOCTYPE html> <!-- HTML 5 -->
<html lang="en">
    <head>
        <%block name="head">
            <%block name="title">
                <title>CRATE Archive: ${patient_id}</title>
            </%block>
            <meta charset="utf-8">
            <%block name="extra_head_start"></%block>
            <link rel="icon" type="image/png" href="${static_url("scrubber.png")}" >
            <link rel="stylesheet" type="text/css" href="${static_url("archive.css")}" >
            <%block name="extra_head_end"></%block>
        </%block>
    </head>
    <body <%block name="body_tags"></%block>>
        ${next.body()}

        <%block name="body_end"></%block>
    </body>
</html>
