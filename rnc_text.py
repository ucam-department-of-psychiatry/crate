#!/usr/bin/python
# -*- encoding: utf8 -*-

"""Textfile results storage.

Author: Rudolf Cardinal (rudolf@pobox.com)
Created: 2009
Last update: 24 Sep 2015

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

import csv
import string
import datetime


def produce_csv_output(filehandle, fields, values):
    """Produce CSV output, without using csv.writer, so the log can be used for
    lots of things."""
    output_csv(filehandle, fields)
    for row in values:
        output_csv(filehandle, row)


def output_csv(filehandle, values):
    line = ",".join(values)
    filehandle.write(line + "\n")


def get_what_follows_raw(s, prefix, onlyatstart=True, stripwhitespace=True):
    prefixstart = string.find(s, prefix)
    if ((prefixstart == 0 and onlyatstart)
            or (prefixstart != -1 and not onlyatstart)):
        # substring found
        resultstart = prefixstart + len(prefix)
        result = s[resultstart:]
        if stripwhitespace:
            result = string.strip(result)
        return (True, result)
    return (False, "")


def get_what_follows(strings, prefix, onlyatstart=True, stripwhitespace=True,
                     precedingline=""):
    if not precedingline:
        for s in strings:
            (found, result) = get_what_follows_raw(s, prefix, onlyatstart,
                                                   stripwhitespace)
            if found:
                return result
        return ""
    else:
        for i in range(1, len(strings)):  # i indexes the second of a pair
            if string.find(strings[i-1], precedingline) == 0:
                # ... if found at the start
                (found, result) = get_what_follows_raw(strings[i], prefix,
                                                       onlyatstart,
                                                       stripwhitespace)
                if found:
                    return result
        return ""


def get_string(strings, prefix, ignoreleadingcolon=False, precedingline=""):
    s = get_what_follows(strings, prefix, precedingline=precedingline)
    if ignoreleadingcolon:
        f = string.find(s, ":")
        if f != -1:
            s = string.strip(s[f+1:])
    if len(s) == 0:
        return None
    return s


def get_string_relative(strings, prefix1, delta, prefix2,
                        ignoreleadingcolon=False, stripwhitespace=True):
    """Finds line beginning prefix1. Moves delta lines. Returns end of line
    beginning prefix2, if found."""
    for firstline in range(0, len(strings)):
        if string.find(strings[firstline], prefix1) == 0:  # if found...
            secondline = firstline + delta
            if secondline < 0 or secondline >= len(strings):
                continue
            if string.find(strings[secondline], prefix2) == 0:
                s = strings[secondline][len(prefix2):]
                if stripwhitespace:
                    s = string.strip(s)
                if ignoreleadingcolon:
                    f = string.find(s, ":")
                    if f != -1:
                        s = string.strip(s[f+1:])
                    if stripwhitespace:
                        s = string.strip(s)
                if len(s) == 0:
                    return None
                return s
    return None


def get_int(strings, prefix, ignoreleadingcolon=False, precedingline=""):
    return get_int_raw(get_string(strings, prefix,
                                  ignoreleadingcolon=ignoreleadingcolon,
                                  precedingline=precedingline))


def get_float(strings, prefix, ignoreleadingcolon=False, precedingline=""):
    return get_float_raw(get_string(strings, prefix,
                                    ignoreleadingcolon=ignoreleadingcolon,
                                    precedingline=precedingline))


def get_int_raw(str):
    if str is None:
        return None
    return int(str)


def get_bool_raw(str):
    if str == "Y" or str == "y":
        return True
    elif str == "N" or str == "n":
        return False
    return None


def get_float_raw(str):
    if str is None:
        return None
    return float(str)


def get_bool(strings, prefix, ignoreleadingcolon=False, precedingline=""):
    return get_bool_raw(get_string(strings, prefix,
                                   ignoreleadingcolon=ignoreleadingcolon,
                                   precedingline=precedingline))


def get_bool_relative(strings, prefix1, delta, prefix2,
                      ignoreleadingcolon=False):
    return get_bool_raw(get_string_relative(
        strings, prefix1, delta, prefix2,
        ignoreleadingcolon=ignoreleadingcolon))


def get_float_relative(strings, prefix1, delta, prefix2,
                       ignoreleadingcolon=False):
    return get_float_raw(get_string_relative(
        strings, prefix1, delta, prefix2,
        ignoreleadingcolon=ignoreleadingcolon))


def get_int_relative(strings, prefix1, delta, prefix2,
                     ignoreleadingcolon=False):
    return get_int_raw(get_string_relative(
        strings, prefix1, delta, prefix2,
        ignoreleadingcolon=ignoreleadingcolon))


def get_datetime(strings, prefix, datetime_format_string,
                 ignoreleadingcolon=False, precedingline=""):
    x = get_string(strings, prefix, ignoreleadingcolon=ignoreleadingcolon,
                   precedingline=precedingline)
    if len(x) == 0:
        return None
    # For the format strings you can pass to datetime.datetime.strptime, see
    # http://docs.python.org/library/datetime.html
    # A typical one is "%d-%b-%Y (%H:%M:%S)"
    d = datetime.datetime.strptime(x, datetime_format_string)
    return d


def find_line_beginning(strings, linestart):
    if linestart is None:  # match an empty line
        for i in range(len(strings)):
            if is_empty_string(strings[i]):
                return i
        return -1
    for i in range(len(strings)):
        if string.find(strings[i], linestart) == 0:
            return i
    return -1


def find_line_containing(strings, contents):
    for i in range(len(strings)):
        if string.find(strings[i], contents) != -1:
            return i
    return -1


def get_lines_from_to(strings, firstlinestart, list_of_lastline_starts):
    """Takes a list of strings. Returns a list of strings FROM firstlinestart
    (inclusive) TO one of list_of_lastline_starts (exclusive).

    To search to the end of the list, use list_of_lastline_starts = []
    To search to a blank line, use list_of_lastline_starts = [None]"""
    start_index = find_line_beginning(strings, firstlinestart)
    if start_index == -1:
        return []
    end_offset = None  # itself a valid slice index
    for lls in list_of_lastline_starts:
        possible_end_offset = find_line_beginning(strings[start_index:], lls)
        if possible_end_offset != -1:  # found one
            if end_offset is None or possible_end_offset < end_offset:
                end_offset = possible_end_offset
    end_index = None if end_offset is None else (start_index + end_offset)
    return strings[start_index:end_index]


def is_empty_string(str):
    return (len(string.strip(str)) == 0)


def csv_to_list_of_fields(lines, csvheader, quotechar='"'):
    data = []
    # an empty line marks the end of the block
    csvlines = get_lines_from_to(lines, csvheader, [None])[1:]
    # ... remove the CSV header
    reader = csv.reader(csvlines, quotechar=quotechar)
    for fields in reader:
        data.append(fields)
    return data


def csv_to_list_of_dicts(lines, csvheader, quotechar='"'):
    data = []  # empty list
    # an empty line marks the end of the block
    csvlines = get_lines_from_to(lines, csvheader, [None])[1:]
    # ... remove the CSV header
    headerfields = string.split(csvheader, sep=",")
    reader = csv.reader(csvlines, quotechar=quotechar)
    for fields in reader:
        row = {}  # empty dictionary
        for f in range(len(headerfields)):
            row[headerfields[f]] = fields[f]
        data.append(row)
    return data


def dictlist_convert_to_string(dict_list, key):
    for d in dict_list:
        d[key] = str(d[key])
        if d[key] == "":
            d[key] = None


def dictlist_convert_to_datetime(dict_list, key, DATETIME_FORMAT_STRING):
    for d in dict_list:
        d[key] = datetime.datetime.strptime(d[key], DATETIME_FORMAT_STRING)


def dictlist_convert_to_int(dict_list, key):
    for d in dict_list:
        try:
            d[key] = int(d[key])
        except ValueError:
            d[key] = None


def dictlist_convert_to_float(dict_list, key):
    for d in dict_list:
        try:
            d[key] = float(d[key])
        except ValueError:
            d[key] = None


def dictlist_convert_to_bool(dict_list, key):
    for d in dict_list:
        # d[key] = True if d[key] == "Y" else False
        d[key] = 1 if d[key] == "Y" else 0


def dictlist_replace(dict_list, key, value):
    for d in dict_list:
        d[key] = value


def dictlist_wipe_key(dict_list, key):
    for d in dict_list:
        d.pop(key, None)
