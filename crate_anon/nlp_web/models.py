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
    __tablename__ = 'docprocrequests'
    # docprocrequest_id = Column(Integer, primary_key=True, autoincrement=True)
    docprocrequest_id = Column(VARCHAR(50), primary_key=True)
    document_id = Column(VARCHAR(50))
    doctext = Column(Text)
    processor_id = Column(VARCHAR(50))
