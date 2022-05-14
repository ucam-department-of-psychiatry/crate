#!/usr/bin/env python

"""
crate_anon/common/spreadsheet.py

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

Functions for reading/writing spreadsheets.

"""

# =============================================================================
# Imports
# =============================================================================

import csv
from enum import Enum
import logging
import os
from typing import Any, Dict, Iterable, List, Sequence, TextIO

from cardinal_pythonlib.file_io import smart_open
import openpyxl
import pyexcel_ods
import pyexcel_xlsx

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

SPREADSHEET_ROW_TYPE = Sequence[Any]
# ... a row is a sequence of cell values
SINGLE_SPREADSHEET_TYPE = Iterable[SPREADSHEET_ROW_TYPE]
# ... iterable of rows
SINGLE_SPREADSHEET_GENERATOR_TYPE = Iterable[SPREADSHEET_ROW_TYPE]
MULTIPLE_SPREADSHEET_TYPE = Dict[str, SINGLE_SPREADSHEET_TYPE]
# ... maps spreadsheet names to spreadsheets


# =============================================================================
# Enums
# =============================================================================


class SpreadsheetFileExtensions(Enum):
    CSV = ".csv"
    TSV = ".tsv"
    ODS = ".ods"
    XLSX = ".xlsx"


# =============================================================================
# Reading methods
# =============================================================================


def skip_spreadsheet_row(row: SPREADSHEET_ROW_TYPE) -> bool:
    """
    Should we skip a row, because it's empty or starts with a comment?
    """
    if not row:
        return True
    first = row[0]
    if isinstance(first, str) and first.strip().startswith("#"):
        return True
    return not any(v for v in row)


def gen_rows_from_csv(filename: str) -> SINGLE_SPREADSHEET_GENERATOR_TYPE:
    """
    Generates rows from a CSV file.
    """
    log.debug(f"Loading as CSV: {filename}")
    with open(filename, "r") as csvfile:
        reader = csv.reader(csvfile)
        for row in reader:
            if skip_spreadsheet_row(row):
                continue
            yield row


def gen_rows_from_tsv(filename: str) -> SINGLE_SPREADSHEET_GENERATOR_TYPE:
    """
    Generates rows from a TSV file.
    """
    log.debug(f"Loading as TSV: {filename}")
    with open(filename, "r") as tsvfile:
        reader = csv.reader(tsvfile, delimiter="\t")
        for row in reader:
            if skip_spreadsheet_row(row):
                continue
            yield row


def gen_rows_from_xlsx(filename: str) -> SINGLE_SPREADSHEET_GENERATOR_TYPE:
    """
    Generates rows from an XLSX file, reading the first sheet.
    """
    log.debug(f"Loading as XLSX: {filename}")
    workbook = openpyxl.load_workbook(filename)
    # ... NB potential bug using read_only; see postcodes.py
    worksheet = workbook.active  # first sheet, by default
    for sheet_row in worksheet.iter_rows():
        row = ["" if cell.value is None else cell.value for cell in sheet_row]
        if skip_spreadsheet_row(row):
            continue
        yield row


def gen_rows_from_ods(filename: str) -> SINGLE_SPREADSHEET_GENERATOR_TYPE:
    """
    Generates rows from an ODS file, reading the first sheet.
    """
    log.debug(f"Loading as ODS: {filename}")
    data = pyexcel_ods.get_data(filename)  # type: MULTIPLE_SPREADSHEET_TYPE
    # ... but it's an ordered dictionary, so:
    first_key = next(iter(data))
    first_sheet_rows = data[first_key]
    for row in first_sheet_rows:
        if skip_spreadsheet_row(row):
            continue
        yield row


def gen_rows_from_spreadsheet(
    filename: str,
) -> SINGLE_SPREADSHEET_GENERATOR_TYPE:
    """
    Generates rows from a spreadsheet-type file, autodetecting it.

    Args:
        filename:
            Filename to read.
    """
    _, ext = os.path.splitext(filename)
    if ext == SpreadsheetFileExtensions.CSV.value:
        row_gen = gen_rows_from_csv(filename)
    elif ext == SpreadsheetFileExtensions.ODS.value:
        row_gen = gen_rows_from_ods(filename)
    elif ext == SpreadsheetFileExtensions.TSV.value:
        row_gen = gen_rows_from_tsv(filename)
    elif ext == SpreadsheetFileExtensions.XLSX.value:
        row_gen = gen_rows_from_xlsx(filename)
    else:
        raise ValueError(f"Unknown spreadsheet extension: {ext!r}")
    for row in row_gen:
        yield row


