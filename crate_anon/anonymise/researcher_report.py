#!/usr/bin/env python

"""
crate_anon/anonymise/researcher_report.py

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

**Produce a researcher-oriented report about a destination database.**

"""

import argparse
from dataclasses import dataclass, field
import datetime
import decimal
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from cardinal_pythonlib.datetimefunc import (
    format_datetime,
    get_now_localtz_pendulum,
    strfdelta,
)
from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from cardinal_pythonlib.pdf import make_pdf_on_disk_from_html
import django
from django.conf import settings
from django.template.loader import render_to_string
import pendulum
from sqlalchemy.engine.url import make_url, URL
from sqlalchemy.sql.expression import distinct, func, select, table
from sqlalchemy.schema import Column, ForeignKey, Table

from crate_anon.anonymise.config import Config
from crate_anon.anonymise.constants import ANON_CONFIG_ENV_VAR
from crate_anon.anonymise.dbholder import DatabaseHolder
from crate_anon.anonymise.ddr import DataDictionaryRow, DDRLabels
from crate_anon.common.argparse_assist import (
    RawDescriptionArgumentDefaultsRichHelpFormatter,
)
from crate_anon.version import CRATE_VERSION, CRATE_VERSION_PRETTY

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================


THIS_DIR = os.path.abspath(os.path.dirname(__file__))
TEMPLATE_DIR = os.path.join(THIS_DIR, "templates", "researcher_report")


class Templates:
    """
    Template filenames, within TEMPLATE_DIR.
    """

    PDF_FOOTER = "pdf_footer.html"
    PDF_HEADER = "pdf_header.html"
    REPORT = "report.html"
    STYLE = "style.css"
    TABLE = "table.html"


class DateFormat:
    # https://docs.python.org/3/library/datetime.html#strftime-and-strptime-format-codes  # noqa: E501
    PRETTY = "%a %d %B %Y, %H:%M %z"
    # ... e.g. Wed 24 July 2013, 20:04 +0100
    DATE = "%Y-%m-%d"  # e.g. 2023-07-24
    DATETIME = "%Y-%m-%d %H:%M"  # e.g. 2023-07-24 20:04
    TIME = "%H:%M"  # e.g. 20:04

    # And one for our custom strfdelta function:
    TIMEDELTA = "{D:02}d {H:02}h {M:02}m {S:02}s"


class Default:
    """
    Default values.
    """

    BASE_FONT_SIZE = "11pt"
    HEADER_FOOTER_SPACING_MM = 3
    # ... always in mm; https://wkhtmltopdf.org/usage/wkhtmltopdf.txt
    MAX_DISTINCT_VALUES = 20
    MAX_VALUE_LENGTH = 50
    ORIENTATION = "landscape"
    PAGE_SIZE = "A4"
    MARGIN_LEFT_RIGHT = "15mm"
    MARGIN_TOP_BOTTOM = "18mm"  # see HEADER_FOOTER_SPACING_MM


EN_DASH = "–"
MINUS = "−"
HYPHEN = "-"
TICK = "✓"
# RIGHT_ARROW = "►"


# =============================================================================
# Helper classes/functions
# =============================================================================


