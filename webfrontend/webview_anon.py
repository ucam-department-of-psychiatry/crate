#!/usr/bin/python2.7
# -*- encoding: utf8 -*-

"""
Views (pre-anonymised) SQL-based databases using a data dictionary.

Author: Rudolf Cardinal
Created at: 19 Mar 2015
Last update: see VERSION_DATE below

IN PROGRESS.

Copyright/licensing:

    Copyright (C) 2015-2015 Rudolf Cardinal (rudolf@pobox.com).
    Department of Psychiatry, University of Cambridge.

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

        http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.

IN PROGRESS
    - output roughly sketched out
    - WSGI framework drafted

    - needs safe SQL creation framework
        - easy to make something too fiddly: http://www.ajaxquerybuilder.com/
    - needs session, security/users, main menu, audit
    - user accessing the destination database must be READ ONLY here
    
This kind of queries that might benefit from some autogeneration:

    SELECT
        master.rid, master.dob, ...
        secondtable.field1, secondtable.field2, ...
        thirdtable.field1, thirdtable.field2, ...
    FROM
        master
        INNER JOIN secondtable ON (secondtable.rid = master.rid)
        INNER JOIN thirdtable ON (thirdtable.rid = master.rid)
    WHERE
        MATCH(secondtable.field1) AGAINST ('schizophrenia')
        OR MATCH(thirdtable.field1) AGAINST ('schizophrenia')

However, it's not clear anything really improves on writing raw SQL; most
assisted query generation frameworks are quite crippled functionally. Simple
SQL also has the advantage of producing a clear tabular structure, without
nesting.

What is definitely useful is result highlighting.
"""

from __future__ import division
from __future__ import print_function

# =============================================================================
# Debugging options
# =============================================================================

# Not possible to put the next two flags in environment variables, because we
# need them at load-time and the WSGI system only gives us environments at
# run-time.

# For debugging, set the next variable to True, and it will provide much
# better HTML debugging output.
# Use caution enabling this on a production system.
# However, system passwords should be concealed regardless (see cc_shared.py).
DEBUG_TO_HTTP_CLIENT = True

# Report profiling information to the HTTPD log? (Adds overhead; do not enable
# for production systems.)
PROFILE = False

# =============================================================================
# Imports
# =============================================================================

import argparse
import csv
import io
import logging
logger = logging.getLogger(__name__)
import math
import re
import sys
import textwrap

# Local
import pythonlib.rnc_db as rnc_db
import pythonlib.rnc_web as ws
from pythonlib.rnc_lang import AttrDict
from anonymise.anonymise import config
    # *** WRONG: needs separate config (different, less privileged,
    # database user) - just with reference to DD
from anonymise.anon_regex import escape_literal_string_for_regex

# Conditional imports
if PROFILE:
    import werkzeug.contrib.profiler
if DEBUG_TO_HTTP_CLIENT:
    import pythonlib.wsgi_errorreporter as wsgi_errorreporter

# Configure logger
logger.setLevel(logging.INFO)

# =============================================================================
# Constants
# =============================================================================

