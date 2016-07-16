#!/usr/bin/env python
# crate_anon/common/sql.py

import logging

from sqlalchemy import inspect

log = logging.getLogger(__name__)


# =============================================================================
# SQL elements: literals, identifiers
# =============================================================================

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


# =============================================================================
# SQLAlchemy reflection and DDL
# =============================================================================

_print_not_execute = False


def set_print_not_execute(print_not_execute):
    global _print_not_execute
    _print_not_execute = print_not_execute


def format_sql_for_print(sql):
    # Remove blank lines and trailing spaces
    lines = list(filter(None, [x.replace("\t", "    ").rstrip()
                               for x in sql.splitlines()]))
    # Shift all lines left if they're left-padded
    firstleftpos = float('inf')
    for line in lines:
        leftpos = len(line) - len(line.lstrip())
        firstleftpos = min(firstleftpos, leftpos)
    if firstleftpos > 0:
        lines = [x[firstleftpos:] for x in lines]
    return "\n".join(lines)


def sql_fragment_cast_to_int(expr):
    # Conversion to INT:
    # http://stackoverflow.com/questions/2000045
    # http://stackoverflow.com/questions/14719760  # this one
    # http://stackoverflow.com/questions/14692131
    return "CASE WHEN {expr} NOT LIKE '%[^0-9]%' " \
           "THEN CAST({expr} AS INTEGER) ELSE NULL END".format(expr=expr)


def execute(engine, sql):
    log.debug(sql)
    if _print_not_execute:
        print(format_sql_for_print(sql) + "\n;")
        # extra \n in case the SQL ends in a comment
    else:
        engine.execute(sql)


def add_columns(engine, table, name_coltype_dict):
    existing_column_names = get_column_names(engine, table=table,
                                             to_lower=True)
    column_defs = []
    for name, coltype in name_coltype_dict.items():
        if name.lower() not in existing_column_names:
            column_defs.append("{} {}".format(name, coltype))
        else:
            log.debug("Table '{}': column '{}' already exists; not "
                      "adding".format(table.name, name))
    # ANSI SQL: add one column at a time: ALTER TABLE ADD [COLUMN] coldef
    #   - i.e. "COLUMN" optional, one at a time, no parentheses
    #   - http://www.contrib.andrew.cmu.edu/~shadow/sql/sql1992.txt
    # MySQL: ALTER TABLE ADD [COLUMN] (a INT, b VARCHAR(32));
    #   - i.e. "COLUMN" optional, parentheses required for >1, multiple OK
    #   - http://dev.mysql.com/doc/refman/5.7/en/alter-table.html
    # MS SQL Server: ALTER TABLE ADD COLUMN a INT, B VARCHAR(32);
    #   - i.e. no "COLUMN", no parentheses, multiple OK
    #   - https://msdn.microsoft.com/en-us/library/ms190238.aspx
    #   - https://msdn.microsoft.com/en-us/library/ms190273.aspx
    #   - http://stackoverflow.com/questions/2523676
    # SQLAlchemy doesn't provide a shortcut for this.
    for column_def in column_defs:
        log.info("Table '{}': adding column {}".format(
            table.name, column_def))
        execute(engine, """
            ALTER TABLE {tablename} ADD {column_def}
        """.format(tablename=table.name, column_def=column_def))


def drop_columns(engine, table, column_names):
    existing_column_names = get_column_names(engine, table=table,
                                             to_lower=True)
    for name in column_names:
        if name.lower() not in existing_column_names:
            log.debug("Table '{}': column '{}' does not exist; not "
                      "dropping".format(table.name, name))
        else:
            log.info("Table '{}': dropping column '{}'".format(table.name,
                                                               name))
            sql = "ALTER TABLE {t} DROP COLUMN {c}".format(t=table.name,
                                                           c=name)
            # SQL Server:
            #   http://www.techonthenet.com/sql_server/tables/alter_table.php
            # MySQL:
            #   http://dev.mysql.com/doc/refman/5.7/en/alter-table.html
            execute(engine, sql)


def add_indexes(engine, table, indexdictlist):
    existing_index_names = get_index_names(engine, table=table, to_lower=True)
    for idxdefdict in indexdictlist:
        index_name = idxdefdict['index_name']
        column = idxdefdict['column']
        if not isinstance(column, str):
            column = ", ".join(column)  # must be a list
        unique = idxdefdict.get('unique', False)
        if index_name.lower() not in existing_index_names:
            log.info("Table '{}': adding index '{}' on columns '{}'".format(
                table.name, index_name, column))
            execute(engine, """
              CREATE{unique} INDEX {idxname} ON {tablename} ({column})
            """.format(
                unique=" UNIQUE" if unique else "",
                idxname=index_name,
                tablename=table.name,
                column=column,
            ))
        else:
            log.debug("Table '{}': index '{}' already exists; not "
                      "adding".format(table.name, index_name))


def drop_indexes(engine, table, index_names):
    existing_index_names = get_index_names(engine, table=table, to_lower=True)
    for index_name in index_names:
        if index_name.lower() not in existing_index_names:
            log.debug("Table '{}': index '{}' does not exist; not "
                      "dropping".format(table.name, index_name))
        else:
            log.info("Table '{}': dropping index '{}'".format(table.name,
                                                              index_name))
            if engine.dialect.name == 'mysql':
                sql = "ALTER TABLE {t} DROP INDEX {i}".format(t=table.name,
                                                              i=index_name)
            elif engine.dialect.name == 'mssql':
                sql = "DROP INDEX {t}.{i}".format(t=table.name, i=index_name)
            else:
                assert False, "Unknown dialect: {}".format(engine.dialect.name)
            execute(engine, sql)