# =============================================================================
# Writing methods
# =============================================================================


def make_safe_for_spreadsheet(x: Any) -> Any:
    """
    Helper function for :func:`remove_none_values_from_spreadsheet`.
    """
    return "" if x is None else x


def remove_none_values_from_spreadsheet(
    data: MULTIPLE_SPREADSHEET_TYPE,
) -> MULTIPLE_SPREADSHEET_TYPE:
    """
    The ODS writer does not cope with ``None`` values, giving:

    .. code-block::

        AttributeError: 'NoneType' object has no attribute 'split'

    Here, we transform ``None`` values to the empty string.
    """
    result = {}
    for sheetname, sheetdata in data.items():
        converted_sheetdata = []  # type: List[List[Any]]
        for row in sheetdata:
            converted_row = [make_safe_for_spreadsheet(x) for x in row]
            converted_sheetdata.append(converted_row)
        result[sheetname] = converted_sheetdata
    return result


def write_csv(filename: str, rows: SINGLE_SPREADSHEET_TYPE) -> None:
    """
    Writes to a comma-separated values (CSV) file.

    Empty (null) values are translated to "".

    Args:
        rows:
            Rows to write. (The first row is often a header row.)
        filename:
            Name of file to write.
    """
    log.info(f"Saving as CSV: {filename}")
    with smart_open(filename, "wt") as f:  # type: TextIO
        writer = csv.writer(f)
        writer.writerows(rows)


def write_tsv(filename: str, rows: SINGLE_SPREADSHEET_TYPE) -> None:
    """
    Writes to a tab-separated values (TSV) file.

    Empty (null) values are translated to "".

    Args:
        rows:
            Rows to write. (The first row is often a header row.)
        filename:
            Name of file to write.
    """
    log.info(f"Saving as TSV: {filename}")
    with smart_open(filename, "wt") as f:  # type: TextIO
        writer = csv.writer(f, delimiter="\t")
        writer.writerows(rows)


def write_ods(filename: str, data: MULTIPLE_SPREADSHEET_TYPE) -> None:
    """
    Writes to an OpenOffice spreadsheet (ODS) file.

    Args:
        data:
            See :func:`write_spreadsheet`.
        filename:
            Name of file to write.
    """
    log.info(f"Saving as ODS: {filename}")
    pyexcel_ods.save_data(filename, data)


def write_xlsx(filename: str, data: MULTIPLE_SPREADSHEET_TYPE) -> None:
    """
    Writes to an OpenOffice spreadsheet (ODS) file.

    Args:
        data:
            See :func:`write_spreadsheet`.
        filename:
            Name of file to write.
    """
    log.info(f"Saving as XLSX: {filename}")
    pyexcel_xlsx.save_data(filename, data)


def write_spreadsheet(
    filename: str, data: MULTIPLE_SPREADSHEET_TYPE, filetype: str = None
) -> None:
    """
    Writes to a spreadsheet-style file, autodetecting it.

    Args:
        filename:
            Name of file to write, or "-" for stdout (in which case the
            filetype is forced to TSV).
        data:
            A dictionary whose keys are spreadsheet names and whose
            corresponding values contain spreadsheet data. (For TSV, which is a
            single-sheet format, only the first value is used.) Each dictionary
            value is an iterable containing rows, and each row is an iterable
            of cell data items.
        filetype:
            File type as one of the string values of SpreadsheetFileExtensions;
            alternatively, use ``None`` to autodetect from the filename.
    """
    ext = filetype or os.path.splitext(filename)[1]
    if filename == "-" or ext == SpreadsheetFileExtensions.TSV.value:
        first_key = next(iter(data))
        # https://stackoverflow.com/questions/30362391/how-do-you-find-the-first-key-in-a-dictionary  # noqa
        first_sheet = data[first_key]
        write_tsv(filename, first_sheet)
    elif ext == SpreadsheetFileExtensions.CSV.value:
        first_key = next(iter(data))
        first_sheet = data[first_key]
        write_csv(filename, first_sheet)
    elif ext == SpreadsheetFileExtensions.ODS.value:
        # The ODS writer does not like None values.
        write_ods(filename, remove_none_values_from_spreadsheet(data))
    elif ext == SpreadsheetFileExtensions.XLSX.value:
        write_xlsx(filename, data)
    else:
        raise ValueError(f"Unknown spreadsheet extension: {ext!r}")
