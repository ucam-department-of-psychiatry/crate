..  crate_anon/docs/source/changelog.rst

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

.. include:: <isonum.txt>
.. https://docutils.sourceforge.io/docs/ref/rst/definitions.html
.. but see also site-packages/docutils/parsers/rst/include


Change log/history
==================

Contributors
------------

- Rudolf Cardinal <rudolf@pobox.com>, 2015–.
- Francesca Spivack, 2018–2020.
- Martin Burchell, 2020–.

Quick links:

- :ref:`2015 <changelog_2015>`
- :ref:`2016 <changelog_2016>`
- :ref:`2017 <changelog_2017>`
- :ref:`2018 <changelog_2018>`
- :ref:`2019 <changelog_2019>`
- :ref:`2020 <changelog_2020>`
- :ref:`2021 <changelog_2021>`

Changes
-------

.. _changelog_2015:

2015
~~~~

**2015-02-18**

- Started.

**v0.03, 2015-03-19**

- Bug fix for incremental update (previous version inserted rather than
  updating when the source content had changed); search for
  ``update_on_duplicate_key``.

- Checks for missing/extra fields in destination.

- “No separator” allowed for
  :func:`crate_anon.anonymise.anonregex.get_date_regex_elements`, allowing
  anonymisation of e.g. ``19Mar2015``, ``19800101``.

- New default ``at_word_boundaries_only=False`` for
  :func:`crate_anon.anonymise.anonregex.get_date_regex_elements`, allowing
  anonymisation of ISO8601-format dates (e.g. ``1980-10-01T0000``), etc.

- Similar option for
  :func:`crate_anon.anonymise.anonregex.get_code_regex_elements`.

- Similar option for
  :func:`crate_anon.anonymise.anonregex.get_string_regex_elements`.

- Options in config to control these.

- Fuzzy matching for
  :func:`crate_anon.anonymise.anonregex.get_string_regex_elements`;
  ``string_max_regex_errors`` option in config. The downside is the potential
  for greedy matching; for example, if you anonymise “Ronald MacDonald” with
  “Ronald” and “MacDonald”, you can end up with “XXX MacXXX”, as the regex
  greedy-matches “Donald” to “Ronald” with a typo, and therefore fails to
  process the whole “MacDonald”. On the other hand, this protects against
  simple typos, which are probably more common.

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

- ``min_string_length_for_errors`` option

- ``min_string_length_to_scrub_with`` option

- ``words_not_to_scrub`` option

- bugfix: date regex couldn't cope with years prior to 1900

- :func:`crate_anon.anonymise.patient.gen_all_values_for_patient` was
  inefficient in that it would process the same source table multiple times to
  retrieve different fields.

- ``ddgen_index_fields`` option

- simplification of
  :func:`crate_anon.anonymise.anonregex.get_anon_fragments_from_string`

- ``SCRUBMETHOD.CODE``, particularly for postcodes. (Not very different from
  ``SCRUBMETHOD.NUMERIC``, but a little different.)

- ``debug_row_limit`` applies to patient-based tables (as a per-thread limit);
  was previously implemented as a per-patient limit, which was silly.

- Indirection step in config for destination/admin databases.

- ``ddgen_allow_fulltext_indexing`` option, for old MySQL versions.

**v0.06, 2015-06-25**

- Option: ``replace_nonspecific_info_with``

- Option: ``scrub_all_numbers_of_n_digits``

- Option: ``scrub_all_uk_postcodes``

**v0.06, 2015-07-14**

- bugfix: if a source scrub-from value was a number with value ``'.'``, the
  regex went haywire... so regex builders now check for blanks.

**v0.07, 2015-07-16**

- ``regex.ENHANCEMATCH`` flag tried unsuccessfully (segmentation fault, i.e.
  internal error in ``regex`` module, likely because generated regular
  expressions got too complicated for it).

**v0.08, 2015-07-20**

- ``SCRUBMETHOD.WORDS`` renamed ``SCRUBMETHOD.WORDS`` [? typo in changelog!]

- ``SCRUBMETHOD.PHRASE`` added

- ``ddgen_scrubmethod_phrase_fields`` added

**v0.09, 2015-07-28**

- ``debug_max_n_patients`` option, used with
  :func:`crate_anon.anonymise.anonymise.gen_patient_ids`, to reduce the number
  of patients processed for “full rebuild” debugging.

- ``debug_pid_list`` option, similarly

**v0.10, 2015-09-02 to 2015-09-13**

- Opt-out mechanism.

- Default hasher changed to SHA256.

- Bugfix to datatypes in
  :func:`crate_anon.anonymise.delete_dest_rows_with_no_src_row`.

**v0.11, 2015-09-16**

- Split main source code for simplicity.

**v0.12, 2015-09-21**

- Database interface renamed from mysqldb to mysql, to allow for PyMySQL
  support as well (backend details otherwise irrelevant to front-end
  application).

**v0.13, 2015-10-06**

- Added TRID.


.. _changelog_2016:

2016
~~~~

**2016-02-09**

