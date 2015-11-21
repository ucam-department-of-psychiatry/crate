#!/bin/bash
#
# Script to check all Python code using pyflakes

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
SEARCHDIR=`readlink -f "$DIR/.."`  # gets absolute path

find $SEARCHDIR \
    -type f \
    -name "*.py" \
    ! -path "*/migrations/*" \
    -exec flake8 {} \;

#find $SEARCHDIR \
#    -type f \
#    -name "*.py" \
#    ! -path "*/migrations/*" \
#    -exec awk '!/#!\/usr\/bin\/env python3/ && NR < 2 {print FILENAME " - missing start: #!/usr/bin/env python3"; nextfile}' {} \;
