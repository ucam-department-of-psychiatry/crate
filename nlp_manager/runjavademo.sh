#!/bin/sh

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
BUILDDIR=$DIR/compiled_nlp_classes
GATEDIR=~/GATE_Developer_8.0
GATEJAR="$GATEDIR/bin/gate.jar"
GATELIBJARS="$GATEDIR/lib/*"
APPFILE="$GATEDIR/plugins/ANNIE/ANNIE_with_defaults.gapp"

java -classpath $BUILDDIR:$GATEJAR:$GATELIBJARS CamAnonGatePipeline -g $APPFILE -a Person -a Location -it END -ot END -v -v
