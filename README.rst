..  README.rst
    GitHub README.
    This is visible at https://github.com/ucam-department-of-psychiatry/crate


Clinical Records Anonymisation and Text Extraction (CRATE)
==========================================================

.. Build status:

.. image:: https://github.com/ucam-department-of-psychiatry/crate/actions/workflows/docker.yml/badge.svg
    :target: https://github.com/ucam-department-of-psychiatry/crate/actions/workflows/docker.yml/

.. image:: https://github.com/ucam-department-of-psychiatry/crate/actions/workflows/docs.yml/badge.svg
    :target: https://github.com/ucam-department-of-psychiatry/crate/actions/workflows/docs.yml/

.. image:: https://github.com/ucam-department-of-psychiatry/crate/actions/workflows/installer.yml/badge.svg
    :target: https://github.com/ucam-department-of-psychiatry/crate/actions/workflows/installer.yml/

.. image:: https://github.com/ucam-department-of-psychiatry/crate/actions/workflows/integration-tests.yml/badge.svg
    :target: https://github.com/ucam-department-of-psychiatry/crate/actions/workflows/integration-tests.yml/

.. image:: https://github.com/ucam-department-of-psychiatry/crate/actions/workflows/precommit.yml/badge.svg
    :target: https://github.com/ucam-department-of-psychiatry/crate/actions/workflows/precommit.yml/

.. image:: https://github.com/ucam-department-of-psychiatry/crate/actions/workflows/python-checks.yml/badge.svg
    :target: https://github.com/ucam-department-of-psychiatry/crate/actions/workflows/python-checks.yml/

.. image:: https://github.com/ucam-department-of-psychiatry/crate/actions/workflows/python-tests.yml/badge.svg
    :target: https://github.com/ucam-department-of-psychiatry/crate/actions/workflows/python-tests.yml/

.. image:: https://github.com/ucam-department-of-psychiatry/crate/actions/workflows/release.yml/badge.svg
    :target: https://github.com/ucam-department-of-psychiatry/crate/actions/workflows/release.yml/

.. Code style:
.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
    :target: https://github.com/psf/black


Purpose
-------

Create and use de-identified databases for research.

- Anonymises relational databases.

- Extracts and de-identifies text from associated binary files.

- Performs some specific preprocessing tasks; e.g.

  - preprocesses some specific databases (e.g. Servelec RiO EMR);
  - drafts a "data dictionary" for anonymisation, with special knowledge of
    some databases (e.g. TPP SystmOne);
  - fetches some word lists, e.g. forenames/surnames/eponyms.

- Provides tools to link databases, including via Bayesian personal identity
  matching, in identifiable or de-identified fashion.

- Provides a natural language processing (NLP) pipeline, including built-in
  NLP, support for external tools, and client/server support for the Natural
  Language Processing Request Protocol (NLPRP).

- Web app for

  - querying the anonymised database;
  - providing a de-identification API;
  - managing a consent-to-contact process.


Documentation
-------------

See https://crateanon.readthedocs.io


Sources
-------

- Python package: https://pypi.org/project/crate-anon/
- Source code: https://github.com/ucam-department-of-psychiatry/crate


Licence
-------

- Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
  Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

- Licensed under the GNU GPL v3+: see LICENSE file.

- Some third-party libraries have slightly different licences;
  see the documentation.
