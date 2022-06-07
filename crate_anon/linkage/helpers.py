#!/usr/bin/env python

r"""
crate_anon/linkage/helpers.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

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
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

**Helper functions for linkage tools.**

"""


# =============================================================================
# Imports
# =============================================================================

from contextlib import contextmanager, ExitStack
from io import StringIO, TextIOWrapper
import logging
from math import log as math_ln
import os
import pickle
import random
import re
import string
from typing import Any, Generator, TYPE_CHECKING
from zipfile import ZipFile

from cardinal_pythonlib.fileops import mkdir_p
from cardinal_pythonlib.stringfunc import mangle_unicode_to_ascii
from fuzzy import DMetaphone
from numba import jit

from crate_anon.anonymise.anonregex import get_uk_postcode_regex_string
from crate_anon.common.logfunc import warn_once
from crate_anon.linkage.constants import MINUS_INFINITY

if TYPE_CHECKING:
    from crate_anon.linkage.matchconfig import MatchConfig

log = logging.getLogger(__name__)


# =============================================================================
# Notes
# =============================================================================

_ = """

Geography
---------

[COVERED IN THE PAPER. FURTHER DETAIL HERE.]

UK postcodes have this format:

+---------------------------------+
| Postcode                        |
+-----------------+---------------+
| Outward code    | Inward code   |
+------+----------+--------+------+
| Area | District | Sector | Unit |
+------+----------+--------+------+
| SW   | 1W       | 0      | NY   |
+------+----------+--------+------+

See
https://en.wikipedia.org/wiki/Postcodes_in_the_United_Kingdom#Formatting.

UK census geography is described at
https://www.ons.gov.uk/methodology/geography/ukgeographies/censusgeography.

The most important unit for our purposes is the Output Area (OA), the smallest
unit, which is made up of an integer number of postcode units.

So an OA is bigger than a postcode unit. But is it bigger or smaller than a
postcode sector? Smaller, I think.

- https://data.gov.uk/dataset/7f4e1818-4305-4962-adc4-e4e3effd7784/output-area-to-postcode-sector-december-2011-lookup-in-england-and-wales
- this allows you to look up *from* output area *to* postcode sector, implying
  that postcode sectors must be larger.

"""  # noqa


# =============================================================================
# Metaphones
# =============================================================================

dmeta = DMetaphone()


# =============================================================================
# Caching
# =============================================================================


def cache_load(filename: str) -> Any:
    """
    Reads from a cache.

    Args:
        filename: cache filename (pickle format)

    Returns:
        the result

    Raises:
        :exc:`FileNotFoundError` if it doesn't exist.

    See
    https://stackoverflow.com/questions/82831/how-do-i-check-whether-a-file-exists-without-exceptions

    """  # noqa
    assert filename
    try:
        log.info(f"Reading from cache: {filename}")
        result = pickle.load(open(filename, "rb"))
        log.info("... done")
        return result
    except FileNotFoundError:
        log.info("... cache not found")
        raise


def cache_save(filename: str, data: Any) -> None:
    """
    Writes to a cache.

    Args:
        filename: cache filename (pickle format)
        data: data to write
    """
    assert filename
    log.info(f"Saving to cache: {filename}")
    dirname = os.path.dirname(filename)
    mkdir_p(dirname)
    pickle.dump(data, open(filename, "wb"), protocol=pickle.HIGHEST_PROTOCOL)
    log.info("... done")


# =============================================================================
# Reading from file or zipped file
# =============================================================================


@contextmanager
def open_even_if_zipped(filename: str) -> Generator[StringIO, None, None]:
    """
    Yields (as a context manager) a text file, opened directly or through a
    ZIP file (distinguished by its extension) containing that file.
    """
    is_zip = os.path.splitext(filename)[1].lower() == ".zip"
    with ExitStack() as stack:
        if is_zip:
            log.info(f"Reading ZIP file: {filename}")
            z = stack.enter_context(ZipFile(filename))  # type: ZipFile
            contents = z.infolist()
            if not contents:
                raise ValueError("ZIP file is empty")
            first_file = contents[0]
            log.info(f"Within ZIP, reading: {first_file.filename}")
            # noinspection PyTypeChecker
            binary_file = stack.enter_context(z.open(first_file))
            f = TextIOWrapper(binary_file)
        else:
            log.info(f"Reading file: {filename}")
            # noinspection PyTypeChecker
            f = stack.enter_context(open(filename, "rt"))
        yield f
        log.info(f"... finished reading: {filename}")


