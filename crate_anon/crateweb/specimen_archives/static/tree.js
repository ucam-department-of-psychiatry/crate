// ============================================================================
// Dynamic tree views.
// ============================================================================
// See https://www.w3schools.com/howto/howto_js_treeview.asp

// ----------------------------------------------------------------------------
// Make the tree's expand/collapse functions active.
// ----------------------------------------------------------------------------

function activateTreeExpansion()
{
    // Makes all trees in the document active.
    // - Nodes that can be expanded/collapsed should have the class "caret".
    // - They should be siblings of an element (e.g. <ul>) called "nested",
    //   containing the content.

    var toggler = document.getElementsByClassName("caret");
    for (var i = 0; i < toggler.length; i++) {
      toggler[i].addEventListener("click", function() {
        this.parentElement.querySelector(".nested").classList.toggle("active");
        this.classList.toggle("caret-down");
      });
    }
}


function createCallback(fn, param)
{
    // https://stackoverflow.com/questions/750486/javascript-closure-inside-loops-simple-practical-example
    return function() {
        fn(param);
    }
}


function treeNodeHasChildren(node)
{
    var ul_elements = node.getElementsByTagName("ul");
    return ul_elements.length > 0;
}


function addTreeIDCallbacks(tree_id, handler_fn)
{
    // Adds callbacks to all items in a tree.
    // When clicked, they will call handler_fn(css_id_of_item).

    var tree = document.getElementById(tree_id);
    if (tree === null) {
        console.log("Error: no element with ID '" + tree_id + "'");
        return;
    }
    // Find all "<li>" elements within it, EXCEPT those with class "caret":
    var li_elements = tree.getElementsByTagName("li");
    for (var i = 0; i < li_elements.length; i++) {
        var node = li_elements[i];
        if (treeNodeHasChildren(node)) {
            continue;
        }
        // Set callback.
        node.onclick = createCallback(handler_fn, node.id);
    }
}


function setElementClassName(element_id, classname)
{
    var element = document.getElementById(element_id);
    if (element === null) {
        console.log("Error: no element with ID '" + element_id + "'");
        return;
    }
    element.className = classname;
}
