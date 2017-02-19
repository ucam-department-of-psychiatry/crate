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
from typing import List, Optional

from pyparsing import ParseResults

from crate_anon.common.logsupport import main_only_quicksetup_rootlogger
from crate_anon.common.sql import (
    ColumnId,
    get_first_from_table,
    JoinInfo,
    parser_add_result_column,
    parser_add_from_tables,
    set_distinct_within_parsed,
    TableId,
    WhereCondition,
)
from crate_anon.common.sql_grammar import (
    format_sql,
    SqlGrammar,
    text_from_parsed,
)
from crate_anon.common.sql_grammar_factory import DIALECT_MYSQL, make_grammar
from crate_anon.crateweb.research.research_db_info import (
    research_database_info,
)

log = logging.getLogger(__name__)


# =============================================================================
# Automagically create/manipulate SQL statements based on our extra knowledge
# of the fields that can be used to link across tables/databases.
# =============================================================================

def get_join_info(grammar: SqlGrammar,
                  parsed: ParseResults,
                  jointable: TableId,
                  magic_join: bool = False,
                  nonmagic_join_type: str = "INNER JOIN",
                  nonmagic_join_condition: str = '') -> List[JoinInfo]:
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
        return [JoinInfo(join_type=nonmagic_join_type,
                         table=jointable.identifier(grammar),
                         join_condition=nonmagic_join_condition)]

    if from_table_in_join_schema:
        # Another table from the same database is present. Link on the
        # TRID field.
        # log.critical("get_join_info: joining to another table in same DB")
        return [JoinInfo(
            join_type='INNER JOIN',
            table=jointable.identifier(grammar),
            join_condition="ON {new} = {existing}".format(
                new=research_database_info.get_trid_column(
                    jointable).identifier(grammar),
                existing=research_database_info.get_trid_column(
                    from_table_in_join_schema).identifier(grammar),
            )
        )]

    # OK. So now we're building a cross-database join.
    existing_family = research_database_info.get_db_rid_family(
        first_from_table.schema_id())
    new_family = research_database_info.get_db_rid_family(
        jointable.schema_id())
    # log.critical("existing_family={}, new_family={}".format(
    #     existing_family, new_family))
    if existing_family and existing_family == new_family:
        # log.critical("get_join_info: new DB, same RID family")
        return [JoinInfo(
            join_type='INNER JOIN',
            table=jointable.identifier(grammar),
            join_condition="ON {new} = {existing}".format(
                new=research_database_info.get_rid_column(
                    jointable).identifier(grammar),
                existing=research_database_info.get_rid_column(
                    first_from_table).identifier(grammar),
            )
        )]

    # If we get here, we have to do a complicated join via the MRID.
    # log.critical("get_join_info: new DB, different RID family, using MRID")
    existing_mrid_column = research_database_info.get_mrid_column_from_table(
        first_from_table)
    existing_mrid_table = existing_mrid_column.table_id()
    if not existing_mrid_table:
        raise ValueError(
            "No MRID table available (in the same database as table {}; "
            "cannot link)".format(first_from_table))
    new_mrid_column = research_database_info.get_mrid_column_from_table(
        jointable)
    new_mrid_table = new_mrid_column.table_id()
    existing_mrid_table_in_query = bool(get_first_from_table(
        parsed,
        match_db=existing_mrid_table.db(),
        match_schema=existing_mrid_table.schema(),
        match_table=existing_mrid_table.table()))

    joins = []
    if not existing_mrid_table_in_query:
        joins.append(JoinInfo(
            join_type='INNER JOIN',
            table=existing_mrid_table.identifier(grammar),
            join_condition="ON {m1_trid1} = {t1_trid1}".format(
                m1_trid1=research_database_info.get_trid_column(
                    existing_mrid_table).identifier(grammar),
                t1_trid1=research_database_info.get_trid_column(
                    first_from_table).identifier(grammar),
            )
        ))
    joins.append(JoinInfo(
        join_type='INNER JOIN',
        table=new_mrid_table.identifier(grammar),
        join_condition="ON {m2_mrid2} = {m1_mrid1}".format(
            m2_mrid2=new_mrid_column.identifier(grammar),
            m1_mrid1=existing_mrid_column.identifier(grammar),
        )
    ))
    if jointable != new_mrid_table:
        joins.append(JoinInfo(
            join_type='INNER JOIN',
            table=jointable.identifier(grammar),
            join_condition="ON {t2_trid2} = {m2_trid2}".format(
                t2_trid2=research_database_info.get_trid_column(
                    jointable).identifier(grammar),
                m2_trid2=research_database_info.get_trid_column(
                    new_mrid_table).identifier(grammar),
            )
        ))
    return joins


