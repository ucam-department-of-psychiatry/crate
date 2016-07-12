#!/usr/bin/env python3
# crate_anon/crateweb/research/views.py

from functools import lru_cache
import json
import logging

from django import forms
from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import (
    ObjectDoesNotExist,
    ValidationError,
)
# from django.core.urlresolvers import reverse
from django.db import DatabaseError
from django.db.models import Q
from django.http import HttpResponse
# from django.middleware import csrf
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
# from django.views.decorators.csrf import csrf_exempt
from pyparsing import ParseException
# from sqlalchemy.sql import sqltypes

from crate_anon.crateweb.core.dbfunc import (
    dictlist_to_tsv,
    escape_sql_string_literal,
    get_fieldnames_from_cursor,
)
from crate_anon.crateweb.core.utils import is_superuser, paginate
from crate_anon.crateweb.extra.serve import file_response
from crate_anon.crateweb.research.forms import (
    AddHighlightForm,
    AddQueryForm,
    PidLookupForm,
    QueryBuilderForm,
    SQLHelperTextAnywhereForm,
)
from crate_anon.crateweb.research.html_functions import (
    collapsible_div_contentdiv,
    collapsible_div_spanbutton,
    highlight_text,
    make_result_element,
    make_collapsible_query,
    N_CSS_HIGHLIGHT_CLASSES,
)
from crate_anon.crateweb.research.models import (
    ColumnInfo,
    get_default_schema,
    get_researchdb_schemas,
    is_schema_eligible_for_query_builder,
    get_schema_trid_field,
    get_schema_rid_field,
    Highlight,
    PidLookup,
    Query,
    research_database_info,
)
from crate_anon.crateweb.research.sql_writer import (
    add_to_select,
    sql_date_literal,
    sql_string_literal,
    toggle_distinct,
)

log = logging.getLogger(__name__)


# =============================================================================
# Helper functions
# =============================================================================

def validate_blank_form(request):
    """
    Checks that the request is (a) a POST request, and (b) passes CRSF
    validation.
    """
    if request.method != "POST":
        raise ValidationError("Use HTTP POST, not HTTP GET or other methods")
    form = forms.Form(request.POST)
    if not form.is_valid():  # checks CSRF
        raise ValidationError("Form failed validation")


def query_context(request):
    query_id = Query.get_active_query_id_or_none(request)
    return {
        'query_selected': query_id is not None,
        'current_query_id': query_id,
    }
    # Try to minimize SQL here, as these calls will be used for EVERY
    # request.
    # This problem can be circumvented with a per-request cache; see
    # http://stackoverflow.com/questions/3151469/per-request-cache-in-django


# =============================================================================
# Queries
# =============================================================================

@lru_cache(maxsize=None)
def get_db_structure_json():
    colinfolist = research_database_info.get_colinfolist()
    info = []
    for schema in get_researchdb_schemas():  # preserve order
        if not is_schema_eligible_for_query_builder(schema):
            continue
        schema_cil = [x for x in colinfolist if x.table_schema == schema]
        trid_field = get_schema_trid_field(schema)
        rid_field = get_schema_rid_field(schema)
        table_info = []
        for table in sorted(set(x.table_name for x in schema_cil)):
            table_cil = [x for x in schema_cil if x.table_name == table]
            if not any(x for x in table_cil
                       if x.column_name == trid_field):
                # This table doesn't contain a TRID, so we will skip it.
                continue
            if not any(x for x in table_cil
                       if x.column_name == rid_field):
                # This table doesn't contain a RID, so we will skip it.
                continue
            column_info = []
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
        if table_info:
            info.append({
                'schema': schema,
                'tables': table_info,
            })
    return json.dumps(info)


