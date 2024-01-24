#!/usr/bin/env python

"""
crate_anon/anonymise/make_demo_database.py

===============================================================================

    Copyright (C) 2015, University of Cambridge, Department of Psychiatry.
    Created by Rudolf Cardinal (rnc1001@cam.ac.uk).

    This file is part of CRATE.

    CRATE is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    CRATE is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with CRATE. If not, see <https://www.gnu.org/licenses/>.

===============================================================================

**Makes a test database (from tiny to large) for anonymisation testing.**

See also:

- https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3751474/
- https://www.ncbi.nlm.nih.gov/pmc/articles/PMC3751474/table/T7/

After anonymisation, check with:

.. code-block:: sql

    SELECT * FROM anonymous_output.notes WHERE brcid IN (
        SELECT brcid
        FROM anonymous_mapping.secret_map
        WHERE patient_id < 2
    );
    SELECT * FROM test.patients WHERE patient_id < 2;

"""

import argparse
import datetime
import enum
import logging
import os
import random
from typing import TYPE_CHECKING

from cardinal_pythonlib.datetimefunc import pendulum_to_datetime
from cardinal_pythonlib.logs import configure_logger_for_colour
from cardinal_pythonlib.nhs import generate_random_nhs_number
from faker import Faker
import pendulum
from pendulum import DateTime as Pendulum  # NB name clash with SQLAlchemy
from rich_argparse import ArgumentDefaultsRichHelpFormatter
from sqlalchemy import (
    create_engine,
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,  # NB name clash with pendulum
    Enum,
    ForeignKey,
    Integer,
    LargeBinary,
    MetaData,
    String,
    Text,
)
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from sqlalchemy.sql import text

from crate_anon.anonymise.constants import (
    CHARSET,
    COMMENT,
    TABLE_KWARGS,
)
from crate_anon.common.constants import EnvVar

if TYPE_CHECKING:
    from sqlalchemy.sql.type_api import TypeEngine
    from sqlalchemy.sql.compiler import SQLCompiler

log = logging.getLogger(__name__)
metadata = MetaData()
Base = declarative_base(metadata=metadata)

# =============================================================================
# Constants
# =============================================================================

CONSOLE_ENCODING = "utf8"
REPORT_EVERY = 50
DATE_FORMATS = [
    "%d %b %Y",  # e.g. 24 Jul 2013
    "%d %B %Y",  # e.g. 24 July 2013
    "%Y-%m-%d",  # e.g. 2013-07-24
    "%Y-%m-%d",  # e.g. 20130724
    "%Y%m%d",  # e.g. 20130724
]

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

if EnvVar.GENERATING_CRATE_DOCS in os.environ:
    DEFAULT_DOCDIR = "/path/to/test_docs"
else:
    DEFAULT_DOCDIR = os.path.abspath(
        os.path.join(CURRENT_DIR, os.pardir, "testdocs_for_text_extraction")
    )

DEFAULT_DOCTEST_DOC = os.path.join(DEFAULT_DOCDIR, "doctest.doc")
DEFAULT_DOCTEST_DOCX = os.path.join(DEFAULT_DOCDIR, "doctest.docx")
DEFAULT_DOCTEST_ODT = os.path.join(DEFAULT_DOCDIR, "doctest.odt")
DEFAULT_DOCTEST_PDF = os.path.join(DEFAULT_DOCDIR, "doctest.pdf")

MAX_EXT_LENGTH_WITH_DOT = 10

PATIENT_ID_COMMENT = "Patient ID"


# =============================================================================
# BLOB type
# =============================================================================

# http://docs.sqlalchemy.org/en/latest/core/custom_types.html
# noinspection PyUnusedLocal
@compiles(LargeBinary, "mysql")
def compile_blob_mysql(
    type_: "TypeEngine", compiler: "SQLCompiler", **kw
) -> str:
    """
    Provides a custom type for the SQLAlchemy ``LargeBinary`` type under MySQL,
    by using ``LONGBLOB`` (which overrides the default of ``BLOB``).

    MySQL: https://dev.mysql.com/doc/refman/5.7/en/storage-requirements.html

    .. code-block:: none

        TINYBLOB: up to 2^8 bytes
        BLOB: up to 2^16 bytes = 64 KiB
        MEDIUMBLOB: up to 2^24 bytes = 16 MiB  <-- minimum for docs
        LONGBLOB: up to 2^32 bytes = 4 GiB

        VARBINARY: up to 65535 = 64 KiB

    SQL Server: https://msdn.microsoft.com/en-us/library/ms188362.aspx

    .. code-block:: none

        BINARY: up to 8000 bytes = 8 KB
        VARBINARY(MAX): up to 2^31 - 1 bytes = 2 GiB <-- minimum for docs
        IMAGE: deprecated; up to 2^31 - 1 bytes = 2 GiB
            https://msdn.microsoft.com/en-us/library/ms187993.aspx

    SQL Alchemy:

    .. code-block:: none

        _Binary: base class
        LargeBinary: translates to BLOB in MySQL
        VARBINARY, as an SQL base data type
        dialects.mysql.base.LONGBLOB
        dialects.mssql.base.VARBINARY

    Therefore, we can take the LargeBinary type and modify it.
    """
    return "LONGBLOB"  # would have been "BLOB"


