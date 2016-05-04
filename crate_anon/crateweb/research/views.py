#!/usr/bin/env python3
# research/views.py

import logging

from django import forms
from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import (
    ObjectDoesNotExist,
    ValidationError,
)
from django.db import OperationalError, ProgrammingError
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from crate_anon.crateweb.core.dbfunc import (
    dictlist_to_tsv,
    escape_sql_string_literal,
    get_fieldnames_from_cursor,
)
from crate_anon.crateweb.core.utils import is_superuser, paginate
from crate_anon.crateweb.research.forms import (
    AddHighlightForm,
    AddQueryForm,
    PidLookupForm,
    SQLHelperTextAnywhereForm,
)
from crate_anon.crateweb.research.html_functions import (
    highlight_text,
    make_result_element,
    make_collapsible_query,
    N_CSS_HIGHLIGHT_CLASSES,
)
from crate_anon.crateweb.research.models import (
    Highlight,
    PidLookup,
    Query,
    research_database_info,
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


# =============================================================================
# Queries
# =============================================================================

def edit_select_query(request):
    """
    Edit or select SQL for current query.
    """
    # log.debug("query")
    # if this is a POST request we need to process the form data
    all_queries = Query.objects.filter(user=request.user, deleted=False)\
                               .order_by('-active', '-created')
    if request.method == 'POST':
        # create a form instance and populate it with data from the request:
        form = AddQueryForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            sql = form.cleaned_data['sql']
            identical_queries = all_queries.filter(sql=sql)
            if identical_queries:
                identical_queries[0].activate()
            else:
                query = Query(sql=sql, raw=True, user=request.user,
                              active=True)
                query.save()
            # redirect to a new URL:
            return redirect('query')

    # if a GET (or any other method) we'll create a blank form
    values = {}
    active_queries = all_queries.filter(active=True)
    if active_queries:
        values['sql'] = active_queries[0].get_original_sql()
    form = AddQueryForm(values)
    queries = paginate(request, all_queries)
    # profile = request.user.profile
    for i, q in enumerate(queries):
        q.formatted_query_safe = make_collapsible_query(
            q.get_original_sql(),
            i,
            collapse_at_n_lines=5,
        )
    context = {
        'form': form,
        'queries': queries,
        'nav_on_query': True,
    }
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


def count(request, query_id):
    """
    View COUNT(*) from specific query.
    """
    if query_id is None:
        return render(request, 'no_query_selected.html')
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
        return render(request, 'no_query_selected.html')
    return render_resultcount(request, query)


def results(request, query_id):
    """
    View results of chosen query.
    """
    if query_id is None:
        return render(request, 'no_query_selected.html')
    try:
        query_id = int(query_id)
        query = Query.objects.get(id=query_id, user=request.user)
    except ObjectDoesNotExist:
        return render_bad_query_id(request, query_id)
    profile = request.user.profile
    highlights = Highlight.get_active_highlights(request)
    return render_resultset(request, query, highlights,
                            collapse_at=profile.collapse_at,
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


def render_resultcount(request, query):
    """
    Displays the number of rows that a given query will fetch.
    """
    if query is None:
        return render_missing_query(request)
    try:
        cursor = query.get_executed_cursor()
    except (ProgrammingError, OperationalError) as exception:
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
                     collapse_at=None, line_length=None):
    # Query
    if query is None:
        return render_missing_query(request)
    try:
        cursor = query.get_executed_cursor()
    except (ProgrammingError, OperationalError) as exception:
        query.audit(failed=True, fail_msg=str(exception))
        return render_bad_query(request, query, exception)
    rowcount = cursor.rowcount
    query.audit(n_records=rowcount)
    fieldnames = get_fieldnames_from_cursor(cursor)
    rows = cursor.fetchall()
    # Highlights
    highlight_dict = Highlight.as_ordered_dict(highlights)
    highlight_descriptions = get_highlight_descriptions(highlight_dict)
    # Views
    elementnum = 0
    processedrows = []
    for row in rows:
        pr = []
        for value in row:
            processedvalue = make_result_element(
                value,
                elementnum,
                highlight_dict=highlight_dict,
                collapse_at=collapse_at,
                line_length=line_length
            )
            elementnum += 1
            pr.append(processedvalue)
        processedrows.append(pr)
    displayrows = paginate(request, processedrows)
    context = {
        'fieldnames': fieldnames,
        'highlight_descriptions': highlight_descriptions,
        'rows': displayrows,
        'rowcount': rowcount,
        'sql': query.get_original_sql(),
        'nav_on_results': True,
    }
    return render(request, 'query_result.html', context)


def render_tsv(request, query):
    if query is None:
        return render_missing_query(request)
    try:
        tsv_result = query.make_tsv()
    except (ProgrammingError, OperationalError) as exception:
        return render_bad_query(request, query, exception)
    return HttpResponse(tsv_result, content_type='text/csv')


def render_missing_query(request):
    return render(request, 'query_missing.html')


def render_bad_query(request, query, exception):
    (final_sql, args) = query.get_sql_args_for_mysql()
    context = {
        'original_sql': query.get_original_sql(),
        'final_sql': final_sql,
        'args': str(args),
        'exception': str(exception),
    }
    return render(request, 'query_bad.html', context)


def render_bad_query_id(request, query_id):
    context = {'query_id': query_id}
    return render(request, 'bad_query_id.html', context)


def render_bad_highlight_id(request, highlight_id):
    context = {'highlight_id': highlight_id}
    return render(request, 'bad_highlight_id.html', context)


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
        'default_schema': settings.DATABASES['research']['NAME'],
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
        'default_schema': settings.DATABASES['research']['NAME'],
    }
    return render(request, 'database_structure.html', context)


# noinspection PyUnusedLocal
def structure_tsv(request):
    infodictlist = research_database_info.get_infodictlist()
    tsv_result = dictlist_to_tsv(infodictlist)
    return HttpResponse(tsv_result, content_type='text/csv')


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
            sql += "\nORDER BY {}".format(fkname)
        return HttpResponse(sql, content_type='text/plain')

    return render(request, 'sqlhelper_form_text_anywhere.html', {'form': form})
