#!/usr/bin/env python
# crate_anon/common/timing.py

"""
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
        self._totaldurations = OrderedDict()  # dict of name: duration
        self._stack = []  # list of names

    def reset(self) -> None:
        self._overallstart = get_now_utc()
        self._starttimes.clear()
        self._totaldurations.clear()
        self._stack.clear()

    def set_timing(self, timing: bool, reset: bool = False) -> None:
        self._timing = timing
        if reset:
            self.reset()

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
            self._totaldurations[name] = datetime.timedelta()
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

    def report(self) -> None:
        """Finish and report to the log."""
        while self._stack:
            self.stop(self._stack[-1])
        now = get_now_utc()
        grand_total = datetime.timedelta()
        overall_duration = now - self._overallstart
        summaries = []
        for name, duration in self._totaldurations.items():
            summaries.append("{}: {} s".format(name, duration.total_seconds()))
            grand_total += duration
        unmetered = overall_duration - grand_total
        if not self._totaldurations:
            summaries.append("<no timings recorded>")
        log.info("Timing summary: " + ", ".join(summaries))
        log.info("Unmetered time: {} s".format(unmetered.total_seconds()))


class MultiTimerContext(object):
    def __init__(self, multitimer: MultiTimer, name: str) -> None:
        self.timer = multitimer
        self.name = name

    def __enter__(self):
        self.timer.start(self.name)

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.timer.stop(self.name)


timer = MultiTimer()
