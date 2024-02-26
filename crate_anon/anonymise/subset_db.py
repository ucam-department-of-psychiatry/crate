#!/usr/bin/env python

"""
crate_anon/anonymise/subset_db.py

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

**Create a simple subset of a database.**

"""

import argparse
from dataclasses import dataclass
import logging
from typing import Any, Generator, List, Set, Union

from cardinal_pythonlib.argparse_func import str2bool
from cardinal_pythonlib.file_io import gen_lines_without_comments
from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from sqlalchemy.engine.url import make_url

from sqlalchemy.engine import Row
from sqlalchemy.sql.expression import column, select, table
from sqlalchemy.schema import Table

from crate_anon.anonymise.dbholder import DatabaseHolder
from crate_anon.common.argparse_assist import (
    RawDescriptionArgumentDefaultsRichHelpFormatter,
)
from crate_anon.version import CRATE_VERSION_PRETTY

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

BOOLHELP = " (Specify as yes/y/true/t/1 or no/n/false/f/0.)"
INCHELP = (
    " (If 'include' tables are given, only tables explicitly named are "
    "included. If no 'include' tables are specified, all tables are included "
    "by default. Explicit excluding always overrides including.)"
)


class SubsetDefaults:
    INC_IF_FILTERCOL_NULL = False
    INC_TABLES_NO_FILTERCOL = True


# =============================================================================
# Helper functions
# =============================================================================


def to_str(x: Any) -> Union[str, None]:
    """
    Convert to a string, or None.
    """
    return None if x is None else str(x)


# =============================================================================
# Data classes
# =============================================================================


@dataclass
class DatabaseFilterSource:
    name: str
    url: str
    table: str
    column: str
    echo: bool = False

    def gen_values(self) -> Generator[str, None, None]:
        dbh = DatabaseHolder(
            name=self.name, url=self.url, with_session=True, echo=self.echo
        )
        query = select(column(self.column)).select_from(table(self.table))
        result = dbh.session.execute(query)
        for row in result:
            yield to_str(row[0])


# =============================================================================
# Config
# =============================================================================


