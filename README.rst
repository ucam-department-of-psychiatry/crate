
Clinical Records Anonymisation and Text Extraction (CRATE)
==========================================================

Purpose
-------

- Anonymises relational databases.

- Performs some specific preprocessing tasks; e.g.

  - preprocesses some specific databases (e.g. Servelec RiO EMR).
  - fetches some word lists, e.g. forenames/surnames/eponyms.

- Provides a natural language processing (NLP) pipeline.

- Web app for

  - querying the anonymised database
  - managing a consent-to-contact process

Authors
-------

- Rudolf Cardinal, 2015-.
- Francesca Spivack, 2018-.

Documentation
-------------

See https://egret.psychol.cam.ac.uk/crate

Sources
-------

- Python package: https://pypi.org/project/crate-anon/
- Source code: https://github.com/RudolfCardinal/crate

Licence
-------

- Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

- Licensed under the GNU GPL v3+: see LICENSE file.

- Some third-party libraries have slightly different licences:

  - aspects of ``CamAnonGatePipeline.java`` are based on demonstration GATE
    code, copyright (C); University of Sheffield, and licensed under the GNU
    LGPL; see https://gate.ac.uk/.
