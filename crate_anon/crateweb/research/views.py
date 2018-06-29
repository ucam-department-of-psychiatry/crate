#!/usr/bin/env python
# crate_anon/crateweb/research/views.py

"""
===============================================================================

    Copyright (C) 2015-2018 Rudolf Cardinal (rudolf@pobox.com).

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

import datetime
# from functools import lru_cache
import json
import logging
# import pprint
from typing import Any, Dict, List, Type, Union

from cardinal_pythonlib.dbfunc import get_fieldnames_from_cursor
from cardinal_pythonlib.django.function_cache import django_cache_function
from cardinal_pythonlib.django.serve import file_response
from cardinal_pythonlib.exceptions import recover_info_from_exception
from cardinal_pythonlib.hash import hash64
from cardinal_pythonlib.logs import BraceStyleAdapter
from cardinal_pythonlib.sqlalchemy.dialect import SqlaDialectName
from django import forms
from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import (
    ObjectDoesNotExist,
    ValidationError,
)
# from django.db import connection
from django.db import DatabaseError
from django.db.models import Q, QuerySet
from django.http.response import HttpResponse, HttpResponseRedirect
from django.http.request import HttpRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import escape
from pyparsing import ParseException

from crate_anon.common.contenttypes import ContentType
from crate_anon.common.sql import (
    ColumnId,
    escape_sql_string_literal,
    escape_sql_string_or_int_literal,
    SQL_OPS_MULTIPLE_VALUES,
    SQL_OPS_VALUE_UNNECESSARY,
    TableId,
    toggle_distinct,
    WhereCondition,
)
from crate_anon.crateweb.core.utils import is_clinician, is_superuser, paginate
from crate_anon.crateweb.research.forms import (
    AddHighlightForm,
    AddQueryForm,
    ClinicianAllTextFromPidForm,
    DatabasePickerForm,
    DEFAULT_MIN_TEXT_FIELD_LENGTH,
    FieldPickerInfo,
    ManualPeQueryForm,
    PidLookupForm,
    QueryBuilderForm,
    RidLookupForm,
    SQLHelperTextAnywhereForm,
)
from crate_anon.crateweb.research.html_functions import (
    highlight_text,
    HtmlElementCounter,
    make_result_element,
    make_collapsible_sql_query,
    N_CSS_HIGHLIGHT_CLASSES,
    prettify_sql_css,
    prettify_sql_html,
    prettify_sql_and_args,
)
from crate_anon.crateweb.research.models import (
    Highlight,
    PidLookup,
    PatientExplorer,
    PatientMultiQuery,
    Query,
)
from crate_anon.crateweb.research.research_db_info import (
    research_database_info,
    PatientFieldPythonTypes,
    SingleResearchDatabase,
)
from crate_anon.crateweb.userprofile.models import get_patients_per_page
from crate_anon.crateweb.research.sql_writer import (
    add_to_select,
    SelectElement,
)

log = BraceStyleAdapter(logging.getLogger(__name__))


# =============================================================================
# Helper functions
# =============================================================================

def validate_blank_form(request: HttpRequest) -> None:
    """
    Checks that the request is (a) a POST request, and (b) passes CRSF
    validation.
    """
    if request.method != "POST":
        raise ValidationError("Use HTTP POST, not HTTP GET or other methods")
    form = forms.Form(request.POST)
    if not form.is_valid():  # checks CSRF
        raise ValidationError("Form failed validation")


def query_context(request: HttpRequest) -> Dict[str, Any]:
    query_id = Query.get_active_query_id_or_none(request)
    pe_id = PatientExplorer.get_active_pe_id_or_none(request)
    return {
        'query_selected': query_id is not None,
        'current_query_id': query_id,
        'pe_selected': pe_id is not None,
        'current_pe_id': pe_id,
    }
    # Try to minimize SQL here, as these calls will be used for EVERY
    # request.
    # This problem can be circumvented with a per-request cache; see
    # http://stackoverflow.com/questions/3151469/per-request-cache-in-django


def datetime_iso_for_filename() -> str:
    dtnow = datetime.datetime.now()
    return dtnow.strftime("%Y%m%d_%H%M%S")


# =============================================================================
# Errors
# =============================================================================

def generic_error(request: HttpRequest, error: str) -> HttpResponse:
    context = {
        'error': error,
    }
    return render(request, 'generic_error.html', context)


# =============================================================================
# Queries
# =============================================================================

@django_cache_function(timeout=None)
# @lru_cache(maxsize=None)
def get_db_structure_json() -> str:
    colinfolist = research_database_info.get_colinfolist()
    if not colinfolist:
        log.warning("get_db_structure_json(): colinfolist is empty")
    info = []  # type: List[Dict[str, Any]]
    for dbinfo in research_database_info.dbinfolist:
        log.info("get_db_structure_json: schema {}".format(
            dbinfo.schema_identifier))
        if not dbinfo.eligible_for_query_builder:
            log.debug("Skipping schema={}: not eligible for query "
                      "builder".format(dbinfo.schema_identifier))
            continue
        schema_cil = [x for x in colinfolist
                      if x.table_catalog == dbinfo.database and
                      x.table_schema == dbinfo.schema_name]
        table_info = []  # type: List[Dict[str, Any]]
        for table in sorted(set(x.table_name for x in schema_cil)):
            table_cil = [x for x in schema_cil if x.table_name == table]
            if not any(x for x in table_cil
                       if x.column_name == dbinfo.trid_field):
                # This table doesn't contain a TRID, so we will skip it.
                log.debug("... skipping table {}: no TRID [{}]".format(
                    table, dbinfo.trid_field))
                continue
            if not any(x for x in table_cil
                       if x.column_name == dbinfo.rid_field):
                # This table doesn't contain a RID, so we will skip it.
                log.debug("... skipping table {}: no RID [{}]".format(
                    table, dbinfo.rid_field))
                continue
            column_info = []  # type: List[Dict[str, str]]
            for ci in sorted(table_cil, key=lambda x: x.column_name):
                column_info.append({
                    'colname': ci.column_name,
                    'coltype': ci.querybuilder_type,
                    'rawtype': ci.column_type,
                    'comment': ci.column_comment or '',
                })
            if column_info:
                table_info.append({
                    'table': table,
                    'columns': column_info,
                })
            log.debug("... using table {}: {} columns".format(
                table, len(column_info)))
        if table_info:
            info.append({
                'database': dbinfo.database,
                'schema': dbinfo.schema_name,
                'tables': table_info,
            })
    return json.dumps(info)


def query_build(request: HttpRequest) -> HttpResponse:
    """
    Assisted query builder, based on the data dictionary.
    """
    # NOTES FOR FIRST METHOD, with lots (and lots) of forms.
    # - In what follows, we want a normal template but we want to include a
    #   large chunk of raw HTML. I was doing this with
    #   {{ builder_html | safe }} within the template, but it was very slow
    #   (e.g. 500ms on my machine; 50s on the CPFT "sandpit" server,
    #   2016-06-28). The delay was genuinely in the template rendering, it
    #   seems, based on profiling and manual log calls.
    # - A simple string replacement, as below, was about 7% of the total time
    #   (e.g. 3300ms instead of 50s).
    # - Other alternatives might include the Jinja2 template system, which is
    #   apparently faster than the Django default, but we may not need further
    #   optimization.
    # - Another, potentially better, solution, is not to send dozens or
    #   hundreds of forms, but to write some Javascript to make this happen
    #   mostly on the client side. Might look better, too. (Yes, it does.)

    # NB: first "submit" button takes the Enter key, so place WHERE
    # before SELECT so users can hit enter in the WHERE value fields.

    # - If you provide the "request=request" argument to
    #   render_to_string it gives you the CSRF token.
    # - Another way is to ignore "request" and use render_to_string
    #   with a manually crafted context including 'csrf_token'.
    #   (This avoids the global context processors.)
    # - Note that the CSRF token prevents simple caching of the forms.
    # - But we can't cache anyway if we're going to have some forms
    #   (differentially) non-collapsed at the start, e.g. on form POST.
    # - Also harder work to do this HTML manually (rather than with
    #   template rendering), because the csrf_token ends up like:
    #   <input type='hidden' name='csrfmiddlewaretoken' value='RGN5UZnTVkLFAVNtXRpJwn5CclBRAdLr' />  # noqa

    profile = request.user.profile
    parse_error = ''
    default_database = research_database_info.get_default_database_name()
    default_schema = research_database_info.get_default_schema_name()
    with_database = research_database_info.uses_database_level()
    form = None

    if request.method == 'POST':
        grammar = research_database_info.grammar
        try:
            if 'global_clear' in request.POST:
                profile.sql_scratchpad = ''
                profile.save()

            elif 'global_toggle_distinct' in request.POST:
                profile.sql_scratchpad = toggle_distinct(
                    profile.sql_scratchpad, grammar=grammar)
                profile.save()

            elif 'global_save' in request.POST:
                return query_submit(request, profile.sql_scratchpad, run=False)

            elif 'global_run' in request.POST:
                return query_submit(request, profile.sql_scratchpad, run=True)

            else:
                form = QueryBuilderForm(request.POST, request.FILES)
                if form.is_valid():
                    database = (form.cleaned_data['database'] if with_database
                                else '')
                    schema = form.cleaned_data['schema']
                    table = form.cleaned_data['table']
                    column = form.cleaned_data['column']
                    column_id = ColumnId(db=database, schema=schema,
                                         table=table, column=column)
                    table_id = column_id.table_id

                    if 'submit_select' in request.POST:
                        profile.sql_scratchpad = add_to_select(
                            profile.sql_scratchpad,
                            select_elements=[
                                SelectElement(column_id=column_id)
                            ],
                            magic_join=True,
                            grammar=grammar
                        )

                    elif 'submit_select_star' in request.POST:
                        select_elements = [
                            SelectElement(column_id=c.column_id) for c in
                            research_database_info.all_columns(table_id)]
                        profile.sql_scratchpad = add_to_select(
                            profile.sql_scratchpad,
                            select_elements=select_elements,
                            magic_join=True,
                            grammar=grammar,
                        )

                    elif 'submit_where' in request.POST:
                        datatype = form.cleaned_data['datatype']
                        op = form.cleaned_data['where_op']
                        # Value
                        if op in SQL_OPS_MULTIPLE_VALUES:
                            value = form.file_values_list
                        elif op in SQL_OPS_VALUE_UNNECESSARY:
                            value = None
                        else:
                            value = form.get_cleaned_where_value()
                        # WHERE fragment
                        wherecond = WhereCondition(column_id=column_id,
                                                   op=op,
                                                   datatype=datatype,
                                                   value_or_values=value)
                        profile.sql_scratchpad = add_to_select(
                            profile.sql_scratchpad,
                            where_type="AND",
                            where_conditions=[wherecond],
                            magic_join=True,
                            grammar=grammar
                        )

                    else:
                        raise ValueError("Bad form command!")
                    profile.save()

                else:
                    pass

        except ParseException as e:
            parse_error = str(e)

    if form is None:
        form = QueryBuilderForm()

    starting_values_dict = {
        'database': form.data.get('database', '') if with_database else '',
        'schema': form.data.get('schema', ''),
        'table': form.data.get('table', ''),
        'column': form.data.get('column', ''),
        'op': form.data.get('where_op', ''),
        'date_value': form.data.get('date_value', ''),
        # Impossible to set file_value programmatically. (See querybuilder.js.)
        'float_value': form.data.get('float_value', ''),
        'int_value': form.data.get('int_value', ''),
        'string_value': form.data.get('string_value', ''),
        'offer_where': bool(profile.sql_scratchpad),  # existing SELECT?
        'form_errors': "<br>".join("{}: {}".format(k, v)
                                   for k, v in form.errors.items()),
        'default_database': default_database,
        'default_schema': default_schema,
        'with_database': with_database,
    }
    context = {
        'nav_on_querybuilder': True,
        'sql': prettify_sql_html(profile.sql_scratchpad),
        'parse_error': parse_error,
        'database_structure': get_db_structure_json(),
        'starting_values': json.dumps(starting_values_dict),
        'sql_dialect': settings.RESEARCH_DB_DIALECT,
        'dialect_mysql': settings.RESEARCH_DB_DIALECT == SqlaDialectName.MYSQL,
        'dialect_mssql': settings.RESEARCH_DB_DIALECT == SqlaDialectName.MSSQL,
        'sql_highlight_css': prettify_sql_css(),
    }
    context.update(query_context(request))
    return render(request, 'query_build.html', context)


def get_all_queries(request: HttpRequest) -> QuerySet:
    return Query.objects.filter(user=request.user, deleted=False)\
                        .order_by('-active', '-created')


def get_identical_queries(request: HttpRequest, sql: str) -> List[Query]:
    all_queries = get_all_queries(request)

    # identical_queries = all_queries.filter(sql=sql)
    #
    # - 2017-02-03: we had a problem here, in which the parameter was sent to
    #   SQL Server as type NTEXT, but the field "sql" is NVARCHAR(MAX), leading
    #   to "The data types nvarchar(max) and ntext are incompatible in the
    #   equal to operator."
    # - The Django field type TextField is converted to NVARCHAR(MAX) by
    #   django-pyodbc-azure, in sql_server/pyodbc/base.py, also at [1].
    # - That seems fine; NVARCHAR(MAX) seems more capable than NTEXT.
    #   NTEXT is deprecated.
    # - Error is reproducible with
    #       ... WHERE sql = CAST('hello' AS NTEXT) ...
    # - The order of the types in the error message matches the order in the
    #   SQL statement.
    # - A solution would be to cast the parameter as
    #   CAST(some_parameter AS NVARCHAR(MAX))
    # - Fixed by upgrading pyodbc from 3.1.1 to 4.0.3
    # - Added to FAQ
    # - WARNING: the problem came back with pyodbc==4.0.6, but not fixed again
    #   by downgrading to 4.0.3
    # - See also [2].
    # - An alternative solution would not be to compare on the long text, but
    #   store and compare on a hash of it.
    # - The problem is that either pyodbc or ODBC itself, somehow, is sending
    #   the string parameter as NTEXT.
    #   Similar Perl problem: [3].
    #
    # - In pyodbc, the key functions are:
    #       cursor.cpp: static PyObject* execute(...)
    #       -> params.cpp: bool PrepareAndBind(...)
    #           -> GetParameterInfo  // THIS ONE
    #               Parameter will be of type str.
    #               This will fail for PyBytes_Check [4].
    #               This will match for PyUnicode_Check [5].
    #               Thus:
    #                   -> GetUnicodeInfo
    #                   ... and depending on the string length of the
    #                       parameter, this returns either
    #                   SQL_WVARCHAR -> NVARCHAR on SQL Server [6], for short strings  # noqa
    #                   SQL_WLONGVARCHAR -> NTEXT on SQL Server [6], for long strings  # noqa
    #                   ... and the length depends on
    #                       -> connection.h: cur->cnxn->GetMaxLength(info.ValueType);  # noqa
    #           -> BindParameter
    #   in cursor.cpp
    #
    # - Now we also have pyodbc docs: [7].
    #
    # - Anyway, the upshot is that there is some unpredictabilty in sending
    #   very long parameters... the intermittency would be explained by some
    #   dependency on string length.
    # - Empirically, it fails somewhere around 1,900 characters.
    #
    # - Could switch away from pyodbc, e.g. to Django-mssql [8, 9].
    #   But, as per the CRATE manual, there were version incompatibilities
    #   here. Tried again with v1.8, but it gave configuration errors
    #   (ADODB.Connection; Provider cannot be found. It may not be properly
    #   installed.) Anyway, pyodbc is good enough for SQLAlchemy.
    #
    # [1] https://github.com/michiya/django-pyodbc-azure/blob/azure-1.10/sql_server/pyodbc/base.py  # noqa
    # [2] https://github.com/mkleehammer/pyodbc/blob/master/tests2/informixtests.py  # noqa
    # [3] http://stackoverflow.com/questions/13090907
    # [4] https://docs.python.org/3/c-api/bytes.html
    # [5] https://docs.python.org/3/c-api/unicode.html
    # [6] https://documentation.progress.com/output/DataDirect/DataDirectCloud/index.html#page/queries/microsoft-sql-server-data-types.html  # noqa
    # [7] https://github.com/mkleehammer/pyodbc/wiki/Data-Types
    # [8] https://docs.djangoproject.com/en/1.10/ref/databases/#using-a-3rd-party-database-backend  # noqa
    # [9] https://django-mssql.readthedocs.io/en/latest/

    # Screw it, let's use a hash. We can use our hash64() function and
    # a Django BigIntegerField.

    identical_queries = all_queries.filter(sql_hash=hash64(sql))
    # Now eliminate any chance of errors via hash collisions by double-checking
    # the Python objects:
    return [q for q in identical_queries if q.sql == sql]


def query_submit(request: HttpRequest,
                 sql: str,
                 run: bool = False) -> HttpResponse:
    """
    Ancillary function to add a query, and redirect to the editing or
    run page.
    """
    identical_queries = get_identical_queries(request, sql)
    if identical_queries:
        identical_queries[0].activate()
        query_id = identical_queries[0].id
    else:
        query = Query(sql=sql, raw=True, user=request.user,
                      active=True)
        query.save()
        query_id = query.id
    # redirect to a new URL:
    if run:
        return redirect('results', query_id)
    else:
        return redirect('query')


def query_edit_select(request: HttpRequest) -> HttpResponse:
    """
    Edit or select SQL for current query.
    """
    # log.debug("query")
    # if this is a POST request we need to process the form data
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = AddQueryForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            cmd_run = 'submit_run' in request.POST
            cmd_add = 'submit_add' in request.POST
            cmd_builder = 'submit_builder' in request.POST
            # process the data in form.cleaned_data as required
            sql = form.cleaned_data['sql']
            if cmd_add or cmd_run:
                run = 'submit_run' in request.POST
                return query_submit(request, sql, run)
            elif cmd_builder:
                profile = request.user.profile
                profile.sql_scratchpad = sql
                profile.save()
                return redirect('build_query')
            else:
                raise ValueError("Bad command!")

    # if a GET (or any other method) we'll create a blank form
    values = {}
    all_queries = get_all_queries(request)
    active_queries = all_queries.filter(active=True)
    if active_queries:
        values['sql'] = active_queries[0].get_original_sql()
    form = AddQueryForm(values)
    queries = paginate(request, all_queries)
    profile = request.user.profile
    element_counter = HtmlElementCounter()
    for q in queries:
        q.formatted_query_safe = make_collapsible_sql_query(
            q.get_original_sql(),
            element_counter=element_counter,
            collapse_at_n_lines=profile.collapse_at_n_lines,
        )
    context = {
        'form': form,
        'queries': queries,
        'nav_on_query': True,
        'dialect_mysql': settings.RESEARCH_DB_DIALECT == SqlaDialectName.MYSQL,
        'dialect_mssql': settings.RESEARCH_DB_DIALECT == SqlaDialectName.MSSQL,
        'sql_highlight_css': prettify_sql_css(),
    }
    context.update(query_context(request))
    return render(request, 'query_edit_select.html', context)


def query_activate(request: HttpRequest, query_id: str) -> HttpResponse:
    validate_blank_form(request)
    query = get_object_or_404(Query, id=query_id)  # type: Query
    query.activate()
    return redirect('query')


def query_delete(request: HttpRequest, query_id: str) -> HttpResponse:
    validate_blank_form(request)
    query = get_object_or_404(Query, id=query_id)  # type: Query
    query.delete_if_permitted()
    return redirect('query')


def no_query_selected(request: HttpRequest) -> HttpResponse:
    return render(request, 'query_none_selected.html', query_context(request))


def query_count(request: HttpRequest, query_id: str) -> HttpResponse:
    """
    View COUNT(*) from specific query.
    """
    if query_id is None:
        return no_query_selected(request)
    try:
        query_id = int(query_id)
        # ... conceivably might raise TypeError (from e.g. None), ValueError
        # (from e.g. "xyz"), but both should be filtered out by the URL parser
        query = Query.objects.get(id=query_id, user=request.user)
        # ... will return None if not found, but may raise something derived
        # from ObjectDoesNotExist or (in principle, if this weren't a PK)
        # MultipleObjectsReturned;
        # https://docs.djangoproject.com/en/1.9/ref/models/querysets/#django.db.models.query.QuerySet.get  # noqa
    except ObjectDoesNotExist:
        return render_bad_query_id(request, query_id)
    return render_resultcount(request, query)


def query_count_current(request: HttpRequest) -> HttpResponse:
    """
    View COUNT(*) from current query.
    """
    query = Query.get_active_query_or_none(request)
    if query is None:
        return no_query_selected(request)
    return render_resultcount(request, query)


def query_results(request: HttpRequest, query_id: str) -> HttpResponse:
    """
    View results of chosen query, in tabular format
    """
    if query_id is None:
        return no_query_selected(request)
    try:
        query_id = int(query_id)
        query = Query.objects.get(id=query_id, user=request.user)
    except ObjectDoesNotExist:
        return render_bad_query_id(request, query_id)
    profile = request.user.profile
    highlights = Highlight.get_active_highlights(request)
    return render_resultset(request, query, highlights,
                            collapse_at_len=profile.collapse_at_len,
                            collapse_at_n_lines=profile.collapse_at_n_lines,
                            line_length=profile.line_length)


def query_results_recordwise(request: HttpRequest,
                             query_id: str) -> HttpResponse:
    """
    View results of chosen query, in tabular format
    """
    if query_id is None:
        return no_query_selected(request)
    try:
        query_id = int(query_id)
        query = Query.objects.get(id=query_id, user=request.user)
    except ObjectDoesNotExist:
        return render_bad_query_id(request, query_id)
    profile = request.user.profile
    highlights = Highlight.get_active_highlights(request)
    return render_resultset_recordwise(
        request, query, highlights,
        collapse_at_len=profile.collapse_at_len,
        collapse_at_n_lines=profile.collapse_at_n_lines,
        line_length=profile.line_length)


def query_tsv(request: HttpRequest, query_id: str) -> HttpResponse:
    """
    Download TSV of current query.
    """
    query = get_object_or_404(Query, id=query_id)  # type: Query
    try:
        return file_response(
            query.make_tsv(),
            content_type=ContentType.TSV,
            filename="crate_results_{num}_{datetime}.tsv".format(
                num=query.id,
                datetime=datetime_iso_for_filename(),
            )
        )
    except DatabaseError as exception:
        return render_bad_query(request, query, exception)


def query_excel(request: HttpRequest, query_id: str) -> HttpResponse:
    query = get_object_or_404(Query, id=query_id)  # type: Query
    try:
        return file_response(
            query.make_excel(),
            content_type=ContentType.XLSX,
            filename="crate_query_{}_{}.xlsx".format(
                query_id, datetime_iso_for_filename())
        )
    except DatabaseError as exception:
        return render_bad_query(request, query, exception)


# @user_passes_test(is_superuser)
# def audit(request):
#     """
#     View audit log
#     """
#     all_audits = QueryAudit.objects.all()\
#                                    .select_related('query', 'query__user')\
#                                    .order_by('-id')
#     audits = paginate(request, all_audits)
#     context = {'audits': audits}
#     return render(request, 'audit.html', context)