class SubsetConfig:
    """
    Simple configuration class for subsetting databases.
    """

    def __init__(
        self,
        src_db_url: str,
        dst_db_url: str,
        filter_column: str = None,
        filter_values: List[str] = None,
        filter_value_filenames: List[str] = None,
        filter_value_db_urls: List[str] = None,
        filter_value_tablecols: List[str] = None,
        include_rows_filtercol_null: bool = (
            SubsetDefaults.INC_IF_FILTERCOL_NULL
        ),
        include_tables_without_filtercol: bool = (
            SubsetDefaults.INC_TABLES_NO_FILTERCOL
        ),
        include_tables: List[str] = None,
        include_table_filenames: List[str] = None,
        exclude_tables: List[str] = None,
        exclude_table_filenames: List[str] = None,
        echo: bool = False,
    ) -> None:
        """
        Args:
            src_db_url:
                SQLAlchemy URL for the source database.
            dst_db_url:
                SQLAlchemy URL for the destination database.
            filter_column:
                Name of column to filter on (e.g. "patient_id"). If blank,
                might copy everything.
            filter_values:
                Values, treated as strings, to accept.
            filter_value_filenames:
                Filename(s), containing values, treated as strings, to accept.
            include_rows_filtercol_null:
                Allow the filter column to be NULL as well?
            include_tables_without_filtercol:
                Include tables that don't possess the filter column (e.g.
                system/lookup tables)?
            include_tables:
                Specific named tables to include.
            include_table_filenames:
                Filename(s), containin specific named tables to include.
            exclude_tables:
                Specific named tables to exclude.
            exclude_table_filenames:
                Filename(s), containin specific named tables to exclude.
            echo:
                Echo SQL (debugging only)?
        """
        filter_values = filter_values or []
        filter_value_filenames = filter_value_filenames or []
        filter_value_db_urls = filter_value_db_urls or []
        filter_value_tablecols = filter_value_tablecols or []
        include_tables = include_tables or []
        include_table_filenames = include_table_filenames or []
        exclude_tables = exclude_tables or []
        exclude_table_filenames = exclude_table_filenames or []

        self.src_db_url = src_db_url
        self.dst_db_url = dst_db_url
        self.filter_column = filter_column
        self.include_rows_filtercol_null = include_rows_filtercol_null
        self.include_tables_without_filtercol = (
            include_tables_without_filtercol
        )
        self.echo = echo

        # Parse database filter sources
        if len(filter_value_db_urls) != len(filter_value_tablecols):
            raise ValueError(
                f"filter_value_db_urls (length {len(filter_value_db_urls)} "
                f"must be the same length as filter_value_tablecols (length "
                f"{len(filter_value_tablecols)})"
            )
        dbfilters = []  # type: List[DatabaseFilterSource]
        for i, (url, tablecol) in enumerate(
            zip(filter_value_db_urls, filter_value_tablecols), start=1
        ):
            tcvals = tablecol.split(".")
            if len(tcvals) != 2:
                raise ValueError(
                    f"Arguments to 'filter_value_tablecols' must be in the "
                    f"format 'table.column' but one is: {tablecol!r}"
                )
            dbfilters.append(
                DatabaseFilterSource(
                    name=f"filtersource_{i}",
                    url=url,
                    table=tcvals[0],
                    column=tcvals[1],
                    echo=self.echo,
                )
            )

        # Fetch filter values.
        # - No conversion to string required for command-line arguments, or
        #   file sources, which come to us as strings anyway.
        # - But conversion required for database sources, which is
        #   performed by the DatabaseFilterSource generator.
        self.filter_values = set(filter_values)  # type: Set[Union[str, None]]
        for filename in filter_value_filenames:
            self.filter_values.update(gen_lines_without_comments(filename))
        for dbfiltersource in dbfilters:
            self.filter_values.update(dbfiltersource.gen_values())
        # Permit NULL?
        if self.include_rows_filtercol_null:
            self.filter_values.add(None)

        # Fetch "include" tables:
        self.include_tables = set(include_tables)  # type: Set[str]
        for filename in include_table_filenames:
            self.include_tables.update(gen_lines_without_comments(filename))

        # Fetch "exclude" tables:
        self.exclude_tables = set(exclude_tables)  # type: Set[str]
        for filename in exclude_table_filenames:
            self.exclude_tables.update(gen_lines_without_comments(filename))

    @staticmethod
    def _safe_url(url: str) -> str:
        """
        Return a version of the SQLAlchemy URL with any password obscured.
        """
        u = make_url(url)
        return repr(u)  # obscures password

    @property
    def safe_src_db_url(self) -> str:
        """
        Password-obscured version of the source database URL.
        """
        return self._safe_url(self.src_db_url)

    @property
    def safe_dst_db_url(self) -> str:
        """
        Password-obscured version of the destination database URL.
        """
        return self._safe_url(self.dst_db_url)

    def permit_table_name(self, table_name: str) -> bool:
        """
        Should this table be permitted (judging only by its name)?
        """
        if self.include_tables:
            # "include_tables" is not empty; therefore, some tables are being
            # explicitly included. In that case, only specifically named tables
            # can be included. (If "include_tables" was empty, we'd include
            # everything by default. See command-line help.)
            if table_name not in self.include_tables:
                # Not specifically included.
                return False
        if table_name in self.exclude_tables:
            # Specifically excluded.
            return False
        # Otherwise, OK.
        return True


# =============================================================================
# Subsetter
# =============================================================================


