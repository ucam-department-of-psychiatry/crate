#!/usr/bin/env python
# crate_anon/crateweb/research/sql_writer.py

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
from typing import Dict, List

from pyparsing import ParseResults
import sqlparse

from crate_anon.common.logsupport import main_only_quicksetup_rootlogger
from crate_anon.common.sql import (
    ColumnName,
    get_first_from_table,
    parser_add_result_column,
    parser_add_from_tables,
    TableName,
)
from crate_anon.common.sql_grammar import (
    DIALECT_MYSQL,
    make_grammar,
    SqlGrammar,
    text_from_parsed,
)
from crate_anon.crateweb.research.models import (
    get_schema_trid_field,
    get_schema_rid_field,
    get_db_rid_family,
    get_db_mrid_table,
    get_db_mrid_field,
)

log = logging.getLogger(__name__)


def get_rid_column(table: TableName) -> ColumnName:
    # RID column in the specified table
    return table.columnname(get_schema_rid_field(table.db(), table.schema()))


def get_trid_column(table: TableName) -> ColumnName:
    # TRID column in the specified table
    return table.columnname(get_schema_trid_field(table.db(), table.schema()))


def get_mrid_column(table: TableName) -> ColumnName:
    # MRID column in the MRID master table
    db = table.db()
    schema = table.schema()
    return ColumnName(db=db,
                      schema=schema,
                      table=get_db_mrid_table(db=db, schema=schema),
                      column=get_db_mrid_field(db=db, schema=schema))


def get_join_info(grammar: SqlGrammar,
                  parsed: ParseResults,
                  jointable: TableName,
                  magic_join: bool = False,
                  nonmagic_join_type: str = "INNER JOIN",
                  nonmagic_join_condition: str = None) -> List[Dict[str, str]]:
    # Returns e.g. ["INNER JOIN", "tablename", "WHERE somecondition"].
    # INNER JOIN etc. is part of ANSI SQL
    first_from_table = get_first_from_table(parsed)
    from_table_in_join_schema = get_first_from_table(
        parsed,
        match_db=jointable.db(),
        match_schema=jointable.schema())
    exact_match_table = get_first_from_table(
        parsed,
        match_db=jointable.db(),
        match_schema=jointable.schema(),
        match_table=jointable.table())

    if not first_from_table:
        # No tables in query yet.
        # This should not happen; this function is to help with adding
        # new FROM tables to existing FROM clauses.
        log.warning("get_join_info: no tables in query")
        return []

    if exact_match_table:
        # This table is already in the query. No JOIN should be required.
        # log.critical("get_join_info: same table already in query")
        return []

    if not magic_join:
        # log.critical("get_join_info: non-magic join")
        return [{
            'join_type': nonmagic_join_type,
            'table': jointable.identifier(grammar),
            'join_condition': nonmagic_join_condition,
        }]

    if from_table_in_join_schema:
        # Another table from the same database is present. Link on the
        # TRID field.
        # log.critical("get_join_info: joining to another table in same DB")
        return [{
            'join_type': 'INNER JOIN',
            'table': jointable.identifier(grammar),
            'join_condition': "ON {new} = {existing}".format(
                new=get_trid_column(jointable).identifier(grammar),
                existing=get_trid_column(from_table_in_join_schema).identifier(grammar),  # noqa
            ),
        }]

    # OK. So now we're building a cross-database join.
    existing_family = get_db_rid_family(db=first_from_table.db(),
                                        schema=first_from_table.schema())
    new_family = get_db_rid_family(db=jointable.db(),
                                   schema=jointable.schema())
    # log.critical("existing_family={}, new_family={}".format(
    #     existing_family, new_family))
    if existing_family and existing_family == new_family:
        # log.critical("get_join_info: new DB, same RID family")
        return [{
            'join_type': 'INNER JOIN',
            'table': jointable.identifier(grammar),
            'join_condition': "ON {new} = {existing}".format(
                new=get_rid_column(jointable).identifier(grammar),
                existing=get_rid_column(first_from_table).identifier(grammar),
            ),
        }]

    # If we get here, we have to do a complicated join via the MRID.
    # log.critical("get_join_info: new DB, different RID family, using MRID")
    existing_mrid_column = get_mrid_column(first_from_table)
    existing_mrid_table = existing_mrid_column.tablename()
    new_mrid_column = get_mrid_column(jointable)
    new_mrid_table = new_mrid_column.tablename()
    existing_mrid_table_in_query = bool(get_first_from_table(
        parsed,
        match_db=existing_mrid_table.db(),
        match_schema=existing_mrid_table.schema(),
        match_table=existing_mrid_table.table()))

    joins = []
    if not existing_mrid_table_in_query:
        joins.append({
            'join_type': 'INNER JOIN',
            'table': existing_mrid_table.identifier(grammar),
            'join_condition': "ON {m1_trid1} = {t1_trid1}".format(
                m1_trid1=get_trid_column(existing_mrid_table).identifier(grammar),  # noqa
                t1_trid1=get_trid_column(first_from_table).identifier(grammar),
            ),
        })
    joins.append({
        'join_type': 'INNER JOIN',
        'table': new_mrid_table.identifier(grammar),
        'join_condition': "ON {m2_mrid2} = {m1_mrid1}".format(
            m2_mrid2=new_mrid_column.identifier(grammar),
            m1_mrid1=existing_mrid_column.identifier(grammar),
        ),
    })
    if jointable != new_mrid_table:
        joins.append({
            'join_type': 'INNER JOIN',
            'table': jointable.identifier(grammar),
            'join_condition': "ON {t2_trid2} = {m2_trid2}".format(
                t2_trid2=get_trid_column(jointable).identifier(grammar),
                m2_trid2=get_trid_column(new_mrid_table).identifier(grammar),
            ),
        })
    return joins