@dataclass
class ResearcherReportConfig:
    anonconfig: Config
    output_filename: str

    base_font_size: str = Default.BASE_FONT_SIZE
    db_name: str = None  # overrides that in config
    db_url: str = None  # overrides that in config
    debug_pdf: bool = False
    max_distinct_values: int = Default.MAX_DISTINCT_VALUES
    max_value_length: int = Default.MAX_VALUE_LENGTH
    header_footer_spacing_mm: int = Default.HEADER_FOOTER_SPACING_MM
    margin_left_right: str = Default.MARGIN_LEFT_RIGHT
    margin_top_bottom: str = Default.MARGIN_TOP_BOTTOM
    page_size: str = Default.PAGE_SIZE
    orientation: str = Default.ORIENTATION
    show_counts: bool = True  # count records in each table?
    show_url: bool = True  # include a sanitised URL for the database
    show_values: bool = True  # include specimen values/ranges

    def __post_init__(self) -> None:
        # Set up lookups.
        anonconfig = self.anonconfig
        self.annotation_from_colname = {
            anonconfig.trid_fieldname: DDRLabels.TRID,
            anonconfig.master_research_id_fieldname: DDRLabels.MRID,
            anonconfig.research_id_fieldname: DDRLabels.RID,
            anonconfig.source_hash_fieldname: DDRLabels.SOURCE_HASH,
        }

        # Set up DD
        anonconfig.load_dd(check_against_source_db=False)

        # Set up database
        if self.db_url:
            if not self.db_name:
                raise ValueError(
                    "Should specify database name if passing a custom URL"
                )
            self.db = DatabaseHolder(
                self.db_name,
                self.db_url,
                with_session=True,
                reflect=True,
            )
        else:
            # Use destination database from the config
            self.db = anonconfig.destdb
            self.db.enable_reflect()
            self.db.create_session()
            self.db_name = self.db_name or anonconfig.destdb.name
            self.db_url = self.db.engine.url
        self.db_session = self.db.session

    def safe_db_url_if_selected(self) -> str:
        """
        Sanitised version of the database URL, or a blank string if not
        enabled.
        """
        if not self.show_url:
            return ""
        url_obj = make_url(self.db_url)  # type: URL
        return repr(url_obj)
        # The default repr() implementation calls
        # self.__to_string__(hide_password=False)

    def wkhtmltopdf_options(self) -> Dict[str, Optional[str]]:
        """
        Returns wkhtmltopdf options for the current setup.
        """
        return {  # dict for pdfkit
            "page-size": self.page_size,
            "margin-left": self.margin_left_right,
            "margin-right": self.margin_left_right,
            "margin-top": self.margin_top_bottom,
            "margin-bottom": self.margin_top_bottom,
            "header-spacing": str(self.header_footer_spacing_mm),
            "footer-spacing": str(self.header_footer_spacing_mm),
            # "--print-media-type": None
            # ... https://stackoverflow.com/q/42005819
            "orientation": self.orientation,
        }

    def get_db_name(self) -> str:
        """
        Returns a short database name used for titles.
        """
        return self.db_name

    def get_db_engine_type(self) -> str:
        """
        Returns the engine type (e.g. mysql).
        """
        return self.db.engine.name

    def get_annotation_when_no_ddr_found(self, col_name: str) -> str:
        """
        Returns best-guess CRATE annotation information when no data dictionary
        row is available.

        Args:
            col_name:
                Column name.
        """
        return self.annotation_from_colname.get(col_name, DDRLabels.UNKNOWN)


@dataclass
class ColumnInfo:
    name: str
    sql_type: str
    pk: bool = False
    fk: List[ForeignKey] = field(default_factory=list)
    nullable: bool = True
    comment: str = ""  # database comment
    crate_annotation: str = "?"
    values_info: str = "?"

    @property
    def nullable_str(self) -> str:
        return TICK if self.nullable else "NOT NULL"

    @property
    def pk_str(self) -> str:
        return "PK" if self.pk else ""

    @property
    def fk_str(self) -> str:
        if self.fk:
            fk_cols = [
                f"{fk.column.table.name}.{fk.column.name}" for fk in self.fk
            ]
            return "FK to " + ", ".join(fk_cols)
        else:
            return ""


def template(filename: str) -> str:
    """
    Returns a filename from our specific template directory.
    """
    return os.path.join(TEMPLATE_DIR, filename)


def mk_comment(column: Column, ddr: DataDictionaryRow = None) -> str:
    """
    Return a comment. For databases that don't support comments, we'll want
    the CRATE DD one. For databases that do, we don't want duplication.
    """
    col_comment = column.comment or ""
    dd_comment = (ddr.comment or "") if ddr else ""
    if not col_comment and not dd_comment:
        return EN_DASH
    if dd_comment in col_comment:  # within, or equals
        return col_comment
    if col_comment in dd_comment:
        return dd_comment
    return f"[DB] {col_comment} [DD] {dd_comment}"


def literal(
    value: Any,
    max_length: int = Default.MAX_VALUE_LENGTH,
    truncated_suffix: str = "...",
) -> str:
    """
    Returns a rough-and-ready SQL literal, intended for human viewing only.
    Truncates long strings at a given length.

    - Some duplication from within
      cardinal_pythonlib.sqlalchemy.dump.get_literal_query.
    - Dates are NOT enclosed in quotes here.
    - DATETIME values are truncated to dates.
    """
    if value is None:
        return "NULL"
    elif isinstance(value, str):
        if len(value) > max_length:
            value = value[:max_length] + truncated_suffix
        value = value.replace("'", "''")  # SQL-style escaping of quotes
        return f"'{value}'"
    elif isinstance(value, (float, int)):
        return repr(value).replace(HYPHEN, MINUS)
    elif isinstance(value, decimal.Decimal):
        return str(value).replace(HYPHEN, MINUS)
    elif isinstance(value, datetime.datetime) or isinstance(
        value, pendulum.DateTime
    ):
        return value.strftime(DateFormat.DATETIME)
    elif isinstance(value, datetime.date) or isinstance(value, pendulum.Date):
        return value.strftime(DateFormat.DATE)
    elif isinstance(value, datetime.time) or isinstance(value, pendulum.Time):
        return value.strftime(DateFormat.TIME)
    elif isinstance(value, bytes):
        return f"<binary_length_{len(value)}>"
    elif isinstance(value, datetime.timedelta):
        return strfdelta(value, fmt=DateFormat.TIMEDELTA)
    else:
        raise NotImplementedError(
            f"Don't know how to represent value {value!r}"
        )


