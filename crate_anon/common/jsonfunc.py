#!/usr/bin/env python
# crate_anon/crateweb/research/models.py

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

See notes_on_pickle_json.txt

"""

import json
import logging
from typing import Any, Callable, Dict

from django.core.exceptions import ValidationError
from django.db.models import TextField

log = logging.getLogger(__name__)

TYPE_LABEL = '__type__'

DEBUG = False


# =============================================================================
# Convert Python class instances to/from dictionaries in various ways
# =============================================================================

def simple_to_dict(obj: Any) -> Dict:
    """
    For use when object attributes (found in obj.__dict__) should be mapped
    directly to the serialized JSON dictionary. Typically used for classes
    like:

class SimpleClass(object):
    def __init__(self, a, b, c):
        self.a = a
        self.b = b
        self.c = c

    Here, after

        x = SimpleClass(a=1, b=2, c=3)

    we will find that

        x.__dict__ == {'a': 1, 'b': 2, 'c': 3}

    and that dictionary is a reasonable thing to serialize to JSON.
    """
    return obj.__dict__


def simple_from_dict(d: Dict, cls: Any) -> Any:
    """
    Converse of simple_to_dict().
    Given that JSON dictionary, we will end up re-instantiating the class with

        d = {'a': 1, 'b': 2, 'c': 3}
        new_x = SimpleClass(**d)
    """
    return cls(**d)


def strip_underscore_to_dict(obj: Any) -> Dict:
    """
    This is appropriate when a class uses a '_' prefix for all its __init__
    parameters, like this:

