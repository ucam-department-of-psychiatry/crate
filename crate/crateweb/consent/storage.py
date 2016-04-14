#!/usr/bin/env python3
# consent/storage.py

import logging
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.core.urlresolvers import get_script_prefix
from django.utils.encoding import filepath_to_uri
# noinspection PyUnresolvedReferences
from django.utils.six.moves.urllib.parse import urljoin

log = logging.getLogger(__name__)


class CustomFileSystemStorage(FileSystemStorage):
    def url(self, name):
        if self.base_url is None:
            raise ValueError("This file is not accessible via a URL.")
        # log.debug("get_script_prefix(): %s" % get_script_prefix())
        return urljoin(get_script_prefix() + self.base_url,
                       filepath_to_uri(name))


privatestorage = CustomFileSystemStorage(
    location=settings.PRIVATE_FILE_STORAGE_ROOT,
    base_url='download_privatestorage',  # NB must match urls.py
)

"""
In order to use reverse(), config/urls.py can't import views that
import models that use this... so use string, not actual Python object,
references for urls.py

However, in urls.py, we also need things like mgr_admin_site.urls,
and consent/admin.py also imports models (which import storage).
Problem.
Specifically, a problem for making the URLs non-absolute for non-root
hosting.

So we use get_script_prefix() instead?
https://docs.djangoproject.com/en/1.8/ref/urlresolvers/
But that isn't set at the time this is loaded, so that's no good either.
The only other way to handle this would be to override the view form,
or offer the private storage via Apache (but the latter would prevent
proper security, so that's a no-no).

Therefore, let's subclass FileSystemStorage, so we can make the change at
runtime.
"""

# log.debug("privatestorage.base_url: %s" % privatestorage.base_url)
# log.debug("get_script_prefix(): %s" % get_script_prefix())
