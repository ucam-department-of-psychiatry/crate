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
import logging
import os
import random

from cardinal_pythonlib.logs import configure_logger_for_colour
import factory
import factory.random
from rich_argparse import ArgumentDefaultsRichHelpFormatter
from sqlalchemy import (
    create_engine,
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import text

from crate_anon.anonymise.constants import CHARSET

from crate_anon.common.constants import EnvVar
from crate_anon.testing import Base
from crate_anon.testing.factories import (
    DemoPatientFactory,
    set_sqlalchemy_session_on_all_factories,
)
from crate_anon.testing.models import (
    Note,
)
from crate_anon.testing.providers import (
    AlcoholProvider,
    ChoiceProvider,
    ConsistentDateOfBirthProvider,
    DateFormatProvider,
    FormattedDateOfBirthProvider,
    FormattedIncrementingDateProvider,
    IncrementingDateProvider,
    RelationshipProvider,
    SexProvider,
)

log = logging.getLogger(__name__)

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
# Randomness
# =============================================================================


def coin(p: float = 0.5) -> bool:
    """
    Biased coin toss. Returns ``True`` with probability ``p``.
    """
    return random.random() < p


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
    Base.metadata.drop_all(engine, checkfirst=True)
    Base.metadata.create_all(engine, checkfirst=True)

    # 3. Insert

    log.info(
        f"Aiming for a total of "
        f"{n_patients * notes_per_patient * words_per_note} "
        f"words in notes."
    )

    set_sqlalchemy_session_on_all_factories(session)
    with factory.Faker.override_default_locale("en_GB"):
        factory.Faker.add_provider(AlcoholProvider)
        factory.Faker.add_provider(ChoiceProvider)
        factory.Faker.add_provider(ConsistentDateOfBirthProvider)
        factory.Faker.add_provider(DateFormatProvider)
        factory.Faker.add_provider(FormattedDateOfBirthProvider)
        factory.Faker.add_provider(FormattedIncrementingDateProvider)
        factory.Faker.add_provider(IncrementingDateProvider)
        factory.Faker.add_provider(RelationshipProvider)
        factory.Faker.add_provider(SexProvider)

        log.info("Inserting data.")

        total_words = 0

        for p in range(1, n_patients + 1):
            # Seed both the global python RNG and Faker's RNG
            # as we don't use Faker for everything
            random.seed(p)
            factory.random.reseed_random(p)
            if p % REPORT_EVERY == 0:
                log.info(f"patient {p}")

            patient = DemoPatientFactory(notes=notes_per_patient)
            session.flush()
            for note in session.query(Note).filter(
                Note.patient_id == patient.patient_id
            ):
                num_words = len(note.note.split())
                total_words += num_words

    session.commit()
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
