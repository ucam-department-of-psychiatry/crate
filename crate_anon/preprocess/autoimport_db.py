"""
crate_anon/preprocess/autoimport_db.py

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

**Automatically import to a database from a collection of tabular files.**

Efficiency is challenging here. Simple CSV/TSV files are efficiently handled
as file-like objects, and can be iterated in a low-memory way very fast.
Spreadsheet-type objects often need to be loaded "whole", so repeat iteration
is less sensible. We're trying to handle both, so no perfect/simple way.

"""

import argparse
import csv
import datetime
from itertools import zip_longest
import logging
from operator import attrgetter
from pathlib import Path
import tempfile
from typing import (
    Any,
    BinaryIO,
    Callable,
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    Tuple,
    Union,
)
import zipfile

from cardinal_pythonlib.lists import chunks
from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from rich_argparse import ArgumentDefaultsRichHelpFormatter
import openpyxl  # xlrd might be faster...
from openpyxl.cell.cell import Cell
import pendulum
import pendulum.parsing.exceptions
import pyexcel_ods
from sqlalchemy.engine import create_engine, Engine
from sqlalchemy.orm.session import sessionmaker, Session
from sqlalchemy.sql.expression import insert
from sqlalchemy.sql.schema import Column, MetaData, Table
from sqlalchemy.sql.sqltypes import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    String,
)
from sqlalchemy.sql.type_api import TypeEngine

from crate_anon.anonymise.constants import CHARSET

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

SPREADSHEET_DICT_ROW_TYPE = Dict[str, Any]
DEFAULT_CHUNKSIZE = int(1e5)
DEFAULT_COL_TYPE = String(1)
FIRST_SHEET_ONLY_MSG = (
    "Only reading the first sheet of this file. See --use_spreadsheet_names."
)
WARNING_VALUES_VISIBLE = (
    "WARNING: not suitable for production use (may show actual data values). "
    "Use for testing only."
)


# =============================================================================
# Data type detection functions
# =============================================================================


def does_datetime_have_zero_time(
    d: Union[datetime.datetime, pendulum.DateTime]
) -> bool:
    """
    Does a given datetime-like object have all its time fields set to zero?
    """
    return d.hour == d.minute == d.second == d.microsecond == 0


def is_date_like_not_datetime_like(v: Any) -> bool:
    """
    Does this look like a date (but not a datetime)?
    """
    if isinstance(v, datetime.date):
        # NB a datetime.datetime is also an instance of datetime.date (but not
        # the reverse)
        if isinstance(v, datetime.datetime):
            return does_datetime_have_zero_time(v)
        else:
            return True
    elif isinstance(v, pendulum.Date):
        # Likewise, pendulum.DateTime is an instance of pendulum.Date.
        if isinstance(v, pendulum.DateTime):
            return does_datetime_have_zero_time(v)
        else:
            return True
    elif isinstance(v, str):
        try:
            d = pendulum.parse(v)
        except (pendulum.parsing.exceptions.ParserError, ValueError):
            return False
        # pendulum.parse() can return a pendulum.DateTime, or a
        # pendulum.Duration.
        if isinstance(d, pendulum.DateTime):
            return does_datetime_have_zero_time(d)
        else:
            return False
    else:
        return False


def is_datetime_or_date_like(v: Any) -> bool:
    """
    Does this look like a datetime (or a date)?
    """
    if isinstance(
        v, (datetime.date, datetime.datetime, pendulum.Date, pendulum.DateTime)
    ):
        return True
    elif isinstance(v, str):
        try:
            d = pendulum.parse(v)
        except (pendulum.parsing.exceptions.ParserError, ValueError):
            return False
        return isinstance(d, pendulum.DateTime)
    else:
        return False


# =============================================================================
# Column type detection
# =============================================================================