# =============================================================================
# Internal functions for views on queries
# =============================================================================

# def make_demo_query_unless_exists(request):
#     DEMOQUERY = Query(
#         pk=1,
#         sql="SELECT * FROM notes\nWHERE note LIKE '%Adam%'\nLIMIT 20",
#         raw=True,
#         user=request.user,
#     )
#     DEMOQUERY.save()
#     H1 = Highlight(pk=1, text="Aaron", colour=0, user=request.user)
#     H1.save()
#     H2 = Highlight(pk=2, text="Adam", colour=0, user=request.user)
#     H2.save()
#     H3 = Highlight(pk=3, text="October", colour=1, user=request.user)
#     H3.save()

# EXCEPTIONS FOR HOMEBREW SQL.
# You can see:
# - django.db.ProgrammingError
# - django.db.OperationalError
# - InternalError (?django.db.utils.InternalError)
# ... but I think all are subclasses of django.db.utils.DatabaseError


def render_resultcount(request: HttpRequest, query: Query) -> HttpResponse:
    """
    Displays the number of rows that a given query will fetch.
    """
    if query is None:
        return render_missing_query(request)
    try:
        with query.get_executed_cursor() as cursor:
            rowcount = cursor.rowcount
        query.audit(count_only=True, n_records=rowcount)
        context = {
            'rowcount': rowcount,
            'sql': query.get_original_sql(),
            'nav_on_count': True,
        }
        context.update(query_context(request))
        return render(request, 'query_count.html', context)
    # See above re exception classes
    except DatabaseError as exception:
        query.audit(count_only=True, failed=True,
                    fail_msg=str(exception))
        return render_bad_query(request, query, exception)


