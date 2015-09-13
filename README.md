# CRATE
**Clinical Records Anonymisation and Text Extraction (CRATE)**

## Purpose
- Anonymises relational databases.
- Operates a GATE natural language processing (NLP) pipeline.
- Includes a tool to audit all MySQL queries (with user details) via a TCP
  proxy.

## Directory structure with key files
- `anonymise/`
  - **`anonymise.py`** &ndash; core program
  - `launch_makedata.sh` &ndash; launcher for make_demo_database.py
  - `launch_multiprocess_anonymiser.sh` &ndash; parallel processing
    (multiprocess) launcher for anonymise.py
  - `make_demo_database.py` &ndash; creates a demonstration database
  - `test_anonymisation.py` &ndash; generates a comparison of records between
    source and destination databases, to check anonymisation.
- `mysql_auditor/` &ndash; auditing tool for MySQL
  - `mysql_auditor.conf` &ndash; sample configuration file; edit for your own
    needs.
  - `mysql_auditor.sh` &ndash; launcher for mysql-proxy with auditing script;
    it fires up mysql-proxy (which communicates with MySQL on port A and makes
    another MySQL instance appear on port B, inserting a script in between);
    it stores the stdout/stderr output from the script in a disk log if
    requested.
  - `query_auditor_mysqlproxy.lua` &ndash; Lua script that implements the
    auditor; this is used by the external mysql-proxy tool; its output is to
    stdout/stderr.
- `nlp_manager/` &ndash; NLP interface tool
  - `buildjava.sh` &ndash; script to compile the necessary Java source on your
    machine
  - `CamAnonGatePipeline.java` &ndash; Java code to interface between
    nlp_manager.py (via stdin/stdout) and the Java-based external GATE tools
    (via code); must be compiled before use
  - `launch_multiprocess_nlp.sh` &ndash; parallel processing (multiprocess)
    launcher for nlp_manager.py
  - `nlp_manager.py` &ndash; core program to pipe parts of a database to a GATE
    program and insert the output back into a database; uses
    CamAnonGatePipeline.java to communicate with the NLP app
  - `runjavademo.sh` &ndash; directly executes CamAnonGatePipeline using the
    ANNIE demo GATE app, for testing
- `pythonlib/` &ndash; common RNC python libraries (a Git subtree)
  - ...
- `webfrontend/` &ndash; incomplete code for a WSGI web application to serve
  the data dictionary and SQL query results
  - ...
- `working/` &ndash; ignored
  - ...
- `estimate_mysql_memory_usage.sh` &ndash; script to estimate memory usage by a
  MySQL instance
- `LICENCE` &ndash; Apache license applicable to CRATE
- `LINT_CHECK` &ndash; script to check all Python code with pyflakes
- `notes.txt` &ndash; development notes
- `PEP8_CHECK` &ndash; script to check all Python code with pep8
- **`pipeline.txt`** &ndash; description of data pipeline
- `PUSH_EVERYTHING` &ndash; script to push to Github etc.
- **`README.md`** &ndash; this file
- `SET_PATHS.sh` &ndash; execute with `'. SET_PATHS.sh'` to set PYTHONPATH
  and Java CLASSPATH environment variables

## Copyright/licensing
- CRATE: copyright &copy; 2015-2015 Rudolf Cardinal (rudolf@pobox.com).
- Licensed under the Apache License, version 2.0: see LICENSE file.
- Third-party code/libraries included:
  - aspects of CamAnonGatePipeline.java are based on demonstration GATE code,
    copyright &copy; University of Sheffield, and licensed under the GNU LGPL
    (which license is therefore used for npl_manager/CamAnonGatePipeline.java;
    q.v.).
