#!/bin/bash
# http://stackoverflow.com/questions/4824590/propagate-all-arguments-in-a-bash-shell-script

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
export PYTHONPATH=$PYTHONPATH:$DIR/pythonlib
$DIR/makedata.py "$@"
