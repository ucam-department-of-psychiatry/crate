..  crate_anon/docs/source/nlp/gate.rst

..  Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).
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
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

.. |testapp| replace::
    You can test the application via the GATE Developer console. See
    :ref:`testing GATE applications <testgateapps>`.

.. |specimen| replace::
    See the :ref:`specimen CRATE NLP config file <specimen_nlp_config>`.

.. _UMLS: https://www.nlm.nih.gov/research/umls/index.html


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


.. _crate_nlp_build_gate_java_interface:

crate_nlp_build_gate_java_interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This program builds ``CrateGatePipeline``.

Options:

..  literalinclude:: _crate_nlp_build_gate_java_interface_help.txt
    :language: none


.. _crate_nlp_write_gate_auto_install_xml:

crate_nlp_write_gate_auto_install_xml
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This program writes a GATE automatic installation XML script.

..  literalinclude:: _crate_nlp_write_gate_auto_install_xml_help.txt
    :language: none


CrateGatePipeline
~~~~~~~~~~~~~~~~~

The following specimen scripts presuppose that you have set the environment
variable `GATE_HOME`, and assume specific locations for the compiled Java (e.g.
files like `CrateGatePipeline.class`); edit them as required.

You can configure logging either with `log4j.xml` (GATE 8.x) or `logback.xml`
(GATE 9.x). The configuration file must be on the Java classpath when running
`CrateGatePipeline`. You can find examples of these files in
``crate_anon/nlp_manager/gate_log_config``.


.. _crate_show_crate_gate_pipeline_options:

Asking `CrateGatePipeline` to show its command-line options:

.. code-block:: bash

    crate_show_crate_gate_pipeline_options

The resulting output:

..  literalinclude:: _CrateGatePipeline_help.txt
    :language: none

.. _crate_run_gate_annie_demo:

Asking `CrateGatePipeline` to run the GATE “ANNIE” demonstration:

.. code-block:: bash

    crate_run_gate_annie_demo

.. note::
    For the demonstrations that follow, we presuppose that you have also set
    the environment variable ``CRATE_GATE_PLUGIN_FILE`` to be the filename of
    a GATE plugin INI file like this:

.. literalinclude:: _specimen_gate_plugin_file.ini
    :language: ini


KConnect (Bio-YODIE)
~~~~~~~~~~~~~~~~~~~~

This GATE application finds diseases. Bio-YODIE is part of the KConnect
project.

- See https://gate.ac.uk/applications/bio-yodie.html; https://web.archive.org/web/20210805175524/http://kconnect.eu/.

- The main application is called `main-bio.xgapp`.

|testapp|

|specimen|

.. _crate_run_gate_kcl_kconnect_demo:

Script to test the app via the command line:

.. code-block:: bash

    crate_run_gate_kcl_kconnect_demo

.. _crate_nlp_prepare_ymls_for_bioyodie:

The KConnect GATE application requires you to register and download UMLS_ data,
containing disease vocabularies. Once you've done so, the
``crate_nlp_prepare_ymls_for_bioyodie`` tool will do some necessary
preprocessing. Its help is:

.. literalinclude:: _crate_nlp_prepare_ymls_for_bioyodie.txt
    :language: none


.. _kcl_pharmacotherapy:

KCL pharmacotherapy application
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This GATE application finds drugs (medications).

- See https://github.com/KHP-Informatics/brc-gate-pharmacotherapy

- The main application is called `application.xgapp`.

|testapp|

|specimen|

.. _crate_run_gate_kcl_pharmacotherapy_demo:

Script to test the app via the command line:

.. code-block:: bash

    crate_run_gate_kcl_pharmacotherapy_demo


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

.. _crate_run_gate_kcl_lewy_demo:

Script to test the app via the command line:

.. code-block:: bash

    crate_run_gate_kcl_lewy_demo


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

- To see the results, go back to the document, and toggle on both “Annotation
  Sets” and “Annotation Lists”. If you tick "sets" in the Annotation Sets
  window (at the right; it’s colourful) you should see specific annotations in
  the Annotation List window (at the bottom).


Troubleshooting GATE
~~~~~~~~~~~~~~~~~~~~

**Out of Java heap space**

You may see an error like "Out of memory error: java heap space".

- On a Windows machine, set the ``_JAVA_OPTIONS`` environment variable (not
  ``JAVA_OPTS``; we're not sure when that one applies).

  - Edit environment variables via the control panel or e.g.
    ``rundll32 sysdm.cpl,EditEnvironmentVariables``.

  - For the user or the system (as you prefer), set ``_JAVA_OPTIONS`` to e.g.
    ``-Xms2048m -Xmx4096m -XX:MaxPermSize=1024m``.

- Restart the relevant application (e.g. GATE Developer) and retry.

See:

- https://stackoverflow.com/questions/17369522/set-default-heap-size-in-windows

- https://serverfault.com/questions/351129/can-the-environment-variables-tool-in-windows-be-launched-directly


===============================================================================

.. rubric:: Footnotes

.. [#gate]
    University of Sheffield (2016). “GATE: General Architecture for Text
    Engineering.” https://gate.ac.uk/
