..  crate_anon/docs/source/glossary.rst

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


.. _abbreviations:

Abbreviations
=============

=============== ===============================================================
Abbreviation    Meaning
=============== ===============================================================
C4C             consent for contact
CPFT            Cambridgeshire & Peterborough NHS Foundation Trust
CRATE           Clinical Records Anonymisation and Text Extraction (software)
                [#crate]_
CRIS            Clinical Records Interactive Search [#cris1]_ [#cris2]_
CSV             comma-separated value (file)
DD              data dictionary
EMR             electronic medical record (system)
GATE            General Architecture for Text Engineering (software)
IAPT            UK Improving Access to Psychological Therapies service
ID              identifier
KCL             King's College London
MPID            master patient identifier
MRID            master research identifier
NHS             UK National Health Service
NLP             natural language processing
PID             patient identifier
RCEP            RiO CRIS Extraction Program (by Servelec)
RDBM            Research database manager
RID             research identifier
RiO             An EMR product from Servelec
SLAM            South London & Maudsley NHS Foundation Trust
SQL             Structured Query Language [#sql]_
TRID            transient research identifier
TSV             tab-separated value (file)
UK              United Kingdom
=============== ===============================================================


.. _glossary:

Glossary
========

.. _mpid:

- **Master patient ID (MPID).** A number that uniquely identifies a patient
  across many databases. In the UK, the NHS number is the usual MPID.

.. _mrid:

- **Master research ID (MRID).** A research identifier that is unique to a
  de-identified patient's record across many linked research databases. A
  securely hashed version of the :ref:`MPID <mpid>`.

.. _pid:

- **Patient ID (PID).** A number that uniquely identifies a patient within a
  given database. For example, in a Servelec RiO database, the RiO number is
  the PID.

.. _rdbm:

- **Research database administrator (RDBM).** A person authorized to run a
  research database. They may also function as a member of the clinical
  administrative team, to whom clinicians may delegate work.

.. _rid:

- **Research ID (RID).** A research identifier that is unique to a
  de-identified patient's record in a research database. A securely hashed
  version of the :ref:`PID <pid>`.

.. _trid:

- **Transient research ID (TRID).** An integer that is unique to a
  de-identified patient within a given database, but which is susceptible to
  being destroyed and replaced by a different number if the database is
  de-identified again. It's faster than the :ref:`RID <rid>`, because it's an
  integer, and it can be used reliably to link tables within a :ref:`query
  <research_queries>`, but it can't be stored and relied on again later,
  unlike the :ref:`RID <rid>` or :ref:`MRID <mrid>`.


===============================================================================

.. rubric:: Footnotes

.. [#sql]
    Codd EF (1970). “A Relational Model of Data for Large Shared Data Banks.”
    *Commun. ACM* 13: 377–387. https://doi.org/10.1145/362384.362685.

.. [#cris1]
    Stewart R et al. (2009). “The South London and Maudsley NHS Foundation
    Trust Biomedical Research Centre (SLAM BRC) case register: development and
    descriptive data.”
    *BMC Psychiatry* 9: 51.
    https://www.ncbi.nlm.nih.gov/pubmed/19674459;
    https://doi.org/10.1186/1471-244X-9-51.

.. [#cris2]
    Fernandes A et al. (2013). “Development and evaluation of a
    de-identification procedure for a case register sourced from mental health
    electronic records.”
    *BMC Medical Informatics and Decision Making* 13: 71.
    https://www.ncbi.nlm.nih.gov/pubmed/23842533;
    https://doi.org/10.1186/1472-6947-13-71.

.. [#crate]
    Cardinal RN (2017). "Clinical records anonymisation and text extraction
    (CRATE): an open-source software system."
    *BMC Medical Informatics and Decision Making* 17: 50.
    https://www.ncbi.nlm.nih.gov/pubmed/28441940;
    https://doi.org/10.1186/s12911-017-0437-1.
