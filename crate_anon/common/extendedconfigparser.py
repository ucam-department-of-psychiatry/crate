#!/usr/bin/env python

"""
crate_anon/common/extendedconfigparser.py

===============================================================================

    Copyright (C) 2015-2020 Rudolf Cardinal (rudolf@pobox.com).

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

**Slightly extended ConfigParser.**

"""

import ast
import configparser
import logging
from typing import (Any, Dict, Iterable, Generator, List, Optional, TextIO,
                    TYPE_CHECKING)

from crate_anon.anonymise.dbholder import DatabaseHolder
from crate_anon.nlp_manager.constants import DatabaseConfigKeys

if TYPE_CHECKING:
    from crate_anon.anonymise.config import DatabaseSafeConfig

log = logging.getLogger(__name__)


def configfail(errmsg) -> None:
    """
    Args:
        errmsg: error message

    Raises:
        :exc:`ValueError`

    """
    log.critical(errmsg)
    raise ValueError(errmsg)


def gen_lines(multiline: str) -> Generator[str, None, None]:
    """
    Generate lines from a multi-line string. (Apply :func:`strip`, too.)
    """
    for line in multiline.splitlines():
        line = line.strip()
        if line:
            yield line


def gen_words(lines: Iterable[str]) -> Generator[str, None, None]:
    """
    Generate words from lines.
    """
    for line in lines:
        for word in line.split():
            yield word


def gen_ints(words: Iterable[str],
             minimum: int = None,
             maximum: int = None,
             suppress_errors: bool = False) -> Generator[int, None, None]:
    """
    Generate integers from words.

    Args:
        words: iterable of word strings
        minimum: minimum permissible value, or ``None``
        maximum: maximum permissible value, or ``None``
        suppress_errors: suppress values that fail, rather than raising an
            exception

    Yields:
        integers

    Raises:
        :exc:`ValueError` if bad values come through, unless
        ``suppress_errors`` is set.

    """
    for word in words:
        try:
            value = int(word)
            if minimum is not None:
                if value < minimum:
                    configfail(f"Value {value} less than minimum of {minimum}")
            if maximum is not None:
                if value > maximum:
                    configfail(f"Value {value} more than maximum of {maximum}")
            yield value
        except ValueError:
            if not suppress_errors:
                raise


