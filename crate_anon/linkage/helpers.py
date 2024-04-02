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

Avoid using pickle for caching; it is insecure (arbitrary code execution).

"""

# =============================================================================
# Imports
# =============================================================================

from argparse import ArgumentTypeError
from contextlib import contextmanager, ExitStack
from io import StringIO, TextIOWrapper
import logging
from math import log as math_ln
import os
import random
import re
import string
from typing import (
    Any,
    Dict,
    Generator,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TYPE_CHECKING,
    Union,
)
import unicodedata
from zipfile import ZipFile

import regex
from cardinal_pythonlib.datetimefunc import coerce_to_pendulum_date
from cardinal_pythonlib.fileops import mkdir_p
from fuzzy import DMetaphone
from numba import jit
from pendulum import Date
from pendulum.parsing.exceptions import ParserError

from crate_anon.anonymise.anonregex import get_uk_postcode_regex_string
from crate_anon.common.logfunc import warn_once
from crate_anon.common.regex_helpers import anchor
from crate_anon.linkage.constants import (
    FuzzyDefaults,
    MANGLE_PRETRANSLATE,
    MINUS_INFINITY,
    NONE_TYPE,
    SAFE_UPPER_PRETRANSLATE,
    SIMPLIFY_PUNCTUATION_WHITESPACE_TRANS,
)

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

UK postcodes have this format (A letter, 9 digit, plus Wikipedia concrete
examples;
https://en.wikipedia.org/wiki/Postcodes_in_the_United_Kingdom#Formatting):

+------------+----------------+------------+----------+
| Postcode                                            |
+------------+----------------+------------+----------+
| Outward code                | Inward code           |
+------------+----------------+------------+----------+
| Area (1-2) | District (1-2) | Sector (1) | Unit (2) |
| (A, AA)    | (9, 99, 9A)    | (9)        | (AA)     |
+------------+----------------+------------+----------+
| AA         | 9A             | 9          | AA       |
| SW         | 1W             | 0          | NY       |
| EC         | 9A             | 9          | AA       |
+------------+----------------+------------+----------+
| A          | 9A             | 9          | AA       |
| W          | 1A             | 0          | AX       |
+------------+----------------+------------+----------+
| A          | 9              | 9          | AA       |
| M          | 1              | 1          | AE       |
+------------+----------------+------------+----------+
| A          | 99             | 9          | AA       |
| B          | 33             | 8          | TH       |
+------------+----------------+------------+----------+
| AA         | 9              | 9          | AA       |
| CR         | 2              | 6          | XH       |
+------------+----------------+------------+----------+
| AA         | 99             | 9          | AA       |
| DN         | 55             | 1          | PT       |
+------------+----------------+------------+----------+

Then there are "special cases" that don't fit, but they are mostly
extraterritorial. See
https://en.wikipedia.org/wiki/Postcodes_in_the_United_Kingdom#Special_cases.

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

_ = """

For a sense of metaphones:

>>> dmeta("Rudolf")
[b'RTLF', None]
>>> dmeta("Cardinal")
[b'KRTN', None]
>>> dmeta("Supercalifragilistic")
[b'SPRK', None]
>>> dmeta("Christopher")
[b'KRST', None]
>>> dmeta("Chris")
[b'KRS', None]
>>> dmeta("C")
[b'K', None]
>>> dmeta("Philip")
[b'FLP', None]
>>> dmeta("Phil")
[b'FL', None]
>>> dmeta("Phi")
[b'F', None]
>>> dmeta("Knuth")  # https://stackabuse.com/phonetic-similarity-of-words-a-vectorized-approach-in-python/
[b'N0', b'NT']

>>> dmeta("Clérambault")  # raises UnicodeEncodeError

