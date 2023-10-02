#!/bin/bash

set -e

# CRATE_WAIT_FOR is in the form:
# host1:port1 host2:port2 host3:port3 etc
for hostandport in ${CRATE_WAIT_FOR:-}
do
    host=${hostandport%:*}
    port=${hostandport#"$host"}
    port=${port#:}

    wait-for-it --host=$host --port=$port --timeout=0 --strict
done

source /crate/venv/bin/activate
exec $@
