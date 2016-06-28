#!/usr/bin/env python3
# crate_anon/crateweb/extra/request_cache.py

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

    def process_request(self, request):
        cache = _request_cache.get(currentThread()) or RequestCache()
        _request_cache[currentThread()] = cache

        cache.clear()
