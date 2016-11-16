#!/usr/bin/env python
# crate_anon/nlp_manager/output_user_config.py

import ast
from typing import List

from cardinal_pythonlib.rnc_db import (
    ensure_valid_field_name,
    ensure_valid_table_name,
    is_sqltype_valid
)
from cardinal_pythonlib.rnc_lang import chunks
from sqlalchemy import Column, Index

from crate_anon.common.extendedconfigparser import ExtendedConfigParser
from crate_anon.common.sqla import get_sqla_coltype_from_dialect_str
from crate_anon.nlp_manager.input_field_config import InputFieldConfig


# =============================================================================
# OutputUserConfig
# =============================================================================

class OutputUserConfig(object):
    """
    Class defining configuration for the output of a given GATE app.
    """

    def __init__(self, parser: ExtendedConfigParser, section: str) -> None:
        """
        Read config from a configparser section.
        """
        def opt_str(option: str, required: bool = False) -> str:
            return parser.get_str(section, option, required=required)

        def opt_strlist(option: str,
                        required: bool = False,
                        lower: bool = True,
                        as_words: bool = True) -> List[str]:
            return parser.get_str_list(section, option, required=required,
                                       lower=lower, as_words=as_words)

        if not parser.has_section(section):
            raise ValueError("config missing section: " + section)

        self._desttable = opt_str('desttable', required=True)
        ensure_valid_table_name(self._desttable)

        self._destfields = []
        self._dest_datatypes = []
        dest_fields_datatypes = opt_strlist('destfields', required=True)
        # log.critical(dest_fields_datatypes)
        for c in chunks(dest_fields_datatypes, 2):
            field = c[0]
            datatype = c[1].upper()
            ensure_valid_field_name(field)
            if not is_sqltype_valid(datatype):
                raise Exception(
                    "Invalid datatype for {}: {}".format(field, datatype))
            self._destfields.append(field)
            self._dest_datatypes.append(datatype)

        src_fields = [c.name for c in
                      InputFieldConfig.get_core_columns_for_dest()]
        for sf in src_fields:
            if sf in self._destfields:
                raise Exception(
                    "For section {}, destination field {} is auto-supplied; "
                    "do not add it manually".format(section, sf))

        if len(set(self._destfields)) != len(self._destfields):
            raise ValueError("Duplicate fields exist in destination fields: "
                             "{}".format(self._destfields))

        self._indexfields = []
        self._indexlengths = []
        indexdefs = opt_strlist('indexdefs')
        if indexdefs:
            for c in chunks(indexdefs, 2):  # pairs: field, length
                indexfieldname = c[0]
                lengthstr = c[1]
                if indexfieldname not in self._destfields:
                    raise ValueError(
                        "Index field {} not in destination fields {}".format(
                            indexfieldname, self._destfields))
                try:
                    length = ast.literal_eval(lengthstr)
                    if length is not None:
                        length = int(length)
                except ValueError:
                    raise ValueError(
                        "Bad index length: {}".format(lengthstr))
                self._indexfields.append(indexfieldname)
                self._indexlengths.append(length)

    def get_tablename(self) -> str:
        return self._desttable

    def get_columns(self, engine) -> List[Column]:
        columns = []
        for i, field in enumerate(self._destfields):
            datatype = self._dest_datatypes[i]
            columns.append(Column(
                field,
                get_sqla_coltype_from_dialect_str(datatype, engine.dialect)
            ))
        return columns

    def get_indexes(self) -> List[Index]:
        indexes = []
        for i, field in enumerate(self._indexfields):
            index_name = '_idx_{}'.format(field)
            length = self._indexlengths[i]
            kwargs = {'mysql_length': length} if length is not None else {}
            indexes.append(Index(index_name, field, **kwargs))
        return indexes
