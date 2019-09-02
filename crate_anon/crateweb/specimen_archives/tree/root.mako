## -*- coding: utf-8 -*-
## crate_anon/crateweb/specimen_archives/tree/root.mako
<%inherit file="base.mako"/>

## ============================================================================
## Imports
## ============================================================================
<%!
from crate_anon.common.constants import HelpUrl
from crate_anon.crateweb.core.utils import javascript_quoted_string_from_html


def blank_content() -> str:
    return '<div class="obscure_spinner"><i>Choose from the left-hand tree.</i></div>'  # noqa


def js_blank_content() -> str:
    return javascript_quoted_string_from_html(blank_content())


def not_implemented() -> str:
    return '<div class="warning"><i>Not implemented yet.</i></div>'


def js_not_implemented() -> str:
    return javascript_quoted_string_from_html(not_implemented())

%>
<%
def js_template_element(filename: str) -> str:
    url = archive_url(filename)
    return javascript_quoted_string_from_html(f"""
        <iframe class="embedded_attachment" src="{url}"></iframe>
    """)


%>

<%namespace name="attachments" file="snippets/attachments.mako"/>
## ... for test_pdf only

<div class="mainpage_row">
  ## --------------------------------------------------------------------------
  ## Left-hand side: title bar, navigation tree
  ## --------------------------------------------------------------------------
  <div class="mainpage_col_left">
    ## ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    ## Title bar (keep this small!)
    ## ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    <div class="title_bar">
        <div>
            CRATE tree-style archive demo: BRCID <b>${patient_id}</b>.<br>
            [ <a href="${CRATE_HOME_URL}">Return to CRATE home</a>
            | <a href="<%block name="helpurl">${HelpUrl.archive()}</%block>">Help</a>
            ]
        </div>
    </div>

    ## ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    ## Navigation tree
    ## ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    <ul class="tree" id="archive_tree">
      <li>
        <span class="caret">RiO</span>
        <ul class="nested">
          <li id="clinical_documents">Clinical Documents</li>
          <li id="diagnoses">Diagnoses</li>
          <li id="progress_notes">Progress Notes</li>
          <li>
            <span class="caret">Assessments</span>
            <ul class="nested">
              <li id="core_assessments">Core Assessments</li>
            </ul>
          </li>
        </ul>
      </li>
      <li id="nlp">NLP</li>
      <li id="test_pdf">Test PDF</li>
    </ul>

  </div>

  ## --------------------------------------------------------------------------
  ## Right-hand side: content (make this 100% height; best for PDFs etc).
  ## --------------------------------------------------------------------------
  <div class="mainpage_col_right" id="main_content">${blank_content()}</div>

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
    return document.getElementById("main_content");
}


function callback(id)
{
    // Called when the user clicks an item in the expanding menu.

    console.log("Item clicked: " + id);

    // Is this a change?
    if (id === g_current_tree_item_id) {
        // Don't reload existing content
        return;
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
    switch (id) {
        case "clinical_documents":
            return ${js_template_element("panels/clinical_documents.mako")};
        case "nlp":
            return ${js_template_element("panels/nlp.mako")};
        case "progress_notes":
            return ${js_template_element("panels/progress_notes.mako")};
        case "test_pdf":
            return ${attachments.embedded_attachment("doctest.pdf")};
        default:
            return ${js_not_implemented()};
    }
}


// ----------------------------------------------------------------------------
// Execute immediately
// ----------------------------------------------------------------------------

var TREE_ID = "archive_tree";
activateTreeExpansion();
addTreeIDCallbacks(TREE_ID, callback);

var g_current_tree_item_id = "";  // global

</script>
