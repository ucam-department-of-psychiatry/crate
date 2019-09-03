## -*- coding: utf-8 -*-
<%doc>

crate_anon/crateweb/specimen_archives/tree/snippets/subtree.mako

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

<%!
import logging
from crate_anon.crateweb.core.utils import JavascriptTree

log = logging.getLogger(__name__)

%>

<%def name="subtree_page(tree: JavascriptTree, page_title: str = '', no_content_selected: str = 'Choose from the left-hand tree.', leftcol_class: str = 'mainpage_col_left', rightcol_class: str = 'mainpage_col_right', html_above_title: str = '')">
    ## Page with a clickable tree on the left, and content on the right.

## ============================================================================
## HTML
## ============================================================================

<div class="mainpage_row">
  ## --------------------------------------------------------------------------
  ## Left-hand side: title and tree
  ## --------------------------------------------------------------------------
  <div class="${leftcol_class}">
    ${html_above_title}
    %if page_title:
        <div class="pad"><h1>${page_title}</h1></div>
    %endif
    <div class="pad">
        ${tree.html()}
    </div>
  </div>

  ## --------------------------------------------------------------------------
  ## Right-hand side: content, with initial "nothing selected" text.
  ## --------------------------------------------------------------------------
  <div class="${rightcol_class}" id="chosen_content">
    <div class="obscure_spinner"><i>${no_content_selected}</i></div>
  </div>

</div>

## ============================================================================
## Scripts
## ============================================================================

<script src="${get_static_url("tree.js")}" type="text/javascript"></script>
<script type="text/javascript">

// ----------------------------------------------------------------------------
// Infrastructure
// ----------------------------------------------------------------------------

function getRightContentDiv()
{
    // Returns the <div> for the main right panel.
    return document.getElementById("chosen_content");
}


function callback(id)
{
    // Called when the user clicks an item in the expanding menu.
    console.log("Item clicked: " + id);

    // Is this a change?
    if (id === g_current_tree_item_id) {
        // Don't reload existing content
        // return;
    }

    // Set the contents panels
    var rcd = getRightContentDiv();
    rcd.innerHTML = getRightContent(id);

    // Indicate on the left-hand tree which is currently selected
    if (g_current_tree_item_id !== "") {
        setElementClassName(g_current_tree_item_id, "");
    }
    setElementClassName(id, "tree_chosen");
    g_current_tree_item_id = id;
}


// ----------------------------------------------------------------------------
// Main callback choice
// ----------------------------------------------------------------------------

function getRightContent(id)
{
    return TREE_DATA[id];
}


// ----------------------------------------------------------------------------
// Execute immediately
// ----------------------------------------------------------------------------

var TREE_DATA = ${tree.js_data()};

var TREE_ID = "${tree.tree_id}";
activateTreeExpansion();
addTreeIDCallbacks(TREE_ID, callback);

var g_current_tree_item_id = "";  // global

</script>

</%def>
