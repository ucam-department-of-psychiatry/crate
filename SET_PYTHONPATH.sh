#!/bin/bash

pythonpathadd() {
    # http://superuser.com/questions/39751
    if [ -d "$1" ] && [[ ":$PYTHONPATH:" != *":$1:"* ]]; then
        export PYTHONPATH="${PYTHONPATH:+"$PYTHONPATH:"}$1"
    fi
}

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )

if [ "$0" != "bash" ]; then
    echo "Execute this as 'source $0' or '. $0' or it will do nothing"
    exit 1
fi

pythonpathadd $DIR/pythonlib
pythonpathadd $DIR/anon_modules
echo "New PYTHONPATH should be: $PYTHONPATH"