# If this goes wrong for future versions of SQL Server, write another
# specializer to produce "VARBINARY(MAX)" instead of "IMAGE". I haven't done
# that because it may be that SQL Alchemy is reading the SQL Server version
# (it definitely executes "select @@version") and specializing accordingly.


# =============================================================================
# A silly enum
# =============================================================================


class EnumColours(enum.Enum):
    """
    A silly enum, for testing.
    """

    red = 1
    green = 2
    blue = 3


# =============================================================================
# Randomness
# =============================================================================


def coin(p: float = 0.5) -> bool:
    """
    Biased coin toss. Returns ``True`` with probability ``p``.
    """
    return random.random() < p


# =============================================================================
# Tables
# =============================================================================


class Patient(Base):
    """
    SQLAlchemy ORM class for fictional patients.
    """

    __tablename__ = "patient"
    __table_args__ = {
        COMMENT: "Fictional patients",
        **TABLE_KWARGS,
    }

    patient_id = Column(
        Integer,
        primary_key=True,
        autoincrement=False,
        comment=PATIENT_ID_COMMENT,
    )
    forename = Column(String(50), comment="Forename")
    surname = Column(String(50), comment="Surname")
    dob = Column(Date, comment="Date of birth (DOB)")
    nullfield = Column(Integer, comment="Always NULL")
    nhsnum = Column(BigInteger, comment="NHS number")
    phone = Column(String(50), comment="Phone number")
    postcode = Column(String(50), comment="Postcode")
    optout = Column(
        Boolean, default=False, comment="Opt out from research database?"
    )
    related_patient_id = Column(Integer, comment="ID of another patient")
    colour = Column(
        Enum(EnumColours),
        nullable=True,
        comment="An enum column, which may be red/green/blue",
    )  # new in v0.18.41


class Note(Base):
    """
    SQLAlchemy ORM class for fictional notes.
    """

    __tablename__ = "note"
    __table_args__ = {
        COMMENT: "Fictional textual notes",
        **TABLE_KWARGS,
    }

    note_id = Column(Integer, primary_key=True, comment="Note ID")
    patient_id = Column(
        Integer, ForeignKey("patient.patient_id"), comment=PATIENT_ID_COMMENT
    )
    note = Column(Text, comment="Text of the note")
    note_datetime = Column(DateTime, comment="Date/time of the note")

    patient = relationship("Patient")


class BlobDoc(Base):
    """
    SQLAlchemy ORM class for fictional binary documents.
    """

    __tablename__ = "blobdoc"
    __table_args__ = {
        COMMENT: "Fictional documents as binary large objects",
        **TABLE_KWARGS,
    }

    blob_doc_id = Column(
        Integer, primary_key=True, comment="Binary document ID"
    )
    patient_id = Column(
        Integer, ForeignKey("patient.patient_id"), comment=PATIENT_ID_COMMENT
    )
    blob = Column(
        LargeBinary, comment="The BLOB (binary large object)"
    )  # modified as above!
    extension = Column(
        String(MAX_EXT_LENGTH_WITH_DOT), comment="Filename extension"
    )
    blob_datetime = Column(DateTime, comment="Date/time of the document")

    patient = relationship("Patient")

    def __init__(
        self, patient: Patient, filename: str, blob_datetime: datetime.datetime
    ) -> None:
        """
        Args:
            patient: corresponding :class:`Patient` object
            filename: filename containing the binary document to load and
                store in the database
            blob_datetime: date/time value to give this BLOB
        """
        _, extension = os.path.splitext(filename)
        with open(filename, "rb") as f:
            contents = f.read()  # will be of type 'bytes'
        # noinspection PyArgumentList
        super().__init__(
            patient=patient,
            blob=contents,
            extension=extension,
            blob_datetime=blob_datetime,
        )


class FilenameDoc(Base):
    """
    SQLAlchemy ORM class for a table containing the filenames of binary
    documents.
    """

    __tablename__ = "filenamedoc"
    __table_args__ = {
        COMMENT: "Filenames of binary documents",
        **TABLE_KWARGS,
    }

    filename_doc_id = Column(Integer, primary_key=True, comment="Filename ID")
    patient_id = Column(
        Integer, ForeignKey("patient.patient_id"), comment=PATIENT_ID_COMMENT
    )
    filename = Column(Text, comment="Filename")
    file_datetime = Column(DateTime, comment="Date/time of the document")

    patient = relationship("Patient")


