#!/usr/bin/env python

"""
crate_anon/crateweb/research/sql_writer.py

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

**Automatically create/manipulate SQL statements based on our extra knowledge
of the fields that can be used to link across tables/databases.**

"""

import logging
from typing import List, Optional

from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from cardinal_pythonlib.sql.sql_grammar import (
    format_sql,
    SqlGrammar,
    text_from_parsed,
)
from cardinal_pythonlib.sql.sql_grammar_factory import make_grammar
from cardinal_pythonlib.sqlalchemy.dialect import SqlaDialectName
from pyparsing import ParseResults

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
from crate_anon.crateweb.research.research_db_info import (
    research_database_info,
)

log = logging.getLogger(__name__)


# =============================================================================
# Automatic SQL generation functions
# =============================================================================

def get_join_info(grammar: SqlGrammar,
                  parsed: ParseResults,
                  jointable: TableId,
                  magic_join: bool = False,
                  nonmagic_join_type: str = "INNER JOIN",
                  nonmagic_join_condition: str = '') -> List[JoinInfo]:
    """
    Works out how to join a new table into an existing SQL ``SELECT`` query.

    Args:
        grammar:
            :class:`cardinal_pythonlib.sql.sql_grammar.SqlGrammar`
            representing the SQL dialect/grammar in use
        parsed:
            existing :class:`pyparsing.ParseResults` representing the
            ``SELECT`` statement so far
        jointable:
            :class:`crate_anon.common.sql.TableId` representing the table to be
            joined in
        magic_join:
            perform a "magic join", i.e. join the new table in based on our
            knowledge of the research database structure?
        nonmagic_join_type:
            if ``not magic_join``, this is an SQL string specifying the join
            type, e.g. ``"INNER JOIN"``
        nonmagic_join_condition:
            if ``not magic_join``, this is an SQL string specifying the join
            condition, e.g. ``"ON x = y"``

    Returns:
        a list of :class:`crate_anon.common.sql.JoinInfo` objects, e.g.
        ``[JoinInfo("tablename", "INNER JOIN", "WHERE somecondition")]``.

    Notes:

    - ``INNER JOIN`` etc. is part of ANSI SQL

    """
    first_from_table = get_first_from_table(parsed)
    from_table_in_join_schema = get_first_from_table(
        parsed,
        match_db=jointable.db,
        match_schema=jointable.schema)
    exact_match_table = get_first_from_table(
        parsed,
        match_db=jointable.db,
        match_schema=jointable.schema,
        match_table=jointable.table)

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
    existing_family = research_database_info.get_dbinfo_by_schema_id(
        first_from_table.schema_id).rid_family
    new_family = research_database_info.get_dbinfo_by_schema_id(
        jointable.schema_id).rid_family
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
    existing_mrid_table = existing_mrid_column.table_id
    if not existing_mrid_table:
        raise ValueError(
            f"No MRID table available (in the same database as table "
            f"{first_from_table}; cannot link)")
    new_mrid_column = research_database_info.get_mrid_column_from_table(
        jointable)
    new_mrid_table = new_mrid_column.table_id
    existing_mrid_table_in_query = bool(get_first_from_table(
        parsed,
        match_db=existing_mrid_table.db,
        match_schema=existing_mrid_table.schema,
        match_table=existing_mrid_table.table))

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
    """
    Class to represent a result column in an SQL ``SELECT`` statement.
    """
    def __init__(self,
                 column_id: ColumnId = None,
                 raw_select: str = '',
                 from_table_for_raw_select: TableId = None,
                 alias: str = ''):
        """
        Args:
            column_id:
                a :class:`crate_anon.common.sql.ColumnId` object; using this
                will automatically add the column's table to the ``FROM``
                clause
            raw_select:
                as an alternative to ``column_id``, raw SQL for the ``SELECT``
                clause
            from_table_for_raw_select:
                if ``raw_select`` is used, a
                :class:`crate_anon.common.sql.TableId` that should be added to
                the ``FROM`` clause
            alias:
                alias to be used, i.e. for ``SELECT something AS alias``
        """
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
        """
        Return the raw SQL for this ``SELECT`` result column.

        Args:
            grammar:
                :class:`cardinal_pythonlib.sql.sql_grammar.SqlGrammar`
                representing the SQL dialect/grammar in use

        Returns:
            str: SQL like ``colname`` or ``expression`` or ``colname AS alias``

        """
        result = self.raw_select or self.column_id.identifier(grammar)
        if self.alias:
            result += " AS " + self.alias
        return result

    def from_table(self) -> Optional[TableId]:
        """
        Returns details of the table to be added to the ``FROM`` clause of the
        ``SELECT`` statement.

        Returns:
            a :class:`crate_anon.common.sql.TableId`, or ``None`` (if
            ``raw_select`` is used and ``from_table_for_raw_select`` was not
            specified)

        """
        if self.raw_select:
            return self.from_table_for_raw_select
        return self.column_id.table_id

    def from_table_str(self, grammar: SqlGrammar) -> str:
        """
        Returns a string form of :meth:`from_table`, i.e. an SQL identifier
        for the ``FROM`` clause.

        Args:
            grammar:
                :class:`cardinal_pythonlib.sql.sql_grammar.SqlGrammar`
                representing the SQL dialect/grammar in use

        Returns:
            str: SQL like ``from_table``

        """
        table_id = self.from_table()
        if not table_id:
            return ''
        return table_id.identifier(grammar)

    def sql_select_from(self, grammar: SqlGrammar) -> str:
        """
        Returns a full ``SELECT... FROM...`` statement.

        Args:
            grammar:
                :class:`cardinal_pythonlib.sql.sql_grammar.SqlGrammar`
                representing the SQL dialect/grammar in use

        Returns:
            str: SQL like ``SELECT colname AS alias FROM from_table``

        """
        sql = "SELECT " + self.sql_select_column(grammar=grammar)
        from_table = self.from_table()
        if from_table:
            sql += " FROM " + from_table.identifier(grammar)
        return sql


