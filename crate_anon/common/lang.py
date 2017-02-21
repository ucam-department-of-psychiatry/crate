#!/usr/bin/env python
# crate_anon/common/lang.py

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
from typing import Any, Dict, Iterable, List, Optional, Tuple


log = logging.getLogger(__name__)


def get_case_insensitive_dict_key(d: Dict, k: str) -> Optional[str]:
    for key in d.keys():
        if k.lower() == key.lower():
            return key
    return None


def rename_kwarg(kwargs: Dict[str, Any], old: str, new: str) -> None:
    kwargs[new] = kwargs.pop(old)


def unique_list(seq: Iterable[Any]) -> List[Any]:
    # http://stackoverflow.com/questions/480214/how-do-you-remove-duplicates-from-a-list-in-whilst-preserving-order  # noqa
    seen = set()
    seen_add = seen.add
    return [x for x in seq if not (x in seen or seen_add(x))]


def add_info_to_exception(err: Exception, info: Dict) -> None:
    # http://stackoverflow.com/questions/9157210/how-do-i-raise-the-same-exception-with-a-custom-message-in-python  # noqa
    if not err.args:
        err.args = ('', )
    err.args += (info, )


def recover_info_from_exception(err: Exception) -> Dict:
    if len(err.args) < 1:
        return {}
    info = err.args[-1]
    if not isinstance(info, dict):
        return {}
    return info


# =============================================================================
# __repr__ aids
# =============================================================================
# The repr() function often attempts to return something suitable for eval();
# failing that, it usually shows an address.
# https://docs.python.org/3/library/functions.html#repr

def _repr_result(obj: Any, elements: List[str],
                 with_addr: bool = False) -> str:
    if with_addr:
        return "<{qualname}({elements}) at {addr}>".format(
            qualname=obj.__class__.__qualname__,
            elements=", ".join(elements),
            addr=hex(id(obj)),
        )
    else:
        return "{qualname}({elements})".format(
            qualname=obj.__class__.__qualname__,
            elements=", ".join(elements),
        )


def auto_repr(obj: Any, with_addr: bool = False) -> str:
    """
    Convenience function for repr().
    Works its way through the object's __dict__ and reports accordingly.
    """
    elements = ["{}={}".format(k, repr(v)) for k, v in obj.__dict__.items()]
    return _repr_result(obj, elements, with_addr=with_addr)


def simple_repr(obj: Any, attrnames: List[str],
                with_addr: bool = False) -> str:
    """
    Convenience function for repr().
    Works its way through a list of attribute names, and creates a repr()
    assuming that parameters to the constructor have the same names.
    """
    elements = ["{}={}".format(name, repr(getattr(obj, name)))
                for name in attrnames]
    return _repr_result(obj, elements, with_addr=with_addr)


def mapped_repr(obj: Any, attributes: List[Tuple[str, str]],
                with_addr: bool = False) -> str:
    """
    Convenience function for repr().
    Takes a list of tuples: (attr_name, init_param_name).
    """
    elements = ["{}={}".format(init_param_name, repr(getattr(obj, attr_name)))
                for attr_name, init_param_name in attributes]
    return _repr_result(obj, elements, with_addr=with_addr)


def mapped_repr_stripping_underscores(obj: Any, attrnames: List[str],
                                      with_addr: bool = False) -> str:
    """
    Convenience function for repr().
    Here, you pass a list of internal attributes, and it assumes that the
    __init__() parameter names have the leading underscore dropped.
    """
    attributes = []
    for attr_name in attrnames:
        if attr_name.startswith('_'):
            init_param_name = attr_name[1:]
        else:
            init_param_name = attr_name
        attributes.append((attr_name, init_param_name))
    return mapped_repr(obj, attributes, with_addr=with_addr)
