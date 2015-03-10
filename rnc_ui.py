#!/usr/bin/python
# -*- encoding: utf8 -*-

"""Support functions for user interaction.

Author: Rudolf Cardinal (rudolf@pobox.com)
Created: 2009
Last update: 26 Feb 2015

Copyright/licensing:

    Copyright (C) 2009-2015 Rudolf Cardinal (rudolf@pobox.com).

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


import errno
import getpass
import os
import sys
import Tkinter
import tkFileDialog


def ask_user(prompt, default=None, to_unicode=False):
    """Prompts the user, with a default. Returns str or unicode."""
    if default is None:
        prompt = prompt + ": "
    else:
        prompt = prompt + " [" + default + "]: "
    result = raw_input(prompt.encode(sys.stdout.encoding))
    if to_unicode:
        result = result.decode(sys.stdin.encoding)
    return result if len(result) > 0 else default


def ask_user_password(prompt):
    """Read a password from the console."""
    return getpass.getpass(prompt + ": ")


def get_save_as_filename(defaultfilename, defaultextension, title="Save As"):
    """Provides a GUI "Save As" dialogue and returns the filename."""
    root = Tkinter.Tk()  # create and get Tk topmost window
    # (don't do this too early; the command prompt loses focus)
    root.withdraw()  # won't need this; this gets rid of a blank Tk window
    root.attributes('-topmost', True)  # makes the tk window topmost
    filename = tkFileDialog.asksaveasfilename(
        initialfile=defaultfilename,
        defaultextension=defaultextension,
        parent=root,
        title=title
    )
    root.attributes('-topmost', False)  # stop the tk window being topmost
    return filename


def get_open_filename(defaultfilename, defaultextension, title="Open"):
    """Provides a GUI "Open" dialogue and returns the filename."""
    root = Tkinter.Tk()  # create and get Tk topmost window
    # (don't do this too early; the command prompt loses focus)
    root.withdraw()  # won't need this; this gets rid of a blank Tk window
    root.attributes('-topmost', True)  # makes the tk window topmost
    filename = tkFileDialog.askopenfilename(
        initialfile=defaultfilename,
        defaultextension=defaultextension,
        parent=root,
        title=title
    )
    root.attributes('-topmost', False)  # stop the tk window being topmost
    return filename


def mkdir_p(path):
    """Makes a directory if it doesn't exist."""
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST:
            pass
        else:
            raise
