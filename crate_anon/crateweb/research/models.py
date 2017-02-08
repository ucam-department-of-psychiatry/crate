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

from django.db import connections, models
from django.db.models import QuerySet
from django.conf import settings
from django.http.request import HttpRequest
from openpyxl import Workbook
from picklefield.fields import PickledObjectField

from crate_anon.common.sql import (
    ColumnId,
    columns_to_table_column_hierarchy,
    make_grammar,
    set_distinct,
    TableId,
    WhereCondition,
)
from crate_anon.common.sql_grammar import format_sql
from crate_anon.crateweb.core.dbfunc import (
    dictfetchall,
    escape_percent_for_python_dbapi,
    get_fieldnames_from_cursor,
    make_tsv_row,
    translate_sql_qmark_to_percent,
)
from crate_anon.crateweb.research.html_functions import (
    highlight_text,
    N_CSS_HIGHLIGHT_CLASSES,
)
from crate_anon.crateweb.research.research_db_info import (
    get_trid_column,
    get_rid_column,
)
from crate_anon.crateweb.research.sql_writer import (
    add_to_select,
)

log = logging.getLogger(__name__)


# =============================================================================
# Debugging SQL
# =============================================================================

def debug_query() -> None:
    cursor = connections['research'].cursor()
    cursor.execute("SELECT 'debug'")


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
    args = PickledObjectField(verbose_name='Pickled arguments',
                              null=True)
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

    def __str__(self) -> str:
        return "<Query id={}>".format(self.id)

    def save(self, *args, **kwargs) -> None:
        """
        Custom save method.
        Ensures that only one Query has active == True for a given user.
        """
        # http://stackoverflow.com/questions/1455126/unique-booleanfield-value-in-django  # noqa
        if self.active:
            Query.objects.filter(user=self.user, active=True)\
                         .update(active=False)
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

    def get_sql_args_for_mysql(self) -> Tuple[str, Optional[List[Any]]]:
        """
        Get sql/args in a format suitable for MySQL, with %s placeholders,
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

    def get_executed_cursor(self, sql_append_raw: str = None) -> Any:
        """
        Get cursor with a query executed
        """
        (sql, args) = self.get_sql_args_for_mysql()
        if sql_append_raw:
            sql += sql_append_raw
        cursor = connections['research'].cursor()
        if args:
            cursor.execute(sql, args)
        else:
            cursor.execute(sql)
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

    def add_excel_sheet(self, workbook: Workbook, title: str = None) -> None:
        ws = workbook.create_sheet(title)
        with self.get_executed_cursor() as cursor:
            fieldnames = get_fieldnames_from_cursor(cursor)
            ws.append(fieldnames)
            row = cursor.fetchone()
            while row is not None:
                ws.append(row)
                row = cursor.fetchone()

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


class PatientMultiQuery(object):
    def __init__(self,
                 output_columns: List[ColumnId] = None,
                 patient_conditions: List[WhereCondition] = None,
                 manual_patient_id_query: str = ''):
        self._output_columns = output_columns or []  # type: List[ColumnId]
        self._patient_conditions = patient_conditions or []  # type: List[WhereCondition]
        self._manual_patient_id_query = manual_patient_id_query

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

    def get_output_columns(self) -> List[ColumnId]:
        return sorted(self._output_columns)

    def get_patient_conditions(self) -> List[WhereCondition]:
        return sorted(self._patient_conditions)

    def get_manual_patient_id_query(self) -> str:
        return self._manual_patient_id_query

    def add_output_column(self, column_id: ColumnId) -> None:
        if column_id not in self._output_columns:
            self._output_columns.append(column_id)

    def add_patient_condition(self, where: WhereCondition) -> None:
        if where not in self._patient_conditions:
            self._patient_conditions.append(where)

    def set_override_query(self, query: str) -> None:
        self._manual_patient_id_query = query

    def patient_id_query(self) -> str:
        # Returns an SQL SELECT statement based on the list of WHERE conditions
        # already stored, joined with AND by default.

        if self._manual_patient_id_query:
            # User has specified one manually.
            return self._manual_patient_id_query

        if not self._patient_conditions:
            return ''

        dialect = settings.RESEARCH_DB_DIALECT
        grammar = make_grammar(dialect)
        select_trid_column = get_trid_column(
            self._patient_conditions[0].table_id())
        trid_alias = "_trid"
        sql = add_to_select(
            '',
            select_column=select_trid_column,
            select_alias=trid_alias,
            magic_join=True,
            dialect=dialect,
            formatted=False
        )
        sql = set_distinct(sql, dialect=dialect, formatted=False)
        # log.critical(sql)
        for where_condition in self._patient_conditions:
            sql = add_to_select(
                sql,
                where_type="AND",
                where_expression=where_condition.sql(grammar),
                where_table=where_condition.table_id(),
                magic_join=True,
                dialect=dialect,
                formatted=False
            )
            # log.critical(sql)
        sql = format_sql(sql)
        return sql

    def all_full_queries(self) -> List[Tuple[TableId, str]]:
        return self.all_queries(trids=None)

    def all_queries_specific_patients(
            self,
            trids: List[int]) -> List[Tuple[TableId, str]]:
        return self.all_queries(trids=trids)

    def all_queries(self,
                    trids: List[int] = None) -> List[Tuple[TableId, str]]:
        queries = []
        table_columns_map = columns_to_table_column_hierarchy(
            self._output_columns, sort=True)
        for table, columns in table_columns_map:
            newquery = self.make_query(table_id=table,
                                       columns=columns,
                                       trids=trids)
            queries.append(newquery)
        return queries

    def make_query(self,
                   table_id: TableId,
                   columns: List[ColumnId],
                   trids: List[int] = None) -> Tuple[TableId, str]:
        # TRUSTS THE "trids" PARAMETERS.
        trids = trids or []
        if not columns:
            raise ValueError("No columns specified")

        grammar = make_grammar(settings.RESEARCH_DB_DIALECT)
        rid_column = get_rid_column(table_id)
        trid_column = get_trid_column(table_id)
        all_columns = [rid_column, trid_column]
        for c in columns:
            if c not in all_columns:
                all_columns.append(c)

        if trids:
            in_clause = ",".join(str(t) for t in trids)
        else:
            # If we haven't specified specific patients, use our patient-
            # finding query.
            in_clause = self.patient_id_query()
        where_clause = "WHERE {trid} IN ({in_clause})".format(
            trid=trid_column.identifier(grammar),
            in_clause=in_clause,
        )
        sql = "SELECT {all_columns} FROM {table} {where_clause}".format(
            all_columns=", ".join(c.identifier(grammar) for c in all_columns),
            table=table_id.identifier(grammar),
            where_clause=where_clause,
        )
        return table_id, sql


PATIENT_EXPLORER_FWD_REF = "PatientExplorer"


class PatientExplorer(models.Model):
    """
    Class to explore the research database on a per-patient basis.
    """
    class Meta:
        app_label = "research"

    id = models.AutoField(primary_key=True)  # automatic
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    patient_multiquery = PickledObjectField(
        verbose_name='Pickled PatientMultiQuery',
        null=True)  # type: PatientMultiQuery
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
        """
        if self.active:
            PatientExplorer.objects\
                .filter(user=self.user, active=True)\
                .update(active=False)
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

    def all_queries(self, trids: List[int] = None) -> List[Tuple[TableId, str]]:  # noqa
        return self.patient_multiquery.all_queries(trids=trids)

    @staticmethod
    def get_executed_cursor(sql: str, args: List[Any] = None) -> Any:
        """
        Get cursor with a query executed
        """
        args = args or []
        cursor = connections['research'].cursor()
        if args:
            cursor.execute(sql, args)
        else:
            cursor.execute(sql)
        return cursor

    def get_patient_trids(self) -> List[int]:
        sql = self.patient_multiquery.patient_id_query()
        with self.get_executed_cursor(sql) as cursor:
            return [row[0] for row in cursor.fetchall()]

    def get_zipped_tsv_binary_data(self) -> bytes:
        # Don't pass giant result sets around beyond what's necessary.
        # Use cursor.fetchone()
        grammar = make_grammar(settings.RESEARCH_DB_DIALECT)
        memfile = io.BytesIO()
        z = zipfile.ZipFile(memfile, "w")
        for table_id, sql in self.patient_multiquery.all_queries():
            with self.get_executed_cursor(sql) as cursor:
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

    def get_xlsx_binary_data(self) -> bytes:
        wb = Workbook()
        wb.remove_sheet(wb.active)  # remove the autocreated blank sheet
        sqlsheet_rows = [["Table", "SQL", "Executed at"]]
        for table_id, sql in self.patient_multiquery.all_queries():
            sqlsheet_rows.append([str(table_id), sql, datetime.datetime.now()])
            ws = wb.create_sheet(title=str(table_id))
            with self.get_executed_cursor(sql) as cursor:
                fieldnames = get_fieldnames_from_cursor(cursor)
                ws.append(fieldnames)
                row = cursor.fetchone()
                while row is not None:
                    ws.append(row)
                    row = cursor.fetchone()
        sql_ws = wb.create_sheet(title="SQL")
        for r in sqlsheet_rows:
            sql_ws.append(r)
        memfile = io.BytesIO()
        wb.save(memfile)
        return memfile.getvalue()

    # -------------------------------------------------------------------------
    # Using the internal PatientMultiQuery
    # -------------------------------------------------------------------------

    def get_patient_id_query(self) -> str:
        return self.patient_multiquery.patient_id_query()


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