"""  # noqa


# =============================================================================
# For caching
# =============================================================================


def mkdir_for_filename(filename: str) -> None:
    """
    Ensures that a directory exists for the filename.
    """
    assert filename
    mkdir_p(os.path.dirname(filename))


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
        log.debug(f"... finished reading: {filename}")


# =============================================================================
# Name manipulation
# =============================================================================

REMOVE_PUNCTUATION_SPACE_TABLE = str.maketrans("", "", string.punctuation)
# ... the three-argument version of str.maketrans removes anything in the third
# category. The object returned is a dictionary mapping integer ASCII values
# to replacement character values (or None).
REMOVE_PUNCTUATION_SPACE_TABLE[ord(" ")] = None  # also remove spaces
NONWORD_REGEX = regex.compile(r"\W")
ONE_OR_MORE_SPACE_REGEX = regex.compile(r"\s+")


def mangle_unicode_to_ascii(s: Any) -> str:
    """
    Mangle unicode to ASCII, losing accents etc. in the process.
    This is a slightly different version to that in cardinal_pythonlib, because
    the Eszett gets a rough ride:

    .. code-block:: python

        "Straße Clérambault".encode("ascii", "ignore")  # b'Strae Clerambault'

    So we add the ``MANGLE_PRETRANSLATE`` step.
    """
    if s is None:
        return ""
    if not isinstance(s, str):
        s = str(s)
    return (
        unicodedata.normalize("NFKD", s)
        .translate(MANGLE_PRETRANSLATE)
        .encode("ascii", "ignore")  # gets rid of accents
        .decode("ascii")  # back to a string
    )


def safe_upper(name: str) -> str:
    """
    Convert to upper case, but don't mess up a few specific accents. Note that:

    - 'ß'.upper() == 'SS' but 'ẞ'.upper() == 'ẞ'

    ... here, we will use an upper-case Eszett, and the "SS" will be dealt with
    through transliteration.
    """
    return name.translate(SAFE_UPPER_PRETRANSLATE).upper()


def remove_redundant_whitespace(x: str) -> str:
    """
    Strip at edges; remove double-spaces; remove any other whitespace by a
    single space.
    """
    return ONE_OR_MORE_SPACE_REGEX.sub(" ", x).strip()


def simplify_punctuation_whitespace(x: str) -> str:
    """
    Simplify punctuation and whitespace, e.g. curly to straight quotes, tab to
    space, en dash to hyphen, etc.
    """
    return x.translate(SIMPLIFY_PUNCTUATION_WHITESPACE_TRANS)


def standardize_name(name: str) -> str:
    """
    Converts a name to a standard form: upper case (will also e.g. translate
    Eszett to SS), no spaces, no punctuation.

    This is the format used by the US surname database, e.g. ACOSTAPEREZ for
    (probably) Acosta Perez, and just PEREZ without e.g. PÉREZ.

    We use this for our name frequency databases. For other purposes, we use
    a more sophisticated approach; see e.g. surname_alternative_fragments().

    Examples: see unit tests.
    """
    return mangle_unicode_to_ascii(
        name.upper().translate(REMOVE_PUNCTUATION_SPACE_TABLE)
    )


def _gen_name_versions(
    x: str,
    accent_transliterations: Dict[
        int, Union[str, int, None]
    ] = FuzzyDefaults.ACCENT_TRANSLITERATIONS_TRANS,
) -> Generator[str, None, None]:
    """
    Generate the string itself and accent-mangled and accent-transliterated
    versions thereof. We assume that either nothing happens, mangling
    happens, or transliteration happens, but not some nasty combination.
    """
    x = x.strip()
    if not x:
        return
    # The string:
    yield x
    # Mangled, e.g. Ü to U:
    yield mangle_unicode_to_ascii(x)
    # Transliterated, e.g. Ü to UE.
    yield x.translate(accent_transliterations)


def surname_alternative_fragments(
    surname: str,
    accent_transliterations: Dict[
        int, Union[str, int, None]
    ] = FuzzyDefaults.ACCENT_TRANSLITERATIONS_TRANS,
    nonspecific_name_components: Set[
        str
    ] = FuzzyDefaults.NONSPECIFIC_NAME_COMPONENTS,
) -> List[str]:
    """
    Return a list of fragments that may occur as substitutes for the name
    (including the name itself). Those fragments include:

    - Parts of double-barrelled surnames.
    - ASCII-mangled versions of accents (e.g. Ü to U).
    - Transliterated versions of accents (e.g. Ü to UE).

    Upper case will be used throughout.

    Args:
        surname:
            The name to process. This should contain all original accents,
            spacing, and punctuation (i.e. should NOT have been standardized as
            above). Case is unimportant (we will use upper case internally).
        accent_transliterations:
            A mapping from accents to potential transliterated versions, in the
            form of a Python string translation table.
        nonspecific_name_components:
            Name fragments that should not be produced in their own right, e.g.
            nobiliary particles such as "van" in "van Beethoven".

    Returns:
        A list of fragments: full name first, then other fragments in
        alphabetical order.
    """
    if not surname:
        # No name, nothing to do.
        return []

    # Very basic standardization first: upper case, sort out punctuation.
    surname = safe_upper(simplify_punctuation_whitespace(surname))

    # Split into word chunks:
    chunks = list(filter(None, NONWORD_REGEX.split(surname)))
    # Filtering is required, e.g. "hello ' world" -> ['hello', '', '', 'world']

    # Now make a standardized version of the name where punctuation/spaces have
    # been removed (as per the US name databases also):
    surname = "".join(chunks)

    # Create a set of fragments. The set will de-duplicate.
    fragments = set()  # type: Set[str]

    # The name itself, and any accent-modified versions:
    fragments.update(_gen_name_versions(surname, accent_transliterations))

    # Components, and any accent-modified versions:
    for chunk in chunks:
        # All should be pre-stripped and none should be blank
        if chunk in nonspecific_name_components:
            continue
        fragments.update(_gen_name_versions(chunk, accent_transliterations))
    # This process may well have worked through duplicates, but the set will
    # take care of those.

    # Return the (standardized) name first.
    return [surname] + sorted(fragments - {surname})


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
        warn_once(f"No metaphone for {x!r}", log, level=logging.DEBUG)
        return ""
    return first_part.decode("ascii")


def get_first_two_char(x: str) -> str:
    """
    Returns the first two characters of a string. Having this as a function is
    slight overkill.
    """
    return x[:2]


# =============================================================================
# Postcode manipulation
# =============================================================================

POSTCODE_REGEX = re.compile(
    anchor(get_uk_postcode_regex_string(at_word_boundaries_only=False))
    # Need at_word_boundaries_only=True.
    # We don't want at_word_boundaries_only=True, since that matches e.g.
    # "VALID_POSTCODE JUNK". We want anchor() instead.
)


def standardize_postcode(postcode_unit_or_sector: str) -> str:
    """
    Standardizes postcodes to "no space" format.
    """
    return postcode_unit_or_sector.upper().translate(
        REMOVE_PUNCTUATION_SPACE_TABLE
    )


def get_postcode_sector(
    postcode_unit: str, prestandardized: bool = False
) -> str:
    """
    Returns the postcode (area + district +) sector from a full postcode. For
    example, converts "AB12 3CD" to "AB12 3".

    While the format and length of the first part (area + district) varies (2-4
    characters), the format of the second (sector + unit) is fixed, of the
    format "9AA" (3 characters);
    https://en.wikipedia.org/wiki/Postcodes_in_the_United_Kingdom#Formatting.
    So to get the sector, we chop off the last two characters.
    """
    if not prestandardized:
        postcode_unit = standardize_postcode(postcode_unit)
    return postcode_unit[:-2]


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
PSEUDOPOSTCODE_NFA = "ZZ993VZ"  # no fixed abode


def is_pseudopostcode(
    postcode_unit: str, prestandardized: bool = False
) -> bool:
    """
    Is this a pseudopostcode?
    """
    if not prestandardized:
        postcode_unit = standardize_postcode(postcode_unit)
    return postcode_unit.startswith(PSEUDO_POSTCODE_START)


def is_nfa_postcode(postcode_unit: str, prestandardized: bool = False) -> bool:
    """
    Is this the pseudopostcode meaning "no fixed abode"?
    """
    if not prestandardized:
        postcode_unit = standardize_postcode(postcode_unit)
    return postcode_unit == PSEUDOPOSTCODE_NFA


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
        cfg: the main :class:`MatchConfig` object
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
        # Either x > 0 but causing problems anyway (unlikely), or x == 0.
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
            log posterior odds of H,
            :math:`ln(\frac{ P(H | D) }{ P(\neg H | D) })`
    """
    return log_prior_odds + ln(p_d_given_h) - ln(p_d_given_not_h)


