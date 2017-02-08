#!/usr/bin/env python
# crate_anon/common/contenttypes.py

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

Many of these can be extracted:

import mimetypes
mimetypes.types_map['.zip']  # application/zip -- this is built in
mimetypes.types_map['.xlsx']  # fails
mimetypes.init()
mimetypes.types_map['.xlsx']  # application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
# ... must read some local thing...

"""  # noqa

CONTENTTYPE_PDF = "application/pdf"
CONTENTTYPE_ZIP = "application/zip"
# ... http://stackoverflow.com/questions/4411757/zip-mime-types-when-to-pick-which-one  # noqa
CONTENTTYPE_TSV = "text/tab-separated-values"
CONTENTTYPE_CSV = "text/csv"
CONTENTTYPE_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"  # noqa
