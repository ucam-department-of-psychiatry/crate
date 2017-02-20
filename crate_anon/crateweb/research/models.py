#!/usr/bin/env python
# crate_anon/crateweb/research/models.py

"""
===============================================================================
    Copyright (C) 2015-2017 Rudolf Cardinal (rudolf@pobox.com).

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
"""

from collections import OrderedDict
import datetime
import io
import logging
from typing import Any, Dict, List, Iterable, Optional, Tuple, Type
import zipfile

from django.db import connections, DatabaseError, models
from django.db.models import QuerySet
from django.conf import settings
from django.http.request import HttpRequest
from openpyxl import Workbook
from openpyxl.worksheet import Worksheet

from crate_anon.common.hash import hash64
from crate_anon.common.jsonfunc import (
    JsonClassField,
    json_encode,
    METHOD_STRIP_UNDERSCORE,
    register_for_json,
)
from crate_anon.common.lang import add_info_to_exception, simple_repr
from crate_anon.common.sql import (
    ColumnId,
    columns_to_table_column_hierarchy,
    escape_percent_for_python_dbapi,
    make_grammar,
    sql_string_literal,
    TableId,
    translate_sql_qmark_to_percent,
    WhereCondition,
)
from crate_anon.common.sql_grammar import format_sql, SqlGrammar
from crate_anon.crateweb.core.dbfunc import (
    dictfetchall,
    get_fieldnames_from_cursor,
    make_tsv_row,
)
from crate_anon.crateweb.extra.excel import excel_to_bytes
from crate_anon.crateweb.research.html_functions import (
    highlight_text,
    HtmlElementCounter,
    N_CSS_HIGHLIGHT_CLASSES,
    prettify_sql_html,
)
from crate_anon.crateweb.research.research_db_info import (
    research_database_info,
)
from crate_anon.crateweb.research.sql_writer import (
    add_to_select,
    SelectElement,
)

log = logging.getLogger(__name__)


# =============================================================================
# Debugging SQL
# =============================================================================

def debug_query() -> None:
    cursor = connections['research'].cursor()
    cursor.execute("SELECT 'debug'")


# =============================================================================
# Hacking PyODBC
# =============================================================================

PYODBC_ENGINE = 'sql_server.pyodbc'


def hack_pyodbc_cursor(cursor):
    def new_fetchone(self):
        row = self.cursor.fetchone()
        if row is not None:
            row = self.format_row(row)
        # BUT DO NOT CALL self.cursor.nextset()
        return row

    cursor.fetchone = new_fetchone


# =============================================================================
# Query highlighting class
# =============================================================================

HIGHLIGHT_FWD_REF = "Highlight"


class Highlight(models.Model):
    """
    Represents the highlighting of a query.
    """
    id = models.AutoField(primary_key=True)  # automatic
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    colour = models.PositiveSmallIntegerField(verbose_name="Colour number")
    text = models.CharField(max_length=255, verbose_name="Text to highlight")
    active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return "colour={}, text={}".format(self.colour, self.text)

    def get_safe_colour(self) -> int:
        if self.colour is None:
            return 0
        return min(self.colour, N_CSS_HIGHLIGHT_CLASSES - 1)

    @staticmethod
    def as_ordered_dict(highlight_list) -> Dict[int, List[HIGHLIGHT_FWD_REF]]:
        d = dict()
        for highlight in highlight_list:
            n = highlight.get_safe_colour()
            if n not in d:
                d[n] = []  # type: List[HIGHLIGHT_FWD_REF]
            d[n].append(highlight)
        return OrderedDict(sorted(d.items()))

    @staticmethod
    def get_active_highlights(request: HttpRequest) -> QuerySet:
        return Highlight.objects.filter(user=request.user, active=True)

    def activate(self) -> None:
        self.active = True
        self.save()

    def deactivate(self) -> None:
        self.active = False
        self.save()


# =============================================================================
# Query class
# =============================================================================

QUERY_FWD_REF = "Query"


