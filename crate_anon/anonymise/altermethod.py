#!/usr/bin/env python
# crate_anon/anonymise/altermethod.py

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
"""

import logging

# don't import config: circular dependency would have to be sorted out
from crate_anon.anonymise.constants import ALTERMETHOD

log = logging.getLogger(__name__)


# =============================================================================
# AlterMethod
# =============================================================================

class AlterMethod(object):
    def __init__(self,
                 text_value: str = None,
                 scrub: bool = False,
                 truncate_date: bool = False,
                 extract_from_filename: bool = False,
                 extract_from_file_format: bool = False,  # new in v0.18.18
                 file_format_str: str = "",  # new in v0.18.18
                 extract_from_blob: bool = False,
                 skip_if_text_extract_fails: bool = False,
                 extract_ext_field: str = "",
                 # html_escape: bool = False,
                 html_unescape: bool = False,
                 html_untag: bool = False) -> None:
        self.scrub = scrub
        self.truncate_date = truncate_date
        self.extract_from_blob = extract_from_blob
        self.extract_from_filename = extract_from_filename
        self.extract_from_file_format = extract_from_file_format
        self.file_format_str = file_format_str
        self.skip_if_text_extract_fails = skip_if_text_extract_fails
        self.extract_ext_field = extract_ext_field
        # self.html_escape = html_escape
        self.html_unescape = html_unescape
        self.html_untag = html_untag

        self.extract_text = (extract_from_filename or
                             extract_from_file_format or
                             extract_from_blob)

        if text_value is not None:
            self.set_from_text(text_value)

    def set_from_text(self, value: str) -> None:
        """
        Convert the alter_method field (from the data dictionary) to a bunch of
        boolean/simple fields.
        """
        self.scrub = False
        self.truncate_date = False
        self.extract_text = False
        self.extract_from_blob = False
        self.extract_from_file_format = False
        self.file_format_str = ""
        self.extract_from_filename = False
        self.skip_if_text_extract_fails = False
        self.extract_ext_field = ""

        if value == ALTERMETHOD.TRUNCATEDATE.value:
            self.truncate_date = True
        elif value == ALTERMETHOD.SCRUBIN.value:
            self.scrub = True
        elif value.startswith(ALTERMETHOD.BINARY_TO_TEXT.value):
            if "=" not in value:
                raise ValueError(
                    "Bad format for alter method: {}".format(value))
            secondhalf = value[value.index("=") + 1:]
            if not secondhalf:
                raise ValueError(
                    "Missing filename/extension field in alter method: "
                    "{}".format(value))
            self.extract_text = True
            self.extract_from_blob = True
            self.extract_ext_field = secondhalf
        elif value.startswith(ALTERMETHOD.FILENAME_FORMAT_TO_TEXT.value):
            if "=" not in value:
                raise ValueError(
                    "Bad format for alter method: {}".format(value))
            secondhalf = value[value.index("=") + 1:]
            if not secondhalf:
                raise ValueError(
                    "Missing filename format field in alter method: "
                    "{}".format(value))
            self.extract_text = True
            self.extract_from_file_format = True
            self.file_format_str = secondhalf
        elif value == ALTERMETHOD.FILENAME_TO_TEXT.value:
            self.extract_text = True
            self.extract_from_filename = True
        elif value == ALTERMETHOD.SKIP_IF_TEXT_EXTRACT_FAILS.value:
            self.skip_if_text_extract_fails = True
        # elif value == ALTERMETHOD.HTML_ESCAPE:
        #     self.html_escape = True
        elif value == ALTERMETHOD.HTML_UNESCAPE.value:
            self.html_unescape = True
        elif value == ALTERMETHOD.HTML_UNTAG.value:
            self.html_untag = True
        else:
            raise ValueError("Bad alter_method part: {}".format(value))

    def get_text(self) -> str:
        """
        Return the alter_method fragment from the working fields.
        """
        if self.truncate_date:
            return ALTERMETHOD.TRUNCATEDATE.value
        if self.scrub:
            return ALTERMETHOD.SCRUBIN.value
        if self.extract_text:
            if self.extract_from_blob:
                return (ALTERMETHOD.BINARY_TO_TEXT.value + "=" +
                        self.extract_ext_field)
            elif self.extract_from_file_format:
                return (ALTERMETHOD.FILENAME_FORMAT_TO_TEXT.value + "=" +
                        self.file_format_str)
            else:  # plain filename
                return ALTERMETHOD.FILENAME_TO_TEXT.value
        if self.skip_if_text_extract_fails:
            return ALTERMETHOD.SKIP_IF_TEXT_EXTRACT_FAILS.value
        # if self.html_escape:
        #     return ALTERMETHOD.HTML_ESCAPE.value
        if self.html_unescape:
            return ALTERMETHOD.HTML_UNESCAPE.value
        if self.html_untag:
            return ALTERMETHOD.HTML_UNTAG.value
        return ""