- SQL helpers for free-text search.
- Massive SQL speedup for fetching/caching table info from database.
- NOTE that highlighting will not always work for unusual characters, e.g.
  apostrophes ('); see research.html_functions.make_result_element This is
  because we apply django.utils.html.escape before we apply the highlighting,
  and django.utils.html.escape transforms "'" into "&#39;". But we can't
  highlight and then escape, because we need the HTML in the highlighting.
  Not critical.

**v0.14.0, 2016-03-10**

- Code cleanup.

- HMAC for RID generation, replacing simpler hashes, for improved security.
  Default becomes ``HMAC_MD5``.

- New option: ``secret_trid_cache_tablename``

- Removed option: ``words_not_to_scrub``

- New options: ``whitelist_filenames`` (replaces ``words_not_to_scrub``),
  ``blacklist_filenames``.

- Transition from ``cardinal_pythonlib.rnc_db`` to SQLAlchemy for anonymiser
  database interface.

- Environment variable changed from ``CRATE_LOCAL_SETTINGS`` to
  ``CRATE_WEB_LOCAL_SETTINGS`` and coded into
  :mod:`crate_anon.crateweb.config.constants`.

- Web front end now happy getting structure from SQL Server and PostgreSQL.

- Windows support. Windows XP not supported as Erlang (and thus RabbitMQ) won’t
  run on it from the distributed binaries. Windows 10 works fine.

- Semantic versioning.

**v0.16.0, 2016-06-04**

- Fixes to work properly with SQL Server, including proper automatic conversion
  of ``VARCHAR(MAX)`` and ``NVARCHAR(MAX)`` to MySQL ``TEXT`` fields. Note:
  also needs SQLAlchemy 1.1 or higher [#f1]_, currently available only via (1)
  fetching source via ``git clone https://github.com/zzzeek/sqlalchemy`` and
  changing into the ‘sqlalchemy’ directory this will create; (2) activating
  your CRATE virtual environment; (3) ``pip install .`` to install SQLAlchemy
  from your source copy. Further note: as of v0.18.2, this is done via PyPI
  again.

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

- v0.18.1 (2016-11-04): new ``anonymise_numbers_at_numeric_boundaries_only``
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
  operator, ``%``. In addition, we store PK values to speed up incremental
  updates. It becomes messy if we have to cope with lots and lots of types of
  PKs. Also, Python’s :func:`hash` function is inconsistent across invocations
  [#f2]_. This is not a cryptographic application, so we can use anything
  simple and fast [#f3]_. It looks like MurmurHash3 is suitable (hash DDoS
  attacks are not relevant here) [#f4]_. However, the problem then is with
  collisions [#f5]_. We want to ask “has this PK been processed before?”
  Realistically, the only types of PKs are integers and strings; it would be
  crazy to use floating-point numbers or BLOBs or something. So let’s put a cap
  at ``VARCHAR(n)``, where ``n`` comes from ``MAX_STRING_PK_LENGTH``; store a
  64-bit integer hash for speed, and then use the hash to say quickly “no, not
  processed” and check the original PK if processed. If the PK field is
  integer, we can just use the integer field for the PK itself. Note that the
  ``delete_where_no_source`` function may be imperfect now under hash
  collisions (and it may be imperfect in other ways too).

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

- Speed increases by not requesting unnecessary ``ORDER BY`` conditions.

- Commit-every options for NLP (every n bytes and/or every n rows).

- Regex NLP for ACE, mini-ACE, MOCA.

- Timing framework for NLP (for when it’s dreadfully slow and you think the
  problem might be the source database).

- Significant NLP performance enhancement by altering progress DB lookup
  methods.

**v0.18.9, 2016-12-02**

- Regex NLP: option in
  :class:`crate_anon.nlp_manager.regex_parser.SimpleNumericalResultParser` to
  take absolute values, e.g. to deal with text like ``Na-142, K-4.1, CRP-97``,
  which use ``-`` simply as punctuation, rather than as a minus sign. Failing
  to account for these would distort results.

- No attempt is made to specify maximum or minimum values, which can easily be
  excluded as required from the resulting data set. One could of course use the
  SQL ``ABS()`` function to deal with negative values post hoc, but some things
  have no physical meaning when negative, such as a white cell count or CRP
  value, so it’s preferable to fix these at source to reduce the chance of user
  error through not noticing negative values.

- The ``take_absolute`` option is applied to: CRP, sodium, TSH, BMI, MMSE, ACE,
  mini-ACE, MOCA, ESR, and white cell/differential counts. (NLP processors for
  height, BP already enforced positive values. Weight must be able to handle
  negatives, like “weight change –0.4kg”.)

- Similarly, hyphen followed by whitespace treated as ignorable in regex NLP
  (e.g. in ``weight - 48 kg``; though spaces are meaningful for mathematical
  operations (“a – b = c”), it is syntactically wrong to use ``- 4`` as a unary
  minus sign to indicate a negative number (–4) and much more likely that this
  context means a dash.

- En and em dashes, and a double-hyphen as a dash (``--``) treated as
  ignorables in regex NLP.

- At present, Unicode minus signs (``−``) are not handled. For reference
  [#dashes]_:

    =============== =========== =========================== ======================================
    name            character   code                        handling
    =============== =========== =========================== ======================================
    hyphen-minus    ``-``       Unicode 002D or ASCII 45    minus sign if context correct
    formal hyphen   ``‐``       Unicode 2010                not handled at present
    minus sign      ``−``       Unicode 2212                not handled at present
    en dash         ``–``       Unicode 2013                treated as ignorable [#ignoreendash]_
    em dash         ``—``       Unicode 2014                treated as ignorable
    =============== =========== =========================== ======================================

- Improved regex self-testing, including new test framework in
  :mod:`crate_anon.nlp_manager.test_all_regex`.

**v0.18.10, 2016-12-11**

- Full support for SQL Server as the backend.

- Hot-swapping databases (compare MySQL [#mysqlrenamedb]_): you can rename
  databases, so this seems OK [#sqlserverrenamedb]_.

- Full-text indexing: optional in SQL Server 2008, 2012, 2014 and 2016
  [#sqlserverfulltext]_; basic SELECT syntax is ``WHERE CONTAINS(fieldname,
  "word")``, and index creation with ``CREATE FULLTEXT INDEX ON table_name
  (column_name) KEY INDEX index_name ...``. Added to
  :mod:`crate_anon.common.sqla`.

- Support for SQL query building, with user-configurable selector mechanism.
  See Transact-SQL syntax reference [#tsql]_. We use the Django setting
  ``settings.RESEARCH_DB_DIALECT`` to govern this.

**v0.18.11, 2016-12-19**

- Tweaks/bugfixes for RiO preprocessor, and for anonymisation to SQL Server
  databases.

- Local help HTML offered via web front end.


.. _changelog_2017:

2017
~~~~

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

- Full-text finder generates ``CONTAINS(column, 'word')`` properly for SQL
  Server.

- Bugfix to Patient Explorer (wasn’t offering WHERE options always).

- “Table browser” views in Patient Explorer

- Bugfix to Windows service. Problem: a Python process was occasionally being
  “left over” by the Windows service, i.e. not being killed properly. Process
  Explorer indicated it was the one launched as ``python
  launch_cherrypy_server.py``. The Windows event log has a message reading
  “Process 1/2 (Django/CherryPy) (PID=62516): Subprocess finished cleanly
  (return code 0).” The problem was probably that in
  :mod:`crate_anon.crateweb.core.management.commands.runcpserver`, the
  ``cherrypy.engine.stop()`` call was only made upon a KeyboardInterrupt
  exception, and not on other exceptions. Solution: broadened to all
  exceptions.

**v0.18.17, 2017-03-17**

- Removed erroneous debugging code from
  :meth:`crate_anon.nlp_manager.parse_medex.Medex.parse`.

- If you mis-configured the Java interface to a GATE application, it crashed
  quickly, which was helpful. If you mis-configured the Java interface to
  MedEx, it tried repeatedly. Now it crashes quickly.

**v0.18.18 to v0.18.23, 2017-04-28**

- Paper published on 2017-04-26 as **Cardinal (2017), BMC Medical Informatics
  and Decision Making 17:50; http://www.pubmed.gov/28441940;
  https://doi.org/10.1186/s12911-017-0437-1.**

- Support for configurable paths for finding on-disk documents (e.g. from a
  combination of a fixed root directory, a patient ID, and a filename).

**v0.18.23 to v0.18.33, 2017-05-02**

- NLP ``value_text`` field (``FN_VALUE_TEXT`` in code) given maximum length,
  rather than 50, for the regex parsers, as it was overflowing (e.g. when a lot
  of whitespace was present). See
  :meth:`crate_anon.nlp_manager.regex_parser.NumericalResultParser.dest_tables_columns`.

- Supports more simple text file types (``.csv``, ``.msg``, ``.htm``).

- New option: ``ddgen_rename_tables_remove_suffixes``.

- Bugfix to CRATE GATE handler’s stdout-suppression switch.

- New option: ``ddgen_extra_hash_fields``.

- **PCMIS preprocessor.**

- **Support non-integer PIDs and MPIDs.** Note that the hashing is based on a
  string representation, so if you have one database using an integer NHS
  number, and another using a string NHS number, the same number will hash to
  the same result if you use the same key.

- Hashing of additional fields, initially to support the PCMIS ``CaseNumber``
  (as well as ``PatientId``).

**v0.18.34 to v0.18.39, 2017-06-05**

- For SLAM BRC GATE pharmacotherapy app: add support for output columns whose
  SQL column name is different to the GATE tag (e.g. when ``dose-value`` must
  be changed to ``dose_value``); see **``renames``** option. GATE output fields
  now preserve case. Another option (``null_literals``) to allow GATE output of
  ``null`` to be changed to an SQL NULL. Also added ``_set`` column to GATE
  output.

**v0.18.40, 2017-07-20**

- Fixed Python type-checking bug in
  :meth:`crate_anon.common.extendedconfigparser.ExtendedConfigParser.get_pyvalue_list`;
  changed from ``Generic`` to ``Any``.

**v0.18.41, 2017-07-21**

- Support for MySQL ``ENUM`` types. However, see
  http://komlenic.com/244/8-reasons-why-mysqls-enum-data-type-is-evil/ also!

**To v0.18.46, 2017-07-28 to 2017-08-05**

- Fix to ``coerce_to_date`` (for date types), renamed to
  ``coerce_to_datetime``.

- NLP bug fixed relating to a missing ``pytz`` import.

- Fixes to NLP, including accepting views (not just tables) as input. Note that
  under SQL Server, you should not have to specify ‘dbo’ anywhere in the config
  (but consider setting ``ALTER USER... WITH DEFAULT SCHEMA`` as above).

- Manual and 2017 paper distributed with package.

- Shift some core stuff to cardinal_pythonlib to reduce code duplication with
  other projects.

**v0.18.48, 2017-11-06**

- Clinician view: find text across a database, for an identified patient. See
  ``crate_anon.crateweb.research.views.all_text_from_pid``.

  - Rationale: Should privileged clinical queries be in any way integrated
    with CRATE? Advantages would include allowing the receiving user to run
    the query themselves without RDBM intervention and RDBM-to-recipient data
    transfer considerations, while ensuring the receiving user doesn’t have
    unrestricted access (e.g. via SQL Server Management Studio). Plus there may
    be a UI advantage.

- Clinician view: look up (M)RIDs from (M)PIDs. Intended purpose for this and
  the preceding function: “My clinical front end won’t tell me if my patient’s
  ever had mirtazapine. I want to ask the research database.” (As per CO’L
  request 2017-05-04.) See ``crate_anon.crateweb.research.views.ridlookup``.

- Code to generate and test demonstration databases improved.


.. _changelog_2018:

2018
~~~~

**v0.18.49, 2018-01-07, 2018-03-21, 2018-03-27, published 2018-04-20**

- Use ``flashtext`` (rather than ``regex``) for denylisting words; this is
  much faster and allows large denylists (e.g. a long list of all known
  forenames/surnames).

- Provides the ``crate_fetch_wordlists`` tool to fetch names and English words
  (and perform in-A-not-B functions, e.g. to generate a list of names that are
  not English words).

- Extend CRATE’s GATE pipeline to include or exclude GATE sets, since some
  applications produce results just in one set, and some produce them twice
  (e.g. in the unnamed set, named ``""``, and in a specific named set).

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
  :mod:`crate_anon.tools.launch_celery`, as this should prevent multiple Celery
  threads doing the same work twice if you call ``crate_django_manage
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


**v0.18.53, to 2018-10-24**

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

- To ``cardinal_pythonlib==1.0.25`` with updates to :func:`document_to_text`
  parameter handling, then to ``1.0.32``.

  - Note that ``cardinal_pythonlib==1.0.25`` also fixes a bug related to
    SQLAlchemy that manifested as ``AttributeError: module
    'sqlalchemy.sql.sqltypes' has no attribute '_DateAffinity'``.

- NLPRP draft to 0.1.0.

- ``django==2.0.6`` to ``django==2.1.2`` given security vulnerabilities
  reported in Django versions [2.0, 2.0.8).

- Bugfix: ``mark_safe`` decorator added to all Django admin site parts with
  ``allow_tags = True`` set (for embedded URLs).

- ``django-debug-toolbar==1.9.1`` to ``django-debug-toolbar==1.10.1``

- Improved docstrings.

- Minor bugfixes in :mod:`crate_anon.anonymise.anonymise` for fetching values
  from files.

- ``_addition_only`` DDR flag only permitted on PK fields. (Was only attended
  to for them in any case!)

- Bugfix to :func:`crate_anon.crateweb.consent.views.validate_email_request`
  and :func:`crate_anon.crateweb.consent.views.validate_letter_request`; these
  were returning rather than raising. Testing showed that something else was
  also blocking permission to access such things inappropriately, but fixed
  anyway!

- Renamed ``generate_fake_nhs`` to ``generate_random_nhs`` to emphasize what
  this does.

- :meth:`crate_anon.crateweb.consent.models.Study.html_summary`

- Sitewide queries, editable by RDBM.

- Restrict anonymiser to specific patient IDs (for subset generation +/- custom
  pseudonyms).


**v0.18.54, 2018-10-26**

- Deferred load of clinical team info. (Main research database structure is
  still loaded at the start; I think my intention was to fail as early as
  possible if it's going to fail, and/or ensure that "filling the cache" time
  is not experienced by the end user).

- Fixed packaging bug in ``setup.py``.

- 2018-10-21: Fixed bug in :menuselection:`RDBM admin --> Studies`:

  .. code-block:: none

    OperationalError at /mgr_admin/consent/study/

    (1054, "Unknown column 'consent_study.p_summary' in 'field list'")

  Changed ``p_summary`` to a property.


**v0.18.55, 2018-11-02**

- In :meth:`crate_anon.anonymise.altermethod.AlterMethod._extract_text_func`,
  pre-check that a file exists (to save time if it doesn't).

- Bugfix to ``cardinal_pythonlib`` (now v1.0.33) in the autotranslation of SQL
  Server ``TIMESTAMP`` fields.

- Changed caching for
  :class:`crate_anon.crateweb.research.research_db_info.SingleResearchDatabase`
  to make command-line startup faster (at the expense of first-fetch speed).


**v0.18.56, 2018-11-02**

- ``cardinal_pythonlib==1.0.36``

- Bugfix to ``setup.py``; Java files were not being distributed properly.

- Performance optimization to query "column filtering" for "show only columns
  containing no NULL values", and more generally optimized; should run queries
  only once per web session.

- Bugfix to
  :func:`crate_anon.crateweb.research.models.get_executed_researchdb_cursor`,
  which was double-wrapping a database cursor incorrectly.

**v0.18.57, 2018-12-11**

- New lithium NLP processor (still needs external validation).

- Bugfix: "cmm" was meant to be accepted as an abbreviation for "cubic mm" as
  per v0.18.53 above, but wasn't. Rechecked all with
  :mod:`crate_anon.nlp_manager.test_all_regex` and
  added additional specific tests for this unit in
  :func:`crate_anon.nlp_manager.regex_units.test_unit_regexes`. All passing.

**v0.18.58, 2018-12-23**

- Clinician requests added so that a clinician can request that their patient
  is included in a study.

- Bugfix to
  :func:`crate_anon.preprocess.preprocess_rio.main`. Changed 'progargs.rio'
  to 'rio'.

**v0.18.59, 2018-12-24**

- Bugfix to
  :func:`clinician_initiated_contact_request`. Now checks that patient's
  consent mode is green or yellow before confirming request.

**v0.18.60, 2018-12-27**

- New look of website.

- Bugfix to clinician requests. Also now sends a more appropriate email
  in these cases.


.. _changelog_2019:

2019
~~~~

**v0.18.61, 2019-01-15**

- Updated version of Django in ``setup.py``.

- Flag on website to check if query has been run since last database update.

- Option of column in anonymiser output specifying when processed.

**v0.18.62, 2019-02-09**

- Improved the ``crate_test_extract_text`` command
  (:mod:`crate_anon.anonymise.test_extract_text`), including errorlevel/return
  codes to detect text presence.

- Bump to ``cardinal_pythonlib==1.0.47``. Note that this now raises an
  exception from :func:`cardinal_pythonlib.extract_text.document_to_text` if
  a filename is passed and the file doesn't exist.

**v0.18.63, 2019-02-12**

- NLP web server based on the NLPRP API.

- Bugfix to the website string finder - 'text fields' now includes
  'NVARCHAR(-1)'.

**v0.18.64, 2019-02-21**

- NLP for glucose cholesterol (LDL, HDL, total), triglycerides, HbA1c
  (still need external validation).

**v0.18.65, 2019-03-04 to 2019-03-25**

- NLP for potassium, urea, creatinine, haemoglobin, haematocrit (still need
  external validation).

- At some point before this: SQL helpers to find :ref:`drug classes/types
  <sql_find_drug_type>` (e.g. "atypical antipsychotics", "SSRIs"), as per
  JL's idea of 2018-01-08.

- At some point before this: research query options to show a subset of
  columns.

- At some point before this: "Clinician asks for a study pack" -- create a
  contact request that's pre-authorized by a clinician (who might want to pass
  on the pack themselves or delegate the RDBM to do it).

- :ref:`Standard site queries <site_queries>` now handle the following problem:

  - With regular data updates there might be problems with queries returning
    different results if rerun a week later, so might be worth returning a
    timestamp of some type, like: ``MAX(DATE_CREATED) FROM
    RIO.DBO.Clinical_Documents + MAX(whenprocessedutc)) FROM
    [RiONLP].[dbo].[crate_nlp_progress] + …``

**v0.18.66, 2019-03-29**

- Update to ``CrateGatePipeline.java`` to support an option to continue after
  GATE crashes.

**v0.18.67, 2019-03-30 to 2019-03-31**

- ``semver`` to ``semantic_version``; consistent with CamCOPS and better (and
  not actually used hitherto by CRATE!)

- NLPRP constants and core API.

- Move to Python 3.6 (already the minimum in CPFT), allowing f-strings.

- f-strings. (Note: use Alt-Enter in PyCharm.)

- ``CrateGatePipeline.java`` supports continuation after a Java
  RuntimeException ("bug in GATE code").

**v0.18.68, 2019-04-09**

- Creatinine regex supports mg/dl units as well as micromolar.

- ``url`` and ``max_content_length`` configurable.

- Bugfixes to :func:`crate_anon.nlp_manager.nlp_manager.send_cloud_requests`
  and :meth:`crate_anon.nlp_webserver.views.NlpWebViews.show_queue`.

**v0.18.70, 2019-04-17**

- PyPI distribution properly contains ``nlprp`` directory.

**v0.18.71, 2019-05-13**

- Bugfix to nlp incremental mode.

- Use of tokens in cloud NLP and option not to verify SSL.

**v0.18.72, 2019-05-16**

- Bugfix to :class:`crate_anon.nlp_manager.cloud_parser.CloudRequest` to
  convert string datetime back to datetime object. (MySQL automatically
  converts when writing to the database, but MSSQL doesn't.)

**v0.18.73, 2019-05-21**

- Only do nlp processing on records with alphanumeric characters.

- Do highlighting only once per query, then save the highlighted version in
  an attribute of the :class:`crate_anon.crateweb.Query` class.

**v0.18.74, 2019-05-21**

- Changed migrations to make them compatible with SQL Server.

**v0.18.75, 2019-06-06**

- Long queries are now hidden on website in order to avoid long render time.

- :class:`crate_anon.nlp_manager.cloud_parser.CloudRequest` now extracts
  content from GATE processors based on the start and end indexes.

**v0.18.76, 2019-06-12**

- Option to truncate source data in nlp and to mark truncated records as
  processed or not.

- Upgrade to ``SQLAlchemy==1.3.0`` and ``django==2.2.2``.

- Bugfix to :mod:`crate_anon.nlp_webserver.views` - ``include_text`` and
  ``client_job_id`` are obtained from args rather than top-level of the
  request.

- In :mod:`crate_anon.nlp_manager.nlp_manager`, open file to write after
  completing retrieval of requests so if there is a problem you don't lose all
  your queue_ids.

- Records will not be sent with no word character.

- :meth:`session.remove()` has been added to to
  :mod:`crate_anon.nlp_webserver.views`.

**v0.18.77, 2019-06-12**

- :mod:`crate_anon.nlp_manager.cloud_parser` won't crash if one request gives
  an error. This is so we don't lose all data if just one request doesn't work.

**v0.18.78, 2019-06-12**

- In :func:`crate_anon.nlp_manager.nlp_manager.process_cloud_nlp`, use append
  file instead of write, so that, is there's a problem part-way through, we
  don't lose all data.

**v0.18.79, 2019-06-13**

- Downgraded to ``SQLAlchemy==1.2.8``, which it was before and
  ``django==2.1.9``, which is higher than it was before, because the updates
  where causing clashes with ``django-pyodbc-azure``.

- Log error messages from server in
  :meth:`crate_anon.nlp_manager.cloud_parser.CloudRequest.list_processors`.

**v0.18.80, 2019-06-13**

- Sending requests to the cloud servers is broken up into blocks so that the
  database can be written to periodically.

- New sessions for each request on the server-side.

**v0.18.81, 2019-06-17**

- Microsoft specific bugfix in cloud nlp.

- Commit every n records, where n is specified by the user, in retrieval of
  cloud requests.

**v0.18.82, 2019-06-17**

- Used rate limiter.

**v0.18.83, 2019-06-23**

- Bugfix to
  :meth:`crate_anon.nlp_manager.cloud_parser.CloudRequest.get_nlp_values_gate`
  and
  :meth:`crate_anon.nlp_manager.cloud_parser.CloudRequest.get_nlp_values_internal`
  so that they don't try to fish out results for a processor when there are
  errors.

- Retry after connection failure in :mod:`crate_anon.nlp_manager.cloud_parser`.

**v0.18.85, 2019-07-21**

- Regexes: ``MICROLITRE``, ``CUBIC_MM_OR_MICROLITRE``,
  ``CELLS_PER_CUBIC_MM_OR_MICROLITRE``.
- ``HGB`` as synonym for haemoglobin in
  :class:`crate_anon.nlp_manager.parse_haematology.Haemoglobin`.
- ``OPTIONAL_POC`` element in several biochemistry/haematology parsers
- :class:`crate_anon.nlp_manager.parse_haematology.WbcBase` allows "per
  microlitre" as well as "per cubic mm".
- :class:`crate_anon.nlp_manager.parse_haematology.Platelets`
- :class:`crate_anon.nlp_manager.parse_haematology.RBC`
- logging, rather than :func:`print`, for regex testing
- mention ``urllib3==1.23`` explicitly in ``setup.py`` (used by ``requests``)
- ... then ``urllib==1.24.2`` to avoid a high severity security vulnerability
  (automatic Github warning; well done, it).

**v0.18.86, 2019-08-06**

- :ref:`NLPRP <nlprp>` v0.2.0, with schema support.
- ``django==2.1.11`` (from 2.1.10), Github-prompted security fix.
- ``sqlalchemy==1.3.6`` (from 1.2.8); needed to go to 1.3.0 (Github-prompted
  security fix) but we'd noted Windows problems with 1.3.0; looks like SQL
  Server regression was fixed in 1.3.1 (see
  https://docs.sqlalchemy.org/en/13/changelog/changelog_13.html) so going to
  1.3.6.
- ``python-dateutil==2.6.1`` (required by ``pandas``), from 2.6.0 (was
  blocking readthedocs updates).
- ``cardinal_pythonlib==1.0.61`` (from 1.0.58); bugfix in log probability
  handling; fix relating to Django ``settings.XSENDFILE``.
- Bugfix to :class:`crate_anon.nlp_manager.parse_cognitive.MocaValidator`; was
  looking at the mini-ACE instead!
- Abstract base classes in NLP parsers to assist with NLPRP work.
- Comments for NLP output columns (for build-in fields and those specified by
  :ref:`destfields <nlp_config_destfields>`).
- Cloud NLP config modularized.
  **Breaking change to existing cloud NLP configs.**
- Some code simplification, including classes:
  - :class:`crate_anon.nlp_manager.errors.NlprpError`
  - :class:`crate_anon.nlp_manager.tasks.NlpServerResult`
  - :class:`crate_anon.nlp_manager.views.NlprpProcessRequest`
- Reset ``count`` in :func:`crate_anon.nlp_manager.retrieve_nlp_data` after
  committing.
- Renamed ``max_retries`` to :ref:`max_tries <nlp_config_max_tries>`.
- Moved "verify SSL" option from ``--noverify`` on the command line to the
  :ref:`verify_ssl <nlp_config_verify_ssl>` parameter.
- Parameterized maximum request frequency via :ref:`rate_limit_hz
  <nlp_config_rate_limit_hz>`.
- Split ``limit_before_write`` parameter into :ref:`max_records_per_request
  <nlp_config_max_records_per_request>` and :ref:`limit_before_commit
  <nlp_config_limit_before_commit>`.
- Renamed ``nlp_web`` to ``nlp_webserver`` for clarity (since "web" might refer
  to client or server).
- Split ``nlp_webserver/constants.py`` into
  :mod:`crate_anon.nlp_webserver.constants` and
  :mod:`crate_anon.nlp_webserver.settings` so "constants" has no import
  side-effects
- More compact encoding (including for CRATE web Javascript) via
  :data:`crate_anon.constants.JSON_SEPARATORS_COMPACT`.
- Removed dependencies:

  - ``typing`` -- now using Python 3.6
  - ``Werkzeug`` -- no longer in use

- Pinned versions:

  - ``pytz==2018.5``

- Added requirements:

  - ``cairosvg==2.4.0``
  - ``pillow==6.1.0``

- Context-sensitive help on the CRATE web site, via
  :class:`crate_anon.common.constants.HelpUrl`.

- Amended ``show_sitewide_queries.html`` to remove ``<form>`` children of
  ``<tr>``; see

  - https://stackoverflow.com/questions/7737163/form-within-table-row-tag
  - https://stackoverflow.com/questions/1249688/html-is-it-possible-to-have-a-form-tag-in-each-table-row-in-a-xhtml-valid-way/16941843

- NLPRP client sets ``include_text`` to ``False`` (see :ref:`process
  <nlprp_process>`).

- Removed reference to Django setting ``SEND_BROKEN_LINK_EMAILS`` (and thus
  ``MANAGERS`` since we won't enable Django's ``BrokenLinkEmailsMiddleware``);
  see https://docs.djangoproject.com/en/dev/internals/deprecation/.

- Experimental: :ref:`archive <archive>` system.

  - Removed
    :class:`cardinal_pythonlib.django.middleware.DisableClientSideCachingMiddleware`
    since we may want to do some caching.

- ``cardinal_pythonlib==1.0.63``

- Added standard ``tense_text`` column to NLP classes
  :class:`crate_anon.nlp_manager.parse_clinical.Bp`,
  :class:`crate_anon.nlp_manager.regex_parser.NumeratorOutOfDenominatorParser`.

- Python NLP:

  - CRP value column case changed from ``value_mg_l`` to ``value_mg_L``.
  - Creatinine value column renamed from ``value_mmol_L`` (wrong!) to
    ``value_micromol_L``.
  - HbA1c value column renamed from ``value_mmol_L`` (wrong!) to
    ``value_mmol_mol``.
  - Haematocrit value column case changed from ``value_l_l`` to ``value_L_L``.
  - Haemoglobin value column case changed from ``value_g_l`` to ``value_g_L``.

- GATE parser now avoids stripping terminal tabs (now just newlines), removing
  error messages saying "Bad chunk, not of length 2". See
  :meth:`crate_anon.nlp_manager.parse_gate.Gate.parse`.

- :class:`crate_anon.crateweb.research.models.PatientExplorer` use is audited.


**v0.18.87, 2019-09-30**

- NLP web server performance tweaks; database structure changes.

- Remove dependence on ``cardinal_pythonlib.rnc_db``, which is trivial but
  gives a warning.

- ``cardinal_pythonlib==1.0.65``

- readthedocs.org problems fixed; see

  - environment variable ``_SPHINX_AUTODOC_IN_PROGRESS`` (re errors from
    docs build environment)
  - ``readthedocs.yml`` (re resource usage)
  - all ``.ini`` files were being ignored (despite being fine on a local Sphinx
    build) -- this was a ``.gitignore`` bug.


**v0.18.88 to 0.18.91, 2019-10-06 to 2019-10-07**

- We were seeing :exc:`BrokenPipeError` exceptions when very large chunks of
  text (e.g. 27 Mb) were being sent to GATE processors under Windows. This was
  due to a bug in the DOCX text extractor. So:

  - new :exc:`crate_anon.nlp_manager.base_nlp_parser.TextProcessingFailed`
    exception;

  - :exc:`BrokenPipeError` exceptions now trapped by the GATE and MedEx
    processors (leading to a log error, a restart of the processor, and a
    :exc:`crate_anon.nlp_manager.base_nlp_parser.TextProcessingFailed` error);

  - ``cardinal_pythonlib==1.0.67``, which has improvements to DOCX table
    extraction;

  - right-strip all extracted text

**v0.18.92, 2019-10-10**

- Bugfix: tools that were unrelated to the NLP web server were importing its
  settings (so requiring a dummy config file).

- ``crate_email_rdbm`` tool

- Bugfix in the way that ``postcodes.py`` imported from
  :mod:`cardinal_pythonlib.extract_text`.

- ``cardinal_pythonlib==1.0.73``

**v0.18.93, 2019-11-19**

- New option :ref:`add_mrid_wherever_rid_added <add_mrid_wherever_rid_added>`.

  Preceding thoughts:

  - Option to add MRID to every table, to make cross-database queries simpler?

    - Column would have to support NULL values; not all patients with a PID
      (e.g. local identifier) will have a MPID (e.g. national identifier).
    - Would not require sequencing of tables during anonymisation, since the
      MRID should be found via
      :meth:`crate_anon.anonymise.patient.Patient._build_scrubber`.
    - Would involve modifying
      :func:`crate_anon.anonymise.anonymise.process_table` to call
      :meth:`crate_anon.anonymise.patient.Patient.get_mrid`, possibly where it
      checks for a column being the primary PID, and adding an extra row there
      subject to a flag.
    - The flag relates to the whole database rather than a specific row, so
      it should probably be in the config file -- e.g. named
      ``add_mrid_wherever_rid_added``, within the ``[main]`` section, and the
      "Output fields and formatting" subsection.
    - Might also need an option to index that field automatically (true by
      default) -- *indexed automatically*.

- Update ``pillow`` from 6.1.0 to 6.2.0
  (https://nvd.nist.gov/vuln/detail/CVE-2019-16865).

- :class:`crate_anon.nlp_manager.parse_biochemistry.TotalCholesterol` was
  incorrectly labelling its output "HDL cholesterol"; changed to "Total
  cholesterol".

- ``cardinal_pythonlib==1.0.80``, including a better call to Celery that
  handles a Ctrl-C to the Python process better (via the ``nice_call``
  function). See CamCOPS documentation for more detail.

**v0.18.94, 2019-12-05**

- Option to filter out free text; see ``--free_text_limit``; see
  :ref:`crate_anonymise <crate_anonymise>`.

- Option to exclude all text fields which are set to be scrubbed via
  ``--excludescrubbed``.

- Temporary bugfix to get round a bug in the ``flashtext`` module.

- On crash, show which record is being processed in anonymiser.

- Allow option 'C' ('patient is definitely ineligible') for all clinician
  responses to contact requests.

**v0.18.95, 2019-12-10**

- Bugfix to
  :func:`crate_anon.anonymise.anonymise.process_nonpatient_tables`.


.. _changelog_2020:

2020
~~~~

**v0.18.96, 2020-01-07**

- Security fixes for external dependencies:

  - waitress from 1.4.1 to 1.4.2
    (https://github.com/advisories/GHSA-m5ff-3wj3-8ph4;
    https://github.com/advisories/GHSA-968f-66r5-5v74)

  - django from 2.1.11 to 2.1.15
    (https://github.com/advisories/GHSA-hvmf-r92r-27hr)

**v0.18.97, 2020-03-20**

- Create ``crate_anon.__version__``

- :ref:`crate_nlp_build_gate_java_interface
  <crate_nlp_build_gate_java_interface>`: the ``--launch`` option now includes
  the directory for the CRATE Java class as part of the Java classpath.

- Document ``CRATE_HTTPS`` setting.

- New ``crate_bulk_hash`` tool.

- ``cardinal_pythonlib==1.0.85``

- Bump ``waitress`` from 1.4.2 to 1.4.3 (security alert).

- Bugfix to ``crate_postcodes`` (re nonexistent ``commit`` argument).

- Update ``crate_postcodes`` for ONSPD Nov 2019.

- Changes to :mod:`crate_anon.nlp_manager.nlp_manager` and
  :mod:`crate_anon.nlp_manager.input_field_config` to go back to a single query.

**v0.18.98, 2020-03-28**

- Downgrade Django as most recent version was not compatible.

**0.18.99, 2020-04-28 to 2020-07-20**

- More efficient simple postcode regex in
  :func:`crate_anon.anonymise.anonregex.get_uk_postcode_regex_elements`.

- Fuzzy ID matching work.

- Neutral language review, as per https://lkml.org/lkml/2020/7/4/229:

  - ``blacklist`` |rarr| ``denylist``, verb "deny", noun "denial",
    jargon verb "denylist", jargon adjective "denylisted".
  - ``whitelist`` |rarr| ``allowlist``, verb "allow", noun "allowing" (not
    "allowance"; that sense only in the late 15th century, according to the
    OED; "allowing" as a noun is a gerund or verbal noun; example in UK
    legislation at
    https://www.legislation.gov.uk/ukpga/1955/26/pdfs/ukpga_19550026_en.pdf);
    jargon verb "allowlist", jargon adjective "allowlisted".

  - Tidy up config file processing as part of this work.

- Bump Pillow from 6.2.0 to 7.2.0. Bump Django from 2.2.11 to 2.2.14.

**0.19.0, 2020-07-21**

- Django 3 and multiple other internal package upgrades.

- Basic Docker operation.

- Comment lines and blank lines ignored in data dictionary.

**0.19.1, 2020-12-18**

- "LFT" NLP processors: albumin, ALT, alkaline phosphatase, bilirubin, gamma
  GT.

- ``crate_run_crate_nlp_demo`` tool to test internal NLP more conveniently.

- Bugfix to ``crate_anon.anonymise.anonregex.escape_literal_string_for_regex``:
  was not doing its job!

- Read code support for blood test NLP parsers (biochemistry, haematology).

- Significant rework to numerical NLP to support a wider variety, e.g.
  ``sodium (mM) 132`` as well as ``sodium 132 mM``.


.. _changelog_2021:

2021
~~~~

**0.19.2, 2021-01-26**

- Handle errors when inserting rows in the destination table during NLP.

**0.19.3, in progress**

- Migrating Travis CI.

- ``django`` from 3.1.7 to 3.1.12 for CVE-2021-31542, then to 3.1.13 for
  CVE-2021-35042.

- ``pillow`` from 8.1.2 to 8.2.0 for several alerts including CVE-2021-25288,
  then to 8.3.2 (CVE-2021-23437).

- ``urllib3`` from 1.26.4 to 1.26.5 for CVE-2021-33503.

- ``MarkupSafe`` from 1.1.1 to 2.0.1 (for other dependencies).

- ``cardinal_pythonlib`` from 1.1.10 to 1.1.15.

- ``kombu`` from 4.4.6 to 5.2.1 (security fix), and ``celery`` from 4.4.6 to
  5.2.0 in consequence, then ``amqp`` from 2.6.0 to 5.0.6 in consequence.
  Change syntax in ``launch_nlp_webserver_celery.py`` as a result, and
  similarly elsewhere.

- Update jQuery from 3.1.1 to 3.6.0, and jQuery UI from 1.12.1 to 1.13.0.

- Remove need for ``xlrd`` (was only used for the postcode database and now
  redundant; all other Excel work uses ``openpyxl``), but add ``pyexcel-ods``
  for ODS files.

- ``pendulum`` from 2.1.1 to 2.1.2 so it installs (Python 3.7, Windows)
  (previously, it complained about PEP 517;
  https://github.com/sdispater/pendulum/issues/454).

- **Minimum Python version is now 3.7.**

- Specific code for TIMELY project.

- Full support for data dictionaries in ODS and XLSX format. (Use the first
  spreadsheet of a file.)

- Split out standalone commands, as the ``crate_anonymise`` command was
  becoming confusingly multi-purpose:

  - ``crate_anonymise --count`` becomes ``crate_anon_show_counts``;
  - ``crate_anonymise --democonfig`` becomes ``crate_anon_demo_config``;
  - ``crate_anonymise --checkextractor`` becomes
    ``crate_anon_check_text_extractor``;
  - ``crate_anonymise --draftdd`` and ``crate_anonymise --incrementaldd``
    become ``crate_anon_draft_dd``.

- Work on SystmOne data dictionaries.

- New scrub method: ``phrase_unless_numeric``.

- Efficiency check when recursing into third-party records, to avoid doing the
  same work twice.

- Automatically hash third-party PIDs using the same hasher as patient PIDs,
  rendering the de-identified records linkable (if and only if the third-party
  PID field is marked for inclusion).

- Explicit support for Python 3.10.

- ``ddgen_force_lower_case`` default changed from True to False.

- ``ddgen_min_length_for_scrubbing`` default changed from 0 to 50.

- New ``ddgen_freetext_index_min_length`` option.

- Fulltext indexing during data dictionary autogeneration now bases its
  decisions on the source (not destination) datatype. This handles the
  "auto-expansion" better -- otherwise all sorts of things were attracting the
  full-text flag.

- Remove warnings about lack of primary PID field in source tables with an MPID
  if no scrubbing is required (that's an inconvenience, not a de-identification
  risk).

- Use ``DataDictionary.get_pid_name`` instead of ``ddgen_per_table_pid_field``
  to establish the PID field for each table for scrubbing. The ``ddgen``
  options should only be for generating a data dictionary; the user may have
  revised the data dictionary subsequently, and there is no requirement that
  all PID fields have the same name across tables.

- Add data dictionary check that all scrub-source tables have a patient ID
  field.

- Remove ``ddgen_allow_no_patient_info`` option and replace it with
  ``allow_no_patient_info`` -- this is now a "runtime" setting, not a "data
  dictionary definition" setting. Depending on ``allow_no_patient_info``,
  warnings or errors are produced if a data dictionary is used without
  patient-defining information (which is usually wrong, but there are sometimes
  sensible use-cases for it).

- Option for ``ddgen_min_length_for_scrubbing`` to be less than 1 to disable
  scrubbing entirely (helpful for the SystmOne automatic data dictionary
  generation).

- ``crate_anon_summarize_dd`` tool.

- Change some hyphens to underscores in the command-line arguments to the
  PCMIS and RiO preprocessing tools, for consistency.


===============================================================================

.. rubric:: Footnotes

.. [#f1]
    https://bitbucket.org/zzzeek/sqlalchemy/issues/3504;
    http://docs.sqlalchemy.org/en/latest/changelog/migration_11.html#change-3504;
    http://docs.sqlalchemy.org/en/latest/changelog/changelog_11.html#change-1.1.0b1

.. [#f2]
    https://docs.python.org/3/reference/datamodel.html#object.__hash__;
    https://stackoverflow.com/questions/27522626/hash-function-in-python-3-3-returns-different-results-between-sessions

.. [#f3]
    See also https://stackoverflow.com/questions/5400275/fast-large-width-non-cryptographic-string-hashing-in-python

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
    https://stackoverflow.com/questions/67093/how-do-i-quickly-rename-a-mysql-database-change-schema-name

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