N_CSS_HIGHLIGHT_CLASSES = 2  # named highlight0, highlight1, ... highlight<n-1>
PLUS_IMAGE = (
    "data:image/gif;base64,R0lGODlhCQAJAMQAAJ2sw8PP4e/z+pakupWlucXR5OXs97vN66/"
    "A2Z2swrbF3c/b8u/z+/n7/ebs+MTU79rk9JyrwJ6uxJqovvD0+/j6/am82JSkuJinvOXs+M/N"
    "xaK21v///zVJYwAAAAAAACH5BAAAAAAALAAAAAAJAAkAAAU4oCYl0YQNl8itXMUYHcB2ghN00"
    "dp0GYR0E05nOLR0MBVKprN4bDoEJaTzODwvjoLCsul2NMSwJgQAOw=="
)
MINUS_IMAGE = (
    "data:image/gif;base64,R0lGODlhCQAJAMQAAM/b8qm82J2sw+/z+5SjuLbF3a/A2ZemvPj"
    "6/ZSkuJinu/Dz+/n6/eXs9/n7/ubs+MTU75yrwJ6uxJalupqovvD0+6W516K21sHP5eXs+Nrj"
    "9M/Nxf///zVJYwAAAAAAACH5BAAAAAAALAAAAAAJAAkAAAU24CYJEaVMhMitHDI0ncA6w4N10"
    "eosmWZ0FE5nOAx0DoxKDwCxdCZKDRNz6SRshYDlUt0Qv5sQADs="
)
HTML_START = u"""
<!DOCTYPE html> <!-- HTML 5 -->
<html>
    <head>
        <title>webanon</title>
        <meta charset="utf-8">
        <style type="text/css">

/*=============================================================================
CSS start
=============================================================================*/

body {
    font-size: small;
    font-family: Georgia, "Times New Roman", Times, serif;
    text-align: left;
}

table {
    display: table-cell;
    border-collapse: collapse;
    vertical-align: top;
}
th {
    border-bottom: 1px solid #000;
    vertical-align: top;
}
tr {
    border-bottom: 1px solid #ccc;
}
td {
    vertical-align: top;
}

.expandcollapse {
}
.detail {
}
.indent {
    margin-left: 50px;
}

/* yellow and red are typically used by browsers for all-instances and
   instance-at-the-cursor with Ctrl-F */
.highlight0 { background-color: #0F0; }
.highlight1 { background-color: #88F; }
/* If altering: change also N_CSS_HIGHLIGHT_CLASSES in the source */

/*=============================================================================
CSS end
=============================================================================*/

        </style>
        <script>

// ============================================================================
// Javascript start
// ============================================================================

var getElementsByClassName = function (className, tag, elm){
    // http://robertnyman.com/2008/05/27/
    //        the-ultimate-getelementsbyclassname-anno-2008/
    // Developed by Robert Nyman, http://www.robertnyman.com
    // Code/licensing: http://code.google.com/p/getelementsbyclassname/
    if (document.getElementsByClassName) {
        getElementsByClassName = function (className, tag, elm) {
            elm = elm || document;
            var elements = elm.getElementsByClassName(className),
                nodeName = (
                    tag
                    ? new RegExp("\\b" + tag + "\\b", "i")
                    : null
                ),
                returnElements = [],
                current;
            for(var i=0, il=elements.length; i<il; i+=1){
                current = elements[i];
                if (!nodeName || nodeName.test(current.nodeName)) {
                    returnElements.push(current);
                }
            }
            return returnElements;
        };
    } else if (document.evaluate) {
        getElementsByClassName = function (className, tag, elm) {
            tag = tag || "*";
            elm = elm || document;
            var classes = className.split(" "),
                classesToCheck = "",
                xhtmlNamespace = "http://www.w3.org/1999/xhtml",
                namespaceResolver = (
                    document.documentElement.namespaceURI
                        === xhtmlNamespace
                    ? xhtmlNamespace
                    : null
                ),
                returnElements = [],
                elements,
                node;
            for (var j=0, jl=classes.length; j<jl; j+=1){
                classesToCheck += (
                    "[contains(concat(' ', @class, ' '), ' "
                    + classes[j]
                    + " ')]"
                );
            }
            try {
                elements = document.evaluate(
                    ".//" + tag + classesToCheck, elm,
                    namespaceResolver, 0, null
                );
            }
            catch (e) {
                elements = document.evaluate(
                    ".//" + tag + classesToCheck, elm, null, 0, null
                );
            }
            while ((node = elements.iterateNext())) {
                returnElements.push(node);
            }
            return returnElements;
        };
    } else {
        getElementsByClassName = function (className, tag, elm) {
            tag = tag || "*";
            elm = elm || document;
            var classes = className.split(" "),
                classesToCheck = [],
                elements = (
                    (tag === "*" && elm.all)
                    ? elm.all
                    : elm.getElementsByTagName(tag)
                ),
                current,
                returnElements = [],
                match;
            for (var k=0, kl=classes.length; k<kl; k+=1) {
                classesToCheck.push(new RegExp("(^|\\s)" + classes[k]
                                    + "(\\s|$)"));
            }
            for (var l=0, ll=elements.length; l<ll; l+=1) {
                current = elements[l];
                match = false;
                for (var m=0, ml=classesToCheck.length; m<ml; m+=1) {
                    match = classesToCheck[m].test(current.className);
                    if (!match) {
                        break;
                    }
                }
                if (match) {
                    returnElements.push(current);
                }
            }
            return returnElements;
        };
    }
    return getElementsByClassName(className, tag, elm);
};

function hideAll() {
    var elements = getElementsByClassName("detail"),
        i;
    for (i = 0; i < elements.length; ++i) {
        elements[i].style.display = "none";
    }
    elements = getElementsByClassName("summary");
    for (i = 0; i < elements.length; ++i) {
        elements[i].style.display = "none";
    }
    elements = getElementsByClassName("plusminus_image");
    for (i = 0; i < elements.length; ++i) {
        elements[i].src = "%s"; // PLUS
    }
}

function showAll() {
    var elements = getElementsByClassName("detail"),
        i;
    for (i = 0; i < elements.length; ++i) {
        elements[i].style.display = "";
    }
    elements = getElementsByClassName("summary");
    for (i = 0; i < elements.length; ++i) {
        elements[i].style.display = "";
    }
    elements = getElementsByClassName("plusminus_image");
    for (i = 0; i < elements.length; ++i) {
        elements[i].src = "%s"; // MINUS
    }
}

function toggle(divId, imageId) {
    var div = document.getElementById(divId),
        img = document.getElementById(imageId);
    if (div.style.display == "none") {
        div.style.display = "";
        img.src = "%s"; // MINUS
    }
    else {
        div.style.display = "none";
        img.src = "%s"; // PLUS
    }
}

// ============================================================================
// Javascript end
// ============================================================================

        </script>
    </head>
    <body>
""" % (
    PLUS_IMAGE,
    MINUS_IMAGE,
    MINUS_IMAGE,
    PLUS_IMAGE,
)

