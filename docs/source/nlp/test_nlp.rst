..  crate_anon/docs/source/nlp/test_nlp.rst

..  Copyright (C) 2015-2021 Rudolf Cardinal (rudolf@pobox.com).
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


.. _testing_nlp:

Testing NLP
-----------

CRATE provides specific ways to test individual NLP tools:

- :ref:`CRATE internal Python NLP <crate_run_crate_nlp_demo>`
- Specific GATE tools:

  - The :ref:`ANNIE <crate_run_gate_annie_demo>` demo
  - :ref:`KConnect (Bio-YODIE) <crate_run_gate_kcl_kconnect_demo>`
  - :ref:`KCL pharmacotherapy <crate_run_gate_kcl_pharmacotherapy_demo>`
  - :ref:`KCL Lewy body dementia <crate_run_gate_kcl_lewy_demo>`

However, you can also test any NLP tool that you have configured:

.. code-block:: bash

    crate_nlp [--config CONFIGFILE] --nlpdef NLPDEF --test_nlp

When you do this, you are asked to type text line by line, it's passed to one
or more NLP processors (as determined by the NLP definition), and you see the
results.

The test does not use any databases.
