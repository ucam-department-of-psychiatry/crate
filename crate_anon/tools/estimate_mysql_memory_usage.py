#!/usr/bin/env python
#
# Script to check the memory usage (approximately) of a running MySQL instance.
#
# From: https://dev.mysql.com/doc/refman/5.0/en/memory-use.html
# - However, innodb_additional_mem_pool_size deprecated in 5.6.3 and removed in
#   5.7.4; http://dev.mysql.com/doc/refman/5.7/en/innodb-parameters.html

import argparse
import subprocess

import prettytable


MYSQL_DEFAULT_PORT = 3306
MYSQL_DEFAULT_USER = 'root'
UNITS_MB = 'Mb'


def get_mysql_vars(host, port, user):
    cmdargs = [
        "mysql",
        "-h", host,
        "-P", str(port),
        "-e", "SHOW VARIABLES; SHOW STATUS",
        "-u", user,
        "-p"  # prompt for password
    ]
    print("Connecting to MySQL with user: {}".format(user))
    print(cmdargs)
    process = subprocess.Popen(cmdargs, stdout=subprocess.PIPE)
    out, err = process.communicate()
    lines = out.decode("utf8").splitlines()
    mysqlvars = {}
    for line in lines:
        var, val = line.split("\t")
        mysqlvars[var] = val
    return mysqlvars


def val_mb(valstr):
    try:
        return "{:.3f}".format(int(valstr) / (1024 * 1024))
    except (TypeError, ValueError):
        return '?'


def val_int(valstr):
    return str(valstr) + " " * 4


def add_var_mb(table, vardict, varname):
    valstr = vardict.get(varname, None)
    table.add_row([varname, val_mb(valstr), UNITS_MB])


def add_blank_row(table):
    table.add_row([''] * 3)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--host", default="127.0.0.1",
        help="MySQL server/host (prefer '127.0.0.1' to 'localhost')")
    parser.add_argument(
        "--port", type=int, default=MYSQL_DEFAULT_PORT,
        help="MySQL port (default={})".format(MYSQL_DEFAULT_PORT))
    parser.add_argument(
        "--user", default=MYSQL_DEFAULT_USER,
        help="MySQL user (default={})".format(MYSQL_DEFAULT_USER))
    args = parser.parse_args()

    vardict = get_mysql_vars(
        host=args.host,
        port=args.port,
        user=args.user,
    )
    max_conn = int(vardict["max_connections"])
    max_used_conn = int(vardict["Max_used_connections"])
    base_mem = (
        int(vardict["key_buffer_size"]) +
        int(vardict["query_cache_size"]) +
        int(vardict["innodb_buffer_pool_size"]) +
        # int(vardict["innodb_additional_mem_pool_size"]) +
        int(vardict["innodb_log_buffer_size"])
    )
    mem_per_conn = (
        int(vardict["read_buffer_size"]) +
        int(vardict["read_rnd_buffer_size"]) +
        int(vardict["sort_buffer_size"]) +
        int(vardict["join_buffer_size"]) +
        int(vardict["binlog_cache_size"]) +
        int(vardict["thread_stack"]) +
        int(vardict["tmp_table_size"])
    )
    mem_total_min = base_mem + mem_per_conn * max_used_conn
    mem_total_max = base_mem + mem_per_conn * max_conn

    table = prettytable.PrettyTable(["Variable", "Value", "Units"])
    table.align["Variable"] = "l"
    table.align["Value"] = "r"
    table.align["Units"] = "l"

    add_var_mb(table, vardict, "key_buffer_size")
    add_var_mb(table, vardict, "query_cache_size")
    add_var_mb(table, vardict, "innodb_buffer_pool_size")
    # print_var_mb(table, vardict, "innodb_additional_mem_pool_size")
    add_var_mb(table, vardict, "innodb_log_buffer_size")
    add_blank_row(table)
    table.add_row(["BASE MEMORY", val_mb(base_mem), UNITS_MB])
    add_blank_row(table)
    add_var_mb(table, vardict, "sort_buffer_size")
    add_var_mb(table, vardict, "read_buffer_size")
    add_var_mb(table, vardict, "read_rnd_buffer_size")
    add_var_mb(table, vardict, "join_buffer_size")
    add_var_mb(table, vardict, "thread_stack")
    add_var_mb(table, vardict, "binlog_cache_size")
    add_var_mb(table, vardict, "tmp_table_size")
    add_blank_row(table)
    table.add_row(["MEMORY PER CONNECTION", val_mb(mem_per_conn), UNITS_MB])
    add_blank_row(table)
    table.add_row(["Max_used_connections", val_int(max_used_conn), ''])
    table.add_row(["max_connections", val_int(max_conn), ''])
    add_blank_row(table)
    table.add_row(["TOTAL (MIN)", val_mb(mem_total_min), UNITS_MB])
    table.add_row(["TOTAL (MAX)", val_mb(mem_total_max), UNITS_MB])

    print(table.get_string())


if __name__ == '__main__':
    main()
