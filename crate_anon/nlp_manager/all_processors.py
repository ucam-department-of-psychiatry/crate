#!/usr/bin/env python
# crate_anon/nlp_manager/nlp_definition.py

"""
===============================================================================
    Copyright © 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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

# import logging
from operator import attrgetter
# noinspection PyUnresolvedReferences
from typing import Generic, List

import prettytable

# noinspection PyUnresolvedReferences
from crate_anon.nlp_manager.base_nlp_parser import BaseNlpParser

from crate_anon.nlp_manager.parse_gate import Gate
from crate_anon.nlp_manager.parse_medex import Medex
from crate_anon.nlp_manager.parse_biochemistry import *
from crate_anon.nlp_manager.parse_clinical import *
from crate_anon.nlp_manager.parse_cognitive import *
from crate_anon.nlp_manager.parse_haematology import *

# log = logging.getLogger(__name__)


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


# noinspection PyUnresolvedReferences
def get_all_subclasses(cls: Generic) -> List[Generic]:
    # Type hinting, but not quite:
    #   http://stackoverflow.com/questions/35655257
    # Getting derived subclasses: http://stackoverflow.com/questions/3862310
    all_subclasses = []
    for subclass in cls.__subclasses__():
        all_subclasses.append(subclass)
        all_subclasses.extend(get_all_subclasses(subclass))
    all_subclasses.sort(key=attrgetter('__name__'))
    lower_case_names = set()
    for cls in all_subclasses:
        lc_name = cls.__name__.lower()
        if lc_name in lower_case_names:
            raise ValueError(
                "Trying to add NLP processor {} but a processor with the same "
                "lower-case name already exists".format(cls.__name__))
        lower_case_names.add(lc_name)
    return all_subclasses


# noinspection PyTypeChecker
def all_parser_classes() -> List[Generic]:
    return get_all_subclasses(BaseNlpParser)


# noinspection PyTypeChecker,PyCallingNonCallable
def make_processor(processor_type: str,
                   nlpdef: NlpDefinition,
                   section: str) -> BaseNlpParser:
    for cls in all_parser_classes():
        if processor_type.lower() == cls.__name__.lower():
            return cls(nlpdef, section)
        # else:
        #     log.debug("mismatch: {} != {}".format(processor_type,
        #                                           cls.__name__))
    raise ValueError("Unknown NLP processor type: {}".format(processor_type))


# noinspection PyTypeChecker
def possible_processor_names() -> List[str]:
    return [cls.__name__ for cls in all_parser_classes()]


# noinspection PyTypeChecker
def possible_processor_table() -> str:
    pt = prettytable.PrettyTable(
        ["NLP name", "Description"],
        header=True,
        border=True,
    )
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
    for cls in all_parser_classes():
        if cls.__name__ in ['Gate',
                            'Medex',
                            'NumericalResultParser',
                            'SimpleNumericalResultParser',
                            'NumeratorOutOfDenominatorParser',
                            'ValidatorBase',
                            'WbcBase']:
            continue
        # if cls.__name__.endswith('Validator'):
        #     continue
        print("Testing parser class: {}".format(cls.__name__))
        # noinspection PyCallingNonCallable
        instance = cls(None, None)
        print("... instantiated OK")
        instance.test(verbose=verbose)


if __name__ == '__main__':
    test_all_processors()
