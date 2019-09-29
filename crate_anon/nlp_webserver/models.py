#!/usr/bin/env python

r"""
crate_anon/nlp_webserver/models.py

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

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
    along with CRATE. If not, see <http://www.gnu.org/licenses/>.

===============================================================================

SQLAlchemy models for CRATE's implementation of an NLPRP server.

"""

import datetime
from typing import List, Optional
import uuid

from cardinal_pythonlib.datetimefunc import coerce_to_pendulum
from pendulum import DateTime as Pendulum
from sqlalchemy import (
    Column,
    Text,
    VARCHAR,
    Boolean,
    DateTime,
    # Integer,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import (
    deferred,
    relationship,
    scoped_session,
    sessionmaker,
)
from sqlalchemy.sql.schema import ForeignKey
# noinspection PyPackageRequirements
from zope.sqlalchemy import ZopeTransactionExtension


# =============================================================================
# SQLAlchemy setup
# =============================================================================

Session = sessionmaker(extension=ZopeTransactionExtension())
dbsession = scoped_session(Session)

Base = declarative_base()


# =============================================================================
# Constants
# =============================================================================

UUID64_LEN = 36  # see make_unique_id()

MAX_DOC_ID_LEN = UUID64_LEN
MAX_DOCPROC_ID_LEN = UUID64_LEN
MAX_QUEUE_ID_LEN = UUID64_LEN

MAX_JOB_ID_LEN = 255  # specified by client
MAX_USERNAME_LEN = 255  # arbitrary
MAX_PROCESSOR_ID_LEN = 255  # e.g. Python fully-qualified name, underscore, version  # noqa


# =============================================================================
# Helper functions
# =============================================================================

def make_unique_id() -> str:
    """
    Generates a random unique ID for labelling objects, via :func:`uuid.uuid4`.

    They look like '79cc4bac-6e8b-4ac6-bbd9-a65b5e1d1e29' (that is, hex with
    format 8-4-4-4-12, so 32 informative characters and overall length 36
    including the hyphens). The space is 16^32 = 3.4e38. See
    https://docs.python.org/3.7/library/uuid.html.
    """
    return str(uuid.uuid4())


# =============================================================================
# Model classes
# =============================================================================

class Document(Base):
    """
    Represents a user-submitted document for processing. (A single document
    may be processed by multiple processors.)
    """
    __tablename__ = 'documents'

    document_id = Column(
        "document_id",
        VARCHAR(MAX_DOC_ID_LEN), primary_key=True,
        comment="Primary key (UUID) for the document"
    )  # type: str
    doctext = deferred(Column(
        "doctext",
        Text,
        comment="Text contents of the document"
    ))  # type: Optional[str]
    client_job_id = Column(
        "client_job_id",
        VARCHAR(MAX_JOB_ID_LEN),
        comment="Client job ID (supplied by the client)",
        index=True
    )  # type: Optional[str]
    queue_id = Column(
        "queue_id",
        VARCHAR(MAX_QUEUE_ID_LEN),
        comment="The UUID of the client request, if in queued mode",
        index=True
    )  # type: Optional[str]
    username = Column(
        "username",
        VARCHAR(MAX_USERNAME_LEN),
        comment="Username that submitted this document",
        nullable=False,
        index=True,
    )  # type: Optional[str]
    client_metadata = deferred(Column(
        "client_metadata",
        Text,
        comment="Metadata submitted by the client"
    ))  # type: Optional[str]
    include_text = Column(
        "include_text",
        Boolean,
        nullable=False,
        default=False,
        comment="Include the source text in the reply?"
    )  # type: Optional[bool]
    datetime_submitted_utc = Column(
        "datetime_submitted_utc",
        DateTime,
        nullable=False,
        # Is the following OK, given that it's not exactly when it was
        # submitted?
        default=datetime.datetime.utcnow,
        comment="Date/time when the request was submitted (in UTC)"
    )  # type: Optional[datetime.datetime]

    docprocrequests = relationship(
        "DocProcRequest",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="document",
        lazy="select",
        # https://docs.sqlalchemy.org/en/13/orm/collections.html#using-passive-deletes  # noqa
    )  # type: List[DocProcRequest]

    @property
    def datetime_submitted_pendulum(self) -> Optional[Pendulum]:
        return coerce_to_pendulum(self.datetime_submitted_utc,
                                  assume_local=False)


class DocProcRequest(Base):
    """
    SQLAlchemy table recording processor requests for a given document (that
    is, document/processor pairs).
    """  # noqa
    __tablename__ = 'docprocrequests'

    docprocrequest_id = Column(
        "docprocrequest_id",
        VARCHAR(MAX_DOCPROC_ID_LEN), primary_key=True,
        comment="Primary key (UUID) for the document/processor pair; also "
                "used as the Celery task ID"
    )  # type: str
    document_id = Column(
        "document_id",
        VARCHAR(MAX_DOC_ID_LEN),
        ForeignKey("documents.document_id", ondelete='CASCADE'),
        # ... delete DocProcRequests when their Documents are deleted
        # ... https://stackoverflow.com/questions/5033547/sqlalchemy-cascade-delete  # noqa
        # ... https://docs.sqlalchemy.org/en/13/orm/collections.html#using-passive-deletes  # noqa
        nullable=False,
        comment="Document ID (FK to documents.document_id)"
    )  # type: str
    processor_id = Column(
        "processor_id",
        VARCHAR(MAX_PROCESSOR_ID_LEN),
        nullable=False,
        comment="Processor ID, in '<name>_<version>' format"
    )  # type: str
    done = Column(
        "done",
        Boolean,
        nullable=False,
        default=False,
        comment="Has the task associated with this request been completed?"
    )  # type: bool
    when_done_utc = Column(
        "when_done_utc",
        DateTime,
        default=None,
        comment="Date/time when the request was completed (in UTC)"
    )  # type: Optional[datetime.datetime]
    results = deferred(Column(
        "results",
        Text,
        comment="Results (as JSON)"
    ))  # type: Optional[str]

    document = relationship(
        "Document",
        back_populates="docprocrequests",
        lazy="select",
    )  # type: Document

    @property
    def doctext(self) -> Optional[str]:
        return self.document.doctext