def get_view_names(engine, to_lower=False, sort=False):
    inspector = inspect(engine)
    view_names = inspector.get_view_names()
    if to_lower:
        view_names = [x.lower() for x in view_names]
    if sort:
        view_names = sorted(view_names, key=lambda x: x.lower())
    return view_names


def get_column_names(engine, tablename=None, table=None, to_lower=False,
                     sort=False):
    """
    Reads columns names afresh from the database (in case metadata is out of
    date.
    """
    assert (table is not None) != bool(tablename), "Need table XOR tablename"
    tablename = tablename or table.name
    inspector = inspect(engine)
    columns = inspector.get_columns(tablename)
    column_names = [x['name'] for x in columns]
    if to_lower:
        column_names = [x.lower() for x in column_names]
    if sort:
        column_names = sorted(column_names, key=lambda x: x.lower())
    return column_names


def get_index_names(engine, tablename=None, table=None, to_lower=False):
    """
    Reads index names from the database.
    """
    # http://docs.sqlalchemy.org/en/latest/core/reflection.html
    assert (table is not None) != bool(tablename), "Need table XOR tablename"
    tablename = tablename or table.name
    inspector = inspect(engine)
    indexes = inspector.get_indexes(tablename)
    index_names = [x['name'] for x in indexes if x['name']]
    # ... at least for SQL Server, there always seems to be a blank one
    # with {'name': None, ...}.
    if to_lower:
        index_names = [x.lower() for x in index_names]
    return index_names


def ensure_columns_present(engine, table=None, tablename=None,
                           column_names=None):
    assert column_names, "Need column_names"
    assert (table is not None) != bool(tablename), "Need table XOR tablename"
    tablename = tablename or table.name
    existing_column_names = get_column_names(engine, tablename=tablename,
                                             to_lower=True)
    for col in column_names:
        if col.lower() not in existing_column_names:
            raise ValueError(
                "Column '{}' missing from table '{}'".format(col, tablename))


def create_view(engine, viewname, select_sql):
    # MySQL has CREATE OR REPLACE VIEW.
    # SQL Server doesn't: http://stackoverflow.com/questions/18534919
    if engine.dialect.name == 'mysql':
        sql = "CREATE OR REPLACE VIEW {viewname} AS {select_sql}".format(
            viewname=viewname,
            select_sql=select_sql,
        )
    else:
        drop_view(engine, viewname, quiet=True)
        sql = "CREATE VIEW {viewname} AS {select_sql}".format(
            viewname=viewname,
            select_sql=select_sql,
        )
    log.info("Creating view: '{}'".format(viewname))
    execute(engine, sql)


def drop_view(engine, viewname, quiet=False):
    # MySQL has DROP VIEW IF EXISTS, but SQL Server only has that from
    # SQL Server 2016 onwards.
    # - https://msdn.microsoft.com/en-us/library/ms173492.aspx
    # - http://dev.mysql.com/doc/refman/5.7/en/drop-view.html
    view_names = get_view_names(engine, to_lower=True)
    if viewname.lower() not in view_names:
        log.debug("View {} does not exist; not dropping".format(viewname))
    else:
        if not quiet:
            log.info("Dropping view: '{}'".format(viewname))
        sql = "DROP VIEW {viewname}".format(viewname=viewname)
        execute(engine, sql)


# =============================================================================
# View-building assistance class
# =============================================================================

class ViewMaker(object):
    def __init__(self, engine, basetable, existing_to_lower=False,
                 rename=None):
        rename = rename or {}
        self.engine = engine
        self.basetable = basetable
        self.select_elements = []
        for colname in get_column_names(engine, tablename=basetable,
                                        to_lower=existing_to_lower):
            if colname in rename:
                rename_to = rename[colname]
                if not rename_to:
                    continue
                as_clause = " AS {}".format(rename_to)
            else:
                as_clause = ""
            self.select_elements.append("{t}.{c}{as_clause}".format(
                t=basetable, c=colname, as_clause=as_clause))
        assert self.select_elements, "Must have some active SELECT elements " \
                                     "from base table"
        self.from_elements = [basetable]
        self.where_elements = []
        self.lookup_table_keyfields = []  # of (table, keyfield(s)) tuples

    def add_select(self, clause):
        self.select_elements.append(clause)

    def add_from(self, clause):
        self.from_elements.append(clause)

    def add_where(self, clause):
        self.where_elements.append(clause)

    def get_sql(self):
        if self.where_elements:
            where = "\n    WHERE {}".format(
                "\n        AND ".join(self.where_elements))
        else:
            where = ""
        return (
            "\n    SELECT {select_elements}"
            "\n    FROM {from_elements}{where}".format(
                select_elements=",\n        ".join(self.select_elements),
                from_elements="\n        ".join(self.from_elements),
                where=where))

    def record_lookup_table_keyfield(self, table, keyfield):
        self.lookup_table_keyfields.append((table, keyfield))

    def record_lookup_table_keyfields(self, table_keyfield_tuples):
        for t, k in table_keyfield_tuples:
            self.record_lookup_table_keyfield(t, k)

    def get_lookup_tables(self):
        return list(set(table for table, keyfield
                        in self.lookup_table_keyfields))

    def get_lookup_table_keyfields(self):
        return list(self.lookup_table_keyfields)
