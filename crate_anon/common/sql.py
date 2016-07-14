#!/usr/bin/env python
# crate_anon/common/sql.py


def sql_string_literal(text):
    return "'" + text.replace("'", "''") + "'"


def sql_date_literal(dt):
    return dt.strftime("'%Y-%m-%d'")


def sql_datetime_literal(dt, subsecond=False):
    fmt = "'%Y-%m-%dT%H:%M:%S{}'".format(".%f" if subsecond else "")
    return dt.strftime(fmt)


def combine_db_table(db, table):
    if db:
        return "{}.{}".format(db, table)
    else:
        return table


def split_db_table(dbtable):
    components = dbtable.split('.')
    if len(components) == 2:  # db.table
        return components[0], components[1]
    elif len(components) == 1:  # table
        return None, components[0]
    else:
        raise ValueError("Bad dbtable: {}".format(dbtable))