def mk_columns(
    datagen: Iterable[SPREADSHEET_DICT_ROW_TYPE], verbose: bool = False
) -> List[Column]:
    """
    Attempt to autodetect SQLAlchemy column types.

    Args:
        datagen:
            Generator of data.
        verbose:
            Be verbose and report values? (WARNING: therefore unsuitable for
            production use.)
    """
    coldict = {}  # type: Dict[str, ColumnTypeDetector]
    for row in datagen:
        for k, v in row.items():
            if k is None:
                raise ValueError(
                    "Sheet has missing column headings; headings are: "
                    f"{list(row.keys())}"
                )
            try:
                d = coldict[k]
            except KeyError:
                d = ColumnTypeDetector(
                    k, default_type=DEFAULT_COL_TYPE, verbose=verbose
                )
                coldict[k] = d
            d.inspect(v)
    return [c.sqlalchemy_column() for c in coldict.values()]


# =============================================================================
# Helper classes
# =============================================================================


class TabularFileInfo:
    """
    Simple class to represent information about a potential database table,
    from a tabular data file format.
    """

    def __init__(
        self,
        tablename: str,
        datagen: Iterable[SPREADSHEET_DICT_ROW_TYPE] = None,
        with_columns: bool = False,
        with_data: bool = False,
        verbose: bool = False,
    ) -> None:
        """
        Args:
            tablename:
                Name of the table.
            datagen:
                Optional iterable to provide data. (Must be supplied if
                with_columns or with_data is True.)
            with_columns:
                Provide column information, for creating tables?
            with_data:
                Provide data?
            verbose:
                Be verbose if the process fails? WARNING: will report values.
        """
        self.tablename = tablename
        self.with_columns = with_columns
        self.with_data = with_data

        # If requested, a list of SQLAlchemy columns to create:
        self.columns = None  # type: Optional[List[Column]]
        # If requested, a generator for data (with each dictionary mapping
        # column name to value):
        self.data_generator = (
            None
        )  # type: Optional[Iterable[SPREADSHEET_DICT_ROW_TYPE]]

        if with_columns or with_data:
            assert datagen is not None
        # Don't use a generator twice:
        if with_columns and with_data:
            data = list(datagen)  # consumes the generator
            self.columns = mk_columns(data, verbose=verbose)
            self.data_generator = data
        elif with_columns:
            self.columns = mk_columns(datagen, verbose=verbose)
            # ... consumes the generator
        elif with_data:
            self.data_generator = datagen
            # generator unused, ready for use

        # Internal cached SQLAlchemy table:
        self._table = None  # type: Optional[Table]

    def has_columns(self) -> bool:
        """
        Do we have at least one column?
        """
        return bool(self.columns)

    def validate_columns(self) -> None:
        """
        Validates columns, or raises ValueError.
        """
        if self.columns is None:
            log.warning("Validating columns, but there aren't any")
            return
        if not self.columns:
            raise ValueError(f"Table {self.tablename} has no columns")
        colnames = [c.name for c in self.columns]
        if len(colnames) != len(set(colnames)):
            raise ValueError(
                f"Table {self.tablename} has duplicate columns: {colnames!r}"
            )

    def colreport(self) -> str:
        """
        A text-format report of our columns.
        """
        if self.columns is None:
            raise ValueError(
                f"Can't produce column report: table {self.tablename} "
                f"has no columns"
            )
        return "\n".join(f"- {c!r}" for c in self.columns)

    def table(self, metadata: MetaData) -> Table:
        """
        Returns an SQLAlchemy table object. Caches this across requests (or
        SQLAlchemy will complain that we re-assign columns to a table). Assumes
        that the MetaData object WILL NOT CHANGE ACROSS CALLS.
        """
        if self._table is None:
            self._table = Table(
                self.tablename, metadata, *(self.columns or ())
            )
        return self._table


