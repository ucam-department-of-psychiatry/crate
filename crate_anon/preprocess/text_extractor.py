"""
crate_anon/preprocess/text_extractor.py

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

**Extract text from a document store prior to anonymisation.**

"""

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import re
import traceback
from typing import Generator, Optional, Tuple

from cardinal_pythonlib.extract_text import (
    document_to_text,
    ext_map,
    TextProcessingConfig,
)
from cardinal_pythonlib.sqlalchemy.schema import (
    make_bigint_autoincrement_column,
)
from pendulum import DateTime as Pendulum
from sqlalchemy import (
    BigInteger,
    Column,
    Connection,
    CursorResult,
    DateTime,
    insert,
    select,
    String,
    Table,
    UnicodeText,
    update,
)
from sqlalchemy.engine.base import Engine
from sqlalchemy.exc import IntegrityError, MultipleResultsFound, NoResultFound
from sqlalchemy.sql.schema import MetaData

from crate_anon.anonymise.constants import AnonymiseConfigDefaults
from crate_anon.common.sql import add_indexes, IndexCreationInfo

from crate_anon.preprocess.constants import (
    CRATE_COL_FILE_PATH,
    CRATE_COL_PK,
    CRATE_COL_TEXT,
    CRATE_COL_TEXT_LAST_EXTRACTED,
    CRATE_IDX_PREFIX,
    CRATE_TABLE_EXTRACTED_TEXT,
)
from crate_anon.preprocess.systmone_ddgen import (
    contextual_tablename,
    S1GenericCol,
    S1Table,
    SystmOneContext,
)

log = logging.getLogger(__name__)


class TextExtractor:
    def __init__(
        self,
        engine: Engine,
        metadata: MetaData,
        context: SystmOneContext,
        root_directory: str,
        drop_table: bool = False,
        plain: bool = AnonymiseConfigDefaults.EXTRACT_TEXT_PLAIN,
        width: int = AnonymiseConfigDefaults.EXTRACT_TEXT_WIDTH,
    ) -> None:
        self.engine = engine
        self.metadata = metadata
        self.context = context
        self.root_directory = root_directory
        self.drop_table = drop_table
        self.plain = plain
        self.width = width

        self.extensions = list(ext_map)
        self.extensions.remove(None)

    def extract_all(self) -> None:
        self.create_table()
        self.process_files()

    def create_table(self) -> None:
        self.extracted_text_table = self.metadata.tables.get(
            CRATE_TABLE_EXTRACTED_TEXT
        )

        drop_table = self.extracted_text_table is not None and self.drop_table
        create_table = self.extracted_text_table is None or self.drop_table

        if drop_table:
            self.extracted_text_table.drop(checkfirst=True)

        if create_table:
            self.extracted_text_table = self.get_table_definition()
            self.extracted_text_table.create(self.engine, checkfirst=True)
            self.index_table()

    def generate_filenames(self) -> Generator[Tuple[str, str], None, None]:
        log.info(f"Extracting text from {self.root_directory}...")
        for dirpath, dirnames, filenames in os.walk(self.root_directory):
            log.debug(f"Processing {dirpath}")
            for filename in filenames:
                yield dirpath, filename

    def index_table(self) -> None:
        for column in self.extracted_text_table.columns:
            colname = column.name
            if colname in self.indexed_column_names:
                idxname = f"{CRATE_IDX_PREFIX}_{colname}"
                add_indexes(
                    self.engine,
                    self.extracted_text_table,
                    [
                        IndexCreationInfo(
                            index_name=idxname, column=colname, unique=False
                        )
                    ],
                )

    def process_files(self) -> None:
        raise NotImplementedError(
            "Implement 'process_files()' in derived class!"
        )

    @property
    def indexed_column_names(self) -> list[str]:
        raise NotImplementedError(
            "Implement 'indexed_column_names' property in derived class!"
        )

    def get_table_definition(self) -> Table:
        raise NotImplementedError(
            "Implement 'get_table_definition()' in derived class!"
        )

    def extract_text_from_file(
        self, full_path: str, extension: str
    ) -> Tuple[Optional[str], Pendulum]:
        last_extracted = None
        text = None
        if extension in self.extensions:
            log.info("... extracting text...")
            try:
                config = TextProcessingConfig(
                    width=self.width, plain=self.plain
                )
                text = document_to_text(filename=full_path, config=config)
                log.info("... extracted.")
            except Exception as e:
                traceback.print_exc()
                log.error(f"... caught exception from document_to_text: {e}")
        else:
            log.info(f"... unsupported file extension '{extension}'.")

        if text is not None:
            last_extracted = Pendulum.now()

        return text, last_extracted


@dataclass
class SystmOneDocumentInfo:
    full_path: str
    row_identifier: int
    document_uid: str
    extension: str

    def __post_init__(self) -> None:
        self.relative_path = str(Path(*Path(self.full_path).parts[-2:]))


