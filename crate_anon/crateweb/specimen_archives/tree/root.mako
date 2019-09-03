## -*- coding: utf-8 -*-
<%doc>

crate_anon/crateweb/specimen_archives/tree/root.mako

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

</%doc>

<%inherit file="base.mako"/>

## ============================================================================
## Imports
## ============================================================================
<%!
import logging

from crate_anon.common.constants import HelpUrl
from crate_anon.crateweb.core.utils import (
    javascript_quoted_string_from_html,
    JavascriptBranchNode,
    JavascriptLeafNode,
    JavascriptTree,
)
from crate_anon.crateweb.research.archive_func import (
    embedded_attachment_html,
    template_html,
)

log = logging.getLogger(__name__)

NOT_IMPLEMENTED = '<div class="warning pad"><i>Not implemented yet.</i></div>'

%>
<%

def template_element(template_name: str) -> str:
    return template_html(template_name, context)


%>

<%namespace name="subtree" file="snippets/subtree.mako"/>

<%

# Title bar (keep this small!)
title_bar = f"""
    <div class="title_bar">
        <div>
            CRATE tree-style archive demo: BRCID <b>{patient_id}</b>.<br>
            [ <a href="{CRATE_HOME_URL}">Return to CRATE home</a>
            | <a href="{HelpUrl.archive()}">Help</a>
            ]
        </div>
    </div>
"""

tree = JavascriptTree(
    tree_id="main_tree",
    child_id_prefix="main_tree_child_",
    children=[
        JavascriptBranchNode("RiO", [
            JavascriptLeafNode(
                "Clinical Documents",
                template_element("panels/clinical_documents.mako")),
            JavascriptLeafNode("Diagnoses", NOT_IMPLEMENTED),
            JavascriptLeafNode(
                "Progress Notes",
                template_element("panels/progress_notes.mako")),
            JavascriptBranchNode("Assessments", [
                JavascriptLeafNode("Core Assessments", NOT_IMPLEMENTED),
            ]),
        ]),
        JavascriptLeafNode("NLP", template_element("panels/nlp.mako")),
        JavascriptLeafNode("Test PDF", embedded_attachment_html("doctest.pdf", context)),
    ]
)

%>

${subtree.subtree_page(tree=tree, html_above_title=title_bar)}