class ColumnTypeDetector:
    """
    Class to inspect values from a spreadsheet column, and make a decision
    about what kind of SQLAlchemy column should be used.
    """

    def __init__(
        self,
        colname: str,
        values: Iterable[Any] = None,
        default_type: TypeEngine = None,
        verbose: bool = False,
    ) -> None:
        """
        Args:
            colname:
                Future column name.
            values:
                Optional values to inspect immediately.
            default_type:
                Type to use if no non-NULL data whatsoever is seen.
            verbose:
                Report values on failure. WARNING: unsuitable, for this reason,
                for production code.
        """
        if not colname:
            raise ValueError("Missing column name")
        if "\t" in colname:
            raise ValueError(
                f"Likely TSV file being read as CSV, because column name "
                f"includes tabs: {colname!r}"
            )

        self.colname = colname
        self.default_type = default_type
        self.verbose = verbose

        # None/NULL types:
        self.seen_none = False

        # Sanity check
        self.seen_something_not_none = False

        # Non-string types:
        self.seen_bool = False
        self.seen_int = False
        self.seen_float = False
        # self.min_numeric = math.inf
        # self.max_numeric = -math.inf

        # String and string-derived types:
        self.seen_str = False
        self.seen_date = False
        self.seen_datetime = False
        self.seen_str_not_date_or_datetime = False
        self.max_strlen = 0

        # For verbose mode:
        self.inspected = set()

        # If created with values:
        if values is not None:
            for v in values:
                self.inspect(v)

    def __str__(self) -> str:
        """
        String representation.
        """
        try:
            c = self.sqlalchemy_column()
        except ValueError:
            c = "<no_known_column_type>"
        return f"{self.colname}: {c}"

    def inspect(self, v: Any) -> None:
        """
        Inspect a new value.
        """
        if self.verbose:
            self.inspected.add(v)
        if v is None:
            self.seen_none = True
            return
        self.seen_something_not_none = True
        if isinstance(v, bool):
            self.seen_bool = True
            return
        if isinstance(v, int):
            self.seen_int = True
            # self.min_numeric = min(self.min_numeric, v)
            # self.max_numeric = max(self.max_numeric, v)
            return
        if isinstance(v, float):
            self.seen_float = True
            # self.min_numeric = min(self.min_numeric, v)
            # self.max_numeric = max(self.max_numeric, v)
            return
        is_str = isinstance(v, str)
        if is_date_like_not_datetime_like(v):
            self.seen_date = True
            if is_str:
                self.max_strlen = max(len(v), self.max_strlen)
        elif is_datetime_or_date_like(v):
            self.seen_datetime = True
            if is_str:
                self.max_strlen = max(len(v), self.max_strlen)
        elif is_str:
            # NB A string that does not look like a date/datetime.
            self.seen_str = True
            self.max_strlen = max(len(v), self.max_strlen)
            self.seen_str_not_date_or_datetime = True
        else:
            raise ValueError(f"Unexpected value of type {type(v)}")
            # Implausible that we will get a BLOB via a spreadsheet.

    def _values_seen_suffix(self) -> str:
        """
        In verbose mode, returns a string suffix (for error messages) showing
        what values we've seen.
        """
        return ": " + repr(self.inspected) if self.verbose else ""

    def _sqla_coltype(self) -> TypeEngine:
        """
        Returns the SQLAlchemy column type to use, or raises ValueError.

        Copes with simple types (and NULL/None values):

        - bool -> Boolean
        - int -> BigInteger
        - float -> Float
        - date -> Date
        - datetime -> DateTime
        - str (interpretable as date) -> Date
        - str (interpretable as datetime, but not date) -> DateTime
        - str (otherwise) -> String (of the maximum length seen)

        Copes with mixtures:

        - int + float -> Float
        - date and date-as-str ("date-like") -> Date
        - datetime and datetime-as-str ("datetime-like") -> DateTime
        - date-like + datetime-like -> DateTime
        - {date-like or datetime-like} and {str not interpretable as date or
          datetime} -> String

        Failure conditions (raises ValueError):

        - nothing seen
        - only NULL/None values seen
        - more than one type among {bool, int, float}
        - string type and {bool, int, float} type
        - something not recognized as above

        """
        if not self.seen_something_not_none:
            if self.default_type is not None:
                return self.default_type
            raise ValueError(
                f"Column type {self.colname}: no data seen yet and no "
                f"default type"
            )
        is_numeric = self.seen_int or self.seen_float
        n_non_string_based = sum([self.seen_bool, is_numeric])
        if n_non_string_based > 1:
            raise ValueError(
                f"Column {self.colname}: mixed non-string types"
                + self._values_seen_suffix()
            )
        if n_non_string_based > 0 and self.seen_str:
            raise ValueError(
                f"Column {self.colname}: mixed string/non-string types"
                + self._values_seen_suffix()
            )
        # If we get here, either it's string-derived, or a single non-string
        # type.
        if self.seen_bool:
            return Boolean()
        elif is_numeric:
            if self.seen_float:
                return Float()
            else:
                return BigInteger()
        elif self.seen_str_not_date_or_datetime:
            return String(length=max(1, self.max_strlen))
        elif self.seen_datetime:
            return DateTime()
        elif self.seen_date:
            return Date()
        else:
            raise AssertionError("Type analysis bug")

    def sqlalchemy_column(self, nullable: bool = None) -> Column:
        """
        Returns an SQLAlchemy Column object (free-floating, i.e. with no table
        attached), or raises ValueError.

        Args:
            nullable:
                Should the column be NULL-capable? Use True for "NULL", False
                for "NOT NULL", and None for "NULL if NULL/None values have
                been seen, otherwise NOT NULL".
        """
        if nullable is None:
            nullable = self.seen_none
        elif not nullable and self.seen_none:
            raise ValueError(
                f"Column {self.colname}: requested nullable=False but have "
                f"seen a NULL value"
            )
        return Column(
            self.colname,
            self._sqla_coltype(),
            nullable=nullable,
        )


