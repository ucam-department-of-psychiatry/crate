.. crate_anon/docs/source/misc/to_do.rst

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

Things to do
============

.. todolist::

- "Clinician asks for a study pack" -- create a contact request that's
  pre-authorized by a clinician (who might want to pass on the pack themselves
  or delegate the RDBM to do it). Needs some thought re e.g. green patients,
  audit trail.

- query "display subset of columns" -- in progress

- fix bug (reported by JL 6/11/2018) where the RiO preprocessor tries to put
  the same column into the same index more than once (see RNC email 6/11/2018)

- BENCHMARK name blacklisting (with forenames + surnames – English words –
  eponyms): speed, precision, recall. Share results with MB.

- option to filter out all free text automatically (as part of full
  anonymisation)

- Personal configurable highlight colours (with default set if none
  configured)? Or just more colours? Look at a standard highlighter pack.

- More of JL’s ideas from 8 Jan 2018:

  - Lists of drug names (“atypical antipsychotics”/”SSRIs” … ).

  - A series of functions like fn_age(rid), fn_is_alive(rid),
    fn_open_referral(rid)

  - Friendly names for the top 10 most used tables, which might appear at the
    top of the tables listing.

  - With regular data updates there might be problems with queries returning
    different results if rerun a week later, so might be worth returning a
    timestamp of some type, like: ``MAX(DATE_CREATED) FROM
    RIO.DBO.Clinical_Documents + MAX(whenprocessedutc)) FROM
    [RiONLP].[dbo].[crate_nlp_progress] + …``

- When the Windows service stops, it is still failing to kill child processes.
  See ``crate_anon/tools/winservice.py``.