def resultset_html_table(fieldnames: List[str],
                         rows: List[List[Any]],
                         element_counter: HtmlElementCounter,
                         start_index: int = 0,
                         highlight_dict: Dict[int, List[Highlight]] = None,
                         collapse_at_len: int = None,
                         collapse_at_n_lines: int = None,
                         line_length: int = None,
                         ditto: bool = True,
                         ditto_html: str = '″',
                         no_ditto_cols: List[int] = None,
                         null: str = '<i>NULL</i>') -> str:
    # Considered but not implemented: hiding table columns
    # ... see esp "tr > *:nth-child(n)" at
    # http://stackoverflow.com/questions/5440657/how-to-hide-columns-in-html-table  # noqa
    no_ditto_cols = no_ditto_cols or []
    ditto_cell = '    <td class="queryresult ditto">{}</td>\n'.format(
        ditto_html)
    html = '<table>\n'
    html += '  <tr>\n'
    html += '    <th><i>#</i></th>\n'
    for field in fieldnames:
        html += '    <th>{}</th>\n'.format(escape(field))
    html += '  </tr>\n'
    for row_index, row in enumerate(rows):
        # row_index is zero-based within this table
        html += '  <tr class="{}">\n'.format(
            "stripy_even" if row_index % 2 == 0 else "stripy_odd"
        )
        # Row number
        html += '    <td><b><i>{}</i></b></td>\n'.format(
            row_index + start_index + 1)
        # Values
        for col_index, value in enumerate(row):
            if (row_index > 0 and ditto and col_index not in no_ditto_cols and
                    value == rows[row_index - 1][col_index]):
                html += ditto_cell
            else:
                html += '    <td class="queryresult">{}</td>\n'.format(
                    make_result_element(
                        value,
                        element_counter=element_counter,
                        highlight_dict=highlight_dict,
                        collapse_at_len=collapse_at_len,
                        collapse_at_n_lines=collapse_at_n_lines,
                        line_length=line_length,
                        null=null
                    )
                )
        html += '  </tr>\n'
    html += '</table>\n'
    return html


def single_record_html_table(fieldnames: List[str],
                             record: List[Any],
                             element_counter: HtmlElementCounter,
                             highlight_dict: Dict[int, List[Highlight]] = None,
                             collapse_at_len: int = None,
                             collapse_at_n_lines: int = None,
                             line_length: int = None) -> str:
    table_html = '<table>\n'
    for col_index, value in enumerate(record):
        fieldname = fieldnames[col_index]
        table_html += '  <tr class="{}">\n'.format(
            "stripy_even" if col_index % 2 == 0 else "stripy_odd"
        )
        table_html += '    <th>{}</th>'.format(escape(fieldname))
        table_html += (
            '    <td class="queryresult">{}</td>\n'.format(
                make_result_element(
                    value,
                    element_counter=element_counter,
                    highlight_dict=highlight_dict,
                    collapse_at_len=collapse_at_len,
                    collapse_at_n_lines=collapse_at_n_lines,
                    line_length=line_length,
                    collapsed=False,
                )
            )
        )
        table_html += '  </tr>\n'
    table_html += '</table>\n'
    return table_html


def render_resultset(request: HttpRequest,
                     query: Query,
                     highlights: Union[QuerySet, List[Highlight]],
                     collapse_at_len: int = None,
                     collapse_at_n_lines: int = None,
                     line_length: int = None,
                     ditto: bool = True,
                     ditto_html: str = '″') -> HttpResponse:
    # Query
    if query is None:
        return render_missing_query(request)
    try:
        with query.get_executed_cursor() as cursor:
            fieldnames = get_fieldnames_from_cursor(cursor)
            rows = cursor.fetchall()
            rowcount = cursor.rowcount
            query.audit(n_records=rowcount)
    except DatabaseError as exception:
        query.audit(failed=True, fail_msg=str(exception))
        return render_bad_query(request, query, exception)
    row_indexes = list(range(len(rows)))
    # We don't need to process all rows before we paginate.
    page = paginate(request, row_indexes)
    start_index = page.start_index() - 1
    end_index = page.end_index() - 1
    display_rows = rows[start_index:end_index + 1]
    # Highlights
    highlight_dict = Highlight.as_ordered_dict(highlights)
    # Table
    element_counter = HtmlElementCounter()
    table_html = resultset_html_table(
        fieldnames=fieldnames,
        rows=display_rows,
        element_counter=element_counter,
        start_index=start_index,
        highlight_dict=highlight_dict,
        collapse_at_len=collapse_at_len,
        collapse_at_n_lines=collapse_at_n_lines,
        line_length=line_length,
        ditto=ditto,
        ditto_html=ditto_html,
    )
    # Render
    context = {
        'table_html': table_html,
        'page': page,
        'rowcount': rowcount,
        'sql': prettify_sql_html(query.get_original_sql()),
        'nav_on_results': True,
        'sql_highlight_css': prettify_sql_css(),
    }
    context.update(query_context(request))
    return render(request, 'query_result.html', context)


