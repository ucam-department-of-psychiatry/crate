#!/usr/bin/env python3
# anonymise/anon_hash.py

"""
Config class for CRATE anonymiser.

Author: Rudolf Cardinal
Created at: 22 Nov 2015
Last update: 22 Nov 2015

Copyright/licensing:

    Copyright (C) 2015-2015 Rudolf Cardinal (rudolf@pobox.com).
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


# =============================================================================
# Hashers
# =============================================================================

class GenericHasher(object):
    def __init__(self, hashfunc, salt):
        self.hashfunc = hashfunc
        self.salt = salt
        self.salt_bytes = str(salt).encode('utf-8')

    def hash(self, raw):
        raw_bytes = str(raw).encode('utf-8')
        return self.hashfunc(self.salt_bytes + raw_bytes).hexdigest()


class MD5Hasher(GenericHasher):
    def __init__(self, salt):
        super().__init__(hashlib.md5, salt)


class SHA256Hasher(GenericHasher):
    def __init__(self, salt):
        super().__init__(hashlib.sha256, salt)


class SHA512Hasher(GenericHasher):
    def __init__(self, salt):
        super().__init__(hashlib.sha512, salt)
