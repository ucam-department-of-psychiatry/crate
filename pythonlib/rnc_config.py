#!/usr/bin/python
# -*- encoding: utf8 -*-

"""Support functions for config (.INI) file reading

Author: Rudolf Cardinal (rudolf@pobox.com)
Created: 16 Apr 2015
Last update: 16 Apr 2015

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

# =============================================================================
# Config
# =============================================================================

def read_config_string_options(obj, parser, section, options,
                               enforce_str=False):
    if not parser.has_section(section):
        raise ValueError("config missing section: " + section)
    for o in options:
        if parser.has_option(section, o):
            value = parser.get(section, o)
            setattr(obj, o, str(value) if enforce_str else value)
        else:
            setattr(obj, o, None)


def read_config_multiline_options(obj, parser, section, options):
    if not parser.has_section(section):
        raise ValueError("config missing section: " + section)
    for o in options:
        if parser.has_option(section, o):
            multiline = parser.get(section, o)
            values = [x.strip() for x in multiline.splitlines() if x.strip()]
            setattr(obj, o, values)
        else:
            setattr(obj, o, [])
