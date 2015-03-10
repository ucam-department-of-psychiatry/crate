#!/bin/bash
# http://stackoverflow.com/questions/356100
# http://stackoverflow.com/questions/1644856
# http://stackoverflow.com/questions/8903239
# http://stackoverflow.com/questions/1951506
# Note: $! is the process ID of last process launched in background
# http://stackoverflow.com/questions/59895

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
    -s ANONYMISER   Specify the path to the anonymiser script.
    -c CONFIG       Specify the config file.
    -p PYTHONPATH   Set the PYTHONPATH before calling.
    -i              Incremental mode (not full). } MUST SPECIFY ONE.
    -f              Full mode (not incremental). }
    -n NPROC        Number of processes (1 for single-tasking).
EOF
}

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
CPUCOUNT=`grep -c ^processor /proc/cpuinfo`
CONFIG=$DIR/working_anon_config.ini
NPROCESSES_PATIENT=$CPUCOUNT
NPROCESSES_INDEX=$CPUCOUNT
NPROCESSES_NONPATIENT=$CPUCOUNT
ANONYMISER=$DIR/anonymise.py
PYTHONPATH=$PYTHONPATH:/srv/www/pythonlib
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
            ANONYMISER=$OPTARG
            ;;
        c)
            CONFIG=$OPTARG
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
            NPROCESSES_PATIENT=$OPTARG
            NPROCESSES_INDEX=$OPTARG
            NPROCESSES_NONPATIENT=$OPTARG
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

COMMON_OPTIONS="--threads=1 $INCREMENTAL $VERBOSITY"

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
$ANONYMISER $CONFIG --dropremake --processcluster="STRUCTURE" \
    $COMMON_OPTIONS || fail

# =============================================================================
# Now run lots of things simultaneously:
# =============================================================================
# (a) patient tables
pids=()
for ((i=0; i < $NPROCESSES_PATIENT; i++)); do
    $ANONYMISER $CONFIG --patienttables --processcluster="PATIENT" \
        --nprocesses=$NPROCESSES_PATIENT --process=$i \
        $COMMON_OPTIONS &
    pids+=($!)
done
# (b) non-patient tables
for ((i=0; i < $NPROCESSES_NONPATIENT; i++)); do
    $ANONYMISER $CONFIG --nonpatienttables --processcluster="NON-PATIENT" \
        --nprocesses=$NPROCESSES_NONPATIENT --process=$i \
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
    $ANONYMISER $CONFIG --index --processcluster="INDEX" \
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
