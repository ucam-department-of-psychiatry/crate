#!/usr/bin/env python3
# research/views.py

import logging
logger = logging.getLogger(__name__)
from django import forms
from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import ValidationError
from django.db import OperationalError, ProgrammingError
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from core.dbfunc import dictlist_to_tsv, get_fieldnames_from_cursor
from core.utils import is_superuser, paginate
from .forms import (
    AddHighlightForm,
    PidLookupForm,
    AddQueryForm,
)
from .html_functions import (
    highlight_text,
    make_result_element,
    N_CSS_HIGHLIGHT_CLASSES,
)
from .models import (
    Highlight,
    PidLookup,
    Query,
    research_database_info,
)


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

def query(request):
    """
    Edit or select SQL for current query.
    """
    # logger.debug("query")
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


def highlight(request):
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
    View COUNT(*) from current query.
    """
    if query_id is None:
        return render(request, 'no_query_selected.html')
    try:
        query_id = int(query_id)
        query = Query.objects.get(id=query_id, user=request.user)
    except:
        return render_bad_query_id(request, query_id)
    query = Query.get_active_query_or_none(request)
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
    except:
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
    if request.method == 'POST':
        form = PidLookupForm(request.POST)
        if form.is_valid():
            trids = form.cleaned_data['trids']
            rids = form.cleaned_data['rids']
            mrids = form.cleaned_data['mrids']
            return render_lookup(request, trids=trids, rids=rids, mrids=mrids)

    form = PidLookupForm()
    context = {
        'form': form,
    }
    return render(request, 'pid_lookup_form.html', context)


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
        tsv = query.make_tsv()
    except (ProgrammingError, OperationalError) as exception:
        return render_bad_query(request, query, exception)
    return HttpResponse(tsv, content_type='text/csv')


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
    context = {
        'paginated': False,
        'infodictlist': research_database_info.infodictlist,
        'default_schema': settings.DATABASES['research']['NAME'],
    }
    return render(request, 'database_structure.html', context)


def structure_table_paginated(request):
    infodictlist = research_database_info.infodictlist
    infodictlist = paginate(request, infodictlist)
    context = {
        'paginated': True,
        'infodictlist': infodictlist,
        'default_schema': settings.DATABASES['research']['NAME'],
    }
    return render(request, 'database_structure.html', context)


def structure_tsv(request):
    infodictlist = research_database_info.infodictlist
    tsv = dictlist_to_tsv(infodictlist)
    return HttpResponse(tsv, content_type='text/csv')
