#!/usr/bin/env python
# crate_anon/nlp_manager/nlp_definition.py

from typing import Generic, List

from crate_anon.nlp_manager.base_parser import NlpParser

from crate_anon.nlp_manager.gate_parser import Gate
from crate_anon.nlp_manager.parse_biochemistry import *
from crate_anon.nlp_manager.parse_cognitive import *
from crate_anon.nlp_manager.parse_haematology import *


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
    for subclass in cls.__subclasses__():
        all_subclasses.append(subclass)
        all_subclasses.extend(get_all_subclasses(subclass))
    return all_subclasses


# noinspection PyTypeChecker,PyCallingNonCallable
def make_processor(processor_type: str,
                   nlpdef: NlpDefinition,
                   section: str) -> NlpParser:
    possible_processors = get_all_subclasses(NlpParser)
    for cls in possible_processors:
        if processor_type.lower() == cls.__name__.lower():
            return cls(nlpdef, section)
    raise ValueError("Unknown NLP processor type: {}".format(processor_type))


# noinspection PyTypeChecker
def possible_processor_names():
    possible_processors = get_all_subclasses(NlpParser)
    return sorted(cls.__name__ for cls in possible_processors)


if __name__ == '__main__':
    print(possible_processor_names())
