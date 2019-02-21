#!/usr/bin/env python

"""
crate_anon/crateweb/extra/salutation.py

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

**Converts names to salutations and parses names into component parts.**

"""

from typing import Optional, Tuple


# =============================================================================
# Salutation and other forms of name/title generation
# =============================================================================

def title_forename_surname(title: Optional[str],
                           forename: Optional[str],
                           surname: Optional[str],
                           always_title: bool = False,
                           sex: str = '',
                           assume_dr: bool = False) -> str:
    """
    Used when reporting names. Returns a string of the format ``Title Forename
    Surname``, as far as we can work it out.

    Args:
        title: title
        forename: forename
        surname: surname
        always_title: if we don't know the title, guess one?
        sex: ``"M"`` or ``"F"`` or other/unknown
        assume_dr: assume the person has the title "Dr"?

    Returns:
        str: a string of a format like

        .. code-block:: none

            Prof. John Smith
            John Smith
            Prof. Smith

        etc.

    """
    if always_title and not title:
        title = salutation_default_title(sex, assume_dr)
    return " ".join(filter(None, [title, forename, surname]))


def forename_surname(forename: Optional[str], surname: Optional[str]) -> str:
    """
    For use when reporting names.

    Args:
        forename: forename
        surname: surname

    Returns:
        str: a string of the style ``Forename Surname``

    """
    return " ".join(filter(None, [forename, surname]))


def salutation_default_title(sex: str = '', assume_dr: bool = False) -> str:
    """
    Returns a guess as to someone's title.

    Args:
        sex: ``"M"`` or ``"F"`` or other/unknown
        assume_dr: assume the person has the title "Dr"?

    Returns:
        a title

    """
    if assume_dr:
        return "Dr"
    if sex.upper() == 'M':
        return "Mr"
    if sex.upper() == 'F':
        return "Ms"
    # really stuck now
    # https://en.wikipedia.org/wiki/Gender_neutral_title
    return "Mx"


def salutation(title: Optional[str],
               forename: Optional[str],
               surname: Optional[str],
               sex: str = '',
               assume_dr: bool = False) -> str:
    """
    For salutations: "Dear ..."

    Args:
        title: title
        forename: forename
        surname: surname
        sex: ``"M"`` or ``"F"`` or other/unknown
        assume_dr: assume the person has the title "Dr"?

    Returns:
        a salutation like ``Prof. Smith``

    """
    if not title:
        title = salutation_default_title(sex, assume_dr)
    if title.lower() == "sir":  # frivolous!
        return " ".join([title, forename])
    return " ".join([title, surname])


# =============================================================================
# String parsing
# =============================================================================

def get_initial_surname_tuple_from_string(s: str) -> Tuple[str, str]:
    """
    Parses a name-like string into plausible parts. Try:

    .. code-block:: python

        get_initial_surname_tuple_from_string("AJ VAN DEN BERG")
        get_initial_surname_tuple_from_string("VAN DEN BERG AJ")
        get_initial_surname_tuple_from_string("J Smith")
        get_initial_surname_tuple_from_string("J. Smith")
        get_initial_surname_tuple_from_string("Smith J.")
        get_initial_surname_tuple_from_string("Smith JKC")
        get_initial_surname_tuple_from_string("Dr Bob Smith")
        get_initial_surname_tuple_from_string("LINTON H C (PL)")

    Returns:
        tuple: ``initial, surname``
    """
    parts = s.split() if s else []
    nparts = len(parts)
    if nparts == 0:
        return "", ""
    elif "(" in s:
        # something v. odd like "Linton H C (PL)", for Linton Health Centre
        # partners or similar. We can't fix it, but...
        return "", parts[0]
    elif nparts == 1:
        # hmm... assume "Smith"
        return "", parts[0]
    elif nparts == 2:
        if len(parts[0]) < len(parts[1]):
            # probably "J Smith"
            return parts[0][0], parts[1]
        else:
            # probably "Smith JKC"
            return parts[1][0], parts[0]
    else:
        # Lots of parts.
        if parts[0].lower() == "dr":
            parts = parts[1:]
            nparts -= 1
        if len(parts[0]) < len(parts[-1]):
            # probably "AJ VAN DEN BERG"
            return parts[0][0], " ".join(parts[1:])
        else:
            # probably "VAN DEN BERG AJ"
            return parts[-1][0], " ".join(parts[:-1])