class UnderscoreClass(object):
    def __init__(self, a, b, c):
        self._a = a
        self._b = b
        self._c = c

    Here, after

        y = UnderscoreClass(a=1, b=2, c=3)

    we will find that

        y.__dict__ == {'_a': 1, '_b': 2, '_c': 3}

    but we would like to serialize the parameters we can pass back to __init__,
    like this:

        {'a': 1, 'b': 2, 'c': 3}
    """
    d = {}
    for k, v in obj.__dict__.items():
        if k.startswith('_'):
            k = k[1:]
            if k in d:
                raise ValueError(
                    "Attribute conflict: _{k} and {k}".format(k=k))
        d[k] = v
    return d


# =============================================================================
# Describe how a Python class should be serialized to/from JSON
# =============================================================================

class JsonDescriptor(object):
    def __init__(self,
                 obj_to_dict_fn: Callable[[Any], Dict],
                 dict_to_obj_fn: Callable[[Dict, Any], Any],
                 cls: Any) -> None:
        self._obj_to_dict_fn = obj_to_dict_fn
        self._dict_to_obj_fn = dict_to_obj_fn
        self._cls = cls

    def to_dict(self, obj: Any) -> Dict:
        return self._obj_to_dict_fn(obj)

    def to_obj(self, d: Dict) -> Any:
        return self._dict_to_obj_fn(d, self._cls)


# =============================================================================
# Maintain a record of how several classes should be serialized
# =============================================================================

TYPE_MAP = {}  # type: Dict[str, JsonDescriptor]


def register_class_for_json(
        cls: Any,
        method: str = '',
        obj_to_dict_fn: Callable[[Any], Dict] = None,
        dict_to_obj_fn: Callable[[Dict, Any], Any] = None) -> None:
    """
    Registers the class cls for JSON serialization.
    - If both obj_to_dict_fn and dict_to_obj_fn are registered, the framework
      uses these to convert instances of the class to/from Python dictionaries,
      which are in turn serialized to JSON.
    - Otherwise:

        if method == 'simple':
            # ... uses simple_to_dict and simple_from_dict (q.v.)

        if method == 'strip_underscore':
            # ... uses strip_underscore_to_dict and simple_from_dict (q.v.)
    """
    typename = cls.__name__
    if obj_to_dict_fn and dict_to_obj_fn:
        descriptor = JsonDescriptor(obj_to_dict_fn=obj_to_dict_fn,
                                    dict_to_obj_fn=dict_to_obj_fn,
                                    cls=cls)
    elif method == 'simple':
        descriptor = JsonDescriptor(obj_to_dict_fn=simple_to_dict,
                                    dict_to_obj_fn=simple_from_dict,
                                    cls=cls)
    elif method == 'strip_underscore':
        descriptor = JsonDescriptor(obj_to_dict_fn=strip_underscore_to_dict,
                                    dict_to_obj_fn=simple_from_dict,
                                    cls=cls)
    else:
        raise ValueError("Unknown method and functions not fully specified")
    global TYPE_MAP
    TYPE_MAP[typename] = descriptor


def register_for_json(
        method: str = '',
        obj_to_dict_fn: Callable[[Any], Dict] = None,
        dict_to_obj_fn: Callable[[Dict, Any], Any] = None) -> Any:
    """
    Class decorator to register classes with our JSON system.

    - If method is 'provides_to_init_dict', the class provides a function
        def to_init_dict(self) -> Dict
      that yields a dictionary suitable for passing to its __init__() function.

    - Otherwise, the method argument is as for register_class_for_json().
    """
    def register_json_class(cls):
        if method == 'provides_to_init_dict':
            register_class_for_json(cls,
                                    obj_to_dict_fn=cls.to_init_dict,
                                    dict_to_obj_fn=simple_from_dict)
        else:
            register_class_for_json(cls, method=method,
                                    obj_to_dict_fn=obj_to_dict_fn,
                                    dict_to_obj_fn=dict_to_obj_fn)
        return cls

    return register_json_class


# =============================================================================
# Hooks to implement the JSON encoding/decoding
# =============================================================================

class CrateJsonEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        typename = type(obj).__name__
        if typename in TYPE_MAP:
            descriptor = TYPE_MAP[typename]
            d = descriptor.to_dict(obj)
            if TYPE_LABEL in d:
                raise ValueError("Class already has attribute: " + TYPE_LABEL)
            d[TYPE_LABEL] = typename
            if DEBUG:
                log.debug("Serializing {} -> {}".format(repr(obj), repr(d)))
            return d
        # Otherwise, nothing that we know about:
        return super().default(obj)


def crate_json_decoder_hook(d: Dict) -> Any:
    if TYPE_LABEL in d:
        typename = d.get(TYPE_LABEL)
        if typename in TYPE_MAP:
            if DEBUG:
                log.debug("Deserializing: {}".format(repr(d)))
            d.pop(TYPE_LABEL)
            descriptor = TYPE_MAP[typename]
            obj = descriptor.to_obj(d)
            if DEBUG:
                log.debug("... to: {}".format(repr(obj)))
            return obj
    return d


# =============================================================================
# Functions for end users
# =============================================================================

def json_encode(obj: Any) -> str:
    return json.dumps(obj, cls=CrateJsonEncoder)


def json_decode(s: str) -> Any:
    try:
        return json.JSONDecoder(object_hook=crate_json_decoder_hook).decode(s)
    except json.JSONDecodeError:
        log.warning("Failed to decode JSON (returning None): {}".format(
            repr(s)))
        return None


# =============================================================================
# Django field
# - To use a class with this, the class must be registered with
#   register_class_for_json() above. Register the class immediately after
#   defining it.
# =============================================================================

class CrateJsonField(TextField):
    # https://docs.djangoproject.com/en/1.10/howto/custom-model-fields/
    description = "Python objects serialized into JSON"

    # No need to implement __init__()
    # No need to implement deconstruct()
    # No need to implement db_type()

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def from_db_value(self, value, expression, connection, context):
        """
        "Called in all circumstances when the data is loaded from the
        database, including in aggregates and values() calls."
        """
        if value is None:
            return value
        return json_decode(value)

    def to_python(self, value):
        """
        "Called during deserialization and during the clean() method used
        from forms.... [s]hould deal gracefully with... (*) an instance of
        the correct type; (*) a string; (*) None (if the field allows
        null=True)."

        "For to_python(), if anything goes wrong during value conversion, you
        should raise a ValidationError exception."
        """
        if value is None:
            return value
        if not isinstance(value, str):
            return value
        try:
            return json_decode(value)
        except Exception as err:
            raise ValidationError(repr(err))

    def get_prep_value(self, value):
        """
        Converse of to_python(). Converts Python objects back to query
        values.
        """
        return json_encode(value)
