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

# -----------------------------------------------------------------------------
# Indexes in destination databases
# -----------------------------------------------------------------------------
# Prefix for index names:
CRATE_IDX_PREFIX = "crate_idx"

# -----------------------------------------------------------------------------
# Columns for source databases
# -----------------------------------------------------------------------------
# If our preprocessors need to create a primary key (PK) column in a table as
# part of preprocessing, we call it this:
CRATE_COL_PK = "crate_pk"
# Making it explicitly CRATE-related makes it distinctive from more generic
# names like "id" or "pk" or "RowIdentifier".

# -----------------------------------------------------------------------------
# Columns in ONS Postcode Database (from CRATE import)
# -----------------------------------------------------------------------------
ONSPD_TABLE_POSTCODE = "postcode"
DEFAULT_GEOG_COLS = [
    # These are geographically "blurry" areas. The most specific is likely
    # LSOA (or, equivalently, IMD).
    # For details, see postcodes.py.
    "bua11",  # Built-up Area (BUA)
    "buasd11",  # Built-up Area Sub-division (BUASD)
    "casward",  # Census Area Statistics (CAS) ward
    "imd",  # Index of Multiple Deprivation (IMD) [rank of LSOA/equivalent]
    "lea",  # todo: gone? (Local Education Authority in previous data?)
    "lsoa01",  # 2001 Census Lower Layer Super Output Area (LSOA) or equivalent
    "lsoa11",  # 2011 Census Lower Layer Super Output Area (LSOA) or equiv.
    "msoa01",  # 2001 Census Middle Layer Super Output Area (MSOA) or equiv.
    "msoa11",  # 2011 Census Middle Layer Super Output Area (MSOA) or equiv.
    "nuts",  # EU Local Administrative Unit, level 2
    "oac01",  # 2001 Census Output Area classification (OAC)
    "oac11",  # 2011 Census Output Area classification (OAC)
    "parish",  # Parish/community
    "pcon",  # Westminster parliamentary constituency
    "pct",  # Primary Care Trust or equivalent
    "ru11ind",  # 2011 Census rural-urban classification
    "statsward",  # Statistical ward
    "ur01ind",  # 2001 Census urban/rural indicator
]