class SelectElement(object):
    def __init__(self,
                 column_id: ColumnId = None,
                 raw_select: str = '',
                 from_table_for_raw_select: TableId = None,
                 alias: str = ''):
        self.column_id = column_id
        self.raw_select = raw_select
        self.from_table_for_raw_select = from_table_for_raw_select
        self.alias = alias

    def __repr__(self) -> str:
        return (
            "<{qualname}("
            "column_id={column_id}, "
            "raw_select={raw_select}, "
            "from_table_for_raw_select={from_table_for_raw_select}, "
            "alias={alias}) "
            "at {addr}>".format(
                qualname=self.__class__.__qualname__,
                column_id=repr(self.column_id),
                raw_select=repr(self.raw_select),
                from_table_for_raw_select=repr(self.from_table_for_raw_select),
                alias=repr(self.alias),
                addr=hex(id(self)),
            )
        )

    def sql_select_column(self, grammar: SqlGrammar) -> str:
        result = self.raw_select or self.column_id.identifier(grammar)
        if self.alias:
            result += " AS " + self.alias
        return result

    def from_table(self) -> Optional[TableId]:
        if self.raw_select:
            return self.from_table_for_raw_select
        return self.column_id.table_id()

    def from_table_str(self, grammar: SqlGrammar) -> str:
        table_id = self.from_table()
        if not table_id:
            return ''
        return table_id.identifier(grammar)

    def sql_select_from(self, grammar: SqlGrammar) -> str:
        sql = "SELECT " + self.sql_select_column(grammar=grammar)
        from_table = self.from_table()
        if from_table:
            sql += " FROM " + from_table.identifier(grammar)
        return sql


def reparse_select(p: ParseResults, grammar: SqlGrammar) -> ParseResults:
    """
    Internal function for when we get desperate trying to hack around
    the results of pyparsing's efforts.
    """
    return grammar.get_select_statement().parseString(
        text_from_parsed(p, formatted=False),
        parseAll=True
    )