# =============================================================================
# String manipulation and postcodes
# =============================================================================

ISO_DATE_REGEX = re.compile(
    r"[1-9][0-9][0-9][0-9]-(?:1[0-2]|0[1-9])-(?:3[01]|0[1-9]|[12][0-9])"
)  # YYYY-MM-DD
POSTCODE_REGEX = re.compile(
    get_uk_postcode_regex_string(at_word_boundaries_only=False)
)
REMOVE_PUNCTUATION_SPACE_TABLE = str.maketrans("", "", string.punctuation)
REMOVE_PUNCTUATION_SPACE_TABLE[ord(" ")] = None  # also remove spaces


def standardize_name(name: str) -> str:
    """
    Converts names to a standard form: upper case, no spaces, no punctuation.

    Examples:

    .. code-block:: python

        from crate_anon.tools.fuzzy_id_match import *
        standardize_name("Alice")
        standardize_name("Mary Ellen")
        standardize_name("D'Souza")
        standardize_name("de Clérambault")
    """
    return mangle_unicode_to_ascii(
        name.upper().translate(REMOVE_PUNCTUATION_SPACE_TABLE)
    )


def get_metaphone(x: str) -> str:
    """
    Returns a string representing a metaphone of the string -- specifically,
    the first (primary) part of a Double Metaphone.

    See

    - https://www.b-eye-network.com/view/1596
    - https://dl.acm.org/citation.cfm?id=349132

    The implementation is from https://pypi.org/project/Fuzzy/.

    Alternatives (soundex, NYSIIS) are in ``fuzzy`` and also in ``jellyfish``
    (https://jellyfish.readthedocs.io/en/latest/).

    .. code-block:: python

        from crate_anon.tools.fuzzy_id_match import *
        get_metaphone("Alice")  # ALK
        get_metaphone("Alec")  # matches Alice; ALK
        get_metaphone("Mary Ellen")  # MRLN
        get_metaphone("D'Souza")  # TSS
        get_metaphone("de Clerambault")  # TKRM; won't do accents

    """
    if not x:
        return ""
    metaphones = dmeta(x)
    first_part = metaphones[0]  # the first part only
    if first_part is None:
        warn_once(f"No metaphone for {x!r}", log)
        return ""
    return first_part.decode("ascii")


def standardize_postcode(postcode_unit_or_sector: str) -> str:
    """
    Standardizes postcodes to "no space" format.
    """
    return postcode_unit_or_sector.upper().translate(
        REMOVE_PUNCTUATION_SPACE_TABLE
    )


def get_postcode_sector(postcode_unit: str) -> str:
    """
    Returns the postcode (area + district +) sector from a full postcode. For
    example, converts "AB12 3CD" to "AB12 3".

    While the format and length of the first part (area + district) varies (2-4
    characters), the format of the second (sector + unit) is fixed, of the
    format "9AA" (3 characters);
    https://en.wikipedia.org/wiki/Postcodes_in_the_United_Kingdom#Formatting.
    So to get the sector, we chop off the last two characters.
    """
    return standardize_postcode(postcode_unit)[:-2]


# noinspection HttpUrlsUsage
_ = """
PSEUDO_POSTCODES = set(standardize_postcode(p) for p in (
    "ZZ99 3VZ",  # No fixed abode [1, 2]
    "ZZ99 3WZ",  # Address not known [2]
    "ZZ99 3CZ",  # England/U.K, not otherwise specified [1, 3] (*)
                 # ... or "Z99 3CZ"? [2] (*).
    "ZZ99 3GZ",  # Wales, not otherwise specified [1, 2]
    "ZZ99 1WZ",  # Scotland, not otherwise specified [1, 2]
    "ZZ99 2WZ",  # Northern Ireland, not otherwise specified [1, 2]
    # Also: ZZ99 <nnn>, where <nnn> is a country code -- so that's a large
    # range.
    # [1] http://www.datadictionary.wales.nhs.uk/index.html#!WordDocuments/postcode.htm
    # [2] https://www.england.nhs.uk/wp-content/uploads/2021/03/commissioner-assignment-method-2122-guidance-v1.1.pdf
    # [3] https://afyonluoglu.org/PublicWebFiles/Reports-TR/Veri%20Sozlugu/international/2017-HES%20Admitted%20Patient%20Care%20Data%20Dictionary.pdf
    # (*) [2] uses "Z99 3CZ" (page 6); [1, 3] use "ZZ99 3CZ".
))
PSEUDO_POSTCODE_SECTORS = set(get_postcode_sector(p) for p in PSEUDO_POSTCODES)
"""  # noqa
PSEUDO_POSTCODE_START = "ZZ99"


