.. crate_anon/docs/source/nlp/gate.rst

..  Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).
    .
    This file is part of CRATE.
    .
    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    .
    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.
    .
    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.

.. |testapp| replace::
    You can test the application via the GATE Developer console. See
    :ref:`testing GATE applications <testgateapps>`.

.. |specimen| replace::
    See the :ref:`specimen CRATE NLP config file <specimen_nlp_config>`.

.. _gate_nlp:

GATE NLP applications
---------------------

GATE NLP is done via an external program, GATE [#gate]_. GATE runs in Java.
CRATE supplies an external front-end Java program (`CrateGatePipeline.java`)
that loads a GATE app, sends text to it, and returns answers.

In general, CRATE sends text to the external program (via stdin), and will
expect a result (via stdout) as a set of tab-separated value (TSV) lines
corresponding to the expected destination fields.

The `CrateGatePipeline.java` program takes arguments that describe how a
specific GATE application should be handled.

Output columns
~~~~~~~~~~~~~~

In addition to the :ref:`standard NLP output columns
<standard_nlp_output_columns>`, the CRATE GATE processor produces these output
columns:

=============== =============== ===============================================
Column          SQL type        Description
=============== =============== ===============================================
_set            VARCHAR(64)     GATE output set name

_type           VARCHAR(64)     GATE annotation type name (e.g. 'Person')

_id             INT             GATE annotation ID. Not clear that this is very
                                useful.

_start          INT             Start position in the content

_end            INT             End position in the content

_content        TEXT            Full content marked as relevant. (Not the
                                entire content of the source field.)
=============== =============== ===============================================

These default output columns are prefixed with an underscore to reduce the risk
of name clashes, since GATE applications can themselves generate arbitrary
column names. For example, the demonstration GATE Person app generates these:

.. code-block:: none

    rule
    firstname
    surname
    gender
    kind

You tell CRATE about the specific fields produced by a GATE application using
the ``destfields`` option; see the :ref:`NLP config file <nlp_config>`.

KConnect (Bio-YODIE)
~~~~~~~~~~~~~~~~~~~~

This GATE application finds diseases.

- See https://gate.ac.uk/applications/bio-yodie.html

- The main application is called `main-bio.xgapp`.

|testapp|

|specimen|

KCL pharmacotherapy application
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This GATE application finds drugs (medications).

- See https://github.com/KHP-Informatics/brc-gate-pharmacotherapy

- The main application is called `application.xgapp`.

|testapp|

|specimen|

KCL Lewy Body Diagnosis Application
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This GATE application finds references to Lewy body dementia.

- Clone it from https://github.com/KHP-Informatics/brc-gate-LBD

- As of 2018-03-20, the Git repository just contains a zip. Unzip it.

- The main application is called `application.xgapp`.

- The principal annotation is called `cDiagnosis` ("confirmed diagnosis"),
  which has `rule` and `text` elements.

|testapp|

|specimen|


.. _testgateapps:

Testing a GATE application manually
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The illustration below assumes that the main GATE application file is called
`main-bio.xgapp`, which is correct for KConnect. For others, the name is
different; see above.

- Run GATE Developer.

- Load the application:

  - :menuselection:`File --> Restore application from file`
  - find `main-bio.xgapp`, in the downloaded KConnect directory (or whichever
    the appropriate `.xgapp` file is for your application);
  - load this;
  - wait until it’s finished loading.

- Create a document:

  - :menuselection:`Right-click Language Resources --> New --> GATE Document`
  - name it (e.g. ``my_test_doc``);
  - open it;
  - paste some text in the “Text” window.

- Create a corpus

  - :menuselection:`Right-click Language Resources --> New --> GATE Corpus`
  - name it (e.g. ``my_test_corpus``);
  - open it;
  - add the document (e.g. with the icon looking like ‘G+’).

- View the application:

  - Go to the application tab (`main-bio.xgapp`), or double-click
    `main-bio.xgapp` in the left hand tree (under Applications) to open it if
    it’s not already open. For other applications: fine the appropriate
    application in the “Applications” tree and double-click it.

  - Make sure your corpus is selected in the “Corpus:” section. (There should
    already be a bunch of things in the top-right-hand box, “Selected
    processing resources”; for example, for KConnect, you’ll see
    “MP:preprocess” through to “MP:finalize”.)

- Click “Run this Application”.

- To see the results, go back to the document, and toggle on both “Annotation
  Sets” and “Annotation Lists”. If you tick "sets" in the Annotation Sets
  window (at the right; it’s colourful) you should see specific annotations in
  the Annotation List window (at the bottom).


crate_nlp_build_gate_java_interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Options as of 2017-02-28:

..  literalinclude:: crate_nlp_build_gate_java_interface_help.txt
    :language: none


CrateGatePipeline
~~~~~~~~~~~~~~~~~

The following specimen scripts presuppose that you have set the environment
variable `GATE_DIR`, and assume specific locations for the compiled Java (e.g.
files like `CrateGatePipeline.class`); edit them as required.

Asking `CrateGatePipeline` to show its command-line options:

.. code-block:: bash

    #!/bin/bash
    THISDIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
    CRATE_NLP_JAVA_CLASS_DIR=$THISDIR/../crate_anon/nlp_manager/compiled_nlp_classes
    java \
        -classpath "${CRATE_NLP_JAVA_CLASS_DIR}":"${GATE_DIR}/bin/gate.jar":"${GATE_DIR}/lib/*" \
        -Dgate.home="${GATE_DIR}" \
        CrateGatePipeline \
        --help \
        -v -v

The resulting output (2018-04-17):

..  literalinclude:: CrateGatePipeline_help.txt
    :language: none


Asking CrateGatePipeline to run the GATE “ANNIE” demonstration:

.. code-block:: bash

    #!/bin/bash
    THISDIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )
    CRATE_NLP_JAVA_CLASS_DIR=$THISDIR/../crate_anon/nlp_manager/compiled_nlp_classes
    java \
        -classpath "${CRATE_NLP_JAVA_CLASS_DIR}":"${GATE_DIR}/bin/gate.jar":"${GATE_DIR}/lib/*" \
        -Dgate.home="${GATE_DIR}" \
        CrateGatePipeline \
        -g "${GATE_DIR}/plugins/ANNIE/ANNIE_with_defaults.gapp" \
        -a Person \
        -a Location \
        -it STOP \
        -ot END_OF_NLP_OUTPUT_RECORD \
        -lt . \
        -v -v



.. rubric:: Footnotes

.. [#gate]
    University of Sheffield (2016). “GATE: General Architecture for Text
    Engineering.” https://gate.ac.uk/