def add_to_select(sql: str,
                  grammar: SqlGrammar,
                  select_elements: List[SelectElement] = None,
                  where_conditions: List[WhereCondition] = None,
                  # For SELECT:
                  distinct: bool = None,  # True, False, or None to leave as is
                  # For WHERE:
                  where_type: str = "AND",
                  bracket_where: bool = False,
                  # For either, for JOIN:
                  magic_join: bool = True,
                  join_type: str = "NATURAL JOIN",
                  join_condition: str = '',
                  # General:
                  formatted: bool = True,
                  debug: bool = False,
                  debug_verbose: bool = False) -> str:
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

    Parsing is SLOW, so we should do as much as possible in a single call to
    this function.
    """
    select_elements = select_elements or []  # type: List[SelectElement]
    where_conditions = where_conditions or []  # type: List[WhereCondition]
    if debug:
        log.info("START: {}".format(sql))
        log.debug("select_elements: {}".format(select_elements))
        log.debug("where_conditions: {}".format(where_conditions))
        log.debug("where_type: {}".format(where_type))
        log.debug("join_type: {}".format(join_type))
        log.debug("join_condition: {}".format(join_condition))

    # -------------------------------------------------------------------------
    # Get going. We have to handle a fresh SQL statement in a slightly
    # different way.
    # -------------------------------------------------------------------------
    if not sql:
        if not select_elements:
            raise ValueError("Fresh SQL statements must include a SELECT "
                             "element")
        # ---------------------------------------------------------------------
        # Fresh SQL statement
        # ---------------------------------------------------------------------
        first_select = select_elements[0]
        select_elements = select_elements[1:]
        sql = first_select.sql_select_from(grammar)
        # log.debug("Starting SQL from scratch as: " + sql)

    # -------------------------------------------------------------------------
    # Parse what we have (which is now, at a minimum, SELECT ... FROM ...).
    # -------------------------------------------------------------------------
    p = grammar.get_select_statement().parseString(sql, parseAll=True)
    if debug and debug_verbose:
        log.debug("start dump:\n" + p.dump())

    # *** problem emerging here from patient explorer:
    existing_tables = p.join_source.from_tables.asList()  # type: List[str]
    new_tables = []  # type: List[TableId]

    def add_new_table(_table_id: TableId) -> None:
        if (_table_id and
                _table_id not in new_tables and
                _table_id.identifier(grammar) not in existing_tables):
            new_tables.append(_table_id)

    # -------------------------------------------------------------------------
    # DISTINCT?
    # -------------------------------------------------------------------------
    if distinct is True:
        set_distinct_within_parsed(p, action='set')
    elif distinct is False:
        set_distinct_within_parsed(p, action='clear')

    # -------------------------------------------------------------------------
    # Process all the (other?) SELECT clauses
    # -------------------------------------------------------------------------
    for se in select_elements:
        p = parser_add_result_column(p, se.sql_select_column(grammar),
                                     grammar=grammar)
        add_new_table(se.from_table())

    # -------------------------------------------------------------------------
    # Process all the WHERE clauses
    # -------------------------------------------------------------------------
    for wc in where_conditions:
        where_expression = wc.sql(grammar)
        if bracket_where:
            where_expression = '(' + where_expression + ')'

        # The tricky bit: inserting it.
        # We use the [0] to overcome the effects of defining these things
        # as a pyparsing Group(), which encapsulates the results in a list.
        if p.where_clause:
            cond = grammar.get_expr().parseString(where_expression,
                                                  parseAll=True)[0]
            extra = [where_type, cond]
            p.where_clause.where_expr.extend(extra)
        else:
            # No WHERE as yet
            # Doing this properly is a nightmare.
            # It's hard to add a *named* ParseResults element to another.
            # So it's very hard to alter p.where_clause.where_expr such that
            # we can continue adding more WHERE clauses if we want.
            # This is the inefficient, cop-out method:
            # (1) Add as plain text
            p.where_clause.append("WHERE " + where_expression)
            # (2) Reparse...
            p = reparse_select(p, grammar=grammar)

        add_new_table(wc.table_id())

    # -------------------------------------------------------------------------
    # Process all the FROM clauses, autojoining as necessary
    # -------------------------------------------------------------------------

    for table_id in new_tables:
        p = parser_add_from_tables(
            p,
            get_join_info(grammar=grammar,
                          parsed=p,
                          jointable=table_id,
                          magic_join=magic_join,
                          nonmagic_join_type=join_type,
                          nonmagic_join_condition=join_condition),
            grammar=grammar)

    if debug and debug_verbose:
        log.debug("end dump:\n" + p.dump())
    result = text_from_parsed(p, formatted=False)
    if formatted:
        result = format_sql(result)
    if debug:
        log.info("END: {}".format(result))
    return result


# =============================================================================
# Unit tests
# =============================================================================

def unit_tests() -> None:
    grammar = make_grammar(DIALECT_MYSQL)
    log.info(add_to_select(
        "SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 5",
        grammar=grammar,
        select_elements=[SelectElement(
            column_id=ColumnId(table="t2", column="c")
        )],
        magic_join=False  # magic_join requires DB knowledge hence Django
    ))
    log.info(add_to_select(
        "SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 5",
        grammar=grammar,
        select_elements=[SelectElement(
            column_id=ColumnId(table="t1", column="a")
        )]
    ))
    log.info(add_to_select(
        "",
        grammar=grammar,
        select_elements=[SelectElement(
            column_id=ColumnId(table="t2", column="c")
        )]
    ))
    log.info(add_to_select(
        "SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 5",
        grammar=grammar,
        where_conditions=[WhereCondition(raw_sql="t1.col2 < 3")]
    ))
    log.info(add_to_select(
        "SELECT t1.a, t1.b FROM t1",
        grammar=grammar,
        where_conditions=[WhereCondition(raw_sql="t1.col1 > 5")]
    ))
    log.info(add_to_select(
        "SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 5 AND t3.col99 = 100",
        grammar=grammar,
        where_conditions=[WhereCondition(raw_sql="t1.col2 < 3")]
    ))

    # Multiple WHEREs where before there were none:
    log.info(add_to_select(
        "SELECT t1.a, t1.b FROM t1",
        grammar=grammar,
        where_conditions=[WhereCondition(raw_sql="t1.col1 > 99"),
                          WhereCondition(raw_sql="t1.col2 < 999")]
    ))


if __name__ == '__main__':
    main_only_quicksetup_rootlogger()
    unit_tests()
