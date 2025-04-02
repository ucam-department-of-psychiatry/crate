"""
crate_anon/nlp_manager/all_processors.py

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

**Factory functions to manage all NLP processor classes.**

"""

# =============================================================================
# Imports
# =============================================================================

from inspect import isabstract
from typing import Any, List, Optional, Set, Type

from cardinal_pythonlib.json.typing_helpers import (
    JsonArrayType,
    JsonObjectType,
)

from crate_anon.common.stringfunc import (
    get_docstring,
    make_twocol_table,
    trim_docstring,
)
from crate_anon.nlp_manager.base_nlp_parser import BaseNlpParser, TableMaker

# Mostly, here we are not concerned with importing a specific symbol, but the
# side effect on class inheritance (registering classes). So we can import an
# arbitrary class or constant:
from crate_anon.nlp_manager.nlp_definition import NlpDefinition
from crate_anon.nlp_manager.parse_gate import Gate
from crate_anon.nlp_manager.parse_medex import Medex
from crate_anon.nlp_manager.parse_biochemistry import (
    ALL_BIOCHEMISTRY_NLP_AND_VALIDATORS,
)
from crate_anon.nlp_manager.parse_clinical import (
    ALL_CLINICAL_NLP_AND_VALIDATORS,
)
from crate_anon.nlp_manager.parse_cognitive import (
    ALL_COGNITIVE_NLP_AND_VALIDATORS,
)
from crate_anon.nlp_manager.parse_haematology import (
    ALL_HAEMATOLOGY_NLP_AND_VALIDATORS,
)
from crate_anon.nlp_manager.parse_substance_misuse import (
    ALL_SUBSTANCE_MISUSE_NLP_AND_VALIDATORS,
)
from crate_anon.nlp_webserver.server_processor import ServerProcessor

ClassType = Type[object]


# noinspection PyUnusedLocal
def ignore(something: Any) -> None:
    pass


# To make warnings go away about imports being unused:
ignore(Gate)
ignore(Medex)
ignore(ALL_BIOCHEMISTRY_NLP_AND_VALIDATORS)
ignore(ALL_CLINICAL_NLP_AND_VALIDATORS)
ignore(ALL_COGNITIVE_NLP_AND_VALIDATORS)
ignore(ALL_HAEMATOLOGY_NLP_AND_VALIDATORS)
ignore(ALL_SUBSTANCE_MISUSE_NLP_AND_VALIDATORS)


# =============================================================================
# Factory functions
# =============================================================================


def get_all_subclasses(cls: ClassType) -> List[ClassType]:
    """
    Returns all non-abstract subclasses of ``cls``.

    Args:
        cls: class into which to recurse

    Returns:
        list of classes
    """
    # Type hinting, but not quite:
    #   https://stackoverflow.com/questions/35655257
    # Getting derived subclasses: https://stackoverflow.com/questions/3862310
    all_subclasses = []  # List[ClassType]
    # noinspection PyArgumentList
    for subclass in cls.__subclasses__():
        if not isabstract(subclass):
            all_subclasses.append(subclass)
        all_subclasses.extend(get_all_subclasses(subclass))  # recursive
    all_subclasses.sort(key=lambda c: c.__name__.lower())
    return all_subclasses


def all_local_parser_classes() -> List[Type[BaseNlpParser]]:
    """
    Return all classes that are non-abstract subclasses of
    :class:`crate_anon.nlp_manager.base_nlp_parser.BaseNlpParser`.

    ... but not test parsers.

    Checks that they all have unique names in lower case.
    """
    # noinspection PyTypeChecker
    classes = get_all_subclasses(
        BaseNlpParser
    )  # type: List[Type[BaseNlpParser]]
    classes = [cls for cls in classes if not cls.is_test_nlp_parser]

    lower_case_short_names = set()  # type: Set[str]
    lower_case_full_names = set()  # type: Set[str]
    for cls in classes:
        lc_sname = cls.classname().lower()
        if lc_sname in lower_case_short_names:
            raise ValueError(
                f"Trying to add NLP processor {lc_sname!r} but a processor "
                f"with the same lower-case name already exists"
            )
        lower_case_short_names.add(lc_sname)

        lc_fname = cls.fully_qualified_classname().lower()
        if lc_fname in lower_case_full_names:
            raise ValueError(
                f"Trying to add NLP processor {lc_fname!r} but a processor "
                f"with the same lower-case fully-qualified name already exists"
            )
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
        if (
            cls.classname().lower() == classname
            or cls.fully_qualified_classname().lower() == classname
        ):
            return cls
    return None


