#!/usr/bin/env python

"""
crate_anon/nlp_manager/all_processors.py

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

**Factory functions to manage all NLP processor classes.**

"""

# noinspection PyUnresolvedReferences
import logging
# noinspection PyUnresolvedReferences
from typing import List, Type

import prettytable

# noinspection PyUnresolvedReferences
from crate_anon.nlp_manager.base_nlp_parser import BaseNlpParser
from crate_anon.nlp_manager.parse_gate import Gate
from crate_anon.nlp_manager.parse_medex import Medex
from crate_anon.nlp_manager.parse_biochemistry import *
from crate_anon.nlp_manager.parse_clinical import *
from crate_anon.nlp_manager.parse_cognitive import *
from crate_anon.nlp_manager.parse_haematology import *
# noinspection PyUnresolvedReferences
from crate_anon.nlp_manager.regex_parser import NumericalResultParser

log = logging.getLogger(__name__)
ClassType = Type[object]


# noinspection PyUnusedLocal
def ignore(something):
    pass


# To make warnings go away about imports being unused:

# gate_parser
ignore(Gate)

# medex_parser
ignore(Medex)

# parse_biochemistry
ignore(Crp)

# parse_clinical
ignore(Bmi)

# parse_cognitive
ignore(Mmse)

# parse_haematology
ignore(Wbc)
ignore(Neutrophils)
ignore(Lymphocytes)
ignore(Monocytes)
ignore(Basophils)
ignore(Eosinophils)


# T = TypeVar('T', bound=NlpParser)


def get_all_subclasses(cls: ClassType) -> List[ClassType]:
    """
    Returns all subclasses of ``cls``. Checks that they all have unique names
    in lower case.

    Args:
        cls: class into which to recurse

    Returns:
        list of classes

    """
    # Type hinting, but not quite:
    #   http://stackoverflow.com/questions/35655257
    # Getting derived subclasses: http://stackoverflow.com/questions/3862310
    all_subclasses = []  # List[ClassType]
    # noinspection PyArgumentList
    for subclass in cls.__subclasses__():
        all_subclasses.append(subclass)
        all_subclasses.extend(get_all_subclasses(subclass))  # recursive
    all_subclasses.sort(key=lambda c: c.__name__.lower())
    lower_case_names = set()
    for cls in all_subclasses:
        lc_name = cls.__name__.lower()
        if lc_name in lower_case_names:
            raise ValueError(
                "Trying to add NLP processor {} but a processor with the same "
                "lower-case name already exists".format(cls.__name__))
        lower_case_names.add(lc_name)
    return all_subclasses


def all_parser_classes() -> List[Type[BaseNlpParser]]:
    """
    Return all classes that are subclasses of
    :class:`crate_anon.nlp_manager.base_nlp_parser.BaseNlpParser`.
    """
    # noinspection PyTypeChecker
    return get_all_subclasses(BaseNlpParser)  # type: List[Type[BaseNlpParser]]


def make_processor(processor_type: str,
                   nlpdef: NlpDefinition,
                   section: str) -> BaseNlpParser:
    """
    Fetch an NLP processor instance by name.

    Args:
        processor_type: the name of the processor
        nlpdef: a :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
        section: the name of a CRATE NLP config file section, passed to the NLP
            parser as we create it (for it to get extra config information if
            it wishes)

    Returns:
        an NLP processor instance whose class name matches (in case-insensitive
        fashion) ``processor_type``.

    Raises:
        :exc:`ValueError` if no such processor is found

    """
    for cls in all_parser_classes():
        if processor_type.lower() == cls.__name__.lower():
            return cls(nlpdef, section)
        # else:
        #     log.debug("mismatch: {} != {}".format(processor_type,
        #                                           cls.__name__))
    raise ValueError("Unknown NLP processor type: {}".format(processor_type))


def get_nlp_parser_class(classname: str):  # -> Optional[Type[BaseNlpParser]]:
    """
    Fetch an NLP parser class (not instance) by name.

    Args:
        classname: the name of the NLP parser class

    Returns:
        the class, or ``None`` if there isn't one with that name

    """
    classes = all_parser_classes()
    for cls in classes:
        if cls.__name__ == classname:
            return cls
    return None


def get_nlp_parser_debug_instance(classname: str):  # -> Optional[BaseNlpParser]:  # noqa
    """
    Get a debugging (unconfigured) instance of an NLP parser.

    Args:
        classname: the name of the NLP parser class

    Returns:
        the class, or ``None`` if there isn't one with that name

    """
    cls = get_nlp_parser_class(classname)
    if cls:
        return cls(None, None)
    return None


def possible_processor_names() -> List[str]:
    """
    Returns all NLP processor names.
    """
    return [cls.__name__ for cls in all_parser_classes()]


def possible_processor_table() -> str:
    """
    Returns a pretty-formatted string containing a table of all NLP processors
    and their description.
    """
    pt = prettytable.PrettyTable(["NLP name", "Description"],
                                 header=True,
                                 border=True)
    pt.align = 'l'
    pt.valign = 't'
    pt.max_width = 80
    for cls in all_parser_classes():
        name = cls.__name__
        description = getattr(cls, '__doc__', "") or ""
        ptrow = [name, description]
        pt.add_row(ptrow)
    return pt.get_string()


def test_all_processors(verbose: bool = False) -> None:
    """
    Self-tests all NLP processors.

    Args:
        verbose: be verbose?
    """
    for cls in all_parser_classes():
        if cls.__name__ in ('Gate',
                            'Medex',
                            'NumericalResultParser',
                            'SimpleNumericalResultParser',
                            'NumeratorOutOfDenominatorParser',
                            'ValidatorBase',
                            'WbcBase'):
            continue
        # if cls.__name__.endswith('Validator'):
        #     continue
        print("Testing parser class: {}".format(cls.__name__))
        instance = cls(None, None)
        print("... instantiated OK")
        instance.test(verbose=verbose)


if __name__ == '__main__':
    test_all_processors()
