#!/usr/bin/env python
# crate_anon/anonymise/hash.py

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
import sys
from typing import Any, Callable, Tuple, Union
from crate_anon.common.timing import MultiTimerContext, timer

try:
    import mmh3
except ImportError:
    mmh3 = None

# try:
#     import xxhash
#     pyhashxx = None
# except ImportError:
#     xxhash = None
#     import pyhashxx


# https://docs.python.org/3/library/platform.html#platform.architecture
IS_64_BIT = sys.maxsize > 2 ** 32
TIMING_HASH = "hash"


# =============================================================================
# Base classes
# =============================================================================

class GenericHasher(object):
    def hash(self, raw: Any) -> str:
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
    def __init__(self, hashfunc: Callable[[bytes], Any], salt: str) -> None:
        self.hashfunc = hashfunc
        self.salt_bytes = salt.encode('utf-8')

    def hash(self, raw: Any) -> str:
        with MultiTimerContext(timer, TIMING_HASH):
            raw_bytes = str(raw).encode('utf-8')
            return self.hashfunc(self.salt_bytes + raw_bytes).hexdigest()


class MD5Hasher(GenericSaltedHasher):
    """MD5 is cryptographically FLAWED; avoid."""
    def __init__(self, salt: str) -> None:
        super().__init__(hashlib.md5, salt)


class SHA256Hasher(GenericSaltedHasher):
    def __init__(self, salt: str) -> None:
        super().__init__(hashlib.sha256, salt)


class SHA512Hasher(GenericSaltedHasher):
    def __init__(self, salt: str) -> None:
        super().__init__(hashlib.sha512, salt)


# =============================================================================
# HMAC hashers. Better, if what you are hashing is secret.
# =============================================================================

class GenericHmacHasher(GenericHasher):
    def __init__(self, digestmod: Any, key: str) -> None:
        self.key_bytes = str(key).encode('utf-8')
        self.digestmod = digestmod

    def hash(self, raw: Any) -> str:
        with MultiTimerContext(timer, TIMING_HASH):
            raw_bytes = str(raw).encode('utf-8')
            hmac_obj = hmac.new(key=self.key_bytes, msg=raw_bytes,
                                digestmod=self.digestmod)
            return hmac_obj.hexdigest()


class HmacMD5Hasher(GenericHmacHasher):
    def __init__(self, key: str) -> None:
        super().__init__(hashlib.md5, key)


class HmacSHA256Hasher(GenericHmacHasher):
    def __init__(self, key: str) -> None:
        super().__init__(hashlib.sha256, key)


class HmacSHA512Hasher(GenericHmacHasher):
    def __init__(self, key: str) -> None:
        super().__init__(hashlib.sha512, key)


# =============================================================================
# Support functions
# =============================================================================

def to_bytes(data: Any) -> bytearray:
    if isinstance(data, int):
        return bytearray([data])
    return bytearray(data, encoding='latin-1')
    # http://stackoverflow.com/questions/7585435/best-way-to-convert-string-to-bytes-in-python-3  # noqa
    # http://stackoverflow.com/questions/10459067/how-to-convert-my-bytearrayb-x9e-x18k-x9a-to-something-like-this-x9e-x1  # noqa


def to_str(data: Any) -> str:
    return str(data)


def twos_comp_to_signed(val: int, n_bits: int) -> int:
    # http://stackoverflow.com/questions/1604464/twos-complement-in-python
    assert n_bits % 8 == 0, "Must specify a whole number of bytes"
    n_bytes = n_bits // 8
    b = val.to_bytes(n_bytes, byteorder=sys.byteorder, signed=False)
    return int.from_bytes(b, byteorder=sys.byteorder, signed=True)


def signed_to_twos_comp(val: int, n_bits: int) -> int:
    assert n_bits % 8 == 0, "Must specify a whole number of bytes"
    n_bytes = n_bits // 8
    b = val.to_bytes(n_bytes, byteorder=sys.byteorder, signed=True)
    return int.from_bytes(b, byteorder=sys.byteorder, signed=False)


def bytes_to_long(bytesdata: bytes) -> int:
    assert len(bytesdata) == 8
    return sum((b << (k * 8) for k, b in enumerate(bytesdata)))


# =============================================================================
# Pure Python implementations of MurmurHash3
# =============================================================================

# -----------------------------------------------------------------------------
# SO ones
# -----------------------------------------------------------------------------

