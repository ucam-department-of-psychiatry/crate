## -*- coding: utf-8 -*-
## crate_anon/crateweb/specimen_archives/tree/panels/clinical_documents.mako
<%inherit file="../base.mako"/>
<%namespace name="attachments" file="../snippets/attachments.mako"/>

<%!

# =============================================================================
# Imports
# =============================================================================

import os
from typing import Callable, Generator

from django.conf import settings

from crate_anon.crateweb.core.constants import SettingsKeys


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


def blank_content() -> str:
    return '<div class="obscure_spinner"><i>Choose a document.</i></div>'

%>


<%

file_info = [
    (i, filename)
    for i, filename in enumerate(gen_downloadable_filenames())
]

%>

<div class="mainpage_row">
  ## --------------------------------------------------------------------------
  ## Left-hand side: list of documents
  ## --------------------------------------------------------------------------
  <div class="mainpage_col_left">
    <h1>Clinical Documents</h1>
    <ul class="tree" id="doc_tree">
        %for i, filename in enumerate(gen_downloadable_filenames()):
            <li id="${i}">${filename | h}</li>
        %endfor
    </ul>

  </div>

  ## --------------------------------------------------------------------------
  ## Right-hand side: content
  ## --------------------------------------------------------------------------
  <div class="mainpage_col_right" id="doc_content">${blank_content()}</div>

</div>
## ============================================================================
## Scripts
## ============================================================================

<script src="${static_url("tree.js")}" type="text/javascript"></script>
<script type="text/javascript">

// ----------------------------------------------------------------------------
// Infrastructure
// ----------------------------------------------------------------------------

function getRightContentDiv()
{
    // Returns the <div> for the main right panel.
    return document.getElementById("doc_content");
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
    html = JS_FILE_INFO[id];
    return html;
}


// ----------------------------------------------------------------------------
// Execute immediately
// ----------------------------------------------------------------------------

var JS_FILE_INFO = [
    %for _, filename in file_info:
        ${attachments.embedded_attachment(filename)},
    %endfor
];
console.log(JS_FILE_INFO);

var TREE_ID = "doc_tree";
activateTreeExpansion();
addTreeIDCallbacks(TREE_ID, callback);

var g_current_tree_item_id = "";  // global

</script>