class SystmOneTextExtractor(TextExtractor):
    indexed_column_names = [
        CRATE_COL_PK,
        S1GenericCol.ROW_ID,
        S1GenericCol.PATIENT_ID,
    ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.documents_table = self.metadata.tables[
            contextual_tablename(S1Table.DOCUMENTS, self.context)
        ]

    def get_table_definition(self) -> Table:
        return Table(
            CRATE_TABLE_EXTRACTED_TEXT,
            self.metadata,
            make_bigint_autoincrement_column(CRATE_COL_PK),
            Column(
                S1GenericCol.ROW_ID,
                BigInteger,
                comment="FK to S1_Documents",
                nullable=False,
            ),
            Column(
                S1GenericCol.PATIENT_ID,
                BigInteger,
                comment="Patient ID from S1_Documents",
                nullable=False,
            ),
            Column(
                "DocumentUID",
                String(16),
                comment="Unique ID of document",
                nullable=False,
            ),
            Column(
                CRATE_COL_FILE_PATH,
                String(255),
                comment="Path relative to docstore",
                unique=True,
            ),
            Column(
                CRATE_COL_TEXT,
                UnicodeText,
                comment="Extracted text from file",
            ),
            Column(
                CRATE_COL_TEXT_LAST_EXTRACTED,
                DateTime,
                comment="Date/time text was last extracted",
            ),
        )

    def process_files(self) -> None:
        with self.engine.connect() as connection:
            for doc_info in self.generate_matches():
                self.process_file(connection, doc_info)
                connection.commit()

    def process_file(
        self, connection: Connection, doc_info: SystmOneDocumentInfo
    ) -> None:
        log.info(f"Processing {doc_info.full_path}...")

        if self.already_extracted(connection, doc_info):
            log.info("... already extracted.")
            return

        row = self.get_documents_table_row(connection, doc_info)
        if row is not None:
            patient_id = row._mapping[S1GenericCol.PATIENT_ID]
            self.extract_text_into_database(connection, doc_info, patient_id)

    def already_extracted(
        self, connection: Connection, doc_info: SystmOneDocumentInfo
    ) -> bool:
        row = self.get_extracted_text_table_row(connection, doc_info)
        if row is None:
            return False

        last_extracted = row._mapping[CRATE_COL_TEXT_LAST_EXTRACTED]
        return last_extracted is not None

    def get_extracted_text_table_row(
        self, connection: Connection, doc_info: SystmOneDocumentInfo
    ) -> CursorResult:

        relative_path = doc_info.relative_path

        statement = select(self.extracted_text_table).where(
            self.extracted_text_table.c.crate_file_path == relative_path
        )
        return connection.execute(statement).one_or_none()

    def extract_text_into_database(
        self,
        connection: Connection,
        doc_info: SystmOneDocumentInfo,
        patient_id: int,
    ) -> None:
        text, last_extracted = self.extract_text_from_file(
            doc_info.full_path, doc_info.extension
        )

        values = dict(
            RowIdentifier=doc_info.row_identifier,
            DocumentUID=doc_info.document_uid,
            IDPatient=patient_id,
            crate_file_path=doc_info.relative_path,
            crate_text=text,
            crate_text_last_extracted=last_extracted,
        )

        statement = insert(self.extracted_text_table).values(**values)
        try:
            connection.execute(statement)
        except IntegrityError:
            statement = (
                update(self.extracted_text_table)
                .values(**values)
                .where(
                    self.extracted_text_table.c.crate_file_path
                    == doc_info.relative_path
                )
            )

    def get_documents_table_row(
        self, connection: Connection, doc_info: SystmOneDocumentInfo
    ) -> CursorResult:
        row = None
        row_identifier = doc_info.row_identifier

        statement = select(self.documents_table).where(
            self.documents_table.c.RowIdentifier == row_identifier
        )
        try:
            row = connection.execute(statement).one()
        except NoResultFound:
            log.error(f"... no row found for RowIdentifier: {row_identifier}")
        except MultipleResultsFound:
            log.error(
                "... multiple rows found with RowIdentifier: "
                f"{row_identifier}"
            )

        return row

    def generate_matches(
        self,
    ) -> Generator[Tuple[SystmOneDocumentInfo], None, None]:
        # Groups:
        # 1: RowIdentifier
        # 2: DocumentUID (sometimes incorrectly set to IDOrganisation)
        # 3: Subfolder 1-4
        # 4: Index where document split across files
        # 5: Extension, mixed case
        regex = r"(\d+)_([0-9a-f]+)_(\d+)_(\d+)(\.\S+)"

        for dirpath, filename in self.generate_filenames():
            file_path = os.path.join(dirpath, filename)
            if m := re.match(regex, filename):
                yield SystmOneDocumentInfo(
                    full_path=file_path,
                    row_identifier=int(m.group(1)),
                    document_uid=m.group(2),
                    extension=m.group(5).lower(),
                )
            else:
                log.info(f"Completely ignoring {file_path}")
