#!/bin/bash
#
# Script to run an instance of mysql-proxy
#
# Author: Rudolf Cardinal
# Copyright (C) 2015-2016 Rudolf Cardinal.
# License: http://www.apache.org/licenses/LICENSE-2.0
#
# The mysql-proxy version must be at least 0.8.5; see
#       http://dev.mysql.com/doc/mysql-proxy/en/
# and downloads are at
#       https://dev.mysql.com/downloads/mysql-proxy/

set -e  # exit on any error

#==============================================================================
# Helper functions
#==============================================================================

succeed()
{
    echo "$@"
    exit 0
}

fail()
{
    echo "$@"
    exit 1
}

fail_missing_param()
{
    fail "Missing $1 parameter in $CONFIGFILE"
}

fail_syntax()
{
    SCRIPTNAME=$(basename "$0")
    fail "Usage: $SCRIPTNAME CONFIGFILE {start|stop|restart}"
}

#==============================================================================
# Configuration
#==============================================================================

read_config()
{
    #--------------------------------------------------------------------------
    # Read
    #--------------------------------------------------------------------------
    if ! [ -f "$CONFIGFILE" ]; then
        fail "Not a file: $CONFIGFILE"
    fi
    echo "Reading $CONFIGFILE"
    source "$CONFIGFILE"  # NB some danger; executes contents unconditionally!

    # Validation
    if [ -z "$MYSQL_HOST" ]; then
        fail_missing_param MYSQL_HOST
    fi
    if [ -z "$MYSQL_PORT" ]; then
        fail_missing_param MYSQL_PORT
    fi
    # OK to have a missing PROXY_IPADDR
    if [ -z "$PROXY_PORT" ]; then
        fail_missing_param PROXY_PORT
    fi
    if [ -z "$MYSQLPROXY" ]; then
        fail_missing_param MYSQLPROXY
    fi
    if [ -z "$LUA_SCRIPT" ]; then
        fail_missing_param LUA_SCRIPT
    fi
    if [ -z "$LOGDIR" ]; then
        fail_missing_param LOGDIR
    fi
    if [ -z "$STDOUT_PLUS_LOG" ]; then
        fail_missing_param STDOUT_PLUS_LOG
    fi
    if [ -z "$STDERR_PLUS_LOG" ]; then
        fail_missing_param STDERR_PLUS_LOG
    fi
    if [ -z "$LOGLEVEL" ]; then
        fail_missing_param LOGLEVEL
    fi
    if [ -z "$DAEMON" ]; then
        fail_missing_param DAEMON
    fi
    if ${DAEMON} && [ -z "$PID_FILE" ]; then
        fail_missing_param PID_FILE
    fi

    #--------------------------------------------------------------------------
    # Further processing
    #--------------------------------------------------------------------------
    DATE=$(date +"%Y_%m_%d")
    OUTLOG="$LOGDIR/audit_${DATE}.log"  # stdout; audit messages themselves
    ERRLOG="$LOGDIR/mysqlproxy_${DATE}.log"  # stderr; messages from mysql-proxy

    # NOTE: the --proxy-read-only-backend-addresses option isn't something that
    # magically creates read-only access to the database. (Use an appropriately
    # configured user for that.) It's designed for a proxy Lua script to send
    # read-only (SELECT) queries to read-only slave servers, and modification
    # queries to a master server, for a load-balancing system. See
    # http://jan.kneschke.de/2007/8/1/mysql-proxy-learns-r-w-splitting/
    # https://answers.launchpad.net/mysql-proxy/+question/68398
    COMMON_OPTIONS="
        --log-level=$LOGLEVEL
        --plugins=proxy
        --proxy-address=$PROXY_IPADDR:$PROXY_PORT
        --proxy-backend-addresses=$MYSQL_HOST:$MYSQL_PORT
        --proxy-lua-script=$LUA_SCRIPT
        --verbose-shutdown
    "
    if ${DAEMON} ; then
        DAEMON_OPTIONS="
            --daemon
            --keepalive
            --pid-file=$PID_FILE
        "
        STDOUT_PLUS_LOG=false  # silly for it to be true
        STDERR_PLUS_LOG=false  # silly for it to be true
    else
        DAEMON_OPTIONS=
    fi
    CMD="$MYSQLPROXY $DAEMON_OPTIONS $COMMON_OPTIONS"
}

#==============================================================================
# Constants
#==============================================================================

WAIT_TIME_S=3

#==============================================================================
# Execution
#==============================================================================

if [ $# -ne 2 ]; then
    fail_syntax
fi
CONFIGFILE="$1"
case "$2" in
    start)
        read_config
        mkdir -pv "$LOGDIR"
        echo "Launching mysql-proxy with auditing script:"
        echo ${CMD}
        echo "... appending stdout (audit information) to $OUTLOG"
        if ${STDOUT_PLUS_LOG} ; then
            echo "... keeping stdout as well"
        fi
        echo "... appending stderr (mysql-proxy log) to $ERRLOG"
        if ${STDERR_PLUS_LOG}; then
            echo "... keeping stderr as well"
        fi
        # We're not using mysql-proxy's --log-file option; we'll do it by hand.
        # http://stackoverflow.com/questions/692000/how-do-i-write-stderr-to-a-file-while-using-tee-with-a-pipe
        # http://mywiki.wooledge.org/BashGuide/InputAndOutput
        if ${STDOUT_PLUS_LOG} ; then
            if ${STDERR_PLUS_LOG}; then
                # tee stdout; tee stderr
                ${CMD} > >(tee --append ${OUTLOG}) 2> >(tee --append ${ERRLOG} >&2)
            else
                # tee stdout; file stderr
                ${CMD} > >(tee --append ${OUTLOG}) 2>> ${ERRLOG}
            fi
        else
            if ${STDERR_PLUS_LOG}; then
                # file stdout; tee stderr
                ${CMD} >> ${OUTLOG} 2> >(tee --append ${ERRLOG} >&2)
            else
                # file stdout; file stderr
                ${CMD} >> ${OUTLOG} 2>> ${ERRLOG}
            fi
        fi
        chmod -v 600 ${OUTLOG}
        chmod -v 600 ${ERRLOG}
        if ${DAEMON} ; then
            PID=$(cat "$PID_FILE")
            echo "Running in daemon mode as process $PID."
            echo
        fi
        ;;

    stop)
        read_config
        if ! ${DAEMON} ; then
            succeed "No need to stop; not running in daemon mode."
        fi
        if ! [ -f "$PID_FILE" ]; then
            succeed "No need to stop; no file $PID_FILE"
        fi
        PID=$(cat "$PID_FILE")
        if [ -z "$PID" ]; then
            fail "Blank process ID"
        fi
        echo "Stopping auditor on process $PID... If this fails, kill it manually (using ps and kill) and remove $PID_FILE"
        kill ${PID}
        rm -f "$PID_FILE"
        echo "Stopped."
        ;;

    restart)
        "$0" "$CONFIGFILE" stop
        echo "Waiting $WAIT_TIME_S s..."
        sleep ${WAIT_TIME_S}
        "$0" "$CONFIGFILE" start
        ;;

    *)
        fail_syntax
        ;;
esac