def add_to_select(sql: str,
                  # For SELECT:
                  select_column: ColumnName = ColumnName(),
                  # For WHERE:
                  where_expression: str = '',
                  where_type: str = "AND",
                  where_table: TableName = TableName(),
                  bracket_where: bool = False,
                  # For either, for JOIN:
                  magic_join: bool = True,
                  join_type: str = "NATURAL JOIN",
                  join_condition: str = '',
                  # General:
                  formatted: bool = True,
                  debug: bool = False,
                  debug_verbose: bool = False,
                  # Dialect:
                  dialect: str = DIALECT_MYSQL) -> str:
    """
    This function encapsulates our query builder's common operations.
    One premise is that SQL parsing is relatively slow, so we should do this
    only once. We parse; add bits to the parsed structure as required; then
    re-convert to text.

    If you specify table/column, elements will be added to SELECT and FROM
    unless they already exist.

    If you specify where_expression, elements will be added to WHERE.
    In this situation, you should also specify where_table; if the where_table
    isn't yet in the FROM clause, this will be added as well.
    """
    grammar = make_grammar(dialect)
    select_table = select_column.tablename()
    if debug:
        log.info("START: {}".format(sql))
        log.debug("select_column: {}".format(select_column))
        log.debug("join_type: {}".format(join_type))
        log.debug("join_condition: {}".format(join_condition))
        log.debug("where_type: {}".format(where_type))
        log.debug("where_expression: {}".format(where_expression))
        log.debug("where_table: {}".format(where_table))
    if not sql:
        # ---------------------------------------------------------------------
        # Fresh SQL statement
        # ---------------------------------------------------------------------
        if debug:
            log.debug("Starting SQL from scratch")
        if select_table and select_column:
            result = sqlparse.format(
                "SELECT {col} FROM {table}".format(
                    col=select_column.identifier(grammar),
                    table=select_column.tablename().identifier(grammar)
                ),
                reindent=True
            )
            if where_expression:
                result += " WHERE {}".format(where_expression)
        else:
            raise ValueError("Blank starting SQL but no SELECT table/column")
    else:
        p = grammar.get_select_statement().parseString(sql)
        if debug and debug_verbose:
            log.debug("start dump:\n" + p.dump())

        # ---------------------------------------------------------------------
        # add SELECT... +/- FROM
        # ---------------------------------------------------------------------
        if select_table and select_column:
            colspec = select_column.identifier(grammar)
            p = parser_add_result_column(p, colspec, grammar=grammar)
            p = parser_add_from_tables(
                p,
                get_join_info(grammar=grammar,
                              parsed=p,
                              jointable=select_column.tablename(),
                              magic_join=magic_join),
                grammar=grammar
            )

        # ---------------------------------------------------------------------
        # add WHERE... +/- FROM
        # ---------------------------------------------------------------------
        if where_expression:
            cond = grammar.get_expr().parseString(where_expression)
            if p.where_clause:
                if bracket_where:
                    extra = [where_type, "(", cond, ")"]
                else:
                    extra = [where_type, cond]
                p.where_clause.where_expr.extend(extra)
            else:
                # No WHERE as yet
                if bracket_where:
                    extra = ["WHERE", "(", cond, ")"]
                else:
                    extra = ["WHERE", cond]
                p.where_clause.extend(extra)
            if where_table:
                p = parser_add_from_tables(
                    p,
                    get_join_info(grammar=grammar,
                                  parsed=p,
                                  jointable=where_table,
                                  magic_join=magic_join,
                                  nonmagic_join_type=join_type,
                                  nonmagic_join_condition=join_condition),
                    grammar=grammar)

        if debug and debug_verbose:
            log.debug("end dump:\n" + p.dump())
        result = text_from_parsed(p, formatted=formatted)
    if debug:
        log.info("END:\n{}".format(result))
    return result


def unit_tests() -> None:
    add_to_select("SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 5",
                  select_column=ColumnName(table="t2", column="c"))
    add_to_select("SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 5",
                  select_column=ColumnName(table="t1", column="a"))
    add_to_select("", select_column=ColumnName(table="t2", column="c"))
    add_to_select("SELECT t1.a, t1.b FROM t1",
                  where_expression="t1.col2 < 3")
    add_to_select("SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 5",
                  where_expression="t1.col2 < 3")


if __name__ == '__main__':
    main_only_quicksetup_rootlogger()
    unit_tests()