def render_resultset_recordwise(request: HttpRequest,
                                query: Query,
                                highlights: Union[QuerySet, List[Highlight]],
                                collapse_at_len: int = None,
                                collapse_at_n_lines: int = None,
                                line_length: int = None) -> HttpResponse:
    # Query
    if query is None:
        return render_missing_query(request)
    try:
        with query.get_executed_cursor() as cursor:
            fieldnames = get_fieldnames_from_cursor(cursor)
            rows = cursor.fetchall()
            rowcount = cursor.rowcount
            query.audit(n_records=rowcount)
    except DatabaseError as exception:
        query.audit(failed=True, fail_msg=str(exception))
        return render_bad_query(request, query, exception)
    row_indexes = list(range(len(rows)))
    # We don't need to process all rows before we paginate.
    page = paginate(request, row_indexes, per_page=1)
    # Highlights
    highlight_dict = Highlight.as_ordered_dict(highlights)
    if rows:
        record_index = page.start_index() - 1
        record = rows[record_index]
        # Table
        element_counter = HtmlElementCounter()
        table_html = '<p><i>Record {}</i></p>\n'.format(page.start_index())
        table_html += single_record_html_table(
            fieldnames=fieldnames,
            record=record,
            element_counter=element_counter,
            highlight_dict=highlight_dict,
            collapse_at_len=collapse_at_len,
            collapse_at_n_lines=collapse_at_n_lines,
            line_length=line_length,
        )
    else:
        table_html = "<b>No rows returned.</b>"
    # Render
    context = {
        'table_html': table_html,
        'page': page,
        'rowcount': rowcount,
        'sql': prettify_sql_html(query.get_original_sql()),
        'nav_on_results_recordwise': True,
        'sql_highlight_css': prettify_sql_css(),
    }
    context.update(query_context(request))
    return render(request, 'query_result.html', context)


def render_missing_query(request: HttpRequest) -> HttpResponse:
    return render(request, 'query_missing.html', query_context(request))


def render_bad_query(request: HttpRequest,
                     query: Query,
                     exception: Exception) -> HttpResponse:
    info = recover_info_from_exception(exception)
    final_sql = info.get('sql', '')
    args = info.get('args', [])
    context = {
        'original_sql': prettify_sql_html(query.get_original_sql()),
        'final_sql': prettify_sql_and_args(final_sql, args),
        'exception': repr(exception),
        'sql_highlight_css': prettify_sql_css(),
    }
    context.update(query_context(request))
    return render(request, 'query_bad.html', context)


def render_bad_query_id(request: HttpRequest, query_id: str) -> HttpResponse:
    context = {'query_id': query_id}
    context.update(query_context(request))
    return render(request, 'query_bad_id.html', context)


# =============================================================================
# Highlights
# =============================================================================

def highlight_edit_select(request: HttpRequest) -> HttpResponse:
    """
    Edit or select highlighting for current query.
    """
    all_highlights = Highlight.objects.filter(user=request.user)\
                                      .order_by('text', 'colour')
    if request.method == 'POST':
        form = AddHighlightForm(request.POST)
        if form.is_valid():
            colour = form.cleaned_data['colour']
            text = form.cleaned_data['text']
            identicals = all_highlights.filter(colour=colour, text=text)
            if identicals:
                identicals[0].activate()
            else:
                highlight = Highlight(colour=colour, text=text,
                                      user=request.user, active=True)
                highlight.save()
            return redirect('highlight')

    values = {'colour': 0}
    form = AddHighlightForm(values)
    active_highlights = all_highlights.filter(active=True)
    highlight_dict = Highlight.as_ordered_dict(active_highlights)
    highlight_descriptions = get_highlight_descriptions(highlight_dict)
    highlights = paginate(request, all_highlights)
    context = {
        'form': form,
        'highlights': highlights,
        'nav_on_highlight': True,
        'N_CSS_HIGHLIGHT_CLASSES': N_CSS_HIGHLIGHT_CLASSES,
        'highlight_descriptions': highlight_descriptions,
        'colourlist': list(range(N_CSS_HIGHLIGHT_CLASSES)),
    }
    context.update(query_context(request))
    return render(request, 'highlight_edit_select.html', context)


def highlight_activate(request: HttpRequest,
                       highlight_id: str) -> HttpResponse:
    validate_blank_form(request)
    highlight = get_object_or_404(Highlight, id=highlight_id)  # type: Highlight
    highlight.activate()
    return redirect('highlight')


def highlight_deactivate(request: HttpRequest,
                         highlight_id: str) -> HttpResponse:
    validate_blank_form(request)
    highlight = get_object_or_404(Highlight, id=highlight_id)  # type: Highlight
    highlight.deactivate()
    return redirect('highlight')


def highlight_delete(request: HttpRequest,
                     highlight_id: str) -> HttpResponse:
    validate_blank_form(request)
    highlight = get_object_or_404(Highlight, id=highlight_id)  # type: Highlight
    highlight.delete()
    return redirect('highlight')


# def render_bad_highlight_id(request, highlight_id):
#     context = {'highlight_id': highlight_id}
#     context.update(query_context(request))
#     return render(request, 'highlight_bad_id.html', context)


def get_highlight_descriptions(
        highlight_dict: Dict[int, List[Highlight]]) -> List[str]:
    """
    Returns a list of length up to N_CSS_HIGHLIGHT_CLASSES of HTML
    elements illustrating the highlights.
    """
    desc = []
    for n in range(N_CSS_HIGHLIGHT_CLASSES):
        if n not in highlight_dict:
            continue
        desc.append(", ".join([highlight_text(h.text, n)
                               for h in highlight_dict[n]]))
    return desc


# =============================================================================
# PID lookup
# =============================================================================
# In general with these database-choosing functions, don't redirect between
# the "generic" and "database-specific" views using POST, because we can't then
# add default values to a new form (since the request.POST object is
# populated and immutable). Use a dbname query parameter as well.
# (That doesn't make it HTTP GET; it makes it HTTP POST with query parameters.)

def pid_rid_lookup(request: HttpRequest,
                   with_db_url_name: str,
                   html_filename: str) -> HttpResponse:
    """
    Common functionality for pidlookup, ridlookup.
    """
    dbinfolist = research_database_info.dbs_with_secret_map
    n = len(dbinfolist)
    if n == 0:
        return generic_error(request, "No databases with lookup map!")
    elif n == 1:
        dbname = dbinfolist[0].name
        return HttpResponseRedirect(
            reverse(with_db_url_name, args=[dbname])
        )
    else:
        form = DatabasePickerForm(request.POST or None, dbinfolist=dbinfolist)
        if form.is_valid():
            dbname = form.cleaned_data['database']
            return HttpResponseRedirect(
                reverse(with_db_url_name, args=[dbname])
            )
        return render(request, html_filename, {'form': form})


def pid_rid_lookup_with_db(
        request: HttpRequest,
        dbname: str,
        form_html_filename: str,
        formclass: Any,
        result_html_filename: str) -> HttpResponse:
    """
    Common functionality for pidlookup_with_db, ridlookup_with_db.
    """
    # There's a bug in the Python 3.5 typing module; we can't use
    # Union[Type[PidLookupForm], Type[RidLookupForm]] yet; we get
    # TypeError: descriptor '__subclasses__' of 'type' object needs an argument
    # ... see https://github.com/python/typing/issues/266
    try:
        dbinfo = research_database_info.get_dbinfo_by_name(dbname)
    except ValueError:
        return generic_error(request,
                             "No research database named {!r}".format(dbname))
    form = formclass(request.POST or None, dbinfo=dbinfo)  # type: Union[PidLookupForm, RidLookupForm]  # noqa
    if form.is_valid():
        pids = form.cleaned_data.get('pids') or []  # type: List[int]
        mpids = form.cleaned_data.get('mpids') or []  # type: List[int]
        trids = form.cleaned_data.get('trids') or []  # type: List[int]
        rids = form.cleaned_data.get('rids') or []  # type: List[str]
        mrids = form.cleaned_data.get('mrids') or []  # type: List[str]
        return render_lookup(request=request, dbinfo=dbinfo,
                             result_html_filename=result_html_filename,
                             pids=pids, mpids=mpids,
                             trids=trids, rids=rids, mrids=mrids)
    context = {
        'db_name': dbinfo.name,
        'db_description': dbinfo.description,
        'form': form,
    }
    return render(request, form_html_filename, context)


@user_passes_test(is_superuser)
def pidlookup(request: HttpRequest) -> HttpResponse:
    """
    Look up PID information from RID information.
    """
    return pid_rid_lookup(request=request,
                          with_db_url_name="pidlookup_with_db",
                          html_filename="pid_lookup_choose_db.html")


@user_passes_test(is_superuser)
def pidlookup_with_db(request: HttpRequest,
                      dbname: str) -> HttpResponse:
    """
    Look up PID information from RID information, for a specific database.
    """
    return pid_rid_lookup_with_db(
        request=request,
        dbname=dbname,
        form_html_filename='pid_lookup_form.html',
        formclass=PidLookupForm,
        result_html_filename='pid_lookup_result.html')


@user_passes_test(is_clinician)
def ridlookup(request: HttpRequest) -> HttpResponse:
    """
    Look up RID information from PID information.
    """
    return pid_rid_lookup(request=request,
                          with_db_url_name="ridlookup_with_db",
                          html_filename="rid_lookup_choose_db.html")


@user_passes_test(is_clinician)
def ridlookup_with_db(request: HttpRequest,
                      dbname: str) -> HttpResponse:
    """
    Look up RID information from PID information, for a specific database.
    """
    return pid_rid_lookup_with_db(
        request=request,
        dbname=dbname,
        form_html_filename='rid_lookup_form.html',
        formclass=RidLookupForm,
        result_html_filename='rid_lookup_result.html')