HTML_END = """
    </body>
</html>
"""


# =============================================================================
# HTML components
# =============================================================================

def small_menu():
    return u"""
        [ main menu
        | SELECT
        | WHERE
        | ORDER BY
        | preview count
        | view results
        | export as TSV ]
    """


def collapsible_div(tag, contents, extradivclasses=[]):
    classes = ["detail"] + extradivclasses
    return u"""
        <div class="expandcollapse"
                onclick="toggle('{elementname}', '{imgname}');">
            <img class="plusminus_image" id="{imgname}" alt=""
                src="{plusimage}">
        </div>
        <div class="{classes}" id="{elementname}" style="display:none">
            {contents}
        </div>
        <!-- pre-hide, rather than use an onload method -->
    """.format(
        elementname="elem_{}".format(tag),
        classes=" ".join(classes),
        imgname="img_{}".format(tag),
        plusimage=PLUS_IMAGE,
        contents=contents,
    )


# =============================================================================
# Convert query to HTML in a user-friendly way, with highlighting and
# collapsible big bits
# =============================================================================

def gen_rows(db, sql, args, firstrow=0, lastrow=None):
    if firstrow > 0 or lastrow is not None:
        sql += " LIMIT {f},{n}".format(
            f=firstrow,
            # zero-indexed; http://dev.mysql.com/doc/refman/5.0/en/select.html
            n=(lastrow - firstrow + 1),
        )
    cursor = db.cursor()
    db.db_exec_with_cursor(cursor, sql, *args)
    row = cursor.fetchone()
    while row is not None:
        yield row
        row = cursor.fetchone()


