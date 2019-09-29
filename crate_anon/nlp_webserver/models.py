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
    relationship,
    scoped_session,
    sessionmaker,
)
from sqlalchemy.sql.schema import ForeignKey
# noinspection PyPackageRequirements
from zope.sqlalchemy import ZopeTransactionExtension

Session = sessionmaker(extension=ZopeTransactionExtension())
DBSession = scoped_session(Session)

# DBSession = scoped_session(
#     sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()

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
    # Check about indexes etc.
    __tablename__ = 'documents'
    document_id = Column(
        "document_id",
        VARCHAR(MAX_DOC_ID_LEN), primary_key=True,
        comment="Primary key (unique ID) for the document"
    )  # type: str
    doctext = Column(
        "doctext",
        Text,
        comment="Text contents of the document"
    )  # type: Optional[str]
    client_job_id = Column(
        "client_job_id",
        VARCHAR(MAX_JOB_ID_LEN),
        comment="Client job ID (supplied by the client)",
        index=True
    )  # type: Optional[str]
    queue_id = Column(
        "queue_id",
        VARCHAR(MAX_QUEUE_ID_LEN),
        comment="Refers to the id of the client request if in queued mode",
        index=True
    )  # type: Optional[str]
    username = Column(
        "username",
        VARCHAR(MAX_USERNAME_LEN),
        comment="Username that submitted this document",
        index=True,
    )  # type: Optional[str]
    processor_ids = Column(
        "processor_ids",
        Text,
        comment="JSON string representing: [processor_id1, processor_id2]"
    )  # type: Optional[str]
    client_metadata = Column(
        "client_metadata",
        Text,
        comment="Metadata submitted by the client"
    )  # type: Optional[str]
    result_ids = Column(
        "result_ids",
        Text,
        comment="JSON-encoded list of result IDs"
    )  # type: Optional[str]
    include_text = Column(
        "include_text",
        Boolean,
        comment="Include the source text in the reply?"
    )  # type: Optional[bool]
    datetime_submitted = Column(
        "datetime_submitted",
        DateTime,
        # Is the following OK, given that it's not exactly when it was
        # submitted?
        default=datetime.datetime.utcnow,
        comment="Date/time when the request was submitted (in UTC)"
    )  # type: Optional[datetime.datetime]

    docprocrequests = relationship(
        "DocProcRequest",
        back_populates="document"
    )  # type: List[DocProcRequest]

    @property
    def datetime_submitted_pendulum(self) -> Optional[Pendulum]:
        return coerce_to_pendulum(self.datetime_submitted, assume_local=False)


class DocProcRequest(Base):
    """
    SQLAlchemy table recording processor requests for a given document (that
    is, document/processor pairs).

    Note the size inefficiency, but speed efficiency (?), of storing the text
    as part of the DocProcRequest, rather than cross-referencing to the
    :class:`Document`.
    """  # noqa
    __tablename__ = 'docprocrequests'
    docprocrequest_id = Column(
        "docprocrequest_id",
        VARCHAR(MAX_DOCPROC_ID_LEN), primary_key=True,
        comment="Primary key (unique ID) for the document/processor pair"
    )  # type: str
    document_id = Column(
        "document_id",
        VARCHAR(MAX_DOC_ID_LEN),
        ForeignKey("documents.document_id"),
        comment="Document ID (FK to documents.document_id)"
    )  # type: str
    processor_id = Column(
        "processor_id",
        VARCHAR(MAX_PROCESSOR_ID_LEN),
        comment="Processor ID, in '<name>_<version>' format"
    )  # type: str
    done = Column(
        "done",
        Boolean,
        default=False,
        comment="Has the task associated with this request been completed?"
    )  # type: bool
    when_done = Column(
        "when_done",
        DateTime,
        default=None,
        comment="Date/time when the request was completed (in UTC)"
    )

    document = relationship(
        "Document",
        back_populates="docprocrequests"
    )  # type: Document

    @property
    def doctext(self) -> Optional[str]:
        return self.document.doctext