def render_lookup(request: HttpRequest,
                  dbinfo: SingleResearchDatabase,
                  result_html_filename: str,
                  trids: List[int] = None,
                  rids: List[str] = None,
                  mrids: List[str] = None,
                  pids: List[int] = None,
                  mpids: List[int] = None) -> HttpResponse:
    """
    Shows the output of a PID/RID lookup.
    """
    # if not request.user.superuser:
    #    return HttpResponse('Forbidden', status=403)
    #    # http://stackoverflow.com/questions/3297048/403-forbidden-vs-401-unauthorized-http-responses  # noqa
    trids = [] if trids is None else trids
    rids = [] if rids is None else rids
    mrids = [] if mrids is None else mrids
    pids = [] if pids is None else pids
    mpids = [] if mpids is None else mpids

    assert dbinfo.secret_lookup_db
    lookups = PidLookup.objects.using(dbinfo.secret_lookup_db).filter(
        Q(trid__in=trids) |
        Q(rid__in=rids) |
        Q(mrid__in=mrids) |
        Q(pid__in=pids) |
        Q(mpid__in=mpids)
    ).order_by('pid')
    context = {
        'lookups': lookups,
        'trid_field': dbinfo.trid_field,
        'trid_description': dbinfo.trid_description,
        'rid_field': dbinfo.rid_field,
        'rid_description': dbinfo.rid_description,
        'mrid_field': dbinfo.mrid_field,
        'mrid_description': dbinfo.mrid_description,
        'pid_description': dbinfo.pid_description,
        'mpid_description': dbinfo.mpid_description,
    }
    return render(request, result_html_filename, context)


# =============================================================================
# Research database structure
# =============================================================================

def structure_table_long(request: HttpRequest) -> HttpResponse:
    colinfolist = research_database_info.get_colinfolist()
    rowcount = len(colinfolist)
    context = {
        'paginated': False,
        'colinfolist': colinfolist,
        'rowcount': rowcount,
        'default_database': research_database_info.get_default_database_name(),
        'default_schema': research_database_info.get_default_schema_name(),
        'with_database': research_database_info.uses_database_level(),
    }
    return render(request, 'database_structure.html', context)


def structure_table_paginated(request: HttpRequest) -> HttpResponse:
    colinfolist = research_database_info.get_colinfolist()
    rowcount = len(colinfolist)
    colinfolist = paginate(request, colinfolist)
    context = {
        'paginated': True,
        'colinfolist': colinfolist,
        'rowcount': rowcount,
        'default_database': research_database_info.get_default_database_name(),
        'default_schema': research_database_info.get_default_schema_name(),
        'with_database': research_database_info.uses_database_level(),
    }
    return render(request, 'database_structure.html', context)


@django_cache_function(timeout=None)
# @lru_cache(maxsize=None)
def get_structure_tree_html() -> str:
    table_to_colinfolist = research_database_info.get_colinfolist_by_tables()
    content = ""
    element_counter = HtmlElementCounter()
    grammar = research_database_info.grammar
    for table_id, colinfolist in table_to_colinfolist.items():
        html_table = render_to_string(
            'database_structure_table.html', {
                'colinfolist': colinfolist,
                'default_database': research_database_info.get_default_database_name(),  # noqa
                'default_schema': research_database_info.get_default_schema_name(),  # noqa
                'with_database': research_database_info.uses_database_level()
            })
        cd_button = element_counter.visibility_div_spanbutton()
        cd_content = element_counter.visibility_div_contentdiv(
            contents=html_table)
        content += (
            '<div class="titlecolour">{db_schema}.<b>{table}</b>{button}</div>'
            '{cd}'.format(
                db_schema=table_id.database_schema_part(grammar),
                table=table_id.table_part(grammar),
                button=cd_button,
                cd=cd_content,
            )
        )
    return content


def structure_tree(request: HttpRequest) -> HttpResponse:
    context = {
        'content': get_structure_tree_html(),
        'default_database': research_database_info.get_default_database_name(),
        'default_schema': research_database_info.get_default_schema_name(),
    }
    return render(request, 'database_structure_tree.html', context)


# noinspection PyUnusedLocal
def structure_tsv(request: HttpRequest) -> HttpResponse:
    return file_response(
        research_database_info.get_tsv(),
        content_type=ContentType.TSV,
        filename="structure.tsv"
    )


# noinspection PyUnusedLocal
def structure_excel(request: HttpRequest) -> HttpResponse:
    return file_response(
        research_database_info.get_excel(),
        content_type=ContentType.TSV,
        filename="structure.xlsx"
    )


# =============================================================================
# Local help on structure
# =============================================================================

def local_structure_help(request: HttpRequest) -> HttpResponse:
    if settings.DATABASE_HELP_HTML_FILENAME:
        with open(settings.DATABASE_HELP_HTML_FILENAME, 'r') as infile:
            content = infile.read()
            return HttpResponse(content.encode('utf8'))
    else:
        content = "<p>No local help available.</p>"
        context = {'content': content}
        return render(request, 'local_structure_help.html', context)


# =============================================================================
# SQL helpers
# =============================================================================

def textmatch(column_name: str,
              fragment: str,
              as_fulltext: bool,
              dialect: str = 'mysql') -> str:
    if as_fulltext and dialect == 'mysql':
        return "MATCH({column}) AGAINST ('{fragment}')".format(
            column=column_name, fragment=fragment)
    elif as_fulltext and dialect == 'mssql':
        return "CONTAINS({column}, '{fragment}')".format(
            column=column_name, fragment=fragment)
    else:
        return "{column} LIKE '%{fragment}%'".format(
            column=column_name, fragment=fragment)


def textfinder_sql(patient_id_fieldname: str,
                   fragment: str,
                   min_length: int,
                   use_fulltext_index: bool,
                   include_content: bool,
                   include_datetime: bool,
                   patient_id_value: Union[int, str] = None,
                   extra_fieldname: str = None,
                   extra_value: Union[int, str] = None) -> str:
    """
    Returns SQL to find the text in fragment across all tables that contain the
    field indicated by patient_id_fieldname, where the length of the text field
    is at least min_length.

    use_fulltext_index: use database full-text indexing
    include_content: include the text fields in the output
    patient_id_value: restrict to a single patient

    Will raise ValueError if no tables match the request.
    """
    grammar = research_database_info.grammar
    tables = research_database_info.tables_containing_field(
        patient_id_fieldname)
    if not tables:
        raise ValueError(
            "No tables containing fieldname: {}".format(patient_id_fieldname))
    have_pid_value = patient_id_value is not None and patient_id_value != ''
    if have_pid_value:
        pidclause = "{patient_id_fieldname} = {value}".format(
            patient_id_fieldname=patient_id_fieldname,
            value=escape_sql_string_or_int_literal(patient_id_value)
        )
    else:
        pidclause = ""
    using_extra = extra_fieldname and extra_value is not None
    table_heading = "_table_name"
    contents_colname_heading = "_column_name"
    datetime_heading = "_datetime"

    queries = []  # type: List[str]

    def add_query(table_ident: str,
                  extra_cols: List[str],
                  date_value_select: str,
                  extra_conditions: List[str]) -> None:
        selectcols = []  # type: List[str]
        # Patient ID(s); date
        if using_extra:
            selectcols.append('{lit} AS {ef}'.format(
                lit=escape_sql_string_or_int_literal(extra_value),
                ef=extra_fieldname
            ))
        selectcols.append(patient_id_fieldname)
        if include_datetime:
            selectcols.append("{} AS {}".format(date_value_select,
                                                datetime_heading))
        # +/- table/column/content
        selectcols += extra_cols
        # Build query
        query = (
            "SELECT {cols}"
            "\nFROM {table}".format(cols=", ".join(selectcols),
                                    table=table_ident)
        )
        conditions = []  # type: List[str]
        if have_pid_value:
            conditions.append(pidclause)
        conditions.extend(extra_conditions)
        query += "\nWHERE " + " AND ".join(conditions)
        queries.append(query)

    for table_id in tables:
        columns = research_database_info.text_columns(
            table_id=table_id, min_length=min_length)
        if not columns:
            continue
        table_identifier = table_id.identifier(grammar)
        date_col = research_database_info.get_default_date_column(
            table=table_id)
        if date_col:
            date_identifier = date_col.identifier(grammar)
        else:
            date_identifier = "NULL"

        if include_content:
            # Content required; therefore, one query per text column.
            table_select = "'{}' AS {}".format(
                escape_sql_string_literal(table_identifier),
                table_heading
            )
            for columninfo in columns:
                column_identifier = columninfo.column_id.identifier(grammar)
                contentcol_name_select = "'{}' AS {}".format(
                    column_identifier, contents_colname_heading)
                content_select = "{} AS _content".format(column_identifier)
                add_query(table_ident=table_identifier,
                          extra_cols=[table_select,
                                      contentcol_name_select,
                                      content_select],
                          date_value_select=date_identifier,
                          extra_conditions=[
                              textmatch(
                                  column_name=column_identifier,
                                  fragment=fragment,
                                  as_fulltext=(columninfo.indexed_fulltext and
                                               use_fulltext_index)
                              )
                          ])

        else:
            # Content not required; therefore, one query per table.
            elements = []  # type: List[str]
            for columninfo in columns:
                elements.append(textmatch(
                    column_name=columninfo.column_id.identifier(grammar),
                    fragment=fragment,
                    as_fulltext=(columninfo.indexed_fulltext and
                                 use_fulltext_index)
                ))
            add_query(table_ident=table_identifier,
                      extra_cols=[],
                      date_value_select=date_identifier,
                      extra_conditions=[
                          "(\n    {}\n)".format("\n    OR ".join(elements))
                      ])

    sql = "\nUNION\n".join(queries)
    if sql:
        order_by_cols = []
        if using_extra:
            order_by_cols.append(extra_fieldname)
        order_by_cols.append(patient_id_fieldname)
        if include_datetime:
            order_by_cols.append(datetime_heading + " DESC")
        if include_content:
            order_by_cols.extend([table_heading, contents_colname_heading])
        sql += "\nORDER BY " + ", ".join(order_by_cols)
    return sql


