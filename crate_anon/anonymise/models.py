#!/usr/bin/env python
# crate_anon/anonymise/models.py

"""
To create a SQLAlchemy Table programmatically:
    http://docs.sqlalchemy.org/en/latest/core/schema.html
    http://stackoverflow.com/questions/5424942/sqlalchemy-model-definition-at-execution  # noqa
    http://stackoverflow.com/questions/2580497/database-on-the-fly-with-scripting-languages/2580543#2580543  # noqa

To create a SQLAlchemy ORM programmatically:
    http://stackoverflow.com/questions/2574105/sqlalchemy-dynamic-mapping/2575016#2575016  # noqa
"""

import logging
import random

from sqlalchemy import (
    Column,
    MetaData,
    Text,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.exc import NoResultFound

from crate_anon.anonymise.constants import (
    MAX_TRID,
    MYSQL_TABLE_ARGS,
    PidType,
    TridType,
)
from crate_anon.anonymise.config_singleton import config
from crate_anon.anonymise.sqla import exists_orm


log = logging.getLogger(__name__)
admin_meta = MetaData()
AdminBase = declarative_base(metadata=admin_meta)


class PatientInfo(AdminBase):
    __tablename__ = 'secret_map'
    __table_args__ = MYSQL_TABLE_ARGS

    pid = Column(
        'pid', PidType,
        primary_key=True, autoincrement=False,
        doc="Patient ID (PID) (PK)")
    rid = Column(
        'rid', config.SqlTypeEncryptedPid,
        nullable=False, unique=True,
        doc="Research ID (RID)")
    trid = Column(
        'trid', TridType,
        unique=True,
        doc="Transient integer research ID (TRID)")
    mpid = Column(
        'mpid', PidType,
        doc="Master patient ID (MPID)")
    mrid = Column(
        'mrid', config.SqlTypeEncryptedPid,
        doc="Master research ID (MRID)")
    scrubber_hash = Column(
        'scrubber_hash', config.SqlTypeEncryptedPid,
        doc="Scrubber hash (for change detection)")
    patient_scrubber_text = Column(
        "_raw_scrubber_patient", Text,
        doc="Raw patient scrubber (for debugging only)")
    tp_scrubber_text = Column(
        "_raw_scrubber_tp", Text,
        doc="Raw third-party scrubber (for debugging only)")

    def ensure_rid(self):
        assert self.pid is not None
        if self.rid:
            return
        self.rid = config.encrypt_primary_pid(self.pid)

    def ensure_trid(self, session):
        assert self.pid is not None
        if self.trid is not None:
            return
        self.trid = TridRecord.get_trid(session, self.pid)

    def set_mpid(self, mpid):
        self.mpid = mpid
        self.mrid = config.encrypt_master_pid(self.mpid)

    def set_scrubber_info(self, scrubber):
        self.scrubber_hash = scrubber.get_hash()
        if config.save_scrubbers:
            self.patient_scrubber_text = scrubber.get_patient_regex_string()
            self.tp_scrubber_text = scrubber.get_tp_regex_string()
        else:
            self.patient_scrubber_text = None
            self.tp_scrubber_text = None


class TridRecord(AdminBase):
    __tablename__ = 'secret_trid_cache'
    __table_args__ = MYSQL_TABLE_ARGS

    pid = Column(
        "pid", PidType,
        primary_key=True, autoincrement=False,
        doc="Patient ID (PID) (PK)")
    trid = Column(
        "trid", TridType,
        nullable=False, unique=True,
        doc="Transient integer research ID (TRID)")

    @classmethod
    def get_trid(cls, session, pid):
        try:
            obj = session.query(cls).filter(cls.pid == pid).one()
            return obj.trid
        except NoResultFound:
            return cls.new_trid(session, pid)

    @classmethod
    def new_trid(cls, session, pid):
        """
        We check for existence by inserting and asking the database if it's
        happy, not by asking the database if it exists (since other processes
        may be doing the same thing at the same time).
        """
        while True:
            session.begin_nested()
            candidate = random.randint(1, MAX_TRID)
            log.debug("Trying candidate TRID: {}".format(candidate))
            obj = cls(pid=pid, trid=candidate)
            try:
                session.add(obj)
                session.commit()  # may raise IntegrityError
                return candidate
            except IntegrityError:
                session.rollback()


class OptOutPid(AdminBase):
    __tablename__ = 'opt_out_pid'
    __table_args__ = MYSQL_TABLE_ARGS

    pid = Column(
        'pid', PidType,
        primary_key=True,
        doc="Patient ID")

    @classmethod
    def opting_out(cls, session, pid):
        return exists_orm(session, cls, cls.pid == pid)

    @classmethod
    def add(cls, session, pid):
        log.debug("Adding opt-out for PID {}".format(pid))
        newthing = cls(pid=pid)
        session.merge(newthing)
        # http://stackoverflow.com/questions/12297156/fastest-way-to-insert-object-if-it-doesnt-exist-with-sqlalchemy  # noqa


class OptOutMpid(AdminBase):
    __tablename__ = 'opt_out_mpid'
    __table_args__ = MYSQL_TABLE_ARGS

    mpid = Column(
        'mpid', PidType,
        primary_key=True,
        doc="Patient ID")

    @classmethod
    def opting_out(cls, session, mpid):
        return exists_orm(session, cls, cls.mpid == mpid)

    @classmethod
    def add(cls, session, mpid):
        log.debug("Adding opt-out for MPID {}".format(mpid))
        newthing = cls(mpid=mpid)
        session.merge(newthing)
