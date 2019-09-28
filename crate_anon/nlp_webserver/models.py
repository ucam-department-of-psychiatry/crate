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
from typing import Optional

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
    scoped_session,
    sessionmaker,
)
# from sqlalchemy.schema import Index
# noinspection PyPackageRequirements
from zope.sqlalchemy import ZopeTransactionExtension

Session = sessionmaker(extension=ZopeTransactionExtension())
DBSession = scoped_session(Session)

# DBSession = scoped_session(
#     sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()


class Document(Base):
    """
    Represents a user-submitted document for processing. (A single document
    may be processed by multiple processors.)
    """
    # Check about indexes etc.
    __tablename__ = 'documents'
    document_id = Column(
        VARCHAR(50), primary_key=True,
        comment="Primary key (unique ID) for the document"
    )  # type: str
    doctext = Column(
        Text,
        comment="Text contents of the document"
    )  # type: Optional[str]
    client_job_id = Column(
        Text,
        comment="Client job ID"
    )  # type: Optional[str]
    queue_id = Column(
        VARCHAR(50),
        comment="Refers to the id of the client request if in queued mode"
    )  # type: Optional[str]
    username = Column(
        Text,
        comment="Username that submitted this document"
    )  # type: Optional[str]
    processor_ids = Column(
        Text,
        comment="JSON string representing: [processor_id1, processor_id2]"
    )  # type: Optional[str]
    client_metadata = Column(
        Text,
        comment="Metadata submitted by the client"
    )  # type: Optional[str]
    result_ids = Column(
        Text,
        comment="JSON-encoded list of result IDs"
    )  # type: Optional[str]
    include_text = Column(
        Boolean,
        comment="Include the source text in the reply?"
    )  # type: Optional[bool]
    datetime_submitted = Column(
        DateTime,
        # Is the following OK, given that it's not exactly when it was
        # submitted?
        default=datetime.datetime.utcnow,
        comment="Date/time when the request was submitted (in UTC)"
    )  # type: Optional[datetime.datetime]

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

    .. todo:: ask FS: is the storage of doctext here (too) optimal?
    .. todo:: ask FS: is VARCHAR(50) enough for processor_id? Probably not now I've messed with it (fully qualified class names)

    """  # noqa
    __tablename__ = 'docprocrequests'
    docprocrequest_id = Column(
        VARCHAR(50), primary_key=True,
        comment="Primary key (unique ID) for the document/processor pair"
    )  # type: str
    document_id = Column(
        VARCHAR(50),
        comment="Document ID (FK to documents.document_id)"
    )  # type: str
    doctext = Column(
        Text,
        comment="Text of the document to processs"
    )  # type: str
    processor_id = Column(
        VARCHAR(100),
        comment="Processor ID, in '<name>_<version>' format"
    )  # type: str
    done = Column(
        Boolean,
        default=False,
        comment="Has the task associated with this request been completed?"
    )  # type: bool
    date_done = Column(
        DateTime,
        default=None,
        comment="Date/time when the request was completed (in UTC)"
    )
