#!/usr/bin/env python
# crate_anon/common/datetimefunc.py

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
"""

import datetime
from typing import Optional
import pytz

import dateutil.parser  # pip install python-dateutil


def get_now_utc() -> datetime.datetime:
    """Get the time now in the UTC timezone."""
    return datetime.datetime.now(pytz.utc)


def get_now_utc_notz() -> datetime.datetime:
    """Get the UTC time now, but with no timezone information."""
    return get_now_utc().replace(tzinfo=None)


def truncate_date_to_first_of_month(dt) -> Optional[datetime.datetime]:
    """Change the day to the first of the month."""
    if dt is None:
        return None
    return dt.replace(day=1)


def coerce_to_datetime(x) -> Optional[datetime.datetime]:
    """
    Ensure an object is a datetime, or coerce to one, or raise (ValueError or
    OverflowError, as per
    http://dateutil.readthedocs.org/en/latest/parser.html).
    """
    if x is None:
        return None
    elif isinstance(x, datetime.datetime):
        return x
    elif isinstance(x, datetime.date):
        return datetime.datetime(x.year, x.month, x.day)
    else:
        return dateutil.parser.parse(x)  # may raise
