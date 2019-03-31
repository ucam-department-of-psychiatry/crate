#!/usr/bin/env python

"""
crate_anon/anonymise/altermethod.py

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

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

**The AlterMethod class.**

"""

import datetime
import html
import logging
import os
import traceback
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from cardinal_pythonlib.datetimefunc import (
    coerce_to_datetime,
    truncate_date_to_first_of_month,
)
from cardinal_pythonlib.extract_text import (
    document_to_text,
    TextProcessingConfig,
)
import regex

# don't import config: circular dependency would have to be sorted out
from crate_anon.anonymise.constants import ALTERMETHOD

if TYPE_CHECKING:
    from cardinal_pythonlib.hash import GenericHasher
    from crate_anon.anonymise.config import Config
    from crate_anon.anonymise.ddr import DataDictionaryRow
    from crate_anon.anonymise.patient import Patient

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

HTML_TAG_RE = regex.compile('<[^>]*>')


# =============================================================================
# AlterMethod
# =============================================================================

class AlterMethod(object):
    """
    Controls the way in which a source field is transformed on its way to the
    destination database.
    """
    def __init__(self,
                 config: "Config",
                 text_value: str = None,
                 scrub: bool = False,
                 truncate_date: bool = False,
                 extract_from_filename: bool = False,
                 extract_from_file_format: bool = False,  # new in v0.18.18
                 file_format_str: str = "",  # new in v0.18.18
                 extract_from_blob: bool = False,
                 skip_if_text_extract_fails: bool = False,
                 extract_ext_field: str = "",
                 hash_: bool = False,
                 hash_config_section: str = "",
                 # html_escape: bool = False,
                 html_unescape: bool = False,
                 html_untag: bool = False) -> None:
        """
        Args:
            config:
                a :class:`crate_anon.anonymise.config.Config`
            text_value:
                string (from the data dictionary) to parse via
                :func:`set_from_text`; may set many of the other attributes
            scrub:
                Boolean; "the source field contains sensitive text; scrub it"
            truncate_date:
                Boolean; "the source is a date; truncate it to the first of the
                month"
            extract_from_filename:
                Boolean; "the source is a filename; extract the text from it"
            extract_from_file_format:
                Boolean; "the source is a partial filename; combine it with
                ``file_format_str`` to calculate the full filename, then
                extract the text from it"
            file_format_str:
                format string for use with ``extract_from_file_format``
            extract_from_blob:
                Boolean; "the source is binary (the database contains a BLOB);
                extract text from it". See also ``extract_ext_field``.
            skip_if_text_extract_fails:
                Boolean: "if text extraction fails, skip the record entirely"
            extract_ext_field:
                For when the database contains a BLOB: this parameter indicates
                a database column (field) name, in the same row, that contains
                the file's extension, to help identify the BLOB.
            hash_:
                Boolean. If true, transform the source by hashing it.
            hash_config_section:
                If ``hash_`` is true, this specifies the config section in
                which the hash is defined.
            html_unescape:
                Boolean: "transform the source by HTML-unescaping it". For
                example, this would convert ``&le;`` to ``<``.
            html_untag:
                Boolean: "transform the source by removing HTML tags". For
                example, this would convert ``hello <b>bold</b> world`` to
                ``hello bold world``.
        """
        self.config = config
        self.scrub = scrub
        self.truncate_date = truncate_date
        self.extract_from_blob = extract_from_blob
        self.extract_from_filename = extract_from_filename
        self.extract_from_file_format = extract_from_file_format
        self.file_format_str = file_format_str
        self.skip_if_text_extract_fails = skip_if_text_extract_fails
        self.extract_ext_field = extract_ext_field
        self.hash = hash_
        self.hash_config_section = hash_config_section
        self.hasher = None  # type: GenericHasher
        # self.html_escape = html_escape
        self.html_unescape = html_unescape
        self.html_untag = html_untag

        self.extract_text = (extract_from_filename or
                             extract_from_file_format or
                             extract_from_blob)

        if text_value is not None:
            self.set_from_text(text_value)
        if hash_:
            self.hasher = self.config.get_extra_hasher(
                self.hash_config_section)

    def set_from_text(self, value: str) -> None:
        """
        Take the string from the ``alter_method`` field of the data dictionary,
        and use it to set a bunch of internal attributes.

        To get the configuration string back, see :func:`get_text`.
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
        self.hash = False
        self.hash_config_section = ""

        def get_second_part(missing_description: str) -> str:
            if "=" not in value:
                raise ValueError(
                    f"Bad format for alter method: {value}")
            secondhalf = value[value.index("=") + 1:]
            if not secondhalf:
                raise ValueError(
                    f"Missing {missing_description} in alter method: {value}")
            return secondhalf

        if value == ALTERMETHOD.TRUNCATEDATE.value:
            self.truncate_date = True
        elif value == ALTERMETHOD.SCRUBIN.value:
            self.scrub = True
        elif value.startswith(ALTERMETHOD.BINARY_TO_TEXT.value):
            self.extract_text = True
            self.extract_from_blob = True
            self.extract_ext_field = get_second_part(
                "filename/extension field")
        elif value.startswith(ALTERMETHOD.FILENAME_FORMAT_TO_TEXT.value):
            self.extract_text = True
            self.extract_from_file_format = True
            self.file_format_str = get_second_part(
                "filename format field")
        elif value == ALTERMETHOD.FILENAME_TO_TEXT.value:
            self.extract_text = True
            self.extract_from_filename = True
        elif value == ALTERMETHOD.SKIP_IF_TEXT_EXTRACT_FAILS.value:
            self.skip_if_text_extract_fails = True
        elif value.startswith(ALTERMETHOD.HASH.value):
            self.hash = True
            self.hash_config_section = get_second_part("hash config section")
            self.hasher = self.config.get_extra_hasher(
                self.hash_config_section)
        # elif value == ALTERMETHOD.HTML_ESCAPE:
        #     self.html_escape = True
        elif value == ALTERMETHOD.HTML_UNESCAPE.value:
            self.html_unescape = True
        elif value == ALTERMETHOD.HTML_UNTAG.value:
            self.html_untag = True
        else:
            raise ValueError(f"Bad alter_method part: {value}")

    def get_text(self) -> str:
        """
        Return the ``alter_method`` fragment from the working fields;
        effectively the reverse of :func:`set_from_text`.
        """
        def two_part(altermethod: str, parameter: str):
            return altermethod + "=" + parameter

        if self.truncate_date:
            return ALTERMETHOD.TRUNCATEDATE.value
        if self.scrub:
            return ALTERMETHOD.SCRUBIN.value
        if self.extract_text:
            if self.extract_from_blob:
                return two_part(ALTERMETHOD.BINARY_TO_TEXT.value,
                                self.extract_ext_field)
            elif self.extract_from_file_format:
                return two_part(ALTERMETHOD.FILENAME_FORMAT_TO_TEXT.value,
                                self.file_format_str)
            else:  # plain filename
                return ALTERMETHOD.FILENAME_TO_TEXT.value
        if self.skip_if_text_extract_fails:
            return ALTERMETHOD.SKIP_IF_TEXT_EXTRACT_FAILS.value
        if self.hash:
            return two_part(ALTERMETHOD.HASH.value,
                            self.hash_config_section)
        # if self.html_escape:
        #     return ALTERMETHOD.HTML_ESCAPE.value
        if self.html_unescape:
            return ALTERMETHOD.HTML_UNESCAPE.value
        if self.html_untag:
            return ALTERMETHOD.HTML_UNTAG.value
        return ""

    def alter(self,
              value: Any,
              ddr: "DataDictionaryRow",  # corresponding DataDictionaryRow
              row: List[Any],  # all values in row
              ddrows: List["DataDictionaryRow"],  # all of them
              patient: "Patient" = None) -> Tuple[Any, bool]:
        """
        Performs the alteration.

        Args:
            value:
                source value of interest
            ddr:
                corresponding
                :class:`crate_anon.anonymise.ddr.DataDictionaryRow`
            row:
                all values in the same source row
            ddrows:
                all data dictionary rows
            patient:
                :class:`crate_anon.anonymise.patient.Patient` object

        Returns:
            tuple: ``newvalue, skiprow``

        If multiple transformations are specified within one
        :class:`AlterMethod`, only one is performed, and in the following
        order:

        #. scrub
        #. truncate_date
        #. extract_text
        #. hash
        #. html_unescape
        #. html_untag
        #. skip_if_text_extract_fails

        However, multiple alteration methods can be specified for one field.
        See :func:`crate_anon.anonymise.anonymise.process_table` and
        :class:`crate_anon.anonymise.ddr.DataDictionaryRow`.

        """

        if self.scrub:
            return self._scrub_func(value, patient), False

        if self.truncate_date:
            return self._truncate_date_func(value), False

        if self.extract_text:
            value, extracted = self._extract_text_func(value, row, ddrows)
            if not extracted and ddr.skip_row_if_extract_text_fails():
                log.debug("Skipping row as text extraction failed")
                return None, True
            return value, False

        if self.hash:
            assert self.hasher is not None
            return self.hasher.hash(value), False

        # if alter_method.html_escape:
        #     return html.escape(value), False

        if self.html_unescape:
            return html.unescape(value), False

        if self.html_untag:
            return self._html_untag_func(value), False

        if self.skip_if_text_extract_fails:
            # Modifies other alter methods; doesn't do anything itself
            return value, True

    @staticmethod
    def _scrub_func(value: Any, patient: "Patient") -> Optional[str]:
        """
        Takes a source value and scrubs it.

        **Main point of anonymisation within CRATE.**

        Args:
            value: source data
            patient: :class:`crate_anon.anonymise.patient.Patient` object

        Returns:
            scrubbed data

        """
        if value is None:
            return None
        return patient.scrub(str(value))

    @staticmethod
    def _truncate_date_func(value: Any) -> Optional[datetime.datetime]:
        """
        Truncates a date-like object to the first of the month.
        """
        try:
            value = coerce_to_datetime(value)
            return truncate_date_to_first_of_month(value)
        except (ValueError, OverflowError):
            log.warning(
                f"Invalid date received to "
                f"{ALTERMETHOD.TRUNCATEDATE} method: {value}")
            return None

    @staticmethod
    def _html_untag_func(text: str) -> str:
        """
        Removes HTML tags.
        """
        # Lots of ways...
        # -- xml.etree, for well-formed XML
        #    http://stackoverflow.com/questions/9662346
        # return ''.join(xml.etree.ElementTree.fromstring(text).itertext())
        # -- html.parser
        #    http://stackoverflow.com/questions/753052
        # -- lxml (but needs source build on Windows):
        #    http://www.neuraladvance.com/removing-html-from-python-strings.html
        #    http://lxml.de/
        # -- regex/re
        #    http://stackoverflow.com/questions/3662142
        return HTML_TAG_RE.sub('', text)

    def _extract_text_func(
            self, value: Any, row: List[Any],
            ddrows: List["DataDictionaryRow"]) -> Tuple[Optional[str], bool]:
        """
        Take a field's value and return extracted text, for file-related
        fields, where the DD row indicated that this field contains a filename
        or a BLOB.

        Args:
            value: source field contents
            row: all values in the same source row
            ddrows: all data dictionary rows

        Returns:
            tuple: ``value, extracted``

        """
        use_filename = False
        filename = None
        blob = None

        # Work out either a full filename, or a BLOB.
        # Set either use_filename + filename + extension, or blob + extension.
        if self.extract_from_filename:
            # The database contains a plain and full filename.
            use_filename = True
            filename = value
            _, extension = os.path.splitext(filename)
            log.info(f"extract_text: disk file, filename={filename!r}")

        elif self.extract_from_file_format:
            # The database contains a filename. However, it may not be a full
            # path. For example, in RiO, we have fields like
            #   dbo.ClientDocument.Path, e.g. '1-1-20121023-1000001-LET.pdf'
            #   dbo.ClientDocument.ClientID, e.g. '1000001-LET.pdf'
            # and the disk file might be
            #   C:\some_base_directory\1000001\Docs\1-1-20121023-1000001-LET.pdf
            # We could specify this as a file spec:
            #   "C:\some_base_directory\{ClientID}\{Path}".
            # In principle, this might need to be field-specific, so it could
            # go in the data dictionary (rather than as a setting that's
            # constant across an entire anonymisation run).
            # Let's introduce ALTERMETHOD.FILENAME_FORMAT_TO_TEXT, in v0.18.18.
            #
            # Create a dictionary of column name -> value
            ffdict = {}  # type: Dict[str, Any]
            for i, ddr in enumerate(ddrows):
                ffdict[ddr.src_field] = row[i]
            # Use that dictionary with the format string to make the filename
            log.debug(
                f"extract_text: file_format_str={repr(self.file_format_str)}, "
                f"ffdict={repr(ffdict)}")
            use_filename = True
            filename = self.file_format_str.format(**ffdict)
            _, extension = os.path.splitext(filename)
            log.info(f"extract_text: disk file, filename={filename!r}")

        else:
            # The database contains the BLOB itself. However, we'd also like to
            # know the file type, here from its extension. We look for another
            # field that contains the extension, marked as such using
            # alter_method.extract_ext_field in the data dictionary.
            blob = value
            extindex = next(
                (i for i, ddr in enumerate(ddrows)
                    if ddr.src_field == self.extract_ext_field),
                None)
            if extindex is None:
                # Configuration error
                raise ValueError(
                    f"Bug: missing extension field for "
                    f"alter_method={self.get_text()}")
            extension = row[extindex]
            log.info(f"extract_text: database BLOB, extension={extension}")

        # Is it a permissible file type?
        if not self.config.extract_text_extension_permissible(extension):
            log.info(f"Extension {extension!r} not permissible; skipping")
            return None, False

        if use_filename:
            if not filename:
                log.error("No filename; skipping")
                return None, False

            if not os.path.isfile(filename):
                log.error(f"Filename {filename!r} is not a file; skipping")
                return None, False

        # Extract text from the file (given its filename), or from a BLOB.
        try:
            textconfig = TextProcessingConfig(
                plain=self.config.extract_text_plain,
                width=self.config.extract_text_width,
            )
            value = document_to_text(filename=filename,
                                     blob=blob,
                                     extension=extension,
                                     config=textconfig)
        except Exception as e:
            # Runtime error
            traceback.print_exc()  # full details, please
            log.error(f"Caught exception from document_to_text: {e}")
            return None, False
        return value, True
