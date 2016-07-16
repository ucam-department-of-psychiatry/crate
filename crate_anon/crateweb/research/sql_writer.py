#!/usr/bin/env python
# crate_anon/crateweb/research/sql_writer.py

import logging

import sqlparse

from crate_anon.common.logsupport import main_only_quicksetup_rootlogger
from crate_anon.common.sql import (
    combine_db_table,
    split_db_table,
)
from crate_anon.common.sql_grammar_mysql import (
    column_spec,
    expr,
    # flatten,
    join_constraint,
    join_op,
    select_statement,
    table_spec,
    text_from_parsed,
)
from crate_anon.crateweb.research.models import (
    get_schema_trid_field,
    get_schema_rid_field,
    get_schema_rid_family,
    get_schema_mrid_table,
    get_schema_mrid_field,
)

log = logging.getLogger(__name__)


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


def parser_add_from_tables(parsed, joininfo):
    """
    joininfo: list of dictionaries with keys:
        table, join_type, join_condition
    Presupposes at least one table already in the FROM clause.
    """
    # log.critical(parsed.dump())
    existing_tables = parsed.join_source.from_tables.asList()
    # log.critical("existing tables: {}".format(existing_tables))
    # log.critical("adding table: {}".format(table))
    for infodict in joininfo:
        table = infodict['table']
        join_type = infodict.get('join_type', 'INNER JOIN')
        join_condition = infodict.get('join_condition', None)
        if table in existing_tables:  # already there
            # log.critical("field already present")
            continue
        parsed_join = join_op.parseString(join_type)[0]  # e.g. INNER JOIN
        parsed_table = table_spec.parseString(table)[0]
        extrabits = [parsed_join, parsed_table]
        if join_condition:  # e.g. ON x = y
            extrabits.append(join_constraint.parseString(join_condition)[0])
        parsed.join_source.extend(extrabits)
    # log.critical(parsed.dump())
    return parsed


def get_first_from_db_table(parsed, match_db=False, match_db_table=False,
                            db=None, table=None):
    existing_tables = parsed.join_source.from_tables.asList()
    for t in existing_tables:
        db_component, table_component = split_db_table(t)
        if ((not match_db and not match_db_table) or
                (match_db_table and db_component == db and
                 table_component == table) or
                (match_db and db_component == db)):
            return db_component, table_component
    return None, None


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


def get_join_info(parsed, joindb, jointable, magic_join=False,
                  nonmagic_join_type="INNER JOIN",
                  nonmagic_join_condition=None):
    join_db_table = combine_db_table(joindb, jointable)
    first_db, first_table = get_first_from_db_table(parsed)
    db_match_db, db_match_table = get_first_from_db_table(
        parsed, match_db=True, db=joindb)
    _, table_match_table = get_first_from_db_table(
        parsed, match_db_table=True, db=joindb, table=jointable)

    if not first_table:
        # No tables in query yet.
        # This should not happen; this function is to help with adding
        # new FROM tables to existing FROM clauses.
        log.warning("get_join_info: no tables in query")
        return []
    if table_match_table:
        # This table is already in the query. No JOIN should be required.
        # log.critical("get_join_info: same table already in query")
        return []
    if not magic_join:
        # log.critical("get_join_info: non-magic join")
        return [{
            'join_type': nonmagic_join_type,
            'table': join_db_table,
            'join_condition': nonmagic_join_condition,
        }]
    if db_match_table:
        # Another table from the same database is present. Link on the
        # TRID field.
        # log.critical("get_join_info: joining to another table in same DB")
        return [{
            'join_type': 'INNER JOIN',
            'table': join_db_table,
            'join_condition': (
                "ON {new}.{trid} = {existing}.{trid}".format(
                    new=join_db_table,
                    existing=combine_db_table(db_match_db, db_match_table),
                    trid=get_schema_trid_field(db_match_db),
                )
            ),
        }]
    # OK. So now we're building a cross-database join.
    existing_family = get_schema_rid_family(first_db)
    new_family = get_schema_rid_family(joindb)
    # log.critical("existing_family={}, new_family={}".format(
    #     existing_family, new_family))
    if existing_family and existing_family == new_family:
        # log.critical("get_join_info: new DB, same RID family")
        return [{
            'join_type': 'INNER JOIN',
            'table': join_db_table,
            'join_condition': (
                "ON {new}.{newrid} = {existing}.{exrid}".format(
                    new=join_db_table,
                    newrid=get_schema_rid_field(joindb),
                    existing=combine_db_table(first_db, first_table),
                    exrid=get_schema_rid_field(first_db),
                )
            ),
        }]
    # If we get here, we have to do a complicated join via the MRID.
    # log.critical("get_join_info: new DB, different RID family, using MRID")
    existing_mrid_table = get_schema_mrid_table(first_db)
    existing_mrid_field = get_schema_mrid_field(first_db)
    new_mrid_table = get_schema_mrid_table(joindb)
    new_mrid_field = get_schema_mrid_field(joindb)

    existing_mrid_table_in_query = bool(get_first_from_db_table(
        parsed, match_db_table=True,
        db=first_db, table=existing_mrid_table)[1])

    joins = []
    if not existing_mrid_table_in_query:
        joins.append({
            'join_type': 'INNER JOIN',
            'table': combine_db_table(first_db, existing_mrid_table),
            'join_condition': (
                "ON {m1}.{trid1} = {t1}.{trid1}".format(
                    m1=combine_db_table(first_db, existing_mrid_table),
                    t1=combine_db_table(first_db, first_table),
                    trid1=get_schema_trid_field(first_db),
                )
            ),
        })
    joins.append({
        'join_type': 'INNER JOIN',
        'table': combine_db_table(joindb, new_mrid_table),
        'join_condition': (
            "ON {m2}.{mrid2} = {m1}.{mrid1}".format(
                m2=combine_db_table(joindb, new_mrid_table),
                mrid2=new_mrid_field,
                m1=combine_db_table(first_db, existing_mrid_table),
                mrid1=existing_mrid_field,
            )
        ),
    })
    if jointable != new_mrid_table:
        joins.append({
            'join_type': 'INNER JOIN',
            'table': join_db_table,
            'join_condition': (
                "ON {t2}.{trid2} = {m2}.{trid2}".format(
                    t2=combine_db_table(joindb, jointable),
                    m2=combine_db_table(joindb, new_mrid_table),
                    trid2=get_schema_trid_field(joindb),
                )
            ),
        })
    return joins