# =============================================================================
# Spreadsheet generator functions
# =============================================================================


def is_single_sheet_filetype(ext_lower: str) -> bool:
    """
    Does this file extension indicate a file type containing just a single
    sheet/table of values?
    """
    return ext_lower in [".csv", ".tsv"]


def is_multisheet_filetype(ext_lower: str) -> bool:
    """
    Does this file extension indicate a file type containing just multiple
    sheets/tables of values?
    """
    return ext_lower in [".ods", ".xlsx"]


def ods_row_to_list(row: List[Any]) -> List[Any]:
    """
    Convert an OpenOffice ODS row to a list of values, translating the empty
    string (used for empty cells) to None.
    """
    return [None if v == "" else v for v in row]


def xlsx_row_to_list(row: List[Cell]) -> List[Any]:
    """
    Convert an OpenPyXL XLSX row to a list of values, translating the empty
    string (used for empty cells) to None.
    """
    return [None if cell.value == "" else cell.value for cell in row]


def dict_from_rows(
    row_iterator: Iterable[List], row_to_list_fn: Callable[[List], List]
) -> Generator[Dict, None, None]:
    """
    Iterate through rows (from row_iterator); apply row_to_list_fn() to each;
    yield dictionaries mapping column names to values.
    """
    headings = []  # type: List[str]
    first_row = True
    for row in row_iterator:
        values = row_to_list_fn(row)
        if first_row:
            headings = values
            first_row = False
        else:
            if not bool(list(filter(None, values))):
                # skip blank rows
                continue
            # Care required here. If values is shorter than headings, zip()
            # will just discard headings that don't have a value. So use
            # zip_longest().
            d = dict(zip_longest(headings, values))
            yield d


def translate_empty_str_to_none(
    reader: Iterable[Dict[str, Any]]
) -> Generator[SPREADSHEET_DICT_ROW_TYPE, None, None]:
    """
    Yield dictionaries (mapping column name to value), but
    (a) translating blank strings (often the product of empty cells e.g. with
    csv.DictReader) to None; (b) skipping entirely blank rows.

    Args:
        reader:
            For example, a csv.DictReader().
    """
    for row in reader:
        d = {k: (None if v == "" else v) for k, v in row.items()}
        if d:  # skip blank rows
            yield d


def gen_dicts_from_csv(
    fileobj: BinaryIO,
) -> Generator[SPREADSHEET_DICT_ROW_TYPE, None, None]:
    """
    Generates value dictionaries from a CSV file.
    """
    reader = csv.DictReader(fileobj)
    yield from translate_empty_str_to_none(reader)


def gen_dicts_from_tsv(
    fileobj: BinaryIO,
) -> Generator[SPREADSHEET_DICT_ROW_TYPE, None, None]:
    """
    Generates value dictionaries from a TSV file.
    """
    reader = csv.DictReader(fileobj, delimiter="\t")
    yield from translate_empty_str_to_none(reader)


