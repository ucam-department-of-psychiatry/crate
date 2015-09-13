#!/bin/bash
#
# Script to set up PYTHONPATH and Java CLASSPATH
#
# Author: Rudolf Cardinal
# Copyright (C) 2015-2015 Rudolf Cardinal.
# License: http://www.apache.org/licenses/LICENSE-2.0

add_pythonpath() {
    # http://superuser.com/questions/39751
    if [ -d "$1" ] && [[ ":$PYTHONPATH:" != *":$1:"* ]]; then
        export PYTHONPATH="${PYTHONPATH:+"$PYTHONPATH:"}$1"
    fi
}

add_javaclasspath() {
    # doesn't have to be a directory
    if [[ ":$CLASSPATH:" != *":$1:"* ]]; then
        export CLASSPATH="${CLASSPATH:+"$CLASSPATH:"}$1"
    fi
}

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )

if [ "$0" != "bash" ] && [ "$0" != "-bash" ]; then
    echo "Execute this as 'source $0' or '. $0' or it will do nothing"
    exit 1
fi

add_pythonpath $DIR
#add_pythonpath $DIR/pythonlib
#add_pythonpath $DIR/anon_modules
echo "New PYTHONPATH should be: $PYTHONPATH"

add_javaclasspath /usr/share/java/mysql.jar
add_javaclasspath $DIR/sqljdbc_4.1/enu/sqljdbc41.jar
echo "New (Java) CLASSPATH should be: $CLASSPATH"