def get_regex_from_highlights(highlights, at_word_boundaries_only=False):
    elements = []
    wb = r"\b"  # word boundary; escape the slash if not using a raw string
    for h in highlights:
        h = escape_literal_string_for_regex(h)
        if at_word_boundaries_only:
            elements.append(wb + h + wb)
        else:
            elements.append(h)
    regexstring = u"(" + "|".join(elements) + ")"  # group required, to replace
    return re.compile(regexstring, re.IGNORECASE | re.UNICODE)


def highlight_text(x, n=0):
    n %= N_CSS_HIGHLIGHT_CLASSES
    return ur'<span class="highlight{n}">{x}</span>'.format(n=n, x=x)


def make_highlight_replacement_regex(n=0):
    return highlight_text(r"\1", n=n)


def make_html_element(x, elementnum,
                      highlights=[], collapse_at=None, line_length=None):
    if x is None:
        return ""
    if not isinstance(x, (str, unicode)):
        x = str(x)
    xlen = len(x)  # before we mess around with it
    if line_length:
        x = "\n".join(textwrap.wrap(x, width=line_length))
    x = ws.webify(x)
    for n, highlight_values in enumerate(highlights):
        find = get_regex_from_highlights(highlight_values)
        replace = make_highlight_replacement_regex(n)
        x = find.sub(replace, x)
    if collapse_at and xlen >= collapse_at:
        return collapsible_div(elementnum, x)
    return x


def make_html_row(row, elementnum,
                  highlights=[], collapse_at=None, line_length=None):
    elements = []
    for e in row:
        x = make_html_element(e, elementnum, highlights=highlights,
                              collapse_at=collapse_at, line_length=line_length)
        elements.append(u"""
                <td>{}</td>
            """.format(x)
        )
        elementnum += 1
    return (
        elementnum,
        u"""
            <tr>{}
            </tr>""".format(u"".join(elements))
    )


def make_html_results_table(db, sql, args, fieldnames,
                            firstrow=0, lastrow=None,
                            highlights=[], collapse_at=None, line_length=None):
    elementnum = 0
    header_elements = [
        u"""
                <th>{}</th>""".format(e) for e in fieldnames
    ]
    th = u"""
            <tr>{}
            </tr>""".format(u"".join(header_elements))
    table = u"""
        <table>""" + th
    for r in gen_rows(db, sql, args, firstrow=firstrow, lastrow=lastrow):
        (elementnum, rowhtml) = make_html_row(
            r, elementnum, highlights=highlights, collapse_at=collapse_at,
            line_length=line_length)
        table += rowhtml
    table += """
        </table>
    """
    return table


def make_results_tsv(db, sql, args, fieldnames, firstrow=0, lastrow=None):
    output = io.StringIO()
    writer = csv.writer(output, delimiter='\t')
    writer.writerow(fieldnames)
    for r in gen_rows(db, sql, args, firstrow=firstrow, lastrow=lastrow):
        writer.writerow(r)
    return output.getvalue()


def navigation(first_row_this_page, total_rows, rows_per_page):
    page = int(math.floor(first_row_this_page / rows_per_page)) + 1
    npages = int(math.ceil(total_rows / rows_per_page))
    if page == 1:
        first = "First"
        previous = "Previous"
    else:
        first = "NAV_FIRST"  # ***
        previous = "NAV_PREVIOUS"  # ***
    if page == npages:
        nxt = "Next"  # 'next' is a keyword
        last = "Last"
    else:
        nxt = "NAV_NEXT"  # ***
        last = "NAV_LAST"  # ***
    return """
        <div>
            <b>Page {page}</b> of {npages} ({total_rows} rows found)
            [ {first} | {previous} | {nxt} | {last} ]
        </div>
    """.format(
        page=page,
        npages=npages,
        total_rows=total_rows,
        first=first,
        previous=previous,
        nxt=nxt,
        last=last,
    )