def murmur3_x86_32(data: Union[bytes, bytearray], seed: int = 0) -> int:
    # http://stackoverflow.com/questions/13305290/is-there-a-pure-python-implementation-of-murmurhash  # noqa
    c1 = 0xcc9e2d51
    c2 = 0x1b873593

    length = len(data)
    h1 = seed
    rounded_end = (length & 0xfffffffc)  # round down to 4 byte block
    for i in range(0, rounded_end, 4):
        # little endian load order
        # RNC: removed ord() calls
        k1 = (data[i] & 0xff) | ((data[i + 1] & 0xff) << 8) | \
             ((data[i + 2] & 0xff) << 16) | (data[i + 3] << 24)
        k1 *= c1
        k1 = (k1 << 15) | ((k1 & 0xffffffff) >> 17)  # ROTL32(k1, 15)
        k1 *= c2

        h1 ^= k1
        h1 = (h1 << 13) | ((h1 & 0xffffffff) >> 19)  # ROTL32(h1, 13)
        h1 = h1 * 5 + 0xe6546b64

    # tail
    k1 = 0

    val = length & 0x03
    if val == 3:
        k1 = (data[rounded_end + 2] & 0xff) << 16
    # fallthrough
    if val in [2, 3]:
        k1 |= (data[rounded_end + 1] & 0xff) << 8
    # fallthrough
    if val in [1, 2, 3]:
        k1 |= data[rounded_end] & 0xff
        k1 *= c1
        k1 = (k1 << 15) | ((k1 & 0xffffffff) >> 17)  # ROTL32(k1, 15)
        k1 *= c2
        h1 ^= k1

    # finalization
    h1 ^= length

    # fmix(h1)
    h1 ^= ((h1 & 0xffffffff) >> 16)
    h1 *= 0x85ebca6b
    h1 ^= ((h1 & 0xffffffff) >> 13)
    h1 *= 0xc2b2ae35
    h1 ^= ((h1 & 0xffffffff) >> 16)

    return h1 & 0xffffffff


