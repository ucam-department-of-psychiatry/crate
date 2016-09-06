#!/usr/bin/env python
# crate_anon/nlp_manager/models.py

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import Column, Index, MetaData
from sqlalchemy.types import BigInteger, DateTime, String

from crate_anon.anonymise.constants import MAX_PID_STR, MYSQL_TABLE_KWARGS
from crate_anon.nlp_manager.constants import (
    HashClass,
    SqlTypeDbIdentifier,
)

progress_meta = MetaData()
ProgressBase = declarative_base(metadata=progress_meta)


# =============================================================================
# Global constants
# =============================================================================

encrypted_length = len(HashClass("dummysalt").hash(MAX_PID_STR))
SqlTypeHash = String(encrypted_length)


# =============================================================================
# Record of progress
# =============================================================================

class NlpRecord(ProgressBase):
    """
    Class to record the fact of processing a source record (and to keep a hash
    allowing identification of altered source contents later).
    """
    __tablename__ = 'crate_nlp_progress'
    __table_args__ = (
        Index('_idx1',  # index name
              # index fields:
              'srcdb', 'srctable', 'srcpkfield', 'srcpkval', 'srcfield',
              'nlpdef',
              unique=True),
        MYSQL_TABLE_KWARGS
    )
    # http://stackoverflow.com/questions/6626810/multiple-columns-index-when-using-the-declarative-orm-extension-of-sqlalchemy  # noqa
    # http://docs.sqlalchemy.org/en/latest/orm/extensions/declarative/table_config.html  # noqa

    pk = Column(
        'pk', BigInteger, primary_key=True, autoincrement=True,
        doc="PK of NLP record (no specific use)")
    srcdb = Column(
        'srcdb', SqlTypeDbIdentifier,
        doc="Source database")
    srctable = Column(
        'srctable', SqlTypeDbIdentifier,
        doc="Source table name")
    srcpkfield = Column(
        'srcpkfield', SqlTypeDbIdentifier,
        doc="Primary key column name in source table")
    srcpkval = Column(
        'srcpkval', BigInteger,
        doc="Primary key value in source table")
    srcfield = Column(
        'srcfield', SqlTypeDbIdentifier,
        doc="Name of column in source field containing actual data")
    nlpdef = Column(
        'nlpdef', SqlTypeDbIdentifier,
        doc="Name of natural language processing definition that source was "
            "processed for")
    whenprocessedutc = Column(
        'whenprocessedutc', DateTime,
        doc="Time that NLP record was processed")
    srchash = Column(
        'srchash', SqlTypeHash,
        doc='Secure hash of source field contents at the time of processing')
