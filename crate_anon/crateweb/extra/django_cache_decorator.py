#!/usr/bin/env python
# crate_anon/crateweb/extra/django_cache_decorator.py

"""
===============================================================================
    Copyright (C) 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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

Based on https://github.com/rchrd2/django-cache-decorator
but fixed for Python 3 / Django 1.10.

"""

import hashlib
import logging
from typing import Any, Callable, Dict, Tuple

from django.core.cache import cache  # default cache

from crate_anon.common.jsonfunc import json_encode

FunctionType = Callable[..., Any]
ArgsType = Tuple[Any]
KwargsType = Dict[str, Any]
CallSignature = Tuple[str, ArgsType, KwargsType]

log = logging.getLogger(__name__)


def get_call_signature(fn: FunctionType,
                       args: ArgsType,
                       kwargs: KwargsType) -> CallSignature:
    return fn.__qualname__, args, kwargs


def make_cache_key(call_signature: CallSignature) -> str:
    # - We have a bunch of components of arbitrary type, and we need to get
    #   a unique string out.
    # - We shouldn't use str(), because that is often poorly specified; e.g.
    #   is 'a.b.c' a TableId, or is it a ColumnId with no 'db' field?
    # - We could use repr(): sometimes that gives us helpful things that
    #   could in principle be passed to eval(), in which case repr() would
    #   be fine, but sometimes it doesn't, and gives unhelpful things like
    #   '<__main__.Thing object at 0x7ff3093ebda0>'.
    # - However, if something encodes to JSON, that representation should
    #   be reversible and thus contain the right sort of information.
    full_str = json_encode(call_signature)
    log.critical("Making cache key from: " + full_str)
    key = hashlib.md5(full_str.encode("utf-8")).hexdigest()
    return key


def django_cache_function(timeout: int = 5 * 60,
                          cache_key: str = ''):
    """
    Decorator to add caching to a function in Django.
    Uses the Django default cache.
    Args:
        timeout: timeout in seconds; use None for "never expire", as 0 means
            "do not cache".
        cache_key: optional cache key to use (if falsy, we'll invent one)
    """
    cache_key = cache_key or None

    def decorator(fn):
        def wrapper(*args, **kwargs):
            # - NOTE that Django returns None from cache.get() for "not in
            #   cache", so can't cache a None value;
            #   https://docs.djangoproject.com/en/1.10/topics/cache/#basic-usage  # noqa
            # - We need to store a bit more than just the function result
            #   anyway, to detect hash collisions when the user doesn't specify
            #   the cache_key, so we may as well use that format even if the
            #   user does specify the cache_key, and then we can store a None
            #   result properly as well.
            call_sig = get_call_signature(fn, args, kwargs)
            if cache_key:
                # User specified a cache key. This is easy.
                _cache_key = cache_key
                check_stored_call_sig = False
            else:
                # User didn't specify a cache key, so we'll do one
                # automatically. Since we do this via a hash, there is a small
                # but non-zero chance of a hash collision.
                _cache_key = make_cache_key(call_sig)
                check_stored_call_sig = True
            cache_result_tuple = cache.get(_cache_key)
            if cache_result_tuple is not None:  # found in cache
                cached_call_sig, func_result = cache_result_tuple
                if not check_stored_call_sig or cached_call_sig == call_sig:
                    log.critical("Cache hit")
                    return func_result
            # If we get here, either it wasn't in the cache, or something
            # was in the cache that matched by cache_key but was actually a
            # hash collision. Either way, we must do the real work.
            log.critical("Cache miss")
            func_result = fn(*args, **kwargs)
            cache.set(key=_cache_key, value=(call_sig, func_result),
                      timeout=timeout)
            return func_result

        return wrapper

    return decorator