def sorter(x: Any) -> Tuple[bool, Any]:
    """
    Used for sorting values that may be None/NULL. Remember that False < True,
    so this puts None values lowest (first in a default sort).
    """
    return x is not None, x


# =============================================================================
# Researcher report about destination database
# =============================================================================


def get_values_summary(
    column: Column,
    reportcfg: ResearcherReportConfig,
    ddr: DataDictionaryRow = None,
) -> str:
    """
    Return a textual summary of values in a column (from a de-identified
    database).

    Args:
        column:
            SQLAlchemy Column object to summarize. (It knows its own Table.)
        reportcfg:
            ResearcherReportOptions object, governing the report.
        ddr:
            Corresponding CRATE DataDictionaryRow, if there is one.
    """
    if not reportcfg.show_values:
        # Don't show anything.
        return EN_DASH

    # Otherwise, we can always do the number of distinct values:
    items = []  # type: List[str]
    session = reportcfg.db_session
    n_distinct = session.execute(
        select([func.count(distinct(column))])
    ).fetchone()[0]
    suffix = "" if n_distinct == 1 else "s"  # "value" or "values"?
    items.append(f"{n_distinct} distinct value{suffix}.")

    do_min_max = False
    do_distinct = False

    if n_distinct == 0:
        # We don't need min/max/distinct if the table is empty.
        pass
    elif ddr and (
        ddr.contains_patient_info
        or ddr.contains_third_party_info
        or ddr.contains_scrub_src
        or ddr.being_scrubbed
    ):
        # More sensitive fields. Don't show these specifically.
        pass
    else:
        # Show some more detail.
        if n_distinct > 1:
            do_min_max = True
        if n_distinct <= reportcfg.max_distinct_values:
            do_distinct = True

    if do_min_max:
        min_val, max_val = session.execute(
            select([func.min(column), func.max(column)])
        ).fetchone()
        items.append(f"Min {literal(min_val)}; max {literal(max_val)}.")

    if do_distinct:
        dv_rows = session.execute(select([func.distinct(column)])).fetchall()
        # Sort before literal (so we get numeric, not string, sort):
        distinct_values = sorted((row[0] for row in dv_rows), key=sorter)
        distinct_value_str = ", ".join(
            literal(v, reportcfg.max_value_length) for v in distinct_values
        )
        items.append(f"Distinct values: {{{distinct_value_str}}}.")
        # It's a set, so use set notation.

    return " ".join(items)


def mk_table_html(table_name: str, reportcfg: ResearcherReportConfig) -> str:
    """
    Returns HTML for the per-table aspects of the report.

    Args:
        table_name:
            Table to process.
        reportcfg:
            ResearcherReportOptions object, governing the report.

    Returns:
        HTML as a string.
    """
    log.info(f"Processing table: {table_name}")
    dest_ddr_rows = reportcfg.anonconfig.dd.get_rows_for_dest_table(table_name)
    session = reportcfg.db_session

    n_records = (
        session.execute(
            select([func.count()]).select_from(table(table_name))
        ).fetchone()[0]
        if reportcfg.show_counts
        else None
    )

    t = reportcfg.db.metadata.tables[table_name]  # type: Table
    table_comment = t.comment or ""  # may be blank
    columns = []  # type: List[ColumnInfo]
    for c in sorted(t.c, key=lambda x: x.name):
        log.debug(repr(c))
        colname = c.name
        try:
            ddr = next(x for x in dest_ddr_rows if x.dest_field == colname)
            crate_annotation = ddr.report_dest_annotation()
        except StopIteration:
            ddr = None
            crate_annotation = reportcfg.get_annotation_when_no_ddr_found(
                col_name=colname
            )
        values_info = get_values_summary(
            column=c,
            reportcfg=reportcfg,
            ddr=ddr,
        )
        columns.append(
            ColumnInfo(
                name=colname,
                sql_type=str(c.type),
                pk=c.primary_key,
                nullable=c.nullable,
                fk=list(c.foreign_keys),
                comment=mk_comment(c, ddr),
                crate_annotation=crate_annotation,
                values_info=values_info,
            )
        )

    return render_to_string(
        template(Templates.TABLE),
        dict(
            columns=columns,
            n_records=n_records,
            show_counts=reportcfg.show_counts,
            show_values=reportcfg.show_values,
            table_comment=table_comment,
            table_name=table_name,
        ),
    )