def common_find_text(request: HttpRequest,
                     dbinfo: SingleResearchDatabase,
                     form_class: Type[SQLHelperTextAnywhereForm],
                     default_values: Dict[str, Any],
                     permit_pid_search: bool,
                     html_filename: str) -> HttpResponse:
    """
    Creates SQL to find text anywhere in the database(s) via a UNION query.
    """
    # When you forget about Django forms, go back to:
    # http://www.slideshare.net/pydanny/advanced-django-forms-usage

    # -------------------------------------------------------------------------
    # What may the user use to look up patients?
    # -------------------------------------------------------------------------
    fk_options = []  # type: List[FieldPickerInfo]
    if permit_pid_search:
        fk_options.append(FieldPickerInfo(
            value=dbinfo.pid_pseudo_field,
            description="{}: {}".format(dbinfo.pid_pseudo_field,
                                        dbinfo.pid_description),
            type_=PatientFieldPythonTypes.PID,
            permits_empty_id=False
        ))
        fk_options.append(FieldPickerInfo(
            value=dbinfo.mpid_pseudo_field,
            description="{}: {}".format(
                dbinfo.mpid_pseudo_field, dbinfo.mpid_description),
            type_=PatientFieldPythonTypes.MPID,
            permits_empty_id=False
        ))
        assert dbinfo.secret_lookup_db
        default_values['fkname'] = dbinfo.pid_pseudo_field
    fk_options.append(
        FieldPickerInfo(value=dbinfo.rid_field,
                        description="{}: {}".format(dbinfo.rid_field,
                                                    dbinfo.rid_description),
                        type_=PatientFieldPythonTypes.RID,
                        permits_empty_id=True),
    )
    if dbinfo.secret_lookup_db:
        fk_options.append(
            FieldPickerInfo(value=dbinfo.mrid_field,
                            description="{}: {}".format(
                                dbinfo.mrid_field, dbinfo.mrid_description),
                            type_=PatientFieldPythonTypes.MRID,
                            permits_empty_id=False)
        )

    # We don't want to make too much of the TRID. Let's not offer it as
    # a lookup option. If performance becomes a major problem with these
    # queries, we could always say "if dbinfo.secret_lookup_db, then
    # look up the TRID from the RID (or whatever we're using)".
    #
    # FieldPickerInfo(value=dbinfo.trid_field,
    #                 description="{}: {}".format(dbinfo.trid_field,
    #                                             dbinfo.trid_description),
    #                 type_=PatientFieldPythonTypes.TRID),

    form = form_class(request.POST or default_values, fk_options=fk_options)
    if form.is_valid():
        patient_id_fieldname = form.cleaned_data['fkname']
        pidvalue = form.cleaned_data['patient_id']
        min_length = form.cleaned_data['min_length']

        # ---------------------------------------------------------------------
        # Whare are we going to use internally for the lookup?
        # ---------------------------------------------------------------------
        # For patient lookups, a TRID is quick but not so helpful for
        # clinicians. Use the RID.
        if patient_id_fieldname == dbinfo.pid_pseudo_field:
            lookup = (
                PidLookup.objects.using(dbinfo.secret_lookup_db)
                .filter(pid=pidvalue).first()
            )  # type: PidLookup
            if lookup is None:
                return generic_error(
                    request, "No patient with PID {!r}".format(pidvalue))
            # Replace:
            extra_fieldname = patient_id_fieldname
            extra_value = pidvalue
            patient_id_fieldname = dbinfo.rid_field
            pidvalue = lookup.rid  # string
        elif patient_id_fieldname == dbinfo.mpid_pseudo_field:
            lookup = (
                PidLookup.objects.using(dbinfo.secret_lookup_db)
                .filter(mpid=pidvalue).first()
            )  # type: PidLookup
            if lookup is None:
                return generic_error(
                    request, "No patient with MPID {!r}".format(pidvalue))
            # Replace:
            extra_fieldname = patient_id_fieldname
            extra_value = pidvalue
            patient_id_fieldname = dbinfo.rid_field
            pidvalue = lookup.rid  # string

        elif patient_id_fieldname == dbinfo.mrid_field:
            # Using MRID. This is not stored in each table. Rather than have
            # an absolutely enormous query (SELECT stuff FROM texttable INNER
            # JOIN mridtable ON patient_id_stuff WHERE textttable.contents
            # LIKE something AND mridtable.mrid = ? UNION SELECT morestuff...)
            # let's look up the RID from the MRID. Consequently, we only offer
            # MRID lookup if we have a secret lookup table.
            lookup = (
                PidLookup.objects.using(dbinfo.secret_lookup_db)
                .filter(mrid=pidvalue).first()
            )
            if lookup is None:
                return generic_error(
                    request, "No patient with RID {!r}".format(pidvalue))
            # Replace:
            extra_fieldname = patient_id_fieldname
            extra_value = pidvalue
            patient_id_fieldname = dbinfo.rid_field
            pidvalue = lookup.rid  # string

        else:
            # Using RID directly (or, if we wanted to support it, TRID).
            extra_fieldname = None
            extra_value = None

        # ---------------------------------------------------------------------
        # Generate the query
        # ---------------------------------------------------------------------
        try:
            sql = textfinder_sql(
                patient_id_fieldname=patient_id_fieldname,
                fragment=escape_sql_string_literal(
                    form.cleaned_data['fragment']),
                min_length=min_length,
                use_fulltext_index=form.cleaned_data['use_fulltext_index'],
                include_content=form.cleaned_data['include_content'],
                include_datetime=form.cleaned_data['include_datetime'],
                patient_id_value=pidvalue,
                extra_fieldname=extra_fieldname,
                extra_value=extra_value,
            )
            # This SQL will link across all available research databases
            # where the fieldname conditions are met.
            if not sql:
                raise ValueError(
                    "No fields matched your criteria (text columns of minimum "
                    "length {} in tables containing field {!r})".format(
                        min_length, patient_id_fieldname))
        except ValueError as e:
            return generic_error(request, str(e))

        # ---------------------------------------------------------------------
        # Run, save, or display the query
        # ---------------------------------------------------------------------
        if 'submit_save' in request.POST:
            return query_submit(request, sql, run=False)
        elif 'submit_run' in request.POST:
            return query_submit(request, sql, run=True)
        else:
            return render(request, 'sql_fragment.html', {'sql': sql})

    # -------------------------------------------------------------------------
    # Offer the starting choices
    # -------------------------------------------------------------------------
    return render(request, html_filename, {
        'db_name': dbinfo.name,
        'db_description': dbinfo.description,
        'form': form,
    })


def sqlhelper_text_anywhere(request: HttpRequest) -> HttpResponse:
    """
    Picks a database, then redirects to sqlhelper_text_anywhere_with_db.
    """
    if research_database_info.single_research_db:
        dbname = research_database_info.first_dbinfo.name
        return HttpResponseRedirect(
            reverse('sqlhelper_text_anywhere_with_db', args=[dbname])
        )
    else:
        form = DatabasePickerForm(request.POST or None,
                                  dbinfolist=research_database_info.dbinfolist)
        if form.is_valid():
            dbname = form.cleaned_data['database']
            return HttpResponseRedirect(
                reverse('sqlhelper_text_anywhere_with_db', args=[dbname])
            )
        return render(request, 'sqlhelper_form_text_anywhere_choose_db.html',
                      {'form': form})


def sqlhelper_text_anywhere_with_db(request: HttpRequest,
                                    dbname: str) -> HttpResponse:
    """
    Creates SQL to find text anywhere in the database(s) via a UNION query.
    """
    try:
        dbinfo = research_database_info.get_dbinfo_by_name(dbname)
    except ValueError:
        return generic_error(request,
                             "No research database named {!r}".format(dbname))
    default_values = {
        'fkname': dbinfo.rid_field,
        'min_length': DEFAULT_MIN_TEXT_FIELD_LENGTH,
        'use_fulltext_index': True,
        'include_content': False,
        'include_datetime': False,
    }
    return common_find_text(
        request=request,
        dbinfo=dbinfo,
        form_class=SQLHelperTextAnywhereForm,
        default_values=default_values,
        permit_pid_search=False,
        html_filename='sqlhelper_form_text_anywhere.html')


@user_passes_test(is_clinician)
def all_text_from_pid(request: HttpRequest) -> HttpResponse:
    """
    Picks a database, then redirects to all_text_from_pid_with_db.
    """
    dbinfolist = research_database_info.dbs_with_secret_map
    n = len(dbinfolist)
    if n == 0:
        return generic_error(request, "No databases with lookup map!")
    elif n == 1:
        dbname = dbinfolist[0].name
        return HttpResponseRedirect(
            reverse('all_text_from_pid_with_db', args=[dbname])
        )
    else:
        form = DatabasePickerForm(request.POST or None, dbinfolist=dbinfolist)
        if form.is_valid():
            dbname = form.cleaned_data['database']
            return HttpResponseRedirect(
                reverse('all_text_from_pid_with_db', args=[dbname])
            )
        return render(request,
                      'clinician_form_all_text_from_pid_choose_db.html',
                      {'form': form})


@user_passes_test(is_clinician)
def all_text_from_pid_with_db(request: HttpRequest,
                              dbname: str) -> HttpResponse:
    """
    Clinician view to look up a patient's RID from their PID and display
    text from any field.
    """
    try:
        dbinfo = research_database_info.get_dbinfo_by_name(dbname)
    except ValueError:
        return generic_error(request,
                             "No research database named {!r}".format(dbname))
    default_values = {
        'min_length': DEFAULT_MIN_TEXT_FIELD_LENGTH,
        'use_fulltext_index': True,
        'include_content': True,
        'include_datetime': True,
    }
    return common_find_text(
        request=request,
        dbinfo=dbinfo,
        form_class=ClinicianAllTextFromPidForm,
        default_values=default_values,
        permit_pid_search=True,
        html_filename='clinician_form_all_text_from_pid.html')


# =============================================================================
# Per-patient views: Patient Explorer
# =============================================================================

