#!/usr/bin/env python
# crate_anon/crateweb/extra/request_cache.py

"""
===============================================================================
    Copyright © 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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
"""

# http://stackoverflow.com/questions/3151469/per-request-cache-in-django

from threading import currentThread
from django.core.cache.backends.locmem import LocMemCache

_request_cache = {}
_installed_middleware = False


def get_request_cache():
    assert _installed_middleware, 'RequestCacheMiddleware not loaded'
    return _request_cache[currentThread()]


# LocMemCache is a threadsafe local memory cache
class RequestCache(LocMemCache):
    def __init__(self):
        name = 'locmemcache@%i' % hash(currentThread())
        params = dict()
        super(RequestCache, self).__init__(name, params)


class RequestCacheMiddleware(object):
    def __init__(self):
        global _installed_middleware
        _installed_middleware = True

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def process_request(self, request):
        cache = _request_cache.get(currentThread()) or RequestCache()
        _request_cache[currentThread()] = cache

        cache.clear()
