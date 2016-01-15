#!/usr/bin/python
# -*- encoding: utf8 -*-

"""WSGI middleware to disable client-side caching.

Author: Rudolf Cardinal (rudolf@pobox.com)
Created:     09 Jan 2016
Last update: 09 Jan 2016

Copyright/licensing:

    Copyright (C) 2016-2016 Rudolf Cardinal (rudolf@pobox.com).

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
"""

import logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())
# logger.setLevel(logging.DEBUG)


# =============================================================================
# DisableClientSideCachingMiddleware
# =============================================================================
# http://stackoverflow.com/questions/49547/making-sure-a-web-page-is-not-cached-across-all-browsers  # noqa
# http://stackoverflow.com/questions/3859097/how-to-add-http-headers-in-wsgi-middleware  # noqa

def add_never_cache_headers(headers):
    headers.append(("Cache-Control", "no-cache, no-store, must-revalidate"))  # HTTP 1.1  # noqa
    headers.append(("Pragma", "no-cache"))  # HTTP 1.0
    headers.append(("Expires", "0"))  # Proxies


class DisableClientSideCachingMiddleware(object):
    """WSGI middleware to disable client-side caching."""

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):

        def custom_start_response(status, headers, exc_info=None):
            add_never_cache_headers(headers)
            logger.debug("HTTP status {}, headers {}".format(status, headers))
            return start_response(status, headers, exc_info)

        return self.app(environ, custom_start_response)
