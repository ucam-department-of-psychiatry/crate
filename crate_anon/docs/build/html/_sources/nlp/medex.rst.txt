.. crate_anon/docs/source/nlp/medex.rst

..  Copyright (C) 2015-2018 Rudolf Cardinal (rudolf@pobox.com).
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


.. _medex_nlp:

MedEx-UIMA drug NLP
-------------------

MedEx-UIMA NLP (for drugs and drug doses) [#medexpub]_ is supported via an
external program. MedEx-UIMA runs in Java. CRATE supplies an external front-end
Java program (`CrateMedexPipeline.java`) that loads the MedEx app, sends text to
it (via a temporary disk file, for reasons relating to MedEx-UIMA’s internal
workings), and returns answers.

Installation
~~~~~~~~~~~~

- Download it from https://sbmi.uth.edu/ccb/resources/medex.htm

- CRATE provides Java code (see `CrateMedexPipeline.java`) to talk to
  MedEx-UIMA. Use ``crate_nlp_build_medex_java_interface`` to build this before
  you use it for the first time.

- CRATE fixes some bugs in MedEx-UIMA. Run ``crate_nlp_build_medex_itself`` to
  rebuild MedEx and fix them.


crate_nlp_build_medex_java_interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Options as of 2017-02-28:

.. code-block:: none

    usage: crate_nlp_build_medex_java_interface [-h] [--builddir BUILDDIR]
                                                [--medexdir MEDEXDIR]
                                                [--java JAVA] [--javac JAVAC]
                                                [--verbose] [--launch]

    Compile Java classes for CRATE's interface to MedEx-UIMA

    optional arguments:
      -h, --help           show this help message and exit
      --builddir BUILDDIR  Output directory for compiled .class files (default: /h
                           ome/rudolf/Documents/code/crate/crate_anon/nlp_manager/
                           compiled_nlp_classes)
      --medexdir MEDEXDIR  Root directory of MedEx installation (default:
                           /home/rudolf/dev/Medex_UIMA_1.3.6)
      --java JAVA          Java executable (default: java)
      --javac JAVAC        Java compiler (default: javac)
      --verbose, -v        Be verbose (use twice for extra verbosity)
      --launch             Launch script in demonstration mode (having previously
                           compiled it)


crate_nlp_build_medex_itself
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This program builds MedEx and implements some bug fixes and improvements for
the UK.

Options as of 2017-02-28:

.. code-block:: none

    usage: crate_nlp_build_medex_itself [-h] [--medexdir MEDEXDIR] [--javac JAVAC]
                                        [--deletefirst] [--verbose]

    Compile MedEx-UIMA itself (in Java)

    optional arguments:
      -h, --help           show this help message and exit
      --medexdir MEDEXDIR  Root directory of MedEx installation (default:
                           /home/rudolf/dev/Medex_UIMA_1.3.6)
      --javac JAVAC        Java compiler (default: javac)
      --deletefirst        Delete existing .class files first (optional)
      --verbose, -v        Be verbose


.. rubric:: Footnotes

.. [#medexpub]
    MedEx UIMA reference publication:
    https://www.ncbi.nlm.nih.gov/pubmed/25954575

.. [#medexdl]
    MedEx-UIMA downloads: https://sbmi.uth.edu/ccb/resources/medex.htm
