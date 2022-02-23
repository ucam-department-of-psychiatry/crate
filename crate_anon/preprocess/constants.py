#!/usr/bin/env python

"""
crate_anon/preprocess/constants.py

===============================================================================

    Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).

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
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

**Constants used for lots of preprocessing functions.**

"""

# Prefix for index names:
CRATE_IDX_PREFIX = "crate_idx"

# If our preprocessors need to create a primary key (PK) column in a table as
# part of preprocessing, we call it this:
CRATE_COL_PK = "crate_pk"
# Making it explicitly CRATE-related makes it distinctive from more generic
# names like "id" or "pk" or "RowIdentifier".
