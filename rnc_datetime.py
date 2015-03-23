#!/usr/bin/python
# -*- encoding: utf8 -*-

"""Support functions for date/time.

Author: Rudolf Cardinal (rudolf@pobox.com)
Created: 26 Feb 2015
Last update: 26 Feb 2015

Copyright/licensing:

    Copyright (C) 2015-2015 Rudolf Cardinal (rudolf@pobox.com).

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

import datetime
import dateutil.parser
import pytz


# =============================================================================
# Date/time functions
# =============================================================================

def format_datetime(d, fmt, default=None):
    """Format a datetime with a format string, or return default if None."""
    if d is None:
        return default
    return d.strftime(fmt)


def get_now_utc():
    """Get the time now in the UTC timezone."""
    return datetime.datetime.now(pytz.utc)


def get_now_utc_notz():
    """Get the UTC time now, but with no timezone information."""
    return get_now_utc().replace(tzinfo=None)


def truncate_date_to_first_of_month(dt):
    """Change the day to the first of the month."""
    if dt is None:
        return None
    return dt.replace(day=1)


def coerce_to_date(x):
    """Ensure an object is a datetime, or coerce to one, or raise."""
    if x is None:
        return None
    if isinstance(x, datetime.datetime):
        return x
    return dateutil.parser.parse(x)  # may raise
