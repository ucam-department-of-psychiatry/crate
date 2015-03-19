#!/bin/bash
# Note: $! is the process ID of last process launched in background

# =============================================================================
# Define our configuration
# =============================================================================

usage()
{
    cat << EOF
usage: $0 [-i | -f] OPTIONS

Run the natural language processing (NLP) manager in parallel.

OPTIONS:
    -h              Show this message
    -v              Verbose (repeat for extra verbosity)
    -s NLPMANAGER   Specify the path to the NLP manager script.
    -c CONFIG       Specify the config file.
    -n NLPNAME      Specify the NLP processing name (from the config file).
    -p PYTHONPATH   Set the PYTHONPATH before calling.
    -i              Incremental mode (not full). } MUST SPECIFY ONE.
    -f              Full mode (not incremental). }
    -n NPROC        Number of processes (1 for single-tasking).
EOF
}

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
CPUCOUNT=`grep -c ^processor /proc/cpuinfo`
CONFIG=$DIR/working_nlp_config.ini
NPROCESSES_MAIN=$CPUCOUNT
NPROCESSES_INDEX=$CPUCOUNT
NLPMANAGER=$DIR/nlp_manager.py
NLPNAME=name_location_nlp
export PYTHONPATH=$PYTHONPATH:$DIR/pythonlib
VERBOSITY=
METHOD_INCREMENTAL=false
METHOD_FULL=false
while getopts “hvs:p:ifn:” OPTION; do
    case $OPTION in
        h)
            usage
            exit
            ;;
        v)
            VERBOSITY="$VERBOSITY -v"
            ;;
        s)
            NLPMANAGER=$OPTARG
            ;;
        c)
            CONFIG=$OPTARG
            ;;
        n)
            NLPNAME=$OPTARG
            ;;
        p)
            PYTHONPATH=$OPTARG
            ;;
        i)
            METHOD_INCREMENTAL=true
            ;;
        f)
            METHOD_FULL=true
            ;;
        n)
            NPROCESSES_MAIN=$OPTARG
            NPROCESSES_INDEX=$OPTARG
            ;;
        ?)
            usage
            exit
            ;;
    esac
done

if ($METHOD_INCREMENTAL && $METHOD_FULL) || (! ($METHOD_INCREMENTAL || $METHOD_FULL)); then
    echo "Specify one of: -i, -f."
    usage
    exit 1
fi
INCREMENTAL=
if $METHOD_INCREMENTAL; then
    INCREMENTAL=--incremental
fi

export PYTHONPATH=$PYTHONPATH

COMMON_OPTIONS="$INCREMENTAL $VERBOSITY"

# =============================================================================
# Setup
# =============================================================================

# Kill all subprocesses if this script is aborted
trap 'kill -HUP 0' EXIT

# Tell the user if something goes wrong
function fail() {
    >&2 echo "PROCESS FAILED; EXITING ALL"
    exit 1
}

# Start.
time_start=$(date +"%s")

# =============================================================================
# Clean/build the tables. Only run one copy of this!
# =============================================================================
$NLPMANAGER $CONFIG $NLPNAME --dropremake --processcluster="STRUCTURE" \
    $COMMON_OPTIONS || fail

# =============================================================================
# Now run lots of things simultaneously:
# =============================================================================
pids=()
for ((i=0; i < $NPROCESSES_MAIN; i++)); do
    $NLPMANAGER $CONFIG $NLPNAME --nlp --processcluster="NLP" \
        --nprocesses=$NPROCESSES_MAIN --process=$i \
        $COMMON_OPTIONS &
    pids+=($!)
done

# Wait for them all to finish
for pid in ${pids[*]}; do
    wait $pid || fail
done

time_middle=$(date +"%s")

# =============================================================================
# Now do the indexing, if nothing else failed. (Always fastest to index last.)
# =============================================================================
pids=()
for ((i=0; i < $NPROCESSES_INDEX ; i++)); do
    $NLPMANAGER $CONFIG $NLPNAME --index --processcluster="INDEX" \
        --nprocesses=$NPROCESSES_INDEX --process=$i \
        $COMMON_OPTIONS &
    pids+=($!)
done
for pid in ${pids[*]}; do
    wait $pid || fail
done

# =============================================================================
# Finished.
# =============================================================================
time_end=$(date +"%s")
main_dur=$(($time_middle - $time_start))
index_dur=$(($time_end - $time_middle))
total_dur=$(($time_end - $time_start))
echo "Time taken: main $main_dur s, indexing $index_dur s, total $total_dur s"
