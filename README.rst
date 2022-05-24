
Clinical Records Anonymisation and Text Extraction (CRATE)
==========================================================

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black


Purpose
-------

- Anonymises relational databases.

- Performs some specific preprocessing tasks; e.g.

  - preprocesses some specific databases (e.g. Servelec RiO EMR);
  - drafts a "data dictionary" for anonymisation, with special knowledge of
    some databases (e.g. TPP SystmOne);
  - fetches some word lists, e.g. forenames/surnames/eponyms.

- Provides a natural language processing (NLP) pipeline.

- Web app for

  - querying the anonymised database
  - managing a consent-to-contact process


Documentation
-------------

See https://crateanon.readthedocs.io


Sources
-------

- Python package: https://pypi.org/project/crate-anon/
- Source code: https://github.com/RudolfCardinal/crate


Licence
-------

- Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
  Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

- Licensed under the GNU GPL v3+: see LICENSE file.

- Some third-party libraries have slightly different licences:

  - aspects of ``CamAnonGatePipeline.java`` are based on demonstration GATE
    code, copyright (C); University of Sheffield, and licensed under the GNU
    LGPL; see https://gate.ac.uk/.
