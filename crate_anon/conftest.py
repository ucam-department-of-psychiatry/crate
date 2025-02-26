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
from typing import Any, Generator, TYPE_CHECKING

from cardinal_pythonlib.sqlalchemy.session import (
    make_sqlite_url,
    SQLITE_MEMORY_URL,
)
import pytest
from sqlalchemy import event, inspect
from sqlalchemy.engine import create_engine
from sqlalchemy.engine.base import Engine
from sqlalchemy.orm.session import Session

# SecretBase is used for more than just testing
from crate_anon.anonymise import SecretBase
from crate_anon.testing import (
    AnonTestBase,
    SourceTestBase,
)

if TYPE_CHECKING:
    from sqlite3 import Connection

    # Should not need to import from _pytest in later versions of pytest
    # https://github.com/pytest-dev/pytest/issues/7469
    from _pytest.config.argparsing import Parser
    from _pytest.fixtures import FixtureRequest
    from sqlalchemy.pool.base import _ConnectionRecord

_this_directory = dirname(abspath(__file__))
CRATE_DIRECTORY = abspath(join(_this_directory, pardir))

ANON_DATABASE_FILENAME = os.path.join(
    CRATE_DIRECTORY, "crate_test_anon.sqlite"
)
SECRET_DATABASE_FILENAME = os.path.join(
    CRATE_DIRECTORY, "crate_test_secret.sqlite"
)
SOURCE_DATABASE_FILENAME = os.path.join(
    CRATE_DIRECTORY, "crate_test_source.sqlite"
)


def pytest_addoption(parser: "Parser") -> None:
    parser.addoption(
        "--databases-in-memory",
        action="store_false",
        dest="databases_on_disk",
        default=True,
        help="Make SQLite databases in memory",
    )

    # create-db is used by pytest-django
    parser.addoption(
        "--create-test-dbs",
        action="store_true",
        dest="create_test_dbs",
        default=False,
        help="Create the test databases even if they already exist",
    )

    parser.addoption(
        "--anon-db-url",
        dest="anon_db_url",
        help="SQLAlchemy anonymised database URL (not applicable to SQLite)",
    )

    parser.addoption(
        "--secret-db-url",
        dest="secret_db_url",
        help="SQLAlchemy secret database URL (not applicable to SQLite)",
    )

    parser.addoption(
        "--source-db-url",
        dest="source_db_url",
        help="SQLAlchemy source database URL (not applicable to SQLite)",
    )

    parser.addoption(
        "--echo",
        action="store_true",
        dest="echo",
        default=False,
        help="Log all SQL statments to the default log handler",
    )


def pytest_configure(config: pytest.Config) -> None:
    if config.option.create_db:
        message = (
            "--create-db is a pytest-django option which is not "
            "currently necessary. Did you mean --create-test-dbs?"
        )
        pytest.exit(message)


# noinspection PyUnusedLocal
def set_sqlite_pragma(
    dbapi_connection: "Connection",
    connection_record: "_ConnectionRecord",
) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture(scope="session")
def databases_on_disk(request: "FixtureRequest") -> bool:
    return request.config.getvalue("databases_on_disk")


@pytest.fixture(scope="session")
def create_test_dbs(
    request: "FixtureRequest", databases_on_disk: bool
) -> bool:
    if not databases_on_disk:
        return True

    if not os.path.exists(ANON_DATABASE_FILENAME):
        return True
    if not os.path.exists(SECRET_DATABASE_FILENAME):
        return True
    if not os.path.exists(SOURCE_DATABASE_FILENAME):
        return True

    return request.config.getvalue("create_test_dbs")


@pytest.fixture(scope="session")
def echo(request: "FixtureRequest") -> bool:
    return request.config.getvalue("echo")


@pytest.fixture(scope="session")
def anon_db_url(request: "FixtureRequest") -> bool:
    return request.config.getvalue("anon_db_url")


@pytest.fixture(scope="session")
def crate_db_url(request: "FixtureRequest") -> bool:
    return request.config.getvalue("crate_db_url")


@pytest.fixture(scope="session")
def nlp_db_url(request: "FixtureRequest") -> bool:
    return request.config.getvalue("nlp_db_url")