class Query(models.Model):
    """
    Class to query the research database.
    """
    class Meta:
        app_label = "research"

    id = models.AutoField(primary_key=True)  # automatic
    user = models.ForeignKey(settings.AUTH_USER_MODEL)

    sql = models.TextField(verbose_name='SQL query')
    sql_hash = models.BigIntegerField(
        verbose_name='64-bit non-cryptographic hash of SQL query')
    args = JsonClassField(verbose_name='SQL arguments (as JSON)', null=True)
    # ... https://github.com/shrubberysoft/django-picklefield
    raw = models.BooleanField(
        default=False, verbose_name='SQL is raw, not parameter-substituted')
    qmark = models.BooleanField(
        default=True,
        verbose_name='Parameter-substituted SQL uses ?, not %s, '
        'as placeholders')
    active = models.BooleanField(default=True)  # see save() below
    created = models.DateTimeField(auto_now_add=True)
    deleted = models.BooleanField(
        default=False,
        verbose_name="Deleted from the user's perspective. "
                     "Audited queries are never properly deleted.")
    audited = models.BooleanField(default=False)

    def __repr__(self) -> str:
        return simple_repr(self, ['id', 'user', 'sql', 'args', 'raw', 'qmark',
                                  'active', 'created', 'deleted', 'audited'])

    def save(self, *args, **kwargs) -> None:
        """
        Custom save method.
        Ensures that only one Query has active == True for a given user.
        Also sets the hash.
        """
        # http://stackoverflow.com/questions/1455126/unique-booleanfield-value-in-django  # noqa
        if self.active:
            Query.objects.filter(user=self.user, active=True)\
                         .update(active=False)
        self.sql_hash = hash64(self.sql)
        super().save(*args, **kwargs)

    # -------------------------------------------------------------------------
    # Fetching
    # -------------------------------------------------------------------------

    @staticmethod
    def get_active_query_or_none(request: HttpRequest) \
            -> Optional[QUERY_FWD_REF]:
        if not request.user.is_authenticated():
            return None
        try:
            return Query.objects.get(user=request.user, active=True)
        except Query.DoesNotExist:
            return None

    @staticmethod
    def get_active_query_id_or_none(request: HttpRequest) -> Optional[int]:
        if not request.user.is_authenticated():
            return None
        try:
            query = Query.objects.get(user=request.user, active=True)
            return query.id
        except Query.DoesNotExist:
            return None

    # -------------------------------------------------------------------------
    # Activating, deleting, auditing
    # -------------------------------------------------------------------------

    def activate(self) -> None:
        self.active = True
        self.save()

    def mark_audited(self) -> None:
        if self.audited:
            return
        self.audited = True
        self.save()

    def mark_deleted(self) -> None:
        if self.deleted:
            # log.debug("pointless")
            return
        self.deleted = True
        self.active = False
        # log.debug("about to save")
        self.save()
        # log.debug("saved")

    def delete_if_permitted(self) -> None:
        """If a query has been audited, it isn't properly deleted."""
        if self.deleted:
            log.debug("already flagged as deleted")
            return
        if self.audited:
            log.debug("marking as deleted")
            self.mark_deleted()
        else:
            # actually delete
            log.debug("actually deleting")
            self.delete()

    def audit(self, count_only: bool = False, n_records: int = 0,
              failed: bool = False, fail_msg: str = "") -> None:
        a = QueryAudit(query=self,
                       count_only=count_only,
                       n_records=n_records,
                       failed=failed,
                       fail_msg=fail_msg)
        a.save()
        self.mark_audited()

    # -------------------------------------------------------------------------
    # Highlights
    # -------------------------------------------------------------------------

    def add_highlight(self, text: str, colour: int = 0) -> None:
        h = Highlight(text=text, colour=colour)
        self.highlight_set.add(h)

    def get_highlights_as_dict(self) -> Dict[int, Iterable[Highlight]]:
        d = OrderedDict()
        for n in range(N_CSS_HIGHLIGHT_CLASSES):
            d[n] = Highlight.objects.filter(query_id=self.id, colour=n)
        return d

    def get_highlight_descriptions(self) -> List[str]:
        d = self.get_highlights_as_dict()
        desc = []
        for n in range(N_CSS_HIGHLIGHT_CLASSES):
            if d[n]:
                # noinspection PyTypeChecker
                desc.append(", ".join(highlight_text(h.text, n) for h in d[n]))
        return desc

    # -------------------------------------------------------------------------
    # SQL queries
    # -------------------------------------------------------------------------

    def get_original_sql(self) -> str:
        # noinspection PyTypeChecker
        return self.sql

    def get_sql_args_for_django(self) -> Tuple[str, Optional[List[Any]]]:
        """
        Get sql/args in a format suitable for Django, with %s placeholders,
        or as escaped raw SQL.
        """
        if self.raw:
            # noinspection PyTypeChecker
            sql = escape_percent_for_python_dbapi(self.sql)
            args = None
        else:
            if self.qmark:
                # noinspection PyTypeChecker
                sql = translate_sql_qmark_to_percent(self.sql)
            else:
                sql = self.sql
            args = self.args
        return sql, args

    def get_executed_cursor(self, sql_append_raw: str = None,
                            hack_pyodbc: bool = True) -> Any:
        """
        Get cursor with a query executed
        """
        (sql, args) = self.get_sql_args_for_django()
        if sql_append_raw:
            sql += sql_append_raw
        cursor = connections['research'].cursor()
        if (hack_pyodbc and
                settings.DATABASES['research']['engine'] == PYODBC_ENGINE):
            hack_pyodbc_cursor(cursor)
        try:
            if args:
                cursor.execute(sql, args)
            else:
                cursor.execute(sql)
        except DatabaseError as exception:
            add_info_to_exception(exception, {'sql': sql, 'args': args})
            raise
        return cursor

    # def gen_rows(self,
    #              firstrow: int = 0,
    #              lastrow: int = None) -> Generator[List[Any], None, None]:
    #     """
    #     Generate rows from the query.
    #     """
    #     if firstrow > 0 or lastrow is not None:
    #         sql_append_raw = " LIMIT {f},{n}".format(
    #             f=firstrow,
    #             n=(lastrow - firstrow + 1),
    #         )
    #         # zero-indexed;
    #         # http://dev.mysql.com/doc/refman/5.0/en/select.html
    #     else:
    #         sql_append_raw = None
    #     with self.get_executed_cursor(sql_append_raw) as cursor:
    #         row = cursor.fetchone()
    #         while row is not None:
    #             yield row
    #             row = cursor.fetchone()

    def make_tsv(self) -> str:
        with self.get_executed_cursor() as cursor:
            fieldnames = get_fieldnames_from_cursor(cursor)
            tsv = make_tsv_row(fieldnames)
            row = cursor.fetchone()
            while row is not None:
                tsv += make_tsv_row(row)
                row = cursor.fetchone()
        return tsv

    def make_excel(self) -> bytes:
        wb = Workbook()
        wb.remove_sheet(wb.active)  # remove the autocreated blank sheet
        sheetname = "query_{}".format(self.id)
        ws = wb.create_sheet(sheetname)
        now = datetime.datetime.now()
        with self.get_executed_cursor() as cursor:
            fieldnames = get_fieldnames_from_cursor(cursor)
            ws.append(fieldnames)
            row = cursor.fetchone()
            while row is not None:
                ws.append(tuple(row))
                # - openpyxl doesn't believe in duck-typing; see
                #   openpyxl/worksheet/worksheet.py
                # - Sometimes this works (e.g. from MySQL), but sometimes it
                #   fails, e.g. when the row is of type pyodbc.Row
                # - So we must coerce to list or tuple
                row = cursor.fetchone()
                # BUG in django-pyodbc-azure==1.10.4.0 (providing
                # sql_server/*), 2017-02-17: this causes
                # ProgrammingError "No results. Previous SQL was not a query."
                # The problem relates to sql_server/pyodbc/base.py
                # CursorWrapper.fetchone() calling self.cursor.nextset(); if
                # you comment this out, it works fine.
                # Related:
                # - https://github.com/pymssql/pymssql/issues/98

        sql_ws = wb.create_sheet(title="SQL")
        sql_ws.append(["SQL", "Executed_at"])
        sql_ws.append([self.get_original_sql(), now])
        return excel_to_bytes(wb)

    def dictfetchall(self) -> List[Dict[str, Any]]:
        """Generates all results as a list of OrderedDicts."""
        with self.get_executed_cursor() as cursor:
            return dictfetchall(cursor)


