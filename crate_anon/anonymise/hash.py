#!/usr/bin/env python3
# crate_anon/anonymise/anon_hash.py

"""
Config class for CRATE anonymiser.

Author: Rudolf Cardinal
Created at: 22 Nov 2015
Last update: 22 Nov 2015

Copyright/licensing:

    Copyright (C) 2015-2016 Rudolf Cardinal (rudolf@pobox.com).
    Department of Psychiatry, University of Cambridge.

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

import hashlib
import hmac


# =============================================================================
# Base classes
# =============================================================================

class GenericHasher(object):
    def hash(self, raw):
        """The public interface to a hasher."""
        raise NotImplementedError()


# =============================================================================
# Simple salted hashers.
# Note that these are vulnerable to attack: if an attacker knows a
# (message, digest) pair, it may be able to calculate another.
# See https://benlog.com/2008/06/19/dont-hash-secrets/ and
# http://citeseerx.ist.psu.edu/viewdoc/summary?doi=10.1.1.134.8430
# +++ You should use HMAC instead if the thing you are hashing is secret. +++
# =============================================================================

class GenericSaltedHasher(GenericHasher):
    def __init__(self, hashfunc, salt):
        self.hashfunc = hashfunc
        self.salt_bytes = str(salt).encode('utf-8')

    def hash(self, raw):
        raw_bytes = str(raw).encode('utf-8')
        return self._hash(raw_bytes).hexdigest()

    def _hash(self, raw_bytes):
        return self.hashfunc(self.salt_bytes + raw_bytes)


class MD5Hasher(GenericSaltedHasher):
    """MD5 is cryptographically FLAWED; avoid."""
    def __init__(self, salt):
        super().__init__(hashlib.md5, salt)


class SHA256Hasher(GenericSaltedHasher):
    def __init__(self, salt):
        super().__init__(hashlib.sha256, salt)


class SHA512Hasher(GenericSaltedHasher):
    def __init__(self, salt):
        super().__init__(hashlib.sha512, salt)


# =============================================================================
# HMAC hashers. Better, if what you are hashing is secret.
# =============================================================================

class GenericHmacHasher(GenericHasher):
    def __init__(self, digestmod, key):
        self.key_bytes = str(key).encode('utf-8')
        self.digestmod = digestmod

    def hash(self, raw):
        raw_bytes = str(raw).encode('utf-8')
        hmac_obj = hmac.new(key=self.key_bytes, msg=raw_bytes,
                            digestmod=self.digestmod)
        return hmac_obj.hexdigest()


class HmacMD5Hasher(GenericHmacHasher):
    def __init__(self, key):
        super().__init__(hashlib.md5, key)


class HmacSHA256Hasher(GenericHmacHasher):
    def __init__(self, key):
        super().__init__(hashlib.sha256, key)


class HmacSHA512Hasher(GenericHmacHasher):
    def __init__(self, key):
        super().__init__(hashlib.sha512, key)
