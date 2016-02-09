#!/usr/bin/python
# -*- encoding: utf8 -*-

"""Network support functions.

Author: Rudolf Cardinal (rudolf@pobox.com)
Created: 04 Jan 2016
Last update: 04 Jan 2016

Copyright/licensing:

    Copyright (C) 2016-2016 Rudolf Cardinal (rudolf@pobox.com).

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

"""
- ping requires root to create ICMP sockets in Linux
- the /bin/ping command doesn't need root (because it has the setuid bit set)
- For Linux, it's best to use the system ping.

http://stackoverflow.com/questions/2953462/pinging-servers-in-python
http://stackoverflow.com/questions/316866/ping-a-site-in-python

- Note that if you want a sub-second timeout, things get trickier.
  One option is fping.
"""

import subprocess
import sys


def ping(hostname, timeout_s=5):
    if sys.platform == "win32":
        timeout_ms = timeout_s * 1000
        args = [
            "ping",
            hostname,
            "-n", "1",  # ping count
            "-w", str(timeout_ms),  # timeout
        ]
    elif sys.platform.startswith('linux'):
        args = [
            "ping",
            hostname,
            "-c", "1",  # ping count
            "-w", str(timeout_s),  # timeout
        ]
    else:
        raise AssertionError("Don't know how to ping on this operating system")
    proc = subprocess.Popen(args,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc.communicate()
    retcode = proc.returncode
    return retcode == 0  # zero success, non-zero failure