# =============================================================================
# Make demo database
# =============================================================================


def mk_demo_database(
    url: str,
    n_patients: int,
    notes_per_patient: int,
    words_per_note: int,
    echo: bool = False,
) -> None:
    fake = Faker("en_GB")
    us_fake = Faker("en_US")  # For text. You get Lorem ipsum with en_GB.
    # 0. Announce intentions

    log.info(
        f"n_patients={n_patients}, "
        f"notes_per_patient={notes_per_patient}, "
        f"words_per_note={words_per_note}"
    )

    # 1. Open database

    log.info("Opening database.")
    log.debug(f"URL: {url}")
    engine = create_engine(url, echo=echo, encoding=CHARSET)
    session = sessionmaker(bind=engine)()

    # 2. Create tables

    log.info("Creating tables (dropping them first if required).")
    metadata.drop_all(engine, checkfirst=True)
    metadata.create_all(engine, checkfirst=True)

    # 3. Insert

    log.info(
        f"Aiming for a total of "
        f"{n_patients * notes_per_patient * words_per_note} "
        f"words in notes."
    )

    log.info("Inserting data.")

    # Autoincrementing date

    # No one is born after this
    first_note_datetime = Pendulum(year=2000, month=1, day=1, hour=9)
    _datetime = first_note_datetime

    def incdatetime() -> datetime.datetime:
        nonlocal _datetime
        _p = _datetime
        _datetime = _datetime.add(days=1)
        return pendulum_to_datetime(_p)

    # A bunch of patients
    prev_forename = ""
    prev_surname = ""
    total_words = 0

    for p in range(1, n_patients + 1):
        Faker.seed(p)
        if p % REPORT_EVERY == 0:
            log.info(f"patient {p}")

        sex = fake.random.choices(["M", "F", "X"], weights=[49.8, 49.8, 0.4])[
            0
        ]

        if sex == "M":
            forename = fake.first_name_male()
            possessive_pronoun = "his"
        elif sex == "F":
            forename = fake.first_name_female()
            possessive_pronoun = "her"
        else:
            forename = fake.first_name()[:1]
            possessive_pronoun = "their"

        surname = fake.last_name()
        # Faker date_of_birth calculates from the current time so gives
        # different results on different days. In our case we don't want
        # the date of birth to be greater than the date stamp on the note.
        dob = fake.date_between_dates(
            date_start=pendulum.date(1900, 1, 1), date_end=first_note_datetime
        )
        nhsnum = generate_random_nhs_number()

        if p == 1:
            related_patient_id = None
            relation_name = ""
        else:
            related_patient_id = p - 1
            relation_name = f" {prev_forename} {prev_surname}"

        # noinspection PyTypeChecker
        patient = Patient(
            patient_id=p,
            forename=forename,
            surname=surname,
            dob=dob,
            nhsnum=nhsnum,
            phone=fake.phone_number(),
            postcode=fake.postcode(),
            related_patient_id=related_patient_id,
            colour=EnumColours.blue if coin() else None,
        )
        session.add(patient)
        patient_id = patient.patient_id

        dob_format = fake.random.choices(DATE_FORMATS)[0]
        dob_formatted = dob.strftime(dob_format)
        # non-gendered for now
        relation = fake.random.choices(
            [
                "child",
                "parent",
                "sibling",
                "spouse",
                "partner",
                "carer",
            ]
        )[0]

        for n in range(notes_per_patient):
            note_datetime = incdatetime()
            note_datetime_format = fake.random.choices(DATE_FORMATS)[0]
            note_datetime_formatted = note_datetime.strftime(
                note_datetime_format
            )

            another_date = fake.date_of_birth()
            another_date_format = fake.random.choices(DATE_FORMATS)[0]
            another_date_formatted = another_date.strftime(another_date_format)

            other = fake.random.choices(
                [
                    "Start aspirin 75mg od. Remains on Lipitor 40mg nocte",
                    "For haloperidol 2mg po prn max qds",
                    "Start amoxicillin 500 mg b.i.d. for 7 days",
                    f"{possessive_pronoun.capitalize()} CRP is 10",
                    (
                        f"{possessive_pronoun.capitalize()} "
                        "previous CRP was <13 mg/dl"
                    ),
                    "Sodium 140",
                    "TSH 3.5; urea normal",
                    "Height 1.82m, weight 75kg, BMI 22.6. BP 135/82",
                    "MMSE 28/30. ACE-R 72, ACE-II 73, ACE 73",
                    "ESR 16 (H) mm/h",
                    (
                        "WBC 9.2; neutrophils 4.3; lymphocytes 2.6; "
                        "eosinophils 0.4; monocytes 1.2; basophils 0.6"
                    ),
                    (
                        f"{forename} took venlafaxine 375 M/R od, "
                        "and is due to start clozapine 75mg bd"
                    ),
                ]
            )[0]

            units = fake.pyint(max_value=100)
            alcohol = fake.random.choices(
                [
                    f"Alcohol {units} u/w",
                    f"EtOH = {units} u/w",
                    f"Alcohol (units/week): {units}",
                    f"alcohol {units} I.U./week",
                    f"Was previously drinking {units} u/w",
                    "teetotal",
                    "Alcohol: no",
                    "Abstinant from alcohol",
                    f"Alcohol: presently less than {units} u/w",
                ]
            )[0]
            note_text = (
                f"I saw {forename} {surname} on {note_datetime_formatted} "
                f"(DOB: {dob_formatted}, NHS {nhsnum}, "
                f"Patient id: {patient_id}), "
                f"accompanied by {possessive_pronoun} {relation}"
                f"{relation_name}. "
                f"{alcohol}. "
                f"Another date: {another_date_formatted}. "
                f"{other}."
            )
            pad_words = words_per_note - len(note_text.split())
            while pad_words > 2:
                nb_words = min(15, pad_words)
                sentence = us_fake.sentence(nb_words=nb_words)
                note_text = f"{note_text} {sentence}"
                pad_words -= len(sentence.split())

            note = Note(
                patient=patient, note=note_text, note_datetime=note_datetime
            )
            total_words += len(note_text.split())
            session.add(note)

        prev_forename = forename
        prev_surname = surname

    # 4. Commit

    log.info("Committing...")
    session.commit()
    log.info("Done.")

    # 5. Report size

    if engine.dialect.name == "mysql":
        log.info("Done. Database size:")
        sql = """
            SELECT
                table_schema,
                table_name,
                table_rows,
                data_length,
                index_length,
                ROUND(((data_length + index_length) / (1024 * 1024)), 2)
                  AS "Size_MB"
            FROM
                information_schema.tables
            WHERE table_schema = DATABASE()
        """
        rows = session.execute(text(sql))
        for r in rows:
            print(
                "schema={}, table={}, rows={}, data_length={}, "
                "index_length={}, size_MB={}".format(*r)
            )

    log.info(f"Total words in all notes: {total_words}")


