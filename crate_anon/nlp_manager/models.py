#!/usr/bin/env python

"""
crate_anon/nlp_manager/models.py

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

**SQLAlchemy ORM models for the NLP progress database.**

"""

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.schema import Column, Index, MetaData
from sqlalchemy.types import BigInteger, DateTime, String

from crate_anon.anonymise.constants import TABLE_KWARGS
from crate_anon.nlp_manager.constants import (
    HashClass,
    MAX_STRING_PK_LENGTH,
    SqlTypeDbIdentifier,
)

progress_meta = MetaData()
ProgressBase = declarative_base(metadata=progress_meta)

FN_SRCHASH = "srchash"


# =============================================================================
# Global constants
# =============================================================================

SqlTypeHash = HashClass("dummysalt").sqla_column_type()


# =============================================================================
# Record of progress
# =============================================================================

class NlpRecord(ProgressBase):
    """
    Class to record the fact of processing a source record for a particular
    kind of NLP (and to keep a hash allowing identification of altered source
    contents later).
    """
    __tablename__ = 'crate_nlp_progress'
    __table_args__ = (
        Index(
            '_idx1',  # index name
            #  index fields:
            'srcpkval',   # integer and most specific
            'nlpdef',     # usually >1 NLP def to 1 db/table/field combo
            'srcfield',   # } roughly, more to less specific?
            'srctable',   # }
            'srcdb',      # }
            'srcpkstr',   # last as we may not use it
            # - performance is critical here
            # - put them in descending order of specificity
            #   http://stackoverflow.com/questions/2292662/how-important-is-the-order-of-columns-in-indexes  # noqa
            # - start with srcpkval, as it's (a) specific and (b) integer
            # - srcpkfield: don't need to index, because the source table
            #   can only have one PK
            # - srcpkstr: must include, since srcpkval can be non-unique,
            #   due to hash collisions, if we're using a string
            #   ... but ?should be last because we may not use it in
            #   queries (for tables with integer PK)
            unique=True
            # Despite having a NULL field in a UNIQUE index, this is OK for
            # SQL Server 2008+ (http://stackoverflow.com/questions/767657) and
            # MySQL also seems happy.
        ),
        TABLE_KWARGS
    )
    # http://stackoverflow.com/questions/6626810/multiple-columns-index-when-using-the-declarative-orm-extension-of-sqlalchemy  # noqa
    # http://docs.sqlalchemy.org/en/latest/orm/extensions/declarative/table_config.html  # noqa

    pk = Column(
        'pk', BigInteger, primary_key=True, autoincrement=True,
        doc="PK of NLP record (no specific use)")
    srcdb = Column(
        'srcdb', SqlTypeDbIdentifier, doc="Source database"
        # primary_key=True
    )
    srctable = Column(
        'srctable', SqlTypeDbIdentifier, doc="Source table name"
        # primary_key=True
    )
    srcpkfield = Column(
        'srcpkfield', SqlTypeDbIdentifier,
        doc="Primary key column name in source table (for info only)")
    srcpkval = Column(
        'srcpkval', BigInteger,
        doc="Primary key value in source table (or hash if PK is a string)"
        # primary_key=True
    )
    srcpkstr = Column(
        'srcpkstr', String(MAX_STRING_PK_LENGTH),
        doc="Original string PK, used when the table has a string PK, to deal "
            "with hash collisions. Max length: {}".format(
            MAX_STRING_PK_LENGTH)
        # primary_key=True, default=''  # can't have a NULL in a composite PK
    )
    srcfield = Column(
        'srcfield', SqlTypeDbIdentifier,
        doc="Name of column in source field containing actual data"
        # primary_key=True
    )
    nlpdef = Column(
        'nlpdef', SqlTypeDbIdentifier,
        doc="Name of natural language processing definition that source was "
            "processed for"
        # primary_key=True
    )
    whenprocessedutc = Column(
        'whenprocessedutc', DateTime,
        doc="Time that NLP record was processed (batch time that the run was "
            "commenced for that NLP definition; UTC)")
    srchash = Column(
        FN_SRCHASH, SqlTypeHash,
        doc='Secure hash of source field contents at the time of processing')
