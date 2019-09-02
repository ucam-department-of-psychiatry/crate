## -*- coding: utf-8 -*-
## crate_anon/crateweb/specimen_archives/tree/snippets/attachments.mako

<%!

# =============================================================================
# Imports
# =============================================================================

from typing import Callable, Generator

from cardinal_pythonlib.httpconst import ContentType

from crate_anon.crateweb.core.utils import (
    guess_mimetype,
    javascript_quoted_string_from_html,
)


# =============================================================================
# Functions
# =============================================================================

def js_embedded_attachment_html(attachment_url: Callable,
                                filename: str) -> str:
    """
    Quoted Javascript string of HTML to show an attachment (such as a PDF)
    within an HTML element.
    """
    url = attachment_url(filename)
    content_type = guess_mimetype(filename, default=ContentType.TEXT)
    html = f"""
        <object
                class="embedded_attachment"
                data="{url}"
                type="{content_type}">
            <div class="obscure_spinner">
                The attachment couldn’t be displayed inline. Download it as
                <a href="{url}">{filename}</a>
            </div>
        </object>
    """
    return javascript_quoted_string_from_html(html)

%>

<%def name="html_ul_all_downloads()">
    ## HTML list to download all files.
    <ul>
        %for filename in gen_downloadable_filenames():
            <li><a href="${attachment_url(filename)}">${filename}</a></li>
        %endfor
    </ul>
</%def>


<%def name="embedded_attachment(filename)">${js_embedded_attachment_html(attachment_url, filename)}</%def>
## ... no newlines!
