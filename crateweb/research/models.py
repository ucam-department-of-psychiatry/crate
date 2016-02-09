#!/usr/bin/env python3
# research/models.py

from collections import OrderedDict
from django.db import connections, models
from django.conf import settings
from django.utils.functional import cached_property
from picklefield.fields import PickledObjectField
import logging
logger = logging.getLogger(__name__)
from core.dbfunc import (
    dictfetchall,
    escape_percent_for_python_dbapi,
    get_fieldnames_from_cursor,
    is_mysql_column_type_textual,
    translate_sql_qmark_to_percent,
    tsv_escape,
)
from .html_functions import highlight_text, N_CSS_HIGHLIGHT_CLASSES


# =============================================================================
# Debugging SQL
# =============================================================================

def debug_query():
    cursor = connections['research'].cursor()
    cursor.execute("SELECT 'debug'")


# =============================================================================
# Query class
# =============================================================================

class Query(models.Model):
    """
    Class to query the research database.
    """
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

    def __str__(self):
        return "<Query id={}>".format(self.id)

    def save(self, *args, **kwargs):
        """
        Custom save method.
        Ensures that only one Query has active == True for a given user.
        """
        # http://stackoverflow.com/questions/1455126/unique-booleanfield-value-in-django  # noqa
        if self.active:
            Query.objects.filter(user=self.user, active=True)\
                         .update(active=False)
        super().save(*args, **kwargs)

    @staticmethod
    def get_active_query_or_none(request):
        try:
            return Query.objects.get(user=request.user, active=True)
        except Query.DoesNotExist:
            return None

    @staticmethod
    def get_active_query_id_or_none(request):
        if not request.user.is_authenticated():
            return None
        try:
            query = Query.objects.get(user=request.user, active=True)
            return query.id
        except Query.DoesNotExist:
            return None

    def activate(self):
        self.active = True
        self.save()

    def mark_audited(self):
        if self.audited:
            return
        self.audited = True
        self.save()

    def mark_deleted(self):
        if self.deleted:
            logger.debug("pointless)")
            return
        self.deleted = True
        self.active = False
        logger.debug("about to save")
        self.save()
        logger.debug("saved")

    def delete_if_permitted(self):
        """If a query has been audited, it isn't properly deleted."""
        if self.deleted:
            logger.debug("already flagged as deleted")
            return
        if self.audited:
            logger.debug("marking as deleted")
            self.mark_deleted()
        else:
            # actually delete
            logger.debug("actually deleting")
            self.delete()

    def audit(self, count_only=False, n_records=0,
              failed=False, fail_msg=""):
        a = QueryAudit(query=self,
                       count_only=count_only,
                       n_records=n_records,
                       failed=failed,
                       fail_msg=fail_msg)
        a.save()
        self.mark_audited()

    def get_original_sql(self):
        return self.sql

    def get_sql_args_for_mysql(self):
        """
        Get sql/args in a format suitable for MySQL, with %s placeholders,
        or as escaped raw SQL.
        """
        if self.raw:
            sql = escape_percent_for_python_dbapi(self.sql)
            args = None
        else:
            if self.qmark:
                sql = translate_sql_qmark_to_percent(self.sql)
            else:
                sql = self.sql
            args = self.args
        return (sql, args)

    def get_executed_cursor(self, sql_append_raw=None):
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

    def gen_rows(self, firstrow=0, lastrow=None):
        """
        Generate rows from the query.
        """
        if firstrow > 0 or lastrow is not None:
            sql_append_raw = " LIMIT {f},{n}".format(
                f=firstrow,
                n=(lastrow - firstrow + 1),
            )
            # zero-indexed; http://dev.mysql.com/doc/refman/5.0/en/select.html
        else:
            sql_append_raw = None
        cursor = self.get_executed_cursor(sql_append_raw)
        row = cursor.fetchone()
        while row is not None:
            yield row
            row = cursor.fetchone()

    def make_tsv(self):
        cursor = self.get_executed_cursor()
        fieldnames = get_fieldnames_from_cursor(cursor)
        tsv = "\t".join([tsv_escape(f) for f in fieldnames]) + "\n"
        row = cursor.fetchone()
        while row is not None:
            tsv += "\t".join([tsv_escape(x) for x in row]) + "\n"
            row = cursor.fetchone()
        return tsv

    def dictfetchall(self):
        """Generates all results as a list of dicts."""
        cursor = self.get_executed_cursor()
        return dictfetchall(cursor)

    def add_highlight(self, text, colour=0):
        h = Highlight(text=text, colour=colour)
        self.highlight_set.add(h)

    def get_highlights_as_dict(self):
        d = OrderedDict()
        for n in range(N_CSS_HIGHLIGHT_CLASSES):
            d[n] = Highlight.objects.filter(query_id=self.id, colour=n)
        return d

    def get_highlight_descriptions(self):
        d = self.get_highlights_as_dict()
        desc = []
        for n in range(N_CSS_HIGHLIGHT_CLASSES):
            if d[n]:
                desc.append([", ".join(highlight_text(h.text, n))
                             for h in d[n]])
        return desc


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
    n_records = models.PositiveIntegerField(default=0)
    failed = models.BooleanField(default=False)
    fail_msg = models.TextField()

    def __str__(self):
        return "<QueryAudit id={}>".format(self.id)


# =============================================================================
# Query highlighting class
# =============================================================================

