#!/bin/bash
#
# Script to set up PYTHONPATH and Java CLASSPATH
#
# Author: Rudolf Cardinal
# Copyright (C) 2015-2015 Rudolf Cardinal.
# License: http://www.apache.org/licenses/LICENSE-2.0

warn() {
    # http://stackoverflow.com/questions/5947742/how-to-change-the-output-color-of-echo-in-linux/5947788#5947788
    echo "$(tput setaf 1)$@$(tput sgr0)"
}

add_pythonpath() {
    # http://superuser.com/questions/39751
    if ! [ -d "$1" ]; then
        warn "Not adding $1 to PYTHONPATH (not a directory)"
    elif ! [[ ":$PYTHONPATH:" != *":$1:"* ]]; then
        warn "Not adding $1 to PYTHONPATH (already on PYTHONPATH)"
    else
        export PYTHONPATH="${PYTHONPATH:+"$PYTHONPATH:"}$1"
    fi
}

add_javaclasspath() {
    # doesn't have to be a directory
    if [[ ":$CLASSPATH:" != *":$1:"* ]]; then
        export CLASSPATH="${CLASSPATH:+"$CLASSPATH:"}$1"
    else
        warn "Not adding $1 to CLASSPATH (already on CLASSPATH)"
    fi
}

# Were we called or sourced? Several ways to tell.
# http://stackoverflow.com/questions/6112540/return-an-exit-code-without-closing-shell
[[ x"${BASH_SOURCE[0]}" != x"$0" ]]&&SOURCED=1||SOURCED=0;
# [[ "$0" == "bash" || "$0" == "-bash" ]]&&SOURCED=1||SOURCED=0;
# [[ $PS1 ]]&&SOURCED=1||SOURCED=0;
if (( $SOURCED == 0 )); then
    warn "Execute this as 'source $0' or '. $0' or it will do nothing"
    exit 1
fi

if [ "$CRATE_VIRTUALENV" == "" ]; then
    warn "Please set \$CRATE_VIRTUALENV first, e.g. with:"
    warn "    export CRATE_VIRTUALENV=~/crate_virtualenv"
    return
fi

# Where are we?
THIS_SCRIPT_DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )

add_javaclasspath /usr/share/java/mysql.jar
add_javaclasspath $THIS_SCRIPT_DIR/sqljdbc_4.1/enu/sqljdbc41.jar
echo "CLASSPATH (for Java) is now: $CLASSPATH"

PYTHONBASE=`find "$CRATE_VIRTUALENV/lib" -name "python*" | head -1`
# ... will include virtualenv path
