#!/usr/bin/env python
# crate_anon/common/timing.py

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

This isn't very elegant, as it uses a global timing record.
"""

from collections import OrderedDict
import datetime
import logging
from cardinal_pythonlib.rnc_datetime import get_now_utc
log = logging.getLogger(__name__)


class MultiTimer(object):
    """Mutually exclusive timing of a set of events."""
    def __init__(self) -> None:
        self._timing = False
        self._overallstart = get_now_utc()
        self._starttimes = OrderedDict()  # name: start time
        self._totaldurations = OrderedDict()  # name: duration
        self._count = OrderedDict()  # name: count
        self._stack = []  # list of names

    def reset(self) -> None:
        self._overallstart = get_now_utc()
        self._starttimes.clear()
        self._totaldurations.clear()
        self._count.clear()
        self._stack.clear()

    def set_timing(self, timing: bool, reset: bool = False) -> None:
        self._timing = timing
        if reset:
            self.reset()

    def start(self, name: str, increment_count: bool = True) -> None:
        if not self._timing:
            return
        now = get_now_utc()

        # If we were already timing something else, pause that.
        if self._stack:
            last = self._stack[-1]
            self._totaldurations[last] += now - self._starttimes[last]

        # Start timing our new thing
        if name not in self._starttimes:
            self._totaldurations[name] = datetime.timedelta()
            self._count[name] = 0
        self._starttimes[name] = now
        if increment_count:
            self._count[name] += 1
        self._stack.append(name)

    def stop(self, name: str) -> None:
        if not self._timing:
            return
        now = get_now_utc()

        # Validity check
        if not self._stack:
            raise AssertionError("MultiTimer.stop() when nothing running")
        if self._stack[-1] != name:
            raise AssertionError(
                "MultiTimer.stop({}) when {} is running".format(
                    repr(name), repr(self._stack[-1])))

        # Finish what we were asked to
        self._totaldurations[name] += now - self._starttimes[name]
        self._stack.pop()

        # Now, if we were timing something else before we started "name",
        # resume...
        if self._stack:
            last = self._stack[-1]
            self._starttimes[last] = now

    def report(self) -> None:
        """Finish and report to the log."""
        while self._stack:
            self.stop(self._stack[-1])
        now = get_now_utc()
        grand_total = datetime.timedelta()
        overall_duration = now - self._overallstart
        for name, duration in self._totaldurations.items():
            grand_total += duration

        log.info("Timing summary:")
        summaries = []
        for name, duration in self._totaldurations.items():
            n = self._count[name]
            total_sec = duration.total_seconds()
            mean = total_sec / n if n > 0 else None

            summaries.append({
                'total': total_sec,
                'description': (
                    "- {}: {:.3f} s ({:.2f}%, n={}, mean={:.3f}s)".format(
                        name,
                        total_sec,
                        (100 * total_sec / grand_total.total_seconds()),
                        n,
                        mean)),
            })
        summaries.sort(key=lambda x: x['total'], reverse=True)
        for s in summaries:
            # noinspection PyTypeChecker
            log.info(s["description"])
        if not self._totaldurations:
            log.info("<no timings recorded>")

        unmetered = overall_duration - grand_total
        log.info("Unmetered time: {:.3f} s ({:.2f}%)".format(
            unmetered.total_seconds(),
            100 * unmetered.total_seconds() / overall_duration.total_seconds()
        ))


class MultiTimerContext(object):
    def __init__(self, multitimer: MultiTimer, name: str) -> None:
        self.timer = multitimer
        self.name = name

    def __enter__(self):
        self.timer.start(self.name)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.timer.stop(self.name)


timer = MultiTimer()
