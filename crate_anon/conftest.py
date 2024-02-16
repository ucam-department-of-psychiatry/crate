#!/usr/bin/env python

"""
crate_anon/conftest.py

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

pytest configuration

"""
import os
from os import pardir
from os.path import abspath, dirname, join
import tempfile
from typing import Generator, TYPE_CHECKING

from cardinal_pythonlib.sqlalchemy.session import (
    make_sqlite_url,
    SQLITE_MEMORY_URL,
)
import pytest
from sqlalchemy import event
from sqlalchemy.engine import create_engine
from sqlalchemy.engine.base import Engine
from sqlalchemy.orm import Session

from crate_anon.common.constants import EnvVar
from crate_anon.testing import Base

os.environ[EnvVar.RUNNING_TESTS] = "True"

if TYPE_CHECKING:

    # Should not need to import from _pytest in later versions of pytest
    # https://github.com/pytest-dev/pytest/issues/7469
    from _pytest.config.argparsing import Parser
    from _pytest.fixtures import FixtureRequest

_this_directory = dirname(abspath(__file__))
CRATE_DIRECTORY = abspath(join(_this_directory, pardir))


TEST_DATABASE_FILENAME = os.path.join(CRATE_DIRECTORY, "crate_test.sqlite")


def pytest_addoption(parser: "Parser"):
    parser.addoption(
        "--database-in-memory",
        action="store_false",
        dest="database_on_disk",
        default=True,
        help="Make SQLite database in memory",
    )

    # create-db is used by pytest-django
    parser.addoption(
        "--create-test-db",
        action="store_true",
        dest="create_test_db",
        default=False,
        help="Create the test database even if it already exists",
    )

    parser.addoption(
        "--mysql",
        action="store_true",
        dest="mysql",
        default=False,
        help="Use MySQL database instead of SQLite",
    )

    parser.addoption(
        "--db-url",
        dest="db_url",
        default=(
            "mysql+mysqldb://crate:crate@localhost:3306/test_crate"
            "?charset=utf8"
        ),
        help="SQLAlchemy test database URL (MySQL only)",
    )

    parser.addoption(
        "--echo",
        action="store_true",
        dest="echo",
        default=False,
        help="Log all SQL statments to the default log handler",
    )


# noinspection PyUnusedLocal
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture(scope="session")
def database_on_disk(request: "FixtureRequest") -> bool:
    return request.config.getvalue("database_on_disk")


@pytest.fixture(scope="session")
def create_test_db(request: "FixtureRequest", database_on_disk) -> bool:
    if not database_on_disk:
        return True

    if not os.path.exists(TEST_DATABASE_FILENAME):
        return True

    return request.config.getvalue("create_test_db")


@pytest.fixture(scope="session")
def echo(request: "FixtureRequest") -> bool:
    return request.config.getvalue("echo")


# noinspection PyUnusedLocal
@pytest.fixture(scope="session")
def mysql(request: "FixtureRequest") -> bool:
    return request.config.getvalue("mysql")


@pytest.fixture(scope="session")
def db_url(request: "FixtureRequest") -> bool:
    return request.config.getvalue("db_url")


@pytest.fixture(scope="session")
def tmpdir_obj(
    request: "FixtureRequest",
) -> Generator[tempfile.TemporaryDirectory, None, None]:
    tmpdir_obj = tempfile.TemporaryDirectory()

    yield tmpdir_obj

    tmpdir_obj.cleanup()


# https://gist.github.com/kissgyorgy/e2365f25a213de44b9a2
# Author says "no [license], feel free to use it"
# noinspection PyUnusedLocal
@pytest.fixture(scope="session")
def engine(
    request: "FixtureRequest",
    create_test_db: bool,
    database_on_disk: bool,
    echo: bool,
    mysql: bool,
    db_url: str,
) -> Generator["Engine", None, None]:

    if mysql:
        engine = create_engine_mysql(db_url, create_test_db, echo)
    else:
        engine = create_engine_sqlite(create_test_db, echo, database_on_disk)

    yield engine
    engine.dispose()


def create_engine_mysql(db_url: str, create_test_db: bool, echo: bool):

    # The database and the user with the given password from db_url
    # need to exist.
    # mysql> CREATE DATABASE <db_name>;
    # mysql> GRANT ALL PRIVILEGES ON <db_name>.*
    #        TO <db_user>@localhost IDENTIFIED BY '<db_password>';
    engine = create_engine(db_url, echo=echo, pool_pre_ping=True)

    if create_test_db:
        Base.metadata.drop_all(engine)

    return engine


def make_memory_sqlite_engine(echo: bool = False) -> Engine:
    """
    Create an SQLAlchemy :class:`Engine` for an in-memory SQLite database.
    """
    return create_engine(SQLITE_MEMORY_URL, echo=echo)


def make_file_sqlite_engine(filename: str, echo: bool = False) -> Engine:
    """
    Create an SQLAlchemy :class:`Engine` for an on-disk SQLite database.
    """
    return create_engine(make_sqlite_url(filename), echo=echo)


def create_engine_sqlite(
    create_test_db: bool, echo: bool, database_on_disk: bool
):
    if create_test_db and database_on_disk:
        try:
            os.remove(TEST_DATABASE_FILENAME)
        except OSError:
            pass

    if database_on_disk:
        engine = make_file_sqlite_engine(TEST_DATABASE_FILENAME, echo=echo)
    else:
        engine = make_memory_sqlite_engine(echo=echo)

    event.listen(engine, "connect", set_sqlite_pragma)

    return engine


# noinspection PyUnusedLocal
@pytest.fixture(scope="session")
def tables(
    request: "FixtureRequest", engine: "Engine", create_test_db: bool
) -> Generator[None, None, None]:
    if create_test_db:
        Base.metadata.create_all(engine)
    yield

    # Any post-session clean up would go here
    # Base.metadata.drop_all(engine)
    # This would only be useful if we wanted to clean up the database
    # after running the tests


# noinspection PyUnusedLocal
@pytest.fixture
def dbsession(
    request: "FixtureRequest", engine: "Engine", tables: None
) -> Generator[Session, None, None]:
    """
    Returns an sqlalchemy session, and after the test tears down everything
    properly.
    """

    connection = engine.connect()
    # begin the nested transaction
    transaction = connection.begin()
    # use the connection with the already started transaction
    session = Session(bind=connection)

    yield session

    session.close()
    # roll back the broader transaction
    transaction.rollback()
    # put back the connection to the connection pool
    connection.close()


@pytest.fixture
def setup(
    request: "FixtureRequest",
    engine: "Engine",
    database_on_disk: bool,
    mysql: bool,
    dbsession: Session,
    tmpdir_obj: tempfile.TemporaryDirectory,
) -> None:
    # Pytest prefers function-based tests over unittest.TestCase subclasses and
    # methods, but it still supports the latter perfectly well.
    # We use this fixture in testing/classes.py to store these values into
    # DatabaseTestCase and its descendants.
    request.cls.engine = engine
    request.cls.database_on_disk = database_on_disk
    request.cls.dbsession = dbsession
    request.cls.tmpdir_obj = tmpdir_obj
    request.cls.db_filename = TEST_DATABASE_FILENAME
    request.cls.mysql = mysql