@pytest.fixture(scope="session")
def secret_db_url(request: "FixtureRequest") -> bool:
    return request.config.getvalue("secret_db_url")


@pytest.fixture(scope="session")
def source_db_url(request: "FixtureRequest") -> bool:
    return request.config.getvalue("source_db_url")


@pytest.fixture(scope="session")
def test_db_url(request: "FixtureRequest") -> bool:
    return request.config.getvalue("test_db_url")


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
def anon_engine(
    request: "FixtureRequest",
    anon_db_url: str,
    create_test_dbs: bool,
    databases_on_disk: bool,
    echo: bool,
) -> Generator["Engine", None, None]:
    engine_obj = engine(
        request,
        anon_db_url,
        AnonTestBase,
        ANON_DATABASE_FILENAME,
        create_test_dbs,
        databases_on_disk,
        echo,
    )
    yield engine_obj

    engine_obj.dispose()


@pytest.fixture(scope="session")
def secret_engine(
    request: "FixtureRequest",
    secret_db_url: str,
    create_test_dbs: bool,
    databases_on_disk: bool,
    echo: bool,
) -> Generator["Engine", None, None]:
    engine_obj = engine(
        request,
        secret_db_url,
        SecretBase,
        SECRET_DATABASE_FILENAME,
        create_test_dbs,
        databases_on_disk,
        echo,
    )
    yield engine_obj

    engine_obj.dispose()


@pytest.fixture(scope="session")
def source_engine(
    request: "FixtureRequest",
    source_db_url: str,
    create_test_dbs: bool,
    databases_on_disk: bool,
    echo: bool,
) -> Generator["Engine", None, None]:
    engine_obj = engine(
        request,
        source_db_url,
        SourceTestBase,
        SOURCE_DATABASE_FILENAME,
        create_test_dbs,
        databases_on_disk,
        echo,
    )
    yield engine_obj

    engine_obj.dispose()


def engine(
    request: "FixtureRequest",
    db_url: str,
    base_class: Any,
    filename: str,
    create_test_dbs: bool,
    databases_on_disk: bool,
    echo: bool,
) -> Engine:

    if db_url:
        return create_engine_from_url(
            db_url, base_class, create_test_dbs, echo
        )

    return create_engine_sqlite(
        filename, create_test_dbs, echo, databases_on_disk
    )


def create_engine_from_url(
    db_url: str, base_class: Any, create_test_dbs: bool, echo: bool
) -> Engine:

    # The database and the user with the given password from db_url
    # need to exist.
    # MySQL example:
    # mysql> CREATE DATABASE <db_name>;
    # mysql> GRANT ALL PRIVILEGES ON <db_name>.*
    #        TO <db_user>@localhost IDENTIFIED BY '<db_password>';
    engine = create_engine(db_url, echo=echo, pool_pre_ping=True, future=True)

    if create_test_dbs:
        base_class.metadata.drop_all(engine)

    return engine


def make_memory_sqlite_engine(echo: bool = False) -> Engine:
    """
    Create an SQLAlchemy :class:`Engine` for an in-memory SQLite database.
    """
    return create_engine(SQLITE_MEMORY_URL, echo=echo, future=True)


def make_file_sqlite_engine(filename: str, echo: bool = False) -> Engine:
    """
    Create an SQLAlchemy :class:`Engine` for an on-disk SQLite database.
    """
    return create_engine(make_sqlite_url(filename), echo=echo, future=True)


def create_engine_sqlite(
    filename: str, create_test_dbs: bool, echo: bool, databases_on_disk: bool
) -> Engine:
    if create_test_dbs and databases_on_disk:
        try:
            os.remove(filename)
        except OSError:
            pass

    if databases_on_disk:
        engine = make_file_sqlite_engine(filename, echo=echo)
    else:
        engine = make_memory_sqlite_engine(echo=echo)

    event.listen(engine, "connect", set_sqlite_pragma)

    return engine


