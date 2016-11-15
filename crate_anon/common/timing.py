#!/usr/bin/env python
# crate_anon/common/timing.py

"""
This isn't very elegant, as it uses a global timing record.
"""

import datetime
import logging
from cardinal_pythonlib.rnc_datetime import get_now_utc
log = logging.getLogger(__name__)


class MultiTimer(object):
    """Mutually exclusive timing of a set of events."""
    def __init__(self) -> None:
        self._starttimes = {}  # dict of name: start time
        self._totaldurations = {}  # dict of name: duration
        self._stack = []  # list of names
        self._timing = False

    def set_timing(self, timing: bool) -> None:
        self._timing = timing

    def start(self, name: str) -> None:
        if not self._timing:
            return
        now = get_now_utc()

        # If we were already timing something else, pause that.
        if self._stack:
            last = self._stack[-1]
            self._totaldurations[last] += now - self._starttimes[last]

        # Start timing our new thing
        if name not in self._starttimes:
            self._totaldurations[name] = datetime.timedelta(0)
        self._starttimes[name] = now
        self._stack.append(name)

    def stop(self, name: str) -> None:
        if not self._timing:
            return
        now = get_now_utc()

        # Finish what we were asked to
        self._totaldurations[name] += now - self._starttimes[name]
        self._stack.pop()

        # Now, if we were timing something else before we started "name",
        # resume...
        if self._stack:
            last = self._stack[-1]
            self._starttimes[last] = now

    def __del__(self) -> None:
        if not self._timing:
            return
        for name, duration in self._totaldurations.items():
            if name in self._totaldurations:
                self._totaldurations[name] += duration
            else:
                self._totaldurations[name] = duration

    def report(self) -> None:
        while self._stack:
            self.stop(self._stack[-1])
        summary = ", ".join("{}: {} s".format(name, duration.total_seconds())
                            for name, duration in self._totaldurations.items())
        if not self._totaldurations:
            summary = "<no timings recorded>"
        log.info("Timing summary: " + summary)


timer = MultiTimer()
