#!/usr/bin/env python
#
# Script to check the memory usage (approximately) of a running MySQL instance.
#
# From: https://dev.mysql.com/doc/refman/5.0/en/memory-use.html
# - However, innodb_additional_mem_pool_size deprecated in 5.6.3 and removed in
#   5.7.4; http://dev.mysql.com/doc/refman/5.7/en/innodb-parameters.html

import subprocess


def get_mysql_vars(user="root"):
    print("Connecting to MySQL with user: {}".format(user))
    process = subprocess.Popen(
        [
            "mysql",
            "-e", "show variables; show status",
            "-u", user, "-p"
        ],
        stdout=subprocess.PIPE)
    out, err = process.communicate()
    lines = out.decode("utf8").splitlines()
    mysqlvars = {}
    for line in lines:
        var, val = line.split("\t")
        mysqlvars[var] = val
    return mysqlvars


def print_sep():
    print("+------------------------------------------+--------------------+")


def print_val_mb(varname, valstr):
    try:
        mb = "{:15.3f}".format(int(valstr) / (1024 * 1024))
    except (TypeError, ValueError):
        mb = " " * 14 + "?"
    print("| {varname:40s} | {mb} MB |".format(
        varname=varname,
        mb=mb,
    ))


def print_val_int(varname, valstr):
    try:
        x = "{:18d}".format(int(valstr))
    except (TypeError, ValueError):
        x = " " * 14 + "?"
    print("| {varname:40s} | {x} |".format(
        varname=varname,
        x=x,
    ))


def print_var_mb(vardict, varname):
    valstr = vardict.get(varname, None)
    print_val_mb(varname, valstr)


def main():
    vardict = get_mysql_vars()
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

    print_sep()
    print_var_mb(vardict, "key_buffer_size")
    print_var_mb(vardict, "query_cache_size")
    print_var_mb(vardict, "innodb_buffer_pool_size")
    # print_var_mb(vardict, "innodb_additional_mem_pool_size")
    print_var_mb(vardict, "innodb_log_buffer_size")
    print_sep()
    print_val_mb("BASE MEMORY", base_mem)
    print_sep()
    print_var_mb(vardict, "sort_buffer_size")
    print_var_mb(vardict, "read_buffer_size")
    print_var_mb(vardict, "read_rnd_buffer_size")
    print_var_mb(vardict, "join_buffer_size")
    print_var_mb(vardict, "thread_stack")
    print_var_mb(vardict, "binlog_cache_size")
    print_var_mb(vardict, "tmp_table_size")
    print_sep()
    print_val_mb("MEMORY PER CONNECTION", mem_per_conn)
    print_sep()
    print_val_int("Max_used_connections", max_used_conn)
    print_val_int("max_connections", max_conn)
    print_sep()
    print_val_mb("TOTAL (MIN)", mem_total_min)
    print_val_mb("TOTAL (MAX)", mem_total_max)
    print_sep()


if __name__ == '__main__':
    main()
