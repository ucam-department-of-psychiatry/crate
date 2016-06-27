#!/usr/bin/env python

import logging

import sqlparse

from crate_anon.anonymise.logsupport import main_only_quicksetup_rootlogger
from crate_anon.crateweb.research.sql_grammar_mysql import (
    column_spec,
    expr,
    # flatten,
    join_constraint,
    join_op,
    select_statement,
    table_spec,
    text_from_parsed,
)

log = logging.getLogger(__name__)


def sql_string_literal(text):
    return "'" + text.replace("'", "''") + "'"


def sql_date_literal(dt):
    return dt.strftime("'%Y-%m-%d'")


def sql_datetime_literal(dt, subsecond=False):
    fmt = "'%Y-%m-%dT%H:%M:%S{}'".format(".%f" if subsecond else "")
    return dt.strftime(fmt)


def parser_add_result_column(parsed, column):
    # Presupposes at least one column already in the SELECT statement.

    existing_columns = parsed.select_expression.select_columns.asList()
    # log.critical(parsed.dump())
    # log.critical("existing columns: {}".format(repr(existing_columns)))
    # log.critical("adding column: {}".format(column))
    if column not in existing_columns:
        # log.critical("... doesn't exist; adding")
        newcol = column_spec.parseString(column)[0]
        parsed.select_expression.extend([",", newcol])
    # else:
    #     log.critical("... skipping column; exists")
    # log.critical(parsed.dump())
    return parsed


def parser_add_from_table(parsed, table, join_type="INNER JOIN",
                          join_condition=None):
    # Presupposes at least one table already in the FROM clause.
    # log.critical(parsed.dump())
    existing_tables = parsed.join_source.from_tables.asList()
    # log.critical("existing tables: {}".format(existing_tables))
    # log.critical("adding table: {}".format(table))
    if table in existing_tables:  # already there
        # log.critical("field already present")
        return parsed
    parsed_join = join_op.parseString(join_type)[0]  # e.g. INNER JOIN
    parsed_table = table_spec.parseString(table)[0]
    extrabits = [parsed_join, parsed_table]
    if join_condition:  # e.g. ON x = y
        extrabits.append(join_constraint.parseString(join_condition)[0])
    parsed.join_source.extend(extrabits)
    # log.critical(parsed.dump())
    return parsed


def get_first_from_table(parsed):
    existing_tables = parsed.join_source.from_tables.asList()
    if existing_tables:
        return existing_tables[0]
    return None


def toggle_distinct(sql, formatted=True, debug=False, debug_verbose=False):
    p = select_statement.parseString(sql)
    if debug:
        log.info("START: {}".format(sql))
        if debug_verbose:
            log.debug("start dump:\n" + p.dump())
    # log.critical(repr(p.select_specifier))
    if p.select_specifier and 'DISTINCT' in p.select_specifier[0]:
        # log.critical("Already has DISTINCT")
        del p.select_specifier[:]
    else:
        # log.critical("Does not already have DISTINCT")
        p.select_specifier.append('DISTINCT')
    result = text_from_parsed(p, formatted=formatted)
    if debug:
        log.info("END: {}".format(result))
        if debug_verbose:
            log.debug("end dump:\n" + p.dump())
    return result


def add_to_select(sql,
                  table=None, column=None,
                  inner_join_to_first_on_keyfield=None,  # overrides others
                  join_type="NATURAL JOIN", join_condition=None,
                  where_type="AND", where_expression=None, where_table=None,
                  bracket_where=False,
                  formatted=True, debug=False, debug_verbose=False):
    """
    This function encapsulates our query builder's common operations.
    One premise is that SQL parsing is relatively slow, so we should do this
    only once. We parse; add bits to the parsed structure as required; then
    re-convert to text.

    If you specify table/column, elements will be added to SELECT and FROM
    unless they already exist.

    If you specify where_expression, elements will be added to WHERE.
    In this situation, you should also specify where_table; if the where_table
    isn't yet in the FROM clause, this will be added as well (according to
    inner_join_to_first_on_keyfield, join_type, and join_condition).
    """

    def get_join_type_condition(jointable):
        _join_type = join_type
        _join_condition = join_condition
        if inner_join_to_first_on_keyfield:
            first_table = get_first_from_table(p)
            if first_table:
                _join_type = "INNER JOIN"
                _join_condition = (
                    "ON {new}.{keyfield}={first}.{keyfield}".format(
                        new=jointable,
                        first=first_table,
                        keyfield=inner_join_to_first_on_keyfield,
                    )
                )
        return _join_type, _join_condition

    if debug:
        log.info("START: {}".format(sql))
    colspec = "{}.{}".format(table, column)
    if not sql:
        if column and table:
            result = sqlparse.format(
                "SELECT {} FROM {}".format(colspec, table),
                reindent=True)
            if where_expression:
                result += " WHERE {}".format(where_expression)
        else:
            raise ValueError("Blank starting SQL but no SELECT table/column")
    else:
        p = select_statement.parseString(sql)
        if debug and debug_verbose:
            log.debug("start dump:\n" + p.dump())

        # ---------------------------------------------------------------------
        # SELECT... FROM
        # ---------------------------------------------------------------------
        if column and table:
            p = parser_add_result_column(p, colspec)
            jt, jc = get_join_type_condition(table)
            p = parser_add_from_table(p, table, jt, jc)

        # ---------------------------------------------------------------------
        # WHERE
        # ---------------------------------------------------------------------
        if where_expression:
            # log.critical(where_expression)
            cond = expr.parseString(where_expression)
            # log.critical(cond)
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
                jt, jc = get_join_type_condition(where_table)
                p = parser_add_from_table(p, where_table, jt, jc)

        if debug and debug_verbose:
            log.debug("end dump:\n" + p.dump())
        result = text_from_parsed(p, formatted=formatted)
    if debug:
        log.info("END:\n{}".format(result))
    return result


def unit_tests():
    add_to_select("SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 5",
                  table="t2", column="c")
    add_to_select("SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 5",
                  table="t1", column="a")
    add_to_select("", table="t2", column="c")
    add_to_select("SELECT t1.a, t1.b FROM t1",
                  where_expression="t1.col2 < 3")
    add_to_select("SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 5",
                  where_expression="t1.col2 < 3")


if __name__ == '__main__':
    main_only_quicksetup_rootlogger()
    unit_tests()