def pe_build(request: HttpRequest) -> HttpResponse:
    profile = request.user.profile
    default_database = research_database_info.get_default_database_name()
    default_schema = research_database_info.get_default_schema_name()
    with_database = research_database_info.uses_database_level()
    manual_form = None
    form = None

    if not profile.patient_multiquery_scratchpad:
        profile.patient_multiquery_scratchpad = PatientMultiQuery()
    pmq = profile.patient_multiquery_scratchpad

    if request.method == 'POST':
        if 'global_clear_select' in request.POST:
            pmq.clear_output_columns()
            profile.save()

        elif 'global_clear_where' in request.POST:
            pmq.clear_patient_conditions()
            profile.save()

        elif 'global_clear_everything' in request.POST:
            pmq.clear_output_columns()
            pmq.clear_patient_conditions()
            pmq.set_override_query('')
            profile.save()

        elif 'global_save' in request.POST:
            if pmq.ok_to_run:
                return pe_submit(request, pmq, run=False)

        elif 'global_run' in request.POST:
            if pmq.ok_to_run:
                return pe_submit(request, pmq, run=True)

        elif 'global_manual_set' in request.POST:
            manual_form = ManualPeQueryForm(request.POST)
            if manual_form.is_valid():
                sql = manual_form.cleaned_data['sql']
                pmq.set_override_query(sql)
                profile.save()

        elif 'global_manual_clear' in request.POST:
            pmq.set_override_query('')
            profile.save()

        else:
            form = QueryBuilderForm(request.POST, request.FILES)
            if form.is_valid():
                database = (form.cleaned_data['database'] if with_database
                            else '')
                schema = form.cleaned_data['schema']
                table = form.cleaned_data['table']
                column = form.cleaned_data['column']
                column_id = ColumnId(db=database, schema=schema,
                                     table=table, column=column)

                if 'submit_select' in request.POST:
                    pmq.add_output_column(column_id)  # noqa

                elif 'submit_select_star' in request.POST:
                    table_id = column_id.table_id
                    all_column_ids = [
                        c.column_id for c in
                        research_database_info.all_columns(table_id)]
                    for c in all_column_ids:
                        pmq.add_output_column(c)

                elif 'submit_where' in request.POST:
                    datatype = form.cleaned_data['datatype']
                    op = form.cleaned_data['where_op']
                    # Value
                    if op in SQL_OPS_MULTIPLE_VALUES:
                        value = form.file_values_list
                    elif op in SQL_OPS_VALUE_UNNECESSARY:
                        value = None
                    else:
                        value = form.get_cleaned_where_value()
                    # WHERE fragment
                    wherecond = WhereCondition(column_id=column_id,
                                               op=op,
                                               datatype=datatype,
                                               value_or_values=value)
                    pmq.add_patient_condition(wherecond)

                else:
                    raise ValueError("Bad form command!")
                profile.save()

            else:
                # log.critical("not is_valid")
                pass

    manual_query = pmq.manual_patient_id_query

    if form is None:
        form = QueryBuilderForm()
    if manual_form is None:
        manual_form = ManualPeQueryForm({'sql': manual_query})

    starting_values_dict = {
        'database': form.data.get('database', '') if with_database else '',
        'schema': form.data.get('schema', ''),
        'table': form.data.get('table', ''),
        'column': form.data.get('column', ''),
        'op': form.data.get('where_op', ''),
        'date_value': form.data.get('date_value', ''),
        # Impossible to set file_value programmatically. (See querybuilder.js.)
        'float_value': form.data.get('float_value', ''),
        'int_value': form.data.get('int_value', ''),
        'string_value': form.data.get('string_value', ''),
        'offer_where': bool(True),
        'form_errors': "<br>".join("{}: {}".format(k, v)
                                   for k, v in form.errors.items()),
        'default_database': default_database,
        'default_schema': default_schema,
        'with_database': with_database,
    }

    if manual_query:
        pmq_patient_conditions = "<div><i>Overridden by manual query.</i></div>"  # noqa
        pmq_manual_patient_query = prettify_sql_html(
            pmq.manual_patient_id_query)
    else:
        pmq_patient_conditions = pmq.pt_conditions_html
        pmq_manual_patient_query = "<div><i>None</i></div>"
    pmq_final_patient_query = prettify_sql_html(pmq.patient_id_query(
        with_order_by=True))

    warnings = ''
    if not pmq.has_patient_id_query:
        warnings += '<div class="warning">No patient criteria yet</div>'
    if not pmq.has_output_columns:
        warnings += '<div class="warning">No output columns yet</div>'

    context = {
        'nav_on_pe_build': True,
        'pmq_output_columns': pmq.output_cols_html,
        'pmq_patient_conditions': pmq_patient_conditions,
        'pmq_manual_patient_query': pmq_manual_patient_query,
        'pmq_final_patient_query': pmq_final_patient_query,
        'warnings': warnings,
        'database_structure': get_db_structure_json(),
        'starting_values': json.dumps(starting_values_dict),
        'sql_dialect': settings.RESEARCH_DB_DIALECT,
        'dialect_mysql': settings.RESEARCH_DB_DIALECT == SqlaDialectName.MYSQL,
        'dialect_mssql': settings.RESEARCH_DB_DIALECT == SqlaDialectName.MSSQL,
        'sql_highlight_css': prettify_sql_css(),
        'manual_form': manual_form,
    }
    context.update(query_context(request))
    return render(request, 'pe_build.html', context)


def pe_choose(request: HttpRequest) -> HttpResponse:
    all_pes = get_all_pes(request)
    patient_explorers = paginate(request, all_pes)
    context = {
        'nav_on_pe_choose': True,
        'patient_explorers': patient_explorers,
        'sql_highlight_css': prettify_sql_css(),
    }
    context.update(query_context(request))
    return render(request, 'pe_choose.html', context)


def pe_activate(request: HttpRequest, pe_id: str) -> HttpResponse:
    validate_blank_form(request)
    pe = get_object_or_404(PatientExplorer, id=pe_id)  # type: PatientExplorer
    pe.activate()
    return redirect('pe_choose')


def pe_delete(request: HttpRequest, pe_id: str) -> HttpResponse:
    validate_blank_form(request)
    pe = get_object_or_404(PatientExplorer, id=pe_id)  # type: PatientExplorer
    pe.delete_if_permitted()
    return redirect('pe_choose')


def pe_edit(request: HttpRequest, pe_id: str) -> HttpResponse:
    validate_blank_form(request)
    pe = get_object_or_404(PatientExplorer, id=pe_id)  # type: PatientExplorer
    profile = request.user.profile
    profile.patient_multiquery_scratchpad = pe.patient_multiquery
    profile.save()
    return redirect('pe_build')


def pe_results(request: HttpRequest, pe_id: str) -> HttpResponse:
    pe = get_object_or_404(PatientExplorer, id=pe_id)  # type: PatientExplorer
    grammar = research_database_info.grammar
    profile = request.user.profile
    highlights = Highlight.get_active_highlights(request)
    highlight_dict = Highlight.as_ordered_dict(highlights)
    element_counter = HtmlElementCounter()
    patient_id_query_html = prettify_sql_html(pe.get_patient_id_query())
    patients_per_page = get_patients_per_page(request)
    try:
        mrids = pe.get_patient_mrids()
        page = paginate(request, mrids, per_page=patients_per_page)
        active_mrids = list(page)
        results = []
        if active_mrids:
            for table_id, sql, args in pe.all_queries(mrids=active_mrids):
                with pe.get_executed_cursor(sql, args) as cursor:
                    fieldnames = get_fieldnames_from_cursor(cursor)
                    rows = cursor.fetchall()
                    table_html = resultset_html_table(
                        fieldnames=fieldnames,
                        rows=rows,
                        element_counter=element_counter,
                        highlight_dict=highlight_dict,
                        collapse_at_len=profile.collapse_at_len,
                        collapse_at_n_lines=profile.collapse_at_n_lines,
                        line_length=profile.line_length,
                    )
                    query_html = element_counter.visibility_div_with_divbutton(
                        contents=prettify_sql_and_args(sql, args),
                        title_html="SQL")
                    results.append({
                        'tablename': table_id.identifier(grammar),
                        'table_html': table_html,
                        'query_html': query_html,
                    })
        context = {
            'nav_on_pe_results': True,
            'results': results,
            'page': page,
            'rowcount': len(mrids),
            'patient_id_query_html': patient_id_query_html,
            'patients_per_page': patients_per_page,
            'sql_highlight_css': prettify_sql_css(),
        }
        context.update(query_context(request))
        return render(request, 'pe_result.html', context)

    except DatabaseError as exception:
        return render_bad_pe(request, pe, exception)


def render_missing_pe(request: HttpRequest) -> HttpResponse:
    return render(request, 'pe_missing.html', query_context(request))


# noinspection PyUnusedLocal
def render_bad_pe(request: HttpRequest,
                  pe: PatientExplorer,
                  exception: Exception) -> HttpResponse:
    info = recover_info_from_exception(exception)
    final_sql = info.get('sql', '')
    args = info.get('args', [])
    context = {
        'exception': repr(exception),
        'query': prettify_sql_and_args(final_sql, args),
        'sql_highlight_css': prettify_sql_css(),
    }
    context.update(query_context(request))
    return render(request, 'pe_bad.html', context)


# def render_bad_pe_id(request: HttpRequest, pe_id: int) -> HttpResponse:
#     context = {'pe_id': pe_id}
#     context.update(query_context(request))
#     return render(request, 'pe_bad_id.html', context)


def get_all_pes(request: HttpRequest) -> QuerySet:
    return PatientExplorer.objects\
        .filter(user=request.user, deleted=False)\
        .order_by('-active', '-created')


def get_identical_pes(request: HttpRequest,
                      pmq: PatientMultiQuery) -> List[PatientMultiQuery]:
    all_pes = get_all_pes(request)

    # identical_pes = all_pes.filter(patient_multiquery=pmq)
    #
    # ... this works, but does so by converting the parameter (pmq) to its
    # JSON representation, presumably via JsonClassField.get_prep_value().
    # Accordingly, we can predict problems under SQL Server with very long
    # strings; see the problem in query_submit().
    # So, we should similarly hash:
    identical_pes = all_pes.filter(pmq_hash=pmq.hash64)
    # Beware: Python's hash() function will downconvert to 32 bits on 32-bit
    # machines; use pmq.hash64() directly, not hash(pmq).

    # Double-check in Python in case of hash collision:
    return [pe for pe in identical_pes if pe.patient_multiquery == pmq]