def reparse_select(p: ParseResults, grammar: SqlGrammar) -> ParseResults:
    """
    Internal function for when we get desperate trying to hack around
    the results of ``pyparsing``'s efforts.

    - takes a :class:`pyparsing.ParseResults`
    - converts it to an SQL string
    - parses the string as a ``SELECT`` statement
    - returns the resulting :class:`pyparsing.ParseResults`
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
                  distinct: bool = None,
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

    If you specify table/column, elements will be added to ``SELECT`` and
    ``FROM`` unless they already exist.

    If you specify ``where_expression``, elements will be added to ``WHERE``.
    In this situation, you should also specify ``where_table``; if the
    ``where_table`` isn't yet in the ``FROM`` clause, this will be added as
    well.

    Parsing is SLOW, so we should do as much as possible in a single call to
    this function.

    Args:
        sql:
            existing SQL statement
        grammar:
            :class:`cardinal_pythonlib.sql.sql_grammar.SqlGrammar`
            representing the SQL dialect/grammar in use
        select_elements:
            optional list of :class:`SelectElement` objects representing
            things to add to the ``SELECT`` clause of the ``SELECT`` statement
            (i.e. results columns)
        where_conditions:
            optional list of :class:`crate_anon.common.sql.WhereCondition`
            representing conditions to add to the ``WHERE`` clause of the
            ``SELECT`` statement
        distinct:
            if ``True``, make the ``SELECT`` statement a ``SELECT DISTINCT``;
            if ``False``, remove any ``DISTINCT``; if ``None``, leave the
            ``DISTINCT`` status as it is.
        where_type:
            logical operator with which to join multiple parts of the ``WHERE``
            expression, typically ``AND`` (but maybe ``OR``, etc.)
        bracket_where:
            put brackets ``()`` around each new part of the ``WHERE``
            expression?
        magic_join:
            perform a "magic join", i.e. join the new table in based on our
            knowledge of the research database structure?
        join_type:
            if ``not magic_join``, this is an SQL string specifying the join
            type, e.g. ``"INNER JOIN"``
        join_condition:
            if ``not magic_join``, this is an SQL string specifying the join
            condition, e.g. ``"ON x = y"``
        formatted:
            reformat the SQL to look pretty?
        debug:
            show debugging information
        debug_verbose:
            show verbose debugging information

    Returns:
        str: SQL statement

    """
    select_elements = select_elements or []  # type: List[SelectElement]
    where_conditions = where_conditions or []  # type: List[WhereCondition]
    if debug:
        log.info(f"START: {sql}")
        log.debug(f"select_elements: {select_elements}")
        log.debug(f"where_conditions: {where_conditions}")
        log.debug(f"where_type: {where_type}")
        log.debug(f"join_type: {join_type}")
        log.debug(f"join_condition: {join_condition}")

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

        add_new_table(wc.table_id)

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
        log.info(f"END: {result}")
    return result


# =============================================================================
# Unit tests
# =============================================================================

def unit_tests() -> None:
    """
    Unit tests.
    """
    grammar = make_grammar(SqlaDialectName.MYSQL)
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
