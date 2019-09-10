## -*- coding: utf-8 -*-
<%doc>

crate_anon/crateweb/specimen_archives/tree/panels/clinical_documents.mako

===============================================================================

    Copyright (C) 2015-2019 Rudolf Cardinal (rudolf@pobox.com).

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

I tried this with

    <%inherit file="../snippets/subtree_page.mako"/>

    <%
    tree = JavascriptTree(
        tree_id="doc_tree",
        child_id_prefix="doc_tree_child_",
        children=[
            JavascriptLeafNode(filename, embedded_attachment_html(filename, context))
            for filename in gen_downloadable_filenames()
        ]
    )
    log.critical(repr(tree))
    %>

    <%block name="tree_id">doc_tree</%block>
    <%block name="treepage_title">Clinical Documents</%block>
    <%block name="tree_html">${tree.html()}</%block>
    <%block name="tree_js_data">${tree.js_data()}</%block>
    <%block name="no_content_selected"><div class="obscure_spinner"><i>Choose a document.</i></div></%block>

However, I think the inheritance system works such that the parent is evaluated
first, and therefore the Python definition of "tree" has not yet occurred by
the time the parent calls back to our (child) <%block> overrides. See
https://docs.makotemplates.org/en/latest/inheritance.html.

Inspecting the source of the "child" template shows that the Python above (to
create "tree") appears within "def render_body(context, **pageargs):" -- which
is separate from e.g. "def render_tree_id()", "def render_treepage_title()".

So we need to use an "inclusion" or a "namespace" method instead.

</%doc>

<%inherit file="../inherit/base.mako"/>

<%!

# =============================================================================
# Imports
# =============================================================================

import logging
import os
from typing import Generator

from django.conf import settings

from crate_anon.crateweb.core.constants import SettingsKeys
from crate_anon.crateweb.core.utils import (
    JavascriptBranchNode,
    JavascriptLeafNode,
    JavascriptTree,
)
from crate_anon.crateweb.research.archive_func import embedded_attachment_html

log = logging.getLogger(__name__)


# =============================================================================
# Functions
# =============================================================================

def gen_downloadable_filenames() -> Generator[str, None, None]:
    """
    Generates filenames that are permissible for download.
    """
    rootdir = getattr(
        settings, SettingsKeys.ARCHIVE_ATTACHMENT_DIR, "")
    if not rootdir:
        return
    for dir_, subdirs, files in os.walk(rootdir, topdown=True):
        if dir_ == rootdir:
            for filename in files:
                yield filename  # don't prepend pointless "./"
        else:
            final_dir = os.path.relpath(dir_, rootdir)
            for filename in files:
                yield os.path.join(final_dir, filename)

%>

<%namespace name="subtree" file="../snippets/subtree.mako"/>

<%

tree = JavascriptTree(
    tree_id="doc_tree",
    child_id_prefix="doc_tree_child_",
    children=[
        JavascriptBranchNode("All", children=[
            JavascriptLeafNode(filename, embedded_attachment_html(filename, context))
            for filename in gen_downloadable_filenames()
        ]),
    ],
)
# log.critical(repr(tree))

%>

${subtree.subtree_page(tree=tree, page_title="Clinical Documents", no_content_selected="Choose a document.")}
