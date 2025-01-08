"""
crate_anon/testing/models.py

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

**Factory Boy SQL Alchemy test models.**

"""

import datetime
import enum
import os
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    Date,
    DateTime,  # NB name clash with pendulum
    Enum,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import relationship

from crate_anon.anonymise.constants import (
    COMMENT,
    TABLE_KWARGS,
)
from crate_anon.testing import SourceTestBase

if TYPE_CHECKING:
    from sqlalchemy.sql.type_api import TypeEngine
    from sqlalchemy.sql.compiler import SQLCompiler

MAX_EXT_LENGTH_WITH_DOT = 10
PATIENT_ID_COMMENT = "Patient ID"


# =============================================================================
# BLOB type
# =============================================================================


# http://docs.sqlalchemy.org/en/latest/core/custom_types.html
# noinspection PyUnusedLocal
@compiles(LargeBinary, "mysql")
def compile_blob_mysql(
    type_: "TypeEngine", compiler: "SQLCompiler", **kw
) -> str:
    """
    Provides a custom type for the SQLAlchemy ``LargeBinary`` type under MySQL,
    by using ``LONGBLOB`` (which overrides the default of ``BLOB``).

    MySQL: https://dev.mysql.com/doc/refman/5.7/en/storage-requirements.html

    .. code-block:: none

        TINYBLOB: up to 2^8 bytes
        BLOB: up to 2^16 bytes = 64 KiB
        MEDIUMBLOB: up to 2^24 bytes = 16 MiB  <-- minimum for docs
        LONGBLOB: up to 2^32 bytes = 4 GiB

        VARBINARY: up to 65535 = 64 KiB

    SQL Server: https://msdn.microsoft.com/en-us/library/ms188362.aspx

    .. code-block:: none

        BINARY: up to 8000 bytes = 8 KB
        VARBINARY(MAX): up to 2^31 - 1 bytes = 2 GiB <-- minimum for docs
        IMAGE: deprecated; up to 2^31 - 1 bytes = 2 GiB
            https://msdn.microsoft.com/en-us/library/ms187993.aspx

    SQL Alchemy:

    .. code-block:: none

        _Binary: base class
        LargeBinary: translates to BLOB in MySQL
        VARBINARY, as an SQL base data type
        dialects.mysql.base.LONGBLOB
        dialects.mssql.base.VARBINARY

    Therefore, we can take the LargeBinary type and modify it.
    """
    return "LONGBLOB"  # would have been "BLOB"


# If this goes wrong for future versions of SQL Server, write another
# specializer to produce "VARBINARY(MAX)" instead of "IMAGE". I haven't done
# that because it may be that SQL Alchemy is reading the SQL Server version
# (it definitely executes "select @@version") and specializing accordingly.

SexColType = String(length=1)


# =============================================================================
# A silly enum
# =============================================================================
class EnumColours(enum.Enum):
    """
    A silly enum, for testing.
    """

    red = 1
    green = 2
    blue = 3


# =============================================================================
# Tables
# =============================================================================


class Patient(SourceTestBase):
    """
    SQLAlchemy ORM class for fictional patients.
    """

    __tablename__ = "patient"
    __table_args__ = {
        COMMENT: "Fictional patients",
        **TABLE_KWARGS,
    }

    patient_id = Column(
        Integer,
        primary_key=True,
        autoincrement=False,
        comment=PATIENT_ID_COMMENT,
    )
    sex = Column(
        SexColType,
        comment="Sex (M, F, X)",
    )
    forename = Column(String(50), comment="Forename")
    surname = Column(String(50), comment="Surname")
    dob = Column(Date, comment="Date of birth (DOB)")
    nullfield = Column(Integer, comment="Always NULL")
    nhsnum = Column(BigInteger, comment="NHS number")
    phone = Column(String(50), comment="Phone number")
    postcode = Column(String(50), comment="Postcode")
    optout = Column(
        Boolean, default=False, comment="Opt out from research database?"
    )
    related_patient_id = Column(
        Integer,
        ForeignKey("patient.patient_id"),
        comment="ID of another patient",
    )
    related_patient = relationship(
        "Patient", uselist=False, remote_side=[patient_id]
    )
    related_patient_relationship = Column(
        String(50),
        comment="Decription of relationship between patient and relation",
    )
    colour = Column(
        Enum(EnumColours),
        nullable=True,
        comment="An enum column, which may be red/green/blue",
    )  # new in v0.18.41

    @property
    def related_patient_name(self) -> str:
        if self.related_patient is None:
            return ""

        forename = self.related_patient.forename
        surname = self.related_patient.surname

        return f"{forename} {surname}"


class Note(SourceTestBase):
    """
    SQLAlchemy ORM class for fictional notes.
    """

    __tablename__ = "note"
    __table_args__ = {
        COMMENT: "Fictional textual notes",
        **TABLE_KWARGS,
    }

    note_id = Column(Integer, primary_key=True, comment="Note ID")
    patient_id = Column(
        Integer, ForeignKey("patient.patient_id"), comment=PATIENT_ID_COMMENT
    )
    note = Column(Text, comment="Text of the note")
    note_datetime = Column(DateTime, comment="Date/time of the note")

    patient = relationship("Patient")


class BlobDoc(SourceTestBase):
    """
    SQLAlchemy ORM class for fictional binary documents.
    """

    __tablename__ = "blobdoc"
    __table_args__ = {
        COMMENT: "Fictional documents as binary large objects",
        **TABLE_KWARGS,
    }

    blob_doc_id = Column(
        Integer, primary_key=True, comment="Binary document ID"
    )
    patient_id = Column(
        Integer, ForeignKey("patient.patient_id"), comment=PATIENT_ID_COMMENT
    )
    blob = Column(
        LargeBinary, comment="The BLOB (binary large object)"
    )  # modified as above!
    extension = Column(
        String(MAX_EXT_LENGTH_WITH_DOT), comment="Filename extension"
    )
    blob_datetime = Column(DateTime, comment="Date/time of the document")

    patient = relationship("Patient")

    def __init__(
        self, patient: Patient, filename: str, blob_datetime: datetime.datetime
    ) -> None:
        """
        Args:
            patient: corresponding :class:`Patient` object
            filename: filename containing the binary document to load and
                store in the database
            blob_datetime: date/time value to give this BLOB
        """
        _, extension = os.path.splitext(filename)
        with open(filename, "rb") as f:
            contents = f.read()  # will be of type 'bytes'
        # noinspection PyArgumentList
        super().__init__(
            patient=patient,
            blob=contents,
            extension=extension,
            blob_datetime=blob_datetime,
        )


class FilenameDoc(SourceTestBase):
    """
    SQLAlchemy ORM class for a table containing the filenames of binary
    documents.
    """

    __tablename__ = "filenamedoc"
    __table_args__ = {
        COMMENT: "Filenames of binary documents",
        **TABLE_KWARGS,
    }

    filename_doc_id = Column(Integer, primary_key=True, comment="Filename ID")
    patient_id = Column(
        Integer, ForeignKey("patient.patient_id"), comment=PATIENT_ID_COMMENT
    )
    filename = Column(Text, comment="Filename")
    file_datetime = Column(DateTime, comment="Date/time of the document")

    patient = relationship("Patient")