def expand_collapse_buttons():
    return u"""
        <button onclick="showAll();">Show all details</button>
        <button onclick="hideAll();">Hide all details</button>
    """


def make_html_results_page(db, sql, args, firstrow=0, highlights=[],
                           collapse_at=None, line_length=None,
                           rows_per_page=25):
    """
    highlights: a list of lists of values. Each list uses a different
        colour highlighter, until we run out of possibilities.
    """
    cursor = db.cursor()
    db.db_exec_with_cursor(cursor, sql, *args)
    rowcount = cursor.rowcount
    fieldnames = [i[0] for i in cursor.description]
    lastrow = firstrow + rows_per_page - 1
    table = make_html_results_table(
        db, sql, args, fieldnames,
        firstrow=firstrow, lastrow=lastrow,
        highlights=highlights, collapse_at=collapse_at,
        line_length=line_length)
    highlightdescription = "".join(
        u"<li>{}</li>".format(", ".join(highlight_text(x, n)
                                        for x in valuelist))
        for n, valuelist in enumerate(highlights)
    )
    return HTML_START + u"""
        {smallmenu}
        <h1>SQL</h1>
        <pre>{sql}</pre>
        <h1>Highlighting</h1>
        <ul>{highlightdescription}</ul>
        <h1>Results</h1>
        {nav}
        {expandcollapse}
        {table}
        {nav}
    """.format(
        smallmenu=small_menu(),
        sql=ws.webify(db.get_literal_sql_with_arguments(sql, *args)),
        args=args,
        highlightdescription=highlightdescription,
        nav=navigation(firstrow, rowcount, rows_per_page),
        expandcollapse=expand_collapse_buttons(),
        table=table,
    ) + HTML_END


# =============================================================================
# Convert query to TSV
# =============================================================================

def tsv_escape(x):
    if x is None:
        return u""
    if not isinstance(x, unicode):
        x = unicode(x)
    return x.replace("\t", "\\t").replace("\n", "\\n")


def make_tsv(db, sql, args):
    cursor = db.cursor()
    db.db_exec_with_cursor(cursor, sql, *args)
    fieldnames = [i[0] for i in cursor.description]
    tsv = u"" + ",".join([tsv_escape(f) for f in fieldnames]) + "\n"
    row = cursor.fetchone()
    while row is not None:
        tsv += ",".join([tsv_escape(x) for x in row]) + "\n"
        row = cursor.fetchone()
    return tsv


# =============================================================================
# Test
# =============================================================================

def test_query_output(session=None, form=None):
    db = config.destdb
    sql = "SELECT * FROM notes WHERE note LIKE ?"
    args = ['%Adam%']
    firstrow = 10  # zero-indexed
    highlights = [
        ["Aaron", "Adam"],  # highlight 0
        ["October"]  # highlight 1
    ]
    rows_per_page = 10
    line_length = 60
    collapse_at = 5 * line_length
    return make_html_results_page(
        db, sql, args, firstrow=firstrow, highlights=highlights,
        collapse_at=collapse_at, rows_per_page=rows_per_page,
        line_length=line_length)


def test_show_fields(session=None, form=None):
    tables = sorted(set([dfi.table for dfi in config.destfieldinfo]))
    table_elements = []
    for t in tables:
        field_elements = []
        dfi_list = [dfi for dfi in config.destfieldinfo if dfi.table == t]
        dfi_list = sorted(dfi_list, key=lambda x: x.field)
        for dfi in dfi_list:
            field_elements.append(u"""
                <div>
                    {table}.<b>{field}</b>, {fieldtype}{sep}<i>{comment}</i>
                </div>
            """.format(
                table=t,
                field=dfi.field,
                fieldtype=dfi.fieldtype,
                sep="; " if dfi.comment else "",
                comment=dfi.comment,
            ))
        fields = collapsible_div("table_{}".format(t),
                                 "\n".join(field_elements),
                                 extradivclasses=["indent"])
        contents = u"""
            <div>
                <b>{table}</b>
                {fields}
            </div>
        """.format(
            table=t,
            fields=fields
        )
        table_elements.append(contents)
    tree = u"""
        <div>
        {}
        </div>
    """.format("\n".join(table_elements))
    return HTML_START + u"""
        <h1>Fields in the anonymised database (from the data dictionary)</h1>
        {expandcollapse}
        {tree}
    """.format(
        expandcollapse=expand_collapse_buttons(),
        tree=tree,
    ) + HTML_END



