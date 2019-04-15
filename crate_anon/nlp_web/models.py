#!/usr/bin/env python

r"""
crate_anon/nlp_web/models.py

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

from sqlalchemy import (
    Column,
    Text,
    VARCHAR,
    Boolean,
    DateTime,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import (
    scoped_session,
    sessionmaker,
)
# noinspection PyPackageRequirements
from zope.sqlalchemy import ZopeTransactionExtension

# testing
Session = sessionmaker(extension=ZopeTransactionExtension())
DBSession = scoped_session(Session)

# DBSession = scoped_session(
#     sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()


class Document(Base):
    """
    Represents a user-submitted document for processing. (A single document
    may be processed by multiple processors)
    """
    # Check about indexes etc.
    __tablename__ = 'documents'
    # document_id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(
        VARCHAR(50), primary_key=True,
        comment="Primary key for the document"
    )
    doctext = Column(
        Text,
        comment="Text contents of the document"
    )
    client_job_id = Column(
        Text,
        comment="Client job ID"
    )
    queue_id = Column(
        VARCHAR(50),
        comment="Refers to the id of the client request if in queued mode"
    )
    username = Column(
        Text,
        comment="Username that submitted this document"
    )
    # should be a JSON string representing:
    # [processor_id1, processor_id2]
    processor_ids = Column(
        Text,
        comment="JSON string representing: [processor_id1, processor_id2]"
    )
    client_metadata = Column(
        Text,
        comment="Metadata submitted by the client"
    )
    result_ids = Column(
        Text,
        comment="JSON-encoded list of result IDs"
    )
    include_text = Column(
        Boolean,
        comment="Include the source text in the reply?"
    )
    datetime_submitted = Column(
        DateTime,
        # Is the following OK, given that it's not exactly when it was submitted?  # noqa
        default=datetime.datetime.utcnow,
        comment="Date/time when the request was submitted"
    )


class DocProcRequest(Base):
    """
    SQLAlchemy table containing processor requests for a given document?

    .. todo:: *** CLARIFY

    """
    __tablename__ = 'docprocrequests'
    # docprocrequest_id = Column(Integer, primary_key=True, autoincrement=True)
    docprocrequest_id = Column(
        VARCHAR(50), primary_key=True,
        comment="???"  # ***
    )
    document_id = Column(
        VARCHAR(50),
        comment="???"  # ***
    )
    doctext = Column(
        Text,
        comment="???"  # ***
    )
    processor_id = Column(
        VARCHAR(50),
        comment="???"  # ***
    )