class Subsetter:
    """
    Class to take a subset of data from one database to another.
    """

    def __init__(self, cfg: SubsetConfig) -> None:
        self.cfg = cfg
        log.info(f"Opening source database: {cfg.safe_src_db_url}")
        self.src_db = DatabaseHolder(
            name="source", url=cfg.src_db_url, with_session=True, echo=cfg.echo
        )
        self.table_names = self.src_db.table_names  # reflects
        log.info(f"Opening destination database: {cfg.safe_dst_db_url}")
        self.dst_db = DatabaseHolder(
            name="destination",
            url=cfg.dst_db_url,
            with_session=True,
            echo=cfg.echo,
        )

        # Any warnings around filters:
        if not cfg.filter_column:
            if cfg.include_tables_without_filtercol:
                log.warning(
                    "No filter column specified. Copying tables UNFILTERED."
                )
            else:
                raise ValueError(
                    "No filter column specified, and tables without a filter "
                    "column not permitted; therefore, nothing to do."
                )

        else:
            if not cfg.filter_values:
                if cfg.include_tables_without_filtercol:
                    log.warning(
                        f"No filter values. Only copying tables without the "
                        f"filter column {cfg.filter_column!r}."
                    )

    # -------------------------------------------------------------------------
    # Information about tables
    # -------------------------------------------------------------------------

    def src_sqla_table(self, table_name: str) -> Table:
        """
        Returns the SQLAlchemy Table from the source database.
        """
        metadata = self.src_db.metadata
        return metadata.tables[table_name]

    def column_names(self, table_name: str) -> List[str]:
        """
        Returns column names for a (source) table column.
        """
        t = self.src_sqla_table(table_name)
        # noinspection PyTypeChecker
        return [c.name for c in t.columns]

    def contains_filter_col(self, table_name: str) -> bool:
        """
        Does this table contain our target filter column?
        """
        return self.cfg.filter_column in self.column_names(table_name)

    def permit_table(self, table_name: str) -> bool:
        """
        Is this table name permitted to go through to the destination?
        """
        if table_name not in self.table_names:
            # log.debug(f"... {table_name}: unknown table")
            return False
        if not self.cfg.permit_table_name(table_name):
            # log.debug(f"... {table_name}: prohibited table")
            return False
        if not self.contains_filter_col(table_name):
            # log.debug(f"... {table_name}: system/lookup table")
            return self.cfg.include_tables_without_filtercol
        # log.debug(f"... {table_name}: standard permitted table")
        return True

    def dst_sqla_table(self, table_name: str) -> Table:
        """
        Returns the SQLAlchemy Table from the destination database.
        """
        metadata = self.dst_db.metadata
        return metadata.tables[table_name]

    # -------------------------------------------------------------------------
    # DDL manipulation
    # -------------------------------------------------------------------------

    def drop_dst_table_if_exists(self, table_name: str) -> None:
        """
        Drop a table on the destination side. Also remove it from the
        destination metadata, so we can recreate it (if necessary) without
        complaint.
        """
        log.debug(f"Dropping destination table: {table_name}")
        dst_metadata = self.dst_db.metadata
        t = Table(table_name, dst_metadata)
        t.drop(self.dst_db.engine, checkfirst=True)
        dst_metadata.remove(t)

    def create_dst_table(self, table_name: str) -> None:
        """
        Create a table on the destination side.
        """
        log.debug(f"Creating destination table: {table_name}")
        t = self.src_sqla_table(table_name).to_metadata(self.dst_db.metadata)
        t.create(self.dst_db.engine, checkfirst=True)

    # -------------------------------------------------------------------------
    # Filtering
    # -------------------------------------------------------------------------

    def gen_src_rows(self, table_name: str) -> Generator[Row, None, None]:
        """
        Generate unfiltered source rows from the database.
        """
        query = select(["*"]).select_from(table(table_name))
        result = self.src_db.session.execute(query)
        yield from result

    def gen_filtered_rows(self, table_name: str) -> Generator[Row, None, None]:
        """
        Generate filtered source rows from the database.
        """
        srcgen = self.gen_src_rows(table_name)
        if self.contains_filter_col(table_name):
            filtercol = self.cfg.filter_column
            filtervals = self.cfg.filter_values
            for row in srcgen:
                # String-based comparison
                if to_str(row[filtercol]) in filtervals:
                    # Row permitted
                    yield row
        else:
            # All rows permitted; go faster.
            yield from srcgen

    def subset_table(self, table_name: str) -> None:
        """
        Read rows from the source table; filter them as required; store them
        in the destination table.
        """
        n_inserted = 0
        dst_session = self.dst_db.session
        dst_table = self.dst_sqla_table(table_name)
        for row in self.gen_filtered_rows(table_name):
            dst_session.execute(dst_table.insert(values=row))
            n_inserted += 1
        log.info(f"Processing table {table_name}: inserted {n_inserted} rows")

    def commit(self) -> None:
        """
        Commit changes to the destination database.
        """
        log.debug("Committing...")
        self.dst_db.session.commit()

    def subset_db(self) -> None:
        """
        Main function -- create a subset of the source database.
        """
        log.info(f"Filtering on column: {self.cfg.filter_column}")
        for table_name in self.table_names:
            self.drop_dst_table_if_exists(table_name)
            if not self.permit_table(table_name):
                log.info(f"SKIPPING table {table_name}")
                continue
            log.info(f"Processing table {table_name}")
            self.create_dst_table(table_name)
            self.subset_table(table_name)
        self.commit()
        log.info("Done.")


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    """
    Command-line entry point.
    """
    parser = argparse.ArgumentParser(
        description=f"Create a simple subset of a database, copying one "
        f"database to another while applying filters. You can filter by a "
        f"standard column (e.g. one representing patient IDs), taking "
        f"permitted filter values from the command line, from file(s), and/or "
        f"from database(s). You can also decide which tables to "
        f"include/exclude. ({CRATE_VERSION_PRETTY})",
        formatter_class=RawDescriptionArgumentDefaultsRichHelpFormatter,
    )

    grp_src = parser.add_argument_group("SOURCE DATABASE")
    grp_src.add_argument(
        "--src_db_url", required=True, help="Source database SQLAlchemy URL"
    )

    grp_dst = parser.add_argument_group("DESTINATION DATABASE")
    grp_dst.add_argument(
        "--dst_db_url",
        required=True,
        help="Destination database SQLAlchemy URL",
    )

    grp_fr = parser.add_argument_group("ROW FILTERING")
    grp_fr.add_argument(
        "--filter_column",
        help="Column on which to filter. Typically the one that defines "
        "individuals (e.g. 'patient_research_id', 'rid', 'brcid'). If "
        "omitted, then the whole database might be copied unfiltered (if you "
        "set --include_tables_without_filtercol).",
    )
    grp_fr.add_argument(
        "--filter_values",
        nargs="*",
        help="Filter values to permit. (Comparison is performed as strings.)",
    )
    grp_fr.add_argument(
        "--filter_value_filenames",
        nargs="*",
        help="Filename(s) of files containing filter values to permit. "
        "('#' denotes comments in the file. "
        "Comparison is performed as strings.)",
    )
    grp_fr.add_argument(
        "--filter_value_db_urls",
        nargs="*",
        help="SQLAlchemy URLs of databases to pull additional filter values "
        "from. Must be in the same order as corresponding arguments to "
        "--filter_value_tablecols.",
    )
    grp_fr.add_argument(
        "--filter_value_tablecols",
        nargs="*",
        help="Table/column pairs, each expressed as 'table.column', of "
        "database columns to pull additional filter values from. Must be in "
        "the same order as corresponding arguments to "
        "--filter_value_db_urls.",
    )
    grp_fr.add_argument(
        "--include_rows_filtercol_null",
        type=str2bool,
        nargs="?",
        const=SubsetDefaults.INC_IF_FILTERCOL_NULL,
        default=SubsetDefaults.INC_IF_FILTERCOL_NULL,
        help="Include rows where the filter column is NULL. You can't "
        "otherwise specify NULL as a permitted value (at least, not from the "
        "command line or from files)." + BOOLHELP,
    )

    grp_ft = parser.add_argument_group("TABLE FILTERING")
    grp_ft.add_argument(
        "--include_tables_without_filtercol",
        type=str2bool,
        nargs="?",
        const=SubsetDefaults.INC_TABLES_NO_FILTERCOL,
        # ... if present with no parameter
        default=SubsetDefaults.INC_TABLES_NO_FILTERCOL,
        # ... if argument entirely absent
        help="Include tables that do not possess the filter column (e.g. "
        "system/lookup tables)." + BOOLHELP,
    )
    grp_ft.add_argument(
        "--include_tables",
        nargs="*",
        help="Names of tables to include." + INCHELP,
    )
    grp_ft.add_argument(
        "--include_table_filenames",
        nargs="*",
        help="Filename(s) of files containing names of tables to include."
        + INCHELP,
    )
    grp_ft.add_argument(
        "--exclude_tables",
        nargs="*",
        help="Names of tables to exclude.",
    )
    grp_ft.add_argument(
        "--exclude_table_filenames",
        nargs="*",
        help="Filename(s) of files containing names of tables to exclude.",
    )

    grp_progress = parser.add_argument_group("PROGRESS")
    grp_progress.add_argument(
        "--verbose", "-v", action="store_true", help="Be verbose"
    )
    grp_progress.add_argument(
        "--echo",
        action="store_true",
        help="Echo SQL (slow; for debugging only)",
    )

    args = parser.parse_args()

    # -------------------------------------------------------------------------
    # Verbosity, logging
    # -------------------------------------------------------------------------

    loglevel = logging.DEBUG if args.verbose else logging.INFO
    main_only_quicksetup_rootlogger(level=loglevel)

    # -------------------------------------------------------------------------
    # Onwards
    # -------------------------------------------------------------------------

    subsetcfg = SubsetConfig(
        # source
        src_db_url=args.src_db_url,
        # destination
        dst_db_url=args.dst_db_url,
        # filter
        filter_column=args.filter_column,
        filter_values=args.filter_values,
        filter_value_filenames=args.filter_value_filenames,
        filter_value_db_urls=args.filter_value_db_urls,
        filter_value_tablecols=args.filter_value_tablecols,
        include_rows_filtercol_null=args.include_rows_filtercol_null,
        include_tables_without_filtercol=args.include_tables_without_filtercol,
        include_tables=args.include_tables,
        include_table_filenames=args.include_table_filenames,
        exclude_tables=args.exclude_tables,
        exclude_table_filenames=args.exclude_table_filenames,
        # progress
        echo=args.echo,
    )
    subsetter = Subsetter(subsetcfg)
    subsetter.subset_db()


if __name__ == "__main__":
    main()