# =============================================================================
# Query auditing class
# =============================================================================

class QueryAudit(models.Model):
    """
    Audit log for a query.
    """
    id = models.AutoField(primary_key=True)  # automatic
    query = models.ForeignKey('Query')
    when = models.DateTimeField(auto_now_add=True)
    count_only = models.BooleanField(default=False)
    n_records = models.IntegerField(default=0)
    # ... not PositiveIntegerField; SQL Server gives -1, for example
    failed = models.BooleanField(default=False)
    fail_msg = models.TextField()

    def __str__(self):
        return "<QueryAudit id={}>".format(self.id)


# =============================================================================
# Lookup class for secret RID-to-PID conversion
# =============================================================================

class PidLookupRouter(object):
    # https://docs.djangoproject.com/en/1.8/topics/db/multi-db/
    # https://newcircle.com/s/post/1242/django_multiple_database_support
    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    def db_for_read(self, model: Type[models.Model], **hints) -> Optional[str]:
        """
        read model PidLookup -> look at database secret
        """
        # log.debug("PidLookupRouter: {}".format(model._meta.model_name))
        # if model._meta.model_name == PidLookup._meta.model_name:
        if model == PidLookup:
            return 'secret'
        return None

    # noinspection PyUnusedLocal
    @staticmethod
    def allow_migrate(db, app_label, model_name=None, **hints):
        # 2017-02-12, to address bug:
        # - https://code.djangoproject.com/ticket/27054
        # See also:
        # - https://docs.djangoproject.com/en/1.10/topics/db/multi-db/#using-other-management-commands  # noqa
        return db == 'default'


class PidLookup(models.Model):
    """
    Lookup class for secret RID-to-PID conversion.
    Uses the 'secret' database connection.

    Use as e.g. Lookup(pid=XXX)
    """
    pid = models.PositiveIntegerField(
        primary_key=True,
        db_column=settings.SECRET_MAP['PID_FIELD'])
    mpid = models.PositiveIntegerField(
        db_column=settings.SECRET_MAP['MASTER_PID_FIELD'])
    rid = models.CharField(
        db_column=settings.SECRET_MAP['RID_FIELD'],
        max_length=settings.SECRET_MAP['MAX_RID_LENGTH'])
    mrid = models.CharField(
        db_column=settings.SECRET_MAP['MASTER_RID_FIELD'],
        max_length=settings.SECRET_MAP['MAX_RID_LENGTH'])
    trid = models.PositiveIntegerField(
        db_column=settings.SECRET_MAP['TRID_FIELD'])

    class Meta:
        managed = False
        db_table = settings.SECRET_MAP['TABLENAME']


def get_pid_lookup(trid: int = None,
                   rid: str = None,
                   mrid: str = None) -> PidLookup:
    if trid is not None:
        lookup = PidLookup.objects.get(trid=trid)
    elif rid is not None:
        lookup = PidLookup.objects.get(rid=rid)
    elif mrid is not None:
        lookup = PidLookup.objects.get(mrid=mrid)
    else:
        raise ValueError("no input")
    return lookup