class Highlight(models.Model):
    """
    Represents the highlighting of a query.
    """
    id = models.AutoField(primary_key=True)  # automatic
    user = models.ForeignKey(settings.AUTH_USER_MODEL)
    colour = models.PositiveSmallIntegerField(verbose_name="Colour number")
    text = models.CharField(max_length=255, verbose_name="Text to highlight")
    active = models.BooleanField(default=True)

    def __str__(self):
        return "colour={}, text={}".format(self.colour, self.text)

    def get_safe_colour(self):
        if self.colour is None:
            return 0
        return min(self.colour, N_CSS_HIGHLIGHT_CLASSES - 1)

    @staticmethod
    def as_ordered_dict(highlight_list):
        d = dict()
        for highlight in highlight_list:
            n = highlight.get_safe_colour()
            if n not in d:
                d[n] = []
            d[n].append(highlight)
        return OrderedDict(sorted(d.items()))

    @staticmethod
    def get_active_highlights(request):
        return Highlight.objects.filter(user=request.user, active=True)

    def activate(self):
        self.active = True
        self.save()

    def deactivate(self):
        self.active = False
        self.save()


# =============================================================================
# Information about the research database
# =============================================================================

class ResearchDatabaseInfo(object):
    """
    Fetches schema information from the research database.
    Class only exists to be able to use @cached_property.
    """
    @cached_property
    def infodictlist(self):
        schemas = settings.RESEARCH_DB_INFO_SCHEMAS
        logger.debug("Fetching/caching database structure "
                     "(for schemas: {})...".format(", ".join(schemas)))
        sql = translate_sql_qmark_to_percent("""
            SELECT
                c.table_schema,
                c.table_name,
                c.column_name,
                c.is_nullable,
                c.column_type,  /* MySQL: e.g. varchar(32) */
                c.column_comment,  /* MySQL */
                EXISTS (
                    SELECT *
                    FROM information_schema.statistics s
                    WHERE s.table_schema = c.table_schema
                    AND s.table_name = c.table_name
                    AND s.column_name = c.column_name
                ) AS indexed,
                EXISTS (
                    SELECT *
                    FROM information_schema.statistics s
                    WHERE s.table_schema = c.table_schema
                    AND s.table_name = c.table_name
                    AND s.column_name = c.column_name
                    AND s.index_type LIKE 'FULLTEXT%'
                ) AS indexed_fulltext
            FROM
                information_schema.columns c
            WHERE
                c.table_schema IN ({schema_placeholder})
            ORDER BY
                c.table_schema,
                c.table_name,
                c.column_name
        """.format(
            schema_placeholder=",".join(["?"] * len(schemas)),
        ))
        args = schemas
        # We execute this one directly, rather than using the Query class,
        # since this is a system rather than a per-user query.
        cursor = connections['research'].cursor()
        cursor.execute(sql, args)
        results = dictfetchall(cursor)
        logger.debug("... done")
        return results
        # Multiple values:
        # - Don't circumvent the parameter protection against SQL injection.
        # - Too much hassle to use Django's ORM model here, though that would
        #   also be possible.
        # - http://stackoverflow.com/questions/907806

    def tables_containing_field(self, fieldname):
        """
        Returns a list of [schema, table] pairs.
        """
        schemas = settings.RESEARCH_DB_INFO_SCHEMAS
        sql = translate_sql_qmark_to_percent("""
            SELECT
                c.table_schema,
                c.table_name
            FROM
                information_schema.columns c
            WHERE
                c.table_schema IN ({schema_placeholder})
                AND c.column_name = ?
            ORDER BY
                c.table_schema,
                c.table_name

        """.format(
            schema_placeholder=",".join(["?"] * len(schemas)),
        ))
        args = schemas + [fieldname]
        cursor = connections['research'].cursor()
        cursor.execute(sql, args)
        return cursor.fetchall()

    def text_columns(self, schema, table, min_length=1):
        """
        Returns list of (column_name, indexed_fulltext) pairs.
        """
        results = []
        for rowdict in self.infodictlist:
            if rowdict['table_schema'] != schema:
                continue
            if rowdict['table_name'] != table:
                continue
            column_type = rowdict['column_type']
            if not is_mysql_column_type_textual(column_type, min_length):
                continue
            column_name = rowdict['column_name']
            indexed_fulltext = rowdict['indexed_fulltext']
            results.append((column_name, indexed_fulltext))
        return results


research_database_info = ResearchDatabaseInfo()


# =============================================================================
# Lookup class for secret RID-to-PID conversion
# =============================================================================

class PidLookupRouter(object):
    # https://docs.djangoproject.com/en/1.8/topics/db/multi-db/
    # https://newcircle.com/s/post/1242/django_multiple_database_support
    def db_for_read(self, model, **hints):
        """
        read model PidLookup -> look at database secret
        """
        # logger.debug("PidLookupRouter: {}".format(model._meta.model_name))
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


def get_pid_lookup(trid=None, rid=None, mrid=None):
    if trid is not None:
        lookup = PidLookup.objects.get(trid=trid)
    elif rid is not None:
        lookup = PidLookup.objects.get(rid=rid)
    elif mrid is not None:
        lookup = PidLookup.objects.get(mrid=mrid)
    else:
        raise ValueError("no input")
    return lookup


def get_mpid(trid=None, rid=None, mrid=None):
    lookup = get_pid_lookup(trid=trid, rid=rid, mrid=mrid)
    return lookup.mpid


def get_pid(trid=None, rid=None, mrid=None):
    lookup = get_pid_lookup(trid=trid, rid=rid, mrid=mrid)
    return lookup.pid
