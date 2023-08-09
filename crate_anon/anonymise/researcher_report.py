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
from typing import Any, List, Tuple

from cardinal_pythonlib.datetimefunc import (
    format_datetime,
    get_now_localtz_pendulum,
)
from cardinal_pythonlib.logs import main_only_quicksetup_rootlogger
from cardinal_pythonlib.pdf import make_pdf_on_disk_from_html
from cardinal_pythonlib.sqlalchemy.session import get_safe_url_from_engine
import django
from django.conf import settings
from django.template.loader import render_to_string
import pendulum
from rich_argparse import ArgumentDefaultsRichHelpFormatter
from sqlalchemy.orm.session import Session
from sqlalchemy.sql.expression import distinct, func, select, table
from sqlalchemy.schema import Column, ForeignKey, Table

from crate_anon.anonymise.config import Config
from crate_anon.anonymise.constants import ANON_CONFIG_ENV_VAR
from crate_anon.anonymise.ddr import DataDictionaryRow, DDRLabels
from crate_anon.version import CRATE_VERSION, CRATE_VERSION_PRETTY

log = logging.getLogger(__name__)


# =============================================================================
# Constants
# =============================================================================

DEFAULT_MAX_DISTINCT_VALUES = 20
DEFAULT_MAX_VALUE_LENGTH = 50

THIS_DIR = os.path.abspath(os.path.dirname(__file__))
TEMPLATE_DIR = os.path.join(THIS_DIR, "templates", "researcher_report")

TEMPLATE_PDF_FOOTER = "pdf_footer.html"
TEMPLATE_PDF_HEADER = "pdf_header.html"
TEMPLATE_REPORT = "report.html"
TEMPLATE_STYLE = "style.css"
TEMPLATE_TABLE = "table.html"

PRETTY_DATETIME_FORMAT = "%a %d %B %Y, %H:%M %z"
# ... e.g. Wed 24 July 2013, 20:04 +0100
DATE_FORMAT = "%Y-%m-%d"  # e.g. 2023-07-24
EN_DASH = "–"
MINUS = "−"
HYPHEN = "-"
TICK = "✓"
RIGHT_ARROW = "►"

PAPER_MARGIN = "15mm"

WKHTMLTOPDF_OPTIONS = {  # dict for pdfkit
    "page-size": "A4",
    "margin-left": PAPER_MARGIN,
    "margin-right": PAPER_MARGIN,
    "margin-top": PAPER_MARGIN,  # from paper edge down to top of content?
    "margin-bottom": PAPER_MARGIN,  # from paper edge up to bottom of content?
    "header-spacing": "3",  # mm, from content up to bottom of header
    "footer-spacing": "3",  # mm, from content down to top of footer
    # "--print-media-type": None  # https://stackoverflow.com/q/42005819
    "orientation": "Landscape",
}


# =============================================================================
# Helper classes/functions
# =============================================================================


@dataclass
class ResearcherReportOptions:
    count: bool = True  # count records in each table?
    url: bool = True  # include a sanitised URL for the database
    values: bool = True  # include specimen values/ranges
    max_distinct_values: int = DEFAULT_MAX_DISTINCT_VALUES
    max_value_length: int = DEFAULT_MAX_VALUE_LENGTH


@dataclass
class ColumnInfo:
    name: str
    sql_type: str
    pk: bool = False
    fk: list[ForeignKey] = field(default_factory=list)
    nullable: bool = True
    comment: str = ""  # database comment
    crate_annotation: str = "?"
    values_info: str = "?"

    @property
    def not_null_str(self) -> str:
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
    max_length: int = DEFAULT_MAX_VALUE_LENGTH,
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
    if isinstance(value, str):
        if len(value) > max_length:
            value = value[:max_length] + truncated_suffix
        value = value.replace("'", "''")
        return "'%s'" % value
    elif value is None:
        return "NULL"
    elif isinstance(value, (float, int)):
        return repr(value).replace(HYPHEN, MINUS)
    elif isinstance(value, decimal.Decimal):
        return str(value).replace(HYPHEN, MINUS)
    elif (
        isinstance(value, datetime.datetime)
        or isinstance(value, datetime.date)
        or isinstance(value, datetime.time)
        or isinstance(value, pendulum.DateTime)
        or isinstance(value, pendulum.Date)
        or isinstance(value, pendulum.Time)
    ):
        # All have an isoformat() method.
        return value.strftime(DATE_FORMAT)
    elif isinstance(value, bytes):
        return "<binary>"
    elif isinstance(value, datetime.timedelta):
        return str(value)
    else:
        raise NotImplementedError(
            "Don't know how to literal-quote value %r" % value
        )