def get_mpid(trid: int = None,
             rid: str = None,
             mrid: str = None) -> int:
    lookup = get_pid_lookup(trid=trid, rid=rid, mrid=mrid)
    # noinspection PyTypeChecker
    return lookup.mpid


def get_pid(trid: int = None,
            rid: str = None,
            mrid: str = None) -> int:
    lookup = get_pid_lookup(trid=trid, rid=rid, mrid=mrid)
    # noinspection PyTypeChecker
    return lookup.pid


# =============================================================================
# Patient Explorer multi-query class
# =============================================================================

"""

1. Patient ID query

- Single database is easy; we can use RID or TRID, and therefore TRID for
  performance.
  Note that UNION gives only DISTINCT results by default ("UNION ALL" gives
  everything).
  ... http://stackoverflow.com/questions/49925/what-is-the-difference-between-union-and-union-all

    -- Clear, but extensibility of boolean logic less clear:
    SELECT trid
        FROM diagnosis_table
        WHERE diagnosis LIKE 'F20%'
    INTERSECT
    SELECT trid
        FROM progress_note_table
        WHERE note LIKE '%schizophreni%' OR note LIKE '%depression%'
    ORDER BY trid
    ... logic across tables requires careful arrangement of UNION vs. INTERSECT
    ... logic for multiple fields within one table can be done with AND/OR

    -- Slower (?), but simpler to manipulate logic?
    SELECT DISTINCT something.trid
    FROM diagnosis_table INNER JOIN progress_note_table
    ON diagnosis_table.trid = progress_note_table.trid
    WHERE
        diagnosis_table.diagnosis LIKE 'F20%'
        AND (progress_note_table.note LIKE '%schizophreni%'
             OR progress_note_table.notenote LIKE '%depression%')
    ORDER BY something.trid
    -- ... boolean logic can all be encapsulated in a single WHERE clause
    -- ... can also share existing join code
    -- ... ?reasonable speed since the TRID fields will be indexed
    -- ... preferable.

1b. Which ID for the patient ID query

    ... the TRID (for speed, inc. sorting) of the first database
    ... can use the TRID from the first "where clause" table
        (don't have to join to a master patient table)
    ... join everything across databases as before

2. Results queries

    -- Something like:

    SELECT rid, date_of_note, note
    FROM progress_note_table
    WHERE trid IN ( ... patient_id_query ... )
    ORDER BY trid

    SELECT rid, date_of_diagnosis, diagnosis, diagnosis_description
    FROM diagnosis_table
    WHERE trid IN ( ... patient_id_query ... )
    ORDER BY trid


This means we will repeat the patient_id_query, which may be inefficient.
Options:
- store the TRIDs in Python, then pass them as arguments
  ... at which point the SQL string/packet length becomes relevant;
  ... http://stackoverflow.com/questions/1869753/maximum-size-for-a-sql-server-query-in-clause-is-there-a-better-approach
  ... http://stackoverflow.com/questions/16335011/what-is-maximum-query-size-for-mysql
  ... http://stackoverflow.com/questions/96553/practical-limit-to-length-of-sql-query-specifically-mysql
- let the database worry about it
  ... probably best for now!


3. Display

    One patient per page, with multiple results tables.

===========

- Boolean logic on patient selection
    ... within


"""  # noqa


# =============================================================================
# PatientMultiQuery
# =============================================================================

