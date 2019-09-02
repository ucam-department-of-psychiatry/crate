## -*- coding: utf-8 -*-
## crate_anon/crateweb/specimen_archives/basic/snippets/attachments.mako

<%!

# =============================================================================
# Imports
# =============================================================================

import os
from typing import Generator

from cardinal_pythonlib.httpconst import ContentType
from django.conf import settings

from crate_anon.crateweb.core.constants import SettingsKeys
from crate_anon.crateweb.core.utils import guess_mimetype


# =============================================================================
# Functions
# =============================================================================

def gen_downloadable_filenames() -> Generator[str, None, None]:
    """
    Generates filenames that are permissible for download.
    """
    rootdir = getattr(
        settings, SettingsKeys.ARCHIVE_ATTACHMENT_DIR, "")
    if not rootdir:
        return
    for dir_, subdirs, files in os.walk(rootdir, topdown=True):
        if dir_ == rootdir:
            for filename in files:
                yield filename  # don't prepend pointless "./"
        else:
            final_dir = os.path.relpath(dir_, rootdir)
            for filename in files:
                yield os.path.join(final_dir, filename)

%>

<%def name="html_ul_all_downloads()">
    ## HTML list to download all files.
    <ul>
        %for filename in gen_downloadable_filenames():
            <li><a href="${attachment_url(filename)}">${filename}</a></li>
        %endfor
    </ul>
</%def>


<%def name="embedded_attachment(filename)">
    ## HTML to show an attachment (such as a PDF) within an HTML element.
    <%
        url = attachment_url(filename)
        content_type = guess_mimetype(filename, default=ContentType.TEXT)
    %>
    <%doc>

    See https://stackoverflow.com/questions/2740297/display-adobe-pdf-inside-a-div.

    (1) This works, but you can't set the height of the "object" except in
        pixels:
        https://developer.mozilla.org/en-US/docs/Web/HTML/Element/object#Attributes

        <object
                class="embedded_attachment"
                data="${url}"
                type="${content_type}">
            If this attachment doesn’t load, see
            <a href="${url}">${filename}</a>
        </object>

    (2) This is less good (re scroll bars etc.), and similarly re height:

        <iframe
                class="embedded_attachment"
                src="${url}" />

    (3) <embed> is relatively deprecated and similarly only permits absolute
        height:
        https://developer.mozilla.org/en-US/docs/Web/HTML/Element/embed

    (4) Aha! Use min-height and vh units.
        https://stackoverflow.com/questions/25766131/embed-pdf-at-full-height

        A vh unit is a percentage of the viewport:
        https://developer.mozilla.org/en-US/docs/Learn/CSS/Building_blocks/Values_and_units

    </%doc>
    <object
            class="embedded_attachment"
            data="${url}"
            type="${content_type}">
        The attachment couldn’t be displayed inline. Download it as
        <a href="${url}">${filename}</a>
    </object>
</%def>