#!/bin/sh
java -classpath /home/rudolf/Documents/Career/15_Psychiatry_SpR_and_CL/CRIS_research_IT_CPFT/anonymiser/test_nlp:/home/rudolf/GATE_Developer_8.0/bin/gate.jar:/home/rudolf/GATE_Developer_8.0/lib/* CamAnonGatePipeline -g /home/rudolf/GATE_Developer_8.0/plugins/ANNIE/ANNIE_with_defaults.gapp  -a Person -a Location -it END -ot END -v -v
