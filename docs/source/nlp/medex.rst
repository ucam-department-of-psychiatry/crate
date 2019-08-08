.. crate_anon/docs/source/nlp/medex.rst

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


Output columns
~~~~~~~~~~~~~~

In addition to the :ref:`standard NLP output columns
<standard_nlp_output_columns>`, the CRATE MedEx processor produces these output
columns:

======================= =============== =======================================================
Column                  SQL type        Description
======================= =============== =======================================================
sentence_index          INT             One-based index of sentence in text
sentence_text           TEXT            Text recognized as a sentence by MedEx

drug                    TEXT            Drug name, as in the text
drug_startpos           INT             Start position of drug
drug_endpos             INT             End position of drug

brand                   TEXT            Drug brand name (?lookup ?only if given)
brand_startpos          INT             Start position of brand
brand_endpos            INT             End position of brand

form                    VARCHAR(255)    Drug/dose form (e.g. 'tablet')
form_startpos           INT             Start position of form
form_endpos             INT             End position of form

strength                VARCHAR(50)     Strength (e.g. '75mg')
strength_startpos       INT             Start position of strength
strength_endpos         INT             End position of strength

dose_amount             VARCHAR(50)     Dose amount (e.g. '2 tablets')
dose_amount_startpos    INT             Start position of dose_amount
dose_amount_endpos      INT             End position of dose_amount

route                   VARCHAR(50)     Route (e.g. 'by mouth')
route_startpos          INT             Start position of route
route_endpos            INT             End position of route

frequency               VARCHAR(50)     frequency (e.g. 'by mouth')
frequency_startpos      INT             Start position of frequency
frequency_endpos        INT             End position of frequency
frequency_timex3        VARCHAR(50)     Normalized frequency in TIMEX3 format (e.g. 'R1P12H')

duration                VARCHAR(50)     Duration (e.g. 'for 10 days')
duration_startpos       INT             Start position of duration
duration_endpos         INT             End position of duration

necessity               VARCHAR(50)     Necessity (e.g. 'prn')
necessity_startpos      INT             Start position of necessity
necessity_endpos        INT             End position of necessity

necessity               VARCHAR(50)     Necessity (e.g. 'prn')
necessity_startpos      INT             Start position of necessity
necessity_endpos        INT             End position of necessity

umls_code               VARCHAR(8)      UMLS CUI
rx_code                 INT             RxNorm RxCUI for drug
generic_code            INT             RxNorm RxCUI for generic name
generic_name            TEXT            Generic drug name (associated with RxCUI code)
======================= =============== =======================================================

Start positions are the zero-based index of the first relevant character. End
positions are the zero-based index of one beyond the last relevant character.


crate_nlp_build_medex_java_interface
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Options:

..  literalinclude:: crate_nlp_build_medex_java_interface_help.txt
    :language: none


crate_nlp_build_medex_itself
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This program builds MedEx and implements some bug fixes and improvements for
the UK.

Options:

..  literalinclude:: crate_nlp_build_medex_itself_help.txt
    :language: none


CrateMedexPipeline
~~~~~~~~~~~~~~~~~~

The following specimen script assumes specific locations for the compiled Java
(``CrateMedexPipeline.class``); edit it as required.

Asking `CrateMedexPipeline` to show its command-line options:

.. literalinclude:: show_crate_medex_pipeline_options.sh
    :language: bash

The resulting output:

..  literalinclude:: CrateMedexPipeline_help.txt
    :language: none


===============================================================================

.. rubric:: Footnotes

.. [#medexpub]
    MedEx UIMA reference publication:
    https://www.ncbi.nlm.nih.gov/pubmed/25954575

.. [#medexdl]
    MedEx-UIMA downloads: https://sbmi.uth.edu/ccb/resources/medex.htm