class ExtendedConfigParser(configparser.ConfigParser):
    """
    A version of ``configparser.ConfigParser`` with assistance functions for
    reading parameters.
    """

    def __init__(self, *args, case_sensitive: bool = False, **kwargs) -> None:
        """
        Args:
            case_sensitive:
                Make the parser case-sensitive for option names?
        """
        kwargs['interpolation'] = None
        kwargs['inline_comment_prefixes'] = ('#', ';')
        # 'converters': Python 3.5 and up
        super().__init__(*args, **kwargs)
        if case_sensitive:
            # https://stackoverflow.com/questions/1611799/preserve-case-in-configparser  # noqa
            self.optionxform = str

    # Use the underlying ConfigParser class for e.g.
    #       getboolean(section, option)

    @staticmethod
    def raise_missing(section: str,
                      option: str) -> None:
        """
        Raise :exc:`ValueError` to complain about a missing parameter.

        Args:
            section: section name
            option: parameter name
        """
        configfail(f"Config section [{section}]: missing parameter: {option}")

    def require_section(self, section: str) -> None:
        """
        Requires that a section be present, or raises :exc:`ValueError`.

        Args:
            section: section name
        """
        if not self.has_section(section):
            log.warning(f"Sections: {list(self.keys())!r}")
            configfail(f"Config missing section: {section}")

    def require_option_to_be_absent(self, section: str, option: str,
                                    msg: str) -> None:
        """
        Require that an option be absent in the specified section, or print
        a message and raise :exc:`ValueError`.
        """
        if not self.has_option(section, option):
            return
        configfail(msg)

    def get_str(self,
                section: str,
                option: str,
                required: bool = False,
                default: str = None) -> Optional[str]:
        """
        Returns a string parameter.

        Args:
            section: section name
            option: parameter name
            required: raise :exc:`ValueError` if the parameter is missing?
            default: value to return if parameter is missing and not required

        Returns:
            string parameter value, or ``default``
        """
        if required and default is not None:
            raise AssertionError("required and default are incompatible")
        s = self.get(section, option, fallback=default)
        if required and not s:
            self.raise_missing(section, option)
        return s

    def get_str_list(self,
                     section: str,
                     option: str,
                     as_words: bool = True,
                     lower: bool = False,
                     required: bool = False) -> List[str]:
        """
        Returns a string list parameter.

        Args:
            section: section name
            option: parameter name
            as_words: break the value into words (rather than lines)?
            lower: force the return value into lower case?
            required: raise :exc:`ValueError` if the parameter is missing?

        Returns:
            list of strings
        """
        multiline = self.get(section, option, fallback='')
        if lower:
            multiline = multiline.lower()
        if as_words:
            result = list(gen_words(gen_lines(multiline)))
        else:  # as lines
            result = list(gen_lines(multiline))
        if required and not result:
            self.raise_missing(section, option)
        return result

    def get_int_default_if_failure(self,
                                   section: str,
                                   option: str,
                                   default: int = None) -> Optional[int]:
        """
        Returns an integer parameter, or a default if we can't read one.

        Args:
            section: section name
            option: parameter name
            default: value to return if the parameter cannot be read (missing
                or not an integer)

        Returns:
            an integer, or ``default``
        """
        try:
            return self.getint(section, option, fallback=default)
        except ValueError:  # e.g. invalid literal for int() with base 10
            return default

    def get_int_raise_if_no_default(self,
                                    section: str,
                                    option: str,
                                    default: int = None) -> int:
        """
        Like :meth:`get_int_default_if_failure`, but if the default is given
        as ``None`` and no value is found, raises an exception.
        """
        result = self.get_int_default_if_failure(
            section=section, option=option, default=default)
        if result is None:
            self.raise_missing(section, option)
        return result

    def get_int_positive_raise_if_no_default(self,
                                             section: str,
                                             option: str,
                                             default: int = None) -> int:
        """
        Like :meth:`get_int_default_if_failure`, but also requires
        that the result be greater than or equal to 0.
        """
        result = self.get_int_raise_if_no_default(
            section=section, option=option, default=default)
        if result < 0:
            configfail(f"Config section [{section}]: option {option!r} "
                       f"must not be negative")
        return result

    def get_int_list(self,
                     section: str,
                     option: str,
                     minimum: int = None,
                     maximum: int = None,
                     suppress_errors: bool = True) -> List[int]:
        """
        Returns a list of integers from a parameter.

        Args:
            section: config section name
            option: parameter name
            minimum: minimum permissible value, or ``None``
            maximum: maximum permissible value, or ``None``
            suppress_errors: suppress values that fail, rather than raising an
                exception

        Returns:
            list of integers

        """
        multiline = self.get(section, option, fallback='')
        return list(gen_ints(gen_words(gen_lines(multiline)),
                             minimum=minimum,
                             maximum=maximum,
                             suppress_errors=suppress_errors))

    def get_bool(self,
                 section: str,
                 option: str,
                 default: bool = None) -> bool:
        """
        Retrieves a boolean value from a parser.


        Args:
            section:
                section name within config file
            option:
                option (parameter) name within that section
            default:
                Value to return if option is absent and not required. If the
                default if not specified, and the option is missing, raise an
                error.

        Returns:
            Boolean value

        Raises:
            NoSectionError: if the section is absent
            NoOptionError: if the parameter is absent and required

        """
        result = self.getboolean(section, option, fallback=default)
        if result is None:
            self.raise_missing(section, option)
        return result

    def get_pyvalue_list(self,
                         section: str,
                         option: str,
                         default: Any = None) -> List[Any]:
        """
        Returns a list of Python values, produced by applying
        :func:`ast.literal_eval` to the string parameter value, and checking
        that the result is a list.

        Args:
            section: config section name
            option: parameter name
            default: value to return if no string is found for the parameter

        Returns:
            a Python list of some sort

        Raises:
            :exc:`ValueError` if a string is found but it doesn't evaluate to
            a list

        """
        default = default or []
        strvalue = self.get(section, option, fallback=None)
        if not strvalue:
            return default
        pyvalue = ast.literal_eval(strvalue)
        # Now, make sure it's a list:
        # http://stackoverflow.com/questions/1835018
        if not isinstance(pyvalue, list):
            configfail(f"Option {option} must evaluate to a Python list "
                       f"using ast.literal_eval()")
        return pyvalue

    def get_database(self,
                     section: str,
                     dbname: str = None,
                     srccfg: "DatabaseSafeConfig" = None,
                     with_session: bool = False,
                     with_conn: bool = False,
                     reflect: bool = False) -> DatabaseHolder:
        """
        Gets a database description from the config file.

        Args:
            section: config section name
            dbname: name to give the database (if ``None``, the section name
                will be used)
            srccfg: :class:`crate_anon.anonymise.config.DatabaseSafeConfig`
            with_session: create an SQLAlchemy Session?
            with_conn: create an SQLAlchemy connection (via an Engine)?
            reflect: read the database structure (when required)?

        Returns:
            a :class:`crate_anon.anonymise.dbholder.DatabaseHolder` object

        """

        dbname = dbname or section
        url = self.get_str(section, DatabaseConfigKeys.URL, required=True)
        echo = self.get_bool(section, DatabaseConfigKeys.ECHO, default=False)
        return DatabaseHolder(dbname, url, srccfg=srccfg,
                              with_session=with_session,
                              with_conn=with_conn,
                              reflect=reflect,
                              echo=echo)

    def get_env_dict(
            self,
            section: str,
            parent_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        Gets an operating system environment variable dictionary (``variable:
        value`` mapping) from the config file.

        Args:
            section: config section name
            parent_env: optional starting point (e.g. parent OS environment)

        Returns:
            a dictionary suitable for use as an OS environment

        """
        if parent_env:
            env = parent_env.copy()
        else:
            env = {}  # type: Dict[str, str]
        newitems = {(str(k), str(v))
                    for k, v in self.items(section)}
        # items() returns a list of (name, value) tuples
        env.update(newitems)
        return env


class ConfigSection(object):
    """
    Represents a section within a config file.
    """
    def __init__(self,
                 section: str,
                 parser: ExtendedConfigParser = None,
                 filename: str = None,
                 fileobj: TextIO = None,
                 case_sensitive: bool = False,
                 encoding: str = "utf8") -> None:
        """
        You must specify exactly one of ``parser``, ``filename``, or
        ``fileobj``.

        Args:
            section:
                The name of the section within the config file, e.g.
                ``main`` for the section marked by ``[main]``.
            parser:
                Specify this, a :class:`ExtendedConfigParser`, if you
                have already loaded the file into a parser.
            filename:
                The name of a file to option. Specify also the encoding.
            fileobj:
                A file-like object to open.
            case_sensitive:
                If ``parser`` is used, make it case-sensitive for options?
            encoding:
                If ``filename`` is used, the character encoding.
        """
        self.section = section

        # Check paramers
        if bool(parser) + bool(filename) + bool(fileobj) != 1:
            raise ValueError("Specify exactly one of: "
                             "parser, filename, fileobj")

        # Record or create parser
        if parser:
            assert isinstance(parser, ExtendedConfigParser)
            self.parser = parser
        elif filename:
            self.parser = ExtendedConfigParser(case_sensitive=case_sensitive)
            log.info(f"Reading config file: {filename}")
            self.parser.read(filename, encoding=encoding)
        else:
            self.parser.read_file(fileobj)

        # Check section exists
        self.parser.require_section(self.section)

    def opt_str(self,
                option: str,
                default: str = None,
                required: bool = False) -> str:
        """
        Reads a string option.

        Args:
            option: parameter (option) name
            default: default if not found and not required
            required: is the parameter required?
        """
        return self.parser.get_str(self.section, option, default=default,
                                   required=required)

    def opt_multiline(self,
                      option: str,
                      required: bool = False,
                      lower: bool = False,
                      as_words: bool = True) -> List[str]:
        """
        Reads a multiline string, returning a list of words or lines.
        Similar to :meth:`opt_strlist`, but different defaults.

        Args:
            option: parameter (option) name
            required: is the parameter required?
            lower: convert to lower case?
            as_words: split as words, rather than as lines?
        """
        return self.parser.get_str_list(
            self.section,
            option,
            as_words=as_words,
            lower=lower,
            required=required
        )

    def opt_strlist(self,
                    option: str,
                    required: bool = False,
                    lower: bool = False,
                    as_words: bool = True) -> List[str]:
        """
        Returns a list of strings from the config file.
        Similar to :meth:`opt_multiline`, but different defaults.

        Args:
            option: parameter (option) name
            required: is the parameter required?
            lower: convert to lower case?
            as_words: split as words, rather than as lines?
        """
        return self.parser.get_str_list(
            self.section,
            option,
            as_words=as_words,
            lower=lower,
            required=required
        )

    def opt_bool(self,
                 option: str,
                 default: bool = None) -> bool:
        """
        Reads a boolean option.

        Args:
            option: parameter (option) name
            default: default if not found (if None, the parameter is required)
        """
        return self.parser.get_bool(self.section, option, default=default)

    def opt_int(self,
                option: str,
                default: int = None) -> Optional[int]:
        """
        Reads an integer option.

        Args:
            option: parameter (option) name
            default: default if not found (if None, the parameter is required)
        """
        return self.parser.get_int_raise_if_no_default(
            self.section, option, default=default)

    def opt_int_positive(self,
                         option: str,
                         default: int = None) -> Optional[int]:
        """
        Reads an integer option that must be greater than or equal to 0.

        Args:
            option: parameter (option) name
            default: default if not found (if None, the parameter is required)
        """
        return self.parser.get_int_positive_raise_if_no_default(
            self.section, option, default=default)

    def opt_multiline_int(self,
                          option: str,
                          minimum: int = None,
                          maximum: int = None) -> List[int]:
        """
        Returns a list of integers within the specified range.
        """
        return self.parser.get_int_list(
            self.section,
            option,
            minimum=minimum,
            maximum=maximum,
            suppress_errors=False
        )

    def opt_multiline_csv_pairs(self, option: str) -> Dict[str, str]:
        """
        Reads a dictionary of key-value pairs, specified as lines each of
        the format ``key, value``.

        Args:
            option: name of the config file option
        """
        d = {}  # type: Dict[str, str]
        lines = self.opt_multiline(option, as_words=False)
        for line in lines:
            pair = [item.strip() for item in line.split(",")]
            if len(pair) != 2:
                raise ValueError(f"For option {option}: specify items as "
                                 f"a list of comma-separated pairs")
            d[pair[0]] = pair[1]
        return d

    def opt_pyvalue_list(self, option: str, default: Any = None) -> Any:
        """
        Returns a list of evaluated Python values.
        """
        return self.parser.get_pyvalue_list(
            self.section, option, default=default)

    def require_absent(self, option: str, msg: str) -> None:
        """
        If an option is present, print the message and raise an exception.
        Use this for deprecated option names.
        """
        self.parser.require_option_to_be_absent(self.section, option, msg)
