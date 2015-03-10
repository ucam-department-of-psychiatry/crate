#!/bin/sh
DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
GATEDIR=~/GATE_Developer_8.0
java -classpath $DIR/test_nlp:$GATEDIR/bin/gate.jar:$GATEDIR/lib/* \
    CamAnonGatePipeline \
    -g $GATEDIR/plugins/ANNIE/ANNIE_with_defaults.gapp \
    -a Person -a Location -it END -ot END -v -v
