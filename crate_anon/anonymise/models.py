"""
crate_anon/anonymise/models.py

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

**SQLAlchemy ORM models for the CRATE anonymiser, representing information it
stores in its admin database.**

To create a SQLAlchemy Table programmatically:

- https://docs.sqlalchemy.org/en/latest/core/schema.html
- https://stackoverflow.com/questions/5424942/sqlalchemy-model-definition-at-execution
- https://stackoverflow.com/questions/2580497/database-on-the-fly-with-scripting-languages/2580543#2580543

To create a SQLAlchemy ORM programmatically:

- https://stackoverflow.com/questions/2574105/sqlalchemy-dynamic-mapping/2575016#2575016
"""  # noqa: E501

import logging
import random
from typing import Optional, TYPE_CHECKING, Union

from cardinal_pythonlib.sqlalchemy.orm_query import exists_orm
from sqlalchemy import (
    Column,
    Text,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.orm.session import Session

from crate_anon.anonymise import SecretBase
from crate_anon.anonymise.config_singleton import config
from crate_anon.anonymise.constants import (
    MAX_TRID,
    PatientInfoConstants,
    TABLE_KWARGS,
    TridType,
)

if TYPE_CHECKING:
    from crate_anon.anonymise.scrub import PersonalizedScrubber

log = logging.getLogger(__name__)


class PatientInfo(SecretBase):
    """
    Represent patient information in the secret admin database.

    Design decision in this class:

    - It gets too complicated if you try to make the fieldnames arbitrary and
      determined by the config.

    - So we always use 'pid', 'rid', etc.

        - Older config settings that this decision removes:

          .. code-block:: none

            mapping_patient_id_fieldname
            mapping_master_id_fieldname

        - Note that the following are still actively used, as they can be used
          to set the names in the OUTPUT database (not the mapping database):

          .. code-block:: none

            research_id_fieldname
            trid_fieldname
            master_research_id_fieldname
            source_hash_fieldname

    - The config is allowed to set three column types:

        - the source PID type (e.g. INT, BIGINT, VARCHAR)
        - the source MPID type (e.g. BIGINT)
        - the encrypted (RID, MRID) type, which is set by the encryption
          algorithm; e.g. VARCHAR(128) for SHA-512.
    """

    __tablename__ = PatientInfoConstants.SECRET_MAP_TABLENAME
    __table_args__ = TABLE_KWARGS

    pid = Column(
        PatientInfoConstants.PID_FIELDNAME,
        config.pidtype,
        primary_key=True,
        autoincrement=False,
        comment="Patient ID (PID) (PK)",
    )
    rid = Column(
        PatientInfoConstants.RID_FIELDNAME,
        config.sqltype_encrypted_pid,
        nullable=False,
        unique=True,
        comment="Research ID (RID)",
    )
    trid = Column(
        PatientInfoConstants.TRID_FIELDNAME,
        TridType,
        unique=True,
        comment="Transient integer research ID (TRID)",
    )
    mpid = Column(
        PatientInfoConstants.MPID_FIELDNAME,
        config.mpidtype,
        comment="Master patient ID (MPID)",
    )
    mrid = Column(
        PatientInfoConstants.MRID_FIELDNAME,
        config.sqltype_encrypted_pid,
        comment="Master research ID (MRID)",
    )
    scrubber_hash = Column(
        "scrubber_hash",
        config.sqltype_encrypted_pid,
        comment="Scrubber hash (for change detection)",
    )
    patient_scrubber_text = Column(
        "_raw_scrubber_patient",
        Text,
        comment="Raw patient scrubber (for debugging only)",
    )
    tp_scrubber_text = Column(
        "_raw_scrubber_tp",
        Text,
        comment="Raw third-party scrubber (for debugging only)",
    )

    def ensure_rid(self) -> None:
        """
        Ensure that :attr:`rid` is a hashed version of :attr:`pid`.
        """
        assert self.pid is not None
        if self.rid is not None:
            return
        self.rid = config.encrypt_primary_pid(self.pid)

    def ensure_trid(self, session: Session) -> None:
        """
        Ensure that :attr:`trid` is a suitable transient research ID
        (TRID): the TRID we have already generated for this PID, or a fresh
        random integer that we'll remember.

        Args:
            session: SQLAlchemy database session for the secret admin database
        """
        assert self.pid is not None
        if self.trid is not None:
            return
        # noinspection PyTypeChecker
        self.trid = TridRecord.get_trid(session, self.pid)

    def set_mpid(self, mpid: Union[int, str]) -> None:
        """
        Sets the MPID, and at the same time, the MRID (a hashed version of the
        MPID).

        Args:
            mpid: master patient ID (MPID) value
        """
        self.mpid = mpid
        self.mrid = config.encrypt_master_pid(self.mpid)

    def set_scrubber_info(self, scrubber: "PersonalizedScrubber") -> None:
        """
        Sets our :attr:`scrubber_hash` to be the hash of the scrubber passed as
        a parameter.

        If our :class:`crate_anon.anonymise.config.Config` has its
        ``save_scrubbers`` flag set, then we also save the textual regex
        string for the patient scrubber and the third-party scrubber.

        Args:
            scrubber: :class:`crate_anon.anonymise.scrub.PersonalizedScrubber`
        """
        self.scrubber_hash = scrubber.get_hash()
        if config.save_scrubbers:
            self.patient_scrubber_text = scrubber.get_patient_regex_string()
            self.tp_scrubber_text = scrubber.get_tp_regex_string()
        else:
            self.patient_scrubber_text = None  # type: Optional[str]
            self.tp_scrubber_text = None  # type: Optional[str]


class TridRecord(SecretBase):
    """
    Records the mapping from patient ID (PID) to integer transient research ID
    (TRID), and makes new TRIDs as required.
    """

    __tablename__ = "secret_trid_cache"
    __table_args__ = TABLE_KWARGS

    pid = Column(
        "pid",
        config.pidtype,
        primary_key=True,
        autoincrement=False,
        comment="Patient ID (PID) (PK)",
    )
    trid = Column(
        "trid",
        TridType,
        nullable=False,
        unique=True,
        comment="Transient integer research ID (TRID)",
    )

    @classmethod
    def get_trid(cls, session: Session, pid: Union[int, str]) -> int:
        """
        Looks up the PID in the database and returns its corresponding TRID.
        If there wasn't one, make a new one, store the mapping, and return the
        new TRID.

        Args:
            session: SQLAlchemy database session for the secret admin database
            pid: patient ID (PID) value

        Returns:
            integer TRID

        """
        try:
            obj = session.query(cls).filter(cls.pid == pid).one()
            return obj.trid
        except NoResultFound:
            return cls.new_trid(session, pid)

    @classmethod
    def new_trid(cls, session: Session, pid: Union[int, str]) -> int:
        """
        Creates a new TRID: a random integer that's not yet been used as a
        TRID.

        We check for existence by inserting and asking the database if it's
        happy, not by asking the database if it exists (since other processes
        may be doing the same thing at the same time).
        """
        while True:
            session.begin_nested()
            candidate = random.randint(1, MAX_TRID)
            log.debug(f"Trying candidate TRID: {candidate}")
            # noinspection PyArgumentList
            obj = cls(pid=pid, trid=candidate)
            try:
                session.add(obj)
                session.commit()  # may raise IntegrityError
                return candidate
            except IntegrityError:
                session.rollback()


class OptOutPid(SecretBase):
    """
    Records the PID values of patients opting out of the anonymised database.
    """

    __tablename__ = "opt_out_pid"
    __table_args__ = TABLE_KWARGS

    pid = Column(
        "pid",
        config.pidtype,
        primary_key=True,
        autoincrement=False,
        comment="Patient ID",
    )
    # If autoincrement is not specified, it becomes "auto", which turns on the
    # autoincrement behaviour if the column is of integer type and a primary
    # key (see sqlalchemy.sql.schema.Column.__init__). In turn, that (under SQL
    # Server) likely makes it an IDENTITY column, this being an SQL Server
    # mechanism for auto-incrementing
    # (https://docs.microsoft.com/en-us/sql/t-sql/statements/create-table-transact-sql-identity-property?view=sql-server-ver16).  # noqa: E501
    # And in turn that means that when a value is explicitly inserted, it gives
    # the error "Cannot insert explicit value for identity column in table
    # 'opt_out_pid' when IDENTITY_INSERT is set to OFF. (544)"

    @classmethod
    def opting_out(cls, session: Session, pid: Union[int, str]) -> bool:
        """
        Is this patient opting out?

        Args:
            session: SQLAlchemy database session for the secret admin database
            pid: PID of the patient to test

        Returns:
            opting out?

        """
        return exists_orm(session, cls, cls.pid == pid)

    @classmethod
    def add(cls, session: Session, pid: Union[int, str]) -> None:
        """
        Add a record of a patient who wishes to opt out.

        Args:
            session: SQLAlchemy database session for the secret admin database
            pid: PID of the patient who is opting out
        """
        log.debug(f"Adding opt-out for PID {pid}")
        # noinspection PyArgumentList
        newthing = cls(pid=pid)
        session.merge(newthing)
        # https://stackoverflow.com/questions/12297156/fastest-way-to-insert-object-if-it-doesnt-exist-with-sqlalchemy  # noqa: E501


class OptOutMpid(SecretBase):
    """
    Records the MPID values of patients opting out of the anonymised database.
    """

    __tablename__ = "opt_out_mpid"
    __table_args__ = TABLE_KWARGS

    mpid = Column(
        "mpid",
        config.mpidtype,
        primary_key=True,
        autoincrement=False,
        comment="Patient ID",
    )
    # See OptOutPid above re autoincrement.

    @classmethod
    def opting_out(cls, session: Session, mpid: Union[int, str]) -> bool:
        """
        Is this patient opting out?

        Args:
            session: SQLAlchemy database session for the secret admin database
            mpid: MPID of the patient to test

        Returns:
            opting out?

        """
        return exists_orm(session, cls, cls.mpid == mpid)

    @classmethod
    def add(cls, session: Session, mpid: Union[int, str]) -> None:
        """
        Add a record of a patient who wishes to opt out.

        Args:
            session: SQLAlchemy database session for the secret admin database
            mpid: MPID of the patient who is opting out
        """
        log.debug(f"Adding opt-out for MPID {mpid}")
        # noinspection PyArgumentList
        newthing = cls(mpid=mpid)
        session.merge(newthing)
