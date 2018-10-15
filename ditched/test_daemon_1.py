#!/usr/bin/env python

"""
ditched/test_daemon_1.py

===============================================================================

    Copyright (C) 2015-2018 Rudolf Cardinal (rudolf@pobox.com).

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

A threading "daemon" thread IS NOT A PROPER DAEMON.
http://www.bogotobogo.com/python/Multithread/python_multithreading_Daemon_join_method_threads.php
The daemon threads are killed when the main process exits.
"""

import threading

def threadfunc():
    while True:
        print("In daemon thread")
        time.sleep(5)

th = threading.Thread(target=threadfunc)
th.daemon = True
print("Starting daemon thread")
th.start()
print("At end of main program")
