#!/usr/bin/env python
# crate_anon/nlp_manager/nlp_definition.py

import logging
from operator import attrgetter
from typing import Generic, List

import prettytable

from crate_anon.nlp_manager.base_nlp_parser import BaseNlpParser
from crate_anon.nlp_manager.regex_parser import ValidatorBase

from crate_anon.nlp_manager.gate_parser import Gate
from crate_anon.nlp_manager.medex_parser import Medex
from crate_anon.nlp_manager.parse_biochemistry import *
from crate_anon.nlp_manager.parse_cognitive import *
from crate_anon.nlp_manager.parse_haematology import *

log = logging.getLogger(__name__)


# noinspection PyUnusedLocal
def ignore(something):
    pass


# To make warnings go away about imports being unused:
ignore(Gate)

ignore(Crp)

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
    lower_case_names = set()
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


# noinspection PyTypeChecker,PyCallingNonCallable
def make_processor(processor_type: str,
                   nlpdef: NlpDefinition,
                   section: str) -> BaseNlpParser:
    possible_processors = get_all_subclasses(BaseNlpParser)
    for cls in possible_processors:
        if processor_type.lower() == cls.__name__.lower():
            return cls(nlpdef, section)
        # else:
        #     log.debug("mismatch: {} != {}".format(processor_type,
        #                                           cls.__name__))
    raise ValueError("Unknown NLP processor type: {}".format(processor_type))


# noinspection PyTypeChecker
def possible_processor_names() -> List[str]:
    possible_processors = get_all_subclasses(BaseNlpParser)
    return [cls.__name__ for cls in possible_processors]


# noinspection PyTypeChecker
def possible_processor_table() -> str:
    possible_processors = get_all_subclasses(BaseNlpParser)
    pt = prettytable.PrettyTable(
        ["NLP name", "Description"],
        header=True,
        border=True,
    )
    pt.align = 'l'
    pt.valign = 't'
    pt.max_width = 80
    for cls in possible_processors:
        name = cls.__name__
        description = getattr(cls, '__doc__', "") or ""
        ptrow = [name, description]
        pt.add_row(ptrow)
    return pt.get_string()


if __name__ == '__main__':
    print(possible_processor_table())