def sorter(x: Any) -> Tuple[bool, Any]:
    """
    Used for sorting values that may be None/NULL.
    Remember that False < True.
    """
    return x is not None, x


# =============================================================================
# Researcher report about destination database
# =============================================================================


def get_db_name(config: Config) -> str:
    """
    Returns a short database name used for titles.

    Args:
        config:
            Anonymisation config object.
    """
    return config.destdb.name


def get_values_summary(
    session: Session,
    column: Column,
    options: ResearcherReportOptions,
    ddr: DataDictionaryRow = None,
) -> str:
    """
    Return a textual summary of values in a column (from a de-identified
    database).

    Args:
        session:
            SQLAlchemy session.
        column:
            SQLAlchemy Column object to summarize. (It knows its own Table.)
        options:
            ResearcherReportOptions object, governing the report.
        ddr:
            Corresponding CRATE DataDictionaryRow, if there is one.
    """
    if not options.values:
        # Don't show anything.
        return EN_DASH

    # Otherwise, we can always do the number of distinct values:
    items = []  # type: List[str]
    n_distinct = session.execute(
        select([func.count(distinct(column))])
    ).fetchone()[0]
    suffix = "s" if n_distinct != 1 else ""
    items.append(f"{n_distinct} distinct value{suffix}.")

    do_min_max = False
    do_distinct = False

    if ddr and (
        ddr.defines_primary_pids
        or ddr.primary_pid
        or ddr.master_pid
        or ddr.third_party_pid
        or ddr.being_scrubbed
    ):
        # More sensitive fields. Don't show these specifically.
        pass
    else:
        # Do some more.
        do_min_max = True
        if n_distinct <= options.max_distinct_values:
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
            literal(v, options.max_value_length) for v in distinct_values
        )
        items.append(f"Distinct values: [{distinct_value_str}].")

    return " ".join(items)


def mk_table_html(
    table_name: str, config: Config, options: ResearcherReportOptions
) -> str:
    """
    Returns HTML for the whole-database aspects of the report, shown at the
    start.

    Args:
        table_name:
            Table to process.
        config:
            Anonymisation config object.
        options:
            ResearcherReportOptions object, governing the report.

    Returns:
        HTML as a string.
    """
    log.info(f"Processing table: {table_name}")
    dest_ddr_rows = config.dd.get_rows_for_dest_table(table_name)
    session = config.destdb.session

    n_records = (
        session.execute(
            select([func.count()]).select_from(table(table_name))
        ).fetchone()[0]
        if options.count
        else None
    )

    t = config.destdb.metadata.tables[table_name]  # type: Table
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
            if colname == config.trid_fieldname:
                crate_annotation = DDRLabels.TRID
            elif colname == config.master_research_id_fieldname:
                crate_annotation = DDRLabels.MRID
            elif colname == config.research_id_fieldname:
                crate_annotation = DDRLabels.RID
            elif colname == config.source_hash_fieldname:
                crate_annotation = DDRLabels.SOURCE_HASH
            else:
                crate_annotation = DDRLabels.UNKNOWN
        values_info = get_values_summary(
            session=session,
            column=c,
            options=options,
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
        template(TEMPLATE_TABLE),
        dict(
            columns=columns,
            count=options.count,
            n_records=n_records,
            table_name=table_name,
            table_comment=table_comment,
            values=options.values,
        ),
    )


