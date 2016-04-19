#!/bin/bash

java -classpath "/home/rudolf/Documents/code/crate/crate_anon/nlp_manager/compiled_nlp_classes:/home/rudolf/software/GATE_Developer_8.0/bin/gate.jar:/home/rudolf/software/GATE_Developer_8.0/lib/*" CrateGatePipeline -g /home/rudolf/software/GATE_Developer_8.0/plugins/ANNIE/ANNIE_with_defaults.gapp -a Person -a Location -it END -ot END -v -v

# For extra verbosity:
# java -classpath "/home/rudolf/Documents/code/crate/crate_anon/nlp_manager/compiled_nlp_classes:/home/rudolf/software/GATE_Developer_8.0/bin/gate.jar:/home/rudolf/software/GATE_Developer_8.0/lib/*" CrateGatePipeline -g /home/rudolf/software/GATE_Developer_8.0/plugins/ANNIE/ANNIE_with_defaults.gapp -a Person -a Location -it END -ot END -v -v -wg wholexml_ -wa annotxml_
