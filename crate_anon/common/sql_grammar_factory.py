#!/usr/bin/env python
# crate_anon/crateweb/research/sql_grammar_factory.py

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

from crate_anon.common.sql_grammar import SqlGrammar
from crate_anon.common.sql_grammar_mssql import SqlGrammarMSSQLServer
from crate_anon.common.sql_grammar_mysql import SqlGrammarMySQL


DIALECT_MSSQL = 'mssql'  # Microsoft SQL Server; must match querybuilder.js
DIALECT_MYSQL = 'mysql'  # MySQL; must match querybuilder.js
DIALECT_POSTGRES = 'postgres'  # *** NOT PROPERLY SUPPORTED.

VALID_DIALECTS = [DIALECT_MYSQL, DIALECT_MYSQL]


# =============================================================================
# Factory
# =============================================================================

mysql_grammar = SqlGrammarMySQL()
mssql_grammar = SqlGrammarMSSQLServer()


def make_grammar(dialect: str) -> SqlGrammar:
    if dialect == DIALECT_MYSQL:
        return mysql_grammar
    elif dialect == DIALECT_MSSQL:
        return mssql_grammar
    else:
        raise AssertionError("Invalid SQL dialect: {}".format(repr(dialect)))
