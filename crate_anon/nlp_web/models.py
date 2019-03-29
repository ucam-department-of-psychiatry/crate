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

DBSession = scoped_session(
    sessionmaker(extension=ZopeTransactionExtension()))
Base = declarative_base()


class Document(Base):
    """
    .. todo:: INSERT DOCSTRING FOR Document
    """
    # Check about indexes etc.
    __tablename__ = 'documents'
    # document_id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(VARCHAR(50), primary_key=True)
    doctext = Column(Text)
    client_job_id = Column(Text)
    # 'queue_id' refers to the id of the client request if in queued mode
    queue_id = Column(VARCHAR(50))
    username = Column(Text)
    # should be a JSON string representing:
    # [processor_id1, processor_id2]
    processor_ids = Column(Text)
    client_metadata = Column(Text)
    result_ids = Column(Text)
    include_text = Column(Boolean)
    # Is the following OK, given that it's not exactly when it was submitted?
    datetime_submitted = Column(DateTime, default=datetime.datetime.utcnow)


class DocProcRequest(Base):
    """
    .. todo:: INSERT DOCSTRING FOR DocProcRequest
    """
    __tablename__ = 'docprocrequests'
    # docprocrequest_id = Column(Integer, primary_key=True, autoincrement=True)
    docprocrequest_id = Column(VARCHAR(50), primary_key=True)
    document_id = Column(VARCHAR(50))
    doctext = Column(Text)
    processor_id = Column(VARCHAR(50))
