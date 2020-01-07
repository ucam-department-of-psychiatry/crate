#!/usr/bin/env python

"""
crate_anon/nlp_manager/all_processors.py

===============================================================================

    Copyright (C) 2015-2020 Rudolf Cardinal (rudolf@pobox.com).

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

from inspect import isabstract
# noinspection PyUnresolvedReferences
import logging
# noinspection PyUnresolvedReferences
from typing import Any, List, Set, Type

from cardinal_pythonlib.json.typing_helpers import (
    JsonArrayType,
    JsonObjectType,
)
# noinspection PyUnresolvedReferences
from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
import prettytable

# noinspection PyUnresolvedReferences
from crate_anon.nlp_manager.base_nlp_parser import BaseNlpParser, TableMaker
from crate_anon.nlp_manager.parse_gate import Gate
from crate_anon.nlp_manager.parse_medex import Medex
from crate_anon.nlp_manager.parse_biochemistry import *
from crate_anon.nlp_manager.parse_clinical import *
from crate_anon.nlp_manager.parse_cognitive import *
from crate_anon.nlp_manager.parse_haematology import *
# noinspection PyUnresolvedReferences
from crate_anon.nlp_manager.regex_parser import NumericalResultParser
from crate_anon.nlprp.constants import (
    SqlDialects,
)

log = logging.getLogger(__name__)
ClassType = Type[object]


# noinspection PyUnusedLocal
def ignore(something: Any) -> None:
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
    Returns all non-abstract subclasses of ``cls``.

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
        if not isabstract(subclass):
            all_subclasses.append(subclass)
        # else:
        #     log.critical(f"Skipping abstract class: {subclass.__name__}")
        all_subclasses.extend(get_all_subclasses(subclass))  # recursive
    all_subclasses.sort(key=lambda c: c.__name__.lower())
    return all_subclasses


def all_parser_classes() -> List[Type[BaseNlpParser]]:
    """
    Return all classes that are non-abstract subclasses of
    :class:`crate_anon.nlp_manager.base_nlp_parser.BaseNlpParser`.

    Checks that they all have unique names in lower case.
    """
    # noinspection PyTypeChecker
    classes = get_all_subclasses(BaseNlpParser)  # type: List[Type[BaseNlpParser]]  # noqa
    lower_case_short_names = set()  # type: Set[str]
    lower_case_full_names = set()  # type: Set[str]
    for cls in classes:
        lc_sname = cls.classname().lower()
        if lc_sname in lower_case_short_names:
            raise ValueError(
                f"Trying to add NLP processor {lc_sname!r} but a processor "
                f"with the same lower-case name already exists")
        lower_case_short_names.add(lc_sname)

        lc_fname = cls.fully_qualified_name().lower()
        if lc_fname in lower_case_full_names:
            raise ValueError(
                f"Trying to add NLP processor {lc_fname!r} but a processor "
                f"with the same lower-case fully-qualified name already exists")  # noqa
        lower_case_full_names.add(lc_fname)
    return classes


def all_tablemaker_classes() -> List[Type[TableMaker]]:
    """
    Return all classes that are non-abstract subclasses of
    :class:`crate_anon.nlp_manager.base_nlp_parser.TableMaker`.
    """
    # noinspection PyTypeChecker
    return get_all_subclasses(TableMaker)


def get_nlp_parser_class(classname: str) -> Optional[Type[TableMaker]]:
    """
    Fetch an NLP parser class (not instance) by name. The match may be on
    either the class's short name or the fully-qualified name, and is
    case-insensitive.

    Args:
        classname: the name of the NLP parser class

    Returns:
        the class, or ``None`` if there isn't one with that name

    """
    classname = classname.lower()
    classes = all_tablemaker_classes()
    for cls in classes:
        if (cls.classname().lower() == classname or
                cls.fully_qualified_name().lower() == classname):
            return cls
    return None


def make_nlp_parser(classname: str,
                    nlpdef: NlpDefinition,
                    cfgsection: str) -> TableMaker:
    """
    Fetch an NLP processor instance by name.

    Args:
        classname:
            the name of the processor
        nlpdef:
            a :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
        cfgsection:
            the name of a CRATE NLP config file section, passed to the NLP
            parser as we create it (for it to get extra config information if
            it wishes)

    Returns:
        an NLP processor instance whose class name matches (in case-insensitive
        fashion) ``classname``.

    Raises:
        :exc:`ValueError` if no such processor is found

    """
    cls = get_nlp_parser_class(classname)
    if cls:
        return cls(nlpdef=nlpdef, cfgsection=cfgsection)
    raise ValueError(f"Unknown NLP processor type: {classname!r}")


def make_nlp_parser_unconfigured(classname: str,
                                 raise_if_absent: bool = True) \
        -> Optional[TableMaker]:
    """
    Get a debugging (unconfigured) instance of an NLP parser.

    Args:
        classname: the name of the NLP parser class
        raise_if_absent: raise ``ValueError`` if there is no match?

    Returns:
        the class, or ``None`` if there isn't one with that name

    """
    cls = get_nlp_parser_class(classname)
    if cls:
        return cls(nlpdef=None, cfgsection=None)
    if raise_if_absent:
        raise ValueError(f"Unknown NLP processor type: {classname!r}")
    return None


def possible_processor_names() -> List[str]:
    """
    Returns all NLP processor names.
    """
    return [cls.classname() for cls in all_parser_classes()]


def possible_processor_table() -> str:
    """
    Returns a pretty-formatted string containing a table of all NLP processors
    and their description (from their docstring).
    """
    pt = prettytable.PrettyTable(["NLP name", "Description"],
                                 header=True,
                                 border=True)
    pt.align = 'l'
    pt.valign = 't'
    pt.max_width = 80
    for cls in all_parser_classes():
        name = cls.classname()
        description = getattr(cls, '__doc__', "") or ""
        ptrow = [name, description]
        pt.add_row(ptrow)
    return pt.get_string()


def test_all_processors(verbose: bool = False,
                        skip_validators: bool = False) -> None:
    """
    Self-tests all NLP processors.

    Args:
        verbose: be verbose?
        skip_validators: skip validator classes?
    """
    for cls in all_parser_classes():
        if skip_validators and cls.classname().endswith('Validator'):
            continue
        log.info("Testing parser class: {}".format(cls.classname()))
        instance = cls(None, None)
        log.info("... instantiated OK")
        schema_json = instance.nlprp_processor_info_json(
            indent=4, sort_keys=True, sql_dialect=SqlDialects.MYSQL)
        log.info(f"NLPRP processor information:\n{schema_json}")
        instance.test(verbose=verbose)
    log.info("Tests completed successfully.")


def all_crate_python_processors_nlprp_processor_info(
        sql_dialect: str = None,
        extra_dict: JsonObjectType = None) -> JsonArrayType:
    """
    Returns NLPRP processor information for all CRATE Python NLP processors.

    Args:
        sql_dialect:
            preferred SQL dialect for response, or ``None`` for a default
        extra_dict:
            extra dictionary to merge in for each processor

    Returns:
        list: list of processor information dictionaries
    """
    allprocs = []  # type: JsonArrayType
    for cls in all_parser_classes():
        instance = cls(None, None)
        proc_info = instance.nlprp_processor_info(sql_dialect=sql_dialect)
        if extra_dict:
            proc_info.update(extra_dict)
        allprocs.append(proc_info)
    return allprocs


if __name__ == '__main__':
    main_only_quicksetup_rootlogger(level=logging.DEBUG)
    test_all_processors()