# =============================================================================
# HTTP/HTML forms etc.
# =============================================================================

def fail_unknown_action(action):
    """HTML given when action unknown."""
    # return cc_html.fail_with_error_stay_logged_in(
    #     "Can't process action {} - action not recognized.".format(action)
    # )
    return "GARBAGE"  # ***


def fail_dangerous_database_access():
    """
    HTML given when the database user is mis-configured and might permit
    writes.
    """
    return "GARBAGE"  # ***


# =============================================================================
# Command-line processor
# =============================================================================

def fail():
    sys.exit(1)


def cli_main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        prog="webview_anon",
        description=("Web viewer for anonymisation system. "
                     "Normally run as a WSGI application.")
    )
    parser.add_argument("configfilename", nargs="?", default=None,
                        help="Configuration file")
    parser.add_argument('--verbose', '-v', action='count',
                        help="Be verbose (use twice for extra verbosity)")
    parser.add_argument('--datadictionary', '-d', action='store_true',
                        help="Output is an HTML-formatted copy of the data "
                             "dictionary")
    args = parser.parse_args()

    if not args.configfilename:
        parser.print_help()
        fail()

    rnc_db.set_loglevel(logging.DEBUG if args.verbose >= 2 else logging.INFO)
    LOG_FORMAT = '%(asctime)s.%(msecs)03d:%(levelname)s:%(name)s:%(message)s'
    LOG_DATEFMT = '%Y-%m-%d %H:%M:%S'
    mainloglevel = logging.DEBUG if args.verbose >= 1 else logging.INFO
    logging.basicConfig(format=LOG_FORMAT, datefmt=LOG_DATEFMT,
                        level=mainloglevel)

    config.set(filename=args.configfilename, include_sources=False)

    # For a MySQL database: do I have write permissions or not?
    # Since we're going to allow (with considerable wariness) unrestricted SQL,
    # we should at least check that the user can't destroy everything.
    logger.info("is_read_only: {}".format(config.destdb.is_read_only()))

    if args.datadictionary:
        print(test_show_fields())
    else:
        print(test_query_output())


# =============================================================================
# Main HTTP processor
# =============================================================================

# -------------------------------------------------------------------------
# HTTP actions, parameters, values
# -------------------------------------------------------------------------

ACTION = AttrDict({
    "MAIN_MENU": "main_menu",
})

PARAM = AttrDict({
})

VALUE = AttrDict({
})

# -------------------------------------------------------------------------
# Main set of action mappings.
# All functions take parameters (session, form)
# -------------------------------------------------------------------------
ACTIONDICT = {
    None: test_query_output,
}