def add_to_select(sql,
                  # For SELECT:
                  select_db=None, select_table=None, select_column=None,
                  # For WHERE:
                  where_expression=None, where_type="AND", 
                  where_db=None, where_table=None,
                  bracket_where=False,
                  # For either, for JOIN:
                  magic_join=True,
                  inner_join_to_first_on_keyfield=None,  # overrides others
                  join_type="NATURAL JOIN", join_condition=None,
                  # General:
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
    isn't yet in the FROM clause, this will be added as well.
    """

    if debug:
        log.info("START: {}".format(sql))
        log.debug("table: {}".format(select_table))
        log.debug("column: {}".format(select_column))
        log.debug("inner_join_to_first_on_keyfield: {}".format(
            inner_join_to_first_on_keyfield))
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
        if select_column and select_table:
            db_table = combine_db_table(select_db, select_table)
            colspec = "{}.{}".format(db_table, select_column)
            result = sqlparse.format(
                "SELECT {} FROM {}".format(colspec, db_table),
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
        # add SELECT... +/- FROM
        # ---------------------------------------------------------------------
        if select_column and select_table:
            colspec = "{}.{}".format(
                combine_db_table(select_db, select_table),
                select_column)
            p = parser_add_result_column(p, colspec)
            p = parser_add_from_tables(
                p, get_join_info(p, select_db, select_table,
                                 magic_join=magic_join))

        # ---------------------------------------------------------------------
        # add WHERE... +/- FROM
        # ---------------------------------------------------------------------
        if where_expression:
            cond = expr.parseString(where_expression)
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
                    p, get_join_info(p, where_db, where_table,
                                     magic_join=magic_join))

        if debug and debug_verbose:
            log.debug("end dump:\n" + p.dump())
        result = text_from_parsed(p, formatted=formatted)
    if debug:
        log.info("END:\n{}".format(result))
    return result


def unit_tests():
    add_to_select("SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 5",
                  select_table="t2", select_column="c")
    add_to_select("SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 5",
                  select_table="t1", select_column="a")
    add_to_select("", select_table="t2", select_column="c")
    add_to_select("SELECT t1.a, t1.b FROM t1",
                  where_expression="t1.col2 < 3")
    add_to_select("SELECT t1.a, t1.b FROM t1 WHERE t1.col1 > 5",
                  where_expression="t1.col2 < 3")


if __name__ == '__main__':
    main_only_quicksetup_rootlogger()
    unit_tests()