@register_for_json(method=METHOD_STRIP_UNDERSCORE)
class PatientMultiQuery(object):
    def __init__(self,
                 output_columns: List[ColumnId] = None,
                 patient_conditions: List[WhereCondition] = None,
                 manual_patient_id_query: str = ''):
        self._output_columns = output_columns or []  # type: List[ColumnId]
        self._patient_conditions = patient_conditions or []  # type: List[WhereCondition]  # noqa
        self._manual_patient_id_query = manual_patient_id_query or ''

    def __repr__(self) -> str:
        return (
            "<{qualname}("
            "output_columns={output_columns}, "
            "patient_conditions={patient_conditions}, "
            "manual_patient_id_query={manual_patient_id_query}"
            ") at {addr}>".format(
                qualname=self.__class__.__qualname__,
                output_columns=repr(self._output_columns),
                patient_conditions=repr(self._patient_conditions),
                manual_patient_id_query=repr(self._manual_patient_id_query),
                addr=hex(id(self)),
            )
        )

    def __eq__(self, other: 'PatientMultiQuery') -> bool:
        return (
            self._output_columns == other._output_columns and
            self._patient_conditions == other._patient_conditions and
            self._manual_patient_id_query == other._manual_patient_id_query
        )

    def __hash__(self) -> int:
        """
        WARNING: Python's hash() function converts the result of __hash__()
        to the integer width of the host machine, so 64-bit results can get
        down-converted to 32 bits. Use hash64() directly if you want a 64-bit
        result.
        """
        return self.hash64()

    def hash64(self) -> int:
        return hash64(json_encode(self))

    def get_output_columns(self) -> List[ColumnId]:
        return self._output_columns

    def has_output_columns(self) -> bool:
        return bool(self._output_columns)

    def ok_to_run(self) -> bool:
        return self.has_output_columns() and self.has_patient_id_query()

    def get_patient_conditions(self) -> List[WhereCondition]:
        return self._patient_conditions

    def get_manual_patient_id_query(self) -> str:
        return self._manual_patient_id_query

    def add_output_column(self, column_id: ColumnId) -> None:
        if column_id not in self._output_columns:
            self._output_columns.append(column_id)
            self._output_columns.sort()

    def clear_output_columns(self) -> None:
        self._output_columns = []

    def add_patient_condition(self, where: WhereCondition) -> None:
        if where not in self._patient_conditions:
            self._patient_conditions.append(where)
            self._patient_conditions.sort()

    def clear_patient_conditions(self) -> None:
        self._patient_conditions = []

    def set_override_query(self, query: str) -> None:
        self._manual_patient_id_query = query

    def _get_select_mrid_column(self) -> Optional[ColumnId]:
        if not self._patient_conditions:
            return None
        return research_database_info.get_linked_mrid_column(
            self._patient_conditions[0].table_id())

    def has_patient_id_query(self) -> bool:
        if self._manual_patient_id_query:
            return True
        if self._patient_conditions:
            mrid_col = self._get_select_mrid_column()
            if mrid_col and mrid_col.is_valid():
                return True
        return False

    def patient_id_query(self, with_order_by: bool = True) -> str:
        # Returns an SQL SELECT statement based on the list of WHERE conditions
        # already stored, joined with AND by default.

        if self._manual_patient_id_query:
            # User has specified one manually.
            return self._manual_patient_id_query

        if not self._patient_conditions:
            return ''

        grammar = research_database_info.grammar
        select_mrid_column = self._get_select_mrid_column()
        if not select_mrid_column.is_valid():
            log.warning(
                "PatientMultiQuery.patient_id_query(): invalid "
                "select_mrid_column: {}".format(repr(select_mrid_column)))
            # One way this can happen: (1) a user saves a PMQ; (2) the
            # administrator removes one of the databases!
            return ''
        mrid_alias = "_mrid"
        sql = add_to_select(
            '',
            grammar=grammar,
            select_elements=[SelectElement(column_id=select_mrid_column,
                                           alias=mrid_alias)],
            distinct=True,
            where_conditions=self._patient_conditions,
            where_type="AND",
            magic_join=True,
            formatted=True
        )
        if with_order_by:
            sql += " ORDER BY " + mrid_alias
            # ... ORDER BY is important for consistency across runs
        # log.critical(sql)
        return sql

    def all_full_queries(self) -> List[Tuple[TableId, str, List[Any]]]:
        return self.all_queries(mrids=None)

    def all_queries_specific_patients(
            self,
            mrids: List[int]) -> List[Tuple[TableId, str, List[Any]]]:
        return self.all_queries(mrids=mrids)

    def all_queries(self,
                    mrids: List[Any] = None) -> List[Tuple[TableId, str,
                                                           List[Any]]]:
        queries = []
        table_columns_map = columns_to_table_column_hierarchy(
            self._output_columns, sort=True)
        for table, columns in table_columns_map:
            table_sql_args = self.make_query(table_id=table,
                                             columns=columns,
                                             mrids=mrids)
            queries.append(table_sql_args)
        return queries

    def where_patient_clause(self, table_id: TableId,
                             grammar: SqlGrammar,
                             mrids: List[Any] = None) -> Tuple[str, List[Any]]:
        """Returns (sql, args)."""
        mrid_column = research_database_info.get_mrid_column_from_table(
            table_id)
        if mrids:
            in_clause = ",".join(["?"] * len(mrids))
            # ... see notes for translate_sql_qmark_to_percent()
            args = mrids
        else:
            # If we haven't specified specific patients, use our patient-
            # finding query.
            in_clause = self.patient_id_query(with_order_by=False)
            # ... SQL Server moans if you use use ORDER BY in a subquery:
            # "The ORDER BY clause is invalid in views, inline functions,
            # derived tables, subqueries, ... unless TOP, OFFSET or FOR XML
            # is specified."
            args = []
        sql = "{mrid} IN ({in_clause})".format(
            mrid=mrid_column.identifier(grammar),
            in_clause=in_clause)
        return sql, args

    def make_query(self,
                   table_id: TableId,
                   columns: List[ColumnId],
                   mrids: List[Any] = None) -> Tuple[TableId, str, List[Any]]:
        if not columns:
            raise ValueError("No columns specified")
        grammar = research_database_info.grammar
        mrid_column = research_database_info.get_mrid_column_from_table(
            table_id)
        all_columns = [mrid_column]
        for c in columns:
            if c not in all_columns:
                all_columns.append(c)
        where_clause, args = self.where_patient_clause(table_id, grammar,
                                                       mrids)
        select_elements = [SelectElement(column_id=col)
                           for col in all_columns]
        where_conditions = [WhereCondition(raw_sql=where_clause)]
        sql = add_to_select('',
                            grammar=grammar,
                            select_elements=select_elements,
                            where_conditions=where_conditions,
                            magic_join=True,
                            formatted=True)
        return table_id, sql, args

    # -------------------------------------------------------------------------
    # Display
    # -------------------------------------------------------------------------

    def output_cols_html(self) -> str:
        grammar = research_database_info.grammar
        return prettify_sql_html("\n".join(
            [column_id.identifier(grammar)
             for column_id in self.get_output_columns()]))

    def pt_conditions_html(self) -> str:
        grammar = research_database_info.grammar
        return prettify_sql_html("\nAND ".join([
            wc.sql(grammar) for wc in self.get_patient_conditions()]))

    def summary_html(self, element_counter: HtmlElementCounter) -> str:
        def collapser(x: str) -> str:
            return element_counter.overflow_div(contents=x)
        outcols = self.output_cols_html()
        manual_query = self.get_manual_patient_id_query()
        if manual_query:
            manual_or_auto = " (MANUAL)"
            ptselect = prettify_sql_html(manual_query)
        else:
            manual_or_auto = ""
            ptselect = self.pt_conditions_html()
        return """
            Output columns:<br>
            {outcols}
            Patient selection:<br>
            {ptselect}
        """.format(
            outcols=collapser(outcols),
            manual_or_auto=manual_or_auto,
            ptselect=collapser(ptselect),
        )

    # -------------------------------------------------------------------------
    # Data finder: COUNT(*) for all patient tables
    # -------------------------------------------------------------------------

    def data_finder_query(self,
                          mrids: List[Any] = None) -> Tuple[str, List[Any]]:
        """
        Returns (sql, args).
        When executed, query gives:
            research_id, table_name, n_records, min_date, max_date
        """
        grammar = research_database_info.grammar
        queries = []
        args = []
        mrid_alias = 'master_research_id'
        table_name_alias = 'table_name'
        n_records_alias = 'n_records'
        min_date_alias = 'min_date'
        max_date_alias = 'max_date'
        for table_id in research_database_info.get_mrid_linkable_patient_tables():  # noqa
            mrid_col = research_database_info.get_mrid_column_from_table(
                table=table_id)
            date_col = research_database_info.get_default_date_column(
                table=table_id)
            if research_database_info.table_contains(table_id, date_col):
                min_date = "MIN({})".format(date_col.identifier(grammar))
                max_date = "MAX({})".format(date_col.identifier(grammar))
            else:
                min_date = "NULL"
                max_date = "NULL"
                # ... OK (at least in MySQL) to do:
                # SELECT col1, COUNT(*), NULL FROM table GROUP BY col1;
            where_clause, new_args = self.where_patient_clause(
                table_id, grammar, mrids)
            args += new_args
            table_identifier = table_id.identifier(grammar)
            select_elements = [
                SelectElement(column_id=mrid_col, alias=mrid_alias),
                SelectElement(raw_select=sql_string_literal(table_identifier),
                              alias='table_name'),
                SelectElement(raw_select='COUNT(*)',
                              from_table_for_raw_select=table_id,
                              alias=n_records_alias),
                SelectElement(raw_select=min_date,
                              from_table_for_raw_select=table_id,
                              alias=min_date_alias),
                SelectElement(raw_select=max_date,
                              from_table_for_raw_select=table_id,
                              alias=max_date_alias),
            ]
            where_conditions = [WhereCondition(raw_sql=where_clause)]
            query = add_to_select('',
                                  grammar=grammar,
                                  select_elements=select_elements,
                                  where_conditions=where_conditions,
                                  magic_join=True,
                                  formatted=False)
            query += " GROUP BY " + mrid_col.identifier(grammar)
            queries.append(query)
        sql = (
            "\nUNION\n".join(queries) +
            "\nORDER BY {mrid_alias}, {table_name_alias}".format(
                mrid_alias=mrid_alias,
                table_name_alias=table_name_alias,
            )
        )
        sql = format_sql(sql)
        return sql, args

    # -------------------------------------------------------------------------
    # Monster data: SELECT * for all patient tables
    # -------------------------------------------------------------------------

    def monster_queries(self,
                        mrids: List[int] = None) -> List[Tuple[TableId, str,
                                                               List[Any]]]:
        grammar = research_database_info.grammar
        table_sql_args_tuples = []
        for table_id in research_database_info.get_mrid_linkable_patient_tables():  # noqa
            mrid_col = research_database_info.get_mrid_column_from_table(
                table=table_id)
            where_clause, args = self.where_patient_clause(
                table_id, grammar, mrids)
            # We add the WHERE using our magic query machine, to get the joins
            # right:
            select_elements = [
                SelectElement(raw_select='*',
                              from_table_for_raw_select=table_id),
            ]
            where_conditions = [
                WhereCondition(raw_sql=where_clause,
                               from_table_for_raw_sql=mrid_col.table_id()),
            ]
            sql = add_to_select(
                '',
                grammar=grammar,
                select_elements=select_elements,
                where_conditions=where_conditions,
                magic_join=True,
                formatted=False)
            sql += " ORDER BY " + mrid_col.identifier(grammar)
            sql = format_sql(sql)
            table_sql_args_tuples.append((table_id, sql, args))
        return table_sql_args_tuples