- Notes to work into documentation properly:

    .. code-block:: none

        PIPELINE

        ===============================================================================
        0. BEFORE FIRST USE
        ===============================================================================

        a)  Software prerequisites

            1)  MySQL 5.6 or later. For Ubuntu 14.10:

                    $ sudo apt-get install mysql-server-5.6 mysql-server-core-5.6 \
                        mysql-client-5.6 mysql-client-core-5.6
                    - Download the corresponding MySQL Workbench from
                        http://dev.mysql.com/downloads/workbench/
                      ... though it may moan about library incompatibilities

                ... but also sensible to use Ubuntu 15.04?

            2)  Stuff that should come with Ubuntu:
                    git
                    Python 2.7

            3)  This toolkit:

                    $ git clone https://github.com/RudolfCardinal/anonymise

            4)  GATE
                - Download GATE Developer
                - java -jar gate-8.0-build4825-installer.jar
                - Read the documentation; it's quite good.

        b)  Ensure that the PYTHONPATH is pointing to necessary Python support files:

                $ . SET_PATHS.sh

            To ensure it's working:

                $ ./anonymise.py --help

        c)  Ensure that all source database(s) are accessible to the Processing
            Computer.

        d)  Write a draft config file, giving connection details for all source
            databases. To generate a demo config for editing:

                $ ./anonymise.py --democonfig > MYCONFIG.ini

            Edit it so that it can access your databases.

        e)  Ensure that the data dictionary (DD) has been created, and then updated and
            verified by a human. To generate a draft DD from your databases for
            editing:

                $ ./anonymise.py MYCONFIG.ini --draftdd

            Edit it with any TSV editor (e.g. Excel, LibreOffice Calc).

        ===============================================================================
        1. PRE-PROCESSING
        ===============================================================================

        a)  Ensure that the databases are copied and ready.

        b)  Add in any additional data. For example, if you want to process a postcode
            field to geographical output areas, such as
                http://en.wikipedia.org/wiki/ONS_coding_system
            then do it now; add in the new fields. Don't remove the old (raw) postcodes;
            they'll be necessary for anonymisation.

        c)  UNCOMMON OPTION: anonymise using NLP to find names. See below.
            If you want to anonymise using NLP to find names, rather than just use the
            name information in your source database, run nlp_manager.py now, using
            (for example) the Person annotation from GATE's
                plugins/ANNIE/ANNIE_with_defaults.gapp
            application, and send the output back into your database. You'll need to
            ensure the resulting data has patient IDs attached, probably with a view
            (see (d) below).

        d)  Ensure every table that relates to a patient has a common field with the
            patient ID that's used across the database(s) to be anonymised.
            Create views if necessary. The data dictionary should reflect this work.

        e)  Strongly consider using a row_id (e.g. integer primary key) field for each
            table. This will make natural language batch processing simpler (see
            below).

        ===============================================================================
        2. ANONYMISATION (AND FULL-TEXT INDEXING) USING A DATA DICTIONARY
        ===============================================================================

        OBJECTIVES:
            - Make a record-by-record copy of tables in the source database(s).
              Handle tables that do and tables that don't contain patient-identifiable
              information.
            - Collect patient-identifiable information and use it to "scrub" free-text
              fields; for example, with forename=John, surname=Smith, and spouse=Jane,
              one can convert freetext="I saw John in clinic with Sheila present" to
              "I saw XXX in clinic with YYY present" in the output. Deal with date,
              numerical, textual, and number-as-text information sensibly.
            - Allow other aspects of information restriction, e.g. truncating dates of
              birth to the first of the month.
            - Apply one-way encryption to patient ID numbers (storing a secure copy for
              superuser re-identification).
            - Enable linking of data from multiple source databases with a common
              identifier (such as the NHS number), similarly encrypted.
            - For performance reasons, enable parallel processing and incremental
              updates.
            - Deal with binary attachments containing text.

            For help: anonymise.py --help

        a)  METHOD 1: THREAD-BASED. THIS IS SLOWER.
                anonymise.py <configfile> [--threads=<n>]

        b)  METHOD 2: PROCESS-BASED. THIS IS FASTER.
            See example in launch_multiprocess.sh

            ---------------------------------------------------------------------------
            Work distribution
            ---------------------------------------------------------------------------
            - Best performance from multiprocess (not multithreaded) operation.
            - Drop/rebuild tables: single-process operation only.
            - Non-patient tables:
                - if there's an integer PK, split by row
                - if there's no integer PK, split by table (in sequence of all tables).
            - Patient tables: split by patient ID.
              (You have to process all scrubbing information from a patient
              simultaneously, so that's the unit of work. Patient IDs need to be
              integer for this method, though for no other reason.)
            - Indexes: split by table (in sequence of all tables requiring indexing).
              (Indexing a whole table at a time is fastest, not index by index.)

            ---------------------------------------------------------------------------
            Incremental updates
            ---------------------------------------------------------------------------
            - Supported via the --incremental option.
            - The problems include:
                - aspects of patient data (e.g. address/phone number) might, in a
                  very less than ideal world, change rather than being added to. How
                  to detect such a change?
                - If a new phone number is added (even in a sensible way) -- or, more
                  importantly, a new alias (following an anonymisation failure),
                  should re-scrub all records for that patient, even records previously
                  scrubbed.
            - Solution:
                - Only tables with a suitable PK can be processed incrementally.
                  The PK must appear in the destination database (and therefore can't
                  be sensitive, but should be an uninformative integer).
                  This is so that if a row is deleted from the source, one can check
                  by looking at the destination.
                - For a table with a src_pk, one can set the add_src_hash flag.
                  If set, then a hash of all source fields (more specifically: all that
                  are not omitted from the destination, plus any that are used for
                  scrubbing, i.e. scrubsrc_patient or scrubsrc_thirdparty) is created
                  and stored in the destination database.
                - Let's call tables that use the src_pk/add_src_hash system "hashed"
                  tables.
                - During incremental processing:
                    1. Non-hashed tables are dropped and rebuilt entirely.
                       Any records in a hashed destination table that don't have a
                       matching PK in their source table are deleted.
                    2. For each patient, the scrubber is calculated. If the
                       *scrubber's* hash has changed (stored in the secret_map table),
                       then all destination records for that patient are reworked
                       in full (i.e. the incremental option is disabled for that
                       patient).
                    3. During processing of a table (either per-table for non-patient
                       tables, or per-patient then per-table for patient tables), each
                       row has its source hash recalculated. For a non-hashed table,
                       this is then reprocessed normally. For a hashed table, if there
                       is a record with a matching PK and a matching source hash, that
                       record is skipped.

            ---------------------------------------------------------------------------
            Anonymising multiple databases together
            ---------------------------------------------------------------------------
            - RATIONALE: A scrubber will be built across ALL source databases, which
              may improve anonymisation.
            - If you don't need this, you can anonymise them separately (even into
              the same destination database, if you want to, as long as table names
              don't overlap).
            - The intention is that if you anonymise multiple databases together,
              then they must share a patient numbering (ID) system. For example, you
              might have two databases using RiO numbers; you can anonymise them
              together. If they also have an NHS number, that can be hashed as a master
              PID, for linking to other databases (anonymised separately). (If you used
              the NHS number as the primary PID, the practical difference would be that
              you would ditch any patients who have a RiO number but no NHS number
              recorded.)
            - Each database must each use a consistent name for this field, across all
              tables, WITHIN that database.
            - This field, which must be an integer, must fit into a BIGINT UNSIGNED
              field (see wipe_and_recreate_mapping_table() in anonymise.py).
            - However, the databases don't have to use the same *name* for the field.
              For example, RiO might use "id" to mean "RiO number", while CamCOPS might
              use "_patient_idnum1".

        ===============================================================================
        3. NATURAL LANGUAGE PROCESSING
        ===============================================================================

        OBJECTIVES: Send free-text content to natural language processing (NLP) tools,
        storing the results in structured form in a relational database -- for example,
        to find references to people, drugs/doses, cognitive examination scores, or
        symptoms.

            - For help: nlp_manager.py --help
            - The Java element needs building; use buildjava.sh

            - STRUCTURE: see nlp_manager.py; CamAnonGatePipeline.java

            - Run the Python script in parallel; see launch_multiprocess_nlp.sh

            ---------------------------------------------------------------------------
            Work distribution
            ---------------------------------------------------------------------------
            - Parallelize by source_pk.

            ---------------------------------------------------------------------------
            Incremental updates
            ---------------------------------------------------------------------------
            - Here, incremental updates are simpler, as the NLP just requires a record
              taken on its own.
            - Nonetheless, still need to deal with the conceptual problem of source
              record modification; how would we detect that?
                - One method would be to hash the source record, and store that with
                  the destination...
            - Solution:
                1. Delete any destination records without a corresponding source.
                2. For each record, hash the source.
                   If a destination exists with the matching hash, skip.

        ===============================================================================
        EXTRA: ANONYMISATION USING NLP.
        ===============================================================================

        OBJECTIVE: remove other names not properly tagged in the source database.

        Here, we have a preliminary stage. Instead of the usual:

                                free text
            source database -------------------------------------> anonymiser
                        |                                           ^
                        |                                           | scrubbing
                        +-------------------------------------------+ information


        we have:

                                free text
            source database -------------------------------------> anonymiser
                  |     |                                           ^  ^
                  |     |                                           |  | scrubbing
                  |     +-------------------------------------------+  | information
                  |                                                    |
                  +---> NLP software ---> list of names ---------------+
                                          (stored in source DB
                                           or separate DB)

        For example, you could:

            a) run the NLP processor to find names, feeding its output back into a new
               table in the source database, e.g. with these options:

                    inputfielddefs =
                        SOME_FIELD_DEF
                    outputtypemap =
                        person SOME_OUTPUT_DEF
                    progenvsection = SOME_ENV_SECTION
                    progargs = java
                        -classpath {NLPPROGDIR}:{GATEDIR}/bin/gate.jar:{GATEDIR}/lib/*
                        CamAnonGatePipeline
                        -g {GATEDIR}/plugins/ANNIE/ANNIE_with_defaults.gapp
                        -a Person
                        -it END_OF_TEXT_FOR_NLP
                        -ot END_OF_NLP_OUTPUT_RECORD
                        -lt {NLPLOGTAG}
                    input_terminator = END_OF_TEXT_FOR_NLP
                    output_terminator = END_OF_NLP_OUTPUT_RECORD

                    # ...

            b) add a view to include patient numbers, e.g.

                    CREATE VIEW patient_nlp_names
                    AS SELECT
                        notes.patient_id,
                        nlp_person_from_notes._content AS nlp_name
                    FROM notes
                    INNER JOIN nlp_person_from_notes
                        ON notes.note_id = nlp_person_from_notes._srcpkval
                    ;

            c) feed that lot to the anonymiser, including the NLP-generated names as
               scrubsrc_* field(s).


        ===============================================================================
        4. SQL ACCESS
        ===============================================================================

        OBJECTIVE: research access to the anonymised database(s).

        a)  Grant READ-ONLY access to the output database for any relevant user.

        b)  Don't grant any access to the secret mapping database! This is for
            trusted superusers only.

        c)  You're all set.
