#!/usr/bin/python
# -*- encoding: utf8 -*-

"""Support functions for process/external command management.

Author: Rudolf Cardinal (rudolf@pobox.com)
Created: 2012
Last update: 24 Sep 2015

Copyright/licensing:

    Copyright (C) 2012-2015 Rudolf Cardinal (rudolf@pobox.com).

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

import shlex
import subprocess


def get_external_command_output(command):
    args = shlex.split(command)
    ret = subprocess.check_output(args)  # this needs Python 2.7 or higher
    return ret


def get_pipe_series_output(commands, stdinput=None):
    # Python arrays indexes are zero-based, i.e. an array is indexed from
    # 0 to len(array)-1.
    # The range/xrange commands, by default, start at 0 and go to one less
    # than the maximum specified.

    # print commands
    processes = []
    for i in range(len(commands)):
        if i == 0:  # first processes
            processes.append(
                subprocess.Popen(
                    shlex.split(commands[i]),
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE
                )
            )
        else:  # subsequent ones
            processes.append(
                subprocess.Popen(
                    shlex.split(commands[i]),
                    stdin=processes[i-1].stdout,
                    stdout=subprocess.PIPE
                )
            )
    return processes[len(processes) - 1].communicate(stdinput)[0]
    # communicate() returns a tuple; 0=stdout, 1=stderr; so this returns stdout

# Also, simple commands: use os.system(command)
