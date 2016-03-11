#!/usr/bin/env python3
# crate/anonymise/make_demo_database.py

"""
Makes a giant test database for anonymisation testing.

Author: Rudolf Cardinal
Created at: 21 Feb 2015
Last update: 22 Nov 2015

Copyright/licensing:

    Copyright (C) 2015-2015 Rudolf Cardinal (rudolf@pobox.com).
    Department of Psychiatry, University of Cambridge.

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

"""

import argparse
import datetime
import getpass
import subprocess

import cardinal_pythonlib.rnc_db as rnc_db


def insert_patient(db, patient_id, forename, surname, dob, nhsnum, phone,
                   postcode):
    db.db_exec("""
        INSERT INTO patients
            (patient_id, forename, surname, dob, nullfield, nhsnum, phone,
            postcode)
        VALUES
            (?, ?, ?, ?, ?, ?, ?, ?)
    """, patient_id, forename, surname, dob, None, nhsnum, phone, postcode)


def insert_note(db, patient_id, note):
    db.db_exec("""
        INSERT INTO notes
            (patient_id, note)
        VALUES
            (?, ?)
    """, patient_id, note)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="localhost",
                        help="MySQL host (server) (default: localhost)")
    parser.add_argument("--port", type=int, default=3306,
                        help="MySQL port (default: 3306)")
    parser.add_argument("--db", default="test",
                        help="MySQL database name (default: test)")
    parser.add_argument("--user", default="root",
                        help="MySQL user (default: root)")
    parser.add_argument(
        "--size", type=int, default=0, choices=[0, 1, 2],
        help="Make small (0), medium (1), or large (2) database")
    args = parser.parse_args()

    password = getpass.getpass("MySQL password: ")

    NWORDS = 10000
    if args.size == 0:
        PATIENTS = 20
        NOTES_PER_PATIENT = 1
        WORDS_PER_NOTE = 100
    elif args.size == 1:
        PATIENTS = 100
        NOTES_PER_PATIENT = 5
        WORDS_PER_NOTE = 100
    else:
        # about 1.9 Gb
        PATIENTS = 1000
        NOTES_PER_PATIENT = 100
        WORDS_PER_NOTE = 1000

    REPORT_EVERY = 50

    BASE_DOB = datetime.datetime(day=1, month=10, year=1980)
    DT_FORMATS = [
        "%d %b %Y",  # e.g. 24 Jul 2013
        "%d %B %Y",  # e.g. 24 July 2013
        "%a %d %B %Y",  # e.g. Wed 24 July 2013
        "%d %B %Y, %H:%M %z",  # ... e.g. 24 July 2013, 20:04 +0100
        "%a %d %B %Y, %H:%M %z",  # ... e.g. Wed 24 July 2013, 20:04 +0100
        "%a %d %B %Y, %H:%M",  # ... e.g. Wed 24 July 2013, 20:04
        "%a %d %b %Y, %H:%M",  # ... e.g. Wed 24 Jul 2013, 20:04
        "%d %B %Y, %H:%M:%S %z",
        "%d %b %Y, %H:%M %z",
        "%d %b %Y, %H:%M:%S %z",
        "%H:%M",
        "%Y-%m-%dT%H:%M:%S%z",  # e.g. 2013-07-24T20:04:07+0100
        "%Y-%m-%d",  # e.g. 2013-07-24
        "%Y-%m-%dT%H%M",  # e.g. 20130724T2004
        "%Y-%m-%d",  # e.g. 20130724
        "%Y%m%d%H%M%S%z",  # e.g. 20130724200407+0100
        "%Y%m%d",  # e.g. 20130724
        "%Y-%m-%dT%H:%M:%SZ",  # e.g. 2013-07-24T20:03:07Z
        "%d/%m/%Y %H:%M",  # e.g. 01/12/2014 09:45
    ]

    # 1. Get words

    print("Fetching words.")
    words = subprocess.check_output([
        "grep",
        "-v", "'s",
        "-m", str(NWORDS),
        "/usr/share/dict/words"
    ]).splitlines()

    # 2. Open database

    print("Opening database.")
    db = rnc_db.DatabaseSupporter()
    db.connect_to_database_mysql(
        server=args.host,
        port=args.port,
        database=args.db,
        user=args.user,
        password=password,
        autocommit=False  # NB therefore need to commit
    )

    # 3. Create tables

    print("Creating tables. Ignore warnings.")
    db.db_exec_literal("DROP TABLE IF EXISTS patients")
    db.db_exec_literal("DROP TABLE IF EXISTS notes")
    db.db_exec_literal("""
        CREATE TABLE patients (
            patient_id INTEGER PRIMARY KEY,
            forename VARCHAR(50),
            surname VARCHAR(50),
            dob DATETIME,
            nullfield INTEGER,
            nhsnum INTEGER,
            phone VARCHAR(50),
            postcode VARCHAR(50)
        )
    """)
    db.db_exec_literal("""
        CREATE TABLE notes (
            note_id INTEGER PRIMARY KEY AUTO_INCREMENT,
            patient_id INTEGER,
            note TEXT
        )
    """)

    # 4. Insert

    print("Aiming for a total of {} words in notes.".format(
        PATIENTS * NOTES_PER_PATIENT * WORDS_PER_NOTE))

    print("Inserting data.")
    patient_id = 0

    # Special extra patient
    insert_patient(db, patient_id, "Ronald Gibbet", "MacDonald",
                   datetime.datetime(day=11, month=11, year=1911), 123456,
                   "(01223)-123456", "CB2 3EB")
    insert_note(db, patient_id, u"""
        Ronald MacDonald lived on a farm and kept a gibbet for scaring off
        small animals. He was born on 11 Nov 1911 and was very proud of this.
        His cat’s name was Flitterwick. It did not like the gibbets.
        Ronalds other passion was blimping.
        A typo might be RonaldMacDonald.
        His phone number was 0122-312-3456, or 01223-123456, or (01223) 123456,
        or 01223 123 456, or 01223 123456.
        His NHS number was 123.456 or possibly 12 34 56.
        His postcode was CB2 3EB, or possible CB23EB, or CB2, or 3EB.
    """)
    patient_id += 1

    # More special ones
    insert_patient(db, patient_id, "Bob D'Souza", "",
                   datetime.datetime(day=11, month=11, year=1911), 123456,
                   "(01223)-123456", "CB2 3EB")
    insert_note(db, patient_id, u"""
        Bob D'Souza, also known as Bob, or Mr DSouza, or sometimes Mr D Souza,
        or the D'Souza bloke down the road, or BobDSouza or BobD'Souza.
        His phone number was 0122-312-3456, or 01223-123456, or (01223) 123456,
        or 01223 123 456, or 01223 123456.
        His NHS number was 123.456 or possibly 12 34 56 or 123456, perhaps.
        His postcode was CB2 3EB, or possible CB23EB, or CB2, or 3EB.
        Bob Hope visited Seattle.
    """)
    patient_id += 1

    """
    See also:

        http://www.ncbi.nlm.nih.gov/pmc/articles/PMC3751474/
        http://www.ncbi.nlm.nih.gov/pmc/articles/PMC3751474/table/T7/

    After anonymisation, check with:

        SELECT * FROM anonymous_output.notes WHERE brcid IN (
            SELECT brcid
            FROM anonymous_mapping.secret_map
            WHERE patient_id < 2
        );
        SELECT * FROM test.patients WHERE patient_id < 2;
    """

    # A bunch of patients
    for p in range(PATIENTS):
        if p % REPORT_EVERY == 0:
            print("patient {}".format(p))
        # forename = words[(p + 1) % NWORDS]
        forename = words[(p + 1) % NWORDS] + " " + words[(p + 10) % NWORDS]
        surname = words[(p + 2) % NWORDS]
        dob = BASE_DOB + datetime.timedelta(days=p)
        ok_date = dob + datetime.timedelta(days=1)
        nhsnum = patient_id * 2
        phone = "123456"
        postcode = "CB2 3EB"
        insert_patient(db, patient_id, forename, surname, dob, nhsnum, phone,
                       postcode)

        dates = "DATES: " + (
            " ".join([dob.strftime(fmt) for fmt in DT_FORMATS]) +
            " ".join([ok_date.strftime(fmt) for fmt in DT_FORMATS])
        ) + ". "
        fname = "FORENAME: " + forename + ". "
        sname = "SURNAME: " + surname + ". "
        numbers = "NUMBERS: {}, {}, {}. ".format(patient_id, patient_id + 1,
                                                 nhsnum)
        for n in range(NOTES_PER_PATIENT):
            wstr = " ".join(words[p % NWORDS:(p + WORDS_PER_NOTE) % NWORDS])
            insert_note(db, patient_id,
                        fname + sname + numbers + dates + wstr)
        patient_id += 1

    # 5. Commit

    print("Committing...")
    db.commit()

    # 6. Adding reasonable indexes

    print("Adding indexes...")
    db.db_exec_literal("CREATE UNIQUE INDEX _idx_patient_id "
                       "ON patients (patient_id)")
    db.db_exec_literal("CREATE INDEX _idx_patient_id ON notes (patient_id)")

    # 7. Report size

    print("Done. Database size:")
    rows = db.fetchall("""
        SELECT
            table_name,
            table_rows,
            data_length,
            index_length,
            round(((data_length + index_length) / 1024 / 1024),2) "Size_MB"
        FROM
            information_schema.tables
        WHERE table_schema = ?;
    """, args.db)
    for r in rows:
        print(
            "table={}, rows={}, data_length={}, index_length={}, "
            "size_MB={}".format(
                r[0], r[1], r[2], r[3], r[4],
            )
        )


if __name__ == 'main':
    main()
