#!/usr/bin/env python

"""
crate_anon/common/contenttypes.py

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

**Content types for HTTP.**

Many of these can be extracted:

.. code-block:: python

    import mimetypes
    mimetypes.types_map['.zip']  # application/zip -- this is built in
    mimetypes.types_map['.xlsx']  # fails
    mimetypes.init()
    mimetypes.types_map['.xlsx']  # application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
    # ... must read some local thing...

"""  # noqa


class ContentType(object):
    """
    Constants for common HTTP content types.
    
    See:
    
    - CSV
    
        - http://stackoverflow.com/questions/264256/what-is-the-best-mime-type-and-extension-to-use-when-exporting-tab-delimited
        - http://www.iana.org/assignments/media-types/text/tab-separated-values
    
    - ZIP
    
        - http://stackoverflow.com/questions/4411757/zip-mime-types-when-to-pick-which-one
    
    """  # noqa
    CSV = "text/csv"

    PDF = "application/pdf"

    TSV = "text/tab-separated-values"

    XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    ZIP = "application/zip"