def mk_researcher_report_html(
    reportcfg: ResearcherReportConfig,
) -> Tuple[str, str, str]:
    """
    Produces a researcher-oriented report about a destination database, as
    HTML.

    Args:
        reportcfg:
            ResearcherReportOptions object, governing the report.

    Returns:
        tuple: header_html, html, footer_html
    """
    # -------------------------------------------------------------------------
    # 1. Set up Django for templates.
    # -------------------------------------------------------------------------
    # https://stackoverflow.com/questions/28123603
    settings.configure(
        TEMPLATES=[
            {
                "BACKEND": "django.template.backends.django.DjangoTemplates",
                "DIRS": [TEMPLATE_DIR],
            }
        ]
    )
    django.setup()

    # -------------------------------------------------------------------------
    # 2. Core variables
    # -------------------------------------------------------------------------
    db_name = reportcfg.get_db_name()
    now = format_datetime(get_now_localtz_pendulum(), DateFormat.PRETTY)
    title = f"{db_name}: CRATE researcher report, {now}"
    css = render_to_string(
        template(Templates.STYLE),
        dict(base_font_size=reportcfg.base_font_size),
    )
    coredict = dict(title=title, css=css, now=now)

    # -------------------------------------------------------------------------
    # 3. Read header/footer (e.g. for PDF page numbers).
    # -------------------------------------------------------------------------
    header_html = render_to_string(template(Templates.PDF_HEADER), coredict)
    footer_html = render_to_string(template(Templates.PDF_FOOTER), coredict)

    # -------------------------------------------------------------------------
    # 4. Scan the database.
    # -------------------------------------------------------------------------
    table_names = sorted(reportcfg.db.table_names)  # reflects (introspects)

    # -------------------------------------------------------------------------
    # 5. Generate our main report.
    # -------------------------------------------------------------------------
    table_html_list = [
        mk_table_html(table_name, reportcfg) for table_name in table_names
    ]
    html = render_to_string(
        template(Templates.REPORT),
        dict(
            CRATE_VERSION=CRATE_VERSION,
            db_engine=reportcfg.get_db_engine_type(),
            db_name=db_name,
            n_tables=len(table_names),
            table_names=table_names,
            tables_html="".join(table_html_list),
            url=reportcfg.safe_db_url_if_selected(),
            **coredict,
        ),
    )

    # -------------------------------------------------------------------------
    # 6. Return HTML components.
    # -------------------------------------------------------------------------
    return header_html, html, footer_html