def build_query(request):
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
    #   mostly on the client side. Might look better, too. ***

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
    default_schema = get_default_schema()
    form = None
    if request.method == 'POST':
        try:
            if 'global_clear' in request.POST:
                profile.sql_scratchpad = ''
                profile.save()
            elif 'global_toggle_distinct' in request.POST:
                profile.sql_scratchpad = toggle_distinct(profile.sql_scratchpad)
                profile.save()
            elif 'global_save' in request.POST:
                return submit_query(request, profile.sql_scratchpad, run=False)
            elif 'global_run' in request.POST:
                return submit_query(request, profile.sql_scratchpad, run=True)
            else:
                form = QueryBuilderForm(request.POST, request.FILES)
                if form.is_valid():
                    # log.critical("is_valid")
                    schema = form.cleaned_data['schema']
                    table = form.cleaned_data['table']
                    if schema == default_schema:
                        full_table = table
                    else:
                        full_table = "{}.{}".format(schema, table)
                    column = form.cleaned_data['column']
                    autojoin_field = get_schema_trid_field(schema)
                    if 'submit_select' in request.POST:
                        profile.sql_scratchpad = add_to_select(
                            profile.sql_scratchpad,
                            # SELECT bits
                            select_db=schema,
                            select_table=table,
                            select_column=column,
                            # JOIN bits
                            inner_join_to_first_on_keyfield=autojoin_field,
                        )
                    elif 'submit_where' in request.POST:
                        datatype = form.cleaned_data['datatype']
                        op = form.cleaned_data['where_op']
                        # Value
                        if op in QueryBuilderForm.FILE_REQUIRED:
                            value = form.file_values_list
                        elif op in QueryBuilderForm.VALUE_UNNECESSARY:
                            value = None
                        else:
                            value = form.get_cleaned_where_value()
                            if datatype in ColumnInfo.STRING_TYPES:
                                value = sql_string_literal(value)
                            elif datatype == ColumnInfo.DATATYPE_DATE:
                                value = sql_date_literal(value)
                        # WHERE fragment
                        if op == 'MATCH':
                            where_expression = (
                                "MATCH ({col}) AGAINST ({val})".format(
                                    col=column, val=value))
                        elif op in QueryBuilderForm.VALUE_UNNECESSARY:
                            where_expression = "{tab}.{col} {op}".format(
                                tab=full_table, col=column, op=op)
                        else:
                            where_expression = "{tab}.{col} {op} {val}".format(
                                tab=full_table, col=column, op=op, val=value)
                        profile.sql_scratchpad = add_to_select(
                            profile.sql_scratchpad,
                            # WHERE bits
                            where_type="AND",
                            where_expression=where_expression,
                            where_db=schema,
                            where_table=table,
                            # JOIN bits
                            inner_join_to_first_on_keyfield=autojoin_field,
                        )
                    else:
                        raise ValueError("Bad form command!")
                    profile.save()
                else:
                    # log.critical("not is_valid")
                    pass
        except ParseException as e:
            parse_error = str(e)
    if form is None:
        form = QueryBuilderForm()

    starting_values_dict = {
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
        'default_schema': default_schema,
    }
    context = {
        'nav_on_querybuilder': True,
        'sql': profile.sql_scratchpad,
        'parse_error': parse_error,
        'database_structure': get_db_structure_json(),
        'starting_values': json.dumps(starting_values_dict),
    }
    context.update(query_context(request))
    return render(request, 'build_query.html', context)


def get_all_queries(request):
    return Query.objects.filter(user=request.user, deleted=False)\
                        .order_by('-active', '-created')


def submit_query(request, sql, run=False):
    """
    Ancillary function to add a query, and redirect to the editing or
    run page.
    """
    all_queries = get_all_queries(request)
    identical_queries = all_queries.filter(sql=sql)
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


def edit_select_query(request):
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
                return submit_query(request, sql, run)
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
    for i, q in enumerate(queries):
        q.formatted_query_safe = make_collapsible_query(
            q.get_original_sql(),
            i,
            collapse_at_n_lines=profile.collapse_at_n_lines,
        )
    context = {
        'form': form,
        'queries': queries,
        'nav_on_query': True,
    }
    context.update(query_context(request))
    return render(request, 'edit_select_query.html', context)


def activate_query(request, query_id):
    validate_blank_form(request)
    query = get_object_or_404(Query, id=query_id)
    query.activate()
    return redirect('query')


def delete_query(request, query_id):
    validate_blank_form(request)
    query = get_object_or_404(Query, id=query_id)
    query.delete_if_permitted()
    return redirect('query')


def edit_select_highlight(request):
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
    query = Query.get_active_query_or_none(request)
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
        'sql': query.get_original_sql() if query else '',
    }
    context.update(query_context(request))
    return render(request, 'edit_select_highlight.html', context)


