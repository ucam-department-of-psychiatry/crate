#!/usr/bin/env python3
# core/storage.py

import logging
logger = logging.getLogger(__name__)
from django.contrib.staticfiles.storage import StaticFilesStorage
from django.core.urlresolvers import get_script_prefix
from django.utils.encoding import filepath_to_uri
from django.utils.six.moves.urllib.parse import urljoin


class CustomStaticFilesStorage(StaticFilesStorage):
    """
    As for CustomFileSystemStorage.
    Used to redirect static requests sensibly in a non-root Django
    environment.
    """
    def url(self, name):
        if self.base_url is None:
            raise ValueError("This file is not accessible via a URL.")
        logger.debug("get_script_prefix(): %s" % get_script_prefix())
        return urljoin(get_script_prefix() + self.base_url,
                       filepath_to_uri(name))
