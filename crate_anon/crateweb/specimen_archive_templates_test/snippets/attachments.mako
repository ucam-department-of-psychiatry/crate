## attachments.mako

<%!

# =============================================================================
# Imports
# =============================================================================

import os
from typing import Generator

from django.conf import settings

from crate_anon.crateweb.core.constants import SettingsKeys


# =============================================================================
# Functions
# =============================================================================

def gen_downloadable_filenames() -> Generator[str, None, None]:
    """
    Generates filenames that are permissible for download.
    """
    rootdir = _archive_attachment_root_dir = getattr(
        settings, SettingsKeys.ARCHIVE_ATTACHMENT_ROOT_DIR, "")
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