def mk_researcher_report_pdf(
    reportcfg: ResearcherReportConfig,
) -> bool:
    """
    Produces a researcher-oriented report about a destination database, as a
    PDF.

    Args:
        reportcfg:
            ResearcherReportOptions object, governing the report.

    Returns:
        success
    """
    header_html, html, footer_html = mk_researcher_report_html(reportcfg)
    log.info(f"Writing to {reportcfg.output_filename}")
    return make_pdf_on_disk_from_html(
        html=html,
        output_path=reportcfg.output_filename,
        header_html=header_html,
        footer_html=footer_html,
        wkhtmltopdf_options=reportcfg.wkhtmltopdf_options(),
        debug_options=reportcfg.debug_pdf,
        debug_content=reportcfg.debug_pdf,
        debug_wkhtmltopdf_args=reportcfg.debug_pdf,
    )


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    """
    Command-line entry point.
    """
    # noinspection PyTypeChecker
    parser = argparse.ArgumentParser(
        description=f"""
Produce a researcher-oriented PDF report about a destination database.
({CRATE_VERSION_PRETTY})

Note: if wkhtmtopdf reports 'Too many open files', see
- https://stackoverflow.com/q/25355697;
- https://github.com/wkhtmltopdf/wkhtmltopdf/issues/3081;
setting e.g. "ulimit -n 2048" is one solution.

""",
        formatter_class=RawDescriptionArgumentDefaultsRichHelpFormatter,
    )

    parser.add_argument("output", help="PDF output filename")

    grp_db = parser.add_argument_group("DATABASE")
    grp_db.add_argument(
        "--config",
        help=f"Config file, overriding environment variable "
        f"{ANON_CONFIG_ENV_VAR}",
    )
    grp_db.add_argument(
        "--db_url",
        type=str,
        default=None,
        help="Database URL, overriding that in the config file",
    )
    grp_db.add_argument(
        "--db_name",
        type=str,
        default=None,
        help="Database name, overriding that in the config file; must be "
        "specified if you use --db_url",
    )

    grp_detail = parser.add_argument_group("DETAIL")
    grp_detail.add_argument(
        "--show_url",
        dest="show_url",
        action="store_true",
        default=False,
        help="Include sanitised, password-safe version of database URL",
    )
    grp_detail.add_argument(
        "--no_show_url",
        dest="show_url",
        action="store_false",
        default=True,
        help="Do not include database URL",
    )
    grp_detail.add_argument(
        "--show_counts",
        dest="show_counts",
        action="store_true",
        default=True,
        help="Include row counts for each table",
    )
    grp_detail.add_argument(
        "--no_show_counts",
        dest="show_counts",
        action="store_false",
        default=False,
        help="Do not include row counts",
    )
    grp_detail.add_argument(
        "--show_values",
        dest="show_values",
        action="store_true",
        default=True,
        help="Include specimen values/ranges",
    )
    grp_detail.add_argument(
        "--no_show_values",
        dest="show_values",
        action="store_false",
        default=False,
        help="Do not include specimen values/ranges",
    )
    grp_detail.add_argument(
        "--max_distinct_values",
        type=int,
        default=Default.MAX_DISTINCT_VALUES,
        help="Maximum number of distinct values to show, where applicable",
    )
    grp_detail.add_argument(
        "--max_value_length",
        type=int,
        default=Default.MAX_VALUE_LENGTH,
        help="Maximum string length to show for a literal value",
    )

    grp_visuals = parser.add_argument_group("VISUALS")
    grp_visuals.add_argument(
        "--page_size",
        default=Default.PAGE_SIZE,
        help="Page size, i.e. paper type",
    )
    grp_visuals.add_argument(
        "--margin_left_right",
        default=Default.MARGIN_LEFT_RIGHT,
        help="Page left/right margins, with units",
    )
    grp_visuals.add_argument(
        "--margin_top_bottom",
        default=Default.MARGIN_TOP_BOTTOM,
        help="Page top/bottom margins for content, ignoring header/footer "
        "(see --header_footer_spacing_mm), with units",
    )
    grp_visuals.add_argument(
        "--header_footer_spacing_mm",
        type=int,
        default=Default.HEADER_FOOTER_SPACING_MM,
        help="Gap between content and header/footer, in mm",
    )
    grp_visuals.add_argument(
        "--orientation",
        choices=["portrait", "landscape"],
        default=Default.ORIENTATION,
        help="Page orientation",
    )
    grp_visuals.add_argument(
        "--base_font_size",
        default=Default.BASE_FONT_SIZE,
        help="Base font size, with units",
    )

    grp_progress = parser.add_argument_group("PROGRESS")
    grp_progress.add_argument(
        "--verbose", "-v", action="store_true", help="Be verbose"
    )
    grp_progress.add_argument(
        "--debug_pdf", action="store_true", help="Debug PDF creation"
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

    if args.config:
        os.environ[ANON_CONFIG_ENV_VAR] = args.config
    from crate_anon.anonymise.config_singleton import config  # delayed import

    reportcfg = ResearcherReportConfig(
        anonconfig=config,
        base_font_size=args.base_font_size,
        db_name=args.db_name,
        db_url=args.db_url,
        debug_pdf=args.debug_pdf,
        header_footer_spacing_mm=args.header_footer_spacing_mm,
        margin_left_right=args.margin_left_right,
        margin_top_bottom=args.margin_top_bottom,
        max_distinct_values=args.max_distinct_values,
        max_value_length=args.max_value_length,
        orientation=args.orientation,
        output_filename=args.output,
        page_size=args.page_size,
        show_counts=args.show_counts,
        show_url=args.show_url,
        show_values=args.show_values,
    )

    mk_researcher_report_pdf(reportcfg)