# noinspection PyUnusedLocal
@pytest.fixture(scope="session")
def anon_tables(
    request: "FixtureRequest", anon_engine: "Engine", create_test_dbs: bool
) -> Generator[None, None, None]:

    # Not foolproof. Will still need to pass create-test-dbs if the
    # schema has changed.
    database_is_empty = not inspect(anon_engine).get_table_names()

    if create_test_dbs or database_is_empty:
        AnonTestBase.metadata.create_all(anon_engine)
    yield

    # Any post-session clean up would go here
    # Base.metadata.drop_all(engine)
    # This would only be useful if we wanted to clean up the database
    # after running the tests


# noinspection PyUnusedLocal
@pytest.fixture(scope="session")
def secret_tables(
    request: "FixtureRequest", secret_engine: "Engine", create_test_dbs: bool
) -> Generator[None, None, None]:

    # Not foolproof. Will still need to pass create-test-dbs if the
    # schema has changed.
    database_is_empty = not inspect(secret_engine).get_table_names()

    if create_test_dbs or database_is_empty:
        SecretBase.metadata.create_all(secret_engine)
    yield

    # Any post-session clean up would go here
    # Base.metadata.drop_all(engine)
    # This would only be useful if we wanted to clean up the database
    # after running the tests


# noinspection PyUnusedLocal
@pytest.fixture(scope="session")
def source_tables(
    request: "FixtureRequest", source_engine: "Engine", create_test_dbs: bool
) -> Generator[None, None, None]:
    # Not foolproof. Will still need to pass create-test-dbs if the
    # schema has changed.
    database_is_empty = not inspect(source_engine).get_table_names()

    if create_test_dbs or database_is_empty:
        SourceTestBase.metadata.create_all(source_engine)
    yield

    # Any post-session clean up would go here
    # Base.metadata.drop_all(engine)
    # This would only be useful if we wanted to clean up the database
    # after running the tests


# noinspection PyUnusedLocal
@pytest.fixture
def anon_dbsession(
    request: "FixtureRequest", anon_engine: "Engine", anon_tables: None
) -> Generator[Session, None, None]:
    """
    Returns an sqlalchemy session, and after the test tears down everything
    properly.
    """

    connection = anon_engine.connect()
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


# noinspection PyUnusedLocal
@pytest.fixture
def secret_dbsession(
    request: "FixtureRequest", secret_engine: "Engine", secret_tables: None
) -> Generator[Session, None, None]:
    """
    Returns an sqlalchemy session, and after the test tears down everything
    properly.
    """

    connection = secret_engine.connect()
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


# noinspection PyUnusedLocal
@pytest.fixture
def source_dbsession(
    request: "FixtureRequest", source_engine: "Engine", source_tables: None
) -> Generator[Session, None, None]:
    """
    Returns an sqlalchemy session, and after the test tears down everything
    properly.
    """

    connection = source_engine.connect()
    # begin the nested transaction
    transaction = connection.begin()
    # use the connection with the already started transaction
    session = Session(bind=connection, future=True)

    yield session

    session.close()
    # roll back the broader transaction
    transaction.rollback()
    # put back the connection to the connection pool
    connection.close()


@pytest.fixture
def setup(
    request: "FixtureRequest",
    anon_engine: "Engine",
    secret_engine: "Engine",
    source_engine: "Engine",
    databases_on_disk: bool,
    anon_dbsession: Session,
    secret_dbsession: Session,
    source_dbsession: Session,
    tmpdir_obj: tempfile.TemporaryDirectory,
) -> None:

    # Pytest prefers function-based tests over unittest.TestCase subclasses and
    # methods, but it still supports the latter perfectly well.
    # We use this fixture in testing/classes.py to store these values into
    # DatabaseTestCase and its descendants.
    request.cls.anon_engine = anon_engine
    request.cls.secret_engine = secret_engine
    request.cls.source_engine = source_engine
    request.cls.databases_on_disk = databases_on_disk
    request.cls.anon_dbsession = anon_dbsession
    request.cls.secret_dbsession = secret_dbsession
    request.cls.source_dbsession = source_dbsession
    request.cls.tmpdir_obj = tmpdir_obj
    request.cls.anon_db_filename = ANON_DATABASE_FILENAME
    request.cls.secret_db_filename = SECRET_DATABASE_FILENAME
    request.cls.source_db_filename = SOURCE_DATABASE_FILENAME