# =============================================================================
# PatientExplorer
# =============================================================================

PATIENT_EXPLORER_FWD_REF = "PatientExplorer"


class PatientExplorer(models.Model):
    """
    Class to explore the research database on a per-patient basis.
    """
    class Meta:
        app_label = "research"

    id = models.AutoField(primary_key=True)  # automatic
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    patient_multiquery = JsonClassField(
        verbose_name='PatientMultiQuery as JSON',
        null=True)  # type: PatientMultiQuery
    pmq_hash = models.BigIntegerField(
        verbose_name='64-bit non-cryptographic hash of JSON of '
                     'patient_multiquery')
    active = models.BooleanField(default=True)  # see save() below
    created = models.DateTimeField(auto_now_add=True)
    deleted = models.BooleanField(
        default=False,
        verbose_name="Deleted from the user's perspective. "
                     "Audited queries are never properly deleted.")
    audited = models.BooleanField(default=False)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        if not self.patient_multiquery:
            self.patient_multiquery = PatientMultiQuery()

    def __str__(self) -> str:
        return "<PatientExplorer id={}>".format(self.id)

    def save(self, *args, **kwargs) -> None:
        """
        Custom save method. Ensures that only one PatientExplorer has
        active == True for a given user.
        Also sets the hash.
        """
        if self.active:
            PatientExplorer.objects\
                .filter(user=self.user, active=True)\
                .update(active=False)
        self.pmq_hash = self.patient_multiquery.hash64()
        # Beware: Python's hash() function will downconvert to 32 bits on 32-bit
        # machines; use pmq.hash64() directly, not hash(pmq).
        super().save(*args, **kwargs)

    # -------------------------------------------------------------------------
    # Fetching
    # -------------------------------------------------------------------------

    @staticmethod
    def get_active_pe_or_none(request: HttpRequest) \
            -> Optional[PATIENT_EXPLORER_FWD_REF]:
        if not request.user.is_authenticated():
            return None
        try:
            return PatientExplorer.objects.get(user=request.user, active=True)
        except PatientExplorer.DoesNotExist:
            return None

    @staticmethod
    def get_active_pe_id_or_none(request: HttpRequest) -> Optional[int]:
        if not request.user.is_authenticated():
            return None
        try:
            pe = PatientExplorer.objects.get(user=request.user, active=True)
            return pe.id
        except PatientExplorer.DoesNotExist:
            return None

    # -------------------------------------------------------------------------
    # Activating, deleting, auditing
    # -------------------------------------------------------------------------

    def activate(self) -> None:
        self.active = True
        self.save()

    def mark_audited(self) -> None:
        if self.audited:
            return
        self.audited = True
        self.save()

    def mark_deleted(self) -> None:
        if self.deleted:
            # log.debug("pointless")
            return
        self.deleted = True
        self.active = False
        # log.debug("about to save")
        self.save()
        # log.debug("saved")

    def delete_if_permitted(self) -> None:
        """If a PE has been audited, it isn't properly deleted."""
        if self.deleted:
            log.debug("already flagged as deleted")
            return
        if self.audited:
            log.debug("marking as deleted")
            self.mark_deleted()
        else:
            # actually delete
            log.debug("actually deleting")
            self.delete()

    def audit(self, count_only: bool = False, n_records: int = 0,
              failed: bool = False, fail_msg: str = "") -> None:
        a = PatientExplorerAudit(patient_explorer=self,
                                 count_only=count_only,
                                 n_records=n_records,
                                 failed=failed,
                                 fail_msg=fail_msg)
        a.save()
        self.mark_audited()

    # -------------------------------------------------------------------------
    # Highlights
    # -------------------------------------------------------------------------

    def add_highlight(self, text: str, colour: int = 0) -> None:
        h = Highlight(text=text, colour=colour)
        self.highlight_set.add(h)

    def get_highlights_as_dict(self) -> Dict[int, Iterable[Highlight]]:
        d = OrderedDict()
        for n in range(N_CSS_HIGHLIGHT_CLASSES):
            d[n] = Highlight.objects.filter(query_id=self.id, colour=n)
        return d

    def get_highlight_descriptions(self) -> List[str]:
        d = self.get_highlights_as_dict()
        desc = []
        for n in range(N_CSS_HIGHLIGHT_CLASSES):
            if d[n]:
                # noinspection PyTypeChecker
                desc.append(", ".join(highlight_text(h.text, n) for h in d[n]))
        return desc

    # -------------------------------------------------------------------------
    # Using the internal PatientMultiQuery
    # -------------------------------------------------------------------------

    def all_queries(self,
                    mrids: List[Any] = None) -> List[Tuple[TableId, str,
                                                           List[Any]]]:
        return self.patient_multiquery.all_queries(mrids=mrids)

    @staticmethod
    def get_executed_cursor(sql: str, args: List[Any] = None,
                            hack_pyodbc: bool = True) -> Any:
        """
        Get cursor with a query executed
        """
        sql = translate_sql_qmark_to_percent(sql)
        args = args or []
        cursor = connections['research'].cursor()
        if (hack_pyodbc and
                settings.DATABASES['research']['engine'] == PYODBC_ENGINE):
            hack_pyodbc_cursor(cursor)
        try:
            if args:
                cursor.execute(sql, args)
            else:
                cursor.execute(sql)
        except DatabaseError as exception:
            add_info_to_exception(exception, {'sql': sql, 'args': args})
            raise
        return cursor

    def get_patient_mrids(self) -> List[int]:
        sql = self.patient_multiquery.patient_id_query(with_order_by=True)
        # log.critical(sql)
        with self.get_executed_cursor(sql) as cursor:
            return [row[0] for row in cursor.fetchall()]

    def get_zipped_tsv_binary(self) -> bytes:
        # Don't pass giant result sets around beyond what's necessary.
        # Use cursor.fetchone()
        grammar = make_grammar(settings.RESEARCH_DB_DIALECT)
        memfile = io.BytesIO()
        z = zipfile.ZipFile(memfile, "w")
        for table_id, sql, args in self.patient_multiquery.all_queries():
            with self.get_executed_cursor(sql, args) as cursor:
                fieldnames = get_fieldnames_from_cursor(cursor)
                tsv = make_tsv_row(fieldnames)
                row = cursor.fetchone()
                while row is not None:
                    tsv += make_tsv_row(row)
                    row = cursor.fetchone()
            filename = table_id.identifier(grammar) + ".tsv"
            z.writestr(filename, tsv.encode("utf-8"))
        z.close()
        return memfile.getvalue()

    def get_xlsx_binary(self) -> bytes:
        """
        Other notes:
        - cell size
          http://stackoverflow.com/questions/13197574/python-openpyxl-column-width-size-adjust
          ... and the "auto_size" / "bestFit" options don't really do the job,
              according to the interweb
        """  # noqa
        wb = Workbook()
        wb.remove_sheet(wb.active)  # remove the autocreated blank sheet
        sqlsheet_rows = [["Table", "SQL", "Args", "Executed_at"]]
        for table_id, sql, args in self.patient_multiquery.all_queries():
            sqlsheet_rows.append([str(table_id), sql, repr(args),
                                  datetime.datetime.now()])
            ws = wb.create_sheet(title=str(table_id))
            with self.get_executed_cursor(sql, args) as cursor:
                fieldnames = get_fieldnames_from_cursor(cursor)
                ws.append(fieldnames)
                row = cursor.fetchone()
                while row is not None:
                    ws.append(tuple(row))
                    row = cursor.fetchone()
        sql_ws = wb.create_sheet(title="SQL")
        for r in sqlsheet_rows:
            sql_ws.append(r)
        return excel_to_bytes(wb)

    # -------------------------------------------------------------------------
    # Using the internal PatientMultiQuery
    # -------------------------------------------------------------------------

    def get_patient_id_query(self, with_order_by: bool = True) -> str:
        return self.patient_multiquery.patient_id_query(
            with_order_by=with_order_by)

    # -------------------------------------------------------------------------
    # Display
    # -------------------------------------------------------------------------

    def summary_html(self) -> str:
        # Nasty hack. We want collapsing things, so we want HTML element IDs.
        # We could build the HTML table in code for the Patient Explorer
        # chooser, but I was trying to do it in Django templates.
        # However, it's not easy to pass parameters (such as an
        # HtmlElementCounter) back to Python from Django templates.
        # So we can hack it a bit:
        element_counter = HtmlElementCounter(prefix="pe_{}_".format(self.id))
        return self.patient_multiquery.summary_html(
            element_counter=element_counter)

    def has_patient_id_query(self) -> bool:
        return self.patient_multiquery.has_patient_id_query()

    def has_output_columns(self) -> bool:
        return self.patient_multiquery.has_output_columns()

    # -------------------------------------------------------------------------
    # Data finder
    # -------------------------------------------------------------------------

    def data_finder_excel(self) -> bytes:
        """
        Performs a SELECT COUNT(*)
        Returns (fieldnames, rows).
        """
        sql, args = self.patient_multiquery.data_finder_query()
        wb = Workbook()
        wb.remove_sheet(wb.active)  # remove the autocreated blank sheet
        sql_ws = wb.create_sheet("SQL")
        sql_ws.append(["SQL", "Args", "Executed_at"])
        sql_ws.append([format_sql(sql), repr(args), datetime.datetime.now()])
        all_ws = wb.create_sheet("All_patients")
        with self.get_executed_cursor(sql, args) as cursor:
            fieldnames = get_fieldnames_from_cursor(cursor)
            all_ws.append(fieldnames)
            row = cursor.fetchone()
            ws = None  # type: Worksheet
            while row is not None:
                rid = row[0]
                if rid not in wb:
                    ws = wb.create_sheet(rid)
                    ws.append(fieldnames)
                rowtuple = tuple(row)
                ws.append(rowtuple)
                all_ws.append(rowtuple)
                row = cursor.fetchone()
        return excel_to_bytes(wb)


# =============================================================================
# PatientExplorer auditing class
# =============================================================================

class PatientExplorerAudit(models.Model):
    """
    Audit log for a PatientExplorer.
    """
    id = models.AutoField(primary_key=True)  # automatic
    patient_explorer = models.ForeignKey('PatientExplorer')
    when = models.DateTimeField(auto_now_add=True)
    count_only = models.BooleanField(default=False)
    n_records = models.IntegerField(default=0)
    # ... not PositiveIntegerField; SQL Server gives -1, for example
    failed = models.BooleanField(default=False)
    fail_msg = models.TextField()

    def __str__(self):
        return "<PatientExplorerAudit id={}>".format(self.id)
