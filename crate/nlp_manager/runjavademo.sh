#!/bin/sh
java -classpath /home/rudolf/Documents/code/crate/nlp_manager/compiled_nlp_classes:/home/rudolf/GATE_Developer_8.0/bin/gate.jar:/home/rudolf/GATE_Developer_8.0/lib/* CamAnonGatePipeline -g /home/rudolf/GATE_Developer_8.0/plugins/ANNIE/ANNIE_with_defaults.gapp  -a Person -a Location -it END -ot END -v -v