# def is_pseudo_postcode_sector(postcode_sector: str) -> bool:
#     """
#     Is this a pseudo-postcode sector?
#     Assumes upper case.
#     """
#     return postcode_sector.startswith(PSEUDO_POSTCODE_START)


def is_pseudo_postcode(postcode_unit: str) -> bool:
    """
    Is this a pseudo-postcode?
    Assumes upper case.
    """
    return postcode_unit.startswith(PSEUDO_POSTCODE_START)


# =============================================================================
# Functions to introduce errors (for testing)
# =============================================================================


def mutate_name(name: str) -> str:
    """
    Introduces typos into a (standardized, capitalized,
    no-space-no-punctuation) name.
    """
    n = len(name)
    a = ord("A")
    z = ord("Z")
    which = random.randrange(n)
    start_ord = ord(name[which])
    while True:
        replacement_ord = random.randint(a, z)
        if replacement_ord != start_ord:
            break
    return (
        name[:which] + chr(replacement_ord) + name[which + 1 :]  # noqa: E203
    )


def mutate_postcode(postcode: str, cfg: "MatchConfig") -> str:
    """
    Introduces typos into a UK postcode, keeping the letter/digit format.

    Args:
        postcode: the postcode to alter
        cfg: the master :class:`MatchConfig` object
    """
    n = len(postcode)
    a = ord("A")
    z = ord("Z")
    zero = ord("0")
    nine = ord("9")
    while True:
        while True:
            which = random.randrange(n)
            if postcode[which] != " ":
                break
        # noinspection PyUnboundLocalVariable
        start_ord = ord(postcode[which])
        replacement_ord = start_ord
        if postcode[which].isdigit():
            while replacement_ord == start_ord:
                replacement_ord = random.randint(zero, nine)
        else:
            while replacement_ord == start_ord:
                replacement_ord = random.randint(a, z)
        mutated = (
            postcode[:which]
            + chr(replacement_ord)
            + postcode[which + 1 :]  # noqa: E203
        )
        if cfg.is_valid_postcode(mutated):
            return mutated


# =============================================================================
# Faster maths
# =============================================================================


@jit(nopython=True)
def ln(x: float) -> float:
    """
    Version of :func:`math.log` that treats log(0) as ``-inf``, rather than
    crashing with ``ValueError: math domain error``.

    Args:
        x: parameter

    Returns:
        float: ln(x), the natural logarithm of x
    """
    # noinspection PyBroadException
    try:
        return math_ln(x)
    except Exception:  # numba.jit can only cope with Exception
        if x < 0:
            raise ValueError("Can't take log of a negative number")
        # Either x > 0 but causing problems anyway, or x == 0.
        return MINUS_INFINITY


@jit(nopython=True)
def log_posterior_odds_from_pdh_pdnh(
    log_prior_odds: float, p_d_given_h: float, p_d_given_not_h: float
) -> float:
    r"""
    Calculates posterior odds.
    Fast implementation.

    Args:
        log_prior_odds:
            log prior odds of H, :math:`ln(\frac{ P(H) }{ P(\neg H) })`
        p_d_given_h:
            :math:`P(D | H)`
        p_d_given_not_h:
            :math:`P(D | \neg H)`

    Returns:
        float:
            posterior odds of H, :math:`ln(\frac{ P(H | D) }{ P(\neg H | D) })`
    """
    return log_prior_odds + ln(p_d_given_h) - ln(p_d_given_not_h)