# =============================================================================
# Command-line entry point
# =============================================================================


def main() -> None:
    """
    Command-line processor. See command-line help.
    """
    default_size = 0
    parser = argparse.ArgumentParser(
        formatter_class=ArgumentDefaultsRichHelpFormatter
    )
    parser.add_argument(
        "url",
        help=(
            "SQLAlchemy database URL. Append ?charset=utf8, e.g. "
            "mysql+mysqldb://root:password@127.0.0.1:3306/test?charset=utf8 ."
            " WARNING: If you get the error 'MySQL has gone away', increase "
            "the max_allowed_packet parameter in my.cnf (e.g. to 32M)."
        ),
    )
    parser.add_argument(
        "--size",
        type=int,
        default=default_size,
        choices=[0, 1, 2, 3],
        help="Make tiny (0), small (1), medium (2), or large (3) database",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Be verbose"
    )
    # Not currently used -- todo: add back binaries to demo database?
    # parser.add_argument(
    #     "--doctest_doc", default=DEFAULT_DOCTEST_DOC,
    #     help="Test file for .DOC"
    # )
    # parser.add_argument(
    #     "--doctest_docx",
    #     default=DEFAULT_DOCTEST_DOCX,
    #     help="Test file for .DOCX",
    # )
    # parser.add_argument(
    #     "--doctest_odt", default=DEFAULT_DOCTEST_ODT,
    #     help="Test file for .ODT"
    # )
    # parser.add_argument(
    #     "--doctest_pdf", default=DEFAULT_DOCTEST_PDF,
    #     help="Test file for .PDF"
    # )
    parser.add_argument("--echo", action="store_true", help="Echo SQL")

    args = parser.parse_args()

    loglevel = logging.DEBUG if args.verbose else logging.INFO
    rootlogger = logging.getLogger()
    configure_logger_for_colour(rootlogger, level=loglevel)

    if args.size == 0:
        n_patients = 20
        notes_per_patient = 1
        words_per_note = 100
    elif args.size == 1:
        n_patients = 100
        notes_per_patient = 5
        words_per_note = 100
    elif args.size == 2:
        n_patients = 100
        notes_per_patient = 100
        words_per_note = 1000
    elif args.size == 3:
        # about 1.4 Gb
        n_patients = 1000
        notes_per_patient = 100
        words_per_note = 1000
    else:
        assert False, "Bad size parameter"

    mk_demo_database(
        url=args.url,
        n_patients=n_patients,
        notes_per_patient=notes_per_patient,
        words_per_note=words_per_note,
        echo=args.echo,
    )


if __name__ == "__main__":
    main()
