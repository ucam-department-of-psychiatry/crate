#!/usr/bin/env python
# crate_anon/common/compression.py

"""
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

Compression functions.

"""

import gzip


def gzip_string(text: str, encoding: str = "utf-8") -> bytes:
    """
    When you send data over HTTP and wish to compress it, what should you do?

    - Use HTTP ``Content-Encoding``;
      https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/Content-Encoding.
    - This is defined in HTTP/1.1; see https://www.ietf.org/rfc/rfc2616.txt.
    - The gzip format is the most broadly supported, according to
      https://en.wikipedia.org/wiki/HTTP_compression.
    - This format is defined in https://www.ietf.org/rfc/rfc1952.txt.
    - The gzip format has a header; see above and
      https://en.wikipedia.org/wiki/Gzip.
    - Python's :func:`gzip.compress` writes to a memory file internally and
      writes the header.
    - So the work in the most popular answer here is unnecessary:
      https://stackoverflow.com/questions/8506897/how-do-i-gzip-compress-a-string-in-python
    - All we need is conversion of the string to bytes (via the appropriate
      encoding) and then :func:`gzip.compress`.

    Args:
        text:
            a string to compress
        encoding:
            encoding to use when converting string to bytes prior to
            compression

    Returns:
        bytes: gzip-compressed data

    Test code:

    .. code-block:: python

        import io
        import gzip

        teststring = "Testing; one, two, three."
        testbytes = teststring.encode("utf-8")

        gz1 = gzip.compress(testbytes)

        out1 = io.BytesIO()
        with gzip.GzipFile(fileobj=out1, mode="w") as gzfile1:
            gzfile1.write(testbytes)
        gz2 = out1.getvalue()

        print(len(gz1) == len(gz2))  # False
        print(gz1 == gz2)  # False
        # ... but the difference is probably in the timestamp bytes!

    """  # noqa
    data = text.encode(encoding)
    return gzip.compress(data)


def gunzip_string(zipped: bytes, encoding: str = "utf-8") -> str:
    """
    Reverses :func:`gzip_string`.

    Args:
        zipped:
            zipped data
        encoding:
            encoding that was used for the string prior to compression

    Returns:
        str: text

    Raises:
        - :exc:`OsError` if the data wasn't gzipped
        - :exc:`UnicodeDecodeError` if the decompressed data won't decode

    """
    data = gzip.decompress(zipped)
    return data.decode(encoding)
