#!/bin/bash

DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
BUILDDIR=$DIR/test_nlp
export GATEDIR=~/GATE_Developer_8.0
export GATEJAR="$GATEDIR/bin/gate.jar"
export GATELIBJARS="$GATEDIR/lib/*"
export MY_CLASSPATH=$BUILDDIR:$GATEJAR:$GATELIBJARS
export JAVAC_OPTIONS="-Xlint:unchecked -classpath $MY_CLASSPATH"
export JAVA_OPTIONS="-classpath $MY_CLASSPATH"
export APPFILE="$GATEDIR/plugins/ANNIE/ANNIE_with_defaults.gapp"
export FEATURES="-a Person -a Location"
export EOL_OPTIONS="-it END -ot END"
export DEBUG_OPTIONS_1="-v -v"
export DEBUG_OPTIONS_2="-wg wholexml_ -wa annotxml_"
export PROG_ARGS="-g $APPFILE  $FEATURES $EOL_OPTIONS $DEBUG_OPTIONS_1"

javac $JAVAC_OPTIONS $DIR/CamAnonGatePipeline.java
mkdir -p $BUILDDIR
mv *.class $BUILDDIR/

# JAR build and run
#mkdir -p jarbuild

#cd jarbuild
#javac $JAVAC_OPTIONS ../CamAnonGatePipeline.java
#for JARFILE in $GATEJAR $GATELIBJARS; do
#    echo "Extracting from JAR: $JARFILE"
#    jar xvf $JARFILE
#done
#mkdir -p META-INF
#echo "Main-Class: CamAnonGatePipeline" > META-INF/MANIFEST.MF
#CLASSES=`find . -name "*.class"`
#jar cmvf META-INF/MANIFEST.MF ../gatehandler.jar $CLASSES
#cd ..

# This does work, but it can't find the gate.plugins.home, etc.,
# so we gain little.

# See also: http://one-jar.sourceforge.net/version-0.95/

# Note that arguments *after* the program name are seen by the program, and
# arguments before it go to Java. If you specify the classpath (which you need to
# to find GATE), you must also include the directory of your MyThing.class file.

DEMOCOMMAND="java $JAVA_OPTIONS CamAnonGatePipeline $PROG_ARGS"
RUNSCRIPT=runjavademo.sh

cat >$RUNSCRIPT << END
#!/bin/sh
$DEMOCOMMAND
END

chmod a+x $RUNSCRIPT

echo "Run $RUNSCRIPT for a demo."

#JAR run:

#java -jar ./gatehandler.jar $PROG_ARGS
