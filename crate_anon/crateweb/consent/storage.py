#!/usr/bin/env python

"""
crate_anon/crateweb/consent/storage.py

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

    This file is part of CRATE.

    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.

===============================================================================

**File system storage class and instance for the consent-to-contact system.**

"""

import logging
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.urls import get_script_prefix
from django.utils.encoding import filepath_to_uri
# noinspection PyUnresolvedReferences
from django.utils.six.moves.urllib.parse import urljoin

log = logging.getLogger(__name__)


class CustomFileSystemStorage(FileSystemStorage):
    """
    Subclasses :class:`django.core.files.storage.FileSystemStorage` to improve
    URL processing, as below.

    *Notes:*

    In order to use :func:`reverse`, ``config/urls.py`` can't import views that
    import models that use this... so use string, not actual Python object,
    references for ``urls.py``.

    However, in ``urls.py``, we also need things like ``mgr_admin_site.urls``,
    and ``consent/admin.py`` also imports ``models`` (which imports
    ``storage``). Problem. Specifically, a problem for making the URLs
    non-absolute for non-root hosting.

    So we use :func:`get_script_prefix` instead?

    - https://docs.djangoproject.com/en/1.8/ref/urlresolvers/

    But that isn't set at the time this is loaded, so that's no good either.
    The only other way to handle this would be to override the view form,
    or offer the private storage via Apache (but the latter would prevent
    proper security, so that's a no-no).

    Therefore, let's subclass
    :class:`django.core.files.storage.FileSystemStorage`, so we can make the
    change at runtime.

    """
    def url(self, name: str) -> str:
        """
        Returns the URL for a given filename.
        """
        if self.base_url is None:
            raise ValueError("This file is not accessible via a URL.")
        # log.debug("get_script_prefix(): %s" % get_script_prefix())
        return urljoin(get_script_prefix() + self.base_url,
                       filepath_to_uri(name))


privatestorage = CustomFileSystemStorage(
    location=settings.PRIVATE_FILE_STORAGE_ROOT,
    base_url='download_privatestorage',  # NB must match urls.py
)


# log.debug("privatestorage.base_url: %s" % privatestorage.base_url)
# log.debug("get_script_prefix(): %s" % get_script_prefix())