@jit(nopython=True)
def log_likelihood_ratio_from_p(
    p_d_given_h: float, p_d_given_not_h: float
) -> float:
    r"""
    Calculates the log of the odds ratio.
    Fast implementation.

    Args:
        p_d_given_h:
            :math:`P(D | H)`
        p_d_given_not_h:
            :math:`P(D | \neg H)`

    Returns:
        float:
            log likelihood ratio,
            :math:`ln(\frac{ P(D | H) }{ P(D | \neg H) })`
    """
    return ln(p_d_given_h) - ln(p_d_given_not_h)


# =============================================================================
# Read and check the type of dictionary values
# =============================================================================


def getdictval(
    d: Dict[str, Any],
    key: str,
    type_: Type,
    mandatory: bool = False,
    default: Any = None,
) -> Any:
    """
    Returns a value from a dictionary, or raises ValueError.

    - If ``mandatory`` is True, the key must be present, and the value must not
      be ``None`` or a blank string.
    - If ``mandatory`` is False and the key is absent, ``default`` is returned.
    - The value must be of type `type_` (or ``None`` if permitted).
    """
    try:
        v = d[key]
    except KeyError:
        if mandatory:
            raise ValueError(f"Missing key: {key}")
        else:
            return default
    if mandatory and (v is None or v == ""):
        raise ValueError(f"Missing or blank value: {key}")
    if not isinstance(v, (type_, NONE_TYPE)):
        raise ValueError(
            f"Value for {key!r} should be of type {type_} "
            f"but was of type {type(v)}; was {v!r}"
        )
    return v


def validate_prob(p: float, description: str) -> None:
    """
    Checks a probability is in the range [0, 1] or raises :exc:`ValueError`.
    """
    if not 0 <= p <= 1:
        raise ValueError(
            f"Bad probability for {description}: {p} "
            f"-- must be in range [0, 1]"
        )


