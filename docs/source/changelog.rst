.. crate_anon/docs/source/changelog.rst

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


Change log/history
==================

Contributors
------------

- Rudolf Cardinal, 2015–.
- Francesca Spivack, 2018–.

Changes
-------

**2015-02-18**

- Started.

**v0.03, 2015-03-19**

- Bug fix for incremental update (previous version inserted rather than
  updating when the source content had changed); search for
  update_on_duplicate_key.

- Checks for missing/extra fields in destination.

- “No separator” allowed for get_date_regex_elements(), allowing anonymisation
  of e.g. 19Mar2015, 19800101.

- New default at_word_boundaries_only=False for get_date_regex_elements(),
  allowing anonymisation of ISO8601-format dates (e.g. 1980-10-01T0000), etc.

- Similar option for get_code_regex_elements().

- Similar option for get_string_regex_elements().

- Options in config to control these.

- Fuzzy matching for get_string_regex_elements(); string_max_regex_errors
  option in config. The downside is the potential for greedy matching; for
  example, if you anonymise “Ronald MacDonald” with “Ronald” and “MacDonald”,
  you can end up with “XXX MacXXX”, as the regex greedy-matches “Donald” to
  “Ronald” with a typo, and therefore fails to process the whole “MacDonald”.
  On the other hand, this protects against simple typos, which are probably
  more common.

- Audit database/table.

- Create an incremental update to the data dictionary (i.e. existing DD plus
  any new fields in the source, with safe draft entries).

- Data dictionary optimizations.

**v0.04, 2015-04-25**

- Whole bunch of stuff to cope with a limited computer talking to SQL Server
  with some idiosyncrasies.

**v0.05, 2015-05-01**

- Ability to vary audit/secret map tablenames.

- Made date element separators broader in anonymisation regex.

- min_string_length_for_errors option

- min_string_length_to_scrub_with option

- words_not_to_scrub option

- bugfix: date regex couldn't cope with years prior to 1900

- gen_all_values_for_patient() was inefficient in that it would process the
  same source table multiple times to retrieve different fields.

- ddgen_index_fields option

- simplification of get_anon_fragments_from_string()

- SCRUBMETHOD.CODE, particularly for postcodes. (Not very different from
  SCRUBMETHOD.NUMERIC, but a little different.)

- debug_row_limit applies to patient-based tables (as a per-thread limit); was
  previously implemented as a per-patient limit, which was silly.

- Indirection step in config for destination/admin databases.

- ddgen_allow_fulltext_indexing option, for old MySQL versions.

**v0.06, 2015-06-25**

- Option: replace_nonspecific_info_with

- Option: scrub_all_numbers_of_n_digits

- Option: scrub_all_uk_postcodes

**v0.06, 2015-07-14**

- bugfix: if a source scrub-from value was a number with value '.', the regex
  went haywire... so regex builders now check for blanks.

**v0.07, 2015-07-16**

- regex.ENHANCEMATCH flag tried unsuccessfully (segmentation fault, i.e.
  internal error in regex module, likely because generated regular expressions
  got too complicated for it).

**v0.08, 2015-07-20**

- SCRUBMETHOD.WORDS renamed SCRUBMETHOD.WORDS

- SCRUBMETHOD.PHRASE added

- ddgen_scrubmethod_phrase_fields added

**v0.09, 2015-07-28**

- debug_max_n_patients option, used with gen_patient_ids(), to reduce the
  number of patients processed for “full rebuild” debugging.

- debug_pid_list option, similarly

**v0.10, 2015-09-02 to 2015-09-13**

- Opt-out mechanism.

- Default hasher changed to SHA256.

- Bugfix to datatypes in delete_dest_rows_with_no_src_row().

**v0.11, 2015-09-16**

- Split main source code for simplicity.

**v0.12, 2015-09-21**

- Database interface renamed from mysqldb to mysql, to allow for PyMySQL support as well (backend details otherwise irrelevant to front-end application).

**v0.13, 2015-10-06**

- Added TRID.

**v0.14.0, 2016-03-10**

- Code cleanup.