def gen_sheets_from_ods(
    fileobj: BinaryIO, first_sheet_only: bool = False
) -> Generator[Tuple[str, Iterable[SPREADSHEET_DICT_ROW_TYPE]], None, None]:
    """
    Generates tuples of (sheet name, iterable-of-value-dictionaries) from an
    ODS file.
    """
    data = pyexcel_ods.get_data(fileobj)
    # That's an ordered dictionary, whose keys are spreadsheet names.
    if first_sheet_only:
        log.warning(FIRST_SHEET_ONLY_MSG)
    for sheetname, sheetdata in data.items():
        yield sheetname, dict_from_rows(
            sheetdata, row_to_list_fn=ods_row_to_list
        )
        if first_sheet_only:
            return


def gen_sheets_from_xlsx(
    fileobj: BinaryIO, first_sheet_only: bool = False
) -> Generator[Tuple[str, Iterable[SPREADSHEET_DICT_ROW_TYPE]], None, None]:
    """
    Generates tuples of (sheet name, iterable-of-value-dictionaries) from an
    Excel XLSX file.
    """
    workbook = openpyxl.load_workbook(
        fileobj,
        read_only=True,
        keep_vba=False,
        data_only=True,
        keep_links=False,
    )
    # No obvious bug now (with openpyxl==3.0.7) with read-only mode.
    if first_sheet_only:
        log.warning(FIRST_SHEET_ONLY_MSG)
    for worksheet in workbook.worksheets:
        yield worksheet.title, dict_from_rows(
            worksheet.iter_rows(), row_to_list_fn=xlsx_row_to_list
        )
        if first_sheet_only:
            return


# =============================================================================
# File-related generator functions
# =============================================================================


def get_read_mode(path: Path) -> str:
    """
    What file reading mode to use, i.e. is it binary or text?
    """
    ext = path.suffix.lower()
    return "r" if ext in (".csv", ".tsv") else "rb"


def gen_files_from_zipfile(
    zipfilename: Union[Path, str]
) -> Generator[Tuple[Path, BinaryIO], None, None]:
    """
    Iterates ZIP file(s), yielding filenames and corresponding file-like
    objects from within it/them.

    Args:
        zipfilename: filename of the ``.zip`` file

    Yields:
        tuple (Path, file-like object) for each inner file

    NB related to ``cardinal_pythonlib.file_io.gen_files_from_zipfiles``, but
    simpler and also provides the filenames.
    """
    with zipfile.ZipFile(zipfilename) as zf:
        infolist = zf.infolist()  # type: List[zipfile.ZipInfo]
        infolist.sort(key=attrgetter("filename"))
        for zipinfo in infolist:
            log.info(
                f"Within zip file: {zipfilename} - "
                f"reading subfile: {zipinfo.filename}"
            )
            with tempfile.TemporaryDirectory() as tmpdir:
                zf.extract(zipinfo.filename, tmpdir)
                diskfilename = Path(tmpdir) / zipinfo.filename
                with open(
                    diskfilename, get_read_mode(diskfilename)
                ) as subfile:
                    yield Path(zipinfo.filename), subfile


def gen_filename_fileobj(
    filenames: List[str],
) -> Generator[Tuple[Path, BinaryIO], None, None]:
    """
    Iterates files, yielding (filename, file-like object) tuples. If a file is
    a ZIP file, iterate within it similarly (but not recursively).

    Args:
        filenames:
            Filenames to process.

    Yields:
        tuple (Path, file-like object) for each inner file
    """
    for filename in filenames:
        p = Path(filename)
        if not p.is_file():
            raise ValueError(f"Not a file: {p}")
        log.info(f">>> Processing file: {p}")
        ext = p.suffix.lower()
        if ext == ".zip":
            yield from gen_files_from_zipfile(p)
        else:
            with open(p, get_read_mode(p)) as f:
                yield p, f