def validate_uncertain_prob(p: float, description: str) -> None:
    """
    Checks a probability is in the range (0, 1) or raises :exc:`ValueError`.
    """
    if not 0 < p < 1:
        raise ValueError(
            f"Bad probability for {description}: {p} "
            f"-- must be in range (0, 1)"
        )


def getdictprob(
    d: Dict[str, Any],
    key: str,
    mandatory: bool = False,
    default: Optional[float] = None,
) -> Optional[float]:
    """
    As for :func:`getdictval` but returns a probability and checks that it is
    in range. The default is non-mandatory, returning None.
    """
    v = getdictval(d, key, float, mandatory=mandatory, default=default)
    if v is None:
        return None
    validate_prob(v, key)
    return v


# =============================================================================
# Dates
# =============================================================================

ISO_DATE_REGEX = re.compile(
    # yyyy-MM-dd, from the year 0000 onwards.
    r"^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12][0-9]|3[01])$"
    #  ^^^^^ ^^^^^^^^^^^^^^^^^ ^^^^^^^^^^^^^^^^^^^^^^^^^^
    #  year       month             day
)
# Also: https://stackoverflow.com/questions/3143070


def is_valid_isoformat_date(x: str) -> bool:
    """
    Validates an ISO-format date with separators, e.g. '2022-12-31'.
    """
    if not isinstance(x, str):
        return False
    if not ISO_DATE_REGEX.match(x):
        # We check this because "2020" will convert to 2020-01-01 if we just
        # let Pendulum autoconvert below.
        return False
    try:
        coerce_to_pendulum_date(x)
    except (ParserError, ValueError):
        return False
    return True


def is_valid_isoformat_blurred_date(x: str) -> bool:
    """
    Validates an ISO-format date (as above) that must be the first of the
    month.
    """
    if not is_valid_isoformat_date(x):
        return False
    d = coerce_to_pendulum_date(x)
    return d.day == 1


def isoformat_optional_date_str(d: Optional[Date]) -> str:
    """
    Returns a date in string format.
    """
    if not d:
        return ""
    return d.isoformat()


def isoformat_date_or_none(d: Optional[Date]) -> Optional[str]:
    """
    Returns a date in string format, or None if it is absent.
    """
    if not d:
        return None
    return d.isoformat()


def age_years(dob: Optional[Date], when: Optional[Date]) -> Optional[int]:
    """
    A person's age in years when something happened, or ``None`` if either
    DOB or the index date is unknown.
    """
    if dob and when:
        return (when - dob).in_years()
    return None


def mk_blurry_dates(d: Union[Date, str]) -> Tuple[str, str, str]:
    """
    Returns MONTH_DAY, YEAR_DAY, and YEAR_MONTH versions in a standard form.
    """
    # ISO format is %Y-%m-%d; see
    # https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes  # noqa
    # Here we want the shortest full representation; these are not intended to
    # be human-legible.
    d = coerce_to_pendulum_date(d)
    dob_md = d.strftime("%m%d")
    dob_yd = d.strftime("%Y%d")
    dob_ym = d.strftime("%Y%m")
    return dob_md, dob_yd, dob_ym


# =============================================================================
# argparse helpers
# =============================================================================


def optional_int(value: str) -> Optional[int]:
    """
    ``argparse`` argument type that checks that its value is an integer or the
    value ``None``.
    """
    if value.lower() == "none":
        return None
    try:
        return int(value)
    except (AssertionError, TypeError, ValueError):
        raise ArgumentTypeError(f"{value!r} is an invalid optional int")


# =============================================================================
# Identity function
# =============================================================================


def identity(x: Any) -> Any:
    """
    Returns its input.
    """
    return x


# =============================================================================
# Perfect identifiers
# =============================================================================


def dict_from_str(x: str) -> Dict[str, str]:
    """
    Reads a dictionary like {'a': 'x', 'b': 'y'} from a string like "{a:x,
    b:y}".
    """
    if not x:
        return {}
    w = x.strip()  # working
    if w[0] != "{" or w[-1] != "}":
        raise ValueError(f"Bad dict string: {x!r}")
    w = w[1:-1].strip()
    d = {}
    for pair_str in w.split(","):
        if pair_str.count(":") != 1:
            raise ValueError(f"Bad dict string: {x!r}")
        k, v = pair_str.split(":")
        d[k.strip()] = v.strip()
    return d


def standardize_perfect_id_key(k: str) -> str:
    """
    Keys are compared case-insensitive, in lower case.
    """
    return k.strip().lower()


def standardize_perfect_id_value(k: Any) -> str:
    """
    Values are forced to strings and compared case-insensitive, in upper case.
    """
    return str(k).strip().upper()
