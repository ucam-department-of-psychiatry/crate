#!/bin/bash

THISDIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
DJANGO_ROOT=`readlink -m $THISDIR/../crateweb`
cd "$DJANGO_ROOT"
# FILES_TO_MONITOR=$(find . -name "*.py" -type f | awk '{sub("\\./",""); gsub("/", "."); sub(".py",""); print}' ORS=',' | sed 's/.$//')
# echo "Monitoring: $FILES_TO_MONITOR"
celery -A consent worker \
    --loglevel=debug
    # --autoreload \
    # --include=$FILES_TO_MONITOR

# http://stackoverflow.com/questions/21666229/celery-auto-reload-on-any-changes

# HOWEVER: autoreload appears (a) not to work, and (b) to prevent processing!