def main_http_processor(env):
    """Main processor of HTTP requests."""

    # Sessions details are already in pls.session

    # -------------------------------------------------------------------------
    # Check we don't have dangerous access
    # -------------------------------------------------------------------------
    if not config.destdb.is_read_only():
        pass  # ***

    # -------------------------------------------------------------------------
    # Process requested action
    # -------------------------------------------------------------------------
    form = ws.get_cgi_fieldstorage_from_wsgi_env(env)
    action = ws.get_cgi_parameter_str(form, PARAM.ACTION)
    logger.debug("action = {}".format(action))

    # -------------------------------------------------------------------------
    # Login
    # -------------------------------------------------------------------------
    # if action == ACTION.LOGIN:
    #     return login(pls.session, form)

    # -------------------------------------------------------------------------
    # If we're not authorized, we won't get any further:
    # -------------------------------------------------------------------------
    # if not pls.session.authorized_as_viewer():
    #     if not action:
    #         return cc_html.login_page()
    #     else:
    #         return fail_not_user(action, redirect=env.get("REQUEST_URI"))

    # -------------------------------------------------------------------------
    # Can't bypass an enforced password change, or acknowledging terms:
    # -------------------------------------------------------------------------
    # if pls.session.user_must_change_password():
    #     if action != ACTION.CHANGE_PASSWORD:
    #         return cc_user.enter_new_password(
    #             pls.session, pls.session.user,
    #             as_manager=False, because_password_expired=True
    #         )
    # elif (pls.session.user_must_agree_terms()
    #           and action != ACTION.AGREE_TERMS):
    #     return offer_terms(pls.session, form)
    # Caution with the case where the user must do both; don't want deadlock!
    # The statements let a user through if they're changing their password,
    # even if they also need to acknowledge terms (which comes next).

    # -------------------------------------------------------------------------
    # Process requested action
    # -------------------------------------------------------------------------
    fn = ACTIONDICT.get(action)
    if not fn:
        return fail_unknown_action(action)
    return fn(config.session, form)


# =============================================================================
# WSGI application
# =============================================================================

def application_db_wrapper(environ, start_response):
    """WSGI application entry point. See CamCOPS for explanation."""

    if environ["wsgi.multithread"]:
        logger.critical("Started in multithreaded mode")
        raise RuntimeError("Cannot be run in multithreaded mode")

    # Set global variables, connect/reconnect to database, etc.
    config.set(environ=environ)

    # Trap any errors from here.
    # http://doughellmann.com/2009/06/19/python-exception-handling-techniques.html  # noqa
    try:
        result = application_main(environ, start_response)
        # ... it will commit (the earlier the better for speed)
        return result
    except Exception:
        try:
            raise  # re-raise the original error
        finally:
            try:
                config.admindb.rollback()
            except:
                pass  # ignore errors in rollback


def application_main(environ, start_response):
    """Main WSGI application handler."""

    # Establish a session based on incoming details
    # *** # cc_session.establish_session(environ)  # writes to config.session

    # Call main
    result = main_http_processor(environ)
    status = '200 OK'  # default unless overwritten
    # If it's a 3-value tuple, fine. Otherwise, assume HTML requiring encoding.
    if isinstance(result, tuple) and len(result) == 3:
        (contenttype, extraheaders, output) = result
    elif isinstance(result, tuple) and len(result) == 4:
        (contenttype, extraheaders, output, status) = result
    else:
        (contenttype, extraheaders, output) = ws.html_result(result)

    # Commit (e.g. password changes, audit events, session timestamps)
    config.admindb.commit()  # WSGI route commit

    # Add cookie.
    # *** # extraheaders.extend(config.session.get_cookies())
    # Wipe session details, as an additional safeguard
    config.session = None

    # Return headers and output
    response_headers = [('Content-Type', contenttype),
                        ('Content-Length', str(len(output)))]
    if extraheaders is not None:
        response_headers.extend(extraheaders)  # not append!
    start_response(status, response_headers)
    return [output]


# =============================================================================
# WSGI entry point
# =============================================================================
# The WSGI framework looks for: def application(environ, start_response)
# ... must be called "application"

application = application_db_wrapper
if DEBUG_TO_HTTP_CLIENT:
    application = wsgi_errorreporter.ErrorReportingMiddleware(application)
if PROFILE:
    application = werkzeug.contrib.profiler.ProfilerMiddleware(application)

# =============================================================================
# Command-line entry point
# =============================================================================

if __name__ == '__main__':
    cli_main()
