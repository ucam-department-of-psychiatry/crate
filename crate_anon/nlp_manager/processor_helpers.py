"""
crate_anon/nlp_manager/processor_helpers.py

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

**Helper functions to manage all NLP processor classes.**

These use a delayed import, sorting out some circular import problems.

"""

# =============================================================================
# Imports
# =============================================================================

from typing import Optional

from crate_anon.nlp_manager.base_nlp_parser import TableMaker


# =============================================================================
# Helper functions
# =============================================================================


def make_nlp_parser_unconfigured(
    classname: str, raise_if_absent: bool = True
) -> Optional[TableMaker]:
    """
    Get a debugging (unconfigured) instance of an NLP parser.

    Args:
        classname: the name of the NLP parser class
        raise_if_absent: raise ``ValueError`` if there is no match?

    Returns:
        the class, or ``None`` if there isn't one with that name

    """
    from crate_anon.nlp_manager.all_processors import (
        get_nlp_parser_class,
    )  # delayed import

    cls = get_nlp_parser_class(classname)
    if cls:
        return cls(nlpdef=None, cfg_processor_name=None)
    if raise_if_absent:
        raise ValueError(f"Unknown NLP processor type: {classname!r}")
    return None