def mk_researcher_report_html(
    config: Config, options: ResearcherReportOptions
) -> Tuple[str, str, str]:
    """
    Produces a researcher-oriented report about a destination database, as
    HTML.

    Args:
        config:
            Anonymisation config object.
        options:
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
    db_name = get_db_name(config)
    now = format_datetime(get_now_localtz_pendulum(), PRETTY_DATETIME_FORMAT)
    title = f"{db_name}: CRATE researcher report, {now}"
    css = render_to_string(template(TEMPLATE_STYLE))
    coredict = dict(title=title, css=css, now=now)

    # -------------------------------------------------------------------------
    # 3. Read header/footer (e.g. for PDF page numbers).
    # -------------------------------------------------------------------------
    header_html = render_to_string(template(TEMPLATE_PDF_HEADER), coredict)
    footer_html = render_to_string(template(TEMPLATE_PDF_FOOTER), coredict)

    # -------------------------------------------------------------------------
    # 4. Scan the database.
    # -------------------------------------------------------------------------
    url = get_safe_url_from_engine(config.destdb.engine) if options.url else ""
    config.load_dd(check_against_source_db=False)
    config.destdb.enable_reflect()
    config.destdb.create_session()
    table_names = config.destdb.table_names  # reflects (introspects)

    # -------------------------------------------------------------------------
    # 5. Generate our main report.
    # -------------------------------------------------------------------------
    table_html_list = [
        mk_table_html(table_name, config, options)
        for table_name in table_names
    ]
    html = render_to_string(
        template(TEMPLATE_REPORT),
        dict(
            CRATE_VERSION=CRATE_VERSION,
            db_name=db_name,
            table_names=table_names,
            n_tables=len(table_names),
            tables_html="".join(table_html_list),
            url=url,
            **coredict,
        ),
    )

    # -------------------------------------------------------------------------
    # 6. Return HTML components.
    # -------------------------------------------------------------------------
    return header_html, html, footer_html


def mk_researcher_report_pdf(
    config: Config,
    output_filename: str,
    options: ResearcherReportOptions,
    debug_pdf: bool = False,
) -> bool:
    """
    Produces a researcher-oriented report about a destination database, as a
    PDF.

    Args:
        config:
            Anonymisation config object.
        output_filename:
            PDF file for output.
        options:
            ResearcherReportOptions object, governing the report.
        debug_pdf:
            Be verbose?

    Returns:
        success
    """
    header_html, html, footer_html = mk_researcher_report_html(config, options)
    log.info(f"Writing to {output_filename}")
    return make_pdf_on_disk_from_html(
        html=html,
        output_path=output_filename,
        header_html=header_html,
        footer_html=footer_html,
        wkhtmltopdf_options=WKHTMLTOPDF_OPTIONS,
        debug_options=debug_pdf,
        debug_content=debug_pdf,
        debug_wkhtmltopdf_args=debug_pdf,
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
        description="Produce a researcher-oriented PDF report about a "
        f"destination database. ({CRATE_VERSION_PRETTY}). Note: if wkhtmtopdf "
        "reports 'Too many open files', see "
        "https://stackoverflow.com/q/25355697; "
        "https://github.com/wkhtmltopdf/wkhtmltopdf/issues/3081.",
        formatter_class=ArgumentDefaultsRichHelpFormatter,
    )

    parser.add_argument("output", help="Output filename (PDF).")
    parser.add_argument(
        "--config",
        help=f"Config file (overriding environment variable "
        f"{ANON_CONFIG_ENV_VAR}).",
    )
    parser.add_argument(
        "--count",
        dest="count",
        action="store_true",
        default=True,
        help="Include record (row) counts",
    )
    parser.add_argument(
        "--nocount",
        dest="count",
        action="store_false",
        default=False,
        help="Do not include record (row) counts",
    )
    parser.add_argument(
        "--url",
        dest="url",
        action="store_true",
        default=True,
        help="Include (sanitised, password-safe) database URL",
    )
    parser.add_argument(
        "--nourl",
        dest="url",
        action="store_false",
        default=False,
        help="Do not include database URL",
    )
    parser.add_argument(
        "--values",
        dest="values",
        action="store_true",
        default=True,
        help="Include specimen values/ranges",
    )
    parser.add_argument(
        "--novalues",
        dest="values",
        action="store_false",
        default=False,
        help="Do not include specimen values/ranges",
    )
    parser.add_argument(
        "--max_distinct_values",
        type=int,
        default=DEFAULT_MAX_DISTINCT_VALUES,
        help="Maximum number of distinct values to show, where applicable.",
    )
    parser.add_argument(
        "--max_value_length",
        type=int,
        default=DEFAULT_MAX_VALUE_LENGTH,
        help="Maximum string length to show for a literal value",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Be verbose"
    )
    parser.add_argument(
        "--debug_pdf", action="store_true", help="Debug PDF creation"
    )

    args = parser.parse_args()

    options = ResearcherReportOptions(
        count=args.count,
        url=args.url,
        values=args.values,
        max_distinct_values=args.max_distinct_values,
        max_value_length=args.max_value_length,
    )

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

    mk_researcher_report_pdf(
        config=config,
        output_filename=args.output,
        options=options,
        debug_pdf=args.debug_pdf,
    )
