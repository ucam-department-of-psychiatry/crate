#!/usr/bin/env python

"""
crate_anon/common/extendedconfigparser.py

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

**Slightly extended ConfigParser.**

"""

import ast
import configparser
from typing import Any, Dict, Iterable, Generator, List, Optional
# http://mypy-lang.org/examples.html
# https://www.python.org/dev/peps/pep-0484/
# https://docs.python.org/3/library/typing.html

from crate_anon.anonymise.dbholder import DatabaseHolder


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
                    raise ValueError(
                        f"Value {value} less than minimum of {minimum}")
            if maximum is not None:
                if value > maximum:
                    raise ValueError(
                        f"Value {value} more than maximum of {maximum}")
            yield value
        except ValueError:
            if not suppress_errors:
                raise


DB_SAFE_CONFIG_FWD_REF = "DatabaseSafeConfig"


class ExtendedConfigParser(configparser.ConfigParser):
    """
    A version of ``configparser.ConfigParser`` with assistance functions for
    reading parameters.
    """

    def __init__(self, *args, **kwargs) -> None:
        kwargs['interpolation'] = None
        kwargs['inline_comment_prefixes'] = ('#', ';')
        # 'converters': Python 3.5 and up
        super().__init__(*args, **kwargs)

    # Use the underlying ConfigParser class for e.g.
    #       getboolean(section, option)

    # UNNECESSARY: USE inline_comment_prefixes
    #
    # @staticmethod
    # def strip_inline_comment(text, comment_chars=None):
    #     if comment_chars is None:
    #         comment_chars = ['#', ';']  # standard for ConfigParser
    #     absent = -1
    #     commentpos = absent
    #     for cc in comment_chars:
    #         pos = text.find(cc)
    #         if pos != absent:
    #             commentpos = min(commentpos,
    #                              pos) if commentpos != absent else pos
    #     if commentpos == absent:
    #         return text.strip()
    #     return text[:commentpos].strip()

    @staticmethod
    def raise_missing(section: str,
                      option: str) -> None:
        """
        Raise :exc:`ValueError` to complain about a missing parameter.

        Args:
            section: section name
            option: parameter name
        """
        raise ValueError(
            f"Config section {section}: missing parameter: {option}")

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
            raise ValueError(f"Option {option} must evaluate to a Python list "
                             f"using ast.literal_eval()")
        return pyvalue

    def get_database(self,
                     section: str,
                     dbname: str = None,
                     srccfg: DB_SAFE_CONFIG_FWD_REF = None,
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
        url = self.get_str(section, 'url', required=True)
        return DatabaseHolder(dbname, url, srccfg=srccfg,
                              with_session=with_session,
                              with_conn=with_conn,
                              reflect=reflect)

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
            env = {}
        newitems = {(str(k), str(v))
                    for k, v in self.items(section)}
        # items() returns a list of (name, value) tuples
        env.update(newitems)
        return env
