#!/usr/bin/env python

import logging

from crate_anon.anonymise.logsupport import main_only_quicksetup_rootlogger
from crate_anon.crateweb.research.sql_grammar_mysql import (
    column_spec,
    expr,
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
    newcol = column_spec.parseString(column)[0]
    parsed.columns.extend([",", newcol])
    return parsed


def parser_add_from_table(parsed, table, join_type="INNER JOIN",
                          join_condition=None):
    # Presupposes at least one table already in the FROM clause.
    extrabits = list(join_op.parseString(join_type))  # e.g. INNER JOIN
    extrabits.append(table_spec.parseString(table))
    if join_condition:  # e.g. ON x = y
        extrabits.append(join_constraint.parseString(join_condition))
    parsed.join_source.extend(extrabits)
    return parsed


def add_result_column(sql, column, source_table,
                      join_type="INNER JOIN", join_condition=None,
                      debug=True):
    # The caller should specify the column as table.column
    if debug:
        log.info("START: {}".format(sql))
    if not sql:
        result = "SELECT {} FROM {}".format(column, source_table)
    else:
        p = select_statement.parseString(sql)
        if debug:
            log.debug("start dump:\n" + p.dump())
        p = parser_add_result_column(p, column)
        p = parser_add_from_table(p, source_table, join_type, join_condition)
        if debug:
            log.debug("end dump:\n" + p.dump())
        result = text_from_parsed(p)
    if debug:
        log.info("END:\n{}".format(result))
    return result


def add_where_cond_with_and(sql, expression, debug=True):
    # Presupposes at least SELECT ... FROM ...
    p = select_statement.parseString(sql)
    if debug:
        log.info("START: {}".format(sql))
        log.debug("start dump:\n{}".format(p.dump()))
    cond = expr.parseString(expression)
    if p.where_clause:
        extra = ["AND", "(", cond, ")"]
        p.where_clause.where_expr.extend(extra)
    else:
        # No WHERE as yet
        extra = ["WHERE", "(", cond, ")"]
        p.where_clause.extend(extra)
    result = text_from_parsed(p)
    if debug:
        log.debug("end dump:\n" + p.dump())
        log.info("END:\n{}".format(result))
    return result


def unit_tests():
    add_result_column("SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 5",
                      "t2.c", "t2")
    add_result_column("", "t2.c", "t2")
    add_where_cond_with_and(
        "SELECT t1.a, t1.b FROM t1",
        "t1.col2 < 3")
    add_where_cond_with_and(
        "SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 5",
        "t1.col2 < 3")


if __name__ == '__main__':
    main_only_quicksetup_rootlogger()
    unit_tests()
