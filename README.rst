# CRATE
**Clinical Records Anonymisation and Text Extraction (CRATE)**

## Purpose
- Anonymises relational databases.
- Operates a GATE natural language processing (NLP) pipeline.
- Web app for
  - querying the anonymised database
  - managing a consent-to-contact process

## Key directories and files

- `crate_anon/anonymise/`
  - **`anonymise.py`** &ndash; core program
  - `make_demo_database.py` &ndash; create a test database
  - `launch_multiprocess_anonymiser.sh` &ndash; parallel processing
    (multiprocess) launcher for anonymise.py
  - `make_demo_database.py` &ndash; creates a demonstration database
  - `test_anonymisation.py` &ndash; generates a comparison of records between
    source and destination databases, to check anonymisation.

- **`crate_anon/crateweb/`** &ndash; Django web application, as above

- **`docs/`** &ndash; documentation

- `crate_anon/nlp_manager/` &ndash; NLP interface tool
  - `buildjava.py` &ndash; script to compile the necessary Java source on your
    machine, and create a script to test the pipeline using the ANNIE demo
    GATE app.
  - `CrateGatePipeline.java` &ndash; Java code to interface between
    nlp_manager.py (via stdin/stdout) and the Java-based external GATE tools
    (via code); must be compiled before use
  - `launch_multiprocess_nlp.py` &ndash; parallel processing (multiprocess)
    launcher for nlp_manager.py
  - `nlp_manager.py` &ndash; core program to pipe parts of a database to a GATE
    program and insert the output back into a database; uses
    CrateGatePipeline.java to communicate with the NLP app

- `tools/`
  - **`install_virtualenv.sh`** &ndash; creates a suitable virtualenv for CRATE
  - ...

- `changelog.Debian` &ndash; Debian package changelog and general version history
- `LICENCE` &ndash; Apache license applicable to CRATE
- `README.rst` &ndash; this file
- `setup.py` &ndash; file to set up package for distribution, etc.

## Copyright/licensing

- CRATE: copyright &copy; 2015-2016 Rudolf Cardinal (rudolf@pobox.com).
- Licensed under the Apache License, version 2.0: see LICENSE file.
- Third-party code/libraries included:
  - aspects of CamAnonGatePipeline.java are based on demonstration GATE code,
    copyright &copy; University of Sheffield, and licensed under the GNU LGPL
    (which license is therefore used for npl_manager/CrateGatePipeline.java;
    q.v.).