def murmur3_64(data: Union[bytes, bytearray], seed: int = 19820125) -> int:
    # http://stackoverflow.com/questions/13305290/is-there-a-pure-python-implementation-of-murmurhash  # noqa
    # ... plus RNC bugfixes
    m = 0xc6a4a7935bd1e995
    r = 47

    mask = 2 ** 64 - 1

    length = len(data)

    h = seed ^ ((m * length) & mask)

    offset = (length // 8) * 8
    # RNC: was /, but for Python 3 that gives float; brackets added for clarity
    for ll in range(0, offset, 8):
        k = bytes_to_long(data[ll:ll + 8])
        k = (k * m) & mask
        k ^= (k >> r) & mask
        k = (k * m) & mask
        h = (h ^ k)
        h = (h * m) & mask

    l = length & 7

    if l >= 7:
        h = (h ^ (data[offset + 6] << 48))

    if l >= 6:
        h = (h ^ (data[offset + 5] << 40))

    if l >= 5:
        h = (h ^ (data[offset + 4] << 32))

    if l >= 4:
        h = (h ^ (data[offset + 3] << 24))

    if l >= 3:
        h = (h ^ (data[offset + 2] << 16))

    if l >= 2:
        h = (h ^ (data[offset + 1] << 8))

    if l >= 1:
        h = (h ^ data[offset])
        h = (h * m) & mask

    h ^= (h >> r) & mask
    h = (h * m) & mask
    h ^= (h >> r) & mask

    return h


# -----------------------------------------------------------------------------
# pymmh3 ones, renamed, with some bugfixes
# -----------------------------------------------------------------------------

def pymmh3_hash128_x64(key: Union[bytes, bytearray], seed: int) -> int:
    """Implements 128bit murmur3 hash for x64."""

    def fmix(k):
        k ^= k >> 33
        k = (k * 0xff51afd7ed558ccd) & 0xFFFFFFFFFFFFFFFF
        k ^= k >> 33
        k = (k * 0xc4ceb9fe1a85ec53) & 0xFFFFFFFFFFFFFFFF
        k ^= k >> 33
        return k

    length = len(key)
    nblocks = int(length / 16)

    h1 = seed
    h2 = seed

    c1 = 0x87c37b91114253d5
    c2 = 0x4cf5ad432745937f

    # body
    for block_start in range(0, nblocks * 8, 8):
        # ??? big endian?
        k1 = (
            key[2 * block_start + 7] << 56 |
            key[2 * block_start + 6] << 48 |
            key[2 * block_start + 5] << 40 |
            key[2 * block_start + 4] << 32 |
            key[2 * block_start + 3] << 24 |
            key[2 * block_start + 2] << 16 |
            key[2 * block_start + 1] << 8 |
            key[2 * block_start + 0]
        )

        k2 = (
            key[2 * block_start + 15] << 56 |
            key[2 * block_start + 14] << 48 |
            key[2 * block_start + 13] << 40 |
            key[2 * block_start + 12] << 32 |
            key[2 * block_start + 11] << 24 |
            key[2 * block_start + 10] << 16 |
            key[2 * block_start + 9] << 8 |
            key[2 * block_start + 8]
        )

        k1 = (c1 * k1) & 0xFFFFFFFFFFFFFFFF
        k1 = (k1 << 31 | k1 >> 33) & 0xFFFFFFFFFFFFFFFF  # inlined ROTL64
        k1 = (c2 * k1) & 0xFFFFFFFFFFFFFFFF
        h1 ^= k1

        h1 = (h1 << 27 | h1 >> 37) & 0xFFFFFFFFFFFFFFFF  # inlined ROTL64
        h1 = (h1 + h2) & 0xFFFFFFFFFFFFFFFF
        h1 = (h1 * 5 + 0x52dce729) & 0xFFFFFFFFFFFFFFFF

        k2 = (c2 * k2) & 0xFFFFFFFFFFFFFFFF
        k2 = (k2 << 33 | k2 >> 31) & 0xFFFFFFFFFFFFFFFF  # inlined ROTL64
        k2 = (c1 * k2) & 0xFFFFFFFFFFFFFFFF
        h2 ^= k2

        h2 = (h2 << 31 | h2 >> 33) & 0xFFFFFFFFFFFFFFFF  # inlined ROTL64
        h2 = (h1 + h2) & 0xFFFFFFFFFFFFFFFF
        h2 = (h2 * 5 + 0x38495ab5) & 0xFFFFFFFFFFFFFFFF

    # tail
    tail_index = nblocks * 16
    k1 = 0
    k2 = 0
    tail_size = length & 15

    if tail_size >= 15:
        k2 ^= key[tail_index + 14] << 48
    if tail_size >= 14:
        k2 ^= key[tail_index + 13] << 40
    if tail_size >= 13:
        k2 ^= key[tail_index + 12] << 32
    if tail_size >= 12:
        k2 ^= key[tail_index + 11] << 24
    if tail_size >= 11:
        k2 ^= key[tail_index + 10] << 16
    if tail_size >= 10:
        k2 ^= key[tail_index + 9] << 8
    if tail_size >= 9:
        k2 ^= key[tail_index + 8]

    if tail_size > 8:
        k2 = (k2 * c2) & 0xFFFFFFFFFFFFFFFF
        k2 = (k2 << 33 | k2 >> 31) & 0xFFFFFFFFFFFFFFFF  # inlined ROTL64
        k2 = (k2 * c1) & 0xFFFFFFFFFFFFFFFF
        h2 ^= k2

    if tail_size >= 8:
        k1 ^= key[tail_index + 7] << 56
    if tail_size >= 7:
        k1 ^= key[tail_index + 6] << 48
    if tail_size >= 6:
        k1 ^= key[tail_index + 5] << 40
    if tail_size >= 5:
        k1 ^= key[tail_index + 4] << 32
    if tail_size >= 4:
        k1 ^= key[tail_index + 3] << 24
    if tail_size >= 3:
        k1 ^= key[tail_index + 2] << 16
    if tail_size >= 2:
        k1 ^= key[tail_index + 1] << 8
    if tail_size >= 1:
        k1 ^= key[tail_index + 0]

    if tail_size > 0:
        k1 = (k1 * c1) & 0xFFFFFFFFFFFFFFFF
        k1 = (k1 << 31 | k1 >> 33) & 0xFFFFFFFFFFFFFFFF  # inlined ROTL64
        k1 = (k1 * c2) & 0xFFFFFFFFFFFFFFFF
        h1 ^= k1

    # finalization
    h1 ^= length
    h2 ^= length

    h1 = (h1 + h2) & 0xFFFFFFFFFFFFFFFF
    h2 = (h1 + h2) & 0xFFFFFFFFFFFFFFFF

    h1 = fmix(h1)
    h2 = fmix(h2)

    h1 = (h1 + h2) & 0xFFFFFFFFFFFFFFFF
    h2 = (h1 + h2) & 0xFFFFFFFFFFFFFFFF

    return h2 << 64 | h1


def pymmh3_hash128_x86(key: Union[bytes, bytearray], seed: int) -> int:
    """Implements 128bit murmur3 hash for x86."""

    def fmix(h):
        h ^= h >> 16
        h = (h * 0x85ebca6b) & 0xFFFFFFFF
        h ^= h >> 13
        h = (h * 0xc2b2ae35) & 0xFFFFFFFF
        h ^= h >> 16
        return h

    length = len(key)
    nblocks = int(length / 16)

    h1 = seed
    h2 = seed
    h3 = seed
    h4 = seed

    c1 = 0x239b961b
    c2 = 0xab0e9789
    c3 = 0x38b34ae5
    c4 = 0xa1e38b93

    # body
    for block_start in range(0, nblocks * 16, 16):
        k1 = (
            key[block_start + 3] << 24 |
            key[block_start + 2] << 16 |
            key[block_start + 1] << 8 |
            key[block_start + 0]
        )
        k2 = (
            key[block_start + 7] << 24 |
            key[block_start + 6] << 16 |
            key[block_start + 5] << 8 |
            key[block_start + 4]
        )
        k3 = (
            key[block_start + 11] << 24 |
            key[block_start + 10] << 16 |
            key[block_start + 9] << 8 |
            key[block_start + 8]
        )
        k4 = (
            key[block_start + 15] << 24 |
            key[block_start + 14] << 16 |
            key[block_start + 13] << 8 |
            key[block_start + 12]
        )

        k1 = (c1 * k1) & 0xFFFFFFFF
        k1 = (k1 << 15 | k1 >> 17) & 0xFFFFFFFF  # inlined ROTL32
        k1 = (c2 * k1) & 0xFFFFFFFF
        h1 ^= k1

        h1 = (h1 << 19 | h1 >> 13) & 0xFFFFFFFF  # inlined ROTL32
        h1 = (h1 + h2) & 0xFFFFFFFF
        h1 = (h1 * 5 + 0x561ccd1b) & 0xFFFFFFFF

        k2 = (c2 * k2) & 0xFFFFFFFF
        k2 = (k2 << 16 | k2 >> 16) & 0xFFFFFFFF  # inlined ROTL32
        k2 = (c3 * k2) & 0xFFFFFFFF
        h2 ^= k2

        h2 = (h2 << 17 | h2 >> 15) & 0xFFFFFFFF  # inlined ROTL32
        h2 = (h2 + h3) & 0xFFFFFFFF
        h2 = (h2 * 5 + 0x0bcaa747) & 0xFFFFFFFF

        k3 = (c3 * k3) & 0xFFFFFFFF
        k3 = (k3 << 17 | k3 >> 15) & 0xFFFFFFFF  # inlined ROTL32
        k3 = (c4 * k3) & 0xFFFFFFFF
        h3 ^= k3

        h3 = (h3 << 15 | h3 >> 17) & 0xFFFFFFFF  # inlined ROTL32
        h3 = (h3 + h4) & 0xFFFFFFFF
        h3 = (h3 * 5 + 0x96cd1c35) & 0xFFFFFFFF

        k4 = (c4 * k4) & 0xFFFFFFFF
        k4 = (k4 << 18 | k4 >> 14) & 0xFFFFFFFF  # inlined ROTL32
        k4 = (c1 * k4) & 0xFFFFFFFF
        h4 ^= k4

        h4 = (h4 << 13 | h4 >> 19) & 0xFFFFFFFF  # inlined ROTL32
        h4 = (h1 + h4) & 0xFFFFFFFF
        h4 = (h4 * 5 + 0x32ac3b17) & 0xFFFFFFFF

    # tail
    tail_index = nblocks * 16
    k1 = 0
    k2 = 0
    k3 = 0
    k4 = 0
    tail_size = length & 15

    if tail_size >= 15:
        k4 ^= key[tail_index + 14] << 16
    if tail_size >= 14:
        k4 ^= key[tail_index + 13] << 8
    if tail_size >= 13:
        k4 ^= key[tail_index + 12]

    if tail_size > 12:
        k4 = (k4 * c4) & 0xFFFFFFFF
        k4 = (k4 << 18 | k4 >> 14) & 0xFFFFFFFF  # inlined ROTL32
        k4 = (k4 * c1) & 0xFFFFFFFF
        h4 ^= k4

    if tail_size >= 12:
        k3 ^= key[tail_index + 11] << 24
    if tail_size >= 11:
        k3 ^= key[tail_index + 10] << 16
    if tail_size >= 10:
        k3 ^= key[tail_index + 9] << 8
    if tail_size >= 9:
        k3 ^= key[tail_index + 8]

    if tail_size > 8:
        k3 = (k3 * c3) & 0xFFFFFFFF
        k3 = (k3 << 17 | k3 >> 15) & 0xFFFFFFFF  # inlined ROTL32
        k3 = (k3 * c4) & 0xFFFFFFFF
        h3 ^= k3

    if tail_size >= 8:
        k2 ^= key[tail_index + 7] << 24
    if tail_size >= 7:
        k2 ^= key[tail_index + 6] << 16
    if tail_size >= 6:
        k2 ^= key[tail_index + 5] << 8
    if tail_size >= 5:
        k2 ^= key[tail_index + 4]

    if tail_size > 4:
        k2 = (k2 * c2) & 0xFFFFFFFF
        k2 = (k2 << 16 | k2 >> 16) & 0xFFFFFFFF  # inlined ROTL32
        k2 = (k2 * c3) & 0xFFFFFFFF
        h2 ^= k2

    if tail_size >= 4:
        k1 ^= key[tail_index + 3] << 24
    if tail_size >= 3:
        k1 ^= key[tail_index + 2] << 16
    if tail_size >= 2:
        k1 ^= key[tail_index + 1] << 8
    if tail_size >= 1:
        k1 ^= key[tail_index + 0]

    if tail_size > 0:
        k1 = (k1 * c1) & 0xFFFFFFFF
        k1 = (k1 << 15 | k1 >> 17) & 0xFFFFFFFF  # inlined ROTL32
        k1 = (k1 * c2) & 0xFFFFFFFF
        h1 ^= k1

    # finalization
    h1 ^= length
    h2 ^= length
    h3 ^= length
    h4 ^= length

    h1 = (h1 + h2) & 0xFFFFFFFF
    h1 = (h1 + h3) & 0xFFFFFFFF
    h1 = (h1 + h4) & 0xFFFFFFFF
    h2 = (h1 + h2) & 0xFFFFFFFF
    h3 = (h1 + h3) & 0xFFFFFFFF
    h4 = (h1 + h4) & 0xFFFFFFFF

    h1 = fmix(h1)
    h2 = fmix(h2)
    h3 = fmix(h3)
    h4 = fmix(h4)

    h1 = (h1 + h2) & 0xFFFFFFFF
    h1 = (h1 + h3) & 0xFFFFFFFF
    h1 = (h1 + h4) & 0xFFFFFFFF
    h2 = (h1 + h2) & 0xFFFFFFFF
    h3 = (h1 + h3) & 0xFFFFFFFF
    h4 = (h1 + h4) & 0xFFFFFFFF

    return h4 << 96 | h3 << 64 | h2 << 32 | h1


def pymmh3_hash128(key: Union[bytes, bytearray],
                   seed: int = 0,
                   x64arch: bool = True) -> int:
    """Implements 128bit murmur3 hash."""
    if x64arch:
        return pymmh3_hash128_x64(key, seed)
    else:
        return pymmh3_hash128_x86(key, seed)


def pymmh3_hash64(key: Union[bytes, bytearray],
                  seed: int = 0,
                  x64arch: bool = True) -> Tuple[int, int]:
    """Implements 64bit murmur3 hash. Returns a tuple."""

    hash_128 = pymmh3_hash128(key, seed, x64arch)

    unsigned_val1 = hash_128 & 0xFFFFFFFFFFFFFFFF  # low half
    if unsigned_val1 & 0x8000000000000000 == 0:
        signed_val1 = unsigned_val1
    else:
        signed_val1 = -((unsigned_val1 ^ 0xFFFFFFFFFFFFFFFF) + 1)

    unsigned_val2 = (hash_128 >> 64) & 0xFFFFFFFFFFFFFFFF  # high half
    if unsigned_val2 & 0x8000000000000000 == 0:
        signed_val2 = unsigned_val2
    else:
        signed_val2 = -((unsigned_val2 ^ 0xFFFFFFFFFFFFFFFF) + 1)

    return signed_val1, signed_val2


# =============================================================================
# Checks
# =============================================================================

def compare_python_to_reference_murmur3_32(data: Any, seed=0) -> None:
    assert mmh3, "Need mmh3 module"
    c_data = to_str(data)
    c_signed = mmh3.hash(c_data, seed=seed)  # 32 bit
    py_data = to_bytes(c_data)
    py_unsigned = murmur3_x86_32(py_data, seed=seed)
    py_signed = twos_comp_to_signed(py_unsigned, n_bits=32)
    preamble = "Hashing {data} with MurmurHash3/32-bit/seed={seed}".format(
        data=repr(data), seed=seed)
    if c_signed == py_signed:
        print(preamble + " -> {result}: OK".format(result=c_signed))
    else:
        raise AssertionError(
            preamble + "; mmh3 says "
            "{c_data} -> {c_signed}, Python version says {py_data} -> "
            "{py_unsigned} = {py_signed}".format(
                c_data=repr(c_data),
                c_signed=c_signed,
                py_data=repr(py_data),
                py_unsigned=py_unsigned,
                py_signed=py_signed))


def compare_python_to_reference_murmur3_64(data: Any, seed=0) -> None:
    assert mmh3, "Need mmh3 module"
    c_data = to_str(data)
    c_signed_low, c_signed_high = mmh3.hash64(c_data, seed=seed,
                                              x64arch=IS_64_BIT)
    py_data = to_bytes(c_data)
    py_signed_low, py_signed_high = pymmh3_hash64(py_data, seed=seed)
    preamble = "Hashing {data} with MurmurHash3/64-bit values from 128-bit " \
               "hash/seed={seed}".format(data=repr(data), seed=seed)
    if c_signed_low == py_signed_low and c_signed_high == py_signed_high:
        print(preamble + " -> (low={low}, high={high}): OK".format(
            low=c_signed_low, high=c_signed_high))
    else:
        raise AssertionError(
            preamble +
            "; mmh3 says {c_data} -> (low={c_low}, high={c_high}), Python "
            "version says {py_data} -> (low={py_low}, high={py_high})".format(
                c_data=repr(c_data),
                c_low=c_signed_low,
                c_high=c_signed_high,
                py_data=repr(py_data),
                py_low=py_signed_low,
                py_high=py_signed_high))


# =============================================================================
# Hashing in a NON-CRYPTOGRAPHIC, PREDICTABLE, and fast way
# =============================================================================

def hash32(data: Any, seed=0) -> int:
    """Returns a signed 32-bit integer."""
    with MultiTimerContext(timer, TIMING_HASH):
        c_data = to_str(data)
        if mmh3:
            return mmh3.hash(c_data, seed=seed)
        py_data = to_bytes(c_data)
        py_unsigned = murmur3_x86_32(py_data, seed=seed)
        return twos_comp_to_signed(py_unsigned, n_bits=32)


def hash64(data: Any, seed: int = 0) -> int:
    """Returns a signed 64-bit integer."""
    # -------------------------------------------------------------------------
    # MurmurHash3
    # -------------------------------------------------------------------------
    c_data = to_str(data)
    if mmh3:
        c_signed_low, _ = mmh3.hash64(data, seed=seed, x64arch=IS_64_BIT)
        return c_signed_low
    py_data = to_bytes(c_data)
    py_signed_low, _ = pymmh3_hash64(py_data, seed=seed)
    return py_signed_low

    # -------------------------------------------------------------------------
    # xxHash
    # -------------------------------------------------------------------------
    # if xxhash:
    #     hasher = xxhash.xxh64(seed=0)
    #     hasher.update(data)
    #     return hasher.intdigest()
    # else:
    #     hasher = pyhashxx.Hashxx(seed=0)
    #     # then do some update, but it doesn't like plain strings...
    #     return hasher.digest()


# =============================================================================
# Testing
# =============================================================================

def main():
    if False:
        print(twos_comp_to_signed(0, n_bits=32))  # 0
        print(twos_comp_to_signed(2 ** 31 - 1, n_bits=32))  # 2147483647
        print(twos_comp_to_signed(2 ** 31, n_bits=32))  # -2147483648 == -(2 ** 31)  # noqa
        print(twos_comp_to_signed(2 ** 32 - 1, n_bits=32))  # -1
        print(signed_to_twos_comp(-1, n_bits=32))  # 4294967295 = 2 ** 32 - 1
        print(signed_to_twos_comp(-(2 ** 31), n_bits=32))  # 2147483648 = 2 ** 31 - 1  # noqa
    testdata = [
        "hello",
        1,
        ["bongos", "today"],
    ]
    for data in testdata:
        compare_python_to_reference_murmur3_32(data, seed=0)
        compare_python_to_reference_murmur3_64(data, seed=0)
    print("All OK")


if __name__ == '__main__':
    main()
