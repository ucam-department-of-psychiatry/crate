#!/usr/bin/env python

import logging

import sqlparse

from crate_anon.anonymise.logsupport import main_only_quicksetup_rootlogger
from crate_anon.crateweb.research.sql_grammar_mysql import (
    column_spec,
    expr,
    flatten,
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
    newcol = column_spec.parseString(column)
    existing_columns = parsed.columns[0]
    log.critical(parsed.dump())
    log.critical("adding column: {}".format(repr(newcol)))
    log.critical("existing columns: {}".format(repr(existing_columns)))
    if newcol not in existing_columns:
        # *** test not working
        log.critical("... doesn't exist; adding")
        parsed.columns.extend([",", newcol])
    else:
        log.critical("... skipping column; exists")
    return parsed


def parser_add_from_table(parsed, table, join_type="INNER JOIN",
                          join_condition=None):
    # Presupposes at least one table already in the FROM clause.
    parsed_join = join_op.parseString(join_type)  # e.g. INNER JOIN
    parsed_table = table_spec.parseString(table)
    log.critical("adding table: {}".format(repr(parsed_table)))
    js = parsed.join_source
    log.critical("js: {}".format(repr(js)))
    if parsed_table in parsed.join_source:  # already there
        # ... complex nested list... this worked out using repr!
        log.critical("field already present")
        return parsed
    extrabits = [parsed_join, parsed_table]
    if join_condition:  # e.g. ON x = y
        extrabits.append(join_constraint.parseString(join_condition))
    parsed.join_source.extend(extrabits)
    return parsed


def add_to_select(sql,
                  table=None, column=None,
                  join_type="NATURAL JOIN", join_condition=None,
                  where_expression=None,
                  formatted=True, debug=True):
    # The caller should specify the column as table.column
    # Specify EITHER table and column and join information, OR where info.
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
        if debug:
            log.debug("start dump:\n" + p.dump())

        # ---------------------------------------------------------------------
        # SELECT... FROM
        # ---------------------------------------------------------------------
        if column and table:
            p = parser_add_result_column(p, colspec)
            p = parser_add_from_table(p, table, join_type, join_condition)

        # ---------------------------------------------------------------------
        # WHERE
        # ---------------------------------------------------------------------
        if where_expression:
            cond = expr.parseString(where_expression)
            if p.where_clause:
                extra = ["AND", "(", cond, ")"]
                p.where_clause.where_expr.extend(extra)
            else:
                # No WHERE as yet
                extra = ["WHERE", "(", cond, ")"]
                p.where_clause.extend(extra)

        if debug:
            log.debug("end dump:\n" + p.dump())
        result = text_from_parsed(p, formatted=formatted)
    if debug:
        log.info("END:\n{}".format(result))
    return result


def unit_tests():
    add_to_select("SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 5",
                  table="t2", column="c")
    add_to_select("", table="t2", column="c")
    add_to_select("SELECT t1.a, t1.b FROM t1",
                  where_expression="t1.col2 < 3")
    add_to_select("SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 5",
                  where_expression="t1.col2 < 3")


if __name__ == '__main__':
    main_only_quicksetup_rootlogger()
    unit_tests()