def pe_submit(request: HttpRequest,
              pmq: PatientMultiQuery,
              run: bool = False) -> HttpResponse:
    identical_pes = get_identical_pes(request, pmq)
    if identical_pes:
        identical_pes[0].activate()
        pe_id = identical_pes[0].id
    else:
        pe = PatientExplorer(patient_multiquery=pmq,
                             user=request.user,
                             active=True)
        pe.save()
        pe_id = pe.id
    # log.critical(pprint.pformat(connection.queries))  # show all queries
    # redirect to a new URL:
    if run:
        return redirect('pe_results', pe_id)
    else:
        return redirect('pe_choose')


def pe_tsv_zip(request: HttpRequest, pe_id: str) -> HttpResponse:
    # http://stackoverflow.com/questions/12881294/django-create-a-zip-of-multiple-files-and-make-it-downloadable  # noqa
    pe = get_object_or_404(PatientExplorer, id=pe_id)  # type: PatientExplorer
    try:
        return file_response(
            pe.get_zipped_tsv_binary(),
            content_type=ContentType.ZIP,
            filename="crate_pe_{num}_{datetime}.zip".format(
                num=pe.id,
                datetime=datetime_iso_for_filename(),
            )
        )
    except DatabaseError as exception:
        return render_bad_pe(request, pe, exception)


def pe_excel(request: HttpRequest, pe_id: str) -> HttpResponse:
    pe = get_object_or_404(PatientExplorer, id=pe_id)  # type: PatientExplorer
    try:
        return file_response(
            pe.get_xlsx_binary(),
            content_type=ContentType.XLSX,
            filename="crate_pe_{num}_{datetime}.xlsx".format(
                num=pe.id,
                datetime=datetime_iso_for_filename(),
            )
        )
    except DatabaseError as exception:
        return render_bad_pe(request, pe, exception)


def pe_data_finder_results(request: HttpRequest, pe_id: str) -> HttpResponse:
    pe = get_object_or_404(PatientExplorer, id=pe_id)  # type: PatientExplorer
    profile = request.user.profile
    patients_per_page = get_patients_per_page(request)
    element_counter = HtmlElementCounter()
    patient_id_query_html = prettify_sql_html(pe.get_patient_id_query())
    # If this query is done as a UNION, it's massive, e.g. ~410 characters
    # * number of tables (e.g. 1448 in one RiO database), for 0.5 Mb of query.
    # So do it more sensibly:
    try:
        mrids = pe.get_patient_mrids()
        page = paginate(request, mrids, per_page=patients_per_page)
        active_mrids = list(page)
        results_table_html = ''
        query_html = ''
        if active_mrids:
            fieldnames = []
            rows = []
            for table_identifier, sql, args in \
                    pe.patient_multiquery.gen_data_finder_queries(
                        mrids=active_mrids):
                with pe.get_executed_cursor(sql, args) as cursor:
                    if not fieldnames:
                        fieldnames = get_fieldnames_from_cursor(cursor)
                    rows = cursor.fetchall()
                    query_html += element_counter.visibility_div_with_divbutton(  # noqa
                        contents=prettify_sql_and_args(sql, args),
                        title_html="SQL for " + table_identifier)
            results_table_html = resultset_html_table(
                fieldnames=fieldnames,
                rows=rows,
                element_counter=element_counter,
                collapse_at_len=profile.collapse_at_len,
                collapse_at_n_lines=profile.collapse_at_n_lines,
                line_length=profile.line_length,
                no_ditto_cols=[2, 3, 4],
                null=''
            )
        context = {
            'nav_on_pe_df_results': True,
            'some_patients': len(active_mrids) > 0,
            'results_table_html': results_table_html,
            'query_html': query_html,
            'page': page,
            'rowcount': len(mrids),
            'patient_id_query_html': patient_id_query_html,
            'patients_per_page': patients_per_page,
            'sql_highlight_css': prettify_sql_css(),
        }
        context.update(query_context(request))
        return render(request, 'pe_df_result.html', context)

    except DatabaseError as exception:
        return render_bad_pe(request, pe, exception)


def pe_data_finder_excel(request: HttpRequest, pe_id: str) -> HttpResponse:
    pe = get_object_or_404(PatientExplorer, id=pe_id)  # type: PatientExplorer
    try:
        return file_response(
            pe.data_finder_excel,
            content_type=ContentType.XLSX,
            filename="crate_pe_df_{num}_{datetime}.xlsx".format(
                num=pe.id,
                datetime=datetime_iso_for_filename(),
            )
        )
    except DatabaseError as exception:
        return render_bad_pe(request, pe, exception)


def pe_monster_results(request: HttpRequest, pe_id: str) -> HttpResponse:
    pe = get_object_or_404(PatientExplorer, id=pe_id)  # type: PatientExplorer
    grammar = research_database_info.grammar
    profile = request.user.profile
    highlights = Highlight.get_active_highlights(request)
    highlight_dict = Highlight.as_ordered_dict(highlights)
    element_counter = HtmlElementCounter()
    patient_id_query_html = prettify_sql_html(pe.get_patient_id_query())
    patients_per_page = get_patients_per_page(request)
    try:
        rids = pe.get_patient_mrids()
        page = paginate(request, rids, per_page=patients_per_page)
        active_rids = list(page)
        results = []
        pmq = pe.patient_multiquery
        if active_rids:
            for table_id, sql, args in pmq.gen_monster_queries(mrids=active_rids):  # noqa
                with pe.get_executed_cursor(sql, args) as cursor:
                    fieldnames = get_fieldnames_from_cursor(cursor)
                    rows = cursor.fetchall()
                    if rows:
                        table_html = resultset_html_table(
                            fieldnames=fieldnames,
                            rows=rows,
                            element_counter=element_counter,
                            highlight_dict=highlight_dict,
                            collapse_at_len=profile.collapse_at_len,
                            collapse_at_n_lines=profile.collapse_at_n_lines,
                            line_length=profile.line_length,
                        )
                    else:
                        table_html = "<div><i>No data</i></div>"
                    query_html = element_counter.visibility_div_with_divbutton(
                        contents=prettify_sql_and_args(sql, args),
                        title_html="SQL")
                    results.append({
                        'tablename': table_id.identifier(grammar),
                        'table_html': table_html,
                        'query_html': query_html,
                    })
        context = {
            'nav_on_pe_monster_results': True,
            'results': results,
            'page': page,
            'rowcount': len(rids),
            'patient_id_query_html': patient_id_query_html,
            'patients_per_page': patients_per_page,
            'sql_highlight_css': prettify_sql_css(),
        }
        context.update(query_context(request))
        return render(request, 'pe_monster_result.html', context)

    except DatabaseError as exception:
        return render_bad_pe(request, pe, exception)


def pe_table_browser(request: HttpRequest, pe_id: str) -> HttpResponse:
    pe = get_object_or_404(PatientExplorer, id=pe_id)  # type: PatientExplorer
    tables = research_database_info.get_tables()
    with_database = research_database_info.uses_database_level()
    try:
        context = {
            'nav_on_pe_table_browser': True,
            'pe_id': pe_id,
            'tables': tables,
            'with_database': with_database,
        }
        context.update(query_context(request))
        return render(request, 'pe_table_browser.html', context)

    except DatabaseError as exception:
        return render_bad_pe(request, pe, exception)


def pe_one_table(request: HttpRequest, pe_id: str,
                 schema: str, table: str, db: str = '') -> HttpResponse:
    pe = get_object_or_404(PatientExplorer, id=pe_id)  # type: PatientExplorer
    table_id = TableId(db=db, schema=schema, table=table)
    grammar = research_database_info.grammar
    highlights = Highlight.get_active_highlights(request)
    highlight_dict = Highlight.as_ordered_dict(highlights)
    element_counter = HtmlElementCounter()
    profile = request.user.profile
    patients_per_page = get_patients_per_page(request)
    try:
        mrids = pe.get_patient_mrids()
        page = paginate(request, mrids, per_page=patients_per_page)
        active_mrids = list(page)
        table_html = "<div><i>No data</i></div>"
        sql = ""
        args = []
        rowcount = 0
        if active_mrids:
            mrid_column = research_database_info.get_mrid_column_from_table(
                table_id)
            where_clause = "{mrid} IN ({in_clause})".format(
                mrid=mrid_column.identifier(grammar),
                in_clause=",".join(["?"] * len(active_mrids)),
            )  # ... see notes for translate_sql_qmark_to_percent()
            args = active_mrids
            sql = add_to_select(
                sql='',
                select_elements=[SelectElement(
                    raw_select='*',
                    from_table_for_raw_select=table_id
                )],
                grammar=grammar,
                where_conditions=[WhereCondition(
                    raw_sql=where_clause,
                    from_table_for_raw_sql=mrid_column.table_id
                )],
                magic_join=True,
                formatted=True)
            with pe.get_executed_cursor(sql, args) as cursor:
                fieldnames = get_fieldnames_from_cursor(cursor)
                rows = cursor.fetchall()
                rowcount = cursor.rowcount
                if rows:
                    table_html = resultset_html_table(
                        fieldnames=fieldnames,
                        rows=rows,
                        element_counter=element_counter,
                        highlight_dict=highlight_dict,
                        collapse_at_len=profile.collapse_at_len,
                        collapse_at_n_lines=profile.collapse_at_n_lines,
                        line_length=profile.line_length,
                    )
        # Render
        context = {
            'table_html': table_html,
            'page': page,
            'rowcount': rowcount,
            'sql': prettify_sql_and_args(sql=sql, args=args),
            'sql_highlight_css': prettify_sql_css(),
        }
        context.update(query_context(request))
        return render(request, 'query_result.html', context)

    except DatabaseError as exception:
        return render_bad_pe(request, pe, exception)
