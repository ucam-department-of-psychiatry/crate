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
    vars = {}
    for line in lines:
        var, val = line.split("\t")
        vars[var] = val
    return vars


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
    MAX_CONN = int(vardict["max_connections"])
    MAX_USED_CONN = int(vardict["Max_used_connections"])
    BASE_MEM = (
        int(vardict["key_buffer_size"]) +
        int(vardict["query_cache_size"]) +
        int(vardict["innodb_buffer_pool_size"]) +
        # int(vardict["innodb_additional_mem_pool_size"]) +
        int(vardict["innodb_log_buffer_size"])
    )
    MEM_PER_CONN = (
        int(vardict["read_buffer_size"]) +
        int(vardict["read_rnd_buffer_size"]) +
        int(vardict["sort_buffer_size"]) +
        int(vardict["join_buffer_size"]) +
        int(vardict["binlog_cache_size"]) +
        int(vardict["thread_stack"]) +
        int(vardict["tmp_table_size"])
    )
    MEM_TOTAL_MIN = BASE_MEM + MEM_PER_CONN * MAX_USED_CONN
    MEM_TOTAL_MAX = BASE_MEM + MEM_PER_CONN * MAX_CONN

    print_sep()
    print_var_mb(vardict, "key_buffer_size")
    print_var_mb(vardict, "query_cache_size")
    print_var_mb(vardict, "innodb_buffer_pool_size")
    # print_var_mb(vardict, "innodb_additional_mem_pool_size")
    print_var_mb(vardict, "innodb_log_buffer_size")
    print_sep()
    print_val_mb("BASE MEMORY", BASE_MEM)
    print_sep()
    print_var_mb(vardict, "sort_buffer_size")
    print_var_mb(vardict, "read_buffer_size")
    print_var_mb(vardict, "read_rnd_buffer_size")
    print_var_mb(vardict, "join_buffer_size")
    print_var_mb(vardict, "thread_stack")
    print_var_mb(vardict, "binlog_cache_size")
    print_var_mb(vardict, "tmp_table_size")
    print_sep()
    print_val_mb("MEMORY PER CONNECTION", MEM_PER_CONN)
    print_sep()
    print_val_int("Max_used_connections", MAX_USED_CONN)
    print_val_int("max_connections", MAX_CONN)
    print_sep()
    print_val_mb("TOTAL (MIN)", MEM_TOTAL_MIN)
    print_val_mb("TOTAL (MAX)", MEM_TOTAL_MAX)
    print_sep()


if __name__ == '__main__':
    main()