def gen_tablename_info(
    filenames: List[str],
    use_spreadsheet_names: bool = True,
    with_columns: bool = False,
    with_data: bool = False,
    skip_tables: List[str] = None,
    verbose: bool = False,
) -> Generator[TabularFileInfo, None, None]:
    """
    Args:
        filenames:
            Filenames to iterate through.
        use_spreadsheet_names:
            Use spreadsheet names (where relevant) as table names, rather than
            filenames. (If False, only the first sheet in each spreadsheet
            file will be used.)
        with_columns:
            Provide column information, for creating tables?
        with_data:
            Provide data?
        skip_tables:
            Optional names of tables to skip.
        verbose:
            Be verbose if the process fails? WARNING: will report values.

    Yields:
        TabularFileInfo instances.
    """
    skip_tables = skip_tables or []
    for path, fileobj in gen_filename_fileobj(filenames):
        ext = path.suffix.lower()
        if is_single_sheet_filetype(ext):
            tablename = path.stem
            if tablename in skip_tables:
                log.warning(f"Skipping table: {tablename}")
                continue
            if ext == ".csv":
                dictgen = gen_dicts_from_csv(fileobj)
            elif ext == ".tsv":
                dictgen = gen_dicts_from_tsv(fileobj)
            else:
                raise AssertionError("Bug")
            yield TabularFileInfo(
                tablename=tablename,
                datagen=dictgen,
                with_columns=with_columns,
                with_data=with_data,
                verbose=verbose,
            )
        elif is_multisheet_filetype(ext):
            if ext == ".ods":
                sheetgen = gen_sheets_from_ods
            elif ext == ".xlsx":
                sheetgen = gen_sheets_from_xlsx
            else:
                raise AssertionError("Bug")
            for sheetname, sheetdatagen in sheetgen(
                fileobj, first_sheet_only=not use_spreadsheet_names
            ):
                log.info(f"... Processing sheet: {sheetname}")
                tablename = sheetname if use_spreadsheet_names else path.stem
                if tablename in skip_tables:
                    log.warning(f"Skipping table: {tablename}")
                    continue
                yield TabularFileInfo(
                    tablename=tablename,
                    datagen=sheetdatagen,
                    with_columns=with_columns,
                    with_data=with_data,
                    verbose=verbose,
                )
        else:
            log.warning(f"Unknown file type: {path}")
            continue


# =============================================================================
# Database functios
# =============================================================================


def drop_table(
    ti: TabularFileInfo, engine: Engine, metadata: MetaData
) -> None:
    """
    Drop a database table, if it exists.
    """
    log.info(f"Dropping table (if it exists): {ti.tablename}")
    # See also crate_anon.anonymise.subset_db.drop_dst_table_if_exists().
    t = ti.table(metadata)  # doesn't need columns
    t.drop(engine, checkfirst=True)
    # No COMMIT required after DDL.
    metadata.remove(t)


def create_table(
    ti: TabularFileInfo,
    engine: Engine,
    metadata: MetaData,
) -> None:
    """
    Create a database table, if it doesn't already exist.
    """
    log.info(
        "Creating table (if it doesn't exist): "
        f"{ti.tablename}\n{ti.colreport()}"
    )
    t = ti.table(metadata)
    t.create(engine, checkfirst=True)
    # No COMMIT required after DDL.


def import_table(
    ti: TabularFileInfo,
    session: Session,
    metadata: MetaData,
    chunksize: int = DEFAULT_CHUNKSIZE,
) -> None:
    """
    Import a database table.
    """
    log.info(f"Importing to table: {ti.tablename}")
    t = ti.table(metadata)
    data = list(ti.data_generator)
    for datachunk in chunks(data, chunksize):
        log.debug(f"Inserting {len(datachunk)} rows...")
        session.execute(insert(t), datachunk)
    session.commit()


# =============================================================================
# Importer
# =============================================================================