def make_nlp_parser(
    classname: str, nlpdef: NlpDefinition, cfg_processor_name: str
) -> TableMaker:
    """
    Fetch an NLP processor instance by name.

    Args:
        classname:
            the name of the processor
        nlpdef:
            a :class:`crate_anon.nlp_manager.nlp_definition.NlpDefinition`
        cfg_processor_name:
            the name (suffix) of a CRATE NLP config file section, passed to the
            NLP parser as we create it (for it to get extra config information
            if it wishes)

    Returns:
        an NLP processor instance whose class name matches (in case-insensitive
        fashion) ``classname``.

    Raises:
        :exc:`ValueError` if no such processor is found

    """
    cls = get_nlp_parser_class(classname)
    if cls:
        return cls(nlpdef=nlpdef, cfg_processor_name=cfg_processor_name)
    raise ValueError(f"Unknown NLP processor type: {classname!r}")


def possible_local_processor_names() -> List[str]:
    """
    Returns all NLP processor names that can run locally.
    """
    return [cls.classname() for cls in all_local_parser_classes()]


def all_nlp_processor_classes() -> List[Type[TableMaker]]:
    """
    Returns all NLP processor classes.
    """
    return all_tablemaker_classes()


def possible_processor_names_including_cloud() -> List[str]:
    """
    Returns all NLP processor names.
    """
    return [cls.classname() for cls in all_nlp_processor_classes()]


def all_local_processor_classes_without_external_tools() -> (
    List[Type[BaseNlpParser]]
):
    """
    Returns all NLP processor classes that don't rely on external tools.
    """
    return [
        cls for cls in all_local_parser_classes() if not cls.uses_external_tool
    ]


def possible_local_processor_names_without_external_tools() -> List[str]:
    """
    Returns all NLP processor names for processors that don't rely on external
    tools.
    """
    return [
        cls.classname()
        for cls in all_local_processor_classes_without_external_tools()
    ]


def possible_processor_table() -> str:
    """
    Returns a pretty-formatted string containing a table of all NLP processors
    and their description (from their docstring).
    """
    colnames = ["NLP name", "Description"]
    rows = []  # type: List[List[str]]
    for cls in all_tablemaker_classes():
        name = cls.classname()
        description = get_docstring(cls)
        rows.append([name, trim_docstring(description)])
    return make_twocol_table(colnames, rows, rewrap_right_col=False)


def all_crate_python_processors_nlprp_processor_info(
    sql_dialect: str = None, extra_dict: JsonObjectType = None
) -> JsonArrayType:
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
    for cls in all_local_processor_classes_without_external_tools():
        instance = cls(None, None)
        proc_info = instance.nlprp_processor_info(sql_dialect=sql_dialect)
        if extra_dict:
            proc_info.update(extra_dict)
        allprocs.append(proc_info)
    return allprocs


def register_all_crate_python_processors_with_serverprocessor(
    set_parser: bool = True,
) -> None:
    """
    Somewhat ugly. Register all CRATE Python NLP processors with the
    ServerProcessor class.

    See also crate_anon/nlp_webserver/procs.py, for a similar thing from JSON.

    Args:
        set_parser:
            Set up a "free-floating" parser too?
    """
    for cls in all_local_processor_classes_without_external_tools():
        instance = cls(None, None)
        _proc = instance.nlprp_processor_info()
        _x = ServerProcessor.from_nlprp_json_dict(_proc)
        # ... registers with the ServerProcessor class
        # Doing this here saves time per request
        if set_parser:
            _x.set_parser()