def activate_highlight(request, highlight_id):
    validate_blank_form(request)
    highlight = get_object_or_404(Highlight, id=highlight_id)
    highlight.activate()
    return redirect('highlight')


def deactivate_highlight(request, highlight_id):
    validate_blank_form(request)
    highlight = get_object_or_404(Highlight, id=highlight_id)
    highlight.deactivate()
    return redirect('highlight')


def delete_highlight(request, highlight_id):
    validate_blank_form(request)
    highlight = get_object_or_404(Highlight, id=highlight_id)
    highlight.delete()
    return redirect('highlight')


def no_query_selected(request):
    return render(request, 'no_query_selected.html', query_context(request))


def count(request, query_id):
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


def count_current(request):
    """
    View COUNT(*) from current query.
    """
    query = Query.get_active_query_or_none(request)
    if query is None:
        return no_query_selected(request)
    return render_resultcount(request, query)


def results(request, query_id):
    """
    View results of chosen query.
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


def tsv(request):
    """
    Download TSV of current query.
    """
    query = Query.get_active_query_or_none(request)
    return render_tsv(request, query)


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


def pidlookup(request):
    """
    Look up PID information from RID information.
    """
    form = PidLookupForm(request.POST or None)
    if form.is_valid():
        trids = form.cleaned_data['trids']
        rids = form.cleaned_data['rids']
        mrids = form.cleaned_data['mrids']
        return render_lookup(request, trids=trids, rids=rids, mrids=mrids)
    return render(request, 'pid_lookup_form.html', {'form': form})


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


def render_resultcount(request, query):
    """
    Displays the number of rows that a given query will fetch.
    """
    if query is None:
        return render_missing_query(request)
    try:
        cursor = query.get_executed_cursor()
    # See above re exception classes
    except DatabaseError as exception:
        query.audit(count_only=True, failed=True,
                    fail_msg=str(exception))
        return render_bad_query(request, query, exception)
    rowcount = cursor.rowcount
    query.audit(count_only=True, n_records=rowcount)
    context = {
        'rowcount': rowcount,
        'sql': query.get_original_sql(),
        'nav_on_count': True,
    }
    context.update(query_context(request))
    return render(request, 'query_count.html', context)


def get_highlight_descriptions(highlight_dict):
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


def render_resultset(request, query, highlights,
                     collapse_at_len=None, collapse_at_n_lines=None,
                     line_length=None, ditto=True, ditto_html='″'):
    # Query
    if query is None:
        return render_missing_query(request)
    try:
        cursor = query.get_executed_cursor()
    except DatabaseError as exception:
        query.audit(failed=True, fail_msg=str(exception))
        return render_bad_query(request, query, exception)
    rowcount = cursor.rowcount
    query.audit(n_records=rowcount)
    fieldnames = get_fieldnames_from_cursor(cursor)
    rows = cursor.fetchall()
    row_indexes = list(range(len(rows)))
    # We don't need to process all rows before we paginate.
    page = paginate(request, row_indexes)
    start_index = page.start_index() - 1
    end_index = page.end_index() - 1
    display_rows = rows[start_index:end_index + 1]
    # Highlights
    highlight_dict = Highlight.as_ordered_dict(highlights)
    highlight_descriptions = get_highlight_descriptions(highlight_dict)
    # Table
    ditto_cell = '    <td class="queryresult ditto">{}</td>\n'.format(
        ditto_html)
    elementnum = 0  # used for collapsing divs/buttons
    table_html = '<table>\n'
    table_html += '  <tr>\n'
    table_html += '    <th><i>#</i></th>\n'
    for field in fieldnames:
        table_html += '    <th>{}</th>\n'.format(field)
    table_html += '  </tr>\n'
    for row_index, row in enumerate(display_rows):
        table_html += '  <tr class="{}">\n'.format(
            "stripy_even" if row_index % 2 == 0 else "stripy_odd"
        )
        # Row number
        table_html += '    <td><b><i>{}</i></b></td>\n'.format(
            row_index + start_index + 1)
        # Values
        for col_index, value in enumerate(row):
            if (row_index > 0 and ditto and
                    value == display_rows[row_index - 1][col_index]):
                table_html += ditto_cell
            else:
                table_html += (
                    '    <td class="queryresult">{}</td>\n'.format(
                        make_result_element(
                            value,
                            elementnum,
                            highlight_dict=highlight_dict,
                            collapse_at_len=collapse_at_len,
                            collapse_at_n_lines=collapse_at_n_lines,
                            line_length=line_length
                        )
                    )
                )
            elementnum += 1
        table_html += '  </tr>\n'
    table_html += '</table>\n'
    # Render
    context = {
        'fieldnames': fieldnames,
        'highlight_descriptions': highlight_descriptions,
        'table_html': table_html,
        'page': page,
        'rowcount': rowcount,
        'sql': query.get_original_sql(),
        'nav_on_results': True,
    }
    context.update(query_context(request))
    return render(request, 'query_result.html', context)


def tsv_response(data, filename="download.tsv"):
    # http://stackoverflow.com/questions/264256/what-is-the-best-mime-type-and-extension-to-use-when-exporting-tab-delimited  # noqa
    # http://www.iana.org/assignments/media-types/text/tab-separated-values
    return file_response(data, content_type='text/csv', filename=filename)


def render_tsv(request, query):
    if query is None:
        return render_missing_query(request)
    try:
        tsv_result = query.make_tsv()
    except DatabaseError as exception:
        return render_bad_query(request, query, exception)
    return tsv_response(tsv_result, filename="results.tsv")


def render_missing_query(request):
    return render(request, 'query_missing.html', query_context(request))


def render_bad_query(request, query, exception):
    (final_sql, args) = query.get_sql_args_for_mysql()
    context = {
        'original_sql': query.get_original_sql(),
        'final_sql': final_sql,
        'args': str(args),
        'exception': str(exception),
    }
    context.update(query_context(request))
    return render(request, 'query_bad.html', context)


def render_bad_query_id(request, query_id):
    context = {'query_id': query_id}
    context.update(query_context(request))
    return render(request, 'bad_query_id.html', context)


# def render_bad_highlight_id(request, highlight_id):
#     context = {'highlight_id': highlight_id}
#     context.update(query_context(request))
#     return render(request, 'bad_highlight_id.html', context)


@user_passes_test(is_superuser)
def render_lookup(request,
                  trids=None, rids=None, mrids=None,
                  pids=None, mpids=None):
    # if not request.user.superuser:
    #    return HttpResponse('Forbidden', status=403)
    #    # http://stackoverflow.com/questions/3297048/403-forbidden-vs-401-unauthorized-http-responses  # noqa
    trids = [] if trids is None else trids
    rids = [] if rids is None else rids
    mrids = [] if mrids is None else mrids
    pids = [] if pids is None else pids
    mpids = [] if mpids is None else mpids
    lookups = PidLookup.objects.filter(
        Q(trid__in=trids) |
        Q(rid__in=rids) |
        Q(mrid__in=mrids) |
        Q(pid__in=pids) |
        Q(mpid__in=mpids)
    ).order_by('pid')
    context = {
        'lookups': lookups,
        'SECRET_MAP': settings.SECRET_MAP,
    }
    return render(request, 'pid_lookup_result.html', context)


# =============================================================================
# Research database structure
# =============================================================================

def structure_table_long(request):
    infodictlist = research_database_info.get_infodictlist()
    rowcount = len(infodictlist)
    context = {
        'paginated': False,
        'infodictlist': infodictlist,
        'rowcount': rowcount,
        'default_schema': get_default_schema(),
    }
    return render(request, 'database_structure.html', context)


def structure_table_paginated(request):
    infodictlist = research_database_info.get_infodictlist()
    rowcount = len(infodictlist)
    infodictlist = paginate(request, infodictlist)
    context = {
        'paginated': True,
        'infodictlist': infodictlist,
        'rowcount': rowcount,
        'default_schema': get_default_schema(),
    }
    return render(request, 'database_structure.html', context)


@lru_cache(maxsize=None)
def get_structure_tree_html():
    schema_table_idl = research_database_info.get_infodictlist_by_tables()
    content = ""
    for i, (schema, tablename, infodictlist) in enumerate(schema_table_idl):
        html_table = render_to_string('database_structure_table.html',
                                      {'infodictlist': infodictlist})
        tag = str(i)
        cd_button = collapsible_div_spanbutton(tag)
        cd_content = collapsible_div_contentdiv(tag, html_table)
        content += (
            '<div class="titlecolour">{button} {schema}.<b>{table}</b></div>'
            '{cd}'.format(
                schema=schema,
                table=tablename,
                button=cd_button,
                cd=cd_content,
            )
        )
    return content


def structure_tree(request):
    context = {
        'content': get_structure_tree_html(),
        'default_schema': get_default_schema(),
    }
    return render(request, 'database_structure_tree.html', context)


# noinspection PyUnusedLocal
def structure_tsv(request):
    infodictlist = research_database_info.get_infodictlist()
    tsv_result = dictlist_to_tsv(infodictlist)
    return tsv_response(tsv_result, filename="structure.tsv")


# =============================================================================
# SQL helpers
# =============================================================================

def textmatch(column_name, fragment, as_fulltext, dialect='mysql'):
    if as_fulltext and dialect == 'mysql':
        return "MATCH({column}) AGAINST ('{fragment}')".format(
            column=column_name, fragment=fragment)
    else:
        return "{column} LIKE '%{fragment}%'".format(
            column=column_name, fragment=fragment)


def sqlhelper_text_anywhere(request):
    # When you forget, go back to:
    # http://www.slideshare.net/pydanny/advanced-django-forms-usage
    default_values = {
        'fkname': settings.SECRET_MAP['RID_FIELD'],
        'min_length': 50,
        'use_fulltext_index': True,
        'include_content': False,
    }
    form = SQLHelperTextAnywhereForm(request.POST or default_values)
    if form.is_valid():
        fkname = form.cleaned_data['fkname']
        min_length = form.cleaned_data['min_length']
        use_fulltext_index = form.cleaned_data['use_fulltext_index']
        include_content = form.cleaned_data['include_content']
        fragment = escape_sql_string_literal(form.cleaned_data['fragment'])
        table_queries = []
        tables = research_database_info.tables_containing_field(fkname)
        if not tables:
            return HttpResponse(
                "No tables containing fieldname: {}".format(fkname))
        if include_content:
            queries = []
            for (schema, table) in tables:
                columns = research_database_info.text_columns(
                    schema, table, min_length)
                for column_name, indexed_fulltext in columns:
                    query = (
                        "SELECT {fkname} AS patient_id,"
                        "\n    '{table_literal}' AS table_name,"
                        "\n    '{col_literal}' AS column_name,"
                        "\n    {column_name} AS content"
                        "\nFROM {schema}.{table}"
                        "\nWHERE {condition}".format(
                            fkname=fkname,
                            table_literal=escape_sql_string_literal(table),
                            col_literal=escape_sql_string_literal(column_name),
                            column_name=column_name,
                            schema=schema,
                            table=table,
                            condition=textmatch(
                                column_name,
                                fragment,
                                indexed_fulltext and use_fulltext_index
                            ),
                        )
                    )
                    queries.append(query)
            sql = "\nUNION\n".join(queries)
            sql += "\nORDER BY patient_id".format(fkname)
        else:
            for (schema, table) in tables:
                elements = []
                columns = research_database_info.text_columns(
                    schema, table, min_length)
                if not columns:
                    continue
                for column_name, indexed_fulltext in columns:
                    element = textmatch(
                        column_name,
                        fragment,
                        indexed_fulltext and use_fulltext_index)
                    elements.append(element)
                table_query = (
                    "SELECT {fkname} FROM {schema}.{table} WHERE ("
                    "\n    {elements}\n)".format(
                        fkname=fkname,
                        schema=schema,
                        table=table,
                        elements="\n    OR ".join(elements),
                    )
                )
                table_queries.append(table_query)
            sql = "\nUNION\n".join(table_queries)
            if sql:
                sql += "\nORDER BY {}".format(fkname)
        if 'submit_save' in request.POST:
            return submit_query(request, sql, run=False)
        elif 'submit_run' in request.POST:
            return submit_query(request, sql, run=True)
        else:
            return render(request, 'sql_fragment.html', {'sql': sql})

    return render(request, 'sqlhelper_form_text_anywhere.html', {'form': form})
