.. crate_anon/docs/source/nlp/crate_python_regex.rst

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

.. _regex_nlp:

CRATE's Python regex NLP
------------------------

CRATE provides several simple numerical results processors. Each comes with a
corresponding *validator*.

**Processor**

The processor looks for full results in text, like “his **CRP is 10 mg/L
today**” or “**CRP | (H) | 17**”, and will extract the number, units, and so
forth. It does so by matching a keyword (such as “CRP”, “C-reactive protein”,
“C reactive protein”, etc.) plus other attributes such as an optional tense
indicator (“is”, “was”), an optional relationship (“equals”, “<”, etc.), a
value, and units. Units may be optional, and some units may be recognized and
specifically disallowed. For example, “MMSE 25/30” or “MMSE 25 out of 30” may
be allowed, where variants on “out of 30” are the units, and “MMSE 25” can be
treated as if it were implicitly out of 30, but “MMSE 25/29” disallowed.

The processor produces the :ref:`standard NLP output columns
<standard_nlp_output_columns>`, and also these output columns:

=============== =============== ===============================================
Column          SQL type        Description
=============== =============== ===============================================
variable_name   VARCHAR(64)     Variable name (e.g. ‘CRP’)

_content        TEXT            Matching text contents

_start          INT             Start position (of matching string within whole
                                text)

_end            INT             End position (of matching string within whole
                                text)

variable_text   TEXT            Text that matched the variable name (e.g.
                                ‘CRP’, ‘C-reactive protein’).

relation_text   VARCHAR(50)     Text that matched the mathematical relationship
                                between variable and value (e.g. ‘=’, ‘equals’,
                                ‘less than’)

relation        VARCHAR(2)      Standardized mathematical relationship between
                                variable and value (e.g. ‘=’, ‘<=’)

value_text      VARCHAR(50)     Matched numerical value, as text

units           VARCHAR(50)     Matched units, as text

value_mg_l (\*) FLOAT           Numerical value in preferred units, if known

tense_text      VARCHAR(50)     Tense text, if known (e.g. ‘is’, ‘was’)

tense           VARCHAR(7)      Calculated tense, if known (e.g. ‘past’,
                                ‘present’)
=============== =============== ===============================================

… plus any fields you elected to copy.

The name of the column marked (*) will vary from processor to processor (e.g.
``value_mg_l`` for the CRP processor; ``value_kg`` for the Weight processor;
``value_m`` for the Height processor). The columns may vary from processor to
processor; for example, the blood pressure (BP) processor produces two numbers
per entry (a systolic and a diastolic BP).

**Validator**

The validator simply looks for the corresponding keyword. It doesn’t record
much information except for a reference to the source row.

The validator produces the :ref:`standard NLP output columns
<standard_nlp_output_columns>`, and typically these output columns:

=============== =============== ===============================================
Column          SQL type        Description
=============== =============== ===============================================
variable_name   VARCHAR(64)     Variable name (e.g. ‘CRP’)

_content        TEXT            Matching text contents

_start          INT             Start position (of matching string within whole
                                text)

_end            INT             End position (of matching string within whole
                                text)
=============== =============== ===============================================

… plus any fields you elected to copy.

To look at things the validator recognized but the processor didn’t like, you
can do something like the following. This example was created for a database
with string source PKs (yuk) on Microsoft SQL Server (which sometimes requires
a slightly convoluted way of specifying table names).

.. code-block:: none

    SELECT text  -- field with the free text in
    FROM crissql_v3.dbo.Progress_Notes  -- source table
    WHERE document_id IN (  -- primary key
        SELECT _srcpkstr FROM crissql_workspace.[CRIS-CPFT\RCardinal].validate_crp
    ) AND document_id NOT IN (
        SELECT _srcpkstr FROM crissql_workspace.[CRIS-CPFT\RCardinal].crp
    )

This should produce text where CRP is mentioned but no value given, such as
“FBC, TSH, vitamin B12, CRP and eGFR are all within normal range”; “blood
sample taken (CRP/U&Es and FBC)”; “monitoring CK and CRP”; “CRP was back up
yesterday”.

For a table with integer PKs you would use ``_srcpkval`` instead of
``_srcpkstr``.

**Specimen timing on a slow system (2016-11-15):** 5,954 seconds (1h40) for a
full run of 2,717,779 text notes (one per database row, from a table with a
string PK) through 40 NLP tasks (20 main, 20 validator) on a virtual computer
mimicking 2×2.7GHz CPUs running Windows Server 2003, with all databases under
SQL Server hosted elsewhere over a network. That works out at 18.2 kHz for
processor-notes or 456 Hz for notes. (The corresponding do-nothing incremental
update, with the --skipdelete option, took 4,756 s. That’s not much faster,
and was limited primarily by queries for a record indicating that each datum
had previously been processed. The advantage of incremental updates can be
considerably more than this if the NLP step is slow, as with GATE and other
more complex systems, but regular expressions are pretty quick.) Fast
computers with local networks and SSD storage should perform considerably
better, and tables with integer PKs are also processed faster because their
work can be more efficiently and evenly assigned to parallel processes.

**Current processors**

Use the ``crate_nlp --listprocessors`` or ``crate_nlp --describeprocessors``
commands to show these.

*Not all have been formally validated.*

A summary as of 2019-02-21 is:

.. list-table::
  :header-rows: 1

  * - Processor
    - Description

  * - Ace
    - Addenbrooke's Cognitive Examination (ACE, ACE-R, ACE-III) total score.

  * - Basophils
    - Basophil count (absolute).

  * - Bmi
    - Body mass index (BMI) (in kg / m^2).

  * - Bp
    - Blood pressure, in mmHg. (Systolic and diastolic.)

  * - Crp
    - C-reactive protein (CRP).

  * - Eosinophils
    - Eosinophil count (absolute).

  * - Esr
    - Erythrocyte sedimentation rate (ESR).

  * - Gate
    - Processor handling all :ref:`GATE NLP <gate_nlp>`.

  * - Glucose
    - Glucose.

  * - HbA1c
    - Glycosylated haemoglobin (HbA1c).

  * - HDLCholesterol
    - High-density lipoprotein (HDL) cholesterol.

  * - Height
    - Height. Handles metric (e.g. "1.8m") and imperial (e.g. "5 ft 2 in").

  * - LDLCholesterol
    - Low-density lipoprotein (LDL) cholesterol.

  * - Lithium
    - Lithium (Li) levels (for blood tests, not doses).

  * - Lymphocytes
    - Lymphocyte count (absolute).

  * - MedEx
    - Processor handling :ref:`MedEx-UIMA NLP <medex_nlp>`.

  * - MiniAce
    - Mini-Addenbrooke's Cognitive Examination (M-ACE).

  * - Mmse
    - Mini-mental state examination (MMSE).

  * - Moca
    - Montreal Cognitive Assessment (MOCA).

  * - Monocytes
    - Monocyte count (absolute).

  * - Neutrophils
    - Neutrophil count (absolute).

  * - Sodium
    - Sodium (Na).

  * - TotalCholesterol
    - Total cholesterol.

  * - Tsh
    - Thyroid-stimulating hormone (TSH).

  * - Wbc
    - White cell count (WBC, WCC).

  * - Weight
    - Weight. Handles metric (e.g. "57kg") and imperial (e.g. "10 st 2 lb").