def auto_import_db(
    url: str,
    filenames: List[str],
    use_spreadsheet_names: bool = True,
    drop_tables: bool = False,
    create_tables: bool = False,
    import_data: bool = False,
    chunksize: int = DEFAULT_CHUNKSIZE,
    skip_tables: List[str] = None,
    echo: bool = False,
    verbose: bool = False,
) -> None:
    """
    Main import function.

    Args:
        url:
            Database URL.
        filenames:
            Filenames to iterate through.
        use_spreadsheet_names:
            Use spreadsheet names (where relevant) as table names, rather than
            filenames. (If False, only the first sheet in each spreadsheet
            file will be used.)
        drop_tables:
            Drop tables first?
        create_tables:
            Create tables, if required?
        import_data:
            Do the actual import?
        skip_tables:
            Optional names of tables to skip.
        chunksize:
            Number of records to insert at once.
        echo:
            Echo SQL?
        verbose:
            Be verbose?
    """
    engine = create_engine(url, echo=echo, encoding=CHARSET)
    session = sessionmaker(bind=engine)()  # type: Session
    metadata = MetaData(bind=engine)

    log.info("Processing...")
    for ti in gen_tablename_info(
        filenames,
        use_spreadsheet_names=use_spreadsheet_names,
        with_columns=create_tables,
        with_data=import_data,
        skip_tables=skip_tables,
        verbose=verbose,
    ):
        if drop_tables:
            drop_table(ti, engine, metadata)
        if create_tables or import_data:
            if not ti.has_columns():
                log.warning(
                    f"Skipping creation/import for table {ti.tablename!r}, "
                    f"which has no columns"
                )
                continue
            ti.validate_columns()
        if create_tables:
            create_table(ti, engine, metadata)
        if import_data:
            import_table(ti, session, metadata, chunksize=chunksize)
    log.info("Finished.")


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        formatter_class=ArgumentDefaultsRichHelpFormatter,
        description="""
Take data from one or several tabular files (e.g. CSV, ODS, TSV, XLSX), or ZIP
files containing these. Import that data to a database, if necessary creating
the tables required. Use the filename as the table name (or, with
use_spreadsheet_names, use the names of sheets within multi-sheet spreadsheet
files). The assumption is that within each tabular set of data, the first row
contains column names. The program will attempt to autodetect column types from
the data.
""",
    )
    parser.add_argument(
        "--url",
        help="SQLAlchemy database URL, to write to.",
        required=True,
    )
    # For testing, remember e.g.
    #       sqlite:////home/rudolf/temp.sqlite
    parser.add_argument(
        "--use_spreadsheet_names",
        action="store_true",
        help="Use spreadsheet names (where relevant) as table names, rather "
        "than filenames. (If False, only the first sheet in each spreadsheet "
        "file will be used.)",
    )
    parser.add_argument(
        "--drop_tables",
        action="store_true",
        help="Drop tables first if these exist.",
    )
    parser.add_argument(
        "--create_tables",
        action="store_true",
        help="Creates tables if these do not exist. Table creation may be "
        "IMPERFECT as it attempts to infer column types from the data.",
    )
    parser.add_argument(
        "--skip_data",
        action="store_true",
        help="Skip the data import itself.",
    )
    parser.add_argument(
        "--chunksize",
        type=int,
        default=DEFAULT_CHUNKSIZE,
        help="When inserting rows into the database, insert this many "
        "at a time. (A COMMIT is requested after each complete table.)",
    )
    parser.add_argument(
        "--skip_tables", type=str, nargs="*", help="Named tables to skip."
    )
    parser.add_argument(
        "--echo",
        action="store_true",
        help="Echo SQL. " + WARNING_VALUES_VISIBLE,
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Be verbose. " + WARNING_VALUES_VISIBLE,
    )
    parser.add_argument(
        "filename",
        type=str,
        nargs="+",
        help="Filename(s) to read. These can be tabular files (CSV, ODS, TSV, "
        "XLSX), or ZIP file(s) containing these. (Recursive ZIPs are not "
        "supported.)",
    )
    args = parser.parse_args()
    main_only_quicksetup_rootlogger(
        level=logging.DEBUG if args.verbose else logging.INFO
    )
    auto_import_db(
        url=args.url,
        filenames=args.filename,
        use_spreadsheet_names=args.use_spreadsheet_names,
        drop_tables=args.drop_tables,
        create_tables=args.create_tables,
        import_data=not args.skip_data,
        chunksize=args.chunksize,
        skip_tables=args.skip_tables,
        echo=args.echo,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