- HMAC for RID generation, replacing simpler hashes, for improved security.
  Default becomes HMAC_MD5.

- New option: secret_trid_cache_tablename

- Removed option: words_not_to_scrub

- New options: whitelist_filenames (replaces words_not_to_scrub),
  blacklist_filenames.

- Transition from cardinal_pythonlib.rnc_db to SQLAlchemy for anonymiser
  database interface.

- Environment variable changed from CRATE_LOCAL_SETTINGS to
  CRATE_WEB_LOCAL_SETTINGS and coded into crate_anon/config/constants.py.

- Web front end now happy getting structure from SQL Server and PostgreSQL.

- Windows support. Windows XP not supported as Erlang (and thus RabbitMQ) won’t
  run on it from the distributed binaries. Windows 10 works fine.

- Semantic versioning.

**v0.16.0, 2016-06-04**

- Fixes to work properly with SQL Server, including proper automatic conversion
  of VARCHAR(MAX) and NVARCHAR(MAX) to MySQL TEXT fields. Note: also needs
  SQLAlchemy 1.1 or higher [#f1]_, currently available only via (1) fetching
  source via ``git clone https://github.com/zzzeek/sqlalchemy`` and changing
  into the ‘sqlalchemy’ directory this will create; (2) activating your CRATE
  virtual environment; (3) ``pip install .`` to install SQLAlchemy from your
  source copy. Further note: as of v0.18.2, this is done via PyPI again.

- Opt-out management (1) manually; (2) via disk file; (3) via database fields.

**v0.17.0, 2016-06-25**

- ONS Postcode Database.

- RiO preprocessor.

- Third-party patient cross-referencing for anonymisation.

- The ‘required scrubber’ flag, as a safety measure.

- Recordwise view of results in web interface.

- Static type checking.

**v0.18.0, 2016-09-29**

- Regular expression NLP tools for simple numerical results (CRP, ESR, WBC and
  differential, Na, MMSE).

**v0.18.1, 2016-11-04**

- v0.18.1 (2016-11-04): new anonymise_numbers_at_numeric_boundaries_only
  option, to prevent e.g. ‘23’ being scrubbed from ‘1234’ unless you really
  want to.

- More built-in NLP tools by now (height, weight, BMI, BP, TSH). MedEx support.

**v0.18.2 to v0.18.8, 2016-11-11 to 2016-11-13**

- Too many version numbers here because git connection unavailable for remote
  development.

- Requirement upgraded to SQLAlchemy 1.1.3, now SQLAlchemy 1.1 and higher are
  available from PyPI.

- Support for non-integer PKs for NLP, to allow us to operate with tables we
  have only read-only access to. This is a bit tricky. To parallelize, it helps
  to be able to convert a non-integer to an integer for use with the modulo
  operator, %. In addition, we store PK values to speed up incremental updates.
  It becomes messy if we have to cope with lots and lots of types of PKs. Also,
  Python’s hash() function is inconsistent across invocations [#f2]_. This is
  not a cryptographic application, so we can use anything simple and fast
  [#f3]_. It looks like MurmurHash3 is suitable (hash DDoS attacks are not
  relevant here) [#f4]_. However, the problem then is with collisions [#f5]_.
  We want to ask “has this PK been processed before?” Realistically, the only
  types of PKs are integers and strings; it would be crazy to use
  floating-point numbers or BLOBs or something. So let’s put a cap at
  VARCHAR(n), where n comes from MAX_STRING_PK_LENGTH; store a 64-bit integer
  hash for speed, and then use the hash to say quickly “no, not processed” and
  check the original PK if processed. If the PK field is integer, we can just
  use the integer field for the PK itself. Note that the delete_where_no_source
  function may be imperfect now under hash collisions (and it may be imperfect
  in other ways too).

- This system not implemented for anonymisation; it just gets too confusing
  (PIDs, MPIDs, uniqueness of PID for TRID generation, etc.).

- However, mmh3 requires a Visual C++ 10.0 compiler for Windows. An alternative
  would be to require pymmh3 but load mmh3 if available, but pymmh3 isn’t on
  PyPI. Another is xxHash [#xxhash]_, but that also requires VC++ under
  Windows; pyhashxx installs but the interface isn’t fantastic. Others include
  FNV and siphash [#siphash]_. The xxHash page compares quality and speed and
  xxHash beats FNV for both (and MurmurHash for speed); siphash not listed.
  Installation of siphash is fine. Other comparisons at [#hashcomparisons]_.
  Let’s use xxhash (needs VC++) and pyhashxx as a fallback... only pyhashxx
  only supports 32-bit hashing. The pyhash module doesn’t install under Windows
  Server 2003, and nor does xxh, while lz4tools needs VC++. OK. Upshot: use
  mmh3 but fall back to some baked in Python implementations (from
  StackOverflow and pymmh3, with some bugfixes) if mmh3 not available.

- NLP ``delete_where_no_source`` then failed as expected with large databases,
  so reworked to be OK regardless of size (using temporary tables).

- Python 3.5 can handle circular imports (for type hints) that Python 3.4
  can’t, so some delayed and version-conditional imports to sort that out in
  the NLP code.

- Provide source/destination record counts from NLP manager, and better
  progress indicator for anonymiser.

- Optional NLP record limit for debugging.

- Speed increases by not requesting unnecessary ORDER BY conditions.

- Commit-every options for NLP (every n bytes and/or every n rows).

- Regex NLP for ACE, mini-ACE, MOCA.

- Timing framework for NLP (for when it’s dreadfully slow and you think the
  problem might be the source database).

- Significant NLP performance enhancement by altering progress DB lookup methods.

**v0.18.9, 2016-12-02**

- Regex NLP: option in SimpleNumericalResultParser to take absolute values,
  e.g. to deal with text like “Na-142, K-4.1, CRP-97”, which use “-” simply as
  punctuation, rather than as a minus sign. Failing to account for these would
  distort results.

- No attempt is made to specify maximum or minimum values, which can easily be
  excluded as required from the resulting data set. One could of course use the
  SQL ABS() function to deal with negative values post hoc, but some things
  have no physical meaning when negative, such as a white cell count or CRP
  value, so it’s preferable to fix these at source to reduce the chance of user
  error through not noticing negative values.

- The “take_absolute” option is applied to: CRP, sodium, TSH, BMI, MMSE, ACE,
  mini-ACE, MOCA, ESR, and white cell/differential counts. (NLP processors for
  height, BP already enforced positive values. Weight must be able to handle
  negatives, like “weight change –0.4kg”.)

- Similarly, hyphen followed by whitespace treated as ignorable in regex NLP
  (e.g. in “weight - 48 kg”; though spaces are meaningful for mathematical
  operations (“a – b = c”), it is syntactically wrong to use “- 4” as a unary
  minus sign to indicate a negative number (–4) and much more likely that this
  context means a dash.

- En and em dashes, and a double-hyphen as a dash (“--”) treated as ignorables
  in regex NLP.

- At present, Unicode minus signs (−) are not handled. For reference [#dashes]_:

    =============== =========== =========================== ======================================
    name            character   code                        handling
    =============== =========== =========================== ======================================
    hyphen-minus    -           Unicode 002D or ASCII 45    minus sign if context correct
    formal hyphen   ‐           Unicode 2010                not handled at present
    minus sign      −           Unicode 2212                not handled at present
    en dash         –           Unicode 2013                treated as ignorable [#ignoreendash]_
    em dash         —           Unicode 2014                treated as ignorable
    =============== =========== =========================== ======================================

- Improved regex self-testing, including new test framework in
  crate_anon/nlp_manager/test_all_regex.py.

**v0.18.10, 2016-12-11**

- Full support for SQL Server as the backend.

- Hot-swapping databases (compare MySQL [#mysqlrenamedb]_): you can rename
  databases, so this seems OK [#sqlserverrenamedb]_.

- Full-text indexing: optional in SQL Server 2008, 2012, 2014 and 2016
  [#sqlserverfulltext]_; basic SELECT syntax is ``WHERE CONTAINS(fieldname,
  "word")``, and index creation with ``CREATE FULLTEXT INDEX ON table_name
  (column_name) KEY INDEX index_name ...``. Added to crate_anon/common/sqla.py.

- Support for SQL query building, with user-configurable selector mechanism.
  See Transact-SQL syntax reference [#tsql]_. We use the Django setting
  ``settings.RESEARCH_DB_DIALECT`` to govern this.

**v0.18.11, 2016-12-19**

- Tweaks/bugfixes for RiO preprocessor, and for anonymisation to SQL Server
  databases.

- Local help HTML offered via web front end.

**v0.18.12, 2017-02-26**

- More fixes for SQL Server, including full-text indexing.

- Completed changes to CPFT consent materials to reflect ethics revision (Major
  Amendment 2, 12/EE/0407).

**v0.18.13, 2017-03-04**

- Final update/PyPI push for CPFT consent materials.

**v0.18.14, 2017-03-05**

- Extra debug options for consent-to-contact templates.

- Multi-column FULLTEXT indexes under SQL Server.

**v0.18.15-v0.18.16, 2017-03-06 to 2017-03-13**

- Full-text finder generates CONTAINS(column, ‘word’) properly for SQL Server.

- Bugfix to Patient Explorer (wasn’t offering WHERE options always).

- “Table browser” views in Patient Explorer

- Bugfix to Windows service. Problem: a Python process was occasionally being
  “left over” by the Windows service, i.e. not being killed properly. Process
  Explorer indicated it was the one launched as “python
  launch_cherrypy_server.py”. The Windows event log has a message reading
  “Process 1/2 (Django/CherryPy) (PID=62516): Subprocess finished cleanly
  (return code 0).” The problem was probably that in
  crate_anon/crateweb/core/management/commands/runcpserver.py, the
  cherrypy.engine.stop() call was only made upon a KeyboardInterrupt exception,
  and not on other exceptions. Solution: broadened to all exceptions.

**v0.18.17, 2017-03-17**

- Removed erroneous debugging code from
  crate_anon.nlp_manager.parse_medex.Medex.parse

- If you mis-configured the Java interface to a GATE application, it crashed
  quickly, which was helpful. If you mis-configured the Java interface to
  MedEx, it tried repeatedly. Now it crashes quickly.

**v0.18.18 to v0.18.23, 2017-04-28**

- Paper published on 2017-04-26 as **Cardinal (2017), BMC Medical Informatics
  and Decision Making 17:50; http://www.pubmed.com/28441940;
  https://dx.doi.org/10.1186/s12911-017-0437-1.**

- Support for configurable paths for finding on-disk documents (e.g. from a
  combination of a fixed root directory, a patient ID, and a filename).

**v0.18.23 to v0.18.33, 2017-05-02**

- NLP “value_text” field (FN_VALUE_TEXT in code) given maximum length, rather
  than 50, for the regex parsers, as it was overflowing (e.g. when a lot of
  whitespace was present). See
  regex_parser.NumericalResultParser.dest_tables_columns.

- Supports more simple text file types (.csv, .msg, .htm).

- New option: ddgen_rename_tables_remove_suffixes.

- Bugfix to CRATE GATE handler’s stdout-suppression switch.

- New option: ddgen_extra_hash_fields.

- **PCMIS preprocessor.**

- **Support non-integer PIDs and MPIDs.** Note that the hashing is based on a
  string representation, so if you have one database using an integer NHS
  number, and another using a string NHS number, the same number will hash to
  the same result if you use the same key.

- Hashing of additional fields, initially to support the PCMIS CaseNumber (as
  well as PatientId).

**v0.18.34 to v0.18.39, 2017-06-05**

- For SLAM BRC GATE pharmacotherapy app: add support for output columns whose
  SQL column name is different to the GATE tag (e.g. when “dose-value” must be
  changed to “dose_value”); see **``renames``** option. GATE output fields now
  preserve case. Another option (null_literals) to allow GATE output of ‘null’
  to be changed to an SQL NULL. Also added _set column to GATE output.

**v0.18.40, 2017-07-20**

- Fixed Python type-checking bug in crate_anon/anonymise/crateconfigparser.py
  (ExtendedConfigParser.get_pyvalue_list); changed from Generic to Any.

**v0.18.41, 2017-07-21**

- Support for MySQL ENUM types. However, see
  http://komlenic.com/244/8-reasons-why-mysqls-enum-data-type-is-evil/ also!

**To v0.18.46, 2017-07-28 to 2017-08-05**

- Fix to coerce_to_date (for date types), renamed to coerce_to_datetime.

- NLP bug fixed relating to a missing ‘pytz’ import.

- Fixes to NLP, including accepting views (not just tables) as input. Note that
  under SQL Server, you should not have to specify ‘dbo’ anywhere in the config
  (but consider setting ALTER USER... WITH DEFAULT SCHEMA as above).

- Manual and 2017 paper distributed with package.

- Shift some core stuff to cardinal_pythonlib to reduce code duplication with
  other projects.

**v0.18.48, 2017-11-06**

- Clinician view: find text across a database, for an identified patient.

- Clinician view: look up (M)RIDs from (M)PIDs. Intended purpose for this and
  the preceding function: “My clinical front end won’t tell me if my patient’s
  ever had mirtazapine. I want to ask the research database.” (As per CO’L
  request 2017-05-04.)

- Code to generate and test demonstration databases improved.

**v0.18.49, 2018-01-07, 2018-03-21, 2018-03-27, published 2018-04-20**

- Use flashtext (rather than regex) for blacklisting words; this is much faster
  and allows large blacklists (e.g. a long list of all known
  forenames/surnames).

- Provides the crate_fetch_wordlists tool to fetch names and English words (and
  perform in-A-not-B functions, e.g. to generate a list of names that are not
  English words).

- Extend CRATE’s GATE pipeline to include or exclude GATE sets, since some
  applications produce results just in one set, and some produce them twice
  (e.g. in the unnamed set, named “”, and in a specific named set).

- Medical eponym list.

**v0.18.50 to v0.18.51, 2018-05-04 to 2018-06-29**

- `IllegalCharacterError` possible from
  :meth:`crate_anon.crateweb.research.models.make_excel`; was raised by
  `openpyxl`. The problem may be that the Excel file format itself prohibits
  some Unicode characters; certainly `openpyxl` does [#excelcharacters]_. See
  `gen_excel_row_elements()` for bugfix. Not all queries require this, but
  anything that allows unrestricted textual/binary content does.

- Change to CPFT-specific SQL in
  :meth:`crate_anon.crateweb.consent.lookup_rio.get_latest_consent_mode_from_rio_generic`.

- Bugfix to :class:`crate_anon.crateweb.extra.pdf.CratePdfPlan`; this failed
  to specify ``wkhtmltopdf_filename``, so if ``wkhtmltopdf`` wasn't found on
  the PATH (e.g. via a Celery task), PDFs were not generated properly.

- Addition of ``processed_at`` to
  :class:`crate_anon.crateweb.consent.models.ContactRequest`.

- Addition of ``processed`` and ``processed_at`` to
  :class:`crate_anon.crateweb.consent.models.ClinicianResponse`.

- Addition of ``processed`` and ``processed_at`` to
  :class:`crate_anon.crateweb.consent.models.ClinicianResponse`.

- Addition of ``skip_letter_to_patient``, ``needs_processing`, ``processed``
  and ``processed_at`` to
  :class:`crate_anon.crateweb.consent.models.ClinicianResponse`.

- Package version changes:

  - amqp from 2.1.3 to 2.3.2;
    https://github.com/celery/py-amqp/blob/master/Changelog
  - arrow from 0.10.0 to 0.12.1;
    https://pypi.org/project/arrow/
  - beautifulsoup4 from 4.5.3 to 4.6.0;
    https://github.com/newvem/beautifulsoup/blob/master/CHANGELOG
  - cardinal_pythonlib from 1.0.15 to 1.0.16
  - celery from 4.0.1 to 4.2.0 (no longer constrained by amqp);
    http://docs.celeryproject.org/en/latest/history/
  - chardet from 3.0.2 to 3.0.4
  - cherrypy from 10.0.0 to 16.0.2;
    https://docs.cherrypy.org/en/latest/history.html
  - colorlog from 2.10.0 to 3.1.4
  - distro from 1.0.2 to 1.3.0
  - django from 1.10.5 to 2.0.6;
    https://docs.djangoproject.com/en/2.0/releases/2.0/
  - django-debug-toolbar from 1.6 to 1.9.1
  - django-extensions from 1.7.6 to 2.0.7
  - django-picklefield from 0.3.2 to 1.0.0
  - django-sslserver from 0.19 to 0.20
  - flashtext from 2.5 to 2.7
  - flower from 0.9.1 to 0.9.2
  - gunicorn from 19.6.0 to 19.8.1
  - kombu from 4.0.1 to 4.1.0 (no longer constrained by amqp, but kombu 4.2.1
    is broken: https://github.com/celery/kombu/issues/870)
  - openpyxl from 2.4.2 to 2.5.4
  - pendulum from 1.3.0 to 2.0.2; see
    https://pendulum.eustace.io/history/
  - psutil from 5.0.1 to 5.4.6
  - pyparsing from 2.1.10 to 2.2.0
  - python-dateutil from 2.6.0 to 2.7.3
  - regex from 2017.1.17 to 2018.6.21
  - semver from 2.7.5 to 2.8.0
  - sortedcontainers from 1.5.7 to 2.0.4
  - SQLAlchemy from 1.1.5 to 1.2.8
  - sqlparse from 0.2.2 to 0.2.4
  - typing from 3.5.3.0 to 3.6.4
  - Werkzeug from 0.11.15 to 0.14.1
  - xlrd from 1.0.0 to 1.1.0
  - (Windows) pypiwin32 from 219 to 223
  - (Windows) servicemanager 1.3.0, as below
  - (Windows) winerror

  .. note::

    If you are using SQL Server, you probably need to upgrade
    ``django-pyodbc-azure`` (from e.g. 1.10.4.0 to 2.0.6.1, with the command
    ``pip install django-pyodbc-azure==2.0.6.1``), or you may see errors from
    ``...\sql_server\pyodbc\base.py`` like "Django 2.0.6 is not supported."

    You may also need to update the database connection parameters; e.g. the
    ``DSN`` key has become ``dsn``; see :ref:`django-pyodbc-azure
    <django_pyodbc_azure>`.

- New :ref:`crate_celery_status <crate_celery_status>` command.

- Changed to using Celery ``--concurrency=1`` (formerly 4) from
  ``launch_celery.py``, as this should prevent multiple Celery threads doing
  the same work twice if you call ``crate_django_manage
  resubmit_unprocessed_tasks`` more than once. There was a risk that this
  breaks Flower or other Celery status monitoring (as it did with Celery
  v3.1.23, but that was a long time ago, and it works fine now.


**v0.18.52, 2018-07-02**

- NLP fields now support a standard ``_srcdatetime`` field; this can be NULL,
  but it's normally specified as a defining ``DATETIME`` field from the source
  database (since most NLP needs an associated date and it's far more
  convenient if this is in the destination database, along with patient ID).
  It's specified directly to the
  :class:`crate_anon.nlp_manager.input_field_config.InputFieldConfig` rather
  than via the ``copyfields``, since we want a consistent date/time field name
  in the NLP output even if there is a lack of naming consistency in the
  source. Search for "new in v0.18.52".

- Possibly a bug fixed within the NLP manager, in relation to recording of
  hashed PKs from tables with non-integer PKs; see
  :meth:`crate_anon.nlp_manager.input_field_config.InputFieldConfig.gen_text`.


**v0.18.53, IN PROGRESS**

- Added ``Client_Demographic_Details.National_Insurance_Number`` and
  ``ClientOtherDetail.NINumber`` to RiO automatic data dictionary generator as
  a sensitive (scrub-source) field; they were marked for code anonymisation but
  not flagged as scrub-source automatically.

- Removed full stop from end of sentence in ``email_clinician.html`` beginning
  "If you’d like help, please telephone the Research Database Manager...",
  since some users copied/pasted the full stop as part of the final e-mail
  address, which bounced. Clarity more important than grammar in this case.

- NLP adds CRATE version column, ``_crate_version``.

- NLP adds "when fetched from database" column, ``_when_fetched_utc``.

- NLP supports "cmm" as an abbreviation for cubic mm (seen in CPFT and as
  per https://medical-dictionary.thefreedictionary.com/cmm).

- ``cardinal_pythonlib==1.0.25`` with updates to :func:`document_to_text`
  parameter handling, then to ``1.0.31``.

- NLPRP draft to 0.1.0.

- ``django==2.0.6`` to ``django==2.1.2`` given security vulnerabilities
  reported in Django versions [2.0, 2.0.8).

- ``django-debug-toolbar==1.9.1`` to ``django-debug-toolbar==1.10.1``

- Improved docstrings.

- Minor bugfixes in ``anonymise.py`` for fetching values from files.

- ``_addition_only`` DDR flag only permitted on PK fields. (Was only attended
  to for them in any case!)


.. rubric:: Footnotes

.. [#f1]
    https://bitbucket.org/zzzeek/sqlalchemy/issues/3504;
    http://docs.sqlalchemy.org/en/latest/changelog/migration_11.html#change-3504;
    http://docs.sqlalchemy.org/en/latest/changelog/changelog_11.html#change-1.1.0b1

.. [#f2]
    https://docs.python.org/3/reference/datamodel.html#object.__hash__;
    http://stackoverflow.com/questions/27522626/hash-function-in-python-3-3-returns-different-results-between-sessions

.. [#f3]
    See also http://stackoverflow.com/questions/5400275/fast-large-width-non-cryptographic-string-hashing-in-python

.. [#f4]
    https://pypi.python.org/pypi/mmh3/2.2;
    https://en.wikipedia.org/wiki/MurmurHash; see how it works using the less
    fast Python version at https://github.com/wc-duck/pymmh3

.. [#f5]
    http://preshing.com/20110504/hash-collision-probabilities/

.. [#xxhash]
    https://cyan4973.github.io/xxHash/

.. [#siphash]
    https://www.131002.net/siphash/

.. [#hashcomparisons]
    https://github.com/rurban/perl-hash-stats#number-of-collisions-with-crc32;
    http://fastcompression.blogspot.co.uk/2012/04/selecting-checksum-algorithm.html;
    http://softwareengineering.stackexchange.com/questions/49550/which-hashing-algorithm-is-best-for-uniqueness-and-speed;
    http://aras-p.info/blog/2016/08/02/Hash-Functions-all-the-way-down/

.. [#dashes]
    https://www.cs.tut.fi/~jkorpela/dashes.html

.. [#ignoreendash]
    Possible that we may need to treat this as a minus sign in some contexts
    later, but this is not implemented yet.

.. [#mysqlrenamedb]
    http://stackoverflow.com/questions/67093/how-do-i-quickly-rename-a-mysql-database-change-schema-name

.. [#sqlserverrenamedb]
    https://msdn.microsoft.com/en-GB/library/ms345378.aspx;
    https://www.mssqltips.com/sqlservertip/1891/best-practice-for-renaming-a-sql-server-database/

.. [#sqlserverfulltext]
    https://technet.microsoft.com/en-us/library/cc721269(v=sql.100).aspx;
    https://msdn.microsoft.com/en-us/library/ms142571(v=sql.120).aspx

.. [#tsql]
    https://msdn.microsoft.com/en-us/library/bb510741.aspx

.. [#excelcharacters]
    https://stackoverflow.com/questions/28837057/pandas-writing-an-excel-file-containing-unicode-illegalcharactererror;
    https://openpyxl.readthedocs.io/en/2.5/_modules/openpyxl/utils/exceptions.html;
    in particular, see check_string() in
    http://openpyxl.readthedocs.io/en/stable/_modules/openpyxl/cell/cell.html
